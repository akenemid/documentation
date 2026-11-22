# BRVM Alpha — Architecture et contrats de modules

Ce document est le contrat commun à tous les modules. Toute fonction publique
listée ici doit exister avec cette signature (des arguments optionnels peuvent
être ajoutés). Code en Python 3.11+, commentaires et docstrings en français.

## Arborescence

Arborescence réelle au 22/11/2026 (`data/`, les caches et `reports/*.html` ne sont pas suivis par git).

```
brvm-alpha/
  README.md                # présentation, installation, commandes, méthode, résultat de S1, limites
  .gitignore               # data/, caches, reports/*.html
  configs/
    strategy_v1.yaml       # paramètres FIGÉS de la stratégie v1 (version 1.1 du YAML, additif v1.1)
  brvm_alpha/
    __init__.py            # version du paquet
    __main__.py            # python -m brvm_alpha
    cli.py                 # update, panel, live, notes, indices, universe, explain, backtest,
                           # validate, recommend, report, serve (S1 refusé pour tout signal)
    config.py              # paramètres (frais, taxes, contraintes) — dataclasses
    settings.py            # lecture et contrôle de configs/strategy_v1.yaml, empreinte de configuration
    reference.py           # métadonnées des titres : pays, secteur, fiscalité, événements pays (D10)
    data/
      boc_download.py      # téléchargement poli des BOC (PDF -> texte .txt.gz) : robots.txt, ≥ 10 s, arrêt 403/429
      boc_parser.py        # extraction d'un BOC -> BocDay
      store.py             # panel parquet + ajustements (splits, total return, calendrier des séances)
      live.py              # cours du jour depuis www.brvm.org (page publique)
    notes/                 # notes de l'analyste (voir la section dédiée plus bas)
      model.py  store.py  entities.py  lexicon.py  analyze.py  research.py  signals.py  index_eval.py
    quant/
      features.py          # caractéristiques par titre et par date (fenêtres en séances, D1)
      scoring.py           # normalisation transversale, composites, IC
      stats.py             # métriques, PSR/DSR, PBO, bootstrap, bêta de Dimson
      regime.py            # régime de marché (tendance / volatilité)
      macro.py             # grandeurs macro et de marché : taux de référence, bandes de prix, règlement J+2
    portfolio/
      risk.py              # covariance (Ledoit-Wolf), HRP
      construct.py         # optimisation sous contraintes, plafonds, indice discipliné (D8), cœur-satellite (D9)
      recommend.py         # ordre de bataille : titres, prix limites, coûts au franc, exécution, revenus
      stress.py            # scénarios de stress ST1-ST10 du §9.3 (stress_tests)
    backtest/
      engine.py            # moteur de backtest quotidien réaliste
      metrics.py           # mesures hebdomadaires de validation (§8.2), fenêtre t0 (D2), IC mensuel
      walkforward.py       # validation walk-forward / CSCV, registre des essais, statut §8.3
    validation/            # exécuteur du test unique S1 et du diagnostic S0 (additif v1.1, D12)
      runner.py            # run_validation, plan des 30 runs, métriques, registre, sorties
      lock.py              # verrou S1 (arbre git = HEAD, refus de relance, lock.json)
      benchmarks.py        # étalons : Composite TR, EW des éligibles de A, prix, BRVM 10/30/Prestige
      controls.py          # contrôles comptables et d'exécution de chaque run (cash, identités, bornes, coûts)
      report_md.py         # rapport resultats.md en français
    strategy/
      alpha.py             # le modèle BRVM Alpha (signaux de la spécification, variantes A-I et REF)
    report/                # rapport final (build_report)
      html.py              # rapport HTML autonome : 11 sections, SVG inline, thème clair/sombre
    ui/                    # interface web locale (python -m brvm_alpha serve), 127.0.0.1 uniquement
      server.py            # ThreadingHTTPServer, sécurité (CSRF, Host, corps), services, fil de travail
      pages.py             # pages HTML en français (styles et script en ligne, thème clair/sombre)
  tests/                   # pytest, hors ligne : données synthétiques ou S0, fixtures BOC et pages brvm.org
    conftest.py
    fixtures/              # extraits de BOC (.txt.gz), pages HTML de brvm.org (.html.gz) pour les tests hors ligne
    test_*.py              # 35 modules (parseur, panel, signaux, construction, moteur, validation, notes,
                           # ordre de bataille, stress, rapport, CLI, interface, non-régressions des revues)
  docs/
    SPECIFICATION_STRATEGIE.md  # spécification v1 ; §8.4 additif v1.1 (D1-D12, fait foi) ; §8.5 errata (E1-E9)
    ARCHITECTURE.md        # ce document
    annexes-spec/          # calculs reproductibles de la spécification (univ_breadth.py, tr_reconstruction.py)
    research/              # revues vérifiées 01 à 08 et annexes du document 07 (données, scripts)
  reports/
    validation_S1/         # test unique S1 : lock.json, metrics.json, resultats.md, tentatives.md, run.log,
                           # nav/trades/weekly_returns.parquet ; precedent_<horodatage>/ = premier run (D12)
    diagnostic_S0/         # diagnostic S0 (contaminé, information seulement) ; *_mensuel/ : mode mensuel
    trials.parquet         # registre des essais (N du DSR « registre »)
    ordre_de_bataille_AAAA-MM-JJ*.md   # ordres de bataille publiés (10 M, 1 M, 50 M FCFA)
    rapport_AAAA-MM-JJ.html            # rapport final (non suivi : régénérable)
  data/                    # NON suivi : boc_text/ (BOC .txt.gz), panel/ (*.parquet, _cache/), notes/ (journal)
```

## Schéma des données (sortie de `data/store.py`)

`equities.parquet` : une ligne par (date, symbol).

| colonne | type | sens |
|---|---|---|
| date | datetime64 | séance |
| symbol | str | code BRVM (SNTS, ORAC…) |
| name | str | libellé |
| sector | str | code secteur du BOC (FIN, TEL, CB, ENE, IND, SPU, CD…) |
| compartment | str | PRESTIGE / PRINCIPAL / secteur historique |
| prev_close | float | cours précédent |
| open, close | float | ouverture / clôture (close renseigné même si non échangé) |
| change_pct | float | variation du jour en % |
| volume | float | titres échangés (0 si non échangé) |
| value | float | valeur échangée en FCFA |
| ref_price | float | cours de référence |
| ytd_pct | float | variation depuis le début de l'année en % |
| last_div_net | float | dernier dividende net payé (FCFA) |
| last_div_date | datetime64 | date de paiement du dernier dividende |
| net_yield_pct | float | rendement net en % |
| per | float | PER |
| status | str | traded / not_traded / suspended |
| session_no | int | numéro global de séance (calendrier des BOC, séances manquantes comprises) |

`sessions.parquet` (`store.load_sessions`) : calendrier **contigu** des séances, une
ligne par numéro de BOC (« N° 186 », remis à 1 chaque année), bulletin disponible ou
non : `session_no, year, issue_no, date, available, source_file, missing_before,
gap_start, gap_end, estimated, marker`. 129 séances réelles de 2017-2026 n'ont pas de
BOC téléchargeable (96 en 2021, ex. N° 89-120 du 07/05 au 24/06/2021) : entre deux
lignes d'un titre, `session_no[t] - session_no[t-1] - 1` séances manquent et le
rendement couvre plusieurs séances. La table des rendements (`adjusted_table`) porte
cette valeur dans `missing_sessions`.

`indices.parquet` : (date, index, level, change_pct, ytd_pct).
`corporate_actions.parquet` : (date, symbol, kind, ratio).
`store.adjusted_prices(equities, corporate_actions)` renvoie un DataFrame large
(date × symbol) de cours ajustés des splits, et `store.total_return_index(...)`
un indice de rendement total par titre (dividendes nets réinvestis).

## Conventions transverses

- **Pas de biais d'anticipation** : toute caractéristique calculée à la date t
  n'utilise que des informations publiées au plus tard en t. L'exécution a lieu
  au plus tôt en t+1.
- Panels « larges » : `DataFrame` indexé par date (DatetimeIndex trié), une
  colonne par symbole.
- Rendements simples en décimal (0,01 = 1 %), sauf colonnes `_pct` du BOC.
- Annualisation : 252 séances.
- Monnaie : FCFA (XOF).
- Aucune fonction ne doit écrire hors de `data/` ou `reports/` sauf demande.

## Contrats des modules

### `quant/stats.py`
- `perf_summary(returns: pd.Series, benchmark: pd.Series | None = None, rf: float = 0.0) -> dict`
  (CAGR, vol, Sharpe, Sortino, max drawdown, Calmar, hit rate, bêta, alpha,
  tracking error, information ratio, skew, kurtosis)
- `probabilistic_sharpe(returns, sr_benchmark=0.0) -> float`
- `deflated_sharpe(returns, n_trials: int, sr_variance: float) -> float`
- `min_track_record_length(returns, sr_benchmark=0.0, alpha=0.05) -> float`
- `lo_adjusted_sharpe(returns, q: int = 5) -> float`
- `stationary_bootstrap(returns, stat_fn, n_boot=2000, mean_block=20, seed=0) -> np.ndarray`
- `pbo_cscv(perf_matrix: pd.DataFrame, n_splits: int = 16) -> dict` (matrice T×N
  rendements de N configurations)
- `dimson_beta(asset, market, lags: int = 2) -> float`
- `newey_west_tstat(series, lags=None) -> float`
- `haircut_sharpe(sr_annual, n_obs, n_tests, method="holm") -> float`

### `quant/features.py`
Fonctions pures `f(panel_dict) -> pd.DataFrame` (date × symbol), à partir d'un
dictionnaire de panels larges : `close_adj`, `tr_index`, `volume`, `value`,
`status`, `net_yield_pct`, `per`, `last_div_net`, `last_div_date`, `ref_price`.
Additif v1.1 (D1) : `mom_sessions`, `lowvol`, `vol_scaling`, `crash_filter` acceptent la base
« sessions » (`session_no`) avec seuils au prorata (`prorata_min_obs`, `missing_sessions_in_window`,
planchers `SIGNAL_MIN_OBS_FLOOR = 40`, `FILTER_MIN_OBS_FLOOR = 20`) et bornes de rendement à
`MAX_BOUND_STALE_SESSIONS = 5` séances au plus.

### `quant/scoring.py`
- `cross_sectional_zscore(df, winsor=3.0, method="rank_gauss")`
- `neutralize(df, groups: pd.Series)` (sectorielle / pays)
- `combine(signals: dict[str, DataFrame], weights: dict[str, float])`
- `information_coefficient(signal, fwd_returns, method="spearman") -> pd.Series`
- `quantile_returns(signal, fwd_returns, n=5) -> pd.DataFrame`
- `shrunk_ic_weights(ic_history: DataFrame, prior: dict, shrinkage: float)`

### `portfolio/risk.py`
- `ledoit_wolf_cov(returns: DataFrame) -> DataFrame`
- `hrp_weights(cov: DataFrame) -> pd.Series`

### `portfolio/construct.py`
- `build_portfolio(alpha: pd.Series, cov: DataFrame, constraints: Constraints,
  liquidity: pd.Series | None, prev_weights: pd.Series | None) -> pd.Series`
  (optionnels : `group_caps: list[GroupCap]`, `hrp_distance_of_distances`)
- `to_lots(weights, prices, capital) -> pd.Series` (nombre entier de titres)

Construction v1 (SPECIFICATION_STRATEGIE.md §4.2, §6, §9.1 ; défauts =
`PORTFOLIO_V1_DEFAULTS`, surcharges par dict plat ou dict du YAML de stratégie) :
- `n_holdings(n_eligible) -> int` (`clip(round(N/3), 12, 20)` ; N si N < 15, mode repli)
- `select_with_band(scores, held, eligible, n_target, entry_pct=0.30, exit_pct=0.50) -> BandSelection`
- `line_caps(symbols, country, liquidity_tier_flags, spread_flags, risk_flags, base=0.10, multipliers=None) -> pd.Series`
- `sector_caps(sectors)`, `country_caps(countries, reference=None)`,
  `aes_caps(countries, seat_reference=..., lambda_reference=...) -> list[GroupCap]`
- `equal_weight_with_caps(selected, upper, groups, investable=0.98) -> pd.Series`
  (projection exacte ; `attrs["feasible_full_budget"]`)
- `target_portfolio(scores, eligible, held_weights, context, params) -> (pd.Series, dict)`
  (`params["weighting"]` : `"equal"` (A), `"hrp_tilt"` (G), `"mv_alpha"` (H))
- `weekly_covariance(returns, asof)` (Ledoit-Wolf, W-FRI, 104 semaines, min 52, plancher 0,5)
- Additif v1.1 : `disciplined_index_portfolio(capitalisation, eligible, context, params, index_params)`
  et `disciplined_index_constraints(...)` (D8, `DISCIPLINED_INDEX_V11`) ;
  `core_satellite_weights(core, satellite, upper, groups, core_share=0.5)` (D9) ; paramètre
  `capacity_cap_per_name="budget/n_target"` et `capacity_beyond_exit=True` (D4).

### `portfolio/stress.py` (scénarios du §9.3)
- `stress_tests(weights, panels, asof, capital, params=None) -> DataFrame` : une ligne par scénario
  ST1-ST10 (et par variante) : `code`, `variante`, `scenario`, `perte_fcfa` (variation de valeur,
  **négative = perte**), `perte_pct` (fraction du capital), `hypothese`, `base`, `nature`
  (`estimation` / `contrôle`) ; `attrs` : `beta`, `beta_note`, `investi_fcfa`, `bandeau`. Marché (ST1-ST3) :
  β hebdomadaire du panier contre le Composite TR (104 semaines au plus, 52 au moins, jamais avant le début
  de S0, borné à [0,5 ; 1,5], 1 à défaut) × chocs mesurés de la spécification (aucun rejeu des titres sur
  S1) ; pays (ST4, ST5, ST10) : exposition λ (`reference.economic_exposure`), sévère 21 %, stress 26 %,
  modéré 8 % ; ST6 : liquidation en 20 séances à 5 % de la MDV63, demi-spread × 2 ; ST7 : coûts sévères du
  §7.2 sur 12 mois (rotation 15 %/mois, hypothèse) ; ST8 : plus grosse ligne −10 % / −30 % ; ST9 : division
  non ajustée injectée, le contrôle `data_guard` de la stratégie doit bloquer. `STRESS_DEFAULTS`,
  `portfolio_beta(weights, panels, asof)`. Découvert par l'ordre de bataille (`recommend`).

### `portfolio/recommend.py` (ordre de bataille)
- `recommend(asof, capital, *, panels=None, holdings=None, cash=None, variant=None, costs="central",
  notes_store=None, validation_dir="reports/validation_S1", horizon_months=12, n_boot=5000, seed=0,
  registry_path=None, panel_dir=None, sessions=None, tolerance=0.01, max_participation=0.10,
  mean_block_weeks=8, comparison=True, explanations=True, index_evaluation=True, today=None,
  notes_known_at=None) -> OrdreDeBataille`
  (`notes_known_at` : instant de connaissance des notes ; `None` (défaut sûr) = **mode historique**, règle
  stricte à la date de décision ; donné = **mode direct**, notes connues à cet instant appliquées à la séance
  d'exécution, voir « Deux instants » du module des notes ; `declencheurs["notes"]` porte alors `ligne`
  (« Notes connues au …, appliquées à la séance du … : N en vigueur (dont M manuelles), F filtre(s) de risque
  actif(s) »), `mode`, `connues_au`, `seance_application`, `filtres`, `blocages` (titre, règle, note — date,
  titre, source, adresse —, fin du blocage, `lever` : archiver la note) et `effet` (poids cibles sans et avec
  les notes, même décision recalculée sans aucune note : montre si le poids d'un titre bloqué est redistribué
  ou laissé en liquidités par les règles de construction, inchangées ; `motif` d'une ligne : filtre ou
  inclinaison qui agit sur ce titre, vide si l'écart vient de la redistribution — en indice discipliné
  (REF), seul un filtre qui **bloque les achats** est un motif : un filtre de surveillance comme R10 n'y
  change aucun poids) ; un achat bloqué qui change l'ordre ajoute un avertissement « ACHAT BLOQUÉ par une
  note » ; `declencheurs["indices"]` : une ligne par indice (`indice`, `libelle`, `position`, `confiance`,
  `score`, `lecture`, `position_sans_notes`, `score_sans_notes`, `position_changee_par_les_notes`) ; quand la
  position ne change que par la composante « notes », le tableau écrit « NEUTRE (sans les notes :
  SOUS-PONDÉRER) », la lecture reprend la raison « Effet des notes » et un paragraphe « Position fragile »
  suit (affichage seul : aucune pondération n'est modifiée) ; `explications` : en indice discipliné, un titre
  que sa capitalisation ferait retenir mais dont l'achat est bloqué est expliqué « achat bloqué par un filtre
  de risque, titre non détenu écarté de la sélection (D8) », et non « hors des 20 plus grosses » ;
  `holdings` : symbole → nombre de titres ; un titre connu du panel mais absent du BOC à t est gardé
  « bloqué, hors BOC », valorisé au dernier cours − 10 % (§7.1.7), seuls les symboles jamais vus sont refusés ;
  `cash=None` : `capital − titres détenus` ; `notes_store=None` : journal du dépôt, `False` : aucune note ;
  `today` : contrôle de fraîcheur du panel (défaut : date système si le panel est lu sur disque) : séances
  attendues manquantes avant `today` (`expected_missing_sessions`) ⇒ avertissement « PANEL EN RETARD » en tête,
  `execution["perime"]`, aucune séance d'exécution avant `today`). Distribution : lignes pas encore cotées
  renormalisées (et non comptées à 0 %), `biais_retrospectif` (fenêtre 2017-2026) et `resultat_s1` (actif de la
  variante appliquée lu dans `metrics.json`, affiché à côté de P(battre le TR)) ; avertissement de capital
  insuffisant (investi < cible − 10 points, lignes < cible, frais fixes > 1 %/an) ; lignes recalculées sur les
  tranches effectivement planifiées ; messages du modèle affichés (Markdown, HTML, rapport). Export : `from brvm_alpha.portfolio
  import recommend` donne le sous-module, **appelable** comme la fonction ; alias `ordre_de_bataille`.
- `OrdreDeBataille` (dataclass) : `lignes` (titres détenus / cibles, `sens`, `quantite`, poids cible et
  réalisé, cours de référence, bornes, `prix_limite`, `montant_brut`, `courtage`, `tva`, `brvm`, `dcbr`,
  `demi_spread`, `impact`, `couts_total`, `montant_net`, `pire_cas`, `seances`), `tranches` (échéancier par
  séance : date, titres, limite, provision pire cas, date de règlement, financement), `execution`, `couts`,
  `dividendes`, `revenus`, `distribution`, `stress`, `declencheurs`, `explications`, `comparaison`,
  `faits`, `estimations`, `hypotheses`, `avertissements` ; `to_dict()` (JSON), `to_markdown()`,
  `to_html_fragment()` (`<section>` autonome, texte échappé) ; bandeau « Performance passée ≠ garantie.
  Aucun gain n'est garanti. » et statut toujours affichés, `PHRASE_ETUDE` tant que rien n'est PROMU.
- `choose_variant(variant=None, validation_dir, registry_path)` : `metrics.json` de S1 absent ou statut
  INDÉTERMINÉ ⇒ REF (D8) avec A en comparaison et avertissement ; A CANDIDAT ou PROMU ⇒ A, ou la variante
  promue par la règle du §3.4 ; A REJETÉ ⇒ REF. `s1_executed(registry_path)` lit le registre.
- Arrondis : `limit_prices(dernier_cours, reference_price=None, tolerance=0.01)` (achat
  `min(borne haute ; C × 1,01)` au pas inférieur, vente `max(borne basse ; C × 0,99)` au pas supérieur ; au
  moins **un pas** d'écart avec le dernier cours quand le pas dépasse la tolérance, dans la bande ; bornes
  `macro.price_band` de la référence de la prochaine séance) ; `floor_to_tick`, `ceil_to_tick`,
  `round_fcfa` (chaque composante de coût arrondie au franc) ; titres = `⌊w × valeur / cours⌋` (quotité 1),
  bande de non-transaction de 2 points pour les lignes détenues ; quantités réduites si la provision
  pire cas (tout exécuté à la limite) dépasse les liquidités disponibles.
- Coûts : `fee_breakdown(montant, costs)` (frais facturés), `order_costs(qty, cours, costs, side,
  half_spread, mdv63, tranches, limit)` (demi-spread du carnet sur 120 séances comme le moteur, impact
  `κ√π` avec `π = tranche / MDV63`, coûts implicites plafonnés par `|limite − cours| × qty`).
- Exécution : `participation_schedule(qty, cours, mdv63, 0.10)` (tranches ≤ 10 % de la MDV63 en valeur),
  `plan_execution(orders, cash, calendar, costs)` (ventes d'abord ; provision pire cas des achats dès la
  négociation ; produit d'une vente utilisable à partir de sa date de règlement, `settlement_date`,
  J+3 / J+2 de `macro.settlement_lag` ; liquidités initiales d'abord), `future_sessions` (calendrier connu,
  puis jours ouvrés hors fériés fixes : hypothèse).
- Revenus : `irvm_rate(symbol, date, taxes)` (exceptions par émetteur, pays de l'émetteur, historique
  daté `IRVM_HISTORY` pour reconstituer le brut), `dividend_schedule(quantities, asof, panels)` (dernier
  net publié connu en t, part ordinaire, ajusté des divisions, mois habituel, absences annoncées, garde-fou
  de 15 mois).
- Distribution : `estimation_window(asof, s1_done)` (S0 seulement tant que le registre n'a pas exécuté S1),
  `weekly_tr_returns` (données coupées à la fenêtre avant tout calcul), `stationary_bootstrap_indices`,
  `return_distribution(weekly, weights, horizon_weeks=52, n_boot=5000, mean_block=8, seed, cost_drag,
  with_draws=False)` (portefeuille et Composite TR tirés ensemble ; lignes pas encore cotées renormalisées ;
  médiane, P10, P90, P(perte), P(battre le TR) : « distribution historique, pas une prévision » ;
  `with_draws=True` ajoute les tirages `tirages_net` et `tirages_tr` pour l'histogramme du rapport) ; stress :
  `brvm_alpha.portfolio.stress` s'il existe, sinon `stress_scenarios` (§9.3).
- Affichage : `fr_texte(texte)` met en typographie française les messages techniques du modèle, les
  explications et les détails des filtres R (« 98.00% » → « 98,00 % », signe moins « − ») sans toucher aux
  numéros de section, aux versions ni aux dates ; les formateurs du Markdown écrivent le signe moins « − ».

### `backtest/engine.py`
- `Backtester(panels, costs: CostModel, constraints, capital, ...)`
- `.run(strategy: Callable[[pd.Timestamp, dict], pd.Series], rebalance: str|list) -> BacktestResult`
  (`equity`, `returns`, `weights`, `trades`, `costs`, `turnover`)
- Exécution en t+1 au prix moyen pondéré (value/volume) si le titre est
  échangé, avec plafond de participation au volume ; pas d'achat à la limite
  haute ni de vente à la limite basse ; dividendes nets d'impôt crédités.
- Dividendes (additif v1.1, D6, côté flux) : le moteur crédite le montant **corrigé**
  (`dividend_net`, meilleure estimation du versement réel) ; le panel facultatif
  `dividend_net_boc` (ligne « (d) » du BOC, montant vu par les signaux ;
  `panels_from_equities` le construit depuis `amount_first`) sert à publier l'écart :
  `BacktestResult.dividends_boc`, `dividend_events` (`date, symbol, qty, per_share,
  per_share_boc, credited, boc, gap`), `meta["dividend_gap_vs_boc"]`, `summary()["dividend_gap_vs_boc"]`.
- Quantités : `qty` et `positions` en titres ajustés (`float` seulement si une
  attribution non entière l'impose), `trades["raw_qty"]` en titres réels du jour
  (entiers) ; l'arrondi à la quotité se fait en titres réels (aucune dépendance à une
  division future). Bande de non-transaction : entrée et sortie complète exemptées (§6).
- Options du moteur (`ENGINE_DEFAULTS`, `params`) : `country_shock_recovery`
  (`"persistent"` / `"shock_only"`), `delisted_writedown`, `delisting_min_sessions` ; une clé
  inconnue (dict plat ou section `execution` du YAML) lève `KeyError`.

### `backtest/metrics.py` et `backtest/walkforward.py` (validation, §8)
- `weekly_returns(daily, exclude_windows=EXCLUDE_STATS_WINDOWS, max_sessions=None, session_no=None)` (la
  fenêtre du 06/05 au 25/06/2021 est exclue **par défaut** ; les semaines multi-séances après un trou de BOC sont
  **gardées** pour le chaînage, §3.1.3, et listées dans `attrs["multi_session_weeks"]` ; `max_sessions=6` :
  échantillon de dispersion), `multi_session_weeks(days, weeks=None, session_no=None)`,
  `dispersion_sample(x, multi_weeks)` (IR, TE, Sharpe, PSR/DSR, PBO, CVaR, bootstrap seulement),
  `weekly_observation_mask(...)`, `monthly_one_way_turnover(result)`, `first_investment_date(result)`,
  `family_pbo(..., split="trim_oldest"|"array_split", ties="le"|"half")`, `pbo_null_reference(n, ties)`
- Fenêtre d'évaluation de l'additif v1.1 (D2) : `evaluation_window(daily, t0, end)` (rendements de
  `[t0 ; fin]`, rendement de t0 compté), `rebase_at(level, t0)` (base 100 à la veille de t0),
  `evaluation_subperiods(t0, S1_SUBPERIODS, end=None)` (`[t0 ; 2019-12-31]`, `[2020-01-01 ; 2022-11-16]`) ;
  `S0_SUBPERIODS` (diagnostic), `FAMILY_SIZE_V11 = 9`
- `monthly_ic(scores, tr_index, horizon=21, lag=1, min_names=15, end=None, eligible=None, one_per_month=True)`
  (IC mensuel de Spearman, une décision par mois civil, aucune fenêtre à terme au-delà de `end`)
- `evaluate_status(..., s2_ic_monthly=None, s2_pbo=None, s2_pbo_slope=None, start=None, result=None,
  exposure=None, expected_period=None, exclude_windows=None, rules="v1.1", expected_weeks=None,
  dispersion_exclude=None) -> StatusReport`
  (statuts REJETÉ / CANDIDAT / INDÉTERMINÉ / PROMU ; **D7** : G7 du suivi réel sur les IC S1 puis S2 bout à
  bout, au moins 36 mois, autres filtres de S2 sur S2 seul, au moins 12 mois ; `rules="v1.0"` : lecture
  antérieure ; échantillon trop court ou incomplet : tous les critères `None`, statut INDÉTERMINÉ ;
  critères chaînés R1, R2, R4, R5, C1, C3, C4 sur toutes les semaines, dispersion R3, C2, G2-G9 sans
  `dispersion_exclude` ; couverture sur le calendrier W-FRI de `expected_period` moins la fenêtre du §8.1, seuil
  95 % (§8.5 E2), `couverture_dispersion` publiée ; `expected_weeks` ne doit jamais venir d'une série calculée avec
  les mêmes retraits)
- `variant_promotion(weekly_active, benchmark=None, pbo=None, baseline="A", n_trials=None) -> PromotionReport`
  (règle du §3.4 ; `n_trials=None` : taille de la famille, 9 pour A-I)
- `TrialRegistry.initialize(path, addendum_v11=False)` (`True` : ajoute `S1-I`, `REF-ID` et les essais de
  diagnostic S0 déjà exécutés, `N = 68`), `.record(..., rerun_reason=None)` (relance motivée : nouvel essai
  `S1-<v>-R<k>`), `.executed(sample)`, `.set_metrics(trial_id, metrics)` ; constantes `FAMILY_V11`,
  `REFERENCE_VARIANT = "REF"`, `REFERENCE_TRIAL_ID = "REF-ID"`, `N_TRIALS_START_V11 = 65`
- `cpcv(..., min_train=1)`, `purged_kfold(..., min_train=1)` : `ValueError` si un apprentissage est trop court

### `validation/` (exécuteur du test unique S1 et du diagnostic S0, additif v1.1 D2, D6, D7, D12)
- `run_validation(sample="S1"|"S0", out_dir=None, rerun_reason=None, panel_dir=None, workers=None, *,
  registry_path=None, repo_root=None, panels=None, model_factory=None, plan=None,
  allow_nonstandard_plan=False, n_boot=5000, seed=0, log=None, decision_mode="evenementiel") -> ValidationResult`
  (`out_dir`, `metrics`, `statuses`, `trial_ids`, `duration_s`, `files`, `lock`) ; `decision_mode` :
  `"evenementiel"` (défaut depuis le pré-vol du 22/11/2026 : `strategy_fn(event_driven=True, calendar)` et
  `rebalance="D"` : décisions de fin de mois plus les ordres entre deux du §6 « Fréquence » : règles pays
  dès la première séance qui suit l'annonce (D10), poche S1, ventes reportées) ou `"mensuel"`
  (`strategy_fn()` et `rebalance="M"` : aucun ordre entre deux fins de mois) ; consigné dans le verrou, le
  registre et `metrics.json` ; sur S1, un run dont le mode effectif diffère du mode consigné (repli) est un
  échec ; sur le panel réel, S1 exige `n_boot = 5 000`
- `run_plan() -> list[RunSpec]` : 30 runs dans un ordre fixe — A-I et REF aux coûts centraux et de stress
  à 10 M FCFA ; A et I aux coûts optimistes et sévères ; A, I et REF à 100 M et 1 Md FCFA (centraux).
  `RunSpec(variant, costs, capital)` : `run_id` (`A_central_10M`…), `is_trial` (central à 10 M : seuls ces
  runs entrent au registre, dans la PBO et le DSR), `in_family` (A-I), `role`
- Modèle par défaut `brvm_alpha_model(spec, config, sample)` : `BrvmAlpha(config, variant, capital=K,
  notes=None, window_basis="sessions", validation_s1=(S1), history_start=(None | début de S0))`,
  `.strategy_fn(event_driven=True, calendar)` pour `Backtester.run(fn, rebalance="D", start, end)` (mode
  événementiel ; `.strategy_fn()` et `rebalance="M"` en mode mensuel) ; chocs pays du moteur
  `model.engine_country_shocks()` ; univers éligible et score composite lus dans `model.last_decision`
- D2 : `t0` = `first_investment_date` du run `A_central_10M` ; métriques, critères du §8.3 et étalons sur
  `[t0 ; fin]`, rebasés à t0 ; fenêtre complète publiée pour information
- Étalons (`benchmarks.benchmark_levels`) : `TR` (`store.composite_tr_reconstructed(official=True)`), `EW`
  (`store.equal_weight_tr` avec le masque d'éligibilité PIT de A, mensuel ; au même capital pour 100 M et
  1 Md), `PRIX`, `BRVM10` (jusqu'au 30/12/2022), `BRVM30` et `PRESTIGE` (dès le 02/01/2023), `FONDS`
  (« non disponible » explicite)
- Métriques par run (§8.2, hebdomadaires W-FRI, nettes) : rendement et volatilité annualisés, actif contre
  TR et EW, IR, TE, Sharpe naïf / Lo / GLM (alerte > 25 %), PSR(0), DSR avec N = registre et N = 9, PBO
  CSCV de la famille (10 blocs, Sharpe de Lo des actifs nets), bootstrap stationnaire `n_boot = 5 000`
  explicite et blocs de 8 semaines (IR, actif moyen), drawdowns absolu et relatif, CVaR 95 % à 5 séances
  contre le TR, rotation mensuelle aller, coûts payés, lignes, part investie, sous-périodes, haircut BHY,
  dividendes crédités contre ligne (d) (D6) ; statut §8.3 de chaque variante et règle de promotion §3.4
- Contrôles de chaque run (`controls.accounting_controls(bt, res)`, aucune performance) : cash réglé ≥ 0,
  exposition maximale, identités `VL = cash − frais dus + créances + Σ q·P` et `ΔVL = Σ q·ΔP + exécutions +
  dividendes − coûts` (rompus de division compris, tolérance 1e-6 de la VL), aucune vente à la borne basse ni
  achat à la borne haute, coût par aller (médiane, moyenne pondérée), ordres bloqués par motif ;
  `metrics.json` : `runs[...]["controles"]` et synthèse `controles` (`tous_ok`, `runs_en_anomalie`)
- Verrou (`lock.py`, S1 seulement) : `git diff --quiet HEAD -- brvm_alpha configs` exigé **et** aucun fichier
  non suivi (non ignoré) sous `brvm_alpha/` ni `configs/` (pré-vol du 22/11/2026 : un module non commité
  serait importé sans figurer dans le commit) ; `lock.json` (commit, empreinte `settings.config_fingerprint`
  et `empreinte_controle` (`lock.fingerprint_check`) : comparaison avec l'empreinte de l'état figé `a2bfeb4`,
  référence de pré-enregistrement citée = commit `751d1be` (YAML 1.0, `dcdf1fb7db530c44`), sans autoréférence ;
  le registre garde l'empreinte du pré-enregistrement dans `note` quand l'exécution la remplace), version et
  SHA-256 du YAML, horodatage UTC, plan, `n_boot`, statut `en cours` / `terminé` / `échec`, empreinte de
  `metrics.json`) ; refus (`ValidationRefused`, code 2) si le registre contient des essais S1 « exécuté » ou
  si un verrou existe, sauf `rerun_reason` (nouveaux essais, anciens résultats déplacés dans
  `precedent_<horodatage>/`, les deux publiés). Un run S1 en échec : aucune métrique calculée ni publiée
  (`ValidationFailed`), verrou « échec »
- Parallélisme : `ProcessPoolExecutor` (contexte `spawn`, au plus 3 processus), résultats remis dans l'ordre
  du plan (déterministes), durée de chaque run journalisée
- Sorties : `reports/validation_S1/` (`resultats.md`, `metrics.json`, `weekly_returns.parquet`,
  `nav.parquet`, `trades.parquet`, `lock.json`) ; S0 : `reports/diagnostic_S0/` (mêmes fichiers,
  `contexte.json` au lieu du verrou, mention « contaminé, aucune valeur de preuve ») ; registre
  `reports/trials.parquet` mis à jour (essais S0 de diagnostic : `S0-DIAG-<horodatage>-<variante>`)

### `strategy/alpha.py`
- `BrvmAlpha(config).signals(asof, panels) -> dict[str, pd.Series]`
- `BrvmAlpha(config).target_weights(asof, panels) -> pd.Series`
- `BrvmAlpha(config).explain(asof, panels, symbol) -> dict` (décomposition du score)

Modèle v1 + additif v1.1 (SPECIFICATION_STRATEGIE.md §1.5, §2-§6, §8.4, §9.1 ; paramètres =
`configs/strategy_v1.yaml`, `version: "1.1"`) :
- `BrvmAlpha(config=None, variant="A", capital=None, params=None, *, notes="auto", notes_known_at=None,
  country_events=None, dividend_calendar=None, history_start=None, risk_overlay=True, defer_sales=None,
  sectors=None, window_basis=None, validation_s1=False, capital_increases=None, cfg=None)`
  - `notes_known_at=None` (défaut) : notes en règle stricte à la date de décision (backtests, validation,
    dates passées : inchangé) ; un instant UTC : **mode direct**, les notes connues à cet instant sont
    transmises telles quelles aux mêmes règles (veto, inclinaison, filtres R), appliquées à la séance qui
    suit la décision (`diagnostics["notes"]["mode"]`, `["session"]`, `["known_at"]`, `["table"]`) ; ignoré
    en `validation_s1` et pour une décision postérieure à cet instant ; aucune règle ne change ;
  - `variant` ∈ `VARIANT_SPECS` : famille `FAMILY_V11 = ("A", …, "H", "I")` (PBO et DSR, N = 9) et
    référence `REFERENCE_VARIANT = "REF"` (« indice discipliné » D8, essai REF-ID hors famille) ;
    `VariantSpec.kind` : `"alpha"` (A-H), `"core_satellite"` (I, D9), `"reference"` (REF, D8) ;
  - `cfg` (contrat v1.1) : `PlatformConfig` (alias de `config`) ou dictionnaire de paramètres (alias de
    `params` = surcharges du YAML, validées par `settings.load_strategy_config`, clé inconnue refusée) ;
  - `window_basis=None` ⇒ `data.window_basis` du YAML = `"sessions"` (D1), y compris avec
    `validation_s1=True` ; `"boc"` reste disponible (lecture v1.0) ;
  - `country_events=None` ⇒ `reference.COUNTRY_EVENTS` (D10) ; `False` : aucune règle pays datée ;
  - `validation_s1=True` : réservé au test unique S1 ; notes forcées à `None` (D11) ; hors
    `validation_s1`, aucune série de performance n'est calculée sur S1.
- Additif v1.1 appliqué : **D1** fenêtres en séances, bornes de rendement ≤ 5 séances, seuils
  `m_eff = ⌈m × n_BOC_disponibles / L⌉` (planchers 40 signaux / 20 filtres) ; **D3** garde de
  capitalisation = alerte (`diagnostics["cap_guard"]["alert"]`), |r| > 50 % bloquant ; **D4** titres
  ajoutés pour la capacité ≤ 98 %/n_cible, au-delà des 50 % si nécessaire, reliquat publié
  (`diagnostics["portfolio"]["capacity_fill"]`) ; **D5** drawdown relatif depuis t0 (premier jour investi,
  `record_nav(asof, nav, invested=...)`, `relative_dd_start`), panier w_EW = 20 éligibles les mieux
  classés (`diagnostics["ew_basket"]`), entrées et sorties exemptées de la bande par le moteur ;
  **D6** signaux sur le montant connu en t ; **D8** REF : 20 plus grosses capitalisations, poids ∝
  capitalisation, plafonds D8, rebalancement annuel (première décision de janvier) et sorties forcées
  (`diagnostics["index"]`) ; **D9** I = 0,5 × REF (annuel, dérivé entre deux) + 0,5 × A (mensuel),
  projeté sur les plafonds de groupe de D8 (`diagnostics["core"]`, `["satellite"]`, `["core_satellite"]`) ;
  **D2** G et H sans covariance suffisante : pondération de A, journalisée.
- `.universe(asof, panels) -> DataFrame` (U1-U10 : `eligible`, `reason`, `codes`, MDV63, U6/U7…)
- `.risk_flags(asof, panels, notes="default") -> DataFrame` (R1-R12 du panel, notes de l'analyste si
  `brvm_alpha.notes` s'importe, règles pays)
- `.decide(asof, panels, held=None) -> AlphaDecision` (univers, signaux, risque, score, poids, diagnostics)
- `.strategy_fn(event_driven=False, calendar=None, mode="alpha"|"index")` : fonction
  `(asof, view) -> poids | None` pour `Backtester.run(fn, rebalance="M", start=, end=)` (mémorise
  positions, valeur liquidative et « titres détenus » pour t0 ; REF et `mode="index"` renvoient `None`
  entre deux rebalancements annuels sans sortie forcée). Mode événementiel (`event_driven=True`,
  `rebalance="D"`) : une décision **intra-mois** (règle pays, poche S1) ne modifie pas l'état des poches
  annuelles (`_peek_decide` : le rebalancement annuel de REF et du cœur de I reste la première décision
  mensuelle de janvier ; le satellite A de I garde ses lignes de fin de mois)
- `.disciplined_index_weights(asof, panels)` (indice discipliné D8 à la date, sans état)
- `build_panels(panel_dir) -> dict` : panels du moteur et de la stratégie (`close_raw`, `tr_index`,
  `shares`, `market_tr`, tables datées `dividends_table`, `corporate_actions`, `market`). Interface D6 :
  `dividends_table.amount` = montant connu à `date` (ligne (d) ; correction `amount_revised` visible à
  `revised_seen`) pour les signaux ; `amount_cashflow` = montant corrigé, crédité par le moteur
  (`dividend_net`) ; `dividend_amount_gap(panels)` : écart par dividende et total (à publier).
- `reference.COUNTRY_EVENTS` (DataFrame : `date` d'annonce, `country`, `rule`, `event_date`,
  `action_date`, `sample`, `source`, `confidence`) ; `reference.country_event_action_date(date, calendar)` :
  première séance qui suit l'annonce (Mali 09/01/2022 → 10/01/2022). Un événement est connu de la décision
  de t si l'annonce précède la séance d'exécution t + 1.

### `cli.py`
`python -m brvm_alpha <commande>` ; aide et messages d'erreur en français (`FrArgumentParser`), bannière
« Performance passée ≠ garantie. Aucun gain n'est garanti. » sur toute sortie destinée à l'utilisateur.
Codes de sortie : 0 succès, 1 échec (données absentes, collecte arrêtée), 2 refus ou saisie invalide.
- Données : `update [--from AAAA-MM-JJ] [--jusqu-au] [--delai 10] [--max-requetes 200] [--simulation]
  [--sans-panel]` (BOC manquants depuis le lendemain du dernier BOC local ; client `brvm_fetcher` =
  `notes.research.PoliteSession` sans cache disque : robots.txt, ≥ 10 s entre requêtes **d'une session à
  l'autre**, arrêt définitif et blocage persistant au premier 403/429, refus si www.brvm.org est déjà bloqué ;
  panel reconstruit si un BOC est ajouté) ; `panel [--force] [--workers]` (`store.build_panel`) ; `live
  [--format texte|json] [--symbole] [--hors-ligne]` (page publique, une requête polie, cache 60 s).
- Notes (`--racine` : journal, défaut `data/notes`) : `notes add --cible … --titre --texte|--fichier --avis
  haussier|baissier|neutre --conviction 1-5 --horizon --source --url --publie-le --type --etiquette`
  (`make_manual_note` : source libre en étiquette `source:…`, URL http(s) seulement, date future refusée ;
  `NoteStore.add(analyze=True)`), `notes list [--cible] [--depuis] [--jusqu-au] [--statut]`, `notes show ID`
  et `notes archive ID [--motif]` (préfixe unique d'identifiant, `resolve_note_id`), `notes export [--sortie
  chemin|-]`, `notes research [--cibles] [--hors-ligne] [--max-requetes] [--depuis] [--simulation] [--pdf N]`
  (`run_research`, règles de politesse affichées ; puis lecture du contenu d'au plus `N` documents récents,
  défaut 20, `0` = aucun, non lancée si la collecte en ligne a été arrêtée), `notes lire [--max N]
  [--hors-ligne] [--cibles CODES] [--simulation] [--racine]` (lecture seule des documents, sans nouvelle
  collecte), `notes analyze --texte|--fichier` (sans enregistrer). La lecture appelle
  `notes.research.enrich_documents(store, max_docs=, targets=, offline=, dry_run=)`, **importée au moment de
  l'appel** (`load_enrich_documents`, `run_enrich`) : fonction absente → message clair, code 1 pour `notes
  lire` ; bilan affiché par `format_enrich_report` (candidats, lus, notes enrichies, documents scannés à lire
  à la main avec leur adresse, erreurs, requêtes, arrêt éventuel ; ligne « Détail » quand le bilan porte les
  compteurs de la vraie fonction : documents lus sans chiffre retenu, documents absents du cache hors ligne,
  nouvelles versions écrites au journal, ou « simulation : aucune version écrite » ; « Aucun document à
  lire » quand tout est déjà lu). `--simulation` lit les documents (téléchargement compris, sauf
  `--hors-ligne`) sans rien écrire au journal. Un deuxième appel ne relit rien (les notes lues portent
  `analysis.extracted.doc_sha256`).
- Analyse : `indices [--date] [--detail] [--format] [--notes-au]` et `indices dossier CODE` (`evaluate_indices`,
  `index_dossier`) ; `universe [--date]` ; `explain SYMBOLE [--date] [--variante] [--racine] [--notes-au]` (`explain_symbol` :
  variante par défaut = `choose_variant`) ; `recommend --capital K [--portefeuille fichier.csv] [--cash]
  [--variante] [--format md|json|html] [--date] [--couts] [--tirages] [--graine] [--racine] [--notes-au] [--sortie]` (CSV
  « symbole,titres », `parse_holdings` ; `--racine` : même journal des notes que `serve` et `report`) ;
  `report --capital K [--couts] [--tirages] [--graine] [--racine] [--notes-au] [--sortie]` (`report.build_report`,
  défaut `reports/rapport_AAAA-MM-JJ.html`) ; `serve [--port 8765] [--hote]`.
- **Deux instants** (`notes_instant(date, notes_au, panel_dir, last=, now=)`) : la date des cours est `--date`
  (défaut : dernière séance du panel). L'instant de connaissance des notes vaut `--notes-au
  AAAA-MM-JJ[THH:MM]` s'il est donné (UTC ; date seule = fin de journée, `parse_instant`) ; sinon l'heure
  réelle (`now_utc()`, remplaçable dans les tests) en **mode direct**, c'est-à-dire quand la date de décision
  est la dernière séance du panel (aucune date, ou une date non antérieure à cette séance) ; sinon `None` :
  **mode historique**, règle stricte à la date demandée. `indices`, `explain`, `recommend` et `report`
  transmettent cet instant (`notes_known_at`) et affichent la ligne datée des notes (`notes_status`,
  `filter_lines`) ; `notes add` indique à quelle séance la note saisie comptera.
- **S1** : `indices`, `explain`, `recommend`, `report` refusent (code 2) toute date de décision ≤ 2022-11-16
  avant tout calcul (`in_s1`, `s1_refusal`) ; `backtest` refuse une période qui recoupe S1 sans
  `--validation-s1` (qui exige `--window-basis`) ; `universe` (comptage) reste permis.
- `validate --sample S1|S0 [--rerun-reason TEXTE] [--workers N] [--out-dir] [--panel-dir] [--decision-mode
  evenementiel|mensuel]` : exécuteur de la validation (`validation.run_validation`) ; refus du verrou → 2,
  run en échec → 1.
- Saisies partagées avec l'interface : `parse_date`, `parse_instant`, `parse_capital` (« 10 000 000 », « 10M »,
  « 1,5Md »), `parse_holdings`, `is_loopback`, `last_session(panel_dir)`, `notes_instant`, `notes_status`,
  `run_enrich`.

### `data/boc_download.py`
`download_range(start, end, out_dir, pause=10.0, *, fetcher=None, today=None, progress=None) -> int`,
`fetch_one(fetcher, day, out_dir, pause=None, *, mark_missing=True)`, `pending_days(start, end, out_dir)`,
`PoliteFetcher(session=None, pause=10.0, *, sleep, clock, max_requests)` (robots.txt lu une fois et respecté,
délai ≥ `MIN_DELAY_S = 10` s ou `Crawl-delay`, redirections non suivies, arrêt `DownloadStopped` au premier
403/429 ou sur interdiction ; aucun marqueur `.missing` dans ce cas ni pour les `RECENT_DAYS = 3` derniers
jours). Avant le 22/11/2026, le délai par défaut était de 0,4 s : corrigé.

### `ui/` (interface web locale, `python -m brvm_alpha serve`)
- `server.make_server(host="127.0.0.1", port=8765, *, allow_remote=False, services=None) -> UIServer`
  (`ThreadingHTTPServer` ; `port=0` : port libre ; adresse non locale refusée sans `allow_remote`) ;
  `Services(notes_root, panel_dir, reports_dir, validation_dir, diagnostic_dir, boc_dir, research_kwargs,
  clock=None)` : seuls accès aux données (remplaçables dans les tests) ; `clock` : horloge UTC injectable
  (défaut `cli.now_utc`) ; `Services.notes_instant(asof)` : maintenant (mode direct) si `asof` est vide ou
  n'est pas antérieure à la dernière séance du panel, `None` (mode historique) sinon, transmis à
  `evaluate_indices`, `index_dossier`, `explain`, `recommend` et `build_report` ; `Services.notes_status(asof)` :
  état daté des notes (`notes.signals.notes_in_force`, mis en cache par journal, panel et séance
  d'application) ; `Services.run_research(..., read_docs=False, max_docs=20)` : après la collecte, lecture du
  contenu des documents (`cli.run_enrich`, avec le **même panel** que la collecte et une `PoliteSession`
  propre à la lecture, journalisée comme la collecte, quota `max_docs + 10`), bilan dans le journal du
  travail et `result["documents"]` ;
  `JobManager` : **une** opération longue à la fois
  (recherche, rapport, ordre de bataille) dans un fil, `Job.snapshot()` (statut, progression, journal),
  `JobBusy` → 409.
- Connexions : au plus `MAX_CONNECTIONS = 32` simultanées (sémaphore de `UIServer.process_request`, au-delà
  connexion fermée) ; lecture des en-têtes et du corps expirant après `REQUEST_TIMEOUT_S = 20` s
  (`Handler.timeout` ; corps jamais envoyé → 408, connexion fermée).
- Sécurité : en-tête `Host` ∈ {localhost, 127.0.0.1, [::1]} avec le port du serveur (sinon 400) ; jeton
  anti-CSRF propre au lancement (`_jeton`) sur chaque POST, `Origin` / `Sec-Fetch-Site` d'un autre site →
  403 ; corps ≤ 256 Ko (413), `Content-Length` obligatoire (411), formulaire urlencodé seulement (415), champs
  bornés ; CSP `default-src 'none'` avec nonce de script, `X-Frame-Options`, `nosniff`, `no-referrer`,
  `no-store` ; échappement systématique (`pages.esc`, Markdown sûr `md_to_html`) ; aucune commande système ;
  fichiers servis choisis dans la liste `reports/*.html` (jamais un chemin saisi), rapport régénéré écrit sous
  `reports/rapport_<date du panel>.html` et servi dans un `iframe` *sandbox* avec sa propre CSP.
- Pages (GET) : `/` tableau de bord (état S1, variante, **ligne datée des notes** et filtres actifs, dernier
  rapport, « régénérer »), `/notes` (saisie manuelle avec aide aux codes SYMBOLE / IDX:… / PAYS:… / SECT:… /
  THEME:… / MARCHE ; section « Notes en vigueur à la séance d'application » : ligne datée, filtres actifs avec
  la note qui les porte et la façon de les lever, notes manuelles et notes automatiques séparées (date, cible,
  type, score, confiance, décroissance, source avec lien, filtre), 10 plus positives et 10 plus négatives,
  composante « notes » de chaque indice avec les notes qui la portent ; puis le journal filtrable ; les blocs
  d'une page sont assemblés par `pages.join` — `Safe + Safe` rend une chaîne ordinaire, qui serait échappée),
  `/notes/fiche?id=` (analyse, lecture, versions, archivage), `/recherche` (confirmation, hors ligne / en
  ligne, quota ≤ 150, case « lire le contenu des documents récents » et nombre maximal ≤ 60, journal et
  progression, bilan de la lecture, règles de politesse), `/indices` (ligne datée, colonne « Notes (z) » :
  valeur, « score nul » ou « aucune note », jamais « n.d. » seul ; encadré « Position fragile » et mention
  « sans notes : … » quand la position ne change que par le poids de la composante « notes »,
  `pages.stance_flip`) et `/indices/dossier?code=`
  (notes qui influencent l'indice), `/portefeuille` (capital, portefeuille « symbole,titres », liquidités,
  variante → ordre de bataille complet avec la ligne datée et les achats bloqués, exports Markdown / JSON),
  `/expliquer?symbole=`, `/validation`
  (résultats S1 lus, diagnostic S0 replié et marqué contaminé), `/rapport/voir?nom=`, `/api/travail?id=`.
  Actions (POST) : `/notes/ajouter`, `/notes/archiver`, `/recherche/lancer`, `/rapport/regenerer`,
  `/portefeuille/calculer`. Dates de S1 refusées comme dans la CLI.
- Rendu : aucune ressource externe, thème clair/sombre (variables CSS sur `:root`, préférence du système ou
  bouton), gouttière de 16 px, tableaux dans `.tablewrap` (téléphone), bannière et légende faits /
  estimations / hypothèses sur chaque page.

### `report/html.py` (rapport final, exporté par `brvm_alpha.report`)
- `build_report(asof, capital, out_path, *, panels=None, panel_dir="data/panel", notes_root="data/notes",
  validation_dir="reports/validation_S1", diagnostic_dir="reports/diagnostic_S0", holdings=None, variant=None,
  **kwargs) -> Path` : écrit **un seul fichier HTML** autonome (aucune ressource externe : styles et script en
  ligne, graphiques en SVG inline générés en Python, axes et libellés en HTML ; seuls les liens de la liste des
  sources, `class="src"`, pointent vers brvm.org). Options (`**kwargs`, transmises à `render_report`) : `cash`,
  `costs`, `registry_path`, `n_boot` (5 000), `seed`, `recommend_kwargs` (surcharges de `recommend`), `now`,
  `notes_known_at` (instant de connaissance des notes ; `None`, défaut sûr : mode historique ; la ligne de
  commande et l'interface passent l'heure réelle quand la date est la dernière séance du panel).
  Chemins de données relatifs = racine du dépôt (comme `recommend`) ; `out_path` relatif = répertoire courant.
- `render_report(...) -> RapportHTML` (`html`, `sections` : liste de `SectionResult(id, titre, statut, message,
  duree_s)` avec `statut` ∈ `ok` / `indisponible` / `erreur`, `meta`) ; `read_validation(dir, sample="S1")` :
  état du test lu dans `metrics.json` / `lock.json` (`exécuté`, `non exécuté`, `en cours`, `échec`, `illisible`,
  `autre échantillon`), statut de A et variante principale après la règle du §3.4.
- Sections (`SECTIONS`, dans l'ordre, ancres `#id`) : `bandeau` (date des données = dernière séance ≤ `asof`,
  capital, statut lu dans `metrics.json` ou « test S1 non exécuté », bannière « Performance passée ≠ garantie.
  Aucun gain n'est garanti. Statut : … », phrase étude / paper trading / promu), `marche` (Composite, Composite TR
  officiel ou reconstruit, BRVM 30, Prestige, capitalisation, PER, prime du BOC et bande chère/neutre/bon marché,
  `macro.ref_govt_rate`), `s1` (t0, 9 variantes + REF : rendement, actif contre TR, IR et IC bootstrap, DSR N = 9
  et registre, drawdown relatif, rotation, statut ; courbes A, I, REF, TR, EW rebasées à t0 depuis `nav.parquet`,
  à défaut `weekly_returns.parquet` ; sous-périodes ; sensibilités coûts/capacité ; PBO ; règle du §3.4 ;
  prédiction du §8.3 ; lecture honnête générée ; diagnostic S0 replié et marqué contaminé ; **encadré explicite
  si le test n'est pas exécuté**), `ordre` (`portfolio.recommend.recommend(..., index_evaluation=False)` :
  `to_dict()` pour les ordres, prix limites, coûts, séances, contraintes actives, comparaison A/REF, faits /
  estimations / hypothèses ; `to_html_fragment()` replié ; « module indisponible » si l'import échoue),
  `revenus` (calendrier mensuel et détail des dividendes, net après IRVM), `distribution` (histogramme des
  tirages **recalculés à l'identique** par `recommend.return_distribution(..., with_draws=True)` : même fenêtre,
  mêmes poids, même graine, même renormalisation des lignes pas encore cotées ; médiane/P10/P90, P(battre le TR), P(perte) ; stress du §9.3 **en tête** si la prime
  du BOC classe le marché « cher », §4.5), `indices` (`notes.index_eval.evaluate_indices` : position, confiance,
  raisons, ligne datée des notes et colonne « Notes (z) » ; « aide à la décision, pas un signal validé » ;
  encadré « Position fragile » et mention « sans notes : … » sous la position quand elle ne change que par
  le poids de la composante « notes », `_stance_flip`),
  `notes` (ligne « Notes connues au …, appliquées à la séance du … : N en vigueur (dont M manuelles), F
  filtre(s) de risque actif(s) » ; texte clair si aucune note ne porte de score ; filtres actifs avec la note
  qui les porte et la façon de les lever ; notes en vigueur, manuelles et automatiques séparées : date, cible,
  type, score, confiance, décroissance, source, filtre ; 10 plus positives et 10 plus négatives ; composante
  « notes » de chaque indice avec les notes qui la portent ; puis les 12 dernières notes actives de
  `NoteStore(notes_root)` avec score, matérialité, confiance, lecture ; une adresse n'est un lien
  (`class="src"`) que vers `https://www.brvm.org/`, sinon elle est en texte ; vetos et inclinaisons de la
  décision ; encadré « aucune note » si le journal est absent ; la section `ordre` affiche la même ligne et
  les achats bloqués par une note ; filtres et blocages sont des **fiches** (`_fiche` : en-tête puis lignes
  « libellé : texte »), lisibles à 390 px comme à 1 280 px ; dans les tableaux de notes le score suit la
  cible), `risques` (filtres R actifs de
  `BrvmAlpha.decide`, règles et événements pays, événements à venir, drawdown, valorisation §4.5), `univers`
  (tous les titres : éligible, motif U1-U10, score final, rang, blocs z, poids, filtres R), `methode` (§10,
  trous de données comptés dans `sessions.parquet`, hypothèses de coûts, protocole, sources).
- Robustesse : calculs partagés paresseux (panels, ordre de bataille, décision, évaluation des indices, tirages) ;
  chaque section dans un `try/except` : `Unavailable` → encadré « indisponible », autre exception → encadré
  d'erreur lisible (type, message, trace repliée) ; le rapport est toujours écrit. Tout texte issu des données,
  des notes ou des fichiers de résultats est échappé ; le bloc JSON des graphiques n'a aucun `<`, `>` ou `&` brut.
- Mise en page : largeur utile 1 200 px, gouttière de 16 px, aucun défilement horizontal de la page (tableaux
  larges dans `.tablewrap` ; à 1 280 px, tous les tableaux tiennent sans défilement : textes longs repliés,
  nature des stress sous le code ; à 390 px, résumés compacts des ordres et des stress),
  couleurs en variables CSS sur `:root` redéfinies sous `@media (prefers-color-scheme: dark)` (et
  `:root[data-theme]`, bouton de thème), `body` à fond explicite ; info-bulles et réticule en JavaScript sans
  dépendance. **Aucune performance n'est calculée sur S1** : le résultat du test unique est lu, jamais recalculé.

## Module « Notes de l'analyste » (`brvm_alpha/notes/`)

Objectif : (1) lancer une **recherche automatique** d'informations sur les
titres, les indices, les pays et le marché ; (2) permettre à l'analyste
d'**inscrire manuellement** des informations ; (3) **analyser** chaque note
(type d'événement, ton, chiffres, cibles, matérialité, filtres de risque) ;
(4) **agréger** les notes en scores datés, sans biais d'anticipation, pour
**évaluer les indices** et aider à la prise de position. Les notes ne pilotent
jamais seules le portefeuille : leur poids est borné et mesuré (IC walk-forward,
document 07 §6.5 S5).

```
notes/
  model.py        # dataclasses Note, NoteAnalysis ; codes de cibles
  store.py        # NoteStore : journal JSONL append-only (data/notes/notes.jsonl)
  entities.py     # liaison texte -> symboles / indices / pays / secteurs / thèmes
  lexicon.py      # lexique BRVM-FR (doc 07 §3.3) + règles de types (doc 07 §6.4)
  analyze.py      # analyse d'une note -> NoteAnalysis (lecture en français)
  research.py     # collecteurs polis : brvm.org (listes Drupal), BOC locaux, URL fournie
  signals.py      # scores datés par cible, surcouches manuelles bornées, filtres R1-R10
  index_eval.py   # évaluation des indices -> position SURPONDÉRER / NEUTRE / SOUS-PONDÉRER
```

### Codes de cibles
`SNTS` (symbole), `IDX:BRVM-C`, `IDX:BRVM-30`, `IDX:PRESTIGE`, `IDX:PRINCIPAL`,
`IDX:BRVM-C-TR`, `IDX:SECT:<code secteur>` ; `PAYS:CI|SN|BJ|BF|ML|NE|TG|GW` ;
`SECT:<code secteur BOC>` ; `THEME:<mot>` (taux BCEAO, cacao, pétrole, élections,
sécurité, eurobond…) ; `MARCHE`.

### `notes/model.py`
- `Note` : `note_id`, `created_at` (UTC, saisie/collecte), `published_at` (UTC,
  quand l'information est devenue publique ; défaut = `created_at`),
  `first_tradable_session` (1re séance négociable après `published_at` ;
  une note publiée après la séance n'agit qu'à la séance suivante),
  `author` (`analyste` | `auto`), `source` (`manual`, `brvm_list`,
  `brvm_issuer`, `boc`, `url`), `url`, `title`, `text`, `targets: list[str]`,
  `event_type`, `stance` (`haussier` | `baissier` | `neutre` | None),
  `conviction` (1..5 | None), `horizon_days` (défaut 20 séances), `tags`,
  `status` (`active` | `archived`), `version`, `analysis: dict | None`.
  Champs facultatifs ajoutés : `published_precision` (`date` | `datetime`),
  `recorded_at`, `targets_unknown` (cibles saisies non reconnues : conservées et
  signalées, jamais remplacées par les cibles détectées). Une `first_tradable_session`
  fournie ne peut pas précéder la coupure de 09h00 appliquée à `published_at`.
  Identifiant : fondé sur l'URL pour une pièce collectée ; sur le contenu (titre, texte,
  `published_at`, URL, avis) pour une note de l'analyste.
- `NoteAnalysis` : `targets` (manuelles + détectées), `event_type`, `tone`
  [-1,1], `s_num` [-1,1] (chiffres : ΔRN, Δdividende… ; moitié de `s_num_doc`, affichage),
  `score` [-1,1] = `clip(0,7·s_num_doc + 0,3·tone, −1, 1)` avec `s_num_doc =
  clip(Δ%/25, ±2)` (formule du document 07 §3.4, dans `components`),
  `materiality` [0,1], `confidence` [0,1], `risk_flags` (R1..R10),
  `extracted` (rn, rn_prev, rn_growth, div_net, div_prev, ex_date, ag_date…),
  `reading` (explication en français, phrases courtes), `matched_terms`.

### `notes/store.py`
- `NoteStore(root="data/notes")` : `add(note) -> note_id`, `get(note_id)`,
  `update(note_id, **changes)` (nouvelle version, l'ancienne est conservée),
  `archive(note_id)`, `list(target=None, since=None, until=None, source=None,
  status="active") -> pd.DataFrame`, `asof(ts) -> pd.DataFrame` (notes connues
  à la date, version en vigueur à cette date), `export_markdown(path)`.
- Lecture tolérante (ligne tronquée, non UTF-8 ou mal typée : ignorée et signalée dans
  `errors`) ; analyse faite hors verrou. Un `now` antidaté (reprise d'historique) marque
  la version `reconstitue` / `backdated` : elle est exclue des vues strictes (hors mode
  horloge simulée des tests, variable `BRVM_ALPHA_SIMULATED_CLOCK=1`).

### `notes/analyze.py`
- `analyze_note(note, panels=None, asof=None) -> NoteAnalysis`
- `analyze_text(text, title="") -> NoteAnalysis` (raccourci)
- `read_document(text, title="", event_type=None, max_chars=1500, ocr_layer=False) -> dict` : lecture
  **contrôlée** du texte d'un document (`pdftotext -layout`), appelée par `research.enrich_documents` :
  `figures` (agrégats retenus — chiffre d'affaires, PNB, résultat avant impôt, résultat net, dividende —,
  chacun avec sa ligne ou phrase `source`), `rejected` (chiffres vus mais écartés, avec le motif), `period`
  et `period_ok`, `excerpt` (extrait borné), `has_figures`. Garde-fous : une variation n'est retenue que si
  elle est écrite ou recalculée sur deux montants de même unité et de même périmètre ; une variation écrite
  est recoupée avec les montants à 1 point près ; base négative ou nulle, ou variation au-delà de ±300 % :
  montants gardés, aucun score numérique (« base non comparable ») ; période du document cohérente avec la
  note ; comptes consolidés préférés aux sociaux, jamais mélangés ; en-tête, unité ou appariement ambigus :
  **aucun chiffre** (score fondé sur le ton seul). `ocr_layer=True` (texte issu de l'OCR d'un scanner) : seuls
  les chiffres recoupés sont retenus. Le résultat avant impôt est lu et affiché, il n'entre pas dans le score.

### `notes/research.py`
- `run_research(store, targets=None, since=None, max_requests=150,
  delay_s=10.0, offline=False) -> list[Note]` : collecte brvm.org (annonces,
  OST, avis, calendrier des dividendes, rapports par émetteur) et événements
  des BOC locaux, déduplication par `note_id`, analyse, ajout au store.
- `fetch_url_note(url, store, targets=None) -> Note` : une page publique
  fournie par l'analyste (respect de robots.txt, aucune contournement).
- Politesse : `robots.txt` lu et respecté (brvm.org : `Crawl-delay: 10`),
  User-Agent explicite, cache, arrêt immédiat sur 403/429/5xx répétés. Le délai et le
  blocage après un 403/429 valent **d'une session à l'autre** (`<cache>/politeness.json`,
  levée explicite par `clear_block(hôte)`) ; redirections suivies à la main et contrôlées
  à chaque saut ; hôte normalisé (port, casse, point final). `created_at` d'une note
  collectée = instant où la page a été vue (borne de connaissance) ; `published_at` =
  publication sur le marché.
- **Lecture du contenu** : `enrich_documents(store, *, max_docs=20, targets=None, offline=False, session=None,
  delay_s=10.0, max_requests=None, panel_dir=DEFAULT_PANEL_DIR, dry_run=False, now=None, reread=False) -> dict`
  (`store` : `NoteStore` ou dossier du journal). Pour chaque note choisie par `select_documents`, le PDF de
  www.brvm.org est téléchargé poliment (`PoliteSession`, cache `<journal>/cache/docs` ; jamais retéléchargé),
  son texte lu par `analyze.read_document`, puis une **nouvelle version** de la note est écrite
  (`store.update` : journal en ajout seul, même titre, `text` = extrait de 1 500 caractères au plus, analyse
  recalculée ; étiquette `doc_lu`, `doc_sans_chiffre`, `doc_scan` — PDF image sans texte, aucun OCR lancé, à
  lire à la main — ou `doc_illisible`, plus `ocr` si le texte vient de l'OCR d'un scanner,
  `pdf_text_layer_is_ocr`). Marques dans `analysis["extracted"]` : `doc_sha256`, `doc_pages`, `doc_method`,
  `doc_chars`, `doc_status`, `<agrégat>_source` (ligne exacte de chaque chiffre), `doc_rejected`. Une lecture
  stricte à une date passée voit toujours l'ancienne version. `offline=True` : cache seul (documents absents
  comptés dans `n_skipped`) ; `dry_run=True` : tout sauf l'écriture ; `reread=True` : relit aussi, depuis le
  cache seulement, les documents déjà lus (nouvelle version seulement si le résultat change). Un
  téléchargement en erreur n'écrit rien (nouvel essai au prochain appel) ; arrêt propre au quota, au premier
  403 ou 429, ou si le site ne répond plus. Retour : `n_candidates`, `n_selected`, `n_read`, `n_enriched`,
  `n_no_figure`, `n_scanned`, `n_failed`, `n_skipped`, `n_written`, `n_requests`, `stopped`, `dry_run`,
  `offline`, `details` (par document : `note_id`, `symbol`, `title`, `url`, `status` parmi `enrichie`, `scan`,
  `illisible`, `sans_chiffre`, `erreur`, `score_before`, `score_after`, `extracted`, `reason`, `version`,
  `written`).
- `select_documents(store, *, targets=None, now=None, panel_dir=DEFAULT_PANEL_DIR, calendar=None,
  reread=False) -> list[dict]` : notes actives, hors BOC, portant l'URL d'un PDF de www.brvm.org, pas encore
  lues, d'un type lu (`DOC_PRIORITY` : alerte sur résultats, résultats annuels et semestriels, rapports
  trimestriels, notation, puis communiqués) et encore utiles (`DOC_USEFUL_SESSIONS = 70` séances, 120 pour
  une notation) ; ordre en largeur d'abord (le meilleur document de chaque émetteur avant le deuxième d'un
  émetteur), puis par priorité, puis du plus récent au plus ancien.

### `notes/signals.py`
- `note_scores(store_or_frame, asof, half_life=10·ln 2, calendar=None, ..., tau=None) -> pd.DataFrame`
  (une ligne par cible : score décroissant `Σ s_k·exp(−Δt/τ)`, n_notes,
  dernière note, notes manuelles vs automatiques). **Décroissance** : τ = 10 séances
  (document 07 §3.4 règle 6 et §6.5 S5, `decay_tau_sessions: 10`). `half_life` reste une
  demi-vie (`2^(−Δ/h)`) ; sa valeur par défaut `10·ln 2 ≈ 6,93` reproduit exactement
  `exp(−Δ/10)` ; `tau`, s'il est fourni, est prioritaire. (Avant le 22/11/2026, le défaut
  `half_life=10` donnait `exp(−Δ/14,4)` : corrigé.)
- **Point-in-time strict** (`strict=True`, défaut de `note_scores`, `notes_asof`,
  `manual_overlays`, `notes_panel`) : une note agit à la séance
  `first_tradable_session(max(publication prudente, created_at, recorded_at))` — coupure de
  09h00 appliquée à l'instant de **connaissance** (signaux calculés avant 09h00, document 07
  §2.3) ; la version en vigueur à la séance J est la dernière écrite avant la coupure de J ;
  Δ est compté depuis cette séance effective. `strict=False` : publication seule
  (reconstitution d'historique).
- **Deux instants, deux modes** (`NotesMoment(prices_date, session, known_at, mode)`,
  `notes_moment(asof, known_at=None, calendar=None)`, `application_session(prices_date, known_at, calendar)`) :
  la **date des cours** (dernier BOC, `asof`) et l'**instant de connaissance des notes**. `known_at=None`
  (défaut de `notes_asof`, `note_contributions`, `note_scores`, `manual_overlays`, `notes_in_force`) :
  **mode historique**, règle stricte ci-dessus à la date `asof`, inchangée (dates passées, backtests,
  diagnostics, validation). `known_at=<instant UTC>` : **mode direct** (passé seulement par la ligne de
  commande, l'interface et le rapport à la dernière séance du panel) : séance d'application = `max(séance
  qui suit le dernier BOC, première séance négociable de known_at)` (la séance suivante, ou celle d'après
  si sa coupure de 09h00 UTC est passée) ; sont en vigueur les notes dont une version est écrite au plus
  tard à `known_at`, non archivées, publiées au plus tard à `known_at` (une note datée de demain n'agit
  pas) et dont la première séance négociable est au plus tard la séance d'application. Âge Δ compté
  jusqu'à la séance d'application, depuis la séance de la **publication** pour une note automatique (la date
  de collecte n'est qu'un artefact de l'outil) et depuis `max(publication, saisie)` pour une note de
  l'analyste. Une version reconstituée ne compte que si `known_at` n'est pas antérieur à l'heure réelle.
- `manual_overlays(store, asof, ..., known_at=None) -> dict` : `veto` (exclusions), `tilt`
  (ajustement borné à ±0,5 écart-type), `flags` (R1..R10 actifs), `table` (une ligne par surcouche, avec la
  note qui la porte : `published_at`, `source`, `url`), `tilt_notes`, `session`, `known_at`, `mode`.
- `notes_in_force(store, asof, *, known_at=None, calendar=None, equities="default", ...) -> dict` : état
  daté des notes : `line` (« Notes connues au JJ/MM/AAAA HH:MM UTC, appliquées à la séance du JJ/MM/AAAA :
  N en vigueur (dont M manuelles), F filtre(s) de risque actif(s) »), `scores_message` (texte clair si
  aucune note ne porte de score), `table` (notes en vigueur : connues, négociables et qui agissent encore —
  décroissance ≥ 0,001, filtre actif ou avis dans son horizon ; colonnes `IN_FORCE_COLUMNS`), `filters`
  (titre × filtre : règle, note, fin, `bloque_achats`, `lever`), compteurs `n_in_force`, `n_manual`,
  `n_scored`, `n_filters`… ; `top_notes(table, n=10)` : les plus positives et les plus négatives.
- `notes_panel(store, calendar, symbols, half_life=10·ln 2) -> pd.DataFrame`
  (date × symbole, point-in-time, mêmes règles que `note_scores`) pour l'IC walk-forward.

### `notes/index_eval.py`
- `evaluate_indices(panels, store=None, asof=None) -> pd.DataFrame` : une ligne
  par indice : niveau, rendements 1/3/6/12 mois et YTD, volatilité, drawdown,
  régime, valorisation (PER et rendement du marché/des constituants vs
  percentile historique), largeur (part des titres au-dessus de leur moyenne
  50/200 séances, hausses/baisses), saison des dividendes, score des notes,
  score composite, `stance`, `confidence`, `reasons` (liste de phrases). La composante
  « notes » n'est retenue que si au moins une note en vigueur a une contribution non nulle
  (des notes de score nul ne diluent pas les autres composantes).
- `index_dossier(index, panels, store=None, asof=None) -> dict` (détail :
  constituants, contributions, notes récentes, calendrier, « ce qui ferait
  changer d'avis »).
- `evaluate_indices(..., notes_known_at=None)` et `index_dossier(..., notes_known_at=None)` : `None`
  (défaut) = notes en règle stricte à `asof` ; un instant = mode direct (notes connues à cet instant,
  appliquées à la séance qui suit le dernier BOC ; cours inchangés). Ajouts : `attrs["notes_moment"]` et
  `attrs["notes_line"]`, colonnes `notes_detail` (notes qui portent la composante : `note_id`, `title`,
  `targets`, `note_score`, `decay`, `part`), `composite_ex_notes` et `stance_ex_notes` (score et position
  sans la composante notes) ; raisons « Notes (connues au …) », « Notes qui portent la composante »,
  « Effet des notes » ; quand la composante est absente, le motif est écrit (« notes n.d. : aucune note en
  vigueur » ou « … toutes de score nul »), jamais « n.d. » seul.
