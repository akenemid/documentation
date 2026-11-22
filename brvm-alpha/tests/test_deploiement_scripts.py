"""Scripts de déploiement (``deploiement/*.sh``), **hors ligne**.

Trois niveaux :

- syntaxe (``sh -n``) et règles de forme (shell POSIX, aucun chemin absolu en dur, aucun secret) ;
- logique de la boucle, du verrou et du journal avec une **doublure** de l'interpréteur (un petit
  script qui répond à ``etat``, ``update``, ``panel``… sans rien calculer ni rien envoyer) ;
- mode ``--simulation`` avec le vrai moteur sur un dossier de données minuscule et temporaire.

Aucune requête réseau, aucun fichier écrit dans ``data/`` ni ``reports/`` du dépôt.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploiement"
SCRIPTS = ("commun.sh", "collecte-initiale.sh", "quotidien.sh", "service.sh")
BOC_FIX = ROOT / "tests" / "fixtures" / "notes" / "boc"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="shell POSIX absent")

#: Doublure de l'interpréteur du moteur. Elle tient son état dans des fichiers du dossier ``STUB`` :
#: ``restant`` (jours à chercher), ``pas`` (jours trouvés par lancement de « update »), ``bloque``,
#: ``cache``, ``pret``, ``code_update`` ; elle note chaque appel dans ``appels``.
STUB = r"""#!/bin/sh
case "$1" in -c) exec "$STUB_PYTHON" "$@" ;; esac
shift 2
printf '%s\n' "$*" >> "$STUB/appels"
lire() { cat "$STUB/$1"; }
case "$1" in
    etat)
        printf '{"pret": %s, "bulletins": {"jours_a_telecharger": 0, "jours_a_telecharger_depuis_2017": %s, "en_cache": %s}, "site": {"bloque": %s}}\n' \
            "$(lire pret)" "$(lire restant)" "$(lire cache)" "$(lire bloque)" ;;
    update)
        case " $* " in *" --simulation "*) echo "Simulation : aucune requête envoyée."; exit 0 ;; esac
        n=$(( $(lire lancements) + 1 )); echo "$n" > "$STUB/lancements"
        if [ -f "$STUB/refus_au_lancement" ] && [ "$n" -ge "$(lire refus_au_lancement)" ]; then
            echo true > "$STUB/bloque"; echo "arrêt : HTTP 403" >&2; exit 1
        fi
        r=$(( $(lire restant) - $(lire pas) )); if [ "$r" -lt "$(lire plancher)" ]; then r=$(lire plancher); fi
        echo "$r" > "$STUB/restant"; echo 12 > "$STUB/cache"; exit "$(lire code_update)" ;;
    panel) echo true > "$STUB/pret"; echo "panel reconstruit" ;;
    notes|report|serve) echo "fait : $*" ;;
esac
"""


@pytest.fixture()
def stub(tmp_path):
    """Dossier d'état de la doublure, variables d'environnement des scripts, lecture des appels et du journal."""
    state = tmp_path / "doublure"
    state.mkdir()
    exe = tmp_path / "python-du-moteur"
    exe.write_text(STUB, encoding="utf-8")
    exe.chmod(0o755)
    values = {"restant": 5, "pas": 2, "plancher": 1, "bloque": "false", "cache": 0, "pret": "false", "lancements": 0,
              "code_update": 0}
    for k, v in values.items():
        (state / k).write_text(str(v), encoding="utf-8")
    (state / "appels").write_text("", encoding="utf-8")
    env = {"PATH": os.environ["PATH"], "BRVM_PYTHON": str(exe), "BRVM_CODE": str(ROOT), "STUB": str(state),
           "STUB_PYTHON": sys.executable, "BRVM_ALPHA_DONNEES": str(tmp_path / "donnees"),
           "BRVM_ALPHA_RAPPORTS": str(tmp_path / "rapports"), "BRVM_JOURNAL": str(tmp_path / "journaux")}

    class Stub:
        dir = state
        journal_dir = tmp_path / "journaux"

        def set(self, **kw):
            for k, v in kw.items():
                (state / k).write_text(str(v), encoding="utf-8")

        def run(self, script: str, *args: str, **extra_env: str):
            return subprocess.run(["sh", str(DEPLOY / script), *args], env={**env, **extra_env}, cwd=tmp_path,
                                  capture_output=True, text=True, timeout=120)

        def calls(self) -> list[str]:
            return (state / "appels").read_text(encoding="utf-8").splitlines()

        def log(self, name: str) -> str:
            return (tmp_path / "journaux" / f"{name}.log").read_text(encoding="utf-8")

    return Stub()


# ---------------------------------------------------------------------------
# Forme
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", SCRIPTS)
def test_scripts_are_valid_posix_shell_without_hardcoded_paths_or_secrets(name):
    path = DEPLOY / name
    assert subprocess.run(["sh", "-n", str(path)], capture_output=True, text=True).returncode == 0
    text = path.read_text(encoding="utf-8")
    code = [line.split("#", 1)[0] if not line.lstrip().startswith("#") else "" for line in text.splitlines()]
    assert "Performance passée ≠ garantie. Aucun gain n'est garanti." in text
    if name != "commun.sh":
        assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    for line in code:
        # aucun chemin absolu en dur (hors /dev/null), aucune construction propre à bash
        assert not re.search(r'''(?:^|[\s="':])/(?!dev/null)[A-Za-z]''', line), line
        assert "[[" not in line and "pipefail" not in line and "function " not in line, line
    assert not re.search(r"(?i)(mot.?de.?passe|password|token|secret)\s*=", text)
    assert "--hote" not in text  # le service reste lié à 127.0.0.1


def test_requirements_list_exact_versions_one_per_line():
    lines = [x.strip() for x in (DEPLOY / "requirements-moteur.txt").read_text(encoding="utf-8").splitlines()]
    pins = [x for x in lines if x and not x.startswith("#")]
    assert len(pins) >= 11 and all(re.fullmatch(r"[A-Za-z0-9._-]+==[A-Za-z0-9.+!_-]+", p) for p in pins), pins
    names = {p.split("==")[0].lower() for p in pins}
    assert {"pandas", "numpy", "scipy", "statsmodels", "scikit-learn", "pyarrow", "pyyaml", "requests",
            "beautifulsoup4", "lxml", "pdfplumber"} <= names
    assert "pytest" not in names  # les tests ne font pas partie du moteur installé
    import importlib.metadata as md

    for p in pins:  # versions relevées ici : celles de l'environnement des tests
        name, version = p.split("==")
        assert md.version(name) == version, p


def test_dockerfile_is_standalone_non_root_and_says_it_was_not_built():
    text = (DEPLOY / "Dockerfile.moteur").read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("#") and "N'A PAS ÉTÉ CONSTRUITE" in text.split("FROM")[0]
    assert "FROM python:3.12-slim" in text and re.search(r"^USER brvm$", text, re.M)
    assert re.search(r"^VOLUME \[\"/donnees\"\]$", text, re.M) and re.search(r"^EXPOSE 8765$", text, re.M)
    assert "--hote" not in text and "0.0.0.0" not in text.split("\nFROM")[1]
    assert not re.search(r"(?i)(password|secret|token)\s*=", text)


# ---------------------------------------------------------------------------
# collecte-initiale.sh : boucle, arrêts, verrou, journal (doublure de l'interpréteur)
# ---------------------------------------------------------------------------


def test_initial_collection_loops_until_no_progress_then_builds_panel_notes_report(stub):
    r = stub.run("collecte-initiale.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    calls = [c for c in stub.calls() if not c.startswith("etat")]
    # 5 → 3 → 1 → 1 (le BOC du jour n'est pas paru : le lancement n'avance plus)
    assert calls == ["update --from 2017-01-02 --sans-panel --max-requetes 200"] * 3 + [
        "panel", "notes research --pdf 20", "report --capital 10000000"]
    log = stub.log("collecte-initiale")
    assert "première collecte : 5 jour(s) ouvré(s) à chercher" in log and "avancement : 3 jour(s) restent." in log
    assert "arrêt : ce lancement n'a pas avancé (1 jour(s) restent)." in log
    assert "fin : première collecte terminée (1 jour(s) récent(s) encore sans bulletin)." in log
    # journal horodaté (UTC) et verrou rendu à la fin
    assert all(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ", line) for line in r.stdout.splitlines())
    assert not (stub.journal_dir / "brvm-alpha.verrou").exists()


def test_initial_collection_stops_at_first_refusal_and_sends_nothing_more(stub):
    stub.set(restant=50, pas=10, refus_au_lancement=2)
    r = stub.run("collecte-initiale.sh")
    assert r.returncode == 1
    calls = [c for c in stub.calls() if not c.startswith("etat")]
    assert calls == ["update --from 2017-01-02 --sans-panel --max-requetes 200"] * 2 + ["panel"]  # ni notes ni rapport
    log = stub.log("collecte-initiale")
    assert "arrêt : www.brvm.org a refusé l'accès. Aucune autre requête n'est envoyée." in log
    assert "collecte interrompue par un refus du site ; 40 jour(s) restent" in log


def test_initial_collection_reports_incomplete_history_when_a_run_stalls(stub):
    stub.set(restant=300, pas=100, plancher=120)  # 300 → 200 → 120 → 120 : n'avance plus, loin du but
    r = stub.run("collecte-initiale.sh", BRVM_MAX_REQUETES="50", BRVM_CAPITAL="2500000")
    assert r.returncode == 1
    calls = [c for c in stub.calls() if not c.startswith("etat")]
    assert calls[:3] == ["update --from 2017-01-02 --sans-panel --max-requetes 50"] * 3
    assert calls[3:] == ["panel", "notes research --pdf 20", "report --capital 2500000"]
    assert "fin : collecte incomplète, 120 jour(s) restent. Relancer ce script plus tard." in stub.log("collecte-initiale")


def test_initial_collection_simulation_sends_and_writes_nothing(stub):
    r = stub.run("collecte-initiale.sh", "--simulation")
    assert r.returncode == 0
    assert [c for c in stub.calls() if not c.startswith("etat")] == ["update --from 2017-01-02 --simulation"]
    assert "simulation : aucune requête envoyée" in r.stdout and "viendraient ensuite" in r.stdout
    assert stub.run("collecte-initiale.sh", "--autre").returncode == 2


def test_lock_refuses_a_second_run_and_recovers_a_stale_lock(stub):
    lock = stub.journal_dir / "brvm-alpha.verrou"
    lock.mkdir(parents=True)
    (lock / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")  # une tâche vivante tient le verrou
    for script in ("collecte-initiale.sh", "quotidien.sh"):
        r = stub.run(script)
        assert r.returncode == 3 and "une autre tâche tourne déjà" in r.stdout
    assert stub.calls() == [] and lock.is_dir()  # rien n'a été lancé, le verrou de l'autre reste
    dead = subprocess.Popen(["sh", "-c", "exit 0"])
    dead.wait()
    (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")  # verrou laissé par un processus disparu
    r = stub.run("quotidien.sh")
    assert r.returncode == 0 and "verrou périmé" in r.stdout and not lock.exists()


def test_missing_interpreter_variable_is_refused_before_anything_runs(stub):
    r = subprocess.run(["sh", str(DEPLOY / "quotidien.sh")], env={"PATH": os.environ["PATH"]}, capture_output=True,
                       text=True)
    assert r.returncode == 2 and "BRVM_PYTHON n'est pas défini" in r.stderr
    r = stub.run("quotidien.sh", BRVM_CODE=str(stub.dir))
    assert r.returncode == 2 and "ne contient pas le paquet brvm_alpha" in r.stderr


# ---------------------------------------------------------------------------
# quotidien.sh et service.sh
# ---------------------------------------------------------------------------


def test_daily_task_runs_the_four_steps_in_order_at_low_priority(stub):
    stub.set(pret="true", cache=12)
    r = stub.run("quotidien.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    assert [c for c in stub.calls() if not c.startswith("etat")] == [
        "update --sans-panel", "panel", "notes research --pdf 20", "report --capital 10000000"]
    assert "tâche quotidienne : fin, tout s'est bien passé." in stub.log("quotidien")
    text = (DEPLOY / "commun.sh").read_text(encoding="utf-8")
    assert "nice -n 19" in text and "ionice -c 3" in text and "command -v ionice" in text


def test_daily_task_skips_network_steps_after_a_refusal(stub):
    stub.set(pret="true", cache=12, refus_au_lancement=1)
    r = stub.run("quotidien.sh")
    assert r.returncode == 1
    assert [c for c in stub.calls() if not c.startswith("etat")] == ["update --sans-panel", "panel",
                                                                     "report --capital 10000000"]
    assert "www.brvm.org a refusé l'accès : aucune autre requête cette nuit." in stub.log("quotidien")


def test_service_binds_loopback_and_passes_relay_settings(stub):
    r = stub.run("service.sh", BRVM_PORT="9123", BRVM_ALPHA_PREFIXE="/rz_brvm_alpha/ui",
                 BRVM_ALPHA_ORIGINES_RELAIS="https://erp.exemple.com", BRVM_CADRE_MEME_ORIGINE="oui")
    assert r.returncode == 0, r.stderr
    assert stub.calls() == ["serve --port 9123 --cadre-meme-origine"]  # jamais --hote : 127.0.0.1
    assert "préfixe : /rz_brvm_alpha/ui" in r.stdout and "https://erp.exemple.com" in r.stdout
    stub.run("service.sh")
    assert stub.calls()[-1] == "serve --port 8765"


# ---------------------------------------------------------------------------
# Vrai moteur, dossier de données minuscule : la simulation n'envoie rien et n'écrit aucune donnée
# ---------------------------------------------------------------------------


def test_simulation_with_the_real_engine_on_a_tiny_data_folder(tmp_path):
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    (data / "boc_text").mkdir(parents=True)
    for f in sorted(BOC_FIX.glob("boc_*.txt.gz"))[:3]:
        shutil.copy(f, data / "boc_text" / f.name)
    before = sorted(p.name for p in (data / "boc_text").iterdir())
    env = {"PATH": os.environ["PATH"], "BRVM_PYTHON": sys.executable, "BRVM_ALPHA_DONNEES": str(data),
           "BRVM_ALPHA_RAPPORTS": str(reports), "HOME": str(tmp_path),
           # tout accès réseau échouerait : mandataire inexistant
           "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9"}
    r = subprocess.run(["sh", str(DEPLOY / "collecte-initiale.sh"), "--simulation"], env=env, cwd=tmp_path,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    m = re.search(r"première collecte : (\d+) jour\(s\) ouvré\(s\) à chercher depuis le 2017-01-02", r.stdout)
    assert m and int(m.group(1)) > 2000
    log = (data / "journaux" / "collecte-initiale.log").read_text(encoding="utf-8")
    assert "Simulation : aucune requête envoyée." in log and str(data / "boc_text") in log
    state = json.loads((data / "journaux" / "collecte-initiale.etat.json").read_text(encoding="utf-8"))
    assert state["pret"] is False and state["bulletins"]["en_cache"] == 3
    assert state["donnees"]["dossier"] == str(data) and state["rapport"]["dossier"] == str(reports)
    # aucune donnée écrite : mêmes bulletins, ni panel, ni notes, ni rapport ; seul le journal existe
    assert sorted(p.name for p in (data / "boc_text").iterdir()) == before
    assert sorted(p.name for p in data.iterdir()) == ["boc_text", "journaux"] and not reports.exists()
