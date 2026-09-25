"""#155 — le contenant entre dans le domaine, et dit quand il l'ignore."""

import pytest

from cooking_manager.packing import PackPlan, pack_plan
from cooking_manager.purchase import Purchase


def buy(qty, unit: str | None = "g", kind="mesure"):
    return Purchase(kind=kind, qty=qty, unit=unit, reason="test")


def product(value, unit: str | None = "g", count=1.0, name="sachet"):
    return {"name": name, "pack_size_value": value, "pack_size_unit": unit,
            "pack_count": count, "last_price": None}


class TestRatchetContenantInconnu:
    """Un aliment sans `pack_size` ne rend JAMAIS un nombre de paquets."""

    @pytest.mark.parametrize("products", [
        [],
        [product(None)],
        [product(400, unit=None)],
        [{"name": "cabillaud"}],
        [product(0)],
    ])
    def test_sans_conditionnement_connu_packs_est_none(self, products):
        plan = pack_plan(buy(800), products)
        assert plan.packs is None
        assert plan.pack_known is False
        assert plan.reason

    def test_jamais_un_paquet_par_defaut(self):
        assert pack_plan(buy(800), []).packs != 1

    def test_un_achat_sans_quantite_ne_se_conditionne_pas(self):
        plan = pack_plan(buy(None, unit=None, kind="non_resolu"), [product(400)])
        assert plan.pack_known is False
        assert "quantité" in plan.reason

    def test_une_dose_ne_se_conditionne_pas(self):
        plan = pack_plan(buy(1.0, unit="conditionnement", kind="dose"), [product(400)])
        assert plan.pack_known is False
        assert "dose" in plan.reason


class TestCasConnu:
    def test_1150_g_en_sachets_de_400_font_trois_sachets(self):
        plan = pack_plan(buy(1150), [product(400)])
        assert plan == PackPlan(packs=3, buys=1200.0, unit="g", pack_known=True,
                                pack_size=400.0, reason="3 × 400 g", surplus=50.0)

    def test_le_compte_exact_ne_laisse_aucun_surplus(self):
        assert pack_plan(buy(800), [product(400)]).surplus == 0.0

    def test_un_lot_multiplie_la_taille_du_contenant(self):
        plan = pack_plan(buy(1150), [product(400, count=2.0)])
        assert (plan.packs, plan.buys, plan.pack_size) == (2, 1600.0, 800.0)

    def test_le_plus_petit_contenant_connu_gagne(self):
        plan = pack_plan(buy(1150), [product(1000), product(400), product(2500)])
        assert (plan.packs, plan.pack_size) == (3, 400.0)

    def test_les_unites_se_convertissent_avant_de_compter(self):
        plan = pack_plan(buy(1.15, unit="kg"), [product(400, unit="g")])
        assert (plan.packs, plan.unit) == (3, "kg")

    def test_une_unite_incomparable_ne_conclut_pas(self):
        plan = pack_plan(buy(1150, unit="g"), [product(2, unit="pièce")])
        assert plan.pack_known is False
        assert "comparable" in plan.reason


class TestSurplus:
    """`SURPLUS` se mesure en CONTENANTS, pas en ratio (décision 15 du grill)."""

    def test_un_contenant_entier_de_trop_est_un_surplus(self):
        plan = pack_plan(buy(410), [product(400)])
        assert (plan.packs, plan.surplus) == (2, 390.0)
        assert plan.surplus_packs == pytest.approx(0.975)

    def test_une_gousse_d_ail_n_est_jamais_en_surplus_car_c_est_une_dose(self):
        plan = pack_plan(buy(1.0, unit="conditionnement", kind="dose"), [product(1)])
        assert plan.surplus is None
