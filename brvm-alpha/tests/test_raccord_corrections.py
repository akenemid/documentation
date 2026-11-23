"""Corrections de la relecture du raccordement du module « Rendement net et pertes » (copie raccord-rendement).

Chaque test reproduit un constat de la relecture : il échouait avant la correction et réussit après. Tout se passe
dans des dossiers temporaires : les données réelles ne sont jamais ouvertes, aucune requête réseau, aucun calcul sur
S1, aucune signature sur le vrai registre.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import copy
import html
import json
import re
from pathlib import Path

import pandas as pd
import pytest

import rendement_ui_jeux as J
from test_ui import call
from test_ui_rendement import post, profil, texte, ui  # noqa: F401 - fixture « ui » du serveur local

from brvm_alpha.rendement import grille as G
from brvm_alpha.rendement import plan as PL
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.ui import rendement as RN


# ---------------------------------------------------------------------------
# Constat critique 1 : carte « Mon plan » et /plan/resultat avec une perte acceptée
# ---------------------------------------------------------------------------


def _bilan(frais_an1: int, annuels: int, dividendes: int, part: float, supposee: int) -> dict:
    return {"totaux": {"frais_an1": frais_an1, "annuels": annuels, "dividendes_nets": dividendes,
                       "entree": frais_an1 - annuels, "part_supposee_frais": part, "supposee_frais_fcfa": supposee},
            "lignes": [{"code": "A2", "montant": 100_000, "mot_statut": "supposé"}],
            "dividendes_en_baisse": [{"chute": 0.20, "reste_an1": 64_076}],
            "remise_a_niveau": {"bas": 34_745, "haut": 123_000}}


def _cache_poche() -> dict:
    """Cache écrit par « plan --perte-toleree 1000000 » à 10 M : l'écran (``plan``) décrit le capital total ; la clé
    ``rendement_net`` porte la facture de l'ordre affiché, celui des 3 000 000 FCFA en actions (pour_ordre_poche)."""
    rn_k = copy.deepcopy(J.RN_MINI)
    rn_k["bilan"] = _bilan(284_714, 124_126, 435_988, 0.63, 179_000)
    ecran = PL.construire_plan(rn_k, None, None, J.JOUR)
    rn_a = copy.deepcopy(rn_k)
    rn_a["bilan"] = _bilan(151_702, 107_018, 125_995, 0.80, 121_000)
    rn_a["contexte"].update({"poche": True, "capital_ordre": 3_000_000.0, "en_actions": 3_000_000.0,
                             "reserve": 7_000_000.0})
    c = J.cache_mini()
    c.update({"plan": ecran, "rendement_net": rn_a, "capital_ordre": 3_000_000.0, "perte_toleree": 1_000_000.0})
    return c


def _n(s: str) -> str:
    """Texte sur une ligne, espaces insécables et retours ramenés à des espaces."""
    return " ".join(str(s).replace("\u202f", " ").replace("\xa0", " ").split())


def _sans_seance_ni_feux(plan: dict) -> list:
    return [l for l in plan["lignes"] if l.get("bloc") not in ("etude", "feux")]


def test_card_with_accepted_loss_is_the_screen_of_the_command_except_session_and_lights():
    c = _cache_poche()
    jour = pd.Timestamp("2026-12-02")  # après le début du suivi : la phrase de la séance change de temps
    affiche = RN._plan_affiche(c, {}, None, jour)
    assert _sans_seance_ni_feux(affiche) == _sans_seance_ni_feux(c["plan"])
    t = _n(PL.rendre_plan(affiche, "texte"))
    assert "environ 290 000 FCFA de frais la 1re année, puis 130 000 par an" in t
    assert "160 000" not in t and "63 % de ces frais" in t
    etude = _n(" ".join(l["texte"] for l in affiche["lignes"] if l["bloc"] == "etude"))
    assert RG.phrase_seance(jour.date()) in etude and RG.phrase_seance(J.JOUR) not in etude
    assert any(l["bloc"] == "feux" for l in affiche["lignes"])


def test_result_page_with_accepted_loss_shows_the_total_capital_fees(ui):  # noqa: F811
    p = profil(ui)
    p.mkdir(parents=True, exist_ok=True)
    (p / "plan_cache.json").write_text(json.dumps(_cache_poche(), ensure_ascii=False), encoding="utf-8")
    status, _, body = call(ui, "GET", "/plan/resultat?format=texte")
    assert status == 200 and "environ 290 000 FCFA de frais" in _n(body) and "160 000" not in _n(body)
    status, _, body = call(ui, "GET", "/")
    t = _n(texte(body))
    assert status == 200 and "environ 290 000 FCFA de frais la 1re année" in t and "160 000" not in t


# ---------------------------------------------------------------------------
# Constat critique 2 : un seul champ saisi, un seul champ change de statut
# ---------------------------------------------------------------------------


def _formulaire_grille(body: str) -> dict:
    """Ce qu'un navigateur envoie pour le formulaire « Ce que prend mon courtier » tel qu'il est affiché."""
    m = re.search(r'<form method="post" action="/plan/grille".*?</form>', body, re.S)
    assert m, "formulaire de la grille absent"
    f = m.group(0)
    out = {}
    for n, v in re.findall(r'<input type="(?:text|hidden)"[^>]*?name="([^"]+)"[^>]*?value="([^"]*)"', f):
        out[n] = html.unescape(v)
    for n, v in re.findall(r'<select name="([^"]+)".*?<option value="([^"]*)" selected', f, re.S):
        out[n] = html.unescape(v)
    return out


def test_grid_form_marks_only_the_field_the_user_filled(ui):  # noqa: F811
    J.ecrire_cache(profil(ui))
    status, _, body = call(ui, "GET", "/")
    assert status == 200
    form = _formulaire_grille(body)
    for n in ("courtage", "taxe", "garde", "par_ligne", "forfait"):
        assert form[n] == "", n  # aucun champ prérempli : la valeur actuelle est un exemple grisé
    assert 'id="g-taxe" name="taxe" inputmode="decimal" value="" placeholder="18"' in body
    form.update({"courtage": "0,7", "statut": "grille écrite", "source": "lettre du courtier, courtage seul"})
    form.pop("_jeton", None)
    status, h, _ = post(ui, "/plan/grille", form)
    assert status == 303, h
    g = G.charger(profil(ui))
    assert g.valeur("courtage") == pytest.approx(0.007)
    assert g.champs["courtage"].statut == "grille écrite"
    assert g.champs["courtage"].source == "lettre du courtier, courtage seul"
    for champ in ("taxe_courtage", "garde", "tenue_par_ligne", "forfait_compte", "courtage_min_par_ordre"):
        assert g.champs[champ].statut == "supposé" and not g.champs[champ].source, champ
    status, _, body = call(ui, "GET", "/plan/resultat?format=texte")
    assert status == 200


def test_grid_from_form_one_filled_field_one_status_changed():
    avant = G.defaut()
    v = {"courtage": "0,7", "taxe": "", "garde": "", "par_ligne": "", "forfait": "", "statut": "grille écrite",
         "source": "grille 2026"}
    g = RN.grille_depuis_formulaire(v, avant, J.JOUR)
    changes = [k for k in g.champs if g.champs[k].statut != avant.champs[k].statut]
    assert changes == ["courtage"]
    # Une valeur retapée à l'identique est une confirmation explicite (comme « plan grille --taxe 18 --statut ecrit »)
    g2 = RN.grille_depuis_formulaire({**v, "taxe": "18"}, avant, J.JOUR)
    assert sorted(k for k in g2.champs if g2.champs[k].statut != avant.champs[k].statut) == ["courtage", "taxe_courtage"]


# ---------------------------------------------------------------------------
# Constat majeur 3 : verrou des journaux du suivi (deux écritures simultanées ; code 4)
# ---------------------------------------------------------------------------

from test_cli_rendement import (copie_du_depot, donnees, fausse_reco, one_json, rn10,  # noqa: E402,F401
                                run_cli)

from brvm_alpha import erreurs, fichiers  # noqa: E402
from brvm_alpha import suivi as SU  # noqa: E402
from brvm_alpha.suivi import carnet as CN  # noqa: E402
from brvm_alpha.suivi import declaration as DE  # noqa: E402


#: Petit programme lancé deux fois au même instant : la vraie commande, avec un ajout ralenti (0,5 s entre la lecture
#: de la chaîne et l'écriture), pour que les deux écritures se chevauchent à coup sûr.
_SAISIE = """
import sys, time
sys.path.insert(0, sys.argv[1])
from brvm_alpha import cli, cli_rendement, suivi as SU
from brvm_alpha.suivi import carnet
vrai = SU.ajouter_jsonl
def lent(*a, **k):
    time.sleep(0.5)
    return vrai(*a, **k)
SU.ajouter_jsonl = lent
depart = float(sys.argv[2])
while time.time() < depart:
    time.sleep(0.002)
sys.exit(cli.main(["suivi", "saisir", "--nom", "MOI", "--apport", sys.argv[3], "--format", "json"]))
"""


def test_two_simultaneous_entries_keep_the_chain_of_the_book(donnees, capsys, tmp_path):  # noqa: F811
    import os
    import subprocess
    import sys
    import time

    code, out, _ = run_cli(capsys, "suivi", "demarrer", "--nom", "MOI", "--format", "json")
    assert code == 0
    racine = str(Path(__file__).resolve().parents[1])
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1",
           "BRVM_ALPHA_DONNEES": str(donnees[0]), "BRVM_ALPHA_RAPPORTS": str(donnees[1])}
    depart = time.time() + 8.0  # le temps que les deux processus chargent le code
    ps = [subprocess.Popen([sys.executable, "-c", _SAISIE, racine, repr(depart), m], env=env, cwd=tmp_path,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for m in ("1000", "1001")]
    res = [p.communicate(timeout=120) + (p.returncode,) for p in ps]
    assert [r[2] for r in res] == [0, 0], res  # le second attend le premier, puis écrit à la suite
    for o, _e, _c in res:
        assert json.loads(o)["ok"] is True
    v = CN.ouvrir("MOI", donnees[0] / "suivi", creer=False).verifier()
    assert v["chaine_ok"] and v["n"] == 4, v
    assert [p.name for p in (donnees[0] / "suivi" / "MOI").iterdir()] == ["carnet.jsonl"]  # aucun fichier ajouté


def test_entry_while_the_journal_is_locked_exits_with_code_4(donnees, capsys, monkeypatch):  # noqa: F811
    import threading

    code, _, _ = run_cli(capsys, "suivi", "demarrer", "--nom", "MOI", "--format", "json")
    assert code == 0
    d = donnees[0] / "suivi" / "MOI"
    avant = (d / "carnet.jsonl").read_bytes()
    tenu, fin = threading.Event(), threading.Event()

    def tenir():  # une autre opération (« suivi maj » d'Odoo) tient le journal
        with SU.verrou_ecriture(d, quoi="suivi maj de MOI"):
            tenu.set()
            fin.wait(30)

    t = threading.Thread(target=tenir)
    t.start()
    try:
        assert tenu.wait(10)
        monkeypatch.setenv(fichiers.ENV_ATTENTE, "0.3")
        code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "MOI", "--apport", "5000", "--format", "json")
        r = one_json(out)
        assert code == 4 and r["erreur"] == "verrou_occupe" and "MOI" in r["message"], r
    finally:
        fin.set()
        t.join(10)
    assert (d / "carnet.jsonl").read_bytes() == avant  # rien n'est écrit
    monkeypatch.delenv(fichiers.ENV_ATTENTE)
    code, _, _ = run_cli(capsys, "suivi", "saisir", "--nom", "MOI", "--apport", "5000", "--format", "json")
    assert code == 0 and CN.ouvrir("MOI", donnees[0] / "suivi", creer=False).verifier()["n"] == 3


# ---------------------------------------------------------------------------
# Constat majeur 4 : « suivi declarer » refusé : rien n'est signé ; pas de deuxième signature identique
# ---------------------------------------------------------------------------


def _reponses(capsys, tmp_path):
    import suivi_jeux as SJ

    code, out, _ = run_cli(capsys, "suivi", "declarer", "--modele", "--format", "json")
    assert code == 0
    f = tmp_path / "reponses.json"
    f.write_text(json.dumps(SJ.reponses_proposees(one_json(out)["modele"]), ensure_ascii=False), encoding="utf-8")
    return f


def test_declarer_with_a_wrong_confirmation_signs_nothing(copie_du_depot, capsys, tmp_path):  # noqa: F811
    decl = copie_du_depot / "reports" / "suivi_S2" / "declaration.jsonl"
    f = _reponses(capsys, tmp_path)
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--fichier", str(f), "--signer", "AB", "--registre",
                           "--confirmer", "j'inscris au registre", "--format", "json")
    r = one_json(out)
    assert code == 2 and r["message"].startswith("refusé : ") and DE.CONFIRMATION_REGISTRE in r["message"]
    assert not decl.exists()  # refus avant toute signature
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--registre", "--confirmer", DE.CONFIRMATION_REGISTRE,
                           "--format", "json")
    assert code == 2 and "aucune déclaration signée" in one_json(out)["message"] and not decl.exists()


def test_declarer_refuses_a_second_identical_signature(copie_du_depot, capsys, tmp_path):  # noqa: F811
    decl = copie_du_depot / "reports" / "suivi_S2" / "declaration.jsonl"
    f = _reponses(capsys, tmp_path)
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--fichier", str(f), "--signer", "AB", "--format", "json")
    assert code == 0
    n = len(decl.read_text(encoding="utf-8").splitlines())
    for sig in ("AB", "CD"):
        code, out, _ = run_cli(capsys, "suivi", "declarer", "--fichier", str(f), "--signer", sig, "--format", "json")
        r = one_json(out)
        assert code == 2 and r["message"].startswith("refusé : déjà signés à l'identique"), r
        assert len(decl.read_text(encoding="utf-8").splitlines()) == n, sig
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--fichier", str(f), "--signer", "AB", "--registre",
                           "--confirmer", DE.CONFIRMATION_REGISTRE, "--format", "json")
    assert code == 2 and "--registre --confirmer" in one_json(out)["message"]
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--registre", "--confirmer", DE.CONFIRMATION_REGISTRE,
                           "--format", "json")
    assert code == 0 and "S2-REF" in one_json(out)["inscrits"]
    assert len(decl.read_text(encoding="utf-8").splitlines()) == n and DE.verifier(decl.parent)["chaine_ok"]


# ---------------------------------------------------------------------------
# Constat majeur 5 : taux de la réserve au-delà de 15 % refusé (code 2 ; 400 dans l'interface)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", [["plan"], ["recommend", "--capital", "10M"], ["report", "--capital", "10M"]])
def test_reserve_rate_above_the_maximum_is_refused_before_any_calculation(donnees, fausse_reco, capsys,  # noqa: F811
                                                                           argv):
    code, out, _ = run_cli(capsys, *argv, "--taux-reserve", "15,01", "--format", "json")
    r = one_json(out)
    assert code == 2 and "de 0 à 15 %" in r["message"] and fausse_reco == [], r
    assert not any(donnees[0].iterdir()) and not any(donnees[1].iterdir())


def test_reserve_rate_bounds():
    from brvm_alpha import cli_rendement as CR

    assert CR.parse_taux_reserve("15") == pytest.approx(0.15) and CR.parse_taux_reserve("0") == 0.0
    with pytest.raises(ValueError, match="de 0 à 15 %"):
        CR.parse_taux_reserve("15,01")


def test_reserve_rate_above_the_maximum_is_refused_by_the_interface(ui):  # noqa: F811
    status, _, body = post(ui, "/plan/enregistrer", {"perte": "1000000", "taux": "20"})
    assert status == 400 and "de 0 à 15 %" in html.unescape(body)
    assert not (profil(ui) / "plan.json").exists()


# ---------------------------------------------------------------------------
# Constat majeur 6 : « --arrondi restes » sur un tarif supposé : code 2 avant le calcul, sous les deux contrats
# ---------------------------------------------------------------------------


def test_restes_rounding_on_an_assumed_grid_is_refused_before_the_calculation(donnees, fausse_reco,  # noqa: F811
                                                                              capsys):
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--arrondi", "restes", "--format", "json")
    r = one_json(out)
    assert code == 2 and "--forcer" in r["message"] and fausse_reco == [], r
    g = G.defaut().avec(courtage=0.007)
    g.champs["courtage"].statut, g.champs["courtage"].source = G.ECRITE, "grille 2026"
    G.enregistrer(g)
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--arrondi", "restes", "--grille", "ma_sgi",
                           "--format", "json")
    assert code == 2 and fausse_reco == []  # un seul champ principal écrit : la grille reste supposée
    for k in G.PRINCIPAUX:
        g.champs[k].statut, g.champs[k].source = G.ECRITE, "grille 2026"
    G.enregistrer(g)
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--arrondi", "restes", "--grille", "ma_sgi",
                           "--format", "json")
    assert code == 0 and fausse_reco[-1]["arrondi"] == "restes"


def test_input_refusals_of_the_calculation_are_saisie_invalide():
    """Avec le contrat d'erreurs de l'autre chantier, une ValueError sort en code 7 : les refus de saisie levés pendant
    le calcul sont des SaisieInvalide (classe fille de ValueError), donc le code 2 sous les deux contrats."""
    from brvm_alpha.portfolio import recommend as rec
    from brvm_alpha.rendement import liquidites as LQ

    with pytest.raises(erreurs.SaisieInvalide):
        LQ.arrondi_restes(J.ORDRE_MINI, None, G.defaut(), appliquer=True)
    for kw in ({"apport": -1.0}, {"apport": 5.0}, {"apport": 5.0, "cash": 1.0}, {"arrondi": "haut"}):
        with pytest.raises(erreurs.SaisieInvalide) as e:
            rec.recommend("2026-11-20", 1_000_000.0, **kw)
        assert erreurs.code_retour(e.value) == 2


# ---------------------------------------------------------------------------
# Constats mineurs retenus
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def synthese(tmp_path_factory):
    import rendement_jeux as RJ

    tmp = tmp_path_factory.mktemp("poche")
    return RJ.panel_synthese(), tmp, RJ.registre_vide(tmp / "trials.parquet")


def _ordre(synthese, **kw):
    import warnings

    from brvm_alpha.portfolio import recommend as rec

    P, tmp, reg = synthese
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return rec.recommend(P["close"].index[-1], 5_000_000, panels=P, validation_dir=tmp / "absent",
                             registry_path=reg, notes_store=False, n_boot=300, seed=0, comparison=False,
                             tolerance=0.03, **kw)


def test_pocket_order_keeps_the_index_evaluation_of_the_call(synthese, monkeypatch):
    from brvm_alpha.portfolio import recommend as rec

    lignes = [{"indice": "IDX:BRVM-C", "libelle": "BRVM Composite", "position": "NEUTRE"}]
    monkeypatch.setattr(rec, "_index_evaluation", lambda *a, **k: (list(lignes), "indices évalués (essai)"))
    o = _ordre(synthese, index_evaluation=True, perte_toleree=1_000_000)
    assert o.rendement_net["contexte"]["poche"] is True and o.capital < 5_000_000
    assert o.declencheurs["indices"] == lignes and o.declencheurs["indices_message"] == "indices évalués (essai)"
    assert rec.AVERT_SANS_POCHE not in " ".join(o.avertissements)


def test_without_a_pocket_order_the_total_capital_order_says_so(synthese, monkeypatch):
    from brvm_alpha import rendement
    from brvm_alpha.portfolio import recommend as rec

    o = _ordre(synthese, index_evaluation=False, perte_toleree=1)  # aucune poche possible pour 1 FCFA
    assert o.capital == 5_000_000 and o.avertissements[-1].startswith(rec.AVERT_SANS_POCHE)
    o2 = _ordre(synthese, index_evaluation=False)  # sans perte acceptée : aucun avertissement de plus
    assert not any(a.startswith(rec.AVERT_SANS_POCHE) for a in o2.avertissements)

    def panne(*a, **k):
        raise RuntimeError("module en panne")

    monkeypatch.setattr(rendement, "construire", panne)
    o3 = _ordre(synthese, index_evaluation=False, perte_toleree=1_000_000)
    assert o3.rendement_net == {} and o3.avertissements[-1] == rec.AVERT_SANS_POCHE
    assert o3.avertissements[:-1] == o2.avertissements[:len(o3.avertissements) - 1]


def test_export_with_nothing_to_copy_exits_with_code_1_and_creates_nothing(donnees, capsys):  # noqa: F811
    code, _, _ = run_cli(capsys, "suivi", "demarrer", "--nom", "MOI", "--format", "json")
    assert code == 0
    dest = donnees[1] / "export_suivi"  # chemin absolu : jamais dans l'arbre du code
    for _ in range(2):
        code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(dest), "--format", "json")
        r = one_json(out)
        assert code == 1 and "rien à copier" in r["message"] and "--avec-moi" in r["message"], r
    assert not dest.exists() and not any(donnees[1].iterdir())
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(dest), "--avec-moi", "--format", "json")
    assert code == 0 and one_json(out)["fichiers"] == ["MOI/carnet.jsonl"]


def test_suivi_maj_headers_and_state_files_are_written_atomically(tmp_path, monkeypatch):
    from brvm_alpha.suivi import bulletin as BU
    from brvm_alpha.suivi import temoin as TM

    ecrits = []
    vrai = fichiers.ecrire_atomique

    def note(p, data, **k):
        ecrits.append(Path(p).name)
        return vrai(p, data, **k)

    monkeypatch.setattr(fichiers, "ecrire_atomique", note)
    df = pd.DataFrame({"date": pd.to_datetime(["2026-12-01", "2026-12-02"]), "x": [1.0, 2.0]})
    TM._ecrire_csv_ajout(tmp_path / "operations.csv", df, "date", pd.Timestamp("2026-12-02"))
    BU.ecrire_semaines("MOI", [], tmp_path)
    assert ecrits == ["operations.csv", "semaines.csv"]
    assert (tmp_path / "operations.csv").read_text(encoding="utf-8").splitlines()[0] == "date,x"


def test_plan_refuses_an_accepted_loss_above_the_capital(donnees, fausse_reco, capsys):  # noqa: F811
    code, out, _ = run_cli(capsys, "plan", "--capital", "10M", "--perte-toleree", "20M", "--format", "json")
    r = one_json(out)
    assert code == 2 and "dépasse le capital total" in r["message"] and fausse_reco == []
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--perte-toleree", "20M", "--format", "json")
    assert code == 2 and fausse_reco == []
    assert not any(donnees[0].iterdir())


def test_tiny_capital_screen_says_no_share_is_bought():
    rn = copy.deepcopy(J.RN_MINI)
    rn["contexte"]["capital"] = 1_000.0
    rn["perte"]["table"] = [
        {"perte_toleree": 100.0, "tout": False, "en_actions": 0, "reserve": 1_000, "investi": 0,
         "message": "À ce tarif, le plus petit montant en actions à 20 lignes risque plus que ce que vous acceptez."},
        {"perte_toleree": None, "tout": True, "en_actions": 1_000, "reserve": 0, "investi": 0}]
    t = _n(PL.rendre_plan(PL.construire_plan(rn, None, None, J.JOUR), "texte"))
    assert "Avec 1 000 FCFA, l'ordre n'achète aucun titre" in t and "ce que vous acceptez" not in t
    assert RG.mots_interdits(t) == []
    # Table ordinaire : une ligne proposée sans montant en actions dit « ce montant », pas « ce que vous acceptez ».
    rn["perte"]["table"][1]["investi"] = 900
    t2 = _n(PL.rendre_plan(PL.construire_plan(rn, None, None, J.JOUR), "texte"))
    assert "risque plus que ce montant" in t2 and "ce que vous acceptez" not in t2


def test_provision_margins_and_statuses_are_written_in_the_detail():
    from brvm_alpha.rendement import rendu as RD

    rn = {"grille": {"statut_global": "supposé"},
          "liquidites": {"provision": {"texte": "Provision à avoir avant l'ordre : 9 866 731 FCFA.", "marge": 133_269,
                                       "marge_courtage_plus_cher": 110_269, "surcout_courtage_test": 0.002,
                                       "statut": "Hypothèse"}}}
    t = _n(RD.ligne_execution(rn))
    assert "Marge : +133 269 FCFA ; avec un courtage plus cher de 0,2 point : +110 269 FCFA" in t
    assert t.endswith("[supposé] ; provision calculée sur un tarif supposé.")
    rn["grille"]["statut_global"] = "grille écrite"
    assert "tarif supposé" not in RD.ligne_execution(rn) and RD.ligne_execution(rn).endswith("[estimé].")


def test_w4_with_an_unknown_cause_does_not_claim_it_is_outside_the_tested_rule():
    from brvm_alpha.rendement import alertes as AL

    def w4(cause):
        aqd = {"D": 1_403_292, "D_prevu": 218_672, "D_hors_regle": 1_184_620,
               "causes": [{"code": cause, "cause": cause, "montant": 1_184_620, "prevu": False}]}
        al = AL.alertes_fuite(J.ORDRE_MINI, {"liquidites": {"argent_qui_dort": aqd}}, None, None)
        return next(a for a in al if a["code"] == "W4")

    w = w4("inconnue")
    assert w["prefixe"] == "FUITE" and w["niveau"] == "orange"
    assert "sans cause mesurée" in w["texte"] and "hors de la règle testée" not in w["texte"]
    assert "hors de la règle testée" in w4("ordres non servis")["texte"]  # cause mesurée : texte inchangé


from test_report_rendement import _render, _section, _sous_bloc, synth  # noqa: E402,F401


def test_report_label_bulletin_types_and_statuses(synth, tmp_path, monkeypatch):  # noqa: F811
    from brvm_alpha import paths as PA
    from brvm_alpha.rendement import risque as RQ

    monkeypatch.setattr(PA, "DATA_DIR", tmp_path / "donnees_vides")
    r = _render(synth)
    h = html.unescape(r.html)
    d = _section(h, "distribution")
    assert RQ.LIBELLE_P_BATTRE_TR in d and "P(battre le TR)" not in d
    k = _sous_bloc(h, "risques")
    assert "BULLETIN DE LA SEMAINE" in k and not re.search(r"^\s*#", k, re.M) and "# BULLETIN" not in k
    m = _sous_bloc(h, "methode")
    assert ".." not in re.sub(r"\.\.\.|…", "", texte(m)) and "référence (témoin)" in m and ">reference<" not in m
    o = _sous_bloc(h, "ordre")
    assert "Marge : " in o and "avec un courtage plus cher de 0,2 point" in o
    b = _sous_bloc(h, "bandeau")
    assert b.index(RG.BANNER) < b.index("Étude seulement")  # bandeau en tête de la carte (§F1)


def test_interface_entry_while_the_journal_is_locked_answers_409(ui):  # noqa: F811
    import threading

    from test_ui_rendement import demarrer, suivi

    c = demarrer(ui)
    avant = c.fichier.read_bytes()
    tenu, fin = threading.Event(), threading.Event()

    def tenir():
        with SU.verrou_ecriture(c.dossier, quoi="suivi maj de MOI"):
            tenu.set()
            fin.wait(30)

    t = threading.Thread(target=tenir)
    t.start()
    try:
        assert tenu.wait(10)
        import os

        os.environ[fichiers.ENV_ATTENTE] = "0.3"
        try:
            status, _, body = post(ui, "/suivi/saisir", {"nom": "MOI", "quoi": "apport", "montant": "5000"})
        finally:
            del os.environ[fichiers.ENV_ATTENTE]
        assert status == 409 and "verrou occupé" in html.unescape(body)
    finally:
        fin.set()
        t.join(10)
    assert c.fichier.read_bytes() == avant and suivi(ui) == c.dossier.parent
