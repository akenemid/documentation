"""F9 — Déclaration du suivi sur papier (cahier ``docs/RENDEMENT_NET.md``, §F9 et §8).

Tous les tests travaillent sur des copies dans des dossiers temporaires : la déclaration n'est jamais écrite dans
``reports/suivi_S2/`` et le registre du dépôt (``reports/trials.parquet``) n'est jamais ouvert en écriture.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

import suivi_jeux as J
from brvm_alpha.backtest.walkforward import STATUT_PREENREGISTRE, TrialRegistry
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.suivi import declaration as D

AVANT = "2026-11-25T10:00:00Z"


#: Provenance écrite au registre pour une déclaration de test (dossier temporaire hors du dépôt) : passée
#: explicitement, jamais fabriquée par la fonction.
SOURCE = "reports/suivi_S2"


@pytest.fixture(scope="module", autouse=True)
def registre_du_depot_intact():
    avant = J.sha(J.REGISTRE_DU_DEPOT)
    suivi = J.RACINE / "reports" / "suivi_S2"
    existait = suivi.exists()
    yield
    assert J.sha(J.REGISTRE_DU_DEPOT) == avant
    assert suivi.exists() == existait


def _signer(tmp_path, **choix):
    arts = J.reponses_proposees(D.modele(), **choix)
    p = D.signer(arts, "AB", tmp_path / "decl", racine=J.depot(tmp_path), profil=tmp_path / "profil", maintenant=AVANT)
    return p


def test_modele_articles_propositions_et_phrases_simples():
    arts = D.modele()
    assert [a["id"] for a in arts] == ["REF-S2", "E-L", "E-B", "E-A", "N", "E-C", "E-D", "PLAN"]
    props = {a["id"]: a["proposition"] for a in arts}
    assert props["E-L"] == "oui" and props["E-B"] == "oui" and props["E-C"] == "option 1" and props["E-D"] == "option 1"
    assert props["PLAN"] == "avec les notes" and "choix" in props["E-A"]
    for a in arts:
        assert a["type"] in D.TYPES and a["id"] in D.IDS
        assert RG.mots_interdits(a["phrase"]) == [], a["id"]
        assert RG.compter_mots(a["phrase"]) <= 25
        assert a["reponse"] is None or not a["reponse_requise"]
    n = next(a for a in arts if a["id"] == "N")
    assert n["parametres"]["seuils"]["t_retrait"] == -2.0 and n["hypotheses_de_travail"]
    ref = next(a for a in arts if a["id"] == "REF-S2")
    assert ref["parametres"]["notes"] is None and ref["parametres"]["couts"] == "central"
    assert ref["parametres"]["capital_fcfa"] == 10_000_000 and ref["registre"]["famille"] == "S2-temoin"
    # Départ figé du témoin (§8.2), écrit en date exacte dans l'article.
    assert ref["parametres"]["date_premiere_decision"] == "2026-11-30" and "2026-11-30" in ref["regle"]["depart"]


def test_signature_chaine_et_ajout_seul(tmp_path):
    p = _signer(tmp_path)
    v = D.verifier(p.parent)
    assert v["ok"] and v["n_lignes"] == 8 and v["chaine_ok"]
    ls = D.lignes(p.parent)
    assert [l["n"] for l in ls] == list(range(1, 9))
    for l in ls:
        assert l["signe_par"] == "AB" and l["effet_a_partir_du"] == "2026-12-01"
        assert len(l["empreinte_config"]) == 16 and len(l["empreinte_reglages"]) == 64 and l["version_code"]
        assert l["empreinte_cahier"] is None or len(l["empreinte_cahier"]) == 64
    assert ls[0]["precedente"] == "0" * 64
    plan = next(l for l in ls if l["id"] == "PLAN")
    # E-A : « au choix » ; l'aide de test répond par le premier choix (« oui »)
    assert plan["parametres"]["ecarts_oui"] == ["E-L", "E-B", "E-A", "E-C", "E-D"]
    assert plan["parametres"]["notes_dans_l_ordre"] is True
    texte = p.read_text(encoding="utf-8").splitlines()
    # réécriture d'une ligne : la chaîne est rompue
    modif = texte.copy()
    modif[2] = modif[2].replace("12 mois", "6 mois")
    p.write_text("\n".join(modif) + "\n", encoding="utf-8")
    v = D.verifier(p.parent)
    assert not v["ok"] and any("ligne 3" in a for a in v["anomalies"])
    # ligne retirée
    p.write_text("\n".join(texte[:3] + texte[4:]) + "\n", encoding="utf-8")
    assert not D.verifier(p.parent)["chaine_ok"]
    # lignes inversées
    p.write_text("\n".join([texte[1], texte[0]] + texte[2:]) + "\n", encoding="utf-8")
    assert not D.verifier(p.parent)["chaine_ok"]
    # chaîne rompue : aucune ligne ne peut être ajoutée
    arts = J.reponses_proposees(D.modele())
    with pytest.raises(ValueError, match="chaîne de la déclaration rompue"):
        D.signer(arts[:1], "AB", p.parent, racine=J.depot(tmp_path), profil=tmp_path / "profil")
    p.write_text("\n".join(texte) + "\n", encoding="utf-8")
    assert D.verifier(p.parent)["ok"]


def test_ligne_tardive_ne_vaut_que_pour_l_avenir(tmp_path):
    arts = J.reponses_proposees(D.modele())
    d = tmp_path / "decl"
    D.signer(arts[:1], "AB", d, racine=J.depot(tmp_path), maintenant=AVANT)
    rempl = dict(arts[1], type="remplace", remplace_n=2, phrase="Ordres à cours limité, test plus court.")
    D.signer([rempl], "AB", d, racine=J.depot(tmp_path), maintenant="2026-12-04T18:00:00Z")
    ls = D.lignes(d)
    assert ls[0]["effet_a_partir_du"] == "2026-12-01" and not ls[0]["declaree_apres_debut"]
    assert ls[1]["effet_a_partir_du"] == "2026-12-07" and ls[1]["declaree_apres_debut"]  # vendredi soir → lundi
    assert D.verifier(d)["ok"]
    v1 = D.en_vigueur("2026-12-04", d)
    assert "E-L" not in v1["articles"] and "REF-S2" in v1["articles"]
    v2 = D.en_vigueur("2026-12-07", d)
    assert v2["articles"]["E-L"]["type"] == "remplace" and v2["mention"] == "déclarée après le début du suivi"


def test_sans_declaration_seul_le_temoin(tmp_path):
    v = D.en_vigueur("2026-12-02", tmp_path / "vide")
    assert not v["declaration"] and list(v["articles"]) == ["REF-S2"]
    assert "seul le panier de référence" in v["mention"]
    assert D.verifier(tmp_path / "vide")["existe"] is False


def test_inscription_au_registre_sur_une_copie(tmp_path):
    reg = J.registre(tmp_path)
    avant = pd.read_parquet(reg)
    assert len(avant) == 98
    emp = D.empreinte_lignes(avant)
    p = _signer(tmp_path)
    ids = D.inscrire_au_registre(p.parent, reg, confirmer=D.CONFIRMATION_REGISTRE, source_base=SOURCE)
    assert ids == ["S2-REF", "S2-N", "S2-EC", "S2-ED", "S2-PLAN"]
    apres = pd.read_parquet(reg)
    assert len(apres) == 103 and D.empreinte_lignes(apres, 98) == emp
    neuf = apres.iloc[98:]
    assert set(neuf["echantillon"]) == {"S2"} and set(neuf["statut"]) == {STATUT_PREENREGISTRE}
    fam = dict(zip(neuf["id"], neuf["famille"], strict=True))
    assert fam == {"S2-REF": "S2-temoin", "S2-N": "S2-rendement", "S2-EC": "S2-rendement", "S2-ED": "S2-rendement",
                   "S2-PLAN": "S2-execution"}
    assert neuf["source"].str.match(r"^reports/suivi_S2/declaration\.jsonl#\d+$").all()
    assert json.loads(neuf.iloc[0]["parametres"])["parametres"]["variante"] == "REF"
    assert TrialRegistry.load(reg).n_trials("S2") == 5
    # seconde inscription : aucune ligne en double
    assert D.inscrire_au_registre(p.parent, reg, confirmer=D.CONFIRMATION_REGISTRE, source_base=SOURCE) == []
    assert len(pd.read_parquet(reg)) == 103


def test_derogation_signee_trois_lignes_seulement(tmp_path):
    reg = J.registre(tmp_path)
    p = _signer(tmp_path, E_C="option 2 : oui", E_D="option 2 : non", E_A="non")
    ls = D.lignes(p.parent)
    der = [l for l in ls if l["type"] == "derogation"]
    assert [l["id"] for l in der] == ["E-C", "E-D"]
    assert all("nouvel essai à juger sur S2 seulement" in l["parametres"]["texte_cite"] for l in der)
    plan = next(l for l in ls if l["id"] == "PLAN")
    assert plan["parametres"]["ecarts_oui"] == ["E-L", "E-B", "E-C"]
    assert D.inscrire_au_registre(p.parent, reg, confirmer=D.CONFIRMATION_REGISTRE, source_base=SOURCE) == ["S2-REF", "S2-N", "S2-PLAN"]


def test_non_declare_reste_eteint(tmp_path):
    p = _signer(tmp_path, E_C="non déclaré", E_D="non déclaré", E_A="non")
    ids = [l["id"] for l in D.lignes(p.parent)]
    assert "E-C" not in ids and "E-D" not in ids and "E-A" in ids
    plan = next(l for l in D.lignes(p.parent) if l["id"] == "PLAN")
    assert plan["parametres"]["ecarts_oui"] == ["E-L", "E-B"]


def test_inscription_refusee_sans_confirmation_ni_registre_explicite(tmp_path):
    reg = J.registre(tmp_path)
    h = J.sha(reg)
    p = _signer(tmp_path)
    with pytest.raises(PermissionError):
        D.inscrire_au_registre(p.parent, reg, confirmer="oui", source_base=SOURCE)
    with pytest.raises(ValueError, match="chemin obligatoire"):
        D.inscrire_au_registre(p.parent, None, confirmer=D.CONFIRMATION_REGISTRE, source_base=SOURCE)
    with pytest.raises(FileNotFoundError):
        D.inscrire_au_registre(p.parent, tmp_path / "autre.parquet", confirmer=D.CONFIRMATION_REGISTRE, source_base=SOURCE)
    assert not (tmp_path / "autre.parquet").exists() and J.sha(reg) == h
    # chaîne rompue : inscription refusée
    t = p.read_text(encoding="utf-8").replace("12 mois", "6 mois", 1)
    p.write_text(t, encoding="utf-8")
    with pytest.raises(ValueError, match="chaîne rompue"):
        D.inscrire_au_registre(p.parent, reg, confirmer=D.CONFIRMATION_REGISTRE, source_base=SOURCE)
    assert J.sha(reg) == h


@pytest.mark.parametrize("sig", ["ABCDEFGHIJKLM", "A B", "a@b", "", "J.P"])
def test_signature_refusee(tmp_path, sig):
    with pytest.raises(D.SignatureInvalide):
        D.signer(J.reponses_proposees(D.modele()), sig, tmp_path / "decl", racine=J.depot(tmp_path))
    assert not (tmp_path / "decl").exists()


def test_signature_lue_dans_le_profil(tmp_path):
    prof = tmp_path / "profil"
    prof.mkdir()
    (prof / "signature.json").write_text(json.dumps({"signe_par": "JK-2"}), encoding="utf-8")
    arts = J.reponses_proposees(D.modele())
    p = D.signer(arts, None, tmp_path / "d1", racine=J.depot(tmp_path), profil=prof, maintenant=AVANT)
    assert {l["signe_par"] for l in D.lignes(p.parent)} == {"JK-2"}
    with pytest.raises(D.SignatureInvalide, match="profil"):
        D.signer(arts, "XY", tmp_path / "d2", racine=J.depot(tmp_path), profil=prof)
    h = "a" * 64
    (prof / "signature.json").write_text(json.dumps({"signe_par_empreinte": h}), encoding="utf-8")
    p = D.signer(arts, None, tmp_path / "d3", racine=J.depot(tmp_path), profil=prof, maintenant=AVANT)
    l0 = D.lignes(p.parent)[0]
    assert l0["signe_par_empreinte"] == h and "signe_par" not in l0
    with pytest.raises(D.SignatureInvalide, match="aucune signature"):
        D.signer(arts, None, tmp_path / "d4", racine=J.depot(tmp_path), profil=tmp_path / "vide")


def test_hors_depot_de_developpement_refus_code_2_rien_ecrit(tmp_path, monkeypatch):
    install = tmp_path / "installation"
    install.mkdir()
    monkeypatch.setenv("BRVM_ALPHA_DONNEES", str(tmp_path / "donnees"))
    assert not D.depot_de_developpement(install)
    with pytest.raises(D.HorsDepot) as e:
        D.signer(J.reponses_proposees(D.modele()), "AB", install / "reports" / "suivi_S2", racine=install)
    assert e.value.code == 2 and str(e.value) == D.MESSAGE_HORS_DEPOT
    assert not (install / "reports").exists() and not (tmp_path / "donnees").exists()
    assert D.depot_de_developpement(J.depot(tmp_path))


def test_reponses_manquantes_et_dossier_obligatoire(tmp_path):
    arts = D.modele()
    with pytest.raises(ValueError, match="déclaration incomplète"):
        D.signer(arts, "AB", tmp_path / "decl", racine=J.depot(tmp_path))
    with pytest.raises(ValueError, match="dossier"):
        D.signer(J.reponses_proposees(D.modele()), "AB", None, racine=J.depot(tmp_path))
    bad = J.reponses_proposees(D.modele())
    bad[1]["reponse"] = "peut-être"
    with pytest.raises(ValueError, match="E-L"):
        D.signer(bad, "AB", tmp_path / "decl", racine=J.depot(tmp_path))
    assert not (tmp_path / "decl").exists()


def test_aucune_donnee_personnelle_dans_la_declaration(tmp_path):
    p = _signer(tmp_path)
    t = p.read_text(encoding="utf-8")
    assert "@" not in t and str(tmp_path) not in t
    for l in D.lignes(p.parent):
        assert set(l) & {"nom", "adresse", "courriel", "email"} == set()


def test_provenance_jamais_fabriquee_hors_du_depot(tmp_path):
    reg = J.registre(tmp_path)
    h = J.sha(reg)
    p = _signer(tmp_path)
    # Dossier temporaire, hors du dépôt : sans source_base explicite, l'inscription est refusée (aucune provenance
    # « reports/suivi_S2/... » inventée) et le registre ne change pas.
    with pytest.raises(ValueError, match="n'est pas dans le dépôt"):
        D.inscrire_au_registre(p.parent, reg, confirmer=D.CONFIRMATION_REGISTRE)
    assert J.sha(reg) == h
    ids = D.inscrire_au_registre(p.parent, reg, confirmer=D.CONFIRMATION_REGISTRE, source_base="essai/copie")
    assert ids and pd.read_parquet(reg).iloc[98:]["source"].str.match(r"^essai/copie/declaration\.jsonl#\d+$").all()


def test_troncature_des_dernieres_lignes_detectee_par_le_registre(tmp_path):
    reg = J.registre(tmp_path)
    p = _signer(tmp_path)
    assert D.inscrire_au_registre(p.parent, reg, confirmer=D.CONFIRMATION_REGISTRE, source_base=SOURCE)
    assert D.verifier(p.parent, registre=reg)["chaine_ok"]
    sceau = json.loads(pd.read_parquet(reg).iloc[98]["parametres"])["declaration"]
    assert sceau["n"] == 1 and sceau["n_lignes"] == 8 and len(sceau["empreinte_derniere"]) == 64
    texte = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(texte[:7]) + "\n", encoding="utf-8")  # « head -n 7 » : la dernière ligne (PLAN) disparaît
    assert D.verifier(p.parent)["chaine_ok"]  # la chaîne seule ne le voit pas
    v = D.verifier(p.parent, registre=reg)
    assert not v["chaine_ok"] and any("dernières lignes retirées" in a for a in v["anomalies"])
    assert "PLAN" not in D.en_vigueur("2026-12-02", p.parent)["articles"]  # d'où la lecture du registre


def test_entree_en_plusieurs_fois_E_T_signee_apres_le_debut(tmp_path):
    d = tmp_path / "decl"
    D.signer(J.reponses_proposees(D.modele())[:1], "AB", d, racine=J.depot(tmp_path), maintenant=AVANT)
    e_t = {"type": "ecart_execution", "id": "E-T", "choix": ["oui", "non"], "reponse": "oui", "proposition": None,
           "phrase": "Entrer en trois fois, chaque tranche recalculée sur les liquidités réelles.",
           "regle": {"texte": "F15 : trois tranches, option --apport"}, "parametres": {"tranches": 3},
           "duree_min": "12 mois", "decision_ecrite": "Écart de calendrier déclaré (§8.3).", "source_spec": "cahier §8.3"}
    D.signer([e_t], "AB", d, racine=J.depot(tmp_path), maintenant="2026-12-10T09:00:00Z")
    l = D.lignes(d)[-1]
    assert l["id"] == "E-T" and l["effet_a_partir_du"] == "2026-12-11" and l["declaree_apres_debut"]
    assert "E-T" not in D.en_vigueur("2026-12-10", d)["articles"]
    assert D.en_vigueur("2026-12-11", d)["articles"]["E-T"]["type"] == "ecart_execution"


def test_options_melangees_pour_E_C_et_E_D_refusees(tmp_path):
    arts = J.reponses_proposees(D.modele(), E_C="option 1", E_D="option 2 : oui")
    with pytest.raises(ValueError, match="une seule option pour les deux"):
        D.preparer(arts)
    with pytest.raises(ValueError, match="une seule option"):
        D.signer(arts, "AB", tmp_path / "decl", racine=J.depot(tmp_path), maintenant=AVANT)
    assert not (tmp_path / "decl").exists()
    # « non déclaré » pour l'un et l'option 1 pour l'autre reste permis (§13.3 : déclarer E-D, ou non).
    assert [a["id"] for a in D.preparer(J.reponses_proposees(D.modele(), E_C="option 1", E_D="non déclaré"))
            if a["id"] in ("E-C", "E-D")] == ["E-C"]


def test_un_dossier_git_seul_n_est_pas_le_depot_de_developpement(tmp_path):
    # Une installation copiée avec un .git, sans le registre suivi par git, ne peut pas signer.
    faux = J.faux_depot(tmp_path)
    assert not D.depot_de_developpement(faux)
    with pytest.raises(D.HorsDepot):
        D.signer(J.reponses_proposees(D.modele()), "AB", tmp_path / "decl", racine=faux, maintenant=AVANT)
    assert not (tmp_path / "decl").exists()
    assert D.depot_de_developpement(J.depot(tmp_path)) and D.depot_de_developpement()  # la copie de travail : oui


def test_document_signe_est_la_copie_integrale_du_cahier():
    # §8.7, étape 1 : docs/RENDEMENT_NET.md contient le cahier en entier (partie B), dont l'empreinte date la
    # déclaration ; seuls les chemins de travail sont remplacés par des repères neutres.
    doc = (J.RACINE / "docs" / "RENDEMENT_NET.md").read_text(encoding="utf-8")
    assert "# Partie B — Le cahier des charges, copie intégrale" in doc
    b = doc.split("# Partie B — Le cahier des charges, copie intégrale", 1)[1]
    assert len(b.splitlines()) >= 1786
    for n in range(17):
        assert f"\n## {n}. " in b, n
    for n in range(1, 17):
        assert f"\n### F{n} — " in b, n
    for extrait in ("### 9.1 Trois exceptions déclarées aux tests existants", "(1,645 × 4,31 % × √durée en années)",
                    "le moteur du test, plus un seul refus explicite (forfait de compte non nul, §4.3)",
                    "Règles du mode `limite` :", "**(c) Arrondi « plus forts restes » : `--arrondi restes`.**",
                    "## 14. Registre des chiffres clés", "`M/` = `<mesures>/`", "`D/` = `<dépôt>/`", "cd <mesures>/final"):
        assert extrait in b, extrait
    for interdit in ("/tmp/", "/home/", "scratchpad"):
        assert interdit not in doc.lower(), interdit
    # La partie A (résumé) ne contredit plus l'article 1 : le moteur reçoit un seul ajout (refus du forfait de compte).
    a = doc.split("# Partie B", 1)[0]
    assert "le moteur du test, sans modification" not in a and "ni le moteur, ni" not in a
    assert "plus un seul refus explicite : forfait de compte non nul" in a
    assert "## Notes de la copie" in a and "environ 25 % à 40 %" in " ".join(a.split())
