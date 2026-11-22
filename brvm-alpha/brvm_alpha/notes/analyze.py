"""Analyse d'une note -> :class:`NoteAnalysis` (document 07, §3.2 à §3.4, §6.3 à §6.6).

Chaîne de traitement (« les chiffres d'abord », §3.2) :

1. **cibles** : cibles saisies + entités liées dans le titre et le texte (:mod:`.entities`) ;
2. **type d'événement** : règles du §6.4 sur le titre, puis le début du texte (:mod:`.lexicon`) ;
3. **chiffres** : résultat net, PNB, chiffre d'affaires, dividende et leur variation, au
   format français (« 245,3 milliards FCFA contre 210,1 milliards », « 1 234 567 FCFA »,
   « +16,8 % », « en hausse de 18,2 % ») ; dates (ex-dividende, paiement, registres, AG) ;
4. **sentiment numérique** : ``s = clip(Δ%/25, −2, 2)`` pour RN, PNB, CA (25 % = seuil
   réglementaire d'alerte sur résultats) et ``clip(Δdiv%/20, −2, 2)`` pour le dividende ;
   −2 si le dividende disparaît alors qu'il était versé. ``s_num_doc`` = moyenne pondérée
   (RN 1, dividende 0,8, PNB 0,6, CA 0,5), à l'échelle du document 07 ([−2, 2]) ; le champ
   ``s_num`` du contrat ([−1, 1]) en est la moitié (affichage seulement) ;
5. **ton lexical** : ``(P − N) / (P + N + 1)`` ; les termes d'un indicateur chiffré sont
   remplacés par le chiffre (§3.4, règle 4) ;
6. **score** : ``clip(0,7·s_num_doc + 0,3·tone, −1, 1)`` si un chiffre a été extrait,
   sinon ``tone`` — formule exacte du document 07 §3.4 (règle 5, « les nombres
   d'abord »), bornée à [−1, 1] sans changer ni le signe ni le rapport des poids ; si un
   indicateur pondéré n'est décrit qu'en mots alors qu'un autre est chiffré, le poids 0,7
   est partagé en proportion des poids des indicateurs (pondération par couverture) ;
   pour une note de l'analyste avec ``stance`` / ``conviction``, combinaison bornée du
   jugement (±0,8 au plus) et du texte, avec signalement des contradictions ;
7. **matérialité**, **confiance** (champ structuré 1,0 > regex sur texte 0,6 > OCR 0,3),
   **filtres de risque** R1-R10 lisibles dans le seul texte, et **lecture** en français.

Lecture des documents (``read_document``, appelée par ``research.enrich_documents``) :

- **tableaux** d'un texte mis en page par ``pdftotext -layout`` : ligne de l'agrégat (chiffre
  d'affaires, produit net bancaire, résultat avant impôt, résultat net), colonnes rattachées à
  l'en-tête (périodes N et N−1 de même nature, variation en valeur et en %), unité du tableau
  (FCFA, milliers, millions, milliards) ; phrases lues colonne par colonne ;
- **garde-fous** : une variation n'est retenue que si elle est écrite ou recalculée à partir de
  deux montants de même unité et de même périmètre ; la variation écrite doit concorder avec
  les montants à 1 point près (à l'arrondi d'affichage des montants près) ; base négative ou
  nulle, ou variation au-delà de ±300 % : montants gardés, **aucun score numérique**, mention
  « base non comparable » (le changement de signe du résultat net se lit alors dans le ton) ;
  période du tableau et du document cohérente avec le type de la note ; comptes consolidés
  préférés aux comptes sociaux, jamais mélangés ; en-tête, unité ou appariement ambigus :
  **aucun chiffre** (score fondé sur le ton seul, confiance basse). Mieux vaut aucun chiffre
  qu'un chiffre faux ;
- chaque chiffre retenu porte sa **ligne source** (texte exact du document) dans
  ``extracted["<agrégat>_source"]`` ; les chiffres écartés et leur motif sont dans
  ``extracted["doc_rejected"]`` ;
- le résultat avant impôt (``rai``) est lu et affiché mais **n'entre pas dans le score** (le
  document 07 ne pondère que RN, PNB, CA et dividende).

Aucun score n'est une prévision certaine : c'est une lecture factuelle et chiffrée, avec
son degré de confiance, à valider hors échantillon avant tout usage (S5, poids initial 0).
"""

from __future__ import annotations

import datetime as _dt
import math
import re
import unicodedata
from dataclasses import dataclass, replace as _dc_replace
from typing import Any

import numpy as np
import pandas as pd

from .entities import EntityLinks, alias_key, link_entities, theme_exposure
from .lexicon import TermHit, detect_event_type, scan, tone_from_hits
from .model import (
    EVENT_TYPES,
    TARGET_SPECIFICITY,
    Note,
    NoteAnalysis,
    _APOSTROPHES,
    _DASHES,
    _SPACES,
    _calendar,
    asof_utc,
    fold,
    fold_with_map,
    normalize_event_type,
    normalize_targets,
    first_tradable_session,
    stance_sign,
    target_kind,
    target_label,
    to_day,
    to_utc,
)

ANALYZE_VERSION = "notes-analyze/1 (BRVM-FR v0)"

#: Échelles du sentiment numérique (document 07 §3.4 et §6.7).
NUM_SCALE_PCT = {"rn": 25.0, "pnb": 25.0, "ca": 25.0, "div": 20.0}
NUM_WEIGHTS = {"rn": 1.0, "div": 0.8, "pnb": 0.6, "ca": 0.5}
W_NUM, W_TONE = 0.7, 0.3
#: Part de la composante chiffrée qu'un ton de signe contraire peut retirer au plus quand la variation
#: du résultat net est lue (« nombres d'abord » : le ton ne renverse pas le signe des chiffres ; tant que
#: la formule 0,7·s_num + 0,3·tone garde au moins le quart de la part chiffrée, elle s'applique telle quelle).
TONE_OPPOSITE_CAP = 0.75
#: Poids maximal du jugement de l'analyste et borne de son effet sur le score.
ANALYST_CAP = 0.8
#: Date d'entrée en vigueur de l'instruction BRVM 01-2025 (alertes sur résultats, R10).
R10_EFFECTIVE = pd.Timestamp("2025-10-01", tz="UTC")
EUR_FCFA = 655.957
#: Longueur maximale du texte analysé (comme ``research.MAX_TEXT_CHARS``) : l'analyse d'un
#: texte saisi très long reste bornée en temps ; le texte complet reste dans le journal.
MAX_ANALYZE_CHARS = 20_000

#: Matérialité de base par type d'événement (choix de conception, à valider).
BASE_MATERIALITY: dict[str, float] = {
    "PROFIT_WARNING": 0.90, "TAKEOVER": 0.90, "SUSPENSION": 0.85, "DELISTING": 0.80, "RES_ANNUAL": 0.75,
    "DIV_NOTICE": 0.70, "ACT_Q1": 0.60, "RES_S1": 0.60, "CAP_INC": 0.60, "AG_CANCEL": 0.60, "OPV_IPO": 0.60,
    "NOTATION_SOUVERAINE": 0.60, "POLITIQUE": 0.60, "SECURITE": 0.60, "ACT_Q3": 0.50, "RATING": 0.50,
    "RESUMPTION": 0.50, "MACRO": 0.50, "REGULATOR": 0.45, "MATIERES_PREMIERES": 0.45, "SPLIT": 0.40,
    "REVERSE_SPLIT": 0.40, "MGMT_CHANGE": 0.40, "INDEX_CHANGE": 0.40, "AG_RESOLUTIONS": 0.40, "MANUAL": 0.40,
    "THRESHOLD": 0.35, "AG_CONVOCATION": 0.30, "PRESS": 0.30, "OTHER": 0.20,
}
TARGET_FACTOR = {"symbol": 1.0, "index": 0.9, "sector": 0.8, "country": 0.8, "market": 0.8, "theme": 0.7}

#: Types dont le titre normé porte une direction même sans terme du lexique.
_DIRECTIONAL_EVENTS = {"PROFIT_WARNING", "SUSPENSION", "DELISTING", "AG_CANCEL", "RESUMPTION", "TAKEOVER"}
_RESULT_EVENTS = {"RES_ANNUAL", "RES_S1", "ACT_Q1", "ACT_Q3"}
#: Filtres qu'un rapport de résultats ne fait que citer (ils ont leur propre avis : suspension, AG,
#: notation, augmentation de capital, offre publique, fractionnement).
_CITED_ONLY_RISKS = frozenset({"R1", "R2", "R4", "R5", "R6", "R8"})
_MACRO_EVENT_TYPES = {"POLITIQUE", "SECURITE", "MATIERES_PREMIERES", "MACRO", "NOTATION_SOUVERAINE"}

# ---------------------------------------------------------------------------
# Nombres au format français
# ---------------------------------------------------------------------------

NUM = r"[+\-]?\s?(?:\d{1,3}(?:[ .]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
_NUM_RX = re.compile(r"(?<![\d,.])" + NUM + r"(?![\d])")
_UNIT = (
    r"milliards?|mds?|mrds?|md|millions?|mns?|mio|milliers?|mille|"
    r"m(?=\s*(?:de\s+)?(?:f\s?cfa|fcfa|xof)\b)|k(?=\s*(?:f\s?cfa|fcfa|xof)\b)"
)
_CUR = r"f\s?cfa|fcfa|xof|francs?\s+cfa|euros?|eur\b|usd|dollars?"
AMOUNT_RX = re.compile(
    r"(?<![\d,.])(?P<num>" + NUM + r")(?![\d])\s*(?P<unit>" + _UNIT + r")?(?:\s+de)?\s*(?P<cur>" + _CUR + r")?(?![a-z])"
)
PCT_RX = re.compile(r"(?<![\d,.])(?P<num>" + NUM + r")(?![\d])\s?(?:%|pour\s?cent)")
_MULT = {
    "milliard": 1e9, "milliards": 1e9, "md": 1e9, "mds": 1e9, "mrd": 1e9, "mrds": 1e9,
    "million": 1e6, "millions": 1e6, "mn": 1e6, "mns": 1e6, "mio": 1e6, "m": 1e6,
    "millier": 1e3, "milliers": 1e3, "mille": 1e3, "k": 1e3,
}

_UP_W = re.compile(
    r"(?<![a-z])(?:hausses?|progress\w*|croissance|croit|augment\w*|accroi\w*|amelior\w*|bond\w*|envol\w*|"
    r"doubl\w*|tripl\w*|rebond\w*|grimp\w*|redress\w*)(?![a-z])"
)
_DOWN_W = re.compile(
    r"(?<![a-z])(?:baiss\w*|recul\w*|repli\w*|chut\w*|diminu\w*|contract\w*|degrad\w*|deterior\w*|effondr\w*|"
    r"plong\w*|regress\w*|flechi\w*|erosion|erod\w*|retrait)(?![a-z])"
)
_RATIO_W = re.compile(
    r"(?<![a-z])(?:taux|marges?|ratios?|coefficients?|rendements?|parts?|detient|detenue?s?|capital|payout|"
    r"flottant|represente\w*|pese|participation|couverture|solvabilite|rentabilite|roe|roa)(?![a-z])"
)
_PREV_W = re.compile(r"(?<![a-z])(?:contre|vs\.?|versus|par\s+rapport\s+a|comparativement\s+a|a\s+comparer\s+a)(?![a-z])")
#: « passe de X à Y », « est porté de X à Y », « se réduit de X à Y », « ramené de X à Y » : X est le
#: niveau précédent, Y le niveau courant (recette du 22/11/2026 : X était pris pour le montant courant
#: dès que le verbe n'était pas « passer », et pour tout dividende).
_FROM_TO = re.compile(
    r"(?<![a-z])(?:pass\w*|port\w*|ramen\w*|relev\w*|revien\w*|revenu\w*|se\s+redui\w*|redui\w*|"
    r"s'alourdi\w*|se\s+creus\w*|mont\w*|tomb\w*)\s+de\s+(?P<a>" + NUM + r")\s*(?P<ua>" + _UNIT
    + r")?(?:\s+de)?\s*(?:" + _CUR + r")?\s*"
    r"(?:en\s+20\d\d\s+)?a\s+(?P<b>" + NUM + r")\s*(?P<ub>" + _UNIT + r")?"
)
#: Montant en dollars dans la fenêtre d'un indicateur (« pour atteindre 2,0 milliards de dollars »).
_USD_AMOUNT_RX = re.compile(r"(?<![\d,.])" + NUM + r"(?![\d])\s*(?:" + _UNIT + r")?(?:\s+de)?\s*(?:usd|dollars?|\$)")
#: Motif d'écart d'une variation exprimée dans une autre monnaie que le FCFA (titre coté en FCFA).
FOREIGN_CURRENCY = "variation exprimée en dollars (titre coté en FCFA) : non retenue"

#: Mentions d'indicateurs (texte normalisé). « Bénéfice par action » n'est pas le RN.
_IND_PATTERNS = {
    "rn": (
        r"resultats?\s+nets?(?:\s+(?:consolides?|sociaux|social|part\s+du\s+groupe|global|de\s+l'exercice|pdg))*"
        r"(?!\s+(?:par\s+action|unitaire))|benefices?(?:\s+nets?)?(?!\s+(?:net\s+)?par\s+action|\s+avant\s+impot)|\brn\b|"
        r"resultats?\s+de\s+l'exercice|pertes?\s+nettes?"
    ),
    "pnb": r"produit\s+net\s+bancaire|\bpnb\b",
    "ca": r"chiffres?\s+d'affaires|\bca\b(?!\s+a\s+decide)|ventes",
    "div": (
        r"montant\s+(?:net\s+|brut\s+)?(?:du\s+)?dividende|dividendes?(?:\s+(?:nets?|bruts?|unitaires?|par\s+action|"
        r"ordinaires?|global|proposes?|verses?))*"
    ),
}
_IND_RX = re.compile("|".join(f"(?P<{k}>{v})" for k, v in _IND_PATTERNS.items()))
_SENT_END = re.compile(r"(?<!\d)[.!?](?!\d)|[;\n]|(?<=\d)\.(?=\s)")
#: « une baisse de 8 % du chiffre d'affaires » : le pourcentage appartient à l'indicateur
#: qui le SUIT (tournure française courante), pas à celui dont la fenêtre le contient.
_PCT_OF_RX = re.compile(r"\s+(?:du|de\s+la|de\s+l'|des|d'|de)\s*(?:" + _IND_RX.pattern + r")")


def parse_fr_number(s: str) -> float | None:
    """Nombre au format français ou anglais : « 1 234 567 », « 12,5 », « 245.3 », « +16,8 », « −3 »."""
    if s is None:
        return None
    t = fold(str(s)).replace(" ", "")
    if not t:
        return None
    sign = 1.0
    if t[0] in "+-":
        sign = -1.0 if t[0] == "-" else 1.0
        t = t[1:]
    if not t or not t[0].isdigit():
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", t):
        t = t.replace(".", "")  # séparateur de milliers
    try:
        return sign * float(t)
    except ValueError:
        return None


@dataclass
class _Amount:
    value: float  # FCFA
    start: int
    end: int
    has_unit: bool
    multiplier: float
    surface: str


_COMPOSITE_GAP = re.compile(r"\s*(?:et\s*)?$")  # NUM peut commencer par une espace


def _amounts(norm: str, a: int, b: int) -> list[_Amount]:
    """Montants de ``norm[a:b]`` ; « 12 milliards 500 millions de FCFA » vaut 12,5 Md."""
    out = _raw_amounts(norm, a, b)
    merged: list[_Amount] = []
    for x in out:
        prev = merged[-1] if merged else None
        if (prev is not None and prev.has_unit and x.has_unit and x.multiplier < prev.multiplier
                and abs(x.value) < prev.multiplier and _COMPOSITE_GAP.match(norm[prev.end : x.start])
                and prev.value >= 0 and x.value >= 0):
            merged[-1] = _Amount(prev.value + x.value, prev.start, x.end, True, prev.multiplier,
                                 (prev.surface + " " + x.surface).strip())
            continue
        merged.append(x)
    return merged


def _raw_amounts(norm: str, a: int, b: int) -> list[_Amount]:
    out = []
    for m in AMOUNT_RX.finditer(norm, a, b):
        unit = (m.group("unit") or "").strip()
        cur = (m.group("cur") or "").strip()
        if not unit and not cur:
            continue
        v = parse_fr_number(m.group("num"))
        if v is None:
            continue
        mult = _MULT.get(unit, 1.0)
        if cur.startswith("eur"):
            mult *= EUR_FCFA
        elif cur.startswith(("usd", "dollar")):
            continue  # pas de conversion USD (taux variable)
        out.append(_Amount(v * mult, m.start(), m.end(), bool(unit), mult, m.group(0).strip()))
    return out


def _pcts(norm: str, a: int, b: int) -> list[tuple[float, int, int, bool, str]]:
    out = []
    for m in PCT_RX.finditer(norm, a, b):
        raw = m.group("num")
        v = parse_fr_number(raw)
        if v is None:
            continue
        explicit = raw.strip()[:1] in "+-"
        out.append((v, m.start(), m.end(), explicit, m.group(0).strip()))
    return out


def _pct_owners(norm: str, mentions: list[tuple[str, int, int]]) -> dict[int, tuple[str, int]]:
    """Pourcentages suivis de « du/de la/des <indicateur> » : ``{début du % : (indicateur, début de la mention)}``."""
    owners: dict[int, tuple[str, int]] = {}
    for m in PCT_RX.finditer(norm):
        om = _PCT_OF_RX.match(norm, m.end())
        if om is None or not om.lastgroup:
            continue
        # Début de la mention de l'indicateur (après « du », « de la »…) : c'est celui que
        # ``_IND_RX.finditer`` donne pour cette mention.
        owners[m.start()] = (om.lastgroup, om.start(om.lastgroup))
    return owners


def _direction(text: str) -> int:
    """+1 / −1 selon le dernier mot de direction de ``text`` ; 0 si aucun."""
    last_up = max((m.end() for m in _UP_W.finditer(text)), default=-1)
    last_dn = max((m.end() for m in _DOWN_W.finditer(text)), default=-1)
    if last_up < 0 and last_dn < 0:
        return 0
    return 1 if last_up > last_dn else -1


def _sentence_end(norm: str, pos: int) -> int:
    m = _SENT_END.search(norm, pos)
    return m.start() if m else len(norm)


def _sentence_start(norm: str, pos: int) -> int:
    last = 0
    for m in _SENT_END.finditer(norm, 0, pos):
        last = m.end()
    return last


def _sentence_figures(text: str, title: str = "", strict: bool = False) -> dict[str, Any]:
    """RN, PNB, CA et dividende (niveau, niveau précédent, variation) lus dans des **phrases**.

    Renvoie un dictionnaire ``{indicateur: {...}}`` pour ``rn``, ``pnb``, ``ca``, ``div``
    (clés ``value``, ``prev``, ``growth`` en décimal, ``growth_from`` = ``pct`` | ``levels``,
    ``consistent``, ``surface``) ; pour le dividende : ``net``, ``gross``, ``prev``,
    ``growth``, ``total``. Les montants sont en FCFA. Sans garde-fou : voir :func:`extract_figures`.
    ``strict=True`` (lecture d'un document) : « ventes » ne vaut pas chiffre d'affaires (dans un
    rapport, « les ventes de janvier à avril reculent de 18 % » parle de volumes ou d'une sous-période).
    """
    full = (title.strip() + "\n" if title and title.strip() else "") + (text or "")
    norm, idx = fold_with_map(full)
    res: dict[str, Any] = {}
    mentions = [(m.lastgroup, m.start(), m.end()) for m in _IND_RX.finditer(norm)]
    # Une mention précédée de « contre » (« perte nette de 3,2 Md contre un bénéfice de
    # 1,6 Md ») décrit le niveau précédent : elle ne coupe pas la fenêtre et n'est pas lue seule.
    comparative = {
        k for k, (_, ms, _) in enumerate(mentions)
        if re.search(r"(?:contre|vs\.?|versus|par\s+rapport\s+a)\s+(?:un|une|le|la|les|des|l')?\s*$", norm[max(0, ms - 25) : ms])
    }
    owners = _pct_owners(norm, mentions)
    for i, (ind, s, e) in enumerate(mentions):
        if i in comparative:
            continue
        if ind in res and res[ind].get("growth") is not None and (ind != "div" or res[ind].get("net") is not None):
            continue  # première mention exploitable retenue
        if ind != "div" and _NOT_SUBJECT_RX.search(norm[max(0, s - 16) : s]):
            continue  # « capitaux propres hors résultat de l'exercice », « impôt sur le résultat net »
        if strict and ind == "ca" and norm[s:e] == "ventes":
            continue
        # Pourcentages placés AVANT la mention et qui lui appartiennent (« hausse de 30 % du
        # résultat net ») ; ceux qui appartiennent à un autre indicateur sont exclus.
        own = sorted(ps for ps, (oi, oms) in owners.items() if oms == s and oi == ind)
        foreign = {ps for ps, (oi, oms) in owners.items() if not (oms == s and oi == ind)}
        stop = _sentence_end(norm, e)
        nxt = next((ms for k, (_, ms, _) in enumerate(mentions) if k > i and ms >= e and k not in comparative), None)
        if nxt is not None:
            stop = min(stop, nxt)  # les chiffres suivants appartiennent à l'indicateur suivant
        stop = min(stop, e + 220)
        mention_txt = norm[s:e]
        lookback = norm[max(_sentence_start(norm, s), s - 40) : s]
        surface = full[idx[s] : idx[min(stop, len(idx)) - 1] + 1] if stop > s else full[idx[s] : idx[e - 1] + 1]
        sent_lo = _sentence_start(norm, s)
        if ind == "div":
            info = _extract_div(norm, e, stop, mention_txt, own=own, foreign=foreign, lo=sent_lo)
        else:
            info = _extract_level(norm, e, stop, mention_txt, lookback, negative=("perte" in mention_txt),
                                  own=own, foreign=foreign, lo=sent_lo)
        if not info:
            continue
        info["surface"] = surface.strip()
        prev = res.get(ind)
        if ind == "div" and prev is not None:
            # Avis en deux mentions (« dividende brut : 2 612 FCFA ; dividende net : 2 298,75 FCFA ») :
            # les champs se complètent, aucun n'est écrasé.
            for k, v in info.items():
                if k == "surface":
                    continue
                if prev.get(k) is None and v is not None:
                    prev[k] = v
            continue
        if prev is None or (prev.get("growth") is None and info.get("growth") is not None):
            res[ind] = info
    return res


def _owned_pcts(norm: str, own: list[int] | None, lo: int) -> list[tuple[float, int, int, bool, str, int]]:
    """Pourcentages appartenant à la mention mais placés avant elle, avec le début de leur contexte."""
    out = []
    for ps in own or []:
        m = PCT_RX.match(norm, ps)
        if m is None:
            continue
        v = parse_fr_number(m.group("num"))
        if v is None:
            continue
        explicit = m.group("num").strip()[:1] in "+-"
        out.append((v, m.start(), m.end(), explicit, m.group(0).strip(), max(lo, ps - 40)))
    return out


#: L'agrégat n'est pas le sujet de la phrase : « hors résultat de l'exercice », « y compris le résultat net ».
_NOT_SUBJECT_RX = re.compile(r"(?<![a-z])(?:hors|y\s+compris|incluant|dont|sur)\s+(?:le\s+|la\s+|les\s+|l')?$")
_YEAR_ONLY_RX = re.compile(r"\s*(?:19|20)\d\d\s*")
#: Comparaisons qui ne sont pas d'une année sur l'autre (trimestre précédent, budget, début d'année).
_NOT_YOY_RX = re.compile(
    r"(?:par\s+rapport\s+(?:au|a\s+la|aux)|vs\.?|versus|comparee?\s+(?:au|a\s+la))\s+(?:trimestre|semestre|mois)\s+precedent|"
    r"(?:trimestre|semestre|mois)\s+precedent|par\s+rapport\s+au\s+(?:t[1-4]|s[12]|[1-4]\s?(?:er|e|eme)\s+trimestre)(?![a-z0-9])|"
    r"par\s+rapport\s+(?:au|aux)\s+(?:budget|previsions?|objectifs?)|vs\.?\s+budget|"
    r"par\s+rapport\s+a\s+(?:fin\s+)?decembre|depuis\s+(?:le\s+debut\s+de\s+l'annee|(?:fin\s+)?decembre)|"
    r"en\s+glissement\s+trimestriel"
)
#: Un montant précédé d'un mot de variation est un **écart**, pas un niveau (« en hausse de +141 MFCFA »,
#: « soit une baisse de 916 millions de FCFA », « en retrait de 831 millions, à −579 millions »).
_DELTA_BEFORE = re.compile(
    r"(?:hausses?|baisses?|progressions?|augmentations?|reculs?|diminutions?|croissances?|replis?|ameliorations?|"
    r"retraits?|ecarts?|variations?|regressions?|gains?)\s+(?:de|d'environ|de\s+pres\s+de|de\s+plus\s+de)\s*$|"
    r"(?:augment\w*|progress\w*|recul\w*|baiss\w*|diminu\w*|croit|accroit|chut\w*|bondi\w*|amelior\w*|degrad\w*|"
    r"grimp\w*)\s+(?:de|de\s+pres\s+de|de\s+plus\s+de)\s*$"
)


def _extract_level(norm: str, a: int, b: int, mention: str, lookback: str, negative: bool,
                   own: list[int] | None = None, foreign: set[int] | None = None, lo: int = 0) -> dict[str, Any]:
    amounts = _amounts(norm, a, b)
    deltas = [x for x in amounts if _DELTA_BEFORE.search(norm[max(a, x.start - 36) : x.start])]
    amounts = [x for x in amounts if x not in deltas]
    for x in amounts:
        # « un résultat net de (-) 864 millions » : notation comptable d'un montant négatif
        if x.value > 0 and re.search(r"\(\s*-\s*\)\s*$", norm[max(0, x.start - 6) : x.start]):
            x.value = -x.value
    foreign = foreign or set()
    pcts = [(v, ps, pe, ex, sf, max(a, ps - 40)) for v, ps, pe, ex, sf in _pcts(norm, a, b) if ps not in foreign]
    owned = _owned_pcts(norm, own, lo)
    pcts = owned + pcts
    cur = prev = None
    m = _FROM_TO.search(norm, a, b)
    if m:
        va = parse_fr_number(m.group("a"))
        vb = parse_fr_number(m.group("b"))
        mult = _MULT.get((m.group("ub") or m.group("ua") or "").strip(), 1.0)
        mult_a = _MULT.get((m.group("ua") or "").strip(), mult)
        if va is not None and vb is not None:
            prev, cur = va * mult_a, vb * mult
    if cur is None and amounts:
        cur = amounts[0].value
        # « contre X » : niveau précédent (unité héritée si absente).
        pm = _PREV_W.search(norm, amounts[0].end, b)
        if pm:
            after = [x for x in amounts[1:] if x.start >= pm.end() and x.start - pm.end() <= 32]
            if after:
                prev = after[0].value
            else:
                nm = _NUM_RX.search(norm, pm.end(), min(b, pm.end() + 20))
                # « par rapport à 2025 », « contre 12 % », « contre le 30 juin » : ni une année, ni un
                # pourcentage, ni un jour ne sont le montant précédent.
                if nm and not _YEAR_ONLY_RX.fullmatch(nm.group(0)) and not re.match(
                        r"\s?(?:%|pour\s?cent|er\b|janvier|fevrier|mars|avril|mai|juin|juillet|aout|sept|oct|nov|dec|/)",
                        norm[nm.end() : nm.end() + 12]):
                    v = parse_fr_number(nm.group(0))
                    if v is not None:
                        prev = v * amounts[0].multiplier
    if negative:
        if cur is not None and cur > 0:
            cur = -cur
        # « la perte nette se réduit de 477 à 346 millions », « perte nette de 346 millions contre 477
        # millions » : le montant précédent est lui aussi une perte, sauf si le texte nomme un bénéfice.
        if prev is not None and prev > 0 and not re.search(
                r"(?<![a-z])(?:benefices?|profits?|excedents?|resultats?\s+(?:nets?\s+)?(?:positifs?|beneficiaires?))(?![a-z])",
                norm[a:b]):
            prev = -prev
    window = norm[a:b]
    if cur is not None and cur > 0 and re.search(r"deficitaire|negatif|deficit", window[:80]):
        cur = -cur
    if cur is not None and cur > 0 and amounts and re.search(
            r"(?<![a-z])(?:une\s+|la\s+|en\s+)?pertes?(?![a-z])", norm[a : amounts[0].start]) and not _PREV_W.search(
            norm[a : amounts[0].start]):
        cur = -cur  # « le résultat net est une perte qui s'élève à 346 millions »
    growth_lv = None
    if cur is not None and prev not in (None, 0):
        growth_lv = (cur - prev) / abs(prev)
    growth_pct = None
    owned_pos = {x[1] for x in owned}
    for v, ps, pe, explicit, surf, ctx in pcts:
        before = norm[ctx:ps]
        if _NOT_YOY_RX.search(norm[pe : min(len(norm), pe + 70)]) or _NOT_YOY_RX.search(before):
            continue  # « +15 % par rapport au trimestre précédent » : pas une variation N / N−1
        if ps >= a and _RATIO_W.search(norm[a:ps]):
            continue  # « le PNB … un coefficient d'exploitation à 36,7 % » : le pourcentage est celui du ratio
        if explicit:
            growth_pct = v / 100.0
            break
        d = _direction(before)
        if d == 0 and _RATIO_W.search(norm[max(ctx, ps - 25) : ps]):
            continue
        if d == 0 and ps in owned_pos:
            continue  # « représente 35 % du PNB » : un ratio, pas une variation
        if d == 0 and ps - a <= 40 and not re.search(r"(?:^|\s)a\s+$", norm[max(a, ps - 4) : ps]):
            d = _direction(lookback)
        if d == 0 and growth_lv is not None and abs(abs(v) / 100.0 - abs(growth_lv)) < 0.02:
            d = 1 if growth_lv >= 0 else -1
        if d == 0:
            continue
        growth_pct = d * abs(v) / 100.0
        break
    if cur is None and growth_pct is None:
        return {}
    info: dict[str, Any] = {"value": cur, "prev": prev}
    if growth_pct is not None and cur is None and _USD_AMOUNT_RX.search(norm, a, b):
        # Niveau donné en dollars seulement (aucun montant en FCFA dans la phrase) : la variation est
        # celle des comptes en dollars (ETI : +12 % en dollars, +8 % en FCFA dans le tableau du même document).
        info["currency"] = "USD"
    if growth_pct is not None:
        info["growth"] = growth_pct
        info["growth_from"] = "pct"
        if growth_lv is not None:
            info["growth_levels"] = growth_lv
            info["consistent"] = abs(growth_pct - growth_lv) <= 0.01 + 1e-9  # écart toléré : 1 point
    elif growth_lv is not None:
        info["growth"] = growth_lv
        info["growth_from"] = "levels"
        if deltas and cur is not None and prev is not None:
            # Variation en valeur écrite (« soit une baisse de 916 millions ») : elle recoupe les deux montants.
            d = abs(deltas[0].value)
            if abs(abs(cur - prev) - d) <= max(0.6 * deltas[0].multiplier, 0.006 * d):
                info["consistent"] = True
    else:
        info["growth"] = None
    return info


def _extract_div(norm: str, a: int, b: int, mention: str, own: list[int] | None = None,
                 foreign: set[int] | None = None, lo: int = 0) -> dict[str, Any]:
    amounts = [x for x in _amounts(norm, a, b)]
    foreign = foreign or set()
    info: dict[str, Any] = {"net": None, "gross": None, "prev": None, "growth": None, "total": None}
    per_share = [x for x in amounts if abs(x.value) < 1e6]
    totals = [x for x in amounts if abs(x.value) >= 1e6]
    if totals:
        info["total"] = totals[0].value
    prev_pos = None
    pm = _PREV_W.search(norm, a, b)
    if pm:
        prev_pos = pm.end()
    ft = _FROM_TO.search(norm, a, b)
    if ft:
        # « le dividende net par action passe de 1 500 FCFA à 1 800 FCFA » : 1 500 est l'ancien montant.
        va, vb = parse_fr_number(ft.group("a")), parse_fr_number(ft.group("b"))
        if va is not None and vb is not None and abs(va) < 1e6 and abs(vb) < 1e6 and not (ft.group("ua") or ft.group("ub")):
            q = "gross" if re.search(r"(?<![a-z])bruts?(?![a-z])", mention) else "net"
            if q == "net" and not re.search(r"(?<![a-z])nets?(?![a-z])", mention):
                info["assumed_net"] = True
            info[q], info["prev"] = vb, va
            per_share = [x for x in per_share if not (ft.start() <= x.start < ft.end())]
    for k, x in enumerate(per_share):
        after = norm[x.end : x.end + 12]
        before = norm[max(a, x.start - 12) : x.start]
        if prev_pos is not None and x.start >= prev_pos and info["prev"] is None:
            info["prev"] = x.value
            continue
        q = None
        if re.search(r"(?<![a-z])nets?(?![a-z])", after) or re.search(r"(?<![a-z])nets?(?![a-z])", before):
            q = "net"
        elif re.search(r"(?<![a-z])bruts?(?![a-z])", after) or re.search(r"(?<![a-z])bruts?(?![a-z])", before):
            q = "gross"
        elif k == 0 and not ft:
            q = "gross" if re.search(r"(?<![a-z])bruts?(?![a-z])", mention) else "net"
            if q == "net" and not re.search(r"(?<![a-z])nets?(?![a-z])", mention):
                info["assumed_net"] = True
        if q and info[q] is None:
            info[q] = x.value
    pcts = _owned_pcts(norm, own, lo) + [
        (v, ps, pe, ex, sf, max(a, ps - 40)) for v, ps, pe, ex, sf in _pcts(norm, a, b) if ps not in foreign
    ]
    for v, ps, pe, explicit, surf, ctx in pcts:
        before = norm[ctx:ps]
        d = (1 if v >= 0 else -1) if explicit else _direction(before)
        if d == 0:
            continue
        info["growth"] = abs(v) * d / 100.0
        info["growth_from"] = "pct"
        break
    base = info["net"] if info["net"] is not None else info["gross"]
    if info["growth"] is None and base is not None and info["prev"]:
        info["growth"] = (base - info["prev"]) / abs(info["prev"])
        info["growth_from"] = "levels"
    if all(info[k] is None for k in ("net", "gross", "prev", "growth", "total")):
        return {}
    return info


# ---------------------------------------------------------------------------
# Garde-fous d'une variation (lecture des documents, tâche « lecture » du 22/11/2026)
# ---------------------------------------------------------------------------

#: Écart toléré entre la variation écrite et celle recalculée à partir des deux montants (1 point).
CONSISTENCY_TOL = 0.01
#: Borne de plausibilité : au-delà de ±300 %, la base n'est pas comparable (pas de score numérique).
MAX_ABS_GROWTH = 3.0
NOT_COMPARABLE = "base non comparable"
INCONSISTENT = "variation écrite incohérente avec les montants"
_EPS = 1e-9


def _consistent(written: float, levels: float) -> bool:
    """Variation écrite et variation recalculée à moins d'un point d'écart ?"""
    return abs(written - levels) <= CONSISTENCY_TOL + _EPS


def _vet_figure(f: dict[str, Any]) -> dict[str, Any]:
    """Garde-fous d'une variation ; modifie et renvoie ``f``.

    Une variation n'est gardée que si elle est écrite ou recalculée à partir de deux montants,
    si la variation écrite concorde avec les montants (écart ≤ 1 point), si la base est
    strictement positive et si la variation reste dans ±300 %. Sinon ``growth`` passe à
    ``None`` (aucun score numérique) et ``growth_rejected`` garde la valeur écartée :

    - variation écrite incohérente avec les montants : ``reject`` = motif, **le chiffre entier
      est écarté** (on ne sait pas lequel des nombres est mal lu) ;
    - base négative ou nulle, ou variation au-delà de ±300 % : les montants restent,
      ``note`` = « base non comparable ».
    """
    g = f.get("growth")
    if g is None or f.get("reject") or f.get("note"):
        return f
    prev = f.get("prev")
    if f.get("growth_from") == "pct" and f.get("growth_levels") is not None and not _consistent(g, f["growth_levels"]):
        f["reject"] = INCONSISTENT
        f["consistent"] = False
    elif (prev is not None and prev <= 0) or not np.isfinite(g) or abs(g) > MAX_ABS_GROWTH + _EPS or (
            prev is None and f.get("value") is not None and f["value"] < 0):
        # (une perte « en baisse de 27 % » se réduit : sans le montant précédent, le sens ne se lit pas)
        f["note"] = NOT_COMPARABLE
    else:
        return f
    f["growth_rejected"] = g
    f["growth"] = None
    return f


# ---------------------------------------------------------------------------
# Lecture des tableaux d'un document (texte de « pdftotext -layout »)
# ---------------------------------------------------------------------------

#: Libellés d'agrégats en tête de ligne d'un tableau (texte normalisé, colonnes conservées).
_ROW_LABELS = {
    "ca": r"(?:total\s+)?chiffres?\s+d'affaires|ca\b",
    "pnb": r"produits?\s+nets?\s+bancaires?|pnb\b",
    "rai": (
        r"resultats?\s+(?:courants?\s+)?avant\s+impots?(?:\s+sur\s+(?:les?\s+)?(?:benefices?|resultats?|societes?))?|"
        r"resultats?\s+des\s+activites\s+ordinaires|rai\b|rao\b"
    ),
    "rn": r"resultats?\s+nets?|benefices?\s+nets?|r\.\s?nets?|rn\b",
}
#: Qualificatifs admis après le libellé (« Résultat net (part du Groupe) », « CA HT », « (1) »).
_ROW_QUAL = (
    r"(?:\s*(?:nets?|consolides?|sociaux|social|globale?|globaux|total|hors\s+taxes?|ht\b|h\.t\.?|cumules?|"
    r"de\s+l'exercice|de\s+la\s+periode|du\s+trimestre|du\s+semestre|de\s+l'ensemble\s+consolide|"
    r"part\s+(?:du\s+)?groupe|pdg\b|apres\s+impots?|comptable|provisoire|d'impots?|semestriel|trimestriel|annuel|"
    r"\(\s*(?:rn|pnb|ca|rai|rao|ht|\d|\*+|consolides?|social|sociaux|part\s+du\s+groupe|provisoire|"
    r"en\s+[^)]{1,40}|(?:m|k|mds?|millions?|milliards?|milliers?)?\s*(?:de\s+)?(?:f\s?cfa|fcfa|xof))\s*\)|\*+))*"
)
_ROW_RX = re.compile(
    r"^\s*(?:[^a-z0-9(]{0,6}|(?:[ivx]{1,4}|[a-z]|\d{1,2})\s?[.)\-]\s+|[a-z]{1,2}\d{1,3}\s+)?(?:"
    + "|".join(f"(?P<{k}>{v})" for k, v in _ROW_LABELS.items())
    + r")" + _ROW_QUAL + r"\s*:?(?=\s|$)"
)
_ROW_IND_LABEL = {"ca": "chiffre d'affaires", "pnb": "produit net bancaire", "rai": "résultat avant impôt",
                  "rn": "résultat net"}
#: Une cellule numérique : montant, pourcentage, écart en points ; négatif entre parenthèses.
_TCELL_RX = re.compile(
    r"(?<![\w.,/])(?P<open>\(\s?)?(?P<sign>[+\-]\s?)?"
    r"(?P<num>\d{1,3}(?:[ .]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)(?!\d)"
    r"(?:\s?(?P<pct>%)|\s?(?P<pts>bps|pbs?|pts?|points?|pp)\b|\s?(?P<unit>milliards?|mds?|mrds?|millions?|mios?|m|k)\b)?"
    r"(?P<star>\s?\*+)?(?P<close>\s?\))?"
)
_FILLER_RX = re.compile(
    r"(?<![a-z0-9])(?:n\.?\s?s\.?|n\s?/\s?a|n\.?d\.?|nc|f\s?cfa|fcfa|xof)(?![a-z0-9])|[\-|*:;=<>~()%]+"
)
_MONTH_NUM = {
    "janvier": 1, "janv": 1, "jan": 1, "fevrier": 2, "fevr": 2, "fev": 2, "mars": 3, "avril": 4, "avr": 4,
    "mai": 5, "juin": 6, "juillet": 7, "juil": 7, "aout": 8, "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10, "novembre": 11, "nov": 11, "decembre": 12, "dec": 12,
}
_MN = "|".join(sorted(_MONTH_NUM, key=len, reverse=True))
_MONTH_KIND = {3: "Q1", 6: "S1", 9: "Q3", 12: "A"}
#: Seules les dates d'arrêté (fin de trimestre) désignent une période ; « le 18 juin 2026 » n'en est pas une.
_CLOSING_DAYS = {(31, 3), (30, 6), (30, 9), (31, 12)}
_ORD_NUM = {"premier": 1, "deuxieme": 2, "second": 2, "troisieme": 3, "quatrieme": 4, "trois": 3, "six": 6,
            "neuf": 9, "douze": 12}
_QUARTER_KIND = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
_MONTHS_KIND = {3: "Q1", 6: "S1", 9: "Q3", 12: "A"}
_Y = r"(20\d\d|\d\d)"
#: Jetons de période d'un en-tête de tableau, par ordre de priorité (le premier occupe la place).
_HDR_PERIOD_RX: tuple[tuple[str, re.Pattern], ...] = (
    ("date", re.compile(r"(?<!\d)(\d{1,2})\s?[/.\-]\s?(\d{1,2})\s?[/.\-]\s?" + _Y + r"(?!\d)")),
    ("datefr", re.compile(r"(?<!\d)(\d{1,2})\s?(?:er)?[\s\-]+(" + _MN + r")\.?[\s\-]+" + _Y + r"(?!\d)")),
    ("quarter", re.compile(
        r"(?<![a-z0-9])[tq]\s?([1-4])[\s\-_/.]*" + _Y + r"(?!\d)|"
        r"(?<![a-z0-9])([1-4])\s?(?:er|e|eme|ieme|nd)?\s*(?:trimestre|trim\.?|t)[\s\-_/.]*(?:de\s+l'(?:annee|exercice)\s+)?"
        + _Y + r"(?!\d)|"
        r"(?<![a-z])(premier|deuxieme|troisieme|quatrieme)\s+trimestre\s+(?:de\s+l'(?:annee|exercice)\s+)?(20\d\d)(?!\d)")),
    ("semester", re.compile(
        r"(?<![a-z0-9])s(?:em\.?)?\s?([12])[\s\-_/.]*" + _Y + r"(?!\d)|"
        r"(?<![a-z0-9])([12])\s?(?:er|e|eme|nd)?\s*semestre[\s\-_/.]*(?:de\s+l'(?:annee|exercice)\s+)?" + _Y + r"(?!\d)|"
        r"(?<![a-z])(premier|deuxieme|second)\s+semestre\s+(?:de\s+l'(?:annee|exercice)\s+)?(20\d\d)(?!\d)")),
    ("months", re.compile(r"(?<![a-z0-9])(3|6|9|12|trois|six|neuf|douze)\s+mois\s+(?:de\s+)?(20\d\d)(?!\d)")),
    ("monthyear", re.compile(r"(?<![a-z])(" + _MN + r")\.?[\s\-]*" + _Y + r"(?!\d)")),
    ("fy", re.compile(r"(?<![a-z])(?:exercice|annee|fy)\s+(20\d\d)(?!\d)")),
    ("year", re.compile(r"(?<![\d/.,\-])(20[0-4]\d)(?![\d/.,])")),
    ("nm1", re.compile(r"(?<![a-z0-9'])n\s?-\s?1(?![a-z0-9])")),
    ("n", re.compile(r"(?<![a-z0-9'\-])n(?![a-z0-9'°\-])")),
)
_HDR_VAR_RX = re.compile(
    r"(?<![a-z])(?:variations?|var\b\.?|evolutions?|evol\b\.?|ecarts?|progression|croissance|(?:en\s+)?valeurs?"
    r"(?:\s+absolues?)?|en\s+pourcentage)(?![a-z])|%"
)
#: « Variation 2026/2025 », « Var. 26/25 », « 2026 vs 2025 » : une colonne de variation, pas deux périodes.
_HDR_VARPAIR_RX = re.compile(
    r"(?<![\d/])(?:20\d\d|\d\d)\s?(?:/|vs\.?|-)\s?(?:20\d\d|\d\d)(?![\d/])|"
    r"(?<![a-z0-9])n\s?(?:/|vs\.?)\s?n\s?-\s?1(?![a-z0-9])"
)
_HDR_RATIO_RX = re.compile(r"%\s*(?:du\s+)?(?:ca|pnb|chiffre)|(?<![a-z])(?:marges?|taux|poids|structure|parts?)(?![a-z])")
_HDR_BUDGET_RX = re.compile(r"(?<![a-z])(?:budgets?|previsions?|previsionnel\w*|objectifs?|prevu\w*|pro\s?forma)(?![a-z])")
#: Déclaration d'unité d'un tableau (« en millions de FCFA », « (MFCFA) », « en milliers de francs CFA »).
_UNIT_RX = re.compile(
    r"(?<![a-z0-9])(?P<u>milliards?|mds?|mrds?|millions?|mios?|milliers?|m|k)\s*(?:de\s+|d')?"
    r"(?P<c>f\s?\.?\s?cfa|fcfa|francs?\s*cfa|xof|francs?|usd|dollars?(?:\s+us)?|\$\s?(?:us|eu)?|euros?|eur)(?![a-z])|"
    r"(?<![a-z0-9])(?P<u2>m|k|mds?)(?P<c2>fcfa|xof)(?![a-z])|"
    r"(?<![a-z])en\s+(?P<c3>f\s?\.?\s?cfa|fcfa|francs?\s*cfa|xof)(?![a-z])"
)
_UNIT_NAME = {1.0: "FCFA", 1e3: "milliers de FCFA", 1e6: "millions de FCFA", 1e9: "milliards de FCFA"}
#: Bornes de vraisemblance d'un agrégat annuel ou intermédiaire d'une société cotée, en FCFA.
_VALUE_BOUNDS = (1e6, 2e13)
#: Sans unité écrite, un montant brut au-dessus de ce seuil ne peut être qu'en FCFA (en milliers, il
#: dépasserait le plus gros agrégat de la cote : environ 2 000 Md de chiffre d'affaires, 400 Md de résultat).
_FCFA_ONLY_ABOVE = {"ca": 4e9, "pnb": 4e9, "rn": 6e8, "rai": 6e8}
_EXPECTED_KIND = {"RES_ANNUAL": "A", "RES_S1": "S1", "ACT_Q1": "Q1", "ACT_Q3": "Q3"}
_KIND_LABEL = {"A": "exercice", "S1": "1er semestre", "Q1": "1er trimestre", "Q3": "3e trimestre",
               "Q2": "2e trimestre", "Q4": "4e trimestre", "S2": "2e semestre"}


def _canon_line(line: str) -> str:
    """Ligne en minuscules sans accents, tirets et apostrophes unifiés, **espaces conservées**
    (les colonnes d'un tableau gardent leur position)."""
    out: list[str] = []
    for ch in line:
        if ch in _APOSTROPHES:
            out.append("'")
        elif ch in _DASHES:
            out.append("-")
        elif ch in _SPACES or ch in "\t\r\v\f":
            out.append(" ")
        elif ch in "œŒ":
            out.append("oe")
        elif ch in "æÆ":
            out.append("ae")
        else:
            rep = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)).lower()
            out.append(rep if rep else " ")
    return "".join(out).rstrip()


@dataclass
class _Cell:
    kind: str  # "amt" | "pct" | "pts"
    value: float  # montant dans l'unité du tableau, ou variation en décimal
    start: int
    end: int
    mult: float | None = None  # unité accolée au montant (« 1 049,8 Mds »)
    prec: float = 1.0  # pas d'affichage du montant (1 pour un entier, 0,1 pour une décimale)
    lone_dash: bool = False  # un « - » isolé précède le nombre : signe détaché ou cellule vide ?


@dataclass
class _HTok:
    kind: str  # "period" | "var" | "ratio" | "budget"
    ptype: str | None  # Q1 | Q2 | S1 | Q3 | Q4 | S2 | A | Y (année seule) | N (N, N−1) | M<mois> | D (date quelconque)
    year: int | None  # année ; 0 et −1 pour N et N−1
    start: int
    end: int
    line: int
    text: str


def _row_cells(rest: str, offset: int) -> list[_Cell] | None:
    """Cellules numériques du reste d'une ligne ; ``None`` s'il reste du texte (ce n'est pas un tableau)."""
    cells: list[_Cell] = []
    junk: list[str] = []
    pos = 0
    for m in _TCELL_RX.finditer(rest):
        gap = rest[pos : m.start()]
        junk.append(gap)
        pos = m.end()
        v = parse_fr_number(m.group("num"))
        if v is None:
            return None
        sign = (m.group("sign") or "").strip()
        lone = bool(re.search(r"(?:^|\s)-\s{2,}$", gap)) and not sign and not m.group("open")
        if sign == "-" or (m.group("open") and m.group("close") and not sign):
            v = -v
        if m.group("pct"):
            cells.append(_Cell("pct", v / 100.0, offset + m.start("num"), offset + m.end("pct")))
        elif m.group("pts"):
            cells.append(_Cell("pts", v, offset + m.start("num"), offset + m.end("pts")))
        else:
            unit = m.group("unit")
            num = m.group("num")
            dec = len(num.rsplit(",", 1)[1]) if "," in num else (
                len(num.rsplit(".", 1)[1]) if num.count(".") == 1 and not re.fullmatch(r"\d{1,3}\.\d{3}", num) else 0)
            cells.append(_Cell("amt", v, offset + m.start("num"), offset + m.end("num"), _MULT.get(unit) if unit else None,
                               10.0 ** -dec, lone))
    junk.append(rest[pos:])
    if _FILLER_RX.sub(" ", " ".join(junk)).strip():
        return None
    return cells


def _table_row(canon: str) -> tuple[str, int, list[_Cell]] | None:
    """``(indicateur, fin du libellé, cellules)`` si la ligne est une ligne d'agrégat d'un tableau :
    libellé reconnu en tête, puis au moins deux montants et rien d'autre que des nombres."""
    m = _ROW_RX.match(canon)
    if not m or not m.lastgroup:
        return None
    cells = _row_cells(canon[m.end():], m.end())
    if not cells or sum(c.kind == "amt" for c in cells) < 2:
        return None
    return m.lastgroup, m.end(), cells


def _year(raw: str) -> int:
    y = int(raw)
    return y if y >= 100 else 2000 + y


def _header_tokens(canon: str, line_no: int) -> list[_HTok]:
    """Jetons d'en-tête d'une ligne : périodes (dates, trimestres, années, N / N−1), colonnes de
    variation, colonnes de ratio, colonnes de budget."""
    toks: list[_HTok] = []
    taken = [False] * len(canon)

    def claim(s: int, e: int) -> bool:
        if any(taken[s:e]):
            return False
        taken[s:e] = [True] * (e - s)
        return True

    for name, rx in _HDR_PERIOD_RX:
        if name == "datefr":
            # Après les dates chiffrées, avant tout le reste : « Var. 2026/2025 » est une colonne
            # de variation, pas deux périodes.
            for m in _HDR_VARPAIR_RX.finditer(canon):
                if claim(m.start(), m.end()):
                    toks.append(_HTok("var", None, None, m.start(), m.end(), line_no, m.group(0)))
        for m in rx.finditer(canon):
            g = [x for x in m.groups() if x is not None]
            ptype: str | None = None
            year: int | None = None
            try:
                if name == "date":
                    day, month, year = int(g[0]), int(g[1]), _year(g[2])
                    if not (1 <= month <= 12 and 1 <= day <= 31):
                        continue
                    ptype = _MONTH_KIND[month] if (day, month) in _CLOSING_DAYS else "D"
                elif name == "datefr":
                    day, month, year = int(g[0]), _MONTH_NUM[g[1]], _year(g[2])
                    ptype = _MONTH_KIND[month] if (day, month) in _CLOSING_DAYS else "D"
                elif name == "quarter":
                    q = _ORD_NUM.get(g[0]) or int(g[0])
                    ptype, year = _QUARTER_KIND[q], _year(g[1])
                elif name == "semester":
                    s = _ORD_NUM.get(g[0]) or int(g[0])
                    ptype, year = ("S1" if s == 1 else "S2"), _year(g[1])
                elif name == "months":
                    n = _ORD_NUM.get(g[0]) or int(g[0])
                    ptype, year = _MONTHS_KIND[n], _year(g[1])
                elif name == "monthyear":
                    month, year = _MONTH_NUM[g[0]], _year(g[1])
                    ptype = _MONTH_KIND.get(month, f"M{month}")
                elif name == "fy":
                    ptype, year = "A", _year(g[0])
                elif name == "year":
                    ptype, year = "Y", int(g[0])
                elif name == "nm1":
                    ptype, year = "N", -1
                else:
                    ptype, year = "N", 0
            except (KeyError, ValueError, IndexError):
                continue
            if year is not None and year > 0 and not 2000 <= year <= 2049:
                continue
            if claim(m.start(), m.end()):
                toks.append(_HTok("period", ptype, year, m.start(), m.end(), line_no, m.group(0)))
    for rx, kind in ((_HDR_BUDGET_RX, "budget"), (_HDR_RATIO_RX, "ratio"), (_HDR_VAR_RX, "var")):
        for m in rx.finditer(canon):
            if claim(m.start(), m.end()):
                toks.append(_HTok(kind, None, None, m.start(), m.end(), line_no, m.group(0)))
    # « N » seul n'est une période que s'il est accompagné de « N-1 » sur la même ligne.
    if not any(t.kind == "period" and t.ptype == "N" and t.year == -1 for t in toks):
        toks = [t for t in toks if not (t.kind == "period" and t.ptype == "N")]
    return toks


def _is_prose(canon: str) -> bool:
    """Ligne de texte courant : un segment (entre deux blancs de 3 espaces) d'au moins 9 mots."""
    return any(len(re.findall(r"[a-z]{2,}", seg)) >= 9 for seg in re.split(r"\s{3,}", canon))


def _has_stray_numbers(canon: str, toks: list[_HTok]) -> bool:
    """La ligne porte-t-elle des nombres hors jetons de période (donc des données, pas un en-tête) ?"""
    buf = list(canon)
    for t in toks:
        if t.kind in ("period", "var"):
            buf[t.start : t.end] = " " * (t.end - t.start)
    rest = re.sub(r"\(\s?\d\s?\)|\b\d\s?(?:er|e|eme|ieme|nd)\b|\b(?:3|6|9|12)\s+mois\b|\bt[1-4]\b|\bs[12]\b", " ", "".join(buf))
    return bool(re.search(r"\d", rest))


#: Mots de période sans année (« 1er semestre » au-dessus de « 2026 », « Exercice » au-dessus de « 2025 »).
_KIND_WORD_RX: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"(?:1\s?er|premier)\s+semestre|(?<![a-z0-9])s1(?![a-z0-9])|(?<!\d)6\s+mois|six\s+mois"), "S1"),
    (re.compile(r"(?:2\s?(?:e|eme|nd)|second|deuxieme)\s+semestre|(?<![a-z0-9])s2(?![a-z0-9])"), "S2"),
    (re.compile(r"(?:1\s?er|premier)\s+trim(?:estre)?\b\.?|(?<![a-z0-9])t1(?![a-z0-9])|(?<!\d)3\s+mois|trois\s+mois"), "Q1"),
    (re.compile(r"(?:2\s?(?:e|eme|nd)|deuxieme)\s+trim(?:estre)?\b\.?|(?<![a-z0-9])t2(?![a-z0-9])"), "Q2"),
    (re.compile(r"(?:3\s?(?:e|eme|ieme)|troisieme)\s+trim(?:estre)?\b\.?|(?<![a-z0-9])t3(?![a-z0-9])|(?<!\d)9\s+mois|neuf\s+mois"), "Q3"),
    (re.compile(r"(?:4\s?(?:e|eme|ieme)|quatrieme)\s+trim(?:estre)?\b\.?|(?<![a-z0-9])t4(?![a-z0-9])"), "Q4"),
    (re.compile(r"(?<![a-z])(?:exercice|annee|annuel|decembre)(?![a-z])|(?<!\d)12\s+mois|douze\s+mois"), "A"),
    (re.compile(r"(?<![a-z])juin(?![a-z])"), "S1"),
    (re.compile(r"(?<![a-z])sept(?:embre)?(?![a-z])"), "Q3"),
    (re.compile(r"(?<![a-z])mars(?![a-z])"), "Q1"),
)
_VAR_WORD_RX = re.compile(r"(?<![a-z])(?:variations?|var\b\.?|evolutions?|evol\b\.?|ecarts?)(?![a-z])")


def _segments(canon: str) -> list[tuple[int, int]]:
    """Cellules d'une ligne : portions de texte séparées par au moins trois espaces."""
    return [(m.start(), m.end()) for m in re.finditer(r"\S(?:.*?\S)?(?=\s{3,}|$)", canon)]


def _header_zone(canon: list[str], row: int, max_up: int = 45, max_lines: int = 7) -> list[_HTok]:
    """Jetons des lignes d'en-tête au-dessus de la ligne ``row`` (les plus proches d'abord).

    On remonte à travers les autres lignes de données et les lignes vides ; les premières
    lignes sans nombre parasite qui portent une période, une colonne de variation ou un budget
    forment l'en-tête ; on s'arrête au texte courant ou aux données d'un tableau précédent.

    Deux corrections tiennent à la mise en page réelle des rapports :

    - une période citée **dans une colonne de variation** (« Variation 30-06-2026 vs » puis
      « 30-06-2025 » dessous, « Variation en valeur (Juin 2026 - Juin 2025) ») n'est pas une
      colonne de montants : elle devient un jeton de variation ;
    - une année seule prend la nature écrite au-dessus ou au-dessous d'elle, dans la même
      colonne (« 1er semestre » / « 2026 », « Exercice » / « 2025 », « décembre » / « 2025 »).
    """
    out: list[_HTok] = []
    zone: list[int] = []
    pending: list[int] = []
    n_hdr = 0
    blanks = 0
    for i in range(row - 1, max(-1, row - 1 - max_up), -1):
        line = canon[i]
        if not line.strip():
            blanks += 1
            if n_hdr and blanks >= 2:
                break
            continue
        toks = _header_tokens(line, i)
        stray = _has_stray_numbers(line, toks)
        if stray or _is_prose(line):
            if n_hdr:
                break
            if _is_prose(line) and not stray:
                break  # paragraphe avant le tableau : pas d'en-tête lisible
            blanks = 0
            pending = []
            continue  # autre ligne de données du même tableau
        blanks = 0
        if toks:
            out.extend(toks)
            zone.extend(pending + [i])
            pending = []
            n_hdr += 1
            if n_hdr >= max_lines:
                break
        else:
            pending.append(i)  # ligne de mots (« Indicateurs », « 1er semestre   1er semestre »)
    if not out:
        return out
    top = min(zone)
    zone = sorted(set(zone) | {k for k in pending if k > top} | {k for k in range(top - 2, top) if k >= 0 and canon[k].strip()
                                                                 and not _is_prose(canon[k]) and not _tabular(canon[k])})
    # 1) Périodes citées dans une colonne de variation.
    var_segs: list[tuple[int, int, int]] = []  # (ligne, début, fin)
    for k in zone:
        for s, e in _segments(canon[k]):
            if e - s <= 45 and _VAR_WORD_RX.search(canon[k], s, e):
                var_segs.append((k, s, e))
    for t in out:
        if t.kind != "period":
            continue
        for k, s, e in var_segs:
            same_cell = k == t.line and s <= t.start < e
            below = k < t.line and s <= (t.start + t.end) / 2 <= e
            if same_cell or below:
                t.kind, t.ptype, t.year = "var", None, None
                break
    # 2) Année seule : nature lue dans la même colonne, sur une ligne voisine de l'en-tête.
    taken = {(t.line, x) for t in out if t.kind == "period" and t.ptype != "Y" for x in range(t.start, t.end)}
    words: list[tuple[int, int, int, str]] = []
    for k in zone:
        for rx, kind in _KIND_WORD_RX:
            for m in rx.finditer(canon[k]):
                if not any((k, x) in taken for x in range(m.start(), m.end())):
                    words.append((k, m.start(), m.end(), kind))
    for t in out:
        if t.kind != "period" or t.ptype != "Y":
            continue
        best = None
        for k, s, e, kind in words:
            if k == t.line or abs(k - t.line) > 3:
                continue
            overlap = min(t.end + 4, e) - max(t.start - 4, s)
            if overlap <= 0:
                continue
            key = (abs(k - t.line), -overlap)
            if best is None or key < best[0]:
                best = (key, kind)
        if best is not None:
            t.ptype = best[1]
    return out


def _orig_span(lines: list[str], canon: list[str], t: _HTok) -> str:
    """Texte d'origine d'un jeton d'en-tête (casse et accents du document)."""
    raw = lines[t.line]
    if len(raw.rstrip()) == len(canon[t.line]):
        return raw[t.start : t.end].strip()
    return t.text.strip()


def _span_gap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, max(a0, b0) - min(a1, b1))


def _assign(cells: list[_Cell], toks: list[_HTok], row: int, max_gap: int = 6) -> dict[int, _HTok]:
    """Associe chaque cellule au jeton d'en-tête placé au-dessus d'elle (au plus un jeton par
    cellule et une cellule par jeton), du plus proche au plus lointain."""
    pairs = []
    for ci, c in enumerate(cells):
        for ti, t in enumerate(toks):
            gap = _span_gap(c.start, c.end, t.start, t.end)
            if gap <= max_gap:
                centre = abs((c.start + c.end) / 2 - (t.start + t.end) / 2)
                pairs.append((gap, row - t.line, centre, ci, ti))
    out: dict[int, _HTok] = {}
    used: set[int] = set()
    for _gap, _dl, _centre, ci, ti in sorted(pairs):
        if ci in out or ti in used:
            continue
        out[ci] = toks[ti]
        used.add(ti)
    return out


def _find_unit(canon: list[str], row: int, label: str) -> tuple[float | None, str | None, int | None, bool]:
    """Unité du tableau : ``(multiplicateur, monnaie, ligne de la déclaration, déclaration proche)``.

    Recherche dans le libellé de la ligne, puis en remontant (60 lignes, même page), puis
    juste sous le tableau ; à défaut, l'unité du document si toutes ses déclarations concordent.
    Une mention précédée d'un nombre (« 230 milliards FCFA ») est un montant, pas une déclaration.
    """

    def decl(line: str) -> tuple[float, str] | None:
        for m in _UNIT_RX.finditer(line):
            if re.search(r"\d\s*$", line[max(0, m.start() - 4) : m.start()]):
                continue
            if m.group("c3"):
                return 1.0, "FCFA"
            u = m.group("u") or m.group("u2")
            cur = (m.group("c") or m.group("c2") or "").replace(" ", "")
            mult = 1e3 if u.startswith("millier") or u == "k" else (1e6 if u.startswith("mio") else _MULT.get(u, None))
            if mult is None:
                continue
            if cur.startswith(("usd", "dollar", "$")):
                return mult, "USD"
            if cur.startswith("eur"):
                return mult, "EUR"
            if cur in ("francs", "franc"):
                continue  # « millions de francs » sans CFA : trop vague
            return mult, "FCFA"
        return None

    # Déclarations proches : libellé de la ligne, lignes du tableau et de son en-tête au-dessus
    # (30 lignes, hors paragraphes), ligne de pied juste dessous (12 lignes).
    near: list[tuple[float, str, int]] = []
    got = decl(label)
    if got:
        near.append((got[0], got[1], row))
    for i in range(row - 1, max(-1, row - 31), -1):
        got = None if _is_prose(canon[i]) else decl(canon[i])
        if got:
            near.append((got[0], got[1], i))
            break
    for i in range(row + 1, min(len(canon), row + 13)):
        got = None if _is_prose(canon[i]) else decl(canon[i])
        if got:
            near.append((got[0], got[1], i))
            break
    # En-tête sur plusieurs lignes (« S1 2026 (Milliards » puis « FCFA) ») : un seul mot d'unité et une
    # mention du franc CFA dans les lignes d'en-tête juste au-dessus du tableau.
    zone = " ".join(" ".join(canon[k].split()) for k in range(max(0, row - 12), row)
                    if canon[k].strip() and not _is_prose(canon[k]) and not _tabular(canon[k]))
    words = {m.group(1) for m in re.finditer(r"(?<![a-z0-9])(milliards?|millions?|milliers?)(?![a-z])", zone)
             if not re.search(r"\d\s*$", zone[max(0, m.start() - 4) : m.start()])}
    mults = {(1e3 if w.startswith("millier") else _MULT[w]) for w in words}
    if len(mults) == 1 and re.search(r"(?<![a-z])(?:f\s?\.?\s?cfa|fcfa|xof)(?![a-z])", zone):
        near.append((mults.pop(), "FCFA", -1))
    if near:
        if len({(m, c) for m, c, _ in near}) > 1:
            # « (En MXOF) » dans l'en-tête et « Montants en milliards de FCFA » sous le tableau : contradiction.
            return None, "conflit", None, True
        m, c, line = near[0]
        return m, c, (line if line >= 0 else None), True
    for i in range(row - 1, max(-1, row - 61), -1):
        got = decl(canon[i])
        if got:
            return got[0], got[1], i, False
    found = {d for d in (decl(line) for line in canon) if d}
    if len(found) == 1:
        mult, cur = next(iter(found))
        return mult, cur, None, False
    return None, None, None, False


def _levels_growth(cur: float, prev: float) -> float | None:
    return (cur - prev) / abs(prev) if prev else None


_PERIM_CONSO_RX = re.compile(r"consolid|part\s+(?:du\s+)?groupe|(?<![a-z])groupe(?![a-z])")
_PERIM_SOCIAL_RX = re.compile(r"(?<![a-z])(?:sociaux|social|individuels?|societe\s+mere)(?![a-z])")


def _perimeter(canon: list[str], f: dict[str, Any]) -> str | None:
    """Périmètre d'une ligne d'agrégat : ``"consolidé"``, ``"social"`` ou ``None`` (non précisé).

    D'abord le libellé de la ligne ; sinon le premier titre « comptes sociaux » / « comptes
    consolidés » rencontré en remontant de l'en-tête du tableau (12 lignes au plus).
    """
    label = _canon_line(str(f.get("label") or ""))
    if re.search(r"consolid|part\s+(?:du\s+)?groupe", label):
        return "consolidé"
    if _PERIM_SOCIAL_RX.search(label):
        return "social"
    top = min(f.get("ctx") or [f["line"]])
    for k in range(top, max(-1, top - 13), -1):
        line = canon[k]
        if _is_prose(line) or _tabular(line):
            if k < top:
                break
            continue
        if re.search(r"comptes?\s+consolid|etats?\s+financiers\s+consolid|donnees\s+consolid|chiffres\s+consolid|"
                     r"resultats?\s+consolid", line):
            return "consolidé"
        if re.search(r"comptes?\s+(?:sociaux|social|individuels?)|etats?\s+financiers\s+(?:sociaux|individuels?)|"
                     r"donnees\s+sociales", line):
            return "social"
    return None


def _cells_consistent(written: float, cur: _Cell, prev: _Cell) -> bool:
    """La variation écrite concorde-t-elle avec les deux montants, à 1 point près ?

    Les montants d'un tableau sont arrondis à leur pas d'affichage (le million, la décimale) :
    la variation recalculée n'est connue qu'à cet arrondi près. Elle concorde si la variation
    écrite est à moins d'un point de l'intervalle des variations possibles (« 105 » et
    « −770 » en millions donnent entre −829 % et −837 % : « −835 % » concorde).
    """
    vals = []
    for c in (cur.value - cur.prec / 2, cur.value + cur.prec / 2):
        for q in (prev.value - prev.prec / 2, prev.value + prev.prec / 2):
            if q:
                vals.append((c - q) / abs(q))
    if not vals or (prev.value - prev.prec / 2) * (prev.value + prev.prec / 2) <= 0:
        return False
    return min(vals) - CONSISTENCY_TOL - _EPS <= written <= max(vals) + CONSISTENCY_TOL + _EPS


def _read_row(lines: list[str], canon: list[str], i: int, ind: str, label_end: int, cells: list[_Cell],
              expected: tuple[str | None, int | None]) -> dict[str, Any]:
    """Lit une ligne d'agrégat (:func:`_read_row_once`), y compris quand le signe « - » d'un montant
    négatif est détaché du nombre (« 1 857 862 -        139 568 719 » : le second montant est négatif).

    Un « - » isolé peut aussi marquer une cellule vide : la lecture « signe détaché » n'est retenue que
    si elle seule tient, ou si elle seule est recoupée par la variation écrite ; sinon, aucun chiffre.
    """
    first = _read_row_once(lines, canon, i, ind, label_end, cells, expected)
    if not any(c.lone_dash and c.kind == "amt" for c in cells):
        return first
    flipped = [_dc_replace(c, value=-c.value) if c.lone_dash and c.kind == "amt" else c for c in cells]
    second = _read_row_once(lines, canon, i, ind, label_end, flipped, expected)
    ok1, ok2 = not first.get("reject"), not second.get("reject")
    if ok2 and (not ok1 or (second.get("verified") and not first.get("verified"))):
        second["sign_note"] = "signe « - » détaché du nombre"
        return second
    if ok1 and ok2 and not first.get("verified"):
        first["reject"] = "signe « - » ambigu (signe détaché du nombre ou cellule vide)"
    return first


def _read_row_once(lines: list[str], canon: list[str], i: int, ind: str, label_end: int, cells: list[_Cell],
                   expected: tuple[str | None, int | None]) -> dict[str, Any]:
    """Lit une ligne d'agrégat : les deux périodes comparables, la variation, l'unité.

    Renvoie un chiffre (``value``, ``prev``, ``growth``…) ou un rejet (``reject`` = motif),
    toujours avec ``source`` = la ligne exacte du document. ``verified`` : la paire de montants
    est recoupée par une variation écrite (en % ou en valeur).
    """
    source = _squeeze(lines[i])  # texte exact de la ligne ; les colonnes restent séparées par deux espaces
    out: dict[str, Any] = {"ind": ind, "origin": "table", "source": source, "line": i,
                           "label": " ".join(lines[i][:label_end].split()), "value": None, "prev": None,
                           "growth": None}
    amts = [k for k, c in enumerate(cells) if c.kind == "amt"]
    pcts = [k for k, c in enumerate(cells) if c.kind == "pct"]
    toks = _header_zone(canon, i)
    out["ctx"] = sorted({t.line for t in toks})
    budget = any(t.kind == "budget" for t in toks)
    periods = [t for t in toks if t.kind == "period"]
    amap = _assign([cells[k] for k in amts], periods, i)
    amap = {amts[k]: t for k, t in amap.items()}
    others = [t for t in toks if t.kind in ("var", "ratio", "budget")]
    rest_cells = [k for k in range(len(cells)) if k not in amap and cells[k].kind in ("amt", "pct")]
    omap = _assign([cells[k] for k in rest_cells], others, i)
    omap = {rest_cells[k]: t for k, t in omap.items()}
    # Pourcentages placés sous une colonne de ratio (« % du CA », « marge ») : pas des variations.
    var_pcts = [k for k in pcts if not (k in omap and omap[k].kind in ("ratio", "budget"))]

    exp_kind, exp_year = expected
    cands: list[tuple[int, int]] = []
    for a in amap:
        for b in amap:
            ta, tb = amap[a], amap[b]
            if a == b or ta.ptype != tb.ptype or ta.year is None or tb.year is None or ta.year != tb.year + 1:
                continue
            cands.append((a, b))
    chosen: tuple[int, int] | None = None
    written: float | None = None
    if cands:
        # Période du tableau cohérente avec la note (type et année de la colonne N).
        ok = []
        for a, b in cands:
            t = amap[a]
            kind_ok = exp_kind is None or t.ptype in (exp_kind, "Y", "N") or (exp_kind == "S1" and t.ptype == "Q2")
            year_ok = exp_year is None or t.ptype == "N" or t.year == exp_year
            if kind_ok and year_ok:
                ok.append((a, b))
        if not ok:
            t = amap[cands[0][0]]
            out["reject"] = (f"période du tableau ({t.text.strip()}) différente de celle de la note "
                             f"({_KIND_LABEL.get(exp_kind or '', exp_kind or '?')} {exp_year or ''})").replace("  ", " ")
            return out
        cands = ok
        if var_pcts:
            hits = []
            for a, b in cands:
                for p in var_pcts:
                    if _cells_consistent(cells[p].value, cells[a], cells[b]):
                        hits.append((a, b, p))
            pairs = {(a, b) for a, b, _ in hits}
            if len(pairs) == 1:
                a, b, p = hits[0]
                chosen, written = (a, b), cells[p].value
            elif not pairs:
                a, b = cands[0]
                if len(cands) == 1 and cells[b].value > 0:
                    out["reject"] = INCONSISTENT
                    out["growth_rejected"] = cells[var_pcts[0]].value
                    out["growth_levels"] = _levels_growth(cells[a].value, cells[b].value)
                    return out
                if len(cands) == 1:
                    chosen = (a, b)  # base négative ou nulle : la variation écrite n'est pas vérifiable
                else:
                    out["reject"] = "plusieurs colonnes comparables, aucune ne concorde avec la variation écrite"
                    return out
            else:
                out["reject"] = "plusieurs paires de colonnes concordent avec une variation écrite"
                return out
        elif len(cands) == 1:
            chosen = cands[0]
        else:
            out["reject"] = "plusieurs paires de colonnes comparables (trimestre et cumul ?) sans variation écrite"
            return out
        # Les colonnes doivent être alignées avec l'en-tête : tout montant placé à gauche d'une des deux
        # colonnes retenues a lui aussi son jeton, et l'ordre des jetons suit l'ordre des cellules.
        left = [k for k in amts if k < max(chosen)]
        mapped = sorted((cells[k].start, amap[k].start) for k in amap)
        if any(k not in amap and k not in omap for k in left) or any(
                t2 < t1 for (_, t1), (_, t2) in zip(mapped, mapped[1:]) ):
            out["reject"] = "colonnes du tableau mal alignées avec l'en-tête : périodes non identifiées"
            return out
        out["periods"] = [_orig_span(lines, canon, amap[k]) for k in chosen]
    else:
        # En-tête illisible : la ligne doit s'expliquer entièrement (deux montants, leur écart
        # éventuel, une variation écrite qui concorde dans un seul sens).
        if budget:
            out["reject"] = "tableau avec une colonne de budget ou de prévision, colonnes non identifiées"
            return out
        if len(var_pcts) != 1 or len(amts) not in (2, 3):
            out["reject"] = "en-tête du tableau illisible : colonnes N et N−1 non identifiées"
            return out
        p = var_pcts[0]
        hits = []
        for a in amts:
            for b in amts:
                if a == b:
                    continue
                if cells[b].value <= 0 or not _cells_consistent(cells[p].value, cells[a], cells[b]):
                    continue
                third = [k for k in amts if k not in (a, b)]
                if third and abs(abs(cells[third[0]].value) - abs(cells[a].value - cells[b].value)) > max(
                        1.0, 0.005 * abs(cells[a].value - cells[b].value)):
                    continue
                hits.append((a, b))
        if len(hits) != 1:
            out["reject"] = "en-tête du tableau illisible : colonnes N et N−1 non identifiées"
            return out
        chosen, written = hits[0], cells[p].value
        out["periods"] = None
        out["header"] = False
    a, b = chosen
    cur, prev = cells[a].value, cells[b].value
    g_lv = _levels_growth(cur, prev)
    out["verified"] = written is not None
    # Colonne « variation en valeur » : elle doit valoir N − (N−1).
    for k in amts:
        if k in (a, b) or not (k in omap and omap[k].kind == "var"):
            continue
        if abs(abs(cells[k].value) - abs(cur - prev)) > max(1.0, 0.005 * abs(cur - prev)):
            out["reject"] = "variation en valeur incohérente avec les deux montants"
            return out
        out["verified"] = True
    mult, currency, unit_line, near = _find_unit(canon, i, canon[i][:label_end])
    fcfa_only = max(abs(cur), abs(prev)) >= _FCFA_ONLY_ABOVE[ind]
    if mult is not None and currency == "FCFA" and not near and fcfa_only and mult != 1.0:
        # Déclaration lointaine (« en millions de FCFA » dans un commentaire) contredite par l'ordre de
        # grandeur des montants du tableau, qui ne peuvent être qu'en FCFA.
        mult, currency, unit_line = None, None, None
    if unit_line is not None and unit_line != i and near:
        out["ctx"] = sorted(set(out["ctx"]) | {unit_line})
    cell_mults = {cells[k].mult for k in (a, b)}
    if cell_mults != {None}:
        if len(cell_mults) != 1:
            out["reject"] = "les deux montants ne sont pas dans la même unité"
            return out
        mult, currency = cell_mults.pop(), "FCFA"
    out["raw"] = [cur, prev]
    if mult is not None and currency == "FCFA":
        v, pv = cur * mult, prev * mult
        if all(_VALUE_BOUNDS[0] <= abs(x) <= _VALUE_BOUNDS[1] for x in (v, pv) if x):
            out["value"], out["prev"] = v, pv
            out["unit"] = _UNIT_NAME.get(mult, f"×{mult:g} FCFA")
        else:
            out["unit_note"] = "unité douteuse (montant hors des bornes de vraisemblance) : montants non convertis"
    elif mult is not None:
        out["unit_note"] = f"montants en {currency}, non convertis"
    elif currency == "conflit":
        out["unit_note"] = "unités contradictoires près du tableau : montants non convertis"
    else:
        # Unité non écrite : elle n'est déduite que si le montant ne peut être qu'en FCFA
        # (« 42 256 666 676 » en milliers dépasserait tout chiffre d'affaires de la cote) ;
        # « 16 438 » ou « 258 691 309 » restent indéterminés (montants non convertis).
        if fcfa_only and currency != "conflit":
            out["value"], out["prev"] = cur, prev
            out["unit"] = "FCFA (unité déduite de l'ordre de grandeur)"
            mult = 1.0
        else:
            out.setdefault("unit_note", "unité du tableau non lue : montants non convertis")
    out["mult"] = mult if (mult is not None and out.get("value") is not None) else None
    if prev <= 0:
        out["note"] = NOT_COMPARABLE
        out["growth_rejected"] = written if written is not None else g_lv
    elif written is not None:
        out.update(growth=written, growth_from="pct", growth_levels=g_lv, consistent=True)
    else:
        out.update(growth=g_lv, growth_from="levels")
    if out.get("growth") is not None and abs(out["growth"]) > MAX_ABS_GROWTH + _EPS:
        out["note"] = NOT_COMPARABLE
        out["growth_rejected"] = out["growth"]
        out["growth"] = None
    return out


def period_mentions(text: str) -> set[str]:
    """Périodes comptables citées dans un texte : ``{"2026Q3", "2025A", …}`` (dates de clôture,
    « 3e trimestre 2026 », « 1er semestre 2026 », « exercice 2025 »…)."""
    out: set[str] = set()
    for i, line in enumerate((text or "").splitlines()):
        if not re.search(r"\d", line):
            continue
        for t in _header_tokens(_canon_line(line), i):
            if t.kind == "period" and t.year and t.year > 0 and t.ptype in ("Q1", "Q2", "S1", "Q3", "Q4", "S2", "A"):
                out.add(f"{t.year}{t.ptype}")
    return out


def expected_period(title: str = "", event_type: str | None = None) -> tuple[str | None, int | None]:
    """Période attendue d'une publication : ``(type, année)`` d'après son type et son titre.

    ``("Q3", 2026)`` pour « Rapport d'activités - 3e trimestre 2026 » ; ``(None, None)`` si le
    type de la note n'est pas une publication périodique (communiqué, notation…).
    """
    kind = _EXPECTED_KIND.get(str(event_type or "").upper())
    year = None
    fp = fiscal_period("", title or "")
    if fp:
        t_kind, t_year = fp[4:], int(fp[:4])
        if kind is None or kind == t_kind:
            kind, year = t_kind, t_year
    elif kind in (None, "S1"):
        # « Rapport d'activités - 2ème trimestre 2026 » : cumul au 30 juin, lu comme un 1er semestre.
        m = re.search(r"(?:2\s?(?:e|eme|ieme|nd)|deuxieme|second)\s+trimestre\s+(20\d\d)", fold(title or ""))
        if m:
            kind, year = "S1", int(m.group(1))
    return kind, year


def _period_cited(mentions: set[str], kind: str, year: int | None) -> bool:
    """La période attendue est-elle citée ? (un « 2e trimestre » vaut un 1er semestre : cumul au 30 juin)"""
    kinds = ("S1", "Q2") if kind == "S1" else (kind,)
    if year:
        return any(f"{year}{k}" in mentions for k in kinds)
    return any(m.endswith(k) for m in mentions for k in kinds)


def _tabular(canon: str) -> bool:
    """Ligne de données d'un tableau quelconque : un libellé puis au moins deux nombres, sans phrase."""
    m = re.match(r"^\s*\S.*?\s{2,}(?=[(+\-]?\s?\d)", canon)
    rest = canon[m.end():] if m else (canon if re.match(r"^\s*[(+\-]?\s?\d", canon) else None)
    if rest is None:
        return False
    cells = _row_cells(rest, 0)
    return bool(cells) and len(cells) >= 2


def _is_heading(body: str, next_line: str) -> bool:
    """Titre de rubrique : ligne courte, sans ponctuation finale ni pourcentage, suivie d'une ligne qui
    commence par une majuscule (ou vide), numérotée (« 2. », « II – ») ou tout en capitales ou très courte."""
    body = body.strip()
    if not body or len(body) > 70 or body[-1] in ".,;:!?" or "%" in body:
        return False
    nxt = next_line.strip()
    if nxt and not (nxt[0].isupper() or nxt[0] in "•●▪■-–"):
        return False
    n_words = len(re.findall(r"[^\W\d_]{2,}", body))
    if n_words == 0 or n_words > 9:
        return False
    numbered = bool(re.match(r"^(?:[IVX]{1,4}|\d{1,2}|[A-Z])\s?[.)\-–—]\s*\S", body))
    letters = [c for c in body if c.isalpha()]
    upper = bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.85
    return numbered or upper or n_words <= 5


_BULLET_RX = re.compile(r"^\s*(?:[•●▪■◦‣►➢✓]|[\-–—*o]\s)\s*")
_GUTTER_RX = re.compile(r"\s{4,}")


def _paragraphs(lines: list[str], skip: set[int]) -> list[tuple[int, str]]:
    """Paragraphes de texte courant d'un texte mis en page : ``[(première ligne, texte)]``.

    Les lignes de tableau (``skip``) sont exclues. Deux colonnes côte à côte (un blanc d'au
    moins 4 espaces entre deux portions de phrase) sont lues l'une après l'autre, et non
    ligne à ligne : sans cela, une phrase de la colonne de gauche se poursuivrait dans celle
    de droite.
    """
    out: list[tuple[int, str]] = []
    left: list[str] = []
    right: list[str] = []
    first = [0, 0]

    def flush() -> None:
        for k, buf in enumerate((left, right)):
            if buf:
                out.append((first[k], " ".join(" ".join(buf).split())))
        left.clear()
        right.clear()

    def words(s: str) -> int:
        return len(re.findall(r"[^\W\d_]{2,}", s))

    for i, raw in enumerate(lines):
        line = raw.replace("\f", " ").rstrip()
        if i in skip or not line.strip():
            flush()
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        parts = [p for p in _GUTTER_RX.split(body) if p.strip()]
        if len(parts) >= 3:
            # Chiffres clés « en cases » côte à côte (« 53,7 Mds     22,8 Mds     14,5 Mds ») : lus ligne à
            # ligne, un libellé recevrait la variation de la case voisine. Ce ne sont pas des phrases.
            flush()
            continue
        if not right and _is_heading(body, lines[i + 1] if i + 1 < len(lines) else ""):
            # Titre de rubrique (« 2. Volumes et chiffre d'affaires ») : paragraphe à part, sinon les
            # chiffres de la phrase suivante seraient attribués à l'agrégat nommé dans le titre.
            flush()
            out.append((i, " ".join(body.split())))
            continue
        if len(parts) == 2 and words(parts[0]) >= 2 and words(parts[1]) >= 2:
            if not left:
                first[0] = i
            if not right:
                first[1] = i
            left.append(parts[0])
            right.append(parts[1])
            continue
        if right and indent >= 40:
            right.append(body)
            continue
        if _BULLET_RX.match(line) and not right:
            flush()
        if not left:
            first[0] = i
        left.append(" ".join(parts) if len(parts) > 1 else body)
    flush()
    return out


def _merge_sentence_figures(res: dict[str, Any], figs: dict[str, Any], where: int) -> None:
    """Fusionne les chiffres d'un paragraphe : première mention exploitable de chaque indicateur."""
    for ind, info in figs.items():
        info = dict(info)
        info.setdefault("origin", "sentence")
        info["line"] = where
        if info.get("surface"):
            info["source"] = " ".join(str(info["surface"]).split())
        prev = res.get(ind)
        if ind == "div" and prev is not None:
            for k, v in info.items():
                if k not in ("surface", "source", "line") and prev.get(k) is None and v is not None:
                    prev[k] = v
            continue
        if prev is None or (prev.get("growth") is None and info.get("growth") is not None):
            res[ind] = info


def _read_layout(text: str, title: str = "", expected: tuple[str | None, int | None] = (None, None)) -> dict[str, Any]:
    """Lecture d'un texte mis en page : tableaux d'abord, puis phrases, avec les garde-fous.

    Renvoie ``figures`` (chiffres retenus par indicateur, chacun avec ``source``), ``rejected``
    (lignes ou phrases écartées, avec le motif), ``rows`` (lignes d'agrégat vues), ``context``
    (numéros des lignes d'en-tête et d'unité des tableaux retenus) et ``paragraphs``.
    """
    lines = (text or "").splitlines()
    canon = [_canon_line(line) for line in lines]
    rows: dict[int, tuple[str, int, list[_Cell]]] = {}
    label_of: dict[int, int] = {}  # ligne des nombres -> ligne du libellé (libellé seul sur sa ligne)
    for i, line in enumerate(canon):
        r = _table_row(line)
        if r:
            rows[i] = r
    # Libellé seul sur sa ligne, ses nombres sur la ligne voisine (cellule haute de deux lignes) : selon
    # le document, les nombres sont au-dessus ou au-dessous du libellé. Chaque libellé isolé (d'agrégat
    # ou non) prend la ligne de nombres voisine quand il n'y en a qu'une de libre ; s'il en reste
    # deux, l'appariement est ambigu et rien n'est lu.
    numbers: dict[int, list[_Cell]] = {}
    for i, line in enumerate(canon):
        if i not in rows and re.match(r"^\s*[(+\-]?\s?\d", line):
            cells = _row_cells(line, 0)
            if cells and sum(c.kind == "amt" for c in cells) >= 2:
                numbers[i] = cells
    options: dict[int, list[int]] = {}
    for i, line in enumerate(canon):
        body = line.strip()
        if not body or len(body) > 70 or re.search(r"\d", re.sub(r"\(\s?\d\s?\)", "", body)) or _is_prose(line):
            continue
        near_numbers = [j for j in (i - 1, i + 1) if j in numbers]
        if near_numbers and not _header_tokens(line, i):
            options[i] = near_numbers
    taken: dict[int, int] = {}  # ligne de nombres -> ligne du libellé
    progress = True
    while progress:
        progress = False
        for i, opts in list(options.items()):
            free = [j for j in opts if j not in taken]
            if len(free) == 1:
                taken[free[0]] = i
            if len(free) <= 1:
                del options[i]
                progress = True
    for j, i in taken.items():
        m = _ROW_RX.match(canon[i])
        if m and m.lastgroup and not canon[i][m.end():].strip():
            rows[j] = (m.lastgroup, 0, numbers[j])
            label_of[j] = i
    figures: dict[str, Any] = {}
    rejected: list[dict[str, Any]] = []
    context: dict[str, list[int]] = {}
    by_ind: dict[str, list[dict[str, Any]]] = {}
    header_lines: set[int] = set()
    for i, (ind, label_end, cells) in rows.items():
        f = _read_row(lines, canon, i, ind, label_end, cells, expected)
        header_lines.update(k for k in f.get("ctx") or [] if k not in rows)
        if i in label_of:
            f["label"] = " ".join(lines[label_of[i]].split())
            f["source"] = f["label"] + "  " + f["source"]  # libellé et nombres sont sur deux lignes voisines
            f["label_line"] = label_of[i]
        by_ind.setdefault(ind, []).append(f)
    # Unité d'un tableau : celle lue ou déduite pour une ligne vaut pour les autres lignes du même
    # tableau (même en-tête) quand elle est unique.
    by_table: dict[tuple[int, ...], set[float]] = {}
    for found in by_ind.values():
        for f in found:
            if f.get("mult") is not None and f.get("ctx"):
                by_table.setdefault(tuple(f["ctx"]), set()).add(f["mult"])
    for found in by_ind.values():
        for f in found:
            mults = by_table.get(tuple(f.get("ctx") or ()), set())
            if f.get("raw") and f.get("value") is None and len(mults) == 1 and "non convertis" in str(f.get("unit_note")) \
                    and "non lue" in str(f.get("unit_note")):
                m = next(iter(mults))
                f["value"], f["prev"] = f["raw"][0] * m, f["raw"][1] * m
                f["unit"] = _UNIT_NAME.get(m, f"×{m:g} FCFA") + " (unité des autres lignes du tableau)"
                f.pop("unit_note", None)
    # Périmètre de chaque ligne : libellé (« consolidé », « part du groupe », « social »), sinon le titre
    # placé au-dessus du tableau (« COMPTES SOCIAUX », « COMPTES CONSOLIDÉS »).
    for found in by_ind.values():
        for f in found:
            f["perimeter"] = _perimeter(canon, f)
    blocked: set[str] = set()
    for ind, found in by_ind.items():
        good = [f for f in found if not f.get("reject")]
        for f in found:
            if f.get("reject"):
                rejected.append({"ind": ind, "reason": f["reject"], "source": f["source"], "line": f["line"]})
        if not good:
            continue
        if ind == "rai" and any("avant impot" in _canon_line(f["label"]) for f in good):
            # « Résultat avant impôt » et « résultat des activités ordinaires » : le premier, s'il est donné.
            good = [f for f in good if "avant impot" in _canon_line(f["label"])]
        # Plusieurs lignes pour le même agrégat (social et consolidé, trimestre et cumul, deux unités) :
        # elles doivent dire la même chose ; sinon la ligne consolidée si elle est seule, sinon rien.
        groups: list[list[dict[str, Any]]] = []
        for f in good:
            g_f = _levels_growth(f["raw"][0], f["raw"][1])
            for grp in groups:
                g_0 = _levels_growth(grp[0]["raw"][0], grp[0]["raw"][1])
                same_sign = (f["raw"][0] >= 0) == (grp[0]["raw"][0] >= 0)
                if same_sign and ((g_f is None and g_0 is None) or (g_f is not None and g_0 is not None
                                                                     and abs(g_f - g_0) <= 0.012 + 0.01 * abs(g_0))):
                    grp.append(f)
                    break
            else:
                groups.append([f])
        pick: dict[str, Any] | None = None
        if len(groups) == 1:
            # même chiffre répété (tableau en milliards puis en millions) : la ligne convertie la plus précise
            pick = max(groups[0], key=lambda f: (f.get("value") is not None, abs(f["raw"][0])))
        else:
            conso = [grp for grp in groups if any(f.get("perimeter") == "consolidé" for f in grp)]
            if len(conso) == 1:
                pick = next(f for f in conso[0] if f.get("perimeter") == "consolidé")
            else:
                blocked.add(ind)
                for f in good:
                    rejected.append({"ind": ind, "reason": "plusieurs lignes concurrentes pour cet agrégat "
                                     "(périmètres ou périodes différents)", "source": f["source"], "line": f["line"]})
        if pick is not None:
            figures[ind] = pick
            context[ind] = list(pick.get("ctx") or [])
    # Un seul périmètre par document : si un chiffre consolidé est retenu, un chiffre « social » ne l'accompagne pas.
    if any(f.get("perimeter") == "consolidé" for f in figures.values()):
        for ind in [k for k, f in figures.items() if f.get("perimeter") == "social"]:
            f = figures.pop(ind)
            blocked.add(ind)
            rejected.append({"ind": ind, "reason": "chiffre des comptes sociaux alors que les autres chiffres retenus "
                             "sont consolidés", "source": f["source"], "line": f["line"]})
    for f in figures.values():
        if f.get("perimeter") is None:
            f.pop("perimeter", None)
    skip = {i for i, line in enumerate(canon) if i in rows or _tabular(line)} | set(label_of.values()) | header_lines
    paragraphs = _paragraphs(lines, skip)
    sent: dict[str, Any] = {}
    if title and title.strip():
        _merge_sentence_figures(sent, _sentence_figures("", title), -1)
    for where, par in paragraphs:
        if not re.search(r"\d", par):
            continue
        _merge_sentence_figures(sent, _sentence_figures(par, strict=True), where)
    # Unité d'un tableau confirmée par le commentaire : « 1 012 » au tableau et « 1 012 milliards FCFA »
    # dans la phrase qui le commente donnent l'unité (elle vaut alors pour les lignes du même tableau).
    confirmed: dict[tuple[int, ...], float] = {}
    for ind, f in figures.items():
        s = sent.get(ind)
        if f.get("origin") != "table" or f.get("value") is not None or not f.get("raw") or not s or "non convertis" not in str(
                f.get("unit_note")) or " en " in str(f.get("unit_note"))[:12]:
            continue
        cur_raw, s_val = f["raw"][0], s.get("value")
        if not cur_raw or not s_val or (cur_raw > 0) != (s_val > 0):
            continue
        fits = [m for m in (1.0, 1e3, 1e6, 1e9) if abs(s_val / (cur_raw * m) - 1.0) <= 0.006]
        if len(fits) == 1 and all(_VALUE_BOUNDS[0] <= abs(x * fits[0]) <= _VALUE_BOUNDS[1] for x in f["raw"] if x):
            confirmed[tuple(f.get("ctx") or (f["line"],))] = fits[0]
    for ind, f in figures.items():
        m = confirmed.get(tuple(f.get("ctx") or (f.get("line"),)))
        if m is not None and f.get("origin") == "table" and f.get("value") is None and f.get("raw"):
            f["value"], f["prev"] = f["raw"][0] * m, f["raw"][1] * m
            f["unit"] = _UNIT_NAME.get(m, f"×{m:g} FCFA") + " (unité confirmée par le commentaire)"
            f.pop("unit_note", None)
    for ind, f in sent.items():
        if ind != "div":
            if f.get("currency") == "USD":
                # Document à deux monnaies (ETI) : la variation écrite en dollars n'est pas celle des comptes
                # en FCFA ; elle est écartée, seul un tableau en FCFA peut porter le chiffre.
                rejected.append({"ind": ind, "reason": FOREIGN_CURRENCY, "source": f.get("source", ""), "line": f["line"]})
                continue
            _vet_figure(f)
            if f.get("reject"):
                rejected.append({"ind": ind, "reason": f["reject"], "source": f.get("source", ""), "line": f["line"]})
                continue
        if ind in blocked:
            continue  # tableaux concurrents pour cet agrégat : une phrase ne tranche pas
        if ind not in figures:
            figures[ind] = f
        elif ind != "div" and figures[ind].get("growth") is not None and f.get("growth") is not None \
                and not _consistent(figures[ind]["growth"], f["growth"]):
            figures[ind]["text_growth"] = f["growth"]  # le commentaire dit autre chose que le tableau
    return {"figures": figures, "rejected": rejected, "rows": sorted(rows), "context": context,
            "paragraphs": paragraphs, "lines": lines, "canon": canon}


def extract_figures(text: str, title: str = "") -> dict[str, Any]:
    """Extrait RN, PNB, CA, résultat avant impôt et dividende d'un texte, avec les garde-fous.

    - texte courant : comme :func:`_sentence_figures` (« 245,3 milliards FCFA contre 210,1
      milliards, soit +16,8 % ») ;
    - texte mis en page par ``pdftotext -layout`` contenant des **tableaux** : la ligne de
      l'agrégat est repérée (« Chiffre d'affaires », « Produit Net Bancaire », « Résultat
      net », « Résultat avant impôt »), ses colonnes sont rattachées à l'en-tête (périodes N
      et N−1 de même nature, variation en valeur et en %), l'unité du tableau est lue (FCFA,
      milliers, millions, milliards) ; les phrases sont lues colonne par colonne.

    Garde-fous (:func:`_vet_figure`, :func:`_read_row`) : une variation n'est retenue que si
    elle est écrite ou recalculée à partir de deux montants de même unité et de même
    périmètre ; la variation écrite doit concorder avec les montants à 1 point près, sinon le
    chiffre est écarté (``reject``) ; base négative ou nulle, ou variation au-delà de ±300 % :
    montants gardés mais ``growth = None`` et ``note = "base non comparable"`` ; en-tête ou
    colonnes ambigus : aucun chiffre. Chaque chiffre porte ``source`` (ligne ou phrase exacte).

    Renvoie ``{indicateur: {...}}`` pour ``rn``, ``pnb``, ``ca``, ``rai``, ``div`` (clés
    ``value``, ``prev``, ``growth`` en décimal, ``growth_from`` = ``pct`` | ``levels``,
    ``consistent``, ``surface`` / ``source``, ``origin`` = ``table`` | ``sentence``) ; pour le
    dividende : ``net``, ``gross``, ``prev``, ``growth``, ``total``. Montants en FCFA.
    """
    if not any(_table_row(_canon_line(line)) for line in (text or "").splitlines() if re.search(r"\d\s{2,}\S*\d", line)):
        res = _sentence_figures(text, title)
        for ind, f in res.items():
            if ind != "div":
                _vet_figure(f)
        return res
    return _read_layout(text, title)["figures"]


#: Longueur maximale de l'extrait d'un document conservé dans la note.
MAX_EXCERPT_CHARS = 1500
READER_VERSION = "notes-lecture/1"


def _squeeze(line: str) -> str:
    """Ligne d'un tableau, blancs réduits à deux espaces (les colonnes restent séparées)."""
    return re.sub(r"\s{2,}", "  ", line.strip())


def read_document(text: str, title: str = "", event_type: str | None = None,
                  max_chars: int = MAX_EXCERPT_CHARS, ocr_layer: bool = False) -> dict[str, Any]:
    """Lit le texte d'un document (``pdftotext -layout``) : chiffres contrôlés et extrait borné.

    - ``figures`` : agrégats retenus (voir :func:`extract_figures`), chacun avec ``source`` ;
    - ``rejected`` : lignes ou phrases vues mais écartées, avec le motif (ambiguïté,
      incohérence, période) — aucun score numérique n'en est tiré ;
    - ``period`` : période attendue (``"2026Q3"``) d'après le type et le titre de la note ;
      ``period_ok`` : ``True`` si le document la cite, ``False`` s'il cite d'autres périodes
      mais pas celle-là (alors **aucun chiffre n'est retenu**), ``None`` si rien n'est datable ;
    - ``excerpt`` : extrait de ``max_chars`` caractères au plus — en-tête du document, lignes
      de tableau et phrases qui portent les chiffres, phrases à fort contenu, puis début du
      texte ; ``has_figures`` : au moins un agrégat ou un dividende retenu ;
    - ``ocr_layer=True`` (texte issu de l'OCR d'un scanner, ``research.pdf_text_layer_is_ocr``) :
      un chiffre n'est retenu que s'il est **recoupé** (variation écrite, en % ou en valeur,
      qui concorde avec les deux montants) — un chiffre mal reconnu ne se recoupe pas.
    """
    text = text or ""
    exp_kind, exp_year = expected_period(title, event_type)
    doc = _read_layout(text, title, (exp_kind, exp_year))
    figures, rejected = doc["figures"], doc["rejected"]
    lines, paragraphs = doc["lines"], doc["paragraphs"]
    mentions = period_mentions(text)
    period_ok: bool | None = None
    if exp_kind is not None and mentions:
        period_ok = _period_cited(mentions, exp_kind, exp_year)
    if period_ok is False:
        why = (f"période du document ({', '.join(sorted(mentions)[:4])}) différente de celle de la note "
               f"({exp_year or ''}{exp_kind})")
        for ind, f in list(figures.items()):
            if ind == "div":
                continue
            rejected.append({"ind": ind, "reason": why, "source": f.get("source", ""), "line": f.get("line", 0)})
            del figures[ind]
    elif period_ok is None and exp_kind is not None:
        # Période non datable dans le document : seuls les tableaux dont l'en-tête a été lu restent.
        for ind, f in list(figures.items()):
            if ind != "div" and not (f.get("origin") == "table" and f.get("periods")):
                rejected.append({"ind": ind, "reason": "période du document non lisible", "source": f.get("source", ""),
                                 "line": f.get("line", 0)})
                del figures[ind]
    if ocr_layer:
        for ind, f in list(figures.items()):
            if ind != "div" and f.get("consistent") is not True:
                rejected.append({"ind": ind, "reason": "texte issu de l'OCR d'un scanner : chiffre non recoupé par une "
                                 "variation écrite", "source": f.get("source", ""), "line": f.get("line", 0)})
                del figures[ind]
    # --- extrait ---------------------------------------------------------------------------
    blocks: list[tuple[int, float, str]] = []  # (priorité, position, texte)
    n_head = 0
    for where, par in paragraphs[:3]:
        if n_head and n_head + len(par) > 260:
            break
        blocks.append((0, where, par[:260]))
        n_head += len(par)
    par_of = {where: par for where, par in paragraphs}

    def sentence_block(f: dict[str, Any], prio: int) -> None:
        par = par_of.get(f.get("line"), "")
        src = f.get("source") or ""
        if not par:
            if src:
                blocks.append((prio, float(f.get("line", 0)), src))
            return
        if len(par) <= 420:
            blocks.append((prio, float(f["line"]), par))
            return
        pos = par.find(src[:30]) if src else -1
        a = max(par.rfind(". ", 0, max(pos, 0)) + 2, 0) if pos > 0 else 0
        b = par.find(". ", (pos if pos >= 0 else 0) + len(src))
        b = len(par) if b < 0 else b + 1
        blocks.append((prio, float(f["line"]), par[a:b][:600]))

    for ind in ("rn", "pnb", "ca", "rai", "div"):
        f = figures.get(ind)
        if not f:
            continue
        if f.get("origin") == "table":
            ctx = doc["context"].get(ind, [])
            if ctx:
                # toutes les lignes de l'en-tête, de sa première ligne à la ligne de l'agrégat
                top = min(ctx)
                last = f.get("label_line") if f.get("label_line") is not None else f["line"]
                extra = [k for k in range(top, min(last, top + 8)) if lines[k].strip()
                         and not _tabular(doc["canon"][k]) and not _is_prose(doc["canon"][k])]
                ctx = sorted(set(ctx) | set(extra))
            for i in ctx:
                blocks.append((1, i, _squeeze(lines[i])))
            if f.get("label_line") is not None:
                blocks.append((1, f["label_line"], _squeeze(lines[f["label_line"]])))
            blocks.append((1, f["line"], _squeeze(lines[f["line"]])))
        else:
            sentence_block(f, 1)
    for r in rejected[:6]:
        if r.get("source"):
            blocks.append((2, float(r.get("line", 0)) + 0.1, r["source"][:300]))
    for where, par in paragraphs:
        if len(par) < 25 or len(par) > 900:
            continue
        hits = [h for h in scan(par) if h.kind in ("pos", "neg") and (h.risk or abs(h.base_weight) >= 2)]
        if hits:
            blocks.append((3, where + 0.2, par[:500]))
    for where, par in paragraphs:
        if len(par) >= 40:
            blocks.append((4, where + 0.3, par[:700]))
    chosen: list[tuple[float, str]] = []
    seen: set[str] = set()
    used = 0
    for prio, pos, s in sorted(blocks, key=lambda b: (b[0], b[1])):
        key = " ".join(s.split())
        if not key or key in seen or any(key in k for k in seen):
            continue
        room = max_chars - used - (1 if chosen else 0)
        if room < 40:
            break
        if len(s) > room:
            if prio >= 3 and room >= 120:
                s = s[: room - 4].rstrip() + " […]"
            else:
                continue
        seen.add(key)
        chosen.append((pos, s))
        used += len(s) + (1 if len(chosen) > 1 else 0)
    excerpt = "\n".join(s for _, s in sorted(chosen, key=lambda c: c[0]))[:max_chars]
    has = any(
        (f.get("value") is not None or f.get("growth") is not None or f.get("raw")) if ind != "div"
        else (f.get("net") is not None or f.get("gross") is not None)
        for ind, f in figures.items()
    )
    period = f"{exp_year}{exp_kind}" if exp_kind and exp_year else None
    return {"figures": figures, "rejected": rejected, "period": period, "period_ok": period_ok,
            "periods_found": sorted(mentions), "excerpt": excerpt, "has_figures": bool(has),
            "n_rows": len(doc["rows"]), "reader": READER_VERSION, "ocr_layer": bool(ocr_layer)}


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}
_WEEKDAYS = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6}
_DATE_RX = re.compile(
    r"(?:(?P<wd>lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+)?"
    r"(?:(?P<d1>\d{1,2})\s?(?:er)?\s*[/.-]\s*(?P<m1>\d{1,2})\s*[/.-]\s*(?P<y1>\d{4})|"
    r"(?P<d2>\d{1,2})\s?(?:er)?\s+(?P<m2>janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+(?P<y2>\d{4}))"
)
_DATE_LABELS = {
    "ex_date": r"(?:date\s+)?ex[\s-]?dividendes?|date\s+de\s+detachement|detachement(?:\s+du\s+(?:dividende|coupon|droit))?",
    "pay_date": r"date\s+de\s+(?:mise\s+en\s+)?paiement|mise\s+en\s+paiement|payes?\s+le|payables?\s+(?:a\s+partir\s+)?(?:du|le)|paiement\s+(?:le|a\s+partir\s+du)",
    "record_date": r"(?:date\s+de\s+)?fermeture\s+des\s+registres|date\s+d'enregistrement",
    "ag_date": (
        r"assemblee\s+generale(?:\s+(?:ordinaire|extraordinaire|mixte))?(?:\s+annuelle)?|\bago\b|\bage\b|\bagm\b|\bagm?o\b"
    ),
}


def _parse_date_match(m: re.Match) -> tuple[pd.Timestamp | None, str | None]:
    try:
        if m.group("d1"):
            d, mo, y = int(m.group("d1")), int(m.group("m1")), int(m.group("y1"))
        else:
            d, mo, y = int(m.group("d2")), _MONTHS[m.group("m2")], int(m.group("y2"))
        ts = pd.Timestamp(year=y, month=mo, day=d)
    except (ValueError, KeyError):
        return None, None
    warn = None
    wd = m.group("wd")
    if wd and _WEEKDAYS[wd] != ts.dayofweek:
        warn = f"jour de la semaine incohérent : « {wd} » pour le {ts:%d/%m/%Y} (coquille probable de l'avis)"
    return ts, warn


def extract_dates(text: str, title: str = "") -> tuple[dict[str, Any], list[str]]:
    """Dates d'un avis : ex-dividende, paiement, fermeture des registres, assemblée générale."""
    full = (title.strip() + "\n" if title and title.strip() else "") + (text or "")
    norm = fold(full)
    out: dict[str, Any] = {}
    warnings: list[str] = []
    for key, pat in _DATE_LABELS.items():
        for lm in re.finditer(r"(?<![a-z])(?:" + pat + r")(?![a-z])", norm):
            stop = min(len(norm), lm.end() + (140 if key == "ag_date" else 60))
            seg_end = _sentence_end(norm, lm.end()) if key != "ag_date" else stop
            dm = _DATE_RX.search(norm, lm.end(), max(min(stop, seg_end + 1), lm.end()))
            if not dm:
                continue
            ts, warn = _parse_date_match(dm)
            if ts is None:
                continue
            out[key] = ts
            if warn and warn not in warnings:
                warnings.append(warn)
            if key == "ag_date":
                kind = re.search(r"ordinaire|extraordinaire|mixte|\bago\b|\bage\b|\bagm\b", lm.group(0))
                if kind:
                    k = kind.group(0)
                    out["ag_type"] = {"ordinaire": "AGO", "ago": "AGO", "extraordinaire": "AGE", "age": "AGE",
                                      "mixte": "AGM", "agm": "AGM"}.get(k, k.upper())
            break
    ex = out.get("ex_date")
    if ex is not None and ex.dayofweek >= 5:
        warnings.append(f"date ex-dividende un week-end ({ex:%d/%m/%Y}) : à recouper avec le BOC (doc 07 §6.7)")
    pay = out.get("pay_date")
    if ex is not None and pay is not None and pay < ex:
        warnings.append("date de paiement antérieure à la date ex-dividende : saisie à vérifier")
    return out, warnings


_PERIOD_RX = (
    (re.compile(r"(?:1\s?er|premier)\s+trimestre\s+(20\d\d)|\bt1\s+(20\d\d)|31\s+mars\s+(20\d\d)"), "Q1"),
    (re.compile(r"(?:3\s?(?:e|eme|ieme)|troisieme)\s+trimestre\s+(20\d\d)|\bt3\s+(20\d\d)|(?:9|neuf)\s+mois\s+(20\d\d)|30\s+septembre\s+(20\d\d)"), "Q3"),
    (re.compile(r"(?:1\s?er|premier)\s+semestre\s+(20\d\d)|\bs1\s+(20\d\d)|30\s+juin\s+(20\d\d)"), "S1"),
    (re.compile(r"exercice\s+(?:clos\s+le\s+31\s+decembre\s+)?(20\d\d)|31\s+decembre\s+(20\d\d)|annee\s+(20\d\d)"), "A"),
)


def fiscal_period(text: str, title: str = "") -> str | None:
    """Période comptable : ``2025A``, ``2026Q1``, ``2026S1``, ``2026Q3`` (titre d'abord)."""
    for zone in (fold(title or ""), fold(text or "")[:1500]):
        for rx, suffix in _PERIOD_RX:
            m = rx.search(zone)
            if m:
                year = next(g for g in m.groups() if g)
                return f"{year}{suffix}"
    return None


# ---------------------------------------------------------------------------
# Formatage français
# ---------------------------------------------------------------------------


def fr_num(x: float, decimals: int = 1) -> str:
    """« 1 234,5 » (espace fine pour les milliers, virgule décimale)."""
    s = f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return s


def fr_signed(x: float, decimals: int = 2) -> str:
    """Nombre signé : « +0,34 », « −0,62 »."""
    s = fr_num(abs(x), decimals)
    return ("+" if x >= 0 else "−") + s


def fr_pct(x: float, decimals: int = 1) -> str:
    """Variation en % signée (``x`` en décimal) : « +16,8 % »."""
    return fr_signed(100.0 * x, decimals) + " %"


def fr_amount(v: float) -> str:
    """Montant en FCFA lisible : « 245,3 Md FCFA », « 12,5 M FCFA », « 92 FCFA »."""
    a = abs(v)
    sign = "−" if v < 0 else ""
    if a >= 1e9:
        return f"{sign}{fr_num(a / 1e9, 1)} Md FCFA"
    if a >= 1e6:
        return f"{sign}{fr_num(a / 1e6, 1)} M FCFA"
    return f"{sign}{fr_num(a, 2 if a != int(a) else 0)} FCFA"


def fr_date(ts: Any) -> str:
    """« 18/11/2026 »."""
    return pd.Timestamp(ts).strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Panels (lecture point-in-time)
# ---------------------------------------------------------------------------


def _panel_series(panels: dict | None, name: str, symbol: str, cutoff: pd.Timestamp | None) -> pd.Series | None:
    """Série d'un champ pour un titre, limitée aux dates ``<= cutoff`` (sans fuseau)."""
    if not panels:
        return None
    s = None
    wide = panels.get(name)
    if isinstance(wide, pd.DataFrame) and symbol in wide.columns:
        s = wide[symbol]
    elif isinstance(panels.get("equities"), pd.DataFrame):
        eq = panels["equities"]
        if name in eq.columns:
            if isinstance(eq.index, pd.MultiIndex) and "symbol" in eq.index.names:
                try:
                    s = eq.xs(symbol, level="symbol")[name]
                except KeyError:
                    s = None
            elif "symbol" in eq.columns and "date" in eq.columns:
                sub = eq[eq["symbol"] == symbol]
                s = sub.set_index("date")[name]
    if s is None:
        return None
    s = s.copy()
    s.index = pd.to_datetime(s.index)
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    s = s.sort_index()
    if cutoff is not None:
        s = s[s.index <= cutoff]
    return s.dropna()


def _panel_last_date(panels: dict | None, name: str, symbol: str, cutoff: pd.Timestamp | None) -> pd.Timestamp | None:
    s = _panel_series(panels, name, symbol, cutoff)
    if s is None or s.empty:
        return None
    v = pd.to_datetime(s.iloc[-1], errors="coerce")
    if pd.isna(v):
        return None
    v = pd.Timestamp(v)
    return v.tz_localize(None) if v.tzinfo is not None else v


def _panel_last(panels: dict | None, name: str, symbol: str, cutoff: pd.Timestamp | None) -> float | None:
    s = _panel_series(panels, name, symbol, cutoff)
    if s is None or s.empty:
        return None
    try:
        return float(s.iloc[-1])
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------

_PUBLISHER_KEYS = frozenset({"brvm", "labrvm", "bourseregionaledesvaleursmobilieres", "bourseregionale"})

_BOND_RX = re.compile(
    r"(?<![a-z0-9])(?:emprunts?(?:\s+obligataires?)?|obligat\w*|bonds?|tpci|tpbf|sukuk|fctc|titrisation|"
    r"etat\s+du\s+\w+\s+\d|diaspora\s+bonds?)(?![a-z0-9])|\.o\d+\b"
)


def _clip(x: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, x)))


def _primary_target(manual: list[str], links: EntityLinks) -> str | None:
    if manual:
        return manual[0]
    if not links.targets:
        return None

    def key(code: str) -> tuple[int, int, int, int]:
        kind = target_kind(code)
        first = min((i for i, m in enumerate(links.matches) if m.code == code), default=10**6)
        # Le titre désigne le sujet (« Élections au Togo : risque pour ETI et Oragroup » ->
        # PAYS:TG) ; à défaut, la cible la plus précise du texte.
        return (0 if links.in_title(code) else 1, TARGET_SPECIFICITY.get(kind, 9), -links.count(code), first)

    return sorted(links.targets, key=key)[0]


def analyze_text(text: str, title: str = "", **kwargs: Any) -> NoteAnalysis:
    """Analyse d'un texte isolé (raccourci de :func:`analyze_note`, sans horodatage)."""
    return _analyze(title=title or "", text=text or "", **kwargs)


def analyze_note(
    note: Note,
    panels: dict | None = None,
    asof: Any = None,
    history: pd.DataFrame | None = None,
    sessions: Any = None,
    structured: dict[str, Any] | None = None,
    document: dict[str, Any] | None = None,
) -> NoteAnalysis:
    """Analyse d'une note -> :class:`NoteAnalysis`.

    - ``panels`` : dictionnaire de panels larges (``close``, ``last_div_net``, ``value``…)
      ou ``{"equities": load_equities(...)}`` ; seules les données **antérieures** à la
      première séance négociable (et à ``asof``) sont lues ;
    - ``history`` : notes antérieures (``NoteStore.asof``) pour vérifier R10 (alerte sur
      résultats préalable dans les 120 jours) ;
    - ``sessions`` : calendrier pour compter les séances jusqu'au détachement ;
    - ``structured`` : champs structurés fournis par un collecteur (``div_net``,
      ``ex_date``, ``pay_date``, ``rn``, ``rn_prev``…) : confiance d'extraction 1,0. Un
      dictionnaire ``note.analysis["structured"]`` est utilisé de la même façon ;
    - ``document`` : lecture du document joint à la note (:func:`read_document`, complétée par
      ``marks`` = marques ``doc_*`` du fichier lu). Les agrégats (RN, PNB, CA, résultat avant
      impôt) viennent alors **du document entier**, contrôlés, et non du texte de la note (qui
      n'en est qu'un extrait). Une note déjà lue (``analysis["extracted"]["doc_sha256"]``) est
      ré-analysée avec les chiffres du document qu'elle porte (``doc_figures``) : une mise à
      jour d'étiquette ne perd pas la lecture.
    """
    if structured is None and isinstance(note.analysis, dict) and isinstance(note.analysis.get("structured"), dict):
        structured = note.analysis["structured"]
    if document is None and isinstance(note.analysis, dict):
        document = document_from_extracted(note.analysis.get("extracted"))
    return _analyze(
        title=note.title,
        text=note.text,
        manual_targets=list(note.targets),
        event_hint=note.event_type,
        stance=note.stance,
        conviction=note.conviction,
        author=note.author,
        source=note.source,
        tags=list(note.tags),
        published_at=note.published_at,
        published_precision=note.published_precision,
        first_session=note.first_tradable_session,
        known_at=note.known_at,
        panels=panels,
        asof=asof,
        history=history,
        sessions=sessions,
        structured=structured,
        note_id=note.note_id,
        unknown_targets=list(getattr(note, "targets_unknown", None) or []),
        document=document,
    )


#: Marques d'un document lu, conservées dans ``analysis["extracted"]`` (contrat de ``enrich_documents``).
DOC_MARK_KEYS = ("doc_sha256", "doc_pages", "doc_method", "doc_chars", "doc_status")
_FIGURE_KEYS = ("value", "prev", "growth", "growth_from", "growth_levels", "growth_rejected", "consistent", "source",
                "origin", "unit", "unit_note", "periods", "perimeter", "note", "raw", "label", "header",
                "text_growth", "sign_note", "net", "gross", "total", "assumed_net")


def _public_figure(f: dict[str, Any]) -> dict[str, Any]:
    """Champs d'un chiffre conservés dans la note (sérialisables, sans positions internes)."""
    out = {k: f[k] for k in _FIGURE_KEYS if f.get(k) is not None}
    if "source" not in out and f.get("surface"):
        out["source"] = " ".join(str(f["surface"]).split())
    return out


def document_from_extracted(extracted: Any) -> dict[str, Any] | None:
    """Reconstitue l'argument ``document`` de :func:`analyze_note` à partir des marques d'une note lue."""
    if not isinstance(extracted, dict) or not extracted.get("doc_status"):
        return None
    return {
        "figures": {k: dict(v) for k, v in (extracted.get("doc_figures") or {}).items() if isinstance(v, dict)},
        "rejected": [dict(r) for r in (extracted.get("doc_rejected") or []) if isinstance(r, dict)],
        "period": extracted.get("doc_period"),
        "period_ok": extracted.get("doc_period_ok"),
        "marks": {k: extracted[k] for k in DOC_MARK_KEYS if k in extracted},
        "reader": extracted.get("doc_reader"),
    }


def _analyze(
    title: str,
    text: str,
    manual_targets: list[str] | None = None,
    event_hint: str | None = None,
    stance: str | None = None,
    conviction: int | None = None,
    author: str = "auto",
    source: str = "manual",
    tags: list[str] | None = None,
    published_at: pd.Timestamp | None = None,
    published_precision: str | None = None,
    first_session: pd.Timestamp | None = None,
    known_at: pd.Timestamp | None = None,
    panels: dict | None = None,
    asof: Any = None,
    history: pd.DataFrame | None = None,
    sessions: Any = None,
    structured: dict[str, Any] | None = None,
    note_id: str | None = None,
    unknown_targets: list[str] | None = None,
    document: dict[str, Any] | None = None,
) -> NoteAnalysis:
    tags = [fold(t) for t in (tags or [])]
    warnings: list[str] = []
    text = text or ""
    if len(text) > MAX_ANALYZE_CHARS:
        warnings.append(f"texte de {len(text)} caractères : seuls les {MAX_ANALYZE_CHARS} premiers sont analysés")
        text = text[:MAX_ANALYZE_CHARS]
    manual = normalize_targets(manual_targets or [])
    if unknown_targets:
        warnings.append(
            "cible(s) saisie(s) non reconnue(s) : " + ", ".join(f"« {t} »" for t in unknown_targets)
            + (" ; l'avis n'est reporté sur aucune cible détectée dans le texte" if not manual else "")
            + " (corriger la saisie : symbole, indice, pays, secteur ou thème)"
        )

    # 1) Entités et cibles.
    links = link_entities(text, title)
    # La BRVM comme émettrice de l'avis (« La Bourse Régionale des Valeurs Mobilières
    # informe… ») n'est pas une cible quand une société est nommée — ni quand l'avis porte
    # sur un indice ou un État (« Avis 166-2025 (BRVM) : … titres de l'ETAT DU NIGER »).
    named = set(links.targets) | set(manual)
    if any(target_kind(t) in ("symbol", "index", "country") for t in named):
        publisher = [m for m in links.matches if m.code == "MARCHE" and alias_key(m.alias) in _PUBLISHER_KEYS]
        if publisher and all(alias_key(m.alias) in _PUBLISHER_KEYS for m in links.matches if m.code == "MARCHE"):
            links.matches = [m for m in links.matches if m.code != "MARCHE"]
            links.targets = [t for t in links.targets if t != "MARCHE"]
    # Document d'un émetteur collecté automatiquement (communiqué, rapport, avis) : les
    # pays, secteurs, thèmes et le marché cités dans le corps du texte (« six banques du
    # Groupe (Bénin, Burkina Faso…) », « filières cacao, café ») sont du contexte, pas des
    # cibles (essai réel du 22/11/2026). Ils restent dans components["context_entities"].
    issuer_doc = author == "auto" and (
        any(target_kind(t) == "symbol" for t in manual)
        or any(m.kind == "symbol" and m.field == "title" for m in links.matches)
    )
    context_entities: list[str] = []
    if issuer_doc:
        keep = []
        for m in links.matches:
            if m.field == "text" and m.kind in ("country", "sector", "theme", "market"):
                if m.code not in context_entities:
                    context_entities.append(m.code)
                continue
            keep.append(m)
        links.matches = keep
        links.targets = [t for t in links.targets if any(m.code == t for m in keep)]
        context_entities = [c for c in context_entities if c not in links.targets]
    detected = sorted(
        [t for t in links.targets if t not in manual],
        key=lambda c: (TARGET_SPECIFICITY.get(target_kind(c), 9), links.targets.index(c)),
    )
    targets = list(manual) + detected
    primary = _primary_target(manual, links)
    norm_title = fold(title)
    norm_all = fold((title or "") + "\n" + (text or ""))
    bond_context = bool(_BOND_RX.search(norm_title)) and not any(target_kind(t) == "symbol" for t in manual) and not any(
        target_kind(t) == "symbol" for t in links.targets
    )

    # 2) Type d'événement.
    if event_hint:
        event_type, ev_origin = normalize_event_type(event_hint) or "OTHER", "manual"
    else:
        event_type, ev_origin = detect_event_type(title, text, macro_text=not issuer_doc)
        if ev_origin == "weak" and author == "analyste":
            event_type, ev_origin = "OTHER", "none"  # « résultat » dans une note libre : pas une publication
        if event_type == "OTHER":
            if author == "analyste":
                event_type, ev_origin = "MANUAL", "default"
            elif "presse" in tags or "press" in tags:
                event_type, ev_origin = "PRESS", "default"

    # 3) Chiffres et dates.
    figs = extract_figures(text, title)
    if document is not None:
        # Document lu : les agrégats viennent du document entier (contrôlés par read_document),
        # jamais de l'extrait conservé dans la note ; le dividende, du document puis de l'extrait.
        doc_figs = {k: dict(v) for k, v in (document.get("figures") or {}).items() if isinstance(v, dict)}
        figs = {k: v for k, v in figs.items() if k == "div"}
        figs.update(doc_figs)
    # Note libre de l'analyste : un type d'émetteur lu seulement dans le texte (« le
    # fractionnement récent », « les états financiers seraient publiés avec retard ») est
    # du contexte, pas l'événement de la note. Seuls restent les types macro, et les
    # publications de résultats quand le texte en donne les chiffres (essai réel du 22/11/2026).
    event_candidate = None
    if author == "analyste" and ev_origin == "text" and event_type not in _MACRO_EVENT_TYPES:
        has_result_figures = any(figs.get(k) for k in ("rn", "pnb", "ca"))
        if not (event_type in _RESULT_EVENTS and has_result_figures):
            event_candidate = event_type
            event_type, ev_origin = "MANUAL", "default"
    dates, date_warnings = extract_dates(text, title)
    warnings.extend(date_warnings)
    period = (document or {}).get("period") or fiscal_period(text, title)
    method = "ocr" if "ocr" in tags else "regex"
    extract_conf = 0.3 if method == "ocr" else 0.6
    extracted: dict[str, Any] = {}
    for ind in ("rn", "pnb", "ca", "rai"):
        f = figs.get(ind)
        if not f:
            continue
        if f.get("reject"):
            # Chiffre vu mais écarté par un garde-fou : aucun montant, aucune variation.
            extracted[f"{ind}_note"] = f["reject"]
            if f.get("growth_rejected") is not None and f.get("growth_levels") is not None:
                warnings.append(
                    f"{ind.upper()} : variation annoncée {fr_pct(f['growth_rejected'])} et variation des niveaux "
                    f"{fr_pct(f['growth_levels'])} incohérentes : chiffre écarté"
                )
            else:
                warnings.append(f"{ind.upper()} : {f['reject']} : chiffre écarté")
            continue
        extracted[ind] = f.get("value")
        extracted[f"{ind}_prev"] = f.get("prev")
        extracted[f"{ind}_growth"] = f.get("growth")
        if f.get("note"):
            extracted[f"{ind}_note"] = f["note"]
            warnings.append(f"{ind.upper()} : {f['note']} (base négative ou nulle, ou variation au-delà de "
                            f"±{MAX_ABS_GROWTH * 100:.0f} %) : pas de score numérique")
        if document is not None or f.get("origin") == "table":
            src_line = f.get("source") or f.get("surface")
            if src_line:
                extracted[f"{ind}_source"] = re.sub(r"\s{2,}", "  ", str(src_line).strip())
                if ind == "rai" and re.search(r"activites\s+ordinaires", fold(str(src_line))):
                    # Libellé lu, non renommé : le résultat des activités ordinaires n'est pas le résultat
                    # avant impôt (il manque le résultat hors activités ordinaires).
                    extracted["rai_label"] = "résultat des activités ordinaires"
            if f.get("unit_note"):
                extracted[f"{ind}_unit_note"] = f["unit_note"]
    d = figs.get("div") or {}
    if d:
        extracted["div_net"] = d.get("net")
        extracted["div_gross"] = d.get("gross")
        extracted["div_prev"] = d.get("prev")
        extracted["div_growth"] = d.get("growth")
        if d.get("total") is not None:
            extracted["div_total"] = d.get("total")
        if d.get("assumed_net"):
            extracted["div_assumed_net"] = True
    extracted.update({k: v for k, v in dates.items()})
    if period:
        extracted["fiscal_period"] = period
    if structured:
        for k, v in structured.items():
            if v is None:
                continue
            if k in ("ex_date", "pay_date", "record_date", "ag_date"):
                v = to_day(v)
            extracted[k] = v
        method, extract_conf = "structured", 1.0
        if extracted.get("div_net") is not None and extracted.get("div_prev") and extracted.get("div_growth") is None:
            extracted["div_growth"] = (extracted["div_net"] - extracted["div_prev"]) / abs(extracted["div_prev"])
        if extracted.get("rn") is not None and extracted.get("rn_prev") and extracted.get("rn_growth") is None:
            extracted["rn_growth"] = (extracted["rn"] - extracted["rn_prev"]) / abs(extracted["rn_prev"])
    has_numbers = any(extracted.get(k) is not None for k in ("rn", "pnb", "ca", "rai", "div_net", "div_gross", "rn_growth",
                                                             "pnb_growth", "ca_growth", "rai_growth"))
    if document is not None:
        # Marques du document lu (contrat de research.enrich_documents) et chiffres contrôlés,
        # gardés pour toute ré-analyse de la note.
        extracted.update({k: v for k, v in (document.get("marks") or {}).items() if k in DOC_MARK_KEYS})
        extracted["doc_figures"] = {k: _public_figure(v) for k, v in figs.items() if isinstance(v, dict) and k != "div"}
        rejected = [{"ind": r.get("ind"), "reason": r.get("reason"), "source": str(r.get("source") or "")[:300]}
                    for r in (document.get("rejected") or [])][:8]
        if rejected:
            extracted["doc_rejected"] = rejected
        if document.get("period"):
            extracted["doc_period"] = document["period"]
        if document.get("period_ok") is not None:
            extracted["doc_period_ok"] = bool(document["period_ok"])
        perimeters = {v.get("perimeter") for k, v in figs.items() if isinstance(v, dict) and k != "div" and v.get("perimeter")}
        if len(perimeters) == 1:
            extracted["doc_perimeter"] = perimeters.pop()  # « consolidé » ou « social »
        extracted["doc_reader"] = document.get("reader") or READER_VERSION
    if has_numbers or dates:
        extracted["extract_method"] = method
        extracted["extract_conf"] = extract_conf
    if bond_context:
        extracted["bond_context"] = True

    # 3b) Panels : dividende précédent, rendement, liquidité (avant la séance négociable).
    sym = primary if primary and target_kind(primary) == "symbol" else None
    cutoff = None
    if first_session is not None:
        cutoff = pd.Timestamp(first_session) - pd.Timedelta(days=1)
    if asof is not None:
        a = to_day(asof)
        cutoff = a if cutoff is None else min(cutoff, a)
        a_utc = asof_utc(asof)
        if known_at is not None and a_utc is not None and a_utc < known_at:
            warnings.append("asof antérieur à la date où la note est connue : analyse à titre rétrospectif")
    if sym and panels:
        last_div = _panel_last(panels, "last_div_net", sym, cutoff)
        last_div_date = _panel_last_date(panels, "last_div_date", sym, cutoff)
        close = _panel_last(panels, "close", sym, cutoff)
        if close is None:
            close = _panel_last(panels, "close_adj", sym, cutoff)
        vals = _panel_series(panels, "value", sym, cutoff)
        if close:
            extracted["close_at_notice"] = close
        if vals is not None and len(vals):
            extracted["median_value_60d"] = float(vals.tail(60).median())
        if last_div and extracted.get("div_prev") is None and (extracted.get("div_net") is not None or event_type == "DIV_NOTICE"):
            # Dividende précédent = dernier dividende payé, s'il a été payé au moins 60 jours
            # avant la séance négociable (sinon c'est le même dividende, déjà enregistré).
            ref_day = pd.Timestamp(first_session) if first_session is not None else cutoff
            if last_div_date is not None and ref_day is not None:
                is_previous = last_div_date < ref_day - pd.Timedelta(days=60)
            else:
                is_previous = extracted.get("div_net") is None or abs(extracted["div_net"] - last_div) > 1e-9
            if is_previous:
                extracted["div_prev"] = last_div
                extracted["div_prev_source"] = "panel"
                if extracted.get("div_net") is not None and extracted.get("div_growth") is None:
                    extracted["div_growth"] = (extracted["div_net"] - last_div) / abs(last_div)
        div_now = extracted.get("div_net")
        if div_now and close:
            extracted["yield_at_notice"] = div_now / close
    if extracted.get("ex_date") is not None and first_session is not None:
        cal = _calendar(sessions)
        ex = pd.Timestamp(extracted["ex_date"])
        if ex > pd.Timestamp(first_session):
            extracted["sessions_to_ex"] = cal.sessions_between(first_session, ex)
        else:
            extracted["sessions_to_ex"] = 0
            if ex < pd.Timestamp(first_session):
                warnings.append("date ex-dividende antérieure à la première séance négociable : fenêtre S1 fermée")
        if extracted["sessions_to_ex"] > 30:
            warnings.append(
                f"{extracted['sessions_to_ex']} séances entre l'avis et le détachement (> 30) : date d'avis "
                "probablement fausse (cas LNBB 2026, doc 07 §1.2)"
            )

    # 4) Lexique.
    hits = scan(text, title)
    if bond_context:
        for h in hits:
            if h.label in ("suspension de la cotation", "réduction de capital, radiation") or h.risk in ("R1", "R6"):
                h.weight = 0.0
                h.modifiers.append("ligne obligataire : sans portée pour les actions")

    if document is not None and event_type in _RESULT_EVENTS:
        # Document de résultats lu en entier : une suspension, une AG, une notation, une opération sur le
        # capital ou un fractionnement qu'il CITE ont leur propre avis ; ici ce n'est ni un ton ni un filtre.
        for h in hits:
            if h.risk in _CITED_ONLY_RISKS and h.weight != 0:
                h.weight = 0.0
                h.modifiers.append("événement cité dans un rapport de résultats : ni ton ni filtre")

    # 4b) Résultat net dont la base n'est pas comparable (perte, changement de signe, variation
    # hors bornes) : aucun score numérique, mais le fait se dit en mots — « passage d'un bénéfice
    # à une perte » pèse comme le terme du lexique correspondant (document 07 §3.3).
    rn_fig = figs.get("rn") if isinstance(figs.get("rn"), dict) else None
    if rn_fig and rn_fig.get("note") == NOT_COMPARABLE and not rn_fig.get("reject"):
        raw = rn_fig.get("raw") or [rn_fig.get("value"), rn_fig.get("prev")]
        cur_v, prev_v = (raw + [None, None])[:2]
        fact: tuple[str, float] | None = None
        if cur_v is not None and cur_v < 0 and prev_v is None:
            fact = ("résultat net négatif (perte)", -2.0)  # « est une perte qui s'élève à… », montant précédent non lu
        elif cur_v is not None and prev_v is not None:
            if prev_v > 0 > cur_v:
                fact = ("passage d'un bénéfice à une perte", -2.0)
            elif prev_v < 0 < cur_v:
                fact = ("retour aux bénéfices", 2.0)
            elif cur_v < 0 and prev_v < 0:
                # Perte réduite : amélioration, mais toujours une perte → fait NEUTRE (ni le −2 d'une perte qui
                # dure, ni un terme positif pour une société encore déficitaire) ; perte égale ou aggravée : −2.
                fact = ("perte nette réduite (toujours une perte)", 0.0) if cur_v > prev_v else \
                    ("résultat net toujours déficitaire", -2.0)
            elif cur_v > prev_v > 0:
                fact = ("résultat net multiplié par plus de quatre", 2.0)
        if fact and fact[1] == 0.0:
            # Perte réduite : les mots négatifs sur le résultat (« perte nette », « déficitaire ») décrivent
            # un niveau, pas une dégradation : sans portée. Le fait est listé, avec un poids nul.
            for h in hits:
                if h.indicator == "rn" and h.kind == "neg" and h.weight < 0:
                    h.weight = 0.0
                    h.modifiers.append("perte réduite d'après les montants lus : sans portée")
            hits.append(TermHit(fact[0], "neutral", 0.0, 0.0, "rn", None, str(rn_fig.get("source") or fact[0])[:120],
                                0, 0, 0, modifiers=["lu dans les chiffres : base non comparable"],
                                source="chiffres du document"))
            fact = None
        if fact:
            # Le fait lu dans les montants prime sur les mots du même indicateur qui disent le contraire.
            for h in hits:
                if h.indicator == "rn" and h.kind in ("pos", "neg") and h.weight * fact[1] < 0:
                    h.weight = 0.0
                    h.modifiers.append("contredit par les montants lus : sans portée")
        if fact and not any(h.indicator == "rn" and h.kind in ("pos", "neg") and h.weight * fact[1] > 0 for h in hits):
            hits.append(TermHit(fact[0], "pos" if fact[1] > 0 else "neg", fact[1], fact[1], "rn", None,
                                str(rn_fig.get("source") or fact[0])[:120], 0, 0, 0,
                                modifiers=["lu dans les chiffres : base non comparable"], source="chiffres du document"))

    # 5) Sentiment numérique.
    s_parts: dict[str, float] = {}
    for ind in ("rn", "pnb", "ca"):
        g = extracted.get(f"{ind}_growth")
        if g is not None and np.isfinite(g):
            s_parts[ind] = _clip(100.0 * g / NUM_SCALE_PCT[ind], -2.0, 2.0)
    g = extracted.get("div_growth")
    if g is not None and np.isfinite(g):
        s_parts["div"] = _clip(100.0 * g / NUM_SCALE_PCT["div"], -2.0, 2.0)
    absence = [h for h in hits if h.label == "absence de dividende" and h.weight < 0]
    if absence and "div" not in s_parts and (extracted.get("div_prev") or 0) > 0:
        s_parts["div"] = -2.0
        extracted["div_net"] = 0.0
        extracted["div_growth"] = -1.0
    for ind, v in s_parts.items():
        extracted[f"s_{ind}"] = round(v, 4)
    # s_num_doc : échelle du document 07 (clip(Δ%/25, −2, 2)) ; s_num (contrat, [−1, 1]) :
    # sa moitié, pour l'affichage seulement — le score utilise s_num_doc (« nombres d'abord »).
    s_num_raw = 0.0
    if s_parts:
        wsum = sum(NUM_WEIGHTS[k] for k in s_parts)
        s_num_raw = sum(NUM_WEIGHTS[k] * v for k, v in s_parts.items()) / wsum
    s_num = _clip(s_num_raw / 2.0, -1.0, 1.0)
    replaced = set(s_parts)
    if "pnb" in s_parts and "ca" not in s_parts:
        # Banque : les « revenus », les « recettes » ou le « chiffre d'affaires » décrits en mots sont le
        # produit net bancaire, déjà chiffré (recette du 22/11/2026 : « progression des revenus » comptait
        # comme un chiffre d'affaires « décrit en mots » et réduisait le poids des chiffres).
        replaced.add("ca")
    for h in hits:
        if h.indicator in replaced and h.kind in ("pos", "neg"):
            h.modifiers.append("remplacé par le chiffre" if h.indicator in s_parts
                               else "remplacé par le chiffre (PNB : revenus d'une banque)")
    tone_d = tone_from_hits(hits, exclude_indicators=replaced)
    tone = _clip(tone_d["tone"], -1.0, 1.0)
    # Pondération par couverture : si un indicateur pondéré (RN, dividende, PNB, CA) n'est
    # décrit qu'en mots (« le résultat reste déficitaire ») alors qu'un autre est chiffré
    # (« les ventes bondissent de 40 % »), le poids des chiffres est partagé en proportion.
    lex_only = {
        h.indicator for h in hits
        if h.kind in ("pos", "neg") and h.weight != 0 and h.indicator in NUM_WEIGHTS and h.indicator not in replaced
    }
    w_num_eff = 0.0
    if s_parts:
        cov_num = sum(NUM_WEIGHTS[k] for k in s_parts)
        cov_lex = sum(NUM_WEIGHTS[k] for k in lex_only)
        w_num_eff = W_NUM * cov_num / (cov_num + cov_lex)
    # Document 07 §3.4 règle 5 : s = 0,7·s_num_doc + 0,3·tone, borné à [−1, 1] (le bornage ne
    # change ni le signe, ni le rapport 0,7:0,3 des poids dans le domaine usuel).
    num_part = w_num_eff * s_num_raw
    tone_part = (1.0 - w_num_eff) * tone
    # « Nombres d'abord » (document 07 §3.4, règle 4) : quand la variation du résultat net est lue, le ton
    # peut atténuer la part chiffrée, jamais en renverser le signe. Un ton de signe contraire retire au
    # plus TONE_OPPOSITE_CAP (les trois quarts) de la part chiffrée. Sans cette borne, un seul terme positif
    # (ton +0,67, saturé) donnait un score positif à une publication dont le résultat net, le résultat
    # avant impôt et le PNB baissent, et une concession (« malgré la baisse du chiffre d'affaires »)
    # l'emportait sur la proposition principale chiffrée (recette du 22/11/2026). Choix de conception, non validé.
    tone_capped = False
    if "rn" in s_parts and num_part * tone_part < 0 and abs(tone_part) > TONE_OPPOSITE_CAP * abs(num_part):
        tone_part = -float(np.sign(num_part)) * TONE_OPPOSITE_CAP * abs(num_part)
        tone_capped = True
        warnings.append(
            f"ton lexical ({fr_signed(tone)}) contraire aux chiffres (sentiment numérique {fr_signed(s_num_raw)}) : "
            "le score garde le signe des chiffres, le ton n'en retire que les trois quarts au plus")
    text_score = _clip(num_part + tone_part, -1.0, 1.0) if s_parts else tone

    # 6) Jugement de l'analyste (borné) et contradiction.
    contradiction = False
    analyst_component = None
    score = text_score
    sgn = stance_sign(stance)
    directional_hits = [h for h in hits if h.kind in ("pos", "neg") and h.weight != 0]
    text_evidence = 1.0 if s_parts else (0.6 if directional_hits else 0.0)
    if stance is not None:
        conv = conviction if conviction is not None else 3
        m = sgn * conv / 5.0
        analyst_component = ANALYST_CAP * m
        alpha = 1.0 if text_evidence == 0.0 else (0.4 if s_parts else 0.6)
        score = _clip(alpha * analyst_component + (1.0 - alpha) * text_score, -1.0, 1.0)
        if sgn != 0 and text_evidence > 0 and abs(text_score) >= 0.25 and np.sign(text_score) == -sgn:
            contradiction = True
        if stance == "neutre" and abs(text_score) >= 0.5:
            contradiction = True

    # 7) Filtres de risque.
    flags: list[str] = []

    def flag(code: str) -> None:
        if code not in flags:
            flags.append(code)

    for h in hits:
        if not h.risk or h.weight == 0:
            continue
        if h.kind == "neg" and h.weight < 0:
            if h.risk == "R4" and event_type == "NOTATION_SOUVERAINE":
                continue
            if h.risk == "R1" and event_type == "RESUMPTION":
                continue  # une levée de suspension cite la suspension qu'elle lève
            flag(h.risk)
        elif h.kind == "pos" and h.weight > 0 and h.risk in ("R6", "R8"):
            if author == "analyste" and event_type == "MANUAL":
                continue  # simple mention dans un commentaire (« le fractionnement récent »)
            flag(h.risk)
    if not bond_context:
        if event_type == "SUSPENSION":
            flag("R1")
        if event_type in ("TAKEOVER", "OPV_IPO") and (sym or any(target_kind(t) == "symbol" for t in targets)):
            flag("R6")
    if event_type == "AG_CANCEL":
        flag("R2")
    if event_type in ("SPLIT", "REVERSE_SPLIT"):
        flag("R8")
    if event_type == "PROFIT_WARNING":
        flag("R9")
    if event_type == "RATING" and any(h.indicator == "rating" and h.weight < 0 for h in hits):
        flag("R4")
    if event_type == "CAP_INC" and re.search(r"numeraire|droits?\s+preferentiels?|\bdps\b", norm_all):
        flag("R5")
    if re.search(r"respect\s+de\s+(?:la\s+)?diffusion\s+d'information", norm_title):
        flag("R7")
    rn_g = extracted.get("rn_growth")
    degraded = rn_g is not None and rn_g <= -0.25
    if not degraded and rn_g is None and extracted.get("rn") is not None and extracted.get("rn_prev") is not None:
        # Base non comparable (perte, changement de signe, variation au-delà de ±300 %) : aucune variation
        # n'est notée, mais les deux montants sont gardés et la dégradation se lit sur eux. Sans ce test,
        # les dégradations les plus fortes (bénéfice → perte, perte aggravée) échappaient à R10 (§5.6 :
        # ΔRN ≤ −25 % ; recette du 22/11/2026).
        degraded = rn_degradation(extracted["rn"], extracted["rn_prev"]) is not None
        if degraded:
            extracted["rn_degradation"] = rn_degradation(extracted["rn"], extracted["rn_prev"])
    if event_type in _RESULT_EVENTS and degraded:
        in_force = published_at is None or published_at >= R10_EFFECTIVE
        if in_force:
            pw_found = None
            if history is not None and sym is not None and len(history):
                pw_found = _had_profit_warning(history, sym, published_at)
            if pw_found is False:
                flag("R10")
            elif pw_found is None:
                extracted["r10_candidate"] = True
                what = "ΔRN ≤ −25 %" if rn_g is not None else f"résultat net dégradé ({extracted.get('rn_degradation')})"
                warnings.append(f"{what} : vérifier qu'une alerte sur résultats a précédé (R10)")
    flags.sort(key=lambda c: int(c[1:]))

    # 8) Matérialité.
    base = BASE_MATERIALITY.get(event_type, 0.3)
    mat = base
    mags = [abs(v) for v in s_parts.values()]
    if mags:
        mat += 0.2 * min(max(mags) / 2.0, 1.0)
    elif directional_hits:
        mat += 0.05 * min(len(directional_hits), 2)
    if any(f in flags for f in ("R1", "R3", "R9")):
        mat += 0.1
    kind = target_kind(primary) if primary else None
    mat *= TARGET_FACTOR.get(kind, 0.5) if kind else 0.5
    if bond_context:
        mat *= 0.3 if kind != "country" else 0.6
    if stance is not None and conviction:
        mat = max(mat, 0.3 + 0.1 * conviction)
    materiality = _clip(mat, 0.0, 1.0)

    # 9) Confiance.
    c_type = {"manual": 0.9, "title": 1.0, "text": 0.7, "weak": 0.5, "default": 0.4, "none": 0.3}.get(ev_origin, 0.3)
    if manual:
        c_target = 1.0
    elif primary is None:
        c_target = 0.2
    else:
        c_target = {"symbol": 1.0 if links.in_title(primary) else 0.8, "index": 0.7, "sector": 0.7, "country": 0.7}.get(
            kind or "", 0.5
        )
    if s_parts or has_numbers:
        c_signal = extract_conf
        if any(isinstance(figs.get(k), dict) and figs[k].get("consistent") is True for k in ("rn", "pnb", "ca")):
            c_signal = min(1.0, c_signal + 0.1)
        if any(isinstance(figs.get(k), dict) and figs[k].get("consistent") is False for k in ("rn", "pnb", "ca")):
            c_signal = max(0.1, c_signal - 0.2)
    elif directional_hits:
        c_signal = min(0.55, 0.25 + 0.1 * len(directional_hits))
    elif event_type in _DIRECTIONAL_EVENTS and ev_origin == "title":
        c_signal = 0.5
    else:
        c_signal = 0.2
    discarded = [k for k in ("rn", "pnb", "ca") if isinstance(figs.get(k), dict) and (figs[k].get("reject") or figs[k].get("note"))]
    if document is not None and document.get("rejected"):
        discarded += [str(r.get("ind")) for r in document["rejected"] if r.get("ind") in ("rn", "pnb", "ca")]
    if discarded and not s_parts:
        # Chiffres vus mais écartés (ambiguïté, incohérence, base non comparable) : le score ne
        # repose que sur le ton, avec une confiance basse.
        c_signal = min(c_signal, 0.25)
    if stance is not None:
        c_signal = max(c_signal, 0.35 + 0.05 * (conviction or 3))
    conf = 0.30 * c_type + 0.25 * c_target + 0.45 * c_signal
    if contradiction:
        conf *= 0.7
    if tone_capped:
        conf *= 0.85  # le texte et les chiffres ne disent pas la même chose
    if tone_d["uncertainty"] >= 2:
        conf *= 0.85
    if method == "ocr":
        conf *= 0.8
    if len(norm_all.strip()) < 25 and ev_origin not in ("title", "manual"):
        conf *= 0.8
    confidence = _clip(conf, 0.05, 0.95)

    # 10) Lecture.
    analysis = NoteAnalysis(
        targets=targets,
        event_type=event_type,
        tone=round(tone, 4),
        s_num=round(s_num, 4),
        score=round(score, 4),
        materiality=round(materiality, 4),
        confidence=round(confidence, 4),
        risk_flags=flags,
        extracted={k: v for k, v in extracted.items()},
        reading="",
        matched_terms=[h.to_dict() for h in hits],
        primary_target=primary,
        components={
            "P": round(tone_d["P"], 4),
            "N": round(tone_d["N"], 4),
            "uncertainty_terms": int(tone_d["uncertainty"]),
            "s_num_raw": round(s_num_raw, 4),
            "s_num_doc": round(s_num_raw, 4),
            "score_formula": ("clip(w_num·s_num_doc + (1 − w_num)·tone, −1, 1) (document 07 §3.4) ; w_num = 0,7 × part "
                              "des indicateurs chiffrés ; ton contraire aux chiffres borné aux trois quarts de la part "
                              "chiffrée quand la variation du résultat net est lue") if s_parts else "tone",
            "s_parts": {k: round(v, 4) for k, v in s_parts.items()},
            "text_score": round(text_score, 4),
            "analyst": None if analyst_component is None else round(analyst_component, 4),
            "event_origin": ev_origin,
            "entity_terms": links.terms,
            "ambiguous_entities": list(links.ambiguous),
            "weights": {"w_num": round(w_num_eff, 4) if s_parts else 0.0, "w_tone": round(1 - w_num_eff, 4) if s_parts else 1.0,
                        "analyst_cap": ANALYST_CAP},
            "lexical_only_indicators": sorted(lex_only),
            "tone_contradicts_numbers": bool(tone_capped),
            "event_candidate": event_candidate,
            "context_entities": context_entities,
            "theme_exposure": {t: theme_exposure(t) for t in targets if target_kind(t) == "theme" and theme_exposure(t)},
        },
        contradiction=contradiction,
        warnings=warnings,
        version=ANALYZE_VERSION,
    )
    analysis.reading = build_reading(
        analysis, hits, stance=stance, conviction=conviction, published_at=published_at,
        published_precision=published_precision, first_session=first_session, known_at=known_at,
        sessions=sessions,
    )
    return analysis


def rn_degradation(cur: float | None, prev: float | None, threshold: float = 0.25) -> str | None:
    """Dégradation du résultat net d'au moins ``threshold`` lue sur les **montants** (filtre R10).

    Renvoie le motif en français, ou ``None`` : « passage d'un bénéfice à une perte » (base positive,
    résultat négatif ou nul), « perte aggravée de X % » (base négative, perte accrue d'au moins 25 % de
    la perte précédente), « baisse de X % » (base positive, baisse d'au moins 25 %). Sert quand la
    variation n'est pas notée (« base non comparable ») : le score numérique reste absent.
    """
    if cur is None or prev is None or not np.isfinite(cur) or not np.isfinite(prev) or cur >= prev:
        return None
    if prev > 0:
        if cur <= 0:
            return "passage d'un bénéfice à une perte"
        g = (cur - prev) / prev
        return f"baisse de {abs(g) * 100:.0f} %" if g <= -threshold + _EPS else None
    if prev < 0:
        g = (cur - prev) / abs(prev)
        return f"perte aggravée de {abs(g) * 100:.0f} %" if g <= -threshold + _EPS else None
    return "passage de l'équilibre à une perte"  # prev == 0, cur < 0


def _had_profit_warning(history: pd.DataFrame, symbol: str, published_at: pd.Timestamp | None) -> bool | None:
    """Une alerte sur résultats du titre a-t-elle été publiée dans les 120 jours précédents ?"""
    if history is None or not len(history) or published_at is None:
        return None
    df = history
    if "published_at" not in df.columns:
        return None
    pub = pd.to_datetime(df["published_at"], utc=True)
    lo = published_at - pd.Timedelta(days=120)
    mask = (pub >= lo) & (pub < published_at)
    if "event_type" in df.columns:
        et = df["event_type"].astype(str)
        mask &= et.eq("PROFIT_WARNING")
    else:
        return None

    def has_sym(row: Any) -> bool:
        tg = row.get("all_targets", None)
        if tg is None or (isinstance(tg, float) and math.isnan(tg)):
            tg = row.get("targets", [])
        return symbol in list(tg or [])

    sub = df[mask]
    return bool(any(has_sym(r) for _, r in sub.iterrows()))


# ---------------------------------------------------------------------------
# Lecture en français
# ---------------------------------------------------------------------------

_IND_LABEL = {"rn": "résultat net", "pnb": "PNB", "ca": "chiffre d'affaires", "rai": "résultat avant impôt"}
_FLAG_SHORT = {
    "R1": "R1 (suspension : aucun achat)",
    "R2": "R2 (AG annulée ou reportée : aucun achat pendant 60 séances)",
    "R3": "R3 (audit, continuité ou capitaux propres : exclusion)",
    "R4": "R4 (notation dégradée : poids maximal × 0,5)",
    "R5": "R5 (augmentation de capital en numéraire : attendre le détachement des droits)",
    "R6": "R6 (offre publique : signaux automatiques gelés)",
    "R7": "R7 (publication en retard)",
    "R8": "R8 (fractionnement ou regroupement : contrôler l'ajustement)",
    "R9": "R9 (alerte sur résultats : aucun achat pendant 60 séances)",
    "R10": "R10 (baisse ≥ 25 % sans alerte préalable)",
}


def _cap_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def build_reading(
    a: NoteAnalysis,
    hits: list[TermHit],
    stance: str | None = None,
    conviction: int | None = None,
    published_at: pd.Timestamp | None = None,
    published_precision: str | None = None,
    first_session: pd.Timestamp | None = None,
    known_at: pd.Timestamp | None = None,
    sessions: Any = None,
) -> str:
    """Deux à cinq phrases factuelles qui expliquent le score.

    ``known_at`` (saisie ou collecte) : si la note n'est connue qu'après la coupure de sa
    séance négociable, la lecture donne aussi la séance où les signaux stricts la prennent en
    compte (coupure de 09h00 appliquée à l'instant de connaissance, ``signals.notes_asof``).
    """
    ex = a.extracted
    sentences: list[str] = []
    # 1) Type et cible.
    etype = EVENT_TYPES.get(a.event_type, a.event_type.lower())
    if a.primary_target:
        tgt = a.primary_target if target_kind(a.primary_target) == "symbol" else target_label(a.primary_target)
        others = [t for t in a.targets if t != a.primary_target][:3]
        s1 = f"{_cap_first(etype)} ({a.event_type}) concernant {tgt}"
        if others:
            s1 += " ; autres cibles : " + ", ".join(others)
    else:
        s1 = f"{_cap_first(etype)} ({a.event_type}) sans cible identifiée (ni titre, ni indice, ni pays reconnu)"
    if ex.get("bond_context"):
        s1 += " ; il s'agit d'une ligne obligataire, sans portée directe pour les actions"
    cand = a.components.get("event_candidate")
    if cand:
        s1 += f" ; le texte évoque aussi « {EVENT_TYPES.get(cand, cand.lower())} », retenu comme contexte et non comme événement"
    expo = a.components.get("theme_exposure") or {}
    if expo:
        sign = {1: "+", -1: "−", 0: "±"}
        bits = []
        for items in expo.values():
            for it in items:
                if it["target"] not in a.targets:
                    bits.append(f"{it['target']} ({sign.get(it['sign'], '±')})")
        if bits:
            s1 += " ; titres exposés au thème (sens d'une hausse du facteur) : " + ", ".join(dict.fromkeys(bits))
    sentences.append(s1 + ".")
    # 2) Chiffres.
    parts = []
    dropped = []
    for ind in ("rn", "pnb", "ca", "rai"):
        v, p, g = ex.get(ind), ex.get(f"{ind}_prev"), ex.get(f"{ind}_growth")
        why = ex.get(f"{ind}_note")
        if v is None and g is None:
            if why:
                dropped.append(f"{ex.get(f'{ind}_label') or _IND_LABEL[ind]} ({why})")
            continue
        txt = str(ex.get(f"{ind}_label") or _IND_LABEL[ind])
        if v is not None:
            txt += " " + fr_amount(v)
        if p is not None:
            txt += " contre " + fr_amount(p)
        if g is not None:
            txt += f" ({fr_pct(g)})"
        elif why:
            txt += f" ({why} : pas de score numérique)"
        if ind == "rai":
            txt += " [non pondéré]"
        parts.append(txt)
    if ex.get("div_net") is not None or ex.get("div_gross") is not None:
        dv = ex.get("div_net") if ex.get("div_net") is not None else ex.get("div_gross")
        lab = "dividende net" if ex.get("div_net") is not None else "dividende brut"
        txt = f"{lab} {fr_amount(dv)}" if dv else "dividende supprimé"
        if ex.get("div_gross") is not None and ex.get("div_net") is not None and dv:
            basis = ex.get("div_basis") or "brut"
            if basis == "brut présumé":
                txt += f" (estimé : montant affiché {fr_amount(ex['div_gross'])} présumé brut, IRVM déduit)"
            else:
                txt += f" (brut {fr_amount(ex['div_gross'])})"
        if ex.get("div_prev"):
            src = " (dernier versé, BOC)" if ex.get("div_prev_source") == "panel" else ""
            txt += f" contre {fr_amount(ex['div_prev'])}{src}"
        if ex.get("div_growth") is not None:
            txt += f" ({fr_pct(ex['div_growth'])})"
        parts.append(txt)
    doc_status = ex.get("doc_status")
    if parts:
        perim = f" (comptes {ex['doc_perimeter']}s)" if ex.get("doc_perimeter") else ""
        s2 = (f"Chiffres lus dans le document{perim} : " if doc_status else "Chiffres extraits : ") + " ; ".join(parts)
        if a.components.get("s_parts"):
            s_doc = a.components.get("s_num_doc", 2.0 * a.s_num)
            s2 += (f", soit un sentiment numérique de {fr_signed(s_doc)} "
                   "(échelle du document 07 : ±25 % sur le RN, le PNB ou le CA, ±20 % sur le dividende = ±1, "
                   "borné à ±2)")
        if dropped:
            s2 += " ; écarté(s) : " + ", ".join(dropped)
        sentences.append(s2 + ".")
    elif dropped:
        sentences.append("Chiffres vus mais écartés, aucun score numérique : " + ", ".join(dropped) + ".")
    if doc_status in ("scan", "illisible"):
        sentences.append(
            ("Document scanné (image sans texte) : son contenu n'a pas pu être lu, seul le titre est analysé."
             if doc_status == "scan" else
             "Document illisible : son contenu n'a pas pu être lu, seul le titre est analysé.")
        )
    # 2b) Dividende : rendement et fenêtre (orientation rendement, signal S1 du doc 07).
    if a.event_type == "DIV_NOTICE" or ex.get("ex_date") is not None:
        bits = []
        if ex.get("ex_date") is not None:
            bits.append(f"détachement le {fr_date(ex['ex_date'])}")
        if ex.get("pay_date") is not None:
            bits.append(f"paiement le {fr_date(ex['pay_date'])}")
        y = ex.get("yield_at_notice")
        if y is not None:
            seuil = "au-dessus" if y >= 0.04 else "en dessous"
            bits.append(f"rendement net {fr_num(100 * y, 2)} % au dernier cours connu ({seuil} du seuil S1 de 4 %)")
        liq = ex.get("median_value_60d")
        if liq is not None:
            ok = "≥" if liq >= 1e6 else "<"
            bits.append(f"valeur médiane échangée {fr_amount(liq)} par séance ({ok} 1 M FCFA, seuil S1)")
        if ex.get("sessions_to_ex") is not None:
            n = ex["sessions_to_ex"]
            ok = "suffisant" if n >= 3 else "insuffisant"
            bits.append(f"{n} séance(s) négociable(s) avant le détachement ({ok} pour S1, minimum 3)")
        if bits:
            sentences.append(_cap_first(" ; ".join(bits)) + ".")
    # 3) Ton lexical.
    shown = [h for h in hits if h.kind in ("pos", "neg") and h.weight != 0 and "remplacé par le chiffre" not in h.modifiers]
    if shown:
        items = []
        for h in shown[:4]:
            mod = ""
            if h.modifiers:
                mod = ", " + ", ".join(m for m in h.modifiers if not m.startswith("pourcentage"))
                mod = mod if mod != ", " else ""
            items.append(f"« {h.surface.strip()} » ({fr_signed(h.weight, 1)}{mod})")
        s3 = f"Ton lexical {fr_signed(a.tone)} : " + ", ".join(items)
        if a.components.get("tone_contradicts_numbers"):
            s3 += " ; ce ton est contraire aux chiffres : le score garde le signe des chiffres"
        sentences.append(s3 + ".")
    elif not parts and not dropped and doc_status not in ("scan", "illisible"):
        unc = [h for h in hits if h.kind == "unc"]
        if unc:
            sentences.append(
                "Aucun terme directionnel du lexique BRVM-FR ; termes d'incertitude : "
                + ", ".join(f"« {h.surface.strip()} »" for h in unc[:3]) + "."
            )
        else:
            sentences.append("Aucun terme directionnel du lexique BRVM-FR ni chiffre exploitable : ton neutre.")
    # 4) Analyste et contradiction.
    if stance is not None:
        conv = conviction if conviction is not None else 3
        s4 = f"Avis de l'analyste : {stance}, conviction {conv}/5, pris en compte de façon bornée (±0,8 au plus)"
        if a.contradiction:
            s4 += (
                f" ; contradiction avec le texte (score du texte {fr_signed(a.components.get('text_score', 0.0))}) : "
                "note à revoir avant toute prise de position"
            )
        sentences.append(s4 + ".")
    # 5) Score, filtres, négociabilité.
    s5 = f"Score {fr_signed(a.score)}, matérialité {fr_num(a.materiality, 2)}, confiance {fr_num(a.confidence, 2)}"
    if a.risk_flags:
        s5 += " ; filtres : " + ", ".join(_FLAG_SHORT.get(f, f) for f in a.risk_flags)
    if first_session is not None:
        if published_at is not None:
            if published_precision == "date":
                pub = f"publication datée du {fr_date(published_at)} sans heure, réputée après la séance"
            else:
                t = published_at
                when = "avant" if t.time() < _dt.time(9, 0) else "après"
                pub = f"publication le {t:%d/%m/%Y} à {t:%Hh%M} UTC, {when} la coupure de 09h00"
            s5 += f" ; négociable à partir de la séance du {fr_date(first_session)} ({pub})"
        else:
            s5 += f" ; négociable à partir de la séance du {fr_date(first_session)}"
        k = to_utc(known_at) if known_at is not None else None
        if k is not None:
            k_session = first_tradable_session(k, sessions, date_only=False)
            if k_session is not None and k_session > pd.Timestamp(first_session):
                s5 += (f" ; connue le {k:%d/%m/%Y} à {k:%Hh%M} UTC : prise en compte par les signaux à partir "
                       f"de la séance du {fr_date(k_session)}")
    sentences.append(s5 + ".")
    # Deux à cinq phrases : fusion des phrases intermédiaires si nécessaire.
    while len(sentences) > 5:
        a1, a2 = sentences[1], sentences[2]
        sentences[1:3] = [a1.rstrip(".") + " ; " + a2[:1].lower() + a2[1:]]
    return " ".join(sentences)


__all__ = [
    "analyze_note", "analyze_text", "extract_figures", "extract_dates", "fiscal_period", "parse_fr_number",
    "build_reading", "fr_amount", "fr_pct", "fr_num", "fr_signed", "fr_date", "BASE_MATERIALITY", "ANALYZE_VERSION",
    "read_document", "period_mentions", "expected_period", "document_from_extracted", "DOC_MARK_KEYS",
    "CONSISTENCY_TOL", "MAX_ABS_GROWTH", "NOT_COMPARABLE", "INCONSISTENT", "MAX_EXCERPT_CHARS", "READER_VERSION",
]
