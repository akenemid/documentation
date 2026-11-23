"""Sous-blocs du module « Rendement net et pertes » dans le rapport HTML (cahier ``docs/RENDEMENT_NET.md``, §7.2).

Chaque sous-bloc s'ajoute **à la fin** d'une section existante ; ``SECTIONS`` garde ses 11 entrées et leur ordre :

* ``bandeau`` : carte « Mon plan » (forme écran, sans lecture flatteuse) et les trois feux ;
* ``ordre`` : « Argent qui dort et provision », graphique des liquidités par mois, « Passer l'ordre » ;
* ``revenus`` : « Du brut au net », « Frais évités », « Inconnues à lever », « Argent placé en plus » ;
* ``distribution`` : lectures du risque ;
* ``risques`` : « Ce que j'accepte de risquer », concentration, bulletin de la semaine du panier de référence ;
* ``methode`` : déclaration du suivi sur papier, statut des chiffres, limites.

Tous les tableaux passent par ``report.html._table`` (bloc ``tablewrap``) ; chaque sous-bloc porte le bandeau. Lecture
seule : aucune écriture, aucun réseau. Une erreur du module rend un sous-bloc vide : la section garde son statut.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from brvm_alpha import paths

SECTIONS_AVEC_SOUS_BLOC = ("bandeau", "ordre", "revenus", "distribution", "risques", "methode")
#: Libellés des types d'articles de la déclaration (en clair, avec les accents).
TYPES_ARTICLES = {"reference": "référence (témoin)", "essai": "essai sur papier", "ecart_execution": "écart d'exécution",
                  "regle_papier": "règle sur papier", "decision_humaine": "décision humaine", "derogation": "dérogation",
                  "retrait": "retrait", "remplace": "remplace"}


def _ok(b: Any) -> bool:
    return isinstance(b, Mapping) and not b.get("erreur")


def _graphique_liquidites(rn: Mapping[str, Any], RH: Any) -> str:
    pr = ((rn.get("liquidites") or {}).get("projection") if isinstance(rn.get("liquidites"), Mapping) else None) or {}
    fdm = pr.get("fins_de_mois") if _ok(pr) else None
    if not fdm:
        return ""
    from brvm_alpha.rendement.reglages import fcfa

    mois = list(fdm.keys())
    vals = [float(fdm[m] or 0) for m in mois]
    tips = [f"{m} : {fcfa(v)} (estimé, cours constants)" for m, v in zip(mois, vals)]
    return str(RH._card(RH.H("<h3>Liquidités en fin de mois (projection à cours constants)</h3>"),
                        RH.bar_chart("c-rn-liquidites", [str(m) for m in mois], vals, tips=tips,
                                     label="Liquidités projetées en fin de mois",
                                     caption="Estimation : dividendes prévus et frais supposés, cours inchangés. "
                                             "Compte des francs ; ne prévoit rien.")))


def _bulletin_temoin(ctx: Any, RH: Any) -> str:
    from brvm_alpha.suivi import bulletin as BU

    jour = pd.Timestamp(ctx.now).tz_convert("UTC").tz_localize(None).normalize() if getattr(ctx, "now", None) is not None \
        else None
    b = BU.depuis_journal("REF-S2", paths.DATA_DIR / "suivi", aujourd_hui=jour)
    import re

    texte = re.sub(r"^#{1,6}\s*", "", BU.rendre(b, "md"), flags=re.M)  # titres Markdown : texte simple dans <pre>
    return str(RH._card(RH.H("<h3>Bulletin de la semaine : le panier de référence (suivi sur papier)</h3>"),
                        RH.H(f'<pre class="small wrap">{RH.esc(texte)}</pre>'),
                        RH._p("Lignes à revoir : une revue, jamais une vente.", "muted small")))


def _declaration(ctx: Any, RH: Any) -> str:
    from brvm_alpha.suivi import declaration as DE

    dossier = paths.REPO_ROOT / "reports" / "suivi_S2"
    registre = paths.REPO_ROOT / "reports" / "trials.parquet"
    jour = pd.Timestamp(ctx.now).tz_convert("UTC").tz_localize(None).normalize() if getattr(ctx, "now", None) is not None \
        else pd.Timestamp.now().normalize()
    v = DE.verifier(dossier, registre=registre if registre.exists() else None)
    ev = DE.en_vigueur(jour, dossier)
    rows = []
    for k, a in sorted((ev.get("articles") or {}).items()):
        ty = str(a.get("type") or "")
        rows.append([k, TYPES_ARTICLES.get(ty, ty), str(a.get("reponse") or a.get("proposition") or ""),
                     str(a.get("effet_a_partir_du") or "définition du test"),
                     RH.H(f"<span class='small wrap'>{RH.esc(str(a.get('phrase') or ''))}</span>")])
    etat = (f"{v['n_lignes']} ligne(s) signée(s), chaîne {'intacte' if v['chaine_ok'] else 'rompue'}" if v["existe"]
            else str(v.get("mention") or "aucune déclaration signée"))
    from brvm_alpha.rendement.reglages import PH_ESSAI

    return str(RH._card(RH.H("<h3>Suivi sur papier : ce qui est déclaré</h3>"),
                        RH._p(f"Déclaration ({RH._rel(dossier)}) : {etat.rstrip('. ')}.", "small"),
                        RH._table(["Article", "Type", "Réponse", "En vigueur à partir du", "Règle"], rows,
                                  left=(0, 1, 2, 3, 4)) if rows else "",
                        RH._p(PH_ESSAI, "muted small")))


def sous_bloc(ctx: Any, section: str) -> str:
    """HTML du sous-bloc de ``section`` (fragment déjà échappé) ; ``""`` sans clé ``rendement_net``."""
    from brvm_alpha.report import html as RH
    from brvm_alpha.rendement import rendu as RD

    if section not in SECTIONS_AVEC_SOUS_BLOC:
        return ""
    od = ctx.try_get("order_dict", "ordre de bataille", ctx.order_dict) or {}
    rn = od.get("rendement_net") or {}
    blocs = RD.sous_blocs_rapport(rn).get(section) if rn else None
    if not blocs:
        return ""
    corps = list(blocs)
    fin = [corps.pop()] if corps and corps[-1][0] == "banner" else []
    extras = []
    for fn in ({"ordre": (lambda: _graphique_liquidites(rn, RH),),
                "risques": (lambda: _bulletin_temoin(ctx, RH),),
                "methode": (lambda: _declaration(ctx, RH),)}.get(section) or ()):
        try:
            extras.append(fn())
        except MemoryError:
            raise
        except Exception:  # noqa: BLE001 - un complément en échec n'efface pas le sous-bloc
            extras.append("")
    html = (RD.html_rapport(corps, table=RH._table, box=RH._box) + "".join(extras)
            + RD.html_rapport(fin, table=RH._table, box=RH._box))
    return f'<div class="rn-sous-bloc" id="rn-{RH.esc(section)}">\n{html}</div>\n'


__all__ = ["SECTIONS_AVEC_SOUS_BLOC", "TYPES_ARTICLES", "sous_bloc"]
