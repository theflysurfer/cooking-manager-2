"""Verse la moisson en base via l'API, en `a-tester` — ADR 0024."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NOT_A_DINNER = re.compile(
    r"^(?:p[aâ]te [aà] |la p[aâ]te)|ch[aâ]taignes|pur[eé]e de |pois cass[eé]s"
    r"|cr[eê]pes sal[eé]es|fondue bourguignonne|steak tartare|carottes vichy"
    r"|[eé]pinards cr[eé]meux|choux? \(?vert\)? brais|mont d'or",
    re.I,
)

def slugify(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    folded = re.sub(r"\s*:\s*la meilleure recette\s*$", "", folded, flags=re.I)
    folded = re.sub(r"[^a-zA-Z0-9]+", "-", folded).strip("-").lower()
    return re.sub(r"-+", "-", folded)[:80]

def to_payload(recipe: dict) -> dict:
    title = re.sub(r"\s*:\s*la meilleure recette\s*$", "", recipe["title"], flags=re.I)
    servings = recipe.get("servings") or 4
    body = [f"## Ingrédients ({servings} portions)"]
    body += [f"- {line}" for line in recipe["ingredients"]]
    body.append("")
    body.append("## Étapes")
    body += [f"{i}. {step}" for i, step in enumerate(recipe["steps"], start=1)]
    return {
        "title": title,
        "slug": slugify(title),
        "servings": servings,
        "total_time_min": recipe.get("total_time_min"),
        "status": "a-tester",
        "family": "plat",
        "tags": ["moisson-semaine", recipe.get("band", "")],
        "sources": [recipe["source"]],
        "body": "\n".join(body) + "\n",
    }

def post(payload: dict) -> str:
    """L'API est derrière une basic auth nginx : on passe par le VPS."""
    blob = json.dumps(payload, ensure_ascii=False)
    remote = "/tmp/cm2_import.json"
    subprocess.run(
        ["ssh", "srv759970", f"cat > {remote}"],
        input=blob.encode("utf-8"), check=True, capture_output=True,
    )
    done = subprocess.run(
        ["ssh", "srv759970",
         f'curl -s -X POST localhost:8795/api/recipes -H "Content-Type: application/json" -d @{remote}'],
        check=True, capture_output=True,
    )
    return done.stdout.decode("utf-8", "ignore").strip()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", default="data/scraped_weeknight.json")
    args = parser.parse_args()

    harvest = json.loads((ROOT / args.source).read_text(encoding="utf-8"))
    kept, skipped = [], []
    for recipe in harvest["recipes"]:
        if NOT_A_DINNER.search(recipe["title"]):
            skipped.append(recipe["title"])
            continue
        kept.append(to_payload(recipe))

    print(f"{len(kept)} à importer, {len(skipped)} écartés (base ou accompagnement)")
    for title in skipped:
        print("  écarté :", title[:60])
    if args.dry_run:
        for payload in kept:
            print(f"  {payload['slug'][:52]:54} {payload['total_time_min']} min")
        return 0

    for payload in kept:
        print(f"  {payload['slug'][:48]:50} {post(payload)[:70]}", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
