from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sre_agent.adapters.registry import select_adapter
from sre_agent.ai.guardrails import FixGuardrails
from sre_agent.ai.plan_generator import PlanGenerator
from sre_agent.artifacts.provenance import build_provenance_artifact
from sre_agent.database import get_async_session
from sre_agent.explainability.evidence_extractor import (
    attach_operation_links,
    extract_evidence_lines,
)
from sre_agent.fix_pipeline.patch_generator import PatchGenerator
from sre_agent.fix_pipeline.store import FixPipelineRunStore
from sre_agent.intelligence.rca_engine import RCAEngine
from sre_agent.models.events import PipelineEvent
from sre_agent.models.fix_pipeline import FixPipelineRunStatus
from sre_agent.observability.metrics import METRICS, bucket_danger_score
from sre_agent.observability.tracing import start_span
from sre_agent.pr.pr_orchestrator import PROrchestrator
from sre_agent.safety.diff_parser import parse_unified_diff
from sre_agent.safety.policy_models import PlanIntent
from sre_agent.safety.runtime import get_policy_engine
from sre_agent.sandbox.repo_manager import RepoManager
from sre_agent.sandbox.validator import ValidationOrchestrator
from sre_agent.schemas.context import FailureContextBundle
from sre_agent.schemas.fix import (
    FileDiff,
    FixSuggestion,
    GuardrailStatus,
    SafetyStatus,
    SafetyViolation,
)
from sre_agent.schemas.fix_plan import FixPlan
from sre_agent.schemas.intelligence import RCAResult
from sre_agent.schemas.validation import ValidationRequest
from sre_agent.services.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


def _derive_repo_url(event: PipelineEvent) -> str | None:
    repo_info = (event.raw_payload or {}).get("repository") or {}
    for key in ("clone_url", "git_url", "http_url", "http_url_to_repo"):
        if repo_info.get(key):
            return str(repo_info[key])
    if event.ci_provider.value == "github_actions":
        return f"https://github.com/{event.repo}.git"
    return None


def _list_repo_files(repo_path) -> list[str]:
    from pathlib import Path

    root = Path(repo_path)
    out: list[str] = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(".git/"):
            continue
        out.append(rel)
    return out


def _split_file_diffs(combined_diff: str) -> list[FileDiff]:
    diffs: list[FileDiff] = []
    current: list[str] = []
    current_file: str | None = None

    for line in combined_diff.splitlines(keepends=True):
        if line.startswith("--- a/"):
            if current_file and current:
                diff_text = "".join(current)
                added, removed = _count_diff_changes(diff_text)
                diffs.append(
                    FileDiff(
                        filename=current_file,
                        diff=diff_text,
                        lines_added=added,
                        lines_removed=removed,
                    )
                )
            current = [line]
            current_file = line[len("--- a/") :].strip()
            continue
        current.append(line)

    if current_file and current:
        diff_text = "".join(current)
        added, removed = _count_diff_changes(diff_text)
        diffs.append(
            FileDiff(
                filename=current_file,
                diff=diff_text,
                lines_added=added,
                lines_removed=removed,
            )
        )
    return diffs


def _count_diff_changes(diff_text: str) -> tuple[int, int]:
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


class FixPipelineOrchestrator:
    def __init__(
        self,
        store: FixPipelineRunStore | None = None,
        plan_generator: PlanGenerator | None = None,
        patch_generator: PatchGenerator | None = None,
    ):
        self.store = store or FixPipelineRunStore()
        self.plan_generator = plan_generator or PlanGenerator()
        self.patch_generator = patch_generator or PatchGenerator()
        self.repo_manager = RepoManager()
        self.guardrails = FixGuardrails()
        self.validator = ValidationOrchestrator()
        self.pr_orchestrator = PROrchestrator()
        self.policy_engine = get_policy_engine()

    async def run(self, run_id: UUID) -> dict:
        run = await self.store.get_run(run_id)
        if run is None:
            return {"success": False, "error": "run_not_found"}

        async with get_async_session() as session:
            event = await session.get(PipelineEvent, run.event_id)
        if event is None:
            return {"success": False, "error": "event_not_found"}

        timeline: list[dict] = []

        def _step_start(step: str) -> tuple[int, datetime]:
            started = datetime.now(UTC)
            timeline.append(
                {
                    "step": step,
                    "status": "running",
                    "started_at": started.isoformat(),
                    "completed_at": None,
                    "duration_ms": None,
                }
            )
            return len(timeline) - 1, started

        def _step_end(step_index: int, *, status: str, started: datetime) -> None:
            completed = datetime.now(UTC)
            duration_ms = int((completed - started).total_seconds() * 1000)
            step_name = str(timeline[step_index].get("step") or "unknown")
            timeline[step_index] = {
                **timeline[step_index],
                "status": status,
                "completed_at": completed.isoformat(),
                "duration_ms": duration_ms,
            }
            METRICS.pipeline_stage_duration_seconds.labels(stage=step_name).observe(
                max(0.0, duration_ms / 1000.0)
            )

        repo_path = None
        try:
            ingest_idx, ingest_started = _step_start("ingest")
            context, rca = await self._load_or_build_context(event, run_id)
            _step_end(ingest_idx, status="ok", started=ingest_started)

            log_text = (
                context.log_content.raw_content
                if context.log_content is not None
                else (context.log_summary or "")
            )
            adapter_idx, adapter_started = _step_start("adapter_select")
            repo_files_hint = [f.filename for f in (context.changed_files or []) if f.filename]
            selected = select_adapter(log_text, repo_files_hint)
            if selected is None:
                _step_end(adapter_idx, status="fail", started=adapter_started)
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PLAN_BLOCKED.value,
                    error_message="No adapter matched this repository/logs",
                )
                return {"success": False, "error": "no_adapter"}
            _step_end(adapter_idx, status="ok", started=adapter_started)

            await self.store.update_run(
                run_id,
                adapter_name=selected.adapter.name,
                detection_json=selected.detection.model_dump(mode="json"),
            )

            plan_idx, plan_started = _step_start("plan")
            with start_span(
                "generate_plan",
                attributes={
                    "run_id": str(run_id),
                    "failure_id": str(event.id),
                    "run_key": str(getattr(event, "idempotency_key", "") or ""),
                    "language": str(getattr(selected.detection, "language", "") or ""),
                },
            ):
                plan = await self._generate_plan(context, rca, run_id)
            if plan is None:
                _step_end(plan_idx, status="fail", started=plan_started)
                return {"success": False, "error": "plan_failed"}
            _step_end(plan_idx, status="ok", started=plan_started)

            policy_plan_idx, policy_plan_started = _step_start("policy_plan")
            with start_span(
                "policy_check_plan",
                attributes={
                    "run_id": str(run_id),
                    "failure_id": str(event.id),
                    "run_key": str(getattr(event, "idempotency_key", "") or ""),
                    "category": str(getattr(plan, "category", "") or ""),
                },
            ):
                plan_decision = self.policy_engine.evaluate_plan(
                    PlanIntent(
                        target_files=plan.files,
                        category=plan.category,
                        operation_types=[op.type for op in plan.operations],
                    )
                )
            _step_end(
                policy_plan_idx,
                status="ok" if plan_decision.allowed else "fail",
                started=policy_plan_started,
            )
            await self.store.update_run(
                run_id,
                plan_json=plan.model_dump(),
                plan_policy_json=plan_decision.model_dump(),
            )
            for v in plan_decision.violations:
                METRICS.policy_violations_total.labels(type=str(v.code).split(".")[0]).inc()

            if not plan_decision.allowed:
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PLAN_BLOCKED.value,
                    error_message="Plan blocked by safety policy",
                )
                return {
                    "success": False,
                    "error": "plan_blocked",
                    "policy": plan_decision.model_dump(),
                }

            allowed_categories = selected.adapter.allowed_categories()
            if allowed_categories and plan.category not in allowed_categories:
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PLAN_BLOCKED.value,
                    error_message=f"Unsupported plan category: {plan.category}",
                )
                return {"success": False, "error": "unsupported_category"}

            allowed_types = selected.adapter.allowed_fix_types()
            op_types = {str(op.type) for op in plan.operations}
            if not op_types.issubset(allowed_types):
                disallowed = sorted(op_types - allowed_types)
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PLAN_BLOCKED.value,
                    error_message=f"Plan used disallowed fix types: {disallowed}",
                )
                return {"success": False, "error": "disallowed_fix_types"}

            await self.store.update_run(run_id, status=FixPipelineRunStatus.PLAN_READY.value)

            repo_url = _derive_repo_url(event)
            if not repo_url:
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PLAN_BLOCKED.value,
                    error_message="Unsupported repository URL for cloning",
                )
                return {"success": False, "error": "repo_url_missing"}

            clone_idx, clone_started = _step_start("clone")
            repo_path = await self.repo_manager.clone(
                repo_url=repo_url,
                branch=event.branch,
                commit=event.commit_sha,
                depth=50,
            )
            _step_end(clone_idx, status="ok", started=clone_started)

            repo_files = _list_repo_files(repo_path)
            selected_repo = select_adapter(log_text, repo_files) or selected
            if selected_repo.adapter.name != selected.adapter.name:
                selected = selected_repo
                await self.store.update_run(
                    run_id,
                    adapter_name=selected.adapter.name,
                    detection_json=selected.detection.model_dump(mode="json"),
                )

            patch_idx, patch_started = _step_start("patch")
            with start_span(
                "generate_patch",
                attributes={
                    "run_id": str(run_id),
                    "failure_id": str(event.id),
                    "run_key": str(getattr(event, "idempotency_key", "") or ""),
                    "category": str(getattr(plan, "category", "") or ""),
                },
            ):
                patch = self.patch_generator.generate(repo_path, plan)
            _step_end(patch_idx, status="ok", started=patch_started)
            parsed = parse_unified_diff(patch.diff_text)
            touched = {f.path for f in parsed.files}
            plan_files = set(plan.files)
            if touched - plan_files:
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PATCH_BLOCKED.value,
                    error_message="Patch touched files outside plan.files",
                    patch_diff=patch.diff_text,
                    patch_stats_json=patch.stats.as_dict(),
                )
                return {"success": False, "error": "patch_outside_plan"}

            policy_patch_idx, policy_patch_started = _step_start("policy_patch")
            with start_span(
                "policy_check_patch",
                attributes={
                    "run_id": str(run_id),
                    "failure_id": str(event.id),
                    "run_key": str(getattr(event, "idempotency_key", "") or ""),
                },
            ):
                patch_decision = self.policy_engine.evaluate_patch(patch.diff_text)
            _step_end(
                policy_patch_idx,
                status="ok" if patch_decision.allowed else "fail",
                started=policy_patch_started,
            )
            await self.store.update_run(
                run_id,
                patch_diff=patch.diff_text,
                patch_stats_json=patch.stats.as_dict(),
                patch_policy_json=patch_decision.model_dump(),
            )
            for v in patch_decision.violations:
                METRICS.policy_violations_total.labels(type=str(v.code).split(".")[0]).inc()
            METRICS.danger_score_bucket.labels(
                bucket=bucket_danger_score(int(patch_decision.danger_score))
            ).inc()

            if not patch_decision.allowed:
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PATCH_BLOCKED.value,
                    error_message="Patch blocked by safety policy",
                )
                return {
                    "success": False,
                    "error": "patch_blocked",
                    "policy": patch_decision.model_dump(),
                }

            patch_check = self.repo_manager.apply_patch(
                repo_path=repo_path, diff=patch.diff_text, check_only=True
            )
            if not patch_check.success:
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PATCH_BLOCKED.value,
                    error_message=f"Patch does not apply cleanly: {patch_check.error_message}",
                )
                return {"success": False, "error": "patch_not_applicable"}

            fix = self._build_fix_suggestion(
                str(run_id), event.id, plan, patch.diff_text, patch_decision
            )
            guardrail_status: GuardrailStatus = self.guardrails.validate(fix)
            fix.guardrail_status = guardrail_status
            if not guardrail_status.passed:
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PATCH_BLOCKED.value,
                    error_message="Patch blocked by guardrails",
                )
                return {"success": False, "error": "guardrails_blocked"}

            await self.store.update_run(run_id, status=FixPipelineRunStatus.PATCH_READY.value)

            validate_idx, validate_started = _step_start("validate")
            with start_span(
                "sandbox_validate",
                attributes={
                    "run_id": str(run_id),
                    "failure_id": str(event.id),
                    "run_key": str(getattr(event, "idempotency_key", "") or ""),
                    "adapter": str(selected.adapter.name),
                },
            ):
                validation = await self.validator.validate(
                    ValidationRequest(
                        fix_id=str(run_id),
                        event_id=event.id,
                        repo_url=repo_url,
                        branch=event.branch,
                        commit_sha=event.commit_sha,
                        diff=patch.diff_text,
                        adapter_name=selected.adapter.name,
                        validation_steps=(
                            selected.adapter.build_validation_steps(str(repo_path)) or None
                        ),
                    )
                )
            _step_end(
                validate_idx,
                status="ok" if validation.is_successful else "fail",
                started=validate_started,
            )
            with start_span(
                "run_scans",
                attributes={
                    "run_id": str(run_id),
                    "failure_id": str(event.id),
                    "run_key": str(getattr(event, "idempotency_key", "") or ""),
                    "outcome": "ok" if validation.is_successful else "fail",
                },
            ):
                pass
            scans_status = "skipped"
            if validation.scans:
                scans_status = "ok"
                if validation.scans.gitleaks and validation.scans.gitleaks.status.value in {
                    "fail",
                    "error",
                }:
                    scans_status = "fail"
                if validation.scans.trivy and validation.scans.trivy.status.value in {
                    "fail",
                    "error",
                }:
                    scans_status = "fail"
                if validation.scans.gitleaks:
                    METRICS.scan_findings_total.labels(scanner="gitleaks", severity="UNKNOWN").inc(
                        int(validation.scans.gitleaks.findings_count or 0)
                    )
                    if validation.scans.gitleaks.status.value in {"fail", "error"}:
                        METRICS.scan_fail_total.labels(
                            scanner="gitleaks",
                            reason=(
                                "timeout"
                                if "timeout"
                                in str(validation.scans.gitleaks.error_message or "").lower()
                                else (
                                    "error"
                                    if validation.scans.gitleaks.status.value == "error"
                                    else "unknown"
                                )
                            ),
                        ).inc()
                if validation.scans.trivy:
                    for sev, count in (validation.scans.trivy.severity_counts or {}).items():
                        METRICS.scan_findings_total.labels(
                            scanner="trivy", severity=str(sev).upper() or "UNKNOWN"
                        ).inc(int(count or 0))
                    if validation.scans.trivy.status.value in {"fail", "error"}:
                        METRICS.scan_fail_total.labels(
                            scanner="trivy",
                            reason=(
                                "timeout"
                                if "timeout"
                                in str(validation.scans.trivy.error_message or "").lower()
                                else (
                                    "error"
                                    if validation.scans.trivy.status.value == "error"
                                    else "unknown"
                                )
                            ),
                        ).inc()
            timeline.append(
                {
                    "step": "scans",
                    "status": scans_status,
                    "started_at": None,
                    "completed_at": None,
                    "duration_ms": None,
                }
            )

            sbom = validation.scans.sbom if validation.scans else None
            update_fields: dict = {"validation_json": validation.model_dump(mode="json")}
            if sbom and sbom.path and sbom.sha256 and sbom.size_bytes is not None:
                update_fields.update(
                    {
                        "sbom_path": sbom.path,
                        "sbom_sha256": sbom.sha256,
                        "sbom_size_bytes": sbom.size_bytes,
                    }
                )
            await self.store.update_run(run_id, **update_fields)
            if not validation.is_successful:
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.VALIDATION_FAILED.value,
                    error_message=validation.error_message or "Validation failed",
                )
                return {"success": False, "error": "validation_failed"}

            await self.store.update_run(run_id, status=FixPipelineRunStatus.VALIDATION_PASSED.value)

            existing_run = await self.store.get_run(run_id)
            if existing_run and (
                existing_run.last_pr_url
                or (
                    existing_run.pr_json
                    and str(existing_run.pr_json.get("status") or "").lower() == "created"
                )
            ):
                from sre_agent.ops.metrics import inc

                inc(
                    "pr_create_skipped",
                    attributes={"run_id": str(run_id), "reason": "already_created"},
                )
                timeline.append(
                    {
                        "step": "pr_create",
                        "status": "skipped",
                        "started_at": None,
                        "completed_at": None,
                        "duration_ms": None,
                    }
                )
                await self.store.update_run(run_id, status=FixPipelineRunStatus.PR_CREATED.value)
                return {"success": True, "run_id": str(run_id), "skipped": "pr_already_created"}

            pr_idx, pr_started = _step_start("pr_create")
            with start_span(
                "create_pr",
                attributes={
                    "run_id": str(run_id),
                    "failure_id": str(event.id),
                    "run_key": str(getattr(event, "idempotency_key", "") or ""),
                    "pr_label": str(getattr(fix.safety_status, "pr_label", "") or ""),
                },
            ):
                pr_result = await self.pr_orchestrator.create_pr_for_fix(
                    fix=fix,
                    rca_result=rca,
                    validation=validation,
                    repo_url=repo_url,
                    base_branch=event.branch,
                )
            _step_end(
                pr_idx,
                status="ok" if pr_result.status.value == "created" else "fail",
                started=pr_started,
            )
            await self.store.update_run(
                run_id,
                pr_json=pr_result.model_dump(),
                last_pr_url=pr_result.pr_url,
                last_pr_created_at=pr_result.created_at,
            )

            if pr_result.status.value != "created":
                await self.store.update_run(
                    run_id,
                    status=FixPipelineRunStatus.PR_FAILED.value,
                    error_message=pr_result.error_message or "PR creation failed",
                )
                return {"success": False, "error": "pr_failed"}

            METRICS.pr_created_total.labels(
                label=str(getattr(fix.safety_status, "pr_label", "") or "unknown")
            ).inc()
            await self.store.update_run(run_id, status=FixPipelineRunStatus.PR_CREATED.value)
            return {"success": True, "run_id": str(run_id), "pr": pr_result.model_dump()}
        finally:
            try:
                latest = await self.store.get_run(run_id)
                if latest is not None:
                    evidence: list[dict] = []
                    if latest.context_json:
                        log_content = (latest.context_json or {}).get("log_content") or {}
                        raw = (log_content or {}).get("raw_content")
                        summary = (latest.context_json or {}).get("log_summary")
                        log_text = str(raw or summary or "")
                        if log_text:
                            extracted = extract_evidence_lines(log_text, max_lines=30)
                            linked = attach_operation_links(
                                extracted,
                                operations=(
                                    (latest.plan_json or {}).get("operations")
                                    if latest.plan_json
                                    else None
                                ),
                            )
                            evidence = [
                                {
                                    "idx": e.idx,
                                    "line": e.line,
                                    "tag": e.tag,
                                    "operation_idx": e.operation_idx,
                                }
                                for e in linked
                            ]

                    with start_span(
                        "persist_artifact",
                        attributes={
                            "run_id": str(run_id),
                            "failure_id": str(getattr(latest, "event_id", "")),
                            "run_key": str(getattr(event, "idempotency_key", "") or ""),
                        },
                    ):
                        artifact = build_provenance_artifact(
                            run_id=latest.id,
                            failure_id=latest.event_id,
                            repo=event.repo,
                            status=str(getattr(latest, "status", "unknown")),
                            started_at=getattr(latest, "created_at", None),
                            error_message=getattr(latest, "error_message", None),
                            plan_json=getattr(latest, "plan_json", None),
                            plan_policy_json=getattr(latest, "plan_policy_json", None),
                            patch_stats_json=getattr(latest, "patch_stats_json", None),
                            patch_policy_json=getattr(latest, "patch_policy_json", None),
                            validation_json=getattr(latest, "validation_json", None),
                            adapter_name=getattr(latest, "adapter_name", None),
                            detection_json=getattr(latest, "detection_json", None),
                            evidence=evidence,
                            timeline=timeline,
                        )
                        await self.store.update_run(
                            run_id, artifact_json=artifact.model_dump(mode="json")
                        )
            except Exception:
                logger.exception("Failed to persist provenance artifact")

            if repo_path is not None:
                try:
                    self.repo_manager.cleanup(repo_path)
                except Exception:
                    logger.exception("Failed to cleanup repo")

    async def _load_or_build_context(
        self, event: PipelineEvent, run_id: UUID
    ) -> tuple[FailureContextBundle, RCAResult]:
        run = await self.store.get_run(run_id)
        if run and run.context_json and run.rca_json:
            return (
                FailureContextBundle.model_validate(run.context_json),
                RCAResult.model_validate(run.rca_json),
            )

        builder = ContextBuilder()
        context = await builder.build_context(event)
        rca_engine = RCAEngine()
        rca = rca_engine.analyze(context)

        await self.store.update_run(
            run_id, context_json=context.model_dump(), rca_json=rca.model_dump()
        )
        return context, rca

    async def _generate_plan(
        self, context: FailureContextBundle, rca: RCAResult, run_id: UUID
    ) -> FixPlan | None:
        try:
            plan = await self.plan_generator.generate_plan(rca_result=rca, context=context)
            return plan
        except Exception as e:
            await self.store.update_run(
                run_id,
                status=FixPipelineRunStatus.PLAN_BLOCKED.value,
                error_message=f"Plan generation failed: {e}",
            )
            return None

    def _build_fix_suggestion(
        self, fix_id: str, event_id: UUID, plan: FixPlan, diff_text: str, patch_decision
    ) -> FixSuggestion:
        file_diffs = _split_file_diffs(diff_text)
        total_added = sum(d.lines_added for d in file_diffs)
        total_removed = sum(d.lines_removed for d in file_diffs)

        safety_status = SafetyStatus(
            allowed=patch_decision.allowed,
            pr_label=patch_decision.pr_label,
            danger_score=patch_decision.danger_score,
            violations=[
                SafetyViolation(
                    code=v.code,
                    severity=v.severity.value,
                    message=v.message,
                    file_path=v.file_path,
                )
                for v in patch_decision.violations
            ],
            danger_reasons=[r.message for r in patch_decision.danger_reasons],
        )

        summary = f"{plan.category}: {plan.root_cause}".strip()
        explanation = "\n".join(
            [plan.root_cause] + [f"{op.type} {op.file}: {op.rationale}" for op in plan.operations]
        )

        return FixSuggestion(
            event_id=event_id,
            fix_id=fix_id,
            diffs=file_diffs,
            explanation=explanation,
            summary=summary[:200],
            target_files=plan.files,
            confidence=plan.confidence,
            total_lines_added=total_added,
            total_lines_removed=total_removed,
            guardrail_status=GuardrailStatus(passed=True),
            safety_status=safety_status,
            model_used=self.plan_generator.last_model_name or "unknown",
        )


def run_fix_pipeline_sync(run_id: str) -> dict:
    orchestrator = FixPipelineOrchestrator()
    return asyncio.run(orchestrator.run(UUID(run_id)))
