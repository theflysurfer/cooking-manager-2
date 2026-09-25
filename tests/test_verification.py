from cooking_manager.verification import (
    MISSING,
    OFF_APP,
    OFF_MENU_ASSUMED,
    OK,
    SURPLUS,
    UNMEASURABLE,
    CartLine,
    Need,
    unreadable,
    verify,
)

READ_AT = "2026-09-24T18:02"


def judged(result, food):
    return next(e for e in result["per_food"] if e["food"] == food)


class TestLesQuatreVerdictsDu21Septembre:
    """Les quatre lignes de l'exemple de #157 sont les quatre pannes réelles de ce jour-là."""

    RESULT = verify(
        [Need("oeuf", 26, "piece", pack_size=6),
         Need("poivron", 1150, "g", pack_size=500),
         Need("courgette", 400, "g", pack_size=500)],
        [CartLine("Oeufs x12", food="oeuf", qty=12, unit="piece", origin="menu"),
         CartLine("Poivrons 1,2 kg", food="poivron", qty=1200, unit="g", origin="menu"),
         CartLine("Courgettes 2 kg", food="courgette", qty=2000, unit="g", origin="menu"),
         CartLine("Cabillaud 800 g", food="cabillaud", qty=800, unit="g",
                  origin="manual")],
        READ_AT)

    def test_un_repas_sans_son_ingredient_bloque(self):
        assert judged(self.RESULT, "oeuf")["verdict"] == MISSING

    def test_la_quantite_juste_a_un_contenant_pres_passe(self):
        assert judged(self.RESULT, "poivron")["verdict"] == OK

    def test_au_dela_d_un_contenant_de_trop_avertit(self):
        courgette = judged(self.RESULT, "courgette")
        assert courgette["verdict"] == SURPLUS
        assert "contenant" in courgette["reason"]

    def test_une_ligne_posee_a_la_main_est_un_hors_menu_assume(self):
        assert judged(self.RESULT, "cabillaud")["verdict"] == OFF_MENU_ASSUMED

    def test_le_verdict_global_est_faux_et_nomme_ses_bloquants(self):
        assert self.RESULT["ok"] is False
        assert "oeuf" in self.RESULT["reason"]
        assert [e["food"] for e in self.RESULT["blocking"]] == ["oeuf"]


class TestUnPanierConformeConclut:
    def test_tout_au_compte_rend_ok(self):
        result = verify([Need("carotte", 1000, "g", pack_size=1000)],
                        [CartLine("Carottes 1 kg", food="carotte", qty=1000, unit="g",
                                  origin="menu")], READ_AT)
        assert result["ok"] is True
        assert result["measured"] is True
        assert result["counts"] == {OK: 1}


class TestCeQuiNAPasEteRegarde:
    """Un panier illisible ne vaut jamais un panier conforme."""

    def test_une_lecture_impossible_n_est_jamais_ok(self):
        result = unreadable("session anonyme")
        assert result["ok"] is False
        assert result["measured"] is False
        assert "session anonyme" in result["reason"]
        assert result["per_food"] == []

    def test_un_contenant_inconnu_chez_le_drive_ne_conclut_pas(self):
        result = verify([Need("farine", 1000, "g", pack_size=1000)],
                        [CartLine("Farine", food="farine", qty=None, unit=None,
                                  origin="menu")], READ_AT)
        assert judged(result, "farine")["verdict"] == UNMEASURABLE
        assert result["ok"] is False

    def test_des_unites_incomparables_ne_concluent_pas(self):
        result = verify([Need("lait", 2000, "ml", pack_size=1000)],
                        [CartLine("Lait 2 kg", food="lait", qty=2000, unit="g",
                                  origin="menu")], READ_AT)
        assert judged(result, "lait")["verdict"] == UNMEASURABLE

    def test_un_surplus_sans_contenant_connu_se_lit_comme_non_mesurable(self):
        """`surplus_measurable: false` : le silence se lit, il ne passe pas pour un surplus nul."""
        result = verify([Need("sel", 100, "g", pack_size=None)],
                        [CartLine("Sel 1 kg", food="sel", qty=1000, unit="g",
                                  origin="menu")], READ_AT)
        sel = judged(result, "sel")
        assert sel["verdict"] == OK
        assert sel["surplus_measurable"] is False


class TestSaisiHorsDeLApplication:
    def test_une_ligne_du_drive_qu_aucune_ligne_de_l_appli_ne_porte_bloque(self):
        result = verify([], [CartLine("Chips 150 g", food=None, qty=150, unit="g")],
                        READ_AT)
        entry = result["per_food"][0]
        assert entry["verdict"] == OFF_APP
        assert result["ok"] is False

    def test_un_aliment_hors_menu_non_assume_bloque(self):
        """La ligne existe dans l'appli mais vient du menu : rien ne l'assume hors menu."""
        result = verify([], [CartLine("Saumon 400 g", food="saumon", qty=400, unit="g",
                                      origin="menu")], READ_AT)
        assert judged(result, "saumon")["verdict"] == OFF_APP


class TestLesSixPaquetsDeParmesan:
    """#113 : la ligne ajoutée en 6 exemplaires le 20/09 doit se voir AVANT la commande."""

    def test_six_paquets_pour_un_besoin_d_un_seul_sont_un_surplus(self):
        result = verify([Need("parmesan", 100, "g", pack_size=100)],
                        [CartLine("Parmesan râpé 100 g", food="parmesan", qty=600,
                                  unit="g", origin="menu")], READ_AT)
        parmesan = judged(result, "parmesan")
        assert parmesan["verdict"] == SURPLUS
        assert parmesan["cart"] == 600
        assert parmesan["need"] == 100

    def test_les_carottes_manquantes_bloquent_la_meme_commande(self):
        """L'autre retour du 20/09 : « il manque des carottes ? » — la question devient un verdict."""
        result = verify([Need("carotte", 1000, "g", pack_size=1000)], [], READ_AT)
        assert judged(result, "carotte")["verdict"] == MISSING
        assert result["ok"] is False


class TestUnZeroEstUneMesure:
    def test_un_aliment_absent_du_panier_manque_il_n_est_pas_non_mesurable(self):
        """Zéro ligne chez le drive se compare : 0 g contre 1000 g, c'est un MANQUE."""
        result = verify([Need("carotte", 1000, "g", pack_size=1000)], [], READ_AT)
        carotte = judged(result, "carotte")
        assert carotte["verdict"] == MISSING
        assert carotte["cart"] == 0
