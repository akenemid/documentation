"""Contrôle des retouches du moteur embarqué : constats rejoués sur bf68de2, puis corrigés.

Chaque essai échouait avant la correction :

- chemins : en mode embarqué, une option de chemin vide ou faite d'espaces (``--racine ' '``) désignait le dossier
  courant, hors de ``BRVM_ALPHA_DONNEES`` (code 0, journal créé ailleurs) ; ``recommend --sortie -`` écrivait dans le
  dossier courant ; désormais 2, ou le dossier des rapports ;
- ``notes add`` : un ``SIGXCPU`` (ou un TERM) reçu juste après l'écriture de la note donnait 8 « sans résultat
  partiel » alors que la note était au journal ; désormais 0, avec l'objet de la note ;
- un signal reçu pendant l'écriture de l'objet JSON coupait l'objet, puis un second objet suivait ;
- ``panel`` sans aucun bulletin (installation neuve) sortait en 7 « KeyError : file » ; désormais 1 ;
- ``BRVM_ALPHA_CPU_MIN`` négatif coupait le contrôle sans rien dire ; le message arrondissait la marge vers le haut
  (« 900,0 s de marge ; le moteur en demande au moins 900 s ») ;
- un outil de poppler fini restait jusqu'à 50 ms zombie avant d'être récolté (``Popen.wait``) ;
- un processus de travail du panel dont le serveur était déjà mort (moteur tué au démarrage du pool) restait vivant.

Hors ligne : dossiers temporaires, doublures, aucune requête vers l'extérieur. Le code 3 n'est jamais attendu.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import argparse
import fcntl
import io
import json
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

from brvm_alpha import cli, demarrage, erreurs, paths, pdf

ROOT = Path(__file__).resolve().parents[1]
BOC_FIX = ROOT / "tests" / "fixtures" / "notes" / "boc"
CODES_ADMIS = {0, 1, 2, 4, 5, 6, 7, 8, 130}
LINUX = sys.platform.startswith("linux")


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


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("BRVM_ALPHA_")}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(ROOT), "HTTPS_PROXY": "http://127.0.0.1:9",
                "HTTP_PROXY": "http://127.0.0.1:9"})
    env.update(extra)
    return env


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


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    """Sept BOC des fixtures et leur panel."""
    from brvm_alpha.data import store

    base = tmp_path_factory.mktemp("controle_retouches")
    (base / "boc_text").mkdir()
    for f in BOC_FIX.glob("boc_*.txt.gz"):
        shutil.copy(f, base / "boc_text" / f.name)
    store.build_panel(base / "boc_text", base / "panel", workers=1)
    return base


# ---------------------------------------------------------------------------
# Chemins vides ou faits d'espaces (mode embarqué)
# ---------------------------------------------------------------------------


def test_embedded_blank_path_options_are_refused_and_nothing_lands_in_the_current_folder(embarque, tmp_path, capsys,
                                                                                         monkeypatch):
    data, reports = embarque
    courant = tmp_path / "cwd_odoo"
    courant.mkdir()
    monkeypatch.chdir(courant)
    note = ["--cible", "SNTS", "--titre", "t", "--texte", "essai"]
    for argv in (["notes", "add", "--racine", " ", *note],  # avant : code 0, courant/' '/notes.jsonl
                 ["notes", "add", "--fichier", " ", "--cible", "SNTS", "--titre", "t"],
                 ["notes", "list", "--racine", "  "],
                 ["panel", "--panel-dir", " "],  # avant : code 0, panel complet écrit dans courant/' '
                 ["panel", "--boc-dir", "\t"],
                 ["update", "--simulation", "--boc-dir", " "],  # avant : 2581 jours « à chercher » dans courant/' '
                 ["recommend", "--capital", "10000000", "--sortie", " "],
                 ["recommend", "--capital", "10000000", "--portefeuille", " "],
                 ["report", "--capital", "10000000", "--sortie", ""]):
        code, out, _ = run_cli(capsys, *argv, "--format", "json")
        d = one_json(out)
        assert code == 2 and d["erreur"] == "saisie_invalide" and "vide" in d["message"], (argv, d)
    assert list(courant.iterdir()) == [] and list((data / "notes").iterdir()) == []
    assert sorted(p.name for p in data.iterdir()) == ["notes"] and list(reports.iterdir()) == []


def test_sortie_dash_is_stdout_only_for_notes_export(embarque, tmp_path, monkeypatch):
    _data, reports = embarque
    monkeypatch.chdir(tmp_path)

    def resoudre(**kw):
        args = argparse.Namespace(command=kw.pop("command"), **kw)
        cli._resolve_path_options(args)
        return args.sortie

    assert resoudre(command="notes", notes_cmd="export", sortie="-") == "-"  # sortie standard
    # recommend et report : « - » est un nom de fichier, dans les rapports (avant : écrit dans le dossier courant)
    assert resoudre(command="recommend", sortie="-") == str(reports / "-")
    assert resoudre(command="report", sortie=" - ") == str(reports / " - ")
    with pytest.raises(erreurs.SaisieInvalide):
        resoudre(command="notes", notes_cmd="export", sortie=" ")


def test_blank_path_options_are_unchanged_outside_embedded_mode(tmp_path, capsys, monkeypatch):
    assert not paths.est_embarque()
    monkeypatch.chdir(tmp_path)
    code, out, _ = run_cli(capsys, "notes", "add", "--racine", " ", "--cible", "SNTS", "--titre", "t", "--texte",
                           "hors mode embarqué", "--format", "json")
    assert code == 0 and json.loads(out)["cree"] is True and (tmp_path / " " / "notes.jsonl").is_file()


# ---------------------------------------------------------------------------
# Signal reçu après l'écriture de la note, ou pendant l'écriture de l'objet JSON
# ---------------------------------------------------------------------------

_SCRIPT_APRES_ECRITURE = r'''
import os, signal, sys
from brvm_alpha import demarrage
from brvm_alpha.notes import store

ecrire = store.NoteStore._append


def ecrire_puis_signal(self, rec):  # la ligne est au journal (fsync), puis le signal arrive
    ecrire(self, rec)
    os.kill(os.getpid(), getattr(signal, os.environ["SIG_APRES"]))


store.NoteStore._append = ecrire_puis_signal
sys.exit(demarrage.lancer(sys.argv[1:]))
'''


@pytest.mark.parametrize("sig", ["SIGXCPU", "SIGTERM"])
def test_a_signal_right_after_the_journal_write_gives_0_with_the_note(tmp_path, sig):
    script = tmp_path / "apres.py"
    script.write_text(_SCRIPT_APRES_ECRITURE, encoding="utf-8")
    racine = tmp_path / "notes"
    p = subprocess.run([sys.executable, "-B", str(script), "notes", "add", "--cible", "SNTS", "--titre", "Après",
                        "--texte", "Note écrite avant le signal", "--racine", str(racine), "--format", "json"],
                       env=_env(SIG_APRES=sig), capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    obj = json.loads(p.stdout)  # avant : 8 (ou 130), « arrêtée … sans résultat partiel », note pourtant au journal
    assert p.returncode == 0 and obj["ok"] is True and obj["cree"] is True, (p.returncode, p.stdout[-600:], p.stderr[-600:])
    lignes = [json.loads(x) for x in (racine / "notes.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [x["note_id"] for x in lignes] == [obj["note_id"]]
    assert f"signal {sig.replace('SIG', '') if sig == 'SIGTERM' else sig} reçu pendant l'écriture du résultat" in p.stderr
    # un nouvel envoi est reconnu comme doublon (code 0, deja_enregistree)
    p = subprocess.run([sys.executable, "-B", "-m", "brvm_alpha", "notes", "add", "--cible", "SNTS", "--titre", "Après",
                        "--texte", "Note écrite avant le signal", "--racine", str(racine), "--format", "json"],
                       env=_env(), capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    assert p.returncode == 0 and json.loads(p.stdout)["deja_enregistree"] is True


def test_term_while_waiting_for_the_journal_lock_still_stops_the_command(tmp_path):
    racine = tmp_path / "notes"
    racine.mkdir()
    with open(racine / "notes.jsonl.lock", "a+") as verrou:
        fcntl.flock(verrou.fileno(), fcntl.LOCK_EX)  # une autre écriture tient le journal
        p = subprocess.Popen([sys.executable, "-B", "-m", "brvm_alpha", "notes", "add", "--cible", "SNTS", "--titre",
                              "Attente", "--texte", "x", "--racine", str(racine), "--format", "json"],
                             env=_env(BRVM_ALPHA_ATTENTE_VERROU="60"), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, cwd=str(tmp_path))
        t0 = time.monotonic()
        attend = False
        while time.monotonic() - t0 < 60 and not attend and p.poll() is None:  # la commande attend le verrou
            try:
                fds = os.listdir(f"/proc/{p.pid}/fd")
                attend = any(os.readlink(f"/proc/{p.pid}/fd/{fd}").endswith("notes.jsonl.lock") for fd in fds)
            except OSError:
                pass
            time.sleep(0.02)
        assert attend, "la commande n'a pas ouvert le verrou du journal"
        time.sleep(0.3)
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=60)
        duree = time.monotonic() - t0
    obj = json.loads(out)
    assert p.returncode == 130 and obj["erreur"] == "interruption", (p.returncode, out, err[-600:])
    assert duree < 30 and not (racine / "notes.jsonl").exists()  # rien d'écrit, TERM non reporté pendant l'attente


class _FluxCoupe(io.StringIO):
    """Sortie standard dont l'écriture reçoit ``sig`` au milieu (comme un tube plein qui se vide lentement)."""

    def __init__(self, sig: int):
        super().__init__()
        self.sig, self.envoye = sig, False

    def write(self, s: str) -> int:
        if self.envoye or len(s) < 20:
            return super().write(s)
        self.envoye = True
        moitie = len(s) // 2
        super().write(s[:moitie])
        os.kill(os.getpid(), self.sig)
        time.sleep(0.01)  # le gestionnaire du signal passe ici
        super().write(s[moitie:])
        return len(s)


@pytest.mark.skipif(not hasattr(signal, "SIGXCPU"), reason="SIGXCPU : Unix seulement")
@pytest.mark.parametrize("sig", [signal.SIGTERM, getattr(signal, "SIGXCPU", 24)])
def test_a_signal_during_the_json_write_never_cuts_the_object(tmp_path, monkeypatch, sig):
    flux = _FluxCoupe(int(sig))
    monkeypatch.setattr(sys, "stdout", flux)
    code = demarrage.lancer(["notes", "list", "--racine", str(tmp_path), "--format", "json"])
    texte = flux.getvalue()
    assert flux.envoye
    obj = json.loads(texte)  # avant : objet coupé, puis un second objet (« interruption » ou « configuration »)
    assert code == 0 and obj["ok"] is True and obj["n"] == 0, texte[-400:]


def test_a_signal_after_the_json_object_keeps_the_code_of_the_object():
    demarrage.reinitialiser()
    st = cli._SortieJson(io.StringIO())
    tok = cli._SORTIE_JSON.set(st)
    try:
        cli.emit_json({"n": 1})
        assert cli._report_error(erreurs.ArretDemande("arrêt demandé"), st) == 0  # avant : 130 avec "ok": true
        assert cli._report_error(erreurs.TempsCalculDepasse("limite"), st) == 0  # avant : 8 avec "ok": true
        assert json.loads(st.out.getvalue())["ok"] is True  # un seul objet
        demarrage.reinitialiser()
        st2 = cli._SortieJson(io.StringIO())
        cli._SORTIE_JSON.set(st2)
        cli.emit_echec(erreurs.VERROU_OCCUPE, "refusé : verrou occupé")
        assert cli._report_error(erreurs.ArretDemande("arrêt demandé"), st2) == erreurs.VERROU_OCCUPE
    finally:
        cli._SORTIE_JSON.reset(tok)
        demarrage.reinitialiser()


def test_after_the_json_object_the_closing_engine_ignores_term():
    # Gestionnaires du processus des essais gardés puis rétablis : un SIGXCPU laissé ignoré ici serait hérité par les
    # sous-processus des essais suivants (une disposition « ignoré » traverse exec).
    avant = signal.getsignal(signal.SIGTERM)
    xcpu_avant = signal.getsignal(signal.SIGXCPU) if hasattr(signal, "SIGXCPU") else None
    try:
        demarrage.reinitialiser()
        demarrage.marquer_json_emis(0)
        demarrage._rendre_term(processus=True)  # fin de « python -m brvm_alpha » : l'objet est écrit
        assert signal.getsignal(signal.SIGTERM) == signal.SIG_IGN  # avant : SIG_DFL, un TERM tardif donnait −15
        demarrage.reinitialiser()
        demarrage._rendre_term(processus=True)  # aucun objet écrit (sortie texte) : TERM garde son effet
        assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL
    finally:
        signal.signal(signal.SIGTERM, avant)
        if xcpu_avant is not None:
            signal.signal(signal.SIGXCPU, xcpu_avant)
        demarrage.reinitialiser()


def test_signal_dispositions_of_the_test_process_are_left_untouched():
    # Garde-fou : après les essais ci-dessus, SIGXCPU et SIGTERM ont leur action par défaut dans ce processus.
    assert signal.getsignal(signal.SIGTERM) in (signal.SIG_DFL, None)
    if hasattr(signal, "SIGXCPU"):
        assert signal.getsignal(signal.SIGXCPU) == signal.SIG_DFL


def test_xcpu_message_no_longer_promises_no_partial_result():
    msg = demarrage.message_xcpu()
    assert "sans résultat partiel" not in msg and "déjà enregistré" in msg and "RLIMIT_CPU" in msg


# ---------------------------------------------------------------------------
# panel sans aucun bulletin
# ---------------------------------------------------------------------------


def test_panel_without_any_bulletin_exits_1_with_a_clear_message(tmp_path, capsys):
    boc = tmp_path / "boc_text"
    boc.mkdir()
    (boc / "boc_20210507.missing").write_bytes(b"")  # marqueurs seulement : aucun bulletin
    for _ in range(2):
        code, out, _ = run_cli(capsys, "panel", "--boc-dir", str(boc), "--panel-dir", str(tmp_path / "panel"),
                               "--format", "json")
        d = one_json(out)  # avant : 7, « erreur interne : KeyError : file »
        assert code == 1 and d["erreur"] == "donnees_absentes", d
        assert "aucun bulletin dans" in d["message"] and "update" in d["message"]
        assert not (tmp_path / "panel").exists()
        (boc / "boc_20210507.missing").unlink(missing_ok=True)  # second tour : dossier vide


# ---------------------------------------------------------------------------
# BRVM_ALPHA_CPU_MIN : valeurs illisibles ou négatives, arrondis du message
# ---------------------------------------------------------------------------


def test_cpu_min_negative_or_unreadable_takes_the_default_and_says_so():
    env = demarrage.ENV_CPU_MIN
    for v in ("-5", "-900", "abc", "nan", "inf", "-inf", "1e400", "900s"):
        assert demarrage.seuil_cpu({env: v}) == 900, v  # avant : « -5 » coupait le contrôle
        msg = demarrage.controle_cpu({env: v}, limite=600, consomme=1)
        assert msg is not None and "illisible ou négative" in msg and "défaut de 900 s" in msg, v
    for v in ("0", "0.0", "-0"):
        assert demarrage.controle_cpu({env: v}, limite=1, consomme=0) is None, v  # seul 0 coupe le contrôle
    assert demarrage.controle_cpu({}, limite=1000, consomme=50) is None
    assert "illisible" not in demarrage.controle_cpu({}, limite=600, consomme=1)


def test_cpu_refusal_message_never_contradicts_itself():
    import re

    for lim, used, seuil in ((900, 0.03, None), (60, 0.04, "60"), (899, 0.0, None), (950, 60.0, None),
                             (901, 1.04, None), (3600, 0.03, "1e12"), (40, 10.2, "30")):
        env = {} if seuil is None else {demarrage.ENV_CPU_MIN: seuil}
        msg = demarrage.controle_cpu(env, limite=lim, consomme=used)
        assert msg is not None, (lim, used, seuil)
        marge = float(re.search(r"([\d,]+) s de marge", msg).group(1).replace(",", "."))
        demande = float(re.search(r"au moins (\d+) s", msg).group(1))
        assert marge < demande, msg  # avant : « 900,0 s de marge ; le moteur en demande au moins 900 s »
    assert "899,9 s de marge" in demarrage.controle_cpu({}, limite=900, consomme=0.03)


# ---------------------------------------------------------------------------
# Outils de poppler : récoltés dès leur fin
# ---------------------------------------------------------------------------

_MESURE_ZOMBIE = r'''
import json, os, subprocess, sys, time
outil, n = sys.argv[1], int(sys.argv[2])
code = "import sys\nfrom brvm_alpha import pdf\nfor i in range(int(sys.argv[2])):\n    pdf.lancer_outil([sys.argv[1]], delai=60)\n"
p = subprocess.Popen([sys.executable, "-B", "-c", code, outil, str(n)])
vus = {}
while p.poll() is None:
    try:
        enfants = [int(x) for t in os.listdir(f"/proc/{p.pid}/task")
                   for x in open(f"/proc/{p.pid}/task/{t}/children").read().split()]
    except OSError:
        enfants = []
    now = time.monotonic()
    for k in enfants:
        try:
            st = open(f"/proc/{k}/stat").read()
        except OSError:
            continue
        if st[st.rfind(")") + 2] == "Z" and k not in vus:
            vus[k] = [now, None]
    for k, v in vus.items():
        if v[1] is None and k not in enfants:
            v[1] = now
    time.sleep(0.0002)
print(json.dumps({"rc": p.returncode, "ms": [round((b - a) * 1000, 2) for a, b in vus.values() if b]}))
'''


@pytest.mark.skipif(not LINUX, reason="/proc : Linux seulement")
def test_a_finished_poppler_tool_is_reaped_at_once(tmp_path):
    outil = tmp_path / "outil"
    outil.write_text("#!/bin/sh\nsleep 0.15\nexit 3\n", encoding="utf-8")  # sort en 3, comme poppler le documente
    outil.chmod(0o755)
    (tmp_path / "mesure.py").write_text(_MESURE_ZOMBIE, encoding="utf-8")
    p = subprocess.run([sys.executable, "-B", str(tmp_path / "mesure.py"), str(outil), "12"], env=_env(),
                       capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    res = json.loads(p.stdout)
    assert res["rc"] == 0, p.stderr[-800:]
    if not res["ms"]:  # outil récolté avant d'être vu zombie : rien à mesurer, c'est le but
        return
    # avant : 0,4 à 49,5 ms (24 ms en moyenne), le temps que Popen.wait se réveille de ses sommeils
    assert statistics.median(res["ms"]) < 5.0, res


def test_tool_wait_keeps_its_time_limit_and_works_without_pidfd(monkeypatch):
    t0 = time.monotonic()
    with pytest.raises(pdf.ExtractionRatee):
        pdf.lancer_outil(["/bin/sleep", "5"], delai=0.3)
    assert time.monotonic() - t0 < 3.0
    code, _out, _err = pdf.lancer_outil(["/bin/sh", "-c", "exit 3"], delai=30)
    assert code == 3  # le code de l'outil est rendu au moteur, qui ne sort jamais en 3 pour autant
    monkeypatch.setattr(os, "pidfd_open", lambda pid: (_ for _ in ()).throw(OSError(38, "pas de pidfd")),
                        raising=False)
    assert pdf.lancer_outil(["/bin/sh", "-c", "exit 0"], delai=30)[0] == 0
    with pytest.raises(pdf.ExtractionRatee):
        pdf.lancer_outil(["/bin/sleep", "5"], delai=0.3)


# ---------------------------------------------------------------------------
# Panel : processus de travail dont le serveur est déjà mort
# ---------------------------------------------------------------------------

_SCRIPT_SERVEUR_MORT = r'''
import ctypes, json, os, sys, time
assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER : joue le processus 1
r, w = os.pipe()
serveur = os.fork()
if serveur == 0:  # faux serveur de processus : charge brvm_alpha.lien_parent comme le vrai
    import brvm_alpha.lien_parent  # noqa: F401
    pid_serveur = os.getpid()
    travailleur = os.fork()
    if travailleur == 0:  # processus de travail : attend la mort du serveur, puis pose son lien
        while os.getppid() == pid_serveur:
            time.sleep(0.01)
        from brvm_alpha import ressources
        ressources.initialiser_travailleur()
        os._exit(0)  # avant : il continuait, orphelin
    os.write(w, str(travailleur).encode())
    os._exit(0)
os.close(w)
travailleur = int(os.read(r, 32))
codes = {}
t0 = time.monotonic()
while len(codes) < 2 and time.monotonic() - t0 < 60:
    pid, st = os.waitpid(-1, 0)
    codes["serveur" if pid == serveur else "travailleur" if pid == travailleur else str(pid)] = os.waitstatus_to_exitcode(st)
print(json.dumps(codes))
'''


@pytest.mark.skipif(not LINUX, reason="PR_SET_PDEATHSIG : Linux seulement")
def test_a_worker_whose_server_is_already_dead_stops_at_once(tmp_path):
    (tmp_path / "serveur_mort.py").write_text(_SCRIPT_SERVEUR_MORT, encoding="utf-8")
    p = subprocess.run([sys.executable, "-B", str(tmp_path / "serveur_mort.py")], env=_env(), capture_output=True,
                       text=True, timeout=120, cwd=str(tmp_path))
    codes = json.loads(p.stdout)
    assert codes == {"serveur": 0, "travailleur": 1}, (codes, p.stderr[-800:])  # avant : travailleur 0


_SCRIPT_POOL = r'''
import ctypes, json, os, signal, subprocess, sys, time
assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER : joue le processus 1
boc, sortie, decalage = sys.argv[1], sys.argv[2], float(sys.argv[3])


def enfants(pid):
    out = []
    try:
        for t in os.listdir(f"/proc/{pid}/task"):
            out += [int(x) for x in open(f"/proc/{pid}/task/{t}/children").read().split()]
    except OSError:
        pass
    return out


def descendants(pid):
    vus, a_voir = [], [pid]
    while a_voir:
        for k in enfants(a_voir.pop()):
            vus.append(k)
            a_voir.append(k)
    return vus


def lire(chemin):
    try:
        return open(chemin, "rb").read()
    except OSError:
        return b""


def vivant(pid):
    try:
        st = open(f"/proc/{pid}/stat").read()
    except OSError:
        return False
    return st[st.rfind(")") + 2] != "Z"


p = subprocess.Popen([sys.executable, "-B", "-m", "brvm_alpha", "panel", "--force", "--boc-dir", boc, "--panel-dir",
                      sortie, "--workers", "2", "--format", "json"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
t0, tue = time.monotonic(), False
while time.monotonic() - t0 < 60 and p.poll() is None:
    serveurs = [k for k in enfants(p.pid) if b"forkserver" in lire(f"/proc/{k}/cmdline")]
    if serveurs and enfants(serveurs[0]):  # premier processus de travail né
        time.sleep(decalage / 1000)
        os.kill(p.pid, signal.SIGKILL)  # KILL au seul moteur
        tue = True
        break
    time.sleep(0.0003)
time.sleep(5)
restants = [k for k in descendants(os.getpid()) if vivant(k)]
for k in restants:
    os.kill(k, signal.SIGKILL)
codes = []
while True:
    try:
        _pid, st = os.waitpid(-1, 0)
    except ChildProcessError:
        break
    codes.append(os.waitstatus_to_exitcode(st))
print(json.dumps({"tue": tue, "restants": len(restants), "codes": codes}))
'''


@pytest.mark.skipif(not LINUX, reason="forkserver et PR_SET_PDEATHSIG : Linux seulement")
def test_killing_the_engine_alone_as_the_pool_starts_leaves_no_live_process(tiny, tmp_path):
    (tmp_path / "pool.py").write_text(_SCRIPT_POOL, encoding="utf-8")
    vus = []
    for decalage in ("0", "5", "15"):
        p = subprocess.run([sys.executable, "-B", str(tmp_path / "pool.py"), str(tiny / "boc_text"),
                            str(tmp_path / f"panel_{decalage}"), decalage], env=_env(), capture_output=True, text=True,
                           timeout=180, cwd=str(tmp_path))
        res = json.loads(p.stdout)
        vus.append(res)
        # avant : processus de travail et resource_tracker vivants (plus de 90 s), rattachés au processus 1
        assert res["restants"] == 0, (decalage, res, p.stderr[-800:])
        assert 3 not in res["codes"], res
    assert any(r["tue"] for r in vus), vus


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------


def test_deployment_doc_states_the_remaining_risks_plainly():
    doc = (ROOT / "docs" / "DEPLOIEMENT.md").read_text(encoding="utf-8")
    plat = " ".join(doc.split())
    a7 = plat.split("### A.7", 1)[1].split("### A.8", 1)[0]
    assert "sans jamais sortir en 3" not in a7 and "Le risque reste" in a7.replace("**", "")
    assert "nouveau groupe de processus" in a7.replace("**", "")
    a8 = plat.split("### A.8", 1)[1].split("### A.9", 1)[0]
    assert "reportés" in a8 and "seul `KILL` l'arrête" in a8
    a6 = plat.split("### A.6", 1)[1].split("### A.7", 1)[0]
    assert "reste **court**" in a6
    # récolte : « jamais de récolteur » seulement dans le travailleur Odoo ; un lanceur dédié peut l'être, à trois
    # conditions ; HOME=<D>/home admis ; purge du dossier temporaire conseillée
    a6n = a6.replace("**", "")
    assert "Lanceur dans le travailleur Odoo" in a6n and "jamais PR_SET_CHILD_SUBREAPER, jamais waitpid(-1)" in \
        a6n.replace("`", "")
    assert "Lanceur processus dédié" in a6n and "trois conditions" in a6n
    for condition in ("(a) il attend d'abord son enfant direct par `Popen.wait`, dans un seul fil, sans gestionnaire "
                      "de `SIGCHLD`", "(b) il récolte jusqu'à `ECHILD` avant toute sortie",
                      "après le `KILL` ciblé du groupe du moteur et sur erreur", "(c) sa propre sortie vaut 0 ou 1, "
                      "jamais 3 (`os._exit` dans le `finally`)"):
        assert condition in a6n, condition
    assert "`<D>/home`" in a6n and "sauf par `expanduser` d'un chemin donné en option" in a6n
    assert "purge de `<T>`" in a6n and "après chaque lancement" in a6n
    assert "ne vaut donc que pour un lanceur qui tourne dans le travailleur Odoo" in a7
    a3 = plat.split("### A.3", 1)[1].split("### A.4", 1)[0]
    assert "seul `0` coupe le contrôle" in a3
    a2 = plat.split("### A.2", 1)[1].split("### A.3", 1)[0]
    assert "vide ou faite seulement d'espaces" in a2.replace("**", "")
    assert "Performance passée ≠ garantie. Aucun gain n'est garanti." in doc


# ---------------------------------------------------------------------------
# Documentation : le lanceur dédié récolteur du § A.6, essayé tel qu'il est écrit
# ---------------------------------------------------------------------------

_PILOTE_LANCEUR_DEDIE = r"""
import json, sys
ns = {"__name__": "lanceur_dedie"}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), "DEPLOIEMENT.md § A.6 (lanceur dédié)", "exec"), ns)
spec = json.loads(sys.argv[2])
ns["lancer_dedie"](spec["cmd"], spec["env"], spec["delai_s"], spec["sortie"], spec["erreurs"], spec["resultat"],
                   grace_s=spec["grace_s"])
raise SystemExit(3)  # jamais atteint : lancer_dedie ne rend pas la main
"""

_FAUX_MOTEUR = r"""
import json, os, signal, subprocess, sys, time
mode, trace = sys.argv[1], sys.argv[2]
if mode == "ignore_term":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
duree = "0.5" if mode == "orphelin" else "60"
petit = subprocess.Popen([sys.executable, "-c", "import sys, time; time.sleep(float(sys.argv[1])); sys.exit(3)", duree])
with open(trace, "w") as fh:
    fh.write(json.dumps({"moteur": os.getpid(), "petit_enfant": petit.pid}))
print(json.dumps({"ok": True, "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti."}), flush=True)
if mode == "orphelin":
    os._exit(0)  # sort sans attendre son enfant : un orphelin qui sortira en 3 (comme un outil de poppler)
time.sleep(60)
"""


def _bloc_lanceur_dedie() -> str:
    doc = (ROOT / "docs" / "DEPLOIEMENT.md").read_text(encoding="utf-8")
    a6 = doc.split("### A.6", 1)[1].split("### A.7", 1)[0]
    blocs = [b.split("```", 1)[0] for b in a6.split("```python")[1:]]
    dedies = [b for b in blocs if b.lstrip().startswith("# Lanceur dédié")]
    assert len(dedies) == 1, "un seul exemple de lanceur dédié au § A.6"
    return dedies[0]


def _vivant(pid: int) -> bool:
    try:
        st = open(f"/proc/{pid}/stat").read()
    except OSError:
        return False
    return st[st.rfind(")") + 2] != "Z"


@pytest.mark.skipif(not LINUX, reason="PR_SET_CHILD_SUBREAPER : Linux seulement")
@pytest.mark.parametrize("cas", ["orphelin", "ignore_term", "term_lanceur", "commande_absente"])
def test_the_dedicated_reaping_launcher_of_the_doc_reaps_every_process_and_never_exits_3(tmp_path, cas):
    """Lanceur dédié du § A.6, essayé tel qu'il est écrit : (a) code du moteur par Popen.wait ; (b) orphelins du moteur
    récoltés par le lanceur (jamais par le processus 1), après le KILL du groupe et sur arrêt du lanceur compris ;
    (c) sortie du lanceur en 0 ou 1, jamais 3, même quand un orphelin sort en 3."""
    (tmp_path / "lanceur.py").write_text(_bloc_lanceur_dedie(), encoding="utf-8")
    (tmp_path / "pilote.py").write_text(_PILOTE_LANCEUR_DEDIE, encoding="utf-8")
    (tmp_path / "moteur.py").write_text(_FAUX_MOTEUR, encoding="utf-8")
    trace = tmp_path / "trace.json"
    mode = {"orphelin": "orphelin", "ignore_term": "ignore_term"}.get(cas, "attend")
    cmd = ([str(tmp_path / "absent")] if cas == "commande_absente"
           else [sys.executable, "-I", "-B", str(tmp_path / "moteur.py"), mode, str(trace)])
    spec = {"cmd": cmd, "env": {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, "sortie": str(tmp_path / "sortie.json"),
            "erreurs": str(tmp_path / "erreurs.txt"), "resultat": str(tmp_path / "resultat.json"),
            "delai_s": 0.5 if cas == "ignore_term" else 30.0, "grace_s": 0.5}
    p = subprocess.Popen([sys.executable, "-I", "-B", str(tmp_path / "pilote.py"), str(tmp_path / "lanceur.py"),
                          json.dumps(spec)], cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cas == "term_lanceur":
        fin = time.monotonic() + 30
        while not (trace.exists() and trace.read_text()) and time.monotonic() < fin:
            time.sleep(0.01)
        p.send_signal(signal.SIGTERM)  # le lanceur lui-même est arrêté pendant que le moteur tourne
    _out, err = p.communicate(timeout=60)
    res = json.loads((tmp_path / "resultat.json").read_text(encoding="utf-8"))
    attendu = {"orphelin": (0, 0, [3]), "ignore_term": (0, -9, [-9]), "term_lanceur": (1, None, [-9, -9]),
               "commande_absente": (1, None, [])}[cas]
    assert (p.returncode, res["code"], sorted(res["orphelins"])) == attendu, (res, err.decode()[-800:])
    assert p.returncode != 3
    if cas != "commande_absente":
        pids = json.loads(trace.read_text())
        assert not _vivant(pids["moteur"]) and not _vivant(pids["petit_enfant"])  # tout est récolté, rien ne reste
        assert json.loads((tmp_path / "sortie.json").read_text())["ok"] is True  # objet du moteur, dans un fichier
