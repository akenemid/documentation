"""F12 — Carnet d'un portefeuille suivi : journal en ajout seul, prix de revient, mémoire, avis d'opéré.

Cahier ``docs/RENDEMENT_NET.md``, §F12. L'outil se souvient de ce qui a été acheté, à quel prix, avec quels frais. Le
carnet est un fichier ``<dossier>/<nom>/carnet.jsonl`` en **ajout seul** : une ligne JSON par mouvement, chaînée à la
précédente (``precedente`` = SHA-256 du texte exact de la ligne précédente ; ``empreinte`` = SHA-256 de son contenu).
Une erreur ne s'efface pas : elle se corrige par un mouvement ``correction`` qui annule le mouvement fautif.

Mouvements : ``mandat``, ``apport``, ``retrait``, ``ordre``, ``execution``, ``expiration``, ``dividende``, ``frais``,
``division``, ``revue``, ``correction``.

Prix de revient par ligne : coût moyen pondéré, frais facturés compris, ``PR = Σ(titres × prix + frais) ÷ Σ titres``.
Une vente ne change pas PR ; résultat réalisé = titres × (prix − PR) − frais. Division : titres × rapport, PR ÷ rapport.
Refus : saisie en double, vente de plus de titres que détenus, retrait de plus que les liquidités, revue d'un code
d'alerte inconnu, date de l'échantillon S1 (≤ 16/11/2022).

Aucune écriture hors du dossier du portefeuille ; jamais sous ``reports/``. Performance passée ≠ garantie. Aucun gain
n'est garanti.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from brvm_alpha import suivi as _s

__all__ = ["COLONNES_OPERATIONS", "Carnet", "TYPES", "ouvrir", "lignes_depuis_operations", "positions_depuis_operations"]

TYPES = ("mandat", "apport", "retrait", "ordre", "execution", "expiration", "dividende", "frais", "division", "revue",
         "correction")
SENS = ("achat", "vente")
SOURCES = ("papier", "avis_opere", "moteur", "saisie")
#: Colonnes de ``operations.csv`` (§F10), plus ``cours_reference`` (cours de référence avant l'ordre, base unique du pont)
#: et ``ordre`` (numéro de l'ordre d'origine).
COLONNES_OPERATIONS = ("date", "type", "symbole", "titres", "prix", "courtage", "taxe", "brvm", "dcbr", "autres_frais",
                       "cout_prix", "montant_net", "source", "cours_reference", "ordre")
_TECH = ("n", "ecrit_utc", "precedente", "empreinte")


def _f(x: Any, defaut: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return defaut
    return v if math.isfinite(v) else defaut


def _fcfa(x: float) -> str:
    """Montant en FCFA au franc, chiffres groupés par une espace fine (« 10 000 000 »)."""
    return f"{x:,.0f}".replace(",", " ")


def _frais_total(fr: Mapping[str, Any] | None) -> float:
    fr = fr or {}
    return sum(_f(fr.get(k)) for k in ("courtage", "taxe", "brvm", "dcbr", "autres"))


class Carnet:
    """Carnet d'un portefeuille (``<dossier>/<nom>/carnet.jsonl``)."""

    def __init__(self, nom: str, dossier: str | Path | None = None) -> None:
        self.nom = str(nom)
        self.dossier = _s.dossier_portefeuille(self.nom, dossier)
        self.fichier = self.dossier / "carnet.jsonl"

    def __repr__(self) -> str:
        return f"Carnet({self.nom!r}, {len(self.mouvements(actifs=False))} mouvements)"

    # -- lecture ---------------------------------------------------------------------------------

    def lignes_brutes(self) -> list[tuple[str, dict[str, Any] | None]]:
        return _s.lire_jsonl(self.fichier)

    def mouvements(self, *, actifs: bool = True, types: Iterable[str] | None = None,
                   jusqu_a: Any = None) -> list[dict[str, Any]]:
        """Mouvements dans l'ordre d'écriture. ``actifs`` : sans les mouvements annulés par une ``correction`` (ni les
        corrections elles-mêmes). ``jusqu_a`` : mouvements datés au plus tard ce jour."""
        tous = [o for _t, o in self.lignes_brutes() if o is not None]
        if actifs:
            annules = {int(o["annule"]) for o in tous if o.get("type") == "correction" and o.get("annule") is not None}
            tous = [o for o in tous if o.get("type") != "correction" and int(o.get("n", 0)) not in annules]
        if types is not None:
            ts = set(types)
            tous = [o for o in tous if o.get("type") in ts]
        if jusqu_a is not None:
            t = pd.Timestamp(jusqu_a).normalize()
            tous = [o for o in tous if pd.Timestamp(o["date"]).normalize() <= t]
        return [copy.deepcopy(o) for o in tous]

    def verifier(self) -> dict[str, Any]:
        """Chaîne du carnet : toute réécriture d'une ligne la rompt (feu « Données » rouge)."""
        anomalies: list[str] = []
        prec = _s.ZERO
        brut = self.lignes_brutes()
        for i, (txt, obj) in enumerate(brut, start=1):
            if obj is None:
                anomalies.append(f"ligne {i} illisible")
            else:
                if obj.get("n") != i:
                    anomalies.append(f"ligne {i} : numéro {obj.get('n')!r}")
                if obj.get("precedente") != prec:
                    anomalies.append(f"ligne {i} : chaîne rompue")
                if obj.get("empreinte") != _s.empreinte({k: v for k, v in obj.items() if k != "empreinte"}):
                    anomalies.append(f"ligne {i} : contenu modifié")
            prec = _s.empreinte_texte(txt)
        return {"ok": not anomalies, "chaine_ok": not anomalies, "n": len(brut), "anomalies": anomalies,
                "derniere": prec if brut else _s.ZERO}

    # -- écriture --------------------------------------------------------------------------------

    def _contenu(self, m: Mapping[str, Any]) -> str:
        return _s.canonique({k: v for k, v in m.items() if k not in _TECH})

    def ajouter(self, mouvement: Mapping[str, Any], *, maintenant: Any = None,
                autoriser_double: bool = False) -> dict[str, Any]:
        """Ajoute un mouvement à la fin du carnet (jamais de réécriture) et le rend, numéroté et chaîné.

        Refus (``ValueError``) : type inconnu ; date absente ou de l'échantillon S1 ; saisie en double (même contenu
        qu'un mouvement actif, sauf ``autoriser_double``) ; vente de plus de titres que détenus ; retrait de plus que les
        liquidités du carnet à sa date ; revue d'un code d'alerte inconnu
        (:func:`brvm_alpha.rendement.alertes.cible_de_revue`) ou sans texte ; division sans rapport positif ; correction d'un mouvement
        absent ; chaîne déjà rompue."""
        return self.ajouter_plusieurs([mouvement], maintenant=maintenant, autoriser_double=autoriser_double)[0]

    def ajouter_plusieurs(self, mouvements: Sequence[Mapping[str, Any]], *, maintenant: Any = None,
                          autoriser_double: bool = False) -> list[dict[str, Any]]:
        """Comme :meth:`ajouter`, pour plusieurs mouvements écrits ensemble. La vérification de la chaîne et l'ajout se
        font sous le verrou d'écriture du portefeuille (:func:`brvm_alpha.suivi.verrou_ecriture` ; code 4 s'il reste
        tenu par une autre opération)."""
        with _s.verrou_ecriture(self.dossier, quoi=f"carnet {self.nom}"):
            return self._ajouter_plusieurs(mouvements, maintenant=maintenant, autoriser_double=autoriser_double)

    def _ajouter_plusieurs(self, mouvements: Sequence[Mapping[str, Any]], *, maintenant: Any,
                           autoriser_double: bool) -> list[dict[str, Any]]:
        v = self.verifier()
        if not v["chaine_ok"]:
            raise ValueError("carnet à la chaîne rompue : aucun mouvement ne peut être ajouté avant une décision écrite ("
                             + " ; ".join(v["anomalies"][:3]) + ")")
        actifs = self.mouvements()
        vus = {self._contenu(m) for m in actifs}
        tous_n = {int(o.get("n", 0)) for o in self.mouvements(actifs=False)}
        t = pd.Timestamp(maintenant) if maintenant is not None else pd.Timestamp.now(tz="UTC")
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        n = v["n"]
        prec = v["derniere"]
        prets: list[dict[str, Any]] = []
        for brut in mouvements:
            m = {k: copy.deepcopy(val) for k, val in brut.items() if k not in _TECH}
            self._valider(m, actifs + prets, tous_n | {int(p["n"]) for p in prets})
            c = self._contenu(m)
            if c in vus and not autoriser_double:
                raise ValueError(f"saisie en double refusée : {m.get('type')} du {m.get('date')} déjà au carnet")
            vus.add(c)
            n += 1
            m = {"n": n, "ecrit_utc": t.isoformat(), **m, "precedente": prec}
            m["empreinte"] = _s.empreinte(m)
            prec = _s.empreinte_texte(_s.ligne_json(m))
            prets.append(m)
        _s.ajouter_jsonl(self.fichier, prets)
        return prets

    def _valider(self, m: dict[str, Any], deja: list[dict[str, Any]], numeros: set[int]) -> None:
        ty = m.get("type")
        if ty not in TYPES:
            raise ValueError(f"type de mouvement inconnu : {ty!r} (attendus : {', '.join(TYPES)})")
        if not m.get("date"):
            raise ValueError("date du mouvement obligatoire")
        d = _s.refuser_s1(m["date"], f"le mouvement « {ty} »")
        m["date"] = d.date().isoformat()
        if ty in ("execution", "ordre", "expiration", "dividende", "division") and not m.get("symbole"):
            raise ValueError(f"{ty} : symbole obligatoire")
        if ty in ("execution", "ordre"):
            if m.get("sens") not in SENS:
                raise ValueError(f"{ty} : sens « achat » ou « vente »")
            if int(_f(m.get("titres"))) <= 0 or int(_f(m.get("titres"))) != _f(m.get("titres")):
                raise ValueError(f"{ty} : nombre entier de titres positif")
            m["titres"] = int(_f(m["titres"]))
        if ty == "execution":
            if _f(m.get("prix")) <= 0:
                raise ValueError("execution : prix positif")
            m.setdefault("frais", {})
            m.setdefault("source", "saisie")
            if m["source"] not in SOURCES:
                raise ValueError(f"execution : source parmi {SOURCES}")
            if m["sens"] == "vente":
                pos = positions_depuis_mouvements(deja, d).get(m["symbole"], {})
                if int(m["titres"]) > int(pos.get("titres", 0)):
                    raise ValueError(f"vente refusée : {m['titres']} titres {m['symbole']} pour {int(pos.get('titres', 0))} "
                                     "détenus")
        if ty in ("apport", "retrait") and _f(m.get("montant")) <= 0 and int(_f(m.get("titres"))) <= 0:
            raise ValueError(f"{ty} : montant positif (ou titres apportés)")
        if ty == "retrait" and _f(m.get("montant")) > 0:
            # Le carnet est en ajout seul : un retrait plus grand que les liquidités y resterait pour toujours. Refus
            # avant toute écriture ; un retrait égal aux liquidités reste accepté (à un demi-franc près).
            ops = operations_depuis_mouvements([x for x in deja if pd.Timestamp(x["date"]).normalize() <= d])
            liq = float(ops["montant_net"].sum()) if len(ops) else 0.0
            if _f(m["montant"]) > liq + 0.5:
                raise ValueError(f"retrait refusé : {_fcfa(_f(m['montant']))} FCFA demandés pour {_fcfa(liq)} FCFA de "
                                 f"liquidités au carnet « {self.nom} » le {d:%d/%m/%Y} (rien n'est écrit)")
        if ty == "revue":
            from brvm_alpha.rendement import alertes as _al

            m["alerte"] = _al.cible_de_revue(m.get("alerte"))  # code inconnu (« W99 ») : refusé, codes connus cités
            if not str(m.get("texte") or "").strip():  # la revue consigne une décision écrite, pour toujours
                raise ValueError("revue : texte vide ; écrire les réponses aux questions de la revue (rien n'est écrit)")
        if ty == "apport" and int(_f(m.get("titres"))) > 0 and (not m.get("symbole") or _f(m.get("cours")) <= 0):
            raise ValueError("apport de titres : symbole et cours de clôture du jour d'apport obligatoires")
        if ty == "division" and _f(m.get("rapport")) <= 0:
            raise ValueError("division : rapport positif (10 pour 1 : rapport 10)")
        if ty == "dividende" and _f(m.get("montant")) < 0:
            raise ValueError("dividende : montant net positif ou nul")
        if ty == "frais" and _f(m.get("montant")) <= 0:
            raise ValueError("frais : montant positif")
        if ty == "correction":
            if m.get("annule") is None or int(m["annule"]) not in numeros:
                raise ValueError("correction : numéro du mouvement annulé absent du carnet")
            if not m.get("motif"):
                raise ValueError("correction : motif obligatoire")

    # -- états dérivés ---------------------------------------------------------------------------

    def positions(self, date: Any = None) -> dict[str, dict[str, Any]]:
        """Lignes détenues à ``date`` (défaut : tout le carnet) : titres, prix de revient, coût, cours de référence
        moyen, résultat réalisé, dividendes reçus, date du premier achat."""
        return {k: v for k, v in positions_depuis_mouvements(self.mouvements(), date).items() if v["titres"] > 0}

    def operations(self, date: Any = None) -> pd.DataFrame:
        """Opérations au format de ``operations.csv`` (§F10), dans l'ordre des dates."""
        return operations_depuis_mouvements(self.mouvements(jusqu_a=date))

    def liquidites(self, date: Any = None) -> float:
        """Liquidités : apports − retraits + ventes nettes − achats nets + dividendes − frais."""
        ops = self.operations(date)
        return float(ops["montant_net"].sum()) if len(ops) else 0.0

    def mandat(self, date: Any = None) -> dict[str, Any] | None:
        """Dernier mandat (capital, ce que j'accepte de risquer, montant en actions, réserve, grille, mode)."""
        ms = self.mouvements(types=("mandat",), jusqu_a=date)
        return ms[-1] if ms else None

    def ordres(self, date: Any = None) -> list[dict[str, Any]]:
        """Ordres et leur état : titres servis, reste, expiré (à la date)."""
        return etat_des_ordres(self.mouvements(jusqu_a=date))

    def memoire(self, date: Any = None) -> dict[str, Any]:
        """État pour ``recommend --suivi`` (§F13a) : titres détenus, liquidités réelles, date et année de la dernière
        remise à niveau de janvier (``memoire_ref`` = ``{"annee", "date"}``), quantités de l'ordre d'origine non servies.
        Aucune remise à niveau au carnet : ``memoire_ref`` vide."""
        pos = self.positions(date)
        ords = self.ordres(date)
        rem = [o for o in ords if str(o.get("motif") or "") == "remise_a_niveau"]
        ref = None
        non_servis: dict[str, int] = {}
        if rem:
            def _dec(o: Mapping[str, Any]) -> pd.Timestamp:
                return pd.Timestamp(o.get("date_decision") or o["date"]).normalize()

            dmax = max(_dec(o) for o in rem)
            ref = {"annee": int(dmax.year), "date": dmax.date().isoformat()}
            for o in rem:
                if _dec(o) == dmax and o["sens"] == "achat" and o["reste"] > 0 and o["etat"] == "expiré":
                    non_servis[o["symbole"]] = non_servis.get(o["symbole"], 0) + int(o["reste"])
        return {"titres": {k: int(v["titres"]) for k, v in pos.items()}, "liquidites": self.liquidites(date),
                "memoire_ref": ref, "non_servis": non_servis, "nom": self.nom}

    # -- avis d'opéré ----------------------------------------------------------------------------

    def saisir_avis(self, lignes: Sequence[Mapping[str, Any]], grille: Any = None, *, ajouter: bool = True,
                    maintenant: Any = None) -> dict[str, Any]:
        """Avis d'opéré (mode réel) : chaque ligne (``date, symbole, sens, titres, prix, courtage, taxe, commissions`` ou
        ``brvm`` et ``dcbr``, ``autres_frais``, ``total`` ; ``cours_reference`` facultatif) est comparée à la grille au
        franc près. Taux déduits : courtage ÷ montant ; taxe ÷ courtage ; commissions ÷ montant.

        Si tout concorde : la grille rendue passe ses champs (courtage, taxe) au statut ``avis d'opéré``. Sinon l'écart
        est rendu en FCFA et une grille corrigée est **proposée** (``grille_proposee``), jamais appliquée ici. Les
        frais inconnus de la grille (``autres_frais``) sont gardés comme postes nouveaux. Coût dans le prix mesuré =
        (prix payé − cours de référence) × titres. ``ajouter`` : les exécutions entrent au carnet (source
        ``avis_opere``)."""
        from brvm_alpha.rendement import grille as _gr

        g = grille if grille is not None else _gr.defaut()
        out_l: list[dict[str, Any]] = []
        concorde = True
        nouveaux: list[dict[str, Any]] = []
        mouv: list[dict[str, Any]] = []
        for l in lignes:
            n, px = int(_f(l.get("titres"))), _f(l.get("prix"))
            a = n * px
            attendu = _gr.frais_explicites(a, g)
            lu = {"courtage": _f(l.get("courtage")), "taxe": _f(l.get("taxe")),
                  "brvm": _f(l.get("brvm", _f(l.get("commissions")) * 2 / 3 if l.get("commissions") is not None else 0)),
                  "dcbr": _f(l.get("dcbr", _f(l.get("commissions")) / 3 if l.get("commissions") is not None else 0))}
            comm = _f(l.get("commissions")) if l.get("commissions") is not None else lu["brvm"] + lu["dcbr"]
            ecarts = {"courtage": int(round(lu["courtage"] - attendu["courtage"])),
                      "taxe": int(round(lu["taxe"] - attendu["tva"])),
                      "commissions": int(round(comm - attendu["brvm"] - attendu["dcbr"]))}
            ok = all(abs(v) <= 1 for v in ecarts.values())
            concorde = concorde and ok
            autres = _f(l.get("autres_frais"))
            if autres > 0:
                nouveaux.append({"symbole": l.get("symbole"), "date": l.get("date"), "montant": autres,
                                 "libelle": str(l.get("libelle_autres") or "autres frais de l'avis")})
            ref = l.get("cours_reference")
            cp = int(round(n * (px - _f(ref)))) if ref is not None and str(l.get("sens")) == "achat" else (
                int(round(n * (_f(ref) - px))) if ref is not None else None)
            out_l.append({"symbole": l.get("symbole"), "date": l.get("date"), "montant": int(round(a)), "lu": lu,
                          "attendu": attendu, "ecarts_fcfa": ecarts, "concorde": ok,
                          "taux": {"courtage": lu["courtage"] / a if a else None,
                                   "taxe": lu["taxe"] / lu["courtage"] if lu["courtage"] else None,
                                   "commissions": comm / a if a else None},
                          "cout_prix_mesure": cp, "total": _f(l.get("total")) if l.get("total") is not None else None})
            mouv.append({"type": "execution", "date": l.get("date"), "symbole": l.get("symbole"), "sens": l.get("sens"),
                         "titres": n, "prix": px, "source": "avis_opere",
                         "frais": {"courtage": lu["courtage"], "taxe": lu["taxe"], "brvm": lu["brvm"], "dcbr": lu["dcbr"],
                                   "autres": autres},
                         "cours_reference": _f(ref) if ref is not None else None, "ordre": l.get("ordre")})
        grille_out = g
        proposee = None
        if concorde and out_l:
            grille_out = copy.deepcopy(g)
            for k in ("courtage", "taxe_courtage"):
                grille_out.champs[k].statut = _gr.AVIS
                grille_out.champs[k].source = "avis d'opéré"
        elif out_l:
            tot_a = sum(x["montant"] for x in out_l)
            tot_c = sum(x["lu"]["courtage"] for x in out_l)
            proposee = copy.deepcopy(g).avec(courtage=round(tot_c / tot_a, 6) if tot_a else g.valeur("courtage"))
        if ajouter and mouv:
            self.ajouter_plusieurs(mouv, maintenant=maintenant)
        return {"concorde": bool(concorde and out_l), "lignes": out_l, "grille": grille_out, "grille_proposee": proposee,
                "postes_nouveaux": nouveaux,
                "texte": ("Tous les frais concordent avec la grille au franc près : statut « avis d'opéré »."
                          if concorde and out_l else
                          "Écart avec la grille : correction proposée, appliquée seulement après votre confirmation.")}


def ouvrir(nom: str, dossier: str | Path | None = None, *, creer: bool = True) -> Carnet:
    """Carnet ``<dossier>/<nom>/carnet.jsonl`` (``dossier`` : défaut ``<données>/suivi``, jamais sous ``reports/``)."""
    c = Carnet(nom, dossier)
    if creer:
        c.dossier.mkdir(parents=True, exist_ok=True)
    return c


# ---------------------------------------------------------------------------
# Calculs sur des mouvements (sans fichier)
# ---------------------------------------------------------------------------


def operations_depuis_mouvements(mouvements: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Opérations (format ``operations.csv``) d'une liste de mouvements actifs : achats et ventes (frais détaillés,
    coût dans le prix contre le cours de référence de l'ordre), dividendes nets, frais fixes, apports, retraits, divisions
    (``titres`` = titres créés). ``montant_net`` est le flux de liquidités signé."""
    rows: list[dict[str, Any]] = []
    held: dict[str, int] = {}
    ordres = {int(m["n"]): m for m in mouvements if m.get("type") == "ordre" and m.get("n") is not None}
    for m in sorted(mouvements, key=lambda x: (pd.Timestamp(x["date"]), int(x.get("n", 0)))):
        ty = m.get("type")
        base = {c: 0.0 for c in COLONNES_OPERATIONS}
        base.update(date=pd.Timestamp(m["date"]).normalize(), symbole=m.get("symbole") or "", source=m.get("source") or
                    "saisie", cours_reference=None, ordre=m.get("ordre"))
        if ty == "execution":
            n, px = int(m["titres"]), _f(m["prix"])
            fr = m.get("frais") or {}
            ref = m.get("cours_reference")
            if ref is None and m.get("ordre") is not None and int(m["ordre"]) in ordres:
                ref = ordres[int(m["ordre"])].get("cours_reference")
            ref = _f(ref, px) if ref is not None else px
            brut = n * px
            tot = _frais_total(fr)
            cp = n * (px - ref) if m["sens"] == "achat" else n * (ref - px)
            base.update(type=m["sens"], titres=n, prix=px, courtage=_f(fr.get("courtage")), taxe=_f(fr.get("taxe")),
                        brvm=_f(fr.get("brvm")), dcbr=_f(fr.get("dcbr")), autres_frais=_f(fr.get("autres")),
                        cout_prix=cp, cours_reference=ref,
                        montant_net=-(brut + tot) if m["sens"] == "achat" else brut - tot)
            held[m["symbole"]] = held.get(m["symbole"], 0) + (n if m["sens"] == "achat" else -n)
        elif ty == "dividende":
            base.update(type="dividende", titres=int(_f(m.get("titres"))), prix=_f(m.get("net_par_titre")),
                        montant_net=_f(m.get("montant")))
        elif ty == "frais":
            base.update(type="frais_fixes", autres_frais=_f(m.get("montant")), montant_net=-_f(m.get("montant")),
                        symbole=str(m.get("nature") or ""))
        elif ty == "apport":
            n = int(_f(m.get("titres")))
            if n > 0:
                base.update(type="apport", titres=n, prix=_f(m.get("cours")), montant_net=0.0)
                held[m["symbole"]] = held.get(m["symbole"], 0) + n
            else:
                base.update(type="apport", montant_net=_f(m.get("montant")))
        elif ty == "retrait":
            base.update(type="retrait", montant_net=-_f(m.get("montant")))
        elif ty == "division":
            h = held.get(m["symbole"], 0)
            neuf = int(math.floor(h * _f(m.get("rapport")) + 1e-9))
            base.update(type="division", titres=neuf - h, prix=_f(m.get("rapport")), montant_net=0.0)
            held[m["symbole"]] = neuf
        else:
            continue
        rows.append(base)
    df = pd.DataFrame(rows, columns=list(COLONNES_OPERATIONS))
    if len(df):
        df["date"] = pd.to_datetime(df["date"])
    return df


def positions_depuis_operations(ops: pd.DataFrame, date: Any = None) -> dict[str, dict[str, Any]]:
    """Lignes à ``date`` rejouées depuis des opérations : titres, prix de revient (frais facturés compris), coût,
    cours de référence moyen, résultat réalisé, dividendes reçus, date du premier achat de la ligne en cours."""
    out: dict[str, dict[str, Any]] = {}
    if ops is None or not len(ops):
        return out
    f = ops if date is None else ops[pd.to_datetime(ops["date"]) <= pd.Timestamp(date).normalize()]
    for r in f.itertuples(index=False):
        s = str(r.symbole)
        ty = r.type
        if ty in ("achat", "vente", "division", "dividende") or (ty == "apport" and _f(r.titres) > 0):
            p = out.setdefault(s, {"symbole": s, "titres": 0, "cout": 0.0, "ref_total": 0.0, "resultat_realise": 0.0,
                                   "frais_vente": 0.0, "dividendes_recus": 0.0, "premier_achat": None,
                                   "prix_de_revient": None, "cours_reference_moyen": None})
        else:
            continue
        frais = _f(r.courtage) + _f(r.taxe) + _f(r.brvm) + _f(r.dcbr) + _f(r.autres_frais)
        n = int(_f(r.titres))
        if ty in ("achat", "apport"):
            if p["titres"] == 0:
                p["premier_achat"] = pd.Timestamp(r.date)
                p["cout"], p["ref_total"] = 0.0, 0.0
            p["titres"] += n
            p["cout"] += n * _f(r.prix) + (frais if ty == "achat" else 0.0)
            ref = _f(r.cours_reference, _f(r.prix)) if r.cours_reference is not None and not pd.isna(r.cours_reference) \
                else _f(r.prix)
            p["ref_total"] += n * ref
        elif ty == "vente":
            if n > p["titres"]:
                raise ValueError(f"vente de {n} titres {s} pour {p['titres']} détenus")
            pr = p["cout"] / p["titres"] if p["titres"] else 0.0
            rm = p["ref_total"] / p["titres"] if p["titres"] else 0.0
            p["resultat_realise"] += n * (_f(r.prix) - pr) - frais
            p["frais_vente"] += frais
            p["cout"] -= n * pr
            p["ref_total"] -= n * rm
            p["titres"] -= n
            if p["titres"] == 0:
                p["cout"], p["ref_total"] = 0.0, 0.0
        elif ty == "division":
            p["titres"] += n
        elif ty == "dividende":
            p["dividendes_recus"] += _f(r.montant_net)
        p["prix_de_revient"] = p["cout"] / p["titres"] if p["titres"] else None
        p["cours_reference_moyen"] = p["ref_total"] / p["titres"] if p["titres"] else None
    return out


def positions_depuis_mouvements(mouvements: Sequence[Mapping[str, Any]], date: Any = None) -> dict[str, dict[str, Any]]:
    return positions_depuis_operations(operations_depuis_mouvements(mouvements), date)


def lignes_depuis_operations(ops: pd.DataFrame) -> list[dict[str, Any]]:
    """Opérations en lignes de dictionnaires (pour ``operations.csv``), montants au centime."""
    out = []
    for r in ops.to_dict("records"):
        r = dict(r)
        r["date"] = pd.Timestamp(r["date"]).date().isoformat()
        out.append(r)
    return out


def etat_des_ordres(mouvements: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Ordres du carnet avec leurs exécutions : titres servis, reste, état (``en cours``, ``servi``, ``expiré``,
    ``ressaisi``), séances pour finir (si servi)."""
    ords = {int(m["n"]): {**m, "servis": 0, "executions": [], "etat": "en cours", "reste": int(m["titres"]),
                          "expire_le": None}
            for m in mouvements if m.get("type") == "ordre"}
    for m in mouvements:
        if m.get("type") == "execution" and m.get("ordre") is not None and int(m["ordre"]) in ords:
            o = ords[int(m["ordre"])]
            o["servis"] += int(m["titres"])
            o["executions"].append({"date": m["date"], "titres": int(m["titres"]), "prix": _f(m["prix"])})
        elif m.get("type") == "expiration" and m.get("ordre") is not None and int(m["ordre"]) in ords:
            ords[int(m["ordre"])]["etat"] = "expiré"
            ords[int(m["ordre"])]["expire_le"] = m["date"]
        elif m.get("type") == "ordre" and m.get("ressaisie_de") is not None and int(m["ressaisie_de"]) in ords:
            ords[int(m["ressaisie_de"])]["etat"] = "ressaisi"
    for o in ords.values():
        o["reste"] = max(0, int(o["titres"]) - int(o["servis"]))
        if o["etat"] == "en cours" and o["reste"] == 0:
            o["etat"] = "servi"
    return [ords[k] for k in sorted(ords)]
