#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Harris Teeter flyer sync — Cloud Run Job edition.

Identical logic to ht_flyer_sync.py but loads OAuth credentials from
Secret Manager instead of an interactive browser flow.
"""

import base64
import json
import logging
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.cloud import secretmanager
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from playwright.sync_api import sync_playwright

# ── Config ────────────────────────────────────────────────────────────────────

PROJECT_ID    = "personal-494020"
SECRET_NAME   = f"projects/{PROJECT_ID}/secrets/ht-oauth-token/versions/latest"
DRIVE_FOLDER  = "Harris Teeter Flyers"
GMAIL_LABEL   = "harris-teeter"
MAX_FILES     = 10
LOOKBACK_DAYS = 7

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive",
]

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_credentials() -> Credentials:
    sm = secretmanager.SecretManagerServiceClient()
    response = sm.access_secret_version(request={"name": SECRET_NAME})
    token_data = json.loads(response.payload.data.decode("utf-8"))

    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if creds.expired and creds.refresh_token:
        log.info("Refreshing OAuth token")
        creds.refresh(Request())
        # Write refreshed token back so the next run doesn't have to re-auth
        parent = f"projects/{PROJECT_ID}/secrets/ht-oauth-token"
        sm.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": creds.to_json().encode("utf-8")},
            }
        )
        log.info("Refreshed token saved to Secret Manager")

    return creds


# ── Drive helpers ─────────────────────────────────────────────────────────────

def get_folder_id(drive, folder_name: str) -> str:
    resp = drive.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
    ).execute()
    files = resp.get("files", [])
    if not files:
        raise FileNotFoundError(f"Drive folder '{folder_name}' not found")
    return files[0]["id"]


def list_folder_files(drive, folder_id: str) -> list[dict]:
    resp = drive.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, createdTime)",
        orderBy="createdTime asc",
    ).execute()
    return resp.get("files", [])


def already_uploaded(drive, folder_id: str, msg_id: str) -> bool:
    """Return True if a file for this message ID already exists in the folder."""
    resp = drive.files().list(
        q=f"'{folder_id}' in parents and name contains '{msg_id[:8]}' and trashed=false",
        fields="files(id, name)",
    ).execute()
    files = resp.get("files", [])
    if files:
        log.info("Skipping message %s — already uploaded as '%s'", msg_id, files[0]["name"])
        return True
    return False


def enforce_rolling_max(drive, folder_id: str) -> None:
    files = list_folder_files(drive, folder_id)
    count = len(files)
    log.info("Drive folder contains %d file(s)", count)
    if count >= MAX_FILES:
        to_delete = count - (MAX_FILES - 1)
        log.info("Deleting %d oldest file(s) to make room", to_delete)
        for f in files[:to_delete]:
            drive.files().delete(fileId=f["id"]).execute()
            log.info("  Deleted: %s (created %s)", f["name"], f["createdTime"])


def upload_pdf(drive, folder_id: str, pdf_path: str, filename: str) -> str:
    meta   = {"name": filename, "parents": [folder_id]}
    media  = MediaFileUpload(pdf_path, mimetype="application/pdf")
    result = drive.files().create(body=meta, media_body=media, fields="id,name").execute()
    log.info("Uploaded '%s' → Drive file id %s", result["name"], result["id"])
    return result["id"]


# ── Gmail helpers ─────────────────────────────────────────────────────────────

def search_label_emails(gmail, label: str, days: int) -> list[str]:
    query = f"label:{label} newer_than:{days}d"
    resp  = gmail.users().messages().list(userId="me", q=query).execute()
    msgs  = resp.get("messages", [])
    log.info("Gmail query '%s' → %d message(s)", query, len(msgs))
    return [m["id"] for m in msgs]


def get_email_body_html(gmail, msg_id: str) -> str | None:
    msg = gmail.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

    def extract(parts):
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            if "parts" in part:
                result = extract(part["parts"])
                if result:
                    return result
        return None

    payload = msg.get("payload", {})
    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return extract(payload.get("parts", []))


def extract_view_online_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    patterns = re.compile(r"view\s*(online|in\s*browser|this\s*email)", re.IGNORECASE)
    for a in soup.find_all("a", href=True):
        if patterns.search(a.get_text(strip=True)):
            log.info("Found 'View Online' link via anchor text: %s", a["href"][:80])
            return a["href"]

    for td in soup.find_all("td")[:5]:
        for a in td.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "harris" in href.lower():
                log.info("Found candidate link via preheader heuristic: %s", href[:80])
                return href

    log.warning("Could not find 'View Online' link in email body")
    return None


# ── PDF rendering ─────────────────────────────────────────────────────────────

def render_url_to_pdf(url: str, output_path: str) -> None:
    log.info("Rendering URL to PDF: %s", url[:80])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page    = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60_000)
        page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
        )
        browser.close()
    log.info("PDF saved to %s (%d bytes)", output_path, os.path.getsize(output_path))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=== Harris Teeter flyer sync started ===")

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    gmail = build("gmail", "v1", credentials=creds)

    try:
        folder_id = get_folder_id(drive, DRIVE_FOLDER)
        log.info("Drive folder '%s' found (id: %s)", DRIVE_FOLDER, folder_id)
    except FileNotFoundError as e:
        log.error("FATAL: %s", e)
        sys.exit(1)

    try:
        msg_ids = search_label_emails(gmail, GMAIL_LABEL, LOOKBACK_DAYS)
    except HttpError as e:
        log.error("Gmail search failed: %s", e)
        sys.exit(1)

    if not msg_ids:
        log.info("No new Harris Teeter emails found — nothing to do")
        return

    success_count = 0
    for msg_id in msg_ids:
        log.info("--- Processing message %s ---", msg_id)
        try:
            html = get_email_body_html(gmail, msg_id)
            if not html:
                log.warning("No HTML body found in message %s — skipping", msg_id)
                continue

            if already_uploaded(drive, folder_id, msg_id):
                continue

            url = extract_view_online_url(html)
            if not url:
                log.warning("No 'View Online' URL in message %s — skipping", msg_id)
                continue

            datestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            filename  = f"HarrisTeeter_Flyer_{datestamp}_{msg_id[:8]}.pdf"

            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = os.path.join(tmpdir, filename)
                render_url_to_pdf(url, pdf_path)
                enforce_rolling_max(drive, folder_id)
                upload_pdf(drive, folder_id, pdf_path, filename)

            success_count += 1

        except Exception as e:
            log.error("Failed to process message %s: %s", msg_id, e, exc_info=True)

    log.info("=== Done — %d/%d flyer(s) uploaded successfully ===", success_count, len(msg_ids))


if __name__ == "__main__":
    main()
