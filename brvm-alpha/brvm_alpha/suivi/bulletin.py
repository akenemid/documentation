"""F10 — Ligne de la semaine, journal hebdomadaire chaîné et bulletin (texte, Markdown, JSON).

Cahier ``docs/RENDEMENT_NET.md``, §F10. Chaque semaine, sans commande à taper, un bulletin dit d'où vient chaque franc
gagné ou perdu : cours, dividendes reçus, frais d'achat et de vente, frais annuels prélevés ; les frais partis pour de
bon et les baisses de cours non vendues (qui peuvent se retourner ou s'aggraver) ; trois feux ; l'écart du panier de
référence au marché, en valeur de part.

* :func:`lignes_semaines` : une ligne par semaine (vendredi v ; t = dernière séance disponible ≤ v), pont à une seule
  base (:mod:`~brvm_alpha.suivi.etat`), identité au franc ;
* :func:`ecrire_semaines` : ``semaines.csv`` en ajout seul, ``empreintes.jsonl`` (SHA-256 de chaque ligne, chaînées) ;
  deux lancements la même semaine donnent une seule ligne ; une ligne déjà écrite n'est jamais réécrite : si le
  recalcul diffère, une entrée « le passé a changé » est ajoutée à ``anomalies.jsonl`` (feu « Données » rouge) ;
* :func:`bulletin` et :func:`rendre` : le bulletin de la semaine (gabarit du §F10), sans mot interdit (§1.1).

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from brvm_alpha import suivi as _s
from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.suivi import etat as _et

__all__ = ["COLONNES", "ENTETE", "LIGNE_MARCHE", "bulletin", "depuis_journal", "dernier_vendredi",
           "dividendes_non_credites", "ecrire_semaines", "lignes_semaines", "lire_semaines", "premiere_seance",
           "prevu_depuis_projection", "semaine_pour_feux", "semaines_du_journal", "remise_a_niveau_suivante",
           "rendez_vous", "rendre", "vendredis", "verifier_semaines"]

#: Colonnes de ``semaines.csv`` (montants en FCFA, au franc ; parts et écarts au millionième).
COLONNES = ("semaine", "vendredi", "date", "valeur_titres", "liquidites", "valeur", "argent_engage", "ecart",
            "effet_cours", "dividendes_recus", "frais_transaction", "frais_factures", "cout_prix", "frais_fixes",
            "interets", "ecart_identite", "fuites_definitives", "pertes_non_realisees", "pertes_realisees", "a_recevoir",
            "part_investie", "argent_qui_dort", "argent_qui_dort_prevu", "indice_tr", "valeur_de_part", "ecart_au_marche",
            "ordres_emis", "ordres_servis", "ordres_expires", "titres_demandes", "titres_servis", "bulletins_manquants",
            "variation_semaine", "variation_cours", "variation_dividendes", "variation_frais_transaction",
            "variation_frais_fixes", "variation_interets")
_FRANCS = {"valeur_titres", "liquidites", "valeur", "argent_engage", "ecart", "effet_cours", "dividendes_recus",
           "frais_transaction", "frais_factures", "cout_prix", "frais_fixes", "interets", "fuites_definitives",
           "pertes_non_realisees", "pertes_realisees", "a_recevoir", "argent_qui_dort", "argent_qui_dort_prevu",
           "variation_semaine", "variation_cours", "variation_dividendes", "variation_frais_transaction",
           "variation_frais_fixes", "variation_interets"}
_ENTIERS = {"semaine", "ordres_emis", "ordres_servis", "ordres_expires", "titres_demandes", "titres_servis",
            "bulletins_manquants"}
ENTETE = "BULLETIN DE LA SEMAINE"
LIGNE_MARCHE = "LE PANIER DE RÉFÉRENCE FACE AU MARCHÉ"
RETARD_ATTENDU = ("retard attendu la 1re année : 3,3 à 4,2 points ; avant plusieurs années, cet écart ne prouve rien")


def _f(x: Any, defaut: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return defaut
    return v if math.isfinite(v) else defaut


def vendredis(debut: Any, fin: Any) -> list[pd.Timestamp]:
    """Vendredis de la première semaine qui contient ``debut`` jusqu'au dernier vendredi ≤ ``fin``."""
    d0, d1 = pd.Timestamp(debut).normalize(), pd.Timestamp(fin).normalize()
    v = d0 + pd.Timedelta(days=(4 - d0.weekday()) % 7)
    out = []
    while v <= d1:
        out.append(v)
        v += pd.Timedelta(days=7)
    return out


def _seances_ouvrees(a: pd.Timestamp, b: pd.Timestamp) -> list[pd.Timestamp]:
    from brvm_alpha.portfolio import recommend as R

    return [d for d in pd.bdate_range(a, b) if not R._is_fixed_holiday(d)]


def _bulletins_manquants(panels: Mapping[str, Any], seances: pd.DatetimeIndex, a: pd.Timestamp, b: pd.Timestamp) -> int:
    """Séances de la semaine ``]a ; b]`` sans bulletin : table ``sessions`` du panel (``available`` faux) si elle existe,
    sinon jours ouvrés (hors fériés à date fixe) absents du panel."""
    ses = panels.get("sessions") if isinstance(panels, Mapping) else None
    if isinstance(ses, pd.DataFrame) and {"date", "available"} <= set(ses.columns):
        d = pd.to_datetime(ses["date"]).dt.normalize()
        m = (d > a) & (d <= b)
        return int((~ses.loc[m, "available"].astype(bool)).sum())
    ouv = _seances_ouvrees(a + pd.Timedelta(days=1), b)
    have = set(pd.DatetimeIndex(seances))
    return int(sum(1 for d in ouv if d not in have))


def remise_a_niveau_suivante(t: Any) -> pd.Timestamp:
    """Prochaine remise à niveau de fin janvier : dernière séance ouvrée de janvier (hors fériés à date fixe) après t."""
    d = pd.Timestamp(t).normalize()
    an = d.year if d.month == 1 else d.year + 1
    for _ in range(2):
        j = [x for x in _seances_ouvrees(pd.Timestamp(an, 1, 1), pd.Timestamp(an, 1, 31))]
        if j and j[-1] > d:
            return j[-1]
        an += 1
    return pd.Timestamp(an, 1, 31)


def _ordres_semaine(ordres: Sequence[Mapping[str, Any]] | None, a: pd.Timestamp, b: pd.Timestamp) -> dict[str, int]:
    out = {"ordres_emis": 0, "ordres_servis": 0, "ordres_expires": 0, "titres_demandes": 0, "titres_servis": 0}
    for o in ordres or []:
        d = pd.Timestamp(o.get("date")).normalize()
        if a < d <= b and not o.get("ressaisie_de"):
            out["ordres_emis"] += 1
            out["titres_demandes"] += int(_f(o.get("titres")))
        servi = False
        for e in o.get("executions") or []:
            de = pd.Timestamp(e["date"]).normalize()
            if a < de <= b:
                out["titres_servis"] += int(_f(e.get("titres")))
                servi = True
        if servi:
            out["ordres_servis"] += 1
        exp = o.get("expire_le")
        if o.get("etat") == "expiré" and exp is not None and a < pd.Timestamp(exp).normalize() <= b:
            out["ordres_expires"] += 1
    return out


def lignes_semaines(ops: pd.DataFrame, panels: Mapping[str, Any], *, debut: Any, fin: Any = None,
                    jusqu_au: Any = None, ordres: Sequence[Mapping[str, Any]] | None = None,
                    detaches: pd.DataFrame | None = None,
                    prevu: Callable[[pd.Timestamp, Mapping[str, Any]], float] | None = None,
                    reglages: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Lignes de la semaine de ``debut`` à ``fin`` (défaut : dernière séance du panel), une par vendredi v :
    t = dernière séance disponible ≤ v. Champs : ``COLONNES`` (valeur, liquidités, argent engagé, écart et pont, fuites
    définitives, baisses de cours non vendues, part investie, argent qui dort et ce que la règle déclarée prévoit,
    indice, valeur de part, écart au marché, ordres, bulletins manquants, variation de la semaine avec le même pont).

    ``prevu(t, ligne)`` : argent qui dort prévu par la règle déclarée à la date t (projection de F7 d, voir
    :func:`prevu_depuis_projection`) ; il rend ``None`` hors de la période projetée. Sans ``prevu`` : ``None`` (« non
    calculé ») — jamais l'argent qui dort du portefeuille lui-même, qui rendrait la condition (b) du feu « Fuites »
    verte par construction. Pour ``REF-S2`` et ``N``, qui sont la règle déclarée, l'appelant passe l'identité.
    ``detaches`` : dividendes détachés (``symbole, date_detachement, date_paiement, montant``) pour la
    colonne « à recevoir », hors identité. ``jusqu_au`` : date du jour ; seules les semaines finies (vendredi ≤
    ``jusqu_au``, défaut : dernière séance du panel) ont une ligne, pour qu'une semaine en cours ne soit jamais écrite
    puis « changée ». Un vendredi sans bulletin prend la dernière séance disponible."""
    d0 = _s.refuser_s1(debut, "le début du suivi")
    px = _et.prix_valorisation(panels)
    seances = pd.DatetimeIndex(px.index)
    d1 = pd.Timestamp(fin).normalize() if fin is not None else seances[-1]
    s = _et.serie(ops, panels, debut=d0, fin=d1, prix=px)
    part_regle = float(_rg.lire(reglages, "liquidites.part_reserve_regle", 0.02))
    out: list[dict[str, Any]] = []
    prec: dict[str, Any] | None = None
    i0 = s["indice"].iloc[0] if len(s) else float("nan")
    u0 = float(s["u"].iloc[0]) if len(s) else 1.0
    cloture = max(d1, pd.Timestamp(jusqu_au).normalize()) if jusqu_au is not None else d1
    for k, v in enumerate(vendredis(d0, cloture), start=1):
        dispo = s.index[s.index <= v]
        if not len(dispo):
            continue
        t = dispo[-1]
        r = s.loc[t]
        a = v - pd.Timedelta(days=7)
        V, L, T = float(r["V"]), float(r["L"]), float(r["T"])
        st = _et.etat(ops, panels, t, detaches=detaches, debut=d0) if len(ops) else None
        ligne: dict[str, Any] = {
            "semaine": k, "vendredi": v.date().isoformat(), "date": t.date().isoformat(), "valeur_titres": T,
            "liquidites": L, "valeur": V, "argent_engage": float(r["K"]), "ecart": float(r["E"]),
            "effet_cours": float(r["effet_cours"]), "dividendes_recus": float(r["dividendes_recus"]),
            "frais_transaction": float(r["frais_transaction"]), "frais_factures": float(r["frais_factures"]),
            "cout_prix": float(r["cout_prix"]), "frais_fixes": float(r["frais_fixes"]), "interets": float(r["interets"]),
            "ecart_identite": float(r["ecart_identite"]),
            "fuites_definitives": float(r["frais_transaction"] + r["frais_fixes"]),
            "pertes_non_realisees": float(st["pertes_non_realisees"]) if st else 0.0,
            "pertes_realisees": float(st["pertes_realisees"]) if st else 0.0,
            "a_recevoir": float(st["a_recevoir"]["total"]) if st else 0.0,
            "part_investie": float(r["part_investie"]), "argent_qui_dort": L - part_regle * V,
            "indice_tr": float(r["indice"]) if pd.notna(r["indice"]) else None, "valeur_de_part": float(r["u"]),
            "ecart_au_marche": (float(r["u"]) / u0) / (float(r["indice"]) / float(i0)) - 1.0
            if pd.notna(r["indice"]) and pd.notna(i0) and float(i0) > 0 and float(r["indice"]) > 0 else None,
            **_ordres_semaine(ordres, a, v),
            "bulletins_manquants": _bulletins_manquants(panels, seances, max(a, d0 - pd.Timedelta(days=1)), v)}
        pv = prevu(t, ligne) if prevu is not None else None
        ligne["argent_qui_dort_prevu"] = float(pv) if pv is not None else None
        for cle, comp in (("variation_cours", "effet_cours"), ("variation_dividendes", "dividendes_recus"),
                          ("variation_frais_transaction", "frais_transaction"), ("variation_frais_fixes", "frais_fixes"),
                          ("variation_interets", "interets")):
            ligne[cle] = ligne[comp] - (prec[comp] if prec else 0.0)
        ligne["variation_semaine"] = ligne["ecart"] - (prec["ecart"] if prec else 0.0)
        if st:
            ligne["_lignes"] = st["lignes"]
        out.append(ligne)
        prec = ligne
    return out


# ---------------------------------------------------------------------------
# semaines.csv, empreintes.jsonl, anomalies.jsonl
# ---------------------------------------------------------------------------


def _fmt(c: str, v: Any) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ""
    if c in _FRANCS:
        from brvm_alpha.portfolio import recommend as R

        return str(R.round_fcfa(_f(v)))
    if c in _ENTIERS:
        return str(int(_f(v)))
    if isinstance(v, (int, float)):
        return f"{float(v):.6f}"
    return str(v)


def _texte_ligne(l: Mapping[str, Any]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow([_fmt(c, l.get(c)) for c in COLONNES])
    return buf.getvalue()


def lire_semaines(nom: str, dossier: str | Path | None = None) -> pd.DataFrame:
    """``semaines.csv`` d'un portefeuille (tableau vide s'il n'existe pas)."""
    p = _s.dossier_portefeuille(nom, dossier) / "semaines.csv"
    if not p.exists():
        return pd.DataFrame(columns=list(COLONNES))
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def verifier_semaines(nom: str, dossier: str | Path | None = None) -> dict[str, Any]:
    """Chaîne de ``semaines.csv`` : chaque ligne a son empreinte dans ``empreintes.jsonl``, chaînée à la précédente.
    Toute réécriture d'une ligne la rompt (feu « Données » rouge)."""
    d = _s.dossier_portefeuille(nom, dossier)
    p = d / "semaines.csv"
    lignes = p.read_text(encoding="utf-8").splitlines()[1:] if p.exists() else []
    emp = [o for _t, o in _s.lire_jsonl(d / "empreintes.jsonl") if o is not None]
    anomalies = []
    chaine = _s.ZERO
    if len(emp) != len(lignes):
        anomalies.append(f"{len(lignes)} lignes pour {len(emp)} empreintes")
    for i, (txt, e) in enumerate(zip(lignes, emp), start=1):
        h = _s.empreinte_texte(txt)
        chaine = _s.empreinte_texte(chaine + h)
        if e.get("ligne") != h or e.get("chaine") != chaine:
            anomalies.append(f"semaine {i} : ligne réécrite ou chaîne rompue")
    return {"ok": not anomalies, "chaine_ok": not anomalies, "n": len(lignes), "anomalies": anomalies,
            "derniere_chaine": chaine}


def ecrire_semaines(nom: str, lignes: Sequence[Mapping[str, Any]], dossier: str | Path | None = None, *,
                    maintenant: Any = None) -> dict[str, Any]:
    """Écrit les semaines nouvelles à la fin de ``semaines.csv`` (ajout seul) et leurs empreintes chaînées.

    Une semaine déjà écrite n'est jamais réécrite : si son recalcul est identique, rien ne change (idempotence) ; s'il
    diffère, une entrée est ajoutée à ``anomalies.jsonl`` (« le passé a changé », cause probable : donnée corrigée), une
    seule fois par écart. Rend ``{"ajoutees", "identiques", "anomalies", "passe_a_change"}``."""
    d = _s.dossier_portefeuille(nom, dossier, creer=True)
    p = d / "semaines.csv"
    v = verifier_semaines(nom, dossier)
    t = pd.Timestamp(maintenant) if maintenant is not None else pd.Timestamp.now(tz="UTC")
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    existants: dict[str, str] = {}
    if p.exists():
        rows = p.read_text(encoding="utf-8").splitlines()[1:]
        for txt in rows:
            existants[next(csv.reader([txt]))[1]] = txt
    anomalies_vues = {(o.get("vendredi"), o.get("recalcule")) for _t, o in _s.lire_jsonl(d / "anomalies.jsonl") if o}
    nouvelles, identiques, anomalies = [], 0, []
    for l in lignes:
        txt = _texte_ligne(l)
        cle = str(l.get("vendredi"))
        if cle in existants:
            if existants[cle] == txt:
                identiques += 1
            elif (cle, _s.empreinte_texte(txt)) not in anomalies_vues:
                anomalies.append({"date_utc": t.isoformat(), "vendredi": cle, "cause": "le passé a changé",
                                  "cause_probable": "donnée corrigée", "ecrit": _s.empreinte_texte(existants[cle]),
                                  "recalcule": _s.empreinte_texte(txt)})
            continue
        if existants and cle < max(existants):
            continue  # une semaine antérieure à la dernière écrite ne s'insère pas : le fichier est en ajout seul
        nouvelles.append(txt)
        existants[cle] = txt
    if not p.exists():
        p.write_text(",".join(COLONNES) + "\n", encoding="utf-8")
    if nouvelles:
        with p.open("a", encoding="utf-8") as fh:
            for txt in nouvelles:
                fh.write(txt + "\n")
        chaine = v["derniere_chaine"]
        emp = []
        n0 = v["n"]
        for i, txt in enumerate(nouvelles, start=1):
            h = _s.empreinte_texte(txt)
            chaine = _s.empreinte_texte(chaine + h)
            emp.append({"n": n0 + i, "vendredi": next(csv.reader([txt]))[1], "ligne": h, "chaine": chaine})
        _s.ajouter_jsonl(d / "empreintes.jsonl", emp)
    if anomalies:
        _s.ajouter_jsonl(d / "anomalies.jsonl", anomalies)
    toutes = [o for _t, o in _s.lire_jsonl(d / "anomalies.jsonl") if o]
    return {"ajoutees": len(nouvelles), "identiques": identiques, "anomalies": anomalies,
            "passe_a_change": bool(toutes), "chaine": verifier_semaines(nom, dossier)}


# ---------------------------------------------------------------------------
# Bulletin
# ---------------------------------------------------------------------------


def _signe(x: Any) -> str:
    return _rg.fcfa(x, signe=True, unite=False)


def _plier(lignes: Sequence[str], largeur: int = 100) -> list[str]:
    """Lignes de 100 colonnes au plus ; une ligne pliée garde le retrait de sa première ligne (« FEU … » : 14)."""
    import textwrap

    out: list[str] = []
    for l in lignes:
        if len(l) <= largeur:
            out.append(l)
            continue
        retrait = " " * (len(l) - len(l.lstrip(" ")))
        if l.startswith("FEU "):
            retrait = " " * 14
        out.extend(textwrap.wrap(l, largeur, subsequent_indent=retrait, break_long_words=False,
                                 break_on_hyphens=False))
    return out


def dernier_vendredi(jour: Any) -> pd.Timestamp:
    """Dernier vendredi au plus tard à ``jour`` (``jour`` lui-même si c'est un vendredi)."""
    d = pd.Timestamp(jour).normalize()
    return d - pd.Timedelta(days=(d.weekday() - 4) % 7)


def premiere_seance(date: Any) -> pd.Timestamp:
    """Première séance ouvrée (hors fériés à date fixe) à partir de ``date``."""
    d = pd.Timestamp(date).normalize()
    return _seances_ouvrees(d, d + pd.Timedelta(days=14))[0]


def bulletin(ligne: Mapping[str, Any] | None, *, nom: str = "", feux: Mapping[str, Any] | None = None,
             a_revoir: Sequence[Mapping[str, Any]] | None = None, rendez_vous: Mapping[str, Any] | None = None,
             ecart_marche_temoin: float | None = None, papier: bool = True, aujourd_hui: Any = None,
             debut_suivi: str | None = None, argent_engage: float | None = None, premier_achat: Any = None,
             reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Bulletin de la semaine (gabarit du §F10), structuré : ``lignes`` de texte et ``valeurs``. ``ligne`` : dernière
    ligne du journal (``None`` : semaine 0, état avant achat et prochains rendez-vous seulement ; l'en-tête porte alors
    le dernier vendredi au plus tard à la date du jour). ``feux`` : sortie de ``rendement.alertes.feux`` ;
    ``a_revoir`` : lignes « à revoir, pas à vendre ». Semaine 0 : ``argent_engage`` et ``premier_achat`` (pour
    ``REF-S2`` et ``N`` : le capital du témoin et la première séance du suivi, par défaut). L'écart au marché du panier
    de référence est celui de ``REF-S2`` : pour un autre portefeuille, ``ecart_marche_temoin`` (sinon « non calculé »).
    Aucun mot interdit (§1.1)."""
    jour = aujourd_hui if aujourd_hui is not None else _dt.date.today()
    debut = debut_suivi or str(_rg.lire(reglages, "dates.debut_suivi", "2026-12-01"))
    L: list[str] = []
    zero = not ligne or (abs(_f(ligne.get("valeur_titres"))) < 0.5 and not _f(ligne.get("frais_transaction")))
    v = pd.Timestamp(ligne["vendredi"]) if ligne else dernier_vendredi(jour)
    numero = int(_f(ligne.get("semaine"))) if ligne and not zero else 0
    moteur = nom in ("REF-S2", "N")
    if zero and moteur:
        if argent_engage is None:
            argent_engage = float(_rg.lire(reglages, "suivi.capital_temoin_fcfa", 10_000_000))
        if premier_achat is None:
            premier_achat = premiere_seance(debut)
    genre = "portefeuille sur papier" if papier else "portefeuille réel"
    L.append(f"{ENTETE} — vendredi {_rg.date_fr(v)} — semaine {numero} — {genre}")
    L.append(f"{_rg.BANNER} Étude seulement.")
    L.append(_rg.PH_ETUDE)
    L.append(_rg.phrase_seance(jour, reglages))
    L.append("")
    if zero:
        engage = argent_engage if argent_engage is not None else (ligne.get("argent_engage") if ligne else None)
        txt0 = "Le suivi sur papier n'a pas encore d'opération : état avant achat."
        if engage is not None and _f(engage):
            txt0 += f" Argent engagé : {_rg.fcfa(engage)} (en liquidités)"
            txt0 += (f" ; premier achat prévu à la séance du {_rg.date_fr(premier_achat)}." if premier_achat is not None
                     else ".")
        L.append(txt0)
    else:
        L.append(f"Mon portefeuille vaut {_rg.fcfa(ligne['valeur'])}. Depuis le départ : {_signe(ligne['ecart'])} FCFA. "
                 f"Depuis la semaine dernière : {_signe(ligne['variation_semaine'])} FCFA.")
        L.append(f"   cours {_signe(ligne['effet_cours'])} ; dividendes reçus {_signe(ligne['dividendes_recus'])} ; frais "
                 f"d'achat et de vente {_signe(-_f(ligne['frais_transaction']))} ; frais annuels prélevés "
                 f"{_signe(-_f(ligne['frais_fixes']))}")
        L.append(f"   Frais partis pour de bon : {_rg.fcfa(ligne['fuites_definitives'])}. Baisses de cours non vendues : "
                 f"{_rg.fcfa(-_f(ligne['pertes_non_realisees']))} (elles peuvent se retourner")
        L.append("   ou s'aggraver).")
        if _f(ligne.get("a_recevoir")) > 0:
            L.append(f"   Dividendes à recevoir (détachés, pas encore payés) : {_rg.fcfa(ligne['a_recevoir'])}.")
    L.append("")
    fx = feux or {}
    for cle, lib in (("perte", "FEU PERTE    "), ("fuites", "FEU FUITES   "), ("donnees", "FEU DONNÉES  ")):
        f = fx.get(cle) or {"affichage": "—", "phrase": "le suivi n'a pas commencé"}
        L.append(f"{lib} {f.get('affichage', '—'):<8} {f.get('phrase', '')}".rstrip())
        if f.get("rappel"):
            L.append(f"              {f['rappel']}")
    L.append("")
    rv = list(a_revoir or [])
    if rv:
        L.append(f"À REVOIR (pas à vendre) : {len(rv)} ligne(s) : "
                 + " ; ".join(f"{x['symbole']} ({x['motifs'][0]})" for x in rv[:5]) + ".")
    else:
        L.append("À REVOIR (pas à vendre) : aucune ligne.")
    rdv = rendez_vous or {}
    morceaux = []
    if rdv.get("dividende"):
        dv = rdv["dividende"]
        morceaux.append(f"dividende attendu {dv['symbole']} vers le {_rg.date_fr(dv['date'])} "
                        f"({_rg.fcfa(dv['montant'])}, estimé)")
    elif zero or rdv.get("sans_titres"):
        morceaux.append("pas encore de titres")
    elif "titres" in rdv:
        morceaux.append("aucun dividende attendu dans les 12 mois")
    else:
        morceaux.append("prochain dividende : non calculé")
    if rdv.get("prelevement") and not zero:
        pr = rdv["prelevement"]
        morceaux.append(f"prélèvement de frais vers le {_rg.date_fr(pr['date'])} (environ {_rg.fcfa(pr['montant'])}, "
                        "supposé)")
    morceaux.append(f"remise à niveau le {_rg.date_fr(rdv.get('remise_a_niveau') or remise_a_niveau_suivante(v))}")
    L.append("PROCHAINS RENDEZ-VOUS : " + " ; ".join(morceaux))
    if ecart_marche_temoin is not None:
        em = ecart_marche_temoin
    elif nom == "REF-S2":
        em = ligne.get("ecart_au_marche") if ligne else None
    else:
        em = None  # l'écart d'un autre portefeuille n'est jamais écrit sous le libellé du panier de référence
    txt_em = _rg.pct(em, 1, signe=True) if em is not None else "non calculé"
    L.append(f"{LIGNE_MARCHE} : {txt_em} depuis le {_rg.date_fr(debut)} (retard attendu")
    L.append(f"   {RETARD_ATTENDU[len('retard attendu '):]}).")
    L.append(_rg.PH_REVUE)
    L = _plier(L)
    valeurs = {k: ligne.get(k) for k in COLONNES} if ligne else {}
    return {"nom": nom, "semaine": numero, "vendredi": v.date().isoformat(), "lignes": L, "valeurs": valeurs,
            "feux": dict(fx), "a_revoir": rv, "rendez_vous": rdv, "bandeau": _rg.BANNER, "papier": papier,
            "ecart_au_marche": em}


def rendre(b: Mapping[str, Any], fmt: str = "texte") -> str:
    """Bulletin en ``texte``, ``md`` (Markdown) ou ``json``."""
    if fmt == "texte":
        return "\n".join(b["lignes"]) + "\n"
    if fmt == "md":
        out = [f"### {b['lignes'][0]}", ""]
        for l in b["lignes"][1:]:
            out.append(l.strip() if l.strip() else "")
        return "\n".join(x if x == "" else x + "  " for x in out).rstrip() + "\n"
    if fmt == "json":
        return json.dumps(_s._jsonable(dict(b)), ensure_ascii=False, indent=1) + "\n"
    raise ValueError("format : texte, md ou json")


# ---------------------------------------------------------------------------
# Du journal au bulletin (commande « suivi bulletin », tâche de nuit)
# ---------------------------------------------------------------------------


def _nombre(x: Any) -> Any:
    if x is None or x == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    return v


def semaines_du_journal(nom: str, dossier: str | Path | None = None) -> list[dict[str, Any]]:
    """Lignes de ``semaines.csv`` relues (nombres convertis)."""
    df = lire_semaines(nom, dossier)
    out = []
    for r in df.to_dict("records"):
        out.append({k: (v if k in ("vendredi", "date") else _nombre(v)) for k, v in r.items()})
    return out


def _vide(x: Any) -> bool:
    return x is None or x == "" or (isinstance(x, float) and not math.isfinite(x))


def dividendes_non_credites(detaches: pd.DataFrame | None, operations: pd.DataFrame | None, jour: Any, *,
                            delai_jours: int = 30) -> list[dict[str, Any]]:
    """Condition (d) du feu « Fuites » (§F11) : dividendes dont l'avis de paiement publié (``date_paiement`` de
    ``detaches`` : ``symbole, date_detachement, date_paiement, montant``) date de plus de ``delai_jours`` jours et qui ne
    sont pas crédités (aucune opération ``dividende`` du titre depuis le détachement)."""
    if detaches is None or not len(detaches):
        return []
    t = pd.Timestamp(jour).normalize()
    ops = operations if isinstance(operations, pd.DataFrame) else pd.DataFrame(columns=["date", "type", "symbole"])
    div = ops[ops["type"].astype(str) == "dividende"] if len(ops) else ops
    out = []
    for r in detaches.to_dict("records"):
        if _vide(r.get("date_paiement")):
            continue
        dp = pd.Timestamp(r["date_paiement"]).normalize()
        if dp + pd.Timedelta(days=int(delai_jours)) > t:
            continue
        ex = pd.Timestamp(r.get("date_detachement") if not _vide(r.get("date_detachement")) else dp).normalize()
        recu = div[(div["symbole"].astype(str) == str(r["symbole"])) & (pd.to_datetime(div["date"]).dt.normalize() >= ex)] \
            if len(div) else div
        if not len(recu):
            out.append({"symbole": str(r["symbole"]), "date_paiement": dp.date().isoformat(),
                        "montant": _f(r.get("montant"))})
    return out


def semaine_pour_feux(lignes: Sequence[Mapping[str, Any]], *, papier: bool = True, aujourd_hui: Any = None,
                      chaine_ok: bool = True, passe_a_change: bool = False, prochain_prelevement: float | None = None,
                      w1_critique: bool | None = None, rendez_vous: Mapping[str, Any] | None = None,
                      detaches: pd.DataFrame | None = None, operations: pd.DataFrame | None = None,
                      reglages: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """Dernière semaine du journal, avec les clés lues par ``rendement.alertes.feux`` : valeur, argent engagé, papier,
    argent qui dort et ce que la règle déclarée prévoit (``None`` : « non calculé »), séances au-delà du seuil
    (semaines consécutives), ordres expirés, dividendes non crédités 30 jours après leur avis de paiement (``detaches``
    et ``operations``), liquidités et prochain prélèvement (donné, ou pris de ``rendez_vous``), W1 critique (donné, ou
    frais annuels supérieurs aux dividendes attendus de ``rendez_vous``), bulletins manquants, retard du journal,
    chaîne rompue, « le passé a changé »."""
    if not lignes:
        return None
    der = dict(lignes[-1])
    seuil = float(_rg.lire(reglages, "feux.argent_qui_dort_ecart_fcfa", 100_000))
    au_dela = 0
    for l in reversed(list(lignes)):
        if _vide(l.get("argent_qui_dort_prevu")):
            break
        if _f(l.get("argent_qui_dort")) - _f(l.get("argent_qui_dort_prevu")) > seuil:
            au_dela += max(0, 5 - int(_f(l.get("bulletins_manquants"))))
        else:
            break
    jour = pd.Timestamp(aujourd_hui).normalize() if aujourd_hui is not None else pd.Timestamp(_dt.date.today())
    rdv = rendez_vous or {}
    if prochain_prelevement is None and isinstance(rdv.get("prelevement"), Mapping):
        prochain_prelevement = _f(rdv["prelevement"].get("montant"))
    if w1_critique is None:
        fa, dv = rdv.get("frais_annuels"), rdv.get("dividendes_12_mois")
        w1_critique = bool(fa is not None and dv is not None and float(fa) > float(dv))
    prevu = der.get("argent_qui_dort_prevu")
    return {"date": der.get("date"), "valeur": _f(der.get("valeur")), "argent_engage": _f(der.get("argent_engage")),
            "argent_engage_actions": _f(der.get("argent_engage")), "papier": bool(papier),
            "argent_qui_dort": _f(der.get("argent_qui_dort")),
            "argent_qui_dort_prevu": None if _vide(prevu) else _f(prevu),
            "seances_argent_qui_dort_au_dela": au_dela, "ordres_expires": int(_f(der.get("ordres_expires"))),
            "dividendes_non_credites": dividendes_non_credites(detaches, operations, jour),
            "liquidites": _f(der.get("liquidites")), "prochain_prelevement": prochain_prelevement,
            "w1_critique": bool(w1_critique), "bulletins_manquants": int(_f(der.get("bulletins_manquants"))),
            "retard_journal_jours": max(0, (jour - pd.Timestamp(der.get("vendredi"))).days),
            "chaine_rompue": not chaine_ok, "passe_a_change": bool(passe_a_change)}


def prevu_depuis_projection(projection: Mapping[str, Any], *, part_reserve: float = 0.02
                            ) -> Callable[[pd.Timestamp, Mapping[str, Any]], float | None]:
    """Argent qui dort prévu par la règle déclarée (§F10, §F11 b) à partir d'une projection de F7 (d) avec sa série
    journalière (``rendement.liquidites.projection(..., serie=True)`` ou ``projection_detenus``) : liquidités projetées
    au dernier jour ≤ t, moins ``part_reserve`` × la valeur de la semaine. ``None`` hors de la période projetée."""
    serie = projection.get("serie") if isinstance(projection, Mapping) else None
    if not serie:
        raise ValueError("projection sans série journalière (projection(..., serie=True))")
    idx = pd.DatetimeIndex(pd.to_datetime(list(serie.keys())))
    val = pd.Series(list(serie.values()), index=idx).sort_index()

    def prevu(t: pd.Timestamp, ligne: Mapping[str, Any]) -> float | None:
        tt = pd.Timestamp(t).normalize()
        if tt < val.index[0] or tt > val.index[-1]:
            return None
        return float(val.loc[:tt].iloc[-1]) - float(part_reserve) * _f(ligne.get("valeur"))

    return prevu


def depuis_journal(nom: str, dossier: str | Path | None = None, *, plan: Mapping[str, Any] | None = None,
                   declaration: Mapping[str, Any] | None = None, alertes_ouvertes: Sequence[Mapping[str, Any]] | None = None,
                   papier: bool = True, aujourd_hui: Any = None, ecart_marche_temoin: float | None = None,
                   rendez_vous: Mapping[str, Any] | None = None, a_revoir: Sequence[Mapping[str, Any]] | None = None,
                   debut_suivi: str | None = None, detaches: pd.DataFrame | None = None,
                   operations: pd.DataFrame | None = None, prochain_prelevement: float | None = None,
                   w1_critique: bool | None = None, reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Bulletin d'un portefeuille à partir de son journal (``semaines.csv``), avec ses trois feux (lecture seule).
    Journal absent : semaine 0, feux « — ». L'écart au marché du panier de référence est lu dans le journal de
    ``REF-S2`` du même dossier quand le portefeuille en est un autre (sinon « non calculé »). ``rendez_vous`` donne
    aussi le prochain prélèvement et la condition W1 critique du feu « Fuites » ; ``detaches`` et ``operations``, les
    dividendes non crédités 30 jours après leur avis de paiement."""
    from brvm_alpha.rendement import alertes as _al

    lignes = semaines_du_journal(nom, dossier)
    d = _s.dossier_portefeuille(nom, dossier)
    ch = verifier_semaines(nom, dossier)
    passe = bool([o for _t, o in _s.lire_jsonl(d / "anomalies.jsonl") if o])
    sem = semaine_pour_feux(lignes, papier=papier, aujourd_hui=aujourd_hui, chaine_ok=ch["chaine_ok"],
                            passe_a_change=passe, prochain_prelevement=prochain_prelevement, w1_critique=w1_critique,
                            rendez_vous=rendez_vous, detaches=detaches, operations=operations, reglages=reglages)
    fx = _al.feux(sem, plan, declaration, alertes_ouvertes, reglages=reglages)
    em = ecart_marche_temoin
    if em is None and nom != "REF-S2":
        ref = semaines_du_journal("REF-S2", dossier)
        em = ref[-1].get("ecart_au_marche") if ref else None
    return bulletin(lignes[-1] if lignes else None, nom=nom, feux=fx, a_revoir=a_revoir, rendez_vous=rendez_vous,
                    ecart_marche_temoin=em, papier=papier, aujourd_hui=aujourd_hui,
                    debut_suivi=debut_suivi, reglages=reglages)


def _calendrier(panels: Mapping[str, Any]) -> pd.DatetimeIndex | None:
    ses = panels.get("sessions") if isinstance(panels, Mapping) else None
    if isinstance(ses, pd.DataFrame) and "date" in ses.columns:
        return pd.DatetimeIndex(pd.to_datetime(ses["date"])).normalize()
    close = panels.get("close") if isinstance(panels, Mapping) else None
    return pd.DatetimeIndex(close.index).normalize() if isinstance(close, pd.DataFrame) else None


def rendez_vous(titres: Mapping[str, int], panels: Mapping[str, Any], date: Any, *, costs: Any = None,
                valeur_titres: float | None = None, dernier_prelevement: Any = None, rythme: str = "trimestre",
                forfait: float = 0.0) -> dict[str, Any]:
    """Prochains rendez-vous du bulletin : prochain dividende attendu (calendrier de l'ordre de bataille,
    ``recommend.dividend_schedule`` avec le **calendrier des séances du panel** : dernier dividende reconduit, payé à la
    date prévue ; estimé), prochain prélèvement de frais fixes (supposé), remise à niveau de fin janvier. Lecture seule.

    Prélèvement : ``(garde × valeur des titres + tenue × lignes + forfait) × jours ÷ 365``, au prorata des jours écoulés
    depuis le dernier prélèvement (``dernier_prelevement`` ; défaut : la fin du trimestre précédent), comme la projection
    de F7 (d). ``rythme="semaine"`` (témoin : le moteur prélève ses frais fixes chaque semaine) : le prélèvement du
    vendredi suivant, pour 7 jours. Rend aussi ``frais_annuels`` et ``dividendes_12_mois`` (condition W1 critique du
    feu « Fuites ») ; sans titres : ``sans_titres``."""
    from brvm_alpha.config import CostModel
    from brvm_alpha.portfolio import recommend as R

    t = pd.Timestamp(date).normalize()
    out: dict[str, Any] = {"remise_a_niveau": remise_a_niveau_suivante(t).date().isoformat()}
    q = {k: int(v) for k, v in (titres or {}).items() if int(v) > 0}
    if not q:
        return out
    out["titres"] = len(q)
    try:
        cal = R.dividend_schedule(q, t, panels, calendar=_calendrier(panels))
        cal = cal[(cal["montant_net"] > 0) & cal["date_paiement_prevue"].notna()]
        out["dividendes_12_mois"] = int(cal["montant_net"].sum()) if len(cal) else 0
        if len(cal):
            cal = cal.assign(_p=pd.to_datetime(cal["date_paiement_prevue"])).sort_values("_p")
            r = cal.iloc[0]
            out["dividende"] = {"symbole": str(r["symbole"]), "date": pd.Timestamp(r["_p"]).date().isoformat(),
                                "montant": int(r["montant_net"]), "statut": "estimé"}
    except Exception:  # noqa: BLE001 - un calendrier illisible ne fait pas tomber le bulletin : « non calculé »
        out.pop("titres", None)
    cm = costs if isinstance(costs, CostModel) else CostModel()
    T = float(valeur_titres) if valeur_titres is not None else 0.0
    annuel = cm.annual_custody * T + cm.account_fee_per_line_fcfa * len(q) + float(forfait or 0.0)
    out["frais_annuels"] = int(R.round_fcfa(annuel))
    if rythme == "semaine":
        prochain = t + pd.Timedelta(days=(4 - t.weekday()) % 7 or 7)
        jours = 7
    else:
        prochain = (t + pd.offsets.QuarterEnd(0)).normalize()
        if prochain == t:
            prochain = (t + pd.offsets.QuarterEnd(1)).normalize()
        dernier = (pd.Timestamp(dernier_prelevement).normalize() if dernier_prelevement is not None
                   else (prochain - pd.offsets.QuarterEnd(1)).normalize())
        jours = max(0, (prochain - dernier).days)
    out["prelevement"] = {"date": prochain.date().isoformat(), "statut": "supposé", "jours": int(jours),
                          "montant": int(R.round_fcfa(annuel * jours / 365.0))}
    return out
