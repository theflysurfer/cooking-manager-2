from cooking_manager.effort import (
    HANDS_OFF,
    HANDS_ON,
    LIGHT,
    PROJECT,
    declared_bands,
    fits_weeknight,
    read_effort,
)

MAFE = ["Faire revenir les oignons.", "Ajouter la pâte d'arachide.",
        "Verser le bouillon et laisser mijoter 35 min à couvert.",
        "Ajouter le poisson.", "Servir avec le riz."]
RISOTTO = ["Saisir le poulet.", "Faire suer l'oignon.", "Nacrer le riz.",
           "Verser le bouillon louche par louche en remuant.",
           "Incorporer le parmesan.", "Servir."]
OATS = ["Mélanger le skyr et les flocons.", "Laisser reposer une nuit au frais."]
BOULETTES = ["Mélanger le haché et l'oeuf.", "Façonner 12 boulettes.",
             "Saisir les boulettes.", "Mijoter 15 min."]

class TestReadEffort:
    def test_a_stew_leaves_the_hands_free(self):
        assert read_effort(MAFE).band == HANDS_OFF

    def test_continuous_stirring_is_hands_on(self):
        reading = read_effort(RISOTTO)
        assert reading.band == HANDS_ON and "louche par louche" in reading.markers

    def test_shaping_is_a_weekend_project(self):
        assert read_effort(BOULETTES).band == PROJECT

    def test_resting_overnight_is_not_effort(self):
        assert read_effort(OATS).band == HANDS_OFF

    def test_a_plain_assembly_is_light(self):
        assert read_effort(["Couper les légumes.", "Mélanger.", "Assaisonner."]).band == LIGHT

    def test_no_steps_is_not_derivable(self):
        reading = read_effort([])
        assert reading.derivable is False and reading.as_dict()["band"] is None

    def test_the_step_count_alone_never_decides(self):
        """8 étapes triviales (ninja-creami, 10 min) ne font pas un plat exigeant."""
        steps = ["Sortir le bol.", "Verser le skyr.", "Ajouter le fruit.",
                 "Mixer.", "Congeler 24 h.", "Passer en machine.",
                 "Remettre en machine.", "Servir."]
        assert read_effort(steps).band != HANDS_ON

class TestFitsWeeknight:
    def test_a_long_stew_does_not_fit_even_hands_off(self):
        """« Un mafé un soir de semaine, ça ne le fait pas du tout » — Julien."""
        assert fits_weeknight(read_effort(MAFE), 50) is False

    def test_the_same_stew_shorter_fits(self):
        assert fits_weeknight(read_effort(MAFE), 40) is True

    def test_short_hands_on_fits(self):
        assert fits_weeknight(read_effort(RISOTTO), 15) is True

    def test_long_hands_on_does_not(self):
        assert fits_weeknight(read_effort(RISOTTO), 35) is False

    def test_a_project_never_fits(self):
        assert fits_weeknight(read_effort(BOULETTES), 20) is False

    def test_without_a_clock_nothing_is_decided(self):
        assert fits_weeknight(read_effort(MAFE), None) is None

    def test_without_steps_nothing_is_decided(self):
        assert fits_weeknight(read_effort([]), 20) is None

def test_the_code_invents_no_band():
    assert {HANDS_OFF, LIGHT, HANDS_ON, PROJECT} == declared_bands()
