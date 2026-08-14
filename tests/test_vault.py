"""Unitaires — lecture du vault. Aucun réseau, aucune DB.

Le `slug` est la clé, pas le nom de fichier : deux fiches peuvent le déclarer en
double, et l'upsert d'ingestion n'en garde alors qu'une. Laquelle ne doit PAS
dépendre de l'ordre alphabétique du glob.
"""

from pathlib import Path

from cooking_manager.vault import read_recipes


def _write(dirpath: Path, name: str, *, slug: str, updated: str, marker: str) -> None:
    (dirpath / name).write_text(
        f"---\ntitle: Journal\nslug: {slug}\nupdated: {updated}\n---\n\n{marker}\n",
        encoding="utf-8",
    )


class TestDuplicateSlugs:
    """`<slug>-v2.md` trie AVANT `<slug>.md` ('-' < '.') : à l'ordre de glob, la
    version périmée écrasait la bonne. Constaté en production sur le journal
    Creami — l'app servait l'état du 08/07 alors que le vault décrivait le 06/08."""

    def _vault(self, tmp_path: Path) -> Path:
        recipes = tmp_path / "Recettes"
        recipes.mkdir()
        _write(recipes, "journal.md", slug="journal", updated="2026-07-08", marker="PERIME")
        _write(recipes, "journal-v2.md", slug="journal", updated="2026-08-06", marker="A_JOUR")
        return tmp_path

    def test_the_most_recently_declared_wins(self, tmp_path: Path):
        recipes = read_recipes(self._vault(tmp_path))
        assert len(recipes) == 1
        assert "A_JOUR" in recipes[0]["_body"]

    def test_the_shadowed_file_is_reported(self, tmp_path: Path):
        """Un doublon écarté en silence est une fiche qui n'existe nulle part."""
        recipes = read_recipes(self._vault(tmp_path))
        shadowed = [Path(p).name for p in recipes[0]["_duplicate_paths"]]
        assert shadowed == ["journal.md"]

    def test_mtime_does_not_decide(self, tmp_path: Path):
        """Sur le VPS le vault est un mount rclone : le mtime date la COPIE.
        Le fichier périmé touché en dernier ne doit pas gagner pour autant."""
        vault = self._vault(tmp_path)
        stale = vault / "Recettes" / "journal.md"
        stale.touch()  # mtime le plus récent, donnée la plus ancienne
        recipes = read_recipes(vault)
        assert "A_JOUR" in recipes[0]["_body"]

    def test_distinct_slugs_are_both_kept(self, tmp_path: Path):
        recipes = tmp_path / "Recettes"
        recipes.mkdir()
        _write(recipes, "a.md", slug="a", updated="2026-01-01", marker="A")
        _write(recipes, "b.md", slug="b", updated="2026-01-01", marker="B")
        assert len(read_recipes(tmp_path)) == 2

    def test_no_duplicate_key_when_unique(self, tmp_path: Path):
        recipes = tmp_path / "Recettes"
        recipes.mkdir()
        _write(recipes, "a.md", slug="a", updated="2026-01-01", marker="A")
        assert "_duplicate_paths" not in read_recipes(tmp_path)[0]
