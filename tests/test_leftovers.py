"""Un reste hérite de son plat source, et un reste sans source se nomme — #76."""

import pytest

from backend.ingest import _parse_place


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    async def fetch(self, _sql, *_args):
        return self.rows

    async def execute(self, _sql, *args):
        self.updates.append(args)


ROWS = [
    {"id": 10, "position": 1, "slot": "dinner", "match_kind": "explicit"},
    {"id": 11, "position": 2, "slot": "lunch", "match_kind": "leftovers"},
    {"id": 12, "position": 3, "slot": "lunch", "match_kind": "freestyle"},
]


class TestPlace:
    def test_une_place_se_lit_position_slot(self):
        assert _parse_place("1:dinner") == (1, "dinner")

    def test_une_place_illisible_ne_devine_rien(self):
        assert _parse_place("la veille") is None
        assert _parse_place("1") is None


class TestLiaison:
    @pytest.mark.asyncio
    async def test_un_reste_pointe_le_plat_de_la_veille(self):
        from backend.ingest import _link_leftovers

        conn = FakeConn(ROWS)
        await _link_leftovers(conn, 1, [(2, "lunch", "1:dinner")])
        assert conn.updates == [(10, 1, 2, "lunch")]

    @pytest.mark.asyncio
    async def test_une_source_absente_laisse_le_repas_non_controlable(self):
        """Pointer un repas qui n'existe pas ne doit JAMAIS élire le premier venu."""
        from backend.ingest import _link_leftovers

        conn = FakeConn(ROWS)
        await _link_leftovers(conn, 1, [(2, "lunch", "9:dinner")])
        assert conn.updates == []

    @pytest.mark.asyncio
    async def test_un_reste_de_reste_est_refuse(self):
        from backend.ingest import _link_leftovers

        conn = FakeConn(ROWS)
        await _link_leftovers(conn, 1, [(2, "lunch", "3:lunch")])
        assert conn.updates == []
