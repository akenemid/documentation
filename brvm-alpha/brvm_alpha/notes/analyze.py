"""Analyse d'une note -> :class:`NoteAnalysis` (document 07, §3.2 à §3.4, §6.3 à §6.6).

Chaîne de traitement (« les chiffres d'abord », §3.2) :

1. **cibles** : cibles saisies + entités liées dans le titre et le texte (:mod:`.entities`) ;
2. **type d'événement** : règles du §6.4 sur le titre, puis le début du texte (:mod:`.lexicon`) ;
3. **chiffres** : résultat net, PNB, chiffre d'affaires, dividende et leur variation, au
   format français (« 245,3 milliards FCFA contre 210,1 milliards », « 1 234 567 FCFA »,
   « +16,8 % », « en hausse de 18,2 % ») ; dates (ex-dividende, paiement, registres, AG) ;
4. **sentiment numérique** : ``s = clip(Δ%/25, −2, 2)`` pour RN, PNB, CA (25 % = seuil
   réglementaire d'alerte sur résultats) et ``clip(Δdiv%/20, −2, 2)`` pour le dividende ;
   −2 si le dividende disparaît alors qu'il était versé. ``s_num`` = moyenne pondérée
   (RN 1, dividende 0,8, PNB 0,6, CA 0,5), ramenée à [−1, 1] (division par 2) ;
5. **ton lexical** : ``(P − N) / (P + N + 1)`` ; les termes d'un indicateur chiffré sont
   remplacés par le chiffre (§3.4, règle 4) ;
6. **score** : ``0,7·s_num + 0,3·tone`` si un chiffre a été extrait, sinon ``tone`` ; si un
   indicateur pondéré n'est décrit qu'en mots alors qu'un autre est chiffré, le poids 0,7
   est partagé en proportion des poids des indicateurs (pondération par couverture) ;
   pour une note de l'analyste avec ``stance`` / ``conviction``, combinaison bornée du
   jugement (±0,8 au plus) et du texte, avec signalement des contradictions ;
7. **matérialité**, **confiance** (champ structuré 1,0 > regex sur texte 0,6 > OCR 0,3),
   **filtres de risque** R1-R10 lisibles dans le seul texte, et **lecture** en français.

Aucun score n'est une prévision certaine : c'est une lecture factuelle et chiffrée, avec
son degré de confiance, à valider hors échantillon avant tout usage (S5, poids initial 0).
"""

from __future__ import annotations

import datetime as _dt
import math
import re
from dataclasses import dataclass
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
    _calendar,
    asof_utc,
    fold,
    fold_with_map,
    normalize_event_type,
    normalize_targets,
    stance_sign,
    target_kind,
    target_label,
    to_day,
)

ANALYZE_VERSION = "notes-analyze/1 (BRVM-FR v0)"

#: Échelles du sentiment numérique (document 07 §3.4 et §6.7).
NUM_SCALE_PCT = {"rn": 25.0, "pnb": 25.0, "ca": 25.0, "div": 20.0}
NUM_WEIGHTS = {"rn": 1.0, "div": 0.8, "pnb": 0.6, "ca": 0.5}
W_NUM, W_TONE = 0.7, 0.3
#: Poids maximal du jugement de l'analyste et borne de son effet sur le score.
ANALYST_CAP = 0.8
#: Date d'entrée en vigueur de l'instruction BRVM 01-2025 (alertes sur résultats, R10).
R10_EFFECTIVE = pd.Timestamp("2025-10-01", tz="UTC")
EUR_FCFA = 655.957

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
_FROM_TO = re.compile(
    r"(?<![a-z])pass\w*\s+de\s+(?P<a>" + NUM + r")\s*(?P<ua>" + _UNIT + r")?(?:\s+de)?\s*(?:" + _CUR + r")?\s*"
    r"(?:en\s+20\d\d\s+)?a\s+(?P<b>" + NUM + r")\s*(?P<ub>" + _UNIT + r")?"
)

#: Mentions d'indicateurs (texte normalisé). « Bénéfice par action » n'est pas le RN.
_IND_PATTERNS = {
    "rn": (
        r"resultats?\s+nets?(?:\s+(?:consolides?|sociaux|social|part\s+du\s+groupe|global|de\s+l'exercice|pdg))*"
        r"(?!\s+(?:par\s+action|unitaire))|benefices?(?:\s+nets?)?(?!\s+(?:net\s+)?par\s+action)|\brn\b|"
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


def _amounts(norm: str, a: int, b: int) -> list[_Amount]:
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


def extract_figures(text: str, title: str = "") -> dict[str, Any]:
    """Extrait RN, PNB, CA et dividende (niveau, niveau précédent, variation) d'un texte.

    Renvoie un dictionnaire ``{indicateur: {...}}`` pour ``rn``, ``pnb``, ``ca``, ``div``
    (clés ``value``, ``prev``, ``growth`` en décimal, ``growth_from`` = ``pct`` | ``levels``,
    ``consistent``, ``surface``) ; pour le dividende : ``net``, ``gross``, ``prev``,
    ``growth``, ``total``. Les montants sont en FCFA.
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
    for i, (ind, s, e) in enumerate(mentions):
        if i in comparative:
            continue
        if ind in res and res[ind].get("growth") is not None and (ind != "div" or res[ind].get("net") is not None):
            continue  # première mention exploitable retenue
        stop = _sentence_end(norm, e)
        nxt = next((ms for k, (_, ms, _) in enumerate(mentions) if k > i and ms >= e and k not in comparative), None)
        if nxt is not None:
            stop = min(stop, nxt)  # les chiffres suivants appartiennent à l'indicateur suivant
        stop = min(stop, e + 220)
        mention_txt = norm[s:e]
        lookback = norm[max(_sentence_start(norm, s), s - 40) : s]
        surface = full[idx[s] : idx[min(stop, len(idx)) - 1] + 1] if stop > s else full[idx[s] : idx[e - 1] + 1]
        if ind == "div":
            info = _extract_div(norm, e, stop, mention_txt)
        else:
            info = _extract_level(norm, e, stop, mention_txt, lookback, negative=("perte" in mention_txt))
        if not info:
            continue
        info["surface"] = surface.strip()
        prev = res.get(ind)
        if prev is None or (prev.get("growth") is None and info.get("growth") is not None) or (
            ind == "div" and prev.get("net") is None and info.get("net") is not None
        ):
            res[ind] = info
    return res


def _extract_level(norm: str, a: int, b: int, mention: str, lookback: str, negative: bool) -> dict[str, Any]:
    amounts = _amounts(norm, a, b)
    pcts = _pcts(norm, a, b)
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
                if nm:
                    v = parse_fr_number(nm.group(0))
                    if v is not None:
                        prev = v * amounts[0].multiplier
    if negative:
        if cur is not None and cur > 0:
            cur = -cur
    window = norm[a:b]
    if cur is not None and cur > 0 and re.search(r"deficitaire|negatif|deficit", window[:80]):
        cur = -cur
    growth_lv = None
    if cur is not None and prev not in (None, 0):
        growth_lv = (cur - prev) / abs(prev)
    growth_pct = None
    for v, ps, pe, explicit, surf in pcts:
        before = norm[max(a, ps - 40) : ps]
        if explicit:
            growth_pct = v / 100.0
            break
        d = _direction(before)
        if d == 0 and _RATIO_W.search(norm[max(a, ps - 25) : ps]):
            continue
        if d == 0:
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
    if growth_pct is not None:
        info["growth"] = growth_pct
        info["growth_from"] = "pct"
        if growth_lv is not None:
            info["growth_levels"] = growth_lv
            info["consistent"] = abs(growth_pct - growth_lv) <= 0.01 + 0.05 * abs(growth_lv)
    elif growth_lv is not None:
        info["growth"] = growth_lv
        info["growth_from"] = "levels"
    else:
        info["growth"] = None
    return info


def _extract_div(norm: str, a: int, b: int, mention: str) -> dict[str, Any]:
    amounts = [x for x in _amounts(norm, a, b)]
    info: dict[str, Any] = {"net": None, "gross": None, "prev": None, "growth": None, "total": None}
    per_share = [x for x in amounts if abs(x.value) < 1e6]
    totals = [x for x in amounts if abs(x.value) >= 1e6]
    if totals:
        info["total"] = totals[0].value
    prev_pos = None
    pm = _PREV_W.search(norm, a, b)
    if pm:
        prev_pos = pm.end()
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
        elif k == 0:
            q = "gross" if re.search(r"(?<![a-z])bruts?(?![a-z])", mention) else "net"
            if q == "net" and not re.search(r"(?<![a-z])nets?(?![a-z])", mention):
                info["assumed_net"] = True
        if q and info[q] is None:
            info[q] = x.value
    pcts = _pcts(norm, a, b)
    for v, ps, pe, explicit, surf in pcts:
        before = norm[max(a, ps - 40) : ps]
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
      dictionnaire ``note.analysis["structured"]`` est utilisé de la même façon.
    """
    if structured is None and isinstance(note.analysis, dict) and isinstance(note.analysis.get("structured"), dict):
        structured = note.analysis["structured"]
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
    )


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
) -> NoteAnalysis:
    tags = [fold(t) for t in (tags or [])]
    warnings: list[str] = []
    manual = normalize_targets(manual_targets or [])

    # 1) Entités et cibles.
    links = link_entities(text, title)
    # La BRVM comme émettrice de l'avis (« La Bourse Régionale des Valeurs Mobilières
    # informe… ») n'est pas une cible quand une société est nommée.
    if any(target_kind(t) == "symbol" for t in links.targets):
        publisher = [m for m in links.matches if m.code == "MARCHE" and alias_key(m.alias) in _PUBLISHER_KEYS]
        if publisher and all(alias_key(m.alias) in _PUBLISHER_KEYS for m in links.matches if m.code == "MARCHE"):
            links.matches = [m for m in links.matches if m.code != "MARCHE"]
            links.targets = [t for t in links.targets if t != "MARCHE"]
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
        event_type, ev_origin = detect_event_type(title, text)
        if ev_origin == "weak" and author == "analyste":
            event_type, ev_origin = "OTHER", "none"  # « résultat » dans une note libre : pas une publication
        if event_type == "OTHER":
            if author == "analyste":
                event_type, ev_origin = "MANUAL", "default"
            elif "presse" in tags or "press" in tags:
                event_type, ev_origin = "PRESS", "default"

    # 3) Chiffres et dates.
    figs = extract_figures(text, title)
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
    period = fiscal_period(text, title)
    method = "ocr" if "ocr" in tags else "regex"
    extract_conf = 0.3 if method == "ocr" else 0.6
    extracted: dict[str, Any] = {}
    for ind in ("rn", "pnb", "ca"):
        f = figs.get(ind)
        if f:
            extracted[ind] = f.get("value")
            extracted[f"{ind}_prev"] = f.get("prev")
            extracted[f"{ind}_growth"] = f.get("growth")
            if f.get("consistent") is False:
                warnings.append(
                    f"{ind.upper()} : variation annoncée {fr_pct(f['growth'])} et variation des niveaux "
                    f"{fr_pct(f['growth_levels'])} incohérentes"
                )
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
    has_numbers = any(extracted.get(k) is not None for k in ("rn", "pnb", "ca", "div_net", "div_gross", "rn_growth"))
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
    s_num_raw = 0.0
    if s_parts:
        wsum = sum(NUM_WEIGHTS[k] for k in s_parts)
        s_num_raw = sum(NUM_WEIGHTS[k] * v for k, v in s_parts.items()) / wsum
    s_num = _clip(s_num_raw / 2.0, -1.0, 1.0)
    replaced = set(s_parts)
    for h in hits:
        if h.indicator in replaced and h.kind in ("pos", "neg"):
            h.modifiers.append("remplacé par le chiffre")
    tone_d = tone_from_hits(hits, exclude_indicators=replaced)
    tone = _clip(tone_d["tone"], -1.0, 1.0)
    # Pondération par couverture : si un indicateur pondéré (RN, dividende, PNB, CA) n'est
    # décrit qu'en mots (« le résultat reste déficitaire ») alors qu'un autre est chiffré
    # (« les ventes bondissent de 40 % »), le poids des chiffres est partagé en proportion.
    lex_only = {
        h.indicator for h in hits
        if h.kind in ("pos", "neg") and h.weight != 0 and h.indicator in NUM_WEIGHTS and h.indicator not in s_parts
    }
    w_num_eff = 0.0
    if s_parts:
        cov_num = sum(NUM_WEIGHTS[k] for k in s_parts)
        cov_lex = sum(NUM_WEIGHTS[k] for k in lex_only)
        w_num_eff = W_NUM * cov_num / (cov_num + cov_lex)
    text_score = _clip(w_num_eff * s_num + (1.0 - w_num_eff) * tone, -1.0, 1.0) if s_parts else tone

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
    if event_type in _RESULT_EVENTS and rn_g is not None and rn_g <= -0.25:
        in_force = published_at is None or published_at >= R10_EFFECTIVE
        if in_force:
            pw_found = None
            if history is not None and sym is not None and len(history):
                pw_found = _had_profit_warning(history, sym, published_at)
            if pw_found is False:
                flag("R10")
            elif pw_found is None:
                extracted["r10_candidate"] = True
                warnings.append("ΔRN ≤ −25 % : vérifier qu'une alerte sur résultats a précédé (R10)")
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
    if stance is not None:
        c_signal = max(c_signal, 0.35 + 0.05 * (conviction or 3))
    conf = 0.30 * c_type + 0.25 * c_target + 0.45 * c_signal
    if contradiction:
        conf *= 0.7
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
            "s_parts": {k: round(v, 4) for k, v in s_parts.items()},
            "text_score": round(text_score, 4),
            "analyst": None if analyst_component is None else round(analyst_component, 4),
            "event_origin": ev_origin,
            "entity_terms": links.terms,
            "ambiguous_entities": list(links.ambiguous),
            "weights": {"w_num": round(w_num_eff, 4) if s_parts else 0.0, "w_tone": round(1 - w_num_eff, 4) if s_parts else 1.0,
                        "analyst_cap": ANALYST_CAP},
            "lexical_only_indicators": sorted(lex_only),
            "event_candidate": event_candidate,
            "theme_exposure": {t: theme_exposure(t) for t in targets if target_kind(t) == "theme" and theme_exposure(t)},
        },
        contradiction=contradiction,
        warnings=warnings,
        version=ANALYZE_VERSION,
    )
    analysis.reading = build_reading(
        analysis, hits, stance=stance, conviction=conviction, published_at=published_at,
        published_precision=published_precision, first_session=first_session,
    )
    return analysis


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

_IND_LABEL = {"rn": "résultat net", "pnb": "PNB", "ca": "chiffre d'affaires"}
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
) -> str:
    """Deux à cinq phrases factuelles qui expliquent le score."""
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
    for ind in ("rn", "pnb", "ca"):
        v, p, g = ex.get(ind), ex.get(f"{ind}_prev"), ex.get(f"{ind}_growth")
        if v is None and g is None:
            continue
        txt = _IND_LABEL[ind]
        if v is not None:
            txt += " " + fr_amount(v)
        if p is not None:
            txt += " contre " + fr_amount(p)
        if g is not None:
            txt += f" ({fr_pct(g)})"
        parts.append(txt)
    if ex.get("div_net") is not None or ex.get("div_gross") is not None:
        dv = ex.get("div_net") if ex.get("div_net") is not None else ex.get("div_gross")
        lab = "dividende net" if ex.get("div_net") is not None else "dividende brut"
        txt = f"{lab} {fr_amount(dv)}" if dv else "dividende supprimé"
        if ex.get("div_prev"):
            src = " (dernier versé, BOC)" if ex.get("div_prev_source") == "panel" else ""
            txt += f" contre {fr_amount(ex['div_prev'])}{src}"
        if ex.get("div_growth") is not None:
            txt += f" ({fr_pct(ex['div_growth'])})"
        parts.append(txt)
    if parts:
        s2 = "Chiffres extraits : " + " ; ".join(parts)
        if a.components.get("s_parts"):
            s2 += (f", soit un sentiment numérique de {fr_signed(a.s_num)} "
                   "(échelle : ±25 % sur le RN, le PNB ou le CA, ±20 % sur le dividende = ±0,5)")
        sentences.append(s2 + ".")
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
        sentences.append(f"Ton lexical {fr_signed(a.tone)} : " + ", ".join(items) + ".")
    elif not parts:
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
    sentences.append(s5 + ".")
    # Deux à cinq phrases : fusion des phrases intermédiaires si nécessaire.
    while len(sentences) > 5:
        a1, a2 = sentences[1], sentences[2]
        sentences[1:3] = [a1.rstrip(".") + " ; " + a2[:1].lower() + a2[1:]]
    return " ".join(sentences)


__all__ = [
    "analyze_note", "analyze_text", "extract_figures", "extract_dates", "fiscal_period", "parse_fr_number",
    "build_reading", "fr_amount", "fr_pct", "fr_num", "fr_signed", "fr_date", "BASE_MATERIALITY", "ANALYZE_VERSION",
]
