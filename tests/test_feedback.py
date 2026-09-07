import pytest

from cooking_manager.feedback import (
    APPRECIATION_FACET,
    ISSUE_FACET,
    VERDICT_FACET,
    UnknownConcept,
    facet_keys,
    interpret,
    validate_concept,
)


def test_les_trois_axes_se_lisent_ensemble():
    reading = interpret("moyen, à refaire en modifiant, c'était trop cuit")
    assert reading.appreciation == "mixed"
    assert reading.verdict == "adjust"
    assert reading.issue_kinds == ("doneness",)
    assert reading.unmatched == ()


def test_refaire_en_modifiant_ne_gagne_pas_pour_keep_as_is():
    assert interpret("à refaire en modifiant").verdict == "adjust"
    assert interpret("à refaire tel quel").verdict == "keep_as_is"


def test_la_negation_ne_se_lit_pas_comme_son_contraire():
    assert interpret("pas aimé").appreciation == "disliked"
    assert interpret("aimé").appreciation == "liked"


def test_une_negation_partielle_ne_se_lit_pas_comme_un_eloge():
    assert interpret("j'ai moins aimé").appreciation == "mixed"
    assert interpret("moins bon que la derniere fois").appreciation == "mixed"


def test_une_occasion_ne_se_lit_pas_comme_une_rotation_libre():
    assert interpret("à réserver pour les pique-niques").verdict == "situational"
    assert interpret("seulement quand il faut finir les restes").verdict == "situational"
    assert interpret("à refaire tel quel").verdict == "keep_as_is"


def test_un_texte_muet_ne_remplit_aucun_axe():
    reading = interpret("il pleuvait ce soir-là")
    assert reading.appreciation is None
    assert reading.verdict is None
    assert reading.issue_kinds == ()
    assert set(reading.unmatched) == {APPRECIATION_FACET, VERDICT_FACET, ISSUE_FACET}


def test_les_apostrophes_typographiques_sont_reconnues():
    assert interpret("elle n’a pas mangé").appreciation == "refused"


def test_plusieurs_defauts_remontent_tous():
    assert interpret("fade et trop peu servi") .issue_kinds == ("portion", "seasoning")


def test_une_cle_hors_vocabulaire_est_refusee():
    with pytest.raises(UnknownConcept):
        validate_concept(APPRECIATION_FACET, "genial")
    assert validate_concept(APPRECIATION_FACET, "loved") == "loved"


def test_les_trois_facettes_survivent_a_la_generation():
    assert "loved" in facet_keys(APPRECIATION_FACET)
    assert "adjust" in facet_keys(VERDICT_FACET)
    assert "effort" in facet_keys(ISSUE_FACET)
