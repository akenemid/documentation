"""Ligne de commande pour le déploiement : commande ``etat``, options de ``serve``, données déplaçables.

Hors ligne : dossiers temporaires, extraits de BOC des fixtures, aucun calcul sur S1. Les variables
``BRVM_ALPHA_DONNEES`` et ``BRVM_ALPHA_RAPPORTS`` sont lues au démarrage du programme : elles sont
essayées dans un **sous-processus**, avec une garde qui arrête tout avant la moindre écriture si le
dossier de données n'est pas le dossier temporaire (``data/notes`` du dépôt n'est jamais touché).
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from brvm_alpha import cli, etat, paths

ROOT = Path(__file__).resolve().parents[1]
BOC_FIX = ROOT / "tests" / "fixtures" / "notes" / "boc"


@pytest.fixture()
def no_network(monkeypatch):
    """Toute tentative de requête fait échouer le test."""
    from brvm_alpha.notes import research as rs

    def forbidden(*a, **k):
        raise AssertionError("aucune requête réseau : « etat » ne lit que le disque")

    monkeypatch.setattr(rs, "_requests_transport", forbidden)
    monkeypatch.setattr(cli, "brvm_fetcher", forbidden)
    import socket

    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    """Dossier de données minuscule : sept BOC, un marqueur « sans bulletin », le panel correspondant."""
    from brvm_alpha.data import store

    base = tmp_path_factory.mktemp("donnees_minuscules")
    boc = base / "boc_text"
    boc.mkdir()
    for f in BOC_FIX.glob("boc_*.txt.gz"):
        shutil.copy(f, boc / f.name)
    (boc / "boc_20261030.missing").touch()  # jour marqué sans bulletin
    (boc / "notes_diverses.txt").write_text("ignoré", encoding="utf-8")
    store.build_panel(boc, base / "panel", workers=1)
    return base


# ---------------------------------------------------------------------------
# Commande « etat »
# ---------------------------------------------------------------------------


def test_etat_exits_zero_when_nothing_is_ready_and_creates_nothing(tmp_path, capsys, no_network):
    argv = ["etat", "--panel-dir", str(tmp_path / "panel"), "--boc-dir", str(tmp_path / "boc"),
            "--racine", str(tmp_path / "notes")]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "Prêt : non (panel absent ou vide)." in out and "python -m brvm_alpha update" in out
    assert "Panel : aucune séance." in out and "(dernier : aucun)" in out  # accords (relecture du 22/11/2026)
    assert "Notes : aucun journal pour l'instant." in out and "Aucune requête n'a été envoyée." in out
    assert out.rstrip().endswith(cli.BANNER)
    assert cli.main(argv + ["--format", "json"]) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["pret"] is False and state["bandeau"] == cli.BANNER
    assert state["raison"] == "panel absent ou vide" and state["historique_complet"] is False
    assert state["panel"] == {"dossier": str(tmp_path / "panel"), "derniere_seance": None, "seances_presentes": 0,
                              "seances_manquantes": 0, "seances_en_retard": 0, "retard": None,
                              "premiere_seance": None, "lisible": False, "erreur": None}
    assert state["bulletins"]["en_cache"] == 0 and state["bulletins"]["dernier"] is None
    assert state["notes"] == {"dossier": str(tmp_path / "notes"), "journal_present": False, "au_journal": 0,
                              "en_vigueur": 0}
    assert list(tmp_path.iterdir()) == []  # lecture seule : aucun dossier n'est créé


def test_etat_on_a_tiny_installation(tiny, tmp_path, capsys, no_network):
    notes = tmp_path / "notes"
    assert cli.main(["notes", "add", "--racine", str(notes), "--cible", "SNTS", "--titre", "Sonatel : avis",
                     "--avis", "haussier", "--conviction", "3"]) == 0
    capsys.readouterr()
    argv = ["etat", "--panel-dir", str(tiny / "panel"), "--boc-dir", str(tiny / "boc_text"), "--racine", str(notes)]
    assert cli.main(argv + ["--format", "json"]) == 0
    state = json.loads(capsys.readouterr().out)
    # Sept bulletins seulement : panel lisible, mais historique incomplet depuis 2017, donc pas « prêt ».
    assert state["pret"] is False and state["historique_complet"] is False
    assert state["raison"].startswith("historique incomplet : ") and "jour(s) à télécharger" in state["raison"]
    assert state["panel"]["lisible"] is True and state["panel"]["premiere_seance"] == "2025-12-31"
    assert state["panel"]["derniere_seance"] == "2026-10-29" and state["panel"]["seances_presentes"] == 7
    assert state["panel"]["seances_manquantes"] > 0  # numéros de BOC absents entre les sept extraits
    assert state["bulletins"]["jours_manquants"] > 2000
    # « update » comble depuis le 02/01/2017 sans --from : les deux décomptes sont égaux (relecture du 22/11/2026).
    assert state["bulletins"]["jours_a_telecharger"] == state["bulletins"]["jours_a_telecharger_depuis_2017"] > 2000
    assert state["bulletins"] | {"jours_a_telecharger": 0, "jours_a_telecharger_depuis_2017": 0,
                                 "jours_manquants": 0} == {
        "dossier": str(tiny / "boc_text"), "en_cache": 7, "sans_bulletin": 1, "dernier": "2026-10-29",
        "jours_a_telecharger": 0, "premier_jour_cherche": "2017-01-02", "jours_a_telecharger_depuis_2017": 0,
        "premier": "2025-12-31", "sans_bulletin_definitif": 1, "a_reessayer": 0, "jours_manquants": 0,
        "historique_complet": False}
    assert state["notes"]["au_journal"] == 1 and state["notes"]["en_vigueur"] == 1
    assert state["notes"]["journal_present"] is True
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "Prêt : non (historique incomplet : " in out and "update --from 2017-01-02" in out
    assert "Panel : dernière séance le 29/10/2026 ; 7 séance(s) présente(s)" in out
    assert "Bulletins : 7 en cache (dernier : 29/10/2026), 1 jour(s) marqué(s) sans bulletin." in out
    assert "Notes : 1 au journal, 1 en vigueur." in out and out.rstrip().endswith(cli.BANNER)


def test_etat_counts_days_like_update_simulation_without_any_request(tiny, capsys, no_network):
    boc = tiny / "boc_text"
    assert cli.main(["update", "--simulation", "--boc-dir", str(boc)]) == 0
    out = capsys.readouterr().out
    n_default = int(re.search(r": (\d+) jour\(s\) ouvré\(s\) à chercher", out).group(1))
    assert cli.main(["update", "--simulation", "--boc-dir", str(boc), "--from", "2017-01-02"]) == 0
    n_history = int(re.search(r": (\d+) jour\(s\) ouvré\(s\) à chercher", capsys.readouterr().out).group(1))
    b = etat.bulletins_state(boc, dt.date.today())
    assert b["jours_a_telecharger"] == n_default and b["jours_a_telecharger_depuis_2017"] == n_history
    # Défaut de « update » (relecture du 22/11/2026) : tout l'historique depuis le 02/01/2017, donc les trous
    # laissés par un lancement arrêté sont repris sans --from ; même calcul avec --from 2017-01-02.
    assert n_history == n_default > 2000
    start, end, days = cli.update_window(boc, today=dt.date(2026, 11, 6))
    assert (start, end) == (cli.HISTORY_START, dt.date(2026, 11, 6))
    assert [d.isoformat() for d in sorted(days)][-5:] == ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05",
                                                          "2026-11-06"]
    assert dt.date(2026, 10, 29) not in days and dt.date(2026, 10, 30) not in days  # bulletin et marqueur présents
    assert days == sorted(days, reverse=True)  # du plus récent au plus ancien
    start, end, days = cli.update_window(boc, start=dt.date(2026, 10, 31), today=dt.date(2026, 11, 6))
    assert [d.isoformat() for d in sorted(days)] == ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]
    assert cli.update_window(boc, start=dt.date(2026, 10, 28), end=dt.date(2026, 12, 31),
                             today=dt.date(2026, 10, 30))[1:] == (dt.date(2026, 10, 30), [dt.date(2026, 10, 28)])
    assert cli.update_window(tiny / "absent", today=dt.date(2017, 1, 3)) == (
        cli.HISTORY_START, dt.date(2017, 1, 3), [dt.date(2017, 1, 3), dt.date(2017, 1, 2)])


def test_etat_reports_panel_delay_with_the_existing_function(tiny):
    from brvm_alpha.portfolio import recommend as rec

    on_time = etat.panel_state(tiny / "panel", pd.Timestamp("2026-10-30 10:00", tz="UTC"))
    assert on_time["seances_en_retard"] == 0 and on_time["retard"] is None
    now = pd.Timestamp("2026-11-04 18:00", tz="UTC")  # mercredi soir : 30/10, 02/11, 03/11 et 04/11 attendues
    late = etat.panel_state(tiny / "panel", now)
    assert late["seances_en_retard"] == 4
    assert late["retard"] == rec.stale_panel_message(pd.Timestamp("2026-10-29"), now, orders=False)
    assert late["retard"].startswith("PANEL EN RETARD de 4 séance(s)")
    state = etat.collect_state(panel_dir=tiny / "panel", boc_dir=tiny / "boc_text", notes_root=tiny / "notes", now=now)
    assert "Retard du panel : PANEL EN RETARD de 4 séance(s)" in etat.format_text(state)
    assert state["releve_le"] == "2026-11-04T18:00:00Z" and state["pret"] is False  # historique incomplet


def test_etat_reports_a_blocked_site_last_report_and_data_size(tmp_path):
    from brvm_alpha.notes import research as rs

    notes, reports, data = tmp_path / "notes", tmp_path / "rapports", tmp_path / "donnees"
    (notes / "cache").mkdir(parents=True)
    (notes / "cache" / rs.POLITENESS_STATE).write_text(json.dumps({"hosts": {"www.brvm.org": {
        "blocked": {"ts": "2026-11-20T08:00:00+00:00", "status": 403, "url": "https://www.brvm.org/x"}}}}), "utf-8")
    reports.mkdir()
    for name, age in (("rapport_2026-11-19.html", 200), ("rapport_2026-11-20.html", 100), ("autre.html", 0),
                      ("rapport_2026-11-21.html.tmp", 0)):
        f = reports / name
        f.write_text("x", encoding="utf-8")
        os.utime(f, (1_800_000_000 - age, 1_800_000_000 - age))
    (data / "a" / "b").mkdir(parents=True)
    (data / "a" / "un.bin").write_bytes(b"x" * 1500)
    (data / "a" / "b" / "deux.bin").write_bytes(b"x" * 3 * 1024 * 1024)
    os.symlink(data / "a" / "b" / "deux.bin", data / "lien")  # lien symbolique : non compté
    state = etat.collect_state(panel_dir=tmp_path / "p", boc_dir=tmp_path / "b", notes_root=notes, reports_dir=reports,
                               data_dir=data)
    assert state["site"] == {"bloque": True, "depuis": "2026-11-20T08:00:00+00:00", "code_http": 403}
    assert state["rapport"] == {"dossier": str(reports), "nom": "rapport_2026-11-20.html", "date": "2027-01-15T07:58:20Z"}
    assert state["donnees"] == {"dossier": str(data), "taille_octets": 1500 + 3 * 1024 * 1024, "taille": "3 Mo"}
    text = etat.format_text(state)
    assert "Site www.brvm.org : bloqué depuis le 2026-11-20T08:00:00+00:00 (HTTP 403)" in text
    assert "Dernier rapport écrit : rapport_2026-11-20.html, le 15/01/2027 07:58 UTC." in text
    assert etat.human_size(0) == "0 octet" and etat.human_size(900) == "900 octets"
    assert etat.human_size(5 * 1024 ** 3 // 2) == "2,5 Go" and etat.dir_size(tmp_path / "absent") == 0


def test_code_version_reads_git_without_running_a_command(tmp_path, monkeypatch):
    sha = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("aucune commande")))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("aucune commande")))
    code = tmp_path / "depot" / "brvm-alpha"
    git = tmp_path / "depot" / ".git"
    (git / "refs" / "heads" / "travail").mkdir(parents=True)
    code.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/travail/branche\n", encoding="utf-8")
    assert etat.code_version(code, {}) == "inconnue"  # référence absente
    (git / "refs" / "heads" / "travail" / "branche").write_text(sha + "\n", encoding="utf-8")
    assert etat.code_version(code, {}) == "0123456"  # .git du dossier parent, comme dans ce dépôt
    (git / "refs" / "heads" / "travail" / "branche").unlink()
    (git / "packed-refs").write_text(f"# pack-refs\n{'f' * 40} refs/heads/autre\n{sha[::-1]} refs/heads/travail/branche\n", "utf-8")
    assert etat.code_version(code, {}) == sha[::-1][:7]  # références compactées
    (git / "HEAD").write_text("89abcdef" * 5 + "\n", encoding="utf-8")
    assert etat.code_version(code, {}) == "89abcde"  # HEAD détaché
    (git / "HEAD").write_text("ref: refs/heads/../../etc/passwd\n", encoding="utf-8")
    assert etat.code_version(code, {}) == "inconnue"
    # sans dossier .git (image Docker) : variable de repli, contrôlée
    alone = tmp_path / "seul"
    alone.mkdir()
    monkeypatch.setattr(etat, "_git_dir", lambda start: None)
    assert etat.code_version(alone, {}) == "inconnue"
    assert etat.code_version(alone, {"BRVM_ALPHA_VERSION": "152f3d5"}) == "152f3d5"
    assert etat.code_version(alone, {"BRVM_ALPHA_VERSION": "<script>"}) == "inconnue"


def test_etat_version_of_this_checkout_is_a_short_commit_or_unknown():
    assert re.fullmatch(r"[0-9a-f]{7}|inconnue", etat.code_version(environ={}))


def test_etat_is_listed_in_help_with_the_banner(capsys):
    with pytest.raises(SystemExit):
        cli.main(["etat", "-h"])
    out = capsys.readouterr().out
    assert "--format" in out and "--panel-dir" in out and "--racine" in out and "Code de sortie 0" in out
    assert cli.BANNER in out
    with pytest.raises(SystemExit):
        cli.main(["-h"])
    assert "etat" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# « serve » : préfixe, origines du relais, cadre
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_serve(monkeypatch):
    """Remplace le serveur : relève les arguments de ``make_server`` sans ouvrir de port."""
    from brvm_alpha.ui import server

    calls: list[dict] = []

    class FakeSrv:
        server_address = ("127.0.0.1", 8765)

        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown_jobs(self):
            pass

        def server_close(self):
            pass

    def fake_make(host, port, **kw):
        kw.pop("services", None)
        calls.append({"host": host, "port": port, **kw})
        return FakeSrv()

    monkeypatch.setattr(server, "make_server", fake_make)
    monkeypatch.delenv(cli.ENV_PREFIX, raising=False)
    monkeypatch.delenv(cli.ENV_RELAY_ORIGINS, raising=False)
    return calls


def test_serve_without_new_options_calls_the_server_exactly_as_before(fake_serve, capsys):
    assert cli.main(["serve", "--port", "0"]) == 0
    assert fake_serve == [{"host": "127.0.0.1", "port": 0, "allow_remote": False}]
    out = capsys.readouterr().out
    assert out.splitlines()[0] == (f"Interface BRVM Alpha : http://127.0.0.1:8765/  (Ctrl+C pour arrêter). {cli.BANNER}")
    assert "Préfixe" not in out and "relais" not in out and "cadre" not in out


def test_serve_passes_prefix_relay_origins_and_frame_option(fake_serve, capsys):
    assert cli.main(["serve", "--prefixe", "/rz_brvm_alpha/ui", "--origine-relais", "https://ERP.exemple.com/",
                     "--origine-relais", "http://preprod.local:8069", "--origine-relais", "https://erp.exemple.com:443",
                     "--cadre-meme-origine"]) == 0
    assert fake_serve[-1] == {"host": "127.0.0.1", "port": 8765, "allow_remote": False, "prefix": "/rz_brvm_alpha/ui",
                              "relay_origins": ("https://erp.exemple.com", "http://preprod.local:8069"),
                              "frame_same_origin": True}
    out = capsys.readouterr().out
    assert "http://127.0.0.1:8765/rz_brvm_alpha/ui/" in out and "tout autre chemin répond 404" in out
    assert "https://erp.exemple.com, http://preprod.local:8069" in out and "--cadre-meme-origine" in out
    assert cli.BANNER in out


def test_serve_reads_environment_and_the_option_wins(fake_serve, monkeypatch):
    monkeypatch.setenv(cli.ENV_PREFIX, "/depuis/env")
    monkeypatch.setenv(cli.ENV_RELAY_ORIGINS, "https://a.exemple.com, https://b.exemple.com")
    assert cli.main(["serve"]) == 0
    assert fake_serve[-1]["prefix"] == "/depuis/env"
    assert fake_serve[-1]["relay_origins"] == ("https://a.exemple.com", "https://b.exemple.com")
    assert "frame_same_origin" not in fake_serve[-1]
    assert cli.main(["serve", "--prefixe", "/option", "--origine-relais", "https://c.exemple.com"]) == 0
    assert fake_serve[-1]["prefix"] == "/option" and fake_serve[-1]["relay_origins"] == ("https://c.exemple.com",)
    assert cli.main(["serve", "--prefixe", ""]) == 0  # option vide : aucun préfixe, malgré la variable
    assert "prefix" not in fake_serve[-1]


@pytest.mark.parametrize("argv, env, message", [
    (["--prefixe", "sans-barre"], {}, "préfixe d'adresse invalide"),
    (["--prefixe", "/a/../b"], {}, "préfixe d'adresse invalide"),
    (["--origine-relais", "erp.exemple.com"], {}, "origine invalide"),
    (["--origine-relais", "https://erp.exemple.com/chemin"], {}, "origine invalide"),
    ([], {"BRVM_ALPHA_PREFIXE": "/fini/"}, "préfixe d'adresse invalide"),
    ([], {"BRVM_ALPHA_ORIGINES_RELAIS": "https://ok.exemple.com *"}, "origine invalide"),
])
def test_serve_refuses_malformed_relay_settings_with_exit_code_2(fake_serve, monkeypatch, capsys, argv, env, message):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert cli.main(["serve", *argv]) == 2
    assert message in capsys.readouterr().err and fake_serve == []


def test_serve_help_documents_the_relay_options(capsys):
    with pytest.raises(SystemExit):
        cli.main(["serve", "-h"])
    out = capsys.readouterr().out
    for word in ("--prefixe", "--origine-relais", "--cadre-meme-origine", "BRVM_ALPHA_PREFIXE",
                 "BRVM_ALPHA_ORIGINES_RELAIS", "404"):
        assert word in out, word


# ---------------------------------------------------------------------------
# Données déplaçables : BRVM_ALPHA_DONNEES et BRVM_ALPHA_RAPPORTS
# ---------------------------------------------------------------------------


def test_default_folders_are_unchanged_without_the_variables():
    """Dans les tests, aucune des deux variables n'est posée : tout reste dans l'arbre du code."""
    assert not os.environ.get(paths.ENV_DATA) and not os.environ.get(paths.ENV_REPORTS)
    assert (paths.DATA_DIR, paths.REPORTS_DIR) == (ROOT / "data", ROOT / "reports") and not paths.relocated()
    assert cli.DEFAULT_PANEL_DIR == ROOT / "data" / "panel" and cli.DEFAULT_BOC_DIR == ROOT / "data" / "boc_text"
    assert cli.DEFAULT_REPORTS_DIR == ROOT / "reports"
    assert paths.VALIDATION_DIR == ROOT / "reports" / "validation_S1"


def test_resolve_dirs_and_repo_path(tmp_path):
    env = {paths.ENV_DATA: str(tmp_path / "d"), paths.ENV_REPORTS: f"  {tmp_path / 'r'}  "}
    assert paths.resolve_dirs(env) == (tmp_path / "d", tmp_path / "r")
    assert paths.resolve_dirs({paths.ENV_DATA: "", paths.ENV_REPORTS: "   "}) == (ROOT / "data", ROOT / "reports")
    assert paths.resolve_dirs({paths.ENV_DATA: "relatif/donnees"})[0] == Path.cwd() / "relatif" / "donnees"
    assert paths.env_dir("ABSENTE", {}) is None
    # chemins relatifs au dépôt : « data/… » suit le dossier de données, la validation reste au dépôt
    assert paths.repo_path("data/panel") == paths.PANEL_DIR and paths.repo_path("data/notes") == paths.NOTES_DIR
    assert paths.repo_path("reports/validation_S1") == ROOT / "reports" / "validation_S1"
    assert paths.repo_path("configs/strategy_v1.yaml") == ROOT / "configs" / "strategy_v1.yaml"
    assert paths.repo_path(tmp_path / "absolu") == tmp_path / "absolu"


#: Programme lancé dans un sous-processus : il relève les dossiers par défaut de chaque module.
PROBE = r"""
import json
from brvm_alpha import cli, paths
from brvm_alpha.notes import model, research as rs
from brvm_alpha.notes.store import NoteStore
from brvm_alpha.portfolio import recommend as rec
from brvm_alpha.report import html as H
from brvm_alpha.strategy import alpha
from brvm_alpha.ui import server as S
from brvm_alpha.validation import runner
s = S.Services()
print(json.dumps({k: str(v) for k, v in {
    "donnees": paths.DATA_DIR, "rapports": paths.REPORTS_DIR,
    "cli_panel": cli.DEFAULT_PANEL_DIR, "cli_boc": cli.DEFAULT_BOC_DIR, "cli_rapports": cli.DEFAULT_REPORTS_DIR,
    "notes_recherche": rs.DEFAULT_NOTES_DIR, "boc_recherche": rs.DEFAULT_BOC_DIR, "panel_recherche": rs.DEFAULT_PANEL_DIR,
    "journal": NoteStore().root, "panel_modele": model.default_panel_dir(), "panel_strategie": alpha.DEFAULT_PANEL_DIR,
    "panel_ordre": rec.DEFAULT_PANEL_DIR, "rapport_panel": H._resolve("data/panel"), "rapport_notes": H._resolve("data/notes"),
    "ui_panel": s.panel_dir, "ui_boc": s.boc_dir, "ui_rapports": s.reports_dir, "ui_journal": s.notes_store().root,
    "ui_cible_rapport": s.report_target("2026-11-20"),
    "validation_ui": s.validation_dir, "diagnostic_ui": s.diagnostic_dir, "validation_rapport": H._resolve("reports/validation_S1"),
    "validation_ordre": rec._resolve(None, rec.DEFAULT_VALIDATION_DIR), "registre": rec.DEFAULT_REGISTRY_PATH,
    "validation_sorties": runner.REPORTS_DIR,
}.items()}))
"""


def run_python(args, tmp_path, **env):
    full = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONPATH": str(ROOT),
            "BRVM_ALPHA_SIMULATED_CLOCK": "1", **env}
    return subprocess.run([sys.executable, *args], env=full, cwd=tmp_path, capture_output=True, text=True, timeout=300)


def test_environment_variables_move_every_default_folder_but_not_the_validation(tmp_path):
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    r = run_python(["-c", PROBE], tmp_path, BRVM_ALPHA_DONNEES=str(data), BRVM_ALPHA_RAPPORTS=str(reports))
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["donnees"] == str(data) and got["rapports"] == str(reports)
    for key in ("cli_panel", "panel_recherche", "panel_modele", "panel_strategie", "panel_ordre", "rapport_panel", "ui_panel"):
        assert got[key] == str(data / "panel"), key
    for key in ("cli_boc", "boc_recherche", "ui_boc"):
        assert got[key] == str(data / "boc_text"), key
    for key in ("notes_recherche", "journal", "rapport_notes", "ui_journal"):
        assert got[key] == str(data / "notes"), key
    assert got["cli_rapports"] == got["ui_rapports"] == str(reports)
    assert got["ui_cible_rapport"] == str(reports / "rapport_2026-11-20.html")
    # les résultats de la validation et le registre restent lus dans le dépôt
    for key in ("validation_ui", "validation_rapport", "validation_ordre"):
        assert got[key] == str(ROOT / "reports" / "validation_S1"), key
    assert got["diagnostic_ui"] == str(ROOT / "reports" / "diagnostic_S0")
    assert got["registre"] == str(ROOT / "reports" / "trials.parquet")
    assert got["validation_sorties"] == str(ROOT / "reports")
    assert not data.exists() and not reports.exists()  # relever les dossiers ne crée rien
    # sans les variables : exactement les dossiers du dépôt
    r = run_python(["-c", PROBE], tmp_path)
    plain = json.loads(r.stdout)
    assert plain["cli_panel"] == str(ROOT / "data" / "panel") and plain["journal"] == str(ROOT / "data" / "notes")
    assert plain["cli_rapports"] == str(ROOT / "reports")


#: Programme lancé dans un sous-processus : commandes qui ÉCRIVENT, après une garde sur le dossier de données.
WRITER = r"""
import json, sys
from brvm_alpha import cli, paths
from brvm_alpha.notes.store import NoteStore
data, reports = sys.argv[1], sys.argv[2]
# Garde : si les variables n'étaient pas prises en compte, on s'arrête AVANT toute écriture.
assert str(paths.DATA_DIR) == data and str(paths.REPORTS_DIR) == reports, "garde : dossiers inattendus"
assert str(NoteStore().root) == data + "/notes" and str(cli.DEFAULT_PANEL_DIR) == data + "/panel", "garde"
codes = {
    "panel": cli.main(["panel", "--workers", "1"]),
    "notes add": cli.main(["notes", "add", "--cible", "SNTS", "--titre", "Sonatel : essai", "--avis", "haussier"]),
    "notes list": cli.main(["notes", "list"]),
    "notes export": cli.main(["notes", "export"]),
    "notes research": cli.main(["notes", "research", "--hors-ligne", "--pdf", "0"]),
    "indices": cli.main(["indices", "--format", "json"]),
    "universe": cli.main(["universe"]),
    "update --simulation": cli.main(["update", "--simulation"]),
}
print("CODES=" + json.dumps(codes))
cli.main(["etat", "--format", "json"])
"""


def test_commands_read_and_write_in_the_relocated_folders(tmp_path):
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    (data / "boc_text").mkdir(parents=True)
    for f in BOC_FIX.glob("boc_*.txt.gz"):
        shutil.copy(f, data / "boc_text" / f.name)
    real_journal = ROOT / "data" / "notes" / "notes.jsonl"
    before = real_journal.stat() if real_journal.exists() else None
    r = run_python(["-c", WRITER, str(data), str(reports)], tmp_path, BRVM_ALPHA_DONNEES=str(data),
                   BRVM_ALPHA_RAPPORTS=str(reports), HTTPS_PROXY="http://127.0.0.1:9", HTTP_PROXY="http://127.0.0.1:9")
    assert r.returncode == 0, r.stderr[-2000:]
    codes = json.loads(re.search(r"^CODES=(.*)$", r.stdout, re.M).group(1))
    assert codes == {k: 0 for k in codes}, (codes, r.stderr[-2000:])
    # panel, journal des notes et son cache, export : tout est dans les dossiers déplacés
    assert (data / "panel" / "equities.parquet").is_file() and (data / "panel" / "sessions.parquet").is_file()
    assert (data / "notes" / "notes.jsonl").is_file()
    assert [p.name for p in reports.iterdir()] == [f"notes_{dt.date.today():%Y%m%d}.md"]
    assert f"Reconstruction du panel {data / 'panel'} depuis {data / 'boc_text'}" in r.stdout
    assert f"dossier {data / 'boc_text'}" in r.stdout  # update --simulation
    state = json.loads(r.stdout[r.stdout.rindex('{\n "ok": true'):])  # objet JSON : « ok » en tête
    assert state["pret"] is False and state["panel"]["dossier"] == str(data / "panel")  # sept BOC : incomplet
    assert state["panel"]["lisible"] is True and state["raison"].startswith("historique incomplet")
    assert state["bulletins"]["dossier"] == str(data / "boc_text") and state["bulletins"]["en_cache"] == 7
    assert state["notes"]["dossier"] == str(data / "notes") and state["notes"]["au_journal"] >= 1
    assert state["rapport"]["dossier"] == str(reports) and state["donnees"]["dossier"] == str(data)
    assert state["donnees"]["taille_octets"] > 100_000
    # le journal réel du dépôt n'a pas bougé
    after = real_journal.stat() if real_journal.exists() else None
    assert (before is None) == (after is None)
    if before is not None:
        assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)


def test_command_line_options_win_over_the_environment_variables(tmp_path):
    env_data, env_reports = tmp_path / "env_donnees", tmp_path / "env_rapports"
    other = tmp_path / "option"
    argv = ["-m", "brvm_alpha", "etat", "--format", "json", "--panel-dir", str(other / "panel"),
            "--boc-dir", str(other / "boc"), "--racine", str(other / "notes")]
    r = run_python(argv, tmp_path, BRVM_ALPHA_DONNEES=str(env_data), BRVM_ALPHA_RAPPORTS=str(env_reports))
    assert r.returncode == 0, r.stderr
    state = json.loads(r.stdout)
    assert state["panel"]["dossier"] == str(other / "panel") and state["bulletins"]["dossier"] == str(other / "boc")
    assert state["notes"]["dossier"] == str(other / "notes")
    assert state["donnees"]["dossier"] == str(env_data) and state["rapport"]["dossier"] == str(env_reports)
    assert state["pret"] is False and not any(tmp_path.iterdir())  # code 0 même si rien n'est prêt ; rien n'est créé
