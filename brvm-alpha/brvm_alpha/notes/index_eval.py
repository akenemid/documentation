"""Évaluation des indices BRVM : position SURPONDÉRER / NEUTRE / SOUS-PONDÉRER, chiffrée et datée.

Contrat : ``docs/ARCHITECTURE.md``, section « Module Notes de l'analyste » (``notes/index_eval.py``).

Pour chaque indice disponible à la date ``asof`` (dernière observation au plus 14 jours
avant), :func:`evaluate_indices` calcule, **uniquement avec des données datées ``<= asof``** :

- niveau, rendements 1/3/6/12 mois (mois civils : niveau à la dernière séance ``<= t − k
  mois``) et depuis le 31/12 (``ytd_pct`` officiel du BOC) ; rendement relatif au Composite ;
- volatilité annualisée sur 63 rendements quotidiens (``× √252`` ; les rendements qui
  couvrent plus de 6 jours civils, BOC manquants, sont écartés) ; repli courant depuis le
  plus haut de 12 mois et repli maximal sur 12 mois ;
- régime : :func:`brvm_alpha.quant.regime.market_regime` (moyenne 200 séances, pente 20
  séances, volatilité 21 séances et son percentile, krach > 15 % en 63 séances) ;
- valorisation : marché (Composite, Composite TR) : ``avg_per`` et ``avg_yield_pct`` du BOC ;
  autres indices : PER médian (0 < PER ≤ 100) et rendement net médian (0 ≤ r < 30 %) des
  constituants ; percentile et z-score robuste (médiane, 1,4826 × MAD) sur ``history_years``
  ans ; PER publié de l'indice (BOC) en information ;
- largeur : part des constituants au-dessus de leur moyenne 50 et 200 séances (cours ajustés
  des divisions), rapport hausses / baisses sur 20 séances (BOC pour le marché, constituants
  sinon), chacun comparé à son propre historique (z-score robuste) ;
- saison des dividendes : détachements attendus dans les ``window_days`` jours d'après
  l'historique (``dividends.parquet`` : date anniversaire médiane des 3 derniers
  détachements) et annoncés (notes ``DIV_NOTICE`` avec date ex), rendement net attendu
  pondéré par la capitalisation : c'est la **baisse mécanique** attendue d'un indice de prix
  au détachement (sans effet sur l'indice Total Return) ;
- notes : :func:`brvm_alpha.notes.signals.note_contributions` sur l'indice (et ses alias :
  ``MARCHE`` pour le Composite, ``SECT:X`` pour l'indice sectoriel X) + moyenne des scores des
  constituants pondérée par la valeur échangée sur 6 mois (hors propagation de l'indice
  lui-même, pour ne pas compter deux fois la même note). La composante n'est disponible que
  si au moins une note a une contribution non nulle : des notes de score nul ne diluent pas
  les autres composantes.

**Score composite** : moyenne pondérée explicite de z-scores bornés à ±3
(:data:`COMPONENT_WEIGHTS` : tendance 0,30, valorisation 0,25, largeur 0,15, régime 0,15,
notes 0,15 ; une composante sans donnée est retirée et les poids sont renormalisés) :

- tendance = moyenne des z du rendement 3 mois, du rendement 12 mois et de l'écart à la
  moyenne 200 séances, chacun contre son historique ;
- valorisation = moyenne de ``−z(PER)`` et de ``z(rendement)`` (positif = bon marché) ;
- largeur = moyenne des z (part > MM50, part > MM200, log hausses/baisses 20 séances) ;
- régime = +1 haussier, 0 neutre, −1 baissier, −2 stress ;
- notes = score des notes / 0,5 (une note récente de score 0,5 vaut z = 1), borné.

``stance`` : SURPONDÉRER si composite > +0,5, SOUS-PONDÉRER si < −0,5, NEUTRE sinon.
``confidence`` = qualité des données × (0,3 + 0,4 × accord + 0,3 × marge), bornée à
[0,05 ; 0,95] : accord des composantes avec la position (pondéré par ``w·|z|`` ; pour NEUTRE,
équilibre des composantes), marge du score au seuil le plus proche (pleine à 0,5), qualité
des données (racine de la couverture des poids, profondeur d'historique, × 0,85 si la
composition est approchée, × 0,9 si la série est chaînée ou reconstituée, × 0,8 sous 3
titres). ``reasons`` : phrases françaises chiffrées.

Composition des indices (:func:`index_constituents`) : Composite et Composite TR = toutes
les actions cotées ; Prestige / Principal = colonne ``compartment`` (depuis le 02/01/2023) ;
indices sectoriels = colonne ``sector`` du BOC (codes base 2025 depuis le 02/01/2025 ; pour
un indice base 1999 après cette date, la classification du dernier BOC qui la portait) ;
BRVM 30 = composition officielle (avis 289-2026 pour le T4-2026, T3-2026 reconstitué à partir
des entrées et sorties de cet avis, ou note ``INDEX_CHANGE`` du journal portant la liste),
sinon **approximation documentée** : les 30 titres au meilleur rang moyen (valeur + volume
échangés) sur le trimestre civil précédent, règle officielle « les plus échangées sur un
trimestre » (28/30 titres retrouvés pour les compositions officielles T3 et T4 2026, contre
24 à 26/30 avec la seule valeur échangée sur 6 mois, option ``brvm30_method="valeur_6m"``).

**Deux instants** (voir ``signals.NotesMoment``) : toutes les données de marché sont datées
``<= asof`` (date des cours). Les notes suivent, par défaut, la règle stricte à cette date (mode
historique, aucune anticipation). Avec ``notes_known_at=<instant UTC>`` (mode direct, passé par
la ligne de commande, l'interface et le rapport quand la date est le dernier BOC), la composante
« notes », les dividendes annoncés, le calendrier et les filtres des constituants utilisent les
notes connues à cet instant, appliquées à la séance qui suit le dernier BOC ; les cours, eux, ne
changent pas.

Ces lectures sont factuelles et **ne sont pas des garanties** : les poids et seuils sont des
choix de conception, non validés hors échantillon ; la composante « notes » relève du signal
S5, dont le poids dans le modèle multifacteur reste nul tant que l'IC walk-forward n'a pas
dépassé 0,05 (document 07 §6.5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from brvm_alpha import reference as ref

from .model import (
    SECTOR_INDEX_NAMES,
    default_panel_dir,
    index_names,
    normalize_target,
    target_kind,
    target_label,
    to_day,
)
from . import signals as sg

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

#: Poids explicites des composantes du score composite (choix de conception, non validés).
COMPONENT_WEIGHTS: dict[str, float] = {
    "tendance": 0.30,
    "valorisation": 0.25,
    "largeur": 0.15,
    "regime": 0.15,
    "notes": 0.15,
}
STANCE_UP = 0.5
STANCE_DOWN = -0.5
STANCES = ("SURPONDÉRER", "NEUTRE", "SOUS-PONDÉRER")
Z_CLIP = 3.0
HISTORY_YEARS = 5
MIN_HISTORY = 60
NOTES_SCALE = 0.5
REGIME_SCORE = {"haussier": 1.0, "neutre": 0.0, "baissier": -1.0, "stress": -2.0}
DIV_WINDOW_DAYS = 60
STALE_DAYS = 14
MAX_RETURN_GAP_DAYS = 6
PER_BOUNDS = (0.0, 100.0)
YIELD_BOUNDS = (0.0, 30.0)
LIQUIDITY_MONTHS = 6
#: Plafond de poids par titre (document 01 §10.2 : Prestige plafonné à environ 20 %,
#: règle reconstituée, non publiée ; les autres indices ne sont pas plafonnés).
WEIGHT_CAPS: dict[str, float] = {"IDX:PRESTIGE": 0.20}

#: Ordre d'affichage des indices.
INDEX_CODES: tuple[str, ...] = (
    "IDX:BRVM-C", "IDX:BRVM-C-TR", "IDX:BRVM-30", "IDX:PRESTIGE", "IDX:PRINCIPAL", "IDX:BRVM-10",
    *(f"IDX:SECT:{c}" for c in SECTOR_INDEX_NAMES),
)
MARKET_CODES = frozenset({"IDX:BRVM-C", "IDX:BRVM-C-TR"})
COMPOSITE_NAME = "BRVM COMPOSITE"
TR_NAME = "BRVM COMPOSITE TOTAL RETURN"
#: Base de l'indice Composite Total Return officiel (avis 308-2025).
TR_BASE = ("2025-01-02", 100.0)

#: Compositions officielles du BRVM 30 : (date d'effet, symboles, source). Chaque composition
#: vaut un trimestre civil (révision le 1er jour ouvré de janvier, avril, juillet, octobre).
BRVM30_T4_2026 = (
    "SDSC BOABF BOAB BOAC BOAM BOAN BOAS BICB CFAC CIEC CBIBF ECOC ETIT SIVC LNBB NSBC ONTBF ORGT "
    "ORAC SAFC SPHC STBC SGBC SIBC SOGC SLBC SNTS TTLC UNXC SHEC"
).split()
_T4_IN = {"LNBB", "ONTBF", "SHEC", "SLBC"}
_T4_OUT = {"NEIC", "SCRC", "SEMC", "STAC"}
BRVM30_T3_2026 = sorted((set(BRVM30_T4_2026) - _T4_IN) | _T4_OUT)
BRVM30_COMPOSITIONS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("2026-07-01", tuple(BRVM30_T3_2026),
     "T3-2026 reconstituée : composition T4-2026 sans ses entrées (LNBB, ONTBF, SHEC, SLBC) et avec ses sorties "
     "(NEIC, SCRC, SEMC, STAC), avis 289-2026"),
    ("2026-10-01", tuple(BRVM30_T4_2026), "officielle T4-2026, avis 289-2026 du 01/10/2026 (document 01 §10.4)"),
)
#: Première séance des indices (BOC) : BRVM 30, Prestige, Principal le 02/01/2023 ; BRVM 10
#: jusqu'au 30/12/2022.
INDEX_LIFE: dict[str, tuple[str | None, str | None]] = {
    "IDX:BRVM-30": ("2023-01-02", None),
    "IDX:PRESTIGE": ("2023-01-02", None),
    "IDX:PRINCIPAL": ("2023-01-02", None),
    "IDX:BRVM-10": (None, "2022-12-30"),
}

# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------


def _num(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _signed(x: float, d: int = 2) -> str:
    return ("+" if x >= 0 else "−") + _num(abs(x), d)


def _pct(x: float | None, d: int = 1, signed: bool = True) -> str:
    if x is None or not np.isfinite(x):
        return "n.d."
    return (_signed(100 * x, d) if signed else _num(100 * x, d)) + " %"


def _date(ts: Any) -> str:
    return pd.Timestamp(ts).strftime("%d/%m/%Y")


def _fin(x: Any) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _z_txt(z: float | None) -> str:
    return "n.d." if z is None or not np.isfinite(z) else _signed(z, 2)


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

_PANEL_FILES = ("equities", "indices", "market", "dividends", "adjusted_prices", "corporate_actions", "sessions")


@lru_cache(maxsize=2)
def _load_panels_cached(path: str, stamp: tuple[int, ...]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    root = Path(path)
    for name in _PANEL_FILES:
        p = root / f"{name}.parquet"
        if p.exists():
            out["adjusted" if name == "adjusted_prices" else name] = pd.read_parquet(p)
    return out


def load_panels(panel_dir: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Tables longues du panel (``equities``, ``indices``, ``market``, ``dividends``,
    ``adjusted``, ``corporate_actions``, ``sessions``), lecture mise en cache."""
    root = Path(panel_dir) if panel_dir is not None else default_panel_dir()
    stamp = tuple((root / f"{n}.parquet").stat().st_mtime_ns if (root / f"{n}.parquet").exists() else 0
                  for n in _PANEL_FILES)
    if not any(stamp):
        raise FileNotFoundError(f"aucun panel dans {root}")
    return _load_panels_cached(str(root.resolve()), stamp)


def _long(df: pd.DataFrame | None, keys: tuple[str, ...] = ("date",)) -> pd.DataFrame | None:
    if df is None:
        return None
    if not all(k in df.columns for k in keys):
        df = df.reset_index()
    df = df.copy()
    for k in ("date", "ex_date", "first_seen", "payment_date"):
        if k in df.columns:
            df[k] = pd.to_datetime(df[k])
    return df


def _resolve_panels(panels: Any) -> dict[str, pd.DataFrame]:
    if panels is None:
        return dict(load_panels())
    if isinstance(panels, (str, Path)):
        return dict(load_panels(panels))
    if not isinstance(panels, Mapping):
        raise TypeError("panels : dictionnaire de tables longues, chemin du panel ou None")
    out = dict(panels)
    if "adjusted_prices" in out and "adjusted" not in out:
        out["adjusted"] = out["adjusted_prices"]
    return out


def truncate_panels(panels: Any, asof: Any) -> dict[str, pd.DataFrame]:
    """Copie des tables datées tronquées à ``asof`` (dividendes : ``ex_date <= asof``).

    ``corporate_actions`` et ``sessions`` ne sont pas tronqués : ils ne servent qu'à
    reconstituer le nombre de titres à chaque date passée et le calendrier.
    """
    P = _resolve_panels(panels)
    day = to_day(asof)
    out: dict[str, pd.DataFrame] = {}
    for k, v in P.items():
        if v is None:
            continue
        if k in ("corporate_actions", "sessions"):
            out[k] = v
            continue
        df = _long(v, ("ex_date",) if k == "dividends" else ("date",))
        col = "ex_date" if k == "dividends" else "date"
        out[k] = df[df[col] <= day].reset_index(drop=True) if col in df.columns else df
    return out


class _Ctx:
    """Données tronquées à ``asof`` et panels larges (date × symbole)."""

    def __init__(self, panels: Any, asof: Any, store: Any = None, calendar: Any = None,
                 notes_known_at: Any = None):
        P = _resolve_panels(panels)
        eq = _long(P.get("equities"), ("date", "symbol"))
        ix = _long(P.get("indices"), ("date", "index"))
        if eq is None or ix is None:
            raise ValueError("panels : 'equities' et 'indices' sont nécessaires")
        mk = _long(P.get("market"))
        last = max(eq["date"].max(), ix["date"].max())
        if asof is None:
            day = pd.Timestamp(last).normalize()
        else:
            day = to_day(asof)
        self.asof = day
        self.eq = eq[eq["date"] <= day].sort_values(["date", "symbol"]).reset_index(drop=True)
        self.ix = ix[ix["date"] <= day].reset_index(drop=True)
        self.mk = None if mk is None else mk[mk["date"] <= day].set_index("date").sort_index()
        dv = _long(P.get("dividends"), ("ex_date",))
        self.dv = None if dv is None else dv[dv["ex_date"] <= day].reset_index(drop=True)
        self.ca = P.get("corporate_actions")
        adj = _long(P.get("adjusted"), ("date", "symbol"))
        self.adj = None if adj is None else adj[adj["date"] <= day]
        if calendar is None and P.get("sessions") is not None:
            calendar = P["sessions"].reset_index() if "date" not in P["sessions"].columns else P["sessions"]
        self.calendar = calendar
        self.store = store
        if not len(self.eq):
            raise ValueError(f"aucune donnée d'actions avant le {_date(day)}")
        self.date = pd.Timestamp(self.eq["date"].max())
        # Deux instants : date des cours (self.date) et instant de connaissance des notes. Mode
        # direct si ``notes_known_at`` est donné (notes appliquées à la séance qui suit le dernier
        # BOC) ; sinon mode historique (règle stricte à ``asof``, comportement inchangé).
        k = sg.knowledge_instant(notes_known_at)
        self.notes_moment = sg.notes_moment(self.date if k is not None else day, k, self.calendar)
        self.notes_direct = self.notes_moment.direct

        def wide(df: pd.DataFrame, col: str, idx: str = "symbol") -> pd.DataFrame:
            return df.pivot_table(index="date", columns=idx, values=col, aggfunc="last").sort_index()

        self.close = wide(self.eq, "close")
        if self.adj is not None and len(self.adj):
            self.close_adj = wide(self.adj, "adj_close").reindex(index=self.close.index)
            self.ret = wide(self.adj, "ret").reindex(index=self.close.index)
            self.tr_idx = wide(self.adj, "tr_index").reindex(index=self.close.index)
        else:
            self.close_adj = self.close
            self.ret = self.close.pct_change(fill_method=None)
            self.tr_idx = None
        self.value = wide(self.eq, "value").fillna(0.0)
        self.volume = wide(self.eq, "volume").fillna(0.0)
        self.per = wide(self.eq, "per") if "per" in self.eq.columns else None
        self.yld = wide(self.eq, "net_yield_pct") if "net_yield_pct" in self.eq.columns else None
        self.status = self.eq.pivot_table(index="date", columns="symbol", values="status", aggfunc="last")
        self.levels = wide(self.ix, "level", "index")
        self.ytd = wide(self.ix, "ytd_pct", "index") if "ytd_pct" in self.ix.columns else None
        self.ix_per = wide(self.ix, "per", "index") if "per" in self.ix.columns else None
        self.universe = sg.Universe(self.eq)
        self._series: dict[str, tuple[pd.Series, dict[str, Any]]] = {}
        self._shares: pd.Series | None = None

    # -- notes ----------------------------------------------------------------
    def notes_frame(self, t: Any) -> pd.DataFrame:
        """Notes en vigueur : mode direct (connues à l'instant de connaissance) ou strict à ``t``."""
        if self.notes_direct:
            return sg.notes_asof(self.store, self.date, calendar=self.calendar, known_at=self.notes_moment)
        return sg.notes_asof(self.store, t)

    # -- capitalisation ------------------------------------------------------
    def shares_at(self, day: pd.Timestamp | None = None) -> pd.Series:
        """Nombre de titres par symbole à une date (avis 303-2026 propagé par les divisions)."""
        from brvm_alpha.data.store import shares_outstanding_panel

        d = self.date if day is None else pd.Timestamp(day)
        if day is None and self._shares is not None:
            return self._shares
        snap = self.eq[self.eq["date"] == self.eq.loc[self.eq["date"] <= d, "date"].max()]
        ca = self.ca if self.ca is not None else pd.DataFrame(columns=["symbol", "date", "kind", "ratio", "confidence"])
        try:
            n = shares_outstanding_panel(equities=snap[["date", "symbol"]], corporate_actions=ca, listed_only=False)
            out = n.iloc[-1] if len(n) else pd.Series(dtype=float)
        except Exception:  # pragma: no cover - référence absente
            out = pd.Series({s: ref.shares_outstanding(s, d) for s in snap["symbol"]}, dtype=float)
        out = out.astype(float)
        if day is None:
            self._shares = out
        return out

    def cap_weights(self, members: Iterable[str], day: pd.Timestamp | None = None, cap: float | None = None) -> pd.Series:
        """Poids en capitalisation totale (nombre de titres × cours), plafonnés à ``cap`` si donné."""
        d = self.date if day is None else pd.Timestamp(day)
        members = list(members)
        sh = self.shares_at(d).reindex(members)
        px = self.close.loc[:d].iloc[-1].reindex(members) if len(self.close.loc[:d]) else pd.Series(np.nan, index=members)
        cap_v = (sh * px).where(lambda x: x > 0)
        if cap_v.notna().sum() == 0:
            return pd.Series(1.0 / max(len(members), 1), index=members)
        w = (cap_v / cap_v.sum()).fillna(0.0)
        return _cap(w, cap) if cap else w


# ---------------------------------------------------------------------------
# Composition des indices
# ---------------------------------------------------------------------------


def _cap(w: pd.Series, limit: float, max_iter: int = 50) -> pd.Series:
    """Plafonnement itératif des poids à ``limit`` (excédent redistribué au prorata)."""
    w = w.astype(float).copy()
    n = int((w > 0).sum())
    if n == 0 or limit * n < 1.0:
        return w
    for _ in range(max_iter):
        over = w > limit + 1e-12
        if not over.any():
            break
        excess = float((w[over] - limit).sum())
        w[over] = limit
        free = (~over) & (w > 0) & (w < limit)
        if not free.any():
            break
        w[free] += excess * w[free] / w[free].sum()
    return w


def _quarter_start(day: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(year=day.year, month=3 * ((day.month - 1) // 3) + 1, day=1)


def _composition_from_store(store: Any, code: str, day: pd.Timestamp) -> tuple[list[str], str] | None:
    """Composition portée par une note ``INDEX_CHANGE`` du journal (``extracted['constituents']``)."""
    if store is None:
        return None
    try:
        df = sg.notes_asof(store, day)
    except Exception:
        return None
    if not len(df):
        return None
    best = None
    for r in df.to_dict("records"):
        an = sg.note_analysis(r)
        et = r.get("event_type") or an.get("event_type")
        if et != "INDEX_CHANGE":
            continue
        tg = [c for c, _ in sg.effective_targets(r, an)]
        if code not in tg:
            continue
        ex = an.get("extracted") or {}
        members = ex.get("constituents") or (an.get("structured") or {}).get("constituents")
        if not members:
            continue
        eff = to_day(ex.get("effective_date")) or pd.Timestamp(r["first_tradable_session"])
        if eff > day:
            continue
        if best is None or eff > best[0]:
            best = (eff, [str(s).upper() for s in members], r["note_id"])
    if best is None:
        return None
    return best[1], f"composition de la note {best[2][:10]} (INDEX_CHANGE, effet le {_date(best[0])})"


def _liquidity_rank(eq: pd.DataFrame, listed: list[str], lo: pd.Timestamp, hi: pd.Timestamp, n: int) -> list[str]:
    w = eq[(eq["date"] >= lo) & (eq["date"] <= hi) & eq["symbol"].isin(listed)]
    if not len(w):
        return []
    g = w.groupby("symbol")
    val = g["value"].sum().reindex(listed).fillna(0.0)
    vol = g["volume"].sum().reindex(listed).fillna(0.0)
    score = val.rank(ascending=False, method="min") + vol.rank(ascending=False, method="min")
    order = pd.DataFrame({"s": score, "v": -val}).sort_values(["s", "v"]).index
    return list(order[:n])


def index_constituents(
    code: str,
    asof: Any,
    equities: Any = None,
    store: Any = None,
    universe: Any = None,
    brvm30_method: str = "trimestre",
) -> tuple[list[str], str]:
    """Constituants d'un indice à la date ``asof`` (sans information postérieure) et méthode.

    ``brvm30_method`` (approximation du BRVM 30 / BRVM 10 hors compositions connues) :
    ``"trimestre"`` (rang moyen valeur + volume au trimestre civil précédent, défaut) ou
    ``"valeur_6m"`` (valeur échangée sur 6 mois).
    """
    code = normalize_target(code) or str(code).upper()
    day = pd.Timestamp(to_day(asof))
    uni = universe if isinstance(universe, sg.Universe) else sg.Universe(equities if equities is not None else "default")
    snap = uni.snapshot(day)
    listed = uni.listed(day)
    if code in MARKET_CODES:
        return listed, "toutes les actions cotées"
    if code in ("IDX:PRESTIGE", "IDX:PRINCIPAL"):
        comp = code[4:]
        if snap is not None and "compartment" in snap.columns and (snap["compartment"] == comp).any():
            return sorted(snap.loc[snap["compartment"] == comp, "symbol"].unique()), "compartiment du BOC à la date"
        if snap is None and comp == "PRESTIGE":
            return sorted(sg.Universe.PRESTIGE_2026), "compartiment Prestige 2026 (avis 001-2026)"
        return [], "compartiment absent à cette date (indice créé le 02/01/2023)"
    if code.startswith("IDX:SECT:"):
        sec = code[9:]
        if snap is not None and "sector" in snap.columns:
            if (snap["sector"] == sec).any():
                return sorted(snap.loc[snap["sector"] == sec, "symbol"].unique()), "secteur du BOC à la date"
            eq = uni.equities
            hist = eq[(eq["date"] <= day) & (eq["sector"] == sec)] if eq is not None else None
            if hist is not None and len(hist):
                last = hist["date"].max()
                syms = sorted(set(hist.loc[hist["date"] == last, "symbol"]) & set(listed))
                return syms, f"classification du dernier BOC qui portait le secteur {sec} ({_date(last)})"
        return [s for s in listed if ref.SECTOR_2025.get(s) == sec], "secteur BRVM 2025 (reference)"
    if code in ("IDX:BRVM-30", "IDX:BRVM-10"):
        n = 30 if code == "IDX:BRVM-30" else 10
        if code == "IDX:BRVM-30":
            hit = _composition_from_store(store, code, day)
            if hit is not None:
                return sorted(set(hit[0])), hit[1]
            for eff, members, src in sorted(BRVM30_COMPOSITIONS, key=lambda x: x[0], reverse=True):
                e = pd.Timestamp(eff)
                if e <= day < e + pd.DateOffset(months=3):
                    return sorted(members), f"composition {src}"
        eq = uni.equities
        if eq is None or "value" not in eq.columns:
            return [], "composition inconnue (pas de panel)"
        if brvm30_method == "valeur_6m":
            lo, hi = day - pd.DateOffset(months=6) + pd.Timedelta(days=1), day
            w = eq[(eq["date"] >= lo) & (eq["date"] <= hi) & eq["symbol"].isin(listed)]
            val = w.groupby("symbol")["value"].sum().reindex(listed).fillna(0.0)
            members = list(val.sort_values(ascending=False, kind="stable").index[:n])
            how = f"approximation : {n} titres les plus échangés en valeur sur 6 mois (au {_date(hi)})"
        else:
            qs = _quarter_start(day)
            lo, hi = qs - pd.DateOffset(months=3), qs - pd.Timedelta(days=1)
            if eq["date"].min() > lo:
                lo, hi = eq["date"].min(), day
            members = _liquidity_rank(eq, listed, lo, hi, n)
            how = (f"approximation : {n} titres au meilleur rang moyen valeur + volume échangés du {_date(lo)} au "
                   f"{_date(hi)} (règle « les plus échangées sur un trimestre »)")
        return sorted(members), how
    kind = target_kind(code)
    if kind in ("symbol", "country", "sector", "theme", "market"):
        return uni.members(code, day)
    return [], "indice inconnu"


def index_aliases(code: str) -> set[str]:
    """Cibles dont les notes portent directement sur l'indice (alias)."""
    if code in MARKET_CODES:
        return {"IDX:BRVM-C", "IDX:BRVM-C-TR", "MARCHE"}
    if code.startswith("IDX:SECT:"):
        return {code, "SECT:" + code[9:]}
    return {code}


# ---------------------------------------------------------------------------
# Séries de niveaux
# ---------------------------------------------------------------------------


def _tr_returns(ctx: _Ctx) -> pd.Series:
    """Rendement Total Return reconstitué : ``r_Composite + Σ N·D_net / Cap(t−1)`` (spéc. §1.1)."""
    comp = ctx.levels[COMPOSITE_NAME].dropna() if COMPOSITE_NAME in ctx.levels else pd.Series(dtype=float)
    if not len(comp) or ctx.mk is None or "market_cap" not in ctx.mk:
        return pd.Series(dtype=float)
    mc = ctx.mk["market_cap"]
    mc = mc[~mc.index.duplicated(keep="last")].reindex(comp.index)
    cash = pd.Series(0.0, index=comp.index)
    if ctx.dv is not None and len(ctx.dv):
        dv = ctx.dv[ctx.dv["ex_date"].isin(comp.index)]
        if len(dv):
            from brvm_alpha.data.store import shares_outstanding_panel

            ca = ctx.ca if ctx.ca is not None else pd.DataFrame(columns=["symbol", "date", "kind", "ratio", "confidence"])
            pairs = dv.rename(columns={"ex_date": "date"})[["date", "symbol"]]
            try:
                n = shares_outstanding_panel(equities=pairs, corporate_actions=ca, listed_only=False)
            except Exception:  # pragma: no cover
                n = None
            if n is not None:
                for r in dv.itertuples(index=False):
                    if r.symbol in n.columns:
                        k = n.at[pd.Timestamp(r.ex_date), r.symbol]
                        if np.isfinite(k):
                            cash.loc[pd.Timestamp(r.ex_date)] += float(k) * float(r.amount)
    return comp.pct_change(fill_method=None) + (cash / mc.shift(1)).fillna(0.0)


def level_series(code: str, ctx: _Ctx) -> tuple[pd.Series, dict[str, Any]]:
    """Niveaux de l'indice ``<= asof`` et informations (nom BOC, chaînage, reconstitution)."""
    if code in ctx._series:
        return ctx._series[code]
    info: dict[str, Any] = {"name": None, "chained": False, "reconstructed": False, "notes": []}
    lv = ctx.levels
    s = pd.Series(dtype=float)
    if code == "IDX:BRVM-C-TR":
        off = lv[TR_NAME].dropna() if TR_NAME in lv else pd.Series(dtype=float)
        r = _tr_returns(ctx)
        info["name"] = TR_NAME
        if len(off):
            s = off.copy()
            first = off.index[0]
            back = r[r.index <= first]
            if len(back) > 1:
                # Chaînage arrière : L(t−1) = L(t) / (1 + r(t)).
                vals = [float(off.iloc[0])]
                idx = [first]
                rr = back.iloc[::-1]
                for d_prev, r_t in zip(rr.index[1:], rr.iloc[:-1]):
                    if not np.isfinite(r_t):
                        break
                    vals.append(vals[-1] / (1.0 + float(r_t)))
                    idx.append(d_prev)
                pre = pd.Series(vals[1:], index=idx[1:]).sort_index()
                s = pd.concat([pre, s]).sort_index()
                info["reconstructed"] = True
                info["notes"].append(f"avant le {_date(first)} : rendement total reconstitué (Composite + dividendes nets)")
        elif len(r):
            base_d = pd.Timestamp(TR_BASE[0])
            if r.index[-1] >= base_d:
                lvl = (1.0 + r.fillna(0.0)).cumprod()
                anchor = lvl.loc[:base_d].iloc[-1]
                s = lvl / anchor * TR_BASE[1]
                info["reconstructed"] = True
                info["notes"].append("indice non encore publié au BOC : niveau reconstitué (base 100 le 02/01/2025)")
    elif code.startswith("IDX:SECT:"):
        names = [n for n in index_names(code) if n in lv.columns and lv[n].notna().any()]
        if names:
            info["name"] = names[0]
            s = lv[names[0]].dropna()
            if len(names) > 1:
                old = lv[names[1]].dropna()
                if len(old) and len(s) and old.index[0] < s.index[0]:
                    link_d = s.index[0]
                    ref_old = old.loc[:link_d]
                    if len(ref_old):
                        ratio = float(s.iloc[0]) / float(ref_old.iloc[-1])
                        pre = old[old.index < link_d] * ratio
                        s = pd.concat([pre, s]).sort_index()
                        info["chained"] = True
                        info["notes"].append(f"série chaînée au {_date(link_d)} avec « {names[1]} » (composition différente)")
    else:
        for n in index_names(code):
            if n in lv.columns and lv[n].notna().any():
                info["name"] = n
                s = lv[n].dropna()
                break
    s = s[np.isfinite(s) & (s > 0)].sort_index()
    s = s[~s.index.duplicated(keep="last")]
    ctx._series[code] = (s, info)
    return s, info


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------


def _ret_hist(s: pd.Series, months: int) -> pd.Series:
    """Rendement sur ``months`` mois civils à chaque date (NaN si l'historique est trop court)."""
    if not len(s):
        return s
    idx = s.index
    refs = idx - pd.DateOffset(months=months)
    pos = idx.searchsorted(refs, side="right") - 1
    vals = s.to_numpy(dtype=float)
    out = np.full(len(s), np.nan)
    ok = pos >= 0
    out[ok] = vals[ok] / vals[pos[ok]] - 1.0
    return pd.Series(out, index=idx)


def _ret_back(s: pd.Series, t: pd.Timestamp, months: int) -> float | None:
    if not len(s):
        return None
    refd = t - pd.DateOffset(months=months)
    if s.index[0] > refd:
        return None
    base = s.loc[:refd]
    if not len(base):
        return None
    return float(s.iloc[-1] / base.iloc[-1] - 1.0)


def _daily_returns(s: pd.Series) -> pd.Series:
    r = np.log(s / s.shift(1))
    gap = s.index.to_series().diff().dt.days
    return r[(gap <= MAX_RETURN_GAP_DAYS) & np.isfinite(r)]


def _hist_window(h: pd.Series, t: pd.Timestamp, years: float) -> np.ndarray:
    lo = t - pd.DateOffset(years=int(years)) if float(years).is_integer() else t - pd.Timedelta(days=365.25 * years)
    w = h[(h.index > lo) & (h.index <= t)]
    return w.to_numpy(dtype=float)


def robust_z(x: float | None, hist: np.ndarray, clip: float = Z_CLIP, min_n: int = MIN_HISTORY) -> float | None:
    """z-score robuste ``(x − médiane) / (1,4826 · MAD)`` (écart-type si MAD nul), borné à ``±clip``."""
    if x is None or not np.isfinite(x):
        return None
    h = hist[np.isfinite(hist)]
    if len(h) < min_n:
        return None
    med = float(np.median(h))
    mad = 1.4826 * float(np.median(np.abs(h - med)))
    scale = mad if mad > 1e-12 else float(np.std(h))
    if not np.isfinite(scale) or scale <= 1e-12:
        return None
    return float(np.clip((x - med) / scale, -clip, clip))


def percentile_rank(x: float | None, hist: np.ndarray, min_n: int = MIN_HISTORY) -> float | None:
    """Part de l'historique ``<= x`` (dans [0, 1])."""
    if x is None or not np.isfinite(x):
        return None
    h = hist[np.isfinite(hist)]
    if len(h) < min_n:
        return None
    return float(np.mean(h <= x))


def _zinfo(series: pd.Series, t: pd.Timestamp, years: float) -> dict[str, float | None]:
    if series is None or not len(series):
        return {"value": None, "z": None, "pct": None, "median": None, "scale": None}
    s = series.loc[:t].dropna()
    if not len(s):
        return {"value": None, "z": None, "pct": None, "median": None, "scale": None}
    x = float(s.iloc[-1])
    h = _hist_window(s, t, years)
    hh = h[np.isfinite(h)]
    med = float(np.median(hh)) if len(hh) else None
    mad = 1.4826 * float(np.median(np.abs(hh - med))) if len(hh) else None
    scale = mad if mad and mad > 1e-12 else (float(np.std(hh)) if len(hh) else None)
    return {"value": x, "z": robust_z(x, h), "pct": percentile_rank(x, h), "median": med, "scale": scale}


def _mean_finite(xs: Iterable[float | None]) -> float | None:
    v = [x for x in xs if x is not None and np.isfinite(x)]
    return float(np.mean(v)) if v else None


# ---------------------------------------------------------------------------
# Composantes
# ---------------------------------------------------------------------------


def _breadth(ctx: _Ctx, code: str, members: list[str], t: pd.Timestamp, years: float) -> dict[str, Any]:
    cols = [m for m in members if m in ctx.close_adj.columns]
    out: dict[str, Any] = {"breadth_50": None, "breadth_200": None, "up_down_20": None, "z_b50": None,
                           "z_b200": None, "z_ud": None, "source_ud": None}
    if not cols:
        return out
    px = ctx.close_adj.reindex(columns=cols)
    ma50 = px.rolling(50, min_periods=40).mean()
    ma200 = px.rolling(200, min_periods=150).mean()
    a50 = (px > ma50).astype(float).where(ma50.notna() & px.notna())
    a200 = (px > ma200).astype(float).where(ma200.notna() & px.notna())
    b50 = a50.mean(axis=1, skipna=True).where(a50.notna().sum(axis=1) >= max(1, min(3, len(cols))))
    b200 = a200.mean(axis=1, skipna=True).where(a200.notna().sum(axis=1) >= max(1, min(3, len(cols))))
    if code in MARKET_CODES and ctx.mk is not None and {"n_up", "n_down"} <= set(ctx.mk.columns):
        up = ctx.mk["n_up"].astype(float)
        dn = ctx.mk["n_down"].astype(float)
        out["source_ud"] = "BOC : hausses et baisses du marché"
    else:
        r = ctx.ret.reindex(columns=cols)
        st = ctx.status.reindex(index=r.index, columns=cols)
        traded = st.eq("traded")
        up = ((r > 0) & traded).sum(axis=1).astype(float)
        dn = ((r < 0) & traded).sum(axis=1).astype(float)
        out["source_ud"] = "constituants"
    ud = up.rolling(20, min_periods=15).sum() / dn.rolling(20, min_periods=15).sum().clip(lower=1.0)
    lud = np.log(ud.where(ud > 0))
    i50, i200, iud = _zinfo(b50, t, years), _zinfo(b200, t, years), _zinfo(lud, t, years)
    out.update({
        "breadth_50": i50["value"], "breadth_200": i200["value"],
        "up_down_20": None if iud["value"] is None else float(np.exp(iud["value"])),
        "z_b50": i50["z"], "z_b200": i200["z"], "z_ud": iud["z"],
    })
    return out


def _valuation(ctx: _Ctx, code: str, members: list[str], t: pd.Timestamp, years: float, name: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {"per": None, "per_pct": None, "per_z": None, "yield_pct": None, "yield_rank": None,
                           "yield_z": None, "per_index": None, "valuation_source": None, "per_hist": None,
                           "yield_hist": None}
    if code in MARKET_CODES and ctx.mk is not None and "avg_per" in ctx.mk.columns:
        per_s = ctx.mk["avg_per"].where(ctx.mk["avg_per"] > 0)
        yld_s = ctx.mk["avg_yield_pct"] if "avg_yield_pct" in ctx.mk.columns else None
        out["valuation_source"] = "marché (PER moyen et rendement moyen du BOC)"
    else:
        cols = [m for m in members if ctx.per is not None and m in ctx.per.columns]
        if not cols:
            return out
        p = ctx.per[cols]
        p = p.where((p > PER_BOUNDS[0]) & (p <= PER_BOUNDS[1]))
        per_s = p.median(axis=1, skipna=True).where(p.notna().sum(axis=1) >= max(1, min(3, len(cols))))
        yld_s = None
        if ctx.yld is not None:
            y = ctx.yld[[c for c in cols if c in ctx.yld.columns]]
            y = y.where((y >= YIELD_BOUNDS[0]) & (y < YIELD_BOUNDS[1]))
            yld_s = y.median(axis=1, skipna=True).where(y.notna().sum(axis=1) >= max(1, min(3, len(cols))))
        out["valuation_source"] = "constituants (médianes)"
    ip, iy = _zinfo(per_s, t, years), _zinfo(yld_s, t, years) if yld_s is not None else _zinfo(None, t, years)
    out.update({"per": ip["value"], "per_pct": ip["pct"], "per_z": ip["z"], "yield_pct": iy["value"],
                "yield_rank": iy["pct"], "yield_z": iy["z"], "per_hist": ip, "yield_hist": iy})
    if name and ctx.ix_per is not None and name in ctx.ix_per.columns:
        v = ctx.ix_per[name].loc[:t].dropna()
        if len(v) and (t - v.index[-1]).days <= STALE_DAYS:
            out["per_index"] = float(v.iloc[-1])
    return out


def _split_factor_after(ctx: _Ctx, symbol: str, after: pd.Timestamp, until: pd.Timestamp) -> float:
    """Produit des ratios de division (et regroupements) dans ``]after, until]``."""
    ca = ctx.ca
    if ca is None or not len(ca):
        return 1.0
    c = ca[(ca["symbol"] == symbol) & ca["kind"].isin(["split", "reverse_split"])]
    if "confidence" in c.columns:
        c = c[c["confidence"] != "low"]
    d = pd.to_datetime(c["date"])
    c = c[(d > after) & (d <= until)]
    f = 1.0
    for r in c["ratio"].dropna():
        f *= float(r)
    return f


def _announced_dividends(ctx: _Ctx, t: pd.Timestamp, horizon: pd.Timestamp) -> dict[str, dict[str, Any]]:
    """Détachements annoncés par les notes (``DIV_NOTICE`` avec ``ex_date`` dans ``]t, horizon]``)."""
    if ctx.store is None:
        return {}
    try:
        df = ctx.notes_frame(t)
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for r in df.to_dict("records") if len(df) else []:
        an = sg.note_analysis(r)
        if (r.get("event_type") or an.get("event_type")) != "DIV_NOTICE":
            continue
        ex = an.get("extracted") or {}
        exd = to_day(ex.get("ex_date")) if ex.get("ex_date") else None
        if exd is None or not (t < exd <= horizon):
            continue
        for s, _o in sg.effective_targets(r, an):
            if target_kind(s) == "symbol":
                out[s] = {"ex_date": exd, "div_net": _fin(ex.get("div_net")), "note_id": r["note_id"],
                          "pay_date": to_day(ex.get("pay_date")) if ex.get("pay_date") else None}
    return out


def expected_detachments(ctx: _Ctx, members: list[str], t: pd.Timestamp,
                         window_days: int = DIV_WINDOW_DAYS) -> pd.DataFrame:
    """Prochains détachements attendus des constituants (historique + annonces), un titre par ligne.

    Date attendue : jour de l'année médian des 3 derniers détachements, projeté sur la
    première occurrence postérieure à ``t`` et à 180 jours après le dernier détachement.
    Un titre sans détachement depuis 550 jours n'est pas compté comme payeur.
    """
    horizon = t + pd.Timedelta(days=window_days)
    ann = _announced_dividends(ctx, t, t + pd.Timedelta(days=max(window_days, 120)))
    rows = []
    dv = ctx.dv if ctx.dv is not None else pd.DataFrame(columns=["symbol", "ex_date", "amount"])
    close_t = ctx.close.loc[:t].iloc[-1] if len(ctx.close.loc[:t]) else pd.Series(dtype=float)
    for s in members:
        h = dv[dv["symbol"] == s].sort_values("ex_date")
        px = _fin(close_t.get(s))
        if s in ann:
            a = ann[s]
            amt = a.get("div_net")
            if amt is None and len(h):
                last = h.iloc[-1]
                amt = float(last["amount"]) / _split_factor_after(ctx, s, pd.Timestamp(last["ex_date"]), t)
            rows.append({"symbol": s, "payer": True, "expected_ex": a["ex_date"], "source": "annoncé (note)",
                         "div_net": amt, "close": px, "yield": (amt / px) if amt and px else None,
                         "last_ex": h["ex_date"].iloc[-1] if len(h) else None, "in_window": a["ex_date"] <= horizon,
                         "note_id": a["note_id"]})
            continue
        if not len(h):
            rows.append({"symbol": s, "payer": False, "expected_ex": None, "source": "aucun détachement connu",
                         "div_net": None, "close": px, "yield": None, "last_ex": None, "in_window": False})
            continue
        last = h.iloc[-1]
        last_ex = pd.Timestamp(last["ex_date"])
        if (t - last_ex).days > 550:
            rows.append({"symbol": s, "payer": False, "expected_ex": None, "source": "aucun détachement depuis 550 jours",
                         "div_net": None, "close": px, "yield": None, "last_ex": last_ex, "in_window": False})
            continue
        doy = int(np.median([pd.Timestamp(d).dayofyear for d in h["ex_date"].iloc[-3:]]))
        cands = []
        for y in (t.year - 1, t.year, t.year + 1, t.year + 2):
            d = pd.Timestamp(year=y, month=1, day=1) + pd.Timedelta(days=doy - 1)
            if d > t and d > last_ex + pd.Timedelta(days=180):
                cands.append(d)
        exp = min(cands) if cands else None
        amt = float(last["amount"]) / _split_factor_after(ctx, s, last_ex, t)
        rows.append({"symbol": s, "payer": True, "expected_ex": exp, "source": "historique (date anniversaire)",
                     "div_net": amt, "close": px, "yield": (amt / px) if px else None, "last_ex": last_ex,
                     "in_window": exp is not None and exp <= horizon})
    return pd.DataFrame(rows)


def _dividend_season(ctx: _Ctx, members: list[str], t: pd.Timestamp, window_days: int,
                     weights: pd.Series) -> dict[str, Any]:
    tab = expected_detachments(ctx, members, t, window_days)
    if not len(tab):
        return {"div_payers": 0, "div_expected": 0, "div_season_share": None, "div_yield_window": None,
                "div_announced": 0, "div_table": tab}
    payers = tab[tab["payer"]]
    exp = payers[payers["in_window"]]
    w = weights.reindex(exp["symbol"]).fillna(0.0).to_numpy()
    y = pd.to_numeric(exp["yield"], errors="coerce").fillna(0.0).to_numpy()
    return {
        "div_payers": int(len(payers)), "div_expected": int(len(exp)),
        "div_season_share": (len(exp) / len(payers)) if len(payers) else None,
        "div_yield_window": float(np.sum(w * y)) if len(exp) else 0.0,
        "div_announced": int((exp["source"] == "annoncé (note)").sum()),
        "div_table": tab,
    }


#: Nombre maximal de notes détaillées par indice (``notes_detail``).
NOTES_DETAIL_MAX = 12


def _notes_component(ctx: _Ctx, code: str, members: list[str], con: pd.DataFrame | None) -> dict[str, Any]:
    out = {"notes_score": None, "notes_n": 0, "notes_index": 0.0, "notes_constituents": 0.0, "z_notes": None,
           "notes_n_index": 0, "notes_n_constituents": 0, "notes_n_informative": 0, "notes_detail": []}
    if con is None or not len(con):
        return out
    alias = index_aliases(code)
    d = con[con["target"].isin(alias) & (con["relation"] == "directe")]
    c = con[con["target"].isin(members) & (con["kind"] == "symbol") & ~con["source_target"].isin(alias)]
    v = ctx.value.loc[ctx.value.index > ctx.date - pd.DateOffset(months=LIQUIDITY_MONTHS)]
    vw = v.reindex(columns=members).sum().fillna(0.0) if len(v) else pd.Series(0.0, index=members)
    s_i = c.groupby("target")["contribution"].sum().reindex(members).fillna(0.0)
    const = float((vw * s_i).sum() / vw.sum()) if vw.sum() > 0 else float(s_i.mean()) if len(s_i) else 0.0
    idx = float(d["contribution"].sum())
    n = int(pd.concat([d["note_id"], c["note_id"]]).nunique())
    # Notes porteuses d'information : contribution non nulle. Des notes de score nul (avis
    # administratifs propagés au marché…) ne rendent pas la composante disponible : z = 0
    # diluerait les autres composantes par la renormalisation des poids.
    informative = pd.concat([d.loc[d["contribution"].abs() > 1e-12, "note_id"],
                             c.loc[c["contribution"].abs() > 1e-12, "note_id"]])
    n_info = int(informative.nunique())
    # Notes qui portent la composante : part de chaque note dans le score (indice et alias : la
    # contribution elle-même ; constituant : contribution × part de la valeur échangée).
    share = (vw / vw.sum()) if vw.sum() > 0 else pd.Series(1.0 / max(len(members), 1), index=members)
    detail: dict[str, dict[str, Any]] = {}
    for part, rel_default in ((d, "indice"), (c, "constituant")):
        for r in part.to_dict("records"):
            val = float(r["contribution"]) * (1.0 if rel_default == "indice" else float(share.get(r["target"], 0.0)))
            if abs(val) <= 1e-12:
                continue
            e = detail.setdefault(str(r["note_id"]), {
                "note_id": str(r["note_id"]), "title": r.get("title") or "", "author": r.get("author"),
                "event_type": r.get("event_type"), "note_score": float(r["note_score"]), "decay": float(r["decay"]),
                "first_tradable_session": pd.Timestamp(r["first_tradable_session"]), "targets": [], "part": 0.0,
                "via": rel_default})
            e["part"] += val
            if r["target"] not in e["targets"]:
                e["targets"].append(r["target"])
    ranked = sorted(detail.values(), key=lambda e: -abs(e["part"]))
    out.update({"notes_index": idx, "notes_constituents": const, "notes_n": n,
                "notes_n_index": int(d["note_id"].nunique()), "notes_n_constituents": int(c["note_id"].nunique()),
                "notes_n_informative": n_info, "notes_detail": ranked[:NOTES_DETAIL_MAX]})
    if n_info:
        raw = idx + const
        out["notes_score"] = raw
        out["z_notes"] = float(np.clip(raw / NOTES_SCALE, -Z_CLIP, Z_CLIP))
    return out


def _stance_support(stance: str, composite: float | None, avail: Mapping[str, float],
                    weights: Mapping[str, float]) -> tuple[float, float]:
    """Accord des composantes avec la position et marge au seuil le plus proche.

    - SURPONDÉRER / SOUS-PONDÉRER : part (pondérée par ``w·|z|``) des composantes de même
      signe que la position ;
    - NEUTRE : ``1 − |Σ w·z| / Σ w·|z|`` (composantes équilibrées ou nulles : neutralité
      solide ; toutes du même signe : neutralité fragile) ;
    - marge : distance du score composite au seuil de changement de position le plus proche.
    """
    if composite is None or not avail:
        return 0.0, 0.0
    tot = sum(weights[k] * abs(v) for k, v in avail.items())
    if stance == "NEUTRE":
        agree = 1.0 if tot <= 1e-12 else 1.0 - abs(sum(weights[k] * v for k, v in avail.items())) / tot
        margin = min(STANCE_UP - composite, composite - STANCE_DOWN)
    else:
        sgn = 1.0 if stance == "SURPONDÉRER" else -1.0
        agree = 0.0 if tot <= 1e-12 else sum(weights[k] * max(0.0, sgn * v) for k, v in avail.items()) / tot
        margin = (composite - STANCE_UP) if sgn > 0 else (STANCE_DOWN - composite)
    return float(np.clip(agree, 0.0, 1.0)), float(max(margin, 0.0))


def _stance(composite: float | None) -> str:
    if composite is None or not np.isfinite(composite):
        return "NEUTRE"
    if composite > STANCE_UP:
        return "SURPONDÉRER"
    if composite < STANCE_DOWN:
        return "SOUS-PONDÉRER"
    return "NEUTRE"


@dataclass
class _Eval:
    row: dict[str, Any]
    members: list[str]
    method: str
    series: pd.Series
    info: dict[str, Any]
    extras: dict[str, Any]


def _evaluate_one(code: str, ctx: _Ctx, con: pd.DataFrame | None, weights: Mapping[str, float], years: float,
                  window_days: int, brvm30_method: str, composite_series: pd.Series | None) -> _Eval | None:
    s, info = level_series(code, ctx)
    t = ctx.asof
    if not len(s) or (t - s.index[-1]).days > STALE_DAYS:
        return None
    t_obs = s.index[-1]
    members, method = index_constituents(code, t_obs, equities=ctx.eq, store=ctx.store, universe=ctx.universe,
                                         brvm30_method=brvm30_method)
    approx = method.startswith("approximation")
    name = info.get("name")
    level = float(s.iloc[-1])

    # Rendements.
    rets = {m: _ret_back(s, t_obs, m) for m in (1, 3, 6, 12)}
    ytd = None
    if ctx.ytd is not None and name in ctx.ytd.columns and not info.get("reconstructed"):
        y = ctx.ytd[name].loc[:t_obs].dropna()
        if len(y) and y.index[-1] == t_obs:
            ytd = float(y.iloc[-1]) / 100.0
    if ytd is None:
        prev = s[s.index.year < t_obs.year]
        if len(prev) and (s.index[0].year < t_obs.year):
            ytd = float(level / prev.iloc[-1] - 1.0)
    rel = {}
    if composite_series is not None and code not in MARKET_CODES and len(composite_series):
        for m in (3, 12):
            a, b = rets[m], _ret_back(composite_series.loc[:t_obs], t_obs, m)
            rel[m] = None if a is None or b is None else a - b

    # Risque.
    dr = _daily_returns(s)
    vol = float(dr.iloc[-63:].std(ddof=1) * math.sqrt(252)) if len(dr) >= 40 else None
    win = s[s.index > t_obs - pd.DateOffset(months=12)]
    dd = float(level / win.max() - 1.0) if len(win) else None
    mdd = float((win / win.cummax() - 1.0).min()) if len(win) else None

    # Régime.
    from brvm_alpha.quant.regime import market_regime

    reg = market_regime(s)
    last = reg.iloc[-1]
    state = last.get("state")
    state = state if isinstance(state, str) else None
    trend200 = _fin(last.get("trend"))
    slope = _fin(last.get("ma_slope"))
    ma200 = _fin(last.get("ma"))
    vol_pct = _fin(last.get("vol_percentile"))
    z_reg = REGIME_SCORE.get(state) if state else None

    # Tendance (z contre l'historique propre de l'indice).
    t3, t12 = _zinfo(_ret_hist(s, 3), t_obs, years), _zinfo(_ret_hist(s, 12), t_obs, years)
    ttr = _zinfo(reg["trend"], t_obs, years)
    z_trend = _mean_finite([t3["z"], t12["z"], ttr["z"]])

    # Valorisation, largeur, dividendes, notes.
    val = _valuation(ctx, code, members, t_obs, years, name)
    z_val = _mean_finite([None if val["per_z"] is None else -val["per_z"], val["yield_z"]])
    br = _breadth(ctx, code, members, t_obs, years)
    z_br = _mean_finite([br["z_b50"], br["z_b200"], br["z_ud"]])
    capw = ctx.cap_weights(members, cap=WEIGHT_CAPS.get(code)) if members else pd.Series(dtype=float)
    div = _dividend_season(ctx, members, t_obs, window_days, capw) if members else {
        "div_payers": 0, "div_expected": 0, "div_season_share": None, "div_yield_window": None, "div_announced": 0,
        "div_table": pd.DataFrame()}
    nt = _notes_component(ctx, code, members, con)

    comps = {"tendance": z_trend, "valorisation": z_val, "largeur": z_br, "regime": z_reg, "notes": nt["z_notes"]}
    avail = {k: v for k, v in comps.items() if v is not None and np.isfinite(v) and weights.get(k, 0) > 0}
    wsum = sum(weights[k] for k in avail)
    composite = float(sum(weights[k] * avail[k] for k in avail) / wsum) if wsum > 0 else None
    stance = _stance(composite)
    # Score sans la composante « notes » (transparence : effet des notes sur la position).
    rest = {k: v for k, v in avail.items() if k != "notes"}
    wrest = sum(weights[k] for k in rest)
    composite_ex = float(sum(weights[k] * rest[k] for k in rest) / wrest) if wrest > 0 else None
    wall = sum(v for v in weights.values() if v > 0)
    coverage = wsum / wall if wall > 0 else 0.0
    agreement, margin = _stance_support(stance, composite, avail, weights)
    hist_q = min(1.0, len(s) / 504.0)
    data_q = math.sqrt(coverage) * (0.6 + 0.4 * hist_q)
    if approx:
        data_q *= 0.85
    if info.get("chained") or info.get("reconstructed"):
        data_q *= 0.9
    if len(members) < 3:
        data_q *= 0.8
    margin_q = min(1.0, margin / 0.5)
    confidence = float(np.clip(data_q * (0.3 + 0.4 * agreement + 0.3 * margin_q), 0.05, 0.95))

    row: dict[str, Any] = {
        "index": code, "label": target_label(code).replace("indice ", ""), "name": name, "date": t_obs,
        "level": level, "ret_1m": rets[1], "ret_3m": rets[3], "ret_6m": rets[6], "ret_12m": rets[12], "ytd": ytd,
        "rel_3m": rel.get(3), "rel_12m": rel.get(12), "vol_63": vol, "drawdown": dd, "max_drawdown_12m": mdd,
        "regime": state or "indéterminé", "trend_200": trend200, "ma_200": ma200, "ma_slope": slope, "vol_percentile": vol_pct,
        "per": val["per"], "per_pct": val["per_pct"], "per_z": val["per_z"], "yield_pct": val["yield_pct"],
        "yield_rank": val["yield_rank"], "yield_z": val["yield_z"], "per_index": val["per_index"],
        "breadth_50": br["breadth_50"], "breadth_200": br["breadth_200"], "up_down_20": br["up_down_20"],
        "div_payers": div["div_payers"], "div_expected_60d": div["div_expected"],
        "div_season_share": div["div_season_share"], "div_yield_60d": div["div_yield_window"],
        "notes_score": nt["notes_score"], "notes_n": nt["notes_n"], "notes_detail": nt["notes_detail"],
        "z_trend": z_trend, "z_valuation": z_val, "z_breadth": z_br, "z_regime": z_reg, "z_notes": nt["z_notes"],
        "composite": composite, "stance": stance, "confidence": confidence, "agreement": agreement,
        "composite_ex_notes": composite_ex, "stance_ex_notes": _stance(composite_ex),
        "n_constituents": len(members),
        "composition": method, "approx_composition": approx,
    }
    extras = {"val": val, "br": br, "div": div, "notes": nt, "trend": {"r3": t3, "r12": t12, "t200": ttr},
              "weights": dict(weights), "avail": avail, "agreement": agreement, "coverage": coverage,
              "margin": margin, "data_quality": data_q,
              "cap_weights": capw, "regime": reg,
              "notes_moment": ctx.notes_moment if ctx.store is not None else None}
    row["reasons"] = _reasons(row, info, extras, window_days, years)
    return _Eval(row, members, method, s, info, extras)


def _reasons(row: dict[str, Any], info: dict[str, Any], ex: dict[str, Any], window_days: int, years: float) -> list[str]:
    R: list[str] = []
    lab = row["label"]
    t = pd.Timestamp(row["date"])
    ytd_txt = f"{_pct(row['ytd'], 2)} depuis le 31/12/{t.year - 1}" if row["ytd"] is not None else "variation annuelle n.d."
    R.append(f"{lab} : {_num(row['level'], 2)} au {_date(t)} ; {ytd_txt}, {_pct(row['ret_1m'])} sur 1 mois, "
             f"{_pct(row['ret_3m'])} sur 3 mois, {_pct(row['ret_12m'])} sur 12 mois.")
    for n in info.get("notes", []):
        R.append(f"Série : {n}.")
    if row.get("rel_12m") is not None or row.get("rel_3m") is not None:
        R.append(f"Écart avec le BRVM Composite : {_pct(row.get('rel_3m'))} sur 3 mois, {_pct(row.get('rel_12m'))} sur 12 mois.")
    tr = ex["trend"]
    if row["trend_200"] is not None:
        R.append(f"Tendance : niveau {_pct(row['trend_200'])} par rapport à la moyenne 200 séances "
                 f"({_num(row['ma_200'], 2)}), pente 20 séances {_pct(row['ma_slope'], 2)} ; régime {row['regime']} ; "
                 f"z tendance {_z_txt(row['z_trend'])} (3 mois {_z_txt(tr['r3']['z'])}, 12 mois {_z_txt(tr['r12']['z'])}, "
                 f"écart à la moyenne {_z_txt(tr['t200']['z'])}, contre {int(years)} ans d'historique).")
    else:
        R.append(f"Tendance : historique trop court pour la moyenne 200 séances ; z tendance {_z_txt(row['z_trend'])}.")
    R.append(f"Risque : volatilité {_pct(row['vol_63'], 1, signed=False)} annualisée (63 séances) ; repli "
             f"{_pct(row['drawdown'])} depuis le plus haut de 12 mois, repli maximal {_pct(row['max_drawdown_12m'])}.")
    val = ex["val"]
    if val["per"] is not None or val["yield_pct"] is not None:
        who = "moyen du marché" if row["index"] in MARKET_CODES else "médian des constituants"
        per_txt = (f"PER {who} {_num(val['per'], 2)} (percentile {_num(100 * val['per_pct'], 0)}, z "
                   f"{_z_txt(val['per_z'])})") if val["per"] is not None and val["per_pct"] is not None else (
            f"PER {who} {_num(val['per'], 2)}" if val["per"] is not None else "PER n.d.")
        y_txt = (f"rendement net {'moyen' if row['index'] in MARKET_CODES else 'médian'} {_num(val['yield_pct'], 2)} % "
                 f"(percentile {_num(100 * val['yield_rank'], 0)}, z {_z_txt(val['yield_z'])})") if (
            val["yield_pct"] is not None and val["yield_rank"] is not None) else (
            f"rendement net {_num(val['yield_pct'], 2)} %" if val["yield_pct"] is not None else "rendement n.d.")
        pub = f" ; PER publié de l'indice {_num(val['per_index'], 2)}" if val.get("per_index") is not None and row["index"] not in MARKET_CODES else ""
        R.append(f"Valorisation : {per_txt} ; {y_txt}, sur {int(years)} ans{pub} ; z valorisation "
                 f"{_z_txt(row['z_valuation'])} (positif = bon marché).")
    br = ex["br"]
    if br["breadth_50"] is not None:
        R.append(f"Largeur : {_pct(br['breadth_50'], 0, signed=False)} des constituants au-dessus de leur moyenne 50 séances, "
                 f"{_pct(br['breadth_200'], 0, signed=False)} au-dessus de la 200 ; hausses/baisses sur 20 séances "
                 f"{_num(br['up_down_20'], 2) if br['up_down_20'] is not None else 'n.d.'} ({br['source_ud']}) ; "
                 f"z largeur {_z_txt(row['z_breadth'])}.")
    div = ex["div"]
    if row["div_payers"] and not row["div_expected_60d"]:
        horizon = t + pd.Timedelta(days=window_days)
        tab = div.get("div_table")
        nxt = None
        if tab is not None and len(tab) and "expected_ex" in tab:
            e = pd.to_datetime(tab.loc[tab["payer"], "expected_ex"], errors="coerce").dropna()
            nxt = e.min() if len(e) else None
        R.append(f"Dividendes : aucun détachement attendu d'ici le {_date(horizon)} parmi les {row['div_payers']} "
                 f"payeur(s)" + (f" ; prochain détachement attendu vers le {_date(nxt)} (historique)" if nxt is not None else "")
                 + " : pas de baisse mécanique de l'indice de prix à court terme.")
    elif row["div_payers"]:
        horizon = t + pd.Timedelta(days=window_days)
        mech = ("réinvestis dans l'indice Total Return : sans baisse mécanique" if row["index"] == "IDX:BRVM-C-TR"
                else f"soit une baisse mécanique d'environ {_pct(row['div_yield_60d'], 2, signed=False)} de l'indice de prix "
                     "aux détachements (sans effet sur le rendement total)")
        ann = f", dont {div['div_announced']} annoncé(s) par une note" if div.get("div_announced") else ""
        R.append(f"Dividendes : {row['div_expected_60d']} détachement(s) attendu(s) d'ici le {_date(horizon)} sur "
                 f"{row['div_payers']} payeur(s) ({_pct(row['div_season_share'], 0, signed=False)}){ann} ; rendement net "
                 f"attendu pondéré par la capitalisation {_pct(row['div_yield_60d'], 2, signed=False)}, {mech}.")
    nt = ex["notes"]
    nm = ex.get("notes_moment")
    when = ""
    if nm is not None and nm.direct:
        when = f" (connues au {nm.known_at:%d/%m/%Y %H:%M} UTC, appliquées à la séance du {_date(nm.session)})"
    elif nm is not None:
        when = f" (mode historique : règle stricte au {_date(nm.session)})"
    if nt["notes_n"] and nt["z_notes"] is None:
        notes_nd = f"n.d. : {nt['notes_n']} note(s) en vigueur, toutes de score nul"
        R.append(f"Notes{when} : {nt['notes_n']} note(s) en vigueur, toutes de score nul (aucune information "
                 "directionnelle) ; composante exclue du score.")
    elif nt["notes_n"]:
        notes_nd = ""
        R.append(f"Notes{when} : score {_signed(nt['notes_score'], 3)} ({nt['notes_n']} note(s) en vigueur : "
                 f"{_signed(nt['notes_index'], 3)} sur l'indice et ses alias, {_signed(nt['notes_constituents'], 3)} pour "
                 f"les constituants pondérés par la valeur échangée sur 6 mois) ; z notes {_z_txt(row['z_notes'])}.")
        top = [e for e in nt.get("notes_detail") or []][:3]
        if top:
            R.append("Notes qui portent la composante : " + " ; ".join(
                f"« {str(e['title'])[:70]} » ({', '.join(e['targets'][:3])}, score {_signed(e['note_score'], 2)}, "
                f"part {_signed(e['part'], 3)})" for e in top) + ".")
        if row.get("composite_ex_notes") is not None and row.get("composite") is not None:
            flip = "" if row["stance_ex_notes"] == row["stance"] else (
                " : la position change à cause de cette composante (elle pèse "
                f"{_num(100 * ex['weights'].get('notes', 0), 0)} % du score dès qu'une note porte un score, même faible)")
            R.append(f"Effet des notes : sans la composante notes, le score composite serait "
                     f"{_z_txt(row['composite_ex_notes'])} ({row['stance_ex_notes']}) ; avec elle, "
                     f"{_z_txt(row['composite'])} ({row['stance']}){flip}.")
    else:
        notes_nd = "n.d. : aucune note en vigueur" if nm is not None else "n.d. : aucun journal de notes"
        R.append(f"Notes{when} : aucune note en vigueur sur l'indice ou ses constituants ; composante exclue du "
                 "score.")
    R.append(f"Composition ({row['n_constituents']} titres) : {row['composition']}.")
    w = ex["weights"]
    parts = []
    for k, lab_k in (("tendance", "tendance"), ("valorisation", "valorisation"), ("largeur", "largeur"),
                     ("regime", "régime"), ("notes", "notes")):
        z = ex["avail"].get(k)
        nd = notes_nd if k == "notes" and notes_nd else "n.d."
        parts.append(f"{lab_k} {_z_txt(z)} × {_num(w.get(k, 0), 2)}" if z is not None else f"{lab_k} {nd}")
    comp = row["composite"]
    lean = ""
    if row["stance"] == "NEUTRE" and comp is not None:
        lean = " (penche à la hausse)" if comp >= 0.25 else (" (penche à la baisse)" if comp <= -0.25 else "")
    R.append(f"Score composite {_z_txt(comp)} ({' ; '.join(parts)}) → {row['stance']}{lean} "
             f"(seuils ±{_num(STANCE_UP, 1)}) ; confiance {_num(row['confidence'], 2)} (accord des composantes avec la "
             f"position {_num(ex['agreement'], 2)}, marge au seuil {_num(ex['margin'], 2)}, couverture "
             f"{_num(ex['coverage'], 2)}, qualité des données {_num(ex['data_quality'], 2)}).")
    R.append("Lecture factuelle et datée : ce score n'est pas une garantie de rendement.")
    return R


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def _codes(indices: Iterable[str] | None) -> list[str]:
    if indices is None:
        return list(INDEX_CODES)
    out = []
    for i in indices:
        c = normalize_target(i) or str(i).upper()
        if not c.startswith("IDX:"):
            raise ValueError(f"indice inconnu : {i!r}")
        out.append(c)
    return out


def _prepare(panels: Any, store: Any, asof: Any, calendar: Any, half_life: float,
             propagation: Mapping[str, float] | None, notes_known_at: Any = None) -> tuple[_Ctx, pd.DataFrame | None]:
    ctx = _Ctx(panels, asof, store=store, calendar=calendar, notes_known_at=notes_known_at)
    con = None
    if store is not None and ctx.notes_direct:
        con = sg.note_contributions(store, ctx.date, half_life=half_life, calendar=ctx.calendar,
                                    propagation=propagation, universe=ctx.universe, known_at=ctx.notes_moment)
    elif store is not None:
        con = sg.note_contributions(store, ctx.asof, half_life=half_life, calendar=ctx.calendar,
                                    propagation=propagation, universe=ctx.universe)
    return ctx, con


def evaluate_indices(
    panels: Any = None,
    store: Any = None,
    asof: Any = None,
    indices: Iterable[str] | None = None,
    weights: Mapping[str, float] | None = None,
    history_years: float = HISTORY_YEARS,
    window_days: int = DIV_WINDOW_DAYS,
    half_life: float = sg.DEFAULT_HALF_LIFE,
    calendar: Any = None,
    propagation: Mapping[str, float] | None = None,
    brvm30_method: str = "trimestre",
    notes_known_at: Any = None,
) -> pd.DataFrame:
    """Une ligne par indice disponible à ``asof`` (voir le module pour les définitions).

    - ``panels`` : dictionnaire de tables longues (:func:`load_panels`), chemin du panel, ou
      ``None`` (panel du dépôt) ; toutes les tables datées sont tronquées à ``asof`` ;
    - ``store`` : ``NoteStore`` (ou ``DataFrame`` / liste de ``Note``) pour la composante
      « notes » et les dividendes annoncés ; ``None`` : composante exclue ;
    - ``asof`` : date d'évaluation (défaut : dernière séance du panel) ;
    - ``indices`` : codes (``IDX:BRVM-C``…) ou désignations libres ; défaut : tous ;
    - ``weights`` : poids des composantes (:data:`COMPONENT_WEIGHTS`) ;
    - ``notes_known_at`` : ``None`` (défaut : mode historique, notes en règle stricte à
      ``asof``) ou instant de connaissance des notes (mode direct : notes connues à cet instant,
      appliquées à la séance qui suit le dernier BOC ; les cours restent ceux de ``asof``).

    ``attrs`` : ``asof``, ``weights``, ``history_years``, ``notes_moment``
    (``signals.NotesMoment`` ou ``None`` sans journal) et ``notes_line`` (phrase datée).

    Index : code de l'indice. Colonnes : ``label``, ``name`` (BOC), ``date``, ``level``,
    ``ret_1m``…``ret_12m``, ``ytd`` (décimaux), ``rel_3m``, ``rel_12m``, ``vol_63``,
    ``drawdown``, ``max_drawdown_12m``, ``regime``, ``trend_200``, ``ma_200``, ``ma_slope``,
    ``per``, ``per_pct``, ``per_z``, ``yield_pct`` (en %), ``yield_rank``, ``yield_z``,
    ``per_index``, ``breadth_50``, ``breadth_200``, ``up_down_20``, ``div_payers``,
    ``div_expected_60d``, ``div_season_share``, ``div_yield_60d``, ``notes_score``,
    ``notes_n``, ``z_trend``, ``z_valuation``, ``z_breadth``, ``z_regime``, ``z_notes``,
    ``composite``, ``stance``, ``confidence``, ``n_constituents``, ``composition``,
    ``approx_composition``, ``reasons``, ``notes_detail`` (notes qui portent la composante
    « notes » : ``note_id``, ``title``, ``targets``, ``note_score``, ``decay``, ``part``),
    ``composite_ex_notes`` et ``stance_ex_notes`` (score et position sans la composante notes).
    """
    w = dict(COMPONENT_WEIGHTS if weights is None else weights)
    unknown = set(w) - set(COMPONENT_WEIGHTS)
    if unknown:
        raise ValueError(f"composantes inconnues : {', '.join(sorted(unknown))}")
    ctx, con = _prepare(panels, store, asof, calendar, half_life, propagation, notes_known_at)
    comp_s, _ = level_series("IDX:BRVM-C", ctx)
    rows = []
    for code in _codes(indices):
        ev = _evaluate_one(code, ctx, con, w, history_years, window_days, brvm30_method, comp_s)
        if ev is not None:
            rows.append(ev.row)
    df = pd.DataFrame(rows)
    if len(df):
        df = df.set_index("index")
    df.attrs.update({"asof": ctx.asof, "weights": w, "history_years": history_years,
                     "notes": "lecture factuelle, sans garantie ; poids non validés hors échantillon",
                     "notes_moment": ctx.notes_moment if store is not None else None,
                     "notes_line": ctx.notes_moment.describe() if store is not None else
                     "Notes : aucun journal transmis, composante « notes » exclue"})
    return df


def _contributions(ctx: _Ctx, code: str, members: list[str], s: pd.Series, t: pd.Timestamp,
                   months: int | None) -> tuple[pd.DataFrame, float | None, float | None]:
    """Contributions des constituants à la performance : ``w_i(t0) × r_i(t0 → t)``.

    ``w_i(t0)`` : poids en capitalisation totale à ``t0`` (nombre de titres × cours), plafonnés
    à 20 % pour le BRVM Prestige (:data:`WEIGHT_CAPS`) ; la composition est celle de ``t``
    (les entrées et sorties de la fenêtre ne sont pas rejouées) : l'écart de reconstitution
    entre la somme des contributions et le rendement publié le mesure.
    Pour le Composite TR, les rendements des titres incluent les dividendes nets.
    """
    if months is None:
        t0s = s[s.index.year < t.year]
        if not len(t0s):
            return pd.DataFrame(), None, None
        t0 = t0s.index[-1]
    else:
        base = s.loc[:t - pd.DateOffset(months=months)]
        if not len(base):
            return pd.DataFrame(), None, None
        t0 = base.index[-1]
    px = ctx.tr_idx if (code == "IDX:BRVM-C-TR" and ctx.tr_idx is not None) else ctx.close_adj
    cols = [m for m in members if m in px.columns]
    p0 = px.loc[:t0].iloc[-1].reindex(cols)
    p1 = px.loc[:t].iloc[-1].reindex(cols)
    r = p1 / p0 - 1.0
    w0 = ctx.cap_weights(cols, t0, cap=WEIGHT_CAPS.get(code))
    contrib = (w0 * r).fillna(0.0)
    idx_ret = float(s.loc[:t].iloc[-1] / s.loc[t0] - 1.0) if t0 in s.index else None
    tab = pd.DataFrame({"weight_start": w0, "return": r, "contribution": contrib})
    tab.index.name = "symbol"
    return tab.sort_values("contribution", ascending=False), idx_ret, float(contrib.sum())


def _change_my_mind(row: dict[str, Any], ex: dict[str, Any], s: pd.Series) -> list[str]:
    """Seuils chiffrés qui feraient changer la position (une composante à la fois)."""
    out: list[str] = []
    comp = row["composite"]
    if comp is None:
        return ["Score composite indisponible : aucune composante calculable."]
    w = ex["weights"]
    avail = ex["avail"]
    wsum = sum(w[k] for k in avail)
    stance = row["stance"]
    targets = []
    if stance == "SURPONDÉRER":
        targets.append(("NEUTRE", STANCE_UP))
    elif stance == "SOUS-PONDÉRER":
        targets.append(("NEUTRE", STANCE_DOWN))
    else:
        targets.extend([("SURPONDÉRER", STANCE_UP), ("SOUS-PONDÉRER", STANCE_DOWN)])
    lab = {"tendance": "tendance seule", "valorisation": "valorisation seule", "largeur": "largeur seule",
           "regime": "régime seul", "notes": "notes seules"}
    for new_stance, bound in targets:
        delta = bound - comp
        out.append(f"Passage à {new_stance} si le score composite franchit {_signed(bound, 2)} (actuel {_signed(comp, 2)}, "
                   f"écart {_signed(delta, 2)}).")
        for k, z in avail.items():
            if w.get(k, 0) <= 0:
                continue
            z_new = z + delta * wsum / w[k]
            if abs(z_new) > Z_CLIP + 1e-9:
                out.append(f"  - {lab[k]} : il faudrait un z de {_signed(z_new, 2)}, hors de la borne ±{_num(Z_CLIP, 0)} : "
                           "ce levier seul ne suffit pas.")
                continue
            txt = f"  - {lab[k]} : z de {_signed(z, 2)} à {_signed(z_new, 2)}"
            if k == "valorisation":
                ph, yh = ex["val"].get("per_hist") or {}, ex["val"].get("yield_hist") or {}
                zy = ex["val"].get("yield_z")
                zp = ex["val"].get("per_z")
                if ph and ph.get("scale") and zp is not None:
                    other = zy if zy is not None else None
                    zp_new = -(2 * z_new - other) if other is not None else -z_new
                    zp_new = float(np.clip(zp_new, -Z_CLIP, Z_CLIP))
                    per_new = ph["median"] + zp_new * ph["scale"]
                    txt += f", par exemple un PER de {_num(per_new, 2)} (actuel {_num(ex['val']['per'], 2)}) à rendement inchangé"
            elif k == "tendance":
                t2 = ex["trend"]["t200"]
                ma = row.get("ma_200")
                if t2.get("scale") and ma and t2.get("z") is not None:
                    zs = [ex["trend"]["r3"]["z"], ex["trend"]["r12"]["z"]]
                    zs = [x for x in zs if x is not None]
                    n = len(zs) + 1
                    zt_new = float(np.clip(z_new * n - sum(zs), -Z_CLIP, Z_CLIP))
                    tr_new = t2["median"] + zt_new * t2["scale"]
                    lvl = ma * (1 + tr_new)
                    txt += (f", par exemple une clôture vers {_num(lvl, 2)} ({_pct(lvl / row['level'] - 1)} par rapport au "
                            f"niveau actuel ; écart à la moyenne 200 séances {_pct(tr_new)}), 3 et 12 mois inchangés")
            elif k == "notes":
                txt += f", soit un score de notes de {_signed(z_new * NOTES_SCALE, 2)} (actuel {_signed(z * NOTES_SCALE, 2)})"
            elif k == "regime":
                states = [st for st, v in REGIME_SCORE.items() if (v - z) * np.sign(delta) >= abs(delta) * wsum / w[k] - 1e-9]
                if states:
                    txt += f" : il faudrait un régime {' ou '.join(states)}"
                else:
                    txt += " : aucun changement de régime n'y suffit"
            elif k == "largeur":
                txt += (f" (part > MM50 actuelle {_pct(row.get('breadth_50'), 0, signed=False)}, > MM200 "
                        f"{_pct(row.get('breadth_200'), 0, signed=False)})")
            out.append(txt + ".")
    ma = row.get("ma_200")
    if ma:
        out.append(f"Repère de tendance : moyenne 200 séances à {_num(ma, 2)} ({_pct(ma / row['level'] - 1)} du niveau "
                   "actuel) ; une clôture durable en dessous avec une pente négative fait passer le régime à « baissier ».")
    if len(s):
        hi = s[s.index > s.index[-1] - pd.DateOffset(months=3)].max()
        out.append(f"Repère de stress : une baisse de 15 % depuis le plus haut des 63 dernières séances "
                   f"({_num(hi, 2)}), soit une clôture sous {_num(0.85 * hi, 2)}, sous la moyenne 200 séances, "
                   "déclenche l'état « stress » (market_regime).")
    ph = ex["val"].get("per_hist") or {}
    if row.get("per") is not None and ph.get("median") is not None and ph.get("scale"):
        zp = ex["val"].get("per_z")
        out.append(f"Repère de valorisation : PER médian de l'historique {_num(ph['median'], 2)} (échelle robuste "
                   f"{_num(ph['scale'], 2)}) ; PER actuel {_num(row['per'], 2)}, soit z {_z_txt(zp)} ; z +1 = "
                   f"{_num(ph['median'] + ph['scale'], 2)}, z +2 = {_num(ph['median'] + 2 * ph['scale'], 2)} "
                   "(au-delà, la composante valorisation pèse fortement à la baisse).")
    return out


def _calendar(ctx: _Ctx, code: str, members: list[str], div_table: pd.DataFrame, t: pd.Timestamp,
              horizon_days: int = 120) -> list[dict[str, Any]]:
    """Événements à venir : détachements (annoncés, attendus), AG, dates limites, révisions."""
    ev: list[dict[str, Any]] = []
    end = t + pd.Timedelta(days=horizon_days)
    if div_table is not None and len(div_table):
        for r in div_table.to_dict("records"):
            d = r.get("expected_ex")
            if d is None or pd.isna(d) or not (t < pd.Timestamp(d) <= end):
                continue
            y = r.get("yield")
            ev.append({"date": pd.Timestamp(d), "type": "détachement", "symbol": r["symbol"], "source": r["source"],
                       "description": f"détachement {r['source']}" + (
                           f", dividende net ≈ {_num(r['div_net'], 0)} FCFA ({_pct(y, 2, signed=False)} du cours)"
                           if r.get("div_net") and y else "")})
    if ctx.store is not None:
        try:
            df = ctx.notes_frame(t)
        except Exception:
            df = pd.DataFrame()
        for r in df.to_dict("records") if len(df) else []:
            an = sg.note_analysis(r)
            tg = [c for c, _ in sg.effective_targets(r, an)]
            if not (set(tg) & (set(members) | index_aliases(code))):
                continue
            ex = an.get("extracted") or {}
            for key, lab in (("ag_date", "assemblée générale"), ("pay_date", "paiement du dividende")):
                d = to_day(ex.get(key)) if ex.get(key) else None
                if d is not None and t < d <= end:
                    ev.append({"date": d, "type": lab, "symbol": ",".join(s for s in tg if target_kind(s) == "symbol"),
                               "source": f"note {r['note_id'][:10]}", "description": f"{lab} : {r.get('title', '')[:80]}"})
    for y in (t.year, t.year + 1):
        for md, lab in (("04-30", "date limite BRVM : comptes annuels et rapport du T1 (R7)"),
                        ("10-31", "date limite BRVM : rapport du S1 et du T3 (R7)")):
            d = pd.Timestamp(f"{y}-{md}")
            if t < d <= end:
                ev.append({"date": d, "type": "date limite", "symbol": "", "source": "avis 214-2026 et 291-2025",
                           "description": lab})
    if code == "IDX:BRVM-30":
        q = _quarter_start(t) + pd.DateOffset(months=3)
        if q <= end:
            ev.append({"date": q, "type": "révision", "symbol": "", "source": "document 01 §10.2",
                       "description": "révision trimestrielle du BRVM 30 (1er jour ouvré du trimestre)"})
    if code == "IDX:PRESTIGE":
        d = pd.Timestamp(year=t.year + 1, month=1, day=2)
        if d <= end:
            ev.append({"date": d, "type": "révision", "symbol": "", "source": "avis 001-2026",
                       "description": "révision annuelle du compartiment Prestige (1er jour ouvré de janvier)"})
    ev.sort(key=lambda e: (e["date"], e["symbol"]))
    return ev


def index_dossier(
    index: str,
    panels: Any = None,
    store: Any = None,
    asof: Any = None,
    weights: Mapping[str, float] | None = None,
    history_years: float = HISTORY_YEARS,
    window_days: int = DIV_WINDOW_DAYS,
    half_life: float = sg.DEFAULT_HALF_LIFE,
    calendar: Any = None,
    propagation: Mapping[str, float] | None = None,
    brvm30_method: str = "trimestre",
    recent_days: int = 90,
    notes_known_at: Any = None,
) -> dict[str, Any]:
    """Dossier détaillé d'un indice à ``asof`` (mêmes données point-in-time que :func:`evaluate_indices`).

    ``notes_known_at`` : voir :func:`evaluate_indices` (mode direct des notes) ; clés ajoutées :
    ``notes_moment`` et ``notes_line``.

    Clés : ``index``, ``label``, ``asof``, ``evaluation`` (ligne de :func:`evaluate_indices`),
    ``constituents`` (``DataFrame`` : poids en capitalisation, cours, rendements, PER,
    rendement net, valeur échangée, score des notes, filtres actifs), ``composition``,
    ``contributions`` (par fenêtre ``1m``, ``3m``, ``12m``, ``ytd`` : tableau, rendement de
    l'indice, somme des contributions), ``top_contributors`` / ``bottom_contributors`` (12
    mois), ``recent_notes``, ``calendar`` (événements des 120 prochains jours),
    ``change_my_mind`` (seuils chiffrés), ``overlays`` (filtres et veto des constituants),
    ``reasons``.
    """
    code = normalize_target(index) or str(index).upper()
    if not code.startswith("IDX:"):
        raise ValueError(f"indice inconnu : {index!r}")
    w = dict(COMPONENT_WEIGHTS if weights is None else weights)
    ctx, con = _prepare(panels, store, asof, calendar, half_life, propagation, notes_known_at)
    comp_s, _ = level_series("IDX:BRVM-C", ctx)
    ev = _evaluate_one(code, ctx, con, w, history_years, window_days, brvm30_method, comp_s)
    if ev is None:
        raise ValueError(f"{code} : aucune donnée au {_date(ctx.asof)} (indice non publié à cette date)")
    row, members, s = ev.row, ev.members, ev.series
    t = pd.Timestamp(row["date"])
    capw = ev.extras["cap_weights"]
    windows = {"1m": 1, "3m": 3, "12m": 12, "ytd": None}
    contribs = {}
    for k, m in windows.items():
        tab, idx_ret, csum = _contributions(ctx, code, members, s, t, m)
        contribs[k] = {"table": tab, "index_return": idx_ret, "sum_contributions": csum,
                       "gap": None if idx_ret is None or csum is None else idx_ret - csum}
    snap = ctx.universe.snapshot(t)
    info = snap.drop_duplicates("symbol").set_index("symbol") if snap is not None else pd.DataFrame()
    v6 = ctx.value.loc[ctx.value.index > t - pd.DateOffset(months=LIQUIDITY_MONTHS)]
    scores = sg.aggregate_contributions(con) if con is not None else pd.DataFrame(columns=sg.SCORE_COLUMNS)
    overlays = sg.manual_overlays(store, ctx.date if ctx.notes_direct else t, calendar=ctx.calendar, equities=ctx.eq,
                                  propagation=propagation,
                                  known_at=ctx.notes_moment if ctx.notes_direct else None) \
        if store is not None else None
    rows = []
    for sym in members:
        g = info.loc[sym] if sym in info.index else None
        r12 = contribs["12m"]["table"]
        rows.append({
            "symbol": sym,
            "name": None if g is None else g.get("name"),
            "sector": None if g is None else g.get("sector"),
            "country": ref.country_of(sym),
            "compartment": None if g is None else g.get("compartment"),
            "close": _fin(ctx.close[sym].loc[:t].dropna().iloc[-1]) if sym in ctx.close and ctx.close[sym].loc[:t].notna().any() else None,
            "weight": float(capw.get(sym, np.nan)),
            "ret_1m": _ret_back(ctx.close_adj[sym].dropna(), t, 1) if sym in ctx.close_adj else None,
            "ret_3m": _ret_back(ctx.close_adj[sym].dropna(), t, 3) if sym in ctx.close_adj else None,
            "ret_12m": _ret_back(ctx.close_adj[sym].dropna(), t, 12) if sym in ctx.close_adj else None,
            "contribution_12m": _fin(r12["contribution"].get(sym)) if len(r12) else None,
            "contribution_ytd": _fin(contribs["ytd"]["table"]["contribution"].get(sym)) if len(contribs["ytd"]["table"]) else None,
            "per": _fin(ctx.per[sym].loc[:t].dropna().iloc[-1]) if ctx.per is not None and sym in ctx.per and ctx.per[sym].loc[:t].notna().any() else None,
            "net_yield_pct": _fin(ctx.yld[sym].loc[:t].dropna().iloc[-1]) if ctx.yld is not None and sym in ctx.yld and ctx.yld[sym].loc[:t].notna().any() else None,
            "value_6m": float(v6[sym].sum()) if sym in v6 else 0.0,
            "note_score": _fin(scores["score"].get(sym)) if len(scores) else None,
            "flags": [f["code"] for f in (overlays["flags"].get(sym, []) if overlays else [])],
            "veto": bool(overlays and sym in overlays["veto"]),
        })
    cons = pd.DataFrame(rows).set_index("symbol").sort_values("weight", ascending=False) if rows else pd.DataFrame()
    c12 = contribs["12m"]["table"]
    top = c12.head(5) if len(c12) else c12
    bottom = c12.tail(5).iloc[::-1] if len(c12) else c12
    recent: list[dict[str, Any]] = []
    if con is not None and len(con):
        rel = con[con["target"].isin(set(members) | index_aliases(code))
                  & (con["first_tradable_session"] >= t - pd.Timedelta(days=recent_days))]
        for nid, g in rel.groupby("note_id", sort=False):
            r0 = g.iloc[0]
            recent.append({"note_id": nid, "first_tradable_session": r0["first_tradable_session"], "title": r0["title"],
                           "event_type": r0["event_type"], "author": r0["author"], "score": r0["note_score"],
                           "targets": sorted(set(g["target"])), "decay": float(g["decay"].max()),
                           "risk_flags": r0["risk_flags"]})
        recent.sort(key=lambda d: d["first_tradable_session"], reverse=True)
    cal = _calendar(ctx, code, members, ev.extras["div"].get("div_table"), t)
    cmm = _change_my_mind(row, ev.extras, s)
    reasons = list(row["reasons"])
    for k in ("12m", "ytd"):
        c = contribs[k]
        if c["index_return"] is not None and len(c["table"]):
            tb = c["table"]
            best = ", ".join(f"{i} {_pct(v, 2)}" for i, v in tb["contribution"].head(3).items())
            worst = ", ".join(f"{i} {_pct(v, 2)}" for i, v in tb["contribution"].tail(3).iloc[::-1].items())
            reasons.append(f"Contributions {('sur 12 mois' if k == '12m' else 'depuis le 31/12')} (poids en capitalisation "
                           f"au départ) : indice {_pct(c['index_return'], 2)}, somme des contributions "
                           f"{_pct(c['sum_contributions'], 2)} (écart de reconstitution {_pct(c['gap'], 2)}) ; en tête "
                           f"{best} ; en queue {worst}.")
    if overlays is not None:
        hits = [m for m in members if m in overlays["flags"] or m in overlays["veto"]]
        if hits:
            reasons.append("Filtres actifs sur les constituants : " + " ; ".join(
                f"{m} ({', '.join(sorted({f['code'] for f in overlays['flags'].get(m, [])} | ({'veto'} if m in overlays['veto'] else set())))})"
                for m in hits) + ".")
    return {
        "index": code, "label": row["label"], "asof": ctx.asof, "evaluation": row, "composition": ev.method,
        "constituents": cons, "contributions": contribs, "top_contributors": top, "bottom_contributors": bottom,
        "recent_notes": recent, "calendar": cal, "change_my_mind": cmm, "overlays": overlays,
        "dividends": ev.extras["div"].get("div_table"), "reasons": reasons,
        "notes_moment": ctx.notes_moment if store is not None else None,
        "notes_line": ctx.notes_moment.describe() if store is not None else
        "Notes : aucun journal transmis, composante « notes » exclue",
    }


__all__ = [
    "COMPONENT_WEIGHTS", "INDEX_CODES", "BRVM30_COMPOSITIONS", "BRVM30_T4_2026", "BRVM30_T3_2026",
    "evaluate_indices", "index_dossier", "index_constituents", "index_aliases", "level_series", "load_panels",
    "truncate_panels", "expected_detachments", "robust_z", "percentile_rank",
]
