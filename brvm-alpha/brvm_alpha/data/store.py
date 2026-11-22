"""Magasin de données BRVM : panel multi-séances construit à partir des BOC.

Fonctions principales
---------------------
* :func:`build_panel` : analyse (en parallèle) tous les BOC d'un répertoire et écrit
  ``equities.parquet``, ``indices.parquet``, ``market.parquet``,
  ``order_book.parquet``, ``corporate_actions.parquet``, ``dividends.parquet``,
  ``adjusted_prices.parquet`` et ``parse_report.csv``. Le traitement est
  **incrémental** : un cache (``_cache/``) mémorise le résultat de chaque fichier
  (clé : nom, taille, date de modification, version du parseur) ; seuls les
  fichiers nouveaux ou modifiés sont réanalysés.
* :func:`load_equities`, :func:`load_indices` (+ ``load_market``,
  ``load_order_book``, ``load_corporate_actions``) : lecture avec un index propre
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
    "parser_version",
    "total_return_index",
]

#: Codes d'avertissement purement informatifs (réparation réussie, cas normal rare).
INFO_WARNING_CODES = frozenset({"wrapped_digits_joined", "first_listing", "lang_en", "change_vs_adjusted_ref",
                                "untraded_ref_change"})

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

    def __str__(self) -> str:  # pragma: no cover - affichage
        top = "\n".join(f"    {n:6d}  {c}" for c, n in self.top_warnings)
        return (
            f"Fichiers : {self.n_files} (analysés {self.n_parsed}, cache {self.n_cached}, erreurs {self.n_errors})\n"
            f"Séances  : {self.n_sessions} du {self.first_date:%Y-%m-%d} au {self.last_date:%Y-%m-%d}\n"
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
    equities = _finalize_equities(cached["equities"], excluded)
    indices = _finalize_simple(cached["indices"], excluded, ["date", "index"], INDEX_COLUMNS)
    market = _finalize_simple(cached["market"], excluded, ["date"], None)
    order_book = _finalize_simple(cached["order_book"], excluded, ["date", "symbol"], ORDER_BOOK_COLUMNS)
    dividends = detect_dividends(equities)
    corporate = detect_corporate_actions(equities, dividends)
    adjusted = adjusted_table(equities, corporate, dividends)

    _write_parquet(equities, out_dir / "equities.parquet")
    _write_parquet(indices, out_dir / "indices.parquet")
    _write_parquet(market, out_dir / "market.parquet")
    _write_parquet(order_book, out_dir / "order_book.parquet")
    _write_parquet(dividends, out_dir / "dividends.parquet")
    _write_parquet(corporate, out_dir / "corporate_actions.parquet")
    _write_parquet(adjusted, out_dir / "adjusted_prices.parquet")

    report = manifest.drop(columns=["size", "mtime", "version"], errors="ignore").copy()
    report["excluded"] = report["file"].map(excluded).fillna("")
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


def load_corporate_actions(panel_dir: str | Path) -> pd.DataFrame:
    """Événements sur titres détectés (divisions, regroupements, ruptures inexpliquées)."""
    return _load(panel_dir, "corporate_actions")


# ---------------------------------------------------------------------------
# Dividendes
# ---------------------------------------------------------------------------

DIVIDEND_COLUMNS = ["symbol", "ex_date", "amount", "payment_date", "first_seen", "evidence", "close_before", "yield_pct"]


def detect_dividends(equities: pd.DataFrame) -> pd.DataFrame:
    """Nouveaux dividendes : la date du « dernier dividende payé » change.

    Un dividende est *nouveau* quand ``last_div_date`` devient postérieure à toutes
    les dates déjà vues pour le titre (une date qui « revient en arrière » est une
    coquille). Une correction de date à montant identique dans les 60 jours suivant
    un dividende détecté est fusionnée avec lui. Les montants retraités après une
    division (même date, montant / k) ne sont pas de nouveaux dividendes.

    Date de détachement (``ex_date``), par ordre de préférence (voir
    :func:`_find_ex_date` pour la fenêtre de recherche) :

    1. séance suivant un marqueur ``(d)`` (ex-dividende) dont le cours de référence
       est abaissé d'environ le dividende (``clôture - réf`` ≈ montant) ;
    2. séance suivant une telle baisse de la référence, sans marqueur ;
    3. séance suivant un marqueur ``(d)`` seul ;
    4. séance marquée ``(V)`` (variation calculée sur la référence ajustée) ;
    5. à défaut, la première séance où le nouveau dividende apparaît.
    """
    if equities is None or not len(equities):
        return pd.DataFrame(columns=DIVIDEND_COLUMNS)
    eq = equities.reset_index() if "symbol" not in equities.columns else equities
    out: list[dict[str, Any]] = []
    for sym, g in eq.sort_values("date").groupby("symbol", sort=True):
        g = g.reset_index(drop=True)
        dates = g["date"].to_numpy()
        seen_max: pd.Timestamp | None = None
        last_event: dict[str, Any] | None = None
        for i, row in enumerate(g.itertuples(index=False)):
            ddate = row.last_div_date
            if pd.isna(ddate):
                continue
            if seen_max is None:
                seen_max = ddate  # dividende déjà connu au début de l'historique
                continue
            if ddate <= seen_max:
                continue
            seen_max = ddate
            amount = row.last_div_net
            if amount is None or not np.isfinite(amount) or amount <= 0:
                continue
            if (last_event is not None and abs(last_event["amount"] - amount) < 1e-6
                    and (row.date - last_event["first_seen"]).days <= 60):
                last_event["payment_date"] = ddate  # simple correction de la date
                continue
            ex_i, evidence = _find_ex_date(g, i, amount, ddate)
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


def _find_ex_date(g: pd.DataFrame, i: int, amount: float, payment_date: pd.Timestamp | None = None) -> tuple[int, str]:
    """Indice de la séance de détachement du dividende apparu à la ligne ``i``.

    Fenêtre de recherche : de 30 jours avant ``min(première apparition, date de
    paiement)`` à 10 séances après la première apparition (la BRVM met parfois à
    jour la colonne « dernier dividende » plusieurs semaines après le détachement).
    """
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
    for s in order:  # 2) référence abaissée du montant la veille
        if ref_drop_ok(s):
            return s, "ref_adjusted"
    for s in order:  # 3) marqueur (d) seul
        if bool(g.at[s - 1, "ex_div"]) and abs(s - i) <= 10:
            return s, "ex_div_flag"
    for s in order:  # 4) variation calculée sur la référence ajustée
        if "(V)" in str(g.at[s, "flags"] or "") and abs(s - i) <= 10:
            return s, "variation_vs_ref"
    if payment_date is not None and pd.notna(payment_date) and payment_date < g.at[i, "date"] - pd.Timedelta(days=7):
        # Information publiée bien après le paiement : détachement estimé deux séances
        # ouvrées avant la date de paiement (pratique usuelle à la BRVM).
        target = np.datetime64(pd.Timestamp(np.busday_offset(np.datetime64(payment_date.date()), -2, roll="backward")))
        s = int(np.searchsorted(g["date"].to_numpy(), target, side="right")) - 1
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
ADJUSTING_KINDS = ("split", "reverse_split", "capital_adjustment")


def _nearest_ratio(x: float, ratios: Iterable[float] = SIMPLE_RATIOS) -> tuple[float, float]:
    """Ratio le plus proche (division k:1 ou regroupement 1:k) et écart absolu en log."""
    cands = [*ratios, *(1.0 / k for k in ratios)]
    best = min(cands, key=lambda k: abs(math.log(x / k)))
    return best, abs(math.log(x / best))


def detect_corporate_actions(equities: pd.DataFrame, dividends: pd.DataFrame | None = None) -> pd.DataFrame:
    """Détecte les divisions / regroupements d'actions et autres ajustements de cours.

    Pour deux séances consécutives d'un titre (``t-1``, ``t``), on calcule :

    * ``pub  = close[t-1] / prev_close[t]`` : la BRVM a-t-elle ajusté le cours précédent publié ?
    * ``jump = close[t-1] / close[t]`` : rupture du cours ;
    * ``ref  = close[t-1] / ref_price[t-1]`` : référence de la veille déjà ajustée (« Val-T »).

    Un événement est candidat si ``pub`` ou ``jump`` sort de la bande ±7,5 % (+ marge
    de 2,5 points), bande élargie quand des séances manquent entre ``t-1`` et ``t``
    (``(1+bande)^(n_manquantes+1)``). Une rupture expliquée par un dividende détaché
    autour de ``t`` (``(close[t] + D) / close[t-1]`` dans la bande, ou ajustement
    publié ≈ ``close[t-1] - D``) est ignorée. Une référence aberrante isolée (sans
    rupture du cours ni ajustement publié) n'est pas un événement.

    Classement (``kind``) :

    * ``split`` / ``reverse_split`` : rapport arrondi au ratio simple le plus proche
      (2, 3, 4, 5, 10, 20, 25, 50, 100, 1,5 et leurs inverses ; + 1,2, 1,25, 1,6, 2,5
      quand l'ajustement est publié par la BRVM) ;
    * ``capital_adjustment`` : ajustement publié par la BRVM mais non réductible à un
      ratio simple (ex. augmentation de capital avec droits, « Ex-d ») ; ``ratio`` =
      rapport exact publié ;
    * ``data_error`` : pic isolé qui revient le lendemain ;
    * ``unexplained_jump`` : rupture non expliquée (non utilisée pour l'ajustement).
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
        close = g["close"].to_numpy(float)
        prev = g["prev_close"].to_numpy(float)
        ref = g["ref_price"].to_numpy(float)
        flags = g["flags"].fillna("").astype(str).to_numpy()
        sym_divs = div_by_sym.get(sym, [])
        for t in range(1, len(g)):
            c0, c1, p1, r0 = close[t - 1], close[t], prev[t], ref[t - 1]
            if not (c0 > 0 and c1 > 0):
                continue
            n_missing = max(0, int(np.busday_count(dates[t - 1] + np.timedelta64(1, "D"), dates[t])))
            band = log_band * (min(n_missing, 5) + 1)
            pub = c0 / p1 if p1 > 0 else np.nan
            refadj = c0 / r0 if r0 > 0 else np.nan
            jump = c0 / c1
            pub_out = np.isfinite(pub) and abs(math.log(pub)) > log_band * (1 if n_missing == 0 else min(n_missing, 5) + 1)
            jump_out = abs(math.log(jump)) > band
            if not (pub_out or jump_out):
                continue
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
            if pub_out:
                est, evidence, tol, ratios = pub, "prev_close_adjusted", math.log(1.03), PUBLISHED_RATIOS
            elif np.isfinite(refadj) and abs(math.log(refadj)) > log_band and abs(math.log(refadj / jump)) < log_band:
                est, evidence, tol, ratios = refadj, "ref_adjusted", math.log(1.03), PUBLISHED_RATIOS
            else:
                est, evidence, tol, ratios = jump, "price_jump", math.log(1 + PRICE_BAND + 0.05), SIMPLE_RATIOS
            if "VAL-T" in flags[t - 1].upper() or "VAL-T" in flags[t].upper():
                evidence += "+val_t"
            k, err = _nearest_ratio(est, ratios)
            # Pic isolé qui revient le lendemain : erreur de donnée, pas une opération.
            reverts = t + 1 < len(g) and close[t + 1] > 0 and abs(math.log(c0 / close[t + 1])) <= band
            # ... ou second temps d'un tel pic (retour au niveau de l'avant-veille).
            returns = bool(out) and out[-1]["symbol"] == sym and out[-1]["kind"] == "data_error" \
                and out[-1]["date"] == g.at[t - 1, "date"] and t >= 2 and close[t - 2] > 0 \
                and abs(math.log(close[t - 2] / c1)) <= band
            if evidence == "price_jump" and (reverts or returns):
                kind, ratio, conf = "data_error", np.nan, "low"
            elif err <= tol:
                kind, ratio = ("split" if k > 1 else "reverse_split"), k
                conf = "high" if evidence != "price_jump" else "medium"
            elif evidence != "price_jump":
                kind, ratio, conf = "capital_adjustment", est, "medium"
            else:
                kind, ratio, conf = "unexplained_jump", np.nan, "low"
            out.append({
                "symbol": sym, "date": g.at[t, "date"], "prev_date": g.at[t - 1, "date"],
                "kind": kind, "ratio": ratio, "raw_ratio": est, "evidence": evidence,
                "confidence": conf, "close_before": c0, "close_after": c1,
                "prev_close_published": p1, "ref_before": r0,
                "gap_days": int((g.at[t, "date"] - g.at[t - 1, "date"]).days),
                "missing_sessions": n_missing,
            })
    return pd.DataFrame(out, columns=CORPORATE_ACTION_COLUMNS)


# ---------------------------------------------------------------------------
# Cours ajustés et total return
# ---------------------------------------------------------------------------

ADJUSTED_COLUMNS = [
    "date", "symbol", "close", "split_ratio", "split_factor", "adj_close", "dividend",
    "ret", "tr_ret", "tr_index", "adj_close_tr",
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
    * ``adj_close_tr`` : cours ajusté divisions + dividendes (égal au dernier cours).

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
    df = eq[["date", "symbol", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"]).reset_index(drop=True)

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
