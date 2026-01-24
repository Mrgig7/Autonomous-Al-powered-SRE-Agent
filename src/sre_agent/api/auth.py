"""Authentication API routes.

This module provides REST endpoints for:
- User authentication (login/logout)
- OAuth flows (GitHub, Google)
- Token management (refresh, revoke)
- User profile management
"""

import logging
import secrets
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from sre_agent.auth.jwt_handler import TokenPayload, get_jwt_handler
from sre_agent.auth.permissions import get_current_user
from sre_agent.auth.rbac import UserRole, get_role_permissions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


# Request/Response Models
class LoginRequest(BaseModel):
    """Email/password login request."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class UserProfileResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    name: str
    role: str
    permissions: list[str]
    avatar_url: Optional[str] = None
    created_at: str
    last_login_at: Optional[str] = None


class OAuthInitResponse(BaseModel):
    """OAuth initialization response."""

    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request."""

    code: str
    state: str


# In-memory state storage (use Redis in production)
_oauth_states: dict[str, dict[str, Any]] = {}


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate user with email and password.

    Returns access and refresh tokens on success.
    """
    # TODO: In production, validate against database
    # This is a placeholder implementation

    # For demo purposes, accept any valid email/password combo
    # In production, hash and verify against stored password

    jwt_handler = get_jwt_handler()

    # Simulate user lookup (replace with actual DB query)
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    role = UserRole.OPERATOR
    permissions = [p.value for p in get_role_permissions(role)]

    access_token = jwt_handler.create_access_token(
        user_id=user_id,
        email=request.email,
        role=role.value,
        permissions=permissions,
    )

    refresh_token = jwt_handler.create_refresh_token(
        user_id=user_id,
        email=request.email,
    )

    logger.info(f"User logged in: {request.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=jwt_handler.access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(request: RefreshTokenRequest) -> TokenResponse:
    """Get a new access token using a refresh token."""
    jwt_handler = get_jwt_handler()

    # Verify refresh token
    payload = jwt_handler.verify_token(request.refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Get user's current role and permissions (would query DB in production)
    role = UserRole.OPERATOR
    permissions = [p.value for p in get_role_permissions(role)]

    new_access_token = jwt_handler.create_access_token(
        user_id=payload.user_id,
        email=payload.email,
        role=role.value,
        permissions=permissions,
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=request.refresh_token,  # Keep same refresh token
        token_type="bearer",
        expires_in=jwt_handler.access_token_expire_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke tokens",
)
async def logout(
    request: Request,
    user: TokenPayload = Depends(get_current_user),
) -> None:
    """Logout user and revoke their tokens."""
    jwt_handler = get_jwt_handler()

    # Get token from header and revoke
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        jwt_handler.revoke_token(token)

    logger.info(f"User logged out: {user.email}")


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
async def get_profile(
    user: TokenPayload = Depends(get_current_user),
) -> UserProfileResponse:
    """Get the current authenticated user's profile."""
    return UserProfileResponse(
        id=str(user.user_id),
        email=user.email,
        name=user.email.split("@")[0],  # Placeholder
        role=user.role,
        permissions=user.permissions,
        avatar_url=None,
        created_at=user.iat.isoformat(),
        last_login_at=datetime.utcnow().isoformat(),
    )


@router.get(
    "/permissions",
    summary="Get current user's permissions",
)
async def get_permissions(
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current user's role and permissions."""
    role = UserRole(user.role)
    all_permissions = get_role_permissions(role)

    return {
        "role": user.role,
        "permissions": [p.value for p in all_permissions],
        "permission_count": len(all_permissions),
    }


# OAuth Endpoints
@router.get(
    "/oauth/github",
    response_model=OAuthInitResponse,
    summary="Initialize GitHub OAuth flow",
)
async def oauth_github_init() -> OAuthInitResponse:
    """Start GitHub OAuth authorization flow."""
    from sre_agent.config import get_settings

    settings = get_settings()

    if not settings.github_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth not configured",
        )

    from sre_agent.auth.oauth_providers import GitHubOAuthProvider

    provider = GitHubOAuthProvider(
        client_id=settings.github_oauth_client_id,
        client_secret=settings.github_oauth_client_secret,
        redirect_uri=settings.github_oauth_redirect_uri,
    )

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "provider": "github",
        "created_at": datetime.utcnow(),
    }

    return OAuthInitResponse(
        authorization_url=provider.get_authorization_url(state),
        state=state,
    )


@router.post(
    "/oauth/github/callback",
    response_model=TokenResponse,
    summary="Handle GitHub OAuth callback",
)
async def oauth_github_callback(request: OAuthCallbackRequest) -> TokenResponse:
    """Complete GitHub OAuth flow and issue tokens."""
    from sre_agent.config import get_settings

    settings = get_settings()

    # Verify state
    if request.state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    del _oauth_states[request.state]

    from sre_agent.auth.oauth_providers import GitHubOAuthProvider, OAuthError

    provider = GitHubOAuthProvider(
        client_id=settings.github_oauth_client_id,
        client_secret=settings.github_oauth_client_secret,
        redirect_uri=settings.github_oauth_redirect_uri,
    )

    try:
        access_token = await provider.exchange_code(request.code)
        user_info = await provider.get_user_info(access_token)
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await provider.close()

    # Create or update user in database (placeholder)
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    role = UserRole.OPERATOR
    permissions = [p.value for p in get_role_permissions(role)]

    jwt_handler = get_jwt_handler()

    new_access_token = jwt_handler.create_access_token(
        user_id=user_id,
        email=user_info.email,
        role=role.value,
        permissions=permissions,
    )

    refresh_token = jwt_handler.create_refresh_token(
        user_id=user_id,
        email=user_info.email,
    )

    logger.info(f"User authenticated via GitHub: {user_info.email}")

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=jwt_handler.access_token_expire_minutes * 60,
    )


@router.get(
    "/oauth/google",
    response_model=OAuthInitResponse,
    summary="Initialize Google OAuth flow",
)
async def oauth_google_init() -> OAuthInitResponse:
    """Start Google OAuth authorization flow."""
    from sre_agent.config import get_settings

    settings = get_settings()

    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured",
        )

    from sre_agent.auth.oauth_providers import GoogleOAuthProvider

    provider = GoogleOAuthProvider(
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        redirect_uri=settings.google_oauth_redirect_uri,
    )

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "provider": "google",
        "created_at": datetime.utcnow(),
    }

    return OAuthInitResponse(
        authorization_url=provider.get_authorization_url(state),
        state=state,
    )


@router.post(
    "/oauth/google/callback",
    response_model=TokenResponse,
    summary="Handle Google OAuth callback",
)
async def oauth_google_callback(request: OAuthCallbackRequest) -> TokenResponse:
    """Complete Google OAuth flow and issue tokens."""
    from sre_agent.config import get_settings

    settings = get_settings()

    # Verify state
    if request.state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    del _oauth_states[request.state]

    from sre_agent.auth.oauth_providers import GoogleOAuthProvider, OAuthError

    provider = GoogleOAuthProvider(
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        redirect_uri=settings.google_oauth_redirect_uri,
    )

    try:
        access_token = await provider.exchange_code(request.code)
        user_info = await provider.get_user_info(access_token)
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await provider.close()

    # Create or update user in database (placeholder)
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    role = UserRole.OPERATOR
    permissions = [p.value for p in get_role_permissions(role)]

    jwt_handler = get_jwt_handler()

    new_access_token = jwt_handler.create_access_token(
        user_id=user_id,
        email=user_info.email,
        role=role.value,
        permissions=permissions,
    )

    refresh_token = jwt_handler.create_refresh_token(
        user_id=user_id,
        email=user_info.email,
    )

    logger.info(f"User authenticated via Google: {user_info.email}")

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=jwt_handler.access_token_expire_minutes * 60,
    )
