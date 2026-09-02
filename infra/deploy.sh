#!/usr/bin/env bash
# Provisions the Azure infrastructure (main.bicep) and then builds/pushes
# the three service images and forces Container Apps to pick them up.
#
# Two phases are needed because of a chicken-and-egg problem: the Container
# Registry doesn't exist until main.bicep creates it, but the Container
# Apps it also creates need an image to exist in that registry to start.
#   1. az deployment group create  — provisions everything (apps included;
#      their first revision will fail to start until step 2 pushes an image)
#   2. az acr build (per service)  — builds each image *in the cloud*, no
#      local Docker daemon required, then az containerapp update forces a
#      fresh revision that pulls it.
#
# Usage:
#   RESOURCE_GROUP=multiagent-rg POSTGRES_ADMIN_PASSWORD='...' ./infra/deploy.sh
#
# Required:
#   POSTGRES_ADMIN_PASSWORD   (or you'll be prompted for it, hidden)
# Optional (defaults shown):
#   RESOURCE_GROUP=multiagent-rg
#   LOCATION=eastus
#   ENVIRONMENT_NAME=multiagent
#   DEPLOY_AZURE_OPENAI=false
#   AZURE_OPENAI_LOCATION=eastus2
#   IMAGE_TAG=latest

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESOURCE_GROUP="${RESOURCE_GROUP:-multiagent-rg}"
LOCATION="${LOCATION:-eastus}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-multiagent}"
DEPLOY_AZURE_OPENAI="${DEPLOY_AZURE_OPENAI:-false}"
AZURE_OPENAI_LOCATION="${AZURE_OPENAI_LOCATION:-eastus2}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

command -v az >/dev/null || { echo "Azure CLI ('az') not found — install it first: https://learn.microsoft.com/cli/azure/install-azure-cli" >&2; exit 1; }
az account show >/dev/null 2>&1 || { echo "Not logged in — run 'az login' first." >&2; exit 1; }

if [ -z "${POSTGRES_ADMIN_PASSWORD:-}" ]; then
  read -r -s -p "PostgreSQL admin password (min 8 chars, not stored anywhere but Key Vault): " POSTGRES_ADMIN_PASSWORD
  echo
fi

echo "==> Resource group: $RESOURCE_GROUP ($LOCATION)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> Deploying infrastructure (main.bicep) — this takes several minutes, mostly Postgres/Redis provisioning."
DEPLOYMENT_NAME="multiagent-$(date +%Y%m%d%H%M%S)"
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --template-file "$REPO_ROOT/infra/main.bicep" \
  --parameters \
    environmentName="$ENVIRONMENT_NAME" \
    postgresAdminPassword="$POSTGRES_ADMIN_PASSWORD" \
    deployAzureOpenAI="$DEPLOY_AZURE_OPENAI" \
    azureOpenAILocation="$AZURE_OPENAI_LOCATION" \
    imageTag="$IMAGE_TAG" \
  --output none

ACR_LOGIN_SERVER=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.containerRegistryLoginServer.value -o tsv)
KEY_VAULT_NAME=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.keyVaultName.value -o tsv)
GATEWAY_URL=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.gatewayUrl.value -o tsv)
ACR_NAME="${ACR_LOGIN_SERVER%%.*}"

echo "==> Infra deployed. Registry: $ACR_LOGIN_SERVER"

for service in gateway orchestrator worker; do
  echo "==> Building $service image in ACR (cloud build, no local Docker needed)..."
  az acr build \
    --registry "$ACR_NAME" \
    --image "multiagent/${service}:${IMAGE_TAG}" \
    --file "$REPO_ROOT/services/${service}/Dockerfile" \
    "$REPO_ROOT" \
    --output none

  echo "==> Forcing $ENVIRONMENT_NAME-${service} to pull the freshly built image..."
  az containerapp update \
    --name "${ENVIRONMENT_NAME}-${service}" \
    --resource-group "$RESOURCE_GROUP" \
    --image "${ACR_LOGIN_SERVER}/multiagent/${service}:${IMAGE_TAG}" \
    --output none
done

echo
echo "==================================================================="
echo "Done."
echo "Gateway URL:   $GATEWAY_URL"
echo "Fetch the gateway API key with:"
echo "  az keyvault secret show --vault-name $KEY_VAULT_NAME --name gateway-api-key --query value -o tsv"
echo
echo "Try it:"
echo "  curl -H \"X-API-Key: \$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name gateway-api-key --query value -o tsv)\" \\"
echo "       -H \"Content-Type: application/json\" \\"
echo "       -d '{\"user_id\":\"alice\",\"message\":\"The VPN is down, can you check system status?\"}' \\"
echo "       ${GATEWAY_URL}/v1/chat"
echo "==================================================================="
