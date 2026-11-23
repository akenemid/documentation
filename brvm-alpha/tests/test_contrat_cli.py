"""Contrat de la ligne de commande pour le moteur embarqué (Odoo l'appelle en sous-processus).

- codes de retour (:mod:`brvm_alpha.erreurs`) : 0, 1, 2, 4, 5, 6, 7, 8, 130 ; **jamais 3** (le maître
  Odoo, processus 1 du conteneur, s'arrête s'il récolte un enfant sorti avec ce code) ;
- ``--format json`` : exactement un objet JSON sur la sortie standard, erreur comprise ;
- mode embarqué : dossiers obligatoires, chemins relatifs résolus dans les dossiers de données, aucune
  écriture dans le code, ``validate`` et ``backtest`` refusés, historique incomplet refusé ;
- ``notes add`` atomique, doublon sans écriture ; ``update`` (bilan, ``--sans-panel``, ``--workers``) ;
  ``report`` (état des sections, code non nul si l'ordre de bataille échoue).

Hors ligne : doublures pour les calculs lourds et le réseau, dossiers temporaires, aucun calcul sur S1.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from brvm_alpha import cli, erreurs, paths
from brvm_alpha.data import boc_download

ROOT = Path(__file__).resolve().parents[1]
BOC_FIX = ROOT / "tests" / "fixtures" / "notes" / "boc"


def run_cli(capsys, *argv: str) -> tuple[int, str, str]:
    """``(code, sortie standard, sortie d'erreur)`` ; une erreur d'arguments (``SystemExit``) donne son code."""
    try:
        code = cli.main(list(argv))
    except SystemExit as exc:
        code = exc.code
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def one_json(out: str) -> dict:
    """La sortie standard est exactement un objet JSON (``json.loads`` refuse tout texte en plus)."""
    d = json.loads(out)
    assert isinstance(d, dict) and d["bandeau"] == cli.BANNER
    return d


@pytest.fixture()
def fake_etat(monkeypatch):
    """Remplace la commande « etat » par une doublure qui écrit de la progression puis lève ``exc``."""
    box: dict = {}

    def handler(args):
        print("progression : étape 1")  # texte écrit sur la sortie standard par la commande
        exc = box.get("exc")
        if exc is not None:
            raise exc
        return box.get("code", 0)

    monkeypatch.setitem(cli.COMMANDS, "etat", handler)
    return box


@pytest.fixture()
def tiny(tmp_path_factory):
    """Dossier de données minuscule : sept BOC des fixtures et leur panel (historique incomplet)."""
    from brvm_alpha.data import store

    base = tmp_path_factory.mktemp("contrat_minuscule")
    (base / "boc_text").mkdir()
    for f in BOC_FIX.glob("boc_*.txt.gz"):
        shutil.copy(f, base / "boc_text" / f.name)
    store.build_panel(base / "boc_text", base / "panel", workers=1)
    return base


# ---------------------------------------------------------------------------
# Table des codes de retour, JSON toujours
# ---------------------------------------------------------------------------


from brvm_alpha.notes.store import StoreLockError  # noqa: E402

CASES = [
    (erreurs.DonneesAbsentes("panel absent"), 1, "donnees_absentes"),
    (FileNotFoundError("equities.parquet introuvable"), 1, "donnees_absentes"),
    (erreurs.HistoriqueIncomplet("historique incomplet"), 1, "historique_incomplet"),
    (erreurs.JournalIllisible("journal des notes illisible"), 1, "donnees_absentes"),
    (OSError("Could not open Parquet input source '<Buffer>': Parquet magic bytes not found"), 1, "donnees_absentes"),
    (erreurs.SaisieInvalide("date invalide"), 2, "saisie_invalide"),
    (erreurs.CleInconnue("aucune note d'identifiant 'abcd'"), 2, "saisie_invalide"),
    # Constat de recette : une ValueError ou une KeyError qui ne vient pas d'une saisie est une erreur interne.
    (ValueError("cannot convert float NaN to integer"), 7, "interne"),
    (KeyError("close_raw"), 7, "interne"),
    (erreurs.VerrouOccupe("verrou occupé : panel"), 4, "verrou_occupe"),
    (StoreLockError("verrou occupé : journal"), 4, "verrou_occupe"),
    (erreurs.AccesRefuse("HTTP 403"), 5, "acces_refuse"),
    (boc_download.DownloadStopped("HTTP 429", raison="bloque"), 5, "acces_refuse"),
    (MemoryError(), 6, "memoire"),
    (ImportError("/x/_hausdorff.cpython-311-x86_64-linux-gnu.so: failed to map segment from shared object"), 6,
     "memoire"),
    (RuntimeError("défaut inattendu"), 7, "interne"),
    (SystemExit(3), 7, "interne"),
    (SystemExit(259), 7, "interne"),
    (SystemExit(-253), 7, "interne"),
    (ModuleNotFoundError("No module named 'scipy'", name="scipy"), 8, "configuration"),
    (erreurs.ConfigurationError("pdftotext absent : installer poppler-utils"), 8, "configuration"),
    (KeyboardInterrupt(), 130, "interruption"),
]


@pytest.mark.parametrize("exc, code, kind", CASES, ids=[f"{type(c[0]).__name__}-{c[1]}" for c in CASES])
def test_every_failure_has_its_exit_code_and_one_json_object(fake_etat, capsys, exc, code, kind):
    fake_etat["exc"] = exc
    got, out, err = run_cli(capsys, "etat")
    assert got == code and out.strip() == "progression : étape 1"  # texte : la progression reste sur stdout
    assert err.strip() and "Traceback" not in err or code == 7
    fake_etat["exc"] = exc
    got, out, err = run_cli(capsys, "etat", "--format", "json")
    assert got == code != 3
    d = one_json(out)  # rien d'autre que l'objet : la progression est passée sur la sortie d'erreur
    assert d["ok"] is False and d["code"] == code and d["erreur"] == kind and d["message"]
    assert list(d) == ["ok", "code", "erreur", "message", "bandeau"]
    assert "progression : étape 1" in err


def test_internal_error_prints_a_trace_on_stderr_only(fake_etat, capsys):
    fake_etat["exc"] = TypeError("objet inattendu")
    code, out, err = run_cli(capsys, "etat", "--format", "json")
    assert code == 7 and one_json(out)["message"].startswith("erreur interne : TypeError")
    assert "Traceback" in err and "Traceback" not in out


def test_a_handler_never_returns_3_and_a_bare_failure_still_gives_json(fake_etat, capsys):
    fake_etat["code"] = 3
    assert run_cli(capsys, "etat")[0] == 7
    fake_etat["code"] = 1
    cli_say = cli._say

    def handler(args):
        cli_say("échec : rien à lire")
        return 1

    cli.COMMANDS["etat"] = handler
    code, out, _ = run_cli(capsys, "etat", "--format", "json")
    d = one_json(out)
    assert code == 1 and d == {"ok": False, "code": 1, "erreur": "donnees_absentes", "message": "échec : rien à lire",
                               "bandeau": cli.BANNER}
    cli.COMMANDS["etat"] = lambda args: 0
    code, out, _ = run_cli(capsys, "etat", "--format", "json")
    assert code == 0 and one_json(out) == {"ok": True, "bandeau": cli.BANNER}


def test_broken_pipe_is_silent(fake_etat, capsys, monkeypatch):
    fake_etat["exc"] = BrokenPipeError(32, "Broken pipe")
    monkeypatch.setattr(cli, "_silence_stdout", lambda stream: None)
    code, out, err = run_cli(capsys, "etat")
    assert code == 0 and "Traceback" not in err
    fake_etat["exc"] = BrokenPipeError(32, "Broken pipe")
    assert run_cli(capsys, "etat", "--format", "json")[0] == 1  # l'objet JSON n'a pas pu être lu


def test_argument_errors_exit_2_with_a_json_error_object(capsys, monkeypatch):
    from brvm_alpha.portfolio import recommend as rec

    monkeypatch.setattr(rec, "recommend", lambda *a, **k: (_ for _ in ()).throw(AssertionError("aucun calcul")))
    for argv in (["recommend", "--format", "json"],  # --capital manque
                 ["recommend", "--capital", "10M", "--couts", "inconnu", "--format", "json"],
                 ["notes", "add", "--conviction", "9", "--format=json"],
                 ["etat", "--forma", "json", "--option-inconnue"]):
        code, out, err = run_cli(capsys, *argv)
        d = one_json(out)
        assert code == 2 and d["ok"] is False and d["code"] == 2 and d["erreur"] == "saisie_invalide", argv
        assert "utilisation :" in err and "erreur :" in d["message"]
    code, out, err = run_cli(capsys, "recommend", "--capital", "10M", "--couts", "inconnu")
    assert code == 2 and out == "" and "choix invalide" in err  # texte : rien sur la sortie standard
    a = cli.build_parser().parse_args(["report", "--capital", "1M", "--couts", "optimiste"])
    assert a.couts == "optimistic"  # alias français gardés
    assert cli.json_demande(["etat", "--format", "json"]) and cli.json_demande(["x", "--format=json"])
    assert not cli.json_demande(["etat", "--format", "texte"]) and not cli.json_demande(["etat", "json"])


#: Motifs interdits : toute sortie en code 3 (Python ou shell).
EXIT3 = [re.compile(p) for p in (r"\bexit\s*\(\s*3\s*\)", r"SystemExit\s*\(\s*3\s*\)", r"_exit\s*\(\s*3\s*\)",
                                 r"(?m)^\s*exit\s+3\b", r"[;&|]\s*exit\s+3\b", r"\breturn\s+3\b")]


def test_no_exit_code_3_anywhere_in_the_package_and_the_scripts():
    files = [p for p in (ROOT / "brvm_alpha").rglob("*.py") if "__pycache__" not in p.parts]
    files += sorted((ROOT / "deploiement").glob("*.sh")) + sorted((ROOT / "deploiement").glob("*.py"))
    assert len(files) > 40
    for f in files:
        text = f.read_text(encoding="utf-8")
        for pat in EXIT3:
            if f.name == "macro.py" and pat.pattern == r"\breturn\s+3\b":
                continue  # quant/macro.py : « return 3 » est un délai de règlement (J+3), pas un code de sortie
            assert not pat.search(text), (f, pat.pattern)
    macro = (ROOT / "brvm_alpha" / "quant" / "macro.py").read_text(encoding="utf-8")
    assert "def main" not in macro and "sys.exit" not in macro


def test_model_name_is_absent_from_code_and_tests():
    word = "cla" + "ude"
    for base in ("brvm_alpha", "tests", "deploiement"):
        for f in (ROOT / base).rglob("*"):
            if f.is_file() and f.suffix in (".py", ".sh", ".txt", ".tsv", ".md") and "__pycache__" not in f.parts:
                assert word not in f.read_text(encoding="utf-8", errors="replace").lower(), f


# ---------------------------------------------------------------------------
# Mode embarqué (dans ce processus : fonctions de détection remplacées)
# ---------------------------------------------------------------------------


@pytest.fixture()
def embedded(tmp_path, monkeypatch):
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    data.mkdir()
    reports.mkdir()
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: True)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "REPORTS_DIR", reports)
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    return data, reports


def test_embedded_relative_paths_live_in_the_data_folders_and_never_in_the_code(embedded, capsys, monkeypatch):
    from brvm_alpha.notes.store import NoteStore
    from brvm_alpha.portfolio import recommend as rec

    data, reports = embedded
    code, out, _ = run_cli(capsys, "notes", "add", "--racine", "notes", "--cible", "SNTS", "--titre", "Essai",
                           "--format", "json")
    assert code == 0 and one_json(out)["cree"] is True and len(NoteStore(data / "notes")) == 1
    code, out, _ = run_cli(capsys, "notes", "list", "--racine", "data/notes", "--format", "json")  # « data/ » retiré
    assert code == 0 and one_json(out)["n"] == 1

    class Order:
        asof = pd.Timestamp("2026-11-20")
        avertissements: list = []

        def to_markdown(self):
            return "# Ordre\n" + "\n".join(self.avertissements)

        def to_dict(self):
            return {"bandeau": cli.BANNER, "avertissements": self.avertissements}

    monkeypatch.setattr(rec, "recommend", lambda *a, **k: Order())
    monkeypatch.setattr(cli, "history_state", lambda *a, **k: {"complet": True, "raison": None, "jours_manquants": 0,
                                                                "avertissement": None})
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--date", "2026-11-20", "--sortie", "ordre.md",
                           "--format", "json")
    assert code == 0 and one_json(out)["chemin"] == str(reports / "ordre.md") and (reports / "ordre.md").is_file()
    inside = paths.REPO_ROOT / "brvm_alpha" / "essai_interdit.md"
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--sortie", str(inside), "--format", "json")
    assert code == 8 and one_json(out)["erreur"] == "configuration" and not inside.exists()
    code, out, _ = run_cli(capsys, "notes", "list", "--racine", "../ailleurs", "--format", "json")
    assert code == 2 and "« .. »" in one_json(out)["message"]
    elsewhere = data.parent / "ailleurs" / "ordre.md"  # ni données, ni rapports, ni fichiers temporaires
    monkeypatch.setattr("tempfile.tempdir", str(data.parent / "tmp_systeme"))
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--sortie", str(elsewhere), "--format", "json")
    assert code == 2 and "hors des dossiers permis" in one_json(out)["message"] and not elsewhere.exists()


@pytest.mark.parametrize("argv", [["validate", "--sample", "S0"], ["backtest", "--start", "2023-01-02", "--end",
                                                                     "2023-06-30"]])
def test_embedded_refuses_validation_commands(embedded, capsys, argv, monkeypatch):
    from brvm_alpha import validation

    monkeypatch.setattr(validation, "run_validation", lambda *a, **k: (_ for _ in ()).throw(AssertionError("non")))
    code, _out, err = run_cli(capsys, *argv)
    assert code == 8 and "n'est pas livrée dans Odoo" in err


def test_embedded_configuration_error_stops_every_command_before_any_write(embedded, capsys, monkeypatch):
    data, reports = embedded
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION",
                        erreurs.ConfigurationError("mode embarqué : la variable BRVM_ALPHA_DONNEES est obligatoire"))
    for argv in (["etat", "--format", "json"], ["notes", "add", "--titre", "x", "--format", "json"],
                 ["update", "--simulation", "--format", "json"], ["panel", "--format", "json"]):
        code, out, _ = run_cli(capsys, *argv)
        assert code == 8 and one_json(out)["erreur"] == "configuration", argv
    assert not any(data.iterdir()) and not any(reports.iterdir())


def test_embedded_mode_without_folders_in_a_real_process_writes_nothing(tmp_path):
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONPATH": str(ROOT), "BRVM_ALPHA_EMBARQUE": "1",
           "PYTHONDONTWRITEBYTECODE": "1"}
    real_journal = ROOT / "data" / "notes" / "notes.jsonl"
    before = real_journal.stat().st_mtime_ns if real_journal.exists() else None
    for argv, extra in ((["etat", "--format", "json"], {}),
                        (["notes", "add", "--titre", "x", "--format", "json"], {}),
                        (["etat", "--format", "json"], {"BRVM_ALPHA_DONNEES": "relatif", "BRVM_ALPHA_RAPPORTS": "/tmp"}),
                        (["etat", "--format", "json"], {"BRVM_ALPHA_DONNEES": str(ROOT / "data"),
                                                        "BRVM_ALPHA_RAPPORTS": str(tmp_path / "r")})):
        r = subprocess.run([sys.executable, "-m", "brvm_alpha", *argv], env={**env, **extra}, cwd=tmp_path,
                           capture_output=True, text=True, timeout=120)
        d = json.loads(r.stdout)
        assert r.returncode == 8 and d["code"] == 8 and d["erreur"] == "configuration", (argv, extra, r.stderr)
    assert not any(tmp_path.iterdir())
    after = real_journal.stat().st_mtime_ns if real_journal.exists() else None
    assert before == after


# ---------------------------------------------------------------------------
# Historique incomplet
# ---------------------------------------------------------------------------


class _Order:
    asof = pd.Timestamp("2026-10-29")

    def __init__(self):
        self.avertissements = ["avertissement existant"]

    def to_markdown(self):
        return "# Ordre de bataille\n" + "\n".join(f"> {w}" for w in self.avertissements)

    def to_dict(self):
        return {"bandeau": cli.BANNER, "avertissements": list(self.avertissements)}

    def to_html_fragment(self):
        return "<section></section>"


def test_incomplete_history_warns_in_normal_mode_and_refuses_in_embedded_mode(tiny, capsys, monkeypatch, tmp_path):
    import brvm_alpha.report as report
    from brvm_alpha.portfolio import recommend as rec

    calls: list[str] = []
    monkeypatch.setattr(rec, "recommend", lambda *a, **k: calls.append("recommend") or _Order())

    def fake_report(asof, capital, out, **k):
        calls.append("report")
        assert k["historique"]["complet"] is False
        Path(out).write_text("<html></html>", encoding="utf-8")
        return Path(out)

    monkeypatch.setattr(report, "build_report", fake_report)
    panel = ["--panel-dir", str(tiny / "panel"), "--sans-notes"]
    code, out, err = run_cli(capsys, "recommend", "--capital", "10M", *panel)
    assert code == 0 and "HISTORIQUE INCOMPLET" in out.splitlines()[1] and "HISTORIQUE INCOMPLET" in err
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--format", "json", *panel)
    d = one_json(out)
    assert code == 0 and d["historique_complet"] is False and d["avertissements"][0].startswith("HISTORIQUE INCOMPLET")
    assert "jour(s) ouvré(s) sans bulletin" in d["avertissement_historique"]
    code, out, _ = run_cli(capsys, "report", "--capital", "10M", "--format", "json", "--sortie",
                           str(tmp_path / "r.html"), *panel[:2])
    assert code == 0 and one_json(out)["historique_complet"] is False
    # Mode embarqué : refus (code 1, « historique_incomplet ») sauf option explicite.
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: True)
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    calls.clear()
    for argv in (["recommend", "--capital", "10M", "--sans-notes"], ["report", "--capital", "10M", "--sortie",
                                                                     str(tmp_path / "r2.html")]):
        code, out, _ = run_cli(capsys, *argv, "--format", "json", *panel[:2])
        d = one_json(out)
        assert code == 1 and d["erreur"] == "historique_incomplet" and "--accepter-historique-incomplet" in d["message"]
    assert calls == [] and not (tmp_path / "r2.html").exists()
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--format", "json", "--accepter-historique-incomplet",
                           *panel)
    assert code == 0 and one_json(out)["historique_complet"] is False and calls == ["recommend"]


def test_indices_and_explain_carry_the_history_key(tiny, capsys, monkeypatch):
    from brvm_alpha.notes import index_eval

    monkeypatch.setattr(index_eval, "evaluate_indices", lambda **k: pd.DataFrame(
        {"label": ["BRVM Composite"], "date": [pd.Timestamp("2026-10-29")], "level": [1.0], "stance": ["NEUTRE"],
         "confidence": [0.5], "composite": [0.0], "reasons": [["r"]]}, index=pd.Index(["IDX:BRVM-C"])))
    code, out, _ = run_cli(capsys, "indices", "--panel-dir", str(tiny / "panel"), "--sans-notes", "--format", "json")
    assert code == 0 and one_json(out)["historique_complet"] is False
    code, out, _ = run_cli(capsys, "indices", "--panel-dir", str(tiny / "panel"), "--sans-notes")
    assert out.startswith("⚠ HISTORIQUE INCOMPLET")

    def fake_explain(symbol, asof, **k):
        return {"symbol": symbol, "asof": asof, "variant": "A", "text": "", "blocks": {"Valeur": {"z": 1.0}},
                "score": {}, "weight": 0.0, "risk_flags": {}, "banner": cli.BANNER, "choix_variante": None}

    monkeypatch.setattr(cli, "explain_symbol", fake_explain)
    code, out, _ = run_cli(capsys, "explain", "SNTS", "--panel-dir", str(tiny / "panel"), "--sans-notes", "--format",
                           "json")
    d = one_json(out)
    assert code == 0 and "banner" not in d and d["decomposition"] == {"Valeur": {"z": 1.0}}
    assert d["historique_complet"] is False and "notes" in d


# ---------------------------------------------------------------------------
# notes add, report, update, panel, etat
# ---------------------------------------------------------------------------


def test_notes_add_json_contract(tmp_path, capsys):
    root = str(tmp_path / "notes")
    base = ["notes", "add", "--racine", root, "--cible", "SNTS", "--titre", "Sonatel : dividende", "--texte",
            "Dividende net de 1 800 FCFA contre 1 655 FCFA.", "--avis", "haussier", "--format", "json"]
    code, out, _ = run_cli(capsys, *base, "--publie-le", "2026-11-18")
    d = one_json(out)
    assert code == 0 and d["ok"] is True and d["cree"] is True and d["doublon_id"] is None
    assert d["note"]["published_at"].startswith("2026-11-18")  # --publie-le gardé tel quel
    assert {"note_id", "score", "filtres", "seance_application", "notes_connues", "prise_en_compte"} <= set(d)
    first = d["note_id"]
    code, out, _ = run_cli(capsys, *base, "--publie-le", "2026-11-18")
    d = one_json(out)
    assert code == 0 and d["cree"] is False and d["doublon_id"] == first and d["meme_identifiant"] is True
    code, out, _ = run_cli(capsys, *base, "--publie-le", "2026-11-19")  # même contenu, autre date : doublon
    d = one_json(out)
    assert code == 0 and d["cree"] is False and d["doublon_id"] == first and d["meme_identifiant"] is False
    from brvm_alpha.notes.store import NoteStore

    assert len(NoteStore(root)) == 1
    code, out, _ = run_cli(capsys, "notes", "add", "--racine", root, "--titre", "x", "--url", "ftp://x", "--format",
                           "json")
    assert code == 2 and one_json(out)["erreur"] == "saisie_invalide"
    code, out, _ = run_cli(capsys, "notes", "archive", "--racine", root, first[:8], "--format", "json")
    assert code == 0 and one_json(out)["archivee"] is True


def _fake_rendered(ordre_status: str, code: int | None):
    from brvm_alpha.report.html import RapportHTML, SectionResult

    secs = [SectionResult("bandeau", "Bandeau", "ok"), SectionResult("ordre", "Ordre de bataille", ordre_status,
                                                                       "RuntimeError : panne", 0.1, code)]
    return RapportHTML(html="<html></html>", sections=secs, asof=pd.Timestamp("2026-11-20"))


@pytest.mark.parametrize("status, section_code, expected", [("ok", None, 0), ("erreur", 7, 7), ("indisponible", 1, 1),
                                                            ("erreur", 8, 8)])
def test_report_gives_the_state_of_each_section_and_fails_when_the_order_fails(tmp_path, capsys, monkeypatch, status,
                                                                                section_code, expected):
    import brvm_alpha.report as report

    def fake(asof, capital, out, **k):
        Path(out).write_text("<html></html>", encoding="utf-8")
        k["rendu"].append(_fake_rendered(status, section_code))
        return Path(out)

    monkeypatch.setattr(report, "build_report", fake)
    monkeypatch.setattr(cli, "history_state", lambda *a, **k: {"complet": True, "raison": None, "jours_manquants": 0,
                                                                "avertissement": None})
    code, out, _ = run_cli(capsys, "report", "--capital", "10M", "--date", "2026-11-20", "--sortie",
                           str(tmp_path / "r.html"), "--format", "json")
    d = one_json(out)
    assert code == expected and d["chemin"] == str(tmp_path / "r.html")
    assert [s["id"] for s in d["sections"]] == ["bandeau", "ordre"] and d["sections"][1]["statut"] == status
    assert d["ok"] is (expected == 0)
    if expected:
        assert d["code"] == expected and "section « Ordre de bataille »" in d["message"] and d["sections_en_echec"]


def test_report_write_is_atomic_and_memory_error_stops_the_report(tmp_path, monkeypatch):
    from brvm_alpha import fichiers
    from brvm_alpha.report import html as H

    seen = []
    real = fichiers.ecrire_atomique
    monkeypatch.setattr(fichiers, "ecrire_atomique", lambda p, data, **k: seen.append(Path(p)) or real(p, data, **k))
    rep = H.RapportHTML(html="<html>x</html>", sections=[], asof=None)
    out = rep.write(tmp_path / "a" / "rapport.html")
    assert seen == [tmp_path / "a" / "rapport.html"] and out.read_text(encoding="utf-8") == "<html>x</html>"
    assert rep.chemin == out and [p.name for p in out.parent.iterdir()] == ["rapport.html"]  # aucun .part laissé
    results: list = []
    with pytest.raises(MemoryError):
        H._run_section("ordre", "Ordre", None, lambda: (_ for _ in ()).throw(MemoryError()), results)
    H._run_section("ordre", "Ordre", None, lambda: (_ for _ in ()).throw(erreurs.ConfigurationError("x")), results)
    assert results[-1].statut == "erreur" and results[-1].code == 8


def test_update_json_bilan_sans_panel_and_workers(tmp_path, capsys, monkeypatch):
    from brvm_alpha.data import store
    from brvm_alpha.notes import research as rs

    boc = tmp_path / "boc"
    boc.mkdir()
    monkeypatch.setattr(rs, "DEFAULT_NOTES_DIR", tmp_path / "notes")
    good = boc_download.BASE_URL.format(date="20261119", suffix="_2")
    calls: list[str] = []

    def fake_fetcher(**kw):
        def fetch(url):
            calls.append(url)
            return (200, b"%PDF-1.4 essai") if url == good else (404, b"")

        fetch.session = type("S", (), {"n_requests": 0})()
        return fetch

    monkeypatch.setattr(cli, "brvm_fetcher", fake_fetcher)
    monkeypatch.setattr(boc_download, "convert_pdf", lambda content: ("ligne de cote\n" * 60, "pdftotext", "24.02"))
    built: list = []

    def fake_build(boc_dir, panel_dir, **kw):
        built.append(kw)
        return type("P", (), {"to_dict": lambda self: {"seances": 1}, "__str__": lambda self: "panel"})()

    monkeypatch.setattr(store, "build_panel", fake_build)
    argv = ["update", "--boc-dir", str(boc), "--panel-dir", str(tmp_path / "panel"), "--from", "2026-11-18",
            "--jusqu-au", "2026-11-19", "--format", "json"]
    code, out, _ = run_cli(capsys, *argv, "--sans-panel")
    d = one_json(out)
    assert code == 0 and d["bulletins_telecharges"] == 1 and d["panel_reconstruit"] is False and built == []
    assert d["debut"] == "2026-11-18" and d["arret"] is False and (boc / "boc_20261119.txt.gz").is_file()
    m = d["marqueurs"]  # 18/11 : 404 partout une fois, marqueur non définitif (seul un 404 répété le rend définitif)
    assert m["bulletins_en_cache"] == 1 and m["definitifs"] == 0 and m["a_reessayer"] == len(list(boc.glob("*.missing")))
    (boc / "boc_20261119.txt.gz").unlink()
    code, out, _ = run_cli(capsys, *argv, "--workers", "1")
    d = one_json(out)
    assert code == 0 and d["panel_reconstruit"] is True and built == [{"workers": 1, "force": False}]
    code, out, _ = run_cli(capsys, "update", "--boc-dir", str(boc), "--simulation", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["simulation"] is True and d["debut"] == "2017-01-02" and d["jours_a_chercher"] > 2000


def test_update_requires_pdftotext_in_embedded_mode(embedded, tmp_path, capsys, monkeypatch):
    import shutil as sh

    from brvm_alpha.notes import research as rs

    monkeypatch.setattr(rs, "DEFAULT_NOTES_DIR", tmp_path / "notes")
    monkeypatch.setattr(cli, "brvm_fetcher", lambda **k: (_ for _ in ()).throw(AssertionError("aucune requête")))
    real_which = sh.which
    monkeypatch.setattr(sh, "which", lambda name, *a, **k: None if name == "pdftotext" else real_which(name, *a, **k))
    code, out, _ = run_cli(capsys, "update", "--boc-dir", str(tmp_path / "boc"), "--from", "2026-11-18",
                           "--jusqu-au", "2026-11-19", "--format", "json")
    d = one_json(out)
    assert code == 8 and d["message"].startswith("pdftotext absent : installer poppler-utils")
    from brvm_alpha import etat

    state = etat.collect_state(panel_dir=tmp_path / "p", boc_dir=tmp_path / "b", notes_root=tmp_path / "n")
    assert state["extracteur_pdf"]["manquant"] is True and state["embarque"] is True


def test_panel_json_and_missing_boc_folder(tmp_path, capsys):
    code, out, _ = run_cli(capsys, "panel", "--boc-dir", str(tmp_path / "absent"), "--panel-dir",
                           str(tmp_path / "p"), "--format", "json")
    d = one_json(out)
    assert code == 1 and d["erreur"] == "donnees_absentes" and "dossier des BOC introuvable" in d["message"]
    boc = tmp_path / "boc"
    boc.mkdir()
    for f in sorted(BOC_FIX.glob("boc_*.txt.gz"))[:2]:
        shutil.copy(f, boc / f.name)
    code, out, err = run_cli(capsys, "panel", "--boc-dir", str(boc), "--panel-dir", str(tmp_path / "p"), "--workers",
                             "1", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["panel"]["seances"] == 2 and "Reconstruction du panel" in err


def test_etat_json_has_ok_and_pdf_state(tmp_path, capsys):
    code, out, _ = run_cli(capsys, "etat", "--panel-dir", str(tmp_path / "p"), "--boc-dir", str(tmp_path / "b"),
                           "--racine", str(tmp_path / "n"), "--format", "json")
    d = one_json(out)
    assert code == 0 and list(d)[:2] == ["ok", "bandeau"] and d["pret"] is False
    assert set(d["extracteur_pdf"]) == {"pdftotext", "chemin", "obligatoire", "manquant"}
    assert d["extracteur_pdf"]["obligatoire"] is False and d["embarque"] is False


def test_notes_research_and_lire_json(tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import research as rs

    monkeypatch.setattr(rs, "_requests_transport", lambda *a, **k: (_ for _ in ()).throw(AssertionError("réseau")))

    def fake_run(store, **kw):
        res = rs.ResearchResult()
        res.report = rs.ResearchReport(n_items=3, n_new=0, max_requests=kw["max_requests"])
        return res

    monkeypatch.setattr(rs, "run_research", fake_run)
    monkeypatch.setattr(rs, "enrich_documents", lambda store, **kw: {"n_candidates": 0, "n_read": 0, "stopped": None,
                                                                     "details": []}, raising=False)
    (tmp_path / "notes").mkdir()
    code, out, err = run_cli(capsys, "notes", "research", "--racine", str(tmp_path / "notes"), "--hors-ligne",
                             "--pdf", "0", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["recherche"]["elements_lus"] == 3 and d["hors_ligne"] is True and "Règles" in err
    assert (tmp_path / "notes" / ".recherche.lock").exists()  # une recherche à la fois sur ce journal
    code, out, _ = run_cli(capsys, "notes", "lire", "--racine", str(tmp_path / "notes"), "--hors-ligne", "--format",
                           "json")
    assert code == 0 and one_json(out)["lecture_documents"]["n_candidates"] == 0


def test_update_window_default_reaches_back_to_2017(tmp_path):
    boc = tmp_path / "boc"
    boc.mkdir()
    with gzip.open(boc / "boc_20261117.txt.gz", "wt", encoding="utf-8") as fh:
        fh.write("x")
    start, end, days = cli.update_window(boc, today=dt.date(2026, 11, 20))
    assert start == dt.date(2017, 1, 2) and end == dt.date(2026, 11, 20)
    assert dt.date(2026, 11, 17) not in days and days[0] == dt.date(2026, 11, 20) and days[-1] == dt.date(2017, 1, 2)


def test_panel_workers_get_a_short_temporary_folder_only_when_needed(monkeypatch, tmp_path):
    import tempfile

    long_dir = tmp_path / ("t" * 80)
    long_dir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(long_dir))
    with cli.short_tempdir_for_workers():
        inside = tempfile.gettempdir()
    assert len(inside) <= cli._TEMPDIR_MAX and inside in ("/tmp", "/var/tmp", "/dev/shm")
    assert tempfile.gettempdir() == str(long_dir)  # rétabli après le bloc
    monkeypatch.setattr(tempfile, "tempdir", "/tmp")
    with cli.short_tempdir_for_workers():
        assert tempfile.gettempdir() == "/tmp"


def test_term_signal_stops_a_command_cleanly_with_code_130(tmp_path):
    import signal
    import time

    prog = ("import sys, time\nfrom brvm_alpha import cli\n"
            "def lent(args):\n    print('début', file=sys.stderr, flush=True)\n    time.sleep(60)\n    return 0\n"
            "cli.COMMANDS['etat'] = lent\nraise SystemExit(cli.main(['etat', '--format', 'json']))\n")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen([sys.executable, "-c", prog], env=env, cwd=tmp_path, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    assert proc.stderr.readline().strip() == "début"
    time.sleep(0.2)
    proc.send_signal(signal.SIGTERM)
    out, err = proc.communicate(timeout=30)
    d = json.loads(out)
    assert proc.returncode == 130 and d["erreur"] == "interruption" and "signal TERM" in d["message"]
    assert "Traceback" not in err
