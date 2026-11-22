"""Lexique BRVM-FR v0 et règles de types d'événements (document 07, §3.3, §3.4 et §6.4).

Le lexique est **construit pour ce projet** et **non validé** (aucune annotation à ce
jour, document 07 §3.6 et §7) : ses poids sont des hypothèses de départ.

- Poids : ±2 signal fort, ±1 signal modéré ; ``unc`` = incertitude (augmente le risque,
  pas la direction) ; ``neutral`` = forme neutre qui **bloque** une lecture trompeuse
  (« déficit budgétaire » n'est pas une perte de la société, « sans réserve » n'est pas
  une réserve d'audit, « principe de continuité d'exploitation » n'est pas un doute).
- Les expressions s'appliquent au texte normalisé (minuscules, sans accents, voir
  :func:`brvm_alpha.notes.model.fold`).
- « provision », « charges », « impôt », « dette », « capital » ne sont **pas** négatifs
  en eux-mêmes (piège Loughran-McDonald).

Règles de calcul (§3.4) appliquées par :func:`scan` :
1. négation (« pas de », « absence de », « aucun », « sans », « ne … pas », « non ») dans
   les 3 mots qui précèdent le terme, dans la même proposition : signe inversé ;
2. contraste : avec « malgré », « en dépit de », « bien que », la proposition concédée
   (qui suit) pèse ×0,5 ; avec « mais », « toutefois », « cependant », « néanmoins », la
   proposition qui précède pèse ×0,5 ;
3. intensité : « fortement », « nettement », « significativement », « record », ou un
   pourcentage supérieur à 20 % : ×1,5 ; « légèrement », « léger », « stable » : ×0,5 ;
4. ton du document : ``tone = (P − N) / (P + N + 1)``.

Extensions v0.1 (signalées ``ext``) : symétriques négatives des termes positifs du
§3.3 (« baisse du chiffre d'affaires », « recul des crédits »), nécessaires à l'exemple
de contraste du §3.4 (« malgré le recul des crédits »).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from .model import fold, fold_with_map

LEXICON_VERSION = "BRVM-FR v0 (document 07 §3.3, 22/11/2026) + ext v0.1"

# ---------------------------------------------------------------------------
# Briques d'expressions (texte normalisé)
# ---------------------------------------------------------------------------

UP = r"(?:hausses?|progressions?|croissance|ameliorations?|augmentations?|accroissements?|redressement|envolee|bond|rebond|embellie)"
DOWN = (
    r"(?:baisses?|reculs?|replis?|chutes?|contractions?|diminutions?|deteriorations?|degradations?|"
    r"effondrement|regression|erosion|flechissement|retrait)"
)
DET = r"(?:\s+(?:du|de\s+la|de\s+l'|de|des|d'|son|sa|ses|leur|leurs|le|la|les|l'))*"
RN = (
    r"(?:resultats?\s+nets?(?:\s+(?:consolides?|sociaux|social|part\s+du\s+groupe|global))?|"
    r"benefices?(?:\s+nets?)?|rn|resultats?\s+de\s+l'exercice|resultats?)"
)
PNB = r"(?:pnb|produit\s+net\s+bancaire)"
CA = r"(?:chiffres?\s+d'affaires|ventes|revenus|recettes)"
MARGE = (
    r"(?:marges?(?:\s+(?:brutes?|nettes?|operationnelles?|d'exploitation))?|ebe|excedent\s+brut\s+d'exploitation|"
    r"ebitda|resultats?\s+d'exploitation|resultats?\s+operationnels?)"
)
DIV = r"(?:dividendes?(?:\s+(?:nets?|bruts?|par\s+action|ordinaires?))*)"
ACTIVITY = (
    r"(?:credits?|depots?|encours|volumes?|activites?|production|parc\s+(?:clients|abonnes)|abonnes|"
    r"trafic|tonnages?|exportations|clientele)"
)
VERB_UP = r"(?:progresse(?:nt)?|augmente(?:nt)?|s'ameliore(?:nt)?|s'accroit|s'accroissent|croit|croissent|grimpe(?:nt)?)"
VERB_DOWN = (
    r"(?:recule(?:nt)?|baisse(?:nt)?|chute(?:nt)?|diminue(?:nt)?|se\s+degrade(?:nt)?|se\s+contracte(?:nt)?|"
    r"s'erode(?:nt)?|plonge(?:nt)?|s'effondre(?:nt)?|flechi(?:t|ssent))"
)
ADJ = (
    r"(?:(?:legere|leger|forte|fort|nette|sensible|vive|vif|lente|nouvelle|tres\s+forte|tres\s+nette|"
    r"significative|importante|spectaculaire|nouveau|net)\s+)?"
)
COPULA = r"(?:(?:est|reste|ressort|s'inscrit|s'affiche|se\s+situe|apparait|demeure|etait|sont)\s+)?"
PRESS_UP = r"(?:bondi(?:t|ssent)|s'envole(?:nt)?|double(?:nt)?|triple(?:nt)?|explose(?:nt)?|grimpe(?:nt)?)"
#: Jusqu'à deux mots entre l'indicateur et « en hausse » (« dividende Sonatel attendu en
#: hausse ») ; les mots qui changeraient le sujet (« contre », « et », chiffres) sont exclus.
GAP2 = r"(?:\s+(?!en\b|et\b|contre\b|mais\b|ni\b)[a-z][a-z'-]*){0,2}"

# ---------------------------------------------------------------------------
# Termes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Term:
    """Une entrée du lexique."""

    label: str
    pattern: str
    weight: float
    kind: str  # pos | neg | unc | neutral
    indicator: str | None = None  # rn | pnb | ca | marge | div | rating | activity
    risk: str | None = None  # R1..R10
    builtin_negation: bool = False  # la négation fait partie du terme (« pas de dividende »)
    source: str = "§3.3"
    context: str | None = None  # expression exigée dans la même phrase (texte normalisé)


TERMS: tuple[Term, ...] = (
    # --- Positifs -----------------------------------------------------------
    Term("hausse du résultat net",
         rf"{UP}{DET}\s+{RN}|{RN}\s+{COPULA}(?:en\s+)?{ADJ}(?:{UP}|{VERB_UP})|benefices?\s+en\s+hausse", 2, "pos", "rn"),
    Term("bénéfice record",
         r"(?:benefices?|resultats?(?:\s+nets?)?)\s+records?|plus\s+haut\s+historique|record\s+historique", 2, "pos", "rn"),
    Term("retour aux bénéfices",
         r"retour\s+(?:aux\s+benefices|a\s+la\s+rentabilite|a\s+l'equilibre|a\s+la\s+croissance|dans\s+le\s+vert)|"
         r"renou(?:e|ent)\s+avec\s+(?:les\s+benefices|le\s+benefice|la\s+croissance|la\s+rentabilite)|"
         r"redevient\s+beneficiaire", 2, "pos", "rn"),
    Term("verbe de presse sur le bénéfice",
         rf"(?:benefices?|resultats?(?:\s+nets?)?|rn)\b[^.;]{{0,40}}?\b{PRESS_UP}|"
         r"(?:accroit|ameliore|augmente|double|triple)\s+(?:son|sa|ses|leur|leurs)\s+(?:benefices?|resultats?(?:\s+nets?)?)",
         2, "pos", "rn"),
    Term("verbe de presse sur le PNB",
         rf"{PNB}\b[^.;]{{0,40}}?\b{PRESS_UP}|(?:accroit|ameliore|augmente|double|triple)\s+(?:son|sa|ses|leur)\s+{PNB}",
         2, "pos", "pnb"),
    Term("verbe de presse sur le chiffre d'affaires",
         rf"{CA}\b[^.;]{{0,40}}?\b{PRESS_UP}|(?:accroit|ameliore|augmente|double|triple)\s+(?:son|sa|ses|leur|leurs)\s+{CA}",
         2, "pos", "ca"),
    Term("hausse du PNB", rf"{UP}{DET}\s+{PNB}|{PNB}\s+{COPULA}(?:en\s+)?{ADJ}(?:{UP}|{VERB_UP})", 1, "pos", "pnb"),
    Term("hausse du chiffre d'affaires", rf"{UP}{DET}\s+{CA}|{CA}\s+{COPULA}(?:en\s+)?{ADJ}(?:{UP}|{VERB_UP})", 1, "pos", "ca"),
    Term("hausse de la marge", rf"{UP}{DET}\s+{MARGE}|{MARGE}\s+{COPULA}(?:en\s+)?{ADJ}(?:{UP}|{VERB_UP})", 1, "pos", "marge"),
    Term("dividende en hausse",
         rf"{DIV}{GAP2}\s+en\s+{ADJ}hausse|(?:relevement|hausse|augmentation|progression)\s+du\s+dividende|"
         rf"{DIV}\s+(?:est\s+|sera\s+|a\s+ete\s+)?(?:releve|augmente|revu\s+a\s+la\s+hausse)|"
         r"dividendes?\s+records?|acompte\s+sur\s+dividendes?|dividendes?\s+exceptionnels?", 2, "pos", "div"),
    Term("attribution gratuite d'actions",
         r"attribution\s+(?:gratuite\s+d'actions|d'actions\s+gratuites)|actions\s+gratuites|"
         r"augmentation\s+de\s+capital\s+par\s+incorporation\s+de\s+(?:reserves|primes)(?:\s+et\s+de\s+primes)?|"
         r"incorporation\s+de\s+reserves", 1, "pos"),
    Term("fractionnement", r"fractionnement(?:\s+(?:du\s+nominal|de\s+l'action|des\s+actions|d'actions))?", 1, "pos", risk="R8"),
    Term("relèvement de la notation",
         r"(?:relevement|rehaussement|amelioration)\s+de\s+(?:la\s+|sa\s+)?(?:notation|note)|"
         r"perspectives?\s+(?:positive|favorable)s?|(?:note|notation)\s+(?:confirmee|maintenue|relevee|rehaussee)|"
         r"(?:confirme|rehausse|releve)\s+(?:la|sa)\s+(?:note|notation)", 1, "pos", "rating"),
    Term("amélioration de la qualité du portefeuille",
         r"(?:baisse|diminution|recul|repli)\s+du\s+cout\s+du\s+risque|"
         r"cout\s+du\s+risque\s+(?:est\s+|reste\s+)?en\s+(?:baisse|recul|repli|diminution)|"
         r"(?:baisse|diminution|recul|repli)\s+des\s+creances\s+(?:en\s+souffrance|douteuses|improductives)|"
         r"amelioration\s+du\s+coefficient\s+d'exploitation", 1, "pos"),
    Term("levée de la suspension",
         r"levee\s+de\s+(?:la\s+)?suspension(?:\s+(?:de\s+(?:la\s+)?cotation|du\s+titre|des\s+titres))?|"
         r"reprise\s+de\s+(?:la\s+)?cotation", 1, "pos"),
    Term("offre publique d'achat ou de retrait",
         r"offres?\s+publiques?\s+d'achat|offres?\s+publiques?\s+de\s+retrait|\bopa\b|\bopr\b|"
         r"prime\s+de\s+\d+(?:[,.]\d+)?\s?%", 2, "pos", risk="R6"),
    Term("nouveau contrat ou concession",
         r"nouveaux?\s+contrats?|nouvelles?\s+concessions?|renouvellement\s+de\s+(?:la\s+)?(?:convention|concession|licence)|"
         r"partenariat\s+strategique|nouvelle\s+licence", 1, "pos"),
    Term("hausse de l'activité", rf"{UP}{DET}\s+{ACTIVITY}|{ACTIVITY}\s+en\s+(?:hausse|progression)", 1, "pos", "activity",
         source="ext v0.1"),
    # Extensions v0.2 (notes de l'analyste, essai réel du 22/11/2026) : politique monétaire,
    # effet annoncé. Hypothèses de départ, non validées (doc 05 §2.3 : la baisse de 25 pb du
    # 16/06/2025 précède +7,3 % du marché à 60 séances ; signe seul retenu, poids modéré).
    Term("assouplissement monétaire",
         r"assouplissement\s+(?:de\s+la\s+politique\s+)?monetaire|"
         r"(?:baisse|reduction|diminution)\s+(?:de\s+\d+\s+(?:points\s+de\s+base|pb)\s+)?(?:du|des|de\s+ses|de\s+son)\s+taux\s+directeurs?|"
         r"(?:baisse|abaisse|reduit|diminue)(?:r|nt)?\s+(?:ses|son|les|le)\s+taux\s+directeurs?|"
         r"taux\s+directeurs?\s+(?:est\s+|sont\s+)?(?:en\s+)?(?:baisse|abaisses?|reduits?)",
         1, "pos", source="ext v0.2"),
    Term("effet favorable annoncé",
         r"(?:impacts?|effets?|incidences?|retombees?)\s+(?:tres\s+|nettement\s+)?(?:positi(?:f|fs|ve|ves)|favorables?)|"
         r"favorables?\s+(?:a|au|aux|pour)|"
         r"(?:profite(?:nt|ra|ront)?|beneficie(?:nt|ra|ront)?)\s+(?:de\s+la|de\s+l'|du|des|d')\s*"
         r"(?:hausse|baisse\s+des\s+taux|reprise|croissance|amelioration|dynamique|redressement|embellie)",
         1, "pos", source="ext v0.2"),
    # --- Négatifs -----------------------------------------------------------
    # Extensions v0.2 (notes de l'analyste, essai réel du 22/11/2026).
    Term("resserrement monétaire",
         r"resserrement\s+(?:de\s+la\s+politique\s+)?monetaire|durcissement\s+monetaire|"
         r"(?:hausse|relevement|augmentation)\s+(?:de\s+\d+\s+(?:points\s+de\s+base|pb)\s+)?(?:du|des|de\s+ses|de\s+son)\s+taux\s+directeurs?|"
         r"(?:releve|augmente|rehausse)(?:r|nt)?\s+(?:ses|son|les|le)\s+taux\s+directeurs?|"
         r"taux\s+directeurs?\s+(?:est\s+|sont\s+)?(?:en\s+)?(?:hausse|releves?)",
         -1, "neg", source="ext v0.2"),
    Term("effet défavorable annoncé",
         r"(?:impacts?|effets?|incidences?|consequences?)\s+(?:tres\s+|nettement\s+)?(?:negati(?:f|fs|ve|ves)|defavorables?)|"
         r"defavorables?\s+(?:a|au|aux|pour)|sous\s+pression|pese(?:nt|ra|ront|rait|raient)?\s+sur",
         -1, "neg", source="ext v0.2"),
    Term("risque politique ou sécuritaire",
         r"(?:tentative\s+de\s+)?coups?\s+d'etat|putsch|attaques?\s+(?:terroristes?|jihadistes?|djihadistes?|armees?)|"
         r"attentats?|tensions?\s+politiques?|crise\s+politique|instabilite\s+politique|troubles\s+(?:politiques|post-electoraux)|"
         r"violences?\s+(?:politiques|post-electorales)",
         -1, "neg", source="ext v0.2"),
    Term("nouvelle charge fiscale",
         r"nouvelles?\s+taxes?|nouveaux?\s+impots?|alourdissement\s+(?:de\s+la\s+)?fiscal\w*|hausse\s+de\s+la\s+fiscalite|"
         r"redressements?\s+fiscaux|redressement\s+fiscal",
         -1, "neg", source="ext v0.2"),
    Term("baisse du résultat net",
         rf"{DOWN}{DET}\s+{RN}|{RN}\s+{COPULA}(?:en\s+)?{ADJ}(?:{DOWN}|{VERB_DOWN})|benefices?\s+en\s+baisse|"
         rf"(?:benefices?|resultats?(?:\s+nets?)?)\b[^.;]{{0,40}}?\b(?:plonge(?:nt)?|s'effondre(?:nt)?|fond(?:ent)?)",
         -2, "neg", "rn"),
    Term("perte nette",
         r"pertes?\s+nettes?|resultats?\s+nets?\s+negatifs?|resultats?\s+(?:nets?\s+)?deficitaires?|"
         r"(?:reste|demeure|devient|est)\s+deficitaire|deficitaires?|deficits?(?:\s+nets?)?", -2, "neg", "rn"),
    Term("absence de dividende",
         r"(?:absence|suspension|suppression)\s+(?:de\s+|du\s+)(?:versement\s+(?:de\s+|du\s+|d'un\s+)?)?dividendes?|"
         r"pas\s+de\s+dividendes?|aucun\s+dividende|sans\s+dividende|"
         r"ne\s+(?:pas\s+)?(?:verser|distribuer)\s+(?:de\s+)?dividendes?|"
         r"ne\s+(?:versera|distribuera|verse|distribue)\s+(?:pas|aucun)\s+(?:de\s+)?dividendes?",
         -2, "neg", "div", builtin_negation=True),
    Term("baisse du dividende",
         rf"(?:baisse|reduction|diminution|recul)\s+du\s+dividende|dividendes?{GAP2}\s+en\s+(?:legere\s+|forte\s+)?baisse|"
         r"dividendes?\s+(?:est\s+|sera\s+|a\s+ete\s+)?(?:reduit|abaisse|revu\s+a\s+la\s+baisse)", -2, "neg", "div"),
    Term("hausse du coût du risque",
         r"(?:hausse|augmentation|alourdissement)\s+du\s+cout\s+du\s+risque|cout\s+du\s+risque\s+en\s+hausse|"
         r"dotations?\s+aux\s+provisions\s+en\s+hausse|"
         r"(?:hausse|augmentation)\s+des\s+(?:dotations\s+aux\s+provisions|creances\s+(?:douteuses|en\s+souffrance|improductives))|"
         r"creances\s+(?:douteuses|en\s+souffrance|improductives)\s+en\s+hausse|depreciations?", -1, "neg"),
    Term("alerte sur résultats",
         r"alertes?\s+sur\s+(?:les\s+)?resultats?|profit\s+warning|avertissements?\s+sur\s+(?:les\s+)?resultats?",
         -2, "neg", risk="R9"),
    Term("suspension de la cotation",
         r"suspensions?\s+(?:de\s+(?:la\s+)?cotation|du\s+titre|des\s+titres|de\s+la\s+negociation)|"
         r"titres?\s+suspendus?|suspendu\s+de\s+la\s+cote|cotation\s+suspendue", -2, "neg", risk="R1"),
    Term("procédure collective",
         r"redressement\s+judiciaire|liquidation(?:\s+judiciaire|\s+des\s+biens)?|cessation\s+(?:d'activite|des\s+paiements)|"
         r"procedures?\s+collectives?|reglement\s+preventif|en\s+liquidation", -2, "neg", risk="R3"),
    Term("capitaux propres inférieurs à la moitié du capital",
         r"capitaux\s+propres\s+(?:sont\s+|devenus\s+|deviennent\s+|restent\s+)?inferieurs?\s+a\s+la\s+moitie\s+du\s+capital(?:\s+social)?|"
         r"reconstitution\s+des\s+capitaux\s+propres|capitaux\s+propres\s+negatifs", -2, "neg", risk="R3"),
    Term("réserves ou refus de certification",
         r"certification\s+avec\s+reserves?|certifies?\s+avec\s+reserves?|(?:emet\w*|exprim\w*|formul\w*|assortie?s?\s+de)\s+(?:des\s+|une\s+|deux\s+|plusieurs\s+)?reserves?|"
         r"reserves?\s+(?:des|du)\s+commissaires?\s+aux\s+comptes|refus\s+de\s+certifi(?:er|cation)|"
         r"impossibilite\s+de\s+certifier|(?:pas\s+en\s+mesure|dans\s+l'impossibilite)\s+de\s+certifier|"
         r"opinion\s+(?:avec\s+reserves?|defavorable)|abstention\s+d'opinion", -2, "neg", risk="R3", builtin_negation=True),
    Term("doute sur la continuité d'exploitation",
         r"(?:incertitudes?|doutes?|menaces?|risques?)(?:\s+\w+){0,2}\s+(?:sur|quant\s+a|relatifs?\s+a|relatives?\s+a|concernant|pesant\s+sur)"
         r"\s+la\s+continuite\s+d'exploitation|continuite\s+d'exploitation\s+(?:est\s+)?(?:menacee|compromise|incertaine)|"
         r"mise\s+en\s+cause\s+de\s+la\s+continuite", -2, "neg", risk="R3"),
    Term("dégradation de la notation",
         r"(?:degradation|abaissement|baisse)\s+de\s+(?:la\s+|sa\s+)?(?:notation|note)|perspectives?\s+negatives?|"
         r"(?:mise\s+)?sous\s+surveillance\s+negative|(?:note|notation)\s+(?:abaissee|degradee)|"
         r"(?:abaisse|degrade)\s+(?:la|sa)\s+(?:note|notation)", -1, "neg", "rating", risk="R4"),
    Term("annulation ou report de l'assemblée générale",
         r"annulation\s+de\s+l'assemblee|report\s+de\s+l'assemblee|assemblee\s+generale(?:\s+\w+)?\s+(?:est\s+)?(?:annulee|reportee)|"
         r"(?:sur|conformement\s+aux?)\s+instructions?\s+de\s+la\s+commission\s+bancaire|"
         r"prorogation(?:\s+\w+){0,6}\s+assemblee", -1, "neg", risk="R2"),
    Term("assemblée générale qui n'aura pas lieu", r"n'aura\s+pas\s+lieu|ne\s+se\s+tiendra\s+pas", -1, "neg",
         risk="R2", builtin_negation=True, context=r"assemblee|\bago\b|\bage\b|\bagm\b"),
    Term("retard de publication",
         r"retards?\s+(?:de|dans\s+la)\s+publication|publies?\s+avec\s+retard|avec\s+retard|"
         r"non[\s-]respect\s+des\s+(?:obligations|delais)(?:\s+d'information)?|defaut\s+de\s+publication",
         -1, "neg", risk="R7", builtin_negation=True),
    Term("sanction, litige",
         r"mise\s+en\s+demeure|sanctions?|sanctionnee?s?|amendes?|contentieux|litiges?|proces", -1, "neg"),
    Term("augmentation de capital en numéraire",
         r"augmentation\s+de\s+capital\s+(?:par\s+(?:apport\s+en\s+)?|en\s+)numeraire|"
         r"droits?\s+preferentiels?\s+de\s+souscription|\bdps\b", -1, "neg", risk="R5"),
    Term("réduction de capital, radiation",
         r"reduction\s+(?:de\s+(?:son\s+)?|du\s+)capital(?:\s+social)?(?:\s+pour\s+(?:apurer|resorber|absorber)\s+(?:des|les)\s+pertes)?|"
         r"radiations?(?:\s+de\s+la\s+cote)?|retrait\s+de\s+la\s+cote|retrait\s+obligatoire", -2, "neg"),
    Term("baisse du PNB", rf"{DOWN}{DET}\s+{PNB}|{PNB}\s+{COPULA}(?:en\s+)?{ADJ}(?:{DOWN}|{VERB_DOWN})", -1, "neg", "pnb", source="ext v0.1"),
    Term("baisse du chiffre d'affaires", rf"{DOWN}{DET}\s+{CA}|{CA}\s+{COPULA}(?:en\s+)?{ADJ}(?:{DOWN}|{VERB_DOWN})", -1, "neg", "ca",
         source="ext v0.1"),
    Term("baisse de la marge", rf"{DOWN}{DET}\s+{MARGE}|{MARGE}\s+{COPULA}(?:en\s+)?{ADJ}(?:{DOWN}|{VERB_DOWN})", -1, "neg", "marge",
         source="ext v0.1"),
    Term("baisse de l'activité", rf"{DOWN}{DET}\s+{ACTIVITY}|{ACTIVITY}\s+en\s+(?:baisse|recul|repli)", -1, "neg", "activity",
         source="ext v0.1"),
    # --- Incertitude (I) ----------------------------------------------------
    Term("départ du dirigeant",
         r"demission\s+(?:du|de\s+la|de\s+son|de\s+sa)\s+(?:directeur\s+general|directrice\s+generale|dg|pdg|president)|"
         r"depart\s+(?:du|de\s+la|de\s+son|de\s+sa)\s+(?:directeur\s+general|directrice\s+generale|dg|pdg|president)|"
         r"par\s+interim|interimaire", 0, "unc"),
    Term("incertitude",
         r"incertitudes?|contexte\s+difficile|conjoncture\s+(?:defavorable|difficile)|crise\s+securitaire|"
         r"sanctions\s+(?:de\s+la\s+)?cedeao|tensions?\s+de\s+tresorerie|sous\s+reserve\s+de|eventuel(?:le)?s?|"
         r"susceptibles?\s+de|en\s+attente\s+de\s+l'autorisation|revisions?|volatilite|"
         r"rumeurs?|non\s+confirme(?:e|es|s)?|selon\s+(?:une|des|plusieurs)\s+sources?|a\s+verifier|"
         r"sous\s+toutes\s+reserves", 0, "unc"),
    # --- Formes neutres (bloquent une lecture trompeuse) ---------------------
    Term("déficit public (neutre pour la société)",
         r"deficits?\s+(?:budgetaires?|publics?|commerciaux|commercial|courants?|pluviometriques?|de\s+l'etat|"
         r"du\s+budget|de\s+la\s+balance\s+\w+)|"
         r"(?:balance(?:\s+commerciale|\s+courante|\s+des\s+paiements)?|budget(?:\s+de\s+l'etat)?|solde\s+budgetaire|"
         r"compte\s+courant|finances\s+publiques)\s+(?:est\s+|reste\s+|demeure\s+)?deficitaires?", 0, "neutral"),
    Term("certification sans réserve (neutre)",
         r"(?:certifi\w*|opinion)\s+sans\s+reserves?|sans\s+reserves?", 0, "neutral"),
    Term("principe de continuité d'exploitation (neutre)",
         r"(?:principe|hypothese|convention)\s+de\s+(?:la\s+)?continuite\s+d'exploitation", 0, "neutral"),
    Term("sans impact (neutre)",
         r"(?:sans|pas\s+d'|aucun(?:e)?|ni)\s*(?:impact|incidence|effet|consequence)s?"
         r"(?:\s+(?:negati\w+|defavorable\w*|significati\w+|majeur\w*|notable\w*))?"
         r"(?:\s+sur(?:\s+\S+){1,5})?", 0, "neutral"),
    Term("provision seule (neutre)", r"provisions?\s+pour\s+(?:risques?|charges?)", 0, "neutral"),
    Term("fractionnement d'un fonds (neutre)",
         r"fractionnement\s+(?:de\s+la\s+)?valeur\s+liquidative|fractionnement\s+des\s+(?:parts|actions)\s+de\s+(?:la\s+)?(?:sicav|fcp)",
         0, "neutral", source="ext v0.2"),
)

NEGATIONS = frozenset({"pas", "aucun", "aucune", "sans", "non", "ni", "jamais", "absence", "nullement"})
#: Faux amis de la négation : « non seulement », « ne … que », « pas seulement ».
NEGATION_BLOCKERS = frozenset({"seulement", "uniquement", "que", "qu", "moins"})
INTENSIFIERS = frozenset({
    "fortement", "nettement", "significativement", "sensiblement", "considerablement", "fort", "forte", "fortes",
    "forts", "vif", "vive", "vives", "massivement", "spectaculaire", "record", "records", "tres", "substantiel",
    "substantielle", "substantiellement", "marque", "marquee",
})
ATTENUATORS = frozenset({
    "legerement", "leger", "legere", "legers", "legeres", "stable", "stables", "modere", "moderee", "moderes",
    "moderement", "faible", "faiblement", "limite", "limitee", "marginal", "marginale", "marginalement",
})
#: Marqueurs de concession : la proposition qui SUIT est concédée (×0,5).
CONCESSIVE = ("malgre", "en depit de", "en depit d'", "bien que", "quoique", "meme si")
#: Marqueurs d'opposition : la proposition qui PRÉCÈDE est concédée (×0,5).
ADVERSATIVE = ("mais", "toutefois", "cependant", "neanmoins", "pourtant", "en revanche")

NEGATION_WINDOW = 3
CONCESSION_WEIGHT = 0.5
INTENSIFIER_MULT = 1.5
ATTENUATOR_MULT = 0.5
PCT_INTENSITY_THRESHOLD = 20.0


@lru_cache(maxsize=1)
def _compiled_terms() -> tuple[tuple[Term, re.Pattern], ...]:
    return tuple((t, re.compile(r"(?<![a-z0-9])(?:" + t.pattern + r")(?![a-z0-9])")) for t in TERMS)


# ---------------------------------------------------------------------------
# Analyse lexicale
# ---------------------------------------------------------------------------


@dataclass
class TermHit:
    """Un terme trouvé, avec ses modificateurs et son poids effectif."""

    label: str
    kind: str
    base_weight: float
    weight: float
    indicator: str | None
    risk: str | None
    surface: str
    start: int  # position dans le texte normalisé
    end: int
    sentence: int
    modifiers: list[str] = field(default_factory=list)
    source: str = "§3.3"

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.surface,
            "label": self.label,
            "kind": self.kind,
            "base_weight": self.base_weight,
            "weight": round(self.weight, 4),
            "indicator": self.indicator,
            "risk": self.risk,
            "modifiers": list(self.modifiers),
            "source": self.source,
        }


_SENT_SPLIT = re.compile(r"(?<!\d)[.!?](?!\d)|[;\n]|(?<=\d)\.(?=\s)")
_CLAUSE_SPLIT = re.compile(r"[,:()\[\]«»\"]|\s-\s|\s-$|^-\s")
_TOKEN = re.compile(r"[a-z0-9]+")
_PCT = re.compile(r"([+\-]?\s?\d+(?:[.,]\d+)?)\s?%")


def _sentences(norm: str) -> list[tuple[int, int]]:
    spans = []
    last = 0
    for m in _SENT_SPLIT.finditer(norm):
        if m.start() > last:
            spans.append((last, m.start()))
        last = m.end()
    if last < len(norm):
        spans.append((last, len(norm)))
    return spans


def _clauses(norm: str, a: int, b: int) -> list[tuple[int, int]]:
    out = []
    last = a
    for m in _CLAUSE_SPLIT.finditer(norm, a, b):
        if m.start() > last:
            out.append((last, m.start()))
        last = m.end()
    if last < b:
        out.append((last, b))
    return out


def _marker_positions(norm: str, a: int, b: int, markers: tuple[str, ...]) -> list[tuple[int, int]]:
    out = []
    seg = norm[a:b]
    for mk in markers:
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(mk) + r"(?![a-z0-9])", seg):
            out.append((a + m.start(), a + m.end()))
    return sorted(out)


def _conceded_spans(norm: str, a: int, b: int) -> list[tuple[int, int]]:
    """Portions concédées d'une phrase (règle de contraste, §3.4)."""
    spans: list[tuple[int, int]] = []
    clause_ends = [e for _, e in _clauses(norm, a, b)]
    for s, e in _marker_positions(norm, a, b, CONCESSIVE):
        end = next((ce for ce in clause_ends if ce > e), b)
        # « malgré X, Y » : X va jusqu'à la fin de la proposition ; « Y malgré X » idem.
        spans.append((s, end))
    adv = _marker_positions(norm, a, b, ADVERSATIVE)
    prev = a
    for s, e in adv:
        after = norm[e : e + 12]
        additive = re.match(r"\s*(?:aussi|egalement|encore|surtout)\b", after) is not None
        if additive or re.search(r"(?<![a-z0-9])(?:non|pas)\s+seulement(?![a-z0-9])", norm[prev:s]):
            continue  # « non seulement … mais aussi » : addition, pas concession
        spans.append((prev, s))
        prev = e
    return spans


def _tokens_before(norm: str, clause_start: int, pos: int, n: int) -> list[tuple[str, int]]:
    toks = [(m.group(0), m.start()) for m in _TOKEN.finditer(norm, clause_start, pos)]
    return toks[-n:] if n else toks


def scan(text: str, title: str = "") -> list[TermHit]:
    """Trouve les termes du lexique dans ``title`` puis ``text`` et applique les règles du §3.4.

    Les chevauchements sont résolus au profit du terme le plus long (une forme neutre
    plus longue neutralise un terme trompeur qu'elle contient).
    """
    full = (title.strip() + "\n" if title and title.strip() else "") + (text or "")
    norm, idx = fold_with_map(full)
    if not norm:
        return []
    sentences = _sentences(norm)

    def _sentence_of(pos: int) -> tuple[int, int]:
        for a, b in sentences:
            if a <= pos < b:
                return a, b
        return (0, len(norm))

    raw: list[tuple[int, int, Term]] = []
    for term, rx in _compiled_terms():
        for m in rx.finditer(norm):
            if m.end() <= m.start():
                continue
            if term.context:
                sa, sb = _sentence_of(m.start())
                if not re.search(term.context, norm[sa:sb]):
                    continue
            raw.append((m.start(), m.end(), term))
    # Plus long d'abord, puis le plus à gauche.
    raw.sort(key=lambda x: (-(x[1] - x[0]), x[0]))
    chosen: list[tuple[int, int, Term]] = []
    occupied: list[tuple[int, int]] = []
    for s, e, t in raw:
        if any(s < oe and os_ < e for os_, oe in occupied):
            continue
        chosen.append((s, e, t))
        occupied.append((s, e))
    chosen.sort(key=lambda x: x[0])
    hits: list[TermHit] = []
    for s, e, t in chosen:
        si = next((i for i, (a, b) in enumerate(sentences) if a <= s < b), len(sentences) - 1)
        sa, sb = sentences[si] if sentences else (0, len(norm))
        if t.context and not re.search(t.context, norm[sa:sb]):
            continue
        surface = " ".join(full[idx[s] : idx[e - 1] + 1].split())
        hit = TermHit(t.label, t.kind, float(t.weight), float(t.weight), t.indicator, t.risk, surface, s, e, si, source=t.source)
        if t.kind in ("pos", "neg"):
            _apply_modifiers(hit, norm, sa, sb, t)
        hits.append(hit)
    return hits


def _apply_modifiers(hit: TermHit, norm: str, sa: int, sb: int, term: Term) -> None:
    s, e = hit.start, hit.end
    clause_start = sa
    for ca, cb in _clauses(norm, sa, sb):
        if ca <= s < cb:
            clause_start = ca
            break
    # 1) Négation.
    if not term.builtin_negation:
        before = _tokens_before(norm, clause_start, s, NEGATION_WINDOW + 1)
        window = before[-NEGATION_WINDOW:]
        toks = [w for w, _ in before]
        negated = False
        for i, (w, _) in enumerate(window):
            j = len(before) - len(window) + i
            nxt = toks[j + 1] if j + 1 < len(toks) else ""
            if w in NEGATIONS and nxt not in NEGATION_BLOCKERS:
                negated = True
        if negated:
            hit.weight = -hit.weight
            hit.modifiers.append("négation")
    # 2) Contraste.
    for a, b in _conceded_spans(norm, sa, sb):
        if a <= s < b:
            hit.weight *= CONCESSION_WEIGHT
            hit.modifiers.append("concession ×0,5")
            break
    # 3) Intensité (hors du terme lui-même, ±3 mots dans la proposition).
    clause_end = sb
    for ca, cb in _clauses(norm, sa, sb):
        if ca <= s < cb:
            clause_end = cb
            break
    left = [w for w, _ in _tokens_before(norm, clause_start, s, 3)]
    right = [m.group(0) for m in _TOKEN.finditer(norm, e, clause_end)][:3]
    inside = set(_TOKEN.findall(norm[s:e]))
    if "record" in term.label:
        inside -= {"record", "records"}  # « record » fait partie du terme : pas de double compte
    words = set(left) | set(right) | inside
    intens = bool(words & INTENSIFIERS)
    atten = bool(words & ATTENUATORS)
    if not intens:
        for m in _PCT.finditer(norm, s, min(sb, e + 80)):
            try:
                v = float(m.group(1).replace(" ", "").replace(",", "."))
            except ValueError:
                continue
            if abs(v) > PCT_INTENSITY_THRESHOLD:
                intens = True
                hit.modifiers.append(f"pourcentage {m.group(1).strip()} % > 20 %")
            break
    if intens and not atten:
        hit.weight *= INTENSIFIER_MULT
        hit.modifiers.append("intensité ×1,5")
    elif atten and not intens:
        hit.weight *= ATTENUATOR_MULT
        hit.modifiers.append("atténuation ×0,5")


def tone_from_hits(hits: list[TermHit], exclude_indicators: set[str] | frozenset[str] = frozenset()) -> dict[str, float]:
    """Ton lexical ``(P − N) / (P + N + 1)`` et ses composantes.

    Les termes dont l'indicateur figure dans ``exclude_indicators`` sont ignorés : le
    sentiment numérique les **remplace** (§3.4, règle 4).
    """
    p = n = 0.0
    unc = 0
    for h in hits:
        if h.kind == "unc":
            unc += 1
            continue
        if h.kind not in ("pos", "neg"):
            continue
        if h.indicator and h.indicator in exclude_indicators:
            continue
        if h.weight > 0:
            p += h.weight
        elif h.weight < 0:
            n += -h.weight
    tone = (p - n) / (p + n + 1.0)
    return {"P": p, "N": n, "tone": tone, "uncertainty": float(unc)}


def score_text(text: str, title: str = "") -> dict[str, Any]:
    """Raccourci : termes trouvés et ton lexical d'un texte."""
    hits = scan(text, title)
    res = tone_from_hits(hits)
    res["hits"] = [h.to_dict() for h in hits]
    return res


# ---------------------------------------------------------------------------
# Types d'événements (§6.4, sur le titre, insensibles à la casse et aux accents)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EventRule:
    """Règle de détection d'un type d'événement."""

    event_type: str
    pattern: str
    exclude: str | None = None
    strong: bool = True  # étiquette officielle (titre normé) ou indice plus faible
    source: str = "§6.4"


#: Documents qui ressemblent à une publication de résultats sans en être une : bilan
#: semestriel du contrat de liquidité (56 notes sur 1 097 classées RES_S1 lors de l'essai
#: réel du 22/11/2026), rapport RSE.
_NOT_RESULTS = r"contrat\s+de\s+liquidite|\brse\b|responsabilite\s+societale"
#: Fonds (SICAV, FCP, OPCVM, FCTC) : un « fractionnement de la valeur liquidative » n'est
#: pas un fractionnement d'actions (essai réel du 22/11/2026).
_FUND_CONTEXT = r"\bsicav\b|\bfcp\b|\bfcpr\b|\bopcvm\b|\bfctc\b|valeur\s+liquidative"
#: Objets d'une « suspension » qui ne sont pas la cotation d'un titre.
_NOT_LISTING = (
    r"(?:paiements?|activites?|production|exportations?|importations?|aides?|cooperation|financements?|"
    r"decaissements?|operations?\s+bancaires|transactions?\s+financieres|travaux|contrats?|licences?|"
    r"programmes?|relations?|echanges|livraisons?|accords?|versements?)"
)

EVENT_RULES: tuple[EventRule, ...] = (
    EventRule("PROFIT_WARNING",
              r"alertes?\s+sur\s+(?:les\s+)?resultats?|profit\s+warning|avertissements?\s+sur\s+(?:les\s+)?resultats?|"
              r"note\s+d'information\s+sur\s+la\s+baisse\s+d[eu]s?\s+(?:son\s+)?resultats?"),
    EventRule("RESUMPTION", r"levee\s+de\s+(?:la\s+)?suspension|reprise\s+de\s+(?:la\s+)?cotation"),
    # « suspension des paiements » (sanctions CEDEAO), « a suspendu ses activités » : pas une
    # suspension de cotation (essai réel du 22/11/2026 : faux R1 sur une note sur le Niger).
    EventRule("SUSPENSION",
              rf"\bsuspension\b(?!\s+(?:des|du|de\s+la|de\s+l'|de\s+ses|de\s+son|de\s+sa|d')\s*{_NOT_LISTING})|"
              rf"\bsuspendue?s?\b(?!\s+(?:ses|les|son|sa|leurs?)\s+{_NOT_LISTING})",
              exclude=r"dividende"),
    EventRule("DELISTING", r"\bradiation\b|retrait\s+de\s+la\s+cote|retrait\s+obligatoire"),
    EventRule("TAKEOVER",
              r"offres?\s+publiques?\s+d'achat|\bopa\b|offres?\s+publiques?\s+de\s+retrait|\bopr\b|"
              r"offres?\s+publiques?\s+d'echange|\bope\b"),
    EventRule("CAP_INC", r"augmentation\s+de\s+capital|actions\s+nouvelles|droits?\s+preferentiels?\s+de\s+souscription"),
    EventRule("OPV_IPO",
              r"offres?\s+publiques?\s+de\s+vente|introduction\s+en\s+bourse|premiere\s+cotation|\bopv\b|admission\s+a\s+la\s+cote"),
    EventRule("AG_CANCEL", r"annulation.*assembl|report.*assembl|prorogation.*assembl|assembl.*(?:annulee|reportee)"),
    EventRule("AG_CONVOCATION", r"avis\s+de\s+convocation|\bconvocation\b"),
    EventRule("AG_RESOLUTIONS", r"projets?\s+de\s+resolutions?"),
    EventRule("DIV_NOTICE",
              r"paiement\s+(?:de|des|du)\s+dividendes?|calendrier\s+de\s+paiement\s+(?:des\s+)?dividendes?|"
              r"montant\s+du\s+dividende|mise\s+en\s+paiement|date\s+ex-?\s?dividende|detachement\s+du\s+dividende"),
    EventRule("REVERSE_SPLIT", r"regroupement|consolidation\s+(?:des\s+|d')actions", exclude=_FUND_CONTEXT),
    EventRule("SPLIT", r"fractionnement", exclude=_FUND_CONTEXT),
    EventRule("NOTATION_SOUVERAINE",
              r"notations?\s+souveraines?|notes?\s+souveraines?|moody'?s|fitch|standard\s+(?:&|and|et)\s+poor'?s",
              source="notes"),
    EventRule("RATING", r"notations?\s+financieres?|\bnotation\b|\brating\b"),
    EventRule("MGMT_CHANGE",
              r"changements?\s+importants?\s+(?:dans|a)\s+la\s+direction|changements?\s+de\s+dirigeants?|\bnomination\b|"
              r"\bdemission\b|nouve(?:au|lle)\s+(?:directeur|directrice)\s+general",
              exclude=r"amf-umoa|\bamf\b|crepmf|\bbceao\b|commission\s+bancaire"),
    EventRule("THRESHOLD", r"franchissements?\s+de\s+seuils?"),
    EventRule("INDEX_CHANGE",
              r"composition\s+(?:de\s+l'|des\s+)?indices?|composition.*(?:brvm\s?30|prestige|brvm\s?10|principal)|"
              r"revision\s+(?:des\s+|de\s+l')indices?"),
    EventRule("ACT_Q1", r"1\s?er\s+trimestre|premier\s+trimestre|\bt1\b|31\s+mars|(?:first|1st)\s+quar?ter(?:ly)?|\bq1\b", exclude=_NOT_RESULTS),
    EventRule("ACT_Q3",
              r"3\s?(?:e|eme|ieme)\s+trimestre|troisieme\s+trimestre|\bt3\b|\b9\s+mois\b|neuf\s+mois|30\s+septembre|"
              r"(?:third|3rd)\s+quar?ter(?:ly)?|\bq3\b", exclude=_NOT_RESULTS),
    EventRule("RES_S1",
              r"semestre|semestriel(?:le)?s?|examen\s+limite|\bs1\b|30\s+juin|2\s?(?:e|eme|ieme)\s+trimestre|"
              r"deuxieme\s+trimestre|half[\s-]year|(?:first|1st)\s+half|semi[\s-]annual|\bh1\b", exclude=_NOT_RESULTS),
    EventRule("RES_ANNUAL",
              r"etats\s+financiers|commissaires\s+aux\s+comptes|comptes\s+annuels|rapport\s+annuel|resultats?\s+annuels?|"
              r"exercice\s+clos|31\s+decembre|rapport\s+de\s+gestion|attestation\s+(?:d'execution\s+de\s+la\s+mission\s+de\s+)?commissari|"
              r"rapports?\s+d'activites?\s+annuel|rapports?\s+d'activites?\s+(?:de\s+l'(?:exercice|annee)\s+)?20\d\d\b|"
              r"4\s?(?:e|eme|ieme)\s+trimestre|quatrieme\s+trimestre|rapport\s+du\s+conseil\s+d'administration|"
              r"financial\s+statements|annual\s+report|\bcac\b", exclude=_NOT_RESULTS),
    EventRule("REGULATOR",
              r"amf-umoa|\bamf\b|crepmf|commission\s+bancaire|mise\s+en\s+demeure|"
              r"sanctions?\s+(?:pecuniaires?|disciplinaires?|de\s+l'amf|du\s+regulateur)",
              exclude=r"coups?\s+d'etat|cedeao|election"),
    # Types propres aux notes (macro, politique…) : titre puis texte.
    EventRule("POLITIQUE",
              r"\belections?\b|presidentielle|legislatives|coups?\s+d'etat|putsch|\bjunte\b|sanctions\s+(?:de\s+la\s+)?(?:cedeao|uemoa)|"
              r"\bcedeao\b|\baes\b|confederation\s+des\s+etats|remaniement|referendum|transition\s+politique|"
              r"crise\s+politique|tensions?\s+politiques?", source="notes"),
    EventRule("SECURITE",
              r"securitaire|insecurite|terroris|jihadist|djihadist|attaques?\s+(?:armees?|terroristes?)|groupes\s+armes",
              source="notes"),
    EventRule("MATIERES_PREMIERES",
              r"\bcacao\b|caoutchouc|\bhevea\b|huile\s+de\s+palme|palmiste|\bsucre\b|\bcajou\b|anacarde|\bcoton\b|"
              r"cours\s+de\s+l'or|prix\s+de\s+l'or|\bpetrole\b|\bbaril\b|\bbrent\b|matieres\s+premieres|cours\s+mondiaux",
              source="notes"),
    EventRule("MACRO",
              r"\bbceao\b|taux\s+directeurs?|politique\s+monetaire|\binflation\b|\bpib\b|croissance\s+economique|"
              r"dette\s+publique|finances\s+publiques|\bfmi\b|eurobonds?|loi\s+de\s+finances|\bparite\b|franc\s+cfa|"
              r"emprunts?\s+(?:obligataires?\s+)?(?:de\s+l')?etat|bons\s+du\s+tresor|umoa-titres|deficit\s+budgetaire",
              source="notes"),
)

#: Types issus d'une règle « faible » : le mot « résultats » seul, sans période.
WEAK_RESULTS = re.compile(r"(?<![a-z0-9])resultats?(?![a-z0-9])(?!\s+de\s+premiere\s+cotation)")

_MACRO_TYPES = ("POLITIQUE", "SECURITE", "MATIERES_PREMIERES", "MACRO")


@lru_cache(maxsize=1)
def _compiled_rules() -> tuple[tuple[EventRule, re.Pattern, re.Pattern | None], ...]:
    return tuple(
        (r, re.compile(r.pattern), re.compile(r.exclude) if r.exclude else None) for r in EVENT_RULES
    )


def detect_event_type(title: str = "", text: str = "", text_chars: int = 400) -> tuple[str, str]:
    """Type d'événement et origine de la détection.

    Renvoie ``(type, origine)`` avec origine ∈ ``title`` (règle §6.4 sur le titre),
    ``text`` (règle trouvée dans les ``text_chars`` premiers caractères du texte),
    ``weak`` (mot « résultats » seul) ou ``none`` (``OTHER``).
    Les types macro (POLITIQUE, SECURITE, MATIERES_PREMIERES, MACRO) sont cherchés dans
    le titre puis dans tout le texte, après les types propres aux émetteurs.
    """
    nt = fold(title or "")
    nx = fold(text or "")
    rules = _compiled_rules()
    for zone, origin in ((nt, "title"), (nx[:text_chars], "text")):
        if not zone:
            continue
        for rule, rx, ex in rules:
            if rule.event_type in _MACRO_TYPES:
                continue
            if rx.search(zone) and not (ex and ex.search(zone)):
                return rule.event_type, origin
    for zone, origin in ((nt, "title"), (nx, "text")):
        if not zone:
            continue
        for rule, rx, ex in rules:
            if rule.event_type not in _MACRO_TYPES:
                continue
            if rx.search(zone) and not (ex and ex.search(zone)):
                return rule.event_type, origin
    if WEAK_RESULTS.search(nt) or WEAK_RESULTS.search(nx[:text_chars]):
        return "RES_ANNUAL", "weak"
    return "OTHER", "none"


__all__ = [
    "LEXICON_VERSION", "Term", "TERMS", "TermHit", "scan", "tone_from_hits", "score_text",
    "EventRule", "EVENT_RULES", "detect_event_type", "NEGATIONS", "INTENSIFIERS", "ATTENUATORS",
    "CONCESSIVE", "ADVERSATIVE",
]
