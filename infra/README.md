# Deploying to Azure

Bicep templates that provision the "proper" production path for this app:
managed Postgres and Redis instead of containers, the three services
(`gateway`, `orchestrator`, `worker`) as Azure Container Apps, Key Vault for
secrets, a shared managed identity, and Log Analytics/App Insights — no
docker-compose involved. Everything compiles cleanly with the Bicep CLI
(`bicep build infra/main.bicep`, verified with 0 errors/warnings).

## What gets deployed

| Resource | Purpose |
|---|---|
| Container Registry (Basic) | holds the 3 built images |
| User-assigned managed identity | ACR pull, Key Vault secrets, (optionally) Azure OpenAI access — no passwords anywhere |
| Key Vault (RBAC) | `sql-database-url`, `redis-url`, `gateway-api-key`, `appinsights-connection-string` |
| Postgres Flexible Server (Burstable B1ms) | replaces the `postgres` container |
| Azure Cache for Redis (Basic C0) | replaces the `redis` container |
| Log Analytics + Application Insights | Container Apps logs + distributed tracing |
| Container Apps Environment | hosts the 3 services |
| Container App: `<env>-gateway` | external ingress (the only public endpoint) |
| Container App: `<env>-orchestrator` | internal ingress only |
| Container App: `<env>-worker` | internal ingress only, pinned to 1 replica (see caveat below) |
| Azure OpenAI + model deployment | **optional**, off by default (`deployAzureOpenAI=false`) |

Secrets are wired to the containers via Container Apps' **native Key Vault
secret references** — the app itself never calls the Key Vault SDK for
these; Azure resolves them into environment variables at container start
using the managed identity.

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), logged in (`az login`) with a subscription that has quota for these resources
- No local Docker required — images are built in the cloud via `az acr build`
- For `deployAzureOpenAI=true`: your subscription needs Azure OpenAI access, and the model must be available in the chosen region

## Quick start

```bash
RESOURCE_GROUP=multiagent-rg \
LOCATION=eastus \
POSTGRES_ADMIN_PASSWORD='pick-a-strong-one-here' \
./infra/deploy.sh
```

This runs both phases needed (see the script's header comment for why):
1. `az deployment group create` — provisions everything.
2. `az acr build` (×3, cloud-built) + `az containerapp update` (×3) — builds
   each service's image and forces a fresh revision that pulls it.

It prints the gateway URL and the command to fetch your API key from Key
Vault at the end.

### What if I don't want to use the script?

Same two phases, by hand:

```bash
az group create --name multiagent-rg --location eastus

az deployment group create \
  --resource-group multiagent-rg \
  --template-file infra/main.bicep \
  --parameters environmentName=multiagent postgresAdminPassword='...'

# capture outputs
ACR=$(az deployment group show -g multiagent-rg -n main --query properties.outputs.containerRegistryLoginServer.value -o tsv)

# build + push each image, then force a new revision
for svc in gateway orchestrator worker; do
  az acr build --registry "${ACR%%.*}" --image "multiagent/$svc:latest" \
    --file "services/$svc/Dockerfile" .
  az containerapp update --name "multiagent-$svc" --resource-group multiagent-rg \
    --image "$ACR/multiagent/$svc:latest"
done
```

## Configuration reference

All parameters have defaults except `postgresAdminPassword` — see
`main.bicep` for the full list and descriptions. The ones you're most
likely to change:

| Parameter | Default | Notes |
|---|---|---|
| `environmentName` | `multiagent` | lowercase alphanumeric, ≤12 chars — used to build every resource name |
| `postgresAdminPassword` | *(required)* | pass via `--parameters`, never commit it |
| `gatewayApiKey` | random GUID each deploy | **pin an explicit value** if you need it stable across redeploys — see note below |
| `imageTag` | `latest` | bump this (and rebuild/push) for real releases instead of floating `latest` |
| `deployAzureOpenAI` | `false` | see [Enabling Azure OpenAI](#enabling-azure-openai) |
| `enableKeyVaultPurgeProtection` | `false` | leave off while iterating; turn on for real production (irreversible) |
| `minReplicas` / `maxReplicas` | `1` / `3` | applies to gateway + orchestrator; worker is pinned to 1 (see below) |

**`gatewayApiKey` defaults to a fresh random GUID on every deploy that
doesn't pass it explicitly** — convenient for a first deploy, but it means
redeploying without pinning the value rotates the key and breaks any
client using the old one. Pass `--parameters gatewayApiKey='...'`
explicitly once you have real clients depending on it.

## Enabling Azure OpenAI

By default the orchestrator runs on the offline mock LLM (same as
docker-compose with no `.env` set). To use real Azure OpenAI instead:

```bash
DEPLOY_AZURE_OPENAI=true AZURE_OPENAI_LOCATION=eastus2 \
RESOURCE_GROUP=multiagent-rg POSTGRES_ADMIN_PASSWORD='...' \
./infra/deploy.sh
```

This provisions an Azure OpenAI account + a `gpt-4o` deployment, and wires
the orchestrator to it via `AZURE_USE_MANAGED_IDENTITY=true` — no API key
ever touches Key Vault or an env var for this path.

## Verifying the deployment

```bash
GATEWAY_URL=$(az deployment group show -g multiagent-rg -n <deployment-name> --query properties.outputs.gatewayUrl.value -o tsv)
KEY=$(az keyvault secret show --vault-name <kv-name> --name gateway-api-key --query value -o tsv)

curl -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"user_id":"alice","message":"The VPN is down, can you check system status?"}' \
  "$GATEWAY_URL/v1/chat"
```

Check Container Apps logs in the portal, or:
```bash
az containerapp logs show --name multiagent-orchestrator --resource-group multiagent-rg --follow
```

## Updating after a code change

```bash
az acr build --registry <acr-name> --image multiagent/orchestrator:latest \
  --file services/orchestrator/Dockerfile .
az containerapp update --name multiagent-orchestrator --resource-group multiagent-rg \
  --image <acr-login-server>/multiagent/orchestrator:latest
```
(repeat per changed service — `az containerapp update --image` always
creates a fresh revision, even for the same tag, so the new build gets
pulled.)

## Tearing down

```bash
az group delete --name multiagent-rg --yes --no-wait
```

If you deployed with `enableKeyVaultPurgeProtection=true`, the Key Vault
name stays reserved for 90 days after this — pick a different
`environmentName` (or wait) if you redeploy under the same name.

## Known limitations / not included here

Scope was matched to what was asked (managed Postgres/Redis + 3 Container
Apps + Key Vault), not the full reference diagram. Notably absent, and
reasonable next additions if you need them:

- **No VNet / private endpoints** — Postgres is reachable from any Azure
  service (`AllowAllAzureServices` firewall rule), Redis and Key Vault use
  public endpoints with key/RBAC auth. Fine for a first deployment; add a
  VNet + Private Link for the Postgres/Redis/Key Vault boxes' actual
  network-isolation story in the diagram.
- **No API Management** — the `gateway` service plays that role, as
  documented in the main README's architecture mapping.
- **Worker is pinned to 1 replica** — its Redis Streams consumer name is
  currently hardcoded (`core/events/local_queue.py`), so multiple replicas
  would collide as the same consumer. Fix that in code before raising
  `maxReplicas` for the worker.
- **One shared managed identity** for all three services, not one each —
  simpler to wire up, but not least-privilege (e.g. the worker doesn't
  need Azure OpenAI access but technically has the role if
  `deployAzureOpenAI=true`). Split into three identities if that matters
  for your threat model.
- **Cosmos DB / Azure AI Search / Blob Storage are not provisioned** —
  the app's adapters for them exist (`core/data/`) and activate
  automatically if you set their env vars, but this template doesn't
  create those resources. Add modules for them the same way
  `postgres.bicep`/`redis.bicep` were added, if you need them.
