"""Authentication and authorization package.

This package provides enterprise-grade authentication and authorization:
- JWT token management
- OAuth providers (GitHub, Google)
- Role-based access control (RBAC)
- Audit logging
"""

from sre_agent.auth.jwt_handler import (
    JWTHandler,
    TokenPayload,
    create_access_token,
    decode_access_token,
)
from sre_agent.auth.permissions import (
    Permission,
    require_permission,
    require_role,
)
from sre_agent.auth.rbac import (
    UserRole,
    get_role_permissions,
    has_permission,
)

__all__ = [
    "JWTHandler",
    "TokenPayload",
    "create_access_token",
    "decode_access_token",
    "Permission",
    "require_permission",
    "require_role",
    "UserRole",
    "get_role_permissions",
    "has_permission",
]
