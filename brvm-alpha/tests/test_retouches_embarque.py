"""Retouches du moteur embarqué : points ouverts du contrôle final.

Chaque essai reproduit un constat du contrôle final (il échouait avant la correction) :

- P1 temps de calcul hérité : un travailleur Odoo baisse sa limite souple ``RLIMIT_CPU`` et le moteur en hérite.
  ``recommend`` sortait en −24 sans objet JSON ; un processus de travail du panel tué par ``SIGXCPU`` donnait 6
  « memoire ». Désormais : marge trop basse au démarrage → 8 avec un objet JSON (la limite n'est pas relevée par
  le moteur) ; ``SIGXCPU`` en cours de commande → 8 avec un objet JSON ; travailleur tué par ``SIGXCPU`` → 8,
  par ``SIGSEGV`` → 7, par ``SIGKILL`` sous une limite de mémoire → 6 ;
- P2 chemins : ``--racine``, ``--panel-dir`` et ``--boc-dir`` hors de ``BRVM_ALPHA_DONNEES`` étaient acceptés en mode
  embarqué (``notes add --racine /ailleurs`` y créait un journal) ; désormais 2, et rien n'est créé ;
- P3 outils de poppler : sans lien au parent, un ``pdftotext`` lent survivait au moteur tué seul et sortait en 3,
  récolté par le processus 1 ; désormais il meurt avec le moteur ;
- P4 documentation : nombre de fichiers exportés, ``RLIMIT_CPU`` et ``TMPDIR`` dédié dans le lanceur d'exemple ;
- P5 ``update --simulation --rouvrir`` ne comptait pas les jours rouverts dans ``jours_a_chercher`` ;
- P6 une requête refusée avant l'envoi (adresse interdite, hôte hors liste) réservait quand même un créneau dans
  ``politeness.json`` : 10 s d'attente de trop au lancement suivant. Revu ensuite (constat du contrôle de bf68de2,
  trois sessions simultanées : une requête partait 4 s après la FIN d'une autre, car la réservation retirée remettait
  une date plus ancienne) : les contrôles d'adresse sont faits avant toute réservation ou attente, une réservation
  n'est plus jamais retirée, la fin d'une vraie requête est toujours notée, une seule requête à la fois vers le site.
  Revu encore (contrôle de 1a1fd28) : une requête interrompue (TERM, Ctrl+C, SIGXCPU, KILL) ne notait pas sa fin, et
  la session qui attendait partait aussitôt ; désormais la fin est notée à toute sortie, et une marque « envoi en
  cours » restée sans fin (KILL) coûte un délai entier ; verrou d'envoi impossible alors que politeness.json s'écrit :
  rien ne part (code 8) ; date illisible : un délai ; 403 d'une autre session : arrêt dès la prise du verrou.
  Marge de coupure ensuite (après d99bbbc) : une requête qui ne s'est pas terminée normalement compte comme finie 2 s
  après sa coupure, et une marque orpheline coûte un délai plus 2 s (le site ne voit la coupure qu'à sa prochaine
  écriture) ; une fin normale garde exactement un délai ;
- P7 ``recommend`` sur un panel de 7 séances sortait en 7 (``TypeError`` dans l'évaluation des indices).

Hors ligne : dossiers temporaires, doublures, aucune requête vers l'extérieur. Le code 3 n'est jamais attendu.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from brvm_alpha import cli, demarrage, erreurs, paths, pdf

ROOT = Path(__file__).resolve().parents[1]
BOC_FIX = ROOT / "tests" / "fixtures" / "notes" / "boc"
CODES_ADMIS = {0, 1, 2, 4, 5, 6, 7, 8, 130}


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


def _env_sous_processus(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("BRVM_ALPHA_")}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(ROOT), "HTTPS_PROXY": "http://127.0.0.1:9",
                "HTTP_PROXY": "http://127.0.0.1:9"})
    env.update(extra)
    return env


def _moteur(args: list[str], env: dict[str, str], *, preexec=None, timeout: float = 180,
            cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", "-m", "brvm_alpha", *args], env=env, cwd=str(cwd or ROOT),
                          capture_output=True, text=True, timeout=timeout, preexec_fn=preexec)


def _cpu(soft: int):
    """``preexec_fn`` : limite souple de temps de calcul à ``soft`` secondes, limite dure inchangée (comme Odoo)."""
    def f():
        import resource

        _s, hard = resource.getrlimit(resource.RLIMIT_CPU)
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return f


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    """Sept BOC des fixtures et leur panel (historique incomplet)."""
    from brvm_alpha.data import store

    base = tmp_path_factory.mktemp("retouches_embarque")
    (base / "boc_text").mkdir()
    for f in BOC_FIX.glob("boc_*.txt.gz"):
        shutil.copy(f, base / "boc_text" / f.name)
    store.build_panel(base / "boc_text", base / "panel", workers=1)
    return base


# ---------------------------------------------------------------------------
# P1 : temps de calcul hérité (RLIMIT_CPU, SIGXCPU)
# ---------------------------------------------------------------------------


def test_low_cpu_limit_at_start_exits_8_with_one_json_object_and_the_limit_is_left_alone(tmp_path):
    env = _env_sous_processus()
    p = _moteur(["etat", "--format", "json"], env, preexec=_cpu(5), cwd=tmp_path)
    obj = json.loads(p.stdout)  # avant : recommend sortait en −24, sans objet JSON
    assert p.returncode == 8 and obj["ok"] is False and obj["code"] == 8 and obj["erreur"] == "configuration"
    assert "limite de temps de calcul trop basse" in obj["message"]
    assert "le lanceur doit relever RLIMIT_CPU" in obj["message"] and "5 s" in obj["message"]
    assert list(obj) == ["ok", "code", "erreur", "message", "bandeau"] and obj["bandeau"] == cli.BANNER
    p = _moteur(["etat"], env, preexec=_cpu(5), cwd=tmp_path)
    assert p.returncode == 8 and p.stdout == "" and "limite de temps de calcul trop basse" in p.stderr
    # rien n'est chargé et la limite n'est pas relevée par le moteur (décision laissée au lanceur)
    script = ("import resource, sys\nfrom brvm_alpha import demarrage\ncode = demarrage.lancer(sys.argv[1:])\n"
              "print('LIMITE', resource.getrlimit(resource.RLIMIT_CPU)[0], 'PANDAS', 'pandas' in sys.modules, "
              "file=sys.stderr)\nsys.exit(code)\n")
    p = subprocess.run([sys.executable, "-B", "-c", script, "etat", "--format", "json"], env=env, preexec_fn=_cpu(5),
                       capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    assert p.returncode == 8 and "LIMITE 5 PANDAS False" in p.stderr, p.stderr[-800:]
    # seuil réglable ; 0 désactive le contrôle
    assert demarrage.controle_cpu({}, limite=1000, consomme=50) is None
    assert demarrage.controle_cpu({}, limite=950, consomme=60) is not None  # 890 s de marge < 900
    assert demarrage.controle_cpu({demarrage.ENV_CPU_MIN: "0"}, limite=1, consomme=0) is None
    assert "au moins 2000 s" in demarrage.controle_cpu({demarrage.ENV_CPU_MIN: "2000"}, limite=1500, consomme=0)
    assert demarrage.seuil_cpu({}) == 900 and demarrage.seuil_cpu({demarrage.ENV_CPU_MIN: "abc"}) == 900
    p = _moteur(["etat", "--format", "json"], _env_sous_processus(BRVM_ALPHA_CPU_MIN="0"), preexec=_cpu(600),
                cwd=tmp_path)
    assert p.returncode in CODES_ADMIS and json.loads(p.stdout)["ok"] is True


def test_sigxcpu_during_a_command_exits_8_with_one_json_object(tiny, tmp_path):
    env = _env_sous_processus(BRVM_ALPHA_CPU_MIN="0")  # contrôle du démarrage coupé : la limite tombe en cours
    p = _moteur(["recommend", "--capital", "10000000", "--sans-indices", "--tirages", "50", "--panel-dir",
                 str(tiny / "panel"), "--racine", str(tmp_path), "--format", "json"], env, preexec=_cpu(1),
                cwd=tmp_path)
    if p.returncode == 0:  # machine très rapide : la commande a fini sous 1 s de calcul
        pytest.skip("commande finie avant la limite de temps de calcul")
    assert p.returncode == 8, (p.returncode, p.stderr[-1500:])  # avant : −24, sortie vide
    obj = json.loads(p.stdout)
    assert obj["ok"] is False and obj["code"] == 8 and obj["erreur"] == "configuration"
    assert "SIGXCPU" in obj["message"] and "le lanceur doit relever rlimit_cpu" in obj["message"].lower()


_SCRIPT_TRAVAILLEUR = r'''
import os, resource, signal, sys


def suicide(path):  # remplace l'analyse d'un BOC dans le processus de travail du panel
    os.kill(os.getpid(), getattr(signal, os.environ["SIG_TRAVAILLEUR"]))


if __name__ == "__main__":
    _s, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024 ** 3, hard))  # comme le lanceur d'Odoo
    from brvm_alpha import cli
    from brvm_alpha.data import store
    store._parse_one = suicide
    sys.exit(cli.main(sys.argv[1:]))
'''


@pytest.mark.parametrize("sig, code, erreur, motif", [
    ("SIGXCPU", 8, "configuration", "temps de calcul"),
    ("SIGSEGV", 7, "interne", "SIGSEGV"),
    ("SIGKILL", 6, "memoire", "SIGKILL"),
])
def test_a_panel_worker_killed_by_a_signal_gets_the_code_of_its_cause(tiny, tmp_path, sig, code, erreur, motif):
    script = tmp_path / "travailleur.py"
    script.write_text(_SCRIPT_TRAVAILLEUR, encoding="utf-8")
    p = subprocess.run([sys.executable, "-B", str(script), "panel", "--force", "--boc-dir", str(tiny / "boc_text"),
                        "--panel-dir", str(tmp_path / "panel"), "--workers", "2", "--format", "json"],
                       env=_env_sous_processus(SIG_TRAVAILLEUR=sig), capture_output=True, text=True, timeout=180,
                       cwd=str(tmp_path))
    obj = json.loads(p.stdout)  # avant : 6 « memoire » pour les trois signaux (RLIMIT_AS posée)
    assert p.returncode == code and obj["code"] == code and obj["erreur"] == erreur, (obj, p.stderr[-1200:])
    assert motif in obj["message"] and obj["bandeau"] == cli.BANNER


def _pool_casse(codes):
    from concurrent.futures.process import BrokenProcessPool

    exc = BrokenProcessPool("A process in the process pool was terminated abruptly while the future was running.")
    if codes is not None:
        setattr(exc, erreurs.ATTR_CODES_TRAVAILLEURS, codes)
    return exc


def test_worker_deaths_are_classified_by_their_exit_codes_not_only_by_the_memory_limit(monkeypatch):
    monkeypatch.setattr(erreurs, "limite_memoire", lambda: 3 * 1024 ** 3)  # RLIMIT_AS posée, comme dans Odoo
    cas = {(-24, -15): 8, (-11, -15): 7, (-6,): 7, (-7,): 7, (-9,): 6, (-9, -24): 8}
    for codes, attendu in cas.items():
        exc = _pool_casse(list(codes))
        assert erreurs.code_retour(exc) == attendu, codes
        assert erreurs.est_memoire(exc) is (attendu == 6), codes
        assert erreurs.type_erreur(exc) == erreurs.TYPES[attendu]
    assert "temps de calcul" in erreurs.message_erreur(_pool_casse([-24]))
    assert "SIGSEGV" in erreurs.message_erreur(_pool_casse([-11])) and "pas un manque de mémoire" in \
        erreurs.message_erreur(_pool_casse([-11]))
    # cause inconnue : classement d'avant (6 sous RLIMIT_AS), écrit dans le message
    for codes in (None, [], [1, -15], [-15]):
        exc = _pool_casse(codes)
        assert erreurs.code_retour(exc) == 6 and "cause inconnue" in erreurs.message_erreur(exc), codes
    # dans une chaîne d'exceptions
    try:
        try:
            raise _pool_casse([-24])
        except Exception as inner:
            raise RuntimeError("panel") from inner
    except RuntimeError as outer:
        assert erreurs.code_retour(outer) == 8
    # sans limite de mémoire : SIGKILL ou cause inconnue → 7 (comme avant), SIGXCPU → 8
    monkeypatch.setattr(erreurs, "limite_memoire", lambda: None)
    assert erreurs.code_retour(_pool_casse([-9])) == 7 and "cause inconnue" in erreurs.message_erreur(_pool_casse([-9]))
    assert erreurs.code_retour(_pool_casse(None)) == 7 and erreurs.code_retour(_pool_casse([-24])) == 8
    assert erreurs.code_retour(erreurs.TempsCalculDepasse("x")) == 8
    assert erreurs.type_erreur(erreurs.TempsCalculDepasse("x")) == "configuration"
    assert all(erreurs.code_sur(c) == c for c in CODES_ADMIS) and erreurs.code_sur(3) == 7  # jamais 3


# ---------------------------------------------------------------------------
# P2 : --racine, --panel-dir, --boc-dir dans BRVM_ALPHA_DONNEES (mode embarqué)
# ---------------------------------------------------------------------------


@pytest.fixture()
def embarque(tmp_path, monkeypatch):
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    (data / "notes").mkdir(parents=True)
    reports.mkdir()
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: True)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "REPORTS_DIR", reports)
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    return data, reports


def test_embedded_data_folder_options_outside_the_data_folder_are_refused_before_any_write(embarque, tmp_path,
                                                                                           capsys, monkeypatch):
    data, _reports = embarque
    dehors = tmp_path / "ailleurs"
    dehors.mkdir()
    courant = tmp_path / "cwd_odoo"  # dossier courant du lanceur : une valeur faite d'espaces y menait
    courant.mkdir()
    monkeypatch.chdir(courant)
    (data / "lien").symlink_to(dehors, target_is_directory=True)  # lien placé dans les données, qui mène dehors
    note = ["--cible", "SNTS", "--titre", "t", "--texte", "essai"]
    refus = [
        ["notes", "add", "--racine", str(dehors / "racine"), *note],  # avant : code 0, journal créé dehors
        ["notes", "add", "--racine", str(data / "lien" / "racine"), *note],
        ["notes", "list", "--racine", str(data) + "/../ailleurs"],
        ["panel", "--panel-dir", str(dehors / "panel")],
        ["update", "--simulation", "--boc-dir", str(dehors / "boc")],
        ["etat", "--panel-dir", str(dehors / "panel"), "--boc-dir", str(data / "boc_text")],
        ["panel", "--panel-dir", str(data)],  # le dossier des données lui-même
        ["panel", "--panel-dir", "."],  # relatif : le dossier des données lui-même
        ["panel", "--panel-dir", str(data / "notes")],  # le panel remplacerait le journal
        ["panel", "--panel-dir", str(data / "boc_text" / "panel")],
        # valeur vide ou faite d'espaces (avant : code 0, journal ou panel créé dans le dossier courant)
        ["notes", "add", "--racine", " ", *note],
        ["notes", "add", "--racine", "\t", *note],
        ["notes", "add", "--racine", "", *note],
        ["panel", "--panel-dir", " "],
        ["etat", "--panel-dir", " "],
        ["update", "--simulation", "--boc-dir", " "],
    ]
    for argv in refus:
        code, out, _ = run_cli(capsys, *argv, "--format", "json")
        d = one_json(out)
        assert code == 2 and d["erreur"] == "saisie_invalide" and d["message"].startswith("refusé"), (argv, d)
    assert list(dehors.iterdir()) == [] and list(courant.iterdir()) == []  # rien n'a été créé dehors
    assert sorted(p.name for p in data.iterdir()) == ["lien", "notes"] and list((data / "notes").iterdir()) == []
    # dans les données : accepté (absolu ou relatif)
    code, out, _ = run_cli(capsys, "notes", "add", "--racine", str(data / "notes"), *note, "--format", "json")
    assert code == 0 and one_json(out)["cree"] is True and (data / "notes" / "notes.jsonl").is_file()
    code, out, _ = run_cli(capsys, "notes", "list", "--racine", "notes", "--format", "json")
    assert code == 0 and one_json(out)["n"] == 1


def test_data_folder_options_are_unchanged_outside_embedded_mode(tmp_path, capsys):
    assert not paths.est_embarque()
    code, _out, _ = run_cli(capsys, "notes", "add", "--racine", str(tmp_path / "ailleurs"), "--cible", "SNTS",
                           "--titre", "t", "--texte", "hors mode embarqué", "--format", "json")
    assert code == 0 and (tmp_path / "ailleurs" / "notes.jsonl").is_file()


# ---------------------------------------------------------------------------
# P3 : outils de poppler liés au moteur (PR_SET_PDEATHSIG)
# ---------------------------------------------------------------------------


def test_poppler_tools_are_linked_to_the_engine(tmp_path):
    if not sys.platform.startswith("linux"):
        pytest.skip("PR_SET_PDEATHSIG : Linux seulement")
    outil = tmp_path / "outil"
    outil.write_text(f"#!{sys.executable} -I\nimport ctypes\nlibc = ctypes.CDLL(None)\nv = ctypes.c_int(0)\n"
                     "libc.prctl(2, ctypes.byref(v), 0, 0, 0)\nprint(v.value)\n", encoding="utf-8")  # PR_GET_PDEATHSIG
    outil.chmod(0o755)
    code, out, _err = pdf.lancer_outil([str(outil)], delai=60)
    assert code == 0 and out.decode().strip() == str(int(signal.SIGKILL))  # avant : 0 (aucun lien)


_FAUX_PDFTOTEXT = '''#!{python} -I
# Faux pdftotext lent, en un seul processus : il note son début, dort, note sa fin et sort en 3 (code de poppler).
import os, sys, time
if sys.argv[1:2] == ["-v"]:
    sys.stderr.write("pdftotext version 24.02.0\\n")
    sys.exit(0)
trace = os.environ["FAUX_TRACE"]
with open(trace, "a") as fh:
    fh.write(f"{{os.getpid()}} debut\\n")
time.sleep(4)
with open(trace, "a") as fh:
    fh.write(f"{{os.getpid()}} fin\\n")
sys.exit(3)
'''

_RECOLTEUR = r'''
import ctypes, json, os, signal, subprocess, sys, time
bin_dir, trace, pdf_path = sys.argv[1:4]
assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER : joue le processus 1
env = dict(os.environ, PATH=bin_dir + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"), FAUX_TRACE=trace)
pilote = subprocess.Popen([sys.executable, "-B", "-c",
                           "import sys; from brvm_alpha import pdf; pdf.par_pdftotext(sys.argv[1])", pdf_path],
                          env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.monotonic()
while time.monotonic() - t0 < 60 and "debut" not in open(trace).read():
    time.sleep(0.02)
time.sleep(0.3)
os.kill(pilote.pid, signal.SIGKILL)  # KILL au seul moteur (tueur de mémoire du noyau)
t_kill = time.monotonic()
recoltes = []
while True:
    try:
        pid, st = os.waitpid(-1, 0)
    except ChildProcessError:
        break
    recoltes.append({"principal": pid == pilote.pid, "code": os.waitstatus_to_exitcode(st),
                     "apres_kill_s": round(time.monotonic() - t_kill, 2)})
print(json.dumps({"recoltes": recoltes, "trace": open(trace).read()}))
'''


def test_killing_the_engine_alone_during_a_slow_pdftotext_leaves_no_orphan(tmp_path):
    if not sys.platform.startswith("linux"):
        pytest.skip("PR_SET_CHILD_SUBREAPER : Linux seulement")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "pdftotext").write_text(_FAUX_PDFTOTEXT.format(python=sys.executable), encoding="utf-8")
    (bin_dir / "pdftotext").chmod(0o755)
    (tmp_path / "trace").write_text("", encoding="utf-8")
    (tmp_path / "x.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (tmp_path / "recolteur.py").write_text(_RECOLTEUR, encoding="utf-8")
    p = subprocess.run([sys.executable, "-B", str(tmp_path / "recolteur.py"), str(bin_dir), str(tmp_path / "trace"),
                        str(tmp_path / "x.pdf")], env=_env_sous_processus(), capture_output=True, text=True,
                       timeout=120, cwd=str(tmp_path))
    assert p.returncode == 0, p.stderr[-1500:]
    res = json.loads(p.stdout)
    assert "debut" in res["trace"] and "fin" not in res["trace"]  # l'outil n'a pas survécu au moteur
    outils = [r for r in res["recoltes"] if not r["principal"]]
    assert all(r["code"] != 3 for r in res["recoltes"])  # avant : outil récolté 4 s plus tard, code 3
    assert all(r["apres_kill_s"] < 2.0 for r in res["recoltes"]), res
    assert all(r["code"] == -signal.SIGKILL for r in outils), res


# ---------------------------------------------------------------------------
# P4 : documentation du lanceur et de l'export
# ---------------------------------------------------------------------------


def test_deployment_doc_raises_the_cpu_limit_and_matches_the_export(tmp_path):
    doc = (ROOT / "docs" / "DEPLOIEMENT.md").read_text(encoding="utf-8")
    plat = " ".join(doc.split())
    a6 = doc.split("### A.6", 1)[1].split("### A.7", 1)[0]
    assert "resource.setrlimit(resource.RLIMIT_CPU, (hard, hard))" in a6 and "--cpu=unlimited:" in a6
    assert "TMPDIR` **dédié**" in a6 and "70 caractères au plus" in a6
    assert "BRVM_ALPHA_CPU_MIN" in doc.split("### A.3", 1)[1].split("### A.4", 1)[0]
    assert "Odoo ne passe jamais ces trois options" in plat.replace("**", "")
    assert "Performance passée ≠ garantie. Aucun gain n'est garanti." in doc
    # le lanceur d'exemple relève bien la limite souple de temps de calcul à la limite dure
    code = a6.split("```python", 1)[1].split("```", 1)[0]
    ns: dict = {}
    exec(compile(code, "DEPLOIEMENT.md § A.6", "exec"), ns)  # noqa: S102 - définitions seulement, aucun lancement

    def preexec():
        _cpu(5)()
        ns["_limite"]()

    lire = "import resource; s, h = resource.getrlimit(resource.RLIMIT_CPU); print(s == h)"
    r = subprocess.run([sys.executable, "-I", "-c", lire], preexec_fn=preexec, capture_output=True, text=True,
                       timeout=60)
    assert r.stdout.strip() == "True", r.stderr
    # nombre de fichiers exportés
    r = subprocess.run(["sh", str(ROOT / "deploiement" / "exporter-moteur.sh"), str(tmp_path / "moteur")],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    n = int(re.search(r"^# fichiers : (\d+)$", (tmp_path / "moteur" / "VERSION").read_text(encoding="utf-8"),
                      re.MULTILINE).group(1))
    assert f"Mesuré : {n} fichiers" in doc, n


# ---------------------------------------------------------------------------
# P5 : update --simulation --rouvrir compte les jours rouverts
# ---------------------------------------------------------------------------


def test_update_simulation_counts_the_reopened_days(tmp_path, capsys):
    boc = tmp_path / "boc_text"
    boc.mkdir()
    for day in ("20210507", "20210510", "20210511"):
        (boc / f"boc_{day}.missing").write_bytes(b"")  # anciens marqueurs vides : définitifs
    base = ["update", "--boc-dir", str(boc), "--panel-dir", str(tmp_path / "panel"), "--from", "2021-05-07",
            "--jusqu-au", "2021-05-12", "--sans-panel", "--simulation", "--format", "json"]
    code, out, _ = run_cli(capsys, *base)
    d = one_json(out)
    assert code == 0 and d["jours_a_chercher"] == 1 and [str(x) for x in d["jours"]] == ["2021-05-12"]
    code, out, _ = run_cli(capsys, *base, "--rouvrir", "2021-05-07..2021-05-10")
    d = one_json(out)
    assert code == 0 and d["marqueurs_rouverts"] == ["2021-05-07", "2021-05-10"]
    assert d["jours_a_chercher"] == 3  # avant : 1 (les jours rouverts n'étaient pas comptés)
    assert [str(x) for x in d["jours"]] == ["2021-05-07", "2021-05-10", "2021-05-12"]
    assert len(list(boc.glob("*.missing"))) == 3  # simulation : rien n'est retiré
    # un jour rouvert hors de la fenêtre (--from) n'est pas compté, comme dans un vrai lancement
    code, out, _ = run_cli(capsys, *[a if a != "2021-05-07" else "2021-05-10" for a in base], "--rouvrir",
                           "2021-05-07..2021-05-11")
    d = one_json(out)
    assert d["marqueurs_rouverts"] == ["2021-05-07", "2021-05-10", "2021-05-11"] and d["jours_a_chercher"] == 3


# ---------------------------------------------------------------------------
# P6 : politesse entre sessions. Contrôles d'adresse AVANT toute réservation ; une réservation n'est jamais retirée
# ni reculée ; la fin d'une vraie requête est toujours notée ; une requête à la fois vers le site.
# ---------------------------------------------------------------------------

_NOW = dt.datetime(2026, 11, 23, 3, 40, tzinfo=dt.timezone.utc)
URL_BOC = "https://www.brvm.org/sites/default/files/boc_20261123.pdf"


class _R:
    def __init__(self, status, content=b"", headers=None, url=""):
        self.status_code, self.content, self.headers, self.url = status, content, headers or {}, url


class _Horloge:
    """Horloge des délais qui avance avec les attentes ; ``attentes`` : attentes demandées."""

    def __init__(self, t0: float = 1000.0):
        self.t0 = self.t = t0
        self.attentes: list[float] = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.attentes.append(float(s))
        self.t += max(0.0, float(s))

    def now(self):
        return _NOW + dt.timedelta(seconds=self.t - 1000.0)


def _session(cache, transport, h):
    from brvm_alpha.notes import research as rs

    return rs.PoliteSession(transport=transport, clock=h, sleep=h.sleep, now=h.now, cache_dir=cache,
                            log_path=cache.parent / "fetch_log.jsonl", delay_s=10.0)


def _etat_politesse(cache) -> dict:
    from brvm_alpha.notes import research as rs

    f = cache / rs.POLITENESS_STATE
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _attente_avant_premier_envoi(cache, t0: float) -> float:
    h = _Horloge(t0)
    envoi = []

    def ok(url, headers, timeout):
        envoi.append(sum(h.attentes))
        return _R(404 if url.endswith("robots.txt") else 200, b"%PDF-1.4 x", None, url)

    _session(cache, ok, h).get("https://www.brvm.org/sites/default/files/boc_20261120.pdf")
    return envoi[0]


class _SansReseau:
    """Session ``requests`` de doublure, sans mandataire : tout envoi fait échouer l'essai."""

    proxies: dict = {}
    trust_env = False

    def get(self, *a, **k):
        raise AssertionError("aucune requête ne doit partir")


def _client_refusant(refus):
    """Client commun du moteur (``net.ClientHttp``) dont les contrôles d'avant l'envoi refusent www.brvm.org."""
    import socket

    from brvm_alpha import net

    def resout(ip):
        return lambda host, port, *a: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    if refus == "AdresseInterdite":  # le nom se résout en adresse de boucle locale
        return net.ClientHttp(net.politique_par_defaut(), session=_SansReseau(), resolveur=resout("127.0.0.1"))
    # hôte hors de la liste blanche du client (la session, elle, le permet)
    return net.ClientHttp(net.Politique(hotes=frozenset({"brvm.org"})), session=_SansReseau(),
                          resolveur=resout("52.1.1.1"))


@pytest.mark.parametrize("refus, motif", [("AdresseInterdite", "adresse interdite"),
                                          ("HoteNonAutorise", "hors de la liste blanche")])
def test_a_request_refused_before_sending_reserves_no_politeness_slot(tmp_path, refus, motif):
    """Refus avant l'envoi (liste blanche, adresse résolue : contrôles faits AVANT la réservation) : aucune attente,
    ``politeness.json`` inchangé octet pour octet, rien de compté ; le lancement suivant n'attend que le reste du
    délai de la vraie requête précédente. Avant : le créneau était réservé et attendu, puis le refus découvert."""
    from brvm_alpha import net
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    h = _Horloge()
    _session(cache, lambda u, hd, t: _R(404 if u.endswith("robots.txt") else 200, b"%PDF-1.4 x", None, u), h).get(
        "https://www.brvm.org/sites/default/files/boc_20261120.pdf")  # vraie requête d'un lancement précédent
    avant = (cache / rs.POLITENESS_STATE).read_bytes()
    fichiers = sorted(p.name for p in cache.iterdir())
    h2 = _Horloge(h.t + 3.0)  # 3 s après la fin de cette requête
    sess = _session(cache, net.transport_http(client=_client_refusant(refus)), h2)
    with pytest.raises(rs.PolicyRefused, match=motif):
        sess.get(URL_BOC)
    assert h2.attentes == []  # avant : 7 s d'attente (reste du délai), puis le refus
    assert sess.n_requests == 0 and sess.stop_kind == "politique"
    assert (cache / rs.POLITENESS_STATE).read_bytes() == avant  # rien réservé
    assert sorted(p.name for p in cache.iterdir()) == fichiers  # pas même un verrou d'envoi
    assert _attente_avant_premier_envoi(cache, h.t + 3.5) == pytest.approx(6.5)  # 10 s après la vraie requête


def test_the_standalone_fetcher_checks_the_address_before_waiting_its_turn():
    from brvm_alpha.data import boc_download as bd

    attentes: list[float] = []
    f = bd.PoliteFetcher(sleep=attentes.append, clock=lambda: 0.0)
    f._client = _client_refusant("AdresseInterdite")
    f._last = 0.0  # une requête vient de finir : avant, 10 s d'attente puis le refus
    with pytest.raises(bd.DownloadStopped, match="adresse interdite") as ei:
        f(URL_BOC)
    assert ei.value.raison == "politique" and attentes == [] and f.n_requests == 0


def test_a_request_refused_only_at_connection_keeps_its_reservation(tmp_path):
    """Refus constaté seulement à la connexion (adresse réellement jointe, ``net._controler_pair``) : rien n'est
    compté, la session s'arrête (« politique »), et sa réservation **reste** (prudent : une attente de plus au
    lancement suivant). Avant : elle était retirée, et pouvait remettre une réservation plus ancienne."""
    from brvm_alpha import net
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    h = _Horloge()

    def connexion_refusee(url, headers, timeout):
        raise net.AdresseInterdite("connexion vers une adresse interdite (127.0.0.1) : aucune requête n'est envoyée.")

    sess = _session(cache, connexion_refusee, h)
    with pytest.raises(rs.PolicyRefused, match="adresse interdite"):
        sess.get(URL_BOC)
    assert sess.n_requests == 0 and sess.stop_kind == "politique" and h.attentes == []
    entry = _etat_politesse(cache)["hosts"]["www.brvm.org"]
    assert entry["session"] == sess.session_id and rs.to_utc(entry["last"]) == h.now()  # créneau gardé
    assert "fin" not in entry and "envoi" not in entry  # aucune vraie requête ; marque « envoi en cours » retirée
    assert _attente_avant_premier_envoi(cache, h.t + 2.0) == pytest.approx(8.0)  # 10 s après ce créneau
    assert not hasattr(rs.PoliteSession, "_annuler_reservation")


def test_a_request_that_leaves_still_reserves_its_slot_and_other_sessions_keep_theirs(tmp_path):
    """Vraie requête : créneau réservé, fin notée ; la suivante part 10 s après sa FIN, même longue. La fin d'une
    requête est notée même si une autre session a réservé plus tard pendant cette requête, et cette réservation reste
    à son nom (jamais remplacée par une date plus ancienne)."""
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    h = _Horloge()

    def lente(url, headers, timeout):
        h.t += 6.0  # requête de 6 s
        return _R(404 if url.endswith("robots.txt") else 200, b"%PDF-1.4 x", None, url)

    sess = _session(cache, lente, h)
    sess.get(URL_BOC)  # robots.txt (6 s), puis le PDF 10 s après la FIN de robots.txt
    assert h.attentes == [pytest.approx(10.0)]
    entry = _etat_politesse(cache)["hosts"]["www.brvm.org"]
    assert entry["session"] == entry["fin_session"] == sess.session_id and "envoi" not in entry
    assert rs.to_utc(entry["last"]) == rs.to_utc(entry["fin"]) == h.now()
    assert _attente_avant_premier_envoi(cache, h.t + 1.0) == pytest.approx(9.0)  # 10 s après la fin
    # X part, Y réserve pendant la requête de X (créneau = début de X + 10 s), X finit 6 s après son départ.
    url = "https://www.brvm.org/fr/page"
    t = [0.0]

    def now():
        return _NOW + dt.timedelta(seconds=t[0])

    def mk():
        return rs.PoliteSession(transport=lente, clock=lambda: t[0], sleep=lambda s: None, now=now, cache_dir=cache,
                                log_path=tmp_path / "fetch_log.jsonl")

    t[0] = 100.0
    x, y = mk(), mk()
    x._wait_turn(url)
    t[0] += 1.0
    y._wait_turn(url)
    t[0] += 5.0
    x._record_done("www.brvm.org")
    entry = _etat_politesse(cache)["hosts"]["www.brvm.org"]
    assert entry["session"] == y.session_id and rs.to_utc(entry["last"]) == _NOW + dt.timedelta(seconds=110)
    assert entry["fin_session"] == x.session_id and rs.to_utc(entry["fin"]) == _NOW + dt.timedelta(seconds=106)
    assert rs.STOP_STATUSES >= {403, 429}  # arrêt au premier 403/429 : inchangé


def _sessions_temps_reel(tmp_path, delai):
    """Sessions en temps réel (fils), délai ``delai`` vers exemple.test, état partagé ; horloge commune monotone."""
    from brvm_alpha.notes import research as rs

    base, t0 = _NOW, time.monotonic()
    cache = tmp_path / "cache"
    cache.mkdir(exist_ok=True)

    def now():
        return base + dt.timedelta(seconds=time.monotonic() - t0)

    def mk(transport, attentes=None):
        def sleep(s):
            if attentes is not None:
                attentes.append(float(s))
            time.sleep(s)

        return rs.PoliteSession(transport=transport, cache_dir=cache, log_path=tmp_path / "fetch_log.jsonl",
                                delay_s=delai, max_retries=1, hosts=("exemple.test",), now=now, sleep=sleep)

    return mk, (lambda: time.monotonic() - t0)


@pytest.mark.parametrize("cas", ["refus_a_la_connexion", "refus_avant_envoi", "vraie_requete"])
def test_three_sessions_never_send_less_than_the_delay_after_the_end_of_another_request(tmp_path, cas):
    """Constat du contrôle (p6_trois.py, délai 10 s ramené à 1 s) : X envoie une requête longue ; pendant ce temps Y
    réserve le créneau suivant puis est refusée (ou envoie une vraie requête) ; Z arrive ensuite. Avant : Z partait
    4 s après la FIN de X (la réservation de Y, retirée, remettait celle de X datée de son début), et une vraie
    requête de Y partait pendant celle de X quand X durait plus que le délai."""
    import threading

    from brvm_alpha import net
    from brvm_alpha.notes import research as rs

    D = 1.0
    longue = 1.5 if cas == "vraie_requete" else 0.6  # plus longue que le délai : Y attend la fin de X
    mk, T = _sessions_temps_reel(tmp_path, D)
    ev: dict[str, float] = {}
    attentes_y: list[float] = []

    def tr_x(url, h, timeout):
        ev["X envoi"] = T()
        time.sleep(longue)
        ev["X fin"] = T()
        return _R(404, b"", None, url)

    def tr_y(url, h, timeout):
        ev["Y envoi"] = T()
        if cas == "refus_a_la_connexion":
            raise net.AdresseInterdite("connexion vers une adresse interdite (127.0.0.1)")
        time.sleep(0.1)
        ev["Y fin"] = T()
        return _R(404, b"", None, url)

    def avant_envoi(url):
        ev["Y refus avant l'envoi"] = T()
        raise net.AdresseInterdite("exemple.test se résout en adresse interdite (127.0.0.1)")

    if cas == "refus_avant_envoi":
        tr_y.controle_avant_envoi = avant_envoi

    def tr_z(url, h, timeout):
        ev["Z envoi"] = T()
        return _R(404, b"", None, url)

    def lancer(transport, attentes=None):
        try:
            mk(transport, attentes)._network_get("https://exemple.test/doc.pdf", {}, nature="pdf")
        except rs.PolicyRefused:
            pass

    x = threading.Thread(target=lancer, args=(tr_x,))
    x.start()
    time.sleep(0.1)
    y = threading.Thread(target=lancer, args=(tr_y, attentes_y))
    y.start()
    y.join()
    x.join()
    lancer(tr_z)
    marge = 2e-3  # dates notées à la microseconde
    assert ev["Z envoi"] - ev["X fin"] >= D - marge, ev  # avant : 0,4 s (soit 4 s pour un délai de 10 s)
    if cas == "refus_avant_envoi":
        assert "Y envoi" not in ev and attentes_y == []  # refus sans réservation ni attente
        assert ev["Y refus avant l'envoi"] < ev["X fin"]
    else:
        assert ev["Y envoi"] - ev["X fin"] >= D - marge, ev  # avant (vraie requête) : partie pendant celle de X
    if cas == "refus_a_la_connexion":  # réservation de Y gardée : Z part un délai après elle
        assert ev["Z envoi"] - ev["X envoi"] >= 2 * D - marge, ev
    if cas == "vraie_requete":
        assert ev["Z envoi"] - ev["Y fin"] >= D - marge, ev


def test_two_sessions_alternating_real_requests_and_refusals_never_send_within_the_delay_of_an_end(tmp_path):
    """Deux suites de lancements simultanées (temps réel, délai 0,5 s) : vraies requêtes (dont une plus longue que le
    délai), refus avant l'envoi, refus à la connexion. Aucune requête ne part moins d'un délai après la FIN d'une vraie
    requête, deux requêtes ne sont jamais en cours ensemble, et un refus avant l'envoi n'attend rien."""
    import threading

    from brvm_alpha import net
    from brvm_alpha.notes import research as rs

    D = 0.5
    mk, T = _sessions_temps_reel(tmp_path, D)
    envois: list[tuple[float, float, str]] = []  # (début, fin, nature) de chaque appel du transport
    garde = threading.Lock()
    attentes_refus: list[list[float]] = []

    def transport(duree, nature):
        def tr(url, h, timeout):
            debut = T()
            if nature == "connexion":
                with garde:
                    envois.append((debut, T(), nature))
                raise net.AdresseInterdite("connexion vers une adresse interdite (127.0.0.1)")
            time.sleep(duree)
            with garde:
                envois.append((debut, T(), nature))
            return _R(404, b"", None, url)

        if nature == "avant_envoi":
            def refus(url):
                raise net.AdresseInterdite("exemple.test se résout en adresse interdite (127.0.0.1)")

            tr.controle_avant_envoi = refus
        return tr

    def suite(lancements):
        for i, (duree, nature) in enumerate(lancements):
            attentes: list[float] = []
            if nature == "avant_envoi":
                attentes_refus.append(attentes)
            try:
                mk(transport(duree, nature), attentes)._network_get(f"https://exemple.test/doc{i}.pdf", {},
                                                                    nature="pdf")
            except rs.PolicyRefused:
                pass

    a = threading.Thread(target=suite, args=([(0.2, "vraie"), (0.9, "vraie"), (0.1, "vraie")],))
    b = threading.Thread(target=suite, args=([(0.0, "avant_envoi"), (0.0, "connexion"), (0.3, "vraie"),
                                              (0.0, "avant_envoi")],))
    a.start()
    time.sleep(0.05)
    b.start()
    a.join()
    b.join()
    envois.sort()
    vraies = [e for e in envois if e[2] == "vraie"]
    assert len(vraies) == 4 and len(envois) == 5, envois
    marge = 2e-3
    for debut, _fin, _n in envois:  # aucun envoi moins d'un délai après la fin d'une vraie requête précédente
        fins = [f for d, f, n in vraies if d < debut]
        assert not fins or debut - max(fins) >= D - marge, envois
    for (d1, f1, _), (d2, _f2, _) in zip(vraies, vraies[1:]):  # jamais deux vraies requêtes ensemble
        assert d2 >= f1 + D - marge, vraies
    assert attentes_refus and all(w == [] for w in attentes_refus)  # refus avant l'envoi : aucune attente



def test_a_session_waiting_its_turn_does_not_send_after_a_403_received_by_another_session(tmp_path):
    """Arrêt au premier 403/429, toutes sessions confondues : B attend son tour pendant la requête de A, que le site
    refuse (403) ; le blocage est noté avant que B puisse partir, et B s'arrête sans rien envoyer. Avant : B partait à
    son créneau, pendant la requête de A, puis après le 403."""
    import threading

    from brvm_alpha.notes import research as rs

    D = 0.5
    mk, T = _sessions_temps_reel(tmp_path, D)
    ev: dict[str, float] = {}
    issue: dict[str, str] = {}

    def tr_a(url, h, timeout):
        ev["A envoi"] = T()
        time.sleep(0.8)
        ev["A fin"] = T()
        return _R(403, b"refus", None, url)

    def tr_b(url, h, timeout):
        ev["B envoi"] = T()
        return _R(404, b"", None, url)

    def lancer(nom, transport):
        try:
            mk(transport)._network_get("https://exemple.test/doc.pdf", {}, nature="pdf")
        except rs.AccessBlocked as exc:
            issue[nom] = type(exc).__name__

    a = threading.Thread(target=lancer, args=("A", tr_a))
    a.start()
    time.sleep(0.1)
    lancer("B", tr_b)
    a.join()
    assert issue == {"A": "AccessBlocked", "B": "AccessBlocked"} and "B envoi" not in ev, ev
    assert rs.blocked_hosts(tmp_path / "cache")["exemple.test"]["status"] == 403


# Contrôle de 1a1fd28 : requête interrompue (TERM du lanceur, Ctrl+C, SIGXCPU, KILL), verrou d'envoi impossible,
# date illisible dans politeness.json, 403 vu par une session qui attend.


@pytest.mark.parametrize("interruption", [erreurs.ArretDemande, KeyboardInterrupt, erreurs.TempsCalculDepasse,
                                          MemoryError, erreurs.VerrouOccupe, erreurs.ConfigurationError])
def test_an_interrupted_request_still_notes_its_end_and_the_next_session_waits_the_delay_after_it(tmp_path,
                                                                                                  interruption):
    """Requête interrompue pendant l'envoi (TERM du lanceur : ``ArretDemande`` ; Ctrl+C ; ``SIGXCPU`` ;
    ``MemoryError`` ; erreur venue du transport) : la fin est notée quand même, la marque « envoi en cours » est
    retirée, et la session suivante part 10 s après l'interruption, plus la marge de coupure de 2 s (la requête n'a pas
    fini normalement : ``fin_coupee``). Avant 1a1fd28 : aucune fin notée, la session qui attendait partait 0,06 s après
    le TERM (pendant que le site servait encore la réponse) ; avant la marge : 10 s après l'interruption."""
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    h = _Horloge()

    def coupee(url, headers, timeout):
        if url.endswith("robots.txt"):
            return _R(404, b"", None, url)
        h.t += 4.0  # 4 s de réponse, puis l'interruption
        raise interruption("interrompue pendant la requête")

    sess = _session(cache, coupee, h)
    with pytest.raises(interruption):
        sess.get(URL_BOC)
    entry = _etat_politesse(cache)["hosts"]["www.brvm.org"]
    assert entry["fin_session"] == sess.session_id and rs.to_utc(entry["fin"]) == h.now()  # instant réel de la coupure
    assert "envoi" not in entry and entry["fin_coupee"] is True
    # 1 s après la coupure : 11 s d'attente, soit 12 s après la coupure (avant la marge : 9 s ; avant 1a1fd28 : 5 s)
    assert _attente_avant_premier_envoi(cache, h.t + 1.0) == pytest.approx(10.0 + rs.MARGE_COUPURE_S - 1.0)


@pytest.mark.parametrize("fin", ["reponse_200", "erreur_http_404", "erreur_http_503", "erreur_transport",
                                 "delai_depasse", "connexion_impossible"])
def test_only_a_request_that_did_not_end_normally_costs_the_cut_margin(tmp_path, fin):
    """Marge de coupure : une requête terminée normalement (réponse lue en entier, ou erreur HTTP reçue) garde
    exactement un délai (10 s) ; une requête coupée par le transport (erreur, délai dépassé, connexion impossible)
    compte comme finie 2 s après sa coupure : la suivante part 12 s après. ``fin`` reste l'instant réel."""
    from brvm_alpha import net
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    h = _Horloge()

    def tr(url, headers, timeout):
        if url.endswith("robots.txt"):
            return _R(404, b"", None, url)
        h.t += 3.0  # 3 s de requête
        if fin == "erreur_transport":
            raise OSError("connexion remise à zéro par le pair")
        if fin == "delai_depasse":
            raise net.DelaiDepasse("délai total dépassé")
        if fin == "connexion_impossible":
            raise net.ConnexionImpossible("connexion impossible")
        return _R({"reponse_200": 200, "erreur_http_404": 404, "erreur_http_503": 503}[fin], b"%PDF-1.4 x", None, url)

    sess = rs.PoliteSession(transport=tr, clock=h, sleep=h.sleep, now=h.now, cache_dir=cache,
                            log_path=tmp_path / "fetch_log.jsonl", delay_s=10.0, max_retries=1)
    try:
        sess.get(URL_BOC)
    except (rs.ResearchError, rs.ServerUnavailable):
        pass
    entry = _etat_politesse(cache)["hosts"]["www.brvm.org"]
    normale = fin.startswith(("reponse", "erreur_http"))
    assert rs.to_utc(entry["fin"]) == h.now() and ("fin_coupee" in entry) is (not normale), entry
    attendu = 10.0 if normale else 10.0 + rs.MARGE_COUPURE_S
    copie = tmp_path / "copie" / "cache"  # chaque sonde écrit sa propre requête : une copie de l'état pour la seconde
    shutil.copytree(cache, copie)
    assert _attente_avant_premier_envoi(cache, h.t) == pytest.approx(attendu)
    assert _attente_avant_premier_envoi(copie, h.t + 4.0) == pytest.approx(attendu - 4.0)


def test_the_cut_margin_also_holds_for_the_same_session_and_a_normal_end_clears_it(tmp_path):
    """Même session : après une requête coupée (erreur du transport), son nouvel essai part 12 s après la coupure
    (attente d'essai comprise) ; une fin normale suivante retire ``fin_coupee`` : de nouveau 10 s."""
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    h = _Horloge()
    envois: list[float] = []
    coupure: list[float] = []

    def tr(url, headers, timeout):
        if url.endswith("robots.txt"):
            return _R(404, b"", None, url)
        envois.append(h.t)
        if len(envois) == 1:
            h.t += 1.0
            coupure.append(h.t)
            raise OSError("connexion coupée")
        return _R(200, b"%PDF-1.4 x", None, url)

    sess = rs.PoliteSession(transport=tr, clock=h, sleep=h.sleep, now=h.now, cache_dir=cache,
                            log_path=tmp_path / "fetch_log.jsonl", delay_s=10.0, max_retries=2, backoff_s=1.0)
    sess.get(URL_BOC)
    assert len(envois) == 2 and envois[1] - coupure[0] == pytest.approx(10.0 + rs.MARGE_COUPURE_S)
    entry = _etat_politesse(cache)["hosts"]["www.brvm.org"]
    assert "fin_coupee" not in entry and rs.to_utc(entry["fin"]) == h.now()
    assert _attente_avant_premier_envoi(cache, h.t) == pytest.approx(10.0)


@pytest.mark.parametrize("etat", ["marque_orpheline", "fin_illisible_coupee", "fin_future_coupee",
                                  "fin_coupee_illisible"])
def test_an_orphan_mark_or_a_cut_end_costs_the_delay_plus_the_margin_never_more(tmp_path, etat):
    """Marque « envoi en cours » d'une autre session restée sans fin (KILL) : délai plus marge (12 s) depuis la prise
    du verrou ; fin coupée illisible ou datée dans le futur : 12 s, jamais plus ; valeur illisible de ``fin_coupee`` :
    la marge compte (prudent)."""
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    entry = {"orphelin": {"envoi": {"debut": (_NOW - dt.timedelta(seconds=30)).isoformat(), "session": "tuée"}},
             "fin_illisible_coupee": {"fin": "NaT", "fin_session": "autre", "fin_coupee": True},
             "fin_future_coupee": {"fin": (_NOW + dt.timedelta(days=3)).isoformat(), "fin_session": "autre",
                                   "fin_coupee": True},
             "fin_coupee_illisible": {"fin": _NOW.isoformat(), "fin_session": "autre", "fin_coupee": "oui ?"},
             }[etat.replace("marque_orpheline", "orphelin")]
    (cache / rs.POLITENESS_STATE).write_text(json.dumps({"hosts": {"www.brvm.org": entry}}), encoding="utf-8")
    assert _attente_avant_premier_envoi(cache, 1000.0) == pytest.approx(10.0 + rs.MARGE_COUPURE_S)
    if etat == "marque_orpheline":
        journal = [json.loads(x) for x in (tmp_path / "fetch_log.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [e["wait_s"] for e in journal if e.get("envoi_sans_fin")] == [10.0 + rs.MARGE_COUPURE_S]


_ENVOI_INTERROMPU = r'''
import signal, sys, time
from pathlib import Path
from brvm_alpha import erreurs
from brvm_alpha.notes import research as rs

cache, journal, marque, delai = sys.argv[1], sys.argv[2], Path(sys.argv[3]), float(sys.argv[4])


def term(signum, frame):  # comme la ligne de commande : TERM devient ArretDemande (code 130)
    raise erreurs.ArretDemande("arrêt demandé (signal TERM)")


signal.signal(signal.SIGTERM, term)


def lente(url, headers, timeout):
    marque.write_text(repr(time.time()))
    time.sleep(60)


s = rs.PoliteSession(transport=lente, cache_dir=cache, log_path=journal, delay_s=delai, max_retries=1,
                     hosts=("exemple.test",))
try:
    s._network_get("https://exemple.test/k.pdf", {}, nature="pdf")
except KeyboardInterrupt:
    sys.exit(130)
'''


@pytest.mark.parametrize("sig", ["SIGKILL", "SIGTERM"])
@pytest.mark.parametrize("moment", ["B_attend_le_verrou", "avant_le_creneau_de_B"])
def test_a_session_killed_during_its_request_never_lets_the_next_one_leave_within_the_delay(tmp_path, sig, moment):
    """Deux vrais processus (constat majeur du contrôle de 1a1fd28) : K envoie une requête longue ; B, lancée 0,2 s
    après, attend son tour ; K est tué (KILL) ou reçoit TERM pendant sa requête, alors que B attend le verrou
    d'envoi, ou avant le créneau de B. B ne part jamais moins d'un délai plus la marge de coupure (2 s) après le
    signal : TERM note la fin, requête coupée ; après KILL, la marque « envoi en cours » restée sans fin coûte un délai
    entier plus la marge. Avant : B partait 0,03 s après le signal (B attendait le verrou), ou à son créneau, 0,6 s
    après la coupure ; avant la marge, un délai après le signal."""
    import threading

    from brvm_alpha.notes import research as rs

    D = 1.0
    cache = tmp_path / "cache"
    cache.mkdir()
    marque = tmp_path / "envoi_K"
    k = subprocess.Popen([sys.executable, "-B", "-c", _ENVOI_INTERROMPU, str(cache), str(tmp_path / "k.jsonl"),
                          str(marque), str(D)], env=_env_sous_processus(), cwd=str(ROOT))
    ev: dict[str, float] = {}
    try:
        fin_attente = time.time() + 60
        while not (marque.exists() and marque.read_text()) and time.time() < fin_attente and k.poll() is None:
            time.sleep(0.01)
        t_k = float(marque.read_text())
        assert "envoi" in _etat_politesse(cache)["hosts"]["exemple.test"]  # marque écrite avant l'envoi
        coupure = t_k + (2.0 if moment == "B_attend_le_verrou" else 0.4)

        def couper():
            while time.time() < coupure:
                time.sleep(0.002)
            ev["signal"] = time.time()
            k.send_signal(getattr(signal, sig))

        def tr_b(url, h, timeout):
            ev["B envoi"] = time.time()
            return _R(404, b"", None, url)

        th = threading.Thread(target=couper)
        th.start()
        while time.time() < t_k + 0.2:
            time.sleep(0.002)
        b = rs.PoliteSession(transport=tr_b, cache_dir=cache, log_path=tmp_path / "b.jsonl", delay_s=D,
                             max_retries=1, hosts=("exemple.test",))
        b._network_get("https://exemple.test/b.pdf", {}, nature="pdf")
        th.join()
        k.wait(timeout=30)
    finally:
        if k.poll() is None:
            k.kill()
            k.wait(timeout=10)
    assert k.returncode == (-9 if sig == "SIGKILL" else 130)
    # délai plus la marge de coupure (avant la marge : D ; avant 1a1fd28 : 0,03 s au verrou, 0,6 s au créneau), sans
    # attente de trop
    assert D + rs.MARGE_COUPURE_S - 2e-3 <= ev["B envoi"] - ev["signal"] <= D + rs.MARGE_COUPURE_S + 1.5, ev
    entry = _etat_politesse(cache)["hosts"]["exemple.test"]
    assert "envoi" not in entry and entry["fin_session"] == b.session_id  # marque retirée par la fin de B
    journal = [json.loads(x) for x in (tmp_path / "b.jsonl").read_text(encoding="utf-8").splitlines()]
    sans_fin = [e for e in journal if e.get("event") == "attente" and e.get("envoi_sans_fin")]
    assert bool(sans_fin) == (sig == "SIGKILL")  # KILL : un délai entier, faute de fin notée


@pytest.mark.parametrize("panne", ["verrou", "marque"])
def test_no_request_leaves_when_the_send_lock_or_mark_cannot_be_written_while_the_state_can(tmp_path, monkeypatch,
                                                                                            panne):
    """Verrou d'envoi impossible à prendre (un dossier à sa place ; fichier d'un autre utilisateur) ou marque
    « envoi en cours » impossible à écrire, alors que ``politeness.json`` s'écrit : rien ne part (code 8), et c'est
    noté dans ``fetch_log.jsonl``. Avant : la requête partait quand même, seul un avertissement le disait, et deux
    requêtes pouvaient se chevaucher."""
    import errno

    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    if panne == "verrou":
        (cache / "politeness.envoi.www.brvm.org.lock").mkdir()
    else:
        orig = rs.PoliteSession._state_update

        def update(self, host, fn, *a, **k):
            if getattr(fn, "__name__", "") == "marque":
                raise OSError(errno.EIO, "écriture impossible")
            return orig(self, host, fn, *a, **k)

        monkeypatch.setattr(rs.PoliteSession, "_state_update", update)
    envois: list[str] = []
    h = _Horloge()

    def ok(url, headers, timeout):
        envois.append(url)
        return _R(404, b"", None, url)

    sess = _session(cache, ok, h)
    with pytest.raises(rs.PolitesseNonGarantie, match="aucune requête n'est envoyée"):
        sess.get(URL_BOC)
    assert envois == [] and sess.n_requests == 0
    assert erreurs.code_retour(rs.PolitesseNonGarantie("x")) == 8
    journal = [json.loads(x) for x in (tmp_path / "fetch_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in journal if e["event"] == "politesse_non_garantie"] == ["politesse_non_garantie"]


@pytest.mark.parametrize("cle", ["fin", "last"])
@pytest.mark.parametrize("valeur", ["NaT", "nan", "pas une date", 5])
def test_an_unreadable_date_in_the_politeness_state_costs_one_delay_never_an_internal_error(tmp_path, cle, valeur):
    """Date illisible notée par une autre session (``"NaT"``, ``"nan"``, texte, nombre) : un délai d'attente, jamais
    une erreur interne, jamais aucune attente. Avant : ``fin`` à ``"NaT"`` ou ``"nan"`` donnait le code 7
    (« cannot convert float NaN to integer ») ; ``last`` illisible était ignorée (aucune attente)."""
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    entry = {cle: valeur, ("fin_session" if cle == "fin" else "session"): "autre session"}
    (cache / rs.POLITENESS_STATE).write_text(json.dumps({"hosts": {"www.brvm.org": entry}}), encoding="utf-8")
    assert _attente_avant_premier_envoi(cache, 1000.0) == pytest.approx(10.0)


@pytest.mark.parametrize("moment", ["B_attend_le_verrou", "creneau_de_B_apres_le_403"])
def test_a_403_of_another_session_stops_a_waiting_session_as_soon_as_it_takes_the_send_lock(tmp_path, moment):
    """403 reçu par A pendant que B attend : B s'arrête dès qu'elle prend le verrou d'envoi, sans attendre encore un
    délai après la fin de A (rien ne part, comme avant ; seule l'attente inutile disparaît). Avant : jusqu'à un
    délai entier de plus."""
    import threading

    from brvm_alpha.notes import research as rs

    D = 1.0
    mk, T = _sessions_temps_reel(tmp_path, D)
    ev: dict[str, float] = {}
    duree_a = 1.5 if moment == "B_attend_le_verrou" else 0.6

    def tr_a(url, h, timeout):
        time.sleep(duree_a)
        ev["A fin"] = T()
        return _R(403, b"refus", None, url)

    def tr_b(url, h, timeout):
        ev["B envoi"] = T()
        return _R(404, b"", None, url)

    issue: dict[str, str] = {}

    def lancer(nom, transport, url):
        try:
            mk(transport)._network_get(url, {}, nature="pdf")
        except rs.AccessBlocked as exc:
            ev[f"{nom} refus"] = T()
            issue[nom] = type(exc).__name__

    a = threading.Thread(target=lancer, args=("A", tr_a, "https://exemple.test/a.pdf"))
    a.start()
    time.sleep(0.1)
    lancer("B", tr_b, "https://exemple.test/b.pdf")
    a.join()
    assert issue == {"A": "AccessBlocked", "B": "AccessBlocked"} and "B envoi" not in ev, ev
    if moment == "B_attend_le_verrou":
        assert ev["B refus"] - ev["A fin"] < 0.3, ev  # avant : un délai de plus (1,0 s)
    else:  # créneau de B à 1,0 s, A finie à 0,6 s : refus au créneau (avant : 1,6 s)
        assert ev["B refus"] - ev["A fin"] < 0.7, ev


def test_deployment_doc_lists_the_send_lock_of_every_online_command_and_its_limits():
    """DEPLOIEMENT.md § A.9 : le verrou d'envoi figure pour toutes les commandes qui envoient des requêtes
    (``notes lire`` en ligne et ``live`` compris) ; § A.14 : limites du verrou d'envoi (une seule machine)."""
    doc = (ROOT / "docs" / "DEPLOIEMENT.md").read_text(encoding="utf-8")
    a9 = doc[doc.index("### A.9 "):doc.index("### A.10 ")]
    for debut in ("| `update --sans-panel", "| `notes research [--pdf", "| `notes lire", "| `live"):
        lignes = [x for x in a9.splitlines() if x.startswith(debut)]
        assert lignes and "politeness.envoi.www.brvm.org.lock" in lignes[0] and "politeness.json.lock" in lignes[0], \
            debut
    a14 = doc[doc.index("### A.14 "):doc.index("### A.15 ")]
    assert "une seule machine" in a14 and "disque réseau" in a14
    # marge de coupure : décrite, chiffrée (§ A.14) et listée dans les changements (§ A.15)
    from brvm_alpha.notes import research as rs

    a14p = " ".join(a14.split()).replace("**", "")
    assert rs.MARGE_COUPURE_S == 2.0 and "marge de coupure de 2 s" in a14p and "un délai entier plus 2 s" in a14p
    assert "12,02 à 12,03 s après le signal" in a14p and "Fin normale : 10,02 s" in a14p
    a15 = " ".join(doc[doc.index("### A.15 "):doc.index("### A.16 ")].split()).replace("**", "")
    assert "marge de coupure" in a15 and "fin_coupee" in a15 and "garde exactement 10 s" in a15


# ---------------------------------------------------------------------------
# P7 : recommend sur un tout petit panel
# ---------------------------------------------------------------------------


def test_recommend_on_a_tiny_panel_gives_the_order_with_the_index_evaluation_not_available(tiny, tmp_path, capsys):
    code, out, err = run_cli(capsys, "recommend", "--capital", "10000000", "--tirages", "50", "--panel-dir",
                             str(tiny / "panel"), "--racine", str(tmp_path), "--format", "json")
    d = one_json(out)
    assert code == 0 and d["ok"] is True, (d.get("message"), err[-800:])  # avant : 7, TypeError float(None)
    rows = d["declencheurs"]["indices"]
    assert rows and all(r["score"] is None for r in rows) and all("n.d." in r["lecture"] for r in rows)
    assert d["historique_complet"] is False
    assert any(str(a).startswith("HISTORIQUE INCOMPLET") for a in d["avertissements"])
