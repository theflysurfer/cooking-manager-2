"""Unitaires — garde-manger vivant et différentiel.

Le contrat central : **un faux positif coûte plus cher qu'un faux négatif**.
Dire « tu en as » alors qu'on n'en a pas fait sauter un achat nécessaire, et ça
ne se découvre qu'en cuisine. D'où les tests qui vérifient qu'on répond
`inconnu` plutôt que de deviner.

Le cas fondateur (2026-08-04) est en bas : miel et sauce soja étaient
`status=ok` au garde-manger et ont été rachetés quand même.
"""

from datetime import date, timedelta

import pytest

from cooking_manager.pantry import (
    ENOUGH,
    Pantry,
    PantryItem,
    MISSING,
    PARTIAL,
    UNKNOWN,
    Need,
    build_needs,
    check_need,
    parse_pantry,
)
from cooking_manager.ingredients import Ingredient, normalize_name

VAULT = """---
updated: 2026-07-11
---

# Garde-manger

## Épicerie sèche

- Miel bio (liquide) — 2 pots (entré 2026-06-02) # status=ok
- Sauce soja salée (Auchan) — 1 flacon 250 ml # status=ok
- Farine T65 — 250 g # status=low
- Riz basmati — 0 # status=out

## Frais — Protéines

- Œufs — 6 pièces (entré 2026-07-08) # status=ok
- Filets de poulet — 480 g / 4 filets # status=urgent
"""


def need_of(name, qty=None, unit=None):
    """Un besoin isolé, tel que `build_needs` le produirait."""
    return Need(name=name, name_normalized=normalize_name(name), qty=qty, unit=unit)


@pytest.fixture
def pantry():
    return parse_pantry(VAULT)


class TestParse:
    def test_reads_updated_and_rayons(self, pantry):
        assert pantry.updated == date(2026, 7, 11)
        assert {i.rayon for i in pantry.items} == {"Épicerie sèche", "Frais — Protéines"}

    def test_reads_status_and_quantities(self, pantry):
        farine = pantry.find("farine")
        assert farine is not None
        assert (farine.status, farine.qty_value, farine.unit) == ("low", 250.0, "g")

    def test_ligature_in_name_is_matchable(self, pantry):
        """« Œufs » n'a AUCUNE décomposition Unicode : sans expansion explicite
        de la ligature, « oeuf dur » ne trouve jamais les œufs du stock."""
        assert pantry.find("oeufs") is not None

    def test_staleness_is_computed_not_assumed(self, pantry):
        assert pantry.age_days(today=date(2026, 8, 4)) == 24
        assert pantry.is_stale(today=date(2026, 8, 4)) is True
        assert pantry.is_stale(today=date(2026, 7, 12)) is False


class TestMatching:
    def test_containment_match(self, pantry):
        """« miel » doit rencontrer « Miel bio (liquide) » — c'est cet
        appariement-là qui manquait le 2026-08-04."""
        item = pantry.find("miel")
        assert item is not None and item.status == "ok"

    def test_no_match_returns_none(self, pantry):
        assert pantry.find("cardamome") is None

    def test_partial_word_does_not_match(self, pantry):
        """« ri » ne doit pas matcher « riz » : une inclusion nue transforme
        n'importe quel fragment en faux positif."""
        assert pantry.find("ri") is None

    def _stock(self, *names):
        return Pantry(items=[
            PantryItem(rayon="X", name=n, name_normalized=normalize_name(n),
                       qty_text="", status="ok")
            for n in names
        ], updated=None)

    @pytest.mark.parametrize("besoin,attendu", [
        ("mélange mâche et roquette", "Mélange de mâche et roquette"),
        ("bouillon de légumes", "Knorr Bouillon de Légumes"),
        ("origan", "Hello Fresh Origan"),
    ])
    def test_un_mot_outil_ou_une_marque_ne_cassent_pas_l_appariement(self, besoin, attendu):
        """Un seul « de » manquant faisait racheter un sachet déjà au frigo
        (mesuré sur le stock réel le 2026-09-07)."""
        stock = self._stock("Mélange de mâche et roquette", "Knorr Bouillon de Légumes",
                            "Hello Fresh Origan")
        found = stock.find(normalize_name(besoin))
        assert found is not None and found.name == attendu

    def test_un_alias_tranche_ce_qu_aucune_regle_ne_peut_decider(self):
        """`pantry_alias` existait depuis le 2026-09-01 mais n'était lu par
        AUCUN code : 10 lignes écrites, jamais consultées. « origan séché » ne
        pouvait pas rencontrer « Hello Fresh Origan » — rien dans le nom du
        stock ne dit qu'il est séché, et deviner produirait un faux « tu en as ».
        """
        item = PantryItem(item_id=7, rayon="Épices", name="Hello Fresh Origan",
                          name_normalized=normalize_name("Hello Fresh Origan"))
        besoin = normalize_name("origan séché")
        assert Pantry(items=[item]).find(besoin) is None
        aliased = Pantry(items=[item], aliases={besoin: 7})
        found = aliased.find(besoin)
        assert found is not None and found.name == "Hello Fresh Origan"

    @pytest.mark.parametrize("besoin", ["lait de coco", "crème fraîche", "huile de sésame"])
    def test_le_besoin_plus_precis_ne_se_satisfait_pas_du_generique(self, besoin):
        """Le stock peut être plus précis que le besoin, jamais l'inverse : un
        faux « tu en as » fait sauter un achat, et ça se découvre en cuisine."""
        stock = self._stock("Lait entier", "Crème liquide", "Huile d'olive")
        assert stock.find(normalize_name(besoin)) is None


class TestVerdicts:
    def test_enough_when_stock_covers(self, pantry):
        need = need_of("miel", 1.0, "c.s.")
        assert check_need(need, pantry).outcome == ENOUGH

    def test_missing_when_absent(self, pantry):
        need = need_of("cardamome", 200.0, "g")
        v = check_need(need, pantry)
        assert v.outcome == MISSING and v.pantry_item is None

    def test_missing_when_status_out(self, pantry):
        need = need_of("riz basmati", 300.0, "g")
        assert check_need(need, pantry).outcome == MISSING

    def test_partial_when_stock_is_short(self, pantry):
        need = need_of("farine T65", 500.0, "g")
        v = check_need(need, pantry)
        assert v.outcome == PARTIAL
        assert v.to_buy == 250.0

    def test_unknown_when_units_are_incommensurable(self, pantry):
        """« 3 filets » contre « 480 g » : on ne convertit pas, on demande.
        Deviner ici ferait sauter un achat de viande."""
        need = need_of("filets de poulet", 3.0, "pièce")
        assert check_need(need, pantry).outcome == UNKNOWN

    def test_quantityless_need_on_stocked_item_is_enough(self, pantry):
        """« sauce soja » sans quantité chiffrée, sur un flacon en stock :
        répondre `inconnu` noierait la liste sous des questions sans objet —
        et une liste qu'on n'a plus envie de lire est une liste qu'on cesse
        de croire."""
        need = need_of("sauce soja")
        assert check_need(need, pantry).outcome == ENOUGH


class TestStaleness:
    def test_fresh_is_assumed_gone_when_inventory_is_old(self, pantry):
        """Inventaire vieux de 24 jours → le frais est supposé épuisé. La
        déduction doit être DITE (elle est dans `reason`), jamais silencieuse."""
        need = need_of("œufs", 4.0, "pièce")
        v = check_need(need, pantry, today=date(2026, 8, 4))
        assert v.outcome in (MISSING, UNKNOWN)
        assert "inventaire" in v.reason.lower()

    def test_dry_goods_survive_a_stale_inventory(self, pantry):
        """Le sec ne périme pas : la règle d'ancienneté ne s'y applique pas."""
        need = need_of("miel", 1.0, "c.s.")
        assert check_need(need, pantry, today=date(2026, 8, 4)).outcome == ENOUGH

    def test_fresh_is_trusted_when_inventory_is_recent(self, pantry):
        need = need_of("œufs", 4.0, "pièce")
        assert check_need(need, pantry, today=date(2026, 7, 12)).outcome == ENOUGH


class TestAggregation:
    def test_same_ingredient_across_recipes_is_summed(self):
        """Deux recettes qui veulent des œufs produisent UNE ligne, avec les
        deux recettes citées — sinon on achète deux fois."""
        needs = build_needs([
            ("Gratin", [Ingredient(raw="2 œufs", name="œufs", qty_min=2.0, unit="pièce", position=1)], 1.0),
            ("Cookies", [Ingredient(raw="3 œufs", name="œufs", qty_min=3.0, unit="pièce", position=1)], 1.0),
        ])
        assert len(needs) == 1
        assert needs[0].qty == 5.0
        assert set(needs[0].recipes) == {"Gratin", "Cookies"}

    def test_portions_ratio_scales_quantities(self):
        needs = build_needs([
            ("Gratin", [Ingredient(raw="400 g pommes de terre", name="pommes de terre",
                                   qty_min=400.0, unit="g", position=1)], 1.5),
        ])
        assert needs[0].qty == 600.0

    def test_incommensurable_units_stay_separate(self):
        """« 2 pièces » et « 200 g » de courgette ne s'additionnent pas — les
        fondre produirait un chiffre faux qui a l'air juste."""
        needs = build_needs([
            ("A", [Ingredient(raw="2 courgettes", name="courgettes", qty_min=2.0, unit="pièce", position=1)], 1.0),
            ("B", [Ingredient(raw="200 g courgettes", name="courgettes", qty_min=200.0, unit="g", position=1)], 1.0),
        ])
        assert len(needs) == 2

    def test_same_family_different_units_convert_before_summing(self):
        """« 800 g » + « 1 kg » du même aliment font 1,8 kg, pas 801.

        Le défaut est resté invisible tant que « patates douces » et « patates
        douces, en gros cubes » étaient deux besoins distincts : la fusion des
        doublons (2026-09-07) l'a fait apparaître d'un coup, en kg.
        """
        needs = build_needs([
            ("Saumon", [Ingredient(raw="800 g patates douces", name="patates douces",
                                   qty_min=800.0, unit="g", position=1)], 1.0),
            ("Pilons", [Ingredient(raw="1 kg patates douces", name="patates douces",
                                   qty_min=1.0, unit="kg", position=1)], 1.0),
        ])
        assert len(needs) == 1
        assert (needs[0].qty, needs[0].unit) == (1800.0, "g")

    def test_range_takes_the_upper_bound(self):
        """« 2–3 c.s. » : on achète pour 3. Manquer coûte plus cher qu'avoir
        un peu trop."""
        needs = build_needs([
            ("A", [Ingredient(raw="2–3 c.s. miel", name="miel",
                              qty_min=2.0, qty_max=3.0, unit="c.s.", position=1)], 1.0),
        ])
        assert needs[0].qty == 3.0


class TestNeedConsolidation:
    """Deux libellés d'un même aliment font UN besoin (#81).

    Chaque fiche décrit son ingrédient dans le contexte de sa recette
    (« chaud », « en lanières », « poids cuit »). Laisser les deux lignes fait
    pire que doublonner : « lentilles vertes » ressort en stock pendant que
    « lentilles vertes sèches » ressort absente, et on rachète.
    """

    def test_a_qualifier_merges_into_the_generic_name(self):
        needs = build_needs([
            ("Risotto", [Ingredient(raw="1 l bouillon de légumes", name="bouillon de légumes",
                                    qty_min=1.0, unit="l", position=1)], 1.0),
            ("Dahl", [Ingredient(raw="1 l bouillon de légumes chaud", name="bouillon de légumes chaud",
                                 qty_min=1.0, unit="l", position=1)], 1.0),
        ])
        assert len(needs) == 1
        assert needs[0].name_normalized == "bouillon de legume"
        assert needs[0].qty == 2000.0
        assert "bouillon de légumes chaud" in needs[0].merged_from

    def test_the_founding_case_lentils(self):
        """Le cas qui faisait racheter : le stock porte « lentilles vertes »,
        la seconde fiche écrit « lentilles vertes sèches »."""
        needs = build_needs([
            ("Salade", [Ingredient(raw="300 g lentilles vertes", name="lentilles vertes",
                                   qty_min=300.0, unit="g", position=1)], 1.0),
            ("Poêlée", [Ingredient(raw="300 g lentilles vertes sèches", name="lentilles vertes sèches",
                                   qty_min=300.0, unit="g", position=1)], 1.0),
        ])
        assert len(needs) == 1
        assert needs[0].name_normalized == "lentille verte"

    def test_incommensurable_units_are_never_merged(self):
        """« 2 sachets » et « 2 pièces » de mâche restent deux besoins : les
        fondre additionnerait des choses qui ne s'additionnent pas."""
        needs = build_needs([
            ("A", [Ingredient(raw="2 sachets mélange mâche et roquette",
                              name="mélange mâche et roquette", qty_min=2.0, unit="sachet", position=1)], 1.0),
            ("B", [Ingredient(raw="2 poignées de mâche et roquette",
                              name="poignée de mâche et roquette", qty_min=2.0, unit="pièce", position=1)], 1.0),
        ])
        assert len(needs) == 2

    def test_two_varieties_stay_apart(self):
        """« lentilles corail » et « lentilles vertes » ne sont pas le même
        aliment — aucun des deux noms n'est contenu dans l'autre."""
        needs = build_needs([
            ("A", [Ingredient(raw="300 g lentilles corail", name="lentilles corail",
                              qty_min=300.0, unit="g", position=1)], 1.0),
            ("B", [Ingredient(raw="300 g lentilles vertes", name="lentilles vertes",
                              qty_min=300.0, unit="g", position=1)], 1.0),
        ])
        assert len(needs) == 2

    def test_a_partial_overlap_is_left_alone(self):
        """« trio de poivrons en lanières » et « poivrons en lanières (rouge et
        jaune) » : l'un contient l'autre, ils fusionnent. Mais « poivrons
        rouges » en pièces reste à part — deux mots communs ne suffisent pas."""
        needs = build_needs([
            ("A", [Ingredient(raw="600 g poivrons en lanières", name="poivrons en lanières",
                              qty_min=600.0, unit="g", position=1)], 1.0),
            ("B", [Ingredient(raw="600 g trio de poivrons en lanières", name="trio de poivrons en lanières",
                              qty_min=600.0, unit="g", position=1)], 1.0),
            ("C", [Ingredient(raw="2 poivrons rouges", name="poivrons rouges",
                              qty_min=2.0, unit="pièce", position=1)], 1.0),
        ])
        assert len(needs) == 2
        merged = [n for n in needs if n.unit == "g"][0]
        assert merged.name_normalized == "poivron en laniere"
        assert merged.qty == 1200.0

    def test_recipes_and_requirement_survive_the_merge(self):
        """Une recette qui EXIGE l'ingrédient l'emporte sur une qui le rend
        optionnel, et les deux recettes restent citées."""
        needs = build_needs([
            ("A", [Ingredient(raw="10 g persil", name="persil", qty_min=10.0,
                              unit="g", is_optional=True, position=1)], 1.0),
            ("B", [Ingredient(raw="10 g persil plat", name="persil plat", qty_min=10.0,
                              unit="g", position=1)], 1.0),
        ])
        assert len(needs) == 1
        assert needs[0].is_optional is False
        assert set(needs[0].recipes) == {"A", "B"}


class TestFoundingBug:
    """Non-régression du 2026-08-04 : sauce soja et miel étaient au
    garde-manger en `status=ok` et ont quand même été achetés."""

    @pytest.mark.parametrize("name,unit,qty", [
        ("miel", "c.s.", 2.0),
        ("sauce soja", "c.s.", 3.0),
    ])
    def test_stocked_condiments_never_reach_the_shopping_list(self, pantry, name, unit, qty):
        need = need_of(name, qty, unit)
        v = check_need(need, pantry, today=date(2026, 8, 4))
        assert v.outcome == ENOUGH, f"{name} repart en courses — le bug est revenu"
        assert v.pantry_item is not None

    def test_the_inventory_age_does_not_silently_flush_the_pantry(self, pantry):
        """Le garde-fou du garde-fou : la règle d'ancienneté ne doit pas
        devenir un moyen détourné de tout racheter."""
        old = parse_pantry(VAULT.replace("2026-07-11", "2025-01-01"))
        need = need_of("miel", 2.0, "c.s.")
        assert check_need(need, old, today=date(2026, 8, 4)).outcome == ENOUGH


class TestRealVault:
    """Contrôle de volume contre le vrai fichier — le compte connu est 244
    items (celui de `cuisine.json` produit par v1)."""

    def test_real_file_parses_completely(self):
        from pathlib import Path
        path = Path(r"E:\Dr2\Dropbox\JULIEN\Obsidian\vault\Noyau\Cuisine\Garde-manger.md")
        if not path.exists():
            pytest.skip("vault local indisponible")
        p = parse_pantry(path.read_text(encoding="utf-8"))
        assert len(p.items) > 200
        assert p.updated is not None
        age = p.age_days()
        assert age is not None and age >= 0
        assert p.is_stale(today=p.updated + timedelta(days=15)) is True
