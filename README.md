# Personal Chef Assistant

A personal batch-cooking assistant powered by Claude AI. Recipes discussed in Claude are saved directly to a Google Sheet with one command. A weekly cron job scrapes Harris Teeter email flyers, renders them to PDF, and stores them in Google Drive so Claude can factor current deals into meal planning.

## Architecture

```
Claude.ai (chef project)
    │
    ├── mcp/      MCP Server (Cloud Run)         ← Claude calls save_recipe tool directly
    │                   │
    │             api/  Recipe API (Cloud Run)    ← writes to Google Sheets
    │
    └── flyer-sync/  HT Flyer Sync (Cloud Run Job)  ← daily cron, Gmail → PDF → Google Drive
```

## Components

### `api/` — Recipe API
Flask API deployed to Cloud Run. Accepts a `POST /recipe` request and:
- Duplicates the Recipe Detail template tab and fills it with the recipe
- Appends ingredients to the Grocery List sheet
- Appends a row to the Recipe Index with clickable links to both

### `mcp/` — MCP Server
FastMCP server deployed to Cloud Run. Exposes `save_recipe` as a tool that Claude.ai can call natively from a Claude project. Proxies calls through to the Recipe API.

### `flyer-sync/` — HT Flyer Sync
Cloud Run Job triggered daily at 9am UTC by Cloud Scheduler. Searches Gmail for emails labeled `harris-teeter`, extracts the "View Online" link, renders each flyer to PDF via Playwright headless Chromium, and uploads to a Google Drive folder. Keeps a rolling max of 10 PDFs (FIFO). Deduplicates so re-runs never upload the same flyer twice.

### `scripts/` — Utilities
One-time and CLI scripts: `setup_sheets.py` (initial Google Sheet setup) and `log_recipe.py` (local CLI logging).

### `claude-project-instructions.md`
System prompt for the Claude.ai project. Configures Claude as a personal chef assistant with:
- Allergy awareness (peanuts, walnuts, pecans, pistachios, chickpeas)
- Batch cooking focus with work lunch vs. dinner modes
- Recipe logging flow that calls `save_recipe` via MCP
- Harris Teeter deal awareness via the Drive flyer folder

## Google Sheets Structure

| Tab | Purpose |
|-----|---------|
| Recipe Index | One row per recipe with links to detail tab and grocery list |
| Recipe Detail `<name>` | Full recipe (duplicated from template per save) |
| Recipe Detail template | Template tab — do not modify |
| Grocery List | All ingredients across all recipes, tagged by recipe |

## Setup

### Prerequisites
- Google Cloud project with billing enabled
- `gcloud` CLI authenticated
- Google Sheets API, Gmail API, Drive API, Secret Manager API enabled
- A Google Sheet set up with the three template tabs (run `setup_sheets.py` once)

### 1. OAuth credentials
Create a Desktop OAuth client in Google Cloud Console and save as `chef-google-creds.json`.

### 2. Deploy Recipe API
```bash
cd api && bash deploy.sh
```
This builds and pushes the Docker image, deploys to Cloud Run, and wires up the `GOOGLE_SERVICE_ACCOUNT_JSON` and `API_KEY` secrets from Secret Manager.

### 3. Deploy MCP Server
```bash
cd mcp && bash deploy.sh
```
Add the printed `/mcp` URL as a custom connector in your Claude.ai project settings.

### 4. Deploy HT Flyer Sync
First authorize OAuth locally (opens a browser):
```bash
python3 flyer-sync/ht_flyer_sync.py
```
Then deploy to Cloud Run Jobs + Cloud Scheduler:
```bash
cd flyer-sync && bash deploy.sh
```

### 5. Configure Claude project
Paste the contents of `claude-project-instructions.md` into your Claude.ai project instructions. Add the Google Drive connector so Claude can read flyer PDFs.

## GCP Resources

| Resource | Purpose | Cost |
|----------|---------|------|
| Cloud Run (recipe-api) | Recipe save API | Free tier |
| Cloud Run (recipe-mcp) | MCP tool server | Free tier |
| Cloud Run Job (ht-flyer-sync) | Daily flyer sync | Free tier |
| Cloud Scheduler | Triggers daily job | Free tier |
| Secret Manager | API keys & OAuth token | Free tier |
| Container Registry | Docker images | ~$0.10–0.20/month |

Set a billing budget alert at $1/month as a safeguard:
```bash
gcloud billing budgets create \
  --billing-account=<BILLING_ACCOUNT_ID> \
  --display-name="GCP Spending Alert" \
  --budget-amount=1USD \
  --threshold-rule=percent=0.5,basis=current-spend \
  --threshold-rule=percent=1.0,basis=current-spend
```

## Environment Variables & Secrets

| Secret | Used by | Description |
|--------|---------|-------------|
| `recipe-api-key` | recipe-api, recipe-mcp | API key for the recipe endpoint |
| `google-service-account-key` | recipe-api | Service account JSON for Sheets access |
| `ht-oauth-token` | ht-flyer-sync | OAuth token JSON for Gmail + Drive access |

## Manual Operations

**Trigger a flyer sync immediately:**
```bash
gcloud run jobs execute ht-flyer-sync --region=us-central1 --project=<PROJECT_ID> --wait
```

**Pause the daily sync:**
```bash
gcloud scheduler jobs pause ht-flyer-sync-weekly --location=us-central1 --project=<PROJECT_ID>
```

**Emergency shutdown (all services):**
```bash
gcloud scheduler jobs pause ht-flyer-sync-weekly --location=us-central1 --project=<PROJECT_ID>
gcloud run services delete recipe-api --region=us-central1 --project=<PROJECT_ID>
gcloud run services delete recipe-mcp --region=us-central1 --project=<PROJECT_ID>
gcloud run jobs delete ht-flyer-sync --region=us-central1 --project=<PROJECT_ID>
```
