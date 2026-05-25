#!/bin/bash
# Deploy recipe-api to Google Cloud Run.
# Run from the chef/ directory: bash deploy.sh
set -euo pipefail

PROJECT_ID="personal-494020"
REGION="us-central1"
SERVICE_NAME="recipe-api"
SA_NAME="recipe-api-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "==> [1/7] Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> [2/7] Creating service account (skipped if it already exists)..."
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="Recipe API" \
  --project="${PROJECT_ID}" 2>/dev/null || true

echo "==> [3/7] Creating service account key and storing in Secret Manager..."
TMP_KEY=$(mktemp)
gcloud iam service-accounts keys create "${TMP_KEY}" \
  --iam-account="${SA_EMAIL}" \
  --project="${PROJECT_ID}"

if gcloud secrets describe recipe-sa-key --project="${PROJECT_ID}" &>/dev/null; then
  gcloud secrets versions add recipe-sa-key \
    --data-file="${TMP_KEY}" --project="${PROJECT_ID}"
else
  gcloud secrets create recipe-sa-key \
    --data-file="${TMP_KEY}" --project="${PROJECT_ID}"
fi
rm -f "${TMP_KEY}"

echo "==> [4/7] Generating API key and storing in Secret Manager..."
if gcloud secrets describe recipe-api-key --project="${PROJECT_ID}" &>/dev/null; then
  # Reuse the existing key so callers don't break
  API_KEY=$(gcloud secrets versions access latest \
    --secret="recipe-api-key" --project="${PROJECT_ID}")
  echo "    (reusing existing API key)"
else
  API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  printf '%s' "${API_KEY}" | gcloud secrets create recipe-api-key \
    --data-file=- --project="${PROJECT_ID}"
fi

echo "==> [5/7] Granting service account access to both secrets..."
for SECRET in recipe-sa-key recipe-api-key; do
  gcloud secrets add-iam-policy-binding "${SECRET}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}"
done

echo "==> [6/7] Building Docker image via Cloud Build..."
gcloud builds submit \
  --tag="${IMAGE}" \
  --project="${PROJECT_ID}" \
  .

echo "==> [7/7] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE}" \
  --platform=managed \
  --region="${REGION}" \
  --service-account="${SA_EMAIL}" \
  --set-secrets="GOOGLE_SERVICE_ACCOUNT_JSON=recipe-sa-key:latest,API_KEY=recipe-api-key:latest" \
  --allow-unauthenticated \
  --project="${PROJECT_ID}"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

echo ""
echo "============================================================"
echo "  Deployment complete!"
echo "  Service URL : ${SERVICE_URL}"
echo "  API Key     : ${API_KEY}"
echo ""
echo "  IMPORTANT — share your Google Sheet with this address:"
echo "  ${SA_EMAIL}"
echo "============================================================"
echo ""
echo "  Health check:"
echo "  curl ${SERVICE_URL}/health"
echo ""
echo "  Log a recipe:"
printf "  curl -X POST %s/log \\\\\n" "${SERVICE_URL}"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H \"X-API-Key: ${API_KEY}\" \\"
echo "    -d '{\"name\": \"Test Recipe\", \"category\": \"Main\", \"servings\": 4}'"
