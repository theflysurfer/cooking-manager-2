"""E2E — l'API ne doit plus renvoyer d'artefacts de flottant.

Contexte (2026-08-04) : les colonnes numériques étaient en `REAL` (float4
Postgres). 3.8 stocké puis élargi en float8 à la lecture ressortait en
3.799999952316284, et le front l'affichait tel quel — « les macros avec 10
chiffres après la virgule ».

Correctif à deux niveaux, tous deux testés ici :
  * colonnes migrées en NUMERIC (supprime la cause) ;
  * arrondi + conversion Decimal→float à la sérialisation (couvre l'affichage,
    et évite qu'un Decimal remonte jusqu'au JSON).
"""

import pytest

pytestmark = pytest.mark.e2e

# Décimales tolérées par champ, alignées sur _ROUNDING côté backend.
MAX_DECIMALS = {
    "kcal": 1, "protein": 1, "carbs": 1, "fat": 1,
    "protein_density": 3,
    "price_unit": 2, "total_price": 2, "price_per_kg": 2, "total": 2,
}


def _decimals(value) -> int:
    text = repr(float(value))
    if "e" in text or "E" in text:
        return 99  # notation scientifique = jamais un nombre présentable
    return len(text.split(".")[1].rstrip("0")) if "." in text else 0


def _offenders(payload: dict) -> list[str]:
    bad = []
    for key, limit in MAX_DECIMALS.items():
        val = payload.get(key)
        if val is None or isinstance(val, (bool, str)):
            continue
        if _decimals(val) > limit:
            bad.append(f"{key}={val!r} ({_decimals(val)} décimales > {limit})")
    return bad


def test_recipe_macros_have_no_float_artifacts(client):
    r = client.get("/api/recipes", params={"limit": 500})
    r.raise_for_status()
    recipes = r.json()["recipes"]
    assert recipes, "aucune recette — impossible de conclure"

    failures = []
    for recipe in recipes:
        for source in (recipe.get("macros") or {}, recipe):
            for problem in _offenders(source):
                failures.append(f"{recipe['slug']}: {problem}")

    assert not failures, "artefacts de flottant :\n  " + "\n  ".join(failures[:10])


def test_recipe_detail_macros_are_clean(client):
    """La fiche détaillée passe par le même sérialiseur que la liste."""
    listing = client.get("/api/recipes", params={"limit": 500}).json()["recipes"]
    with_macros = [r for r in listing if r.get("macros")]
    assert with_macros, "aucune recette avec macros"

    for recipe in with_macros[:5]:
        detail = client.get(f"/api/recipes/{recipe['slug']}").json()
        problems = _offenders(detail.get("macros") or {}) + _offenders(detail)
        assert not problems, f"{recipe['slug']}: {problems}"


def test_no_decimal_leaks_into_json(client):
    """asyncpg rend des Decimal sur les colonnes NUMERIC. S'ils fuyaient
    jusqu'au JSON, ils sortiraient en chaîne — pas en nombre."""
    r = client.get("/api/recipes", params={"limit": 500})
    for recipe in r.json()["recipes"]:
        for key, val in (recipe.get("macros") or {}).items():
            assert isinstance(val, (int, float)), (
                f"{recipe['slug']}.{key} est un {type(val).__name__} "
                f"({val!r}) — un Decimal a fui jusqu'au JSON"
            )


def test_shopping_sessions_prices_are_clean(client):
    r = client.get("/api/shopping/sessions")
    r.raise_for_status()
    for session in r.json()["sessions"]:
        problems = _offenders(session)
        assert not problems, f"session {session['id']}: {problems}"
