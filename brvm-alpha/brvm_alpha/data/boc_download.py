"""Téléchargement poli des Bulletins Officiels de la Cote (BOC) publiés par la BRVM.

Les BOC sont des PDF publics publiés chaque jour de bourse sur
https://www.brvm.org/fr/bulletins-officiels-de-la-cote. Leur URL suit le motif
``/sites/default/files/boc_AAAAMMJJ[suffixe].pdf`` ; le suffixe varie selon les
années (``""``, ``"_2"``, ``"_2_0"``...).

Le module convertit chaque PDF en texte (mise en page conservée), compresse le
texte en ``.txt.gz`` et supprime le PDF : ~20 Ko par séance au lieu de ~1 Mo.

Politesse (corrigée le 22/11/2026 ; l'ancien délai par défaut de 0,4 s ne respectait pas le
``Crawl-delay: 10`` de www.brvm.org) :

- **au moins 10 s** entre deux requêtes vers brvm.org (:data:`DEFAULT_PAUSE_S`, plancher
  :data:`MIN_DELAY_S`), ou le ``Crawl-delay`` du robots.txt s'il est plus long ;
- ``robots.txt`` lu une fois et respecté ; un robots.txt inaccessible (5xx), redirigé ou illisible
  arrête tout ;
- **arrêt définitif au premier HTTP 403 ou 429** (:class:`DownloadStopped`), sans nouvel
  essai ni contournement, et sans marquer la séance comme manquante ;
- User-Agent explicite ; quota de requêtes facultatif ;
- les jours récents (moins de :data:`RECENT_DAYS` jours) sans bulletin ne sont pas marqués
  ``.missing`` : le BOC du jour est publié le soir, il sera cherché à la mise à jour suivante.

Marqueurs ``boc_AAAAMMJJ.missing`` (jour sans bulletin) : un petit JSON (:func:`lire_marqueur`) —
``statut``, ``code_http``, ``url``, ``date``, ``tentatives``, ``definitif``. Seul un **404 répété**
(:data:`TENTATIVES_404` tentatives, espacées d'au moins un jour) ou une décision explicite
(:func:`marquer_definitif`) rend un marqueur définitif. Une réponse 200 qui n'est pas un PDF, une
redirection, une extraction ratée ou une réponse trop grosse laissent un marqueur **non définitif** : le
jour est cherché de nouveau (au plus tôt le lendemain, puis à intervalle croissant). Les anciens marqueurs
vides restent lus : définitifs, sauf si un ``.bad`` (extraction ratée) les accompagne.

Écritures : ``.txt.gz``, marqueurs et ``.bad`` sont écrits de façon atomique
(:mod:`brvm_alpha.fichiers`) ; un fichier compagnon ``boc_AAAAMMJJ.meta.json`` inscrit l'adresse,
l'extracteur et sa version (le ``.txt.gz`` est inchangé : le panel le lit comme avant). Un seul
téléchargement à la fois par dossier (verrou ``.telechargement.lock``, :class:`VerrouOccupe` sinon).

``download_range(..., fetcher=...)`` accepte un client externe (``fetcher(url) -> (statut,
contenu)``) : la commande ``python -m brvm_alpha update`` y branche :func:`client_brvm` (client poli
de ``brvm_alpha.notes.research`` : délai et blocage partagés d'une session à l'autre).
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib import robotparser
from urllib.parse import urlparse

from brvm_alpha import fichiers, net, paths
from brvm_alpha import pdf as _pdf
from brvm_alpha.erreurs import ACCES_REFUSE, DONNEES_ABSENTES, ConfigurationError, ErreurMoteur

BASE_URL = "https://www.brvm.org/sites/default/files/boc_{date}{suffix}.pdf"
ROBOTS_URL = "https://www.brvm.org/robots.txt"
USER_AGENT = "brvm-alpha/0.1 (outil d'analyse personnel; lecture des BOC publics)"
RECENT_SUFFIXES = ("_2", "", "_3", "_2_0", "_1")
OLD_SUFFIXES = ("", "_2", "_1", "_0", "_3")
SUFFIX_SWITCH = dt.date(2021, 1, 1)
#: Premier jour de l'historique (premier jour de bourse de 2017).
HISTORY_START = dt.date(2017, 1, 2)
#: Délai par défaut entre deux requêtes (s) : ``Crawl-delay: 10`` de www.brvm.org.
DEFAULT_PAUSE_S = 10.0
#: Plancher du délai vers brvm.org, quel que soit le réglage demandé.
MIN_DELAY_S = 10.0
#: Codes HTTP qui arrêtent définitivement le téléchargement.
STOP_STATUSES = frozenset({403, 429})
#: Jours récents sans bulletin non marqués ``.missing`` (BOC publié le soir).
RECENT_DAYS = 3
MAX_RETRIES = 3
#: Tentatives « 404 partout » (espacées d'au moins un jour) qui rendent un marqueur définitif.
TENTATIVES_404 = 3
#: Intervalle maximal entre deux relances d'un jour au marqueur non définitif (jours).
RELANCE_MAX_JOURS = 30
#: Verrou du téléchargement (dans le dossier des BOC).
LOCK_NAME = ".telechargement.lock"
#: Texte extrait trop court pour un BOC (caractères).
MIN_TEXT_CHARS = 500

log = logging.getLogger(__name__)

Fetcher = Callable[[str], tuple[int, bytes]]


class DownloadStopped(RuntimeError, ErreurMoteur):
    """Téléchargement arrêté définitivement (HTTP 403/429, robots.txt, serveur indisponible, quota, refus).

    ``raison`` : ``"bloque"`` (403/429), ``"robots"``, ``"serveur"``, ``"quota"``, ``"politique"`` (liste
    blanche, adresse) ou ``"erreur"`` ; ``code_sortie`` : 1 pour le quota (historique pas encore complet),
    5 sinon.
    """

    def __init__(self, message: str = "", raison: str = "erreur") -> None:
        super().__init__(message)
        self.raison = raison
        self.code_sortie = DONNEES_ABSENTES if raison == "quota" else ACCES_REFUSE


class ReponseInexploitable(RuntimeError):
    """Réponse sans bulletin exploitable à cette adresse (redirections en boucle, réponse trop grosse).

    Le téléchargement continue ; le jour reçoit un marqueur **non définitif** (``statut``).
    """

    def __init__(self, statut: str, message: str = "") -> None:
        super().__init__(message or statut)
        self.statut = statut


# ---------------------------------------------------------------------------
# Conversion PDF -> texte
# ---------------------------------------------------------------------------


def pdf_to_text(pdf_path: Path) -> str:
    """Extrait le texte d'un PDF en conservant la mise en page (:func:`brvm_alpha.pdf.extraire_texte`).

    pdftotext, sinon (hors mode embarqué) pdfplumber ; :class:`ConfigurationError` si aucun extracteur
    n'est utilisable (mode embarqué sans pdftotext compris).
    """
    return _pdf.extraire_texte(pdf_path, layout=True)[0]


def convert_pdf(content: bytes) -> tuple[str, str, str | None]:
    """``(texte, extracteur, version)`` d'un PDF reçu en mémoire (fichier temporaire hors du code)."""
    with tempfile.TemporaryDirectory(prefix="brvm-boc-") as tmp:
        path = Path(tmp) / "boc.pdf"
        path.write_bytes(content)
        return _pdf.extraire_texte(path, layout=True)


def weekdays(start: dt.date, end: dt.date):
    """Jours ouvrés du plus récent au plus ancien."""
    day = end
    while day >= start:
        if day.weekday() < 5:
            yield day
        day -= dt.timedelta(days=1)


# ---------------------------------------------------------------------------
# Marqueurs « sans bulletin »
# ---------------------------------------------------------------------------

#: Statuts d'un marqueur : seul « introuvable » (404 partout) peut devenir définitif tout seul.
STATUTS = ("introuvable", "pas_un_pdf", "redirection", "extraction_ratee", "trop_gros", "reseau", "autre",
           "decision", "ancien")
_PRIORITE = ("extraction_ratee", "pas_un_pdf", "trop_gros", "redirection", "reseau", "autre")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@dataclass
class Marqueur:
    """Contenu d'un marqueur ``boc_AAAAMMJJ.missing``."""

    statut: str
    code_http: int | None = None
    url: str | None = None
    date: str | None = None
    tentatives: int = 1
    definitif: bool = False
    premiere_date: str | None = None
    raison: str | None = None
    #: Ancien marqueur vide (avant le 22/11/2026), lu pour compatibilité.
    ancien: bool = False

    def jour(self) -> dt.date | None:
        """Jour (UTC) de la dernière tentative."""
        try:
            return dt.datetime.fromisoformat(str(self.date)).date() if self.date else None
        except ValueError:
            return None

    def a_relancer(self, today: dt.date) -> bool:
        """Vrai si le jour doit être cherché de nouveau aujourd'hui (marqueur non définitif, délai écoulé)."""
        if self.definitif:
            return False
        last = self.jour()
        if last is None:
            return True
        wait = 1 if self.statut == "introuvable" else min(2 ** max(self.tentatives - 1, 0), RELANCE_MAX_JOURS)
        return (today - last).days >= wait

    def to_json(self) -> str:
        d = asdict(self)
        d.pop("ancien", None)
        return json.dumps({"format": 1, **d}, ensure_ascii=False, indent=1) + "\n"


def marker_path(out_dir: str | Path, day: dt.date) -> Path:
    return Path(out_dir) / f"boc_{day:%Y%m%d}.missing"


def lire_marqueur(path: str | Path) -> Marqueur | None:
    """Marqueur d'un jour, ou ``None`` s'il n'existe pas.

    Ancien marqueur **vide** : définitif (comme avant), sauf si un ``.bad`` du même jour signale une
    extraction ratée (alors non définitif). Contenu illisible : non définitif (le jour sera cherché de nouveau).
    """
    p = Path(path)
    try:
        raw = p.read_bytes()
        mtime = p.stat().st_mtime
    except FileNotFoundError:
        return None
    except OSError:
        return Marqueur(statut="autre", raison="marqueur illisible", definitif=False)
    stamp = dt.datetime.fromtimestamp(mtime, dt.timezone.utc).isoformat(timespec="seconds")
    if not raw.strip():
        bad = p.with_suffix(".bad").exists()
        return Marqueur(statut="extraction_ratee" if bad else "ancien", date=stamp, premiere_date=stamp,
                        tentatives=1, definitif=not bad, ancien=True,
                        raison="ancien marqueur vide" + (" avec extraction ratée (.bad)" if bad else ""))
    try:
        d = json.loads(raw.decode("utf-8"))
        if not isinstance(d, dict):
            raise ValueError("objet attendu")
        return Marqueur(statut=str(d.get("statut") or "autre"),
                        code_http=int(d["code_http"]) if d.get("code_http") is not None else None,
                        url=d.get("url"), date=d.get("date") or stamp, tentatives=max(1, int(d.get("tentatives") or 1)),
                        definitif=bool(d.get("definitif")), premiere_date=d.get("premiere_date"),
                        raison=d.get("raison"))
    except (ValueError, TypeError, UnicodeDecodeError):
        return Marqueur(statut="autre", date=stamp, raison="marqueur illisible", definitif=False)


def _bilan_jour(outcomes: list[tuple[str, int | None, str]]) -> tuple[str, int | None, str | None]:
    """Statut d'un jour d'après les réponses de ses adresses : « introuvable » si toutes ont répondu 404."""
    if outcomes and all(k == "introuvable" for k, _s, _u in outcomes):
        return "introuvable", outcomes[0][1], outcomes[0][2]
    for kind in _PRIORITE:
        for k, s, u in outcomes:
            if k == kind:
                return k, s, u
    return "autre", None, None


def ecrire_marqueur(out_dir: str | Path, day: dt.date, outcomes: list[tuple[str, int | None, str]],
                    now: dt.datetime | None = None) -> Marqueur:
    """Écrit (ou met à jour) le marqueur d'un jour sans bulletin ; rend le marqueur écrit.

    ``outcomes`` : ``(statut, code HTTP, adresse)`` par adresse essayée. Une tentative de plus ; le
    marqueur devient définitif à la :data:`TENTATIVES_404`-ième tentative « 404 partout ».
    """
    now = now or _utcnow()
    p = marker_path(out_dir, day)
    old = lire_marqueur(p)
    statut, code, url = _bilan_jour(outcomes)
    n = 1
    first = now.isoformat(timespec="seconds")
    if old is not None and not old.definitif:
        n = (old.tentatives + 1) if old.statut == statut else 1
        first = old.premiere_date or old.date or first
    m = Marqueur(statut=statut, code_http=code, url=url, date=now.isoformat(timespec="seconds"), tentatives=n,
                 definitif=statut == "introuvable" and n >= TENTATIVES_404, premiere_date=first,
                 raison=("404 sur toutes les adresses" if statut == "introuvable" else None))
    fichiers.ecrire_atomique(p, m.to_json())
    return m


def marquer_definitif(out_dir: str | Path, day: dt.date, raison: str = "décision explicite",
                      now: dt.datetime | None = None) -> Marqueur:
    """Décision explicite : le jour n'a pas de bulletin (marqueur définitif, plus aucune recherche)."""
    now = now or _utcnow()
    p = marker_path(out_dir, day)
    old = lire_marqueur(p)
    m = Marqueur(statut="decision", code_http=old.code_http if old else None, url=old.url if old else None,
                 date=now.isoformat(timespec="seconds"), tentatives=old.tentatives if old else 0, definitif=True,
                 premiere_date=(old.premiere_date or old.date) if old else None, raison=raison)
    fichiers.ecrire_atomique(p, m.to_json())
    return m


def reouvrir(out_dir: str | Path, day: dt.date) -> bool:
    """Décision explicite inverse : retire le marqueur d'un jour (il sera cherché de nouveau) ; ``True`` s'il existait."""
    p = paths.verifier_ecriture(marker_path(out_dir, day))
    try:
        p.unlink()
    except FileNotFoundError:
        return False
    return True


def _write_bad(out_dir: Path, stamp: str, url: str, reason: str) -> None:
    fichiers.ecrire_atomique(out_dir / f"boc_{stamp}.bad", f"{url}\n{reason}\n")


# ---------------------------------------------------------------------------
# Client poli autonome
# ---------------------------------------------------------------------------


class PoliteFetcher:
    """Client HTTP poli pour www.brvm.org : robots.txt, délai ≥ 10 s, arrêt au premier 403/429.

    ``session`` : objet à méthode ``get(url, timeout=…, allow_redirects=False, headers=…)`` (session
    ``requests`` ou doublure) ; absent, le client commun du moteur (:class:`brvm_alpha.net.ClientHttp` :
    liste blanche, plafonds, délai total). ``sleep`` et ``clock`` sont injectables (tests sans attente).
    """

    def __init__(self, session: Any = None, pause: float = DEFAULT_PAUSE_S, *,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 max_requests: int | None = None, timeout: float = 60.0, user_agent: str = USER_AGENT) -> None:
        self.session = session
        self.delay = max(float(pause), MIN_DELAY_S)
        self.sleep = sleep
        self.clock = clock
        self.max_requests = max_requests
        self.timeout = timeout
        self.user_agent = user_agent
        self.n_requests = 0
        self.stopped: str | None = None
        self._last: float | None = None
        self._robots: robotparser.RobotFileParser | None = None
        self._robots_read = False
        self._client: net.ClientHttp | None = None

    def _get(self, url: str, nature: str) -> tuple[int, bytes]:
        if self.session is None:
            if self._client is None:
                self._client = net.ClientHttp(net.politique_par_defaut(), user_agent=self.user_agent)
            resp = self._client.get(url, nature=nature, suivre=0, delai_lecture=self.timeout)
        else:
            # Redirections non suivies : une réponse 3xx vaut « pas de bulletin à cette adresse ».
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=False,
                                    headers={"User-Agent": self.user_agent})
        content = bytes(resp.content or b"")
        cap = net.PLAFONDS.get(nature, net.PLAFONDS["page"])
        if len(content) > cap:
            raise net.ReponseTropGrosse(f"{url} : réponse de {len(content)} octets, plafond {cap}.")
        return int(resp.status_code), content

    def _wait(self) -> None:
        if self._last is not None:
            wait = self._last + self.delay - self.clock()
            if wait > 0:
                self.sleep(wait)

    def _stop(self, reason: str, raison: str, message: str | None = None) -> DownloadStopped:
        self.stopped = reason
        return DownloadStopped(message or reason, raison=raison)

    def _raw_get(self, url: str, nature: str = "pdf") -> tuple[int, bytes]:
        """Une requête GET (délai respecté, erreurs réseau réessayées avec attente croissante)."""
        if self.stopped:
            raise DownloadStopped(f"téléchargement arrêté ({self.stopped}) : aucune nouvelle requête",
                                  raison="erreur")
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            if self.max_requests is not None and self.n_requests >= self.max_requests:
                raise self._stop(f"quota de {self.max_requests} requêtes atteint", "quota")
            self._wait()
            self.n_requests += 1
            try:
                status, content = self._get(url, nature)
            except MemoryError:
                raise
            except (ConfigurationError, fichiers.VerrouOccupe):
                raise
            except net.ReponseTropGrosse as exc:
                self._last = self.clock()
                raise ReponseInexploitable("trop_gros", str(exc)) from exc
            except net.RefusPolitique as exc:  # liste blanche, adresse locale : arrêt, sans nouvel essai
                self._last = self.clock()
                raise self._stop(f"requête refusée : {exc}", "politique") from exc
            except Exception as exc:  # réseau instable (délai dépassé compris) : nouvel essai après une attente
                last_exc = exc
                self._last = self.clock()
                log.warning("%s : %s (essai %d)", url, exc, attempt)
                self.sleep(self.delay * attempt)
                continue
            self._last = self.clock()
            if status in STOP_STATUSES:
                raise self._stop(f"HTTP {status} sur {url}", "bloque",
                                 f"www.brvm.org a répondu HTTP {status} : téléchargement arrêté définitivement, "
                                 "sans nouvel essai ni contournement.")
            if status >= 500 and attempt < MAX_RETRIES:
                self.sleep(self.delay * attempt)
                continue
            if status >= 500:
                reason = f"HTTP {status} répété sur {url}"
                raise self._stop(reason, "serveur", f"www.brvm.org indisponible ({reason}) : nouvel essai plus tard.")
            return status, content
        raise self._stop(f"erreur réseau répétée sur {url} ({last_exc})", "serveur")

    def _read_robots(self) -> None:
        self._robots_read = True
        try:
            status, content = self._raw_get(ROBOTS_URL, nature="robots")
        except ReponseInexploitable as exc:
            raise self._stop("robots.txt trop gros", "robots",
                             f"robots.txt de www.brvm.org illisible ({exc}) : par prudence, aucune page n'est lue.") from exc
        if status == 200:
            text = content.decode("utf-8", errors="replace")
            head = text[:512].lstrip().lower()
            if "\x00" in text[:4096] or head.startswith(("<!doctype", "<html", "<?xml", "<head", "<body")):
                raise self._stop("robots.txt illisible", "robots",
                                 "robots.txt de www.brvm.org illisible (page HTML ou binaire) : par prudence, "
                                 "aucune page n'est lue.")
            rp = robotparser.RobotFileParser(ROBOTS_URL)
            rp.parse(text.splitlines())
            self._robots = rp
            try:
                cd = rp.crawl_delay(self.user_agent)
            except Exception:  # pragma: no cover - robots.txt atypique
                cd = None
            if cd:
                self.delay = max(self.delay, float(cd))
        elif status in (401, 403):  # pragma: no cover - 403 déjà traité par _raw_get
            raise self._stop("robots.txt refusé", "robots", "robots.txt de www.brvm.org refusé : aucune page n'est lue.")
        elif 300 <= status < 400:
            raise self._stop("robots.txt redirigé", "robots",
                             f"robots.txt de www.brvm.org redirigé (HTTP {status}) : par prudence, aucune page "
                             "n'est lue.")
        else:
            self._robots = None  # pas de robots.txt (4xx) : tout est permis

    def __call__(self, url: str) -> tuple[int, bytes]:
        host = (urlparse(url).hostname or "").lower()
        if host not in ("www.brvm.org", "brvm.org"):
            raise DownloadStopped(f"hôte non prévu : {host or '?'} (seul www.brvm.org est interrogé)",
                                  raison="politique")
        if not self._robots_read:
            self._read_robots()
        if self._robots is not None and not self._robots.can_fetch(self.user_agent, url):
            raise self._stop(f"robots.txt interdit {url}", "robots",
                             f"Le robots.txt de www.brvm.org interdit {url} : téléchargement arrêté.")
        return self._raw_get(url)


def client_brvm(max_requests: int = 200, delay_s: float = DEFAULT_PAUSE_S, cache_dir: Any = None) -> Fetcher:
    """Client poli de ``notes.research`` pour le téléchargement (délai et blocage partagés, sans cache disque).

    L'appelable renvoie ``(statut, contenu)`` ; il lève :class:`DownloadStopped` au premier 403/429, sur
    interdiction du robots.txt, quota atteint, serveur indisponible ou refus de la liste blanche, et
    :class:`ReponseInexploitable` pour des redirections en boucle ou une réponse trop grosse (le jour reçoit
    alors un marqueur non définitif). Toute autre erreur de collecte arrête aussi le téléchargement : elle
    n'est jamais prise pour « pas de bulletin ». Attribut ``session`` : la ``PoliteSession`` utilisée.
    """
    from brvm_alpha.notes import research as rs

    class _NoCacheSession(rs.PoliteSession):
        """Les PDF (~1 Mo) ne sont pas conservés dans le cache HTTP."""

        def cache_get(self, url: str):  # noqa: D401
            return None

        def cache_put(self, *args: Any, **kwargs: Any) -> None:
            return None

    cdir = Path(cache_dir) if cache_dir is not None else rs.DEFAULT_NOTES_DIR / "cache"
    sess = _NoCacheSession(delay_s=max(float(delay_s), MIN_DELAY_S), max_requests=max_requests,
                           cache_dir=cdir, log_path=cdir.parent / "fetch_log.jsonl", max_retries=2,
                           user_agent=USER_AGENT)

    def fetch(url: str) -> tuple[int, bytes]:
        try:
            res = sess.get(url, nature="pdf")
        except rs.TooManyRedirects as exc:  # pas de bulletin exploitable à cette adresse
            raise ReponseInexploitable("redirection", str(exc)) from exc
        except rs.PolicyRefused as exc:
            if isinstance(exc.__cause__, net.ReponseTropGrosse):
                raise ReponseInexploitable("trop_gros", str(exc)) from exc
            raise DownloadStopped(str(exc), raison="politique") from exc
        except rs.AccessBlocked as exc:
            raise DownloadStopped(str(exc), raison="bloque") from exc
        except rs.RobotsDisallowed as exc:
            raise DownloadStopped(str(exc), raison="robots") from exc
        except rs.QuotaExceeded as exc:
            raise DownloadStopped(str(exc), raison="quota") from exc
        except rs.ServerUnavailable as exc:
            raise DownloadStopped(str(exc), raison="serveur") from exc
        except rs.SourceDisabled as exc:
            raise DownloadStopped(str(exc), raison="politique") from exc
        except rs.ResearchError as exc:  # toute autre erreur : arrêt, jamais « pas de bulletin »
            raise DownloadStopped(str(exc), raison="erreur") from exc
        return int(res.status), bytes(res.content or b"")

    fetch.session = sess  # type: ignore[attr-defined]
    return fetch


# ---------------------------------------------------------------------------
# Un jour, une fenêtre
# ---------------------------------------------------------------------------


def _write_bulletin(out_dir: Path, stamp: str, url: str, text: str, method: str, version: str | None,
                    size: int) -> Path:
    target = out_dir / f"boc_{stamp}.txt.gz"
    buf = io.BytesIO()
    with gzip.GzipFile(filename=target.name[:-3], mode="wb", fileobj=buf) as gz:
        gz.write(f"# source: {url}\n".encode("utf-8"))
        gz.write(text.encode("utf-8"))
    fichiers.ecrire_atomique(target, buf.getvalue())
    meta = {"format": 1, "source": url, "extracteur": method, "version_extracteur": version,
            "taille_pdf": int(size), "converti_le": _utcnow().isoformat(timespec="seconds")}
    fichiers.ecrire_atomique(out_dir / f"boc_{stamp}.meta.json", json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    return target


def lire_meta(path: str | Path) -> dict[str, Any] | None:
    """Fichier compagnon d'un BOC (``boc_AAAAMMJJ.meta.json`` ; on peut donner le ``.txt.gz``) : source, extracteur."""
    p = Path(path)
    if p.name.endswith(".txt.gz"):
        p = p.with_name(p.name[: -len(".txt.gz")] + ".meta.json")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def fetch_one(fetcher: Any, day: dt.date, out_dir: Path, pause: float | None = None, *,
              mark_missing: bool = True, today: dt.date | None = None,
              now: dt.datetime | None = None) -> str | None:
    """Télécharge le BOC d'une séance. Renvoie le nom du fichier ou None.

    ``fetcher`` : client poli (:class:`PoliteFetcher` ou appelable ``url -> (statut, contenu)``) ;
    un ``requests.Session`` est accepté et enveloppé dans un :class:`PoliteFetcher` (délai
    ``pause``, au moins 10 s). :class:`DownloadStopped` (403/429, robots.txt…) est propagée :
    la séance n'est **pas** marquée manquante. ``mark_missing=False`` : aucun marqueur
    ``.missing`` si aucun bulletin n'est trouvé (jour récent, BOC pas encore publié).
    Un marqueur définitif fait passer le jour ; un marqueur non définitif aussi, tant que son délai de
    relance n'est pas écoulé (:meth:`Marqueur.a_relancer`).
    """
    out_dir = Path(out_dir)
    today = today or dt.date.today()
    stamp = day.strftime("%Y%m%d")
    target = out_dir / f"boc_{stamp}.txt.gz"
    if target.exists():
        return target.name
    old = lire_marqueur(marker_path(out_dir, day))
    if old is not None and not old.a_relancer(today):
        return None
    if not callable(fetcher):  # ancien appel : fetch_one(requests.Session(), ...)
        fetcher = PoliteFetcher(fetcher, DEFAULT_PAUSE_S if pause is None else pause)
    suffixes = RECENT_SUFFIXES if day >= SUFFIX_SWITCH else OLD_SUFFIXES
    outcomes: list[tuple[str, int | None, str]] = []
    for suffix in suffixes:
        url = BASE_URL.format(date=stamp, suffix=suffix)
        try:
            status, content = fetcher(url)
        except ReponseInexploitable as exc:
            outcomes.append((exc.statut, None, url))
            continue
        if status != 200 or not content.startswith(b"%PDF"):
            kind = ("introuvable" if status in (404, 410) else "pas_un_pdf" if status == 200 else
                    "redirection" if 300 <= status < 400 else "reseau" if status == 0 else "autre")
            outcomes.append((kind, status, url))
            continue
        try:
            text, method, version = convert_pdf(content)
        except (ConfigurationError, MemoryError):
            raise  # extracteur absent, mémoire : la commande s'arrête, aucun jour n'est marqué
        except Exception as exc:  # PDF illisible : on le note et on passe à la suite
            log.warning("%s illisible : %s", url, exc)
            _write_bad(out_dir, stamp, url, str(exc))
            outcomes.append(("extraction_ratee", 200, url))
            continue
        if len(text.strip()) < MIN_TEXT_CHARS:
            log.warning("%s : texte vide ou trop court", url)
            _write_bad(out_dir, stamp, url, "texte vide")
            outcomes.append(("extraction_ratee", 200, url))
            continue
        _write_bulletin(out_dir, stamp, url, text, method, version, len(content))
        if old is not None:  # le jour a enfin son bulletin : son marqueur n'a plus d'objet
            try:
                paths.verifier_ecriture(marker_path(out_dir, day)).unlink()
            except OSError:
                pass
        return target.name
    # Aucun bulletin : jour férié ou fichier introuvable. On le note (sauf jour récent : le BOC du jour
    # n'est publié que le soir) ; seul un 404 répété rend le marqueur définitif.
    if mark_missing:
        ecrire_marqueur(out_dir, day, outcomes, now)
    return None


@dataclass
class EtatDossier:
    """Relevé du dossier des BOC sur une fenêtre (lecture du disque seule)."""

    en_cache: int = 0
    marques_definitifs: int = 0
    marques_non_definitifs: int = 0
    #: Jours à chercher maintenant : sans fichier, ou marqueur non définitif dont le délai est écoulé.
    a_chercher: list[dt.date] = field(default_factory=list)
    #: Jours sans aucun fichier (ni bulletin, ni marqueur), jours récents exclus.
    sans_fichier: list[dt.date] = field(default_factory=list)
    #: Jours au marqueur non définitif.
    non_definitifs: list[dt.date] = field(default_factory=list)


def etat_dossier(out_dir: str | Path, start: dt.date = HISTORY_START, end: dt.date | None = None,
                 today: dt.date | None = None) -> EtatDossier:
    """Relevé du dossier des BOC sur ``[start ; end]`` (un seul parcours du dossier ; aucune requête)."""
    today = today or dt.date.today()
    end = today if end is None or end > today else end
    recent = today - dt.timedelta(days=RECENT_DAYS)
    try:
        names = set(os.listdir(out_dir))
    except OSError:
        names = set()
    out = EtatDossier()
    for day in weekdays(start, end):
        stamp = day.strftime("%Y%m%d")
        if f"boc_{stamp}.txt.gz" in names:
            out.en_cache += 1
            continue
        if f"boc_{stamp}.missing" in names:
            m = lire_marqueur(Path(out_dir) / f"boc_{stamp}.missing")
            if m is not None and m.definitif:
                out.marques_definitifs += 1
                continue
            out.marques_non_definitifs += 1
            out.non_definitifs.append(day)
            if m is None or m.a_relancer(today):
                out.a_chercher.append(day)
            continue
        out.a_chercher.append(day)
        if day < recent:
            out.sans_fichier.append(day)
    return out


def pending_days(start: dt.date, end: dt.date, out_dir: Path, today: dt.date | None = None) -> list[dt.date]:
    """Jours ouvrés de ``[start ; end]`` à chercher (du plus récent au plus ancien) : sans BOC local, et
    sans marqueur ``.missing`` ou avec un marqueur non définitif dont le délai de relance est écoulé."""
    return etat_dossier(out_dir, start, end, today).a_chercher


def update_window(boc_dir: str | Path, start: dt.date | None = None, end: dt.date | None = None,
                  today: dt.date | None = None) -> tuple[dt.date, dt.date, list[dt.date]]:
    """``(premier jour, dernier jour, jours ouvrés à chercher)`` de ``update`` ; lecture du disque seule.

    Défaut : **tout le calendrier depuis le 02/01/2017** (:data:`HISTORY_START`) jusqu'à aujourd'hui, si
    bien qu'une collecte interrompue est reprise depuis le plus ancien jour manquant, sans ``--from``.
    ``start`` (``--from``) borne la fenêtre. Ordre : du plus récent au plus ancien (le bulletin du jour
    n'attend jamais le rattrapage) ; le quota de requêtes s'applique à chaque lancement.
    """
    today = today or dt.date.today()
    start = HISTORY_START if start is None else start
    end = today if end is None or end > today else end
    days = pending_days(start, end, Path(boc_dir), today) if start <= end else []
    return start, end, days


def download_range(start: dt.date, end: dt.date, out_dir: Path, pause: float = DEFAULT_PAUSE_S, *,
                   fetcher: Fetcher | None = None, today: dt.date | None = None,
                   progress: Callable[[str], None] | None = None, lock_timeout_s: float | None = None) -> int:
    """Télécharge les BOC manquants de ``[start ; end]`` ; renvoie le nombre de bulletins écrits.

    ``pause`` : délai entre requêtes (s), jamais moins de 10 s vers brvm.org. ``fetcher`` : client
    externe (sinon :class:`PoliteFetcher`). Lève :class:`DownloadStopped` au premier 403/429 (les
    bulletins déjà écrits sont conservés). Un seul téléchargement à la fois par dossier : verrou
    ``.telechargement.lock`` (``fcntl.flock``) ; :class:`~brvm_alpha.erreurs.VerrouOccupe` au-delà de
    ``lock_timeout_s`` secondes (défaut : :func:`brvm_alpha.fichiers.delai_verrou`).
    """
    out_dir = Path(out_dir)
    paths.verifier_ecriture(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = today or dt.date.today()
    recent = today - dt.timedelta(days=RECENT_DAYS)
    count = 0
    with fichiers.verrou(out_dir / LOCK_NAME, attente=lock_timeout_s, quoi="téléchargement des BOC"):
        fichiers.purger_temporaires(out_dir)
        fetch = fetcher if fetcher is not None else PoliteFetcher(pause=pause)
        for day in pending_days(start, end, out_dir, today):
            name = fetch_one(fetch, day, out_dir, pause, mark_missing=day < recent, today=today)
            if name:
                count += 1
                log.info("%s OK (%d)", name, count)
                if progress:
                    progress(f"{name} téléchargé ({count})")
            elif progress:
                progress(f"{day:%d/%m/%Y} : aucun bulletin")
    return count


# ---------------------------------------------------------------------------
# Mise à jour complète (téléchargement puis panel), pour la ligne de commande
# ---------------------------------------------------------------------------


@dataclass
class BilanMiseAJour:
    """Bilan de :func:`mettre_a_jour` (sérialisable par :meth:`to_dict`)."""

    debut: dt.date
    fin: dt.date
    jours_cherches: int
    bulletins: int = 0
    requetes: int = 0
    quota: int = 0
    arret: str | None = None
    raison_arret: str | None = None
    panel_reconstruit: bool = False
    panel: dict[str, Any] | None = None
    jours_restants: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"debut": self.debut.isoformat(), "fin": self.fin.isoformat(), "jours_cherches": self.jours_cherches,
                "bulletins_telecharges": self.bulletins, "requetes": self.requetes, "quota": self.quota,
                "quota_restant": max(0, self.quota - self.requetes), "arret": self.arret is not None,
                "raison_arret": self.raison_arret, "motif_arret": self.arret,
                "panel_reconstruit": self.panel_reconstruit, "panel": self.panel,
                "jours_restants": self.jours_restants}


def mettre_a_jour(boc_dir: str | Path, panel_dir: str | Path, *, start: dt.date | None = None,
                  end: dt.date | None = None, today: dt.date | None = None, max_requetes: int = 200,
                  delai: float = DEFAULT_PAUSE_S, workers: int | None = None, sans_panel: bool = False,
                  cache_dir: str | Path | None = None, fetcher: Fetcher | None = None,
                  progress: Callable[[str], None] | None = None,
                  lock_timeout_s: float | None = None) -> BilanMiseAJour:
    """Téléchargement des BOC manquants (fenêtre :func:`update_window`), puis panel s'il y a du nouveau.

    ``workers`` : processus de travail du panel (défaut : :func:`brvm_alpha.ressources.workers_par_defaut`).
    Un site bloqué (403/429 enregistré) : aucune requête, :class:`DownloadStopped` (raison « bloque »).
    Un arrêt en cours de route (quota, 403…) est rendu dans le bilan (``arret``, ``raison_arret``), le panel
    étant reconstruit avec les bulletins déjà reçus. Verrous : téléchargement et panel
    (:class:`~brvm_alpha.erreurs.VerrouOccupe` si une autre opération les tient).
    """
    from brvm_alpha.notes import research as rs

    boc_dir, panel_dir = Path(boc_dir), Path(panel_dir)
    today = today or dt.date.today()
    first, last, days = update_window(boc_dir, start, end, today)
    bilan = BilanMiseAJour(debut=first, fin=last, jours_cherches=len(days), quota=int(max_requetes))
    cdir = Path(cache_dir) if cache_dir is not None else rs.DEFAULT_NOTES_DIR / "cache"
    blocked = rs.blocked_hosts(cdir).get("www.brvm.org")
    if blocked and fetcher is None:
        raise DownloadStopped(f"www.brvm.org a refusé l'accès le {blocked.get('ts')} (HTTP {blocked.get('status')}) : "
                              "aucune requête n'est envoyée ; le blocage ne se lève qu'explicitement, avec l'accord "
                              "du site.", raison="bloque")
    if days:
        fetch = fetcher if fetcher is not None else client_brvm(max_requests=max_requetes, delay_s=delai,
                                                                 cache_dir=cdir)
        try:
            bilan.bulletins = download_range(first, last, boc_dir, pause=delai, fetcher=fetch, today=today,
                                             progress=progress, lock_timeout_s=lock_timeout_s)
        except DownloadStopped as exc:
            bilan.arret, bilan.raison_arret = str(exc), exc.raison
        sess = getattr(fetch, "session", None)
        bilan.requetes = int(getattr(sess, "n_requests", 0) or 0)
    bilan.jours_restants = len(update_window(boc_dir, start, end, today)[2])
    if bilan.bulletins > 0 and not sans_panel:
        from brvm_alpha.data import store

        summary = store.build_panel(boc_dir, panel_dir, workers=workers, lock_timeout_s=lock_timeout_s)
        bilan.panel_reconstruit = True
        bilan.panel = summary.to_dict() if hasattr(summary, "to_dict") else None
    return bilan


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=HISTORY_START.isoformat())
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument("--out", default="data/boc_text")
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_S,
                        help="secondes entre requêtes (au moins 10 s vers brvm.org)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        n = download_range(
            dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end), Path(args.out), args.pause
        )
    except DownloadStopped as exc:
        log.error("Arrêt : %s", exc)
        raise SystemExit(exc.code_sortie) from exc
    log.info("Terminé : %d bulletins", n)


__all__ = ["BASE_URL", "ROBOTS_URL", "USER_AGENT", "HISTORY_START", "DEFAULT_PAUSE_S", "MIN_DELAY_S", "RECENT_DAYS",
           "TENTATIVES_404", "DownloadStopped", "ReponseInexploitable", "Marqueur", "pdf_to_text", "convert_pdf",
           "weekdays", "marker_path", "lire_marqueur", "ecrire_marqueur", "marquer_definitif", "reouvrir",
           "PoliteFetcher", "client_brvm", "lire_meta", "fetch_one", "EtatDossier", "etat_dossier", "pending_days",
           "update_window", "download_range", "BilanMiseAJour", "mettre_a_jour", "main"]


if __name__ == "__main__":
    main()
