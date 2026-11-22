"""Signaux datés tirés des notes : scores par cible, surcouches manuelles bornées, filtres R1-R10.

Contrat : ``docs/ARCHITECTURE.md``, section « Module Notes de l'analyste » (``notes/signals.py``).

Principes
---------
- **Point-in-time strict** : à la date ``asof`` (une date seule désigne la fin de cette
  journée), une note n'est prise en compte que si elle est **connue** (``NoteStore.asof`` :
  saisie, publication et version en vigueur ``<= asof``) **et** négociable
  (``first_tradable_session <= asof``). Une note publiée après la séance n'agit qu'à la
  séance suivante (document 07 §2.3, coupure 09h00 UTC).
- **Score de nouvelles** (document 07 §3.4-6, signal S5 §6.5) :
  ``S(t) = Σ_k s_k · w_k · d_k(t)``, où ``s_k`` est le score de la note (``analyze``, dans
  [−1, 1]), ``w_k`` le poids de propagation (1 pour la cible elle-même) et
  ``d_k(t) = 2^(−Δ_k/h)`` la décroissance, ``Δ_k`` étant le nombre de séances écoulées
  depuis ``first_tradable_session`` (``h`` = demi-vie, 10 séances par défaut). Le
  document 07 écrit ``exp(−Δ/τ)`` avec τ = 10 séances (constante de temps) : c'est une
  demi-vie de ``10·ln 2 ≈ 6,9`` séances ; ``tau=10`` reproduit exactement cette formule.
- **Propagation** (paramètres explicites, :data:`DEFAULT_PROPAGATION`) : une note sur un
  pays ou un secteur se répercute sur les titres concernés avec un poids 0,5, une note sur
  le marché avec 0,25, une note sur un indice sur ses constituants avec 0,25, une note sur
  un thème sur les sociétés exposées (:data:`THEME_EXPOSURE`, document 05 §10.1) avec 0,25.
  Pour une même note, un titre reçoit le **plus grand** des poids applicables (pas de double
  compte). La composition (secteur, compartiment, indice) est celle de la séance
  ``first_tradable_session`` de la note.
- **Cibles d'une note** : les cibles saisies (``targets``) font foi ; à défaut, les cibles
  détectées par l'analyse ; si un symbole est détecté, les cibles plus larges détectées
  (pays, secteur, thème, marché, indice) ne sont que du contexte et ne propagent pas.
- **Surcouches manuelles** (:func:`manual_overlays`) : ``veto`` (note manuelle étiquetée
  « veto », ou filtre R3 / R9 actif), ``tilt`` (``signe(stance) × conviction/5 × 0,5``
  écart-type, borné à ±0,5, valable ``horizon_days`` séances), ``flags`` (R1-R10 actifs,
  durées du document 07 §6.6).

Les notes ne pilotent jamais seules le portefeuille : le poids du score S5 reste nul tant
que l'IC walk-forward n'a pas dépassé 0,05 sur au moins 3 années (document 07 §6.5) ;
:func:`notes_panel` fournit le panel date × symbole pour cette mesure. Aucune sortie n'est
une garantie : ce sont des lectures factuelles, chiffrées, avec leur confiance.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from brvm_alpha.reference import AES_COUNTRIES, country_of

from .model import (
    DEFAULT_HORIZON_DAYS,
    FIXED_HOLIDAYS,
    HISTORICAL_SYMBOLS,
    KNOWN_SYMBOLS,
    RISK_FLAGS,
    Note,
    SessionCalendar,
    asof_utc,
    default_calendar,
    default_panel_dir,
    fold,
    normalize_targets,
    stance_sign,
    target_kind,
    target_label,
    to_day,
    to_utc,
)
from .store import COLUMNS as STORE_COLUMNS
from .store import NoteStore, _to_frame

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

#: Demi-vie par défaut du score de nouvelles, en séances (contrat : ``half_life=10``).
DEFAULT_HALF_LIFE = 10.0
#: Poids de propagation d'une note vers les titres concernés (choix de conception, non
#: validés : à mesurer par l'IC walk-forward avant tout usage pondéré).
DEFAULT_PROPAGATION: dict[str, float] = {
    "country": 0.5,
    "sector": 0.5,
    "market": 0.25,
    "index": 0.25,
    "theme": 0.25,
}
#: En dessous de ce facteur de décroissance, une note est considérée comme éteinte
#: (≈ 100 séances pour une demi-vie de 10).
MIN_DECAY = 1e-3
#: Borne de la surcouche manuelle (en écarts-types du score multifacteur).
TILT_MAX_SD = 0.5
#: Conviction supposée quand l'analyste donne un avis sans conviction.
DEFAULT_CONVICTION = 3

#: Types d'événements qui valent « comptes suivants » (fin de R3, fin anticipée de R9).
ACCOUNTS_EVENTS = frozenset({"RES_ANNUAL", "RES_S1"})
#: Types d'événements qui valent « rapport publié » (fin de R7).
REPORT_EVENTS = frozenset({"RES_ANNUAL", "RES_S1", "ACT_Q1", "ACT_Q3"})

#: Filtres de risque (document 07 §6.6) : durée en séances et actions.
#: ``sessions`` : durée fixe ; ``until`` : événement qui y met fin ; ``fallback`` : durée
#: retenue quand l'événement de fin n'est pas observable (choix de conception, signalé).
RISK_RULES: dict[str, dict[str, Any]] = {
    "R1": {"until": "resumption", "buffer": 5, "block_buys": True, "liquidity_haircut": 0.10,
           "action": "aucun achat ; alerte sur les positions ; décote de liquidité de 10 %",
           "duration": "jusqu'à la reprise de cotation + 5 séances"},
    "R2": {"sessions": 60, "block_buys": True, "governance_penalty": -1.0,
           "action": "aucun nouvel achat ; −1 en gouvernance", "duration": "60 séances"},
    "R3": {"until": "next_accounts", "block_buys": True, "exclude": True, "veto": True,
           "action": "exclusion des achats ; révision manuelle", "duration": "jusqu'aux comptes suivants"},
    "R4": {"sessions": 120, "max_weight_mult": 0.5,
           "action": "poids maximal × 0,5", "duration": "120 séances"},
    "R5": {"until": "ex_date", "fallback": 60, "block_buys": True,
           "action": "aucun achat avant le détachement des droits",
           "duration": "jusqu'au détachement des droits (60 séances à défaut de date)"},
    "R6": {"until": "offer_result", "fallback": 120, "freeze_auto": True,
           "action": "gel des signaux automatiques ; analyse manuelle de la prime",
           "duration": "jusqu'au résultat de l'offre (120 séances à défaut)"},
    "R7": {"until": "next_report", "alert": True, "quality_penalty_red": -0.5,
           "action": "alerte « retard » ; −0,5 en qualité au niveau rouge", "duration": "jusqu'à la publication"},
    "R8": {"sessions": 5, "check_adjustment": True,
           "action": "contrôle du facteur d'ajustement avant tout signal", "duration": "5 séances"},
    "R9": {"sessions": 60, "until": "next_accounts", "block_buys": True, "veto": True, "quality_penalty": -1.0,
           "disable": ("S1", "S4"),
           "action": "aucun achat ; S1 et S4 désactivés ; −1 en qualité",
           "duration": "60 séances (fin anticipée aux comptes suivants)"},
    "R10": {"sessions": 120, "alert": True, "quality_penalty": -0.5, "lookback_days": 120,
            "action": "alerte « alerte sur résultats manquante » ; −0,5 en qualité", "duration": "120 séances"},
}

#: Exposition des thèmes aux sociétés cotées (document 05 §10.1, carte des expositions ;
#: §2.3 pour la BCEAO). Valeurs : symboles, ``SECT:<code>``, ``PAYS:<code>`` ou ``MARCHE``.
#: Un score positif sur un thème est lu comme favorable aux sociétés exposées (le sens
#: économique d'une hausse de prix dépend de la société : à préciser par l'analyste avec
#: une cible explicite quand il compte).
THEME_EXPOSURE: dict[str, tuple[str, ...]] = {
    "CAOUTCHOUC": ("SPHC", "SOGC"),
    "HUILE_PALME": ("PALC", "SOGC"),
    "SUCRE": ("SCRC",),
    "CACAO": ("SDSC", "FTSC", "NTLC"),
    "CAFE": ("NTLC",),
    "PETROLE": ("TTLC", "TTLS", "SHEC", "SMBC"),
    "GAZ": ("CIEC",),
    "ENERGIE": ("CIEC", "SDCC", "SNTS", "ONTBF", "ORAC", "SCRC"),
    "OR": ("BOAM", "BOABF", "CBIBF", "ONTBF"),
    "COTON": ("UNXC",),
    "LOGISTIQUE": ("SDSC",),
    "CLIMAT": ("SPHC", "SOGC", "PALC", "SCRC"),
    "MOBILE_MONEY": ("SNTS", "ORAC", "ONTBF"),
    "TAUX_BCEAO": ("SECT:FIN",),
    "AES": tuple(f"PAYS:{c}" for c in AES_COUNTRIES),
    "INFLATION": ("MARCHE",),
    "CROISSANCE": ("MARCHE",),
    "MONNAIE": ("MARCHE",),
    "FISCALITE": ("MARCHE",),
}

_RELATION = {"country": "pays", "sector": "secteur", "market": "marché", "index": "indice", "theme": "thème"}


# ---------------------------------------------------------------------------
# Mise en forme (copie locale : ce module ne dépend pas de l'import d'analyze)
# ---------------------------------------------------------------------------


def _fr_num(x: float, decimals: int = 2) -> str:
    return f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _fr_signed(x: float, decimals: int = 2) -> str:
    return ("+" if x >= 0 else "−") + _fr_num(abs(x), decimals)


def _fr_date(ts: Any) -> str:
    return pd.Timestamp(ts).strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Calendrier : compteur de séances vectorisé
# ---------------------------------------------------------------------------


def _as_calendar(calendar: Any) -> SessionCalendar:
    if isinstance(calendar, SessionCalendar):
        return calendar
    if calendar is None:
        return default_calendar()
    if isinstance(calendar, pd.DataFrame) and "date" not in calendar.columns and calendar.index.name == "date":
        calendar = calendar.reset_index()
    return SessionCalendar(calendar)


class SessionClock:
    """Compteur de séances : ``count(j)`` = nombre de séances ``<= j``.

    Construit sur le calendrier :class:`~brvm_alpha.notes.model.SessionCalendar` (séances
    connues, prolongées par les jours ouvrés hors fériés fixes dans les lacunes et hors du
    panel). ``between(a, b)`` = nombre de séances dans ``]a, b]``, identique à
    ``SessionCalendar.sessions_between`` mais vectorisé.
    """

    def __init__(self, calendar: Any = None):
        self.calendar = _as_calendar(calendar)
        self._lo: np.datetime64 | None = None
        self._cum: np.ndarray = np.array([], dtype=np.int64)
        self._sess: np.ndarray = np.array([], dtype=bool)

    def _is_session_vec(self, days: np.ndarray) -> np.ndarray:
        cal = self.calendar
        dts = cal.dates
        ts = pd.DatetimeIndex(days)
        open_wd = (ts.dayofweek < 5) & ~pd.Index(list(zip(ts.month, ts.day))).isin(list(FIXED_HOLIDAYS))
        if len(dts) == 0:
            return np.asarray(open_wd)
        unknown = (days < dts[0]) | (days > dts[-1])
        for lo, hi in cal.gaps:
            unknown |= (days > lo) & (days < hi)
        known = np.isin(days, dts)
        return np.where(unknown, np.asarray(open_wd), known)

    def _ensure(self, lo: np.datetime64, hi: np.datetime64) -> None:
        if self._lo is not None and lo >= self._lo and hi < self._lo + len(self._cum):
            return
        cur_lo = self._lo if self._lo is not None else lo
        cur_hi = self._lo + len(self._cum) - 1 if self._lo is not None else hi
        new_lo = min(lo, cur_lo) - np.timedelta64(30, "D")
        new_hi = max(hi, cur_hi) + np.timedelta64(400, "D")
        days = np.arange(new_lo, new_hi + np.timedelta64(1, "D"), dtype="datetime64[D]")
        sess = self._is_session_vec(days)
        self._lo, self._sess, self._cum = new_lo, sess, np.cumsum(sess.astype(np.int64))

    @staticmethod
    def _days(values: Any) -> np.ndarray:
        idx = pd.DatetimeIndex(pd.to_datetime(pd.Index(np.atleast_1d(values))))
        if idx.tz is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        return idx.normalize().values.astype("datetime64[D]")

    def count(self, days: Any) -> np.ndarray:
        """Nombre de séances ``<= j`` pour chaque jour (tableau d'entiers)."""
        d = self._days(days)
        if not len(d):
            return np.array([], dtype=np.int64)
        self._ensure(d.min(), d.max())
        return self._cum[(d - self._lo).astype(np.int64)]

    def between(self, a: Any, b: Any) -> int:
        """Nombre de séances dans ``]a, b]`` (0 si ``b <= a``)."""
        ca, cb = self.count([a, b])
        return int(max(cb - ca, 0))

    def nth_session(self, day: Any, n: int) -> pd.Timestamp:
        """``n``-ième séance après ``day`` (``n >= 1``) ; ``n = 0`` : ``day`` s'il est une séance, sinon la suivante."""
        d = self._days([day])[0]
        self._ensure(d, d + np.timedelta64(int(2 * n + 30), "D"))
        base = self._cum[int((d - self._lo).astype(np.int64))]
        target = base + n if n >= 1 else base + (0 if self._sess[int((d - self._lo).astype(np.int64))] else 1)
        while self._cum[-1] < target:
            self._ensure(d, self._lo + len(self._cum) + np.timedelta64(400, "D"))
        pos = int(np.searchsorted(self._cum, target, side="left"))
        return pd.Timestamp(self._lo + np.timedelta64(pos, "D"))


_CLOCKS: dict[int, tuple[Any, SessionClock]] = {}


def _clock(calendar: Any) -> SessionClock:
    """Compteur mis en cache par objet calendrier (le défaut est partagé)."""
    if isinstance(calendar, SessionClock):
        return calendar
    key = id(calendar)
    hit = _CLOCKS.get(key)
    if hit is not None and hit[0] is calendar:
        return hit[1]
    clk = SessionClock(calendar)
    if len(_CLOCKS) > 16:
        _CLOCKS.clear()
    _CLOCKS[key] = (calendar, clk)
    return clk


def decay_factor(elapsed: Any, half_life: float = DEFAULT_HALF_LIFE, tau: float | None = None) -> np.ndarray:
    """Facteur de décroissance : ``2^(−Δ/h)`` (demi-vie) ou ``exp(−Δ/τ)`` si ``tau`` est donné."""
    e = np.asarray(elapsed, dtype=float)
    if tau is not None:
        if tau <= 0:
            raise ValueError("tau doit être > 0")
        return np.exp(-e / float(tau))
    if half_life is None or half_life <= 0:
        raise ValueError("half_life doit être > 0")
    return np.power(0.5, e / float(half_life))


# ---------------------------------------------------------------------------
# Univers : composition des cibles larges, point-in-time
# ---------------------------------------------------------------------------

_EQ_COLUMNS = ["date", "symbol", "name", "sector", "compartment", "value", "volume", "status", "close"]


@lru_cache(maxsize=2)
def _default_equities_cached(path: str, mtime_ns: int) -> pd.DataFrame:
    df = pd.read_parquet(path)
    cols = [c for c in _EQ_COLUMNS if c in df.columns]
    df = df[cols].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def default_equities() -> pd.DataFrame | None:
    """Colonnes utiles de ``data/panel/equities.parquet`` (lecture mise en cache), ou ``None``."""
    path = default_panel_dir() / "equities.parquet"
    if not path.exists():
        return None
    return _default_equities_cached(str(path), path.stat().st_mtime_ns)


def _equities_long(equities: Any) -> pd.DataFrame | None:
    if equities is None:
        return None
    if isinstance(equities, (str, Path)):
        p = Path(equities)
        p = p / "equities.parquet" if p.is_dir() else p
        return _default_equities_cached(str(p), p.stat().st_mtime_ns)
    if isinstance(equities, Mapping):
        equities = equities.get("equities")
        if equities is None:
            return None
    df = equities
    if "symbol" not in df.columns or "date" not in df.columns:
        df = df.reset_index()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


class Universe:
    """Composition des cibles larges à une date (``equities`` au format long de ``load_equities``).

    Sans panel : univers des symboles connus (``reference``), secteurs de la classification
    2025 (``reference.SECTOR_2025``) et compartiment Prestige 2026 (avis 001-2026).
    """

    PRESTIGE_2026 = frozenset("ECOC NTLC ONTBF ORAC PALC SGBC SIBC SMBC SNTS SPHC TTLC TTLS".split())

    def __init__(self, equities: Any = "default"):
        if isinstance(equities, str) and equities == "default":
            eq = default_equities()
        else:
            eq = _equities_long(equities)
        self.equities = eq
        self._dates = np.array([], dtype="datetime64[ns]")
        self._groups: dict[np.datetime64, np.ndarray] = {}
        if eq is not None and len(eq):
            eq = eq.sort_values(["date", "symbol"]).reset_index(drop=True)
            self.equities = eq
            d = eq["date"].values
            self._dates, starts = np.unique(d, return_index=True)
            ends = np.r_[starts[1:], len(eq)]
            self._bounds = dict(zip(self._dates, zip(starts, ends)))
        self._cache: dict[tuple[str, Any], tuple[list[str], str]] = {}

    def snapshot(self, day: Any) -> pd.DataFrame | None:
        """Lignes de la dernière séance ``<= day`` (``None`` sans panel ou avant le panel)."""
        if self.equities is None or not len(self._dates):
            return None
        d = np.datetime64(pd.Timestamp(to_day(day)), "ns")
        i = int(np.searchsorted(self._dates, d, side="right")) - 1
        if i < 0:
            return None
        a, b = self._bounds[self._dates[i]]
        return self.equities.iloc[a:b]

    def listed(self, day: Any) -> list[str]:
        snap = self.snapshot(day)
        if snap is None:
            return sorted(KNOWN_SYMBOLS - set(HISTORICAL_SYMBOLS))
        return sorted(snap["symbol"].unique())

    def members(self, code: str, day: Any) -> tuple[list[str], str]:
        """Symboles couverts par ``code`` à la date (et la méthode utilisée)."""
        key = (code, pd.Timestamp(to_day(day)))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        out = self._members(code, key[1])
        self._cache[key] = out
        return out

    def _members(self, code: str, day: pd.Timestamp) -> tuple[list[str], str]:
        from brvm_alpha import reference as ref

        kind = target_kind(code)
        if kind == "symbol":
            return [code], "titre"
        listed = self.listed(day)
        if kind == "market":
            return listed, "toutes les actions cotées"
        if kind == "country":
            c = code[5:]
            return [s for s in listed if country_of(s) == c], f"titres du pays {c} (reference.country_of)"
        if kind == "sector":
            sec = code[5:]
            snap = self.snapshot(day)
            if snap is not None and "sector" in snap.columns and (snap["sector"] == sec).any():
                return sorted(snap.loc[snap["sector"] == sec, "symbol"].unique()), "secteur du BOC à la date"
            return [s for s in listed if ref.SECTOR_2025.get(s) == sec], "secteur BRVM 2025 (reference)"
        if kind == "theme":
            th = code[6:]
            out: list[str] = []
            for item in THEME_EXPOSURE.get(th, ()):
                syms = self.members(item, day)[0] if target_kind(item) != "symbol" else [item]
                out.extend(s for s in syms if s in listed and s not in out)
            return sorted(out), "exposition du thème (document 05 §10.1)"
        if kind == "index":
            from . import index_eval  # import tardif (index_eval importe ce module)

            members, method = index_eval.index_constituents(code, day, equities=self.equities, universe=self)
            return list(members), method
        return [], "inconnu"


# ---------------------------------------------------------------------------
# Lecture des notes
# ---------------------------------------------------------------------------


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in STORE_COLUMNS:
        if c not in df.columns:
            df[c] = None
    for c in ("recorded_at", "created_at", "published_at"):
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce", format="mixed")
    df["first_tradable_session"] = pd.to_datetime(df["first_tradable_session"], errors="coerce")
    if getattr(df["first_tradable_session"].dt, "tz", None) is not None:
        df["first_tradable_session"] = df["first_tradable_session"].dt.tz_convert("UTC").dt.tz_localize(None)
    df["first_tradable_session"] = df["first_tradable_session"].dt.normalize()
    df["version"] = pd.to_numeric(df["version"], errors="coerce").fillna(1).astype(int)
    df["status"] = df["status"].fillna("active")
    df["published_precision"] = df["published_precision"].fillna("datetime")
    return df


def _published_effective(df: pd.DataFrame) -> pd.Series:
    pub = df["published_at"]
    end = pub.dt.normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return pub.where(df["published_precision"] != "date", end)


def all_versions(store_or_frame: Any) -> pd.DataFrame:
    """Toutes les versions des notes (``NoteStore``, ``DataFrame`` du journal ou liste de ``Note``)."""
    if isinstance(store_or_frame, NoteStore):
        return _ensure_columns(store_or_frame.frame(all_versions=True))
    if isinstance(store_or_frame, pd.DataFrame):
        return _ensure_columns(store_or_frame)
    if store_or_frame is None:
        return _ensure_columns(_to_frame([]))
    items = list(store_or_frame)
    recs = []
    for n in items:
        if isinstance(n, Note):
            recs.append(n.to_dict())
        elif isinstance(n, Mapping):
            recs.append(Note.from_dict(dict(n)).to_dict())
        else:
            raise TypeError("attendu : NoteStore, DataFrame ou liste de Note")
    return _ensure_columns(_to_frame(recs))


def notes_asof(store_or_frame: Any, asof: Any, strict: bool = True) -> pd.DataFrame:
    """Notes connues et négociables à ``asof`` : ``store.asof`` puis ``first_tradable_session <= asof``.

    Pour un ``DataFrame`` (ou une liste de notes), la règle de ``NoteStore.asof`` est
    reproduite : version en vigueur (dernière écrite avant ``asof`` si ``strict``),
    ``created_at <= asof`` (si ``strict``), publication prudente ``<= asof``, notes actives.
    """
    t = asof_utc(asof)
    if t is None:
        raise ValueError("asof : date vide")
    day = t.tz_localize(None).normalize()
    if isinstance(store_or_frame, NoteStore):
        df = _ensure_columns(store_or_frame.asof(asof, strict=strict))
    else:
        df = _select_in_force(all_versions(store_or_frame), t, strict)
    if not len(df):
        return df
    fts = df["first_tradable_session"]
    return df[fts.notna() & (fts <= day)].reset_index(drop=True)


def _select_in_force(df: pd.DataFrame, t: pd.Timestamp, strict: bool) -> pd.DataFrame:
    if not len(df):
        return df
    rec = df["recorded_at"].fillna(df["created_at"])
    keep = []
    for _, g in df.assign(_rec=rec).groupby("note_id", sort=False):
        g = g.sort_values("version")
        if strict:
            g = g[g["_rec"] <= t]
            if not len(g):
                continue
        keep.append(g.index[-1])
    out = df.loc[keep]
    pub = _published_effective(out)
    mask = pub.notna() & (pub <= t) & (out["status"] != "archived")
    if strict:
        mask &= out["created_at"].notna() & (out["created_at"] <= t)
    return out[mask].reset_index(drop=True)


_ANALYSIS_CACHE: dict[tuple[str, int, str], dict[str, Any]] = {}


def _row_note(row: Mapping[str, Any]) -> Note:
    d = {k: row.get(k) for k in ("note_id", "created_at", "published_at", "first_tradable_session", "author",
                                 "source", "url", "title", "text", "targets", "event_type", "stance", "conviction",
                                 "horizon_days", "tags", "status", "version", "published_precision", "recorded_at")}
    for k in ("conviction", "horizon_days"):
        v = d.get(k)
        if v is not None and isinstance(v, float) and math.isnan(v):
            d[k] = None
    if d.get("horizon_days") is None:
        d["horizon_days"] = DEFAULT_HORIZON_DAYS
    d["targets"] = list(d.get("targets") or [])
    d["tags"] = list(d.get("tags") or [])
    return Note.from_dict(d)


def note_analysis(row: Mapping[str, Any], calendar: Any = None) -> dict[str, Any]:
    """Analyse d'une ligne du journal (celle du journal si elle existe, sinon calculée et mise en cache)."""
    an = row.get("analysis")
    if isinstance(an, dict) and an:
        return an
    key = (str(row.get("note_id")), int(row.get("version") or 1), str(row.get("title") or "")[:80])
    hit = _ANALYSIS_CACHE.get(key)
    if hit is not None:
        return hit
    from .analyze import analyze_note  # import tardif

    res = analyze_note(_row_note(row), sessions=None if calendar is None else _as_calendar(calendar)).to_dict()
    if len(_ANALYSIS_CACHE) > 20000:
        _ANALYSIS_CACHE.clear()
    _ANALYSIS_CACHE[key] = res
    return res


def _finite(x: Any) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def note_score_value(row: Mapping[str, Any], calendar: Any = None) -> tuple[float, dict[str, Any]]:
    """Score ``s_k`` d'une note (dans [−1, 1]) et son analyse."""
    an = note_analysis(row, calendar)
    s = _finite(an.get("score"))
    return (0.0 if s is None else max(-1.0, min(1.0, s))), an


def effective_targets(row: Mapping[str, Any], analysis: Mapping[str, Any] | None = None) -> list[tuple[str, str]]:
    """Cibles retenues pour une note : ``[(code, origine)]``, origine ``"saisie"`` ou ``"détectée"``.

    Les cibles saisies font foi. À défaut, cibles détectées ; si un symbole est détecté,
    les cibles plus larges détectées ne sont que du contexte (elles ne propagent pas).
    """
    manual = normalize_targets(list(row.get("targets") or []))
    if manual:
        return [(t, "saisie") for t in manual]
    an = analysis if analysis is not None else (row.get("analysis") or {})
    detected = normalize_targets(list((an or {}).get("targets") or row.get("all_targets") or []))
    if any(target_kind(t) == "symbol" for t in detected):
        detected = [t for t in detected if target_kind(t) == "symbol"]
    return [(t, "détectée") for t in detected]


def _target_weights(
    targets: list[tuple[str, str]],
    day: pd.Timestamp,
    universe: Universe,
    propagation: Mapping[str, float],
) -> dict[str, tuple[float, str, str]]:
    """Poids par cible atteinte : ``{cible: (poids, cible source, relation)}`` (poids maximal)."""
    out: dict[str, tuple[float, str, str]] = {}
    for code, _origin in targets:
        cur = out.get(code)
        if cur is None or cur[0] < 1.0:
            out[code] = (1.0, code, "directe")
    for code, _origin in targets:
        kind = target_kind(code)
        if kind == "symbol":
            continue
        w = float(propagation.get(kind, 0.0))
        if w <= 0:
            continue
        syms, _method = universe.members(code, day)
        for s in syms:
            cur = out.get(s)
            if cur is None or w > cur[0]:
                out[s] = (w, code, _RELATION.get(kind, kind))
    return out


# ---------------------------------------------------------------------------
# Scores datés
# ---------------------------------------------------------------------------

CONTRIBUTION_COLUMNS = [
    "target", "kind", "note_id", "version", "source_target", "relation", "weight", "first_tradable_session",
    "sessions_elapsed", "decay", "note_score", "contribution", "author", "source", "event_type", "title",
    "materiality", "confidence", "risk_flags", "stance", "conviction",
]


def note_contributions(
    store_or_frame: Any,
    asof: Any,
    half_life: float = DEFAULT_HALF_LIFE,
    calendar: Any = None,
    propagation: Mapping[str, float] | None = None,
    equities: Any = "default",
    strict: bool = True,
    tau: float | None = None,
    min_decay: float = MIN_DECAY,
    universe: Universe | None = None,
) -> pd.DataFrame:
    """Contributions élémentaires ``s_k · w_k · d_k(asof)`` : une ligne par (cible atteinte, note).

    Voir :func:`note_scores` pour les paramètres. ``relation`` vaut ``directe`` pour la cible
    de la note elle-même, sinon ``pays``, ``secteur``, ``marché``, ``indice`` ou ``thème``.
    """
    prop = dict(DEFAULT_PROPAGATION if propagation is None else propagation)
    t = asof_utc(asof)
    if t is None:
        raise ValueError("asof : date vide")
    day = t.tz_localize(None).normalize()
    df = notes_asof(store_or_frame, asof, strict=strict)
    if not len(df):
        return pd.DataFrame(columns=CONTRIBUTION_COLUMNS)
    clock = _clock(calendar)
    uni = universe if universe is not None else Universe(equities)
    elapsed = clock.count(day)[0] - clock.count(df["first_tradable_session"].values)
    dec = decay_factor(np.maximum(elapsed, 0), half_life, tau)
    rows: list[dict[str, Any]] = []
    for (_, r), e, d in zip(df.iterrows(), elapsed, dec):
        if d < min_decay:
            continue
        row = r.to_dict()
        s, an = note_score_value(row, calendar)
        tg = effective_targets(row, an)
        if not tg:
            continue
        fts = pd.Timestamp(row["first_tradable_session"])
        for target, (w, src, rel) in _target_weights(tg, fts, uni, prop).items():
            rows.append({
                "target": target, "kind": target_kind(target), "note_id": row["note_id"], "version": int(row["version"]),
                "source_target": src, "relation": rel, "weight": w, "first_tradable_session": fts,
                "sessions_elapsed": int(max(e, 0)), "decay": float(d), "note_score": s,
                "contribution": s * w * float(d), "author": row.get("author"), "source": row.get("source"),
                "event_type": row.get("event_type") or an.get("event_type"), "title": row.get("title") or "",
                "materiality": _finite(an.get("materiality")), "confidence": _finite(an.get("confidence")),
                "risk_flags": list(an.get("risk_flags") or []), "stance": row.get("stance"),
                "conviction": _finite(row.get("conviction")),
            })
    out = pd.DataFrame(rows, columns=CONTRIBUTION_COLUMNS)
    return out


SCORE_COLUMNS = [
    "kind", "label", "score", "score_direct", "score_propagated", "score_manual", "score_auto", "n_notes",
    "n_direct", "n_propagated", "n_manual", "n_auto", "mean_confidence", "last_session", "last_note_id",
    "last_title", "last_event_type",
]


def note_scores(
    store_or_frame: Any,
    asof: Any,
    half_life: float = DEFAULT_HALF_LIFE,
    calendar: Any = None,
    propagation: Mapping[str, float] | None = None,
    equities: Any = "default",
    strict: bool = True,
    tau: float | None = None,
    min_decay: float = MIN_DECAY,
    propagate: bool = True,
) -> pd.DataFrame:
    """Score de nouvelles par cible à la date ``asof`` : ``Σ s_k · w_k · 2^(−Δ_k/h)``.

    - ``store_or_frame`` : ``NoteStore``, ``DataFrame`` du journal (``store.frame``,
      ``store.asof``…) ou liste de ``Note`` ;
    - ``asof`` : date (fin de journée) ou instant UTC ; seules les notes connues à cet
      instant et négociables (``first_tradable_session <= asof``) comptent ;
    - ``half_life`` : demi-vie en séances (``tau`` : constante de temps du document 07,
      ``exp(−Δ/τ)``, prioritaire si donnée) ; ``calendar`` : calendrier des séances
      (``load_sessions``, liste de dates, ``SessionCalendar``) ; défaut : panel du dépôt ;
    - ``propagation`` : poids par nature de cible (:data:`DEFAULT_PROPAGATION`) ;
      ``propagate=False`` : cibles directes seulement ;
    - ``equities`` : panel long (``load_equities``) pour la composition des secteurs,
      compartiments et indices ; ``"default"`` : panel du dépôt ; ``None`` : référence ;
    - ``strict`` : voir ``NoteStore.asof``.

    Une ligne par cible (index ``target``) : ``score`` (total), ``score_direct`` (notes sur
    la cible elle-même), ``score_propagated``, ``score_manual`` / ``score_auto`` (auteur),
    ``n_notes``…, ``last_session`` (séance négociable de la note la plus récente),
    ``last_note_id``, ``last_title``, ``last_event_type``. Trié par ``|score|`` décroissant.
    """
    con = note_contributions(store_or_frame, asof, half_life=half_life, calendar=calendar, propagation=propagation,
                             equities=equities, strict=strict, tau=tau, min_decay=min_decay)
    if not propagate and len(con):
        con = con[con["relation"] == "directe"]
    return aggregate_contributions(con)


def aggregate_contributions(con: pd.DataFrame) -> pd.DataFrame:
    """Agrège des contributions (:func:`note_contributions`) en une ligne par cible."""
    if con is None or not len(con):
        out = pd.DataFrame(columns=SCORE_COLUMNS)
        out.index.name = "target"
        return out
    rows = []
    for target, g in con.groupby("target", sort=False):
        direct = g["relation"] == "directe"
        manual = g["author"] == "analyste"
        last = g.sort_values(["first_tradable_session", "note_id"]).iloc[-1]
        conf = pd.to_numeric(g["confidence"], errors="coerce")
        rows.append({
            "target": target, "kind": target_kind(target), "label": target_label(target),
            "score": float(g["contribution"].sum()),
            "score_direct": float(g.loc[direct, "contribution"].sum()),
            "score_propagated": float(g.loc[~direct, "contribution"].sum()),
            "score_manual": float(g.loc[manual, "contribution"].sum()),
            "score_auto": float(g.loc[~manual, "contribution"].sum()),
            "n_notes": int(g["note_id"].nunique()), "n_direct": int(g.loc[direct, "note_id"].nunique()),
            "n_propagated": int(g.loc[~direct, "note_id"].nunique()),
            "n_manual": int(g.loc[manual, "note_id"].nunique()), "n_auto": int(g.loc[~manual, "note_id"].nunique()),
            "mean_confidence": float(conf.mean()) if conf.notna().any() else np.nan,
            "last_session": last["first_tradable_session"], "last_note_id": last["note_id"],
            "last_title": last["title"], "last_event_type": last["event_type"],
        })
    out = pd.DataFrame(rows).set_index("target")
    out = out.reindex(out["score"].abs().sort_values(ascending=False, kind="stable").index)
    return out[SCORE_COLUMNS]


def notes_panel(
    store: Any,
    calendar: Any,
    symbols: Iterable[str] | None,
    half_life: float = DEFAULT_HALF_LIFE,
    propagation: Mapping[str, float] | None = None,
    equities: Any = "default",
    strict: bool = True,
    tau: float | None = None,
    min_decay: float = MIN_DECAY,
    targets: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Panel date × symbole du score de nouvelles, point-in-time (IC walk-forward, S5).

    ``calendar`` : dates des lignes (``load_sessions`` : séances avec date ; liste de dates ;
    ``SessionCalendar``) et calendrier de comptage des séances. Chaque valeur est égale à
    ``note_scores(store, t, ...)["score"]`` pour le symbole à la date ``t`` : version en
    vigueur à ``t``, note connue à ``t``, ``first_tradable_session <= t`` (aucune information
    postérieure). ``symbols=None`` : tous les symboles atteints ; ``targets`` : codes non
    symboles à ajouter en colonnes (``IDX:BRVM-30``, ``PAYS:CI``…). 0 en l'absence de note.
    """
    prop = dict(DEFAULT_PROPAGATION if propagation is None else propagation)
    cal = _as_calendar(calendar)
    if isinstance(calendar, SessionCalendar):
        dates = pd.DatetimeIndex(pd.to_datetime(cal.dates))
    elif isinstance(calendar, pd.DataFrame):
        col = calendar["date"] if "date" in calendar.columns else calendar.index.to_series()
        dates = pd.DatetimeIndex(pd.to_datetime(col.dropna()).dt.normalize().unique()).sort_values()
    else:
        dates = pd.DatetimeIndex(pd.to_datetime(pd.Index(list(calendar))).dropna().normalize().unique()).sort_values()
    clock = _clock(cal)
    cols = list(dict.fromkeys(list(symbols or []) + list(targets or [])))
    df = all_versions(store)
    out = pd.DataFrame(0.0, index=dates, columns=cols)
    out.index.name = "date"
    if not len(df) or not len(dates):
        return out
    uni = Universe(equities)
    c_dates = clock.count(dates.values)
    day_ns = dates.values.astype("datetime64[D]")
    acc: dict[str, np.ndarray] = {c: np.zeros(len(dates)) for c in cols}
    rec_all = df["recorded_at"].fillna(df["created_at"])
    pub_eff = _published_effective(df)
    df = df.assign(_rec=rec_all, _pub=pub_eff)
    max_len = None
    if tau is None:
        max_len = int(math.ceil(half_life * math.log2(1.0 / min_decay))) + 1
    else:
        max_len = int(math.ceil(tau * math.log(1.0 / min_decay))) + 1

    def _day(ts: Any) -> np.datetime64 | None:
        if ts is None or pd.isna(ts):
            return None
        return np.datetime64(pd.Timestamp(ts).tz_convert("UTC").tz_localize(None).normalize(), "D") \
            if pd.Timestamp(ts).tzinfo is not None else np.datetime64(pd.Timestamp(ts).normalize(), "D")

    for _nid, g in df.groupby("note_id", sort=False):
        g = g.sort_values("version")
        recs = list(g["_rec"]) if strict else [None] * len(g)
        rows = list(g.iterrows())
        if not strict:
            rows = rows[-1:]
            recs = [None]
        for i, (_, r) in enumerate(rows):
            if r["status"] == "archived":
                continue
            fts = r["first_tradable_session"]
            if fts is None or pd.isna(fts):
                continue
            starts = [np.datetime64(pd.Timestamp(fts), "D")]
            if strict:
                for v in (_day(r["created_at"]), _day(recs[i])):
                    if v is None:
                        starts = []
                        break
                    starts.append(v)
                if not starts:
                    continue
            pd_ = _day(r["_pub"])
            if pd_ is None:
                continue
            starts.append(pd_)
            start = max(starts)
            end = None
            if strict and i + 1 < len(rows):
                end = _day(recs[i + 1])
            lo = int(np.searchsorted(day_ns, start, side="left"))
            hi = len(dates) if end is None else int(np.searchsorted(day_ns, end, side="left"))
            if hi <= lo:
                continue
            row = r.to_dict()
            s, an = note_score_value(row, cal)
            if s == 0.0:
                continue
            tg = effective_targets(row, an)
            if not tg:
                continue
            weights = _target_weights(tg, pd.Timestamp(fts), uni, prop)
            wanted = {c: w for c, (w, _src, _rel) in weights.items()
                      if (c in acc) or (symbols is None and target_kind(c) == "symbol")}
            if not wanted:
                continue
            c_fts = clock.count([fts])[0]
            el = c_dates[lo:hi] - c_fts
            keep = el <= max_len
            if not keep.any():
                continue
            dec = decay_factor(np.maximum(el, 0), half_life, tau)
            dec = np.where(keep & (dec >= min_decay), dec, 0.0)
            for c, w in wanted.items():
                if c not in acc:
                    acc[c] = np.zeros(len(dates))
                acc[c][lo:hi] += s * w * dec
    out = pd.DataFrame(acc, index=dates)
    out.index.name = "date"
    if symbols is None:
        out = out[sorted(out.columns)]
    return out


# ---------------------------------------------------------------------------
# Surcouches manuelles et filtres de risque
# ---------------------------------------------------------------------------


def _is_veto(row: Mapping[str, Any]) -> bool:
    tags = [fold(str(t)) for t in (row.get("tags") or [])]
    return row.get("author") == "analyste" and any(t == "veto" or t.startswith("veto:") for t in tags)


def _fold_title(row: Mapping[str, Any]) -> str:
    return fold(str(row.get("title") or ""))


def _r7_level(fts: pd.Timestamp, day: pd.Timestamp) -> tuple[str, pd.Timestamp]:
    """Niveau R7 (orange / rouge) d'après les dates limites BRVM (document 07 §5.2, §6.6).

    Note publiée de mai à octobre : comptes annuels et T1 (date limite 30/04, rouge le 30/06) ;
    de novembre à avril : S1 et T3 (31/10, rouge le 31/12). Choix de conception signalé.
    """
    y = fts.year
    if 5 <= fts.month <= 10:
        red = pd.Timestamp(year=y, month=6, day=30)
    elif fts.month >= 11:
        red = pd.Timestamp(year=y, month=12, day=31)
    else:
        red = pd.Timestamp(year=y - 1, month=12, day=31)
    return ("rouge" if day >= red else "orange"), red


def _panel_resumption(uni: Universe, symbol: str, since: pd.Timestamp, day: pd.Timestamp) -> pd.Timestamp | None:
    """Première séance non suspendue après une série de mentions SP observée depuis ``since``."""
    eq = uni.equities
    if eq is None or "status" not in eq.columns:
        return None
    g = eq[(eq["symbol"] == symbol) & (eq["date"] >= since) & (eq["date"] <= day)].sort_values("date")
    if not len(g):
        return None
    st = g["status"].astype(str).to_numpy()
    sp = np.flatnonzero(st == "suspended")
    if not len(sp):
        return None
    after = np.flatnonzero(st[sp[0]:] != "suspended")
    if not len(after):
        return None
    return pd.Timestamp(g["date"].iloc[sp[0] + after[0]])


def manual_overlays(
    store: Any,
    asof: Any,
    calendar: Any = None,
    equities: Any = "default",
    propagation: Mapping[str, float] | None = None,
    strict: bool = True,
    tilt_max: float = TILT_MAX_SD,
    use_panel_status: bool = True,
) -> dict[str, Any]:
    """Surcouches de l'analyste et filtres de risque actifs à la date ``asof``.

    Renvoie un dictionnaire :

    - ``veto`` : ``{symbole: [motifs]}`` — note manuelle étiquetée « veto » (valable
      ``horizon_days`` séances après sa séance négociable, sauf archivage ; une cible large
      s'étend à ses titres) ou filtre R3 / R9 actif ;
    - ``tilt`` : ``pd.Series`` symbole -> ajustement en écarts-types, somme des
      ``signe(stance) × conviction/5 × 0,5`` des notes manuelles en vigueur (pondérée par la
      propagation pour une cible large), bornée à ``±tilt_max`` ; ``tilt_targets`` : idem
      par cible saisie ;
    - ``flags`` : ``{symbole: [ {code, label, since, until, remaining_sessions, note_id,
      title, action, ...} ]}`` — R1-R10 actifs (durées du document 07 §6.6) ;
    - ``block_buys`` (R1, R2, R3, R5, R9 et veto), ``max_weight_mult`` (R4 : 0,5),
      ``freeze_auto`` (R6), ``quality_penalty`` (R7 rouge −0,5, R9 −1, R10 −0,5),
      ``governance_penalty`` (R2 −1), ``disabled_signals`` (R9 : S1, S4) ;
    - ``table`` : une ligne par surcouche active ; ``reasons`` : phrases en français.
    """
    prop = dict(DEFAULT_PROPAGATION if propagation is None else propagation)
    t = asof_utc(asof)
    if t is None:
        raise ValueError("asof : date vide")
    day = t.tz_localize(None).normalize()
    df = notes_asof(store, asof, strict=strict)
    clock = _clock(calendar)
    uni = Universe(equities)
    rows: list[dict[str, Any]] = []
    tilt_t: dict[str, float] = {}
    tilt_s: dict[str, float] = {}
    tilt_src: dict[str, list[str]] = {}

    if len(df):
        df = df.sort_values(["first_tradable_session", "published_at", "note_id"]).reset_index(drop=True)
        analyses = [note_analysis(r.to_dict(), calendar) for _, r in df.iterrows()]
        df = df.assign(_an=analyses)
        df["_et"] = [r.get("event_type") or a.get("event_type") for r, a in zip(df.to_dict("records"), analyses)]
        sym_targets = []
        for _, r in df.iterrows():
            tg = effective_targets(r.to_dict(), r["_an"])
            sym_targets.append([c for c, _ in tg if target_kind(c) == "symbol"])
        df["_syms"] = sym_targets
        df["_ft"] = [_fold_title(r) for r in df.to_dict("records")]
    c_day = clock.count(day)[0]

    def later_events(sym: str, after: pd.Timestamp, types: frozenset[str], title_rx: str | None = None) -> pd.Timestamp | None:
        if not len(df):
            return None
        m = (df["first_tradable_session"] > after) & df["_et"].isin(types) & df["_syms"].apply(lambda xs: sym in xs)
        if title_rx is not None:
            m &= df["_ft"].str.contains(title_rx, regex=True)
        sub = df[m]
        return None if not len(sub) else pd.Timestamp(sub["first_tradable_session"].min())

    for _, r in (df.iterrows() if len(df) else []):
        row = r.to_dict()
        an = row["_an"]
        fts = pd.Timestamp(row["first_tradable_session"])
        elapsed = int(c_day - clock.count([fts])[0])
        nid = row["note_id"]
        title = row.get("title") or ""
        base = {"note_id": nid, "title": title, "since": fts, "first_tradable_session": fts,
                "author": row.get("author"), "event_type": row.get("_et")}

        # 1) Veto manuel.
        horizon = int(_finite(row.get("horizon_days")) or DEFAULT_HORIZON_DAYS)
        tg = effective_targets(row, an)
        if _is_veto(row) and elapsed < horizon:
            until = clock.nth_session(fts, horizon - 1) if horizon > 1 else fts
            for code, _o in tg:
                syms, _m = uni.members(code, fts)
                for s in syms:
                    rows.append({**base, "symbol": s, "kind": "veto", "code": "VETO", "until": until,
                                 "remaining_sessions": horizon - 1 - elapsed, "source_target": code,
                                 "action": "exclusion manuelle (veto de l'analyste)"})

        # 2) Surcouche manuelle bornée (tilt).
        sgn = stance_sign(row.get("stance"))
        if row.get("author") == "analyste" and sgn != 0 and elapsed < horizon:
            conv = _finite(row.get("conviction")) or DEFAULT_CONVICTION
            val = sgn * conv / 5.0 * tilt_max
            for code, _o in tg:
                tilt_t[code] = tilt_t.get(code, 0.0) + val
            for s, (w, src, _rel) in _target_weights(tg, fts, uni, prop).items():
                if target_kind(s) != "symbol":
                    continue
                tilt_s[s] = tilt_s.get(s, 0.0) + val * w
                tilt_src.setdefault(s, []).append(nid)

        # 3) Filtres de risque (titres seulement).
        flags = list(an.get("risk_flags") or [])
        ex = an.get("extracted") or {}
        r10_unconfirmed = False
        if "R10" not in flags and ex.get("r10_candidate") and row["_syms"]:
            pub = pd.Timestamp(row["published_at"])
            sym0 = row["_syms"][0]
            prior = df[(df["_et"] == "PROFIT_WARNING") & df["_syms"].apply(lambda xs: sym0 in xs)
                       & (df["published_at"] < pub) & (df["published_at"] >= pub - pd.Timedelta(days=120))]
            if not len(prior):
                flags.append("R10")
                r10_unconfirmed = True
        for code in flags:
            rule = RISK_RULES.get(code)
            if rule is None:
                continue
            for s in row["_syms"]:
                until: pd.Timestamp | None = None
                remaining: int | None = None
                active = True
                extra: dict[str, Any] = {}
                if code == "R1":
                    res = later_events(s, fts, frozenset({"RESUMPTION"}))
                    if use_panel_status:
                        pr = _panel_resumption(uni, s, fts, day)
                        if pr is not None and (res is None or pr < res):
                            res = pr
                    if res is not None:
                        until = clock.nth_session(res, int(rule["buffer"]))
                        extra["resumption"] = res
                        active = day <= until
                elif code in ("R3", "R7"):
                    types = ACCOUNTS_EVENTS if code == "R3" else REPORT_EVENTS
                    nxt = later_events(s, fts, types)
                    if nxt is not None and nxt <= day:
                        active = False
                    if code == "R7":
                        level, red = _r7_level(fts, day)
                        extra.update({"level": level, "red_from": red})
                elif code == "R5":
                    exd = to_day(ex.get("ex_date")) if ex.get("ex_date") is not None else None
                    if exd is not None and exd > fts:
                        until = exd - pd.Timedelta(days=1)
                        active = day < exd
                        extra["rights_ex_date"] = exd
                    else:
                        n = int(rule["fallback"])
                        active = elapsed < n
                        until = clock.nth_session(fts, n - 1)
                        remaining = n - 1 - elapsed
                        extra["fallback"] = True
                elif code == "R6":
                    res = later_events(s, fts, frozenset({"TAKEOVER", "OPV_IPO"}), r"resultat|cloture|bilan")
                    if res is not None and res <= day:
                        active = False
                    else:
                        n = int(rule["fallback"])
                        active = elapsed < n
                        until = clock.nth_session(fts, n - 1)
                        remaining = n - 1 - elapsed
                        extra["fallback"] = True
                else:
                    n = int(rule["sessions"])
                    active = elapsed < n
                    until = clock.nth_session(fts, n - 1) if n > 1 else fts
                    remaining = n - 1 - elapsed
                    if code == "R9":
                        nxt = later_events(s, fts, ACCOUNTS_EVENTS)
                        if nxt is not None and nxt <= day:
                            active = False
                            extra["ended_by_accounts"] = nxt
                    if code == "R10" and r10_unconfirmed:
                        extra["confirmed"] = False
                if not active:
                    continue
                if remaining is None and until is not None:
                    remaining = max(int(clock.between(day, until)), 0)
                rows.append({**base, "symbol": s, "kind": "flag", "code": code, "until": until,
                             "remaining_sessions": remaining, "source_target": s, "action": rule["action"],
                             "label": RISK_FLAGS.get(code, code), **extra})

    table = pd.DataFrame(rows)
    if len(table):
        table = table.sort_values(["symbol", "code", "since"]).reset_index(drop=True)
    veto: dict[str, list[str]] = {}
    flags_out: dict[str, list[dict[str, Any]]] = {}
    block: set[str] = set()
    mwm: dict[str, float] = {}
    freeze: set[str] = set()
    qpen: dict[str, float] = {}
    gpen: dict[str, float] = {}
    disabled: dict[str, set[str]] = {}
    reasons: list[str] = []
    for rec in table.to_dict("records") if len(table) else []:
        s = rec["symbol"]
        code = rec["code"]
        short = rec["note_id"][:10]
        until_txt = f"jusqu'au {_fr_date(rec['until'])}" if rec.get("until") is not None and not pd.isna(rec.get("until")) else \
            RISK_RULES.get(code, {}).get("duration", "durée ouverte")
        if code == "VETO":
            veto.setdefault(s, []).append(f"veto manuel (note {short} du {_fr_date(rec['since'])}, {until_txt})")
            block.add(s)
            reasons.append(f"{s} : veto manuel de l'analyste depuis le {_fr_date(rec['since'])}, {until_txt} "
                           f"(note {short} « {rec['title'][:60]} »).")
            continue
        rule = RISK_RULES[code]
        info = {k: rec.get(k) for k in ("code", "label", "since", "until", "remaining_sessions", "note_id", "title",
                                        "action", "level", "resumption", "confirmed", "fallback", "rights_ex_date")
                if k in rec and not (isinstance(rec.get(k), float) and math.isnan(rec.get(k)))}
        flags_out.setdefault(s, []).append(info)
        if rule.get("veto"):
            veto.setdefault(s, []).append(f"{code} actif depuis le {_fr_date(rec['since'])} (note {short})")
        if rule.get("block_buys"):
            block.add(s)
        if rule.get("max_weight_mult"):
            mwm[s] = min(mwm.get(s, 1.0), float(rule["max_weight_mult"]))
        if rule.get("freeze_auto"):
            freeze.add(s)
        pen = rule.get("quality_penalty")
        if code == "R7" and rec.get("level") == "rouge":
            pen = rule.get("quality_penalty_red")
        if pen:
            qpen[s] = min(qpen.get(s, 0.0), float(pen))
        if rule.get("governance_penalty"):
            gpen[s] = min(gpen.get(s, 0.0), float(rule["governance_penalty"]))
        for sig in rule.get("disable", ()):
            disabled.setdefault(s, set()).add(sig)
        rem = rec.get("remaining_sessions")
        rem_txt = f", encore {int(rem)} séance(s)" if rem is not None and not pd.isna(rem) and rem >= 0 else ""
        extra = ""
        if code == "R10" and rec.get("confirmed") is False:
            extra = " (aucune alerte sur résultats dans le journal des 120 jours précédents : à vérifier)"
        if code == "R7" and rec.get("level"):
            extra = f" (niveau {rec['level']})"
        reasons.append(f"{s} : {code} depuis le {_fr_date(rec['since'])}, {until_txt}{rem_txt} — {rule['action']}{extra}.")

    tilt = pd.Series({s: float(np.clip(v, -tilt_max, tilt_max)) for s, v in tilt_s.items()}, dtype=float, name="tilt")
    tilt_targets = pd.Series({c: float(np.clip(v, -tilt_max, tilt_max)) for c, v in tilt_t.items()}, dtype=float,
                             name="tilt")
    for s, v in tilt.items():
        if v != 0:
            reasons.append(f"{s} : surcouche manuelle {_fr_signed(v)} écart-type (borne ±{_fr_num(tilt_max, 1)} ; "
                           f"{len(tilt_src.get(s, []))} note(s) de l'analyste).")
    return {
        "asof": day,
        "veto": veto,
        "tilt": tilt.sort_index(),
        "tilt_targets": tilt_targets.sort_index(),
        "flags": flags_out,
        "block_buys": sorted(block),
        "max_weight_mult": mwm,
        "freeze_auto": sorted(freeze),
        "quality_penalty": qpen,
        "governance_penalty": gpen,
        "disabled_signals": {k: sorted(v) for k, v in disabled.items()},
        "table": table,
        "reasons": reasons,
    }


__all__ = [
    "DEFAULT_HALF_LIFE", "DEFAULT_PROPAGATION", "RISK_RULES", "THEME_EXPOSURE", "TILT_MAX_SD", "SessionClock",
    "Universe", "decay_factor", "note_contributions", "note_scores", "aggregate_contributions", "notes_panel",
    "manual_overlays", "notes_asof", "effective_targets", "all_versions",
]
