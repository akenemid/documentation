"""Recette du moteur embarqué dans Odoo : constats corrigés (contrat, réseau, compatibilité).

Chaque essai reproduit un constat (il échouait avant la correction) :

- journal des notes illisible : l'ordre de bataille sortait en code 0 **sans** aucune note (vetos et achats
  bloqués ignorés) ; désormais code 1, et ``etat`` dit ``pret: false`` ;
- ``MemoryError`` avalée par un ``except Exception`` : code 0 avec un résultat dégradé ; désormais code 6 ;
- démarrage sous une mémoire trop basse, paquet manquant, signal TERM au démarrage : sortie sans objet JSON,
  code 1, 127, −11 ou −15 ; désormais un objet JSON et un code de la table (6, 8, 130) ;
- dossiers de données inexistants acceptés en mode embarqué ; désormais code 8 ;
- ``ValueError`` d'une bibliothèque (panel abîmé) classée « saisie invalide » (2) ; désormais 1 (panel
  illisible) ou 7 (erreur interne) ;
- ``update --delai nan`` : plus aucune attente entre deux requêtes ; désormais refusé (code 2) ;
- ``etat`` « prêt » alors que des séances n'avaient pas de bulletin lisible (marqueurs à réessayer) ;
- et les constats mineurs : cibles inconnues, chemins lus ou écrits hors des dossiers permis, garde « jamais 3 »,
  processus de travail liés à leur parent, attente des verrous, liens symboliques, ``serve`` en mode embarqué…

Hors ligne : dossiers temporaires, doublures, aucune requête vers l'extérieur.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from brvm_alpha import cli, demarrage, erreurs, etat, fichiers, paths
from brvm_alpha.data import boc_download as bd

ROOT = Path(__file__).resolve().parents[1]
BOC_FIX = ROOT / "tests" / "fixtures" / "notes" / "boc"


def run_cli(capsys, *argv: str) -> tuple[int, str, str]:
    try:
        code = cli.main(list(argv))
    except SystemExit as exc:
        code = exc.code
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def one_json(out: str) -> dict:
    d = json.loads(out)
    assert isinstance(d, dict) and d["bandeau"] == cli.BANNER
    return d


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    """Sept BOC des fixtures et leur panel (historique incomplet)."""
    from brvm_alpha.data import store

    base = tmp_path_factory.mktemp("recette_embarque")
    (base / "boc_text").mkdir()
    for f in BOC_FIX.glob("boc_*.txt.gz"):
        shutil.copy(f, base / "boc_text" / f.name)
    store.build_panel(base / "boc_text", base / "panel", workers=1)
    return base


def _env_sous_processus(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("BRVM_ALPHA_")}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(ROOT), "HTTPS_PROXY": "http://127.0.0.1:9",
                "HTTP_PROXY": "http://127.0.0.1:9"})
    env.update(extra)
    return env


def _moteur(args: list[str], env: dict[str, str], *, preexec=None, timeout: float = 120,
            cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", "-m", "brvm_alpha", *args], env=env, cwd=str(cwd or ROOT),
                          capture_output=True, text=True, timeout=timeout, preexec_fn=preexec)


# ---------------------------------------------------------------------------
# Journal des notes illisible (majeur)
# ---------------------------------------------------------------------------


def _reco_args(tiny: Path, racine: Path) -> list[str]:
    return ["recommend", "--capital", "10000000", "--sans-indices", "--tirages", "50", "--panel-dir",
            str(tiny / "panel"), "--racine", str(racine), "--format", "json"]


def test_unreadable_notes_journal_stops_the_order_instead_of_ignoring_vetoes(tiny, tmp_path, capsys):
    racine = tmp_path / "notes"
    (racine / "notes.jsonl").mkdir(parents=True)  # journal remplacé par un dossier (constat de recette)
    code, out, _ = run_cli(capsys, *_reco_args(tiny, racine))
    d = one_json(out)
    assert code == 1 and d["ok"] is False and d["erreur"] == "donnees_absentes"  # avant : code 0, sans note
    assert "journal des notes illisible" in d["message"]
    for argv in (["explain", "SNTS"], ["indices"]):
        code, out, _ = run_cli(capsys, *argv, "--panel-dir", str(tiny / "panel"), "--racine", str(racine),
                               "--format", "json")
        assert code == 1 and one_json(out)["erreur"] == "donnees_absentes", argv
    for argv in (["notes", "list"], ["notes", "add", "--cible", "SNTS", "--titre", "t", "--texte", "x"]):
        code, out, _ = run_cli(capsys, *argv, "--racine", str(racine), "--format", "json")
        assert code == 1 and "journal des notes illisible" in one_json(out)["message"], argv  # avant : 7
    # etat : notes.lisible faux, donc pas « prêt », avec la raison
    st = etat.notes_state(cli._notes_store(racine), tiny / "panel", None, cli.now_utc())
    assert st["journal_present"] is True and st["lisible"] is False and "illisible" in st["erreur"]
    # un journal ABSENT reste sans effet : l'ordre de bataille est rendu
    (tmp_path / "vide").mkdir()
    code, out, _ = run_cli(capsys, *_reco_args(tiny, tmp_path / "vide"))
    assert code == 0 and one_json(out)["ok"] is True


def test_etat_is_not_ready_with_an_unreadable_journal(tiny, tmp_path, monkeypatch):
    racine = tmp_path / "notes"
    (racine / "notes.jsonl").mkdir(parents=True)
    monkeypatch.setattr(etat, "readiness", lambda panel, bulletins: (True, None))  # historique réputé complet
    st = etat.collect_state(panel_dir=tiny / "panel", boc_dir=tiny / "boc_text", notes_root=racine,
                            reports_dir=tmp_path, data_dir=tmp_path)
    assert st["pret"] is False and st["raison"].startswith("journal des notes illisible")
    assert st["notes"]["lisible"] is False and st["notes"]["au_journal"] == 0
    (racine / "notes.jsonl").rmdir()
    (racine / "notes.jsonl").write_text('{"pas": "une note"}\n{abîmé\n', encoding="utf-8")
    st = etat.collect_state(panel_dir=tiny / "panel", boc_dir=tiny / "boc_text", notes_root=racine,
                            reports_dir=tmp_path, data_dir=tmp_path)
    assert st["pret"] is True and st["notes"]["lisible"] is True and st["notes"]["lignes_illisibles"] == 2
    assert any("2 ligne(s) illisible(s)" in a for a in st["avertissements"])


# ---------------------------------------------------------------------------
# MemoryError jamais avalée (majeur)
# ---------------------------------------------------------------------------


def test_memory_error_in_the_notes_overlay_exits_6_not_a_degraded_0(tiny, tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import signals

    def boom(*a, **k):
        raise MemoryError("Unable to allocate 962. KiB for an array")

    monkeypatch.setattr(signals, "manual_overlays", boom)
    code, out, _ = run_cli(capsys, *_reco_args(tiny, tmp_path))
    d = one_json(out)
    assert code == 6 and d["erreur"] == "memoire"  # avant : code 0, « surcouches des notes non calculées »


def test_memory_error_in_the_stress_guard_and_the_panels_propagates(tiny, monkeypatch):
    import pandas as pd

    from brvm_alpha.data import store
    from brvm_alpha.portfolio import stress
    from brvm_alpha.strategy import BrvmAlpha, alpha

    def boom(*a, **k):
        raise MemoryError("Unable to allocate")

    monkeypatch.setattr(BrvmAlpha, "risk_flags", boom)
    idx = pd.bdate_range("2026-01-05", periods=5)
    panels = {"close": pd.DataFrame({"SNTS": [1.0, 2, 3, 4, 5]}, index=idx)}
    with pytest.raises(MemoryError):  # avant : « contrôle non évaluable (MemoryError …) », code 0
        stress._split_guard(panels, idx[-1], "SNTS", 0.6)
    monkeypatch.setattr(store, "composite_tr_reconstructed", boom)
    with pytest.raises(MemoryError):  # avant : « Composite TR indisponible », distribution sans indice TR
        alpha.build_panels(tiny / "panel")


def test_no_broad_handler_swallows_memory_errors():
    """Chaque ``except Exception`` du moteur (hors interface web, validation et backtest, qui ne tournent pas dans
    Odoo) est précédé, dans le même ``try``, d'une clause qui laisse passer ``MemoryError`` (code 6, jamais un
    résultat dégradé en code 0)."""
    bad = []
    for f in sorted((ROOT / "brvm_alpha").rglob("*.py")):
        rel = f.relative_to(ROOT / "brvm_alpha")
        if ("__pycache__" in f.parts or rel.parts[0] in ("ui", "validation")
                or rel.as_posix() in ("backtest/metrics.py", "backtest/walkforward.py")
                or f.name in ("demarrage.py", "erreurs.py")):
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Try):
                continue
            seen_memory = False
            for h in node.handlers:
                names = {n.id for n in ast.walk(h.type) if isinstance(n, ast.Name)} if h.type is not None else set()
                if "MemoryError" in names or "BaseException" in names:
                    seen_memory = True
                if "Exception" in names and not seen_memory:
                    bad.append(f"{rel}:{h.lineno}")
    assert bad == []


def test_memory_import_errors_are_memory_errors(tmp_path):
    """« failed to map segment » au chargement d'une bibliothèque compilée : MemoryError (code 6), pas une
    ImportError prise pour un module absent (repli silencieux)."""
    code = r"""
import importlib.machinery as m, json, sys
import brvm_alpha  # pose la garde du chargement
orig = m.ExtensionFileLoader.create_module
def fail(self, spec):
    raise ImportError(f"{spec.origin}: failed to map segment from shared object")
m.ExtensionFileLoader.create_module = fail
import os, sysconfig
dyn = sysconfig.get_config_var("DESTSHARED") or ""
names = sorted({f.split(".")[0] for f in (os.listdir(dyn) if os.path.isdir(dyn) else []) if f.endswith(".so")})
out = {}
import importlib.util
def ours(n):  # trouvé par le chargeur standard des fichiers (un autre chercheur peut servir certains modules)
    try:
        return type(importlib.util.find_spec(n).loader).__name__ == "ChargeurExtension"
    except Exception:
        return False
for name in [n for n in names if n not in sys.modules and not n.startswith("_test") and ours(n)][:4]:
    try:
        __import__(name)
        out[name] = "importé"
    except MemoryError as exc:
        out[name] = "MemoryError"
    except ImportError as exc:
        out[name] = "ImportError : " + str(exc)[:80]
print(json.dumps(out))
"""
    r = subprocess.run([sys.executable, "-B", "-c", code], env=_env_sous_processus(), capture_output=True, text=True,
                       timeout=120, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout)
    if not out:
        pytest.skip("aucune extension compilée à charger dans cet interpréteur")
    assert all(v == "MemoryError" for v in out.values()), out
    assert erreurs.code_retour(ImportError("x.so: failed to map segment from shared object")) == 6
    assert erreurs.code_retour(ImportError("libx.so: cannot allocate memory in static TLS block")) == 7


# ---------------------------------------------------------------------------
# Garde du démarrage : mémoire, paquet manquant, TERM (majeurs)
# ---------------------------------------------------------------------------


def _limite(octets: int):
    def f():
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (octets, octets))
    return f


def test_too_low_memory_limit_exits_6_with_one_json_object_before_loading_pandas(tmp_path):
    d, r = tmp_path / "d", tmp_path / "r"
    d.mkdir(), r.mkdir()
    env = _env_sous_processus(BRVM_ALPHA_EMBARQUE="1", BRVM_ALPHA_DONNEES=str(d), BRVM_ALPHA_RAPPORTS=str(r))
    p = _moteur(["etat", "--format", "json"], env, preexec=_limite(300 * 1024 ** 2), cwd=tmp_path)
    obj = json.loads(p.stdout)  # avant : code 1 sans JSON (OpenBLAS, ImportError) ou figé
    assert p.returncode == 6 and obj["ok"] is False and obj["code"] == 6 and obj["erreur"] == "memoire"
    assert "300 Mo" in obj["message"] and obj["bandeau"] == cli.BANNER
    p = _moteur(["etat"], env, preexec=_limite(300 * 1024 ** 2), cwd=tmp_path)
    assert p.returncode == 6 and p.stdout == "" and "limite de mémoire virtuelle trop basse" in p.stderr
    assert demarrage.controle_memoire({}, limite=2 * 1024 ** 3) is None
    assert demarrage.controle_memoire({demarrage.ENV_MEMOIRE_MIN: "0"}, limite=10) is None
    assert "au moins 2048 Mo" in demarrage.controle_memoire({demarrage.ENV_MEMOIRE_MIN: "2048"}, limite=1024 ** 3)


def test_missing_package_at_load_time_exits_8_with_one_json_object(tmp_path):
    launcher = ("import sys, runpy; sys.modules['pandas'] = None; sys.argv = ['brvm_alpha'] + sys.argv[1:]; "
                "runpy.run_module('brvm_alpha', run_name='__main__', alter_sys=True)")
    p = subprocess.run([sys.executable, "-B", "-c", launcher, "etat", "--format", "json"], env=_env_sous_processus(),
                       capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    obj = json.loads(p.stdout)  # avant : trace et code 1 (« données absentes »), sortie vide
    assert p.returncode == 8 and obj["code"] == 8 and obj["erreur"] == "configuration" and "pandas" in obj["message"]
    assert list(obj) == ["ok", "code", "erreur", "message", "bandeau"]


def test_term_during_start_up_gives_130_and_the_interruption_object(tmp_path):
    proc = subprocess.Popen([sys.executable, "-B", "-m", "brvm_alpha", "etat", "--panel-dir", str(tmp_path / "p"),
                             "--format", "json"], env=_env_sous_processus(), cwd=str(tmp_path),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.25)  # pendant le chargement de pandas (avant : code −15, sortie vide)
    proc.send_signal(signal.SIGTERM)
    out, err = proc.communicate(timeout=60)
    if proc.returncode == 0:  # machine très rapide : la commande avait déjà fini
        pytest.skip("commande finie avant le signal")
    assert proc.returncode == 130, err[-1500:]
    obj = json.loads(out)
    assert obj["code"] == 130 and obj["erreur"] == "interruption" and "TERM" in obj["message"]


def test_help_with_json_gives_one_object(capsys):
    code, out, err = run_cli(capsys, "etat", "--help", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["ok"] is True and "utilisation :" in d["aide"] and "utilisation :" in err
    code, out, _ = run_cli(capsys, "etat", "--help")
    assert code == 0 and out.startswith("utilisation :")  # texte : inchangé


# ---------------------------------------------------------------------------
# Dossiers inexistants, commandes refusées, chemins (majeur et mineurs)
# ---------------------------------------------------------------------------


def test_embedded_mode_refuses_missing_data_folders_before_any_write(tmp_path):
    d, r = tmp_path / "inexistant" / "donnees", tmp_path / "inexistant" / "rapports"
    env = _env_sous_processus(BRVM_ALPHA_EMBARQUE="1", BRVM_ALPHA_DONNEES=str(d), BRVM_ALPHA_RAPPORTS=str(r))
    for args in (["notes", "add", "--cible", "SNTS", "--titre", "t", "--texte", "x"], ["etat"],
                 ["update", "--simulation"]):
        p = _moteur([*args, "--format", "json"], env, cwd=tmp_path)
        obj = json.loads(p.stdout)
        assert p.returncode == 8 and obj["erreur"] == "configuration" and "n'existe pas" in obj["message"], args
    assert not (tmp_path / "inexistant").exists()  # avant : notes.jsonl créé, collecte lancée au mauvais endroit


def test_serve_and_validate_are_refused_in_embedded_mode_before_argument_parsing(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: True)
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    for argv in (["serve"], ["validate", "--format", "json"], ["backtest", "--format", "json"],
                 ["serve", "--port", "9", "--format", "json"]):
        code, out, err = run_cli(capsys, *argv)
        assert code == 8, argv
        if "--format" in argv:
            d = one_json(out)
            assert d["erreur"] == "configuration" and "mode embarqué" in d["message"]
    assert "serve" in cli.EMBEDDED_REFUSED


def test_embedded_paths_cannot_read_server_files_or_overwrite_the_journal(tmp_path, capsys, monkeypatch):
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    (data / "notes").mkdir(parents=True)
    reports.mkdir()
    journal = data / "notes" / "notes.jsonl"
    journal.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: True)
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "REPORTS_DIR", reports)
    secret = ROOT / "configs" / "strategy_v1.yaml"  # un fichier hors des dossiers permis (lu seulement si accepté)
    code, out, _ = run_cli(capsys, "notes", "add", "--cible", "SNTS", "--titre", "lecture", "--fichier", str(secret),
                           "--racine", str(data / "notes"), "--format", "json")
    assert code == 2 and "--fichier" in one_json(out)["message"]  # avant : code 0, fichier recopié dans le journal
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--portefeuille", str(secret), "--format", "json")
    assert code == 2 and "--portefeuille" in one_json(out)["message"]
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--sortie", str(journal), "--format", "json")
    assert code == 2 and "fichier du moteur" in one_json(out)["message"]  # avant : journal écrasé
    assert journal.read_text(encoding="utf-8") == ""
    code, out, _ = run_cli(capsys, "report", "--capital", "10M", "--sortie", str(reports), "--format", "json")
    assert code == 2 and "est un dossier" in one_json(out)["message"]  # avant : 7, IsADirectoryError


def test_report_output_to_a_folder_is_refused_in_normal_mode_too(tmp_path, capsys):
    code, out, _ = run_cli(capsys, "report", "--capital", "10M", "--sortie", str(tmp_path), "--format", "json")
    assert code == 2 and one_json(out)["erreur"] == "saisie_invalide"


# ---------------------------------------------------------------------------
# Code 2 réservé aux saisies ; panel illisible : 1 (majeur)
# ---------------------------------------------------------------------------


def test_a_damaged_panel_is_unreadable_data_not_an_invalid_input(tiny, tmp_path, capsys):
    panel = tmp_path / "panel"
    shutil.copytree(tiny / "panel", panel)
    raw = (panel / "equities.parquet").read_bytes()
    (panel / "equities.parquet").write_bytes(raw[: len(raw) // 2])  # coupé de moitié (constat de recette)
    code, out, _ = run_cli(capsys, "explain", "SNTS", "--panel-dir", str(panel), "--racine", str(tmp_path),
                           "--format", "json")
    d = one_json(out)
    assert code == 1 and d["erreur"] == "donnees_absentes" and "panel illisible" in d["message"]  # avant : 2
    assert erreurs.code_retour(ValueError("cannot convert float NaN to integer")) == 7
    assert erreurs.code_retour(KeyError("close_raw")) == 7
    assert erreurs.code_retour(erreurs.SaisieInvalide("date invalide")) == 2


def test_user_input_errors_still_exit_2(capsys, tmp_path, tiny):
    for argv in (["recommend", "--capital", "abc"],
                 ["indices", "dossier", "IDX:INCONNU", "--panel-dir", str(tiny / "panel"), "--racine", str(tmp_path)],
                 ["notes", "show", "--racine", str(tmp_path), "zzzz"]):
        code, out, err = run_cli(capsys, *argv, "--format", "json")
        assert code == 2 and one_json(out)["erreur"] == "saisie_invalide", (argv, out, err)


def test_unknown_index_has_a_clear_message():
    from brvm_alpha.notes import index_eval

    with pytest.raises(erreurs.CleInconnue, match="indice inconnu : 'IDX:INCONNU'"):
        index_eval.index_dossier("IDX:INCONNU", panels={})


# ---------------------------------------------------------------------------
# update --delai : nombre fini, 10 à 3600 s (majeur)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "5", "1e9", "abc"])
def test_update_delay_must_be_a_finite_number_of_10_to_3600_seconds(value, capsys, monkeypatch, tmp_path):
    from brvm_alpha.notes import research as rs

    def no_network(*a, **k):
        raise AssertionError("aucune requête ne doit partir")

    monkeypatch.setattr(rs, "_requests_transport", no_network)
    code, out, _ = run_cli(capsys, "update", f"--delai={value}", "--boc-dir", str(tmp_path / "b"), "--panel-dir",
                           str(tmp_path / "p"), "--sans-panel", "--format", "json")
    d = one_json(out)
    assert code == 2 and d["erreur"] == "saisie_invalide" and "délai" in d["message"]  # avant : nan accepté
    assert "cannot convert" not in d["message"]


def test_non_finite_delays_are_refused_by_every_client():
    from brvm_alpha.notes import research as rs

    for bad in (float("nan"), float("inf")):
        with pytest.raises(erreurs.SaisieInvalide):
            rs.PoliteSession(delay_s=bad)
        with pytest.raises(erreurs.SaisieInvalide):
            bd.PoliteFetcher(pause=bad)
        with pytest.raises(erreurs.SaisieInvalide):
            bd.client_brvm(delay_s=bad)
    assert bd.delai_poli(3) == 10.0 and bd.delai_poli(12.5) == 12.5
    assert cli.build_parser().parse_args(["update", "--delai", "12,5"]).delai == 12.5


# ---------------------------------------------------------------------------
# « prêt » : marqueurs à réessayer comptés comme manquants (majeur)
# ---------------------------------------------------------------------------


def _historique_complet(boc: Path, today: dt.date) -> None:
    """Un bulletin, puis un ancien marqueur vide (définitif) pour chaque autre jour ouvré depuis 2017."""
    boc.mkdir(parents=True)
    shutil.copy(BOC_FIX / "boc_20261029.txt.gz", boc / "boc_20261029.txt.gz")
    for day in bd.weekdays(bd.HISTORY_START, today - dt.timedelta(days=bd.RECENT_DAYS + 1)):
        if day != dt.date(2026, 10, 29):
            (boc / f"boc_{day:%Y%m%d}.missing").write_bytes(b"")


def test_retry_markers_without_a_readable_bulletin_make_the_history_incomplete(tmp_path):
    today = dt.date(2026, 11, 23)
    boc = tmp_path / "boc"
    _historique_complet(boc, today)
    st = etat.bulletins_state(boc, today)
    assert st["historique_complet"] is True and st["jours_manquants"] == 0
    day = dt.date(2019, 4, 2)
    bd.ecrire_marqueur(boc, day, [("pas_un_pdf", 200, "https://www.brvm.org/x.pdf")],
                       now=dt.datetime(2026, 11, 22, 23, tzinfo=dt.timezone.utc))  # site en maintenance (HTML 200)
    st = etat.bulletins_state(boc, today)
    assert st["historique_complet"] is False and st["jours_manquants"] == 1 and st["sans_bulletin_lisible"] == 1
    assert st["a_reessayer"] == 1 and st["prochaine_relance"] == "2026-11-23"  # avant : « complet », « prêt »
    ok, reason = etat.readiness({"lisible": True, "seances_presentes": 10}, st)
    assert ok is False and "dont 1 sans bulletin lisible à réessayer (prochaine relance le 23/11/2026)" in reason
    # « introuvable » (404 partout) reste compté comme connu, même avant d'être définitif
    bd.ecrire_marqueur(boc, day, [("introuvable", 404, "https://www.brvm.org/x.pdf")],
                       now=dt.datetime(2026, 11, 22, 23, tzinfo=dt.timezone.utc))
    st = etat.bulletins_state(boc, today)
    assert st["historique_complet"] is True and st["a_reessayer"] == 1 and st["jours_manquants"] == 0


def test_two_404_attempts_ten_minutes_apart_across_midnight_count_once(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return 404, b""

    day = dt.date(2019, 6, 3)
    t0 = dt.datetime(2026, 11, 23, 23, 55, tzinfo=dt.timezone.utc)
    for when in (t0, t0 + dt.timedelta(minutes=10), t0 + dt.timedelta(days=1, minutes=10)):
        bd.fetch_one(fetch, day, tmp_path, today=when.date(), now=when)
    m = bd.lire_marqueur(bd.marker_path(tmp_path, day))
    # avant : trois tentatives (définitif) en 24 h 10 ; désormais l'essai de 00:05 n'est pas fait
    assert m.tentatives == 2 and m.definitif is False and len(calls) == 2 * len(bd.OLD_SUFFIXES)
    assert m.prochaine_relance() == dt.date(2026, 11, 26)  # un jour et 20 h au moins après le 25 à 00:05


# ---------------------------------------------------------------------------
# Mineurs : garde « jamais 3 », processus liés au parent, verrous, liens, saisies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [3, 259, -253, 515, 255, 9, -1, 1000, "x", None, 3.5])
def test_exit_codes_outside_the_table_become_7(code):
    assert erreurs.code_sur(code) == 7 and cli._code_sur(code) == 7
    if isinstance(code, int):
        assert erreurs.code_retour(SystemExit(code)) == 7
    assert all(erreurs.code_sur(c) == c for c in (0, 1, 2, 4, 5, 6, 7, 8, 130))


def test_panel_workers_die_with_their_parent():
    code = r"""
import ctypes, signal
from brvm_alpha import ressources
ressources.initialiser_travailleur()
libc = ctypes.CDLL(None, use_errno=True)
sig = ctypes.c_int(0)
libc.prctl(2, ctypes.byref(sig), 0, 0, 0)  # PR_GET_PDEATHSIG
print(sig.value == signal.SIGKILL)
"""
    r = subprocess.run([sys.executable, "-B", "-c", code], env=_env_sous_processus(), capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "True", r.stderr[-1500:]


def test_notes_journal_lock_honours_the_shared_wait_variable(tmp_path, monkeypatch):
    from brvm_alpha.notes.model import Note
    from brvm_alpha.notes.store import NoteStore, StoreLockError

    store = NoteStore(tmp_path)
    holder = subprocess.Popen([sys.executable, "-B", "-c", (
        "import fcntl, sys, time\nf = open(sys.argv[1], 'a')\nfcntl.flock(f, fcntl.LOCK_EX)\nprint('PRET', flush=True)\n"
        "time.sleep(30)"), str(store.lock_path)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "PRET"
        monkeypatch.setenv(fichiers.ENV_ATTENTE, "0.5")
        t = time.monotonic()
        with pytest.raises(StoreLockError):
            store.add(Note(title="t", text="x", targets=["SNTS"]))
        assert time.monotonic() - t < 4  # avant : 10 s quelle que soit la variable
    finally:
        holder.kill()
        holder.wait()


def test_atomic_writes_follow_symlinks_and_write_devices_directly(tmp_path):
    target = tmp_path / "cible.md"
    target.write_text("ancien", encoding="utf-8")
    link = tmp_path / "lien.md"
    os.symlink(target, link)
    fichiers.ecrire_atomique(link, "nouveau")
    assert link.is_symlink() and target.read_text(encoding="utf-8") == "nouveau"  # avant : lien remplacé
    null = tmp_path / "nul.md"
    os.symlink("/dev/null", null)
    fichiers.ecrire_atomique(null, "x" * 100)
    fichiers.ecrire_atomique_avec(null, lambda p: Path(p).write_text("y"))
    assert null.is_symlink() and os.readlink(null) == "/dev/null"
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".part")]


def test_package_detection_of_embedded_mode_agrees_with_paths(tmp_path):
    """``brvm_alpha/__init__.py`` coupe les ``.pyc`` avant tout import : même réponse que ``paths.est_embarque``,
    y compris quand le code est atteint par un lien symbolique."""
    real = tmp_path / "reel"
    shutil.copytree(ROOT / "brvm_alpha", real / "brvm_alpha", ignore=shutil.ignore_patterns("__pycache__"))
    (real / "VERSION").write_text("essai\n", encoding="utf-8")
    (tmp_path / "lien").mkdir()
    os.symlink(real / "brvm_alpha", tmp_path / "lien" / "brvm_alpha")
    code = "import sys, brvm_alpha\nfrom brvm_alpha import paths\nprint(sys.dont_write_bytecode, paths.est_embarque())"
    for where in (real, tmp_path / "lien"):
        env = {k: v for k, v in _env_sous_processus().items() if k not in ("PYTHONPATH", "PYTHONDONTWRITEBYTECODE")}
        r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(where), capture_output=True, text=True,
                           timeout=60)
        assert r.returncode == 0 and r.stdout.split() == ["True", "True"], (where, r.stderr[-1500:])
    # (le .pyc de __init__.py lui-même est écrit avant que son code ne tourne : d'où « -B » chez le lanceur)
    assert sorted(p.name for p in (real / "brvm_alpha" / "__pycache__").iterdir()) == [
        f"__init__.{sys.implementation.cache_tag}.pyc"]


def test_notes_add_refuses_a_note_without_any_known_target(tmp_path, capsys):
    racine = str(tmp_path / "notes")
    for cible in ("ZZZZ", ""):
        code, out, _ = run_cli(capsys, "notes", "add", "--racine", racine, "--cible", cible, "--titre", "t", "--texte",
                               "Texte de la note.", "--format", "json")
        assert code == 2 and one_json(out)["erreur"] == "saisie_invalide", cible  # avant : code 0, aucune cible
    assert not (tmp_path / "notes" / "notes.jsonl").exists()


# ---------------------------------------------------------------------------
# Réseau : en-têtes goutte à goutte, rebinding DNS, politesse par site, diagnostics
# ---------------------------------------------------------------------------


def _local_server(handler_fn):
    import http.server
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        hits: list[str] = []

        def log_message(self, *a):
            return

        def do_GET(self):  # noqa: N802
            H.hits.append(self.path)
            handler_fn(self)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, H.hits


def _guarded_session():
    from brvm_alpha import net

    sess = net.creer_session()
    sess.trust_env = False  # aucun mandataire de l'environnement pendant l'essai
    sess.proxies = {}
    return sess


def test_headers_sent_drop_by_drop_are_cut_at_the_total_deadline():
    from brvm_alpha import net

    def drip_headers(h):
        try:
            for b in b"HTTP/1.1 200 OK\r\nX-Lent: " + b"a" * 200:
                h.wfile.write(bytes([b]))
                h.wfile.flush()
                time.sleep(0.05)
        except OSError:
            pass

    httpd, hits = _local_server(drip_headers)
    try:
        port = httpd.server_address[1]
        pol = net.Politique(hotes=frozenset({f"127.0.0.1:{port}"}), schemas=frozenset({"http"}), adresses_locales=True,
                            delais={"page": 1.0}, delai_lecture=5.0)
        cli = net.ClientHttp(pol, session=_guarded_session())
        t0 = time.monotonic()
        with pytest.raises(net.DelaiDepasse, match="délai total"):
            cli.get(f"http://127.0.0.1:{port}/lent")
        assert time.monotonic() - t0 < 3.0  # avant : environ 11 s (en-têtes jamais bornés)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_address_actually_connected_is_checked_dns_rebinding():
    import socket as so

    from brvm_alpha import net

    def ok(h):
        h.send_response(200)
        h.send_header("Content-Length", "2")
        h.end_headers()
        h.wfile.write(b"ok")

    httpd, hits = _local_server(ok)
    try:
        port = httpd.server_address[1]
        pol = net.Politique(hotes=frozenset({f"localhost:{port}"}), schemas=frozenset({"http"}))

        def public_first(host, p, *a):  # résolution de contrôle : adresse publique ; la connexion : 127.0.0.1
            return [(so.AF_INET, so.SOCK_STREAM, 6, "", ("52.1.1.1", p))]

        cli = net.ClientHttp(pol, session=_guarded_session(), resolveur=public_first)
        with pytest.raises(net.AdresseInterdite, match="connexion vers une adresse interdite"):
            cli.get(f"http://localhost:{port}/a.pdf")
        assert hits == []  # avant : GET reçu par l'écoute locale, statut 200
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---------------------------------------------------------------------------
# Outils de poppler bornés : mémoire et taille de la sortie
# ---------------------------------------------------------------------------


def test_poppler_tools_are_bounded_in_memory_output_and_time(tmp_path):
    from brvm_alpha import pdf

    with pytest.raises(pdf.ExtractionRatee, match="sortie de plus de"):  # avant : sortie gardée entière en mémoire
        pdf.lancer_outil(["/bin/sh", "-c", "exec head -c 5000000 /dev/zero"], delai=30, sortie=1024 * 1024)
    code, out, err = pdf.lancer_outil([sys.executable, "-I", "-c", "x = bytearray(2 * 1024 ** 3)"], delai=60,
                                      memoire=256 * 1024 ** 2)
    assert code != 0 and b"MemoryError" in err  # avant : seule la limite du lanceur (3 Go) s'appliquait
    code, out, _ = pdf.lancer_outil(["/bin/sh", "-c", "printf texte"], delai=30)
    assert code == 0 and out == b"texte"
    assert pdf.DELAI_PDFTOTEXT_S == 60.0


def test_pdfplumber_fallback_runs_isolated_from_the_pdf_folder(tmp_path, monkeypatch):
    """Repli pdfplumber (hors mode embarqué) : « -I », dossier courant temporaire, environnement réduit ; un fichier
    pdfplumber.py posé à côté du PDF n'est pas importé."""
    from brvm_alpha import pdf

    seen = {}

    def fake_run(cmd, **kw):
        seen.update(cmd=cmd, **kw)

        class R:
            returncode, stdout, stderr = 0, b"texte", b""
        return R()

    monkeypatch.delenv(paths.ENV_EMBARQUE, raising=False)
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: False)
    monkeypatch.setattr(pdf, "_pdfplumber_present", lambda: True)
    monkeypatch.setattr(pdf.subprocess, "run", fake_run)
    monkeypatch.setenv("PYTHONPATH", "/ailleurs")
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4")
    assert pdf.par_pdfplumber(f) == "texte"
    assert seen["cmd"][1] == "-I" and seen["cwd"] != str(tmp_path) and "PYTHONPATH" not in seen["env"]


# ---------------------------------------------------------------------------
# Session polie : politesse par site, diagnostic d'adresse, état illisible, quota, live, PDF
# ---------------------------------------------------------------------------

_NOW = dt.datetime(2026, 11, 22, 3, 40, tzinfo=dt.timezone.utc)


class _R:
    def __init__(self, status, content=b"", headers=None, url=""):
        self.status_code, self.content, self.headers, self.url = status, content, headers or {}, url


class _VraieHorloge:
    """Horloge des délais (``clock``) qui avance avec les attentes (``sleep``), et instant (``now``) qui suit."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += max(0.0, float(s))

    def now(self):
        return _NOW + dt.timedelta(seconds=self.t - 1000.0)


def _polite(tmp_path, transport, **kw):
    from brvm_alpha.notes import research as rs

    h = _VraieHorloge()
    kw.setdefault("delay_s", 10.0)
    sess = rs.PoliteSession(transport=transport, clock=h, sleep=h.sleep, now=h.now, cache_dir=tmp_path / "cache",
                            log_path=tmp_path / "fetch_log.jsonl", **kw)
    return sess, h


def test_www_and_apex_hosts_share_one_politeness_slot(tmp_path):
    sent: list[tuple[float, str]] = []
    box = {}

    def transport(url, headers, timeout):
        sent.append((box["h"].t, url))
        if url.endswith("robots.txt"):
            return _R(404, b"", None, url)
        if url.startswith("https://www.brvm.org/"):
            return _R(301, b"", {"Location": "https://brvm.org/canonique.pdf"}, url)
        return _R(200, b"%PDF-1.4 x", {"Content-Type": "application/pdf"}, url)

    sess, h = _polite(tmp_path, transport)
    box["h"] = h
    for day in ("20190610", "20190611"):
        sess.get(f"https://www.brvm.org/sites/default/files/boc_{day}.pdf")
    times = [t for t, _u in sent]
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert len(sent) == 6 and min(gaps) >= 10.0 - 1e-9, sent  # avant : 0,015 s entre www et brvm.org


def test_a_forbidden_address_is_reported_as_policy_not_robots_and_not_counted(tmp_path):
    from brvm_alpha import net
    from brvm_alpha.notes import research as rs

    def transport(url, headers, timeout):
        raise net.AdresseInterdite(f"www.brvm.org se résout en adresse interdite (127.0.0.1) : {url}")

    sess, _h = _polite(tmp_path, transport)
    with pytest.raises(rs.PolicyRefused, match="adresse interdite"):  # avant : « robots.txt interdit »
        sess.get("https://www.brvm.org/sites/default/files/boc_20261123.pdf")
    assert sess.n_requests == 0 and sess.stop_kind == "politique"  # avant : requetes 1 (aucun envoi réel)


def test_unreadable_politeness_state_refuses_every_request_and_is_not_rewritten(tmp_path):
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    state = cache / rs.POLITENESS_STATE
    full = json.dumps({"hosts": {"www.brvm.org": {"blocked": {"ts": "2026-11-20T08:00:00+00:00", "status": 403,
                                                               "url": "https://www.brvm.org/x"}}}})
    state.write_text(full[:40], encoding="utf-8")  # tronqué : le blocage 403 n'est plus lisible
    calls = []
    sess, _h = _polite(tmp_path, lambda u, h, t: calls.append(u) or _R(200, b"", None, u))
    with pytest.raises(rs.EtatPolitesseIllisible):  # avant : code 0, 6 requêtes au site qui avait refusé
        sess.get("https://www.brvm.org/fr/cours-actions/0")
    assert calls == [] and state.read_text(encoding="utf-8") == full[:40]
    assert erreurs.code_retour(rs.EtatPolitesseIllisible("x")) == 8


def test_research_quota_fills_the_stop_reason_and_skips_document_reading(tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import research as rs

    class Res(list):
        report = rs.ResearchReport()

    res = Res()
    res.report.max_requests, res.report.n_requests, res.report.stop_kind = 25, 25, "quota"
    monkeypatch.setattr(rs, "run_research", lambda *a, **k: res)
    monkeypatch.setattr(cli, "_exiger_extracteur", lambda: None)
    called = []
    monkeypatch.setattr(cli, "run_enrich", lambda *a, **k: called.append(1) or (None, []))
    code, out, _ = run_cli(capsys, "notes", "research", "--pdf", "4", "--max-requetes", "25", "--racine",
                           str(tmp_path), "--format", "json")
    d = one_json(out)
    assert code == 0 and called == []  # avant : la lecture des documents partait (29 GET pour un quota de 25)
    assert d["recherche"]["raison_arret"] == "quota" and d["recherche"]["motif_arret"] == "quota de 25 requêtes atteint"


def test_live_refused_by_the_site_exits_5_not_1(capsys, monkeypatch):
    from brvm_alpha.notes import research as rs

    def blocked(self, url, **kw):
        raise rs.AccessBlocked("Le site www.brvm.org a refusé l'accès (HTTP 403)")

    monkeypatch.setattr(rs.PoliteSession, "get", blocked)
    code, out, _ = run_cli(capsys, "live", "--format", "json")
    d = one_json(out)
    assert code == 5 and d["erreur"] == "acces_refuse"  # avant : 1, « donnees_absentes »


def test_a_pdf_content_type_with_an_html_body_is_read_as_a_page(tmp_path, monkeypatch):
    from brvm_alpha.notes import research as rs

    html = b"<html><head><title>Communique</title></head><body><p>Sonatel : avis aux actionnaires.</p></body></html>"

    def transport(url, headers, timeout):
        if url.endswith("robots.txt"):
            return _R(404, b"", None, url)
        return _R(200, html, {"Content-Type": "application/pdf"}, url)

    sess, _h = _polite(tmp_path, transport)
    seen = []
    monkeypatch.setattr(rs, "extract_pdf_text", lambda p, *a, **k: seen.append(p) or {"text": "", "ocr_needed": True})
    from brvm_alpha.notes.store import NoteStore

    note = rs.fetch_url_note("https://www.brvm.org/c25/communique.pdf", store=NoteStore(tmp_path / "notes"),
                             session=sess, analyze=False, panel_dir=None)
    assert seen == []  # avant : voie PDF sur du HTML, note vide « ocr_requis »
    assert "avis aux actionnaires" in note.text and "ocr_requis" not in note.tags


def test_a_slow_pdf_is_set_aside_and_the_next_documents_are_read(tmp_path):
    from brvm_alpha import net
    from brvm_alpha.notes import research as rs

    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        if url.endswith("robots.txt"):
            return _R(404, b"", None, url)
        raise net.DelaiDepasse(f"{url} : délai total de 300 s dépassé (pdf).")

    sess, _h = _polite(tmp_path, transport)
    with pytest.raises(rs.DocumentTropLent):
        sess.get("https://www.brvm.org/sites/default/files/gros.pdf", nature="pdf")
    assert not sess.stopped and calls.count("https://www.brvm.org/sites/default/files/gros.pdf") == 1
    # une page lente, elle, reste une erreur passagère (nouvel essai, puis arrêt « serveur »)
    with pytest.raises(rs.ServerUnavailable):
        sess.get("https://www.brvm.org/fr/lente")


# ---------------------------------------------------------------------------
# Marqueurs hérités rouverts, journal des requêtes, cache HTTP
# ---------------------------------------------------------------------------


def test_update_reopen_removes_markers_of_a_period_explicitly(tmp_path, capsys, monkeypatch):
    boc = tmp_path / "boc_text"
    boc.mkdir()
    for day in ("20210507", "20210510", "20210511"):
        (boc / f"boc_{day}.missing").write_bytes(b"")  # anciens marqueurs vides : définitifs
    base = ["update", "--boc-dir", str(boc), "--panel-dir", str(tmp_path / "panel"), "--from", "2021-05-07",
            "--jusqu-au", "2021-05-10", "--sans-panel", "--format", "json"]
    code, out, _ = run_cli(capsys, *base, "--rouvrir", "2021-05-07..2021-05-10", "--simulation")
    d = one_json(out)
    assert code == 0 and d["marqueurs_rouverts"] == ["2021-05-07", "2021-05-10"]
    assert d["jours_a_chercher"] == 2  # jours rouverts comptés (tests/test_retouches_embarque.py, P5)
    assert len(list(boc.glob("*.missing"))) == 3  # simulation : rien n'est retiré
    calls = []
    monkeypatch.setattr(cli, "_exiger_extracteur", lambda: None)
    monkeypatch.setattr(cli, "brvm_fetcher", lambda **k: (lambda url: calls.append(url) or (404, b"")))
    code, out, _ = run_cli(capsys, *base, "--rouvrir", "2021-05-07..2021-05-10")
    d = one_json(out)
    assert code == 0 and d["marqueurs_rouverts"] == ["2021-05-07", "2021-05-10"]
    assert {u.split("boc_")[1][:8] for u in calls} == {"20210507", "20210510"}  # cherchés de nouveau
    m = bd.lire_marqueur(boc / "boc_20210507.missing")
    assert m.statut == "introuvable" and m.tentatives == 1 and m.definitif is False
    assert (boc / "boc_20210511.missing").read_bytes() == b""  # hors période : intact
    code, out, _ = run_cli(capsys, "update", "--rouvrir", "2021-05-10..2021-05-07", "--format", "json")
    assert code == 2


def test_fetch_log_rotates_and_duplicate_pdf_bodies_leave_the_http_cache(tmp_path):
    import gzip

    from brvm_alpha.notes import research as rs

    log = tmp_path / "fetch_log.jsonl"
    log.write_text("x" * 100, encoding="utf-8")
    assert rs.tourner_journal(log, max_octets=50) is True
    assert not log.exists() and (tmp_path / "fetch_log.1.jsonl").stat().st_size == 100
    assert rs.tourner_journal(log, max_octets=50) is False
    cache = tmp_path / "cache"
    url_pdf, url_page = "https://www.brvm.org/a.pdf", "https://www.brvm.org/page"
    for url, body in ((url_pdf, b"%PDF-1.4 contenu"), (url_page, b"<html>page</html>")):
        h = rs.url_hash(url)
        (cache / "http" / h[:2]).mkdir(parents=True, exist_ok=True)
        (cache / "http" / h[:2] / f"{h}.json").write_text(json.dumps({"url": url}), encoding="utf-8")
        (cache / "http" / h[:2] / f"{h}.body.gz").write_bytes(gzip.compress(body))
    (cache / "docs").mkdir()
    (cache / "docs" / f"{rs.url_hash(url_pdf)}.pdf").write_bytes(b"%PDF-1.4 contenu")
    assert rs.purger_pdf_du_cache_http(cache) == 1 and rs.purger_pdf_du_cache_http(cache) == 0  # idempotent
    h = rs.url_hash(url_pdf)
    assert not (cache / "http" / h[:2] / f"{h}.body.gz").exists() and (cache / "http" / h[:2] / f"{h}.json").exists()
    assert len(list((cache / "http").glob("*/*.body.gz"))) == 1  # la page reste


def test_read_only_or_full_data_folder_is_a_configuration_error(tmp_path, monkeypatch):
    import errno

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "donnees")
    monkeypatch.setattr(paths, "REPORTS_DIR", tmp_path / "rapports")
    for err in (errno.EROFS, errno.EACCES, errno.ENOSPC):
        exc = OSError(err, os.strerror(err), str(tmp_path / "donnees" / "notes" / "notes.jsonl"))
        assert erreurs.code_retour(exc) == 8 and "inscriptibles" in erreurs.message_erreur(exc)  # avant : 7, trace
    assert erreurs.code_retour(OSError(errno.EROFS, "ro", "/ailleurs/x")) == 7  # hors des dossiers configurés
    (tmp_path / "ro").mkdir()
    assert etat.inscriptible(tmp_path / "ro") is True and etat.inscriptible(tmp_path / "ro" / "a" / "b") is True


def test_update_refuses_to_send_anything_with_an_unreadable_politeness_state(tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import research as rs

    notes = tmp_path / "notes"
    (notes / "cache").mkdir(parents=True)
    (notes / "cache" / rs.POLITENESS_STATE).write_text('{"hosts": {"www.brvm.org": {"blocked": {"ts": "2026-11',
                                                         encoding="utf-8")
    monkeypatch.setattr(rs, "DEFAULT_NOTES_DIR", notes)
    monkeypatch.setattr(cli, "_exiger_extracteur", lambda: None)

    def no_network(*a, **k):
        raise AssertionError("aucune requête ne doit partir")

    monkeypatch.setattr(rs, "_requests_transport", no_network)
    code, out, _ = run_cli(capsys, "update", "--from", "2026-11-02", "--jusqu-au", "2026-11-02", "--boc-dir",
                           str(tmp_path / "boc"), "--panel-dir", str(tmp_path / "panel"), "--sans-panel", "--format",
                           "json")
    d = one_json(out)
    assert code == 8 and d["erreur"] == "configuration" and "politesse illisible" in d["message"]  # avant : 0
    st = etat.site_state(notes)
    assert "etat_illisible" in st
