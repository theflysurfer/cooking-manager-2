"""Unitaires — référentiel de présence.

La règle qui a manqué le 2026-08-04 : la cantine n'existe **que hors vacances
scolaires**. La grille type de `Convives.md` porte bien la mention, mais
raisonner dessus sans vérifier la période donne une réponse fausse avec l'aplomb
d'une règle écrite.
"""

from datetime import date

from cooking_manager.presence import (
    Absence,
    Referential,
    SchoolPeriod,
    Stay,
    attendees,
    children_present_this_week,
    parse_referential,
    week_grid,
)

SUMMER = SchoolPeriod("Vacances d'été 2026", date(2026, 7, 4), date(2026, 8, 31))


class TestCustodyCycle:
    def test_reference_week_has_children(self):
        assert children_present_this_week(date(2026, 3, 3)) is True

    def test_alternates_every_other_week(self):
        assert children_present_this_week(date(2026, 3, 10)) is False
        assert children_present_this_week(date(2026, 3, 17)) is True

    def test_same_answer_all_week(self):
        monday, sunday = date(2026, 3, 3), date(2026, 3, 8)
        assert children_present_this_week(monday) == children_present_this_week(sunday)


class TestCanteen:
    """Mardi/jeudi/vendredi midi : enfants à la cantine — mais SEULEMENT en
    période scolaire."""

    SCHOOL_TUESDAY = date(2026, 3, 3)   # semaine AVEC enfants, hors vacances
    HOLIDAY_TUESDAY = date(2026, 8, 4)  # semaine AVEC enfants, en vacances

    def test_canteen_applies_during_school(self):
        assert attendees(self.SCHOOL_TUESDAY, "lunch") == ["Julien", "Clémence"]

    def test_canteen_does_not_apply_during_holidays(self):
        """LE cas de l'incident : en août, les enfants sont là à midi."""
        ref = Referential(school_holidays=[SUMMER])
        assert attendees(self.HOLIDAY_TUESDAY, "lunch", ref) == [
            "Julien", "Clémence", "Léa", "Titouan"
        ]

    def test_without_referential_the_answer_is_wrong(self):
        """Sans référentiel, la règle cantine s'applique à tort — c'est
        exactement l'erreur commise, et elle a l'air d'une règle légitime."""
        assert "Léa" not in attendees(self.HOLIDAY_TUESDAY, "lunch")

    def test_dinner_is_never_canteen(self):
        ref = Referential(school_holidays=[SUMMER])
        assert "Léa" in attendees(self.SCHOOL_TUESDAY, "dinner", ref)

    def test_wednesday_lunch_is_never_canteen(self):
        assert "Léa" in attendees(date(2026, 3, 4), "lunch")


class TestAbsences:
    def test_absent_person_is_removed(self):
        ref = Referential(
            school_holidays=[SUMMER],
            absences=[Absence("Clémence", date(2026, 8, 4), date(2026, 8, 6), "voyage")],
        )
        assert "Clémence" not in attendees(date(2026, 8, 5), "dinner", ref)
        assert "Clémence" in attendees(date(2026, 8, 7), "dinner", ref)

    def test_no_adult_means_no_home_meal(self):
        """Des enfants ne peuvent pas être les seuls convives d'un repas maison :
        mieux vaut rendre une liste vide (« hors foyer ») qu'une table qui se
        lirait comme un repas à préparer."""
        ref = Referential(
            school_holidays=[SUMMER],
            absences=[
                Absence("Julien", date(2026, 8, 8), date(2026, 8, 16), "Bordeaux"),
                Absence("Clémence", date(2026, 8, 8), date(2026, 8, 16), "Bordeaux"),
            ],
        )
        assert attendees(date(2026, 8, 10), "dinner", ref) == []


class TestStays:
    """Le correctif du bug fondateur (F.30, Bègles 2026-08-10) : en location de
    vacances on cuisine sur place, donc les membres du séjour sont à table —
    même s'ils sont par ailleurs marqués absents du foyer principal."""

    BEGLES = Stay(
        label="Semaine à Bègles",
        start=date(2026, 8, 8), end=date(2026, 8, 16),
        members=["Julien", "Clémence", "Léa", "Titouan"],
        cooking=True, location="Bègles",
    )

    def test_stay_members_are_at_the_table(self):
        ref = Referential(school_holidays=[SUMMER], stays=[self.BEGLES])
        assert attendees(date(2026, 8, 10), "dinner", ref) == [
            "Julien", "Clémence", "Léa", "Titouan"
        ]

    def test_stay_beats_absence(self):
        """Le bug exact : les adultes marqués 'à Bordeaux/absents' vidaient la
        tablée. Le séjour l'emporte sur l'absence."""
        ref = Referential(
            school_holidays=[SUMMER],
            absences=[
                Absence("Julien", date(2026, 8, 8), date(2026, 8, 16), "Bordeaux"),
                Absence("Clémence", date(2026, 8, 8), date(2026, 8, 16), "Bordeaux"),
            ],
            stays=[self.BEGLES],
        )
        assert attendees(date(2026, 8, 10), "lunch", ref) == [
            "Julien", "Clémence", "Léa", "Titouan"
        ]

    def test_stay_ignores_canteen_frame(self):
        """Un mardi midi de séjour : pas de cantine, tout le monde à table."""
        ref = Referential(school_holidays=[SUMMER], stays=[self.BEGLES])
        assert "Léa" in attendees(date(2026, 8, 11), "lunch", ref)

    def test_outside_the_stay_the_frame_applies(self):
        """Hors période de séjour, le stay n'a aucun effet : la trame reprend."""
        day = date(2026, 8, 20)  # hors séjour (fini le 16)
        with_stay = Referential(school_holidays=[SUMMER], stays=[self.BEGLES])
        without_stay = Referential(school_holidays=[SUMMER])
        assert attendees(day, "dinner", with_stay) == attendees(day, "dinner", without_stay)


class TestSlotAbsence:
    def test_absence_limited_to_one_slot(self):
        """« déjeune au bureau ce midi » — absent au déjeuner, présent au dîner."""
        ref = Referential(
            absences=[Absence("Julien", date(2026, 3, 3), date(2026, 3, 3),
                              "bureau", slot="lunch")],
        )
        assert "Julien" not in attendees(date(2026, 3, 3), "lunch", ref)
        assert "Julien" in attendees(date(2026, 3, 3), "dinner", ref)


class TestOverrides:
    def test_override_wins_over_everything(self):
        ref = Referential(
            school_holidays=[SUMMER],
            overrides={"2026-08-04/lunch": ["Julien"]},
        )
        assert attendees(date(2026, 8, 4), "lunch", ref) == ["Julien"]

    def test_override_wins_over_stay(self):
        ref = Referential(
            stays=[TestStays.BEGLES],
            overrides={"2026-08-10/lunch": ["Julien"]},
        )
        assert attendees(date(2026, 8, 10), "lunch", ref) == ["Julien"]


class TestParseReferential:
    BODY = """
## Vacances scolaires

| Période | Début | Fin |
|---|---|---|
| **Vacances d'été 2026** | 2026-07-04 | 2026-08-31 |

## Absences

| Qui | Début | Fin | Motif |
|---|---|---|---|
| Julien | 2026-08-08 | 2026-08-16 | Bordeaux |

## Exceptions

- 2026-08-05/dinner : Julien, Clémence
"""

    def test_parses_all_three_sections(self):
        ref = parse_referential(self.BODY)
        assert len(ref.school_holidays) == 1
        assert len(ref.absences) == 1
        assert ref.overrides == {"2026-08-05/dinner": ["Julien", "Clémence"]}

    def test_holiday_detection(self):
        ref = parse_referential(self.BODY)
        assert ref.is_school_holiday(date(2026, 8, 4))
        assert not ref.is_school_holiday(date(2026, 9, 15))

    def test_empty_body_is_safe(self):
        """Un référentiel absent ne casse rien : la trame déterministe
        s'applique seule."""
        ref = parse_referential("")
        assert ref.school_holidays == [] and ref.absences == []
        assert attendees(date(2026, 8, 4), "dinner", ref)


class TestWeekGrid:
    def test_grid_covers_seven_days(self):
        ref = Referential(school_holidays=[SUMMER])
        grid = week_grid(date(2026, 8, 3), ref)
        assert len(grid) == 7
        assert grid[0]["day"] == "lundi" and grid[6]["day"] == "dimanche"

    def test_grid_marks_holidays(self):
        ref = Referential(school_holidays=[SUMMER])
        assert week_grid(date(2026, 8, 3), ref)[0]["school_holiday"] == "Vacances d'été 2026"
