"""Raccords du module « Rendement net et pertes » au moteur (cahier ``docs/RENDEMENT_NET.md``, §4.3) : champ du forfait
de compte, clé ``rendement_net`` de l'ordre de bataille, blocs de l'ordre, vérification du §F4 par l'ordre complet,
paramètre ``memoire_ref`` du modèle, refus du forfait par le moteur de simulation.

L'ordre par défaut ne change pas : mêmes titres, quantités, prix limites, frais, dividendes, distribution et stress ;
seuls s'ajoutent les blocs d'information du §3 (lignes 1 à 4, 15 et 16). Panel de synthèse (dates de S0 seulement),
aucune donnée réelle, aucune écriture hors des dossiers temporaires.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import dataclasses
import json
import warnings

import pandas as pd
import pytest

import rendement_jeux as J
from brvm_alpha import rendement, settings
from brvm_alpha.backtest.engine import Backtester
from brvm_alpha.config import CostModel
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.rendement import grille as G
from brvm_alpha.rendement import raccord as RX
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.rendement import risque as RQ
from brvm_alpha.strategy import BrvmAlpha

CLES_45 = ("version", "bandeau", "etude", "grille", "bilan", "leviers", "perte", "reserve", "risque", "liquidites",
           "passer_l_ordre", "alertes", "suivi", "plan")
#: Blocs de l'ordre qui ne doivent pas bouger d'un franc (§9 : comparaison champ par champ).
BLOCS_ORDRE = ("lignes", "tranches", "execution", "couts", "dividendes", "revenus", "distribution", "stress", "statut",
               "variante", "capital", "valeur_portefeuille", "liquidites_initiales", "comparaison", "declencheurs",
               "explications", "faits", "estimations", "hypotheses", "choix", "phrase_etude", "asof", "bandeau")


def _js(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, default=str)


@pytest.fixture(scope="module")
def jeu(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("raccord")
    P = J.panel_synthese()
    with_rn = J.ordre_synthese(P, 5_000_000, tmp)
    sans = J.ordre_synthese(P, 5_000_000, tmp, rendement=False)
    return P, tmp, with_rn, sans


# --------------------------------------------------------------------- R1, R12 : forfait de compte


def test_costmodel_porte_le_forfait_de_compte_nul_par_defaut():
    noms = {f.name for f in dataclasses.fields(CostModel)}
    assert "account_fee_fixed_fcfa" in noms and CostModel().account_fee_fixed_fcfa == 0.0
    for sc in settings.cost_scenarios().values():  # les quatre scénarios du YAML : forfait nul
        assert sc.account_fee_fixed_fcfa == 0.0
    g = G.defaut().avec(forfait_compte=36_000)
    cm, forfait = G.vers_cost_model(g, settings.cost_scenario("central"))
    assert forfait == 36_000 and cm.account_fee_fixed_fcfa == 36_000  # le raccord du §4.3 remplit le champ


def test_le_moteur_de_simulation_refuse_un_forfait_de_compte_non_nul():
    P = J.panel_synthese(n_jours=60, n_titres=6)
    with pytest.raises(NotImplementedError, match="forfait de compte non simulé"):
        Backtester(P, costs=CostModel(account_fee_fixed_fcfa=12_000.0))
    Backtester(P, costs=CostModel())  # forfait nul : construction inchangée


# --------------------------------------------------------------------- R11 : memoire_ref


def test_memoire_ref_amorce_la_poche_de_ref_sans_changer_l_empreinte():
    m0 = BrvmAlpha(variant="REF", capital=10_000_000, notes=None)
    m1 = BrvmAlpha(variant="REF", capital=10_000_000, notes=None, memoire_ref={"annee": 2026, "date": "2026-01-30"})
    assert m0._sleeves["ref"] is None
    assert m1._sleeves["ref"] == {"year": 2026, "t": pd.Timestamp("2026-01-30")}
    assert m0.fingerprint == m1.fingerprint
    assert BrvmAlpha(variant="REF", capital=10_000_000, notes=None, memoire_ref=None)._sleeves["ref"] is None
    m1.reset_state()
    assert m1._sleeves["ref"] is None


# --------------------------------------------------------------------- R2 à R6 : ordre par défaut inchangé


def test_l_ordre_par_defaut_ne_change_pas_et_recoit_la_cle_rendement_net(jeu):
    _P, _tmp, o, o0 = jeu
    d, d0 = o.to_dict(), o0.to_dict()
    for b in BLOCS_ORDRE:
        assert _js(d[b]) == _js(d0[b]), b
    # module éteint : pas de clé rendement_net (contrôle de a58b4c8, constat 2 : la clé vide « {} » était écrite)
    assert "rendement_net" not in d0 and o0.rendement_net == {}
    rn = d["rendement_net"]
    for k in CLES_45:
        assert k in rn, k
    assert rn["bandeau"] == RG.BANNER and rn["etude"]["argent_reel_recommande"] is False
    json.dumps(d, ensure_ascii=False, allow_nan=False)
    # avertissements existants identiques et en tête ; alertes du module en fin de liste, trois au plus (§7.3)
    n0 = len(o0.avertissements)
    assert o.avertissements[:n0] == o0.avertissements
    ajout = o.avertissements[n0:]
    assert len(ajout) <= 3 and all(a.startswith(("FUITE : ", "À VÉRIFIER : ")) for a in ajout)
    assert ajout == [a for a in rn["avertissements_a_ajouter"] if a not in o0.avertissements]


def test_cle_forfait_du_resume_des_couts_et_frais_fixes_de_la_distribution(jeu):
    P, tmp, o, _o0 = jeu
    assert o.couts["forfait_compte_annuel"] == 0
    g = G.depuis_cost_model(settings.cost_scenario("central"), "Essai avec forfait", forfait=60_000)
    og = J.ordre_synthese(P, 5_000_000, tmp, grille=g, rendement=False)
    assert og.couts["forfait_compte_annuel"] == 60_000
    assert "Essai avec forfait" in og.couts["scenario"]
    # même grille sans forfait : mêmes quantités ; la distribution déduit en plus le forfait de l'horizon (12 mois)
    g0 = G.depuis_cost_model(settings.cost_scenario("central"), "Essai sans forfait")
    og0 = J.ordre_synthese(P, 5_000_000, tmp, grille=g0, rendement=False)
    assert list(og.lignes["cibles"]) == list(og0.lignes["cibles"])
    ecart = og.distribution["frais_deduits"] - og0.distribution["frais_deduits"]
    assert ecart == pytest.approx(60_000 / og.valeur_portefeuille, rel=1e-9)


def test_grille_centrale_ou_absente_donne_l_ordre_par_defaut(jeu):
    P, tmp, _o, o0 = jeu
    oc = J.ordre_synthese(P, 5_000_000, tmp, grille="central", rendement=False)
    for b in ("lignes", "couts", "distribution", "stress", "dividendes"):
        assert _js(oc.to_dict()[b]) == _js(o0.to_dict()[b]), b


def test_le_module_ne_fait_jamais_tomber_l_ordre(jeu, monkeypatch):
    P, tmp, _o, o0 = jeu

    def boom(*a, **k):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(rendement, "construire", boom)
    ob = J.ordre_synthese(P, 5_000_000, tmp)
    assert ob.rendement_net == {}
    assert _js(ob.to_dict()["lignes"]) == _js(o0.to_dict()["lignes"])
    assert ob.to_markdown().startswith("# Ordre de bataille")


# --------------------------------------------------------------------- R7, R8 : blocs de l'ordre


def test_blocs_de_l_ordre_a_leur_place(jeu):
    _P, _tmp, o, o0 = jeu
    md = o.to_markdown()
    lignes = md.splitlines()
    assert md.startswith("# Ordre de bataille")
    titres = [x for x in lignes if x.startswith("## ")]
    assert [int(x.split(".")[0][3:]) for x in titres] == list(range(1, len(titres) + 1))  # numérotation refaite
    i_rev = next(i for i, x in enumerate(titres) if "Revenus attendus" in x)
    assert "Rendement net et pertes" in titres[i_rev + 1]
    assert any("Distribution historique" in x for x in titres[i_rev + 2:])
    # « L'essentiel » : après les avertissements, avant « Décision à la clôture »
    i_ess = lignes.index("### L'essentiel")
    i_dec = next(i for i, x in enumerate(lignes) if x.startswith("Décision à la clôture"))
    tete = [i for i, x in enumerate(lignes[:i_dec]) if x.startswith("> ⚠")]  # avertissements en tête
    assert tete and max(tete) < i_ess < i_dec
    bloc = lignes[i_ess + 1:i_dec]
    assert 0 < len([x for x in bloc if x.startswith("- ")]) <= 14
    # libellé réécrit (§F6), clé JSON inchangée
    assert RQ.LIBELLE_P_BATTRE_TR in md and "P(battre le TR)" not in md
    assert "p_battre_tr" in o.to_dict()["distribution"]
    assert "### Lectures du risque : plusieurs lectures d'un seul passé" in lignes
    # ligne ajoutée à « Exécution » : provision à avoir
    texte_prov = o.rendement_net["liquidites"]["provision"]["texte"]
    i_ex = next(i for i, x in enumerate(lignes) if x.startswith("## ") and "Exécution" in x)
    i_ex2 = next(i for i, x in enumerate(lignes) if i > i_ex and x.startswith("## "))
    assert any(texte_prov in x for x in lignes[i_ex:i_ex2])
    # rien de tout cela sans la clé (rendement=False), hormis le libellé réécrit
    md0 = o0.to_markdown()
    assert "L'essentiel" not in md0 and "Rendement net et pertes" not in md0 and RQ.LIBELLE_P_BATTRE_TR in md0
    html = o.to_html_fragment()
    assert html.startswith('<section class="brvm-ordre-de-bataille"') and "essentiel</h3>" in html


def test_ligne_ne_pas_transmettre_au_dessus_de_la_table_si_rejete(jeu):
    _P, _tmp, o, _o0 = jeu
    o2 = dataclasses.replace(o, choix={**o.choix, "statut": "REJETÉ"})
    lignes = o2.to_markdown().splitlines()
    i = next(k for k, x in enumerate(lignes) if x.startswith("## ") and "Ordres (au titre et au franc près)" in x)
    suite = [x for x in lignes[i + 1:] if x.strip()]
    assert suite[0] == f"**{RG.PH_NE_PAS_TRANSMETTRE}**"
    assert suite[1].startswith("| Titre | Sens |")  # le titre et la table ne changent pas
    assert RG.PH_NE_PAS_TRANSMETTRE not in o.to_markdown().split("Rendement net et pertes")[0]  # statut non rejeté


# --------------------------------------------------------------------- R6 : vérification du §F4 par l'ordre complet


def test_ordre_de_la_poche_dans_le_meme_mode_que_l_ordre_du_capital(jeu, monkeypatch):
    P, tmp, _o, _o0 = jeu
    appels: list[bool] = []
    vrai = R.recommend

    def compte(*a, **k):
        appels.append(bool(k.get("rendement", True)))
        return vrai(*a, **k)

    monkeypatch.setattr(R, "recommend", compte)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ok = vrai(P["close"].index[-1], 5_000_000, panels=P, validation_dir=tmp / "absent",
                  registry_path=J.registre_vide(tmp / "reg_poche.parquet"), notes_store=False, n_boot=300, seed=0,
                  index_evaluation=False, comparison=False, tolerance=0.03, perte_toleree=1_000_000)
    rn = ok.rendement_net
    ch = rn["perte"]["choix"]
    A = float(ch["en_actions"])
    assert 0 < A < 5_000_000 and ch["verifie_par_ordre"] is True
    assert 1 <= ch["appels"] <= 10 and len(appels) == ch["appels"] and not any(appels)  # jamais de rendement imbriqué
    assert ch["P_verifiee"] <= 1_000_000
    # l'ordre rendu est celui de la poche, dans le même mode que l'ordre de K
    assert ok.capital == A and ok.execution["tolerance"] == 0.03 and ok.variante == "REF"
    assert rn["contexte"]["poche"] is True and rn["contexte"]["capital"] == 5_000_000
    assert rn["contexte"]["reserve"] == 5_000_000 - A
    entete = rendement.rendu.ligne_entete_poche(rn)
    assert entete == (f"Capital total {RG.fcfa(5_000_000)} ; en actions {RG.fcfa(A)} ; en réserve "
                      f"{RG.fcfa(5_000_000 - A)}.")
    md = ok.to_markdown().splitlines()
    assert md[0].startswith("# Ordre de bataille") and f"**{entete}**" in md[:8]
    # sans perte acceptée : l'ordre de K, sans aucune vérification
    appels.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ok2 = vrai(P["close"].index[-1], 5_000_000, panels=P, validation_dir=tmp / "absent",
                   registry_path=tmp / "reg_poche.parquet", notes_store=False, n_boot=300, seed=0,
                   index_evaluation=False, comparison=False, tolerance=0.03)
    assert appels == [] and ok2.capital == 5_000_000 and ok2.rendement_net["perte"]["choix"] is None


# --------------------------------------------------------------------- R9 : état du journal REF-S2


def test_etat_du_journal_ref_s2_dans_les_declencheurs(tmp_path, monkeypatch):
    assert RX.etat_journal_ref_s2(tmp_path) is None  # aucun journal : la mention d'origine reste
    from brvm_alpha.suivi import bulletin

    monkeypatch.setattr(bulletin, "semaines_du_journal",
                        lambda nom, dossier=None: [{"semaine": 3, "vendredi": "2026-12-18", "ecart_au_marche": -0.012}]
                        if nom == "REF-S2" else [])
    txt = RX.etat_journal_ref_s2()
    assert "REF-S2" in txt and "semaine 3" in txt and "18/12/2026" in txt and "−1,2 %" in txt
    assert "aucun portefeuille réel" in txt and "ce n'est pas une performance" in txt
    monkeypatch.setattr(bulletin, "semaines_du_journal", lambda nom, dossier=None: (_ for _ in ()).throw(OSError("x")))
    assert RX.etat_journal_ref_s2() is None  # journal illisible : jamais d'exception
