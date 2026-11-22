"""Magasin de données BRVM : panel multi-séances construit à partir des BOC.

Fonctions principales
---------------------
* :func:`build_panel` : analyse (en parallèle) tous les BOC d'un répertoire et écrit
  ``equities.parquet``, ``indices.parquet``, ``market.parquet``,
  ``order_book.parquet``, ``corporate_actions.parquet``, ``dividends.parquet``,
  ``adjusted_prices.parquet``, ``sessions.parquet`` (calendrier contigu des séances,
  bulletins manquants compris) et ``parse_report.csv``. Le traitement est
  **incrémental** : un cache (``_cache/``) mémorise le résultat de chaque fichier
  (clé : nom, taille, date de modification, version du parseur) ; seuls les
  fichiers nouveaux ou modifiés sont réanalysés.
* :func:`session_calendar` : calendrier contigu des séances d'après les numéros des
  bulletins (« N° 186 ») ; repère les séances réelles dont le BOC manque. La table
  actions porte le numéro global de séance ``session_no`` et la table des rendements
  ``missing_sessions`` (rendement couvrant plusieurs séances).
* :func:`load_equities`, :func:`load_indices` (+ ``load_market``,
  ``load_order_book``, ``load_corporate_actions``, ``load_sessions``) : lecture avec un index propre
  (``MultiIndex`` (date, symbol) / (date, index), trié, sans doublon).
* :func:`detect_corporate_actions` : détection des divisions / regroupements
  d'actions (rupture du cours hors de la bande de fluctuation de ±7,5 %, non
  expliquée par un détachement de dividende).
* :func:`detect_dividends` : détection des nouveaux dividendes (changement de la
  date du dernier dividende) et estimation de la date de détachement.
* :func:`adjusted_prices` (large, cours ajustés des divisions), :func:`total_return_index`
  (large, dividendes nets réinvestis) et :func:`adjusted_table` (table longue
  complète : ratios, dividendes, rendements, indice total return).
"""

from __future__ import annotations

import hashlib
import logging
import math
import multiprocessing
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from . import boc_parser
from .boc_parser import EQUITY_COLUMNS, INDEX_COLUMNS, ORDER_BOOK_COLUMNS, parse_boc_file, warning_code

log = logging.getLogger(__name__)

__all__ = [
    "INFO_WARNING_CODES",
    "PanelSummary",
    "adjusted_prices",
    "adjusted_table",
    "build_panel",
    "detect_corporate_actions",
    "detect_dividends",
    "load_corporate_actions",
    "load_equities",
    "load_indices",
    "load_market",
    "load_order_book",
    "load_sessions",
    "parser_version",
    "session_calendar",
    "total_return_index",
]

#: Codes d'avertissement purement informatifs (réparation réussie, cas normal rare).
INFO_WARNING_CODES = frozenset({"wrapped_digits_joined", "first_listing", "lang_en", "change_vs_adjusted_ref",
                                "untraded_ref_change", "position_override", "order_book_absent",
                                "order_book_empty"})

#: Bande de fluctuation quotidienne de la BRVM (±7,5 %) et marge de détection.
PRICE_BAND = 0.075
BAND_MARGIN = 0.025
#: Ratios « simples » de division (k nouvelles actions pour 1 ancienne) reconnus sur
#: une simple rupture de cours ; leurs inverses représentent des regroupements.
SIMPLE_RATIOS: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0)

_CACHE_TABLES = ("equities", "indices", "market", "order_book")
_FILE_RE = re.compile(r"^boc_(\d{8})\.txt(\.gz)?$")


# ---------------------------------------------------------------------------
# Version du parseur (invalide le cache quand le code change)
# ---------------------------------------------------------------------------


def parser_version() -> str:
    """Empreinte du code du parseur : toute modification invalide le cache."""
    src = Path(boc_parser.__file__).read_bytes()
    return hashlib.sha1(src).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Analyse d'un fichier (exécutée dans les processus de travail)
# ---------------------------------------------------------------------------


def _parse_one(path: str) -> dict[str, Any]:
    """Analyse un BOC et renvoie des tables sérialisables (jamais d'exception)."""
    name = os.path.basename(path)
    try:
        day = parse_boc_file(path)
    except Exception as exc:  # un fichier corrompu ne doit pas bloquer le panel
        return {"file": name, "error": f"{type(exc).__name__}: {exc}", "warnings": []}
    eq = day.equities.copy()
    idx = day.indices.copy()
    ob = day.order_book.copy()
    for df in (eq, idx, ob):
        df["source_file"] = name
    mk = pd.DataFrame([{"date": pd.Timestamp(day.date) if day.date else pd.NaT, **day.market, "source_file": name}])
    return {
        "file": name,
        "error": None,
        "date": day.date,
        "header_date": day.meta.get("header_date"),
        "issue_no": day.meta.get("issue_no"),
        "lang": day.meta.get("lang"),
        "equities": eq,
        "indices": idx,
        "order_book": ob,
        "market": mk,
        "warnings": day.warnings,
    }


# ---------------------------------------------------------------------------
# Cache incrémental
# ---------------------------------------------------------------------------


def _file_key(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_size, int(st.st_mtime)


def _read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame(columns=columns or [])


def _concat(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    frames = [f for f in frames if f is not None and len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@dataclass
class PanelSummary:
    """Résumé d'une construction de panel."""

    n_files: int
    n_parsed: int
    n_cached: int
    n_errors: int
    n_sessions: int
    first_date: pd.Timestamp | None
    last_date: pd.Timestamp | None
    n_symbols: int
    n_rows: int
    row_warning_rate: float
    row_anomaly_rate: float
    top_warnings: list[tuple[str, int]]
    out_dir: Path
    #: Séances dont le BOC manque (numéros de bulletin sautés) et nombre de trous.
    n_missing_sessions: int = 0
    n_gaps: int = 0

    def __str__(self) -> str:  # pragma: no cover - affichage
        top = "\n".join(f"    {n:6d}  {c}" for c, n in self.top_warnings)
        return (
            f"Fichiers : {self.n_files} (analysés {self.n_parsed}, cache {self.n_cached}, erreurs {self.n_errors})\n"
            f"Séances  : {self.n_sessions} du {self.first_date:%Y-%m-%d} au {self.last_date:%Y-%m-%d}"
            f" ; {self.n_missing_sessions} séances sans BOC ({self.n_gaps} trous, voir sessions.parquet)\n"
            f"Symboles : {self.n_symbols} ; lignes actions : {self.n_rows}\n"
            f"Lignes avec avertissement : {self.row_warning_rate:.2%} "
            f"(hors informatifs : {self.row_anomaly_rate:.2%})\n"
            f"Avertissements les plus fréquents :\n{top}"
        )


def build_panel(
    boc_dir: str | Path,
    out_dir: str | Path,
    *,
    workers: int | None = None,
    force: bool = False,
) -> PanelSummary:
    """Construit (ou met à jour) le panel à partir des BOC texte de ``boc_dir``.

    Parameters
    ----------
    boc_dir:
        Répertoire contenant les ``boc_AAAAMMJJ.txt.gz`` (ou ``.txt``).
    out_dir:
        Répertoire de sortie (créé si besoin).
    workers:
        Nombre de processus d'analyse (défaut : nombre de cœurs).
    force:
        Ignore le cache et réanalyse tous les fichiers.
    """
    boc_dir, out_dir = Path(boc_dir), Path(out_dir)
    cache_dir = out_dir / "_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    version = parser_version()

    files = sorted(p for p in boc_dir.iterdir() if _FILE_RE.match(p.name))
    # Si .txt et .txt.gz coexistent pour une date, on garde le .gz (sortie du téléchargeur).
    by_stamp: dict[str, Path] = {}
    for p in files:
        stamp = _FILE_RE.match(p.name).group(1)  # type: ignore[union-attr]
        if stamp not in by_stamp or p.suffix == ".gz":
            by_stamp[stamp] = p
    files = [by_stamp[s] for s in sorted(by_stamp)]

    manifest = _read_parquet(cache_dir / "manifest.parquet")
    cached: dict[str, pd.DataFrame] = {t: _read_parquet(cache_dir / f"{t}.parquet") for t in _CACHE_TABLES}
    known: dict[str, tuple[int, int, str]] = {}
    if not force and len(manifest):
        for r in manifest.itertuples(index=False):
            known[r.file] = (int(r.size), int(r.mtime), str(r.version))
    todo: list[Path] = []
    for p in files:
        size, mtime = _file_key(p)
        if known.get(p.name) != (size, mtime, version):
            todo.append(p)
    todo_names = {p.name for p in todo}
    present = {p.name for p in files}

    # Analyse parallèle des fichiers nouveaux ou modifiés.
    results: list[dict[str, Any]] = []
    if todo:
        n_workers = workers or os.cpu_count() or 1
        if n_workers > 1 and len(todo) > 4:
            # « fork » est déconseillé depuis un processus multi-threadé (pyarrow...).
            methods = multiprocessing.get_all_start_methods()
            ctx = multiprocessing.get_context("forkserver" if "forkserver" in methods else "spawn")
            with ProcessPoolExecutor(max_workers=min(n_workers, len(todo)), mp_context=ctx) as pool:
                results = list(pool.map(_parse_one, [str(p) for p in todo], chunksize=8))
        else:
            results = [_parse_one(str(p)) for p in todo]
    log.info("BOC : %d fichiers, %d à analyser", len(files), len(todo))

    # Mise à jour du cache : on retire les anciennes lignes des fichiers réanalysés
    # ou disparus, puis on ajoute les nouvelles.
    for t in _CACHE_TABLES:
        old = cached[t]
        if len(old) and "source_file" in old.columns:
            old = old[old["source_file"].isin(present) & ~old["source_file"].isin(todo_names)]
        cached[t] = _concat([old, *(r[t] for r in results if r.get(t) is not None)])
    new_manifest = []
    for r in results:
        p = boc_dir / r["file"]
        size, mtime = _file_key(p)
        new_manifest.append({
            "file": r["file"], "size": size, "mtime": mtime, "version": version,
            "date": pd.Timestamp(r["date"]) if r.get("date") else pd.NaT,
            "header_date": pd.Timestamp(r["header_date"]) if r.get("header_date") else pd.NaT,
            "issue_no": float(r["issue_no"]) if r.get("issue_no") else np.nan,
            "lang": r.get("lang"),
            "n_equities": len(r["equities"]) if r.get("equities") is not None else 0,
            "n_indices": len(r["indices"]) if r.get("indices") is not None else 0,
            "n_order_book": len(r["order_book"]) if r.get("order_book") is not None else 0,
            "n_warnings": len(r["warnings"]),
            "warning_codes": ";".join(f"{c}={n}" for c, n in Counter(map(warning_code, r["warnings"])).most_common()),
            "warnings": " | ".join(r["warnings"]),
            "error": r.get("error"),
        })
    if len(manifest):
        manifest = manifest[manifest["file"].isin(present) & ~manifest["file"].isin(todo_names)]
    manifest = _concat([manifest, pd.DataFrame(new_manifest)])
    if len(manifest):
        manifest = manifest.sort_values("file").reset_index(drop=True)
    for t in _CACHE_TABLES:
        _write_parquet(cached[t], cache_dir / f"{t}.parquet")
    _write_parquet(manifest, cache_dir / "manifest.parquet")

    # Tables finales.
    excluded = _duplicate_sessions(manifest, cached["equities"])
    sessions = session_calendar(_available_sessions(manifest, excluded), _marker_dates(boc_dir))
    equities = _attach_sessions(_finalize_equities(cached["equities"], excluded), sessions)
    indices = _finalize_simple(cached["indices"], excluded, ["date", "index"], INDEX_COLUMNS)
    market = _finalize_simple(cached["market"], excluded, ["date"], None)
    order_book = _finalize_simple(cached["order_book"], excluded, ["date", "symbol"], ORDER_BOOK_COLUMNS)
    dividends = detect_dividends(equities)
    corporate = detect_corporate_actions(equities, dividends)
    adjusted = adjusted_table(equities, corporate, dividends)

    _write_parquet(equities, out_dir / "equities.parquet")
    _write_parquet(sessions, out_dir / "sessions.parquet")
    _write_parquet(indices, out_dir / "indices.parquet")
    _write_parquet(market, out_dir / "market.parquet")
    _write_parquet(order_book, out_dir / "order_book.parquet")
    _write_parquet(dividends, out_dir / "dividends.parquet")
    _write_parquet(corporate, out_dir / "corporate_actions.parquet")
    _write_parquet(adjusted, out_dir / "adjusted_prices.parquet")

    report = manifest.drop(columns=["size", "mtime", "version"], errors="ignore").copy()
    report["excluded"] = report["file"].map(excluded).fillna("")
    if len(sessions):
        avail = sessions[sessions["available"]]
        report["missing_before"] = report["file"].map(pd.Series(avail["missing_before"].to_numpy(),
                                                                index=avail["source_file"]))
    report.to_csv(out_dir / "parse_report.csv", index=False)

    # Résumé.
    codes: Counter[str] = Counter()
    for w in manifest.get("warnings", pd.Series(dtype=str)).fillna(""):
        for part in filter(None, w.split(" | ")):
            codes[warning_code(part)] += 1
    row_codes = equities["warnings"].fillna("") if len(equities) else pd.Series(dtype=str)
    anomalies = row_codes.map(lambda s: any(c and c not in INFO_WARNING_CODES for c in s.split(";")))
    dates = equities["date"] if len(equities) else pd.Series(dtype="datetime64[ns]")
    summary = PanelSummary(
        n_files=len(files),
        n_parsed=len(todo),
        n_cached=len(files) - len(todo),
        n_errors=int(manifest["error"].notna().sum()) if len(manifest) else 0,
        n_sessions=int(dates.nunique()),
        first_date=dates.min() if len(dates) else None,
        last_date=dates.max() if len(dates) else None,
        n_symbols=int(equities["symbol"].nunique()) if len(equities) else 0,
        n_rows=len(equities),
        row_warning_rate=float((row_codes != "").mean()) if len(row_codes) else 0.0,
        row_anomaly_rate=float(anomalies.mean()) if len(anomalies) else 0.0,
        top_warnings=codes.most_common(10),
        out_dir=out_dir,
        n_missing_sessions=int((~sessions["available"]).sum()) if len(sessions) else 0,
        n_gaps=int((sessions["missing_before"] > 0).sum()) if len(sessions) else 0,
    )
    log.info("%s", summary)
    return summary


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def _duplicate_sessions(manifest: pd.DataFrame, equities: pd.DataFrame) -> dict[str, str]:
    """Fichiers à exclure : séance en double ou copie du bulletin d'une autre date.

    * même date de séance obtenue par deux fichiers -> on garde celui dont le nom
      correspond à l'en-tête ;
    * contenu identique (symbole, clôture, volume, valeur) à la séance précédente
      avec des échanges -> republication du BOC de la veille, exclue.
    """
    excluded: dict[str, str] = {}
    if not len(manifest) or not len(equities):
        return excluded
    m = manifest[manifest["error"].isna()].copy()
    for d, grp in m.groupby("date"):
        if len(grp) > 1:
            good = grp[grp["header_date"] == d]
            keep = (good if len(good) else grp)["file"].iloc[0]
            for f in grp["file"]:
                if f != keep:
                    excluded[f] = f"duplicate_date:{keep}"
    sig = (
        equities.sort_values(["source_file", "symbol"])
        .groupby("source_file")
        .apply(lambda g: hashlib.sha1(
            g[["symbol", "close", "volume", "value"]].to_csv(index=False).encode()).hexdigest(),
            include_groups=False)
    )
    traded = equities.groupby("source_file")["volume"].sum()
    prev_sig, prev_file = None, None
    for f in sorted(sig.index):
        if f in excluded:
            continue
        if prev_sig is not None and sig[f] == prev_sig and traded.get(f, 0) > 0:
            excluded[f] = f"duplicate_content:{prev_file}"
            continue
        prev_sig, prev_file = sig[f], f
    return excluded


# ---------------------------------------------------------------------------
# Calendrier des séances (numéros des bulletins)
# ---------------------------------------------------------------------------

SESSION_COLUMNS = ["session_no", "year", "issue_no", "date", "available", "source_file", "missing_before",
                   "gap_start", "gap_end", "estimated", "marker"]
_MARKER_RE = re.compile(r"^boc_(\d{8})\.(missing|bad)$")
_DAY = np.timedelta64(1, "D")


def _open_days(lo: np.datetime64, hi: np.datetime64) -> np.ndarray:
    """Jours ouvrés de ``[lo, hi[`` hors 1er janvier et 25 décembre (fériés partout dans l'UEMOA)."""
    if hi <= lo:
        return np.array([], dtype="datetime64[D]")
    days = np.arange(lo, hi, dtype="datetime64[D]")
    days = days[np.is_busday(days)]
    idx = pd.DatetimeIndex(days)
    keep = ~(((idx.month == 1) & (idx.day == 1)) | ((idx.month == 12) & (idx.day == 25)))
    return days[np.asarray(keep)]


def _year_issues(dates: np.ndarray, raw: np.ndarray, jan1: np.datetime64) -> tuple[np.ndarray, np.ndarray]:
    """Numéros des bulletins d'une année (validés, à défaut estimés) et masque des estimés.

    Un numéro lu est retenu s'il prolonge la suite strictement croissante et ne dépasse
    pas le nombre de jours ouvrés écoulés depuis le 1er janvier. Un numéro absent ou
    incohérent est estimé : numéro précédent + 1 + jours ouvrés intercalaires, borné par
    le numéro lu suivant.
    """
    n = len(dates)
    valid = np.full(n, np.nan)
    prev = 0.0
    for k in range(n):
        x = raw[k]
        if np.isfinite(x) and x == int(x) and prev < x <= np.busday_count(jan1, dates[k] + _DAY):
            valid[k] = prev = x
    est = ~np.isfinite(valid)
    issues = valid.copy()
    prev_i, prev_d = 0.0, jan1 - _DAY
    for k in range(n):
        if est[k]:
            guess = prev_i + 1 + len(_open_days(prev_d + _DAY, dates[k]))
            nxt = next((j for j in range(k + 1, n) if not est[j]), None)
            if nxt is not None:
                guess = min(guess, valid[nxt] - (nxt - k))
            issues[k] = max(prev_i + 1, guess)
        elif issues[k] <= prev_i:  # données contradictoires : on garde une suite croissante
            issues[k], est[k] = prev_i + 1, True
        prev_i, prev_d = issues[k], dates[k]
    return issues, est


def session_calendar(available: pd.DataFrame, markers: dict[pd.Timestamp, str] | None = None) -> pd.DataFrame:
    """Calendrier contigu des séances : une ligne par numéro de bulletin, disponible ou non.

    Chaque BOC porte un numéro (« N° 186 ») remis à 1 au premier jour de bourse de
    l'année ; deux BOC successifs disponibles dont les numéros ne se suivent pas
    encadrent des séances **réelles** dont le bulletin manque (le téléchargeur les a
    notées ``.missing`` comme des jours fériés : 2021-05-07 -> 2021-06-24, N° 89 à 120 ;
    2026-10-02, N° 187). ``available`` : table (``date``, ``source_file``, ``issue_no``)
    des BOC retenus ; ``markers`` : {date: ``"missing"`` | ``"bad"``} (fichiers témoins
    du téléchargeur).

    Colonnes :

    * ``session_no`` : numéro global de séance, contigu (manquantes comprises) ; la
      différence entre deux séances moins 1 est le nombre de séances manquantes ;
    * ``year``, ``issue_no`` : année et numéro du bulletin ;
    * ``date`` : date de la séance (pour une séance manquante : déduite quand les
      jours ouvrés du trou sont exactement aussi nombreux que les bulletins manquants,
      sinon ``NaT``) ;
    * ``available`` / ``source_file`` : bulletin présent dans le panel ;
    * ``missing_before`` : séances manquantes juste avant (séances disponibles) ;
    * ``gap_start`` / ``gap_end`` : séances disponibles qui encadrent le trou (séances
      manquantes) ;
    * ``estimated`` : numéro non lu sur le bulletin mais estimé (numéro illisible, fin
      d'année ou année sans bulletin : nombre de jours ouvrés hors 1er janvier et
      25 décembre) ;
    * ``marker`` : ``"bad"`` (PDF illisible, ex. 2020-07-07) ou ``"missing"`` (aucun PDF
      à l'URL attendue) pour une séance manquante datée.

    Le calendrier commence à la première et finit à la dernière séance disponible.
    """
    if available is None or not len(available):
        return pd.DataFrame(columns=SESSION_COLUMNS)
    a = available.dropna(subset=["date"]).copy()
    a["date"] = pd.to_datetime(a["date"]).dt.normalize()
    a = a.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if "issue_no" not in a.columns:
        a["issue_no"] = np.nan
    if "source_file" not in a.columns:
        a["source_file"] = None
    markers = markers or {}
    years = a["date"].dt.year.to_numpy()
    first_year, last_year = int(years[0]), int(years[-1])
    rows: list[dict[str, Any]] = []
    offset = 0
    for y in range(first_year, last_year + 1):
        jan1, next_jan1 = np.datetime64(f"{y}-01-01", "D"), np.datetime64(f"{y + 1}-01-01", "D")
        g = a[years == y]
        if not len(g):  # année entière sans bulletin : nombre de séances estimé
            total = len(_open_days(jan1, next_jan1))
            rows += [{"session_no": offset + k, "year": y, "issue_no": k, "available": False, "estimated": True}
                     for k in range(1, total + 1)]
            offset += total
            continue
        dates = g["date"].to_numpy("datetime64[D]")
        issues, est = _year_issues(dates, pd.to_numeric(g["issue_no"], errors="coerce").to_numpy(float), jan1)
        by_issue = {int(n): k for k, n in enumerate(issues)}
        start = int(issues[0]) if y == first_year else 1
        last = int(issues[-1])
        trailing = 0 if y == last_year else len(_open_days(dates[-1] + _DAY, next_jan1))
        for n in range(start, last + trailing + 1):
            k = by_issue.get(n)
            if k is None:
                rows.append({"session_no": offset + n, "year": y, "issue_no": n, "available": False,
                             "estimated": n > last})
            else:
                rows.append({"session_no": offset + n, "year": y, "issue_no": n, "date": pd.Timestamp(dates[k]),
                             "available": True, "source_file": g["source_file"].iloc[k],
                             "estimated": bool(est[k])})
        offset += last + trailing
    cal = pd.DataFrame(rows)
    for col in SESSION_COLUMNS:
        if col not in cal.columns:
            cal[col] = None
    cal["date"] = pd.to_datetime(cal["date"])
    cal["gap_start"] = pd.NaT
    cal["gap_end"] = pd.NaT
    cal["missing_before"] = 0
    cal["marker"] = ""
    avail = np.flatnonzero(cal["available"].to_numpy(bool))
    sess = cal["session_no"].to_numpy(int)
    for a_i, b_i in zip(avail[:-1], avail[1:]):
        m = b_i - a_i - 1
        cal.iat[b_i, cal.columns.get_loc("missing_before")] = int(sess[b_i] - sess[a_i] - 1)
        if m <= 0:
            continue
        da, db = cal.at[a_i, "date"], cal.at[b_i, "date"]
        run = slice(a_i + 1, b_i)
        cal.loc[cal.index[run], "gap_start"] = da
        cal.loc[cal.index[run], "gap_end"] = db
        days = _open_days(np.datetime64(da.date(), "D") + _DAY, np.datetime64(db.date(), "D"))
        if len(days) == m:  # une séance par jour ouvré du trou : dates déduites
            cal.loc[cal.index[run], "date"] = pd.DatetimeIndex(days)
            cal.loc[cal.index[run], "marker"] = [markers.get(pd.Timestamp(d), "") for d in days]
    cal["available"] = cal["available"].astype(bool)
    cal["estimated"] = cal["estimated"].fillna(False).astype(bool)
    cal["session_no"] = cal["session_no"].astype("int64")
    cal["year"] = cal["year"].astype("int64")
    cal["issue_no"] = cal["issue_no"].astype("int64")
    cal["missing_before"] = cal["missing_before"].astype("int64")
    return cal[SESSION_COLUMNS]


def _available_sessions(manifest: pd.DataFrame, excluded: dict[str, str]) -> pd.DataFrame:
    """BOC retenus dans le panel : (date, source_file, issue_no)."""
    if not len(manifest):
        return pd.DataFrame(columns=["date", "source_file", "issue_no"])
    m = manifest[manifest["error"].isna() & ~manifest["file"].isin(excluded) & manifest["date"].notna()]
    issue = m["issue_no"] if "issue_no" in m.columns else pd.Series(np.nan, index=m.index)
    return pd.DataFrame({"date": pd.to_datetime(m["date"]), "source_file": m["file"], "issue_no": issue})


def _marker_dates(boc_dir: Path) -> dict[pd.Timestamp, str]:
    """Fichiers témoins du téléchargeur : ``boc_AAAAMMJJ.missing`` / ``.bad``."""
    out: dict[pd.Timestamp, str] = {}
    for p in boc_dir.iterdir():
        m = _MARKER_RE.match(p.name)
        if m:
            out[pd.Timestamp(m.group(1))] = m.group(2)
    return out


def _attach_sessions(eq: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    """Ajoute à la table actions le numéro global de séance (``session_no``)."""
    if not len(eq) or not len(sessions):
        return eq
    avail = sessions[sessions["available"]]
    eq["session_no"] = eq["date"].map(pd.Series(avail["session_no"].to_numpy(), index=avail["date"]))
    if eq["session_no"].notna().all():
        eq["session_no"] = eq["session_no"].astype("int64")
    return eq


def _session_numbers(g: pd.DataFrame) -> tuple[np.ndarray, bool]:
    """Numéros de séance des lignes d'un titre et indicateur « calendrier exact ».

    Avec la colonne ``session_no`` du panel (calendrier des numéros de BOC), la
    différence entre deux lignes moins 1 est le nombre exact de séances manquantes. À
    défaut (tables construites à la main), rang des jours ouvrés : un jour ouvré sans
    séance peut alors être un simple jour férié.
    """
    if "session_no" in g.columns:
        s = pd.to_numeric(g["session_no"], errors="coerce").to_numpy(float)
        if len(s) and np.isfinite(s).all():
            return s, True
    d = pd.to_datetime(g["date"]).to_numpy("datetime64[D]")
    return np.busday_count(np.datetime64("1970-01-01"), d).astype(float), False


def _missing_between(sess: np.ndarray, a: int, b: int) -> int:
    """Séances manquantes entre les lignes ``a`` < ``b`` d'un titre."""
    return int(sess[b] - sess[a] - 1)


def _has_gap(sess: np.ndarray, exact: bool, a: int, b: int) -> bool:
    """Des séances manquent-elles entre les lignes ``a`` et ``b`` ?

    Sans calendrier exact, un seul jour ouvré intercalaire est présumé férié.
    """
    return _missing_between(sess, a, b) > (0 if exact else 1)


def _finalize_equities(eq: pd.DataFrame, excluded: dict[str, str]) -> pd.DataFrame:
    """Table actions finale : exclusions, dédoublonnage, secteur complété, tri."""
    if not len(eq):
        return pd.DataFrame(columns=[*EQUITY_COLUMNS, "source_file"])
    eq = eq[~eq["source_file"].isin(excluded)].copy()
    eq["date"] = pd.to_datetime(eq["date"])
    eq["last_div_date"] = pd.to_datetime(eq["last_div_date"])
    eq = eq.sort_values(["date", "symbol", "source_file"]).drop_duplicates(["date", "symbol"], keep="first")
    # Secteur manquant (omission ponctuelle du BOC) : repris de la même valeur dans la
    # même nomenclature (codes 2025+ : CB/CD/ENE/TEL..., avant : AGR/DIS/TRP...).
    era = (eq["date"] >= pd.Timestamp("2025-01-01")).astype(int)
    eq["sector"] = eq.groupby([eq["symbol"], era])["sector"].transform(lambda s: s.ffill().bfill())
    num_cols = ["prev_close", "open", "close", "change_pct", "volume", "value", "ref_price",
                "ytd_pct", "last_div_net", "net_yield_pct", "per"]
    eq[num_cols] = eq[num_cols].astype("float64")
    # Contrat du panel : volume / valeur à 0 (et non vides) quand le titre n'a pas été échangé.
    untraded = eq["status"] != "traded"
    eq.loc[untraded, ["volume", "value"]] = eq.loc[untraded, ["volume", "value"]].fillna(0.0)
    eq["ex_div"] = eq["ex_div"].astype(bool)
    return eq.reset_index(drop=True)


def _finalize_simple(df: pd.DataFrame, excluded: dict[str, str], keys: list[str], columns: list[str] | None) -> pd.DataFrame:
    """Exclusions, dédoublonnage sur ``keys`` et tri d'une table secondaire."""
    if not len(df):
        return pd.DataFrame(columns=[*(columns or keys), "source_file"])
    df = df[~df["source_file"].isin(excluded)].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["date"]).sort_values([*keys, "source_file"]).drop_duplicates(keys, keep="first")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def _load(panel_dir: str | Path, name: str) -> pd.DataFrame:
    path = Path(panel_dir) / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} introuvable : lancer build_panel() d'abord")
    return pd.read_parquet(path)


def _filter_dates(df: pd.DataFrame, start: Any, end: Any) -> pd.DataFrame:
    if start is not None:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end is not None:
        df = df[df["date"] <= pd.Timestamp(end)]
    return df


def load_equities(
    panel_dir: str | Path,
    symbols: Iterable[str] | None = None,
    start: Any = None,
    end: Any = None,
    traded_only: bool = False,
) -> pd.DataFrame:
    """Actions, indexées par ``(date, symbol)`` (trié, unique)."""
    df = _filter_dates(_load(panel_dir, "equities"), start, end)
    if symbols is not None:
        df = df[df["symbol"].isin(list(symbols))]
    if traded_only:
        df = df[df["status"] == "traded"]
    return df.set_index(["date", "symbol"]).sort_index()


def load_indices(
    panel_dir: str | Path,
    indices: Iterable[str] | None = None,
    start: Any = None,
    end: Any = None,
    wide: bool = False,
) -> pd.DataFrame:
    """Indices, indexés par ``(date, index)`` ; ``wide=True`` : niveaux en colonnes."""
    df = _filter_dates(_load(panel_dir, "indices"), start, end)
    if indices is not None:
        df = df[df["index"].isin(list(indices))]
    if wide:
        return df.pivot(index="date", columns="index", values="level").sort_index()
    return df.set_index(["date", "index"]).sort_index()


def load_market(panel_dir: str | Path, start: Any = None, end: Any = None) -> pd.DataFrame:
    """Indicateurs de marché, indexés par date."""
    return _filter_dates(_load(panel_dir, "market"), start, end).set_index("date").sort_index()


def load_order_book(panel_dir: str | Path, start: Any = None, end: Any = None) -> pd.DataFrame:
    """Meilleures limites, indexées par ``(date, symbol)``."""
    return _filter_dates(_load(panel_dir, "order_book"), start, end).set_index(["date", "symbol"]).sort_index()


def load_sessions(panel_dir: str | Path, available_only: bool = False) -> pd.DataFrame:
    """Calendrier contigu des séances (voir :func:`session_calendar`), indexé par ``session_no``."""
    df = _load(panel_dir, "sessions")
    if available_only:
        df = df[df["available"]]
    return df.set_index("session_no").sort_index()


def load_corporate_actions(panel_dir: str | Path) -> pd.DataFrame:
    """Événements sur titres détectés (divisions, regroupements, ruptures inexpliquées)."""
    return _load(panel_dir, "corporate_actions")


# ---------------------------------------------------------------------------
# Dividendes
# ---------------------------------------------------------------------------

DIVIDEND_COLUMNS = ["symbol", "ex_date", "amount", "payment_date", "first_seen", "evidence", "close_before", "yield_pct"]


#: Preuves de détachement jugées fortes (marqueur, baisse de la référence ou du cours
#: précédent publié du montant).
STRONG_EX_EVIDENCE = ("ex_div_flag", "ref_adjusted", "prev_close_adjusted")
#: Délai (jours) pendant lequel la BOC peut corriger le montant d'un dividende publié.
DIVIDEND_CORRECTION_DAYS = 30
#: Délai (jours) en deçà duquel un même montant republié sans preuve de détachement est
#: une republication du dividende précédent (et non un second versement).
DIVIDEND_REPUBLICATION_DAYS = 365


def detect_dividends(equities: pd.DataFrame) -> pd.DataFrame:
    """Nouveaux dividendes : la date du « dernier dividende payé » change.

    Un dividende est *nouveau* quand ``last_div_date`` devient postérieure à toutes
    les dates déjà vues pour le titre (une date qui « revient en arrière » est une
    coquille). Le premier dividende publié pour un titre est nouveau lorsque les
    séances antérieures du titre avaient une colonne dividende vide et qu'il a été payé
    après la première séance (voir :func:`_known_at_history_start`). Ne sont **pas** de
    nouveaux dividendes :

    * le dividende publié dès la première séance du titre ou payé avant elle ;
    * une correction de date à montant identique dans les 60 jours suivant un
      dividende détecté (fusionnée avec lui) ;
    * un même montant republié moins d'un an après, sans marqueur ni baisse de la
      référence (CIEC : 3 465 du 12/07/2017, effacé le 13/07 puis republié daté du
      20/09/2017) ;
    * un montant retraité après une division : même date et montant / k, ou montant
      précédent / nouveau ≈ ajustement de cours publié à ±3 séances (FTSC 31/01/2018 :
      1 045 -> 261 daté du 09/01/2018, le jour de la division par 4).

    Un montant corrigé par la BOC pour la même date dans les
    ``DIVIDEND_CORRECTION_DAYS`` jours remplace le premier quand il explique mieux la
    baisse de la référence au détachement (ONTBF : 226,45 -> 266,45, baisse 2 995 ->
    2 730), ou, sans baisse mesurable, s'il en reste proche (rapport dans [2/3, 3/2]).

    Date de détachement (``ex_date``), par ordre de préférence (voir
    :func:`_find_ex_date` pour la fenêtre de recherche) :

    1. séance suivant un marqueur ``(d)`` (ex-dividende) dont le cours de référence
       est abaissé d'environ le dividende (``clôture - réf`` ≈ montant) ;
    2. séance suivant une telle baisse de la référence, sans marqueur ;
    3. séance dont le cours précédent publié est abaissé du montant (titre suspendu
       au détachement, cours ajusté à la reprise) ;
    4. séance suivant un marqueur ``(d)`` seul ;
    5. séance marquée ``(V)`` (variation calculée sur la référence ajustée) ;
    6. information publiée plus de 7 jours après le paiement : date de paiement - 2
       jours ouvrés ; dans un trou de BOC manquants, première séance après le trou ;
    7. à défaut, la première séance où le nouveau dividende apparaît.

    Un détachement voisin d'un trou de plus de ``MAX_MISSING_SESSIONS`` séances
    (calendrier des numéros de BOC) porte ``+data_gap`` dans ``evidence``.
    """
    if equities is None or not len(equities):
        return pd.DataFrame(columns=DIVIDEND_COLUMNS)
    eq = equities.reset_index() if "symbol" not in equities.columns else equities
    out: list[dict[str, Any]] = []
    for sym, g in eq.sort_values("date").groupby("symbol", sort=True):
        g = g.reset_index(drop=True)
        dates = g["date"].to_numpy()
        sess, _ = _session_numbers(g)
        first_session = g.at[0, "date"]
        seen_max: pd.Timestamp | None = None
        last_event: dict[str, Any] | None = None
        for i, row in enumerate(g.itertuples(index=False)):
            ddate = row.last_div_date
            if pd.isna(ddate):
                continue
            if seen_max is None and _known_at_history_start(i, ddate, first_session):
                seen_max = ddate  # dividende déjà connu au début de l'historique
                continue
            amount = row.last_div_net
            valid = amount is not None and np.isfinite(amount) and amount > 0
            if (valid and last_event is not None and ddate == last_event["payment_date"]
                    and abs(amount - last_event["amount"]) > 1e-6
                    and (row.date - last_event["first_seen"]).days <= DIVIDEND_CORRECTION_DAYS):
                _correct_dividend_amount(g, last_event, float(amount), i)
                continue
            if seen_max is not None and ddate <= seen_max:
                continue
            seen_max = ddate
            if not valid:
                continue
            if i > 0 and _is_split_restatement(g, i, g.at[i - 1, "last_div_net"], amount):
                continue
            same_amount = last_event is not None and abs(last_event["amount"] - amount) < 1e-6
            if same_amount and (row.date - last_event["first_seen"]).days <= 60:  # type: ignore[index]
                last_event["payment_date"] = ddate  # type: ignore[index]  # simple correction de la date
                continue
            ex_i, evidence = _find_ex_date(g, i, amount, ddate)
            if (same_amount and evidence not in STRONG_EX_EVIDENCE
                    and (row.date - last_event["first_seen"]).days <= DIVIDEND_REPUBLICATION_DAYS):  # type: ignore[index]
                continue  # republication du dividende précédent, sans détachement
            if _next_to_data_gap(sess, ex_i):
                evidence += "+data_gap"  # détachement probablement dans un trou de BOC manquants
            close_before = g.at[ex_i - 1, "close"] if ex_i > 0 else np.nan
            last_event = {
                "symbol": sym,
                "ex_date": pd.Timestamp(dates[ex_i]),
                "amount": float(amount),
                "payment_date": ddate,
                "first_seen": row.date,
                "evidence": evidence,
                "close_before": close_before,
                "yield_pct": float(amount / close_before * 100) if close_before and close_before > 0 else np.nan,
            }
            out.append(last_event)
    return pd.DataFrame(out, columns=DIVIDEND_COLUMNS)


def _known_at_history_start(i: int, payment_date: pd.Timestamp, first_session: pd.Timestamp) -> bool:
    """Le premier « dernier dividende » publié pour un titre précède-t-il son historique ?

    Oui s'il figure dès la première séance du titre (``i == 0``), ou s'il a été payé
    avant celle-ci (colonne vide sur les premières séances). Sinon les séances
    antérieures avaient une colonne dividende vide (nouvelle cotation, titre n'ayant
    encore rien distribué) : c'est le premier dividende versé pendant l'historique
    (ORAC, cotée le 30/12/2022 : 752,76 apparu le 12/06/2023 avec (d) et référence
    9 600 -> 8 850).
    """
    return i == 0 or payment_date < first_session


def _next_to_data_gap(sess: np.ndarray, i: int) -> bool:
    """La séance ``i`` jouxte-t-elle un trou de plus de ``MAX_MISSING_SESSIONS`` séances ?

    ``sess`` : numéros de séance du titre (:func:`_session_numbers`).
    """
    for a, b in ((i - 1, i), (i, i + 1)):
        if 0 <= a and b < len(sess) and _missing_between(sess, a, b) > MAX_MISSING_SESSIONS:
            return True
    return False


def _published_adjustments(g: pd.DataFrame, lo: int, hi: int) -> list[float]:
    """Ajustements de cours publiés par la BOC entre les séances ``lo`` et ``hi`` (incluses).

    Rapports ``clôture[s-1] / précédent_publié[s]`` et ``clôture[s-1] / référence[s-1]``
    sortant de la bande de fluctuation (division, regroupement, augmentation de capital).
    """
    out: list[float] = []
    log_band = math.log(1 + PRICE_BAND + BAND_MARGIN)
    for s in range(max(1, lo), min(len(g) - 1, hi) + 1):
        c = g.at[s - 1, "close"]
        for den in (g.at[s, "prev_close"], g.at[s - 1, "ref_price"]):
            if pd.notna(c) and pd.notna(den) and c > 0 and den > 0 and abs(math.log(c / den)) > log_band:
                out.append(float(c / den))
    return out


def _is_split_restatement(g: pd.DataFrame, i: int, old: float, new: float) -> bool:
    """Le dividende ``new`` apparu à la séance ``i`` est-il l'ancien ``old`` exprimé après division ?"""
    if old is None or not np.isfinite(old) or old <= 0 or new <= 0:
        return False
    f = old / new
    if abs(math.log(f)) < math.log(1.15):
        return False
    return any(abs(math.log(f / adj)) < math.log(1.03) for adj in _published_adjustments(g, i - 3, i + 3))


def _correct_dividend_amount(g: pd.DataFrame, event: dict[str, Any], new: float, i: int) -> None:
    """Montant d'un dividende corrigé par la BOC (même date) : garde le plus vraisemblable."""
    old = event["amount"]
    i0 = int(np.searchsorted(g["date"].to_numpy(), np.datetime64(event["first_seen"])))
    if _published_adjustments(g, i0, i):
        return  # division entre-temps : montant retraité en nouvelles actions, pas une correction
    ex_i = int(np.searchsorted(g["date"].to_numpy(), np.datetime64(event["ex_date"])))
    drop = np.nan
    if 0 < ex_i < len(g):
        c, r = g.at[ex_i - 1, "close"], g.at[ex_i - 1, "ref_price"]
        if pd.notna(c) and pd.notna(r) and c > r:
            drop = float(c - r)
    if np.isfinite(drop):
        better = abs(new - drop) < abs(old - drop)
    else:
        better = 2.0 / 3.0 <= new / old <= 1.5
    if better:
        event["amount"] = new
        event["evidence"] = f"{event['evidence']}+amount_corrected"
        cb = event["close_before"]
        event["yield_pct"] = float(new / cb * 100) if cb and cb > 0 else np.nan


def _find_ex_date(g: pd.DataFrame, i: int, amount: float, payment_date: pd.Timestamp | None = None) -> tuple[int, str]:
    """Indice de la séance de détachement du dividende apparu à la ligne ``i``.

    Fenêtre de recherche : de 30 jours avant ``min(première apparition, date de
    paiement)`` à 10 séances après la première apparition (la BRVM met parfois à
    jour la colonne « dernier dividende » plusieurs semaines après le détachement).

    Preuves, par ordre de préférence : (1) marqueur ``(d)`` la veille et référence
    abaissée du montant ; (2) référence abaissée du montant la veille ; (3) cours
    précédent publié abaissé du montant (``clôture[s-1] - précédent[s]`` ≈ montant,
    séances consécutives) : titre suspendu au détachement dont la BOC n'ajuste le cours
    qu'à la reprise (SLBC : suspendu jusqu'au 11/09/2024 à 83 250, précédent publié
    80 550 = 83 250 - 2 700 le 12/09) ; (4) marqueur ``(d)`` seul ; (5) marqueur ``(V)`` ;
    (6) date de paiement - 2 jours ouvrés, quand l'information paraît bien après le
    paiement. Si cette date estimée tombe dans un trou de BOC manquants, le
    détachement est daté de la **première séance après le trou** (première séance
    où le titre est observé ex-dividende ; la dernière séance avant le trou est encore
    cum-dividende : ONTBF 06/05/2021 publie encore 387,17 du 10-juin-20 et une référence
    égale à la clôture) ; si elle tombe un jour férié, de la séance précédente.
    """
    sess, exact = _session_numbers(g)
    prev = g["prev_close"].to_numpy(float) if "prev_close" in g.columns else np.full(len(g), np.nan)
    anchor = g.at[i, "date"]
    if payment_date is not None and pd.notna(payment_date):
        anchor = min(anchor, payment_date)
    lo_date = anchor - pd.Timedelta(days=30)
    lo = max(1, int(np.searchsorted(g["date"].to_numpy(), np.datetime64(lo_date))))
    hi = min(len(g) - 1, i + 10)
    order = sorted(range(lo, hi + 1), key=lambda s: (abs(s - i), s))

    def ref_drop_ok(s: int) -> bool:
        c, r = g.at[s - 1, "close"], g.at[s - 1, "ref_price"]
        return bool(pd.notna(c) and pd.notna(r) and c > r and 0.6 <= (c - r) / amount <= 1.4)

    for s in order:  # 1) marqueur (d) la veille ET référence abaissée du montant
        if bool(g.at[s - 1, "ex_div"]) and ref_drop_ok(s):
            return s, "ex_div_flag"
    def prev_drop_ok(s: int) -> bool:
        if _has_gap(sess, exact, s - 1, s):  # précédent publié = clôture d'une séance manquante
            return False
        c, p = g.at[s - 1, "close"], prev[s]
        return bool(pd.notna(c) and np.isfinite(p) and c > p > 0 and 0.6 <= (c - p) / amount <= 1.4)

    for s in order:  # 2) référence abaissée du montant la veille
        if ref_drop_ok(s):
            return s, "ref_adjusted"
    for s in order:  # 3) cours précédent publié abaissé du montant
        if prev_drop_ok(s):
            return s, "prev_close_adjusted"
    for s in order:  # 4) marqueur (d) seul
        if bool(g.at[s - 1, "ex_div"]) and abs(s - i) <= 10:
            return s, "ex_div_flag"
    for s in order:  # 5) variation calculée sur la référence ajustée
        if "(V)" in str(g.at[s, "flags"] or "") and abs(s - i) <= 10:
            return s, "variation_vs_ref"
    if payment_date is not None and pd.notna(payment_date) and payment_date < g.at[i, "date"] - pd.Timedelta(days=7):
        # 6) Information publiée bien après le paiement : détachement estimé deux séances
        # ouvrées avant la date de paiement (pratique usuelle à la BRVM).
        target = np.busday_offset(np.datetime64(payment_date.date()), -2, roll="backward")
        days = g["date"].to_numpy("datetime64[D]")
        s = int(np.searchsorted(days, target, side="left"))  # première séance >= cible
        if 1 <= s < len(g) and days[s] != target and not _has_gap(sess, exact, s - 1, s):
            s -= 1  # cible un jour férié : séance précédente
        # Sinon (cible dans un trou de BOC) : première séance après le trou, jamais une
        # séance où le titre est encore cum-dividende.
        if 1 <= s < i:
            return s, "payment_date_estimate"
    return i, "first_seen"


# ---------------------------------------------------------------------------
# Opérations sur titres
# ---------------------------------------------------------------------------

CORPORATE_ACTION_COLUMNS = [
    "symbol", "date", "prev_date", "kind", "ratio", "raw_ratio", "evidence", "confidence",
    "close_before", "close_after", "prev_close_published", "ref_before", "gap_days", "missing_sessions",
]
#: Rapports « fractionnaires » acceptés quand l'ajustement est publié par la BRVM
#: (ex. 3 actions pour 2 = 1,5 ; 8 pour 5 = 1,6, divisions des filiales BOA en 2024).
PUBLISHED_RATIOS: tuple[float, ...] = (1.2, 1.25, 1.5, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0)
#: Kinds utilisés pour ajuster les cours.
ADJUSTING_KINDS = ("split", "reverse_split", "capital_adjustment", "price_reset", "suspension_reset")


def _nearest_ratio(x: float, ratios: Iterable[float] = SIMPLE_RATIOS, integers: bool = False) -> tuple[float, float]:
    """Ratio le plus proche (division k:1 ou regroupement 1:k) et écart absolu en log.

    ``integers=True`` accepte aussi tout entier k >= 2 (et 1/k) : la BRVM publie des
    divisions « exotiques » (1:40 SICABLE 2017, 1:64 TRACTAFRIC 2019).
    """
    cands = [*ratios, *(1.0 / k for k in ratios)]
    if integers and x > 0:
        cands += [float(round(x))] if x >= 1.5 else [1.0 / round(1.0 / x)]
    cands = [c for c in cands if c > 0]
    best = min(cands, key=lambda k: abs(math.log(x / k)))
    return best, abs(math.log(x / best))


#: Marqueurs du BOC signalant une opération sur titres la veille ou le jour même.
_OPERATION_FLAGS = ("VAL-T", "(#)", "EX-D", "EX-C")
#: Au-delà de ce nombre de séances manquantes, une rupture n'est plus interprétable.
MAX_MISSING_SESSIONS = 5


#: Fenêtre (séances) de regroupement des ajustements successifs d'un même titre.
CLUSTER_SESSIONS = 10


def _valuation_close(g: pd.DataFrame, divs: Iterable[tuple[pd.Timestamp, float]] = ()) -> np.ndarray:
    """Cours de valorisation d'un titre (``g`` : une valeur, triée par date, index 0..n-1).

    Égal au cours de clôture du panel, sauf :

    * **titre suspendu** : dernier cours de valorisation avant la suspension. Pendant
      une suspension, la BOC remet parfois la référence à niveau (UNLC 2019-2020 :
      3 500, 2 500, 3 500...) ; ces mouvements ne sont pas des rendements ;
    * **détachement sans cotation** : le jour de détachement d'un dividende ``D`` (et
      les séances non cotées qui suivent tant que la BOC republie le cours cum), si la
      référence du jour est abaissée d'environ ``D`` (``0,5 D <= clôture - réf <= 1,5 D``),
      le titre est valorisé à cette référence ex-dividende (SDCC 25/10/2019 : 2 625 et
      non 2 895). Sinon le dividende serait crédité au cours cum, ce qui crée un faux
      rendement qui ne s'annule qu'à la cotation suivante.
    """
    close = g["close"].to_numpy(float)
    px = close.copy()
    status = g["status"].astype(str).to_numpy() if "status" in g else np.array(["traded"] * len(g))
    ref = g["ref_price"].to_numpy(float) if "ref_price" in g else np.full(len(g), np.nan)
    for t in range(1, len(g)):
        if status[t] == "suspended" and np.isfinite(px[t - 1]) and px[t - 1] > 0:
            px[t] = px[t - 1]
    dates = g["date"].to_numpy("datetime64[ns]")
    for ex, amount in divs:
        t = int(np.searchsorted(dates, np.datetime64(pd.Timestamp(ex))))
        if not (t < len(g) and dates[t] == np.datetime64(pd.Timestamp(ex))) or status[t] == "traded":
            continue
        if status[t] == "suspended" or not (amount > 0 and ref[t] > 0 and close[t] > ref[t]):
            continue
        if not 0.5 <= (close[t] - ref[t]) / amount <= 1.5:
            continue
        cum = close[t]
        k = t
        while k < len(g) and k - t <= CLUSTER_SESSIONS and status[k] != "traded" and close[k] == cum:
            px[k] = ref[k] if 0 < ref[k] < cum else ref[t]
            k += 1
    return px


def _dividend_restatements(g: pd.DataFrame) -> list[tuple[pd.Timestamp, float]]:
    """Dividendes retraités par la BOC (même date, montant / k) : (séance, k).

    Après une division, la BOC exprime le dernier dividende en actions nouvelles
    (SAFC : 576 -> 23,04, k = 25 ; SEMC : 676,8 -> 16,92, k = 40) : k confirme le
    rapport exact de la division.
    """
    out: list[tuple[pd.Timestamp, float]] = []
    amt = g["last_div_net"].to_numpy(float)
    ddt = g["last_div_date"].to_numpy("datetime64[ns]")
    for s in range(1, len(g)):
        if ddt[s] == ddt[s - 1] and not np.isnat(ddt[s]) and amt[s - 1] > 0 and amt[s] > 0:
            k = amt[s - 1] / amt[s]
            if abs(math.log(k)) > math.log(1.15):
                out.append((g.at[s, "date"], float(k)))
    return out


def _confirming_restatement(restated: list[tuple[pd.Timestamp, float]], day: pd.Timestamp,
                            raw: float) -> float | None:
    """Rapport de retraitement du dividende (−30 / +90 jours) compatible avec ``raw`` (±10 %)."""
    for when, k in restated:
        if -30 <= (when - day).days <= 90 and abs(math.log(k / raw)) < math.log(1.10):
            best, err = _nearest_ratio(k, PUBLISHED_RATIOS, integers=True)
            return best if err < math.log(1.01) else k
    return None


def detect_corporate_actions(equities: pd.DataFrame, dividends: pd.DataFrame | None = None) -> pd.DataFrame:
    """Détecte les divisions / regroupements d'actions et autres ajustements de cours.

    Les cours utilisés sont les cours de valorisation (:func:`_valuation_close` :
    suspensions et détachements sans cotation neutralisés). Pour deux séances
    consécutives d'un titre (``t-1``, ``t``), on calcule :

    * ``jump = close[t-1] / close[t]`` : rupture du cours ;
    * ``pub  = close[t-1] / prev_close[t]`` : la BRVM a-t-elle ajusté le cours précédent publié ?
    * ``ref  = close[t-1] / ref_price[s]`` : référence déjà ajustée la veille (``s = t-1``,
      « Val-T »), ou plus tôt depuis la dernière cotation si la séance ``s`` porte un
      marqueur d'opération (SAFC : référence 9 000 les 11-13/10/2017 sous « Val-T » /
      « Ex-d », remise à 22 500 le 16/10, première cotation à 9 675 le 17/10 : rapport 2,5).

    Un événement est candidat si ``jump`` sort de la bande ±7,5 % (+ marge de 2,5
    points), bande élargie quand des séances manquent entre ``t-1`` et ``t``
    (``(1+bande)^(n_manquantes+1)`` ; séances manquantes d'après les numéros de BOC,
    colonne ``session_no``, à défaut d'après les jours ouvrés). Un cours précédent publié aberrant sans rupture du
    cours n'est pas un événement. Une rupture expliquée par un dividende détaché autour
    de ``t`` (``(close[t] + D) / close[t-1]`` dans la bande, ou ajustement publié ≈
    ``close[t-1] - D``) est ignorée.

    Le rapport retenu est l'ajustement publié (``pub`` ou ``ref``, le plus proche d'un
    ratio simple), à défaut la rupture ``jump``. Un retraitement du dernier dividende
    (même date, montant / k) dans les 90 jours confirme et fixe le rapport exact k
    (``evidence`` + ``div_restated``). Classement (``kind``) :

    * ``split`` / ``reverse_split`` : ratio simple (2, 3, 4, 5, 10, 20, 25, 50, 100 ;
      + 1,2, 1,25, 1,5, 1,6, 2,5 et tout entier quand l'ajustement est publié). Une
      simple rupture de cours n'est retenue que pour une division (k >= 2) ;
    * ``capital_adjustment`` : ajustement publié non réductible à un ratio simple mais
      accompagné d'un marqueur d'opération (``Ex-d``, ``Val-T``, ``(#)``) : augmentation
      de capital avec droits, etc. ; ``ratio`` = rapport exact publié ;
    * ``price_reset`` : allers-retours de la référence publiée (ajustements successifs
      à moins de ``CLUSTER_SESSIONS`` séances) ; appliqués tels quels, ce qui laisse les
      rendements continus. Si leur produit n'est pas neutre (SAFC 24/12/2018 -
      07/01/2019 : la BOC alterne 5 300 et 215), il s'agit d'une division unique : le
      premier ajustement dans ce sens devient ``split`` et porte la correction qui
      amène le produit au rapport exact (25 ; SEMC : 40) ;
    * ``suspension_reset`` : rupture inexpliquée à la reprise de cotation d'un titre
      suspendu (référence remise à niveau, admission d'actions nouvelles : UNLC
      17/03/2020) ; neutralisée (``ratio = jump``) car non négociable ;
    * ``data_error`` : pic isolé qui revient le lendemain ;
    * ``unexplained_jump`` : rupture non expliquée (dont trou de plus de
      ``MAX_MISSING_SESSIONS`` séances dans les données) ; non utilisée pour l'ajustement.
    """
    if equities is None or not len(equities):
        return pd.DataFrame(columns=CORPORATE_ACTION_COLUMNS)
    eq = equities.reset_index() if "symbol" not in equities.columns else equities
    log_band = math.log(1 + PRICE_BAND + BAND_MARGIN)
    div_by_sym: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, float]]] = {}
    if dividends is not None and len(dividends):
        for d in dividends.itertuples(index=False):
            div_by_sym.setdefault(d.symbol, []).append((d.ex_date, d.first_seen, float(d.amount)))
    out: list[dict[str, Any]] = []
    for sym, g in eq.sort_values("date").groupby("symbol", sort=True):
        g = g.reset_index(drop=True)
        dates = g["date"].to_numpy("datetime64[D]")
        sess, _ = _session_numbers(g)
        sym_divs = div_by_sym.get(sym, [])
        close = _valuation_close(g, [(ex, a) for ex, _, a in sym_divs])
        prev = g["prev_close"].to_numpy(float)
        ref = g["ref_price"].to_numpy(float)
        flags = g["flags"].fillna("").astype(str).str.upper().to_numpy() if "flags" in g else np.array([""] * len(g))
        status = g["status"].astype(str).to_numpy() if "status" in g else np.array(["traded"] * len(g))
        restated = _dividend_restatements(g) if "last_div_net" in g and "last_div_date" in g else []
        sym_events: list[dict[str, Any]] = []
        for t in range(1, len(g)):
            c0, c1, p1, r0 = close[t - 1], close[t], prev[t], ref[t - 1]
            if not (c0 > 0 and c1 > 0):
                continue
            n_missing = max(0, _missing_between(sess, t - 1, t))
            widen = min(n_missing, MAX_MISSING_SESSIONS)
            band = log_band * (widen + 1)
            jump = c0 / c1
            if abs(math.log(jump)) <= band:
                continue
            pub = c0 / p1 if p1 > 0 else np.nan
            refadj = c0 / r0 if r0 > 0 else np.nan
            # Détachement de dividende autour de t ?
            day = pd.Timestamp(dates[t])
            near = [a for ex, fs, a in sym_divs
                    if abs((ex - day).days) <= 7 or (pd.Timedelta(days=-3) <= day - fs <= pd.Timedelta(days=15))]
            explained = False
            for amt in near:
                if abs(math.log((c1 + amt) / c0)) <= band:
                    explained = True
                if np.isfinite(pub) and c0 > amt and abs(math.log((c0 - amt) / p1)) < math.log(1.03):
                    explained = True
            if explained:
                continue
            # Séances depuis la dernière cotation (incluse) : marqueurs et références ajustées.
            lb = t - 1
            while lb > 0 and status[lb] != "traded" and t - 1 - lb < CLUSTER_SESSIONS:
                lb -= 1
            window = range(lb, t)
            flagged = any(f in flags[s] for s in (*window, t) for f in _OPERATION_FLAGS)
            # Ajustements publiés (hors bande) : le plus proche d'un ratio simple l'emporte.
            # Séances manquantes : l'écart toléré s'élargit, mais seulement si un marqueur
            # d'opération confirme l'événement (sinon une simple remise à niveau de la
            # référence d'un titre suspendu passerait pour une division).
            tol_pub = math.log(1.03) + (log_band * widen if flagged else 0.0)
            estimates = [(pub, "prev_close_adjusted"), (refadj, "ref_adjusted")]
            for s in window:
                if s < t - 1 and ref[s] > 0 and any(f in flags[s] for f in _OPERATION_FLAGS):
                    estimates.append((c0 / ref[s], "ref_adjusted_earlier"))
            published = []
            for est, name in estimates:
                if np.isfinite(est) and abs(math.log(est)) > log_band:
                    k, err = _nearest_ratio(est, PUBLISHED_RATIOS, integers=True)
                    published.append((err, est, name, k))
            if published:
                err, est, evidence, k = min(published)
                tol = tol_pub
            else:
                est, evidence = jump, "price_jump"
                k, err = _nearest_ratio(est, SIMPLE_RATIOS)
                tol = math.log(1 + PRICE_BAND + 0.05)
            if any("VAL-T" in flags[s] for s in (*window, t)):
                evidence += "+val_t"
            elif any("(#)" in flags[s] for s in (*window, t)):
                evidence += "+split_flag"
            # Pic isolé qui revient le lendemain (ou second temps d'un tel pic).
            reverts = t + 1 < len(g) and close[t + 1] > 0 and abs(math.log(c0 / close[t + 1])) <= band
            returns = bool(sym_events) and sym_events[-1]["kind"] == "data_error" \
                and sym_events[-1]["date"] == g.at[t - 1, "date"] and t >= 2 and close[t - 2] > 0 \
                and abs(math.log(close[t - 2] / c1)) <= band
            if evidence.startswith("price_jump") and (reverts or returns):
                kind, ratio, conf = "data_error", np.nan, "low"
            elif n_missing > MAX_MISSING_SESSIONS:
                kind, ratio, conf = "unexplained_jump", np.nan, "low"
                evidence += "+long_gap"
            elif err <= tol and (not evidence.startswith("price_jump") or k >= 2):
                kind, ratio = ("split" if k > 1 else "reverse_split"), k
                conf = "high" if not evidence.startswith("price_jump") else "medium"
            elif published and flagged:
                kind, ratio, conf = "capital_adjustment", est, "medium"
            elif status[t - 1] == "suspended":
                kind, ratio, conf = "suspension_reset", jump, "low"
                evidence += "+suspension"
            else:
                kind, ratio, conf = "unexplained_jump", np.nan, "low"
            if kind in ("split", "reverse_split", "capital_adjustment"):
                k_div = _confirming_restatement(restated, day, est)
                if k_div is not None:
                    ratio, conf = k_div, "high"
                    evidence += "+div_restated"
            sym_events.append({
                "symbol": sym, "date": g.at[t, "date"], "prev_date": g.at[t - 1, "date"],
                "kind": kind, "ratio": ratio, "raw_ratio": est, "evidence": evidence,
                "confidence": conf, "close_before": c0, "close_after": c1,
                "prev_close_published": p1, "ref_before": r0,
                "gap_days": int((g.at[t, "date"] - g.at[t - 1, "date"]).days),
                "missing_sessions": n_missing, "_t": t,
            })
        _resolve_clusters(sym_events, restated)
        out.extend(sym_events)
    df = pd.DataFrame(out, columns=CORPORATE_ACTION_COLUMNS)
    return df


def _resolve_clusters(events: list[dict[str, Any]], restated: list[tuple[pd.Timestamp, float]]) -> None:
    """Ajustements successifs rapprochés (allers-retours de la référence publiée).

    Grappe : ajustements consécutifs séparés d'au plus ``CLUSTER_SESSIONS`` séances.
    Produit des rapports bruts neutre (±5 %) : tous ``price_reset`` (rapports bruts).
    Produit non neutre et proche d'un rapport simple (3 %) ou confirmé par un
    retraitement du dividende : division unique, portée par le premier ajustement de
    même sens, avec la correction qui amène le produit exactement à ce rapport ; les
    autres sont des ``price_reset`` (rapports bruts).
    """
    clusters: list[list[dict[str, Any]]] = []
    for ev in events:
        if ev["kind"] not in ADJUSTING_KINDS or ev["kind"] == "suspension_reset":
            continue
        if clusters and ev["_t"] - clusters[-1][-1]["_t"] <= CLUSTER_SESSIONS:
            clusters[-1].append(ev)
        else:
            clusters.append([ev])
    for cl in clusters:
        if len(cl) < 2:
            continue
        net = math.prod(ev["raw_ratio"] for ev in cl)
        if abs(math.log(net)) < math.log(1.05):
            for ev in cl:
                ev["kind"], ev["ratio"], ev["confidence"] = "price_reset", ev["raw_ratio"], "low"
            continue
        k_div = _confirming_restatement(restated, cl[0]["date"], net)
        k, err = _nearest_ratio(net, PUBLISHED_RATIOS, integers=True)
        tags: tuple[str, ...]
        if k_div is not None:
            k, tags = k_div, ("flip_flop", "div_restated")
        elif err <= math.log(1.03):
            tags = ("flip_flop",)
        else:
            continue  # produit inexpliqué : classements individuels conservés
        lead = next(ev for ev in cl if math.log(ev["raw_ratio"]) * math.log(net) > 0)
        for ev in cl:
            if ev is lead:
                ev["kind"] = "split" if k > 1 else "reverse_split"
                ev["ratio"] = ev["raw_ratio"] * k / net
                ev["confidence"] = "high" if k_div is not None else "medium"
                ev["evidence"] += "".join(f"+{tag}" for tag in tags if tag not in ev["evidence"])
            else:
                ev["kind"], ev["ratio"], ev["confidence"] = "price_reset", ev["raw_ratio"], "low"


# ---------------------------------------------------------------------------
# Cours ajustés et total return
# ---------------------------------------------------------------------------

ADJUSTED_COLUMNS = [
    "date", "symbol", "close", "split_ratio", "split_factor", "adj_close", "dividend",
    "ret", "tr_ret", "tr_index", "adj_close_tr", "missing_sessions",
]


def adjusted_table(
    equities: pd.DataFrame | None = None,
    corporate_actions: pd.DataFrame | None = None,
    dividends: pd.DataFrame | None = None,
    *,
    panel_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Table longue (date, symbol) des cours ajustés et de la série total return.

    Colonnes produites :

    * ``close`` : cours de **valorisation** (:func:`_valuation_close`) : clôture du
      panel, sauf titre suspendu (dernier cours avant la suspension) et jour de
      détachement sans cotation (référence ex-dividende) ;
    * ``split_ratio`` : k le jour où une division k:1 (ou un ajustement publié de
      type ``capital_adjustment``) prend effet, 1 sinon ;
    * ``split_factor`` : produit des ratios des divisions *postérieures* ;
      ``adj_close = close / split_factor`` (le dernier cours est inchangé, les cours
      antérieurs sont ramenés à la base de titres actuelle) ;
    * ``dividend`` : dividende net détaché à la séance (voir :func:`detect_dividends`) ;
    * ``ret`` : rendement de prix ajusté des divisions ``close*k / close[t-1] - 1`` ;
    * ``tr_ret`` : rendement total ``(close + D)*k / close[t-1] - 1`` (dividende net
      réinvesti au cours de clôture du jour de détachement) ;
    * ``tr_index`` : indice total return (base 100 à la première séance du titre) ;
    * ``adj_close_tr`` : cours ajusté divisions + dividendes (égal au dernier cours) ;
    * ``missing_sessions`` : séances sans ligne pour le titre entre la ligne précédente
      et celle-ci (BOC manquants : 32 séances avant le 25/06/2021) ; ``ret`` et
      ``tr_ret`` couvrent alors ``missing_sessions + 1`` séances. Calculé d'après
      ``session_no`` (calendrier des numéros de BOC), à défaut d'après les jours ouvrés.

    Si ``equities`` n'est pas fourni, les tables sont lues dans ``panel_dir``.
    """
    if equities is None:
        if panel_dir is None:
            raise ValueError("fournir equities ou panel_dir")
        equities = _load(panel_dir, "equities")
        if corporate_actions is None and (Path(panel_dir) / "corporate_actions.parquet").exists():
            corporate_actions = _load(panel_dir, "corporate_actions")
        if dividends is None and (Path(panel_dir) / "dividends.parquet").exists():
            dividends = _load(panel_dir, "dividends")
    eq = equities.reset_index() if "symbol" not in equities.columns else equities
    if not len(eq):
        return pd.DataFrame(columns=ADJUSTED_COLUMNS)
    if dividends is None:
        dividends = detect_dividends(eq)
    if corporate_actions is None:
        corporate_actions = detect_corporate_actions(eq, dividends)
    cols = [c for c in ("date", "symbol", "close", "status", "ref_price", "session_no") if c in eq.columns]
    df = eq[cols].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"]).reset_index(drop=True)
    # Cours de valorisation (suspensions et détachements sans cotation, voir _valuation_close).
    divs_by_sym: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    if len(dividends):
        for d in dividends.itertuples(index=False):
            divs_by_sym.setdefault(d.symbol, []).append((d.ex_date, float(d.amount)))
    px = np.empty(len(df))
    missing = np.zeros(len(df), dtype="int64")
    for sym, idx in df.groupby("symbol", sort=False).indices.items():
        g = df.iloc[idx].reset_index(drop=True)
        px[idx] = _valuation_close(g, divs_by_sym.get(sym, []))
        sess, _ = _session_numbers(g)
        missing[idx[1:]] = np.maximum(0, np.diff(sess) - 1).astype("int64")
    df["close"] = px
    df["missing_sessions"] = missing

    adj = corporate_actions[corporate_actions["kind"].isin(ADJUSTING_KINDS)] if len(corporate_actions) else corporate_actions
    split_map = adj.groupby(["symbol", "date"])["ratio"].prod() if len(adj) else pd.Series(dtype=float)
    div_map = dividends.groupby(["symbol", "ex_date"])["amount"].sum() if len(dividends) else pd.Series(dtype=float)
    key = pd.MultiIndex.from_frame(df[["symbol", "date"]])
    df["split_ratio"] = split_map.reindex(key).fillna(1.0).to_numpy() if len(split_map) else 1.0
    df["dividend"] = div_map.reindex(key).fillna(0.0).to_numpy() if len(div_map) else 0.0

    by_sym = df.groupby("symbol", sort=False)
    prev_close = by_sym["close"].shift(1)
    df["ret"] = df["close"] * df["split_ratio"] / prev_close - 1.0
    df["tr_ret"] = (df["close"] + df["dividend"]) * df["split_ratio"] / prev_close - 1.0
    df["tr_index"] = 100.0 * (1.0 + df["tr_ret"].fillna(0.0)).groupby(df["symbol"], sort=False).cumprod()
    # Facteur de division cumulé : produit des ratios des séances postérieures
    # (produit cumulé à rebours, exact pour des ratios entiers).
    df["split_factor"] = df.groupby("symbol", sort=False)["split_ratio"].transform(
        lambda k: k[::-1].cumprod()[::-1].shift(-1, fill_value=1.0))
    df["adj_close"] = df["close"] / df["split_factor"]
    last_close = by_sym["close"].transform("last")
    last_tr = df.groupby("symbol", sort=False)["tr_index"].transform("last")
    df["adj_close_tr"] = last_close * df["tr_index"] / last_tr
    return df[ADJUSTED_COLUMNS].sort_values(["date", "symbol"]).reset_index(drop=True)


def adjusted_prices(
    equities: pd.DataFrame | None = None,
    corporate_actions: pd.DataFrame | None = None,
    dividends: pd.DataFrame | None = None,
    *,
    panel_dir: str | Path | None = None,
    wide: bool = True,
) -> pd.DataFrame:
    """Cours ajustés des divisions (contrat ``docs/ARCHITECTURE.md``).

    * ``wide=True`` (défaut) : DataFrame large (date x symbol) des cours de clôture
      ajustés des divisions / regroupements (``adj_close``) ;
    * ``wide=False`` : table longue complète de :func:`adjusted_table` (cours
      ajustés **et** série total return réinvestissant les dividendes nets).
    """
    table = adjusted_table(equities, corporate_actions, dividends, panel_dir=panel_dir)
    if not wide:
        return table
    return table.pivot(index="date", columns="symbol", values="adj_close").sort_index()


def total_return_index(
    equities: pd.DataFrame | None = None,
    corporate_actions: pd.DataFrame | None = None,
    dividends: pd.DataFrame | None = None,
    *,
    panel_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Indice total return par titre (date x symbol, base 100), dividendes nets réinvestis."""
    table = adjusted_table(equities, corporate_actions, dividends, panel_dir=panel_dir)
    return table.pivot(index="date", columns="symbol", values="tr_index").sort_index()


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - utilitaire en ligne de commande
    """``python -m brvm_alpha.data.store BOC_DIR OUT_DIR [--force]``."""
    import argparse

    ap = argparse.ArgumentParser(description="Construit le panel BRVM à partir des BOC texte.")
    ap.add_argument("boc_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--force", action="store_true", help="ignorer le cache")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print(build_panel(args.boc_dir, args.out_dir, workers=args.workers, force=args.force))


if __name__ == "__main__":  # pragma: no cover
    main()
