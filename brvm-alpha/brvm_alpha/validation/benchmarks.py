"""Étalons de la validation (spécification §8.2, additif v1.1 D2).

Cinq étalons, tous évalués sur la fenêtre commune ``[t0 ; fin]`` et rebasés à ``t0`` :

1. ``TR`` : BRVM Composite Total Return (``store.composite_tr_reconstructed``,
   ``official=True`` : niveaux officiels raccordés à la reconstruction) — étalon principal ;
2. ``EW`` : panier équipondéré en rendement total des titres **éligibles de A** (masque
   d'éligibilité point-in-time des décisions de A, rebalancement mensuel,
   ``store.equal_weight_tr``) — il isole la compétence de sélection ;
3. ``PRIX`` : BRVM Composite (indice prix, information seulement) ;
4. ``BRVM10`` jusqu'au 30/12/2022 ; ``BRVM30`` et ``PRESTIGE`` à partir du 02/01/2023 ;
5. ``FONDS`` : médiane des fonds actions (catégorie A du BOC) : **non disponible** tant que
   les valeurs liquidatives des OPCVM ne sont pas extraites dans le panel (déclaré
   explicitement, jamais remplacé par une autre série).

Aucun coût n'est déduit des étalons (ce ne sont pas des stratégies investissables) ; ce
module ne calcule aucune performance de stratégie.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "BENCHMARKS",
    "benchmark_levels",
    "equal_weight_from_panels",
    "equal_weight_level",
]

#: Code -> (libellé, rôle).
BENCHMARKS: dict[str, tuple[str, str]] = {
    "TR": ("BRVM Composite Total Return (officiel raccordé, reconstruit avant)", "étalon principal"),
    "EW": ("panier équipondéré TR des éligibles de A (mensuel)", "compétence de sélection"),
    "PRIX": ("BRVM Composite (indice prix)", "information seulement"),
    "BRVM10": ("BRVM 10 (jusqu'au 30/12/2022)", "information"),
    "BRVM30": ("BRVM 30 (à partir du 02/01/2023)", "information"),
    "PRESTIGE": ("BRVM Prestige (à partir du 02/01/2023)", "information"),
    "FONDS": ("médiane des fonds actions (catégorie A du BOC)", "information"),
}
_INDEX_NAMES = {"PRIX": "BRVM COMPOSITE", "BRVM10": "BRVM 10", "BRVM30": "BRVM 30", "PRESTIGE": "BRVM PRESTIGE"}
_INDEX_LIMITS = {"BRVM10": (None, "2022-12-30"), "BRVM30": ("2023-01-02", None), "PRESTIGE": ("2023-01-02", None)}


def _has_parquet(panel_dir: str | Path | None, name: str) -> bool:
    return panel_dir is not None and (Path(panel_dir) / f"{name}.parquet").exists()


def _month_end_sessions(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(dates, index=dates)
    return pd.DatetimeIndex(s.groupby(dates.to_period("M")).max().to_numpy())


def equal_weight_from_panels(tr_index: pd.DataFrame, eligible_mask: pd.DataFrame | None, base_value: float = 100.0
                             ) -> pd.Series:
    """Panier équipondéré TR mensuel à partir d'un panel large d'indices TR par titre.

    Même règle que ``store.equal_weight_tr(rebalance="monthly")`` : poids égaux fixés à la
    dernière séance de chaque mois (et à la première) sur les titres éligibles **à cette
    date** (masque connu à la clôture), appliqués aux rendements des séances suivantes,
    puis dérive des poids ; un titre sans cours garde sa valeur. Repli utilisé quand le
    panel parquet n'est pas disponible (panels en mémoire, tests).
    """
    tr = tr_index.sort_index().astype(float)
    ret = tr / tr.ffill().shift(1) - 1.0
    if eligible_mask is None:
        elig = tr.notna()
    else:
        elig = eligible_mask.reindex(index=tr.index, columns=tr.columns)
        elig = elig.astype("boolean").fillna(False).astype(bool)
    rebal = set(_month_end_sessions(pd.DatetimeIndex(tr.index))) | {tr.index[0]}
    r = np.zeros(len(tr.index))
    weights: pd.Series | None = None
    for i, d in enumerate(tr.index):
        if weights is not None and float(weights.sum()) > 0:
            ri = ret.loc[d, weights.index].fillna(0.0)
            r[i] = float((weights * ri).sum()) / float(weights.sum())
            weights = weights * (1.0 + ri)
        if d in rebal:
            names = elig.columns[elig.loc[d].to_numpy()]
            weights = pd.Series(1.0, index=names) if len(names) else None
    return pd.Series(base_value * np.cumprod(1.0 + r), index=tr.index, name="EW_TR_monthly")


def equal_weight_level(
    panels: Mapping[str, Any],
    *,
    panel_dir: str | Path | None = None,
    eligible_mask: pd.DataFrame | None = None,
) -> tuple[pd.Series | None, str, str]:
    """Étalon n° 2 : panier équipondéré TR des éligibles (masque PIT de A, mensuel).

    ``store.equal_weight_tr(panel_dir, masque, rebalance="monthly")`` si le panel parquet
    existe, sinon :func:`equal_weight_from_panels` sur ``panels["tr_index"]``. Renvoie
    ``(niveaux, source, note)``.
    """
    ew = None
    src = ""
    note = "" if eligible_mask is not None else "masque d'éligibilité de A absent : titres cotés non suspendus"
    if _has_parquet(panel_dir, "adjusted_prices") and _has_parquet(panel_dir, "equities"):
        from brvm_alpha.data import store

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ew = store.equal_weight_tr(panel_dir, eligible_mask, rebalance="monthly")
            src = "store.equal_weight_tr(masque PIT de A, rebalance='monthly')"
        except Exception as exc:  # noqa: BLE001 - repli sur le panel en mémoire
            note = (note + " ; " if note else "") + f"store indisponible ({exc.__class__.__name__})"
    if ew is None and isinstance(panels.get("tr_index"), pd.DataFrame):
        ew = equal_weight_from_panels(panels["tr_index"], eligible_mask)
        src = "panels['tr_index'] (même règle que store.equal_weight_tr, mensuel)"
    return ew, src or "aucune source", note


def _composite_tr(panels: Mapping[str, Any], panel_dir: str | Path | None) -> tuple[pd.Series | None, str]:
    if _has_parquet(panel_dir, "indices") and _has_parquet(panel_dir, "market"):
        from brvm_alpha.data import store

        try:
            s = store.composite_tr_reconstructed(panel_dir, official=True)
            return pd.Series(s, dtype=float), "store.composite_tr_reconstructed(official=True)"
        except Exception as exc:  # noqa: BLE001 - repli sur le panel du moteur
            note = f"reconstruction indisponible ({exc.__class__.__name__}) ; "
    else:
        note = ""
    mt = panels.get("market_tr") if isinstance(panels, Mapping) else None
    if mt is not None:
        return pd.Series(mt, dtype=float), note + "panels['market_tr']"
    return None, note + "aucun Composite TR"


def _index_levels(panels: Mapping[str, Any], panel_dir: str | Path | None) -> pd.DataFrame | None:
    if _has_parquet(panel_dir, "indices"):
        from brvm_alpha.data import store

        try:
            return store.load_indices(panel_dir, indices=list(_INDEX_NAMES.values()), wide=True)
        except Exception:  # noqa: BLE001 - indices facultatifs
            return None
    idx = panels.get("indices") if isinstance(panels, Mapping) else None
    return idx if isinstance(idx, pd.DataFrame) else None


def benchmark_levels(
    panels: Mapping[str, Any],
    calendar: pd.DatetimeIndex,
    *,
    panel_dir: str | Path | None = None,
    eligible_mask: pd.DataFrame | None = None,
    end: Any = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Niveaux quotidiens des étalons sur ``calendar`` et notes de disponibilité.

    Renvoie ``(niveaux, notes)`` : ``niveaux`` (date × code, NaN hors couverture : aucun
    remplissage au-delà de la dernière valeur, pour ne pas inventer de rendements nuls) et
    ``notes[code] = {"libelle", "role", "disponible", "source", "note"}``. ``end`` borne les
    séries (fin de l'échantillon évalué).
    """
    cal = pd.DatetimeIndex(calendar)
    levels: dict[str, pd.Series] = {}
    notes: dict[str, dict[str, Any]] = {}

    def put(code: str, series: pd.Series | None, source: str, note: str = "") -> None:
        lab, role = BENCHMARKS[code]
        ok = series is not None and bool(pd.Series(series).notna().any())
        if ok:
            s = pd.Series(series, dtype=float)
            s.index = pd.DatetimeIndex(pd.to_datetime(s.index))
            s = s[~s.index.duplicated(keep="last")].sort_index()
            s = s.reindex(s.index.union(cal)).ffill(limit_area="inside").reindex(cal)
            if end is not None:
                s = s.where(s.index <= pd.Timestamp(end))
            ok = bool(s.notna().any())
            if ok:
                levels[code] = s
        notes[code] = {"libelle": lab, "role": role, "disponible": ok, "source": source,
                       "note": note if ok else (note or "non disponible")}

    tr, src = _composite_tr(panels, panel_dir)
    put("TR", tr, src)

    ew, ew_src, ew_note = equal_weight_level(panels, panel_dir=panel_dir, eligible_mask=eligible_mask)
    put("EW", ew, ew_src, ew_note)

    idx = _index_levels(panels, panel_dir)
    for code, name in _INDEX_NAMES.items():
        s = None
        if idx is not None and name in idx.columns:
            s = idx[name].dropna()
            lo, hi = _INDEX_LIMITS.get(code, (None, None))
            if lo is not None:
                s = s[s.index >= pd.Timestamp(lo)]
            if hi is not None:
                s = s[s.index <= pd.Timestamp(hi)]
        lim = {"BRVM10": "publié jusqu'au 30/12/2022", "BRVM30": "publié à partir du 02/01/2023",
               "PRESTIGE": "publié à partir du 02/01/2023"}.get(code, "")
        put(code, s, f"indices.parquet « {name} »" if s is not None else "indices absents", lim)

    put("FONDS", None, "aucune",
        "non disponible : les valeurs liquidatives des OPCVM actions (catégorie A du BOC) ne sont pas extraites "
        "dans le panel ; étalon non calculé (aucune série de substitution)")
    frame = pd.DataFrame(levels, index=cal)
    frame.index.name = "date"
    return frame, notes
