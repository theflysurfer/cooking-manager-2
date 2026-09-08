"""Unitaires — l'ingestion du vault n'atteint pas le garde-manger (#91, ADR 0017)."""

from pathlib import Path

import pytest

INGEST = Path(__file__).resolve().parents[1] / "backend" / "ingest.py"

FORBIDDEN = ("pantry_item", "garde-manger", "parse_pantry")


@pytest.fixture
def ingest_source():
    return INGEST.read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("token", FORBIDDEN)
def test_ingest_never_reaches_the_pantry(ingest_source, token):
    assert token not in ingest_source


def test_the_guard_can_fail(ingest_source):
    assert "menu_meal" in ingest_source
