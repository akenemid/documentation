"""F1 — Écran « Mon plan » (cahier ``docs/RENDEMENT_NET.md``, §F1) : forme écran (texte, HTML, montants arrondis),
forme détail (Markdown, au franc), bloc « L'essentiel » de l'ordre. Recette sur l'ordre figé du 20/11/2026."""

from __future__ import annotations

import html
import json
import re

import pytest

import rendement_jeux as J
from brvm_alpha import rendement
from brvm_alpha.rendement import plan as PL
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.rendement import rendu as RD


def _construire(cap="10M", **kw):
    args = dict(panels=J.panels_reels(), validation_dir=J.VALIDATION_S1, aujourd_hui=J.AUJOURD_HUI,
                carnet_cloture=J.carnet())
    args.update(kw)
    return rendement.construire(J.ordre(cap), **args)


@pytest.fixture(scope="module")
def rn10():
    return _construire()


def _plat(t: str) -> str:
    t = html.unescape(t).replace("\u00a0", " ").replace("\u202f", " ")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def _formes(rn):
    p = rn["plan"]
    return {"texte": PL.rendre_plan(p, "texte"), "md": PL.rendre_plan(p, "md"), "html": PL.rendre_plan(p, "html")}


def test_phrases_dans_les_formes_et_ordre_des_blocs(rn10):
    seance = rn10["etude"]["phrases"][1]
    for nom, t in _formes(rn10).items():
        p = _plat(t)
        n = lambda s: _plat(s)  # noqa: E731
        for ph in (RG.BANNER, RG.PH_ETUDE, seance, RG.PH_PASSE, RG.PH_DESCRIPTIF):
            assert n(ph) in p, (nom, ph)
        # PH_PASSE et PH_DESCRIPTIF après la table de la décision 2, avant la décision 3.
        assert p.index("CE QUE J'ACCEPTE DE RISQUER") < p.index(n(RG.PH_PASSE)) < p.index("OÙ DORT LE RESTE")
        assert p.index(n(RG.PH_DESCRIPTIF)) < p.index("OÙ DORT LE RESTE")
        assert n(RG.PH_INTERETS) in p and n(RG.PH_COURS) in p
    ess = _plat(RD.fragment(RD.bloc_essentiel(rn10), "md"))
    for ph in (seance, RG.PH_PASSE, RG.PH_DESCRIPTIF, RG.PH_INTERETS):
        assert _plat(ph) in ess
    sec = _plat(RD.fragment(RD.blocs_section(rn10), "md"))
    assert _plat(RG.BANNER) in sec and _plat(RG.PH_ETUDE) in sec


@pytest.mark.parametrize("cap,X", [("10M", None), ("1M", None), ("50M", None), ("10M", 1_000_000), ("detenu_624840", None),
                                   ("partiel", None)])
def test_forme_ecran_lexique_lignes_colonnes(cap, X):
    ver = (lambda A: J.ordre(str(int(A)))) if X else None
    rn = _construire(cap, perte_toleree=X, verifier=ver)
    t = PL.rendre_plan(rn["plan"], "texte")
    lignes = t.rstrip("\n").split("\n")
    assert len(lignes) <= 45 and max(len(x) for x in lignes) <= 100
    assert RG.mots_interdits(t) == []
    assert RG.mots_interdits(_plat(PL.rendre_plan(rn["plan"], "html"))) == []
    assert "acheter" not in rn["plan"]["une_chose"]
    for m in re.finditer(r"[^.]*\bachetez\b[^.]*", t, flags=re.I):
        assert re.search(r"\bsi\b|n'|ne |jamais|aucun", m.group(0), flags=re.I), m.group(0)
    assert "aucun achat" in _plat(t)
    for l in rn["plan"]["lignes"]:
        if l.get("montant") is not None:
            assert l["statut"] in ("compté", "estimé", "supposé"), l
    if cap == "1M":
        # Règle 10 : montants supposés arrondis, précédés de « environ », avec leur statut ; au franc dans le détail.
        assert _plat(t).startswith("À ce tarif, 20 lignes coûtent plus qu'elles ne rapportent : environ 110 000 FCFA de "
                                   "frais par an pour environ 38 000 FCFA de dividendes attendus [supposé].")
        md = _plat(PL.rendre_plan(rn["plan"], "md"))
        assert ("102 166 FCFA de frais par an pour 38 458 FCFA de dividendes attendus [supposé], soit 63 708 FCFA de "
                "moins par an") in md


def test_memes_montants_json_md_ecran(rn10):
    p = rn10["plan"]
    md = _plat(PL.rendre_plan(p, "md"))
    txt = _plat(PL.rendre_plan(p, "texte"))
    rec = [l for l in p["lignes"] if l["bloc"] == "recevoir" and l["type"] == "ligne_montant"]
    assert [l["montant"] for l in rec] == [435_988, -160_588, -124_126, 151_274, 311_862]
    for l in rec:
        assert _plat(RG.fcfa(l["montant"], signe=True)) in md
        assert _plat(l["montant_ecran"]) in txt and l["montant_ecran"] == RG.arrondi_ecran(l["montant"])


def test_recette_json_et_ecran(rn10):
    t = rn10["bilan"]["totaux"]
    assert (t["frais_an1"], t["annuels"], t["reste_an1"], t["reste_suivant"]) == (284_714, 124_126, 151_274, 311_862)
    assert next(x["reste_an1"] for x in rn10["bilan"]["dividendes_en_baisse"] if x["chute"] == 0.20) == 64_076
    assert round(t["part_supposee_frais"], 3) == 0.898
    assert [r["en_actions"] for r in rn10["perte"]["table"]] == [1_400_000, 3_000_000, 6_300_000, 10_000_000]
    ecran = _plat(PL.rendre_plan(rn10["plan"], "texte"))
    for s in ("environ 290 000", "−830 000 à −980 000", "+110 000", "90 %", "−420 000 à −480 000", "+660 000",
              "pire moment de 2018 : −1 040 000 ; si 2017-2020 revenait : −1 410 000 (les deux dépassent)",
              "Dividendes moins frais environ +150 000", "+64 000 si dividendes −20 %", "remise à niveau −35 000 à −130 000",
              "environ 73 000 FCFA de moins la 1re année, puis 96 000 de moins par an",
              "un point d'intérêt vaut 100 000 FCFA par an", "SI VOUS NE FAITES QU'UNE CHOSE CETTE SEMAINE : envoyez les 8 "
              "questions à votre courtier.", "TROIS FEUX CHAQUE SEMAINE Perte : — Fuites : — Données : — (le suivi n'a pas commencé)"):
        assert s in ecran, s


def test_table_de_choix_sans_plan_enregistre(rn10):
    p = rn10["plan"]
    rows = [l for l in p["lignes"] if l["type"] == "ligne_table"]
    sous = [l for l in p["lignes"] if l["type"] == "sous_ligne"]
    assert len(rows) == 4 and len(sous) == 4 and rows[-1]["cellules"][0] == "tout"
    for l, r in zip(sous, rn10["perte"]["table"]):
        assert "pire moment de 2018 : −" in l["texte"] and "si 2017-2020 revenait : −" in l["texte"]
        X = r["perte_toleree"]
        dep = X is not None and (r["pire_moment_2018"] > X or r["baisse_2017_2020"] > X)
        assert ("dépasse" in l["texte"]) == dep
    assert "« tout » : tout en actions." in _plat(PL.rendre_plan(p, "texte"))
    assert "[ tarif supposé, non vérifié ]" in _plat(PL.rendre_plan(p, "texte"))
    assert "[ taux inconnu : compté à 0 % ]" in _plat(PL.rendre_plan(p, "texte"))


def test_lecture_flatteuse_seulement_au_detail(rn10):
    f = _formes(rn10)
    assert "flatteuse" not in f["texte"] and "flatteuse" not in f["html"]
    md = f["md"]
    assert "flatteuse" in md
    assert md.index(RG.PH_FLATTE) > md.index("Année ordinaire (flatteuse)")


@pytest.mark.parametrize("jour,mot", [("2026-11-24", "à partir du 01/12/2026"), ("2026-12-02", "depuis le 01/12/2026"),
                                      ("2027-06-02", "écrite et signée")])
def test_phrase_seance_rendue_a_la_date(jour, mot):
    rn = _construire(aujourd_hui=jour, graines=1)
    t = _plat(PL.rendre_plan(rn["plan"], "texte"))
    assert mot in t and "lundi" not in t.lower().replace("lundi 3", "") and "au plus tôt" not in t


def test_choix_du_montant_accepte_et_une_chose():
    rn = _construire(perte_toleree=1_000_000, verifier=lambda A: J.ordre(str(int(A))), graines=1,
                     plan_enregistre={"perte_toleree": 1_000_000, "questions_envoyees": True})
    t = _plat(PL.rendre_plan(rn["plan"], "texte"))
    for s in ("Vous acceptez de risquer 1 000 000 FCFA sur 12 mois. Ce n'est pas une limite.",
              "En actions : 3 000 000 FCFA. En réserve : 7 000 000 FCFA [estimé].",
              "Une année comme 2018 : environ −830 000 à −980 000 FCFA, frais compris [estimé]. Au pire moment de l'année : "
              "environ −1 040 000 FCFA. Cela dépasse ce que vous acceptez.",
              "Si la baisse de 2017-2020 revenait : environ −1 410 000 FCFA, sur plusieurs années [estimé].",
              "environ +110 000 FCFA au lieu de +660 000 (environ 550 000 FCFA de moins) [estimé]",
              "chaque point d'intérêt vaut 70 000 FCFA par an [estimé]", _plat(RG.PH_RISQUE)):
        assert s in t, s
    assert "flatteuse" not in t and "915 950" not in t
    assert rn["plan"]["une_chose_code"] == "taux"
    md = _plat(PL.rendre_plan(rn["plan"], "md"))
    assert "les frais dépassent les dividendes attendus de 25 707 FCFA [supposé]" in md
    # Détail : le prix de la prudence en lecture flatteuse (915 950 FCFA), suivi de PH_FLATTE (§F4).
    i = md.index("Lecture flatteuse (passé rejoué) : +263 350 FCFA au lieu de +1 179 300 FCFA (915 950 FCFA de moins).")
    assert md.index(_plat(RG.PH_FLATTE), i) > i
    # Statut des montants de la ligne retenue (§14 : « Estimation (règle du §F4) »).
    lig = {l["texte"].split(" :")[0].strip(): l for l in rn["plan"]["lignes"] if l["bloc"] == "risque" and l.get("montant") is not None}
    assert lig["En actions"]["statut"] == "estimé"


def test_statut_ecrit_sur_chaque_ligne_de_montant_du_bloc_2():
    rn = _construire(perte_toleree=1_000_000, verifier=lambda A: J.ordre(str(int(A))), graines=1)
    vus = 0
    for l in rn["plan"]["lignes"]:
        if l["bloc"] != "risque" or l.get("montant") is None or l["texte"].strip().startswith("Vous acceptez de risquer"):
            continue  # la ligne « Vous acceptez de risquer X » reprend la saisie de l'utilisateur
        vus += 1
        assert re.search(r"\[(compté|estimé|supposé)\]", l["texte"]), l["texte"]
        assert re.search(r"\[(compté|estimé|supposé)\]", l["texte_detail"]), l["texte_detail"]
    assert vus >= 4


def test_verification_par_l_ordre_en_echec_rien_n_est_chiffre():
    # verifier « trop cher » : chaque ordre complet dépasse ce que l'utilisateur accepte (§F4, étape 6).
    rn = _construire(perte_toleree=900_000, verifier=lambda A: J.ordre("3000000"), graines=1)
    ch = rn["perte"]["choix"]
    assert ch["en_actions"] == 0 and ch["reserve"] == 10_000_000 and ch["appels"] == 10 and not ch["verifie_par_ordre"]
    assert ch["annee_2018"] == [None, None] and ch["pire_moment_2018"] is None and ch["annee_ordinaire"]["prudente"] is None
    assert ch["message"] == "vérification arrêtée après 10 ordres : montant en actions à confirmer"
    assert rn["reserve"]["montant"] == 10_000_000
    t = _plat(PL.rendre_plan(rn["plan"], "texte"))
    bloc2 = t[t.index("2. CE QUE J'ACCEPTE"):t.index("3. OÙ DORT LE RESTE")]
    assert "En actions : 2" not in bloc2 and "En actions : 3" not in bloc2
    assert not re.search(r"−[\d ]+ à −[\d ]+", bloc2), bloc2  # aucune fourchette « année comme 2018 »
    assert "montant en actions à confirmer" in bloc2 and "Montant en actions : non calculé" in bloc2
    sec = _plat(RD.fragment(RD.blocs_section(rn), "md"))
    assert "montant en actions à confirmer" in sec


def test_reserve_nulle_bloc_masque():
    rn = _construire(perte_toleree=5_000_000, verifier=lambda A: J.ordre("10M"), graines=1)
    assert rn["perte"]["choix"]["en_actions"] == 10_000_000 and rn["reserve"]["masque"]
    t = PL.rendre_plan(rn["plan"], "texte")
    assert "OÙ DORT LE RESTE" not in t and "0 FCFA : chaque point" not in t


def test_forme_fragment_pour_la_carte_du_rapport(rn10):
    f = PL.rendre_plan(rn10["plan"], "fragment")
    assert "<style" not in f and not re.search(r"#[0-9a-fA-F]{3,6}\b", f) and "background" not in f
    assert f.count("<table") == f.count('<div class="tablewrap"><table') == 1
    p = _plat(f)
    for ph in (RG.BANNER, RG.PH_ETUDE, RG.PH_PASSE, RG.PH_DESCRIPTIF):
        assert _plat(ph) in p, ph
    assert "flatteuse" not in f and "environ 290 000" in p
    blocs = PL.vers_blocs(rn10["plan"])
    assert ("banner", RG.BANNER) in blocs and sum(1 for g, _v in blocs if g == "table") == 1


def test_bloc_essentiel_quatorze_lignes_au_plus(rn10):
    b = RD.bloc_essentiel(rn10)
    assert b[0] == ("h3", "L'essentiel") and len(b[1][1]) <= 13
    txt = RD.fragment(b, "md")
    assert len(txt.strip().split("\n")) <= 14
    assert "284\u202f714 FCFA" in txt and "89,8 %" in txt and "(dépasse)" in txt


def test_bloc_en_echec_ecrit_non_calcule(monkeypatch):
    from brvm_alpha.rendement import risque

    def casse(*a, **k):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(risque, "lectures", casse)
    rn = _construire(graines=1)
    assert rn["risque"]["erreur"].startswith("RuntimeError")
    assert not rn["plan"].get("erreur") and rn["perte"]["table"]
    monkeypatch.setattr(PL, "construire_plan", casse)
    rn2 = _construire(graines=1)
    assert rn2["plan"]["erreur"].startswith("RuntimeError") and not rn2["bilan"].get("erreur")
    json.dumps(rn2, ensure_ascii=False)


def test_html_sans_ressource_externe(rn10):
    h = PL.rendre_plan(rn10["plan"], "html")
    assert "http" not in h and "<script" not in h and "<link" not in h and "src=" not in h
    assert h.count("<table>") == 1 and "prefers-color-scheme: dark" in h
    with pytest.raises(ValueError):
        PL.rendre_plan(rn10["plan"], "pdf")
