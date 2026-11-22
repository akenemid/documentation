"""F6 — Lectures du risque (cahier ``docs/RENDEMENT_NET.md``, §F6).

L'ordre ne dit plus seulement « 25,6 % de chances de perte ». Le module montre plusieurs lectures du **même**
passé, leur fourchette, et dit qu'il s'agit d'un seul passé (``PH_PASSE``, ``PH_DESCRIPTIF``) :

1. **passé rejoué** (lecture existante de l'ordre, flatteuse : elle est toujours suivie de ``PH_FLATTE``) : blocs
   moyens de 8 semaines ; ajouts : « une année sur vingt » et le pire tirage ;
2. **sensibilité aux blocs** : même calcul avec des blocs de 26 et de 52 semaines ;
3. **marché chargé des mêmes frais** (lecture prudente) : mêmes indices de tirage, rendement hebdomadaire =
   part investie × rendement du Composite TR, mêmes frais déduits ;
4. **périodes réellement observées** : série quotidienne du panier d'aujourd'hui, règle de renormalisation de
   ``recommend.return_distribution`` (une ligne compte à partir de son premier rendement ; 0 % les jours sans cours
   après cotation), fins de mois, périodes de 12 mois nettes des frais.

Chaque lecture bootstrap est calculée pour les graines 0 à 19 : l'affichage prend la médiane des 20 graines ; le
JSON garde aussi la graine 0 (recette, reproductible) et le minimum et le maximum. La lecture 1 à la graine 0 est
identique à la distribution de l'ordre. Ce sont des statistiques descriptives d'un seul passé, pas un test ni une
prévision : aucune règle n'est simulée. Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.rendement.reglages import ESTIMATION, R

__all__ = ["LIBELLE_P_BATTRE_TR", "LecteurPoche", "concentration", "fenetre", "hebdo", "lectures", "periodes_reelles",
           "resume_pour_leviers", "synthese"]

BENCH = "__TR__"
#: Libellé réécrit de « P(battre le TR) » (§F6, point 7) ; la clé JSON ``p_battre_tr`` ne change pas.
LIBELLE_P_BATTRE_TR = ("Fréquence passée au-dessus du marché, aux poids d'aujourd'hui (flatteuse : le test S1 a donné "
                       "−5,6 points par an)")
PHRASE_CHEVAUCHEMENT = "trop peu de périodes qui ne se chevauchent pas pour un chiffre fiable"


# ---------------------------------------------------------------------------
# Données : fenêtre, rendements hebdomadaires
# ---------------------------------------------------------------------------


def fenetre(ordre: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Fenêtre d'estimation de l'ordre (``meta.fenetre_estimation``) ; à défaut la règle de l'outil
    (``recommend.estimation_window``)."""
    o = _rg.en_dict(ordre)
    fe = (o.get("meta") or {}).get("fenetre_estimation") or {}
    if fe.get("debut") and fe.get("fin"):
        return pd.Timestamp(fe["debut"]).normalize(), pd.Timestamp(fe["fin"]).normalize()
    s1 = bool((o.get("distribution") or {}).get("s1_utilise"))
    w = R.estimation_window(o.get("asof"), s1)
    return pd.Timestamp(w["debut"]), pd.Timestamp(w["fin"])


def _poids(o: Mapping[str, Any]) -> dict[str, float]:
    return {str(l["symbole"]): float(l["poids_realise"]) for l in (o.get("lignes") or [])
            if int(l.get("cibles") or 0) > 0 and float(l.get("poids_realise") or 0) > 0}


def _frais_deduits(o: Mapping[str, Any], forfait: float = 0.0) -> float:
    d = o.get("distribution") or {}
    c = o.get("couts") or {}
    nav = float(o.get("valeur_portefeuille") or 0)
    if d.get("frais_deduits") is not None and not forfait:
        return float(d["frais_deduits"])
    fixes = float(c.get("garde_annuelle") or 0) + float(c.get("tenue_compte_annuelle") or 0) + float(forfait or 0)
    return (float(c.get("total") or 0) + fixes) / nav if nav > 0 else 0.0


def hebdo(ordre: Any, panels: Mapping[str, Any], *, symboles: Iterable[str] | None = None) -> pd.DataFrame:
    """Rendements hebdomadaires TR des lignes de l'ordre et du Composite TR (``recommend.weekly_tr_returns``,
    fenêtre de l'ordre)."""
    o = _rg.en_dict(ordre)
    tr = panels.get("tr_index")
    mtr = panels.get("market_tr")
    if not isinstance(tr, pd.DataFrame) or mtr is None:
        raise ValueError("indices TR (tr_index, market_tr) absents des panels")
    a, b = fenetre(o)
    syms = list(symboles) if symboles is not None else [str(l["symbole"]) for l in (o.get("lignes") or [])
                                                        if int(l.get("cibles") or 0) > 0]
    return R.weekly_tr_returns(tr, mtr, syms, a, b)


def rendement_panier(weekly: pd.DataFrame, weights: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray]:
    """Rendement hebdomadaire du panier aux poids fixes et du Composite TR, règle de ``return_distribution`` :
    une ligne pas encore cotée n'est pas comptée à 0 % (poids renormalisés sur les lignes cotées) ; après la
    cotation, une semaine sans cours compte 0 %."""
    w = pd.Series({k: float(v) for k, v in weights.items() if float(v) > 0}, dtype=float)
    data = weekly.loc[weekly[BENCH].notna()]
    sub = data.reindex(columns=list(w.index)).astype(float)
    wv = w.reindex(sub.columns).to_numpy(dtype=float)
    listed = np.zeros(sub.shape, dtype=bool)
    for j, c in enumerate(sub.columns):
        fv = sub[c].first_valid_index()
        if fv is not None:
            listed[:, j] = sub.index >= fv
    w_listed = listed * wv[None, :]
    tot = float(wv.sum())
    act = w_listed.sum(axis=1)
    scale = np.divide(tot, act, out=np.zeros_like(act), where=act > 0)
    rp = (sub.fillna(0.0).to_numpy() * w_listed).sum(axis=1) * scale
    return rp, data[BENCH].astype(float).to_numpy()


def _stats(x: np.ndarray) -> dict[str, float]:
    q = lambda p: float(np.quantile(x, p))  # noqa: E731
    return {"p_perte": float(np.mean(x < 0.0)), "mediane": q(0.5), "p10": q(0.10), "p5": q(0.05), "p90": q(0.90),
            "pire": float(np.min(x))}


def _tirage(rp: np.ndarray, rb: np.ndarray, x: float, drag: float, horizon: int, n_boot: int, bloc: float,
            graine: int) -> tuple[np.ndarray, np.ndarray]:
    idx = R.stationary_bootstrap_indices(len(rp), int(horizon), int(n_boot), float(bloc), int(graine))
    gross = np.prod(1.0 + rp[idx], axis=1) - 1.0
    net = (1.0 + gross) * (1.0 - float(drag)) - 1.0
    marche = np.prod(1.0 + float(x) * rb[idx], axis=1) * (1.0 - float(drag)) - 1.0
    return net, marche


# ---------------------------------------------------------------------------
# Lectures 1 à 3 (bootstrap)
# ---------------------------------------------------------------------------


def lectures(ordre: Any, panels: Mapping[str, Any] | None = None, *, weekly: pd.DataFrame | None = None,
             graines: int | Sequence[int] | None = None, blocs: Sequence[float] | None = None,
             n_boot: int | None = None, horizon_semaines: int = 52, forfait: float = 0.0,
             reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Lectures 1 à 3 du §F6 pour l'ordre affiché : passé rejoué et marché chargé des mêmes frais, blocs de 8, 26 et
    52 semaines, graines 0 à 19 (``risque.graines``), 5 000 tirages chacune.

    Chaque lecture rend ``graine_0``, ``mediane_graines`` et ``min_max_graines`` de : fréquence de perte, année
    ordinaire (médiane), une année sur dix, une année sur vingt, pire tirage."""
    o = _rg.en_dict(ordre)
    wk = weekly if weekly is not None else hebdo(o, panels or {})
    w = _poids(o)
    if not w:
        raise ValueError("aucune ligne détenue après ordres")
    rp, rb = rendement_panier(wk, w)
    if len(rp) < 26:
        raise ValueError(f"historique hebdomadaire trop court ({len(rp)} semaines < 26)")
    drag = _frais_deduits(o, forfait)
    x = float((o.get("couts") or {}).get("investi_pct") or 0.0)
    gs = list(range(int(graines))) if isinstance(graines, int) else (
        list(graines) if graines is not None else list(range(int(_rg.lire(reglages, "risque.graines", 20)))))
    bl = [float(b) for b in (blocs if blocs is not None else _rg.lire(reglages, "risque.blocs_semaines", [8, 26, 52]))]
    nb = int(n_boot if n_boot is not None else _rg.lire(reglages, "risque.tirages", 5000))
    out: list[dict[str, Any]] = []
    for b in bl:
        res: dict[str, list[dict[str, float]]] = {"passe_rejoue": [], "marche_charge": []}
        for g in gs:
            net, mar = _tirage(rp, rb, x, drag, horizon_semaines, nb, b, g)
            res["passe_rejoue"].append(_stats(net))
            res["marche_charge"].append(_stats(mar))
        for fam, nom in (("passe_rejoue", "Passé rejoué"), ("marche_charge", "Marché chargé des mêmes frais")):
            r = res[fam]
            cles = r[0].keys()
            out.append({"nom": f"{nom}, blocs de {int(b)} semaines", "famille": fam, "bloc": b,
                        "flatteuse": fam == "passe_rejoue", "graine_0": r[0] if 0 in gs else None,
                        "mediane_graines": {k: float(np.median([z[k] for z in r])) for k in cles},
                        "min_max_graines": {k: [float(min(z[k] for z in r)), float(max(z[k] for z in r))] for k in cles},
                        "n_graines": len(gs)})
    return {"lectures": out, "frais_deduits": drag, "investi_pct": x, "n_semaines": int(len(rp)),
            "horizon_semaines": int(horizon_semaines), "n_boot": nb, "graines": gs,
            "phrases": [_rg.PH_PASSE, _rg.PH_DESCRIPTIF], "phrase_flatteuse": _rg.PH_FLATTE,
            "libelle_p_battre_tr": LIBELLE_P_BATTRE_TR, "statut": ESTIMATION}


class LecteurPoche:
    """Année ordinaire et fréquence de perte d'un montant en actions (§F4, étape 7) : blocs de 8 semaines,
    graine 0, 5 000 tirages ; lecture prudente (marché chargé des mêmes frais) et lecture flatteuse (passé rejoué,
    au détail seulement)."""

    def __init__(self, weekly: pd.DataFrame, *, bloc: float = 8.0, graine: int = 0, n_boot: int = 5000,
                 horizon: int = 52) -> None:
        self.weekly = weekly
        self.rb = weekly.loc[weekly[BENCH].notna(), BENCH].astype(float).to_numpy()
        self.idx = R.stationary_bootstrap_indices(len(self.rb), int(horizon), int(n_boot), float(bloc), int(graine))
        self.bloc, self.graine, self.n_boot, self.horizon = float(bloc), int(graine), int(n_boot), int(horizon)

    def poche(self, pp: Mapping[str, Any]) -> dict[str, Any]:
        A = float(pp["A"])
        if A <= 0:
            raise ValueError("montant en actions nul")
        drag = (float(pp["frais_achat"]) + float(pp["frais_annuels"])) / A
        x = float(pp["investi"]) / A
        rp, _rb = rendement_panier(self.weekly, pp["poids"])
        net = (np.prod(1.0 + rp[self.idx], axis=1)) * (1.0 - drag) - 1.0
        mar = np.prod(1.0 + x * self.rb[self.idx], axis=1) * (1.0 - drag) - 1.0
        return {"mediane_prudente_fcfa": A * float(np.median(mar)), "mediane_flatteuse_fcfa": A * float(np.median(net)),
                "p10_prudente_fcfa": A * float(np.quantile(mar, 0.10)), "p10_flatteuse_fcfa": A * float(np.quantile(net, 0.10)),
                "p_perte_prudente": float(np.mean(mar < 0)), "p_perte_flatteuse": float(np.mean(net < 0))}


# ---------------------------------------------------------------------------
# Lecture 4 : périodes réellement observées
# ---------------------------------------------------------------------------


def niveau_quotidien(tr_index: pd.DataFrame, weights: Mapping[str, float], debut: Any, fin: Any) -> pd.Series:
    """Niveau quotidien du panier aux poids fixes (règle de renormalisation de ``return_distribution`` à la
    journée) : une ligne compte à partir de son **premier rendement** (le lendemain de sa première cote) ; 0 % les
    jours sans cours après cotation ; poids renormalisés sur les lignes qui comptent."""
    a, b = pd.Timestamp(debut).normalize(), pd.Timestamp(fin).normalize()
    w = pd.Series({k: float(v) for k, v in weights.items() if float(v) > 0}, dtype=float)
    cols = [c for c in w.index if c in tr_index.columns]
    if not cols:
        raise ValueError("aucune ligne du panier dans les indices TR")
    fr = tr_index.loc[(tr_index.index >= a) & (tr_index.index <= b)].reindex(columns=cols).astype(float)
    fr = fr.where(np.isfinite(fr) & (fr > 0))
    ret = fr.ffill().pct_change(fill_method=None)
    wv = w.reindex(cols)
    listed = pd.DataFrame({c: fr.index >= (ret[c].first_valid_index() or (fr.index[-1] + pd.Timedelta(days=1)))
                           for c in cols}, index=fr.index)
    num = (ret.fillna(0.0) * listed * wv).sum(axis=1)
    act = (listed * wv).sum(axis=1)
    rp = (num * (float(wv.sum()) / act.where(act > 0))).fillna(0.0)
    return (1.0 + rp).cumprod()


def periodes_reelles(ordre: Any, panels: Mapping[str, Any] | None = None, *, horizons: Sequence[int] = (12, 24, 36),
                     niveau: pd.Series | None = None, forfait: float = 0.0) -> dict[str, Any]:
    """Périodes de 12, 24 et 36 mois réellement observées, nettes des frais (entrée + frais annuels × durée) :
    ``m_{i+H} ÷ m_i × (1 − frais) − 1`` sur les dernières séances de chaque mois.

    À 12 mois : nombre de périodes, nombre en perte, niveau dépassé neuf fois sur dix, pire période, répartition des
    périodes en perte par année de départ. À 24 et 36 mois (règle fixe, §F14) : nombre et pire période seulement,
    aucune fréquence. Moins de 24 mois d'historique : pas de périodes réelles."""
    o = _rg.en_dict(ordre)
    w = _poids(o)
    a, b = fenetre(o)
    if niveau is None:
        tr = (panels or {}).get("tr_index")
        if not isinstance(tr, pd.DataFrame):
            raise ValueError("indices TR (tr_index) absents des panels")
        niveau = niveau_quotidien(tr, w, a, b)
    me = niveau.groupby(niveau.index.to_period("M")).last()
    if len(me) < 25:
        return {"disponible": False, "motif": "moins de 24 mois d'historique : pas de périodes réelles",
                "n_fins_de_mois": int(len(me))}
    c = o.get("couts") or {}
    K = float(o.get("valeur_portefeuille") or o.get("capital") or 0)
    fixes = float(c.get("garde_annuelle") or 0) + float(c.get("tenue_compte_annuelle") or 0) + float(forfait or 0)
    out: dict[str, Any] = {"disponible": True, "n_fins_de_mois": int(len(me)), "premier_mois": str(me.index[0]),
                           "dernier_mois": str(me.index[-1]), "phrases": [_rg.PH_PASSE, _rg.PH_DESCRIPTIF],
                           "statut": ESTIMATION, "horizons": {}}
    for H in horizons:
        drag = (float(c.get("total") or 0) + fixes * H / 12.0) / K if K > 0 else 0.0
        r = (me.shift(-int(H)) / me * (1.0 - drag) - 1.0).dropna()
        if not len(r):
            out["horizons"][str(H)] = {"n": 0}
            continue
        d: dict[str, Any] = {"n": int(len(r)), "pire": float(r.min()), "pire_depart": str(r.idxmin()), "frais_deduits": drag}
        if int(H) == 12:
            neg = r[r < 0]
            d.update({"n_perte": int(len(neg)), "part_perte": float(len(neg) / len(r)), "p10": float(r.quantile(0.10)),
                      "par_annee": {str(k): int(v) for k, v in neg.groupby(neg.index.year).size().items()},
                      "proches_de_zero": {str(k): float(x) for k, x in r.items() if abs(x) < 0.005}})
        else:
            d["phrase"] = PHRASE_CHEVAUCHEMENT
        out["horizons"][str(H)] = d
    return out


# ---------------------------------------------------------------------------
# Synthèse, concentration
# ---------------------------------------------------------------------------


def _pts(x: float) -> int:
    return int(math.floor(100.0 * float(x) + 0.5))


def synthese(lec: Mapping[str, Any] | None, per: Mapping[str, Any] | None) -> dict[str, Any]:
    """Phrase de synthèse (§F6, point 5) : ``PH_PASSE``, ``PH_DESCRIPTIF``, puis « Selon la façon de compter et le
    tirage, environ {min} % à {max} % des périodes de 12 mois ont fini en perte, et une année sur dix a fini sous
    {haut} % à {bas} %. » Bornes : minimum et maximum des lectures 1 à 4 (médianes des 20 graines pour 1 à 3),
    arrondies au point entier."""
    freq: list[float] = []
    dix: list[float] = []
    for l in (lec or {}).get("lectures") or []:
        m = l.get("mediane_graines") or {}
        if m.get("p_perte") is not None:
            freq.append(float(m["p_perte"]))
        if m.get("p10") is not None:
            dix.append(float(m["p10"]))
    h12 = ((per or {}).get("horizons") or {}).get("12") or {}
    if h12.get("part_perte") is not None:
        freq.append(float(h12["part_perte"]))
    if h12.get("p10") is not None:
        dix.append(float(h12["p10"]))
    if not freq:
        return {"phrase": None, "phrases": [_rg.PH_PASSE, _rg.PH_DESCRIPTIF]}
    fmin, fmax = _pts(min(freq)), _pts(max(freq))
    haut, bas = _pts(max(dix)) if dix else None, _pts(min(dix)) if dix else None
    ph = f"Selon la façon de compter et le tirage, environ {fmin} % à {fmax} % des périodes de 12 mois ont fini en perte"
    if dix:
        ph += f", et une année sur dix a fini sous {_rg.fcfa(haut, unite=False)} % à {_rg.fcfa(bas, unite=False)} %"
    ph += "."
    return {"phrase": ph, "frequence_min": fmin, "frequence_max": fmax, "une_sur_dix_haut": haut, "une_sur_dix_bas": bas,
            "phrases": [_rg.PH_PASSE, _rg.PH_DESCRIPTIF]}


def resume_pour_leviers(lec: Mapping[str, Any] | None, per: Mapping[str, Any] | None) -> dict[str, float | None]:
    """Rendements utilisés par le tableau B des leviers (graine 0, blocs de 8 semaines ; périodes réelles)."""
    out: dict[str, float | None] = {"ordinaire_prudente": None, "ordinaire_flatteuse": None, "une_sur_dix_flatteuse": None,
                                    "une_sur_dix_prudente": None, "une_sur_dix_periodes": None}
    for l in (lec or {}).get("lectures") or []:
        if float(l.get("bloc") or 0) != 8.0 or not l.get("graine_0"):
            continue
        g0 = l["graine_0"]
        if l["famille"] == "passe_rejoue":
            out["ordinaire_flatteuse"], out["une_sur_dix_flatteuse"] = g0["mediane"], g0["p10"]
        else:
            out["ordinaire_prudente"], out["une_sur_dix_prudente"] = g0["mediane"], g0["p10"]
    h12 = ((per or {}).get("horizons") or {}).get("12") or {}
    out["une_sur_dix_periodes"] = h12.get("p10")
    return out


def concentration(ordre: Any, X: float | None = None, *, reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Concentration (§F6, point 6) : pour les deux premières lignes et toute ligne de plus de 5 %, perte d'un choc
    de 30 % sur la ligne (en FCFA, en % du capital total, en part de X) ; poids cumulé des deux premières lignes ;
    lignes effectives = 1 ÷ Σ (v_i ÷ investi)²."""
    o = _rg.en_dict(ordre)
    choc = float(_rg.lire(reglages, "risque.choc_titre", 0.30))
    seuil = float(_rg.lire(reglages, "risque.seuil_concentration", 0.05))
    V = float(o.get("valeur_portefeuille") or o.get("capital") or 0)
    K = float(o.get("capital") or V)
    L = sorted([l for l in (o.get("lignes") or []) if int(l.get("cibles") or 0) > 0],
               key=lambda l: -float(l.get("valeur_apres") or 0))
    inv = sum(float(l.get("valeur_apres") or 0) for l in L)
    rows = []
    for i, l in enumerate(L):
        v = float(l.get("valeur_apres") or 0)
        if i < 2 or (V > 0 and v / V > seuil):
            perte = int(R.round_fcfa(choc * v))
            rows.append({"symbole": l["symbole"], "nom": l.get("nom") or l["symbole"], "valeur": int(R.round_fcfa(v)),
                         "poids": v / V if V else None, "perte_choc": perte, "pct_capital": perte / K if K else None,
                         "part_de_X": (perte / float(X)) if X else None})
    top2 = sum(float(l.get("valeur_apres") or 0) for l in L[:2])
    eff = 1.0 / sum((float(l.get("valeur_apres") or 0) / inv) ** 2 for l in L) if inv > 0 else None
    return {"lignes": rows, "poids_deux_premieres": top2 / V if V else None, "lignes_effectives": eff, "choc": choc,
            "statut": ESTIMATION}
