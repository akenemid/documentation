"""Cours du jour depuis la page publique https://www.brvm.org/fr/cours-actions/0.

La page liste, pour chaque action : symbole, nom, volume, cours veille,
cours d'ouverture, cours de clôture et variation (%). Elle donne aussi les
indices BRVM-C, BRVM-30, BRVM-PRES et l'activité du marché. C'est une photo
instantanée (pas d'historique) : l'historique vient des BOC (``store.py``).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup, FeatureNotFound

LIVE_URL = "https://www.brvm.org/fr/cours-actions/0"
USER_AGENT = "brvm-alpha/0.1 (outil d'analyse personnel)"


def parse_number(text: str) -> float | None:
    """Convertit « 12 737 890 », « 3,66 % » ou « -0,21% » en nombre."""
    if text is None:
        return None
    cleaned = (
        text.replace("\xa0", " ")
        .replace(" ", " ")
        .replace("FCFA", "")
        .replace("%", "")
        .strip()
    )
    cleaned = re.sub(r"(?<=\d) (?=\d)", "", cleaned).replace(" ", "").replace(",", ".")
    if cleaned in {"", "-", "NC", "SP"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


@dataclass
class LiveSnapshot:
    fetched_at: dt.datetime
    quotes: pd.DataFrame
    indices: dict[str, dict[str, float | None]] = field(default_factory=dict)
    activity: dict[str, float | None] = field(default_factory=dict)


def parse_live_html(html: str, fetched_at: dt.datetime | None = None) -> LiveSnapshot:
    """Extrait le tableau des cours et les indicateurs de la page brvm.org."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:  # paquet lxml absent : analyseur de la bibliothèque standard
        soup = BeautifulSoup(html, "html.parser")
    rows = []
    indices: dict[str, dict[str, float | None]] = {}
    activity: dict[str, float | None] = {}
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if headers and headers[0].startswith("Symbole"):
            body = table.find("tbody") or table  # page sans <tbody> : lignes du tableau, en-tête sauté
            for tr in body.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if len(cells) < 7:
                    continue
                rows.append(
                    {
                        "symbol": cells[0].strip(),
                        "name": cells[1].strip(),
                        "volume": parse_number(cells[2]),
                        "prev_close": parse_number(cells[3]),
                        "open": parse_number(cells[4]),
                        "close": parse_number(cells[5]),
                        "change_pct": parse_number(cells[6]),
                    }
                )
        elif headers and headers[0].startswith("Activit"):
            for tr in table.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if len(cells) < 2:
                    continue
                label = cells[0]
                if label.startswith("BRVM"):
                    indices[label] = {
                        "level": parse_number(cells[1]),
                        "change_pct": parse_number(cells[2]) if len(cells) > 2 else None,
                    }
                else:
                    activity[label] = parse_number(cells[1])
    quotes = pd.DataFrame(rows)
    return LiveSnapshot(
        fetched_at=fetched_at or dt.datetime.now(),
        quotes=quotes,
        indices=indices,
        activity=activity,
    )


def fetch_live(timeout: float = 30.0, *, session: Any = None, cache_dir: str | Path | None = None,
               offline: bool = False, max_age_s: float = 60.0) -> LiveSnapshot:
    """Télécharge et analyse la page des cours du jour, **poliment** (comme la commande ``live``).

    La requête passe par ``brvm_alpha.notes.research.PoliteSession`` : session réseau commune
    (:mod:`brvm_alpha.net` : liste blanche, plafonds, délai total), robots.txt, au moins 10 s entre deux
    requêtes vers brvm.org (état partagé ``politeness.json``), arrêt au premier 403/429, quota de 3
    requêtes ; une page lue depuis moins de ``max_age_s`` secondes est reprise du cache. ``session`` :
    session polie déjà ouverte ; ``offline`` : cache seulement. Lève une erreur de collecte
    (``ResearchError``) ou ``RuntimeError`` pour un statut HTTP autre que 200.
    """
    from brvm_alpha.notes import research as rs

    if session is None:
        cdir = Path(cache_dir) if cache_dir is not None else rs.DEFAULT_NOTES_DIR / "cache"
        session = rs.PoliteSession(max_requests=3, offline=offline, cache_dir=cdir,
                                   log_path=cdir.parent / "fetch_log.jsonl", timeout=timeout)
    res = session.get(LIVE_URL, max_age_s=max_age_s)
    if res.status != 200:
        raise RuntimeError(f"HTTP {res.status} sur {LIVE_URL}")
    fetched = pd.Timestamp(res.fetched_at) if res.fetched_at else pd.Timestamp.now(tz="UTC")
    return parse_live_html(res.text, fetched_at=fetched.to_pydatetime())
