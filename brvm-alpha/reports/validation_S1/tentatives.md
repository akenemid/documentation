# Test unique S1 : journal des tentatives

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

Procédure : spécification §8.3 et additif v1.1 §8.4 (D12). S1 = 2017-01-02 → 2022-11-16.

## Tentative 1 (unique) : terminée, aucune relance

| Élément | Valeur (faits) |
|---|---|
| Commande | `python -m brvm_alpha validate --sample S1` (défauts : mode de décision « evenementiel », 3 processus, n_boot = 5 000) |
| Commit figé avant l'exécution | `a2bfeb4c9b09c6a97f1208dfd7d585146455b651` (« [ADD] brvm-alpha: état figé avant le test unique S1 (additif v1.1) ») |
| Arbre `brvm_alpha/` et `configs/` | identique à HEAD, aucun fichier non suivi |
| Empreinte de configuration | `f1582ed8e9fa1c85`, conforme au pré-enregistrement v1.1 (S1-I, REF-ID) |
| Début / fin (UTC) | 2026-11-22T09:56:26Z / 2026-11-22T10:07:47Z (679,6 s) |
| Code de sortie | 0 ; 30 runs sur 30 « ok » ; contrôles comptables verts |
| Verrou | `lock.json`, statut « terminé » |
| Registre | 10 essais S1 passés de « pré-enregistré » à « exécuté » (S1-A à S1-I, REF-ID), N = 88 |
| Journal | `run.log` |

Contrôles faits avant l'exécution :
- suite complète verte : 1192 tests réussis, en 301,58 s ;
- registre : aucun essai S1 « exécuté » ;
- `reports/validation_S1/` absent.

Aucun bogue n'a été corrigé, aucun paramètre n'a été modifié et aucune relance n'a été faite. Les résultats ont été produits au premier passage. Conformément au pré-enregistrement, plus aucune relance n'est permise sans bogue démontré (`--rerun-reason`).

## Point signalé avant l'exécution, non tranché par une décision humaine

Le pré-vol S0 avait demandé une décision humaine sur l'univers vide du 30/07/2021. Cause : 17 BOC sur 63 séances, sous le plancher de 20 observations fixé par D1 pour les filtres d'univers.

Aucune décision n'a été consignée avant le test. La règle figée de l'additif v1.1 (D1) a donc été appliquée **telle quelle**, conformément au §8.4, qui fait foi.

Constat sur les sorties (faits de simulation) :
- ventes totales les 02-03/08/2021 (décision du 30/07) ;
- aucune décision de fin août (pas de BOC à cette date) ;
- rachat les 05-12/10/2021 (décision du 28/09).

Sur cette fenêtre (30/07 → 05/10/2021), le TR gagne +11,1 %, contre −3,6 % pour REF et −3,7 % pour A.
