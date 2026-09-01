#!/usr/bin/env python3
"""Propose les lignes de pantry_item qui décrivent le même aliment (ADR 0002)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_STOPWORDS = {"de", "du", "des", "d", "au", "aux", "a", "la", "le", "les", "en", "et", "l"}
_PACKAGING = re.compile(r"^(x\d+|\d+|kg|g|ml|cl|l|pieces?|paquets?|boites?|sachets?)$")


def _significant_words(normalized: str) -> list[str]:
    """Mots porteurs d'identité, au singulier, sans conditionnement."""
    words = []
    for raw in normalized.split():
        if _PACKAGING.match(raw) or raw in _STOPWORDS:
            continue
        singular = re.sub(r"(?<=\w\w)[sx]$", "", raw)
        words.append(singular)
    return words


@dataclass
class Row:
    id: int
    name: str
    name_normalized: str
    section: str
    qty_text: str
    status: str
    source: str
    updated_at: str = ""


@dataclass
class Candidate:
    canonical: Row
    other: Row
    reason: str
    conflicting: bool = False


@dataclass
class Report:
    candidates: list[Candidate] = field(default_factory=list)


def find_candidates(rows: list[Row]) -> list[Candidate]:
    """Paires dont le mot de tête coïncide et dont les mots de l'une couvrent l'autre."""
    words = {r.id: _significant_words(r.name_normalized) for r in rows}
    out: list[Candidate] = []
    for i, a in enumerate(rows):
        wa = words[a.id]
        if not wa:
            continue
        for b in rows[i + 1:]:
            wb = words[b.id]
            if not wb or wa[0] != wb[0]:
                continue
            sa, sb = set(wa), set(wb)
            if not (sa <= sb or sb <= sa):
                continue
            canonical, other = (a, b) if _prefer(a, b) else (b, a)
            reason = "graphies identiques" if sa == sb else "l'une precise l'autre"
            out.append(Candidate(
                canonical, other, reason,
                conflicting=(a.status != b.status),
            ))
    return out


def _prefer(a: Row, b: Row) -> bool:
    """La ligne du vault fait référence, sinon la plus anciennement connue."""
    if (a.source == "vault") != (b.source == "vault"):
        return a.source == "vault"
    return a.id <= b.id


def render(candidates: list[Candidate]) -> str:
    lines = []
    for n, c in enumerate(candidates, 1):
        flag = "  ⚠ STATUTS CONTRADICTOIRES" if c.conflicting else ""
        lines.append(f"[{n:>2}] {c.reason}{flag}")
        for role, r in (("garder ", c.canonical), ("alias  ", c.other)):
            lines.append(
                f"     {role} #{r.id:<5} {r.name!r} | {r.section} | "
                f"{r.qty_text or '—'} | {r.status} | {r.source}"
            )
        lines.append("")
    return "\n".join(lines)


async def _load(dsn: str) -> list[Row]:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        recs = await conn.fetch(
            """SELECT id, name, name_normalized, section, qty_text, status, source,
                      updated_at
                 FROM pantry_item ORDER BY id"""
        )
    finally:
        await conn.close()
    return [
        Row(r["id"], r["name"], r["name_normalized"], r["section"],
            r["qty_text"] or "", r["status"], r["source"], str(r["updated_at"])[:10])
        for r in recs
    ]


async def _apply(dsn: str, decisions: list[dict]) -> int:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    applied = 0
    try:
        for d in decisions:
            await conn.execute(
                """INSERT INTO pantry_alias (alias_normalized, pantry_item_id)
                   VALUES ($1, $2)
                   ON CONFLICT (alias_normalized) DO UPDATE
                       SET pantry_item_id = EXCLUDED.pantry_item_id""",
                d["alias_normalized"], d["canonical_id"],
            )
            applied += 1
    finally:
        await conn.close()
    return applied


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=os.environ.get(
        "DATABASE_URL", "postgresql://cooking:cooking@127.0.0.1:5432/cooking_manager"))
    ap.add_argument("--json", help="ecrit les propositions dans ce fichier")
    ap.add_argument("--apply", help="fichier de decisions confirmees a appliquer")
    args = ap.parse_args()

    if args.apply:
        decisions = json.load(open(args.apply, encoding="utf-8"))
        n = asyncio.run(_apply(args.dsn, decisions))
        print(f"{n} alias declare(s)")
        return 0

    rows = asyncio.run(_load(args.dsn))
    candidates = find_candidates(rows)
    print(f"{len(rows)} lignes, {len(candidates)} paire(s) candidate(s), "
          f"{sum(1 for c in candidates if c.conflicting)} en contradiction de statut\n")
    print(render(candidates))

    if args.json:
        payload = [
            {"n": n, "alias_normalized": c.other.name_normalized,
             "canonical_id": c.canonical.id,
             "canonical": c.canonical.name, "other": c.other.name,
             "conflicting": c.conflicting}
            for n, c in enumerate(candidates, 1)
        ]
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"propositions ecrites dans {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
