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
- ``robots.txt`` lu une fois et respecté ; un robots.txt inaccessible (5xx) arrête tout ;
- **arrêt définitif au premier HTTP 403 ou 429** (:class:`DownloadStopped`), sans nouvel
  essai ni contournement, et sans marquer la séance comme manquante ;
- User-Agent explicite ; quota de requêtes facultatif ;
- les jours récents (moins de :data:`RECENT_DAYS` jours) sans bulletin ne sont pas marqués
  ``.missing`` : le BOC du jour est publié le soir, il sera cherché à la mise à jour suivante.

``download_range(..., fetcher=...)`` accepte un client externe (``fetcher(url) -> (statut,
contenu)``) : la commande ``python -m brvm_alpha update`` y branche le client poli de
``brvm_alpha.notes.research`` (délai et blocage partagés d'une session à l'autre).
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import logging
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib import robotparser
from urllib.parse import urlparse

BASE_URL = "https://www.brvm.org/sites/default/files/boc_{date}{suffix}.pdf"
ROBOTS_URL = "https://www.brvm.org/robots.txt"
USER_AGENT = "brvm-alpha/0.1 (outil d'analyse personnel; lecture des BOC publics)"
RECENT_SUFFIXES = ("_2", "", "_3", "_2_0", "_1")
OLD_SUFFIXES = ("", "_2", "_1", "_0", "_3")
SUFFIX_SWITCH = dt.date(2021, 1, 1)
#: Délai par défaut entre deux requêtes (s) : ``Crawl-delay: 10`` de www.brvm.org.
DEFAULT_PAUSE_S = 10.0
#: Plancher du délai vers brvm.org, quel que soit le réglage demandé.
MIN_DELAY_S = 10.0
#: Codes HTTP qui arrêtent définitivement le téléchargement.
STOP_STATUSES = frozenset({403, 429})
#: Jours récents sans bulletin non marqués ``.missing`` (BOC publié le soir).
RECENT_DAYS = 3
MAX_RETRIES = 3

log = logging.getLogger(__name__)

Fetcher = Callable[[str], tuple[int, bytes]]


class DownloadStopped(RuntimeError):
    """Téléchargement arrêté définitivement (HTTP 403/429, robots.txt, serveur indisponible, quota)."""


def pdf_to_text(pdf_path: Path) -> str:
    """Extrait le texte d'un PDF en conservant la mise en page."""
    if shutil.which("pdftotext"):
        out = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
        )
        # pdftotext renvoie parfois un code d'erreur sur un PDF légèrement
        # corrompu tout en extrayant le texte : on garde la sortie si elle existe.
        if out.stdout.strip():
            return out.stdout.decode("utf-8", errors="replace")
    import pdfplumber  # repli pur Python, plus lent

    with pdfplumber.open(pdf_path) as pdf:
        return "\n\f".join((p.extract_text(layout=True) or "") for p in pdf.pages)


def weekdays(start: dt.date, end: dt.date):
    """Jours ouvrés du plus récent au plus ancien."""
    day = end
    while day >= start:
        if day.weekday() < 5:
            yield day
        day -= dt.timedelta(days=1)


class PoliteFetcher:
    """Client HTTP poli pour www.brvm.org : robots.txt, délai ≥ 10 s, arrêt au premier 403/429.

    ``session`` : objet ``requests.Session`` (créé à la première requête si absent) ;
    ``sleep`` et ``clock`` sont injectables (tests sans attente réelle).
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

    def _session(self) -> Any:
        if self.session is None:
            import requests

            self.session = requests.Session()
            self.session.headers["User-Agent"] = self.user_agent
        return self.session

    def _wait(self) -> None:
        if self._last is not None:
            wait = self._last + self.delay - self.clock()
            if wait > 0:
                self.sleep(wait)

    def _raw_get(self, url: str) -> tuple[int, bytes]:
        """Une requête GET (délai respecté, erreurs réseau réessayées avec attente croissante)."""
        if self.stopped:
            raise DownloadStopped(f"téléchargement arrêté ({self.stopped}) : aucune nouvelle requête")
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            if self.max_requests is not None and self.n_requests >= self.max_requests:
                self.stopped = f"quota de {self.max_requests} requêtes atteint"
                raise DownloadStopped(self.stopped)
            self._wait()
            self.n_requests += 1
            try:
                # Redirections non suivies : une réponse 3xx vaut « pas de bulletin à cette adresse ».
                resp = self._session().get(url, timeout=self.timeout, allow_redirects=False,
                                           headers={"User-Agent": self.user_agent})
                status, content = int(resp.status_code), bytes(resp.content or b"")
            except Exception as exc:  # réseau instable : nouvel essai après une attente
                last_exc = exc
                self._last = self.clock()
                log.warning("%s : %s (essai %d)", url, exc, attempt)
                self.sleep(self.delay * attempt)
                continue
            self._last = self.clock()
            if status in STOP_STATUSES:
                self.stopped = f"HTTP {status} sur {url}"
                raise DownloadStopped(
                    f"www.brvm.org a répondu HTTP {status} : téléchargement arrêté définitivement, "
                    "sans nouvel essai ni contournement."
                )
            if status >= 500 and attempt < MAX_RETRIES:
                self.sleep(self.delay * attempt)
                continue
            if status >= 500:
                self.stopped = f"HTTP {status} répété sur {url}"
                raise DownloadStopped(f"www.brvm.org indisponible ({self.stopped}) : nouvel essai plus tard.")
            return status, content
        self.stopped = f"erreur réseau répétée sur {url} ({last_exc})"
        raise DownloadStopped(self.stopped)

    def _read_robots(self) -> None:
        self._robots_read = True
        status, content = self._raw_get(ROBOTS_URL)
        if status == 200:
            rp = robotparser.RobotFileParser(ROBOTS_URL)
            rp.parse(content.decode("utf-8", errors="replace").splitlines())
            self._robots = rp
            try:
                cd = rp.crawl_delay(self.user_agent)
            except Exception:  # pragma: no cover - robots.txt atypique
                cd = None
            if cd:
                self.delay = max(self.delay, float(cd))
        elif status in (401, 403):  # pragma: no cover - 403 déjà traité par _raw_get
            raise DownloadStopped("robots.txt de www.brvm.org refusé : aucune page n'est lue.")
        else:
            self._robots = None  # pas de robots.txt (4xx) : tout est permis

    def __call__(self, url: str) -> tuple[int, bytes]:
        host = (urlparse(url).hostname or "").lower()
        if host not in ("www.brvm.org", "brvm.org"):
            raise DownloadStopped(f"hôte non prévu : {host or '?'} (seul www.brvm.org est interrogé)")
        if not self._robots_read:
            self._read_robots()
        if self._robots is not None and not self._robots.can_fetch(self.user_agent, url):
            self.stopped = f"robots.txt interdit {url}"
            raise DownloadStopped(f"Le robots.txt de www.brvm.org interdit {url} : téléchargement arrêté.")
        return self._raw_get(url)


def fetch_one(fetcher: Any, day: dt.date, out_dir: Path, pause: float | None = None, *,
              mark_missing: bool = True) -> str | None:
    """Télécharge le BOC d'une séance. Renvoie le nom du fichier ou None.

    ``fetcher`` : client poli (:class:`PoliteFetcher` ou appelable ``url -> (statut, contenu)``) ;
    un ``requests.Session`` est accepté et enveloppé dans un :class:`PoliteFetcher` (délai
    ``pause``, au moins 10 s). :class:`DownloadStopped` (403/429, robots.txt…) est propagée :
    la séance n'est **pas** marquée manquante. ``mark_missing=False`` : aucun marqueur
    ``.missing`` si aucun bulletin n'est trouvé (jour récent, BOC pas encore publié).
    """
    stamp = day.strftime("%Y%m%d")
    target = out_dir / f"boc_{stamp}.txt.gz"
    if target.exists() or (out_dir / f"boc_{stamp}.missing").exists():
        return target.name if target.exists() else None
    if not callable(fetcher):  # ancien appel : fetch_one(requests.Session(), ...)
        fetcher = PoliteFetcher(fetcher, DEFAULT_PAUSE_S if pause is None else pause)
    suffixes = RECENT_SUFFIXES if day >= SUFFIX_SWITCH else OLD_SUFFIXES
    for suffix in suffixes:
        url = BASE_URL.format(date=stamp, suffix=suffix)
        status, content = fetcher(url)
        if status != 200 or not content.startswith(b"%PDF"):
            continue
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            text = pdf_to_text(tmp_path)
        except Exception as exc:  # PDF illisible : on le note et on passe à la suite
            log.warning("%s illisible : %s", url, exc)
            (out_dir / f"boc_{stamp}.bad").write_text(f"{url}\n{exc}\n", encoding="utf-8")
            continue
        finally:
            tmp_path.unlink(missing_ok=True)
        if len(text.strip()) < 500:
            log.warning("%s : texte vide ou trop court", url)
            (out_dir / f"boc_{stamp}.bad").write_text(f"{url}\ntexte vide\n", encoding="utf-8")
            continue
        with gzip.open(target, "wt", encoding="utf-8") as fh:
            fh.write(f"# source: {url}\n")
            fh.write(text)
        return target.name
    # Aucun bulletin : jour férié ou fichier introuvable. On le note pour ne pas réessayer
    # (sauf jour récent : le BOC du jour n'est publié que le soir).
    if mark_missing:
        (out_dir / f"boc_{stamp}.missing").touch()
    return None


def pending_days(start: dt.date, end: dt.date, out_dir: Path) -> list[dt.date]:
    """Jours ouvrés de ``[start ; end]`` sans BOC local ni marqueur ``.missing`` (du plus récent au plus ancien)."""
    out = []
    for day in weekdays(start, end):
        stamp = day.strftime("%Y%m%d")
        if not (out_dir / f"boc_{stamp}.txt.gz").exists() and not (out_dir / f"boc_{stamp}.missing").exists():
            out.append(day)
    return out


def download_range(start: dt.date, end: dt.date, out_dir: Path, pause: float = DEFAULT_PAUSE_S, *,
                   fetcher: Fetcher | None = None, today: dt.date | None = None,
                   progress: Callable[[str], None] | None = None) -> int:
    """Télécharge les BOC manquants de ``[start ; end]`` ; renvoie le nombre de bulletins écrits.

    ``pause`` : délai entre requêtes (s), jamais moins de 10 s vers brvm.org. ``fetcher`` : client
    externe (sinon :class:`PoliteFetcher`). Lève :class:`DownloadStopped` au premier 403/429 (les
    bulletins déjà écrits sont conservés).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetch = fetcher if fetcher is not None else PoliteFetcher(pause=pause)
    today = today or dt.date.today()
    recent = today - dt.timedelta(days=RECENT_DAYS)
    count = 0
    for day in pending_days(start, end, out_dir):
        name = fetch_one(fetch, day, out_dir, pause, mark_missing=day < recent)
        if name:
            count += 1
            log.info("%s OK (%d)", name, count)
            if progress:
                progress(f"{name} téléchargé ({count})")
        elif progress:
            progress(f"{day:%d/%m/%Y} : aucun bulletin")
    return count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2017-01-01")
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
        raise SystemExit(2) from exc
    log.info("Terminé : %d bulletins", n)


if __name__ == "__main__":
    main()
