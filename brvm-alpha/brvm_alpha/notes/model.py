"""Modèle de données des notes de l'analyste : ``Note``, ``NoteAnalysis``, codes de cibles.

Ce module est le socle du paquet ``brvm_alpha.notes`` (contrat : ``docs/ARCHITECTURE.md``,
section « Module Notes de l'analyste »). Il ne dépend que de pandas et numpy ; le
calendrier des séances (``data/panel/sessions.parquet``) n'est lu qu'à la demande.

Codes de cibles canoniques
--------------------------
- ``SNTS`` : symbole d'une action BRVM ;
- ``IDX:BRVM-C``, ``IDX:BRVM-30``, ``IDX:PRESTIGE``, ``IDX:PRINCIPAL``,
  ``IDX:BRVM-C-TR`` (Composite Total Return), ``IDX:BRVM-10`` (historique, jusqu'en 2022),
  ``IDX:SECT:<code secteur>`` (indices sectoriels) ;
- ``PAYS:CI|SN|BJ|BF|ML|NE|TG|GW`` ;
- ``SECT:<code secteur BOC>`` (FIN, TEL, CB, CD, ENE, IND, SPU ; base 1999 : AGR, DIS, TRP, AUT) ;
- ``THEME:<MOT>`` (TAUX_BCEAO, CACAO, PETROLE, ELECTIONS, SECURITE, EUROBOND…) ;
- ``MARCHE``.

Règle de négociabilité (document 07, §2.3, harmonisée le 22/11/2026)
---------------------------------------------------------------------
Une information mise en ligne le jour J à ``published_at`` (UTC) n'est négociable qu'au
fixing d'ouverture suivant (09h45 UTC). Coupure unique : **09h00 UTC** (début de la
pré-ouverture). Avant 09h00 un jour de séance : séance du jour J ; sinon : séance
suivante. Une date **sans heure** (listes brvm.org « date seule ») est traitée comme
publiée en fin de journée : elle n'agit qu'à la séance suivante (prudence, aucun biais
d'anticipation). Par convention, un horodatage à exactement 00:00:00 est une date seule.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from brvm_alpha import paths as _paths
from brvm_alpha.reference import COUNTRY_NAMES, SYMBOLS_2026

# ---------------------------------------------------------------------------
# Vocabulaires contrôlés
# ---------------------------------------------------------------------------

AUTHORS = ("analyste", "auto")
SOURCES = ("manual", "brvm_list", "brvm_issuer", "boc", "url")
STANCES = ("haussier", "baissier", "neutre")
STATUSES = ("active", "archived")
DEFAULT_HORIZON_DAYS = 20

#: Heure de coupure (UTC) : avant, la séance du jour est encore négociable (doc 07 §2.3).
NEWS_CUTOFF_UTC = _dt.time(9, 0)
#: Fixing d'ouverture (UTC), pour l'affichage.
OPEN_FIXING_UTC = _dt.time(9, 45)

#: Types d'événements : document 07 §6.4, plus les types propres aux notes.
EVENT_TYPES: dict[str, str] = {
    "DIV_NOTICE": "avis de paiement de dividendes",
    "AG_CONVOCATION": "convocation d'assemblée générale",
    "AG_RESOLUTIONS": "projets de résolutions",
    "AG_CANCEL": "annulation ou report d'assemblée générale",
    "RES_ANNUAL": "comptes annuels",
    "RES_S1": "comptes ou rapport semestriels",
    "ACT_Q1": "rapport d'activité du 1er trimestre",
    "ACT_Q3": "rapport d'activité du 3e trimestre",
    "PROFIT_WARNING": "alerte sur résultats",
    "RATING": "notation financière",
    "MGMT_CHANGE": "changement de dirigeants",
    "THRESHOLD": "franchissement de seuil",
    "CAP_INC": "augmentation de capital",
    "SPLIT": "fractionnement",
    "REVERSE_SPLIT": "regroupement d'actions",
    "OPV_IPO": "offre publique de vente ou première cotation",
    "TAKEOVER": "offre publique d'achat ou de retrait",
    "SUSPENSION": "suspension de cotation",
    "RESUMPTION": "levée de suspension",
    "DELISTING": "radiation",
    "INDEX_CHANGE": "changement de composition d'indice",
    "REGULATOR": "décision du régulateur",
    "PRESS": "article de presse",
    "MANUAL": "note manuelle de l'analyste",
    "MACRO": "macroéconomie (BCEAO, inflation, croissance, dette)",
    "POLITIQUE": "politique (élections, sanctions, institutions)",
    "SECURITE": "sécurité",
    "MATIERES_PREMIERES": "matières premières",
    "NOTATION_SOUVERAINE": "notation souveraine",
    "OTHER": "autre",
}

#: Filtres de risque (document 07 §6.6).
RISK_FLAGS: dict[str, str] = {
    "R1": "suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances)",
    "R2": "annulation ou report d'AG : −1 en gouvernance, aucun achat (60 séances)",
    "R3": "réserves d'audit, continuité d'exploitation, capitaux propres < ½ capital : exclusion",
    "R4": "dégradation de notation ou perspective négative : poids maximal × 0,5 (120 séances)",
    "R5": "augmentation de capital en numéraire : aucun achat avant le détachement des droits",
    "R6": "offre publique ou introduction : gel des signaux automatiques",
    "R7": "rapport périodique en retard : alerte, −0,5 en qualité au niveau rouge",
    "R8": "fractionnement ou regroupement : contrôle du facteur d'ajustement (5 séances)",
    "R9": "alerte sur résultats : aucun achat, S1 et S4 désactivés (60 séances)",
    "R10": "ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)",
}

#: Indices de marché : code -> (libellé, noms dans ``indices.parquet``).
INDEX_TARGETS: dict[str, tuple[str, tuple[str, ...]]] = {
    "IDX:BRVM-C": ("BRVM Composite", ("BRVM COMPOSITE",)),
    "IDX:BRVM-30": ("BRVM 30", ("BRVM 30",)),
    "IDX:PRESTIGE": ("BRVM Prestige", ("BRVM PRESTIGE",)),
    "IDX:PRINCIPAL": ("BRVM Principal", ("BRVM PRINCIPAL",)),
    "IDX:BRVM-C-TR": ("BRVM Composite Total Return", ("BRVM COMPOSITE TOTAL RETURN",)),
    "IDX:BRVM-10": ("BRVM 10 (jusqu'en 2022)", ("BRVM 10",)),
}

#: Secteurs du BOC : code -> libellé. Les sept premiers sont ceux de la base 2025.
SECTOR_LABELS: dict[str, str] = {
    "FIN": "Services financiers",
    "TEL": "Télécommunications",
    "CB": "Consommation de base",
    "CD": "Consommation discrétionnaire",
    "ENE": "Énergie",
    "IND": "Industriels",
    "SPU": "Services publics",
    "AGR": "Agriculture (base 1999)",
    "DIS": "Distribution (base 1999)",
    "TRP": "Transport (base 1999)",
    "AUT": "Autres secteurs (base 1999)",
}

#: Indices sectoriels : code -> noms dans ``indices.parquet`` (base 2025 d'abord).
SECTOR_INDEX_NAMES: dict[str, tuple[str, ...]] = {
    "FIN": ("BRVM - SERVICES FINANCIERS (base 2025)", "BRVM - FINANCES (base 1999)"),
    "TEL": ("BRVM - TELECOMMUNICATIONS (base 2025)",),
    "CB": ("BRVM - CONSOMMATION DE BASE (base 2025)",),
    "CD": ("BRVM - CONSOMMATION DISCRETIONNAIRE (base 2025)",),
    "ENE": ("BRVM - ENERGIE (base 2025)",),
    "IND": ("BRVM - INDUSTRIELS (base 2025)", "BRVM - INDUSTRIE (base 1999)"),
    "SPU": ("BRVM - SERVICES PUBLICS (base 2025)", "BRVM - SERVICES PUBLICS (base 1999)"),
    "AGR": ("BRVM - AGRICULTURE (base 1999)",),
    "DIS": ("BRVM - DISTRIBUTION (base 1999)",),
    "TRP": ("BRVM - TRANSPORT (base 1999)",),
    "AUT": ("BRVM - AUTRES SECTEURS (base 1999)",),
}

#: Thèmes macro et matières premières (document 05) : code -> libellé.
THEMES: dict[str, str] = {
    "TAUX_BCEAO": "taux directeurs et politique monétaire de la BCEAO",
    "INFLATION": "inflation",
    "CROISSANCE": "croissance économique (PIB)",
    "DETTE_PUBLIQUE": "dette et finances publiques, FMI",
    "EUROBOND": "eurobonds",
    "OBLIGATIONS_ETAT": "emprunts d'État sur le marché régional",
    "NOTATION_SOUVERAINE": "notations souveraines",
    "MONNAIE": "franc CFA, parité avec l'euro, projet ECO",
    "ELECTIONS": "élections",
    "COUP_ETAT": "coup d'État, transition militaire",
    "SANCTIONS": "sanctions CEDEAO / UEMOA",
    "AES": "Alliance des États du Sahel",
    "SECURITE": "sécurité, terrorisme",
    "FISCALITE": "fiscalité, nouvelles taxes",
    "MOBILE_MONEY": "monnaie électronique, mobile money",
    "CACAO": "cacao",
    "CAFE": "café",
    "CAOUTCHOUC": "caoutchouc naturel",
    "HUILE_PALME": "huile de palme",
    "SUCRE": "sucre",
    "CAJOU": "noix de cajou",
    "COTON": "coton",
    "OR": "or",
    "PETROLE": "pétrole et produits pétroliers",
    "GAZ": "gaz naturel",
    "ENERGIE": "énergie, électricité, délestages",
    "CLIMAT": "pluviométrie, climat",
    "LOGISTIQUE": "ports et logistique",
}

#: Symboles historiques (radiés ou suspendus de longue date) présents dans le panel.
HISTORICAL_SYMBOLS = ("SVOC", "TTRC")
KNOWN_SYMBOLS: frozenset[str] = frozenset(SYMBOLS_2026) | frozenset(HISTORICAL_SYMBOLS)


@lru_cache(maxsize=1)
def panel_symbols() -> frozenset[str]:
    """Symboles présents dans ``data/panel/equities.parquet`` (lecture paresseuse, mise en cache).

    Complète :data:`KNOWN_SYMBOLS` (liste 2026) par les titres réellement cotés dans le
    panel, par exemple une nouvelle cotation. Ensemble vide si le panel est absent.
    """
    path = default_panel_dir() / "equities.parquet"
    if not path.exists():
        return frozenset()
    try:
        col = pd.read_parquet(path, columns=["symbol"])["symbol"]
    except Exception:  # pragma: no cover - panel illisible
        return frozenset()
    return frozenset(str(s).strip().upper() for s in col.dropna().unique() if str(s).strip())


def is_known_symbol(code: str) -> bool:
    """Le code est-il un symbole connu (liste 2026, historiques, ou présent dans le panel) ?"""
    c = str(code or "").strip().upper()
    if not c:
        return False
    return c in KNOWN_SYMBOLS or c in panel_symbols()

TARGET_KINDS = ("symbol", "index", "country", "sector", "theme", "market")

# ---------------------------------------------------------------------------
# Normalisation de texte (partagée par entities, lexicon, analyze)
# ---------------------------------------------------------------------------

_APOSTROPHES = "’‘ʼ´`′"
_DASHES = "‐‑‒–—―−"
_SPACES = "     "


def fold(text: str) -> str:
    """Minuscules, sans accents, apostrophes et tirets unifiés, espaces simplifiées."""
    return fold_with_map(text)[0]


def fold_with_map(text: str) -> tuple[str, list[int]]:
    """Comme :func:`fold`, et renvoie pour chaque caractère produit l'indice d'origine.

    La table permet de retrouver la forme exacte (casse, accents) d'un terme trouvé
    dans le texte normalisé. Les ligatures (« œ ») sont développées (« oe »).
    """
    if not text:
        return "", []
    out: list[str] = []
    idx: list[int] = []
    prev_space = True
    for i, ch in enumerate(str(text)):
        if ch in _APOSTROPHES:
            ch = "'"
        elif ch in _DASHES:
            ch = "-"
        elif ch in _SPACES or ch in "\t\r\n\f\v":
            ch = " "
        if ch == " ":
            if prev_space:
                continue
            out.append(" ")
            idx.append(i)
            prev_space = True
            continue
        if ch in "œŒ":
            rep = "oe"
        elif ch in "æÆ":
            rep = "ae"
        elif ch == "ß":
            rep = "ss"
        else:
            rep = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        for c in rep.lower():
            out.append(c)
            idx.append(i)
        prev_space = False
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def slug(text: str) -> str:
    """Identifiant ASCII en majuscules (``taux BCEAO`` -> ``TAUX_BCEAO``)."""
    s = re.sub(r"[^a-z0-9]+", "_", fold(text)).strip("_")
    return s.upper()


# ---------------------------------------------------------------------------
# Codes de cibles
# ---------------------------------------------------------------------------

_SECTOR_WORDS = {
    "finance": "FIN", "finances": "FIN", "services financiers": "FIN", "financier": "FIN",
    "banques": "FIN", "bancaire": "FIN", "telecommunications": "TEL", "telecoms": "TEL",
    "telecom": "TEL", "consommation de base": "CB", "consommation discretionnaire": "CD",
    "energie": "ENE", "industriels": "IND", "industrie": "IND", "services publics": "SPU",
    "agriculture": "AGR", "distribution": "DIS", "transport": "TRP", "transports": "TRP",
    "autres secteurs": "AUT",
}

_INDEX_WORDS = {
    "brvm c": "IDX:BRVM-C", "brvmc": "IDX:BRVM-C", "brvm composite": "IDX:BRVM-C",
    "composite": "IDX:BRVM-C", "brvm composite index": "IDX:BRVM-C",
    "indice composite": "IDX:BRVM-C",
    "brvm 30": "IDX:BRVM-30", "brvm30": "IDX:BRVM-30", "indice brvm 30": "IDX:BRVM-30",
    "brvm 10": "IDX:BRVM-10", "brvm10": "IDX:BRVM-10",
    "prestige": "IDX:PRESTIGE", "brvm prestige": "IDX:PRESTIGE", "compartiment prestige": "IDX:PRESTIGE",
    "principal": "IDX:PRINCIPAL", "brvm principal": "IDX:PRINCIPAL", "compartiment principal": "IDX:PRINCIPAL",
    "brvm c tr": "IDX:BRVM-C-TR", "brvm ctr": "IDX:BRVM-C-TR", "brvmc tr": "IDX:BRVM-C-TR",
    "composite total return": "IDX:BRVM-C-TR", "brvm composite total return": "IDX:BRVM-C-TR",
    "total return": "IDX:BRVM-C-TR",
}

_MARKET_WORDS = {"marche", "brvm", "market", "le marche", "marche brvm", "bourse", "la bourse", "cote", "la cote"}


def _country_lookup() -> dict[str, str]:
    table: dict[str, str] = {}
    for code, name in COUNTRY_NAMES.items():
        table[fold(code)] = code
        table[re.sub(r"[^a-z0-9]+", " ", fold(name)).strip()] = code
    extra = {
        "cote divoire": "CI", "rci": "CI", "ivory coast": "CI", "senegal": "SN", "benin": "BJ",
        "burkina": "BF", "guinee bissau": "GW", "bissau": "GW", "civ": "CI", "sen": "SN",
        "ben": "BJ", "bfa": "BF", "mli": "ML", "ner": "NE", "tgo": "TG", "gnb": "GW",
    }
    table.update(extra)
    return table


_COUNTRY_LOOKUP = _country_lookup()


def _index_name_lookup() -> dict[str, str]:
    table: dict[str, str] = {}
    for code, (label, names) in INDEX_TARGETS.items():
        for n in (label,) + names:
            table[re.sub(r"[^a-z0-9]+", " ", fold(n)).strip()] = code
    for code, names in SECTOR_INDEX_NAMES.items():
        for n in names:
            key = re.sub(r"[^a-z0-9]+", " ", fold(n)).strip()
            table[key] = f"IDX:SECT:{code}"
            table[re.sub(r" base (1999|2025)$", "", key)] = f"IDX:SECT:{code}"
    return table


_INDEX_NAME_LOOKUP = _index_name_lookup()


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", fold(text)).strip()


def target_kind(code: str) -> str:
    """Nature d'un code canonique : symbol, index, country, sector, theme ou market."""
    if code == "MARCHE":
        return "market"
    if code.startswith("IDX:"):
        return "index"
    if code.startswith("PAYS:"):
        return "country"
    if code.startswith("SECT:"):
        return "sector"
    if code.startswith("THEME:"):
        return "theme"
    return "symbol"


#: Ordre de spécificité (le plus précis d'abord), utilisé pour la cible principale.
TARGET_SPECIFICITY = {"symbol": 0, "index": 1, "sector": 2, "country": 3, "theme": 4, "market": 5}


def _normalize_sector(code: str) -> str | None:
    k = _key(code)
    up = k.upper().replace(" ", "")
    if up in SECTOR_LABELS:
        return up
    if k in _SECTOR_WORDS:
        return _SECTOR_WORDS[k]
    for c, label in SECTOR_LABELS.items():
        if k == _key(re.sub(r"\(.*\)", "", label)):
            return c
    return None


def normalize_target(value: Any, strict: bool = False) -> str | None:
    """Code canonique d'une cible saisie librement.

    Accepte ``"snts"``, ``"BRVM 30"``, ``"brvm-30"``, ``"Prestige"``, ``"Côte d'Ivoire"``,
    ``"CI"``, ``"pays:sn"``, ``"SECT:fin"``, ``"theme:taux BCEAO"``, ``"cacao"``,
    ``"Sonatel"``, ``"Orange CI"``, ``"marché"``…

    Renvoie ``None`` (ou lève ``ValueError`` si ``strict``) quand la valeur est inconnue.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    k = _key(raw)
    if not k:
        return None
    up = raw.upper().strip()

    # Préfixes explicites.
    m = re.match(r"^\s*(idx|indice|index|pays|country|sect|secteur|sector|theme|thème)\s*[:=]\s*(.+)$", raw, re.I)
    if m:
        prefix = fold(m.group(1))
        rest = m.group(2).strip()
        if prefix in ("idx", "indice", "index"):
            sm = re.match(r"^\s*(sect|secteur)\s*[:=]\s*(.+)$", rest, re.I)
            if sm:
                sec = _normalize_sector(sm.group(2))
                if sec:
                    return f"IDX:SECT:{sec}"
            else:
                rk = _key(rest)
                if rk in _INDEX_WORDS:
                    return _INDEX_WORDS[rk]
                if rk in _INDEX_NAME_LOOKUP:
                    return _INDEX_NAME_LOOKUP[rk]
                if rk.replace(" ", "-").upper() in {c[4:] for c in INDEX_TARGETS}:
                    return "IDX:" + rk.replace(" ", "-").upper()
                sec = _normalize_sector(rest)
                if sec:
                    return f"IDX:SECT:{sec}"
        elif prefix in ("pays", "country"):
            rk = _key(rest)
            if rk in _COUNTRY_LOOKUP:
                return "PAYS:" + _COUNTRY_LOOKUP[rk]
            code = _entity_lookup(rest, kinds=("country",))
            if code:
                return code
        elif prefix in ("sect", "secteur", "sector"):
            sec = _normalize_sector(rest)
            if sec:
                return f"SECT:{sec}"
        else:  # thème
            th = _theme_code(rest)
            if th:
                return th
        if strict:
            raise ValueError(f"cible inconnue : {value!r}")
        return None

    if k in ("marche", "market", "le marche", "brvm", "marche brvm", "bourse", "la bourse", "ensemble du marche"):
        return "MARCHE"
    if up.replace(" ", "") in KNOWN_SYMBOLS:
        return up.replace(" ", "")
    if re.fullmatch(r"[A-Z0-9]{3,6}", up.replace(" ", "")) and is_known_symbol(up.replace(" ", "")):
        return up.replace(" ", "")
    if k in _INDEX_WORDS:
        return _INDEX_WORDS[k]
    if k in _INDEX_NAME_LOOKUP:
        return _INDEX_NAME_LOOKUP[k]
    if k in _COUNTRY_LOOKUP:
        return "PAYS:" + _COUNTRY_LOOKUP[k]
    if k.upper().replace(" ", "") in SECTOR_LABELS:
        return "SECT:" + k.upper().replace(" ", "")
    th = THEMES.get(slug(raw))
    if th:
        return "THEME:" + slug(raw)
    # Dernier recours : table d'alias (noms de sociétés, pays, thèmes…).
    code = _entity_lookup(raw)
    if code:
        return code
    if strict:
        raise ValueError(f"cible inconnue : {value!r}")
    return None


def _theme_code(text: str) -> str | None:
    s = slug(text)
    if not s:
        return None
    if s in THEMES:
        return "THEME:" + s
    code = _entity_lookup(text, kinds=("theme",))
    if code:
        return code
    return "THEME:" + s  # thème libre : accepté tel quel (slug)


def _entity_lookup(text: str, kinds: tuple[str, ...] | None = None) -> str | None:
    """Résolution par la table d'alias de :mod:`brvm_alpha.notes.entities` (import tardif)."""
    try:
        from brvm_alpha.notes import entities
    except Exception:  # pragma: no cover - module absent ou en cours d'écriture
        return None
    try:
        return entities.resolve_alias(text, kinds=kinds)
    except Exception:  # pragma: no cover
        return None


def normalize_targets(values: Any, strict: bool = False) -> list[str]:
    """Liste de codes canoniques, sans doublon, dans l'ordre de saisie.

    ``values`` peut être une chaîne (séparateurs ``,`` ``;`` ``|``) ou un itérable.
    Les valeurs inconnues sont ignorées (ou lèvent ``ValueError`` si ``strict``).
    """
    if values is None:
        return []
    if isinstance(values, str):
        items: Iterable[Any] = [v for v in re.split(r"[;,|\n]+", values) if v.strip()]
    else:
        items = values
    out: list[str] = []
    for v in items:
        code = normalize_target(v, strict=strict)
        if code and code not in out:
            out.append(code)
    return out


def index_names(code: str) -> tuple[str, ...]:
    """Noms d'indices (``indices.parquet``) correspondant à un code ``IDX:*``."""
    if code in INDEX_TARGETS:
        return INDEX_TARGETS[code][1]
    if code.startswith("IDX:SECT:"):
        return SECTOR_INDEX_NAMES.get(code[9:], ())
    return ()


def target_label(code: str) -> str:
    """Libellé lisible d'un code de cible."""
    kind = target_kind(code)
    if kind == "market":
        return "marché (BRVM)"
    if kind == "index":
        if code in INDEX_TARGETS:
            return "indice " + INDEX_TARGETS[code][0]
        sec = code[9:]
        return "indice sectoriel " + SECTOR_LABELS.get(sec, sec)
    if kind == "country":
        return COUNTRY_NAMES.get(code[5:], code[5:])
    if kind == "sector":
        return "secteur " + SECTOR_LABELS.get(code[5:], code[5:])
    if kind == "theme":
        return "thème " + THEMES.get(code[6:], code[6:].lower().replace("_", " "))
    return code


def target_symbols(code: str, equities: pd.DataFrame | None = None, asof: Any = None) -> list[str] | None:
    """Symboles couverts par une cible, si on peut les déterminer sans information future.

    - symbole : lui-même ; pays : symboles de ce pays (``reference.country_of``) ;
    - secteur, Prestige, Principal : d'après la dernière séance ``<= asof`` de ``equities``
      (format long ``load_equities`` ou colonnes ``date, symbol, sector, compartment``) ;
    - Composite, Composite TR, ``MARCHE`` : toutes les actions cotées à la date ;
    - BRVM 30, BRVM 10, thèmes : ``None`` (composition non disponible dans le panel).
    """
    from brvm_alpha.reference import country_of

    kind = target_kind(code)
    if kind == "symbol":
        return [code]
    if kind == "theme" or code in ("IDX:BRVM-30", "IDX:BRVM-10"):
        return None
    universe = sorted(KNOWN_SYMBOLS - set(HISTORICAL_SYMBOLS))
    snap = None
    if equities is not None and len(equities):
        df = equities.reset_index() if "symbol" not in equities.columns else equities
        if "date" in df.columns:
            dates = pd.to_datetime(df["date"])
            if asof is not None:
                df = df[dates <= to_day(asof)]
                dates = pd.to_datetime(df["date"])
            if len(df):
                snap = df[dates == dates.max()]
        if snap is not None and len(snap):
            universe = sorted(snap["symbol"].unique())
    if kind == "country":
        return [s for s in universe if country_of(s) == code[5:]]
    if kind in ("market",) or code in ("IDX:BRVM-C", "IDX:BRVM-C-TR"):
        return universe
    if snap is None:
        return None
    if kind == "sector" or code.startswith("IDX:SECT:"):
        sec = code.split(":")[-1]
        return sorted(snap.loc[snap["sector"] == sec, "symbol"].unique())
    if code in ("IDX:PRESTIGE", "IDX:PRINCIPAL"):
        comp = code[4:]
        return sorted(snap.loc[snap["compartment"] == comp, "symbol"].unique())
    return None


# ---------------------------------------------------------------------------
# Dates et calendrier des séances
# ---------------------------------------------------------------------------

#: Jours fériés à date fixe observés dans tout le calendrier 2017-2026 (aucune séance) :
#: 1er janvier, 1er mai, 7 août (fête nationale CI), 15 août, 1er et 15 novembre, 25 décembre.
#: Les fêtes mobiles (Pâques, Tabaski, Ramadan, Mawlid…) ne sont pas modélisées.
FIXED_HOLIDAYS = frozenset({(1, 1), (5, 1), (8, 7), (8, 15), (11, 1), (11, 15), (12, 25)})

_FR_DATE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[ T]+(\d{1,2})[:h](\d{2})(?::(\d{2}))?)?\s*(?:utc|z|gmt)?\s*$", re.I)
_ISO_DATE_ONLY = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*$")


def is_date_only(value: Any) -> bool:
    """La valeur est-elle une date sans heure (ou un horodatage à 00:00:00 exactement) ?"""
    if value is None:
        return False
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return True
    if isinstance(value, str):
        s = value.strip()
        if _ISO_DATE_ONLY.match(s):
            return True
        m = _FR_DATE.match(s)
        if m and m.group(4) is None:
            return True
    ts = to_utc(value)
    if ts is None:
        return False
    return ts.hour == 0 and ts.minute == 0 and ts.second == 0 and ts.microsecond == 0 and ts.nanosecond == 0


def to_utc(value: Any) -> pd.Timestamp | None:
    """Horodatage UTC (``pd.Timestamp`` avec fuseau) ; ``None`` si vide.

    Une valeur sans fuseau est supposée en UTC. Les dates françaises ``JJ/MM/AAAA``
    (avec heure ``HH:MM`` ou ``HHhMM`` optionnelle) sont reconnues explicitement.
    """
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        m = _FR_DATE.match(s)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hh = int(m.group(4) or 0)
            mm = int(m.group(5) or 0)
            ss = int(m.group(6) or 0)
            return pd.Timestamp(year=y, month=mo, day=d, hour=hh, minute=mm, second=ss, tz="UTC")
        value = s
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"date illisible : {value!r}") from exc
    if ts is pd.NaT or pd.isna(ts):
        return None
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def asof_utc(value: Any) -> pd.Timestamp | None:
    """Instant d'une date d'analyse : une date seule désigne la **fin** de cette journée.

    Convention du panel : les données datées ``t`` sont connues en fin de séance ``t`` ;
    ``asof("2026-11-17")`` inclut donc tout ce qui a été publié le 17/11/2026.
    """
    ts = to_utc(value)
    if ts is None:
        return None
    if is_date_only(value):
        return ts.normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return ts


def utc_now() -> pd.Timestamp:
    """Instant présent en UTC (à la microseconde)."""
    return pd.Timestamp.now(tz="UTC")


#: Variable d'environnement du « mode horloge simulée » (tests) : un instant d'écriture
#: ``now`` antérieur à l'heure réelle y est accepté tel quel.
SIMULATED_CLOCK_ENV = "BRVM_ALPHA_SIMULATED_CLOCK"
#: Écart toléré entre un instant d'écriture fourni (``now``) et l'heure réelle.
BACKDATE_TOLERANCE = pd.Timedelta(minutes=10)
#: Étiquette des notes écrites avec un instant antérieur à l'heure réelle (reprise
#: d'historique) : elles sont exclues des vues strictes (``asof(strict=True)``).
RECONSTRUCTED_TAG = "reconstitue"


def simulated_clock() -> bool:
    """Le mode horloge simulée est-il actif (variable :data:`SIMULATED_CLOCK_ENV` à 1) ?"""
    return os.environ.get(SIMULATED_CLOCK_ENV, "").strip().lower() in ("1", "true", "oui", "yes")


def is_backdated(value: Any, reference: Any = None, tolerance: pd.Timedelta = BACKDATE_TOLERANCE) -> bool:
    """``value`` est-il antérieur à l'heure réelle (``reference``) de plus de ``tolerance`` ?

    Toujours ``False`` en mode horloge simulée (tests). Un instant d'écriture antidaté
    ne prouve pas que l'information était connue à cet instant : la note est alors
    marquée « reconstituée » et ne compte pas dans les vues strictes.
    """
    if simulated_clock():
        return False
    ts = to_utc(value)
    if ts is None:
        return False
    ref = utc_now() if reference is None else to_utc(reference)
    return ts < ref - tolerance


def to_day(value: Any) -> pd.Timestamp | None:
    """Date (``pd.Timestamp`` sans fuseau, à minuit) d'une valeur quelconque."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    ts = to_utc(value)
    if ts is None:
        return None
    return ts.tz_localize(None).normalize()


def _is_open_weekday(day: np.datetime64) -> bool:
    ts = pd.Timestamp(day)
    return ts.dayofweek < 5 and (ts.month, ts.day) not in FIXED_HOLIDAYS


class SessionCalendar:
    """Calendrier des séances BRVM, prolongé par les jours ouvrés là où il est inconnu.

    ``sessions`` peut être :
    - le résultat de ``store.load_sessions`` (colonnes ``date``, ``gap_start``, ``gap_end``) :
      les séances sans BOC (date inconnue) sont remplacées par les jours ouvrés de la lacune ;
    - une liste, un ``Index`` ou une ``Series`` de dates de séances (liste exhaustive) ;
    - ``None`` : jours ouvrés (lundi-vendredi hors fériés fixes).

    Avant la première et après la dernière séance connue, les jours ouvrés font foi.
    """

    def __init__(self, sessions: Any = None):
        self.dates = np.array([], dtype="datetime64[D]")
        self.gaps: list[tuple[np.datetime64, np.datetime64]] = []
        if sessions is None:
            return
        if isinstance(sessions, SessionCalendar):
            self.dates, self.gaps = sessions.dates, sessions.gaps
            return
        if isinstance(sessions, pd.DataFrame):
            df = sessions
            if "date" not in df.columns:
                raise ValueError("le calendrier doit avoir une colonne 'date'")
            d = pd.to_datetime(df["date"], errors="coerce")
            self.dates = np.unique(d.dropna().dt.normalize().values.astype("datetime64[D]"))
            if "gap_start" in df.columns and "gap_end" in df.columns:
                miss = df[d.isna()]
                gs = pd.to_datetime(miss["gap_start"], errors="coerce")
                ge = pd.to_datetime(miss["gap_end"], errors="coerce")
                seen = set()
                for a, b in zip(gs, ge):
                    a = np.datetime64(a, "D") if pd.notna(a) else None
                    b = np.datetime64(b, "D") if pd.notna(b) else None
                    if a is None and b is None:
                        continue
                    lo = a if a is not None else np.datetime64("1900-01-01")
                    hi = b if b is not None else np.datetime64("2999-12-31")
                    if (lo, hi) not in seen:
                        seen.add((lo, hi))
                        self.gaps.append((lo, hi))
            return
        values = pd.to_datetime(pd.Index(list(sessions)), errors="coerce")
        self.dates = np.unique(values.dropna().normalize().values.astype("datetime64[D]"))

    # -- requêtes -----------------------------------------------------------
    def _unknown(self, day: np.datetime64) -> bool:
        """Le jour est-il hors de la partie connue du calendrier ?"""
        if len(self.dates) == 0:
            return True
        if day < self.dates[0] or day > self.dates[-1]:
            return True
        return any(lo < day < hi for lo, hi in self.gaps)

    def is_session(self, day: Any) -> bool:
        """Le jour est-il une séance (connue, ou jour ouvré dans une zone inconnue) ?"""
        d = np.datetime64(pd.Timestamp(to_day(day)), "D")
        if self._unknown(d):
            return _is_open_weekday(d)
        i = np.searchsorted(self.dates, d)
        return bool(i < len(self.dates) and self.dates[i] == d)

    def next_session(self, day: Any, inclusive: bool = False) -> pd.Timestamp:
        """Première séance ``>= day`` (``inclusive``) ou ``> day``."""
        d = np.datetime64(pd.Timestamp(to_day(day)), "D")
        start = d if inclusive else d + np.timedelta64(1, "D")
        known = None
        if len(self.dates):
            i = np.searchsorted(self.dates, start, side="left")
            if i < len(self.dates):
                known = self.dates[i]
        cur = start
        limit = known if known is not None else start + np.timedelta64(30, "D")
        while cur < limit or known is None:
            if self._unknown(cur) and _is_open_weekday(cur):
                return pd.Timestamp(cur)
            cur = cur + np.timedelta64(1, "D")
            if known is None and cur > limit:  # pragma: no cover - garde-fou
                break
        return pd.Timestamp(known)

    def sessions_between(self, start: Any, end: Any) -> int:
        """Nombre de séances dans ``]start, end]`` (approximation par jours ouvrés hors calendrier)."""
        a = to_day(start)
        b = to_day(end)
        if a is None or b is None or b <= a:
            return 0
        n = 0
        cur = self.next_session(a)
        while cur <= b:
            n += 1
            cur = self.next_session(cur)
        return n


_CAL_CACHE: dict[int, tuple[Any, SessionCalendar]] = {}
_DEFAULT_SESSIONS: list[Any] = []  # [valeur] si fixé par set_default_sessions


def _calendar(sessions: Any) -> SessionCalendar:
    if isinstance(sessions, SessionCalendar):
        return sessions
    if sessions is None:
        return default_calendar()
    key = id(sessions)
    hit = _CAL_CACHE.get(key)
    if hit is not None and hit[0] is sessions:
        return hit[1]
    cal = SessionCalendar(sessions)
    if len(_CAL_CACHE) > 16:
        _CAL_CACHE.clear()
    _CAL_CACHE[key] = (sessions, cal)
    return cal


def default_panel_dir() -> Path:
    """Répertoire du panel : ``<dépôt>/data/panel``, ou ``<BRVM_ALPHA_DONNEES>/panel`` si la variable est posée."""
    return _paths.PANEL_DIR


@lru_cache(maxsize=1)
def _load_default_calendar() -> SessionCalendar:
    path = default_panel_dir() / "sessions.parquet"
    if not path.exists():
        return SessionCalendar(None)
    try:
        df = pd.read_parquet(path)
    except Exception:  # pragma: no cover - fichier illisible : jours ouvrés
        return SessionCalendar(None)
    return SessionCalendar(df)


def default_calendar() -> SessionCalendar:
    """Calendrier par défaut : ``set_default_sessions`` sinon ``data/panel/sessions.parquet``."""
    if _DEFAULT_SESSIONS:
        val = _DEFAULT_SESSIONS[0]
        return val if isinstance(val, SessionCalendar) else SessionCalendar(val)
    return _load_default_calendar()


def set_default_sessions(sessions: Any) -> None:
    """Fixe le calendrier par défaut (``None`` : revenir au fichier du panel)."""
    _DEFAULT_SESSIONS.clear()
    if sessions is not None:
        _DEFAULT_SESSIONS.append(SessionCalendar(sessions))


def first_tradable_session(
    published_at: Any,
    sessions: Any = None,
    date_only: bool | None = None,
    cutoff: _dt.time = NEWS_CUTOFF_UTC,
) -> pd.Timestamp | None:
    """Première séance négociable après la publication (document 07 §2.3).

    - avant ``cutoff`` (09h00 UTC) un jour de séance : la séance du jour ;
    - sinon (pendant ou après la séance, week-end, férié) : la séance suivante ;
    - date sans heure (``date_only``, déduit de la valeur si ``None``) : séance suivante.

    ``sessions`` : calendrier (``load_sessions``, liste de dates, ``SessionCalendar``) ;
    ``None`` : calendrier par défaut, prolongé par les jours ouvrés.
    Renvoie une date sans fuseau (minuit), ou ``None`` si ``published_at`` est vide.
    """
    ts = to_utc(published_at)
    if ts is None:
        return None
    if date_only is None:
        date_only = is_date_only(published_at)
    cal = _calendar(sessions)
    day = ts.tz_localize(None).normalize()
    if not date_only and ts.time() < cutoff and cal.is_session(day):
        return day
    return cal.next_session(day, inclusive=False)


def first_tradable_floor(published_at: Any, date_only: bool | None = None,
                         cutoff: _dt.time = NEWS_CUTOFF_UTC) -> pd.Timestamp | None:
    """Borne inférieure de ``first_tradable_session``, valable quel que soit le calendrier.

    Le jour de publication si elle a lieu avant ``cutoff`` (09h00 UTC), sinon le
    lendemain (date seule comprise). Aucune séance négociable ne peut la précéder.
    """
    ts = to_utc(published_at)
    if ts is None:
        return None
    if date_only is None:
        date_only = is_date_only(published_at)
    day = ts.tz_localize(None).normalize()
    if not date_only and ts.time() < cutoff:
        return day
    return day + pd.Timedelta(days=1)


# ---------------------------------------------------------------------------
# Identifiants
# ---------------------------------------------------------------------------


def _norm_for_id(text: Any) -> str:
    return re.sub(r"\s+", " ", fold(str(text or ""))).strip()


def make_note_id(
    source: str,
    url: str = "",
    title: str = "",
    text: str = "",
    published_at: Any = None,
    author: str = "",
    stance: str | None = None,
    conviction: Any = None,
) -> str:
    """Identifiant stable (sha1, 40 caractères hexadécimaux).

    - pièce **collectée** (URL fournie, ni ``source="manual"`` ni ``author="analyste"``) :
      ``sha1(source | url | titre normalisé)`` — la même pièce collectée deux fois a le
      même identifiant (déduplication) ;
    - note **de l'analyste** (``source="manual"`` ou ``author="analyste"``), ou sans URL :
      ``sha1(source | auteur | titre | texte | published_at [| url] [| avis | conviction])``
      — deux notes manuelles différentes qui citent la même pièce source restent
      distinctes, et deux notes identiques saisies à des instants différents aussi.
    Le titre et le texte sont normalisés (casse, accents, espaces) avant hachage. L'URL,
    l'avis et la conviction n'entrent dans la clé que s'ils sont renseignés (les
    identifiants des notes manuelles sans URL ni avis sont inchangés).
    """
    url = (url or "").strip()
    manual = (source or "") == "manual" or (author or "") == "analyste"
    if url and not manual:
        key = "|".join([source or "", url, _norm_for_id(title)])
    else:
        ts = to_utc(published_at)
        parts = [source or "", author or "", _norm_for_id(title), _norm_for_id(text),
                 ts.isoformat() if ts is not None else ""]
        if url:
            parts.append("url=" + url)
        if stance:
            parts.append("avis=" + str(stance))
        if conviction is not None and not (isinstance(conviction, float) and np.isnan(conviction)):
            parts.append("conviction=" + str(int(round(float(conviction)))))
        key = "|".join(parts)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------


def jsonable(value: Any) -> Any:
    """Convertit récursivement en types JSON (numpy, pandas, dates, ensembles…)."""
    if value is None or isinstance(value, (bool, str)):
        return value
    # Date ou valeur manquante (``pd.NaT``, ``pd.NA``) : ``pd.NaT`` est une instance de ``datetime``
    # sans être un ``Timestamp`` et ``pd.Timestamp(pd.NaT)`` rend ``pd.NaT`` ; sans ce test la branche
    # « datetime » se rappelait sans fin (« indices dossier --format json », recette du 22/11/2026).
    if value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return None if (np.isnan(f) or np.isinf(f)) else f
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        if value.tzinfo is None and value == value.normalize():
            return value.strftime("%Y-%m-%d")
        return value.isoformat()
    if isinstance(value, (_dt.datetime, _dt.date, np.datetime64)):
        ts = pd.Timestamp(value)
        return None if ts is pd.NaT else jsonable(ts)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset, np.ndarray, pd.Index, pd.Series)):
        seq = list(value)
        if isinstance(value, (set, frozenset)):
            seq = sorted(seq, key=str)
        return [jsonable(v) for v in seq]
    if hasattr(value, "to_dict"):
        return jsonable(value.to_dict())
    return str(value)


def _iso(ts: pd.Timestamp | None) -> str | None:
    return None if ts is None else ts.isoformat()


# ---------------------------------------------------------------------------
# Normalisation des champs
# ---------------------------------------------------------------------------

_STANCE_MAP = {
    "haussier": "haussier", "haussiere": "haussier", "hausse": "haussier", "bullish": "haussier",
    "achat": "haussier", "acheter": "haussier", "positif": "haussier", "positive": "haussier",
    "surponderer": "haussier", "+": "haussier", "+1": "haussier", "1": "haussier", "buy": "haussier",
    "baissier": "baissier", "baissiere": "baissier", "baisse": "baissier", "bearish": "baissier",
    "vente": "baissier", "vendre": "baissier", "negatif": "baissier", "negative": "baissier",
    "sous ponderer": "baissier", "-": "baissier", "-1": "baissier", "sell": "baissier",
    "neutre": "neutre", "neutral": "neutre", "conserver": "neutre", "0": "neutre", "hold": "neutre",
}


def normalize_stance(value: Any) -> str | None:
    """``haussier`` | ``baissier`` | ``neutre`` | ``None`` (accepte achat/vente, +/-, anglais)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    k = re.sub(r"[^a-z0-9+\-]+", " ", fold(s)).strip()
    if k in _STANCE_MAP:
        return _STANCE_MAP[k]
    raise ValueError(f"stance inconnue : {value!r} (attendu : haussier, baissier, neutre)")


def stance_sign(stance: str | None) -> int:
    """+1 haussier, −1 baissier, 0 sinon."""
    return {"haussier": 1, "baissier": -1}.get(stance or "", 0)


def normalize_event_type(value: Any) -> str | None:
    """Type d'événement en majuscules (types connus : :data:`EVENT_TYPES`)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    up = slug(s)
    if up in EVENT_TYPES:
        return up
    aliases = {
        "DIVIDENDE": "DIV_NOTICE", "DIVIDENDES": "DIV_NOTICE", "RESULTATS": "RES_ANNUAL",
        "RESULTATS_ANNUELS": "RES_ANNUAL", "ETATS_FINANCIERS": "RES_ANNUAL", "SEMESTRE": "RES_S1",
        "ALERTE_SUR_RESULTATS": "PROFIT_WARNING", "NOTATION": "RATING", "AG": "AG_CONVOCATION",
        "NOMINATION": "MGMT_CHANGE", "OPA": "TAKEOVER", "OPR": "TAKEOVER", "IPO": "OPV_IPO",
        "OPV": "OPV_IPO", "SUSPENDU": "SUSPENSION", "REPRISE": "RESUMPTION", "RADIATION": "DELISTING",
        "POLITICAL": "POLITIQUE", "SECURITY": "SECURITE", "COMMODITIES": "MATIERES_PREMIERES",
        "PRESSE": "PRESS", "AUTRE": "OTHER", "NOTE": "MANUAL",
    }
    return aliases.get(up, up)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in re.split(r"[;,|]+", value) if v.strip()]
    if isinstance(value, float) and np.isnan(value):
        return []
    return list(value)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class NoteAnalysis:
    """Résultat de l'analyse d'une note (``analyze.analyze_note``).

    ``tone``, ``s_num`` et ``score`` sont dans [−1, 1] ; ``materiality`` et
    ``confidence`` dans [0, 1]. ``s_num`` vaut 0 quand aucun chiffre n'a été extrait
    (voir ``extracted``). Aucune valeur n'est une garantie : c'est une lecture
    factuelle, avec son degré de confiance.
    """

    targets: list[str] = field(default_factory=list)
    event_type: str = "OTHER"
    tone: float = 0.0
    s_num: float = 0.0
    score: float = 0.0
    materiality: float = 0.0
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    extracted: dict[str, Any] = field(default_factory=dict)
    reading: str = ""
    matched_terms: list[dict[str, Any]] = field(default_factory=list)
    # Champs complémentaires (facultatifs) -------------------------------
    primary_target: str | None = None
    components: dict[str, Any] = field(default_factory=dict)
    contradiction: bool = False
    warnings: list[str] = field(default_factory=list)
    version: str = "notes-analyze/1"

    def to_dict(self) -> dict[str, Any]:
        """Dictionnaire sérialisable en JSON."""
        return jsonable(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "NoteAnalysis":
        """Reconstruit une analyse (clés inconnues ignorées)."""
        data = dict(data or {})
        names = {f.name for f in fields(cls)}
        kw = {k: v for k, v in data.items() if k in names}
        return cls(**kw)


_NOTE_FIELD_ORDER = (
    "note_id", "created_at", "published_at", "first_tradable_session", "author", "source", "url",
    "title", "text", "targets", "event_type", "stance", "conviction", "horizon_days", "tags",
    "status", "version", "analysis", "published_precision", "recorded_at", "targets_unknown",
)


@dataclass
class Note:
    """Une information sur un titre, un indice, un pays, un secteur, un thème ou le marché.

    Tous les horodatages sont en UTC. ``published_at`` (quand l'information est devenue
    publique) vaut ``created_at`` par défaut ; ``first_tradable_session`` est calculée
    à partir de ``published_at`` si elle n'est pas fournie. ``note_id`` est un sha1
    stable (voir :func:`make_note_id`).

    Champs ajoutés au contrat (facultatifs) :
    - ``published_precision`` : ``"datetime"`` ou ``"date"`` (date seule : l'information
      est réputée connue en fin de journée) ;
    - ``recorded_at`` : instant d'écriture de cette version dans le journal (renseigné
      par ``NoteStore``) ;
    - ``targets_unknown`` : cibles saisies **non reconnues** (faute de frappe, titre hors
      liste et hors panel). Elles ne sont jamais remplacées en silence par les cibles
      détectées dans le texte : une note de l'analyste dont toutes les cibles sont
      inconnues ne se propage à aucun titre (voir ``signals.effective_targets``).

    ``first_tradable_session`` fournie n'est jamais antérieure à la règle de coupure
    appliquée à ``published_at`` (:func:`first_tradable_floor`) : une valeur plus tôt est
    remplacée par la séance calculée.
    """

    note_id: str = ""
    created_at: Any = None
    published_at: Any = None
    first_tradable_session: Any = None
    author: str = "analyste"
    source: str = "manual"
    url: str = ""
    title: str = ""
    text: str = ""
    targets: list[str] = field(default_factory=list)
    event_type: str | None = None
    stance: str | None = None
    conviction: int | None = None
    horizon_days: int = DEFAULT_HORIZON_DAYS
    tags: list[str] = field(default_factory=list)
    status: str = "active"
    version: int = 1
    analysis: dict[str, Any] | None = None
    published_precision: str | None = None
    recorded_at: Any = None
    targets_unknown: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Auteur, source, statut.
        self.author = (self.author or "analyste").strip().lower()
        if self.author not in AUTHORS:
            raise ValueError(f"author invalide : {self.author!r} (attendu : {', '.join(AUTHORS)})")
        self.source = (self.source or "manual").strip().lower()
        if self.source not in SOURCES:
            raise ValueError(f"source invalide : {self.source!r} (attendu : {', '.join(SOURCES)})")
        self.status = (self.status or "active").strip().lower()
        if self.status not in STATUSES:
            raise ValueError(f"status invalide : {self.status!r} (attendu : active, archived)")
        self.url = (self.url or "").strip()
        self.title = str(self.title or "").strip()
        self.text = str(self.text or "")
        if not self.title and not self.text.strip():
            raise ValueError("une note doit avoir un titre ou un texte")
        # Horodatages.
        created = to_utc(self.created_at)
        if created is None:
            created = utc_now()
        self.created_at = created
        raw_pub = self.published_at if self.published_at not in (None, "") else None
        if self.published_precision not in (None, "date", "datetime"):
            raise ValueError("published_precision : 'date' ou 'datetime'")
        if raw_pub is None:
            self.published_at = created
            if self.published_precision is None:
                self.published_precision = "datetime"
        else:
            self.published_at = to_utc(raw_pub)
            if self.published_precision is None:
                self.published_precision = "date" if is_date_only(raw_pub) else "datetime"
        self.recorded_at = to_utc(self.recorded_at)
        # Cibles, type, avis de l'analyste. Une cible non reconnue est conservée à part
        # (``targets_unknown``) au lieu de disparaître sans avertissement.
        codes: list[str] = []
        unknown: list[str] = [str(u).strip() for u in _as_list(self.targets_unknown) if str(u).strip()]
        for v in _as_list(self.targets):
            code = normalize_target(v)
            if code is None:
                raw = str(v).strip() if v is not None else ""
                if raw and raw not in unknown:
                    unknown.append(raw)
            elif code not in codes:
                codes.append(code)
        self.targets = codes
        self.targets_unknown = unknown
        self.event_type = normalize_event_type(self.event_type)
        self.stance = normalize_stance(self.stance)
        if self.conviction is not None and not (isinstance(self.conviction, float) and np.isnan(self.conviction)):
            c = int(round(float(self.conviction)))
            if not 1 <= c <= 5:
                raise ValueError("conviction : entier de 1 à 5")
            self.conviction = c
        else:
            self.conviction = None
        self.horizon_days = int(self.horizon_days if self.horizon_days not in (None, "") else DEFAULT_HORIZON_DAYS)
        if self.horizon_days <= 0:
            raise ValueError("horizon_days doit être > 0")
        self.tags = [str(t).strip() for t in _as_list(self.tags) if str(t).strip()]
        self.version = int(self.version or 1)
        if self.analysis is not None and isinstance(self.analysis, NoteAnalysis):
            self.analysis = self.analysis.to_dict()
        # Séance négociable : jamais avant la coupure de 09h00 appliquée à published_at.
        date_only = self.published_precision == "date"
        given = None if self.first_tradable_session in (None, "") else to_day(self.first_tradable_session)
        floor = first_tradable_floor(self.published_at, date_only=date_only)
        if given is None or (floor is not None and given < floor):
            self.first_tradable_session = first_tradable_session(self.published_at, date_only=date_only)
        else:
            self.first_tradable_session = given
        if not self.note_id:
            self.note_id = self.compute_id()

    # -- identifiant et dates ------------------------------------------------
    def compute_id(self) -> str:
        """Identifiant stable de la note (voir :func:`make_note_id`)."""
        return make_note_id(self.source, self.url, self.title, self.text, self.published_at, self.author,
                            stance=self.stance, conviction=self.conviction)

    @property
    def published_effective(self) -> pd.Timestamp:
        """Instant prudent de publication : fin de journée pour une date seule."""
        if self.published_precision == "date":
            return self.published_at.normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        return self.published_at

    @property
    def known_at(self) -> pd.Timestamp:
        """Instant à partir duquel la note est connue : max(created_at, publication prudente)."""
        return max(self.created_at, self.published_effective)

    def recompute_first_tradable(self, sessions: Any = None) -> pd.Timestamp | None:
        """Recalcule ``first_tradable_session`` avec un calendrier donné."""
        self.first_tradable_session = first_tradable_session(
            self.published_at, sessions=sessions, date_only=self.published_precision == "date"
        )
        return self.first_tradable_session

    @property
    def all_targets(self) -> list[str]:
        """Cibles manuelles puis cibles détectées par l'analyse."""
        out = list(self.targets)
        for t in (self.analysis or {}).get("targets", []) or []:
            if t not in out:
                out.append(t)
        return out

    # -- sérialisation -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Dictionnaire JSON (horodatages ISO 8601 UTC, séance au format AAAA-MM-JJ)."""
        d: dict[str, Any] = {}
        for name in _NOTE_FIELD_ORDER:
            v = getattr(self, name)
            if name in ("created_at", "published_at", "recorded_at"):
                d[name] = _iso(v)
            elif name == "first_tradable_session":
                d[name] = None if v is None else pd.Timestamp(v).strftime("%Y-%m-%d")
            else:
                d[name] = jsonable(v)
        return d

    def to_json(self) -> str:
        """Une ligne JSON (UTF-8 lisible)."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Note":
        """Reconstruit une note ; les clés inconnues sont ignorées, ``note_id`` est conservé."""
        names = {f.name for f in fields(cls)}
        kw = {k: v for k, v in dict(data).items() if k in names}
        return cls(**kw)

    @classmethod
    def from_json(cls, line: str) -> "Note":
        """Reconstruit une note à partir d'une ligne JSON."""
        return cls.from_dict(json.loads(line))

    def copy(self, **changes: Any) -> "Note":
        """Copie modifiée (re-validée) ; ``note_id`` est conservé.

        Changer ``published_at`` (ou ``published_precision``) sans fournir
        ``first_tradable_session`` recalcule la séance négociable ; changer
        ``published_at`` sans ``published_precision`` la redéduit de la nouvelle valeur.
        """
        d = self.to_dict()
        if ("published_at" in changes or "published_precision" in changes) and "first_tradable_session" not in changes:
            d["first_tradable_session"] = None
        if "published_at" in changes and "published_precision" not in changes:
            d["published_precision"] = None
        d.update(changes)
        return Note.from_dict(d)


__all__ = [
    "AUTHORS", "SOURCES", "STANCES", "STATUSES", "EVENT_TYPES", "RISK_FLAGS", "INDEX_TARGETS",
    "SECTOR_LABELS", "SECTOR_INDEX_NAMES", "THEMES", "KNOWN_SYMBOLS", "FIXED_HOLIDAYS",
    "NEWS_CUTOFF_UTC", "Note", "NoteAnalysis", "SessionCalendar", "first_tradable_session", "first_tradable_floor",
    "panel_symbols", "is_known_symbol", "simulated_clock", "is_backdated", "SIMULATED_CLOCK_ENV",
    "BACKDATE_TOLERANCE", "RECONSTRUCTED_TAG",
    "normalize_target", "normalize_targets", "target_kind", "target_label", "index_names",
    "target_symbols", "make_note_id", "to_utc", "to_day", "is_date_only", "fold",
    "fold_with_map", "slug", "normalize_stance", "stance_sign", "normalize_event_type",
    "set_default_sessions", "default_calendar", "jsonable", "asof_utc", "utc_now",
]
