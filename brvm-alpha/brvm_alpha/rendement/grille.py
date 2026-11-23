"""F2 — Ce que prend mon courtier : la grille réelle (cahier ``docs/RENDEMENT_NET.md``, §F2).

L'utilisateur saisit une fois la grille écrite de son courtier (SGI). Chaque valeur garde son origine :
``supposé``, ``grille écrite`` ou ``avis d'opéré``. La grille par défaut est le tarif supposé « central » de
l'outil : ses frais sont identiques au franc à ``--couts central``.

* :func:`charger`, :func:`enregistrer` : ``<données>/profil/grille_sgi.yaml`` (jamais dans le dépôt) ; le dossier
  est un paramètre, les tests n'ouvrent jamais le profil réel ;
* :func:`vers_cost_model` : ``CostModel`` existant et forfait de compte **à part** tant que le champ
  ``CostModel.account_fee_fixed_fcfa`` n'existe pas (raccord du §4.3) ;
* :func:`comparer` : frais recalculés ligne par ligne aux quantités et tranches de l'ordre, sans relancer
  ``recommend`` ;
* :func:`questions` : les 8 questions à envoyer au courtier.

Aucun montant de frais n'est affiché sans son statut. Une économie de frais n'est pas un gain.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from brvm_alpha import paths as _paths
from brvm_alpha.config import CostModel
from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.rendement.reglages import FAIT, HYPOTHESE, R

__all__ = ["CHAMPS", "PRINCIPAUX", "STATUTS", "Champ", "GrilleSGI", "GrilleHorsFourchette", "charger", "comparer",
           "controler", "cost_model_de", "couts_recalcules", "defaut", "depuis_cost_model", "enregistree", "enregistrer",
           "exemples", "frais_explicites", "frais_hors_modele", "lire_fichier", "lire_texte", "questions", "resoudre",
           "statut_champ", "statut_global", "vers_cost_model"]

#: Origines possibles d'une valeur.
SUPPOSE, ECRITE, AVIS = "supposé", "grille écrite", "avis d'opéré"
STATUTS = (SUPPOSE, ECRITE, AVIS)

#: nom : (défaut, saisie min, saisie max, fourchette homologuée connue ou None, unité, libellé)
CHAMPS: dict[str, tuple[float, float, float, tuple[float, float] | None, str, str]] = {
    "courtage": (0.008, 0.0, 0.03, (0.004, 0.010), "part", "courtage"),
    "courtage_min_par_ordre": (0.0, 0.0, 50_000.0, None, "FCFA", "minimum de courtage par ordre"),
    "taxe_courtage": (0.18, 0.0, 0.25, None, "part", "taxe sur le courtage"),
    "garde": (0.0025, 0.0, 0.01, (0.001, 0.005), "part", "droits de garde"),
    "tenue_par_ligne": (5000.0, 0.0, 50_000.0, (0.0, 10_000.0), "FCFA", "tenue de compte par ligne"),
    "forfait_compte": (0.0, 0.0, 200_000.0, None, "FCFA", "forfait de compte"),
    "taxe_frais_annuels": (0.0, 0.0, 0.25, None, "part", "taxe sur les frais annuels"),
    "garde_minimum": (0.0, 0.0, 100_000.0, None, "FCFA", "minimum de droits de garde"),
    "encaissement_taux": (0.0, 0.0, 0.05, None, "part", "encaissement des dividendes"),
    "encaissement_fixe": (0.0, 0.0, 10_000.0, None, "FCFA", "encaissement par paiement"),
    "transfert_par_ligne": (0.0, 0.0, 100_000.0, (5000.0, 34_375.0), "FCFA", "transfert de titres par ligne"),
    "impot_plus_values": (0.0, 0.0, 0.30, None, "part", "impôt sur les plus-values"),
}
#: Les cinq champs principaux (statut global, formulaire de la carte « Mon plan »).
PRINCIPAUX = ("courtage", "taxe_courtage", "garde", "tenue_par_ligne", "forfait_compte")
INVESTISSEURS = ("personne physique résidente", "personne morale")
SOURCE_EXEMPLE = "exemples construits sur des grilles homologuées ; non confirmés pour vous"


class GrilleHorsFourchette(UserWarning):
    """Valeur acceptée mais hors de la fourchette homologuée connue (avertissement, pas un refus)."""


@dataclass
class Champ:
    """Une valeur de la grille et son origine."""

    valeur: float
    statut: str = SUPPOSE
    source: str = ""
    date: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"valeur": float(self.valeur), "statut": self.statut, "source": self.source, "date": self.date}


def _champs_defaut() -> dict[str, Champ]:
    return {k: Champ(float(v[0])) for k, v in CHAMPS.items()}


@dataclass
class GrilleSGI:
    """Grille du courtier : douze champs chiffrés (avec statut, source, date), statut de l'investisseur."""

    nom: str = "Tarif supposé (central)"
    champs: dict[str, Champ] = field(default_factory=_champs_defaut)
    investisseur: str = INVESTISSEURS[0]
    pays_residence: str = ""

    def valeur(self, nom: str) -> float:
        return float(self.champs[nom].valeur) if nom in self.champs else float(CHAMPS[nom][0])

    def avec(self, **valeurs: Any) -> "GrilleSGI":
        """Copie avec des valeurs changées (statut inchangé) : ``g.avec(tenue_par_ligne=0)``."""
        g = copy.deepcopy(self)
        for k, v in valeurs.items():
            if k not in CHAMPS:
                raise KeyError(f"champ inconnu : {k}")
            g.champs[k] = dataclasses.replace(g.champs.get(k, Champ(CHAMPS[k][0])), valeur=float(v))
        return g

    def to_dict(self) -> dict[str, Any]:
        return {"nom": self.nom, "investisseur": self.investisseur, "pays_residence": self.pays_residence,
                "statut_global": statut_global(self),
                "champs": {k: self.champs[k].to_dict() for k in CHAMPS if k in self.champs}}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "GrilleSGI":
        g = cls(nom=str(d.get("nom") or "Ma grille"), investisseur=str(d.get("investisseur") or INVESTISSEURS[0]),
                pays_residence=str(d.get("pays_residence") or ""))
        for k, v in (d.get("champs") or {}).items():
            if k not in CHAMPS:
                continue
            if isinstance(v, Mapping):
                g.champs[k] = Champ(float(v.get("valeur", CHAMPS[k][0])), str(v.get("statut") or SUPPOSE),
                                    str(v.get("source") or ""), str(v.get("date") or ""))
            else:
                g.champs[k] = Champ(float(v))
        return g


def defaut() -> GrilleSGI:
    """Grille par défaut : tarif supposé « central », tous les champs ``supposé``."""
    return GrilleSGI()


def depuis_cost_model(cm: CostModel, nom: str | None = None, forfait: float = 0.0) -> GrilleSGI:
    """Grille (tous champs ``supposé``) équivalente à un ``CostModel`` : sert quand aucune grille n'est saisie."""
    g = GrilleSGI(nom=nom or "Tarif supposé")
    vals = {"courtage": cm.sgi_commission, "courtage_min_par_ordre": cm.min_ticket_fcfa,
            "taxe_courtage": cm.vat_on_commission, "garde": cm.annual_custody,
            "tenue_par_ligne": cm.account_fee_per_line_fcfa,
            "forfait_compte": float(getattr(cm, "account_fee_fixed_fcfa", 0.0) or forfait or 0.0)}
    for k, v in vals.items():
        g.champs[k] = Champ(float(v))
    return g


# ---------------------------------------------------------------------------
# Contrôle, lecture, écriture
# ---------------------------------------------------------------------------


def _pc(v: float) -> str:
    s = f"{100 * float(v):.4f}".rstrip("0").rstrip(".")
    return s.replace(".", ",").replace("-", "−")


def _txt(nom: str, v: float) -> str:
    return f"{_pc(v)} %" if CHAMPS[nom][4] == "part" else _rg.fcfa(v)


def _plage(nom: str, lo: float, hi: float) -> str:
    if CHAMPS[nom][4] == "part":
        return f"{_pc(lo)} à {_pc(hi)} %"
    return f"{_rg.fcfa(lo, unite=False)} à {_rg.fcfa(hi)}"


def controler(grille: GrilleSGI) -> dict[str, list[str]]:
    """Erreurs (valeur hors de la saisie acceptée : refus) et avertissements (hors fourchette homologuée)."""
    err: list[str] = []
    av: list[str] = []
    for k, (d, lo, hi, homo, _u, lib) in CHAMPS.items():
        ch = grille.champs.get(k)
        if ch is None:
            continue
        v = float(ch.valeur)
        if not math.isfinite(v) or v < lo - 1e-12 or v > hi + 1e-12:
            err.append(f"{lib} : {_txt(k, v)} est hors de la plage acceptée ({_plage(k, lo, hi)})")
        elif homo is not None and abs(v - d) > 1e-12 and (v < homo[0] - 1e-12 or v > homo[1] + 1e-12):
            av.append(f"{lib} : {_txt(k, v)} est hors de la fourchette homologuée connue ({_plage(k, *homo)}) ; "
                      "valeur acceptée, à vérifier sur la grille écrite")
        if ch.statut not in STATUTS:
            err.append(f"{lib} : statut « {ch.statut} » inconnu ({', '.join(STATUTS)})")
        elif ch.statut in (ECRITE, AVIS) and not str(ch.source or "").strip():
            # §F2 : un tarif reste une Hypothèse tant qu'il n'est pas saisi avec une source.
            err.append(f"{lib} : statut « {ch.statut} » sans source (indiquez la grille écrite ou l'avis d'opéré)")
    if grille.investisseur not in INVESTISSEURS:
        err.append(f"investisseur : « {grille.investisseur} » inconnu ({' ou '.join(INVESTISSEURS)})")
    if grille.investisseur == INVESTISSEURS[1]:
        av.append("personne morale : taux d'impôt sur les dividendes et tenue de compte différents : non modélisés")
    return {"erreurs": err, "avertissements": av}


def _dossier(dossier: str | Path | None) -> Path:
    return Path(dossier) if dossier is not None else _paths.DATA_DIR / "profil"


def charger(dossier: str | Path | None = None) -> GrilleSGI:
    """Grille enregistrée (``<dossier>/grille_sgi.yaml``). Fichier absent : grille par défaut, tous les champs
    ``supposé``. Fichier illisible : ``ValueError`` avec le chemin ; aucun calcul silencieux."""
    p = _dossier(dossier) / "grille_sgi.yaml"
    if not p.exists():
        return defaut()
    try:
        import yaml

        brut = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(brut, Mapping):
            raise ValueError("un dictionnaire est attendu")
        g = GrilleSGI.from_dict(brut)
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception as exc:  # noqa: BLE001 - toute erreur est signalée avec le chemin
        raise ValueError(f"grille du courtier illisible : {p} ({exc})") from exc
    c = controler(g)
    if c["erreurs"]:
        raise ValueError(f"grille du courtier illisible : {p} (" + " ; ".join(c["erreurs"]) + ")")
    return g


def enregistrer(grille: GrilleSGI, dossier: str | Path | None = None) -> Path:
    """Écrit ``<dossier>/grille_sgi.yaml``. Refuse une valeur hors de la saisie acceptée (``ValueError``, par
    exemple « courtage : 4 % est hors de la plage acceptée (0 à 3 %) ») ; avertit sans refuser hors de la
    fourchette homologuée (``GrilleHorsFourchette``)."""
    c = controler(grille)
    if c["erreurs"]:
        raise ValueError(" ; ".join(c["erreurs"]))
    for a in c["avertissements"]:
        warnings.warn(a, GrilleHorsFourchette, stacklevel=2)
    import yaml

    d = _dossier(dossier)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "grille_sgi.yaml"
    contenu = grille.to_dict()
    contenu.pop("statut_global", None)
    entete = ("# Grille du courtier (BRVM Alpha, module « Rendement net et pertes »). Donnée de l'installation :\n"
              "# jamais dans le dépôt. Statuts : supposé, grille écrite, avis d'opéré.\n")
    from brvm_alpha import demarrage, fichiers

    texte = entete + yaml.safe_dump(contenu, allow_unicode=True, sort_keys=False)
    # Écriture atomique (fichier temporaire, fsync, renommage) ; TERM et SIGXCPU reportés pendant l'écriture : la
    # grille est toujours complète et lisible, jamais à moitié écrite.
    with demarrage.ecriture_protegee():
        fichiers.ecrire_atomique(p, texte)
    return p


#: Taille d'un fichier de grille (``--grille FICHIER``), contrôlée avant la lecture : une grille fait quelques
#: centaines d'octets (avant : aucune borne).
FICHIER_MAX_OCTETS = 65_536


def lire_fichier(chemin: str | Path) -> GrilleSGI:
    """Grille lue dans un fichier YAML donné (option ``--grille FICHIER``) ; illisible, trop volumineux (plus de
    :data:`FICHIER_MAX_OCTETS` octets) ou vide : ``ValueError`` avec le chemin."""
    p = Path(chemin)
    try:
        taille = p.stat().st_size
        if taille > FICHIER_MAX_OCTETS:
            raise ValueError(f"fichier trop volumineux ({taille} octets, {FICHIER_MAX_OCTETS} au plus)")
        texte = p.read_text(encoding="utf-8")
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"grille du courtier illisible : {p} ({exc})") from exc
    return lire_texte(texte, p)


def lire_texte(texte: str, origine: str | Path = "grille") -> GrilleSGI:
    """Grille lue dans le texte YAML d'un fichier (``origine`` : son chemin, pour le message). Texte vide, fait de
    commentaires ou dictionnaire vide : ``ValueError`` « grille vide » (avant : tarif par défaut pris sous le nom « Ma
    grille », sans le dire) ; illisible : ``ValueError`` avec le chemin."""
    try:
        import yaml

        brut = yaml.safe_load(texte)
        if brut is None or (isinstance(brut, Mapping) and not brut):
            raise ValueError("grille vide : le fichier ne contient aucune valeur (YAML de « plan grille », ou les "
                             "champs courtage, taxe…) ; sans l'option, le tarif par défaut est pris")
        if not isinstance(brut, Mapping):
            raise ValueError("un dictionnaire est attendu")
        g = GrilleSGI.from_dict(brut)
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"grille du courtier illisible : {origine} ({exc})") from exc
    c = controler(g)
    if c["erreurs"]:
        raise ValueError(f"grille du courtier illisible : {origine} (" + " ; ".join(c["erreurs"]) + ")")
    return g


def resoudre(option: Any, dossier: str | Path | None = None) -> GrilleSGI | None:
    """Option ``--grille`` : ``None`` ou ``central`` → ``None`` (tarif de ``--couts``, défaut de ``recommend``) ;
    ``ma_sgi`` → grille enregistrée (``None`` si aucune n'est enregistrée) ; un ``GrilleSGI`` → lui-même ; sinon un
    chemin de fichier YAML."""
    if option is None or isinstance(option, GrilleSGI):
        return option
    o = str(option).strip()
    if o in ("", "central"):
        return None
    if o == "ma_sgi":
        return charger(dossier) if (_dossier(dossier) / "grille_sgi.yaml").exists() else None
    return lire_fichier(o)


def enregistree(dossier: str | Path | None = None) -> bool:
    """Vrai si une grille est enregistrée dans le profil (mention « votre grille enregistrée n'est pas employée »)."""
    return (_dossier(dossier) / "grille_sgi.yaml").exists()


# ---------------------------------------------------------------------------
# Statuts
# ---------------------------------------------------------------------------


def statut_champ(grille: GrilleSGI | None, nom: str) -> str:
    """Statut du cahier d'un champ : ``Fait`` si sa source est la grille écrite ou un avis d'opéré, sinon
    ``Hypothèse``."""
    if grille is None or nom not in grille.champs:
        return HYPOTHESE
    return FAIT if grille.champs[nom].statut in (ECRITE, AVIS) else HYPOTHESE


def statut_global(grille: GrilleSGI | None) -> str:
    """``supposé`` si l'un des cinq champs principaux est supposé ; ``avis d'opéré`` si les cinq le sont ;
    sinon ``grille écrite``."""
    if grille is None:
        return SUPPOSE
    st = [grille.champs[k].statut if k in grille.champs else SUPPOSE for k in PRINCIPAUX]
    if any(s == SUPPOSE for s in st):
        return SUPPOSE
    if all(s == AVIS for s in st):
        return AVIS
    return ECRITE


# ---------------------------------------------------------------------------
# Vers le modèle de coûts de l'outil
# ---------------------------------------------------------------------------


def vers_cost_model(grille: GrilleSGI, base: CostModel | None = None) -> tuple[CostModel, float]:
    """``(CostModel, forfait de compte annuel en FCFA)``.

    ``recommend.replace_costs(base, sgi_commission, vat_on_commission, min_ticket_fcfa, annual_custody,
    account_fee_per_line_fcfa)`` ; les coûts dans le prix (demi-écart, impact) restent ceux de ``base``. Le forfait
    est rendu à part tant que ``CostModel`` n'a pas le champ ``account_fee_fixed_fcfa`` ; s'il l'a, il y est aussi
    écrit (raccord du §4.3)."""
    b = base if base is not None else CostModel()
    ch = dict(sgi_commission=grille.valeur("courtage"), vat_on_commission=grille.valeur("taxe_courtage"),
              min_ticket_fcfa=grille.valeur("courtage_min_par_ordre"), annual_custody=grille.valeur("garde"),
              account_fee_per_line_fcfa=grille.valeur("tenue_par_ligne"))
    forfait = float(grille.valeur("forfait_compte"))
    if "account_fee_fixed_fcfa" in {f.name for f in dataclasses.fields(CostModel)}:
        ch["account_fee_fixed_fcfa"] = forfait
    return R.replace_costs(b, **ch), forfait


def frais_explicites(montant: float, grille: GrilleSGI) -> dict[str, int]:
    """Frais facturés d'une exécution de ``montant`` FCFA, calculés directement sur la grille (contrôle de
    :func:`vers_cost_model` : égalité au franc avec ``recommend.fee_breakdown``)."""
    a = float(montant)
    if a <= 0:
        return {"courtage": 0, "tva": 0, "brvm": 0, "dcbr": 0, "explicites": 0}
    base = CostModel()
    c = R.round_fcfa(max(grille.valeur("courtage") * a, grille.valeur("courtage_min_par_ordre")))
    t = R.round_fcfa(grille.valeur("taxe_courtage") * c)
    b = R.round_fcfa(base.brvm_fee * a)
    d = R.round_fcfa(base.dcbr_fee * a)
    return {"courtage": c, "tva": t, "brvm": b, "dcbr": d, "explicites": c + t + b + d}


def frais_hors_modele(grille: GrilleSGI, couts: Mapping[str, Any], revenus: Mapping[str, Any] | None = None,
                      dividendes: Sequence[Mapping[str, Any]] | None = None, forfait: float | None = None) -> dict[str, int]:
    """Frais de la grille que le modèle de coûts ne connaît pas (§F2).

    ``taxe_annuelle = round_fcfa(taxe_frais_annuels × (garde + tenue + forfait))`` ;
    ``garde_complement = max(0 ; garde_minimum − garde)`` ;
    ``encaissement = round_fcfa(encaissement_taux × dividendes nets) + encaissement_fixe × paiements``."""
    garde = float(couts.get("garde_annuelle") or 0)
    tenue = float(couts.get("tenue_compte_annuelle") or 0)
    f = float(grille.valeur("forfait_compte") if forfait is None else forfait)
    taxe = R.round_fcfa(grille.valeur("taxe_frais_annuels") * (garde + tenue + f))
    compl = R.round_fcfa(max(0.0, grille.valeur("garde_minimum") - garde))
    net = float((revenus or {}).get("net") or 0)
    n_pay = int((revenus or {}).get("n_paiements") or 0)
    if dividendes is not None and not n_pay:
        n_pay = sum(1 for d in dividendes if float(d.get("montant_net") or 0) > 0)
    enc = R.round_fcfa(grille.valeur("encaissement_taux") * net) + R.round_fcfa(grille.valeur("encaissement_fixe") * n_pay)
    return {"taxe_annuelle": int(taxe), "garde_complement": int(compl), "encaissement": int(enc),
            "total": int(taxe + compl + enc)}


# ---------------------------------------------------------------------------
# Exemples et comparateur
# ---------------------------------------------------------------------------


def exemples(reglages: Mapping[str, Any] | None = None) -> dict[str, GrilleSGI]:
    """Grilles d'exemple (``frais.grilles_exemple`` des réglages), étiquetées « exemples construits sur des
    grilles homologuées ; non confirmés pour vous ». Tous les champs restent ``supposé`` pour l'utilisateur."""
    ex = _rg.lire(reglages, "frais.grilles_exemple", {}) or {}
    out: dict[str, GrilleSGI] = {}
    for cle, v in ex.items():
        g = GrilleSGI(nom=str(v.get("nom") or cle))
        for k in PRINCIPAUX + ("courtage_min_par_ordre",):
            if k in v:
                g.champs[k] = Champ(float(v[k]), SUPPOSE, SOURCE_EXEMPLE, "")
        out[str(cle)] = g
    return out


def _lignes_ordre(o: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [l for l in (o.get("lignes") or []) if str(l.get("sens")) in ("achat", "vente") and int(l.get("quantite") or 0) > 0]


def couts_recalcules(ordre: Any, grille: GrilleSGI, base: CostModel | None = None) -> dict[str, Any]:
    """Postes de coûts de l'ordre recalculés avec la grille (mêmes quantités, tranches et limites ; coûts dans le prix
    de ``base``) : courtage, taxe, BRVM, DC/BR, demi-écart, impact, total, garde, tenue de compte et forfait. Avec la
    grille par défaut, ils sont égaux au franc à ceux de l'ordre calculé au tarif central."""
    o = _rg.en_dict(ordre)
    b = base if base is not None else cost_model_de(o)
    cm, forfait = vers_cost_model(grille, b)
    out = {k: 0 for k in ("courtage", "tva", "brvm", "dcbr", "redevance", "demi_spread", "impact", "explicites",
                          "implicites", "total")}
    for l in _lignes_ordre(o):
        q = int(l["quantite"])
        tr = [int(x) for x in (l.get("tranches") or [q])]
        lim = l.get("prix_limite")
        lim = float(lim) if lim is not None and math.isfinite(float(lim)) else None
        oc = R.order_costs(q, float(l["cours_reference"]), cm, side=str(l["sens"]),
                           half_spread=float(l.get("demi_spread_pct") or 0.0),
                           mdv63=float(l["mdv63"]) if l.get("mdv63") is not None else None, tranches=tr, limit=lim)
        for k in out:
            out[k] += int(oc[k])
    c = o.get("couts") or {}
    investi = float(c.get("investi_apres") or 0)
    n = int(c.get("n_lignes") or 0)
    out.update({"garde_annuelle": int(R.round_fcfa(cm.annual_custody * investi)),
                "tenue_compte_annuelle": int(R.round_fcfa(cm.account_fee_per_line_fcfa * n)),
                "forfait_compte_annuel": int(R.round_fcfa(forfait)), "taux_garde": float(cm.annual_custody),
                "frais_par_ligne": float(cm.account_fee_per_line_fcfa), "recalcule_avec": grille.nom})
    return out


def _facture(o: Mapping[str, Any], cm: CostModel, forfait: float, grille: GrilleSGI | None) -> dict[str, Any]:
    entree = 0
    explicites = 0
    pire_achats = 0
    pire_ventes = 0
    for l in _lignes_ordre(o):
        q = int(l["quantite"])
        tr = [int(x) for x in (l.get("tranches") or [q])]
        lim = l.get("prix_limite")
        lim = float(lim) if lim is not None and math.isfinite(float(lim)) else None
        oc = R.order_costs(q, float(l["cours_reference"]), cm, side=str(l["sens"]),
                           half_spread=float(l.get("demi_spread_pct") or 0.0),
                           mdv63=float(l["mdv63"]) if l.get("mdv63") is not None else None, tranches=tr, limit=lim)
        entree += int(oc["total"])
        explicites += int(oc["explicites"])
        if lim is not None:
            if l["sens"] == "achat":
                pire_achats += R._worst_case(tr, lim, cm, "achat")
            else:
                pire_ventes += R._worst_case(tr, lim, cm, "vente")
    c = o.get("couts") or {}
    investi = float(c.get("investi_apres") or 0)
    n = int(c.get("n_lignes") or 0)
    garde = R.round_fcfa(cm.annual_custody * investi)
    tenue = R.round_fcfa(cm.account_fee_per_line_fcfa * n)
    hm = frais_hors_modele(grille, {"garde_annuelle": garde, "tenue_compte_annuelle": tenue},
                           o.get("revenus"), o.get("dividendes"), forfait) if grille is not None else {"total": 0}
    annuels = int(garde + tenue + R.round_fcfa(forfait) + hm["total"])
    liq = float(o.get("liquidites_initiales") or 0)
    marge = int(math.floor(liq)) + pire_ventes - pire_achats
    return {"frais_achat": entree, "explicites": explicites, "frais_annuels": annuels, "garde": int(garde),
            "tenue": int(tenue), "forfait": int(R.round_fcfa(forfait)), "hors_modele": int(hm["total"]),
            "premiere_annee": entree + annuels, "provision_pire_cas": int(pire_achats), "marge": int(marge),
            "quantites_a_recalculer": bool(marge < 0)}


def comparer(ordre: Any, grilles: Mapping[str, GrilleSGI] | Iterable[GrilleSGI], *, base: CostModel | None = None,
             reference: GrilleSGI | None = None) -> list[dict[str, Any]]:
    """Frais de chaque grille recalculés ligne par ligne avec ``order_costs`` aux quantités et tranches de l'ordre
    (aucune relance de ``recommend``) : frais d'achat, frais annuels, 1re année, écart avec la grille en vigueur
    (``reference``, défaut : le tarif de l'ordre), provision du pire cas, marge. Une provision qui dépasse les
    liquidités porte « quantités à recalculer » : l'ordre complet est alors à relancer."""
    o = _rg.en_dict(ordre)
    b = base if base is not None else cost_model_de(o)
    ref_g = reference if reference is not None else depuis_cost_model(b, "Tarif de l'ordre")
    cm_ref, f_ref = vers_cost_model(ref_g, b)
    ref = _facture(o, cm_ref, f_ref, ref_g)
    items = list(grilles.items()) if isinstance(grilles, Mapping) else [(g.nom, g) for g in grilles]
    out = []
    for cle, g in items:
        cm, f = vers_cost_model(g, b)
        fa = _facture(o, cm, f, g)
        fa.update({"cle": cle, "nom": g.nom, "statut": statut_global(g),
                   "ecart_premiere_annee": fa["premiere_annee"] - ref["premiere_annee"],
                   "ecart_annuel": fa["frais_annuels"] - ref["frais_annuels"],
                   "ecart_achat": fa["frais_achat"] - ref["frais_achat"],
                   "mention": "quantités à recalculer : relancer l'ordre complet" if fa["quantites_a_recalculer"] else ""})
        fa["sens_ecart"] = "surcoût" if fa["ecart_premiere_annee"] > 0 else ("frais évités" if fa["ecart_premiere_annee"] < 0 else "égal")
        out.append(fa)
    return out


def cost_model_de(o: Mapping[str, Any], costs: CostModel | str | None = None) -> CostModel:
    """``CostModel`` d'un ordre : celui donné, sinon le scénario de l'ordre, aligné sur les taux écrits dans
    ``couts`` (courtage, taxe, BRVM, DC/BR, impact, garde, tenue par ligne)."""
    if isinstance(costs, CostModel):
        return costs
    from brvm_alpha import settings

    if isinstance(costs, str):
        return settings.cost_scenario(costs)
    c = o.get("couts") or {}
    try:
        b = settings.cost_scenario(str(c.get("scenario") or "central"))
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception:  # noqa: BLE001 - scénario « fourni » ou inconnu : valeurs de l'ordre
        b = CostModel()
    ch: dict[str, Any] = {}
    for cle, champ in (("taux_courtage", "sgi_commission"), ("taux_tva", "vat_on_commission"),
                       ("taux_brvm", "brvm_fee"), ("taux_dcbr", "dcbr_fee"), ("kappa", "impact_coef"),
                       ("taux_garde", "annual_custody"), ("frais_par_ligne", "account_fee_per_line_fcfa")):
        if c.get(cle) is not None:
            ch[champ] = float(c[cle])
    if c.get("forfait_compte_annuel") is not None and "account_fee_fixed_fcfa" in {f.name for f in dataclasses.fields(CostModel)}:
        ch["account_fee_fixed_fcfa"] = float(c["forfait_compte_annuel"])
    return R.replace_costs(b, **ch)


def questions() -> list[str]:
    """Les 8 questions au courtier, texte prêt à copier."""
    return [
        "1. Quel est mon taux de courtage sur les actions ? Y a-t-il un minimum par ordre ? Ce taux comprend-il les "
        "commissions de la BRVM (0,20 %) et du dépositaire (0,10 %) ?",
        "2. Quelle taxe s'applique, à quel taux ? Sur le courtage seul ou sur tous les frais ? Vos tarifs sont-ils "
        "hors taxes ?",
        "3. Droits de garde : quel taux, sur quelle base (valeur de marché à quelle date), prélevés à quelles dates ? "
        "Y a-t-il un minimum ?",
        "4. Tenue de compte : par compte ou par ligne de titres ? Combien par an ? Le tarif change-t-il pour une "
        "personne morale ?",
        "5. Y a-t-il des frais d'encaissement des dividendes, de virement, de transfert de titres, de modification ou "
        "d'annulation d'un ordre ?",
        "6. Puis-je avoir un avis d'opéré type, avec toutes les lignes de frais ?",
        "7. Le compte espèces est-il rémunéré ? À quel taux net ? Faut-il provisionner avant l'ordre ? Quand le "
        "produit d'une vente et les dividendes sont-ils disponibles ?",
        "8. Un impôt sur les plus-values s'applique-t-il à ma situation ?",
    ]
