"""'Azure Key Vault (Secrets)' box.

Every other adapter in this codebase reads secrets from environment
variables (``core.config.Settings``) for simplicity and to work in plain
Docker Compose. In an actual Azure deployment, populate those same
environment variables at container-start time by resolving them from Key
Vault here — Container Apps' native Key Vault secret references are the
simpler alternative and need no code at all, but this function is provided
for setups (AKS, custom scripts) that need to pull secrets in-process via
Managed Identity.
"""
from __future__ import annotations


async def resolve_secret(vault_uri: str, secret_name: str) -> str:
    from azure.identity.aio import DefaultAzureCredential
    from azure.keyvault.secrets.aio import SecretClient

    async with DefaultAzureCredential() as credential, SecretClient(vault_uri, credential) as client:
        secret = await client.get_secret(secret_name)
        return secret.value
