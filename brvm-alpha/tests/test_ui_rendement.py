"""Interface du module « Rendement net et pertes » (cahier ``docs/RENDEMENT_NET.md``, §7.1), **hors ligne**.

Serveur local sur un port libre (doublures de ``test_ui``), dossier de données temporaire (dossier parent du journal
des notes de la doublure) : les données réelles ne sont jamais ouvertes. Le calcul de l'écran est remplacé par un
ordre simulé ; aucun calcul sur S1, aucune requête réseau.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import html
import json
import re
import threading
from urllib.parse import urlsplit

import pandas as pd
import pytest

import rendement_ui_jeux as J
from test_ui import FakeServices, call, token, wait_job

from brvm_alpha import paths
from brvm_alpha.rendement import grille as G
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.suivi import carnet as CN
from brvm_alpha.ui import pages as P
from brvm_alpha.ui import rendement as RN
from brvm_alpha.ui import server as S

HORLOGE = pd.Timestamp(f"{J.JOUR} 09:00", tz="UTC")


@pytest.fixture()
def ui(tmp_path, monkeypatch):
    from brvm_alpha.notes import research as rs

    def no_network(*a, **k):
        raise AssertionError("aucune requête réseau dans les tests")

    monkeypatch.setattr(rs, "_requests_transport", no_network)
    # Garde : rien n'est jamais lu ni écrit dans le dossier de données de l'installation.
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "donnees_installation_interdites")
    services = FakeServices(tmp_path)
    services.clock = lambda: HORLOGE
    srv = S.make_server("127.0.0.1", 0, services=services)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.shutdown_jobs()
        srv.server_close()
        assert not (tmp_path / "donnees_installation_interdites").exists()


@pytest.fixture()
def recommend_simule(monkeypatch):
    """``recommend`` remplacé : enregistre ses arguments, rend un ordre avec ``rendement_net``."""
    from brvm_alpha.portfolio import recommend as rec

    appels = []

    def faux(asof, capital, **kw):
        appels.append({"asof": asof, "capital": capital, **kw})
        return J.OrdreAvecRendement(str(pd.Timestamp(asof).date()))

    monkeypatch.setattr(rec, "recommend", faux)
    return appels


def profil(srv):
    return RN.dossier_profil(srv.services)


def suivi(srv):
    return RN.dossier_suivi(srv.services)


def post(srv, path, form):
    return call(srv, "POST", path, {"_jeton": token(srv), **form})


def texte(fragment: str) -> str:
    """Texte lisible d'un fragment (balises retirées, espaces insécables ramenées à des espaces)."""
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\u202f", " ").replace("\xa0", " ")


def carte(body: str) -> str:
    m = re.search(r'<section class="card" id="mon-plan">.*?</form></details></section>', body, re.S)
    assert m, "carte « Mon plan » absente"
    return m.group(0)


def demarrer(srv, nom="MOI", mode="papier"):
    c = CN.ouvrir(nom, suivi(srv), creer=True)
    c.ajouter_plusieurs([{"type": "mandat", "date": J.JOUR, "capital": 1_000_000.0, "mode": mode, "grille": "central",
                          "perte_toleree": None, "taux_reserve": None, "options_execution": []},
                         {"type": "apport", "date": J.JOUR, "montant": 1_000_000.0}])
    return c


# ---------------------------------------------------------------------------
# Dossiers : jamais les données de l'installation dans les tests
# ---------------------------------------------------------------------------


def test_data_folder_follows_the_services(tmp_path):
    s = S.Services(notes_root=tmp_path / "copie" / "notes", panel_dir=tmp_path / "panel")
    assert RN.dossier_donnees(s) == tmp_path / "copie" and RN.dossier_profil(s) == tmp_path / "copie" / "profil"
    s2 = S.Services(notes_root=tmp_path / "n", data_dir=tmp_path / "donnees")
    assert RN.dossier_suivi(s2) == tmp_path / "donnees" / "suivi"
    assert RN.dossier_donnees(S.Services()) == paths.DATA_DIR


# ---------------------------------------------------------------------------
# Tableau de bord : carte « Mon plan »
# ---------------------------------------------------------------------------


def test_card_reads_the_cache_and_never_runs_recommend(ui, recommend_simule):
    J.ecrire_cache(profil(ui))
    status, _, body = call(ui, "GET", "/")
    assert status == 200 and recommend_simule == []  # la carte lit le cache, elle ne lance jamais recommend
    c = carte(body)
    assert body.index('id="mon-plan"') < body.index("<h2>État (faits)</h2>")  # en tête du Tableau de bord
    t = texte(c)
    for phrase in (RG.BANNER, RG.PH_ETUDE, RG.phrase_seance(J.JOUR)):
        assert phrase in " ".join(t.split()), phrase[:40]
    assert "Calculé le 23/11/2026 sur le bulletin du 20/11/2026." in t
    for titre in ("1. CE QUE PREND MON COURTIER (SGI)", "2. CE QUE J'ACCEPTE DE RISQUER SUR 12 MOIS",
                  "3. OÙ DORT LE RESTE, ET À QUEL TAUX", "SI VOUS NE FAITES QU'UNE CHOSE CETTE SEMAINE",
                  "TROIS FEUX CHAQUE SEMAINE"):
        assert titre in t, titre
    # forme écran : montants arrondis, aucune lecture flatteuse
    assert "−830 000 à −980 000" in t and "flatteuse" not in t.lower() and RG.PH_FLATTE not in t
    # liens et formulaires (POST seulement, avec jeton)
    for href in ("/plan/resultat", "/suivi/bulletin", "/plan/questions"):
        assert f'href="{href}"' in c
    forms = re.findall(r'<form method="(\w+)" action="([^"]+)"', c)
    assert {a for m, a in forms} == {"/plan/enregistrer", "/plan/grille"} and {m for m, a in forms} == {"post"}
    assert c.count('name="_jeton"') == len(forms)
    # table de choix cliquable : les montants capital total, en actions, en réserve toujours ensemble
    assert 'name="perte" value="1000000"' in c and 'name="perte" value="tout"' in c
    assert "en actions 3 000 000 FCFA ; en réserve 7 000 000 FCFA ; capital total 10 000 000 FCFA" in t
    assert RG.mots_interdits(t) == []


def test_card_without_cache_offers_the_calculation(ui):
    status, _, body = call(ui, "GET", "/")
    c = carte(body)
    t = " ".join(texte(c).split())
    assert status == 200 and "Mon plan n'est pas encore calculé (aucun calcul enregistré)" in t
    assert RG.PH_ETUDE in t and RG.phrase_seance(J.JOUR) in t and RG.BANNER in t
    assert "Calculer mon plan" in t and 'action="/plan/grille"' in c and 'action="/plan/enregistrer"' in c
    assert RG.mots_interdits(texte(c)) == []


def test_stale_cache_is_dated_and_recalculation_is_offered(ui, monkeypatch):
    J.ecrire_cache(profil(ui), asof="2026-11-19")
    status, _, body = call(ui, "GET", "/")
    t = " ".join(texte(carte(body)).split())
    assert status == 200 and "Calcul à refaire" in t
    assert "Ce plan est calculé sur le bulletin du 19/11/2026 ; le dernier bulletin est celui du 20/11/2026" in t
    assert 'name="recalculer" value="oui"' in body


def test_unreadable_cache_shows_no_amount(ui):
    profil(ui).mkdir(parents=True)
    (profil(ui) / "plan_cache.json").write_text("{pas du json", encoding="utf-8")
    status, _, body = call(ui, "GET", "/")
    t = texte(carte(body))
    assert status == 200 and "calcul enregistré illisible" in t and "FCFA de frais" not in t


def test_recalculation_runs_in_the_work_thread_and_writes_the_cache(ui, recommend_simule):
    status, h, _ = post(ui, "/plan/enregistrer", {"recalculer": "oui"})
    assert status == 303 and h["location"] == "/?plan=1#mon-plan"
    job = wait_job(ui, RN.JOB_PLAN)
    assert job.status == "terminé", job.snapshot()
    assert not (profil(ui) / "plan.json").exists()  # « Recalculer » n'enregistre aucun choix
    c = json.loads((profil(ui) / "plan_cache.json").read_text(encoding="utf-8"))
    assert c["asof"] == J.ASOF and c["bandeau"] == RG.BANNER and c["plan"]["lignes"]
    kw = recommend_simule[-1]
    assert kw["capital"] == 10_000_000 and kw["grille"] == "central" and kw["index_evaluation"] is False
    assert "perte_toleree" not in kw and "taux_reserve" not in kw
    body = call(ui, "GET", "/")[2]
    assert "Calculé le 24/11/2026 sur le bulletin du 20/11/2026." in texte(carte(body))
    assert f'data-job-id="{job.id}"' in carte(body)  # le travail du plan est le dernier : la carte le suit


def test_saved_choices_feed_the_calculation(ui, recommend_simule):
    form = {"perte": "1000000", "capital": "10 000 000", "taux": "3,5", "placement": "compte espèces", "besoin": "24",
            "questions_envoyees": "oui"}
    status, h, _ = post(ui, "/plan/enregistrer", form)
    assert status == 303
    pe = json.loads((profil(ui) / "plan.json").read_text(encoding="utf-8"))
    assert pe["perte_toleree"] == 1_000_000.0 and pe["taux_reserve"] == pytest.approx(0.035)
    assert pe["statut_taux"] == "supposé" and pe["besoin_dans_mois"] == 24 and pe["questions_envoyees"] is True
    assert pe["placement"] == "compte espèces" and pe["bandeau"] == RG.BANNER
    assert wait_job(ui, RN.JOB_PLAN).status == "terminé"
    kw = recommend_simule[-1]
    assert kw["perte_toleree"] == 1_000_000.0 and kw["taux_reserve"] == pytest.approx(0.035)
    assert kw["plan_enregistre"]["perte_toleree"] == 1_000_000.0
    body = call(ui, "GET", "/")[2]
    c = carte(body)
    assert 'value="1000000" checked' in c and 'value="3,5"' in c
    # « une chose » avance : les questions sont envoyées, le risque et le taux sont choisis
    assert "lisez le bulletin de la semaine" in texte(c)
    # « tout » et « pas encore choisi »
    post(ui, "/plan/enregistrer", {"perte": "tout", "capital": "10M"})
    wait_job(ui, RN.JOB_PLAN)
    pe = json.loads((profil(ui) / "plan.json").read_text(encoding="utf-8"))
    assert pe["perte_toleree"] is None and pe["risque"] == "tout" and "taux_reserve" not in pe
    assert 'value="tout" checked' in carte(call(ui, "GET", "/")[2])


@pytest.mark.parametrize("form, motif", [
    ({"perte": "libre", "perte_libre": ""}, "saisir un montant"),
    ({"perte": "libre", "perte_libre": "abc"}, "ce que j'accepte de risquer"),
    ({"perte": "20000000", "capital": "10M"}, "plus que le capital total"),
    ({"taux": "cinq"}, "taux net de la réserve"),
    ({"capital": "rien"}, "capital"),
    ({"besoin": "0"}, "besoin de cet argent"),
])
def test_refused_choices_write_nothing_and_keep_the_input(ui, recommend_simule, form, motif):
    status, _, body = post(ui, "/plan/enregistrer", form)
    assert status == 400 and motif in html.unescape(body) and "Saisie refusée" in body
    assert not (profil(ui) / "plan.json").exists() and recommend_simule == []
    assert '<details class="decision" open><summary>2 et 3.' in body


def test_grid_entry_recomputes_fees_on_the_cached_lines(ui, recommend_simule):
    J.ecrire_cache(profil(ui))
    form = {"courtage": "1", "taxe": "18", "garde": "0,25", "par_ligne": "0", "forfait": "4000",
            "source": "grille écrite 2026", "statut": "grille écrite"}
    status, h, _ = post(ui, "/plan/grille", form)
    assert status == 303 and h["location"] == "/?grille=1#mon-plan"
    g = G.charger(profil(ui))
    assert g.valeur("courtage") == pytest.approx(0.01) and g.valeur("forfait_compte") == 4000
    assert g.champs["courtage"].statut == "grille écrite" and g.champs["courtage"].source == "grille écrite 2026"
    assert g.champs["garde_minimum"].statut == "supposé"  # « plus de champs » inchangés : statut inchangé
    assert G.statut_global(g) == "grille écrite"
    status, _, body = call(ui, "GET", "/?grille=1")
    t = texte(carte(body))
    assert status == 200 and recommend_simule == []  # moins d'une seconde : aucune relance de l'ordre
    ref = G.comparer(J.ORDRE_MINI, {"c": G.defaut(), "m": g}, reference=G.defaut())
    ec = ref[1]["ecart_premiere_annee"]
    sens = "surcoût" if ec > 0 else "frais évités par rapport au tarif supposé"
    assert ec != 0 and texte(f"{RG.fcfa(ec, signe=True)} ({sens})") in t
    assert texte(RG.fcfa(ref[1]["premiere_annee"])) in t and "Ma grille" in t
    assert RG.PH_FRAIS in " ".join(t.split()) and "Votre grille a changé depuis ce calcul" in t


@pytest.mark.parametrize("form, motif", [
    ({"courtage": "4"}, "hors de la plage acceptée"),
    ({"courtage": "0,8", "statut": "grille écrite"}, "sans source"),
    ({"courtage": "huit"}, "Courtage"),
    ({"statut": "inventé"}, "statut inconnu"),
])
def test_refused_grid_writes_nothing(ui, form, motif):
    status, _, body = post(ui, "/plan/grille", form)
    assert status == 400 and motif in html.unescape(body)
    assert not (profil(ui) / "grille_sgi.yaml").exists()


def test_card_forms_need_the_token_and_stale_forms_come_back(ui, recommend_simule):
    for path in ("/plan/enregistrer", "/plan/grille", "/suivi/revue", "/suivi/saisir"):
        assert call(ui, "POST", path, {"perte": "1000000", "courtage": "1"})[0] == 403
    status, _, body = call(ui, "POST", "/plan/enregistrer", {"_jeton": "perime", "perte": "libre",
                                                             "perte_libre": "750000", "taux": "2"})
    assert status == 403 and "session renouvelée" in body and 'value="750000"' in carte(body)
    status, _, body = call(ui, "POST", "/plan/grille", {"_jeton": "perime", "courtage": "0,6", "statut": "supposé"})
    assert status == 403 and 'id="g-courtage" name="courtage" inputmode="decimal" value="0,6"' in body
    status, _, body = call(ui, "POST", "/suivi/revue", {"_jeton": "perime", "alerte": "perte", "texte": "gardée"})
    assert status == 403 and "gardée</textarea>" in body
    assert not profil(ui).exists() and recommend_simule == [] and not suivi(ui).exists()


def test_one_long_operation_at_a_time_for_the_plan(ui, recommend_simule):
    gate = threading.Event()
    job = ui.jobs.start("rapport", "travail bloquant", lambda j: gate.wait(30))
    try:
        status, _, body = post(ui, "/plan/enregistrer", {"perte": "1000000"})
        assert status == 409 and "déjà en cours" in body
        assert (profil(ui) / "plan.json").exists()  # le choix est gardé ; le calcul sera relancé
        assert "disabled" in carte(body)
    finally:
        gate.set()
    ui.jobs.wait(job.id, 10)
    assert recommend_simule == []


# ---------------------------------------------------------------------------
# Pages atteintes par des liens
# ---------------------------------------------------------------------------


def test_questions_page_lists_the_8_questions(ui):
    status, _, body = call(ui, "GET", "/plan/questions")
    assert status == 200 and body.count("<li>") == 8 and "<textarea" in body and "readonly" in body
    assert P.esc(RG.BANNER) in body and "<form" not in body.split("<main>")[1]


def test_result_page_shows_the_detail_and_exports(ui):
    status, _, body = call(ui, "GET", "/plan/resultat")
    assert status == 200 and "pas encore calculé" in body
    assert call(ui, "GET", "/plan/resultat?format=json")[0] == 404
    J.ecrire_cache(profil(ui))
    status, _, body = call(ui, "GET", "/plan/resultat")
    assert status == 200 and "<table>" in body and "1 000 000" in body.replace(" ", " ")
    status, h, js = call(ui, "GET", "/plan/resultat?format=json")
    d = json.loads(js)
    assert status == 200 and d["bandeau"] == RG.BANNER and d["rendement_net"]["contexte"]["capital"] == 10_000_000
    status, h, txt = call(ui, "GET", "/plan/resultat?format=texte")
    assert status == 200 and h["content-type"].startswith("text/plain") and RG.BANNER in txt
    assert len(txt.splitlines()) <= 45 and max(map(len, txt.splitlines())) <= 100
    assert call(ui, "GET", "/plan/resultat?format=pdf")[0] == 400


def test_bulletin_page_without_journal_and_unknown_portfolio(ui):
    status, _, body = call(ui, "GET", "/suivi/bulletin")
    assert status == 200 and "BULLETIN DE LA SEMAINE" in body and "semaine 0" in body
    assert RG.mots_interdits(texte(body.split('<pre class="bulletin">')[1].split("</pre>")[0])) == []
    status, h, txt = call(ui, "GET", "/suivi/bulletin?nom=REF-S2&format=texte")
    assert status == 200 and RG.BANNER in txt
    status, _, js = call(ui, "GET", "/suivi/bulletin?format=json")
    assert status == 200 and json.loads(js)["bandeau"] == RG.BANNER
    assert call(ui, "GET", "/suivi/bulletin?nom=..%2Fetc")[0] == 400
    assert not suivi(ui).exists()  # lecture seule


# ---------------------------------------------------------------------------
# Page Portefeuille : champs, revue, saisie
# ---------------------------------------------------------------------------


def test_portfolio_fields_are_empty_and_unchecked_by_default(ui):
    status, _, body = call(ui, "GET", "/portefeuille")
    form = re.search(r'<form method="post" action="/portefeuille/calculer".*?</form>', body, re.S).group(0)
    assert status == 200
    for nom in ("perte", "taux", "apport_montant"):
        assert re.search(rf'name="{nom}"[^>]* value=""', form), nom
    for nom in ("arrondi", "apport", "completer"):
        assert re.search(rf'<input type="checkbox" id="[^"]+" name="{nom}" value="oui">', form), nom
    assert "Ce que j'accepte de risquer sur 12 mois (FCFA)" in html.unescape(form)
    assert "Taux net de ma réserve (% par an)" in html.unescape(form) and 'name="tarif"' in form
    assert 'id="suivi"' in body and "Bulletin de la semaine" in body


def test_portfolio_without_new_field_calls_recommend_exactly_as_before(ui):
    status, h, _ = post(ui, "/portefeuille/calculer", {"capital": "10M", "tirages": "1000", "perte": "", "taux": "",
                                                        "tarif": "", "apport_montant": ""})
    assert status == 303
    wait_job(ui, "portefeuille")
    kw = [c for c in ui.services.calls if c[0] == "recommend"][-1][1]
    assert set(kw) == {"asof", "capital", "holdings", "cash", "variant", "n_boot", "log"}


def test_portfolio_options_are_passed_only_when_filled(ui):
    status, h, _ = post(ui, "/portefeuille/calculer", {"capital": "10M", "tirages": "1000", "perte": "1M", "taux": "3",
                                                        "cash": "2 000 000", "apport": "oui", "completer": "oui"})
    assert status == 303
    job = wait_job(ui, "portefeuille")
    kw = [c for c in ui.services.calls if c[0] == "recommend"][-1][1]
    assert kw["options"] == {"perte_toleree": 1_000_000.0, "taux_reserve": pytest.approx(0.03), "apport": 2_000_000.0,
                             "completer": True}
    body = call(ui, "GET", f"/portefeuille?travail={job.id}")[2]
    assert 'name="perte" inputmode="numeric" value="1M"' in body and 'name="completer" value="oui" checked' in body


@pytest.mark.parametrize("form, motif", [
    ({"arrondi": "oui"}, "grille écrite"),
    ({"tarif": "ma_sgi"}, "aucune grille enregistrée"),
    ({"apport": "oui"}, "liquidités réelles nécessaires"),
    ({"apport": "oui", "cash": "1M", "apport_montant": "2M"}, "supérieur aux liquidités"),
    ({"apport_montant": "1M"}, "cocher"),
    ({"perte": "beaucoup"}, "ce que j'accepte de risquer"),
    ({"tarif": "autre"}, "tarif"),
])
def test_portfolio_refuses_inconsistent_options_before_any_calculation(ui, form, motif):
    status, _, body = post(ui, "/portefeuille/calculer", {"capital": "10M", "tirages": "1000", **form})
    assert status == 400 and motif in html.unescape(body)
    assert not [c for c in ui.services.calls if c[0] == "recommend"]


def test_review_is_written_to_the_book_and_creates_no_order(ui):
    status, _, body = post(ui, "/suivi/revue", {"nom": "MOI", "alerte": "perte", "decision": "garder", "texte": "x"})
    assert status == 400 and "non démarré" in body
    assert post(ui, "/suivi/revue", {"nom": "REF-S2", "alerte": "perte", "decision": "garder"})[0] == 400
    c = demarrer(ui)
    status, _, body = post(ui, "/suivi/revue", {"nom": "MOI", "alerte": "perte", "decision": "inventée"})
    assert status == 400 and "décision" in body
    status, _, body = post(ui, "/suivi/revue", {"nom": "MOI", "alerte": "SNTS", "decision": "ne-plus-acheter",
                                                "texte": "Réponses <écrites>."})
    assert status == 200 and "Revue consignée" in body and "Aucun ordre n&#x27;est créé" in body
    revues = c.mouvements(types=("revue",))
    assert len(revues) == 1 and revues[0]["decision"] == "ne-plus-acheter" and revues[0]["texte"] == "Réponses <écrites>."
    assert not c.mouvements(types=("ordre",))
    assert RG.PH_REVUE in html.unescape(body)


def test_entries_apport_retrait_and_avis_on_paper_refused(ui):
    c = demarrer(ui)
    status, _, body = post(ui, "/suivi/saisir", {"nom": "MOI", "quoi": "apport", "montant": "250 000"})
    assert status == 200 and "Consigné" in body
    status, _, body = post(ui, "/suivi/saisir", {"nom": "MOI", "quoi": "retrait", "montant": "abc"})
    assert status == 400 and "montant" in body
    status, _, body = post(ui, "/suivi/saisir", {"nom": "MOI", "quoi": "avis",
                                                 "avis": J_AVIS})
    assert status == 400 and "portefeuille réel" in html.unescape(body)
    assert [m["montant"] for m in c.mouvements(types=("apport",))] == [1_000_000.0, 250_000.0]
    assert post(ui, "/suivi/saisir", {"nom": "MOI", "quoi": "rien"})[0] == 400


J_AVIS = (RN.EN_TETE_AVIS + "\n" + f"{J.JOUR};SNTS;achat;10;4040;323;58;121;0;40902\n")


def test_avis_on_a_real_portfolio_is_compared_to_the_grid(ui):
    c = demarrer(ui, mode="reel")
    status, _, body = post(ui, "/suivi/saisir", {"nom": "MOI", "quoi": "avis", "avis": J_AVIS})
    t = html.unescape(body)
    assert status == 200 and "1 exécution(s) consignée(s) au carnet « MOI »" in t
    assert len(c.mouvements(types=("execution",))) == 1
    # saisie en double : refusée par le carnet (ajout seul)
    status, _, body = post(ui, "/suivi/saisir", {"nom": "MOI", "quoi": "avis", "avis": J_AVIS})
    assert status == 400 and len(c.mouvements(types=("execution",))) == 1


# ---------------------------------------------------------------------------
# Page Validation, navigation, formulaires GET
# ---------------------------------------------------------------------------


def test_validation_table_of_what_is_declared(ui):
    status, _, body = call(ui, "GET", "/validation")
    t = " ".join(texte(body).split())
    assert status == 200 and "Suivi sur papier : ce qui est déclaré" in t and RG.PH_ESSAI in t
    assert "Prochain point d'étape : le 01/12/2026" in t and "On ne classe jamais des essais par leur rendement" in t
    for code in ("REF-S2", "N", "E-L", "E-B", "E-A", "E-C", "E-D", "PLAN"):
        assert f'<td class="c">{code}</td>' in body, code
    section = body.split('id="suivi-declare"')[1].split("</section>")[0]
    entetes = re.findall(r'<th scope="col">([^<]*)</th>', section)
    assert "non déclaré à ce jour" in t and entetes == ["Code", "Rôle", "Règle", "État au 24/11/2026", "Mesures comptées"]


def test_navigation_keeps_7_pages_and_no_new_get_form(ui):
    assert len(P.NAV) == 7
    for path in ("/", "/portefeuille", "/validation", "/plan/questions", "/plan/resultat", "/suivi/bulletin"):
        body = call(ui, "GET", path)[2]
        gets = {a for m, a in re.findall(r'<form method="(\w+)" action="([^"]+)"', body) if m == "get"}
        assert gets <= {"/notes", "/indices", "/expliquer"}, (path, gets)
        assert body.count('<nav class="main"') == 1 and body.count("</a>", body.index('<nav class="main"'),
                                                                   body.index("</nav>")) == 7


def test_every_new_route_is_reachable_from_the_pages(ui):
    J.ecrire_cache(profil(ui))
    seen = set()
    for path in ("/", "/portefeuille"):
        body = call(ui, "GET", path)[2]
        seen |= {urlsplit(html.unescape(u)).path for u in re.findall(r'(?:href|action)="([^"]+)"', body)}
    assert {"/plan/questions", "/plan/resultat", "/suivi/bulletin", "/plan/enregistrer", "/plan/grille",
            "/suivi/revue", "/suivi/saisir"} <= seen


def test_card_failure_never_breaks_the_dashboard(ui, monkeypatch):
    J.ecrire_cache(profil(ui))

    def panne(*a, **k):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(RN, "carte_mon_plan", panne)
    status, _, body = call(ui, "GET", "/")
    assert status == 200 and "carte « Mon plan » non affichée" in body and "<h2>État (faits)</h2>" in body


def test_embedded_mode_refuses_profile_writes_in_the_code_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "est_embarque", lambda *a, **k: True)
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    services = FakeServices(tmp_path)
    services.notes_root = paths.REPO_ROOT / "data_interdit" / "notes"  # le dossier de données serait dans le code
    services.clock = lambda: HORLOGE
    srv = S.make_server("127.0.0.1", 0, services=services)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        status, _, body = call(srv, "POST", "/plan/enregistrer", {"_jeton": token(srv), "perte": "1000000"})
        assert status in (400, 500) and "mode embarqué" in html.unescape(body)
        assert not (paths.REPO_ROOT / "data_interdit").exists()
    finally:
        srv.shutdown()
        srv.shutdown_jobs()
        srv.server_close()
