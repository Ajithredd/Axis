"""
Auth routes — GitLab OAuth2 flow + connector-agnostic auth endpoints.

Supports any connector's OAuth flow through the same endpoints:
  GET  /api/auth/login/{connector_type}     → redirect to OAuth provider
  GET  /api/auth/callback/{connector_type}  → handle OAuth callback
  GET  /api/auth/me                         → current user info
"""

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.connectors.registry import connector_registry

router = APIRouter()

# In-memory state store for OAuth (use Redis in production)
_oauth_states: dict[str, dict] = {}


@router.get("/login/{connector_type}")
async def oauth_login(connector_type: str, request: Request):
    """Start the OAuth flow for a given connector."""
    connector = connector_registry.get(connector_type)
    if not connector:
        raise HTTPException(404, f"Connector '{connector_type}' not found")

    state = secrets.token_urlsafe(32)
    redirect_uri = f"{settings.api_url}/api/auth/callback/{connector_type}"

    auth_url = await connector.get_oauth_url(state, redirect_uri)
    if not auth_url:
        raise HTTPException(400, f"Connector '{connector_type}' does not support OAuth")

    _oauth_states[state] = {"connector_type": connector_type}
    return RedirectResponse(auth_url)


@router.get("/callback/{connector_type}")
async def oauth_callback(
    connector_type: str,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback — exchange code for tokens, create/update user."""
    # Verify state
    state_data = _oauth_states.pop(state, None)
    if not state_data or state_data["connector_type"] != connector_type:
        raise HTTPException(400, "Invalid OAuth state")

    connector = connector_registry.get(connector_type)
    if not connector:
        raise HTTPException(404, f"Connector '{connector_type}' not found")

    redirect_uri = f"{settings.api_url}/api/auth/callback/{connector_type}"
    tokens = await connector.exchange_oauth_code(code, redirect_uri)
    if not tokens:
        raise HTTPException(400, "Failed to exchange OAuth code")

    # For GitLab, fetch user info
    if connector_type == "gitlab":
        from app.connectors.gitlab.client import GitLabClient

        async with GitLabClient(tokens["access_token"]) as client:
            gitlab_user = await client.get_current_user()

        # Find or create user
        result = await db.execute(
            select(User).where(User.gitlab_user_id == gitlab_user["id"])
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                email=gitlab_user.get("email", f"gitlab_{gitlab_user['id']}@axis.local"),
                display_name=gitlab_user.get("name", gitlab_user["username"]),
                avatar_url=gitlab_user.get("avatar_url"),
                gitlab_user_id=gitlab_user["id"],
            )
            db.add(user)

        user.gitlab_access_token = tokens["access_token"]
        user.gitlab_refresh_token = tokens.get("refresh_token")
        await db.flush()

    # Redirect to frontend with user session
    # (In production, use JWT or secure session cookie)
    return RedirectResponse(f"{settings.app_url}?auth=success&user_id={user.id}")


@router.get("/me")
async def get_current_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get current user info (simplified — use JWT in production)."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user ID")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "has_gitlab": user.gitlab_access_token is not None,
    }


@router.get("/connectors")
async def list_available_connectors():
    """List all available connectors and their auth requirements."""
    connectors = connector_registry.list_connectors()
    return {
        ctype: {
            "display_name": info.display_name,
            "description": info.description,
            "icon": info.icon,
            "auth_type": info.auth_type,
        }
        for ctype, info in connectors.items()
    }
