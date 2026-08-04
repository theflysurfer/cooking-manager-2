"""Configuration pytest — trois étages de tests.

  * unitaires  : purs, sans réseau ni DB. Toujours joués.
  * compat     : gate iOS 12 sur le front statique. Toujours joué.
  * e2e        : frappent l'API RÉELLE (VPS). Opt-in via `-m e2e`.

Les e2e sont opt-in parce qu'ils écrivent en base de production. Ils créent
des objets préfixés `test-e2e-` et les nettoient systématiquement, mais on ne
veut pas qu'un `pytest` distrait les déclenche.

    pytest                  # unitaires + compat
    pytest -m e2e           # e2e seuls (VPS)
    pytest -m ""            # tout
"""

import os

import pytest

# Le VPS est la cible par défaut : ce projet n'a pas de serveur local
# (décision consignée en mémoire — toujours le VPS, jamais localhost).
API_BASE = os.environ.get("COOKING_API_BASE", "https://cooking.srv759970.hstgr.cloud")

# Préfixe de tout objet créé par les tests, pour pouvoir les reconnaître
# et les nettoyer sans jamais toucher aux vraies données.
E2E_PREFIX = "test-e2e-"


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: frappe l'API réelle (VPS) — opt-in")
    config.addinivalue_line("markers", "compat: gate de compatibilité iOS 12")


def pytest_collection_modifyitems(config, items):
    """Désélectionne les e2e sauf si `-m e2e` (ou `-m ""`) est demandé."""
    if config.getoption("-m"):
        return
    skip = pytest.mark.skip(reason="e2e opt-in : lancer avec `pytest -m e2e`")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def api_base() -> str:
    return API_BASE


@pytest.fixture(scope="session")
def client(api_base):
    """Client HTTP vers l'API réelle. Timeout large : l'enrichissement
    nutritionnel scrape le catalogue Auchan article par article."""
    httpx = pytest.importorskip("httpx")
    with httpx.Client(base_url=api_base, timeout=300.0) as c:
        try:
            r = c.get("/health")
            r.raise_for_status()
        except Exception as exc:  # pragma: no cover - dépend du réseau
            pytest.skip(f"API injoignable sur {api_base} : {exc}")
        yield c
