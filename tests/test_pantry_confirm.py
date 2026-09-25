"""#161 — une entrée sans quantité ne se compare à rien, un panier part sur une confirmation."""

from datetime import date, timedelta

import pytest

from cooking_manager.pantry import (
    STATUS_LOW,
    STATUS_OK,
    STATUS_OUT,
    CONFIRMATION_MAX_AGE,
    confirmation_gate,
    entry_quantity,
)


class TestEntryQuantity:
    def test_ok_avec_quantite_rend_la_valeur_et_l_unite(self):
        value, unit, refusal = entry_quantity("500 g", STATUS_OK)
        assert (value, unit, refusal) == (500.0, "g", None)

    def test_ok_sans_quantite_est_refuse_avec_son_motif(self):
        value, unit, refusal = entry_quantity("en stock", STATUS_OK)
        assert (value, unit) == (None, None)
        assert refusal and "ne se compare" in refusal

    def test_qty_text_vide_est_refuse(self):
        assert entry_quantity("", STATUS_OK)[2] is not None
        assert entry_quantity(None, STATUS_OK)[2] is not None

    def test_low_exige_aussi_une_quantite(self):
        assert entry_quantity("reste un peu", STATUS_LOW)[2] is not None
        assert entry_quantity("200 g", STATUS_LOW)[:2] == (200.0, "g")

    def test_out_n_exige_rien_car_il_n_y_a_rien_a_mesurer(self):
        assert entry_quantity("", STATUS_OUT) == (None, None, None)

    def test_un_nombre_sans_unite_ne_passe_pas(self):
        assert entry_quantity("3", STATUS_OK)[2] is not None

    def test_multiplication_resolue(self):
        assert entry_quantity("2×100 g", STATUS_OK)[:2] == (200.0, "g")


class TestConfirmationGate:
    def _conf(self, **kw):
        base = {"menu_slug": "s39", "blind": False, "reason": None,
                "confirmed_at": date.today(), "lines_count": 12}
        base.update(kw)
        return base

    def test_aucune_confirmation_bloque(self):
        gate = confirmation_gate(None, "s39")
        assert gate["ok"] is False
        assert gate["blind"] is False
        assert "non confirmé" in gate["reason"]

    def test_confirmation_du_jour_laisse_passer(self):
        gate = confirmation_gate(self._conf(), "s39")
        assert gate["ok"] is True
        assert gate["reason"] is None

    def test_confirmation_a_l_aveugle_laisse_passer_et_se_dit(self):
        gate = confirmation_gate(
            self._conf(blind=True, reason="pas à la maison", lines_count=0), "s39")
        assert gate["ok"] is True
        assert gate["blind"] is True
        assert "aveugle" in gate["note"].lower()
        assert "pas à la maison" in gate["note"]

    def test_confirmation_d_un_autre_menu_ne_compte_pas(self):
        assert confirmation_gate(self._conf(menu_slug="s38"), "s39")["ok"] is False

    def test_confirmation_perimee_bloque(self):
        old = date.today() - CONFIRMATION_MAX_AGE - timedelta(days=1)
        gate = confirmation_gate(self._conf(confirmed_at=old), "s39")
        assert gate["ok"] is False
        assert "périmée" in gate["reason"]

    def test_une_confirmation_sans_date_ne_se_juge_pas(self):
        gate = confirmation_gate(self._conf(confirmed_at=None), "s39")
        assert gate["ok"] is False
        assert "sans date" in gate["reason"]

    @pytest.mark.parametrize("bad", [{"blind": True, "reason": None},
                                     {"blind": True, "reason": "  "}])
    def test_un_aveugle_sans_motif_n_est_pas_une_confirmation(self, bad):
        assert confirmation_gate(self._conf(**bad), "s39")["ok"] is False

    def test_une_confirmation_qui_passe_ne_porte_pas_de_note_sans_aveugle(self):
        assert confirmation_gate(self._conf(), "s39")["note"] is None

    def test_tout_refus_porte_les_quatre_cles(self):
        for conf in (None, self._conf(confirmed_at=None), self._conf(menu_slug="s38")):
            gate = confirmation_gate(conf, "s39")
            assert set(gate) == {"ok", "blind", "reason", "note"}
