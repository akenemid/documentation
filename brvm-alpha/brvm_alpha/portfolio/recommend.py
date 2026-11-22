"""Ordre de bataille : du poids cible au carnet d'ordres, « au titre et au franc près ».

Point d'entrée : :func:`recommend` ``(asof, capital, *, panels=None, holdings=None, cash=None,
variant=None, costs="central", notes_store=None, validation_dir="reports/validation_S1",
horizon_months=12, n_boot=5000, seed=0) -> OrdreDeBataille``.

Ce que contient l'ordre de bataille (spécification ``docs/SPECIFICATION_STRATEGIE.md``) :

1. **Choix de la variante** (:func:`choose_variant`) d'après ``reports/validation_S1/metrics.json`` :
   A si A est CANDIDAT (ou la variante promue par la règle du §3.4), REF (« indice discipliné »,
   D8) si A est REJETÉ ; test S1 non exécuté ou statut INDÉTERMINÉ : REF par défaut, A affiché en
   comparaison, avec un avertissement. Tant que rien n'est PROMU, la phrase
   :data:`PHRASE_ETUDE` est affichée.
2. **Ordres** : nombre exact de titres (quotité 1, arrondi vers le bas), poids cible et réalisé,
   cours de référence, bornes de la prochaine séance (:func:`brvm_alpha.quant.macro.price_band`),
   prix limites (:func:`limit_prices`), montant brut, coûts détaillés (:func:`order_costs` :
   courtage, TVA sur le courtage, BRVM, DC/BR, demi-spread estimé, impact κ·√π) et montant net.
3. **Exécution** (:func:`participation_schedule`, :func:`plan_execution`) : tranches à au plus 10 %
   de la MDV63 en valeur par séance, ventes avant achats, règlement J+2 (depuis le 04/12/2025) :
   un achat financé par une vente n'utilise le produit qu'à partir de la date de règlement ; les
   liquidités initiales sont utilisées d'abord. La provision d'un achat est son **pire cas**
   (exécution au prix limite, frais explicites compris) : le plan est finançable même si tout est
   exécuté à la limite.
4. **Revenus** (:func:`dividend_schedule`) : dividendes attendus sur 12 mois (dernier dividende net
   publié au BOC, ajusté des divisions, mois de détachement habituel tiré de l'historique, absences
   annoncées de ``reference.py``), IRVM du pays de l'émetteur (:func:`irvm_rate`), revenu net.
5. **Distribution à 12 mois** (:func:`return_distribution`) : bootstrap stationnaire (blocs de 8
   semaines) des rendements hebdomadaires TR des lignes aux poids réalisés et du Composite TR, tirés
   **ensemble** ; fenêtre d'estimation S0 seulement tant que le registre n'indique pas que S1 a été
   exécuté (:func:`estimation_window`). C'est une **distribution historique, pas une prévision**.
6. **Stress** (§9.3) : ``brvm_alpha.portfolio.stress`` s'il existe, sinon les chocs de
   :func:`stress_scenarios`.
7. **Déclencheurs de revue** : filtres R actifs, drawdown relatif, événements à venir (dates ex,
   AG, publications, événements pays), prochain rebalancement, notes de l'analyste, indices.
   **Notes de l'analyste, deux instants** : la date des cours est celle du dernier BOC ; les notes
   suivent par défaut la règle stricte à cette date (mode historique). Avec ``notes_known_at``
   (mode direct, passé par la ligne de commande, l'interface et le rapport à la dernière séance du
   panel), les notes connues à cet instant sont appliquées à la séance d'exécution : veto,
   inclinaisons et filtres R entrent dans la décision ; chaque achat bloqué par une note est écrit
   en clair (règle, note, fin du blocage, comment le lever) avec son effet sur les poids cibles.
8. **Explications** (``BrvmAlpha.explain``) des titres retenus et des 5 premiers écartés.

**Honnêteté** : rien ici ne garantit un gain. Les coûts, l'impact, les dates projetées et la
distribution sont des **estimations** sous **hypothèses** (listées dans chaque ordre de bataille) ;
seuls les cours et dividendes publiés au BOC, les règles de marché et le statut du registre sont
des **faits**.
"""

from __future__ import annotations

import copy
import html
import importlib
import inspect
import json
import math
import re
import sys
import time
import types
import warnings
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from brvm_alpha import reference, settings
from brvm_alpha.config import CostModel, TaxModel
from brvm_alpha.quant import macro

__all__ = [
    "BANNER",
    "DEFAULT_SEED",
    "FIXED_HOLIDAYS",
    "IRVM_HISTORY",
    "OrdreDeBataille",
    "PHRASE_ETUDE",
    "choose_variant",
    "ceil_to_tick",
    "dividend_schedule",
    "estimation_window",
    "fee_breakdown",
    "floor_to_tick",
    "future_sessions",
    "irvm_rate",
    "limit_prices",
    "ordre_de_bataille",
    "order_costs",
    "participation_schedule",
    "plan_execution",
    "recommend",
    "fr_texte",
    "return_distribution",
    "round_fcfa",
    "s1_executed",
    "settlement_date",
    "stationary_bootstrap_indices",
    "stress_scenarios",
    "weekly_tr_returns",
]

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PANEL_DIR = ROOT / "data" / "panel"
DEFAULT_VALIDATION_DIR = "reports/validation_S1"
DEFAULT_REGISTRY_PATH = ROOT / "reports" / "trials.parquet"

#: Bandeau permanent (§10).
BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."
#: Phrase affichée tant qu'aucune variante n'est PROMUE (§8.3).
PHRASE_ETUDE = ("recommandation à titre d'étude ; suivi réel (paper trading) requis avant tout "
                "engagement d'argent réel")
#: Échantillons (§8.1).
S1_START = pd.Timestamp("2017-01-02")
S1_END = pd.Timestamp("2022-11-16")
S0_START = pd.Timestamp("2022-11-17")
S2_START = pd.Timestamp("2026-12-01")

DEFAULT_SEED = 0
LIMIT_TOLERANCE = 0.01  # tolérance des prix limites autour du dernier cours
MAX_PARTICIPATION = 0.10  # part maximale de la MDV63 (valeur) par séance (§6, §7.1)
MAX_CARRY_SESSIONS = 10  # report maximal d'un ordre (§7.1.1)
BLOCK_WEEKS = 8  # bloc moyen du bootstrap stationnaire (§8.2)
WEEKS_PER_YEAR = 52
AGO_TO_EX_DAYS = 42  # date ex = AGO + 42 jours en médiane (§5.4)
DIVIDEND_MAX_AGE_DAYS = 456  # garde-fou de 15 mois (§3.2) : au-delà, aucun dividende supposé
REVIEW_REL_UNDERPERF_63 = -0.25  # revue obligatoire d'une ligne (§9.1)
#: Jours fériés à date fixe absents du calendrier des BOC chaque année 2017-2026 (sessions.parquet) :
#: 01/01, 01/05, 07/08, 15/08, 01/11, 15/11, 25/12. Les fêtes mobiles (Pâques, Tabaski…) ne sont
#: pas connues à l'avance : le calendrier futur est une **hypothèse**.
FIXED_HOLIDAYS: tuple[tuple[int, int], ...] = ((1, 1), (5, 1), (8, 7), (8, 15), (11, 1), (11, 15), (12, 25))
#: Échéances réglementaires de publication (R7, §5.6 et avis 214-2026 / 291-2025).
PUBLICATION_DEADLINES: tuple[tuple[int, int, str], ...] = (
    (4, 30, "comptes annuels de l'exercice précédent et activité du T1 (échéance R7)"),
    (10, 31, "comptes semestriels et activité du T3 (échéance R7)"),
)
_PUB_TYPES = {"RES_ANNUAL": "comptes annuels", "RES_S1": "comptes semestriels", "ACT_Q1": "activité du T1",
              "ACT_Q3": "activité du T3", "AG_CONVOCATION": "convocation d'AG"}
_BENCH = "__TR__"

#: Historique (daté) des taux d'IRVM personne physique, quand il diffère du taux actuel de
#: ``config.TaxModel`` (spéc. §7.3) : ``(date de début, taux)``. Valeurs antérieures **inférées** ou
#: **[NON VÉRIFIÉ]** : elles ne servent qu'à reconstituer le brut d'un dividende net publié avant le
#: changement de taux. Le taux en vigueur est toujours celui de ``TaxModel``.
IRVM_HISTORY: dict[str, tuple[tuple[str | None, float], ...]] = {
    "CI": ((None, 0.10), ("2025-01-01", 0.12)),  # 10 % jusqu'en 2024 (inférence), 12 % ensuite
    "SN": ((None, 0.125), ("2026-01-01", 0.10)),  # avant 2026 : nets compatibles avec 12,5 % (NV)
    "ML": ((None, 0.10), ("2025-01-01", 0.07)),  # 10 % en 2024 (NV), 7 % en 2025-2026
}
#: Pays dont le taux d'IRVM est inconnu ou non vérifié (le net publié au BOC fait foi).
IRVM_UNVERIFIED = {"BF": "12,5 % [NON VÉRIFIÉ]", "TG": "inconnu (13 % supposé) : le net du BOC fait foi",
                   "GW": "10 % [NON VÉRIFIÉ]", "BJ": "selon l'émetteur (inférences)"}

_STATUS_ALIASES = {"REJETE": "REJETÉ", "REJETÉ": "REJETÉ", "CANDIDAT": "CANDIDAT", "PROMU": "PROMU",
                   "INDETERMINE": "INDÉTERMINÉ", "INDÉTERMINÉ": "INDÉTERMINÉ"}
NOT_TESTED = "NON TESTÉ"


# ---------------------------------------------------------------------------
# Arrondis : franc, pas de cotation, prix limites
# ---------------------------------------------------------------------------


def round_fcfa(x: float) -> int:
    """Arrondi au franc CFA le plus proche (demi vers le haut en valeur absolue).

    Le FCFA n'a pas de subdivision : chaque composante de coût est arrondie séparément, puis
    sommée (convention d'un avis d'opéré).
    """
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"montant non fini : {x!r}")
    sign = -1 if v < 0 else 1
    return int(sign * math.floor(abs(v) + 0.5 + 1e-9))


def floor_to_tick(price: float) -> float:
    """Arrondi **inférieur** au pas de cotation (``macro.tick_size`` : 1 FCFA sous 100, sinon 5)."""
    p = float(price)
    step = float(macro.tick_size(p))
    return float(math.floor(p / step + 1e-9) * step)


def ceil_to_tick(price: float) -> float:
    """Arrondi **supérieur** au pas de cotation (1 FCFA sous 100 FCFA, sinon 5)."""
    p = float(price)
    step = float(macro.tick_size(p))
    v = float(math.ceil(p / step - 1e-9) * step)
    # Passage de la frontière de 100 FCFA : le résultat doit être sur la grille de son propre pas.
    if v >= 100 and v % 5:
        v = float(math.ceil(v / 5.0) * 5.0)
    return v


def limit_prices(last_close: float, *, reference_price: float | None = None,
                 tolerance: float = LIMIT_TOLERANCE) -> dict[str, float]:
    """Bornes de la prochaine séance et prix limites d'un ordre (spéc. §7.1.3).

    * bornes : ``macro.price_band(réf)``, ``réf`` = cours de référence de la prochaine séance
      (par défaut le dernier cours ; la référence ex-dividende si le détachement est connu) ;
    * achat : ``min(borne haute ; dernier cours × (1 + tolérance))`` arrondi au pas **inférieur** ;
    * vente : ``max(borne basse ; dernier cours × (1 − tolérance))`` arrondi au pas **supérieur** ;
    * titre dont le pas dépasse la tolérance (sous 100 FCFA avec un pas de 1, sous 500 FCFA avec un pas
      de 5) : la limite serait égale au dernier cours ; elle est portée à **un pas** au-dessus (achat)
      ou au-dessous (vente) du dernier cours, dans la bande (correction du 22/11/2026 : ETIT à 57 FCFA,
      limite 57 et coûts implicites mis à zéro).

    Exemple : dernier cours 4 385 FCFA ⇒ bornes (4 060 ; 4 710), achat 4 425, vente 4 345.
    """
    c = float(last_close)
    if not math.isfinite(c) or c <= 0:
        raise ValueError(f"dernier cours invalide : {last_close!r}")
    ref = c if reference_price is None else float(reference_price)
    low, high = macro.price_band(ref)
    buy = floor_to_tick(min(high, c * (1.0 + tolerance)))
    sell = ceil_to_tick(max(low, c * (1.0 - tolerance)))
    one_tick = False
    if buy <= c and high > c:
        buy = max(buy, floor_to_tick(min(high, c + float(macro.tick_size(c)))))
        one_tick = True
    if sell >= c and low < c:
        sell = min(sell, ceil_to_tick(max(low, c - float(macro.tick_size(max(c - 0.5, 0.5))))))
        one_tick = True
    return {"reference": ref, "low": float(low), "high": float(high), "buy": buy, "sell": sell,
            "tick": float(macro.tick_size(c)), "tolerance": float(tolerance), "un_pas": one_tick}


# ---------------------------------------------------------------------------
# Fiscalité des dividendes (IRVM)
# ---------------------------------------------------------------------------


def irvm_rate(symbol: str, date: Any = None, taxes: TaxModel | None = None) -> float:
    """Taux d'IRVM (personne physique) d'un dividende de ``symbol`` payé à ``date`` (spéc. §7.3).

    Exceptions par émetteur d'abord (``TaxModel.issuer_withholding`` : LNBB et BICB 5 %, BOAB
    10 %), puis taux du pays de l'émetteur (``reference.country_of``) : CI 12 %, SN 10 %, BF 12,5 %
    (NV), ML 7 %, NE 7 %… ``date`` antérieure à un changement de taux connu
    (:data:`IRVM_HISTORY`) : taux de l'époque (CI 10 % avant 2025, SN 12,5 % avant 2026).
    """
    tm = taxes if taxes is not None else TaxModel()
    sym = str(symbol).upper().strip()
    if sym in tm.issuer_withholding:
        return float(tm.issuer_withholding[sym])
    c = reference.country_of(sym)
    current = float(tm.dividend_withholding.get(c, 0.0))
    hist = IRVM_HISTORY.get(c)
    if date is None or not hist:
        return current
    d = pd.Timestamp(date).normalize()
    last_start = hist[-1][0]
    if last_start is not None and d >= pd.Timestamp(last_start):
        return current
    rate = current
    for start, r in hist:
        if start is None or d >= pd.Timestamp(start):
            rate = float(r)
    return rate


# ---------------------------------------------------------------------------
# Coûts d'un ordre (§7.2)
# ---------------------------------------------------------------------------


def _cost_model(costs: str | CostModel | None, cfg: Mapping[str, Any] | None = None) -> tuple[CostModel, str]:
    if isinstance(costs, CostModel):
        return costs, "fourni"
    name = "central" if costs is None else str(costs)
    return settings.cost_scenario(name, cfg), name


def fee_breakdown(amount: float, costs: CostModel) -> dict[str, int]:
    """Frais **explicites** (facturés) d'une exécution de montant ``amount`` FCFA, au franc près.

    ``courtage = max(taux SGI × montant ; minimum)`` ; ``TVA = taux × courtage`` (arrondi) ;
    ``BRVM = 0,20 %`` ; ``DC/BR = 0,10 %`` ; redevance AMF-UMOA (0 : introuvable). Chaque
    composante est arrondie au franc le plus proche.
    """
    a = float(amount)
    if a <= 0:
        return {"courtage": 0, "tva": 0, "brvm": 0, "dcbr": 0, "redevance": 0, "explicites": 0}
    courtage = round_fcfa(max(costs.sgi_commission * a, float(costs.min_ticket_fcfa)))
    tva = round_fcfa(costs.vat_on_commission * courtage)
    brvm = round_fcfa(costs.brvm_fee * a)
    dcbr = round_fcfa(costs.dcbr_fee * a)
    red = round_fcfa(costs.regulator_fee * a)
    return {"courtage": courtage, "tva": tva, "brvm": brvm, "dcbr": dcbr, "redevance": red,
            "explicites": courtage + tva + brvm + dcbr + red}


def order_costs(qty: int, price: float, costs: CostModel, *, side: str = "achat", half_spread: float = 0.0,
                mdv63: float | None = None, tranches: Sequence[int] | None = None,
                limit: float | None = None) -> dict[str, Any]:
    """Coûts détaillés d'un ordre de ``qty`` titres au cours ``price`` (estimation centrale, §7.2).

    Par tranche ``k`` (une par séance, :func:`participation_schedule`) de montant
    ``A_k = q_k × cours`` : frais explicites (:func:`fee_breakdown`), demi-spread
    ``s × A_k`` et impact ``κ × √π_k × A_k`` avec ``π_k = A_k / MDV63`` (participation estimée à
    la valeur médiane échangée ; ``MDV63`` absente ou nulle : π = 1, signalé). Montant net :
    ``brut + coûts`` à l'achat, ``brut − coûts`` à la vente. Les coûts implicites (demi-spread,
    impact) sont des **estimations** : ils se lisent dans le prix d'exécution, pas sur l'avis d'opéré.
    ``limit`` (prix limite) : un ordre à cours limité ne peut pas coûter plus que
    ``|limite − cours| × qty`` en coûts implicites ; l'estimation est plafonnée (``implicites_plafonnes``).
    """
    q = int(qty)
    if q < 0:
        raise ValueError("qty doit être >= 0")
    side_n = _side(side)
    px = float(price)
    parts = list(tranches) if tranches is not None else ([q] if q > 0 else [])
    if sum(int(t) for t in parts) != q:
        raise ValueError("la somme des tranches doit égaler qty")
    out = {"courtage": 0, "tva": 0, "brvm": 0, "dcbr": 0, "redevance": 0, "explicites": 0,
           "demi_spread": 0, "impact": 0}
    brut = 0
    max_pi = 0.0
    pi_known = mdv63 is not None and np.isfinite(mdv63) and float(mdv63) > 0
    for t in parts:
        a = int(t) * px
        if a <= 0:
            continue
        brut += round_fcfa(a)
        f = fee_breakdown(a, costs)
        for k in ("courtage", "tva", "brvm", "dcbr", "redevance", "explicites"):
            out[k] += f[k]
        pi = min(a / float(mdv63), 1.0) if pi_known else 1.0
        max_pi = max(max_pi, pi)
        out["demi_spread"] += round_fcfa(max(float(half_spread), 0.0) * a)
        out["impact"] += round_fcfa(float(costs.impact_coef) * math.sqrt(pi) * a)
    out["implicites"] = out["demi_spread"] + out["impact"]
    out["implicites_plafonnes"] = False
    if limit is not None and np.isfinite(limit) and q > 0:
        room = (float(limit) - px) if side_n == "achat" else (px - float(limit))
        cap = max(round_fcfa(room * q), 0)
        if out["implicites"] > cap:
            ds = round_fcfa(out["demi_spread"] * cap / out["implicites"]) if out["implicites"] else 0
            out["demi_spread"], out["impact"] = ds, cap - ds
            out["implicites"] = cap
            out["implicites_plafonnes"] = True
    out["total"] = out["explicites"] + out["implicites"]
    out["brut"] = brut
    out["net"] = brut + out["total"] if side_n == "achat" else brut - out["total"]
    out["participation_max"] = max_pi
    out["participation_connue"] = bool(pi_known)
    out["sens"] = side_n
    return out


def _side(side: str) -> str:
    s = str(side).strip().lower()
    if s in ("achat", "buy", "a"):
        return "achat"
    if s in ("vente", "sell", "v"):
        return "vente"
    raise ValueError(f"sens inconnu : {side!r} (achat ou vente)")


def _worst_case(tranches: Sequence[int], limit: float, costs: CostModel, side: str) -> int:
    """Pire cas d'un ordre : provision d'un achat (``q × limite + frais``) ou encaissement minimal
    d'une vente (``q × limite − frais``), tranche par tranche, au franc près."""
    total = 0
    for t in tranches:
        a = int(t) * float(limit)
        if a <= 0:
            continue
        f = fee_breakdown(a, costs)["explicites"]
        total += round_fcfa(a) + f if side == "achat" else round_fcfa(a) - f
    return int(total)


# ---------------------------------------------------------------------------
# Calendrier, participation, règlement
# ---------------------------------------------------------------------------


def _is_fixed_holiday(d: pd.Timestamp) -> bool:
    return (d.month, d.day) in FIXED_HOLIDAYS


def future_sessions(asof: Any, n: int, sessions: Any = None) -> list[pd.Timestamp]:
    """Les ``n`` séances qui suivent ``asof`` (strictement).

    Séances connues du calendrier ``sessions`` d'abord, puis jours ouvrés sans les fériés à date
    fixe (:data:`FIXED_HOLIDAYS`) : **hypothèse** (fêtes mobiles inconnues à l'avance).
    """
    d = pd.Timestamp(asof).normalize()
    cal = macro.session_index(sessions)
    out = [pd.Timestamp(x) for x in cal[cal > d]][: int(n)]
    cur = max([d] + out)
    while len(out) < int(n):
        cur = cur + pd.Timedelta(days=1)
        if cur.weekday() < 5 and not _is_fixed_holiday(cur):
            out.append(cur)
    return out


def expected_missing_sessions(last_session: Any, today: Any) -> list[pd.Timestamp]:
    """Séances attendues **après** le dernier BOC du panel et **avant** ``today`` (exclu : le BOC du jour
    n'est publié qu'après la clôture) : jours ouvrés hors fériés à date fixe (hypothèse, fêtes mobiles
    inconnues). Une liste non vide signale un panel en retard (lancer ``update``)."""
    a = pd.Timestamp(last_session).normalize() + pd.Timedelta(days=1)
    b = pd.Timestamp(today).normalize() - pd.Timedelta(days=1)
    if b < a:
        return []
    return [pd.Timestamp(d) for d in pd.bdate_range(a, b) if not _is_fixed_holiday(pd.Timestamp(d))]


def _session_calendar(asof: Any, sessions: Any, horizon_days: int = 800) -> pd.DatetimeIndex:
    """Calendrier passé connu + séances futures (hypothèse) jusqu'à ``horizon_days`` jours."""
    d = pd.Timestamp(asof).normalize()
    past = macro.session_index(sessions)
    past = past[past <= d]
    fut = future_sessions(d, int(horizon_days * 5 / 7) + 10, sessions)
    return pd.DatetimeIndex(list(past) + fut).unique().sort_values()


def settlement_date(trade_date: Any, calendar: Sequence[pd.Timestamp] | pd.DatetimeIndex) -> pd.Timestamp:
    """Date de règlement-livraison : ``trade_date`` + ``macro.settlement_lag`` séances (J+2 depuis
    le 04/12/2025, J+3 avant), sur le calendrier fourni."""
    t = pd.Timestamp(trade_date).normalize()
    lag = int(macro.settlement_lag(t))
    cal = pd.DatetimeIndex(calendar)
    after = cal[cal > t]
    if len(after) < lag:
        raise ValueError("calendrier trop court pour le règlement")
    return pd.Timestamp(after[lag - 1])


def participation_schedule(qty: int, price: float, mdv63: float | None,
                           max_participation: float = MAX_PARTICIPATION) -> list[int]:
    """Tranches (titres par séance) d'un ordre à au plus ``max_participation`` × MDV63 en valeur.

    ``m = ⌊max_participation × MDV63 / cours⌋`` titres au plus par séance (au moins 1 : un seul
    titre peut alors dépasser 10 %, c'est signalé par l'appelant) ; ``n = ⌈qty / m⌉`` séances ;
    répartition la plus égale possible (les premières tranches reçoivent le reste). MDV63
    absente ou nulle : une seule tranche (ordre à cours limité, participation non mesurable).
    """
    q = int(qty)
    if q <= 0:
        return []
    px = float(price)
    if mdv63 is None or not np.isfinite(mdv63) or float(mdv63) <= 0 or px <= 0:
        return [q]
    m = max(int(math.floor(float(max_participation) * float(mdv63) / px + 1e-9)), 1)
    n = int(math.ceil(q / m))
    base, rem = divmod(q, n)
    return [base + 1] * rem + [base] * (n - rem)


def plan_execution(orders: Sequence[Mapping[str, Any]], cash: float, calendar: Sequence[pd.Timestamp] | pd.DatetimeIndex,
                   costs: CostModel, *, max_sessions: int = 260) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Échéancier par séance : **ventes d'abord**, puis achats financés (pire cas).

    ``orders`` : dictionnaires ``symbol, side, qty, tranches, limit, ref_price, half_spread, mdv63``.
    ``calendar`` : séances **futures** (la première est la séance d'exécution t + 1).

    Règles :

    * chaque ordre place au plus une tranche par séance (participation ≤ 10 % de la MDV63) ;
    * une vente encaisse au minimum ``q × limite − frais`` à sa **date de règlement** (J+2) ; ce
      produit ne finance un achat qu'à partir de cette date ;
    * un achat mobilise sa provision pire cas (``q × limite + frais``) dès la négociation ;
      les **liquidités initiales** sont utilisées d'abord, puis le produit des ventes réglées ;
    * une tranche non finançable est décalée à la séance suivante (et réduite si nécessaire).
    """
    cal = pd.DatetimeIndex(calendar)
    if not len(cal):
        raise ValueError("calendrier vide")
    sells = [o for o in orders if o["side"] == "vente" and int(o["qty"]) > 0]
    buys = [o for o in orders if o["side"] == "achat" and int(o["qty"]) > 0]
    rows: list[dict[str, Any]] = []
    receipts: list[tuple[pd.Timestamp, int, str]] = []
    for o in sells:
        for k, q in enumerate(o["tranches"]):
            if k >= len(cal):
                raise ValueError("calendrier trop court pour les ventes")
            date = cal[k]
            sett = settlement_date(date, cal)
            proceeds = _worst_case([q], o["limit"], costs, "vente")
            receipts.append((sett, proceeds, o["symbol"]))
            rows.append({"seance": k + 1, "date": date, "symbole": o["symbol"], "sens": "vente", "titres": int(q),
                         "prix_limite": float(o["limit"]), "montant_ref": round_fcfa(q * float(o["ref_price"])),
                         "pire_cas": proceeds, "date_reglement": sett, "financement": "",
                         "liquidites_initiales_utilisees": 0, "produit_ventes_utilise": 0})
    init_left = int(math.floor(float(cash)))
    sales_avail = 0
    credited: set[int] = set()
    queues = {o["symbol"]: deque(int(t) for t in o["tranches"]) for o in buys}
    s = 0
    unfunded: dict[str, int] = {}
    while any(queues.values()):
        if s >= min(len(cal), max_sessions):
            unfunded = {k: int(sum(v)) for k, v in queues.items() if v}
            break
        date = cal[s]
        for i, (sd, amt, _sym) in enumerate(receipts):
            if i not in credited and sd <= date:
                sales_avail += int(amt)
                credited.add(i)
        for o in buys:
            qd = queues[o["symbol"]]
            if not qd:
                continue
            want = qd[0]
            avail = init_left + sales_avail
            q = want
            while q > 0 and _worst_case([q], o["limit"], costs, "achat") > avail:
                unit = float(o["limit"]) * (1.0 + costs.rate())
                q = min(q - 1, int(math.floor(avail / unit)) if unit > 0 else 0)
            if q <= 0:
                continue
            need = _worst_case([q], o["limit"], costs, "achat")
            use_init = min(init_left, need)
            use_sales = need - use_init
            init_left -= use_init
            sales_avail -= use_sales
            if q == want:
                qd.popleft()
            else:
                qd[0] = want - q
            fin = ("liquidités initiales" if use_sales == 0 else
                   "produit de ventes réglées" if use_init == 0 else "liquidités initiales + produit de ventes réglées")
            rows.append({"seance": s + 1, "date": date, "symbole": o["symbol"], "sens": "achat", "titres": int(q),
                         "prix_limite": float(o["limit"]), "montant_ref": round_fcfa(q * float(o["ref_price"])),
                         "pire_cas": need, "date_reglement": settlement_date(date, cal), "financement": fin,
                         "liquidites_initiales_utilisees": int(use_init), "produit_ventes_utilise": int(use_sales)})
        s += 1
    for i, (sd, amt, _sym) in enumerate(receipts):
        if i not in credited:
            sales_avail += int(amt)
    cols = ["seance", "date", "symbole", "sens", "titres", "prix_limite", "montant_ref", "pire_cas", "date_reglement",
            "financement", "liquidites_initiales_utilisees", "produit_ventes_utilise"]
    tab = pd.DataFrame(rows, columns=cols)
    if len(tab):
        tab["_o"] = (tab["sens"] == "achat").astype(int)
        tab = tab.sort_values(["seance", "_o", "symbole"]).drop(columns="_o").reset_index(drop=True)
    info = {"liquidites_initiales_restantes_pire_cas": int(init_left),
            "produit_ventes_non_utilise_pire_cas": int(sales_avail),
            "liquidites_finales_pire_cas": int(init_left + sales_avail),
            "non_finance": unfunded, "n_seances": int(tab["seance"].max()) if len(tab) else 0}
    return tab, info


# ---------------------------------------------------------------------------
# Choix de la variante (statut du test S1)
# ---------------------------------------------------------------------------


def _resolve(path: str | Path | None, default: str | Path) -> Path:
    p = Path(default if path is None else path)
    return p if p.is_absolute() else ROOT / p


def s1_executed(registry_path: str | Path | None = None) -> tuple[bool, str]:
    """Le registre (``reports/trials.parquet``) contient-il des essais S1 « exécuté » ?"""
    path = _resolve(registry_path, DEFAULT_REGISTRY_PATH)
    if not path.exists():
        return False, f"registre des essais absent ({path})"
    try:
        from brvm_alpha.backtest.walkforward import TrialRegistry

        ex = TrialRegistry.load(path).executed("S1")
    except Exception as exc:  # registre illisible : prudence, S1 réputé non exécuté
        return False, f"registre illisible ({exc.__class__.__name__} : {exc}) : S1 réputé non exécuté"
    n = int(len(ex))
    if n:
        return True, f"registre : {n} essai(s) S1 au statut « exécuté »"
    return False, "registre : aucun essai S1 exécuté (échantillon vierge)"


def _norm_status(x: Any) -> str | None:
    if x is None:
        return None
    s = str(x).strip().upper()
    return _STATUS_ALIASES.get(s, s or None)


def choose_variant(variant: str | None = None, validation_dir: str | Path | None = DEFAULT_VALIDATION_DIR,
                   registry_path: str | Path | None = None) -> dict[str, Any]:
    """Variante de l'ordre de bataille d'après le test S1 (``metrics.json``) et le registre.

    * ``variant`` fourni : il est appliqué (hors règle, signalé) ;
    * ``metrics.json`` absent, illisible ou d'un autre échantillon que S1 : **REF** (« indice
      discipliné », D8), **A en comparaison**, avertissement « test S1 non exécuté » ;
    * A CANDIDAT ou PROMU : **A**, ou la variante promue par la règle du §3.4 (``promue`` vrai dans
      ``metrics["promotion"]``, statut CANDIDAT ou PROMU ; meilleur actif net si plusieurs) ;
    * A REJETÉ : **REF** ;
    * A INDÉTERMINÉ (ou statut inconnu) : **REF**, A en comparaison, avertissement.

    ``phrase_etude`` est vrai tant que la variante retenue n'est pas PROMUE.
    """
    vdir = _resolve(validation_dir, DEFAULT_VALIDATION_DIR)
    s1_done, s1_msg = s1_executed(registry_path)
    out: dict[str, Any] = {"variante": "REF", "comparaison": "A", "statut_A": NOT_TESTED, "statut": NOT_TESTED,
                           "statut_REF": None, "variante_promue": None, "s1_execute": s1_done, "registre": s1_msg,
                           "metrics_json": None, "motif": "", "avertissements": [], "impose": False}
    path = vdir / "metrics.json"
    m: dict[str, Any] | None = None
    if path.exists():
        try:
            m = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            out["avertissements"].append(f"metrics.json illisible ({exc.__class__.__name__}) : test S1 réputé non exécuté")
            m = None
        if m is not None and str(m.get("echantillon", "S1")).upper() != "S1":
            out["avertissements"].append(f"metrics.json porte sur l'échantillon {m.get('echantillon')!r}, pas sur S1 : ignoré")
            m = None
    if m is not None:
        out["metrics_json"] = str(path)
        variants = m.get("variantes") or {}
        out["statut_A"] = _norm_status((variants.get("A") or {}).get("statut")) or "INDÉTERMINÉ"
        out["statut_REF"] = _norm_status((variants.get("REF") or {}).get("statut"))
        res_s1: dict[str, Any] = {}
        for code, vd in variants.items():
            run = ((m.get("runs") or {}).get((vd or {}).get("run_id")) or {})
            act = run.get("actif_tr_an")
            res_s1[str(code)] = {"statut": _norm_status((vd or {}).get("statut")),
                                 "actif_tr_an": float(act) if isinstance(act, (int, float)) else None}
        out["resultats_s1"] = res_s1
        if not s1_done:
            out["avertissements"].append("incohérence : metrics.json de S1 présent mais le registre n'indique aucun "
                                         "essai S1 exécuté ; vérifier reports/trials.parquet")
    st_a = out["statut_A"]
    if variant is not None:
        code = str(variant).upper().strip()
        out.update({"variante": code, "comparaison": None, "impose": True,
                    "motif": f"variante {code} imposée par l'appelant (hors règle de choix)"})
        out["statut"] = (st_a if code == "A" else
                         _norm_status(((m or {}).get("variantes") or {}).get(code, {}).get("statut")) or
                         (NOT_TESTED if m is None else "INDÉTERMINÉ"))
        if m is None:
            out["avertissements"].append("test S1 non exécuté : aucune variante n'a de statut de validation")
    elif m is None:
        out.update({"variante": "REF", "comparaison": "A", "statut": NOT_TESTED,
                    "motif": "test S1 non exécuté : « indice discipliné » (REF, D8) par défaut, A en comparaison"})
        out["avertissements"].append("Le test unique S1 n'a pas encore été exécuté : aucune variante n'est validée. "
                                     "L'ordre suit l'indice discipliné (REF) ; la variante A est affichée pour "
                                     "comparaison seulement.")
    elif st_a in ("CANDIDAT", "PROMU"):
        chosen, status = "A", st_a
        promo = [r for r in ((m.get("promotion") or {}).get("criteres") or [])
                 if r.get("promue") is True and str(r.get("variante")) != "A"]
        promo = [r for r in promo
                 if _norm_status(((m.get("variantes") or {}).get(str(r["variante"])) or {}).get("statut"))
                 in ("CANDIDAT", "PROMU")]
        if promo:
            best = max(promo, key=lambda r: float(r.get("actif_net_an") or -np.inf))
            chosen = str(best["variante"])
            status = _norm_status((m["variantes"].get(chosen) or {}).get("statut"))
            out["variante_promue"] = chosen
        out.update({"variante": chosen, "comparaison": "REF", "statut": status,
                    "motif": (f"A est {st_a} sur S1" + (f" ; {chosen} promue par la règle du §3.4" if chosen != "A"
                                                        else ""))})
    elif st_a == "REJETÉ":
        out.update({"variante": "REF", "comparaison": None, "statut": out["statut_REF"] or "RÉFÉRENCE",
                    "motif": "A est REJETÉ sur S1 : mode « indice discipliné » (§8.3, D8), aucune promesse d'alpha"})
    else:
        out.update({"variante": "REF", "comparaison": "A", "statut": out["statut_REF"] or "INDÉTERMINÉ",
                    "motif": f"statut de A sur S1 : {st_a} : « indice discipliné » (REF) par défaut, A en comparaison"})
        out["avertissements"].append(f"Statut de A sur S1 : {st_a} (données insuffisantes ou statut non reconnu) : "
                                     "aucun suivi réel autorisé par D7 ; REF par défaut.")
    out["promu"] = out["statut"] == "PROMU"
    out["phrase_etude"] = not out["promu"]
    return out


# ---------------------------------------------------------------------------
# Accès aux panels
# ---------------------------------------------------------------------------


def _get(panels: Mapping[str, Any], key: str) -> Any:
    try:
        return panels.get(key) if isinstance(panels, Mapping) else panels[key]
    except (KeyError, TypeError):
        return None


def _wide_upto(panels: Mapping[str, Any], key: str, t: pd.Timestamp) -> pd.DataFrame | None:
    df = _get(panels, key)
    if not isinstance(df, pd.DataFrame):
        return None
    return df.loc[df.index <= t]


def _decision_date(panels: Mapping[str, Any], asof: Any) -> pd.Timestamp:
    close = _get(panels, "close_raw")
    close = close if isinstance(close, pd.DataFrame) else _get(panels, "close")
    if not isinstance(close, pd.DataFrame) or not len(close):
        raise ValueError("panels : cours de clôture absents (close_raw / close)")
    idx = close.index[close.index <= pd.Timestamp(asof).normalize()]
    if not len(idx):
        raise ValueError(f"aucune séance au plus tard le {pd.Timestamp(asof).date()}")
    return pd.Timestamp(idx[-1])


def _known_dividends(panels: Mapping[str, Any], t: pd.Timestamp) -> pd.DataFrame:
    tab = _get(panels, "dividends_table")
    if not isinstance(tab, pd.DataFrame) or not len(tab):
        return pd.DataFrame(columns=["symbol", "ex_date", "amount", "payment_date", "date"])
    df = tab.copy()
    df["ex_date"] = pd.to_datetime(df["ex_date"])
    known = pd.to_datetime(df["date"]) if "date" in df.columns else df["ex_date"]
    df["date"] = known.fillna(df["ex_date"])
    df = df[df["date"] <= t].copy()
    if "amount_revised" in df.columns and "revised_seen" in df.columns:
        seen = pd.to_datetime(df["revised_seen"])
        use = df["amount_revised"].notna() & seen.notna() & (seen <= t)
        df.loc[use, "amount"] = df.loc[use, "amount_revised"]
    if "payment_date" in df.columns:
        df["payment_date"] = pd.to_datetime(df["payment_date"])
    else:
        df["payment_date"] = pd.NaT
    return df.sort_values(["symbol", "ex_date"]).reset_index(drop=True)


def _split_factor_after(panels: Mapping[str, Any], symbol: str, after: pd.Timestamp, t: pd.Timestamp) -> float:
    """Produit des ratios de division (ou regroupement) de ``symbol`` connus entre ``after``
    (exclu) et ``t`` (inclus) : un dividende détaché avant est ramené à la base de titres de t."""
    ca = _get(panels, "corporate_actions")
    if not isinstance(ca, pd.DataFrame) or not len(ca):
        return 1.0
    kinds = ("split", "reverse_split", "capital_adjustment")
    d = pd.to_datetime(ca["date"])
    m = (ca["symbol"].astype(str) == symbol) & ca["kind"].isin(kinds) & (d > after) & (d <= t)
    r = pd.to_numeric(ca.loc[m, "ratio"], errors="coerce").dropna()
    return float(np.prod(r.to_numpy())) if len(r) else 1.0


# ---------------------------------------------------------------------------
# Dividendes attendus (12 mois)
# ---------------------------------------------------------------------------


def _usual_date(ex_dates: Sequence[pd.Timestamp]) -> tuple[int, int]:
    """Mois de détachement habituel (le plus fréquent ; égalité : le plus récent) et jour médian."""
    ds = sorted(pd.Timestamp(x) for x in ex_dates)
    months = pd.Series([d.month for d in ds])
    counts = months.value_counts()
    top = counts[counts == counts.max()].index
    month = max(top, key=lambda mo: max(i for i, d in enumerate(ds) if d.month == mo))
    day = int(np.median([d.day for d in ds if d.month == month]))
    return int(month), day


def _next_occurrence(t: pd.Timestamp, month: int, day: int, calendar: pd.DatetimeIndex) -> pd.Timestamp:
    for year in (t.year, t.year + 1, t.year + 2):
        last = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
        cand = pd.Timestamp(year=year, month=month, day=min(day, last.day))
        if cand > t:
            after = calendar[calendar >= cand]
            return pd.Timestamp(after[0]) if len(after) else cand
    raise AssertionError("date introuvable")  # pragma: no cover


def dividend_schedule(quantities: Mapping[str, int], asof: Any, panels: Mapping[str, Any], *,
                      taxes: TaxModel | None = None, horizon_months: int = 12,
                      calendar: Any = None) -> pd.DataFrame:
    """Calendrier des dividendes attendus sur ``horizon_months`` mois pour des quantités détenues.

    Pour chaque titre : dernier dividende **net publié** connu en ``asof`` (``dividends_table``,
    montant de la ligne (d) ou correction déjà publiée), part ordinaire seulement
    (``reference.ordinary_dividend_net``), ramené à la base de titres actuelle (divisions
    postérieures) ; date de détachement attendue = prochaine occurrence du **mois habituel**
    (historique) ; paiement = détachement + délai médian observé. Aucun dividende supposé si une
    **absence est annoncée** (``reference.announced_no_dividend``) ou si le dernier paiement a plus
    de 15 mois (garde-fou du §3.2).

    IRVM (:func:`irvm_rate`) : brut reconstitué ``net / (1 − τ_alors)``, net attendu
    ``brut × (1 − τ_actuel)`` (identique au net publié si le taux n'a pas changé).
    Montants en FCFA arrondis au franc : ``net = round(titres × net par titre)``,
    ``IRVM = round(titres × brut par titre) − net``.
    """
    tm = taxes if taxes is not None else TaxModel()
    t = pd.Timestamp(asof).normalize()
    end = t + pd.DateOffset(months=int(horizon_months))
    cal = _session_calendar(t, calendar, horizon_days=int(31 * (horizon_months + 3)))
    divs = _known_dividends(panels, t)
    rows = []
    for sym, q in quantities.items():
        q = int(q)
        if q <= 0:
            continue
        g = divs[divs["symbol"].astype(str) == sym]
        base = {"symbole": sym, "titres": q, "pays": reference.country_of(sym)}
        if not len(g):
            rows.append({**base, "statut": "aucun dividende dans l'historique", "montant_net": 0, "montant_brut": 0,
                         "irvm": 0})
            continue
        last = g.iloc[-1]
        ex_last = pd.Timestamp(last["ex_date"])
        pay_last = pd.Timestamp(last["payment_date"]) if pd.notna(last["payment_date"]) else ex_last
        net_raw = float(reference.ordinary_dividend_net(sym, ex_last, float(last["amount"])))
        factor = _split_factor_after(panels, sym, ex_last, t)
        net_ps_last = net_raw / factor
        month, day = _usual_date(list(g["ex_date"]))
        lags = [int(((cal > pd.Timestamp(e)) & (cal <= pd.Timestamp(p))).sum())
                for e, p in zip(g["ex_date"], g["payment_date"]) if pd.notna(p) and pd.Timestamp(p) >= pd.Timestamp(e)]
        lag = int(np.median(lags)) if lags else 2
        info = {**base, "dernier_detachement": ex_last, "dernier_paiement": pay_last,
                "dernier_dividende_net_publie": net_raw, "facteur_division": factor,
                "dividende_net_ajuste": net_ps_last, "mois_habituel": month, "n_historique": int(len(g))}
        absence = reference.announced_no_dividend(sym, t, last_payment_date=pay_last)
        if absence is not None:
            rows.append({**info, "statut": f"absence annoncée (exercice {absence.fiscal_year or 'durable'}, "
                                           f"connue le {absence.available_from})", "montant_net": 0,
                         "montant_brut": 0, "irvm": 0, "source": absence.source})
            continue
        if (t - pay_last).days > DIVIDEND_MAX_AGE_DAYS:
            rows.append({**info, "statut": "aucun dividende depuis plus de 15 mois : aucun supposé (§3.2)",
                         "montant_net": 0, "montant_brut": 0, "irvm": 0})
            continue
        ex_next = _next_occurrence(t, month, day, cal)
        after = cal[cal > ex_next]
        pay_next = pd.Timestamp(after[lag - 1]) if lag >= 1 and len(after) >= lag else ex_next
        if ex_next > end:
            rows.append({**info, "date_ex_prevue": ex_next, "date_paiement_prevue": pay_next,
                         "statut": "hors horizon", "montant_net": 0, "montant_brut": 0, "irvm": 0})
            continue
        tau_then = irvm_rate(sym, pay_last, tm)
        tau_now = irvm_rate(sym, pay_next, tm)
        gross_ps = net_ps_last / (1.0 - tau_then)
        net_ps = gross_ps * (1.0 - tau_now)
        net_amt = round_fcfa(q * net_ps)
        gross_amt = round_fcfa(q * gross_ps)
        late = (t - ex_last).days > 365 + 30
        rows.append({**info, "date_ex_prevue": ex_next, "date_paiement_prevue": pay_next,
                     "date_ago_estimee": ex_next - pd.Timedelta(days=AGO_TO_EX_DAYS),
                     "taux_irvm_dernier": tau_then, "taux_irvm_prevu": tau_now,
                     "dividende_brut_par_titre": gross_ps, "dividende_net_prevu_par_titre": net_ps,
                     "statut": "prévu (estimation : dernier dividende reconduit)" + (
                         " ; dernier détachement il y a plus d'un an : dividende de l'exercice en retard ou absent, "
                         "à vérifier" if late else ""),
                     "montant_brut": gross_amt, "irvm": gross_amt - net_amt, "montant_net": net_amt,
                     "irvm_note": IRVM_UNVERIFIED.get(reference.country_of(sym), "")})
    cols = ["symbole", "titres", "pays", "statut", "dernier_detachement", "dernier_paiement",
            "dernier_dividende_net_publie", "facteur_division", "dividende_net_ajuste", "mois_habituel", "n_historique",
            "date_ex_prevue", "date_paiement_prevue", "date_ago_estimee", "taux_irvm_dernier", "taux_irvm_prevu",
            "dividende_brut_par_titre", "dividende_net_prevu_par_titre", "montant_brut", "irvm", "montant_net",
            "irvm_note", "source"]
    out = pd.DataFrame(rows)
    for c in cols:
        if c not in out.columns:
            out[c] = None
    out = out[cols]
    if len(out):
        out = out.sort_values(["date_ex_prevue", "symbole"], na_position="last").reset_index(drop=True)
    for c in ("montant_brut", "irvm", "montant_net", "titres"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype("int64")
    return out


# ---------------------------------------------------------------------------
# Distribution à 12 mois (bootstrap stationnaire)
# ---------------------------------------------------------------------------


def estimation_window(asof: Any, s1_done: bool) -> dict[str, Any]:
    """Fenêtre d'estimation de la distribution : toute l'histoire (2017-2026) **seulement** si le
    registre indique que S1 a été exécuté, sinon S0 seulement (≥ 17/11/2022)."""
    t = pd.Timestamp(asof).normalize()
    if s1_done:
        return {"debut": S1_START, "fin": t, "s1_utilise": True,
                "texte": "toute l'histoire 2017-2026 (le registre indique que le test unique S1 a été exécuté)"}
    return {"debut": S0_START, "fin": t, "s1_utilise": False,
            "texte": "S0 seulement (17/11/2022 → décision) : le test S1 n'a pas été exécuté, l'échantillon vierge "
                     "2017-2022 n'est pas lu"}


def weekly_tr_returns(tr_index: pd.DataFrame, market_tr: pd.Series | None, symbols: Sequence[str],
                      start: Any, end: Any) -> pd.DataFrame:
    """Rendements hebdomadaires (W-FRI) des indices TR des ``symbols`` et du Composite TR (colonne
    ``__TR__``), calculés **uniquement** sur les cours de ``[start ; end]``.

    Les données sont coupées à la fenêtre **avant** tout calcul (aucune observation antérieure à
    ``start`` n'est lue, pas même comme base du premier rendement) ; la première semaine incomplète
    est retirée ; fenêtres exclues et semaines à trous de BOC : règles de
    ``backtest.metrics.weekly_returns``.
    """
    from brvm_alpha.backtest import metrics as bm

    a, b = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    cols = [s for s in symbols if s in tr_index.columns]
    px = tr_index.loc[(tr_index.index >= a) & (tr_index.index <= b), cols].astype(float)
    parts = [px]
    if market_tr is not None:
        m = pd.Series(market_tr, dtype=float)
        parts.append(m.loc[(m.index >= a) & (m.index <= b)].rename(_BENCH))
    frame = pd.concat(parts, axis=1).sort_index()
    frame = frame.where(np.isfinite(frame) & (frame > 0))
    daily = frame.pct_change(fill_method=None).iloc[1:]
    if not len(daily):
        return pd.DataFrame(columns=list(cols) + ([_BENCH] if market_tr is not None else []))
    # Tirages du bootstrap = statistiques de dispersion : semaines multi-séances (trous de BOC) retirées.
    weekly = bm.weekly_returns(daily, max_sessions=bm.MAX_WEEKLY_SESSIONS)
    if isinstance(weekly, pd.Series):
        weekly = weekly.to_frame()
    monday = weekly.index - pd.Timedelta(days=4)
    weekly = weekly[monday >= a]
    weekly.attrs["debut_donnees"] = frame.index.min()
    return weekly


def stationary_bootstrap_indices(n_obs: int, horizon: int, n_boot: int, mean_block: float, seed: int) -> np.ndarray:
    """Indices ``(n_boot, horizon)`` du bootstrap stationnaire (Politis & Romano 1994), raccord
    circulaire : nouveau bloc avec la probabilité ``1/mean_block`` à chaque pas. Déterministe pour
    une graine donnée (``numpy.random.default_rng(seed)``)."""
    if n_obs < 1 or horizon < 1 or n_boot < 1:
        raise ValueError("n_obs, horizon et n_boot doivent être >= 1")
    if mean_block < 1:
        raise ValueError("mean_block doit être >= 1")
    rng = np.random.default_rng(int(seed))
    starts = rng.integers(0, n_obs, size=(n_boot, horizon))
    new = rng.random((n_boot, horizon)) < (1.0 / float(mean_block))
    idx = np.empty((n_boot, horizon), dtype=np.int64)
    idx[:, 0] = starts[:, 0]
    for k in range(1, horizon):
        idx[:, k] = np.where(new[:, k], starts[:, k], (idx[:, k - 1] + 1) % n_obs)
    return idx


def return_distribution(weekly: pd.DataFrame, weights: Mapping[str, float], *, horizon_weeks: int = WEEKS_PER_YEAR,
                        n_boot: int = 5000, mean_block: float = BLOCK_WEEKS, seed: int = DEFAULT_SEED,
                        cost_drag: float = 0.0, with_draws: bool = False) -> dict[str, Any]:
    """Distribution historique à ``horizon_weeks`` semaines du portefeuille aux poids fixes et du
    Composite TR, tirés **ensemble** (mêmes semaines) par bootstrap stationnaire.

    Rendement hebdomadaire du portefeuille ``r_p = Σ w_i r_i`` (liquidités à 0 %). Une ligne **pas
    encore cotée** (semaines antérieures à sa première observation dans la fenêtre) n'est pas comptée
    à 0 % : les poids des lignes cotées sont renormalisés à l'exposition totale (correction du
    22/11/2026 : compter ces semaines à 0 % revenait à détenir des liquidités pendant la baisse de
    2017-2020). Après la cotation, une semaine sans cours (suspension) compte 0 % (cours inchangé).
    ``R = Π(1 + r) − 1`` sur l'horizon ; net : ``(1 + R)(1 − c) − 1`` avec ``c = cost_drag`` (coûts
    d'entrée et frais fixes de l'horizon, en fraction de la valeur). Sorties : médiane, P10, P90,
    P(perte), P(battre le TR) (net contre TR), quantiles du TR, β, lignes sans historique complet.
    ``with_draws=True`` ajoute les tirages (``tirages_net``, ``tirages_tr`` : tableaux numpy) pour
    l'histogramme du rapport, qui reprend ainsi exactement la distribution de l'ordre de bataille.
    **Distribution historique, pas une prévision.**
    """
    if _BENCH not in weekly.columns:
        raise ValueError("colonne du Composite TR absente")
    w = pd.Series({k: float(v) for k, v in weights.items() if float(v) > 0}, dtype=float)
    data = weekly.loc[weekly[_BENCH].notna()]
    missing_cols = [s for s in w.index if s not in data.columns]
    sub = data.reindex(columns=list(w.index)).astype(float)
    n_missing = int(sub.isna().sum().sum())
    wv = w.reindex(sub.columns).to_numpy(dtype=float)
    listed = np.zeros(sub.shape, dtype=bool)
    partial: list[dict[str, Any]] = []
    for j, c in enumerate(sub.columns):
        fv = sub[c].first_valid_index()
        if fv is None:
            continue
        listed[:, j] = sub.index >= fv
        if len(sub) and fv > sub.index[0]:
            partial.append({"symbole": c, "poids": float(wv[j]), "premiere_semaine": pd.Timestamp(fv),
                            "semaines_avant_cotation": int((sub.index < fv).sum())})
    for c in missing_cols:
        partial.append({"symbole": c, "poids": float(w[c]), "premiere_semaine": None,
                        "semaines_avant_cotation": int(len(sub))})
    n_before = int((~listed).sum())
    n_missing_after = int((sub.isna().to_numpy() & listed).sum())
    w_listed = listed * wv[None, :]
    tot = float(wv.sum())
    act = w_listed.sum(axis=1)
    scale = np.divide(tot, act, out=np.zeros_like(act), where=act > 0)
    rp = pd.Series((sub.fillna(0.0).to_numpy() * w_listed).sum(axis=1) * scale, index=sub.index)
    rb = data[_BENCH].astype(float)
    n = int(len(rp))
    if n < 26:
        return {"disponible": False, "motif": f"historique hebdomadaire trop court ({n} semaines < 26)", "n_semaines": n}
    idx = stationary_bootstrap_indices(n, int(horizon_weeks), int(n_boot), float(mean_block), int(seed))
    rp_a, rb_a = rp.to_numpy(), rb.to_numpy()
    gross = np.prod(1.0 + rp_a[idx], axis=1) - 1.0
    bench = np.prod(1.0 + rb_a[idx], axis=1) - 1.0
    net = (1.0 + gross) * (1.0 - float(cost_drag)) - 1.0
    var_b = float(np.var(rb_a, ddof=1))
    beta = float(np.cov(rp_a, rb_a, ddof=1)[0, 1] / var_b) if var_b > 0 else float("nan")
    q = lambda x, p: float(np.quantile(x, p))  # noqa: E731
    extra = {"tirages_net": net, "tirages_tr": bench} if with_draws else {}
    return {**extra, "disponible": True, "n_semaines": n, "debut": rp.index.min(), "fin": rp.index.max(),
            "horizon_semaines": int(horizon_weeks), "n_boot": int(n_boot), "bloc_moyen_semaines": float(mean_block),
            "graine": int(seed), "frais_deduits": float(cost_drag),
            "mediane": q(net, 0.5), "p10": q(net, 0.10), "p90": q(net, 0.90),
            "p_perte": float(np.mean(net < 0.0)), "p_battre_tr": float(np.mean(net > bench)),
            "mediane_brute": q(gross, 0.5), "tr_mediane": q(bench, 0.5), "tr_p10": q(bench, 0.10),
            "tr_p90": q(bench, 0.90), "beta_hebdo": beta,
            "rendement_annualise_fenetre": float(np.prod(1.0 + rp_a) ** (WEEKS_PER_YEAR / n) - 1.0),
            "tr_rendement_annualise_fenetre": float(np.prod(1.0 + rb_a) ** (WEEKS_PER_YEAR / n) - 1.0),
            "vol_annuelle": float(np.std(rp_a, ddof=1) * math.sqrt(WEEKS_PER_YEAR)),
            "tr_vol_annuelle": float(np.std(rb_a, ddof=1) * math.sqrt(WEEKS_PER_YEAR)),
            "valeurs_manquantes": n_missing, "lignes_sans_historique": missing_cols,
            "lignes_sans_historique_complet": partial,
            "poids_sans_historique_complet": float(sum(x["poids"] for x in partial)),
            "valeurs_avant_cotation_renormalisees": n_before, "valeurs_manquantes_apres_cotation": n_missing_after,
            "avertissement": "distribution historique, pas une prévision"}


# ---------------------------------------------------------------------------
# Stress (§9.3)
# ---------------------------------------------------------------------------


def _lambda(symbol: str, countries: Iterable[str]) -> float:
    try:
        lam = reference.economic_exposure(symbol)
    except Exception:
        lam = {reference.country_of(symbol): 1.0}
    cs = set(countries)
    return float(sum(v for k, v in lam.items() if k in cs))


def stress_scenarios(values: Mapping[str, float], nav: float, *, beta: float | None = None,
                     extra_costs: Mapping[str, int] | None = None, data_guard: bool | None = None) -> list[dict[str, Any]]:
    """Chocs du §9.3 appliqués à des positions (``values`` : symbole → valeur en FCFA).

    Marché (ST1, ST2, ST3) : ``perte = β_p × choc × valeur investie`` (β hebdomadaire du
    portefeuille contre le TR sur la fenêtre d'estimation, borné à [0,5 ; 1,5] ; 1 à défaut :
    **hypothèse** de linéarité). Pays (ST4, ST5, ST10) : choc de −26 % sur l'exposition
    économique λ des lignes (siège, ou filiales pour SNTS). ST8 : la plus grosse ligne suspendue,
    valorisée −30 %. ST6 et ST7 : surcoût de l'exécution du plan (``extra_costs``). ST9 : contrôle
    de données (garde |r| > 50 %), bloquant.
    """
    v = pd.Series({k: float(x) for k, x in values.items() if float(x) > 0}, dtype=float)
    inv = float(v.sum())
    b = 1.0 if beta is None or not np.isfinite(beta) else float(np.clip(beta, 0.5, 1.5))
    b_note = ("β = 1 supposé" if beta is None or not np.isfinite(beta) else
              f"β hebdomadaire {_num(float(beta))} borné à {_num(b)}")
    aes = reference.AES_COUNTRIES

    def row(code: str, label: str, loss: float, hyp: str, basis: str) -> dict[str, Any]:
        loss_i = round_fcfa(loss)
        return {"code": code, "scenario": label, "perte_fcfa": loss_i, "perte_pct": loss_i / nav if nav > 0 else 0.0,
                "hypothese": hyp, "base": basis}

    out = [
        row("ST1", "marché baissier long (TR −46,7 %, 01/03/2017 → 26/10/2020)", -b * 0.467 * inv,
            b_note, "[C-SPEC] §1.1 (fait mesuré sur le TR reconstruit)"),
        row("ST2", "pire année (2018 : TR reconstruit −25,1 %)", -b * 0.251 * inv, b_note, "[C-SPEC] ; [R08]"),
        row("ST3", "correction rapide (−15 % en 8 semaines)", -b * 0.15 * inv, b_note, "[R04] §12.4"),
    ]
    aes_loss = -0.26 * sum(val * _lambda(s, aes) for s, val in v.items())
    out.append(row("ST4", "choc pays sévère AES (−26 % sur BF, ML, NE en 9 séances)", aes_loss,
                   "exposition λ (siège ; filiales pour SNTS)", "[R05] §9 (Niger 2023)"))
    sn_loss = -0.26 * sum(val for s, val in v.items() if reference.country_of(s) == "SN")
    out.append(row("ST5", "stress souverain Sénégal (−26 % sur les titres sénégalais)", sn_loss,
                   "−9 % relatif observé en 2024 ; −26 % = stress", "[R05] §9, §12"))
    if extra_costs:
        if "ST6" in extra_costs:
            out.append(row("ST6", "liquidité (participation 5 %, demi-spread × 2)", -float(extra_costs["ST6"]),
                           "surcoût de l'exécution du plan", "hypothèse de conception"))
        if "ST7" in extra_costs:
            out.append(row("ST7", "coûts sévères (§7.2)", -float(extra_costs["ST7"]),
                           "surcoût de l'exécution du plan", "§7.2"))
    if len(v):
        top = str(v.idxmax())
        out.append(row("ST8", f"suspension de la plus grosse ligne ({top}, 60 séances, −30 %)", -0.30 * float(v.max()),
                       "−10 % pour le risque puis −30 %", "[R07] §4.7"))
    out.append({"code": "ST9", "scenario": "erreur de données (split non ajusté)", "perte_fcfa": 0, "perte_pct": 0.0,
                "hypothese": ("contrôle |rendement| > 50 % bloquant : "
                              + ("un titre bloqué à la date" if data_guard else "aucun blocage à la date")),
                "base": "[R08] §1"})
    peg = sum(val * (_lambda(s, aes) + (_lambda(s, ("GN", "SL", "GW")) if s == "SNTS" else 0.0)) for s, val in v.items())
    out.append(row("ST10", "rupture de parité ou sortie de l'UEMOA (règle sévère AES et filiales de SNTS)", -0.26 * peg,
                   "perte de change non chiffrée (aucune source)", "[R05] §7"))
    return out


def _external_stress(positions: Mapping[str, float], weights: Mapping[str, float], panels: Mapping[str, Any],
                     asof: pd.Timestamp, nav: float) -> tuple[list[dict[str, Any]] | None, str]:
    """Appelle ``brvm_alpha.portfolio.stress`` s'il existe (API découverte prudemment)."""
    try:
        mod = importlib.import_module("brvm_alpha.portfolio.stress")
    except ImportError:
        return None, "module brvm_alpha.portfolio.stress absent : chocs du §9.3 de ce module"
    except Exception as exc:  # pragma: no cover - module en cours d'écriture
        return None, f"module de stress inutilisable ({exc.__class__.__name__}) : chocs du §9.3 de ce module"
    candidates = ("stress_tests", "run_stress_tests", "apply_stress_tests", "portfolio_stress", "stress_report")
    avail = {"weights": pd.Series(weights, dtype=float), "positions": pd.Series(positions, dtype=float),
             "values": pd.Series(positions, dtype=float), "panels": panels, "asof": asof, "nav": nav,
             "capital": nav}
    for name in candidates:
        fn = getattr(mod, name, None)
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
            kwargs = {k: avail[k] for k in sig.parameters if k in avail}
            required = [p for p in sig.parameters.values() if p.default is inspect.Parameter.empty
                        and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.name not in kwargs]
            if required:
                continue
            res = fn(**kwargs)
        except Exception as exc:
            return None, f"brvm_alpha.portfolio.stress.{name} en échec ({exc.__class__.__name__}) : chocs de ce module"
        if isinstance(res, pd.DataFrame):
            rows = res.to_dict("records")  # la note sur β figure dans la colonne « hypothese »
        elif isinstance(res, Mapping):
            rows = [dict(v, code=k) if isinstance(v, Mapping) else {"code": k, "valeur": v} for k, v in res.items()]
        elif isinstance(res, (list, tuple)):
            rows = [dict(r) if isinstance(r, Mapping) else {"valeur": r} for r in res]
        else:
            continue
        return rows, f"brvm_alpha.portfolio.stress.{name}"
    return None, "brvm_alpha.portfolio.stress sans fonction reconnue : chocs du §9.3 de ce module"


# ---------------------------------------------------------------------------
# Formats français
# ---------------------------------------------------------------------------


def _num(x: Any, decimals: int = 2, signed: bool = False) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n.d."
    if not math.isfinite(v):
        return "n.d."
    s = f"{v:+,.{decimals}f}" if signed else f"{v:,.{decimals}f}"
    return s.replace(",", "\u202f").replace(".", ",").replace("-", "−")


def _fcfa(x: Any, signed: bool = False) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n.d."
    if not math.isfinite(v):
        return "n.d."
    s = f"{v:+,.0f}" if signed else f"{v:,.0f}"
    return s.replace(",", "\u202f").replace("-", "−") + " FCFA"


def _int(x: Any) -> str:
    try:
        return f"{int(x):,}".replace(",", "\u202f").replace("-", "−")
    except (TypeError, ValueError):
        return "n.d."


_TECH_FR = {"notes désactivées (notes=None)": "notes désactivées (aucun journal de notes transmis)"}


def fr_texte(texte: Any) -> str:
    """Typographie française d'un message technique du modèle (affichage seulement) : décimales à
    virgule (« 98.00% » → « 98,00 % », « 1.31 » → « 1,31 »), signe moins typographique, espace avant
    « % ». Les numéros de section (« §4.2 »), de version (« v1.1 ») et les dates ne sont pas touchés."""
    s = _TECH_FR.get(str(texte), str(texte))
    s = re.sub(r"(?<![§\w.,/])(\d+)\.(\d+)(?![\w.])", r"\1,\2", s)
    s = re.sub(r"(?<![\w\-−])-(?=\d)", "−", s)
    return re.sub(r"(\d)%", "\\1 %", s)


def _pct(x: Any, decimals: int = 2, signed: bool = False) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n.d."
    if not math.isfinite(v):
        return "n.d."
    s = f"{100 * v:+.{decimals}f}" if signed else f"{100 * v:.{decimals}f}"
    return s.replace(".", ",").replace("-", "−") + " %"


def _d(x: Any) -> str:
    try:
        if x is None or pd.isna(x):
            return "n.d."
        return f"{pd.Timestamp(x):%d/%m/%Y}"
    except (TypeError, ValueError):
        return str(x)


def _jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return v if math.isfinite(v) else None
    if isinstance(obj, pd.Timestamp):
        return None if pd.isna(obj) else obj.isoformat()
    if obj is pd.NaT:
        return None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.DataFrame):
        return [_jsonable(r) for r in obj.to_dict("records")]
    if isinstance(obj, pd.Series):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_jsonable(v) for v in obj.tolist()]
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return str(obj)


# ---------------------------------------------------------------------------
# L'ordre de bataille
# ---------------------------------------------------------------------------


@dataclass
class OrdreDeBataille:
    """Ordre de bataille complet (sortie de :func:`recommend`).

    ``lignes`` : une ligne par titre détenu ou cible (quantités, poids, prix limites, coûts, net) ;
    ``tranches`` : échéancier par séance ; ``dividendes`` : revenus attendus ; ``distribution`` :
    bootstrap à 12 mois ; ``stress`` ; ``declencheurs`` ; ``explications`` ; ``comparaison``
    (variante affichée en comparaison, ou ``None``). ``faits``, ``estimations``, ``hypotheses`` :
    ce qui est publié, ce qui est estimé, ce qui est supposé.
    """

    asof: pd.Timestamp
    asof_demande: pd.Timestamp
    capital: float
    valeur_portefeuille: float
    liquidites_initiales: float
    variante: str
    choix: dict[str, Any]
    lignes: pd.DataFrame
    tranches: pd.DataFrame
    execution: dict[str, Any]
    couts: dict[str, Any]
    dividendes: pd.DataFrame
    revenus: dict[str, Any]
    distribution: dict[str, Any]
    stress: list[dict[str, Any]]
    declencheurs: dict[str, Any]
    explications: list[dict[str, Any]]
    comparaison: dict[str, Any] | None
    faits: list[str]
    estimations: list[str]
    hypotheses: list[str]
    avertissements: list[str]
    messages_modele: list[str]
    meta: dict[str, Any] = field(default_factory=dict)
    bandeau: str = BANNER

    # ------------------------------------------------------------- accès
    @property
    def statut(self) -> str:
        return str(self.choix.get("statut"))

    @property
    def phrase_etude(self) -> str | None:
        return PHRASE_ETUDE if self.choix.get("phrase_etude", True) else None

    def ordres(self) -> pd.DataFrame:
        """Lignes avec un ordre (achat ou vente)."""
        return self.lignes[self.lignes["sens"] != "aucun"].reset_index(drop=True)

    # ------------------------------------------------------------- exports
    def to_dict(self) -> dict[str, Any]:
        """Dictionnaire sérialisable en JSON (dates ISO, nombres Python)."""
        d = {
            "bandeau": self.bandeau, "statut": self.statut, "phrase_etude": self.phrase_etude,
            "asof": self.asof, "asof_demande": self.asof_demande, "capital": self.capital,
            "valeur_portefeuille": self.valeur_portefeuille, "liquidites_initiales": self.liquidites_initiales,
            "variante": self.variante, "choix": self.choix, "lignes": self.lignes, "tranches": self.tranches,
            "execution": self.execution, "couts": self.couts, "dividendes": self.dividendes, "revenus": self.revenus,
            "distribution": self.distribution, "stress": self.stress, "declencheurs": self.declencheurs,
            "explications": self.explications, "comparaison": self.comparaison, "faits": self.faits,
            "estimations": self.estimations, "hypotheses": self.hypotheses, "avertissements": self.avertissements,
            "messages_modele": self.messages_modele, "meta": self.meta,
        }
        return _jsonable(d)

    def to_markdown(self) -> str:
        """Rapport Markdown en français (bandeau, statut, ordres, exécution, revenus, risques)."""
        return _render(self._blocks(), "md")

    def to_html_fragment(self) -> str:
        """Fragment HTML autonome (``<section>``, sans ``<html>`` ni style externe), texte échappé."""
        return _render(self._blocks(), "html")

    # ------------------------------------------------------------- contenu
    def _blocks(self) -> list[tuple[str, Any]]:
        B: list[tuple[str, Any]] = []
        c = self.choix
        B.append(("h1", f"Ordre de bataille BRVM Alpha au {_d(self.asof)}"))
        B.append(("banner", f"{self.bandeau} Statut : {self.statut}."))
        if self.phrase_etude:
            B.append(("strong", self.phrase_etude[0].upper() + self.phrase_etude[1:] + "."))
        for w in self.avertissements:
            B.append(("warn", w))
        B.append(("p", f"Décision à la clôture du BOC du {_d(self.asof)} ; exécution à partir du "
                       f"{_d(self.execution.get('premiere_seance'))}. Capital {_fcfa(self.capital)} ; valeur du "
                       f"portefeuille avant ordres {_fcfa(self.valeur_portefeuille)}, dont liquidités "
                       f"{_fcfa(self.liquidites_initiales)}."))
        nt_top = (self.declencheurs or {}).get("notes") or {}
        if nt_top.get("ligne"):
            B.append(("p", nt_top["ligne"]))
        # 1. variante
        B.append(("h2", "1. Variante et statut de validation"))
        B.append(("ul", [f"Variante retenue : **{self.variante}** — {c.get('description', '')}",
                         f"Motif : {c.get('motif')}",
                         f"Statut de A sur S1 : {c.get('statut_A')} ; {c.get('registre')}",
                         f"Variante en comparaison : {c.get('comparaison') or 'aucune'}"]))
        # 2. ordres
        B.append(("h2", "2. Ordres (au titre et au franc près)"))
        L = self.lignes
        rows = []
        for r in L.itertuples(index=False):
            if r.sens == "aucun" and int(r.cibles) == 0 and int(r.detenus) == 0:
                continue
            rows.append([r.symbole, r.sens.upper() if r.sens != "aucun" else "—", _int(r.quantite), _int(r.detenus),
                         _int(r.cibles), _pct(r.poids_cible), _pct(r.poids_realise), _num(r.cours_reference, 0),
                         f"{_num(r.borne_basse, 0)} – {_num(r.borne_haute, 0)}", _num(r.prix_limite, 0),
                         _fcfa(r.montant_brut), _fcfa(r.couts_total), _fcfa(r.montant_net), _int(r.seances)])
        B.append(("table", (["Titre", "Sens", "Quantité", "Détenus", "Cible", "Poids cible", "Poids réalisé",
                             "Cours réf.", "Bornes", "Limite", "Brut", "Coûts", "Net", "Séances"], rows)))
        notes = [f"{r.symbole} : {r.note}" for r in L.itertuples(index=False) if getattr(r, "note", "")]
        if notes:
            B.append(("ul", notes))
        B.extend(self._notes_blocks())
        crow = []
        for r in L[L["sens"] != "aucun"].itertuples(index=False):
            crow.append([r.symbole, r.sens, _fcfa(r.courtage), _fcfa(r.tva), _fcfa(r.brvm), _fcfa(r.dcbr),
                         _fcfa(r.demi_spread), _fcfa(r.impact), _fcfa(r.couts_total), _pct(r.demi_spread_pct, 3),
                         _pct(r.participation_max, 1), _fcfa(r.pire_cas)])
        if crow:
            B.append(("h3", "Coûts détaillés par ordre (estimation au cours de référence)"))
            B.append(("table", (["Titre", "Sens", "Courtage", "TVA", "BRVM", "DC/BR", "Demi-spread", "Impact",
                                 "Total", "Demi-spread %", "Particip. max", "Pire cas (provision)"], crow)))
        k = self.couts
        B.append(("ul", [
            f"Achats : brut {_fcfa(k['achats_brut'])}, coûts {_fcfa(k['achats_couts'])} (explicites "
            f"{_fcfa(k['achats_explicites'])}, implicites estimés {_fcfa(k['achats_implicites'])}), net "
            f"{_fcfa(k['achats_net'])} ; provision pire cas {_fcfa(k['achats_pire_cas'])}",
            f"Ventes : brut {_fcfa(k['ventes_brut'])}, coûts {_fcfa(k['ventes_couts'])} (explicites "
            f"{_fcfa(k.get('ventes_explicites'))}, implicites estimés {_fcfa(k.get('ventes_implicites'))}), net "
            f"{_fcfa(k['ventes_net'])}",
            f"Coûts totaux du plan : {_fcfa(k['total'])} ({_pct(k['total_pct'])} de la valeur du portefeuille)",
            f"Frais fixes annuels estimés : garde {_fcfa(k['garde_annuelle'])} ({_pct(k['taux_garde'])} de l'encours) "
            f"+ tenue de compte {_fcfa(k['tenue_compte_annuelle'])} ({_int(k['n_lignes'])} lignes × "
            f"{_fcfa(k['frais_par_ligne'])})",
            f"Investi après ordres (au cours de référence) : {_fcfa(k['investi_apres'])} "
            f"({_pct(k['investi_pct'])}) pour une cible atteignable de {_pct(k['cible_pct'])} (cible de la "
            f"spécification : {_pct(k.get('cible_specification', 0.98))}"
            + (f", reliquat non investissable sous les plafonds {_pct(k.get('reliquat_plafonds'))}, D4"
               if (k.get("reliquat_plafonds") or 0) > 0.0005 else "") + ") ; reliquat de l'arrondi vers le bas "
            f"{_fcfa(k['reliquat_arrondi'])} (reste en liquidités, §6) ; liquidités restantes estimées "
            f"{_fcfa(k['liquidites_apres'])} (pire cas {_fcfa(self.execution.get('liquidites_finales_pire_cas'))})",
            f"Scénario de coûts : {k['scenario']} (courtage {_pct(k['taux_courtage'])} × (1 + TVA "
            f"{_pct(k['taux_tva'], 0)}), BRVM {_pct(k['taux_brvm'])}, DC/BR {_pct(k['taux_dcbr'])}, impact "
            f"κ = {_num(k['kappa'], 3)})"]))
        mm = [m for m in self.messages_modele if m]
        if mm:
            B.append(("h3", "Messages du modèle (signalés)"))
            B.append(("ul", mm))
        if self.execution.get("perime"):
            B.append(("warn", "ORDRES PÉRIMÉS : panel en retard (voir l'avertissement en tête) ; ne pas transmettre."))
        if self.execution.get("reductions"):
            B.append(("p", "Quantités réduites pour que le pire cas (tout exécuté à la limite) reste finançable : "
                           + ", ".join(f"{s} −{_int(n)}" for s, n in self.execution["reductions"].items()) + "."))
        # 3. exécution
        B.append(("h2", "3. Exécution : échéancier par séance"))
        ex = self.execution
        B.append(("ul", [
            f"{_int(ex.get('n_seances'))} séance(s) du {_d(ex.get('premiere_seance'))} au {_d(ex.get('derniere_seance'))} ; "
            f"participation ≤ {_pct(ex.get('participation_max_regle'), 0)} de la MDV63 en valeur par séance",
            "Ventes d'abord ; règlement J+2 (depuis le 04/12/2025) : le produit d'une vente ne finance un achat qu'à "
            "partir de sa date de règlement ; liquidités initiales utilisées d'abord",
            f"Prix limites : achat = min(borne haute ; dernier cours × {_num(1 + ex.get('tolerance', 0.01), 2)}) au pas "
            f"inférieur ; vente = max(borne basse ; dernier cours × {_num(1 - ex.get('tolerance', 0.01), 2)}) au pas "
            "supérieur. Aucun achat si le titre cote à la borne haute, aucune vente à la borne basse : ordre reporté "
            f"(au plus {MAX_CARRY_SESSIONS} séances, puis réévaluation)",
            "Jour ex et jour de division : la BRVM annule les ordres en attente ; les ressaisir le jour même",
            ex.get("calendrier", "")]))
        if ex.get("au_dela_report"):
            B.append(("warn", "Ordres de plus de 10 séances (au-delà du report maximal) : "
                              + ", ".join(ex["au_dela_report"]) + " ; à réévaluer au rebalancement suivant."))
        trows = [[_int(r.seance), _d(r.date), r.symbole, r.sens, _int(r.titres), _num(r.prix_limite, 0),
                  _fcfa(r.montant_ref), _fcfa(r.pire_cas), _d(r.date_reglement), r.financement or "—"]
                 for r in self.tranches.itertuples(index=False)]
        B.append(("table", (["Séance", "Date", "Titre", "Sens", "Titres", "Limite", "Montant réf.", "Pire cas",
                             "Règlement", "Financement"], trows)))
        # 4. revenus
        B.append(("h2", f"4. Revenus attendus : dividendes sur {self.revenus.get('horizon_mois')} mois (estimation)"))
        drows = []
        for r in self.dividendes.itertuples(index=False):
            drows.append([r.symbole, _int(r.titres), _d(r.date_ex_prevue), _d(r.date_paiement_prevue),
                          _num(r.dividende_net_ajuste, 2) if r.dividende_net_ajuste is not None else "n.d.",
                          _pct(r.taux_irvm_prevu, 1) if r.taux_irvm_prevu is not None else "—",
                          _fcfa(r.montant_brut), _fcfa(r.irvm), _fcfa(r.montant_net),
                          str(r.statut) + (f" ; IRVM {r.irvm_note}" if isinstance(r.irvm_note, str) and r.irvm_note
                                           and r.montant_net > 0 else "")])
        B.append(("table", (["Titre", "Titres", "Date ex prévue", "Paiement prévu", "Dernier net/titre", "IRVM",
                             "Brut", "IRVM (FCFA)", "Net", "Statut"], drows)))
        rv = self.revenus
        B.append(("p", f"Revenu net attendu {_fcfa(rv['net'])} (brut {_fcfa(rv['brut'])}, IRVM {_fcfa(rv['irvm'])}) ; "
                       f"rendement net du portefeuille {_pct(rv['rendement_net'])} de la valeur "
                       f"({_pct(rv['rendement_net_investi'])} de l'investi). Dernier dividende reconduit : hypothèse, "
                       "pas une promesse ; un dividende n'est acquis que si les titres sont détenus la veille du "
                       "détachement."))
        # 5-6. distribution et stress (stress d'abord si le marché est « cher », §4.5)
        dist_blocks = self._dist_blocks()
        stress_blocks = self._stress_blocks()
        if self.meta.get("valorisation", {}).get("regime") == "chère":
            B.append(("p", f"Valorisation du marché « cher » (prime du BOC {_num(self.meta['valorisation'].get('prime'))} "
                           "< 1 %) : les stress sont affichés en premier (§4.5) ; l'exposition ne change pas."))
            B.extend(stress_blocks)
            B.extend(dist_blocks)
        else:
            B.extend(dist_blocks)
            B.extend(stress_blocks)
        # 7. déclencheurs
        B.extend(self._trigger_blocks())
        # 8. explications
        B.append(("h2", "8. Explications (titres retenus et 5 premiers écartés)"))
        erows = [[e["symbole"], e["statut"], _int(e.get("rang")) if e.get("rang") else "—", _pct(e.get("poids")),
                  e.get("texte_court", "")] for e in self.explications]
        B.append(("table", (["Titre", "Statut", "Rang", "Poids", "Explication"], erows)))
        # 9. comparaison
        if self.comparaison:
            B.extend(self._comparison_blocks())
        # 10. faits / estimations / hypothèses
        B.append(("h2", "10. Faits, estimations, hypothèses"))
        B.append(("h3", "Faits (publiés ou réglementaires)"))
        B.append(("ul", self.faits))
        B.append(("h3", "Estimations (calculées, incertaines)"))
        B.append(("ul", self.estimations))
        B.append(("h3", "Hypothèses (supposées, non vérifiées)"))
        B.append(("ul", self.hypotheses))
        B.append(("banner", self.bandeau))
        return B

    def _notes_blocks(self) -> list[tuple[str, Any]]:
        """Achats bloqués par une note (règle, note, fin du blocage, levée) et effet sur les poids."""
        nt = (self.declencheurs or {}).get("notes") or {}
        blocs = nt.get("blocages") or []
        eff = nt.get("effet") or {}
        B: list[tuple[str, Any]] = []
        if not blocs and not eff.get("lignes"):
            return B
        B.append(("h3", "Achats bloqués par les notes de l'analyste et effet sur les poids"))
        if blocs:
            rows = []
            for b in blocs:
                note = (f"note {str(b.get('note_id', ''))[:12]} du {_d(b.get('note_date'))} : « {b.get('note_titre', '')} » "
                        f"(source {b.get('note_source') or 'n.d.'}"
                        + (f", {b['note_url']}" if b.get("note_url") else "") + ")")
                fin = b.get("duree") or "durée ouverte"
                if b.get("seances_restantes") is not None:
                    fin += f" (encore {_int(b['seances_restantes'])} séance(s))"
                rows.append([b.get("symbole"), f"{b.get('code')} — {b.get('libelle')}", note,
                             f"depuis le {_d(b.get('depuis'))}, {fin}", b.get("effet_poids") or "—",
                             b.get("lever") or ""])
            B.append(("table", (["Titre", "Règle", "Note", "Blocage", "Effet sur l'ordre", "Pour lever le blocage"],
                                rows)))
        if eff.get("texte"):
            B.append(("p", eff["texte"]))
        if eff.get("lignes"):
            B.append(("table", (["Titre", "Poids cible sans les notes", "Poids cible avec les notes", "Écart", "Motif"],
                                [[x["symbole"], _pct(x["poids_sans_notes"]), _pct(x["poids_avec_notes"]),
                                  _pct(x["ecart"], 2, True), x.get("motif") or "redistribution (construction)"]
                                 for x in eff["lignes"]])))
        return B

    def _dist_blocks(self) -> list[tuple[str, Any]]:
        D = self.distribution
        B: list[tuple[str, Any]] = [("h2", "5. Distribution historique à 12 mois (pas une prévision)")]
        if not D.get("disponible"):
            B.append(("p", f"Distribution non calculée : {D.get('motif')}."))
            return B
        nav = self.valeur_portefeuille
        B.append(("p", f"Bootstrap stationnaire ({_int(D['n_boot'])} tirages, blocs moyens de "
                       f"{_num(D['bloc_moyen_semaines'], 0)} semaines, graine {D['graine']}) des rendements "
                       f"hebdomadaires TR des lignes aux poids réalisés et du Composite TR, tirés ensemble ; fenêtre "
                       f"{D.get('fenetre', '')} ({_int(D['n_semaines'])} semaines, du {_d(D['debut'])} au "
                       f"{_d(D['fin'])}). Nets des coûts du plan et des frais fixes de l'horizon "
                       f"({_pct(D['frais_deduits'])}). C'est une distribution historique, pas une prévision."))
        if D.get("biais_fenetre"):
            B.append(("warn", D["biais_fenetre"]))
        if D.get("biais_retrospectif"):
            B.append(("warn", D["biais_retrospectif"]))
        rs1 = D.get("resultat_s1") or {}
        if rs1.get("texte"):
            B.append(("warn", rs1["texte"]))
        B.append(("table", (["Mesure", "Portefeuille (net)", "Composite TR"], [
            ["Médiane", f"{_pct(D['mediane'], 1, True)} ({_fcfa(nav * (1 + D['mediane']))})", _pct(D['tr_mediane'], 1, True)],
            ["P10", f"{_pct(D['p10'], 1, True)} ({_fcfa(nav * (1 + D['p10']))})", _pct(D['tr_p10'], 1, True)],
            ["P90", f"{_pct(D['p90'], 1, True)} ({_fcfa(nav * (1 + D['p90']))})", _pct(D['tr_p90'], 1, True)],
            ["P(perte)", _pct(D['p_perte'], 1), "—"],
            ["P(battre le TR)", _pct(D['p_battre_tr'], 1) + (" (fréquence historique aux poids actuels)"
                                                             if rs1.get("texte") else ""),
             rs1.get("court", "—")],
            ["Rendement des dividendes (net)", _pct(self.revenus.get('rendement_net'), 2), "inclus dans le TR"],
            ["Rendement annualisé du TR sur la fenêtre (fait)", "— (poids actuels : biais rétrospectif)",
             _pct(D['tr_rendement_annualise_fenetre'], 1, True)],
            ["Volatilité annualisée (hebdo)", _pct(D['vol_annuelle'], 1), _pct(D['tr_vol_annuelle'], 1)],
            [f"β hebdomadaire contre le TR ({_d(D['debut'])} → {_d(D['fin'])})", _num(D['beta_hebdo']), "1"]])))
        return B

    def _stress_blocks(self) -> list[tuple[str, Any]]:
        B: list[tuple[str, Any]] = [("h2", "6. Scénarios de stress (§9.3)")]
        B.append(("p", f"Source : {self.meta.get('stress_source', '')}."))
        rows = []
        for s in self.stress:
            label = str(s.get("scenario", s.get("libelle", "")))
            if s.get("variante") and str(s.get("variante")) not in ("nan", "None"):
                label += f" — {s['variante']}"
            rows.append([str(s.get("code", "")), label,
                         _fcfa(s.get("perte_fcfa")), _pct(s.get("perte_pct"), 1), str(s.get("hypothese", "")),
                         str(s.get("base", ""))])
        B.append(("table", (["Code", "Scénario", "Perte", "En % de la valeur", "Hypothèse", "Base"], rows)))
        return B

    def _trigger_blocks(self) -> list[tuple[str, Any]]:
        T = self.declencheurs
        B: list[tuple[str, Any]] = [("h2", "7. Déclencheurs de revue")]
        rb = T.get("rebalancement", {})
        items = [f"Prochaine revue mensuelle (dernière séance du mois) : {_d(rb.get('prochaine_revue'))}"]
        if rb.get("rebalancement_annuel"):
            items.append(f"Rebalancement annuel de l'indice discipliné (première décision de janvier) : "
                         f"{_d(rb.get('rebalancement_annuel'))} ; entre deux, seules les sorties forcées s'appliquent")
        items.append(f"Début du suivi réel S2 (§8.1) : {_d(S2_START)}")
        fr = T.get("filtres_r") or []
        items.append("Filtres R actifs sur les lignes : " + ("; ".join(f"{x['symbole']} ({x['filtres']})" for x in fr)
                                                             if fr else "aucun"))
        dd = T.get("drawdown", {})
        items.append(dd.get("texte", ""))
        for x in dd.get("revues_lignes", []):
            items.append(f"Revue obligatoire {x['symbole']} : {_pct(x['relatif_63'], 1, True)} contre le TR sur 63 séances")
        nt = T.get("notes", {})
        items.append(nt.get("texte", ""))
        if nt.get("ligne"):
            items.append(nt["ligne"])
        if nt.get("message_scores"):
            items.append("Scores des notes : " + nt["message_scores"])
        for f in nt.get("filtres") or []:
            fin = f.get("duree") or "durée ouverte"
            items.append(f"Filtre {f.get('code')} sur {f.get('symbole')} ({f.get('libelle')}) depuis le "
                         f"{_d(f.get('depuis'))}, {fin} — note {str(f.get('note_id', ''))[:12]} du {_d(f.get('note_date'))} "
                         f"« {f.get('note_titre', '')} »"
                         + (" ; achats bloqués" if f.get("bloque_achats") else "")
                         + ("" if f.get("dans_le_plan") else " ; titre hors du plan"))
        items.append(T.get("pays", {}).get("texte", ""))
        B.append(("ul", [i for i in items if i]))
        ev = T.get("evenements")
        if isinstance(ev, pd.DataFrame) and len(ev):
            rows = [[_d(r.date), r.type, r.cible, r.description, r.nature] for r in ev.itertuples(index=False)]
            B.append(("h3", "Événements à venir (12 mois)"))
            B.append(("table", (["Date", "Type", "Cible", "Description", "Nature"], rows)))
        ix = T.get("indices") or []
        if ix:
            B.append(("h3", "Évaluation des indices (notes.index_eval, information)"))
            B.append(("table", (["Indice", "Position", "Confiance", "Score", "Lecture"],
                                [[x["libelle"], x["position"] + (f" (sans les notes : {x['position_sans_notes']})"
                                                                 if x.get("position_changee_par_les_notes") else ""),
                                  _num(x["confiance"]), _num(x["score"], 2, True), x["lecture"]] for x in ix])))
            changed = [x["libelle"] for x in ix if x.get("position_changee_par_les_notes")]
            if changed:
                B.append(("p", "Position fragile : " + ", ".join(changed) + " — la position ne change que par le poids "
                               "donné à la composante « notes » dans le score (voir « Effet des notes » dans la "
                               "lecture), pas par un signal fort des notes. À lire avec la position « sans les "
                               "notes »."))
        elif T.get("indices_message"):
            B.append(("p", T["indices_message"]))
        return B

    def _comparison_blocks(self) -> list[tuple[str, Any]]:
        C = self.comparaison or {}
        B: list[tuple[str, Any]] = [("h2", f"9. Comparaison : variante {C.get('variante')} (information seulement)")]
        B.append(("p", C.get("texte", "")))
        rows = [[r["symbole"], _int(r["cibles"]), _pct(r["poids_cible"]), _pct(r["poids_realise"]),
                 _num(r["prix_limite"], 0), _fcfa(r["montant_net"])] for r in C.get("lignes", [])]
        B.append(("table", (["Titre", "Titres", "Poids cible", "Poids réalisé", "Limite", "Net"], rows)))
        D, K, R = C.get("distribution", {}), C.get("couts", {}), C.get("revenus", {})
        main = self.distribution
        B.append(("table", (["Mesure", self.variante, str(C.get("variante"))], [
            ["Lignes", _int(self.couts.get("n_lignes")), _int(K.get("n_lignes"))],
            ["Coûts du plan", _fcfa(self.couts.get("total")), _fcfa(K.get("total"))],
            ["Revenu net de dividendes (12 mois)", _fcfa(self.revenus.get("net")), _fcfa(R.get("net"))],
            ["Médiane à 12 mois (net)", _pct(main.get("mediane"), 1, True), _pct(D.get("mediane"), 1, True)],
            ["P10 / P90", f"{_pct(main.get('p10'), 1, True)} / {_pct(main.get('p90'), 1, True)}",
             f"{_pct(D.get('p10'), 1, True)} / {_pct(D.get('p90'), 1, True)}"],
            ["P(perte)", _pct(main.get("p_perte"), 1), _pct(D.get("p_perte"), 1)],
            ["P(battre le TR)", _pct(main.get("p_battre_tr"), 1), _pct(D.get("p_battre_tr"), 1)]])))
        return B


def _md_cell(x: Any) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def _inline_html(text: str) -> str:
    """Échappe le texte puis rend ``**gras**``."""
    parts = str(text).split("**")
    return "".join(f"<strong>{html.escape(p)}</strong>" if i % 2 else html.escape(p) for i, p in enumerate(parts))


def _render(blocks: list[tuple[str, Any]], fmt: str) -> str:
    out: list[str] = []
    if fmt == "md":
        for kind, val in blocks:
            if kind == "h1":
                out.append(f"# {val}\n")
            elif kind == "h2":
                out.append(f"## {val}\n")
            elif kind == "h3":
                out.append(f"### {val}\n")
            elif kind == "banner":
                out.append(f"> **{val}**\n")
            elif kind == "strong":
                out.append(f"**{val}**\n")
            elif kind == "warn":
                out.append(f"> ⚠ {val}\n")
            elif kind == "p":
                out.append(f"{val}\n")
            elif kind == "ul":
                out.append("\n".join(f"- {x}" for x in val if x) + "\n")
            elif kind == "table":
                head, rows = val
                if not rows:
                    out.append("_(aucune ligne)_\n")
                    continue
                out.append("| " + " | ".join(_md_cell(h) for h in head) + " |")
                out.append("|" + "|".join("---" for _ in head) + "|")
                out.extend("| " + " | ".join(_md_cell(c) for c in r) + " |" for r in rows)
                out.append("")
        return "\n".join(out).rstrip() + "\n"
    out.append('<section class="brvm-ordre-de-bataille" lang="fr">')
    for kind, val in blocks:
        if kind in ("h1", "h2", "h3"):
            out.append(f"<{kind}>{_inline_html(val)}</{kind}>")
        elif kind == "banner":
            out.append(f'<p class="bandeau"><strong>{html.escape(str(val))}</strong></p>')
        elif kind == "strong":
            out.append(f'<p class="etude"><strong>{html.escape(str(val))}</strong></p>')
        elif kind == "warn":
            out.append(f'<p class="avertissement" role="note">⚠ {_inline_html(val)}</p>')
        elif kind == "p":
            out.append(f"<p>{_inline_html(val)}</p>")
        elif kind == "ul":
            out.append("<ul>" + "".join(f"<li>{_inline_html(x)}</li>" for x in val if x) + "</ul>")
        elif kind == "table":
            head, rows = val
            if not rows:
                out.append("<p><em>(aucune ligne)</em></p>")
                continue
            out.append("<table><thead><tr>" + "".join(f"<th scope=\"col\">{html.escape(str(h))}</th>" for h in head)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline_html(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table>")
    out.append("</section>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Construction du plan pour une variante
# ---------------------------------------------------------------------------


def _half_spreads(panels: Mapping[str, Any], t: pd.Timestamp, close: pd.Series, costs: CostModel) -> pd.Series:
    """Demi-spread par titre, comme le moteur : ``mult × max(mesure 120 séances ou défaut ; pas/(2·cours))``."""
    syms = close.index
    base = pd.Series(float(costs.half_spread_default), index=syms)
    bid, ask = _get(panels, "bid"), _get(panels, "ask")
    measured = pd.Series(False, index=syms)
    if isinstance(bid, pd.DataFrame) and isinstance(ask, pd.DataFrame):
        from brvm_alpha.backtest import engine

        b = bid.loc[bid.index <= t]
        a = ask.loc[ask.index <= t]
        if len(b) and len(a):
            hs = engine.quoted_half_spread(b, a, window=120, min_obs=20, lag=0)
            if len(hs) and hs.index[-1] == t:
                row = hs.iloc[-1].reindex(syms).astype(float)
                ok = np.isfinite(row) & (row >= 0)
                base = base.where(~ok, row)
                measured = ok
    px = close.astype(float)
    floor = pd.Series(np.where(np.isfinite(px) & (px > 0), macro.tick_size(px.fillna(1.0).to_numpy()) / (2.0 * px), 0.0),
                      index=syms)
    out = float(costs.half_spread_mult) * np.maximum(base, floor.fillna(0.0))
    out.attrs["mesure"] = measured
    return out


def _next_ex_reference(panels: Mapping[str, Any], t: pd.Timestamp, next_session: pd.Timestamp,
                       sym: str, close: float) -> tuple[float | None, str]:
    """Référence ex-dividende si le détachement de la prochaine séance est connu en t (ligne (d))."""
    divs = _known_dividends(panels, t)
    g = divs[(divs["symbol"].astype(str) == sym) & (divs["ex_date"] == next_session)]
    if not len(g):
        return None, ""
    amt = float(g["amount"].iloc[-1])
    return ceil_to_tick(max(close - amt, 1.0)), f"référence ex-dividende ({_num(amt)} FCFA net détaché le {_d(next_session)})"


class _Plan:
    """Calculs d'un plan pour une variante (modèle, décision, ordres, exécution, revenus, distribution)."""

    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


def _build_plan(*, variant: str, t: pd.Timestamp, panels: Mapping[str, Any], nav: float, cash: float,
                held_q: Mapping[str, int], close: pd.Series, costs: CostModel, cost_name: str, taxes: TaxModel,
                notes_arg: Any, calendar_past: Any, horizon_months: int, n_boot: int, seed: int,
                window: dict[str, Any], tolerance: float, max_participation: float, mean_block: float,
                cfg: Mapping[str, Any], prebuilt: tuple[Any, Any] | None = None,
                exec_after: pd.Timestamp | None = None, blocked: Mapping[str, Any] | None = None,
                notes_known_at: Any = None) -> _Plan:
    from brvm_alpha.strategy import BrvmAlpha

    held_w = pd.Series({s: q * float(close[s]) / nav for s, q in held_q.items() if q > 0}, dtype=float)
    if prebuilt is not None:  # même décision, autres hypothèses de coûts ou de participation (ST6, ST7)
        model, dec = prebuilt
    else:
        model = BrvmAlpha(variant=variant, capital=nav, notes=notes_arg, notes_known_at=notes_known_at)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dec = model.decide(t, panels, held_w if len(held_w) else None)
    w = dec.weights.astype(float).fillna(0.0)
    uni = dec.universe
    syms = sorted(set(w[w > 0].index) | {s for s, q in held_q.items() if q > 0})
    # Première séance d'exécution : après la décision ET pas avant aujourd'hui (panel en retard : jamais
    # d'ordre daté dans le passé).
    fut = future_sessions(max(t, exec_after) if exec_after is not None else t, 400, calendar_past)
    next_s = fut[0]
    hs_all = _half_spreads(panels, t, close.reindex(uni.index), costs)
    status_t = _get(panels, "status")
    status_t = status_t.loc[t] if isinstance(status_t, pd.DataFrame) and t in status_t.index else None
    band = float(cfg.get("portfolio", {}).get("no_trade_band", 0.02))
    lines: list[dict[str, Any]] = []
    msgs: list[str] = []
    for s in syms:
        c = float(close.get(s, np.nan))
        if not np.isfinite(c) or c <= 0:
            msgs.append(f"{s} : cours absent au {_d(t)}, ligne ignorée")
            continue
        ref_ex, ref_note = _next_ex_reference(panels, t, next_s, s, c)
        lp = limit_prices(c, reference_price=ref_ex, tolerance=tolerance)
        cur = int(held_q.get(s, 0))
        wt = float(w.get(s, 0.0))
        tgt = int(math.floor(wt * nav / c + 1e-9)) if wt > 0 else 0
        w_cur = cur * c / nav
        note = ref_note
        if cur > 0 and tgt > 0 and abs(wt - w_cur) < band:
            tgt = cur
            note = (note + " ; " if note else "") + f"écart < {_pct(band, 0)} : bande de non-transaction (§6)"
        suspended = status_t is not None and str(status_t.get(s, "")) == "suspended"
        if blocked and s in blocked:
            b = blocked[s]
            note = (note + " ; " if note else "") + (
                f"bloquée, hors BOC (dernier cours {_num(b['dernier_cours'], 0)} FCFA le {_d(b['date_dernier_cours'])}, "
                "valorisé −10 %, §7.1.7) : aucun ordre possible")
            tgt = cur
        elif suspended and tgt != cur:
            note = (note + " ; " if note else "") + "titre suspendu (R1) : aucun ordre possible"
            tgt = cur
        mdv = float(uni["mdv63"].get(s, np.nan)) if "mdv63" in uni.columns else float("nan")
        lines.append({"symbole": s, "pays": reference.country_of(s), "secteur": reference.sector_of(s),
                      "detenus": cur, "cibles": tgt, "poids_actuel": w_cur, "poids_cible": wt,
                      "cours_reference": c, "reference_prochaine_seance": lp["reference"], "borne_basse": lp["low"],
                      "borne_haute": lp["high"], "limite_achat": lp["buy"], "limite_vente": lp["sell"],
                      "mdv63": mdv, "demi_spread_pct": float(hs_all.get(s, costs.half_spread_default)),
                      "note": note})
    L = pd.DataFrame(lines)

    def tranches_for(r: Mapping[str, Any], q: int) -> list[int]:
        return participation_schedule(q, r["cours_reference"], r["mdv63"], max_participation)

    def worst_buy(r: Mapping[str, Any], q: int) -> int:
        return _worst_case(tranches_for(r, q), r["limite_achat"], costs, "achat") if q > 0 else 0

    # Faisabilité : provision pire cas des achats ≤ liquidités + encaissement minimal des ventes.
    sell_min = 0
    for r in lines:
        dq = r["cibles"] - r["detenus"]
        if dq < 0:
            sell_min += _worst_case(tranches_for(r, -dq), r["limite_vente"], costs, "vente")
    budget = int(math.floor(cash)) + sell_min
    buys = {i: r["cibles"] - r["detenus"] for i, r in enumerate(lines) if r["cibles"] > r["detenus"]}
    reductions: dict[str, int] = {}
    total = sum(worst_buy(lines[i], q) for i, q in buys.items())
    if total > budget and buys:
        f = budget / total
        new = {i: int(math.floor(q * f)) for i, q in buys.items()}
        cur_total = sum(worst_buy(lines[i], q) for i, q in new.items())
        changed = True
        while changed:
            changed = False
            order = sorted(new, key=lambda i: -(lines[i]["poids_cible"] * nav
                                                - (lines[i]["detenus"] + new[i]) * lines[i]["cours_reference"])
                           / lines[i]["cours_reference"])
            for i in order:
                if new[i] >= buys[i]:
                    continue
                delta = worst_buy(lines[i], new[i] + 1) - worst_buy(lines[i], new[i])
                if cur_total + delta <= budget:
                    new[i] += 1
                    cur_total += delta
                    changed = True
        for i, q in buys.items():
            if new[i] < q:
                reductions[lines[i]["symbole"]] = q - new[i]
                lines[i]["cibles"] = lines[i]["detenus"] + new[i]
    # Ordres et coûts.
    def apply_costs(r: dict[str, Any], tr: list[int]) -> None:
        side, q = r["sens"], int(r["quantite"])
        r["tranches"] = list(tr)
        r["seances"] = len(tr)
        if side == "aucun":
            oc = order_costs(0, r["cours_reference"], costs, side="achat")
            r["pire_cas"] = 0
        else:
            oc = order_costs(q, r["cours_reference"], costs, side=side, half_spread=r["demi_spread_pct"],
                             mdv63=r["mdv63"], tranches=tr, limit=r["prix_limite"])
            r["pire_cas"] = _worst_case(tr, r["prix_limite"], costs, side)
        r["implicites_plafonnes"] = bool(oc.get("implicites_plafonnes", False))
        r["_oc"] = oc
        for k in ("brut", "courtage", "tva", "brvm", "dcbr", "redevance", "explicites", "demi_spread", "impact",
                  "implicites", "total", "net", "participation_max"):
            r[{"brut": "montant_brut", "total": "couts_total", "net": "montant_net",
               "explicites": "frais_explicites", "implicites": "couts_implicites"}.get(k, k)] = oc[k]

    orders = []
    for r in lines:
        dq = r["cibles"] - r["detenus"]
        side = "achat" if dq > 0 else "vente" if dq < 0 else "aucun"
        q = abs(dq)
        r["sens"], r["quantite"] = side, q
        r["prix_limite"] = r["limite_achat"] if side == "achat" else r["limite_vente"] if side == "vente" else np.nan
        tr = tranches_for(r, q)
        apply_costs(r, tr)
        oc = r.pop("_oc")
        if side != "aucun":
            if oc["implicites_plafonnes"]:
                r["note"] = ((r["note"] + " ; ") if r["note"] else "") + (
                    "coûts implicites plafonnés par le prix limite (écart limite − cours : l'ordre peut ne pas être "
                    "servi)")
            orders.append({"symbol": r["symbole"], "side": side, "qty": q, "tranches": tr, "limit": r["prix_limite"],
                           "ref_price": r["cours_reference"], "weight": r["poids_cible"]})
        r["poids_realise"] = r["cibles"] * r["cours_reference"] / nav
        r["valeur_apres"] = r["cibles"] * r["cours_reference"]
        mdv = r["mdv63"]
        r["participation_depassee"] = bool(np.isfinite(mdv) and mdv > 0 and q > 0
                                           and r["cours_reference"] > max_participation * mdv)
    orders.sort(key=lambda o: (o["side"] != "vente", -float(o["weight"]), o["symbol"]))
    tranches, einfo = plan_execution(orders, cash, fut, costs)
    # Lignes recalculées sur les tranches EFFECTIVEMENT planifiées (le financement peut réduire et décaler
    # une tranche) : séances, frais et pire cas au franc près, cohérents avec l'échéancier.
    for r in lines:
        if r["sens"] == "aucun" or not len(tranches):
            continue
        sel = tranches[(tranches["symbole"] == r["symbole"]) & (tranches["sens"] == r["sens"])]
        planned = [int(x) for x in sel.sort_values("seance")["titres"]]
        rest = int(r["quantite"]) - sum(planned)
        if rest > 0:
            planned.append(rest)
            r["note"] = ((r["note"] + " ; ") if r["note"] else "") + (
                f"{_int(rest)} titre(s) non planifié(s) dans l'horizon (financement) : coûts estimés sur une tranche "
                "supplémentaire")
        if planned != list(r["tranches"]):
            apply_costs(r, planned)
            r.pop("_oc", None)
    L = pd.DataFrame(lines)
    if len(L):
        L = L.sort_values(["poids_cible", "symbole"], ascending=[False, True]).reset_index(drop=True)
    return _Plan(model=model, decision=dec, held_w=held_w, lines=L, tranches=tranches, exec_info=einfo,
                 reductions=reductions, sessions=fut, messages=msgs, orders=orders)


def _cost_summary(L: pd.DataFrame, nav: float, cash: float, costs: CostModel, name: str) -> dict[str, Any]:
    def s(side: str, col: str) -> int:
        if not len(L):
            return 0
        return int(L.loc[L["sens"] == side, col].sum())

    invested = float(L["valeur_apres"].sum()) if len(L) else 0.0
    target_val = float((L["poids_cible"] * nav).sum()) if len(L) else 0.0
    n_lines = int((L["cibles"] > 0).sum()) if len(L) else 0
    tot = s("achat", "couts_total") + s("vente", "couts_total")
    liquid = float(cash) - s("achat", "montant_net") + s("vente", "montant_net")
    return {"scenario": name, "achats_brut": s("achat", "montant_brut"), "achats_couts": s("achat", "couts_total"),
            "achats_explicites": s("achat", "frais_explicites"), "achats_implicites": s("achat", "couts_implicites"),
            "achats_net": s("achat", "montant_net"), "achats_pire_cas": s("achat", "pire_cas"),
            "ventes_brut": s("vente", "montant_brut"), "ventes_couts": s("vente", "couts_total"),
            "ventes_explicites": s("vente", "frais_explicites"), "ventes_implicites": s("vente", "couts_implicites"),
            "ventes_net": s("vente", "montant_net"), "ventes_pire_cas": s("vente", "pire_cas"),
            "explicites": s("achat", "frais_explicites") + s("vente", "frais_explicites"),
            "implicites": s("achat", "couts_implicites") + s("vente", "couts_implicites"),
            "flux_net": s("achat", "montant_net") - s("vente", "montant_net"),
            "courtage": s("achat", "courtage") + s("vente", "courtage"), "tva": s("achat", "tva") + s("vente", "tva"),
            "brvm": s("achat", "brvm") + s("vente", "brvm"), "dcbr": s("achat", "dcbr") + s("vente", "dcbr"),
            "demi_spread": s("achat", "demi_spread") + s("vente", "demi_spread"),
            "impact": s("achat", "impact") + s("vente", "impact"),
            "total": tot, "total_pct": tot / nav if nav > 0 else 0.0,
            "garde_annuelle": round_fcfa(costs.annual_custody * invested), "taux_garde": float(costs.annual_custody),
            "tenue_compte_annuelle": round_fcfa(costs.account_fee_per_line_fcfa * n_lines),
            "frais_par_ligne": float(costs.account_fee_per_line_fcfa), "n_lignes": n_lines,
            "investi_apres": round_fcfa(invested), "investi_pct": invested / nav if nav > 0 else 0.0,
            "cible_investie": round_fcfa(target_val), "cible_pct": target_val / nav if nav > 0 else 0.0,
            "reliquat_arrondi": round_fcfa(target_val - invested),
            "liquidites_apres": round_fcfa(liquid), "taux_courtage": float(costs.sgi_commission),
            "taux_tva": float(costs.vat_on_commission), "taux_brvm": float(costs.brvm_fee),
            "taux_dcbr": float(costs.dcbr_fee), "kappa": float(costs.impact_coef),
            "taux_explicites": float(costs.rate())}


def _capital_warnings(L: pd.DataFrame, k: Mapping[str, Any], nav: float, costs: CostModel, spec_target: float,
                      variant: str) -> list[str]:
    """Avertissements de capital (correction du 22/11/2026) : réplication impossible (part investie sous la
    cible de plus de 10 points, moins de lignes que la cible) ou frais **fixes** (tenue de compte par ligne)
    supérieurs à 1 % par an de la valeur du portefeuille. Les droits de garde, proportionnels à l'encours, ne
    dépendent pas du capital et ne sont pas comptés ici."""
    if not len(L) or nav <= 0:
        return []
    tgt = L[L["poids_cible"] > 0]
    n_target = int(len(tgt))
    n_lines = int(k.get("n_lignes") or 0)
    inv = float(k.get("investi_pct") or 0.0)
    fixed = float(k.get("tenue_compte_annuelle") or 0)
    fixed_pct = fixed / nav
    repl = []
    if inv < spec_target - 0.10:
        repl.append(f"{_pct(inv, 1)} investi contre une cible de {_pct(spec_target, 0)}")
    if n_lines < n_target:
        repl.append(f"{_int(n_lines)} ligne(s) sur {_int(n_target)} visée(s)")
    fee_txt = (f"frais fixes de tenue de compte {_fcfa(fixed)} par an, soit {_pct(fixed_pct, 1)} de la valeur "
               f"({_pct(fixed / max(float(k.get('investi_apres') or 0), 1.0), 0)} de l'investi)")
    k_lines = max((float(r.cours_reference) / float(r.poids_cible) for r in tgt.itertuples(index=False)
                   if r.poids_cible > 0), default=0.0)
    k_fees = n_target * float(costs.account_fee_per_line_fcfa) / 0.01 if costs.account_fee_per_line_fcfa else 0.0
    out = []
    if repl:
        out.append(f"Capital insuffisant pour répliquer {variant} : " + " ; ".join(repl)
                   + (f" ; {fee_txt}" if fixed_pct > 0.01 else "")
                   + f". Capital minimal indicatif : {_fcfa(max(k_lines, k_fees))} (au moins un titre de chaque "
                     f"ligne : {_fcfa(k_lines)} ; tenue de compte ≤ 1 %/an : {_fcfa(k_fees)}). Les frais fixes "
                     "peuvent absorber tout rendement espéré ; préférer une SGI sans frais par ligne (§6) ou un "
                     "capital plus élevé.")
    elif fixed_pct > 0.01:
        out.append(f"Frais fixes élevés : {fee_txt}. Capital pour les ramener à 1 %/an : {_fcfa(k_fees)} ; "
                   "préférer une SGI sans frais par ligne (§6).")
    return out


def _revenue_summary(div: pd.DataFrame, nav: float, invested: float, horizon: int) -> dict[str, Any]:
    net = int(div["montant_net"].sum()) if len(div) else 0
    return {"horizon_mois": int(horizon), "net": net, "brut": int(div["montant_brut"].sum()) if len(div) else 0,
            "irvm": int(div["irvm"].sum()) if len(div) else 0, "rendement_net": net / nav if nav > 0 else 0.0,
            "rendement_net_investi": net / invested if invested > 0 else 0.0,
            "n_paiements": int((div["montant_net"] > 0).sum()) if len(div) else 0}


def _distribution_for(plan: _Plan, panels: Mapping[str, Any], nav: float, costs_sum: Mapping[str, Any],
                      window: Mapping[str, Any], horizon_months: int, n_boot: int, seed: int,
                      mean_block: float) -> tuple[dict[str, Any], pd.DataFrame | None]:
    L = plan.lines
    weights = {r.symbole: float(r.poids_realise) for r in L.itertuples(index=False) if r.cibles > 0}
    tr = _get(panels, "tr_index")
    mtr = _get(panels, "market_tr")
    if not isinstance(tr, pd.DataFrame) or mtr is None:
        return {"disponible": False, "motif": "indices TR (tr_index, market_tr) absents des panels"}, None
    weekly = weekly_tr_returns(tr, mtr, list(weights), window["debut"], window["fin"])
    h_weeks = int(round(WEEKS_PER_YEAR * horizon_months / 12))
    fixed = (costs_sum["garde_annuelle"] + costs_sum["tenue_compte_annuelle"]) * horizon_months / 12.0
    drag = (costs_sum["total"] + fixed) / nav if nav > 0 else 0.0
    if not weights:
        return {"disponible": False, "motif": "aucune ligne détenue après ordres"}, weekly
    dist = return_distribution(weekly, weights, horizon_weeks=h_weeks, n_boot=n_boot, mean_block=mean_block,
                               seed=seed, cost_drag=drag)
    dist["fenetre"] = window["texte"]
    dist["s1_utilise"] = bool(window["s1_utilise"])
    if dist.get("disponible") and window["s1_utilise"]:
        # Fenêtre 2017-2026 : poids ACTUELS et sélection d'AUJOURD'HUI appliqués au passé (biais rétrospectif).
        part = sorted(dist.get("lignes_sans_historique_complet") or [], key=lambda x: -x["poids"])
        lst = ", ".join(f"{x['symbole']} ({_pct(x['poids'], 1)}, "
                        + (f"depuis le {_d(x['premiere_semaine'])}" if x.get("premiere_semaine") is not None
                           else "aucun cours dans la fenêtre") + ")" for x in part)
        dist["biais_retrospectif"] = (
            "Biais rétrospectif : poids actuels et sélection d'aujourd'hui (plus grosses capitalisations au "
            f"{_d(window['fin'])}) appliqués à toute l'histoire 2017-2026 ; les titres alors en difficulté ou "
            "radiés n'y figurent pas, ce qui flatte la distribution. "
            + (f"Lignes sans historique complet : {lst}, soit {_pct(dist.get('poids_sans_historique_complet'), 1)} "
               f"du portefeuille ; {_int(dist.get('valeurs_avant_cotation_renormalisees'))} valeur(s) "
               "antérieure(s) à la cotation : poids renormalisés sur les lignes cotées (et non comptées à 0 %). "
               if part else "Toutes les lignes ont un historique complet sur la fenêtre. ")
            + f"{_int(dist.get('valeurs_manquantes_apres_cotation'))} valeur(s) manquante(s) après cotation "
              "(suspensions) comptée(s) à 0 %.")
    if dist.get("disponible") and not window["s1_utilise"]:
        dist["biais_fenetre"] = (
            f"Fenêtre S0 seulement : le Composite TR y a progressé de "
            f"{_pct(dist['tr_rendement_annualise_fenetre'], 1, True)} par an (phase la plus haussière de 2017-2026) ; "
            "la baisse de 2017-2020 (TR −46,7 %) et les années négatives n'y figurent pas. Cette distribution est donc "
            "très probablement optimiste (P(perte) sous-estimée) : lire les stress ST1 à ST3.")
    dist["debut_donnees"] = weekly.attrs.get("debut_donnees")
    return dist, weekly


# ---------------------------------------------------------------------------
# Déclencheurs de revue
# ---------------------------------------------------------------------------


def _month_end_session(t: pd.Timestamp, calendar_past: Any, months_ahead: int = 0) -> pd.Timestamp:
    cal = _session_calendar(t, calendar_past, horizon_days=480)
    target = (t + pd.offsets.MonthEnd(0)) if months_ahead == 0 else (t + pd.offsets.MonthEnd(months_ahead))
    month_days = cal[(cal.year == target.year) & (cal.month == target.month)]
    month_days = month_days[month_days > t]
    if len(month_days):
        return pd.Timestamp(month_days[-1])
    return _month_end_session(t, calendar_past, months_ahead + 1)


def _publication_events(store: Any, t: pd.Timestamp, symbols: Sequence[str], end: pd.Timestamp,
                        known_at: Any = None) -> list[dict[str, Any]]:
    """Publications attendues d'après l'historique des notes (dernière publication + 1 an).

    ``known_at`` : instant de connaissance du journal (défaut : fin du jour ``t``) ; information de
    calendrier seulement, jamais un signal.
    """
    rows: list[dict[str, Any]] = []
    if store is None:
        return rows
    k = pd.Timestamp(t if known_at is None else known_at).normalize() + pd.Timedelta(hours=23, minutes=59)
    try:
        if isinstance(store, pd.DataFrame):  # table de notes (DataFrame.asof n'est pas la vue des notes)
            frame = store
        elif hasattr(store, "asof"):
            frame = store.asof(k)
        else:
            frame = pd.DataFrame(store)
    except Exception:
        return rows
    if not isinstance(frame, pd.DataFrame) or not len(frame) or "event_type" not in frame.columns:
        return rows
    f = frame[frame["event_type"].isin(list(_PUB_TYPES))].copy()
    if not len(f):
        return rows
    f["_pub"] = pd.to_datetime(f["published_at"], utc=True, errors="coerce").dt.tz_localize(None)
    for s in symbols:
        def has(x: Any, s: str = s) -> bool:
            try:
                return s in list(x)
            except TypeError:
                return False

        cols = [c for c in ("targets", "all_targets") if c in f.columns]
        mask = np.zeros(len(f), dtype=bool)
        for c in cols:
            mask |= f[c].apply(has).to_numpy()
        g = f[mask]
        for et, lab in _PUB_TYPES.items():
            h = g[(g["event_type"] == et) & (g["_pub"] <= k)].dropna(subset=["_pub"])
            if not len(h):
                continue
            last = pd.Timestamp(h["_pub"].max()).normalize()
            years = 1
            while last + pd.DateOffset(years=years) <= t:
                years += 1
            nxt = last + pd.DateOffset(years=years)
            if nxt <= end:
                rows.append({"date": nxt, "type": "publication attendue", "cible": s,
                             "description": f"{lab} (dernière connue : {_d(last)}, + {years} an(s))",
                             "nature": "estimation (historique des notes)"})
    return rows


def _triggers(plan: _Plan, t: pd.Timestamp, panels: Mapping[str, Any], div: pd.DataFrame, calendar_past: Any,
              horizon_months: int, notes_store: Any, index_rows: list[dict[str, Any]] | None,
              index_msg: str, known_at: Any = None, notes_state: Mapping[str, Any] | None = None,
              notes_effect: Mapping[str, Any] | None = None) -> dict[str, Any]:
    dec = plan.decision
    L = plan.lines
    syms = [r.symbole for r in L.itertuples(index=False) if r.cibles > 0 or r.detenus > 0]
    end = t + pd.DateOffset(months=int(horizon_months))
    risk = dec.risk
    fr = []
    for s in syms:
        if s in risk.index and str(risk.loc[s, "active"]):
            fr.append({"symbole": s, "filtres": str(risk.loc[s, "active"]),
                       "achats_bloques": bool(risk.loc[s, "block_buys"])})
    # Drawdown relatif : lignes détenues (§9.1) et règle de portefeuille (D5).
    reviews = []
    tr = _wide_upto(panels, "tr_index", t)
    mtr = _get(panels, "market_tr")
    held = [s for s, w in plan.held_w.items() if w > 0]
    if held and isinstance(tr, pd.DataFrame) and mtr is not None and len(tr) > 63:
        m = pd.Series(mtr, dtype=float)
        m = m[m.index <= t]
        if len(m) > 63:
            m_ret = float(m.iloc[-1] / m.iloc[-64])
            for s in held:
                if s in tr.columns:
                    col = tr[s].dropna()
                    if len(col) > 63:
                        rel = float(col.iloc[-1] / col.iloc[-64]) / m_ret - 1.0
                        if rel <= REVIEW_REL_UNDERPERF_63:
                            reviews.append({"symbole": s, "relatif_63": rel})
    rdd = dec.diagnostics.get("relative_drawdown") or {}
    if rdd.get("dd") is not None and np.isfinite(rdd.get("dd")):
        dd_txt = f"Drawdown relatif du suivi contre le TR : {_pct(rdd['dd'], 1, True)} (seuils −10 % alerte, −15 % actif ÷ 2, −20 % arrêt)"
    else:
        dd_txt = ("Drawdown relatif contre le TR : aucun historique de suivi réel (mesuré depuis le premier jour investi, "
                  "D5) ; seuils à surveiller : −10 % alerte, −15 % exposition active ÷ 2, −20 % arrêt et indice discipliné")
    # Notes de l'analyste.
    nd = dec.diagnostics.get("notes") or {}
    veto = dict(nd.get("veto") or {})
    tilt = pd.Series(nd.get("tilt") if nd.get("tilt") is not None else [], dtype=float)
    tilt = tilt[tilt != 0] if len(tilt) else tilt
    flags = dict(nd.get("flags") or {})
    if not nd.get("available"):
        n_txt = f"Notes de l'analyste : {fr_texte(nd.get('message') or 'non disponibles')}"
    else:
        parts = [f"{len(veto)} veto(s)" + (f" ({', '.join(sorted(veto))})" if veto else ""),
                 f"{len(tilt)} inclinaison(s)" + (" (" + ", ".join(f"{k} {_num(v, 2, True)} σ" for k, v in tilt.items())
                                                  + ")" if len(tilt) else ""),
                 f"{len(flags)} titre(s) avec filtre R issu des notes"]
        n_txt = "Notes de l'analyste : " + ", ".join(parts)
    # Pays : règles actives et événements datés à venir.
    cs = dec.diagnostics.get("country_rules") or {}
    p_txt = ("Règles pays actives : " + "; ".join(f"{c} ({st.get('label', st.get('rule'))})" for c, st in cs.items())
             if cs else "Règles pays actives : aucune")
    events: list[dict[str, Any]] = []
    ce = getattr(reference, "COUNTRY_EVENTS", None)
    if isinstance(ce, pd.DataFrame) and len(ce):
        fut = ce[(pd.to_datetime(ce["date"]) > t) & (pd.to_datetime(ce["date"]) <= end)]
        for r in fut.itertuples(index=False):
            events.append({"date": pd.Timestamp(r.date), "type": f"événement pays ({r.rule})", "cible": r.country,
                           "description": str(r.label), "nature": f"daté ({r.confidence})"})
        if not len(fut):
            p_txt += " ; aucun événement pays daté à venir dans reference.COUNTRY_EVENTS (horizon 12 mois)"
    else:
        p_txt += " ; reference.COUNTRY_EVENTS absent"
    for r in div.itertuples(index=False):
        if r.date_ex_prevue is not None and pd.notna(r.date_ex_prevue) and r.montant_net > 0:
            events.append({"date": pd.Timestamp(r.date_ex_prevue), "type": "détachement prévu", "cible": r.symbole,
                           "description": f"{_num(r.dividende_net_prevu_par_titre)} FCFA net/titre, soit "
                                          f"{_fcfa(r.montant_net)} payés vers le {_d(r.date_paiement_prevue)} ; une vente "
                                          "programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6)",
                           "nature": "estimation (mois habituel)"})
            if r.date_ago_estimee is not None and pd.notna(r.date_ago_estimee) and pd.Timestamp(r.date_ago_estimee) > t:
                events.append({"date": pd.Timestamp(r.date_ago_estimee), "type": "AGO estimée", "cible": r.symbole,
                               "description": "date ex − 42 jours (médiane §5.4)", "nature": "estimation"})
    pubs = _publication_events(notes_store, t, syms, end, known_at)
    events.extend(pubs)
    for year in (t.year, t.year + 1):
        for mo, day, lab in PUBLICATION_DEADLINES:
            d = pd.Timestamp(year=year, month=mo, day=day)
            if t < d <= end:
                events.append({"date": d, "type": "échéance de publication", "cible": "toutes les lignes",
                               "description": lab + " ; alerte orange le lendemain, rouge à +61 jours",
                               "nature": "fait (règle R7)"})
    for year in (t.year, t.year + 1):
        for mo in (1, 4, 7, 10):
            first = pd.Timestamp(year=year, month=mo, day=1)
            cal = _session_calendar(t, calendar_past, horizon_days=480)
            nxt = cal[cal >= first]
            if len(nxt) and t < nxt[0] <= end:
                events.append({"date": pd.Timestamp(nxt[0]), "type": "révision du BRVM 30", "cible": "IDX:BRVM-30",
                               "description": "révision trimestrielle de la composition (information seulement, §5.5)",
                               "nature": "fait (calendrier ; date de séance estimée)"})
    if t < S2_START <= end:
        events.append({"date": S2_START, "type": "suivi réel", "cible": "plate-forme",
                       "description": "début du suivi réel S2 (paper trading, §8.1)", "nature": "fait (protocole)"})
    ev = pd.DataFrame(events, columns=["date", "type", "cible", "description", "nature"])
    if len(ev):
        ev = ev.sort_values(["date", "type", "cible"]).reset_index(drop=True)
    next_review = _month_end_session(t, calendar_past)
    annual = None
    if dec.diagnostics.get("mode") == "indice_discipline" or plan.model.spec.kind in ("reference", "core_satellite"):
        # Première décision (mensuelle, dernière séance du mois) de janvier de l'année suivante (D8).
        annual = _month_end_session(pd.Timestamp(year=t.year + 1, month=1, day=1), calendar_past)
    notes_out: dict[str, Any] = {
        "texte": n_txt, "veto": veto, "inclinaisons": tilt.to_dict() if len(tilt) else {},
        "drapeaux": {k: [str(x.get("code", x)) if isinstance(x, Mapping) else str(x) for x in v]
                     for k, v in flags.items()}}
    notes_out.update(_notes_trigger(notes_state, notes_effect, L, dec))
    return {"filtres_r": fr, "drawdown": {"texte": dd_txt, "revues_lignes": reviews, "etat_modele": rdd},
            "notes": notes_out,
            "pays": {"texte": p_txt, "regles_actives": {c: st.get("rule") for c, st in cs.items()}},
            "evenements": ev,
            "rebalancement": {"prochaine_revue": next_review, "rebalancement_annuel": annual},
            "indices": index_rows or [], "indices_message": index_msg}


def _notes_state(plan: _Plan, t: pd.Timestamp, store: Any, calendar_dates: Any) -> dict[str, Any] | None:
    """État des notes de la décision (``notes.signals.notes_in_force``) : mêmes surcouches que le modèle.

    Mode direct si le modèle l'a appliqué (``diagnostics["notes"]["mode"]``), historique sinon.
    ``None`` si les notes sont désactivées ou indisponibles.
    """
    nd = plan.decision.diagnostics.get("notes") or {}
    if store is None or not nd.get("available"):
        return None
    try:
        from brvm_alpha.notes import signals as ns

        known = nd.get("known_at") if nd.get("mode") == "direct" else None
        ov = {"table": nd.get("table"), "tilt_notes": list(nd.get("tilt_notes") or []), "tilt": nd.get("tilt")}
        cal = calendar_dates if isinstance(calendar_dates, pd.DataFrame) else list(pd.DatetimeIndex(calendar_dates))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return ns.notes_in_force(store, t, known_at=known, calendar=cal, overlays=ov)
    except Exception as exc:  # l'ordre de bataille ne dépend pas de cette synthèse
        return {"erreur": f"{exc.__class__.__name__} : {exc}"}


def _notes_effect(plan: _Plan, variant: str, t: pd.Timestamp, panels: Mapping[str, Any], nav: float,
                  state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Effet des notes sur les poids cibles : même décision recalculée **sans aucune note**.

    Calculé seulement si une note agit sur la décision (filtre, veto ou inclinaison). Les règles
    de construction ne changent pas : la comparaison montre ce qu'elles font du poids d'un titre
    bloqué (redistribué aux autres lignes ou laissé en liquidités).
    """
    if not state or state.get("erreur"):
        return None
    if not (state.get("n_filters") or state.get("n_veto") or state.get("n_tilt")):
        return None
    from brvm_alpha.strategy import BrvmAlpha

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            base = BrvmAlpha(variant=variant, capital=nav, notes=None).decide(
                t, panels, plan.held_w if len(plan.held_w) else None)
    except Exception as exc:  # pragma: no cover - comparaison facultative
        return {"texte": f"Effet des notes sur les poids non calculé ({exc.__class__.__name__} : {exc}).", "lignes": []}
    w1 = plan.decision.weights.astype(float).fillna(0.0)
    w0 = base.weights.astype(float).fillna(0.0)
    syms = sorted(set(w1[w1 > 0].index) | set(w0[w0 > 0].index))
    # Indice discipliné (REF) : sélection par capitalisation, l'inclinaison n'y entre pas (seuls le veto et
    # les filtres R qui bloquent les achats agissent) ; ni l'inclinaison ni un filtre de simple surveillance
    # (R10 : malus de qualité, sans effet sur un poids de capitalisation) n'y sont donc cités comme motif
    # d'un écart de poids : l'écart d'un tel titre vient de la redistribution.
    by_cap = getattr(getattr(plan.model, "spec", None), "kind", "") == "reference"
    reasons: dict[str, list[str]] = {}
    for f in state.get("filters") or []:
        if by_cap and not f.get("bloque_achats"):
            continue
        reasons.setdefault(str(f["symbole"]), []).append(str(f["code"]))
    tilt = pd.Series(state.get("overlays", {}).get("tilt"), dtype=float)
    rows = []
    for s in syms:
        a, b = float(w0.get(s, 0.0)), float(w1.get(s, 0.0))
        if abs(b - a) < 5e-6:
            continue
        why = []
        if s in reasons:
            why.append("filtre " + ", ".join(sorted(set(reasons[s]))))
        if not by_cap and s in tilt.index and float(tilt[s]) != 0:
            why.append(f"inclinaison {_num(float(tilt[s]), 2, True)} σ")
        rows.append({"symbole": s, "poids_sans_notes": a, "poids_avec_notes": b, "ecart": b - a,
                     "motif": " ; ".join(why)})
    rows.sort(key=lambda r: (r["ecart"], r["symbole"]))
    tot0, tot1 = float(w0.sum()), float(w1.sum())
    if not rows:
        txt = ("Effet des notes sur les poids cibles : aucun (ni veto ni filtre sur un titre de la sélection"
               + (" ; en indice discipliné, l'inclinaison n'entre pas dans la sélection par capitalisation"
                  if by_cap else "")
               + f") ; total investi cible {_pct(tot1)} avec ou sans les notes.")
    else:
        cash = tot0 - tot1
        dest = ("le poids retiré est redistribué aux autres lignes par les règles de construction existantes"
                if abs(cash) < 5e-5 else
                f"{_pct(abs(cash))} du portefeuille {'restent en liquidités' if cash > 0 else 'sont investis en plus'} "
                "(règles de construction existantes)")
        txt = (f"Effet des notes sur les poids cibles (même décision recalculée sans aucune note, pour information) : "
               f"{len(rows)} ligne(s) modifiée(s) ; total investi cible {_pct(tot0)} sans les notes, {_pct(tot1)} avec : "
               f"{dest}. Les notes ne changent aucune règle : elles retirent un titre des achats ou inclinent un "
               "score, dans les bornes de la spécification"
               + (" (indice discipliné : l'inclinaison n'entre pas dans la sélection par capitalisation)."
                  if by_cap else "."))
    return {"texte": txt, "lignes": rows, "total_sans_notes": tot0, "total_avec_notes": tot1}


def _notes_trigger(state: Mapping[str, Any] | None, effect: Mapping[str, Any] | None, L: pd.DataFrame,
                   dec: Any) -> dict[str, Any]:
    """Partie « notes » des déclencheurs : ligne datée, filtres actifs, achats bloqués, effet."""
    if not state:
        return {}
    if state.get("erreur"):
        return {"ligne": f"Notes de l'analyste : synthèse indisponible ({state['erreur']})."}
    in_plan = {str(r.symbole) for r in L.itertuples(index=False) if r.cibles > 0 or r.detenus > 0} if len(L) else set()
    eff_rows = {r["symbole"]: r for r in (effect or {}).get("lignes") or []}
    held = {str(r.symbole): int(r.detenus) for r in L.itertuples(index=False)} if len(L) else {}
    filters = []
    gap = float((effect or {}).get("total_sans_notes") or 0.0) - float((effect or {}).get("total_avec_notes") or 0.0)
    fate = ("ce poids est redistribué aux autres lignes par les règles de construction" if abs(gap) < 5e-5 else
            f"{_pct(abs(gap))} du portefeuille {'restent en liquidités' if gap > 0 else 'sont investis en plus'} "
            "(règles de construction)")
    for f in state.get("filters") or []:
        g = dict(f)
        s = str(g["symbole"])
        g["dans_le_plan"] = s in in_plan
        if g.get("bloque_achats"):
            e = eff_rows.get(s)
            if e is not None and e["poids_sans_notes"] > 0 and e["poids_avec_notes"] <= 1e-9:
                g["effet_poids"] = (f"aucun achat (poids cible {_pct(e['poids_sans_notes'])} sans les notes, 0 % avec) ; "
                                    f"{fate} (voir le tableau d'effet)")
            elif e is not None:
                g["effet_poids"] = (f"poids cible {_pct(e['poids_sans_notes'])} sans les notes, "
                                    f"{_pct(e['poids_avec_notes'])} avec (aucun renforcement)")
            elif held.get(s, 0) > 0:
                g["effet_poids"] = "ligne détenue conservée sans renforcement"
            else:
                g["effet_poids"] = "titre hors de la sélection : aucun effet sur cet ordre"
        filters.append(g)
    m = state["moment"]
    return {"ligne": state["line"], "mode": state["mode"], "date_des_cours": m.prices_date,
            "connues_au": m.known_at, "seance_application": m.session, "n_connues": state["n_known"],
            "n_en_vigueur": state["n_in_force"], "n_manuelles": state["n_manual"], "n_filtres": state["n_filters"],
            "n_avec_score": state["n_scored"], "message_scores": state["scores_message"], "filtres": filters,
            "blocages": [g for g in filters if g.get("bloque_achats")], "effet": dict(effect) if effect else None}


def _index_evaluation(t: pd.Timestamp, panel_dir: Path | None, panels_given: bool, store: Any,
                      notes_known_at: Any = None) -> tuple[list[dict[str, Any]], str]:
    if panels_given and panel_dir is None:
        return [], "Évaluation des indices non calculée : panel long non fourni (passer panel_dir)."
    try:
        from brvm_alpha.notes import index_eval

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = index_eval.evaluate_indices(str(panel_dir) if panel_dir is not None else None, store, t,
                                              notes_known_at=notes_known_at)
    except Exception as exc:
        return [], f"Évaluation des indices indisponible ({exc.__class__.__name__} : {exc})."
    rows = []
    keep = ("IDX:BRVM-C", "IDX:BRVM-C-TR", "IDX:BRVM-30", "IDX:PRESTIGE", "IDX:PRINCIPAL")
    for code in [c for c in keep if c in res.index] + [c for c in res.index if c not in keep]:
        r = res.loc[code]
        reasons = list(r.get("reasons") or [])
        lecture = next((x for x in reasons if x.startswith("Score composite")), reasons[0] if reasons else "")
        # Position qui change par la seule composante « notes » : dit en clair dans la lecture (transparence ;
        # aucune pondération n'est modifiée).
        ex_stance = r.get("stance_ex_notes")
        ex_stance = str(ex_stance) if isinstance(ex_stance, str) and ex_stance else None
        ex_score = r.get("composite_ex_notes")
        ex_score = float(ex_score) if ex_score is not None and np.isfinite(float(ex_score)) else None
        flips = bool(ex_stance and ex_score is not None and r.get("z_notes") is not None
                     and np.isfinite(float(r.get("z_notes"))) and ex_stance != str(r.get("stance", "")))
        if flips:
            effet = next((x for x in reasons if x.startswith("Effet des notes")), "")
            lecture = f"{lecture} {effet}".strip()
        rows.append({"indice": code, "libelle": str(r.get("label", code)), "position": str(r.get("stance", "")),
                     "confiance": float(r.get("confidence", np.nan)), "score": float(r.get("composite", np.nan)),
                     "lecture": lecture, "position_sans_notes": ex_stance, "score_sans_notes": ex_score,
                     "position_changee_par_les_notes": flips})
    return rows, ""


# ---------------------------------------------------------------------------
# Explications (BrvmAlpha.explain)
# ---------------------------------------------------------------------------


def _explain_one(model: Any, dec: Any, t: pd.Timestamp, panels: Mapping[str, Any], sym: str, held: Any) -> dict[str, Any]:
    """``model.explain`` sur **la** décision de l'ordre (copie du modèle dont ``decide`` renvoie la
    décision déjà calculée : l'état des poches annuelles ne peut pas la modifier)."""
    ex = copy.copy(model)
    ex.decide = lambda *a, **k: dec  # noqa: ARG005 - la décision de l'ordre fait foi
    return ex.explain(t, panels, sym, held)


def _short_explanation(e: Mapping[str, Any], kind: str, extra: str = "") -> str:
    parts: list[str] = []
    sc = e.get("score") or {}
    if kind != "reference":
        rank, n = sc.get("rank"), sc.get("n_ranked")
        if rank:
            parts.append(f"rang {rank}/{n}, score {_num(sc.get('final'), 2, True)}")
        blocks = [(b, v) for b, v in (e.get("blocks") or {}).items() if not v.get("research_only")]
        top = sorted(blocks, key=lambda kv: -abs(float(kv[1].get("contribution") or 0.0)))[:3]
        if top:
            parts.append("blocs : " + ", ".join(f"{b} {_num(v.get('contribution'), 2, True)}" for b, v in top))
    caps = e.get("caps") or {}
    if caps.get("line_detail"):
        parts.append(f"plafond de ligne {caps['line_detail']}")
    elif caps.get("upper") is not None and np.isfinite(caps.get("upper", np.nan)):
        parts.append(f"plafond {_pct(caps['upper'], 1)}")
    if e.get("construction_reason"):
        parts.append(str(e["construction_reason"]))
    if extra:
        parts.append(extra)
    rf = (e.get("risk_flags") or {}).get("active") or []
    if rf:
        parts.append("filtres : " + ", ".join(rf))
    if not e.get("eligible", True):
        uni = e.get("universe") or {}
        parts.append("non éligible : " + str(uni.get("reasons") or uni.get("reason") or ""))
    return " ; ".join(p for p in parts if p)


def _explanations(plan: _Plan, t: pd.Timestamp, panels: Mapping[str, Any], n_rejected: int = 5) -> list[dict[str, Any]]:
    model, dec = plan.model, plan.decision
    kind = model.spec.kind
    held = plan.held_w if len(plan.held_w) else None
    w = dec.weights
    elig = dec.universe.index[dec.universe["eligible"].astype(bool)]
    if kind == "reference":
        shares = _wide_upto(panels, "shares", t)
        close = _wide_upto(panels, "close_raw", t)
        if isinstance(shares, pd.DataFrame) and isinstance(close, pd.DataFrame) and len(shares) and len(close):
            cap = (close.iloc[-1] * shares.iloc[-1].reindex(close.columns)).reindex(elig).dropna()
            order = list(cap.sort_values(ascending=False).index)
        else:
            order = list(elig)
        rank_of = {s: i + 1 for i, s in enumerate(order)}
    else:
        final = dec.score["final"].reindex(elig).dropna()
        order = list(final.sort_values(ascending=False).index)
        rank_of = {s: i + 1 for i, s in enumerate(order)}
    retained = sorted((s for s in w.index if float(w[s]) > 0),
                      key=lambda s: (-round(float(w[s]), 12), rank_of.get(s, 10 ** 6), s))
    rejected = [s for s in order if s not in retained][:n_rejected]
    out = []
    for status, names in (("retenu", retained), ("écarté", rejected)):
        for s in names:
            try:
                e = _explain_one(model, dec, t, panels, s, held)
            except Exception as exc:  # pragma: no cover - explication indisponible
                out.append({"symbole": s, "statut": status, "rang": rank_of.get(s), "poids": float(w.get(s, 0.0)),
                            "texte_court": f"explication indisponible ({exc.__class__.__name__})", "texte": ""})
                continue
            extra = ""
            if kind == "reference" and status == "écarté" and (e.get("risk_flags") or {}).get("block_buys"):
                # Titre que sa capitalisation ferait retenir, écarté parce que ses achats sont bloqués (D8 : un
                # titre à achat bloqué et non détenu est écarté) : le dire, au lieu de « hors des 20 plus grosses ».
                extra = (f"capitalisation n° {rank_of.get(s)} parmi les éligibles : achat bloqué par un filtre de "
                         "risque, titre non détenu écarté de la sélection (D8)")
            elif kind == "reference" and status == "écarté":
                extra = f"capitalisation n° {rank_of.get(s)} parmi les éligibles : hors des 20 plus grosses (D8)"
            elif kind == "reference":
                extra = f"capitalisation n° {rank_of.get(s)} parmi les éligibles"
            out.append({"symbole": s, "statut": status, "rang": rank_of.get(s), "poids": float(w.get(s, 0.0)),
                        "texte_court": fr_texte(_short_explanation(e, kind, extra if not e.get("construction_reason")
                                                                   or status == "écarté" else "")),
                        "texte": fr_texte(e.get("text", "")), "plafonds": e.get("caps", {}),
                        "filtres": (e.get("risk_flags") or {}).get("active", []),
                        "score": (e.get("score") or {}).get("final")})
    return out


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def _valuation_regime(panels: Mapping[str, Any], t: pd.Timestamp) -> dict[str, Any]:
    mk = _get(panels, "market")
    if not isinstance(mk, pd.DataFrame) or "risk_premium" not in mk.columns:
        return {"regime": None}
    m = mk.copy()
    if "date" in m.columns:
        m = m.set_index(pd.to_datetime(m["date"]))
    m = m[m.index <= t]
    if not len(m):
        return {"regime": None}
    prime = float(pd.to_numeric(m["risk_premium"], errors="coerce").dropna().iloc[-1]) if m["risk_premium"].notna().any() else float("nan")
    if not np.isfinite(prime):
        return {"regime": None}
    regime = "chère" if prime < 1.0 else "bon marché" if prime > 4.0 else "neutre"
    label = {"chère": "cher"}.get(regime, regime)  # clé historique « chère » ; texte accordé : marché « cher »
    return {"regime": regime, "libelle": label, "prime": prime,
            "texte": f"prime de risque du BOC {_num(prime)} : marché « {label} » (information, jamais un signal, §4.5)"}


def _names(panel_dir: Path | None, panels: Mapping[str, Any]) -> dict[str, str]:
    nm = _get(panels, "names")
    if isinstance(nm, (pd.Series, Mapping)):
        return {str(k): str(v) for k, v in dict(nm).items()}
    if panel_dir is None or not (panel_dir / "equities.parquet").exists():
        return {}
    try:
        eq = pd.read_parquet(panel_dir / "equities.parquet", columns=["date", "symbol", "name"])
        return eq.sort_values("date").groupby("symbol")["name"].last().astype(str).to_dict()
    except Exception:
        return {}


def recommend(
    asof: Any,
    capital: float,
    *,
    panels: Mapping[str, Any] | None = None,
    holdings: Mapping[str, int] | None = None,
    cash: float | None = None,
    variant: str | None = None,
    costs: str | CostModel = "central",
    notes_store: Any = None,
    validation_dir: str | Path | None = DEFAULT_VALIDATION_DIR,
    horizon_months: int = 12,
    n_boot: int = 5000,
    seed: int = DEFAULT_SEED,
    registry_path: str | Path | None = None,
    panel_dir: str | Path | None = None,
    sessions: Any = None,
    tolerance: float = LIMIT_TOLERANCE,
    max_participation: float = MAX_PARTICIPATION,
    mean_block_weeks: float = BLOCK_WEEKS,
    comparison: bool = True,
    explanations: bool = True,
    index_evaluation: bool = True,
    today: Any = None,
    notes_known_at: Any = None,
) -> OrdreDeBataille:
    """Ordre de bataille à la date ``asof`` pour un capital ``capital`` (FCFA).

    Parameters
    ----------
    asof
        Date de décision : dernière séance du panel au plus tard à cette date (clôture du BOC) ;
        exécution à partir de la séance suivante.
    capital
        Capital total (FCFA). Il fixe le plancher de capacité U5 du modèle. Sans ``cash``, les
        liquidités valent ``capital − valeur des titres détenus``.
    panels
        Panels de :func:`brvm_alpha.strategy.build_panels` (défaut : construits depuis
        ``panel_dir`` ou ``data/panel``).
    holdings
        Titres détenus (symbole → nombre de titres), valorisés au dernier cours.
    cash
        Liquidités disponibles (FCFA) ; la valeur du portefeuille vaut ``titres + cash``.
    variant
        ``None`` : choix par :func:`choose_variant` (REF tant que S1 n'est pas exécuté, A en
        comparaison) ; sinon la variante imposée.
    costs
        Scénario de coûts du §7.2 (``"central"``, ``"stress"``…) ou ``CostModel``.
    notes_store
        Journal des notes de l'analyste (``NoteStore``) ; ``None`` : journal du dépôt
        (``notes="auto"`` du modèle) ; ``False`` : aucune note.
    validation_dir, registry_path
        Résultats du test S1 (``metrics.json``) et registre des essais (fenêtre d'estimation).
    horizon_months, n_boot, seed, mean_block_weeks
        Horizon des revenus et de la distribution ; bootstrap stationnaire (5 000 tirages, blocs
        de 8 semaines, graine fixée : résultat reproductible).
    tolerance, max_participation
        Tolérance des prix limites (1 %) ; participation maximale par séance (10 % de la MDV63).
    comparison, explanations, index_evaluation
        Calculs facultatifs (variante de comparaison, explications ``BrvmAlpha.explain``,
        ``notes.index_eval``).
    today
        Date du jour pour le contrôle de fraîcheur du panel (défaut : date système quand le panel est
        lu sur disque ; aucun contrôle pour des panels fournis en mémoire sans ``today``). Si la
        décision porte sur le dernier BOC du panel et que des séances manquent avant ``today`` :
        avertissement en tête (« panel en retard »), ordres marqués **périmés**, et aucune séance
        d'exécution antérieure à ``today``.
    notes_known_at
        Instant de connaissance des notes (UTC ; une date seule désigne la fin de la journée).
        ``None`` (défaut sûr) : **mode historique**, les notes suivent la règle stricte à la date
        de décision (aucune anticipation ; appels programmatiques, dates passées). Donné (**mode
        direct**, passé par la ligne de commande, l'interface et le rapport quand la décision
        porte sur le dernier BOC) : les notes connues à cet instant sont appliquées à la séance
        qui suit le dernier BOC (ou la suivante si sa coupure de 09h00 UTC est passée) ; veto,
        inclinaisons et filtres R entrent dans la décision, sans changer aucune règle.
    """
    t0 = time.time()
    if capital is None or float(capital) <= 0:
        raise ValueError("capital doit être > 0")
    pdir = Path(panel_dir) if panel_dir is not None else (DEFAULT_PANEL_DIR if panels is None else None)
    panels_given = panels is not None
    if panels is None:
        from brvm_alpha.strategy import build_panels

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            panels = build_panels(pdir)
    t_req = pd.Timestamp(asof).normalize()
    t = _decision_date(panels, t_req)
    if sessions is None and pdir is not None and (pdir / "sessions.parquet").exists():
        sessions = pd.read_parquet(pdir / "sessions.parquet", columns=["date"])
    if sessions is None:
        close_any = _get(panels, "close_raw")
        close_any = close_any if isinstance(close_any, pd.DataFrame) else _get(panels, "close")
        sessions = close_any.index
    cfg = settings.load_strategy_config()
    cm, cost_name = _cost_model(costs, cfg)
    taxes = TaxModel()
    close_df = _wide_upto(panels, "close_raw", t)
    close_df = close_df if close_df is not None and len(close_df) else _wide_upto(panels, "close", t)
    close = close_df.iloc[-1].astype(float)
    hold = {str(k).upper().strip(): int(v) for k, v in (holdings or {}).items() if int(v) != 0}
    warn: list[str] = []
    blocked_off_boc: dict[str, dict[str, Any]] = {}
    for s, q in hold.items():
        if q < 0:
            raise ValueError(f"{s} : nombre de titres négatif (vente à découvert interdite, art. 1123)")
        if s not in close.index or not np.isfinite(close.get(s, np.nan)):
            # Titre connu du panel mais absent du BOC à t (suspendu de longue date, radié) : dernier cours
            # connu − 10 % (§7.1.7), ligne bloquée « hors BOC » ; seuls les symboles jamais vus sont refusés.
            hist = close_df[s].dropna() if s in close_df.columns else pd.Series(dtype=float)
            hist = hist[np.isfinite(hist) & (hist > 0)]
            if not len(hist):
                raise ValueError(f"{s} : titre inconnu ou sans cours au {_d(t)}")
            last_px, last_dt = float(hist.iloc[-1]), pd.Timestamp(hist.index[-1])
            val_px = floor_to_tick(last_px * 0.90) or last_px
            close = close.copy()
            close[s] = val_px
            blocked_off_boc[s] = {"dernier_cours": last_px, "date_dernier_cours": last_dt, "cours_valorisation": val_px}
            warn.append(f"{s} : absent du BOC du {_d(t)} (dernier cours {_num(last_px, 0)} FCFA le {_d(last_dt)}) : "
                        f"ligne bloquée « hors BOC », valorisée {_num(val_px, 0)} FCFA (dernier cours − 10 %, §7.1.7), "
                        "aucun ordre possible ; les autres lignes sont calculées normalement.")
    held_value = float(sum(q * float(close[s]) for s, q in hold.items()))
    if cash is None:
        cash_v = float(capital) - held_value
        if cash_v < 0:
            warn.append(f"titres détenus ({_fcfa(held_value)}) supérieurs au capital : liquidités ramenées à 0")
            cash_v = 0.0
    else:
        cash_v = float(cash)
        if cash_v < 0:
            raise ValueError("cash doit être >= 0 (pas de découvert)")
        if abs(held_value + cash_v - float(capital)) > 1.0:
            warn.append(f"capital ({_fcfa(capital)}) différent de titres + liquidités "
                        f"({_fcfa(held_value + cash_v)}) : la valeur du portefeuille retenue est titres + liquidités")
    nav = held_value + cash_v
    if nav <= 0:
        raise ValueError("valeur du portefeuille nulle")
    if t != t_req:
        warn.append(f"{_d(t_req)} n'est pas une séance du panel : décision à la clôture du {_d(t)}")
    # Fraîcheur du panel : le dernier BOC attendu avant aujourd'hui est-il présent ?
    stale: list[pd.Timestamp] = []
    exec_after: pd.Timestamp | None = None
    full_close = _get(panels, "close_raw")
    full_close = full_close if isinstance(full_close, pd.DataFrame) and len(full_close) else _get(panels, "close")
    last_panel = pd.Timestamp(pd.DatetimeIndex(full_close.index).max()).normalize()
    if today is not None or not panels_given:
        tt = pd.Timestamp(today) if today is not None else pd.Timestamp.now()
        if tt.tzinfo is not None:
            tt = tt.tz_convert("UTC").tz_localize(None)
        today_ts = tt.normalize()
        if t >= last_panel and t_req >= last_panel:
            stale = expected_missing_sessions(last_panel, today_ts)
            exec_after = max(t, today_ts - pd.Timedelta(days=1))
    stale_msg = None
    if stale:
        stale_msg = (f"PANEL EN RETARD de {len(stale)} séance(s) : dernier BOC du panel le {_d(last_panel)}, "
                       f"séance(s) attendue(s) avant aujourd'hui : {', '.join(_d(x) for x in stale[:5])}"
                       + ("…" if len(stale) > 5 else "") + " (jours ouvrés hors fériés fixes, hypothèse). Lancer "
                       "`python -m brvm_alpha update` puis recalculer : les ordres ci-dessous sont PÉRIMÉS (cours, "
                       f"bornes et prix limites du {_d(t)}), à ne pas transmettre.")
    choice = choose_variant(variant, validation_dir, registry_path)
    warn = ([stale_msg] if stale_msg else []) + list(choice["avertissements"]) + warn
    from brvm_alpha.strategy import VARIANT_SPECS

    if choice["variante"] not in VARIANT_SPECS:
        raise ValueError(f"variante inconnue {choice['variante']!r}")
    choice["description"] = VARIANT_SPECS[choice["variante"]].description
    window = estimation_window(t, bool(choice["s1_execute"]))
    notes_arg = "auto" if notes_store is None else (None if notes_store is False else notes_store)
    store_for_events = None
    if notes_store is None:
        try:
            from brvm_alpha.notes.store import NoteStore

            store_for_events = NoteStore()
        except Exception:
            store_for_events = None
    elif notes_store is not False:
        store_for_events = notes_store
    common = dict(t=t, panels=panels, nav=nav, cash=cash_v, held_q=hold, close=close, costs=cm, cost_name=cost_name,
                  taxes=taxes, notes_arg=notes_arg, calendar_past=sessions, horizon_months=horizon_months,
                  n_boot=n_boot, seed=seed, window=window, tolerance=tolerance, max_participation=max_participation,
                  mean_block=mean_block_weeks, cfg=cfg, exec_after=exec_after, blocked=blocked_off_boc,
                  notes_known_at=notes_known_at)
    plan = _build_plan(variant=choice["variante"], **common)
    L = plan.lines
    # Notes de l'analyste : état daté (deux instants) et effet sur les poids cibles. Calendrier des
    # séances du panel (lacunes de BOC comprises) s'il est sur disque, comme l'évaluation des indices.
    notes_cal: Any = None
    if pdir is not None and (pdir / "sessions.parquet").exists():
        try:
            notes_cal = pd.read_parquet(pdir / "sessions.parquet")
        except Exception:
            notes_cal = None
    notes_state = _notes_state(plan, t, store_for_events, notes_cal if notes_cal is not None else close_df.index)
    notes_effect = _notes_effect(plan, choice["variante"], t, panels, nav, notes_state)
    names = _names(pdir, panels)
    if len(L):
        L.insert(1, "nom", [names.get(s, s) for s in L["symbole"]])
    csum = _cost_summary(L, nav, cash_v, cm, cost_name)
    spec_target = float((cfg.get("portfolio") or {}).get("gross_equity", 0.98))
    csum["cible_specification"] = spec_target
    csum["reliquat_plafonds"] = max(0.0, spec_target - float(csum["cible_pct"]))
    warn += _capital_warnings(L, csum, nav, cm, spec_target, choice["variante"])
    quantities = {r.symbole: int(r.cibles) for r in L.itertuples(index=False) if r.cibles > 0}
    div = dividend_schedule(quantities, t, panels, taxes=taxes, horizon_months=horizon_months, calendar=sessions)
    rev = _revenue_summary(div, nav, float(csum["investi_apres"]), horizon_months)
    dist, _weekly = _distribution_for(plan, panels, nav, csum, window, horizon_months, n_boot, seed, mean_block_weeks)
    res_s1 = (choice.get("resultats_s1") or {}).get(choice["variante"]) or {}
    if dist.get("disponible") and res_s1.get("actif_tr_an") is not None:
        act = float(res_s1["actif_tr_an"])
        st1 = res_s1.get("statut") or "n.d."
        dist["resultat_s1"] = {
            "variante": choice["variante"], "actif_tr_an": act, "statut": st1,
            "court": f"test S1 : {choice['variante']} {_pct(act, 1, True)}/an contre le TR ({st1})",
            "texte": (f"Résultat du test unique S1 (metrics.json, fait de simulation) : la variante appliquée "
                      f"{choice['variante']} fait {_pct(act, 1, True)} par an contre le Composite TR (statut {st1}). "
                      "La P(battre le TR) de la distribution à 12 mois est une fréquence historique aux poids actuels, "
                      "pas une probabilité de surperformance future.")}
    # Stress : module dédié s'il existe, sinon chocs du §9.3.
    values = {r.symbole: float(r.valeur_apres) for r in L.itertuples(index=False) if r.cibles > 0}
    weights_after = {s: v / nav for s, v in values.items()}
    ext, stress_src = _external_stress(values, weights_after, panels, t, nav)
    if ext is not None:
        stress = ext
    else:
        extra: dict[str, int] = {}
        try:
            liq = replace_costs(cm, half_spread_mult=2.0 * cm.half_spread_mult)
            pre = (plan.model, plan.decision)
            p6 = _build_plan(variant=choice["variante"], **{**common, "costs": liq,
                                                             "max_participation": max_participation / 2},
                             prebuilt=pre)
            extra["ST6"] = max(int(_cost_summary(p6.lines, nav, cash_v, liq, "liquidité")["total"]) - csum["total"], 0)
            sev = settings.cost_scenario("severe", cfg)
            p7 = _build_plan(variant=choice["variante"], **{**common, "costs": sev}, prebuilt=pre)
            extra["ST7"] = max(int(_cost_summary(p7.lines, nav, cash_v, sev, "sévère")["total"]) - csum["total"], 0)
        except Exception as exc:  # pragma: no cover - surcoût non calculable
            stress_src += f" (surcoûts ST6/ST7 non calculés : {exc.__class__.__name__})"
        guard = bool(plan.decision.risk["data_guard"].any()) if "data_guard" in plan.decision.risk.columns else None
        beta = dist.get("beta_hebdo") if dist.get("disponible") else None
        stress = stress_scenarios(values, nav, beta=beta, extra_costs=extra, data_guard=guard)
    # Indices, déclencheurs, explications.
    if index_evaluation:
        idx_rows, idx_msg = _index_evaluation(t, pdir, panels_given, store_for_events, notes_known_at)
    else:
        idx_rows, idx_msg = [], "Évaluation des indices non demandée."
    pub_known = max(t, t_req)
    if notes_known_at is not None and notes_state and not notes_state.get("erreur") \
            and notes_state["moment"].known_at is not None:
        pub_known = max(pub_known, notes_state["moment"].known_at.tz_localize(None))
    trig = _triggers(plan, t, panels, div, sessions, horizon_months, store_for_events, idx_rows, idx_msg,
                     known_at=pub_known, notes_state=notes_state, notes_effect=notes_effect)
    for b in (trig.get("notes") or {}).get("blocages") or []:
        if b.get("dans_le_plan") or "sans les notes" in str(b.get("effet_poids", "")):
            warn.append(f"ACHAT BLOQUÉ par une note : {b['symbole']} ({b['code']}, {b['libelle']}) — note "
                        f"{str(b['note_id'])[:12]} du {_d(b.get('note_date'))} « {b.get('note_titre', '')} », "
                        f"{b.get('duree') or 'durée ouverte'}. Effet : {b.get('effet_poids', '')}. Pour lever le "
                        f"blocage : {b.get('lever', '')}.")
    expl = _explanations(plan, t, panels) if explanations else []
    # Comparaison.
    comp = None
    if comparison and choice.get("comparaison") and choice["comparaison"] in VARIANT_SPECS:
        cv = choice["comparaison"]
        cp = _build_plan(variant=cv, **common)
        c_sum = _cost_summary(cp.lines, nav, cash_v, cm, cost_name)
        c_q = {r.symbole: int(r.cibles) for r in cp.lines.itertuples(index=False) if r.cibles > 0}
        c_div = dividend_schedule(c_q, t, panels, taxes=taxes, horizon_months=horizon_months, calendar=sessions)
        c_rev = _revenue_summary(c_div, nav, float(c_sum["investi_apres"]), horizon_months)
        c_dist, _ = _distribution_for(cp, panels, nav, c_sum, window, horizon_months, n_boot, seed, mean_block_weeks)
        cl = cp.lines[cp.lines["cibles"] > 0]
        comp = {"variante": cv, "description": VARIANT_SPECS[cv].description,
                "texte": (f"Variante {cv} ({VARIANT_SPECS[cv].description}) calculée dans les mêmes conditions, "
                          "pour information : elle n'est pas recommandée tant que le test S1 ne l'a pas validée."),
                "lignes": [{k: getattr(r, k) for k in ("symbole", "cibles", "poids_cible", "poids_realise",
                                                       "prix_limite", "montant_net", "sens", "quantite")}
                           for r in cl.itertuples(index=False)],
                "couts": c_sum, "revenus": c_rev, "distribution": c_dist,
                "messages_modele": list(cp.decision.messages)}
    # Exécution : résumé.
    tr_tab = plan.tranches
    first = plan.sessions[0]
    over = [f"{r.symbole} ({int(r.seances)} séances)" for r in L.itertuples(index=False)
            if r.sens != "aucun" and int(r.seances) > MAX_CARRY_SESSIONS]
    pdep = [r.symbole for r in L.itertuples(index=False) if r.participation_depassee]
    exec_info = {**plan.exec_info, "premiere_seance": first,
                 "derniere_seance": tr_tab["date"].max() if len(tr_tab) else first,
                 "participation_max_regle": float(max_participation), "tolerance": float(tolerance),
                 "reductions": plan.reductions, "au_dela_report": over, "participation_depassee": pdep,
                 "calendrier": ("Calendrier futur : jours ouvrés hors fériés à date fixe observés 2017-2026 "
                                "(01/01, 01/05, 07/08, 15/08, 01/11, 15/11, 25/12) ; fêtes mobiles inconnues "
                                "(hypothèse)")}
    if pdep:
        warn.append("Un seul titre dépasse 10 % de la MDV63 : " + ", ".join(pdep) + " (participation signalée).")
    if exec_info.get("non_finance"):
        warn.append("Achats non finançables dans l'horizon de planification : "
                    + ", ".join(f"{k} {v}" for k, v in exec_info["non_finance"].items()))
    if dist.get("biais_fenetre"):
        warn.append(dist["biais_fenetre"])
    if dist.get("biais_retrospectif"):
        warn.append(dist["biais_retrospectif"])
    if (dist.get("resultat_s1") or {}).get("texte"):
        warn.append(dist["resultat_s1"]["texte"])
    exec_info["perime"] = bool(stale)
    exec_info["seances_manquantes"] = list(stale)
    exec_info["dernier_boc_panel"] = last_panel
    exec_info["lignes_hors_boc"] = sorted(blocked_off_boc)
    val = _valuation_regime(panels, t)
    faits = [
        f"Cours de clôture et cours de référence du BOC du {_d(t)} (source : BOC, data/panel).",
        "Bornes de ±7,5 % autour de la référence ajustée ; pas de cotation 1 FCFA sous 100 FCFA, 5 FCFA au-delà ; "
        "quotité 1 titre (instruction I-A, §7.1, §11).",
        "Règlement-livraison J+2 depuis le 04/12/2025 (instruction 03-2025) ; la BRVM annule les ordres en attente "
        "le jour ex.",
        "Dividendes : derniers montants nets publiés au BOC (ligne (d) ou correction publiée) ; IRVM CI 12 %, SN 10 % "
        "(2026), NE 7 %, ML 7 % (§7.3).",
        "Commissions BRVM 0,20 % et DC/BR 0,10 % par côté (barèmes primaires).",
        f"Statut du test S1 : {choice['statut_A']} ({choice['registre']}).",
        f"Variante appliquée : {choice['variante']} ({choice['motif']}).",
    ]
    if val.get("texte"):
        faits.append(val["texte"][0].upper() + val["texte"][1:] + ".")
    estimations = [
        "Demi-spread par titre : ½ × spread médian de clôture sur 120 séances (carnet du BOC), plancher d'un demi-pas ; "
        f"défaut {_pct(cm.half_spread_default, 2)} si non mesuré.",
        "Impact de marché κ·√π par tranche, π = montant de la tranche / MDV63 (valeur médiane échangée sur 63 séances, "
        "séances sans échange comptées à 0).",
        "Montants bruts et nets au cours de référence (le prix d'exécution réel peut différer jusqu'au prix limite) ; "
        "provision « pire cas » au prix limite.",
        "Dates de détachement et de paiement projetées sur le mois habituel ; AGO = date ex − 42 jours (médiane).",
        f"Distribution à {horizon_months} mois par bootstrap stationnaire ({window['texte']}) : distribution "
        "historique, pas une prévision.",
        "Stress du §9.3 : pertes calculées sous hypothèse de linéarité (β) ou de choc direct par pays.",
    ]
    hypotheses = [
        f"Scénario de coûts « {cost_name} » : courtage {_pct(cm.sgi_commission)} × (1 + taxe {_pct(cm.vat_on_commission, 0)}) "
        "— taxe [NON VÉRIFIÉ] (TVA ou TAF) ; redevance AMF-UMOA nulle (introuvable).",
        f"Impact κ = {_num(cm.impact_coef, 3)} (« 50 pb à 10 % de participation », aucune étude d'impact BRVM).",
        f"Droits de garde {_pct(cm.annual_custody)} par an et tenue de compte {_fcfa(cm.account_fee_per_line_fcfa)} par "
        "ligne et par an (SGI de type BICI ; 0 chez FGI).",
        "Dernier dividende reconduit à l'identique (aucune prévision de résultat) ; IRVM BF 12,5 %, BJ par émetteur, "
        "TG inconnu : [NON VÉRIFIÉ] ; aucun impôt sur les plus-values (personne physique résidente, NV).",
        "Calendrier futur des séances : jours ouvrés hors fériés à date fixe (fêtes mobiles inconnues).",
        "Personne physique résidente ; aucun ordre au-delà de la cible ; la décision du jour est reconduite jusqu'à "
        "la revue mensuelle.",
    ]
    meta = {"duree_s": round(time.time() - t0, 2), "cout_scenario": cost_name, "valorisation": val,
            "stress_source": stress_src, "fenetre_estimation": window, "n_boot": int(n_boot), "graine": int(seed),
            "horizon_mois": int(horizon_months), "notes": "auto" if notes_store is None else
            ("désactivées" if notes_store is False else "fournies"),
            "notes_mode": (notes_state or {}).get("mode") if notes_state and not notes_state.get("erreur") else None,
            "empreinte_config": settings.config_fingerprint(cfg), "modele": repr(plan.model),
            "s1_lu": bool(window["s1_utilise"])}
    return OrdreDeBataille(
        asof=t, asof_demande=t_req, capital=float(capital), valeur_portefeuille=nav, liquidites_initiales=cash_v,
        variante=choice["variante"], choix=choice, lignes=L, tranches=tr_tab, execution=exec_info, couts=csum,
        dividendes=div, revenus=rev, distribution=dist, stress=stress, declencheurs=trig, explications=expl,
        comparaison=comp, faits=faits, estimations=estimations, hypotheses=hypotheses,
        avertissements=_dedup(warn), messages_modele=[fr_texte(m) for m in list(plan.decision.messages) + plan.messages if m],
        meta=meta)


def replace_costs(costs: CostModel, **changes: Any) -> CostModel:
    """Copie d'un ``CostModel`` avec des champs modifiés (scénarios ST6/ST7)."""
    from dataclasses import replace

    return replace(costs, **changes)


def _dedup(xs: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(x for x in xs if x))


#: Alias français du point d'entrée (exporté par ``brvm_alpha.portfolio``).
ordre_de_bataille = recommend


class _CallableModule(types.ModuleType):
    """Le sous-module porte le nom de sa fonction principale : ``from brvm_alpha.portfolio import
    recommend`` renvoie le module (règle des sous-modules de Python), qui reste donc **appelable**
    comme la fonction : ``recommend("2026-11-20", 10_000_000)``."""

    def __call__(self, *args: Any, **kwargs: Any) -> OrdreDeBataille:
        return recommend(*args, **kwargs)


sys.modules[__name__].__class__ = _CallableModule
