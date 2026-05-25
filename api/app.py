#!/usr/bin/env python3
"""Flask API — POST /recipe saves a full recipe across all three sheets."""

import functools
import json
import os
import re
from datetime import date

from flask import Flask, jsonify, request
from flask_cors import CORS
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://mpolimen.github.io", "http://localhost:*"]}})

SPREADSHEET_ID    = "1WiEKIPMYBIh0xnART5NQDAUGOXprW8dacOKBfzNXiow"
INDEX_SHEET       = "Recipe Index"
GROCERY_SHEET     = "Grocery List"
TEMPLATE_SHEET    = "Recipe Detail template"
MEAL_LOG_SHEET    = "Meal Log"
SCOPES            = ["https://www.googleapis.com/auth/spreadsheets"]

# Alternating row colors for Recipe Index data rows
ROW_COLORS = [
    {"red": 1.0,   "green": 1.0,   "blue": 1.0},      # white
    {"red": 0.922, "green": 0.961, "blue": 0.922},     # sage #EBF5EB
]
# 0-indexed columns to center-align in Recipe Index: servings, prep, cook, rating
CENTER_COLS = {3, 4, 5, 6}

_service = None


def get_service():
    global _service
    if _service:
        return _service
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        token_path = os.path.join(os.path.dirname(__file__), "token.json")
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
    _service = build("sheets", "v4", credentials=creds)
    return _service


def all_sheet_ids(service) -> dict:
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return {s["properties"]["title"]: s["properties"]["sheetId"]
            for s in meta["sheets"]}


def ensure_meal_log_sheet(service, ids: dict) -> int:
    if MEAL_LOG_SHEET in ids:
        return ids[MEAL_LOG_SHEET]

    resp = service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"addSheet": {"properties": {"title": MEAL_LOG_SHEET}}}]},
    ).execute()
    sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]
    ids[MEAL_LOG_SHEET] = sheet_id

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{MEAL_LOG_SHEET}'!A1:F1",
        valueInputOption="USER_ENTERED",
        body={"values": [["Date", "Recipe Name", "Cuisine", "Servings", "HT Savings ($)", "Notes"]]},
    ).execute()

    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.18, "green": 0.36, "blue": 0.24},
                "textFormat": {
                    "bold": True, "fontSize": 11,
                    "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                },
                "verticalAlignment": "MIDDLE",
                "horizontalAlignment": "CENTER",
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,horizontalAlignment)",
        }}]},
    ).execute()

    return sheet_id


# ── Formatting ───────────────────────────────────────────────────────────────

def format_data_row(service, sheet_id: int, row_index: int, end_col: int = None) -> None:
    bg = ROW_COLORS[row_index % 2]
    row_range = {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1}
    if end_col is not None:
        row_range["startColumnIndex"] = 0
        row_range["endColumnIndex"] = end_col
    requests = [{
        "repeatCell": {
            "range": row_range,
            "cell": {"userEnteredFormat": {
                "backgroundColor": bg,
                "textFormat": {"bold": False, "fontSize": 10},
                "verticalAlignment": "MIDDLE",
                "horizontalAlignment": "LEFT",
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,horizontalAlignment)",
        }
    }]
    for col in CENTER_COLS:
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id,
                      "startRowIndex": row_index, "endRowIndex": row_index + 1,
                      "startColumnIndex": col, "endColumnIndex": col + 1},
            "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}},
            "fields": "userEnteredFormat.horizontalAlignment",
        }})
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID, body={"requests": requests}
    ).execute()


# ── Recipe Detail tab ────────────────────────────────────────────────────────

def create_detail_tab(service, recipe_name: str, sheet_ids: dict) -> int:
    """Duplicate the template and rename it. Returns new sheetId."""
    resp = service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"duplicateSheet": {
            "sourceSheetId": sheet_ids[TEMPLATE_SHEET],
            "insertSheetIndex": len(sheet_ids),
            "newSheetName": recipe_name,
        }}]},
    ).execute()
    return resp["replies"][0]["duplicateSheet"]["properties"]["sheetId"]


def fill_detail_tab(service, recipe_name: str, data: dict) -> None:
    sheet = f"'{recipe_name}'"
    ingredients = data.get("ingredients", [])
    instructions = data.get("instructions", [])

    # Metadata block: labels are already in column A from the template
    meta = [
        [data.get("name", "")],
        [data.get("category", "")],
        [data.get("servings", "")],
        [data.get("prep_time", "")],
        [data.get("cook_time", "")],
        [data.get("rating", "")],
        [data.get("source", "")],
    ]

    # Ingredient rows: A=item, B="qty unit"
    ing_rows = []
    for ing in ingredients:
        if isinstance(ing, dict):
            item = ing.get("item", "")
            qty  = str(ing.get("quantity", ""))
            unit = ing.get("unit", "")
            qty_str = f"{qty} {unit}".strip() if unit else qty
        else:
            item, qty_str = str(ing), ""
        ing_rows.append([item, qty_str])

    # Instruction rows: A="N.", B=step text
    instr_rows = [[f"{i+1}.", step] for i, step in enumerate(instructions)]

    # Layout (1-indexed rows):
    # 1-7  : metadata values in col B
    # 9    : INGREDIENTS header (from template)
    # 10.. : ingredient rows
    # after ingredients: blank, INSTRUCTIONS, instruction rows, blank, NOTES, notes
    ing_start  = 10
    ing_end    = ing_start + max(len(ing_rows), 1)
    instr_head = ing_end + 1
    instr_start = instr_head + 1
    notes_head  = instr_start + max(len(instr_rows), 1) + 1
    notes_start = notes_head + 1

    updates = [{"range": f"{sheet}!B1:B7", "values": meta}]

    if ing_rows:
        updates.append({
            "range": f"{sheet}!A{ing_start}:B{ing_start + len(ing_rows) - 1}",
            "values": ing_rows,
        })

    updates.append({"range": f"{sheet}!A{instr_head}", "values": [["INSTRUCTIONS"]]})
    if instr_rows:
        updates.append({
            "range": f"{sheet}!A{instr_start}:B{instr_start + len(instr_rows) - 1}",
            "values": instr_rows,
        })

    updates.append({"range": f"{sheet}!A{notes_head}", "values": [["NOTES"]]})
    if data.get("notes"):
        updates.append({"range": f"{sheet}!A{notes_start}", "values": [[data["notes"]]]})

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": updates},
    ).execute()


# ── Grocery List ─────────────────────────────────────────────────────────────

def add_to_grocery_list(service, ingredients: list, recipe_name: str,
                        grocery_sheet_id: int) -> None:
    rows = []
    for ing in ingredients:
        if isinstance(ing, dict):
            item     = ing.get("item", "")
            qty      = ing.get("quantity", "")
            unit     = ing.get("unit", "")
            category = ing.get("category", "")
        else:
            item = str(ing)
            qty = unit = category = ""
        rows.append([item, qty, unit, category, recipe_name, ""])

    if not rows:
        return

    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{GROCERY_SHEET}'!A:F",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()

    # Format each appended row: plain text, alternating background, no bold
    updated = result.get("updates", {}).get("updatedRange", "")
    match = re.search(r"!A(\d+):F(\d+)", updated)
    if match:
        start_row = int(match.group(1)) - 1  # 0-based
        end_row   = int(match.group(2))       # exclusive
        format_requests = []
        for row_index in range(start_row, end_row):
            bg = ROW_COLORS[row_index % 2]
            format_requests.append({"repeatCell": {
                "range": {"sheetId": grocery_sheet_id,
                          "startRowIndex": row_index, "endRowIndex": row_index + 1},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": bg,
                    "textFormat": {"bold": False, "fontSize": 10},
                    "verticalAlignment": "MIDDLE",
                    "horizontalAlignment": "LEFT",
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,horizontalAlignment)",
            }})
        if format_requests:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID, body={"requests": format_requests}
            ).execute()


# ── Recipe Index ─────────────────────────────────────────────────────────────

SHEET_BASE_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid="


def add_to_recipe_index(service, data: dict) -> tuple:
    """Append data columns A:H to Recipe Index. Returns (updated_range, row_index)."""
    today = date.today().isoformat()
    row = [[
        today,
        data.get("name", ""),
        data.get("category", "Uncategorized"),
        data.get("servings", ""),
        data.get("prep_time", ""),
        data.get("cook_time", ""),
        data.get("rating", ""),
        data.get("notes", ""),
    ]]
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{INDEX_SHEET}'!A:H",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": row},
    ).execute()
    updated_range = result.get("updates", {}).get("updatedRange", "")
    match = re.search(r":H(\d+)", updated_range)
    row_index = int(match.group(1)) - 1 if match else None
    return updated_range, row_index


def write_index_links(service, index_sheet_id: int, row_index: int,
                      detail_gid: int, grocery_gid: int) -> None:
    """Write hyperlinks into columns I and J AFTER row formatting is applied."""
    bg = ROW_COLORS[row_index % 2]

    def link_cell(url: str, label: str) -> dict:
        return {
            "userEnteredValue": {"stringValue": label},
            "userEnteredFormat": {
                "backgroundColor": bg,
                "verticalAlignment": "MIDDLE",
                "horizontalAlignment": "LEFT",
                "textFormat": {
                    "link": {"uri": url},
                    "foregroundColor": {"red": 0.06, "green": 0.46, "blue": 0.82},
                    "underline": True,
                    "bold": False,
                    "fontSize": 10,
                },
            },
        }

    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{
            "updateCells": {
                "range": {
                    "sheetId": index_sheet_id,
                    "startRowIndex": row_index, "endRowIndex": row_index + 1,
                    "startColumnIndex": 8, "endColumnIndex": 10,
                },
                "rows": [{"values": [
                    link_cell(f"{SHEET_BASE_URL}{detail_gid}",  "View Recipe"),
                    link_cell(f"{SHEET_BASE_URL}{grocery_gid}", "View Grocery"),
                ]}],
                "fields": "userEnteredValue,userEnteredFormat(backgroundColor,verticalAlignment,horizontalAlignment,textFormat)",
            }
        }]},
    ).execute()


# ── Auth middleware ───────────────────────────────────────────────────────────

def require_api_key(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        key      = request.headers.get("X-API-Key", "")
        expected = os.environ.get("API_KEY", "")
        if not expected or key != expected:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/recipe", methods=["POST"])
@require_api_key
def save_recipe():
    """
    Save a full recipe:
      - Creates a Recipe Detail tab (duplicated from template)
      - Appends ingredients to Grocery List
      - Appends a row to Recipe Index with hyperlinks to both
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "'name' is required"}), 400

    try:
        service  = get_service()
        ids      = all_sheet_ids(service)

        detail_gid  = create_detail_tab(service, name, ids)
        fill_detail_tab(service, name, data)

        ingredients = data.get("ingredients", [])
        if ingredients:
            add_to_grocery_list(service, ingredients, name, ids[GROCERY_SHEET])

        updated_range, row_index = add_to_recipe_index(service, data)

        if row_index is not None:
            # Format A:H first, then write links into I:J so they aren't overwritten
            format_data_row(service, ids[INDEX_SHEET], row_index, end_col=8)
            write_index_links(service, ids[INDEX_SHEET], row_index,
                              detail_gid, ids[GROCERY_SHEET])

        return jsonify({
            "status":            "ok",
            "recipe":            name,
            "detail_tab":        name,
            "ingredients_added": len(ingredients),
            "range":             updated_range,
        }), 200

    except HttpError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/log", methods=["POST"])
@require_api_key
def log_recipe():
    """Lightweight index-only entry (used by the local log_recipe.py CLI)."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "'name' is required"}), 400

    try:
        service = get_service()
        ids     = all_sheet_ids(service)
        today   = date.today().isoformat()

        row = [[today, name,
                data.get("category", "Uncategorized"),
                data.get("servings", ""),
                data.get("prep_time", ""),
                data.get("cook_time", ""),
                data.get("rating", ""),
                data.get("notes", "")]]

        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{INDEX_SHEET}'!A:H",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": row},
        ).execute()

        updated_range = result.get("updates", {}).get("updatedRange", "")
        match = re.search(r":H(\d+)", updated_range)
        if match:
            row_index = int(match.group(1)) - 1
            format_data_row(service, ids[INDEX_SHEET], row_index)

        return jsonify({"status": "ok", "range": updated_range, "date": today}), 200

    except HttpError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/meal", methods=["POST"])
@require_api_key
def log_meal():
    """Log a cooked meal to the Meal Log sheet (auto-created if absent)."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "'name' is required"}), 400

    try:
        service = get_service()
        ids     = all_sheet_ids(service)
        sheet_id = ensure_meal_log_sheet(service, ids)
        today   = date.today().isoformat()

        row = [[
            today,
            name,
            data.get("cuisine", ""),
            data.get("servings", ""),
            data.get("ht_savings", ""),
            data.get("notes", ""),
        ]]

        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{MEAL_LOG_SHEET}'!A:F",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": row},
        ).execute()

        updated_range = result.get("updates", {}).get("updatedRange", "")
        match = re.search(r"!A(\d+)", updated_range)
        if match:
            row_index = int(match.group(1)) - 1
            bg = ROW_COLORS[row_index % 2]
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"repeatCell": {
                    "range": {"sheetId": sheet_id,
                              "startRowIndex": row_index, "endRowIndex": row_index + 1},
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": bg,
                        "textFormat": {"bold": False, "fontSize": 10},
                        "verticalAlignment": "MIDDLE",
                        "horizontalAlignment": "LEFT",
                    }},
                    "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,horizontalAlignment)",
                }}]},
            ).execute()

        return jsonify({"status": "ok", "meal": name, "date": today}), 200

    except HttpError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/recipes", methods=["GET"])
def list_recipes():
    """Return all rows from Recipe Index as a list of recipe objects."""
    try:
        service = get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{INDEX_SHEET}'!A2:H",
        ).execute()
        rows = result.get("values", [])
        recipes = []
        for row in rows:
            # Pad to 8 columns in case trailing cells are empty
            row += [""] * (8 - len(row))
            recipes.append({
                "date":      row[0],
                "name":      row[1],
                "category":  row[2],
                "servings":  row[3],
                "prep_time": row[4],
                "cook_time": row[5],
                "rating":    row[6],
                "notes":     row[7],
            })
        return jsonify(recipes), 200
    except HttpError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/recipes/<path:name>", methods=["GET"])
def get_recipe(name: str):
    """Return full detail for a single recipe by name (reads its detail tab)."""
    try:
        service = get_service()

        # Fetch metadata from Recipe Index
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{INDEX_SHEET}'!A2:H",
        ).execute()
        rows   = result.get("values", [])
        meta   = next((r for r in rows if len(r) > 1 and r[1].lower() == name.lower()), None)
        if meta is None:
            return jsonify({"error": "Recipe not found"}), 404
        meta  += [""] * (8 - len(meta))

        # Fetch detail tab
        detail = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{meta[1]}'!A1:B200",
        ).execute()
        cells = detail.get("values", [])

        # Parse detail tab layout: rows 1-7 are metadata (label in A, value in B)
        # Then sections: INGREDIENTS, INSTRUCTIONS, NOTES
        def cell(r, c):
            return cells[r][c] if r < len(cells) and c < len(cells[r]) else ""

        ingredients, instructions, notes = [], [], ""
        section = None
        for i, row in enumerate(cells):
            if i < 7:
                continue
            label = (row[0] if row else "").strip().upper()
            if label == "INGREDIENTS":
                section = "ingredients"
            elif label == "INSTRUCTIONS":
                section = "instructions"
            elif label == "NOTES":
                section = "notes"
            elif section == "ingredients" and row:
                ingredients.append({"item": row[0], "quantity": row[1] if len(row) > 1 else ""})
            elif section == "instructions" and len(row) > 1:
                instructions.append(row[1])
            elif section == "notes" and row:
                notes = row[0]

        return jsonify({
            "date":         meta[0],
            "name":         meta[1],
            "category":     meta[2],
            "servings":     meta[3],
            "prep_time":    meta[4],
            "cook_time":    meta[5],
            "rating":       meta[6],
            "notes":        notes or meta[7],
            "ingredients":  ingredients,
            "instructions": instructions,
        }), 200

    except HttpError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/metrics", methods=["GET"])
def get_metrics():
    """Return aggregate stats for the dashboard."""
    try:
        service = get_service()

        # Recipe Index
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{INDEX_SHEET}'!A2:H",
        ).execute()
        rows = result.get("values", [])

        by_category: dict = {}
        ratings = []
        by_month: dict = {}

        for row in rows:
            row += [""] * (8 - len(row))
            category = row[2] or "Uncategorized"
            by_category[category] = by_category.get(category, 0) + 1
            if row[6]:
                try:
                    ratings.append(float(row[6]))
                except ValueError:
                    pass
            if row[0]:
                month = row[0][:7]
                by_month[month] = by_month.get(month, 0) + 1

        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

        # Meal Log
        ids = all_sheet_ids(service)
        total_meals       = 0
        total_servings    = 0
        total_ht_savings  = 0.0
        meals_by_cuisine: dict  = {}
        meals_by_month: dict    = {}
        monthly_ht_savings: dict = {}

        if MEAL_LOG_SHEET in ids:
            meal_result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'{MEAL_LOG_SHEET}'!A2:F",
            ).execute()
            meal_rows = meal_result.get("values", [])
            total_meals = len(meal_rows)

            for mrow in meal_rows:
                mrow += [""] * (6 - len(mrow))
                if mrow[3]:
                    try:
                        total_servings += int(mrow[3])
                    except ValueError:
                        pass
                savings = 0.0
                if mrow[4]:
                    try:
                        savings = float(mrow[4])
                        total_ht_savings += savings
                    except ValueError:
                        pass
                cuisine = mrow[2] or "Other"
                meals_by_cuisine[cuisine] = meals_by_cuisine.get(cuisine, 0) + 1
                if mrow[0]:
                    month = mrow[0][:7]
                    meals_by_month[month] = meals_by_month.get(month, 0) + 1
                    if savings:
                        monthly_ht_savings[month] = round(
                            monthly_ht_savings.get(month, 0.0) + savings, 2
                        )

        return jsonify({
            "total_recipes":      len(rows),
            "avg_rating":         avg_rating,
            "by_category":        by_category,
            "by_month":           dict(sorted(by_month.items())),
            "total_meals":        total_meals,
            "total_servings":     total_servings,
            "total_ht_savings":   round(total_ht_savings, 2),
            "meals_by_cuisine":   meals_by_cuisine,
            "meals_by_month":     dict(sorted(meals_by_month.items())),
            "monthly_ht_savings": dict(sorted(monthly_ht_savings.items())),
        }), 200

    except HttpError as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
