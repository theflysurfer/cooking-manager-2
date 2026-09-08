"""Configuration pytest — trois étages de tests."""

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
    """Client HTTP vers l'API réelle. Timeout large : l'enrichissement"""
    httpx = pytest.importorskip("httpx")
    with httpx.Client(base_url=api_base, timeout=300.0) as c:
        try:
            r = c.get("/health")
            r.raise_for_status()
        except Exception as exc:  # pragma: no cover - dépend du réseau
            pytest.skip(f"API injoignable sur {api_base} : {exc}")
        yield c
