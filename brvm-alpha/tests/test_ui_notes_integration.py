"""Interface locale après l'assemblage des notes : aucun bloc HTML n'est affiché en texte brut.

Défaut vu à l'assemblage (page Notes servie sur une copie du journal réel) : deux blocs construits par
``Safe + Safe`` — une chaîne ordinaire, que ``pages.join`` échappe — s'affichaient en code HTML brut : le
tableau repliable des notes automatiques en vigueur et le bilan de la lecture des documents. Serveur
local sur un port libre, journal temporaire, aucune requête vers l'extérieur.
"""

from __future__ import annotations

from test_notes_direct import SUNDAY, ag_cancel_note, fake_enrich, ui_direct  # noqa: F401 - fixtures importées
from test_ui import call, token, wait_job

from brvm_alpha.notes.store import NoteStore

#: Balises de bloc écrites par les pages : échappées, elles s'afficheraient en texte brut (un titre de note
#: contenant « <b> » reste, lui, légitimement échappé).
ESCAPED_BLOCK = ("&lt;details", "&lt;summary", "&lt;table", "&lt;section", "&lt;pre", "&lt;div", "&lt;/details",
                 "&lt;/section", "&lt;/pre", "&lt;/table")


def test_ui_notes_page_renders_the_automatic_notes_table_as_html(ui_direct):  # noqa: F811
    st = NoteStore(ui_direct.services.notes_root)
    st.add(ag_cancel_note("ETIT", SUNDAY, author="auto", published="2026-10-23",
                          url="https://www.brvm.org/sites/default/files/annulation_ago.pdf"), now=SUNDAY)
    status, _, body = call(ui_direct, "GET", "/notes")
    assert status == 200 and "Notes automatiques en vigueur (1)" in body
    # Le tableau repliable est du HTML, pas son code affiché en clair.
    assert '<details><summary>Afficher le tableau</summary><div class="tablewrap"><table>' in body
    assert not any(piece in body for piece in ESCAPED_BLOCK)
    # Textes courts insécables (séance, cible, type, effet d'un filtre) : jamais coupés au milieu d'un mot.
    for piece in ('<span class="nw">26/10/2026</span>', '<span class="nw">ETIT</span>',
                  '<span class="nw">AG_CANCEL</span>', '<span class="nw">achats bloqués</span>'):
        assert piece in body, piece


def test_ui_research_page_renders_the_reading_report_as_html(ui_direct, fake_enrich):  # noqa: F811
    form = {"_jeton": token(ui_direct), "mode": "hors_ligne", "max_requetes": "10", "confirmer": "oui",
            "lire_documents": "oui", "max_documents": "5"}
    status, _, _ = call(ui_direct, "POST", "/recherche/lancer", form)
    assert status == 303
    job = wait_job(ui_direct, "recherche")
    assert job.status == "terminé", job.snapshot()
    status, _, body = call(ui_direct, "GET", "/recherche")
    assert status == 200
    assert ('<section class="card"><h2>Lecture du contenu des documents (dernière recherche)</h2><pre class="log">'
            in body)
    assert "2 note(s) enrichie(s)" in body and not any(piece in body for piece in ESCAPED_BLOCK)
