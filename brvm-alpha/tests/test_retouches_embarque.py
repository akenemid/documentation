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
  ``politeness.json`` : 10 s d'attente de trop au lancement suivant ;
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
                                                                                           capsys):
    data, _reports = embarque
    dehors = tmp_path / "ailleurs"
    dehors.mkdir()
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
    ]
    for argv in refus:
        code, out, _ = run_cli(capsys, *argv, "--format", "json")
        d = one_json(out)
        assert code == 2 and d["erreur"] == "saisie_invalide" and d["message"].startswith("refusé"), (argv, d)
    assert list(dehors.iterdir()) == []  # rien n'a été créé dehors
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
# P6 : aucune réservation de politesse pour une requête refusée avant l'envoi
# ---------------------------------------------------------------------------

_NOW = dt.datetime(2026, 11, 23, 3, 40, tzinfo=dt.timezone.utc)


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


@pytest.mark.parametrize("refus", ["AdresseInterdite", "HoteNonAutorise"])
def test_a_request_refused_before_sending_reserves_no_politeness_slot(tmp_path, refus):
    from brvm_alpha import net
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()

    def transport(url, headers, timeout):
        raise getattr(net, refus)(f"www.brvm.org refusé avant l'envoi : {url}")

    sess = _session(cache, transport, _Horloge())
    with pytest.raises(rs.PolicyRefused):
        sess.get("https://www.brvm.org/sites/default/files/boc_20261123.pdf")
    assert sess.n_requests == 0 and sess.stop_kind == "politique"
    hosts = _etat_politesse(cache).get("hosts", {})
    assert not any("last" in e for e in hosts.values()), hosts  # avant : « last » noté, aucune requête partie
    assert _attente_avant_premier_envoi(cache, 1000.5) == 0.0  # avant : 10 s d'attente au lancement suivant


def test_a_request_that_leaves_still_reserves_its_slot_and_other_sessions_keep_theirs(tmp_path):
    from brvm_alpha.notes import research as rs

    cache = tmp_path / "cache"
    cache.mkdir()
    h = _Horloge()
    sess = _session(cache, lambda u, hd, t: _R(404 if u.endswith("robots.txt") else 200, b"%PDF-1.4 x", None, u), h)
    sess.get("https://www.brvm.org/sites/default/files/boc_20261123.pdf")
    entry = _etat_politesse(cache)["hosts"]["www.brvm.org"]
    assert entry["last"] and entry["session"] == sess.session_id  # règle inchangée : 10 s entre deux requêtes
    assert _attente_avant_premier_envoi(cache, h.t) >= 10.0 - 1e-6
    # une réservation posée depuis par une autre session n'est jamais retirée
    before = _etat_politesse(cache)
    sess._annuler_reservation({"hote": "www.brvm.org", "avant": {}, "posee": {"last": "x", "session": "y",
                                                                             "reserved_at": "z"}})
    assert _etat_politesse(cache) == before
    assert rs.STOP_STATUSES >= {403, 429}  # arrêt au premier 403/429 : inchangé


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
