# BRVM Alpha — Validation S1 — test unique pré-enregistré (additif v1.1)

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

> Test **unique** sur l'échantillon vierge S1 (2017-01-02 → 2022-11-16), paramètres figés avant l'exécution (§3.4, §8.3, additif v1.1 §8.4). Toute relance exige un bogue démontré (`--rerun-reason`) et crée de nouveaux essais.

## 1. Contexte d'exécution (faits)

| Élément | Valeur |
|---|---|
| Commit | `1819997bc8f01ef6977a7db6dc3ddac0c2875401` (branche claude/brvm-stock-analysis-platform-4myn3g) |
| Arbre `brvm_alpha/` et `configs/` identique à HEAD, sans fichier non suivi | oui |
| Fichiers non suivis (refusés sur S1, listés) | aucun |
| Empreinte de configuration | `f1582ed8e9fa1c85` (identique à l'empreinte de l'état figé `a2bfeb4` ; référence de pré-enregistrement : commit `751d1be`, YAML 1.0, empreinte `dcdf1fb7db530c44` ; l'empreinte de l'état figé n'est pas une valeur pré-enregistrée indépendante) |
| Version du YAML | 1.1 |
| Horodatage (UTC) | 2026-11-22T12:13:28.193940+00:00 |
| Durée totale / des runs | 755,1 s / 702,5 s (3 processus) |
| Panel | /home/user/documentation/brvm-alpha/data/panel |
| Plan des runs | 30 runs |
| Événements pays chargés (D10) | 19 |
| Mode de décision | evenementiel (effectif : evenementiel) |
| Bootstrap stationnaire | n_boot = 5000 (explicite), blocs moyens de 8 semaines |

**Relance motivée (D12)** : Bogues démontrés par l'audit du 22/11/2026 (comptabilité des statistiques) : (1) semaines multi-séances après un trou de BOC retirées du chaînage du rendement, de l'actif et des drawdowns, contrairement au §3.1.3 (« gardé pour chaîner le TR ») ; (2) garde-fou de couverture tautologique (semaines attendues = semaines du TR calculées avec les mêmes retraits). Corrections de publication associées : coûts annualisés en années calendaires, DSR sous deux conventions de variance, sensibilité de la PBO, un IC par mois, contrôle d'empreinte sans autoréférence. Aucun paramètre de stratégie modifié.. Anciens résultats : `/home/user/documentation/brvm-alpha/reports/validation_S1/precedent_20261122T121328Z`.

## 2. Fenêtre d'évaluation (additif v1.1, D2)

- **t0 = 01/08/2017** : première séance où la variante A (coûts centraux, 10 M FCFA) détient des titres. Toutes les variantes et tous les étalons sont évalués sur la **même** fenêtre [01/08/2017 ; 16/11/2022], rebasés à t0 (base 100 à la clôture de la veille de t0 : le rendement de t0, qui porte les frais d'achat initiaux, est compté).
- Sous-périodes : [01/08/2017 ; 31/12/2019] ; [01/01/2020 ; 18/11/2022].
- Fréquence : hebdomadaire (W-FRI), nette de tous les coûts ; annualisation à 52 semaines.
- Semaines retirées de toutes les mesures : fenêtre(s) du §8.1 06/05/2021 → 25/06/2021 (07/05/2021, 25/06/2021).
- Semaines multi-séances (observation de plus de 6 séances après un trou de BOC) : 14/12/2018, 09/07/2021, 23/07/2021, 10/09/2021, 24/09/2021, 22/10/2021, 05/11/2021. Elles sont **gardées** pour les critères chaînés (rendement annualisé, actif R1/R2/C1/C3, drawdowns R4/R5/C4) et **retirées** des seules statistiques de dispersion (volatilité, IR, TE, Sharpe, PSR, DSR, PBO, CVaR, bootstrap) : §3.1.3, « exclu des estimations de volatilité […] mais gardé pour chaîner le TR ».
- La fenêtre complète (depuis la première séance simulée, liquidités de démarrage comprises) est publiée en section 10 **pour information seulement**.

## 3. Étalons (sur [t0 ; fin], sans coûts)

| Code | Étalon | Disponible | Rendement an. | Vol. an. | Drawdown | Semaines | Note |
|---|---|---|---|---|---|---|---|
| TR | BRVM Composite Total Return (officiel raccordé, reconstruit avant) | oui | −0,8 % | 12,5 % | −40,8 % | 262 | source : store.composite_tr_reconstructed(official=True) |
| EW | panier équipondéré TR des éligibles de A (mensuel) | oui | 1,4 % | 15,0 % | −42,9 % | 262 | source : store.equal_weight_tr(masque PIT de A, rebalance='monthly') |
| PRIX | BRVM Composite (indice prix) | oui | −6,4 % | 12,8 % | −51,1 % | 262 | source : indices.parquet « BRVM COMPOSITE » |
| BRVM10 | BRVM 10 (jusqu'au 30/12/2022) | oui | −6,8 % | 15,6 % | −49,0 % | 262 | publié jusqu'au 30/12/2022 ; source : indices.parquet « BRVM 10 » |
| BRVM30 | BRVM 30 (à partir du 02/01/2023) | **non disponible** | n.d. | n.d. | n.d. |  | publié à partir du 02/01/2023 ; source : indices.parquet « BRVM 30 » |
| PRESTIGE | BRVM Prestige (à partir du 02/01/2023) | **non disponible** | n.d. | n.d. | n.d. |  | publié à partir du 02/01/2023 ; source : indices.parquet « BRVM PRESTIGE » |
| FONDS | médiane des fonds actions (catégorie A du BOC) | **non disponible** | n.d. | n.d. | n.d. |  | non disponible : les valeurs liquidatives des OPCVM actions (catégorie A du BOC) ne sont pas extraites dans le panel ; étalon non calculé (aucune série de substitution) ; source : aucune |
| EW_100M | panier équipondéré TR des éligibles de A à 100M FCFA | oui | −3,6 % | 17,9 % | −42,6 % | 262 |  |
| EW_1Md | panier équipondéré TR des éligibles de A à 1Md FCFA | oui | 0,8 % | 22,4 % | −35,1 % | 262 |  |

## 4. Variantes aux coûts centraux, 10 M FCFA (estimations)

| Var. | Rdt an. | Vol. | Actif / TR | Actif / EW | IR | TE | Sharpe naïf / Lo / GLM | PSR(0) | DSR (N = 98) | DSR (N = 9) | DD abs. | DD rel. TR | CVaR / TR | Rotation /mois | Coûts /an | Lignes | Investi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** | −10,1 % | 11,8 % | −9,3 % | −11,5 % | −1,14 | 6,9 % | −0,99 / −0,85 / −0,83 | 0,00 | 0,00 | 0,00 | −54,0 % | −40,2 % | 1,02 | 6,2 % | 7,04 % | 17,7 | 81,9 % |
| **B** | −10,3 % | 12,1 % | −9,5 % | −11,7 % | −1,16 | 6,9 % | −0,97 / −0,87 / −0,84 | 0,00 | 0,00 | 0,00 | −54,4 % | −40,8 % | 1,04 | 6,0 % | 6,99 % | 17,8 | 82,5 % |
| **C** | −10,1 % | 11,7 % | −9,3 % | −11,5 % | −1,15 | 6,9 % | −1,00 / −0,85 / −0,84 | 0,00 | 0,00 | 0,00 | −53,9 % | −40,2 % | 0,99 | 6,0 % | 6,80 % | 17,8 | 82,1 % |
| **D** | −10,5 % | 11,7 % | −9,7 % | −12,0 % | −1,22 | 6,8 % | −1,03 / −0,88 / −0,87 | 0,00 | 0,00 | 0,00 | −55,1 % | −41,7 % | 1,03 | 6,1 % | 7,12 % | 17,8 | 81,9 % |
| **E** | −10,1 % | 11,8 % | −9,3 % | −11,5 % | −1,14 | 6,9 % | −0,99 / −0,85 / −0,83 | 0,00 | 0,00 | 0,00 | −54,0 % | −40,2 % | 1,02 | 6,2 % | 7,04 % | 17,7 | 81,9 % |
| **F** | −10,0 % | 11,7 % | −9,2 % | −11,5 % | −1,13 | 6,9 % | −0,98 / −0,85 / −0,82 | 0,00 | 0,00 | 0,00 | −53,7 % | −40,0 % | 1,02 | 6,2 % | 7,05 % | 17,7 | 81,6 % |
| **G** | −10,1 % | 11,7 % | −9,2 % | −11,5 % | −1,14 | 6,8 % | −0,99 / −0,85 / −0,83 | 0,00 | 0,00 | 0,00 | −53,8 % | −40,1 % | 1,00 | 6,1 % | 6,98 % | 17,7 | 81,6 % |
| **H** | −10,1 % | 11,8 % | −9,3 % | −11,5 % | −1,14 | 6,9 % | −0,99 / −0,85 / −0,83 | 0,00 | 0,00 | 0,00 | −53,9 % | −40,2 % | 1,02 | 6,2 % | 7,03 % | 17,7 | 81,8 % |
| **I** | −8,4 % | 11,2 % | −7,6 % | −9,9 % | −1,16 | 5,6 % | −0,91 / −0,80 / −0,75 | 0,00 | 0,00 | 0,00 | −49,7 % | −34,6 % | 0,96 | 4,4 % | 5,40 % | 20,9 | 84,3 % |
| **REF** (réf.) | −6,4 % | 10,6 % | −5,6 % | −7,9 % | −0,94 | 4,3 % | −0,74 / −0,71 / −0,67 | 0,01 | 0,01 | 0,01 | −42,2 % | −27,1 % | 0,82 | 2,8 % | 3,94 % | 17,6 | 82,0 % |

⚠ : écart entre Sharpe de Lo et Sharpe GLM supérieur à 25 % (prix périmés à examiner, §8.2). PSR, DSR, IR et Sharpe portent sur les rendements **actifs** nets contre le TR (sauf la colonne Sharpe, rendements absolus). Coûts /an : coûts payés rapportés à la NAV moyenne, annualisés par les années calendaires de la fenêtre.

**DSR sous deux conventions de variance** (N = 98 ; §8.5) : variance des Sharpe hebdomadaires de la famille (0,000013, utilisée pour G3) ou de tous les essais exécutés du registre (0,0465, prudente).

| Var. | DSR (variance famille) | DSR (variance registre) | DSR (N = 9) |
|---|---|---|---|
| A | 0,0016 | 0,0000 | 0,0020 |
| B | 0,0014 | 0,0000 | 0,0018 |
| C | 0,0015 | 0,0000 | 0,0018 |
| D | 0,0006 | 0,0000 | 0,0008 |
| E | 0,0016 | 0,0000 | 0,0020 |
| F | 0,0018 | 0,0000 | 0,0022 |
| G | 0,0016 | 0,0000 | 0,0020 |
| H | 0,0016 | 0,0000 | 0,0020 |
| I | 0,0018 | 0,0000 | 0,0022 |
| REF | 0,0084 | 0,0000 | 0,0099 |

## 5. Statuts du §8.3 (règles exactes, estimations)

| Var. | Statut | Rejets déclenchés (R1-R5) | Critères candidat non vérifiés (C1-C7) | Actif central | Actif stress | IR sous-périodes | t NW de l'IC | HSR (BHY) |
|---|---|---|---|---|---|---|---|---|
| **A** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −9,3 % | −10,8 % | −1,14 / −1,27 | 1,72 | −0,00 |
| **B** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −9,5 % | −11,2 % | −1,17 / −1,27 | 2,58 | −0,00 |
| **C** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −9,3 % | −10,9 % | −1,15 / −1,26 | 1,56 | −0,00 |
| **D** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −9,7 % | −11,2 % | −1,27 / −1,27 | 1,55 | −0,00 |
| **E** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −9,3 % | −10,8 % | −1,14 / −1,27 | 1,72 | −0,00 |
| **F** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −9,2 % | −10,9 % | −1,13 / −1,26 | 1,72 | −0,00 |
| **G** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −9,2 % | −10,5 % | −1,13 / −1,28 | 1,72 | −0,00 |
| **H** | **REJETÉ** | R1, R2, R3, R4, R5 | C1, C2, C3, C4, C6 | −9,3 % | −10,8 % | −1,14 / −1,26 | 1,72 | −0,00 |
| **I** | **REJETÉ** | R1, R2, R3, R4 | C1, C2, C3, C4, C6 | −7,6 % | −9,3 % | −1,21 / −1,10 | 1,60 | −0,00 |
| **REF** | **REJETÉ** (informatif) | R1, R2, R3, R4 | C1, C2, C3, C4, C6 | −5,6 % | −7,1 % | −0,32 / −1,44 | n.d. | −0,00 |

Couverture de la période attendue (calendrier W-FRI de [t0 ; fin] moins la fenêtre du §8.1, 269 semaines ; seuil 95 %, §8.5) : **97,4 %** sur les séries chaînées (critère) ; 94,8 % sans les semaines multi-séances (lecture antérieure à la correction du 22/11/2026, sous le seuil : elle aurait rendu le statut INDÉTERMINÉ).

**Non testée(s) sur S1** : E non testée sur S1 : rendements identiques à ceux de A (clone exact). Pour E, aucun avis de dividende n'est daté à l'avance dans les données (première vue environ un jour avant la date ex) : la poche S1 ne s'ouvre jamais. Statut publié pour information.

REJETÉ : l'une des conditions R1-R5 est vraie. CANDIDAT : C1-C7 toutes vraies (paper trading autorisé). INDÉTERMINÉ : ni l'un ni l'autre, ou données insuffisantes (aucun suivi réel autorisé). **PROMU est impossible sans suivi réel S2** (au moins 12 mois ; G7 sur les IC S1 puis S2 bout à bout, au moins 36 mois, D7). La référence REF (« indice discipliné », D8) est évaluée pour information, hors famille de la PBO.

## 6. Famille (N = 9), PBO et règle de promotion du §3.4

- Variantes de la famille exécutées : A, B, C, D, E, F, G, H, I (complète) ; semaines communes : 262.
- **PBO (CSCV, S = 10 blocs hebdomadaires, Sharpe de Lo (q = 4) des rendements actifs nets contre le TR (semaines multi-séances exclues))** : 0,845 ; pente de dégradation : −0,763.
- **Sensibilité de la PBO** (publiée ; C6 reste évalué avec la convention figée) : convention figée (blocs égaux, semaines anciennes en surnombre ignorées) 0,845 ; toutes les semaines (`array_split`) 0,710 ; λ = 0 compté pour ½ 0,817 ; famille sans clone (A, B, C, D, F, G, H, I) 0,802 ; famille simulée de quasi-clones de A 0,198 ; PBO nulle de référence pour N = 9 : 0,556 (0,5 si λ = 0 compte pour ½).
- Clones exacts dans la famille : E = A (variantes identiques : la PBO perd son pouvoir discriminant).
- Registre : N = 98 essais (DSR « registre » et haircut BHY) ; G1 (registre complet) : vert ; variance des Sharpe hebdomadaires entre variantes : 0,000013.
- Règle : §3.4 : X remplace A seulement si X bat A en actif net ET DSR ≥ 0,95 avec N = 9 ET PBO ≤ 0,25. **Variante principale après la règle : A**.

| Variante | Actif net an. | Bat A | DSR (N = 9) | Remplace A |
|---|---|---|---|---|
| A | −9,3 % | — | 0,00 | — |
| B | −9,5 % | non | 0,00 | non |
| C | −9,3 % | oui | 0,00 | non |
| D | −9,7 % | non | 0,00 | non |
| E | −9,3 % | non | 0,00 | non |
| F | −9,2 % | oui | 0,00 | non |
| G | −9,2 % | oui | 0,00 | non |
| H | −9,3 % | oui | 0,00 | non |
| I | −7,6 % | oui | 0,00 | non |

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
| A | [01/08/2017 ; 31/12/2019] : actif −8,6 %, IR −1,14, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,0 %, IR −1,27, 136 sem. |
| B | [01/08/2017 ; 31/12/2019] : actif −8,9 %, IR −1,17, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,0 %, IR −1,27, 136 sem. |
| C | [01/08/2017 ; 31/12/2019] : actif −8,5 %, IR −1,15, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,0 %, IR −1,26, 136 sem. |
| D | [01/08/2017 ; 31/12/2019] : actif −9,4 %, IR −1,27, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,0 %, IR −1,27, 136 sem. |
| E | [01/08/2017 ; 31/12/2019] : actif −8,6 %, IR −1,14, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,0 %, IR −1,27, 136 sem. |
| F | [01/08/2017 ; 31/12/2019] : actif −8,4 %, IR −1,13, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,0 %, IR −1,26, 136 sem. |
| G | [01/08/2017 ; 31/12/2019] : actif −8,4 %, IR −1,13, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,1 %, IR −1,28, 136 sem. |
| H | [01/08/2017 ; 31/12/2019] : actif −8,5 %, IR −1,14, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,0 %, IR −1,26, 136 sem. |
| I | [01/08/2017 ; 31/12/2019] : actif −5,6 %, IR −1,21, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −9,8 %, IR −1,10, 136 sem. |
| REF | [01/08/2017 ; 31/12/2019] : actif −1,1 %, IR −0,32, 126 sem. | [01/01/2020 ; 18/11/2022] : actif −10,6 %, IR −1,44, 136 sem. |

## 9. Analyses de sensibilité (le même essai sous d'autres hypothèses ; hors PBO et DSR)

| Run | Rdt an. | Actif / TR | Actif / EW | IR | DD rel. TR | Rotation /mois | Coûts /an | Lignes | Investi |
|---|---|---|---|---|---|---|---|---|---|
| A (coûts de stress, 10 M FCFA) | −11,6 % | −10,8 % | −13,1 % | −1,34 | −45,0 % | 5,9 % | 9,48 % | 17,9 | 83,4 % |
| B (coûts de stress, 10 M FCFA) | −12,0 % | −11,2 % | −13,5 % | −1,61 | −46,3 % | 5,6 % | 9,32 % | 17,9 | 85,7 % |
| C (coûts de stress, 10 M FCFA) | −11,7 % | −10,9 % | −13,2 % | −1,35 | −45,3 % | 5,8 % | 9,23 % | 17,9 | 83,0 % |
| D (coûts de stress, 10 M FCFA) | −12,0 % | −11,2 % | −13,5 % | −1,63 | −46,2 % | 5,5 % | 9,36 % | 17,9 | 85,9 % |
| E (coûts de stress, 10 M FCFA) | −11,6 % | −10,8 % | −13,1 % | −1,34 | −45,0 % | 5,9 % | 9,48 % | 17,9 | 83,4 % |
| F (coûts de stress, 10 M FCFA) | −11,7 % | −10,9 % | −13,1 % | −1,35 | −45,2 % | 6,0 % | 9,53 % | 17,9 | 82,8 % |
| G (coûts de stress, 10 M FCFA) | −11,3 % | −10,5 % | −12,8 % | −1,30 | −44,1 % | 5,8 % | 9,34 % | 17,9 | 83,2 % |
| H (coûts de stress, 10 M FCFA) | −11,6 % | −10,8 % | −13,1 % | −1,34 | −45,0 % | 5,9 % | 9,48 % | 17,9 | 83,3 % |
| I (coûts de stress, 10 M FCFA) | −10,1 % | −9,3 % | −11,6 % | −1,43 | −40,2 % | 4,3 % | 7,22 % | 20,6 | 85,2 % |
| REF (coûts de stress, 10 M FCFA) | −7,9 % | −7,1 % | −9,3 % | −1,22 | −32,4 % | 2,8 % | 5,32 % | 17,5 | 83,4 % |
| A (coûts optimistes, 10 M FCFA) | −6,8 % | −6,0 % | −8,3 % | −0,56 | −29,6 % | 8,7 % | 5,24 % | 18,0 | 77,0 % |
| A (coûts sévères, 10 M FCFA) | −14,8 % | −14,0 % | −16,2 % | −1,99 | −54,1 % | 4,9 % | 13,22 % | 18,5 | 86,1 % |
| I (coûts optimistes, 10 M FCFA) | −5,9 % | −5,1 % | −7,3 % | −0,67 | −26,2 % | 4,4 % | 2,98 % | 22,8 | 83,1 % |
| I (coûts sévères, 10 M FCFA) | −12,9 % | −12,1 % | −14,4 % | −1,85 | −48,9 % | 3,8 % | 10,36 % | 19,2 | 86,6 % |
| A (coûts centraux, 100 M FCFA) | −3,5 % | −2,7 % | +0,1 % | −0,03 | −37,0 % | 3,8 % | 2,75 % | 4,0 | 28,3 % |
| A (coûts centraux, 1 Md FCFA) | −0,3 % | +0,5 % | −1,1 % | 0,31 | −41,3 % | 0,6 % | 0,37 % | 1,0 | 7,2 % |
| I (coûts centraux, 100 M FCFA) | −4,0 % | −3,2 % | −0,4 % | −0,06 | −35,5 % | 3,0 % | 2,38 % | 4,1 | 37,0 % |
| I (coûts centraux, 1 Md FCFA) | −0,6 % | +0,2 % | −1,4 % | 0,32 | −40,2 % | 0,9 % | 0,58 % | 1,0 | 13,3 % |
| REF (coûts centraux, 100 M FCFA) | −4,4 % | −3,5 % | −0,7 % | −0,09 | −35,2 % | 2,2 % | 2,03 % | 3,4 | 44,9 % |
| REF (coûts centraux, 1 Md FCFA) | 0,2 % | +1,0 % | −0,7 % | 0,38 | −39,2 % | 0,9 % | 0,56 % | 1,0 | 14,0 % |

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

Décomposition **pondérée** du coût par aller sur [t0 ; fin] (somme des composantes = coût moyen pondéré ; le demi-spread médian mesuré n'entre pas dans cette somme) :

| Run | Frais (courtage, taxe, BRVM, DC/BR) | Demi-spread | Impact | Total |
|---|---|---|---|---|
| A (coûts centraux, 10 M FCFA) | 1,244 % | 1,325 % | 0,323 % | 2,892 % |
| A (coûts de stress, 10 M FCFA) | 1,480 % | 1,991 % | 0,643 % | 4,114 % |
| B (coûts centraux, 10 M FCFA) | 1,244 % | 1,336 % | 0,326 % | 2,906 % |
| B (coûts de stress, 10 M FCFA) | 1,480 % | 1,990 % | 0,638 % | 4,108 % |
| C (coûts centraux, 10 M FCFA) | 1,244 % | 1,314 % | 0,318 % | 2,876 % |
| C (coûts de stress, 10 M FCFA) | 1,480 % | 1,985 % | 0,633 % | 4,098 % |
| D (coûts centraux, 10 M FCFA) | 1,244 % | 1,351 % | 0,328 % | 2,922 % |
| D (coûts de stress, 10 M FCFA) | 1,480 % | 2,030 % | 0,648 % | 4,158 % |
| E (coûts centraux, 10 M FCFA) | 1,244 % | 1,325 % | 0,323 % | 2,892 % |
| E (coûts de stress, 10 M FCFA) | 1,480 % | 1,991 % | 0,643 % | 4,114 % |
| F (coûts centraux, 10 M FCFA) | 1,244 % | 1,322 % | 0,323 % | 2,890 % |
| F (coûts de stress, 10 M FCFA) | 1,480 % | 1,992 % | 0,642 % | 4,114 % |
| G (coûts centraux, 10 M FCFA) | 1,244 % | 1,329 % | 0,326 % | 2,898 % |
| G (coûts de stress, 10 M FCFA) | 1,480 % | 1,994 % | 0,647 % | 4,121 % |
| H (coûts centraux, 10 M FCFA) | 1,244 % | 1,326 % | 0,323 % | 2,893 % |
| H (coûts de stress, 10 M FCFA) | 1,480 % | 1,994 % | 0,642 % | 4,116 % |
| I (coûts centraux, 10 M FCFA) | 1,244 % | 1,338 % | 0,317 % | 2,900 % |
| I (coûts de stress, 10 M FCFA) | 1,480 % | 1,998 % | 0,633 % | 4,111 % |
| REF (coûts centraux, 10 M FCFA) | 1,244 % | 1,395 % | 0,313 % | 2,953 % |
| REF (coûts de stress, 10 M FCFA) | 1,480 % | 2,103 % | 0,615 % | 4,198 % |
| A (coûts optimistes, 10 M FCFA) | 0,850 % | 1,198 % | 0,210 % | 2,258 % |
| A (coûts sévères, 10 M FCFA) | 2,070 % | 2,682 % | 0,976 % | 5,728 % |
| I (coûts optimistes, 10 M FCFA) | 0,850 % | 1,324 % | 0,198 % | 2,372 % |
| I (coûts sévères, 10 M FCFA) | 2,070 % | 2,701 % | 0,941 % | 5,712 % |
| A (coûts centraux, 100 M FCFA) | 1,244 % | 0,824 % | 0,447 % | 2,515 % |
| A (coûts centraux, 1 Md FCFA) | 1,244 % | 0,563 % | 0,465 % | 2,271 % |
| I (coûts centraux, 100 M FCFA) | 1,244 % | 0,891 % | 0,434 % | 2,569 % |
| I (coûts centraux, 1 Md FCFA) | 1,244 % | 0,478 % | 0,485 % | 2,207 % |
| REF (coûts centraux, 100 M FCFA) | 1,244 % | 0,896 % | 0,444 % | 2,584 % |
| REF (coûts centraux, 1 Md FCFA) | 1,244 % | 0,432 % | 0,488 % | 2,164 % |

Cash réglé ≥ 0 à chaque séance (aucun levier) ; identités `VL = cash − frais dus + créances + Σ q·P` et `ΔVL = Σ q·ΔP + exécutions + dividendes − coûts` (écart maximal en fraction de la VL, tolérance 1e-06) ; aucune vente à la borne basse ni achat à la borne haute (§7.1.3). Une exposition légèrement supérieure à 100 % vient des frais de garde et de tenue de compte dus mais non encore payés (cash réglé nul en attendant un règlement J+3/J+2) : ce n'est pas un levier. Coût par aller : courtage, taxe, BRVM, DC/BR, demi-spread et impact rapportés au montant exécuté (§7.2 : environ 1,75 % pour un titre médian aux coûts centraux).

## 10. Dividendes (D6) et fenêtre complète (information)

| Var. | Dividendes crédités | Ligne (d) du BOC | Écart | Rdt an. (complet) | Actif / TR (complet) | IR (complet) | DD rel. (complet) |
|---|---|---|---|---|---|---|---|
| A | 1 903 598 FCFA | 1 904 444 FCFA | -846 FCFA | −9,1 % | −6,9 % | −0,77 | −40,6 % |
| B | 1 896 794 FCFA | 1 897 631 FCFA | -837 FCFA | −9,3 % | −7,1 % | −0,79 | −41,2 % |
| C | 1 900 820 FCFA | 1 901 666 FCFA | -846 FCFA | −9,1 % | −6,9 % | −0,77 | −40,6 % |
| D | 1 857 189 FCFA | 1 858 017 FCFA | -828 FCFA | −9,5 % | −7,3 % | −0,83 | −42,1 % |
| E | 1 903 598 FCFA | 1 904 444 FCFA | -846 FCFA | −9,1 % | −6,9 % | −0,77 | −40,6 % |
| F | 1 899 996 FCFA | 1 900 851 FCFA | -855 FCFA | −9,0 % | −6,8 % | −0,76 | −40,4 % |
| G | 1 879 998 FCFA | 1 880 853 FCFA | -855 FCFA | −9,1 % | −6,9 % | −0,77 | −40,5 % |
| H | 1 902 084 FCFA | 1 902 930 FCFA | -846 FCFA | −9,1 % | −6,9 % | −0,77 | −40,6 % |
| I | 2 090 486 FCFA | 2 091 152 FCFA | -666 FCFA | −7,6 % | −5,4 % | −0,70 | −35,0 % |
| REF | 2 190 919 FCFA | 2 191 972 FCFA | -1 053 FCFA | −5,8 % | −3,6 % | −0,42 | −27,4 % |

Flux de trésorerie : montant **corrigé** (meilleure estimation du versement réel) ; signaux (DY, S1, S2) : montant connu en t, ligne (d) du BOC (D6). La fenêtre complète inclut les mois de liquidités de démarrage : elle crée un rendement actif mécanique et n'entre dans **aucun** critère (D2).

## 11. Faits, estimations, hypothèses et limites

**Faits** : cours, volumes, dividendes et numéros de BOC lus dans les bulletins officiels ; règles et seuils du §8.3 et de l'additif v1.1, figés avant l'exécution ; plan des runs et paramètres consignés dans `lock.json` (S1) et dans le registre `reports/trials.parquet`.

**Estimations** : toutes les métriques (rendements, IR, Sharpe, PSR, DSR, PBO, CVaR, intervalles du bootstrap) sont des estimations sur environ cinq ans de données hebdomadaires : leur incertitude est large (voir les intervalles de la section 7).

**Hypothèses** : barèmes de coûts du §7.2 (courtage, taxe [NON VÉRIFIÉ], demi-spread mesuré, impact κ·√π sans étude publiée) ; exécution au VWAP de t+1 avec participation ≤ 10 % ; Composite TR reconstruit avant le premier niveau officiel ; secteurs de 2025 appliqués à tout l'historique ; chronologie des événements pays [NON VÉRIFIÉ] en partie (D10) ; étalon « fonds actions » non disponible.

**Limites** : 129 séances sans BOC (dont 96 en 2021) ; semaines multi-séances gardées pour le chaînage et exclues des seules statistiques de dispersion ; annualisation conventionnelle (52 semaines observées) ; aucun suivi réel (S2) : le statut PROMU est impossible.

## 12. Prédiction du §8.3 (rappel, écrite avant l'exécution)

Prédiction écrite d'avance (§8.3, maintenue par l'additif v1.1) : avec un IR réel de 0,3, le z attendu sur S1 (5,9 ans) vaut 0,3 × √5,9 ≈ 0,73, soit un PSR ≈ 0,77 : G2 échouera probablement. Le statut le plus probable, même pour une bonne stratégie, est « candidat » ; le rejet de A est un résultat plausible (l'essai de fumée de S0 est défavorable). Un IR > 1 serait d'abord traité comme une ERREUR (anticipation, prix périmés, coûts oubliés).

## 13. Résultats de l'exécution précédente (conservés, publiés avec la relance)

Dossier : `/home/user/documentation/brvm-alpha/reports/validation_S1/precedent_20261122T121328Z` ; t0 précédent : 01/08/2017.

| Var. | Statut précédent | Rdt an. | Actif / TR | IR | DD rel. TR |
|---|---|---|---|---|---|
| A | REJETÉ | −11,6 % | −7,2 % | −1,14 | −33,1 % |
| B | REJETÉ | −11,8 % | −7,3 % | −1,16 | −33,8 % |
| C | REJETÉ | −11,6 % | −7,2 % | −1,15 | −33,2 % |
| D | REJETÉ | −12,0 % | −7,5 % | −1,22 | −34,5 % |
| E | REJETÉ | −11,6 % | −7,2 % | −1,14 | −33,1 % |
| F | REJETÉ | −11,5 % | −7,1 % | −1,13 | −32,9 % |
| G | REJETÉ | −11,5 % | −7,1 % | −1,14 | −32,9 % |
| H | REJETÉ | −11,6 % | −7,1 % | −1,14 | −33,1 % |
| I | REJETÉ | −10,3 % | −5,8 % | −1,16 | −28,2 % |
| REF | REJETÉ | −8,0 % | −3,6 % | −0,94 | −19,5 % |

## Fichiers

`metrics.json` (toutes les mesures), `weekly_returns.parquet` (rendements hebdomadaires nets des stratégies et des étalons sur la fenêtre d'évaluation), `nav.parquet` (valeurs liquidatives et niveaux, rebasés à t0), `trades.parquet` (exécutions de tous les runs), `lock.json` (verrou du test unique).

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
