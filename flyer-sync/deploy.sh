#!/bin/bash
# Deploy ht_flyer_sync as a Cloud Run Job triggered daily by Cloud Scheduler.
# Run from the flyer-sync/ directory: bash deploy.sh
set -euo pipefail

PROJECT_ID="personal-494020"
REGION="us-central1"
JOB_NAME="ht-flyer-sync"
SA_EMAIL="recipe-api-sa@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="gcr.io/${PROJECT_ID}/${JOB_NAME}"
SECRET_NAME="ht-oauth-token"
SCHEDULE="0 9 * * *"   # Daily 9am UTC

# ── 1. Upload current ht_token.json to Secret Manager ────────────────────────
echo "==> Creating/updating Secret Manager secret '${SECRET_NAME}'..."
if gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud secrets versions add "${SECRET_NAME}" \
    --data-file=../ht_token.json \
    --project="${PROJECT_ID}"
  echo "    Added new version to existing secret."
else
  gcloud secrets create "${SECRET_NAME}" \
    --data-file=../ht_token.json \
    --replication-policy=automatic \
    --project="${PROJECT_ID}"
  echo "    Secret created."
fi

# ── 2. Grant SA access to the secret ─────────────────────────────────────────
echo "==> Granting SA secret access (idempotent)..."
gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --project="${PROJECT_ID}" 2>/dev/null || true

# ── 3. Build image via Cloud Build ───────────────────────────────────────────
echo "==> Building image via Cloud Build (this takes a few minutes — Playwright base is large)..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --config=cloudbuild.yaml \
  .

# ── 4. Deploy Cloud Run Job ───────────────────────────────────────────────────
echo "==> Deploying Cloud Run Job '${JOB_NAME}'..."
if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud run jobs update "${JOB_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --service-account="${SA_EMAIL}" \
    --memory=1Gi \
    --cpu=1 \
    --max-retries=1 \
    --task-timeout=300s \
    --project="${PROJECT_ID}"
else
  gcloud run jobs create "${JOB_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --service-account="${SA_EMAIL}" \
    --memory=1Gi \
    --cpu=1 \
    --max-retries=1 \
    --task-timeout=300s \
    --project="${PROJECT_ID}"
fi

# ── 5. Grant SA permission to invoke the job ─────────────────────────────────
echo "==> Granting SA run.invoker role (idempotent)..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker" 2>/dev/null || true

# ── 6. Create Cloud Scheduler trigger ────────────────────────────────────────
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"

echo "==> Creating/updating Cloud Scheduler job..."
if gcloud scheduler jobs describe "${JOB_NAME}-weekly" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud scheduler jobs update http "${JOB_NAME}-weekly" \
    --schedule="${SCHEDULE}" \
    --uri="${JOB_URI}" \
    --http-method=POST \
    --oauth-service-account-email="${SA_EMAIL}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}"
  echo "    Scheduler job updated."
else
  gcloud scheduler jobs create http "${JOB_NAME}-weekly" \
    --schedule="${SCHEDULE}" \
    --uri="${JOB_URI}" \
    --http-method=POST \
    --oauth-service-account-email="${SA_EMAIL}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}"
  echo "    Scheduler job created."
fi

echo ""
echo "============================================================"
echo "  Deployment complete!"
echo ""
echo "  Schedule : ${SCHEDULE} UTC (daily 9am)"
echo "  Job      : ${JOB_NAME} in ${REGION}"
echo ""
echo "  To trigger a manual test run:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID} --wait"
echo "============================================================"
