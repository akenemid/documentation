"""Serveur de l'interface web locale : ``http.server`` + ``ThreadingHTTPServer``, lié à 127.0.0.1.

Sécurité (aucune authentification : l'interface est réservée à la machine locale) :

- **adresse d'écoute** : 127.0.0.1 (ou une autre adresse de bouclage) ; toute autre adresse est
  refusée sauf ``allow_remote=True`` (option ``--hote`` de ``serve``, avec avertissement) ;
- **en-tête Host vérifié** (``localhost``, ``127.0.0.1``, ``[::1]`` et le port du serveur) : une
  requête d'un autre nom (rebinding DNS) reçoit 400 ;
- **jeton anti-CSRF** (aléatoire, propre à chaque lancement) exigé sur **chaque POST** ; en-têtes
  ``Origin`` / ``Sec-Fetch-Site`` d'un autre site refusés (403) ;
- corps limité à :data:`MAX_BODY_BYTES` (413 au-delà, 411 sans ``Content-Length``), seul
  ``application/x-www-form-urlencoded`` est accepté (415), nombre de champs borné ;
- échappement HTML systématique (:mod:`.pages`), politique CSP stricte (script autorisé par nonce,
  aucune ressource externe), ``X-Frame-Options``, ``nosniff``, ``no-referrer``, ``no-store`` ;
- aucune exécution de commande système ; **aucun chemin de fichier tiré de l'entrée** : les fichiers
  servis (rapports) sont choisis dans la liste ``reports/*.html`` dressée par le serveur, les
  rapports régénérés sont écrits sous un nom construit à partir de la date du panel.

Les opérations longues (recherche, rapport, ordre de bataille) tournent dans **un** fil de travail
(:class:`JobManager`) avec suivi d'état (statut, progression, journal) ; une seule à la fois.

**Deux instants** : la date des cours est celle du dernier BOC ; quand la date demandée est la
dernière séance du panel (ou vide), l'interface travaille en **mode direct** : les notes connues à
l'instant de la requête (horloge de :class:`Services`, remplaçable dans les tests) sont appliquées
à la séance suivante (indices, dossier, explication, ordre de bataille, rapport, pages Notes et
Tableau de bord). Une date passée reste en mode historique (règle stricte, sans anticipation).
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import socket
import threading
import traceback
import warnings
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pandas as pd

from brvm_alpha import cli
from brvm_alpha.ui import pages as P

MAX_BODY_BYTES = 256 * 1024
MAX_FIELDS = 64
MAX_QUERY_FIELDS = 32
JOB_LOG_LINES = 400
JOBS_KEPT = 20
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = cli.DEFAULT_PORT
LOCAL_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
RESEARCH_MAX_REQUESTS = 150
#: Lecture du contenu des documents après une recherche : nombre par défaut et maximum.
RESEARCH_MAX_DOCS_DEFAULT = 20
RESEARCH_MAX_DOCS = 60
_ID_RE = re.compile(r"^[0-9a-f]{4,64}$")
_JOB_RE = re.compile(r"^[0-9a-f]{16}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,8}$")
_REPORT_NAME_RE = re.compile(r"^[\w.\-]{1,120}\.html$")


def _now_txt() -> str:
    return pd.Timestamp.now(tz="UTC").strftime("%d/%m/%Y %H:%M:%S UTC")


# ---------------------------------------------------------------------------
# Travaux
# ---------------------------------------------------------------------------


class JobBusy(RuntimeError):
    """Une opération longue est déjà en cours (une seule à la fois)."""


class Job:
    """Opération longue suivie : statut (``en attente``, ``en cours``, ``terminé``, ``échec``), journal, résultat."""

    def __init__(self, kind: str, label: str) -> None:
        self.id = secrets.token_hex(8)
        self.kind = kind
        self.label = label
        self.status = "en attente"
        self.created = _now_txt()
        self.started: str | None = None
        self.finished: str | None = None
        self.progress = ""
        self.result: Any = None
        self.error: str | None = None
        self._log: deque[str] = deque(maxlen=JOB_LOG_LINES)
        self._lock = threading.Lock()
        self.done = threading.Event()

    def log(self, message: Any) -> None:
        """Ajoute une ligne au journal (et met à jour la progression)."""
        msg = str(message)
        stamp = pd.Timestamp.now(tz="UTC").strftime("%H:%M:%S")
        with self._lock:
            for line in msg.splitlines() or [""]:
                self._log.append(f"{stamp}  {line}")
            self.progress = msg.splitlines()[0][:240] if msg.strip() else self.progress

    @property
    def finished_ok(self) -> bool:
        return self.status == "terminé"

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            journal = list(self._log)
        return {"id": self.id, "type": self.kind, "libelle": self.label, "statut": self.status,
                "progression": self.progress, "journal": journal, "debut": self.started or self.created,
                "fin": self.finished, "erreur": self.error, "termine": self.status in ("terminé", "échec")}


class JobManager:
    """Exécute **une** opération longue à la fois dans un fil de travail (démon)."""

    def __init__(self, keep: int = JOBS_KEPT) -> None:
        self._lock = threading.Lock()
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._current: Job | None = None
        self._threads: list[threading.Thread] = []
        self.keep = keep

    def start(self, kind: str, label: str, fn: Callable[[Job], Any]) -> Job:
        """Lance ``fn(job)`` dans un fil ; :class:`JobBusy` si une opération est en cours."""
        with self._lock:
            cur = self._current
            if cur is not None and cur.status in ("en attente", "en cours"):
                raise JobBusy(f"une opération est déjà en cours : « {cur.label} » ({cur.status}). "
                              "Attendre sa fin avant d'en lancer une autre.")
            job = Job(kind, label)
            self._jobs[job.id] = job
            while len(self._jobs) > self.keep:
                self._jobs.popitem(last=False)
            self._current = job
            th = threading.Thread(target=self._run, args=(job, fn), name=f"brvm-ui-{kind}", daemon=True)
            self._threads = [t for t in self._threads if t.is_alive()] + [th]
        th.start()
        return job

    def _run(self, job: Job, fn: Callable[[Job], Any]) -> None:
        job.status = "en cours"
        job.started = _now_txt()
        job.log(f"début : {job.label}")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                job.result = fn(job)
            job.status = "terminé"
            job.log("terminé")
        except Exception as exc:  # l'erreur est affichée dans la page, jamais propagée au serveur
            job.error = f"{type(exc).__name__} : {exc}"
            job.status = "échec"
            job.log(f"échec : {job.error}")
            for line in traceback.format_exc().splitlines()[-6:]:
                job.log("  " + line)
        finally:
            job.finished = _now_txt()
            job.done.set()

    def get(self, job_id: str | None) -> Job | None:
        if not job_id:
            return None
        with self._lock:
            return self._jobs.get(job_id)

    def current(self) -> Job | None:
        with self._lock:
            return self._current

    def latest(self, kind: str) -> Job | None:
        with self._lock:
            for job in reversed(self._jobs.values()):
                if job.kind == kind:
                    return job
        return None

    def wait(self, job_id: str, timeout: float = 60.0) -> Job | None:
        job = self.get(job_id)
        if job is not None:
            job.done.wait(timeout)
        return job

    def shutdown(self, timeout: float = 2.0) -> None:
        for t in list(self._threads):
            t.join(timeout)


# ---------------------------------------------------------------------------
# Services de calcul (remplaçables dans les tests)
# ---------------------------------------------------------------------------


def _describe_fetch(e: Mapping[str, Any]) -> str:
    """Ligne de journal en français pour un évènement du client poli (``PoliteSession._log``)."""
    ev, url, st = e.get("event"), e.get("url", ""), e.get("status")
    if ev in ("page", "robots", "document"):
        return f"requête {'robots.txt ' if ev == 'robots' else ''}{url} → HTTP {st}"
    return {
        "cache": f"lu dans le cache : {url}",
        "cache_miss": f"absent du cache (hors ligne, aucune requête) : {url}",
        "stop": f"ARRÊT de la collecte : {e.get('reason')}",
        "blocked": f"site bloqué, aucune requête : {e.get('reason')}",
        "quota": f"quota de requêtes atteint ({e.get('n_requests')})",
        "retry": f"nouvel essai dans {e.get('wait_s')} s (HTTP {st})",
        "robots_disallow": f"interdit par robots.txt, page non lue : {url}",
        "redirect": f"redirection {url} → {e.get('location')}",
        "source_disabled": f"source désactivée : {url}",
        "too_many_redirects": f"trop de redirections : {url}",
    }.get(str(ev), f"{ev} {url}")


class Services:
    """Accès aux données et calculs utilisés par les pages (chemins fixés à la construction)."""

    def __init__(self, notes_root: str | Path | None = None, panel_dir: str | Path | None = None,
                 reports_dir: str | Path | None = None, validation_dir: str | Path | None = None,
                 diagnostic_dir: str | Path | None = None, boc_dir: str | Path | None = None,
                 research_kwargs: Mapping[str, Any] | None = None,
                 clock: Callable[[], pd.Timestamp] | None = None) -> None:
        #: horloge UTC de l'interface (instant de connaissance des notes en mode direct) ; injectable
        self.clock: Callable[[], pd.Timestamp] = clock or (lambda: cli.now_utc())
        self._status_cache: OrderedDict[Any, Any] = OrderedDict()
        self.notes_root = Path(notes_root) if notes_root else None
        self.panel_dir = Path(panel_dir) if panel_dir else cli.DEFAULT_PANEL_DIR
        self.reports_dir = Path(reports_dir) if reports_dir else cli.DEFAULT_REPORTS_DIR
        self.validation_dir = Path(validation_dir) if validation_dir else cli.ROOT / "reports" / "validation_S1"
        self.diagnostic_dir = Path(diagnostic_dir) if diagnostic_dir else cli.ROOT / "reports" / "diagnostic_S0"
        self.boc_dir = Path(boc_dir) if boc_dir else cli.DEFAULT_BOC_DIR
        self.research_kwargs = dict(research_kwargs or {})
        self._lock = threading.RLock()
        self._store: Any = None
        self._panels: Any = None
        self._panels_key: Any = None
        self._names: tuple[Any, dict[str, str]] | None = None
        self._idx_cache: OrderedDict[Any, Any] = OrderedDict()

    # -- notes -------------------------------------------------------------
    def notes_store(self) -> Any:
        with self._lock:
            if self._store is None:
                from brvm_alpha.notes.store import NoteStore

                self._store = NoteStore(self.notes_root) if self.notes_root else NoteStore()
            return self._store

    def _notes_key(self) -> Any:
        p = Path(self.notes_store().path)
        try:
            st = p.stat()
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    # -- panel -------------------------------------------------------------
    def _panel_key(self) -> Any:
        try:
            return (self.panel_dir / "equities.parquet").stat().st_mtime_ns
        except OSError:
            return None

    def last_session(self) -> pd.Timestamp | None:
        return cli.last_session(self.panel_dir)

    def symbol_names(self) -> dict[str, str]:
        key = self._panel_key()
        with self._lock:
            if self._names is not None and self._names[0] == key:
                return self._names[1]
        names: dict[str, str] = {}
        if key is not None:
            try:
                eq = pd.read_parquet(self.panel_dir / "equities.parquet", columns=["date", "symbol", "name"])
                last = eq.sort_values("date").groupby("symbol")["name"].last()
                names = {str(k): str(v) for k, v in last.items() if isinstance(v, str)}
            except Exception:
                names = {}
        with self._lock:
            self._names = (key, names)
        return names

    def strategy_panels(self) -> Any:
        key = self._panel_key()
        with self._lock:
            if self._panels is not None and self._panels_key == key:
                return self._panels
            from brvm_alpha.strategy import build_panels

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._panels = build_panels(self.panel_dir)
            self._panels_key = key
            return self._panels

    # -- deux instants : date des cours et instant de connaissance des notes ------
    def notes_instant(self, asof: Any = None) -> pd.Timestamp | None:
        """Instant de connaissance des notes pour ``asof`` : maintenant (mode direct) si ``asof`` est
        vide ou n'est pas antérieure à la dernière séance du panel ; ``None`` (mode historique) sinon."""
        try:
            return cli.notes_instant(asof, None, self.panel_dir, last=self.last_session(), now=self.clock())
        except Exception:
            return None

    def _moment_key(self, asof: Any, known: Any) -> Any:
        """Clé de cache d'un calcul daté : la séance d'application suffit (le journal a sa propre clé)."""
        if known is None:
            return None
        try:
            from brvm_alpha.notes import signals as sg

            return str(sg.notes_moment(asof, known).session.date())
        except Exception:
            return str(known)

    def notes_status(self, asof: Any = None) -> dict[str, Any] | None:
        """État daté des notes (ligne « Notes connues au … », notes en vigueur, filtres actifs).

        ``asof`` vide : dernière séance du panel (mode direct). ``None`` si le journal ou le panel
        manquent ; ne lève jamais (une erreur est rendue dans la ligne).
        """
        store = self._notes_for_eval()
        t = pd.Timestamp(asof) if asof is not None else self.last_session()
        if store is None or t is None:
            return None
        known = self.notes_instant(t)
        key = (str(t.date()), self._panel_key(), self._notes_key(), self._moment_key(t, known))
        with self._lock:
            if key in self._status_cache:
                return self._status_cache[key]
        cal: Any = None
        eq: Any = None
        try:
            if (self.panel_dir / "sessions.parquet").exists():
                cal = pd.read_parquet(self.panel_dir / "sessions.parquet")
            if (self.panel_dir / "equities.parquet").exists():
                eq = str(self.panel_dir)
        except Exception:
            cal, eq = None, None
        out = cli.notes_status(store, t, known, calendar=cal, equities=eq)
        with self._lock:
            self._status_cache[key] = out
            while len(self._status_cache) > 8:
                self._status_cache.popitem(last=False)
        return out

    # -- indices -------------------------------------------------------------
    def _notes_for_eval(self) -> Any:
        store = self.notes_store()
        return store if Path(store.path).exists() else None

    def evaluate_indices(self, asof: Any) -> tuple[pd.DataFrame, bool]:
        from brvm_alpha.notes import index_eval

        store = self._notes_for_eval()
        known = self.notes_instant(asof) if store is not None else None
        key = (str(asof), self._panel_key(), self._notes_key() if store is not None else None,
               self._moment_key(asof, known))
        with self._lock:
            if key in self._idx_cache:
                return self._idx_cache[key]
        panels = index_eval.load_panels(self.panel_dir)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ev = index_eval.evaluate_indices(panels=panels, store=store, asof=asof, notes_known_at=known)
        out = (ev, store is not None)
        with self._lock:
            self._idx_cache[key] = out
            while len(self._idx_cache) > 8:
                self._idx_cache.popitem(last=False)
        return out

    def index_dossier(self, code: str, asof: Any) -> dict[str, Any]:
        from brvm_alpha.notes import index_eval

        panels = index_eval.load_panels(self.panel_dir)
        store = self._notes_for_eval()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return index_eval.index_dossier(code, panels=panels, store=store, asof=asof,
                                            notes_known_at=self.notes_instant(asof) if store is not None else None)

    # -- explication, ordre de bataille, rapport -------------------------------
    def explain(self, symbol: str, asof: Any, variant: str | None) -> dict[str, Any]:
        notes: Any = self.notes_store() if self.notes_root else "auto"
        return cli.explain_symbol(symbol, asof, variant=variant, notes=notes, panels=self.strategy_panels(),
                                  notes_known_at=self.notes_instant(asof))

    def recommend(self, *, asof: Any, capital: float, holdings: Mapping[str, int] | None, cash: float | None,
                  variant: str | None, n_boot: int, log: Callable[[str], None]) -> Any:
        from brvm_alpha.portfolio import recommend as rec

        log(f"ordre de bataille au {cli.fr_date(asof)} pour {cli.fr_num(capital, 0)} FCFA ({n_boot} tirages)…")
        known = self.notes_instant(asof)
        log(f"notes : connues au {known:%d/%m/%Y %H:%M} UTC, appliquées à la séance suivante (mode direct)"
            if known is not None else "notes : mode historique (règle stricte à la date demandée, sans anticipation)")
        return rec.recommend(asof, capital, holdings=holdings or None, cash=cash, variant=variant, n_boot=n_boot,
                             notes_store=self.notes_store() if self.notes_root else None,
                             panel_dir=self.panel_dir, validation_dir=self.validation_dir, notes_known_at=known)

    def report_target(self, asof: Any) -> Path:
        """Chemin du rapport régénéré : construit à partir de la date (jamais d'une saisie)."""
        return self.reports_dir / f"rapport_{pd.Timestamp(asof):%Y-%m-%d}.html"

    def build_report(self, *, asof: Any, capital: float, log: Callable[[str], None]) -> Path:
        from brvm_alpha.report import build_report

        out = self.report_target(asof)
        log(f"rapport au {cli.fr_date(asof)} pour {cli.fr_num(capital, 0)} FCFA → {out.name}")
        known = self.notes_instant(asof)
        log(f"notes : connues au {known:%d/%m/%Y %H:%M} UTC, appliquées à la séance suivante (mode direct)"
            if known is not None else "notes : mode historique (règle stricte à la date demandée, sans anticipation)")
        return build_report(asof, capital, out, panel_dir=self.panel_dir,
                            notes_root=self.notes_root or "data/notes", validation_dir=self.validation_dir,
                            diagnostic_dir=self.diagnostic_dir, notes_known_at=known)

    # -- recherche --------------------------------------------------------------
    def run_research(self, *, offline: bool, max_requests: int, targets: list[str] | None, since: Any,
                     log: Callable[[str], None], read_docs: bool = False, max_docs: int = 20) -> dict[str, Any]:
        """Recherche (listes de www.brvm.org ou cache, BOC locaux) puis, si ``read_docs``, lecture du
        contenu d'au plus ``max_docs`` documents récents (``notes.research.enrich_documents``)."""
        from brvm_alpha.notes import research as rs

        store = self.notes_store()
        root = Path(store.root)

        class _LoggedSession(rs.PoliteSession):
            def _log(self, **entry: Any) -> None:
                super()._log(**entry)
                try:
                    log(_describe_fetch(entry))
                except Exception:  # pragma: no cover - le journal ne bloque jamais la collecte
                    pass

        kw: dict[str, Any] = {"boc_dir": self.boc_dir, "panel_dir": self.panel_dir}
        kw.update(self.research_kwargs)
        injected = kw.pop("session", None)
        sess = injected or _LoggedSession(delay_s=10.0, max_requests=max_requests, offline=offline,
                                          cache_dir=root / "cache", log_path=root / "fetch_log.jsonl")
        log(("hors ligne : cache disque et BOC locaux, aucune requête réseau" if offline else
             f"en ligne : au plus {max_requests} requêtes vers www.brvm.org, au moins 10 s entre deux"))
        res = rs.run_research(store, targets=targets, since=since, max_requests=max_requests, offline=offline,
                              session=sess, **kw)
        summary = res.report.summary()
        log(summary)
        out = {"resume": summary, "notes": [n.note_id for n in res], "arret": res.report.stopped,
               "requetes": res.report.n_requests, "documents": None}
        if read_docs and int(max_docs) > 0:
            if res.report.stopped and not offline:
                log("lecture du contenu des documents : non lancée (collecte arrêtée, aucune autre requête)")
            else:
                log(f"lecture du contenu d'au plus {int(max_docs)} document(s) récent(s)"
                    + (" (hors ligne : cache seulement)" if offline else " (au moins 10 s entre deux requêtes)"))
                # Même panel (calendrier des séances) que la collecte : celui de l'interface, pas celui du dépôt.
                # Session propre à la lecture (quota : un document par requête, plus robots.txt), journalisée
                # comme la collecte : chaque téléchargement apparaît dans le journal de la tâche.
                doc_sess = injected or _LoggedSession(delay_s=10.0, max_requests=int(max_docs) + 10, offline=offline,
                                                      cache_dir=root / "cache", log_path=root / "fetch_log.jsonl")
                rep, lines = cli.run_enrich(store, max_docs=int(max_docs), targets=targets, offline=offline,
                                            panel_dir=kw.get("panel_dir", self.panel_dir), session=doc_sess)
                for line in lines:
                    log(line)
                out["documents"] = {"bilan": rep, "lignes": lines}
        return out

    def blocked_hosts(self) -> dict[str, Any]:
        try:
            from brvm_alpha.notes import research as rs

            return rs.blocked_hosts(Path(self.notes_store().root) / "cache")
        except Exception:
            return {}

    # -- validation et rapports ------------------------------------------------------
    def read_validation(self) -> dict[str, Any] | None:
        try:
            from brvm_alpha.report.html import read_validation

            return read_validation(self.validation_dir, sample="S1")
        except Exception:
            return None

    def choose_variant(self) -> dict[str, Any] | None:
        try:
            from brvm_alpha.portfolio import recommend as rec

            return rec.choose_variant(validation_dir=self.validation_dir)
        except Exception:
            return None

    def read_text(self, which: str) -> str | None:
        """Texte d'un fichier de résultats **connu** (``s1``, ``tentatives``, ``s0``)."""
        path = {"s1": self.validation_dir / "resultats.md", "tentatives": self.validation_dir / "tentatives.md",
                "s0": self.diagnostic_dir / "resultats.md"}.get(which)
        if path is None or not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def list_reports(self) -> list[dict[str, Any]]:
        """Rapports HTML de ``reports/`` (du plus récent au plus ancien)."""
        if not self.reports_dir.is_dir():
            return []
        items = []
        for p in self.reports_dir.glob("*.html"):
            if not p.is_file() or not _REPORT_NAME_RE.match(p.name):
                continue
            st = p.stat()
            items.append({"nom": p.name, "chemin": p, "mtime": st.st_mtime,
                          "modifie": pd.Timestamp(st.st_mtime, unit="s", tz="UTC").strftime("%d/%m/%Y %H:%M UTC"),
                          "taille": f"{st.st_size / 1024:.0f} Ko"})
        return sorted(items, key=lambda d: d["mtime"], reverse=True)

    def report_path(self, name: str | None) -> Path | None:
        """Rapport choisi **dans la liste** du serveur (le nom saisi n'est jamais un chemin)."""
        reps = self.list_reports()
        if not reps:
            return None
        if not name:
            return reps[0]["chemin"]
        for r in reps:
            if r["nom"] == name:
                return r["chemin"]
        return None


# ---------------------------------------------------------------------------
# Serveur HTTP
# ---------------------------------------------------------------------------


#: Délai d'expiration (s) de la lecture des en-têtes et du corps d'une connexion (revue produit du
#: 22/11/2026 : un corps annoncé jamais envoyé bloquait un fil indéfiniment).
REQUEST_TIMEOUT_S = 20.0
#: Connexions traitées simultanément au plus (au-delà : refus immédiat, connexion fermée).
MAX_CONNECTIONS = 32


class UIServer(ThreadingHTTPServer):
    """Serveur de l'interface (un fil par requête, plus un fil de travail pour les opérations longues).

    Les connexions simultanées sont bornées (:data:`MAX_CONNECTIONS`, sémaphore dans
    :meth:`process_request`) et chaque connexion expire après :data:`REQUEST_TIMEOUT_S` secondes
    d'inactivité (``Handler.timeout``) : aucun fil ne reste bloqué sur un corps jamais envoyé.
    """

    daemon_threads = True
    allow_reuse_address = True
    max_connections = MAX_CONNECTIONS

    def __init__(self, address: tuple[str, int], *, services: Services | None = None, allow_remote: bool = False):
        host = address[0]
        if not cli.is_loopback(host) and not allow_remote:
            raise ValueError(f"adresse d'écoute refusée : {host} (127.0.0.1 uniquement ; option --hote explicite "
                             "pour une autre adresse)")
        if ":" in host:
            self.address_family = socket.AF_INET6
        super().__init__(address, Handler)
        self.services = services or Services()
        self.jobs = JobManager()
        self.csrf_token = secrets.token_urlsafe(32)
        self.allow_remote = allow_remote
        self.port = int(self.server_address[1])
        names = set(LOCAL_NAMES)
        if allow_remote:
            names.add(host.strip("[]").lower())
        self.allowed_names = frozenset(names)
        self.last_results: dict[str, Any] = {}
        self._slots = threading.BoundedSemaphore(int(self.max_connections))

    def process_request(self, request: Any, client_address: Any) -> None:
        """Un fil par connexion, dans la limite de ``max_connections`` (au-delà : connexion fermée)."""
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def shutdown_jobs(self) -> None:
        self.jobs.shutdown()


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *, allow_remote: bool = False,
                services: Services | None = None) -> UIServer:
    """Crée le serveur (``port=0`` : port libre) ; ``ValueError`` pour une adresse non locale sans ``allow_remote``."""
    return UIServer((host, int(port)), services=services, allow_remote=allow_remote)


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *, allow_remote: bool = False,
          services: Services | None = None) -> None:  # pragma: no cover - boucle bloquante
    srv = make_server(host, port, allow_remote=allow_remote, services=services)
    try:
        srv.serve_forever()
    finally:
        srv.shutdown_jobs()
        srv.server_close()


class HTTPError(Exception):
    def __init__(self, status: int, title: str, message: str):
        super().__init__(message)
        self.status, self.title, self.message = status, title, message


def _first(form: Mapping[str, list[str]], name: str, default: str = "") -> str:
    v = form.get(name)
    return v[0] if v else default


class Handler(BaseHTTPRequestHandler):
    """Routage et sécurité des requêtes."""

    server: UIServer
    server_version = "BRVMAlpha"
    sys_version = ""
    protocol_version = "HTTP/1.0"
    #: Expiration des lectures sur la connexion (en-têtes et corps) : ``socket.settimeout`` dans ``setup``.
    timeout = REQUEST_TIMEOUT_S

    # -- journal discret -----------------------------------------------------
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature de la bibliothèque
        if getattr(self.server, "quiet", True):
            return
        super().log_message(format, *args)  # pragma: no cover

    # -- réponses ----------------------------------------------------------------
    def _headers(self, nonce: str | None, *, report: bool = False) -> dict[str, str]:
        if report:
            csp = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
                   "form-action 'none'; base-uri 'none'; frame-ancestors 'self'; "
                   "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox")
            frame = "SAMEORIGIN"
        else:
            csp = (f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                   "img-src 'self' data:; connect-src 'self'; form-action 'self'; frame-src 'self'; "
                   "frame-ancestors 'none'; base-uri 'none'")
            frame = "DENY"
        return {"Content-Security-Policy": csp, "X-Frame-Options": frame, "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
                "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Resource-Policy": "same-origin",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()"}

    def _send(self, status: int, body: str | bytes, content_type: str = "text/html; charset=utf-8", *,
              nonce: str | None = None, report: bool = False, extra: Mapping[str, str] | None = None) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for k, v in self._headers(nonce or secrets.token_urlsafe(12), report=report).items():
            self.send_header(k, v)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _ctx(self) -> P.PageContext:
        return P.PageContext(token=self.server.csrf_token, nonce=secrets.token_urlsafe(16))

    def _page(self, status: int, render: Callable[[P.PageContext], str]) -> None:
        ctx = self._ctx()
        self._send(status, render(ctx), nonce=ctx.nonce)

    def _error(self, status: int, title: str, message: str) -> None:
        self._page(status, lambda ctx: P.error_page(ctx, status, title, message))

    def _redirect(self, location: str) -> None:
        # ``location`` est toujours un chemin interne construit par le serveur.
        if not location.startswith("/") or location.startswith("//"):
            location = "/"
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        for k, v in self._headers(secrets.token_urlsafe(12)).items():
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()

    # -- contrôles -------------------------------------------------------------------
    def _check_host(self) -> bool:
        raw = (self.headers.get("Host") or "").strip().lower()
        m = re.fullmatch(r"(\[[0-9a-f:.]+\]|[a-z0-9.\-]+)(?::(\d{1,5}))?", raw)
        if not m:
            return False
        name, port = m.group(1).strip("[]"), m.group(2)
        if name not in self.server.allowed_names:
            return False
        return (int(port) if port else 80) == self.server.port

    def _check_origin(self) -> bool:
        site = (self.headers.get("Sec-Fetch-Site") or "").lower()
        if site and site not in ("same-origin", "none"):
            return False
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        try:
            u = urlsplit(origin)
        except ValueError:
            return False
        host = (u.hostname or "").lower()
        return u.scheme == "http" and host in self.server.allowed_names and (u.port or 80) == self.server.port

    def _query(self) -> tuple[str, dict[str, list[str]]]:
        parts = urlsplit(self.path)
        try:
            qs = parse_qs(parts.query, keep_blank_values=True, max_num_fields=MAX_QUERY_FIELDS)
        except ValueError as exc:
            raise HTTPError(400, "Requête invalide", "trop de paramètres dans l'adresse") from exc
        return parts.path, qs

    def _read_form(self) -> dict[str, list[str]]:
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        length_s = self.headers.get("Content-Length")
        if length_s is None:
            raise HTTPError(411, "Longueur requise", "en-tête Content-Length absent")
        try:
            length = int(length_s)
        except ValueError as exc:
            raise HTTPError(400, "Requête invalide", "Content-Length invalide") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise HTTPError(413, "Corps trop volumineux",
                            f"le formulaire dépasse {MAX_BODY_BYTES // 1024} Ko (texte trop long ?)")
        if ctype != "application/x-www-form-urlencoded":
            raise HTTPError(415, "Type non pris en charge", "formulaire attendu (application/x-www-form-urlencoded)")
        try:
            raw = self.rfile.read(length) if length else b""
        except (TimeoutError, OSError) as exc:  # corps annoncé jamais envoyé : la connexion expire
            self.close_connection = True
            raise HTTPError(408, "Délai dépassé", f"corps de la requête non reçu en {REQUEST_TIMEOUT_S:g} s") from exc
        if len(raw) < length:
            self.close_connection = True
            raise HTTPError(400, "Requête invalide", "corps de la requête incomplet")
        try:
            text = raw.decode("utf-8")
            return parse_qs(text, keep_blank_values=True, max_num_fields=MAX_FIELDS, strict_parsing=False)
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPError(400, "Requête invalide", "formulaire illisible (UTF-8 attendu, champs en nombre limité)") \
                from exc

    def _check_csrf(self, form: Mapping[str, list[str]]) -> bool:
        tok = _first(form, "_jeton")
        return bool(tok) and hmac.compare_digest(tok.encode("utf-8"), self.server.csrf_token.encode("utf-8"))

    # -- verbes ---------------------------------------------------------------------------
    def do_HEAD(self) -> None:  # noqa: N802 - API de la bibliothèque
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        if not self._check_host():
            self._send(400, "Hôte refusé : interface réservée à localhost / 127.0.0.1.", "text/plain; charset=utf-8")
            return
        try:
            path, qs = self._query()
            route = GET_ROUTES.get(path)
            if route is None:
                raise HTTPError(404, "Page introuvable", f"aucune page à l'adresse {path}")
            route(self, qs)
        except HTTPError as exc:
            self._error(exc.status, exc.title, exc.message)
        except Exception as exc:  # erreur imprévue : page lisible, pas de trace exposée hors du journal
            self._error(500, "Erreur interne", f"{type(exc).__name__} : {exc}")

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_host():
            self._send(400, "Hôte refusé : interface réservée à localhost / 127.0.0.1.", "text/plain; charset=utf-8")
            return
        try:
            if not self._check_origin():
                raise HTTPError(403, "Requête refusée", "requête venue d'un autre site (Origin / Sec-Fetch-Site)")
            path, _qs = self._query()
            route = POST_ROUTES.get(path)
            if route is None:
                raise HTTPError(404, "Page introuvable", f"aucune action à l'adresse {path}")
            form = self._read_form()
            if not self._check_csrf(form):
                raise HTTPError(403, "Requête refusée", "jeton anti-CSRF absent ou invalide : recharger la page et "
                                                         "recommencer")
            route(self, form)
        except HTTPError as exc:
            self._error(exc.status, exc.title, exc.message)
        except Exception as exc:
            self._error(500, "Erreur interne", f"{type(exc).__name__} : {exc}")

    def _not_allowed(self) -> None:
        self._send(405, "Méthode non autorisée.", "text/plain; charset=utf-8", extra={"Allow": "GET, HEAD, POST"})

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_TRACE = do_CONNECT = _not_allowed  # noqa: N815


# ---------------------------------------------------------------------------
# Pages (GET)
# ---------------------------------------------------------------------------


def _qv(qs: Mapping[str, list[str]], name: str) -> str:
    v = qs.get(name)
    return v[0].strip()[:500] if v else ""


def _opt_date(value: str, what: str) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        t = cli.parse_date(value)
    except ValueError as exc:
        raise ValueError(f"{what} : {exc}") from exc
    return t


def _job_view(job: Job | None) -> dict[str, Any] | None:
    return job.snapshot() if job is not None else None


def _records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or not len(df):
        return []
    return [{k: P._val(v) for k, v in r.items()} for r in df.to_dict(orient="records")]


def get_dashboard(h: Handler, qs: Mapping[str, list[str]]) -> None:
    s = h.server.services
    store = s.notes_store()
    df = store.list(status="active")
    recent = _records(df.sort_values("published_at", ascending=False).head(5)) if len(df) else []
    job = h.server.jobs.latest("rapport")
    flash = None
    if _qv(qs, "lance"):
        flash = ("info", "Régénération du rapport lancée : suivi ci-dessous.")
    status = _safe(s.notes_status)
    h._page(200, lambda ctx: P.page_dashboard(
        ctx, last_session=s.last_session(), validation=s.read_validation(), choice=s.choose_variant(),
        reports=s.list_reports(), job=_job_view(job), recent_notes=recent, flash=flash, notes_status=status))


def _safe(fn: Callable[..., Any], *args: Any) -> Any:
    """Résultat de ``fn(*args)``, ou ``None`` si le calcul échoue (une page ne tombe jamais pour une synthèse)."""
    try:
        return fn(*args)
    except Exception:
        return None


def get_report(h: Handler, qs: Mapping[str, list[str]]) -> None:
    name = _qv(qs, "nom")
    path = h.server.services.report_path(name or None)
    if path is None:
        raise HTTPError(404, "Rapport introuvable", "aucun rapport de ce nom dans reports/")
    h._send(200, path.read_bytes(), report=True)


def _note_filters(qs: Mapping[str, list[str]]) -> dict[str, str]:
    return {"cible": _qv(qs, "cible"), "depuis": _qv(qs, "depuis"), "texte": _qv(qs, "texte"),
            "statut": _qv(qs, "statut") or "actives"}


def _render_notes(h: Handler, status: int, filters: Mapping[str, str], *, form_values: Mapping[str, Any] | None = None,
                  form_error: Any = None, flash: Any = None) -> None:
    s = h.server.services
    store = s.notes_store()
    statut = {"actives": "active", "archivees": "archived", "toutes": None}.get(filters.get("statut") or "actives", "active")
    err = None
    try:
        since = _opt_date(filters.get("depuis", ""), "date")
        df = store.list(target=filters.get("cible") or None, since=since, status=statut)
    except ValueError as exc:
        err, df = str(exc), store.list(status=statut)
    txt = (filters.get("texte") or "").strip().lower()
    if txt and len(df):
        mask = df["title"].str.lower().str.contains(txt, regex=False) | df["text"].str.lower().str.contains(txt, regex=False)
        df = df[mask]
    if len(df):
        df = df.sort_values("published_at", ascending=False).head(200)
    total = len(store)
    opts = P.target_options(s.symbol_names())
    fl = flash or (("error", err) if err else None)
    # Notes en vigueur à la séance d'application (mode direct) et composante « notes » des indices.
    nstatus = _safe(s.notes_status)
    last = _safe(s.last_session)
    idx = None
    if nstatus and last is not None and not cli.in_s1(last):
        res = _safe(s.evaluate_indices, last)
        idx = res[0] if isinstance(res, tuple) and res else None
    h._page(status, lambda ctx: P.page_notes(ctx, notes=_records(df), filters=filters, options=opts,
                                             form_values=form_values, form_error=form_error,
                                             store_errors=list(store.errors), total=total, flash=fl,
                                             notes_status=nstatus, indices=idx))


def get_notes(h: Handler, qs: Mapping[str, list[str]]) -> None:
    _render_notes(h, 200, _note_filters(qs))


def get_note(h: Handler, qs: Mapping[str, list[str]]) -> None:
    from brvm_alpha.notes.model import EVENT_TYPES, RISK_FLAGS

    nid = _qv(qs, "id").lower()
    if not _ID_RE.match(nid):
        raise HTTPError(400, "Identifiant invalide", "identifiant de note attendu (caractères hexadécimaux)")
    store = h.server.services.notes_store()
    try:
        full = cli.resolve_note_id(store, nid)
    except KeyError as exc:
        raise HTTPError(404, "Note introuvable", str(exc.args[0] if exc.args else exc)) from exc
    note = store.get(full).to_dict()
    allv = store.frame(all_versions=True)
    allv = allv[allv["note_id"] == full].sort_values("version")
    versions = [{"version": int(r["version"]), "recorded_at": cli.fr_date(r["recorded_at"]) + (
        f" {pd.Timestamp(r['recorded_at']):%H:%M}" if pd.notna(r["recorded_at"]) else ""),
        "op": r["op"], "status": r["status"], "title": r["title"], "score": r["score"]}
        for r in allv.to_dict(orient="records")]
    flash = ("ok", "Note enregistrée et analysée.") if _qv(qs, "cree") else (
        ("ok", "Note archivée (nouvelle version ; historique conservé).") if _qv(qs, "archivee") else None)
    h._page(200, lambda ctx: P.page_note(ctx, note=note, versions=versions, risk_labels=RISK_FLAGS,
                                         event_labels=EVENT_TYPES, flash=flash))


def get_research(h: Handler, qs: Mapping[str, list[str]]) -> None:
    _render_research(h, 200)


def _render_research(h: Handler, status: int, *, defaults: Mapping[str, Any] | None = None, error: Any = None,
                     flash: Any = None) -> None:
    s = h.server.services
    job = h.server.jobs.latest("recherche")
    new_notes: list[dict[str, Any]] = []
    if job is not None and job.finished_ok and isinstance(job.result, Mapping):
        ids = set(job.result.get("notes") or [])
        if ids:
            df = s.notes_store().list(status=None)
            new_notes = _records(df[df["note_id"].isin(ids)].sort_values("published_at", ascending=False).head(100))
    docs = None
    if job is not None and job.finished_ok and isinstance(job.result, Mapping):
        d = job.result.get("documents")
        docs = list(d.get("lignes") or []) if isinstance(d, Mapping) else None
    opts = P.target_options(s.symbol_names())
    h._page(status, lambda ctx: P.page_research(ctx, job=_job_view(job), blocked=s.blocked_hosts(),
                                                defaults=defaults, error=error, new_notes=new_notes, flash=flash,
                                                options=opts, documents=docs))


def _asof_or_last(h: Handler, value: str) -> pd.Timestamp | None:
    t = _opt_date(value, "date")
    return t if t is not None else h.server.services.last_session()


def get_indices(h: Handler, qs: Mapping[str, list[str]]) -> None:
    s = h.server.services
    err, ev, inc, asof = None, None, False, None
    try:
        asof = _asof_or_last(h, _qv(qs, "date"))
        if asof is None:
            err = "panel introuvable : lancer « python -m brvm_alpha panel »"
        elif cli.in_s1(asof):
            err = cli.s1_refusal(asof, "l'évaluation des indices")
        else:
            ev, inc = s.evaluate_indices(asof)
    except ValueError as exc:
        err = str(exc)
    status = 400 if err and asof is not None and cli.in_s1(asof) else 200
    nstatus = _safe(s.notes_status, asof) if ev is not None and inc else None
    h._page(status, lambda ctx: P.page_indices(ctx, evaluation=ev, asof=asof, notes_included=inc, error=err,
                                               notes_status=nstatus))


def get_dossier(h: Handler, qs: Mapping[str, list[str]]) -> None:
    from brvm_alpha.notes.model import normalize_target

    raw = _qv(qs, "code")
    code = normalize_target(raw) if raw else None
    if not code or not code.startswith("IDX:"):
        raise HTTPError(400, "Indice inconnu", f"code d'indice attendu (IDX:BRVM-C, IDX:BRVM-30…), lu {raw!r}")
    d, err = None, None
    try:
        asof = _asof_or_last(h, _qv(qs, "date"))
        if asof is None:
            err = "panel introuvable"
        elif cli.in_s1(asof):
            err = cli.s1_refusal(asof, "le dossier d'indice")
        else:
            d = h.server.services.index_dossier(code, asof)
    except ValueError as exc:
        err = str(exc)
    h._page(200 if d is not None else 400, lambda ctx: P.page_dossier(ctx, dossier=d, code=code, error=err))


def get_portfolio(h: Handler, qs: Mapping[str, list[str]]) -> None:
    _render_portfolio(h, 200, qs=qs)


def _render_portfolio(h: Handler, status: int, *, qs: Mapping[str, list[str]] | None = None,
                      values: Mapping[str, Any] | None = None, error: Any = None) -> None:
    jid = _qv(qs or {}, "travail")
    job = h.server.jobs.get(jid) if _JOB_RE.match(jid or "") else h.server.jobs.latest("portefeuille")
    if job is not None and job.kind != "portefeuille":
        job = None
    fragment = None
    vals = dict(values or {})
    if job is not None:
        if not values and isinstance(getattr(job, "inputs", None), Mapping):
            vals = dict(job.inputs)  # type: ignore[attr-defined]
        if job.finished_ok and job.result is not None:
            fragment = job.result.to_html_fragment()
    nstatus = _safe(h.server.services.notes_status)
    h._page(status, lambda ctx: P.page_portfolio(ctx, values=vals, job=_job_view(job), fragment=fragment, error=error,
                                                 job_id=job.id if job is not None else None, notes_status=nstatus))


def get_portfolio_result(h: Handler, qs: Mapping[str, list[str]]) -> None:
    jid = _qv(qs, "travail")
    job = h.server.jobs.get(jid) if _JOB_RE.match(jid) else None
    if job is None or job.kind != "portefeuille" or not job.finished_ok or job.result is None:
        raise HTTPError(404, "Résultat introuvable", "aucun ordre de bataille terminé pour ce travail")
    fmt = _qv(qs, "format")
    if fmt == "json":
        h._send(200, json.dumps(job.result.to_dict(), ensure_ascii=False, indent=1), "application/json; charset=utf-8")
    elif fmt == "md":
        h._send(200, job.result.to_markdown(), "text/plain; charset=utf-8")
    else:
        raise HTTPError(400, "Format inconnu", "format md ou json")


def get_explain(h: Handler, qs: Mapping[str, list[str]]) -> None:
    s = h.server.services
    values = {"symbole": _qv(qs, "symbole").upper(), "date": _qv(qs, "date"), "variante": _qv(qs, "variante").upper()}
    err, e, status = None, None, 200
    if values["symbole"]:
        try:
            if not _SYMBOL_RE.match(values["symbole"]):
                raise ValueError(f"symbole invalide : {values['symbole'][:12]!r}")
            variant = values["variante"] or None
            if variant is not None and variant not in {v for v, _ in P.VARIANT_CHOICES if v}:
                raise ValueError(f"variante inconnue : {variant[:8]!r}")
            asof = _asof_or_last(h, values["date"])
            if asof is None:
                raise ValueError("panel introuvable")
            if cli.in_s1(asof):
                raise ValueError(cli.s1_refusal(asof, "l'explication"))
            e = s.explain(values["symbole"], asof, variant)
        except (ValueError, KeyError) as exc:
            err, status = str(exc.args[0] if isinstance(exc, KeyError) and exc.args else exc), 400
    opts = [(k, v) for k, v in P.target_options(s.symbol_names()) if _SYMBOL_RE.match(k)]
    h._page(status, lambda ctx: P.page_explain(ctx, values=values, explanation=e, options=opts, error=err))


def get_validation(h: Handler, qs: Mapping[str, list[str]]) -> None:
    s = h.server.services
    h._page(200, lambda ctx: P.page_validation(ctx, s1=s.read_validation(), s1_md=s.read_text("s1"),
                                               attempts_md=s.read_text("tentatives"), s0_md=s.read_text("s0")))


def get_job(h: Handler, qs: Mapping[str, list[str]]) -> None:
    jid = _qv(qs, "id")
    job = h.server.jobs.get(jid) if _JOB_RE.match(jid) else None
    if job is None:
        h._send(404, json.dumps({"erreur": "travail inconnu"}, ensure_ascii=False), "application/json; charset=utf-8")
        return
    h._send(200, json.dumps(job.snapshot(), ensure_ascii=False), "application/json; charset=utf-8")


GET_ROUTES: dict[str, Callable[[Handler, Mapping[str, list[str]]], None]] = {
    "/": get_dashboard,
    "/rapport/voir": get_report,
    "/notes": get_notes,
    "/notes/fiche": get_note,
    "/recherche": get_research,
    "/indices": get_indices,
    "/indices/dossier": get_dossier,
    "/portefeuille": get_portfolio,
    "/portefeuille/resultat": get_portfolio_result,
    "/expliquer": get_explain,
    "/validation": get_validation,
    "/api/travail": get_job,
}


# ---------------------------------------------------------------------------
# Actions (POST)
# ---------------------------------------------------------------------------


def post_note_add(h: Handler, form: Mapping[str, list[str]]) -> None:
    from brvm_alpha.notes.store import NoteConflictError

    fields = ("cibles", "titre", "texte", "avis", "conviction", "horizon", "type", "source", "url", "publie_le",
              "heure", "etiquettes")
    v = {k: _first(form, k).strip() if k != "texte" else _first(form, k) for k in fields}
    try:
        conviction = int(v["conviction"]) if v["conviction"] else None
        horizon = int(v["horizon"]) if v["horizon"] else None
    except ValueError:
        _render_notes(h, 400, _note_filters({}), form_values=v, form_error="conviction et horizon : nombres entiers")
        return
    if v["avis"] and v["avis"] not in ("haussier", "baissier", "neutre"):
        _render_notes(h, 400, _note_filters({}), form_values=v, form_error="avis : haussier, baissier ou neutre")
        return
    published = None
    if v["publie_le"]:
        published = v["publie_le"] + (f" {v['heure']}" if v["heure"] else "")
        if v["heure"] and not re.fullmatch(r"\d{1,2}:\d{2}", v["heure"]):
            _render_notes(h, 400, _note_filters({}), form_values=v, form_error="heure : HH:MM attendu")
            return
    tags = [t.strip() for t in v["etiquettes"].split(",") if t.strip()]
    try:
        note = cli.make_manual_note(targets=[v["cibles"]] if v["cibles"] else None, title=v["titre"], text=v["texte"],
                                    stance=v["avis"] or None, conviction=conviction, horizon=horizon,
                                    source=v["source"] or None, url=v["url"] or None, published=published,
                                    event_type=v["type"] or None, tags=tags)
        store = h.server.services.notes_store()
        nid = store.add(note, analyze=True)
    except NoteConflictError as exc:
        _render_notes(h, 409, _note_filters({}), form_values=v, form_error=str(exc))
        return
    except ValueError as exc:
        _render_notes(h, 400, _note_filters({}), form_values=v, form_error=str(exc))
        return
    h._redirect(f"/notes/fiche?id={nid}&cree=1")


def post_note_archive(h: Handler, form: Mapping[str, list[str]]) -> None:
    nid = _first(form, "id").strip().lower()
    if not _ID_RE.match(nid):
        raise HTTPError(400, "Identifiant invalide", "identifiant de note attendu")
    store = h.server.services.notes_store()
    try:
        full = cli.resolve_note_id(store, nid)
    except KeyError as exc:
        raise HTTPError(404, "Note introuvable", str(exc.args[0] if exc.args else exc)) from exc
    motif = _first(form, "motif").strip()[:200] or None
    store.archive(full, reason=motif)
    h._redirect(f"/notes/fiche?id={full}&archivee=1")


def post_research(h: Handler, form: Mapping[str, list[str]]) -> None:
    s = h.server.services
    mode = _first(form, "mode") or "hors_ligne"
    read_docs = _first(form, "lire_documents") == "oui"
    defaults = {"mode": mode, "max_requetes": _first(form, "max_requetes") or "30", "cibles": _first(form, "cibles"),
                "depuis": _first(form, "depuis"), "lire_documents": "oui" if read_docs else "",
                "max_documents": _first(form, "max_documents") or str(RESEARCH_MAX_DOCS_DEFAULT)}
    if _first(form, "confirmer") != "oui":
        _render_research(h, 400, defaults=defaults, error="cocher la case de confirmation pour lancer la recherche")
        return
    if mode not in ("hors_ligne", "en_ligne"):
        _render_research(h, 400, defaults=defaults, error="mode : hors ligne ou en ligne")
        return
    try:
        n = int(defaults["max_requetes"])
        if not 1 <= n <= RESEARCH_MAX_REQUESTS:
            raise ValueError
    except ValueError:
        _render_research(h, 400, defaults=defaults, error=f"quota : entier de 1 à {RESEARCH_MAX_REQUESTS}")
        return
    max_docs = RESEARCH_MAX_DOCS_DEFAULT
    if read_docs:
        try:
            max_docs = int(defaults["max_documents"])
            if not 1 <= max_docs <= RESEARCH_MAX_DOCS:
                raise ValueError
        except ValueError:
            _render_research(h, 400, defaults=defaults,
                             error=f"nombre maximal de documents : entier de 1 à {RESEARCH_MAX_DOCS}")
            return
    try:
        since = _opt_date(defaults["depuis"], "date")
    except ValueError as exc:
        _render_research(h, 400, defaults=defaults, error=str(exc))
        return
    from brvm_alpha.notes.model import normalize_targets

    raw_targets = [t.strip() for t in re.split(r"[;,|]+", defaults["cibles"]) if t.strip()]
    targets = normalize_targets(raw_targets) if raw_targets else None
    if raw_targets and len(targets or []) != len(raw_targets):
        _render_research(h, 400, defaults=defaults, error="périmètre : cible(s) non reconnue(s) ; voir l'aide des codes")
        return
    offline = mode == "hors_ligne"
    label = f"recherche {'hors ligne' if offline else 'en ligne'} (quota {n})" + (
        f" + lecture d'au plus {max_docs} document(s)" if read_docs else "")
    kw: dict[str, Any] = {"read_docs": True, "max_docs": max_docs} if read_docs else {}
    try:
        h.server.jobs.start("recherche", label, lambda job: s.run_research(offline=offline, max_requests=n,
                                                                           targets=targets, since=since, log=job.log,
                                                                           **kw))
    except JobBusy as exc:
        _render_research(h, 409, defaults=defaults, error=str(exc))
        return
    h._redirect("/recherche")


def post_report(h: Handler, form: Mapping[str, list[str]]) -> None:
    s = h.server.services
    try:
        capital = cli.parse_capital(_first(form, "capital") or cli.DEFAULT_CAPITAL)
    except ValueError as exc:
        raise HTTPError(400, "Saisie refusée", str(exc)) from exc
    asof = s.last_session()
    if asof is None:
        raise HTTPError(400, "Panel introuvable", "lancer « python -m brvm_alpha panel »")
    if cli.in_s1(asof):  # pragma: no cover - le panel s'étend au-delà de S1
        raise HTTPError(400, "Refusé", cli.s1_refusal(asof, "le rapport"))
    try:
        h.server.jobs.start("rapport", f"rapport au {cli.fr_date(asof)} ({cli.fr_num(capital, 0)} FCFA)",
                            lambda job: s.build_report(asof=asof, capital=capital, log=job.log))
    except JobBusy as exc:
        raise HTTPError(409, "Opération en cours", str(exc)) from exc
    h._redirect("/?lance=1")


def post_portfolio(h: Handler, form: Mapping[str, list[str]]) -> None:
    s = h.server.services
    v = {k: _first(form, k) for k in ("capital", "portefeuille", "cash", "variante", "date", "tirages")}
    try:
        capital = cli.parse_capital(v["capital"])
        cash = cli.parse_capital(v["cash"]) if v["cash"].strip() else None
        holdings = cli.parse_holdings(v["portefeuille"])
        variant = v["variante"].strip().upper() or None
        if variant is not None and variant not in {x for x, _ in P.VARIANT_CHOICES if x}:
            raise ValueError(f"variante inconnue : {variant[:8]!r}")
        n_boot = int(v["tirages"] or 5000)
        if n_boot not in (1000, 2000, 5000):
            raise ValueError("tirages : 1000, 2000 ou 5000")
        asof = _asof_or_last(h, v["date"].strip())
        if asof is None:
            raise ValueError("panel introuvable : lancer « python -m brvm_alpha panel »")
        if cli.in_s1(asof):
            raise ValueError(cli.s1_refusal(asof, "l'ordre de bataille"))
    except ValueError as exc:
        _render_portfolio(h, 400, values=v, error=str(exc))
        return
    try:
        job = h.server.jobs.start("portefeuille", f"ordre de bataille ({cli.fr_num(capital, 0)} FCFA)",
                                  lambda job: s.recommend(asof=asof, capital=capital, holdings=holdings, cash=cash,
                                                          variant=variant, n_boot=n_boot, log=job.log))
    except JobBusy as exc:
        _render_portfolio(h, 409, values=v, error=str(exc))
        return
    job.inputs = v  # type: ignore[attr-defined]
    h._redirect(f"/portefeuille?travail={job.id}")


POST_ROUTES: dict[str, Callable[[Handler, Mapping[str, list[str]]], None]] = {
    "/notes/ajouter": post_note_add,
    "/notes/archiver": post_note_archive,
    "/recherche/lancer": post_research,
    "/rapport/regenerer": post_report,
    "/portefeuille/calculer": post_portfolio,
}


__all__ = ["Job", "JobBusy", "JobManager", "Services", "UIServer", "Handler", "make_server", "serve",
           "GET_ROUTES", "POST_ROUTES", "MAX_BODY_BYTES"]
