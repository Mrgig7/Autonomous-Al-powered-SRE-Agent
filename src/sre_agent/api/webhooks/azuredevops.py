"""Azure DevOps webhook handler.

Receives Azure DevOps Service Hook events for builds and releases.
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


@router.post("/azuredevops", response_model=WebhookResponse)
async def azuredevops_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> WebhookResponse:
    """Azure DevOps webhook handler for build and release events."""
    delivery_id = str(uuid4())
    correlation_id_ctx.set(delivery_id)
    
    raw_body = await request.body()
    headers = dict(request.headers)
    
    try:
        provider = ProviderRegistry.get_provider(ProviderType.AZURE_DEVOPS)
    except Exception as e:
        logger.error(f"Failed to get Azure DevOps provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure DevOps provider not available",
        )
    
    verification = provider.verify_webhook(headers, raw_body)
    
    if not verification.valid:
        logger.warning(f"Azure DevOps webhook verification failed: {verification.error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=verification.error or "Invalid authentication",
        )
    
    logger.info(f"Received Azure DevOps webhook", extra={"delivery_id": delivery_id})
    
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    
    event_type = payload.get("eventType", "")
    if not event_type.startswith(("build.complete", "ms.vss-release")):
        return WebhookResponse(
            status="ignored",
            message=f"Event type '{event_type}' not processed",
            correlation_id=delivery_id,
        )
    
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
