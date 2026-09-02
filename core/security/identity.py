"""'Azure Entra ID (Identity & Access)' + 'Managed Identity' boxes.

Two distinct concerns live here:
1. Validating *inbound* end-user/app bearer tokens issued by Entra ID
   (used by the gateway's auth layer as an alternative to static API keys).
2. Vending credentials the platform's own services use to call *other*
   Azure resources without any secret in config — Managed Identity.
   ``core.llm.azure_openai_provider`` and the Key Vault adapter below both
   use #2 when ``AZURE_USE_MANAGED_IDENTITY=true``.
"""
from __future__ import annotations

from core.config import Settings


class EntraTokenValidationError(Exception):
    pass


async def validate_entra_token(token: str, settings: Settings) -> dict:
    """Validate an Entra ID-issued JWT and return its claims.

    Requires ``AZURE_TENANT_ID`` and ``AZURE_AD_AUDIENCE`` to be configured;
    raises if Entra validation isn't set up so callers don't silently trust
    an unverified token.
    """
    if not settings.entra_tenant_id or not settings.entra_audience:
        raise EntraTokenValidationError("Entra ID validation is not configured")

    import jwt
    from jwt import PyJWKClient

    jwks_client = PyJWKClient(
        f"https://login.microsoftonline.com/{settings.entra_tenant_id}/discovery/v2.0/keys"
    )
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.entra_audience,
            issuer=f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0",
        )
    except jwt.PyJWTError as exc:
        raise EntraTokenValidationError(str(exc)) from exc


def get_managed_identity_credential():
    """Returns a ``DefaultAzureCredential`` for services calling Azure APIs
    directly (outside the LLM/Key Vault adapters, which already wire this
    in themselves)."""
    from azure.identity.aio import DefaultAzureCredential

    return DefaultAzureCredential()
