"""Gate de compatibilité iOS 12 sur le front statique.

Ce test EST le garde-fou : il échoue tant que `web/` contient une cassure
bloquante pour Safari 12.5.8 (iPad mini 2 en cuisine).

⚠️ Il est attendu ROUGE tant que la refonte du front n'est pas faite — le
baseline mesuré le 2026-08-04 est 0/100 avec 2 bloquants (`<dialog>` +
`showModal()`, qui rendent la fiche recette littéralement inaccessible sur
l'appareil). Voir `xfail` ci-dessous : le jour où la refonte passe, le test
vire au vert et le `xfail(strict=True)` force à retirer la tolérance.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.compat

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
SCANNER = (
    PROJECT_ROOT.parent
    / "2025.11 Claude Code MarketPlace"
    / "skills" / "julien-audit-ios12-compat" / "scripts" / "audit_ios12.py"
)

MIN_SCORE = 90


def _run_audit() -> dict:
    if not SCANNER.exists():
        pytest.skip(f"scanner introuvable : {SCANNER}")
    proc = subprocess.run(
        [sys.executable, str(SCANNER), str(WEB_DIR), "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if not proc.stdout.strip():
        pytest.fail(f"le scanner n'a rien produit : {proc.stderr[:500]}")
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def audit() -> dict:
    return _run_audit()


@pytest.fixture(scope="module")
def scanner():
    """Importe le scanner pour tester ses analyses contextuelles directement.

    ⚠️ L'enregistrement dans `sys.modules` est OBLIGATOIRE avant `exec_module` :
    `@dataclass` résout ses annotations via `sys.modules[cls.__module__]`, et
    lève un AttributeError obscur si le module n'y est pas.
    """
    if not SCANNER.exists():
        pytest.skip(f"scanner introuvable : {SCANNER}")
    spec = importlib.util.spec_from_file_location("audit_ios12", SCANNER)
    if spec is None or spec.loader is None:
        pytest.skip("scanner non importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fmt(findings, limit=8) -> str:
    lines = [f"  {f['severity']:10} {f['file']}:{f['line']}  {f['feature']}"
             for f in findings[:limit]]
    if len(findings) > limit:
        lines.append(f"  … et {len(findings) - limit} autre(s)")
    return "\n".join(lines)


def test_no_blocking_incompatibility(audit):
    """Aucune cassure BLOQUANTE : celles qui rendent une fonctionnalité morte.

    `<dialog>` est le cas d'école : non seulement `showModal()` lève un
    TypeError, mais l'élément inconnu affiche son contenu EN PERMANENCE dans
    le flux de la page.
    """
    blockers = [f for f in audit["findings"] if f["severity"] == "bloquant"]
    assert not blockers, f"{len(blockers)} cassure(s) bloquante(s) :\n{_fmt(blockers)}"


def test_score_above_threshold(audit):
    assert audit["score"] >= MIN_SCORE, (
        f"score {audit['score']}/100 < {MIN_SCORE}\n"
        f"{_fmt(audit['findings'])}"
    )


def test_scanner_is_functional(audit):
    """Le scanner tourne et lit bien les fichiers — sans ça, un gate vert ne
    voudrait rien dire (un scanner muet ressemble à un code propre)."""
    assert audit["files_scanned"] >= 3, (
        f"seulement {audit['files_scanned']} fichier(s) scanné(s) — "
        "le scanner ne voit pas le front"
    )
    assert "score" in audit and "findings" in audit


def test_scanner_does_not_flag_its_own_documentation(scanner):
    """Méta-test : un fichier qui DOCUMENTE la syntaxe interdite ne doit pas
    être accusé de l'employer.

    Le front porte en tête un commentaire listant « ❌ ?. ?? ||= ». Le scanner
    le signalait comme trois cassures bloquantes. Un linter qui accuse ses
    propres commentaires perd toute crédibilité, et on finit par ignorer ses
    vraies alertes."""
    js = (
        "// ne pas utiliser ?. ni ?? ni ||=\n"
        "/* interdit : a?.b */\n"
        "var url = 'https://x.test/a?b';\n"
        "var ok = a && a.b;\n"
    )
    stripped = scanner._strip_js_comments(js)
    report = scanner.Report()
    scanner._scan_simple(stripped, scanner.JS_RULES, "t.js", report)
    assert not report.findings, [f.feature for f in report.findings]
    # La numérotation doit survivre au dépouillement.
    assert stripped.count("\n") == js.count("\n")


def test_real_syntax_is_still_caught(scanner):
    """Le dépouillement ne doit pas rendre le scanner aveugle au vrai code."""
    report = scanner.Report()
    scanner._scan_simple(
        scanner._strip_js_comments("var x = a?.b;\n"), scanner.JS_RULES, "t.js", report
    )
    assert [f.feature for f in report.findings] == ["chaînage optionnel ?."]


def test_javascript_syntax_stays_es2019(audit):
    """La syntaxe JS doit rester dans ce que le moteur d'iOS 12.5 parse.

    C'est le point le plus facile à casser sans s'en rendre compte : `?.` et
    `??` s'écrivent par réflexe, et rien dans un navigateur moderne ne
    proteste.
    """
    syntax = {"chaînage optionnel ?.", "coalescence ??", "affectation logique",
              "séparateur numérique (1_000)", "champ de classe privé",
              "bloc static de classe"}
    hits = [f for f in audit["findings"] if f["feature"] in syntax]
    assert not hits, f"syntaxe hors ES2019 :\n{_fmt(hits)}"


def test_flex_gap_detection_is_context_aware(scanner):
    """Méta-test du scanner : `gap` ne doit être signalé qu'en contexte flex.

    Sans cette distinction, toute la grille remonterait en faux positifs et le
    signal se noierait — c'est ce qui rend ce scanner utile face à un grep.
    """
    module = scanner
    css = (
        ".flex-cassé { display: flex; gap: 10px; }\n"
        ".grid-ok    { display: grid; gap: 10px; }\n"
    )
    report = module.Report()
    module._scan_flex_gap(css, "t.css", report)

    features = [f.feature for f in report.findings]
    assert features == ["gap en contexte flex"], (
        f"attendu 1 signalement (flex uniquement), obtenu {len(features)} : {features}"
    )
    assert report.findings[0].line == 1


def test_clamp_fallback_detection(scanner):
    """Méta-test : `clamp()` sans repli doit être signalé, avec repli non.

    L'enjeu est le mode d'échec MUET — si clamp() n'est pas supporté, la
    déclaration est jetée, la valeur retombe au défaut, et l'app paraît
    seulement « un peu différente ». Personne ne le signale jamais.
    """
    module = scanner
    sans_repli = "html { font-size: clamp(20px, 3.3vw, 40px); }"
    avec_repli = "html { font-size: 28px; font-size: clamp(20px, 3.3vw, 40px); }"

    r1, r2 = module.Report(), module.Report()
    module._scan_clamp_fallback(sans_repli, "a.css", r1)
    module._scan_clamp_fallback(avec_repli, "b.css", r2)

    assert len(r1.findings) == 1, "clamp() sans repli non détecté"
    assert not r2.findings, "faux positif : le repli était bien présent"
