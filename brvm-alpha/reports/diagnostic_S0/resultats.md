# BRVM Alpha — Diagnostic S0 — échantillon contaminé

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

> **Contaminé, aucune valeur de preuve.** S0 (2022-11-17 → 2026-11-20) a déjà été exploré par les revues et par la mise au point du moteur : ces chiffres servent à vérifier que la chaîne tourne, jamais à conclure. Les essais exécutés ici sont inscrits au registre et comptent dans N.

## 1. Contexte d'exécution (faits)

| Élément | Valeur |
|---|---|
| Commit | `751d1be729ac1501fe672eb47be084c794dac7a9` (branche claude/brvm-stock-analysis-platform-4myn3g) |
| Arbre `brvm_alpha/` et `configs/` identique à HEAD, sans fichier non suivi | non |
| Fichiers non suivis (refusés sur S1, listés) | brvm_alpha/portfolio/recommend.py, brvm_alpha/portfolio/stress.py, brvm_alpha/validation/__init__.py, brvm_alpha/validation/benchmarks.py, brvm_alpha/validation/controls.py, brvm_alpha/validation/lock.py, brvm_alpha/validation/report_md.py, brvm_alpha/validation/runner.py |
| Empreinte de configuration | `f1582ed8e9fa1c85` (identique au pré-enregistrement v1.1) |
| Version du YAML | 1.1 |
| Horodatage (UTC) | 2026-11-22T09:18:19.901332+00:00 |
| Durée totale / des runs | 670,5 s / 643,9 s (3 processus) |
| Panel | /home/user/documentation/brvm-alpha/data/panel |
| Plan des runs | 30 runs |
| Événements pays chargés (D10) | 19 |
| Mode de décision | evenementiel (effectif : evenementiel) |
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

| Var. | Rdt an. | Vol. | Actif / TR | Actif / EW | IR | TE | Sharpe naïf / Lo / GLM | PSR(0) | DSR (N = 88) | DSR (N = 9) | DD abs. | DD rel. TR | CVaR / TR | Rotation /mois | Coûts /an | Lignes | Investi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** | 23,4 % | 10,4 % | −11,4 % | −17,8 % | −1,69 | 5,2 % | 2,08 / 1,50 / 1,70 | 0,00 | 0,00 | 0,00 | −9,9 % | −31,5 % | 1,13 | 6,8 % | 4,52 % | 19,1 | 96,0 % |
| **B** | 22,2 % | 10,8 % | −12,6 % | −19,0 % | −1,47 | 6,7 % | 1,92 / 1,36 / 1,55 | 0,00 | 0,00 | 0,00 | −10,5 % | −34,7 % | 1,17 | 9,6 % | 5,88 % | 19,2 | 95,7 % |
| **C** | 23,7 % | 10,4 % | −11,2 % | −17,6 % | −1,42 | 6,1 % | 2,09 / 1,44 / 1,71 | 0,00 | 0,00 | 0,00 | −10,6 % | −31,0 % | 1,14 | 7,7 % | 4,88 % | 18,7 | 95,5 % |
| **D** | 24,8 % | 11,1 % | −10,1 % | −16,5 % | −1,19 | 6,5 % | 2,06 / 1,42 / 1,69 | 0,01 | 0,00 | 0,00 | −10,9 % | −28,4 % | 1,17 | 7,5 % | 4,65 % | 18,5 | 96,5 % |
| **E** | 23,4 % | 10,4 % | −11,4 % | −17,8 % | −1,69 | 5,2 % | 2,08 / 1,50 / 1,70 | 0,00 | 0,00 | 0,00 | −9,9 % | −31,5 % | 1,13 | 6,8 % | 4,52 % | 19,1 | 96,0 % |
| **F** | 23,4 % | 10,4 % | −11,4 % | −17,8 % | −1,69 | 5,2 % | 2,08 / 1,50 / 1,70 | 0,00 | 0,00 | 0,00 | −9,9 % | −31,5 % | 1,13 | 6,8 % | 4,52 % | 19,1 | 96,0 % |
| **G** | 24,3 % | 10,4 % | −10,5 % | −17,0 % | −1,60 | 5,1 % | 2,14 / 1,54 / 1,73 | 0,00 | 0,00 | 0,00 | −10,1 % | −29,6 % | 1,09 | 7,2 % | 4,61 % | 18,9 | 96,0 % |
| **H** | 23,9 % | 10,5 % | −11,0 % | −17,4 % | −1,65 | 5,2 % | 2,09 / 1,49 / 1,69 | 0,00 | 0,00 | 0,00 | −10,3 % | −30,8 % | 1,14 | 6,6 % | 4,40 % | 18,8 | 96,4 % |
| **I** | 29,1 % | 9,7 % | −5,8 % | −12,2 % | −0,91 | 4,9 % | 2,68 / 1,79 / 2,03 | 0,04 | 0,00 | 0,00 | −10,4 % | −17,9 % | 0,91 | 4,6 % | 3,76 % | 24,2 | 95,2 % |
| **REF** (réf.) | 28,9 % | 10,2 % | −6,0 % | −12,4 % | −1,40 | 3,2 % | 2,56 / 1,79 / 1,97 | 0,00 | 0,00 | 0,00 | −10,7 % | −19,9 % | 1,02 | 0,9 % | 1,64 % | 19,5 | 93,0 % |

⚠ : écart entre Sharpe de Lo et Sharpe GLM supérieur à 25 % (prix périmés à examiner, §8.2). PSR, DSR, IR et Sharpe portent sur les rendements **actifs** nets contre le TR (sauf la colonne Sharpe, rendements absolus). Coûts /an : coûts payés rapportés à la NAV moyenne.

## 5. Statuts du §8.3 (règles exactes, estimations)

| Var. | Statut | Rejets déclenchés (R1-R5) | Critères candidat non vérifiés (C1-C7) | Actif central | Actif stress | IR sous-périodes | t NW de l'IC | HSR (BHY) |
|---|---|---|---|---|---|---|---|---|
| **A** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,4 % | −12,8 % | −1,98 / −1,36 | 3,25 | −0,50 |
| **B** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −12,6 % | −12,1 % | −1,61 / −1,49 | 4,66 | −0,00 |
| **C** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,2 % | −12,8 % | −1,31 / −1,88 | 2,33 | −0,00 |
| **D** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −10,1 % | −13,2 % | −1,42 / −0,90 | 3,56 | −0,00 |
| **E** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,4 % | −12,8 % | −1,98 / −1,36 | 3,25 | −0,50 |
| **F** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,4 % | −12,8 % | −1,98 / −1,36 | 3,25 | −0,50 |
| **G** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −10,5 % | −11,8 % | −1,96 / −1,08 | 3,26 | −0,24 |
| **H** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4 | −11,0 % | −13,1 % | −1,88 / −1,40 | 3,25 | −0,38 |
| **I** | **REJETÉ** | R1, R2, R3 | C1, C2, C3 | −5,8 % | −6,3 % | −1,55 / −0,36 | 3,18 | −0,00 |
| **REF** | **REJETÉ** (informatif) | R1, R2, R3 | C1, C2, C3 | −6,0 % | −6,7 % | −2,04 / −0,82 | n.d. | −0,00 |

REJETÉ : l'une des conditions R1-R5 est vraie. CANDIDAT : C1-C7 toutes vraies (paper trading autorisé). INDÉTERMINÉ : ni l'un ni l'autre, ou données insuffisantes (aucun suivi réel autorisé). **PROMU est impossible sans suivi réel S2** (au moins 12 mois ; G7 sur les IC S1 puis S2 bout à bout, au moins 36 mois, D7). La référence REF (« indice discipliné », D8) est évaluée pour information, hors famille de la PBO.

## 6. Famille (N = 9), PBO et règle de promotion du §3.4

- Variantes de la famille exécutées : A, B, C, D, E, F, G, H, I (complète) ; semaines communes : 208.
- **PBO (CSCV, S = 10 blocs hebdomadaires, Sharpe de Lo (q = 4) des rendements actifs nets contre le TR)** : 0,302 ; pente de dégradation : −0,616.
- Registre : N = 88 essais (DSR « registre » et haircut BHY) ; G1 (registre complet) : vert ; variance des Sharpe hebdomadaires entre variantes : 0,001428.
- Règle : §3.4 : X remplace A seulement si X bat A en actif net ET DSR ≥ 0,95 avec N = 9 ET PBO ≤ 0,25. **Variante principale après la règle : A**.

| Variante | Actif net an. | Bat A | DSR (N = 9) | Remplace A |
|---|---|---|---|---|
| A | −11,4 % | — | 0,00 | — |
| B | −12,6 % | non | 0,00 | non |
| C | −11,2 % | oui | 0,00 | non |
| D | −10,1 % | oui | 0,00 | non |
| E | −11,4 % | non | 0,00 | non |
| F | −11,4 % | non | 0,00 | non |
| G | −10,5 % | oui | 0,00 | non |
| H | −11,0 % | oui | 0,00 | non |
| I | −5,8 % | oui | 0,00 | non |

## 7. Intervalles du bootstrap stationnaire (95 %, rendements actifs contre le TR)

| Var. | IR [IC 95 %] | Actif moyen annualisé [IC 95 %] |
|---|---|---|
| A | −1,69 [−2,56 ; −0,83] | −8,9 % [−14,6 % ; −4,0 %] |
| B | −1,47 [−2,32 ; −0,65] | −9,8 % [−16,2 % ; −4,1 %] |
| C | −1,42 [−2,29 ; −0,60] | −8,7 % [−14,4 % ; −3,5 %] |
| D | −1,19 [−2,00 ; −0,40] | −7,7 % [−13,7 % ; −2,4 %] |
| E | −1,69 [−2,56 ; −0,83] | −8,9 % [−14,6 % ; −4,0 %] |
| F | −1,69 [−2,56 ; −0,83] | −8,9 % [−14,6 % ; −4,0 %] |
| G | −1,60 [−2,52 ; −0,71] | −8,2 % [−13,8 % ; −3,2 %] |
| H | −1,65 [−2,57 ; −0,74] | −8,5 % [−14,0 % ; −3,5 %] |
| I | −0,91 [−1,94 ; 0,10] | −4,4 % [−9,0 % ; +0,5 %] |
| REF | −1,40 [−2,43 ; −0,43] | −4,5 % [−7,6 % ; −1,4 %] |

## 8. Sous-périodes (coûts centraux, 10 M FCFA)

| Var. | Sous-période 1 | Sous-période 2 |
|---|---|---|
| A | [01/12/2022 ; 31/12/2024] : actif −15,3 %, IR −1,98, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,2 %, IR −1,36, 99 sem. |
| B | [01/12/2022 ; 31/12/2024] : actif −16,3 %, IR −1,61, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −7,7 %, IR −1,49, 99 sem. |
| C | [01/12/2022 ; 31/12/2024] : actif −12,2 %, IR −1,31, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −9,9 %, IR −1,88, 99 sem. |
| D | [01/12/2022 ; 31/12/2024] : actif −14,1 %, IR −1,42, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −4,7 %, IR −0,90, 99 sem. |
| E | [01/12/2022 ; 31/12/2024] : actif −15,3 %, IR −1,98, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,2 %, IR −1,36, 99 sem. |
| F | [01/12/2022 ; 31/12/2024] : actif −15,3 %, IR −1,98, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,2 %, IR −1,36, 99 sem. |
| G | [01/12/2022 ; 31/12/2024] : actif −14,8 %, IR −1,96, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −4,9 %, IR −1,08, 99 sem. |
| H | [01/12/2022 ; 31/12/2024] : actif −14,3 %, IR −1,88, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −6,5 %, IR −1,40, 99 sem. |
| I | [01/12/2022 ; 31/12/2024] : actif −8,2 %, IR −1,55, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −2,7 %, IR −0,36, 99 sem. |
| REF | [01/12/2022 ; 31/12/2024] : actif −7,5 %, IR −2,04, 109 sem. | [01/01/2025 ; 20/11/2026] : actif −4,0 %, IR −0,82, 99 sem. |

## 9. Analyses de sensibilité (le même essai sous d'autres hypothèses ; hors PBO et DSR)

| Run | Rdt an. | Actif / TR | Actif / EW | IR | DD rel. TR | Rotation /mois | Coûts /an | Lignes | Investi |
|---|---|---|---|---|---|---|---|---|---|
| A (coûts de stress, 10 M FCFA) | 22,0 % | −12,8 % | −19,3 % | −1,78 | −34,2 % | 6,7 % | 6,21 % | 19,3 | 96,1 % |
| B (coûts de stress, 10 M FCFA) | 22,7 % | −12,1 % | −18,5 % | −1,86 | −32,7 % | 7,6 % | 6,67 % | 20,4 | 95,7 % |
| C (coûts de stress, 10 M FCFA) | 22,1 % | −12,8 % | −19,2 % | −1,62 | −34,2 % | 7,5 % | 6,75 % | 19,2 | 95,2 % |
| D (coûts de stress, 10 M FCFA) | 21,6 % | −13,2 % | −19,6 % | −1,76 | −35,3 % | 7,3 % | 6,49 % | 19,3 | 95,2 % |
| E (coûts de stress, 10 M FCFA) | 22,0 % | −12,8 % | −19,3 % | −1,78 | −34,2 % | 6,7 % | 6,21 % | 19,3 | 96,1 % |
| F (coûts de stress, 10 M FCFA) | 22,0 % | −12,8 % | −19,3 % | −1,78 | −34,2 % | 6,7 % | 6,21 % | 19,3 | 96,1 % |
| G (coûts de stress, 10 M FCFA) | 23,0 % | −11,8 % | −18,2 % | −1,67 | −33,0 % | 7,1 % | 6,31 % | 19,1 | 96,2 % |
| H (coûts de stress, 10 M FCFA) | 21,7 % | −13,1 % | −19,5 % | −1,80 | −34,8 % | 6,7 % | 6,22 % | 19,2 | 95,9 % |
| I (coûts de stress, 10 M FCFA) | 28,6 % | −6,3 % | −12,7 % | −0,99 | −19,1 % | 4,3 % | 5,01 % | 24,9 | 96,7 % |
| REF (coûts de stress, 10 M FCFA) | 28,1 % | −6,7 % | −13,1 % | −1,52 | −21,8 % | 0,9 % | 2,22 % | 19,5 | 93,3 % |
| A (coûts optimistes, 10 M FCFA) | 25,0 % | −9,9 % | −16,3 % | −1,44 | −28,3 % | 6,8 % | 2,76 % | 18,8 | 95,1 % |
| A (coûts sévères, 10 M FCFA) | 22,9 % | −12,0 % | −18,4 % | −1,80 | −32,4 % | 5,4 % | 7,60 % | 20,4 | 97,0 % |
| I (coûts optimistes, 10 M FCFA) | 32,2 % | −2,7 % | −9,1 % | −0,41 | −11,0 % | 4,5 % | 2,04 % | 24,1 | 95,8 % |
| I (coûts sévères, 10 M FCFA) | 26,9 % | −7,9 % | −14,3 % | −1,26 | −23,0 % | 3,6 % | 6,23 % | 25,2 | 97,0 % |
| A (coûts centraux, 100 M FCFA) | 25,5 % | −9,4 % | −14,8 % | −1,21 | −29,7 % | 6,1 % | 3,30 % | 13,5 | 86,8 % |
| A (coûts centraux, 1 Md FCFA) | 5,4 % | −29,4 % | −29,8 % | −2,94 | −67,4 % | 0,1 % | 0,12 % | 1,0 | 15,6 % |
| I (coûts centraux, 100 M FCFA) | 29,6 % | −5,3 % | −10,7 % | −0,73 | −19,8 % | 6,7 % | 4,09 % | 16,0 | 88,6 % |
| I (coûts centraux, 1 Md FCFA) | 6,0 % | −28,8 % | −29,2 % | −2,89 | −66,7 % | 0,0 % | 0,12 % | 1,0 | 17,6 % |
| REF (coûts centraux, 100 M FCFA) | 28,4 % | −6,5 % | −11,9 % | −0,98 | −23,8 % | 1,6 % | 1,26 % | 10,6 | 81,2 % |
| REF (coûts centraux, 1 Md FCFA) | 7,2 % | −27,7 % | −28,1 % | −2,79 | −65,3 % | 0,2 % | 0,22 % | 1,0 | 21,3 % |

Aux capacités de 100 M et 1 Md FCFA, le panier EW est celui des éligibles de A **au même capital** (plancher de liquidité U5 dépendant du capital).

## 9 bis. Contrôles comptables et d'exécution (faits de simulation, aucune performance)

| Run | Contrôles verts | Cash min. | Exposition max. | Identité VL | Identité de flux | Ventes borne basse / achats borne haute | Coût par aller (médiane) | Coût par aller (moyenne pondérée) | Exécutions |
|---|---|---|---|---|---|---|---|---|---|
| A (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,18 % | 1.5e-16 | 2.9e-16 | 0 / 0 | 2,38 % | 2,34 % | 564 |
| A (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,20 % | 0.0e+00 | 2.4e-16 | 0 / 0 | 3,33 % | 3,28 % | 572 |
| B (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,17 % | 1.7e-16 | 3.0e-16 | 0 / 0 | 2,42 % | 2,31 % | 721 |
| B (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,07 % | 1.5e-16 | 2.8e-16 | 0 / 0 | 3,49 % | 3,35 % | 642 |
| C (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,11 % | 0.0e+00 | 2.1e-16 | 0 / 0 | 2,33 % | 2,34 % | 568 |
| C (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,22 % | 1.4e-16 | 2.3e-16 | 0 / 0 | 3,30 % | 3,32 % | 540 |
| D (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,16 % | 1.4e-16 | 2.3e-16 | 0 / 0 | 2,27 % | 2,29 % | 603 |
| D (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,22 % | 0.0e+00 | 2.6e-16 | 0 / 0 | 3,27 % | 3,24 % | 562 |
| E (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,18 % | 1.5e-16 | 2.9e-16 | 0 / 0 | 2,38 % | 2,34 % | 564 |
| E (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,20 % | 0.0e+00 | 2.4e-16 | 0 / 0 | 3,33 % | 3,28 % | 572 |
| F (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,18 % | 1.5e-16 | 2.9e-16 | 0 / 0 | 2,38 % | 2,34 % | 564 |
| F (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,20 % | 0.0e+00 | 2.4e-16 | 0 / 0 | 3,33 % | 3,28 % | 572 |
| G (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,17 % | 0.0e+00 | 2.6e-16 | 0 / 0 | 2,33 % | 2,30 % | 565 |
| G (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,21 % | 0.0e+00 | 2.6e-16 | 0 / 0 | 3,26 % | 3,23 % | 571 |
| H (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,15 % | 0.0e+00 | 2.9e-16 | 0 / 0 | 2,36 % | 2,33 % | 531 |
| H (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,22 % | 1.5e-16 | 2.9e-16 | 0 / 0 | 3,30 % | 3,27 % | 556 |
| I (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,09 % | 1.3e-16 | 2.6e-16 | 0 / 0 | 2,23 % | 2,15 % | 397 |
| I (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,10 % | 2.6e-16 | 2.3e-16 | 0 / 0 | 3,04 % | 3,03 % | 419 |
| REF (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 100,15 % | 0.0e+00 | 1.8e-16 | 0 / 0 | 2,30 % | 2,25 % | 118 |
| REF (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,20 % | 0.0e+00 | 2.2e-16 | 0 / 0 | 3,29 % | 3,15 % | 120 |
| A (coûts optimistes, 10 M FCFA) | oui | 7 FCFA | 100,00 % | 1.4e-16 | 2.4e-16 | 0 / 0 | 1,84 % | 1,82 % | 563 |
| A (coûts sévères, 10 M FCFA) | oui | 0 FCFA | 100,16 % | 1.6e-16 | 2.9e-16 | 0 / 0 | 4,69 % | 4,68 % | 518 |
| I (coûts optimistes, 10 M FCFA) | oui | 2 FCFA | 100,00 % | 1.5e-16 | 2.5e-16 | 0 / 0 | 1,71 % | 1,64 % | 405 |
| I (coûts sévères, 10 M FCFA) | oui | 0 FCFA | 100,17 % | 1.7e-16 | 2.6e-16 | 0 / 0 | 4,35 % | 4,33 % | 380 |
| A (coûts centraux, 100 M FCFA) | oui | 0 FCFA | 100,06 % | 1.3e-16 | 3.3e-16 | 0 / 0 | 2,25 % | 2,23 % | 952 |
| A (coûts centraux, 1 Md FCFA) | oui | 883 971 187 FCFA | 29,39 % | 0.0e+00 | 2.3e-16 | 0 / 0 | 2,01 % | 1,92 % | 23 |
| I (coûts centraux, 100 M FCFA) | oui | 0 FCFA | 100,01 % | 2.0e-16 | 2.5e-16 | 0 / 0 | 2,17 % | 2,15 % | 1269 |
| I (coûts centraux, 1 Md FCFA) | oui | 857 869 048 FCFA | 29,10 % | 0.0e+00 | 2.7e-16 | 0 / 0 | 1,92 % | 1,95 % | 11 |
| REF (coûts centraux, 100 M FCFA) | oui | 0 FCFA | 100,06 % | 0.0e+00 | 2.1e-16 | 0 / 0 | 2,23 % | 2,18 % | 229 |
| REF (coûts centraux, 1 Md FCFA) | oui | 767 009 501 FCFA | 29,13 % | 0.0e+00 | 2.5e-16 | 0 / 0 | 1,96 % | 2,00 % | 29 |

Cash réglé ≥ 0 à chaque séance (aucun levier) ; identités `VL = cash − frais dus + créances + Σ q·P` et `ΔVL = Σ q·ΔP + exécutions + dividendes − coûts` (écart maximal en fraction de la VL, tolérance 1e-06) ; aucune vente à la borne basse ni achat à la borne haute (§7.1.3). Une exposition légèrement supérieure à 100 % vient des frais de garde et de tenue de compte dus mais non encore payés (cash réglé nul en attendant un règlement J+3/J+2) : ce n'est pas un levier. Coût par aller : courtage, taxe, BRVM, DC/BR, demi-spread et impact rapportés au montant exécuté (§7.2 : environ 1,75 % pour un titre médian aux coûts centraux).

## 10. Dividendes (D6) et fenêtre complète (information)

| Var. | Dividendes crédités | Ligne (d) du BOC | Écart | Rdt an. (complet) | Actif / TR (complet) | IR (complet) | DD rel. (complet) |
|---|---|---|---|---|---|---|---|
| A | 3 658 100 FCFA | 3 651 123 FCFA | 6 976 FCFA | 23,2 % | −11,1 % | −1,66 | −31,5 % |
| B | 3 464 326 FCFA | 3 456 710 FCFA | 7 616 FCFA | 22,0 % | −12,3 % | −1,45 | −34,7 % |
| C | 3 500 026 FCFA | 3 492 505 FCFA | 7 522 FCFA | 23,4 % | −10,9 % | −1,39 | −31,0 % |
| D | 3 818 097 FCFA | 3 811 288 FCFA | 6 809 FCFA | 24,5 % | −9,8 % | −1,16 | −28,4 % |
| E | 3 658 100 FCFA | 3 651 123 FCFA | 6 976 FCFA | 23,2 % | −11,1 % | −1,66 | −31,5 % |
| F | 3 658 100 FCFA | 3 651 123 FCFA | 6 976 FCFA | 23,2 % | −11,1 % | −1,66 | −31,5 % |
| G | 3 609 775 FCFA | 3 609 268 FCFA | 507 FCFA | 24,1 % | −10,2 % | −1,56 | −29,6 % |
| H | 3 685 769 FCFA | 3 677 125 FCFA | 8 644 FCFA | 23,6 % | −10,7 % | −1,61 | −30,8 % |
| I | 4 184 048 FCFA | 4 176 227 FCFA | 7 821 FCFA | 28,8 % | −5,5 % | −0,88 | −17,9 % |
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
