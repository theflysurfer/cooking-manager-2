"""Compteur de rattachement à un aliment — il se lit avant les lignes (ADR 0032)."""

import pytest

from cooking_manager.matching import food_link_counts


class TestCounts:
    def test_unlinked_is_the_complement_not_a_guess(self):
        assert food_link_counts(3, 10) == {"linked": 3, "unlinked": 7, "total": 10}

    def test_an_empty_population_says_zero_of_zero(self):
        assert food_link_counts(0, 0) == {"linked": 0, "unlinked": 0, "total": 0}

    def test_a_null_count_is_zero_not_a_crash(self):
        assert food_link_counts(None, None)["total"] == 0

    def test_it_knows_how_to_fail(self):
        """Un garde-fou qui ne sait pas échouer n'en est pas un."""
        with pytest.raises(ValueError, match="depasse"):
            food_link_counts(11, 10)


SERVING_ROUTES = (
    ("/api/pantry", "get_pantry"),
    ("/api/menus/{slug}/shopping-list", "menu_shopping_list"),
)


class TestRoutesCarryTheCounter:
    """Un compteur qu'on peut oublier d'afficher n'est pas un compteur."""

    @pytest.mark.parametrize("path, handler", SERVING_ROUTES, ids=[p for p, _ in SERVING_ROUTES])
    def test_the_route_emits_food_link(self, path, handler):
        import inspect

        from backend import app as app_module

        fn = getattr(app_module, handler)
        source = inspect.getsource(inspect.unwrap(fn))
        assert '"food_link"' in source, (
            f"{path} ne rend plus food_link : le rattachement redevient invisible"
        )

    def test_both_routes_are_still_declared(self):
        from backend.app import app

        declared = {getattr(r, "path", "") for r in app.routes}
        for path, _ in SERVING_ROUTES:
            assert path in declared, f"{path} a disparu — le compteur ne sert plus rien"
