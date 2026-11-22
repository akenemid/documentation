# Test unique S1 : journal des tentatives

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

Procédure : spécification §8.3, additif v1.1 §8.4 (D12) et précisions du §8.5 (écrites après le premier test). S1 = 2017-01-02 → 2022-11-16. Les deux résultats sont publiés : la tentative 1 dans `precedent_20261122T121328Z/` (fichiers inchangés), la tentative 2 dans ce dossier.

Légende : **faits** (données, règles, journaux d'exécution) ; **estimations** (toutes les métriques, calculées sur environ cinq ans) ; **hypothèses** (coûts, exécution, étalon reconstruit, chronologie pays [NON VÉRIFIÉ]).

## Tentative 1 : exécutée le 22/11/2026, résultats conservés

| Élément | Valeur (faits) |
|---|---|
| Commande | `python -m brvm_alpha validate --sample S1` (mode « evenementiel », 3 processus, n_boot = 5 000) |
| Commit exécuté | `a2bfeb4c9b09c6a97f1208dfd7d585146455b651` (état figé avant le test unique) |
| Début / fin (UTC) | 2026-11-22T09:56:26Z / 2026-11-22T10:07:47Z (679,6 s) ; 30 runs sur 30 « ok » ; contrôles comptables verts |
| Registre | essais S1-A à S1-I et REF-ID « exécuté », N = 88 |
| Statuts | A à H : REJETÉ (R1 à R5) ; I : REJETÉ (R1 à R4) ; REF : REJETÉ (R1 à R3) |
| Dossier | `precedent_20261122T121328Z/` (`metrics.json`, `resultats.md`, `lock.json`, `run.log`, `tentatives.md` d'origine) |

**Errata de la tentative 1** (audit du 22/11/2026 ; les fichiers archivés ne sont pas modifiés) :

1. **Statistiques chaînées faussées (bogue, constat majeur)** : 9 semaines étaient retirées de toutes les mesures, dont 7 hors de la fenêtre du §8.1 (2018-12-14, 2021-07-09, 2021-07-23, 2021-09-10, 2021-09-24, 2021-10-22, 2021-11-05). Le §3.1.3 exclut ces rendements multi-séances des seules estimations de dispersion « mais [les garde] pour chaîner le TR ». Le TR y gagnait +19,8 % cumulés : rendement du TR, rendements actifs, drawdowns et capacités publiés étaient faux (voir le tableau de la tentative 2).
2. **Couverture tautologique (bogue, constat majeur)** : les semaines attendues étaient celles du TR, calculées avec les mêmes retraits : couverture de 100 % par construction. Sur le calendrier W-FRI (moins la fenêtre du §8.1), elle valait **94,8 %** dans la lecture de la tentative 1 (sous le seuil de 95 %, fixé par le code seulement : statut INDÉTERMINÉ), et vaut **97,4 %** une fois les semaines multi-séances chaînées. Le seuil et la règle sont désormais écrits au §8.5 (E2).
3. **Empreinte « conforme au pré-enregistrement v1.1 » : contrôle autoréférentiel.** L'empreinte `f1582ed8e9fa1c85` apparaît pour la première fois dans le registre au commit figé `a2bfeb4` (09:56:15 UTC), 11 s avant le run : c'est l'empreinte de l'état figé, pas une valeur pré-enregistrée indépendante. La référence de pré-enregistrement est le commit `751d1be` (spécification ; YAML 1.0, empreinte `dcdf1fb7db530c44` des essais S1-A à S1-H). Atténuation vérifiée par l'audit : la spécification n'a pas changé depuis `751d1be` et les clés v1.1 du YAML reprennent les valeurs D1 à D12 du §8.4. Le verrou de la tentative 2 cite cette référence (`empreinte_controle.reference_preenregistrement`).
4. **Récit de 2021 inexact.** Le journal d'origine disait « aucune décision de fin août (pas de BOC à cette date) ». Faits : le 13/08/2021 est la dernière séance BOC d'août du calendrier de la stratégie ; une décision a bien eu lieu ce jour-là (33 titres éligibles, mode « selection » ; A_optimistic_10M passe en indice discipliné ce jour-là). Ses ordres ont **expiré** avant toute tentative : séance n° 1149 le 13/08, prochain BOC le 08/09 (n° 1167), âge de l'ordre 18 séances > `max_order_age` = 11 (âge compté en séances, BOC manquants compris). Le passage en liquidités du 02-03/08 au 05-12/10/2021 vient donc de **deux** règles figées : le plancher D1 (univers vide à la décision du 30/07 : 17 BOC sur 63 séances, sous le plancher de 20 observations des filtres d'univers) et l'âge des ordres après un trou de BOC. Sur cette fenêtre (30/07 → 05/10/2021), le TR gagnait +11,1 %, contre −3,6 % pour REF et −3,7 % pour A (faits de simulation de la tentative 1). Le rejet de A n'en dépend pas : R1, R3, R4 et R5 sont déjà vrais avant le 30/07/2021 (audit).
5. **Lectures à corriger** : la lecture « liquidités face à un TR baissier » ne tient plus : sur [t0 ; fin], le TR chaîné fait −0,82 %/an (et non −4,43 %/an), et les semaines retirées étaient des semaines de **hausse** du TR (2021), pendant lesquelles A et REF étaient en partie en liquidités. Le drawdown relatif journalier de REF (−31,3 %) cité à l'issue de la tentative 1 ne venait pas de la fréquence : il venait de ces semaines retirées ; en hebdomadaire chaîné, il vaut −27,1 % et **R4 devient vrai pour REF**.
6. **Coûts annuels surestimés d'environ 10 %** (annualisation à 252 séances au lieu des années calendaires : 1 207 séances observées sur 5,30 ans, soit 228 par an) ; la décomposition du coût par aller de A citée (« frais 1,24 %, demi-spread médian 1,41 %, impact 0,44 % » = 3,09 %) ne sommait pas au coût par aller de 2,89 % : décomposition pondérée exacte 1,244 + 1,325 + 0,323 = 2,892 %.

## Tentative 2 : relance motivée (D12), exécutée le 22/11/2026

| Élément | Valeur (faits) |
|---|---|
| Commande | `python -m brvm_alpha validate --sample S1 --rerun-reason "<motif>"` (mêmes défauts) ; journal : `run.log` |
| Motif consigné | bogues démontrés par l'audit (comptabilité des statistiques) : (1) semaines multi-séances retirées du chaînage, contraire au §3.1.3 ; (2) garde-fou de couverture tautologique ; corrections de publication associées (coûts en années calendaires, DSR sous deux conventions, sensibilité de la PBO, un IC par mois, empreinte sans autoréférence). **Aucun paramètre de stratégie modifié** |
| Commit exécuté | `1819997bc8f01ef6977a7db6dc3ddac0c2875401` (« [FIX] brvm-alpha: correction avant relance motivée de S1 ») ; arbre `brvm_alpha/` et `configs/` identique à HEAD |
| Empreinte de configuration | `f1582ed8e9fa1c85`, identique à celle de l'état figé `a2bfeb4` (mêmes paramètres que la tentative 1) |
| Début / fin (UTC) | 2026-11-22T12:13:28Z / 2026-11-22T12:26:03Z (755,3 s) ; code 0 ; 30 runs sur 30 « ok » ; contrôles comptables verts |
| Registre | 10 **nouveaux** essais S1-A-R1 à S1-I-R1 et REF-ID-R1 ; N = 88 → **98** ; les essais de la tentative 1 restent au registre |
| Statuts | A à H : **REJETÉ** (R1 à R5) ; I : **REJETÉ** (R1 à R4) ; REF : **REJETÉ** (R1 à R4, R4 nouveau) |
| Simulation | `nav.parquet` et `trades.parquet` **identiques octet pour octet** à ceux de la tentative 1 : mêmes ordres, mêmes valeurs liquidatives ; seules les mesures publiées changent |

Contrôles faits avant la relance (faits) : suite complète verte (1 280 tests réussis, sur l'état de travail incluant ces corrections) ; tests de régression des deux constats majeurs, qui échouent sur le code de la tentative 1 (`tests/test_fix_all_s1.py`) ; contrôle de fumée du pipeline corrigé sur **S0** seulement (4 runs A, A stress, E, REF, registre temporaire hors dépôt, aucun chiffre publié) pour vérifier qu'il tourne sur le panel réel avant la relance unique.

### Chiffres recalculés (estimations, coûts centraux, 10 M FCFA sauf mention ; fenêtre [01/08/2017 ; 16/11/2022])

| Mesure | Tentative 1 (publiée) | Tentative 2 (§3.1.3) |
|---|---|---|
| Composite TR : rendement annualisé | −4,43 %/an (255 semaines) | **−0,82 %/an** (262 semaines) |
| Composite TR : drawdown absolu | −42,7 % | −40,8 % |
| A : actif net contre le TR | −7,16 %/an | **−9,28 %/an** |
| A : drawdown relatif contre le TR | −33,1 % | **−40,2 %** |
| A : actif aux coûts de stress | −8,73 %/an | −10,81 %/an |
| A : actif par sous-période | −8,10 / −5,91 %/an | −8,55 / −9,97 %/an |
| I : actif net / drawdown relatif | −5,83 %/an / −28,2 % | −7,60 %/an / −34,6 % |
| REF : actif net / drawdown relatif | −3,59 %/an / −19,5 % | **−5,60 %/an / −27,1 % (R4 vrai)** |
| Capacité, actif contre le TR : A à 100 M / 1 Md | +0,36 / +4,13 %/an | **−2,69 / +0,51 %/an** |
| Capacité : I à 1 Md ; REF à 100 M / 1 Md | +3,89 ; −0,30 / +4,67 %/an | +0,25 ; −3,54 / +0,97 %/an |
| IR de A (dispersion, sans les semaines multi-séances) | −1,14 | −1,14 (inchangé) |
| Couverture de la période attendue | 100 % (tautologique) | **97,4 %** (94,8 % sans les semaines multi-séances) |
| Coûts annuels (A / I / REF) | 7,78 / 5,97 / 4,36 % de la VL | 7,04 / 5,40 / 3,94 % (années calendaires) |
| Coût par aller de A, décomposition pondérée | — | frais 1,244 % + demi-spread 1,325 % + impact 0,323 % = 2,892 % |
| DSR de A (N du registre) | 0,0016 (variance de la famille) | 0,0016 (famille) ; ≈ 2,5 × 10⁻³⁵ (variance des essais du registre) |
| IC mensuels de A (G7) | 67 IC sur 64 mois, t NW 1,68 | 62 mois distincts, t NW 1,72 |
| Part investie moyenne (A / REF) | 81,9 % / 82,0 % | inchangée |

**PBO de la famille (C6 échoue dans toutes les conventions)** : 0,845 (convention figée : 10 blocs de 25 semaines, plus anciennes semaines ignorées) ; 0,710 avec toutes les semaines (`array_split`) ; 0,817 si λ = 0 compte pour ½ ; 0,802 sans le clone exact E. Référence : PBO nulle de 5/9 ≈ 0,556 pour N = 9 (0,5 si λ = 0 compte pour ½). Le repère « famille simulée de quasi-clones » publié dans `metrics.json` (0,198 : une seule graine, bruit non recentré) n'est **pas probant** ; corrigé après la relance pour les exécutions futures (quasi-clones de même performance sur l'échantillon complet, 10 graines : environ 0,97 sur données synthétiques). La variance des Sharpe de la famille (1,3 × 10⁻⁵) montre des variantes quasi identiques : la PBO n'a pas de pouvoir discriminant ici.

**Variante E : non testée sur S1** (faits de données) : ses rendements sont identiques à ceux de A, faute d'avis de dividende daté à l'avance (première vue environ un jour avant la date ex en médiane) : la poche S1 ne s'ouvre jamais.

**Lecture (estimations)** : la correction **aggrave** la sous-performance mesurée (le TR chaîné est presque plat sur la fenêtre, et ses semaines de hausse de 2021 tombaient pendant des périodes en liquidités) et **ne change aucun rejet** de A à I ; elle ajoute R4 au rejet de REF. Les capacités positives de la tentative 1 à 1 Md FCFA étaient surtout un artefact des semaines retirées. Ce sont des estimations sur un seul échantillon : elles ne disent rien de garanti sur l'avenir.

## Points ouverts : décisions humaines attendues (nouvel essai, à juger sur S2 seulement)

1. **Trous de BOC de 2021 : deux règles en jeu.** Plancher D1 des filtres d'univers (univers vide à la décision du 30/07/2021) **et** âge des ordres compté en séances, BOC manquants compris (ordres de la décision du 13/08/2021 expirés pendant le trou). Un amendement porterait sur les deux règles ; ce serait un nouvel essai, jamais une relance de S1.
2. **REF investi à 82 % en moyenne (cible D8 : 98 %)** : dividendes et produit des sorties forcées gardés en liquidités jusqu'au rebalancement annuel (93-95 % après chaque rebalancement, 64-71 % avant le suivant). Application littérale des règles, contraire à l'intention de D8 ; une mise en œuvre différente (p. ex. réinvestir chaque fin de mois dans le cœur) serait un nouvel essai, à juger sur S2.
3. **Conventions pour S2** (propositions du §8.5) : DSR de G3 avec la plus grande des deux variances ; PBO avec λ = 0 compté pour ½ et clones exacts retirés ; empreinte enregistrée dans un commit antérieur à l'état figé.

Plus aucune relance de S1 n'est permise sans un nouveau bogue démontré (`--rerun-reason`).

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
