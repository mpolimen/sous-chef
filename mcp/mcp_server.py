#!/usr/bin/env python3
"""MCP server — exposes save_recipe as a tool Claude can call directly."""

import os
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

RECIPE_API_URL = "https://recipe-api-476979361711.us-central1.run.app/recipe"
MEAL_API_URL   = "https://recipe-api-476979361711.us-central1.run.app/meal"

# Disable localhost-only DNS rebinding protection — Cloud Run provides HTTPS
mcp = FastMCP(
    "Chef Recipe Book",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
def save_recipe(
    name: str,
    category: str,
    servings: int,
    prep_time: int,
    cook_time: int,
    ingredients: list[dict],
    instructions: list[str],
    rating: str = "",
    source: str = "",
    notes: str = "",
) -> str:
    """
    Save a confirmed recipe to the Recipe Book Google Sheet.

    Creates a Recipe Detail tab, appends ingredients to the Grocery List,
    and logs a linked entry in the Recipe Index.

    Args:
        name:         Recipe name
        category:     One of: Main, Soup, Dessert, Breakfast, Snack, Vegetarian, Other
        servings:     Number of portions
        prep_time:    Prep time in minutes
        cook_time:    Cook time in minutes
        ingredients:  List of dicts — each must have:
                        item (str), quantity (str), unit (str),
                        category (Produce | Proteins | Dairy/Refrigerated |
                                  Pantry/Dry Goods | Frozen | Other)
        instructions: List of step strings, in order
        rating:       Optional 1–5 rating as string
        source:       Optional source or URL
        notes:        Storage instructions, freezability, reheating tips
    """
    payload = {
        "name": name,
        "category": category,
        "servings": servings,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "rating": rating,
        "source": source,
        "notes": notes,
        "ingredients": ingredients,
        "instructions": instructions,
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            RECIPE_API_URL,
            json=payload,
            headers={"X-API-Key": os.environ["RECIPE_API_KEY"]},
        )
        response.raise_for_status()
        data = response.json()

    return (
        f"Saved '{name}' to Recipe Book — "
        f"detail tab created, {data.get('ingredients_added', 0)} ingredients logged to grocery list."
    )


@mcp.tool()
def log_meal(
    name: str,
    cuisine: str,
    servings: int = 0,
    ht_savings: float = 0.0,
    notes: str = "",
) -> str:
    """
    Log a meal that was actually cooked today.

    Call this when the user says they made, cooked, or prepared a recipe.
    Infer cuisine from the recipe name (e.g. Greek, Italian, American, Asian, Mexican, Mediterranean, etc.)

    Args:
        name:        Recipe name (match a saved recipe when possible)
        cuisine:     Cuisine type inferred from the recipe
        servings:    Number of servings made (0 if unknown)
        ht_savings:  Dollar amount saved using Harris Teeter flyer deals (0.0 if none)
        notes:       Optional notes (substitutions, variations, how it turned out)
    """
    payload = {
        "name":       name,
        "cuisine":    cuisine,
        "servings":   servings or "",
        "ht_savings": ht_savings or "",
        "notes":      notes,
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            MEAL_API_URL,
            json=payload,
            headers={"X-API-Key": os.environ["RECIPE_API_KEY"]},
        )
        response.raise_for_status()

    savings_str = f" (saved ${ht_savings:.2f} with HT deals)" if ht_savings else ""
    return f"Logged '{name}' ({cuisine}) to Meal Log{savings_str}."


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=port)
