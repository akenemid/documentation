"""Petits défauts du module « Rendement net et pertes » relevés au contrôle final, rejoués sur l'état fusionné (364bed5)
puis corrigés. Chaque essai échouait avant la correction (sauf ceux qui gardent ce qui ne devait pas changer) :

1. ``suivi exporter --sortie ' '`` (ou vide) sortait en 7 (TypeError) : désormais 2, rien d'écrit, dans les deux modes ;
2. ``suivi saisir --retrait`` plus grand que les liquidités du carnet rendait 0 et restait au carnet pour toujours :
   désormais 2 avant toute écriture ; un retrait égal aux liquidités reste accepté ;
3. ``suivi revue --alerte W99`` acceptait un code inconnu : désormais 2, les codes connus sont cités ;
4. ``plan --grille ' '`` prenait le tarif par défaut et rendait 0 : désormais 2 (de même pour ``recommend``) ;
5. un courtage saisi « 0,7 » était enregistré 0.006999999999999999 : désormais 0.007, montants inchangés ;
6. « L'essentiel » portait « [compté] » sur la réserve, l'écran « taux inconnu : compté à 0 % » : un seul libellé ;
7. TERM et ``SIGXCPU`` reçus pendant une écriture de ``plan``, ``plan grille`` ou ``suivi`` : l'écriture se termine
   (fichier complet et valide) ; puis la commande sort en 130 (8 pour ``SIGXCPU``) si elle avait encore à faire, ou
   rend son vrai résultat si l'écriture était sa dernière étape (comme ``notes add`` depuis 0b26241) ; toujours un
   seul objet JSON. Essais à vrais processus : doublure lente de l'écriture, signal envoyé de l'extérieur.

Dossiers temporaires seulement ; aucune requête réseau ; le code 3 n'est jamais attendu.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import fcntl
import html
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

import rendement_jeux as RJ
from test_cli_rendement import _Ordre, donnees, fausse_reco, gardes_du_depot, horloge, one_json, rn10, run_cli  # noqa: F401

from brvm_alpha import cli, cli_rendement, paths, rendement
from brvm_alpha.rendement import alertes as AL
from brvm_alpha.rendement import grille as G
from brvm_alpha.rendement import perte as PE
from brvm_alpha.rendement import plan as PL
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.rendement import rendu as RD
from brvm_alpha.suivi import carnet as CN

ROOT = Path(__file__).resolve().parents[1]
LINUX = sys.platform.startswith("linux")
JOUR = "2026-11-23"


@pytest.fixture()
def embarque(tmp_path, monkeypatch):
    data, reports = tmp_path / "donnees_emb", tmp_path / "rapports_emb"
    (data / "notes").mkdir(parents=True)
    reports.mkdir()
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: True)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "REPORTS_DIR", reports)
    monkeypatch.setattr(paths, "NOTES_DIR", data / "notes")
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    return data, reports


def _carnet(data: Path, nom: str = "PLAN", capital: float = 2_000_000.0) -> CN.Carnet:
    c = CN.ouvrir(nom, data / "suivi", creer=True)
    c.ajouter_plusieurs([{"type": "mandat", "date": JOUR, "capital": capital, "mode": "papier", "grille": "central",
                          "perte_toleree": None, "taux_reserve": None, "options_execution": []},
                         {"type": "apport", "date": JOUR, "montant": capital}])
    return c


def _arbre(p: Path) -> list[str]:
    return sorted(x.relative_to(p).as_posix() for x in p.rglob("*")) if p.exists() else []


# ---------------------------------------------------------------------------
# 1. suivi exporter --sortie vide ou blanche
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valeur", ["", " ", "\t"])
@pytest.mark.parametrize("mode", ["normal", "embarque"])
def test_export_with_a_blank_destination_is_refused_and_writes_nothing(request, tmp_path, monkeypatch, capsys, valeur,
                                                                       mode, horloge):
    data, reports = request.getfixturevalue("donnees" if mode == "normal" else "embarque")
    _carnet(data)
    courant = tmp_path / "courant"
    courant.mkdir()
    monkeypatch.chdir(courant)
    avant = _arbre(data), _arbre(reports)
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", valeur, "--format", "json")
    d = one_json(out)  # avant : code 7, « erreur interne : TypeError »
    assert code == 2 and d["erreur"] == "saisie_invalide" and "--sortie vide" in d["message"], d
    assert (_arbre(data), _arbre(reports)) == avant and _arbre(courant) == []


def test_export_still_copies_to_a_new_folder(donnees, horloge, capsys, tmp_path):
    data, _ = donnees
    _carnet(data)
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", str(tmp_path / "copie"), "--format", "json")
    d = one_json(out)
    assert code == 0 and d["fichiers"] == ["PLAN/carnet.jsonl"]
    assert (tmp_path / "copie" / "PLAN" / "carnet.jsonl").read_bytes() == (data / "suivi/PLAN/carnet.jsonl").read_bytes()


# ---------------------------------------------------------------------------
# 2. Retrait plus grand que les liquidités
# ---------------------------------------------------------------------------


def test_a_withdrawal_above_the_cash_is_refused_before_any_write(donnees, horloge, capsys):
    data, _ = donnees
    c = _carnet(data, capital=2_000_000.0)
    brut = c.fichier.read_bytes()
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "PLAN", "--retrait", "999999999999", "--format", "json")
    d = one_json(out)  # avant : code 0, retrait inscrit pour toujours dans le carnet (ajout seul)
    assert code == 2 and d["erreur"] == "saisie_invalide", d
    assert "retrait refusé" in d["message"] and "liquidités" in d["message"] and "2 000 000" in d["message"]
    assert c.fichier.read_bytes() == brut
    # Égal aux liquidités : accepté ; un franc de plus ensuite : refusé.
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "PLAN", "--retrait", "2M", "--format", "json")
    assert code == 0 and one_json(out)["mouvement"]["montant"] == 2_000_000.0
    assert c.liquidites() == 0.0
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "PLAN", "--retrait", "1", "--format", "json")
    assert code == 2 and "retrait refusé" in one_json(out)["message"]
    assert [m["type"] for m in c.mouvements()] == ["mandat", "apport", "retrait"] and c.verifier()["chaine_ok"]


def test_the_book_counts_purchases_and_dividends_in_the_cash(tmp_path):
    c = CN.ouvrir("MOI", tmp_path)
    c.ajouter({"type": "apport", "date": JOUR, "montant": 100_000})
    c.ajouter({"type": "execution", "date": JOUR, "symbole": "AAA", "sens": "achat", "titres": 300, "prix": 101,
               "frais": {"courtage": 377}, "source": "papier"})
    liq = c.liquidites()
    assert liq == pytest.approx(100_000 - 300 * 101 - 377)
    with pytest.raises(ValueError, match="retrait refusé"):
        c.ajouter({"type": "retrait", "date": JOUR, "montant": liq + 1})
    assert c.ajouter({"type": "retrait", "date": JOUR, "montant": liq})["montant"] == liq  # égal : accepté
    with pytest.raises(ValueError, match="retrait refusé"):  # dans un même ajout groupé aussi
        c.ajouter_plusieurs([{"type": "apport", "date": JOUR, "montant": 10}, {"type": "retrait", "date": JOUR,
                                                                              "montant": 11}])
    assert c.liquidites() == pytest.approx(0.0) and c.verifier()["chaine_ok"]


# ---------------------------------------------------------------------------
# 3. Code d'alerte inconnu dans une revue
# ---------------------------------------------------------------------------


def test_a_review_of_an_unknown_alert_code_is_refused_and_cites_the_known_codes(donnees, horloge, capsys):
    data, _ = donnees
    c = _carnet(data)
    brut = c.fichier.read_bytes()
    for code_inconnu in ("W99", "W0", "w10", "W1_fort", "la ligne SNTS"):
        code, out, _ = run_cli(capsys, "suivi", "revue", "--nom", "PLAN", "--alerte", code_inconnu, "--decision",
                               "garder", "--texte", "essai", "--format", "json")
        d = one_json(out)  # avant : code 0, revue « W99 » consignée
        assert code == 2 and "alerte inconnue" in d["message"], (code_inconnu, d)
        assert all(x in d["message"] for x in ("W1", "W9", "perte", "fuites", "données")), d["message"]
    assert c.fichier.read_bytes() == brut
    for vu, garde in (("w4", "W4"), ("perte", "perte"), ("Données", "donnees"), ("snts", "SNTS")):
        code, out, _ = run_cli(capsys, "suivi", "revue", "--nom", "PLAN", "--alerte", vu, "--decision", "garder",
                               "--texte", f"essai {vu}", "--format", "json")
        assert code == 0 and one_json(out)["mouvement"]["alerte"] == garde, vu
    assert AL.CODES_ALERTES == tuple(f"W{i}" for i in range(1, 10))
    assert AL.cible_de_revue(" W9 ") == "W9" and c.verifier()["chaine_ok"]


# ---------------------------------------------------------------------------
# 4. --grille vide ou blanche
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valeur", ["", " "])
def test_a_blank_grid_option_is_refused_before_any_calculation(donnees, fausse_reco, capsys, valeur):
    data, _ = donnees
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--grille", valeur, "--format", "json")
    d = one_json(out)  # avant : code 0, tarif par défaut pris sans le dire
    assert code == 2 and "--grille vide" in d["message"] and fausse_reco == [], d
    assert not (data / "profil").exists()
    code, out, _ = run_cli(capsys, "recommend", "--capital", "10M", "--grille", valeur, "--format", "json")
    assert code == 2 and "--grille vide" in one_json(out)["message"] and fausse_reco == []
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--grille", "central", "--format", "json")
    assert code == 0 and fausse_reco[-1]["grille"] == "central"  # une vraie valeur passe toujours


def test_a_blank_grid_option_is_refused_in_embedded_mode_too(embarque, fausse_reco, capsys):
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--grille", " ", "--format", "json")
    assert code == 2 and "--grille vide" in one_json(out)["message"] and fausse_reco == []
    assert not (embarque[0] / "profil").exists()


# ---------------------------------------------------------------------------
# 5. Taux saisis : valeur décimale exacte
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("saisie, attendu", [("0,7", "0.007"), ("0,6", "0.006"), ("1,1 %", "0.011"), ("0.35", "0.0035"),
                                             ("18", "0.18"), ("0", "0.0"), ("2,05", "0.0205")])
def test_rates_are_parsed_to_the_exact_decimal_value(saisie, attendu):
    assert repr(cli_rendement.parse_taux(saisie)) == attendu  # avant : « 0,7 » → 0.006999999999999999


@pytest.mark.parametrize("saisie", ["huit", "nan", "inf", "-1", "101", "", "1e400"])
def test_invalid_rates_are_still_refused(saisie):
    with pytest.raises(ValueError, match="taux invalide"):
        cli_rendement.parse_taux(saisie)


def test_grid_entry_saves_0_007_and_the_rounded_amounts_do_not_change(donnees, fausse_reco, capsys):
    data, _ = donnees
    code, out, _ = run_cli(capsys, "plan", "grille", "--courtage", "0,7", "--format", "json")
    assert code == 0 and one_json(out)["grille"]["champs"]["courtage"]["valeur"] == 0.007
    texte = (data / "profil" / "grille_sgi.yaml").read_text(encoding="utf-8")
    assert "valeur: 0.007\n" in texte and "0.00699" not in texte
    assert G.charger(data / "profil").valeur("courtage") == 0.007
    assert not [p for p in (data / "profil").iterdir() if p.name != "grille_sgi.yaml"]  # aucun fichier temporaire
    # Montants arrondis inchangés entre l'ancienne valeur et la nouvelle (ordre figé du 10 M).
    g_avant = G.defaut().avec(courtage=0.006999999999999999)
    g_apres = G.defaut().avec(courtage=0.007)
    od = RJ.ordre("10M")
    a, b = G.comparer(od, {"avant": g_avant, "apres": g_apres})
    cles = ("frais_achat", "frais_annuels", "premiere_annee")
    assert {k: a[k] for k in cles} == {k: b[k] for k in cles}


# ---------------------------------------------------------------------------
# 6. Libellé de la réserve : le même partout
# ---------------------------------------------------------------------------


def _plat(t: str) -> str:
    """Texte de l'écran sans espaces insécables ni retours à la ligne (les colonnes de l'écran restent séparées)."""
    return " ".join(t.replace("\u202f", " ").replace("\xa0", " ").split())


def _ligne_reserve(rn) -> str:
    items = [b[1] for b in RD.bloc_essentiel(rn) if b[0] == "ul"][0]
    return next(x for x in items if x.startswith("Réserve "))


def test_the_reserve_carries_the_screen_label_in_the_summary_markdown_html_and_json(rn10):
    ligne = _ligne_reserve(rn10)
    assert "[taux inconnu : compté à 0 %]" in ligne and "[compté]" not in ligne, ligne  # avant : « [compté] »
    assert rn10["reserve"]["etiquette"] == PE.TAUX_INCONNU == "taux inconnu : compté à 0 %"
    titre = next(l for l in rn10["plan"]["lignes"] if l["bloc"] == "reserve" and l["type"] == "titre")
    assert titre["etiquette"] == rn10["reserve"]["etiquette"]  # écran « Mon plan » et JSON : le même libellé
    assert "[ taux inconnu : compté à 0 % ]" in _plat(PL.rendre_plan(rn10["plan"], "texte"))
    blocs = RD.bloc_essentiel(rn10) + RD.blocs_section(rn10)
    for fmt, t in (("md", RD.fragment(blocs, "md")), ("html", RD.fragment(blocs, "html")),
                   ("rapport", RD.html_rapport(blocs))):  # rendu de l'ordre (Markdown, HTML) et du rapport HTML
        t = html.unescape(t)
        reserve = [_plat(x) for x in t.replace("<li>", "\n").split("\n") if "point d'intérêt" in x]
        assert len(reserve) == 2, (fmt, reserve)  # « L'essentiel » et la section « Où dort le reste »
        assert "[taux inconnu : compté à 0 %]" in reserve[0] and "[compté]" not in reserve[0], (fmt, reserve)
        assert "Réserve 10 000 000 FCFA ; taux inconnu : compté à 0 % ;" in _plat(t), fmt
    ordre = _Ordre(rn10)
    assert json.loads(json.dumps(cli.to_jsonable(ordre.to_dict())))["rendement_net"]["reserve"]["etiquette"] \
        == "taux inconnu : compté à 0 %"


def test_a_known_rate_and_an_equity_pocket_keep_the_same_label_on_screen_and_in_the_summary():
    rn = rendement.construire(RJ.ordre("10M"), panels=RJ.panels_reels(), validation_dir=RJ.VALIDATION_S1,
                              aujourd_hui=RJ.AUJOURD_HUI, carnet_cloture=RJ.carnet(), perte_toleree=1_000_000,
                              taux_reserve=0.03)
    r = rn["reserve"]
    etiq = f"taux saisi : {RG.pct(0.03, 2)} [supposé]"
    assert r["etiquette"] == etiq and r["montant"] < 10_000_000
    assert _ligne_reserve(rn).endswith(f"[estimé ; {etiq}]. {RG.PH_INTERETS}")  # avant : « [compté] »
    assert r["statut_valeur_d_un_point"] == "Estimation"  # comme « [estimé] » sur l'écran (avant : « Fait »)
    texte = _plat(PL.rendre_plan(rn["plan"], "texte"))
    assert f"[ {_plat(etiq)} ]" in texte and "[estimé]" in texte
    assert PE.etiquette_taux(None) == PE.TAUX_INCONNU


# ---------------------------------------------------------------------------
# 7. TERM et SIGXCPU pendant les écritures de plan, plan grille et suivi (vrais processus)
# ---------------------------------------------------------------------------

#: Lanceur d'essai : doublure lente de l'écriture (fsync ou renommage du fichier visé), puis le moteur. Avec
#: DOUBLURE_PLAN, le calcul de l'ordre est remplacé par un ordre figé (rendement net du 20/11/2026).
_LANCEUR = r'''
import json, os, sys, time
from pathlib import Path

MOTIF, MARQUE = os.environ["ECRITURE_LENTE"], Path(os.environ["MARQUE"])
_fsync, _replace = os.fsync, os.replace


def _attendre(nom):
    if MOTIF in os.path.basename(str(nom)) and not MARQUE.exists():
        MARQUE.write_text(str(nom), encoding="utf-8")
        fin = time.monotonic() + float(os.environ.get("LENTEUR", "2"))
        while time.monotonic() < fin:  # le signal du test arrive pendant cette attente
            time.sleep(0.02)


def fsync(fd):
    try:
        nom = os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        nom = ""
    _attendre(nom)
    return _fsync(fd)


def replace(src, dst, *a, **k):
    _attendre(src)
    return _replace(src, dst, *a, **k)


os.fsync, os.replace = fsync, replace
if os.environ.get("DOUBLURE_PLAN"):
    import pandas as pd
    from brvm_alpha import cli
    from brvm_alpha.portfolio import recommend as rec

    rn = json.loads(Path(os.environ["RN_JSON"]).read_text(encoding="utf-8"))

    class _Ordre:
        rendement_net = rn

        def to_dict(self):
            return {"asof": "2026-11-20", "capital": 10_000_000.0, "lignes": [], "rendement_net": rn}

    cli.history_state = lambda *a, **k: {"complet": True, "raison": None, "jours_manquants": 0, "avertissement": None}
    cli.last_session = lambda *a, **k: pd.Timestamp("2026-11-20")
    rec.recommend = lambda *a, **k: _Ordre()
from brvm_alpha import demarrage

sys.exit(demarrage.lancer(sys.argv[1:]))
'''


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("BRVM_ALPHA_")}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(ROOT), "HTTPS_PROXY": "http://127.0.0.1:9",
                "HTTP_PROXY": "http://127.0.0.1:9", "BRVM_ALPHA_DONNEES": str(tmp_path / "donnees"),
                "BRVM_ALPHA_RAPPORTS": str(tmp_path / "rapports")})
    env.update(extra)
    return env


def _pendant_l_ecriture(tmp_path: Path, argv: list[str], motif: str, sig: int, **extra: str
                        ) -> tuple[int, dict, str]:
    """Lance ``python -m brvm_alpha argv`` (lanceur d'essai) ; dès que l'écriture du fichier ``motif`` commence, envoie
    ``sig`` depuis l'extérieur ; rend (code, l'unique objet JSON, sortie d'erreur)."""
    (tmp_path / "donnees").mkdir(exist_ok=True)
    (tmp_path / "rapports").mkdir(exist_ok=True)
    lanceur, marque = tmp_path / "lanceur.py", tmp_path / "marque_ecriture"
    lanceur.write_text(_LANCEUR, encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-B", str(lanceur), *argv, "--format", "json"],
                         env=_env(tmp_path, ECRITURE_LENTE=motif, MARQUE=str(marque), **extra), cwd=str(tmp_path),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    t0 = time.monotonic()
    while not marque.exists() and p.poll() is None and time.monotonic() - t0 < 90:
        time.sleep(0.02)
    assert marque.exists(), ("l'écriture visée n'a pas commencé", p.poll(), p.communicate(timeout=60))
    time.sleep(0.2)
    p.send_signal(sig)
    out, err = p.communicate(timeout=90)
    d = json.loads(out)  # exactement un objet JSON (json.loads refuse tout texte en plus)
    assert isinstance(d, dict) and d["bandeau"] == cli.BANNER
    assert p.returncode in {0, 1, 2, 4, 5, 6, 7, 8, 130}
    return p.returncode, d, err


SIGNAUX = [pytest.param(signal.SIGTERM, 130, "interruption", id="TERM"),
           pytest.param(getattr(signal, "SIGXCPU", 24), 8, "configuration", id="SIGXCPU")]
pytestmark_linux = pytest.mark.skipif(not LINUX, reason="vrais processus et /proc : Linux seulement")


@pytest.fixture()
def rn_json(tmp_path, rn10):
    p = tmp_path / "rn.json"
    p.write_text(json.dumps(cli.to_jsonable(rn10), ensure_ascii=False), encoding="utf-8")
    return str(p)


@pytestmark_linux
@pytest.mark.parametrize("sig, code_attendu, erreur", SIGNAUX)
def test_a_signal_during_the_saved_plan_write_finishes_the_file_then_stops(tmp_path, rn_json, sig, code_attendu, erreur):
    code, d, err = _pendant_l_ecriture(tmp_path, ["plan", "--sans-notes", "--capital", "5M", "--perte-toleree", "1M",
                                                  "--enregistrer"], "plan.json", sig, DOUBLURE_PLAN="1", RN_JSON=rn_json)
    profil = tmp_path / "donnees" / "profil"
    # avant : plan.json jamais écrit (fichier temporaire retiré), 130 ou 8
    assert (profil / "plan.json").is_file(), (code, d, err[-800:])
    pe = json.loads((profil / "plan.json").read_text(encoding="utf-8"))  # complet et valide
    assert pe["capital"] == 5_000_000 and pe["perte_toleree"] == 1_000_000 and pe["bandeau"] == cli.BANNER
    # plan.json précède le calcul : la commande s'arrête ensuite, comme demandé (130, ou 8), un seul objet
    assert code == code_attendu and d["ok"] is False and d["erreur"] == erreur, (code, d)
    assert not (profil / "plan_cache.json").exists() and sorted(x.name for x in profil.iterdir()) == ["plan.json"]


@pytestmark_linux
def test_term_during_the_plan_cache_write_gives_the_screen_and_a_complete_cache(tmp_path, rn_json):
    code, d, err = _pendant_l_ecriture(tmp_path, ["plan", "--sans-notes"], "plan_cache.json", signal.SIGTERM,
                                       DOUBLURE_PLAN="1", RN_JSON=rn_json)
    cache = tmp_path / "donnees" / "profil" / "plan_cache.json"
    assert cache.is_file(), (code, d, err[-800:])  # avant : cache jamais écrit, 130
    c = json.loads(cache.read_text(encoding="utf-8"))
    assert c["bandeau"] == cli.BANNER and c["plan"]["lignes"] and c["capital"] == 10_000_000
    # dernière étape de la commande : le résultat est donné, comme « notes add » (0b26241)
    assert code == 0 and d["ok"] is True and d["plan_cache"] == str(cache), (code, d)
    assert "signal TERM reçu pendant l'écriture du résultat" in err


@pytestmark_linux
def test_term_during_the_grid_write_leaves_a_complete_readable_grid(tmp_path):
    code, d, err = _pendant_l_ecriture(tmp_path, ["plan", "grille", "--courtage", "0,7"], "grille_sgi.yaml",
                                       signal.SIGTERM)
    profil = tmp_path / "donnees" / "profil"
    assert (profil / "grille_sgi.yaml").is_file(), (code, d, err[-800:])  # avant : grille absente, 130
    assert yaml.safe_load((profil / "grille_sgi.yaml").read_text(encoding="utf-8"))["champs"]["courtage"]["valeur"] \
        == 0.007
    assert G.charger(profil).valeur("courtage") == 0.007
    assert code == 0 and d["ok"] is True and d["enregistree"] is True, (code, d)
    assert sorted(x.name for x in profil.iterdir()) == ["grille_sgi.yaml"]  # aucun fichier temporaire laissé


@pytestmark_linux
def test_term_during_the_grid_write_before_a_comparison_finishes_the_file_then_stops(tmp_path):
    code, d, err = _pendant_l_ecriture(tmp_path, ["plan", "grille", "--courtage", "0,7", "--comparer"],
                                       "grille_sgi.yaml", signal.SIGTERM)
    profil = tmp_path / "donnees" / "profil"
    assert G.charger(profil).valeur("courtage") == 0.007, (code, d, err[-800:])
    assert code == 130 and d["erreur"] == "interruption"  # la comparaison (un calcul de l'ordre) n'est pas lancée


@pytestmark_linux
def test_term_during_the_start_of_a_book_writes_mandate_and_deposit_together(tmp_path):
    code, d, err = _pendant_l_ecriture(tmp_path, ["suivi", "demarrer", "--nom", "PLAN", "--capital", "2M"],
                                       "carnet.jsonl", signal.SIGTERM)
    c = CN.ouvrir("PLAN", tmp_path / "donnees" / "suivi", creer=False)
    assert [m["type"] for m in c.mouvements()] == ["mandat", "apport"] and c.verifier()["chaine_ok"]
    # avant : 130 « interruption » alors que le carnet était démarré (une relance aurait dit « déjà démarré »)
    assert code == 0 and d["ok"] is True and [m["type"] for m in d["mouvements"]] == ["mandat", "apport"], (code, d)


@pytestmark_linux
@pytest.mark.parametrize("sig", [signal.SIGTERM, getattr(signal, "SIGXCPU", 24)], ids=["TERM", "SIGXCPU"])
def test_a_signal_during_a_withdrawal_gives_the_true_result_and_one_line(tmp_path, sig):
    c = _carnet(tmp_path / "donnees")
    code, d, err = _pendant_l_ecriture(tmp_path, ["suivi", "saisir", "--nom", "PLAN", "--retrait", "500000"],
                                       "carnet.jsonl", sig)
    assert [m["type"] for m in c.mouvements()] == ["mandat", "apport", "retrait"] and c.verifier()["chaine_ok"]
    # avant : 130 (ou 8) alors que le retrait était inscrit pour toujours
    assert code == 0 and d["ok"] is True and d["mouvement"]["montant"] == 500_000.0, (code, d)
    # Une seconde saisie identique est reconnue comme un doublon : jamais deux retraits.
    p = subprocess.run([sys.executable, "-B", "-m", "brvm_alpha", "suivi", "saisir", "--nom", "PLAN", "--retrait",
                        "500000", "--format", "json"], env=_env(tmp_path), cwd=str(tmp_path), capture_output=True,
                       text=True, timeout=120)
    assert p.returncode == 2 and "double" in json.loads(p.stdout)["message"]
    assert len(c.mouvements(types=("retrait",))) == 1


@pytestmark_linux
def test_term_during_a_review_gives_the_true_result(tmp_path):
    c = _carnet(tmp_path / "donnees")
    code, d, err = _pendant_l_ecriture(tmp_path, ["suivi", "revue", "--nom", "PLAN", "--alerte", "W4", "--decision",
                                                  "garder", "--texte", "réponses écrites"], "carnet.jsonl",
                                       signal.SIGTERM)
    assert [m["type"] for m in c.mouvements()] == ["mandat", "apport", "revue"] and c.verifier()["chaine_ok"]
    assert code == 0 and d["ok"] is True and d["mouvement"]["alerte"] == "W4", (code, d)


@pytestmark_linux
def test_term_during_the_export_gives_a_complete_copy(tmp_path):
    c = _carnet(tmp_path / "donnees")
    dest = tmp_path / "rapports" / "copie_suivi"
    code, d, err = _pendant_l_ecriture(tmp_path, ["suivi", "exporter", "--sortie", str(dest)], "copie_suivi",
                                       signal.SIGTERM)
    assert (dest / "PLAN" / "carnet.jsonl").is_file(), (code, d, err[-800:])  # avant : copie retirée, 130
    assert (dest / "PLAN" / "carnet.jsonl").read_bytes() == c.fichier.read_bytes()
    assert code == 0 and d["ok"] is True and d["fichiers"] == ["PLAN/carnet.jsonl"], (code, d)
    assert not [x for x in dest.parent.iterdir() if x.name.endswith(".part")]


@pytestmark_linux
def test_term_while_waiting_for_the_book_lock_still_stops_at_once(tmp_path):
    # Ce qui ne change pas : avant le point de non-retour (attente du verrou), TERM arrête la commande, rien d'écrit.
    c = _carnet(tmp_path / "donnees")
    brut = c.fichier.read_bytes()
    fd = os.open(c.dossier, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)  # une autre écriture tient le carnet
        p = subprocess.Popen([sys.executable, "-B", "-m", "brvm_alpha", "suivi", "saisir", "--nom", "PLAN", "--apport",
                              "1000", "--format", "json"], env=_env(tmp_path, BRVM_ALPHA_ATTENTE_VERROU="60"),
                             cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        t0, attend = time.monotonic(), False
        while time.monotonic() - t0 < 60 and not attend and p.poll() is None:
            try:
                attend = any(os.readlink(f"/proc/{p.pid}/fd/{x}") == str(c.dossier) for x in os.listdir(f"/proc/{p.pid}/fd"))
            except OSError:
                pass
            time.sleep(0.02)
        assert attend, "la commande n'a pas ouvert le verrou du carnet"
        time.sleep(0.3)
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=60)
    finally:
        os.close(fd)
    assert p.returncode == 130 and json.loads(out)["erreur"] == "interruption", (p.returncode, out, err[-600:])
    assert c.fichier.read_bytes() == brut
