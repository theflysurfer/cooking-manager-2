"""Configuration pytest — étages unitaires, compat iOS 12 et e2e opt-in."""

import os

import pytest

API_BASE = os.environ.get("COOKING_API_BASE", "https://cooking.srv759970.hstgr.cloud")

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
    """Client HTTP authentifié vers l'API réelle, timeout large (scraping Auchan)."""
    httpx = pytest.importorskip("httpx")

    user = os.environ.get("COOKING_API_USER")
    password = os.environ.get("COOKING_API_PASSWORD")
    if not user or not password:
        pytest.skip(
            "COOKING_API_USER / COOKING_API_PASSWORD absents : /api/ est derrière "
            "le basic-auth nginx, les e2e ne peuvent pas s'authentifier"
        )

    with httpx.Client(base_url=api_base, timeout=300.0, auth=(user, password)) as c:
        try:
            r = c.get("/health")
            r.raise_for_status()
        except Exception as exc:  # pragma: no cover - dépend du réseau
            pytest.skip(f"API injoignable sur {api_base} : {exc}")
        yield c
