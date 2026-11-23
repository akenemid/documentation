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
SCRIPTS = ("commun.sh", "collecte-initiale.sh", "quotidien.sh", "service.sh", "exporter-moteur.sh",
           "preparer-python-et-roues.sh", "installer-python-et-roues.sh")
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
        printf '{"pret": %s, "raison": "historique incomplet", "bulletins": {"jours_a_telecharger": 0, "jours_a_telecharger_depuis_2017": %s, "en_cache": %s}, "site": {"bloque": %s, "code_http": 403}}\n' \
            "$(lire pret)" "$(lire restant)" "$(lire cache)" "$(lire bloque)" ;;
    update)
        case " $* " in *" --simulation "*) echo "Simulation : aucune requête envoyée."; exit 0 ;; esac
        if [ -f "$STUB/dormir" ]; then echo $$ > "$STUB/pid_update"; exec sleep "$(lire dormir)"; fi
        n=$(( $(lire lancements) + 1 )); echo "$n" > "$STUB/lancements"
        if [ -f "$STUB/refus_au_lancement" ] && [ "$n" -ge "$(lire refus_au_lancement)" ]; then
            echo true > "$STUB/bloque"; echo "arrêt : HTTP 403" >&2; exit 5
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

        def start(self, script: str, *args: str, **extra_env: str):
            return subprocess.Popen(["sh", str(DEPLOY / script), *args], env={**env, **extra_env}, cwd=tmp_path,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
        # aucun chemin absolu en dur (hors /dev/null et, pour l'installateur, le préfixe par défaut de production
        # /opt/rz-brvm-alpha demandé par la session du serveur), aucune construction propre à bash
        if name == "installer-python-et-roues.sh":
            line = line.replace("PREFIXE=/opt/rz-brvm-alpha;", "PREFIXE=;")
        assert not re.search(r'''(?:^|[\s="':])/(?!dev/null)[A-Za-z]''', line), line
        assert "[[" not in line and "pipefail" not in line and "function " not in line, line
    assert not re.search(r"(?i)(mot.?de.?passe|password|token|secret)\s*=", text)
    assert "--hote" not in text  # le service reste lié à 127.0.0.1


def _pins(name: str) -> list[str]:
    lines = [x.strip() for x in (DEPLOY / name).read_text(encoding="utf-8").splitlines()]
    pins = [x for x in lines if x and not x.startswith("#")]
    assert all(re.fullmatch(r"[A-Za-z0-9._-]+==[A-Za-z0-9.+!_-]+", p) for p in pins), pins
    return pins


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_requirements_list_exact_versions_one_per_line():
    """Le fichier qui correspond à l'interpréteur courant porte exactement ses versions (une ligne par paquet) :
    Python 3.11 (CPython autonome du module Odoo) : requirements-tests-py311.txt ; sinon requirements-moteur.txt."""
    current = "requirements-tests-py311.txt" if sys.version_info[:2] == (3, 11) else "requirements-moteur.txt"
    pins = _pins(current)
    assert len(pins) >= 11
    names = {_norm(p.split("==")[0]) for p in pins}
    assert {"pandas", "numpy", "scipy", "statsmodels", "scikit-learn", "pyarrow", "pyyaml", "requests",
            "beautifulsoup4", "lxml", "pdfplumber"} <= names
    assert ("pytest" in names) == current.startswith("requirements-tests")  # pytest : seulement pour les tests
    assert not any(re.search(r"(dev|a|b|rc)\d*$", p.split("==")[1]) for p in pins), "version de développement"
    import importlib.metadata as md

    for p in pins:  # versions relevées ici : celles de l'environnement des tests
        name, version = p.split("==")
        assert md.version(name) == version, p


def test_minimal_python311_set_matches_the_wheel_list_and_the_test_set():
    """Jeu minimal du moteur embarqué (16 paquets, Python 3.11) : mêmes noms et versions que la liste des roues
    (taille et sha256 de chacune), versions identiques à celles du jeu de test."""
    pins = _pins("requirements-moteur-py311.txt")
    assert len(pins) == 16
    want = {_norm(p.split("==")[0]): p.split("==")[1] for p in pins}
    assert {"statsmodels", "scikit-learn", "pdfplumber", "pytest"}.isdisjoint(want)
    rows = [x.split("\t") for x in (DEPLOY / "roues-py311-x86_64.tsv").read_text(encoding="utf-8").splitlines()
            if x and not x.startswith("#")]
    assert len(rows) == 16 and all(len(r) == 3 and r[0].endswith(".whl") and r[1].isdigit() for r in rows)
    assert all(re.fullmatch(r"[0-9a-f]{64}", r[2]) for r in rows)
    wheels = {_norm(r[0].split("-")[0]): r[0].split("-")[1] for r in rows}
    assert wheels == want
    tests = {_norm(p.split("==")[0]): p.split("==")[1] for p in _pins("requirements-tests-py311.txt")}
    assert all(tests[k] == v for k, v in want.items())
    assert all(re.search(r"(cp311|py3|py2\.py3)-(cp311|none|abi3)-(manylinux[^ ]*x86_64|any)\.whl$", r[0]) for r in rows)
    ref = (DEPLOY / "python-autonome.txt").read_text(encoding="utf-8")
    assert "3.11.15" in ref and "23ccae6f1ff73e8aa8378436f869da003b8eb7d6c95f2bc706f494115ba1447d" in ref
    assert "30930344" in ref and "install_only_stripped.tar.gz" in ref


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
    # journal horodaté (UTC) et verrou rendu à la fin (flock : le fichier reste, le verrou est libre)
    assert all(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ", line) for line in r.stdout.splitlines())
    import fcntl

    with open(stub.journal_dir / "brvm-alpha.verrou", "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_initial_collection_stops_at_first_refusal_and_sends_nothing_more(stub):
    stub.set(restant=50, pas=10, refus_au_lancement=2)
    r = stub.run("collecte-initiale.sh")
    assert r.returncode == 5  # refus du site : code 5, jamais 3
    calls = [c for c in stub.calls() if not c.startswith("etat")]
    assert calls == ["update --from 2017-01-02 --sans-panel --max-requetes 200"] * 2 + ["panel"]  # ni notes ni rapport
    log = stub.log("collecte-initiale")
    assert "arrêt : www.brvm.org a refusé l'accès (HTTP 403). Aucune autre requête n'est envoyée." in log
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


@pytest.mark.skipif(shutil.which("flock") is None, reason="flock (util-linux) absent")
def test_lock_refuses_a_second_run_with_code_4_and_is_released_by_the_system(stub):
    import fcntl

    lock = stub.journal_dir / "brvm-alpha.verrou"
    lock.parent.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen([sys.executable, "-c", (
        "import fcntl, sys, time\nf = open(sys.argv[1], 'a')\nfcntl.flock(f, fcntl.LOCK_EX)\nprint('tenu', flush=True)\n"
        "time.sleep(60)\n"), str(lock)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "tenu"  # une autre tâche tient le verrou (flock)
        for script in ("collecte-initiale.sh", "quotidien.sh"):
            r = stub.run(script)
            assert r.returncode == 4 and "une autre tâche tourne déjà" in r.stdout, r.stdout + r.stderr
        assert stub.calls() == []  # rien n'a été lancé
    finally:
        holder.kill()  # détenteur tué : le système rend le verrou, aucun verrou « périmé » à deviner
        holder.wait()
    stub.set(pret="true", cache=12)
    r = stub.run("quotidien.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    assert lock.is_file()  # le fichier de verrou n'est jamais supprimé
    with open(lock, "a") as fh:  # et il est libre à la fin de la tâche
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.skipif(shutil.which("flock") is None, reason="flock (util-linux) absent")
def test_term_is_passed_to_the_running_command_and_the_task_stops(stub):
    import signal
    import time

    stub.set(dormir=60)
    proc = stub.start("quotidien.sh")
    pid_file = stub.dir / "pid_update"
    deadline = time.monotonic() + 30
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    child = int(pid_file.read_text(encoding="utf-8"))
    proc.send_signal(signal.SIGTERM)
    out, _err = proc.communicate(timeout=30)
    assert proc.returncode == 143 and "arrêt demandé (signal TERM)" in out
    with pytest.raises(ProcessLookupError):  # la commande en cours a reçu TERM : elle n'existe plus
        os.kill(child, 0)
    assert not [c for c in stub.calls() if c.startswith(("panel", "notes", "report"))]  # aucune étape après l'arrêt


def test_relative_paths_bad_numbers_and_usage_errors_are_refused_with_code_2(stub):
    for var in ("BRVM_ALPHA_DONNEES", "BRVM_ALPHA_RAPPORTS", "BRVM_JOURNAL"):
        r = stub.run("quotidien.sh", **{var: "relatif/dossier"})
        assert r.returncode == 2 and f"{var} doit être un chemin absolu" in r.stderr
    r = stub.run("collecte-initiale.sh", BRVM_MAX_REQUETES="beaucoup")
    assert r.returncode == 2 and "BRVM_MAX_REQUETES doit être un entier" in r.stderr
    r = stub.run("quotidien.sh", BRVM_CAPITAL="10M")
    assert r.returncode == 2 and "BRVM_CAPITAL doit être un entier" in r.stderr
    assert stub.calls() == []
    # « update » refuse ses arguments (code 2) : mauvaise utilisation, pas un refus du site.
    stub.set(code_update=2)
    r = stub.run("collecte-initiale.sh")
    log = stub.log("collecte-initiale")
    assert r.returncode == 2 and "mauvaise utilisation de « update »" in log and "refusé l'accès" not in log


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
        "update --sans-panel", "panel", "suivi maj", "notes research --pdf 20", "report --capital 10000000"]
    assert "tâche quotidienne : fin, tout s'est bien passé." in stub.log("quotidien")
    text = (DEPLOY / "commun.sh").read_text(encoding="utf-8")
    assert "nice -n 19" in text and "ionice -c 2 -n 7" in text and "command -v ionice" in text


def test_daily_task_skips_network_steps_after_a_refusal(stub):
    stub.set(pret="true", cache=12, refus_au_lancement=1)
    r = stub.run("quotidien.sh")
    assert r.returncode == 5
    assert [c for c in stub.calls() if not c.startswith("etat")] == ["update --sans-panel", "panel", "suivi maj",
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


# ---------------------------------------------------------------------------
# Interpréteur autonome et roues : vérifications avant toute installation (fichiers factices, hors ligne)
# ---------------------------------------------------------------------------


def _fake_payload(tmp_path: Path, name: str):
    """Copie ``name`` dans un faux dossier de code, avec des références qui décrivent 16 roues factices."""
    import hashlib

    code = tmp_path / "code"
    (code / "deploiement").mkdir(parents=True)
    shutil.copy(DEPLOY / name, code / "deploiement" / name)
    shutil.copy(DEPLOY / "requirements-moteur-py311.txt", code / "deploiement")
    src = tmp_path / "source"
    (src / "roues").mkdir(parents=True)
    archive = src / "cpython-essai.tar.gz"
    archive.write_bytes(b"archive factice")
    rows = []
    for i in range(16):
        whl = src / "roues" / f"paquet{i}-1.0-py3-none-any.whl"
        whl.write_bytes(f"roue {i}".encode())
        rows.append(f"{whl.name}\t{whl.stat().st_size}\t{hashlib.sha256(whl.read_bytes()).hexdigest()}")
    (code / "deploiement" / "roues-py311-x86_64.tsv").write_text("# roue\toctets\tsha256\n" + "\n".join(rows) + "\n",
                                                                 encoding="utf-8")
    (code / "deploiement" / "python-autonome.txt").write_text(
        "version=3.11.15\narchive=cpython-essai.tar.gz\nurl=https://exemple.invalid/x.tar.gz\n"
        f"octets={archive.stat().st_size}\nsha256={hashlib.sha256(archive.read_bytes()).hexdigest()}\n",
        encoding="utf-8")
    return code / "deploiement" / name, src


def test_installer_refuses_any_mismatch_before_extracting_anything(tmp_path):
    script, src = _fake_payload(tmp_path, "installer-python-et-roues.sh")
    prefix, moteur = tmp_path / "prefixe", tmp_path / "moteur"
    (moteur / "brvm_alpha").mkdir(parents=True)
    (moteur / "brvm_alpha" / "__init__.py").write_text("", encoding="utf-8")
    env = {"PATH": os.environ["PATH"]}

    def run(*args):
        return subprocess.run(["sh", str(script), *map(str, args)], env=env, capture_output=True, text=True, timeout=60)

    assert run("relatif", src, moteur).returncode == 2
    assert run(prefix).returncode == 2
    (src / "roues" / "paquet3-1.0-py3-none-any.whl").write_bytes(b"roue modifiee")
    r = run(prefix, src, moteur)
    assert r.returncode == 1 and "roue paquet3-1.0-py3-none-any.whl : taille ou sha256 inattendu" in r.stderr
    (src / "roues" / "paquet3-1.0-py3-none-any.whl").write_bytes(b"roue 3")
    (src / "roues" / "intrus-1.0-py3-none-any.whl").write_bytes(b"x")
    r = run(prefix, src, moteur)
    assert r.returncode == 1 and "pas exactement les 16 roues" in r.stderr
    (src / "roues" / "intrus-1.0-py3-none-any.whl").unlink()
    # Constat de recette : tout fichier de plus est refusé, pas seulement un *.whl (sdist, sitecustomize.py, caché)
    for intrus in ("evil-1.0.tar.gz", "sitecustomize.py", ".cache"):
        (src / "roues" / intrus).write_bytes(b"x")
        r = run(prefix, src, moteur)
        assert r.returncode == 1 and "et rien d'autre" in r.stderr, intrus
        (src / "roues" / intrus).unlink()
    (src / "roues" / "paquet0-1.0-py3-none-any.whl").unlink()
    assert run(prefix, src, moteur).returncode == 1
    (src / "roues" / "paquet0-1.0-py3-none-any.whl").write_bytes(b"roue 0")
    (src / "cpython-essai.tar.gz").write_bytes(b"archive alteree")
    r = run(prefix, src, moteur)
    assert r.returncode == 1 and "taille ou sha256 inattendu" in r.stderr
    assert not prefix.exists()  # rien n'a été extrait ni installé


def test_preparer_copies_local_files_verifies_them_and_removes_a_bad_one(tmp_path):
    script, src = _fake_payload(tmp_path, "preparer-python-et-roues.sh")
    dest = tmp_path / "paquets"
    env = {"PATH": os.environ["PATH"], "BRVM_DEPUIS": str(src)}
    r = subprocess.run(["sh", str(script), str(dest)], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert len(list((dest / "roues").glob("*.whl"))) == 16 and (dest / "cpython-essai.tar.gz").is_file()
    assert (dest / "roues-py311-x86_64.tsv").is_file() and (dest / "python-autonome.txt").is_file()
    shutil.rmtree(dest)
    (src / "roues" / "paquet5-1.0-py3-none-any.whl").write_bytes(b"alteree")
    r = subprocess.run(["sh", str(script), str(dest)], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and "fichier retiré" in r.stderr
    assert not (dest / "roues" / "paquet5-1.0-py3-none-any.whl").exists()
    r = subprocess.run(["sh", str(script), str(script.parent / "dans_le_code")], env=env, capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 2 and "est dans le dépôt" in r.stderr


def test_gitignore_keeps_wheels_and_interpreter_archives_out_of_the_repository():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.whl" in text and "cpython-*.tar.gz" in text
