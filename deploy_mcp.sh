#!/bin/bash
# Deploy the MCP server to Cloud Run as a separate service.
# Run from the chef/ directory: bash deploy_mcp.sh
set -euo pipefail

PROJECT_ID="personal-494020"
REGION="us-central1"
SERVICE_NAME="recipe-mcp"
SA_EMAIL="recipe-api-sa@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "==> Building MCP server image via Cloud Build..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --config=cloudbuild.mcp.yaml \
  .

echo "==> Granting service account access to recipe-api-key secret (idempotent)..."
gcloud secrets add-iam-policy-binding recipe-api-key \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --project="${PROJECT_ID}" 2>/dev/null || true

echo "==> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE}" \
  --platform=managed \
  --region="${REGION}" \
  --service-account="${SA_EMAIL}" \
  --set-secrets="RECIPE_API_KEY=recipe-api-key:latest" \
  --allow-unauthenticated \
  --project="${PROJECT_ID}"

MCP_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

echo ""
echo "============================================================"
echo "  MCP server live!"
echo ""
echo "  Add this URL to your Claude project settings:"
echo "  ${MCP_URL}/mcp"
echo "============================================================"
