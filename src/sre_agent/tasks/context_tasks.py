"""Celery tasks for building failure context.

These tasks are triggered after event ingestion to aggregate
observability data for RCA.
"""
import logging

from celery import Task

from sre_agent.celery_app import celery_app

logger = logging.getLogger(__name__)


class BaseContextTask(Task):
    """Base task class for context building."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "Context building task failed",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "error": str(exc),
            },
            exc_info=exc,
        )


@celery_app.task(
    bind=True,
    base=BaseContextTask,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def build_failure_context(
    self,
    event_id: str,
    correlation_id: str | None = None,
) -> dict:
    """
    Build failure context bundle for a pipeline event.

    This task:
    1. Loads the event from database
    2. Fetches logs from GitHub
    3. Parses logs for errors/stack traces
    4. Fetches git context (changed files, commit message)
    5. Stores the context bundle
    6. Triggers the next stage (Failure Intelligence)

    Args:
        event_id: UUID of the pipeline event
        correlation_id: Optional correlation ID for tracing

    Returns:
        Dict with context building result
    """
    import asyncio
    from uuid import UUID

    logger.info(
        "Building failure context",
        extra={
            "event_id": event_id,
            "correlation_id": correlation_id,
            "task_id": self.request.id,
        },
    )

    # Run async context building
    result = asyncio.get_event_loop().run_until_complete(
        _build_context_async(event_id, correlation_id)
    )

    return result


async def _build_context_async(
    event_id: str,
    correlation_id: str | None,
) -> dict:
    """Async implementation of context building."""
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from sre_agent.database import async_session_factory
    from sre_agent.models.events import EventStatus, PipelineEvent
    from sre_agent.services.context_builder import ContextBuilder

    async with async_session_factory() as session:
        # Load event from database
        stmt = select(PipelineEvent).where(PipelineEvent.id == UUID(event_id))
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            logger.error(
                "Event not found for context building",
                extra={"event_id": event_id},
            )
            return {
                "event_id": event_id,
                "status": "error",
                "message": "Event not found",
            }

        # Update status to processing
        event.status = EventStatus.PROCESSING.value
        await session.commit()

        # Build context
        builder = ContextBuilder()
        context = await builder.build_context(event)

        # Store context bundle
        # TODO: Store in MinIO or PostgreSQL JSONB column
        # For MVP, we log the summary

        logger.info(
            "Context building completed",
            extra={
                "event_id": event_id,
                "has_stack_traces": context.has_stack_traces,
                "has_test_failures": context.has_test_failures,
                "errors_count": len(context.errors),
                "changed_files": len(context.changed_files),
            },
        )

        # Run RCA analysis
        from sre_agent.intelligence.rca_engine import RCAEngine

        rca_engine = RCAEngine()
        rca_result = rca_engine.analyze(context)

        logger.info(
            "RCA analysis completed",
            extra={
                "event_id": event_id,
                "category": rca_result.classification.category.value,
                "confidence": rca_result.classification.confidence,
                "hypothesis": rca_result.primary_hypothesis.description[:100],
            },
        )

        # Mark as completed
        event.status = EventStatus.COMPLETED.value
        await session.commit()

        return {
            "event_id": event_id,
            "status": "completed",
            "context_summary": {
                "errors": len(context.errors),
                "stack_traces": len(context.stack_traces),
                "test_failures": len(context.test_failures),
                "changed_files": len(context.changed_files),
                "has_logs": context.log_content is not None,
            },
            "rca_summary": {
                "category": rca_result.classification.category.value,
                "confidence": rca_result.classification.confidence,
                "hypothesis": rca_result.primary_hypothesis.description,
                "affected_files": len(rca_result.affected_files),
                "similar_incidents": len(rca_result.similar_incidents),
            },
            "next_step": "ai_fix_generation",
        }


@celery_app.task(bind=True, base=BaseContextTask)
def store_context_bundle(
    self,
    event_id: str,
    context_data: dict,
) -> dict:
    """
    Store a context bundle for later retrieval.

    Args:
        event_id: Event ID
        context_data: Serialized context bundle

    Returns:
        Storage confirmation
    """
    logger.info(
        "Storing context bundle",
        extra={"event_id": event_id, "task_id": self.request.id},
    )

    # TODO: Implement storage in MinIO or PostgreSQL
    # For MVP, this is a placeholder

    return {
        "event_id": event_id,
        "stored": True,
        "storage_location": "database",  # Future: MinIO path
    }
