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

import pandas as pd
import requests
from bs4 import BeautifulSoup

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
    soup = BeautifulSoup(html, "lxml")
    rows = []
    indices: dict[str, dict[str, float | None]] = {}
    activity: dict[str, float | None] = {}
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if headers and headers[0].startswith("Symbole"):
            for tr in table.find("tbody").find_all("tr"):
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


def fetch_live(timeout: float = 30.0) -> LiveSnapshot:
    """Télécharge et analyse la page des cours du jour."""
    resp = requests.get(LIVE_URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return parse_live_html(resp.text)
