"""GitHub webhook handler.

Receives GitHub Actions webhook events, validates signatures,
normalizes events, stores them idempotently, and dispatches
async processing tasks.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sre_agent.core.logging import correlation_id_ctx
from sre_agent.core.security import get_verified_github_payload
from sre_agent.database import get_db_session
from sre_agent.models.events import EventStatus
from sre_agent.schemas.normalized import WebhookResponse
from sre_agent.services.event_normalizer import GitHubEventNormalizer
from sre_agent.services.event_store import EventStore
from sre_agent.tasks.dispatch import process_pipeline_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github", response_model=WebhookResponse)
async def github_webhook(
    verified_payload: tuple[bytes, str, str] = Depends(get_verified_github_payload),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookResponse:
    """
    GitHub webhook handler for workflow events.

    Receives GitHub Actions webhook events, specifically:
    - workflow_job: Fired when a job starts, completes, or fails

    We only process completed jobs that have failed.

    Flow:
    1. Verify webhook signature (done in dependency)
    2. Parse and validate payload
    3. Filter for relevant events (completed failures only)
    4. Normalize to canonical format
    5. Store idempotently
    6. Dispatch async processing task
    7. Return response

    Returns:
        - 200: Event ignored (not a failure or unsupported event type)
        - 202: Event accepted and queued for processing
        - 400: Invalid payload
        - 401: Invalid signature (handled by dependency)
    """
    raw_body, event_type, delivery_id = verified_payload

    # Set correlation ID for tracing
    correlation_id_ctx.set(delivery_id)

    logger.info(
        "Received GitHub webhook",
        extra={
            "event_type": event_type,
            "delivery_id": delivery_id,
        },
    )

    # Parse JSON payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.warning(
            "Invalid JSON payload",
            extra={"error": str(e), "delivery_id": delivery_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    # Filter for supported event types
    if event_type not in ("workflow_job", "workflow_run"):
        logger.debug(
            "Ignoring unsupported event type",
            extra={"event_type": event_type, "delivery_id": delivery_id},
        )
        return WebhookResponse(
            status="ignored",
            message=f"Event type '{event_type}' is not processed",
            correlation_id=delivery_id,
        )

    # For workflow_job events, check if it's a completed failure
    if event_type == "workflow_job":
        action = payload.get("action")
        conclusion = payload.get("workflow_job", {}).get("conclusion")

        # Only process completed jobs that failed
        if action != "completed":
            logger.debug(
                "Ignoring non-completed job event",
                extra={"action": action, "delivery_id": delivery_id},
            )
            return WebhookResponse(
                status="ignored",
                message=f"Job action '{action}' is not processed (only 'completed')",
                correlation_id=delivery_id,
            )

        if conclusion not in ("failure", "timed_out"):
            logger.debug(
                "Ignoring non-failure job event",
                extra={"conclusion": conclusion, "delivery_id": delivery_id},
            )
            return WebhookResponse(
                status="ignored",
                message=f"Job conclusion '{conclusion}' is not a failure",
                correlation_id=delivery_id,
            )

    # For workflow_run events, check if it's a completed failure
    elif event_type == "workflow_run":
        action = payload.get("action")
        conclusion = payload.get("workflow_run", {}).get("conclusion")

        if action != "completed" or conclusion != "failure":
            logger.debug(
                "Ignoring non-failure run event",
                extra={"action": action, "conclusion": conclusion},
            )
            return WebhookResponse(
                status="ignored",
                message="Workflow run is not a completed failure",
                correlation_id=delivery_id,
            )

        # TODO: Process workflow_run events for run-level summaries
        # For now, we focus on workflow_job for granular failure tracking
        return WebhookResponse(
            status="ignored",
            message="workflow_run events are not processed in MVP (use workflow_job)",
            correlation_id=delivery_id,
        )

    # Normalize the event
    try:
        normalizer = GitHubEventNormalizer()
        normalized_event = normalizer.normalize(
            payload=payload,
            correlation_id=delivery_id,
        )
    except ValueError as e:
        logger.warning(
            "Failed to normalize event",
            extra={"error": str(e), "delivery_id": delivery_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to normalize event: {e}",
        )

    # Store the event idempotently
    event_store = EventStore(session)
    try:
        stored_event, is_new = await event_store.store_event(normalized_event)
    except Exception as e:
        logger.error(
            "Failed to store event",
            extra={"error": str(e), "delivery_id": delivery_id},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
            headers={"Retry-After": "60"},
        )

    # If this is a duplicate, don't dispatch again
    if not is_new:
        logger.info(
            "Duplicate event - skipping dispatch",
            extra={
                "event_id": str(stored_event.id),
                "idempotency_key": normalized_event.idempotency_key,
            },
        )
        return WebhookResponse(
            status="ignored",
            message="Duplicate event - already processed",
            event_id=stored_event.id,
            correlation_id=delivery_id,
        )

    # Dispatch async processing task
    try:
        # Update status to dispatched
        await event_store.update_status(stored_event.id, EventStatus.DISPATCHED)
        await session.commit()

        # Dispatch Celery task
        process_pipeline_event.delay(
            event_id=str(stored_event.id),
            correlation_id=delivery_id,
        )

        logger.info(
            "Event dispatched for processing",
            extra={
                "event_id": str(stored_event.id),
                "repo": normalized_event.repo,
                "failure_type": normalized_event.failure_type,
            },
        )
    except Exception as e:
        logger.error(
            "Failed to dispatch event",
            extra={"error": str(e), "event_id": str(stored_event.id)},
            exc_info=True,
        )
        # Event is stored, so we return success but log the dispatch failure
        # The event can be reprocessed later

    return WebhookResponse(
        status="accepted",
        message="Event accepted and queued for processing",
        event_id=stored_event.id,
        correlation_id=delivery_id,
    )
