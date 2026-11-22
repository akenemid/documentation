"""Recherche automatique d'informations pour les notes de l'analyste.

Le module collecte, **poliment et sans contournement**, les informations publiques
sur les titres, les indices, les pays et le marché de la BRVM, puis les convertit
en notes (:class:`brvm_alpha.notes.model.Note`) analysées et ajoutées au journal.

Il est organisé en deux couches :

(a) **collecteurs** (testables seuls, sans le modèle de notes) : ils renvoient des
    dictionnaires bruts (« éléments ») avec le titre, l'URL de la page, l'URL du
    document, la date du document, l'émetteur et son symbole s'il est reconnu, le
    type de liste, un texte éventuel et des champs structurés (``extra``) :

    - listes Drupal de www.brvm.org (annonces des émetteurs, opérations sur titres,
      avis), avec pagination ``?page=N`` arrêtée à la première URL déjà connue ou à
      la date ``since`` (document 07, §1.2-1.3) ;
    - pages « rapports-societe-cotes/<slug> » d'un émetteur ;
    - sections d'événements des BOC locaux ``data/boc_text/*.txt.gz`` : calendrier
      des AG, « OPERATIONS EN COURS », « AVIS », « COMMUNIQUES » et mentions
      « SP » du tableau des cours (document 07, §1.4) ;
    - texte des PDF (pdftotext, repli pdfplumber ; scan détecté si moins de
      200 caractères par page : ``ocr_needed``, pas d'OCR obligatoire).

(b) **conversion** : :func:`run_research` et :func:`fetch_url_note` transforment les
    éléments en notes, les dédupliquent, les analysent (``analyze.analyze_note``) et
    les ajoutent au :class:`~brvm_alpha.notes.store.NoteStore`. Les modules du
    paquet ``notes`` sont importés à l'intérieur des fonctions : la couche (a) ne
    dépend pas d'eux.

Politesse et sûreté (document 07, §6.2 et §6.7) :

- seul www.brvm.org est interrogé automatiquement ; Sika Finance, Richbourse et la
  presse sont **désactivés par défaut** ;
- ``robots.txt`` est lu et respecté (``urllib.robotparser``), ``Crawl-delay: 10`` de
  brvm.org compris (au moins 10 s entre deux requêtes vers ce site) ;
- User-Agent explicite, cache disque avec ``ETag`` / ``If-Modified-Since``,
  quota ``max_requests`` ;
- **arrêt définitif** de la session au premier HTTP 403 ou 429 ; 3 essais avec
  attente exponentielle sur 5xx, puis arrêt ;
- journal de chaque requête dans ``data/notes/fetch_log.jsonl`` ;
- mode ``offline=True`` : seul le cache disque est lu, aucune requête réseau.

Point-in-time (document 07, §2.3, §6.3 et §6.8) : une information n'agit qu'à partir
de ``first_tradable_session``, la première séance dont le fixing d'ouverture (09h45 UTC)
suit sa publication. Règle unique : publiée **avant 09h00 UTC** un jour de séance,
elle agit le jour même ; sinon à la séance suivante. Concrètement :

- avis horodaté (date et heure de la liste des avis) : l'heure fait foi ;
- BOC : publié le soir (19h00 UTC retenu), il agit à la séance suivante ;
- date de mise en ligne sans heure (colonne d'une liste) : réputée connue en fin de
  journée, donc séance suivante ;
- date lue seulement dans le nom du PDF (date du document, pas de sa mise en ligne) :
  reportée d'une séance par prudence (``doc_date`` + 1 séance) ;
- date d'avis suspecte (week-end, année fausse...) : bornée par ``ex_date - 10 jours`` ;
- l'heure de collecte borne toujours la publication (un élément vu à 03h40 était en
  ligne à 03h40) ; deux sources pour un même document : la plus tôt des deux bornes.

Aucune « garantie » n'est donnée : ces notes alimentent un score, une confiance et
une lecture factuelle ; leur poids dans le portefeuille est borné et mesuré.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import gzip
import hashlib
import html as html_lib
import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib import robotparser
from urllib.parse import parse_qs, urljoin, urlparse

import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BASE_URL = "https://www.brvm.org"
BRVM_HOST = "www.brvm.org"
USER_AGENT = "brvm-alpha/0.1 (outil d'analyse personnel)"
#: Délai minimal entre deux requêtes vers un même site (s). brvm.org impose 10 s.
DEFAULT_DELAY_S = 10.0
#: Délais planchers par site, quel que soit le réglage (robots.txt de brvm.org).
HOST_MIN_DELAY_S = {BRVM_HOST: 10.0, "brvm.org": 10.0}
#: Codes HTTP qui arrêtent définitivement la session (aucun nouvel essai).
STOP_STATUSES = frozenset({403, 429})
MAX_RETRIES = 3
BACKOFF_S = 10.0

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_NOTES_DIR = DATA_DIR / "notes"
DEFAULT_BOC_DIR = DATA_DIR / "boc_text"
DEFAULT_PANEL_DIR = DATA_DIR / "panel"

#: Heure de coupure des nouvelles (document 07, §2.3, harmonisée le 22/11/2026).
NEWS_CUTOFF_UTC = dt.time(9, 0)
#: Heure de publication retenue pour un BOC (mis en ligne le soir, collecté vers 19h UTC).
BOC_PUBLICATION_UTC = dt.time(19, 0)
#: Seuil de caractères par page en dessous duquel un PDF est considéré comme un scan.
OCR_MIN_CHARS_PER_PAGE = 200
#: Longueur maximale du texte conservé dans une note.
MAX_TEXT_CHARS = 20_000
#: Écart p10 avis de paiement -> détachement (document 07, §2.1) : borne prudente.
NOTICE_TO_EX_MIN_DAYS = 10

#: Sources désactivées par défaut (document 07, §1.1 et §6.7) : pas de contournement.
DISABLED_DOMAINS: dict[str, str] = {
    "sikafinance.com": "Sika Finance renvoie une page de protection Cloudflare (HTTP 403)",
    "richbourse.com": "Richbourse a bloqué la collecte (HTTP 403, « garde anti-aspiration »)",
    "financialafrik.com": "presse : désactivée par défaut",
    "agenceecofin.com": "presse : désactivée par défaut",
    "abidjan.net": "presse : désactivée par défaut",
}


@dataclass(frozen=True)
class BrvmList:
    """Une liste Drupal de www.brvm.org (document 07, §1.2)."""

    key: str
    path: str
    kind: str  # "annonce" | "esv" | "avis"
    label: str
    event_hint: str | None = None


#: Listes collectées, dans l'ordre de priorité : une liste « esv » (champs structurés)
#: passe avant l'avis qui porte le même PDF, ce qui garde la version la plus riche.
BRVM_LISTS: dict[str, BrvmList] = {
    b.key: b
    for b in (
        BrvmList("dividendes", "/fr/esv/paiement-de-dividendes", "esv", "Paiement de dividendes", "DIV_NOTICE"),
        BrvmList("augmentation_capital", "/fr/esv/augmentation-de-capital", "esv", "Augmentations de capital", "CAP_INC"),
        BrvmList("fractionnement", "/fr/esv/fractionnement", "esv", "Fractionnements", "SPLIT"),
        BrvmList("radiation", "/fr/esv/radiation", "esv", "Radiations", "DELISTING"),
        BrvmList("communiques", "/fr/emetteurs/type-annonces/communiques", "annonce", "Communiqués"),
        BrvmList("convocations", "/fr/emetteurs/type-annonces/convocations-assemblees-generales", "annonce",
                 "Convocations d'AG", "AG_CONVOCATION"),
        BrvmList("resolutions", "/fr/emetteurs/type-annonces/projets-de-resolution", "annonce",
                 "Projets de résolution", "AG_RESOLUTIONS"),
        BrvmList("dirigeants", "/fr/emetteurs/type-annonces/changements-de-dirigeants", "annonce",
                 "Changements de dirigeants", "MGMT_CHANGE"),
        BrvmList("seuils", "/fr/emetteurs/type-annonces/franchissements-de-seuil", "annonce",
                 "Franchissements de seuil", "THRESHOLD"),
        BrvmList("notations", "/fr/emetteurs/type-annonces/notations-financieres", "annonce",
                 "Notations financières", "RATING"),
        BrvmList("avis", "/fr/marche/avis-et-publications/avis", "avis", "Avis de la BRVM"),
    )
}
#: Listes publiées par la BRVM elle-même : un élément sans émetteur y concerne le marché.
MARKET_LISTS = frozenset({"avis", "boc_avis", "boc_operations"})
#: Listes dont le type d'événement est certain (il prime sur la classification du titre).
STRUCTURAL_LISTS = frozenset({"dividendes", "augmentation_capital", "fractionnement", "radiation"})

ISSUERS_INDEX_PATH = "/fr/rapports-societes-cotees"
ISSUER_REPORTS_PATH = "/fr/rapports-societe-cotes/{slug}"

#: Pages « rapports-societe-cotes/<slug> » des 48 actions (index lu le 22/11/2026,
#: 75 émetteurs sur 3 pages). Le premier slug est la page principale ; les suivants
#: sont d'anciennes pages (changement de nom) lues seulement avec ``all_slugs=True``.
ISSUER_SLUGS: dict[str, tuple[str, ...]] = {
    "ABJC": ("servair-abidjan-ci",), "BBGC": ("bbgci",), "BICB": ("biic",), "BICC": ("bici-ci",),
    "BNBC": ("bernabe-ci",), "BOAB": ("bank-africa-bn",), "BOABF": ("bank-africa-bf",),
    "BOAC": ("bank-africa-ci",), "BOAM": ("bank-africa-ml",), "BOAN": ("bank-africa-ng",),
    "BOAS": ("bank-africa-sn",), "CABC": ("sicable",), "CBIBF": ("coris-bank-international",),
    "CFAC": ("cfao-motors-ci",), "CIEC": ("cie-ci",), "ECOC": ("ecobank-ci",), "ETIT": ("ecobank-tg",),
    "FTSC": ("filtisac-ci",), "LNBB": ("lnb",), "NEIC": ("nei-ceda-ci",), "NSBC": ("nsbc",),
    "NTLC": ("nestle-ci",), "ONTBF": ("onatel-bf",), "ORAC": ("orange-ci", "cote-divoire-telecom"),
    "ORGT": ("oragroup",), "PALC": ("palm-ci",), "PRSC": ("tractafric-ci",), "SAFC": ("safca-ci",),
    "SCRC": ("sucrivoire",), "SDCC": ("sodeci",), "SDSC": ("bollore-transport-logistics",),
    "SEMC": ("crown-siem-ci",), "SGBC": ("sgb-ci", "sgci"), "SHEC": ("vivo-energy-ci",),
    "SIBC": ("sib",), "SICC": ("sicor",), "SIVC": ("air-liquide-ci",), "SLBC": ("solibra",),
    "SMBC": ("smb",), "SNTS": ("sonatel",), "SOGC": ("sogb",), "SPHC": ("saph-ci",),
    "STAC": ("setao-ci",), "STBC": ("sitab",), "TTLC": ("total",),
    "TTLS": ("totalenergies-marketing-sn", "total-senegal-sa"), "UNLC": ("unilever-ci",),
    "UNXC": ("uniwax-ci",), "SVOC": ("movis-ci",), "TTRC": ("tritraf-ci",),
}

#: Libellés (actuels et historiques) des émetteurs -> symbole. Les colonnes
#: « Société » de brvm.org portent souvent d'anciens noms (document 07, §1.2).
ISSUER_ALIASES: dict[str, tuple[str, ...]] = {
    "ABJC": ("SERVAIR ABIDJAN CI", "SERVAIR ABIDJAN", "SERVAIR"),
    "BBGC": ("BRIDGE BANK GROUP CI", "BRIDGE BANK GROUPE CI", "BRIGDE BANK GROUPE CI", "BRIDGE BANK", "BBGCI"),
    "BICB": ("BIIC BN", "BIIC BENIN", "BIIC", "BANQUE INTERNATIONALE POUR L'INDUSTRIE ET LE COMMERCE"),
    "BICC": ("BICI CI", "BICI COTE D'IVOIRE", "BICICI", "BICI",
             "BANQUE INTERNATIONALE POUR LE COMMERCE ET L'INDUSTRIE DE COTE D'IVOIRE"),
    "BNBC": ("BERNABE CI", "BERNABE COTE D'IVOIRE", "BERNABE"),
    "BOAB": ("BANK OF AFRICA BN", "BANK OF AFRICA BENIN", "BANK OF AFRICA - BENIN", "BOA BN", "BOA BENIN"),
    "BOABF": ("BANK OF AFRICA BF", "BANK OF AFRICA BURKINA FASO", "BANK OF AFRICA - BURKINA FASO", "BOA BF",
              "BOA BURKINA FASO", "BOA BURKINA"),
    "BOAC": ("BANK OF AFRICA CI", "BANK OF AFRICA COTE D'IVOIRE", "BANK OF AFRICA - COTE D'IVOIRE", "BOA CI",
             "BOA COTE D'IVOIRE"),
    "BOAM": ("BANK OF AFRICA ML", "BANK OF AFRICA MALI", "BANK OF AFRICA - MALI", "BOA ML", "BOA MALI"),
    "BOAN": ("BANK OF AFRICA NG", "BANK OF AFRICA NIGER", "BANK OF AFRICA - NIGER", "BOA NG", "BOA NIGER"),
    "BOAS": ("BANK OF AFRICA SN", "BANK OF AFRICA SENEGAL", "BANK OF AFRICA - SENEGAL", "BOA SN", "BOA SENEGAL"),
    "CABC": ("SICABLE CI", "SICABLE"),
    "CBIBF": ("CORIS BANK INTERNATIONAL BF", "CORIS BANK INTERNATIONAL BURKINA FASO", "CORIS BANK INTERNATIONAL",
              "CORIS BANK BF", "CORIS BANK"),
    "CFAC": ("CFAO MOTORS CI", "CFAO MOTORS", "CFAO CI"),
    "CIEC": ("CIE CI", "CIE COTE D'IVOIRE", "COMPAGNIE IVOIRIENNE D'ELECTRICITE", "CIE"),
    "ECOC": ("ECOBANK CI", "ECOBANK COTE D'IVOIRE"),
    "ETIT": ("ECOBANK TRANS. INCORP. TG", "ECOBANK TRANSNATIONAL INCORPORATED TOGO",
             "ECOBANK TRANSNATIONAL INCORPORATED", "ECOBANK TG", "ETI TG", "ETI TOGO", "ETI"),
    "FTSC": ("FILTISAC CI", "FILTISAC"),
    "LNBB": ("LOTERIE NATIONALE DU BENIN", "LNB BN", "LNB BENIN", "LNB"),
    "NEIC": ("NEI-CEDA CI", "NEI-CEDA", "NEI CEDA"),
    "NSBC": ("NSIA BANQUE CI", "NSIA BANQUE COTE D'IVOIRE", "NSIA BANQUE", "NSBC"),
    "NTLC": ("NESTLE CI", "NESTLE COTE D'IVOIRE", "NESTLE"),
    "ONTBF": ("ONATEL BF", "ONATEL BURKINA FASO", "ONATEL", "MOOV BURKINA FASO", "MOOV AFRICA BURKINA FASO"),
    "ORAC": ("ORANGE COTE D'IVOIRE", "ORANGE CI", "COTE D'IVOIRE TELECOM"),
    "ORGT": ("ORAGROUP TOGO", "ORAGROUP TG", "ORAGROUP S.A", "ORAGROUP"),
    "PALC": ("PALM CI", "PALM COTE D'IVOIRE", "PALMCI"),
    "PRSC": ("TRACTAFRIC MOTORS CI", "TRACTAFRIC MOTORS", "TRACTAFRIC CI", "TRACTAFRIC"),
    "SAFC": ("SAFCA CI", "SAFCA", "ALIOS FINANCE CI", "ALIOS FINANCE SA", "ALIOS FINANCE"),
    "SCRC": ("SUCRIVOIRE CI", "SUCRIVOIRE"),
    "SDCC": ("SODE CI", "SODECI"),
    "SDSC": ("BOLLORE TRANSPORT & LOGISTICS CI", "BOLLORE TRANSPORT & LOGISTICS", "BOLLORE TRANSPORT & LOGISTICS C",
             "AFRICA GLOBAL LOGISTICS CI", "AFRICA GLOBAL LOGISTICS", "AGL CI", "BOLLORE"),
    "SEMC": ("CROWN SIEM CI", "EVIOSYS PACKAGING SIEM CI", "SONOCO METAL PACKAGING SIEM", "SONOCO METAL",
             "CROWN SIEM", "SIEM CI"),
    "SGBC": ("SOCIETE GENERALE COTE D'IVOIRE", "SOCIETE GENERALE CI", "SOCIETE GENERALE DE BANQUES EN COTE D'IVOIRE",
             "SGB CI", "SGBCI", "SGCI"),
    "SHEC": ("VIVO ENERGY CI", "VIVO ENERGY COTE D'IVOIRE", "VIVO ENERGY", "SHELL CI"),
    "SIBC": ("SOCIETE IVOIRIENNE DE BANQUE CI", "SOCIETE IVOIRIENNE DE BANQUE", "SIB CI", "SIB"),
    "SICC": ("SICOR CI", "SICOR"),
    "SIVC": ("ERIUM CI", "AIR LIQUIDE CI", "AIR LIQUIDE COTE D'IVOIRE", "AIR LIQUIDE INTERNATIONAL", "AIR LIQUIDE",
             "ERIUM"),
    "SLBC": ("SOLIBRA CI", "SOLIBRA"),
    "SMBC": ("SMB CI", "SOCIETE MULTINATIONALE DE BITUMES", "SMB"),
    "SNTS": ("SONATEL SN", "SONATEL SENEGAL", "SONATEL"),
    "SOGC": ("SOGB CI", "SOGB"),
    "SPHC": ("SAPH CI", "SAPH COTE D'IVOIRE", "SAPH"),
    "STAC": ("SETAO CI", "SETAO"),
    "STBC": ("SITAB CI", "SITAB COTE D'IVOIRE", "SITAB"),
    "SVOC": ("MOVIS CI", "MOVIS"),
    "TTLC": ("TOTALENERGIES MARKETING CI", "TOTALENERGIES MARKETING COTE D'IVOIRE", "TOTAL ENERGIES MARKETING CI",
             "TOTAL CI", "TOTAL COTE D'IVOIRE", "TOTAL"),
    "TTLS": ("TOTALENERGIES MARKETING SN", "TOTALENERGIES MARKETING SENEGAL", "TOTAL SENEGAL S.A.", "TOTAL SENEGAL",
             "TOTAL SN"),
    "TTRC": ("TRITURAF CI", "TRITRAF CI", "TRITURAF"),
    "UNLC": ("UNILEVER CI", "UNILEVER COTE D'IVOIRE", "UNILEVER"),
    "UNXC": ("UNIWAX CI", "UNIWAX"),
}
#: Libellés qui ressemblent à un alias mais désignent une autre société : Coris Bank
#: International **Côte d'Ivoire** (OPV annoncée fin 2026, document 07 §1.5) n'est pas
#: CBIBF (Burkina Faso). Symbole -> motif interdit dans le libellé normalisé.
ALIAS_EXCLUSIONS: dict[str, str] = {"CBIBF": r"\bCOTE D IVOIRE\b|\bCI\b|\bIVOIRE\b"}
#: Alias trop courts ou trop communs pour être cherchés n'importe où dans un titre.
#: Ils ne servent que pour un libellé d'émetteur ou un en-tête de titre.
AMBIGUOUS_ALIASES = frozenset({"TOTAL", "ETI", "CIE", "SIB", "SMB", "LNB", "SAPH", "PALM", "BICI", "SIEM",
                               "BOLLORE", "NESTLE", "SETAO", "SICOR", "SAFCA", "UNIWAX", "SODECI", "SOGB",
                               "MOVIS", "ERIUM", "AIR LIQUIDE", "ONATEL", "SITAB", "NSBC", "BIIC"})

#: Composition du BRVM 30 au T4-2026 (avis 289-2026 du 01/10/2026, document 01).
BRVM30_T4_2026 = (
    "SDSC BOABF BOAB BOAC BOAM BOAN BOAS BICB CFAC CIEC CBIBF ECOC ETIT SIVC LNBB NSBC ONTBF ORGT "
    "ORAC SAFC SPHC STBC SGBC SIBC SOGC SLBC SNTS TTLC UNXC SHEC"
).split()
#: Compartiment et secteur au BOC du 20/11/2026 (repli si le panel est absent).
FALLBACK_COMPARTMENT_PRESTIGE = frozenset("ECOC NTLC ONTBF ORAC PALC SGBC SIBC SMBC SNTS SPHC TTLC TTLS".split())
FALLBACK_SECTORS: dict[str, str] = {
    **{s: "FIN" for s in "BBGC BICB BICC BOAB BOABF BOAC BOAM BOAN BOAS CBIBF ECOC ETIT NSBC ORGT SAFC SGBC SIBC".split()},
    **{s: "CD" for s in "ABJC BNBC CFAC LNBB NEIC PRSC UNXC".split()},
    **{s: "IND" for s in "CABC FTSC SDSC SEMC SIVC STAC".split()},
    **{s: "CB" for s in "NTLC PALC SCRC SICC SLBC SOGC SPHC STBC UNLC".split()},
    **{s: "ENE" for s in "SHEC SMBC TTLC TTLS".split()},
    **{s: "SPU" for s in "CIEC SDCC".split()},
    **{s: "TEL" for s in "ONTBF ORAC SNTS".split()},
}

#: Émetteurs souverains (obligations d'État) -> pays (codes de reference.py).
SOVEREIGN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bTPCI\b|ETAT DE COTE D ?IVOIRE|TRESOR PUBLIC DE COTE D ?IVOIRE", "CI"),
    (r"\bEOS\b|ETAT DU SENEGAL|\bSUKUK ETAT DU SENEGAL", "SN"),
    (r"\bTPBF\b|ETAT DU BURKINA|TRESOR PUBLIC DU BURKINA", "BF"),
    (r"\bTPBJ\b|ETAT DU BENIN|TRESOR PUBLIC DU BENIN", "BJ"),
    (r"\bTPTG\b|ETAT DU TOGO|TRESOR PUBLIC DU TOGO", "TG"),
    (r"\bTPNE\b|ETAT DU NIGER|TRESOR PUBLIC DU NIGER", "NE"),
    (r"\bEOM\b|ETAT DU MALI|TRESOR PUBLIC DU MALI", "ML"),
    (r"\bTPGB\b|GUINEE BISSAU", "GW"),
)
_BOND_RE = re.compile(
    r"\b[A-Z][A-Z0-9_]{1,12}\.O\d+\b|\bBOND\b|\bSUKUK\b|EMPRUNT OBLIGATAIRE|\bFCTC\b|\bOBLIGATION|"
    r"\d+[,.]?\d*\s*%\s*\(?\s*20\d\d\s*-\s*20\d\d|TAUX DE BASE",
    re.IGNORECASE,
)
#: Pièces annexes d'un même événement (pouvoirs, formulaires, attestations sur un rapport
#: d'activité, versions anglaises) : écartées par défaut pour ne pas compter deux fois.
_ANCILLARY_RE = re.compile(
    r"\bpouvoir|formulaire|bulletin de vote|procuration|fiche d.inscription|"
    r"attestation des commissaires aux comptes sur le rapport d.activit|"
    r"^\s*(activity report|financial statements|press release|notice of)\b",
    re.IGNORECASE,
)

#: Types repérés sur le titre pour la seule déduplication entre sources (la classification
#: complète est celle de ``notes.lexicon`` / ``notes.analyze``) : type -> (motif, fenêtre en jours).
_DEDUP_TYPES: tuple[tuple[str, re.Pattern[str], int], ...] = (
    ("RESUMPTION", re.compile(r"lev[ée]e de (la )?suspension|reprise de (la )?cotation", re.I), 10),
    ("SUSPENSION", re.compile(r"\bsuspen(sion|du)", re.I), 10),
    ("AG_CANCEL", re.compile(r"annulation.*assembl|report.*assembl|assembl.*(annul|report)", re.I), 30),
    ("DIV_NOTICE", re.compile(r"paiement de dividendes?|dividendes? de [\d ,.]+ ?f ?cfa", re.I), 45),
    ("REVERSE_SPLIT", re.compile(r"regroupement|consolidation des actions", re.I), 30),
    ("SPLIT", re.compile(r"fractionnement", re.I), 30),
    ("CAP_INC", re.compile(r"augmentation de capital", re.I), 30),
    ("DELISTING", re.compile(r"radiation", re.I), 30),
    ("AG_CONVOCATION", re.compile(r"avis de convocation|assembl[ée]e g[ée]n[ée]rale (ordinaire|extraordinaire|mixte) du", re.I), 15),
)

# ---------------------------------------------------------------------------
# Erreurs (messages en français, à afficher tels quels à l'analyste)
# ---------------------------------------------------------------------------


class ResearchError(RuntimeError):
    """Erreur de collecte."""


class RobotsDisallowed(ResearchError):
    """La page est interdite aux robots par le robots.txt du site."""


class AccessBlocked(ResearchError):
    """Le site refuse l'accès (HTTP 403/429) : arrêt définitif, aucun contournement."""


class QuotaExceeded(ResearchError):
    """Le quota de requêtes de la session est atteint."""


class ServerUnavailable(ResearchError):
    """Le site répond 5xx ou ne répond pas, même après les nouveaux essais."""


class OfflineCacheMiss(ResearchError):
    """Mode hors ligne : la page n'est pas dans le cache."""


class SourceDisabled(ResearchError):
    """Source désactivée par défaut (protection anti-robot ou accord non obtenu)."""


# ---------------------------------------------------------------------------
# Outils : texte, dates, empreintes
# ---------------------------------------------------------------------------


def utcnow() -> dt.datetime:
    """Heure courante en UTC (avec fuseau)."""
    return dt.datetime.now(dt.timezone.utc)


def to_utc(ts: Any) -> dt.datetime:
    """Convertit une date ou un horodatage en ``datetime`` UTC (naïf = UTC)."""
    if isinstance(ts, pd.Timestamp):
        ts = ts.to_pydatetime()
    if isinstance(ts, str):
        ts = pd.Timestamp(ts).to_pydatetime()
    if isinstance(ts, dt.datetime):
        return ts.replace(tzinfo=dt.timezone.utc) if ts.tzinfo is None else ts.astimezone(dt.timezone.utc)
    if isinstance(ts, dt.date):
        return dt.datetime(ts.year, ts.month, ts.day, tzinfo=dt.timezone.utc)
    raise TypeError(f"horodatage non reconnu : {ts!r}")


def _as_date(value: Any) -> dt.date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.date()
    if isinstance(value, str):
        return parse_date_fr(value)
    return None


def strip_accents(text: str) -> str:
    """Supprime les accents (« Côte » -> « Cote »)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def norm_label(text: str | None) -> str:
    """Normalise un libellé pour la comparaison : majuscules, sans accents ni ponctuation."""
    if not text:
        return ""
    s = strip_accents(html_lib.unescape(str(text))).upper()
    s = s.replace("&", " ET ").replace("’", " ").replace("'", " ").replace("`", " ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_text(text: str | None) -> str:
    """Espaces normalisés (insécables compris)."""
    if not text:
        return ""
    s = html_lib.unescape(str(text)).replace("\xa0", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def url_hash(url: str) -> str:
    """Empreinte sha256 d'une URL (clé du cache)."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


_MONTHS_FR = {
    "janvier": 1, "janv": 1, "jan": 1, "fevrier": 2, "fevr": 2, "fev": 2, "mars": 3, "mar": 3, "avril": 4,
    "avr": 4, "mai": 5, "juin": 6, "juillet": 7, "juil": 7, "aout": 8, "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10, "novembre": 11, "nov": 11, "decembre": 12, "dec": 12,
}
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_LONG_FR_RE = re.compile(r"\b(\d{1,2})(?:er)?\s+([a-z]+)\.?\s+(\d{4})\b")
_FILE_DATE_RE = re.compile(r"/files/(?:[^/]+/)*?(\d{8})(?=[_\-.])")


def parse_date_fr(text: str | None) -> dt.date | None:
    """Analyse une date : ISO, « 16/11/2026 », « 1er décembre 2026 », « 7-sept.-26 »."""
    if not text:
        return None
    s = str(text).strip()
    try:
        m = _ISO_DATE_RE.search(s)
        if m:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = _SLASH_RE.search(s)
        if m:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = _LONG_FR_RE.search(strip_accents(s).lower())
        if m and m.group(2) in _MONTHS_FR:
            return dt.date(int(m.group(3)), _MONTHS_FR[m.group(2)], int(m.group(1)))
    except ValueError:
        return None
    try:  # formats de tableau du BOC (« 7-sept.-26 »)
        from brvm_alpha.data.boc_parser import parse_french_date

        return parse_french_date(s)
    except Exception:  # pragma: no cover - repli défensif
        return None


def date_from_filename(url: str | None) -> dt.date | None:
    """Date ``AAAAMMJJ`` en tête du nom d'un fichier brvm.org (``/files/20261116_-_...``)."""
    if not url:
        return None
    m = _FILE_DATE_RE.search(url)
    if not m:
        return None
    try:
        d = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None
    return d if 1995 <= d.year <= 2100 else None


def _fmt(d: dt.date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "?"


def _iso(d: dt.date | dt.datetime | None) -> str | None:
    return d.isoformat() if d else None


def _parse_amount(text: str | None) -> float | None:
    """« 2 606 FCFA » -> 2606.0 ; « 158,8270 FCFA » -> 158.827."""
    if not text:
        return None
    s = clean_text(text).upper().replace("FCFA", "").replace("F CFA", "").strip()
    m = re.search(r"-?\d[\d ]*(?:[,.]\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


_NUM_WORDS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8,
              "neuf": 9, "dix": 10, "vingt": 20, "quarante": 40, "cent": 100}


def parse_parity(text: str | None) -> float | None:
    """Parité « dix (10) actions nouvelles pour une (1) ancienne » -> 10.0 (nouvelles / anciennes)."""
    if not text:
        return None
    s = strip_accents(clean_text(text)).lower()
    m = re.search(r"(.*?)\bpour\b(.*)", s)
    if not m:
        return None

    def first_number(part: str) -> float | None:
        p = re.search(r"\((\d+(?:[,.]\d+)?)\)", part) or re.search(r"\b(\d+(?:[,.]\d+)?)\b", part)
        if p:
            return float(p.group(1).replace(",", "."))
        for w in re.findall(r"[a-z]+", part):
            if w in _NUM_WORDS:
                return float(_NUM_WORDS[w])
        return None

    new, old = first_number(m.group(1)), first_number(m.group(2))
    if new is None:
        return None
    return new / (old or 1.0)


# ---------------------------------------------------------------------------
# Session polie : robots.txt, crawl-delay, cache, quota, arrêts
# ---------------------------------------------------------------------------


@dataclass
class FetchResult:
    """Réponse HTTP (ou lecture du cache)."""

    url: str
    status: int
    content: bytes
    headers: dict[str, str] = field(default_factory=dict)
    from_cache: bool = False
    final_url: str | None = None
    fetched_at: str | None = None

    @property
    def text(self) -> str:
        ctype = self.headers.get("Content-Type", "") or self.headers.get("content-type", "")
        m = re.search(r"charset=([\w\-]+)", ctype)
        enc = m.group(1) if m else "utf-8"
        try:
            return self.content.decode(enc, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")

    @property
    def content_type(self) -> str:
        return (self.headers.get("Content-Type") or self.headers.get("content-type") or "").lower()


def _requests_transport(user_agent: str) -> Callable[..., Any]:
    """Transport réseau par défaut (``requests``), créé à la première requête."""
    import requests

    sess = requests.Session()
    sess.headers["User-Agent"] = user_agent

    def transport(url: str, headers: Mapping[str, str], timeout: float) -> Any:
        return sess.get(url, headers=dict(headers), timeout=timeout, allow_redirects=True)

    return transport


class PoliteSession:
    """Client HTTP poli : robots.txt, délai entre requêtes, cache, quota et arrêts.

    Paramètres principaux :

    - ``delay_s`` : délai minimal entre deux requêtes vers un même site ; le
      ``Crawl-delay`` du robots.txt et le plancher de :data:`HOST_MIN_DELAY_S`
      (10 s pour brvm.org) s'appliquent s'ils sont plus longs ;
    - ``max_requests`` : quota de requêtes réseau (robots.txt et nouveaux essais
      compris) ; au-delà, :class:`QuotaExceeded` ;
    - ``offline`` : aucune requête, seul le cache disque est lu ;
    - ``cache_dir`` / ``log_path`` : cache HTTP et journal JSONL ;
    - ``transport``, ``clock``, ``sleep``, ``now`` : injectables pour les tests
      (aucun accès réseau, horloge simulée).

    Un HTTP 403 ou 429 arrête **définitivement** la session (attribut ``stopped``) :
    aucune requête ultérieure n'est envoyée, à aucun site.
    """

    def __init__(
        self,
        *,
        user_agent: str = USER_AGENT,
        delay_s: float = DEFAULT_DELAY_S,
        max_requests: int = 150,
        offline: bool = False,
        cache_dir: str | Path | None = None,
        log_path: str | Path | None = None,
        timeout: float = 60.0,
        max_retries: int = MAX_RETRIES,
        backoff_s: float = BACKOFF_S,
        transport: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], dt.datetime] = utcnow,
    ) -> None:
        self.user_agent = user_agent
        self.delay_s = float(delay_s)
        self.max_requests = int(max_requests)
        self.offline = bool(offline)
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_NOTES_DIR / "cache"
        self.log_path = Path(log_path) if log_path is not None else DEFAULT_NOTES_DIR / "fetch_log.jsonl"
        self.timeout = timeout
        self.max_retries = max(1, int(max_retries))
        self.backoff_s = backoff_s
        self._transport = transport
        self.clock = clock
        self.sleep = sleep
        self.now = now
        self.n_requests = 0
        self.stopped: str | None = None
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._last_request: dict[str, float] = {}
        self.history: list[dict[str, Any]] = []

    # -- journal ------------------------------------------------------------
    def _log(self, **entry: Any) -> None:
        entry = {"ts": self.now().isoformat(timespec="seconds"), **entry}
        self.history.append(entry)
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:  # le journal ne doit jamais bloquer la collecte
            log.warning("journal %s non écrit : %s", self.log_path, exc)

    # -- cache --------------------------------------------------------------
    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        h = url_hash(url)
        base = self.cache_dir / "http" / h[:2]
        return base / f"{h}.json", base / f"{h}.body.gz"

    def cache_get(self, url: str) -> FetchResult | None:
        """Réponse en cache pour ``url`` (ou ``None``)."""
        meta_p, body_p = self._cache_paths(url)
        if not (meta_p.exists() and body_p.exists()):
            return None
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            body = gzip.decompress(body_p.read_bytes())
        except (OSError, ValueError, EOFError):
            return None
        return FetchResult(url=url, status=int(meta.get("status", 200)), content=body,
                           headers=meta.get("headers", {}), from_cache=True,
                           final_url=meta.get("final_url"), fetched_at=meta.get("fetched_at"))

    def cache_put(self, url: str, content: bytes, status: int = 200, headers: Mapping[str, str] | None = None,
                  final_url: str | None = None) -> None:
        """Enregistre une réponse dans le cache (utilisé aussi pour amorcer le mode hors ligne)."""
        meta_p, body_p = self._cache_paths(url)
        meta_p.parent.mkdir(parents=True, exist_ok=True)
        keep = {k: v for k, v in (headers or {}).items()
                if k.lower() in ("etag", "last-modified", "content-type")}
        meta = {"url": url, "status": status, "headers": keep, "final_url": final_url or url,
                "fetched_at": self.now().isoformat(timespec="seconds")}
        body_p.write_bytes(gzip.compress(content, mtime=0))
        meta_p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    # -- robots.txt ---------------------------------------------------------
    @staticmethod
    def _origin(url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    def robots_for(self, url: str) -> robotparser.RobotFileParser | None:
        """Règles robots.txt du site de ``url`` (lues une fois par session ; ``None`` = tout permis)."""
        origin = self._origin(url)
        if origin in self._robots:
            return self._robots[origin]
        robots_url = origin + "/robots.txt"
        rp = robotparser.RobotFileParser(robots_url)
        cached = self.cache_get(robots_url)
        fresh = False
        if cached is not None and cached.fetched_at:
            try:
                age = (self.now() - to_utc(cached.fetched_at)).total_seconds()
                fresh = age < 86_400
            except (TypeError, ValueError):
                fresh = False
        if cached is not None and (fresh or self.offline):
            res = cached
        elif self.offline:
            # Hors ligne, aucune requête n'est envoyée : robots.txt n'a pas d'objet.
            self._robots[origin] = None
            return None
        else:
            try:
                res = self._network_get(robots_url, {}, purpose="robots")
            except ServerUnavailable as exc:
                raise ServerUnavailable(
                    f"robots.txt de {origin} inaccessible ({exc}) : par prudence, aucune page n'est lue."
                ) from exc
            if res.status == 200:
                self.cache_put(robots_url, res.content, 200, res.headers, res.final_url)
        if res.status == 200:
            rp.parse(res.text.splitlines())
            self._robots[origin] = rp
        elif res.status in (401, 403):
            rp.disallow_all = True
            self._robots[origin] = rp
        elif 400 <= res.status < 500:
            self._robots[origin] = None  # pas de robots.txt : tout est permis
        else:
            raise ServerUnavailable(
                f"robots.txt de {origin} inaccessible (HTTP {res.status}) : par prudence, aucune page n'est lue."
            )
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        """``True`` si robots.txt autorise ``url`` pour notre User-Agent (toujours vérifié)."""
        rp = self.robots_for(url)
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    def crawl_delay(self, url: str) -> float:
        """Délai effectif entre deux requêtes vers le site de ``url``."""
        host = urlparse(url).netloc.lower()
        delay = max(self.delay_s, HOST_MIN_DELAY_S.get(host, 0.0))
        rp = self._robots.get(self._origin(url))
        if rp is not None:
            try:
                cd = rp.crawl_delay(self.user_agent)
            except Exception:  # pragma: no cover
                cd = None
            if cd:
                delay = max(delay, float(cd))
        return delay

    # -- requêtes -------------------------------------------------------------
    def _wait_turn(self, url: str) -> None:
        host = urlparse(url).netloc.lower()
        last = self._last_request.get(host)
        if last is not None:
            wait = last + self.crawl_delay(url) - self.clock()
            if wait > 0:
                self.sleep(wait)

    def _network_get(self, url: str, headers: Mapping[str, str], purpose: str = "page") -> FetchResult:
        """Une requête GET réseau, avec délai, quota, nouveaux essais et arrêts."""
        if self.stopped:
            raise AccessBlocked(f"Session arrêtée ({self.stopped}) : aucune nouvelle requête n'est envoyée.")
        if self.offline:
            raise OfflineCacheMiss(f"Mode hors ligne : {url} n'est pas dans le cache.")
        if self._transport is None:
            self._transport = _requests_transport(self.user_agent)
        hdrs = {"User-Agent": self.user_agent, **dict(headers)}
        host = urlparse(url).netloc.lower()
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            if self.n_requests >= self.max_requests:
                self._log(event="quota", url=url, n_requests=self.n_requests)
                raise QuotaExceeded(f"Quota de {self.max_requests} requêtes atteint : collecte interrompue.")
            self._wait_turn(url)
            self.n_requests += 1
            t0 = self.clock()
            try:
                resp = self._transport(url, hdrs, self.timeout)
                status = int(resp.status_code)
                content = bytes(resp.content or b"")
                rheaders = {str(k): str(v) for k, v in dict(getattr(resp, "headers", {}) or {}).items()}
                final_url = str(getattr(resp, "url", None) or url)
                error = None
            except Exception as exc:  # erreur réseau : traitée comme un 5xx
                status, content, rheaders, final_url, error = 0, b"", {}, url, f"{type(exc).__name__}: {exc}"
            self._last_request[host] = self.clock()
            self._log(event=purpose, url=url, status=status, bytes=len(content), attempt=attempt,
                      elapsed_s=round(self.clock() - t0, 3), final_url=final_url, error=error)
            if status in STOP_STATUSES:
                self.stopped = f"HTTP {status} sur {url}"
                self._log(event="stop", url=url, status=status, reason=self.stopped)
                raise AccessBlocked(
                    f"Le site {host} a répondu HTTP {status} : la collecte est arrêtée définitivement "
                    "pour cette session, sans aucune tentative de contournement."
                )
            if status == 0 or status >= 500:
                last_error = error or f"HTTP {status}"
                if attempt < self.max_retries:
                    wait = self.backoff_s * (2 ** (attempt - 1))
                    self._log(event="retry", url=url, status=status, wait_s=wait)
                    self.sleep(wait)
                    continue
                self.stopped = f"{last_error} répété sur {url}"
                self._log(event="stop", url=url, status=status, reason=self.stopped)
                raise ServerUnavailable(
                    f"{host} ne répond pas correctement ({last_error}) après {self.max_retries} essais : "
                    "collecte arrêtée, nouvel essai plus tard."
                )
            return FetchResult(url=url, status=status, content=content, headers=rheaders,
                               final_url=final_url, fetched_at=self.now().isoformat(timespec="seconds"))
        raise ServerUnavailable(f"{url} : {last_error}")  # pragma: no cover

    def get(self, url: str, *, max_age_s: float | None = None, immutable: bool = False) -> FetchResult:
        """GET poli de ``url``.

        - hors ligne : réponse du cache ou :class:`OfflineCacheMiss` ;
        - ``immutable=True`` (PDF) : le cache suffit, aucune revalidation ;
        - ``max_age_s`` : âge maximal du cache accepté sans requête ;
        - sinon requête conditionnelle (``If-None-Match`` / ``If-Modified-Since``) ;
          une réponse 304 renvoie le corps en cache.

        Lève :class:`RobotsDisallowed` si robots.txt interdit la page.
        """
        cached = self.cache_get(url)
        if self.offline:
            if cached is None:
                self._log(event="cache_miss", url=url, offline=True)
                raise OfflineCacheMiss(f"Mode hors ligne : {url} n'est pas dans le cache.")
            self._log(event="cache", url=url, status=cached.status, from_cache=True)
            return cached
        if cached is not None and cached.status == 200:
            if immutable:
                self._log(event="cache", url=url, status=200, from_cache=True)
                return cached
            if max_age_s is not None and cached.fetched_at:
                age = (self.now() - to_utc(cached.fetched_at)).total_seconds()
                if age <= max_age_s:
                    self._log(event="cache", url=url, status=200, from_cache=True, age_s=round(age))
                    return cached
        if self.stopped:
            raise AccessBlocked(f"Session arrêtée ({self.stopped}) : aucune nouvelle requête n'est envoyée.")
        if not self.allowed(url):
            self._log(event="robots_disallow", url=url)
            raise RobotsDisallowed(
                f"Le fichier robots.txt de {urlparse(url).netloc} interdit la lecture de {url} par un robot : "
                "la page n'est pas lue (aucun contournement)."
            )
        headers: dict[str, str] = {}
        if cached is not None and cached.status == 200:
            etag = cached.headers.get("ETag") or cached.headers.get("etag")
            lastmod = cached.headers.get("Last-Modified") or cached.headers.get("last-modified")
            if etag:
                headers["If-None-Match"] = etag
            if lastmod:
                headers["If-Modified-Since"] = lastmod
        res = self._network_get(url, headers)
        if res.status == 304 and cached is not None:
            self.cache_put(url, cached.content, 200, cached.headers, cached.final_url)
            return dataclasses.replace(cached, from_cache=True, fetched_at=res.fetched_at)
        if res.status == 200:
            self.cache_put(url, res.content, 200, res.headers, res.final_url)
        return res


# ---------------------------------------------------------------------------
# Correspondance émetteur -> symbole
# ---------------------------------------------------------------------------


class IssuerResolver:
    """Associe un libellé d'émetteur (actuel ou historique) à un symbole BRVM.

    Sources, par ordre de priorité : alias de :data:`ISSUER_ALIASES`, noms du panel
    ``equities.parquet`` (si disponible), puis ``notes.entities`` (si le module
    existe) pour une recherche libre dans un titre.
    """

    def __init__(self, equities: pd.DataFrame | None = None, panel_dir: str | Path | None = None,
                 extra_aliases: Mapping[str, str] | None = None, use_entities: bool = True) -> None:
        self.aliases: dict[str, str] = {}
        for sym, names in ISSUER_ALIASES.items():
            for n in names:
                self.aliases.setdefault(norm_label(n), sym)
            self.aliases.setdefault(norm_label(sym), sym)
        if equities is None and panel_dir is not None:
            try:
                equities = pd.read_parquet(Path(panel_dir) / "equities.parquet", columns=["symbol", "name"])
            except Exception:  # panel absent : alias intégrés seulement
                equities = None
        self.symbols: set[str] = set(ISSUER_ALIASES)
        if equities is not None and {"symbol", "name"} <= set(equities.columns):
            pairs = equities[["symbol", "name"]].dropna().drop_duplicates()
            for sym, name in pairs.itertuples(index=False):
                self.symbols.add(str(sym))
                self.aliases.setdefault(norm_label(name), str(sym))
        for k, v in (extra_aliases or {}).items():
            self.aliases[norm_label(k)] = v
        self._by_len = sorted(self.aliases, key=len, reverse=True)
        self._entities = None
        if use_entities:
            try:  # module de liaison texte -> entités (autre agent), facultatif
                from brvm_alpha.notes import entities as _ent  # type: ignore

                self._entities = _ent
            except Exception:
                self._entities = None

    @staticmethod
    def _excluded(sym: str | None, normalized: str) -> bool:
        pat = ALIAS_EXCLUSIONS.get(sym or "")
        return bool(pat and re.search(pat, normalized))

    def exact(self, label: str | None) -> str | None:
        """Correspondance exacte d'un libellé normalisé."""
        if not label:
            return None
        n = norm_label(label)
        sym = self.aliases.get(n)
        return None if self._excluded(sym, n) else sym

    def prefix(self, label: str | None) -> str | None:
        """Alias le plus long qui commence le libellé (« BOA CI : Rapport... » -> BOAC)."""
        n = norm_label(label)
        if not n:
            return None
        for alias in self._by_len:
            if n == alias or n.startswith(alias + " "):
                sym = self.aliases[alias]
                return None if self._excluded(sym, n) else sym
        return None

    def anywhere(self, text: str | None) -> str | None:
        """Alias non ambigu le plus long trouvé n'importe où (mots entiers)."""
        n = f" {norm_label(text)} "
        if not n.strip():
            return None
        for alias in self._by_len:
            if len(alias) < 5 or alias in AMBIGUOUS_ALIASES:
                continue
            if f" {alias} " in n:
                sym = self.aliases[alias]
                return None if self._excluded(sym, n) else sym
        if self._entities is not None:
            sym = self._entities_symbol(text or "")
            if sym and not self._excluded(sym, n.strip()):
                return sym
        return None

    def _entities_symbol(self, text: str) -> str | None:
        """Symbole unique trouvé par ``notes.entities.link_entities`` (sinon ``None``)."""
        ent = self._entities
        fn = getattr(ent, "link_entities", None)
        if callable(fn):
            try:
                links = fn(text, kinds=("symbol",))
            except Exception:
                return None
            syms = [c for c in getattr(links, "targets", []) or [] if isinstance(c, str) and c in self.symbols]
            return syms[0] if len(syms) == 1 else None
        fn = getattr(ent, "resolve_alias", None)
        if callable(fn):
            try:
                out = fn(text, kinds=("symbol",))
            except Exception:
                return None
            return out if isinstance(out, str) and out in self.symbols else None
        return None

    def resolve(self, label: str | None = None, title: str | None = None) -> str | None:
        """Symbole d'après le libellé d'émetteur puis l'en-tête, la fin ou le corps du titre."""
        sym = self.exact(label) or self.prefix(label)
        if sym:
            return sym
        if title:
            parts = re.split(r"\s+[:;]\s+|\s+[-–]\s+|\s*:\s+", clean_text(title))
            head, tail = parts[0], parts[-1]
            head = re.sub(r"\(.*?\)", " ", head)
            sym = self.exact(head) or self.prefix(head) or self.exact(tail) or self.prefix(tail)
            if sym:
                return sym
            return self.anywhere(title)
        return None


@lru_cache(maxsize=4)
def _default_resolver(panel_dir: str) -> IssuerResolver:
    return IssuerResolver(panel_dir=panel_dir)


def default_resolver(panel_dir: str | Path | None = None) -> IssuerResolver:
    """Résolveur partagé (alias intégrés + noms du panel)."""
    return _default_resolver(str(panel_dir or DEFAULT_PANEL_DIR))


def sovereign_country(text: str | None) -> str | None:
    """Pays d'un émetteur souverain cité dans un titre (« TPCI 5,75 % ... » -> CI)."""
    n = norm_label(text)
    for pat, country in SOVEREIGN_PATTERNS:
        if re.search(pat, n):
            return country
    return None


def _country_of(symbol: str | None) -> str | None:
    if not symbol:
        return None
    from brvm_alpha.reference import country_of

    return country_of(symbol)


# ---------------------------------------------------------------------------
# Couche (a) — analyse HTML des vues Drupal de brvm.org
# ---------------------------------------------------------------------------


def _soup(html: str | bytes):
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "lxml")


def parse_views_table(html: str | bytes, page_url: str = BASE_URL) -> tuple[list[dict[str, dict[str, Any]]], int | None]:
    """Lignes d'une table Drupal ``views-table`` et numéro de la dernière page.

    Chaque ligne est un dictionnaire ``champ -> {"text", "iso", "links"}`` où le
    champ est le suffixe de la classe ``views-field-<champ>`` de la cellule,
    ``iso`` la liste des dates ISO (attribut ``content``) et ``links`` les liens
    absolus. La dernière page vient de ``<li class="pager-last">`` (0 si absente).
    """
    soup = _soup(html)
    table = soup.find("table", class_=lambda c: c and "views-table" in c)
    rows: list[dict[str, dict[str, Any]]] = []
    if table is not None:
        body = table.find("tbody") or table
        for tr in body.find_all("tr", recursive=False) or body.find_all("tr"):
            row: dict[str, dict[str, Any]] = {}
            for td in tr.find_all("td"):
                classes = td.get("class") or []
                name = next((c[len("views-field-"):] for c in classes if c.startswith("views-field-")), None)
                if not name:
                    continue
                row[name] = {
                    "text": clean_text(td.get_text(" ", strip=True)),
                    "iso": [s.get("content") for s in td.find_all(attrs={"content": True})],
                    "links": [urljoin(page_url, a["href"]) for a in td.find_all("a", href=True)],
                }
            if row:
                rows.append(row)
    return rows, _last_page(soup)


def _last_page(soup: Any) -> int | None:
    """Numéro (0-based) de la dernière page d'une vue paginée ; 0 sans pagination."""
    li = soup.find("li", class_="pager-last")
    hrefs: list[str] = []
    if li is not None and li.find("a", href=True):
        hrefs = [li.find("a", href=True)["href"]]
    else:  # dernière page atteinte : seuls les liens « précédent » / numéros restent
        pager = soup.find("ul", class_="pagination") or soup.find(class_="pager")
        if pager is not None:
            hrefs = [a["href"] for a in pager.find_all("a", href=True)]
    pages = []
    for h in hrefs:
        q = parse_qs(urlparse(h).query)
        if "page" in q:
            try:
                pages.append(int(q["page"][0]))
            except ValueError:
                pass
    if pages:
        return max(pages)
    return 0


def _cell(row: Mapping[str, dict[str, Any]], name: str) -> dict[str, Any]:
    return row.get(name) or {"text": "", "iso": [], "links": []}


def _cell_date(cell: Mapping[str, Any]) -> dt.date | None:
    for iso in cell.get("iso") or []:
        d = parse_date_fr(iso)
        if d:
            return d
    return parse_date_fr(cell.get("text"))


def _cell_datetime(cell: Mapping[str, Any]) -> dt.datetime | None:
    for iso in cell.get("iso") or []:
        try:
            ts = pd.Timestamp(iso)
        except (ValueError, TypeError):
            continue
        return to_utc(ts)
    return None


def _first_link(row: Mapping[str, dict[str, Any]], names: Iterable[str]) -> str | None:
    for n in names:
        links = _cell(row, n)["links"]
        if links:
            return links[0]
    return None


def _instrument_of(title: str, symbol: str | None) -> str | None:
    """« obligation » si le titre décrit un emprunt, « fctc » pour une titrisation, sinon None."""
    if re.search(r"\bFCTC\b", title, re.IGNORECASE):
        return "fctc"
    if _BOND_RE.search(title) and not (symbol and re.search(r"\bactions?\b", title, re.IGNORECASE)):
        return "obligation"
    return None


def _base_item(list_key: str, source: str, page_url: str, title: str, doc_url: str | None,
               doc_date: dt.date | None, issuer: str | None, symbol: str | None,
               event_hint: str | None, text: str = "", published_at: dt.datetime | None = None,
               extra: dict[str, Any] | None = None, date_source: str | None = None) -> dict[str, Any]:
    """Élément brut commun à toutes les sources.

    ``date_source`` dit d'où vient la date : ``horodatage`` (date et heure : avis, BOC),
    ``liste`` (colonne date de la liste = mise en ligne), ``fichier`` (date lue dans le
    nom du PDF : date du document, pas de la mise en ligne).
    """
    file_date = date_from_filename(doc_url)
    if date_source is None:
        date_source = "horodatage" if published_at else ("liste" if doc_date else ("fichier" if file_date else None))
    instrument = (extra or {}).get("instrument") or _instrument_of(title, symbol)
    if instrument in ("obligation", "fctc") and symbol and not (extra or {}).get("keep_symbol"):
        extra = {**(extra or {}), "issuer_symbol": symbol}
        symbol = None
    country = (_country_of(symbol) or sovereign_country((extra or {}).get("bond")) or sovereign_country(title)
               or sovereign_country(issuer))
    return {
        "source": source,
        "list_type": list_key,
        "page_url": page_url,
        "doc_url": doc_url,
        "doc_date": _iso(doc_date or file_date),
        "file_date": _iso(file_date),
        "date_source": date_source,
        "published_at": published_at.isoformat() if published_at else None,
        "title": clean_text(title),
        "issuer": clean_text(issuer) or None,
        "symbol": symbol,
        "country": country,
        "instrument": instrument,
        "market_level": symbol is None and instrument is None and country is None and list_key in MARKET_LISTS,
        "event_hint": event_hint,
        "ancillary": bool(_ANCILLARY_RE.search(title or "")),
        "text": text,
        "extra": dict(extra or {}),
    }


def parse_list_page(html: str | bytes, list_key: str, page_url: str | None = None,
                    resolver: IssuerResolver | None = None) -> dict[str, Any]:
    """Analyse une page d'une liste brvm.org -> ``{"items", "last_page", "n_rows"}``.

    ``list_key`` est une clé de :data:`BRVM_LISTS` (``communiques``, ``dividendes``...).
    Les éléments sont dans l'ordre de la page (du plus récent au plus ancien).
    """
    spec = BRVM_LISTS[list_key]
    page_url = page_url or BASE_URL + spec.path
    resolver = resolver or default_resolver()
    rows, last_page = parse_views_table(html, page_url)
    items = []
    for row in rows:
        if spec.kind == "annonce":
            item = _annonce_item(row, spec, page_url, resolver)
        elif spec.kind == "avis":
            item = _avis_item(row, spec, page_url, resolver)
        else:
            item = _esv_item(row, spec, page_url, resolver)
        if item is not None:
            items.append(item)
    return {"items": items, "last_page": last_page, "n_rows": len(rows)}


def _annonce_item(row, spec: BrvmList, page_url: str, resolver: IssuerResolver) -> dict[str, Any] | None:
    title = _cell(row, "title")["text"]
    if not title:
        return None
    issuer = _cell(row, "og-group-ref")["text"]
    doc_url = _first_link(row, ("field-fichier-annonce",))
    doc_date = _cell_date(_cell(row, "field-date-annonce"))
    sym_label = resolver.resolve(issuer, None)
    sym_title = resolver.resolve(None, title)
    symbol = sym_label or sym_title
    extra: dict[str, Any] = {}
    if sym_label and sym_title and sym_label != sym_title:
        # Le libellé « Société » est parfois faux ou historique : on garde celui du
        # titre, plus précis, et on trace le désaccord.
        extra["symbol_conflict"] = [sym_label, sym_title]
        symbol = sym_title
    # Texte sans date : l'analyse ne doit pas confondre la date de mise en ligne avec une date d'AG.
    # (ni « BRVM » ni « bourse » : la liaison d'entités y verrait le marché entier)
    text = f"Liste « {spec.label} » du site officiel ; émetteur : {issuer or 'non précisé'}."
    return _base_item(spec.key, "brvm_list", page_url, title, doc_url, doc_date, issuer, symbol,
                      spec.event_hint, text, None, extra, date_source="liste" if doc_date else None)


def _avis_item(row, spec: BrvmList, page_url: str, resolver: IssuerResolver) -> dict[str, Any] | None:
    title = _cell(row, "title")["text"]
    if not title:
        return None
    cell = _cell(row, "field-date-avis")
    published = _cell_datetime(cell)
    doc_date = published.date() if published else _cell_date(cell)
    doc_url = _first_link(row, ("field-fichier-avis",))
    symbol = resolver.resolve(None, title)
    extra: dict[str, Any] = {}
    m = re.search(r"avis_n(?:deg|°|o)?_?(\d+)", doc_url or "", re.IGNORECASE)
    if m:
        extra["avis_no"] = int(m.group(1))
    if re.search(r"composition|indice|brvm ?30|prestige|brvm ?10", title, re.IGNORECASE):
        extra["index_related"] = True
    text = "Avis officiel (liste des avis du site officiel)."
    return _base_item(spec.key, "brvm_list", page_url, title, doc_url, doc_date, None, symbol,
                      spec.event_hint, text, published, extra)


def _esv_item(row, spec: BrvmList, page_url: str, resolver: IssuerResolver) -> dict[str, Any] | None:
    issuer = _cell(row, "field-emetteur-esv")["text"]
    bond = _cell(row, "body-1")["text"]
    share = _cell(row, "body")["text"]
    avis_url = _first_link(row, ("field-avis-dividende-esv",))
    comm_url = _first_link(row, ("field-communique-esv",))
    doc_url = avis_url or comm_url
    symbol = resolver.resolve(issuer, None) or (resolver.resolve(share, None) if share else None)
    who = issuer or share or bond or "émetteur non précisé"
    extra: dict[str, Any] = {"communique_url": comm_url} if comm_url and comm_url != doc_url else {}
    if bond and not share:
        extra["instrument"] = "obligation"
        extra["bond"] = bond
    file_date = date_from_filename(doc_url) or date_from_filename(comm_url)
    lines: list[str] = []
    if spec.key == "dividendes":
        exo = _cell(row, "field-exercice-comptable-esv")
        exercice = (_cell_date(exo).year if _cell_date(exo) else None) or (exo["text"] or None)
        pay = _cell_date(_cell(row, "field-date-de-paiement-esv"))
        ex = _cell_date(_cell(row, "field-date-ex-dividende"))
        amount_txt = _cell(row, "field-montant-du-dividende-net")["text"]
        div = _parse_amount(amount_txt)
        title = f"{who} : Paiement de dividendes - exercice {exercice or '?'}"
        lines = [f"Dividende net : {amount_txt or '?'} par action.", f"Date ex-dividende : {_fmt(ex)}.",
                 f"Date de paiement : {_fmt(pay)}.", f"Exercice : {exercice or '?'}."]
        extra.update({"div_net": div, "ex_date": _iso(ex), "pay_date": _iso(pay), "exercice": exercice})
        extra.update(_dividend_date_checks(file_date, ex, pay))
        m = re.search(r"avis_n(?:deg)?_?(\d+)", doc_url or "", re.IGNORECASE)
        if m:
            extra["avis_no"] = int(m.group(1))
    elif spec.key == "augmentation_capital":
        record = _cell_date(_cell(row, "field-date-de-fermeture-des-regi"))
        parity_txt = _cell(row, "field-autre-parite")["text"]
        nature = _cell(row, "field-nature-du-droit-esv")["text"]
        period = _cell(row, "field-periode-de-negociation-esv")["text"]
        title = f"{who} : Augmentation de capital" + (f" ({nature})" if nature else "")
        lines = [f"Parité : {parity_txt or '?'}", f"Date de fermeture des registres : {_fmt(record)}.",
                 f"Nature du droit : {nature or '?'}.", f"Période de négociation : {period or '?'}"]
        extra.update({"record_date": _iso(record), "parity": parity_txt or None, "parity_ratio": parse_parity(parity_txt),
                      "right_type": nature or None, "trading_period": period or None})
    elif spec.key == "fractionnement":
        split = _cell_date(_cell(row, "field-date-de-fractionnement"))
        parity_txt = _cell(row, "field-parite-esv")["text"]
        theo = _cell(row, "field-valeur-theorique")["text"]
        ratio = parse_parity(parity_txt)
        reverse = ratio is not None and ratio < 1
        title = f"{who} : {'Regroupement' if reverse else 'Fractionnement'} des actions" + (
            f" ({parity_txt})" if parity_txt else "")
        lines = [f"Date de fractionnement : {_fmt(split)}.", f"Parité : {parity_txt or '?'}."]
        if theo:
            lines.append(f"Valeur théorique : {theo}.")
        extra.update({"split_date": _iso(split), "parity": parity_txt or None, "split_ratio": ratio,
                      "theoretical_value": _parse_amount(theo)})
        if reverse:
            extra["event_hint_override"] = "REVERSE_SPLIT"
    elif spec.key == "radiation":
        when = _cell_date(_cell(row, "field-date-de-radiation"))
        what = bond or share or issuer
        title = f"{what or who} : Radiation de la cote" + (f" ({issuer})" if issuer and issuer not in (what or "") else "")
        lines = [f"Date de radiation : {_fmt(when)}."]
        extra.update({"delisting_date": _iso(when)})
        if not bond:
            symbol = symbol or resolver.resolve(share, None)
    else:  # pragma: no cover - liste esv non prévue
        title = who
    if not (issuer or bond or share):
        return None
    hint = extra.pop("event_hint_override", None) or spec.event_hint
    text = " ".join(lines)
    return _base_item(spec.key, "brvm_list", page_url, title, doc_url, file_date, issuer, symbol, hint,
                      text, None, extra, date_source="fichier" if file_date else None)


def _dividend_date_checks(file_date: dt.date | None, ex: dt.date | None, pay: dt.date | None) -> dict[str, Any]:
    """Contrôles du document 07 §1.2 / §6.7 (validation) sur la liste des dividendes.

    La date de l'avis lue dans le nom du fichier est parfois fausse (année erronée :
    cas LNB 2026). Si elle est suspecte, la date de publication retenue est bornée
    prudemment par ``ex_date - 10 jours`` (p10 du délai avis -> détachement), ce qui
    ne peut que retarder la note : aucun biais d'anticipation.
    """
    reasons = []
    if file_date is None:
        reasons.append("date d'avis absente du nom de fichier")
    else:
        if file_date.weekday() >= 5:
            reasons.append("date d'avis un week-end")
        if ex and file_date > ex:
            reasons.append("avis postérieur à la date ex-dividende")
        if ex and (ex - file_date).days > 45:
            reasons.append("plus de 45 jours entre l'avis et la date ex-dividende")
    if ex and ex.weekday() >= 5:
        reasons.append("date ex-dividende un week-end")
    if ex and pay and pay < ex:
        reasons.append("date de paiement antérieure à la date ex")
    out: dict[str, Any] = {}
    if reasons:
        out["date_suspect"] = reasons
        if ex is not None:
            floor = ex - dt.timedelta(days=NOTICE_TO_EX_MIN_DAYS)
            out["published_floor"] = _iso(max(floor, file_date) if file_date else floor)
    return out


def parse_issuers_index(html: str | bytes, page_url: str = BASE_URL + ISSUERS_INDEX_PATH,
                        resolver: IssuerResolver | None = None) -> dict[str, Any]:
    """Index « rapports des sociétés cotées » -> ``{"issuers": [...], "last_page"}``.

    Chaque émetteur : ``code`` (numéro interne brvm.org, pas le symbole), ``name``,
    ``slug``, ``url``, ``description`` et ``symbol`` (action reconnue ou ``None``).
    """
    resolver = resolver or default_resolver()
    rows, last_page = parse_views_table(html, page_url)
    issuers = []
    for row in rows:
        title = _cell(row, "title")
        if not title["links"]:
            continue
        url = title["links"][0]
        slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        name = title["text"]
        desc = _cell(row, "field-description-emetteur")["text"]
        sym = next((s for s, slugs in ISSUER_SLUGS.items() if slug in slugs), None)
        if sym is None and not re.search(r"\.O\d|^TNC_|FCTC|^TP[A-Z]{2}$|^DC/BR$", name):
            sym = resolver.exact(name)
        issuers.append({"code": _cell(row, "field-code-emetteur")["text"], "name": name, "slug": slug,
                        "url": url, "description": desc, "symbol": sym})
    return {"issuers": issuers, "last_page": last_page}


def parse_issuer_reports(html: str | bytes, page_url: str, symbol: str | None = None,
                         resolver: IssuerResolver | None = None) -> dict[str, Any]:
    """Page « rapports-societe-cotes/<slug> » -> ``{"items", "last_page", "issuer"}``.

    La page n'a pas de colonne de date : la date du document se lit dans le nom du
    PDF (``/files/AAAAMMJJ_-_...``). Si l'en-tête du titre désigne un autre émetteur
    que la page (erreur de rattachement sur le site), le symbole du titre l'emporte
    et ``extra["symbol_conflict"]`` le signale.
    """
    resolver = resolver or default_resolver()
    rows, last_page = parse_views_table(html, page_url)
    soup = _soup(html)
    h1 = soup.find("h1")
    issuer = clean_text(h1.get_text(" ", strip=True)) if h1 else None
    page_symbol = symbol or resolver.resolve(issuer, None)
    items = []
    for row in rows:
        title = _cell(row, "nothing")["text"] or _cell(row, "title")["text"]
        if not title:
            continue
        doc_url = _first_link(row, ("field-fichier", "nothing", "title"))
        title_sym = resolver.resolve(None, title)
        extra: dict[str, Any] = {"page_symbol": page_symbol}
        sym = page_symbol
        if title_sym and page_symbol and title_sym != page_symbol:
            extra["symbol_conflict"] = [page_symbol, title_sym]
            sym = title_sym
        elif title_sym and not page_symbol:
            sym = title_sym
        file_date = date_from_filename(doc_url)
        if file_date is None:
            extra["date_inconnue"] = True
        text = f"Document de la page « rapports » de {issuer or 'l’émetteur'} (site officiel)."
        items.append(_base_item("rapports_emetteur", "brvm_issuer", page_url, title, doc_url, file_date, issuer,
                                sym, None, text, None, extra, date_source="fichier" if file_date else None))
    return {"items": items, "last_page": last_page, "issuer": issuer, "symbol": page_symbol}


# ---------------------------------------------------------------------------
# Couche (a) — collecteurs paginés
# ---------------------------------------------------------------------------


def _page_url(path: str, page: int) -> str:
    url = path if path.startswith("http") else BASE_URL + path
    return url if page == 0 else f"{url}{'&' if '?' in url else '?'}page={page}"


def item_key(item: Mapping[str, Any]) -> str:
    """Clé d'unicité d'un élément brut : URL du document, sinon page + titre + date."""
    if item.get("doc_url"):
        return normalize_url(item["doc_url"])
    return "|".join(str(item.get(k) or "") for k in ("list_type", "page_url", "doc_date")) + "|" + norm_label(
        item.get("title"))


def normalize_url(url: str) -> str:
    """URL comparable (schéma https, hôte en minuscules, sans fragment)."""
    p = urlparse(url.strip())
    scheme = "https" if p.scheme in ("http", "https") else p.scheme
    return f"{scheme}://{p.netloc.lower()}{p.path}" + (f"?{p.query}" if p.query else "")


def collect_list(session: PoliteSession, list_key: str, *, since: Any = None,
                 known_urls: Iterable[str] = (), max_pages: int | None = 1,
                 resolver: IssuerResolver | None = None, errors: list[str] | None = None) -> list[dict[str, Any]]:
    """Collecte une liste brvm.org, page 0 puis ``?page=N``.

    La pagination s'arrête : après la page où apparaît une URL déjà connue
    (``known_urls``) ; après une page dont le dernier élément est antérieur à
    ``since`` ; à la dernière page de la vue ; à ``max_pages`` pages (``None`` :
    sans limite autre que le quota). Les éléments antérieurs à ``since`` sont
    écartés. Une erreur de collecte (quota, 403, robots...) arrête la liste ; elle
    est ajoutée à ``errors`` si fourni, sinon relancée.
    """
    spec = BRVM_LISTS[list_key]
    since_d = _as_date(since)
    known = {normalize_url(u) for u in known_urls if u}
    out: list[dict[str, Any]] = []
    page = 0
    while True:
        url = _page_url(spec.path, page)
        try:
            res = session.get(url)
        except ResearchError as exc:
            if errors is None:
                raise
            errors.append(f"{list_key} page {page} : {exc}")
            break
        if res.status != 200:
            msg = f"{list_key} page {page} : HTTP {res.status} ({url})"
            if errors is not None:
                errors.append(msg)
            log.warning(msg)
            break
        parsed = parse_list_page(res.content, list_key, url, resolver)
        stop = False
        for it in parsed["items"]:
            it["page"] = page
            d = _as_date(it.get("doc_date"))
            if it.get("doc_url") and normalize_url(it["doc_url"]) in known:
                stop = True
                continue
            if since_d and (d is None or d < since_d):  # sans date : récence non prouvée
                continue
            out.append(it)
        items = parsed["items"]
        if since_d and items:
            last_d = _as_date(items[-1].get("doc_date"))
            if last_d and last_d < since_d:
                stop = True
        last = parsed["last_page"] or 0
        page += 1
        if stop or not items or page > last or (max_pages is not None and page >= max_pages):
            break
    return out


def collect_issuers_index(session: PoliteSession, max_pages: int = 5,
                          resolver: IssuerResolver | None = None) -> list[dict[str, Any]]:
    """Toutes les pages de l'index des émetteurs (75 émetteurs, 3 pages au 22/11/2026)."""
    out: list[dict[str, Any]] = []
    for page in range(max_pages):
        url = _page_url(ISSUERS_INDEX_PATH, page)
        res = session.get(url)
        if res.status != 200:
            break
        parsed = parse_issuers_index(res.content, url, resolver)
        out.extend(parsed["issuers"])
        if page >= (parsed["last_page"] or 0):
            break
    return out


def collect_issuer_reports(session: PoliteSession, symbol: str | None = None, slug: str | None = None, *,
                           max_pages: int = 1, since: Any = None, known_urls: Iterable[str] = (),
                           resolver: IssuerResolver | None = None,
                           errors: list[str] | None = None) -> list[dict[str, Any]]:
    """Rapports d'un émetteur (page 0 par défaut, comme la collecte nocturne du §6.2).

    Une page absente (HTTP 404 : slug changé sur le site) est signalée dans ``errors``
    si fourni ; les erreurs de session (403/429, quota, robots.txt) sont relancées.
    """
    if slug is None:
        if not symbol or symbol not in ISSUER_SLUGS:
            raise ValueError(f"Aucune page « rapports » connue pour {symbol!r}.")
        slug = ISSUER_SLUGS[symbol][0]
    since_d = _as_date(since)
    known = {normalize_url(u) for u in known_urls if u}
    out: list[dict[str, Any]] = []
    for page in range(max_pages):
        url = _page_url(ISSUER_REPORTS_PATH.format(slug=slug), page)
        res = session.get(url)
        if res.status != 200:
            msg = f"rapports {symbol or ''} ({slug}) : HTTP {res.status} ({url})"
            if errors is not None:
                errors.append(msg)
            log.info(msg)
            break
        parsed = parse_issuer_reports(res.content, url, symbol, resolver)
        stop = False
        for it in parsed["items"]:
            if it.get("doc_url") and normalize_url(it["doc_url"]) in known:
                stop = True
                continue
            d = _as_date(it.get("doc_date"))
            if since_d and (d is None or d < since_d):  # sans date : récence non prouvée
                continue
            out.append(it)
        if stop or page >= (parsed["last_page"] or 0):
            break
    return out


# ---------------------------------------------------------------------------
# Couche (a) — événements des BOC locaux
# ---------------------------------------------------------------------------

_SECTION_HEADERS = ("OPERATIONS EN COURS", "AVIS", "COMMUNIQUES")
_PAGE_NO_RE = re.compile(r"^\s*\d{1,3}\s*$")
_DATE_HEADER_RE = re.compile(r"^\s*(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d", re.IGNORECASE)
_AG_ROW_RE = re.compile(
    r"^(?P<soc>\S.*?)\s{2,}(?P<nature>Ordinaire|Extraordinaire|Mixte|Sp[ée]ciale|Constitutive)\w*\s+"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<heure>\d{1,2}[:h]\d{2}(?::\d{2})?)?\s*(?P<lieu>.*)$",
    re.IGNORECASE,
)
_AG_CANCEL_RE = re.compile(r"annul|report", re.IGNORECASE)
_SP_TOKEN_RE = re.compile(r"(?<![\w.()/-])SP(?![\w.()/-])")


def _columns(header: str) -> list[int]:
    """Positions de début des colonnes d'un en-tête (blocs séparés par 2 espaces ou plus)."""
    return [m.start() for m in re.finditer(r"\S+(?:\s\S+)*", header)]


def _split_columns(line: str, starts: list[int], tol: int = 3) -> list[str]:
    """Répartit les blocs d'une ligne dans les colonnes (début de bloc ± ``tol``)."""
    cols = [""] * len(starts)
    for m in re.finditer(r"\S+(?:\s\S+)*", line):
        idx = 0
        for i, s in enumerate(starts):
            if m.start() + tol >= s:
                idx = i
        cols[idx] = (cols[idx] + " " + m.group(0)).strip()
    return cols


def _boc_sections(lines: list[str]) -> dict[str, list[list[str]]]:
    """Lignes des tableaux « OPERATIONS EN COURS », « AVIS », « COMMUNIQUES » (lignes fusionnées)."""
    out: dict[str, list[list[str]]] = {}
    idx = [i for i, ln in enumerate(lines) if ln.strip() in _SECTION_HEADERS]
    for k, i in enumerate(idx):
        name = lines[i].strip()
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        j = i + 1
        while j < end and not lines[j].strip():
            j += 1
        if j >= end:
            continue
        starts = _columns(lines[j])
        rows: list[list[str]] = []
        blank = 0
        for ln in lines[j + 1:end]:
            if _PAGE_NO_RE.match(ln) or _DATE_HEADER_RE.match(ln):
                break
            if not ln.strip():
                blank += 1
                if blank >= 4 and rows:
                    break
                continue
            blank = 0
            cols = _split_columns(ln, starts)
            if len(cols) < 3:  # « Emetteur | Opération »
                new_row = bool(cols[0])
            else:  # « Entité | N° | Nature | Objet » : un numéro et (une entité ou une nature)
                new_row = bool(cols[1]) and (bool(cols[0]) or bool(cols[2]))
            if new_row or not rows:
                rows.append(cols)
            else:
                rows[-1] = [(a + " " + b).strip() for a, b in zip(rows[-1], cols)]
        out[name] = rows
    return out


def _boc_ag_rows(lines: list[str]) -> list[dict[str, Any]]:
    """Calendrier des AG de l'année (« ANNEE : AAAA ») -> lignes société/nature/date/heure/lieu."""
    start = next((i for i, ln in enumerate(lines) if re.match(r"^\s*ANNEE\s*:\s*\d{4}", ln)), None)
    if start is None:
        return []
    rows: list[dict[str, Any]] = []
    for ln in lines[start + 1:]:
        if "OPCVM" in ln:
            break
        m = _AG_ROW_RE.match(ln)
        if m:
            rows.append({k: clean_text(v) for k, v in m.groupdict().items()})
        elif rows and ln.startswith(" ") and ln.strip() and not _PAGE_NO_RE.match(ln) \
                and not _DATE_HEADER_RE.match(ln):
            rows[-1]["lieu"] = (rows[-1]["lieu"] + " " + clean_text(ln)).strip()
    return rows


def _boc_sp_symbols(lines: list[str], equity_symbols: Iterable[str]) -> set[str]:
    """Actions portant la mention « SP » (suspendu) dans le tableau des cours.

    La ligne commence par le symbole (BOC récents) ou par le code secteur puis le
    symbole (« TRP  SVOC  MOVIS CI ... SP »), et contient le mot isolé « SP ».
    """
    eq = set(equity_symbols)
    out = set()
    for ln in lines:
        if "SP" not in ln:
            continue
        toks = ln.split()
        if len(toks) < 3:
            continue
        if toks[0] in eq:
            sym = toks[0]
        elif re.fullmatch(r"[A-Z]{2,4}", toks[0]) and toks[1] in eq:
            sym = toks[1]
        else:
            continue
        if _SP_TOKEN_RE.search(ln):
            out.add(sym)
    return out


def _boc_published(boc_date: dt.date) -> dt.datetime:
    return dt.datetime.combine(boc_date, BOC_PUBLICATION_UTC, tzinfo=dt.timezone.utc)


def _boc_source(text: str, boc_date: dt.date | None) -> str:
    first = text.split("\n", 1)[0]
    m = re.match(r"#\s*source:\s*(\S+)", first)
    if m:
        return m.group(1)
    return f"{BASE_URL}/sites/default/files/boc_{boc_date:%Y%m%d}.pdf" if boc_date else BASE_URL


def parse_boc_events(text: str, boc_date: Any = None, source_url: str | None = None,
                     resolver: IssuerResolver | None = None, equity_symbols: Iterable[str] | None = None,
                     include_bonds: bool = False) -> list[dict[str, Any]]:
    """Éléments bruts des sections d'événements d'un BOC (document 07, §1.4).

    Types (``list_type``) : ``boc_operations``, ``boc_avis``, ``boc_communiques``,
    ``boc_ag`` (calendrier des AG ; ``boc_ag_annulation`` si la ligne porte
    « Annulé » ou « reporté »), ``boc_suspension`` (mention SP). Chaque élément porte
    ``extra["key"]``, une clé stable d'un BOC à l'autre (pour garder la première
    apparition). Le BOC paraît le soir : ``published_at`` = date du BOC à 19h00 UTC.
    Les lignes d'obligations (intérêts, remboursements) sont écartées sauf si
    ``include_bonds``.
    """
    resolver = resolver or default_resolver()
    lines = text.splitlines()
    day = _as_date(boc_date)
    if day is None:
        from brvm_alpha.data.boc_parser import _header_date  # lecture seule du module

        day = _header_date(lines[:40])
    src = source_url or _boc_source(text, day)
    published = _boc_published(day) if day else None
    eq_symbols = set(equity_symbols) if equity_symbols is not None else set(resolver.symbols)
    items: list[dict[str, Any]] = []

    def add(list_key: str, title: str, issuer: str | None, symbol: str | None, hint: str | None,
            body: str, key: str, extra: dict[str, Any] | None = None) -> None:
        it = _base_item(list_key, "boc", src, title, None, day, issuer, symbol, hint, body, published,
                        {"key": key, "boc_date": _iso(day), **(extra or {})})
        if not include_bonds and it["instrument"] in ("obligation", "fctc"):
            return
        items.append(it)

    sections = _boc_sections(lines)
    for cols in sections.get("OPERATIONS EN COURS", []):
        issuer, op = (cols + ["", ""])[:2]
        if not op:
            continue
        sym = resolver.resolve(issuer, op)
        hint = "DIV_NOTICE" if re.search(r"dividende", op, re.IGNORECASE) else None
        extra: dict[str, Any] = {}
        m = re.search(r"dividendes? de ([\d ,.]+)\s*F\s*CFA", op, re.IGNORECASE)
        if m:
            extra["div_net"] = _parse_amount(m.group(1))
            pay = re.search(r"le (\d{1,2}/\d{1,2}/\d{4})", op)
            extra["pay_date"] = _iso(parse_date_fr(pay.group(1))) if pay else None
        add("boc_operations", f"{issuer} : {op}", issuer, sym, hint,
            f"Bulletin officiel de la cote, opérations en cours : {issuer} — {op}",
            f"op|{norm_label(issuer)}|{norm_label(op)}", extra)
    for cols in sections.get("AVIS", []):
        entity, no, nature, obj = (cols + ["", "", "", ""])[:4]
        if not (obj or nature):
            continue
        if re.search(r"int[ée]r[êe]ts|remboursement", nature, re.IGNORECASE) and not include_bonds:
            continue
        tail = re.split(r"\s+-\s+", obj)[-1] if obj else ""
        sym = resolver.resolve(tail, obj)
        hint = "DIV_NOTICE" if re.search(r"dividende", nature + obj, re.IGNORECASE) else None
        add("boc_avis", f"Avis {no} ({entity}) : {obj or nature}", entity, sym, hint,
            f"Bulletin officiel de la cote, avis de {entity} — {nature} — {obj}",
            f"avis|{norm_label(entity)}|{norm_label(no)}", {"avis_no": no, "nature": nature})
    for cols in sections.get("COMMUNIQUES", []):
        issuer, no, nature, obj = (cols + ["", "", "", ""])[:4]
        if not (obj or nature):
            continue
        sym = resolver.resolve(issuer, obj)
        add("boc_communiques", obj or nature, issuer, sym, None,
            f"Bulletin officiel de la cote, communiqué de {issuer or 'l’émetteur'} — {nature} — {obj}",
            f"comm|{norm_label(issuer)}|{norm_label(no)}|{norm_label(obj)}", {"numero": no, "nature": nature})
    for ag in _boc_ag_rows(lines):
        ag_date = parse_date_fr(ag["date"])
        sym = resolver.resolve(ag["soc"], None)
        cancel = bool(_AG_CANCEL_RE.search(ag.get("lieu", "")))
        nature = ag["nature"].capitalize()
        base_key = f"ag|{norm_label(ag['soc'])}|{norm_label(nature)}|{_iso(ag_date)}"
        extra = {"ag_date": _iso(ag_date), "ag_type": nature, "ag_time": ag.get("heure") or None,
                 "lieu": ag.get("lieu") or None}
        add("boc_ag", f"{ag['soc']} : Assemblée Générale {nature} du {_fmt(ag_date)}", ag["soc"], sym,
            "AG_CONVOCATION", f"Calendrier des AG du bulletin officiel de la cote : {ag['soc']}, AG {nature.lower()} le "
            f"{_fmt(ag_date)}" + (f" à {ag['heure']}" if ag.get("heure") else "") + f", {ag.get('lieu', '')}",
            base_key, extra)
        if cancel:
            mention = re.search(r"\(?([^()]*(?:annul|report)[^()]*)\)?", ag["lieu"], re.IGNORECASE)
            add("boc_ag_annulation",
                f"{ag['soc']} : Annulation ou report de l'Assemblée Générale {nature} du {_fmt(ag_date)}",
                ag["soc"], sym, "AG_CANCEL",
                f"Calendrier des AG du bulletin officiel de la cote : AG {nature.lower()} de {ag['soc']} du {_fmt(ag_date)} — "
                f"{mention.group(1).strip() if mention else ag['lieu']}", base_key + "|annulation", extra)
    for sym in sorted(_boc_sp_symbols(lines, eq_symbols)):
        add("boc_suspension", f"{sym} : cotation suspendue (mention SP au BOC du {_fmt(day)})", None, sym,
            "SUSPENSION", f"Le BOC du {_fmt(day)} porte la mention SP (suspendu) pour {sym}.",
            f"sp|{sym}", {"suspended": True})
    return items


_BOC_FILE_RE = re.compile(r"^boc_(\d{8})\.txt(?:\.gz)?$")


def list_boc_files(boc_dir: str | Path = DEFAULT_BOC_DIR) -> list[tuple[dt.date, Path]]:
    """Fichiers ``boc_AAAAMMJJ.txt[.gz]`` triés par date."""
    out = []
    for p in Path(boc_dir).glob("boc_*.txt*"):
        m = _BOC_FILE_RE.match(p.name)
        if m:
            out.append((dt.datetime.strptime(m.group(1), "%Y%m%d").date(), p))
    return sorted(out)


@lru_cache(maxsize=4096)
def _read_boc(path: str, mtime: float) -> str:
    from brvm_alpha.data.boc_parser import read_boc_text

    return read_boc_text(path)


def _boc_text(path: Path) -> str:
    return _read_boc(str(path), path.stat().st_mtime)


def collect_boc_events(boc_dir: str | Path = DEFAULT_BOC_DIR, *, since: Any = None, until: Any = None,
                       last_n: int | None = 10, lookback_files: int = 60, resolver: IssuerResolver | None = None,
                       include_bonds: bool = False, max_suspension_walkback: int = 2000) -> list[dict[str, Any]]:
    """Événements des BOC locaux d'une fenêtre, datés de leur **première apparition**.

    La fenêtre est ``[since, until]`` (dates des BOC) ou, sans ``since``, les
    ``last_n`` derniers BOC. Les ``lookback_files`` BOC précédents sont lus pour dater
    la première apparition d'un élément déjà présent au début de la fenêtre. Seuls
    les éléments présents dans la fenêtre sont renvoyés ; pour le calendrier des AG,
    seules les AG dont la date n'est pas antérieure de plus de 7 jours au début de
    la fenêtre. Une suspension (mention SP) est datée du premier BOC de la série
    continue de mentions (recherche en arrière) ; une reprise (``boc_reprise``,
    ``RESUMPTION``) est émise au premier BOC sans mention.
    """
    resolver = resolver or default_resolver()
    files = list_boc_files(boc_dir)
    if not files:
        return []
    until_d = _as_date(until)
    if until_d:
        files = [f for f in files if f[0] <= until_d]
    since_d = _as_date(since)
    if since_d:
        win_idx = [i for i, (d, _) in enumerate(files) if d >= since_d]
    else:
        win_idx = list(range(max(0, len(files) - (last_n or len(files))), len(files)))
    if not win_idx:
        return []
    w0 = win_idx[0]
    window_start = files[w0][0]
    scan = range(max(0, w0 - lookback_files), win_idx[-1] + 1)
    first_seen: dict[str, dict[str, Any]] = {}
    in_window: set[str] = set()
    sp_by_file: dict[int, set[str]] = {}
    for i in scan:
        d, path = files[i]
        text = _boc_text(path)
        for it in parse_boc_events(text, d, None, resolver, include_bonds=include_bonds):
            key = it["extra"]["key"]
            if it["list_type"] == "boc_suspension":
                sp_by_file.setdefault(i, set()).add(it["symbol"])
                continue
            if key not in first_seen:
                first_seen[key] = it
            if i >= w0:
                in_window.add(key)
    out = []
    for key, it in first_seen.items():
        if key not in in_window:
            continue
        if it["list_type"].startswith("boc_ag"):
            agd = _as_date(it["extra"].get("ag_date"))
            if agd and agd < window_start - dt.timedelta(days=7):
                continue
            first = _as_date(it["extra"].get("boc_date"))
            if it["list_type"] == "boc_ag" and agd and first and agd < first:
                continue  # AG déjà tenue quand elle apparaît au calendrier : rien à anticiper
        it["extra"]["first_seen_boc"] = it["extra"].get("boc_date")
        out.append(it)
    out.extend(_suspension_events(files, sp_by_file, w0, win_idx[-1], resolver, max_suspension_walkback))
    return out


def _sp_in_file(files: list[tuple[dt.date, Path]], i: int, resolver: IssuerResolver,
                cache: dict[int, set[str]]) -> set[str]:
    if i not in cache:
        cache[i] = _boc_sp_symbols(_boc_text(files[i][1]).splitlines(), resolver.symbols)
    return cache[i]


def _suspension_events(files, sp_by_file: dict[int, set[str]], w0: int, w1: int, resolver: IssuerResolver,
                       max_walkback: int) -> list[dict[str, Any]]:
    """Suspensions (début de série SP) et reprises (fin de série) touchant la fenêtre."""
    out: list[dict[str, Any]] = []
    cache = dict(sp_by_file)
    seen: set[tuple[str, str]] = set()
    for i in range(w0, w1 + 1):
        cur = _sp_in_file(files, i, resolver, cache)
        prev = _sp_in_file(files, i - 1, resolver, cache) if i > 0 else set()
        for sym in sorted(cur):
            # début de la série continue de mentions SP (recherche en arrière)
            j = i
            steps = 0
            while j > 0 and steps < max_walkback and sym in _sp_in_file(files, j - 1, resolver, cache):
                j -= 1
                steps += 1
            start = files[j][0]
            key = ("SUSPENSION", f"{sym}|{start}")
            if key in seen:
                continue
            seen.add(key)
            src = _boc_source(_boc_text(files[j][1]), start)
            it = _base_item("boc_suspension", "boc", src, f"{sym} : cotation suspendue (mention SP depuis le BOC du "
                            f"{_fmt(start)})", None, start, None, sym, "SUSPENSION",
                            f"Le BOC du {_fmt(start)} porte pour la première fois la mention SP (suspendu) pour {sym} ; "
                            f"mention toujours présente au BOC du {_fmt(files[i][0])}." if i != j else
                            f"Le BOC du {_fmt(start)} porte la mention SP (suspendu) pour {sym}.",
                            _boc_published(start),
                            {"key": f"sp|{sym}|{start}", "boc_date": _iso(start), "suspended_since": _iso(start),
                             "walkback_capped": steps >= max_walkback})
            out.append(it)
        for sym in sorted(prev - cur):
            d = files[i][0]
            key = ("RESUMPTION", f"{sym}|{d}")
            if key in seen:
                continue
            seen.add(key)
            src = _boc_source(_boc_text(files[i][1]), d)
            out.append(_base_item("boc_reprise", "boc", src, f"{sym} : reprise de la cotation (fin de la mention SP "
                                  f"au BOC du {_fmt(d)})", None, d, None, sym, "RESUMPTION",
                                  f"La mention SP (suspendu) de {sym} disparaît au BOC du {_fmt(d)}.",
                                  _boc_published(d), {"key": f"reprise|{sym}|{d}", "boc_date": _iso(d)}))
    return out


# ---------------------------------------------------------------------------
# Couche (a) — documents PDF
# ---------------------------------------------------------------------------


def extract_pdf_text(path: str | Path, min_chars_per_page: int = OCR_MIN_CHARS_PER_PAGE) -> dict[str, Any]:
    """Texte d'un PDF : ``pdftotext -layout`` puis repli ``pdfplumber``.

    Renvoie ``text``, ``n_pages``, ``chars_per_page`` (moyenne), ``ocr_needed``
    (moins de ``min_chars_per_page`` caractères par page : document scanné, à
    passer à l'OCR) et ``method``. L'OCR n'est pas lancé ici.
    """
    path = Path(path)
    text, method, n_pages = "", None, 0
    if shutil.which("pdftotext"):
        try:
            out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, timeout=120)
            text = out.stdout.decode("utf-8", errors="replace")
            method = "pdftotext"
        except (OSError, subprocess.SubprocessError):
            text = ""
        if shutil.which("pdfinfo"):
            try:
                info = subprocess.run(["pdfinfo", str(path)], capture_output=True, timeout=60)
                m = re.search(r"^Pages:\s+(\d+)", info.stdout.decode("utf-8", "replace"), re.MULTILINE)
                n_pages = int(m.group(1)) if m else 0
            except (OSError, subprocess.SubprocessError):
                n_pages = 0
    if not text.strip():
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                pages = [(p.extract_text() or "") for p in pdf.pages]
            text = "\n\f".join(pages)
            n_pages = len(pages)
            method = "pdfplumber"
        except Exception as exc:  # PDF illisible
            return {"text": "", "n_pages": n_pages, "chars_per_page": 0.0, "ocr_needed": True,
                    "method": method, "error": f"{type(exc).__name__}: {exc}"}
    if not n_pages:
        n_pages = max(1, text.count("\f") + (0 if text.endswith("\f") else 1)) if text else 1
    chars = len(re.sub(r"\s+", "", text))
    cpp = chars / max(n_pages, 1)
    return {"text": text, "n_pages": n_pages, "chars_per_page": round(cpp, 1),
            "ocr_needed": cpp < min_chars_per_page, "method": method}


def fetch_document(session: PoliteSession, url: str, cache_dir: str | Path | None = None) -> dict[str, Any]:
    """Télécharge (une seule fois) un PDF public et en extrait le texte.

    Cache par empreinte sha256 de l'URL sous ``cache_dir`` (défaut :
    ``data/notes/cache/docs``) : ``<sha>.pdf`` et ``<sha>.json`` (métadonnées et
    texte). Un document déjà en cache n'est jamais retéléchargé.
    """
    cache = Path(cache_dir) if cache_dir is not None else session.cache_dir / "docs"
    h = url_hash(url)
    meta_p, pdf_p = cache / f"{h}.json", cache / f"{h}.pdf"
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            meta["cached"] = True
            return meta
        except ValueError:
            pass
    res = session.get(url, immutable=True)
    if res.status != 200:
        return {"url": url, "sha256": h, "status": res.status, "text": "", "ocr_needed": None,
                "error": f"HTTP {res.status}"}
    if not res.content.startswith(b"%PDF"):
        return {"url": url, "sha256": h, "status": res.status, "text": "", "ocr_needed": None,
                "error": "le document n'est pas un PDF"}
    cache.mkdir(parents=True, exist_ok=True)
    pdf_p.write_bytes(res.content)
    info = extract_pdf_text(pdf_p)
    meta = {"url": url, "sha256": h, "status": 200, "path": str(pdf_p), "bytes": len(res.content),
            "text_sha256": hashlib.sha256(info["text"].encode("utf-8")).hexdigest(), **info, "cached": False}
    meta_p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


# ---------------------------------------------------------------------------
# Couche (a) — page publique quelconque (URL donnée par l'analyste)
# ---------------------------------------------------------------------------


def extract_html_content(html: str | bytes, url: str = "") -> dict[str, Any]:
    """Titre, date de publication et texte principal d'une page HTML publique."""
    soup = _soup(html)
    title = ""
    for sel in (("meta", {"property": "og:title"}), ("meta", {"name": "twitter:title"})):
        tag = soup.find(*sel)
        if tag and tag.get("content"):
            title = clean_text(tag["content"])
            break
    if not title:
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True)) if h1 else ""
    if not title and soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))
    published: dt.datetime | None = None
    date_source = None
    for attrs in ({"property": "article:published_time"}, {"name": "date"}, {"name": "DC.date.issued"},
                  {"name": "dc.date"}, {"itemprop": "datePublished"}, {"name": "pubdate"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            try:
                published = to_utc(pd.Timestamp(tag["content"]))
                date_source = "meta"
                break
            except (ValueError, TypeError):
                continue
    if published is None:
        tag = soup.find("time", attrs={"datetime": True}) or soup.find(class_="date-display-single",
                                                                      attrs={"content": True})
        if tag is not None:
            try:
                published = to_utc(pd.Timestamp(tag.get("datetime") or tag.get("content")))
                date_source = "time"
            except (ValueError, TypeError):
                published = None
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "form", "aside", "iframe", "svg"]):
        t.decompose()
    main = (soup.find("article") or soup.find("main") or soup.find(id="content")
            or soup.find(class_="region-content") or soup.body or soup)
    raw = main.get_text("\n", strip=True)
    lines = [clean_text(x) for x in raw.split("\n")]
    text = "\n".join(x for x in lines if x)
    return {"title": title, "text": text[:MAX_TEXT_CHARS], "published_at": published, "date_source": date_source,
            "n_chars": len(text)}


def _disabled_domain(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    for dom, why in DISABLED_DOMAINS.items():
        if host == dom or host.endswith("." + dom):
            return why
    return None


# ---------------------------------------------------------------------------
# Cibles : restriction de la recherche
# ---------------------------------------------------------------------------


@dataclass
class TargetScope:
    """Périmètre d'une recherche ciblée (symboles, pays, thèmes, indices)."""

    all_market: bool = True
    symbols: set[str] = field(default_factory=set)
    countries: set[str] = field(default_factory=set)
    themes: list[str] = field(default_factory=list)
    indices: list[str] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)

    def matches(self, item: Mapping[str, Any]) -> bool:
        """``True`` si l'élément brut concerne le périmètre."""
        if self.all_market:
            return True
        sym = item.get("symbol")
        if sym and sym in self.symbols:
            return True
        if not sym and item.get("country") and item["country"] in self.countries:
            return True
        if not sym and self.indices and (item.get("market_level") or (item.get("extra") or {}).get("index_related")):
            return True
        if self.themes:
            blob = norm_label(f"{item.get('title', '')} {item.get('text', '')}")
            if any(f" {t} " in f" {blob} " for t in self.themes):
                return True
        return False

    def issuer_symbols(self, universe: Iterable[str]) -> list[str]:
        """Symboles dont la page « rapports » est à lire."""
        if self.all_market:
            return sorted(set(universe))
        return sorted(self.symbols)


def _latest_cross_section(panels: Mapping[str, Any] | None, panel_dir: str | Path | None) -> pd.DataFrame | None:
    eq = None
    if panels is not None:
        eq = panels.get("equities") if isinstance(panels, Mapping) else None
    if eq is None and panel_dir is not None:
        try:
            eq = pd.read_parquet(Path(panel_dir) / "equities.parquet",
                                 columns=["date", "symbol", "sector", "compartment"])
        except Exception:
            eq = None
    if eq is None or not {"date", "symbol"} <= set(eq.columns):
        return None
    last = eq[eq["date"] == eq["date"].max()]
    return last.drop_duplicates("symbol").set_index("symbol")


def _index_constituents(code: str) -> list[str] | None:
    """Constituants d'un indice via ``notes.entities`` s'il les fournit."""
    try:
        from brvm_alpha.notes import entities as ent  # type: ignore
    except Exception:
        return None
    for fname in ("index_constituents", "constituents", "index_members"):
        fn = getattr(ent, fname, None)
        if callable(fn):
            try:
                out = fn(code)
            except Exception:
                return None
            if out:
                return [str(s) for s in out]
    return None


def expand_targets(targets: Iterable[str] | None, panels: Mapping[str, Any] | None = None,
                   panel_dir: str | Path | None = DEFAULT_PANEL_DIR) -> TargetScope:
    """Traduit des codes de cibles (contrat ``notes``) en périmètre de collecte.

    - ``SNTS`` : le titre ;
    - ``IDX:BRVM-C``, ``IDX:BRVM-C-TR``, ``MARCHE`` : tout le marché ;
    - ``IDX:BRVM-30`` : ses constituants (``entities`` ou avis 289-2026) ;
    - ``IDX:PRESTIGE`` / ``IDX:PRINCIPAL`` : compartiment au dernier BOC ;
    - ``IDX:SECT:<code>`` / ``SECT:<code>`` : titres du secteur BOC ;
    - ``PAYS:CI`` : émetteurs du pays (et événements souverains du pays) ;
    - ``THEME:<mot>`` : éléments dont le titre ou le texte contient le mot.
    """
    if not targets:
        return TargetScope(all_market=True)
    from brvm_alpha.reference import SYMBOLS_2026, country_of

    xs = _latest_cross_section(panels, panel_dir)
    universe = list(xs.index) if xs is not None else list(SYMBOLS_2026)
    sectors = (xs["sector"].to_dict() if xs is not None and "sector" in xs else dict(FALLBACK_SECTORS))
    comps = (xs["compartment"].to_dict() if xs is not None and "compartment" in xs else
             {s: ("PRESTIGE" if s in FALLBACK_COMPARTMENT_PRESTIGE else "PRINCIPAL") for s in SYMBOLS_2026})
    scope = TargetScope(all_market=False, raw=list(targets))
    for raw in targets:
        code = str(raw).strip()
        up = code.upper()
        if up in ("MARCHE", "IDX:BRVM-C", "IDX:BRVM-C-TR", "IDX:BRVM-COMPOSITE"):
            scope.all_market = True
            scope.indices.append(up)
        elif up.startswith("IDX:"):
            scope.indices.append(up)
            name = up[4:]
            members = _index_constituents(up)
            if members is None:
                if name in ("BRVM-30", "BRVM30"):
                    members = list(BRVM30_T4_2026)
                elif name in ("PRESTIGE", "PRINCIPAL"):
                    members = [s for s in universe if str(comps.get(s, "")).upper() == name]
                elif name.startswith("SECT:"):
                    members = [s for s in universe if str(sectors.get(s, "")).upper() == name[5:]]
                else:
                    members = []
            scope.symbols.update(members)
        elif up.startswith("PAYS:"):
            c = up[5:]
            scope.countries.add(c)
            scope.symbols.update(s for s in universe if country_of(s) == c)
        elif up.startswith("SECT:"):
            scope.symbols.update(s for s in universe if str(sectors.get(s, "")).upper() == up[5:])
        elif up.startswith("THEME:"):
            scope.themes.append(norm_label(code[6:]))
        elif re.fullmatch(r"[A-Z]{3,6}", up):
            scope.symbols.add(up)
        else:
            raise ValueError(f"Code de cible non reconnu : {code!r}")
    return scope


# ---------------------------------------------------------------------------
# Calendrier des séances et première séance négociable
# ---------------------------------------------------------------------------


def load_calendar(panel_dir: str | Path | None = DEFAULT_PANEL_DIR) -> pd.DatetimeIndex:
    """Dates des séances BRVM (``sessions.parquet``, séances sans BOC comprises)."""
    try:
        from brvm_alpha.data.store import load_sessions

        s = load_sessions(panel_dir)
        return pd.DatetimeIndex(pd.to_datetime(s["date"]).dt.normalize().unique()).sort_values()
    except Exception:
        return pd.DatetimeIndex([])


def _sessions_for(panel_dir: str | Path | None) -> pd.DataFrame | None:
    """Calendrier ``sessions.parquet`` d'un panel donné ; ``None`` = calendrier par défaut du modèle."""
    if panel_dir is None or Path(panel_dir).resolve() == DEFAULT_PANEL_DIR.resolve():
        return None
    try:
        return pd.read_parquet(Path(panel_dir) / "sessions.parquet")
    except Exception:
        return None


def first_tradable_session(published_at: Any, calendar: pd.DatetimeIndex | None = None,
                           cutoff: dt.time = NEWS_CUTOFF_UTC) -> pd.Timestamp:
    """Première séance dont le fixing d'ouverture (09h45 UTC) suit la publication.

    Règle du document 07 §2.3 : publiée avant 09h00 UTC un jour de séance -> ce
    jour-là ; sinon la séance suivante. Au-delà du calendrier connu, les jours
    ouvrés (lundi-vendredi) servent de séances.
    """
    ts = to_utc(published_at)
    day = pd.Timestamp(ts.date())
    cal = calendar if calendar is not None else pd.DatetimeIndex([])

    def is_session(d: pd.Timestamp) -> bool:
        if len(cal) and cal[0] <= d <= cal[-1]:
            return d in cal
        return d.weekday() < 5

    if ts.timetz().replace(tzinfo=None) < cutoff and is_session(day):
        return day
    d = day + pd.Timedelta(days=1)
    if len(cal) and d <= cal[-1]:
        pos = cal.searchsorted(d)
        if pos < len(cal):
            return cal[pos]
    while not is_session(d):
        d += pd.Timedelta(days=1)
    return d


def _next_session_day(d: dt.date, calendar: Any = None) -> dt.date:
    """Séance qui suit le jour ``d`` (calendrier du modèle si disponible, sinon jours ouvrés)."""
    try:
        from brvm_alpha.notes.model import SessionCalendar, default_calendar

        cal = calendar if isinstance(calendar, SessionCalendar) else (
            SessionCalendar(calendar) if calendar is not None else default_calendar())
        return cal.next_session(pd.Timestamp(d)).date()
    except Exception:
        nxt = d + dt.timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += dt.timedelta(days=1)
        return nxt


def item_published_at(item: Mapping[str, Any], seen_at: dt.datetime,
                      calendar: Any = None) -> tuple[dt.datetime, str, bool]:
    """Publication prudente d'un élément brut : ``(horodatage, précision, estimé)``.

    - horodatage précis (avis : date + heure ; BOC : 19h00 UTC) : retenu, borné par ``seen_at`` ;
    - date de mise en ligne (colonne de la liste) : précision ``"date"`` (réputée connue en
      fin de journée, donc négociable à la séance suivante) ;
    - date lue dans le **nom du fichier** (date du document, pas de sa mise en ligne) :
      reportée d'une séance, par prudence (document 07 §6.8 : ``doc_date`` + 1 séance) ;
    - plancher prudent (dividende à date d'avis suspecte) : appliqué s'il est plus tard ;
    - si la fin du jour retenu est postérieure à ``seen_at``, on retient ``seen_at``
      (l'élément était déjà en ligne quand le collecteur l'a vu) ;
    - aucune date : ``seen_at`` (première fois que notre collecteur l'a vu).
    """
    seen = to_utc(seen_at)
    extra = item.get("extra") or {}
    override = extra.get("published_override")
    if override:
        ts = to_utc(override["ts"])
        prec = override.get("precision", "datetime")
        eff = dt.datetime.combine(ts.date(), dt.time(23, 59, 59), tzinfo=dt.timezone.utc) if prec == "date" else ts
        return (ts, prec, True) if eff <= seen else (seen, "datetime", True)
    floor = _as_date(extra.get("published_floor"))
    if item.get("published_at"):
        ts = min(to_utc(item["published_at"]), seen)
        if floor is not None:
            eod = dt.datetime.combine(floor, dt.time(23, 59, 59), tzinfo=dt.timezone.utc)
            if eod > ts:
                return (to_utc(floor), "date", True) if eod <= seen else (seen, "datetime", True)
        return ts, "datetime", False
    d = _as_date(item.get("doc_date"))
    if d is None:
        return seen, "datetime", True
    if item.get("date_source") == "fichier":
        d = _next_session_day(d, calendar)
    if floor is not None and floor > d:
        d = floor
    eod = dt.datetime.combine(d, dt.time(23, 59, 59), tzinfo=dt.timezone.utc)
    if eod <= seen:
        return to_utc(d), "date", True
    return seen, "datetime", True


def _effective_published(item: Mapping[str, Any], seen_at: dt.datetime, calendar: Any = None) -> dt.datetime:
    ts, prec, _ = item_published_at(item, seen_at, calendar)
    return dt.datetime.combine(ts.date(), dt.time(23, 59, 59), tzinfo=dt.timezone.utc) if prec == "date" else ts


def _merge_publication(kept: dict[str, Any], dup: Mapping[str, Any], seen_at: dt.datetime,
                       calendar: Any = None) -> None:
    """Deux sources pour le même document : on garde la publication la plus tôt.

    Chaque source donne une borne supérieure prudente de l'instant de publication (fin
    du jour de mise en ligne, BOC du soir, avis horodaté) : la plus petite des deux reste
    une borne prudente. Exemple : l'avis de dividende de la liste « paiement de
    dividendes » (date du nom de fichier + 1 séance) et le même PDF dans la liste des
    avis (date et heure exactes).
    """
    a = _effective_published(kept, seen_at, calendar)
    b = _effective_published(dup, seen_at, calendar)
    if b < a:
        ts, prec, _ = item_published_at(dup, seen_at, calendar)
        kept.setdefault("extra", {})["published_override"] = {"ts": ts.isoformat(), "precision": prec,
                                                               "from": dup.get("list_type")}


# ---------------------------------------------------------------------------
# Couche (b) — conversion en notes, déduplication, analyse, ajout au journal
# ---------------------------------------------------------------------------


def note_id_for(item: Mapping[str, Any]) -> str:
    """Identifiant stable d'une note automatique : même document -> même identifiant.

    Clé : URL normalisée du document (quelle que soit la liste ou la page qui l'a
    montré), sinon la clé stable d'un événement de BOC, sinon page + titre + date.
    Le hachage est celui du modèle (``model.make_note_id``, sha1) quand il existe.
    """
    extra = item.get("extra") or {}
    if item.get("source") == "boc" and extra.get("key"):
        basis = "boc://" + str(extra["key"])
    else:
        basis = item_key(item)
    try:
        from brvm_alpha.notes.model import make_note_id

        return make_note_id("auto", url=basis)
    except Exception:
        return hashlib.sha1(("auto|" + basis + "|").encode("utf-8")).hexdigest()


_SIG_STOP = {"LE", "LA", "LES", "DE", "DU", "DES", "D", "L", "ET", "A", "AU", "AUX", "EN", "SUR", "POUR", "PAR",
             "UN", "UNE", "ME", "EME", "ER", "S", "SA", "CI", "SN", "BF", "BN", "ML", "NG", "TG", "COMMUNIQUE"}


def content_signature(title: str | None, symbol: str | None = None) -> str:
    """Signature de contenu d'un titre (sans l'émetteur ni les mots vides).

    Sert à repérer le même document vu par deux sources (liste brvm.org et BOC).
    """
    n = norm_label(title)
    if symbol:
        for alias in ISSUER_ALIASES.get(symbol, ()):
            a = norm_label(alias)
            n = re.sub(rf"\b{re.escape(a)}\b", " ", n)
    n = n.replace("TROISIEME", "3E").replace("3EME", "3E").replace("PREMIER", "1ER")
    toks = sorted({t for t in n.split() if t not in _SIG_STOP and (len(t) >= 3 or t.isdigit() or t[:-1].isdigit())})
    return " ".join(toks)


def _model_module():
    """Module ``notes.model`` (importé à la demande : la couche (a) n'en dépend pas)."""
    from brvm_alpha.notes import model as model_mod

    return model_mod


def _analyze(note: Any, panels: Mapping[str, Any] | None = None, structured: Mapping[str, Any] | None = None,
             sessions: Any = None, history: pd.DataFrame | None = None) -> dict[str, Any]:
    """Analyse d'une note par ``notes.analyze.analyze_note`` -> dictionnaire.

    ``structured`` : champs lus dans une liste structurée (montant, dates ex et de
    paiement, date d'AG, parité...) que l'analyse retient avec une confiance de 1,0.
    """
    from brvm_alpha.notes import analyze as analyze_mod

    kwargs: dict[str, Any] = {"panels": panels, "asof": None}
    if structured:
        kwargs["structured"] = dict(structured)
    if sessions is not None:
        kwargs["sessions"] = sessions
    if history is not None:
        kwargs["history"] = history
    try:
        analysis = analyze_mod.analyze_note(note, **kwargs)
    except TypeError:  # version d'analyze sans ces paramètres facultatifs
        analysis = analyze_mod.analyze_note(note, panels=panels)
    return _analysis_to_dict(analysis) or {}


#: Champs structurés des listes transmis à l'analyse (confiance d'extraction 1,0).
STRUCTURED_KEYS = ("div_net", "ex_date", "pay_date", "record_date", "ag_date", "ag_type", "split_ratio",
                   "split_date", "parity_ratio", "delisting_date", "suspended_since")


def _analysis_to_dict(analysis: Any) -> dict[str, Any] | None:
    if analysis is None:
        return None
    if isinstance(analysis, Mapping):
        return dict(analysis)
    for meth in ("to_dict", "as_dict"):
        fn = getattr(analysis, meth, None)
        if callable(fn):
            return dict(fn())
    if dataclasses.is_dataclass(analysis):
        return dataclasses.asdict(analysis)
    return dict(vars(analysis))


_GENERIC_TYPES = {None, "", "AUTRE", "INCONNU", "UNKNOWN", "OTHER", "NONE", "GENERAL", "GENERIQUE", "PRESS"}


def _make_note(model_mod: Any, **kwargs: Any) -> Any:
    """Construit une ``Note`` en ne passant que les champs qu'elle déclare."""
    Note = model_mod.Note
    if dataclasses.is_dataclass(Note):
        names = {f.name for f in dataclasses.fields(Note)}
        kwargs = {k: v for k, v in kwargs.items() if k in names}
    return Note(**kwargs)


def _note_get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _set(obj: Any, name: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[name] = value
    else:
        try:
            setattr(obj, name, value)
        except (AttributeError, dataclasses.FrozenInstanceError):
            pass


def _tradable(published_at: Any, calendar: Any = None, precision: str = "datetime") -> pd.Timestamp:
    """Première séance négociable : ``model.first_tradable_session`` (calendrier du panel,
    fériés fixes), sinon la règle locale :func:`first_tradable_session`."""
    try:
        from brvm_alpha.notes.model import first_tradable_session as model_fts
    except Exception:
        model_fts = None
    if model_fts is not None:
        out = model_fts(published_at, sessions=calendar, date_only=precision == "date")
        if out is not None:
            return pd.Timestamp(out)
    ts = to_utc(published_at)
    if precision == "date":
        ts = dt.datetime.combine(ts.date(), dt.time(23, 59, 59), tzinfo=dt.timezone.utc)
    cal = calendar if isinstance(calendar, pd.DatetimeIndex) else None
    return first_tradable_session(ts, cal)


def item_to_note(item: Mapping[str, Any], *, now: dt.datetime | None = None,
                 calendar: Any = None, analyze: bool = True,
                 panels: Mapping[str, Any] | None = None, history: pd.DataFrame | None = None) -> Any:
    """Convertit un élément brut en ``Note`` analysée (couche b).

    ``targets`` = symbole de l'élément (ou ``PAYS:XX`` pour un événement souverain,
    ``MARCHE`` pour un avis de marché) ; ``event_type`` = type indiqué par une liste
    structurée (dividendes, fractionnements...) sinon celui de l'analyse ;
    ``analysis["extracted"]`` est complété par les champs structurés de la liste
    (montant, dates ex et de paiement, date d'AG...), plus sûrs qu'une expression
    régulière sur un PDF.
    """
    model_mod = _model_module()
    now = to_utc(now or utcnow())
    published, precision, estimated = item_published_at(item, now, calendar)
    fts = _tradable(published, calendar, precision)
    extra = dict(item.get("extra") or {})
    targets: list[str] = []
    if item.get("symbol"):
        targets.append(item["symbol"])
    elif item.get("country"):
        targets.append(f"PAYS:{item['country']}")
    elif item.get("market_level"):
        targets.append("MARCHE")
    tags = ["auto", f"liste:{item.get('list_type')}"]
    if estimated:
        tags.append("date_estimee")
    if extra.get("date_suspect"):
        tags.append("date_suspecte")
    if extra.get("symbol_conflict"):
        tags.append("emetteur_a_verifier")
    if extra.get("ocr_needed"):
        tags.append("ocr_requis")
    if item.get("instrument"):
        tags.append(f"instrument:{item['instrument']}")
    hint = item.get("event_hint")
    text = item.get("text") or ""
    if extra.get("doc_text"):
        text = (text + "\n\n" + extra["doc_text"]).strip()
    text = text[:MAX_TEXT_CHARS]
    url = item.get("doc_url") or item.get("page_url")
    note = _make_note(
        model_mod,
        note_id=note_id_for(item),
        created_at=now,
        published_at=published,
        published_precision=precision,
        first_tradable_session=fts,
        author="auto",
        source=item.get("source") or "brvm_list",
        url=url,
        title=item.get("title") or "",
        text=text,
        targets=targets,
        event_type=hint if item.get("list_type") in STRUCTURAL_LISTS or item.get("source") == "boc" else None,
        stance=None,
        conviction=None,
        tags=tags,
        status="active",
        version=1,
        analysis=None,
    )
    if analyze:
        structured = {k: extra[k] for k in STRUCTURED_KEYS if extra.get(k) is not None}
        adict = _analyze(note, panels, structured, calendar, history)
        if structured:
            ex = dict(adict.get("extracted") or {})
            for k in ("exercice", "avis_no"):
                if extra.get(k) is not None:
                    ex.setdefault(k, extra[k])
            ex["source_structuree"] = item.get("list_type")
            adict["extracted"] = ex
        a_type = adict.get("event_type")
        if hint and (item.get("list_type") in STRUCTURAL_LISTS or a_type in _GENERIC_TYPES):
            adict["event_type"] = hint
        _set(note, "analysis", adict)
        if _note_get(note, "event_type") in _GENERIC_TYPES and adict.get("event_type"):
            _set(note, "event_type", adict["event_type"])
    elif hint and _note_get(note, "event_type") in _GENERIC_TYPES:
        _set(note, "event_type", hint)
    return note


def _store_frame(store: Any) -> pd.DataFrame:
    for kwargs in ({"status": None}, {}):
        try:
            df = store.list(**kwargs)
            if isinstance(df, pd.DataFrame):
                return df
        except TypeError:
            continue
        except Exception:
            break
    return pd.DataFrame()


def _store_has(store: Any, note_id: str, known_ids: set[str]) -> bool:
    if note_id in known_ids:
        return True
    try:
        return store.get(note_id) is not None
    except (KeyError, LookupError, FileNotFoundError):
        return False
    except Exception:
        return False


class _DateIndex:
    """Clé -> dates, pour retrouver vite un « même contenu » ou un « même événement » proche."""

    def __init__(self) -> None:
        self._d: dict[tuple[str, str], list[dt.date | None]] = {}

    def add(self, key: tuple[str, str], d: dt.date | None) -> None:
        self._d.setdefault(key, []).append(d)

    def near(self, key: tuple[str, str], d: dt.date | None, window: int) -> bool:
        return any(d is None or d2 is None or abs((d - d2).days) <= window for d2 in self._d.get(key, ()))

    def __len__(self) -> int:
        return sum(len(v) for v in self._d.values())


def _signature_index(frame: pd.DataFrame) -> _DateIndex:
    out = _DateIndex()
    if frame.empty or "title" not in frame.columns:
        return out
    for _, r in frame.iterrows():
        tg = r.get("targets")
        syms = [t for t in (list(tg) if isinstance(tg, (list, tuple, set)) or hasattr(tg, "__iter__")
                            and not isinstance(tg, str) else str(tg or "").split(",")) if t and ":" not in str(t)]
        sym = str(syms[0]).strip() if syms else ""
        d = _as_date(r.get("published_at"))
        out.add((sym, content_signature(r.get("title"), sym or None)), d)
    return out


def dedup_event_type(item: Mapping[str, Any]) -> str | None:
    """Type d'événement « unique » d'un élément (pour la déduplication entre sources)."""
    hint = item.get("event_hint")
    if hint in {t for t, _, _ in _DEDUP_TYPES} and item.get("list_type") != "boc_ag":
        return hint
    title = item.get("title") or ""
    for t, pat, _ in _DEDUP_TYPES:
        if pat.search(title):
            return t
    return hint if hint in {t for t, _, _ in _DEDUP_TYPES} else None


_DEDUP_WINDOW = {t: w for t, _, w in _DEDUP_TYPES}


def _event_date(item: Mapping[str, Any]) -> dt.date | None:
    extra = item.get("extra") or {}
    return _as_date(extra.get("first_seen_boc")) or _as_date(item.get("doc_date"))


def _is_event_duplicate(item: Mapping[str, Any], events: _DateIndex) -> bool:
    """Même événement (même titre, même type, dates proches) déjà retenu ou au journal ?

    Un dividende, un fractionnement, une annulation d'AG... apparaissent dans plusieurs
    sources (liste brvm.org, avis, BOC « opérations en cours », « avis »...). On garde
    la première version vue — les listes structurées passent en premier — pour ne pas
    compter plusieurs fois le même événement dans les scores.
    """
    sym = item.get("symbol")
    et = dedup_event_type(item)
    if not sym or not et:
        return False
    return events.near((sym, et), _event_date(item), _DEDUP_WINDOW.get(et, 15))


def _event_index(frame: pd.DataFrame) -> _DateIndex:
    """Événements « uniques » déjà au journal : (symbole, type) -> dates."""
    out = _DateIndex()
    if frame.empty or "title" not in frame.columns:
        return out
    for _, r in frame.iterrows():
        tg = r.get("targets")
        if isinstance(tg, str):
            tg = [t.strip() for t in re.split(r"[;,|]", tg)]
        syms = [t for t in (list(tg) if tg is not None and not isinstance(tg, float) else []) if t and ":" not in str(t)]
        if not syms:
            continue
        fake = {"symbol": syms[0], "title": r.get("title"), "event_hint": r.get("event_type"),
                "doc_date": _as_date(r.get("published_at"))}
        et = dedup_event_type(fake)
        if et:
            out.add((syms[0], et), fake["doc_date"])
    return out


def _is_duplicate(item: Mapping[str, Any], sigs: _DateIndex, days: int = 5) -> bool:
    """Même titre (signature de contenu) pour le même émetteur à ±``days`` jours ?"""
    sym = item.get("symbol") or ""
    sig = content_signature(item.get("title"), sym or None)
    return bool(sig) and sigs.near((sym, sig), _as_date(item.get("doc_date")), days)


@dataclass
class ResearchReport:
    """Bilan d'une recherche (attaché à la liste renvoyée par :func:`run_research`)."""

    n_items: int = 0
    n_new: int = 0
    n_duplicates: int = 0
    n_filtered: int = 0
    n_requests: int = 0
    errors: list[str] = field(default_factory=list)
    stopped: str | None = None
    lists: dict[str, int] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Bilan en français, en phrases courtes (pour l'analyste)."""
        lines = [
            f"{self.n_requests} requête(s) réseau ; {self.n_items} élément(s) lu(s) ; "
            f"{self.n_new} nouvelle(s) note(s) ; {self.n_duplicates} doublon(s) ; {self.n_filtered} écarté(s).",
        ]
        if self.stopped:
            lines.append(f"Collecte arrêtée : {self.stopped}. Aucune tentative de contournement.")
        if self.errors:
            lines.append(f"{len(self.errors)} incident(s) de collecte, dont : {self.errors[0]}")
        if self.unresolved:
            lines.append(f"{len(self.unresolved)} élément(s) sans émetteur coté reconnu ou sans date (voir unresolved).")
        return "\n".join(lines)


class ResearchResult(list):
    """Liste des notes ajoutées, avec le bilan dans ``.report``."""

    report: ResearchReport


def _store_add(store: Any, note: Any, now: dt.datetime) -> None:
    """Ajout au journal, avec l'instant d'écriture si le journal l'accepte."""
    try:
        store.add(note, now=now)
    except TypeError:
        store.add(note)


def _store_root(store: Any) -> Path:
    root = getattr(store, "root", None)
    return Path(root) if root is not None else DEFAULT_NOTES_DIR


def run_research(store: Any, targets: Iterable[str] | None = None, since: Any = None, max_requests: int = 150,
                 delay_s: float = 10.0, offline: bool = False, *, lists: Iterable[str] | None = None,
                 issuer_reports: bool = True, boc: bool = True, boc_dir: str | Path | None = None,
                 boc_last_n: int = 10, max_pages: int | None = None, download_pdfs: bool = False,
                 max_pdfs: int = 10, include_bonds: bool = False, skip_ancillary: bool = True,
                 keep_unresolved: bool = False, all_slugs: bool = False,
                 session: PoliteSession | None = None, panels: Mapping[str, Any] | None = None,
                 panel_dir: str | Path | None = DEFAULT_PANEL_DIR, calendar: Any = None,
                 now: dt.datetime | None = None, analyze: bool = True, dry_run: bool = False) -> ResearchResult:
    """Recherche automatique : brvm.org + BOC locaux -> notes analysées ajoutées au journal.

    Étapes :

    1. périmètre : ``targets`` (codes du contrat ; ``None`` = tout le marché) ;
    2. listes brvm.org (page 0, ou jusqu'à ``since`` / la première URL connue) :
       dividendes, augmentations de capital, fractionnements, radiations,
       annonces des émetteurs, avis ;
    3. pages « rapports » des émetteurs du périmètre (page 0) ;
    4. événements des BOC locaux (``boc_last_n`` derniers BOC, ou depuis ``since``) ;
    5. filtrage (périmètre ; obligations, pièces annexes, émetteurs non reconnus et
       documents sans date écartés par défaut), déduplication (``note_id`` stable = même
       document ; même titre pour un même émetteur à ±5 jours ; même événement unique
       — dividende, fractionnement, annulation d'AG, suspension... — vu par plusieurs
       sources), téléchargement facultatif des PDF nouveaux (``download_pdfs``),
       analyse (champs structurés transmis avec une confiance de 1,0) et ajout au
       journal (sauf ``dry_run``).

    ``calendar`` : calendrier des séances (``store.load_sessions``) ; par défaut celui
    du panel. ``now`` : instant de collecte (UTC), qui borne toute publication.

    Une erreur de collecte (403/429, quota, robots.txt) arrête la collecte réseau
    mais pas le traitement des éléments déjà lus ni des BOC locaux. Le bilan est
    dans ``result.report``.
    """
    root = _store_root(store)
    now = to_utc(now or utcnow())
    report = ResearchReport()
    sess = session or PoliteSession(delay_s=delay_s, max_requests=max_requests, offline=offline,
                                    cache_dir=root / "cache", log_path=root / "fetch_log.jsonl")
    scope = expand_targets(targets, panels, panel_dir)
    resolver = default_resolver(panel_dir)
    if calendar is None:
        calendar = _sessions_for(panel_dir)
    frame = _store_frame(store)
    known_urls = set(frame["url"].dropna().astype(str)) if "url" in frame.columns else set()
    since_d = _as_date(since)
    pages = max_pages if max_pages is not None else (60 if since_d else 1)

    raw: list[dict[str, Any]] = []
    for key in (lists if lists is not None else BRVM_LISTS):
        if sess.stopped or sess.n_requests >= sess.max_requests:
            break
        try:
            got = collect_list(sess, key, since=since_d, known_urls=known_urls, max_pages=pages,
                               resolver=resolver, errors=report.errors)
        except ResearchError as exc:  # pragma: no cover - collect_list capture déjà
            report.errors.append(f"{key} : {exc}")
            got = []
        report.lists[key] = len(got)
        raw.extend(got)
    if issuer_reports and not sess.stopped:
        from brvm_alpha.reference import SYMBOLS_2026

        stop_issuers = False
        for sym in scope.issuer_symbols(SYMBOLS_2026):
            if stop_issuers or sess.stopped or sym not in ISSUER_SLUGS:
                continue
            got = []
            for slug in ISSUER_SLUGS[sym] if all_slugs else ISSUER_SLUGS[sym][:1]:
                try:
                    got += collect_issuer_reports(sess, sym, slug, since=since_d, known_urls=known_urls,
                                                  resolver=resolver, errors=report.errors)
                except ResearchError as exc:
                    report.errors.append(f"rapports {sym} ({slug}) : {exc}")
                    if isinstance(exc, (QuotaExceeded, AccessBlocked, ServerUnavailable)):
                        stop_issuers = True
                        break
            report.lists[f"rapports:{sym}"] = len(got)
            raw.extend(got)
    if boc:
        try:
            got = collect_boc_events(boc_dir or DEFAULT_BOC_DIR, since=since_d, last_n=boc_last_n,
                                     resolver=resolver, include_bonds=include_bonds)
        except Exception as exc:  # BOC local illisible : on continue sans
            report.errors.append(f"BOC : {type(exc).__name__}: {exc}")
            got = []
        report.lists["boc"] = len(got)
        raw.extend(got)
    report.n_items = len(raw)

    sigs = _signature_index(frame)
    events = _event_index(frame)
    known_ids = set(frame["note_id"].astype(str)) if "note_id" in frame.columns else set()
    kept_by_id: dict[str, dict[str, Any]] = {}
    kept_sigs: list[tuple[str, str, dt.date | None, dict[str, Any]]] = []
    selected: list[dict[str, Any]] = []
    for it in raw:
        nid = note_id_for(it)
        if nid in kept_by_id:  # même document vu par deux listes : publication la plus tôt
            _merge_publication(kept_by_id[nid], it, now, calendar)
            report.n_duplicates += 1
            continue
        if not include_bonds and it.get("instrument") in ("obligation", "fctc") and not (
                not scope.all_market and it.get("country") in scope.countries):
            report.n_filtered += 1
            continue
        if skip_ancillary and it.get("ancillary"):
            report.n_filtered += 1
            continue
        if (it.get("extra") or {}).get("date_inconnue") and not keep_unresolved:
            # document sans date (ni colonne, ni nom de fichier) : impossible à placer dans le temps.
            report.n_filtered += 1
            report.unresolved.append(f"date inconnue | {it.get('symbol') or '-'} | {it.get('title')}")
            continue
        if not (it.get("symbol") or it.get("country") or it.get("market_level")) and not keep_unresolved:
            # émetteur non reconnu (souvent un émetteur d'obligations ou un actionnaire) :
            # signalé dans le bilan pour compléter la table d'alias, pas de note.
            report.n_filtered += 1
            report.unresolved.append(f"{it.get('doc_date')} | {it.get('issuer') or '-'} | {it.get('title')}")
            continue
        if not scope.matches(it):
            report.n_filtered += 1
            continue
        sym = it.get("symbol") or ""
        sig = content_signature(it.get("title"), sym or None)
        d = _as_date(it.get("doc_date"))
        twin = next((k for s2, g2, d2, k in kept_sigs if sig and s2 == sym and g2 == sig
                     and (d is None or d2 is None or abs((d - d2).days) <= 5)), None)
        if twin is not None:  # même document sous deux titres proches (liste et BOC)
            _merge_publication(twin, it, now, calendar)
            report.n_duplicates += 1
            continue
        if _store_has(store, nid, known_ids) or _is_duplicate(it, sigs) or _is_event_duplicate(it, events):
            report.n_duplicates += 1
            continue
        kept_by_id[nid] = it
        kept_sigs.append((sym, sig, d, it))
        et = dedup_event_type(it)
        if sym and et:
            events.add((sym, et), _event_date(it))
        selected.append(it)

    if download_pdfs and not offline:
        n_pdf = 0
        for it in selected:
            url = it.get("doc_url")
            if not url or not url.lower().endswith(".pdf") or n_pdf >= max_pdfs or sess.stopped:
                continue
            try:
                doc = fetch_document(sess, url)  # cache : <cache de la session>/docs/<sha256>.pdf
            except ResearchError as exc:
                report.errors.append(f"PDF {url} : {exc}")
                if isinstance(exc, (QuotaExceeded, AccessBlocked)):
                    break
                continue
            n_pdf += 0 if doc.get("cached") else 1
            it["extra"]["doc_text"] = (doc.get("text") or "")[:MAX_TEXT_CHARS]
            it["extra"]["ocr_needed"] = doc.get("ocr_needed")
            it["extra"]["n_pages"] = doc.get("n_pages")

    result = ResearchResult()
    history = frame if len(frame) else None
    for it in selected:
        note = item_to_note(it, now=now, calendar=calendar, analyze=analyze, panels=panels, history=history)
        if not dry_run:
            _store_add(store, note, now)
        result.append(note)
    report.n_new = len(result)
    report.n_requests = sess.n_requests
    report.stopped = sess.stopped
    result.report = report
    return result


def fetch_url_note(url: str, store: Any, targets: Iterable[str] | None = None, *,
                   session: PoliteSession | None = None, offline: bool = False, allow_disabled: bool = False,
                   author: str = "analyste", title: str | None = None, now: dt.datetime | None = None,
                   calendar: Any = None, panel_dir: str | Path | None = DEFAULT_PANEL_DIR,
                   panels: Mapping[str, Any] | None = None, analyze: bool = True, delay_s: float = 3.0) -> Any:
    """Crée une note à partir d'une page publique fournie par l'analyste.

    - le robots.txt du site est lu et respecté ; une page interdite lève
      :class:`RobotsDisallowed` (message en français), **sans contournement** ;
    - un HTTP 403/429 lève :class:`AccessBlocked` ; aucune nouvelle tentative ;
    - les sources désactivées par défaut (Sika Finance, Richbourse, presse) lèvent
      :class:`SourceDisabled`, sauf ``allow_disabled=True`` (accord du site) ;
    - page HTML : titre, date de publication (métadonnées) et texte principal ;
      PDF : texte via pdftotext (``ocr_requis`` si scan) ;
    - la note (``source="url"``) est analysée puis ajoutée ; si la même URL est déjà
      au journal avec le même texte, la note existante est renvoyée ; si le texte a
      changé, une nouvelle version est enregistrée (``store.update``).
    """
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError(f"URL invalide : {url!r} (http ou https attendu).")
    why = _disabled_domain(url)
    if why and not allow_disabled:
        raise SourceDisabled(
            f"La source {p.netloc} est désactivée par défaut ({why}). Elle ne sera lue qu'avec l'accord du site "
            "(allow_disabled=True) ; aucune protection anti-robot n'est contournée."
        )
    root = _store_root(store)
    now = to_utc(now or utcnow())
    sess = session or PoliteSession(delay_s=delay_s, max_requests=5, offline=offline, cache_dir=root / "cache",
                                    log_path=root / "fetch_log.jsonl", backoff_s=5.0)
    res = sess.get(url)
    if res.status in STOP_STATUSES:  # pragma: no cover - déjà levé par la session
        raise AccessBlocked(f"{p.netloc} refuse l'accès (HTTP {res.status}).")
    if res.status != 200:
        raise ResearchError(f"La page {url} a répondu HTTP {res.status} : aucune note créée.")
    tags = ["url"]
    is_pdf = res.content.startswith(b"%PDF") or "pdf" in res.content_type
    if is_pdf:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "doc.pdf"
            pdf.write_bytes(res.content)
            info = extract_pdf_text(pdf)
        text = info["text"][:MAX_TEXT_CHARS]
        page_title = title or next((clean_text(x) for x in text.splitlines() if clean_text(x)),
                                   Path(p.path).name)
        file_day = date_from_filename(url)
        published_at = to_utc(file_day) if file_day else None
        precision = "date"
        if info.get("ocr_needed"):
            tags.append("ocr_requis")
    else:
        content = extract_html_content(res.content, url)
        text = content["text"]
        page_title = title or content["title"] or url
        published_at = content["published_at"]
        precision = "datetime"
        if published_at is not None and published_at.time() == dt.time(0, 0):
            precision = "date"  # date sans heure : connue en fin de journée
    effective = (dt.datetime.combine(published_at.date(), dt.time(23, 59, 59), tzinfo=dt.timezone.utc)
                 if published_at is not None and precision == "date" else published_at)
    if published_at is None or effective > now:
        # Sans date fiable (ou date future), l'information est datée de sa collecte.
        published_at, precision = now, "datetime"
        tags.append("date_collecte")
    if not text.strip() and not page_title:
        raise ResearchError(f"La page {url} ne contient aucun texte lisible : aucune note créée.")
    if calendar is None:
        calendar = _sessions_for(panel_dir)
    model_mod = _model_module()
    resolver = default_resolver(panel_dir)
    manual = [str(t) for t in (targets or [])]
    if not manual:
        sym = resolver.resolve(None, page_title)
        if sym:
            manual = [sym]
    try:
        from brvm_alpha.notes.model import make_note_id

        note_id = make_note_id("url", url=normalize_url(url))
    except Exception:
        note_id = hashlib.sha1(("url|" + normalize_url(url) + "|").encode("utf-8")).hexdigest()
    note = _make_note(
        model_mod, note_id=note_id, created_at=now, published_at=published_at, published_precision=precision,
        first_tradable_session=_tradable(published_at, calendar, precision), author=author, source="url", url=url,
        title=page_title, text=text, targets=manual, event_type=None, stance=None, conviction=None,
        tags=tags, status="active", version=1, analysis=None,
    )
    if analyze:
        adict = _analyze(note, panels, None, calendar)
        _set(note, "analysis", adict)
        if adict.get("event_type") and _note_get(note, "event_type") in _GENERIC_TYPES:
            _set(note, "event_type", adict["event_type"])
    existing = None
    try:
        existing = store.get(note_id)
    except Exception:
        existing = None
    if existing is not None:
        if (_note_get(existing, "text") or "") == text:
            return existing
        changes = {k: _note_get(note, k) for k in ("title", "text", "analysis", "event_type", "published_at",
                                                    "first_tradable_session", "tags")}
        try:
            store.update(note_id, now=now, **changes)
        except TypeError:
            store.update(note_id, **changes)
        try:
            return store.get(note_id)
        except Exception:  # pragma: no cover
            return note
    _store_add(store, note, now)
    return note


__all__ = [
    "BASE_URL", "USER_AGENT", "BRVM_LISTS", "ISSUER_SLUGS", "ISSUER_ALIASES", "BRVM30_T4_2026",
    "ResearchError", "RobotsDisallowed", "AccessBlocked", "QuotaExceeded", "ServerUnavailable",
    "OfflineCacheMiss", "SourceDisabled", "FetchResult", "PoliteSession", "IssuerResolver",
    "parse_views_table", "parse_list_page", "parse_issuers_index", "parse_issuer_reports",
    "collect_list", "collect_issuers_index", "collect_issuer_reports", "parse_boc_events",
    "collect_boc_events", "list_boc_files", "extract_pdf_text", "fetch_document", "extract_html_content",
    "TargetScope", "expand_targets", "load_calendar", "first_tradable_session", "item_published_at",
    "note_id_for", "content_signature", "item_to_note", "run_research", "fetch_url_note",
    "ResearchReport", "ResearchResult", "date_from_filename", "parse_date_fr", "parse_parity",
    "default_resolver", "norm_label", "dedup_event_type", "normalize_url", "item_key", "sovereign_country",
    "DISABLED_DOMAINS", "STOP_STATUSES",
]
