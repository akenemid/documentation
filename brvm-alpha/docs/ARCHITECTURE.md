# BRVM Alpha — Architecture et contrats de modules

Ce document est le contrat commun à tous les modules. Toute fonction publique
listée ici doit exister avec cette signature (des arguments optionnels peuvent
être ajoutés). Code en Python 3.11+, commentaires et docstrings en français.

## Arborescence

```
brvm-alpha/
  brvm_alpha/
    config.py              # paramètres (frais, taxes, contraintes) — dataclasses
    reference.py           # métadonnées des titres : pays, secteur, fiscalité
    data/
      boc_download.py      # téléchargement des BOC (PDF -> texte .txt.gz)
      boc_parser.py        # extraction d'un BOC -> BocDay
      store.py             # panel parquet + ajustements (splits, total return)
      live.py              # cours du jour depuis www.brvm.org (page publique)
      news.py              # actualités / communiqués (brvm.org) + sentiment
    quant/
      features.py          # caractéristiques par titre et par date
      scoring.py           # normalisation transversale, composites, IC
      stats.py             # métriques, PSR/DSR, PBO, bootstrap, bêta de Dimson
      regime.py            # régime de marché (tendance / volatilité)
    portfolio/
      risk.py              # covariance (Ledoit-Wolf), HRP
      construct.py         # optimisation sous contraintes, Kelly fractionnel, lots
    backtest/
      engine.py            # moteur de backtest quotidien réaliste
      walkforward.py       # validation walk-forward / CSCV
    strategy/
      alpha.py             # le modèle BRVM Alpha (signaux de la spécification)
    report/
      html.py              # rapport HTML autonome (graphiques SVG inline)
    cli.py                 # commandes : update, panel, analyze, backtest, report
  tests/
  docs/
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

### `backtest/engine.py`
- `Backtester(panels, costs: CostModel, constraints, capital, ...)`
- `.run(strategy: Callable[[pd.Timestamp, dict], pd.Series], rebalance: str|list) -> BacktestResult`
  (`equity`, `returns`, `weights`, `trades`, `costs`, `turnover`)
- Exécution en t+1 au prix moyen pondéré (value/volume) si le titre est
  échangé, avec plafond de participation au volume ; pas d'achat à la limite
  haute ni de vente à la limite basse ; dividendes nets d'impôt crédités.

### `strategy/alpha.py`
- `BrvmAlpha(config).signals(asof, panels) -> dict[str, pd.Series]`
- `BrvmAlpha(config).target_weights(asof, panels) -> pd.Series`
- `BrvmAlpha(config).explain(asof, panels, symbol) -> dict` (décomposition du score)

Modèle v1 (SPECIFICATION_STRATEGIE.md §1.5, §2-§6, §9.1 ; paramètres = `configs/strategy_v1.yaml`) :
- `BrvmAlpha(config=None, variant="A", capital=None, params=None, *, notes="auto", country_events=None,
  dividend_calendar=None, history_start=None, risk_overlay=True, defer_sales=None, sectors=None)`
  (`variant` ∈ A…H ; `params` = surcharges du YAML, validées par `settings.load_strategy_config`)
- `.universe(asof, panels) -> DataFrame` (U1-U10 : `eligible`, `reason`, `codes`, MDV63, U6/U7…)
- `.risk_flags(asof, panels, notes="default") -> DataFrame` (R1-R12 du panel, notes de l'analyste si
  `brvm_alpha.notes` s'importe, règles pays)
- `.decide(asof, panels, held=None) -> AlphaDecision` (univers, signaux, risque, score, poids, diagnostics)
- `.strategy_fn(event_driven=False, calendar=None, mode="alpha"|"index")` : fonction
  `(asof, view) -> poids | None` pour `Backtester.run` (mémorise positions et valeur liquidative)
- `.disciplined_index_weights(asof, panels)` (mode « indice discipliné », §8.3)
- `build_panels(panel_dir) -> dict` : panels du moteur et de la stratégie (`close_raw`, `tr_index`,
  `shares`, `market_tr`, tables datées `dividends_table`, `corporate_actions`, `market`)

### `cli.py`
`python -m brvm_alpha <commande>` avec `update`, `panel`, `live`, `news`,
`analyze`, `backtest`, `report`.

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
- `manual_overlays(store, asof) -> dict` : `veto` (exclusions), `tilt`
  (ajustement borné à ±0,5 écart-type), `flags` (R1..R10 actifs).
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
