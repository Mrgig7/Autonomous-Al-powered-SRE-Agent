from __future__ import annotations

from dataclasses import dataclass

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)
from prometheus_client.exposition import generate_latest
from prometheus_client.metrics import MetricWrapperBase


def _get_or_create(registry: CollectorRegistry, metric: MetricWrapperBase) -> MetricWrapperBase:
    return metric


@dataclass(frozen=True)
class PrometheusMetrics:
    registry: CollectorRegistry
    http_requests_total: Counter
    http_request_duration_seconds: Histogram
    pipeline_runs_total: Counter
    pipeline_stage_duration_seconds: Histogram
    pipeline_retry_total: Counter
    pipeline_loop_blocked_total: Counter
    pipeline_throttled_total: Counter
    pr_created_total: Counter
    policy_violations_total: Counter
    danger_score_bucket: Counter
    scan_findings_total: Counter
    scan_fail_total: Counter
    celery_tasks_total: Counter
    queue_depth: Gauge


_REGISTRY = CollectorRegistry(auto_describe=True)

METRICS = PrometheusMetrics(
    registry=_REGISTRY,
    http_requests_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_http_requests_total",
            "Total HTTP requests by method/route/status",
            labelnames=("method", "route", "status"),
            registry=_REGISTRY,
        ),
    ),
    http_request_duration_seconds=_get_or_create(
        _REGISTRY,
        Histogram(
            "sre_agent_http_request_duration_seconds",
            "HTTP request duration in seconds by route/method",
            labelnames=("route", "method"),
            registry=_REGISTRY,
        ),
    ),
    pipeline_runs_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_pipeline_runs_total",
            "Total pipeline runs by outcome",
            labelnames=("outcome",),
            registry=_REGISTRY,
        ),
    ),
    pipeline_stage_duration_seconds=_get_or_create(
        _REGISTRY,
        Histogram(
            "sre_agent_pipeline_stage_duration_seconds",
            "Pipeline stage duration in seconds by stage",
            labelnames=("stage",),
            registry=_REGISTRY,
            buckets=(
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
                20.0,
                30.0,
                60.0,
                120.0,
                300.0,
                600.0,
            ),
        ),
    ),
    pipeline_retry_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_pipeline_retry_total",
            "Total pipeline retries by reason",
            labelnames=("reason",),
            registry=_REGISTRY,
        ),
    ),
    pipeline_loop_blocked_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_pipeline_loop_blocked_total",
            "Total pipeline loop blocks by reason",
            labelnames=("reason",),
            registry=_REGISTRY,
        ),
    ),
    pipeline_throttled_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_pipeline_throttled_total",
            "Total pipeline throttles by scope",
            labelnames=("scope",),
            registry=_REGISTRY,
        ),
    ),
    pr_created_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_pr_created_total",
            "Total PRs created by label",
            labelnames=("label",),
            registry=_REGISTRY,
        ),
    ),
    policy_violations_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_policy_violations_total",
            "Total safety policy violations by type",
            labelnames=("type",),
            registry=_REGISTRY,
        ),
    ),
    danger_score_bucket=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_danger_score_bucket",
            "Danger score distribution bucketed by ranges",
            labelnames=("bucket",),
            registry=_REGISTRY,
        ),
    ),
    scan_findings_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_scan_findings_total",
            "Total scan findings by scanner and severity",
            labelnames=("scanner", "severity"),
            registry=_REGISTRY,
        ),
    ),
    scan_fail_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_scan_fail_total",
            "Total scan failures by scanner and reason",
            labelnames=("scanner", "reason"),
            registry=_REGISTRY,
        ),
    ),
    celery_tasks_total=_get_or_create(
        _REGISTRY,
        Counter(
            "sre_agent_celery_tasks_total",
            "Total Celery task executions by task and status",
            labelnames=("task", "status"),
            registry=_REGISTRY,
        ),
    ),
    queue_depth=_get_or_create(
        _REGISTRY,
        Gauge(
            "sre_agent_queue_depth",
            "Queue depth as observed from broker backend",
            labelnames=("queue",),
            registry=_REGISTRY,
        ),
    ),
)


def render_prometheus() -> tuple[bytes, str]:
    return generate_latest(METRICS.registry), CONTENT_TYPE_LATEST


def observe_http_request(*, method: str, route: str, status: str, duration_seconds: float) -> None:
    METRICS.http_requests_total.labels(method=method, route=route, status=status).inc()
    METRICS.http_request_duration_seconds.labels(route=route, method=method).observe(
        duration_seconds
    )


def bucket_danger_score(score: int) -> str:
    if score < 0:
        return "lt_0"
    if score <= 10:
        return "0_10"
    if score <= 20:
        return "10_20"
    if score <= 40:
        return "20_40"
    if score <= 60:
        return "40_60"
    if score <= 80:
        return "60_80"
    if score <= 100:
        return "80_100"
    return "100_plus"


def start_worker_metrics_server(*, port: int) -> None:
    start_http_server(port, registry=METRICS.registry)
