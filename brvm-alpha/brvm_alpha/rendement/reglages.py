"""Réglages, phrases fixes, lexique et mise en forme du module « Rendement net et pertes ».

Cahier des charges : ``docs/RENDEMENT_NET.md`` (§1, §1.1, §1.2, §4.4).

* :func:`charger` lit ``configs/rendement_net.yaml`` (valeurs par défaut du cahier si le fichier manque) ;
* les phrases fixes du §1.2 sont des constantes (``BANNER``, ``PH_ETUDE``…) ; ``PH_SEANCE`` est un gabarit,
  rendu par :func:`phrase_seance` à la date d'affichage ;
* :func:`mots_interdits` applique le test du lexique imposé (§1.1) : mots entiers, texte normalisé, liste
  blanche, règle de la phrase négative ;
* :func:`arrondi_ecran` applique la règle 10 du §1 (forme « écran ») ; :func:`fcfa` écrit un montant au franc
  (forme « détail »).

Le module ne promet aucun gain et ne rend aucune perte impossible. Performance passée ≠ garantie. Aucun gain
n'est garanti.
"""

from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

from brvm_alpha import paths as _paths

__all__ = [
    "BANNER", "PH_ETUDE", "PH_DESCRIPTIF", "PH_INTERETS", "PH_NE_PAS_TRANSMETTRE", "PH_FRAIS", "PH_ECONOMIE",
    "PH_RISQUE", "PH_PASSE", "PH_FLATTE", "PH_PLACE", "PH_COURS", "PH_REVUE", "PH_ESSAI", "PH_RESERVE",
    "PH_ETALER", "PHRASES_FIXES", "CHEMIN_REGLAGES", "DEFAUTS", "FAIT", "ESTIMATION", "HYPOTHESE",
    "R", "arrondi_ecran", "arrondi_valeur", "charger", "date_fr", "empreinte", "en_dict", "fcfa", "lire",
    "mot_statut", "mots_interdits", "normaliser", "pct", "phrase_seance", "phrases_seance", "plus_faible",
]

# ---------------------------------------------------------------------------
# Accès paresseux à l'ordre de bataille (évite tout import circulaire avec recommend.py)
# ---------------------------------------------------------------------------


class _Recommend:
    """Accès paresseux à :mod:`brvm_alpha.portfolio.recommend` : ``R.round_fcfa(x)``.

    Le module de l'ordre de bataille importera ce paquet ; l'inverse se fait à l'appel, jamais à l'import."""

    _module: Any = None

    def __getattr__(self, nom: str) -> Any:
        m = type(self)._module
        if m is None:
            from brvm_alpha.portfolio import recommend as m

            type(self)._module = m
        return getattr(m, nom)


R = _Recommend()

# ---------------------------------------------------------------------------
# Statuts (convention du cahier)
# ---------------------------------------------------------------------------

FAIT = "Fait"
ESTIMATION = "Estimation"
HYPOTHESE = "Hypothèse"
_RANG = {FAIT: 0, ESTIMATION: 1, HYPOTHESE: 2}
_MOT = {FAIT: "compté", ESTIMATION: "estimé", HYPOTHESE: "supposé"}


def plus_faible(*statuts: str) -> str:
    """Statut le plus faible (Hypothèse < Estimation < Fait) : une somme prend celui de ses termes."""
    vus = [s for s in statuts if s in _RANG]
    return max(vus, key=lambda s: _RANG[s]) if vus else HYPOTHESE


def mot_statut(statut: str) -> str:
    """Mot de l'écran : « compté » (Fait), « estimé » (Estimation), « supposé » (Hypothèse)."""
    return _MOT.get(statut, "supposé")


# ---------------------------------------------------------------------------
# Phrases fixes (§1.2), reprises telles quelles
# ---------------------------------------------------------------------------

#: Bandeau permanent, identique à ``recommend.BANNER``.
BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."
PH_ETUDE = ("Étude seulement : aucune méthode de la plate-forme n'a réussi son test. Sur 2017-2022, la règle de "
            "référence, sans les notes, a fait 5,6 points de moins par an que le marché ; les notes n'ont jamais "
            "été testées.")
PH_DESCRIPTIF = "Descriptif, pas un test."
PH_INTERETS = "Les intérêts de la réserve ne sont jamais déduits de la perte estimée."
PH_NE_PAS_TRANSMETTRE = "Étude : ne transmettez pas ces ordres à votre courtier."
PH_FRAIS = ("Ces frais n'existent que si vous achetez. Montants calculés sur un tarif supposé tant que la grille de "
            "votre courtier n'est pas saisie.")
PH_ECONOMIE = "Frais évités par rapport au tarif supposé ; 0 si votre courtier ne facture pas ce poste."
PH_RISQUE = ("Ce que vous acceptez de risquer n'est pas une limite. Une baisse plus forte a existé : le marché a "
             "perdu 46,7 % de mars 2017 à octobre 2020.")
PH_PASSE = ("Fréquences d'un seul passé (2017-2026 : quatre années de baisse, puis six de hausse). Ce ne sont pas "
            "des probabilités.")
PH_FLATTE = ("La lecture « passé rejoué » rejoue les gagnants d'aujourd'hui : elle flatte. Le seul test réel de la "
             "règle de référence a donné 5,6 points de moins par an que le marché.")
PH_PLACE = "Placer plus, c'est gagner plus si le marché monte et perdre plus s'il baisse."
PH_COURS = "Les cours peuvent monter ou baisser bien plus que ces montants."
PH_REVUE = "Un feu ouvre une revue, jamais une vente. Aucune de ces décisions n'a été testée."
PH_ESSAI = "Un essai sur papier n'est pas validé. Douze mois de suivi ne prouveront aucune règle par ses gains."
PH_RESERVE = "Taux saisi par vous. Sûreté, frais, impôt et disponibilité du placement non vérifiés."
PH_ETALER = ("Étaler l'entrée, c'est être moins investi pendant quelques mois. Le gain ou le coût dépend du sens du "
             "marché pendant ce délai : personne ne le connaît.")

PHRASES_FIXES: dict[str, str] = {
    "BANNER": BANNER, "PH_ETUDE": PH_ETUDE, "PH_DESCRIPTIF": PH_DESCRIPTIF, "PH_INTERETS": PH_INTERETS,
    "PH_NE_PAS_TRANSMETTRE": PH_NE_PAS_TRANSMETTRE, "PH_FRAIS": PH_FRAIS, "PH_ECONOMIE": PH_ECONOMIE,
    "PH_RISQUE": PH_RISQUE, "PH_PASSE": PH_PASSE, "PH_FLATTE": PH_FLATTE, "PH_PLACE": PH_PLACE,
    "PH_COURS": PH_COURS, "PH_REVUE": PH_REVUE, "PH_ESSAI": PH_ESSAI, "PH_RESERVE": PH_RESERVE,
    "PH_ETALER": PH_ETALER,
}

# ---------------------------------------------------------------------------
# Réglages (configs/rendement_net.yaml)
# ---------------------------------------------------------------------------

#: Fichier des réglages, dans le dépôt (jamais dans ``configs/strategy_v1.yaml``).
CHEMIN_REGLAGES = _paths.REPO_ROOT / "configs" / "rendement_net.yaml"

#: Valeurs par défaut du cahier (§4.4) : servent si le fichier est absent ou incomplet.
DEFAUTS: dict[str, Any] = {
    "version": 1,
    "dates": {"debut_suivi": "2026-12-01", "premiere_decision_argent_reel": "2027-06-01",
              "affirmation_performance": "2029-12-01"},
    "frais": {"irvm_verifies": ["CI", "SN"], "seuils_frais_annuels_sur_dividendes": [0.15, 0.50, 1.00],
              "seuil_frais_annuels_sur_capital": 0.01, "chutes_dividendes": [0.075, 0.20],
              "rotation_basse_mensuelle": 0.0087, "remise_a_niveau_haute": 0.0123, "horizon_ans": 3,
              "grilles_exemple": {
                  "central": {"nom": "Tarif supposé (central)", "courtage": 0.008, "taxe_courtage": 0.18,
                              "garde": 0.0025, "tenue_par_ligne": 5000, "forfait_compte": 0},
                  "sans_frais_par_ligne": {"nom": "Grille connue sans frais par ligne (FGI aux plafonds)",
                                           "courtage": 0.010, "taxe_courtage": 0.18, "garde": 0.0025,
                                           "tenue_par_ligne": 0, "forfait_compte": 4000},
                  "bas_de_fourchette": {"nom": "Bas de fourchette avec frais par ligne (BICI Bourse)",
                                        "courtage": 0.004, "taxe_courtage": 0.18, "garde": 0.001,
                                        "tenue_par_ligne": 5000, "forfait_compte": 0},
                  "borne_non_attestee": {"nom": "Borne non attestée (aucune grille lue ne cumule ces avantages)",
                                         "courtage": 0.005, "taxe_courtage": 0.18, "garde": 0.0025,
                                         "tenue_par_ligne": 0, "forfait_compte": 4000}}},
    "perte": {"pas_fcfa": 100_000, "choc_2018_ref_publie": 0.2932, "choix_parts": [0.05, 0.10, 0.20],
              "verification_appels_max": 10},
    "reserve": {"taux": None, "taux_max": 0.15},
    "risque": {"blocs_semaines": [8, 26, 52], "graines": 20, "tirages": 5000, "choc_titre": 0.30,
               "seuil_concentration": 0.05},
    "affichage": {"pas_petit_fcfa": 1000, "pas_grand_fcfa": 10_000, "seuil_grand_pas_fcfa": 100_000,
                  "lignes_max": 45, "colonnes_max": 100, "mots_par_phrase_max": 25},
    "liquidites": {"trimestres_reserve": [2, 3], "seuil_argent_qui_dort_fcfa": 100_000,
                   "delai_argent_qui_dort_seances": 20, "marge_arrondi_trimestres": 2,
                   "surcout_courtage_test": 0.002, "part_reserve_regle": 0.02,
                   "seuil_reinvestissement_fcfa": 100_000},
    "feux": {"fenetre_trou_seances": 126, "perte_paliers": [0.5, 1.0, 1.5, 2.0], "perte_sans_choix": [0.10, 0.20],
             "ligne_baisse_paliers": [0.25, 0.35, 0.45], "ligne_part_perte": 0.10,
             "ligne_part_perte_sans_choix": 0.01, "frais_ecart_fcfa": 1000, "frais_ecart_part": 0.05,
             "argent_qui_dort_ecart_fcfa": 100_000, "bulletins_manquants": {"orange": 1, "rouge": 3},
             "retard_journal_jours": 9, "dividende_non_recu_jours": 30, "rappel_rouge_jours": 14},
    "suivi": {"capital_temoin_fcfa": 10_000_000, "validite_ordre_seances": 10, "participation_volume": 0.10},
}

_CACHE: dict[tuple[str, float], dict[str, Any]] = {}


def _fusion(base: dict[str, Any], ajout: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (ajout or {}).items():
        if isinstance(v, Mapping) and isinstance(out.get(k), dict):
            out[k] = _fusion(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def charger(chemin: str | Path | None = None) -> dict[str, Any]:
    """Réglages du module : ``configs/rendement_net.yaml`` fusionné sur :data:`DEFAUTS`.

    Fichier absent : valeurs par défaut du cahier. Fichier illisible : ``ValueError`` avec le chemin (aucun calcul
    silencieux sur des réglages qu'on croit lus). Les dates sont rendues en texte ``AAAA-MM-JJ``."""
    p = Path(chemin) if chemin is not None else CHEMIN_REGLAGES
    if not p.exists():
        return copy.deepcopy(DEFAUTS)
    cle = (str(p.resolve()), p.stat().st_mtime)
    if cle in _CACHE:
        return copy.deepcopy(_CACHE[cle])
    try:
        import yaml

        brut = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - toute erreur de lecture est signalée avec le chemin
        raise ValueError(f"réglages illisibles : {p} ({exc.__class__.__name__} : {exc})") from exc
    if not isinstance(brut, Mapping):
        raise ValueError(f"réglages illisibles : {p} (un dictionnaire est attendu)")
    out = _fusion(DEFAUTS, brut)
    for k, v in list(out.get("dates", {}).items()):
        if isinstance(v, (_dt.date, _dt.datetime)):
            out["dates"][k] = v.strftime("%Y-%m-%d")
    _CACHE[cle] = out
    return copy.deepcopy(out)


def lire(reglages: Mapping[str, Any] | None, cle: str, defaut: Any = None) -> Any:
    """Valeur ``"a.b.c"`` des réglages (``None`` : réglages du fichier) ; ``defaut`` si elle manque."""
    r = charger() if reglages is None else reglages
    cur: Any = r
    for part in cle.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return defaut
        cur = cur[part]
    return cur


def empreinte(chemin: str | Path | None = None) -> str:
    """SHA-256 du fichier de réglages (pour la déclaration du suivi, §F9)."""
    p = Path(chemin) if chemin is not None else CHEMIN_REGLAGES
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Dates et phrase de la prochaine séance
# ---------------------------------------------------------------------------


def _date(x: Any) -> _dt.date:
    if isinstance(x, _dt.datetime):
        return x.date()
    if isinstance(x, _dt.date):
        return x
    if hasattr(x, "to_pydatetime"):
        return x.to_pydatetime().date()
    return _dt.date.fromisoformat(str(x)[:10])


def date_fr(x: Any) -> str:
    """Date au format jj/mm/aaaa (« n.d. » si elle est illisible)."""
    try:
        return _date(x).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "n.d."


def _mois_entre(a: _dt.date, b: _dt.date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)


def phrase_seance(aujourd_hui: Any = None, reglages: Mapping[str, Any] | None = None) -> str:
    """``PH_SEANCE`` rendue à la date d'affichage (§1.2, §8.9).

    La phrase ne promet aucune date de feu vert : avec les règles actuelles, la plate-forme ne recommandera pas
    d'argent réel. Avant le début du suivi : « à partir du » ; pendant les six premiers mois : « depuis le » ;
    ensuite, la date de la première décision possible n'est plus citée comme une date future."""
    jour = _date(aujourd_hui) if aujourd_hui is not None else _dt.date.today()
    debut = _date(lire(reglages, "dates.debut_suivi", "2026-12-01"))
    decision = _date(lire(reglages, "dates.premiere_decision_argent_reel", "2027-06-01"))
    n = _mois_entre(debut, decision)
    tete = ("Prochaine séance : aucun achat. Aucune méthode n'est validée : avec les règles actuelles, la "
            "plate-forme ne recommandera pas d'argent réel. ")
    if jour < debut:
        return (tete + f"Changer ces règles serait votre décision, jamais avant le {date_fr(decision)} "
                       f"({n} mois de suivi sur papier à partir du {date_fr(debut)}).")
    if jour < decision:
        return (tete + f"Changer ces règles serait votre décision, jamais avant le {date_fr(decision)} "
                       f"({n} mois de suivi sur papier depuis le {date_fr(debut)}).")
    return tete + f"Changer ces règles serait votre décision, écrite et signée (suivi sur papier depuis le {date_fr(debut)})."


def phrases_seance(reglages: Mapping[str, Any] | None = None) -> list[str]:
    """Les trois formes possibles de ``PH_SEANCE`` (liste blanche du test du lexique)."""
    debut = _date(lire(reglages, "dates.debut_suivi", "2026-12-01"))
    decision = _date(lire(reglages, "dates.premiere_decision_argent_reel", "2027-06-01"))
    return [phrase_seance(debut - _dt.timedelta(days=1), reglages), phrase_seance(debut, reglages),
            phrase_seance(decision, reglages)]


# ---------------------------------------------------------------------------
# Montants : détail au franc, écran arrondi (règle 10 du §1)
# ---------------------------------------------------------------------------

_ESPACE = "\u202f"  # espace fine insécable, comme l'ordre de bataille
_MOINS = "−"


def _milliers(n: int) -> str:
    return f"{abs(int(n)):,}".replace(",", _ESPACE)


def fcfa(x: Any, *, signe: bool = False, unite: bool = True) -> str:
    """Montant au franc (forme « détail ») : ``round_fcfa`` (demi vers le haut), espace fine, signe moins
    typographique ; ``signe=True`` écrit aussi « + »."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "non calculé"
    if not math.isfinite(v):
        return "non calculé"
    n = R.round_fcfa(v)
    s = (_MOINS if n < 0 else ("+" if signe and n > 0 else "")) + _milliers(n)
    return s + (" FCFA" if unite else "")


def pct(x: Any, decimales: int = 1, *, signe: bool = False) -> str:
    """Pourcentage à la française (« 89,8 % », « −19,5 % »)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "non calculé"
    if not math.isfinite(v):
        return "non calculé"
    s = f"{100 * v:+.{decimales}f}" if signe else f"{100 * v:.{decimales}f}"
    return s.replace(".", ",").replace("-", _MOINS) + " %"


def arrondi_valeur(x: float, reglages: Mapping[str, Any] | None = None) -> int:
    """Valeur arrondie de l'écran : ``pas × floor(x ÷ pas)`` (vers −∞), pas de 10 000 FCFA si |x| ≥ 100 000,
    de 1 000 FCFA sinon. Une perte grossit, un gain se réduit."""
    v = round(float(x), 6)
    grand = int(lire(reglages, "affichage.seuil_grand_pas_fcfa", 100_000))
    pas = int(lire(reglages, "affichage.pas_grand_fcfa", 10_000)) if abs(v) >= grand else \
        int(lire(reglages, "affichage.pas_petit_fcfa", 1000))
    return int(pas * math.floor(v / pas))


def arrondi_ecran(x: Any, *, suffixe: str | None = None, reglages: Mapping[str, Any] | None = None) -> str:
    """Montant de l'écran (règle 10 du §1), ``x`` compté du point de vue de l'utilisateur (gain positif, coût ou
    perte négatif).

    ``arrondi_ecran(-501_430)`` → « −510 000 » ; ``arrondi_ecran(118_001)`` → « +110 000 » ;
    ``arrondi_ecran(400)`` → « entre 0 et +1 000 » ; ``arrondi_ecran(-284_714, suffixe="de frais")`` →
    « 290 000 FCFA de frais » (le signe n'est pas écrit après « de frais » ni « de perte »). Un montant négatif ne
    s'affiche jamais 0 ; un montant absent s'écrit « non calculé », jamais 0."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "non calculé"
    if not math.isfinite(v):
        return "non calculé"
    a = arrondi_valeur(v, reglages)
    if suffixe in ("de frais", "de perte"):
        return f"{_milliers(a)} FCFA {suffixe}"
    if v > 0 and a == 0:
        petit = int(lire(reglages, "affichage.pas_petit_fcfa", 1000))
        txt = f"entre 0 et +{_milliers(petit)}"
    elif a == 0:
        txt = "0"
    else:
        txt = ("+" if a > 0 else _MOINS) + _milliers(a)
    return txt + (f" {suffixe}" if suffixe else "")


# ---------------------------------------------------------------------------
# Lexique imposé (§1.1)
# ---------------------------------------------------------------------------


def normaliser(texte: str) -> str:
    """Minuscules, accents retirés (NFKD), apostrophes typographiques remplacées par « ' », blancs réduits."""
    t = str(texte).replace("’", "'").replace("‘", "'").replace("ʼ", "'")
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[\s\u202f\u00a0]+", " ", t)


def _minuscules(texte: str) -> str:
    t = str(texte).replace("’", "'").replace("‘", "'").replace("ʼ", "'")
    return re.sub(r"[\s\u202f\u00a0]+", " ", unicodedata.normalize("NFC", t.lower()))


#: (mot affiché, motif, sur texte accentué ?, soumis à la règle de la phrase négative ?)
#: « sûr » et « gagné » se cherchent sur le texte accentué : sans accent, « sûr » serait la préposition « sur ».
_INTERDITS: list[tuple[str, str, bool, bool]] = [
    ("SGI (seul)", r"\bsgi\b", False, False),
    ("IRVM", r"\birvm\b", False, False),
    ("P10", r"\bp10\b", False, False),
    ("quantile", r"\bquantiles?\b", False, False),
    ("médiane", r"\bmedianes?\b", False, False),
    ("bootstrap", r"\bbootstrap\b", False, False),
    ("distribution", r"\bdistributions?\b", False, False),
    ("stress", r"\bstress\b", False, False),
    ("ST2", r"\bst2\b", False, False),
    ("drawdown", r"\bdrawdowns?\b", False, False),
    ("challenger", r"\bchallengers?\b", False, False),
    ("S2", r"\bs2\b", False, False),
    ("paper trading", r"\bpaper trading\b", False, False),
    ("REF", r"\bref\b", False, False),
    ("reliquat", r"\breliquats?\b", False, False),
    ("rebalancement", r"\brebalancements?\b", False, False),
    ("poche", r"\bpoches?\b", False, False),
    ("mandat", r"\bmandats?\b", False, False),
    ("garanti", r"\bgaranti(?:e|s|es)?\b", False, True),
    ("sûr", r"\bsûr(?:e|s|es)?\b", True, True),
    ("certain", r"\bcertain\b", False, True),
    ("sans risque", r"\bsans risques?\b", False, True),
    ("protégé", r"\bprotege(?:e|s|es)?\b", False, True),
    ("plafond", r"\bplafonds?\b", False, True),
    ("perte maximale", r"\bpertes? maximales?\b", False, True),
    ("gagné", r"\bgagné(?:e|s|es)?\b", True, False),
    ("rapporte", r"\brapporte\b", False, False),
    ("tracking error", r"\btracking error\b", False, False),
    ("alpha", r"\balpha\b", False, False),
    ("DSR", r"\bdsr\b", False, False),
    ("PBO", r"\bpbo\b", False, False),
    ("bêta", r"\bbeta\b", False, False),
    ("au plus", r"\bau plus\b(?!\s+tot)", False, False),
]
#: Expressions du test F4-7 (bloc « Ce que j'accepte de risquer »), en plus du lexique.
INTERDITS_RISQUE = [("sous la perte acceptée", r"\bsous la perte acceptee\b", False, False)]
_NEGATION = re.compile(r"\baucune?\b|\bjamais\b|\bni\b|\bn'[^.!?;]*?\bpas\b|\bne\b[^.!?;]*?\bpas\b")
#: Noms propres et libellés toujours permis.
LISTE_BLANCHE_BASE = ("BRVM Alpha", "votre courtier (SGI)", "courtier (SGI)")


def _retirer(texte: str, morceaux: Iterable[str], norm) -> str:
    out = texte
    for m in sorted({norm(x) for x in morceaux if x}, key=len, reverse=True):
        if m:
            out = out.replace(m, " ")
    return out


def mots_interdits(texte: str, *, liste_blanche: Iterable[str] = (), phrases_fixes: bool = True,
                   en_plus: Iterable[tuple[str, str, bool, bool]] = ()) -> list[str]:
    """Mots du lexique interdit (§1.1) trouvés dans ``texte`` (liste vide : rien à signaler).

    1. Texte normalisé (minuscules, accents retirés, apostrophes droites) ; recherche par mots entiers.
    2. Liste blanche retirée avant la recherche : « BRVM Alpha », « votre courtier (SGI) », les phrases fixes du
       §1.2 (si ``phrases_fixes``) et ``liste_blanche`` (noms de sociétés, libellés de l'ordre existant).
    3. Phrase négative : « garanti, sûr, certain, sans risque, protégé, plafond, perte maximale » sont permis dans
       une phrase (texte entre deux points) qui contient « aucun(e) », « jamais », « ni », « n'… pas » ou
       « ne… pas ».
    « sûr » et « gagné » se cherchent sur le texte accentué (sans accent, « sûr » serait « sur »)."""
    blanche = list(LISTE_BLANCHE_BASE) + list(liste_blanche)
    if phrases_fixes:
        blanche += list(PHRASES_FIXES.values()) + phrases_seance()
    textes = {False: _retirer(normaliser(texte), blanche, normaliser),
              True: _retirer(_minuscules(texte), blanche, _minuscules)}
    trouves: list[str] = []
    for nom, motif, accentue, negatif in list(_INTERDITS) + list(en_plus):
        t = textes[accentue]
        for phrase in re.split(r"[.!?]+", t):
            if not re.search(motif, phrase):
                continue
            if negatif and _NEGATION.search(normaliser(phrase)):
                continue
            trouves.append(nom)
            break
    return trouves


def compter_mots(phrase: str) -> int:
    """Nombre de mots d'une phrase (les nombres comptent pour un mot : « 100 000 » est un seul mot)."""
    t = str(phrase).strip()
    prec = None
    while prec != t:
        prec, t = t, re.sub("(\\d)[ \u202f\u00a0](\\d{3})(?!\\d)", "\\1\\2", t)
    phrase = t
    return len([m for m in re.split(r"[\s\u202f\u00a0]+", str(phrase).strip()) if re.search(r"\w", m)])


# ---------------------------------------------------------------------------
# Ordre de bataille : objet ou dictionnaire
# ---------------------------------------------------------------------------


def en_dict(ordre: Any) -> dict[str, Any]:
    """Dictionnaire de l'ordre de bataille : ``OrdreDeBataille.to_dict()`` ou le dictionnaire lui-même."""
    if ordre is None:
        raise ValueError("ordre de bataille absent")
    if isinstance(ordre, Mapping):
        return dict(ordre)
    if hasattr(ordre, "to_dict"):
        return ordre.to_dict()
    raise TypeError(f"ordre de bataille illisible : {type(ordre).__name__}")
