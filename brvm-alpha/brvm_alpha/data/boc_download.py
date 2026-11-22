"""Téléchargement poli des Bulletins Officiels de la Cote (BOC) publiés par la BRVM.

Les BOC sont des PDF publics publiés chaque jour de bourse sur
https://www.brvm.org/fr/bulletins-officiels-de-la-cote. Leur URL suit le motif
``/sites/default/files/boc_AAAAMMJJ[suffixe].pdf`` ; le suffixe varie selon les
années (``""``, ``"_2"``, ``"_2_0"``...).

Le module convertit chaque PDF en texte (mise en page conservée), compresse le
texte en ``.txt.gz`` et supprime le PDF : ~20 Ko par séance au lieu de ~1 Mo.
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
from pathlib import Path

import requests

BASE_URL = "https://www.brvm.org/sites/default/files/boc_{date}{suffix}.pdf"
USER_AGENT = "brvm-alpha/0.1 (outil d'analyse personnel; lecture des BOC publics)"
RECENT_SUFFIXES = ("_2", "", "_3", "_2_0", "_1")
OLD_SUFFIXES = ("", "_2", "_1", "_0", "_3")
SUFFIX_SWITCH = dt.date(2021, 1, 1)

log = logging.getLogger(__name__)


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


def fetch_one(session: requests.Session, day: dt.date, out_dir: Path, pause: float) -> str | None:
    """Télécharge le BOC d'une séance. Renvoie le nom du fichier ou None."""
    stamp = day.strftime("%Y%m%d")
    target = out_dir / f"boc_{stamp}.txt.gz"
    if target.exists() or (out_dir / f"boc_{stamp}.missing").exists():
        return target.name if target.exists() else None
    suffixes = RECENT_SUFFIXES if day >= SUFFIX_SWITCH else OLD_SUFFIXES
    for suffix in suffixes:
        url = BASE_URL.format(date=stamp, suffix=suffix)
        for attempt in range(3):
            try:
                resp = session.get(url, timeout=60)
                break
            except requests.RequestException as exc:  # réseau instable : on réessaie
                log.warning("%s : %s (essai %d)", url, exc, attempt + 1)
                time.sleep(pause * 4 * (attempt + 1))
        else:
            return None
        time.sleep(pause)
        if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
            continue
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
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
    # Aucun bulletin : jour férié ou fichier introuvable. On le note pour ne pas réessayer.
    (out_dir / f"boc_{stamp}.missing").touch()
    return None


def download_range(start: dt.date, end: dt.date, out_dir: Path, pause: float = 0.4) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    count = 0
    for day in weekdays(start, end):
        name = fetch_one(session, day, out_dir, pause)
        if name:
            count += 1
            log.info("%s OK (%d)", name, count)
    return count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2017-01-01")
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument("--out", default="data/boc_text")
    parser.add_argument("--pause", type=float, default=0.4, help="secondes entre requêtes")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    n = download_range(
        dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end), Path(args.out), args.pause
    )
    log.info("Terminé : %d bulletins", n)


if __name__ == "__main__":
    main()
