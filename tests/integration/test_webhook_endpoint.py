"""Integration tests for webhook API endpoint."""
import hashlib
import hmac
import json
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class TestGitHubWebhookEndpoint:
    """Integration tests for GitHub webhook endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Health endpoint should return 200."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_missing_event_header_returns_400(self, client: TestClient) -> None:
        """Missing X-GitHub-Event header should return 400."""
        response = client.post(
            "/webhooks/github",
            content=b"{}",
            headers={
                "X-GitHub-Delivery": "test-delivery-id",
            },
        )

        assert response.status_code == 400
        assert "X-GitHub-Event" in response.json()["detail"]

    def test_missing_delivery_header_returns_400(self, client: TestClient) -> None:
        """Missing X-GitHub-Delivery header should return 400."""
        response = client.post(
            "/webhooks/github",
            content=b"{}",
            headers={
                "X-GitHub-Event": "workflow_job",
            },
        )

        assert response.status_code == 400
        assert "X-GitHub-Delivery" in response.json()["detail"]

    def test_unsupported_event_type_returns_ignored(self, client: TestClient) -> None:
        """Unsupported event type should return 200 with ignored status."""
        response = client.post(
            "/webhooks/github",
            content=b"{}",
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-id",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_non_completed_job_returns_ignored(
        self,
        client: TestClient,
        sample_github_workflow_job_payload: dict[str, Any],
    ) -> None:
        """Non-completed job action should be ignored."""
        payload = sample_github_workflow_job_payload.copy()
        payload["action"] = "in_progress"

        response = client.post(
            "/webhooks/github",
            content=json.dumps(payload).encode(),
            headers={
                "X-GitHub-Event": "workflow_job",
                "X-GitHub-Delivery": "test-delivery-id",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_successful_job_returns_ignored(
        self,
        client: TestClient,
        sample_github_workflow_job_success_payload: dict[str, Any],
    ) -> None:
        """Successful job should be ignored."""
        response = client.post(
            "/webhooks/github",
            content=json.dumps(sample_github_workflow_job_success_payload).encode(),
            headers={
                "X-GitHub-Event": "workflow_job",
                "X-GitHub-Delivery": "test-delivery-id",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    @patch("sre_agent.api.webhooks.github.EventStore")
    @patch("sre_agent.api.webhooks.github.process_pipeline_event")
    def test_failed_job_is_accepted(
        self,
        mock_task: Any,
        mock_store_class: Any,
        client: TestClient,
        sample_github_workflow_job_payload: dict[str, Any],
    ) -> None:
        """Failed job should be accepted and processed."""
        from uuid import uuid4
        from unittest.mock import AsyncMock, MagicMock

        # Mock the event store
        mock_event = MagicMock()
        mock_event.id = uuid4()
        mock_store = AsyncMock()
        mock_store.store_event.return_value = (mock_event, True)
        mock_store.update_status = AsyncMock()
        mock_store_class.return_value = mock_store

        # Mock Celery task
        mock_task.delay = MagicMock()

        response = client.post(
            "/webhooks/github",
            content=json.dumps(sample_github_workflow_job_payload).encode(),
            headers={
                "X-GitHub-Event": "workflow_job",
                "X-GitHub-Delivery": "test-delivery-id",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_id"] is not None

    def test_invalid_json_returns_400(self, client: TestClient) -> None:
        """Invalid JSON payload should return 400."""
        response = client.post(
            "/webhooks/github",
            content=b"not valid json",
            headers={
                "X-GitHub-Event": "workflow_job",
                "X-GitHub-Delivery": "test-delivery-id",
            },
        )

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]
