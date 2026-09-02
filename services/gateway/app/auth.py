"""'Authentication & Authorization' node inside the AI Gateway box.

Accepts either a static API key (``X-API-Key``, matched against
``GATEWAY_API_KEYS`` — the default for local dev / service-to-service
calls) or an Entra ID bearer JWT (``Authorization: Bearer <token>``) when
``AZURE_TENANT_ID``/``AZURE_AD_AUDIENCE`` are configured.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from core.config import Settings
from core.security.identity import EntraTokenValidationError, validate_entra_token


class Principal:
    def __init__(self, subject: str, method: str) -> None:
        self.subject = subject
        self.method = method


async def authenticate(
    settings: Settings,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Principal:
    if x_api_key:
        if x_api_key not in settings.gateway_api_key_set:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
        return Principal(subject=f"api-key:{x_api_key[:6]}...", method="api_key")

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            claims = await validate_entra_token(token, settings)
        except EntraTokenValidationError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc
        return Principal(subject=claims.get("sub", "entra-user"), method="entra_id")

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Provide an X-API-Key header or an Entra ID Bearer token",
    )
