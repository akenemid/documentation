"""Régressions de la recette finale du 22/11/2026 — interface web locale (``brvm_alpha.ui``).

Un test par constat prouvé ; chacun échoue sur le code d'avant la correction (commit 552a03b). Serveur
local sur un port libre, journal temporaire, calculs lourds remplacés par des doublures
(``test_ui.FakeServices``) : aucune requête vers l'extérieur, aucun calcul sur l'échantillon vierge S1,
journal réel ``data/notes`` jamais touché. Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import os
import re
import time

import pandas as pd
import pytest

from test_ui import call, token, ui, wait_job  # noqa: F401 - fixture importée

from brvm_alpha.notes.store import NoteStore
from brvm_alpha.ui import pages
from brvm_alpha.ui import server as S

NOTE = {"cibles": "SNTS", "titre": "Sonatel : dividende relevé", "texte": "Dividende relevé.", "avis": "haussier",
        "conviction": "2"}


def browser_headers(srv, origin: str = "null") -> dict[str, str]:
    """En-têtes qu'un navigateur envoie avec un formulaire de même origine."""
    return {"Origin": origin, "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}


# ---------------------------------------------------------------------------
# Constat critique : tous les formulaires refusés (403) par un vrai navigateur
# ---------------------------------------------------------------------------


def test_pages_use_a_same_origin_referrer_policy(ui):  # noqa: F811
    status, h, body = call(ui, "GET", "/notes")
    assert status == 200
    # « no-referrer » fait envoyer « Origin: null » sur un POST de même origine : politique « same-origin ».
    assert h["referrer-policy"] == "same-origin"
    assert '<meta name="referrer" content="same-origin">' in body and "no-referrer" not in body.split("</head>")[0]


def test_form_post_with_browser_headers_is_accepted(ui):  # noqa: F811
    # Chromium avec l'ancienne politique : Origin « null » et Sec-Fetch-Site « same-origin ».
    status, h, body = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), **NOTE}, headers=browser_headers(ui))
    assert status == 303, body[:400]
    assert len(NoteStore(ui.services.notes_root)) == 1
    # Avec la nouvelle politique, le navigateur envoie l'origine réelle.
    status, _, _ = call(ui, "POST", "/notes/archiver", {"_jeton": token(ui), "id": h["location"].split("id=")[1][:40]},
                        headers=browser_headers(ui, f"http://127.0.0.1:{ui.port}"))
    assert status == 303


def test_null_origin_is_refused_without_a_same_origin_attestation(ui):  # noqa: F811
    for headers in ({"Origin": "null"}, {"Origin": "null", "Sec-Fetch-Site": "cross-site"},
                    {"Origin": "null", "Sec-Fetch-Site": "none"}, {"Origin": "http://evil.example",
                                                                   "Sec-Fetch-Site": "same-origin"}):
        status, _, _ = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), **NOTE}, headers=headers)
        assert status == 403, headers
    assert len(NoteStore(ui.services.notes_root)) == 0
    # Le jeton reste exigé même avec les en-têtes d'un navigateur.
    status, _, _ = call(ui, "POST", "/notes/archiver", {"id": "ab" * 20}, headers=browser_headers(ui))
    assert status == 403


# ---------------------------------------------------------------------------
# Constat : une note manuelle saisie deux fois compte double
# ---------------------------------------------------------------------------


def test_same_manual_note_sent_twice_is_refused_with_409(ui):  # noqa: F811
    form = {"_jeton": token(ui), **NOTE}
    status, h, _ = call(ui, "POST", "/notes/ajouter", form)
    assert status == 303
    first = h["location"].split("id=")[1].split("&")[0]
    time.sleep(0.01)
    status, _, body = call(ui, "POST", "/notes/ajouter", form)
    assert status == 409 and "note déjà enregistrée" in body and first[:12] in body
    assert 'value="Sonatel : dividende relevé"' in body and 'name="forcer"' in body  # saisie conservée
    store = NoteStore(ui.services.notes_root)
    assert len(store) == 1
    # Confirmation explicite : la seconde note est enregistrée.
    status, h2, _ = call(ui, "POST", "/notes/ajouter", {**form, "forcer": "oui"})
    assert status == 303 and h2["location"].split("id=")[1].split("&")[0] != first
    assert len(NoteStore(ui.services.notes_root)) == 2


def test_veto_checkbox_sets_the_veto_tag(ui):  # noqa: F811
    status, _, body = call(ui, "GET", "/notes")
    assert 'name="veto"' in body and "Veto (exclure le titre)" in body
    status, h, _ = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "cibles": "ORAC", "titre": "Exclusion ORAC",
                                                       "veto": "oui"})
    assert status == 303
    note = NoteStore(ui.services.notes_root).get(h["location"].split("id=")[1].split("&")[0])
    assert "veto" in note.tags and note.targets == ["ORAC"]
    # Un veto sans cible n'exclut rien : refusé.
    status, _, body = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "titre": "Veto sans cible", "veto": "oui"})
    assert status == 400 and "au moins une cible" in body


# ---------------------------------------------------------------------------
# Constat : saisie perdue quand le jeton est périmé
# ---------------------------------------------------------------------------


def test_stale_token_keeps_the_note_form_values(ui):  # noqa: F811
    status, _, body = call(ui, "POST", "/notes/ajouter", {"_jeton": "jeton-d-un-ancien-serveur", **NOTE})
    assert status == 403 and "session renouvelée" in body and "rien n&#x27;a été enregistré" in body
    assert 'value="Sonatel : dividende relevé"' in body and ">Dividende relevé.</textarea>" in body
    assert f'name="_jeton" value="{token(ui)}"' in body  # jeton neuf dans le formulaire réaffiché
    assert len(NoteStore(ui.services.notes_root)) == 0


def test_stale_token_keeps_the_portfolio_form_values(ui):  # noqa: F811
    status, _, body = call(ui, "POST", "/portefeuille/calculer", {"_jeton": "", "capital": "12 345 678",
                                                                 "portefeuille": "SNTS,120"})
    assert status == 403 and "session renouvelée" in body
    assert 'value="12 345 678"' in body and "SNTS,120</textarea>" in body
    assert ui.jobs.latest("portefeuille") is None
    # Les autres actions gardent le refus simple.
    assert call(ui, "POST", "/rapport/regenerer", {"_jeton": "x", "capital": "10M"})[0] == 403


# ---------------------------------------------------------------------------
# Constat : rapports périmés proposés par l'interface
# ---------------------------------------------------------------------------


def test_only_dated_reports_are_listed_and_old_ones_are_flagged(ui):  # noqa: F811
    s = ui.services
    s.reports_dir.mkdir(parents=True, exist_ok=True)
    for name in ("rapport_demo.html", "tableau_de_bord_2026-11-20.html", "rapport_2026-11-13.html",
                 "rapport_2026-11-20.html"):
        (s.reports_dir / name).write_text("<!doctype html><title>x</title>", encoding="utf-8")
    metrics = s.validation_dir / "metrics.json"
    metrics.write_text("{}", encoding="utf-8")
    now = time.time()
    os.utime(s.reports_dir / "rapport_2026-11-13.html", (now - 7200, now - 7200))  # avant les résultats S1
    os.utime(metrics, (now - 3600, now - 3600))
    os.utime(s.reports_dir / "rapport_2026-11-20.html", (now, now))
    reps = s.list_reports()
    assert [r["nom"] for r in reps] == ["rapport_2026-11-20.html", "rapport_2026-11-13.html"]
    assert [r["perime"] for r in reps] == [False, True]
    status, _, body = call(ui, "GET", "/")
    assert "rapport_demo.html" not in body and "tableau_de_bord" not in body
    assert "périmé (antérieur aux résultats S1 en vigueur)" in body
    for name in ("rapport_demo.html", "tableau_de_bord_2026-11-20.html"):
        assert call(ui, "GET", f"/rapport/voir?nom={name}")[0] == 404
    assert call(ui, "GET", "/rapport/voir?nom=rapport_2026-11-20.html")[0] == 200


# ---------------------------------------------------------------------------
# Constat : lundi soir, aucun avertissement de panel en retard dans l'interface
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/", "/indices", "/portefeuille", "/notes"])
def test_stale_panel_warning_is_shown_on_every_page_after_the_close(ui, path):  # noqa: F811
    ui.services.panel_late_check = True
    ui.services.clock = lambda: pd.Timestamp("2026-11-22 16:00", tz="UTC")  # dimanche : panel du vendredi à jour
    assert "PANEL EN RETARD" not in call(ui, "GET", path)[2]
    ui.services.clock = lambda: pd.Timestamp("2026-11-23 10:00", tz="UTC")  # lundi, séance ouverte
    assert "PANEL EN RETARD" not in call(ui, "GET", path)[2]
    ui.services.clock = lambda: pd.Timestamp("2026-11-23 19:00", tz="UTC")  # lundi soir : séance close
    body = call(ui, "GET", path)[2]
    assert "PANEL EN RETARD de 1 séance(s)" in body and "23/11/2026" in body
    assert "python -m brvm_alpha update" in body and "Données en retard" in body


# ---------------------------------------------------------------------------
# Constat : tableaux illisibles sur téléphone ; libellés bruts ; retour après « Calculer »
# ---------------------------------------------------------------------------


def test_table_cells_never_break_inside_a_number_and_text_columns_keep_a_width():
    css = pages.CSS
    # Les cellules n'héritent plus de « overflow-wrap:anywhere » de la page.
    assert re.search(r"th,td\{[^}]*overflow-wrap:normal", css)
    assert "td.c{white-space:nowrap}" in css and "td.t{min-width:" in css
    assert ".brvm-ordre-de-bataille td.c{white-space:nowrap}" in css
    html = pages.table(["Brut", "Motif"], [["2 541 160 FCFA", "x" * 30 + " explication longue du filtre de risque "
                                            "qui doit rester lisible sur un écran de téléphone, sans une lettre par ligne"]])
    assert '<td class="c">2 541 160 FCFA</td>' in html and '<td class="t long">' in html
    assert pages.cell_class(pages.Safe('<a href="/x">19 440</a>')) == "c"
    assert pages.cell_class("ACHAT") == "c" and pages.cell_class("−0,44") == "c"


def test_order_fragment_cells_carry_wrap_classes():
    from brvm_alpha.portfolio import recommend as R

    frag = R._render([("table", (["Titre", "Brut", "Remarque"],
                                 [["SNTS", "2 541 160 FCFA", "achat bloqué par une note ; " + "détail " * 20]]))], "html")
    assert '<td class="c">SNTS</td>' in frag and '<td class="c">2 541 160 FCFA</td>' in frag
    assert '<td class="t long">' in frag


def test_filters_block_is_collapsible_outside_the_notes_page():
    status = {"line": "Notes connues au …", "filters": [{"symbole": "ETIT", "code": "R2", "libelle": "annulation d'AG",
                                                         "bloque_achats": True, "note_id": "ab" * 20, "note_titre": "x"}]}
    closed = pages.notes_status_block(status)
    assert '<details class="filters"><summary>Filtres de risque actifs issus des notes (1)</summary>' in closed
    assert '<details class="filters" open>' in pages.notes_status_block(status, detail=True)


def test_explain_page_shows_french_cap_labels_and_percentages(ui):  # noqa: F811
    base = ui.services.explain

    def explain(symbol, asof, variant):
        e = base(symbol, asof, variant)
        e["caps"] = {"line": 0.2612, "liquidity": 0.4, "upper": 0.2612, "sector": 0.4611, "country": 0.3,
                     "aes": {"bloc AES (siège)": 0.10615691830658705, "bloc AES (exposition λ)": 0.16833410677960542},
                     "line_detail": "détail"}
        e["messages"] = ["REF : 20 lignes, 98.00% investis"]
        return e

    ui.services.explain = explain
    status, _, body = call(ui, "GET", "/expliquer?symbole=SNTS")
    assert status == 200
    for label in ("Plafond de ligne", "Plafond de liquidité", "Plafond retenu (le plus bas)", "Plafond du secteur",
                  "Plafond du pays", "Bloc AES (Burkina Faso, Mali, Niger)"):
        assert f"<dt>{label}</dt>" in body, label
    assert "Bloc AES (siège) : 10,62 %" in body and "Bloc AES (exposition λ) : 16,83 %" in body
    assert "0.10615691830658705" not in body and "{&#x27;" not in body and "<dt>upper</dt>" not in body
    assert "98,00 % investis" in body and "98.00%" not in body


def test_note_page_shows_french_status_and_source(ui):  # noqa: F811
    _, h, _ = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), **NOTE})
    nid = h["location"].split("id=")[1].split("&")[0]
    body = call(ui, "GET", f"/notes/fiche?id={nid}")[2]
    assert "<dd>saisie manuelle</dd>" in body and "1 (active)" in body and ">ajout<" in body
    assert "<dd>manual</dd>" not in body and ">add<" not in body
    call(ui, "POST", "/notes/archiver", {"_jeton": token(ui), "id": nid})
    body = call(ui, "GET", f"/notes/fiche?id={nid}")[2]
    assert "2 (archivée)" in body and "(archived)" not in body


def test_portfolio_page_gives_visible_feedback_after_calculate(ui):  # noqa: F811
    status, h, _ = call(ui, "POST", "/portefeuille/calculer", {"_jeton": token(ui), "capital": "10M", "tirages": "1000"})
    assert status == 303 and h["location"].endswith("#travail")
    wait_job(ui, "portefeuille")
    status, _, body = call(ui, "GET", h["location"].split("#")[0])
    assert status == 200
    assert 'Ordre de bataille prêt : <a href="#resultat">voir le résultat</a>' in body
    # Travail puis résultat avant le rappel des notes ; ancre de retour pour le rechargement automatique.
    i_job, i_res, i_notes = body.index('<div id="travail">'), body.index('id="resultat"'), body.index(
        "Notes prises en compte à la dernière séance")
    assert i_job < i_res < i_notes and 'data-done-anchor="resultat"' in body
    assert "data-done-anchor" in pages.BODY_JS and "window.location.hash=a" in pages.BODY_JS
