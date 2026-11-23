"""Commandes « plan » et « suivi » et options nouvelles de ``recommend`` et ``report`` (cahier
``docs/RENDEMENT_NET.md``, §6 ; contrat de la ligne de commande, ``docs/DEPLOIEMENT.md`` § A.7 et A.8).

- sans option nouvelle, ``recommend`` et ``report`` reçoivent exactement les mêmes arguments qu'avant ;
- codes de retour de la table (0, 1, 2, 4, 5, 6, 7, 8, 130 ; jamais 3), un seul objet JSON avec ``--format json``,
  erreur comprise, en mode normal et en mode embarqué ;
- écritures atomiques dans les seuls dossiers de données (``profil/``, ``suivi/``) ; aucune écriture dans le code ;
- la déclaration du suivi n'est signée, et le registre complété, que sur une **copie** de dépôt (dossier temporaire) :
  le vrai ``reports/`` du dépôt n'est jamais touché.

Doublures pour les calculs lourds (``recommend``), extraits figés du 20/11/2026 pour le rendement net, panels
fabriqués pour le suivi ; dossiers temporaires seulement ; aucune requête réseau ; aucune date de S1.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import rendement_jeux as RJ
import suivi_jeux as SJ
from brvm_alpha import cli, cli_rendement, erreurs, paths, rendement
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.suivi import carnet as CN
from brvm_alpha.suivi import declaration as DE

ROOT = Path(__file__).resolve().parents[1]
CODES_PERMIS = {0, 1, 2, 4, 5, 6, 7, 8, 130}
JOURS = pd.bdate_range("2026-12-01", periods=20)


def run_cli(capsys, *argv: str) -> tuple[int, str, str]:
    try:
        code = cli.main(list(argv))
    except SystemExit as exc:
        code = exc.code
    cap = capsys.readouterr()
    assert code in CODES_PERMIS and code != 3, (argv, code)
    return code, cap.out, cap.err


def one_json(out: str) -> dict:
    d = json.loads(out)  # exactement un objet : json.loads refuse tout texte en plus
    assert isinstance(d, dict) and d["bandeau"] == cli.BANNER
    return d


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


@pytest.fixture(autouse=True)
def gardes_du_depot():
    """Le vrai registre des essais, S1 publié et ``reports/suivi_S2`` du dépôt ne changent jamais."""
    reg, decl = ROOT / "reports" / "trials.parquet", ROOT / "reports" / "suivi_S2"
    avant = (_sha(reg), decl.exists(), (ROOT / "data" / "profil").exists())
    yield
    assert (_sha(reg), decl.exists(), (ROOT / "data" / "profil").exists()) == avant


@pytest.fixture()
def donnees(tmp_path, monkeypatch):
    """Dossiers de données et de rapports temporaires (jamais ceux de l'installation)."""
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    data.mkdir()
    reports.mkdir()
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "REPORTS_DIR", reports)
    monkeypatch.setattr(paths, "NOTES_DIR", data / "notes")
    return data, reports


@pytest.fixture(scope="module")
def rn10():
    return rendement.construire(RJ.ordre("10M"), panels=RJ.panels_reels(), validation_dir=RJ.VALIDATION_S1,
                                aujourd_hui=RJ.AUJOURD_HUI, carnet_cloture=RJ.carnet())


class _Ordre:
    asof = pd.Timestamp("2026-11-20")

    def __init__(self, rn=None, capital=10_000_000):
        self.rendement_net = rn if rn is not None else {}
        self.avertissements: list = []
        self.capital = capital

    def to_dict(self):
        d = dict(RJ.ordre("10M"))
        d["rendement_net"] = self.rendement_net
        d["avertissements"] = list(self.avertissements)
        return d

    def to_markdown(self):
        return "# Ordre de bataille\n> " + cli.BANNER

    def to_html_fragment(self):
        return "<section></section>"


@pytest.fixture()
def fausse_reco(monkeypatch, rn10):
    """``recommend`` remplacé : note ses arguments et rend un ordre figé (rendement net du 20/11/2026)."""
    from brvm_alpha.portfolio import recommend as rec

    appels: list[dict] = []

    def fake(asof, capital, **kw):
        appels.append({"asof": asof, "capital": capital, **kw})
        return _Ordre(rn10 if kw.get("rendement", True) else {}, capital)

    monkeypatch.setattr(rec, "recommend", fake)
    monkeypatch.setattr(cli, "history_state", lambda *a, **k: {"complet": True, "raison": None, "jours_manquants": 0,
                                                                "avertissement": None})
    monkeypatch.setattr(cli, "last_session", lambda *a, **k: pd.Timestamp("2026-11-20"))
    monkeypatch.setattr(cli, "now_utc", lambda: pd.Timestamp("2026-11-23 08:00", tz="UTC"))
    return appels


# ---------------------------------------------------------------------------
# Aide, analyseur
# ---------------------------------------------------------------------------

AIDES = [["plan"], ["plan", "grille"], ["plan", "questions"], ["suivi"], ["suivi", "demarrer"], ["suivi", "maj"],
         ["suivi", "bulletin"], ["suivi", "saisir"], ["suivi", "revue"], ["suivi", "declarer"], ["suivi", "verifier"],
         ["suivi", "exporter"], ["recommend"], ["report"]]


@pytest.mark.parametrize("argv", AIDES, ids=["-".join(a) for a in AIDES])
def test_every_new_help_page_ends_with_the_banner(capsys, argv):
    code, out, _ = run_cli(capsys, *argv, "--help")
    assert code == 0 and out.rstrip().endswith(cli.BANNER)


def test_new_commands_are_declared_before_serve_and_in_the_command_table():
    assert "plan" in cli.COMMANDS and "suivi" in cli.COMMANDS
    sub = next(a for a in cli.build_parser()._actions if a.__class__.__name__ == "_SubParsersAction")
    noms = list(sub.choices)
    assert noms.index("plan") < noms.index("serve") and noms.index("suivi") < noms.index("serve")


def test_rate_amount_and_loss_parsers():
    assert cli_rendement.parse_taux("0,5") == pytest.approx(0.005) and cli_rendement.parse_taux("3.5 %") == 0.035
    assert cli_rendement.parse_montant("0") == 0.0 and cli_rendement.parse_montant("2,5k") == 2500.0
    assert cli_rendement.parse_perte("10 %") == "10%" and cli_rendement.parse_perte("1 000 000") == 1_000_000.0
    for bad in ("-1", "abc", "120"):
        with pytest.raises(ValueError):
            cli_rendement.parse_taux(bad)
    for bad in ("0,5", "0 %", "beaucoup"):
        with pytest.raises(ValueError):
            cli_rendement.parse_perte(bad)


# ---------------------------------------------------------------------------
# recommend et report : options éteintes par défaut
# ---------------------------------------------------------------------------

#: Arguments de ``recommend`` passés par ``_cmd_recommend`` avant le module (commit cc8d101).
ARGS_AVANT = {"asof", "capital", "holdings", "cash", "variant", "costs", "n_boot", "seed", "notes_store", "panel_dir",
              "index_evaluation", "notes_known_at", "today"}


def test_without_new_option_recommend_gets_exactly_the_same_arguments(donnees, fausse_reco, capsys):
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--sans-notes", "--format", "json")
    assert code == 0 and set(fausse_reco[-1]) == ARGS_AVANT
    assert "rendement_net" in one_json(out)
    assert cli_rendement.options_recommend(cli.build_parser().parse_args(["recommend", "--capital", "1M"])) == {}
    assert cli_rendement.options_recommend(cli.build_parser().parse_args(["report", "--capital", "1M"]), "report") == {}


def test_new_recommend_options_reach_recommend(donnees, fausse_reco, capsys):
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--sans-notes", "--grille", "central",
                           "--perte-toleree", "10 %", "--taux-reserve", "3,5", "--arrondi", "restes", "--forcer",
                           "--cash", "2M", "--apport", "1M", "--completer", "--reinvestir", "--continuite",
                           "--format", "json")
    assert code == 0, out
    kw = fausse_reco[-1]
    assert kw["grille"] == "central" and kw["perte_toleree"] == "10%" and kw["taux_reserve"] == pytest.approx(0.035)
    assert kw["arrondi"] == "restes" and kw["forcer"] is True and kw["apport"] == 1_000_000.0
    assert kw["completer"] is kw["reinvestir"] is kw["continuite"] is True
    run_cli(capsys, "recommend", "--capital", "10M", "--sans-notes", "--sans-rendement")
    assert fausse_reco[-1]["rendement"] is False
    run_cli(capsys, "recommend", "--capital", "10M", "--sans-notes", "--perte-toleree", "1 000 000")
    assert fausse_reco[-1]["perte_toleree"] == 1_000_000.0


@pytest.mark.parametrize("argv, code, mot", [
    (["--sans-rendement", "--perte-toleree", "1M"], 2, "retirer --sans-rendement"),
    (["--forcer"], 2, "--arrondi restes"),
    (["--grille", "ma_sgi"], 2, "aucune grille enregistrée"),
    (["--grille", "grille_absente.yaml"], 1, "introuvable"),
    (["--perte-toleree", "0,5"], 2, "erreur"),
    (["--taux-reserve", "200"], 2, "erreur"),
    (["--suivi", "REF-S2"], 2, "tenu par le moteur"),
    (["--suivi", "MOI"], 1, "suivi demarrer"),
    (["--apport", "1M"], 2, "liquidités réelles nécessaires"),
    (["--apport", "1M", "--cash", "500k"], 2, "--cash doit comprendre"),
])
def test_refused_option_combinations_give_their_code_and_one_json(donnees, fausse_reco, capsys, argv, code, mot):
    n = len(fausse_reco)
    got, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--sans-notes", *argv, "--format", "json")
    d = one_json(out)
    assert got == code and d["ok"] is False and d["code"] == code and mot in d["message"]
    assert len(fausse_reco) == n  # aucun calcul lancé


def test_report_passes_the_options_through_recommend_kwargs(donnees, fausse_reco, capsys, monkeypatch, tmp_path):
    import brvm_alpha.report as report

    vus: list[dict] = []

    def fake_report(asof, capital, out, **k):
        vus.append(k)
        Path(out).write_text("<html></html>", encoding="utf-8")
        return Path(out)

    monkeypatch.setattr(report, "build_report", fake_report)
    code, out, _ = run_cli(capsys, "report", "--capital", "10M", "--sortie", str(tmp_path / "r.html"), "--format", "json")
    assert code == 0 and "recommend_kwargs" not in vus[-1]  # sans option : appel inchangé
    code, out, _ = run_cli(capsys, "report", "--capital", "10M", "--sortie", str(tmp_path / "r.html"), "--grille",
                           "central", "--perte-toleree", "1M", "--taux-reserve", "3", "--format", "json")
    assert code == 0 and vus[-1]["recommend_kwargs"] == {"grille": "central", "perte_toleree": 1_000_000.0,
                                                          "taux_reserve": pytest.approx(0.03)}
    code, out, _ = run_cli(capsys, "report", "--capital", "10M", "--sortie", str(tmp_path / "r.html"),
                           "--sans-rendement", "--format", "json")
    assert code == 0 and vus[-1]["recommend_kwargs"] == {"rendement": False}


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def test_plan_screen_text_json_cache_and_saved_plan(donnees, fausse_reco, capsys):
    data, _ = donnees
    code, out, _ = run_cli(capsys, "plan", "--sans-notes")
    plat = out.replace("\u00a0", " ").replace("\u202f", " ")
    assert code == 0 and RG.BANNER in out and RG.PH_ETUDE.split(" :")[0] in out
    assert "environ 290 000" in plat and "90 %" in plat and len(out.splitlines()) <= 45
    kw = fausse_reco[-1]
    assert kw["capital"] == 10_000_000 and kw["grille"] == "central" and kw["index_evaluation"] is False
    assert kw["plan_enregistre"] is None and "perte_toleree" not in kw
    cache = json.loads((data / "profil" / "plan_cache.json").read_text(encoding="utf-8"))
    assert cache["bandeau"] == cli.BANNER and cache["capital"] == 10_000_000 and cache["plan"]["lignes"]
    assert cache["ordre"]["lignes"] and "rendement_net" not in cache["ordre"] and len(cache["empreinte_ordre"]) == 64
    assert not list((data / "profil").glob("*.part"))  # écriture atomique : aucun fichier temporaire laissé
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--capital", "5M", "--perte-toleree", "1M",
                           "--taux-reserve", "3", "--besoin-dans", "24", "--enregistrer", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["ok"] is True and d["capital"] == 5_000_000 and d["rendement_net"]["plan"]
    assert d["duree"]["statut"] == "non calculé" and Path(d["plan_cache"]).is_file()
    pe = json.loads((data / "profil" / "plan.json").read_text(encoding="utf-8"))
    assert pe["capital"] == 5_000_000 and pe["perte_toleree"] == 1_000_000 and pe["taux_reserve"] == pytest.approx(0.03)
    assert pe["statut_taux"] == "supposé" and pe["besoin_dans_mois"] == 24 and pe["bandeau"] == cli.BANNER
    # Sans --capital : celui du plan enregistré ; le plan est passé au calcul.
    run_cli(capsys, "plan", "--sans-notes")
    assert fausse_reco[-1]["capital"] == 5_000_000 and fausse_reco[-1]["plan_enregistre"]["perte_toleree"] == 1_000_000


def test_plan_md_output_to_a_file_and_json_with_sortie(donnees, fausse_reco, capsys, tmp_path):
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--format", "md", "--sortie", str(tmp_path / "e.md"))
    assert code == 0 and "Écran « Mon plan » écrit" in out and cli.BANNER in out
    assert RG.BANNER in (tmp_path / "e.md").read_text(encoding="utf-8")
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--format", "json", "--sortie", str(tmp_path / "e.json"))
    d = one_json(out)
    assert code == 0 and d["chemin"] == str(tmp_path / "e.json") and d["octets"] > 1000
    assert json.loads((tmp_path / "e.json").read_text(encoding="utf-8"))["rendement_net"]["plan"]


@pytest.mark.parametrize("argv, code, mot", [
    (["--date", "2021-06-30"], 2, "échantillon vierge S1"),
    (["--tranches", "3"], 2, "F15"),
    (["--grille", "ma_sgi"], 2, "aucune grille enregistrée"),
])
def test_plan_refusals(donnees, fausse_reco, capsys, argv, code, mot):
    got, out, _ = run_cli(capsys, "plan", "--sans-notes", *argv, "--format", "json")
    d = one_json(out)
    assert got == code and d["ok"] is False and mot in d["message"]
    assert not (donnees[0] / "profil" / "plan_cache.json").exists()


def test_plan_failures_give_one_json_object(donnees, fausse_reco, capsys, monkeypatch):
    from brvm_alpha.portfolio import recommend as rec

    monkeypatch.setattr(rec, "recommend", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("equities.parquet")))
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--format", "json")
    assert code == 1 and one_json(out)["erreur"] == "donnees_absentes"
    monkeypatch.setattr(rec, "recommend", lambda *a, **k: _Ordre({"erreur": "panne"}))
    code, out, err = run_cli(capsys, "plan", "--sans-notes", "--format", "json")
    assert code == 7 and "non calculé" in one_json(out)["message"]
    (donnees[0] / "profil").mkdir()
    (donnees[0] / "profil" / "plan.json").write_text("{pas du json", encoding="utf-8")
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--format", "json")
    assert code == 2 and "plan enregistré illisible" in one_json(out)["message"]


def test_plan_questions_and_grid(donnees, fausse_reco, capsys):
    data, _ = donnees
    code, out, _ = run_cli(capsys, "plan", "questions", "--format", "json")
    assert code == 0 and len(one_json(out)["questions"]) == 8
    code, out, _ = run_cli(capsys, "plan", "questions")
    assert code == 0 and out.rstrip().endswith(cli.BANNER) and "8. " in out
    code, out, _ = run_cli(capsys, "plan", "grille")
    assert code == 0 and "supposé" in out and out.rstrip().endswith(cli.BANNER)
    assert not (data / "profil" / "grille_sgi.yaml").exists()  # afficher n'écrit rien
    for argv, mot in ((["--courtage", "4"], "hors de la plage acceptée"), (["--courtage", "0,6", "--statut", "ecrit"],
                                                                          "sans source"),
                      (["--statut", "avis"], "dans la même commande")):
        code, out, _ = run_cli(capsys, "plan", "grille", *argv, "--format", "json")
        assert code == 2 and mot in one_json(out)["message"], argv
        assert not (data / "profil" / "grille_sgi.yaml").exists()
    code, out, _ = run_cli(capsys, "plan", "grille", "--courtage", "0,6", "--par-ligne", "0", "--source",
                           "grille écrite du courtier, 2026", "--investisseur", "physique", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["enregistree"] is True and Path(d["chemin"]).is_file()
    ch = d["grille"]["champs"]
    assert ch["courtage"]["valeur"] == pytest.approx(0.006) and ch["courtage"]["statut"] == "grille écrite"
    assert ch["tenue_par_ligne"]["valeur"] == 0.0 and ch["garde"]["statut"] == "supposé"
    assert d["grille"]["statut_global"] == "supposé"  # trois des cinq champs principaux restent supposés
    # La grille enregistrée est employée par défaut par « plan ».
    run_cli(capsys, "plan", "--sans-notes")
    assert fausse_reco[-1]["grille"] == "ma_sgi"
    # Comparaison sur les lignes du cache de « plan » : aucune relance de recommend.
    n = len(fausse_reco)
    code, out, _ = run_cli(capsys, "plan", "grille", "--comparer", "--format", "json")
    d = one_json(out)
    assert code == 0 and len(fausse_reco) == n and d["comparaison"]["source"].startswith("cache")
    noms = {x["cle"]: x for x in d["comparaison"]["lignes"]}
    assert noms["central"]["premiere_annee"] == 284_714 and {"central", "ma_sgi"} <= set(noms)
    code, out, _ = run_cli(capsys, "plan", "grille", "--comparer")
    assert code == 0 and "Frais évités par rapport au tarif supposé" in out and "frais évités" in out


# ---------------------------------------------------------------------------
# suivi : carnets, mise à jour, bulletin, vérification, export
# ---------------------------------------------------------------------------


@pytest.fixture()
def horloge(monkeypatch):
    box = {"t": pd.Timestamp("2026-11-23 08:00", tz="UTC")}
    monkeypatch.setattr(cli, "now_utc", lambda: box["t"])
    return box


@pytest.fixture()
def panel_suivi(monkeypatch):
    p = SJ.panel_simple(JOURS, {"AAA": [100.0] * 20, "BBB": [50.0] * 10 + [55.0] * 10}, volume=10_000.0)
    monkeypatch.setattr(cli_rendement, "_panels", lambda panel_dir=None: p)
    return p


def test_suivi_carnet_commands_write_only_in_the_data_folder(donnees, horloge, panel_suivi, capsys):
    data, reports = donnees
    code, out, _ = run_cli(capsys, "suivi", "demarrer", "--nom", "PLAN", "--capital", "2M", "--format", "json")
    d = one_json(out)
    assert code == 0 and [m["type"] for m in d["mouvements"]] == ["mandat", "apport"]
    assert Path(d["carnet"]) == data / "suivi" / "PLAN" / "carnet.jsonl"
    code, out, _ = run_cli(capsys, "suivi", "demarrer", "--nom", "PLAN", "--format", "json")
    assert code == 2 and "déjà démarré" in one_json(out)["message"]
    code, out, _ = run_cli(capsys, "suivi", "demarrer", "--nom", "REF-S2", "--format", "json")
    assert code == 2 and "moteur" in one_json(out)["message"]
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "PLAN", "--apport", "500000")
    assert code == 0 and "Apport de 500\u202f000 FCFA" in out and out.rstrip().endswith(cli.BANNER)
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "PLAN", "--retrait", "100k", "--format", "json")
    assert code == 0 and one_json(out)["mouvement"]["type"] == "retrait"
    code, out, _ = run_cli(capsys, "suivi", "revue", "--nom", "PLAN", "--alerte", "W1", "--decision", "garder",
                           "--texte", "frais connus, dividende attendu", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["mouvement"]["decision"] == "garder" and "jamais une vente" in d["phrase"]
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "PLAN", "--fichier", "avis.csv", "--format", "json")
    assert code == 2 and "portefeuille réel" in one_json(out)["message"]  # sur papier : pas d'avis d'opéré
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "INCONNU", "--apport", "1000", "--format", "json")
    assert code == 1 and "suivi demarrer" in one_json(out)["message"]
    for argv in (["demarrer", "--nom", "../X"], ["saisir", "--nom", ".cache", "--apport", "1"], ["bulletin", "--nom", "a/b"],
                 ["maj", "--nom", "../X"]):
        code, out, _ = run_cli(capsys, "suivi", *argv, "--format", "json")
        assert code == 2 and "nom de portefeuille invalide" in one_json(out)["message"], argv  # refus, pas une panne
    c = CN.ouvrir("PLAN", data / "suivi", creer=False)
    assert c.verifier()["ok"] and c.liquidites() == 2_400_000
    assert not any(reports.iterdir())


def test_suivi_maj_writes_weeks_once_and_the_witness_waits_for_its_first_bulletin(donnees, horloge, panel_suivi,
                                                                                  capsys):
    data, _ = donnees
    horloge["t"] = pd.Timestamp(JOURS[0], tz="UTC") + pd.Timedelta(hours=8)
    run_cli(capsys, "suivi", "demarrer", "--nom", "PLAN", "--capital", "1M")
    c = CN.ouvrir("PLAN", data / "suivi", creer=False)
    c.ajouter({"type": "ordre", "date": JOURS[0], "symbole": "AAA", "sens": "achat", "titres": 50, "limite": 102,
               "cours_reference": 100, "validite": 10, "motif": "remise_a_niveau"})
    horloge["t"] = pd.Timestamp(JOURS[-1], tz="UTC") + pd.Timedelta(hours=20)
    code, out, _ = run_cli(capsys, "suivi", "maj", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["en_echec"] == []
    pf = {r["nom"]: r for r in d["portefeuilles"]}
    assert pf["REF-S2"]["ecrit"] is False and pf["REF-S2"]["semaine_0"] is True  # départ du 30/11/2026 absent
    assert pf["PLAN"]["ecrit"] is True and pf["PLAN"]["ajoutees"] >= 3 and pf["PLAN"]["mouvements_ajoutes"] >= 1
    assert not (data / "suivi" / "REF-S2").exists()
    # Relance : rien de nouveau, rien de réécrit.
    code, out, _ = run_cli(capsys, "suivi", "maj", "--format", "json")
    pf = {r["nom"]: r for r in one_json(out)["portefeuilles"]}
    assert code == 0 and pf["PLAN"]["ajoutees"] == 0 and pf["PLAN"]["identiques"] >= 3 and not pf["PLAN"]["passe_a_change"]
    code, out, _ = run_cli(capsys, "suivi", "bulletin", "--nom", "PLAN", "--format", "json")
    b = one_json(out)
    assert code == 0 and b["nom"] == "PLAN" and b["semaine"] >= 3 and set(b["feux"]) >= {"perte", "fuites", "donnees"}
    code, out, _ = run_cli(capsys, "suivi", "bulletin", "--nom", "PLAN")
    assert code == 0 and out.startswith("BULLETIN DE LA SEMAINE") and RG.BANNER in out
    assert RG.mots_interdits(out) == []
    code, out, _ = run_cli(capsys, "suivi", "bulletin", "--format", "md", "--sortie", str(data / "b.md"))
    assert code == 0 and "Bulletin écrit" in out and (data / "b.md").read_text(encoding="utf-8").startswith("### ")
    code, out, _ = run_cli(capsys, "suivi", "verifier", "--format", "json")
    d = one_json(out)
    assert code == 0 and d["rompues"] == [] and d["declaration"]["existe"] is False
    # Une semaine réécrite rompt la chaîne : code 1, un seul objet JSON.
    p = data / "suivi" / "PLAN" / "semaines.csv"
    lignes = p.read_text(encoding="utf-8").splitlines()
    lignes[1] = lignes[1].replace(",", ";", 1)
    p.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    code, out, err = run_cli(capsys, "suivi", "verifier", "--format", "json")
    d = one_json(out)
    assert code == 1 and d["ok"] is False and d["rompues"] == ["PLAN"] and "chaîne rompue" in d["message"]
    code, out, err = run_cli(capsys, "suivi", "verifier")
    assert code == 1 and "chaîne rompue" in err


def test_suivi_maj_one_failing_portfolio_does_not_stop_the_others(donnees, horloge, panel_suivi, capsys, monkeypatch):
    horloge["t"] = pd.Timestamp(JOURS[0], tz="UTC") + pd.Timedelta(hours=8)
    for nom in ("E-C", "PLAN"):
        run_cli(capsys, "suivi", "demarrer", "--nom", nom)
    vrai = cli_rendement._maj_carnet
    vus: list[str] = []

    def fragile(nom, *a, **k):
        vus.append(nom)
        if nom == "E-C":
            raise RuntimeError("panne du carnet")
        return vrai(nom, *a, **k)

    monkeypatch.setattr(cli_rendement, "_maj_carnet", fragile)
    code, out, err = run_cli(capsys, "suivi", "maj", "--format", "json")
    d = one_json(out)
    assert code == 7 and d["ok"] is False and d["en_echec"] == ["E-C"] and vus == ["E-C", "PLAN"]
    assert {r["nom"]: r["ok"] for r in d["portefeuilles"]} == {"REF-S2": True, "E-C": False, "PLAN": True}
    assert "panne du carnet" in err
    code, out, _ = run_cli(capsys, "suivi", "maj", "--nom", "N", "--format", "json")
    assert code == 2 and "déclaré" in one_json(out)["message"]  # N n'est suivi que s'il est déclaré
    monkeypatch.setattr(cli_rendement, "_panels", lambda panel_dir=None: (_ for _ in ()).throw(
        erreurs.DonneesAbsentes("échec : panel introuvable")))
    code, out, _ = run_cli(capsys, "suivi", "maj", "--format", "json")
    assert code == 1 and one_json(out)["erreur"] == "donnees_absentes"


def test_suivi_bulletin_without_journal_and_without_panel(donnees, horloge, capsys, monkeypatch):
    monkeypatch.setattr(cli_rendement, "_panels", lambda panel_dir=None: (_ for _ in ()).throw(
        erreurs.DonneesAbsentes("échec : panel introuvable")))
    code, out, _ = run_cli(capsys, "suivi", "bulletin")
    assert code == 0 and "semaine 0" in out and "le suivi n'a pas commencé" in out and RG.BANNER in out
    assert RG.mots_interdits(out) == []
    assert not any(donnees[0].iterdir())  # lecture seule


def test_suivi_exporter_copies_in_one_block_and_leaves_moi_out(donnees, horloge, capsys, tmp_path):
    data, reports = donnees
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(tmp_path / "x"), "--format", "json")
    assert code == 1 and one_json(out)["erreur"] == "donnees_absentes"
    run_cli(capsys, "suivi", "demarrer", "--nom", "MOI")
    run_cli(capsys, "suivi", "demarrer", "--nom", "PLAN")
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(tmp_path / "export"), "--format", "json")
    d = one_json(out)
    assert code == 0 and d["fichiers"] == ["PLAN/carnet.jsonl"] and d["exclus"] == ["MOI"]
    assert not list(tmp_path.glob(".export*"))  # aucun dossier temporaire laissé
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(tmp_path / "export"), "--format", "json")
    assert code == 2 and "rien n'est écrasé" in one_json(out)["message"]
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(data / "suivi" / "copie"), "--format", "json")
    assert code == 2 and "recouvre" in one_json(out)["message"]
    interdit = ROOT / "reports" / "validation_S1" / "journaux_interdits"
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(interdit), "--format", "json")
    assert code == 2 and "résultats publiés" in one_json(out)["message"] and not interdit.exists()
    (tmp_path / "vide").mkdir()
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(tmp_path / "vide"), "--avec-moi")
    assert code == 0 and (tmp_path / "vide" / "MOI" / "carnet.jsonl").is_file()


def test_suivi_saisir_avis_in_a_real_portfolio(donnees, horloge, capsys, tmp_path):
    from brvm_alpha.rendement import grille as G

    run_cli(capsys, "suivi", "demarrer", "--nom", "MOI", "--mode", "reel", "--capital", "1M")
    g = G.defaut()
    fr = G.frais_explicites(10 * 15_000, g)
    avis = tmp_path / "avis.csv"
    avis.write_text("date;symbole;sens;titres;prix;courtage;taxe;brvm;dcbr;autres_frais;total\n"
                    f"2026-11-23;snts;achat;10;15000;{fr['courtage']};{fr['tva']};{fr['brvm']};{fr['dcbr']};0;\n",
                    encoding="utf-8")
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "MOI", "--fichier", str(avis), "--format", "json")
    d = one_json(out)
    assert code == 0 and d["concorde"] is True and d["grille_enregistree"]
    assert G.charger(donnees[0] / "profil").champs["courtage"].statut == G.AVIS
    c = CN.ouvrir("MOI", donnees[0] / "suivi", creer=False)
    assert c.positions()["SNTS"]["titres"] == 10
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "MOI", "--fichier", str(avis), "--format", "json")
    assert code == 2 and "double" in one_json(out)["message"]  # saisie en double refusée
    bad = tmp_path / "mauvais.csv"
    bad.write_text("date,symbole,sens,titres,prix\n2026-11-23,SNTS,don,1,1\n", encoding="utf-8")
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "MOI", "--fichier", str(bad), "--format", "json")
    assert code == 2 and "sens" in one_json(out)["message"]


# ---------------------------------------------------------------------------
# suivi declarer : jamais sur le vrai dépôt ; signature et registre sur une copie
# ---------------------------------------------------------------------------


def test_declarer_outside_the_development_repository_is_refused_with_code_2(donnees, capsys, monkeypatch):
    monkeypatch.setattr(DE, "depot_de_developpement", lambda racine=None: False)
    for argv in (["--modele"], ["--fichier", "x.json", "--signer", "AB"], ["--registre", "--confirmer", "x"]):
        code, out, _ = run_cli(capsys, "suivi", "declarer", *argv, "--format", "json")
        d = one_json(out)
        assert code == 2 and DE.MESSAGE_HORS_DEPOT in d["message"], argv


@pytest.fixture()
def copie_du_depot(tmp_path, monkeypatch, donnees):
    """Copie de dépôt de développement (``git init``, registre copié et suivi) : la seule où l'on signe."""
    d = SJ.depot(tmp_path)
    monkeypatch.setattr(paths, "REPO_ROOT", d)
    return d


def test_declarer_signs_and_registers_only_in_a_copy(copie_du_depot, capsys, tmp_path):
    d = copie_du_depot
    reg = d / "reports" / "trials.parquet"
    avant = pd.read_parquet(reg)
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--modele", "--format", "json")
    arts = one_json(out)["modele"]
    assert code == 0 and {a["id"] for a in arts} >= {"REF-S2", "N", "PLAN"}
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--modele", "--sortie", str(tmp_path / "modele.json"))
    assert code == 0 and json.loads((tmp_path / "modele.json").read_text(encoding="utf-8"))
    reponses = tmp_path / "reponses.json"
    reponses.write_text(json.dumps(SJ.reponses_proposees(arts), ensure_ascii=False), encoding="utf-8")
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--fichier", str(reponses), "--signer", "Jean Dupont",
                           "--format", "json")
    assert code == 2 and "initiales" in one_json(out)["message"] and not (d / "reports" / "suivi_S2").exists()
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--fichier", str(reponses), "--signer", "AB", "--format", "json")
    v = one_json(out)
    assert code == 0 and v["verification"]["existe"] and v["verification"]["chaine_ok"]
    assert Path(v["chemin"]) == d / "reports" / "suivi_S2" / "declaration.jsonl"
    lignes = DE.lignes(d / "reports" / "suivi_S2")
    assert all(x["signe_par"] == "AB" for x in lignes) and not any("Dupont" in json.dumps(x) for x in lignes)
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--registre", "--confirmer", "oui", "--format", "json")
    assert code == 2 and "J'INSCRIS AU REGISTRE" in one_json(out)["message"]
    assert len(pd.read_parquet(reg)) == len(avant)
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--registre", "--confirmer", DE.CONFIRMATION_REGISTRE,
                           "--format", "json")
    d2 = one_json(out)
    apres = pd.read_parquet(reg)
    assert code == 0 and "S2-REF" in d2["inscrits"] and len(apres) == len(avant) + len(d2["inscrits"])
    assert DE.empreinte_lignes(apres, len(avant)) == DE.empreinte_lignes(avant)  # lignes existantes intactes
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--registre", "--confirmer", DE.CONFIRMATION_REGISTRE,
                           "--format", "json")
    assert code == 0 and one_json(out)["inscrits"] == []  # pas de doublon
    code, out, _ = run_cli(capsys, "suivi", "verifier", "--format", "json")
    assert code == 0 and one_json(out)["declaration"]["n_lignes"] == len(lignes)
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--format", "json")
    assert code == 2 and "--modele" in one_json(out)["message"]


# ---------------------------------------------------------------------------
# Mode embarqué
# ---------------------------------------------------------------------------


@pytest.fixture()
def embarque(donnees, monkeypatch):
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: True)
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    return donnees


def test_embedded_plan_and_suivi_write_only_in_the_data_folders(embarque, fausse_reco, horloge, panel_suivi, capsys,
                                                                  monkeypatch):
    data, reports = embarque
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--format", "json")
    assert code == 0 and Path(one_json(out)["plan_cache"]) == data / "profil" / "plan_cache.json"
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--sortie", "ecran.txt", "--format", "json")
    assert code == 0 and Path(one_json(out)["chemin"]) == reports / "ecran.txt" and (reports / "ecran.txt").is_file()
    inside = paths.REPO_ROOT / "brvm_alpha" / "ecran_interdit.txt"
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--sortie", str(inside), "--format", "json")
    assert code == 8 and one_json(out)["erreur"] == "configuration" and not inside.exists()
    code, out, _ = run_cli(capsys, "suivi", "demarrer", "--nom", "PLAN", "--format", "json")
    assert code == 0 and Path(one_json(out)["carnet"]).is_relative_to(data)
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", "journaux", "--format", "json")
    assert code == 0 and Path(one_json(out)["chemin"]) == reports / "journaux"
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(paths.REPO_ROOT / "export_interdit"),
                           "--format", "json")
    assert code == 8 and not (paths.REPO_ROOT / "export_interdit").exists()
    monkeypatch.setattr("tempfile.tempdir", str(data.parent / "tmp_systeme"))  # ni rapports, ni temporaires
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(data.parent / "ailleurs"), "--format", "json")
    assert code == 2 and "hors des dossiers permis" in one_json(out)["message"]
    code, out, _ = run_cli(capsys, "suivi", "declarer", "--modele", "--format", "json")
    assert code == 2 and DE.MESSAGE_HORS_DEPOT in one_json(out)["message"]  # jamais signée sur l'installation
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--grille", "../grille.yaml", "--format", "json")
    assert code == 2 and "« .. »" in one_json(out)["message"]
    for argv in (["plan", "questions"], ["suivi", "verifier"], ["suivi", "bulletin"]):
        code, out, _ = run_cli(capsys, *argv, "--format", "json")
        assert code == 0 and one_json(out)["ok"] is True, argv


def test_embedded_configuration_error_stops_plan_and_suivi_before_any_write(embarque, fausse_reco, capsys,
                                                                             monkeypatch):
    data, reports = embarque
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION",
                        erreurs.ConfigurationError("mode embarqué : la variable BRVM_ALPHA_DONNEES est obligatoire"))
    for argv in (["plan"], ["plan", "questions"], ["suivi", "maj"], ["suivi", "demarrer", "--nom", "MOI"],
                 ["suivi", "verifier"]):
        code, out, _ = run_cli(capsys, *argv, "--format", "json")
        assert code == 8 and one_json(out)["erreur"] == "configuration", argv
    assert not any(data.iterdir()) and not any(reports.iterdir()) and fausse_reco == []


def test_embedded_incomplete_history_refuses_plan_with_code_1(embarque, fausse_reco, capsys, monkeypatch):
    monkeypatch.setattr(cli, "history_state", lambda *a, **k: {"complet": False, "raison": "3 jour(s) ouvré(s)",
                                                                "jours_manquants": 3, "avertissement": "HISTORIQUE"})
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--enregistrer", "--format", "json")
    assert code == 1 and one_json(out)["erreur"] == "historique_incomplet" and fausse_reco == []
    assert not (embarque[0] / "profil").exists()  # refus avant toute écriture
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--accepter-historique-incomplet", "--format", "json")
    assert code == 0 and one_json(out)["historique_complet"] is False


def test_real_process_json_contract_in_normal_and_embedded_mode(tmp_path):
    """Processus réel, comme Odoo : un seul objet JSON sur la sortie standard, code de la table."""
    data, reports = tmp_path / "donnees", tmp_path / "rapports"
    data.mkdir()
    reports.mkdir()
    base = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1",
            "BRVM_ALPHA_DONNEES": str(data), "BRVM_ALPHA_RAPPORTS": str(reports)}
    cas = [({}, ["plan", "questions"], 0), ({}, ["suivi", "verifier"], 0), ({}, ["suivi", "bulletin"], 0),
           ({}, ["plan", "grille", "--courtage", "9"], 2), ({}, ["suivi", "saisir", "--nom", "MOI", "--apport", "1"], 1),
           ({"BRVM_ALPHA_EMBARQUE": "1"}, ["suivi", "verifier"], 0),
           ({"BRVM_ALPHA_EMBARQUE": "1"}, ["suivi", "declarer", "--modele"], 2),
           ({"BRVM_ALPHA_EMBARQUE": "1", "BRVM_ALPHA_DONNEES": ""}, ["suivi", "maj"], 8),
           ({"BRVM_ALPHA_EMBARQUE": "1", "BRVM_ALPHA_DONNEES": ""}, ["plan"], 8)]
    for extra, argv, attendu in cas:
        env = {k: v for k, v in {**base, **extra}.items() if v != ""}
        r = subprocess.run([sys.executable, "-m", "brvm_alpha", *argv, "--format", "json"], env=env, cwd=tmp_path,
                           capture_output=True, text=True, timeout=120)
        d = json.loads(r.stdout)
        assert r.returncode == attendu and d["bandeau"] == cli.BANNER and d["ok"] is (attendu == 0), (argv, r.stderr)
    assert not any(reports.iterdir()) and not any(data.iterdir())  # refus et lectures : rien n'est écrit


def test_unreadable_grid_file_or_saved_grid_is_an_input_error(donnees, fausse_reco, capsys, tmp_path):
    bad = tmp_path / "grille.yaml"
    bad.write_text("champs: [", encoding="utf-8")
    n = len(fausse_reco)
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--sans-notes", "--grille", str(bad), "--format",
                           "json")
    assert code == 2 and "grille du courtier illisible" in one_json(out)["message"] and len(fausse_reco) == n
    (donnees[0] / "profil").mkdir()
    (donnees[0] / "profil" / "grille_sgi.yaml").write_text("champs: {courtage: 0.9}\n", encoding="utf-8")
    for argv in (["plan", "--sans-notes"], ["plan", "grille"], ["recommend", "--capital", "1M", "--grille", "ma_sgi"]):
        code, out, _ = run_cli(capsys, *argv, "--format", "json")
        assert code == 2 and "illisible" in one_json(out)["message"], argv  # 90 % de courtage : hors plage
