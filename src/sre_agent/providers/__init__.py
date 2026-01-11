"""CI Provider package.

Unified interface for multiple CI/CD platform integrations.
"""

from sre_agent.providers.base_provider import (
    BaseCIProvider,
    FetchedLogs,
    ProviderConfig,
    ProviderRegistry,
    ProviderType,
    WebhookVerificationResult,
)

__all__ = [
    "BaseCIProvider",
    "FetchedLogs",
    "ProviderConfig",
    "ProviderRegistry",
    "ProviderType",
    "WebhookVerificationResult",
]

# Import providers to trigger registration
# These imports must come after the base classes are defined
def register_all_providers():
    """Import all provider implementations to register them."""
    try:
        from sre_agent.providers import gitlab_provider
    except ImportError:
        pass
    try:
        from sre_agent.providers import circleci_provider
    except ImportError:
        pass
    try:
        from sre_agent.providers import jenkins_provider
    except ImportError:
        pass
    try:
        from sre_agent.providers import azuredevops_provider
    except ImportError:
        pass
