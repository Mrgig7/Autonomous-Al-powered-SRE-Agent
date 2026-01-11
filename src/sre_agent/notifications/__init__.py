"""Notification system package for SRE Agent.

This package provides enterprise-grade notification capabilities
supporting multiple channels: Slack, Microsoft Teams, Email, PagerDuty,
and custom webhooks.
"""

from sre_agent.notifications.base import (
    BaseNotifier,
    NotificationLevel,
    NotificationPayload,
    NotificationResult,
)
from sre_agent.notifications.manager import NotificationManager

__all__ = [
    "BaseNotifier",
    "NotificationLevel",
    "NotificationPayload",
    "NotificationResult",
    "NotificationManager",
]
