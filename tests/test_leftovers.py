"""Un reste hérite de son plat source, et un reste sans source se nomme — #76."""

import pytest

from backend.ingest import _parse_place
from cooking_manager.convives import Convive, check_ingredients, inherit_leftovers


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


PILONS = [{"name": "pilons de poulet", "name_normalized": "pilon de poulet",
           "raw": "6 pilons de poulet"}]
CLEMENCE = Convive(name="Clémence", diet="pescetarian")


class TestHeritage:
    def test_le_reste_des_pilons_leve_enfin_le_conflit(self):
        """Le cas du 2026-09-07 : sans héritage, Clémence n'avait rien à manger."""
        lines = {10: PILONS}
        meals = [{"meal_id": 11, "match_kind": "leftovers", "leftovers_of": 10,
                  "day_label": "mardi", "slot": "lunch", "dish": "Restes des pilons"}]
        assert inherit_leftovers(meals, lines, {}) == []
        assert check_ingredients(lines[11], [CLEMENCE])

    def test_un_reste_sans_source_se_nomme_au_lieu_de_se_taire(self):
        meals = [{"meal_id": 11, "match_kind": "leftovers", "leftovers_of": None,
                  "day_label": "mardi", "slot": "lunch", "dish": "Restes"}]
        lines: dict[int, list] = {}
        unsourced = inherit_leftovers(meals, lines, {})
        assert [u["dish"] for u in unsourced] == ["Restes"]
        assert 11 not in lines

    def test_un_regime_ecrit_en_francais_interdit_les_memes_choses(self):
        """« pescetarien » rendait une liste vide : le régime ne bloquait plus rien."""
        assert Convive(name="C", diet="pescetarien").diet_terms == CLEMENCE.diet_terms

    def test_une_source_sans_ingredient_ne_passe_pas_pour_un_controle(self):
        """Emprunter une liste vide rendrait « zéro conflit » indiscernable de « contrôlé »."""
        meals = [{"meal_id": 11, "match_kind": "leftovers", "leftovers_of": 10,
                  "day_label": "mardi", "slot": "lunch", "dish": "Restes"}]
        assert len(inherit_leftovers(meals, {10: []}, {})) == 1
