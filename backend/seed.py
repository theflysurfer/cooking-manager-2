"""Seed the database from an existing cuisine.json file."""

import asyncio
import json
import sys
from pathlib import Path

from .db import get_pool, init_schema
from .ingest import UPSERT_RECIPE, _recipe_row, _menu_row, UPSERT_MENU


async def seed(json_path: str, dsn: str):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    await init_schema(dsn)
    pool = await get_pool(dsn)

    async with pool.acquire() as conn:
        for r in data.get("recipes", []):
            await conn.execute(UPSERT_RECIPE, *_recipe_row(r))

        await conn.execute("DELETE FROM menu")
        for m in data.get("menus", []):
            await conn.execute(UPSERT_MENU, *_menu_row(m))

    print(f"Seeded {len(data.get('recipes', []))} recipes, {len(data.get('menus', []))} menus")
    await (await get_pool(dsn)).close()


if __name__ == "__main__":
    dsn = sys.argv[2] if len(sys.argv) > 2 else "postgresql://cooking:cooking@127.0.0.1:5432/cooking_manager"
    asyncio.run(seed(sys.argv[1], dsn))
