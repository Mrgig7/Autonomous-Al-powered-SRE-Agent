"""Jenkins webhook handler.

Receives Jenkins webhook events via Generic Webhook Trigger plugin.
"""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from sre_agent.core.logging import correlation_id_ctx
from sre_agent.database import get_db_session
from sre_agent.models.events import EventStatus
from sre_agent.providers import ProviderRegistry, ProviderType
from sre_agent.schemas.normalized import WebhookResponse
from sre_agent.services.event_store import EventStore
from sre_agent.tasks.dispatch import process_pipeline_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/jenkins", response_model=WebhookResponse)
async def jenkins_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> WebhookResponse:
    """Jenkins webhook handler for build events."""
    delivery_id = str(uuid4())
    correlation_id_ctx.set(delivery_id)
    
    raw_body = await request.body()
    headers = dict(request.headers)
    
    try:
        provider = ProviderRegistry.get_provider(ProviderType.JENKINS)
    except Exception as e:
        logger.error(f"Failed to get Jenkins provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Jenkins provider not available",
        )
    
    verification = provider.verify_webhook(headers, raw_body)
    
    if not verification.valid:
        logger.warning(f"Jenkins webhook verification failed: {verification.error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=verification.error or "Invalid token",
        )
    
    logger.info(f"Received Jenkins webhook", extra={"delivery_id": delivery_id})
    
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    
    should_process, reason = provider.should_process(payload)
    if not should_process:
        return WebhookResponse(status="ignored", message=reason, correlation_id=delivery_id)
    
    try:
        normalized = provider.normalize_event(payload, delivery_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    event_store = EventStore(session)
    stored_event, is_new = await event_store.store_event(normalized)
    
    if not is_new:
        return WebhookResponse(
            status="ignored",
            message="Duplicate event",
            event_id=stored_event.id,
            correlation_id=delivery_id,
        )
    
    await event_store.update_status(stored_event.id, EventStatus.DISPATCHED)
    await session.commit()
    process_pipeline_event.delay(str(stored_event.id), delivery_id)
    
    return WebhookResponse(
        status="accepted",
        message="Event queued for processing",
        event_id=stored_event.id,
        correlation_id=delivery_id,
    )
