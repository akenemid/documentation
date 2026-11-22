"""Tests des scénarios de stress du §9.3 (``brvm_alpha.portfolio.stress``).

Données **synthétiques** (``test_strategy_alpha.make_panels``, séances 2023-2024 de S0) ; aucune
donnée de l'échantillon vierge S1 n'est lue (le bêta s'arrête au début de S0). Aucune requête
réseau.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from test_strategy_alpha import SYMS, make_panels

from brvm_alpha import reference
from brvm_alpha.portfolio.stress import STRESS_DEFAULTS, portfolio_beta, stress_tests

SYMS_ST = SYMS[:20] + ["SNTS"]
K = 10_000_000.0


@pytest.fixture(scope="module")
def panels() -> dict:
    return make_panels(symbols=SYMS_ST)


def _weights(names: list[str]) -> pd.Series:
    return pd.Series(0.98 / len(names), index=names)


def _run(w, panels, t, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return stress_tests(w, panels, t, K, **kw)


def test_all_scenarios_present_signed_and_scaled(panels):
    t = panels["close"].index[-1]
    names = ["SNTS", "BOAS", "BOABF", "BOAM", "ORAC", "SGBC", "CBIBF", "ETIT"]
    w = _weights(names)
    df = _run(w, panels, t)
    assert set(df["code"]) == {f"ST{i}" for i in range(1, 11)}
    assert (df["perte_fcfa"] <= 0).all() and (df["perte_pct"] <= 0).all()
    assert df["perte_pct"].to_numpy() == pytest.approx(df["perte_fcfa"].to_numpy() / K, abs=1e-6)
    beta = df.attrs["beta"]
    lo, hi = STRESS_DEFAULTS["beta_bounds"]
    assert lo <= beta <= hi and df.attrs["investi_fcfa"] == pytest.approx(0.98 * K)
    st3 = df.loc[df["code"] == "ST3", "perte_fcfa"].iloc[0]
    assert st3 == pytest.approx(-beta * 0.15 * 0.98 * K, abs=1.0)
    st1 = df[(df["code"] == "ST1") & (df["variante"] == "TR")]["perte_fcfa"].iloc[0]
    assert st1 == pytest.approx(-beta * 0.467 * 0.98 * K, abs=1.0)
    # ST4 : exposition λ AES (BOABF, BOAM au siège ; SNTS par sa filiale malienne)
    lam = {s: sum(v for c, v in reference.economic_exposure(s).items() if c in reference.AES_COUNTRIES) for s in names}
    v_aes = sum(w[s] * K * lam[s] for s in names)
    assert lam["SNTS"] == pytest.approx(0.238) and lam["BOAM"] == 1.0 and lam["ORAC"] == 0.0
    sev = df[(df["code"] == "ST4") & (df["variante"] == "sévère 21 %")]["perte_fcfa"].iloc[0]
    assert sev == pytest.approx(-0.21 * v_aes, abs=1.0)
    stress = df[(df["code"] == "ST4") & df["variante"].str.startswith("stress 26")]["perte_fcfa"].iloc[0]
    assert stress == pytest.approx(-0.26 * v_aes, abs=1.0)
    # ST5 : −26 % sur BOAS et SNTS ; −9 % sur les titres sénégalais
    st5 = df[(df["code"] == "ST5") & (df["variante"] == "stress −26 %")]["perte_fcfa"].iloc[0]
    assert st5 == pytest.approx(-0.26 * (w["BOAS"] + w["SNTS"]) * K, abs=1.0)
    # ST8 : la plus grosse ligne, −10 % puis −30 %
    st8 = df[df["code"] == "ST8"].set_index("variante")["perte_fcfa"]
    assert st8["−10 %"] == pytest.approx(-0.10 * w.max() * K, abs=1.0)
    assert st8["−30 %"] == pytest.approx(-0.30 * w.max() * K, abs=1.0)
    # ST6 et ST7 : coûts au moins égaux aux frais proportionnels du §7.2 (1,244 % par aller au central)
    st6 = -df.loc[df["code"] == "ST6", "perte_fcfa"].iloc[0]
    assert st6 >= 0.01244 * 0.98 * K * 0.5  # au moins la moitié vendable en 20 séances dans ce panel
    st7 = -df.loc[df["code"] == "ST7", "perte_fcfa"].iloc[0]
    assert st7 > 12 * 2 * 0.15 * 0.98 * K * 0.0207  # rotation 15 %/mois, frais sévères proportionnels
    assert "Aucun gain n'est garanti" in df.attrs["bandeau"]


def test_split_error_is_blocked_by_the_data_guard(panels):
    t = panels["close"].index[-1]
    df = _run(_weights(["SNTS", "SGBC", "ORAC"]), panels, t)
    st9 = df[df["code"] == "ST9"].iloc[0]
    assert st9["nature"] == "contrôle" and st9["perte_fcfa"] == 0 and "BLOQUANT" in st9["hypothese"]
    assert df.attrs["controle_split_bloquant"] is True


def test_beta_never_reads_s1_and_defaults_to_one(panels):
    # 20 semaines de S0 seulement avant la date : moins de 52 semaines -> β = 1 (hypothèse)
    t = panels["close"].index[100]
    b, note, n = portfolio_beta(_weights(["SGBC", "ORAC"]), panels, t)
    assert b == 1.0 and "supposé" in note and n < 52
    # panel décalé dans S1 (dates fictives) : la fenêtre commence au début de S0, aucune semaine lue
    shifted = {k: (v.set_axis(v.index - pd.DateOffset(years=3)) if isinstance(v, (pd.DataFrame, pd.Series))
                   and isinstance(v.index, pd.DatetimeIndex) else v) for k, v in panels.items()}
    t1 = shifted["close"].index[-1]
    assert t1 < pd.Timestamp("2022-11-17")
    b1, note1, n1 = portfolio_beta(_weights(["SGBC", "ORAC"]), shifted, t1)
    assert b1 == 1.0 and n1 == 0


def test_parameters_override_and_unknown_key(panels):
    t = panels["close"].index[-1]
    w = _weights(["SGBC", "ORAC"])
    base = _run(w, panels, t)
    harder = _run(w, panels, t, params={"drop_8_weeks": 0.30})
    b3 = base.loc[base["code"] == "ST3", "perte_fcfa"].iloc[0]
    h3 = harder.loc[harder["code"] == "ST3", "perte_fcfa"].iloc[0]
    assert h3 == pytest.approx(2.0 * b3, rel=1e-6)
    with pytest.raises(KeyError, match="inconnu"):
        _run(w, panels, t, params={"choc_inconnu": 1.0})
    with pytest.raises(ValueError):
        stress_tests(w, panels, t, 0.0)


def test_empty_portfolio_has_no_loss(panels):
    df = _run(pd.Series(dtype=float), panels, panels["close"].index[-1])
    assert (df["perte_fcfa"] == 0).all() and np.isfinite(df["perte_pct"]).all()


def test_order_of_battle_discovers_the_stress_module(panels):
    # L'ordre de bataille (``portfolio.recommend``) découvre ``stress_tests`` par son nom et ses arguments.
    recommend = pytest.importorskip("brvm_alpha.portfolio.recommend")
    ext = getattr(recommend, "_external_stress", None)
    if ext is None:
        pytest.skip("ordre de bataille sans découverte du module de stress")
    t = panels["close"].index[-1]
    w = _weights(["SGBC", "ORAC", "SNTS"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rows, src = ext((w * K).to_dict(), w.to_dict(), panels, t, K)
    assert rows is not None and src == "brvm_alpha.portfolio.stress.stress_tests"
    assert {r["code"] for r in rows} >= {"ST1", "ST3", "ST4", "ST8"}
    assert all({"code", "scenario", "perte_fcfa", "perte_pct", "hypothese", "base"} <= set(r) for r in rows)
