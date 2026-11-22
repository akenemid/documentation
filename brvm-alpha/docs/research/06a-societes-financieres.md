# 06a — Fiches fondamentales des sociétés financières cotées à la BRVM (état au 22/11/2026)

> **Périmètre** : les 17 valeurs du secteur « BRVM – Services financiers » (code FIN) du Bulletin Officiel de la Cote (BOC) du 20/11/2026. Pour chacune : pays, cours, capitalisation, PER, rendement, dividendes 2021-2026, résultats 2023-2025 et 9 mois 2026, ROE, solvabilité, qualité des actifs, actionnaire de référence et événements récents. Les valeurs sont ensuite classées par attractivité (qualité × valeur × croissance).
> **Date de rédaction** : 22/11/2026. **Dernier BOC utilisé** : 20/11/2026 (`data/boc_text/boc_20261120.txt.gz`).
> **Méthode** : les chiffres viennent de documents primaires publiés sur `www.brvm.org` : BOC, rapports d'activité trimestriels, états financiers annuels, communiqués des émetteurs, pages émetteurs et calendrier des dividendes. Les PDF scannés (BOA, Coris, Oragroup) ont été lus page par page. L'historique des dividendes a été reconstitué en analysant 1 sur 3 des BOC de 2020 à 2026 avec `brvm_alpha.data.boc_parser`.
> **Limites de cette recherche (à lire)** : (1) le quota de recherche web de la session était **épuisé** au moment de cette tâche. Aucune source secondaire (presse, notes d'analystes) n'a donc pu être consultée. (2) Le réseau de la session ne résout que `www.brvm.org` : african-markets.com et capmad.com sont **inaccessibles**. (3) Quand un chiffre n'a pas été trouvé dans les documents lus, c'est écrit « n.d. » ou « introuvable ». **Aucun chiffre n'a été inventé.**
> **Avertissement** : un classement fondamental n'est **pas** une prévision de rendement. Aucune méthode ne « garantit » un gain. Le secteur financier a déjà monté de **+52,06 % depuis le 1er janvier 2026** (BOC 20/11/2026), et une partie de la valeur décrite ici est donc déjà dans les cours. L'efficacité de ce score sur la BRVM **n'est pas démontrée** : elle doit être testée hors échantillon avec des données « point-in-time » (voir §9 et le document 04).

> **Vérification adversariale du 22/11/2026** : 28 éléments ont été revérifiés de façon indépendante (BOC locaux, PDF primaires de brvm.org relus, en-têtes HTTP `Last-Modified`, OCR). Les corrections sont intégrées dans le texte et signalées par « *(corrigé le 22/11/2026)* ». Ce qui reste incertain est marqué **[NON VÉRIFIÉ]**. Le détail figure dans la section finale « Vérification adversariale (2026-11-22) ». Principales corrections : délai de disponibilité des PDF porté à **2 séances**, dividende BOAC de **594,53** (et non 597,53), payout à calculer sur le **brut** (BOABF dépasse alors aussi 100 %), RN part du groupe 2025 d'Oragroup de **18,36 Md** (BPA de base 264, BPA dilué 241), flottant BICC expliqué.

Légende de confiance : **H** = document primaire lu (BOC, rapport ou états financiers de l'émetteur) ; **M** = calcul ou inférence à partir de documents primaires (formule indiquée) ; **B** = information partielle, ancienne ou non revérifiée.

Abréviations : RN = résultat net ; 9M = neuf premiers mois (au 30/09) ; S1 = premier semestre ; TTM = douze derniers mois ; CP = capitaux propres ; Md = milliard de FCFA ; PER = cours / bénéfice par action ; P/B = capitalisation / capitaux propres ; NPL = créances en souffrance ; CoR = coût du risque.

---

## 0. Synthèse en 12 points

| # | Constat | Valeur | Date | Conf. | Source |
|---|---|---|---|---|---|
| 1 | Valeurs du secteur FIN | **17** : 14 banques, 2 holdings bancaires (ETIT, ORGT) et 1 établissement financier (SAFC) | 20/11/2026 | H | BOC 20/11/2026 |
| 2 | Compagnies d'assurance cotées | **Aucune** : pas une seule action d'assureur parmi les 48 lignes du BOC | 20/11/2026 | H | BOC 20/11/2026 |
| 3 | Indice BRVM – Services financiers | 221,79 points ; **+52,06 % depuis le 1er janvier** ; PER moyen 14,51 | 20/11/2026 | H | BOC p.1 |
| 4 | Plus fortes hausses depuis le 1er janvier (FIN) | CBIBF +155 %, ETIT +148 %, BOABF +105 %, BOAN +69 %, BICC +59 % | 20/11/2026 | H | BOC |
| 5 | Seules valeurs en baisse depuis le 1er janvier | ECOC −7,5 %, SAFC −8,3 % (SAFC sans ajustement du DPS) | 20/11/2026 | H | BOC |
| 6 | Meilleures croissances du RN sur 9M 2026 | BOAN +122 %, BICB +64 %, BBGC +41 %, BOABF +34 %, CBIBF +18 %, BICC +15 % | 30/09/2026 | H | rapports T3 2026 |
| 7 | RN 9M 2026 en recul | NSBC **−27 %**, ECOC **−12 %**, SGBC −3,5 %, BOAB −3 % | 30/09/2026 | H | rapports T3 2026 |
| 8 | ROE 2025 les plus élevés | BICC ≈33 % (M), BOAC ≈30 % (M), ECOC 29,0 % (H), SIBC 27,2 % (H), BICB 26,8 % (H) | 2025 | H/M | rapports annuels |
| 9 | Taux de distribution (payout) > 100 % | **BOAB** : dividende net 2026 ≈ 23,7 Md pour un RN 2025 de 20,1 Md, soit ≈118 % en net et **≈131 % en brut** (brut 650 déduit d'un IRVM béninois de 10 %, inférence). **BOABF** : 91 % en net, mais **≈104 % en brut** si l'IRVM burkinabè est de 12,5 % [NON VÉRIFIÉ] *(corrigé le 22/11/2026)* | 2026 | M | BOC + états financiers ; doc 01 §6.1 |
| 10 | Exercice 2025 sans dividende | **BOAN** (RN −92 %) ; **ORGT** (dernier dividende en 2020) ; **SAFC** (dernier dividende en 2011) | 2026 | H | communiqué BOA-NG ; BOC |
| 11 | Changements réglementaires | Capital minimum des banques de l'UMOA porté à **20 Md FCFA** (avis BCEAO n°001-01-2024 du **05/01/2024**), avec un délai de 3 ans à compter du 01/01/2024, donc jusqu'au **31/12/2026**. C'est la raison explicite de la hausse du nominal de SGCI. Pour les attributions gratuites BOA/SIB de 2024, le lien est une **inférence** (M) : aucun communiqué BOA/SIB ne l'affirme dans les documents lus | 2024-2026 | H (SGCI) / M (BOA, SIB) | communiqué SGCI 21/02/2025 |
| 12 | Gouvernance | ETI : l'AGO du 26/10/2026 a été **annulée sur instruction de la Commission Bancaire de l'UMOA** | 23/10/2026 | H | communiqué ETI |

**Classement final (§7)**, à lire comme une liste de priorités de recherche et non comme des ordres d'achat :
1. BOAC
2. BICB
3. BOAS
4. BOAM
5. BICC
6. ETIT
7. SGBC
8. CBIBF
9. SIBC
10. ECOC
11. BBGC
12. BOABF
13. NSBC
14. BOAB
15. BOAN
16. ORGT
17. SAFC

---

## 1. Univers : les 17 valeurs FIN au 20/11/2026

Sources : BOC 20/11/2026 pour le cours, le PER, le rendement net, la variation depuis le 1er janvier et le compartiment. Nombre de titres et flottant : avis BRVM 303-2026, repris dans le document 01, §11. Liquidité et spread : calcul sur les BOC 2026 (document 01). Variation sur un an : clôtures du BOC du 20/11/2025 comparées à celles du 20/11/2026, sans ajustement (aucune opération sur titres dans la période, sauf le DPS SAFC d'avril 2026).

| Symbole | Société | Pays | Compart. | Cours (FCFA) | Nb titres | Capi. (Md) | Flottant % | PER BOC | Rdt net BOC | Var. depuis le 1er janv. | Var. 1 an | Valeur médiane/séance (M FCFA) | Spread médian |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SGBC | Société Générale Côte d'Ivoire | CI | Prestige | 38 795 | 31 111 110 | 1 207 | 43,4 | 11,91 | 5,93 % | +29,8 % | +46,4 % | 105,5 | 0,28 % |
| SIBC | Société Ivoirienne de Banque | CI | Prestige | 8 200 | 100 000 000 | 820 | 20,0 | 14,75 | 4,56 % | +42,6 % | +43,9 % | 62,2 | 0,57 % |
| ECOC | Ecobank Côte d'Ivoire | CI | Prestige | 14 795 | 55 050 600 | 814 | 23,8 | 12,83 | 5,28 % | −7,5 % | −7,5 % | 28,3 | 0,60 % |
| BICC | BICI CI (ex-BICICI) | CI | Principal | 31 000 | 16 666 670 | 517 | 32,5 | 14,15 | 3,73 % | +59,4 % | +59,0 % | 13,6 | 0,69 % |
| NSBC | NSIA Banque CI | CI | Principal | 15 000 | 24 734 572 | 371 | 20,0 | 9,11 | 4,51 % | +31,1 % | +25,0 % | 30,2 | 0,37 % |
| BBGC | Bridge Bank Group CI | CI | Principal | 8 145 | 50 000 000 | 407 | 20,0 | 14,97 | — | (IPO 24/09/2026) | — | 81,5 (40 séances) | 0,52 % |
| BOAC | Bank of Africa CI | CI | Principal | 10 995 | 40 000 000 | 440 | 30,3 | 12,37 | 5,43 % | +53,1 % | +50,7 % | 82,1 | 0,33 % |
| SAFC | SAFCA (Alios Finance CI) | CI | Principal | 3 030 | 11 869 750 | 36 | 29,2 | 51,31 | — | −8,3 % | (DPS) | 18,5 | 0,79 % |
| BOAB | Bank of Africa Bénin | BJ | Principal | 9 095 | 40 561 048 | 369 | 45,9 | 18,35 | 6,43 % | +55,5 % | +80,6 % | 31,0 | 0,48 % |
| BICB | BIIC Bénin | BJ | Principal | 7 500 | 57 759 800 | 433 | 33,1 | 11,95 | 3,39 % | +50,8 % | +51,5 % | 23,7 | 0,48 % |
| BOABF | Bank of Africa Burkina Faso | BF | Principal | 7 700 | 44 000 000 | 339 | 43,5 | 17,60 | 5,16 % | +105,3 % | +103,7 % | 23,7 | 0,46 % |
| CBIBF | Coris Bank International | BF | Principal | 27 505 | 32 000 000 | 880 | 30,4 | 13,44 | 3,27 % | +155,2 % | +154,7 % | 21,2 | 0,77 % |
| BOAM | Bank of Africa Mali | ML | Principal | 5 100 | 27 450 000 | 140 | 35,8 | 12,63 | 5,98 % | +27,5 % | +34,2 % | 24,6 | 0,21 % |
| BOAN | Bank of Africa Niger | NE | Principal | 4 420 | 20 800 000 | 92 | 40,9 | 224,63 | 4,73 % (*) | +69,4 % | +75,0 % | 25,2 | 0,62 % |
| BOAS | Bank of Africa Sénégal | SN | Principal | 7 700 | 36 000 000 | 277 | 38,3 | 12,65 | 5,84 % | +47,0 % | +39,9 % | 46,1 | 0,27 % |
| ETIT | Ecobank Transnational Inc. | TG | Principal | 57 | 18 084 106 722 (**) | 1 031 (**) | 33,5 | 2,98 (**) | 1,61 % | +147,8 % | +137,5 % | 45,8 | 2,99 % |
| ORGT | Oragroup | TG | Principal | 2 500 | 69 986 131 | 175 | 19,8 | 8,02 (**) | 2,38 % (*) | +4,2 % | +0,2 % | 11,6 | 0,52 % |

(*) Le rendement BOC est **périmé** : il se calcule sur le dernier dividende payé, versé en juin 2025 pour BOAN et en juillet 2020 pour ORGT. BOAN ne verse **rien** au titre de 2025, et ORGT ne verse rien depuis 2020.
(***) *(Ajout du 22/11/2026)* Le rendement BOC de BOAC (5,43 %) est calculé sur 597,53 FCFA, une valeur erronée de la colonne « Dernier dividende payé ». Le dividende réellement appliqué par la BRVM est de 594,53 FCFA (voir §4), ce qui donne un rendement de 5,41 %. Le flottant de BOAN (40,9 %, avis 303) compte la part de SONIMEX (5,73 %) : seul le bloc de BOA West Africa (59,06 %) en est exclu.
(**) Le PER du BOC et la capitalisation BRVM d'ETIT et d'ORGT **ne sont pas fiables** : le BOC divise le résultat consolidé **total** (minoritaires compris) par le nombre de titres. Pour ETIT, le BPA IFRS 2025 publié est de 10,00 FCFA, ce qui donne un **PER de 5,7** au cours de 57, et non 2,98. Ce BPA implique ≈23,7 milliards d'actions, contre 18,08 milliards retenus par la BRVM (voir §8). Pour ORGT, le BPA part du groupe 2025 est de **264 FCFA (de base)** et de **241 FCFA (dilué)**, soit un **PER de 9,5 (de base) ou de 10,4 (dilué)** *(précisé le 22/11/2026)*. Pour ETIT, la vérification confirme : RN consolidé 2025 de 345 523 M FCFA / 18,084 milliards de titres = 19,1 FCFA, et 57 / 19,1 = 2,98, soit exactement le PER du BOC.

**Lecture** : les trois banques du compartiment Prestige (SGBC, SIBC, ECOC) et BOAC/BBGC sont les plus liquides (≥ 60 M FCFA par séance). Les spreads sont serrés (0,2-0,8 %), sauf ETIT : son pas de cotation de 1 FCFA pour un cours de 57 FCFA représente à lui seul 1,75 %.

---

## 2. Contexte sectoriel utile au modèle

| Fait | Détail | Date | Conf. | Source |
|---|---|---|---|---|
| Capital social minimum des banques | Le capital minimum des **banques** de l'UMOA passe à **20 Md FCFA** (décision du Conseil des ministres de l'UMOA du 21/12/2023, avis BCEAO n°001-01-2024 du **05/01/2024**). Les banques ont 3 ans à compter du 01/01/2024 pour s'y conformer, soit jusqu'au 31/12/2026. Le seuil applicable aux **établissements financiers** (cas de SAFC) n'est pas clair dans le texte du communiqué SGCI et reste **[NON VÉRIFIÉ]** : le site de la BCEAO n'est pas accessible depuis cette session *(corrigé le 22/11/2026)*. Conséquences observées : attributions gratuites BOA et SIB en 2024 (doc 01, §8.2), nominal SGCI porté de 500 à 643 FCFA (AGE du 28/05/2024), hausse de capital de BICI CI par incorporation de réserves (titre d'un communiqué de 11/2024) | 2024-2026 | H | communiqué SGCI 21/02/2025 ; communiqué BICI 29/11/2024 (titre) |
| Ratio de solvabilité minimum | **11,50 %** pour la solvabilité totale (et pour SAFC : CET1 ≥ 7,5 %, Tier 1 ≥ 8,5 %, levier ≥ 3 %, division des risques ≤ 25 %). Une éventuelle surcharge pour les banques d'importance systémique n'a pas été vérifiée **[NON VÉRIFIÉ]** : pour une grande banque, le minimum effectif peut être supérieur à 11,5 % | 2025-2026 | H | rapport annuel BIIC 2025 (« minimum réglementaire BCEAO de 11,50 % ») ; rapport T3 2026 SAFCA (annexe 4) |
| Fiscalité des dividendes (CI) | Le calendrier BRVM donne les dividendes **bruts** des sociétés ivoiriennes, avec un **IRVM de 12 %** pour les personnes physiques et de **10 %** pour les personnes morales. Les autres pays sont publiés en net. **Exception** : SGBC 2026, avec un brut de 2 606 et un net publié de 2 298,75 (et non 2 606 × 0,88 = 2 293,28). La BRVM a appliqué 2 298,75 au cours de référence (40 000 → 37 705 le 20/08/2026). Il faut donc **toujours utiliser le net publié**, jamais brut × 0,88 *(corrigé le 22/11/2026)* | 06/10/2026 | H | calendrier des dividendes, exercice 2025 ; BOC 20/08/2026 |
| Saison des dividendes FIN (exercice 2025) | BOABF le 23/04 (premier) ; BOAC le 06/05 ; BOAB et ECOC le 26/05 ; BOAS le 01/06 ; BOAM le 03/06 ; CBIBF le 19/06 ; ETIT le 30/06 ; BICC le 06/07 ; SIBC et BICB le 31/07 ; NSBC le 04/08 ; SGBC le 24/08 (dernier). Date ex-dividende = veille de la date de paiement | 2026 | H | calendrier des dividendes, exercice 2025 |
| Risque souverain (Sénégal) | Plusieurs obligations de l'État du Sénégal cotent nettement sous le pair (ex. EOS.O24 à 8 500 pour 10 000 de nominal). Les banques sénégalaises (BOAS) portent des titres publics | 20/11/2026 | H (cours) / M (lien) | BOC 20/11/2026, p.5 |
| Risque pays (Niger) | Créances en souffrance du secteur bancaire nigérien : **24,4 % → 28,6 %** entre 11/2024 et 11/2025 ; crédits du secteur −4,1 % en 2025. Le communiqué est daté du 20/02/2026, mais il n'a été publié sur brvm.org que le 18/03/2026 à 09:06 UTC (fichier préfixé 20260313) | 20/02/2026 (publication : 18/03/2026) | H | communiqué BOA-Niger (« profit warning ») ; en-tête HTTP `Last-Modified` |
| Prime de risque du marché affichée au BOC | 0,58 (indicateur BRVM, définition non documentée ici) | 20/11/2026 | H (valeur) / B (définition) | BOC p.1 |

---

## 3. Tableau comparatif des résultats (en Md FCFA)

RN = résultat net **social** (comptes PCB-UMOA), sauf pour BICB (IFRS depuis 2025, 2024 retraité), ETIT (IFRS consolidé, **part du groupe**) et ORGT (IFRS consolidé). TTM = RN 2025 + RN 9M 2026 − RN 9M 2025 (pour BOAM : S1 au lieu de 9M). Les chiffres 9M ne sont pas audités.

| Symb. | RN 2023 | RN 2024 | RN 2025 | Var. 2025 | RN 9M 2025 | RN 9M 2026 | Var. 9M | RN TTM (M) | TCAM 23→25 (M) | Conf. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SGBC | 97,23 | 101,23 | 101,35 | +0,1 % | 83,31 | 80,42 | −3,5 % | 98,5 | +2,1 % | H |
| SIBC | 43,5 | 50,2 | 55,6 | +11 % | 43,0 | 45,7 | +6 % | 58,3 | +13,1 % | H |
| ECOC | 48,07 | 57,48 | 63,48 | +10,4 % | 44,44 | 38,95 | −12,3 % | 58,0 | +14,9 % | H |
| BICC | 16,69 | 26,23 | 36,52 | +39,2 % | 27,40 | 31,44 | +14,7 % | 40,6 | +47,9 % | H |
| NSBC | 34,81 | 38,11 | 40,71 | +7 % | 25,04 | 18,39 | −27 % | 34,1 | +8,1 % | H |
| BOAB | 21,53 | 19,65 | 20,11 | +2,3 % | 15,88 | 15,34 | −3 % | 19,6 | −3,4 % | H |
| BOABF | 29,06 | 22,42 | 19,25 | −14,1 % | 13,45 | 18,05 | +34,2 % | 23,9 | −18,6 % | H |
| BOAC | 26,08 | 32,04 | 35,54 | +10,9 % | 26,63 | 29,66 | +11,4 % | 38,6 | +16,7 % | H |
| BOAM | 5,78 | 9,12 | 11,08 | +21,5 % | S1 : 6,21 | S1 : 6,72 | +8,2 % | 11,6 | +38,5 % | H |
| BOAN | 10,08 | 5,00 | 0,41 | −91,8 % | 2,84 | 6,29 | +121,9 % | 3,9 | n.s. | H |
| BOAS | 17,02 | 19,98 | 21,91 | +9,6 % | 16,37 | 18,17 | +11,0 % | 23,7 | +13,5 % | H |
| CBIBF | 64,25 | 47,94 | 65,50 | +36,6 % | 52,92 | 62,34 | +17,8 % | 74,9 | +1,0 % | H |
| ETIT (part du groupe) | 174,6 (287,8 M$) | 202,3 (333,2 M$) | 236,8 (407,1 M$) | +22 % ($) | 182,1 (310,0 M$) | 205,8 (364,0 M$) | +17 % ($) | 260,5 | +16,5 % | H |
| ORGT (total ; part du groupe) | −18,19 ; −19,46 | −44,36 ; **−37,87** | 21,64 ; **18,36** *(corrigé : et non ≈16,9)* | n.s. | 19,06 | 21,72 | +14 % | 24,3 (total) | n.s. | H |
| SAFC | −0,58 | −0,17 | 0,70 | n.s. | 0,31 | 1,21 | +294 % | 1,6 | n.s. | H |
| BICB | n.d. (avant IFRS) | 29,0 (IFRS retraité) | 36,2 | +24,7 % | 12,96 | 21,20 | +63,6 % | 44,4 | n.d. | H |
| BBGC | n.d. | n.d. | ≈27,2 (M) | n.d. | 16,9 | 23,8 | +41 % | ≈34,1 | n.d. | H (9M) / M (2025) |

Notes :
- ORGT *(corrigé le 22/11/2026)* : les états financiers 2025 donnent un RN « attribuable aux actionnaires de la holding » de **18 355 M** (2024 : −37 865 M), un **BPA de base de 264** FCFA et un **BPA dilué de 241** FCFA. L'ancien chiffre de ≈16,9 Md venait de 241 × 69,99 M d'actions, ce qui mélange le BPA dilué et le nombre d'actions de base.
- Contrôle croisé (22/11/2026) : pour les 16 valeurs hors ETIT, RN 2025 ≈ (cours / PER BOC) × nombre de titres, à ±0,1 % près (ORGT +0,8 %). Les RN 2025 du tableau sont donc cohérents avec ceux qu'utilise la BRVM.
- BBGC : le RN 2025 est **déduit** du PER BOC (8 145 / 14,97 = 544 FCFA par action × 50 M d'actions). Il n'a pas été trouvé dans un document de l'émetteur (la note d'information de l'OPV n'a pas pu être lue).
- ETIT : les montants en FCFA sont publiés par ETI au taux de chaque période. La variation en dollars est la plus parlante.
- BICB : le RN du 4e trimestre est historiquement élevé. Selon la direction, le RN 9M 2026 représente déjà 59 % du RN 2025.

### 3.1 Rentabilité, valorisation et solidité

ROE = RN / moyenne des CP de début et de fin d'exercice (M), sauf mention « publié ». P/B = capitalisation BRVM / derniers CP connus. PER TTM = capitalisation / RN TTM. Rendement bénéficiaire (E/P) = 1 / PER TTM.

| Symb. | ROE 2025 | CP récents (Md) | P/B | PER TTM | E/P TTM | Solvabilité | Qualité des actifs (dernière donnée) | Conf. |
|---|---:|---:|---:|---:|---:|---|---|---|
| SGBC | 21,4 % (M) | 495,1 (12/2025) | 2,44 | 12,3 | 8,2 % | 16,3 % (12/2024) ; **17,6 % (S1 2026)** | NPL 7,5 % (2024) → **8,0 %** (2025), couverture 82 % ; CoR stable à 26,4 Md sur 9M 2026 | H |
| SIBC | **27,16 % (publié)** | 204,8 (12/2025) | 4,00 | 14,1 | 7,1 % | > 14 % (2025) | NPL non publié dans les rapports lus | H |
| ECOC | **29,0 % (publié)** ; 24,9 % sur 9M 2026 | 218,6 (12/2025) | 3,73 | 14,0 | 7,1 % | n.d. | NPL 3,9 %, couverture 99,1 % (T1 2026). Puis NPL bruts **+28 %** à 46,9 Md (09/2026), couverture ≈92,6 % (M). CoR de 0,1 % à **1,1 %** | H |
| BICC | ≈33,1 % (M) | 120,6 (12/2025) | 4,28 | 12,7 | 7,9 % | n.d. | CoR en reprise nette en 2025 (+1,5 Md) ; crédits nets −7,2 % (2025) | H/M |
| NSBC | 18,3 % (M) | 233,3 (12/2025) | 1,59 | 10,9 | 9,2 % | n.d. | CoR −8,5 Md (2025) ; « provisionnement prudent » sur 9M 2026 ; crédits nets **−19 %** depuis décembre | H |
| BOAB | 17,1 % (M) | 117,5 (12/2025) | 3,14 | 18,9 | 5,3 % | n.d. | crédits −5 % (9M 2026) ; CoR en hausse | H |
| BOABF | 15,1 % (M) | 126,5 (12/2025) | 2,68 | 14,2 | 7,0 % | n.d. | CoR 2025 −8,4 Md (+94 %) ; crédits clientèle **−19,3 %** (2025) | H |
| BOAC | ≈30 % (M, CP 2025 estimés) ; 30,7 % en 2024 (M) | ≈127 (estim.) | ≈3,5 | 11,4 | 8,8 % | n.d. | crédits nets +20 % ; CoR 3,4 Md (9M 2026, stable) | H/M |
| BOAM | 23,1 % (M) | 49,8 (12/2025) | 2,81 | 12,1 | 8,3 % | n.d. | CoR S1 2026 −4,5 Md (+23,5 %) | H |
| BOAN | **1,0 % (publié)** ; 11,4 % en 2024 ; 16,0 % au T1 2026 | ≈44 (M, déduit du ROE 2024) | ≈2,1 | 23,8 (≈11 sur le 9M 2026 annualisé) | 4,2 % | 15,4 % (2024) → 14,1 % (2025) → **17,4 %** (T1 2026) | crédits **−20,9 %** (2025) ; dotations non récurrentes ; pays à 28,6 % de NPL sectoriel | H |
| BOAS | 23,7 % (M) | 96,5 (12/2025) | 2,87 | 11,7 | 8,5 % | n.d. | emplois −3,4 % (9M 2026) ; exposition au souverain sénégalais | H/M |
| CBIBF | n.d. (CP non trouvés) | n.d. | n.d. | 11,7 | 8,5 % | n.d. | CoR 2024 40,5 Md (+72 %), puis 16,5 Md en 2025 (−59 %) : nettoyage du portefeuille en 2024 | H |
| ETIT | **ROTE 27,8 % (publié 2025)** ; 24,9 % sur 9M 2026 | 1 181,8 part du groupe (09/2026) | ≈1,1-1,25 (sur BPA) | ≈5,3 (sur BPA TTM) | ≈19 % | n.d. | créances douteuses **9,4 % → 7,5 %** (12/2025 → 09/2026) ; CoR 287 M$ sur 9M | H/M |
| ORGT | ≈29,5 % (M, RN part du groupe 18,36 / moyenne des CP 54,8 et 69,5), sur une base de fonds propres très mince ; peu significatif | 69,5 part du groupe (12/2025) | 2,52 | 9,0 | 11,2 % | n.d. | CoR −69,1 Md (2024) → −7,0 Md (2025) ; crédits −9 % (9M 2026) | H |
| SAFC | ≈12,6 % (M) | 8,6 (09/2026) | 4,17 | 22,5 | 4,4 % | **12,11 %** (minimum 11,5 %) | CoR positif (reprises) | H |
| BICB | **26,8 % (publié)** | 140,8 (09/2026) | 3,08 | 9,8 | 10,3 % | **19,64 %** (CET1 = T1 = total) | couverture ECL IFRS 9 de 1,14 % (2025) puis 1,65 % (S1 2026) ; CoR = 26 % du RBE | H |
| BBGC | n.d. | n.d. | n.d. | ≈11,9 (M) | ≈8,4 % | n.d. | CoR 5,9 Md (+28 %) ; crédits **+39 %** sur un an | H/M |

**Point d'attention valorisation** : en 2026, les P/B ont fortement monté avec les cours. SIBC, BICC, ECOC et SAFC dépassent 3,7 fois les capitaux propres. Un P/B élevé reste cohérent si le ROE se maintient (le P/B « juste » vaut à peu près (ROE − g) / (k − g)). Mais tout recul du ROE (cas d'ECOC et de NSBC en 2026) se paie alors par une baisse plus que proportionnelle du cours.

---

## 4. Historique des dividendes (2021 → 2026)

Source : colonne « Dernier dividende payé » des BOC 2020-2026 (montants **nets** par action, en FCFA, classés par **année de paiement** ; le dividende payé en N porte sur l'exercice N−1). Les colonnes « ajustées » tiennent compte des attributions gratuites de 2024 (doc 01, §8.2). Payout de l'exercice 2025 = dividende 2026 × nombre de titres / RN 2025.

> *(Corrigé le 22/11/2026)* Le payout est calculé ici sur le **brut** pour les sociétés ivoiriennes et sur le **net** pour les autres. Les deux ne sont donc pas comparables. Le payout économique est celui du **brut** (ce que la société distribue). Pour les émetteurs non ivoiriens, le brut se déduit du net avec l'IRVM du pays (doc 01 §6.1 : BJ ≈10 % pour BOAB, ≈5 % pour BICB ; BF 12,5 % [NON VÉRIFIÉ] ; ML et NE 7 % ; SN 10 % ; TG non vérifié). Les payouts bruts figurent entre crochets dans la colonne.

| Symb. | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Ajustement attributions | Série ajustée 2021→2026 | Payout exercice 2025 | Conf. |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|
| SGBC | 368,30 | 1 004,93 | 1 112,43 | 1 553,85 | 1 645,78 | 2 298,75 (brut 2 606) | aucun | identique | **80 % brut** (57,25 % pour l'exercice 2024) | H |
| SIBC | 360 | 405 | 495 | 495 | 330 | 374 (brut 425) | 1:1 le 14/11/2024 (×0,5) | 180 ; 202,5 ; 247,5 ; 247,5 ; 330 ; 374 | 76 % brut | H |
| ECOC | 294,30 | 420,30 | 549 | 594 | 707,52 | 781,44 (brut 888) | aucun | identique | 77 % brut (publié) | H |
| BICC | 50 | 518 | 401,40 | 540,90 | 830,72 | 1 157,20 (brut 1 315) | aucun (même nombre de titres) | identique | 60 % brut | H |
| NSBC | — | — | 363,60 | 454,83 | 668,15 | 675,98 (brut 768,16) | aucun | identique | 47 % brut | H |
| BOAB | 436 | 546 | 627 | 706 | 468 | 585 | 1:1 le 03/09/2024 (×0,5) | 218 ; 273 ; 313,5 ; 353 ; 468 ; 585 | **≈118 % net** [≈131 % brut] | H/M |
| BOABF | 370 | 448 | 577 | 704 | 428 | 397 | 1:1 le 28/08/2024 (×0,5) | 185 ; 224 ; 288,5 ; 352 ; 428 ; 397 | ≈91 % net [**≈104 % brut**, IRVM 12,5 % NON VÉRIFIÉ] | H/M |
| BOAC | 315 | 374 | 540 | 684 | 469 | **594,53** *(corrigé : 597,53 au BOC)* | 1:1 le 25/10/2024 (×0,5) | 157,5 ; 187 ; 270 ; 342 ; 469 ; 594,5 | ≈67 % net [≈76 % brut si IRVM 12 %] | H/M |
| BOAM | — | — | — | 144 | 237,15 | 305,04 | 1:2 le 28/08/2024 (×2/3) | — ; — ; — ; 96 ; 237,15 ; 305,04 | ≈76 % net [≈81 % brut] | H/M |
| BOAN | 429,66 | 567,30 | 613,80 | 609,15 | 209,25 | **0** | 3:5 le 04/09/2024 (×0,625) | 268,5 ; 354,6 ; 383,6 ; 380,7 ; 209,25 ; 0 | 0 % | H |
| BOAS | 161,01 | — | 187,50 | 300 | 350 | 450 | 1:2 le 29/08/2024 (×2/3) | 107,3 ; — ; 125 ; 200 ; 350 ; 450 | ≈74 % net | H/M |
| CBIBF | 406 | 448 | 525 | 790 | 555 | 900 | aucun | identique | ≈44 % net | H/M |
| ETIT | — | 0,90 | 0,60 | — | — | 0,9184 | aucun | identique | ≈10 % (40 M$ pour 407 M$) | H |
| ORGT | — | — | — | — | — | — | — | dernier dividende : 59,52 le 17/07/2020 | 0 % | H |
| SAFC | — | — | — | — | — | — | — | dernier dividende : 23,04 le 29/07/2011 | 0 % | H |
| BICB | (non cotée) | — | — | — | 254,6 | 254,6 | aucun | identique | ≈41 % net | H |
| BBGC | (non cotée) | — | — | — | — | — | — | premier dividende attendu en 2027 (non annoncé) | — | H |

Anomalies relevées dans les BOC : (a) ECOC affiche en 2023 une date « 30-mai-22 » pour le dividende de 549 FCFA payé en 2023. Il s'agit d'une coquille de date à corriger. (b) BOAC *(corrigé le 22/11/2026 ; la recommandation précédente est **réfutée**)* : le BOC du 04/05/2026 (ligne « (d) ») affiche 594,53 et une référence ex de 8 845 pour une clôture de 9 435. Or 9 435 − 594,53 = 8 840,47, arrondi au pas supérieur de 5 FCFA = 8 845, alors que 597,53 donnerait 8 840. La colonne ne passe à 597,53 qu'à partir du BOC du 05/05/2026. **La BRVM a donc appliqué 594,53** (calendrier : 594,528 ; page émetteur : 594,5). Pour l'ajustement des prix, retenir 594,528 et considérer 597,53 comme une coquille du BOC.

**Lecture** : SGBC, ECOC, BICC, BOAS, BOAC et CBIBF combinent un dividende ajusté en hausse régulière et un payout soutenable (≤ 80 % en brut pour les sociétés ivoiriennes). Pour BOAB, le dividende 2026 dépasse le bénéfice 2025, en net (118 %) comme en brut (≈131 %). Il est donc **financé en partie par les réserves**, ce qui n'est pas soutenable sans reprise des résultats. *(Ajout du 22/11/2026)* Pour BOABF, le brut est probablement **supérieur au RN 2025 lui aussi** (≈104 % avec un IRVM de 12,5 %, ≈96 % avec 5 %). Le constat dépend du taux d'IRVM du Burkina, qui reste [NON VÉRIFIÉ].

---

## 5. Fiches par société

Chaque fiche indique les faits, puis un verdict. Les URL complètes sont en §11.

### 5.1 SGBC — Société Générale Côte d'Ivoire (CI, Prestige)
- **Marché** : 38 795 FCFA ; capitalisation de 1 207 Md, la plus forte du secteur ; PER BOC 11,91 ; rendement net 5,93 % ; +29,8 % depuis le 1er janvier ; la plus liquide du secteur (105 M FCFA par séance, spread 0,28 %) (H).
- **Résultats** : RN 97,2 Md (2023), 101,2 Md (2024), 101,4 Md (2025, +0,1 %). Sur 9M 2026 : PNB 197,6 Md (−1,7 %), RN **80,4 Md (−3,5 %)**. Selon la banque, la marge d'intérêts a été pénalisée par une « croissance sélective » et des « régularisations exceptionnelles ». Coefficient d'exploitation de 36,8 %. Crédits 2 593 Md (+4,3 %), dépôts 2 962 Md (+0,8 %) (H).
- **Rentabilité et solidité** : ROE 2025 ≈21,4 % (M). Solvabilité 16,3 % (2024) puis 17,6 % (S1 2026). NPL de 6,8 % (2023) à 7,5 % (2024) puis 8,0 % (2025), couverture 82 % (H).
- **Dividende** : brut de 2 606 FCFA pour l'exercice 2025 (payout 80 %, contre 57 % un an plus tôt) ; net de 2 298,75 FCFA le 24/08/2026 (H).
- **Actionnariat** : Société Générale 55,10 % et S.G. Financial Services Holding 1,41 % au 31/12/2023 (page émetteur BRVM, donnée ancienne → B pour 2026). Flottant de 43,4 % (avis 303-2026) (H).
- **Événements** : hausse du nominal de 500 à 643 FCFA par incorporation de réserves (AGE du 28/05/2024 ; capital porté à 20,0 Md) pour respecter le capital minimum BCEAO (H).
- **Verdict** : franchise de premier rang, valeur défensive et de rendement. Mais la croissance est **à l'arrêt** et les NPL montent doucement. La hausse du payout à 80 % limite la progression future du dividende. **Rang 7.**

### 5.2 SIBC — Société Ivoirienne de Banque (CI, Prestige)
- **Marché** : 8 200 FCFA ; 820 Md ; PER BOC 14,75 ; rendement 4,56 % ; +42,6 % depuis le 1er janvier (H).
- **Résultats** : RN 43,5 Md (2023), 50,2 Md (2024), 55,6 Md (2025, +11 %). S1 2026 : 32,1 Md (+9 %). 9M 2026 : **45,7 Md (+6 %)**, PNB 83,3 Md (+2 %). Crédits +12 % et dépôts +12 % sur un an au S1 2026 (H).
- **Rentabilité** : ROE publié de 30,56 % (2024) puis 27,16 % (2025). Solvabilité « > 14 % » (2025) (H). NPL **non publié** dans les rapports lus.
- **Dividende** : brut de 425 FCFA (payout 76 %) ; net de 374 FCFA le 31/07/2026. Attribution gratuite de 1 action pour 1 le 14/11/2024 (H).
- **Actionnariat** : la banque mentionne un « actionnaire de référence » sans le nommer dans les documents lus. Le nom du groupe bancaire de contrôle n'a pas pu être vérifié dans une source primaire pendant cette session (**à compléter**). Flottant de 20,0 % (H pour le flottant).
- **Qualité des données** : le PDF du rapport T3 2026 contient un texte parasite (« Bonsoir M.KADER ») au milieu du tableau. Les chiffres restent cohérents entre eux, mais l'extraction automatique doit être contrôlée (H).
- **Verdict** : très bonne qualité (ROE > 27 %, croissance régulière) mais valorisation exigeante (P/B 4,0 ; PER TTM 14,1). **Rang 9.**

### 5.3 ECOC — Ecobank Côte d'Ivoire (CI, Prestige)
- **Marché** : 14 795 FCFA ; 814 Md ; PER BOC 12,83 ; rendement 5,28 % ; **−7,5 % depuis le 1er janvier**, l'une des deux seules valeurs FIN en baisse (H).
- **Résultats** : RN 48,1 Md (2023, ROE 27,0 %), 57,5 Md (2024), 63,5 Md (2025, +10,4 %, ROE 29,0 %). 9M 2026 : PNB 98,2 Md (+1,8 %), mais RN **39,0 Md (−12,3 %)**, à cause d'un CoR passé de 0,7 à 8,1 Md. ROE de 24,9 % sur 9M 2026 (H).
- **Qualité des actifs** : NPL de 3,9 % et couverture de 99,1 % au T1 2026. Au 30/09/2026, les créances en souffrance brutes atteignent 46,9 Md (+28 % sur un an) pour 43,4 Md de provisions (couverture ≈92,6 %, M). Ratio crédits/dépôts de 54,5 % (H).
- **Dividende** : brut de 888 FCFA (payout 77 %, +10 %) ; net de 781,44 FCFA le 26/05/2026 (H).
- **Actionnariat** : filiale du groupe Ecobank (ETI). Le pourcentage exact n'a pas été trouvé dans les documents lus (B). Flottant de 23,8 %.
- **Verdict** : ROE très élevé et dividende solide. Mais le **risque de crédit remonte** et le RN 2026 sera probablement inférieur à celui de 2025. Le marché l'a déjà sanctionnée. Point d'entrée à surveiller : stabilisation du CoR au T4 2026. **Rang 10.**

### 5.4 BICC — BICI CI, ex-BICICI (CI, Principal)
- **Marché** : 31 000 FCFA ; 517 Md ; PER BOC 14,15 (BPA 2025 de 2 191 FCFA, H) ; rendement 3,73 % ; +59,4 % depuis le 1er janvier ; liquidité modeste (13,6 M FCFA par séance) (H).
- **Résultats** : RN 12,4 Md (2022), 16,7 Md (2023), 26,2 Md (2024), **36,5 Md (2025, +39,2 %)**. 9M 2026 : PNB 65,2 Md (+12,1 %), RN **31,4 Md (+14,7 %)**. Moteurs : portefeuille titres (+25,6 % en 2025) et commissions (+29,8 %). Les crédits nets **reculent** (−7,2 % en 2025, −1,2 % sur 9M 2026) et les dépôts augmentent (+16,3 %, puis +9,1 %) (H).
- **Rentabilité** : ROE 2025 ≈33 % (M ; CP de 99,8 → 120,6 Md) (M).
- **Dividende** : brut de 1 315 FCFA (payout 60 %) ; net de 1 157,20 FCFA le 06/07/2026 (H).
- **Actionnariat** : décret du 28/09/2022 autorisant un consortium ivoirien (**BNI, CNPS, CDC-CI, IPS-CGRAE**) à racheter **67,49 %** (BNP Paribas 59,79 % + Proparco 7,70 %) pour 80 Md FCFA. **Brandon & McAin Capital** a franchi le seuil de 10 % (19,11 %) le 27/06/2023 en rachetant les titres des sociétés SUNU au cours de 6 945 FCFA (H). *(Corrigé le 22/11/2026)* Le flottant officiel de 32,51 % (avis 303 : 5 418 860 titres) **n'est pas incohérent** : 16 666 670 − 11 247 810 (bloc du consortium) = 5 418 860, exactement. La BRVM n'exclut que le bloc de contrôle et compte les 19,11 % de Brandon & McAin dans le flottant. Le flottant **économique** est donc d'au plus ≈13,4 % si ce bloc est toujours détenu (détention actuelle [NON VÉRIFIÉ]).
- **Verdict** : la croissance la plus forte des banques ivoiriennes et un ROE de premier plan. Mais la croissance vient de la **trésorerie et des titres, pas du crédit**, ce qui la rend sensible à une baisse des taux BCEAO. Valorisation élevée (P/B 4,3), liquidité faible. **Rang 5.**

### 5.5 NSBC — NSIA Banque Côte d'Ivoire (CI, Principal)
- **Marché** : 15 000 FCFA ; 371 Md ; PER BOC 9,11 ; rendement 4,51 % ; +31,1 % depuis le 1er janvier (H).
- **Résultats** : RN 34,8 Md (2023), 38,1 Md (2024), 40,7 Md (2025, +7 %). 9M 2026 : PNB 73,5 Md (−5 %), RN **18,4 Md (−27 %)**. Crédits nets de 1 818,7 à 1 472,6 Md (**−19 %** depuis décembre, « dénouement d'opérations de financement significatives ») et dépôts −10 % (H).
- **Rentabilité** : ROE 2025 ≈18,3 % (M). P/B 1,59, le plus bas des banques commerciales (M).
- **Dividende** : aucun en 2021 ni en 2022, puis 363,60 / 454,83 / 668,15 / 675,98 FCFA nets (brut 768,16 en 2026 ; payout 47 %) (H).
- **Actionnariat** : « désormais détenue par **NSIA Holding Financière** (NHF) ». Deux déclarations de franchissement de seuil le 16/04/2026 (NSIA Holding Financière et NSIA Participations) correspondent à un reclassement intra-groupe (H pour l'existence ; le détail des pourcentages n'a pas été lu car le PDF est scanné).
- **Verdict** : la moins chère sur le P/B, mais le **bilan se contracte** fortement et le RN 2026 sera nettement inférieur à celui de 2025. Risque de « piège à valeur » tant que la production de crédit ne repart pas. **Rang 13.**

### 5.6 BBGC — Bridge Bank Group Côte d'Ivoire (CI, Principal)
- **Marché** : 8 145 FCFA ; 407 Md ; PER BOC 14,97 ; introduite le **24/09/2026** au prix de 6 750 FCFA (+20,7 % depuis), avec un premier cours de 7 255 FCFA et 4 séances bloquées à la hausse (doc 01) (H).
- **OPV** : 20 % du capital (10 M d'actions) cédés par Bridge Group West Africa ; 67,5 Md offerts (10 M × 6 750, H). La demande de 95,8 Md émanant de 17 544 investisseurs et la date de clôture n'ont pas pu être relues pendant la vérification **[NON VÉRIFIÉ]**. Le doc 01 donne une période d'OPV du 20 au 21/07/2026. Vérifié (avis 285-2026 et BOC) : première cotation le 24/09/2026 à 7 255 FCFA (+7,48 %, borne haute), compartiment Principal, 50 M d'actions, puis borne haute les 25, 28 et 29/09. Au 20/11/2026, le titre compte 42 séances de cotation (41 BOC disponibles et 1 manquant), et non 40.
- **Résultats** : RN S1 2026 de 15,2 Md (+46 %). RN 9M 2026 de **23,8 Md (+41 %)** ; PNB 59,3 Md (+28 %) ; coefficient d'exploitation 41,7 % ; crédits 924 Md (+39 %) ; dépôts 1 294 Md (+40 %) (H). RN 2023-2025 non trouvé dans un document de l'émetteur ; 2025 ≈27,2 Md déduit du BOC (M).
- **Actionnariat** : Bridge Group West Africa ≈80 % après l'OPV (M : 100 % − 20 %).
- **Verdict** : croissance la plus rapide du secteur. Mais historique de cotation très court, aucun dividende encore versé et ratios de solvabilité non publiés dans les documents lus. Une croissance de bilan de +40 % par an consomme du capital. **Rang 11** (en quarantaine IPO, voir §9).

### 5.7 BOAC — Bank of Africa Côte d'Ivoire (CI, Principal)
- **Marché** : 10 995 FCFA ; 440 Md ; PER BOC 12,37 ; rendement 5,43 % ; +53,1 % depuis le 1er janvier ; très liquide (82 M FCFA par séance, spread 0,33 %) (H).
- **Résultats** : PNB 60,8 / 72,7 / 73,5 Md et RN **26,1 / 32,0 / 35,5 Md** (2023/2024/2025). 9M 2026 : PNB 57,8 Md (+8,0 %), RN **29,7 Md (+11,4 %)**, crédits nets 495 Md (**+19,9 %**), dépôts 942 Md (+17,7 %), coefficient d'exploitation 35,7 % (H).
- **Rentabilité** : ROE 2024 ≈30,7 % (M, CP 95,8 → 112,6 Md). ROE 2025 ≈30 % (M, CP 2025 **estimés** à ≈127 Md, car les états financiers 2025 scannés n'ont pas été lus en détail).
- **Dividende** : nets de 315 → **594,53** FCFA (série ajustée 157,5 → 594,5 ; la valeur de 597,53 du BOC est une coquille, voir §4) ; payout ≈67 % en net (M).
- **Vérifié le 22/11/2026 (OCR du rapport T3 2026)** : RN de 29 657 contre 26 632 M (+11,35 %), crédits nets de 495 097 M (+19,94 %), dépôts de 942 180 M (+17,71 %), coût du risque de 3 440 M. Les états financiers 2025 ont été publiés sur brvm.org le **12/06/2026** (rapport des CAC). Leur bilan n'a pas pu être lu par OCR : les CP 2025 restent estimés **[NON VÉRIFIÉ]**.
- **Actionnariat** : **BOA West Africa 69,68 %**, flottant 30,32 % (31/12/2025, page émetteur BRVM) (H).
- **Verdict** : le meilleur équilibre du secteur entre ROE ≈30 %, croissance des crédits à deux chiffres, PER TTM 11,4, rendement 5,4 %, liquidité et pays (CI). **Rang 1.**

### 5.8 SAFC — SAFCA / Alios Finance Côte d'Ivoire (CI, Principal)
- **Marché** : 3 030 FCFA ; 36 Md ; PER BOC 51,31 ; aucun dividende depuis 2011 (H).
- **Résultats** : −579 M (2023), −165 M (2024), **+701 M (2025)**, retour aux bénéfices « après près de huit années de déficit ». 9M 2026 : **1 206 M (+294 %)** ; PNB 4,57 Md (+39 %) ; total bilan +82 % (H).
- **Solidité** : solvabilité 12,11 % (minimum 11,5 %), CET1 11,31 %, levier 4,31 % (H).
- **Événements** : augmentation de capital avec DPS de 3 750 000 actions à **400 FCFA**, soit 1,5 Md (visa n°047/AMF-UMOA/2026), avec un taux de souscription de 100 %. Capital porté de 3,25 à 4,75 Md. Nouvelles actions admises le 11/08/2026. Arrivée de l'actionnaire de référence **CREDAF Group** (H).
- **Verdict** : redressement réel, mais micro-capitalisation, P/B 4,2 et marge de solvabilité très mince. La croissance du bilan exigera de nouvelles levées de fonds. **Rang 17** (spéculatif).

### 5.9 BOAB — Bank of Africa Bénin (BJ, Principal)
- **Marché** : 9 095 FCFA ; 369 Md ; PER BOC 18,35 ; rendement 6,43 %, le plus élevé du secteur ; +55,5 % depuis le 1er janvier (H).
- **Résultats** : RN **21,5 / 19,6 / 20,1 Md** (2023/2024/2025). 9M 2026 : PNB 38,6 Md (+4 %), RN 15,3 Md (**−3 %**) ; crédits −5 % ; dépôts stables à 711 Md (H).
- **Rentabilité** : ROE ≈17,1 % (M ; CP de 117,4 et 117,5 Md).
- **Dividende** : le net de 585 FCFA en 2026 représente ≈23,7 Md, pour un **RN 2025 de 20,1 Md (payout ≈118 %)**. Les réserves ont déjà baissé de 57,2 à 56,8 Md en 2025 (H/M).
- **Actionnariat** : groupe BOA (BOA West Africa et BOA Group). Pourcentages récents non trouvés (la page émetteur date de 2014) ; flottant de 45,9 % (H pour le flottant).
- **Verdict** : PER le plus élevé des BOA, bénéfice stagnant et dividende supérieur au bénéfice. Le rendement de 6,4 % est **fragile**. **Rang 14.**

### 5.10 BICB — BIIC, Banque Internationale pour l'Industrie et le Commerce (BJ, Principal)
- **Marché** : 7 500 FCFA ; 433 Md ; PER BOC 11,95 ; rendement 3,39 % ; +50,8 % depuis le 1er janvier ; cotée depuis le **28/04/2025** (OPV de 33,1 % par l'État béninois à 5 250 FCFA) (H).
- **Résultats (IFRS)** : RN de 29,0 Md (2024 retraité) à **36,2 Md (2025, +24,7 %)** ; PNB 52,8 Md (+16,5 %) ; crédits nets +37,3 %. 9M 2026 : RN **21,2 Md (+64 %)**, marge nette d'intérêts +40 %, coefficient d'exploitation de 41,6 % à 31,7 % (H).
- **Rentabilité et solidité** : ROE publié de 26,8 % (2025). **Solvabilité de 19,64 %**, la plus haute des banques qui publient ce ratio (H).
- **Dividende** : 254,6 FCFA nets en 2025 et en 2026 (payout ≈41 %) (H).
- **Actionnariat** : État du Bénin, actionnaire historique et vendeur lors de l'OPV. Sa part résiduelle exacte n'a pas été lue (B).
- **Points de vigilance** : première adoption des IFRS en 2025 (comparabilité), RN du 4e trimestre très élevé (saisonnalité), crédits/dépôts de 97,5 % (liquidité tendue), dettes interbancaires +41 % (H).
- **Verdict** : croissance forte, PER TTM < 10 et bilan solide. Historique court et dividende stable. **Rang 2.**

### 5.11 BOABF — Bank of Africa Burkina Faso (BF, Principal)
- **Marché** : 7 700 FCFA ; 339 Md ; PER BOC 17,60 ; rendement 5,16 % ; **+105,3 % depuis le 1er janvier** (H).
- **Résultats** : RN **29,1 / 22,4 / 19,3 Md** (2023/2024/2025 ; deux années de baisse : −22,9 % puis −14,1 %). 9M 2026 : PNB 45,7 Md (+5,6 %), RN **18,1 Md (+34,2 %)**, commissions +23,3 % (H).
- **Bilan** : emplois clientèle −19,3 % en 2025 (474 Md), puis +2,2 % sur 9M 2026 ; dépôts 939 Md (H).
- **Rentabilité** : ROE 2025 ≈15,1 % (M), ≈19 % en TTM (M).
- **Dividende** : net de 397 FCFA, en baisse pour la deuxième année consécutive après ajustement (428 → 397). Payout ≈91 % en net (M), soit **≈104 % en brut** si l'IRVM est de 12,5 % (brut ≈454 FCFA) [NON VÉRIFIÉ]. Le dividende pourrait donc dépasser le RN 2025, comme chez BOAB *(ajout du 22/11/2026)*.
- **Actionnariat** : BOA West Africa, majoritaire selon la page émetteur de 2014 (52,38 % à l'époque, B). Flottant de 43,5 %.
- **Verdict** : le rebond 2026 est réel, mais le cours a déjà doublé en 2026 et l'historique 2023-2025 est mauvais. **Rang 12.**

### 5.12 CBIBF — Coris Bank International (BF, Principal)
- **Marché** : 27 505 FCFA ; 880 Md ; PER BOC 13,44 ; rendement 3,27 % ; **+155,2 % depuis le 1er janvier**, la plus forte hausse du secteur (H).
- **Résultats** : RN **64,2 / 47,9 / 65,5 Md** (2023/2024/2025). En 2024, le CoR a grimpé à 40,5 Md (+72 %), puis est retombé à 16,5 Md en 2025 (−59 %). S1 2026 : RN 41,7 Md (+23,5 %). 9M 2026 : PNB 116,4 Md (+14,9 %), RN **62,3 Md (+17,8 %)**, crédits 1 386 Md (+15,2 %), dépôts 2 372 Md (+26,4 %). Contribution de la succursale du Niger au RN 2025 : 2,08 Md (H).
- **Rentabilité** : ROE **n.d.** (capitaux propres non trouvés dans les rapports lus ; états financiers 2025 scannés de 13 Mo non exploités).
- **Dividende** : 406 → 900 FCFA nets (payout ≈44 %) (H/M).
- **Actionnariat** : non vérifié pendant cette session (la page émetteur BRVM est mal formatée) (**à compléter**).
- **Verdict** : beaux résultats et payout prudent, mais le cours a été multiplié par 2,5 en un an. Exposition au Burkina Faso et au Niger. **Rang 8.**

### 5.13 BOAM — Bank of Africa Mali (ML, Principal)
- **Marché** : 5 100 FCFA ; 140 Md ; PER BOC 12,63 ; rendement 5,98 % ; spread le plus serré du secteur (0,21 %) (H).
- **Résultats** : RN **5,8 / 9,1 / 11,1 Md** (2023/2024/2025). S1 2026 : PNB 22,0 Md (+17,5 %), RBE +29,4 %, RN 6,7 Md (+8,2 %). Aucun rapport T3 2026 en ligne au 22/11/2026 (H).
- **Rentabilité** : ROE 2025 ≈23,1 % (M ; CP 46,2 → 49,8 Md).
- **Dividende** : aucun de 2020 à 2023 (augmentation de capital avec DPS en 2021), puis 144 → 237,15 → 305,04 FCFA nets ; payout ≈76 % (H/M).
- **Actionnariat** : **BOA West Africa 64,18 %** au 31/12/2025 (page émetteur) (H).
- **Verdict** : bons chiffres et valorisation raisonnable, mais **risque pays Mali** (instabilité politique et sécuritaire, voir doc 05) et petite capitalisation. **Rang 4**, avec une pondération pays réduite.

### 5.14 BOAN — Bank of Africa Niger (NE, Principal)
- **Marché** : 4 420 FCFA ; 92 Md ; PER BOC 224,63 (sur le RN 2025 effondré) ; +69,4 % depuis le 1er janvier (H).
- **Résultats** : RN **10,1 / 5,0 / 0,4 Md** (2023/2024/2025 : −50 % puis −92 %). Alertes sur résultats les 18/12/2025 et 20/02/2026. Crédits −20,9 % en 2025. 9M 2026 : RN **6,3 Md (+122 %)**, coefficient d'exploitation de 63,4 % à 54,2 %, CoR −23 % (H).
- **Rentabilité et solidité** : ROE de 11,4 % (2024), 1,0 % (2025), **16,0 %** (T1 2026). Solvabilité 15,4 % → 14,1 % → 17,4 % (H).
- **Dividende** : **aucun dividende au titre de 2025** (communiqué de presse du 27/04/2026). Le rendement BOC de 4,73 % est donc trompeur (H).
- **Actionnariat** : BOA West Africa 59,06 %, SONIMEX 5,73 %, flottant 35,21 % (31/12/2025, page émetteur) (H). L'avis BRVM 303 retient un flottant de 40,94 %, qui inclut SONIMEX.
- **Publication** *(ajout du 22/11/2026)* : l'alerte sur résultats du conseil du 20/02/2026 n'a été mise en ligne sur brvm.org que le 18/03/2026 à 09:06 UTC. Dans un backtest, l'événement date du **18/03**, pas du 20/02.
- **Verdict** : pari de redressement (PER ≈11 sur le 9M 2026 annualisé). Mais le système bancaire nigérien est très dégradé (28,6 % de NPL sectoriel) et le cours a déjà rebondi de 69 %. **Rang 15.**

### 5.15 BOAS — Bank of Africa Sénégal (SN, Principal)
- **Marché** : 7 700 FCFA ; 277 Md ; PER BOC 12,65 ; rendement 5,84 % ; liquide (46 M FCFA par séance, spread 0,27 %) (H).
- **Résultats** : RN **17,0 / 20,0 / 21,9 Md** (2023/2024/2025). 9M 2026 : PNB 41,1 Md (+9,9 %), RN **18,2 Md (+11,0 %)**, ressources +11,7 %, emplois −3,4 % (H).
- **Rentabilité** : ROE 2025 ≈23,7 % (M ; CP 88,6 → 96,5 Md).
- **Dividende** : 187,5 → 300 → 350 → 450 FCFA nets (450 = +29 % en 2026) ; payout ≈74 % (H/M).
- **Actionnariat** : BOA West Africa, majoritaire (61,52 % en 2014, page ancienne, B). Flottant de 38,3 %.
- **Verdict** : croissance régulière, bon dividende et PER raisonnable. Principal risque : le **souverain sénégalais** (titres publics au bilan, obligations sous le pair). **Rang 3.**

### 5.16 ETIT — Ecobank Transnational Incorporated (TG, Principal)
- **Marché** : 57 FCFA ; capitalisation BRVM de 1 031 Md (sur 18,08 milliards de titres) ; PER BOC 2,98, **non fiable** ; PER sur le BPA IFRS : 57 / 10,00 = **5,7** (TTM ≈5,3) ; rendement 1,61 % ; +147,8 % depuis le 1er janvier (H/M).
- **Résultats (IFRS, groupe)** : RN part du groupe de **287,8 M$ (2023), 333,2 M$ (2024) et 407,1 M$ (2025)**. RN consolidé de 594 M$ en 2025, bénéfice avant impôt de 801 M$ (+21 %), coefficient d'exploitation 48,3 %, ROTE 27,8 %. 9M 2026 : PNB 1 962 M$ (+12 %), bénéfice avant impôt 737 M$ (+12 %), RN part du groupe 364 M$ (+17 %), ROTE 24,9 % (H).
- **Qualité des actifs** : créances douteuses 9,4 % (12/2025) → **7,5 %** (09/2026) ; CoR 287 M$ sur 9M (H). Cession des activités au Mozambique annoncée (H).
- **Dividende** : 40 M$ (0,16 cent US par action) au titre de 2025, soit 0,9184 FCFA nets payés le 30/06/2026. Aucun dividende payé en 2024 ni en 2025 (H).
- **Gouvernance — événement majeur** : AGE du 13/08/2026 (quorum des AG porté à 25 % du capital, conseil plafonné à 12 membres, suppression de la limite de mandats des administrateurs non exécutifs). Puis **annulation de l'AGO du 26/10/2026 « conformément aux instructions de la Commission Bancaire de l'UMOA »** pour « consultations supplémentaires » (H). L'objet du différend n'est pas public dans les documents lus.
- **Verdict** : de loin la moins chère (PER ≈5, P/B ≈1,2) avec une rentabilité en hausse. Mais le différend avec le superviseur, le dividende symbolique, l'exposition aux devises (Nigeria, Ghana, etc.) et un spread de 3 % justifient une forte décote. **Rang 6** : poche « valeur / événement », pas un cœur de portefeuille.

### 5.17 ORGT — Oragroup (TG, Principal)
- **Marché** : 2 500 FCFA ; 175 Md ; PER BOC 8,02 (sur le RN total) ; PER part du groupe ≈9,5 (BPA de base) ou ≈10,4 (BPA dilué) ; aucun dividende depuis 2020 (H/M).
- **Résultats (IFRS consolidé)** : RN total **−18,2 Md (2023 ; part du groupe −19,5), −44,4 Md (2024 ; part du groupe −37,9), +21,6 Md (2025 ; part du groupe 18,36 Md ; BPA de base 264, BPA dilué 241 FCFA)** *(corrigé le 22/11/2026)*. 9M 2026 : PNB 165,0 Md (+8 %), RN **21,7 Md (+14 %)**, crédits nets −9 % depuis décembre, dépôts +11 % (H).
- **Solidité** : capitaux propres part du groupe de 94,4 Md (2023) à **54,8 Md (2024)** puis 69,5 Md (2025) pour un bilan de 4 014 Md. La base de fonds propres est **très mince** au regard du bilan (H).
- **Actionnariat et événements** : ECP Financial Holding (EFH) est l'actionnaire majoritaire. Les cessions à Vista (02/08/2023, puis 30/09/2024) ont été annulées : Vista s'est retiré le 13/05/2025. Le 19/05/2025, le conseil a validé un **plan alternatif avec les actionnaires institutionnels, dont la BOAD**, avec une première tranche de **80 Md FCFA d'augmentation de capital** (H). L'exécution de ce plan à fin 2026 n'a pas pu être vérifiée.
- **Verdict** : redressement en cours, mais une **dilution importante est probable** (80 Md à lever face à une capitalisation de 175 Md) et le dividende reste absent. **Rang 16.**

---

## 6. Données manquantes ou non vérifiées (liste explicite)

| Donnée | Sociétés concernées | Raison |
|---|---|---|
| Ratio de solvabilité | SIBC (seulement « > 14 % »), ECOC, BICC, NSBC, BOAB, BOABF, BOAC, BOAM, BOAS, CBIBF, ETIT, ORGT, BBGC | ratio absent des rapports lus ; non recherché dans les états financiers scannés |
| Taux de NPL | SIBC, BICC, NSBC, BOA (sauf contexte Niger), CBIBF, BBGC, BICB (seulement la couverture ECL) | non publié dans les rapports lus |
| Capitaux propres | CBIBF, BBGC ; BOAC 2025 (estimé) ; BOAN (déduit du ROE) | documents scannés volumineux non exploités |
| RN 2023-2025 | BBGC (2025 déduit du PER BOC), BICB 2023 | note d'information de l'OPV non lue ; BICB passé en IFRS en 2025 |
| Actionnariat à jour | SIBC, CBIBF, ECOC (%), BOAB, BOABF, BOAS (pages émetteurs de 2014), BICB (part résiduelle de l'État) | pages émetteurs BRVM non mises à jour ; aucune source secondaire disponible (quota web épuisé, réseau limité) |
| Changements de direction 2025-2026 | toutes | aucun communiqué de changement de direction trouvé pour 2025-2026 dans la liste des communiqués BRVM. Les noms de DG des pages émetteurs peuvent être anciens |
| Sanctions réglementaires | toutes | aucune sanction AMF-UMOA ou Commission Bancaire trouvée dans les documents lus (le site de l'AMF-UMOA n'a pas pu être consulté) |
| Objet du différend ETI – Commission Bancaire | ETIT | non public dans les documents lus |
| Exécution de la recapitalisation d'Oragroup | ORGT | non trouvé |

---

## 7. Classement par attractivité (qualité × valeur × croissance)

### 7.1 Méthode (reproductible, à recoder dans `brvm_alpha`)
- **Qualité (Q)** = moyenne de trois éléments : rang centile du ROE 2025 ; note de qualité d'actifs (1 = pas d'alerte, 0,5 = surveillance, 0 = dégradation) ; stabilité (1 si RN > 0 en 2023, 2024 et 2025, 0,5 si l'historique est incomplet, 0 sinon).
- **Valeur (V)** = moyenne de trois rangs centiles : E/P TTM (élevé = mieux), rendement net (élevé = mieux) et P/B (bas = mieux).
- **Croissance (G)** = moyenne des rangs centiles de la variation du RN 9M 2026 (bornée entre −50 % et +60 %) et du TCAM du RN 2023→2025.
- Une donnée manquante reçoit le rang 0,4 : c'est une pénalité volontaire, l'opacité étant un risque.
- **Score** = (Q × V × G)^(1/3), soit une moyenne géométrique : une seule dimension faible pénalise le score.
- **Ajustement qualitatif final** (voir les justifications) : risque pays, gouvernance, liquidité, historique de cotation, soutenabilité du dividende.
- *(Note de vérification du 22/11/2026)* Cet ajustement **n'est pas codifié**. Il fait passer ETIT du 2e au 6e rang et BICB du 4e au 2e, ce qui ne se reproduit pas à partir des scores bruts. Dans le code, seul le score brut multiplié par les coefficients de §9.3-§9.4 doit servir. Le classement final est un avis d'analyste, pas un résultat du modèle. Les poids, le rang de 0,4 pour une donnée manquante et le plancher de ROE sont des **choix de conception** : aucune étude ne les étaye et aucun backtest ne les a validés.

### 7.2 Scores bruts calculés (M)

| Symb. | Q | V | G | Score brut |
|---|---:|---:|---:|---:|
| BOAC | 0,97 | 0,62 | 0,66 | **0,736** |
| ETIT | 0,76 | 0,77 | 0,65 | 0,722 |
| BOAM | 0,65 | 0,69 | 0,64 | 0,660 |
| BICB | 0,71 | 0,59 | 0,67 | 0,652 |
| BICC | 1,00 | 0,32 | 0,82 | 0,639 |
| BOAS | 0,68 | 0,69 | 0,51 | 0,621 |
| CBIBF | 0,63 | 0,47 | 0,51 | 0,531 |
| BBGC | 0,63 | 0,38 | 0,61 | 0,527 |
| ECOC | 0,78 | 0,44 | 0,41 | 0,519 |
| SIBC | 0,90 | 0,36 | 0,42 | 0,513 |
| BOABF | 0,55 | 0,52 | 0,46 | 0,508 |
| SGBC | 0,63 | 0,72 | 0,28 | 0,502 |
| NSBC | 0,60 | 0,76 | 0,26 | 0,493 |
| BOAB | 0,74 | 0,53 | 0,23 | 0,450 |
| BOAN | 0,36 | 0,36 | 0,51 | 0,403 |
| ORGT | 0,13 | 0,61 | 0,49 | 0,342 |
| SAFC | 0,30 | 0,13 | 0,67 | 0,299 |

### 7.3 Classement final justifié

| Rang | Symb. | Catégorie | Justification (résumé) | Principaux risques |
|---:|---|---|---|---|
| 1 | **BOAC** | Cœur | ROE ≈30 %, RN +11 % sur 9M 2026, crédits +20 %, PER TTM 11,4, rendement 5,4 %, très liquide, pays CI | P/B ≈3,5 ; CP 2025 estimés |
| 2 | **BICB** | Cœur (taille limitée) | RN +64 % sur 9M 2026, PER TTM 9,8, ROE 26,8 %, solvabilité 19,6 % | historique de cotation et IFRS récents ; dividende stable (3,4 %) ; crédits/dépôts 97 % |
| 3 | **BOAS** | Cœur | RN +11 % sur 9M, ROE ≈24 %, PER 11,7, dividende +29 % | souverain sénégalais |
| 4 | **BOAM** | Satellite | ROE ≈23 %, PER 12, rendement 6 %, RN en hausse | risque pays Mali ; petite capitalisation ; T3 2026 non publié |
| 5 | **BICC** | Cœur (taille limitée) | ROE ≈33 %, RN +15 % sur 9M, TCAM 2023-2025 de +48 % | croissance tirée par les titres et non par le crédit ; P/B 4,3 ; liquidité 14 M FCFA par séance |
| 6 | **ETIT** | Poche valeur / événement | PER ≈5, P/B ≈1,2, ROTE 25-28 %, NPL en baisse | différend avec la Commission Bancaire ; dividende 1,6 % ; devises ; spread 3 % |
| 7 | **SGBC** | Défensif / rendement | leader, rendement 5,9 %, PER 12, solvabilité 17,6 % | croissance nulle ou négative ; NPL à 8 % ; payout déjà à 80 % |
| 8 | **CBIBF** | Satellite | RN +18 % sur 9M, payout 44 % (marge de hausse du dividende) | +155 % depuis le 1er janvier ; Burkina et Niger ; ROE non vérifié |
| 9 | **SIBC** | Qualité chère | ROE 27 %, croissance régulière | P/B 4,0 ; PER 14 |
| 10 | **ECOC** | À surveiller | ROE 25-29 %, dividende 5,3 % | RN −12 % sur 9M ; NPL +28 % ; CoR ×11 |
| 11 | **BBGC** | Quarantaine IPO | croissance +40 % | introduite il y a 42 séances ; pas de dividende ; solvabilité inconnue |
| 12 | **BOABF** | Rebond déjà payé | RN +34 % sur 9M | cours ×2 depuis le 1er janvier ; RN 2023-2025 en baisse ; payout de 91 % en net, ≈104 % en brut [IRVM NON VÉRIFIÉ] |
| 13 | **NSBC** | Piège à valeur possible | P/B 1,6, PER 10,9 | RN −27 % ; bilan −6 % ; crédits −19 % |
| 14 | **BOAB** | Dividende fragile | rendement 6,4 % | payout ≈118 % ; RN stagnant ; PER 19 |
| 15 | **BOAN** | Spéculatif (redressement) | RN +122 % sur 9M ; ROE du T1 2026 à 16 % | Niger (28,6 % de NPL sectoriel) ; aucun dividende 2025 |
| 16 | **ORGT** | Spéculatif | retour aux bénéfices | fonds propres minces ; dilution probable (80 Md) ; pas de dividende |
| 17 | **SAFC** | Spéculatif / illiquide | redressement réel | micro-capitalisation ; P/B 4,2 ; solvabilité 12,1 % pour un minimum de 11,5 % |

**Ce que ce classement ne dit pas** : il ne dit pas quel titre montera le plus. Les titres les mieux classés sur la croissance (CBIBF, BOABF, BICB, BOAN) ont déjà fortement monté en 2026. La documentation académique sur les marchés frontières (docs 02 et 03) n'établit pas de prime « qualité » ou « valeur » robuste et propre à la BRVM. Ce score doit donc être **validé en backtest point-in-time** avant de servir à prendre des positions.

---

## 8. Anomalies de données à traiter dans le code

| # | Anomalie | Traitement recommandé | Conf. |
|---|---|---|---|
| 1 | PER BOC d'ETIT (2,98) et d'ORGT (8,02) calculés sur le RN consolidé **total** (vérifié pour ETIT : 345 523 M / 18,084 Md de titres = 19,1 FCFA) | recalculer le PER sur le BPA part du groupe publié : ETIT 10,00 FCFA (de base = dilué) ; ORGT **264 de base / 241 dilué**. Choisir une convention unique (de base par défaut) | H |
| 2 | Nombre d'actions ETI : 18,08 milliards selon la BRVM, contre ≈23,7 milliards impliqués par le BPA et ≈25 milliards par le dividende (40 M$ / 0,0016 $) | utiliser le BPA publié pour le PER, et le nombre BRVM pour les poids d'indice. Question ouverte | M |
| 3 | Rendement BOC périmé quand aucun dividende n'est voté (BOAN 2026, ORGT, SAFC) | rendement « attendu » = dernier dividende voté pour l'exercice N−1, mis à 0 si l'émetteur annonce une absence de dividende | H |
| 4 | PER BOC de BOAN (224,6) sur un RN 2025 exceptionnellement bas | utiliser le PER TTM et signaler les variations de RN > ±50 % | H |
| 5 | Attributions gratuites BOA et SIB de 2024 (ratios 1:1, 1:2, 3:5) | ajuster les dividendes et les cours historiques (facteurs §4 ; doc 01, §8.2) | H |
| 6 | DPS SAFC d'avril 2026 (émission à 400 FCFA, valeur du DPS 1 615 FCFA) | ajuster la série de cours (facteur = réf. ex / (réf. ex + DPS)) ; la variation BOC depuis le 1er janvier (−8,3 %) n'est **pas** ajustée | H |
| 7 | Date erronée dans le BOC (ECOC, dividende 549 daté « 30-mai-22 » en 2023) | dédupliquer par montant, en gardant la première séance d'apparition | H |
| 8 | BOAC : dividende de 597,53 (BOC) contre 594,528 (calendrier) | *(corrigé le 22/11/2026)* utiliser **594,528**, la valeur effectivement appliquée par la BRVM à la référence ex du 04/05/2026 (9 435 → 8 845). Règle générale : lire le dividende sur la ligne « (d) » (dernière séance avec dividende), et non sur les BOC suivants | H |
| 9 | PDF scannés (BOA, Coris, Oragroup) : pdftotext renvoie 0 caractère | prévoir une OCR ou une saisie manuelle contrôlée ; vérifier la cohérence (RN 9M ≤ RN annuel, etc.) | H |
| 10 | Texte parasite dans un PDF SIB (« Bonsoir M.KADER ») | contrôles de cohérence numérique, sans faire confiance à la seule mise en page | H |
| 11 | Flottant officiel de BICC (32,51 %) : il exclut seulement le bloc du consortium (5 418 860 = 16 666 670 − 11 247 810), et pas les 19,11 % de Brandon & McAin *(expliqué le 22/11/2026)* | le flottant BRVM n'est pas un flottant économique : ne pas l'utiliser seul pour la liquidité ou la pondération | H |
| 12 | Préfixe AAAAMMJJ du nom de fichier ≠ heure de mise en ligne (*ajout du 22/11/2026*). Sur les 79 PDF cités, d'après l'en-tête `Last-Modified` : 59 sont en ligne avant la séance J+1, 18 pendant ou après cette séance (ECOC T3 à 12:03, Coris T3 à 17:29, ETI 2025 à 11:59, etc.), 1 à J+4 (alerte BOAN) et 1 porte un préfixe erroné (n°13) | rendre la donnée disponible à la **première séance dont la pré-ouverture (09:00 UTC) suit le `Last-Modified`**, et au plus tôt à J+1. À défaut d'en-tête, utiliser J+2 | H |
| 13 | Préfixe erroné : `20260703_-_rapport_dactivites_-_4e_trimestre_2024_-_safca_ci.pdf` a un `Last-Modified` du **03/07/2025**, soit un préfixe décalé d'un an | si `Last-Modified` < préfixe − 30 jours, prendre `Last-Modified` et signaler l'anomalie | H |

---

## 9. Implications pour la plate-forme (paramètres prêts à coder)

### 9.1 Données fondamentales point-in-time

Un chiffre fondamental n'est utilisable qu'**à partir de la séance qui suit sa publication sur brvm.org**. *(Corrigé le 22/11/2026)* Le préfixe AAAAMMJJ du nom de fichier n'est **pas** l'heure de mise en ligne : c'est une date de document ou de réception. L'en-tête HTTP `Last-Modified` (simple requête HEAD) montre que 18 des 79 PDF cités sont arrivés pendant ou après la séance J+1, et un à J+4. La règle « J+1 » introduirait donc un biais d'anticipation sur ≈24 % des publications. Il faut utiliser `Last-Modified` quand il est disponible, sinon J+2. Ce chiffre de `Last-Modified` est un majorant de la première mise en ligne (un fichier remplacé garde la date du remplacement), donc la règle reste prudente. Délais observés pour les publications de 2026 (H) :

| Publication | Plus précoce | Plus tardive | Exemples |
|---|---|---|---|
| Comptes annuels 2025 (premier chiffre de RN) | 17/03 (BOAS) | 19/06 (BICB) ; 07/07 (états financiers Coris) | SGBC 16/04 ; ECOC 14/04 ; NSBC 13/05 |
| T1 2026 | 22/04 (BOAS) | 22/07 (BICB) | BOAM 23/06 |
| S1 2026 | 23/07 (BOAB) | 23/10 (NSBC) | BOAC 01/10 ; BBGC 24/09 |
| T3 2026 | 21/10 (BOAS) | 12/11 (ORGT) | BOAM non publié au 22/11 |

```yaml
fundamentals:
  source: brvm.org/fr/rapports-societe-cotes/<slug>   # liste des PDF par émetteur
  # (corrigé le 22/11/2026) J+1 réfuté : 18/79 PDF en ligne pendant ou après la séance J+1, 1 à J+4
  availability_rule: "first_session_with_preopen_after(max(prefix_date+1 session, http_last_modified))"
  preopen_utc: "09:00"
  availability_lag_sessions_fallback: 2   # si pas d'en-tête Last-Modified : J+2 après la date du nom de fichier
  prefix_sanity_check_days: 30            # si Last-Modified < préfixe - 30 j, le préfixe est faux (SAFCA T4 2024)
  event_date: publication_on_brvm         # ex. alerte BOAN : 18/03/2026, et non la date du conseil (20/02/2026)
  stale_after_days: 200               # donnée trimestrielle considérée comme périmée au-delà
  ttm_rule: "RN_FY(N-1) + RN_YTD(N) - RN_YTD(N-1)"
  unaudited_flag: true                # T1/T3 non audités : poids réduit
  slugs:
    SGBC: sgci
    SIBC: sib
    ECOC: ecobank-ci
    BICC: bici-ci
    NSBC: nsbc
    BBGC: bbgci
    BOAC: bank-africa-ci
    SAFC: safca-ci
    BOAB: bank-africa-bn
    BICB: biic
    BOABF: bank-africa-bf
    CBIBF: coris-bank-international
    BOAM: bank-africa-ml
    BOAN: bank-africa-ng
    BOAS: bank-africa-sn
    ETIT: ecobank-tg
    ORGT: oragroup
  eps_override:   # BPA à utiliser à la place du BOC
    ETIT: {basis: "group_share_ifrs", eps_fy2025_fcfa: 10.00}
    ORGT: {basis: "group_share_ifrs", eps_basic_fy2025_fcfa: 264, eps_diluted_fy2025_fcfa: 241, ni_group_fy2025_mfcfa: 18355}  # corrigé le 22/11/2026
  ocr_required: [BOAB, BOABF, BOAC, BOAM, BOAN, BOAS, CBIBF, ORGT]
```

### 9.2 Score qualité × valeur × croissance pour les financières

```yaml
fin_score:
  universe: sector == "FIN"            # 17 titres au 20/11/2026
  quality:
    roe_rank_weight: 1/3
    asset_quality_weight: 1/3          # 1 OK, 0.5 surveillance, 0 dégradation
    stability_weight: 1/3              # RN > 0 sur 3 exercices
    roe_floor_pct: 12                  # ROE < 12 % : qualité plafonnée à 0.3
  value:
    metrics: [earnings_yield_ttm, net_dividend_yield, -price_to_book]
    weights: [0.4, 0.3, 0.3]
  growth:
    metrics: [ni_ytd_yoy_clipped, ni_cagr_3y]
    clip_pct: [-50, 60]
    weights: [0.6, 0.4]
  missing_rank: 0.4                    # pénalité de l'opacité
  combine: geometric_mean              # (Q*V*G)^(1/3)
  rebalance: after_each_reporting_wave # fin avril, fin juillet/sept., début novembre
```

### 9.3 Signaux d'alerte (drapeaux binaires, seuils chiffrés)

```yaml
# Tous les seuils ci-dessous sont des CHOIX DE CONCEPTION calibrés sur 1 ou 2 exemples (risque de surajustement).
# Ils n'ont été validés par aucune étude ni aucun backtest (vérification du 22/11/2026).
red_flags:
  payout_gross_gt: 1.00          # corrigé le 22/11/2026 : brut = net / (1 - IRVM du pays) ; BOAB ≈1.31 ; BOABF ≈1.04 [IRVM BF NON VÉRIFIÉ]
  payout_net_gt: 1.00            # repli si l'IRVM est inconnu ; BOAB ≈1.18 (BOABF 0.91 n'est alors pas détecté)
  ni_ytd_drop_lt_pct: -15        # NSBC -27 %, ECOC -12.3 % (orange à -10 %), vérifiés sur les rapports T3 2026
  cost_of_risk_multiple_gt: 3.0  # ECOC 9M 2026 : 8.079 / 0.702 Md = 11.5x
  cost_of_risk_min_base_pct_loans: 0.25  # garde-fou : multiple ignoré si le CoR N-1 < 0.25 % des crédits ou en reprise nette (BICC, SAFC)
  npl_ratio_ge_pct: 8.0          # ">=" (et non ">") pour que SGBC (8.0 % en 2025) soit bien détecté ;
                                 # les définitions de NPL diffèrent (brut PCB, IFRS stage 3, ETI) : ne comparer que des séries homogènes
  npl_growth_yoy_gt_pct: 25      # ECOC +28 %
  solvency_buffer_lt_pp: 2.0     # solvabilité - 11.5 % < 2 pp -> SAFC (0.6 pp)
  loans_yoy_lt_pct: -15          # NSBC -19 %, BOABF -19 % (2025), BOAN -21 %
  profit_warning_window_days: 120  # après une « alerte sur résultats » (BOAN 12/2025, 02/2026), compté à partir de la mise en ligne sur brvm.org (18/03/2026 pour celle du 20/02)
  regulator_intervention: true   # ETI : AGO annulée sur instruction de la Commission Bancaire (23/10/2026)
  no_dividend_years_ge: 3        # ORGT (depuis 2020), SAFC (depuis 2011)
  pending_dilution: true         # ORGT : plan de 80 Md ; SAFC : besoins futurs
action_on_flag:
  max_weight_multiplier: 0.5     # un drapeau : poids max divisé par 2
  two_or_more_flags: exclude
```

### 9.4 Risque pays, IPO et liquidité

```yaml
country_risk_multiplier:   # appliqué au poids maximum, cohérent avec le doc 05 ; JUGEMENT, aucune source chiffrée [NON VÉRIFIÉ]
  CI: 1.0
  BJ: 1.0
  SN: 0.85       # dette souveraine, obligations sous le pair
  TG: 0.9
  BF: 0.75
  ML: 0.7
  NE: 0.6        # NPL sectoriel 28.6 % (11/2025)
ipo_quarantine_sessions: 60      # choix de conception (sans base empirique) ; BBGC : 42 séances au 20/11/2026 -> éligible vers le 16/12/2026 si aucun jour férié
liquidity:
  min_median_value_per_session_fcfa: 10_000_000    # exclut aucun FIN actuel ; BICC (13.6 M) et ORGT (11.6 M) sont à la limite
  max_participation_of_median_value: 0.10
  max_spread_pct: 1.5                               # ETIT (2.99 %) -> taille réduite
single_name_cap_pct: 10
sector_cap_pct: 45               # le secteur FIN pèse lourd dans les indices ; éviter la surconcentration
```

### 9.5 Dividendes (calendrier et ajustements)

```yaml
dividends:
  # corrigé le 22/11/2026 : lire le montant sur la ligne "(d)" du BOC (dernière séance avec dividende) ;
  # la colonne des BOC suivants peut être fausse (BOAC : 597.53 au lieu de 594.53 appliqué)
  source_priority: [boc_d_line_div, avis_paiement, brvm_calendar_pdf, boc_last_div]
  ci_gross_to_net:                 # calendrier 2025 : sociétés ivoiriennes publiées en brut
    natural_person: 0.88           # IRVM 12 % (vérifié : ECOC, BICC, SIBC, NSBC, ORAC, SLBC)
    legal_person: 0.90             # IRVM 10 %
    use_published_net_first: true  # exception SGBC 2026 : 2298.75 publié et appliqué, contre 2606 x 0.88 = 2293.28
  ex_date_rule: "payment_date - 1 business day"   # vérifié : 1re séance ex = colonne "Ex-dividende" du calendrier (SGBC 21/08, BOAC 05/05, ECOC 22/05)
  boc_flag_day: "ex_date - 1 session"             # ligne "(d)" : dernière séance avec dividende ; la colonne "Cours Référence" y donne déjà la référence ex
  ex_reference_rounding: "ceil_to_tick(close_cum - net_div)"   # 7/7 cas en 2026 pour un pas de 5 FCFA ; ETIT (pas de 1) : 37 - 0.92 -> 36
  bonus_reference_rounding: "floor_to_tick(close_cum * factor)" # BOAM 2020*2/3 -> 1345 ; BOAS 4690*2/3 -> 3125 ; BOAN 5220*0.625 -> 3260
  fin_season_window: ["04-15", "08-31"]           # 23/04 (BOABF) -> 24/08 (SGBC) en 2026
  bonus_adjustment_factors_2024:   # facteur multiplicatif des dividendes et cours antérieurs ; ratios et dates ex VÉRIFIÉS sur les BOC 2024 (référence ex / clôture veille)
    BOAM: 0.6667   # 1:2, ex le 28/08/2024
    BOABF: 0.5     # 1:1, ex le 28/08/2024
    BOAS: 0.6667   # 1:2, ex le 29/08/2024
    BOAB: 0.5      # 1:1, ex le 03/09/2024
    BOAN: 0.625    # 3:5, ex le 04/09/2024
    BOAC: 0.5      # 1:1, ex le 25/10/2024
    SIBC: 0.5      # 1:1, ex le 14/11/2024
  rights_issue_2026:
    SAFC: {ex_date: "2026-04-24", ref_ex: 3890, dps_value: 1615, factor: 0.7066}  # vérifié : BOC 23/04/2026, clôture 5 505 -> référence 3 890 ; 3,75 M actions nouvelles à 400 pour 8 119 750 anciennes
```

### 9.6 Valeurs de référence au 20/11/2026 (pour les tests unitaires)

```python
FIN_SNAPSHOT_20261120 = {
 # sym: (cours, nb_titres, rn_2025_md, rn_ttm_md, roe_2025, dps_net_2026, yoy_ni_ytd)
 "SGBC": (38795, 31_111_110, 101.35, 98.5, 0.214, 2298.75, -0.035),
 "SIBC": (8200, 100_000_000, 55.6, 58.3, 0.272, 374.0, 0.06),
 "ECOC": (14795, 55_050_600, 63.48, 58.0, 0.290, 781.44, -0.123),
 "BICC": (31000, 16_666_670, 36.52, 40.6, 0.331, 1157.20, 0.147),
 "NSBC": (15000, 24_734_572, 40.71, 34.1, 0.183, 675.98, -0.27),
 "BBGC": (8145, 50_000_000, None, None, None, None, 0.41),
 "BOAC": (10995, 40_000_000, 35.54, 38.6, None, 594.53, 0.114),   # corrigé le 22/11/2026 (597.53 = coquille du BOC)
 "SAFC": (3030, 11_869_750, 0.701, 1.6, None, 0.0, 2.94),
 "BOAB": (9095, 40_561_048, 20.11, 19.6, 0.171, 585.0, -0.03),
 "BICB": (7500, 57_759_800, 36.2, 44.4, 0.268, 254.6, 0.636),
 "BOABF": (7700, 44_000_000, 19.25, 23.9, 0.151, 397.0, 0.342),
 "CBIBF": (27505, 32_000_000, 65.50, 74.9, None, 900.0, 0.178),
 "BOAM": (5100, 27_450_000, 11.08, 11.6, 0.231, 305.04, 0.082),   # S1
 "BOAN": (4420, 20_800_000, 0.41, 3.9, 0.010, 0.0, 1.219),
 "BOAS": (7700, 36_000_000, 21.91, 23.7, 0.237, 450.0, 0.110),
 "ETIT": (57, 18_084_106_722, None, None, None, 0.9184, 0.17),     # IFRS, part du groupe en USD
 "ORGT": (2500, 69_986_131, None, None, None, 0.0, 0.14),        # RN part du groupe 2025 = 18.355 Md ; BPA 264 (de base) / 241 (dilué)
}
# Tests suggérés : PER TTM SGBC ≈ 12.3 ; P/B NSBC ≈ 1.59 ; payout BOAB > 1 -> drapeau ;
# rendement attendu BOAN = 0 (et non 4.73 %) ; PER ETIT recalculé ≈ 5.7.
# Tests ajoutés le 22/11/2026 : référence ex BOAC 04/05/2026 = ceil5(9435 - 594.53) = 8845 ;
# SGBC 20/08/2026 = ceil5(40000 - 2298.75) = 37705 ; payout brut BOABF > 1 si IRVM BF = 12.5 % ;
# PER ORGT de base = 2500/264 ≈ 9.5 ; flottant BICC = (16_666_670 - 11_247_810) / 16_666_670 = 0.3251.
```

---

## 10. Questions ouvertes

1. **ETI** : quel est l'objet des « consultations » exigées par la Commission Bancaire, et quand une nouvelle AGO sera-t-elle convoquée ? Quel est le nombre exact d'actions en circulation (18,08 milliards selon la BRVM, contre ≈23,7-25 milliards implicites) ? Pourquoi les capitaux propres part du groupe ont-ils bondi de 1 079 à 1 931 M$ en 2025 ?
2. **Oragroup** : la tranche de 80 Md d'augmentation de capital (plan BOAD du 19/05/2025) a-t-elle été réalisée, à quel prix et avec quelle dilution ?
3. ~~**BICC** : comment le flottant de 32,5 % se concilie-t-il avec les blocs de 67,49 % et 19,11 % ?~~ **Résolu le 22/11/2026** : la BRVM n'exclut que le bloc du consortium (5 418 860 = 16 666 670 − 11 247 810). Reste à savoir si Brandon & McAin détient toujours ses 19,11 % en 2026 [NON VÉRIFIÉ].
4. Ratios de solvabilité et taux de NPL 2025 de la plupart des banques : à extraire des états financiers annuels complets (souvent scannés), ou des publications de la Commission Bancaire.
5. Actionnariats à jour de SIBC, CBIBF, ECOC, BOAB, BOABF, BOAS et BICB.
6. RN 2023-2025 et ratios prudentiels de Bridge Bank (note d'information de l'OPV visée par l'AMF-UMOA).
7. L'échéance de fin 2026 pour le capital minimum de 20 Md entraînera-t-elle d'autres opérations (attributions gratuites, augmentations de capital) chez les plus petites banques ? Capital actuel : BOAN 20,8 Md, BOAM 27,45 Md, SAFC 4,75 Md (établissement financier, donc seuil à vérifier).
8. *(Ajout du 22/11/2026)* IRVM du Burkina Faso et du Togo, et éventuelle surcharge de solvabilité pour les banques systémiques : ces deux points décident si BOABF déclenche le drapeau « payout brut > 1 » et quel minimum de solvabilité retenir pour les grandes banques. Ils sont à vérifier sur les sites de la BCEAO et des administrations fiscales (non joignables depuis cette session).
9. Ces informations sont à compléter quand la recherche web sera de nouveau disponible : il suffira de relancer la tâche ou d'augmenter le quota. Les domaines african-markets.com et capmad.com devront aussi être autorisés dans les réglages réseau de la session.

---

## 11. Sources

Toutes les URL ci-dessous sont des documents primaires de `www.brvm.org`, consultés le 22/11/2026, sauf le BOC local.

**Marché et transversal**
- BOC du 20/11/2026 : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (copie locale `data/boc_text/boc_20261120.txt.gz`) ; BOC 2020-2026 locaux pour l'historique des dividendes et les cours du 20/11/2025 et du 31/12/2025.
- Calendrier de paiement des dividendes, exercice 2025 (06/10/2026) : https://www.brvm.org/sites/default/files/20261006_-_calendrier_de_paiement_des_dividendes_-_exercice_2025.pdf
- Avis 303-2026, flottant des sociétés cotées (repris du doc 01) : https://www.brvm.org/sites/default/files/20261012_-_avis_ndeg303_brvmdg_-_flottant_des_societes_cotees_a_la_brvm.pdf
- Liste des rapports des sociétés cotées : https://www.brvm.org/fr/rapports-societes-cotees ; communiqués : https://www.brvm.org/fr/emetteurs/type-annonces/communiques
- Document interne : `docs/research/01-structure-marche.md` (§8 opérations sur titres, §9 IPO, §11 nombre de titres et liquidité).

**SGBC**
- T3 2026 : https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_societe_generale_ci.pdf
- S1 2026 : https://www.brvm.org/sites/default/files/20260831_-_rapport_dactivites_-_1er_semestre_2026_-_societe_generale_ci.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260421_-_rapport_dactivites_annuel_et_etats_financiers_-_exercice_2025_-_societe_generale_ci_annule_et_remplace_le_precedent.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250207_-_rapport_dactivites_annuel_-_exercice_2024_-_societe_generale_ci.pdf
- Hausse du nominal : https://www.brvm.org/sites/default/files/20250224_-_communique_-_augmentation_de_capital_-_societe_generale_ci.pdf
- Page émetteur : https://www.brvm.org/fr/emetteurs/societes-cotees/societe-generale-cote-divoire-sgci

**SIBC**
- T3 2026 : https://www.brvm.org/sites/default/files/20261102_-_rapport_dactivites_-_3e_trimestre_2026_-_sib_ci.pdf
- S1 2026 : https://www.brvm.org/sites/default/files/20260928_-_rapport_dactivites_-_1er_semestre_2026_-_sib_ci.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260421_-_rapport_dactivites_annuel_et_etats_financiers_-_exercice_2025_-_sib_ci.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250305_-_rapport_dactivites_annuel_-_exercice_2024_-_sib_ci.pdf

**ECOC**
- T3 2026 : https://www.brvm.org/sites/default/files/20261027_-_rapport_dactivites_-_3e_trimestre_2026_-_ecobank_ci.pdf
- T1 2026 : https://www.brvm.org/sites/default/files/20260429_-_rapport_dactivites_-_1er_trimestre_2026_-_ecobank_ci.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260414_-_rapport_dactivites_et_etats_financiers_-_exercice_2025_-_ecobank_ci.pdf
- Exercice 2023 : https://www.brvm.org/sites/default/files/20240328_-_resultats_financiers_-_exercice_2023_-_ecobank_ci.pdf

**BICC**
- T3 2026 : https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_bicici.pdf
- Exercice 2025 (rapport) : https://www.brvm.org/sites/default/files/20260417_-_rapport_dactivites_annuel_-_exercice_2025_-_bici_ci.pdf
- Exercice 2025 (états financiers) : https://www.brvm.org/sites/default/files/20260417_-_etats_financiers_-_exercice_2025_-_bici_ci.pdf
- Exercice 2023 : https://www.brvm.org/sites/default/files/20240502_-_etats_financiers_-_exercice_2023_-_bici_ci.pdf
- Consortium (2022) : https://www.brvm.org/sites/default/files/20220928_-_communique_-_bici_ci.pdf
- Franchissement de seuil Brandon & McAin : https://www.brvm.org/sites/default/files/20230627_-_communique_declaration_franchissement_seuils_-_bici_ci.pdf
- Incorporation de réserves (titre seul) : https://www.brvm.org/sites/default/files/20241129_-_communique_-_augmentation_de_capital_par_incorporation_de_reserves_-_bici_ci.pdf

**NSBC**
- T3 2026 : https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_nsia_banque_ci.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260513_-_etats_financiers_et_communique_-_exercice_2025_-_nsia_banque_ci.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250325_-_etats_financiers_certifies_par_les_commissaires_aux_comptes_-_exercice_2024_-_nsia_banque_ci.pdf
- Communiqué du 13/07/2026 : https://www.brvm.org/sites/default/files/20260713_-_communique_-_nsia_banque_ci.pdf
- Franchissements de seuil : https://www.brvm.org/sites/default/files/20260416_-_communique_-_franchissement_de_seuil_par_nsia_holding_financiere.pdf ; https://www.brvm.org/sites/default/files/20260416_-_communique_-_franchissement_de_seuil_par_nsia_participations.pdf

**BBGC**
- T3 2026 : https://www.brvm.org/sites/default/files/20261028_-_rapport_dactivites_-_3e_trimestre_2026_-_bridge_bank_group_ci.pdf
- S1 2026 : https://www.brvm.org/sites/default/files/20260924_-_rapport_dactivites_-_1er_semestre_2026_-_bridge_bank_group_ci.pdf
- Avis de première cotation : https://www.brvm.org/sites/default/files/20260908_-_avis_ndeg263_brvmdg_-_premiere_cotation_-bridge_bank_group_cote_divoire.pdf
- Résultats de première cotation : https://www.brvm.org/sites/default/files/20260924_-_avis_ndeg285_brvmdg_-_resultats_de_premiere_cotation_-_bridge_bank_group_cote_divoire_bbgc.pdf

**BOAC**
- T3 2026 : https://www.brvm.org/sites/default/files/20261102_-_rapport_dactivites_-_3e_trimestre_2026_-_boa_ci.pdf
- Exercice 2025 (rapport des CAC et états financiers, mis en ligne le 12/06/2026) : https://www.brvm.org/sites/default/files/20260612_-_rapport_des_commissaires_aux_comptes_et_etats_financiers_annuels_-_exercice_2025_-_boa_ci.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250402_-_etats_financiers_-_exercice_2024_-_boa_ci.pdf
- Page émetteur : https://www.brvm.org/fr/emetteurs/societes-cotees/bank-africa-cote-divoire

**SAFC**
- T3 2026 : https://www.brvm.org/sites/default/files/20261102_-_rapport_dactivites_-_3e_trimestre_2026_-_safca_ci.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260609_-_etats_financiers_-_exercice_2025_-_safca_ci_annule_et_remplace_le_precedent.pdf
- T4 2025 : https://www.brvm.org/sites/default/files/20260423_-_rapport_dactivites_au_4eme_trimestre_2025_-_safca_ci.pdf
- T4 2024 : https://www.brvm.org/sites/default/files/20260703_-_rapport_dactivites_-_4e_trimestre_2024_-_safca_ci.pdf
- DPS (avis 108-2026) : https://www.brvm.org/sites/default/files/20260423_-_avis_ndeg108_brvmdg_-_valeur_theorique_-_dps_-_augmentation_de_k_-_safca_ci.pdf
- Admission des actions nouvelles (avis 237-2026) : https://www.brvm.org/sites/default/files/20260811_-_avis_ndeg237_brvmdg_-_admission_a_la_cote_actions_nouvelles_safca_ci.pdf

**BOAB**
- T3 2026 : https://www.brvm.org/sites/default/files/20261102_-_rapport_dactivites_-_3e_trimestre_2026_-_boa_bn.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260415_-_etats_financiers_-_exercice_2025_-_boa_bn.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250422_-_etats_financiers_certifies_par_les_commissaires_aux_comptes_-_exercice_2024_-_boa_benin.pdf

**BICB**
- T3 2026 : https://www.brvm.org/sites/default/files/20261110_-_rapport_dactivites_-_3e_trimestre_2026_-_biic_bn.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260619_-_rapport_dactivites_annuel_et_etats_financiers_ifrs_-_exercice_2025_-_biic.pdf
- Paiement du dividende (avis 199-2026) : https://www.brvm.org/sites/default/files/20260703_-_avis_ndeg199_brvmdg_-_paiement_de_dividendes_exo_2025_-_biic_bn.pdf
- Première cotation (avis 073-2025) : https://www.brvm.org/sites/default/files/20250410_-_avis_ndeg073_brvmdg_-_premiere_cotation_-biic.pdf

**BOABF**
- T3 2026 : https://www.brvm.org/sites/default/files/20261026_-_rapport_dactivites_-_3e_trimestre_2026_-_boa_bf.pdf
- S2 2025 : https://www.brvm.org/sites/default/files/20260323_-_rapport_dactivite_-deuxieme_semestre_2025_-_boa_bf.pdf
- S2 2024 : https://www.brvm.org/sites/default/files/20250416_-_rapport_dactivites_-_2eme_semestre_2024_-_boa_bf.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260323_-_etats_financiers_-_exercice_2025_-_boa_bf.pdf

**CBIBF**
- T3 2026 : https://www.brvm.org/sites/default/files/20261029_-_rapport_dactivites_-_3e_trimestre_2026_-_coris_bank_international_bf.pdf
- S1 2026 : https://www.brvm.org/sites/default/files/20260831_-_rapport_dactivites_-_1er_semestre_2026_-_coris_bank_international_bf.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260423_-_rapport_dactivites_annuel_-_exercice_2025_-_coris_bank_international_bf.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250430_-_rapport_dactivites_annuel_-_exercice_2024_-_coris_bank_international_bf.pdf
- T3 2025 : https://www.brvm.org/sites/default/files/20251030_-_rapport_dactivites_-_3eme_trimestre_2025_-_coris_bank_international_bf.pdf

**BOAM**
- S1 2026 : https://www.brvm.org/sites/default/files/20260923_-_rapport_dactivites_-_1er_semestre_2026_-_boa_mali.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260324_-_etats_financiers_-_exercice_2025_-_boa_ml.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250319_-_etats_financiers_certifies_par_les_cacs_-_exercice_2024_-_boa_mali.pdf
- Page émetteur : https://www.brvm.org/fr/emetteurs/societes-cotees/bank-africa-mali

**BOAN**
- T3 2026 : https://www.brvm.org/sites/default/files/20261026_-_rapport_dactivites_-_3e_trimestre_2026_-_boa_ng.pdf
- Communiqué de presse des résultats 2025 : https://www.brvm.org/sites/default/files/20260429_-_communique_de_presse_-_boa_ng.pdf
- Alerte sur résultats du 18/12/2025 : https://www.brvm.org/sites/default/files/20251223_-_communique_-_alerte_sur_resultats_-_boa_niger.pdf
- Alerte sur résultats du 20/02/2026 : https://www.brvm.org/sites/default/files/20260313_-_communique_-_profit_warning_-_boa_niger.pdf
- Rapport du conseil d'administration à l'AGO, exercice 2025 : https://www.brvm.org/sites/default/files/20260318_-_rapport_du_ca_a_lago_-_exercice_2025_-_boa_ng.pdf
- Page émetteur : https://www.brvm.org/fr/emetteurs/societes-cotees/bank-africa-niger

**BOAS**
- T3 2026 : https://www.brvm.org/sites/default/files/20261021_-_rapport_dactivites_-_3e_trimestre_2026_-_boa_sn.pdf
- Exercice 2025 : https://www.brvm.org/sites/default/files/20260317_-_etats_financiers_-_exercice_2025_-_boa_sn.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250319_-_etats_financiers_certifies_par_les_cacs_-_exercice_2024_-_boa_senegal.pdf

**ETIT**
- T3 2026 : https://www.brvm.org/sites/default/files/20261028_-_rapport_dactivites_-_3e_trimestre_2026_-_eti_tg.pdf
- Exercice 2025 (IFRS) : https://www.brvm.org/sites/default/files/20260413_-_etats_financiers_ifrs_-_exercice_2025_-_eti_tg.pdf
- Exercice 2024 : https://www.brvm.org/sites/default/files/20250328_-_etats_financiers_certifies_par_les_commissaires_aux_comptes_-_exercice_2024_-_eti_tg.pdf
- Annulation de l'AGO : https://www.brvm.org/sites/default/files/20261023_-_communique_-_annulation_ago_-_eti_tg.pdf
- AGE du 13/08/2026 : https://www.brvm.org/sites/default/files/20260817_-_communique_de_presse_-_eti_tg.pdf
- Paiement du dividende (avis 170-2026) : https://www.brvm.org/sites/default/files/20260616_-_avis_ndeg170_brvmdg_-_paiement_de_dividendes_exercice_2025_-_eti_tg.pdf

**ORGT**
- T3 2026 : https://www.brvm.org/sites/default/files/20261112_-_rapport_dactivites_-_3e_trimestre_2026_-_oragroup_tg.pdf
- Exercice 2025 (états financiers) : https://www.brvm.org/sites/default/files/20260504_-_etats_financiers_-_exercice_2025_-_oragroup_tg.pdf
- Exercice 2025 (rapport) : https://www.brvm.org/sites/default/files/20260430_-_rapport_dactivites_annuel_-_exercice_2025_-_oragroup_tg.pdf
- Exercice 2023 : https://www.brvm.org/sites/default/files/20240429_-_etats_financiers_-_exercice_2023_-_oragroup_togo.pdf
- Nouveau plan de financement (BOAD) : https://www.brvm.org/sites/default/files/20250522_-_communique_-_oragroup_tg.pdf
- Contrat de cession à Vista : https://www.brvm.org/sites/default/files/20241001_-_communique_-_oragroup_tg_1.pdf

---

## Vérification adversariale (2026-11-22)

**Méthode** : un vérificateur indépendant a tenté de réfuter les affirmations les plus coûteuses en cas d'erreur, surtout les paramètres qui seront codés. Les moyens utilisés :
- les BOC locaux (`data/boc_text/`, 2024-2026) : lignes « (d) », « (Ex- » et « (V) », cours de référence ;
- 25 PDF primaires de brvm.org retéléchargés et relus (`pdftotext`, OCR `tesseract` pour les documents scannés) ;
- les en-têtes HTTP `Last-Modified` des 79 PDF cités, obtenus par requête HEAD simple.

Limites : le quota de recherche web de la session était épuisé, et `www.bceao.int` et `www.amf-umoa.org` sont inaccessibles (proxy). Aucune source secondaire n'a pu être consultée. Le document ne cite **aucune étude académique nommée** : il n'y avait donc aucune référence à authentifier. La formule du P/B « juste » (ROE − g)/(k − g) est la formule standard tirée du modèle de Gordon.

Verdicts : **confirmé** = la source primaire relue donne la même valeur ; **corrigé** = la valeur ou la règle a été modifiée dans le texte ; **réfuté** = l'affirmation est fausse et a été retirée ou inversée ; **invérifiable** = aucune source primaire accessible.

| # | Élément vérifié | Verdict | Valeur correcte / commentaire | Source de la vérification | Conf. |
|---|---|---|---|---|---|
| 1 | Univers FIN : 17 valeurs (14 banques, ETIT, ORGT, SAFC) ; aucun assureur coté ; indice 221,79 ; +52,06 % ; PER 14,51 | confirmé | 48 actions au BOC, dont 12 en Prestige et 36 en Principal ; les seules mentions « assurance » sont des FCP | BOC 20/11/2026 (https://www.brvm.org/sites/default/files/boc_20261120_2.pdf) | high |
| 2 | `ci_gross_to_net` 0,88 / 0,90 (IRVM CI 12 % / 10 %) | confirmé, avec précision | Taux confirmés par le calendrier. Exception : SGBC, net de 2 298,75 pour un brut de 2 606 (0,8821), net appliqué par la BRVM. Toujours utiliser le net publié | https://www.brvm.org/sites/default/files/20261006_-_calendrier_de_paiement_des_dividendes_-_exercice_2025.pdf ; BOC 20/08/2026 | high |
| 3 | `ex_date_rule` = paiement − 1 jour ouvré | confirmé, règle précisée | La 1re séance ex correspond à la colonne « Ex-dividende » du calendrier. Le BOC de la veille porte « (d) » et donne déjà la référence ex = ceil5(clôture − net) (7 cas sur 7 en 2026) | BOC 20-21/08, 04-05/05, 21-22/05, 02-03/07, 29-30/07, 31/07-03/08/2026 | high |
| 4 | BOAC : « retenir 597,53 (BOC), car c'est la valeur appliquée » | **réfuté** | La BRVM a appliqué **594,53** : référence ex de 8 845 = ceil5(9 435 − 594,53), alors que 597,53 donnerait 8 840. La colonne passe à 597,53 le lendemain seulement | BOC 04/05 et 05/05/2026 ; calendrier (594,528) | high |
| 5 | `bonus_adjustment_factors_2024` (7 titres, ratios et dates ex) | confirmé | Référence ex / clôture de la veille : BOAM 1 345/2 020 ; BOABF 3 400/6 800 ; BOAS 3 125/4 690 ; BOAB 3 885/7 775 ; BOAN 3 260/5 220 ; BOAC 5 150/10 300 ; SIBC 3 550/7 100. Dates ex 28/08, 28/08, 29/08, 03/09, 04/09, 25/10 et 14/11/2024. Arrondi au pas inférieur | BOC 27/08-14/11/2024 (locaux) | high |
| 6 | DPS SAFC : facteur 0,7066, ex le 24/04/2026, référence 3 890, DPS 1 615 | confirmé | BOC 23/04 : clôture 5 505 → référence 3 890. Cohérent avec 3,75 M actions à 400 pour 8 119 750 anciennes (TERP ≈ 3 892) | BOC 23-24/04/2026 ; avis 303 (8 119 750 titres) | high |
| 7 | `solvency_min_pct` = 11,5 (CET1 7,5 ; T1 8,5 ; levier 3) | confirmé | Mention explicite « minimum réglementaire BCEAO de 11,50 % » (BIIC) et tableau des normes (SAFCA). Surcharge systémique [NON VÉRIFIÉ] | https://www.brvm.org/sites/default/files/20260619_-_rapport_dactivites_annuel_et_etats_financiers_ifrs_-_exercice_2025_-_biic.pdf ; https://www.brvm.org/sites/default/files/20261102_-_rapport_dactivites_-_3e_trimestre_2026_-_safca_ci.pdf | high |
| 8 | Capital minimum de 20 Md (avis 001-01-2024), mise en conformité fin 2026 | confirmé pour les banques, corrigé | Avis du **05/01/2024** ; 3 ans à compter du 01/01/2024. Seuil des établissements financiers [NON VÉRIFIÉ]. Le lien avec les attributions BOA/SIB est une inférence | https://www.brvm.org/sites/default/files/20250224_-_communique_-_augmentation_de_capital_-_societe_generale_ci.pdf | high |
| 9 | `availability_lag_sessions` = 1 (confiance « high ») | **corrigé** | 59 PDF sur 79 sont en ligne avant J+1 ; 18 pendant ou après la séance J+1 ; 1 à J+4 (BOAN) ; 1 préfixe décalé d'un an (SAFCA T4 2024). Nouvelle règle : `Last-Modified`, sinon J+2 | en-têtes HTTP `Last-Modified` des 79 URL de §11 (requêtes HEAD du 22/11/2026) | high |
| 10 | ETIT : `eps_override` 10,00 FCFA ; PER 5,7 ; le BOC (2,98) utilise le RN total | confirmé | BPA de base = BPA dilué = 1,68 cent US = 10,00 FCFA ; RN part du groupe 407 141 k$ ; RN consolidé de 345 523 M FCFA / 18,084 Md de titres = 19,1, donc PER 2,98 | https://www.brvm.org/sites/default/files/20260413_-_etats_financiers_ifrs_-_exercice_2025_-_eti_tg.pdf | high |
| 11 | ORGT : `eps_override` 241 ; RN part du groupe 2025 ≈16,9 Md ; 2024 n.d. | **corrigé** | RN attribuable de **18 355 M** (2024 : −37 865 M) ; BPA de **base de 264** et BPA **dilué de 241** ; CP part du groupe de 69 479 M ; bilan de 4 014 192 M (confirmés) | https://www.brvm.org/sites/default/files/20260504_-_etats_financiers_-_exercice_2025_-_oragroup_tg.pdf | high |
| 12 | BOAB : payout ≈118 % ; `payout_net_gt` 1,00 | confirmé, règle corrigée | RN 2025 de 20,10 Md (= cours / PER BOC × titres) ; 585 × 40 561 048 = 23,7 Md. En brut ≈131 % (IRVM BJ de 10 % inféré). Le drapeau doit porter sur le brut : BOABF ≈104 % (IRVM BF NON VÉRIFIÉ) | BOC 20/11/2026 ; calendrier ; doc 01 §6.1 | medium |
| 13 | ECOC : CoR de 0,7 → 8,1 Md ; RN −12,3 % ; NPL +28 % ; ROE 24,9 % | confirmé | CoR de 702 → 8 079 M (×11,5) ; RN de 44 437 → 38 954 M ; créances en souffrance de 36 638 → 46 902 M ; provisions de 43 442 M | https://www.brvm.org/sites/default/files/20261027_-_rapport_dactivites_-_3e_trimestre_2026_-_ecobank_ci.pdf | high |
| 14 | NSBC : RN 9M −27 % ; crédits −19 % | confirmé | RN de 25 037 → 18 388 M ; crédits nets de 1 818 671 → 1 472 560 M (depuis décembre) ; RN 2025 de 40 712 M | https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_nsia_banque_ci.pdf | high |
| 15 | ETI : AGO du 26/10/2026 annulée « conformément aux instructions de la Commission Bancaire de l'UMOA » | confirmé | Texte exact relu (communiqué daté du 23/10/2026, en ligne le 26/10 à 05:11 UTC) | https://www.brvm.org/sites/default/files/20261023_-_communique_-_annulation_ago_-_eti_tg.pdf | high |
| 16 | ETI : AGE du 13/08/2026 (quorum de 25 %, 12 administrateurs, fin de la limite de mandats) | confirmé | Plus un quorum du conseil porté à plus de la moitié des membres ; nombre d'administrateurs réduit de 15 à 12 | https://www.brvm.org/sites/default/files/20260817_-_communique_de_presse_-_eti_tg.pdf | high |
| 17 | ETI 9M 2026 : RN part du groupe de 364 M$ (+17 %) ; NPL de 9,4 → 7,5 % ; ROTE de 24,9 % ; CP part du groupe de 1 181,8 Md | confirmé | Chiffres identiques à ceux du rapport | https://www.brvm.org/sites/default/files/20261028_-_rapport_dactivites_-_3e_trimestre_2026_-_eti_tg.pdf | high |
| 18 | BOAN : aucun dividende au titre de 2025 ; ROE de 11,4 / 1,0 / 16,0 % ; solvabilité de 15,4 / 14,1 / 17,4 % ; NPL sectoriel de 24,4 → 28,6 % | confirmé | Plus : l'alerte du 20/02/2026 n'a été mise en ligne que le 18/03/2026 | https://www.brvm.org/sites/default/files/20260429_-_communique_de_presse_-_boa_ng.pdf ; https://www.brvm.org/sites/default/files/20260313_-_communique_-_profit_warning_-_boa_niger.pdf | high |
| 19 | SGBC : NPL 8,0 % ; couverture 82 % ; brut 2 606 ; payout 80 % ; RN 101 352 M ; solvabilité 17,6 % (S1 2026) | confirmé | Chiffres identiques à ceux des rapports | https://www.brvm.org/sites/default/files/20260421_-_rapport_dactivites_annuel_et_etats_financiers_-_exercice_2025_-_societe_generale_ci_annule_et_remplace_le_precedent.pdf ; https://www.brvm.org/sites/default/files/20260831_-_rapport_dactivites_-_1er_semestre_2026_-_societe_generale_ci.pdf | high |
| 20 | BOAC 9M 2026 : RN de 29,7 Md (+11,4 %), crédits +19,9 %, dépôts +17,7 % | confirmé (OCR) | 29 657 / 26 632 M ; 495 097 M (+19,94 %) ; 942 180 M (+17,71 %). CP 2025 toujours non lus [NON VÉRIFIÉ] | https://www.brvm.org/sites/default/files/20261102_-_rapport_dactivites_-_3e_trimestre_2026_-_boa_ci.pdf | high |
| 21 | BICC : consortium à 67,49 % pour 80 Md ; Brandon & McAin à 19,11 % au cours de 6 945 | confirmé | 11 247 810 actions (BNP 59,79 % + Proparco 7,70 %) ; 3 185 017 actions achetées le 27/06/2023 auprès de SUNU | https://www.brvm.org/sites/default/files/20220928_-_communique_-_bici_ci.pdf ; https://www.brvm.org/sites/default/files/20230627_-_communique_declaration_franchissement_seuils_-_bici_ci.pdf | high |
| 22 | BICC : « flottant de 32,5 % incohérent » | **réfuté** | 5 418 860 = 16 666 670 − 11 247 810 : la BRVM n'exclut que le bloc de contrôle. Flottant économique ≤ 13,4 % | avis 303-2026 (OCR) : https://www.brvm.org/sites/default/files/20261012_-_avis_ndeg303_brvmdg_-_flottant_des_societes_cotees_a_la_brvm.pdf | high |
| 23 | BBGC : 1re cotation le 24/09/2026 à 7 255, 4 séances à la borne haute, compartiment Principal ; « 40 séances » | confirmé / corrigé | Avis 285 et BOC confirmés ; **42** séances au 20/11/2026 ; demande de l'OPV (95,8 Md, 17 544 investisseurs) [NON VÉRIFIÉ] | https://www.brvm.org/sites/default/files/20260924_-_avis_ndeg285_brvmdg_-_resultats_de_premiere_cotation_-_bridge_bank_group_cote_divoire_bbgc.pdf ; BOC 24/09-01/10/2026 | high |
| 24 | `ipo_quarantine_sessions` = 60 ; BBGC « éligible fin décembre » | invérifiable / corrigé | Choix de conception sans base empirique ; éligibilité vers le 16/12/2026, et non fin décembre | BOC locaux (décompte des séances) | low |
| 25 | `red_flag.npl_ratio_gt_pct` = 8,0, « SGBC à 8,0 % » | corrigé | Avec « > », SGBC n'est pas détecté : passage à « ≥ ». Les définitions de NPL (PCB brut, IFRS stage 3) ne sont pas comparables. Garde-fou ajouté sur le multiple de CoR | rapport SGBC 2025 ; rapport ECOC T3 ; rapport ETI T3 | medium |
| 26 | RN 2025 des 16 valeurs (tableau §3) | confirmé | (cours / PER BOC) × nombre de titres = RN du tableau à ±0,1 % (ORGT +0,8 %) | BOC 20/11/2026 | high |
| 27 | BICB : 1re cotation le 28/04/2025 (5 600) ; dividende de 254,6 versé le 15/09/2025 et le 31/07/2026 | confirmé | BOC 28/04/2025, 31/12/2025 et 20/11/2026 ; prix d'OPV de 5 250 tiré de l'avis 073 (scanné, non relu) | BOC locaux | high |
| 28 | `country_risk_multiplier`, poids de `fin_score`, `missing_rank` 0,4 | invérifiable | Jugements de conception, sans source chiffrée ni backtest : à traiter comme hyperparamètres et à valider hors échantillon | — | low |

**Bilan** : 28 éléments vérifiés. 18 sont confirmés (dont 4 avec une précision de règle), 6 corrigés, 2 réfutés (dividende BOAC appliqué ; incohérence du flottant BICC) et 2 invérifiables (paramètres de conception). Aucun chiffre n'a été inventé. Les valeurs non relues restent marquées [NON VÉRIFIÉ] : CP 2025 de BOAC, demande de l'OPV BBGC, IRVM du BF et du TG, seuil de capital des établissements financiers, surcharge des banques systémiques.
