"""E2E — non-régression du bug fondateur : l'ingestion détruisait les menus.

Contexte (2026-08-04) : `UPSERT_MENU` faisait `ON CONFLICT ON CONSTRAINT
menu_pkey` sur un SERIAL — qui n'entre jamais en conflit à l'INSERT — donc
l'upsert ne dédoublonnait rien et `DELETE FROM menu` était la seule protection.
Résultat : tout menu absent du vault était effacé à la première ingestion. Un
`POST /api/ingest` lancé pour charger des recettes a ainsi détruit le menu
structuré « Semaine du 3 au 7 août », d'où l'app qui n'affichait plus aucun jour.

Ces tests échoueraient sur le code d'avant le correctif.
"""

import uuid

import pytest

from .conftest import E2E_PREFIX

pytestmark = pytest.mark.e2e


@pytest.fixture
def throwaway_menu(client):
    """Crée un menu de test et le supprime à la fin, quoi qu'il arrive."""
    slug = f"{E2E_PREFIX}{uuid.uuid4().hex[:8]}"
    payload = {
        "title": f"Menu de test {slug}",
        "slug": slug,
        "week_start": "2026-08-03",
        "week_end": "2026-08-07",
        "status": "proposed",
        "meals": [
            {"day": "lundi", "date": "2026-08-03", "lunch": "Plat A", "dinner": "Plat B"},
            {"day": "mardi", "date": "2026-08-04", "lunch": "Plat C", "dinner": "Plat D"},
        ],
    }
    r = client.post("/api/menus", json=payload)
    r.raise_for_status()
    yield slug
    _delete_menu(client, slug)


def _delete_menu(client, slug: str) -> None:
    """Nettoyage réel — ne laisse aucune trace en base.

    L'endpoint DELETE a été ajouté précisément parce que ces tests le
    réclamaient : depuis que l'ingestion ne fait plus de `DELETE FROM menu`,
    un menu créé par l'API ne pouvait plus jamais être retiré.
    """
    client.delete(f"/api/menus/{slug}")


def _menus_by_slug(client) -> dict:
    r = client.get("/api/menus")
    r.raise_for_status()
    return {m["slug"]: m for m in r.json()["menus"]}


def test_menu_survives_two_consecutive_ingests(client, throwaway_menu):
    """LE test. Un menu créé par l'API doit survivre à deux ingestions vault.

    Avant le correctif, la première ingestion l'effaçait — sans erreur, sans
    trace, sans que rien ne le signale.
    """
    slug = throwaway_menu
    assert slug in _menus_by_slug(client), "le menu n'a pas été créé"

    for run in (1, 2):
        r = client.post("/api/ingest")
        r.raise_for_status()
        assert slug in _menus_by_slug(client), (
            f"le menu a été DÉTRUIT par l'ingestion #{run} — "
            "le DELETE FROM menu est de retour"
        )


def test_menu_keeps_its_day_structure_through_ingest(client, throwaway_menu):
    """La structure `meals` (jour par jour) doit survivre intacte.

    C'est elle qui répond à « on mange quoi quel jour » ; sa perte est ce qui
    forçait le front à retomber sur le dump markdown brut.
    """
    slug = throwaway_menu
    client.post("/api/ingest").raise_for_status()

    menu = _menus_by_slug(client)[slug]
    meals = menu.get("meals")
    assert meals, "les repas ont disparu — la structure jour est perdue"
    assert len(meals) == 2
    assert [m["day"] for m in meals] == ["lundi", "mardi"]
    assert meals[0]["lunch"] == "Plat A"


def test_vault_menu_gets_a_slug_from_its_filename(client):
    """Les menus issus du vault portent un slug dérivé du nom de fichier —
    c'est ce qui rend l'upsert possible sans DELETE."""
    client.post("/api/ingest").raise_for_status()
    menus = _menus_by_slug(client)

    vault_menus = [s for s in menus if not s.startswith((E2E_PREFIX, "legacy-"))]
    assert vault_menus, "aucun menu vault ingéré"
    for slug in vault_menus:
        assert slug and slug != "None"
        assert not slug.startswith("legacy-"), (
            f"{slug} est resté sur le slug de secours : le backfill de migration "
            "n'a pas été remplacé par la vraie valeur"
        )


def test_reposting_same_slug_updates_instead_of_duplicating(client, throwaway_menu):
    """POST /api/menus est idempotent : rejouer le même slug met à jour."""
    slug = throwaway_menu
    before = len(_menus_by_slug(client))

    r = client.post("/api/menus", json={
        "title": "Titre modifié", "slug": slug, "status": "active",
        "meals": [{"day": "dimanche", "dinner": "Nouveau plat"}],
    })
    r.raise_for_status()
    assert r.json()["created"] is False, "un doublon a été créé au lieu d'une mise à jour"

    menus = _menus_by_slug(client)
    assert len(menus) == before, "le nombre de menus a changé — il y a un doublon"
    assert menus[slug]["title"] == "Titre modifié"
    assert menus[slug]["meals"][0]["day"] == "dimanche"


def test_ingest_is_idempotent_on_recipe_count(client):
    """Deux ingestions consécutives donnent le même compte de recettes —
    aucune duplication, aucune perte."""
    first = client.post("/api/ingest").json()
    second = client.post("/api/ingest").json()
    assert first["recipes_ingested"] == second["recipes_ingested"]
    assert first["menus_ingested"] == second["menus_ingested"]


def test_delete_removes_the_menu_for_good(client):
    """La suppression doit être réelle — sinon chaque exécution de test laisse
    un résidu et la table dérive."""
    slug = f"{E2E_PREFIX}{uuid.uuid4().hex[:8]}"
    client.post("/api/menus", json={"title": "À supprimer", "slug": slug}).raise_for_status()
    assert slug in _menus_by_slug(client)

    r = client.delete(f"/api/menus/{slug}")
    r.raise_for_status()
    assert r.json()["deleted"] == slug
    assert slug not in _menus_by_slug(client)

    assert client.delete(f"/api/menus/{slug}").status_code == 404


def test_no_test_residue_left_behind(client):
    """Garde-fou d'hygiène : aucun menu de test ne doit subsister.

    Ce test tourne en dernier et attrape un nettoyage défaillant — un test qui
    pollue la production est un test qu'on finit par désactiver.
    """
    leftovers = [s for s in _menus_by_slug(client) if s.startswith(E2E_PREFIX)]
    assert not leftovers, f"résidus de test non nettoyés : {leftovers}"
