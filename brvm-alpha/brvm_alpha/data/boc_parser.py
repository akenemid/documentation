"""Extraction structurée des Bulletins Officiels de la Cote (BOC) de la BRVM.

Le texte d'entrée est la sortie de ``pdftotext -layout`` (voir ``boc_download``).
Le parseur produit, pour une séance :

* ``equities``   : une ligne par action cotée (cours, volumes, dividende, PER...) ;
* ``indices``    : indices phares, de compartiment, Total Return et sectoriels ;
* ``market``     : indicateurs de marché de la page 1 (capitalisation, PER moyen...) ;
* ``order_book`` : meilleures limites (carnet d'ordres résiduel) des actions ;
* ``warnings``   : anomalies détectées (jamais d'exception pour une ligne douteuse).

Principes de robustesse
-----------------------
1. **Tokenisation typée et positionnelle.** Chaque ligne est découpée en jetons
   (date, pourcentage, marqueur NC/SP/(d), nombre) en mémorisant leur colonne.
   Les dates et pourcentages sont reconnus *avant* les nombres, ce qui règle les
   colonnes collées par une seule espace (``"704 18-sept.-26"``, ``"8,57 % 519,40"``).
   Un nombre n'agrège des groupes de milliers qu'à travers une espace *simple*
   suivie d'exactement 3 chiffres : deux colonnes séparées par 2 espaces ou plus
   ne sont jamais fusionnées.
2. **Grammaire de ligne.** Une ligne action suit l'ordre
   ``préc. ouv. clôt. var% [vol val] réf [var_an%] [div] [date] [rdt%] [PER]``.
   Toutes les affectations jetons -> colonnes compatibles avec les types et
   l'ordre sont énumérées puis notées (cohérence prix/volume/valeur,
   rendement = dividende / cours, etc.).
3. **Désambiguïsation par position.** Quand plusieurs affectations restent
   plausibles (ex. un nombre isolé après la variation annuelle : dividende ou
   PER ?), on compare la colonne du jeton avec la colonne médiane apprise sur
   les lignes non ambiguës de la même page.
4. **Lignes de continuation.** Nom sur deux lignes, code secteur sous le
   symbole (format 2025+) et chiffres débordant sous une colonne (ex. ``270``
   sous la valeur transigée de SONATEL le 20/11/2026 : ``2 988 573`` + ``270`` =
   ``2 988 573 270`` FCFA, confirmé par le TOTAL du compartiment et par
   volume x cours) sont rattachés à la ligne précédente.
5. **Contrôles internes.** variation vs cours, valeur vs volume x cours,
   rendement vs dividende / cours, sommes des volumes/valeurs vs lignes TOTAL,
   nombre de lignes vs nombre de sociétés cotées.
6. **Bulletins en anglais.** Quelques BOC (ex. 02/01/2025) sont publiés en
   anglais (virgule des milliers, point décimal, « 12 Sep 24 », rendement en
   fraction) : la langue est détectée et la tokenisation adaptée.

Règle du cours de clôture (colonne ``close``)
---------------------------------------------
* titre échangé : ``close`` = cours de clôture publié ;
* titre non coté (``NC``) ou suspendu (``SP``) : ``close`` = cours précédent
  publié (le dernier cours de référence connu à l'ouverture de la séance), à
  défaut le cours de référence. On n'utilise pas en priorité le cours de
  référence du jour car la BRVM y applique déjà les ajustements (détachement
  de dividende, division du nominal) valables pour la séance *suivante* ;
* exception : titre non coté dont la bourse a déplacé la référence avec une
  variation publiée non nulle et cohérente (``réf / préc. - 1 = variation``) :
  ``close`` = cours de référence (la valorisation du jour a réellement changé).

Statut (colonne ``status``) : ``"suspended"`` si ``SP``, ``"not_traded"`` si
``NC`` (ou cours sans volume), ``"traded"`` sinon.
"""

from __future__ import annotations

import datetime as dt
import gzip
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

__all__ = [
    "BocDay",
    "EQUITY_COLUMNS",
    "INDEX_COLUMNS",
    "ORDER_BOOK_COLUMNS",
    "Token",
    "parse_boc_file",
    "parse_boc_text",
    "parse_french_date",
    "parse_number",
    "read_boc_text",
    "tokenize",
    "warning_code",
]

# ---------------------------------------------------------------------------
# Schémas de sortie
# ---------------------------------------------------------------------------

EQUITY_COLUMNS: list[str] = [
    "date", "symbol", "name", "sector", "compartment", "prev_close", "open", "close",
    "change_pct", "volume", "value", "ref_price", "ytd_pct", "last_div_net",
    "last_div_date", "net_yield_pct", "per", "status", "ex_div", "flags", "warnings",
]
INDEX_COLUMNS: list[str] = [
    "date", "index", "level", "change_pct", "ytd_pct", "family", "base_date",
    "n_companies", "volume", "value", "per",
]
ORDER_BOOK_COLUMNS: list[str] = [
    "date", "symbol", "name", "bid_qty", "bid", "ask", "ask_qty", "ref_price",
    "bid_at_market", "ask_at_market",
]

# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

#: Mois français abrégés (tableaux) et complets (en-têtes), avec et sans accents.
_MONTHS: dict[str, int] = {
    "janv": 1, "jan": 1, "janvier": 1,
    "févr": 2, "fevr": 2, "fév": 2, "fev": 2, "février": 2, "fevrier": 2,
    "mars": 3, "mar": 3,
    "avr": 4, "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "août": 8, "aout": 8, "aoû": 8,
    "sept": 9, "sep": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "déc": 12, "dec": 12, "décembre": 12, "decembre": 12,
}
#: Mois anglais (BOC publiés en anglais).
_MONTHS_EN: dict[str, int] = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _alt(words: Iterable[str]) -> str:
    """Alternative regex, mots les plus longs d'abord."""
    return "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))


_MONTH_ALT = _alt(_MONTHS)
_MONTH_EN_ALT = _alt(_MONTHS_EN)
_WEEKDAYS = "lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche"

#: En-tête de page : « vendredi 20 novembre 2026 », « lundi 1er juin 2020 ».
_HEADER_DATE_RE = re.compile(
    rf"\b(?:{_WEEKDAYS})\s+(\d{{1,2}})(?:er)?\s+({_MONTH_ALT})\s+(\d{{4}})\b", re.IGNORECASE
)
#: Date longue (« Base = 100 au 02 janvier 2023 »).
_LONG_DATE_RE = re.compile(rf"\b(\d{{1,2}})(?:er)?\s+({_MONTH_ALT})\s+(\d{{4}})\b", re.IGNORECASE)
#: Date longue anglaise (« as of june 14, 1999 », « january 2,2025 »).
_LONG_DATE_EN_RE = re.compile(rf"\b({_MONTH_EN_ALT})\s+(\d{{1,2}})\s*,\s*(\d{{4}})\b", re.IGNORECASE)
#: Date de tableau : « 7-sept.-26 », « 23-mai-18 », « 9-janv.-18 ».
_TABLE_DATE = rf"(\d{{1,2}})\s?-\s?({_MONTH_ALT})\.?\s?-\s?(\d{{4}}|\d{{2}})"
_TABLE_DATE_RE = re.compile(_TABLE_DATE, re.IGNORECASE)
#: Date de tableau anglaise : « 12 Sep 24 ».
_TABLE_DATE_EN = rf"(\d{{1,2}})\s({_MONTH_EN_ALT})\.?\s(\d{{4}}|\d{{2}})"
_TABLE_DATE_EN_RE = re.compile(_TABLE_DATE_EN, re.IGNORECASE)
_SLASH_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})")


def _year2(yy: str) -> int:
    """Convertit une année sur 2 ou 4 chiffres (pivot 70 : 99 -> 1999, 26 -> 2026)."""
    y = int(yy)
    if len(yy) >= 4:
        return y
    return 1900 + y if y >= 70 else 2000 + y


def parse_french_date(text: str) -> dt.date | None:
    """Analyse une date de BOC : ``7-sept.-26``, ``1er juin 2020``, ``12/06/2018``, ``12 Sep 24``.

    Renvoie ``None`` si le texte n'est pas une date valide.
    """
    s = text.strip()
    try:
        m = _TABLE_DATE_RE.fullmatch(s)
        if m:
            return dt.date(_year2(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        m = _TABLE_DATE_EN_RE.fullmatch(s)
        if m:
            return dt.date(_year2(m.group(3)), _MONTHS_EN[m.group(2).lower()], int(m.group(1)))
        m = _SLASH_DATE_RE.fullmatch(s)
        if m:
            return dt.date(_year2(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = _LONG_DATE_RE.search(s)
        if m:
            return dt.date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        m = _LONG_DATE_EN_RE.search(s)
        if m:
            return dt.date(int(m.group(3)), _MONTHS_EN[m.group(1).lower()], int(m.group(2)))
    except (KeyError, ValueError):
        return None
    return None


# ---------------------------------------------------------------------------
# Nombres et tokenisation
# ---------------------------------------------------------------------------

#: Nombre français : milliers séparés par UNE espace, décimale virgule (point toléré).
#: Une virgule finale suivie d'un blanc est acceptée (décimales renvoyées à la ligne).
_NUM_FR = r"-?(?:(?:\d{1,3}(?:[ ]\d{3})+|\d+)(?:[,.]\d+|,(?=\s|$))?|[,.]\d+)"
#: Nombre anglais : milliers séparés par une virgule, décimale point ; une virgule
#: suivie de 1-2 chiffres reste une décimale (les BOC anglais mélangent les styles).
_NUM_EN = r"-?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+[.,]\d{1,2}(?!\d)|\d+(?:\.\d+)?|\.\d+)"
_MARK = r"\((?:d|V|\#|Val-T|Ex-[cd]|\*+)\)|\bNC\b|\bSP\b|\bND\b|\bEx-[cd]\b|\bVal\s?-?\s?T\b|\bMarch[ée]\b|(?<!\S)-(?!\S)"


def _token_re(num: str, date: str) -> re.Pattern[str]:
    """Expression maîtresse : date | pourcentage | nombre | marqueur | texte (dans cet ordre)."""
    return re.compile(
        rf"""
        (?P<date>(?<![\d/]){date}(?![\d])|(?<![\d/])\d{{1,2}}/\d{{1,2}}/(?:\d{{4}}|\d{{2}})(?![\d/]))
      | (?P<pct>(?<![\d,.]){num}\s?%)
      | (?P<num>(?<![\d,.]){num}(?![\d]))
      | (?P<mark>{_MARK})
      | (?P<text>\S+)
        """,
        re.IGNORECASE | re.VERBOSE,
    )


_TOKEN_RES: dict[str, re.Pattern[str]] = {
    "fr": _token_re(_NUM_FR, _TABLE_DATE),
    "en": _token_re(_NUM_EN, _TABLE_DATE_EN),
}


def parse_number(text: str, lang: str = "fr") -> float | None:
    """Convertit un nombre BOC en float.

    * ``lang="fr"`` : ``"12 737 890"``, ``"1 500,00"``, ``",92"``, ``"1 041,"`` ;
    * ``lang="en"`` : ``"10,082,387"``, ``"276.13"`` (et ``"114,56"`` = 114,56).

    Renvoie ``None`` pour un texte non numérique (``"-"``, ``"NC"``...).
    """
    s = text.strip().replace(" ", " ").replace("%", "").replace(" ", "")
    if not s or s in {"-", "–"}:
        return None
    if lang == "en" and re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", s):
        s = s.replace(",", "")
    s = s.replace(",", ".")
    if s.count(".") > 1:  # « 1.234.567 » : points de milliers
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_ob_price(text: str) -> float | None:
    """Prix du carnet d'ordres : la virgule y sépare les milliers (``"4,010"`` = 4010)."""
    s = text.strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", s):
        return float(s.replace(",", ""))
    return parse_number(s)


@dataclass(frozen=True)
class Token:
    """Jeton typé d'une ligne, avec sa position (colonnes de caractères)."""

    kind: str  # "num" | "pct" | "date" | "mark" | "text"
    text: str
    start: int
    end: int
    lang: str = "fr"

    @property
    def value(self) -> Any:
        """Valeur Python du jeton (float, date ou marqueur normalisé)."""
        if self.kind in ("num", "pct"):
            v = parse_number(self.text, self.lang)
            return v + 0.0 if v is not None else None  # « -0,00 % » -> 0.0
        if self.kind == "date":
            return parse_french_date(self.text)
        if self.kind == "mark":
            mark = self.text.upper().replace("É", "E")
            return "VAL-T" if re.fullmatch(r"VAL\s?-?\s?T", mark) else mark
        return self.text


def tokenize(segment: str, offset: int = 0, lang: str = "fr") -> list[Token]:
    """Découpe un segment de ligne en jetons typés (dates et % reconnus avant les nombres).

    ``offset`` est ajouté aux positions (position absolue dans la ligne).
    """
    out: list[Token] = []
    for m in _TOKEN_RES[lang].finditer(segment):
        kind = next(k for k in ("date", "pct", "num", "mark", "text") if m.group(k) is not None)
        out.append(Token(kind, m.group(0), m.start() + offset, m.end() + offset, lang))
    return out


def warning_code(warning: str) -> str:
    """Code d'un avertissement (``"change_mismatch: SNTS: ..."`` -> ``"change_mismatch"``)."""
    return warning.split(":", 1)[0].strip()


# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------


@dataclass
class BocDay:
    """Contenu structuré d'un BOC (une séance)."""

    date: dt.date | None
    equities: pd.DataFrame
    indices: pd.DataFrame
    market: dict[str, float | str | None]
    order_book: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Grammaire d'une ligne action
# ---------------------------------------------------------------------------

#: (nom de colonne, types acceptés, obligatoire) ; N=nombre, P=%, D=date, M=NC/SP.
_SLOTS_FR: list[tuple[str, str, bool]] = [
    ("prev_close", "N", True),
    ("open", "NM", True),
    ("close", "NM", True),
    ("change_pct", "P", True),
    ("volume", "N", False),
    ("value", "N", False),
    ("ref_price", "N", True),
    ("ytd_pct", "P", False),
    ("last_div_net", "N", False),
    ("last_div_date", "D", False),
    ("net_yield_pct", "P", False),
    ("per", "N", False),
]
#: En anglais, le rendement est imprimé en fraction sans « % » (0.08 = 8 %).
_SLOTS_EN = [(n, "PN" if n == "net_yield_pct" else t, r) for n, t, r in _SLOTS_FR]
#: BOC « historiques » (jusqu'à novembre 2017) : volume et valeur en tête, cours moyen,
#: écarts maximaux (seuils bas/haut), compartiment (« 1er »/« 2eme ») avant rendement et PER.
_SLOTS_LEGACY: list[tuple[str, str, bool]] = [
    ("volume", "N", False),
    ("value", "N", False),
    ("prev_close", "N", True),
    ("open", "NM", True),
    ("close", "NM", True),
    ("avg_price", "NM", False),
    ("change_pct", "P", False),
    ("ytd_pct", "P", False),
    ("ref_price", "N", True),
    ("low_limit", "N", False),
    ("high_limit", "N", False),
    ("last_div_net", "N", False),
    ("last_div_date", "D", False),
    ("net_yield_pct", "P", False),
    ("per", "N", False),
]
_SLOT_NAMES = [s[0] for s in _SLOTS_FR]
_KIND_CODE = {"num": "N", "pct": "P", "date": "D", "mark": "M"}
_PRICE_MARKS = {"NC", "SP"}
_EMPTY_MARKS = {"-", "ND"}  # cases vides / non disponibles
_MAX_ASSIGNMENTS = 5000


def _enumerate_assignments(types: list[str], slots: list[tuple[str, str, bool]]) -> list[tuple[list[int], int]]:
    """Énumère les affectations ordonnées jetons -> colonnes compatibles avec les types.

    Renvoie une liste de (indice de colonne par jeton, nb de colonnes obligatoires vides).
    """
    n = len(types)
    results: list[tuple[list[int], int]] = []

    def rec(ti: int, si: int, acc: list[int], missing: int) -> None:
        if len(results) >= _MAX_ASSIGNMENTS:
            return
        if ti == n:
            results.append((acc.copy(), missing + sum(1 for s in range(si, len(slots)) if slots[s][2])))
            return
        # Il doit rester assez de colonnes pour les jetons restants.
        for sj in range(si, len(slots) - (n - ti - 1)):
            if types[ti] in slots[sj][1]:
                acc.append(sj)
                rec(ti + 1, sj + 1, acc, missing + sum(1 for s in range(si, sj) if slots[s][2]))
                acc.pop()

    rec(0, 0, [], 0)
    return results


def _log_ratio(a: float | None, b: float | None) -> float:
    """|log(a/b)| (infini si l'un des deux est absent, nul ou négatif)."""
    if a is None or b is None or a <= 0 or b <= 0:
        return math.inf
    return abs(math.log(a / b))


def _plausibility_cost(vals: dict[str, Any]) -> float:
    """Coût de vraisemblance économique d'une affectation (0 = parfaitement cohérente)."""
    cost = 0.0
    prev, close, ref = vals.get("prev_close"), vals.get("close"), vals.get("ref_price")
    close_num = close if isinstance(close, float) else None
    open_num = vals.get("open") if isinstance(vals.get("open"), float) else None
    base = close_num or prev
    vol, value = vals.get("volume"), vals.get("value")
    # Volume et valeur vont par paire.
    if (vol is None) != (value is None):
        cost += 3.0
    if vol is not None and value is not None and base:
        if vol <= 0 or value < vol * 0.5:  # la valeur est (presque toujours) >> volume
            cost += 2.0
        lr = _log_ratio(value, vol * base)
        if lr > math.log(1.3):
            cost += min(3.0, lr)
    # Le cours de référence est proche du cours du jour (sauf ajustement exceptionnel).
    if ref is not None and base:
        lr = _log_ratio(ref, base)
        if lr > math.log(1.6):
            cost += 3.0
        elif lr > math.log(1.12):
            cost += 0.6
    # Cohérence précédent / ouverture / clôture.
    for p in (open_num, close_num):
        if p is not None and prev and _log_ratio(p, prev) > math.log(1.6):
            cost += 1.5
    # Rendement net = dividende / cours.
    div, yld = vals.get("last_div_net"), vals.get("net_yield_pct")
    if div is not None and yld is not None and base:
        implied = div / base * 100.0
        if not abs(implied - yld) <= max(0.15, 0.15 * abs(yld)):
            cost += 1.5
    if div is not None and vals.get("last_div_date") is None:
        cost += 0.5
        if base and div > 0.5 * base:
            # Dividende sans date valant plus de la moitié du cours : c'est presque
            # toujours une autre colonne (seuil de cotation mal imprimé, STAC 25/10/2017).
            cost += 2.0
    if vals.get("last_div_date") is not None and div is None:
        cost += 1.0
    per = vals.get("per")
    if per is not None and per < 0:
        cost += 0.3
    # BOC historiques : seuils de cotation ≈ référence -7,5 % / +7,5 %, cours moyen ≈ clôture.
    low, high = vals.get("low_limit"), vals.get("high_limit")
    if ref:
        if low is not None and not 0.80 <= low / ref <= 0.97:
            cost += 2.0
        if high is not None and not 1.03 <= high / ref <= 1.20:
            cost += 2.0
    avg = vals.get("avg_price")
    if isinstance(avg, float) and close_num and _log_ratio(avg, close_num) > math.log(1.1):
        cost += 1.0
    if isinstance(vals.get("open"), str) and vals.get("change_pct") is not None and vals.get("ytd_pct") is None:
        cost += 0.3  # non coté : la variation du jour est normalement vide
    return cost


@dataclass
class _RawRow:
    """Ligne action en cours d'analyse (avant affectation définitive)."""

    line_no: int
    page: int
    symbol: str
    name: str
    sector: str | None
    compartment: str | None
    group: str | None
    tokens: list[Token]
    marks: list[str]
    name_start: int
    sym_start: int
    data_start: int
    candidates: list[tuple[float, list[int], int]] = field(default_factory=list)
    choice: list[int] | None = None
    confident: bool = False
    overflow: list[Token] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pending_mark: str | None = None  # marqueur coupé en fin de ligne (« (Ex- » / « d) »)
    names: list[str] = field(default_factory=lambda: list(_SLOT_NAMES))
    line_text: str = ""


def _values_for(tokens: list[Token], assign: list[int], names: list[str] = _SLOT_NAMES) -> dict[str, Any]:
    """Valeurs des colonnes pour une affectation (``"NC"``/``"SP"`` pour ouv./clôt. non cotées)."""
    vals: dict[str, Any] = {}
    for tok, si in zip(tokens, assign):
        name = names[si]
        v = tok.value
        if name == "net_yield_pct" and tok.kind == "num" and v is not None:
            v = v * 100.0  # rendement imprimé en fraction (BOC anglais)
        vals[name] = v
    return vals


def _score_candidates(row: _RawRow, slots: list[tuple[str, str, bool]]) -> None:
    """Calcule et trie les affectations candidates d'une ligne (coût croissant)."""
    data = [t for t in row.tokens if t.kind in _KIND_CODE and not (t.kind == "mark" and t.value not in _PRICE_MARKS)]
    row.tokens = data
    row.names = [s[0] for s in slots]
    types = [_KIND_CODE[t.kind] for t in data]
    cands: list[tuple[float, list[int], int]] = []
    for assign, missing in _enumerate_assignments(types, slots):
        cands.append((4.0 * missing + _plausibility_cost(_values_for(data, assign, row.names)), assign, missing))
    if not cands:
        # Repli : un nombre coupé par une espace parasite (« 4 30 » pour 430, BOC 2017)
        # rend la ligne trop longue ; on recolle la première paire « a b » collée par une
        # seule espace qui rend une affectation possible.
        for k in range(len(data) - 1):
            a, b = data[k], data[k + 1]
            if a.kind == b.kind == "num" and b.start - a.end == 1 and "," not in a.text:
                merged = Token("num", f"{a.text}{b.text}".replace(" ", ""), a.start, b.end, a.lang)
                trial = [*data[:k], merged, *data[k + 2:]]
                ttypes = [_KIND_CODE[t.kind] for t in trial]
                for assign, missing in _enumerate_assignments(ttypes, slots):
                    cands.append((4.0 * missing + _plausibility_cost(_values_for(trial, assign, row.names)),
                                  assign, missing))
                if cands:
                    row.tokens = data = trial
                    row.warnings.append(f"split_number_joined: {row.symbol}: « {a.text} {b.text} »")
                    break
    cands.sort(key=lambda c: c[0])
    row.candidates = cands
    if cands:
        row.choice = cands[0][1]
        margin = cands[1][0] - cands[0][0] if len(cands) > 1 else math.inf
        row.confident = margin >= 1.0 and cands[0][2] == 0


#: Écart (caractères) au-delà duquel un jeton est jugé hors de sa colonne.
_POSITION_OFF = 8


def _position_override(r: "_RawRow", choice: list[int], meds: dict[str, float]) -> list[int]:
    """Corrige une affectation dont les jetons sont nettement hors de leurs colonnes.

    Cas typique : première cotation au format historique (ECOC 12/12/2017, NSBC
    24/10/2017) : la colonne « cours précédent » est vide, mais l'affectation sans
    colonne manquante décale tous les cours d'une colonne vers la gauche (cours moyen
    pris pour la clôture). Si un jeton de l'affectation retenue est à plus de
    ``_POSITION_OFF`` caractères de la colonne médiane apprise sur la page, toutes
    les affectations sont renotées par coût + écart de position / 3.
    """
    if not meds or len(r.candidates) < 2:
        return choice
    devs = [abs(t.end - meds[r.names[si]]) for t, si in zip(r.tokens, choice) if r.names[si] in meds]
    if not devs or max(devs) <= _POSITION_OFF:
        return choice
    cost0 = next(c for c, a, _ in r.candidates if a == choice)
    pc0 = _position_cost(r.tokens, choice, meds, r.names) or 0.0
    best = (cost0 + pc0 / 3.0, choice)
    for cost, assign, _ in r.candidates:
        names = {r.names[si] for si in assign}
        if not names <= set(meds):
            continue
        pc = _position_cost(r.tokens, assign, meds, r.names)
        if pc is not None and cost + pc / 3.0 < best[0] - 2.0:
            best = (cost + pc / 3.0, assign)
    if best[1] is not choice:
        r.warnings.append(f"position_override: {r.symbol}: colonnes réaffectées d'après leur position")
    return best[1]


def _anchor_end(tokens: list[Token], assign: list[int], names: list[str] = _SLOT_NAMES) -> int | None:
    """Fin du jeton « cours précédent » (ancre des positions relatives, toujours présent)."""
    return next((t.end for t, si in zip(tokens, assign) if names[si] == "prev_close"), None)


def _position_cost(tokens: list[Token], assign: list[int], medians: dict[str, float],
                   names: list[str] = _SLOT_NAMES) -> float | None:
    """Somme des écarts (en caractères) entre la fin des jetons et la colonne médiane apprise."""
    diffs = [abs(t.end - medians[names[si]]) for t, si in zip(tokens, assign) if names[si] in medians]
    return sum(diffs) if diffs else None


# ---------------------------------------------------------------------------
# Expressions de structure
# ---------------------------------------------------------------------------

_SECTOR_CODES = {"AGR", "AUT", "DIS", "FIN", "IND", "SPU", "TRP", "CB", "CD", "ENE", "TEL"}
#: Libellés de groupes « SECTEUR - ... » (BOC 2017-2022) -> code secteur des BOC 2023-2024.
_SECTOR_NAME_TO_CODE = {
    "INDUSTRIE": "IND",
    "SERVICES PUBLICS": "SPU",
    "FINANCES": "FIN",
    "TRANSPORT": "TRP",
    "AGRICULTURE": "AGR",
    "DISTRIBUTION": "DIS",
    "AUTRES SECTEURS": "AUT",
    # Classification 2025 (au cas où elle apparaîtrait en en-tête de groupe)
    "TELECOMMUNICATIONS": "TEL",
    "CONSOMMATION DISCRETIONNAIRE": "CD",
    "SERVICES FINANCIERS": "FIN",
    "CONSOMMATION DE BASE": "CB",
    "INDUSTRIELS": "IND",
    "ENERGIE": "ENE",
}
#: Libellés anglais (BOC publiés en anglais) -> libellés français des BOC habituels,
#: pour que les séries (secteurs, indices sectoriels base 1999) restent continues.
_EN_SECTOR_NAMES = {
    "INDUSTRY": "INDUSTRIE",
    "PUBLIC UTILITIES": "SERVICES PUBLICS",
    "FINANCIAL SERVICES": "FINANCES",
    "FINANCE": "FINANCES",
    "TRANSPORTATION": "TRANSPORT",
    "TRANSPORT": "TRANSPORT",
    "AGRICULTURE": "AGRICULTURE",
    "DISTRIBUTION": "DISTRIBUTION",
    "OTHER SECTORS": "AUTRES SECTEURS",
    "MISC.": "AUTRES SECTEURS",
    "MISC": "AUTRES SECTEURS",
    "SMALL CAP": "PETITES CAPITALISATIONS",
}
_NOT_SYMBOLS = {"TOTAL", "SECTEUR", "COMPARTIMENT", "CODE", "SECT", "ACT", "LIBEL", "GRO", "UPE", "BRVM", "AUTRES"}

_ROW_RE = re.compile(r"^(?P<lead>\s*)(?:(?P<sect>[A-Z]{2,3})\s+)?(?P<sym>[A-Z][A-Z0-9]{2,6})\s{2,}(?P<rest>\S.*)$")
_NAME_END_RE = re.compile(r"\s{2,}(?=(?:-?\d|[,.]\d|\((?:d|V|#|Val-T|Ex-[cd]|\*+)\)|NC\b|SP\b))")
_GROUP_RE = re.compile(r"^\s*(?P<name>(?:SECTEUR\s*-\s*)?[A-ZÉÈ][A-ZÉÈ'. \-]+?)\s{2,}(?P<level>-?\d[\d ,.]*)\s+points\b")
_EQ_TABLE_END_RE = re.compile(r"TOTAL\s*-\s*(?:MARCH[EÉ]\s+DES\s+ACTIONS|EQUITIES\s+MARKET)", re.IGNORECASE)
_EQ_TABLE_ALT_END_RE = re.compile(r"MARCH[EÉ]\s+DES\s+DROITS|OBLIGATIONS\s+CLASSIQUES|OBLIGATIONS\s+D'ETAT|RIGHTS\s+MARKET", re.IGNORECASE)
_TOTAL_LINE_RE = re.compile(r"^\s*TOTAL\s{2,}(?P<rest>\d.*)$")
_CONT_SECTOR_RE = re.compile(r"^(?P<lead>\s{0,3})(?P<code>[A-Z]{1,3})(?=\s|$)")


#: Marqueur imprimé dans la zone du nom (casse quelconque, collé ou non au nom).
_NAME_MARK_RE = re.compile(r"\s*\((d|v|\#|-|val\s?-?\s?t|ex-?[cd]|ex-?div(?:idende)?)\)", re.IGNORECASE)


def _normalize_mark(mark: str) -> str:
    """Forme canonique d'un marqueur : ``(d)`` -> ``(D)``, ``(ex-div)`` -> ``(D)``.

    Légende des BOC : ``(d)`` ex-dividende, ``(V)`` variation calculée sur le cours de
    référence, ``Ex-c`` ex-coupon, ``Ex-d`` ex-droit, ``(#)`` division / opération sur
    le nominal, ``Val-T`` valeur théorique.
    """
    m = mark.upper().replace(" ", "")
    if re.fullmatch(r"\(EX-?DIV(?:IDENDE)?\)", m):
        return "(D)"
    if re.fullmatch(r"\(VAL-?T\)", m):
        return "(VAL-T)"
    m = re.sub(r"^\(EX(?=[CD]\)$)", "(EX-", m)
    return m


def _extract_name_marks(name: str) -> tuple[str, list[str]]:
    """Retire les marqueurs de la zone du nom ; ``(-)`` (case vide) n'est pas conservé."""
    marks = [_normalize_mark(f"({m.group(1)})") for m in _NAME_MARK_RE.finditer(name)]
    if not marks:
        return name, []
    return _NAME_MARK_RE.sub(" ", name).rstrip(), [m for m in marks if m != "(-)"]


def _normalize_name(name: str) -> str:
    """Nettoie un libellé : espaces multiples, apostrophes doublées (``D''IVOIRE``)."""
    s = re.sub(r"'{2,}", "'", name.replace("’", "'"))
    return re.sub(r"\s+", " ", s).strip()


def _pages(lines: list[str]) -> list[int]:
    """Numéro de page (0-based) de chaque ligne, d'après les sauts de page ``\\f``."""
    out: list[int] = []
    page = 0
    for ln in lines:
        page += ln.count("\f")
        out.append(page)
    return out


# ---------------------------------------------------------------------------
# Analyse des actions
# ---------------------------------------------------------------------------


def _find_equity_region(lines: list[str], warnings: list[str]) -> tuple[int, int]:
    """Bornes [début, fin) du tableau des actions (fin = ligne « TOTAL - MARCHE DES ACTIONS »)."""
    start = None
    for i, ln in enumerate(lines):
        if re.search(r"\bSymboles?\b|\bSymbol\b", ln) and re.search(r"\bTitre\b|\bEquity\b|Act\.|Précédent|Variation", ln):
            around = "\n".join(lines[max(0, i - 4): i + 4])
            if re.search(r"r[ée]siduelle|Achat\s*/\s*Vente|Remaining", around, re.IGNORECASE):
                continue  # en-tête du carnet d'ordres (parfois placé avant la cote)
            start = i
            break
    if start is None:
        # Repli : première ligne de groupe « SECTEUR - ... points » / « COMPARTIMENT ... points ».
        start = next((max(0, i - 1) for i, ln in enumerate(lines) if _GROUP_RE.match(ln)), None)
    if start is None:
        warnings.append("no_equity_table: tableau des actions introuvable")
        return 0, 0
    for j in range(start, len(lines)):
        if _EQ_TABLE_END_RE.search(lines[j]):
            return start, j
    for j in range(start, len(lines)):
        if _EQ_TABLE_ALT_END_RE.search(lines[j]):
            warnings.append("equity_table_end_missing: ligne « TOTAL - MARCHE DES ACTIONS » absente")
            return start, j
    warnings.append("equity_table_end_missing: fin du tableau des actions introuvable")
    return start, len(lines)


def _is_row_line(line: str, lang: str = "fr") -> re.Match[str] | None:
    """Reconnaît une ligne action : symbole + nom + données (un %, NC/SP, ou >= 4 nombres)."""
    m = _ROW_RE.match(line)
    if not m:
        return None
    if m.group("sym") in _NOT_SYMBOLS or m.group("sect") == "TOTAL":
        return None
    rest = m.group("rest")
    if "%" in rest or re.search(r"\b(NC|SP)\b", rest):
        return m
    # Première cotation : ni cours précédent ni variation, mais des cours et volumes.
    ne = _NAME_END_RE.search(rest)
    if ne and sum(1 for t in tokenize(rest[ne.end():], 0, lang) if t.kind == "num") >= 4:
        return m
    return None


#: Fragment de nombre renvoyé à la ligne suivante : groupe de milliers (« 270 »),
#: décimales après une virgule finale (« 59 ») ou dernier groupe + décimales
#: (« 236,32 » sous « 1 » : PER 1 236,32, BNBC 02/01/2026).
_OVERFLOW_FRAG = r"\d{1,3}|\d{3},\d{1,3}"


def _parse_continuation(
    line: str, row: _RawRow, lang: str
) -> tuple[bool, str | None, str | None, list[Token]]:
    """Analyse une ligne candidate de continuation de ``row``.

    Renvoie (est_continuation, code_secteur, texte_nom, jetons_débordants). La fin
    d'un marqueur coupé (« d) » après « (Ex- ») complète ``row.marks``.
    """
    if not line.strip() or _is_row_line(line, lang) or _GROUP_RE.match(line) or _TOTAL_LINE_RE.match(line):
        return False, None, None, []
    if re.match(r"^\s*TOTAL\b", line) or _HEADER_DATE_RE.search(line):
        return False, None, None, []
    if row.pending_mark:
        frag = re.search(r"(?<=\s)([A-Za-z]{1,3})\)(?=\s|$)", line)
        if frag and frag.start() < row.data_start:
            row.marks.append(_normalize_mark(f"({row.pending_mark}{frag.group(1)})"))
            row.pending_mark = None
            line = line[: frag.start()] + " " * (frag.end() - frag.start()) + line[frag.end():]
    code = truncated = None
    rest_start = 0
    m = _CONT_SECTOR_RE.match(line)
    if m and m.end("code") <= row.sym_start + 1 and m.group("code") in _SECTOR_CODES:
        code = m.group("code")
        rest_start = m.end("code")
    elif (m and m.end("code") <= row.sym_start + 1
          and any(c.startswith(m.group("code")) for c in _SECTOR_CODES)):
        # Code secteur tronqué par pdftotext (« C » pour CB/CD, 10/02/2025) : consommé
        # pour récupérer la fin du nom ; le secteur sera complété dans le panel.
        rest_start = m.end("code")
        truncated = m.group("code")
    name_parts: list[str] = []
    overflow: list[Token] = []
    for t in tokenize(line[rest_start:], rest_start, lang):
        if t.start >= row.data_start - 1 and t.kind == "num" and re.fullmatch(_OVERFLOW_FRAG, t.text):
            overflow.append(t)
        elif row.name_start - 6 <= t.start < row.data_start - 1:
            name_parts.append(t.text)
        else:
            # Contenu inattendu (texte libre...) : ce n'est pas une continuation.
            return False, None, None, []
    if code is None and truncated is None and not name_parts:
        if not overflow:
            return False, None, None, []
        # Ligne de chiffres seuls : uniquement s'ils sont alignés sous une colonne de la
        # ligne (sinon c'est par exemple un numéro de page).
        ends = [t.end for t in row.tokens if t.kind == "num"]
        if not all(any(abs(ov.end - e) <= 3 for e in ends) for ov in overflow):
            return False, None, None, []
    if name_parts:
        # Le texte de nom doit commencer à la colonne du nom.
        first = re.search(r"\S", line[rest_start:])
        pos = (first.start() + rest_start) if first else 0
        if abs(pos - row.name_start) > 6:
            return False, None, None, []
    if truncated:
        row.warnings.append(f"truncated_sector: {row.symbol}: code « {truncated} »")
    return True, code, " ".join(name_parts) or None, overflow


def _drop_garbled_cells(toks: list[Token]) -> tuple[list[Token], str]:
    """Retire les cellules brouillées par pdftotext : chiffre(s) + virgule isolée.

    Exemple (LNBB, 02/06/2025) : PER imprimé « 1 , » (chiffres perdus) ; sans ce
    filtre, « 1 » serait lu comme un PER de 1,00. Le nombre voisin (à une ou deux
    espaces) d'une virgule ou d'un point isolé est supprimé avec elle.
    """
    drop: set[int] = set()
    for k, t in enumerate(toks):
        if t.kind != "text" or not re.fullmatch(r"[,.]+", t.text):
            continue
        drop.add(k)
        for j in (k - 1, k + 1):
            if 0 <= j < len(toks) and toks[j].kind == "num":
                gap = t.start - toks[j].end if j < k else toks[j].start - t.end
                if gap <= 2:
                    drop.add(j)
    if not drop:
        return toks, ""
    text = " ".join(toks[k].text for k in sorted(drop))
    return [t for k, t in enumerate(toks) if k not in drop], text


def _merge_split_groups(row: _RawRow) -> None:
    """Recolle un nombre dont le dernier groupe de milliers est coupé entre deux lignes.

    Exemple (ORGT, 24/08/2022) : ``25 316 630 27`` en fin de colonne, ``5`` sur la
    ligne suivante -> ``25 316 630 275``. Le fragment court (1-2 chiffres) doit être
    séparé du nombre par une seule espace et le complément aligné juste dessous.
    """
    for ov in list(row.overflow):
        toks = row.tokens
        for k in range(len(toks) - 1):
            a, b = toks[k], toks[k + 1]
            if not (a.kind == "num" and b.kind == "num" and re.fullmatch(r"\d{1,2}", b.text)):
                continue
            if b.start - a.end != 1 or " " not in a.text or len(b.text) + len(ov.text) != 3:
                continue
            if not (b.start - 1 <= ov.start <= b.end + 2):
                continue
            merged = Token("num", f"{a.text} {b.text}{ov.text}", a.start, max(b.end, ov.end), a.lang)
            row.tokens = [*toks[:k], merged, *toks[k + 2:]]
            row.overflow.remove(ov)
            row.warnings.append(f"wrapped_digits_joined: {row.symbol}: {a.text} {b.text} + {ov.text}")
            break


def _apply_overflow(row: _RawRow, vals: dict[str, Any], tok_by_slot: dict[str, Token]) -> None:
    """Rattache les chiffres débordants (ligne suivante) à la colonne située au-dessus.

    Deux cas observés : un groupe de milliers renvoyé à la ligne (``2 988 573`` /
    ``270`` sous la valeur transigée) et des décimales renvoyées après une virgule
    finale (``1 041,`` / ``59`` sous le PER).
    """
    for ov in row.overflow:
        best: tuple[int, str, Token] | None = None
        for slot, t in tok_by_slot.items():
            if t.kind != "num":
                continue
            d = abs(ov.end - t.end)
            if (ov.start <= t.end and ov.end >= t.start) or d <= 3:
                if best is None or d < best[0]:
                    best = (d, slot, t)
        if best is None:
            row.warnings.append(f"orphan_digits: {row.symbol}: chiffres « {ov.text} » non rattachés")
            continue
        _, slot, t = best
        old = vals.get(slot)
        if t.text.endswith(",") and ov.text.isdigit():
            new = parse_number(t.text + ov.text, t.lang)  # décimales renvoyées à la ligne
        elif (t.lang == "fr" and re.fullmatch(r"-?\d{1,3}(?: \d{3})*", t.text)
              and (re.fullmatch(r"\d{3},\d+", ov.text)
                   or (len(ov.text) == 3 and slot in ("volume", "value", "per")))):
            # Groupe de milliers renvoyé (« 2 988 573 » + « 270 »), éventuellement avec
            # ses décimales (PER « 1 » + « 236,32 »).
            new = parse_number(t.text + " " + ov.text)
        else:
            row.warnings.append(f"orphan_digits: {row.symbol}: « {ov.text} » sous {slot}")
            continue
        price = vals["close"] if isinstance(vals.get("close"), float) else vals.get("prev_close")
        ok = new is not None
        if ok and slot == "value" and vals.get("volume") and price:
            ok = _log_ratio(new, vals["volume"] * price) < _log_ratio(old, vals["volume"] * price)
        if ok:
            vals[slot] = new
            row.warnings.append(f"wrapped_digits_joined: {row.symbol}: {slot} {t.text} + {ov.text}")
        else:
            row.warnings.append(f"orphan_digits: {row.symbol}: « {ov.text} » incohérent avec {slot}")


def _validate_row(row: _RawRow, rec: dict[str, Any]) -> None:
    """Contrôles internes d'une ligne action (ajoute des avertissements)."""
    sym = row.symbol
    prev, close, chg = rec["prev_close"], rec["close"], rec["change_pct"]
    traded = rec["status"] == "traded"
    # (V) : la variation est calculée sur le cours de référence ajusté, pas sur le
    # cours précédent publié -> pas de contrôle possible sur la seule ligne.
    if prev and close and chg is not None and traded and "(V)" not in row.marks:
        implied = (close / prev - 1.0) * 100.0
        if abs(implied - chg) > max(0.02, 0.006 * abs(chg)):
            div = rec["last_div_net"]
            # Jour de détachement sans marqueur (BOC 2021-2022) : cours précédent publié non
            # ajusté, variation calculée sur la référence ajustée (précédent - dividende,
            # arrondie au pas de cotation).
            adj = (close / (prev - div) - 1.0) * 100.0 if div and prev > div else math.inf
            if abs(adj - chg) <= max(0.3, 0.05 * abs(chg)):
                row.warnings.append(f"change_vs_adjusted_ref: {sym}: variation sur référence ex-dividende")
            else:
                row.warnings.append(
                    f"change_mismatch: {sym}: {prev:g}->{close:g} = {implied:.2f}% vs {chg:.2f}% publié")
    if not traded and chg not in (None, 0.0):
        if close == rec["ref_price"] and close != prev:
            row.warnings.append(f"untraded_ref_change: {sym}: référence déplacée sans cotation ({chg}%)")
        else:
            row.warnings.append(f"change_on_untraded: {sym}: variation {chg}% sans cotation")
    vol, value = rec["volume"], rec["value"]
    if traded and vol and value:
        prices = [p for p in (rec["open"], close, prev) if p]
        lo, hi = min(prices), max(prices)
        avg = value / vol
        if not (lo * 0.85 <= avg <= hi * 1.15):
            row.warnings.append(f"value_volume_mismatch: {sym}: valeur/volume = {avg:.1f} hors [{lo:g}, {hi:g}]")
    if isinstance(close, float) and rec["status"] == "not_traded" and rec["open"] is not None and not vol:
        row.warnings.append(f"close_without_volume: {sym}: cours publié sans volume")
    div, yld = rec["last_div_net"], rec["net_yield_pct"]
    # Rendement publié calculé sur le cours du jour (ou de référence) : on accepte
    # le plus proche des deux (ils diffèrent les jours de détachement).
    prices = [p for p in (close, rec["ref_price"], prev) if p]
    if div is not None and yld is not None and prices and "(*)" not in row.marks:
        implied = min((div / p * 100.0 for p in prices), key=lambda x: abs(x - yld))
        # Dividende parfois imprimé arrondi à l'unité (ETIT 2018 : « 1 » pour 1,21).
        rounding = 0.5 / min(prices) * 100.0 if float(div).is_integer() else 0.0
        if abs(implied - yld) > max(0.10, 0.04 * abs(yld)) + rounding:
            row.warnings.append(f"yield_mismatch: {sym}: {div:g}/{prices[0]:g} = {implied:.2f}% vs {yld:.2f}% publié")
    if prev is None and chg is None and vol:
        row.warnings.append(f"first_listing: {sym}: pas de cours précédent (première cotation ?)")
    elif prev is None:
        row.warnings.append(f"missing_prev_close: {sym}")
    if rec["ref_price"] is None:
        row.warnings.append(f"missing_ref_price: {sym}")
    if rec["sector"] is None:
        row.warnings.append(f"missing_sector: {sym}")


def _build_record(r: _RawRow, vals: dict[str, Any], day: dt.date | None, yield_from_fraction: bool) -> dict[str, Any]:
    """Construit l'enregistrement final (statut, règle du cours de clôture)."""
    open_v, close_v = vals.get("open"), vals.get("close")
    marks = {v for v in (open_v, close_v) if isinstance(v, str)}
    printed_close = close_v if isinstance(close_v, float) else None
    if "SP" in marks:
        status = "suspended"
    elif "NC" in marks or printed_close is None or not (vals.get("volume") or 0) > 0:
        status = "not_traded"
    else:
        status = "traded"
    prev, ref, chg = vals.get("prev_close"), vals.get("ref_price"), vals.get("change_pct")
    close: float | None
    if printed_close is not None:
        close = printed_close
    elif prev is not None and ref is not None and chg and abs((ref / prev - 1.0) * 100.0 - chg) <= 0.05:
        # Non coté mais référence déplacée par la bourse, variation publiée cohérente
        # (ex. SAFC 09/01/2019 : 215 -> 210, -2,33 %) : la valorisation du jour est la référence.
        close = ref
    else:
        close = prev if prev is not None else ref
    div, yld = vals.get("last_div_net"), vals.get("net_yield_pct")
    if yield_from_fraction and div is not None and close:
        # Rendement imprimé en fraction arrondie (0.08) : on le recalcule (DNPA / cours).
        yld = round(div / close * 100.0, 2)
    div_date = vals.get("last_div_date")
    return {
        "date": pd.Timestamp(day) if day else pd.NaT,
        "symbol": r.symbol,
        "name": _normalize_name(re.sub(r"\(\*+\)", "", r.name)),
        "sector": r.sector,
        "compartment": r.compartment,
        "prev_close": prev,
        "open": open_v if isinstance(open_v, float) else None,
        "close": close,
        "change_pct": vals.get("change_pct"),
        "volume": vals.get("volume"),
        "value": vals.get("value"),
        "ref_price": ref,
        "ytd_pct": vals.get("ytd_pct"),
        "last_div_net": div,
        "last_div_date": pd.Timestamp(div_date) if div_date else pd.NaT,
        "net_yield_pct": yld,
        "per": vals.get("per"),
        "status": status,
        "ex_div": "(D)" in r.marks,
        "flags": " ".join(sorted(set(r.marks))),
    }


def _is_integer_token(tok: Token) -> bool:
    """Nombre entier (volume, valeur) : sans décimales (« 10,66 » / « 10.66 » = PER)."""
    return tok.kind == "num" and ("." if tok.lang == "en" else ",") not in tok.text


def _read_group_total(lines: list[str], i: int, end: int, lang: str) -> tuple[list[float], int]:
    """Volume et valeur d'une ligne « TOTAL » de groupe ; renvoie (valeurs, ligne suivante).

    * valeurs sur la ligne suivante (« TOTAL » seul, BOC 2017-2019) ;
    * groupe de milliers renvoyé à la ligne (« 13 174 088 » / « 055 », 28/10/2026) ;
    * PER du groupe en fin de ligne, ou seul sur la ligne (« 10.66 ») : ignoré.
    """
    def clean(k: int) -> str:
        return lines[k].replace("\f", " ") if k < end else ""

    line = clean(i)
    m = _TOTAL_LINE_RE.match(line)
    toks = tokenize(m.group("rest"), m.start("rest"), lang) if m else []
    nxt = i + 1
    if not m:
        # « TOTAL » seul : valeurs éventuelles sur la prochaine ligne non vide.
        k = nxt
        while k < min(end, i + 3) and not clean(k).strip():
            k += 1
        cand = tokenize(clean(k), 0, lang) if k < end else []
        if cand and all(tk.kind == "num" for tk in cand) and not _is_row_line(clean(k), lang):
            toks, nxt = cand, k + 1
    nums = [tk for tk in toks if _is_integer_token(tk)]
    nums, joined = _join_wrapped_groups(nums, clean(nxt), lang)
    return [tk.value for tk in nums], nxt + joined


def _join_wrapped_groups(nums: list[Token], next_line: str, lang: str) -> tuple[list[Token], bool]:
    """Recolle un groupe de milliers renvoyé sous un nombre (« 355 678 » / « 925 »).

    ``next_line`` ne doit contenir que des groupes de 3 chiffres alignés (à 3 caractères
    près) sous la fin d'un des nombres. Renvoie (nombres, ligne consommée ?).
    """
    if not nums or lang != "fr":
        return nums, False
    ov = tokenize(next_line, 0, lang)
    if not ov or not all(tk.kind == "num" and re.fullmatch(r"\d{3}", tk.text) for tk in ov):
        return nums, False
    out = list(nums)
    used = False
    for o in ov:
        k = next((k for k, n in enumerate(out) if abs(n.end - o.end) <= 3), None)
        if k is not None:
            out[k] = Token("num", f"{out[k].text} {o.text}", out[k].start, o.end, out[k].lang)
            used = True
    return out, used


def _parse_equities(
    lines: list[str], pages: list[int], day: dt.date | None, lang: str, warnings: list[str]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Analyse le tableau des actions. Renvoie (DataFrame, totaux publiés)."""
    start, end = _find_equity_region(lines, warnings)
    legacy = any(re.search(r"Ecarts\s+maximaux|\bMoy\.", ln) for ln in lines[start:start + 12])
    slots = _SLOTS_LEGACY if legacy else (_SLOTS_EN if lang == "en" else _SLOTS_FR)
    group_indices: list[dict[str, Any]] = []
    rows: list[_RawRow] = []
    group_totals: list[tuple[str | None, float | None, float | None, list[_RawRow]]] = []
    totals: dict[str, Any] = {}
    sector: str | None = None
    compartment: str | None = None
    group: str | None = None
    group_rows: list[_RawRow] = []
    i = start
    while i < end:
        line = lines[i].replace("\f", " ")
        g = _GROUP_RE.match(line)
        if g:
            gname = re.sub(r"^SECTEUR\s*-\s*", "", _normalize_name(g.group("name")))
            gname = re.sub(r"\s*-\s*SECTOR$", "", gname)  # BOC anglais : « INDUSTRY - SECTOR »
            gname = _EN_SECTOR_NAMES.get(gname, gname)
            group, group_rows = gname, []
            gpct = [tk for tk in tokenize(line[g.end("level"):], 0, lang) if tk.kind == "pct"]
            group_indices.append({"name": gname, "level": parse_number(g.group("level"), lang),
                                  "change_pct": gpct[0].value if gpct else None})
            cm = re.match(r"^(?:COMPARTIMENT|BRVM)[\s-]+(PRESTIGE|PRINCIPAL)$", gname)
            if cm or gname.startswith("COMPARTIMENT"):
                # « COMPARTIMENT PRESTIGE » (ou « BRVM PRESTIGE » le 02/01/2023)
                compartment, sector = (cm.group(1) if cm else gname.replace("COMPARTIMENT", "").strip() or None), None
                group_indices[-1]["name"] = f"COMPARTIMENT {compartment}"
            else:
                # BOC 2017-2022 : pas de compartiment dans le tableau ; le groupe est le
                # secteur historique (contrat docs/ARCHITECTURE.md : compartment = secteur
                # historique, sector = code AGR/DIS/FIN/IND/SPU/TRP/AUT).
                compartment, sector = gname, _SECTOR_NAME_TO_CODE.get(gname, gname)
            i += 1
            continue
        t = _TOTAL_LINE_RE.match(line)
        if t or re.match(r"^\s*TOTAL\s*$", line):
            nums, i = _read_group_total(lines, i, end, lang)
            group_totals.append((group, nums[0] if nums else None,
                                 nums[1] if len(nums) > 1 else None, list(group_rows)))
            group_rows = []
            continue
        m = _is_row_line(line, lang)
        if not m:
            i += 1
            continue
        rest, rest_off = m.group("rest"), m.start("rest")
        ne = _NAME_END_RE.search(rest)
        if ne is None:
            warnings.append(f"unparsed_row: ligne {i + 1}: {line.strip()[:80]}")
            i += 1
            continue
        data_off = rest_off + ne.end()
        data_line = line
        if legacy:  # compartiment « 1er » / « 2eme » entre dividende et rendement : effacé
            data_line = re.sub(r"(?<=\s)(?:1er|2[eè]me|2e|3[eè]me|3e)(?=\s|$)",
                               lambda mm: " " * len(mm.group(0)) if mm.start() >= data_off else mm.group(0), line)
        toks = tokenize(data_line[data_off:], data_off, lang)
        toks, garbled = _drop_garbled_cells(toks)
        row = _RawRow(
            line_no=i, page=pages[i], symbol=m.group("sym"), name=rest[: ne.start()],
            sector=m.group("sect") or sector, compartment=compartment, group=group, tokens=toks,
            marks=[tk.value for tk in toks if tk.kind == "mark" and tk.value not in _PRICE_MARKS | _EMPTY_MARKS],
            name_start=rest_off, sym_start=m.start("sym"), data_start=data_off,
        )
        if re.search(r"\(\*+\)", row.name):
            row.marks.append("(*)")  # renvoi en légende (ex. dividendes cumulés de FILTISAC 2017)
        frag = re.search(r"\s*\((Ex-?|Val-?)\s*$", row.name, re.IGNORECASE)
        if frag:  # marqueur coupé en fin de nom : « SAFCA CI  (Ex- » + « d) » dessous
            row.name, row.pending_mark = row.name[: frag.start()], frag.group(1)
        if garbled:
            row.warnings.append(f"garbled_cell: {row.symbol}: « {garbled} » illisible, ignoré")
        stray = [tk for tk in toks if tk.kind == "text"]
        if stray:
            row.warnings.append(f"stray_text: {row.symbol}: {' '.join(tk.text for tk in stray)[:40]}")
        # Lignes de continuation (nom, code secteur, chiffres débordants).
        j = i + 1
        while j < min(end, i + 3):
            is_cont, ccode, ctext, ov = _parse_continuation(lines[j].replace("\f", " "), row, lang)
            if not is_cont:
                break
            if ccode and not m.group("sect"):
                row.sector = ccode
            if ctext:
                row.name = f"{row.name} {ctext}"
            row.overflow.extend(ov)
            j += 1
        # Marqueurs collés au nom (« AFRICA GLOBAL LOGISTICS (d) » / « CI »,
        # « ECOBANK COTE D'IVOIRE(#) », « BANK OF AFRICA BF   (v) ») : retirés du nom.
        row.name, name_marks = _extract_name_marks(row.name)
        row.marks.extend(name_marks)
        if row.overflow:
            _merge_split_groups(row)
        _score_candidates(row, slots)
        rows.append(row)
        group_rows.append(row)
        i = j

    # Apprentissage des colonnes sur les lignes non ambiguës, page par page.
    per_page: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.confident and r.choice is not None:
            for tok, si in zip(r.tokens, r.choice):
                per_page[r.page][r.names[si]].append(tok.end)
    page_medians = {p: {k: statistics.median(v) for k, v in d.items() if v} for p, d in per_page.items()}
    # Repli (ligne seule sur sa page) : positions relatives à la colonne « variation du
    # jour », apprises sur tout le document (insensibles au décalage d'une page).
    rel: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r.confident and r.choice is not None:
            anchor = _anchor_end(r.tokens, r.choice, r.names)
            if anchor is not None:
                for tok, si in zip(r.tokens, r.choice):
                    rel[r.names[si]].append(tok.end - anchor)
    rel_medians = {k: statistics.median(v) for k, v in rel.items() if v}

    records: list[dict[str, Any]] = []
    rec_by_row: dict[int, dict[str, Any]] = {}
    for r in rows:
        if not r.candidates:
            warnings.append(f"unparsed_row: {r.symbol}: aucun découpage possible")
            continue
        if not r.confident and len(r.candidates) > 1:
            # Départage des affectations proches par la position des colonnes.
            meds = page_medians.get(r.page) or {}
            best0 = r.candidates[0][0]
            close_cands = [c for c in r.candidates if c[0] <= best0 + 1.0]
            # Les colonnes à départager doivent être connues sur la page, sinon repli relatif.
            needed = {r.names[si] for _, a, _ in close_cands for si in a}
            if not needed <= set(meds):
                anchor = _anchor_end(r.tokens, close_cands[0][1], r.names)
                if anchor is not None and needed <= set(rel_medians):
                    meds = {k: v + anchor for k, v in rel_medians.items()}
            scored = []
            for cost, assign, _ in close_cands:
                pc = _position_cost(r.tokens, assign, meds, r.names)
                scored.append((cost + (pc / 3.0 if pc is not None else 0.0), assign, pc))
            scored.sort(key=lambda x: x[0])
            r.choice = scored[0][1]
            if scored[0][2] is None and len(scored) > 1:
                r.warnings.append(f"ambiguous_columns: {r.symbol}: positions de colonnes inconnues")
        choice: list[int] = r.choice if r.choice is not None else r.candidates[0][1]
        choice = _position_override(r, choice, page_medians.get(r.page) or {})
        missing = next(mi for _, a, mi in r.candidates if a == choice)
        vals = _values_for(r.tokens, choice, r.names)
        tok_by_slot = {r.names[si]: tok for tok, si in zip(r.tokens, choice)}
        required = [s[0] for s in slots if s[2]]
        absent = {n for n in required if n not in vals}
        if missing and not ("prev_close" in absent and absent <= {"prev_close", "change_pct"}):
            r.warnings.append(f"incomplete_row: {r.symbol}: {missing} colonne(s) obligatoire(s) manquante(s)")
        if r.overflow:
            _apply_overflow(r, vals, tok_by_slot)
        yfrac = "net_yield_pct" in tok_by_slot and tok_by_slot["net_yield_pct"].kind == "num"
        rec = _build_record(r, vals, day, yfrac)
        _validate_row(r, rec)
        rec["warnings"] = ";".join(sorted({warning_code(w) for w in r.warnings}))
        warnings.extend(r.warnings)
        records.append(rec)
        rec_by_row[id(r)] = rec

    # Contrôle des sous-totaux publiés (lignes TOTAL de chaque groupe).
    for tname, vol, val, grows in group_totals:
        recs = [rec_by_row[id(r)] for r in grows if id(r) in rec_by_row]
        if not recs:
            continue
        s_vol = sum(rc["volume"] or 0 for rc in recs)
        s_val = sum(rc["value"] or 0 for rc in recs)
        if vol is not None and abs(s_vol - vol) > 0.5:
            warnings.append(f"group_total_mismatch: {tname}: volume somme {s_vol:.0f} vs TOTAL {vol:.0f}")
        if val is not None and abs(s_val - val) > 0.5:
            warnings.append(f"group_total_mismatch: {tname}: valeur somme {s_val:.0f} vs TOTAL {val:.0f}")
    if end < len(lines) and _EQ_TABLE_END_RE.search(lines[end]):
        nums = [tok for tok in tokenize(lines[end], 0, lang) if tok.kind == "num"]
        nums, _ = _join_wrapped_groups(nums, lines[end + 1] if end + 1 < len(lines) else "", lang)
        if len(nums) >= 2:
            totals["equity_total_volume"] = nums[-2].value
            totals["equity_total_value"] = nums[-1].value
            s_vol = sum(rc["volume"] or 0 for rc in records)
            s_val = sum(rc["value"] or 0 for rc in records)
            if abs(s_vol - nums[-2].value) > 0.5 or abs(s_val - nums[-1].value) > 0.5:
                warnings.append(
                    f"market_total_mismatch: somme {s_vol:.0f}/{s_val:.0f} vs TOTAL "
                    f"{nums[-2].value:.0f}/{nums[-1].value:.0f}"
                )
    # Marché des droits (inclus dans le volume / la valeur de la page 1 « Actions & Droits »).
    for k in range(end, min(len(lines), end + 200)):
        ln = lines[k].replace("\f", " ")
        if re.search(r"TOTAL\s*-\s*(?:MARCH[EÉ]\s+DES\s+DROITS|RIGHTS\s+MARKET)", ln, re.IGNORECASE):
            nums = [tok for tok in tokenize(ln, 0, lang) if _is_integer_token(tok)]
            nxt = lines[k + 1].replace("\f", " ") if k + 1 < len(lines) else ""
            nums, _ = _join_wrapped_groups(nums, nxt, lang)
            if len(nums) >= 2:
                totals["rights_total_volume"] = nums[-2].value
                totals["rights_total_value"] = nums[-1].value
            break
    totals["group_indices"] = group_indices
    totals["legacy"] = legacy
    df = pd.DataFrame.from_records(records, columns=EQUITY_COLUMNS)
    if len(df):
        dups = sorted(set(df["symbol"][df["symbol"].duplicated()]))
        if dups:
            warnings.append(f"duplicate_symbol: {','.join(dups)}")
    return df, totals


# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------

_HEADLINE_RE = re.compile(
    r"(BRVM\s+(?:COMPOSITE|Composite|10|30|PRESTIGE|Prestige|PRINCIPAL|Principal))\s{2,}"
    r"(-?\d{1,3}(?:[ ,]\d{3})*(?:[,.]\d+)?)(?!\s?%)"
)
_VAR_LABEL_RE = re.compile(
    r"Variation\s+Jour|Variation\s+annuelle|Daily\s+Change|Change\s*/\s*YTD"
    # BOC historiques : « Variation: » (jour) et « Variation / 30 Déc. 2016: » (annuelle),
    # cette dernière parfois coupée (« Variation / 31 » ... « Déc. 2016: » ou « 2016: »).
    r"|Variation\s*:|Variation\s*/\s*3[01]|D[ée]c\.\s*\d{4}\s*:|^\s*\d{4}\s*:",
    re.IGNORECASE,
)
_VAR_PREFIX_RE = re.compile(r"Variation\s*/\s*3[01]", re.IGNORECASE)
_VAR_SUFFIX_RE = re.compile(r"D[ée]c\.\s*\d{4}\s*:|^\s*\d{4}\s*:", re.IGNORECASE)
_HEADLINE_STOP_RE = re.compile(r"Capitalisation\s+boursi|Capitalization\s*\(|PLUS FORTES|TOP GAINS|RESUME DE LA COTE")


def _var_kind(label: str) -> str:
    """``change_pct`` (variation du jour) ou ``ytd_pct`` (depuis le début de l'année)."""
    low = label.lower()
    if re.search(r"/\s*3[01]|^\s*\d{4}\s*:", low):
        return "ytd_pct"  # « Variation / 30 Déc. 2016 », « 2016: »
    return "ytd_pct" if ("annuelle" in low or "ytd" in low or "déc" in low or "dec" in low) else "change_pct"
#: Ligne d'un tableau d'indices. Tolère le « B » perdu (« RVM - CONSOMMATION DE BASE »,
#: 15/07/2026) et le renvoi « (**) » tronqué en « ( » (09/12/2025).
_INDEX_ROW_RE = re.compile(
    r"^\s*(?P<name>B?RVM\s*[-–]?\s*[A-ZÉÈÊÀÂÔÎÇ][A-ZÉÈÊÀÂÔÎÇ0-9' \-–]*?)\s*(?:\(\s*\**\s*\)?)?\s{2,}(?P<rest>(?:\d|-).*)$"
)
#: Caractères parasites des libellés d'indices (« BRVM ²\x03COMPOSITE TOTAL RETURN ») :
#: remplacés par une espace (les positions de colonnes sont conservées).
_INDEX_JUNK_RE = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f²³¹]")
#: PER moyen d'un tableau d'indices : toujours imprimé avec deux décimales dans les BOC
#: français. Toute autre forme (« 1 , », « 7, », « , 8 », « 4, 2 », « 7 »...) est une
#: cellule brouillée par pdftotext. Les BOC anglais omettent les décimales nulles (« 15 »).
_INDEX_PER_RES = {
    "fr": re.compile(r"-?\d{1,3}(?: \d{3})*,\d{2}"),
    "en": re.compile(r"-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|-?\d+,\d{2}"),
}
_INDEX_TITLE_RE = re.compile(
    r"^\s*(?:INDICES?\s+(PAR\s+COMPARTIMENT|TOTAL\s+RETURN|SECTORIELS?)|MARKET\s+INDICES\s+BY\s+(BOARD|SECTOR)"
    r"|(?:PREVIOUS|NEW)\s+(SECTOR)\s+INDICES|(TOTAL\s+RETURN)\s+INDEX)",
    re.IGNORECASE,
)
_BASE_RE = re.compile(r"Base\s*=\s*100\s*(?:au|as\s+of)\s+(.*)$", re.IGNORECASE)
_HEADER_CHG_RE = re.compile(r"Evol\.\s*Jour|Daily\s+Change", re.IGNORECASE)
_HEADER_YTD_RE = re.compile(r"Evol\.\s*annuelle|Yearly\s+Change", re.IGNORECASE)


def _canon_index(name: str) -> str:
    """Nom canonique d'indice : majuscules, tirets normalisés, renvois ``(**)`` supprimés."""
    s = name.upper().replace("–", "-").replace("—", "-")
    s = re.sub(r"\(\*+\)", "", s)
    s = re.sub(r"\s*-\s*", " - ", s)
    return re.sub(r"\s+", " ", s).strip()


def _parse_indices(head: list[str], day: dt.date | None, lang: str, warnings: list[str]) -> pd.DataFrame:
    """Indices de la page 1 (phares, compartiments, Total Return, sectoriels)."""
    recs: dict[str, dict[str, Any]] = {}
    ts = pd.Timestamp(day) if day else pd.NaT

    def put(idx: str, family: str, **kw: Any) -> None:
        rec = recs.setdefault(idx, {"date": ts, "index": idx, "family": family})
        for k, v in kw.items():
            if v is None:
                continue
            old = rec.get(k)
            if old is not None and k == "level" and abs(old - v) > 0.011:
                warnings.append(f"index_level_conflict: {idx}: {old} vs {v}")
                continue
            rec.setdefault(k, v)

    # 1) Indices phares. Chaque pourcentage des lignes « Variation » est rattaché à
    #    l'indice dont la colonne le contient (les étiquettes ne sont pas toujours
    #    sur la même ligne que leur valeur, ex. BOC 2018 et BOC anglais).
    first = next((k for k, ln in enumerate(head) if _HEADLINE_RE.search(ln)), None)
    if first is None:
        warnings.append("no_headline_index: indices phares introuvables")
    else:
        block = head[first:first + 30]
        labels: list[tuple[int, int, str]] = []  # (colonne, ligne, indice)
        for k, ln in enumerate(block):
            for m in _HEADLINE_RE.finditer(ln):
                idx = re.sub(r"\s+", " ", m.group(1)).upper()
                labels.append((m.start(1), k, idx))
                put(idx, "compartment" if idx in ("BRVM PRESTIGE", "BRVM PRINCIPAL") else "headline",
                    level=parse_number(m.group(2), lang))
            if _HEADLINE_STOP_RE.search(ln):
                break
        var_lines: list[tuple[int, str | None, list[Token]]] = []
        for k, ln in enumerate(block):
            if _HEADLINE_STOP_RE.search(ln):
                break
            kinds = {_var_kind(mm.group(0)) for mm in _VAR_LABEL_RE.finditer(ln)}
            pcts = [t for t in tokenize(ln, 0, lang) if t.kind == "pct"]
            var_lines.append((k, kinds.pop() if len(kinds) == 1 else None, pcts))
        # Étiquettes « en attente » de valeur (sans % sur leur ligne). Une étiquette
        # annuelle coupée (« Variation / 31 » ... « Déc. 2016: ») forme un seul groupe,
        # servi si l'une de ses lignes porte la valeur.
        group_of: dict[int, int] = {}
        for k, kind, _ in var_lines:
            if kind is None or k in group_of:
                continue
            group_of[k] = k
            if _VAR_PREFIX_RE.search(block[k]) and not _VAR_SUFFIX_RE.search(block[k]):
                tail = [kk for kk, kd, _ in var_lines if k < kk <= k + 3 and kd == "ytd_pct"
                        and _VAR_SUFFIX_RE.search(block[kk])]
                if tail:
                    group_of[tail[0]] = k
        served = {group_of[k] for k, kind, pcts in var_lines if kind and pcts}
        for k, kind, pcts in var_lines:
            if not pcts:
                continue
            if kind is None:  # valeur sans étiquette sur la ligne : étiquette voisine en attente
                waiting = sorted((abs(kk - k), kk > k, kk, kd) for kk, kd, _ in var_lines
                                 if kd and group_of.get(kk) not in served and abs(kk - k) <= 2)
                if waiting:
                    kind = waiting[0][3]
                    served.add(group_of[waiting[0][2]])
                else:
                    near = [kd for kk, kd, _ in var_lines if kd and abs(kk - k) == 1]
                    kind = near[0] if near else None
            if kind is None:
                continue
            for p in pcts:
                # Indice dont la colonne contient la valeur ; à colonne égale (indices empilés,
                # BOC historiques), le plus proche au-dessus.
                cols = [lb for lb in labels if lb[0] <= p.start + 2 and lb[1] <= k]
                idx = max(cols)[2] if cols else min(labels)[2]
                put(idx, recs[idx]["family"], **{kind: p.value})

    # 2) Tableaux d'indices (compartiments, Total Return, sectoriels).
    family: str | None = None
    base: dt.date | None = None
    col_chg: int | None = None
    col_ytd: int | None = None
    for n, ln in enumerate(head):
        t = _INDEX_TITLE_RE.match(ln)
        if t:
            kind = next(g for g in t.groups() if g).upper()
            family = ("compartment" if ("COMPARTIMENT" in kind or kind == "BOARD")
                      else "total_return" if "RETURN" in kind else "sector")
            base, col_chg, col_ytd = None, None, None
            continue
        b = _BASE_RE.search(ln)
        if b and family:
            txt = re.split(r"\s{2,}", b.group(1).strip())[0]  # la date s'arrête à la colonne suivante
            nxt = head[n + 1].strip() if n + 1 < len(head) else ""
            if not re.search(r"\d{4}", txt) and re.match(r"\d{4}\b", nxt):  # année renvoyée à la ligne
                txt += " " + nxt[:4]
            base = parse_french_date(txt)
            hc, hy = _HEADER_CHG_RE.search(ln), _HEADER_YTD_RE.search(ln)
            col_chg = hc.end() if hc else None
            col_ytd = hy.end() if hy else None
            continue
        if re.match(r"^\s*(Indicateurs|Indicators)\b", ln):
            family = None
            continue
        if family is None:
            continue
        ln = _INDEX_JUNK_RE.sub(" ", ln)
        mrow = _INDEX_ROW_RE.match(ln)
        if not mrow:
            continue
        toks = tokenize(mrow.group("rest"), mrow.start("rest"), lang)
        pct_toks = [tk for tk in toks if tk.kind == "pct"]
        if not pct_toks:
            continue  # ligne de tirets (indice non calculé)
        p0 = toks.index(pct_toks[0])
        before = [tk for tk in toks[:p0] if tk.kind == "num"]
        chg = ytd = None
        if len(pct_toks) >= 2:
            chg, ytd = pct_toks[0].value, pct_toks[1].value
        elif col_chg is not None and col_ytd is not None:
            # Une seule variation imprimée : colonne la plus proche dans l'en-tête.
            e = pct_toks[0].end
            if abs(e - col_chg) <= abs(e - col_ytd):
                chg = pct_toks[0].value
            else:
                ytd = pct_toks[0].value
        else:
            chg = pct_toks[0].value
        after = [tk for tk in toks[toks.index(pct_toks[-1]) + 1:] if tk.kind in ("num", "mark")]
        nums = [tk.value if tk.kind == "num" else None for tk in after]
        name = _canon_index(mrow.group("name"))
        if name.startswith("RVM"):
            name = "B" + name
        if len(after) >= 2:
            # PER moyen : tout ce qui suit la valeur transigée ; illisible -> vide.
            per_txt = ln[after[1].end:].strip()
            nums = nums[:2]
            if _INDEX_PER_RES[lang].fullmatch(per_txt):
                nums.append(parse_number(per_txt, lang))
            elif per_txt and per_txt not in ("-", "ND"):
                warnings.append(f"garbled_index_per: {name}: « {per_txt} » illisible")
        en = re.fullmatch(r"BRVM - (.+)", name)
        if en and en.group(1) in _EN_SECTOR_NAMES:  # BOC anglais : libellés français
            name = f"BRVM - {_EN_SECTOR_NAMES[en.group(1)]}"
        nxt = head[n + 1] if n + 1 < len(head) else ""
        if re.fullmatch(r"\s*[A-ZÉÈ][A-ZÉÈ' ]+\s*", nxt) and not _INDEX_TITLE_RE.match(nxt):
            name = _canon_index(f"{name} {nxt}")  # libellé renvoyé à la ligne (BOC anglais)
        if family in ("compartment", "total_return"):
            idx = name.replace("BRVM - ", "BRVM ")
        else:
            idx = f"{name} (base {base.year})" if base else name
        put(idx, family,
            level=before[-1].value if before else None,
            n_companies=before[-2].value if len(before) >= 2 else None,
            change_pct=chg, ytd_pct=ytd,
            volume=nums[0] if len(nums) > 0 else None,
            value=nums[1] if len(nums) > 1 else None,
            per=nums[2] if len(nums) > 2 else None,
            base_date=pd.Timestamp(base) if base else None)
    return pd.DataFrame.from_records(list(recs.values()), columns=INDEX_COLUMNS)


# ---------------------------------------------------------------------------
# Indicateurs de marché
# ---------------------------------------------------------------------------

#: (expression de l'étiquette, clé 1re occurrence sur la ligne, clé 2e occurrence)
_MARKET_LABELS_FR: list[tuple[str, str, str | None]] = [
    (r"Capitalisation boursi[èe]re\s*-\s*Droits", "rights_market_cap", None),
    (r"Capitalisation boursi[èe]re", "market_cap", "bond_market_cap"),
    (r"Volume [ée]chang[ée]", "volume", "bond_volume"),
    (r"Valeur transig[ée]e", "value", "bond_value"),
    (r"Nombre de titres transig[ée]s", "n_traded", "bond_n_traded"),
    (r"Nombre de titres en hausse", "n_up", "bond_n_up"),
    (r"Nombre de titres en baisse", "n_down", "bond_n_down"),
    (r"Nombre de titres inchang[ée]s", "n_unchanged", "bond_n_unchanged"),
    (r"PER moyen du march[ée]", "avg_per", None),
    (r"Taux de rendement moyen du march[ée]", "avg_yield_pct", None),
    (r"Taux de rentabilit[ée] moyen du march[ée]", "avg_return_pct", None),
    (r"Nombre de soci[ée]t[ée]s cot[ée]es", "n_listed", None),
    (r"Nombre de lignes obligataires", "n_bond_lines", None),
    (r"Volume moyen annuel par s[ée]ance", "avg_session_volume_ytd", None),
    (r"Valeur moyenne annuelle par s[ée]ance", "avg_session_value_ytd", None),
    (r"Ratio moyen de liquidit[ée]", "avg_liquidity_ratio", None),
    (r"Ratio moyen de satisfaction", "avg_satisfaction_ratio", None),
    (r"Ratio moyen de tendance", "avg_trend_ratio", None),
    (r"Ratio moyen de couverture", "avg_coverage_ratio", None),
    (r"Taux de rotation moyen du march[ée]", "avg_turnover_pct", None),
    (r"Prime de risque du march[ée]", "risk_premium", None),
    (r"Nombre de SGI participantes", "n_sgi", None),
]
_MARKET_LABELS_EN: list[tuple[str, str, str | None]] = [
    (r"Capitalization", "market_cap", "bond_market_cap"),
    (r"\bVolume\b", "volume", "bond_volume"),
    (r"\bValue\b", "value", "bond_value"),
    (r"Number of securities", "n_traded", "bond_n_traded"),
    (r"\bGains\b", "n_up", "bond_n_up"),
    (r"\bLosses\b", "n_down", "bond_n_down"),
    (r"\bFlat\b", "n_unchanged", "bond_n_unchanged"),
    (r"PER \(Average\)", "avg_per", None),
    (r"Rate of yi\w*d \(Average\)", "avg_yield_pct", None),
    (r"Rate of profitability \(Average\)", "avg_return_pct", None),
    (r"Securities listed", "n_listed", None),
    (r"Bonds listed", "n_bond_lines", None),
    (r"Yearly volume \(Average\)", "avg_session_volume_ytd", None),
    (r"Yearly value \(Average\)", "avg_session_value_ytd", None),
    (r"Liquidity ratio \(Average\)", "avg_liquidity_ratio", None),
    (r"Satisfaction ratio \(Average\)", "avg_satisfaction_ratio", None),
    (r"Tendency ratio \(Average\)", "avg_trend_ratio", None),
    (r"Coverage ratio \(Average\)", "avg_coverage_ratio", None),
    (r"Turnover rate \(Average\)", "avg_turnover_pct", None),
    (r"Premium risk", "risk_premium", None),
    (r"Number of participating brokerage firms?", "n_sgi", None),
]


def _labels_re(labels: list[tuple[str, str, str | None]]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?P<m{k}>{p})" for k, (p, _, _) in enumerate(labels)))


_MARKET_RES = {"fr": (_MARKET_LABELS_FR, _labels_re(_MARKET_LABELS_FR)),
               "en": (_MARKET_LABELS_EN, _labels_re(_MARKET_LABELS_EN))}
_MARKET_PCT_KEYS = {"market_cap", "volume", "value", "bond_market_cap", "bond_volume", "bond_value"}


def _parse_market_legacy(head: list[str]) -> dict[str, Any]:
    """Indicateurs de la page 1 des BOC historiques (jusqu'à novembre 2017).

    Capitalisations en milliards de FCFA (« - Actions: 7 332,03 »), tableau par
    compartiment (« Actions 33 /43 volume valeur transactions hausses inchangés
    baisses »), ratio de liquidité, PER moyen, SGI participantes.
    """
    market: dict[str, Any] = {}
    for ln in head:
        m = re.search(r"-\s*Actions\s*:\s*(\d[\d ]*[,.]\d+)", ln)
        if m and "market_cap" not in market:
            market["market_cap"] = round(parse_number(m.group(1)) * 1e9)  # type: ignore[operator]
        m = re.search(r"-\s*Obligations\s*:\s*(\d[\d ]*[,.]\d+)", ln)
        if m and "bond_market_cap" not in market:
            market["bond_market_cap"] = round(parse_number(m.group(1)) * 1e9)  # type: ignore[operator]
        m = re.match(r"^\s*(Actions|Obligations)\s+(\d+)\s*/\s*(\d+)\s+(\d.*)$", ln)
        if m:
            pre = "" if m.group(1) == "Actions" else "bond_"
            nums = [t.value for t in tokenize(m.group(4)) if t.kind == "num"]
            market.setdefault(f"{pre}n_traded", float(m.group(2)))
            market.setdefault("n_listed" if not pre else "n_bond_lines", float(m.group(3)))
            for key, v in zip(("volume", "value", "n_transactions", "n_up", "n_unchanged", "n_down"), nums):
                market.setdefault(f"{pre}{key}", v)
        m = re.search(r"Ratio de liquidit[ée]\s*:\s*(-?\d[\d ]*[,.]?\d*)\s*%", ln)
        if m:
            market.setdefault("avg_liquidity_ratio", parse_number(m.group(1)))
        m = re.search(r"PER moyen\s*:\s*(-?\d[\d ]*[,.]?\d*)", ln)
        if m:
            market.setdefault("avg_per", parse_number(m.group(1)))
        m = re.search(r"SGI participantes\s*/\s*Total\s*:\s*(\d+)", ln)
        if m:
            market.setdefault("n_sgi", float(m.group(1)))
    return market


_MARKET_COLS_RE = re.compile(r"^\s*(?:Actions|Equities)\b.*?\b(?P<bond>Obligations|Bonds)\b")


def _parse_market(head: list[str], lang: str, warnings: list[str]) -> dict[str, Any]:
    """Indicateurs de la page 1 (premières occurrences uniquement, hors « Définitions »).

    Les étiquettes présentes dans les deux colonnes (« Volume échangé »...) sont
    affectées aux actions ou aux obligations selon leur **colonne** : celle de
    l'en-tête « Actions ... Obligations ». L'ordre d'apparition sur la ligne ne
    suffit pas : certains BOC (27/05 au 26/06/2019) impriment la colonne
    Obligations une ligne au-dessus de la colonne Actions.
    """
    labels, label_re = _MARKET_RES[lang]
    market: dict[str, Any] = {}
    bond_col: int | None = None
    for ln in head:
        if re.match(r"^\s*(D[ée]finitions|Definitions)\b", ln):
            break
        mc = _MARKET_COLS_RE.match(ln)
        if mc and bond_col is None:
            bond_col = mc.start("bond")
            continue
        matches = list(label_re.finditer(ln))
        seen: Counter[int] = Counter()
        for n, m in enumerate(matches):
            k = int((m.lastgroup or "m0")[1:])
            _, key1, key2 = labels[k]
            if key2 is not None and bond_col is not None:
                key = key2 if m.start() >= bond_col - 8 else key1
            else:
                key = key1 if seen[k] == 0 else key2
            seen[k] += 1
            if key is None or key in market:
                continue
            seg = ln[m.end(): matches[n + 1].start() if n + 1 < len(matches) else len(ln)]
            if re.match(r"\s*=", seg):
                continue  # ligne de définition
            toks = [t for t in tokenize(seg, 0, lang) if t.kind in ("num", "pct")]
            nums = [t for t in toks if t.kind == "num"]
            if not nums:
                continue
            market[key] = nums[0].value
            pcts = [t for t in toks if t.kind == "pct"]
            if pcts and key in _MARKET_PCT_KEYS:
                market[f"{key}_chg_pct"] = pcts[0].value
    if "market_cap" not in market and lang == "fr":
        for lk, lv in _parse_market_legacy(head).items():
            market.setdefault(lk, lv)
    if "market_cap" not in market:
        warnings.append("market_cap_missing: capitalisation introuvable en page 1")
    return market


# ---------------------------------------------------------------------------
# Carnet d'ordres (meilleures limites)
# ---------------------------------------------------------------------------

_OB_ROW_RE = re.compile(r"^\s*(?P<sym>[A-Z][A-Z0-9]{2,6})\s{2,}(?P<rest>\S.*?/.*)$")
#: Ligne sans aucun ordre (« TTRC  TRITURAF ...  -  -  -  490 », BOC 2017) : pas de « / ».
_OB_EMPTY_ROW_RE = re.compile(
    r"^\s*(?P<sym>[A-Z][A-Z0-9]{2,6})\s{2,}(?P<name>\S.*?)(?P<dashes>(?:\s{2,}-){2,})\s{2,}"
    r"(?P<ref>\d{1,3}(?: \d{3})*|\d+)(?:\s+(?P<mark>\S.*?))?\s*$")
_OB_START_RE = re.compile(r"^\s*(MARCH[EÉ] DES ACTIONS|EQUITIES MARKET)\s*$", re.IGNORECASE)
_OB_END_RE = re.compile(r"^\s*(MARCH[EÉ] DES|TROISIEME COMPARTIMENT|RIGHTS MARKET|BONDS MARKET)", re.IGNORECASE)


def _parse_order_book(lines: list[str], day: dt.date | None, warnings: list[str], lang: str = "fr") -> pd.DataFrame:
    """Section « MARCHE DES ACTIONS » : quantité/prix à l'achat, prix/quantité à la vente.

    Format d'une ligne : ``SYMB  NOM  [qté_achat] [prix_achat] / [prix_vente] [qté_vente]  cours_réf``.
    Les prix y utilisent la virgule comme séparateur de milliers (``4,010`` = 4 010 FCFA),
    les quantités l'espace. ``Marché`` désigne un ordre au prix du marché.
    """
    # Le titre « MARCHE DES ACTIONS » sert aussi à la cote (BOC historiques) : on retient
    # celui suivi de l'en-tête « résiduelle / Achat / Vente ».
    start = next((i + 1 for i, ln in enumerate(lines) if _OB_START_RE.match(ln.replace("\f", ""))
                  and re.search(r"r[ée]siduelle|Achat\s*/\s*Vente|Remaining", "\n".join(lines[i + 1:i + 8]),
                                re.IGNORECASE)), None)
    ts = pd.Timestamp(day) if day else pd.NaT
    if start is None:
        return pd.DataFrame(columns=ORDER_BOOK_COLUMNS)
    recs: list[dict[str, Any]] = []
    for ln in lines[start:]:
        ln = ln.replace("\f", " ")
        if _OB_END_RE.match(ln):
            break
        m = _OB_ROW_RE.match(ln)
        if not m:
            e = _OB_EMPTY_ROW_RE.match(ln)
            if e and e.group("sym") not in _NOT_SYMBOLS:
                recs.append({"date": ts, "symbol": e.group("sym"), "name": _normalize_name(e.group("name")),
                             "bid_qty": None, "bid": None, "ask": None, "ask_qty": None,
                             "ref_price": parse_number(e.group("ref"), lang),
                             "bid_at_market": False, "ask_at_market": False})
            continue
        if m.group("sym") in _NOT_SYMBOLS:
            continue
        off = m.start("rest")
        slash = ln.index("/", off)
        ne = re.search(r"\s{2,}(?=(?:\d|/|March))", ln[off:slash + 1])
        name_end = off + (ne.start() if ne else slash - off)
        keep = ("num", "mark", "text")
        left = [t for t in tokenize(ln[name_end:slash], name_end, lang) if t.kind in keep and t.text != "-"]
        right = [t for t in tokenize(ln[slash + 1:], slash + 1, lang) if t.kind in keep and t.text != "-"]
        name = re.sub(r"\s+-$", "", _normalize_name(ln[off:name_end]))  # « - » = case vide (BOC 2017)
        rec: dict[str, Any] = {"date": ts, "symbol": m.group("sym"), "name": name,
                               "bid_qty": None, "bid": None, "ask": None, "ask_qty": None, "ref_price": None,
                               "bid_at_market": False, "ask_at_market": False}

        def is_mkt(t: Token) -> bool:
            return t.text.lower().startswith("march")

        # Marqueurs après le cours de référence (« 3 080 Val- T », « 17 950 Ex-c », BOC 2017).
        while right and right[-1].kind in ("mark", "text") and not is_mkt(right[-1]):
            right = right[:-1]
        # Côté vente : le jeton numérique le plus à droite est le cours de référence.
        if right and right[-1].kind == "num":
            rec["ref_price"] = parse_number(right[-1].text, lang)
            right = right[:-1]
        if len(right) >= 2:
            a, q = right[0], right[1]
            rec["ask_at_market"] = is_mkt(a)
            rec["ask"] = None if is_mkt(a) else _parse_ob_price(a.text)
            rec["ask_qty"] = parse_number(q.text, lang)
        elif len(right) == 1:
            a = right[0]
            if is_mkt(a):
                rec["ask_at_market"] = True
            elif a.start - slash <= 14:  # collé à la barre : c'est un prix
                rec["ask"] = _parse_ob_price(a.text)
            else:
                rec["ask_qty"] = parse_number(a.text, lang)
        # Côté achat : [quantité] [prix] avant la barre.
        if len(left) >= 2:
            q, b = left[-2], left[-1]
            rec["bid_qty"] = parse_number(q.text, lang)
            rec["bid_at_market"] = is_mkt(b)
            rec["bid"] = None if is_mkt(b) else _parse_ob_price(b.text)
        elif len(left) == 1:
            b = left[0]
            if is_mkt(b):
                rec["bid_at_market"] = True
            elif slash - b.end <= 14:
                rec["bid"] = _parse_ob_price(b.text)
            else:
                rec["bid_qty"] = parse_number(b.text, lang)
        if rec["bid"] is not None and rec["ask"] is not None and rec["bid"] > rec["ask"] * 1.0001:
            warnings.append(f"order_book_crossed: {rec['symbol']}: achat {rec['bid']:g} > vente {rec['ask']:g}")
        recs.append(rec)
    return pd.DataFrame.from_records(recs, columns=ORDER_BOOK_COLUMNS)


# ---------------------------------------------------------------------------
# Points d'entrée
# ---------------------------------------------------------------------------


def _header_date(lines: Iterable[str]) -> dt.date | None:
    """Date la plus fréquente des en-têtes de page (« vendredi 20 novembre 2026 »)."""
    found: Counter[dt.date] = Counter()
    for ln in lines:
        for m in _HEADER_DATE_RE.finditer(ln):
            try:
                found[dt.date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))] += 1
            except (KeyError, ValueError):
                continue
    return found.most_common(1)[0][0] if found else None


def _detect_lang(lines: list[str]) -> str:
    """``"en"`` pour un BOC publié en anglais, ``"fr"`` sinon."""
    head = "\n".join(lines[:120])
    en = len(re.findall(r"Daily Change|Equities|Capitalization|TOP GAINS", head))
    fr = len(re.findall(r"Variation Jour|Capitalisation|PLUS FORTES|Variation annuelle", head))
    return "en" if en > fr else "fr"


def parse_boc_text(text: str, date: dt.date | str | None = None) -> BocDay:
    """Analyse le texte d'un BOC.

    Parameters
    ----------
    text:
        Sortie ``pdftotext -layout`` (la 1re ligne ``# source: URL`` est facultative).
    date:
        Date attendue (typiquement celle du nom de fichier), utilisée si l'en-tête
        n'en contient pas. Si l'en-tête (« vendredi 20 novembre 2026 ») donne une
        autre date, c'est ``date`` qui est retenue (l'URL BRVM est datée et garantit
        l'unicité de la séance) et un avertissement ``date_mismatch`` est émis ;
        la date d'en-tête reste disponible dans ``meta["header_date"]``.
    """
    warnings: list[str] = []
    meta: dict[str, Any] = {}
    if isinstance(date, str):
        date = dt.date.fromisoformat(date) if "-" in date else dt.datetime.strptime(date, "%Y%m%d").date()
    # NB : str.splitlines() couperait aussi sur \f (saut de page), qu'on veut conserver.
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0].startswith("# source:"):
        meta["source"] = lines[0].split(":", 1)[1].strip()
        lines = lines[1:]
    pages = _pages(lines)
    lang = _detect_lang(lines)
    meta["lang"] = lang
    if lang != "fr":
        warnings.append(f"lang_{lang}: bulletin publié en anglais")
    hdate = _header_date(lines[:400])
    meta["header_date"] = hdate
    if date is not None and hdate is not None and hdate != date:
        warnings.append(f"date_mismatch: en-tête {hdate.isoformat()} vs attendu {date.isoformat()}")
    day = date or hdate
    if day is None:
        warnings.append("no_date: date de séance introuvable")

    eq_start, _ = _find_equity_region(lines, [])
    head = lines[:eq_start] if eq_start else lines[:120]
    equities, totals = _parse_equities(lines, pages, day, lang, warnings)
    group_indices = totals.pop("group_indices", [])
    legacy = totals.pop("legacy", False)
    meta["legacy_layout"] = legacy
    indices = _parse_indices(head, day, lang, warnings)
    # Indices sectoriels lus dans les en-têtes de groupe de la cote (« SECTEUR - INDUSTRIE
    # 146,08 points -1,10% ») quand la page 1 ne les donne pas (BOC historiques).
    known = set(indices["index"])
    extra = []
    for gi in group_indices:
        if gi["name"].startswith("COMPARTIMENT") or gi["level"] is None:
            continue
        idx_name = f"BRVM - {gi['name']} (base 1999)"
        if idx_name not in known:
            extra.append({"date": pd.Timestamp(day) if day else pd.NaT, "index": idx_name, "level": gi["level"],
                          "change_pct": gi["change_pct"], "family": "sector",
                          "base_date": pd.Timestamp("1999-06-14")})
            known.add(idx_name)
    if extra:
        indices = pd.concat([indices, pd.DataFrame(extra, columns=INDEX_COLUMNS)], ignore_index=True)
    market = _parse_market(head, lang, warnings)
    market.update(totals)
    # Contrôle : volume / valeur de la page 1 (actions & droits) = lignes « TOTAL - MARCHE
    # DES ACTIONS » + « TOTAL - MARCHE DES DROITS ».
    for key in ("volume", "value"):
        a, b = market.get(key), market.get(f"equity_total_{key}")
        if a is not None and b is not None:
            b += market.get(f"rights_total_{key}") or 0.0
            if abs(a - b) > 0.5:
                warnings.append(f"market_total_mismatch: page 1 {key} {a:.0f} vs TOTAL actions+droits {b:.0f}")
    order_book = _parse_order_book(lines, day, warnings, lang)
    if len(order_book) and len(equities):
        # Contrôle croisé : le cours de référence du carnet = celui du tableau des cours.
        # Les veilles de détachement, le carnet garde la référence non ajustée (= clôture).
        eqi = equities.drop_duplicates("symbol").set_index("symbol")
        for r in order_book.itertuples(index=False):
            if r.symbol not in eqi.index or pd.isna(r.ref_price):
                continue
            if eqi.at[r.symbol, "status"] != "traded":
                continue  # non coté / suspendu : la référence du carnet peut différer
            eq_ref, eq_close = eqi.at[r.symbol, "ref_price"], eqi.at[r.symbol, "close"]
            if pd.notna(eq_ref) and abs(eq_ref - r.ref_price) > 0.5 and not abs(eq_close - r.ref_price) <= 0.5:
                warnings.append(f"order_book_ref_mismatch: {r.symbol}: carnet {r.ref_price:g} vs cote {eq_ref:g}")
    n_listed = market.get("n_listed")
    if n_listed and abs(len(equities) - n_listed) > 2:
        warnings.append(f"equity_count_mismatch: {len(equities)} lignes vs {n_listed:g} sociétés cotées")
    meta["n_pages"] = (pages[-1] + 1) if pages else 0
    return BocDay(date=day, equities=equities, indices=indices, market=market,
                  order_book=order_book, warnings=warnings, meta=meta)


_FILE_DATE_RE = re.compile(r"boc_(\d{8})")


def read_boc_text(path: str | Path) -> str:
    """Lit un fichier BOC texte (``.txt.gz`` ou ``.txt``)."""
    p = Path(path)
    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    return p.read_text(encoding="utf-8", errors="replace")


def parse_boc_file(path: str | Path) -> BocDay:
    """Analyse un fichier ``boc_AAAAMMJJ.txt[.gz]`` (date attendue tirée du nom)."""
    p = Path(path)
    m = _FILE_DATE_RE.search(p.name)
    fdate = dt.datetime.strptime(m.group(1), "%Y%m%d").date() if m else None
    day = parse_boc_text(read_boc_text(p), date=fdate)
    day.meta["file"] = p.name
    return day
