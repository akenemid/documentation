"""Pages de référence de l'interface, rendues avec des données fixes (aucun accès au disque ni au réseau).

Sert à prouver deux choses (``tests/test_deploiement_ui.py``) :

- **sans préfixe**, chaque page sort à l'octet près comme avant l'ajout du préfixe d'adresse
  (empreintes SHA-256 relevées sur le commit 3683f3a, dernier commit sans préfixe) ;
- **avec préfixe**, chaque lien, action de formulaire, adresse de fichier et appel JavaScript le porte.

Jeton, nonce et données sont constants : le rendu ne dépend ni de l'heure ni de la machine.
Pour relever de nouvelles empreintes après un changement **voulu** d'une page :
``python tests/ui_reference_pages.py`` (depuis ``brvm-alpha/``).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

if __name__ == "__main__":  # lancement direct : le paquet est à la racine du dépôt
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brvm_alpha.ui import pages as P  # noqa: E402 - après l'ajustement du chemin

TOKEN = "jeton-de-reference-0123456789"
NONCE = "nonce-de-reference"
NOTE_ID = "ab" * 20
JOB_ID = "0123456789abcdef"
DAY = pd.Timestamp("2026-11-20")


def context(prefix: str = "") -> P.PageContext:
    """Contexte fixe ; le champ ``prefix`` n'est passé que s'il est demandé (il n'existait pas avant)."""
    extra = {"prefix": prefix} if prefix else {}
    return P.PageContext(token=TOKEN, nonce=NONCE, **extra)


def _note(**kw):
    base = {"note_id": NOTE_ID, "version": 1, "status": "active", "title": 'Sonatel : dividende <relevé> href="/piege"',
            "text": 'Texte avec <a href="/piege">lien</a> et action="/piege" src="/piege".',
            "published_at": pd.Timestamp("2026-11-18 08:30", tz="UTC"), "published_precision": "datetime",
            "first_tradable_session": DAY, "author": "analyste", "source": "manual",
            "url": "https://www.brvm.org/fr/avis", "targets": ["SNTS"], "all_targets": ["SNTS"],
            "targets_unknown": [], "stance": "haussier", "conviction": 4, "horizon_days": 20, "tags": ["dividende"],
            "score": 0.42, "materiality": 0.6, "confidence": 0.8, "analysis": None}
    return base | kw


def _job(state: str = "terminé"):
    return {"id": JOB_ID, "type": "rapport", "libelle": "rapport au 20/11/2026", "statut": state,
            "progression": "terminé" if state == "terminé" else "calcul…", "journal": ["12:00:00  début", "12:00:05  fin"],
            "debut": "22/11/2026 12:00:00 UTC", "fin": "22/11/2026 12:00:05 UTC" if state == "terminé" else None,
            "erreur": None, "termine": state == "terminé"}


def _evaluation() -> pd.DataFrame:
    return pd.DataFrame({
        "label": ["BRVM Composite", "BRVM 30"], "date": [DAY] * 2, "level": [492.89, 238.73],
        "ret_1m": [-0.06, -0.06], "ret_3m": [-0.05, -0.045], "ret_12m": [0.43, 0.44], "ytd": [0.42, 0.43],
        "per": [15.8, 13.1], "yield_pct": [7.1, 4.7], "stance": ["SOUS-PONDÉRER", "NEUTRE"], "confidence": [0.59, 0.4],
        "composite": [-0.53, -0.2], "reasons": [["Tendance <forte>", "Valorisation"], ["Largeur"]],
    }, index=pd.Index(["IDX:BRVM-C", "IDX:BRVM-30"], name="index"))


def _dossier() -> dict:
    return {"index": "IDX:BRVM-30", "label": "BRVM 30", "asof": DAY, "composition": "officielle",
            "evaluation": {"date": DAY, "stance": "NEUTRE", "confidence": 0.4, "composite": -0.2, "level": 238.7},
            "constituents": pd.DataFrame({"name": ["SONATEL"], "weight": [0.3], "close": [4040.0], "flags": [["R4"]],
                                          "veto": [False]}, index=pd.Index(["SNTS"], name="symbol")),
            "recent_notes": [{"note_id": NOTE_ID, "first_tradable_session": DAY, "title": "Note <b>", "targets": ["SNTS"],
                              "score": 0.4, "decay": 0.9, "risk_flags": [], "author": "analyste",
                              "created_at": pd.Timestamp("2026-11-18 08:30", tz="UTC")}],
            "change_my_mind": ["seuil chiffré"], "calendar": pd.DataFrame(), "reasons": ["raison"]}


def _notes_status() -> dict:
    """État daté des notes avec un filtre actif et deux notes en vigueur (liens vers les fiches)."""
    table = pd.DataFrame([
        {"manual": True, "published_at": pd.Timestamp("2026-11-18 08:30", tz="UTC"), "first_tradable_session": DAY,
         "targets": ["SNTS"], "event_type": "DIV_NOTICE", "stance": "haussier", "conviction": 4, "note_id": NOTE_ID,
         "title": "Sonatel : dividende relevé", "score": 0.42, "confidence": 0.8, "decay": 0.9, "source": "manual",
         "url": "https://www.brvm.org/fr/avis", "filters": [], "weight": 0.38},
        {"manual": False, "published_at": pd.Timestamp("2026-11-17 10:00", tz="UTC"), "first_tradable_session": DAY,
         "targets": ["ORAC"], "event_type": "PROFIT_WARNING", "stance": None, "conviction": None, "note_id": "cd" * 20,
         "title": "Orange CI : alerte", "score": -0.5, "confidence": 0.6, "decay": 0.8, "source": "brvm_list", "url": "",
         "filters": ["R3"], "weight": -0.4},
    ])
    return {"line": "Notes connues au 22/11/2026 12:00 UTC, appliquées à la séance du 23/11/2026 : 2 en vigueur.",
            "scores_message": "1 note de score positif, 1 de score négatif.", "table": table,
            "filters": [{"symbole": "ORAC", "code": "R3", "libelle": "alerte sur résultats", "bloque_achats": True,
                         "depuis": DAY, "duree": "60 séances", "seances_restantes": 58, "note_id": "cd" * 20,
                         "note_titre": "Orange CI : alerte", "note_date": pd.Timestamp("2026-11-17"),
                         "note_source": "brvm_list", "note_url": "https://www.brvm.org/fr/alerte",
                         "lever": "archiver la note"}]}


def _indices_with_notes() -> pd.DataFrame:
    ev = _evaluation()
    ev["z_notes"] = [0.8, None]
    ev["notes_n"] = [1, 0]
    ev["notes_score"] = [0.4, None]
    ev["composite_ex_notes"] = [-0.65, -0.2]
    ev["notes_detail"] = [[{"note_id": NOTE_ID, "title": "Sonatel : dividende relevé", "targets": ["SNTS"],
                            "author": "analyste", "created_at": pd.Timestamp("2026-11-18 08:30", tz="UTC"),
                            "note_score": 0.42, "part": 0.4}], []]
    return ev


def reference_pages(prefix: str = "") -> dict[str, str]:
    """Nom → document HTML complet des pages de l'interface (toutes les familles de liens et de formulaires)."""
    ctx = context(prefix)
    options = [("SNTS", "SONATEL"), ("IDX:BRVM-30", "indice BRVM 30")]
    reports = [{"nom": "rapport_2026-11-20.html", "modifie": "22/11/2026 18:26 UTC", "taille": "512 Ko", "perime": False},
               {"nom": "rapport_2026-11-19.html", "modifie": "21/11/2026 18:02 UTC", "taille": "498 Ko", "perime": True}]
    fragment = ('<section class="brvm-ordre-de-bataille" lang="fr"><h1>Ordre de bataille</h1>'
                "<p>SNTS &lt;achat&gt;</p></section>")
    return {
        "tableau_de_bord": P.page_dashboard(
            ctx, last_session=DAY, validation={"etat": "exécuté", "statut_A": "REJETÉ", "principal": "A",
                                               "statut_principal": "REJETÉ"},
            choice={"variante": "REF", "motif": "A est REJETÉ sur S1"}, reports=reports, job=_job("en cours"),
            recent_notes=[_note()], flash=("info", "Régénération du rapport lancée : suivi ci-dessous.")),
        "tableau_de_bord_vide": P.page_dashboard(ctx, last_session=None, validation=None, choice=None, reports=[],
                                                 job=None, recent_notes=[]),
        "notes": P.page_notes(ctx, notes=[_note()], filters={"cible": "SNTS", "statut": "actives"}, options=options,
                              form_values={"titre": 'Titre "gardé"', "doublon": NOTE_ID},
                              form_error=P.Safe(f"note déjà enregistrée. {P.link('/notes/fiche?id=' + P.q(NOTE_ID), 'Ouvrir la note')}"),
                              total=1),
        "notes_en_vigueur": P.page_notes(ctx, notes=[], filters={}, options=options, total=2,
                                         notes_status=_notes_status(), indices=_indices_with_notes()),
        "tableau_de_bord_notes": P.page_dashboard(ctx, last_session=DAY, validation=None, choice=None, reports=reports[:1],
                                                  job=_job(), recent_notes=[], notes_status=_notes_status()),
        "fiche_note": P.page_note(ctx, note=_note(), versions=[{"version": 1, "recorded_at": "18/11/2026 08:31",
                                                               "op": "add", "status": "active", "title": "Sonatel",
                                                               "score": 0.42}],
                                  risk_labels={}, event_labels={}, flash=("ok", "Note enregistrée et analysée.")),
        "recherche": P.page_research(ctx, job=_job(), blocked={}, new_notes=[_note()], options=options,
                                     documents=["1 document lu"]),
        "indices": P.page_indices(ctx, evaluation=_evaluation(), asof=DAY, notes_included=False),
        "dossier": P.page_dossier(ctx, dossier=_dossier(), code="IDX:BRVM-30"),
        "dossier_erreur": P.page_dossier(ctx, dossier=None, code="IDX:BRVM-30", error="panel introuvable"),
        "portefeuille": P.page_portfolio(ctx, values={"capital": "10 000 000"}, job=_job(), fragment=fragment,
                                         job_id=JOB_ID),
        "portefeuille_en_cours": P.page_portfolio(ctx, values=None, job=_job("en cours"), fragment=None, job_id=JOB_ID),
        "expliquer": P.page_explain(ctx, values={"symbole": "SNTS", "date": "", "variante": ""}, explanation=None,
                                    options=[("SNTS", "SONATEL")]),
        "validation": P.page_validation(ctx, s1={"etat": "exécuté", "statut_A": "REJETÉ", "principal": "A",
                                                 "statut_principal": "REJETÉ", "dossier": "reports/validation_S1",
                                                 "avertissements": []},
                                        s1_md="# Validation S1\n\n| Var. | Statut |\n|---|---|\n| A | REJETÉ |\n\n"
                                              "Voir [la BRVM](https://www.brvm.org/fr) et `href=\"/piege\"`.\n",
                                        attempts_md=None, s0_md="# Diagnostic S0\n\n- contaminé\n"),
        "erreur_404": P.error_page(ctx, 404, "Page introuvable", "aucune page à l'adresse /inconnue"),
    }


def digests(prefix: str = "") -> dict[str, str]:
    return {name: hashlib.sha256(doc.encode("utf-8")).hexdigest() for name, doc in reference_pages(prefix).items()}


if __name__ == "__main__":  # pragma: no cover - outil de relevé des empreintes
    for name, value in digests().items():
        print(f'    "{name}": "{value}",')
