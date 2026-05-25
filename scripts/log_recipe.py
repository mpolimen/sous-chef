#!/usr/bin/env python3
"""Append a recipe log entry to the 'Recipe Index' sheet."""

import argparse
import os
import sys
from datetime import date

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1WiEKIPMYBIh0xnART5NQDAUGOXprW8dacOKBfzNXiow"
SHEET_NAME = "Recipe Index"
CREDS_FILE = os.path.join(os.path.dirname(__file__), "chef-google-creds.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")


def get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            # Opens a local browser tab for authorization; falls back to a
            # printed URL if a browser can't be launched (e.g. headless server).
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_FILE}")

    return creds


def append_recipe(
    name: str,
    category: str,
    servings: int,
    prep_time: int,
    cook_time: int,
    rating: str,
    notes: str,
) -> None:
    creds = get_credentials()
    try:
        service = build("sheets", "v4", credentials=creds)
        sheets = service.spreadsheets()

        today = date.today().isoformat()
        # Columns: Date Added | Recipe Name | Category | Servings |
        #          Prep Time (min) | Cook Time (min) | Rating (1-5) | Notes
        row = [[today, name, category, servings, prep_time, cook_time, rating, notes]]

        result = (
            sheets.values()
            .append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A:H",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": row},
            )
            .execute()
        )

        updated_range = result.get("updates", {}).get("updatedRange", "unknown range")
        print(f"Appended row to {updated_range}")
        print(f"  Date:      {today}")
        print(f"  Recipe:    {name}")
        print(f"  Category:  {category}")
        print(f"  Servings:  {servings}")
        print(f"  Prep:      {prep_time} min")
        print(f"  Cook:      {cook_time} min")
        print(f"  Rating:    {rating}")
        print(f"  Notes:     {notes}")

    except HttpError as err:
        print(f"Google Sheets API error: {err}", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append a recipe entry to the Recipe Index sheet."
    )
    parser.add_argument("--name", required=True, help="Recipe name")
    parser.add_argument(
        "--category", default="Uncategorized",
        help="Category (e.g. Dessert, Main, Soup)",
    )
    parser.add_argument("--servings", type=int, default=4, help="Number of servings")
    parser.add_argument("--prep", type=int, default=0, help="Prep time in minutes")
    parser.add_argument("--cook", type=int, default=0, help="Cook time in minutes")
    parser.add_argument("--rating", default="", help="Rating 1-5")
    parser.add_argument("--notes", default="", help="Optional notes")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    append_recipe(
        name=args.name,
        category=args.category,
        servings=args.servings,
        prep_time=args.prep,
        cook_time=args.cook,
        rating=args.rating,
        notes=args.notes,
    )
