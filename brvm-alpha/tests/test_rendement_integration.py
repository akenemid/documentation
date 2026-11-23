"""``rendement.construire`` : clé ``rendement_net`` de l'ordre de bataille (cahier ``docs/RENDEMENT_NET.md``, §4.3,
§4.5). Ne lève jamais ; accepte l'``OrdreDeBataille`` ou son dictionnaire ; n'écrit rien ; ne se rappelle jamais
elle-même ; aucune donnée réelle de l'installation lue (ordres et extraits figés, panel de synthèse)."""

from __future__ import annotations

import hashlib
import json
import time

import pytest

import rendement_jeux as J
from brvm_alpha import rendement
from brvm_alpha.rendement import reglages as RG

CLES_45 = ("version", "bandeau", "etude", "grille", "bilan", "leviers", "perte", "reserve", "risque", "liquidites",
           "passer_l_ordre", "alertes", "suivi", "plan")


def _empreinte(chemins):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in chemins}


def _proteges():
    r = J.RACINE
    return sorted((r / "reports" / "validation_S1").glob("*.*")) + [r / "reports" / "trials.parquet",
                                                                    r / "configs" / "strategy_v1.yaml",
                                                                    r / "configs" / "rendement_net.yaml"]


@pytest.fixture(scope="module")
def synthese(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("integ")
    P = J.panel_synthese()
    return P, tmp, J.ordre_synthese(P, 5_000_000, tmp)


def test_objet_ou_dictionnaire_meme_resultat(synthese):
    P, tmp, O = synthese
    a = rendement.construire(O, panels=P, validation_dir=tmp / "vide", aujourd_hui=J.AUJOURD_HUI, graines=2)
    b = rendement.construire(O.to_dict(), panels=P, validation_dir=tmp / "vide", aujourd_hui=J.AUJOURD_HUI, graines=2)
    a.pop("duree_s"), b.pop("duree_s")
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    for k in CLES_45:
        assert k in a, k
    for k in ("bilan", "leviers", "perte", "reserve", "risque", "plan", "etude", "grille"):
        assert not a[k].get("erreur"), (k, a[k].get("erreur"))


def test_contenu_du_bloc_etude_et_du_json(synthese):
    P, tmp, O = synthese
    rn = rendement.construire(O, panels=P, validation_dir=tmp / "vide", aujourd_hui="2026-11-24", graines=1)
    json.dumps(rn, ensure_ascii=False, allow_nan=False)
    assert rn["version"] == 1 and rn["bandeau"] == RG.BANNER
    e = rn["etude"]
    assert e["argent_reel_recommande"] is False and e["debut_suivi"] == "2026-12-01"
    assert e["phrases"] == [RG.PH_ETUDE, RG.phrase_seance("2026-11-24")]
    assert rn["reserve"]["deduit_de_la_perte"] is False
    assert rn["perte"]["chocs"]["ref_publie_source"] == "repli"  # aucun fichier S1 publié dans le dossier donné
    assert rn["suivi"] is None and rn["plan"]["feux"]["suivi_commence"] is False
    assert isinstance(rn["avertissements_a_ajouter"], list) and len(rn["avertissements_a_ajouter"]) <= 3


@pytest.mark.parametrize("mauvais", [None, {}, "texte", 42, {"lignes": "x", "couts": None}])
def test_ne_leve_jamais(mauvais):
    rn = rendement.construire(mauvais, panels={"tr_index": "x"}, perte_toleree="beaucoup")
    assert isinstance(rn, dict) and rn["bandeau"] == RG.BANNER
    json.dumps(rn, ensure_ascii=False, default=str)


def test_appel_recursif_refuse_et_ordre_de_la_poche_rendu():
    o = J.ordre("10M")
    vu = {}

    def verifier(A):
        vu["imbrique"] = rendement.construire(o)
        return J.ordre(str(int(A)))

    memo: dict = {}
    rn = rendement.construire(o, panels=J.panels_reels(), validation_dir=J.VALIDATION_S1, perte_toleree="10 %",
                              verifier=verifier, memo=memo, aujourd_hui=J.AUJOURD_HUI, graines=1)
    assert vu["imbrique"]["erreur"] == "appel récursif de rendement.construire refusé"
    c = rn["perte"]["choix"]
    assert c["perte_toleree"] == 1_000_000 and c["en_actions"] == 3_000_000 and c["verifie_par_ordre"] and c["appels"] == 1
    assert memo["ordre_poche"]["capital"] == 3_000_000 and '"_ordre":' not in json.dumps(rn, default=str)
    assert rn["reserve"]["montant"] == 7_000_000 and rn["reserve"]["valeur_d_un_point"] == 70_000


def test_aucune_ecriture_et_duree():
    avant = _empreinte(_proteges())
    t = time.time()
    rn = rendement.construire(J.ordre("10M"), panels=J.panels_reels(), validation_dir=J.VALIDATION_S1,
                              carnet_cloture=J.carnet(), aujourd_hui=J.AUJOURD_HUI)
    assert time.time() - t < 15
    assert _empreinte(_proteges()) == avant
    assert rn["perte"]["chocs"]["ref_publie_source"] == "mesuré"
    assert abs(rn["perte"]["chocs"]["ref_publie"] - 0.2932) <= 0.0005
    assert len(rn["risque"]["lectures"]) == 6 and rn["risque"]["n_graines"] == 20
    assert rn["liquidites"]["projection"]["dividendes_total"] == 435_988
    assert rn["leviers"]["argent_place"][0]["francs"] == 65_485
    assert abs(rn["leviers"]["argent_place"][1]["francs"] - 127_497) < 1_000
    assert rn["passer_l_ordre"]["consignes"][-1].startswith("Au dernier carnet, 5 lignes")
    assert [a["code"] for a in rn["alertes"]] == ["W1", "W2", "W3"]


def test_grille_enregistree_non_employee_et_liquidites_non_donnees():
    rn = rendement.construire(J.ordre("detenu_624840"), grille_enregistree_non_employee=True, cash_fourni=False,
                              aujourd_hui=J.AUJOURD_HUI)
    assert rn["grille"]["non_employee"] == "Votre grille enregistrée n'est pas employée ici. Option --grille ma_sgi."
    assert any(a.startswith("À VÉRIFIER : Liquidités prises égales") for a in rn["avertissements_a_ajouter"])
    assert rn["risque"]["erreur"].startswith("ValueError")  # sans panels : « non calculé », jamais 0
    assert "risque_concentration" in rn


def test_suivi_fournit_les_feux():
    s = {"semaine": {"date": "2027-03-12", "valeur": 9_400_000, "argent_engage": 10_000_000, "papier": True},
         "alertes_ouvertes": []}
    rn = rendement.construire(J.ordre("10M"), suivi=s, perte_toleree=1_000_000, aujourd_hui="2027-03-13")
    f = rn["suivi"]["feux"]
    assert f["suivi_commence"] and f["perte"]["etat"] == "orange"
    assert "Perte : ORANGE" in rn["plan"]["lignes"][-2]["texte"] or any("Perte : ORANGE" in l["texte"] for l in rn["plan"]["lignes"])


def test_blocs_de_l_ordre_et_du_rapport():
    from brvm_alpha.rendement import rendu as RD

    rn = rendement.construire(J.ordre("10M"), panels=J.panels_reels(), validation_dir=J.VALIDATION_S1,
                              carnet_cloture=J.carnet(), aujourd_hui=J.AUJOURD_HUI, graines=2)
    sec = RD.blocs_section(rn)
    assert sec[0] == ("h2", "Rendement net et pertes") and sec[-1] == ("banner", RG.BANNER)
    titres = [v for k, v in sec if k == "h3"]
    assert [t for t in titres if t in RD.SOUS_PARTIES] == list(RD.SOUS_PARTIES)  # sous-parties dans l'ordre du cahier
    md, html = RD.fragment(sec, "md"), RD.fragment(sec, "html")
    assert md.startswith("## Rendement net et pertes") and "| Poste | Montant |" in md
    assert "<script" not in html and "http" not in html and html.startswith('<section class="brvm-ordre-de-bataille"')
    assert "Frais évités par rapport au tarif supposé ; 0 si votre courtier ne facture pas ce poste." in md
    assert RD.ligne_execution(rn).startswith("Provision à avoir avant l'ordre : 9\u202f866\u202f731 FCFA. Part investie "
                                             "maximale à ce tarif : 97,81 %")
    assert RD.ligne_ne_pas_transmettre() == ("strong", RG.PH_NE_PAS_TRANSMETTRE)
    sb = RD.sous_blocs_rapport(rn)
    assert set(sb) == {"bandeau", "ordre", "revenus", "distribution", "risques", "methode"}
    for nom, blocs in sb.items():
        assert blocs[-1] == ("banner", RG.BANNER), nom
    assert ("h3", "Du brut au net") in sb["revenus"] and ("h3", "Ce que j'accepte de risquer") in sb["risques"]
    erreur = RD.blocs_section({"bilan": {"erreur": "x"}, "perte": {"erreur": "y"}})
    assert any("non calculé" in str(v) for _k, v in erreur)



@pytest.fixture(scope="module")
def rn10():
    return rendement.construire(J.ordre("10M"), panels=J.panels_reels(), validation_dir=J.VALIDATION_S1,
                                carnet_cloture=J.carnet(), aujourd_hui=J.AUJOURD_HUI, graines=2)


_MARQUEURS = ("une année sur dix", "une_sur_dix", "flatteuse", "mediane", "médiane", "frequence_perte",
              "année ordinaire", "annee_ordinaire")


def test_garde_phrases_du_passe_dans_chaque_sous_bloc_et_bloc_json(rn10):
    # Règle 8 du §1, §11 (Honnêteté), §F1-10 : partout où une fréquence, une médiane, « une année sur dix » ou la
    # lecture flatteuse apparaît, PH_PASSE et PH_DESCRIPTIF ; PH_FLATTE dès que la lecture flatteuse y figure.
    from brvm_alpha.rendement import rendu as RD

    vus = 0
    for nom, blocs in RD.sous_blocs_rapport(rn10).items():
        f = RD.fragment(blocs, "md")
        bas = f.lower()
        if any(m in bas for m in _MARQUEURS):
            vus += 1
            assert RG.PH_PASSE in f and RG.PH_DESCRIPTIF in f, nom
            if "flatteuse" in bas or "passé rejoué" in bas:
                assert RG.PH_FLATTE in f, nom
    assert vus >= 3
    for cle, bloc in rn10.items():
        t = json.dumps(bloc, ensure_ascii=False).lower()
        if cle in ("plan", "duree_s", "version", "bandeau") or not any(m in t for m in _MARQUEURS):
            continue
        brut = json.dumps(bloc, ensure_ascii=False)
        assert RG.PH_PASSE in brut and RG.PH_DESCRIPTIF in brut, cle
        if "flatteuse" in t:
            assert RG.PH_FLATTE in brut, cle
    assert RG.PH_FLATTE in rn10["perte"]["phrases"] and rn10["leviers"]["phrases"] == [RG.PH_PASSE, RG.PH_DESCRIPTIF, RG.PH_FLATTE]


def test_carte_du_bandeau_et_carnet_du_paragraphe_passer_l_ordre(rn10):
    from brvm_alpha.rendement import rendu as RD

    band = RD.sous_blocs_rapport(rn10)["bandeau"]
    texte = RD.fragment(band, "md")
    assert "rendre_plan" not in texte and "Carte « Mon plan » : voir" not in texte  # aucun texte de développeur
    assert "MON PLAN" in texte and "environ 290 000" in texte.replace("\u202f", " ") and "flatteuse" not in texte
    assert sum(1 for g, _v in band if g == "table") == 1
    h = RD.html_rapport(band)
    assert h.count("<table") == h.count('<div class="tablewrap"><table') == 1 and "<style" not in h
    vu = []
    h2 = RD.html_rapport(band, table=lambda head, rows: vu.append(len(rows)) or '<div class="tablewrap"><table></table></div>')
    assert vu == [4] and "tablewrap" in h2
    assert rn10["passer_l_ordre"]["carnet"] == {"n1": 5, "n2": 5, "date": "2026-11-20"}


def test_concentration_toutes_les_lignes_de_plus_de_5_pourcent(rn10):
    from brvm_alpha.rendement import rendu as RD

    conc = rn10["risque"]["concentration"]
    assert len(conc["lignes"]) == 6
    md = RD.fragment(RD.blocs_section(rn10), "md")
    lignes = [l for l in md.splitlines() if l.startswith("- Un titre en moins")]
    assert len(lignes) == 6 and any("ECOBANK" in l for l in lignes)  # 5,03 % : coupée à 4 lignes auparavant
    for x in conc["lignes"]:
        assert any(x["nom"] in l for l in lignes)


def test_ordre_de_la_poche_recoit_ses_propres_blocs():
    # --perte-toleree : l'ordre affiché est celui de la poche (3 000 000) ; ses frais, liquidités, provision et alertes
    # sont les siens, la table de choix et la ligne retenue restent celles du capital total (§F4, Intégration).
    o10, o3 = J.ordre("10M"), J.ordre("3000000")
    kw = dict(panels=J.panels_reels(), validation_dir=J.VALIDATION_S1, aujourd_hui=J.AUJOURD_HUI, graines=2,
              carnet_cloture=J.carnet())
    memo: dict = {}
    rn_k = rendement.construire(o10, perte_toleree=1_000_000, verifier=lambda A: J.ordre(str(int(A))), memo=memo,
                                capital=10_000_000, **kw)
    assert memo["ordre_poche"] is not None
    rn_a = rendement.pour_ordre_poche(rn_k, memo["ordre_poche"], perte_toleree=1_000_000, capital=10_000_000, **kw)
    assert rn_a["perte"] == rn_k["perte"] and rn_a["plan"] == rn_k["plan"] and rn_a["reserve"]["montant"] == 7_000_000
    assert rn_a["bilan"]["totaux"]["frais_an1"] == 151_702 and rn_k["bilan"]["totaux"]["frais_an1"] == 284_714
    prov = rn_a["liquidites"]["provision"]["provision_pire_cas"]
    assert prov == o3["couts"]["achats_pire_cas"] and prov != 9_866_731
    from brvm_alpha.rendement import rendu as RD

    assert "9\u202f866\u202f731" not in RD.ligne_execution(rn_a)
    assert RD.ligne_entete_poche(rn_a) == ("Capital total 10\u202f000\u202f000 FCFA ; en actions 3\u202f000\u202f000 FCFA ; "
                                          "en réserve 7\u202f000\u202f000 FCFA.")
    assert RD.ligne_entete_poche(rn_k) is None
    w1 = [a for a in rn_a["alertes"] if a["code"] == "W1"]
    assert not w1 or "124\u202f126" not in w1[0]["texte"]
    assert rn_a["risque_capital_total"] == rn_k["risque"] and rn_a["contexte"]["poche"]
    json.dumps(rn_a, ensure_ascii=False)
    assert rendement.pour_ordre_poche({}, None)["version"] == rendement.VERSION  # ne lève jamais
