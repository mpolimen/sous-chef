#!/usr/bin/env python3
"""One-time setup: create Recipe Index, Recipe Detail template, and Grocery List sheets."""

import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1WiEKIPMYBIh0xnART5NQDAUGOXprW8dacOKBfzNXiow"
CREDS_FILE = os.path.join(os.path.dirname(__file__), "chef-google-creds.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")

SHEETS = [
    {
        "name": "Recipe Index",
        "headers": [["Date Added", "Recipe Name", "Category", "Servings",
                      "Prep Time (min)", "Cook Time (min)", "Rating (1-5)", "Notes"]],
        "cols": 8,
    },
    {
        "name": "Grocery List",
        "headers": [["Item", "Quantity", "Unit", "Category", "Recipe", "Done"]],
        "cols": 6,
    },
]

# Recipe Detail template is a vertical label/value layout, built separately.
DETAIL_TEMPLATE = [
    ["Recipe Name",      ""],
    ["Category",         ""],
    ["Servings",         ""],
    ["Prep Time (min)",  ""],
    ["Cook Time (min)",  ""],
    ["Rating (1-5)",     ""],
    ["Source / URL",     ""],
    [""],
    ["INGREDIENTS",      ""],
    ["",                 ""],
    ["",                 ""],
    ["",                 ""],
    ["",                 ""],
    ["",                 ""],
    [""],
    ["INSTRUCTIONS",     ""],
    ["1.", ""],
    ["2.", ""],
    ["3.", ""],
    ["4.", ""],
    ["5.", ""],
    [""],
    ["NOTES",            ""],
    ["",                 ""],
]


def get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def hex_to_rgb(hex_color: str) -> dict:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    return {"red": r, "green": g, "blue": b}


def header_format_request(sheet_id: int, num_cols: int, bg_hex: str) -> dict:
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": num_cols},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": hex_to_rgb(bg_hex),
                    "textFormat": {"bold": True, "fontSize": 11},
                    "horizontalAlignment": "CENTER",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }
    }


def freeze_row_request(sheet_id: int) -> dict:
    return {
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }
    }


def section_bold_request(sheet_id: int, row: int) -> dict:
    """Bold a single-cell section header in the detail template."""
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": row, "endRowIndex": row + 1,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 11}}},
            "fields": "userEnteredFormat.textFormat",
        }
    }


def setup(service) -> None:
    sheets_api = service.spreadsheets()

    # ── 1. Read existing sheet names so we don't duplicate ──────────────────
    meta = sheets_api.get(spreadsheetId=SPREADSHEET_ID).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"]
                for s in meta["sheets"]}
    print(f"Existing sheets: {list(existing.keys())}")

    # ── 2. Add any missing sheets ────────────────────────────────────────────
    all_sheet_names = [s["name"] for s in SHEETS] + ["Recipe Detail template"]
    add_requests = [
        {"addSheet": {"properties": {"title": name}}}
        for name in all_sheet_names
        if name not in existing
    ]
    if add_requests:
        resp = sheets_api.batchUpdate(
            spreadsheetId=SPREADSHEET_ID, body={"requests": add_requests}
        ).execute()
        for reply in resp.get("replies", []):
            props = reply.get("addSheet", {}).get("properties", {})
            if props:
                existing[props["title"]] = props["sheetId"]
        print(f"Created sheets: {[r['addSheet']['properties']['title'] for r in add_requests]}")
    else:
        print("All sheets already exist — skipping creation.")

    # ── 3. Write headers / template content ─────────────────────────────────
    value_updates = []
    for sheet in SHEETS:
        value_updates.append({
            "range": f"'{sheet['name']}'!A1",
            "values": sheet["headers"],
        })
    value_updates.append({
        "range": "'Recipe Detail template'!A1",
        "values": DETAIL_TEMPLATE,
    })

    sheets_api.values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": value_updates},
    ).execute()
    print("Headers and template content written.")

    # ── 4. Format: bold + colored header rows, freeze ───────────────────────
    colors = {
        "Recipe Index": "#4A7C59",       # dark green
        "Grocery List": "#2E6DA4",       # blue
        "Recipe Detail template": "#7B5EA7",  # purple
    }
    format_requests = []
    for sheet in SHEETS:
        sid = existing[sheet["name"]]
        format_requests.append(header_format_request(sid, sheet["cols"], colors[sheet["name"]]))
        format_requests.append(freeze_row_request(sid))

    # Bold section headers in the detail template
    detail_sid = existing["Recipe Detail template"]
    for row_idx, row in enumerate(DETAIL_TEMPLATE):
        if row and row[0] in ("INGREDIENTS", "INSTRUCTIONS", "NOTES"):
            format_requests.append(section_bold_request(detail_sid, row_idx))

    sheets_api.batchUpdate(
        spreadsheetId=SPREADSHEET_ID, body={"requests": format_requests}
    ).execute()
    print("Formatting applied.")
    print("\nSetup complete.")
    print(f"Sheet URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")


if __name__ == "__main__":
    creds = get_credentials()
    try:
        service = build("sheets", "v4", credentials=creds)
        setup(service)
    except HttpError as err:
        print(f"API error: {err}", file=sys.stderr)
        sys.exit(1)
