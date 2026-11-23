"""Le modèle BRVM Alpha v1 (spécification ``docs/SPECIFICATION_STRATEGIE.md``, v1.0 + additif v1.1).

Additif v1.1 (§8.4, décisions figées le 22/11/2026 avant toute exécution sur S1), appliqué ici :
D1 (fenêtres en séances, bornes à 5 séances, seuils au prorata des BOC disponibles), D3 (garde
de capitalisation non bloquante), D4 (remplissage de capacité plafonné à 98 %/n_cible), D5
(drawdown relatif depuis t0, panier w_EW des 20 mieux classés), D6 (signaux sur le montant
de dividende connu en t), D8 (« indice discipliné », variante ``REF``), D9 (variante ``I``
cœur-satellite), D10 (événements pays datés de ``reference.COUNTRY_EVENTS``) et D11 (aucune
note de l'analyste en validation S1).

Contrat (``docs/ARCHITECTURE.md``) : ``BrvmAlpha(config).signals(asof, panels)``,
``.target_weights(asof, panels)`` et ``.explain(asof, panels, symbol)``.

Ordre des couches (§1.5), appliqué à chaque décision ``t`` (clôture du BOC de ``t``,
exécution à partir de ``t + 1``) :

1. **Données** : toutes les entrées sont tronquées à ``t`` (``backtest.engine.truncate_asof``)
   avant tout calcul ; contrôles de qualité (§9.1 : rendement quotidien > |50 %|,
   capitalisation reconstruite à plus de 3 % de la capitalisation publiée).
2. **Filtres de risque** R1-R12 (§5.6) et **règles d'événements pays** (§4.3) : ils priment
   sur le score (achats bloqués, plafonds réduits, exclusions).
3. **Univers** U1-U10 (§2), dépendant du capital K.
4. **Score factoriel** (§3.2-§3.4) : EP, DY, MOM6_1 (modulé), LOWVOL, QUAL ; transformation
   en rang gaussien ; moins de 3 blocs valides ⇒ score neutre.
5. **Surcouches de calendrier** (§5.2) : malus S2 (nouveaux achats seulement), report des
   ventes avant un détachement, poche S1 (variante E).
6. **Construction** (§6) : ``portfolio.construct.target_portfolio`` (bande 30/50, 12 à 20
   lignes, plafonds ligne, secteur, pays, AES et liquidité), puis risque de portefeuille
   (§9.1 : drawdown relatif contre le TR, mode « indice discipliné »).

Les surcouches de l'analyste (module ``brvm_alpha.notes``, facultatif) sont appliquées
**après** le score : veto (exclusion) et inclinaison bornée à ±0,5 écart-type, tracés
dans les diagnostics et dans :meth:`BrvmAlpha.explain`. Si le module ne s'importe pas,
il est ignoré proprement et c'est signalé.

Panels attendus (dictionnaire, ou ``PanelView`` du moteur) : voir :func:`build_panels`.
Clés reconnues : ``close`` (cours ajusté du moteur) et ``adj_factor``, ou ``close_raw``
(clôture brute du BOC) ; ``close_adj``, ``tr_index``, ``split_factor``,
``missing_sessions``, ``stats_usable`` ; ``volume``, ``value``, ``status``, ``per``,
``net_yield_pct``, ``last_div_net``, ``last_div_date``, ``ref_price`` ; ``flags``
(drapeaux du BOC : ``VAL-T``, ``EX-D``…), ``bid`` / ``ask`` (carnet de clôture),
``shares`` (nombre de titres reconstruit) ; séries et tables datées : ``market_tr``
(Composite TR), ``market`` (``date, avg_per, risk_premium, market_cap``),
``dividends_table`` (``date`` = date de connaissance, ``symbol, ex_date, amount``),
``corporate_actions`` (``date, symbol, kind, ratio, confidence``), ``country_events``
(``date, country, rule``…) et ``dividend_calendar`` (avis de paiement : ``date,
symbol, ex_date, amount``).

**Honnêteté** : toutes les sorties sont des **estimations** sous hypothèses (coûts, données
reconstruites, seuils non validés). Rien ici ne garantit un gain ; la variante A n'a pas
encore été validée sur l'échantillon pré-enregistré S1 (§8).
"""

from __future__ import annotations

import importlib

import math
import warnings
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from brvm_alpha import paths as _paths
from brvm_alpha import reference, settings
from brvm_alpha.backtest import engine
from brvm_alpha.config import PlatformConfig
from brvm_alpha.portfolio import construct
from brvm_alpha.quant import features as F
from brvm_alpha.quant import macro, scoring

__all__ = [
    "COUNTRY_RULES",
    "FAMILY_V1",
    "FAMILY_V11",
    "REFERENCE_VARIANT",
    "SIGNAL_LABELS",
    "VARIANTS",
    "VARIANT_SPECS",
    "AlphaDecision",
    "BrvmAlpha",
    "VariantSpec",
    "build_panels",
    "dividend_amount_gap",
    "notes_available",
]

#: Répertoire du panel : ``<dépôt>/data/panel``, ou ``<BRVM_ALPHA_DONNEES>/panel`` (:mod:`brvm_alpha.paths`).
DEFAULT_PANEL_DIR = _paths.PANEL_DIR

#: Bornes de l'échantillon vierge S1 et début de S0 (§8.1).
S1_END = "2022-11-16"
_S1_END_TS = pd.Timestamp(S1_END)
S0_START = "2022-11-17"

#: Bandeau permanent (§10).
BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."

#: Noms des signaux exposés par :meth:`BrvmAlpha.signals` (clé interne -> libellé).
SIGNAL_LABELS: dict[str, str] = {
    "ep": "EP",
    "dy": "DY",
    "mom6_1": "MOM6_1",
    "lowvol": "LOWVOL",
    "quality_proxy": "QUAL",
    "mom3_1": "MOM3_1",
    "mom6_0": "MOM6_0",
    "mom12_1": "MOM12_1",
    "mom12_7": "MOM12_7",
    "amihud": "AMIHUD",
}

_SCORE_BLOCKS = ("ep", "dy", "mom6_1", "lowvol", "quality_proxy", "mom12_1")
_RESEARCH = ("mom3_1", "mom6_0", "mom12_1", "mom12_7", "amihud")


@dataclass(frozen=True)
class VariantSpec:
    """Variante pré-enregistrée (§3.4 ; additif v1.1, §8.4).

    ``kind`` : ``"alpha"`` (A à H : score factoriel et construction du §6), ``"reference"``
    (REF : « indice discipliné » D8, rebalancement annuel) ou ``"core_satellite"`` (I :
    ``core_share × w_REF + (1 − core_share) × w_A``, D9).
    """

    code: str
    weights: str  # code des poids du score (A, B, C ou D)
    weighting: str  # "equal" (A), "hrp_tilt" (G) ou "mv_alpha" (H)
    sector_neutral: tuple[str, ...] = ()
    s1_pocket: bool = False
    regime_scaling: bool = False
    description: str = ""
    kind: str = "alpha"
    core_share: float = 0.0


#: Les variantes déclarées avant toute exécution sur S1 : A à H (§3.4), I (additif v1.1, D9) et
#: la référence REF (« indice discipliné », D8 ; essai REF-ID, hors famille de la PBO).
VARIANT_SPECS: dict[str, VariantSpec] = {
    "A": VariantSpec("A", "A", "equal", description="principal : poids du §3.2, équipondéré, mensuel, bande 30/50"),
    "B": VariantSpec("B", "B", "equal", description="EP 0,25 / DY 0,25 / MOM6_1 0,50 (choisi après coup)"),
    "C": VariantSpec("C", "C", "equal", description="horizon long : MOM6_1 0,20 + MOM12_1 0,15"),
    "D": VariantSpec("D", "A", "equal", ("ep", "dy"), description="A avec EP et DY classés dans les secteurs"),
    "E": VariantSpec("E", "A", "equal", s1_pocket=True, description="A + poche S1 (capture du dividende, ≤ 20 %)"),
    "F": VariantSpec("F", "A", "equal", regime_scaling=True, description="A + exposition × 0,75 en régime agité"),
    "G": VariantSpec("G", "A", "hrp_tilt", description="A pondéré par HRP incliné (γ = 0,5)"),
    "H": VariantSpec("H", "A", "mv_alpha", description="A pondéré par moyenne-variance (alpha de Grinold)"),
    "I": VariantSpec("I", "A", "equal", kind="core_satellite", core_share=0.5,
                     description="cœur-satellite : 0,5 × indice discipliné (annuel) + 0,5 × A (mensuel), D9"),
    "REF": VariantSpec("REF", "A", "equal", kind="reference",
                       description="indice discipliné (D8) : 20 plus grosses capitalisations éligibles, annuel"),
}
#: Tous les codes acceptés par :class:`BrvmAlpha` (famille v1.1 puis référence).
VARIANTS: tuple[str, ...] = tuple(VARIANT_SPECS)
#: Famille v1.0 (8 variantes du §3.4 d'origine).
FAMILY_V1: tuple[str, ...] = ("A", "B", "C", "D", "E", "F", "G", "H")
#: Famille de la PBO et du DSR depuis l'additif v1.1 (N = 9, D9).
FAMILY_V11: tuple[str, ...] = ("A", "B", "C", "D", "E", "F", "G", "H", "I")
#: Référence « indice discipliné » (D8), évaluée sur S1 comme essai REF-ID hors famille.
REFERENCE_VARIANT: str = "REF"

#: Règles d'événements pays (§4.3) reconnues dans ``country_events`` ou dans les étiquettes
#: des notes (``regle_pays:<règle>``). ``sessions`` : durée par défaut.
COUNTRY_RULES: dict[str, dict[str, Any]] = {
    "severe": {"sessions": 60, "rampback": 20, "cap_x_ref": 0.25, "no_buy": True,
               "label": "choc sévère (sanctions UEMOA/BCEAO, défaut, sortie de l'Union)"},
    "coup": {"sessions": 20, "cap_x_ref": 1.0, "no_buy": True, "label": "coup d'État sans sanctions"},
    "relief": {"sessions": 20, "cap_x_ref": 1.0, "no_buy": False, "label": "levée de sanctions ou accord avec le FMI"},
    "election": {"before": 30, "after": 10, "cap_x_ref": 1.0, "no_buy": False, "label": "élection présidentielle"},
    "downgrade": {"sessions": 120, "cap_mult": 0.75, "no_buy": False,
                  "label": "dégradation souveraine (≥ 2 crans) ou révélation budgétaire"},
    "bond_discount": {"sessions": None, "cap_mult": 0.75, "cap_x_ref": 1.0, "no_buy": False,
                      "label": "décote des obligations souveraines < 0,97"},
}
_RULE_ALIASES = {
    "sévère": "severe", "severe": "severe", "sanctions": "severe", "defaut": "severe", "défaut": "severe",
    "coup": "coup", "coup_etat": "coup", "coup_d_etat": "coup",
    "relief": "relief", "levee": "relief", "levée": "relief", "fmi": "relief",
    "election": "election", "élection": "election",
    "downgrade": "downgrade", "degradation": "downgrade", "dégradation": "downgrade", "fiscal": "downgrade",
    "bond_discount": "bond_discount", "decote_obligataire": "bond_discount", "décote_obligataire": "bond_discount",
}

_BLOCKING_NOTE_FLAGS = ("R1", "R2", "R3", "R5", "R9")
_INFO_FLAGS = ("R7", "R10")

_STATE_CACHE_SIZE = 4

#: Borne de l'inclinaison manuelle de l'analyste, en écarts-types du score (contrat des notes).
_TILT_MAX = 0.5


def notes_available() -> tuple[bool, str]:
    """``(True, "")`` si ``brvm_alpha.notes.signals`` s'importe, sinon ``(False, motif)``."""
    try:
        # ``import_module`` consulte ``sys.modules`` (une entrée ``None`` lève ImportError),
        # contrairement à ``from pkg import mod`` qui lit d'abord l'attribut du paquet.
        importlib.import_module("brvm_alpha.notes.signals")
    except ImportError as exc:  # module absent ou en cours d'écriture
        return False, f"module des notes indisponible ({exc.__class__.__name__} : {exc})"
    except Exception as exc:  # pragma: no cover - erreur à l'import d'un module tiers
        return False, f"module des notes inutilisable ({exc.__class__.__name__} : {exc})"
    return True, ""


# ---------------------------------------------------------------------------
# Construction des panels
# ---------------------------------------------------------------------------


def _pivot(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.pivot(index="date", columns="symbol", values=col).sort_index()


def build_panels(
    panel_dir: str | Path | None = None,
    *,
    order_book: bool = True,
    market_tr: bool = True,
    shares: bool = True,
    end: Any = None,
) -> dict[str, Any]:
    """Panels du moteur **et** de la stratégie à partir de ``data/panel/*.parquet``.

    Le dictionnaire renvoyé peut être passé tel quel à ``backtest.engine.Backtester`` (le
    moteur lit ``close`` ajusté, ``adj_factor``, ``volume``, ``value``, ``status``,
    ``dividend_net``, ``bid``/``ask``…) et à :class:`BrvmAlpha` (qui lit en plus
    ``close_raw``, ``close_adj``, ``tr_index``, ``split_factor``, ``stats_usable``,
    ``flags``, ``shares``, ``market_tr``, ``market``, ``dividends_table`` et
    ``corporate_actions``). Toutes les tables portent une colonne ``date`` = date à
    laquelle l'information était connue, pour que le moteur puisse les tronquer.

    ``end`` : dernière date conservée (troncature des panels larges, contrôles de forme).
    Hypothèses : nombre de titres et Composite TR **reconstruits** (spéc. §1.1) ; dates de
    connaissance des dividendes = première apparition au BOC (``first_seen``).

    Montants des dividendes (additif v1.1, D6) — interface entre signaux et moteur :

    * **signaux** (DY via ``last_div_net`` du BOC de t, S1 et S2 via ``dividends_table``) :
      montant **connu en t**. Dans ``dividends_table``, ``amount`` est le montant publié à la
      première apparition (ligne (d) le plus souvent) ; une correction ultérieure du BOC est
      portée à part (``amount_revised``, ``revised_seen``) et n'est lue qu'à partir de sa date
      de publication (5 cas : BOAM 2025, CIEC 2021, ETIT 2026, ONTBF 2017 et 2024) ;
    * **flux de trésorerie** du backtest : montant **corrigé** (meilleure estimation du
      versement réel), colonne ``amount_cashflow`` de ``dividends_table`` et panel
      ``dividend_net`` du moteur (``store.detect_dividends`` : le montant qui explique la
      baisse de la référence au détachement ; **hypothèse** à faire valider). L'écart total
      entre les deux est donné par :func:`dividend_amount_gap` (à publier, D6).
    """
    from brvm_alpha.data import store

    d = Path(panel_dir) if panel_dir is not None else DEFAULT_PANEL_DIR
    eq = store.load_equities(d)
    eq = eq.reset_index() if "symbol" not in eq.columns else eq.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    adj = pd.read_parquet(d / "adjusted_prices.parquet")
    adj["date"] = pd.to_datetime(adj["date"])
    div = pd.read_parquet(d / "dividends.parquet")
    if not {"amount_first", "revised_seen"} <= set(div.columns):
        # Fichier antérieur aux colonnes point-in-time : elles sont recalculées (même détection).
        try:
            det = store.detect_dividends(eq)[["symbol", "ex_date", "amount_first", "revised_seen"]]
            det["ex_date"] = pd.to_datetime(det["ex_date"])
            div = div.assign(ex_date=pd.to_datetime(div["ex_date"])).merge(det, on=["symbol", "ex_date"],
                                                                             how="left")
        except Exception as exc:  # pragma: no cover - panel incomplet
            warnings.warn(f"montants de dividendes point-in-time non recalculés : {exc}", stacklevel=2)
        for col, fill in (("amount_first", div["amount"]), ("revised_seen", pd.NaT)):
            if col not in div.columns:
                div[col] = fill
        div["amount_first"] = div["amount_first"].fillna(div["amount"])
    ca = pd.read_parquet(d / "corporate_actions.parquet")
    ob = pd.read_parquet(d / "order_book.parquet") if order_book and (d / "order_book.parquet").exists() else None
    close_adj = _pivot(adj.drop_duplicates(["date", "symbol"], keep="last"), "adj_close")
    P: dict[str, Any] = engine.panels_from_equities(eq, close=close_adj, dividends=div, corporate_actions=ca,
                                                     order_book=ob)
    fp = F.panels_for_signals(eq, adj)
    P["close_raw"] = fp["close"].astype(float)
    for k in ("close_adj", "tr_index", "split_factor", "missing_sessions"):
        if k in fp:
            P[k] = fp[k]
    eqd = eq.drop_duplicates(["date", "symbol"], keep="last")
    if "flags" in eqd.columns:
        P["flags"] = _pivot(eqd, "flags")
    if "ex_div" in eqd.columns:
        P["ex_div"] = _pivot(eqd, "ex_div").astype("boolean").fillna(False).astype(bool)
    try:
        P["stats_usable"] = store.stats_mask(d)
    except Exception as exc:  # pragma: no cover - panel incomplet
        warnings.warn(f"stats_mask indisponible : {exc}", stacklevel=2)
    if shares:
        try:
            P["shares"] = store.shares_outstanding_panel(d)
        except Exception as exc:  # pragma: no cover
            warnings.warn(f"nombre de titres indisponible : {exc}", stacklevel=2)
    if market_tr:
        try:
            P["market_tr"] = store.composite_tr_reconstructed(d).astype(float)
        except Exception as exc:  # pragma: no cover
            warnings.warn(f"Composite TR indisponible : {exc}", stacklevel=2)
    mk = store.load_market(d)
    mk = mk.reset_index() if "date" not in mk.columns else mk.copy()
    keep = [c for c in ("date", "avg_per", "risk_premium", "market_cap", "avg_yield_pct") if c in mk.columns]
    P["market"] = mk[keep].assign(date=lambda x: pd.to_datetime(x["date"])).sort_values("date").reset_index(drop=True)
    divt = div.copy()
    divt["ex_date"] = pd.to_datetime(divt["ex_date"])
    known = pd.to_datetime(divt["first_seen"]) if "first_seen" in divt.columns else divt["ex_date"]
    divt["date"] = known.fillna(divt["ex_date"])
    # Montant connu à ``date`` (première publication) ; la correction n'est visible qu'à ``revised_seen``.
    divt["revised_seen"] = pd.to_datetime(divt["revised_seen"])
    divt["amount_revised"] = divt["amount"].where(divt["revised_seen"].notna())
    divt["amount_cashflow"] = divt["amount"].astype(float)  # D6 : montant corrigé, crédité par le moteur
    divt["amount"] = divt["amount_first"].astype(float)  # D6 : montant connu à ``date`` (signaux)
    P["dividends_table"] = divt.sort_values(["date", "symbol"]).reset_index(drop=True)
    cat = ca.copy()
    cat["date"] = pd.to_datetime(cat["date"])
    P["corporate_actions"] = cat.drop(columns=[c for c in ("prev_date",) if c in cat.columns]).sort_values(
        ["date", "symbol"]).reset_index(drop=True)
    if end is not None:
        P = engine.truncate_asof(P, pd.Timestamp(end))
    return P


def dividend_amount_gap(panels: Mapping[str, Any]) -> pd.DataFrame:
    """Écart entre montants de dividende des signaux et des flux (additif v1.1, D6).

    Une ligne par dividende de ``panels["dividends_table"]`` (:func:`build_panels`) :
    ``amount_signal`` (montant connu à la date de connaissance : ligne (d) du BOC),
    ``amount_cashflow`` (montant corrigé crédité par le moteur), ``gap`` (= flux − signal,
    FCFA par action). ``attrs["total_gap_per_share"]`` et ``attrs["n_differences"]`` résument
    l'écart, à publier avec les résultats. Aucune performance n'est calculée.
    """
    tab = _get(panels, "dividends_table")
    cols = ["symbol", "ex_date", "date", "amount_signal", "amount_cashflow", "gap"]
    if not isinstance(tab, pd.DataFrame) or not len(tab) or "amount" not in tab.columns:
        out = pd.DataFrame(columns=cols)
        out.attrs.update({"total_gap_per_share": 0.0, "n_differences": 0})
        return out
    cash = tab["amount_cashflow"] if "amount_cashflow" in tab.columns else tab["amount"]
    out = pd.DataFrame({"symbol": tab["symbol"].astype(str), "ex_date": pd.to_datetime(tab["ex_date"]),
                        "date": pd.to_datetime(tab["date"]) if "date" in tab.columns else pd.NaT,
                        "amount_signal": tab["amount"].astype(float), "amount_cashflow": cash.astype(float)})
    out["gap"] = out["amount_cashflow"] - out["amount_signal"]
    out = out.reset_index(drop=True)
    diff = out["gap"].abs() > 1e-9
    out.attrs.update({"total_gap_per_share": float(out["gap"].sum()), "n_differences": int(diff.sum()),
                      "note": "D6 : signaux = montant connu en t (ligne (d)) ; flux = montant corrigé (hypothèse)"})
    return out


# ---------------------------------------------------------------------------
# Accès aux panels (dict ou PanelView)
# ---------------------------------------------------------------------------


def _get(panels: Any, key: str) -> Any:
    try:
        if key in panels:
            return panels[key]
    except TypeError:
        return None
    return None


def _as_ts(x: Any) -> pd.Timestamp:
    t = pd.Timestamp(x)
    if t.tzinfo is not None:
        t = t.tz_convert(None)
    return t


@dataclass
class _Data:
    """Données tronquées à la date de décision ``t`` (alignées sur un même index)."""

    t: pd.Timestamp
    index: pd.DatetimeIndex
    symbols: pd.Index
    wide: dict[str, pd.DataFrame]
    market_tr: pd.Series | None
    market: pd.DataFrame | None
    dividends: pd.DataFrame | None
    corporate_actions: pd.DataFrame | None
    country_events: pd.DataFrame | None
    dividend_calendar: pd.DataFrame | None
    messages: list[str] = field(default_factory=list)
    #: numéro global de séance de chaque ligne (calendrier des BOC), ``None`` s'il est inconnu
    sess: np.ndarray | None = None
    #: augmentations de capital connues en t (R5) : ``date, symbol, detachment_date, kind``
    capital_increases: pd.DataFrame | None = None

    def w(self, key: str) -> pd.DataFrame | None:
        return self.wide.get(key)

    def row(self, key: str) -> pd.Series | None:
        df = self.wide.get(key)
        if df is None or not len(df):
            return None
        return df.iloc[-1]


_WIDE_KEYS = ("close", "close_raw", "close_adj", "adj_factor", "tr_index", "volume", "value", "status", "per",
              "net_yield_pct", "last_div_net", "last_div_date", "ref_price", "change_pct", "split_factor",
              "missing_sessions", "multi_session", "stats_usable", "flags", "bid", "ask", "shares", "ex_div")


def _known_table(obj: Any, t: pd.Timestamp, *, date_candidates: Sequence[str]) -> pd.DataFrame | None:
    """Table longue restreinte aux lignes connues en ``t`` (colonne ``date`` ou repli)."""
    if obj is None:
        return None
    if not isinstance(obj, pd.DataFrame):
        obj = pd.DataFrame(obj)
    df = obj.copy()
    if "date" not in df.columns:
        for c in date_candidates:
            if c in df.columns:
                df["date"] = pd.to_datetime(df[c])
                break
        else:
            raise KeyError(f"table sans colonne de date (attendu : date ou {list(date_candidates)})")
    df["date"] = pd.to_datetime(df["date"])
    return df[df["date"].notna() & (df["date"] <= t)].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Résultat d'une décision
# ---------------------------------------------------------------------------


@dataclass
class AlphaDecision:
    """Décision complète à la date ``asof`` (voir :meth:`BrvmAlpha.decide`)."""

    asof: pd.Timestamp
    variant: str
    weights: pd.Series
    universe: pd.DataFrame
    signals: dict[str, pd.Series]
    risk: pd.DataFrame
    score: pd.DataFrame
    diagnostics: dict[str, Any]
    messages: list[str]

    def summary(self) -> dict[str, Any]:
        w = self.weights
        return {
            "asof": self.asof,
            "variant": self.variant,
            "mode": self.diagnostics.get("mode"),
            "n_eligible": int(self.universe["eligible"].sum()) if len(self.universe) else 0,
            "n_holdings": int((w > 0).sum()),
            "invested": float(w.sum()),
            "banner": BANNER,
        }


# ---------------------------------------------------------------------------
# Le modèle
# ---------------------------------------------------------------------------


class BrvmAlpha:
    """Modèle BRVM Alpha v1 (variantes pré-enregistrées A à I et référence REF, §3.4 et §8.4).

    Parameters
    ----------
    cfg
        (mot-clé, contrat de l'additif v1.1) ``PlatformConfig`` — alias de ``config`` — ou
        dictionnaire de paramètres de stratégie — alias de ``params`` ; ``None`` : défauts.
    config
        ``PlatformConfig`` (coûts, contraintes…) ; défaut :
        ``settings.apply_to_platform_config(params)`` (égal à ``PlatformConfig()`` sur le
        fichier livré).
    variant
        ``"A"`` (principal) … ``"H"``, ``"I"`` (cœur-satellite, D9) ou ``"REF"`` (indice
        discipliné, D8 : référence investissable, hors famille de la PBO).
    capital
        Capital K en FCFA (défaut : ``capital_fcfa_reference`` du YAML, 10 M) : il fixe le
        plancher U5 ``max(0,5 M ; 0,05·K)`` et les plafonds de liquidité.
    params
        Surcharges du YAML ``configs/strategy_v1.yaml`` (dict imbriqué fusionné en
        profondeur et validé par ``settings.load_strategy_config``). Toute surcharge d'un
        paramètre FIGÉ est un essai de plus à journaliser (§8.2).
    notes
        ``"auto"`` (défaut : ``NoteStore()`` du dépôt si le module s'importe), un
        ``NoteStore`` / ``DataFrame`` de notes, ou ``None`` (aucune note). Forcé à ``None``
        quand ``validation_s1=True`` (additif v1.1, D11 : ni veto ni inclinaison, S5 = 0).
    notes_known_at
        Instant de connaissance des notes (UTC) du **mode direct** : ``None`` (défaut, mode
        historique : règle stricte à la date de décision, aucune anticipation — backtests,
        validation, dates passées). Donné par le seul chemin « direct » (ordre de bataille,
        rapport, interface, à la dernière séance du panel) : les notes connues à cet instant
        sont appliquées à la séance qui suit la date de décision (``notes.signals``, en-tête).
        Sans effet sur les règles : seul change l'ensemble des notes transmises. Ignoré en
        validation S1 et pour une décision postérieure à cet instant.
    country_events
        Table ``date, country, rule`` (+ ``event_date``, ``end``, ``sessions``, ``label``)
        des règles d'événements pays (§4.3) ; ``date`` = date de l'annonce publique. ``None``
        (défaut) : chronologie de l'additif v1.1 (``reference.COUNTRY_EVENTS``, D10) ;
        ``False`` : aucune règle pays datée. Un événement est connu de la décision prise à la
        clôture de t s'il a été annoncé avant la séance d'exécution (t + 1) : l'action a lieu à
        la **première séance BOC qui suit l'annonce** (Mali, dimanche 09/01/2022 → 10/01/2022).
    dividend_calendar
        Avis de paiement de dividendes connus à l'avance (``date, symbol, ex_date,
        amount``) : poche S1 (variante E) et report des ventes (§5.2.6).
    history_start
        Date avant laquelle les **séries de performance** (spread du momentum, TR de marché
        pour le filtre de crash et le régime) sont ignorées. Sert à n'utiliser que
        l'échantillon autorisé (S0) dans les essais. ``None`` : tout l'historique **sauf**
        l'échantillon vierge S1 (début effectif ramené au 17/11/2022, signalé), à moins que
        ``validation_s1=True``.
    risk_overlay
        Règles de drawdown relatif du §9.1 (pré-enregistrées dans A) quand la valeur
        liquidative est connue (``PanelView.nav`` du moteur).
    defer_sales
        Report des ventes avant un détachement (§5.2.6) : ``None`` = actif seulement en
        mode événementiel (:meth:`strategy_fn` avec ``event_driven=True``), seul mode où la
        vente peut être exécutée le jour ex.
    sectors
        Table symbole -> secteur (défaut : classification BRVM 2025 de
        ``reference.SECTOR_2025``, appliquée à tout l'historique : hypothèse).
    payout_proxies
        Drapeaux R11 / R12 de payout estimés par ``DY brut × PER`` (approximation, faute de
        fondamentaux point-in-time). ``False`` : seuls les drapeaux exacts sont gardés
        (aucun dividende depuis 3 ans, DY > 15 %).
    window_basis
        Comptage des fenêtres glissantes (MOM, LOWVOL, U2, U3, MDV63, malus S2, tampon R1,
        spread 120) : ``"boc"`` (BOC disponibles, convention de l'annexe ``univ_breadth.py``)
        ou ``"sessions"`` (séances du calendrier des numéros de BOC ; voir
        ``quant.features.WINDOW_BASES``). ``None`` (défaut) : ``data.window_basis`` du YAML,
        soit ``"sessions"`` depuis l'additif v1.1 (D1), y compris avec ``validation_s1=True``.
        En base ``"sessions"`` : bornes de rendement au dernier cours disponible à 5 séances au
        plus, seuils ``m_eff = ⌈m × n_BOC_disponibles / L⌉`` avec un plancher de 40 (signaux)
        ou 20 (filtres d'univers).
    validation_s1
        ``False`` (défaut) : aucune série de performance (spread du momentum, TR de marché du
        filtre de crash et du régime) n'est calculée sur des dates de l'échantillon vierge S1
        (≤ 16/11/2022) : leur début effectif est ramené au début de S0 et c'est signalé.
        ``True`` : réservé à l'exécution **unique** et pré-enregistrée du test S1.
    capital_increases
        Augmentations de capital connues (avis) pour R5 (§5.6) : table ``date`` (annonce,
        date de connaissance), ``symbol``, ``detachment_date`` (détachement des droits),
        ``kind`` (``"cash"`` : numéraire, bloque les achats de l'annonce à la veille du
        détachement ; ``"bonus"`` : attribution gratuite, information seulement).
    memoire_ref
        État de la poche annuelle de REF repris d'un carnet (``{"annee": int, "date": date}``,
        option ``recommend --suivi``) : amorce ``_sleeves["ref"]`` comme le moteur l'aurait laissé
        après cette décision. ``None`` (défaut) : comportement inchangé. N'entre pas dans
        l'empreinte de configuration ; ``reset_state()`` l'oublie.
    """

    def __init__(
        self,
        config: PlatformConfig | None = None,
        variant: str = "A",
        capital: float | None = None,
        params: Mapping[str, Any] | None = None,
        *,
        notes: Any = "auto",
        notes_known_at: Any = None,
        country_events: pd.DataFrame | Iterable[Mapping[str, Any]] | None = None,
        dividend_calendar: pd.DataFrame | None = None,
        history_start: Any = None,
        risk_overlay: bool = True,
        defer_sales: bool | None = None,
        sectors: Mapping[str, str] | pd.Series | None = None,
        payout_proxies: bool = True,
        window_basis: str | None = None,
        validation_s1: bool = False,
        capital_increases: pd.DataFrame | Iterable[Mapping[str, Any]] | None = None,
        cfg: PlatformConfig | Mapping[str, Any] | None = None,
        memoire_ref: Mapping[str, Any] | None = None,
    ) -> None:
        # Contrat de l'additif v1.1 : ``cfg`` = ``PlatformConfig`` (alias de ``config``) ou dictionnaire
        # de paramètres de stratégie (alias de ``params`` : surcharges du YAML, validées).
        if cfg is not None:
            if isinstance(cfg, PlatformConfig):
                if config is not None:
                    raise ValueError("cfg et config désignent le même PlatformConfig : n'en passer qu'un")
                config = cfg
            elif isinstance(cfg, Mapping):
                if params is not None:
                    raise ValueError("cfg (dictionnaire de paramètres) et params : n'en passer qu'un")
                params = cfg
            else:
                raise TypeError("cfg doit être un PlatformConfig, un dictionnaire de paramètres ou None")
        code = str(variant).upper().strip()
        if code not in VARIANT_SPECS:
            raise ValueError(f"variante inconnue {variant!r} ; choix : {', '.join(VARIANTS)}")
        self.validation_s1 = bool(validation_s1)
        if self.validation_s1:
            notes = None  # additif v1.1, D11 : aucune note de l'analyste sur S1
        self.variant = code
        self.spec = VARIANT_SPECS[code]
        self.cfg = settings.load_strategy_config(overrides=params)
        self.config = config if config is not None else settings.apply_to_platform_config(self.cfg)
        cap_default = float(self.cfg.get("capital_fcfa_reference", self.config.capital_fcfa))
        if config is not None and capital is None:
            cap_default = float(config.capital_fcfa)
        self.capital = float(capital) if capital is not None else cap_default
        if self.capital <= 0:
            raise ValueError("capital doit être > 0")
        self.notes_source = notes
        #: instant de connaissance des notes (mode direct) ; None : mode historique (règle stricte)
        self.notes_known_at: Any = None if self.validation_s1 else notes_known_at
        self._store_cache: Any = None
        if country_events is None:  # additif v1.1, D10 : chronologie datée par défaut
            self.country_events = self._normalize_events(reference.COUNTRY_EVENTS)
            self.country_events_source = "reference.COUNTRY_EVENTS (additif v1.1, D10)"
        elif country_events is False:
            self.country_events = None
            self.country_events_source = "désactivés (country_events=False)"
        else:
            self.country_events = self._normalize_events(country_events)
            self.country_events_source = "table fournie"
        self.dividend_calendar = None if dividend_calendar is None else pd.DataFrame(dividend_calendar).copy()
        self.history_start = None if history_start is None else _as_ts(history_start)
        self.risk_overlay = bool(risk_overlay)
        self.defer_sales = defer_sales
        self.payout_proxies = bool(payout_proxies)
        self.sector_map = (pd.Series(sectors, dtype=object) if sectors is not None
                           else pd.Series(reference.SECTOR_2025, dtype=object))
        self.sector_map.index = self.sector_map.index.astype(str)
        self.portfolio_params = construct.portfolio_params(
            {**self.cfg, "capital": self.capital, "weighting": self.spec.weighting})
        # Additif v1.1, D1 : base « sessions » par défaut (clé data.window_basis du YAML), y compris
        # pour le test unique de S1.
        self.window_basis_explicit = window_basis is not None
        self.window_basis = F._check_basis(window_basis if window_basis is not None
                                           else settings.window_basis_default(self.cfg))
        self.window_params = settings.min_obs_prorata_params(self.cfg)
        self.capital_increases = self._normalize_capital_increases(capital_increases)
        self._s1_open: dict[tuple[str, pd.Timestamp], pd.Timestamp] = {}
        self._s1_meta: dict[tuple[str, pd.Timestamp], dict[str, Any]] = {}
        self._s1_journal: list[dict[str, Any]] = []
        self._s1_suspended: dict[str, Any] | None = None
        self._recording = False
        self._calendar: pd.DatetimeIndex | None = None
        self._nav: dict[pd.Timestamp, float] = {}
        #: dates de VL où le portefeuille détenait des titres (D5 : t0 = première d'entre elles)
        self._nav_invested: set[pd.Timestamp] = set()
        self._risk_state: dict[str, Any] = {"halved_since": None, "stopped": False, "alert": False,
                                            "index_year": None}
        #: état des poches annuelles : REF (``ref``), cœur de I (``core``), côté A de I (``a``)
        self._sleeves: dict[str, Any] = {"ref": None, "core": None, "a": None}
        if memoire_ref:
            self._sleeves["ref"] = {"year": int(memoire_ref["annee"]), "t": pd.Timestamp(memoire_ref["date"])}
        self._state_rev = 0
        self._mode_override: str | None = None
        self._cache: OrderedDict[tuple[Any, ...], AlphaDecision] = OrderedDict()
        self._event_mode = False
        self.last_decision: AlphaDecision | None = None

    # ------------------------------------------------------------------ outils

    def __repr__(self) -> str:
        return (f"BrvmAlpha(variant={self.variant!r}, capital={self.capital:,.0f} FCFA, "
                f"pondération={self.spec.weighting!r})")

    @property
    def fingerprint(self) -> str:
        """Empreinte des paramètres (registre des essais) : YAML, variante, capital, base des
        fenêtres, événements pays et statut des notes."""
        ev = self.country_events
        ev_key = None if ev is None else [(str(pd.Timestamp(r["date"]).date()), str(r["country"]), str(r["rule"]))
                                          for r in ev.to_dict("records")]
        return settings.config_fingerprint({**self.cfg, "_variant": self.variant, "_capital": self.capital,
                                            "_window_basis": self.window_basis, "_country_events": ev_key,
                                            "_notes": self.notes_source is not None and self.notes_source is not False,
                                            "_validation_s1": self.validation_s1})

    def mdv_floor(self) -> float:
        """Plancher U5 : ``max(500 000 ; 0,05 × K)`` FCFA (§2)."""
        floor, frac = settings.mdv_floor_params(self.cfg)
        return max(float(floor), float(frac) * self.capital)

    @staticmethod
    def _normalize_capital_increases(events: Any) -> pd.DataFrame | None:
        """Table des augmentations de capital (R5) : ``date, symbol, detachment_date, kind``."""
        if events is None:
            return None
        df = pd.DataFrame(list(events)) if not isinstance(events, pd.DataFrame) else events.copy()
        if not len(df):
            return None
        need = {"date", "symbol", "detachment_date"}
        if not need <= set(df.columns):
            raise KeyError(f"capital_increases : colonnes attendues {sorted(need)} (+ kind)")
        df["date"] = pd.to_datetime(df["date"])
        df["detachment_date"] = pd.to_datetime(df["detachment_date"])
        df["symbol"] = df["symbol"].astype(str).str.upper()
        kind = df["kind"] if "kind" in df.columns else pd.Series("cash", index=df.index)
        df["kind"] = kind.fillna("cash").astype(str).str.lower()
        bad = sorted(set(df["kind"]) - {"cash", "bonus"})
        if bad:
            raise ValueError(f"capital_increases : kind inconnu {bad} (choix : cash, bonus)")
        return df.sort_values("date").reset_index(drop=True)

    @staticmethod
    def _normalize_events(events: Any) -> pd.DataFrame | None:
        if events is None:
            return None
        df = pd.DataFrame(list(events)) if not isinstance(events, pd.DataFrame) else events.copy()
        if not len(df):
            return None
        need = {"date", "country", "rule"}
        if not need <= set(df.columns):
            raise KeyError(f"country_events : colonnes attendues {sorted(need)}")
        df["date"] = pd.to_datetime(df["date"])
        df["rule"] = [_RULE_ALIASES.get(str(r).strip().lower(), str(r).strip().lower()) for r in df["rule"]]
        bad = sorted(set(df["rule"]) - set(COUNTRY_RULES))
        if bad:
            raise ValueError(f"règles pays inconnues : {bad} ; choix : {sorted(COUNTRY_RULES)}")
        df["country"] = df["country"].astype(str).str.upper().str.replace("PAYS:", "", regex=False)
        return df.sort_values("date").reset_index(drop=True)

    def _next_session(self, t: Any) -> pd.Timestamp:
        """Séance d'exécution d'une décision prise à la clôture de ``t`` (calendrier publié des
        séances s'il est connu, sinon jour ouvré suivant)."""
        t = pd.Timestamp(t).normalize()
        cal = self._calendar
        if cal is not None and len(cal) and cal[0] <= t:
            pos = int(cal.searchsorted(t, side="right"))
            if pos < len(cal):
                return pd.Timestamp(cal[pos]).normalize()
        return pd.Timestamp(t + pd.offsets.BDay(1)).normalize()

    def _events_known(self, events: pd.DataFrame, t: Any) -> pd.DataFrame:
        """Événements pays connus de la décision de ``t`` (additif v1.1, D10).

        Un événement daté de son annonce publique est pris en compte par la décision dont
        l'exécution a lieu à la **première séance qui suit l'annonce** : annonce strictement
        antérieure à la séance d'exécution ``t + 1`` (un dimanche 09/01/2022 est connu de la
        décision du vendredi 07/01, exécutée le lundi 10/01). Une date qui tombe un jour de
        séance (notes : première séance négociable) n'est connue qu'à partir de ce jour.
        """
        if events is None or not len(events):
            return events
        nxt = self._next_session(t)
        dates = pd.to_datetime(events["date"]).dt.normalize()
        return events[dates < nxt]

    # ------------------------------------------------------------- préparation

    def _prepare(self, panels: Any, asof: Any) -> _Data:
        t_req = _as_ts(asof)
        if t_req.hour == 0 and t_req.minute == 0:
            t_req = t_req + pd.Timedelta(hours=23, minutes=59, seconds=59)
        raw: dict[str, Any] = {}
        for k in _WIDE_KEYS:
            obj = _get(panels, k)
            if obj is None:
                continue
            obj = engine.truncate_asof(obj, t_req)
            if isinstance(obj, pd.DataFrame):
                raw[k] = obj
        messages: list[str] = []
        if "close_raw" in raw:
            close_raw = raw["close_raw"]
        elif "close" in raw and "adj_factor" in raw:
            close_raw = raw["close"] / raw["adj_factor"].reindex_like(raw["close"])
        elif "close" in raw:
            close_raw = raw["close"]
            messages.append("clôture brute absente : 'close' supposé non ajusté (contrôle de forme)")
        else:
            raise KeyError("panels : 'close_raw' ou 'close' requis")
        close_raw = close_raw.astype(float).sort_index()
        index = pd.DatetimeIndex(close_raw.index)
        if not len(index):
            raise ValueError(f"aucune séance avant le {t_req.date()}")
        symbols = pd.Index(sorted(map(str, close_raw.columns)))
        wide: dict[str, pd.DataFrame] = {}

        def align(df: pd.DataFrame) -> pd.DataFrame:
            out = df.copy()
            out.columns = out.columns.astype(str)
            return out.reindex(index=index, columns=symbols)

        wide["close_raw"] = align(close_raw)
        if "close_adj" in raw:
            wide["close_adj"] = align(raw["close_adj"]).astype(float)
        elif "close" in raw and "adj_factor" in raw:
            # Cours ajusté du moteur ramené aux unités du jour t (aucune division future visible).
            af = align(raw["adj_factor"]).apply(pd.to_numeric, errors="coerce").astype(float)
            af_last = af.ffill().iloc[-1].where(lambda x: x > 0).fillna(1.0)
            wide["close_adj"] = align(raw["close"]).astype(float) / af_last
        else:
            wide["close_adj"] = wide["close_raw"]
        if "tr_index" in raw:
            wide["tr_index"] = align(raw["tr_index"]).astype(float)
        else:
            wide["tr_index"] = wide["close_adj"]
            messages.append("tr_index absent : momentum et volatilité calculés sur les cours ajustés, sans "
                            "réinvestissement des dividendes (approximation)")
        for k in ("volume", "value", "per", "net_yield_pct", "last_div_net", "ref_price", "change_pct",
                  "split_factor", "missing_sessions", "bid", "ask", "shares"):
            if k in raw:
                wide[k] = align(raw[k]).apply(pd.to_numeric, errors="coerce").astype(float)
        for k in ("status", "flags", "last_div_date", "multi_session", "stats_usable", "ex_div"):
            if k in raw:
                wide[k] = align(raw[k])
        # Point-in-time : facteur de division relatif au dernier jour de la vue (1 en t) et
        # cours ajusté aux unités de t. Un panel ajusté « à rebours » (produit des divisions
        # FUTURES) ne doit jamais être lu en niveau.
        if "split_factor" in wide:
            sf_last = wide["split_factor"].ffill().iloc[-1].where(lambda x: x > 0).fillna(1.0)
            wide["split_factor"] = wide["split_factor"] / sf_last
            if "close_adj" in raw:
                wide["close_adj"] = wide["close_adj"] * sf_last
        if "status" not in wide:
            listed = wide["close_raw"].notna()
            vol = wide.get("volume")
            traded = listed & (vol.fillna(0.0) > 0) if vol is not None else listed
            st = np.full(traded.shape, None, dtype=object)
            st[listed.to_numpy()] = "not_traded"
            st[traded.to_numpy()] = "traded"
            wide["status"] = pd.DataFrame(st, index=index, columns=symbols)
            messages.append("statut absent : déduit du volume (aucune suspension détectable)")
        t = index[-1]

        mtr = _get(panels, "market_tr")
        market_tr = None
        if isinstance(mtr, pd.Series):
            market_tr = engine.truncate_asof(mtr, t_req).astype(float).sort_index()
        elif isinstance(mtr, pd.DataFrame) and mtr.shape[1] >= 1:
            market_tr = engine.truncate_asof(mtr, t_req).iloc[:, 0].astype(float).sort_index()
        market = _get(panels, "market")
        market = _known_table(engine.truncate_asof(market, t_req), t, date_candidates=()) if isinstance(
            market, pd.DataFrame) and "date" in market.columns else None
        divs = _get(panels, "dividends_table")
        if divs is None:
            cand = _get(panels, "dividends")
            divs = cand if isinstance(cand, pd.DataFrame) and "ex_date" in getattr(cand, "columns", []) else None
        dividends = _known_table(divs, t, date_candidates=("first_seen", "ex_date")) if divs is not None else None
        if dividends is not None and len(dividends) and "amount_revised" in dividends.columns:
            # Correction du montant par un BOC ultérieur : visible seulement à partir de sa publication.
            rs = pd.to_datetime(dividends.get("revised_seen"), errors="coerce")
            use = dividends["amount_revised"].notna() & rs.notna() & (rs <= t)
            dividends["amount"] = np.where(use, dividends["amount_revised"], dividends["amount"])
        ca = _get(panels, "corporate_actions")
        corporate_actions = _known_table(ca, t, date_candidates=()) if isinstance(ca, pd.DataFrame) else None
        ev_tables = []
        for src in (self.country_events, self._normalize_events(_get(panels, "country_events"))):
            if src is not None:
                ev_tables.append(self._events_known(src, t))
        country_events = pd.concat(ev_tables, ignore_index=True) if ev_tables else None
        cal_tables = []
        for src in (self.dividend_calendar, _get(panels, "dividend_calendar")):
            if isinstance(src, pd.DataFrame) and len(src):
                cal_tables.append(_known_table(src, t, date_candidates=("known_from", "announced")))
        dividend_calendar = pd.concat(cal_tables, ignore_index=True) if cal_tables else None
        sess = None
        sess_obj = _get(panels, "session_no")
        if isinstance(sess_obj, (pd.DataFrame, pd.Series)):
            sess = F.session_numbers({"session_no": engine.truncate_asof(sess_obj, t_req)}, like=wide["close_raw"])
        elif "missing_sessions" in wide:
            sess = F.session_numbers({"missing_sessions": wide["missing_sessions"]}, like=wide["close_raw"])
        if self.window_basis == "sessions" and sess is None:
            messages.append("fenêtres « en séances » demandées mais numéros de BOC absents (session_no) : "
                            "fenêtres comptées en lignes du panel")
        ci_tables = []
        for src in (self.capital_increases, self._normalize_capital_increases(_get(panels, "capital_increases"))):
            if src is not None and len(src):
                ci_tables.append(src[src["date"] <= t])
        capital_increases = pd.concat(ci_tables, ignore_index=True) if ci_tables else None
        return _Data(t=t, index=index, symbols=symbols, wide=wide, market_tr=market_tr, market=market,
                     dividends=dividends, corporate_actions=corporate_actions, country_events=country_events,
                     dividend_calendar=dividend_calendar, messages=messages, sess=sess,
                     capital_increases=capital_increases)

    def _feature_panels(self, d: _Data) -> dict[str, pd.DataFrame]:
        """Panels au format de ``quant.features`` (``close`` = clôture **brute**)."""
        fp: dict[str, pd.DataFrame] = {"close": d.wide["close_raw"], "close_adj": d.wide["close_adj"],
                                       "tr_index": d.wide["tr_index"]}
        for k in ("volume", "value", "status", "per", "net_yield_pct", "last_div_net", "last_div_date",
                  "ref_price", "change_pct", "split_factor", "missing_sessions", "multi_session"):
            if d.w(k) is not None:
                fp[k] = d.wide[k]
        if d.w("stats_usable") is not None:
            fp["stats_usable"] = d.wide["stats_usable"].astype("boolean").fillna(False).astype(bool)
        if d.sess is not None:
            fp["session_no"] = pd.Series(d.sess, index=d.index, name="session_no")  # type: ignore[assignment]
        return fp

    def _grid_sess(self, d: _Data) -> np.ndarray | None:
        """Numéros de séance si les fenêtres sont comptées en séances (``window_basis``), sinon ``None``."""
        return d.sess if self.window_basis == "sessions" else None

    def _roll(self, d: _Data, df: pd.DataFrame, fn: Callable[[pd.DataFrame], pd.DataFrame]) -> pd.DataFrame:
        """Fenêtre glissante comptée selon ``window_basis`` (BOC disponibles ou séances)."""
        return F.on_session_grid(df, self._grid_sess(d), fn)

    def _window_start(self, d: _Data, n: int) -> int:
        """Première ligne des ``n`` dernières séances (base « sessions », D1) ou lignes (base « boc »)."""
        T = len(d.index)
        gs = self._grid_sess(d)
        if gs is None or not T:
            return max(0, T - int(n))
        return int(np.searchsorted(np.asarray(gs), int(gs[T - 1]) - int(n) + 1, side="left"))

    def _bound_row(self, d: _Data, lag: int) -> int | None:
        """Ligne de la borne ``t − lag`` séances : dernière ligne à cette séance ou avant, à 5 séances
        au plus (D1) ; ``None`` sinon. Base « boc » : ``T − 1 − lag`` lignes."""
        T = len(d.index)
        gs = self._grid_sess(d)
        if gs is None:
            r = T - 1 - int(lag)
            return r if r >= 0 else None
        target = int(gs[T - 1]) - int(lag)
        r = int(np.searchsorted(np.asarray(gs), target, side="right")) - 1
        if r < 0 or target - int(gs[r]) > int(self.window_params["max_stale"]):
            return None
        return r

    def _window_note(self, d: _Data) -> str | None:
        """Message si des BOC manquent dans la fenêtre de 126 lignes (lecture « BOC » signalée)."""
        if d.sess is None or len(d.sess) < 2:
            return None
        n = min(126, len(d.sess))
        span = int(d.sess[-1] - d.sess[-n]) + 1
        if span <= n:
            return None
        if self.window_basis == "boc":
            return (f"fenêtres comptées en BOC disponibles (lecture v1.0) : les {n} dernières lignes couvrent {span} "
                    f"séances ({span - n} BOC manquants) ; l'additif v1.1 (D1) retient window_basis='sessions'")
        miss = int(F.missing_sessions_in_window(d.sess, 126)[-1])
        if miss <= 0:
            return None
        return (f"fenêtres comptées en séances (additif v1.1, D1) : {miss} BOC manquants dans les 126 dernières "
                "séances ; seuils minimaux au prorata des BOC disponibles (planchers 40 / 20), bornes de "
                "rendement à 5 séances au plus")

    # ---------------------------------------------------------------- univers

    def _thr(self, d: _Data, window: int, min_obs: int, kind: str = "filter") -> pd.Series | int:
        """Seuil minimal d'observations au prorata des BOC disponibles (additif v1.1, D1).

        ``kind="filter"`` : plancher de 20 (univers) ; ``"signal"`` : plancher de 40. Seuil
        constant ``m`` en base ``"boc"`` (aucune séance manquante dans une fenêtre de lignes).
        """
        floor = self.window_params["filter_floor" if kind == "filter" else "signal_floor"]
        return F.min_obs_thresholds(self._grid_sess(d), int(window), int(min_obs), int(floor), index=d.index)

    @staticmethod
    def _ge(df: pd.DataFrame, thr: pd.Series | int) -> pd.DataFrame:
        return df.ge(thr, axis=0) if isinstance(thr, pd.Series) else df >= thr

    def _universe_frames(self, d: _Data) -> dict[str, pd.DataFrame]:
        """Composantes U1-U9 sur tout l'historique tronqué (date × symbole).

        Base « sessions » (additif v1.1, D1) : fenêtres de 63, 120 et 60 séances du calendrier
        des BOC ; seuils au prorata des BOC disponibles (plancher 20) ; historique U2 compté en
        séances cotées, un BOC manquant entre deux cotations comptant comme une séance cotée
        (« un BOC manquant est une perte de nos données, pas une absence de cotation »).
        """
        u = self.cfg["universe"]
        status = d.wide["status"]
        close = d.wide["close_raw"]
        listed = status.notna() & close.notna()
        susp = status.eq("suspended").fillna(False).astype(bool) if hasattr(status, "eq") else listed & False
        vol = d.w("volume")
        traded = listed & (vol.fillna(0.0) > 0) if vol is not None else listed & status.eq("traded")
        gs = self._grid_sess(d)
        n_hist = listed.astype(float).cumsum()  # « séances cotées » : BOC où le titre figure
        if gs is not None and len(gs) > 1:
            gap = np.r_[0, np.diff(np.asarray(gs, dtype=np.int64)) - 1].astype(float)
            both = (listed & listed.shift(1, fill_value=False)).to_numpy(dtype=bool)
            extra = np.where(both, gap[:, None], 0.0)
            n_hist = pd.DataFrame(listed.to_numpy(dtype=float) + extra, index=d.index, columns=d.symbols).cumsum()
        tr = d.wide["tr_index"]
        ret_ok = (tr.notna() & tr.shift(1).notna() & ~susp & listed).astype(float)
        # Fenêtres (63, 120, 60 et tampon R1) comptées selon ``window_basis`` : BOC disponibles,
        # ou séances du calendrier (un BOC manquant n'apporte ni rendement ni échange).
        n_ret63 = self._roll(d, ret_ok, lambda x: x.rolling(63, min_periods=1).sum()).fillna(0.0)
        thr63 = self._thr(d, 63, int(u["min_obs_63"]))
        tl = traded.astype(float).where(listed)
        frac_raw = self._roll(d, tl, lambda x: x.rolling(120, min_periods=1).mean())
        n120 = self._roll(d, tl, lambda x: x.rolling(120, min_periods=1).count())
        thr120 = self._thr(d, 120, 60)
        frac120 = frac_raw.where(self._ge(n120, thr120))
        value = d.w("value")
        if value is None:
            mdv63 = pd.DataFrame(np.nan, index=d.index, columns=d.symbols)
            mdv60 = mdv63
        else:
            v0 = value.where(traded, 0.0).where(listed)
            med63 = self._roll(d, v0, lambda x: x.rolling(63, min_periods=1).median())
            cnt63 = self._roll(d, v0, lambda x: x.rolling(63, min_periods=1).count())
            mdv63 = med63.where(self._ge(cnt63, self._thr(d, 63, 40)))
            med60 = self._roll(d, v0, lambda x: x.rolling(60, min_periods=1).median())
            cnt60 = self._roll(d, v0, lambda x: x.rolling(60, min_periods=1).count())
            mdv60 = med60.where(self._ge(cnt60, self._thr(d, 60, 40)))
        buf = int(u.get("resume_buffer_sessions", 5))
        if buf > 0:
            prior = self._roll(d, susp.astype(float), lambda x: x.shift(1).rolling(buf, min_periods=1).max())
            recent = prior.fillna(0.0) > 0
        else:
            recent = susp & False
        u1 = listed & ~susp & ~recent
        u2 = (n_hist >= int(u["min_history_sessions"])) & self._ge(n_ret63, thr63)
        u3 = frac120 >= float(u["min_traded_fraction_120"])
        # U4 : flottant d'après le dernier avis utilisable à chaque date (inconnu = admis, signalé).
        ff = pd.DataFrame(np.nan, index=d.index, columns=d.symbols)
        for src, vals in reference.FREE_FLOAT_HISTORY:
            rows = d.index >= pd.Timestamp(src.available_from)
            if rows.any():
                ff.loc[rows] = pd.Series(vals, dtype=float).reindex(d.symbols).to_numpy()[None, :]
        u4 = ~(ff < float(u["min_free_float"]))
        u5 = mdv63 >= self.mdv_floor()
        stale = pd.DataFrame(False, index=d.index, columns=d.symbols)
        max_age = int(u["stale_financials_days"])
        for sym, rec in reference.LAST_ANNUAL_ACCOUNTS.items():
            if sym in stale.columns:
                age = (d.index - pd.Timestamp(rec.fiscal_year_end)).days
                stale[sym] = (d.index >= pd.Timestamp(rec.published)) & (age > max_age)
        u9 = ~stale
        eligible = u1 & u2 & u3 & u4 & u5 & u9
        thr63_df = pd.DataFrame(np.broadcast_to(np.asarray(thr63, dtype=float).reshape(-1, 1) if isinstance(
            thr63, pd.Series) else float(thr63), listed.shape), index=d.index, columns=d.symbols)
        return {"listed": listed, "suspended": susp, "recent_suspension": recent, "traded": traded,
                "n_hist": n_hist, "n_ret63": n_ret63, "thr_ret63": thr63_df, "frac120": frac120, "mdv63": mdv63,
                "mdv60": mdv60,
                "free_float": ff, "stale": stale, "u1": u1, "u2": u2, "u3": u3, "u4": u4, "u5": u5, "u9": u9,
                "eligible": eligible}

    def _median_spread(self, d: _Data) -> pd.Series | None:
        bid, ask = d.w("bid"), d.w("ask")
        if bid is None or ask is None:
            return None
        if self._grid_sess(d) is None:
            hs = engine.quoted_half_spread(bid, ask, window=120, min_obs=20, lag=0)
            return (2.0 * hs.iloc[-1]).reindex(d.symbols) if len(hs) else None
        # Spread médian sur les 120 dernières SÉANCES (BOC manquants : aucune observation).
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = (ask - bid) / (0.5 * (ask + bid))
        rel = rel.where((bid > 0) & (ask > 0) & (ask >= bid) & np.isfinite(rel))
        med = self._roll(d, rel, lambda x: x.rolling(120, min_periods=20).median())
        return med.iloc[-1].reindex(d.symbols) if len(med) else None

    def _universe_table(self, d: _Data, fr: dict[str, pd.DataFrame]) -> pd.DataFrame:
        u = self.cfg["universe"]
        last = {k: v.iloc[-1] for k, v in fr.items()}
        syms = d.symbols
        spread = self._median_spread(d)
        floor = self.mdv_floor()
        low_tier = float(u["low_liquidity_tier_fcfa"])
        max_spread = float(u["max_spread_full_weight"])
        first_dates = fr["listed"].idxmax().where(fr["listed"].any())
        panel_start = d.index[0]
        rows = []
        for s in syms:
            listed = bool(last["listed"][s])
            codes: list[str] = []
            texts: list[str] = []
            if not listed:
                codes.append("U1")
                texts.append("U1 : absent du BOC de la date (non coté ou radié)")
            elif bool(last["suspended"][s]):
                codes.append("U1")
                texts.append("U1 : suspendu (SP) à la date")
            elif bool(last["recent_suspension"][s]):
                codes.append("U1")
                texts.append("U1 : reprise après suspension depuis moins de "
                             f"{int(u['resume_buffer_sessions'])} séances (R1)")
            n_hist = float(last["n_hist"][s])
            n63 = float(last["n_ret63"][s])
            if listed and not bool(last["u2"][s]):
                fd = first_dates.get(s)
                ipo = fd is not pd.NaT and fd is not None and pd.notna(fd) and fd > panel_start + pd.Timedelta(days=10)
                if ipo and n_hist < int(u["min_history_sessions"]):
                    codes.append("U8")
                    texts.append(f"U8 : introduction récente ({int(n_hist)} séances cotées < "
                                 f"{int(u['min_history_sessions'])}) : hors du moteur factoriel")
                else:
                    codes.append("U2")
                    thr = int(last["thr_ret63"][s])
                    texts.append(f"U2 : historique insuffisant ({int(n_hist)} séances cotées, {int(n63)} rendements "
                                 f"sur 63 séances ; minimum {int(u['min_history_sessions'])} et {thr}"
                                 + (f" (seuil {int(u['min_obs_63'])} au prorata des BOC disponibles)"
                                    if thr != int(u["min_obs_63"]) else "") + ")")
            frac = float(last["frac120"][s]) if pd.notna(last["frac120"][s]) else float("nan")
            if listed and not bool(last["u3"][s]):
                codes.append("U3")
                texts.append(f"U3 : cours périmés ({_pct(frac)} des 120 séances échangées < "
                             f"{_pct(float(u['min_traded_fraction_120']))})")
            ffv = float(last["free_float"][s]) if pd.notna(last["free_float"][s]) else float("nan")
            if listed and not bool(last["u4"][s]):
                codes.append("U4")
                texts.append(f"U4 : flottant {_pct(ffv, 2)} < {_pct(float(u['min_free_float']))} (dernier avis publié)")
            mdv = float(last["mdv63"][s]) if pd.notna(last["mdv63"][s]) else float("nan")
            if listed and not bool(last["u5"][s]):
                codes.append("U5")
                texts.append(f"U5 : MDV63 {_fcfa(mdv)} < plancher de capacité {_fcfa(floor)} "
                             f"(K = {_fcfa(self.capital)})")
            if listed and bool(last["stale"][s]):
                codes.append("U9")
                texts.append(f"U9 : comptes annuels périmés (> {int(u['stale_financials_days'])} jours)")
            sp = float(spread[s]) if spread is not None and pd.notna(spread.get(s)) else float("nan")
            rows.append({
                "symbol": s,
                "eligible": not codes,
                "reason": texts[0] if texts else "",
                "codes": ",".join(codes),
                "reasons": " ; ".join(texts),
                "listed": listed,
                "status": d.wide["status"].iloc[-1].get(s),
                "n_sessions": int(n_hist),
                "n_returns_63": int(n63),
                "traded_fraction_120": frac,
                "free_float": ffv,
                "free_float_known": pd.notna(ffv),
                "mdv63": mdv,
                "mdv60": float(last["mdv60"][s]) if pd.notna(last["mdv60"][s]) else float("nan"),
                "mdv_floor": floor,
                "low_liquidity": bool(pd.notna(mdv) and mdv < low_tier),
                "spread_120": sp,
                "wide_spread": bool(pd.notna(sp) and sp > max_spread),
                "liquidity_level": "C" if (pd.notna(mdv) and mdv < low_tier) else ("B" if pd.notna(mdv) else ""),
                "stale_financials": bool(last["stale"][s]),
                "country": reference.country_of(s),
                "sector": self.sector_map.get(s),
            })
        tab = pd.DataFrame(rows).set_index("symbol")
        n = int(tab["eligible"].sum())
        min_names = int(u["min_names_for_selection"])
        mode = "vide" if n == 0 else ("repli" if n < min_names else "selection")
        tab.attrs.update({"asof": d.t, "n_eligible": n, "mode": mode, "mdv_floor": floor, "capital": self.capital,
                          "spread_available": spread is not None,
                          "free_float_known": bool(tab.loc[tab["listed"], "free_float_known"].any())})
        if mode == "repli":
            tab.attrs["message"] = (f"U10 : {n} titres éligibles < {min_names} : mode repli (panier équipondéré des "
                                    "éligibles ; fait de marché, pas un défaut du modèle)")
        return tab

    def universe(self, asof: Any, panels: Any) -> pd.DataFrame:
        """Univers éligible U1-U10 à la date ``asof`` (§2), une ligne par titre.

        Colonnes : ``eligible``, ``reason`` (premier filtre non satisfait, en français),
        ``codes`` / ``reasons`` (tous les filtres non satisfaits), ``n_sessions``,
        ``n_returns_63``, ``traded_fraction_120`` (U3), ``free_float`` (U4 ; NaN si
        aucun avis n'était publié à la date : le filtre n'est alors pas appliqué),
        ``mdv63`` et ``mdv_floor`` (U5), ``low_liquidity`` / ``liquidity_level`` (U6,
        niveau « C » : poids maximal ÷ 2), ``spread_120`` / ``wide_spread`` (U7),
        ``stale_financials`` (U9), ``country``, ``sector``. ``attrs`` : ``n_eligible``,
        ``mode`` (``selection`` / ``repli`` (U10) / ``vide``).
        """
        d = self._prepare(panels, asof)
        return self._universe_table(d, self._universe_frames(d))

    # ---------------------------------------------------------------- signaux

    def _blocks(self, d: _Data, fp: dict[str, pd.DataFrame], elig_hist: pd.DataFrame) -> tuple[
            dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
        sig = self.cfg.get("signals", {})
        sub = lambda k: sig.get(k) if isinstance(sig.get(k), Mapping) else None  # noqa: E731
        eps = self.cfg.get("data", {}).get("eps_override")
        sf = d.w("split_factor")
        dyd = F.dy_signal_details(fp, split_factor=sf, params=sub("dy"))
        wb = self.window_basis
        # Additif v1.1, D1 : bornes à 5 séances au plus, seuils au prorata (plancher 40).
        mk = {"window_basis": wb, "obs_floor": self.window_params["signal_floor"],
              "max_stale_sessions": self.window_params["max_stale"]}
        blocks = {
            "ep": F.ep_signal(fp, eps_override=eps, split_factor=sf, params=sub("ep")),
            "dy": dyd["dy"],
            "mom6_1": F.mom6_1(fp, params=sub("mom6_1"), **mk),
            "lowvol": F.lowvol(fp, params=sub("lowvol"), window_basis=wb, obs_floor=mk["obs_floor"]),
            "quality_proxy": F.quality_proxy(fp, universe=elig_hist, eps_override=eps, split_factor=sf,
                                             params=sub("quality_proxy")),
            "mom3_1": F.mom3_1(fp, params=sub("mom3_1"), **mk),
            "mom6_0": F.mom6_0(fp, params=sub("mom6_0"), **mk),
            "mom12_1": F.mom12_1(fp, params=sub("mom12_1"), **mk),
            "mom12_7": F.mom12_7(fp, params=sub("mom12_7"), **mk),
        }
        if fp.get("value") is not None and (fp.get("status") is not None or fp.get("volume") is not None):
            blocks["amihud"] = F.amihud_signal(fp, params=sub("amihud"))
        return blocks, dyd

    def _performance_start(self) -> tuple[pd.Timestamp | None, str | None]:
        """Début effectif des séries de performance (spread du momentum, TR de marché).

        Hors ``validation_s1``, l'échantillon vierge S1 (≤ 16/11/2022) n'est jamais utilisé :
        le début est ``max(history_start, début de S0)``.
        """
        hs = self.history_start
        if self.validation_s1:
            return hs, None
        s0 = pd.Timestamp(S0_START)
        if hs is None or hs < s0:
            return s0, ("séries de performance des modulateurs (spread du momentum, TR de marché) restreintes à "
                        f"S0 (≥ {s0:%d/%m/%Y}) : échantillon vierge S1 protégé ; validation_s1=True est réservé au "
                        "test pré-enregistré")
        return hs, None

    def _momentum_multiplier(self, d: _Data, fp: dict[str, pd.DataFrame], mom: pd.DataFrame,
                             elig_hist: pd.DataFrame) -> dict[str, Any]:
        comp = self.cfg.get("composite", {})
        hs, guard = self._performance_start()
        out: dict[str, Any] = {"vol_scaling": 1.0, "crash_filter": 1.0, "multiplier": 1.0, "history_start": hs}
        if guard:
            out["s1_guard"] = guard
        if hs is not None and d.t < hs:
            out["s1_guard"] = ("décision antérieure au début des séries de performance autorisées "
                               f"({hs:%d/%m/%Y}) : modulateurs du momentum neutres (multiplicateur 1), aucune "
                               "performance calculée")
            out["multiplier"] = 1.0
            return out
        gs = self._grid_sess(d)
        sess_s = pd.Series(gs, index=d.index) if gs is not None else None  # D1 : fenêtres en séances
        floor = self.window_params["signal_floor"]
        try:
            if hs is not None:
                rows = d.index >= hs
                fps = {k: v.loc[rows] for k, v in fp.items()}
                spread = F.momentum_spread_returns(fps, mom=mom.loc[rows], universe=elig_hist.loc[rows])
            else:
                spread = F.momentum_spread_returns(fp, mom=mom, universe=elig_hist)
            vs = F.vol_scaling(spread, history_start=hs, params=comp.get("momentum_vol_scaling"), sess=sess_s,
                               obs_floor=floor)
            out["vol_scaling"] = float(vs.iloc[-1]) if len(vs) else 1.0
        except Exception as exc:  # garde-fou : modulateur neutre, signalé
            out["vol_scaling_error"] = f"{exc.__class__.__name__} : {exc}"
        if d.market_tr is not None and len(d.market_tr) > 2:
            try:
                mtr = d.market_tr if hs is None else d.market_tr[d.market_tr.index >= hs]
                cf = F.crash_filter(mtr, history_start=hs, params=comp.get("momentum_crash_filter"), sess=sess_s,
                                    obs_floor=floor)
                val = cf.reindex(cf.index.union([d.t])).ffill().get(d.t)
                out["crash_filter"] = float(val) if val is not None and np.isfinite(val) else 1.0
            except Exception as exc:
                out["crash_filter_error"] = f"{exc.__class__.__name__} : {exc}"
        else:
            out["crash_filter_note"] = "Composite TR absent : filtre de crash non évalué (multiplicateur 1)"
        out["multiplier"] = float(np.clip(out["vol_scaling"] * out["crash_filter"], 0.0, 1.0))
        return out

    def _s2_malus(self, d: _Data) -> tuple[pd.Series, dict[str, Any]]:
        """Malus S2 en t : −0,5 écart-type pendant 20 séances à partir du jour ex (§5.2.5)."""
        comp = self.cfg.get("composite", {})
        pen = float(comp.get("s2_post_ex_penalty_sd", -0.5))
        n = int(comp.get("s2_sessions", 20))
        mal = pd.Series(0.0, index=d.symbols, name="S2")
        info: dict[str, Any] = {}
        T = len(d.index)
        events: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
        if d.dividends is not None and len(d.dividends):
            for r in d.dividends.itertuples(index=False):
                ex = getattr(r, "ex_date", None)
                if ex is None or pd.isna(ex):
                    continue
                events.append((str(r.symbol), pd.Timestamp(ex), pd.Timestamp(r.date)))
        elif d.w("ex_div") is not None:
            exd = d.wide["ex_div"].astype("boolean").fillna(False).astype(bool)
            for s in d.symbols:
                for i in np.flatnonzero(exd[s].to_numpy()):
                    if i + 1 < T:
                        events.append((s, d.index[i + 1], d.index[i]))
        for sym, ex, known in events:
            if sym not in mal.index or known > d.t or ex > d.t:
                continue
            p = int(d.index.searchsorted(ex, side="left"))
            age = (T - 1) - p
            gs = self._grid_sess(d)
            if gs is not None and 0 <= p < T:
                age = int(gs[T - 1] - gs[p])  # séances écoulées depuis le jour ex (BOC manquants compris)
            if 0 <= age < n:
                mal[sym] = min(mal[sym], pen)
                info[sym] = {"ex_date": ex, "sessions_since_ex": age, "remaining": n - 1 - age}
        return mal, info

    # ------------------------------------------------------------ notes et risque

    def _notes_api(self) -> tuple[Any, str]:
        ok, why = notes_available()
        if not ok:
            return None, why
        from brvm_alpha.notes import signals as ns

        return ns, ""

    def _notes_store(self) -> tuple[Any, str]:
        src = self.notes_source
        if self.validation_s1:
            return None, ("notes de l'analyste sans rôle en validation S1 (additif v1.1, D11 : ni veto ni "
                          "inclinaison, S5 = 0)")
        if src is None or src is False:
            return None, "notes désactivées (notes=None)"
        ns, why = self._notes_api()
        if ns is None:
            return None, why
        if isinstance(src, str) and src == "auto":
            if self._store_cache is None:
                try:
                    from brvm_alpha.notes.store import NoteStore

                    self._store_cache = NoteStore()
                except Exception as exc:
                    return None, f"journal des notes inaccessible ({exc.__class__.__name__} : {exc})"
            return self._store_cache, ""
        return src, ""

    def _notes_overlay(self, d: _Data) -> dict[str, Any]:
        """Surcouches et filtres de l'analyste (``notes.signals.manual_overlays``), ou rien."""
        out: dict[str, Any] = {"available": False, "message": "", "veto": {}, "tilt": pd.Series(dtype=float),
                               "flags": {}, "block_buys": [], "max_weight_mult": {}, "freeze_auto": [],
                               "quality_penalty": {}, "governance_penalty": {}, "disabled_signals": {},
                               "reasons": [], "scores": None, "country_events": None, "dividend_calendar": None,
                               "table": None, "tilt_notes": [], "mode": "historique", "session": d.t,
                               "known_at": None}
        store, why = self._notes_store()
        if store is None:
            out["message"] = why
            return out
        ns, why = self._notes_api()
        cal = list(d.index)
        # Mode direct : notes connues à ``notes_known_at``, appliquées à la séance qui suit t. Aucune
        # règle ne change ; une décision postérieure à cet instant reste en mode historique.
        kw: dict[str, Any] = {}
        if self.notes_known_at is not None and not self.validation_s1:
            try:
                moment = ns.notes_moment(d.t, self.notes_known_at, cal)
                if moment.known_at is not None and moment.known_at.tz_localize(None) >= d.t:
                    kw = {"known_at": moment}
            except Exception as exc:
                out["message"] = f"instant de connaissance des notes illisible ({exc.__class__.__name__} : {exc})"
                return out
        try:
            ov = ns.manual_overlays(store, d.t, calendar=cal, **kw)
        except Exception as exc:
            out["message"] = f"surcouches des notes non calculées ({exc.__class__.__name__} : {exc})"
            return out
        out.update({k: ov.get(k, out[k]) for k in out if k in ov})
        # Seul le veto manuel (note étiquetée « veto ») exclut le titre ; R3 et R9, que le module des
        # notes range aussi parmi les vetos, bloquent les achats sans forcer la vente (§5.6).
        out["veto_all"] = dict(ov.get("veto") or {})
        manual: dict[str, list[str]] = {}
        tab = ov.get("table")
        if isinstance(tab, pd.DataFrame) and len(tab) and "code" in tab.columns:
            for rec in tab[tab["code"] == "VETO"].to_dict("records"):
                manual.setdefault(str(rec["symbol"]), []).append(
                    f"veto manuel (note {str(rec.get('note_id', ''))[:10]} du {_d(rec.get('since'))})")
        out["veto"] = manual
        out["available"] = True
        try:
            sc = ns.note_scores(store, d.t, calendar=cal, **kw)
            out["scores"] = sc
        except Exception as exc:
            out["reasons"] = list(out["reasons"]) + [f"scores des notes non calculés ({exc.__class__.__name__})"]
        try:
            frame = ns.notes_asof(store, d.t, calendar=cal, **kw) if kw else ns.notes_asof(store, d.t)
            out["country_events"], out["dividend_calendar"] = self._events_from_notes(frame, d, ns)
        except Exception as exc:
            out["reasons"] = list(out["reasons"]) + [f"règles pays des notes non lues ({exc.__class__.__name__})"]
        n_tilt = int((pd.Series(out["tilt"], dtype=float) != 0).sum()) if out["tilt"] is not None else 0
        out["message"] = (f"notes de l'analyste prises en compte : {len(out['veto'])} veto(s), {n_tilt} "
                          f"inclinaison(s), {len(out['flags'])} titre(s) avec filtre R")
        if kw:
            out["message"] += (f" (mode direct : notes connues au {out['known_at']:%d/%m/%Y %H:%M} UTC, appliquées à "
                               f"la séance du {_d(out['session'])})")
        return out

    @staticmethod
    def _events_from_notes(frame: pd.DataFrame, d: _Data, ns: Any) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        """Règles pays (étiquette ``regle_pays:<règle>[:<date>]``) et avis de dividendes des notes."""
        if frame is None or not len(frame):
            return None, None
        ev_rows: list[dict[str, Any]] = []
        cal_rows: list[dict[str, Any]] = []
        for rec in frame.to_dict("records"):
            fts = pd.Timestamp(rec.get("first_tradable_session"))
            tags = [str(x) for x in (rec.get("tags") or [])]
            targets = [str(x) for x in (rec.get("targets") or [])]
            countries = [x.split(":", 1)[1].upper() for x in targets if x.upper().startswith("PAYS:")]
            for tag in tags:
                low = tag.strip().lower()
                if not low.startswith("regle_pays:"):
                    continue
                parts = low.split(":")
                rule = _RULE_ALIASES.get(parts[1], parts[1]) if len(parts) > 1 else ""
                if rule not in COUNTRY_RULES:
                    continue
                edate = pd.to_datetime(parts[2], errors="coerce") if len(parts) > 2 else pd.NaT
                for c in countries:
                    ev_rows.append({"date": fts.normalize(), "country": c, "rule": rule, "event_date": edate,
                                    "label": rec.get("title") or "", "source": f"note {str(rec.get('note_id'))[:10]}"})
            et = str(rec.get("event_type") or "")
            if et == "DIV_NOTICE":
                try:
                    an = ns.note_analysis(rec, list(d.index))
                except Exception:
                    an = rec.get("analysis") or {}
                ex = (an.get("extracted") or {}) if isinstance(an, Mapping) else {}
                exd = pd.to_datetime(ex.get("ex_date"), errors="coerce")
                amt = ex.get("div_net")
                syms = [x for x in targets if ":" not in x]
                if pd.notna(exd) and amt is not None and syms:
                    cal_rows.append({"date": fts.normalize(), "symbol": syms[0], "ex_date": exd,
                                     "amount": float(amt), "source": f"note {str(rec.get('note_id'))[:10]}"})
        ev = pd.DataFrame(ev_rows) if ev_rows else None
        cal = pd.DataFrame(cal_rows) if cal_rows else None
        return ev, cal

    def _country_rule_state(self, d: _Data, events: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
        """Règles pays actives en t : pays -> {règle, depuis, effet}."""
        out: dict[str, dict[str, Any]] = {}
        if events is None or not len(events):
            return out
        idx = d.index
        gs = self._grid_sess(d)
        for r in events.sort_values("date").to_dict("records"):
            rule = r["rule"]
            spec = COUNTRY_RULES[rule]
            c = str(r["country"]).upper()
            since = pd.Timestamp(r["date"])
            # Séances écoulées depuis l'action (première séance qui suit l'annonce, D10), comptées en
            # séances du calendrier des BOC en base « sessions » (D1), en lignes sinon.
            elapsed = int(((idx > since) & (idx <= d.t)).sum())
            if gs is not None and elapsed > 0:
                p0 = int(idx.searchsorted(since, side="right"))
                if since > _S1_END_TS and p0 > 0:
                    # Hors S1 (§8.5 E9) : la règle court depuis la première SÉANCE du calendrier qui suit
                    # l'annonce, BOC manquants compris (D1) : une annonce tombée dans un trou de BOC ne
                    # prolonge pas la règle de la durée du trou. Numéro de cette séance = dernier numéro
                    # connu avant l'annonce + jours ouvrés écoulés jusqu'à l'annonce + 1.
                    prev_day = pd.Timestamp(idx[p0 - 1]).normalize()
                    gap_bd = int(np.busday_count((prev_day + pd.Timedelta(days=1)).date(),
                                                 (pd.Timestamp(since).normalize() + pd.Timedelta(days=1)).date()))
                    s_action = int(gs[p0 - 1]) + gap_bd + 1
                    elapsed = max(int(gs[len(idx) - 1]) - min(s_action, int(gs[p0])) + 1, 1)
                else:
                    elapsed = int(gs[len(idx) - 1] - gs[p0]) + 1
            active = False
            ramp = None
            remaining: int | None = None
            if rule == "election":
                ed = pd.to_datetime(r.get("event_date"), errors="coerce")
                if pd.isna(ed):
                    continue
                lo = ed - pd.offsets.BDay(int(spec["before"]))
                hi = ed + pd.offsets.BDay(int(spec["after"]))
                active = lo <= d.t <= hi
            elif rule == "bond_discount":
                end = pd.to_datetime(r.get("end"), errors="coerce")
                n = r.get("sessions")
                n = int(n) if n is not None and pd.notna(n) else None
                active = (pd.isna(end) or d.t <= end) and (n is None or elapsed < n)
            else:
                n = r.get("sessions")
                n = int(n) if n is not None and pd.notna(n) else int(spec["sessions"])
                if rule == "severe":
                    total = n + int(spec["rampback"])
                    active = elapsed < total
                    if active and elapsed >= n:
                        ok_vol = self._country_vol_normal(d, c)
                        ramp = (elapsed - n + 1) / int(spec["rampback"]) if ok_vol else 0.0
                    remaining = max(total - 1 - elapsed, 0)
                else:
                    active = elapsed < n
                    remaining = max(n - 1 - elapsed, 0)
            if not active:
                continue
            prev = out.get(c)
            entry = {"rule": rule, "label": spec["label"], "since": since, "elapsed": elapsed,
                     "remaining": remaining, "ramp": ramp, "source": r.get("source", "country_events"),
                     "no_buy": bool(spec.get("no_buy")) and (rule != "severe" or ramp is None)}
            # La règle la plus sévère l'emporte (ordre de COUNTRY_RULES).
            if prev is None or list(COUNTRY_RULES).index(rule) < list(COUNTRY_RULES).index(prev["rule"]):
                entry["others"] = ([prev] + prev.get("others", [])) if prev else []
                out[c] = entry
            else:
                prev.setdefault("others", []).append(entry)
                prev["no_buy"] = prev["no_buy"] or entry["no_buy"]
        return out

    def _country_vol_normal(self, d: _Data, country: str) -> bool:
        """Volatilité 20 j d'un panier équipondéré du pays < 1,5 × sa volatilité 250 j (§4.3).

        Base « sessions » (D1) : 20 et 250 dernières séances du calendrier des BOC ; la
        volatilité « normale » (250) exige ``max(⌈200 × n_dispo / 250⌉ ; 40)`` observations
        (convention de LOWVOL, plancher des signaux) ; indéfinie : retour progressif permis
        (comportement antérieur, signalé dans les diagnostics des règles pays).
        """
        syms = [s for s in d.symbols if reference.country_of(s) == country]
        if not syms:
            return True
        tr = d.wide["tr_index"][syms]
        r = (tr / tr.shift(1) - 1.0).mean(axis=1)
        r20 = r.iloc[self._window_start(d, 20):].dropna()
        r250 = r.iloc[self._window_start(d, 250):].dropna()
        gs = self._grid_sess(d)
        need = 2
        if gs is not None:
            miss = F.missing_sessions_in_window(gs, 250)[-1]
            need = int(F.prorata_min_obs(200, 250, miss, self.window_params["signal_floor"]))
            need = max(need, 2)
        v20 = r20.std(ddof=1) if len(r20) >= 2 else float("nan")
        v250 = r250.std(ddof=1) if len(r250) >= need else float("nan")
        if not (np.isfinite(v20) and np.isfinite(v250)) or v250 <= 0:
            return True
        return bool(v20 < 1.5 * v250)

    def _panel_risk(self, d: _Data, fr: dict[str, pd.DataFrame], dyd: dict[str, pd.DataFrame],
                    per: pd.DataFrame) -> pd.DataFrame:
        """Drapeaux déduits du panel : R1, R5, R8, R11, R12, contrôle des données, revue de ligne."""
        syms = d.symbols
        T = len(d.index)
        tab = pd.DataFrame(index=syms)
        tab.index.name = "symbol"
        # R1 : suspension (statut SP) ou reprise depuis moins de 5 séances.
        susp_t = fr["suspended"].iloc[-1]
        recent = fr["recent_suspension"].iloc[-1]
        tab["R1"] = (susp_t | recent).astype(bool)
        # R5 (§5.6) : « aucun achat avant le détachement des droits » d'une augmentation de capital
        # EN NUMÉRAIRE, de son ANNONCE (avis, notes de l'analyste, ``capital_increases``) à la veille
        # du détachement. Le drapeau EX-D du BOC n'apparaît que la veille du détachement : un ordre
        # décidé ce jour-là s'exécute le jour du détachement, donc APRÈS lui ; il ne protège de rien
        # et ne distingue pas une attribution gratuite (BOA 2024) d'une augmentation en numéraire.
        # Il reste une information (``EX-D_boc``), sans blocage. Avec le seul BOC, R5 n'est donc
        # pas applicable (signalé).
        flags = d.w("flags")
        r5 = pd.Series(False, index=syms)
        exd_boc = pd.Series(False, index=syms)
        r8 = pd.Series(False, index=syms)
        detail: dict[str, list[str]] = {s: [] for s in syms}
        r8_n = int(self.cfg.get("events", {}).get("risk_filters", {}).get("R8", {}).get("sessions", 5))
        w5 = self._window_start(d, r8_n)  # R8 : 5 séances (comptées en séances en base « sessions », D1)
        if flags is not None:
            f_t = flags.iloc[-1].astype(str)
            exd_boc = f_t.str.contains("EX-D", regex=False).reindex(syms).fillna(False).astype(bool)
            win = flags.iloc[w5:].astype(str)
            r8 = win.apply(lambda c: c.str.contains(r"VAL-T|\(#\)", regex=True)).any(axis=0).reindex(syms)
            r8 = r8.fillna(False).astype(bool)
        r8_fail = pd.Series(False, index=syms)
        if d.corporate_actions is not None and len(d.corporate_actions):
            lo = d.index[min(w5, T - 1)]
            recent_ca = d.corporate_actions[d.corporate_actions["date"] >= lo]
            for rec in recent_ca.to_dict("records"):
                s = str(rec["symbol"])
                if s not in syms:
                    continue
                kind = str(rec.get("kind"))
                conf = str(rec.get("confidence", ""))
                if kind in ("split", "reverse_split", "capital_adjustment"):
                    r8[s] = True
                    if conf == "low":
                        r8_fail[s] = True
                    detail[s].append(f"R8 : {kind} (ratio {rec.get('ratio')}, confiance {conf}) le "
                                     f"{_d(rec['date'])}")
                elif kind in ("unexplained_jump", "price_reset", "suspension_reset"):
                    r8[s] = True
                    r8_fail[s] = True
                    detail[s].append(f"R8 : saut de cours inexpliqué ({kind}) le {_d(rec['date'])} : contrôle échoué")
        # Contrôle des données (§9.1) : rendement quotidien > |50 %| sur les 5 dernières séances.
        tr = d.wide["tr_index"]
        rets = (tr / tr.shift(1) - 1.0).iloc[self._window_start(d, 5):]
        guard = float(self.cfg.get("data", {}).get("max_abs_daily_return_guard", 0.5))
        bad = (rets.abs() > guard).any(axis=0).reindex(syms).fillna(False).astype(bool)
        for s in syms[bad.to_numpy()]:
            detail[s].append(f"contrôle des données : rendement quotidien > {guard:.0%} (signaux bloqués)")
        if d.capital_increases is not None and len(d.capital_increases):
            for rec in d.capital_increases.to_dict("records"):
                sym = str(rec["symbol"])
                if sym not in r5.index:
                    continue
                det = pd.Timestamp(rec["detachment_date"])
                if not (pd.Timestamp(rec["date"]) <= d.t < det):
                    continue
                if rec.get("kind", "cash") == "cash":
                    r5[sym] = True
                    detail[sym].append(f"R5 : augmentation de capital en numéraire annoncée le {_d(rec['date'])} : "
                                       f"aucun achat avant le détachement des droits du {_d(det)}")
                else:
                    detail[sym].append(f"attribution gratuite annoncée (détachement le {_d(det)}) : information, "
                                       "pas de R5")
        tab["R5"] = r5
        tab["EX-D_boc"] = exd_boc
        tab["R8"] = r8
        tab["R8_fail"] = r8_fail
        tab["data_guard"] = bad
        for s in syms[exd_boc.to_numpy()]:
            if not r5[s]:
                detail[s].append("EX-D au BOC : droits (ou actions gratuites) détachés à la séance suivante ; "
                                 "information seulement (R5 se date de l'annonce, non disponible au seul BOC)")
        # R11 (financières) et R12 (non financières), proxies calculables sur le panel.
        sector = pd.Series([self.sector_map.get(s) for s in syms], index=syms, dtype=object)
        is_fin = sector.eq("FIN")
        ldd = d.w("last_div_date")
        listed_since = fr["listed"].idxmax().where(fr["listed"].any()).reindex(syms)
        three_years = d.t - pd.DateOffset(years=3)
        no_div3 = pd.Series(False, index=syms)
        if ldd is not None:
            last_pay = pd.to_datetime(ldd.iloc[-1].reindex(syms), errors="coerce")
            ever = pd.Series([pd.notna(x) for x in last_pay], index=syms)
            no_div3 = (ever & (last_pay < three_years)) | (~ever & (listed_since <= three_years))
        no_div3 = no_div3.fillna(False).astype(bool) & fr["listed"].iloc[-1].reindex(syms).astype(bool)
        dy_raw = dyd["dy_raw"].iloc[-1].reindex(syms)
        per_t = per.iloc[-1].reindex(syms)
        wht = pd.Series([self.config.taxes.dividend_withholding.get(reference.country_of(s), 0.10) for s in syms],
                        index=syms)
        payout = (dy_raw / (1.0 - wht)) * per_t.where(per_t > 0)
        payout_hi = (payout > 1.0) if self.payout_proxies else pd.Series(False, index=syms)
        per_y = per.iloc[max(0, T - 253)].reindex(syms) if T > 1 else per_t
        dy_y = dyd["dy_raw"].iloc[max(0, T - 253)].reindex(syms)
        payout_y = (dy_y / (1.0 - wht)) * per_y.where(per_y > 0)
        r11 = (no_div3.astype(int) + payout_hi.fillna(False).astype(int)).where(is_fin, 0)
        cap = float(self.cfg.get("signals", {}).get("dy", {}).get("cap", 0.15))
        dy_hi = dy_raw > cap
        r12 = ((dy_hi.fillna(False)) | (payout_hi.fillna(False) & (payout_y > 1.0).fillna(False))) & ~is_fin
        tab["R11"] = r11.astype(int)
        tab["R12"] = r12.astype(bool)
        for s in syms:
            if is_fin[s] and no_div3[s]:
                detail[s].append("R11 : aucun dividende depuis 3 ans ou plus")
            if is_fin[s] and bool(payout_hi.get(s, False)):
                detail[s].append(f"R11 : payout brut estimé {payout[s]:.2f} > 1 (approximation DY brut × PER)")
            if not is_fin[s] and bool(dy_hi.get(s, False)):
                detail[s].append(f"R12 : rendement du dividende {_pct(float(dy_raw[s]))} > {_pct(cap)}")
            if not is_fin[s] and bool(payout_hi.get(s, False)) and bool(payout_y.get(s, 0) > 1.0):
                detail[s].append("R12 : payout estimé > 100 % deux ans de suite (approximation)")
        # Revue obligatoire (§9.1) : sous-performance > 25 % contre le TR sur 63 séances.
        review = pd.Series(False, index=syms)
        r63 = self._bound_row(d, 63) if T > 63 else None
        if d.market_tr is not None and r63 is not None:
            m = d.market_tr.reindex(d.index).ffill()
            if pd.notna(m.iloc[-1]) and pd.notna(m.iloc[r63]) and m.iloc[r63] > 0:
                mret = m.iloc[-1] / m.iloc[r63] - 1.0
                sret = tr.iloc[-1] / tr.iloc[r63] - 1.0
                rel = (1.0 + sret) / (1.0 + mret) - 1.0
                review = (rel < float(self.cfg.get("risk", {}).get("review_if_rel_underperf_63", -0.25)))
                review = review.reindex(syms).fillna(False).astype(bool)
                for s in syms[review.to_numpy()]:
                    detail[s].append(f"revue obligatoire : {_pct(float(rel[s]))} contre le TR sur 63 séances")
        tab["review"] = review
        for s in syms[tab["R1"].to_numpy()]:
            detail[s].insert(0, "R1 : suspendu ou reprise récente (aucun achat ; décote de 10 % pour le risque)")
        tab["detail_panel"] = [list(detail[s]) for s in syms]
        return tab

    def _risk_table(self, d: _Data, panel_risk: pd.DataFrame, notes: dict[str, Any],
                    country_state: dict[str, dict[str, Any]]) -> pd.DataFrame:
        """Table des filtres de risque en t (panel + notes + règles pays)."""
        syms = d.symbols
        tab = panel_risk.copy()
        for code in ("R2", "R3", "R4", "R6", "R7", "R9", "R10"):
            tab[code] = False
        notes_detail: dict[str, list[str]] = {s: [] for s in syms}
        for s, lst in (notes.get("flags") or {}).items():
            if s not in tab.index:
                continue
            for info in lst:
                code = str(info.get("code"))
                if code in tab.columns and code not in ("R11", "R12"):
                    tab.loc[s, code] = True
                notes_detail[s].append(f"{code} (note {str(info.get('note_id', ''))[:10]}) : {info.get('action', '')}")
        veto = notes.get("veto") or {}
        tab["veto"] = [s in veto for s in syms]
        for s, why in veto.items():
            if s in notes_detail:
                notes_detail[s].extend(why)
        tilt = pd.Series(notes.get("tilt"), dtype=float).reindex(syms).fillna(0.0) if notes.get("tilt") is not None \
            else pd.Series(0.0, index=syms)
        tmax = _TILT_MAX
        tab["tilt"] = tilt.clip(-tmax, tmax)
        mwm = notes.get("max_weight_mult") or {}
        tab["max_weight_mult"] = [float(mwm.get(s, 1.0)) for s in syms]
        tab.loc[tab["max_weight_mult"] < 1.0, "R4"] = True
        freeze = set(notes.get("freeze_auto") or [])
        tab["freeze"] = [s in freeze for s in syms]
        tab.loc[tab["freeze"], "R6"] = True
        qpen = notes.get("quality_penalty") or {}
        gpen = notes.get("governance_penalty") or {}
        tab["quality_penalty"] = [float(qpen.get(s, 0.0)) + float(gpen.get(s, 0.0)) for s in syms]
        disabled = notes.get("disabled_signals") or {}
        tab["s1_disabled"] = [("S1" in disabled.get(s, [])) or bool(tab.loc[s, "R9"]) for s in syms]
        nb_notes = set(notes.get("block_buys") or [])
        countries = pd.Series([reference.country_of(s) for s in syms], index=syms)
        tab["country"] = countries
        tab["country_rule"] = [country_state.get(c, {}).get("rule", "") for c in countries]
        c_nobuy = pd.Series([bool(country_state.get(c, {}).get("no_buy", False)) for c in countries], index=syms)
        block = (tab["R1"] | tab["R2"] | tab["R3"] | tab["R5"] | tab["R9"] | tab["R8_fail"] | tab["data_guard"]
                 | tab["veto"] | tab["freeze"] | c_nobuy | pd.Series([s in nb_notes for s in syms], index=syms))
        tab["block_buys"] = block.astype(bool)
        tab["review"] = tab["review"] | tab["R4"] | tab["R9"] | (tab["R11"] > 0)
        tab["detail_notes"] = [list(notes_detail[s]) for s in syms]
        active = []
        for s in syms:
            codes = [c for c in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R12")
                     if bool(tab.loc[s, c])]
            if int(tab.loc[s, "R11"]) > 0:
                codes.append(f"R11×{int(tab.loc[s, 'R11'])}")
            if bool(tab.loc[s, "veto"]):
                codes.append("VETO")
            if tab.loc[s, "country_rule"]:
                codes.append(f"PAYS:{tab.loc[s, 'country_rule']}")
            active.append(",".join(codes))
        tab["active"] = active
        return tab

    def risk_flags(self, asof: Any, panels: Any, notes: Any = "default") -> pd.DataFrame:
        """Filtres de risque à la date ``asof`` (§5.6, §4.3), une ligne par titre.

        Drapeaux déduits du panel : R1 (statut SP, reprise depuis moins de 5 séances),
        R5 (augmentation de capital en numéraire, de l'annonce — ``capital_increases`` ou notes —
        à la veille du détachement ; le drapeau ``EX-D`` du BOC, visible la veille du seul
        détachement, n'est qu'une information ``EX-D_boc``), R8 (``VAL-T`` / ``(#)`` ou
        division récente ; contrôle du facteur : échec si saut inexpliqué ou confiance
        faible), R11 (financières : aucun dividende depuis 3 ans, payout brut estimé > 1),
        R12 (non financières : DY > 15 %, payout estimé > 100 % deux ans de suite),
        contrôle des données (rendement > |50 %|) et revue obligatoire (§9.1). Si le module
        ``brvm_alpha.notes`` s'importe : R2, R3, R4, R6, R7, R9, R10, vetos et
        inclinaisons de l'analyste (``notes.signals.manual_overlays``), et règles pays
        portées par les notes. ``notes`` : ``"default"`` (source du constructeur), ``None``
        (aucune note) ou un ``NoteStore`` / ``DataFrame``. Les payouts sont des
        **approximations** (DY brut × PER) ; les seuils R11 / R12 sont des choix non validés.
        """
        saved = self.notes_source
        if not (isinstance(notes, str) and notes == "default") and not self.validation_s1:
            self.notes_source = notes
        try:
            dec = self.decide(asof, panels, portfolio=False)
        finally:
            self.notes_source = saved
            if not (isinstance(notes, str) and notes == "default"):
                self._cache.clear()
        return dec.risk

    # ------------------------------------------------------------------ score

    def _score(self, d: _Data, blocks_t: dict[str, pd.Series], elig_t: pd.Series, held: pd.Series,
               mult: float, s2: pd.Series, risk: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
        comp = self.cfg.get("composite", {})
        code = self.spec.weights
        weights = dict(comp.get(code) or scoring.variant_weights(code))
        transform = dict(self.cfg.get("signals", {}).get("transform", {}))
        held_mask = pd.Series(False, index=d.symbols)
        if len(held):
            held_mask.loc[[s for s in held.index if s in held_mask.index]] = True
        sectors = self.sector_map.reindex(d.symbols)
        sn = self.spec.sector_neutral or None
        info: dict[str, Any] = {"weights_prior": weights, "momentum_multiplier": mult}
        if not bool(elig_t.any()):
            empty = pd.DataFrame(index=d.symbols, columns=["score", "raw", "with_malus", "tilt", "final"], dtype=float)
            return empty, info
        res = scoring.composite_score(
            {k: blocks_t[k] for k in weights}, weights, s2_malus=s2.where(elig_t, 0.0), universe=elig_t,
            held=held_mask, momentum_multiplier=mult, sector_neutral=sn, sectors=sectors if sn else None,
            params=transform, return_details=True)
        raw = res.raw.iloc[0].reindex(d.symbols)
        W = res.weights.iloc[0] if res.weights is not None else pd.Series(weights, dtype=float)
        z = {k: v.iloc[0].reindex(d.symbols) for k, v in res.z.items()}
        n_valid = res.n_valid.iloc[0].reindex(d.symbols) if res.n_valid is not None else None
        min_blocks = int(transform.get("min_valid_blocks", 3))
        # Pénalités de qualité des filtres R (R2 −1, R7 rouge −0,5, R9 −1, R10 −0,5), en z du bloc QUAL.
        qpen = risk["quality_penalty"].reindex(d.symbols).fillna(0.0)
        delta = pd.Series(0.0, index=d.symbols)
        if "quality_proxy" in z and (qpen != 0).any():
            clip = float(transform.get("clip", 3.0))
            zq = z["quality_proxy"]
            zq_new = (zq + qpen).clip(-clip, clip)
            ok = elig_t & (n_valid >= min_blocks) if n_valid is not None else elig_t
            delta = (float(W.get("quality_proxy", 0.0)) * (zq_new - zq)).where(ok, 0.0).fillna(0.0)
            z["quality_proxy_penalised"] = zq_new
        raw_adj = (raw + delta).where(elig_t)
        mal = s2.reindex(d.symbols).fillna(0.0).where(~held_mask, 0.0).where(elig_t, 0.0)
        sd = float(raw_adj.std(ddof=1)) if raw_adj.notna().sum() > 1 else 0.0
        if not np.isfinite(sd):
            sd = 0.0
        with_malus = raw_adj + mal * sd
        clip = float(transform.get("clip", 3.0))
        score = scoring.rank_gauss_z(with_malus.to_frame().T, universe=elig_t, winsor_pct=None, clip=clip,
                                     missing=float(transform.get("missing", 0.0))).iloc[0].reindex(d.symbols)
        tilt = risk["tilt"].reindex(d.symbols).fillna(0.0).where(elig_t, 0.0)
        final = (score + tilt).where(elig_t)
        tab = pd.DataFrame({"score": score, "raw": raw, "quality_delta": delta, "with_malus": with_malus,
                            "malus": mal, "tilt": tilt, "final": final,
                            "n_valid_blocks": n_valid if n_valid is not None else np.nan})
        for k, v in z.items():
            tab[f"z_{k}"] = v
        info.update({"weights_effective": {k: float(v) for k, v in W.items()}, "sd_raw": sd,
                     "min_blocks": min_blocks, "sector_neutral": list(sn or [])})
        return tab, info

    # -------------------------------------------------------------- décision

    def decide(self, asof: Any, panels: Any, held: Any = None, *, portfolio: bool = True) -> AlphaDecision:
        """Décision complète à la date ``asof`` (univers, signaux, risque, score, poids).

        ``held`` : poids détenus (Series symbole -> fraction de la NAV) ; à défaut,
        ``panels.weights`` si ``panels`` est une ``PanelView`` du moteur. Le résultat est
        mis en cache (même date, mêmes panels, mêmes poids détenus).
        """
        held_s = self._held(held, panels)
        objs = tuple((k, id(v)) for k, v in panels.items()) if isinstance(panels, dict) else ()
        key = (_as_ts(asof), id(panels), objs,
               tuple(sorted((k, round(float(v), 10) if np.isfinite(v) else -1.0) for k, v in held_s.items())),
               bool(portfolio), self._event_mode, len(self._nav), bool(self._risk_state.get("stopped")),
               self._recording, len(self._s1_journal), len(self._s1_open), self._s1_suspended is not None,
               self._state_rev, self._mode_override, len(self._nav_invested))
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        dec = self._decide(asof, panels, held_s, portfolio)
        self._cache[key] = dec
        while len(self._cache) > _STATE_CACHE_SIZE:
            self._cache.popitem(last=False)
        if portfolio:
            self.last_decision = dec
        return dec

    @staticmethod
    def _held(held: Any, panels: Any) -> pd.Series:
        if held is None:
            held = getattr(panels, "weights", None)
        if held is None:
            return pd.Series(dtype=float)
        if isinstance(held, (pd.Series, Mapping)):
            s = pd.Series(held, dtype=float)
        else:
            s = pd.Series(np.nan, index=[str(x) for x in held], dtype=float)
        s.index = s.index.astype(str)
        s = s.groupby(level=0).sum(min_count=1)
        return s[(s > 1e-9) | s.isna()]

    def _decide(self, asof: Any, panels: Any, held: pd.Series, portfolio: bool) -> AlphaDecision:
        d = self._prepare(panels, asof)
        messages = list(d.messages)
        fp = self._feature_panels(d)
        fr = self._universe_frames(d)
        uni = self._universe_table(d, fr)
        if uni.attrs.get("message"):
            messages.append(uni.attrs["message"])
        if not uni.attrs.get("free_float_known"):
            messages.append("U4 : aucun avis de flottant publié à cette date dans la base (premier avis "
                            "utilisable : 14/10/2026) : filtre non appliqué")
        wnote = self._window_note(d)
        if wnote:
            messages.append(wnote)
        elig_hist = fr["eligible"]
        blocks, dyd = self._blocks(d, fp, elig_hist)
        blocks_t = {k: v.iloc[-1].reindex(d.symbols) for k, v in blocks.items()}
        mm = self._momentum_multiplier(d, fp, blocks["mom6_1"], elig_hist)
        for k in ("vol_scaling_error", "crash_filter_error", "crash_filter_note", "s1_guard"):
            if k in mm:
                messages.append(f"modulateur du momentum : {mm[k]}")
        s2, s2_info = self._s2_malus(d)
        per = F.per_v1(fp, self.cfg.get("data", {}).get("eps_override"), split_factor=d.w("split_factor"))
        panel_risk = self._panel_risk(d, fr, dyd, per)
        notes = self._notes_overlay(d)
        if notes["message"]:
            messages.append(notes["message"])
        events = [e for e in (d.country_events, notes.get("country_events")) if e is not None and len(e)]
        ev = pd.concat(events, ignore_index=True) if events else None
        if ev is not None:
            ev = self._normalize_events(ev)
            ev = self._events_known(ev, d.t) if ev is not None else None
        country_state = self._country_rule_state(d, ev)
        risk = self._risk_table(d, panel_risk, notes, country_state)
        elig_t = uni["eligible"].reindex(d.symbols).fillna(False).astype(bool)
        # Signaux bloqués : contrôle de données échoué, R8 en échec, R6 (gel des signaux automatiques).
        sig_block = (risk["data_guard"] | risk["R8_fail"]).reindex(d.symbols).fillna(False).astype(bool)
        score_tab, score_info = self._score(d, blocks_t, elig_t & ~sig_block, held, mm["multiplier"], s2, risk)
        signals_out: dict[str, pd.Series] = {}
        for k, lab in SIGNAL_LABELS.items():
            if k in blocks_t:
                signals_out[lab] = blocks_t[k].rename(lab)
        signals_out["composite"] = score_tab["final"].rename("composite")
        signals_out["composite_raw"] = score_tab["raw"].rename("composite_raw")
        signals_out["S2"] = s2.rename("S2")
        signals_out["tilt"] = score_tab["tilt"].rename("tilt")
        for k in ("ep", "dy", "mom6_1", "lowvol", "quality_proxy", "mom12_1"):
            col = f"z_{k}"
            if col in score_tab.columns:
                signals_out[f"z_{SIGNAL_LABELS[k]}"] = score_tab[col].rename(f"z_{SIGNAL_LABELS[k]}")
        diag: dict[str, Any] = {"momentum": mm, "s2": s2_info, "score": score_info, "notes": notes,
                                "window_basis": {"basis": self.window_basis, "explicit": self.window_basis_explicit,
                                                 "note": wnote},
                                "country_rules": country_state, "dy_reason": dyd["reason"].iloc[-1],
                                "dy_raw": dyd["dy_raw"].iloc[-1], "per": per.iloc[-1], "mode": uni.attrs["mode"],
                                "data": d}
        if not portfolio:
            w0 = pd.Series(0.0, index=d.symbols, name="weight")
            return AlphaDecision(d.t, self.variant, w0, uni, signals_out, risk, score_tab, diag, _uniq(messages))
        kind = "reference" if self._mode_override == "index" else self.spec.kind
        if kind == "reference":
            weights, pdiag, pmsg = self._reference_portfolio(d, uni, risk, held, country_state)
            guard = self._cap_guard(d)
            pdiag["cap_guard"] = guard
            if guard.get("alert"):
                pmsg = [guard["message"]] + list(pmsg)
        elif kind == "core_satellite":
            weights, pdiag, pmsg = self._core_satellite(d, fr, uni, risk, score_tab, held, country_state, dyd,
                                                        elig_t, sig_block)
        else:
            weights, pdiag, pmsg = self._portfolio(d, fr, uni, risk, score_tab, held, country_state, dyd, elig_t,
                                                   sig_block)
        # Invariants de sortie : poids ≥ 0, somme ≤ exposition visée (98 %), y compris quand des poids
        # détenus (dérivés depuis la dernière décision) sont reconduits.
        budget = float(self.portfolio_params["gross_equity"])
        weights = weights.reindex(d.symbols).astype(float).fillna(0.0).clip(lower=0.0)
        weights = weights.where(weights > 1e-12, 0.0)
        if float(weights.sum()) > budget + 1e-12:
            weights = weights * (budget / float(weights.sum()))
        weights = weights.rename("weight")
        messages.extend(pmsg)
        diag.update(pdiag)
        weights.attrs.update({"asof": d.t, "variant": self.variant, "mode": diag.get("mode"),
                              "invested": float(weights.sum()), "banner": BANNER})
        return AlphaDecision(d.t, self.variant, weights, uni, signals_out, risk, score_tab, diag, _uniq(messages))

    # ------------------------------------------------------------ portefeuille

    def _context(self, d: _Data, uni: pd.DataFrame, risk: pd.DataFrame, held: pd.Series,
                 country_state: dict[str, dict[str, Any]], elig: list[str]) -> tuple[dict[str, Any], list[str]]:
        msgs: list[str] = []
        syms = d.symbols
        ctx: dict[str, Any] = {"capital": self.capital, "asof": d.t,
                               "sectors": self.sector_map.reindex(syms).to_dict(),
                               "countries": {s: reference.country_of(s) for s in syms},
                               "mdv63": uni["mdv63"].fillna(0.0)}
        if uni.attrs.get("spread_available"):
            ctx["spread"] = uni["spread_120"]
        rf = pd.DataFrame({"R4": risk["R4"] | (risk["max_weight_mult"] < 1.0), "R11": risk["R11"].astype(int),
                           "R12": risk["R12"]}, index=syms)
        ctx["risk_flags"] = rf
        ctx["no_buy"] = sorted(s for s in syms if bool(risk.loc[s, "block_buys"]))
        close_t = d.wide["close_raw"].iloc[-1]
        shares = d.w("shares")
        b_seat: pd.Series | None = None
        if shares is not None and shares.iloc[-1].notna().any():
            ctx["close"] = close_t
            ctx["shares"] = shares.iloc[-1]
            try:
                b_seat = construct.reference_weights_pit(close_t, shares.iloc[-1])["seat"]
            except ValueError:
                b_seat = None
        else:
            msgs.append("nombre de titres absent : poids de référence b_c non calculés (plafonds pays sur u_c)")
        if self.spec.weighting in ("hrp_tilt", "mv_alpha"):
            tr = d.wide["tr_index"]
            ctx["returns"] = tr / tr.shift(1) - 1.0
            if d.w("stats_usable") is not None:
                ctx["stats_mask"] = d.wide["stats_usable"].astype("boolean").fillna(False).astype(bool)
        # Règles d'événements pays (§4.3) : plafonds et multiplicateurs.
        overrides: dict[str, float] = {}
        mults: dict[str, float] = {}
        n_e = max(len(elig), 1)
        pp = self.portfolio_params
        for c, st in country_state.items():
            entries = [st] + list(st.get("others", []))
            u_c = sum(1 for s in elig if reference.country_of(s) == c) / n_e
            b_c = float(b_seat.get(c, np.nan)) if b_seat is not None else float("nan")
            ref_val = b_c if np.isfinite(b_c) else u_c
            for e in entries:
                spec = COUNTRY_RULES[e["rule"]]
                if e["rule"] == "severe":
                    base = 0.25 * (min(b_c, u_c) if np.isfinite(b_c) else u_c)
                    if e.get("ramp") is not None:
                        normal = (float(pp["gross_equity"]) if c in pp["uncapped_countries"] else
                                  min(float(pp["country_cap_max"]),
                                      max(float(pp["country_cap_floor"]),
                                          float(pp["country_cap_mult"]) * max(u_c, ref_val))))
                        base = base + float(np.clip(e["ramp"], 0.0, 1.0)) * (normal - base)
                    overrides[c] = min(overrides.get(c, np.inf), base)
                elif spec.get("cap_x_ref") is not None:
                    overrides[c] = min(overrides.get(c, np.inf), float(spec["cap_x_ref"]) * ref_val)
                if spec.get("cap_mult") is not None:
                    mults[c] = min(mults.get(c, 1.0), float(spec["cap_mult"]))
            msgs.append(f"règle pays {c} : {st['label']} depuis le {_d(st['since'])}"
                        + (f", encore {st['remaining']} séance(s)" if st.get("remaining") is not None else "")
                        + (" ; aucun achat" if st.get("no_buy") else ""))
        if overrides:
            ctx["country_cap_overrides"] = overrides
        if mults:
            ctx["country_cap_mult"] = mults
        return ctx, msgs

    def _portfolio(self, d: _Data, fr: dict[str, pd.DataFrame], uni: pd.DataFrame, risk: pd.DataFrame,
                   score_tab: pd.DataFrame, held: pd.Series, country_state: dict[str, dict[str, Any]],
                   dyd: dict[str, pd.DataFrame], elig_t: pd.Series, sig_block: pd.Series) -> tuple[
                       pd.Series, dict[str, Any], list[str]]:
        msgs: list[str] = []
        syms = d.symbols
        diag: dict[str, Any] = {}
        # Garde-fou global (§9.1) : capitalisation reconstruite à plus de 3 % de la publiée.
        guard = self._cap_guard(d)
        diag["cap_guard"] = guard
        if guard.get("blocked"):
            msgs.append(guard["message"])
            w = held.reindex(syms).fillna(0.0).clip(lower=0.0).rename("weight")
            diag["mode"] = "gel_donnees"
            return w, diag, msgs
        if guard.get("alert"):
            msgs.append(guard["message"])
        if self._risk_state.get("stopped"):
            msgs.append("ARRÊT (§9.1) : drawdown relatif ≤ −20 % : mode « indice discipliné » ; "
                        "aucune promesse d'alpha")
            diag["mode"] = "indice_discipline"
            # Suivi seulement (l'arrêt est définitif) : ni la division par 2 ni un nouvel arrêt ne
            # s'appliquent en mode « indice discipliné » ; les drapeaux ``halve`` / ``stop`` sont
            # retirés pour que le diagnostic ne décrive pas une règle non appliquée.
            rel_track = self._relative_drawdown(d)
            diag["relative_drawdown"] = {**{k: v for k, v in rel_track.items() if k not in ("halve", "stop")},
                                         "tracking_only": True}
            year = self._risk_state.get("index_year")
            if year == d.t.year and len(held) and np.isfinite(held.to_numpy()).all() and float(held.sum()) > 0:
                w, idiag = self._index_hold(d, uni, risk, held, country_state)
                diag.update(idiag)
                return w, diag, msgs + idiag.get("index", {}).get("messages", [])
            w, idiag = self._index_weights(d, uni, risk, held, country_state)
            self._risk_state["index_year"] = d.t.year
            diag.update(idiag)
            return w, diag, msgs + idiag.get("index", {}).get("messages", [])
        veto = set(syms[risk["veto"].reindex(syms).fillna(False).to_numpy(dtype=bool)])
        elig_mask = elig_t & ~sig_block
        elig = [s for s in syms if bool(elig_mask[s]) and s not in veto]
        for s in veto:
            if bool(elig_t.get(s, False)):
                msgs.append(f"{s} : veto de l'analyste appliqué après le score (exclu de la sélection)")
        ctx, cmsg = self._context(d, uni, risk, held, country_state, elig)
        msgs.extend(cmsg)
        scores = score_tab["final"].reindex(syms)
        w, pdg = construct.target_portfolio(scores.dropna(), elig, held if len(held) else None, ctx,
                                            self.portfolio_params)
        w = w.reindex(syms).fillna(0.0).rename("weight")
        diag["portfolio"] = pdg
        diag["mode"] = pdg.get("mode")
        msgs.extend(pdg.get("messages", []))
        # R6 : gel des signaux automatiques -> ligne détenue conservée telle quelle.
        frozen = [s for s in syms if bool(risk.loc[s, "freeze"]) and s in held.index and np.isfinite(held[s])]
        if frozen:
            w = self._restore_lines(w, {s: float(held[s]) for s in frozen},
                                    float(self.portfolio_params["gross_equity"]))
            msgs.append("R6 (offre publique) : lignes gelées à leur poids actuel : " + ", ".join(frozen))
        # Report des ventes avant un détachement (§5.2.6).
        deferred = self._deferred_sales(d, w, held, risk, country_state)
        diag["deferred_sales"] = deferred
        if deferred and self._defer_active():
            w = self._restore_lines(w, {s: v["weight"] for s, v in deferred.items()},
                                    float(self.portfolio_params["gross_equity"]))
            for s, v in deferred.items():
                msgs.append(f"{s} : vente reportée au jour ex du {_d(v['ex_date'])} (rendement net "
                            f"{_pct(v['yield'])}, {v['sessions_to_ex']} séance(s)) — §5.2.6")
        elif deferred:
            msgs.append("report des ventes avant détachement non appliqué hors mode événementiel : "
                        + ", ".join(sorted(deferred)))
        # Variante F : dosage par le régime (§4.4).
        if self.spec.regime_scaling:
            rg = self._regime(d)
            diag["regime"] = rg
            if rg.get("multiplier", 1.0) < 1.0:
                w = w * float(rg["multiplier"])
                msgs.append(f"variante F : régime agité (P = {rg.get('p_turbulent', float('nan')):.2f}, drawdown du TR "
                            f"{_pct(rg.get('drawdown', float('nan')))}) : exposition × {rg['multiplier']:g}")
            elif rg.get("message"):
                msgs.append(rg["message"])
        # Variante E : poche S1 (§5.2.7).
        if self.spec.s1_pocket:
            w, s1 = self._s1_pocket(d, w, uni, risk, country_state, pdg, held)
            diag["s1"] = s1
            msgs.extend(s1.get("messages", []))
        # Risque de portefeuille (§9.1) : drawdown relatif contre le TR.
        rel = self._relative_drawdown(d)
        diag["relative_drawdown"] = rel
        if rel.get("message"):
            msgs.append(rel["message"])
        if rel.get("halve"):
            w_ew = self._ew_eligible(pdg, elig, scores, held, ctx.get("no_buy", []))
            w = (0.5 * w + 0.5 * w_ew.reindex(syms).fillna(0.0)).rename("weight")
            diag["ew_basket"] = {"names": list(w_ew[w_ew > 0].index), "weights": w_ew[w_ew > 0],
                                 "rule": "additif v1.1, D5 : 20 éligibles les mieux classés, équipondérés sous "
                                         "plafonds ; entrées et sorties exemptées de la bande de non-transaction"}
            msgs.append("§9.1 : drawdown relatif ≤ −15 % : exposition active divisée par 2 (½ cible + ½ panier "
                        f"équipondéré des {int((w_ew > 0).sum())} éligibles les mieux classés, D5 ; plancher de 2 % "
                        "non réappliqué)")
        if rel.get("stop"):
            w, idiag = self._index_weights(d, uni, risk, held, country_state)
            self._risk_state["index_year"] = d.t.year
            diag.update(idiag)
            diag["mode"] = "indice_discipline"
            msgs.extend(idiag.get("index", {}).get("messages", []))
        # Plafond de rotation (§6 : ≤ 50 % aller par rebalancement, ``cap_turnover``) ; les ventes
        # imposées par une règle pays sévère ou un coup d'État n'y sont pas soumises (§4.3).
        urgent = any(st.get("rule") in ("severe", "coup") for st in country_state.values())
        max_to = float(self.cfg.get("portfolio", {}).get("max_turnover_per_rebalance", 0.50))
        prev = held.reindex(syms)
        if len(held) and prev.notna().any() and np.isfinite(held.to_numpy()).all() and not urgent:
            to = 0.5 * float((w - prev.fillna(0.0)).abs().sum())
            if to > max_to + 1e-12:
                w = construct.cap_turnover(w, prev.fillna(0.0), max_turnover=max_to).reindex(syms).fillna(0.0)
                msgs.append(f"rotation visée {_pct(to)} > {_pct(max_to)} : cible ramenée par combinaison convexe "
                            "avec les poids détenus (cap_turnover)")
                diag["turnover_capped"] = {"before": to, "after": max_to}
        # Tracking error ex ante (§9.1), information.
        diag["tracking_error"] = self._tracking_error(d, w, elig)
        te = diag["tracking_error"].get("te")
        te_cap = float(self.cfg.get("risk", {}).get("te_cap", 0.14))
        if te is not None and np.isfinite(te) and te > te_cap:
            msgs.append(f"tracking error ex ante estimée {_pct(te)} > {_pct(te_cap)} : réduction des poids actifs "
                        "à décider (non automatisée en v1)")
        w = w.where(w > 1e-12, 0.0).clip(lower=0.0)
        budget = float(self.portfolio_params["gross_equity"])
        if float(w.sum()) > budget + 1e-9:
            w = w * (budget / float(w.sum()))
        return w.rename("weight"), diag, msgs

    def _defer_active(self) -> bool:
        return self._event_mode if self.defer_sales is None else bool(self.defer_sales)

    @staticmethod
    def _restore_lines(w: pd.Series, keep: Mapping[str, float], budget: float) -> pd.Series:
        """Remet des lignes à un poids imposé et réduit les autres au prorata (budget conservé)."""
        w = w.copy()
        fixed = {s: max(float(v), 0.0) for s, v in keep.items() if s in w.index}
        if not fixed:
            return w
        tot_fixed = sum(fixed.values())
        others = [s for s in w.index if s not in fixed]
        room = max(budget - tot_fixed, 0.0)
        cur = float(w[others].sum())
        if cur > room and cur > 0:
            w[others] = w[others] * (room / cur)
        for s, v in fixed.items():
            w[s] = v
        if float(w.sum()) > budget + 1e-12:
            w = w * (budget / float(w.sum()))
        return w

    def _deferred_sales(self, d: _Data, w: pd.Series, held: pd.Series, risk: pd.DataFrame,
                        country_state: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Ventes d'un titre détenu dont la date ex tombe dans les 15 séances (rendement ≥ 4 %)."""
        rule = self.cfg.get("events", {}).get("sell_deferral_to_ex", {})
        max_s = int(rule.get("max_sessions_to_ex", 15))
        min_y = float(rule.get("min_net_yield", 0.04))
        out: dict[str, dict[str, Any]] = {}
        if not len(held):
            return out
        cal = self._upcoming_ex(d)
        if cal is None or not len(cal):
            return out
        close_t = d.wide["close_raw"].iloc[-1]
        for s, hw in held.items():
            if s not in w.index or not np.isfinite(hw) or w[s] >= hw - 1e-9:
                continue
            rows = cal[cal["symbol"] == s]
            if not len(rows):
                continue
            r = rows.sort_values("ex_date").iloc[0]
            # Séances jusqu'au jour ex (le jour ex compris) ; si le jour ex est la séance suivante,
            # l'ordre normal y est déjà exécuté : aucun report n'est nécessaire.
            n_to = _bdays_between(d.t, pd.Timestamp(r["ex_date"])) + 1
            px = float(close_t.get(s, np.nan))
            y = float(r["amount"]) / px if px and np.isfinite(px) and px > 0 else float("nan")
            if not (2 <= n_to <= max_s and np.isfinite(y) and y >= min_y):
                continue
            rk = risk.loc[s] if s in risk.index else None
            blocked = rk is not None and (any(bool(rk[c]) for c in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
                                                                     "R9", "R10"))
                                          or bool(rk["country_rule"]))
            if blocked:
                continue
            out[s] = {"ex_date": pd.Timestamp(r["ex_date"]), "yield": y, "sessions_to_ex": n_to, "weight": float(hw),
                      "target": float(w[s])}
        return out

    def _upcoming_ex(self, d: _Data) -> pd.DataFrame | None:
        """Dates ex connues en t et postérieures à t (avis de paiement, lignes (d) du BOC)."""
        frames = []
        for src in (d.dividend_calendar, d.dividends):
            if src is not None and len(src) and {"symbol", "ex_date", "amount"} <= set(src.columns):
                x = src[["symbol", "ex_date", "amount"]].copy()
                x["ex_date"] = pd.to_datetime(x["ex_date"])
                frames.append(x[x["ex_date"] > d.t])
        if not frames:
            return None
        out = pd.concat(frames, ignore_index=True).drop_duplicates(["symbol", "ex_date"])
        return out

    def _ew_eligible(self, pdg: Mapping[str, Any], elig: Sequence[str], scores: pd.Series | None = None,
                     held: pd.Series | None = None, no_buy: Iterable[str] = ()) -> pd.Series:
        """Panier w_EW de la règle −15 % (§9.1) : équipondération, sous les plafonds de A, des
        **20 éligibles les mieux classés** (additif v1.1, D5), titres achetables ou détenus."""
        caps = pdg.get("caps", {})
        upper = caps.get("upper")
        groups = caps.get("groups", [])
        held_set = set(held.index) if held is not None else set()
        blocked = set(no_buy)
        names = [s for s in elig if (upper is None or float(upper.get(s, 0.0)) > 0)
                 and (s not in blocked or s in held_set)]
        if scores is not None and len(names):
            ranks = construct.score_ranks(scores.reindex(names), names)
            names = list(ranks.index)
        top_n = int(self.cfg.get("risk", {}).get("relative_dd", {}).get("ew_basket_top_n", 20))
        names = names[:top_n]
        if not names:
            return pd.Series(dtype=float)
        return construct.equal_weight_with_caps(names, upper, groups, float(self.portfolio_params["gross_equity"]),
                                                min_weight=0.0)

    # ------------------------------------------------------------------ régime

    def _regime(self, d: _Data) -> dict[str, Any]:
        """Variante F (§4.4) : exposition × 0,75 si P(agité) > 0,8 et drawdown du TR < −8 %."""
        cfg = (self.cfg.get("macro_overlay", {}).get("regime", {}) or {}).get("variant_F", {})
        p_on = float(cfg.get("p_turbulent", 0.8))
        dd_on = float(cfg.get("tr_drawdown", -0.08))
        mult = float(cfg.get("exposure_mult", 0.75))
        p_off = float(cfg.get("exit_p_lt", 0.5))
        weeks_off = int(cfg.get("exit_weeks", 4))
        out: dict[str, Any] = {"multiplier": 1.0}
        if d.market_tr is None or len(d.market_tr) < 60:
            out["message"] = "variante F : Composite TR absent ou trop court : aucun dosage"
            return out
        lvl = d.market_tr.dropna()
        hs, guard = self._performance_start()
        if hs is not None:
            lvl = lvl[lvl.index >= hs]
        if guard:
            out["s1_guard"] = guard
        wk = lvl.resample("W-FRI").last().dropna()
        r = wk.pct_change().dropna()
        # Observations « hebdomadaires » qui couvrent un trou de BOC (plus de 6 séances : 49 jours
        # au 25/06/2021) ou la fenêtre exclue du §8.1 : retirées avant le modèle de Markov (§4.4,
        # « 2021 traité à part ») ; elles mêleraient plusieurs semaines en une observation.
        from brvm_alpha.backtest import metrics as mt

        keep = mt.weekly_observation_mask(pd.DatetimeIndex(lvl.index), pd.DatetimeIndex(r.index),
                                          exclude_windows=mt.EXCLUDE_STATS_WINDOWS, max_sessions=6)
        out["weeks_dropped"] = [x.date() for x in r.index[~keep]]
        r = r[keep]
        if len(r) < 60:
            out["message"] = "variante F : moins de 60 semaines de TR : aucun dosage"
            return out
        try:
            from brvm_alpha.quant import regime as rg

            probs = rg.hmm_filtered_probabilities(r, n_states=2, refit_every=4, train_window=None, min_train=52)
        except Exception as exc:
            out["message"] = f"variante F : régime non estimé ({exc.__class__.__name__} : {exc})"
            return out
        p = probs.get("p_1")
        if p is None:
            out["message"] = "variante F : probabilités d'état indisponibles"
            return out
        dd = wk / wk.cummax() - 1.0
        reduced = False
        calm = 0
        for dt, pv in p.items():
            if not np.isfinite(pv):
                continue
            ddv = float(dd.get(dt, 0.0))
            if not reduced and pv > p_on and ddv < dd_on:
                reduced, calm = True, 0
            elif reduced:
                calm = calm + 1 if pv < p_off else 0
                if calm >= weeks_off:
                    reduced = False
        last_p = float(p.dropna().iloc[-1]) if p.notna().any() else float("nan")
        out.update({"p_turbulent": last_p, "drawdown": float(dd.iloc[-1]), "reduced": reduced,
                    "multiplier": mult if reduced else 1.0})
        return out

    # --------------------------------------------------------------- poche S1

    def _sessions_between(self, a: pd.Timestamp, b: pd.Timestamp) -> int:
        """Séances strictement entre ``a`` et ``b`` (calendrier des séances s'il est connu, sinon jours ouvrés)."""
        cal = self._calendar
        a, b = pd.Timestamp(a).normalize(), pd.Timestamp(b).normalize()
        if b <= a:
            return -1
        if cal is not None and len(cal) and cal[0] <= a and b <= cal[-1]:
            return int(((cal > a) & (cal < b)).sum())
        return _bdays_between(a, b)

    def _s1_update_journal(self, d: _Data) -> None:
        """Clôture point-in-time des opérations S1 dont le jour ex est passé (journal du coupe-circuit).

        Opération = entrée au VWAP de la première séance échangée après la décision, sortie à la
        clôture du jour ex (fixing), dividende net du calendrier ; gain net **estimé** de tous les
        coûts (aller-retour ``2 × settings.one_way_cost_estimate`` au scénario de coûts du modèle,
        participation de 1 %). Seules les données publiées au plus tard en t sont lues.
        """
        if not self._s1_open:
            return
        close = d.wide["close_raw"]
        vol, val = d.w("volume"), d.w("value")
        sf = d.w("split_factor")
        one_way = settings.one_way_cost_estimate(self.config.costs, participation=0.01)
        for key in sorted(self._s1_open, key=lambda k: (k[1], k[0])):
            sym, exd = key
            if exd > d.t or sym not in close.columns:
                continue
            te = self._s1_open.pop(key)
            info = dict(self._s1_meta.pop(key, {}))
            rows = (d.index > te) & (d.index < exd)
            entry_px, entry_day = math.nan, None
            if vol is not None and val is not None:
                v = vol.loc[rows, sym]
                traded = v[v > 0]
                if len(traded):
                    entry_day = traded.index[0]
                    entry_px = float(val.at[entry_day, sym]) / float(traded.iloc[0])
            pos_ex = int(d.index.searchsorted(exd, side="left"))
            if entry_day is None or pos_ex >= len(d.index) or not np.isfinite(entry_px) or entry_px <= 0:
                self._s1_journal.append({**info, "symbol": sym, "ex_date": exd, "decision": te, "executed": False})
                continue
            exit_day = d.index[pos_ex]
            exit_px = float(close.at[exit_day, sym])
            f_in = float(sf.at[entry_day, sym]) if sf is not None and pd.notna(sf.at[entry_day, sym]) else 1.0
            f_out = float(sf.at[exit_day, sym]) if sf is not None and pd.notna(sf.at[exit_day, sym]) else 1.0
            div = float(info.get("amount", 0.0) or 0.0)
            gross = ((exit_px + div) / f_out) / (entry_px / f_in) - 1.0 if np.isfinite(exit_px) else math.nan
            net = gross - 2.0 * one_way if np.isfinite(gross) else math.nan
            self._s1_journal.append({**info, "symbol": sym, "ex_date": exd, "decision": te, "executed": True,
                                     "entry_date": entry_day, "entry_price": entry_px, "exit_date": exit_day,
                                     "exit_price": exit_px, "dividend": div, "gross": gross,
                                     "round_trip_cost": 2.0 * one_way, "net": net,
                                     "win": bool(np.isfinite(net) and net > 0)})

    def _s1_kill_switch(self, d: _Data) -> dict[str, Any]:
        """Coupe-circuit de S1 (§5.2.7) : sur les 30 dernières opérations, gain net moyen ≤ 0 ou < 50 % gagnantes."""
        ks = dict(self.cfg.get("events", {}).get("S1", {}).get("kill_switch", {}) or {})
        n_req = int(ks.get("trades", 30))
        min_mean = float(ks.get("min_mean_net", 0.0))
        min_hit = float(ks.get("min_hit", 0.50))
        done = [op for op in self._s1_journal if op.get("executed") and np.isfinite(op.get("net", math.nan))]
        out: dict[str, Any] = {"trades_required": n_req, "n_completed": len(done), "suspended": False,
                               "rule": f"suspendu si, sur {n_req} opérations, gain net moyen ≤ {min_mean:g} "
                                       f"ou part gagnante < {min_hit:.0%}"}
        if self._s1_suspended is not None:
            out.update(self._s1_suspended)
            out["suspended"] = True
            return out
        if len(done) >= n_req:
            last = done[-n_req:]
            mean_net = float(np.mean([op["net"] for op in last]))
            hit = float(np.mean([op["win"] for op in last]))
            out.update({"mean_net": mean_net, "hit_rate": hit})
            if mean_net <= min_mean or hit < min_hit:
                state = {"since": d.t, "mean_net": mean_net, "hit_rate": hit, "n": n_req}
                if self._recording:
                    self._s1_suspended = state
                out.update(state)
                out["suspended"] = True
        return out

    def _s1_pocket(self, d: _Data, w: pd.Series, uni: pd.DataFrame, risk: pd.DataFrame,
                   country_state: dict[str, dict[str, Any]],
                   pdg: Mapping[str, Any], held: pd.Series | None = None) -> tuple[pd.Series, dict[str, Any]]:
        """Variante E : poche de capture du dividende (§5.2.7), financée au prorata par le cœur.

        Entrée : seulement si l'exécution en t + 1 a lieu au plus tard 3 séances avant la date ex
        (``séances strictement entre t et ex ≥ min_sessions_to_ex``, calendrier des séances) ;
        une position de la poche déjà ouverte est conservée jusqu'à la veille du jour ex
        (vente exécutée le jour ex). Aucun filtre R1-R10 actif (R7 compris). Coupe-circuit sur
        les 30 dernières opérations (journal point-in-time, gains nets **estimés**).
        """
        p = self.cfg.get("events", {}).get("S1", {})
        min_y = float(p.get("min_net_yield", 0.04))
        min_mdv = float(p.get("min_mdv60_fcfa", 1_000_000))
        min_sess = int(p.get("min_sessions_to_ex", 3))
        per_name = float(p.get("max_per_name", 0.05))
        total_max = float(p.get("max_total", 0.20))
        part = float(self.cfg.get("portfolio", {}).get("liquidity", {}).get("max_participation", 0.10))
        out: dict[str, Any] = {"positions": {}, "messages": []}
        if self._recording:
            self._s1_update_journal(d)
        ks = self._s1_kill_switch(d)
        out["kill_switch"] = ks
        out["journal_size"] = len(self._s1_journal)
        if ks.get("suspended"):
            out["messages"].append(
                f"variante E : coupe-circuit S1 déclenché le {_d(ks.get('since'))} (gain net moyen estimé "
                f"{_pct(ks.get('mean_net', float('nan')), 2)}, {_pct(ks.get('hit_rate', float('nan')))} "
                f"d'opérations gagnantes sur {ks.get('n')}) : poche S1 suspendue")
            return w, out
        cal = d.dividend_calendar
        if cal is None or not len(cal):
            out["messages"].append("variante E : aucun avis de dividende daté (dividend_calendar) : "
                                   "poche S1 vide, E = A")
            return w, out
        held_s = held if held is not None else pd.Series(dtype=float)
        close_t = d.wide["close_raw"].iloc[-1]
        line_caps = pdg.get("caps", {}).get("line")
        floor = self.mdv_floor()
        pocket: dict[str, float] = {}
        meta: dict[tuple[str, pd.Timestamp], dict[str, Any]] = {}
        for r in cal.sort_values(["date", "symbol"]).to_dict("records"):
            s = str(r["symbol"])
            exd = pd.Timestamp(r["ex_date"]).normalize()
            if s not in uni.index or exd <= d.t:
                continue
            known = pd.Timestamp(r["date"])
            first = d.index[d.index.searchsorted(known, side="left")] if known <= d.t else None
            if first is None:
                continue
            n_entry = self._sessions_between(first, exd)
            n_now = self._sessions_between(d.t, exd)
            is_open = (s, exd) in self._s1_open and float(held_s.get(s, 0.0) or 0.0) > 0
            px = float(close_t.get(s, np.nan))
            y = float(r["amount"]) / px if np.isfinite(px) and px > 0 else float("nan")
            mdv60 = float(uni.loc[s, "mdv60"]) if pd.notna(uni.loc[s, "mdv60"]) else 0.0
            mdv63 = float(uni.loc[s, "mdv63"]) if pd.notna(uni.loc[s, "mdv63"]) else 0.0
            rk = risk.loc[s]
            r_active = any(bool(rk[c]) for c in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10")) or \
                bool(rk["s1_disabled"]) or bool(rk["country_rule"]) or int(rk["R11"]) > 0 or bool(rk["R12"])
            # Nouvelle entrée : exécution en t + 1 au plus tard en ex − 3 séances ; position déjà
            # ouverte : conservée tant que le jour ex n'est pas la séance suivante.
            timing_ok = n_now >= min_sess if not is_open else n_now >= 1
            if n_entry < min_sess or not timing_ok or not (np.isfinite(y) and y >= min_y) or mdv60 < min_mdv \
                    or mdv63 < floor or r_active or not bool(uni.loc[s, "listed"]):
                continue
            liq = part * mdv60 * max(n_now, 1) / self.capital
            cap_line = float(line_caps.get(s, 0.10)) if line_caps is not None and s in line_caps.index else 0.10
            room = max(cap_line - float(w.get(s, 0.0)), 0.0)
            pocket[s] = max(0.0, min(per_name, liq, room if room > 0 else per_name))
            out["positions"][s] = {"ex_date": exd, "yield": y, "sessions_to_ex": n_now, "weight": pocket[s],
                                   "renewal": is_open}
            meta[(s, exd)] = {"amount": float(r["amount"]), "yield": y}
        tot = sum(pocket.values())
        if tot > total_max:
            pocket = {s: v * total_max / tot for s, v in pocket.items()}
            tot = total_max
        if self._recording:
            for (s, exd), info in meta.items():
                if s in pocket and pocket[s] > 0 and (s, exd) not in self._s1_open:
                    self._s1_open[(s, exd)] = d.t
                    self._s1_meta[(s, exd)] = info
        if tot <= 0:
            return w, out
        core = float(w.sum())
        w2 = w * (max(core - tot, 0.0) / core) if core > 0 else w.copy()
        for s, v in pocket.items():
            w2[s] = float(w2.get(s, 0.0)) + v
        out["total"] = tot
        out["messages"].append(f"variante E : poche S1 de {_pct(tot)} sur {len(pocket)} titre(s) (hypothèse "
                               "d'exécution : au VWAP, et non à cours limité × 1,02)")
        return w2.rename("weight"), out

    def s1_journal(self) -> pd.DataFrame:
        """Journal des opérations S1 clôturées (variante E) : gains nets **estimés**, coupe-circuit."""
        return pd.DataFrame(self._s1_journal)

    # -------------------------------------------------- risque de portefeuille

    def record_nav(self, asof: Any, nav: float | None, invested: bool | None = None) -> None:
        """Mémorise la valeur liquidative (règles de drawdown relatif du §9.1).

        ``invested`` : le portefeuille détient-il des titres à cette date ? (``None`` : inconnu,
        compté comme investi). Le drawdown relatif est mesuré depuis **t0**, première date
        investie (additif v1.1, D5 ; en production : début du suivi réel).
        """
        if nav is None or not np.isfinite(nav):
            return
        t = _as_ts(asof).normalize()
        self._nav[t] = float(nav)
        if invested is None or bool(invested):
            self._nav_invested.add(t)

    @property
    def relative_dd_start(self) -> pd.Timestamp | None:
        """t0 du drawdown relatif (D5) : première date de VL où le portefeuille détenait des titres."""
        return min(self._nav_invested) if self._nav_invested else None

    def reset_state(self) -> None:
        """Oublie les valeurs liquidatives, l'état des règles de risque, des poches annuelles (REF,
        cœur de I) et le journal S1 (nouveau backtest)."""
        self._nav.clear()
        self._nav_invested.clear()
        self._sleeves = {"ref": None, "core": None, "a": None}
        self._state_rev += 1
        self._risk_state = {"halved_since": None, "stopped": False, "alert": False, "index_year": None}
        self._s1_open.clear()
        self._s1_meta.clear()
        self._s1_journal.clear()
        self._s1_suspended = None
        self._cache.clear()

    def _relative_drawdown(self, d: _Data) -> dict[str, Any]:
        cfg = self.cfg.get("risk", {}).get("relative_dd", {})
        out: dict[str, Any] = {"dd": None}
        if not self.risk_overlay or len(self._nav) < 2 or d.market_tr is None:
            return out
        nav = pd.Series(self._nav).sort_index()
        t0 = self.relative_dd_start
        if t0 is None:
            return out
        # Additif v1.1, D5 : ratio VL / TR rebasé à t0 (premier jour investi), contre son plus haut depuis t0.
        nav = nav[(nav.index >= t0) & (nav.index <= d.t)]
        out["t0"] = t0
        m = d.market_tr.reindex(d.market_tr.index.union(nav.index)).ffill().reindex(nav.index)
        ok = nav.notna() & m.notna() & (m > 0)
        nav, m = nav[ok], m[ok]
        if len(nav) < 2:
            return out
        rel = (nav / nav.iloc[0]) / (m / m.iloc[0])
        dd = rel / rel.cummax() - 1.0
        cur = float(dd.iloc[-1])
        out["dd"] = cur
        st = self._risk_state
        alert, halve_at, recover, stop = (float(cfg.get("alert", -0.10)), float(cfg.get("halve_active", -0.15)),
                                          float(cfg.get("recover_to", -0.075)), float(cfg.get("stop", -0.20)))
        months = int(cfg.get("halve_max_months", 6))
        if cur <= stop:
            st["stopped"] = True
            out.update({"stop": True, "message": f"§9.1 : drawdown relatif {_pct(cur)} ≤ {_pct(stop)} : ARRÊT, mode "
                                                 "« indice discipliné »"})
            return out
        if st.get("halved_since") is None and cur <= halve_at:
            st["halved_since"] = d.t
        if st.get("halved_since") is not None:
            if cur >= recover or d.t >= pd.Timestamp(st["halved_since"]) + pd.DateOffset(months=months):
                st["halved_since"] = None
            else:
                out["halve"] = True
        if cur <= alert:
            out["message"] = f"§9.1 : alerte, drawdown relatif contre le TR {_pct(cur)}"
        return out

    def _tracking_error(self, d: _Data, w: pd.Series, elig: Sequence[str]) -> dict[str, Any]:
        """Tracking error ex ante contre le Composite (pondération par la capitalisation), information."""
        shares = d.w("shares")
        if shares is None or not (w > 0).any():
            return {"te": None}
        cap = (d.wide["close_raw"].iloc[-1] * shares.iloc[-1]).dropna()
        cap = cap[cap > 0]
        if not len(cap):
            return {"te": None}
        b = cap / cap.sum()
        names = sorted(set(b.index) | set(w[w > 0].index))
        tr = d.wide["tr_index"][[s for s in names if s in d.wide["tr_index"].columns]]
        try:
            cov = construct.weekly_covariance(tr / tr.shift(1) - 1.0, d.t,
                                              usable=d.wide["stats_usable"].astype("boolean").fillna(False).astype(bool)
                                              if d.w("stats_usable") is not None else None)
        except Exception as exc:
            return {"te": None, "error": f"{exc.__class__.__name__} : {exc}"}
        names = [s for s in names if s in cov.index]
        a = (w.reindex(names).fillna(0.0) - b.reindex(names).fillna(0.0)).to_numpy()
        var = float(a @ cov.loc[names, names].to_numpy() @ a) * 52.0
        return {"te": math.sqrt(var) if var > 0 else 0.0, "n": len(names), "method": "Ledoit-Wolf W-FRI, × √52"}

    def _cap_guard(self, d: _Data) -> dict[str, Any]:
        tol = float(self.cfg.get("data", {}).get("cap_reconstruction_tolerance", 0.03))
        shares = d.w("shares")
        if shares is None or d.market is None or "market_cap" not in d.market.columns or not len(d.market):
            return {"checked": False}
        last = d.market.iloc[-1]
        if pd.Timestamp(last["date"]) != d.t or not np.isfinite(last["market_cap"]) or last["market_cap"] <= 0:
            return {"checked": False}
        cap = float((d.wide["close_raw"].iloc[-1] * shares.iloc[-1]).sum(min_count=1))
        ratio = cap / float(last["market_cap"])
        blocking = bool(self.cfg.get("data", {}).get("cap_guard_blocking", False))
        out: dict[str, Any] = {"checked": True, "ratio": ratio, "tolerance": tol, "blocking": blocking}
        if not np.isfinite(ratio) or abs(ratio - 1.0) > tol:
            out["alert"] = True
            if blocking:  # lecture v1.0 du §9.1 (désactivée par l'additif v1.1)
                out["blocked"] = True
                out["message"] = (f"§9.1 contrôle des données : capitalisation reconstruite / publiée = {ratio:.4f} "
                                  f"(écart > {tol:.0%}) : calcul des signaux bloqué, positions inchangées")
            else:  # additif v1.1, D3 : alerte journalisée, non bloquante
                out["message"] = (f"ALERTE données (additif v1.1, D3) : capitalisation reconstruite / publiée = "
                                  f"{ratio:.4f} (écart > {tol:.0%}) ; non bloquant : le nombre de titres reconstruit "
                                  "ne sert qu'à l'étalon et aux références b_c, pas aux signaux")
        return out

    # -------------------------------------------------------- indice discipliné

    def _index_inputs(self, d: _Data, uni: pd.DataFrame, risk: pd.DataFrame, held: pd.Series,
                      country_state: dict[str, dict[str, Any]]) -> tuple[pd.Series, list[str], dict[str, Any],
                                                                          list[str]]:
        """Capitalisations (étalon), candidats et contexte de l'indice discipliné (D8), connus en t."""
        syms = d.symbols
        msgs: list[str] = []
        veto = set(syms[risk["veto"].reindex(syms).fillna(False).to_numpy(dtype=bool)])
        sig_block = (risk["data_guard"] | risk["R8_fail"]).reindex(syms).fillna(False).astype(bool)
        elig = [s for s in syms if bool(uni.loc[s, "eligible"]) and s not in veto]
        ctx, cmsg = self._context(d, uni, risk, held, country_state, elig)
        msgs.extend(cmsg)
        no_buy = set(ctx.get("no_buy", [])) | {s for s in syms if bool(sig_block[s])}
        close_t = d.wide["close_raw"].iloc[-1]
        listed = uni["listed"].reindex(syms).fillna(False).astype(bool)
        shares = d.w("shares")
        cap = pd.Series(np.nan, index=syms, dtype=float)
        if shares is not None:
            cap = (close_t * shares.iloc[-1]).reindex(syms)
        if not cap[listed].notna().any():
            cap = uni["mdv63"].reindex(syms).astype(float)
            msgs.append("indice discipliné : nombre de titres absent, capitalisation remplacée par la MDV63 "
                        "(approximation)")
        cap = cap.where(listed)
        seat = expo = None
        if shares is not None:
            try:
                ref_w = construct.reference_weights_pit(close_t, shares.iloc[-1])
                seat, expo = ref_w["seat"], ref_w["exposure"]
            except ValueError:
                seat = expo = None
        ictx = {"countries": ctx["countries"], "sectors": ctx["sectors"], "mdv63": ctx["mdv63"],
                "capital": self.capital, "risk_flags": ctx["risk_flags"], "no_buy": sorted(no_buy),
                "held": held[np.isfinite(held)] if len(held) else held, "seat": seat, "exposure": expo,
                "country_cap_mult": ctx.get("country_cap_mult"), "country_cap_overrides": ctx.get("country_cap_overrides")}
        return cap, elig, ictx, msgs

    def _index_params(self) -> dict[str, Any]:
        sec = self.cfg.get("portfolio", {}).get("disciplined_index", {}) or {}
        return {k: v for k, v in sec.items() if k in construct.DISCIPLINED_INDEX_V11}

    def _index_weights(self, d: _Data, uni: pd.DataFrame, risk: pd.DataFrame, held: pd.Series,
                       country_state: dict[str, dict[str, Any]] | None = None) -> tuple[pd.Series, dict[str, Any]]:
        """Rebalancement de l'indice discipliné (additif v1.1, D8) à la date t."""
        syms = d.symbols
        cap, elig, ictx, msgs = self._index_inputs(d, uni, risk, held, country_state or {})
        w, idg = construct.disciplined_index_portfolio(cap.dropna(), elig, ictx, self.portfolio_params,
                                                       self._index_params())
        out = pd.Series(0.0, index=syms, name="weight")
        out.loc[w.index] = w.to_numpy()
        sel = list(idg.get("selected", []))
        rank = {s_: i + 1 for i, s_ in enumerate(sel)}
        reasons = {s_: (f"indice discipliné : capitalisation n° {rank[s_]} parmi les éligibles"
                        + ("" if out.get(s_, 0.0) > 0 else " ; poids final nul (plancher de 0,5 %)")) for s_ in sel}
        idg = {**idg, "messages": _uniq(msgs + list(idg.get("messages", []))), "action": "rebalancement",
               "changed": True, "reasons": reasons}
        return out, {"index": idg, "portfolio": {"caps": idg.get("caps", {}), "reasons": reasons,
                                                  "mode": "indice_discipline"}}

    def _forced_exits(self, d: _Data, uni: pd.DataFrame, risk: pd.DataFrame, names: Iterable[str]) -> dict[str, str]:
        """Sorties forcées de l'indice discipliné entre deux rebalancements (D8) : inéligibilité,
        veto, R11 avec deux drapeaux ou plus (exclusion)."""
        out: dict[str, str] = {}
        excl = int(self.portfolio_params.get("risk_exclude_flags", 2))
        for s_ in names:
            if s_ not in uni.index:
                out[s_] = "absent du BOC"
            elif not bool(uni.loc[s_, "eligible"]):
                out[s_] = f"inéligible ({uni.loc[s_, 'reason'] or uni.loc[s_, 'codes']})"
            elif bool(risk.loc[s_, "veto"]):
                out[s_] = "veto"
            elif int(risk.loc[s_, "R11"]) >= excl:
                out[s_] = f"R11 : {int(risk.loc[s_, 'R11'])} drapeaux (exclusion)"
        return out

    def _index_hold(self, d: _Data, uni: pd.DataFrame, risk: pd.DataFrame, held: pd.Series,
                    country_state: dict[str, dict[str, Any]]) -> tuple[pd.Series, dict[str, Any]]:
        """Entre deux rebalancements annuels (D8) : positions détenues, moins les sorties forcées
        (filtres R, inéligibilité) et les réductions imposées par les règles pays (§4.3). Le produit
        des ventes reste en liquidités jusqu'au rebalancement suivant (publié)."""
        syms = d.symbols
        w = held.reindex(syms).astype(float).fillna(0.0).clip(lower=0.0)
        forced = self._forced_exits(d, uni, risk, [s_ for s_ in syms if w[s_] > 0])
        for s_ in forced:
            w[s_] = 0.0
        reductions: dict[str, dict[str, float]] = {}
        if country_state:
            elig = [s_ for s_ in syms if bool(uni.loc[s_, "eligible"])]
            ctx, _ = self._context(d, uni, risk, held, country_state, elig)
            caps = dict(ctx.get("country_cap_overrides") or {})
            for c, cap_c in caps.items():
                members = [s_ for s_ in syms if reference.country_of(s_) == c and w[s_] > 0]
                tot = float(w[members].sum()) if members else 0.0
                if tot > float(cap_c) + 1e-12:
                    f = max(float(cap_c), 0.0) / tot
                    w[members] = w[members] * f
                    reductions[c] = {"before": tot, "after": float(w[members].sum()), "cap": float(cap_c)}
        changed = bool(forced or reductions)
        msgs = ["indice discipliné : rebalancement annuel (première décision de janvier), positions conservées"
                + (" sauf sorties forcées : " + ", ".join(f"{k} ({v})" for k, v in forced.items()) if forced else "")
                + (" ; règles pays : " + ", ".join(sorted(reductions)) if reductions else "")]
        idg = {"action": "conservation", "changed": changed, "forced_exits": forced, "country_reductions": reductions,
               "cash_from_exits": float(held.reindex(syms).fillna(0.0).clip(lower=0.0).sum() - w.sum()),
               "messages": msgs}
        return w.rename("weight"), {"index": idg}

    def _reference_portfolio(self, d: _Data, uni: pd.DataFrame, risk: pd.DataFrame, held: pd.Series,
                             country_state: dict[str, dict[str, Any]]) -> tuple[pd.Series, dict[str, Any], list[str]]:
        """Variante REF (additif v1.1, D8) : indice discipliné, rebalancement **annuel** (première
        décision de chaque année civile, ou tant que rien n'est détenu), sorties forcées entre deux.

        Interprétation littérale (signalée) : entre deux rebalancements, aucun ordre hors sorties
        forcées et règles pays ; la part d'un ordre de janvier non exécutée dans son âge maximal
        (moteur) reste en liquidités jusqu'au rebalancement suivant. Le cœur de la variante I, qui
        ne voit pas ses positions réelles, suit au contraire sa cible annuelle dérivée des cours.
        """
        st = self._sleeves.get("ref") or {}
        held_ok = held[np.isfinite(held)] if len(held) else held
        invested = bool(len(held_ok) and float(held_ok.sum()) > 0)
        last_t = st.get("t")
        rebalance = (not st or st.get("year") != d.t.year or not invested
                     or (last_t is not None and d.t < pd.Timestamp(last_t)))
        if rebalance:
            w, idiag = self._index_weights(d, uni, risk, held, country_state)
            if float(w.sum()) > 0 and (last_t is None or d.t >= pd.Timestamp(last_t)):
                self._sleeves["ref"] = {"year": d.t.year, "t": d.t}
                self._state_rev += 1
        else:
            w, idiag = self._index_hold(d, uni, risk, held, country_state)
        diag = {"mode": "indice_discipline", "variant_kind": "reference", **idiag}
        return w, diag, list(idiag.get("index", {}).get("messages", []))

    def _core_sleeve(self, d: _Data, uni: pd.DataFrame, risk: pd.DataFrame, held: pd.Series,
                     country_state: dict[str, dict[str, Any]]) -> tuple[pd.Series, dict[str, Any]]:
        """Cœur de la variante I (D9) : indice discipliné rebalancé chaque année, dérivé entre deux.

        Entre deux rebalancements, le cœur est un portefeuille acheté-conservé : poids
        ``w0_i × P_i(t)/P_i(t0)`` (cours ajustés des divisions, dividendes en liquidités) sur la
        valeur du cœur ; un titre en sortie forcée (inéligible, veto, R11 ≥ 2) passe en
        liquidités. Le cœur ne voit pas les positions réelles (mélangées avec le côté A).
        """
        syms = d.symbols
        st = self._sleeves.get("core") or {}
        t0 = st.get("t0")
        w0 = st.get("w0")
        rebalance = (not st or st.get("year") != d.t.year or w0 is None or float(w0.sum()) <= 0
                     or (t0 is not None and d.t < pd.Timestamp(t0)) or pd.Timestamp(t0) not in d.index)
        if rebalance:
            w, idiag = self._index_weights(d, uni, risk, held, country_state)
            w0n = w[w > 0]
            if float(w0n.sum()) > 0 and (t0 is None or d.t >= pd.Timestamp(t0)):
                self._sleeves["core"] = {"year": d.t.year, "t0": d.t, "w0": w0n.copy()}
                self._state_rev += 1
            return w, {**idiag, "core_action": "rebalancement"}
        px = d.wide["close_adj"]
        r0 = int(d.index.get_loc(pd.Timestamp(t0)))
        ratio = (px.iloc[-1] / px.iloc[r0]).reindex(w0.index)
        ratio = ratio.where(np.isfinite(ratio) & (ratio > 0), 1.0)
        v = w0 * ratio
        value = float(v.sum()) + max(1.0 - float(w0.sum()), 0.0)
        core = (v / value) if value > 0 else v * 0.0
        forced = self._forced_exits(d, uni, risk, list(core[core > 0].index))
        for s_ in forced:
            core[s_] = 0.0
        out = pd.Series(0.0, index=syms, name="weight")
        out.loc[[s_ for s_ in core.index if s_ in out.index]] = core.reindex(
            [s_ for s_ in core.index if s_ in out.index]).to_numpy()
        msgs = [f"variante I : cœur indice discipliné du {_d(t0)} (rebalancement annuel), dérivé des cours"
                + (" ; sorties forcées : " + ", ".join(forced) if forced else "")]
        return out, {"index": {"action": "derive", "t0": t0, "forced_exits": forced, "messages": msgs},
                     "core_action": "derive"}

    def _core_satellite(self, d: _Data, fr: dict[str, pd.DataFrame], uni: pd.DataFrame, risk: pd.DataFrame,
                        score_tab: pd.DataFrame, held: pd.Series, country_state: dict[str, dict[str, Any]],
                        dyd: dict[str, pd.DataFrame], elig_t: pd.Series, sig_block: pd.Series) -> tuple[
                            pd.Series, dict[str, Any], list[str]]:
        """Variante I (additif v1.1, D9) : ``0,5 × w_REF + 0,5 × w_A``, projetée sur les plafonds de
        groupe de D8 ; côté A mensuel (bande 30/50 sur ses propres lignes), cœur annuel."""
        syms = d.symbols
        if self._risk_state.get("stopped"):  # arrêt du §9.1 déjà acté : tout le portefeuille en indice discipliné
            w_s, pdiag, pmsg = self._portfolio(d, fr, uni, risk, score_tab, held, country_state, dyd, elig_t,
                                               sig_block)
            return w_s, {**pdiag, "variant_kind": "core_satellite"}, pmsg
        last_a = self._sleeves.get("a") or {}
        held_a = last_a.get("w") if last_a.get("t") is not None and pd.Timestamp(last_a["t"]) < d.t else None
        held_a = held_a if isinstance(held_a, pd.Series) else pd.Series(dtype=float)
        w_a, pdiag, pmsg = self._portfolio(d, fr, uni, risk, score_tab, held_a, country_state, dyd, elig_t, sig_block)
        if pdiag.get("mode") == "indice_discipline":  # arrêt du §9.1 : tout le portefeuille en indice discipliné
            return w_a, {**pdiag, "variant_kind": "core_satellite"}, pmsg
        core, cdiag = self._core_sleeve(d, uni, risk, held, country_state)
        cap, elig, ictx, imsgs = self._index_inputs(d, uni, risk, held, country_state)
        names = sorted(set(core[core > 0].index) | set(w_a[w_a > 0].index))
        upper, groups, det = construct.disciplined_index_constraints(names, cap.dropna(), elig, ictx,
                                                                     self.portfolio_params, self._index_params())
        held_ok = held[np.isfinite(held)] if len(held) else held
        blocked = {s_: float(held_ok.get(s_, 0.0)) for s_ in ictx.get("no_buy", []) if s_ in names}
        share = float(self.cfg.get("portfolio", {}).get("core_satellite", {}).get("core_share", self.spec.core_share))
        w, cs = construct.core_satellite_weights(core, w_a, upper, groups, core_share=share,
                                                 budget=float(self.portfolio_params["gross_equity"]), blocked=blocked)
        out = pd.Series(0.0, index=syms, name="weight")
        out.loc[w.index] = w.to_numpy()
        if last_a.get("t") is None or d.t >= pd.Timestamp(last_a["t"]):
            self._sleeves["a"] = {"t": d.t, "w": w_a[w_a > 0].copy()}
            self._state_rev += 1
        msgs = list(pmsg) + list(cdiag.get("index", {}).get("messages", [])) + imsgs + list(det.get("messages", []))
        msgs.append(f"variante I (additif v1.1, D9) : {share:.0%} indice discipliné + {1 - share:.0%} A, "
                    f"chevauchements additionnés{', projection sur les plafonds de groupe de D8' if cs['projected'] else ''}"
                    f" ; {int((out > 0).sum())} lignes, {float(out.sum()):.2%} investis")
        caps = {"upper": cs["upper"], "line": det["line"], "line_detail": det["line_detail"],
                "liquidity": det["liquidity"], "groups": groups, "sector": det["sector"], "country": det["country"],
                "aes": det["aes"]}
        reasons: dict[str, str] = {}
        a_reasons = (pdiag.get("portfolio") or {}).get("reasons", {}) or {}
        for s_ in names:
            parts = []
            if float(core.get(s_, 0.0)) > 0:
                parts.append(f"cœur {share * float(core[s_]):.2%}")
            if float(w_a.get(s_, 0.0)) > 0:
                parts.append(f"satellite A {(1 - share) * float(w_a[s_]):.2%} ({a_reasons.get(s_, '')})")
            reasons[s_] = "variante I : " + " + ".join(parts)
        diag = {**pdiag, "mode": "coeur_satellite", "variant_kind": "core_satellite", "core": cdiag,
                "satellite": {"weights": w_a[w_a > 0], "mode": pdiag.get("mode"), "portfolio": pdiag.get("portfolio")},
                "portfolio": {"caps": caps, "reasons": reasons, "violations": cs["violations"],
                              "mode": "coeur_satellite", "active_constraints": cs["active_constraints"]},
                "core_satellite": {k: v for k, v in cs.items() if k not in ("upper", "violations")}}
        return out, diag, msgs

    def disciplined_index_weights(self, asof: Any, panels: Any) -> pd.Series:
        """Mode « indice discipliné » (additif v1.1, D8) : 20 plus grosses capitalisations éligibles.

        Poids proportionnels à la capitalisation point-in-time (cours × nombre de titres
        reconstruit), plafond de ligne ``max(10 % × m_pays ; min(30 % ; 1,25 × b_i))``,
        plancher 0,5 %, secteur ``max(15 % ; 1,25 × b_s)``, plafonds pays, AES et liquidité
        de A, filtres R et règles pays actifs ; 98 % investis au plus. Calcul **à la date**
        (sans état) : le rebalancement annuel et les sorties forcées sont appliqués par la
        variante ``REF`` (:meth:`strategy_fn`) et par le repli du §8.3. Aucune promesse d'alpha.
        """
        dec = self.decide(asof, panels, portfolio=False)
        d: _Data = dec.diagnostics["data"]
        w, diag = self._index_weights(d, dec.universe, dec.risk, pd.Series(dtype=float),
                                      dec.diagnostics.get("country_rules", {}))
        w.attrs.update({"asof": d.t, "mode": "indice_discipline", "banner": BANNER,
                        "messages": diag.get("index", {}).get("messages", []),
                        "invested": float(w.sum())})
        return w

    # ---------------------------------------------------------------- contrat

    def signals(self, asof: Any, panels: Any, held: Any = None) -> dict[str, pd.Series]:
        """Signaux à la date ``asof`` : ``dict[str, pd.Series]`` (une valeur par titre).

        Clés : ``EP``, ``DY``, ``MOM6_1``, ``LOWVOL``, ``QUAL`` (valeurs brutes des blocs de
        A, orientées « élevé = attractif ») ; signaux de recherche à poids nul ``MOM3_1``,
        ``MOM6_0``, ``MOM12_1``, ``MOM12_7``, ``AMIHUD`` ; ``composite`` (score final
        utilisé pour le classement : rang gaussien après malus S2, plus l'inclinaison de
        l'analyste ; NaN hors univers), ``composite_raw`` (``Σ w_b z_b``), ``S2`` (malus
        en écarts-types, avant l'exemption des titres détenus), ``tilt`` et ``z_<bloc>``.
        """
        return self.decide(asof, panels, held, portfolio=False).signals

    def target_weights(self, asof: Any, panels: Any, held: Any = None) -> pd.Series:
        """Poids cibles à la date ``asof`` (fraction de la NAV, somme ≤ 0,98).

        Exécution prévue à partir de ``asof + 1`` par le moteur. ``held`` : poids détenus
        (bande 30/50, malus S2 réservé aux nouveaux achats) ; à défaut, ceux de la
        ``PanelView`` du moteur. Avec une ``PanelView``, la valeur liquidative est
        mémorisée pour les règles de drawdown relatif (§9.1).
        """
        nav = getattr(panels, "nav", None)
        if nav is not None:
            w_now = getattr(panels, "weights", None)
            inv = bool((pd.Series(w_now, dtype=float) > 1e-9).any()) if w_now is not None else None
            self.record_nav(asof, nav, invested=inv)
        return self.decide(asof, panels, held).weights.copy()

    def strategy_fn(
        self,
        *,
        event_driven: bool = False,
        calendar: Sequence[Any] | pd.DatetimeIndex | None = None,
        rebalance: str = "M",
        mode: str = "alpha",
        reset: bool = True,
    ) -> Callable[[pd.Timestamp, Any], pd.Series | None]:
        """Fonction ``(asof, panel_view) -> poids`` pour ``Backtester.run``.

        Elle mémorise les poids détenus (bande 30/50 ; à défaut des poids réels de la vue)
        et la valeur liquidative (§9.1). ``event_driven=False`` (défaut) : à lancer avec
        ``rebalance="M"`` (décision à la dernière séance de chaque mois). ``True`` : à
        lancer avec ``rebalance="D"`` et le calendrier des séances ``calendar`` ; la
        fonction ne renvoie des poids qu'aux fins de mois et lors des événements (règle
        pays nouvelle, poche S1 de la variante E, vente reportée au jour ex), ``None``
        sinon (aucun ordre). ``mode="index"`` : mode « indice discipliné » (D8), comme la
        variante ``REF`` : rebalancement à la première décision de chaque année (ou tant que
        rien n'est détenu), sorties forcées entre deux, ``None`` les autres mois (aucun ordre).

        Additif v1.1 : la VL est mémorisée avec l'indication « titres détenus » (D5 : drawdown
        relatif depuis t0, premier jour investi) ; ``reset=True`` oublie aussi l'état annuel de
        REF et du cœur de I.
        """
        if mode not in ("alpha", "index"):
            raise ValueError("mode doit valoir 'alpha' ou 'index'")
        if reset:
            self.reset_state()
        reb: set[pd.Timestamp] = set()
        if event_driven:
            if calendar is None:
                raise ValueError("event_driven=True exige le calendrier des séances (calendar)")
            reb = {pd.Timestamp(x).normalize() for x in engine.rebalance_dates(pd.DatetimeIndex(calendar), rebalance)}
        cal = pd.DatetimeIndex(calendar) if calendar is not None else None
        if cal is not None:
            self._calendar = cal  # séances jusqu'au jour ex (poche S1), calendrier publié des séances
        state: dict[str, Any] = {"held": pd.Series(dtype=float), "year": None, "last": None, "deferred": {},
                                 "s1": set(), "events_seen": set()}

        def held_from(view: Any) -> pd.Series:
            w = getattr(view, "weights", None)
            if isinstance(w, pd.Series):
                s = w.astype(float)
                s.index = s.index.astype(str)
                return s[s > 1e-9]
            return state["held"]

        def fn(asof: pd.Timestamp, view: Any) -> pd.Series | None:
            self._recording = True  # journal S1 (coupe-circuit) tenu seulement pendant le backtest
            self._mode_override = "index" if mode == "index" else None
            try:
                return _fn(asof, view)
            finally:
                self._recording = False
                self._mode_override = None

        def _fn(asof: pd.Timestamp, view: Any) -> pd.Series | None:
            t = pd.Timestamp(asof).normalize()
            held = held_from(view)
            nav = getattr(view, "nav", None)
            if nav is not None:
                self.record_nav(t, nav, invested=bool(len(held) and float(held.sum()) > 0))
            reference_kind = mode == "index" or self.spec.kind == "reference"
            if reference_kind and not (event_driven and t not in reb):
                dec = self.decide(t, view, held)
                idx_diag = dec.diagnostics.get("index", {}) or {}
                if idx_diag.get("action") == "conservation" and not idx_diag.get("changed"):
                    return None  # rebalancement annuel : aucun ordre entre deux
                w = dec.weights.copy()
                state["year"], state["held"], state["last"] = t.year, w[w > 0], w
                return w
            if not event_driven:
                w = self.decide(t, view, held).weights.copy()
                state["held"], state["last"] = w[w > 0], w
                return w
            self._event_mode = True
            try:
                if t in reb:
                    dec = self.decide(t, view, held)
                    w = dec.weights.copy()
                    state["deferred"] = dict(dec.diagnostics.get("deferred_sales") or {})
                    state["s1"] = set((dec.diagnostics.get("s1") or {}).get("positions", {}))
                    state["held"], state["last"] = w[w > 0], w
                    return w
                return self._intramonth(t, view, held, state, cal)
            finally:
                self._event_mode = False

        return fn

    def _peek_decide(self, t: pd.Timestamp, view: Any, held: pd.Series) -> AlphaDecision:
        """Décision **intra-mois** sans effet sur l'état des poches annuelles (pré-vol du 22/11/2026).

        Entre deux fins de mois, une décision ne sert qu'à dériver les réductions imposées par une
        règle pays (§4.3, D10) ou les entrées et sorties de la poche S1 : elle ne doit ni consommer le
        rebalancement annuel de REF ou du cœur de I (D8 : première décision **mensuelle** de janvier,
        comme en mode mensuel), ni remplacer les lignes « détenues » du satellite A de I (bande 30/50
        évaluée d'une fin de mois à l'autre). L'état ``_sleeves`` est donc rétabli après l'appel.
        """
        orig = dict(self._sleeves)
        saved = {k: (dict(v) if isinstance(v, dict) else v) for k, v in orig.items()}
        try:
            return self.decide(t, view, held)
        finally:
            # Les poches sont remplacées (jamais modifiées sur place) : l'identité suffit à repérer un changement.
            changed = set(self._sleeves) != set(orig) or any(self._sleeves.get(k) is not v for k, v in orig.items())
            self._sleeves = saved
            if changed:
                self._state_rev += 1  # invalide le cache des décisions calculées avec l'état modifié

    def _intramonth(self, t: pd.Timestamp, view: Any, held: pd.Series, state: dict[str, Any],
                    cal: pd.DatetimeIndex | None) -> pd.Series | None:
        """Ordres entre deux fins de mois (§6 « Fréquence ») : règles pays, ventes reportées, S1."""
        trigger = []
        hit_countries: set[str] = set()
        ev = self.country_events
        pv = _get(view, "country_events")
        tables = [x for x in (ev, self._normalize_events(pv) if pv is not None else None) if x is not None]
        for tab in tables:
            for r in self._events_known(tab, t).to_dict("records"):
                key = (str(r["country"]), r["rule"], pd.Timestamp(r["date"]))
                if key not in state["events_seen"] and r["rule"] in ("severe", "coup"):
                    state["events_seen"].add(key)
                    hit_countries.add(str(r["country"]))
                    trigger.append(f"règle pays {r['country']} ({r['rule']})")
        nxt = None
        if cal is not None:
            pos = cal.searchsorted(t, side="right")
            nxt = cal[pos] if pos < len(cal) else None
        due = [s for s, v in state["deferred"].items() if nxt is not None and pd.Timestamp(v["ex_date"]) <= nxt]
        if due:
            trigger.append("ventes reportées au jour ex : " + ", ".join(due))
        s1_change = False
        if self.spec.s1_pocket:
            # La poche est réévaluée chaque séance (entrées et sorties datées), s'il existe une source
            # d'avis de dividendes datés (table fournie ou notes de l'analyste).
            pc = _get(view, "dividend_calendar")
            has_cal = (self.dividend_calendar is not None and len(self.dividend_calendar) > 0) or (
                isinstance(pc, pd.DataFrame) and len(pc) > 0)
            notes_on = self.notes_source is not None and self.notes_source is not False and notes_available()[0]
            s1_change = has_cal or notes_on
        if not trigger and not s1_change:
            return None
        if hit_countries:
            # Règle pays nouvelle (§4.3) : seules les lignes du pays sont réduites dès t + 1 (ventes
            # échelonnées par le plafond de participation du moteur) ; le reste attend la fin du mois.
            dec = self._peek_decide(t, view, held)
            new_w = dec.weights
            if not len(held):
                return None
            w = held.reindex(new_w.index).fillna(0.0)
            for s in new_w.index:
                if reference.country_of(s) in hit_countries:
                    w[s] = min(float(new_w[s]), float(w[s]))
            for s in due:
                w[s] = 0.0
                state["deferred"].pop(s, None)
            state["held"] = w[w > 0]
            return w.rename("weight")
        base = held.copy() if len(held) else (state["last"] if state["last"] is not None else pd.Series(dtype=float))
        w = base.copy()
        for s in due:
            w[s] = 0.0
            state["deferred"].pop(s, None)
        if s1_change:
            dec = self._peek_decide(t, view, held)
            new = set((dec.diagnostics.get("s1") or {}).get("positions", {}))
            if new == state["s1"] and not due:
                return None
            # Entrées et sorties de la poche : on reprend la cible complète (cœur + poche).
            state["s1"] = new
            w = dec.weights.copy()
            for s in due:
                w[s] = 0.0
        state["held"] = w[w > 0]
        return w

    # ---------------------------------------------------------------- explain

    def explain(self, asof: Any, panels: Any, symbol: str, held: Any = None) -> dict[str, Any]:
        """Explication d'une ligne à la date ``asof`` (décomposition du score et contraintes).

        Clés : ``symbol``, ``asof``, ``variant``, ``eligible`` / ``universe`` (filtres
        U1-U10 et motifs), ``blocks`` (par bloc : valeur brute, z, poids a priori et
        effectif, contribution ``w × z``), ``score`` (somme, malus S2, inclinaison,
        score final, rang / N), ``weight`` et ``caps`` (plafond de ligne détaillé,
        liquidité, secteur, pays, AES, motif de la construction), ``risk_flags``,
        ``notes`` (surcouches de l'analyste prises en compte, ou motif d'absence du
        module), ``momentum`` (modulateurs), ``valuation`` (``k_i = rf + β × 4 % + CRP``
        et DDM simple, **pour information** : n'entre pas dans le score), ``text`` (résumé
        en français) et ``banner``.
        """
        sym = str(symbol).upper().strip()
        dec = self.decide(asof, panels, held)
        if sym not in dec.universe.index:
            raise KeyError(f"{sym} absent des panels à la date {dec.asof.date()}")
        uni = dec.universe.loc[sym]
        st = dec.score.loc[sym] if sym in dec.score.index else pd.Series(dtype=float)
        sinfo = dec.diagnostics.get("score", {})
        w_eff = sinfo.get("weights_effective", {})
        w_pri = sinfo.get("weights_prior", {})
        blocks = {}
        for k in list(w_pri) + [b for b in _RESEARCH if b not in w_pri]:
            lab = SIGNAL_LABELS.get(k, k)
            raw_v = dec.signals.get(lab, pd.Series(dtype=float)).get(sym, np.nan)
            z = st.get(f"z_{k}", np.nan) if len(st) else np.nan
            we = float(w_eff.get(k, 0.0))
            blocks[lab] = {"raw": _f(raw_v), "z": _f(z), "weight_prior": float(w_pri.get(k, 0.0)), "weight": we,
                           "contribution": _f(we * z) if np.isfinite(_f(z)) else 0.0,
                           "research_only": k not in w_pri}
        final = dec.score["final"]
        rank = int(final.rank(ascending=False, method="first").get(sym)) if pd.notna(final.get(sym)) else None
        n_rank = int(final.notna().sum())
        pd_diag = dec.diagnostics.get("portfolio") or {}
        caps = pd_diag.get("caps", {})
        cap_info: dict[str, Any] = {}
        if caps:
            line_detail = caps.get("line_detail")
            cap_info = {
                "line": _f(caps.get("line", pd.Series(dtype=float)).get(sym, np.nan)),
                "line_detail": None if line_detail is None else line_detail.get(sym),
                "liquidity": _f(caps.get("liquidity", pd.Series(dtype=float)).get(sym, np.nan)),
                "upper": _f(caps.get("upper", pd.Series(dtype=float)).get(sym, np.nan)),
                "sector": _f(caps.get("sector", pd.Series(dtype=float)).get(self.sector_map.get(sym), np.nan)),
                "country": _f(caps.get("country", pd.Series(dtype=float)).get(reference.country_of(sym), np.nan)),
                "aes": dict(caps.get("aes", {})),
            }
        reason_pf = (pd_diag.get("reasons") or {}).get(sym, "")
        rk = dec.risk.loc[sym]
        flags = [c for c in str(rk["active"]).split(",") if c]
        notes = dec.diagnostics.get("notes", {})
        note_rows = []
        sc = notes.get("scores")
        if isinstance(sc, pd.DataFrame) and sym in sc.index:
            note_rows = [{k: sc.loc[sym, k] for k in sc.columns if k in ("score", "n_notes", "last_title",
                                                                          "last_event_type", "score_manual")}]
        notes_info = {"available": bool(notes.get("available")), "message": notes.get("message", ""),
                      "veto": list((notes.get("veto") or {}).get(sym, [])), "tilt": _f(rk.get("tilt", 0.0)),
                      "flags": list(rk.get("detail_notes") or []), "scores": note_rows,
                      "used_in_score": "inclinaison bornée ±0,5 écart-type et veto, appliqués après le score ; "
                                       "score des nouvelles S5 : poids nul (information)"}
        weight = float(dec.weights.get(sym, 0.0))
        val = self._valuation(dec, sym)
        mm = dec.diagnostics.get("momentum", {})
        text = self._explain_text(dec, sym, uni, blocks, st, rank, n_rank, weight, reason_pf, flags, val, notes_info)
        return {
            "symbol": sym, "asof": dec.asof, "variant": self.variant,
            "eligible": bool(uni["eligible"]),
            "universe": {k: (v.item() if hasattr(v, "item") else v) for k, v in uni.items()},
            "blocks": blocks,
            "score": {"raw": _f(st.get("raw", np.nan)), "quality_penalty": _f(rk.get("quality_penalty", 0.0)),
                      "s2_malus_sd": _f(st.get("malus", 0.0)), "s2": dec.diagnostics.get("s2", {}).get(sym),
                      "with_malus": _f(st.get("with_malus", np.nan)), "score": _f(st.get("score", np.nan)),
                      "tilt": _f(st.get("tilt", 0.0)), "final": _f(st.get("final", np.nan)),
                      "rank": rank, "n_ranked": n_rank, "n_valid_blocks": _f(st.get("n_valid_blocks", np.nan)),
                      "min_blocks": sinfo.get("min_blocks")},
            "weight": weight, "held_weight": _f(self._held(held, panels).get(sym, 0.0)),
            "caps": cap_info, "construction_reason": reason_pf,
            "risk_flags": {"active": flags, "block_buys": bool(rk["block_buys"]),
                           "detail": list(rk.get("detail_panel") or []) + list(rk.get("detail_notes") or []),
                           "country_rule": rk.get("country_rule", "")},
            "notes": notes_info,
            "momentum": {k: mm.get(k) for k in ("vol_scaling", "crash_filter", "multiplier", "history_start")},
            "valuation": val, "mode": dec.diagnostics.get("mode"), "messages": dec.messages,
            "text": text, "banner": BANNER,
        }

    def _valuation(self, dec: AlphaDecision, sym: str) -> dict[str, Any]:
        """Ligne de base de valorisation (§4.1, information seulement)."""
        d: _Data = dec.diagnostics["data"]
        out: dict[str, Any] = {"used_in_score": False}
        rf = float("nan")
        if d.market is not None and {"avg_per", "risk_premium"} <= set(d.market.columns) and len(d.market):
            try:
                rf = float(macro.ref_govt_rate(d.market, asof=d.t))
            except Exception:
                rf = float("nan")
        if not np.isfinite(rf):
            rf = 0.0575
            out["rf_note"] = "rf indisponible à la date : 5,75 % supposé (hypothèse)"
        beta = float("nan")
        if d.market_tr is not None:
            try:
                from brvm_alpha.quant import stats as qs

                tr = d.wide["tr_index"][sym].iloc[-505:]
                m = d.market_tr.reindex(tr.index).ffill()
                a = (tr / tr.shift(1) - 1.0)
                b = (m / m.shift(1) - 1.0)
                if d.w("stats_usable") is not None:
                    a = a.where(d.wide["stats_usable"][sym].iloc[-505:].astype("boolean").fillna(False).astype(bool))
                beta = float(qs.dimson_beta(a, b, lags=2))
            except Exception:
                beta = float("nan")
        beta_note = ""
        if not np.isfinite(beta):
            beta, beta_note = 1.0, "β indisponible : 1,0 supposé"
        try:
            k = float(macro.cost_of_equity(sym, beta=beta, rf=rf, erp=macro.ERP_BRVM))
        except KeyError:
            k = rf + beta * macro.ERP_BRVM
        px = float(d.wide["close_raw"].iloc[-1].get(sym, np.nan))
        dy = float(dec.signals.get("DY", pd.Series(dtype=float)).get(sym, np.nan))
        div = dy * px if np.isfinite(dy) and np.isfinite(px) else float("nan")
        ddm = div / k if np.isfinite(div) and k > 0 else float("nan")
        out.update({"rf": rf, "beta_dimson": beta, "erp": macro.ERP_BRVM, "cost_of_equity": k, "price": px,
                    "dividend_ordinary_net": div, "ddm_value_g0": ddm,
                    "ddm_gap": ddm / px - 1.0 if np.isfinite(ddm) and px > 0 else float("nan"),
                    "implied_growth": k - dy if np.isfinite(dy) else float("nan"),
                    "note": "estimation pour information (k = rf + β × 4 % + Σ λ·CRP ; DDM à croissance nulle) : "
                            "n'entre pas dans le score A" + (f" ; {beta_note}" if beta_note else "")})
        return out

    def _explain_text(self, dec: AlphaDecision, sym: str, uni: pd.Series, blocks: dict[str, Any], st: pd.Series,
                      rank: int | None, n_rank: int, weight: float, reason_pf: str, flags: list[str],
                      val: dict[str, Any], notes_info: dict[str, Any]) -> str:
        lines = [f"{sym} au {dec.asof.date():%d/%m/%Y}, variante {self.variant}."]
        if not bool(uni["eligible"]):
            lines.append(f"Non éligible : {uni['reasons'] or uni['reason']}.")
        else:
            top = sorted(((b, v) for b, v in blocks.items() if not v["research_only"]),
                         key=lambda kv: -abs(kv[1]["contribution"]))[:3]
            parts = [f"{b} {_num(v['contribution'], signed=True)}" for b, v in top]
            lines.append(f"Score final {_num(_f(st.get('final')), signed=True)} (rang {rank} sur {n_rank}) ; "
                         f"principales contributions : {', '.join(parts)}.")
            if _f(st.get("malus", 0.0)) < 0:
                lines.append("Malus S2 appliqué (détachement récent, nouvel achat).")
            if _f(st.get("tilt", 0.0)) != 0:
                lines.append(f"Inclinaison de l'analyste {_num(_f(st.get('tilt')), signed=True)} écart-type.")
        lines.append(f"Poids cible {_pct(weight)}" + (f" ({reason_pf})." if reason_pf else "."))
        if flags:
            lines.append("Filtres actifs : " + ", ".join(flags) + ".")
        if not notes_info["available"]:
            lines.append(f"Notes : {notes_info['message']}.")
        if np.isfinite(val.get("cost_of_equity", float("nan"))):
            ddm = ""
            if np.isfinite(val.get("ddm_value_g0", float("nan"))):
                ddm = f", valeur DDM (g = 0) {_fcfa(val['ddm_value_g0'])} pour un cours de {_fcfa(val['price'])}"
            lines.append(f"Pour information : coût des fonds propres estimé {_pct(val['cost_of_equity'])}{ddm} "
                         "(non utilisé dans le score).")
        lines.append(BANNER)
        return " ".join(lines)

    # --------------------------------------------------------------- moteur

    def engine_country_shocks(self, first_sessions: int = 1) -> pd.DataFrame | None:
        """Chocs pays sévères au format ``Backtester(country_shocks=...)`` (§4.3, §7.1.8)."""
        ev = self.country_events
        if ev is None or not len(ev):
            return None
        sev = ev[ev["rule"] == "severe"]
        if not len(sev):
            return None
        return pd.DataFrame({"country": sev["country"].to_numpy(), "date": sev["date"].to_numpy(),
                             "sessions": int(first_sessions)})


# ---------------------------------------------------------------------------
# Petites fonctions
# ---------------------------------------------------------------------------


def _bdays_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    """Nombre de jours ouvrés strictement entre ``a`` et ``b`` (calendrier sans fériés)."""
    a, b = pd.Timestamp(a).normalize(), pd.Timestamp(b).normalize()
    if b <= a:
        return -1
    return max(int(np.busday_count((a + pd.Timedelta(days=1)).date(), b.date())), 0)


def _uniq(xs: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(x for x in xs if x))


def _f(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def _pct(x: float, decimals: int = 1) -> str:
    if x is None or not np.isfinite(x):
        return "n.d."
    return f"{100.0 * x:.{decimals}f} %".replace(".", ",")


def _num(x: float, decimals: int = 2, signed: bool = False) -> str:
    """Nombre au format français (virgule décimale)."""
    if x is None or not np.isfinite(x):
        return "n.d."
    return (f"{x:+.{decimals}f}" if signed else f"{x:.{decimals}f}").replace(".", ",")


def _fcfa(x: float) -> str:
    if x is None or not np.isfinite(x):
        return "n.d."
    return f"{x:,.0f} FCFA".replace(",", " ")


def _d(x: Any) -> str:
    try:
        return f"{pd.Timestamp(x):%d/%m/%Y}"
    except (TypeError, ValueError):
        return str(x)
