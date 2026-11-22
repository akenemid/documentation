# BRVM Alpha — Spécification de la stratégie (moteur v1)

> **Statut** : v1.0 du 22/11/2026. Document de l'architecte en chef et gérant quant. Il fait foi pour le code (`brvm_alpha/`) et remplace les valeurs `# À CALIBRER` de `brvm_alpha/config.py`.
> **Sources internes** : les neuf revues de recherche `docs/research/01` à `08`, dans leur version **corrigée par les vérificateurs** (les corrections priment toujours). Elles sont citées [R01] à [R08] ; les URL primaires qu'elles contiennent sont reprises dans la section Sources.
> **Calculs propres à ce document** : notés [C-SPEC]. Ils sont reproductibles avec `docs/annexes-spec/univ_breadth.py` et `docs/annexes-spec/tr_reconstruction.py`, sur `data/panel/*.parquet`, construit à partir des BOC locaux (2 334 BOC du 02/01/2017 au 20/11/2026 ; source : `https://www.brvm.org/sites/default/files/boc_AAAAMMJJ_2.pdf`).
> **Limites de cette session** : le budget de recherche web était épuisé (« web search budget is used up ») quand cette spécification a été rédigée. Aucune source nouvelle n'a pu être consultée. Tout repose sur les revues vérifiées, sur les BOC et sur les calculs [C-SPEC]. Les points qui restent invérifiés sont marqués **[NON VÉRIFIÉ]**.
> **Avertissement** : rien ici ne garantit un gain. Ce document décrit comment **chercher** un avantage, le **mesurer honnêtement** et **refuser** de le promettre tant qu'il n'est pas prouvé (section 10).

**Échelle des niveaux de preuve utilisée dans tout le document**

| Niveau | Sens |
|---|---|
| **P1 (fort)** | Fait de microstructure lu dans un texte primaire, ou effet mesuré sur nos BOC avec un t « par grappe » ≥ 3 et un mécanisme plausible. Mesure toujours **dans l'échantillon** |
| **P2 (modéré)** | Effet robuste dans la littérature des marchés émergents et frontières, de même signe sur nos BOC, mais non significatif localement ou qui échoue au Sharpe dégonflé |
| **P3 (faible)** | Étude unique non relue, échantillon interne court, ou sélection faite après coup |
| **P0 (réfuté ou mythe)** | Contredit par nos données ou par la littérature, ou impossible à exploiter après coûts |

---

## 0. Résumé exécutif

| # | Décision | Pourquoi (preuve) | Conf. |
|---|---|---|---|
| 1 | **L'étalon est le BRVM Composite Total Return** (dividendes nets réinvestis), jamais l'indice prix. Avant 2025, on utilise une **reconstruction exacte**, validée ici à **0,18 pb par jour** d'écart médian avec l'indice officiel | Sur 2017-2026, le TR fait **+225,5 %** (12,7 %/an) contre +72,8 % (5,7 %/an) en prix [C-SPEC]. Battre l'indice prix ne prouve rien | high |
| 2 | **Moteur principal = composite factoriel acheteur seul « A »**, pré-enregistré par [R03] : value 35 % (E/P 15, D/P 20), momentum 6-1 35 %, faible volatilité 20 %, qualité 10 % | Value et momentum dominent dans les marchés frontières (P2). Localement, le momentum 3-6 mois est positif, mais le composite échoue au DSR (0,65 < 0,95) [R03] | medium |
| 3 | **Surcouches événementielles** : calendrier du dividende (S1 capture, S2 malus après détachement), règles de risque R1-R10, règles d'événements pays | Cycle du dividende mesuré sur 313 détachements : jour ex +2,48 % (t par grappe 8,1). L'effet **décline** : +5 à +6 % en 2018-2023, environ +2,9 % en 2026 [R07] | high (calcul) / low (futur) |
| 4 | **Rejetés** : poursuite des plafonds hauts, effets calendaires, retournement à 1 mois, momentum 12-1, timing par la prime de risque du BOC, analyse technique simple, « vitesse » de lecture des nouvelles | Section 1.4 | medium-high |
| 5 | **Univers dépendant du capital** : le seuil de liquidité est un plancher de capacité, `max(0,5 M ; 0,05 × capital)` FCFA de valeur médiane par séance, et non un seuil fixe de 5 ou 10 M | Avec un seuil fixe de 2 M FCFA, l'univers tombe à **5 à 10 titres en 2019-2021** ; avec 0,5 M, il reste de 20 à 33 titres [C-SPEC] | high |
| 6 | **Portefeuille** : 12 à 20 lignes équipondérées (tiers supérieur du score), plafond de 10 % par ligne, signal mensuel, bande 30/50, participation ≤ 10 % du volume | Rotation divisée par environ 2 sans perte majeure de signal [R03] ; contraintes de capacité [R01] | medium |
| 7 | **Coûts complets dans le backtest** : courtage × (1 + taxe) + 0,20 % BRVM + 0,10 % DC/BR + demi-spread + impact, plus garde et tenue de compte. Coût aller central ≈ 1,6 à 2,1 % pour un titre médian | Barèmes primaires [B1][B6][B7] ; spread médian mesuré à 0,69 % [R01] | medium |
| 8 | **Validation pré-enregistrée** sur l'échantillon vierge 2017-01-02 → 2022-11-16 (jamais regardé), 8 variantes déclarées **avant** de le regarder, critères de succès et d'échec fixés ici | Sinon le DSR et la PBO perdent leur sens [R03][R04] | high |
| 9 | **Prédiction honnête faite d'avance** : même si l'alpha est réel (IR ≈ 0,3), le test de PSR à 95 % **échouera probablement** sur 5,9 ans (PSR attendu ≈ 0,77). Le moteur ne pourra au mieux atteindre que le statut « candidat » avant plusieurs années de suivi réel | Il faut environ 30 ans pour établir un IR de 0,3 à 95 % (MinTRL) [D] | high (calcul) |
| 10 | **Surperformance attendue a priori** : environ −1 à +3 %/an contre le TR, centre vers +1 %/an, net de coûts complets. Des années négatives sont certaines | Dérivé de [R03] (0 à +4 %, centre +2 %, hors spread) en ajoutant le demi-spread (−0,8 à −1,3 point par an) | low |
| 11 | **Pas de stop-loss mécanique par ligne** : on sortirait au plancher de −7,5 %, où les vendeurs ne sont souvent pas servis, juste avant le rebond médian mesuré de +3,1 % | [R01][R02] | medium |
| 12 | **Les règles de risque pays priment sur l'alpha** : sanctions UEMOA = gel des achats sur 60 séances et ventes échelonnées dès t+1 | Niger 2023 : −26 % en 9 séances ; Mali 2022 : −7,47 % dès t+1 [R05] | high (cas) / low (fréquence) |
| 13 | **Aucun gain garanti.** Les gérants professionnels de la zone ne battent le TR que dans environ 28 à 30 % des années-fonds [R08]. Un marché qui a perdu −46,7 % en TR (2017-2020) peut recommencer | Section 10 | high |

---

## 1. Thèse d'investissement

### 1.1 Ce qu'il faut battre : les faits mesurés

| Fait | Valeur | Date des faits | Conf. | Source |
|---|---|---|---|---|
| Sociétés cotées | 48 (12 Prestige, 36 Principal) | 20/11/2026 | high | BOC n° 222 [B4] |
| BRVM Composite (prix) | 492,89 ; +42,56 % depuis le 31/12/2025 | 20/11/2026 | high | [B4] |
| BRVM Composite Total Return (base 100 au 02/01/2025) | 198,63 ; +49,19 % depuis le 31/12/2025 | 20/11/2026 | high | [B4] ; avis 308-2025 [B9] |
| PER moyen ; rendement moyen ; « prime de risque du marché » | 15,79 (hors UNLC) ; 7,12 % ; 0,58 | 20/11/2026 | high | [B4] |
| Capitalisation actions | 19 328,8 Md FCFA | 20/11/2026 | high | [B4] |
| **Composite TR reconstruit, du 03/01/2017 au 20/11/2026** | **+225,5 %, soit 12,7 %/an** (prix : +72,8 %, 5,7 %/an) | 2017-2026 | high (calcul validé) | [C-SPEC] |
| TR reconstruit par année | 2017 −10,5 % (depuis le 02/01/2017 ; prix −14,8 % sur la même fenêtre) ; 2018 −25,1 % ; 2019 −1,2 % ; 2020 −2,1 % ; 2021 +48,9 %* ; 2022 +7,9 % ; 2023 +14,0 % ; 2024 +38,5 % ; 2025 +33,1 % ; 2026 +49,2 % (au 20/11) | 2017-2026 | high (2025-2026 officiels), medium (avant) | [C-SPEC] ; *2021 contient des trous de BOC, d'où des dividendes peut-être manquants |
| Drawdown maximal du TR | **−46,7 %** (pic le 01/03/2017, creux le 26/10/2020, retour au pic le 25/02/2022) | 2017-2022 | high | [C-SPEC] |
| Drawdown maximal du Composite prix | −59,8 % depuis la clôture 2015 (303,93 → 122,19 au 26/10/2020) ; environ 9 ans et demi sous l'eau en prix | 2015-2025 | high | [R08] (rapports annuels BRVM et BOC) |
| Volatilité du TR | 12,1 %/an (hebdomadaire), 15,7 %/an (mensuelle) | 2017-2026 | high | [C-SPEC] |
| Part des fenêtres de 12 mois négatives (Composite prix) | 43 % | 2017-2026 | high | [R08] |
| Fonds actions UEMOA (catégorie A du BOC) qui battent le TR | **26 à 28 sur 93 années-fonds (28 à 30 %)** ; écart médian de −6,0 à −4,8 points par an | 2017-2026 | medium | [R08] |

**Validation de la reconstruction du TR [C-SPEC]**. Méthode :
1. nombre de titres actuel (avis 303-2026 [B8], tableau de [R01] §11), propagé vers le passé avec les 50 fractionnements et ajustements de capital détectés (`corporate_actions.parquet`, confiance high) ;
2. `r_TR,t = r_Composite,t + Σ_i N_i,t × D_net,i,t / Cap_publiée,t−1`, avec les dividendes nets de `dividends.parquet`.

Résultats :
- la capitalisation reconstruite (Σ N × P) reproduit la capitalisation publiée au BOC à **0,0 à 2,8 %** près sur 2017-2026 ;
- sur les 219 séances de 2026 où l'indice officiel existe, l'écart quotidien vaut 0,18 pb en médiane (0,22 en moyenne, 2,1 au maximum) ;
- niveau reconstruit au 20/11/2026 : **198,45, contre 198,63 publié** (−0,09 % en cumul).

C'est l'étalon officiel du backtest avant le 02/01/2025.

### 1.2 Inefficiences documentées et exploitables

| # | Inefficience | Mesure | Niveau | Exploitable après coûts ? | Usage dans le moteur | Source |
|---|---|---|---|---|---|---|
| E1 | **Cycle du dividende** : la baisse du cours au détachement est incomplète (PDR médian 0,46), avec une montée avant et une baisse après | Jour ex : AR moyen +2,48 % (t par grappe 8,1, 79 % > 0) ; [−20,−1] +2,54 % (t par grappe 4,2) ; [+1,+20] −2,54 % (t par grappe −2,0, non significatif après Bonferroni) ; 313 détachements, 2017-2026 | **P1** (dans l'échantillon) | **Marginal et en déclin** : fenêtre avis → détachement +4,07 % brut en moyenne, environ +2,9 % en 2026 ; net de 1,7 à 2,8 % de coûts : −0,5 à +1,7 % en 2024-2026 | S1 (poche ≤ 20 %, activée seulement si les coûts réels sont bas), S2 (malus) et règles de calendrier d'exécution (§5.2) | [R07] §4.3-4.4, §9 |
| E2 | **Momentum court-moyen terme (3-6 mois)**, sans écho à 12-7 mois | L/S tertiles 6-1 : +2,10 %/mois (t NW 2,34) ; reproduction +2,47 (t 2,72) ; 12-1 nul ; 12-7 négatif ; 2022-2026 | **P2** | Rotation de 0,28/mois sans bande ; avec la bande 30/50 : 0,15. Le composite B (value × momentum) a un DSR de 0,65 seulement | Bloc momentum de A (35 %) | [R03] §7, §12 ; de Groot et al. 2012 [A10] |
| E3 | **Value (E/P, D/P)** | Forte dans les marchés frontières (de Groot ; Zaremba & Maydybura) ; **nulle** localement en 2023-2026 (marché très haussier) | **P2** (littérature) / P3 (local) | Rotation faible (0,12/mois), donc coût faible | Bloc value de A (35 %) | [R03] ; [A10][A11] |
| E4 | **Faible volatilité**, prime **dépendante du régime** | +2,04 %/mois (t 3,47) en 2023-2024 ; −2,48 % en 2025-2026 (phase la plus haussière) | **P2** (défensif) | Rotation faible | Bloc faible volatilité de A (20 %) | [R03] ; Blitz, Pang & van Vliet 2013 [A14] |
| E5 | **Dérive après une bonne publication** (comptes annuels et T1) | AR[0,+1] ≥ +3 % → CAR[+3,+22] +6,9 % (n = 73, t par grappe 3,7) ; groupe témoin sans publication : +0,7 % | **P3** (sélection après coup, saisonnalité non contrôlée) | Inconnu | S4 **désactivé** jusqu'à validation sur 2017-2021 avec un témoin apparié par mois | [R07] §4.6, §9 |
| E6 | **Sous-évaluation à l'introduction, étalée sur plusieurs séances au plafond** | BBGC : 4 séances à la borne haute ; ORAC +7,47 % et LNBB +7,50 % le 1er jour ; sous-évaluation significative après 2011 (une étude) | **P2** (mécanique) / P3 (ampleur) | Seulement si l'on obtient une allocation, souvent réduite | Module IPO (aide à la décision, §5.8) | [R01] §3.3 ; [R02] §6 ; [A20] |
| E7 | **Faible corrélation entre pays** (0,03 à 0,33 en hebdomadaire) | Calcul sur les BOC 2021-2026 | **P1** | C'est une source de **diversification**, pas d'alpha | Plafonds pays (§4.2) | [R05] §9.1 |
| E8 | **Coûts et erreurs de données évitables** : splits non ajustés (faux −89,3 % sur SNTS), PER sur le résultat total (ETIT 2,98 contre 5,7), rendements périmés (FTSC 107,9 %), dividende BOAC erroné | Constats primaires | **P1** | Oui : c'est un avantage **certain** sur l'investisseur qui utilise des données brutes, mais ce n'est pas un rendement garanti | Contrôles de données obligatoires (§3.1, §5) | [R06a] §8 ; [R06b] §6 ; [R08] §2.3 |

### 1.3 Hypothèses plausibles mais non démontrées (désactivées par défaut)

| Hypothèse | Mesure | Pourquoi elle reste désactivée | Source |
|---|---|---|---|
| Rebond après un plafond bas (clôture ≤ −7 %) | Ouverture t+1 → clôture t+5 : médiane +3,09 %, 62 % > 0, n = 396 (2025-2026, répliqué) | Net d'environ 2,5 % de coûts : environ +0,6 % ; marché haussier ; événements regroupés (jusqu'à 14 le même jour) | [R02] §7.1 |
| Montée avant l'AGO (S3) | Fenêtre réellement négociable : +1,36 % en moyenne | Inférieure aux coûts d'un aller-retour | [R07] §6.5 |
| Retour à la moyenne à court terme des indices (demi-vie de 7 jours, Gbenro & Moussa 2019) | **[NON VÉRIFIÉ]** : texte non lu ; ρ1 du Composite = 0,012 sur 2024-2026 | Grandeur modélisée inconnue ; `use_prior: false` | [R02] §3 ; [A19] |
| Tendance de l'indice (VR(20) > 1) | Significative seulement en 2026 ; VR < 1 en 2024-2025 | Un seul épisode | [R02] §7.1 |
| Momentum pays | Indirect (de Groot) **[NON VÉRIFIÉ]** pour les indices pays | 7 pays, dont 6 avec 1 à 3 titres : du bruit | [R05] §13.2 |
| Prévisibilité par M1 et M2 (BCEAO) | Une étude, conclusions jugées fragiles | Délai de publication, données non accessibles (bceao.int bloqué) | [R02] §3 |
| Score de sentiment textuel (S5) | Aucun IC mesuré | Poids 0 tant que l'IC walk-forward ≤ 0,05 sur 3 ans | [R07] §3, §6.5 |

### 1.4 Mythes et pièges (rejetés, niveau P0)

| Mythe | Ce que montrent les données | Source |
|---|---|---|
| « Acheter les titres qui touchent le plafond haut » | La continuation se fait dans le **gap de la nuit** (+2,97 % en moyenne), impossible à capter. Depuis l'ouverture de t+1, la médiane à 5 jours vaut +0,14 % contre +0,07 % sans condition | [R02] §7.1 |
| Effets calendaires exploitables (lundi, décembre, Ramadan) | Instables d'une étude, d'un indice et d'une fenêtre à l'autre ; effet jour de la semaine non validé en fenêtre glissante | [R02] §4 ; Obalade et al. 2022 [A21] |
| Retournement à 1 mois | Sur la BRVM, c'est une **continuation**. Rotation de 0,66/mois, soit environ 20 %/an de coûts | [R03] §4.2, §7.2 |
| Momentum 12-1 « standard » | Nul localement (+0,38 %/mois, t 0,35) ; 12-7 négatif | [R03] §7.2 |
| Prime de taille | Pas de prime fiable (Fama-French 2012 ; Zaremba & Maydybura 2019) | [R03] §1 |
| « Le marché est cher, il faut sortir » (prime BOC < 1 %) | Corrélation **négative** entre la prime et les rendements futurs sur 2021-2026 : ce n'est pas un signal de timing | [R05] §1.2 |
| Filtre de régime ou de tendance comme source d'alpha | 3 croisements de la moyenne mobile 200 séances en 2022-2026 ; l'état « agité » a eu le meilleur rendement | [R04] §14 |
| Analyse technique simple (moyennes mobiles) | N'a pas battu l'achat-conservation dans le seul test BRVM trouvé | [R02] §11 ; [A22] |
| L'avantage de vitesse sur les nouvelles | 92 % des avis sont publiés hors séance ; la presse arrive 1 à 3 jours **après** le document officiel | [R07] §2 |
| Apprentissage automatique (LSTM…) déjà validé sur la BRVM | Aucune étude évaluée par les pairs | [R02] §11 |
| « Battre le Composite » = surperformance | Le Composite est un indice prix : il omet environ 6,6 à 7,9 points de dividendes par an | [R01] §10.3 ; [R08] §4.5 |
| Un gain garanti à 100 % | Même un vrai Sharpe de 1,0 perd une année sur six ; aucune étude ne montre de gain garanti sur la BRVM | [R04] §0 ; section 10 |

### 1.5 Thèse retenue

> Sur un marché de 48 titres, peu profond et dominé par le dividende, l'avantage durable le plus probable n'est **pas** la prédiction de court terme. Il vient de la **combinaison disciplinée de primes lentes** (value, rendement, momentum court-moyen terme, faible volatilité), d'une **exécution qui respecte la microstructure** (bandes de ±7,5 %, calendrier des dividendes, liquidité) et d'un **contrôle strict des coûts, des données et du risque pays**. Tout cela est mesuré contre le **TR**.

Architecture en couches (ordre de priorité décroissant) :
1. **Données correctes** (point-in-time, splits, dividendes nets, PER corrigés).
2. **Filtres de risque** R1-R10 et **règles d'événements pays**. Ils priment sur tout signal.
3. **Univers** (liquidité dépendant du capital).
4. **Score factoriel A** (sélection mensuelle).
5. **Surcouches de calendrier** (S2 toujours, S1 sous condition de coûts).
6. **Construction** (équipondérée sous plafonds) et **exécution** réaliste.

---

## 2. Univers et filtres de liquidité

Tous les filtres sont évalués **à la date t** (point-in-time), avec les seules informations publiées au plus tard en t.

| # | Filtre | Règle exacte | Justification | Source |
|---|---|---|---|---|
| U1 | Cotation | Titre présent au BOC de t ; statut ≠ `suspended` (SP) en t ; exclu jusqu'à la reprise + 5 séances (R1) | Risque de liquidité | [R01] §8.3 ; [R07] §6.6 |
| U2 | Historique | ≥ 126 séances cotées (les signaux momentum 6-1 l'exigent) ; ≥ 40 séances avec rendement sur les 63 dernières | Signaux définis | [R03] §7.1 |
| U3 | Prix périmés | Part des séances avec échange ≥ **50 %** sur les 120 dernières séances (`UniverseFilter.min_traded_fraction`) | Les cours non échangés faussent les signaux | [R04] §2.1 |
| U4 | Flottant | Flottant BRVM ≥ **15 %** (seuil réglementaire de diffusion), d'après le dernier avis publié à la date t. Au 20/11/2026, sont exclus UNLC (0,22 %), CFAC (4,15 %), SEMC (10,29 %) et SICC (12,26 %) | Seuil réglementaire ; carnet artificiel | avis 303-2026 [B8] ; [R06b] §1.2 |
| U5 | **Capacité (dépend du capital K)** | `MDV63_i ≥ max(500 000 ; 0,05 × K)` FCFA, où MDV63 = médiane de la valeur échangée sur 63 séances, **séances sans échange comptées à 0** | Dérivation : poids max 10 %, participation 10 %, sortie en 20 séances ⇒ MDV ≥ 0,10·K/(0,10 × 20) = 0,05·K. Plancher de 0,5 M pour la qualité des cours | [C-SPEC] ; [R01] §12.3 |
| U6 | Liquidité faible | Si 0,05·K ≤ MDV63 < 2 M FCFA : poids maximal divisé par 2 (niveau « C ») | Profondeur | [C-SPEC] ; [R02] §13 |
| U7 | Spread | Si le spread médian de clôture sur 120 séances > **1,5 %** : poids maximal divisé par 2 (ETIT : 2,99 %) | Coût | [R06a] §9.4 |
| U8 | Introduction en bourse | Hors du moteur factoriel pendant 126 séances (U2) ; module IPO séparé (§5.8) | Signaux non définis ; plusieurs séances bloquées au plafond | [R01] §3.3 |
| U9 | Comptes périmés | Exclusion si les derniers comptes annuels portent sur un exercice clos depuis plus de 546 jours (soit le 30/06 de N+1 pour l'exercice N−1) ; au 20/11/2026, UNLC et SEMC | Information périmée | [R06b] §7.1 |
| U10 | Taille minimale de l'univers | `N_elig ≥ 15`, sinon portefeuille = panier équipondéré des titres éligibles (mode « repli ») | Avec moins de 15 titres, aucune sélection en tertiles n'a de sens | [R03] §8.3 ; [R04] §16 |

**Pourquoi un seuil qui dépend du capital, et non 5 ou 10 M FCFA ?** Les seuils des revues 01 et 02 (5 M, 10 M) ont été calibrés sur 2025-2026. Or la liquidité de la BRVM a été **multipliée par environ 30** entre 2019-2020 et 2026 : la médiane des valeurs médianes par titre, les jours d'échange, est passée de 0,4-0,6 M FCFA à 17,5 M FCFA [C-SPEC]. Un seuil fixe rendrait l'historique inutilisable :

| Année (médiane des fins de mois) | Titres cotés | U3 seul | U3 + MDV63 ≥ 0,5 M | U3 + MDV63 ≥ 2 M | U3 + MDV63 ≥ 5 M | U3 + MDV63 ≥ 10 M |
|---|---:|---:|---:|---:|---:|---:|
| 2017 | 43 | 34 | 28 | 19 | 8,5 | 5 |
| 2018 | 45 | 38 | 28 | 16 | 9 | 4 |
| 2019 | 46 | 38 | 22 | 9 | 2,5 | 1 |
| 2020 | 46 | 38 | 20,5 | 5,5 | 2 | 1 |
| 2021 | 46 | 40,5 | 26 | 9,5 | 3 | 2 |
| 2022 | 46 | 43 | 33 | 17,5 | 7 | 4 |
| 2023 | 46 | 43 | 30 | 17,5 | 10,5 | 5 |
| 2024 | 46 | 41 | 32,5 | 23,5 | 15,5 | 8 |
| 2025 | 47 | 45 | 39,5 | 33,5 | 24 | 16,5 |
| 2026 | 47 | 47 | 46 | 45 | 40 | 31 |

Source : [C-SPEC], `docs/annexes-spec/univ_breadth.py` sur `data/panel/equities.parquet` (BOC 2017-2026). Confiance high pour le calcul. Les suspensions sont exclues et le flottant (U4) n'est pas appliqué ici.

**Conséquences codées** :
- capital de référence du backtest K = 10 M FCFA, avec deux variantes de capacité : K = 100 M (plancher de 5 M) et K = 1 Md (plancher de 50 M). Le rapport affiche la **capacité** : rendement net en fonction de K ;
- en 2019-2021, à K = 100 M, l'univers est trop étroit et la stratégie passe en mode repli. C'est un **fait de marché**, pas un défaut du modèle.

---

## 3. Signaux et facteurs

### 3.1 Conventions communes (données, dates, transformations)

1. **Prix** : uniquement le BOC (clôture, cours de référence, volume, valeur). Jamais le bandeau du site, jamais les transactions sur dossier [R01] §2.2.
2. **Rendement total quotidien du titre i** :
   - `r_i,t = (C_t + D_net,i,t · 1[t = jour ex]) / (C_{t−1} / f_i,t) − 1` ;
   - C est la clôture **non ajustée** ; f_i,t est le facteur de split ou d'attribution du jour (1 sinon) : SNTS 10 le 26/10/2026, SLBC 10 le 30/09/2024, attributions de 2024 (BOAM, BOAS 1,5 ; BOABF, BOAB, BOAC, SIBC 2 ; BOAN 1,6), DPS SAFC 1/0,7066 le 24/04/2026 ;
   - le dividende D_net est lu sur la ligne « (d) » du BOC, jamais sur les BOC suivants (BOAC : 594,53, et non 597,53) ;
   - ne jamais utiliser comme rendement la « Variation jour » ni le « Cours précédent » des lignes (V) ([R01] §7 ; [R06a] §8).
3. **Lignes spéciales** :
   - `NC` (non coté) : rendement 0, marqué périmé ;
   - `SP` : exclu ;
   - un rendement sur un trou de plus de 4 jours calendaires (BOC manquant) est marqué `multi_session`. Il est exclu des estimations de volatilité, de bêta et de covariance, mais gardé pour chaîner le TR ;
   - **2021** : la période du 06/05 au 25/06/2021 (trou de 50 jours) est exclue des statistiques ;
   - un BOC absent n'est pas un jour férié : il faut contrôler la continuité des numéros de BOC ([R01] §2.1 ; [R04] §2).
4. **Pas de biais d'anticipation** : tout signal calculé à la clôture de t ne sert qu'à des ordres exécutés à partir de t+1. Les fondamentaux ne sont disponibles qu'à la première séance dont la pré-ouverture (09h00 UTC) suit l'en-tête `Last-Modified` du PDF. Sans cet en-tête, le délai est de 2 séances après la date du nom de fichier ([R06a] §9.1).
5. **Dates de rebalancement** : dernière séance BOC de chaque mois civil (t_m). Exécution à partir de t_m + 1.
6. **Transformation transversale**, sur l'univers éligible U_t :
   - (a) winsorisation des valeurs brutes aux centiles 1 et 99 ;
   - (b) z de rang gaussien `z = Φ⁻¹((rang − 0,5)/N)`, écrêté à ±3 (`cross_sectional_zscore(winsor=3.0, method="rank_gauss")`) ;
   - (c) valeur manquante → z = 0.
   Les rangs rendent le score robuste aux PER extrêmes (UNLC 631, BNBC 519) [R03] §2.2.
7. **Neutralisation** : **aucune** dans la variante principale A (pré-enregistrée par [R03]). La neutralisation sectorielle de la value est testée dans la variante D (§3.4). Pays et secteurs sont contrôlés par des **plafonds de portefeuille** (§6), pas par le signal. Raison : 7 pays dont 6 comptent 1 à 3 titres ; une neutralisation par pays serait du bruit.

### 3.2 Signaux de la variante principale A (pré-enregistrés)

| Signal | Définition mathématique exacte (en t) | Sens | Poids a priori | Justification | Niveau |
|---|---|---|---|---|---|
| **EP** (rendement bénéficiaire) | `ep_i = 1/PER_i` si PER_i > 0, sinon rang minimal. PER = PER du BOC en t, **sauf** surcharges point-in-time : ETIT (BPA part du groupe 2025 = 10,00 FCFA, soit PER ≈ 5,7) et ORGT (BPA de base 264). Dès que la table des fondamentaux existe : PER = capitalisation / RN **part du groupe** (SNTS, ORAC) | + (élevé = mieux) | **0,15** | Value robuste dans les marchés frontières (de Groot 1,53 %/mois brut L/S **[NON VÉRIFIÉ]**) | P2 |
| **DY** (rendement net du dividende) | `dy_i = DPS_net_ordinaire(k) / C_t`, où k est le dernier exercice dont l'**AGO est connue** en t ; dy = 0 si cette AGO n'a voté aucun dividende ; dy = 0 si le dernier paiement a plus de 15 mois (garde-fou). Dividendes exceptionnels exclus (FTSC) ; DPS ajusté des splits ; écrêté à 15 %, avec un drapeau au-delà. Repli v1 tant que les AGO ne sont pas collectées : `net_yield_pct` du BOC, avec le garde-fou de 15 mois et une liste d'absences de dividende annoncées (BOAN 2025, ORGT, SAFC) | + | **0,20** | Rendement moyen du marché d'environ 7 % ; composante value naturelle | P2 |
| **MOM6_1** | `mom_i = TR_i(t−21) / TR_i(t−126) − 1`, en séances (formation d'environ 6 mois, saut de 21 séances) ; au moins 100 rendements valides dans la fenêtre | + | **0,35** (modulé, ci-dessous) | Momentum court-moyen terme dans les frontières, sans écho à 12-7 (Goyal & Wahal 2015) ; local : t NW 2,34 | P2 |
| **LOWVOL** | `lv_i = −σ_i`, écart-type des rendements quotidiens de 250 séances (au moins 200 observations, hors `multi_session`) ; repli sur 126 séances (au moins 100) | − sur σ | **0,20** | Facteur défensif (Blitz, Pang & van Vliet 2013) ; inversé en marché haussier | P2 |
| **QUAL** (v1, proxy) | `q_i = ½·rang(années avec dividende sur les 5 derniers exercices) + ½·1[3 ≤ PER_i ≤ 40]`. **v2** (quand les fondamentaux point-in-time existeront) : FIN = score Q de [R06a] §9.2 (ROE, qualité d'actifs, stabilité) ; non-FIN = qualité de [R06b] §7.2 | + | **0,10** | Évite les pièges de rendement ; volet « distribution » de QMJ | P3 |

**Modulateurs du bloc momentum (pré-enregistrés dans A, ce ne sont pas des essais séparés)** :
- **Dosage par la volatilité** (Barroso & Santa-Clara 2015 [A6], adapté) : `w_mom,t = 0,35 × clip(σ_cible / σ̂_126(spread_mom), 0,5 ; 1)`. Ici spread_mom est le rendement quotidien du tiers supérieur en MOM6_1 moins le panier équipondéré de l'univers, et σ_cible la médiane expansive de σ̂_126 (au moins 24 mois d'historique, sinon multiplicateur = 1). Le poids libéré est réparti au prorata sur les autres blocs.
- **Filtre de crash** (inspiré de Daniel & Moskowitz 2016 [A7]) : si le TR (reconstruit avant 2025) est en baisse sur 24 mois **et** que sa volatilité sur 63 séances dépasse le 80ᵉ centile de son historique expansif, alors `w_mom × 0,5` pendant 3 mois.

**Score composite** : `S_i,t = Σ_b w_b,t × z_b,i,t` sur les blocs EP, DY, MOM6_1, LOWVOL et QUAL. Si moins de 3 blocs sont valides pour un titre, S = 0 (neutre). Puis le malus S2 (§5.2) est ajouté, et S est de nouveau standardisé en rang.

### 3.3 Signaux de recherche (calculés, journalisés, poids nul)

`mom3_1`, `mom6_0`, `mom12_1`, `mom12_7`, momentum résiduel (résidus sur le marché, avec le bêta de Dimson à 1 avance et 5 retards, et sur le pays), continuation à 1 mois (`str1` de signe +), illiquidité d'Amihud (63 séances, en log), bêta de Dimson (504 séances), score de sentiment S5, signaux pays. Chacun est calculé sur l'historique et son IC est journalisé dans le registre des essais (`TrialRegistry`) ; aucun n'entre dans le score tant qu'il n'a pas franchi les filtres G1-G9 (§8). Sources : [R03] §9, [R04] §13, [R07] §6.5.

### 3.4 Variantes pré-enregistrées pour l'échantillon de validation (N = 9 depuis l'additif v1.1, §8.4)

Elles sont **déclarées ici, avant** toute exécution sur 2017-01-02 → 2022-11-16.

| Code | Description | Rôle |
|---|---|---|
| **A** | Signaux et poids du §3.2, équipondéré, mensuel, bande 30/50 | Principal (pré-enregistré par [R03]) |
| B | EP 0,25, DY 0,25, MOM6_1 0,50 | Challenger : le meilleur résultat de 2022-2026, **choisi après coup** (DSR 0,65) |
| C | EP 0,15, DY 0,20, MOM6_1 0,20, MOM12_1 0,15, LOWVOL 0,20, QUAL 0,10 | Challenger : horizon long « standard » |
| D | A, avec EP et DY classés **à l'intérieur des secteurs** de 4 titres ou plus (FIN, CB, CD, IND, ENE) ; les autres secteurs sont regroupés | Test de neutralisation sectorielle de la value |
| E | A + poche S1 (capture du dividende, ≤ 20 %) | Valeur de la surcouche S1 |
| F | A + baisse de 25 % de l'exposition en régime agité (§4.4) | Valeur du dosage par le régime |
| G | A pondéré par `hrp_tilt` (HRP sur une covariance de Ledoit-Wolf hebdomadaire, γ = 0,5) | Pondération par le risque |
| H | A pondéré par `mv_alpha` (alpha de Grinold avec IC_post = 0,02 ; λ = 5 ; κ = coût aller central) | Optimisation moyenne-variance rétrécie |
| I | **Cœur-satellite** : 50 % « indice discipliné » (§8.4, D8) + 50 % A. Ajoutée par l'additif v1.1 (§8.4, D9), **avant** toute exécution sur S1 | Réduction du pari structurel contre l'étalon (TEL, SNTS) |

**Règle de promotion** : A reste le principal. Une variante X ne remplace A que si, sur l'échantillon de validation, X bat A en rendement actif net **et** franchit DSR ≥ 0,95 avec N = 9 (famille de l'additif v1.1) **et** a une PBO ≤ 0,25 sur la famille ([R03] §8.4, `promotion_rule`).

### 3.5 Apprentissage des poids (phase 2, après la validation)

- **Phase 1 (validation)** : poids **figés** = A. Aucun réglage.
- **Phase 2 (walk-forward, dès qu'il existe au moins 36 mois d'IC hors échantillon)** :
  1. IC mensuel de Spearman de chaque bloc, horizon de 21 séances, avec un délai d'une séance et au moins 15 titres par date ;
  2. rétrécissement bayésien `IC_post = k·IC_mesuré + (1 − k)·IC_prior`, avec k = n/(n + 36), IC_prior = 0,02 pour les blocs documentés et 0 pour un nouveau signal, et IC_post plafonné à 0,08 ;
  3. poids de l'IR maximal `w_IC ∝ max(0, Σ̂_IC⁻¹ · IC_post)`, normalisés à une somme de 1, avec Σ̂_IC la covariance des séries d'IC rétrécie par Ledoit-Wolf ;
  4. **rétrécissement vers des poids égaux** : `w = 0,5·w_IC + 0,5·w_EQ`, avec w_EQ = 1/K sur les blocs actifs (`shrunk_ic_weights(..., shrinkage=0.5)`) ;
  5. walk-forward expansif : `walk_forward_windows(train_years=2, test_months=3, embargo_days=42, expanding=True, min_train_days=480)` ;
  6. la version apprise (A-WF) est un essai de plus dans le registre ; elle ne remplace A que selon la règle de promotion.
- **Momentum de facteurs** : interdit tant qu'on n'a pas 120 mois de séries de facteurs propres à la BRVM.

Sources : [R04] §15.4, §16.4, §17.2 ; DeMiguel, Garlappi & Uppal 2009 [A9] ; Grinold-Kahn, et Clarke et al. 2002 [A15].

---

## 4. Overlay macro, pays et régime

### 4.1 Grandeurs de référence

| Grandeur | Règle | Valeur au 20/11/2026 | Conf. | Source |
|---|---|---|---|---|
| Taux sans risque local `rf` | `100/PER_moyen − prime_BOC`, médiane glissante sur 20 séances. Un jour isolé qui s'écarte de plus de 0,10 point est ignoré ; un changement de régime exige 5 séances consécutives au nouveau niveau | **5,75 %** (depuis le 05/01/2024 ; 5,90 % du 22/02/2021 au 29/12/2023 ; 6,00 % puis 6,50 % en 2018-2020) | high | [R05] §1.2 ; [B4] |
| Courbe ivoirienne (proxy sans risque) | coupons des émissions TPCI au BOC | 5,45 % (5 ans) ; 5,70-5,85 % (7 ans) ; 6,00 % (10 ans) | high | [R05] §6.1 |
| Spread local / CI (points de %) | recalculé à chaque nouvelle émission APE | BJ 0,05 ; ML 0,57 ; TG 0,92 ; NE 0,95 ; SN 0,97 ; BF 1,07 | high | [R05] §6.2 |
| CRP relative à la CI | `CRP_c = 1,5 × LS_c + (p_sév × 21 % + p_mod × 8 %)_c − (idem)_CI` | CI 0 ; BJ 0,9 ; TG 2,2 ; SN 3,05 ; ML 4,1 ; NE 5,1 ; BF 5,3 ; hors UEMOA 4,0 % | medium (p_sév et p_mod sont des hypothèses d'expert) | [R05] §12.2 |
| Exposition économique λ | 1 pour le pays du siège, sauf SNTS (variante détention : SN 0,401 ; ML 0,238 ; GN 0,274 ; SL 0,045 ; GW 0,042) et ETIT (panafricain) | — | medium | [R05] §11.2 |
| Poids de référence par pays du siège b_c (capitalisation) | cours × nombre de titres | CI 57,78 ; SN 22,94 ; BF 7,29 ; TG 6,24 ; BJ 4,55 ; ML 0,72 ; NE 0,48 % | high | [R05] §11.1 |

Usages : `rf` et CRP alimentent le **coût des fonds propres** `k_i = rf + β_i × 4 % + Σ_c λ_ic CRP_c` des lignes de base de valorisation (DDM, revenu résiduel des banques ; [R08] §6.1). Ces lignes sont affichées dans `explain()`, mais **n'entrent pas dans A**. Le score géographique S_c de [R05] §13.2 est calculé et journalisé avec un poids nul : il a été conçu pour un portefeuille pondéré par la capitalisation, incompatible avec la sélection équipondérée de A.

### 4.2 Plafonds pays (toujours actifs)

1. **Multiplicateur du poids maximal par ligne** (jugement, non validé, [R06a] §9.4) : CI 1,0 ; BJ 1,0 ; TG 0,9 ; SN 0,85 ; BF 0,75 ; ML 0,7 ; NE 0,6. Poids max d'une ligne = 10 % × multiplicateur × réductions U6/U7.
2. **Plafond par pays du siège c ≠ CI** : `w_c ≤ min(30 % ; max(10 % ; 1,5 × max(u_c, b_c)))`, avec u_c la part (en nombre) du pays dans l'univers éligible.
3. **Bloc AES (BF + ML + NE)** : ≤ 1,25 × sa référence de capitalisation par pays du siège (≈ 10,6 % aujourd'hui), **et** ≤ 1,25 × sa référence en exposition économique λ (≈ 18 %) [R05] §13.3.
4. **CI** : aucun plafond propre au-delà de la diversification sectorielle.

### 4.3 Règles d'événements pays (elles priment sur le score)

| Déclencheur (lu dans les flux §5, horodaté) | Action | Durée | Base empirique | Source |
|---|---|---|---|---|
| **Sévère** : sanctions financières UEMOA/BCEAO (gel), défaut souverain, annonce de sortie de l'UEMOA ou de la BCEAO, coup d'État suivi de sanctions | Poids du pays ≤ 0,25 × min(b_c, u_c) ; aucun achat ; ventes dès l'ouverture de t+1 en ordres à cours limité échelonnés (au plus la participation de 10 % par séance) ; **le backtest suppose que la 1re séance est au plancher de baisse sans vendeur servi** | 60 séances, puis retour progressif sur 20 séances si la volatilité sur 20 jours < 1,5 × la normale | Niger 2023 : −26,2 % au creux ; Mali 2022 : −7,47 % à t+1, −16,9 % en 3 séances | [R05] §9, §13.4 |
| Coup d'État **sans** sanctions UEMOA | P_c = −2 ; aucun achat ; poids ≤ référence | 20 séances | BF 01/2022 et 09/2022 : −4 à −13 % ; ML 08/2020 : −1,5 % | [R05] §13.4 |
| Levée de sanctions, accord avec le FMI | Achats de nouveau autorisés jusqu'à la référence | 20 séances | Mali 07/2022 : +35,7 % brut en 5 séances ; Niger 02/2024 : +11,6 % brut | [R05] §9 |
| Élection présidentielle | Aucune surpondération de J−30 à J+10 | 40 séances | CI 2025, SN 2024 : pas de crise | [R05] §13.4 |
| Dégradation souveraine de 2 crans ou plus, ou révélation budgétaire | Spread de stress majoré de 0,5 point ; plafond pays × 0,75 | 120 séances | Sénégal 09/2024 : −8,9 % en 60 séances | [R05] §13.4 |
| Décote médiane des obligations souveraines du pays < 0,97 sur 20 séances, avec **au moins 5 transactions** | Plafond pays × 0,75 ; aucune surpondération | tant que la condition dure | SN 2026 : 0,98 (64 à 84 transactions par trimestre) ; NE : non concluant | [R05] §6.3, §13.4 |

Ces règles sont des **règles de risque**, pas de l'alpha : elles sont actives dans toutes les variantes. Paramètres de choc pour les stress tests : perte sévère de 21 % (stress 26 %), perte modérée de 8 % [R05] §12.

### 4.4 Régime de marché (dosage du risque seulement)

- **Modèle** : chaîne de Markov à 2 états (moyenne et variance) sur les rendements **hebdomadaires du TR reconstruit**. Ré-estimation mensuelle en fenêtre expansive depuis 2017 (2021 traité à part) ; **probabilités filtrées seulement** (`quant/regime.py`, `hmm_filtered_probabilities`).
- **Règle de la variante F** (désactivée dans A) : exposition actions × 0,75 si P(agité) > 0,8 **et** drawdown du TR < −8 %. Retour à 100 % quand P(agité) < 0,5 pendant 4 semaines.
- **Interdits** : tout timing d'alpha fondé sur le régime tant qu'on n'a pas **au moins 10 changements de régime indépendants hors échantillon**. Le filtre de tendance (moyenne mobile 200 séances ± 2 %) n'est qu'un challenger d'information.
- Justification : sur 2022-2026, l'état agité a eu le **meilleur** rendement, avec seulement 3 croisements de la moyenne mobile 200 séances ; 2017-2020 en compte 13 [R04] §14.

### 4.5 Valorisation du marché (information, jamais un signal de timing)

- Bandes de la prime du BOC : **chère** < 1 % ; neutre de 1 à 4 % ; **bon marché** > 4 %. Au 20/11/2026 : 0,58, donc « chère ».
- Effet : si « chère », le rapport affiche en premier les stress tests de §9.3 (−15 % marché, −26 % pays AES). L'exposition ne change pas.
- Source : [R05] §1.2 et §14.1. Exclure les PER aberrants du BOC (17/02/2021 ; 17/07-26/08/2025) [R08] §4.4.
- **Taux de la BCEAO** : la seule décision connue (−25 pb, effet au 16/06/2025 ; 3,25 % / 5,25 %) est **[NON VÉRIFIÉ]** en source primaire, et les décisions de septembre 2025 à novembre 2026 sont **introuvables** (bceao.int inaccessible). Ces données sont stockées datées dans `config/macro_uemoa.yaml`, avec un poids nul tant qu'elles ne sont pas vérifiées. Variable future : le cumul des variations sur 12 mois, pour les banques seulement.

---

## 5. Module actualité et événements

### 5.1 Horodatage et collecte (point-in-time)

| Règle | Valeur | Source |
|---|---|---|
| Source principale | brvm.org : avis, communiqués, convocations, notations, dividendes, rapports des émetteurs ; `Crawl-delay: 10` ; arrêt sur HTTP 403/429 ; **aucun contournement anti-robot** (Sika Finance, richbourse désactivés) | [R07] §1, §6.7 ; [B10] |
| Fréquence | 08:00, 11:00, 14:00, 17:00, 20:00, 23:00 UTC ; rapports des émetteurs à 03:00 UTC | [R07] §6.7 |
| Négociabilité d'une nouvelle | `published_at` < 09h00 UTC un jour de séance ⇒ négociable au fixing de 09h45 du jour même ; sinon à la séance suivante | [R07] §2.3, §9 |
| Fondamentaux (PDF) | disponibles à la première séance dont la pré-ouverture suit `Last-Modified` ; à défaut, 2 séances après la date du nom de fichier ; préfixe faux si `Last-Modified` < préfixe − 30 jours | [R06a] §9.1 |
| Validation des dates | rejet des dates ex tombant un week-end ; plus de 30 séances entre l'avis et la date ex = date d'avis suspecte (LNBB 2026, SDCC 2025) ; paiement avant la date ex = rejet | [R07] §6.7 |
| OCR | obligatoire si moins de 200 caractères par page (`pdftoppm -r 200 -gray` + `tesseract -l fra`, testé) | [R07] §2.2 |

### 5.2 Dividendes

1. **Date ex** :
   - jusqu'au 03/12/2025 (règlement J+3) : 2 jours ouvrés avant la fermeture des registres ;
   - depuis le 04/12/2025 (J+2) : 1 jour ouvré avant, ou 2 si ce jour est férié (Instruction 03-2025, art. 2 [B5]) ;
   - en pratique : séance qui suit la ligne « (d) » du BOC ; à défaut, colonne « Ex-dividende » du calendrier officiel.
2. **Référence ex** : `ceil_au_pas(clôture_avec_droit − D_net_PP)` (44 cas sur 45 en 2025-2026) ; on préfère la référence publiée sur la ligne (d) [R01] §7.
3. **Montants** : toujours le **net publié** au BOC (IRVM du pays de l'émetteur pour une personne physique). Les taux ne servent qu'à passer du brut au net (§11). Le dividende est crédité en cash **à la date de paiement** (date ex + 2 séances en médiane, ou date de l'avis).
4. **Ordres** : la BRVM annule tous les ordres en attente à la date ex. Le moteur d'exécution **annule les ordres résiduels** le jour ex (et le jour d'un split) et les ressaisit le jour même [R07] §2.2.
5. **S2 — malus après détachement (actif dans toutes les variantes)** : pendant 20 séances après la date ex, −0,5 écart-type sur S_i pour les **nouveaux achats**. On ne force aucune vente. Base : CAR[+1,+20] = −2,54 % en moyenne, médiane −3,46 % [R07] §4.3.
6. **Calendrier d'exécution (actif)** : une vente programmée d'un titre détenu dont la date ex tombe dans les 15 prochaines séances, avec un rendement net ≥ 4 %, est **reportée au fixing de clôture du jour ex**, sauf si un filtre de risque R1-R10 ou une règle pays est actif. Base : AR du jour ex = +2,48 %. Ce report ne coûte aucune transaction supplémentaire.
7. **S1 — poche de capture du dividende (variante E ; activable en production seulement si le coût aller-retour réel tout compris, mesuré sur des avis d'opéré, est ≤ 2,0 %)** :
   - déclencheur : avis de paiement avec date ex connue ;
   - conditions : rendement net ≥ 4 % ; MDV60 ≥ 1 M FCFA et le plancher U5 ; au moins 3 séances entre la première séance négociable et la date ex ; aucun filtre R actif ;
   - entrée : première séance négociable après l'avis, à cours limité égal à la clôture de la veille × 1,02 ; ordre valable jusqu'à 3 séances avant la date ex ;
   - sortie : fixing de clôture du jour ex ; l'ordre est saisi **le jour même** (annulation des ordres en attente) ;
   - taille : ≤ 5 % par titre et ≤ 20 % au total, financés au prorata par le cœur ; ≤ 10 % de MDV × nombre de séances jusqu'à la date ex ;
   - hypothèse de planification : +0,5 à +1,0 % net par opération ;
   - coupe-circuit : sur les 30 dernières opérations, si le gain net moyen est ≤ 0 ou si moins de 50 % sont gagnantes, S1 est suspendu [R07] §6.5.

### 5.3 Publications de résultats

- **Types détectés** (expressions régulières de [R07] §6.4) : `RES_ANNUAL`, `RES_S1`, `ACT_Q1`, `ACT_Q3`, `PROFIT_WARNING`, etc.
- **Extraction** (OCR si nécessaire) : RN, RN part du groupe, PNB ou chiffre d'affaires, dividende proposé. Sentiment numérique `s_num = clip(ΔRN%/25, −2, 2)`.
- Les comptes trimestriels qui couvrent un **trimestre seul** (SITAB) sont convertis en cumul depuis le début de l'année. Le TTM vaut `RN_FY(N−1) + RN_YTD(N) − RN_YTD(N−1)`. Les données sont **périmées après 200 jours** [R06a] §9.1 ; [R06b] §6.
- **S4 (dérive après publication)** : **désactivé**. Il ne sera activé que si : (i) l'historique 2017-2021 des publications est reconstitué ; (ii) le groupe témoin est apparié **par mois civil** ; (iii) les critères de S1 sont remplis (gain net ≥ +0,5 % par opération, ≥ 55 % de gagnants, t par grappe ≥ 2) ; (iv) l'écart avec le témoin est ≥ +1 point en médiane [R07] §6.8.
- **Mise à jour des fondamentaux** : au fil de l'eau (publication + 1 séance, point-in-time) ; révision du score qualité les 15/05, 15/07 et 20/11 [R06b] §7.4.

### 5.4 Assemblées générales

- `AG_CONVOCATION` : alimente le calendrier (AGO = convocation + 18 jours en médiane ; date ex = AGO + 42 jours en médiane). Elle sert à **anticiper** S1 et la règle de report des ventes. S3 reste désactivé [R07] §4.5.
- `AG_CANCEL` (surtout sur instruction d'un régulateur, par exemple ETI le 23/10/2026) : R2.
- Une AGO qui ne vote aucun dividende met DY à 0 dès sa date (§3.2).

### 5.5 Opérations sur titres

| Événement | Règle | Source |
|---|---|---|
| Fractionnement ou regroupement | Facteur f = ratio (SNTS 10 le 26/10/2026 ; SLBC 10 le 30/09/2024 ; 50 splits détectés sur 2017-2026, nombre à **recalculer** et non à coder en dur) ; DPS historiques ajustés ; R8 : vérification du facteur avant tout signal pendant 5 séances. Seuil de détection : \|prev/clôture veille − 1\| > 30 % | [R01] §8 ; [R03] §9 ; [R08] §6.1 |
| Attribution gratuite | f = réf_ex / (réf_ex + valeur du droit), arrondi au pas **inférieur** (BOA et SIB 2024) | [R01] §8.2 ; [R06a] §9.5 |
| Augmentation de capital avec DPS | f = réf_ex / clôture avec droit (SAFC 0,7066) ; R5 : aucun nouvel achat avant le détachement du droit ; nombre de titres recalculé à l'admission des actions nouvelles | [R01] §8.3 |
| OPA, OPR, OPV | R6 : signaux automatiques gelés ; analyse manuelle | [R07] §6.6 |
| Radiation | Le titre sort de l'univers à sa dernière ligne au BOC (MOVIS : 26/06/2025) ; univers **point-in-time** (pas de biais du survivant) | [R01] §8.3 |
| Changement de composition d'indice | Information seulement (révisions du BRVM 30 le 1er jour ouvré de janvier, avril, juillet et octobre) ; aucun signal d'inclusion n'est testé | [R01] §10.4 |

### 5.6 Filtres de risque R1-R10 (ils priment sur les signaux)

| Code | Déclencheur | Action | Durée |
|---|---|---|---|
| R1 | Suspension (avis ou `SP`) | Aucun achat ; position valorisée au dernier cours avec une décote de liquidité de 10 % pour le risque ; alerte | jusqu'à la reprise + 5 séances |
| R2 | AG annulée ou reportée, surtout sur instruction d'un régulateur | Qualité −1 ; aucun nouvel achat | 60 séances |
| R3 | Réserves ou refus de certification ; doute sur la continuité d'exploitation ; capitaux propres < ½ du capital | Exclusion des achats ; revue manuelle | jusqu'aux comptes suivants |
| R4 | Dégradation de notation ou perspective négative | Poids max × 0,5 | 120 séances |
| R5 | Augmentation de capital en numéraire | Aucun achat avant le détachement des droits | jusqu'au détachement |
| R6 | OPA, OPR, OPV sur le titre | Gel des signaux automatiques | jusqu'au résultat |
| R7 | Rapport non publié à la date limite BRVM (comptes annuels et T1 : 30/04 ; S1 et T3 : 31/10) | Alerte orange le lendemain de la date limite ; au niveau rouge (+61 jours), qualité −0,5 | jusqu'à la publication |
| R8 | Split ou regroupement | Contrôle du facteur avant tout signal | 5 séances |
| R9 | « Alerte sur résultats » (instruction 01-2025, baisse du RN ≥ 25 %) | Aucun achat ; S1 désactivé sur le titre ; qualité −1 | 60 séances ou jusqu'aux comptes suivants |
| R10 | Comptes avec ΔRN ≤ −25 % (consolidé, sinon social) **sans** alerte dans les 120 jours précédents, pour des comptes publiés à partir du 01/10/2025 | Qualité −0,5 ; alerte gouvernance | 120 séances |
| R11 (financières) | Drapeaux de [R06a] §9.3 : payout brut > 1 ; RN cumulé de l'année < −15 % ; coût du risque > 3 fois celui de N−1 ; NPL ≥ 8 % ; NPL en hausse de plus de 25 % sur un an ; marge de solvabilité < 2 points ; crédits < −15 % sur un an ; aucun dividende depuis 3 ans ou plus ; dilution en attente | 1 drapeau : poids max × 0,5 ; 2 drapeaux ou plus : exclusion | tant que le drapeau dure |
| R12 (non financières) | Payout > 100 % deux ans de suite ; bénéfice non récurrent ; DY > 15 % | Poids max × 0,5 | idem |

Sources : [R07] §6.6, §9 ; instruction 01-2025 [B11] ; [R06a] §9.3 ; [R06b] §7.1. Les seuils R11 et R12 sont des **choix de conception non validés** : ils restent des hyperparamètres, comptés dans le registre s'ils sont modifiés.

### 5.7 Sentiment (niveau 0)

- Méthode : lexique BRVM-FR v0 de [R07] §3.3 et règles de §3.4 (négation sur 3 mots, concession × 0,5, intensité × 1,5 ou × 0,5).
- Score d'un événement : `s = 0,7·s_num + 0,3·tone`. Score par titre : `S_i(t) = Σ s_k·exp(−(t − t_k)/10)`.
- **Poids nul dans le score** (S5) tant que l'IC walk-forward ≤ 0,05 sur au moins 3 années. Usage immédiat : explication (`explain()`) et détection d'événements.
- Un modèle de langage peut **résumer et étiqueter** les PDF, à condition que chaque appel soit journalisé et daté (point-in-time) ; il ne produit **jamais** un signal de trading direct.

### 5.8 Introductions en bourse (module d'aide à la décision, non automatisé)

- Souscrire si l'émetteur passe le score de qualité de son secteur ([R06a] §9.2 ou [R06b] §7.2) et si son PER d'offre est ≤ au PER médian de son secteur.
- Après la cotation : conserver tant que le titre clôture à la borne haute ; vendre 50 % à la première séance qui clôture sous la borne haute ; le reste n'entre dans le moteur factoriel qu'après 126 séances.
- Base : 4 introductions sur 2022-2026, dont BBGC avec 4 séances à la borne haute. Niveau P3 : ce n'est pas une règle de backtest.

---

## 6. Construction de portefeuille

| Élément | Règle exacte | Source |
|---|---|---|
| Contraintes de marché | Acheteur seul, sans levier, sans vente à découvert (art. 1123) ; quotité de 1 titre ; pas de cotation de 5 FCFA (1 FCFA si cours < 100 FCFA) | [R01] §2 ; [B3] |
| Exposition actions | 98 % (réserve de liquidités de 2 %). Kelly **ne décide pas** de la part actions : le μ du marché n'est pas estimable (James-Stein c = 0) et la prime du BOC n'est pas un signal | [R04] §11, §15.3 |
| Nombre de lignes | `n_cible = clip(round(N_elig/3), 12, 20)` ; mode repli si N_elig < 15 | [R03] §8.3 ; §2 U10 |
| Sélection avec bande | Rang par S_i décroissant. **On garde** un titre détenu tant que son rang est dans les 50 % supérieurs et qu'il reste éligible ; **on ajoute** des titres classés dans les 30 % supérieurs, par ordre de score, jusqu'à n_cible ; si l'on a moins de 12 lignes, on complète avec les meilleurs rangs des 50 % supérieurs ; au-delà de 20 lignes, on retire les moins bien classés | [R03] §8.3 ; Novy-Marx & Velikov 2016 [A8] |
| Pondération (A) | Équipondérée sur la sélection (méthode `equal`), puis projection sur les plafonds. Les variantes G (`hrp_tilt`) et H (`mv_alpha`) sont des challengers | [R03] §8.3 ; DeMiguel et al. 2009 [A9] |
| Plafond par ligne | 10 % × multiplicateur pays (§4.2) × 0,5 si U6 × 0,5 si U7 × 0,5 si R4 ou R11 (un drapeau) ; plancher 2 % (en dessous, la ligne est supprimée) | [R03] ; [R06a] |
| Plafond sectoriel | `w_s ≤ max(15 % ; min(45 % ; 1,5 × u_s))`, avec u_s la part du secteur dans l'univers éligible (FIN ≤ 45 %) | [R03] §8.3 ; [R06a] §9.4 |
| Plafonds pays | §4.2 | [R05] |
| Liquidité | `w_i × K ≤ 0,10 × MDV63_i × 20` (sortie en 20 séances à 10 % de participation) — `liquidity_caps` | [R01] §12.3 |
| Fréquence | Signal et transactions **mensuels** (dernière séance du mois). Entre deux dates : seules les règles R, les règles pays, S1 et le calendrier des dividendes déclenchent des ordres | [R03] §7.3 |
| Bande de non-transaction | Pas d'ordre si \|w_cible − w_actuel\| < 2 points, sauf pour une entrée ou une sortie complète | `Constraints.no_trade_band` |
| Rotation | ≤ 50 % aller par rebalancement (`cap_turnover`) ; objectif ≤ 15 %/mois aller en moyenne | [R03] §7.3 |
| Kelly fractionnel | Seulement dans la variante H : échelle des poids **actifs** `s = min(1 ; fractional_kelly_scale(α, Σ, fraction=0.25, weights=w − w_EW))`, avec α = alpha de Grinold rétréci et Σ hebdomadaire de Ledoit-Wolf ; plafond de la fraction à 0,5 ; `max_gross` = 1 | [R04] §11.4 ; MacLean, Thorp & Ziemba 2010 [A16] |
| Covariance (G, H, CVaR, risque) | Ledoit-Wolf vers la corrélation constante, rendements **hebdomadaires** (W-FRI), 104 semaines (minimum 52), plancher d'intensité 0,5 (attendu 0,7-0,9) ; jamais une volatilité journalière × √252 pour un portefeuille | [R04] §8.4 ; Ledoit & Wolf 2004 [A5] |
| HRP (G) | d = √(½(1 − ρ)) ; lien `single` ; `distance_of_distances=True` à passer explicitement ; inclinaison `exp(0,5·z_α)` | [R04] §9.3 ; López de Prado 2016 [A4] |
| Lots | `to_lots(weights, prices, capital)` : nombre entier de titres, arrondi vers le bas ; le reste reste en liquidités | ARCHITECTURE.md |

**Coûts fixes et petits portefeuilles** : la tenue de compte BICI Bourse coûte 5 000 FCFA par ligne et par an. Avec 15 lignes, cela fait **0,75 %/an** sur un portefeuille de 10 M FCFA, soit l'ordre de grandeur de l'alpha espéré. La plate-forme affiche ce coût. Elle recommande une SGI sans frais par ligne (FGI : tenue de compte gratuite, garde ≤ 0,25 %), mais ne réduit **pas** la diversification sous 12 lignes ([R01] §5 ; [B6][B7]).

---

## 7. Modèle d'exécution et de coûts (backtest)

### 7.1 Exécution

1. **Décision** à la clôture de t (après la publication du BOC). **Exécution** à partir de t+1 au **VWAP du jour** (valeur/volume) si le titre est échangé. Sinon, l'ordre est reporté, pendant **au plus 10 séances**, puis annulé et réévalué au rebalancement suivant.
2. **Participation** ≤ 10 % du volume du jour (`ExecutionModel.max_volume_participation = 0.10`).
3. **Bandes** : bornes `basse = ceil(réf × 0,925 / pas) × pas`, `haute = max(floor(réf × 1,075 / pas) × pas ; réf + pas)` autour de la référence **ajustée**. **Aucun achat** si la clôture de la séance est à la borne haute (|clôture/réf − 1| ≥ 7,5 % − 0,2 %) ; **aucune vente** à la borne basse. Les ordres sont reportés.
4. **Jour ex et jour de split** : les ordres en attente sont annulés et ressaisis le jour même.
5. **Règlement** : J+3 jusqu'au 03/12/2025, J+2 ensuite. Le produit d'une vente ne finance un achat qu'après le délai de règlement.
6. **Dividendes** : crédités nets à la date de paiement ; ils restent en liquidités jusqu'au rebalancement suivant (aucun réinvestissement immédiat, par prudence).
7. **Suspension** : position bloquée. Pour le risque, elle est valorisée au dernier cours moins 10 %.
8. **Choc pays sévère** (§4.3) : en backtest, la première séance qui suit l'annonce est supposée au plancher, sans vendeur servi.

### 7.2 Coûts par côté (achat **et** vente)

`coût_aller = courtage × (1 + taxe) + 0,0020 (BRVM) + 0,0010 (DC/BR) + demi_spread_i + κ·√π`

| Composante | Optimiste | **Central** | Stress | Sévère | Source et confiance |
|---|---:|---:|---:|---:|---|
| Courtage SGI | 0,50 % | **0,80 %** | 1,00 % | 1,50 % | Grilles homologuées : 0,4-1 % (BICI), ≤ 1 % (FGI) [B6][B7], high ; 0,80 % = hypothèse centrale de [R02] ; 1,5 % = haut de la fourchette secondaire, low |
| Taxe sur le courtage | 10 % | **18 %** | 18 % | 18 % | **[NON VÉRIFIÉ]** : aucun taux sur brvm.org ni dans les grilles ; 10 % (TAF) pour [R01], 18 % (TVA) pour [R02]. Le central prend la valeur prudente |
| Commission BRVM | 0,20 % | 0,20 % | 0,20 % | 0,20 % | [B1] ; tarification 2014 [B2], high |
| Commission DC/BR | 0,10 % | 0,10 % | 0,10 % | 0,10 % | idem, high |
| Redevance AMF-UMOA | 0 | 0 | 0 | 0 | introuvable [R01], low |
| **Frais proportionnels aller (sous-total)** | **0,85 %** | **1,244 %** | **1,48 %** | **2,07 %** | calcul |
| Demi-spread | demi-spread_i | demi-spread_i | 1,5 × | 2 × | demi-spread_i = ½ × spread médian de clôture sur 120 séances (deux côtés présents), plancher pas/(2 × cours) ; défaut 0,35 % (spread médian de 0,69 % en 2026 ; 0,21 % pour BOAM, 4,3 % pour UNLC) [R01] §5.2, high (mesure) |
| Impact κ·√π (π = participation au volume du jour) | κ = 0,010 | **κ = 0,016** | κ = 0,032 | κ = 0,050 | **Hypothèse** : 0,5 % d'impact à 10 % de participation (« 50 pb par 10 % du volume » de [R02]) ; aucune étude d'impact publiée sur la BRVM ; low |
| Droits de garde (annuels, sur l'encours) | 0 | **0,25 %** | 0,50 % | 0,50 % | BICI 0,1-0,5 % ; FGI ≤ 0,25 % [B6][B7], high |
| Tenue de compte (par ligne et par an) | 0 | **5 000 FCFA** | 5 000 | 10 000 | BICI : 5 000 (personne physique), 10 000 (personne morale) ; FGI : 0 [B6][B7], high |
| Impôt sur les plus-values | 0 | 0 | 0 | 0 | **[NON VÉRIFIÉ]** (personne physique résidente) [R01] §6.2 |

**Ordre de grandeur** : pour un titre médian (demi-spread 0,35 %, participation 1 %), le coût aller central vaut 1,244 + 0,35 + 0,16 ≈ **1,75 %**, soit **3,5 % aller-retour**. Pour SNTS ou SGBC (demi-spread ≈ 0,13 %) : environ 1,4 % aller. **Toutes** les statistiques de performance sont rapportées aux coûts **central** et **stress**.

Correspondance dans `config.py` (`CostModel`) : `sgi_commission=0.008`, `brvm_fee=0.002`, `dcbr_fee=0.001`, `regulator_fee=0.0`, `vat_on_commission=0.18`, `impact_coef=0.016`, `annual_custody=0.0025`, plus deux nouveaux champs : `half_spread_default=0.0035` et `account_fee_per_line_fcfa=5000`. Le moteur doit ajouter le demi-spread propre à chaque titre (aujourd'hui absent de `engine.py`).

### 7.3 Fiscalité des dividendes (IRVM du pays de l'émetteur, personne physique)

**Règle prioritaire** : utiliser le **net publié au BOC**. Les taux ci-dessous ne servent qu'à passer du brut au net (payout brut, calendrier ivoirien publié en brut).

| Pays | Taux | Période | Conf. | Source |
|---|---|---|---|---|
| CI | 12 % (personne physique) / 10 % (personne morale) ; 10 % jusqu'en 2024 (inférence) ; part exceptionnelle 17 % | 2025-2026 | high | calendrier 06/10/2026 [B12] ; [R01] §6.1 |
| SN | 10 % (2026) ; avant 2026, nets compatibles avec 12,5 % **[NON VÉRIFIÉ]** | 2026 | high (2026) | avis 111-2026 ; [R01] |
| BF | 12,5 % **[NON VÉRIFIÉ]** (CBIBF 2026 compatible avec 10 %) | 2025-2026 | low | [R01] ; [R06b] |
| ML | 7 % (2025-2026) ; 10 % en 2024 **[NON VÉRIFIÉ]** | 2025-2026 | medium | [R01] |
| NE | 7 % | 2021-2025 | high | [R01] |
| BJ | selon l'émetteur : LNBB et BICB ≈ 5 %, BOAB ≈ 10 % (inférences) | 2025-2026 | low | [R01] |
| TG | inconnu : utiliser le net du BOC | — | low | [R01] |

---

## 8. Protocole de validation (fixé AVANT de regarder les résultats)

### 8.1 Échantillons

| Échantillon | Période | Statut | Usage |
|---|---|---|---|
| **S0 — sélection** (contaminé) | 2022-11-17 → 2026-11-20 | Déjà exploré par [R03] et [R04] (au moins 55 essais : 13 composites, 6 fenêtres de momentum, une grille de 36 stratégies) | Diagnostic seulement ; **aucune** conclusion de validation |
| **S1 — validation pré-enregistrée** | **2017-01-02 → 2022-11-16** | **Vierge** : aucun essai n'y a été fait (le vérificateur de [R03] s'en est abstenu ; cette spécification aussi) | Test unique des 8 variantes du §3.4, paramètres figés |
| Sous-périodes de S1 | 2017-01-02 → 2019-12-31 (baissier) ; 2020-01-01 → 2022-11-16 (Covid puis rebond). Du 06/05 au 25/06/2021 : rendements exclus des statistiques | — | Stabilité du signe |
| **S2 — suivi réel (paper trading)** | à partir du 01/12/2026 | Futur, intact | Seul test réellement hors échantillon : au moins 6 mois avant toute recommandation d'argent réel, et 36 mois avant toute affirmation de performance |
| Historique avant 2017 | non téléchargeable au format du projet (HTTP 404) | — | À acheter auprès de la BRVM (CD historique) ; tests qualitatifs seulement |

### 8.2 Métriques et méthodes (toutes nettes de coûts, contre le TR reconstruit)

| Élément | Paramètre | Source |
|---|---|---|
| Fréquence d'évaluation | **Hebdomadaire (W-FRI)** pour toutes les métriques de portefeuille ; annualisation par convention à 252 séances ou 52 semaines (réel : environ 248 séances, soit une surestimation d'environ 0,8 %, documentée) | [R04] §2, §17.2 |
| Sharpe | toujours trois versions : naïf, Lo (troncature des ρ_k à q = 10 en journalier, 4 en hebdomadaire, 2 en mensuel) et GLM ; signaler si \|SR_Lo − SR_GLM\|/SR_Lo > 25 % | [R04] §13.6 ; Lo 2002 |
| PSR / DSR | PSR(SR* = 0) et DSR avec N = nombre d'essais du registre ; seuils de 0,95 | Bailey & López de Prado 2012, 2014 [A1] |
| PBO | CSCV, S = 10 blocs (hebdomadaire) ou 16 (journalier, T ≥ 640), critère = Sharpe de Lo des rendements actifs nets | Bailey et al. 2017 [A2] ; [R04] §3 |
| Tests multiples | haircut BHY (M = registre) ; t de Newey-West ≥ 3 pour un nouveau signal, ≥ 2 pour un facteur documenté et prédéclaré ; Reality Check de White et SPA de Hansen en v2 | Harvey, Liu & Zhu 2016 [A3] ; Harvey & Liu 2015 [A17] |
| Bootstrap | stationnaire, bloc moyen de 8 semaines (20 séances en journalier ; plancher de 10), **n_boot = 5 000** (à passer explicitement : le défaut du code est 2 000) ; différence de Sharpe par le test studentisé de Ledoit-Wolf (2008) | [R04] §7.4 ; Patton, Politis & White 2009 [A18] |
| Walk-forward | expansif ; `train_years=2`, `test_months=3`, `embargo_days = h + 21` (42 pour un label mensuel), `min_train_days=480` | [R04] §6.3 |
| CPCV | 10 groupes, k = 2 (45 découpages, 9 chemins), purge = 21 séances, embargo = 21 séances | [R04] §6 ; López de Prado 2018 |
| Étalons | (1) **Composite TR** (officiel depuis le 02/01/2025, reconstruit avant, §1.1) ; (2) **panier équipondéré TR des titres éligibles** (il isole la compétence de sélection) ; (3) Composite prix (information seulement) ; (4) BRVM 10 jusqu'au 30/12/2022, BRVM 30 et Prestige à partir du 02/01/2023 ; (5) **médiane des fonds actions** (catégorie A du BOC, même fenêtre que les VL) | [R01] §10 ; [R08] §6 |
| Registre | `TrialRegistry` (`reports/trials.parquet`) : chaque variante est journalisée avec ses paramètres, ses rendements hebdomadaires nets et sa date d'exécution. N de départ = 55 (S0) + 8 (S1), porté par l'additif v1.1 (§8.4) à 55 + 9 + 1 (référence « indice discipliné ») + les essais de diagnostic S0 réellement exécutés | [R04] §17.3 |

### 8.3 Critères de décision (écrits avant toute exécution sur S1)

**Statut « REJETÉ »** pour A si **l'une** des conditions suivantes est vraie sur S1 :
1. rendement actif net annualisé contre le TR ≤ 0 aux coûts centraux ;
2. rendement actif net < −1 %/an aux coûts de stress ;
3. IR < −0,5 sur l'une des deux sous-périodes ;
4. drawdown relatif contre le TR pire que −20 % ;
5. drawdown absolu pire que celui du TR de plus de 10 points (TR : −46,7 %).

Si A est rejeté, la plate-forme passe en **mode « indice discipliné »** : réplication du TR par les 15 à 20 plus grosses capitalisations éligibles, rebalancement annuel, calendrier des dividendes et règles de risque. Aucune promesse d'alpha n'est alors faite, et la recherche continue.

**Statut « CANDIDAT » (paper trading autorisé)** si **toutes** les conditions suivantes sont vraies sur S1 :
1. rendement actif net > 0 aux coûts centraux et ≥ −0,5 %/an aux coûts de stress ;
2. IR net ≥ 0,20 ;
3. rendement actif positif dans **les deux** sous-périodes ;
4. drawdown relatif ≥ −20 % ;
5. rotation moyenne ≤ 20 %/mois aller ;
6. PBO de la famille des 8 variantes ≤ 0,5 ;
7. CVaR 95 % à 5 séances ≤ 1,25 × celle du TR.

**Statut « PROMU » (argent réel recommandé)** si, en plus, sur S1 **et** sur le suivi réel S2 d'au moins 12 mois, les filtres G1-G9 de [R04] §17.1 sont tous verts :
- G1 : registre complet ;
- G2 : PSR ≥ 0,95 ;
- G3 : DSR ≥ 0,95 ;
- G4 : PBO ≤ 0,25 et pente de dégradation > −0,5 ;
- G5 : HSR (BHY) > 0,3 ;
- G6 : borne basse de l'IC bootstrap de l'IR > 0 ;
- G7 : t_NW de l'IC ≥ 2 sur au moins 36 mois ;
- G8 : stabilité du signe ;
- G9 : Sharpe de Lo ≥ 0,6 × Sharpe naïf.

**Prédiction écrite d'avance** : avec un IR réel de 0,3, le z attendu sur S1 (5,9 ans) vaut 0,3 × √5,9 ≈ 0,73, soit un PSR ≈ 0,77 : **G2 échouera probablement**. Le statut le plus probable, même si la stratégie est bonne, est « candidat ». Une stratégie qui afficherait un IR > 1 sur S1 serait d'abord traitée comme une **erreur** à rechercher (biais d'anticipation, prix périmés, coûts oubliés) [R04] §16.3.

**Critères d'arrêt en production** :
- rendement actif net sur 36 mois glissants < 0 avec t < −1 : retour au mode « indice discipliné » ;
- coupe-circuit de S1 (§5.2) ;
- tout écart de données avec le BOC de plus de 1 pb : gel des ordres.


### 8.4 Additif v1.1 — décisions figées le 22/11/2026, **avant toute exécution sur S1**

**Pourquoi cet additif.** La mise en œuvre du moteur v1 et sa revue adversariale ont relevé des points que la spécification laissait ouverts, ou qui créent un biais mécanique. Ils sont tranchés ici, une fois pour toutes. **Aucune performance, aucun IC et aucun signal n'a été calculé sur S1** (2017-01-02 → 2022-11-16) avant cette décision. Seuls des comptages d'univers (titres éligibles en 2017, 2020 et 2021) et des contrôles de données y ont été faits.

**Ce qui a été vu, et qui est déclaré.** Deux informations contaminées ont motivé une partie de ces décisions : l'essai de fumée de A sur S0 et la décision du 20/11/2026.
- **Essai de fumée de A sur S0** (variante A, 10 M FCFA, coûts centraux) : environ 28 %/an contre 34,6 %/an pour le TR ; drawdown relatif de −15 % au 30/09/2024, puis −20 % au 29/11/2024, donc arrêt et passage en « indice discipliné ».
- **Décision du 20/11/2026** : remplissage de capacité, poids de CIEC (rang 19) à 8,58 % contre 5,98 % pour BOAC (rang 1).

Ces essais S0 sont inscrits au registre et comptent dans N. Aucun paramètre libre n'a été réglé sur S0 : chaque décision ci-dessous est structurelle ou fixée a priori.

| N° | Point | Décision figée | Raison |
|---|---|---|---|
| **D1** | Fenêtres et BOC manquants (§3.1.3, §3.2, §2) | **Longueur** des fenêtres comptée en **séances** (numéros de BOC, `window_basis = "sessions"`). **Bornes** d'une fenêtre de rendement (MOM) : dernier cours disponible à la date de borne ou avant, à 5 séances au plus ; sinon NaN. **Seuils minimaux d'observations** (MOM6_1 100/126, LOWVOL 200/250 et 100/126, U2, U3, et tout seuil « au moins m observations sur L séances ») : `m_eff = ⌈m × n_BOC_disponibles / L⌉`, avec un plancher absolu de **40** observations pour les signaux et de **20** pour les filtres d'univers. Sous le plancher : bloc manquant (z = 0) pour un signal, exclusion pour un filtre | En base « lignes du panel », MOM6_1 couvre jusqu'à 221 séances au 30/11/2021 : c'est un autre signal. En base « séances » sans prorata, l'univers est vide du 30/06 au 30/11/2021 (0 titre contre 26 à 33) : un BOC manquant est une perte de **nos** données, pas une absence de cotation |
| **D2** | Fenêtre d'évaluation de S1 | **t0** = première séance où la variante A détient des titres (premier rebalancement exécuté, `start = "first_investment"`). Tous les critères du §8.3 et toutes les métriques se calculent sur **[t0 ; 2022-11-16]**, pour **toutes** les variantes et **tous** les étalons, rebasés à t0. Sous-période 1 = [t0 ; 2019-12-31]. Une variante qui ne peut pas encore calculer sa propre pondération (G, H : historique de covariance insuffisant) utilise celle de A jusqu'à ce qu'elle le puisse ; c'est journalisé. Les chiffres sur la fenêtre complète [02/01/2017 ; 16/11/2022] sont publiés **pour information seulement** | Sans historique de 126 séances, aucun titre n'est éligible avant juillet 2017. Comparer 6 à 9 mois de liquidités à un TR qui baisse en 2017 crée un rendement actif mécanique (+1,88 %/an mesuré sur données synthétiques sans alpha) |
| **D3** | Garde de capitalisation (§9.1) | Un écart > 3 % entre capitalisation reconstruite et publiée déclenche une **alerte journalisée, non bloquante**. La garde « rendement journalier > \|50 %\| » reste **bloquante** | Le nombre de titres reconstruit ne sert qu'à l'étalon et aux références b_c, pas aux signaux. Bloquer gèlerait juillet-août 2017 pour une raison étrangère aux cours (opérations BOA de juin 2017) |
| **D4** | Remplissage de capacité (§6, exposition de 98 %) | Si les plafonds empêchent d'investir 98 % sur la sélection de la bande, on ajoute des titres éligibles **par ordre de score** (au-delà des 50 % supérieurs si nécessaire), jusqu'à 20 lignes. Un titre ajouté pèse **au plus 98 % / n_cible** (le poids d'une ligne de la bande). Le reliquat reste en liquidités et est publié | Des liquidités non voulues sont un pari de marché non enregistré. Mais un titre ajouté pour capacité ne doit pas peser plus qu'un titre choisi par le score |
| **D5** | Drawdown relatif (§9.1) | Mesuré sur le ratio VL / TR **rebasé à t0**, contre son plus haut depuis t0 (en production : depuis le début du suivi réel). Le panier w_EW de la règle −15 % est l'équipondération des **20 éligibles les mieux classés** (et non de tous les éligibles). Ses entrées et sorties sont exemptées de la bande de non-transaction | La lettre du §9.1 créait jusqu'à 35 lignes sous le plancher de 2 % et la limite de 20 lignes, avec 5 000 FCFA de frais par ligne |
| **D6** | Montants de dividende | **Flux de trésorerie** du backtest : montant corrigé (meilleure estimation du versement réel). **Signaux** (DY, S1, S2) : montant connu en t, ligne « (d) » du BOC. L'écart total est publié | La comptabilité doit refléter l'argent reçu. Les signaux ne doivent utiliser que l'information disponible |
| **D7** | Statut « PROMU » | G7 (t de Newey-West de l'IC ≥ 2 sur au moins 36 mois) s'évalue sur la série d'IC **S1 puis S2 mise bout à bout**. Les autres filtres de S2 s'évaluent sur S2 seul, avec au moins 12 mois. Statut « INDÉTERMINÉ » (données insuffisantes) : aucun suivi réel autorisé | Sans cette règle, PROMU est impossible avant 36 mois de S2, ce qui contredit le seuil de 12 mois du §8.3 |
| **D8** | Mode « indice discipliné » : repli du §8.3 **et** étalon investissable | **20 plus grosses capitalisations éligibles** (toutes s'il y en a moins), poids **proportionnels à la capitalisation** point-in-time, 98 % investis. **Plafond de ligne** = max(10 % × multiplicateur pays ; min(30 % ; 1,25 × b_i)), avec b_i le poids du titre dans l'étalon. **Plancher** de 0,5 %. **Plafond sectoriel** = max(15 % ; 1,25 × b_s). Plafonds pays, AES et liquidité de A. Filtres R et règles pays actifs. **Rebalancement annuel** (première décision de janvier), plus les sorties forcées (filtres R, inéligibilité). Évalué sur S1 comme **référence** (essai REF-ID du registre, hors famille de la PBO) | Avec les plafonds de A, ce mode n'était pas une réplication : l'étalon place environ 21 à 35 % sur SNTS selon les années (20,9 % au 20/11/2026) et 36 % dans TEL au 20/11/2026 (SNTS + ORAC) |
| **D9** | Nouvelle variante **I « cœur-satellite »** | w_I = 0,5 × w_D8 + 0,5 × w_A, chevauchements additionnés, puis projection sur les plafonds de groupe de D8 ; le côté A se rebalance chaque mois, le cœur chaque année. **Aucun paramètre libre** : 50/50 fixé a priori. Famille de la PBO et du DSR : **N = 9**. Promotion du §3.4 inchangée (I ne remplace A que si elle bat A en actif net **et** franchit DSR ≥ 0,95 **et** PBO ≤ 0,25) | Les plafonds de A (TEL ≤ 15 %, SNTS ≤ 8,5 %) imposent contre l'étalon un pari structurel d'environ −20 points sur TEL, que la thèse du §1 ne justifie pas. Motivé par S0 (déclaré ci-dessus), testé une seule fois sur S1 |
| **D10** | Événements pays utilisés sur S1 (§4.3) | Les règles pays s'appliquent sur S1 avec la chronologie ci-dessous, **à la date de l'annonce publique** (action à la première séance qui suit). Aucune autre information future | Ce sont des règles de risque actives dans toutes les variantes (§4.3) |
| **D11** | Notes de l'analyste sur S1 | Aucun rôle : S5 a un poids nul ; les notes reconstituées sont exclues des vues strictes ; ni veto ni inclinaison manuelle sur S1 | Aucune note n'existait en temps réel sur 2017-2022 |
| **D12** | Exécution unique et verrou | S1 est exécuté **une seule fois** par `python -m brvm_alpha validate --sample S1`, qui exige un arbre git propre et enregistre le commit, l'empreinte de configuration et l'horodatage. La commande écrit `reports/validation_S1/` et marque les essais « exécuté » dans le registre, avec leurs rendements hebdomadaires. Elle **refuse** de se relancer. Une relance n'est permise que pour un **bogue démontré** (anticipation, comptabilité, données) avec `--rerun-reason` : elle crée de nouveaux essais (N augmente) et **les deux résultats sont publiés** | Sans verrou, le DSR et la PBO perdent leur sens (§8, [R03][R04]) |

**Analyses de sensibilité (ce ne sont pas des essais supplémentaires)** : coûts centraux et de stress pour les 9 variantes et la référence ; coûts optimistes et sévères pour A et I ; capacité à 100 M et 1 Md FCFA pour A, I et la référence. Ces runs mesurent le **même** essai sous d'autres hypothèses ; seuls les runs centraux à 10 M FCFA entrent dans la PBO et le DSR.

**Chronologie des événements pays pour S1 (D10).** Dates d'annonce, actions à la première séance BOC suivante. Les dates de confiance « M » sont **[NON VÉRIFIÉ]** en source primaire ([R05] §8-9). Les présidentielles sont tirées de la connaissance générale, également **[NON VÉRIFIÉ]**.

| Date d'annonce | Pays | Règle du §4.3 | Remarque |
|---|---|---|---|
| 29/07/2018 | ML | élection | présidentielle (2ᵉ tour le 12/08/2018) |
| 24/02/2019 | SN | élection | présidentielle |
| 22/02/2020 | TG | élection | présidentielle |
| 18/08/2020 | ML | coup (sans sanctions UEMOA) | [R05] §9 : BOAM −1,5 % |
| 31/10/2020 | CI | élection | présidentielle |
| 22/11/2020 | BF | élection | présidentielle |
| 27/12/2020 | NE | élection | présidentielle (2ᵉ tour le 21/02/2021) |
| 11/04/2021 | BJ | élection | présidentielle |
| 24/05/2021 | ML | coup (sans sanctions UEMOA) | second coup d'État au Mali |
| 09/01/2022 | ML | **sévère** (sanctions CEDEAO/UEMOA, gel BCEAO) | dimanche ; action le 10/01/2022 ; [R05] §9 : BOAM −7,47 % à t+1 |
| 24/01/2022 | BF | coup (sans sanctions UEMOA) | [R05] §9 |
| 03/07/2022 | ML | levée de sanctions | sommet CEDEAO du 03/07/2022 ; [R05] §9 : +35,7 % en 5 séances |
| 30/09/2022 | BF | coup (sans sanctions UEMOA) | [R05] §9 |

Événements postérieurs (pour S0 et le suivi réel) : NE coup 26/07/2023, NE sévère 30/07/2023, NE levée 24/02/2024, SN élection 24/03/2024, CI élection 25/10/2025, BJ élection 12/04/2026 ([R05] §8 ; dates M ou connaissance générale, [NON VÉRIFIÉ]).

**Prédiction maintenue.** Ces décisions ne changent pas la prédiction du §8.3. Le statut le plus probable, même pour une bonne stratégie, est « candidat ». Le rejet de A est un résultat plausible : l'essai de fumée de S0 est défavorable.

### 8.5 Précisions de mise en œuvre et errata, écrits **après** le premier test S1 (22/11/2026)

**Statut de cette section.** Elle est écrite après le premier test S1 (commit `a2bfeb4`, résultats `35e25f7`), à la suite de l'audit de ce test. Elle **ne change aucune décision D1 à D12, aucun paramètre et aucun seuil du §8.3**. Elle documente des règles que seul le code fixait, et corrige des écarts entre le code et le texte (§3.1.3, §8.1). Les corrections de bogues ont motivé **une** relance de S1 (D12, `--rerun-reason`) : nouveaux essais, N augmente, les deux résultats sont publiés. Les points marqués **(S2)** sont des propositions à pré-enregistrer par une décision humaine avant le suivi réel ; ils ne s'appliquent pas à S1.

| N° | Point | Règle (fait foi pour la relance de S1) | Origine |
|---|---|---|---|
| **E1** | Semaines « multi-séances » (§3.1.3) | Une semaine dont l'observation couvre plus de 6 séances (trou de BOC) est **gardée** pour tous les critères chaînés : rendement annualisé, rendement actif (R1, R2, C1, C3), drawdowns (R4, R5, C4), étalons. Elle est **retirée** des seules statistiques de dispersion : volatilité, IR (R3, C2), TE, Sharpe, PSR, DSR, PBO, CVaR, bootstrap, filtres G2 à G9. Seule la fenêtre du §8.1 (06/05 → 25/06/2021) est retirée de tout | Bogue : le code retirait ces semaines de tout. Sur S1, 7 semaines hors fenêtre du §8.1 étaient perdues pour le chaînage |
| **E2** | Couverture de l'échantillon (§8.3, D7) | Semaines attendues = calendrier **W-FRI** de [t0 ; fin], moins la fenêtre du §8.1. Couverture = part de ces semaines présentes dans la série chaînée (E1). **Seuil : 95 %** (valeur du code depuis `a2bfeb4`, absente du texte jusqu'ici) : en dessous, statut INDÉTERMINÉ (données insuffisantes). La couverture de l'échantillon de dispersion est publiée à côté. Les semaines attendues ne sont jamais tirées d'une série calculée avec les mêmes retraits (autoréférence) | Bogue : les semaines attendues étaient celles du TR, d'où 100 % par construction |
| **E3** | Coûts annuels publiés | Coûts payés ÷ VL moyenne ÷ **années calendaires** de la fenêtre (et non × 252 ÷ séances observées : environ 228 séances par an sur S1). Décomposition **pondérée** du coût par aller (frais, demi-spread, impact) dont la somme vaut le coût moyen pondéré | Publication seulement ; aucun critère |
| **E4** | DSR « registre » (G3) | N = nombre d'essais du registre. Deux variances des Sharpe hebdomadaires sont publiées : celle de la **famille** (convention utilisée pour G3 sur S1) et celle de **tous les essais exécutés** du registre. **(S2)** proposition : G3 avec la plus grande des deux (prudente) | La spécification ne fixait pas la variance ; celle de la famille déflate presque rien (variantes quasi identiques) |
| **E5** | PBO (C6, G4) | C6 reste évalué sur S1 avec la convention figée (10 blocs égaux, semaines anciennes en surnombre ignorées, λ = 0 compté comme sur-ajustement). Sensibilité publiée : toutes les semaines (`array_split`), λ = 0 compté pour ½, famille sans clone exact, famille simulée de quasi-clones, PBO nulle de référence ⌊(N + 1)/2⌋/N (5/9 pour N = 9). **(S2)** proposition : λ = 0 compté pour ½ et clones exacts retirés avant la CSCV | Avec N = 9 impair, la PBO nulle vaut 5/9 > 0,5 ; E = A (aucun avis de dividende daté à l'avance) |
| **E6** | Variante E sur S1 | Déclarée **non testée** : ses rendements sont identiques à ceux de A, faute d'avis de dividende daté à l'avance dans les données | Fait de données |
| **E7** | IC mensuels (G7, D7) | Une seule décision par mois civil (la dernière du mois, §3.1.5) ; le seuil « au moins 36 mois » compte des mois distincts | En mode « evenementiel », les décisions d'événement donnaient plusieurs IC par mois |
| **E8** | Empreinte de configuration (D12) | Référence de pré-enregistrement citée : commit `751d1be` (spécification ; YAML 1.0, empreinte `dcdf1fb7db530c44`). L'empreinte `f1582ed8e9fa1c85` est celle de l'état figé `a2bfeb4`, écrite dans le même commit que le run : ce n'est pas une valeur pré-enregistrée indépendante. **(S2)** enregistrer l'empreinte dans un commit antérieur à l'état figé | Contrôle autoréférentiel |
| **E9** | Règles pays après S1 (§4.3, D10) | **(S2, et diagnostics S0)** : élection active sur [J − 30 ; J + 10] séances, la date d'un scrutin étant publique à l'avance ; durée des règles coup / sévère / levée comptée depuis la première **séance** du calendrier qui suit l'annonce (BOC manquants compris), et non depuis le premier BOC disponible. La chronologie D10 de S1 reste appliquée telle qu'elle a été figée (élection connue la veille du scrutin) | Revue quantitative du 22/11/2026 |

**Constat connu, non corrigé à ce jour (S0 et suivi réel seulement)** : les signaux MOM6_1, MOM12_1, LOWVOL et le dosage du momentum lisent l'indice TR construit avec le montant de dividende **corrigé** dès le jour ex, avant la publication de la correction (contraire à D6 : signaux = ligne (d)). Écart d'environ 0,5 % du niveau TR du titre entre le jour ex et la publication de la correction (CIEC 2021 : 167,14 contre 176,14 FCFA, du 19 au 28/07/2021) ; aucune décision de fin de mois de S1 dans ces fenêtres (audit). À corriger par un indice TR point-in-time des signaux avant le suivi réel S2.

**Décisions humaines attendues (non tranchées ici, nouvel essai à juger sur S2 seulement)** : (i) plancher D1 pour les filtres d'univers et âge des ordres compté en séances après un trou de BOC (univers vide du 30/07/2021 ; ordres de la décision du 13/08/2021 expirés pendant le trou de BOC) ; (ii) mise en œuvre du repli D8 (dividendes et produit des sorties forcées gardés en liquidités jusqu'au rebalancement annuel : REF investi à 82 % en moyenne sur S1, contre une cible de 98 %).

---

## 9. Gestion du risque

### 9.1 Règles de position et de portefeuille

| Règle | Seuil | Justification |
|---|---|---|
| **Pas de stop-loss de prix par ligne** | — | Sous les bandes de ±7,5 %, un stop vend au plancher, où les vendeurs ne sont souvent pas servis, juste avant le rebond médian de +3,1 % [R02] §7.1 |
| Revue obligatoire d'une ligne | sous-performance > 25 % contre le TR sur 63 séances, ou R4, R9, R11 | Une sortie n'est décidée que sur un critère fondamental ou de risque, et exécutée de façon échelonnée |
| Drawdown relatif contre le TR | −10 % : alerte ; **−15 % : exposition active divisée par 2** (w = 0,5·w_cible + 0,5·w_EW éligible) jusqu'à un retour à −7,5 % ou pendant 6 mois ; **−20 % : arrêt** et mode « indice discipliné » | Pré-enregistré ; compté comme partie de A |
| Drawdown absolu | aucune réduction automatique dans A (le mandat est investi en actions) ; la variante F teste le dosage par le régime | §4.4 |
| Tracking error ex ante | cible de 6 à 12 % ; au-delà de 14 % (covariance hebdomadaire rétrécie), les poids actifs sont réduits | [R03] §8.5 |
| CVaR | CVaR 95 % à 5 séances ≤ 1,25 × CVaR du TR, sur 5 000 scénarios bootstrap (blocs de 8 semaines) plus des stress ; contrôle mensuel ; jamais sur des scénarios journaliers (troncature à ±7,5 %) | [R04] §12.4 ; Rockafellar & Uryasev 2000 [A13] |
| Plafonds | ligne ≤ 10 % (× multiplicateurs) ; secteur ≤ 45 % ; pays §4.2 ; bloc AES ≤ 10,6 % par siège et ≤ 18 % en λ ; poches S1 ≤ 20 % et S4 ≤ 15 % | §4, §5, §6 |
| Liquidité | sortie possible en 20 séances à 10 % de participation ; rapport quotidien des jours de liquidation | [R01] |
| Qualité des données | tout rendement journalier > \|50 %\| ou tout écart de capitalisation reconstruite > 3 % bloque le calcul des signaux | [R08] §2.3 ; [C-SPEC] |

### 9.2 Risques spécifiques à la BRVM

- **Lien banques–souverain** : les effets publics font 31,3 % du bilan de BOA Mali et les obligations publiques 35,7 % de celui de Coris. Les services financiers représentent environ 44 % de la capitalisation. Un stress souverain se transmet aux banques du pays [R05] §1.3.
- **Concentration** : les 5 premières valeurs font 49,16 % de la capitalisation (20/08/2026) [R05] §1.1.
- **Exposition hors zone FCFA** : environ 12 % du marché (Guinée, Sierra Leone, ETIT) [R05] §11.2.

### 9.3 Scénarios de stress (appliqués chaque mois au portefeuille réel)

| # | Scénario | Paramètres | Base empirique |
|---|---|---|---|
| ST1 | Marché baissier long | Rejouer le chemin du TR du 01/03/2017 au 26/10/2020 (−46,7 %) et du prix depuis fin 2015 (−59,8 % en 58 mois) | [C-SPEC] ; [R08] §4.3 |
| ST2 | Pire année | 2018 : Composite −29,1 %, baisse intra-annuelle maximale −33,0 % ; TR reconstruit −25,1 % | [R08] ; [C-SPEC] |
| ST3 | Correction rapide | −15 % en 8 semaines (pire 8 semaines observé : −14,3 %) | [R04] §12.4 |
| ST4 | Choc pays sévère AES | −26 % sur le pays en 9 séances, dont 3 au plancher sans vendeur servi (rejeu Niger 2023) ; variante Mali 2022 (plancher dès t+1) | [R05] §9 |
| ST5 | Stress souverain Sénégal | SN −9 % relatif en 60 séances (audit 2024) ; stress : −26 % sur BOAS et SNTS | [R05] §9, §12 (hypothèse pour le stress) |
| ST6 | Liquidité | Participation divisée par 2 (5 %) et demi-spread × 2 pendant 20 séances | hypothèse de conception |
| ST7 | Coûts | Scénario sévère du §7.2 sur toute la période | §7.2 |
| ST8 | Suspension d'une ligne | La plus grosse ligne est suspendue 60 séances (SICC et SEMC depuis le 16/09/2026), valorisée à −10 % puis −30 % | [R07] §4.7 |
| ST9 | Erreur de données | Split non ajusté (SNTS, faux −89,3 %) : le contrôle doit bloquer | [R08] §1 |
| ST10 | Rupture de parité ou sortie de l'UEMOA | Règle « sévère » sur les titres AES et filiales de SNTS ; perte de change non chiffrée (aucune source dans la session) | [R05] §7 |

---

## 10. Ce que la plate-forme ne peut PAS promettre

1. **Aucun gain garanti, ni absolu, ni relatif.**
   - Avec un vrai Sharpe de 1,0, la probabilité d'une année négative est de 15,9 % ; avec 0,5, elle est de 30,9 % [R04] §4.6.
   - Avec un IR réel de 0,3 contre le TR, la probabilité de sous-performer l'indice une année donnée vaut Φ(−0,3) ≈ **38 %**, et sur 5 ans en cumul Φ(−0,3·√5) ≈ **25 %** [D].
2. **On ne peut pas prouver rapidement un alpha.** À 95 %, il faut environ **30 ans** de données hebdomadaires pour établir un IR de 0,3, et 10,8 ans pour un IR de 0,5 [R04] §4.6 ; [D]. Dix ans de BOC, 48 titres et un seul cycle complet (baisse 2017-2020, hausse 2021-2026) ne suffisent pas.
3. **Les marchés baissent, parfois longtemps.**
   - Le TR a perdu 46,7 % entre 2017 et 2020 [C-SPEC] ; le Composite prix est resté environ 9 ans et demi sous son niveau de fin 2015 [R08] ;
   - 43 % des fenêtres de 12 mois sont négatives (2017-2026) [R08] ;
   - une stratégie investie en actions subit ces baisses.
4. **Les professionnels n'y arrivent pas régulièrement** : 28 à 30 % des années-fonds battent le TR [R08] §3.3.
5. **Les effets s'affaiblissent quand ils sont connus et exploités.** La fenêtre du dividende est passée de +5 à +6 % brut (2018-2023) à environ +2,9 % (2026) [R07]. Les primes publiées diminuent de 26 % hors échantillon et de 58 % après publication aux États-Unis (McLean & Pontiff 2016 [A12]).
6. **Les coûts mangent la marge.** Le coût aller-retour complet vaut environ 3 à 3,5 % pour un titre médian (§7.2) ; les frais fixes atteignent environ 1 %/an pour un petit portefeuille.
7. **Le risque politique est brutal et imprévisible** (coups d'État, sanctions) : −26 % en 9 séances au Niger, sans délai de sortie au Mali [R05].
8. **Les données ont des limites.**
   - Pas de BOC avant 2017 au format du projet ; trous en 2021 ;
   - fondamentaux en partie scannés ;
   - taxes et IRVM en partie non vérifiés ;
   - **aucune étude académique citée n'a pu être relue** en ligne pendant les revues (hôtes bloqués) : leurs chiffres restent **[NON VÉRIFIÉ]**.
9. **Le régime de liquidité a changé** : environ 30 fois plus de valeur échangée en 2026 qu'en 2019-2020. Les résultats de 2017-2022 décrivent un autre marché que celui de 2026.

**Ce que la plate-forme garantit en revanche (engagements de processus)** :
- des données conformes au BOC et point-in-time ;
- une performance toujours publiée **nette de coûts** contre le **TR**, la médiane des fonds et le panier équipondéré, avec intervalles de confiance, DSR, PBO et nombre d'essais ;
- des critères de succès et d'échec fixés d'avance et appliqués, y compris le **rejet** ;
- des règles de risque qui priment sur les signaux ;
- un bandeau permanent : « Performance passée ≠ garantie. Aucun gain n'est garanti. Statut : [REJETÉ / CANDIDAT / PROMU] ».

---

## 11. Paramètres de calibration

Légende de la confiance : H = haute, M = moyenne, B = basse ; NV = [NON VÉRIFIÉ] ; « choix » = choix de conception, hyperparamètre non validé.

| Nom (clé de configuration) | Valeur | Source | Conf. |
|---|---|---|---|
| `market.price_limit_pct` | 0,075 autour de la référence ajustée (actions et obligations, y compris le jour d'introduction) | Instruction I-A [B3] ; BOC 2018-2026 [R01] | H |
| `market.band_rounding` | basse = ceil, haute = floor au pas ; au moins un pas | 11 avis + BOC [R01] §3.2 | H |
| `market.tick` | 1 FCFA si cours < 100, sinon 5 | BOC 2017-2026 [R01] §2.3 | H |
| `market.lot_size` | 1 | [B3] | H |
| `market.settlement_lag` | J+3 jusqu'au 03/12/2025 ; J+2 depuis le 04/12/2025 | Instruction 03-2025 [B5] | H |
| `market.ex_date_rule` | 2 jours ouvrés avant les registres (≤ 03/12/2025) ; 1 jour ouvré ensuite | [B5] ; lignes (V) du BOC [R01] | H |
| `market.sessions_per_year` | 252 (convention) ; réel ≈ 248 | numéros des BOC [R04] §2 | H |
| `timing.news_cutoff_utc` | 09:00 | horaires [B13] ; [R07] | H |
| `costs.brvm_fee` / `costs.dcbr_fee` | 0,0020 / 0,0010 par côté | [B1][B2] | H |
| `costs.sgi_commission` | 0,008 central (0,005 / 0,010 / 0,015) | [B6][B7] ; [R02] | M |
| `costs.vat_on_commission` | 0,18 central (0,10 en variante) | [R01][R02] | B, NV |
| `costs.regulator_fee` | 0 | introuvable [R01] | B |
| `costs.half_spread_default` | 0,0035 ; par titre = ½ spread médian sur 120 séances | BOC 2026 [R01] §5.2 | H (mesure) |
| `costs.impact_coef` | 0,016 central (0,010 / 0,032 / 0,050) | hypothèse de 50 pb à 10 % de participation [R02] | B, choix |
| `costs.annual_custody` | 0,0025 | [B6][B7] | H |
| `costs.account_fee_per_line_fcfa` | 5 000 (0 chez FGI) | [B6][B7] | H |
| `tax.irvm` | CI 0,12 ; SN 0,10 ; BF 0,125 (NV) ; ML 0,07 ; NE 0,07 ; BJ par émetteur (LNBB et BICB 0,05 ; BOAB 0,10) ; TG : net du BOC | [R01] §6.1 ; [B12] | H / M / B |
| `tax.capital_gains_individual` | 0 | [R01] §6.2 | B, NV |
| `universe.min_traded_fraction_120` | 0,50 | [R04] §2.1 ; code | M |
| `universe.min_history_sessions` | 126 (et au moins 40 rendements sur 63 séances) | [R03] §7.1 | M |
| `universe.min_float` | 0,15 | avis 303-2026 [B8] | H |
| `universe.mdv63_floor_fcfa` | max(500 000 ; 0,05 × K) | [C-SPEC] | M, choix |
| `universe.low_liquidity_tier_fcfa` | < 2 000 000 ⇒ poids max × 0,5 | [R02][R03] | M, choix |
| `universe.max_spread_for_full_weight` | 0,015 | [R06a] §9.4 | B, choix |
| `universe.min_names_for_selection` | 15 (sinon panier équipondéré) | [R04] §16 ; [C-SPEC] | M, choix |
| `universe.stale_financials_days` | 546 jours après la clôture de l'exercice | [R06b] §7.1 | M |
| `signals.ep` | 1/PER si PER > 0 ; surcharges ETIT (BPA 10,00) et ORGT (BPA 264) ; winsorisation 1-99 | [R03] §9 ; [R06a] §9.1 | H (données) |
| `signals.dy` | DPS net ordinaire du dernier exercice dont l'AGO est connue / cours ; garde-fou de 15 mois ; plafond 0,15 | [R06b] §6 A2 | H |
| `signals.mom6_1` | fenêtre de 126 séances, saut de 21, au moins 100 observations | [R03] §8.2 | M |
| `signals.lowvol` | 250 séances (au moins 200) ; repli 126 (au moins 100) | [R03] §9 ; Blitz & van Vliet 2007 | M |
| `signals.quality_proxy` | années de dividende sur 5 ; PER compris entre 3 et 40 | [R03] §8.2 | B |
| `signals.zscore` | rang gaussien, écrêté à ±3, manquant = 0 ; moins de 3 blocs ⇒ S = 0 | [R03] §9 | M |
| `weights.A` | EP 0,15 ; DY 0,20 ; MOM6_1 0,35 ; LOWVOL 0,20 ; QUAL 0,10 | [R03] §8.2 (pré-enregistré) | M |
| `weights.B` / `weights.C` | B : 0,25 / 0,25 / 0,50 ; C : 0,15 / 0,20 / 0,20 (6-1) / 0,15 (12-1) / 0,20 / 0,10 | [R03] §8.4 | B / M |
| `momentum.vol_scaling` | fenêtre de 126 séances ; cible = médiane expansive ; plancher 0,5 | Barroso & Santa-Clara [A6] ; [R03] | M |
| `momentum.crash_filter` | TR sur 24 mois < 0 et volatilité sur 63 séances > 80ᵉ centile ⇒ × 0,5 pendant 3 mois | Daniel & Moskowitz [A7] ; [R03] §5.3 | B, choix |
| `learning.ic` | Spearman, h = 21, au moins 15 titres ; IC_prior 0,02 (documenté) / 0 (nouveau) ; n₀ = 36 ; plafond 0,08 | [R04] §15.4, §16.4 | M |
| `learning.shrink_to_equal` | 0,5 | [R04] ; DeMiguel et al. [A9] | M |
| `learning.factor_momentum_min_months` | 120 | [R03] §9 | M |
| `portfolio.n_holdings` | clip(round(N_elig/3), 12, 20) | [R03] §8.3 ; [C-SPEC] | M, choix |
| `portfolio.band` | entrée dans les 30 % supérieurs ; sortie sous les 50 % supérieurs ; mensuel | [R03] §7.3 ; Novy-Marx & Velikov [A8] | M |
| `portfolio.max_weight` / `min_weight` | 0,10 / 0,02 | [R03] | M |
| `portfolio.country_multiplier` | CI 1,0 ; BJ 1,0 ; TG 0,9 ; SN 0,85 ; BF 0,75 ; ML 0,7 ; NE 0,6 | [R06a] §9.4 | B, choix |
| `portfolio.sector_cap` | max(0,15 ; min(0,45 ; 1,5 × u_s)) | [R03] ; [R06a] | B, choix |
| `portfolio.country_cap_non_ci` | min(0,30 ; max(0,10 ; 1,5 × max(u_c, b_c))) | [R03] ; [R05] | B, choix |
| `portfolio.aes_cap` | 1,25 × référence (≈ 10,6 % par siège ; ≈ 18 % en λ) | [R05] §13.3 | M |
| `portfolio.cash_buffer` | 0,02 | code | M |
| `portfolio.no_trade_band` | 0,02 | code | M |
| `portfolio.max_turnover_per_rebalance` | 0,50 | code | M |
| `execution.price` | VWAP de t+1 ; report des ordres pendant au plus 10 séances | ARCHITECTURE.md ; [R01] | M |
| `execution.max_participation` | 0,10 du volume du jour | [R01][R02][R03] | M, choix |
| `execution.days_to_liquidate` | 20 | code | M |
| `kelly.fraction` / `fraction_max` / `max_gross` | 0,25 / 0,5 / 1,0 (variante H, poids actifs seulement) | [R04] §11.4 | M |
| `covariance` | Ledoit-Wolf, corrélation constante, W-FRI, 104 semaines (minimum 52), plancher d'intensité 0,5 | [R04] §8.4 | H |
| `hrp` | lien `single`, `distance_of_distances=True` | [R04] §9.3 | M |
| `cvar` | α = 0,95 ; horizon de 5 séances ; 5 000 scénarios (b = 8 semaines) ; plafond de 1,25 × CVaR du TR ; stress de −15 % en 8 semaines et de −50 % en 190 semaines | [R04] §12.4 | M |
| `regime` | Markov à 2 états, TR hebdomadaire ; probabilités filtrées ; variante F : × 0,75 si P > 0,8 et drawdown < −8 % | [R04] §14.4 | B |
| `macro.rf_local` | 100/PER − prime (médiane sur 20 séances) ; 5,75 % depuis le 05/01/2024 | [R05] §1.2 | H |
| `macro.local_spread_vs_ci_pp` | BJ 0,05 ; ML 0,57 ; TG 0,92 ; NE 0,95 ; SN 0,97 ; BF 1,07 | [R05] §6.2 | H |
| `macro.crp` | CI 0 ; BJ 0,9 ; TG 2,2 ; SN 3,05 ; ML 4,1 ; NE 5,1 ; BF 5,3 ; hors UEMOA 4,0 % | [R05] §12.2 | M |
| `macro.erp_brvm` | 0,040 (sensibilité de 3 à 6 %) | moyenne de la prime BOC 2021-2025 [R05] | M |
| `macro.jump_loss` | sévère 0,21 (stress 0,26) ; modéré 0,08 | [R05] §9 | M |
| `macro.jump_prob` | CI 2/10 % ; BJ et TG 4/15 % ; SN 2/30 % ; ML 10/30 % ; NE et BF 12/30 % ; GW 15/30 % | dire d'expert [R05] §12 | B |
| `events.severe` | poids ≤ 0,25 × référence ; gel des achats pendant 60 séances ; retour sur 20 séances ; ventes dès t+1 | [R05] §13.4 | M |
| `events.bond_discount` | médiane < 0,97 sur 20 séances, au moins 5 transactions | [R05] §13.4 | M |
| `valuation_regime.prime_bands` | chère < 1 % ; neutre 1-4 % ; bon marché > 4 % (information) | [R05] §14.1 | H |
| `dividend.S1` | rendement ≥ 4 % ; MDV60 ≥ 1 M ; au moins 3 séances ; limite × 1,02 ; sortie au fixing du jour ex ; 5 % par titre et 20 % au total ; coupe-circuit sur 30 opérations ; activation si l'aller-retour réel ≤ 2,0 % | [R07] §6.5 ; [C-SPEC] (condition d'activation) | H (mesure) / B (futur) |
| `dividend.S2` | −0,5 écart-type pendant 20 séances après la date ex | [R07] §6.5 | M |
| `dividend.sell_deferral` | vente reportée au jour ex si la date ex tombe dans les 15 séances et que le rendement ≥ 4 % | [R07] §4.3 ; choix | M |
| `events.S4` | désactivé ; annuels et T1 ; AR[0,+1] ≥ 3 % ; entrée en J+2 ; détention de 20 séances | [R07] §6.5 | B |
| `events.R7_deadlines` | 30/04 (annuels, T1) ; 31/10 (S1, T3) ; rouge à +61 jours | avis 214-2026 et 291-2025 [R07] | H |
| `events.R9_R10` | seuil −25 % du RN consolidé ; R10 à partir du 01/10/2025 | instruction 01-2025 [B11] | H |
| `sentiment` | niveau 0 ; w_num 0,7 / w_tone 0,3 ; τ = 10 séances ; poids S5 = 0 | [R07] §3.4 | B, choix |
| `validation.samples` | S0 2022-11-17 → 2026-11-20 (contaminé) ; S1 2017-01-02 → 2022-11-16 (vierge) ; S2 à partir du 01/12/2026 | [R03] §8 ; [R04] | H |
| `validation.eval_frequency` | W-FRI | [R04] §17.2 | H |
| `validation.dsr_min` / `psr_min` | 0,95 / 0,95 | [A1] | H |
| `validation.pbo_max` | 0,25 (promu), 0,5 (candidat) ; pente > −0,5 | [R04] ; choix | B |
| `validation.min_t` | 3,0 (nouveau signal) ; 2,0 (facteur documenté et prédéclaré) | [A3] | H |
| `validation.bootstrap` | stationnaire ; 8 semaines / 20 séances ; plancher 10 ; n_boot 5 000 | [R04] §7.4 | H |
| `validation.walk_forward` | train 2 ans ; test 3 mois ; embargo h + 21 ; min_train 480 | [R04] §6.3 | M |
| `validation.cpcv` | 10 groupes, k = 2, purge 21, embargo 21 | [R04] §17.2 | M |
| `validation.n_trials_start` | 55 (S0) + 8 (S1) | [R03] §7.3 ; [R04] §3.4 | M |
| `benchmark.primary` | Composite TR officiel (≥ 02/01/2025), reconstruit avant (écart de 0,18 pb par jour) | [B9] ; [C-SPEC] | H |
| `benchmark.facts` | TR 2017-2026 : 12,7 %/an ; drawdown max −46,7 % ; prix 5,7 %/an | [C-SPEC] | H |
| `risk.relative_dd` | −10 % alerte ; −15 % actif ÷ 2 ; −20 % arrêt | choix | B |
| `risk.te_target` | 6-12 % ; plafond 14 % | [R03] §8.5 ; choix | B |
| `expectations.net_excess_vs_tr` | −1 à +3 %/an, centre ≈ +1 % ; IR ≈ 0 à 0,3 | dérivé de [R03] §8.5 + demi-spread | B |

---

## 12. Implications pour la plate-forme (paramètres prêts à coder)

### 12.1 Fichier `brvm_alpha/config/strategy_v1.yaml`

```yaml
# BRVM Alpha — stratégie v1 (SPECIFICATION_STRATEGIE.md, 22/11/2026). Paramètres FIGÉS avant le test S1.
version: "1.0"
capital_fcfa_reference: 10_000_000
capacity_variants_fcfa: [100_000_000, 1_000_000_000]

data:
  price_source: "BOC"                       # jamais le bandeau du site ni les transactions sur dossier
  dividend_amount: "boc_d_line_net"         # ligne (d) ; jamais les BOC suivants (BOAC 594,53)
  multi_session_gap_days: 4
  exclude_stats_windows: [["2021-05-06", "2021-06-25"]]
  missing_boc_is_not_holiday: true
  fundamentals_availability: "first_preopen_after(max(prefix+1 session, http_last_modified))"
  fundamentals_fallback_lag_sessions: 2
  eps_override: {ETIT: 10.00, ORGT: 264}
  max_abs_daily_return_guard: 0.50
  cap_reconstruction_tolerance: 0.03

benchmark:
  primary: "BRVM_COMPOSITE_TR"
  official_from: "2025-01-02"
  pre_official: "reconstructed_full_cap"   # r_TR = r_Composite + Σ N_i·D_net_i / Cap_publiée(t-1) ; validé : 0,18 pb/jour
  secondary: ["EW_TR_ELIGIBLE", "BRVM_COMPOSITE", "BRVM_10_until_2022-12-30", "BRVM_30_from_2023-01-02", "OPCVM_EQUITY_MEDIAN"]

universe:
  exclude_status: ["suspended"]
  resume_buffer_sessions: 5
  min_history_sessions: 126
  min_obs_63: 40
  min_traded_fraction_120: 0.50
  min_free_float: 0.15
  mdv63_floor_fcfa: "max(500000, 0.05 * capital)"   # valeur médiane sur 63 séances, séances sans échange = 0
  low_liquidity_tier_fcfa: 2_000_000                  # en dessous : poids max x 0,5
  max_spread_full_weight: 0.015                       # au-delà : poids max x 0,5
  stale_financials_days: 546
  min_names_for_selection: 15                         # sinon panier équipondéré éligible

signals:
  transform: {winsor_pct: [1, 99], zscore: "rank_gauss", clip: 3.0, missing: 0.0, min_valid_blocks: 3}
  ep: {def: "1/PER if PER>0 else rank_min", per_basis: "group_share_if_available"}
  dy: {def: "dps_net_ordinary(last_fy_with_known_AGM)/price", zero_if_no_dividend_voted: true, max_age_months: 15, cap: 0.15, exclude_exceptional: true}
  mom6_1: {lookback_sessions: 126, skip_sessions: 21, min_obs: 100}
  lowvol: {window_sessions: 250, min_obs: 200, fallback_window: 126, fallback_min_obs: 100, sign: -1}
  quality_proxy: {dividend_years_of_5: 0.5, per_sane_range: [3, 40], per_sane_weight: 0.5}
  neutralization: none                                # variante D : value dans les secteurs >= 4 titres

composite:
  A: {ep: 0.15, dy: 0.20, mom6_1: 0.35, lowvol: 0.20, quality_proxy: 0.10}
  B: {ep: 0.25, dy: 0.25, mom6_1: 0.50}
  C: {ep: 0.15, dy: 0.20, mom6_1: 0.20, mom12_1: 0.15, lowvol: 0.20, quality_proxy: 0.10}
  momentum_vol_scaling: {window_sessions: 126, target: "expanding_median", min_history_months: 24, floor: 0.5}
  momentum_crash_filter: {bear_lookback_months: 24, vol_window_sessions: 63, vol_percentile: 80, multiplier: 0.5, duration_months: 3}
  s2_post_ex_penalty_sd: -0.5
  s2_sessions: 20

learning:                                             # phase 2 seulement
  ic_method: spearman
  ic_horizon_sessions: 21
  ic_min_names: 15
  ic_prior: {documented: 0.02, new: 0.0}
  ic_prior_strength_months: 36
  ic_cap: 0.08
  shrink_to_equal: 0.5
  min_oos_months: 36
  walk_forward: {train_years: 2, test_months: 3, embargo_days: 42, expanding: true, min_train_days: 480}
  factor_momentum_min_months: 120

portfolio:
  long_only: true
  gross_equity: 0.98
  n_holdings: "clip(round(N_elig/3), 12, 20)"
  band: {enter_top_pct: 30, exit_below_top_pct: 50}
  weighting: equal                                    # G : hrp_tilt(gamma=0.5) ; H : mv_alpha(lambda=5)
  max_weight: 0.10
  min_weight: 0.02
  country_multiplier: {CI: 1.0, BJ: 1.0, TG: 0.9, SN: 0.85, BF: 0.75, ML: 0.7, NE: 0.6}
  sector_cap: "max(0.15, min(0.45, 1.5*u_s))"
  country_cap_non_ci: "min(0.30, max(0.10, 1.5*max(u_c, b_c)))"
  aes_cap_multiple: 1.25                              # siège ET exposition λ
  liquidity: {max_participation: 0.10, days_to_liquidate: 20}
  rebalance: "last_session_of_month"
  no_trade_band: 0.02
  max_turnover_per_rebalance: 0.50
  kelly: {fraction: 0.25, fraction_max: 0.5, max_gross: 1.0, scope: "active_weights_variant_H_only"}

execution:
  price: "vwap_t_plus_1"
  carry_unfilled_max_sessions: 10
  max_volume_participation: 0.10
  price_limit: 0.075
  limit_tolerance: 0.002
  block_buy_at_upper_limit: true
  block_sell_at_lower_limit: true
  cancel_orders_on_ex_and_split_days: true
  settlement: [{until: "2025-12-03", lag: 3}, {from: "2025-12-04", lag: 2}]
  dividends: "net_credited_on_payment_date_kept_in_cash"

costs:
  scenarios:
    optimistic: {sgi: 0.005, tax: 0.10, half_spread_mult: 1.0, impact_coef: 0.010, custody: 0.0,    line_fee: 0}
    central:    {sgi: 0.008, tax: 0.18, half_spread_mult: 1.0, impact_coef: 0.016, custody: 0.0025, line_fee: 5000}
    stress:     {sgi: 0.010, tax: 0.18, half_spread_mult: 1.5, impact_coef: 0.032, custody: 0.005,  line_fee: 5000}
    severe:     {sgi: 0.015, tax: 0.18, half_spread_mult: 2.0, impact_coef: 0.050, custody: 0.005,  line_fee: 10000}
  brvm_fee: 0.0020
  dcbr_fee: 0.0010
  regulator_fee: 0.0
  half_spread: "0.5 * median_close_spread_120 ; floor tick/(2*price) ; default 0.0035"
  capital_gains_tax: 0.0                               # NON VÉRIFIÉ

events:
  news_cutoff_utc: "09:00"
  ex_date_rule: [{until: "2025-12-03", bd_before_record: 2}, {from: "2025-12-04", bd_before_record: 1}]
  sell_deferral_to_ex: {max_sessions_to_ex: 15, min_net_yield: 0.04}
  S1: {enabled_in_variant: E, activate_live_if_round_trip_le: 0.020, min_net_yield: 0.04, min_mdv60_fcfa: 1_000_000, min_sessions_to_ex: 3, limit_mult: 1.02, exit: "close_fixing_ex_date", max_per_name: 0.05, max_total: 0.20, kill_switch: {trades: 30, min_mean_net: 0.0, min_hit: 0.50}}
  S3: {enabled: false}
  S4: {enabled: false, types: [RES_ANNUAL, ACT_Q1], min_ar_0_1: 0.03, entry_lag_sessions: 2, hold_sessions: 20, max_per_name: 0.05, max_total: 0.15}
  S5_news_score: {weight: 0.0, min_ic: 0.05, min_years: 3, decay_sessions: 10}
  risk_filters:
    R1: {block_buys: true, resume_buffer: 5, liquidity_haircut: 0.10}
    R2: {quality_penalty: -1, sessions: 60}
    R3: {exclude: true}
    R4: {max_weight_mult: 0.5, sessions: 120}
    R5: {block_buys_until_rights_detached: true}
    R6: {freeze_auto_signals: true}
    R7: {deadlines: {RES_ANNUAL: "04-30", ACT_Q1: "04-30", RES_S1: "10-31", ACT_Q3: "10-31"}, red_after_days: 61, quality_penalty_at_red: -0.5}
    R8: {sessions: 5}
    R9: {block_buys: true, disable: [S1, S4], quality_penalty: -1, sessions: 60}
    R10: {rn_drop: -0.25, lookback_days: 120, quality_penalty: -0.5, effective_from: "2025-10-01"}
    R11_fin_flags: {one_flag_weight_mult: 0.5, two_flags: exclude}
    R12_nonfin_flags: {weight_mult: 0.5}

macro_overlay:
  rf_local: {method: "median20(100/PER - prime)", outlier_pp: 0.10, confirm_sessions: 5}
  country_event_rules: {severe: {cap_x_ref: 0.25, freeze_buys_sessions: 60, rampback_sessions: 20, sell_from: "t+1", backtest_first_session_limit_down: true},
                        coup_no_sanctions: {freeze_buys_sessions: 20, max_x_ref: 1.0},
                        relief: {sessions: 20, max_x_ref: 1.0},
                        election: {window: [-30, 10], no_overweight: true},
                        downgrade_or_fiscal: {country_cap_mult: 0.75, sessions: 120},
                        bond_discount: {median_lt: 0.97, lookback: 20, min_trades: 5, country_cap_mult: 0.75}}
  regime: {model: "markov_2state_weekly_TR", probabilities: "filtered", variant_F: {p_turbulent: 0.8, tr_drawdown: -0.08, exposure_mult: 0.75, exit_p_lt: 0.5, exit_weeks: 4}}
  valuation_bands: {expensive_lt: 1.0, cheap_gt: 4.0, use: "information_and_stress_only"}
  country_score_weight: 0.0

risk:
  no_price_stop_loss: true
  review_if_rel_underperf_63: -0.25
  relative_dd: {alert: -0.10, halve_active: -0.15, recover_to: -0.075, halve_max_months: 6, stop: -0.20}
  te_target: [0.06, 0.12]
  te_cap: 0.14
  cvar: {alpha: 0.95, horizon_sessions: 5, scenarios: 5000, block_weeks: 8, max_ratio_vs_tr: 1.25}
  stress_tests: [ST1_bear_2017_2020, ST2_2018, ST3_minus15_8w, ST4_AES_severe, ST5_senegal, ST6_liquidity, ST7_costs_severe, ST8_suspension, ST9_split_error, ST10_peg]

validation:
  samples: {S0_contaminated: ["2022-11-17", "2026-11-20"], S1_preregistered: ["2017-01-02", "2022-11-16"], S2_live_from: "2026-12-01"}
  subperiods_S1: [["2017-01-02", "2019-12-31"], ["2020-01-01", "2022-11-16"]]
  variants: [A, B, C, D, E, F, G, H]
  eval_frequency: "W-FRI"
  sharpe_report: [naive, lo, glm]
  lo_q: {daily: 10, weekly: 4, monthly: 2}
  psr_min: 0.95
  dsr_min: 0.95
  pbo: {n_splits_weekly: 10, n_splits_daily: 16, max_promoted: 0.25, max_candidate: 0.5, min_slope: -0.5, metric: "sharpe_lo_active_net"}
  haircut: {method: "bhy", min_hsr: 0.3}
  min_t: {new: 3.0, documented: 2.0}
  bootstrap: {method: "stationary", mean_block_weekly: 8, mean_block_daily: 20, floor_daily: 10, n_boot: 5000}
  cpcv: {n_groups: 10, k_test: 2, purge: 21, embargo: 21}
  n_trials_start: 63
  reject_if: {active_net_central_le: 0.0, active_net_stress_lt: -0.01, subperiod_ir_lt: -0.5, rel_dd_lt: -0.20, abs_dd_worse_than_tr_by: 0.10}
  candidate_if: {active_net_central_gt: 0.0, active_net_stress_ge: -0.005, ir_ge: 0.20, both_subperiods_positive: true, rel_dd_ge: -0.20, turnover_month_le: 0.20, pbo_le: 0.5, cvar_ratio_le: 1.25}
  promoted_if: "G1-G9 sur S1 ET >= 12 mois de S2"
  fallback_mode: "indice_discipline"      # 15-20 plus grosses capitalisations éligibles, rebalancement annuel
  live_stop: {rolling_months: 36, active_net_lt: 0.0, t_lt: -1.0}
```

### 12.2 Changements de code (par module)

| Module | Changement | Priorité |
|---|---|---|
| `config.py` | Remplacer les `# À CALIBRER` : `CostModel(sgi_commission=0.008, brvm_fee=0.002, dcbr_fee=0.001, regulator_fee=0.0, vat_on_commission=0.18, impact_coef=0.016, annual_custody=0.0025)` + champs `half_spread_default`, `account_fee_per_line_fcfa` ; `TaxModel` du §7.3 ; `Constraints(max_weight=0.10, min_weight=0.02, max_names=20, min_names=12, max_sector_weight=0.45, max_adv_participation=0.10)` ; `ExecutionModel(max_volume_participation=0.10)` ; `UniverseFilter(min_history_days=126, min_median_value_fcfa=max(500_000, 0.05·capital))` | 1 |
| `data/store.py` | `shares_outstanding_panel()` (avis 303 + facteurs) ; `composite_tr_reconstructed()` (test : écart médian < 0,5 pb par jour sur 2026, niveau à ±0,2 % au 20/11/2026) ; drapeaux `multi_session`, `NC`, `SP` | 1 |
| `data/boc_parser.py` | En-tête du BOC (PER, prime, rendement) ; `parse_sovereign_bonds()` ; section OPCVM | 2 |
| `quant/features.py` | `dividend_yield` fondé sur l'AGO ; surcharges de BPA ; `mom6_1` en séances ; modulateurs du momentum | 1 |
| `quant/scoring.py` | Score composite avec règle des 3 blocs ; malus S2 ; variante D (rang par secteur) | 1 |
| `quant/stats.py` | `dimson_betas(leads=1, lags=5)` ; `glm_smoothing` ; `politis_white_block` ; `pbo_cscv(metric=sharpe_lo)` ; `n_boot=5000` par défaut dans la validation | 2 |
| `quant/regime.py` | `risk_scale(asof)` (variante F) ; ré-estimation sur 2017-2026 | 3 |
| `quant/macro.py` (nouveau) | `ref_govt_rate`, `local_spread_curve`, `bond_price_stress`, `country_crp`, matrice λ | 3 |
| `portfolio/construct.py` | Sélection avec bande 30/50 ; `n_holdings` ; plafonds secteur, pays et AES (siège et λ) ; multiplicateurs ; Kelly sur les poids actifs (H) | 1 |
| `backtest/engine.py` | Demi-spread par titre ; frais de tenue par ligne ; annulation des ordres le jour ex et le jour de split ; report au plus pendant 10 séances ; règlement J+3/J+2 ; crédit du dividende à la date de paiement ; plancher sans vendeur servi en choc sévère | 1 |
| `backtest/walkforward.py` | `TrialRegistry` (`reports/trials.parquet`) ; `cpcv` ; `purged_kfold` ; évaluation des statuts REJETÉ / CANDIDAT / PROMU | 1 |
| `events/` (nouveau paquet) | Collecteur brvm.org, horodatage, types d'événements, R1-R12, S1, S2, calendrier des dividendes | 2 |
| `report/html.py` | Bandeau de statut ; performance nette contre le TR, la médiane des OPCVM et le panier EW ; trois Sharpe ; DSR avec N ; PBO ; MinTRL restant ; courbe de capacité ; stress tests | 2 |

### 12.3 Tests unitaires de non-régression (valeurs du 20/11/2026)

1. TR reconstruit au 20/11/2026 ∈ [198,2 ; 199,0] (officiel 198,63) ; écart médian sur 2026 < 0,5 pb par jour.
2. `ref_govt_rate(20/11/2026)` = 5,75 % ± 0,01 ; vaut 5,75 % le 17/11/2026 malgré la prime imprimée à 0,01.
3. `price_band(4385)` = (4060, 4710) ; `price_band(13, ETIT)` haute = 14.
4. `ex_date(SNTS, paiement 2026-05-26)` = 2026-05-22 ; `ex_date(SNTS, paiement 2025-05-22)` = 2025-05-20.
5. `dy_used(FTSC, 2026-11-20)` = 0 ; `ep(ETIT)` = 10/57.
6. Univers à K = 10 M au 30/06/2020 : entre 15 et 26 titres ; à K = 1 Md : mode repli.
7. Un achat est bloqué quand la clôture est à la borne haute ; une vente est bloquée à la borne basse ; en rejeu de BOAN du 03 au 08/08/2023, les ventes ne sont pas servies aux séances au plancher.
8. Le registre compte au moins 63 essais avant la première exécution de S1 (au moins 65 après l'additif v1.1 : variante I et référence REF-ID).

---

## 13. Questions ouvertes et données à acquérir (ordre de priorité)

1. **Avis d'opéré réel** d'une SGI : taux exact du courtage, taxe (TAF ou TVA), redevances. Cela tranche le coût central et l'activation de S1.
2. **Accès réseau** à `www.bceao.int`, `umoatitres.org`, `www.imf.org`, `pages.stern.nyu.edu`, `doi.org`, `www.mdpi.com`, `www.tandfonline.com` et `www.sciencedirect.com`, pour lever les [NON VÉRIFIÉ] (taux BCEAO 2025-2026, multiplicateur de Damodaran, textes de Gbenro & Moussa 2019, Steyn et al. 2024, de Groot et al. 2012). Le budget de recherche web de cette session était épuisé : une nouvelle session pourra reprendre ces recherches.
3. **Historique avant 2017** (CD historique de la BRVM) pour une deuxième période baissière.
4. **Fondamentaux point-in-time** (RN part du groupe, fonds propres, ROE, NPL) pour QUAL v2 et le PER corrigé de SNTS et ORAC.
5. **Publications 2017-2021** (pages 1 à 3 des émetteurs) pour pouvoir tester S4.
6. **Fiscalité** : IRVM du BF, du BJ (par émetteur) et du TG ; plus-values ; régime des non-résidents.
7. **Impact de marché** : calibrer κ à partir des carnets d'ordres du BOC (`order_book.parquet`) et des exécutions réelles du suivi S2.

---

## Sources

### Documents internes (versions vérifiées, 22/11/2026)
- [R01] `docs/research/01-structure-marche.md` : règles de marché, frais, fiscalité, opérations sur titres, indices.
- [R02] `docs/research/02-litterature-brvm.md` : efficience, limites, plafonds bas et hauts, coûts aller-retour corrigés.
- [R03] `docs/research/03-facteurs-marches-frontieres.md` : facteurs, composite A/B/C, bande, résultats internes 2022-2026, DSR 0,65.
- [R04] `docs/research/04-rigueur-quantitative.md` : PBO, DSR, validation, bootstrap, covariance, HRP, BL, Kelly, CVaR, régimes.
- [R05] `docs/research/05-macro-geopolitique-uemoa.md` : rf local, spreads, CRP, chocs pays, règles d'événements.
- [R06a] `docs/research/06a-societes-financieres.md` et [R06b] `docs/research/06b-societes-non-financieres.md` : fondamentaux, anomalies de données, drapeaux.
- [R07] `docs/research/07-actualite-sentiment-evenements.md` : sources, horodatage, études d'événements, S1-S5, R1-R10.
- [R08] `docs/research/08-outils-et-pratiques-analystes.md` : outils, fonds contre indices, performance des indices 2010-2026.
- [C-SPEC] Calculs de cette spécification : `docs/annexes-spec/univ_breadth.py` et `docs/annexes-spec/tr_reconstruction.py`, sur `data/panel/*.parquet` (BOC 2017-2026 téléchargés depuis https://www.brvm.org/fr/bulletins-officiels-de-la-cote).
- [D] Dérivations mathématiques présentées dans le texte (Φ, MinTRL).

### Sources primaires BRVM et AMF-UMOA (consultées par les revues entre 2025 et le 22/11/2026)
- [B1] Frais applicables : https://www.brvm.org/fr/node/312
- [B2] Tarification BRVM – DC/BR (mise à jour du 01/01/2014) : https://www.brvm.org/sites/default/files/9_pj_tarification_-_v_010710_maj_01012014_v4_-_valide_ca_002.pdf
- [B3] Règles de négociation, d'admission et de radiation (Instructions I-A et I-E, art. 1123 et 1125) : https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf
- [B4] BOC n° 222 du 20/11/2026 : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (copie locale `data/boc_text/boc_20261120.txt.gz`, relue le 22/11/2026)
- [B5] Instruction N°03-2025/BRVM/DG (J+3 → J+2, date ex) : https://www.brvm.org/sites/default/files/instruction_03_2025_brvm_dg_reduction_delai_j3_j2_0.pdf
- [B6] Décision PAMF-UMOA 326-2024 (tarifs de BICI Bourse) : https://www.brvm.org/sites/default/files/decision_ndeg326_sgi_bici_bourse_homologation_des_tarifs_de_la_sgi_bici_bourse.pdf
- [B7] Décision PAMF-UMOA 124-2025 (tarifs de FGI) : https://www.brvm.org/sites/default/files/decision_ndegpamf-umoa_-_124_-_2025_-_homologation_des_tarifs_de_la_sgi_fgi.pdf
- [B8] Avis 303-2026 (flottant au 31/12/2025, nombre de titres) : https://www.brvm.org/sites/default/files/20261012_-_avis_ndeg303_brvmdg_-_flottant_des_societes_cotees_a_la_brvm.pdf
- [B9] Avis 308-2025 (BRVM Composite Total Return) : https://www.brvm.org/sites/default/files/20251224_-_avis_ndeg308_brvmdg_-_affichage_de_lindice_brvm_composite_total_return_index.pdf
- [B10] robots.txt de brvm.org (`Crawl-delay: 10`) : https://www.brvm.org/robots.txt
- [B11] Instruction N°01-2025 (alerte sur résultats) : https://www.brvm.org/sites/default/files/instruction_ndeg01-2025-brvm-dg_-_profit_warning_1.pdf
- [B12] Calendrier de paiement des dividendes, exercice 2025 : https://www.brvm.org/sites/default/files/20261006_-_calendrier_de_paiement_des_dividendes_-_exercice_2025.pdf
- [B13] Horaires de cotation : https://www.brvm.org/fr/horaires-de-cotation
- Avis 289-2026 (BRVM 30, T4-2026) : https://www.brvm.org/sites/default/files/20261001_-_avis_ndeg289_brvmdg_-_composition_de_lindice_brvm_30.pdf
- Avis 309-2026 (fractionnement de Sonatel) : https://www.brvm.org/sites/default/files/20261023_-_avis_ndeg309_brvmdg_-_fractionnement_dactions_valeur_theorique_-_sonatel_sn.pdf
- Liste des paiements de dividendes : https://www.brvm.org/fr/esv/paiement-de-dividendes
- Textes réglementaires : https://www.brvm.org/fr/textes-reglementaires/reglement-general-instructions-circulaires-et-autres-textes-publies-par-la
- Historique de la BRVM (cotation en continu depuis le 16/09/2013) : https://www.brvm.org/fr/historique
- Page des indices : https://www.brvm.org/fr/indices

### Références académiques (citées d'après les revues ; non relues en ligne dans cette session, voir les verdicts des revues)
- [A1] Bailey & López de Prado (2014), Deflated Sharpe Ratio : https://papers.ssrn.com/abstract=2460551
- [A2] Bailey, Borwein, López de Prado & Zhu (2017), Probability of Backtest Overfitting : https://papers.ssrn.com/abstract=2326253
- [A3] Harvey, Liu & Zhu (2016), « …and the Cross-Section of Expected Returns » : https://www.nber.org/papers/w20592
- [A4] López de Prado (2016), Hierarchical Risk Parity : https://papers.ssrn.com/abstract=2708678
- [A5] Ledoit & Wolf (2004), « Honey, I Shrunk the Sample Covariance Matrix » : https://econ-papers.upf.edu/papers/691.pdf
- [A6] Barroso & Santa-Clara (2015), Momentum has its moments : https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120
- [A7] Daniel & Moskowitz (2016), Momentum crashes : https://www.nber.org/papers/w20439
- [A8] Novy-Marx & Velikov (2016), A Taxonomy of Anomalies and their Trading Costs : https://www.nber.org/papers/w20721
- [A9] DeMiguel, Garlappi & Uppal (2009), Optimal versus Naive Diversification : https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html
- [A10] de Groot, Pang & Swinkels (2012), value et momentum dans les marchés frontières : https://econpapers.repec.org/RePEc:eee:empfin:v:19:y:2012:i:5:p:796-818 (chiffres mensuels **[NON VÉRIFIÉ]**)
- [A11] Zaremba & Maydybura (2019), facteurs dans les marchés frontières : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3332958
- [A12] McLean & Pontiff (2016), résumé CFA Institute : https://rpc.cfainstitute.org/research/cfa-digest/2016/06/does-academic-research-destroy-stock-return-predictability-digest-summary
- [A13] Rockafellar & Uryasev (2000), Optimization of CVaR (version de travail) : https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf (volume et pages **[NON VÉRIFIÉ]**)
- [A14] Blitz, Pang & van Vliet (2013), faible volatilité dans les émergents : https://ideas.repec.org/a/eee/ememar/v16y2013icp31-45.html
- [A15] Clarke, de Silva & Thorley (2002), coefficient de transfert : https://ideas.repec.org/a/taf/ufajxx/v58y2002i5p48-66.html
- [A16] MacLean, Thorp & Ziemba (2010), Kelly fractionnel : https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf
- [A17] Harvey & Liu (2015), Backtesting : https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF
- [A18] Patton, Politis & White (2009), longueur de bloc corrigée : https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf
- [A19] Gbenro & Moussa (2019), retour à la moyenne sur la BRVM : https://doi.org/10.3390/jrfm12010038 (**[NON VÉRIFIÉ]**)
- [A20] Sous-évaluation des introductions à la BRVM (*Revue du Chercheur*) : https://zenodo.org/records/4009093
- [A21] Obalade et al. (2022), effets calendaires en fenêtre glissante : https://ojs.tripaledu.com/jefa/article/view/71
- [A22] Mémoire de Tamandja (moyennes mobiles sur la BRVM) : https://www.memoireonline.com/04/07/410/m_efficience-boursiere-gestion-de-portefeuille-brvm5.html
- Goyal & Wahal (2015), absence d'écho du momentum hors des États-Unis : https://ideas.repec.org/a/cup/jfinqa/v50y2015i06p1237-1267_00.html
- Asness, Moskowitz & Pedersen (2013), Value and Momentum Everywhere : https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere
- Hartzmark & Solomon (2013), dividend month premium : https://doi.org/10.1016/j.jfineco.2013.03.011
- Bernard & Thomas (1989), dérive après publication : https://doi.org/10.2307/2491062
- Steyn, Gilbert & Viviers (2024), faible volatilité en Afrique frontière : https://www.tandfonline.com/doi/abs/10.1080/10293523.2024.2361986 (**[NON VÉRIFIÉ]**)

---

## Annexe — Calculs de l'architecte [C-SPEC] (reproductibles)

1. **Largeur de l'univers** : `python3 -I docs/annexes-spec/univ_breadth.py data/panel/equities.parquet 0,250000,500000,1000000,2000000,5000000,10000000`. Médiane, par année, du nombre de titres éligibles aux fins de mois (U3 + MDV63, séances sans échange comptées à 0 ; titres suspendus exclus).
2. **Liquidité historique** : médiane des valeurs médianes par titre, les jours d'échange : 2,31 M FCFA (2017), 0,40 M (2019), 0,59 M (2020), 1,83 M (2023), 17,5 M (2026). Contrôle : valeur ≈ volume × clôture (ratio médian de 1,000 chaque année).
3. **Nombre de titres et TR** : `python3 -I docs/annexes-spec/tr_reconstruction.py /home/user/documentation/brvm-alpha`. Le nombre de titres vient de l'avis 303-2026 (tableau [R01] §11), propagé vers le passé avec les splits et ajustements de confiance high ; SAFC vaut 8 119 750 titres avant le 11/08/2026. Résultats :
   - ratio entre capitalisation reconstruite et publiée : 1,0195 (01/03/2017), 1,0216 (31/12/2018), 1,0029 (31/12/2020), 1,0000 (30/12/2022), 1,0275 (31/12/2024), 1,0001 (20/11/2026) ;
   - TR : écart quotidien médian de 0,18 pb sur 219 séances de 2026 ; niveau de 198,45 contre 198,63 ;
   - TR annuels et drawdown : section 1.1. La reconstruction de 2021 peut omettre des dividendes tombés pendant les trous de BOC.
4. **Ce qui n'a PAS été fait volontairement** : aucune exécution d'une stratégie sur S1 (2017-01-02 → 2022-11-16). Cet échantillon reste vierge pour le test pré-enregistré du §8.
