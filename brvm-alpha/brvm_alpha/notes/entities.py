"""Liaison d'entités : texte -> symboles, indices, pays, secteurs, thèmes et marché.

La table d'alias est construite :
1. à partir des **libellés réels du panel** (``equities.parquet``, colonne ``name``, toutes
   dates : « SONATEL SN », « BOLLORE TRANSPORT & LOGISTICS », « ERIUM CI (Ex AIR LIQUIDE
   CI) »…), avec leurs variantes sans suffixe pays et avec le nom du pays en toutes lettres ;
2. d'**alias usuels** vérifiés un par un contre ces libellés et contre les documents
   06a/06b (SONATEL -> SNTS, Orange CI -> ORAC, Société Générale CI -> SGBC, Ecobank
   Transnational -> ETIT, TotalEnergies Marketing CI/SN, SIB, Coris, NSIA, BOA + pays…) ;
3. des **indices** (BRVM Composite, BRVM 30, Prestige, Principal, Composite Total Return,
   indices sectoriels base 2025 et base 1999), des **pays** (noms, gentilés, capitales
   usuelles), des **secteurs** (codes BOC) et des **thèmes macro** (document 05).

Règles de liaison : insensible à la casse et aux accents, limites de mots strictes
(« BOA » ne se trouve pas dans « boat », « SIB » pas dans « possible », « Niger » pas
dans « Nigeria »), alias le plus long d'abord (« BOA Mali » -> BOAM, sans lien séparé
vers le Mali). Les mots courants ne sont jamais des alias seuls : « total », « orange »,
« principal », « composite », « marché », « or », « brut »… exigent un qualificatif
(« Total CI », « Orange Côte d'Ivoire », « BRVM Principal », « cours de l'or »…).
« CIE » n'est retenu qu'écrit en capitales (sinon « & Cie »). Les alias ambigus
(« BOA », « Bank of Africa », « TotalEnergies », « Ecobank » seuls) ne sont pas liés : ils
sont rendus dans ``ambiguous``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

import pandas as pd

from brvm_alpha.reference import COUNTRY_NAMES, country_of

from .model import (
    INDEX_TARGETS,
    KNOWN_SYMBOLS,
    THEMES,
    default_panel_dir,
    fold,
    fold_with_map,
    target_kind,
)

# ---------------------------------------------------------------------------
# Données de référence
# ---------------------------------------------------------------------------

#: Libellés du panel réel (``equities.parquet``, toutes dates, relevé du 22/11/2026).
#: Utilisés si le panel est absent ; sinon les libellés sont relus dans le fichier.
PANEL_NAMES_FALLBACK: dict[str, tuple[str, ...]] = {
    "ABJC": ("SERVAIR ABIDJAN CI",),
    "BBGC": ("BRIDGE BANK GROUP CI",),
    "BICB": ("BIIC BN",),
    "BICC": ("BICI CI",),
    "BNBC": ("BERNABE CI",),
    "BOAB": ("BANK OF AFRICA BN",),
    "BOABF": ("BANK OF AFRICA BF",),
    "BOAC": ("BANK OF AFRICA CI",),
    "BOAM": ("BANK OF AFRICA ML",),
    "BOAN": ("BANK OF AFRICA NG",),
    "BOAS": ("BANK OF AFRICA SN", "BANK OF AFRICA SENEGAL"),
    "CABC": ("SICABLE CI",),
    "CBIBF": ("CORIS BANK INTERNATIONAL BF", "CORIS BANK INTERNATIONAL"),
    "CFAC": ("CFAO MOTORS CI",),
    "CIEC": ("CIE CI",),
    "ECOC": ("ECOBANK COTE D'IVOIRE",),
    "ETIT": ("ECOBANK TRANS. INCORP. TG",),
    "FTSC": ("FILTISAC CI",),
    "LNBB": ("LOTERIE NATIONALE DU BENIN",),
    "NEIC": ("NEI-CEDA CI",),
    "NSBC": ("NSIA BANQUE CI", "NSIA BANQUE COTE D'IVOIRE"),
    "NTLC": ("NESTLE CI",),
    "ONTBF": ("ONATEL BF",),
    "ORAC": ("ORANGE COTE D'IVOIRE",),
    "ORGT": ("ORAGROUP TOGO",),
    "PALC": ("PALM CI",),
    "PRSC": ("TRACTAFRIC MOTORS CI",),
    "SAFC": ("SAFCA CI",),
    "SCRC": ("SUCRIVOIRE", "SUCRIVOIRE CI"),
    "SDCC": ("SODE CI",),
    "SDSC": ("BOLLORE TRANSPORT & LOGISTICS", "BOLLORE TRANS. & LOG. CI", "BOLLORE", "AFRICA GLOBAL LOGISTICS CI"),
    "SEMC": ("CROWN SIEM CI", "EVIOSYS PACKAGING SIEM CI", "SONOCO METAL PACKAGING SIEM S.A"),
    "SGBC": ("SGB CI", "SOCIETE GENERALE COTE D'IVOIRE"),
    "SHEC": ("VIVO ENERGY CI",),
    "SIBC": ("SOCIETE IVOIRIENNE DE BANQUE CI", "SOCIETE IVOIRIENNE DE BANQUE"),
    "SICC": ("SICOR CI",),
    "SIVC": ("AIR LIQUIDE CI", "ERIUM CI", "ERIUM CI (Ex AIR LIQUIDE CI)"),
    "SLBC": ("SOLIBRA CI",),
    "SMBC": ("SMB CI",),
    "SNTS": ("SONATEL SN",),
    "SOGC": ("SOGB CI",),
    "SPHC": ("SAPH CI",),
    "STAC": ("SETAO CI",),
    "STBC": ("SITAB CI",),
    "SVOC": ("MOVIS CI",),
    "TTLC": ("TOTAL CI", "TOTALENERGIES MARKETING CI"),
    "TTLS": ("TOTAL SN", "TOTALENERGIES MARKETING SN"),
    "TTRC": ("TRITURAF CI-Ste en Liquidation",),
    "UNLC": ("UNILEVER CI",),
    "UNXC": ("UNIWAX CI",),
}

#: Alias usuels (marques, sigles, anciens noms). Chaque entrée est vérifiée contre les
#: libellés du panel ou contre les documents 06a/06b (test ``verify_aliases``).
COMPANY_ALIASES: dict[str, str] = {
    # Télécoms
    "sonatel": "SNTS", "groupe sonatel": "SNTS", "orange senegal": "SNTS", "orange mali": "SNTS",
    "orange guinee": "SNTS", "orange bissau": "SNTS", "orange sierra leone": "SNTS",
    "orange ci": "ORAC", "orange cote d'ivoire": "ORAC", "orange cote-d'ivoire": "ORAC",
    "onatel": "ONTBF", "onatel burkina faso": "ONTBF", "moov africa burkina": "ONTBF",
    "moov africa burkina faso": "ONTBF", "moov burkina": "ONTBF", "moov burkina faso": "ONTBF",
    # Banques et finance
    "societe generale": "SGBC", "societe generale ci": "SGBC", "societe generale cote d'ivoire": "SGBC",
    "sgci": "SGBC", "sgbci": "SGBC", "sgb ci": "SGBC", "sgbc": "SGBC",
    "sib": "SIBC", "sib ci": "SIBC", "societe ivoirienne de banque": "SIBC",
    "ecobank ci": "ECOC", "ecobank cote d'ivoire": "ECOC",
    "ecobank transnational": "ETIT", "ecobank transnational incorporated": "ETIT",
    "ecobank transnational inc": "ETIT", "ecobank trans incorp": "ETIT", "eti": "ETIT",
    "eti tg": "ETIT", "eti togo": "ETIT", "ecobank tg": "ETIT", "groupe ecobank": "ETIT",
    "bici": "BICC", "bici ci": "BICC", "bicici": "BICC", "bici cote d'ivoire": "BICC",
    "nsia": "NSBC", "nsia banque": "NSBC", "nsia banque ci": "NSBC", "nsia banque cote d'ivoire": "NSBC",
    "bridge bank": "BBGC", "bridge bank group": "BBGC", "bridge bank group cote d'ivoire": "BBGC",
    "safca": "SAFC", "alios finance": "SAFC", "safca alios finance": "SAFC", "alios finance ci": "SAFC",
    "biic": "BICB", "biic benin": "BICB", "biic bn": "BICB",
    "banque internationale pour l'industrie et le commerce": "BICB",
    "coris": "CBIBF", "coris bank": "CBIBF", "coris bank international": "CBIBF", "coris bank bf": "CBIBF",
    "coris bank international burkina faso": "CBIBF",
    "oragroup": "ORGT", "oragroup togo": "ORGT", "oragroup tg": "ORGT", "orabank": "ORGT",
    "boa ci": "BOAC", "boa cote d'ivoire": "BOAC", "bank of africa ci": "BOAC", "bank of africa cote d'ivoire": "BOAC",
    "boa benin": "BOAB", "boa bn": "BOAB", "bank of africa benin": "BOAB", "bank of africa bn": "BOAB",
    "boa burkina": "BOABF", "boa burkina faso": "BOABF", "boa bf": "BOABF", "bank of africa burkina faso": "BOABF",
    "bank of africa bf": "BOABF",
    "boa mali": "BOAM", "boa ml": "BOAM", "bank of africa mali": "BOAM", "bank of africa ml": "BOAM",
    "boa niger": "BOAN", "boa ng": "BOAN", "bank of africa niger": "BOAN", "bank of africa ng": "BOAN",
    "boa senegal": "BOAS", "boa sn": "BOAS", "bank of africa senegal": "BOAS", "bank of africa sn": "BOAS",
    # Énergie et services publics
    "totalenergies marketing ci": "TTLC", "totalenergies marketing cote d'ivoire": "TTLC",
    "totalenergies ci": "TTLC", "totalenergies cote d'ivoire": "TTLC", "total ci": "TTLC",
    "total cote d'ivoire": "TTLC",
    "totalenergies marketing sn": "TTLS", "totalenergies marketing senegal": "TTLS",
    "totalenergies senegal": "TTLS", "totalenergies sn": "TTLS", "total sn": "TTLS",
    "total senegal": "TTLS",
    "vivo energy": "SHEC", "vivo energy ci": "SHEC", "vivo energy cote d'ivoire": "SHEC", "shell ci": "SHEC",
    "smb": "SMBC", "smb ci": "SMBC", "societe multinationale de bitumes": "SMBC",
    "cie": "CIEC", "cie ci": "CIEC", "compagnie ivoirienne d'electricite": "CIEC",
    "sodeci": "SDCC", "sode ci": "SDCC", "societe de distribution d'eau de cote d'ivoire": "SDCC",
    # Consommation, agro-industrie
    "nestle": "NTLC", "nestle ci": "NTLC", "nestle cote d'ivoire": "NTLC",
    "palm ci": "PALC", "palmci": "PALC", "palm cote d'ivoire": "PALC", "saph": "SPHC", "saph ci": "SPHC", "sogb": "SOGC", "sogb ci": "SOGC",
    "sucrivoire": "SCRC", "solibra": "SLBC", "sitab": "STBC", "unilever": "UNLC", "unilever ci": "UNLC",
    "unilever cote d'ivoire": "UNLC", "sicor": "SICC", "servair": "ABJC", "servair abidjan": "ABJC",
    "bernabe": "BNBC", "bernabe ci": "BNBC", "cfao": "CFAC", "cfao motors": "CFAC", "cfao mobility": "CFAC",
    "cfao mobility ci": "CFAC", "cfao mobility cote d'ivoire": "CFAC", "cfao motors ci": "CFAC",
    "loterie nationale du benin": "LNBB", "lnb": "LNBB", "lnb benin": "LNBB",
    "nei-ceda": "NEIC", "nei ceda": "NEIC", "tractafric": "PRSC", "tractafric motors": "PRSC",
    "tractafric motors ci": "PRSC", "uniwax": "UNXC",
    # Industriels
    "sicable": "CABC", "filtisac": "FTSC",
    "agl": "SDSC", "agl ci": "SDSC", "africa global logistics": "SDSC", "africa global logistics ci": "SDSC",
    "africa global logistics cote d'ivoire": "SDSC", "bollore": "SDSC", "bollore transport & logistics": "SDSC",
    "bollore transport et logistique": "SDSC",
    "siem": "SEMC", "crown siem": "SEMC", "eviosys": "SEMC", "eviosys packaging siem": "SEMC",
    "sonoco metal packaging siem": "SEMC", "sonoco": "SEMC",
    "erium": "SIVC", "erium ci": "SIVC", "air liquide ci": "SIVC", "air liquide cote d'ivoire": "SIVC",
    "air liquide": "SIVC", "setao": "STAC", "setao ci": "STAC",
    # Historiques
    "movis": "SVOC", "movis ci": "SVOC", "trituraf": "TTRC",
}

#: Alias dont la source n'est pas un libellé du panel (marques, anciens noms) : justification.
ALIAS_EVIDENCE: dict[str, str] = {
    "orange senegal": "marque commerciale de Sonatel au Sénégal (doc 06b, SNTS)",
    "orange mali": "filiale de Sonatel (doc 05 §8.1, doc 06b SNTS)",
    "orange guinee": "filiale de Sonatel (doc 05 §10.1)",
    "orange bissau": "filiale de Sonatel (doc 05 §8.4)",
    "orange sierra leone": "filiale de Sonatel (doc 06b SNTS)",
    "moov africa burkina": "nouveau nom commercial d'Onatel (doc 06b ONTBF ; communiqué « MOOV BURKINA FASO (ex ONATEL BF) »)",
    "cfao mobility": "nouveau nom de CFAO Motors CI (doc 06b CFAC)",
    "africa global logistics": "ex-Bolloré Transport & Logistics CI (libellé panel « AFRICA GLOBAL LOGISTICS CI »)",
    "agl": "sigle d'Africa Global Logistics (liste des avis brvm.org : « AGL CI »)",
    "sodeci": "société de distribution d'eau (doc 06b SDCC ; libellé panel « SODE CI »)",
    "sgci": "ancien libellé brvm.org de SGBC (doc 07 §1.2)",
    "bicici": "ancien nom de BICI CI (doc 06a BICC)",
    "alios finance": "dénomination de SAFCA (doc 06a SAFC ; avis « ALIOS FINANCE (SAFCA CI) »)",
    "orabank": "réseau bancaire d'Oragroup (doc 06a ORGT)",
    "sonoco": "ex-Eviosys, ex-Crown SIEM (libellé panel « SONOCO METAL PACKAGING SIEM »)",
    "vivo energy": "libellé panel « VIVO ENERGY CI » ; ex-Shell CI (symbole SHEC)",
    "shell ci": "ancien nom de Vivo Energy CI (symbole SHEC)",
    "smb": "Société Multinationale de Bitumes (libellé panel « SMB CI »)",
    "cie": "Compagnie Ivoirienne d'Électricité (libellé panel « CIE CI »)",
    "compagnie ivoirienne d'electricite": "raison sociale de la CIE (doc 06b CIEC)",
    "societe multinationale de bitumes": "raison sociale de SMB (doc 06b SMBC)",
    "societe de distribution d'eau de cote d'ivoire": "raison sociale de la SODECI (doc 06b SDCC)",
    "banque internationale pour l'industrie et le commerce": "raison sociale de la BIIC (doc 06a §5.10)",
    "bollore transport et logistique": "forme française de « BOLLORE TRANSPORT & LOGISTICS » (libellé panel)",
    "moov burkina": "communiqué brvm.org « MOOV BURKINA FASO (ex ONATEL BF) » (doc 07 §1.2)",
    "moov burkina faso": "communiqué brvm.org « MOOV BURKINA FASO (ex ONATEL BF) »",
    "moov africa burkina faso": "nouveau nom commercial d'Onatel (doc 06b ONTBF)",
    "cfao mobility ci": "nouveau nom de CFAO Motors CI (doc 06b CFAC)",
    "cfao mobility cote d'ivoire": "nouveau nom de CFAO Motors CI (doc 06b CFAC)",
    "safca alios finance": "libellé brvm.org « SAFCA ALIOS FINANCE » (annexes-07, names.py)",
    "alios finance ci": "dénomination de SAFCA (doc 06a SAFC)",
}

#: Formes qui désignent plusieurs titres ou une entité non cotée : jamais liées.
AMBIGUOUS_ALIASES: dict[str, str] = {
    "boa": "BOA sans pays : six filiales cotées (BOAB, BOABF, BOAC, BOAM, BOAN, BOAS)",
    "bank of africa": "Bank of Africa sans pays : six filiales cotées",
    "groupe boa": "groupe BOA (non coté à la BRVM)",
    "boa west africa": "actionnaire des filiales BOA (non coté)",
    "totalenergies": "TotalEnergies sans pays : TTLC ou TTLS",
    "totalenergies marketing": "TotalEnergies Marketing sans pays : TTLC ou TTLS",
    "ecobank": "Ecobank sans précision : ETIT (holding) ou ECOC (filiale ivoirienne)",
    "coris bank international cote d'ivoire": "filiale ivoirienne de Coris, non cotée en actions au 20/11/2026",
    "coris bank cote d'ivoire": "filiale ivoirienne de Coris, non cotée en actions au 20/11/2026",
    "coris bank ci": "filiale ivoirienne de Coris, non cotée en actions au 20/11/2026",
    "orange money": "service de mobile money (voir le thème MOBILE_MONEY)",
    "moov africa cote d'ivoire": "Moov Africa CI, non coté",
    "air liquide international": "actionnaire d'Erium CI (franchissement de seuil) : non coté",
    "nsia participations": "actionnaire de NSIA Banque CI : non coté",
    "nsia holding financiere": "actionnaire de NSIA Banque CI : non coté",
    "securite sociale": "protection sociale (pas le thème sécurité)",
    "total des": "« total » au sens comptable",
    "election des administrateurs": "gouvernance d'entreprise (pas une élection politique)",
    "election d'un administrateur": "gouvernance d'entreprise (pas une élection politique)",
    "election du president du conseil d'administration": "gouvernance d'entreprise",
    "au total": "« total » au sens comptable",
}

#: Mots courants : jamais retenus comme alias dérivés d'un libellé du panel.
COMMON_WORDS = frozenset({
    "total", "orange", "palm", "bollore trans", "bank", "africa", "group", "groupe", "banque",
    "societe", "generale", "principal", "prestige", "composite", "energie", "marche", "or",
})

#: Alias retenus seulement s'ils sont écrits en capitales dans le texte d'origine.
UPPERCASE_ONLY = frozenset({"cie"})

_COUNTRY_SUFFIXES: dict[str, tuple[str, ...]] = {
    "CI": ("ci", "cote d'ivoire", "rci"),
    "SN": ("sn", "senegal"),
    "BJ": ("bn", "benin"),
    "BF": ("bf", "burkina faso", "burkina"),
    "ML": ("ml", "mali"),
    "NE": ("ng", "niger"),
    "TG": ("tg", "togo"),
    "GW": ("gw", "guinee-bissau"),
}

COUNTRY_ALIASES: dict[str, str] = {
    # Côte d'Ivoire
    "cote d'ivoire": "CI", "cote-d'ivoire": "CI", "rci": "CI", "republique de cote d'ivoire": "CI",
    "ivoirien": "CI", "ivoirienne": "CI", "ivoiriens": "CI", "ivoiriennes": "CI", "abidjan": "CI",
    "yamoussoukro": "CI", "san pedro": "CI", "san-pedro": "CI", "tpci": "CI",
    "etat de cote d'ivoire": "CI", "tresor public de cote d'ivoire": "CI",
    # Sénégal
    "senegal": "SN", "senegalais": "SN", "senegalaise": "SN", "senegalaises": "SN", "dakar": "SN",
    "etat du senegal": "SN",
    # Bénin
    "benin": "BJ", "beninois": "BJ", "beninoise": "BJ", "beninoises": "BJ", "cotonou": "BJ",
    "porto-novo": "BJ", "etat du benin": "BJ",
    # Burkina Faso
    "burkina faso": "BF", "burkina": "BF", "burkinabe": "BF", "burkinabes": "BF", "ouagadougou": "BF",
    "ouaga": "BF", "bobo-dioulasso": "BF", "tpbf": "BF", "etat du burkina": "BF", "etat du burkina faso": "BF",
    # Mali
    "mali": "ML", "malien": "ML", "malienne": "ML", "maliens": "ML", "maliennes": "ML", "bamako": "ML",
    "etat du mali": "ML",
    # Niger
    "niger": "NE", "nigerien": "NE", "nigerienne": "NE", "nigeriens": "NE", "nigeriennes": "NE",
    "niamey": "NE", "etat du niger": "NE",
    # Togo
    "togo": "TG", "togolais": "TG", "togolaise": "TG", "togolaises": "TG", "lome": "TG", "etat du togo": "TG",
    # Guinée-Bissau
    "guinee-bissau": "GW", "guinee bissau": "GW", "bissau-guineen": "GW", "bissau-guineenne": "GW",
    "bissau-guineens": "GW", "bissau": "GW",
}

#: Indices (texte libre) : les mots seuls « composite », « prestige », « principal » sont exclus.
INDEX_ALIASES: dict[str, str] = {
    "brvm composite": "IDX:BRVM-C", "brvm-c": "IDX:BRVM-C", "brvmc": "IDX:BRVM-C",
    "indice composite": "IDX:BRVM-C", "indice brvm composite": "IDX:BRVM-C", "le composite": "IDX:BRVM-C",
    "brvm composite total return": "IDX:BRVM-C-TR", "composite total return": "IDX:BRVM-C-TR",
    "brvm - composite total return": "IDX:BRVM-C-TR", "indice total return": "IDX:BRVM-C-TR",
    "brvm-c-tr": "IDX:BRVM-C-TR", "brvm-c tr": "IDX:BRVM-C-TR",
    "brvm 30": "IDX:BRVM-30", "brvm30": "IDX:BRVM-30", "indice brvm 30": "IDX:BRVM-30",
    "brvm 10": "IDX:BRVM-10", "brvm10": "IDX:BRVM-10", "indice brvm 10": "IDX:BRVM-10",
    "brvm prestige": "IDX:PRESTIGE", "indice prestige": "IDX:PRESTIGE", "compartiment prestige": "IDX:PRESTIGE",
    "indice brvm prestige": "IDX:PRESTIGE",
    "brvm principal": "IDX:PRINCIPAL", "indice principal": "IDX:PRINCIPAL",
    "compartiment principal": "IDX:PRINCIPAL", "indice brvm principal": "IDX:PRINCIPAL",
}

#: Mots désignant chaque secteur (pour les indices sectoriels et ``SECT:``).
_SECTOR_FORMS: dict[str, tuple[str, ...]] = {
    "FIN": ("services financiers", "finances", "finance"),
    "TEL": ("telecommunications", "telecoms", "telecom"),
    "CB": ("consommation de base",),
    "CD": ("consommation discretionnaire",),
    "ENE": ("energie",),
    "IND": ("industriels", "industrie"),
    "SPU": ("services publics",),
    "AGR": ("agriculture",),
    "DIS": ("distribution",),
    "TRP": ("transport", "transports"),
    "AUT": ("autres secteurs",),
}

SECTOR_ALIASES: dict[str, str] = {
    "secteur bancaire": "FIN", "secteur financier": "FIN", "valeurs bancaires": "FIN",
    "valeurs financieres": "FIN", "titres bancaires": "FIN", "banques": "FIN", "les banques": "FIN",
    "etablissements de credit": "FIN",
    "secteur des telecommunications": "TEL", "secteur des telecoms": "TEL", "secteur telecoms": "TEL",
    "telecoms": "TEL", "operateurs telecoms": "TEL", "operateurs de telephonie": "TEL",
    "operateurs de telecommunications": "TEL", "valeurs telecoms": "TEL",
    "agro-industrie": "CB", "agro-industriels": "CB", "agro-industrielles": "CB",
    "secteur agro-industriel": "CB", "valeurs agricoles": "CB",
    "secteur energetique": "ENE", "valeurs energetiques": "ENE", "distribution petroliere": "ENE",
    "distributeurs de produits petroliers": "ENE", "petrolieres cotees": "ENE",
    "secteur industriel": "IND", "valeurs industrielles": "IND",
    "secteur agricole": "AGR",
}
for _code, _forms in _SECTOR_FORMS.items():
    for _f in _forms:
        SECTOR_ALIASES.setdefault(f"secteur {_f}", _code)
        SECTOR_ALIASES.setdefault(f"secteur des {_f}", _code)
        SECTOR_ALIASES.setdefault(f"secteur de la {_f}", _code)
        SECTOR_ALIASES.setdefault(f"secteur de l'{_f}", _code)
        SECTOR_ALIASES.setdefault(f"valeurs {_f}", _code)

#: Thèmes macro, politiques et matières premières (document 05).
THEME_ALIASES: dict[str, str] = {
    # Politique monétaire
    "bceao": "TAUX_BCEAO", "banque centrale": "TAUX_BCEAO", "taux directeur": "TAUX_BCEAO",
    "taux directeurs": "TAUX_BCEAO", "politique monetaire": "TAUX_BCEAO",
    "comite de politique monetaire": "TAUX_BCEAO", "taux minimum de soumission": "TAUX_BCEAO",
    "guichet de pret marginal": "TAUX_BCEAO", "assouplissement monetaire": "TAUX_BCEAO",
    "resserrement monetaire": "TAUX_BCEAO", "taux d'interet directeur": "TAUX_BCEAO",
    "taux bceao": "TAUX_BCEAO", "taux de la bceao": "TAUX_BCEAO",
    # Inflation, croissance
    "inflation": "INFLATION", "desinflation": "INFLATION", "ihpc": "INFLATION",
    "indice des prix a la consommation": "INFLATION", "indice harmonise des prix a la consommation": "INFLATION",
    "hausse des prix a la consommation": "INFLATION",
    "croissance economique": "CROISSANCE", "pib": "CROISSANCE", "produit interieur brut": "CROISSANCE",
    "recession": "CROISSANCE", "croissance du pib": "CROISSANCE",
    # Finances publiques
    "dette publique": "DETTE_PUBLIQUE", "endettement public": "DETTE_PUBLIQUE",
    "finances publiques": "DETTE_PUBLIQUE", "deficit budgetaire": "DETTE_PUBLIQUE",
    "cour des comptes": "DETTE_PUBLIQUE", "fmi": "DETTE_PUBLIQUE", "fonds monetaire international": "DETTE_PUBLIQUE",
    "audit des finances publiques": "DETTE_PUBLIQUE", "dette cachee": "DETTE_PUBLIQUE",
    "eurobond": "EUROBOND", "eurobonds": "EUROBOND", "euro-obligation": "EUROBOND", "euro-obligations": "EUROBOND",
    "emprunt obligataire d'etat": "OBLIGATIONS_ETAT", "emprunts d'etat": "OBLIGATIONS_ETAT",
    "emprunt d'etat": "OBLIGATIONS_ETAT", "umoa-titres": "OBLIGATIONS_ETAT", "umoa titres": "OBLIGATIONS_ETAT",
    "bons du tresor": "OBLIGATIONS_ETAT", "obligations du tresor": "OBLIGATIONS_ETAT",
    "obligations assimilables du tresor": "OBLIGATIONS_ETAT", "appel public a l'epargne": "OBLIGATIONS_ETAT",
    "taux de reference des emprunts d'etat": "OBLIGATIONS_ETAT",
    "notation souveraine": "NOTATION_SOUVERAINE", "note souveraine": "NOTATION_SOUVERAINE",
    "notations souveraines": "NOTATION_SOUVERAINE", "moody's": "NOTATION_SOUVERAINE",
    "moodys": "NOTATION_SOUVERAINE", "fitch": "NOTATION_SOUVERAINE", "fitch ratings": "NOTATION_SOUVERAINE",
    "standard & poor's": "NOTATION_SOUVERAINE", "standard and poor's": "NOTATION_SOUVERAINE",
    "franc cfa": "MONNAIE", "parite fixe": "MONNAIE", "parite avec l'euro": "MONNAIE", "monnaie eco": "MONNAIE",
    "projet eco": "MONNAIE", "monnaie unique": "MONNAIE", "zone franc": "MONNAIE", "devaluation": "MONNAIE",
    "monnaie de l'aes": "MONNAIE",
    # Politique
    "election": "ELECTIONS", "elections": "ELECTIONS", "presidentielle": "ELECTIONS",
    "presidentielles": "ELECTIONS", "election presidentielle": "ELECTIONS", "legislatives": "ELECTIONS",
    "scrutin": "ELECTIONS", "referendum": "ELECTIONS", "campagne electorale": "ELECTIONS",
    "coup d'etat": "COUP_ETAT", "coups d'etat": "COUP_ETAT", "putsch": "COUP_ETAT", "junte": "COUP_ETAT",
    "transition militaire": "COUP_ETAT", "tentative de coup d'etat": "COUP_ETAT",
    "sanctions de la cedeao": "SANCTIONS", "sanctions cedeao": "SANCTIONS", "sanctions de l'uemoa": "SANCTIONS",
    "sanctions economiques": "SANCTIONS", "sanctions financieres": "SANCTIONS", "embargo": "SANCTIONS",
    "gel des avoirs": "SANCTIONS", "cedeao": "SANCTIONS", "ecowas": "SANCTIONS",
    "aes": "AES", "alliance des etats du sahel": "AES", "confederation des etats du sahel": "AES",
    "confederation aes": "AES", "liptako-gourma": "AES",
    # Sécurité
    "securite": "SECURITE", "securitaire": "SECURITE", "insecurite": "SECURITE", "crise securitaire": "SECURITE",
    "situation securitaire": "SECURITE", "terrorisme": "SECURITE", "terroriste": "SECURITE",
    "terroristes": "SECURITE", "jihadiste": "SECURITE", "jihadistes": "SECURITE", "djihadiste": "SECURITE",
    "djihadistes": "SECURITE", "groupes armes": "SECURITE", "attaque terroriste": "SECURITE",
    # Fiscalité, mobile money
    "fiscalite": "FISCALITE", "nouvelle taxe": "FISCALITE", "nouvelles taxes": "FISCALITE",
    "loi de finances": "FISCALITE", "pression fiscale": "FISCALITE", "redressement fiscal": "FISCALITE",
    "controle fiscal": "FISCALITE", "irvm": "FISCALITE", "taxe sur la monnaie electronique": "MOBILE_MONEY",
    "mobile money": "MOBILE_MONEY", "monnaie electronique": "MOBILE_MONEY", "wave": "MOBILE_MONEY",
    "moov money": "MOBILE_MONEY", "paiement mobile": "MOBILE_MONEY", "transfert d'argent": "MOBILE_MONEY",
    # Matières premières
    "cacao": "CACAO", "cacaoyere": "CACAO", "conseil cafe-cacao": "CACAO", "cafe-cacao": "CACAO",
    "feves de cacao": "CACAO", "campagne cacaoyere": "CACAO", "broyage": "CACAO",
    "cafe": "CAFE",
    "caoutchouc": "CAOUTCHOUC", "caoutchouc naturel": "CAOUTCHOUC", "hevea": "CAOUTCHOUC",
    "heveaculture": "CAOUTCHOUC", "tsr20": "CAOUTCHOUC", "tsr 20": "CAOUTCHOUC", "sicom": "CAOUTCHOUC",
    "huile de palme": "HUILE_PALME", "palmiste": "HUILE_PALME", "palmier a huile": "HUILE_PALME",
    "regimes de palme": "HUILE_PALME", "huile brute de palme": "HUILE_PALME", "palmeraies": "HUILE_PALME",
    "sucre": "SUCRE", "canne a sucre": "SUCRE",
    "cajou": "CAJOU", "noix de cajou": "CAJOU", "anacarde": "CAJOU", "anacardes": "CAJOU",
    "coton": "COTON", "filiere coton": "COTON", "coton-graine": "COTON",
    "cours de l'or": "OR", "prix de l'or": "OR", "mines d'or": "OR", "orpaillage": "OR", "aurifere": "OR",
    "auriferes": "OR", "production d'or": "OR", "exportations d'or": "OR",
    "petrole": "PETROLE", "petrolier": "PETROLE", "petroliers": "PETROLE", "petroliere": "PETROLE",
    "petrolieres": "PETROLE", "baril": "PETROLE", "brent": "PETROLE", "hydrocarbures": "PETROLE",
    "prix a la pompe": "PETROLE", "carburant": "PETROLE", "carburants": "PETROLE",
    "produits petroliers": "PETROLE", "sangomar": "PETROLE", "gazole": "PETROLE", "gasoil": "PETROLE",
    "raffinage": "PETROLE", "petrole brut": "PETROLE",
    "gaz naturel": "GAZ", "gnl": "GAZ", "grand tortue": "GAZ", "grande tortue": "GAZ", "gisement de gaz": "GAZ",
    "delestage": "ENERGIE", "delestages": "ENERGIE", "coupures d'electricite": "ENERGIE",
    "coupure d'electricite": "ENERGIE", "crise energetique": "ENERGIE", "penurie d'electricite": "ENERGIE",
    "tarif de l'electricite": "ENERGIE", "electricite": "ENERGIE",
    "pluviometrie": "CLIMAT", "secheresse": "CLIMAT", "inondations": "CLIMAT", "aleas climatiques": "CLIMAT",
    "port autonome": "LOGISTIQUE", "congestion portuaire": "LOGISTIQUE", "trafic portuaire": "LOGISTIQUE",
    "port de san pedro": "LOGISTIQUE", "port d'abidjan": "LOGISTIQUE", "port de san-pedro": "LOGISTIQUE",
}

#: Propagation d'un thème vers les titres exposés (documents 05 §10.1 et 06b §7.5).
#: ``sign`` = sens de l'effet d'une **hausse du facteur** (prix, coût, risque, contrainte)
#: sur le titre : +1, −1, ou 0 quand l'effet est ambigu (marges encadrées, effets de
#: stock). Les magnitudes ne sont pas estimées (régression à faire) : la propagation sert
#: à savoir **quels** titres regarder, pas à fixer un poids.
THEME_EXPOSURES: dict[str, tuple[tuple[str, int, str, str], ...]] = {
    "CAOUTCHOUC": (
        ("SPHC", 1, "prix de vente du caoutchouc (TSR20) ; marge = écart avec le prix d'achat aux planteurs", "doc 06b §7.5"),
        ("SOGC", 1, "prix de vente du caoutchouc", "doc 06b §7.5"),
    ),
    "HUILE_PALME": (
        ("PALC", 0, "+ prix de vente de l'huile, − coût des régimes achetés aux planteurs", "doc 06b §7.5"),
        ("SOGC", 1, "activité palmier", "doc 06b §7.5"),
    ),
    "SUCRE": (("SCRC", 0, "prix de vente plafonnés par l'État", "doc 05 §10.1"),),
    "CACAO": (
        ("FTSC", 1, "campagne cacao : demande de sacs", "doc 06b §7.5"),
        ("SDSC", 1, "campagne cacao : volumes portuaires et logistiques", "doc 06b §7.5"),
        ("NTLC", 0, "intrants cacao et café (coût) ; exposition indirecte", "doc 05 §10.1"),
    ),
    "CAJOU": (
        ("FTSC", 1, "campagne cajou : demande de sacs", "doc 06b §7.5"),
        ("SDSC", 1, "campagne cajou : volumes portuaires", "doc 06b §7.5"),
    ),
    "PETROLE": (
        ("SMBC", 1, "marge de raffinage et prix du brut (bitumes)", "doc 06b §7.5"),
        ("TTLC", 0, "prix à la pompe administrés et effets de stock", "doc 06b §7.5"),
        ("TTLS", 0, "prix à la pompe administrés et effets de stock", "doc 06b §7.5"),
        ("SHEC", 0, "prix à la pompe administrés et effets de stock", "doc 06b §7.5"),
    ),
    "ENERGIE": (
        ("SNTS", -1, "coût de l'énergie et coupures d'électricité", "doc 05 §10.1"),
        ("ORAC", -1, "coût de l'énergie et coupures d'électricité", "doc 05 §10.1"),
        ("ONTBF", -1, "coût de l'énergie et coupures d'électricité", "doc 05 §10.1"),
        ("SCRC", -1, "gazole et réseau : coûts énergétiques (+22 % au S1 2026)", "doc 05 §10.1"),
    ),
    "GAZ": (("CIEC", 0, "concession à tarifs régulés ; parc thermique au gaz", "doc 05 §10.1"),),
    "OR": (
        ("BOAM", 1, "recettes publiques et liquidité bancaire au Mali", "doc 05 §10.1"),
        ("BOABF", 1, "recettes publiques et liquidité bancaire au Burkina Faso", "doc 05 §10.1"),
        ("CBIBF", 1, "recettes publiques et liquidité bancaire au Burkina Faso", "doc 05 §10.1"),
        ("ONTBF", 1, "économie du Burkina Faso", "doc 05 §10.1"),
    ),
    "COTON": (("UNXC", 0, "textiles wax en aval ; exposition indirecte", "doc 05 §10.1"),),
    "MOBILE_MONEY": (
        ("SNTS", -1, "réglementation ou taxation du mobile money (Orange Money)", "doc 06b §7.5 ; doc 05 §8.3"),
        ("ORAC", -1, "réglementation ou taxation du mobile money (Orange Money)", "doc 06b §7.5"),
        ("ONTBF", -1, "réglementation ou taxation du mobile money (Moov Money)", "doc 06b §7.5"),
    ),
    "SECURITE": (
        ("ONTBF", -1, "risque sécuritaire au Sahel", "doc 06b §7.5"),
        ("ORAC", -1, "risque sécuritaire via la filiale du Burkina Faso", "doc 06b §7.5"),
        ("SNTS", -1, "risque sécuritaire via Orange Mali", "doc 06b §7.5"),
    ),
    "LOGISTIQUE": (
        ("SPHC", -1, "congestion portuaire (San-Pedro, Abidjan)", "doc 06b §7.5"),
        ("CABC", -1, "congestion portuaire (San-Pedro, Abidjan)", "doc 06b §7.5"),
    ),
    "TAUX_BCEAO": (
        ("SECT:FIN", -1, "hausse des taux directeurs : coût de refinancement des banques ; effet différé, "
                         "lire le cycle sur 12 mois plutôt que le jour de la décision", "doc 05 §2.3"),
    ),
}


def theme_exposure(code: str) -> list[dict[str, Any]]:
    """Titres (ou secteurs) exposés à un thème : ``[{target, sign, channel, source}]``.

    ``code`` : ``THEME:CACAO`` ou ``CACAO``. Liste vide si le thème n'a pas d'exposition
    documentée (inflation, élections…) : la propagation passe alors par le pays ou le marché.
    """
    key = str(code or "").upper()
    key = key[6:] if key.startswith("THEME:") else key
    return [
        {"target": t, "sign": sg, "channel": ch, "source": src}
        for t, sg, ch, src in THEME_EXPOSURES.get(key, ())
    ]


#: Marché dans son ensemble (« marché » seul est exclu : trop générique).
MARKET_ALIASES: tuple[str, ...] = (
    "brvm", "la brvm", "marche boursier", "marche boursier regional", "marche financier regional",
    "marche financier", "marche des actions", "marche actions", "bourse regionale",
    "bourse regionale des valeurs mobilieres", "la bourse", "ensemble de la cote", "l'ensemble de la cote",
    "l'ensemble du marche", "marche brvm",
)

# ---------------------------------------------------------------------------
# Table d'alias
# ---------------------------------------------------------------------------

_SEP = r"[\s\-'.&/()]{0,5}"


def alias_key(text: str) -> str:
    """Clé d'un alias : caractères alphanumériques normalisés (séparateurs supprimés)."""
    return re.sub(r"[^a-z0-9]+", "", fold(text))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))


@dataclass(frozen=True)
class Alias:
    """Un alias : forme normalisée, code cible (``None`` = forme ambiguë), nature, origine."""

    text: str
    code: str | None
    kind: str
    origin: str  # panel | usuel | pays | indice | secteur | theme | marche | ambigu
    upper_only: bool = False
    note: str = ""


@dataclass
class AliasTable:
    """Table d'alias compilée en une expression régulière (alias le plus long d'abord)."""

    aliases: dict[str, Alias]  # clé = alias_key
    collisions: dict[str, set[str]] = field(default_factory=dict)
    regex: re.Pattern | None = None
    #: découpages en mots rencontrés pour chaque clé (« brvm 30 » et « brvm30 »).
    variants: dict[str, set[tuple[str, ...]]] = field(default_factory=dict)

    def compile(self) -> "AliasTable":
        pats = []
        for key, al in sorted(self.aliases.items(), key=lambda kv: (-len(kv[0]), kv[0])):
            forms = set(self.variants.get(key, set()))
            forms.add(tuple(_tokens(al.text)))
            for toks in sorted(forms, key=lambda t: (-len(t), t)):
                if toks:
                    pats.append(_SEP.join(re.escape(t) for t in toks))
        body = "|".join(pats) if pats else r"(?!x)x"
        self.regex = re.compile(r"(?<![a-z0-9])(?:" + body + r")(?![a-z0-9])")
        return self

    def lookup(self, text: str) -> Alias | None:
        """Alias exact (après normalisation)."""
        return self.aliases.get(alias_key(text))


def _strip_country_suffix(name: str) -> list[str]:
    """Variantes d'un libellé : sans parenthèses, sans suffixe pays, avec pays en toutes lettres."""
    out: list[str] = []
    n = fold(name)
    n = re.sub(r"\(\*+.*$", "", n)  # « (*** »
    ex = re.findall(r"\(ex[\s\-]+([^)]*)\)?", n)
    n = re.sub(r"\(.*?\)?$", "", n).strip()
    n = re.sub(r"-?\s*ste en liquidation$", "", n).strip()
    n = re.sub(r"\s+s\.?\s*a\.?$", "", n).strip()
    n = re.sub(r"\s+s\.$", "", n).strip()
    out.append(n)
    for e in ex:
        out.append(e.strip())
    variants = []
    for v in out:
        variants.append(v)
        toks = v.split()
        if len(toks) >= 2 and toks[-1] in ("ci", "sn", "bf", "bn", "ml", "ng", "tg", "c"):
            variants.append(" ".join(toks[:-1]))
        for full in ("cote d'ivoire", "senegal", "togo", "benin", "mali", "niger", "burkina faso"):
            if v.endswith(" " + full):
                variants.append(v[: -len(full) - 1].strip())
    return [re.sub(r"\s+", " ", v).strip(" -.&") for v in variants if v.strip(" -.&")]


def panel_names(panel_dir: str | Path | None = None) -> dict[str, tuple[str, ...]]:
    """Libellés distincts par symbole lus dans ``equities.parquet`` (repli : liste intégrée)."""
    path = Path(panel_dir) / "equities.parquet" if panel_dir else default_panel_dir() / "equities.parquet"
    if not path.exists():
        return dict(PANEL_NAMES_FALLBACK)
    try:
        df = pd.read_parquet(path, columns=["symbol", "name"])
    except Exception:  # pragma: no cover - fichier illisible
        return dict(PANEL_NAMES_FALLBACK)
    df = df.dropna()
    out: dict[str, tuple[str, ...]] = {}
    for sym, g in df.groupby("symbol"):
        out[str(sym)] = tuple(dict.fromkeys(str(x).strip() for x in g["name"] if str(x).strip()))
    return out


def build_alias_table(
    panel_dir: str | Path | None = None,
    extra_aliases: dict[str, str] | None = None,
) -> AliasTable:
    """Construit la table d'alias (libellés du panel + alias usuels + pays, indices, thèmes…)."""
    names = panel_names(panel_dir)
    entries: dict[str, Alias] = {}
    collisions: dict[str, set[str]] = {}
    variants: dict[str, set[tuple[str, ...]]] = {}

    def add(text: str, code: str | None, kind: str, origin: str, note: str = "", force: bool = False) -> None:
        """Ajoute un alias ; ``force`` écrase l'existant (alias explicites)."""
        key = alias_key(text)
        if len(key) < 2:
            return
        variants.setdefault(key, set()).add(tuple(_tokens(text)))
        upper = fold(text).strip() in UPPERCASE_ONLY
        cur = entries.get(key)
        if cur is not None and not force:
            if cur.code == code:
                return
            if cur.origin == "panel" and origin == "panel":
                # Deux libellés du panel donnent la même forme : forme ambiguë.
                syms = collisions.setdefault(key, set())
                syms.update({str(cur.code), str(code)})
                entries[key] = Alias(fold(text), None, kind, "ambigu", note="libellé partagé : " + ", ".join(sorted(syms)))
            return  # une entrée explicite existe déjà : elle prime
        entries[key] = Alias(fold(text), code, kind, origin, upper_only=upper, note=note)

    # 1) Libellés du panel et variantes.
    derived: dict[str, set[str]] = {}
    for sym, labels in names.items():
        for lab in labels:
            for v in _strip_country_suffix(lab):
                if v in COMMON_WORDS or len(alias_key(v)) < 3:
                    continue
                derived.setdefault(v, set()).add(sym)
    for text, syms in derived.items():
        if len(syms) == 1:
            sym = next(iter(syms))
            add(text, sym, "symbol", "panel")
            # Variantes avec le pays du titre (« SONATEL SN », « NSIA BANQUE CÔTE D'IVOIRE »).
            for suf in _COUNTRY_SUFFIXES.get(country_of(sym), ()):
                if not text.endswith(" " + suf):
                    add(f"{text} {suf}", sym, "symbol", "panel")
        else:
            collisions.setdefault(alias_key(text), set()).update(syms)
            add(text, None, "symbol", "ambigu", note="libellé partagé : " + ", ".join(sorted(syms)), force=True)

    # 2) Alias usuels (prioritaires sur la dérivation automatique).
    usual = dict(COMPANY_ALIASES)
    for text, sym in COMPANY_ALIASES.items():
        if "totalenergies" in text:
            usual.setdefault(text.replace("totalenergies", "total energies"), sym)
    usual.update(extra_aliases or {})
    for text, sym in usual.items():
        if sym not in KNOWN_SYMBOLS and target_kind(sym) == "symbol":
            raise ValueError(f"alias {text!r} -> symbole inconnu {sym!r}")
        kind = target_kind(sym)
        add(text, sym, kind, "usuel", note=ALIAS_EVIDENCE.get(text, ""), force=True)
        if kind == "symbol":
            for suf in _COUNTRY_SUFFIXES.get(country_of(sym), ()):
                if not text.endswith(" " + suf) and alias_key(f"{text} {suf}") not in entries:
                    add(f"{text} {suf}", sym, "symbol", "usuel")
    # Symboles eux-mêmes (« SNTS », « (symbole: SDSC) »).
    for sym in KNOWN_SYMBOLS:
        add(sym.lower(), sym, "symbol", "usuel", force=True)
    for text, why in AMBIGUOUS_ALIASES.items():
        add(text, None, "ambigu", "ambigu", note=why, force=True)

    # 3) Indices.
    for text, code in INDEX_ALIASES.items():
        add(text, code, "index", "indice", force=True)
    for code, (label, idx_names) in INDEX_TARGETS.items():
        for n in (label,) + idx_names:
            if alias_key(n) not in ("brvm",):
                add(n, code, "index", "indice", force=True)
    for sec, forms in _SECTOR_FORMS.items():
        for f in forms:
            for pat in (
                f"brvm {f}", f"brvm - {f}", f"indice {f}", f"indice sectoriel {f}", f"indice sectoriel des {f}",
                f"indice des {f}", f"indice de la {f}", f"indice de l'{f}", f"indice brvm {f}",
                f"indice sectoriel de la {f}", f"indice sectoriel de l'{f}",
            ):
                add(pat, f"IDX:SECT:{sec}", "index", "indice", force=True)

    # 4) Pays, secteurs, thèmes, marché.
    for text, cc in COUNTRY_ALIASES.items():
        add(text, f"PAYS:{cc}", "country", "pays", force=True)
    for cc, name in COUNTRY_NAMES.items():
        add(name, f"PAYS:{cc}", "country", "pays", force=True)
    for text, sec in SECTOR_ALIASES.items():
        add(text, f"SECT:{sec}", "sector", "secteur", force=True)
    for text, th in THEME_ALIASES.items():
        if th not in THEMES:
            raise ValueError(f"thème inconnu {th!r}")
        add(text, f"THEME:{th}", "theme", "theme", force=True)
    for code in THEMES:
        # Les codes trop génériques (« croissance », « climat », « or »…) ne sont pas des alias.
        if code not in ("CROISSANCE", "CLIMAT", "ENERGIE", "OR", "MONNAIE", "SANCTIONS", "LOGISTIQUE", "GAZ"):
            add(code.replace("_", " ").lower(), f"THEME:{code}", "theme", "theme")
    for text in MARKET_ALIASES:
        add(text, "MARCHE", "market", "marche", force=True)
    # Les mots trop courants ne doivent jamais devenir alias, même par dérivation.
    for w in ("or", "brut", "marche", "total", "orange", "principal", "prestige", "composite"):
        entries.pop(alias_key(w), None)
    variants = {k: v for k, v in variants.items() if k in entries}
    return AliasTable(entries, collisions, variants=variants).compile()


_TABLE: list[AliasTable] = []


def alias_table(refresh: bool = False) -> AliasTable:
    """Table d'alias par défaut (construite une fois, à partir du panel du dépôt)."""
    if refresh or not _TABLE:
        _TABLE.clear()
        _TABLE.append(build_alias_table())
    return _TABLE[0]


# ---------------------------------------------------------------------------
# Liaison
# ---------------------------------------------------------------------------


@dataclass
class EntityMatch:
    """Une mention trouvée : code, nature, forme exacte dans le texte, position."""

    code: str
    kind: str
    surface: str
    alias: str
    start: int
    end: int
    field: str  # title | text


@dataclass
class EntityLinks:
    """Résultat de :func:`link_entities`."""

    targets: list[str] = field(default_factory=list)
    matches: list[EntityMatch] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)

    @property
    def terms(self) -> dict[str, list[str]]:
        """Formes trouvées par code (dans l'ordre d'apparition, sans doublon)."""
        out: dict[str, list[str]] = {}
        for m in self.matches:
            lst = out.setdefault(m.code, [])
            if m.surface not in lst:
                lst.append(m.surface)
        return out

    def by_kind(self, kind: str) -> list[str]:
        """Codes d'une nature donnée (symbol, index, country, sector, theme, market)."""
        return [t for t in self.targets if target_kind(t) == kind]

    def count(self, code: str) -> int:
        """Nombre de mentions d'un code."""
        return sum(1 for m in self.matches if m.code == code)

    def in_title(self, code: str) -> bool:
        """Le code est-il mentionné dans le titre ?"""
        return any(m.code == code and m.field == "title" for m in self.matches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "targets": list(self.targets),
            "terms": self.terms,
            "ambiguous": list(self.ambiguous),
            "matches": [m.__dict__.copy() for m in self.matches],
        }


_WORD_START = re.compile(r"(?<![a-z0-9])[a-z0-9]")
_CITY_KEYS = frozenset({
    "abidjan", "yamoussoukro", "sanpedro", "dakar", "cotonou", "portonovo", "ouagadougou", "ouaga",
    "bobodioulasso", "bamako", "niamey", "lome", "bissau",
})
_SIGNATURE_AFTER = re.compile(r"\s*,?\s*(?:le\s+)?\d{1,2}(?:er)?\s+(?:janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre|\d)")


def _scan_longest(rx: re.Pattern, norm: str) -> Iterator[re.Match]:
    """Mentions sans chevauchement, la plus longue l'emportant.

    ``finditer`` renvoie la mention la plus à gauche ; une mention plus longue qui commence
    à l'intérieur (« la BRVM 30 » : « la BRVM » puis « BRVM 30 ») doit l'emporter.
    """
    pos = 0
    n = len(norm)
    while pos < n:
        m = rx.search(norm, pos)
        if m is None:
            return
        best = m
        for ws in _WORD_START.finditer(norm, m.start() + 1, m.end()):
            m2 = rx.match(norm, ws.start())
            if m2 is not None and m2.end() > best.end() and (m2.end() - m2.start()) >= (best.end() - best.start()):
                best = m2
        yield best
        pos = max(best.end(), pos + 1)


def _link_one(text: str, fld: str, table: AliasTable, kinds: Iterable[str] | None) -> tuple[list[EntityMatch], list[str]]:
    norm, idx = fold_with_map(text)
    if not norm:
        return [], []
    matches: list[EntityMatch] = []
    ambiguous: list[str] = []
    allowed = set(kinds) if kinds else None
    for m in _scan_longest(table.regex, norm):  # type: ignore[arg-type]
        key = alias_key(m.group(0))
        al = table.aliases.get(key)
        if al is None:
            continue
        a, b = m.start(), m.end()
        o_start = idx[a]
        o_end = idx[b - 1] + 1
        surface = text[o_start:o_end]
        if al.code is None:
            ambiguous.append(surface)
            continue
        # « brvm » entre barres obliques (n° d'avis « N°289/BRVM/2026 ») : ce n'est pas le marché.
        if al.code == "MARCHE" and key == "brvm":
            before = norm[a - 1] if a > 0 else ""
            after = norm[b] if b < len(norm) else ""
            if before == "/" or after == "/":
                continue
        if al.upper_only and surface != surface.upper():
            continue
        kind = target_kind(al.code)
        if allowed is not None and kind not in allowed:
            continue
        # Lieu de signature (« Lomé, le 23 octobre 2026 ») : ce n'est pas le sujet de la note.
        if kind == "country" and key in _CITY_KEYS and _SIGNATURE_AFTER.match(norm, b):
            continue
        matches.append(EntityMatch(al.code, kind, surface, al.text, o_start, o_end, fld))
    return matches, ambiguous


_TITLE_PREFIX = re.compile(r"^\s*([^:;]{3,70}?)\s*[:;]")


def _fuzzy_issuer(title: str, table: AliasTable, cutoff: float = 0.9) -> EntityMatch | None:
    """Émetteur en tête d'un titre brvm.org (« VIVO ENERY CÔTE D'IVOIRE : … ») mal orthographié.

    Comparaison approchée (``difflib``, ratio ≥ ``cutoff``) de la clé du préfixe avec les
    clés des alias de sociétés ; uniquement si aucune société n'a été trouvée autrement.
    """
    import difflib

    m = _TITLE_PREFIX.match(title or "")
    if not m:
        return None
    prefix = m.group(1)
    key = alias_key(prefix)
    if len(key) < 6:
        return None
    cands = {k: a for k, a in table.aliases.items() if a.code and a.kind == "symbol" and len(k) >= 5}
    al = cands.get(key)
    if al is None:
        best = difflib.get_close_matches(key, list(cands), n=2, cutoff=cutoff)
        if not best:
            return None
        if len(best) == 2 and cands[best[0]].code != cands[best[1]].code:
            r0 = difflib.SequenceMatcher(None, key, best[0]).ratio()
            r1 = difflib.SequenceMatcher(None, key, best[1]).ratio()
            if abs(r0 - r1) < 0.02:
                return None  # deux sociétés également proches : on ne tranche pas
        al = cands[best[0]]
    start = m.start(1)
    return EntityMatch(al.code, "symbol", prefix.strip(), "~" + al.text, start, start + len(prefix.rstrip()), "title")


def link_entities(
    text: str,
    title: str = "",
    kinds: Iterable[str] | None = None,
    table: AliasTable | None = None,
    fuzzy_issuer: bool = True,
) -> EntityLinks:
    """Trouve les entités citées dans ``title`` puis ``text``.

    ``fuzzy_issuer`` : si aucune société n'est trouvée, l'émetteur en tête du titre
    (« XXX : … ») est comparé de façon approchée aux alias (fautes de frappe des listes
    brvm.org : « VIVO ENERY », « AFRICA GLOGAL », « BENABE »).

    Renvoie les cibles (codes canoniques, dans l'ordre d'apparition, titre d'abord), les
    mentions (forme exacte et position) et les formes ambiguës non liées.
    ``kinds`` restreint les natures recherchées (ex. ``("symbol", "index")``).
    """
    table = table or alias_table()
    res = EntityLinks()
    for fld, t in (("title", title or ""), ("text", text or "")):
        ms, amb = _link_one(t, fld, table, kinds)
        res.matches.extend(ms)
        for a in amb:
            if a not in res.ambiguous:
                res.ambiguous.append(a)
    if fuzzy_issuer and (kinds is None or "symbol" in set(kinds)) and title:
        if not any(m.kind == "symbol" for m in res.matches):
            fm = _fuzzy_issuer(title, table)
            if fm is not None:
                # le préfixe approché remplace les liens lus à l'intérieur (« … CÔTE D'IVOIRE »)
                res.matches = [m for m in res.matches if not (m.field == "title" and m.start < fm.end)]
                res.matches.insert(0, fm)
    for m in res.matches:
        if m.code not in res.targets:
            res.targets.append(m.code)
    return res


def resolve_alias(text: str, kinds: Iterable[str] | None = None) -> str | None:
    """Code d'une désignation isolée (« Sonatel », « Orange CI », « Abidjan », « cacao »).

    Correspondance exacte d'abord ; sinon, une seule entité liée couvrant l'essentiel
    de la chaîne. ``None`` si inconnue ou ambiguë.
    """
    table = alias_table()
    allowed = set(kinds) if kinds else None
    al = table.lookup(text)
    if al is not None:
        if al.code is None:
            return None
        if allowed is None or target_kind(al.code) in allowed:
            if al.upper_only:
                return al.code if str(text).strip().isupper() else None
            return al.code
        return None
    links = link_entities(str(text), kinds=allowed, table=table)
    if len(links.targets) == 1 and not links.ambiguous:
        covered = sum(len(alias_key(m.surface)) for m in links.matches)
        if covered >= 0.6 * max(1, len(alias_key(str(text)))):
            return links.targets[0]
    return None


_VERIFY_COUNTRY = (
    ("cote d ivoire", "ci"), ("rci", "ci"), ("senegal", "sn"), ("benin", "bn"), ("burkina faso", "bf"),
    ("burkina", "bf"), ("mali", "ml"), ("niger", "ng"), ("togo", "tg"),
)
_VERIFY_STOP = frozenset({"de", "du", "d", "l", "la", "le", "et", "pour", "des"})


def _verify_tokens(text: str) -> list[str]:
    s = " " + " ".join(_tokens(text)) + " "
    for full, code in _VERIFY_COUNTRY:
        s = s.replace(f" {full} ", f" {code} ")
    s = s.replace(" boa ", " bank of africa ")
    toks = s.split()
    if toks and toks[0] == "groupe":
        toks = toks[1:]
    return toks


def _tok_eq(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)))


def alias_in_label(alias: str, label: str) -> bool:
    """L'alias se lit-il dans le libellé (mots contigus, abréviations, sigle, pays en code) ?"""
    a = _verify_tokens(alias)
    lab = _verify_tokens(label)
    if not a or not lab:
        return False
    for i in range(len(lab) - len(a) + 1):
        if all(_tok_eq(x, y) for x, y in zip(a, lab[i : i + len(a)])):
            return True
    if alias_key(alias) in "".join(lab):
        return True
    # Mots de l'alias présents dans l'ordre (« CORIS BANK BF » / « CORIS BANK INTERNATIONAL BF »).
    j = 0
    for t in lab:
        if j < len(a) and _tok_eq(a[j], t):
            j += 1
    if j == len(a) and len(a) >= 2:
        return True
    if len(a) <= 2 and len(a[0]) >= 3:  # sigle : initiales du libellé (« SIB », « LNB », « AGL », « ETI »)
        initials = "".join(t[0] for t in lab if t not in _VERIFY_STOP)
        if initials.startswith(a[0]):
            return True
    return False


def verify_aliases(panel_dir: str | Path | None = None) -> pd.DataFrame:
    """Contrôle des alias usuels contre les libellés réels du panel.

    Une ligne par alias usuel : symbole, symbole présent dans le panel, alias lisible dans
    un libellé du panel (``in_panel_name`` : mots contigus, abréviation « TRANS. »,
    sigle « SIB » = Société Ivoirienne de Banque, pays écrit en code « CI »), et la
    justification documentaire (``evidence``) quand l'alias est une marque ou un ancien nom.
    """
    names = panel_names(panel_dir)
    rows = []
    for text, sym in COMPANY_ALIASES.items():
        labels = names.get(sym, ())
        # Les autres alias du même titre qui figurent dans le panel servent aussi de libellés
        # (« SIB » se vérifie contre « SOCIETE IVOIRIENNE DE BANQUE »).
        in_name = any(alias_in_label(text, lab) for lab in labels)
        rows.append({
            "alias": text,
            "symbol": sym,
            "symbol_in_panel": sym in names,
            "in_panel_name": in_name,
            "evidence": ALIAS_EVIDENCE.get(text, ""),
            "panel_names": " | ".join(labels),
        })
    return pd.DataFrame(rows)


__all__ = [
    "Alias", "AliasTable", "EntityLinks", "EntityMatch", "alias_table", "build_alias_table",
    "link_entities", "resolve_alias", "verify_aliases", "panel_names", "alias_key",
    "COMPANY_ALIASES", "COUNTRY_ALIASES", "INDEX_ALIASES", "SECTOR_ALIASES", "THEME_ALIASES",
    "MARKET_ALIASES", "AMBIGUOUS_ALIASES", "THEME_EXPOSURES", "theme_exposure",
]
