"""Commandes « plan » et « suivi » du module « Rendement net et pertes », et options nouvelles de ``recommend`` et
``report`` (cahier ``docs/RENDEMENT_NET.md``, §6).

La ligne de commande (:mod:`brvm_alpha.cli`) déclare ces commandes par :func:`ajouter_parseurs` et
:func:`ajouter_options`, puis les lance par :func:`cmd_plan` et :func:`cmd_suivi`. Elles suivent le contrat de
``cli`` : codes de retour de :mod:`brvm_alpha.erreurs` (jamais 3), un seul objet JSON avec ``--format json``, écritures
atomiques, mode embarqué (dossiers obligatoires, aucune écriture dans l'arbre du code).

* ``plan`` : écran « Mon plan » (texte, Markdown ou JSON), cache ``<données>/profil/plan_cache.json`` ; ``plan
  --enregistrer`` écrit ``<données>/profil/plan.json`` ; ``plan grille`` : grille du courtier ; ``plan questions`` :
  les 8 questions à envoyer au courtier ;
* ``suivi`` : suivi sur papier (``<données>/suivi/<nom>/``) : ``demarrer``, ``maj``, ``bulletin``, ``saisir``,
  ``revue``, ``declarer`` (dépôt de développement seulement), ``verifier``, ``exporter``.

Sans option nouvelle, ``recommend`` et ``report`` reçoivent exactement les mêmes arguments qu'avant
(:func:`options_recommend` rend un dictionnaire vide). Aucune commande n'envoie de requête réseau ; aucune ne lance
``validate`` ni ``backtest``. La déclaration du suivi n'est signée, et le registre des essais n'est complété, que par
la commande ``suivi declarer`` lancée par l'utilisateur lui-même.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import csv
import io
import json
import os
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Any, Iterator, Mapping

import pandas as pd

from brvm_alpha import erreurs, paths
from brvm_alpha.erreurs import DonneesAbsentes, SaisieInvalide

BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."
#: Capital du plan quand rien n'est enregistré (§6).
CAPITAL_DEFAUT = 10_000_000.0
#: Portefeuilles tenus par le moteur (journal du témoin), sans carnet.
NOMS_MOTEUR = ("REF-S2", "N")
#: Portefeuilles privés de l'utilisateur : jamais copiés par ``suivi exporter`` sans ``--avec-moi``.
PRIVES = ("MOI",)
#: Essais sur papier exécutés en mode « test » (§F12) ; les autres carnets, en mode « limite ».
MODE_TEST = ("E-C", "E-D")
STATUTS_GRILLE = {"suppose": "supposé", "ecrit": "grille écrite", "avis": "avis d'opéré"}
INVESTISSEURS = {"physique": "personne physique résidente", "morale": "personne morale"}
DECISIONS = ("garder", "ne-plus-acheter", "reduire")
#: Options de ``plan grille`` : (option, champ de la grille, nature).
CHAMPS_GRILLE = (("courtage", "courtage", "taux"), ("taxe", "taxe_courtage", "taux"),
                 ("min_ordre", "courtage_min_par_ordre", "montant"), ("garde", "garde", "taux"),
                 ("par_ligne", "tenue_par_ligne", "montant"), ("forfait", "forfait_compte", "montant"),
                 ("taxe_frais", "taxe_frais_annuels", "taux"), ("garde_min", "garde_minimum", "montant"),
                 ("encaissement", "encaissement_taux", "taux"), ("encaissement_fixe", "encaissement_fixe", "montant"),
                 ("transfert", "transfert_par_ligne", "montant"))


def _cli() -> Any:
    from brvm_alpha import cli

    return cli


# ---------------------------------------------------------------------------
# Saisies
# ---------------------------------------------------------------------------


def parse_taux(value: Any) -> float:
    """Taux en pourcentage, virgule ou point : « 0,5 » ou « 0,5 % » → 0,005 (``ValueError`` sinon)."""
    s = str(value or "").strip().replace(" ", "").replace("\xa0", "").replace(" ", "")
    s = s[:-1] if s.endswith("%") else s
    try:
        x = float(s.replace(",", "."))
    except ValueError:
        raise ValueError(f"taux invalide : {value!r} (en pourcentage : 0,5 pour 0,5 %)") from None
    if not (x == x) or x < 0 or x > 100:
        raise ValueError(f"taux invalide : {value!r} (de 0 à 100, en pourcentage)")
    return x / 100.0


def parse_taux_reserve(value: Any) -> float:
    """Taux net de la réserve, en pourcentage : comme :func:`parse_taux`, dans la plage des réglages (``reserve.taux_max``,
    15 % par défaut). Au-delà : refus (``ValueError``), jamais un taux ignoré puis affiché « taux inconnu »."""
    from brvm_alpha.rendement import reglages as RG

    x = parse_taux(value)
    tmax = float(RG.lire(None, "reserve.taux_max", 0.15))
    if x > tmax + 1e-12:
        raise ValueError(f"taux de la réserve : {RG.pct(x, 2)} est hors de la plage acceptée (de 0 à {RG.pct(tmax, 0)})")
    return x


def parse_montant(value: Any) -> float:
    """Montant en FCFA, zéro compris (« 0 », « 5000 », « 2,5k ») ; ``ValueError`` sinon."""
    s = str(value or "").strip()
    if s.replace(",", ".").replace(" ", "") in ("0", "0.0", "0.00"):
        return 0.0
    return _cli().parse_capital(s)


def parse_perte(value: Any) -> float | str:
    """Ce que j'accepte de risquer : montant en FCFA (« 1000000 », « 1M ») ou part du capital (« 10 % ») ; une part
    est rendue sous la forme « 10% » (lue par ``rendement.construire``)."""
    s = str(value or "").strip().replace(" ", "").replace("\xa0", "")
    if s.endswith("%"):
        p = parse_taux(s)
        if p <= 0:
            raise ValueError("part du capital : strictement positive")
        return f"{round(p * 100, 6):g}%"
    x = _cli().parse_capital(s)
    if x < 1:
        raise ValueError("montant de la perte acceptée : au moins 1 FCFA (ou une part : « 10 % »)")
    return x


def controler_perte(perte: Any, capital: Any) -> None:
    """Même règle que le formulaire de l'interface : ce que j'accepte de risquer ne dépasse pas le capital total
    (``SaisieInvalide``, code 2). Une part (« 10 % ») est toujours dans le capital."""
    if isinstance(perte, (int, float)) and capital and float(perte) > float(capital) + 0.5:
        raise SaisieInvalide(f"refusé : ce que j'accepte de risquer ({_cli().fr_num(perte, 0)} FCFA) dépasse le capital "
                             f"total ({_cli().fr_num(capital, 0)} FCFA) ; sans --perte-toleree, la table de choix "
                             "montre aussi « tout en actions »")


def _type(fn: Any) -> Any:
    def conv(value: str) -> Any:
        try:
            return fn(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc

    conv.__name__ = getattr(fn, "__name__", "valeur")
    return conv


def _mois(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise ValueError(f"nombre de mois entier attendu : {value!r}") from None
    if not 1 <= n <= 600:
        raise ValueError("nombre de mois : de 1 à 600")
    return n


_taux_arg = _type(parse_taux)
_taux_reserve_arg = _type(parse_taux_reserve)
_montant_arg = _type(parse_montant)
_perte_arg = _type(parse_perte)
_mois_arg = _type(_mois)


# ---------------------------------------------------------------------------
# Dossiers et fichiers
# ---------------------------------------------------------------------------


def dossier_profil() -> Path:
    """``<données>/profil`` (grille, plan, cache de l'écran, signature)."""
    return paths.DATA_DIR / "profil"


def dossier_suivi() -> Path:
    """``<données>/suivi`` (journaux du suivi sur papier)."""
    from brvm_alpha import suivi

    return suivi.dossier_suivi(None)


def dossier_declaration() -> Path:
    """``reports/suivi_S2`` du dépôt (déclaration signée, suivie par git)."""
    return paths.REPO_ROOT / "reports" / "suivi_S2"


def registre_des_essais() -> Path:
    """``reports/trials.parquet`` du dépôt (registre des essais)."""
    return paths.REPO_ROOT / "reports" / "trials.parquet"


def _aujourd_hui() -> pd.Timestamp:
    t = _cli().now_utc()
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.tz_localize(None).normalize()


def _ecrire_json(chemin: Path, obj: Any) -> Path:
    from brvm_alpha import fichiers

    cli = _cli()
    paths.verifier_ecriture(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(cli.to_jsonable(obj), ensure_ascii=False, indent=1) + "\n"
    return fichiers.ecrire_atomique(chemin, texte)


def _ecrire_texte(chemin: str | Path, texte: str) -> Path:
    from brvm_alpha import fichiers

    p = Path(chemin)
    paths.verifier_ecriture(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    return fichiers.ecrire_atomique(p, texte)


def lire_plan(dossier: str | Path | None = None) -> dict[str, Any]:
    """Plan enregistré (``<données>/profil/plan.json``) ; ``{}`` s'il n'existe pas ; ``SaisieInvalide`` s'il est
    illisible (aucun calcul silencieux)."""
    p = (Path(dossier) if dossier is not None else dossier_profil()) / "plan.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SaisieInvalide(f"refusé : plan enregistré illisible : {p} ({exc})") from exc
    if not isinstance(d, dict):
        raise SaisieInvalide(f"refusé : plan enregistré illisible : {p} (un dictionnaire est attendu)")
    return d


def _ok(b: Any) -> bool:
    return isinstance(b, Mapping) and not b.get("erreur")


@contextlib.contextmanager
def _saisie(quoi: str = "") -> Iterator[None]:
    """Refus d'une saisie par le module (``ValueError`` : doublon au carnet, nom invalide, grille illisible…) rendu
    comme une saisie invalide (code 2). Seules les opérations qui portent une saisie de l'utilisateur sont
    enveloppées : un défaut du calcul garde son propre code."""
    try:
        yield
    except SaisieInvalide:
        raise
    except ValueError as exc:
        msg = str(exc).strip() or type(exc).__name__
        if not msg.lower().startswith(("refusé", "échec")):
            msg = "refusé : " + (f"{quoi} : " if quoi else "") + msg
        raise SaisieInvalide(msg) from exc


def _panels(panel_dir: Any = None) -> Mapping[str, Any]:
    """Panels du moteur (``strategy.build_panels``) ; panel absent : :class:`DonneesAbsentes` (code 1)."""
    from brvm_alpha.strategy import build_panels

    cli = _cli()
    pdir = Path(panel_dir) if panel_dir else cli.DEFAULT_PANEL_DIR
    if not (pdir / "equities.parquet").exists():
        raise DonneesAbsentes("échec : " + cli.panel_missing_message(panel_dir))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_panels(pdir)


def _dans(p: Path, base: Path) -> bool:
    for a, b in ((Path(os.path.abspath(p)), Path(os.path.abspath(base))),
                 (Path(os.path.realpath(p)), Path(os.path.realpath(base)))):
        try:
            a.relative_to(b)
            return True
        except ValueError:
            continue
    return False


def _fichier_lu(value: Any, quoi: str) -> Path:
    """Fichier donné en option et lu par la commande : chemin résolu (mode embarqué : depuis les données, et seulement
    dans les dossiers de données, de rapports ou temporaire) ; absent : :class:`DonneesAbsentes`."""
    p = Path(os.path.abspath(paths.resoudre_chemin_option(value, base="donnees")))
    if paths.est_embarque() and not any(_dans(p, b) for b in (paths.DATA_DIR, paths.REPORTS_DIR,
                                                              Path(tempfile.gettempdir()))):
        raise SaisieInvalide(f"refusé : {quoi} {p} est hors des dossiers permis en mode embarqué (données "
                             f"{paths.DATA_DIR}, rapports {paths.REPORTS_DIR}, fichiers temporaires).")
    if not p.is_file():
        raise DonneesAbsentes(f"échec : {quoi} introuvable : {p}")
    return p


# ---------------------------------------------------------------------------
# Options nouvelles de recommend et report
# ---------------------------------------------------------------------------


_AIDE_GRILLE = ("tarif du courtier : ma_sgi (grille enregistrée par « plan grille »), central (tarif supposé, défaut), "
                "ou un fichier YAML de grille")


def ajouter_options(p: argparse.ArgumentParser, commande: str) -> None:
    """Options du module sur ``recommend`` ou ``report`` (§6) ; toutes éteintes par défaut."""
    g = p.add_argument_group("rendement net et pertes (options éteintes par défaut)")
    g.add_argument("--grille", default=None, metavar="ma_sgi|central|FICHIER", help=_AIDE_GRILLE)
    g.add_argument("--perte-toleree", dest="perte_toleree", type=_perte_arg, default=None, metavar="MONTANT|P%",
                   help="ce que j'accepte de risquer sur 12 mois (FCFA, ou « 10 %% » du capital) : l'ordre est celui du "
                        "montant en actions calculé pour une année comme 2018 ; ce n'est pas une limite")
    g.add_argument("--taux-reserve", dest="taux_reserve", type=_taux_reserve_arg, default=None, metavar="T",
                   help="taux net de la réserve, en %% par an (« 3 » ou « 3,5 ») : affiché à part, jamais déduit de la "
                        "perte estimée")
    g.add_argument("--sans-rendement", dest="sans_rendement", action="store_true",
                   help="n'ajoute pas la clé rendement_net (calcul plus court)")
    if commande != "recommend":
        return
    g.add_argument("--arrondi", choices=("bas", "restes"), default="bas",
                   help="arrondi des quantités : bas (défaut, règle testée) ou restes (plus forts restes, écart E-A)")
    g.add_argument("--forcer", action="store_true",
                   help="avec --arrondi restes : l'emploie aussi sur un tarif supposé (sur papier)")
    g.add_argument("--apport", type=_cli()._capital_arg, default=None, metavar="MONTANT",
                   help="argent frais apporté, compris dans --cash (écart E-B) : achats sans vente")
    g.add_argument("--completer", action="store_true", help="complète un ordre servi en partie (écart E-B)")
    g.add_argument("--reinvestir", action="store_true", help="réinvestissement de fin de mois (essai E-D, sur papier)")
    g.add_argument("--continuite", action="store_true", help="continuité des données (essai E-C, sur papier)")
    g.add_argument("--suivi", default=None, metavar="NOM",
                   help="portefeuille suivi (carnet <données>/suivi/NOM) : titres, liquidités et mémoire de la règle")


def _grille_option(value: Any) -> str:
    """Option ``--grille`` contrôlée avant le calcul : grille enregistrée présente et lisible, ou fichier lisible."""
    from brvm_alpha.rendement import grille as G

    v = str(value or "").strip()
    if v in ("", "central"):
        return "central"
    if v == "ma_sgi":
        if not G.enregistree():
            raise SaisieInvalide("refusé : --grille ma_sgi : aucune grille enregistrée (la saisir avec « python -m "
                                 "brvm_alpha plan grille --courtage … »)")
        with _saisie("--grille ma_sgi"):
            G.charger()
        return v
    p = _fichier_lu(v, "--grille")
    with _saisie("--grille"):
        G.lire_fichier(p)
    return str(p)


def options_recommend(args: argparse.Namespace, commande: str = "recommend") -> dict[str, Any]:
    """Paramètres nommés de ``recommend`` pour les options du module ; ``{}`` sans option (appel inchangé)."""
    kw: dict[str, Any] = {}
    if getattr(args, "grille", None) not in (None, ""):
        kw["grille"] = _grille_option(args.grille)
    if getattr(args, "perte_toleree", None) is not None:
        controler_perte(args.perte_toleree, getattr(args, "capital", None))
        kw["perte_toleree"] = args.perte_toleree
    if getattr(args, "taux_reserve", None) is not None:
        kw["taux_reserve"] = args.taux_reserve
    if getattr(args, "sans_rendement", False):
        if "perte_toleree" in kw or "taux_reserve" in kw:
            raise SaisieInvalide("refusé : --perte-toleree et --taux-reserve demandent le rendement net : retirer "
                                 "--sans-rendement")
        kw["rendement"] = False
    if commande != "recommend":
        return kw
    if getattr(args, "arrondi", "bas") != "bas":
        kw["arrondi"] = args.arrondi
    if getattr(args, "forcer", False):
        if kw.get("arrondi") != "restes":
            raise SaisieInvalide("refusé : --forcer ne sert qu'avec --arrondi restes")
        kw["forcer"] = True
    if getattr(args, "apport", None) is not None:
        cash = getattr(args, "cash", None)
        if cash is None and not getattr(args, "suivi", None):
            raise SaisieInvalide("refusé : --apport : liquidités réelles nécessaires (--cash, qui comprend l'apport, "
                                 "ou --suivi)")
        if cash is not None and float(cash) + 1.0 < float(args.apport):
            raise SaisieInvalide("refusé : --apport supérieur aux liquidités réelles : --cash doit comprendre l'apport")
        kw["apport"] = float(args.apport)
    for cle in ("completer", "reinvestir", "continuite"):
        if getattr(args, cle, False):
            kw[cle] = True
    if kw.get("arrondi") == "restes" and not kw.get("forcer"):
        # Refus avant le calcul (l'ordre prend plusieurs secondes) : même règle que liquidites.arrondi_restes.
        from brvm_alpha.rendement import grille as G

        with _saisie("--grille"):
            gr = G.resoudre(kw.get("grille"))
        if G.statut_global(gr) == G.SUPPOSE:
            raise SaisieInvalide("refusé : --arrondi restes : la grille du courtier est supposée (grille absente, tarif "
                                 "central ou statut « supposé ») ; option --forcer pour un emploi sur papier")
    if getattr(args, "suivi", None):
        kw.update(_options_suivi(str(args.suivi), getattr(args, "panel_dir", None)))
    return kw


def _carnet_existant(nom: str, D: Path | None = None) -> Any:
    from brvm_alpha.suivi import carnet as cn

    if nom in NOMS_MOTEUR:
        raise SaisieInvalide(f"refusé : {nom} est tenu par le moteur (journal du témoin, sans carnet) ; les carnets "
                             "sont ceux de PLAN, MOI, E-C et E-D")
    with _saisie("portefeuille"):
        c = cn.ouvrir(nom, D if D is not None else dossier_suivi(), creer=False)
    if not c.fichier.exists():
        raise DonneesAbsentes(f"échec : portefeuille suivi « {nom} » introuvable ({c.fichier}) : le démarrer avec "
                              f"python -m brvm_alpha suivi demarrer --nom {nom}")
    return c


def _grille_du_mandat(mandat: Mapping[str, Any] | None, profil: Path | None = None) -> Any:
    from brvm_alpha.rendement import grille as G

    if (mandat or {}).get("grille") == "ma_sgi" and G.enregistree(profil):
        with _saisie("grille enregistrée"):
            return G.charger(profil)
    return G.defaut()


def _cost_model(g: Any) -> tuple[Any, float]:
    from brvm_alpha import settings
    from brvm_alpha.rendement import grille as G

    return G.vers_cost_model(g, settings.cost_scenario("central"))


def _options_suivi(nom: str, panel_dir: Any) -> dict[str, Any]:
    """``recommend --suivi NOM`` : mémoire du carnet et état de la semaine pour les feux (§F13 a, §C de la fiche)."""
    from brvm_alpha.suivi import bulletin as BU
    from brvm_alpha.suivi import declaration as DE

    c = _carnet_existant(nom)
    D = dossier_suivi()
    m = c.memoire()
    mandat = c.mandat() or {}
    rv = None
    try:
        P = _panels(panel_dir)
        g = _grille_du_mandat(mandat)
        cm, forfait = _cost_model(g)
        lignes = BU.semaines_du_journal(nom, D)
        T = float(lignes[-1].get("valeur_titres") or 0) if lignes else 0.0
        rv = BU.rendez_vous(m.get("titres") or {}, P, _aujourd_hui(), costs=cm, valeur_titres=T, forfait=forfait,
                            dernier_prelevement=_dernier_prelevement(c))
    except DonneesAbsentes:
        rv = None
    ch = BU.verifier_semaines(nom, D)
    sem = BU.semaine_pour_feux(BU.semaines_du_journal(nom, D), papier=mandat.get("mode") != "reel",
                               aujourd_hui=_aujourd_hui(), chaine_ok=bool(ch["chaine_ok"] and c.verifier()["chaine_ok"]),
                               rendez_vous=rv, operations=c.operations())
    return {"memoire": m, "suivi": {"semaine": sem, "declaration": DE.verifier(dossier_declaration(),
                                                                               registre=_registre_si_present()),
                                    "alertes_ouvertes": []}}


def _registre_si_present() -> Path | None:
    r = registre_des_essais()
    return r if r.exists() else None


def _dernier_prelevement(c: Any) -> Any:
    fr = c.mouvements(types=("frais",))
    if fr:
        return fr[-1]["date"]
    md = c.mandat()
    return md["date"] if md else None


# ---------------------------------------------------------------------------
# Analyseur : plan et suivi
# ---------------------------------------------------------------------------


def ajouter_parseurs(sub: Any) -> None:
    """Commandes ``plan`` et ``suivi`` (§6), avec leurs sous-commandes."""
    cli = _cli()
    pl = sub.add_parser("plan", help="écran « Mon plan » : frais, ce que j'accepte de risquer, réserve (étude)",
                        description="Écran « Mon plan » (étude seulement) : ce que prend votre courtier (SGI), ce que "
                                    "vous acceptez de risquer sur 12 mois, où dort le reste. Montants arrondis ; le "
                                    "détail au franc est dans --format md et json. Écrit <données>/profil/"
                                    "plan_cache.json ; --enregistrer écrit plan.json. Sous-commandes : « plan grille » "
                                    "(grille du courtier), « plan questions » (les 8 questions à lui envoyer).")
    pl.add_argument("--capital", type=cli._capital_arg, default=None, metavar="K",
                    help="capital total en FCFA (défaut : celui du plan enregistré, sinon 10 000 000)")
    pl.add_argument("--perte-toleree", dest="perte_toleree", type=_perte_arg, default=None, metavar="MONTANT|P%",
                    help="ce que j'accepte de risquer sur 12 mois (FCFA ou « 10 %% ») ; absent : table de choix")
    pl.add_argument("--taux-reserve", dest="taux_reserve", type=_taux_reserve_arg, default=None, metavar="T",
                    help="taux net de la réserve, en %% par an (supposé tant qu'il n'est pas relevé)")
    pl.add_argument("--besoin-dans", dest="besoin_dans", type=_mois_arg, default=None, metavar="MOIS",
                    help="dans combien de mois vous aurez besoin de cet argent (gardé dans le plan ; durée non "
                         "calculée dans cette version)")
    pl.add_argument("--grille", default=None, metavar="ma_sgi|central|FICHIER",
                    help="tarif du courtier (défaut : ma_sgi si une grille est enregistrée, sinon central)")
    pl.add_argument("--tranches", type=cli._positive_int, default=None, metavar="N",
                    help="entrée en plusieurs fois : non disponible dans cette version (seul 1 est accepté)")
    pl.add_argument("--format", choices=("texte", "md", "json"), default="texte", help="format (défaut : texte)")
    pl.add_argument("--sortie", default=None, metavar="CHEMIN", help="écrit l'écran dans ce fichier")
    pl.add_argument("--date", type=cli._date_arg, default=None, metavar="AAAA-MM-JJ",
                    help="date de décision (défaut : dernière séance du panel)")
    pl.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")
    cli._add_notes_root(pl)
    cli._add_notes_au(pl)
    pl.add_argument("--sans-notes", action="store_true", help="ignore les notes de l'analyste")
    cli._add_history_option(pl)
    pl.add_argument("--enregistrer", action="store_true",
                    help="enregistre capital, perte acceptée, taux de la réserve, besoin et tarif dans plan.json")
    pls = pl.add_subparsers(dest="plan_cmd", required=False, title="sous-commandes (facultatives)",
                            metavar="[grille | questions]")
    pg = pls.add_parser("grille", help="grille du courtier : afficher, saisir, comparer",
                        description="Grille du courtier (SGI), enregistrée dans <données>/profil/grille_sgi.yaml (jamais "
                                    "dans le dépôt). Taux en % (« 0,8 » = 0,8 %), montants en FCFA. Une valeur reste "
                                    "« supposé » tant qu'elle n'a pas de source (--statut ecrit ou avis exige "
                                    "--source). Sans saisie : affiche la grille.")
    pg.add_argument("--afficher", action="store_true", help="affiche la grille (défaut sans saisie)")
    pg.add_argument("--comparer", action="store_true",
                    help="frais de chaque grille sur les lignes de l'ordre (cache de « plan », sinon ordre recalculé)")
    pg.add_argument("--capital", type=cli._capital_arg, default=argparse.SUPPRESS, metavar="K",
                    help="capital de la comparaison (défaut : celui du plan, sinon 10 000 000)")
    for opt, champ, nature in CHAMPS_GRILLE:
        flag = "--" + opt.replace("_", "-")
        pg.add_argument(flag, dest="g_" + opt, type=_taux_arg if nature == "taux" else _montant_arg, default=None,
                        metavar="T" if nature == "taux" else "M",
                        help=f"{champ.replace('_', ' ')} ({'en %%' if nature == 'taux' else 'en FCFA'})")
    pg.add_argument("--investisseur", choices=tuple(INVESTISSEURS), default=None,
                    help="statut de l'investisseur : physique (résident) ou morale")
    pg.add_argument("--pays", default=None, metavar="P", help="pays de résidence (texte)")
    pg.add_argument("--source", default=None, metavar="TEXTE", help="source des valeurs saisies (grille écrite, avis)")
    pg.add_argument("--statut", choices=tuple(STATUTS_GRILLE), default=None,
                    help="statut des valeurs saisies : suppose (défaut sans source), ecrit (défaut avec source), avis")
    pg.add_argument("--format", choices=("texte", "json"), default=argparse.SUPPRESS, help="format (défaut : texte)")
    pg.add_argument("--panel-dir", default=argparse.SUPPRESS, metavar="DOSSIER", help="panel (défaut : data/panel)")
    pq = pls.add_parser("questions", help="les 8 questions à envoyer à votre courtier",
                        description="Les 8 questions à envoyer à votre courtier (SGI), prêtes à copier.")
    pq.add_argument("--format", choices=("texte", "json"), default=argparse.SUPPRESS, help="format (défaut : texte)")

    sv = sub.add_parser("suivi", help="suivi sur papier (S2) : journaux, bulletin de la semaine, déclaration",
                        description="Suivi sur papier, sans argent réel (S2, à partir du 01/12/2026). Journaux dans "
                                    "<données>/suivi/<nom>/ (ajout seul, chaînes d'empreintes). REF-S2 : le panier de "
                                    "référence (témoin) ; N : essai avec les notes (s'il est déclaré) ; PLAN, MOI, E-C, "
                                    "E-D : carnets. Aucune vente automatique : un feu ouvre une revue.")
    svs = sv.add_subparsers(dest="suivi_cmd", required=True, title="actions", metavar="ACTION")

    def fmt(p: argparse.ArgumentParser, *choix: str) -> None:
        p.add_argument("--format", choices=choix or ("texte", "json"), default="texte", help="format (défaut : texte)")

    d = svs.add_parser("demarrer", help="démarre un carnet (mandat puis apport)",
                       description="Démarre le carnet d'un portefeuille suivi : mandat (capital, mode, tarif, ce que "
                                   "j'accepte de risquer) puis apport du capital en liquidités, datés d'aujourd'hui.")
    d.add_argument("--nom", required=True, metavar="NOM", help="nom du portefeuille (MOI, PLAN…)")
    d.add_argument("--capital", type=cli._capital_arg, default=None, metavar="K",
                   help="capital en FCFA (défaut : celui du plan, sinon 10 000 000)")
    d.add_argument("--mode", choices=("papier", "reel"), default="papier", help="papier (défaut) ou reel")
    fmt(d)
    m = svs.add_parser("maj", help="met à jour les portefeuilles suivis (ligne de la semaine)",
                       description="Met à jour les journaux : REF-S2 (témoin, moteur existant), N s'il est déclaré, et "
                                   "les carnets (exécution sur papier des ordres en attente). Calcul local, aucune "
                                   "requête. Rien n'est écrit tant que le bulletin du départ n'est pas dans le panel. "
                                   "Une erreur d'un portefeuille est consignée et la mise à jour continue (code non nul "
                                   "à la fin).")
    m.add_argument("--nom", default=None, metavar="NOM", help="un seul portefeuille (défaut : tous)")
    m.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")
    cli._add_notes_root(m)
    fmt(m)
    b = svs.add_parser("bulletin", help="bulletin de la semaine d'un portefeuille (lecture seule)",
                       description="Bulletin de la semaine (texte, Markdown ou JSON) à partir du journal : valeur, d'où "
                                   "vient chaque franc, trois feux, prochains rendez-vous. Lecture seule.")
    b.add_argument("--nom", default=None, metavar="NOM", help="portefeuille (défaut : REF-S2)")
    b.add_argument("--sortie", default=None, metavar="CHEMIN", help="écrit le bulletin dans ce fichier")
    b.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")
    fmt(b, "texte", "md", "json")
    s = svs.add_parser("saisir", help="apport, retrait ou avis d'opéré dans un carnet",
                       description="Ajoute au carnet un apport, un retrait (datés d'aujourd'hui) ou les exécutions d'un "
                                   "avis d'opéré (CSV : date, symbole, sens, titres, prix, courtage, taxe, commissions ou "
                                   "brvm et dcbr, autres_frais, total, cours_reference ; portefeuille réel). Une grille "
                                   "corrigée n'est enregistrée qu'avec --confirmer-grille.")
    s.add_argument("--nom", required=True, metavar="NOM", help="portefeuille (carnet)")
    sg = s.add_mutually_exclusive_group(required=True)
    sg.add_argument("--fichier", default=None, metavar="AVIS.csv", help="avis d'opéré (CSV)")
    sg.add_argument("--apport", type=cli._capital_arg, default=None, metavar="M", help="apport en FCFA")
    sg.add_argument("--retrait", type=cli._capital_arg, default=None, metavar="M", help="retrait en FCFA")
    s.add_argument("--confirmer-grille", dest="confirmer_grille", action="store_true",
                   help="enregistre la grille corrigée proposée par l'avis d'opéré")
    fmt(s)
    r = svs.add_parser("revue", help="consigne la décision d'une revue (aucun ordre n'est créé)",
                       description="Consigne au carnet la décision écrite d'une revue ouverte par un feu. Aucune vente, "
                                   "aucun ordre : « reduire » se fait, si vous le décidez, par ordres à cours limité sur "
                                   "plusieurs séances, saisis par vous.")
    r.add_argument("--nom", required=True, metavar="NOM", help="portefeuille (carnet)")
    r.add_argument("--alerte", required=True, metavar="ID", help="identifiant de l'alerte ou du feu")
    r.add_argument("--decision", required=True, choices=DECISIONS, help="garder, ne-plus-acheter ou reduire")
    r.add_argument("--texte", required=True, metavar="TEXTE", help="réponses aux questions de la revue")
    fmt(r)
    dc = svs.add_parser("declarer", help="déclaration du suivi : modèle, signature, registre (dépôt de développement)",
                        description="Déclaration du suivi sur papier (§8) : --modele donne le projet à remplir ; "
                                    "--fichier F --signer INITIALES le signe dans reports/suivi_S2/declaration.jsonl "
                                    "(ajout seul) ; --registre --confirmer \"J'INSCRIS AU REGISTRE\" ajoute ses lignes "
                                    "au registre des essais. Dépôt de développement seulement (code 2 ailleurs). "
                                    "Initiales ou pseudonyme seulement, jamais un nom complet.")
    dg = dc.add_mutually_exclusive_group()
    dg.add_argument("--modele", action="store_true", help="projet de déclaration (JSON), à remplir")
    dg.add_argument("--fichier", default=None, metavar="F", help="articles répondus (JSON) à signer")
    dc.add_argument("--signer", default=None, metavar="INITIALES",
                    help="initiales ou pseudonyme (défaut : <données>/profil/signature.json)")
    dc.add_argument("--registre", action="store_true", help="inscrit la déclaration au registre des essais")
    dc.add_argument("--confirmer", default=None, metavar="PHRASE", help="phrase exacte : J'INSCRIS AU REGISTRE")
    dc.add_argument("--sortie", default=None, metavar="CHEMIN", help="avec --modele : écrit le projet dans ce fichier")
    fmt(dc)
    v = svs.add_parser("verifier", help="vérifie les chaînes de la déclaration et des journaux",
                       description="Vérifie les chaînes d'empreintes de la déclaration, des journaux hebdomadaires et "
                                   "des carnets (lecture seule). Code 1 si une chaîne est rompue.")
    fmt(v)
    e = svs.add_parser("exporter", help="copie les journaux du suivi (pour un commit aux points d'étape)",
                       description="Copie <données>/suivi dans un dossier nouveau (ou vide), d'un bloc. Le portefeuille "
                                   "privé MOI n'est copié qu'avec --avec-moi.")
    e.add_argument("--sortie", dest="dossier_sortie", required=True, metavar="DOSSIER", help="dossier de destination")
    e.add_argument("--avec-moi", dest="avec_moi", action="store_true", help="copie aussi MOI (privé)")
    fmt(e)


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def cmd_plan(args: argparse.Namespace) -> int:
    sc = getattr(args, "plan_cmd", None)
    if sc == "grille":
        return _plan_grille(args)
    if sc == "questions":
        return _plan_questions(args)
    return _plan_ecran(args)


def _notes(args: argparse.Namespace) -> tuple[Any, Any]:
    cli = _cli()
    if getattr(args, "sans_notes", False):
        return False, None
    store: Any = None
    if getattr(args, "racine", None):
        from brvm_alpha.notes.store import NoteStore

        store = NoteStore(cli.notes_root_arg(args.racine))
    known = cli.notes_instant(getattr(args, "date", None), getattr(args, "notes_au", None),
                              getattr(args, "panel_dir", None))
    return store, known


def _plan_saisi(args: argparse.Namespace, capital: float) -> dict[str, Any]:
    nouveau: dict[str, Any] = {"capital": float(capital)}
    if args.perte_toleree is not None:
        nouveau["perte_toleree"] = args.perte_toleree
    if args.taux_reserve is not None:
        nouveau.update({"taux_reserve": float(args.taux_reserve), "statut_taux": "supposé",
                        "date_taux": _aujourd_hui().date().isoformat()})
    if args.besoin_dans is not None:
        nouveau["besoin_dans_mois"] = int(args.besoin_dans)
    if args.grille not in (None, ""):
        nouveau["grille"] = "ma_sgi" if args.grille == "ma_sgi" else ("central" if args.grille == "central" else "fichier")
    return nouveau


def _empreinte_ordre(od: Mapping[str, Any]) -> str:
    from brvm_alpha import suivi

    return suivi.empreinte([(l.get("symbole"), l.get("sens"), l.get("quantite"), l.get("prix_limite"))
                            for l in (od.get("lignes") or [])])


def cache_du_plan(o: Any, *, t: Any, capital: float, grille: str, perte_toleree: Any,
                  maintenant: Any = None) -> dict[str, Any]:
    """Contenu de ``<données>/profil/plan_cache.json`` pour l'ordre ``o`` (clé ``rendement_net`` calculée) : écran
    « Mon plan », ``rendement_net``, ordre sans sa clé ``rendement_net``, date du bulletin et empreinte de l'ordre. Sert
    à la commande ``plan`` et au calcul lancé depuis l'interface (carte « Mon plan » du Tableau de bord)."""
    rn = getattr(o, "rendement_net", None) or {}
    od = o.to_dict() if hasattr(o, "to_dict") else {}
    calcule = pd.Timestamp(maintenant) if maintenant is not None else _cli().now_utc()
    return {"version": 1, "bandeau": BANNER, "calcule_utc": calcule.isoformat(),
            "asof": str(od.get("asof") or t)[:10], "capital": float(capital),
            "capital_ordre": float(od.get("valeur_portefeuille") or od.get("capital") or capital),
            "grille": grille or "central", "perte_toleree": perte_toleree,
            "empreinte_ordre": _empreinte_ordre(od), "plan": rn.get("plan"), "rendement_net": rn,
            "ordre": {k: v for k, v in od.items() if k != "rendement_net"}}


def _plan_ecran(args: argparse.Namespace) -> int:
    from brvm_alpha.portfolio import recommend as rec
    from brvm_alpha.rendement import grille as G
    from brvm_alpha.rendement import plan as PL

    cli = _cli()
    t = cli._decision_date(args.date, args.panel_dir)
    if cli.in_s1(t):
        raise SaisieInvalide(cli.s1_refusal(t, "l'écran « Mon plan »"))
    if args.tranches not in (None, 1):
        raise SaisieInvalide("refusé : --tranches : l'entrée en plusieurs fois (F15) n'est pas disponible dans cette "
                             "version ; aucune option ne la simule (seul --tranches 1 est accepté)")
    hist = cli.check_history(args, "l'écran « Mon plan »", refuse=True)  # avant toute écriture
    pe = lire_plan()
    capital = float(args.capital or pe.get("capital") or CAPITAL_DEFAUT)
    controler_perte(args.perte_toleree, capital)
    opt_g = args.grille if args.grille not in (None, "") else (pe.get("grille") if pe.get("grille") in ("ma_sgi",)
                                                                else None)
    if opt_g is None and G.enregistree():
        opt_g = "ma_sgi"
    grille_kw = _grille_option(opt_g) if opt_g not in (None, "") else "central"
    chemin_plan = None
    if args.enregistrer:
        pe = {**pe, **_plan_saisi(args, capital), "version": 1, "enregistre_utc": cli.now_utc().isoformat(),
              "bandeau": BANNER}
        chemin_plan = _ecrire_json(dossier_profil() / "plan.json", pe)
    store, known = _notes(args)
    kw: dict[str, Any] = {"grille": grille_kw, "plan_enregistre": pe or None}
    if args.perte_toleree is not None:
        kw["perte_toleree"] = args.perte_toleree
    if args.taux_reserve is not None:
        kw["taux_reserve"] = args.taux_reserve
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        o = rec.recommend(t, capital, notes_store=store, notes_known_at=known, panel_dir=args.panel_dir,
                          index_evaluation=False, today=cli.now_utc(), **kw)
    if hist.get("avertissement"):
        cli._say(f"⚠ {hist['avertissement']}")
    rn = getattr(o, "rendement_net", None) or {}
    if not _ok(rn) or not _ok(rn.get("plan")):
        motif = (rn.get("plan") or {}).get("erreur") if isinstance(rn.get("plan"), Mapping) else rn.get("erreur")
        raise RuntimeError(f"écran « Mon plan » non calculé ({motif or 'module « Rendement net et pertes » en échec'})")
    od = o.to_dict() if hasattr(o, "to_dict") else {}
    duree = None
    besoin = args.besoin_dans if args.besoin_dans is not None else pe.get("besoin_dans_mois")
    if besoin is not None:
        duree = {"besoin_dans_mois": int(besoin), "statut": "non calculé",
                 "mention": "Durée : non calculée dans cette version (F14) ; votre besoin est gardé dans le plan."}
    cache = cache_du_plan(o, t=t, capital=capital, grille=opt_g or "central",
                          perte_toleree=args.perte_toleree if args.perte_toleree is not None else pe.get("perte_toleree"))
    chemin_cache = _ecrire_json(dossier_profil() / "plan_cache.json", cache)
    meta = {"date": str(od.get("asof") or t)[:10], "capital": capital, "grille": opt_g or "central",
            "plan_cache": str(chemin_cache), "plan_enregistre": str(chemin_plan) if chemin_plan else None,
            "duree": duree, **cli._history_keys(hist)}
    if args.format == "json":
        payload = {"ok": True, **meta, "rendement_net": rn, "bandeau": BANNER}
        out = json.dumps(cli.to_jsonable(payload), ensure_ascii=False, indent=1) + "\n"
    else:
        out = PL.rendre_plan(rn["plan"], "md" if args.format == "md" else "texte")
        if duree:
            out = out.rstrip("\n") + "\n" + duree["mention"] + "\n"
    if args.sortie:
        p = _ecrire_texte(args.sortie, out)
        n = len(out.encode("utf-8"))
        if args.format == "json":
            cli.emit_json({"chemin": str(p), "octets": n, **meta})
        else:
            print(f"Écran « Mon plan » écrit : {p} ({n} octets). {BANNER}")
    elif args.format == "json":
        cli.emit_json(payload)
    else:
        print(out, end="")
    return 0


def _texte_grille(g: Any) -> list[str]:
    from brvm_alpha.rendement import grille as G

    out = [f"Grille : {g.nom} (statut : {G.statut_global(g)}) ; investisseur : {g.investisseur}"
           + (f" ; pays : {g.pays_residence}" if g.pays_residence else "")]
    rows = []
    for k, (_d, _lo, _hi, _h, unite, lib) in G.CHAMPS.items():
        ch = g.champs.get(k)
        if ch is None:
            continue
        val = G._txt(k, ch.valeur) if unite == "part" else G._rg.fcfa(ch.valeur)
        rows.append([lib, val, ch.statut, ch.source or "—"])
    out.append(_cli()._table(rows, ["Champ", "Valeur", "Statut", "Source"]))
    return out


def _ordre_pour_comparer(capital: float, args: argparse.Namespace) -> Mapping[str, Any]:
    """Ordre de la comparaison : celui du cache de « plan » s'il porte le même capital, sinon un ordre recalculé
    (sans le rendement net, plus court)."""
    p = dossier_profil() / "plan_cache.json"
    if p.exists():
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
            if abs(float(c.get("capital") or 0) - capital) < 0.5 and isinstance(c.get("ordre"), Mapping):
                return {**c["ordre"], "_source": f"cache de « plan » ({c.get('asof')})",
                        "_capital_ordre": float(c.get("capital_ordre") or capital)}
        except (OSError, ValueError, TypeError):
            pass
    from brvm_alpha.portfolio import recommend as rec

    cli = _cli()
    pdir = getattr(args, "panel_dir", None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        o = rec.recommend(cli._decision_date(None, pdir), capital, panel_dir=pdir, index_evaluation=False,
                          notes_store=None, notes_known_at=cli.notes_instant(None, None, pdir), today=cli.now_utc(),
                          rendement=False)
    return {**o.to_dict(), "_source": "ordre recalculé", "_capital_ordre": capital}


def _plan_grille(args: argparse.Namespace) -> int:
    from brvm_alpha.rendement import grille as G
    from brvm_alpha.rendement import reglages as RG

    cli = _cli()
    champs = {champ: getattr(args, "g_" + opt) for opt, champ, _n in CHAMPS_GRILLE if getattr(args, "g_" + opt) is not None}
    with _saisie("grille enregistrée"):
        avant = G.charger()
    chemin = None
    avertissements: list[str] = []
    if champs or args.investisseur or args.pays is not None:
        statut = STATUTS_GRILLE[args.statut] if args.statut else (G.ECRITE if args.source else G.SUPPOSE)
        g = copy.deepcopy(avant).avec(**champs)
        jour = _aujourd_hui().date().isoformat()
        for k in champs:
            g.champs[k].statut = statut
            g.champs[k].source = str(args.source or "").strip()
            g.champs[k].date = jour
        if g.nom.startswith("Tarif supposé"):
            g.nom = "Ma grille"
        if args.investisseur:
            g.investisseur = INVESTISSEURS[args.investisseur]
        if args.pays is not None:
            g.pays_residence = str(args.pays).strip()
        c = G.controler(g)
        if c["erreurs"]:
            raise SaisieInvalide("refusé : " + " ; ".join(c["erreurs"]) + " (rien n'est enregistré)")
        avertissements = list(c["avertissements"])
        paths.verifier_ecriture(dossier_profil() / "grille_sgi.yaml")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chemin = G.enregistrer(g)
        avant = g
    elif args.statut or args.source:
        raise SaisieInvalide("refusé : --statut et --source s'appliquent aux valeurs saisies dans la même commande "
                             "(par exemple --courtage 0,8 --statut ecrit --source « grille 2026 »)")
    comparaison = None
    if args.comparer:
        capital = float(getattr(args, "capital", None) or lire_plan().get("capital") or CAPITAL_DEFAUT)
        od = _ordre_pour_comparer(capital, args)
        grilles: dict[str, Any] = {"central": G.defaut()}
        if G.enregistree():
            with _saisie("grille enregistrée"):
                grilles["ma_sgi"] = G.charger()
        grilles.update(G.exemples())
        comparaison = {"capital": capital, "capital_ordre": od.get("_capital_ordre", capital),
                       "source": od.get("_source"),
                       "lignes": G.comparer({k: v for k, v in od.items() if not k.startswith("_")}, grilles),
                       "phrases": [RG.PH_FRAIS, RG.PH_ECONOMIE]}
    for a in avertissements:
        cli._say(f"⚠ {a}")
    if cli._json(args):
        cli.emit_json({"grille": avant.to_dict(), "enregistree": G.enregistree(), "chemin": str(chemin) if chemin else None,
                       "avertissements": avertissements, "comparaison": comparaison, "questions": G.questions()})
        return 0
    lignes = _texte_grille(avant)
    if chemin:
        lignes.append(f"Grille enregistrée : {chemin}.")
    for a in avertissements:
        lignes.append(f"Avertissement : {a}")
    if comparaison:
        rows = []
        for x in comparaison["lignes"]:
            ec = x["ecart_premiere_annee"]
            sens = ("frais évités" if ec < 0 else ("surcoût" if ec > 0 else "égal"))
            rows.append([x["nom"][:48], x["statut"], RG.fcfa(x["frais_achat"], unite=False),
                         RG.fcfa(x["frais_annuels"], unite=False), RG.fcfa(x["premiere_annee"], unite=False),
                         f"{RG.fcfa(ec, signe=True, unite=False)} ({sens})", x.get("mention") or ""])
        lignes.append("")
        lignes.append(f"Frais sur les lignes de l'ordre de {RG.fcfa(comparaison['capital_ordre'])} "
                      f"({comparaison['source']}), en FCFA :")
        lignes.append(cli._table(rows, ["Grille", "Statut", "Achat", "Par an", "1re année", "Écart (1re année)",
                                        "Mention"]))
        lignes.extend(comparaison["phrases"])
    lignes.append(BANNER)
    print("\n".join(lignes))
    return 0


def _plan_questions(args: argparse.Namespace) -> int:
    from brvm_alpha.rendement import grille as G

    cli = _cli()
    q = G.questions()
    if cli._json(args):
        cli.emit_json({"questions": q})
        return 0
    print("Les 8 questions à envoyer à votre courtier (SGI) :")
    print("\n".join(q))
    print(BANNER)
    return 0


# ---------------------------------------------------------------------------
# suivi
# ---------------------------------------------------------------------------


def cmd_suivi(args: argparse.Namespace) -> int:
    fn = {"demarrer": _suivi_demarrer, "maj": _suivi_maj, "bulletin": _suivi_bulletin, "saisir": _suivi_saisir,
          "revue": _suivi_revue, "declarer": _suivi_declarer, "verifier": _suivi_verifier,
          "exporter": _suivi_exporter}[args.suivi_cmd]
    return fn(args)


def _sortie_simple(args: argparse.Namespace, payload: Mapping[str, Any], lignes: list[str]) -> int:
    cli = _cli()
    if cli._json(args):
        cli.emit_json(dict(payload))
    else:
        print("\n".join(lignes + [BANNER]))
    return 0


def _suivi_demarrer(args: argparse.Namespace) -> int:
    from brvm_alpha import suivi as S
    from brvm_alpha.rendement import grille as G
    from brvm_alpha.suivi import carnet as cn

    nom = str(args.nom).strip()
    if nom in NOMS_MOTEUR:
        raise SaisieInvalide(f"refusé : {nom} est tenu par le moteur (« suivi maj ») : il n'a pas de carnet")
    D = dossier_suivi()
    paths.verifier_ecriture(D)
    with _saisie("portefeuille"):
        S.dossier_portefeuille(nom, D)  # nom valide, jamais sous reports/
        c = cn.ouvrir(nom, D, creer=False)
    if c.fichier.exists() and c.mandat():
        raise SaisieInvalide(f"refusé : le portefeuille « {nom} » est déjà démarré (mandat du {c.mandat()['date']}) ; "
                             "rien n'est écrit")
    pe = lire_plan()
    capital = float(args.capital or pe.get("capital") or CAPITAL_DEFAUT)
    jour = _aujourd_hui().date().isoformat()
    mandat = {"type": "mandat", "date": jour, "capital": capital, "mode": args.mode,
              "grille": "ma_sgi" if G.enregistree() else "central", "perte_toleree": pe.get("perte_toleree"),
              "taux_reserve": pe.get("taux_reserve"), "options_execution": []}
    c = cn.ouvrir(nom, D, creer=True)
    with _saisie("carnet"):
        ecrits = c.ajouter_plusieurs([mandat, {"type": "apport", "date": jour, "montant": capital}])
    return _sortie_simple(args, {"nom": nom, "carnet": str(c.fichier), "mouvements": ecrits, "mode": args.mode,
                                 "capital": capital},
                          [f"Portefeuille « {nom} » démarré le {jour} ({'sur papier' if args.mode == 'papier' else 'réel'}) "
                           f": mandat et apport de {_cli().fr_num(capital, 0)} FCFA en liquidités ({c.fichier}).",
                           "Aucun ordre n'est passé : le suivi compte, il ne décide pas."])


def _declares(jour: pd.Timestamp) -> set[str]:
    from brvm_alpha.suivi import declaration as DE

    try:
        ev = DE.en_vigueur(jour, dossier_declaration())
    except Exception:  # noqa: BLE001 - déclaration illisible : seul le témoin est suivi
        return set()
    return {k for k, a in (ev.get("articles") or {}).items() if isinstance(a, Mapping) and a.get("type") == "essai"} \
        if ev.get("declaration") else set()


def _portefeuilles(D: Path, jour: pd.Timestamp) -> list[str]:
    noms = ["REF-S2"]
    if "N" in _declares(jour):
        noms.append("N")
    if D.is_dir():
        for p in sorted(D.iterdir()):
            if p.is_dir() and p.name not in NOMS_MOTEUR and (p / "carnet.jsonl").is_file():
                noms.append(p.name)
    return noms


def _maj_moteur(nom: str, P: Mapping[str, Any], D: Path, jour: pd.Timestamp, args: argparse.Namespace) -> dict[str, Any]:
    from brvm_alpha.suivi import temoin as TM

    kw: dict[str, Any] = {}
    if nom == "N":
        from brvm_alpha.notes.store import NoteStore

        racine = getattr(args, "racine", None) or paths.NOTES_DIR
        kw["notes"] = NoteStore(_cli().notes_root_arg(racine))  # règle stricte à la date de décision (mode historique)
    r = TM.maj(nom, P, D, jusqu_au=jour, **kw)
    if r.get("ok") is False:
        raise RuntimeError(f"run du moteur en échec : {r.get('erreur')}")
    sem = r.get("semaines") or {}
    return {"nom": nom, "ok": True, "ecrit": bool(r.get("ecrit")), "semaine_0": bool(r.get("semaine_0", False)),
            "mention": r.get("mention"), "ajoutees": int(sem.get("ajoutees") or 0),
            "identiques": int(sem.get("identiques") or 0), "passe_a_change": bool(r.get("passe_a_change")),
            "derniere_semaine": (r.get("controles") or {}).get("derniere_semaine")}


def _maj_carnet(nom: str, P: Mapping[str, Any], D: Path, jour: pd.Timestamp) -> dict[str, Any]:
    from brvm_alpha.rendement import liquidites as LQ
    from brvm_alpha.suivi import bulletin as BU
    from brvm_alpha.suivi import papier as PA

    c = _carnet_existant(nom)
    g = _grille_du_mandat(c.mandat())
    mode = "test" if nom in MODE_TEST else "limite"
    seances = pd.DatetimeIndex(pd.to_datetime(P["close"].index)).normalize()
    derniere = pd.Timestamp(seances[-1])
    mouv = c.mouvements()
    if not mouv:
        return {"nom": nom, "ok": True, "ecrit": False, "mention": "carnet vide : rien à mettre à jour"}
    debut = min(pd.Timestamp(m["date"]).normalize() for m in mouv)
    if debut > derniere:
        return {"nom": nom, "ok": True, "ecrit": False, "semaine_0": True,
                "mention": f"semaine 0 : aucune séance du panel depuis le départ du {debut:%d/%m/%Y}"}
    from brvm_alpha import suivi as S

    # Exécution sur papier, puis semaines calculées sur le carnet ainsi complété : un seul passage sous le verrou du
    # portefeuille (une saisie lancée en même temps attend, ou sort en code 4 au-delà du délai).
    with S.verrou_ecriture(c.dossier, quoi=f"suivi maj de {nom}"):
        ex = PA.executer(c, P, derniere, mode=mode, grille=g)
        cm, _forfait = _cost_model(g)
        titres = {k: int(v["titres"]) for k, v in c.positions().items()}
        try:
            proj = LQ.projection_detenus(titres, P, derniere, c.liquidites(), costs=cm, grille=g)
            prevu = BU.prevu_depuis_projection(proj)
        except Exception:  # noqa: BLE001 - projection impossible : condition (b) du feu « Fuites » « non calculé »
            prevu = None
        lignes = BU.lignes_semaines(c.operations(), P, debut=debut, ordres=c.ordres(), jusqu_au=jour, prevu=prevu)
        res = BU.ecrire_semaines(nom, lignes, D)
    return {"nom": nom, "ok": True, "ecrit": bool(res["ajoutees"]), "mode": mode,
            "mouvements_ajoutes": len(ex.get("ajoutes") or []), "ajoutees": int(res["ajoutees"]),
            "identiques": int(res["identiques"]), "passe_a_change": bool(res["passe_a_change"]),
            "derniere_semaine": lignes[-1]["vendredi"] if lignes else None}


def _suivi_maj(args: argparse.Namespace) -> int:
    cli = _cli()
    D = dossier_suivi()
    paths.verifier_ecriture(D)
    jour = _aujourd_hui()
    if args.nom:
        from brvm_alpha import suivi as S

        with _saisie("portefeuille"):
            S.dossier_portefeuille(args.nom, D)
    if args.nom == "N" and "N" not in _declares(jour):
        raise SaisieInvalide("refusé : N (essai avec les notes) n'est suivi que s'il est déclaré (suivi declarer)")
    P = _panels(args.panel_dir)
    noms = [args.nom] if args.nom else _portefeuilles(D, jour)
    res: list[dict[str, Any]] = []
    for nom in noms:
        try:
            r = _maj_moteur(nom, P, D, jour, args) if nom in NOMS_MOTEUR else _maj_carnet(nom, P, D, jour)
        except MemoryError:
            raise
        except Exception as exc:  # noqa: BLE001 - un portefeuille en échec n'arrête pas les autres
            code = cli._code_sur(erreurs.code_retour(exc))
            msg = cli._error_message(exc)
            cli._say(f"suivi maj : {nom} en échec : {msg}")
            r = {"nom": nom, "ok": False, "code": code, "message": msg}
        res.append(r)
    echecs = [r for r in res if not r.get("ok")]
    payload = {"date": jour.date().isoformat(), "dossier": str(D), "portefeuilles": res,
               "en_echec": [r["nom"] for r in echecs]}
    lignes = []
    for r in res:
        if not r.get("ok"):
            lignes.append(f"{r['nom']} : en échec ({r['message']}).")
        elif r.get("ecrit"):
            lignes.append(f"{r['nom']} : {r.get('ajoutees', 0)} semaine(s) ajoutée(s), dernière semaine "
                          f"{r.get('derniere_semaine')}.")
        else:
            lignes.append(f"{r['nom']} : rien d'écrit ({r.get('mention') or 'aucune semaine nouvelle'}).")
        if r.get("passe_a_change"):
            lignes.append(f"   {r['nom']} : « le passé a changé » est consigné (anomalies.jsonl).")
    if echecs:
        code = echecs[0]["code"]
        msg = "échec : suivi maj : " + ", ".join(r["nom"] for r in echecs) + " en échec (les autres sont à jour)"
        if cli._json(args):
            return cli.emit_echec(code, msg, **payload)
        print("\n".join(lignes + [BANNER]))
        cli._say(msg)
        return code
    return _sortie_simple(args, payload, lignes)


def _positions_csv(d: Path) -> dict[str, int]:
    p = d / "positions.csv"
    if not p.exists():
        return {}
    df = pd.read_csv(p, dtype={"symbole": str})
    if not len(df):
        return {}
    der = df[df["date"] == df["date"].max()]
    return {str(r.symbole): int(r.titres) for r in der.itertuples(index=False) if int(r.titres) > 0}


def _detaches(ops: pd.DataFrame | None, P: Mapping[str, Any] | None) -> pd.DataFrame | None:
    """Dividendes détachés des titres détenus la veille du détachement (condition d du feu « Fuites »)."""
    from brvm_alpha.suivi import carnet as cn
    from brvm_alpha.suivi import papier as PA

    if P is None or ops is None or not len(ops):
        return None
    tab = PA.dividendes_detaches(P)
    cols = ["symbole", "date_detachement", "date_paiement", "montant", "titres"]
    if not len(tab):
        return pd.DataFrame(columns=cols)
    d0 = pd.to_datetime(ops["date"]).min()
    rows = []
    for r in tab.itertuples(index=False):
        ex = pd.Timestamp(r.date_detachement)
        if ex <= d0:
            continue
        pos = cn.positions_depuis_operations(ops, ex - pd.Timedelta(days=1)).get(str(r.symbole))
        q = int(pos["titres"]) if pos else 0
        if q > 0:
            rows.append({"symbole": str(r.symbole), "date_detachement": ex, "date_paiement": r.date_paiement,
                         "montant": q * float(r.net_par_titre), "titres": q})
    return pd.DataFrame(rows, columns=cols)


def _suivi_bulletin(args: argparse.Namespace) -> int:
    nom = str(args.nom or "REF-S2").strip()
    try:
        P: Mapping[str, Any] | None = _panels(args.panel_dir)
    except DonneesAbsentes:
        P = None  # le bulletin sort quand même, sans les prochains rendez-vous
    b = bulletin_portefeuille(nom, dossier_suivi(), panels=P)
    return _sortir_bulletin(args, b, nom)


def bulletin_portefeuille(nom: str, D: Path, *, profil: Path | None = None, panels: Mapping[str, Any] | None = None,
                          jour: Any = None) -> dict[str, Any]:
    """Bulletin de la semaine du portefeuille ``nom`` (journal ``D/<nom>``) : prochains rendez-vous (si ``panels``),
    trois feux, déclaration en vigueur. ``profil`` : dossier du plan enregistré et de la grille (défaut : celui de
    l'installation). Lecture seule ; sert à ``suivi bulletin`` et à l'interface (page Portefeuille)."""
    from brvm_alpha import suivi as S
    from brvm_alpha.suivi import bulletin as BU
    from brvm_alpha.suivi import declaration as DE

    with _saisie("portefeuille"):
        d = S.dossier_portefeuille(nom, D)
    jour = pd.Timestamp(jour).normalize() if jour is not None else _aujourd_hui()
    P = panels
    lignes = BU.semaines_du_journal(nom, D)
    date_rv = pd.Timestamp(lignes[-1]["date"]) if lignes else jour
    T = float(lignes[-1].get("valeur_titres") or 0) if lignes else 0.0
    if nom in NOMS_MOTEUR:
        ops = pd.read_csv(d / "operations.csv", dtype={"symbole": str}) if (d / "operations.csv").exists() else None
        titres = _positions_csv(d)
        cm, forfait = _cost_model(_grille_du_mandat(None, profil))
        papier = True
        kw_rv: dict[str, Any] = {"rythme": "semaine"}
    else:
        c = _carnet_existant(nom, D)
        ops = c.operations()
        titres = {k: int(v["titres"]) for k, v in c.positions().items()}
        mandat = c.mandat() or {}
        cm, forfait = _cost_model(_grille_du_mandat(mandat, profil))
        papier = mandat.get("mode") != "reel"
        kw_rv = {"rythme": "trimestre", "dernier_prelevement": _dernier_prelevement(c)}
    rv = BU.rendez_vous(titres, P, date_rv, costs=cm, valeur_titres=T, forfait=forfait, **kw_rv) if P is not None else None
    return BU.depuis_journal(nom, D, plan=lire_plan(profil) or None,
                             declaration=DE.verifier(dossier_declaration(), registre=_registre_si_present()),
                             papier=papier, aujourd_hui=jour, rendez_vous=rv, detaches=_detaches(ops, P), operations=ops)


def _sortir_bulletin(args: argparse.Namespace, b: Mapping[str, Any], nom: str) -> int:
    from brvm_alpha.suivi import bulletin as BU

    cli = _cli()
    fmt = args.format if args.format in ("texte", "md", "json") else "texte"
    out = BU.rendre(b, fmt)
    if fmt != "json" and BANNER not in out:
        out = out.rstrip("\n") + "\n" + BANNER + "\n"
    if args.sortie:
        p = _ecrire_texte(args.sortie, out)
        n = len(out.encode("utf-8"))
        if fmt == "json":
            cli.emit_json({"chemin": str(p), "octets": n, "nom": nom, "semaine": b.get("semaine")})
        else:
            print(f"Bulletin écrit : {p} ({n} octets). {BANNER}")
        return 0
    if fmt == "json":
        cli.emit_json(json.loads(out))
    else:
        print(out, end="")
    return 0


def lire_avis(chemin: Path) -> list[dict[str, Any]]:
    """Lignes d'un avis d'opéré (CSV, séparateur « , » ou « ; », virgule décimale acceptée)."""
    return lire_avis_texte(chemin.read_text(encoding="utf-8-sig"), str(chemin))


def lire_avis_texte(texte: str, origine: str = "avis d'opéré") -> list[dict[str, Any]]:
    """Lignes d'un avis d'opéré écrit en CSV (fichier lu, ou texte collé dans l'interface) ; ``origine`` nomme la
    saisie dans le message de refus."""
    texte = str(texte or "").lstrip("\ufeff")
    premiere = texte.splitlines()[0] if texte.strip() else ""
    sep = ";" if premiere.count(";") > premiere.count(",") else ","
    num = {"titres", "prix", "courtage", "taxe", "commissions", "brvm", "dcbr", "autres_frais", "total",
           "cours_reference"}
    out = []
    for i, r in enumerate(csv.DictReader(io.StringIO(texte), delimiter=sep), start=2):
        ligne: dict[str, Any] = {}
        for k, v in r.items():
            if k is None:
                continue
            k2 = str(k).strip().lower()
            v2 = str(v or "").strip()
            if k2 in num:
                if v2 == "":
                    continue
                try:
                    ligne[k2] = float(v2.replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", "."))
                except ValueError:
                    raise SaisieInvalide(f"refusé : avis d'opéré, ligne {i} : {k2} invalide ({v2!r})") from None
            else:
                ligne[k2] = v2
        if not ligne.get("symbole") or not ligne.get("date") or ligne.get("sens") not in ("achat", "vente"):
            raise SaisieInvalide(f"refusé : avis d'opéré, ligne {i} : date, symbole et sens (achat ou vente) obligatoires")
        ligne["symbole"] = str(ligne["symbole"]).upper()
        out.append(ligne)
    if not out:
        raise SaisieInvalide(f"refusé : avis d'opéré vide : {origine}")
    return out


def _suivi_saisir(args: argparse.Namespace) -> int:
    cli = _cli()
    c = _carnet_existant(str(args.nom).strip())
    paths.verifier_ecriture(c.fichier)
    jour = _aujourd_hui().date().isoformat()
    if args.apport is not None or args.retrait is not None:
        ty = "apport" if args.apport is not None else "retrait"
        montant = float(args.apport if args.apport is not None else args.retrait)
        with _saisie("carnet"):
            m = c.ajouter({"type": ty, "date": jour, "montant": montant})
        return _sortie_simple(args, {"nom": c.nom, "mouvement": m},
                              [f"{ty.capitalize()} de {cli.fr_num(montant, 0)} FCFA consigné au carnet « {c.nom} » "
                               f"le {jour}."])
    if (c.mandat() or {}).get("mode") != "reel":
        raise SaisieInvalide("refusé : un avis d'opéré ne se saisit que dans un portefeuille réel (suivi demarrer --mode "
                             "reel) ; un portefeuille sur papier est exécuté par « suivi maj »")
    lignes = lire_avis(_fichier_lu(args.fichier, "--fichier"))
    payload = saisir_avis_au_carnet(c, lignes, confirmer_grille=bool(args.confirmer_grille), jour=jour)
    r = {"texte": payload["texte"], "grille_proposee": payload["grille_proposee"]}
    chemin = payload["grille_enregistree"]
    ecarts = payload["lignes"]
    txt = [f"{len(lignes)} exécution(s) de l'avis d'opéré consignée(s) au carnet « {c.nom} ».", r["texte"]]
    for x in ecarts:
        if not x["concorde"]:
            txt.append(f"   {x['symbole']} ({x['date']}) : écarts en FCFA {x['ecarts_fcfa']}")
    if r.get("grille_proposee") is not None and not chemin:
        txt.append("Grille corrigée proposée, non enregistrée : relancer avec --confirmer-grille, ou la saisir avec "
                   "« plan grille --courtage T --statut avis --source … ».")
    if chemin:
        txt.append(f"Grille enregistrée : {chemin}.")
    return _sortie_simple(args, payload, txt)


def saisir_avis_au_carnet(c: Any, lignes: list[dict[str, Any]], *, confirmer_grille: bool = False, jour: str | None = None,
                          profil: Path | None = None) -> dict[str, Any]:
    """Consigne les lignes d'un avis d'opéré au carnet ``c`` (portefeuille réel) et compare ses frais à la grille du
    profil (``profil``, défaut : celui de l'installation). Si tout concorde, la grille passe au statut « avis d'opéré » ;
    sinon une grille corrigée est proposée et n'est enregistrée qu'avec ``confirmer_grille``. Sert à ``suivi saisir`` et
    à l'interface (page Portefeuille)."""
    from brvm_alpha.rendement import grille as G

    jour = jour or _aujourd_hui().date().isoformat()
    prof = profil if profil is not None else dossier_profil()
    with _saisie("avis d'opéré"):
        g0 = G.charger(prof)
        r = c.saisir_avis(lignes, g0)
    chemin = None
    if r["concorde"]:
        paths.verifier_ecriture(prof / "grille_sgi.yaml")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chemin = G.enregistrer(r["grille"], prof)
    elif r.get("grille_proposee") is not None and confirmer_grille:
        gp = r["grille_proposee"]
        gp.champs["courtage"].statut = G.AVIS
        gp.champs["courtage"].source = f"avis d'opéré saisi le {jour}"
        gp.champs["courtage"].date = jour
        paths.verifier_ecriture(prof / "grille_sgi.yaml")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chemin = G.enregistrer(gp, prof)
    ecarts = [{"symbole": x["symbole"], "date": x["date"], "ecarts_fcfa": x["ecarts_fcfa"], "concorde": x["concorde"]}
              for x in r["lignes"]]
    return {"nom": c.nom, "concorde": r["concorde"], "lignes": ecarts, "postes_nouveaux": r["postes_nouveaux"],
            "grille_enregistree": str(chemin) if chemin else None,
            "grille_proposee": r["grille_proposee"].to_dict() if r.get("grille_proposee") is not None else None,
            "texte": r["texte"]}


def _suivi_revue(args: argparse.Namespace) -> int:
    from brvm_alpha.rendement import reglages as RG

    c = _carnet_existant(str(args.nom).strip())
    paths.verifier_ecriture(c.fichier)
    jour = _aujourd_hui().date().isoformat()
    with _saisie("carnet"):
        m = c.ajouter({"type": "revue", "date": jour, "alerte": str(args.alerte), "decision": args.decision,
                       "texte": str(args.texte)})
    return _sortie_simple(args, {"nom": c.nom, "mouvement": m, "phrase": RG.PH_REVUE},
                          [f"Revue consignée au carnet « {c.nom} » le {jour} : alerte {args.alerte}, décision "
                           f"« {args.decision} ». Aucun ordre n'est créé.", RG.PH_REVUE])


def _suivi_declarer(args: argparse.Namespace) -> int:
    from brvm_alpha.suivi import declaration as DE

    cli = _cli()
    if paths.est_embarque() or not DE.depot_de_developpement():
        raise SaisieInvalide("refusé : " + DE.MESSAGE_HORS_DEPOT)
    if not (args.modele or args.fichier or args.registre):
        raise SaisieInvalide("refusé : suivi declarer attend --modele, --fichier F --signer INITIALES, ou --registre "
                             "--confirmer \"J'INSCRIS AU REGISTRE\"")
    if args.modele:
        arts = DE.modele()
        texte = json.dumps(arts, ensure_ascii=False, indent=1) + "\n"
        if args.sortie:
            p = _ecrire_texte(args.sortie, texte)
            return _sortie_simple(args, {"chemin": str(p), "articles": len(arts)},
                                  [f"Projet de déclaration écrit : {p} ({len(arts)} articles, non signé)."])
        if cli._json(args):
            cli.emit_json({"modele": arts})
        else:
            print(texte, end="")
        return 0
    dossier = dossier_declaration()
    if args.registre:
        # Contrôles de l'inscription AVANT toute signature : une commande refusée n'écrit jamais de ligne signée.
        if args.confirmer != DE.CONFIRMATION_REGISTRE:
            raise SaisieInvalide(f"refusé : inscription au registre : recopiez exactement « {DE.CONFIRMATION_REGISTRE} » "
                                 "après --confirmer ; rien n'est signé ni inscrit")
        if not registre_des_essais().exists():
            raise SaisieInvalide(f"refusé : registre des essais introuvable ({registre_des_essais()}) ; rien n'est signé "
                                 "ni inscrit")
        if not args.fichier and not (dossier / DE.FICHIER).is_file():
            raise SaisieInvalide("refusé : inscription au registre : aucune déclaration signée (signer d'abord avec "
                                 "--fichier F --signer INITIALES)")
    chemin = None
    inscrits: list[str] = []
    try:
        if args.fichier:
            brut = json.loads(_fichier_lu(args.fichier, "--fichier").read_text(encoding="utf-8"))
            arts = brut.get("articles") if isinstance(brut, Mapping) else brut
            if not isinstance(arts, list):
                raise ValueError("articles : une liste JSON est attendue (sortie de --modele, réponses remplies)")
            chemin = DE.signer(arts, args.signer, dossier)
        if args.registre:
            inscrits = DE.inscrire_au_registre(dossier, registre_des_essais(), confirmer=args.confirmer)
    except (DE.SignatureInvalide, DE.HorsDepot, ValueError, PermissionError) as exc:
        msg = str(exc)
        if msg.lower().startswith("inscription refusée : "):
            msg = "inscription au registre : " + msg[len("inscription refusée : "):]
        if chemin is not None:  # signée, mais l'inscription a échoué : le dire, la signature est définitive
            msg += f" (la déclaration est signée : {chemin} ; relancer seulement --registre --confirmer)"
        elif args.registre and msg.startswith("déjà signés"):
            msg += f" ; pour l'inscription seule : suivi declarer --registre --confirmer \"{DE.CONFIRMATION_REGISTRE}\""
        raise SaisieInvalide(msg if msg.lower().startswith("refusé") else "refusé : " + msg) from exc
    v = DE.verifier(dossier, registre=_registre_si_present())
    txt = []
    if chemin:
        txt.append(f"Déclaration signée : {chemin} ({v['n_lignes']} ligne(s), chaîne {'intacte' if v['chaine_ok'] else 'rompue'}).")
        txt.append("Elle se livre par un commit daté, avant le début du suivi.")
    if args.registre:
        txt.append(f"Registre des essais : {len(inscrits)} ligne(s) ajoutée(s)" + (f" ({', '.join(inscrits)})." if inscrits
                                                                                  else " (déjà inscrites)."))
    return _sortie_simple(args, {"chemin": str(chemin) if chemin else None, "inscrits": inscrits, "verification": v},
                          txt)


def _suivi_verifier(args: argparse.Namespace) -> int:
    from brvm_alpha.suivi import bulletin as BU
    from brvm_alpha.suivi import carnet as cn
    from brvm_alpha.suivi import declaration as DE

    cli = _cli()
    v = DE.verifier(dossier_declaration(), registre=_registre_si_present())
    D = dossier_suivi()
    pf = []
    if D.is_dir():
        for p in sorted(D.iterdir()):
            if not p.is_dir() or p.name.startswith("."):
                continue
            e: dict[str, Any] = {"nom": p.name}
            if (p / "semaines.csv").exists():
                e["semaines"] = BU.verifier_semaines(p.name, D)
            if (p / "carnet.jsonl").exists():
                e["carnet"] = cn.ouvrir(p.name, D, creer=False).verifier()
            if len(e) > 1:
                e["ok"] = all(x.get("chaine_ok", False) for k, x in e.items() if k in ("semaines", "carnet"))
                pf.append(e)
    rompues = (["déclaration"] if not v["chaine_ok"] else []) + [e["nom"] for e in pf if not e["ok"]]
    payload = {"declaration": v, "portefeuilles": pf, "rompues": rompues}
    txt = [("Déclaration : " + (f"{v['n_lignes']} ligne(s), chaîne intacte." if v["existe"] and v["chaine_ok"]
                                else (str(v.get("mention") or "absente.") if not v["existe"]
                                      else "chaîne rompue : " + " ; ".join(v["anomalies"][:3]))))]
    for e in pf:
        txt.append(f"{e['nom']} : " + ("chaînes intactes." if e["ok"] else "chaîne rompue : " + " ; ".join(
            (e.get("semaines") or {}).get("anomalies", [])[:2] + (e.get("carnet") or {}).get("anomalies", [])[:2])))
    if not pf:
        txt.append("Aucun journal du suivi pour l'instant.")
    if rompues:
        msg = "échec : chaîne rompue : " + ", ".join(rompues) + " (feu « Données » rouge : une décision écrite est attendue)"
        if cli._json(args):
            return cli.emit_echec(erreurs.DONNEES_ABSENTES, msg, **payload)
        print("\n".join(txt + [BANNER]))
        cli._say(msg)
        return erreurs.DONNEES_ABSENTES
    return _sortie_simple(args, payload, txt)


def _suivi_exporter(args: argparse.Namespace) -> int:
    cli = _cli()
    D = dossier_suivi()
    if not D.is_dir() or not any(D.iterdir()):
        raise DonneesAbsentes(f"échec : aucun journal du suivi à copier ({D})")
    dest = Path(os.path.abspath(paths.resoudre_chemin_option(args.dossier_sortie, base="rapports")))
    paths.verifier_ecriture(dest)
    if paths.est_embarque() and not any(_dans(dest, b) for b in (paths.REPORTS_DIR, Path(tempfile.gettempdir()))):
        raise SaisieInvalide(f"refusé : --sortie {dest} est hors des dossiers permis en mode embarqué (rapports "
                             f"{paths.REPORTS_DIR}, fichiers temporaires).")
    if _dans(dest, D) or _dans(D, dest):
        raise SaisieInvalide(f"refusé : --sortie {dest} recouvre le dossier du suivi ({D})")
    publies = paths.REPO_ROOT / "reports"
    if any(_dans(dest, x) for x in [publies / "validation_S1", publies / "trials.parquet",
                                     *publies.glob("diagnostic_S0*")]):
        raise SaisieInvalide(f"refusé : --sortie {dest} est dans les résultats publiés de la validation (jamais "
                             "modifiés)")
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise SaisieInvalide(f"refusé : --sortie {dest} existe et n'est pas un dossier vide (rien n'est écrasé)")
    exclus = [] if args.avec_moi else [n for n in PRIVES if (D / n).exists()]

    def ignorer(dossier: str, noms: list[str]) -> list[str]:
        haut = Path(dossier) == D
        return [n for n in noms if (haut and n in exclus) or n.endswith((".part", ".lock", ".tmp"))]

    def copie(f: Path) -> bool:
        r = f.relative_to(D).parts
        return f.is_file() and r[0] not in exclus and not any(x.endswith((".part", ".lock", ".tmp")) for x in r)

    if not any(copie(f) for f in D.rglob("*")):  # rien à copier après les exclusions : aucun dossier créé
        raise DonneesAbsentes(f"échec : rien à copier ({D})" + (f" : seul {', '.join(exclus)} (privé) est présent ; "
                                                                "--avec-moi pour le copier" if exclus else ""))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.{os.getpid()}.part"
    if tmp.exists():
        shutil.rmtree(tmp)
    try:
        shutil.copytree(D, tmp, ignore=ignorer)
        if dest.exists():
            dest.rmdir()
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    fichiers_ = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    return _sortie_simple(args, {"chemin": str(dest), "fichiers": fichiers_, "exclus": exclus},
                          [f"Journaux du suivi copiés : {dest} ({len(fichiers_)} fichier(s))."]
                          + ([f"Non copié (privé) : {', '.join(exclus)} ; --avec-moi pour le copier."] if exclus else []))


#: Écriture atomique d'un fichier JSON des données (refusée dans l'arbre du code en mode embarqué).
ecrire_json = _ecrire_json

__all__ = ["BANNER", "CAPITAL_DEFAUT", "NOMS_MOTEUR", "ajouter_options", "ajouter_parseurs", "bulletin_portefeuille",
           "cache_du_plan", "cmd_plan", "cmd_suivi", "dossier_declaration", "dossier_profil", "dossier_suivi",
           "ecrire_json", "lire_avis", "lire_avis_texte", "lire_plan", "options_recommend", "parse_montant",
           "parse_perte", "parse_taux", "parse_taux_reserve", "registre_des_essais", "saisir_avis_au_carnet"]
