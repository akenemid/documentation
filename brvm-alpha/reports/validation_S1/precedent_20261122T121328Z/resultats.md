# BRVM Alpha — Validation S1 — test unique pré-enregistré (additif v1.1)

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

> Test **unique** sur l'échantillon vierge S1 (2017-01-02 → 2022-11-16), paramètres figés avant l'exécution (§3.4, §8.3, additif v1.1 §8.4). Toute relance exige un bogue démontré (`--rerun-reason`) et crée de nouveaux essais.

## 1. Contexte d'exécution (faits)

| Élément | Valeur |
|---|---|
| Commit | `a2bfeb4c9b09c6a97f1208dfd7d585146455b651` (branche claude/brvm-stock-analysis-platform-4myn3g) |
| Arbre `brvm_alpha/` et `configs/` identique à HEAD, sans fichier non suivi | oui |
| Fichiers non suivis (refusés sur S1, listés) | aucun |
| Empreinte de configuration | `f1582ed8e9fa1c85` (identique au pré-enregistrement v1.1) |
| Version du YAML | 1.1 |
| Horodatage (UTC) | 2026-11-22T09:56:27.353723+00:00 |
| Durée totale / des runs | 679,4 s / 648,9 s (3 processus) |
| Panel | /home/user/documentation/brvm-alpha/data/panel |
| Plan des runs | 30 runs |
| Événements pays chargés (D10) | 19 |
| Mode de décision | evenementiel (effectif : evenementiel) |
| Bootstrap stationnaire | n_boot = 5000 (explicite), blocs moyens de 8 semaines |

## 2. Fenêtre d'évaluation (additif v1.1, D2)

- **t0 = 01/08/2017** : première séance où la variante A (coûts centraux, 10 M FCFA) détient des titres. Toutes les variantes et tous les étalons sont évalués sur la **même** fenêtre [01/08/2017 ; 16/11/2022], rebasés à t0 (base 100 à la clôture de la veille de t0 : le rendement de t0, qui porte les frais d'achat initiaux, est compté).
- Sous-périodes : [01/08/2017 ; 31/12/2019] ; [01/01/2020 ; 18/11/2022].
- Fréquence : hebdomadaire (W-FRI), nette de tous les coûts ; annualisation à 52 semaines.
- Exclusions des statistiques : fenêtre(s) 06/05/2021 → 25/06/2021 et semaines couvrant plus de 6 séances (trous de BOC) : 14/12/2018, 07/05/2021, 25/06/2021, 09/07/2021, 23/07/2021, 10/09/2021, 24/09/2021, 22/10/2021, 05/11/2021.
- La fenêtre complète (depuis la première séance simulée, liquidités de démarrage comprises) est publiée en section 10 **pour information seulement**.

## 3. Étalons (sur [t0 ; fin], sans coûts)

| Code | Étalon | Disponible | Rendement an. | Vol. an. | Drawdown | Semaines | Note |
|---|---|---|---|---|---|---|---|
| TR | BRVM Composite Total Return (officiel raccordé, reconstruit avant) | oui | −4,4 % | 12,5 % | −42,7 % | 255 | source : store.composite_tr_reconstructed(official=True) |
| EW | panier équipondéré TR des éligibles de A (mensuel) | oui | −4,1 % | 15,0 % | −45,3 % | 255 | source : store.equal_weight_tr(masque PIT de A, rebalance='monthly') |
| PRIX | BRVM Composite (indice prix) | oui | −9,6 % | 12,8 % | −52,6 % | 255 | source : indices.parquet « BRVM COMPOSITE » |
| BRVM10 | BRVM 10 (jusqu'au 30/12/2022) | oui | −8,7 % | 15,6 % | −49,8 % | 255 | publié jusqu'au 30/12/2022 ; source : indices.parquet « BRVM 10 » |
| BRVM30 | BRVM 30 (à partir du 02/01/2023) | **non disponible** | n.d. | n.d. | n.d. |  | publié à partir du 02/01/2023 ; source : indices.parquet « BRVM 30 » |
| PRESTIGE | BRVM Prestige (à partir du 02/01/2023) | **non disponible** | n.d. | n.d. | n.d. |  | publié à partir du 02/01/2023 ; source : indices.parquet « BRVM PRESTIGE » |
| FONDS | médiane des fonds actions (catégorie A du BOC) | **non disponible** | n.d. | n.d. | n.d. |  | non disponible : les valeurs liquidatives des OPCVM actions (catégorie A du BOC) ne sont pas extraites dans le panel ; étalon non calculé (aucune série de substitution) ; source : aucune |
| EW_100M | panier équipondéré TR des éligibles de A à 100M FCFA | oui | −6,9 % | 17,9 % | −42,3 % | 255 |  |
| EW_1Md | panier équipondéré TR des éligibles de A à 1Md FCFA | oui | 0,7 % | 22,4 % | −33,4 % | 255 |  |

## 4. Variantes aux coûts centraux, 10 M FCFA (estimations)

| Var. | Rdt an. | Vol. | Actif / TR | Actif / EW | IR | TE | Sharpe naïf / Lo / GLM | PSR(0) | DSR (N = 88) | DSR (N = 9) | DD abs. | DD rel. TR | CVaR / TR | Rotation /mois | Coûts /an | Lignes | Investi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** | −11,6 % | 11,8 % | −7,2 % | −7,5 % | −1,14 | 6,9 % | −0,99 / −0,85 / −0,83 | 0,00 | 0,00 | 0,00 | −54,9 % | −33,1 % | 1,02 | 6,2 % | 7,78 % | 17,7 | 81,9 % |
| **B** | −11,8 % | 12,1 % | −7,3 % | −7,7 % | −1,16 | 6,9 % | −0,97 / −0,87 / −0,84 | 0,00 | 0,00 | 0,00 | −55,3 % | −33,8 % | 1,04 | 6,0 % | 7,73 % | 17,8 | 82,5 % |
| **C** | −11,6 % | 11,7 % | −7,2 % | −7,5 % | −1,15 | 6,9 % | −1,00 / −0,85 / −0,84 | 0,00 | 0,00 | 0,00 | −54,9 % | −33,2 % | 0,99 | 6,0 % | 7,52 % | 17,8 | 82,1 % |
| **D** | −12,0 % | 11,7 % | −7,5 % | −7,9 % | −1,22 | 6,8 % | −1,03 / −0,88 / −0,87 | 0,00 | 0,00 | 0,00 | −55,8 % | −34,5 % | 1,03 | 6,1 % | 7,87 % | 17,8 | 81,9 % |
| **E** | −11,6 % | 11,8 % | −7,2 % | −7,5 % | −1,14 | 6,9 % | −0,99 / −0,85 / −0,83 | 0,00 | 0,00 | 0,00 | −54,9 % | −33,1 % | 1,02 | 6,2 % | 7,78 % | 17,7 | 81,9 % |
| **F** | −11,5 % | 11,7 % | −7,1 % | −7,5 % | −1,13 | 6,9 % | −0,98 / −0,85 / −0,82 | 0,00 | 0,00 | 0,00 | −54,6 % | −32,9 % | 1,02 | 6,2 % | 7,79 % | 17,7 | 81,6 % |
| **G** | −11,5 % | 11,7 % | −7,1 % | −7,5 % | −1,14 | 6,8 % | −0,99 / −0,85 / −0,83 | 0,00 | 0,00 | 0,00 | −54,6 % | −32,9 % | 1,00 | 6,1 % | 7,72 % | 17,7 | 81,6 % |
| **H** | −11,6 % | 11,8 % | −7,1 % | −7,5 % | −1,14 | 6,9 % | −0,99 / −0,85 / −0,83 | 0,00 | 0,00 | 0,00 | −54,8 % | −33,1 % | 1,02 | 6,2 % | 7,77 % | 17,7 | 81,8 % |
| **I** | −10,3 % | 11,2 % | −5,8 % | −6,2 % | −1,16 | 5,6 % | −0,91 / −0,80 / −0,75 | 0,00 | 0,00 | 0,00 | −51,5 % | −28,2 % | 0,96 | 4,4 % | 5,97 % | 20,9 | 84,3 % |
| **REF** (réf.) | −8,0 % | 10,6 % | −3,6 % | −4,0 % | −0,94 | 4,3 % | −0,74 / −0,71 / −0,67 | 0,01 | 0,01 | 0,01 | −43,7 % | −19,5 % | 0,82 | 2,8 % | 4,36 % | 17,6 | 82,0 % |

⚠ : écart entre Sharpe de Lo et Sharpe GLM supérieur à 25 % (prix périmés à examiner, §8.2). PSR, DSR, IR et Sharpe portent sur les rendements **actifs** nets contre le TR (sauf la colonne Sharpe, rendements absolus). Coûts /an : coûts payés rapportés à la NAV moyenne.

## 5. Statuts du §8.3 (règles exactes, estimations)

| Var. | Statut | Rejets déclenchés (R1-R5) | Critères candidat non vérifiés (C1-C7) | Actif central | Actif stress | IR sous-périodes | t NW de l'IC | HSR (BHY) |
|---|---|---|---|---|---|---|---|---|
| **A** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −7,2 % | −8,7 % | −1,14 / −1,27 | 1,68 | −0,00 |
| **B** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −7,3 % | −9,4 % | −1,17 / −1,27 | 2,68 | −0,00 |
| **C** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −7,2 % | −8,8 % | −1,15 / −1,26 | 1,55 | −0,00 |
| **D** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −7,5 % | −9,4 % | −1,27 / −1,27 | 1,50 | −0,00 |
| **E** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −7,2 % | −8,7 % | −1,14 / −1,27 | 1,68 | −0,00 |
| **F** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −7,1 % | −8,8 % | −1,13 / −1,26 | 1,68 | −0,00 |
| **G** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −7,1 % | −8,4 % | −1,13 / −1,28 | 1,68 | −0,00 |
| **H** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −7,1 % | −8,7 % | −1,14 / −1,26 | 1,68 | −0,00 |
| **I** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4, C6 | −5,8 % | −7,6 % | −1,21 / −1,10 | 1,57 | −0,00 |
| **REF** | **REJETÉ** (informatif) | R1, R2, R3 | C1, C2, C3, C6 | −3,6 % | −5,1 % | −0,32 / −1,44 | n.d. | −0,00 |

REJETÉ : l'une des conditions R1-R5 est vraie. CANDIDAT : C1-C7 toutes vraies (paper trading autorisé). INDÉTERMINÉ : ni l'un ni l'autre, ou données insuffisantes (aucun suivi réel autorisé). **PROMU est impossible sans suivi réel S2** (au moins 12 mois ; G7 sur les IC S1 puis S2 bout à bout, au moins 36 mois, D7). La référence REF (« indice discipliné », D8) est évaluée pour information, hors famille de la PBO.

## 6. Famille (N = 9), PBO et règle de promotion du §3.4

- Variantes de la famille exécutées : A, B, C, D, E, F, G, H, I (complète) ; semaines communes : 255.
- **PBO (CSCV, S = 10 blocs hebdomadaires, Sharpe de Lo (q = 4) des rendements actifs nets contre le TR)** : 0,845 ; pente de dégradation : −0,763.
- Registre : N = 88 essais (DSR « registre » et haircut BHY) ; G1 (registre complet) : vert ; variance des Sharpe hebdomadaires entre variantes : 0,000013.
- Règle : §3.4 : X remplace A seulement si X bat A en actif net ET DSR ≥ 0,95 avec N = 9 ET PBO ≤ 0,25. **Variante principale après la règle : A**.

| Variante | Actif net an. | Bat A | DSR (N = 9) | Remplace A |
|---|---|---|---|---|
| A | −7,2 % | — | 0,00 | — |
| B | −7,3 % | non | 0,00 | non |
| C | −7,2 % | non | 0,00 | non |
| D | −7,5 % | non | 0,00 | non |
| E | −7,2 % | non | 0,00 | non |
| F | −7,1 % | oui | 0,00 | non |
| G | −7,1 % | oui | 0,00 | non |
| H | −7,1 % | oui | 0,00 | non |
| I | −5,8 % | oui | 0,00 | non |

## 7. Intervalles du bootstrap stationnaire (95 %, rendements actifs contre le TR)

| Var. | IR [IC 95 %] | Actif moyen annualisé [IC 95 %] |
|---|---|---|
| A | −1,14 [−1,86 ; −0,40] | −7,9 % [−13,8 % ; −2,4 %] |
| B | −1,16 [−1,86 ; −0,42] | −8,0 % [−13,9 % ; −2,5 %] |
| C | −1,15 [−1,87 ; −0,37] | −7,9 % [−13,9 % ; −2,3 %] |
| D | −1,22 [−1,92 ; −0,46] | −8,3 % [−14,5 % ; −2,6 %] |
| E | −1,14 [−1,86 ; −0,40] | −7,9 % [−13,8 % ; −2,4 %] |
| F | −1,13 [−1,85 ; −0,38] | −7,8 % [−13,7 % ; −2,3 %] |
| G | −1,14 [−1,85 ; −0,41] | −7,8 % [−13,6 % ; −2,5 %] |
| H | −1,14 [−1,86 ; −0,40] | −7,8 % [−13,8 % ; −2,3 %] |
| I | −1,16 [−1,84 ; −0,42] | −6,4 % [−11,0 % ; −2,1 %] |
| REF | −0,94 [−1,78 ; −0,02] | −4,0 % [−8,6 % ; −0,1 %] |

## 8. Sous-périodes (coûts centraux, 10 M FCFA)

| Var. | Sous-période 1 | Sous-période 2 |
|---|---|---|
| A | [01/08/2017 ; 31/12/2019] : actif −8,1 %, IR −1,14, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −5,9 %, IR −1,27, 130 sem. |
| B | [01/08/2017 ; 31/12/2019] : actif −8,4 %, IR −1,17, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −5,9 %, IR −1,27, 130 sem. |
| C | [01/08/2017 ; 31/12/2019] : actif −8,1 %, IR −1,15, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −5,9 %, IR −1,26, 130 sem. |
| D | [01/08/2017 ; 31/12/2019] : actif −8,8 %, IR −1,27, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −5,9 %, IR −1,27, 130 sem. |
| E | [01/08/2017 ; 31/12/2019] : actif −8,1 %, IR −1,14, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −5,9 %, IR −1,27, 130 sem. |
| F | [01/08/2017 ; 31/12/2019] : actif −8,0 %, IR −1,13, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −5,9 %, IR −1,26, 130 sem. |
| G | [01/08/2017 ; 31/12/2019] : actif −7,9 %, IR −1,13, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −6,0 %, IR −1,28, 130 sem. |
| H | [01/08/2017 ; 31/12/2019] : actif −8,1 %, IR −1,14, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −5,9 %, IR −1,26, 130 sem. |
| I | [01/08/2017 ; 31/12/2019] : actif −5,7 %, IR −1,21, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −5,9 %, IR −1,10, 130 sem. |
| REF | [01/08/2017 ; 31/12/2019] : actif −0,9 %, IR −0,32, 125 sem. | [01/01/2020 ; 18/11/2022] : actif −6,6 %, IR −1,44, 130 sem. |

## 9. Analyses de sensibilité (le même essai sous d'autres hypothèses ; hors PBO et DSR)

| Run | Rdt an. | Actif / TR | Actif / EW | IR | DD rel. TR | Rotation /mois | Coûts /an | Lignes | Investi |
|---|---|---|---|---|---|---|---|---|---|
| A (coûts de stress, 10 M FCFA) | −13,2 % | −8,7 % | −9,1 % | −1,34 | −38,6 % | 5,9 % | 10,48 % | 17,9 | 83,4 % |
| B (coûts de stress, 10 M FCFA) | −13,9 % | −9,4 % | −9,8 % | −1,61 | −40,9 % | 5,6 % | 10,31 % | 17,9 | 85,7 % |
| C (coûts de stress, 10 M FCFA) | −13,3 % | −8,8 % | −9,2 % | −1,35 | −38,9 % | 5,8 % | 10,21 % | 17,9 | 83,0 % |
| D (coûts de stress, 10 M FCFA) | −13,8 % | −9,4 % | −9,8 % | −1,63 | −40,8 % | 5,5 % | 10,35 % | 17,9 | 85,9 % |
| E (coûts de stress, 10 M FCFA) | −13,2 % | −8,7 % | −9,1 % | −1,34 | −38,6 % | 5,9 % | 10,48 % | 17,9 | 83,4 % |
| F (coûts de stress, 10 M FCFA) | −13,2 % | −8,8 % | −9,2 % | −1,35 | −38,7 % | 6,0 % | 10,54 % | 17,9 | 82,8 % |
| G (coûts de stress, 10 M FCFA) | −12,9 % | −8,4 % | −8,8 % | −1,30 | −37,5 % | 5,8 % | 10,33 % | 17,9 | 83,2 % |
| H (coûts de stress, 10 M FCFA) | −13,1 % | −8,7 % | −9,1 % | −1,34 | −38,5 % | 5,9 % | 10,48 % | 17,9 | 83,3 % |
| I (coûts de stress, 10 M FCFA) | −12,0 % | −7,6 % | −7,9 % | −1,43 | −34,5 % | 4,3 % | 7,98 % | 20,6 | 85,2 % |
| REF (coûts de stress, 10 M FCFA) | −9,5 % | −5,1 % | −5,4 % | −1,22 | −24,8 % | 2,8 % | 5,88 % | 17,5 | 83,4 % |
| A (coûts optimistes, 10 M FCFA) | −8,6 % | −4,2 % | −4,6 % | −0,56 | −22,6 % | 8,7 % | 5,79 % | 18,0 | 77,0 % |
| A (coûts sévères, 10 M FCFA) | −16,5 % | −12,0 % | −12,4 % | −1,99 | −49,1 % | 4,9 % | 14,62 % | 18,5 | 86,1 % |
| I (coûts optimistes, 10 M FCFA) | −7,8 % | −3,4 % | −3,7 % | −0,67 | −19,3 % | 4,4 % | 3,29 % | 22,8 | 83,1 % |
| I (coûts sévères, 10 M FCFA) | −14,7 % | −10,3 % | −10,7 % | −1,85 | −43,6 % | 3,8 % | 11,45 % | 19,2 | 86,6 % |
| A (coûts centraux, 100 M FCFA) | −4,1 % | +0,4 % | +2,8 % | −0,03 | −28,5 % | 3,8 % | 3,04 % | 4,0 | 28,3 % |
| A (coûts centraux, 1 Md FCFA) | −0,3 % | +4,1 % | −1,0 % | 0,31 | −31,9 % | 0,6 % | 0,41 % | 1,0 | 7,2 % |
| I (coûts centraux, 100 M FCFA) | −4,4 % | +0,0 % | +2,5 % | −0,06 | −26,6 % | 3,0 % | 2,64 % | 4,1 | 37,0 % |
| I (coûts centraux, 1 Md FCFA) | −0,5 % | +3,9 % | −1,3 % | 0,32 | −30,6 % | 0,9 % | 0,64 % | 1,0 | 13,3 % |
| REF (coûts centraux, 100 M FCFA) | −4,7 % | −0,3 % | +2,2 % | −0,09 | −26,1 % | 2,2 % | 2,24 % | 3,4 | 44,9 % |
| REF (coûts centraux, 1 Md FCFA) | 0,2 % | +4,7 % | −0,5 % | 0,38 | −29,4 % | 0,9 % | 0,61 % | 1,0 | 14,0 % |

Aux capacités de 100 M et 1 Md FCFA, le panier EW est celui des éligibles de A **au même capital** (plancher de liquidité U5 dépendant du capital).

## 9 bis. Contrôles comptables et d'exécution (faits de simulation, aucune performance)

| Run | Contrôles verts | Cash min. | Exposition max. | Identité VL | Identité de flux | Ventes borne basse / achats borne haute | Coût par aller (médiane) | Coût par aller (moyenne pondérée) | Exécutions |
|---|---|---|---|---|---|---|---|---|---|
| A (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 99,22 % | 0.0e+00 | 2.3e-16 | 0 / 0 | 3,00 % | 2,89 % | 516 |
| A (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,15 % | 0.0e+00 | 3.0e-16 | 0 / 0 | 4,32 % | 4,11 % | 511 |
| B (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 99,30 % | 0.0e+00 | 3.1e-16 | 0 / 0 | 3,01 % | 2,91 % | 505 |
| B (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,14 % | 0.0e+00 | 2.4e-16 | 0 / 0 | 4,36 % | 4,11 % | 460 |
| C (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 99,11 % | 0.0e+00 | 2.3e-16 | 0 / 0 | 3,00 % | 2,88 % | 503 |
| C (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,06 % | 0.0e+00 | 2.3e-16 | 0 / 0 | 4,27 % | 4,10 % | 496 |
| D (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 99,22 % | 0.0e+00 | 3.0e-16 | 0 / 0 | 3,01 % | 2,92 % | 521 |
| D (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,14 % | 0.0e+00 | 2.4e-16 | 0 / 0 | 4,35 % | 4,16 % | 464 |
| E (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 99,22 % | 0.0e+00 | 2.3e-16 | 0 / 0 | 3,00 % | 2,89 % | 516 |
| E (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,15 % | 0.0e+00 | 3.0e-16 | 0 / 0 | 4,32 % | 4,11 % | 511 |
| F (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 98,41 % | 0.0e+00 | 2.3e-16 | 0 / 0 | 3,00 % | 2,89 % | 519 |
| F (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,14 % | 0.0e+00 | 2.6e-16 | 0 / 0 | 4,31 % | 4,11 % | 508 |
| G (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 99,02 % | 0.0e+00 | 2.3e-16 | 0 / 0 | 3,01 % | 2,90 % | 507 |
| G (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,14 % | 0.0e+00 | 2.2e-16 | 0 / 0 | 4,33 % | 4,12 % | 501 |
| H (coûts centraux, 10 M FCFA) | oui | 0 FCFA | 99,01 % | 0.0e+00 | 2.3e-16 | 0 / 0 | 3,00 % | 2,89 % | 515 |
| H (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,15 % | 0.0e+00 | 4.0e-16 | 0 / 0 | 4,32 % | 4,12 % | 509 |
| I (coûts centraux, 10 M FCFA) | oui | 427 FCFA | 97,63 % | 0.0e+00 | 5.5e-16 | 0 / 0 | 3,00 % | 2,90 % | 450 |
| I (coûts de stress, 10 M FCFA) | oui | 0 FCFA | 100,11 % | 0.0e+00 | 2.0e-16 | 0 / 0 | 4,33 % | 4,11 % | 428 |
| REF (coûts centraux, 10 M FCFA) | oui | 1 751 FCFA | 99,80 % | 0.0e+00 | 2.1e-16 | 0 / 0 | 3,00 % | 2,95 % | 233 |
| REF (coûts de stress, 10 M FCFA) | oui | 4 066 FCFA | 99,93 % | 0.0e+00 | 2.9e-16 | 0 / 0 | 4,34 % | 4,20 % | 229 |
| A (coûts optimistes, 10 M FCFA) | oui | 246 FCFA | 95,78 % | 0.0e+00 | 2.8e-16 | 0 / 0 | 2,37 % | 2,26 % | 763 |
| A (coûts sévères, 10 M FCFA) | oui | 0 FCFA | 100,50 % | 0.0e+00 | 2.2e-16 | 0 / 0 | 6,14 % | 5,73 % | 424 |
| I (coûts optimistes, 10 M FCFA) | oui | 421 FCFA | 96,94 % | 0.0e+00 | 2.7e-16 | 0 / 0 | 2,47 % | 2,37 % | 477 |
| I (coûts sévères, 10 M FCFA) | oui | 0 FCFA | 100,28 % | 0.0e+00 | 2.2e-16 | 0 / 0 | 6,05 % | 5,71 % | 324 |
| A (coûts centraux, 100 M FCFA) | oui | 25 252 840 FCFA | 69,74 % | 0.0e+00 | 2.5e-16 | 0 / 0 | 2,56 % | 2,51 % | 594 |
| A (coûts centraux, 1 Md FCFA) | oui | 866 287 694 FCFA | 12,40 % | 0.0e+00 | 1.5e-16 | 0 / 0 | 2,25 % | 2,27 % | 97 |
| I (coûts centraux, 100 M FCFA) | oui | 17 954 688 FCFA | 77,78 % | 0.0e+00 | 2.5e-16 | 0 / 0 | 2,62 % | 2,57 % | 491 |
| I (coûts centraux, 1 Md FCFA) | oui | 778 245 014 FCFA | 22,19 % | 0.0e+00 | 1.5e-16 | 0 / 0 | 2,20 % | 2,21 % | 110 |
| REF (coûts centraux, 100 M FCFA) | oui | 8 329 545 FCFA | 91,26 % | 0.0e+00 | 2.5e-16 | 0 / 0 | 2,68 % | 2,58 % | 299 |
| REF (coûts centraux, 1 Md FCFA) | oui | 665 713 249 FCFA | 33,79 % | 0.0e+00 | 1.4e-16 | 0 / 0 | 2,13 % | 2,16 % | 95 |

Cash réglé ≥ 0 à chaque séance (aucun levier) ; identités `VL = cash − frais dus + créances + Σ q·P` et `ΔVL = Σ q·ΔP + exécutions + dividendes − coûts` (écart maximal en fraction de la VL, tolérance 1e-06) ; aucune vente à la borne basse ni achat à la borne haute (§7.1.3). Une exposition légèrement supérieure à 100 % vient des frais de garde et de tenue de compte dus mais non encore payés (cash réglé nul en attendant un règlement J+3/J+2) : ce n'est pas un levier. Coût par aller : courtage, taxe, BRVM, DC/BR, demi-spread et impact rapportés au montant exécuté (§7.2 : environ 1,75 % pour un titre médian aux coûts centraux).

## 10. Dividendes (D6) et fenêtre complète (information)

| Var. | Dividendes crédités | Ligne (d) du BOC | Écart | Rdt an. (complet) | Actif / TR (complet) | IR (complet) | DD rel. (complet) |
|---|---|---|---|---|---|---|---|
| A | 1 903 598 FCFA | 1 904 444 FCFA | -846 FCFA | −10,4 % | −5,0 % | −0,77 | −33,5 % |
| B | 1 896 794 FCFA | 1 897 631 FCFA | -837 FCFA | −10,6 % | −5,2 % | −0,79 | −34,2 % |
| C | 1 900 820 FCFA | 1 901 666 FCFA | -846 FCFA | −10,4 % | −5,0 % | −0,77 | −33,6 % |
| D | 1 857 189 FCFA | 1 858 017 FCFA | -828 FCFA | −10,8 % | −5,4 % | −0,83 | −34,9 % |
| E | 1 903 598 FCFA | 1 904 444 FCFA | -846 FCFA | −10,4 % | −5,0 % | −0,77 | −33,5 % |
| F | 1 899 996 FCFA | 1 900 851 FCFA | -855 FCFA | −10,4 % | −4,9 % | −0,76 | −33,3 % |
| G | 1 879 998 FCFA | 1 880 853 FCFA | -855 FCFA | −10,4 % | −5,0 % | −0,77 | −33,4 % |
| H | 1 902 084 FCFA | 1 902 930 FCFA | -846 FCFA | −10,4 % | −5,0 % | −0,77 | −33,5 % |
| I | 2 090 486 FCFA | 2 091 152 FCFA | -666 FCFA | −9,2 % | −3,8 % | −0,70 | −28,7 % |
| REF | 2 190 919 FCFA | 2 191 972 FCFA | -1 053 FCFA | −7,2 % | −1,8 % | −0,42 | −19,5 % |

Flux de trésorerie : montant **corrigé** (meilleure estimation du versement réel) ; signaux (DY, S1, S2) : montant connu en t, ligne (d) du BOC (D6). La fenêtre complète inclut les mois de liquidités de démarrage : elle crée un rendement actif mécanique et n'entre dans **aucun** critère (D2).

## 11. Faits, estimations, hypothèses et limites

**Faits** : cours, volumes, dividendes et numéros de BOC lus dans les bulletins officiels ; règles et seuils du §8.3 et de l'additif v1.1, figés avant l'exécution ; plan des runs et paramètres consignés dans `lock.json` (S1) et dans le registre `reports/trials.parquet`.

**Estimations** : toutes les métriques (rendements, IR, Sharpe, PSR, DSR, PBO, CVaR, intervalles du bootstrap) sont des estimations sur environ cinq ans de données hebdomadaires : leur incertitude est large (voir les intervalles de la section 7).

**Hypothèses** : barèmes de coûts du §7.2 (courtage, taxe [NON VÉRIFIÉ], demi-spread mesuré, impact κ·√π sans étude publiée) ; exécution au VWAP de t+1 avec participation ≤ 10 % ; Composite TR reconstruit avant le premier niveau officiel ; secteurs de 2025 appliqués à tout l'historique ; chronologie des événements pays [NON VÉRIFIÉ] en partie (D10) ; étalon « fonds actions » non disponible.

**Limites** : 129 séances sans BOC (dont 96 en 2021) ; rendements multi-séances exclus des statistiques ; annualisation conventionnelle (52 semaines) ; aucun suivi réel (S2) : le statut PROMU est impossible.

## 12. Prédiction du §8.3 (rappel, écrite avant l'exécution)

Prédiction écrite d'avance (§8.3, maintenue par l'additif v1.1) : avec un IR réel de 0,3, le z attendu sur S1 (5,9 ans) vaut 0,3 × √5,9 ≈ 0,73, soit un PSR ≈ 0,77 : G2 échouera probablement. Le statut le plus probable, même pour une bonne stratégie, est « candidat » ; le rejet de A est un résultat plausible (l'essai de fumée de S0 est défavorable). Un IR > 1 serait d'abord traité comme une ERREUR (anticipation, prix périmés, coûts oubliés).

## Fichiers

`metrics.json` (toutes les mesures), `weekly_returns.parquet` (rendements hebdomadaires nets des stratégies et des étalons sur la fenêtre d'évaluation), `nav.parquet` (valeurs liquidatives et niveaux, rebasés à t0), `trades.parquet` (exécutions de tous les runs), `lock.json` (verrou du test unique).

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
