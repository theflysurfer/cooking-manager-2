"""E2E — non-régression web : intégrité des liens et couverture des routes.

Méthodologie : GUIDE_non_regression_web.md (skill julien-test-case-design).
Couche 1 : chaque slug du menu pointe vers une recette existante.
Couche 2 : chaque endpoint API répond au bon status.
"""

import pytest

pytestmark = pytest.mark.e2e


# ── Couche 2 — Smoke : chaque endpoint API répond ──────────────────────

SMOKE_ROUTES = [
    ("/health", 200),
    ("/api/menus", 200),
    ("/api/recipes", 200),
    ("/api/recipes?limit=1", 200),
    ("/api/filters", 200),
    ("/api/recipes/slug-inexistant-xyz-999", 404),
]


@pytest.mark.parametrize("path, expected", SMOKE_ROUTES, ids=[p for p, _ in SMOKE_ROUTES])
def test_api_route_responds(client, path, expected):
    r = client.get(path)
    assert r.status_code == expected, f"{path} → {r.status_code} (attendu {expected})"


def test_static_assets_served(client):
    """index.html, app.js, style.css servis sans erreur."""
    for asset in ("/index.html", "/app.js", "/style.css"):
        r = client.get(asset)
        assert r.status_code == 200, f"{asset} → {r.status_code}"
        assert len(r.content) > 100, f"{asset} quasi vide ({len(r.content)} octets)"


def test_js_cache_control_header(client):
    """Nginx doit envoyer Cache-Control sur les fichiers JS/CSS.

    Incident fondateur 2026-08-05 : Safari iPad servait l'ancien app.js
    depuis le cache parce que le header manquait.
    """
    r = client.get("/app.js")
    cc = r.headers.get("cache-control", "")
    assert "no-cache" in cc or "max-age=0" in cc, (
        f"Cache-Control manquant ou permissif sur /app.js : '{cc}'"
    )


# ── Couche 1 — Intégrité des liens : chaque slug menu → recette ───────

def test_all_menu_slugs_resolve_to_recipes(client):
    """Chaque slot du menu qui porte un _slug doit pointer vers une recette
    existante. Un slug fantôme = un lien mort dans le front."""
    menus = client.get("/api/menus").json()["menus"]
    dead = []
    checked = 0

    for menu in menus:
        for meal in (menu.get("meals") or []):
            for slot in ("breakfast", "lunch", "snack", "dinner"):
                slug = meal.get(slot + "_slug")
                if not slug:
                    continue
                checked += 1
                r = client.get(f"/api/recipes/{slug}")
                if r.status_code != 200:
                    day = meal.get("day", "?")
                    dead.append(f"{menu.get('slug','?')}/{day}/{slot}: '{slug}' → {r.status_code}")

    assert checked > 0, "aucun slug trouvé dans les menus — données vides ?"
    assert not dead, f"{len(dead)} lien(s) mort(s) :\n" + "\n".join(dead)


def test_leftovers_meals_have_no_slug(client):
    """Un repas de restes ne doit PAS avoir de slug — lui en donner
    ferait racheter les ingrédients du plat recyclé."""
    menus = client.get("/api/menus").json()["menus"]
    violations = []

    for menu in menus:
        for meal in (menu.get("meals") or []):
            for slot in ("breakfast", "lunch", "snack", "dinner"):
                is_leftovers = meal.get(slot + "_leftovers")
                has_slug = meal.get(slot + "_slug")
                if is_leftovers and has_slug:
                    day = meal.get("day", "?")
                    violations.append(f"{day}/{slot}: restes AVEC slug '{has_slug}'")

    assert not violations, (
        "repas de restes avec un slug (achèterait les ingrédients) :\n"
        + "\n".join(violations)
    )


def test_recipe_detail_has_required_fields(client):
    """Chaque recette liée par un menu doit avoir les champs affichés
    par la vue recette : title, au minimum."""
    menus = client.get("/api/menus").json()["menus"]
    slugs = set()
    for menu in menus:
        for meal in (menu.get("meals") or []):
            for slot in ("breakfast", "lunch", "snack", "dinner"):
                s = meal.get(slot + "_slug")
                if s:
                    slugs.add(s)

    incomplete = []
    for slug in sorted(slugs):
        r = client.get(f"/api/recipes/{slug}")
        if r.status_code != 200:
            continue
        recipe = r.json()
        if not recipe.get("title"):
            incomplete.append(f"{slug}: title manquant")
        if not recipe.get("ingredients") and not recipe.get("steps"):
            incomplete.append(f"{slug}: ni ingrédients ni étapes")

    assert not incomplete, (
        "recette(s) incomplète(s) pour l'affichage :\n" + "\n".join(incomplete)
    )


# ── Couche 1 bis — Catalogue : chaque recette a un slug stable ────────

def test_all_recipes_have_slugs(client):
    """Chaque recette du catalogue doit avoir un slug non vide — c'est la
    clé pour les liens menu → recette et pour les URLs."""
    r = client.get("/api/recipes")
    r.raise_for_status()
    recipes = r.json().get("recipes", [])
    assert recipes, "catalogue vide"

    missing = [rec.get("title", "?") for rec in recipes if not rec.get("slug")]
    assert not missing, f"recette(s) sans slug : {missing}"
