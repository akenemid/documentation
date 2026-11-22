# BRVM Alpha — Diagnostic S0 — échantillon contaminé

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

> **Contaminé, aucune valeur de preuve.** S0 (2022-11-17 → 2026-11-20) a déjà été exploré par les revues et par la mise au point du moteur : ces chiffres servent à vérifier que la chaîne tourne, jamais à conclure. Les essais exécutés ici sont inscrits au registre et comptent dans N.

## 1. Contexte d'exécution (faits)

| Élément | Valeur |
|---|---|
| Commit | `751d1be729ac1501fe672eb47be084c794dac7a9` (branche claude/brvm-stock-analysis-platform-4myn3g) |
| Arbre `brvm_alpha/` et `configs/` identique à HEAD | non |
| Fichiers non suivis (permis, listés) | brvm_alpha/validation/__init__.py, brvm_alpha/validation/benchmarks.py, brvm_alpha/validation/lock.py, brvm_alpha/validation/report_md.py, brvm_alpha/validation/runner.py |
| Empreinte de configuration | `f1582ed8e9fa1c85` |
| Version du YAML | 1.1 |
| Horodatage (UTC) | 2026-11-22T08:23:26.317686+00:00 |
| Durée totale / des runs | 601,9 s / 574,7 s (3 processus) |
| Panel | /home/user/documentation/brvm-alpha/data/panel |
| Plan des runs | 30 runs |
| Événements pays chargés (D10) | 19 |
| Bootstrap stationnaire | n_boot = 5000 (explicite), blocs moyens de 8 semaines |

## 2. Fenêtre d'évaluation (additif v1.1, D2)

- **t0 = 01/12/2022** : première séance où la variante A (coûts centraux, 10 M FCFA) détient des titres. Toutes les variantes et tous les étalons sont évalués sur la **même** fenêtre [01/12/2022 ; 20/11/2026], rebasés à t0 (base 100 à la clôture de la veille de t0 : le rendement de t0, qui porte les frais d'achat initiaux, est compté).
- Sous-périodes : [01/12/2022 ; 31/12/2024] ; [01/01/2025 ; 20/11/2026].
- Fréquence : hebdomadaire (W-FRI), nette de tous les coûts ; annualisation à 52 semaines.
- Exclusions des statistiques : fenêtre(s) 06/05/2021 → 25/06/2021 et semaines couvrant plus de 6 séances (trous de BOC) : aucune.
- La fenêtre complète (depuis la première séance simulée, liquidités de démarrage comprises) est publiée en section 10 **pour information seulement**.

## 3. Étalons (sur [t0 ; fin], sans coûts)

| Code | Étalon | Disponible | Rendement an. | Vol. an. | Drawdown | Semaines | Note |
|---|---|---|---|---|---|---|---|
| TR | BRVM Composite Total Return (officiel raccordé, reconstruit avant) | oui | 34,9 % | 10,1 % | −11,2 % | 208 | source : store.composite_tr_reconstructed(official=True) |
| EW | panier équipondéré TR des éligibles de A (mensuel) | oui | 41,3 % | 12,1 % | −17,8 % | 208 | source : store.equal_weight_tr(masque PIT de A, rebalance='monthly') |
| PRIX | BRVM Composite (indice prix) | oui | 26,5 % | 9,9 % | −11,3 % | 208 | source : indices.parquet « BRVM COMPOSITE » |
| BRVM10 | BRVM 10 (jusqu'au 30/12/2022) | oui | 57,1 % | 16,0 % | −1,9 % | 5 | publié jusqu'au 30/12/2022 ; source : indices.parquet « BRVM 10 » |
| BRVM30 | BRVM 30 (à partir du 02/01/2023) | oui | 24,9 % | 10,5 % | −11,3 % | 203 | publié à partir du 02/01/2023 ; source : indices.parquet « BRVM 30 » |
| PRESTIGE | BRVM Prestige (à partir du 02/01/2023) | oui | 17,2 % | 11,1 % | −10,0 % | 203 | publié à partir du 02/01/2023 ; source : indices.parquet « BRVM PRESTIGE » |
| FONDS | médiane des fonds actions (catégorie A du BOC) | **non disponible** | n.d. | n.d. | n.d. |  | non disponible : les valeurs liquidatives des OPCVM actions (catégorie A du BOC) ne sont pas extraites dans le panel ; étalon non calculé (aucune série de substitution) ; source : aucune |
| EW_100M | panier équipondéré TR des éligibles de A à 100M FCFA | oui | 40,3 % | 12,2 % | −17,5 % | 208 |  |
| EW_1Md | panier équipondéré TR des éligibles de A à 1Md FCFA | oui | 35,2 % | 16,0 % | −16,0 % | 208 |  |

## 4. Variantes aux coûts centraux, 10 M FCFA (estimations)

| Var. | Rdt an. | Vol. | Actif / TR | Actif / EW | IR | TE | Sharpe naïf / Lo / GLM | PSR(0) | DSR (N = 78) | DSR (N = 9) | DD abs. | DD rel. TR | CVaR / TR | Rotation /mois | Coûts /an | Lignes | Investi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** | 23,3 % | 10,3 % | −11,6 % | −18,0 % | −1,67 | 5,4 % | 2,08 / 1,52 / 1,71 | 0,00 | 0,00 | 0,00 | −9,5 % | −32,1 % | 1,11 | 6,7 % | 4,46 % | 19,0 | 96,1 % |
| **B** | 22,4 % | 10,8 % | −12,5 % | −18,9 % | −1,45 | 6,7 % | 1,92 / 1,36 / 1,55 | 0,00 | 0,00 | 0,00 | −10,7 % | −34,3 % | 1,18 | 9,7 % | 5,94 % | 19,2 | 96,0 % |
| **C** | 23,6 % | 10,4 % | −11,2 % | −17,6 % | −1,48 | 5,9 % | 2,10 / 1,45 / 1,71 | 0,00 | 0,00 | 0,00 | −10,4 % | −31,0 % | 1,14 | 7,7 % | 4,88 % | 18,7 | 95,7 % |
| **D** | 23,5 % | 11,2 % | −11,4 % | −17,8 % | −1,36 | 6,4 % | 1,95 / 1,34 / 1,58 | 0,00 | 0,00 | 0,00 | −12,7 % | −31,2 % | 1,21 | 7,7 % | 4,82 % | 18,5 | 96,6 % |
| **E** | 23,3 % | 10,3 % | −11,6 % | −18,0 % | −1,67 | 5,4 % | 2,08 / 1,52 / 1,71 | 0,00 | 0,00 | 0,00 | −9,5 % | −32,1 % | 1,11 | 6,7 % | 4,46 % | 19,0 | 96,1 % |
| **F** | 23,3 % | 10,3 % | −11,6 % | −18,0 % | −1,67 | 5,4 % | 2,08 / 1,52 / 1,71 | 0,00 | 0,00 | 0,00 | −9,5 % | −32,1 % | 1,11 | 6,7 % | 4,46 % | 19,0 | 96,1 % |
| **G** | 23,6 % | 10,3 % | −11,2 % | −17,6 % | −1,68 | 5,2 % | 2,11 / 1,54 / 1,73 | 0,00 | 0,00 | 0,00 | −9,9 % | −30,9 % | 1,11 | 7,3 % | 4,64 % | 18,8 | 96,2 % |
| **H** | 23,3 % | 10,4 % | −11,5 % | −17,9 % | −1,68 | 5,3 % | 2,08 / 1,50 / 1,70 | 0,00 | 0,00 | 0,00 | −9,7 % | −31,8 % | 1,12 | 6,7 % | 4,43 % | 18,9 | 96,0 % |
| **I** | 29,0 % | 9,7 % | −5,9 % | −12,3 % | −0,93 | 4,8 % | 2,67 / 1,79 / 2,03 | 0,03 | 0,00 | 0,00 | −10,5 % | −17,8 % | 0,92 | 4,6 % | 3,73 % | 24,3 | 95,3 % |
| **REF** (réf.) | 28,9 % | 10,2 % | −6,0 % | −12,4 % | −1,40 | 3,2 % | 2,56 / 1,79 / 1,97 | 0,00 | 0,00 | 0,00 | −10,7 % | −19,9 % | 1,02 | 0,9 % | 1,64 % | 19,5 | 93,0 % |

⚠ : écart entre Sharpe de Lo et Sharpe GLM supérieur à 25 % (prix périmés à examiner, §8.2). PSR, DSR, IR et Sharpe portent sur les rendements **actifs** nets contre le TR (sauf la colonne Sharpe, rendements absolus). Coûts /an : coûts payés rapportés à la NAV moyenne.

## 5. Statuts du §8.3 (règles exactes, estimations)

| Var. | Statut | Rejets déclenchés (R1-R5) | Critères candidat non vérifiés (C1-C7) | Actif central | Actif stress | IR sous-périodes | t NW de l'IC | HSR (BHY) |
|---|---|---|---|---|---|---|---|---|
| **A** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,6 % | −14,0 % | −1,98 / −1,29 | 2,84 | −0,50 |
| **B** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −12,5 % | −13,4 % | −1,61 / −1,44 | 4,10 | −0,00 |
| **C** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,2 % | −13,1 % | −1,44 / −1,82 | 2,02 | −0,00 |
| **D** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,4 % | −12,4 % | −1,37 / −1,63 | 3,19 | −0,00 |
| **E** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,6 % | −14,0 % | −1,98 / −1,29 | 2,84 | −0,50 |
| **F** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,6 % | −14,0 % | −1,98 / −1,29 | 2,84 | −0,50 |
| **G** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,2 % | −13,8 % | −1,96 / −1,35 | 2,84 | −0,53 |
| **H** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,5 % | −13,4 % | −1,95 / −1,37 | 2,84 | −0,51 |
| **I** | **REJETÉ** | R1, R2, R3 | C1, C2, C3 | −5,9 % | −6,4 % | −1,57 / −0,39 | 2,77 | −0,00 |
| **REF** | **REJETÉ** (informatif) | R1, R2, R3 | C1, C2, C3 | −6,0 % | −6,7 % | −2,04 / −0,82 | n.d. | −0,00 |

REJETÉ : l'une des conditions R1-R5 est vraie. CANDIDAT : C1-C7 toutes vraies (paper trading autorisé). INDÉTERMINÉ : ni l'un ni l'autre, ou données insuffisantes (aucun suivi réel autorisé). **PROMU est impossible sans suivi réel S2** (au moins 12 mois ; G7 sur les IC S1 puis S2 bout à bout, au moins 36 mois, D7). La référence REF (« indice discipliné », D8) est évaluée pour information, hors famille de la PBO.

## 6. Famille (N = 9), PBO et règle de promotion du §3.4

- Variantes de la famille exécutées : A, B, C, D, E, F, G, H, I (complète) ; semaines communes : 208.
- **PBO (CSCV, S = 10 blocs hebdomadaires, Sharpe de Lo (q = 4) des rendements actifs nets contre le TR)** : 0,437 ; pente de dégradation : −0,517.
- Registre : N = 78 essais (DSR « registre » et haircut BHY) ; G1 (registre complet) : vert ; variance des Sharpe hebdomadaires entre variantes : 0,001196.
- Règle : §3.4 : X remplace A seulement si X bat A en actif net ET DSR ≥ 0,95 avec N = 9 ET PBO ≤ 0,25. **Variante principale après la règle : A**.

| Variante | Actif net an. | Bat A | DSR (N = 9) | Remplace A |
|---|---|---|---|---|
| A | −11,6 % | — | 0,00 | — |
| B | −12,5 % | non | 0,00 | non |
| C | −11,2 % | oui | 0,00 | non |
| D | −11,4 % | oui | 0,00 | non |
| E | −11,6 % | non | 0,00 | non |
| F | −11,6 % | non | 0,00 | non |
| G | −11,2 % | oui | 0,00 | non |
| H | −11,5 % | oui | 0,00 | non |
| I | −5,9 % | oui | 0,00 | non |

## 7. Intervalles du bootstrap stationnaire (95 %, rendements actifs contre le TR)

| Var. | IR [IC 95 %] | Actif moyen annualisé [IC 95 %] |
|---|---|---|
| A | −1,67 [−2,55 ; −0,82] | −9,0 % [−14,8 % ; −4,0 %] |
| B | −1,45 [−2,29 ; −0,64] | −9,7 % [−16,1 % ; −4,0 %] |
| C | −1,48 [−2,34 ; −0,65] | −8,7 % [−14,3 % ; −3,6 %] |
| D | −1,36 [−2,24 ; −0,53] | −8,8 % [−14,9 % ; −3,3 %] |
| E | −1,67 [−2,55 ; −0,82] | −9,0 % [−14,8 % ; −4,0 %] |
| F | −1,67 [−2,55 ; −0,82] | −9,0 % [−14,8 % ; −4,0 %] |
| G | −1,68 [−2,61 ; −0,82] | −8,7 % [−14,3 % ; −3,9 %] |
| H | −1,68 [−2,59 ; −0,80] | −8,9 % [−14,9 % ; −3,8 %] |
| I | −0,93 [−1,96 ; 0,08] | −4,5 % [−9,1 % ; +0,4 %] |
| REF | −1,40 [−2,43 ; −0,43] | −4,5 % [−7,6 % ; −1,4 %] |

## 8. Sous-périodes (coûts centraux, 10 M FCFA)

| Var. | Sous-période 1 | Sous-période 2 |
|---|---|---|
| A | [01/12/2022 ; 31/12/2024] : actif −15,6 %, IR −1,98, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,3 %, IR −1,29, 99 sem. |
| B | [01/12/2022 ; 31/12/2024] : actif −16,4 %, IR −1,61, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −7,3 %, IR −1,44, 99 sem. |
| C | [01/12/2022 ; 31/12/2024] : actif −12,7 %, IR −1,44, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −9,2 %, IR −1,82, 99 sem. |
| D | [01/12/2022 ; 31/12/2024] : actif −13,6 %, IR −1,37, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −8,4 %, IR −1,63, 99 sem. |
| E | [01/12/2022 ; 31/12/2024] : actif −15,6 %, IR −1,98, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,3 %, IR −1,29, 99 sem. |
| F | [01/12/2022 ; 31/12/2024] : actif −15,6 %, IR −1,98, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,3 %, IR −1,29, 99 sem. |
| G | [01/12/2022 ; 31/12/2024] : actif −14,9 %, IR −1,96, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,4 %, IR −1,35, 99 sem. |
| H | [01/12/2022 ; 31/12/2024] : actif −15,4 %, IR −1,95, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,4 %, IR −1,37, 99 sem. |
| I | [01/12/2022 ; 31/12/2024] : actif −8,2 %, IR −1,57, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −2,8 %, IR −0,39, 99 sem. |
| REF | [01/12/2022 ; 31/12/2024] : actif −7,5 %, IR −2,04, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −4,0 %, IR −0,82, 99 sem. |

## 9. Analyses de sensibilité (le même essai sous d'autres hypothèses ; hors PBO et DSR)

| Run | Rdt an. | Actif / TR | Actif / EW | IR | DD rel. TR | Rotation /mois | Coûts /an | Lignes | Investi |
|---|---|---|---|---|---|---|---|---|---|
| A (coûts de stress, 10 M FCFA) | 20,9 % | −14,0 % | −20,4 % | −1,99 | −36,5 % | 6,8 % | 6,35 % | 19,2 | 96,2 % |
| B (coûts de stress, 10 M FCFA) | 21,5 % | −13,4 % | −19,8 % | −1,80 | −35,1 % | 8,7 % | 7,51 % | 19,8 | 96,3 % |
| C (coûts de stress, 10 M FCFA) | 21,8 % | −13,1 % | −19,5 % | −1,67 | −34,8 % | 7,5 % | 6,80 % | 19,2 | 95,1 % |
| D (coûts de stress, 10 M FCFA) | 22,4 % | −12,4 % | −18,9 % | −1,44 | −33,7 % | 7,4 % | 6,48 % | 18,5 | 96,8 % |
| E (coûts de stress, 10 M FCFA) | 20,9 % | −14,0 % | −20,4 % | −1,99 | −36,5 % | 6,8 % | 6,35 % | 19,2 | 96,2 % |
| F (coûts de stress, 10 M FCFA) | 20,9 % | −14,0 % | −20,4 % | −1,99 | −36,5 % | 6,8 % | 6,35 % | 19,2 | 96,2 % |
| G (coûts de stress, 10 M FCFA) | 21,1 % | −13,8 % | −20,2 % | −2,00 | −36,4 % | 7,3 % | 6,56 % | 18,9 | 96,2 % |
| H (coûts de stress, 10 M FCFA) | 21,5 % | −13,4 % | −19,8 % | −1,92 | −35,3 % | 6,7 % | 6,20 % | 19,1 | 96,5 % |
| I (coûts de stress, 10 M FCFA) | 28,4 % | −6,4 % | −12,8 % | −1,02 | −19,4 % | 4,3 % | 4,98 % | 24,9 | 96,6 % |
| REF (coûts de stress, 10 M FCFA) | 28,1 % | −6,7 % | −13,1 % | −1,52 | −21,8 % | 0,9 % | 2,22 % | 19,5 | 93,3 % |
| A (coûts optimistes, 10 M FCFA) | 26,1 % | −8,8 % | −15,2 % | −1,19 | −26,2 % | 7,2 % | 2,86 % | 20,0 | 96,2 % |
| A (coûts sévères, 10 M FCFA) | 20,1 % | −14,8 % | −21,2 % | −2,14 | −38,3 % | 6,3 % | 8,72 % | 19,8 | 97,0 % |
| I (coûts optimistes, 10 M FCFA) | 32,1 % | −2,8 % | −9,2 % | −0,42 | −11,1 % | 4,5 % | 2,06 % | 24,1 | 95,8 % |
| I (coûts sévères, 10 M FCFA) | 25,8 % | −9,1 % | −15,5 % | −1,43 | −25,0 % | 4,2 % | 7,17 % | 25,2 | 97,0 % |
| A (coûts centraux, 100 M FCFA) | 25,5 % | −9,4 % | −14,8 % | −1,21 | −29,7 % | 6,1 % | 3,30 % | 13,5 | 86,8 % |
| A (coûts centraux, 1 Md FCFA) | 5,4 % | −29,5 % | −29,8 % | −2,95 | −67,5 % | 0,1 % | 0,12 % | 1,0 | 15,4 % |
| I (coûts centraux, 100 M FCFA) | 29,2 % | −5,6 % | −11,0 % | −0,77 | −20,7 % | 6,7 % | 4,16 % | 15,8 | 88,5 % |
| I (coûts centraux, 1 Md FCFA) | 6,0 % | −28,8 % | −29,2 % | −2,89 | −66,7 % | 0,0 % | 0,12 % | 1,0 | 17,6 % |
| REF (coûts centraux, 100 M FCFA) | 28,4 % | −6,5 % | −11,9 % | −0,98 | −23,8 % | 1,6 % | 1,26 % | 10,6 | 81,2 % |
| REF (coûts centraux, 1 Md FCFA) | 7,2 % | −27,7 % | −28,1 % | −2,79 | −65,3 % | 0,2 % | 0,22 % | 1,0 | 21,3 % |

Aux capacités de 100 M et 1 Md FCFA, le panier EW est celui des éligibles de A **au même capital** (plancher de liquidité U5 dépendant du capital).

## 10. Dividendes (D6) et fenêtre complète (information)

| Var. | Dividendes crédités | Ligne (d) du BOC | Écart | Rdt an. (complet) | Actif / TR (complet) | IR (complet) | DD rel. (complet) |
|---|---|---|---|---|---|---|---|
| A | 3 673 852 FCFA | 3 667 069 FCFA | 6 783 FCFA | 23,0 % | −11,3 % | −1,64 | −32,1 % |
| B | 3 480 375 FCFA | 3 472 738 FCFA | 7 637 FCFA | 22,1 % | −12,1 % | −1,42 | −34,3 % |
| C | 3 508 565 FCFA | 3 501 065 FCFA | 7 500 FCFA | 23,4 % | −10,9 % | −1,45 | −31,0 % |
| D | 3 689 067 FCFA | 3 682 276 FCFA | 6 791 FCFA | 23,2 % | −11,1 % | −1,33 | −31,2 % |
| E | 3 673 852 FCFA | 3 667 069 FCFA | 6 783 FCFA | 23,0 % | −11,3 % | −1,64 | −32,1 % |
| F | 3 673 852 FCFA | 3 667 069 FCFA | 6 783 FCFA | 23,0 % | −11,3 % | −1,64 | −32,1 % |
| G | 3 655 323 FCFA | 3 655 077 FCFA | 246 FCFA | 23,4 % | −10,9 % | −1,65 | −30,9 % |
| H | 3 650 341 FCFA | 3 644 027 FCFA | 6 313 FCFA | 23,1 % | −11,2 % | −1,64 | −31,8 % |
| I | 4 184 207 FCFA | 4 176 386 FCFA | 7 821 FCFA | 28,7 % | −5,6 % | −0,90 | −17,8 % |
| REF | 3 730 374 FCFA | 3 724 073 FCFA | 6 302 FCFA | 28,6 % | −5,7 % | −1,35 | −19,6 % |

Flux de trésorerie : montant **corrigé** (meilleure estimation du versement réel) ; signaux (DY, S1, S2) : montant connu en t, ligne (d) du BOC (D6). La fenêtre complète inclut les mois de liquidités de démarrage : elle crée un rendement actif mécanique et n'entre dans **aucun** critère (D2).

## 11. Faits, estimations, hypothèses et limites

**Faits** : cours, volumes, dividendes et numéros de BOC lus dans les bulletins officiels ; règles et seuils du §8.3 et de l'additif v1.1, figés avant l'exécution ; plan des runs et paramètres consignés dans `lock.json` (S1) et dans le registre `reports/trials.parquet`.

**Estimations** : toutes les métriques (rendements, IR, Sharpe, PSR, DSR, PBO, CVaR, intervalles du bootstrap) sont des estimations sur environ cinq ans de données hebdomadaires : leur incertitude est large (voir les intervalles de la section 7).

**Hypothèses** : barèmes de coûts du §7.2 (courtage, taxe [NON VÉRIFIÉ], demi-spread mesuré, impact κ·√π sans étude publiée) ; exécution au VWAP de t+1 avec participation ≤ 10 % ; Composite TR reconstruit avant le premier niveau officiel ; secteurs de 2025 appliqués à tout l'historique ; chronologie des événements pays [NON VÉRIFIÉ] en partie (D10) ; étalon « fonds actions » non disponible.

**Limites** : 129 séances sans BOC (dont 96 en 2021) ; rendements multi-séances exclus des statistiques ; annualisation conventionnelle (52 semaines) ; aucun suivi réel (S2) : le statut PROMU est impossible.

## 12. Prédiction du §8.3 (rappel, écrite avant l'exécution)

Prédiction écrite d'avance (§8.3, maintenue par l'additif v1.1) : avec un IR réel de 0,3, le z attendu sur S1 (5,9 ans) vaut 0,3 × √5,9 ≈ 0,73, soit un PSR ≈ 0,77 : G2 échouera probablement. Le statut le plus probable, même pour une bonne stratégie, est « candidat » ; le rejet de A est un résultat plausible (l'essai de fumée de S0 est défavorable). Un IR > 1 serait d'abord traité comme une ERREUR (anticipation, prix périmés, coûts oubliés).

## Fichiers

`metrics.json` (toutes les mesures), `weekly_returns.parquet` (rendements hebdomadaires nets des stratégies et des étalons sur la fenêtre d'évaluation), `nav.parquet` (valeurs liquidatives et niveaux, rebasés à t0), `trades.parquet` (exécutions de tous les runs), `contexte.json` (sans verrou).

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
