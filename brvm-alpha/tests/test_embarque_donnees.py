"""Couches internes du moteur embarqué : mode embarqué, codes de retour, écritures atomiques, verrous,
marqueurs des BOC absents, extraction PDF, panel transactionnel, ressources, journal des notes, état.

Tout essai qui écrit le fait dans un dossier temporaire ; ``data/notes`` du dépôt n'est jamais touché.
Aucune requête réseau (doublures). Les essais à deux processus lancent un second interpréteur qui tient
un verrou, puis le tuent : le système rend le verrou.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from brvm_alpha import erreurs, fichiers, paths, ressources
from brvm_alpha.data import boc_download as bd
from brvm_alpha.data import store

ROOT = Path(__file__).resolve().parents[1]
BOC_FIX = ROOT / "tests" / "fixtures" / "notes" / "boc"
TODAY = dt.date(2026, 11, 22)


def run_py(code: str, *args: str, env: dict[str, str] | None = None, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if not k.startswith("BRVM_ALPHA_")}
    return subprocess.run([sys.executable, "-c", code, *args], cwd=str(cwd), capture_output=True, text=True,
                          env={**base, "PYTHONDONTWRITEBYTECODE": "1", **(env or {})}, timeout=300)


def holder(code: str, *args: str) -> subprocess.Popen:
    """Second processus qui prend un verrou, écrit PRET, puis attend."""
    p = subprocess.Popen([sys.executable, "-c", code, *args], cwd=str(ROOT), stdout=subprocess.PIPE, text=True,
                         env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert p.stdout is not None and p.stdout.readline().strip() == "PRET"
    return p


def stop(p: subprocess.Popen) -> None:
    if p.poll() is None:
        p.kill()
    p.wait(timeout=10)


HOLD = r"""
import sys, time
from brvm_alpha import fichiers
with fichiers.verrou(sys.argv[1], quoi="essai"):
    print("PRET", flush=True)
    time.sleep(float(sys.argv[2]))
"""


# ---------------------------------------------------------------------------
# Mode embarqué et chemins
# ---------------------------------------------------------------------------


def test_embedded_mode_detection(tmp_path, monkeypatch):
    monkeypatch.delenv(paths.ENV_EMBARQUE, raising=False)
    assert paths.est_embarque({}, tmp_path) is False
    assert paths.est_embarque({paths.ENV_EMBARQUE: "1"}, tmp_path) is True
    assert paths.est_embarque({paths.ENV_EMBARQUE: "0"}, tmp_path) is False
    (tmp_path / "VERSION").write_text("2026.11.22-d256e26\n", encoding="utf-8")
    assert paths.est_embarque({}, tmp_path) is True and paths.version_livree(tmp_path) == "2026.11.22-d256e26"
    (tmp_path / "VERSION").write_text("pas une version ; rm -rf\n", encoding="utf-8")
    assert paths.version_livree(tmp_path) is None
    assert not (paths.REPO_ROOT / "VERSION").exists()  # le dépôt de développement n'est jamais embarqué


def test_embedded_mode_requires_absolute_data_and_reports_folders_outside_the_code(tmp_path):
    emb = {paths.ENV_EMBARQUE: "1"}
    with pytest.raises(erreurs.ConfigurationError, match="BRVM_ALPHA_DONNEES"):
        paths.resolve_dirs(emb)
    with pytest.raises(erreurs.ConfigurationError, match="chemin absolu"):
        paths.resolve_dirs({**emb, paths.ENV_DATA: "donnees", paths.ENV_REPORTS: str(tmp_path / "r")})
    with pytest.raises(erreurs.ConfigurationError, match="BRVM_ALPHA_RAPPORTS"):
        paths.resolve_dirs({**emb, paths.ENV_DATA: str(tmp_path / "d")})
    with pytest.raises(erreurs.ConfigurationError, match="dossier du code"):
        paths.resolve_dirs({**emb, paths.ENV_DATA: str(paths.REPO_ROOT / "data"), paths.ENV_REPORTS: str(tmp_path)})
    assert paths.resolve_dirs({**emb, paths.ENV_DATA: str(tmp_path / "d"), paths.ENV_REPORTS: str(tmp_path / "r")}) == (
        tmp_path / "d", tmp_path / "r")
    assert paths.resolve_dirs({}) == (paths.REPO_ROOT / "data", paths.REPO_ROOT / "reports")  # usage normal inchangé
    assert erreurs.code_retour(erreurs.ConfigurationError("x")) == 8


def test_embedded_start_without_folders_imports_but_refuses_every_write(tmp_path):
    code = r"""
import json, sys
from brvm_alpha import erreurs, fichiers, paths
out = {"erreur": paths.ERREUR_CONFIGURATION is not None}
try:
    paths.verifier_configuration()
except erreurs.ConfigurationError as exc:
    out["code"] = erreurs.code_retour(exc)
for what, fn in (("ecriture", lambda: fichiers.ecrire_atomique(paths.REPO_ROOT / "data" / "essai.txt", "x")),
                 ("verrou", lambda: fichiers.verrou(paths.REPO_ROOT / "data" / "essai.lock").__enter__())):
    try:
        fn()
        out[what] = "ecrit"
    except erreurs.ConfigurationError:
        out[what] = "refuse"
from brvm_alpha.notes.store import NoteStore
from brvm_alpha.notes.model import Note
try:
    NoteStore().add(Note(title="essai", text="x"))
    out["journal"] = "ecrit"
except erreurs.ConfigurationError:
    out["journal"] = "refuse"
print(json.dumps(out))
"""
    before = sorted(p.name for p in (ROOT / "data").iterdir()) if (ROOT / "data").exists() else []
    r = run_py(code, env={paths.ENV_EMBARQUE: "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    assert json.loads(r.stdout) == {"erreur": True, "code": 8, "ecriture": "refuse", "verrou": "refuse",
                                    "journal": "refuse"}
    after = sorted(p.name for p in (ROOT / "data").iterdir()) if (ROOT / "data").exists() else []
    assert after == before and not (ROOT / "data" / "essai.txt").exists()


def test_embedded_mode_writes_only_in_the_data_folder_and_reads_the_version_file(tmp_path):
    code = r"""
import json
from brvm_alpha import etat, fichiers, paths
p = fichiers.ecrire_atomique(paths.DATA_DIR / "essai.txt", "x")
try:
    fichiers.ecrire_atomique(paths.REPO_ROOT / "brvm_alpha" / "essai.txt", "x")
    code = "ecrit"
except Exception as exc:
    code = type(exc).__name__
print(json.dumps({"data": str(paths.DATA_DIR), "ecrit": p.read_text(), "code_tree": code,
                  "option": str(paths.resoudre_chemin_option("data/panel")),
                  "rapport": str(paths.resoudre_chemin_option("r.html", base="rapports")),
                  "absolu": str(paths.resoudre_chemin_option("/x/y")), "version": etat.code_version()}))
"""
    env = {paths.ENV_EMBARQUE: "1", paths.ENV_DATA: str(tmp_path / "d"), paths.ENV_REPORTS: str(tmp_path / "r")}
    r = run_py(code, env=env)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout)
    assert out["data"] == str(tmp_path / "d") and out["ecrit"] == "x" and out["code_tree"] == "ConfigurationError"
    assert out["option"] == str(tmp_path / "d" / "panel") and out["rapport"] == str(tmp_path / "r" / "r.html")
    assert out["absolu"] == "/x/y"
    assert not (ROOT / "brvm_alpha" / "essai.txt").exists()
    # La version vient du fichier VERSION d'un code exporté (copie du paquet, sans .git).
    code_copy = tmp_path / "moteur"
    shutil.copytree(ROOT / "brvm_alpha", code_copy / "brvm_alpha", ignore=shutil.ignore_patterns("__pycache__"))
    (code_copy / "VERSION").write_text("2026.11.22-abc1234\n", encoding="utf-8")
    r = run_py("from brvm_alpha import etat, paths, ressources\nimport os\n"
               "print(etat.code_version(), paths.est_embarque(), os.environ.get('OMP_NUM_THREADS'), "
               "os.environ.get('ARROW_DEFAULT_MEMORY_POOL'))",
               env={paths.ENV_DATA: str(tmp_path / "d"), paths.ENV_REPORTS: str(tmp_path / "r")}, cwd=code_copy)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split() == ["2026.11.22-abc1234", "True", "1", "system"]


def test_option_paths_outside_embedded_mode_are_unchanged(monkeypatch):
    monkeypatch.delenv(paths.ENV_EMBARQUE, raising=False)
    assert paths.resoudre_chemin_option("data/panel") == Path("data/panel")
    assert paths.resoudre_chemin_option(None) is None and paths.resoudre_chemin_option("") is None
    with pytest.raises(erreurs.SaisieInvalide):
        paths.resoudre_chemin_option("../code", environ={paths.ENV_EMBARQUE: "1"})


@pytest.mark.parametrize("exc,code,kind", [
    (KeyboardInterrupt(), 130, "interruption"), (MemoryError(), 6, "memoire"), (SystemExit(2), 2, "saisie_invalide"),
    (SystemExit(3), 7, "interne"), (ValueError("x"), 2, "saisie_invalide"), (KeyError("x"), 2, "saisie_invalide"),
    (FileNotFoundError("x"), 1, "donnees_absentes"), (RuntimeError("x"), 7, "interne"),
    (erreurs.VerrouOccupe("x"), 4, "verrou_occupe"), (erreurs.AccesRefuse("x"), 5, "acces_refuse"),
    (erreurs.ConfigurationError("x"), 8, "configuration"), (bd.DownloadStopped("x", raison="quota"), 1, "donnees_absentes"),
    (bd.DownloadStopped("x", raison="bloque"), 5, "acces_refuse"),
])
def test_return_codes_never_3(exc, code, kind):
    assert erreurs.code_retour(exc) == code and erreurs.type_erreur(exc) == kind
    obj = erreurs.erreur_json(exc, "Performance passée ≠ garantie. Aucun gain n'est garanti.")
    assert obj["ok"] is False and obj["code"] == code and obj["erreur"] == kind and obj["message"]
    assert obj["bandeau"] == "Performance passée ≠ garantie. Aucun gain n'est garanti."
    assert erreurs.code_retour(exc) != 3


# ---------------------------------------------------------------------------
# Écritures atomiques et verrous
# ---------------------------------------------------------------------------


def test_atomic_write_leaves_the_old_file_on_failure(tmp_path):
    target = tmp_path / "f.txt"
    fichiers.ecrire_atomique(target, "ancien")
    with pytest.raises(RuntimeError):
        with fichiers.fichier_atomique(target, "w", encoding="utf-8") as fh:
            fh.write("nouveau, à moitié")
            raise RuntimeError("coupure")
    assert target.read_text() == "ancien" and [p.name for p in tmp_path.iterdir()] == ["f.txt"]
    fichiers.ecrire_atomique_avec(tmp_path / "t.parquet", lambda tmp: pd.DataFrame({"a": [1]}).to_parquet(tmp))
    assert pd.read_parquet(tmp_path / "t.parquet")["a"].tolist() == [1]
    (tmp_path / ".x.txt.1.ab.part").write_text("reste")
    os.utime(tmp_path / ".x.txt.1.ab.part", (0, 0))
    assert fichiers.purger_temporaires(tmp_path) == 1


def test_lock_between_two_processes_times_out_then_is_released_when_the_holder_dies(tmp_path):
    lock = tmp_path / "x.lock"
    p = holder(HOLD, str(lock), "60")
    try:
        t0 = time.monotonic()
        with pytest.raises(erreurs.VerrouOccupe, match="essai"):
            with fichiers.verrou(lock, attente=0.3):
                pass
        assert 0.25 <= time.monotonic() - t0 < 3.0
        p.kill()
        p.wait(timeout=10)
        with fichiers.verrou(lock, attente=2.0):
            pass
        assert lock.exists()  # le fichier de verrou n'est jamais supprimé (flock)
    finally:
        stop(p)


def test_lock_is_reentrant_in_a_thread_and_shared_readers_create_nothing(tmp_path):
    lock = tmp_path / "y.lock"
    with fichiers.verrou(lock):
        with fichiers.verrou(lock):  # même fil : réentrant
            pass
    with fichiers.verrou(tmp_path / "absent.lock", partage=True, creer=False) as held:
        assert held is False
    assert not (tmp_path / "absent.lock").exists()
    with fichiers.verrou(lock, partage=True, creer=False) as held:
        assert held is True
    monkey = os.environ.get(fichiers.ENV_ATTENTE)
    try:
        os.environ[fichiers.ENV_ATTENTE] = "1.5"
        assert fichiers.delai_verrou() == 1.5 and fichiers.delai_verrou(0.2) == 0.2
    finally:
        os.environ.pop(fichiers.ENV_ATTENTE, None) if monkey is None else os.environ.__setitem__(fichiers.ENV_ATTENTE,
                                                                                                  monkey)


# ---------------------------------------------------------------------------
# Marqueurs « sans bulletin », fenêtre de update
# ---------------------------------------------------------------------------


def fake_fetch(responses: dict[str, tuple[int, bytes]], default: tuple[int, bytes] = (404, b"")):
    calls: list[str] = []

    def fetch(url: str) -> tuple[int, bytes]:
        calls.append(url)
        r = responses.get(url, default)
        if isinstance(r, Exception):
            raise r
        return r

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


DAY = dt.date(2026, 11, 2)


def test_404_everywhere_becomes_definitive_only_after_three_attempts_a_day_apart(tmp_path):
    fetch = fake_fetch({})
    now = dt.datetime(2026, 11, 10, 20, tzinfo=dt.timezone.utc)
    for k in range(3):
        today = dt.date(2026, 11, 10) + dt.timedelta(days=k)
        assert DAY in bd.pending_days(DAY, DAY, tmp_path, today)
        assert bd.fetch_one(fetch, DAY, tmp_path, today=today, now=now + dt.timedelta(days=k)) is None
        m = bd.lire_marqueur(bd.marker_path(tmp_path, DAY))
        assert m.statut == "introuvable" and m.code_http == 404 and m.tentatives == k + 1 and m.definitif is (k == 2)
        assert DAY not in bd.pending_days(DAY, DAY, tmp_path, today)  # même jour : pas de nouvel essai
    n = len(fetch.calls)
    assert bd.fetch_one(fetch, DAY, tmp_path, today=dt.date(2026, 12, 31)) is None and len(fetch.calls) == n
    raw = json.loads(bd.marker_path(tmp_path, DAY).read_text())
    assert {"statut", "code_http", "url", "date", "tentatives", "definitif"} <= set(raw)


@pytest.mark.parametrize("response,statut", [
    ((200, b"<html>page d'attente</html>"), "pas_un_pdf"),
    ((302, b""), "redirection"),
    (bd.ReponseInexploitable("redirection", "boucle"), "redirection"),
    (bd.ReponseInexploitable("trop_gros", "trop gros"), "trop_gros"),
    ((500, b""), "autre"),
])
def test_non_pdf_answers_never_make_a_definitive_marker(tmp_path, response, statut):
    fetch = fake_fetch({}, default=response)
    for k in range(5):
        today = dt.date(2026, 11, 10) + dt.timedelta(days=40 * k)
        bd.fetch_one(fetch, DAY, tmp_path, today=today, now=dt.datetime.combine(today, dt.time(20), dt.timezone.utc))
        m = bd.lire_marqueur(bd.marker_path(tmp_path, DAY))
        assert m.statut == statut and m.definitif is False and m.tentatives == k + 1
    assert m.a_relancer(today + dt.timedelta(days=bd.RELANCE_MAX_JOURS))
    bd.marquer_definitif(tmp_path, DAY, raison="séance sans bulletin, vérifié sur le site")
    m = bd.lire_marqueur(bd.marker_path(tmp_path, DAY))
    assert m.definitif and m.statut == "decision" and DAY not in bd.pending_days(DAY, DAY, tmp_path, TODAY)
    assert bd.reouvrir(tmp_path, DAY) and DAY in bd.pending_days(DAY, DAY, tmp_path, TODAY)


def test_failed_extraction_writes_bad_and_a_non_definitive_marker(tmp_path, monkeypatch):
    def boom(content):
        raise RuntimeError("PDF abîmé")

    monkeypatch.setattr(bd, "convert_pdf", boom)
    fetch = fake_fetch({}, default=(200, b"%PDF-1.4 abime"))
    assert bd.fetch_one(fetch, DAY, tmp_path, today=TODAY) is None
    m = bd.lire_marqueur(bd.marker_path(tmp_path, DAY))
    assert m.statut == "extraction_ratee" and not m.definitif and (tmp_path / "boc_20261102.bad").exists()


def test_legacy_empty_markers_are_still_read(tmp_path):
    (tmp_path / "boc_20261102.missing").touch()
    (tmp_path / "boc_20261103.missing").touch()
    (tmp_path / "boc_20261103.bad").write_text("url\nUnexpected EOF\n")
    old = dt.datetime(2026, 11, 4, tzinfo=dt.timezone.utc).timestamp()  # marqueurs écrits il y a longtemps
    for name in ("boc_20261102.missing", "boc_20261103.missing"):
        os.utime(tmp_path / name, (old, old))
    a = bd.lire_marqueur(tmp_path / "boc_20261102.missing")
    b = bd.lire_marqueur(tmp_path / "boc_20261103.missing")
    assert a.ancien and a.definitif and not b.definitif and b.statut == "extraction_ratee"
    assert bd.pending_days(dt.date(2026, 11, 2), dt.date(2026, 11, 3), tmp_path, TODAY) == [dt.date(2026, 11, 3)]


def test_configuration_errors_and_memory_errors_stop_without_marking_the_day(tmp_path, monkeypatch):
    for exc in (erreurs.ConfigurationError("pdftotext obligatoire"), MemoryError()):
        def boom(content, _e=exc):
            raise _e

        monkeypatch.setattr(bd, "convert_pdf", boom)
        with pytest.raises(type(exc)):
            bd.fetch_one(fake_fetch({}, default=(200, b"%PDF-1.4")), DAY, tmp_path, today=TODAY)
        assert not list(tmp_path.glob("boc_*"))


def test_update_window_fills_holes_from_the_oldest_missing_day(tmp_path):
    for d in (dt.date(2026, 11, 19), dt.date(2026, 11, 20)):
        (tmp_path / f"boc_{d:%Y%m%d}.txt.gz").write_bytes(gzip.compress(b"x"))
    start, end, days = bd.update_window(tmp_path, today=TODAY)
    assert start == bd.HISTORY_START == dt.date(2017, 1, 2) and end == TODAY
    assert days[0] == dt.date(2026, 11, 18) and days[-1] == dt.date(2017, 1, 2) and len(days) > 2500
    assert bd.update_window(tmp_path, start=dt.date(2026, 11, 16), today=TODAY)[2] == [dt.date(2026, 11, 18),
                                                                                        dt.date(2026, 11, 17),
                                                                                        dt.date(2026, 11, 16)]


def test_download_resumes_with_the_request_quota_and_never_leaves_holes(tmp_path):
    def run(quota: int) -> int:
        n = {"req": 0}

        def fetch(url: str) -> tuple[int, bytes]:
            if n["req"] >= quota:
                raise bd.DownloadStopped("quota", raison="quota")
            n["req"] += 1
            return 404, b""

        try:
            bd.download_range(dt.date(2026, 10, 1), dt.date(2026, 10, 31), tmp_path, fetcher=fetch, today=TODAY)
        except bd.DownloadStopped as exc:
            assert exc.raison == "quota" and exc.code_sortie == 1
        return n["req"]

    for _ in range(30):  # 12 requêtes par lancement, 5 adresses par jour : deux jours complets par lancement
        run(quota=12)
        if not bd.update_window(tmp_path, start=dt.date(2026, 10, 1), end=dt.date(2026, 10, 31), today=TODAY)[2]:
            break
    assert not bd.update_window(tmp_path, start=dt.date(2026, 10, 1), end=dt.date(2026, 10, 31), today=TODAY)[2]
    assert len(list(tmp_path.glob("*.missing"))) == 22  # tous les jours ouvrés d'octobre 2026 vus une fois


def test_bulletin_is_written_atomically_with_its_companion_file_and_the_panel_is_identical(tmp_path, monkeypatch):
    src = BOC_FIX / "boc_20261029.txt.gz"
    text = gzip.decompress(src.read_bytes()).decode("utf-8")
    url, _, body = text.partition("\n")
    assert url.startswith("# source: ")
    monkeypatch.setattr(bd, "convert_pdf", lambda content: (body, "pdftotext", "24.02.0"))
    out = tmp_path / "boc"
    out.mkdir()
    bd.marker_path(out, dt.date(2026, 10, 29)).write_text(
        '{"statut": "pas_un_pdf", "definitif": false, "date": "2026-10-30T20:00:00+00:00", "tentatives": 1}')
    fetch = fake_fetch({url[len("# source: "):]: (200, b"%PDF-1.4 ...")})
    assert bd.fetch_one(fetch, dt.date(2026, 10, 29), out, today=TODAY) == "boc_20261029.txt.gz"
    assert gzip.decompress((out / "boc_20261029.txt.gz").read_bytes()).decode("utf-8") == text
    meta = bd.lire_meta(out / "boc_20261029.txt.gz")
    assert meta["extracteur"] == "pdftotext" and meta["version_extracteur"] == "24.02.0" and meta["source"] == url[10:]
    assert not bd.marker_path(out, dt.date(2026, 10, 29)).exists()  # le jour a son bulletin
    assert not list(out.glob(".*.part"))
    ref = tmp_path / "ref"
    ref.mkdir()
    shutil.copy(src, ref / src.name)
    a, b = store.build_panel(ref, tmp_path / "pa", workers=1), store.build_panel(out, tmp_path / "pb", workers=1)
    assert a.n_rows == b.n_rows > 0
    for name in ("equities", "indices", "market", "sessions"):
        pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "pa" / f"{name}.parquet"),
                                      pd.read_parquet(tmp_path / "pb" / f"{name}.parquet"))


def test_download_lock_between_two_processes(tmp_path):
    p = holder(HOLD, str(tmp_path / bd.LOCK_NAME), "60")
    try:
        with pytest.raises(erreurs.VerrouOccupe, match="essai"):
            bd.download_range(DAY, DAY, tmp_path, fetcher=fake_fetch({}), today=TODAY, lock_timeout_s=0.3)
    finally:
        stop(p)
    assert bd.download_range(DAY, DAY, tmp_path, fetcher=fake_fetch({}), today=TODAY, lock_timeout_s=2.0) == 0


def test_glue_with_the_polite_session_no_longer_swallows_research_errors(tmp_path, monkeypatch):
    from brvm_alpha.notes import research as rs

    pages = {"https://www.brvm.org/robots.txt": (200, b"User-agent: *\nCrawl-delay: 10\n")}
    loop = bd.BASE_URL.format(date="20261102", suffix="_2")
    other = bd.BASE_URL.format(date="20261102", suffix="")

    class R:
        def __init__(self, status, content=b"", headers=None, url=""):
            self.status_code, self.content, self.headers, self.url = status, content, headers or {}, url

    def transport(url, headers, timeout):
        if url == loop:
            return R(302, b"", {"Location": loop}, url)
        if url == other:
            return R(302, b"", {"Location": "https://evil.example/boc.pdf"}, url)
        st, body = pages.get(url, (404, b""))
        return R(st, body, {}, url)

    real = rs.PoliteSession.__init__

    def init(self, **kw):
        kw.update(transport=transport, clock=lambda: 0.0, sleep=lambda s: None)
        real(self, **kw)

    monkeypatch.setattr(rs.PoliteSession, "__init__", init)
    fetch = bd.client_brvm(max_requests=50, cache_dir=tmp_path / "cache")
    with pytest.raises(bd.ReponseInexploitable) as exc:
        fetch(loop)  # redirections en boucle : pas de bulletin exploitable, le téléchargement continue
    assert exc.value.statut == "redirection"
    with pytest.raises(bd.DownloadStopped) as stopped:
        fetch(other)  # redirection hors liste blanche : arrêt, jamais « pas de bulletin »
    assert stopped.value.raison == "politique" and stopped.value.code_sortie == 5
    monkeypatch.setattr(rs.PoliteSession, "get", lambda self, url, **k: (_ for _ in ()).throw(
        rs.ResearchError("autre erreur de collecte")))
    with pytest.raises(bd.DownloadStopped, match="autre erreur"):
        bd.client_brvm(cache_dir=tmp_path / "cache")(loop)


# ---------------------------------------------------------------------------
# Extraction PDF
# ---------------------------------------------------------------------------


def test_embedded_mode_requires_pdftotext_and_no_extractor_is_a_configuration_error(tmp_path, monkeypatch):
    from brvm_alpha import pdf

    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    monkeypatch.setenv(paths.ENV_EMBARQUE, "1")
    with pytest.raises(erreurs.ConfigurationError, match="pdftotext"):
        pdf.extracteur()
    with pytest.raises(erreurs.ConfigurationError):
        bd.convert_pdf(b"%PDF-1.4")
    monkeypatch.delenv(paths.ENV_EMBARQUE)
    monkeypatch.setattr(pdf, "_pdfplumber_present", lambda: False)
    with pytest.raises(erreurs.ConfigurationError, match="aucun extracteur"):
        pdf.extracteur()


def test_pdf_extraction_is_time_bounded_and_size_bounded(tmp_path, monkeypatch):
    from brvm_alpha import pdf

    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF-1.4")
    if pdf.pdftotext_disponible():
        def slow(*a, **k):
            raise subprocess.TimeoutExpired(cmd="pdftotext", timeout=k.get("timeout"))

        monkeypatch.setattr(pdf.subprocess, "run", slow)
        with pytest.raises(pdf.ExtractionRatee, match="délai"):
            pdf.par_pdftotext(f)
    monkeypatch.setattr(pdf, "TAILLE_MAX", 4)
    with pytest.raises(pdf.ExtractionRatee, match="plafond"):
        pdf.par_pdftotext(f)


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext absent")
def test_real_pdf_is_read_by_pdftotext_with_its_version():
    from brvm_alpha import pdf
    from brvm_alpha.notes import research as rs

    doc = ROOT / "tests" / "fixtures" / "notes" / "doc_20261023_communique_annulation_ago_eti_tg.pdf"
    text, method, version = pdf.extraire_texte(doc)
    assert method == "pdftotext" and version and "ETI" in text.upper()
    info = rs.extract_pdf_text(doc)
    assert info["method"] == "pdftotext" and info["method_version"] == version and not info.get("error")


# ---------------------------------------------------------------------------
# Panel : ressources, transaction, verrous
# ---------------------------------------------------------------------------


def test_available_processors_follow_affinity_and_cgroup_quota(tmp_path, monkeypatch):
    v2 = tmp_path / "v2"
    v2.mkdir()
    (v2 / "cpu.max").write_text("150000 100000\n")
    monkeypatch.setattr(os, "sched_getaffinity", lambda pid: {0, 1, 2, 3})
    assert ressources.processeurs_disponibles(v2) == 1
    (v2 / "cpu.max").write_text("max 100000\n")
    assert ressources.processeurs_disponibles(v2) == 4
    v1 = tmp_path / "v1"
    (v1 / "cpu").mkdir(parents=True)
    (v1 / "cpu" / "cpu.cfs_quota_us").write_text("300000\n")
    (v1 / "cpu" / "cpu.cfs_period_us").write_text("100000\n")
    assert ressources.processeurs_disponibles(v1) == 3
    monkeypatch.setattr(ressources, "processeurs_disponibles", lambda *a, **k: 8)
    assert ressources.workers_par_defaut() == 2
    monkeypatch.setattr(ressources, "processeurs_disponibles", lambda *a, **k: 1)
    assert ressources.workers_par_defaut() == 1
    env = {"OMP_NUM_THREADS": "3"}
    ressources.limiter_fils(env)
    assert env["OMP_NUM_THREADS"] == "3" and env["OPENBLAS_NUM_THREADS"] == "1" and env["MKL_NUM_THREADS"] == "1"


def test_panel_workers_get_one_blas_thread_and_default_to_two(tmp_path, monkeypatch):
    seen: dict[str, Any] = {}

    class Pool:
        def __init__(self, max_workers, mp_context, initializer):
            seen.update(max_workers=max_workers, env={k: os.environ.get(k) for k in ressources.VARIABLES_FILS},
                        initializer=initializer)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def map(self, fn, items, chunksize=1):
            return [fn(x) for x in items]

    monkeypatch.setattr(store, "ProcessPoolExecutor", Pool)
    monkeypatch.setattr(ressources, "processeurs_disponibles", lambda *a, **k: 16)
    for k in ressources.VARIABLES_FILS:
        monkeypatch.delenv(k, raising=False)
    boc = tmp_path / "boc"
    shutil.copytree(BOC_FIX, boc)
    store.build_panel(boc, tmp_path / "panel")
    assert seen["max_workers"] == 2 and set(seen["env"].values()) == {"1"}
    assert seen["initializer"] is ressources.initialiser_travailleur
    assert all(os.environ.get(k) is None for k in ressources.VARIABLES_FILS)  # remis comme avant


def test_interrupted_panel_build_leaves_the_old_panel_intact(tmp_path, monkeypatch):
    boc = tmp_path / "boc"
    shutil.copytree(BOC_FIX, boc)
    panel = tmp_path / "panel"
    store.build_panel(boc, panel, workers=1)
    before = {p.name: p.read_bytes() for p in panel.glob("*.parquet")}
    real = store._build_panel_into

    def interrupted(boc_dir, old_dir, out_dir, **kw):
        real(boc_dir, old_dir, out_dir, **kw)
        (out_dir / "equities.parquet").write_bytes(b"abime")
        raise KeyboardInterrupt  # Ctrl+C pendant la construction

    monkeypatch.setattr(store, "_build_panel_into", interrupted)
    (boc / "boc_20261009.txt.gz").unlink()
    with pytest.raises(KeyboardInterrupt):
        store.build_panel(boc, panel, workers=1)
    assert {p.name: p.read_bytes() for p in panel.glob("*.parquet")} == before
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith(".panel.") and p.is_dir()) == []
    monkeypatch.setattr(store, "_build_panel_into", real)
    s = store.build_panel(boc, panel, workers=1)
    assert s.n_files == 6 and s.out_dir == panel and len(pd.read_parquet(panel / "equities.parquet")) == s.n_rows
    assert s.to_dict()["derniere_seance"] == "2026-10-29"


def test_swap_crash_is_recovered_and_files_put_in_the_panel_are_kept(tmp_path):
    boc = tmp_path / "boc"
    shutil.copytree(BOC_FIX, boc)
    panel = tmp_path / "panel"
    store.build_panel(boc, panel, workers=1)
    (panel / "note_de_l_analyste.txt").write_text("à garder")
    os.rename(panel, tmp_path / ".panel.ancien-1-abcd")  # coupure entre les deux renommages
    store.build_panel(boc, panel, workers=1)
    assert (panel / "note_de_l_analyste.txt").read_text() == "à garder"
    assert not list(tmp_path.glob(".panel.ancien-*"))


HOLD_READ = r"""
import sys, time
from brvm_alpha.data import store
with store.lecture_panel(sys.argv[1]):
    print("PRET", flush=True)
    time.sleep(float(sys.argv[2]))
"""


def test_panel_build_lock_and_reader_lock_between_two_processes(tmp_path):
    boc = tmp_path / "boc"
    shutil.copytree(BOC_FIX, boc)
    panel = tmp_path / "panel"
    store.build_panel(boc, panel, workers=1)
    p = holder(HOLD, str(tmp_path / ".panel.construction.lock"), "60")
    try:
        with pytest.raises(erreurs.VerrouOccupe, match="essai"):
            store.build_panel(boc, panel, workers=1, lock_timeout_s=0.3)
    finally:
        stop(p)
    # Un lecteur tient le verrou partagé : la bascule attend la fin de la lecture, jamais de panel à moitié écrit.
    reader = holder(HOLD_READ, str(panel), "2")
    try:
        t0 = time.monotonic()
        store.build_panel(boc, panel, workers=1, lock_timeout_s=20)
        assert time.monotonic() - t0 >= 1.0
    finally:
        stop(reader)


# ---------------------------------------------------------------------------
# Journal des notes
# ---------------------------------------------------------------------------


def _manual(**kw: Any):
    from brvm_alpha.notes.model import Note

    base = dict(author="analyste", source="manual", title="Sonatel : avis", text="Avis de l'analyste.",
                targets=["SNTS"], stance="haussier", conviction=3)
    base.update(kw)
    return Note(**base)


def test_add_unique_finds_the_duplicate_under_the_same_lock_and_keeps_the_given_publication(tmp_path):
    from brvm_alpha.notes.store import NoteStore

    st = NoteStore(tmp_path)
    note, created, dup = st.add_unique(_manual())
    assert created and dup is None
    again, created2, dup2 = st.add_unique(_manual())  # sans date saisie : autre identifiant, même contenu
    assert not created2 and dup2 == note.note_id and again.note_id == note.note_id and len(st) == 1
    forced, created3, _ = st.add_unique(_manual(), force=True)
    assert created3 and len(st) == 2
    dated, ok, _ = st.add_unique(_manual(title="Avis daté", published_at="2026-11-03"))
    assert ok and dated.published_at == pd.Timestamp("2026-11-03", tz="UTC") and dated.published_precision == "date"
    same, ok2, dup4 = st.add_unique(_manual(title="Avis daté", published_at="2026-11-03"))
    assert not ok2 and dup4 == dated.note_id  # même identifiant : rien n'est écrit


def test_two_processes_adding_the_same_note_write_it_once(tmp_path):
    code = r"""
import sys, time
from brvm_alpha.notes.store import NoteStore
from brvm_alpha.notes.model import Note
st = NoteStore(sys.argv[1])
n = Note(author="analyste", source="manual", title="Même note", text="Saisie deux fois.", targets=["SNTS"],
         stance="haussier", conviction=2)
deadline = float(sys.argv[2])
while time.time() < deadline:
    time.sleep(0.001)
note, created, dup = st.add_unique(n)
print("cree" if created else "doublon")
"""
    go = str(time.time() + 3.0)
    procs = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path), go], cwd=str(ROOT), stdout=subprocess.PIPE,
                              text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}) for _ in range(3)]
    outs = sorted(p.communicate(timeout=120)[0].strip() for p in procs)
    assert outs == ["cree", "doublon", "doublon"]
    lines = (tmp_path / "notes.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_journal_lock_held_by_another_process_gives_code_4(tmp_path):
    from brvm_alpha.notes.store import NoteStore, StoreLockError

    p = holder(HOLD, str(tmp_path / "notes.jsonl.lock"), "60")
    try:
        st = NoteStore(tmp_path, lock_timeout_s=0.3)
        with pytest.raises(StoreLockError) as exc:
            st.add(_manual())
        assert erreurs.code_retour(exc.value) == 4
    finally:
        stop(p)
    assert NoteStore(tmp_path).add(_manual())


# ---------------------------------------------------------------------------
# État : prêt seulement avec un historique complet et un panel lisible
# ---------------------------------------------------------------------------


def _complete_history(boc: Path, today: dt.date) -> None:
    """Marque comme « sans bulletin » (anciens marqueurs vides) tous les jours ouvrés sans BOC depuis 2017."""
    have = {p.name[4:12] for p in boc.glob("boc_*.txt.gz")}
    for d in bd.weekdays(bd.HISTORY_START, today - dt.timedelta(days=bd.RECENT_DAYS + 1)):
        if f"{d:%Y%m%d}" not in have:
            (boc / f"boc_{d:%Y%m%d}.missing").touch()


def test_state_is_ready_only_with_a_complete_history_and_a_readable_panel(tmp_path):
    from brvm_alpha import etat

    boc = tmp_path / "boc"
    shutil.copytree(BOC_FIX, boc)
    panel = tmp_path / "panel"
    store.build_panel(boc, panel, workers=1)
    now = pd.Timestamp("2026-10-30 12:00", tz="UTC")
    st = etat.collect_state(panel_dir=panel, boc_dir=boc, notes_root=tmp_path / "notes", now=now, data_dir=tmp_path)
    assert st["pret"] is False and st["historique_complet"] is False
    assert st["raison"].startswith("historique incomplet : ") and st["bulletins"]["jours_manquants"] > 2000
    _complete_history(boc, now.date())
    st = etat.collect_state(panel_dir=panel, boc_dir=boc, notes_root=tmp_path / "notes", now=now, data_dir=tmp_path)
    assert st["pret"] is True and st["raison"] is None and st["historique_complet"] is True
    assert "Prêt : oui (panel lisible, historique complet" in etat.format_text(st)
    # un bulletin plus récent que le panel : le panel ne couvre plus les bulletins
    shutil.copy(BOC_FIX / "boc_20261029.txt.gz", boc / "boc_20261030.txt.gz")
    st = etat.collect_state(panel_dir=panel, boc_dir=boc, notes_root=tmp_path / "notes", now=now, data_dir=tmp_path)
    assert st["pret"] is False and st["raison"].startswith("panel à reconstruire")
    (boc / "boc_20261030.txt.gz").unlink()
    # table des actions abîmée : panel illisible, pas prêt
    (panel / "equities.parquet").write_bytes((panel / "equities.parquet").read_bytes()[:200])
    st = etat.collect_state(panel_dir=panel, boc_dir=boc, notes_root=tmp_path / "notes", now=now, data_dir=tmp_path)
    assert st["pret"] is False and st["raison"].startswith("panel illisible : equities.parquet")
    assert st["panel"]["lisible"] is False


def test_state_counts_markers_to_retry(tmp_path):
    from brvm_alpha import etat

    boc = tmp_path / "boc"
    boc.mkdir()
    bd.ecrire_marqueur(boc, dt.date(2026, 11, 2), [("pas_un_pdf", 200, "u")])
    (boc / "boc_20261103.missing").touch()
    b = etat.bulletins_state(boc, TODAY)
    assert b["a_reessayer"] == 1 and b["sans_bulletin_definitif"] == 1 and b["sans_bulletin"] == 2


# ---------------------------------------------------------------------------
# Fichiers livrés, dépendances facultatives
# ---------------------------------------------------------------------------


def test_missing_shipped_validation_file_is_a_clear_error_in_embedded_mode(tmp_path, monkeypatch):
    from brvm_alpha import settings
    from brvm_alpha.portfolio import recommend as rec

    assert settings.missing_shipped_files() == []
    assert len(settings.missing_shipped_files(tmp_path)) == 3
    with pytest.raises(erreurs.ConfigurationError, match="metrics.json"):
        settings.check_shipped_files(validation_dir=tmp_path)
    monkeypatch.setenv(paths.ENV_EMBARQUE, "1")
    with pytest.raises(erreurs.ConfigurationError, match="metrics.json"):
        rec.choose_variant(validation_dir=tmp_path)
    monkeypatch.delenv(paths.ENV_EMBARQUE)
    assert rec.choose_variant(validation_dir=tmp_path)["statut"]  # hors mode embarqué : repli inchangé


def test_without_statsmodels_validation_stops_cleanly(monkeypatch):
    from brvm_alpha.backtest import metrics as mt
    from brvm_alpha.validation import runner

    monkeypatch.setitem(sys.modules, "statsmodels", None)
    monkeypatch.setitem(sys.modules, "statsmodels.tsa.arima.model", None)
    with pytest.raises(erreurs.ConfigurationError, match="statsmodels"):
        mt.require_statsmodels()
    with pytest.raises(erreurs.ConfigurationError, match="statsmodels"):
        mt.glm_smoothing(pd.Series(range(40), dtype=float) / 100.0)
    with pytest.raises(erreurs.ConfigurationError):
        runner.run_validation(sample="S0", out_dir="/nonexistent/jamais-ecrit")


BLOCKER = r"""
import importlib.abc, json, sys
FORBIDDEN = ("statsmodels", "sklearn", "pdfplumber", "pdfminer")
seen = []
class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in FORBIDDEN:
            seen.append(name)
            raise ImportError(f"module interdit dans les commandes embarquées : {name}")
        return None
sys.meta_path.insert(0, Blocker())
from brvm_alpha import cli
codes = {}
for argv in json.loads(sys.argv[1]):
    try:
        codes[" ".join(argv[:2])] = cli.main(argv)
    except SystemExit as exc:
        codes[" ".join(argv[:2])] = exc.code
print("RESULTAT=" + json.dumps({"interdits": seen, "codes": codes}))
"""


def test_embedded_commands_never_import_statsmodels_sklearn_or_pdfplumber(tmp_path):
    """Exécuté avec l'interpréteur du jeu minimal si ``BRVM_ALPHA_PYTHON_MINIMAL`` le désigne (sinon celui des essais)."""
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    shutil.copytree(BOC_FIX, data / "boc_text")
    reports.mkdir()
    py = os.environ.get("BRVM_ALPHA_PYTHON_MINIMAL") or sys.executable
    commands = [["panel"], ["etat", "--format", "json"], ["update", "--simulation"],
                ["notes", "add", "--cible", "SNTS", "--titre", "Sonatel : avis", "--avis", "haussier", "--conviction", "3"],
                ["notes", "list"], ["notes", "analyze", "--texte", "Résultat net en hausse de 12 %."],
                ["notes", "research", "--hors-ligne", "--sans-boc"], ["notes", "lire", "--hors-ligne"],
                ["indices"], ["explain", "SNTS"], ["report", "--capital", "10000000"]]
    env = {k: v for k, v in os.environ.items() if not k.startswith("BRVM_ALPHA_")}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", paths.ENV_EMBARQUE: "1", paths.ENV_DATA: str(data),
                paths.ENV_REPORTS: str(reports), "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9"})
    r = subprocess.run([py, "-c", BLOCKER, json.dumps(commands)], cwd=str(ROOT), capture_output=True, text=True,
                       env=env, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    out = json.loads(r.stdout[r.stdout.rindex("RESULTAT=") + len("RESULTAT="):])
    assert out["interdits"] == [], out
    assert out["codes"]["panel"] == 0 and out["codes"]["etat --format"] == 0 and out["codes"]["notes add"] == 0
    assert out["codes"]["notes list"] == 0 and out["codes"]["update --simulation"] == 0
    assert all(c != 3 for c in out["codes"].values()), out["codes"]
    assert (data / "panel" / "equities.parquet").exists() and (data / "notes" / "notes.jsonl").exists()


# ---------------------------------------------------------------------------
# Mise à jour complète et client autonome
# ---------------------------------------------------------------------------


def test_mettre_a_jour_downloads_then_rebuilds_the_panel_with_the_given_workers(tmp_path, monkeypatch):
    src = BOC_FIX / "boc_20261029.txt.gz"
    body = gzip.decompress(src.read_bytes()).decode("utf-8").partition("\n")[2]
    monkeypatch.setattr(bd, "convert_pdf", lambda content: (body, "pdftotext", "24.02.0"))
    boc = tmp_path / "boc"
    shutil.copytree(BOC_FIX, boc)
    (boc / "boc_20261029.txt.gz").unlink()
    url = bd.BASE_URL.format(date="20261029", suffix="_2")
    seen: dict[str, Any] = {}
    real = store.build_panel

    def spy(*a, **k):
        seen.update(k)
        return real(*a, **k)

    monkeypatch.setattr(store, "build_panel", spy)
    bilan = bd.mettre_a_jour(boc, tmp_path / "panel", start=dt.date(2026, 10, 27), end=dt.date(2026, 10, 30),
                             today=TODAY, workers=1, fetcher=fake_fetch({url: (200, b"%PDF-1.4")}),
                             cache_dir=tmp_path / "cache")
    d = bilan.to_dict()
    assert d["bulletins_telecharges"] == 1 and d["panel_reconstruit"] is True and seen["workers"] == 1
    assert d["panel"]["derniere_seance"] == "2026-10-29" and d["arret"] is False and d["jours_restants"] == 0
    json.dumps(d)
    from brvm_alpha.notes import research as rs

    (tmp_path / "cache").mkdir(exist_ok=True)
    (tmp_path / "cache" / rs.POLITENESS_STATE).write_text(json.dumps(
        {"hosts": {"www.brvm.org": {"blocked": {"ts": "2026-11-20T10:00:00+00:00", "status": 429}}}}))
    with pytest.raises(bd.DownloadStopped) as exc:
        bd.mettre_a_jour(boc, tmp_path / "panel", today=TODAY, cache_dir=tmp_path / "cache")
    assert exc.value.raison == "bloque" and erreurs.code_retour(exc.value) == 5


def test_standalone_fetcher_goes_through_the_common_client(monkeypatch):
    from brvm_alpha import net

    calls: list[tuple[str, str]] = []

    def get(self, url, *, en_tetes=None, nature="page", suivre=0, delai_lecture=None):
        calls.append((url, nature))
        assert self.politique.refus("https://evil.example/") and suivre == 0
        if url.endswith("robots.txt"):
            return net.Reponse(200, b"User-agent: *\nCrawl-delay: 10\n", {}, url)
        raise net.ReponseTropGrosse("trop gros")

    monkeypatch.setattr(net.ClientHttp, "get", get)
    f = bd.PoliteFetcher(sleep=lambda s: None, clock=lambda: 0.0)
    with pytest.raises(bd.ReponseInexploitable) as exc:
        f(bd.BASE_URL.format(date="20261029", suffix="_2"))
    assert exc.value.statut == "trop_gros" and [n for _, n in calls] == ["robots", "pdf"]
    with pytest.raises(bd.DownloadStopped):
        f("https://evil.example/boc.pdf")
