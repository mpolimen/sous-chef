#!/usr/bin/env python3
"""MCP server — exposes save_recipe as a tool Claude can call directly."""

import os
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

RECIPE_API_URL = "https://recipe-api-476979361711.us-central1.run.app/recipe"

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


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=port)
