# 06b — Fiches fondamentales des sociétés non financières cotées à la BRVM

> **Date de l'étude** : 22/11/2026. **Cours de référence** : BOC n° 222 du vendredi 20/11/2026.
> **Périmètre** : les 31 actions non financières (sur 48) cotées au 20/11/2026.
> **Unités** : Md = milliards de FCFA ; M = millions de FCFA. Sauf mention contraire, « RN » = résultat net et « CA » = chiffre d'affaires.
> **Avertissement** : ce document classe des titres selon des critères mesurables et sourcés. **Il ne garantit aucun gain.** Une note élevée signifie « meilleure combinaison qualité × valeur × croissance × liquidité selon les données publiées », pas « hausse certaine ». Le classement doit être validé hors échantillon (walk-forward, voir `04-rigueur-quantitative.md`) avant tout usage en allocation réelle.

---

## 0. Méthode, sources et limites (à lire en premier)

**Sources primaires utilisées** (toutes sur www.brvm.org, liste complète au §8) :
1. **BOC du 20/11/2026** : cours, PER, dernier dividende net, rendement, variation 2026, secteur, compartiment, statut (copie locale `data/boc_text/boc_20261120.txt.gz`). Le BOC fournit aussi l'**historique des dividendes 2017-2026** via la colonne « dernier dividende payé » de 2 105 séances, extraite par `brvm_alpha.data.store.build_panel` (panel reconstruit dans le bac à sable de session).
2. **États financiers** annuels 2024 et 2025 et **rapports d'activité** 2026 (9 mois, ou semestre quand le 9 mois n'existe pas) publiés par chaque émetteur sur `brvm.org/fr/rapports-societe-cotes/<société>`. Au total, 98 PDF téléchargés : 88 rapports financiers, 2 calendriers et 8 avis. Environ 25 sont des scans sans couche texte : ils ont été lus visuellement, page par page.
3. **Calendriers officiels de paiement des dividendes** : exercice 2024 (publié le 24/12/2025) et exercice 2025 (publié le 06/10/2026). Ils donnent les montants bruts ou nets par action.
4. **Avis BRVM** : suspensions et levées de suspension (2025-2026). Le flottant au 31/12/2025 et le nombre de titres viennent de l'avis 303-2026, repris dans `01-structure-marche.md` §11.
5. **Fiches émetteurs** `brvm.org/fr/emetteurs/societes-cotees/<société>` pour l'actionnariat. **Attention** : la plupart de ces fiches datent de 2014-2015 ou 2019. Seules celles de Sicable, Onatel, CIE, SITAB et TotalEnergies SN sont à jour au 31/12/2025.

**Limites (déclarées, non masquées)** :
- Le **quota de recherche web de la session était épuisé** quand cette étude a commencé (quota partagé entre agents). Aucune source de presse n'a pu être consultée. Tout repose sur des documents primaires de brvm.org. Les changements d'actionnaires postérieurs aux fiches émetteurs (par exemple propriétaire actuel d'AGL, repreneur d'Air Liquide CI devenu Erium, actionnaire d'Eranove) sont donc marqués **« non vérifié »**.
- Non extrait : SICOR (rapport 2025 scanné de 28 pages, titre suspendu), Unilever CI 2024-2025 (aucun état financier publié après l'exercice 2023), SONOCO SIEM 2024-2025 (idem après 2023).
- Les montants de dividendes « 2021-2026 » du tableau §2 sont **nets d'IRVM, par année de paiement**, tels que publiés au BOC. Les montants **bruts** des exercices 2024 et 2025 viennent des calendriers officiels.
- Confiance : **high** = chiffre lu dans un document primaire ; **medium** = calcul dérivé ou lecture de scan peu net ; **low** = donnée ancienne ou incohérence non résolue.

---

## 1. Inventaire : les 31 sociétés non financières (BOC 20/11/2026)

Répartition par secteur BRVM (BOC, ligne « Indices sectoriels ») : Télécommunications 3, Énergie 4, Services publics 2, Consommation de base 9, Consommation discrétionnaire 7, Industriels 6. Le reste de la cote, soit 17 sociétés, relève des Services financiers. Total : 48 sociétés (BOC 20/11/2026, confiance high).

### 1.1 Tableau de marché

Capitalisation = cours × nombre de titres de l'avis 303-2026. Pour SNTS, le nombre de titres est multiplié par 10 après le fractionnement. PER et rendement net sont **ceux du BOC**. Le rendement BOC = dernier dividende net payé / cours : il peut être **périmé** (voir les drapeaux). La variation 2026 est celle du BOC, **non ajustée des dividendes**. La valeur médiane échangée par séance est calculée sur les 220 BOC 2026.

| Symb. | Société | Pays | Secteur | Comp. | Cours | Capi (Md) | PER BOC | Rdt net BOC | Var. 2026 | Val. méd./séance (M) | Flottant | Payout FY25* | Statut |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SNTS | Sonatel | SN | Télécom | Prestige | 4 040 | 4 040,0 | 9,77 | 4,31 % | +54,67 % | 252,3 | 23,9 % | 57 % (PdG) | coté |
| ORAC | Orange Côte d'Ivoire | CI | Télécom | Prestige | 19 250 | 2 900,1 | 17,28 | 3,66 % | +35,09 % | 27,4 | 20,2 % | 93 % (PdG) | coté |
| ONTBF | Onatel (Moov Africa BF) | BF | Télécom | Prestige | 2 805 | 190,7 | 13,14 | 5,18 % | +12,88 % | 8,6 | 23,0 % | 70 % | coté |
| TTLC | TotalEnergies Marketing CI | CI | Énergie | Prestige | 2 990 | 188,3 | 20,72 | 4,67 % | +28,05 % | 11,8 | 27,0 % | 110 % | coté |
| TTLS | TotalEnergies Marketing SN | SN | Énergie | Prestige | 3 580 | 116,6 | 17,20 | 4,93 % | +43,20 % | 6,6 | 30,9 % | ≈104 % | coté |
| SMBC | SMB (bitumes) | CI | Énergie | Prestige | 17 995 | 140,3 | 10,73 | 3,91 % | +89,42 % | 11,6 | 51,8 % | 48 % | coté |
| SHEC | Vivo Energy CI | CI | Énergie | Principal | 1 850 | 116,6 | 19,33 | 4,60 % | +28,03 % | 8,2 | 28,3 % | 101 % | coté |
| CIEC | CIE (électricité) | CI | Serv. publics | Principal | 4 400 | 246,4 | 18,77 | 4,68 % | +86,44 % | 23,5 | 45,9 % | 100 % | coté |
| SDCC | SODECI (eau) | CI | Serv. publics | Principal | 11 300 | 101,7 | 17,29 | 4,09 % | +94,83 % | 8,1 | 49,5 % | 101 % | coté |
| NTLC | Nestlé CI | CI | Conso. base | Prestige | 12 800 | 282,5 | 15,33 | 2,89 % | +20,19 % | 9,9 | 20,0 % | 50 % | coté |
| PALC | Palm CI | CI | Conso. base | Prestige | 7 440 | 115,0 | 7,42 | 5,93 % | −8,15 % | 20,8 | 32,9 % | 50 % | coté |
| SPHC | SAPH | CI | Conso. base | Prestige | 7 645 | 195,4 | 7,82 | 5,63 % | −3,23 % | 17,7 | 59,5 % | 50 % | coté |
| SOGC | SOGB | CI | Conso. base | Principal | 7 600 | 164,2 | 13,14 | 6,60 % | −3,80 % | 17,6 | 26,8 % | 99 % | coté |
| SCRC | Sucrivoire | CI | Conso. base | Principal | 1 230 | 24,1 | — (perte) | 3,29 % ⚠ (2021) | +16,04 % | 19,6 | 23,0 % | — | coté |
| SLBC | Solibra | CI | Conso. base | Principal | 40 500 | 666,7 | 14,56 | 4,62 % | +40,14 % | 12,5 | 18,6 % | 76 % | coté |
| STBC | SITAB | CI | Conso. base | Principal | 21 325 | 382,9 | 10,50 | 8,01 % | +7,81 % | 47,6 | 26,4 % | 96 % | coté |
| UNLC | Unilever CI | CI | Conso. base | Principal | 44 000 | 404,1 | 631,03 ⚠ | — | +28,56 % | 1,0 | **0,2 %** | — | coté (illiquide) |
| SICC | SICOR | CI | Conso. base | Principal | 8 400 | 5,0 | — | — | +154,55 % | 0,2 | 12,3 % | — | **suspendu** |
| ABJC | Servair Abidjan | CI | Conso. discr. | Principal | 3 000 | 32,7 | 24,60 | 6,72 % | +3,45 % | 7,6 | 20,0 % | 185 % | coté |
| BNBC | Bernabé CI | CI | Conso. discr. | Principal | 1 750 | 11,6 | 519,40 | 8,57 % ⚠ (2023) | +24,11 % | 2,7 | 34,9 % | — | coté |
| CFAC | CFAO Mobility CI (ex CFAO Motors) | CI | Conso. discr. | Principal | 1 190 | 215,8 | 25,64 | 4,66 % | −16,78 % | 4,6 | **4,2 %** | 136 % | coté |
| LNBB | Loterie Nationale du Bénin | BJ | Conso. discr. | Principal | 3 900 | 78,0 | 16,87 | 4,21 % | −9,20 % | 7,9 | 45,0 % | ≈75 % | coté |
| NEIC | NEI-CEDA | CI | Conso. discr. | Principal | 1 900 | 24,3 | 11,91 | 7,39 % | +58,33 % | 4,9 | 20,0 % | 100 % | coté |
| PRSC | Tractafric Motors CI | CI | Conso. discr. | Principal | 3 720 | 38,1 | 16,09 | 4,94 % | −4,00 % | 3,3 | 100 % (déclaré) | 90 % | coté |
| UNXC | Uniwax | CI | Conso. discr. | Principal | 1 705 | 35,4 | — (perte) | 3,56 % ⚠ (2022) | +21,79 % | 17,5 | 27,7 % | — | coté |
| CABC | Sicable | CI | Industriels | Principal | 2 720 | 16,1 | 11,19 | 5,59 % | +15,25 % | 4,8 | 48,7 % | ≈60 % | coté |
| FTSC | Filtisac | CI | Industriels | Principal | 1 600 | 22,6 | 48,43 | **107,91 % ⚠** | −27,93 % | 6,5 | 33,7 % | — | coté |
| SDSC | Africa Global Logistics CI | CI | Industriels | Principal | 2 685 | 146,2 | 186,20 | 3,43 % | +77,23 % | 25,9 | 25,0 % | **638 %** | coté |
| SEMC | Sonoco Metal Packaging SIEM | CI | Industriels | Principal | 1 495 | 37,7 | 37,21 ⚠ | 0,94 % ⚠ | +113,57 % | 7,1 | 10,3 % | — | **suspendu** |
| SIVC | Erium CI (ex Air Liquide CI) | CI | Industriels | Principal | 1 600 | 14,0 | 77,94 | — | +1,27 % | 9,8 | 27,9 % | — | coté |
| STAC | SETAO | CI | Industriels | Principal | 2 180 | 29,3 | — (perte) | 3,03 % ⚠ (2022) | +64,53 % | 9,3 | 20,8 % | — | coté |

\* Payout FY25 = dividende brut de l'exercice 2025 × nombre de titres / RN 2025. Les montants viennent des calendriers et des états financiers (calcul propre, confiance medium). Pour les sociétés non ivoiriennes, le brut est déduit du net : IRVM de 10 % au Sénégal (confirmé : résolution d'affectation Sonatel, 1 933 brut → 1 740 net), de 12,5 % au Burkina Faso (confirmé : rapport de gestion Onatel, 166,0816 brut → 145,3214 net « net de l'IRCM ») et d'environ 5 % au Bénin **[NON VÉRIFIÉ : aucune source primaire trouvée pour le taux béninois ; le payout LNBB passerait de ≈75 % à ≈79 % avec un taux de 10 %]** (`01-structure-marche.md` §6.1). Pour la Côte d'Ivoire, les calendriers CAL24 et CAL25 indiquent : IRVM de 12 % (personnes physiques) et 10 % (personnes morales) sur le dividende ordinaire, 17 % et 15 % sur la part exceptionnelle. « PdG » : payout calculé sur le RN part du groupe.

**Contexte marché (BOC 20/11/2026)** :
- BRVM Composite à 492,89, soit +42,56 % depuis le début de 2026. PER moyen du marché : 15,79, calculé hors Unilever.
- Performance 2026 des indices sectoriels : Télécom +44,71 % ; Consommation discrétionnaire −7,32 % ; Consommation de base +17,84 % ; Industriels +50,15 % ; Énergie +42,72 % ; Services publics +88,82 %.
- PER moyens par secteur : Télécom 12,91, Consommation discrétionnaire 36,40, Consommation de base 12,51, Industriels 131,01, Énergie 17,21, Services publics 18,34.

Confiance : high.

### 1.2 Drapeaux de qualité de données (à coder)

| Drapeau | Titres | Preuve |
|---|---|---|
| Suspendu, non-respect de l'information périodique | SICC, SEMC (depuis le 16/09/2026) | Avis 268 et 270-2026. Sucrivoire, suspendue le même jour (avis 269), a repris sa cotation le **mardi 22/09/2026** (avis 276 daté du 21/09, après publication de son rapport du **1er trimestre** 2026 ; le BOC du 21/09 la montre encore « SP »). *(Corrigé le 22/11/2026 : la v1 indiquait une réadmission le 21/09.)* |
| Flottant sous le seuil réglementaire de **15 %** (colonne « Diffusion de 15 % du capital dans le public » de l'avis 303) | UNLC 0,22 %, CFAC 4,15 %, SEMC 10,29 %, SICC 12,26 % (les quatre marqués « Non respectée ») | Avis 303-2026 (données au 31/12/2025), repris dans `01-structure-marche.md` |
| Rendement BOC périmé ou exceptionnel | FTSC (107,91 % : dividende exceptionnel 2025), BNBC (2023), SCRC (2021), UNXC (2022), STAC (2022), SEMC (2021) | Colonne « date du dernier dividende » du BOC |
| PER BOC calculé sur un exercice ancien | UNLC (exercice 2023), SEMC (exercice 2023) | Derniers états financiers publiés |
| Données d'un trimestre isolé, pas d'un cumul | STBC (rapport « T3 2026 » = 3e trimestre seul) | STBC-9M26 contre STBC-S126 |
| Retard de publication | SDSC (aucun rapport périodique 2026 trouvé au 21/11/2026) ; SIVC (rapport T1 2025 publié le 19/12/2025) | Listes des rapports sur brvm.org |

---

## 2. Historique des dividendes 2021-2026

### 2.1 Dividende net par action payé, par année civile de paiement (BOC)

Source : colonne « Dernier dividende payé, montant net » des BOC 2021-2026, regroupée par date de paiement (panel `dividends.parquet`). « — » signifie qu'aucun paiement n'a été détecté. Confiance : medium pour 2021, à cause d'un trou de 35 séances en mai-juin 2021 dans les BOC disponibles ; high pour 2022-2026.

| Symb. | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Brut exercice 2024 (CAL24) | Brut exercice 2025 (CAL25) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SNTS (avant split ; ÷10 après le 26/10/2026) | 1 225 | 1 400 | 1 500 | 1 575 | 1 655 | 1 740 (= 174 ajusté) | net 1 655 | net 1 740 |
| ORAC | — | — | 752,76 | 780 | 660 | 704 | 750 | 800 |
| ONTBF | 399,56 | 416,58 | 287,88 | 266,45 | 189,53 | 145,32 | net 189,53 | net 145,32 |
| TTLC | 109,31 | 159,29 | 175,53 | 199,54 | 195,67 | 139,77 | 222,36 | 158,83 |
| TTLS | 223,60 | 187,30 | 241,01 | 207,58 | 222,40 | 176,65 | net 222,40 | net 176,65 |
| SMBC | 810 | 720 | 720 | 1 080 | 616 | 704 | 700 | 800 |
| SHEC | — | 29,00 | 53,00 | 57,00 | 75,29 | 85,07 | 85,56 | 96,67 |
| CIEC | 167,14 | 153,16 | 157,50 | 171,00 | 158,40 | 205,92 | 180 | 234 |
| SDCC | 337,50 | 432,00 | 450,00 | 481,50 | 352,00 | 462,00 | 400 | 525 |
| NTLC | 363,67 | 856,80 | 728,10 | 675,00 | 721,60 | 369,60 | 820 | 420 |
| PALC | 102,51 | 1 236,34 | 1 213,63 | 563,31 | 451,45 | 441,04 | 513,01 | 501,60 |
| SPHC | 132,30 | 365,40 | 294,30 | 64,80 | 323,84 | 430,32 | 368 | 489 |
| SOGC | 250 | 541,81 | 558 | 207 | 528 | 501,60 | 600 | 570 |
| SCRC | 40,50 | — | — | — | — | — | — | — |
| SLBC (split 10:1 le 30/09/2024) | 2 736 | 4 050 | — | 2 700 | 1 073,60 | 1 871,76 | 1 220 | 2 127 |
| STBC | 436,12 | 445,12 | 551 | 675 | 2 096 | 1 707,20 | 2 375 | 1 940 |
| UNLC, SICC, SIVC | — | — | — | — | — | — | — | — |
| ABJC | — | 57,73 | 92 | 206,20 | — | 201,52 | — | 229 |
| BNBC | — | — | 150 | — | — | — | — | — |
| CFAC | 22,15 | 69,47 | 27,45 | 15,87 | 7,04 | 55,44 | 8 | 63 |
| LNBB (introduite en 12/2024) | — | — | — | — | 275,50 | 164,17 | net 275,5 | net 164,17 |
| NEIC | — | — | 35,25 | 81,78 | — | 140,40 | — | 159,54 |
| PRSC | 162,90 | 175,86 | 224,10 | 182,70 | 182,16 | 183,92 | 207 | 209 |
| UNXC | 18,00 | 60,75 | — | — | — | — | — | — |
| CABC | 133 | 69 | 69 | 79,58 | 112,72 | 152,02 | 128,1 | net 152,02 |
| FTSC | 235 | — | — | 143,10 | **1 726,56** | — | **1 320 + 680,67 exceptionnel** | — |
| SDSC | 100 | 130 | 92 | 92 | 92 | 92 (payé le 27/10/2026) | net 92 | (5,008 Md, état financier 2025) |
| SEMC | 14,40 | — | — | — | — | — | — | — |
| STAC | 66,15 | 66,15 | — | — | — | — | — | — |

Sources : BOC 2021-2026 ; [CAL24] ; [CAL25] ; [SDSC-FY25] pour l'affectation 2025 d'AGL.

*Corrigé le 22/11/2026 (vérification adversariale) : ORAC 2023 = 752,76 payé le 15/06/2023 (BOC 29/12/2023), et non « — » ; ONTBF 2024 = 266,45 payé le 31/07/2024 (BOC 31/12/2024 et fiche émetteur : 266,44625), et non 226,45 ; CIEC 2021 = 167,14 payé le 14/07/2021 (BOC 30/12/2021), et non 176,14 ; STAC 2021 = 66,15 payé le 16/07/2021 (BOC 30/12/2021), et non « — ». Les compteurs « années avec dividende » du score qualité (§5.1) d'ORAC (4/6 au lieu de 3/6) et de STAC (2/6 au lieu de 1/6) sont donc sous-estimés dans le classement du §5.2 ; l'impact n'a pas été recalculé. Pour SLBC, les montants 2021-2024 sont **avant** fractionnement (le paiement du 14/08/2024 apparaît à 270 dans les BOC postérieurs au 30/09/2024) ; 2025-2026 sont **après**. Sonatel : dividende brut de l'exercice 2025 = **1 933 FCFA** avant split (IRVM 10 %, résolution d'affectation [SNTS-FY25]).*

**Enseignements** :
- **Dividendes en hausse continue sur 6 ans** : SNTS (+42 % de 2021 à 2026, sans interruption), PRSC (stable à environ 180 net), SHEC (en hausse depuis 2022), CIEC.
- **Dividendes en baisse structurelle** : ONTBF (de 399,6 à 145,3, soit −64 % en 5 ans, car le RN baisse et le payout est fixé à 70 %) et NTLC (le brut 2025 est divisé par deux : 420 contre 820).
- **Dividendes cycliques**, liés aux matières premières : PALC, SPHC, SOGC.
- **Dividendes non soutenables**, payés au-delà du bénéfice de l'exercice : SDSC (payout de 638 % en 2025, pris sur le report à nouveau de 57,2 Md), ABJC (185 %), CFAC (136 %), TTLC (110 %), TTLS (≈104 %), SHEC et SDCC (≈101 %).

---

## 3. Fondamentaux 2023-2025 et partiel 2026

### 3.1 Tableau de synthèse

RN = résultat net total (consolidé pour SNTS et ORAC, part des minoritaires comprise). Marge = RN 2025 / CA 2025. « 2026 partiel » = cumul 9 mois au 30/09/2026 (6 mois quand indiqué S1), avec la variation sur un an.

| Symb. | CA 2023 | CA 2024 | CA 2025 | RN 2023 | RN 2024 | RN 2025 | Marge 25 | 2026 partiel : CA (var.) / RN (var.) | Structure financière fin 2025 | Sources |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| SNTS | 1 620,7 | 1 776,4 | 1 923,1 | 331,7 (PdG 279,4) | 393,7 (PdG 328,8) | 413,6 (PdG 342,0) | 21,5 % | 9M : 1 583 (+10,5 %) / 354 (+12,9 %) | Trésorerie nette ≈ +113 Md (passifs financiers 402,7 + loyers 20,1 contre disponibilités 536,1) ; capitaux propres 1 399,3 | SNTS-FY25, SNTS-FY24, SNTS-9M26 |
| ORAC | 1 016,5 | 1 084,1 | 1 197,1 | 154,9 (PdG 110,5) | 158,2 (PdG 112,8) | 167,8 (PdG 129,1) | 14,0 % | 9M : 1 012 (+15,5 %) / 141 (+18,3 %) | Dette nette ≈ 110 Md (335,9 − 225,8) ; capitaux propres 707,8 ; DN/CP 0,16 | ORAC-FY25, ORAC-FY24, ORAC-9M26 |
| ONTBF | 139,2 | 141,8 | 146,2 | 21,1 | 21,5 | 15,9 | 10,9 % | 9M : 114,0 (+4,1 %) / 10,5 (contre 11,0) | Dette nette ≈ 59 Md (dettes financières 69,7 + trésorerie passif 49,8 − trésorerie actif 60,4) ; capitaux propres 57,5 ; DN/CP ≈ 1,0 | ONTBF-FY25, ONTBF-RG25, ISS-ONTBF, ONTBF-9M26 |
| TTLC | 578,9 | 621,0 | 588,7 | 8,71 | 9,37 | 9,09 | 1,5 % | 9M : 501,2 (+14,4 %) / 8,55 (+31,2 %) | Dette nette ≈ 25,4 (3,45 + 30,78 − 8,85) ; capitaux propres 36,2 ; DN/CP 0,70 | TTLC-FY25, TTLC-FY24, TTLC-9M26 |
| TTLS | 499,2 | 484,9 | 455,2 | 4,22 | 7,09 | 6,15 | 1,4 % | 9M : 319,8 (−7 %) / 6,93 (+38 %) | Capitaux propres 20,7 ; dettes financières 5,2 ; trésorerie actif 20,6 (trésorerie passif non extraite) | TTLS-FY25, ISS-TTLS, TTLS-9M26 |
| SMBC | 247,6 | 229,1 | 206,7 | 17,26 | 8,70 | 13,08 | 6,3 % | 9M : 179,2 (+15 %) / 8,90 (+57 %) | **Trésorerie nette +14,8** (24,0 − 9,2) ; capitaux propres 42,9 | SMBC-FY25, SMBC-FY24, SMBC-9M26 |
| SHEC | 550,7 | 600,7 | 605,0 | 4,01 | 5,35 | 6,03 | 1,0 % | 9M : 467,7 (+4 %) / 4,75 (+15 %) | **Dette nette ≈ 77,2** (11,9 + 70,3 − 5,0) ; capitaux propres ≈ 27,2 ; **DN/CP ≈ 2,8** | SHEC-FY25, SHEC-FY24, SHEC-9M26 |
| CIEC | 257,2 | 263,3 | 302,3 | 10,63 | 10,10 | 13,13 | 4,3 % | S1 : 138,2 (+2,4 %) / 5,34 (+4,8 %) | Dette nette ≈ 32,1 (64,3 + 156,1 − 188,3) ; capitaux propres ≈ 36,0. Bilan de concessionnaire : 1 470 Md d'« opérations du secteur » à l'actif comme au passif | CIEC-FY25, CIEC-FY24, CIEC-S126 |
| SDCC | 175,5 | 172,2 | 189,4 | 4,90 | 3,56 | 4,66 | 2,5 % | 9M : 126,5 (+1,5 %) / 2,13 (+12,1 %) | Fin 2024 : dettes financières 65,2, trésorerie nette −24,9. 2025 : « trésorerie sous tension » selon la société | SDCC-FY25, SDCC-FY24, SDCC-9M26 |
| NTLC | 203,6 | 220,1 | 233,3 | 16,56 | 18,15 | 18,43 | 7,9 % | 9M : 192,5 (+11,0 %) / 11,99 (+0,4 %) | Autres dettes financières 8,1 | NTLC-FY25, NTLC-FY24, NTLC-9M26 |
| PALC | 206,2 | 172,2 | 197,6 | 19,35 | 15,86 | 15,51 | 7,8 % | 9M : 174,9 (+4 %) / 15,87 (−12 %) | Capitaux propres 142,6 ; dettes financières 0,8 (quasi nulles) | PALC-FY25, PALC-FY24, PALC-9M26 |
| SPHC | 206,5 | 279,4 | 340,8 | 3,64 | 18,79 | 24,97 | 7,3 % | 9M : 232,5 (−8 %) / 9,70 (**−58 %**) | Capitaux propres 137,9 ; dettes financières 35,6 | SPHC-FY25, SPHC-FY24, SPHC-9M26 |
| SOGC | ≈71,8 (ventes) | ≈87,7 (ventes) | 99,0 | 5,27 | 13,11 | 12,49 | 12,6 % | 9M : 67,3 (−11 %) / 7,62 (**−34 %**) | Dettes financières ≈ 0 ; trésorerie actif 5,3 contre passif 0,7 | SOGC-FY25, SOGC-FY24, SOGC-9M26 |
| SCRC | n.e. | 87,2 | 80,6 | n.e. | +2,47 (IFRS) | **−6,13 (SYSCOHADA) / −7,95 (IFRS)** | <0 | S1 : 42,3 (−1,4 %) / −4,79 (contre −6,71) | **Emprunts 67,2 Md (39,4 long terme + 27,8 court terme) contre 30,3 en 2024** ; capitaux propres 17,2 | SCRC-FY25, SCRC-S126 |
| SLBC | 311,4 | 309,7 | 378,1 (CA net 335,9) | 15,08 | 21,47 | 45,78 | 13,6 % | S1 : 180,2 (+8,7 %) / 28,10 (+0,5 %) | Capitaux propres ≈ 195 ; dettes financières ≈ 56 (ordre des colonnes ambigu, confiance medium) | SLBC-FY25, SLBC-FY24, SLBC-S126 |
| STBC | 169,4 | 213,8 | 268,0 | 12,40 | 44,17 (retraité ; 44,73 publié initialement) | 36,46 | 13,6 % | 9M (S1 + T3) : 216,3 (+10,5 %) / 26,57 (**−14,3 %**) | **Trésorerie nette +30,8**, aucune dette ; capitaux propres 45,6 | STBC-FY25, STBC-FY24, STBC-S126, STBC-9M26 |
| UNLC | 36,2 (2022) | n.p. | n.p. | 0,64 | n.p. | n.p. | — | n.p. | Aucun état financier publié après l'exercice 2023 | UNLC-FY23 |
| SICC | n.e. | n.e. | n.e. | n.e. | n.e. | n.e. | — | — | Suspendu le 16/09/2026 | AVIS-268-2026 |
| ABJC | n.e. | 12,47 | 13,30 | n.e. | 1,52 | 1,35 | 10,2 % | 9M : 10,69 (+4,6 %) / 1,33 (+0,4 %) | Trésorerie nette ≈ +4,0 ; capitaux propres 5,16 | ABJC-FY25, ABJC-9M26 |
| BNBC | 45,96 | 45,31 | 42,45 | 0,036 | 0,007 | 0,022 | 0,05 % | 9M : 36,1 (+13 %) / 0,139 (contre −0,157) | Capitaux propres 17,8 ; **trésorerie passif 18,5** | BNBC-FY25, BNBC-FY24, BNBC-9M26 |
| CFAC | 180,2 | 158,3 | 180,5 | 6,40 | 4,69 | 8,42 | 4,7 % | S1 : 91,8 (+0,7 %) / 3,96 (**−27 %**) | n.e. | CFAC-FY25, CFAC-FY24, CFAC-S126 |
| LNBB | 93,9 | 102,5 | 98,6 | 3,91 | 7,18 | 4,6 | 4,7 % | 9M : 77,95 (+7,5 %) / 1,78 (+72 %) | Capitaux propres 22,0 ; dettes financières 1,0 | LNBB-FY25, LNBB-FY24, LNBB-9M26 |
| NEIC | n.e. | n.e. | 5,14 | n.e. | n.e. | 2,04 (reprise de provision) | 39,6 % (non récurrente) | 9M : 3,16 (−7 %) / 0,09 (**−94 %**) | n.e. | NEIC-9M26 |
| PRSC | 77,9 | 74,7 | 81,1 | 2,08 | 2,35 | 2,37 | 2,9 % | S1 : 41,7 (+4,4 %) / 1,27 (−11,8 %) | Trésorerie actif 2,2 | PRSC-FY25, PRSC-FY24, PRSC-S126 |
| UNXC | n.e. | 27,3 | 29,0 | n.e. | −2,19 | −0,62 | −2,1 % | 9M : 22,5 (+0,0 %) / **+0,99** (contre −0,55) | Capitaux propres 24,6 ; dettes financières 1,0 | UNXC-FY25, UNXC-9M26 |
| CABC | 17,75 | 19,13 | 21,26 | 1,43 | 1,22 | 1,70 | 8,0 % | 9M : 17,57 (+5,6 %) / 0,14 (**−89 %**) | Dettes financières 3,8 | CABC-FY25, CABC-FY24, CABC-9M26 |
| FTSC | 38,2 | 30,7 | 32,1 | 3,08 | **18,60 (exceptionnel)** | 0,47 | 1,5 % | 9M : 25,7 (+40 %) / −0,35 (contre −0,25) | Dettes financières 3,8 | FTSC-FY25, FTSC-FY24, FTSC-9M26 |
| SDSC | n.e. | 85,6 | 92,0 | n.e. | 21,07 | **0,79** | 0,9 % | Aucun rapport 2026 publié. 9M 2025 : 66,2 (+7,4 %) / 4,34 (−77 %) | **Trésorerie nette ≈ +66,6** (76,8 − 8,2 − 2,0) ; capitaux propres 72,9 | SDSC-FY25, SDSC-FY24, SDSC-9M25 |
| SEMC | 27,87 | n.p. | n.p. | 1,01 | n.p. | n.p. | — | — | 2023 : trésorerie 3,5, sans dette ; capitaux propres 13,0 | SEMC-FY23 |
| SIVC | n.e. | 9,28 | 10,07 | n.e. | 0,377 | 0,179 | 1,8 % | n.p. | n.e. | SIVC-FY25 |
| STAC | n.e. | n.e. | 3,88 | −1,12 | −0,35 | −0,10 | <0 | 9M : 3,96 (+15 %) / −0,35 ; CA 2026 prévu par la société : 6,5 Md | **Capitaux propres 0,45 Md (2024)** | STAC-FY24, STAC-9M26 |

n.e. = non extrait (le document existe mais le chiffre n'a pas été lu) ; n.p. = non publié sur brvm.org à la date de l'étude.

---

## 4. Fiches par société

Format : identité, actionnaire de référence, marché, résultats, dividende, moteurs, risques, événements, verdict. Les sources de chaque fiche sont les étiquettes du §8.

### 4.1 Télécommunications (3)

#### SNTS — Sonatel (Sénégal ; opérations au Sénégal, au Mali, en Guinée, en Guinée-Bissau et en Sierra Leone)
- **Actionnariat** (fiche BRVM au 31/12/2019) : Orange MEA 42,3 %, État du Sénégal 27,2 %, personnel 7,3 %, flottant 23,2 %. Le flottant était de 23,9 % au 31/12/2025 (avis 303). [ISS-SNTS] Confiance medium, car l'actionnariat date de 2019.
- **Marché** : 4 040 FCFA, capitalisation 4 040 Md. C'est **la première capitalisation et de loin le titre le plus liquide** de la cote : 252 M FCFA échangés par séance en médiane en 2026, soit plus de 9 fois Orange CI. PER BOC 9,77 sur le RN total ; P/E part du groupe ≈ 11,8. [BOC]
- **Résultats** : CA 2025 de 1 923,1 Md (+8,3 %), EBITDAaL 921,2 Md (47,9 %), RN 413,6 Md dont 342,0 Md part du groupe, capex 288,6 Md (15 % du CA). Sur 9 mois 2026 : CA 1 583 Md (+10,5 %), EBITDAaL 769 Md (48,6 %), RN 354 Md (+12,9 %). Parc : 40,3 M de clients mobile, 14,4 M d'actifs Orange Money (+15,5 %), 710 000 clients fibre (+25,6 %). [SNTS-FY25 ; SNTS-9M26] Confiance high.
- **Dividende** : 1 740 FCFA net payé le 26/05/2026, soit 174 FCFA ajusté du split. La série 2021-2026 monte chaque année. [CAL25 ; BOC]
- **Événements** : fractionnement 10 pour 1 adopté par l'AGE du 08/10/2026, effectif le 26/10/2026 (réf. théorique 4 385 FCFA) [SNTS-9M26 ; `01-structure-marche.md` §8.1]. Licence unique de 10 ans en Guinée-Bissau (fibre et 5G). Licence IGW de 10 ans en Sierra Leone. [SNTS-9M26]
- **Moteurs** : data, Orange Money, fibre et haut débit fixe.
- **Risques** (cités par la société) : taxe sur la monnaie électronique au Sénégal ; gratuité de l'interopérabilité BCEAO pour les transferts de 0 à 8 000 FCFA, avec un plafond de 0,8 % au-delà ; dépréciation du franc guinéen ; coût de l'énergie ; concurrence. Il faut y ajouter le risque souverain sénégalais (voir `05-macro-geopolitique-uemoa.md`). [SNTS-9M26]
- **Verdict** : **n° 1 du classement**, mais **à égalité de fait avec STBC** (0,911 contre 0,910) si l'on calcule le PER sur le RN part du groupe, voir §5.2. Il cumule qualité (ROE part du groupe ≈ 29 %, trésorerie nette), valeur (rendement bénéficiaire ≈ 10 %) et croissance (+12,9 % de RN sur 9 mois). Sa liquidité est sans égale. Principal risque : la concentration sur le risque Sénégal-Mali.

#### ORAC — Orange Côte d'Ivoire (CI ; consolide Orange Burkina et Orange Liberia)
- **Actionnariat** : groupe Orange (pourcentage exact non vérifié dans les sources lues). Flottant 20,2 % (avis 303). Introduction en bourse en décembre 2022.
- **Marché** : 19 250 FCFA, capitalisation 2 900 Md, PER BOC 17,3 sur le RN total. P/E part du groupe ≈ 22,5 (BPA part du groupe 2025 de 857,2 FCFA). [ORAC-FY25]
- **Résultats** : CA de 1 016,5 Md (2023) à 1 084,1 Md (2024) puis 1 197,1 Md (2025, +10,4 %) ; RN de 154,9 à 158,2 puis 167,8 Md. Sur 9 mois 2026 : CA 1 012 Md (+15,5 %), EBITDAaL 360 Md (+18,0 %), RN 141 Md (+18,3 %). Croissance tirée par les trois pays, notamment l'accélération d'Orange Money au Liberia. [ORAC-9M26]
- **Dividende** : 800 FCFA brut pour l'exercice 2025 (704 net), payé le 08/06/2026. Il représente environ 93 % du RN part du groupe. [CAL25]
- **Bilan** : dette nette ≈ 110 Md, soit 0,16 fois les capitaux propres.
- **Risques** : intérêts minoritaires importants au Burkina et au Liberia, risque sécuritaire au Burkina Faso, fiscalité, énergie. Payout proche de 100 % du RN part du groupe.
- **Verdict** : n° 7 (n° 9 si le PER est calculé sur le RN part du groupe, voir §5.2). Croissance supérieure à celle de Sonatel en 2026, mais valorisation plus chère (P/E part du groupe ≈ 22,5 contre 11,8) et rendement plus faible (3,7 %).

#### ONTBF — Onatel / Moov Africa Burkina Faso (BF)
- **Actionnariat au 31/12/2025** : Maroc Telecom 61 %, **État burkinabè 16 %**, public 23 % (total 100 %), selon la « Composition du capital ONATEL-SA au 31-12-2025 » du rapport de gestion 2025 [ONTBF-RG25]. La fiche émetteur BRVM [ISS-ONTBF] affiche 26 % pour l'État (total 110 %) : c'est une **erreur de la fiche**. *(Corrigé le 22/11/2026.)* Confiance high.
- **Résultats** : CA de 139,2 Md (2023) à 141,8 Md puis 146,2 Md (2025) ; RN de 21,1 à 21,5 puis **15,9 Md (−26 %)**. Le résultat d'exploitation baisse de 24 % en 2025 : indemnités de fin d'engagement, location des poteaux de la SONABEL pour la fibre, énergie, maintenance dans les zones à défi sécuritaire. Sur 9 mois 2026 : CA 114,0 Md (+4,1 %), RN 10,5 Md (contre 11,0). [ONTBF-RG25 ; ONTBF-FY25 ; ONTBF-9M26]
- **Dividende** : payout de 70 % ; 166,08 FCFA brut, 145,32 net, payé le 15/06/2026. **En baisse continue depuis 2022.** [ONTBF-RG25 ; CAL25]
- **Risques** : environnement sécuritaire, sanction ARCEP de 1,543 Md (2023, en recours devant le Conseil d'État), endettement net d'environ 1 fois les capitaux propres, baisse des dividendes. [ONTBF-RG25]
- **Verdict** : n° 15. Rendement attractif (5,2 %), mais croissance du bénéfice négative et risque pays élevé.

### 4.2 Énergie et distribution pétrolière (4)

#### Lecture du secteur
La distribution pétrolière (TTLC, TTLS, SHEC) travaille avec des **marges nettes de 1 à 1,5 %** et des prix à la pompe administrés. La rentabilité dépend des effets de stock, des subventions (butane) et du volume. SMB est un **raffineur de bitume** : sa marge suit l'indicateur international de marge de raffinage et la demande routière régionale.

#### TTLC — TotalEnergies Marketing Côte d'Ivoire
- **Actionnariat** (fiche BRVM, 2014) : Total Outre-Mer 47,02 % et Total Africa 25,97 %, soit environ 73 %. Flottant 27,0 % (avis 303). [ISS-TTLC] Confiance medium.
- **Résultats** : CA de 578,9 Md (2023) à 621,0 Md puis 588,7 Md ; RN de 8,71 à 9,37 puis 9,09 Md ; EBE 2025 de 22,3 Md. Sur 9 mois 2026 : CA 501,2 Md (+14,4 %), RN 8,55 Md (+31,2 %), « principalement sous l'effet de la hausse des ventes ». Investissements prévus dans le GPL, les lubrifiants et de nouvelles stations. [TTLC-FY25 ; TTLC-9M26]
- **Dividende** : 10 Md brut pour l'exercice 2025, soit 158,83 FCFA par action (139,77 net) et 110 % du RN. Il était de 222,36 brut pour l'exercice 2024 ; la baisse 2026 est donc forte. [TTLC-FY25 ; CAL25 ; CAL24]
- **Verdict** : n° 6. Bonne dynamique 2026 et ROE ≈ 25 %. Le PER de 20,7 et le payout supérieur à 100 % limitent le potentiel.

#### TTLS — TotalEnergies Marketing Sénégal
- **Actionnariat** : TotalEnergies 69,1 % (23,1 % via TotalEnergies Marketing Afrique et 46 % via TotalEnergies Marketing African Holdings). Public 30,9 %. Réseau de 139 stations. [TTLS-9M26 ; ISS-TTLS] Confiance high.
- **Résultats** : CA de 499,2 Md (2023) à 484,9 Md puis 455,2 Md ; RN de 4,22 à 7,09 puis 6,15 Md. Sur 9 mois 2026 : CA 319,8 Md (−7 %, baisse des exportations et des prix à la pompe depuis décembre 2025) mais **RN 6,93 Md (+38 %)** grâce aux marges et aux effets de stock. [TTLS-FY25 ; TTLS-9M26]
- **Dividende** : 176,65 FCFA net (17/07/2026), soit environ 104 % du RN.
- **Risques** : effets de stock non récurrents, finances publiques sénégalaises (créances sur l'État et subventions : non quantifié ici).
- **Verdict** : n° 10. Bonne croissance du bénéfice, mais liquidité faible (6,6 M par séance).

#### SMBC — Société Multinationale de Bitumes (CI)
- **Actionnariat** : non vérifié. La fiche BRVM d'août 2021 ne donne qu'une répartition par catégorie (« compte émetteur » 48,23 %, personnes morales 40,91 %). Flottant 51,8 % (avis 303). Confiance low.
- **Résultats** : CA de 247,6 Md (2023) à 229,1 Md puis 206,7 Md ; RN de 17,26 à 8,70 puis 13,08 Md ; EBE 2025 de 18,5 Md. Sur 9 mois 2026 : **CA 179,2 Md (+15 %), RN 8,90 Md (+57 %)**, grâce à la hausse de la production et des ventes et à une « amélioration notable de l'indicateur international de marge de raffinage ». Perspectives à l'export jugées favorables (Nigeria, Ghana, Burkina Faso, Mali). [SMBC-FY25 ; SMBC-9M26]
- **Bilan** : **trésorerie nette de +14,8 Md**, capitaux propres 42,9 Md, ROE ≈ 30 %.
- **Dividende** : 800 brut (704 net) pour l'exercice 2025, soit un payout de 48 %. La société a de la marge pour augmenter.
- **Risques** : cyclicité de la marge de raffinage, prix du brut, dépendance aux budgets routiers des États. Le titre a déjà gagné 89 % en 2026.
- **Verdict** : **n° 3**. Meilleur rendement bénéficiaire prospectif du panel (≈ 14,6 %) et bilan sain. Le risque est cyclique, pas de solvabilité.

#### SHEC — Vivo Energy Côte d'Ivoire
- **Actionnariat** (fiche BRVM, 2014) : Vivo Energy CI Holdings BV 66,67 %, Petroci Holding 5 %. Flottant 28,3 %. [ISS-SHEC] Confiance medium.
- **Résultats** : CA de 550,7 Md (2023) à 600,7 Md puis 605,0 Md ; RN de 4,01 à 5,35 puis 6,03 Md. Sur 9 mois 2026 : CA 467,7 Md (+4 %), volumes −3 %, RN 4,75 Md (+15 %). Le résultat financier se dégrade (−2,7 Md) avec l'usage accru des découverts. [SHEC-FY25 ; SHEC-9M26]
- **Bilan** : **trésorerie passif de 70,3 Md** et dette nette d'environ 77 Md, pour des capitaux propres d'environ 27 Md, soit **un ratio de 2,8**. Le besoin en fonds de roulement est probablement lié aux subventions butane (hypothèse, à vérifier dans les annexes).
- **Dividende** : 96,67 brut pour l'exercice 2025 (6,09 Md, ≈ 101 % du RN).
- **Verdict** : n° 17. Bénéfice en croissance, mais levier élevé et payout de 100 %.

### 4.3 Services publics (2)

#### CIEC — Compagnie Ivoirienne d'Électricité
- **Actionnariat** (fiche BRVM au 31/12/2025) : Eranove SA 54,02 %. Flottant 45,9 %. [ISS-CIEC] Confiance high.
- **Activité** : en 2025, 13 035 GWh vendus et 5,28 M de clients. Au S1 2026, 5,54 M de clients (+13,3 %) et un temps moyen de coupure de 14 h 16 contre 11 h 36 un an plus tôt (dégradation). [CIEC-S126]
- **Résultats** (SYSCOHADA) : CA de 257,2 Md (2023) à 263,3 Md puis 302,3 Md ; RN de 10,63 à 10,10 puis 13,13 Md (+30 %). Au S1 2026 : CA 138,2 Md (+2,4 %), RN 5,34 Md (+4,8 %) ; en IFRS, RN S1 de 5,96 Md (+16 %). [CIEC-FY25 ; CIEC-S126]
- **Dividende** : 234 brut (13,1 Md, soit 100 % du RN) pour l'exercice 2025, contre 180 l'année précédente.
- **Risques** : concession (affermage) et tarifs fixés par l'État, croissance modeste en 2026, payout de 100 %. Le titre a gagné 86 % en 2026, ce qui fait monter le PER à 18,8.
- **Verdict** : n° 8. Qualité correcte, mais l'essentiel de la revalorisation est déjà fait.

#### SDCC — SODECI (eau)
- **Actionnariat** (fiche BRVM, 2014) : Finagestion 46,07 %. Flottant 49,5 % (2025). [ISS-SDCC] Confiance low (donnée ancienne).
- **Résultats** : CA de 175,5 Md (2023) à 172,2 Md puis 189,4 Md ; RN de 4,90 à 3,56 puis 4,66 Md ; EBE 2025 de 21,8 Md. En 2025 : 2,27 M de clients (+6,1 %), 388,3 Mm³ produits. Sur 9 mois 2026 : CA 126,5 Md (+1,5 %), RN 2,13 Md (+12,1 %), mais un résultat d'exploitation **négatif au 3e trimestre** (−0,68 Md). [SDCC-FY25 ; SDCC-9M26]
- **Événement clé** : le **nouveau contrat d'affermage de l'eau potable urbaine est en attente de notification**. Les « résultats de clôture tiendront compte des modalités retenues ». La société communiquera « sur les résultats de l'exercice et les besoins de financement ». Elle décrit sa trésorerie comme « sous tension ». [SDCC-9M26 ; SDCC-FY25]
- **Dividende** : 525 brut pour l'exercice 2025 (≈ 101 % du RN).
- **Verdict** : n° 16. **Risque binaire** lié au contrat (le titre a gagné 95 % en 2026, le marché anticipe donc un bon contrat), et un besoin de financement est possible. À éviter tant que le contrat n'est pas publié.

### 4.4 Agro-industrie et consommation de base (9)

#### NTLC — Nestlé Côte d'Ivoire
- **Actionnariat** (fiche BRVM, 2014) : Nestlé SA 79,56 % et Entreprises Maggi 6,94 %. Flottant 20,0 %. Confiance medium.
- **Résultats** : CA de 203,6 Md (2023) à 220,1 Md puis 233,3 Md ; RN de 16,56 à 18,15 puis 18,43 Md. Sur 9 mois 2026 : CA 192,5 Md (+11,0 %), résultat des activités ordinaires +8,6 %, **RN 11,99 Md (+0,4 %)**, freiné par le coût des matières premières et de l'énergie. Lancement de MILO au lait en juin 2026. [NTLC-FY25 ; NTLC-9M26]
- **Dividende** : **420 brut pour l'exercice 2025 contre 820 pour 2024**, soit un payout ramené de ≈ 100 % à ≈ 50 %. [CAL24 ; CAL25]
- **Verdict** : n° 13. Franchise solide, mais rendement réduit à 2,9 % et marges sous pression.

#### PALC — Palm CI (huile de palme)
- **Actionnariat** (fiche BRVM, 2014) : SIFCA 41,6 %, Nauvu Investments 25,5 %. Flottant 32,9 %. Confiance medium.
- **Résultats** : CA de 206,2 Md (2023) à 172,2 Md puis 197,6 Md ; RN de 19,35 à 15,86 puis 15,51 Md. Sur 9 mois 2026 : CA 174,9 Md (+4 %), RN 15,87 Md (−12 %, hausse des coûts d'approvisionnement). La société prévoit pour 2026 un RN « dans la même tendance que 2025 ». [PALC-FY25 ; PALC-9M26]
- **Bilan** : capitaux propres 142,6 Md, dette quasi nulle (0,8 Md), ROE ≈ 11 %.
- **Dividende** : 501,6 brut (payout ≈ 50 %), rendement net de 5,9 %.
- **Moteurs** : prix de l'huile de palme brute et coût des régimes achetés aux planteurs.
- **Verdict** : n° 9. **Titre le moins cher du panel** (PER 7,4, rendement bénéficiaire ≈ 12-13 %), sans dette. Pénalisé par un bénéfice en baisse en 2026 et un titre en recul de 8 % sur l'année. Bon candidat « valeur ».

#### SPHC — SAPH (caoutchouc naturel)
- **Actionnariat** (fiche BRVM, 2014) : SIPH 43,37 %, Binger Finance 24,69 %. Le rapport 9M 2026 indique « Filiale du Groupe SIFCA ». Flottant 59,5 % (2025). Confiance medium.
- **Résultats** : CA de 206,5 Md (2023) à 279,4 Md puis 340,8 Md ; RN de 3,64 à 18,79 puis 24,97 Md. **Sur 9 mois 2026 : CA 232,5 Md (−8 %), RN 9,70 Md (−58 %)**. En cause : volumes −9,5 % (congestion du port de San-Pedro), prix −0,6 % et concurrence accrue pour l'achat de caoutchouc aux planteurs. Les frais financiers montent avec les nouveaux emprunts. [SPHC-FY25 ; SPHC-9M26]
- **Dividende** : 489 brut pour l'exercice 2025 (payout 50 %). Le dividende de l'exercice 2026 sera probablement plus bas (inférence, pas une donnée publiée).
- **Verdict** : n° 11. Le PER de 7,8 sur 2025 est trompeur : avec un RN 2026 annualisé en baisse de 58 %, le P/E prospectif tourne autour de 18.

#### SOGC — SOGB (caoutchouc et palmier)
- **Actionnariat** (fiche BRVM, 2014) : Bereby Finances 65,17 % et autres entités, soit plus de 80 %. Flottant 26,8 %. Confiance medium.
- **Résultats** : CA 2025 de 99,0 Md ; RN de 5,27 Md (2023) à 13,11 puis 12,49 Md (marge 12,6 %). Sur 9 mois 2026 : CA 67,3 Md (−11 %), RN 7,62 Md (−34 %). L'hévéa recule (−17 %, volumes −18 %) ; le palmier progresse (+11 %). Un redressement des cours du caoutchouc est noté au 3e trimestre 2026. [SOGC-FY25 ; SOGC-9M26]
- **Bilan** : sans dette financière.
- **Dividende** : 570 brut (≈ 99 % du RN), rendement net de 6,6 %.
- **Verdict** : n° 4. Excellente qualité (marge, bilan, régularité des dividendes) et bon rendement. Le bénéfice 2026 baisse, mais moins que celui de la SAPH.

#### SCRC — Sucrivoire (sucre)
- **Actionnariat** : non vérifié dans les sources lues.
- **Résultats** : CA 2024 de 87,2 Md, puis 80,6 Md en 2025 ; RN 2025 de **−6,13 Md en SYSCOHADA et −7,95 Md en IFRS**. Au S1 2026 : CA 42,3 Md, EBE 7,08 Md (+77 %), RN −4,79 Md (contre −6,71). Campagne 2025/26 : 91 626 t produites (+16 %). [SCRC-S126 ; SCRC-FY25]
- **Bilan** : emprunts portés à 67,2 Md (contre 30,3 Md), pour des capitaux propres de 17,2 Md, soit environ 3,9 fois. Charges financières d'environ 7,6 Md par an. Une obligation SCRC.O1 au taux de 8,55 % (2024-2031) est cotée.
- **Événements** : suspendue le 16/09/2026 pour défaut d'information périodique ; levée de suspension annoncée le 21/09/2026 (avis 276), effective le **22/09/2026**, après publication du rapport du 1er trimestre 2026. Le cours est passé de 3 085 FCFA (15/09, +191 % depuis janvier) à 1 230 FCFA (20/11). [AVIS-269-2026 ; AVIS-276-2026 ; BOC]
- **Verdict** : n° 26. Redressement opérationnel réel, mais pertes et levier élevé. À considérer comme une option, pas comme un placement.

#### SLBC — Solibra (bières et boissons)
- **Actionnariat** (fiche BRVM, 2014) : BGI 81,61 %. Flottant 18,6 % (2025). Confiance medium.
- **Résultats** : CA et autres produits de 311,4 Md (2023) à 309,7 Md puis 378,1 Md (CA net 2025 de 335,9 Md) ; RN de 15,08 à 21,47 puis **45,78 Md**. Au S1 2026 : CA net 180,2 Md (+8,7 %), volumes +7,1 %, RN 28,10 Md (+0,5 %). L'entreprise poursuit son désendettement. [SLBC-FY25 ; SLBC-S126]
- **Dividende** : 2 127 brut pour l'exercice 2025 (35,0 Md, payout ≈ 76 %).
- **Événements** : fractionnement 10 pour 1 le 30/09/2024.
- **Verdict** : n° 5. Leader du marché, croissance des volumes et ROE ≈ 23 %. Le bénéfice se stabilise en 2026 après avoir doublé en 2025.

#### STBC — SITAB (tabac)
- **Actionnariat** (fiche BRVM au 31/12/2025) : Coralma International 59,92 %, ITWA 13,13 %, flottant 26,36 %. Le papier à en-tête porte « An Imperial Brands company ». [ISS-STBC ; STBC-9M26] Confiance high.
- **Résultats** : ventes de 169,4 Md (2023) à 213,8 Md puis 268,0 Md ; RN de 12,40 à 44,17 puis 36,46 Md. Au S1 2026 : CA 138,9 Md (+6,1 %), RN 17,91 Md (−0,9 %). Au 3e trimestre seul : CA 77,4 Md (+19,5 %, achats d'anticipation avant l'entrée en vigueur du **paquet neutre**), RN 8,67 Md (−33 %, hausse des coûts d'acquisition liée à la réglementation). **Cumul 9 mois : CA 216,3 Md (+10,5 %), RN 26,6 Md (−14,3 %).** Prix minimum de 1 000 FCFA le paquet depuis novembre 2024. [STBC-S126 ; STBC-9M26 ; STBC-FY25]
- **Bilan** : trésorerie de 30,8 Md, sans dette, ROE ≈ 80 %.
- **Dividende** : 1 940 brut (1 707,2 net), **rendement net de 8,0 %**.
- **Risques** : réglementation antitabac (paquet neutre, fiscalité, prix minimum), bénéfice 2026 en baisse, actionnariat très concentré.
- **Verdict** : **n° 2**. Rentabilité exceptionnelle, bilan net de dette, rendement de 8 % et deuxième liquidité du panel (47,6 M par séance). Le risque principal est réglementaire. C'est un titre de rendement, pas de croissance.

#### UNLC — Unilever Côte d'Ivoire
- **Actionnariat** (fiche BRVM, 2014) : Unilever Overseas Holding 89,98 %. **Flottant de 0,2 % au 31/12/2025**. Confiance high pour le flottant.
- **Information** : derniers états financiers publiés pour l'exercice 2023 (CA 34,7 Md, RN 0,64 Md). Aucun état financier 2024 ou 2025 sur brvm.org. Le PER BOC de 631 repose sur 2023. Cotation suspendue du 04/08/2025 au 01/09/2025, sans motif public. [UNLC-FY23 ; AVIS-189-2025 ; AVIS-213-2025]
- **Marché** : cours passé de 6 475 (fin 2024) à 34 225 (fin 2025) puis 44 000. Environ 1 M FCFA échangé par séance, spread médian de 4,3 %.
- **Verdict** : **exclu**. Le titre n'est pas valorisable (pas de comptes récents) et n'est pas négociable en taille.

#### SICC — SICOR (coco râpé)
- **Actionnariat** (fiche BRVM, 2014) : Société Devaco 70,44 %. Cotation **suspendue depuis le 16/09/2026** pour non-respect de l'information financière périodique. Dernier dividende en 2000. [AVIS-268-2026 ; ISS-SICC ; BOC]
- **Verdict** : **exclu**.

### 4.5 Consommation discrétionnaire (7)

#### ABJC — Servair Abidjan (restauration aérienne)
- **Actionnariat** (fiche BRVM, 2014) : SIA 85,66 %. Le document 2026 indique « a gategroup member ». Flottant 20 %. Confiance medium.
- **Résultats** : CA de 12,47 Md (2024) à 13,30 Md (2025) ; RN de 1,52 à 1,35 Md. Sur 9 mois 2026 : CA 10,69 Md (+4,6 %), RN 1,33 Md (+0,4 %). L'entreprise se met en conformité avec la réglementation des changes (facturation en devises). [ABJC-FY25 ; ABJC-9M26]
- **Bilan** : trésorerie nette d'environ 4 Md, capitaux propres de 5,2 Md, ROE ≈ 26 %.
- **Dividende** : **229 brut (2,5 Md), soit 185 % du RN 2025**. Les états provisoires proposaient 1,5 Md ; l'avis 244-2026 publie 229 brut par action. Écart non expliqué.
- **Verdict** : n° 12. Société de qualité, mais petite et avec un dividende non soutenable à ce niveau.

#### BNBC — Bernabé Côte d'Ivoire (distribution de matériaux et d'équipement)
- **Actionnariat** (fiche BRVM, 2014) : Yeshi Group 60,45 %. Confiance low (donnée ancienne).
- **Résultats** : CA d'environ 45 Md stable de 2023 à 2025 ; RN quasi nul (0,02 Md en 2025). Sur 9 mois 2026 : CA 36,1 Md (+13 %, intégration de l'activité Équipement), RN 0,139 Md. Trésorerie passif de 18,5 Md. [BNBC-FY25 ; BNBC-9M26]
- **Verdict** : n° 24. PER de 519 et rendement BOC de 8,57 % périmé (2023).

#### CFAC — CFAO Mobility Côte d'Ivoire (distribution automobile)
- **Actionnariat** (fiche BRVM, 2019) : CFAO 95,85 %. **Flottant de 4,2 % (2025), sous le seuil.** Confiance medium.
- **Résultats** : CA de 180,2 Md (2023) à 158,3 Md puis 180,5 Md ; RN de 6,40 à 4,69 puis 8,42 Md (+79 %). Au S1 2026 : CA 91,8 Md (+0,7 %), RN 3,96 Md (−27 %). Part de marché de 41,6 % en 2025 et de 38 % au S1 2026 : Suzuki est la première marque, Toyota la deuxième. [CFAC-FY25 ; CFAC-S126]
- **Dividende** : 63 brut pour l'exercice 2025 (11,4 Md, ≈ 136 % du RN).
- **Verdict** : n° 21. Flottant insuffisant, bénéfice en baisse et payout supérieur à 100 %.

#### LNBB — Loterie Nationale du Bénin (BJ)
- **Actionnariat** : État béninois. Le pourcentage n'est pas vérifié ; un flottant de 45 % implique environ 55 % pour l'État. Introduction en bourse en décembre 2024.
- **Résultats** : CA de 93,9 Md (2023) à 102,5 Md puis 98,6 Md ; RN de 3,91 à 7,18 puis 4,6 Md (−36 %, absence de produits exceptionnels). Sur 9 mois 2026 : CA 77,95 Md (+7,5 % ; paris en ligne +36 %, soit 48 % du CA), taux de retour aux joueurs de 82,1 % contre 78,7 %, produit brut des jeux −9,7 %, mais **RN 1,78 Md (+72 %)** grâce à la baisse des charges. [LNBB-FY25 ; LNBB-9M26]
- **Dividende** : 164,17 net pour l'exercice 2025 (275,5 pour 2024).
- **Verdict** : n° 14. Croissance du bénéfice en 2026, mais qualité moyenne (taux de retour en hausse, bénéfice volatil) et liquidité faible.

#### NEIC — NEI-CEDA (édition scolaire)
- **Actionnariat** (fiche BRVM, 2014) : Education Management 41,72 %, Hachette Livre International (Edicef) 15,22 %, État de Côte d'Ivoire 10,50 %. Confiance low.
- **Résultats** : CA 2025 de 5,14 Md ; RN 2025 de 2,04 Md, gonflé par une reprise de provision. Sur 9 mois 2026 : CA 3,16 Md (−7 %), **RN 0,09 Md (−94 %)**. [NEIC-9M26]
- **Verdict** : n° 23. Le PER de 11,9 et le rendement de 7,4 % reposent sur un bénéfice non récurrent. Piège de valeur.

#### PRSC — Tractafric Motors Côte d'Ivoire
- **Actionnariat** (fiche BRVM, 2019) : Tractafric Motors Corporation 85,94 %. L'avis 303-2026 déclare un **flottant de 100 %**, une donnée incohérente avec la fiche émetteur. Confiance low.
- **Résultats** : CA de 77,9 Md (2023) à 74,7 Md puis 81,1 Md ; RN de 2,08 à 2,35 puis 2,37 Md. Au S1 2026 : CA 41,7 Md (+4,4 %), RN 1,27 Md (−11,8 %). [PRSC-FY25 ; PRSC-S126]
- **Dividende** : 209 brut pour l'exercice 2025 (payout 90 %). C'est la série de dividendes la plus régulière de la cote discrétionnaire.
- **Verdict** : n° 19. Société stable, mais liquidité très faible (3,3 M par séance).

#### UNXC — Uniwax (textile wax)
- **Actionnariat** (fiche BRVM, 2014) : Fragéci 78,04 %, Vlisco 2,94 %. Confiance low.
- **Résultats** : CA de 27,3 Md (2024) à 29,0 Md (2025) ; RN de −2,19 à −0,62 Md. Sur 9 mois 2026 : CA 22,5 Md (stable ; la marque Woodin a été cédée, avec un impact de −0,51 Md), **RN +0,99 Md contre −0,55 Md**, porté par les volumes, le mix et la maîtrise des coûts. [UNXC-FY25 ; UNXC-9M26]
- **Verdict** : n° 27 sur les données 2025, car le score est rétrospectif. **À surveiller** comme cas de redressement : le passage en bénéfice en 2026 n'est pas encore capturé par le RN annuel.

### 4.6 Industriels (6)

#### CABC — Sicable (câbles électriques)
- **Actionnariat** (fiche BRVM au 31/12/2025) : Prysmian Câbles et Systèmes France 51 %. Flottant 49 %. [ISS-CABC] Confiance high.
- **Résultats** : CA de 17,75 Md (2023) à 19,13 Md puis 21,26 Md ; RN de 1,43 à 1,22 puis 1,70 Md. **Sur 9 mois 2026 : CA 17,57 Md (+5,6 % ; négoce +52 %, fabrication −13 %), RN 0,14 Md (−89 %)**. En cause : un arrêt de maintenance planifié, la congestion portuaire et la hausse des matières premières (cuivre). [CABC-FY25 ; CABC-9M26]
- **Dividende** : 152,02 net (01/06/2026).
- **Verdict** : n° 20. Le bénéfice 2026 s'effondre.

#### FTSC — Filtisac (sacs en jute et polypropylène)
- **Actionnariat** (fiche BRVM, 2014) : AKFED 35,81 %, IPS (WA) 10 % et autres. Confiance low.
- **Résultats** : CA de 38,2 Md (2023) à 30,7 Md puis 32,1 Md ; RN de 3,08 Md à **18,60 Md en 2024 (plus-value : les immobilisations financières passent de 11,1 à 1,4 Md)** puis 0,47 Md en 2025. Sur 9 mois 2026 : CA 25,7 Md (+40 %), RN −0,35 Md, plombé par les frais financiers. La société attend une reconstitution des marges pendant la campagne du 4e trimestre. [FTSC-FY24 ; FTSC-FY25 ; FTSC-9M26]
- **Dividende** : pour l'exercice 2024, 2 000,67 FCFA brut (1 320 ordinaire + 680,67 exceptionnel, IRVM de 17 % sur la part exceptionnelle), soit 1 726,56 net le 30/09/2025. **Le rendement BOC de 107,91 % est un artefact.** Aucun dividende pour l'exercice 2025. [CAL24]
- **Verdict** : n° 25.

#### SDSC — Africa Global Logistics Côte d'Ivoire (ex Bolloré Transport & Logistics CI)
- **Actionnariat** (fiche BRVM, 2022) : Africa Global Logistics (France) 74,80 %. Flottant 25 %. Le contrôle ultime du groupe AGL n'est pas vérifié dans les sources lues.
- **Résultats** : CA de 85,6 Md (2024) à 92,0 Md (2025) ; RN de **21,07 Md à 0,79 Md**. Le résultat d'exploitation passe à −2,27 Md, et le résultat financier tombe de 20,9 à 7,1 Md parce que les filiales ont versé moins de dividendes. Sur 9 mois 2025 : RN −77 %. [SDSC-FY25 ; SDSC-9M25]
- **Bilan** : trésorerie de 76,8 Md, capitaux propres de 72,9 Md. **Attention (vérification du 22/11/2026)** : la trésorerie a été multipliée par 3,6 en un an (21,2 → 76,8 Md) surtout parce que les **dettes d'exploitation** sont passées de 96,4 à 175,7 Md (« variation du passif circulant » de +79,8 Md dans le tableau des flux). La CAF n'est que de 7,5 Md. Cette trésorerie n'est donc pas un excédent disponible : le bonus « trésorerie nette » du score qualité est **trompeur** pour SDSC. Il faut le neutraliser quand la variation du passif circulant dépasse la trésorerie nette. [SDSC-FY25]
- **Dividende** : 92 par action maintenu (5,0 Md), payé le 27/10/2026 sur le report à nouveau.
- **Information** : aucun rapport trimestriel 2026 trouvé sur brvm.org. États 2025 certifiés publiés le 17/09/2026.
- **Verdict** : n° 18. Le titre a gagné 77 % en 2026 alors que le RN 2025 est quasi nul. Le marché parie peut-être sur une opération sur le capital ou sur les actifs (hypothèse non vérifiée). La trésorerie affichée vient surtout de la hausse des dettes d'exploitation (voir Bilan) : ce n'est pas un excédent de cash.

#### SEMC — Sonoco Metal Packaging SIEM (ex Eviosys, ex Crown SIEM ; emballages métalliques)
- Derniers comptes publiés : exercice 2023 (CA 27,9 Md, RN 1,01 Md), approuvés par l'AGO du 30/12/2024. Suspendue du 29/07/2025 au 02/01/2026, puis **de nouveau depuis le 16/09/2026** pour défaut d'information périodique. Flottant de 10,3 %. Actionnaire en 2014 : Crown European Holdings, 85,24 %. [SEMC-FY23 ; AVIS-179-2025 ; AVIS-004-2026 ; AVIS-270-2026 ; ISS-SEMC]
- **Verdict** : **exclu**.

#### SIVC — Erium CI (ex Air Liquide CI ; gaz industriels et médicaux)
- **Actionnariat** : Air Liquide International détenait 72,08 % en 2014. Le repreneur actuel n'est pas vérifié dans les sources lues.
- **Résultats** : CA de 9,28 Md (2024) à 10,07 Md (2025) ; RN de 0,38 à 0,18 Md. Rapports 2025 très tardifs (T1 2025 publié le 19/12/2025). Aucun dividende depuis 2017. [SIVC-FY25]
- **Verdict** : n° 22.

#### STAC — SETAO (BTP, groupe Bouygues)
- **Actionnariat** (fiche BRVM, 2014) : Bouygues Bâtiment International 78,61 %. Confiance medium.
- **Résultats** : pertes chaque année de 2023 à 2026 (RN de −1,12, −0,35 et −0,10 Md, puis −0,35 Md sur 9 mois 2026) ; capitaux propres de 0,45 Md fin 2024. La société vise un CA 2026 de 6,5 Md avec la phase II du CHU de Yopougon. [STAC-9M26 ; STAC-FY24]
- **Verdict** : n° 28. Spéculatif (+64,5 % en 2026, sans bénéfice).

---

## 5. Classement par attractivité

### 5.1 Méthode (reproductible ; script `score.py` du bac à sable, à porter dans `brvm_alpha/quant/scoring.py`)

Pour chaque titre $i$ :
- **Qualité** $q_i$ = 1[RN25 > 0] − nombre d'exercices en perte entre 2023 et 2025 + bonus de bilan (trésorerie nette +1 ; DN/CP < 1 : +0,5 ; inconnu : 0 ; DN/CP ≥ 1 : −0,5) + (années avec dividende payé de 2021 à 2026)/6 + 4 × min(max(marge nette 2025 ; 0) ; 0,25) − 0,5 par drapeau de risque (contrat, réglementation, information, bénéfice non récurrent, flottant).
- **Valeur** $v_i$ = 0,6 × $EY^{fwd}_i$ + 0,4 × $DY_i$, avec $EY^{fwd}$ = (1/PER BOC) × (1 + variation du RN cumulé 2026 sur un an), borné à 0, et $DY$ = dividende net de l'exercice 2025 / cours.
- **Croissance** $g_i$ = 0,5 × TCAM du RN 2023→2025 (borné à [−50 % ; +60 %]) + 0,5 × variation du RN cumulé 2026 (bornée à [−60 % ; +80 %]).
- **Liquidité** $l_i$ = ln(1 + valeur médiane échangée par séance en 2026, en M FCFA).
- Chaque dimension est transformée en **rang percentile** $P \in (0, 1]$ sur les 31 titres.
- **Score** = $\exp\big(0{,}35 \ln \max(P_Q, 0{,}05) + 0{,}30 \ln \max(P_V, 0{,}05) + 0{,}20 \ln \max(P_G, 0{,}05) + 0{,}15 \ln \max(P_L, 0{,}05)\big)$, une moyenne géométrique pondérée qui pénalise la faiblesse dans une seule dimension.
- **Exclusion** (score = 0) : titre suspendu, ou flottant inférieur à 1 % combiné à une information financière périmée.

### 5.2 Résultat

| Rang | Symb. | P_Q | P_V | P_G | P_L | Score | EY fwd % | DY net % | Perf. 12 mois (prix) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | SNTS | 1.00 | 0.94 | 0.77 | 1.00 | **0.931** | 11.6 | 4.3 | +58 % |
| 2 | STBC | 0.87 | 0.90 | 0.90 | 0.97 | **0.901** | 8.2 | 8.0 | +9 % |
| 3 | SMBC | 0.94 | 1.00 | 0.87 | 0.61 | **0.883** | 14.6 | 3.9 | +83 % |
| 4 | SOGC | 0.97 | 0.71 | 0.71 | 0.74 | **0.796** | 5.0 | 6.6 | −5 % |
| 5 | SLBC | 0.71 | 0.77 | 0.97 | 0.68 | **0.770** | 6.9 | 4.6 | +42 % |
| 6 | TTLC | 0.81 | 0.74 | 0.81 | 0.65 | **0.761** | 6.3 | 4.7 | +26 % |
| 7 | ORAC | 0.77 | 0.68 | 0.74 | 0.94 | **0.759** | 6.8 | 3.7 | +31 % |
| 8 | CIEC | 0.84 | 0.52 | 0.68 | 0.87 | **0.699** | 5.6 | 4.7 | +67 % |
| 9 | PALC | 0.61 | 0.97 | 0.42 | 0.84 | **0.683** | 11.9 | 5.9 | −7 % |
| 10 | TTLS | 0.52 | 0.84 | 0.94 | 0.29 | **0.617** | 8.0 | 4.9 | +43 % |
| 11 | SPHC | 0.58 | 0.61 | 0.58 | 0.77 | **0.616** | 5.4 | 5.6 | +2 % |
| 12 | ABJC | 0.90 | 0.48 | 0.52 | 0.35 | **0.582** | 4.1 | 6.7 | +26 % |
| 13 | NTLC | 0.65 | 0.45 | 0.61 | 0.58 | **0.565** | 6.5 | 2.9 | +11 % |
| 14 | LNBB | 0.32 | 0.87 | 1.00 | 0.39 | **0.560** | 10.2 | 4.2 | +1 % |
| 15 | ONTBF | 0.45 | 0.81 | 0.45 | 0.48 | **0.543** | 7.3 | 5.2 | +13 % |
| 16 | SDCC | 0.35 | 0.65 | 0.65 | 0.42 | **0.491** | 6.5 | 4.1 | +88 % |
| 17 | SHEC | 0.29 | 0.58 | 0.84 | 0.45 | **0.472** | 5.9 | 4.6 | +32 % |
| 18 | SDSC | 0.74 | 0.32 | 0.19 | 0.90 | **0.455** | 0.5 | 3.4 | +79 % |
| 19 | PRSC | 0.55 | 0.55 | 0.55 | 0.13 | **0.441** | 5.5 | 4.9 | −6 % |
| 20 | CABC | 0.68 | 0.35 | 0.39 | 0.19 | **0.413** | 1.0 | 5.6 | +24 % |
| 21 | CFAC | 0.39 | 0.42 | 0.48 | 0.16 | **0.364** | 2.8 | 4.7 | −21 % |
| 22 | SIVC | 0.23 | 0.29 | 0.19 | 0.55 | **0.270** | 1.3 | 0.0 | +130 % |
| 23 | NEIC | 0.48 | 0.39 | 0.03 | 0.23 | **0.256** | 0.5 | 7.4 | +101 % |
| 24 | BNBC | 0.26 | 0.26 | 0.35 | 0.10 | **0.237** | 0.2 | 0.0 | +25 % |
| 25 | FTSC | 0.42 | 0.13 | 0.19 | 0.26 | **0.235** | 0.0 | 0.0 | −30 % |
| 26 | SCRC | 0.10 | 0.13 | 0.19 | 0.81 | **0.167** | 0.0 | 0.0 | +23 % |
| 27 | UNXC | 0.06 | 0.13 | 0.19 | 0.71 | **0.142** | 0.0 | 0.0 | +19 % |
| 28 | STAC | 0.03 | 0.13 | 0.19 | 0.52 | **0.124** | 0.0 | 0.0 | +90 % |
| — | SICC | — | — | — | — | **exclu** (suspendu) | — | — | +135 % |
| — | UNLC | — | — | — | — | **exclu** (flottant 0,2 %, comptes 2023) | — | — | +15 % |
| — | SEMC | — | — | — | — | **exclu** (suspendu) | — | — | +114 % |

La performance sur 12 mois est calculée du 20/11/2025 au 20/11/2026, en prix seul, à partir du panel BOC. Pour SNTS, le cours de 2025 est divisé par 10.

**Robustesse** : la corrélation de rang de Spearman entre ce classement et quatre variantes reste **≥ 0,986**. Variantes testées : poids égaux (0,991), score additif au lieu de géométrique (0,992), valeur surpondérée à 45 % (0,989), sans liquidité (0,986). Le trio de tête (SNTS, STBC, SMBC) ne change dans aucune variante : sans la liquidité, SMBC passe premier.

**Limite de ce test et sensibilité à la définition du PER (vérification du 22/11/2026).** Le vérificateur a recalculé les variantes à partir des rangs percentiles publiés ci-dessus et retrouve 0,990, 0,993, 0,991 et 0,986. Mais ces variantes ne font que **repondérer les mêmes rangs** : une corrélation élevée est presque mécanique et ne dit rien du pouvoir prédictif. Le classement est plus sensible à la **définition des entrées**. Le PER BOC de SNTS (9,77) et d'ORAC (17,28) porte sur le RN **total**, intérêts minoritaires compris (anomalie A1). Avec le RN **part du groupe**, comme le recommande A1, l'EY prospectif tombe à 9,6 % pour SNTS (au lieu de 11,6 %) et à 5,3 % pour ORAC (au lieu de 6,8 %). Les scores deviennent alors : **SNTS 0,911 et STBC 0,910 (égalité de fait)**, SMBC 0,884, et ORAC recule du 7e au 9e rang (0,671). Le rang n° 1 de SNTS n'est donc **pas robuste** à la définition du PER. Calcul du vérificateur, avec les autres entrées inchangées.

### 5.3 Justification du haut de classement, et pourquoi il ne faut pas acheter aveuglément

1. **SNTS** : la seule valeur qui est à la fois de grande qualité, peu chère (PER 9,8) et en croissance à deux chiffres, avec une liquidité institutionnelle. Le risque est concentré sur la dette souveraine du Sénégal et sur la réglementation du mobile money.
2. **STBC** : rendement de 8 %, aucune dette, ROE ≈ 80 %. **Mais** le bénéfice 2026 baisse de 14 % et le paquet neutre pèse sur les coûts ; la valeur est « défensive mais régulée ».
3. **SMBC** : le bénéfice 2026 progresse de 57 % et le bilan affiche une trésorerie nette. **Mais** l'activité est cyclique (marge de raffinage) et le titre a déjà gagné 89 % en 2026, un risque de retour à la moyenne.
4. **SOGC** et **PALC** sont les deux « valeurs agricoles » sans dette. Leurs bénéfices 2026 baissent (−34 % et −12 %) : ils conviennent à un investisseur à contre-courant qui anticipe un rebond des cours du caoutchouc et de l'huile de palme. SOGB signale un rebond des cours du caoutchouc au 3e trimestre 2026.
5. **Pièges identifiés** (rendement ou PER trompeurs) : FTSC (107,9 % de rendement affiché), NEIC (bénéfice non récurrent), BNBC (rendement 2023), SPHC (PER 2025 bas mais bénéfice −58 %), SDSC (dividende pris sur les réserves), SDCC (contrat non signé).
6. **Momentum 2026 sans fondamentaux** : SIVC (+130 % sur 12 mois), STAC (+90 %), NEIC (+101 %) et les titres suspendus SICC et SEMC. Ce sont des hausses spéculatives sur des titres peu liquides : la plate-forme **ne doit pas** les poursuivre sur la base du seul momentum.

---

## 6. Anomalies et pièges de données relevés (à traiter dans le code)

| # | Anomalie | Impact | Traitement proposé |
|---|---|---|---|
| A1 | Le **PER du BOC** utilise le RN total consolidé (SNTS, ORAC), mais parfois un autre agrégat : ONTBF affiche 13,14 alors que le calcul sur le RN 2025 donne 12,0 ; CABC affiche 11,19 contre 9,5 calculé | Biais de valeur de ±15 % | Recalculer P/E = capitalisation / RN (part du groupe si disponible) à partir de la table des fondamentaux ; garder le PER BOC comme contrôle |
| A2 | **Rendement BOC** = dernier dividende payé / cours, quelle que soit sa date (FTSC 107,9 %, BNBC 8,6 % de 2023) | Faux signaux « haut rendement » | **Corrigé le 22/11/2026.** DY_t = DPS net ordinaire de l'exercice k / cours, où k est le **dernier exercice dont l'AGO (affectation du résultat) est connue à la date t**. Si cette AGO n'a voté aucun dividende, DY = 0. Le plafond de 15 mois ne sert que de garde-fou contre les données périmées. **Un critère « dernier dividende ordinaire payé dans les 15 mois » seul ne suffit pas.** Filtisac a payé 1 320 FCFA brut ordinaires le 30/09/2025, soit 13,7 mois avant le 20/11/2026 : ce critère seul donnerait DY ≈ 72,6 % (1 161,6 net / 1 600), alors que l'exercice 2025 ne verse rien. Ajouter aussi un drapeau si DY > 15 %. |
| A3 | **Dividende exceptionnel** : Filtisac, part exceptionnelle de 680,67 brut taxée à 17 % | Rendement surestimé | Champ `div_type ∈ {ordinaire, exceptionnel}` alimenté par le calendrier (marque « # ») |
| A4 | **Fractionnements** : SNTS 10:1 au 26/10/2026, SLBC 10:1 au 30/09/2024 | Ruptures de série des dividendes et des cours | Ajuster les DPS historiques avec le facteur de split (le panel `corporate_actions.parquet` les détecte) |
| A5 | Rapport « trimestriel » qui couvre **le trimestre seul** (SITAB, « Trimestre 3 ») et non le cumul | Croissance faussée (−33 % au lieu de −14 %) | Normaliser en cumul depuis le début d'année (S1 + T3) ; contrôler que le CA cumulé est ≥ au CA du S1 |
| A6 | Double référentiel SYSCOHADA / IFRS (CIE, Sucrivoire, Servair, Sicable) | RN différents : SCRC −6,13 contre −7,95 | Champ `gaap` ; préférer SYSCOHADA pour la comparabilité, car tous les émetteurs le publient |
| A7 | Ordre des colonnes inversé (Solibra 2025 : N−1 avant N) | Erreur de signe sur la croissance | Contrôle croisé avec le rapport d'activité (RN 2025 = 45,78 Md, confirmé par SLBC-S126) |
| A8 | Fiches émetteurs BRVM périmées (2014-2019) ou incohérentes (ONTBF à 110 %) | Actionnariat erroné | Date de validité par champ ; alerte si plus de 3 ans |
| A9 | Flottant déclaré de 100 % pour PRSC contre 14 % selon la fiche 2019 | Filtre de flottant faussé | Prendre le minimum des deux sources, avec un drapeau |
| A10 | Servair : dividende proposé de 1,5 Md dans les états provisoires contre 2,5 Md publiés (229 brut × 10,9 M titres) | Calcul de payout | Toujours prendre le montant de l'avis BRVM et du calendrier, qui fait foi |
| A11 | Rapports scannés sans texte (environ 25 sur 98) | L'extraction automatique échoue | Prévoir l'OCR (tesseract n'est pas installé dans l'environnement actuel) ou une saisie manuelle validée |
| A12 | *(Ajouté le 22/11/2026.)* La colonne « Dernier dividende payé » du BOC est mise à jour dès la ligne **(d)**, c'est-à-dire le **dernier jour avec dividende** (exemple : SNTS au BOC du 21/05/2026, alors que le titre cote ex-dividende le 22/05). La ligne (d) donne aussi la référence ajustée dans « Cours référence » (27 160 = 28 900 − 1 740) | Prendre la date de changement de cette colonne comme date ex décale tout d'un jour | Date ex = séance qui suit la ligne (d), ou la colonne « Ex-dividende » du calendrier officiel |
| A13 | *(Ajouté le 22/11/2026.)* Calendrier CAL25 : Tractafric Motors affiche une date ex (23/10/2026) **postérieure** à la date de paiement (22/10/2026) | Erreur de saisie dans la source officielle | Contrôle de cohérence `ex_date < payment_date`. En cas d'écart, la date du BOC fait foi (BOC du 20/11 : dernier dividende daté du 23/10/2026) |
| A14 | *(Ajouté le 22/11/2026.)* Après le fractionnement de SLBC, le BOC n'a pas ajusté le dividende de 4 050 FCFA : il affiche un rendement de 36,9 % le 30/09/2024. Pour SNTS en 2026, le BOC l'a ajusté (174) | Rendement BOC faux juste après un fractionnement | Toujours recalculer le DPS avec le facteur de split |

---

## 7. Implications pour la plate-forme (paramètres prêts à coder)

### 7.1 Univers et éligibilité

```yaml
universe_nonfin:
  as_of: "2026-11-20"
  symbols: [SNTS, ORAC, ONTBF, TTLC, TTLS, SMBC, SHEC, CIEC, SDCC, NTLC, PALC, SPHC, SOGC,
            SCRC, SLBC, STBC, UNLC, SICC, ABJC, BNBC, CFAC, LNBB, NEIC, PRSC, UNXC,
            CABC, FTSC, SDSC, SEMC, SIVC, STAC]
  exclude_if:
    status_in: [suspended]                 # SICC, SEMC au 20/11/2026 (BOC : « SP »)
    free_float_pct_lt: 5.0                 # choix du projet : UNLC 0,22 % ; CFAC 4,15 % (ou poids plafonné à 1 %)
    # CORRIGÉ 22/11/2026 : « 400 jours » était ambigu. Mesuré depuis la clôture de l'exercice,
    # il excluait TOUTE la cote du 04/02 jusqu'à la publication des comptes N-1 (mars-juin).
    last_annual_fs_period_end_age_days_gt: 546   # = 30/06 de N+1 pour l'exercice N-1 ; UNLC, SEMC (exercice 2023) exclus
    median_daily_value_mfcfa_lt: 2.0       # BNBC 2,7 est juste au-dessus du seuil (médianes 2026 recalculées : conformes)
  flags:
    free_float_below_regulatory_15pct: [UNLC, CFAC, SEMC, SICC]   # avis 303-2026 : seuil réglementaire de diffusion = 15 %
    payout_gt_100pct_2y: [TTLC, SHEC, SDCC, ABJC, CFAC, SDSC]
    regulatory_event: {SDCC: "contrat d'affermage en attente", STBC: "paquet neutre", SNTS: "taxe e-money / interopérabilité BCEAO"}
    nonrecurring_earnings: [NEIC, FTSC]
    stale_yield: [FTSC, BNBC, SCRC, UNXC, STAC, SEMC]
    reporting_delay: [SDSC, SIVC]
```

### 7.2 Score d'attractivité (valeurs par défaut validées ici, à soumettre au walk-forward)

```yaml
fundamental_score:
  weights: {quality: 0.35, value: 0.30, growth: 0.20, liquidity: 0.15}
  aggregation: geometric            # moyenne géométrique pondérée des rangs percentiles
  pct_floor: 0.05
  quality:
    profit_positive_bonus: 1.0
    loss_year_penalty: -1.0          # par exercice en perte sur 3 ans
    balance_sheet: {net_cash: 1.0, nd_eq_lt_1: 0.5, unknown: 0.0, nd_eq_ge_1: -0.5}
    dividend_years_window: 6         # années de paiement / 6
    margin_weight: 4.0               # × min(max(marge, 0), 0.25)
    risk_flag_penalty: -0.5          # par drapeau (contrat, réglementation, info, non récurrent, flottant)
  value:
    # CORRIGÉ 22/11/2026 : PER = capitalisation / RN PART DU GROUPE (anomalie A1), pas le PER BOC
    # (calculé sur le RN total pour SNTS et ORAC). Sensibilité : SNTS et STBC à égalité (§5.2).
    ey_forward: "(net_income_group / market_cap) * (1 + yoy_ytd_net_income)"   # borné à >= 0
    w_ey_forward: 0.6
    w_div_yield: 0.4
    # CORRIGÉ 22/11/2026 : exercice k = dernier exercice dont l'AGO est connue à t ; DY = 0 si
    # elle n'a voté aucun dividende ; garde-fou : DY = 0 si le paiement a plus de 15 mois.
    # Seul, le critère « dernier dividende ordinaire < 15 mois » donne FTSC ≈ 72,6 % au 20/11/2026.
    div_yield: "dps_net_ordinary(last_fy_with_known_AGM(t)) / price"
    div_yield_max_age_months: 15
    div_yield_flag_gt: 0.15
  growth:
    w_cagr_ni_3y: 0.5                # TCAM du RN N-2 -> N, borné à [-0.5, 0.6]
    w_yoy_ytd_ni: 0.5                # cumul de l'année en cours, borné à [-0.6, 0.8]
  liquidity: "log1p(median_daily_value_mfcfa_current_year)"
  robustness_check: {min_spearman_vs_variants: 0.95}   # observé : 0.986-0.992 (recalculé par le vérificateur : 0.986-0.993)
  rebalance: event_driven_fundamentals_plus_fixed_review   # CORRIGÉ 22/11/2026, voir 7.4
  quality_net_cash_guard: "net_cash bonus = 0 si Δ passif circulant > trésorerie nette"   # ajouté 22/11/2026 (cas SDSC)
```

### 7.3 Table de fondamentaux : schéma et données de départ (Md FCFA)

Schéma : `symbol, fiscal_year, period (FY|9M|S1|Q), gaap (SYSCOHADA|IFRS), revenue, net_income, net_income_group, equity, net_debt, dps_gross, dps_net, div_type, source_url, published_date, confidence`.

```csv
symbol,ni_2023,ni_2024,ni_2025,rev_2025,ytd_period,ytd_ni_yoy,net_debt_2025,equity_2025,dps_gross_fy25,payout_fy25
SNTS,331.7,393.7,413.6,1923.1,9M,0.129,-113.3,1399.3,193.3,0.57
ORAC,154.9,158.2,167.8,1197.1,9M,0.183,110.1,707.8,800,0.93
ONTBF,21.13,21.47,15.89,146.18,9M,-0.045,59.1,57.5,166.08,0.70
TTLC,8.71,9.37,9.09,588.7,9M,0.312,25.4,36.2,158.827,1.10
TTLS,4.22,7.09,6.15,455.2,9M,0.380,,20.7,196.3,1.04
SMBC,17.26,8.70,13.08,206.7,9M,0.570,-14.8,42.9,800,0.48
SHEC,4.01,5.35,6.03,605.0,9M,0.150,77.2,27.2,96.67,1.01
CIEC,10.63,10.10,13.13,302.3,S1,0.048,32.1,36.0,234,1.00
SDCC,4.90,3.56,4.66,189.4,9M,0.121,,,525,1.01
NTLC,16.56,18.15,18.43,233.3,9M,0.004,,,420,0.50
PALC,19.35,15.86,15.51,197.6,9M,-0.120,0.8,142.6,501.596,0.50
SPHC,3.64,18.79,24.97,340.8,9M,-0.580,,137.9,489,0.50
SOGC,5.27,13.11,12.49,99.0,9M,-0.340,,,570,0.99
SCRC,,2.47,-6.13,80.6,S1,,,17.2,0,
SLBC,15.08,21.47,45.78,335.9,S1,0.005,,195.1,2127,0.76
STBC,12.40,44.17,36.46,268.0,9M,-0.143,-30.8,45.6,1940,0.96
ABJC,,1.52,1.35,13.30,9M,0.004,-4.0,5.16,229,1.85
BNBC,0.036,0.007,0.022,42.45,9M,,,17.8,0,
CFAC,6.40,4.69,8.42,180.5,S1,-0.270,,,63,1.36
LNBB,3.91,7.18,4.60,98.6,9M,0.720,,22.0,172.8,0.75
NEIC,,,2.04,5.14,9M,-0.940,,,159.54,1.00
PRSC,2.08,2.35,2.37,81.1,S1,-0.118,,,209,0.90
UNXC,,-2.19,-0.62,29.03,9M,,,24.6,0,
CABC,1.43,1.22,1.70,21.26,9M,-0.893,,,172.75,0.60
FTSC,3.08,18.60,0.47,32.11,9M,,,,0,
SDSC,,21.07,0.785,92.0,,,-66.6,72.9,92,6.38
SIVC,,0.377,0.179,10.07,,,,,0,
STAC,-1.12,-0.35,-0.10,3.88,9M,,,0.45,0,
```

Une dette nette négative signifie une trésorerie nette. Pour ONTBF, TTLS, LNBB et CABC, le brut est déduit du net (IRVM de 12,5 %, 10 %, ≈5 % **[NON VÉRIFIÉ pour le Bénin]** et 12 %). Pour SNTS, le brut 2025 de 193,3 (après split) est confirmé par la résolution d'affectation (1 933 avant split).

### 7.4 Calendrier de mise à jour (observé en 2026)

| Événement | Fenêtre observée en 2026 | Paramètre |
|---|---|---|
| États financiers annuels N−1 | 16/02 (Sonatel) au 17/09 (AGL certifiés ; attestation des CAC le 05/10). Sur les 28 émetteurs non financiers dont la page a été relevée : 2 en février (SNTS, ORAC), **18 au 30/04 au plus tard** (7 fichiers datés du 30/04), 10 entre mai et août (dont AGL le 03/08) | `fy_refresh: [Feb-15, Jun-30]`, alerte de retard après le 30/06 |
| Rapports S1 | 13/07 (Uniwax) au 02/11 (Filtisac, Sucrivoire). Sur 25 rapports S1 relevés : **seulement 3 en juillet** (UNXC, SNTS, LNBB) et 1 en septembre (SAPH). **21** sont publiés entre le 01/10 et le 02/11, dont 15 fichiers datés du 30/10 | `h1_refresh: [Jul-10, Nov-05]` |
| Rapports 9 mois | 13/10 (SAPH) au 17/11 (Vivo). La plupart le **même jour que le S1** (27-30/10) | `q3_refresh: [Oct-10, Nov-20]` ; drapeau `reporting_delay` si absent au 30/11 |
| Dividendes | Paiements des sociétés non financières pour l'exercice 2025 : du 26/05 (SNTS) au 27/10 (SDSC, selon le BOC). Date ex = **1 jour ouvré** avant la date de paiement depuis le passage au règlement J+2 (04/12/2025 ; CAL25, colonne « T-1 »). C'était **2 jours ouvrés** avant sous J+3 (CAL24, colonne « T-2 » : SNTS ex le 20/05/2025, paiement le 22/05/2025) | **Corrigé le 22/11/2026** : `ex_div_offset_bd: {until_2025-12-03: -2, from_2025-12-04: -1}`. Préférer la séance qui suit la ligne (d) du BOC (A12) |
| Révision du score | **Corrigé le 22/11/2026.** La v1 visait « 15 jours ouvrés après chaque vague » (fin février, fin mai, mi-août, fin novembre). Les vagues de février et de mi-août **n'existent pas** dans les publications 2026 : au 15/03, seuls 3 comptes annuels étaient publiés (SNTS, ORAC, CABC) ; au 31/08, seulement 3 S1 sur 25 | Proposition du vérificateur, **non testée en walk-forward** : mise à jour **événementielle** des fondamentaux au jour de publication + 1 séance (point-in-time), et révision du score à dates fixes `["05-15","07-15","11-20"]` (après la vague du 30/04, après les AGO et paiements de juin, après la vague S1 + 9 mois de fin octobre) |

### 7.5 Exposition aux facteurs exogènes (signe à coder ; magnitude à estimer par régression)

| Facteur | Titres (signe) | Preuve |
|---|---|---|
| Cours du caoutchouc (SICOM) | SPHC (+), SOGC (+) | SPHC-9M26, SOGC-9M26 |
| Prix de l'huile de palme brute | PALC (+ prix de vente, − coût des régimes), SOGC (+) | PALC-9M26, SOGC-9M26 |
| Marge de raffinage et prix du brut | SMBC (+ marge) | SMBC-9M26 |
| Prix à la pompe administrés et effets de stock | TTLC, TTLS, SHEC (±) | TTLS-9M26 |
| Cuivre | CABC (−) | CABC-9M26 |
| Campagnes cacao et cajou | FTSC (+), SDSC (+) | FTSC-9M26, SDSC-9M25 |
| Congestion portuaire (San-Pedro, Abidjan) | SPHC (−), CABC (−) | SPHC-9M26, CABC-9M26 |
| Réglementation du mobile money (BCEAO) | SNTS (−), ORAC (−), ONTBF (−) | SNTS-9M26 |
| Réglementation antitabac | STBC (−) | STBC-9M26 |
| Contrat de concession de l'État | SDCC (±, binaire), CIEC (±) | SDCC-9M26 |
| Risque sécuritaire au Sahel | ONTBF (−), ORAC via le Burkina (−), SNTS via le Mali (−) | ONTBF-RG25 |

### 7.6 Règles anti-pièges (tests unitaires suggérés)

1. `assert dy_used(FTSC, 2026-11-20) == 0` : l'AGO de l'exercice 2025 n'a voté **aucun dividende** (projet d'affectation [FTSC-FY25]). *(Corrigé le 22/11/2026 : la v1 attribuait ce zéro à la fenêtre de 15 mois. Or le dividende ordinaire de 1 320 FCFA brut a été payé le 30/09/2025, soit 13,7 mois plus tôt : il est **dans** la fenêtre.)* Test complémentaire : `assert dy_used(FTSC, 2026-03-31) > 0`, car l'AGO 2025 n'est pas encore connue ce jour-là. Ce rendement doit déclencher le drapeau `div_yield_flag_gt`.
1b. `assert ex_date(SNTS, paiement 2026-05-26) == 2026-05-22` (J+2, le 25/05 étant férié) et `assert ex_date(SNTS, paiement 2025-05-22) == 2025-05-20` (J+3 : 2 jours ouvrés avant).
2. `assert ey_forward(SPHC) < ey_trailing(SPHC)` : le RN cumulé 2026 baisse de 58 %.
3. `assert eligible(UNLC) is False and eligible(SICC) is False and eligible(SEMC) is False`.
4. `assert split_adjust(SNTS dividende 2026-05-26) == 174.0`.
5. `assert ytd_cumulative(STBC, 2026-09-30).ni == 17.906 + 8.667` (S1 + T3, en Md).
6. Le payout supérieur à 100 % pendant 2 ans déclenche le drapeau `dividend_at_risk` (TTLC, SHEC, SDCC, ABJC, CFAC, SDSC).

---

## 8. Sources

**Toutes consultées entre le 21 et le 22/11/2026.** Les étiquettes renvoient aux fiches. Base des URL de fichiers : `https://www.brvm.org/sites/default/files/`.

### 8.1 Marché, calendriers, avis
- [BOC] BOC du 20/11/2026 : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (et BOC 2017-2026, copies locales `data/boc_text/`)
- [CAL25] Calendrier de paiement des dividendes, exercice 2025 (06/10/2026) : https://www.brvm.org/sites/default/files/20261006_-_calendrier_de_paiement_des_dividendes_-_exercice_2025.pdf
- [CAL24] Calendrier de paiement des dividendes, exercice 2024 (24/12/2025) : https://www.brvm.org/sites/default/files/20251224_-_calendrier_de_paiement_des_dividendes_-_exercice_2024.pdf
- [AV303] Avis 303-2026, flottant au 31/12/2025 : https://www.brvm.org/sites/default/files/20261012_-_avis_ndeg303_brvmdg_-_flottant_des_societes_cotees_a_la_brvm.pdf
- [AVIS-268-2026] Suspension SICOR : https://www.brvm.org/sites/default/files/20260916_-_avis_ndeg268_brvmdg_-_suspension_-_sicor_ci.pdf
- [AVIS-269-2026] Suspension Sucrivoire : https://www.brvm.org/sites/default/files/20260916_-_avis_ndeg269_brvmdg_-_suspension_-_sucrivoire_ci.pdf
- [AVIS-276-2026] Levée de suspension Sucrivoire : https://www.brvm.org/sites/default/files/20260921_-_avis_ndeg276_brvmdg_-_levee_de_la_suspension_sucrivoire_s.a.pdf
- [AVIS-270-2026] Suspension Sonoco Metal Packaging SIEM : https://www.brvm.org/sites/default/files/20260916_-_avis_ndeg270_brvmdg_-_suspension_-_sonoco_metal_packaging_siem_ci.pdf
- [AVIS-179-2025] Suspension Eviosys SIEM : https://www.brvm.org/sites/default/files/20250729_-_avis_ndeg179_brvmdg_-_suspension_-_eviosys_packaging_siem_ci.pdf
- [AVIS-004-2026] Levée de suspension Eviosys SIEM : https://www.brvm.org/sites/default/files/20260102_-_avis_ndeg004_brvmdg_-_levee_de_la_suspension_-_eviosys_packaging_ci.pdf
- [AVIS-189-2025] Suspension Unilever CI : https://www.brvm.org/sites/default/files/20250804_-_avis_ndeg189_brvmdg_-_suspension_-_unilever_ci.pdf
- [AVIS-213-2025] Levée de suspension Unilever CI : https://www.brvm.org/sites/default/files/20250901_-_avis_ndeg213_brvmdg_-_levee_de_la_suspension_unilever_ci.pdf
- Fractionnements SNTS et SLBC : voir `01-structure-marche.md` §8.1 (avis 309-2026 et 242-2024)

### 8.2 Fiches émetteurs (actionnariat) — `https://www.brvm.org/fr/emetteurs/societes-cotees/<slug>`
- [ISS-SNTS] …/societe-nationale-de-telecommunication-du-senegal-sonatel ; [ISS-ONTBF] …/moov-africa-burkina-faso ; [ISS-TTLC] …/total-cote-divoire-total-cote-divoire ; [ISS-TTLS] …/total-senegal-total-senegal ; [ISS-SHEC] …/vivo-energy-cote-divoire ; [ISS-SMBC] …/societe-multinationale-de-bitume-de-cote-divoire-smb ; [ISS-CIEC] …/compagnie-ivoirienne-delectricite-cie-ci ; [ISS-SDCC] …/societe-de-distribution-deau-de-cote-divoire-sodeci ; [ISS-PALC] …/palm-cote-divoire-palmci ; [ISS-SPHC] …/societe-africaine-de-plantation-dheveas-de-cote-divoire-saph ; [ISS-SOGC] …/societe-des-caoutchoucs-de-grand-bereby-de-cote-divoire-sogb ; [ISS-SLBC] …/societe-de-limonaderies-et-brasseries-dafrique-solibra ; [ISS-NTLC] …/nestle-cote-divoire ; [ISS-UNLC] …/huilerie-savonnerie-lipochimie-unilever ; [ISS-STBC] …/societe-ivoirienne-des-tabacs-sitab ; [ISS-SICC] …/societe-ivoirienne-de-coco-rape-sicor-0 ; [ISS-CABC] …/societe-ivoirienne-de-cables-sicable ; [ISS-FTSC] …/filature-tissage-sacs-de-cote-divoire-filtisac ; [ISS-SDSC] …/africa-global-logistics-agl-cote-divoire ; [ISS-SEMC] …/societe-ivoirienne-demballage-metallique-crown-siem ; [ISS-SIVC] …/erium-cote-divoire ; [ISS-STAC] …/societe-detudes-et-de-travaux-pour-lafrique-de-louest-setao ; [ISS-ABJC] …/servair-abidjan ; [ISS-BNBC] …/bernabe ; [ISS-CFAC] …/compagnie-francaise-de-lafrique-occidentale-en-cote-divoire-cfao-ci ; [ISS-NEIC] …/nouvelles-editions-ivoiriennes-centre-deditions-et-de-diffussion ; [ISS-PRSC] …/tractafric-motors-cote-divoire ; [ISS-UNXC] …/uniwax

### 8.3 États financiers et rapports d'activité (par société)
Télécommunications
- [SNTS-FY25] https://www.brvm.org/sites/default/files/20260216_-_etats_financiers_2025_et_attestation_des_cac_-_sonatel_sn.pdf
- [SNTS-FY24] https://www.brvm.org/sites/default/files/20250221_-_etats_financiers_-_exercice_2024_-_sonatel_sn.pdf
- [SNTS-9M26] https://www.brvm.org/sites/default/files/20261029_-_rapport_dactivites_-_3e_trimestre_2026_-_sonatel_sn.pdf
- [ORAC-FY25] https://www.brvm.org/sites/default/files/20260608_-_etats_financiers_approuves_-_exercice_2025_-_orange_ci.pdf
- [ORAC-FY24] https://www.brvm.org/sites/default/files/20250221_-_etats_financiers_-_exercice_2024_-_orange_ci.pdf
- [ORAC-9M26] https://www.brvm.org/sites/default/files/20261028_-_rapport_dactivites_-_3e_trimestre_2026_-_orange_ci.pdf
- [ONTBF-FY25] https://www.brvm.org/sites/default/files/20260611_-_etats_financiers_approuves_-_exercice_2025_-_onatel_bf.pdf
- [ONTBF-RG25] https://www.brvm.org/sites/default/files/20260611_-_rapport_de_gestion_-_exercice_2025_-_onatel_bf.pdf
- [ONTBF-FY24] https://www.brvm.org/sites/default/files/20250718_-_etats_financiers_certifies_et_approuves_exercice_2024_-_onatel_bf.pdf
- [ONTBF-9M26] https://www.brvm.org/sites/default/files/20261023_-_rapport_dactivites_-_3e_trimestre_2026_-_onatel_bf.pdf

Énergie
- [TTLC-FY25] https://www.brvm.org/sites/default/files/20260601_-_etats_financiers_approuves_-_exercice_2025_-_totalenergies_marketing_ci.pdf
- [TTLC-FY24] https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_totalenergies_marketing_ci.pdf
- [TTLC-9M26] https://www.brvm.org/sites/default/files/20261027_-_rapport_dactivites_-_3e_trimestre_2026_-_totalenergies_marketing_ci.pdf
- [TTLS-FY25] https://www.brvm.org/sites/default/files/20260615_-_rapport_dactivites_annuel_-_exercice_2025_-_totalenergies_marketing_sn.pdf
- [TTLS-9M26] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_totalenergies_marketing_sn.pdf
- [SMBC-FY25] https://www.brvm.org/sites/default/files/20260512_-_etats_financiers_et_projet_daffectation_du_resultat_-_exercice_2025_-_smb_ci.pdf
- [SMBC-FY24] https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_smb_ci.pdf
- [SMBC-9M26] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_smb_ci.pdf
- [SHEC-FY25] https://www.brvm.org/sites/default/files/20260603_-_etats_financiers_-_exercice_2025_-_vivo_energy.pdf
- [SHEC-FY24] https://www.brvm.org/sites/default/files/20250516_-_etats_financiers_2024_et_rapport_dactivites_du_1er_trimestre_2025_-_vivo_energy_ci.pdf
- [SHEC-9M26] https://www.brvm.org/sites/default/files/20261117_-_rapport_dactivites_-_3e_trimestre_2026_-_vivo_energy_ci.pdf

Services publics
- [CIEC-FY25] https://www.brvm.org/sites/default/files/20260520_-_etats_financiers_syscohada_et_ifrs_-_exercice_2025_-_cie_ci.pdf
- [CIEC-FY24] https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_norme_syscohada_-_exercice_2024_-_cie_ci.pdf
- [CIEC-S126] https://www.brvm.org/sites/default/files/20261029_-_rapport_dactivites_-_1er_semestre_2026_-_cie_ci.pdf
- [SDCC-FY25] https://www.brvm.org/sites/default/files/20260427_-_etats_financiers_-_exercice_2025_-_sodeci.pdf
- [SDCC-FY24] https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_sode_ci.pdf
- [SDCC-9M26] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_sode_ci.pdf

Consommation de base
- [NTLC-FY25] https://www.brvm.org/sites/default/files/20260430_-_etats_financiers_-_exercice_2025_-_nestle_ci.pdf
- [NTLC-FY24] https://www.brvm.org/sites/default/files/20250505_-_etats_financiers_-_exercice_2024_-_nestle_ci_annule_et_remplace_le_precedent.pdf
- [NTLC-9M26] https://www.brvm.org/sites/default/files/20261022_-_rapport_dactivites_-_3e_trimestre_2026_-_nestle_ci.pdf
- [PALC-FY25] https://www.brvm.org/sites/default/files/20260323_-_etats_financiers_-_exercice_2025_-_palm_ci.pdf
- [PALC-FY24] https://www.brvm.org/sites/default/files/20250417_-_etats_financiers_provisoires_valides_par_le_ca_-_exercice_2024_-_palm_ci.pdf
- [PALC-9M26] https://www.brvm.org/sites/default/files/20261027_-_rapport_dactivites_-_3e_trimestre_2026_-_palm_ci.pdf
- [SPHC-FY25] https://www.brvm.org/sites/default/files/20260318_-_etats_financiers_syscohada_-_exercice_2025_-_saph_ci.pdf
- [SPHC-FY24] https://www.brvm.org/sites/default/files/20250319_-_etats_financiers_certifies_par_les_cacs_-_exercice_2024_-_saph_ci.pdf
- [SPHC-9M26] https://www.brvm.org/sites/default/files/20261013_-_rapport_dactivites_-_3e_trimestre_2026_-_saph_ci.pdf
- [SOGC-FY25] https://www.brvm.org/sites/default/files/20260422_-_etats_financiers_syscohada_-_exercice_2025_-_sogb_ci.pdf
- [SOGC-FY24] https://www.brvm.org/sites/default/files/20250616_-_etats_financiers_-_exercice_2024_-_sogb_ci.pdf
- [SOGC-9M26] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_sogb_ci.pdf
- [SCRC-FY25] https://www.brvm.org/sites/default/files/20260518_-_etats_financiers_-_exercice_2025_-_sucrivoire_ci_annule_et_remplace_le_precedent.pdf
- [SCRC-FY24] https://www.brvm.org/sites/default/files/20250509_-_etats_financiers_-_normes_syscohada_-_exercice_2024_-_sucrivoire_ci.pdf
- [SCRC-S126] https://www.brvm.org/sites/default/files/20261102_-_rapport_dactivites_-_1er_semestre_2026_-_sucrivoire_ci.pdf
- [SLBC-FY25] https://www.brvm.org/sites/default/files/20260519_-_etats_financiers_-_exercice_2025_-_solibra_ci.pdf
- [SLBC-FY24] https://www.brvm.org/sites/default/files/20250502_-_etats_financiers_-_exercice_2024_-_solibra_ci.pdf
- [SLBC-S126] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_1er_semestre_2026_-_solibra_ci.pdf
- [STBC-FY25] https://www.brvm.org/sites/default/files/20260625_-_etats_financiers_-_exercice_2025_-_sitab_ci_annule_et_remplace_le_precedent.pdf
- [STBC-FY24] https://www.brvm.org/sites/default/files/20250507_-_etats_financiers_-_exercice_2024_-_sitab_ci.pdf
- [STBC-S126] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_1er_semestre_2026_-_sitab_ci.pdf
- [STBC-9M26] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_sitab_ci.pdf
- [UNLC-FY23] https://www.brvm.org/sites/default/files/20240904_-_etats_financiers_-_exercice_2023_-_unilever_ci.pdf
- [SICC-FY25] (consulté, non extrait) https://www.brvm.org/sites/default/files/20260612_-_rapport_dactivites_annuel_et_etats_financiers_-_exercice_2025_-_sicor_ci.pdf

Consommation discrétionnaire
- [ABJC-FY25] https://www.brvm.org/sites/default/files/20260427_-_etats_financiers_syscohada_-_exercice_2025_-_servair_abidjan_ci.pdf
- [ABJC-9M26] https://www.brvm.org/sites/default/files/20261016_-_rapport_dactivites_-_3e_trimestre_2026_-_servair_abidjan_ci.pdf
- [BNBC-FY25] https://www.brvm.org/sites/default/files/20260430_-_etats_financiers_-_exercice_2025_-_bernabe_ci.pdf
- [BNBC-FY24] https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_bernabe_ci.pdf
- [BNBC-9M26] https://www.brvm.org/sites/default/files/20261027_-_rapport_dactivites_-_3e_trimestre_2026_-_bernabe_ci.pdf
- [CFAC-FY25] https://www.brvm.org/sites/default/files/20260713_-_rapport_annuel_-_exercice_2025_-_cfao_motors_ci.pdf
- [CFAC-FY24] https://www.brvm.org/sites/default/files/20250516_-_etats_financiers_-_exercice_2024_-_cfao_motors_ci.pdf
- [CFAC-S126] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_1er_semestre_2026_-_cfao_motors_ci.pdf
- [LNBB-FY25] https://www.brvm.org/sites/default/files/20260430_-_etats_financiers_-_exercice_2025_-_lnb_bn.pdf
- [LNBB-FY24] https://www.brvm.org/sites/default/files/20250602_-_etats_financiers_-_exercice_2024_-_lnb_bn.pdf
- [LNBB-9M26] https://www.brvm.org/sites/default/files/20261028_-_rapport_dactivites_-_3e_trimestre_2026_-_lnb_bn.pdf
- [NEIC-9M26] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_nei-ceda_ci.pdf
- [NEIC-FY25] https://www.brvm.org/sites/default/files/20260423_-_etats_financiers_syscohada_-_exercice_2025_-_nei_ceda_ci.pdf
- [PRSC-FY25] https://www.brvm.org/sites/default/files/20260430_-_etats_financiers_-_exercice_2025_-_tractafric_motors_ci.pdf
- [PRSC-FY24] https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_tractafric_motors_ci.pdf
- [PRSC-S126] https://www.brvm.org/sites/default/files/20261029_-_etats_financiers_-_1er_semestre_2026_-_tractafric_motors_ci.pdf
- [UNXC-FY25] https://www.brvm.org/sites/default/files/20260713_-_etats_financiers_-_exercice_2025_-_uniwax_ci.pdf
- [UNXC-9M26] https://www.brvm.org/sites/default/files/20261028_-_rapport_dactivites_-_3e_trimestre_2026_-_uniwax_ci.pdf

Industriels
- [CABC-FY25] https://www.brvm.org/sites/default/files/20260310_-_etats_financiers_syscohada_-_exercice_2025_-_sicable_ci.pdf
- [CABC-FY24] https://www.brvm.org/sites/default/files/20250313_-_etats_financiers_verifies_par_les_cacs_-_exercice_2024_-_sicable_ci.pdf
- [CABC-9M26] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_sicable_ci.pdf
- [FTSC-FY25] https://www.brvm.org/sites/default/files/20260610_-_etats_financiers_-_exercice_2025_-_filtisac_ci.pdf
- [FTSC-FY24] https://www.brvm.org/sites/default/files/20250523_-_etats_financiers_-_exercice_2024_-_filtisac_ci.pdf
- [FTSC-9M26] https://www.brvm.org/sites/default/files/20261105_-_rapport_dactivites_-_3e_trimestre_2026_-_filtisac_ci_annule_et_remplace_le_precedent.pdf
- [SDSC-FY25] https://www.brvm.org/sites/default/files/20260917_-_etats_financiers_certifies_-_exercice_2025_-_africa_global_logistics_ci.pdf
- [SDSC-FY24] https://www.brvm.org/sites/default/files/20250829_-_etats_financiers_et_rapport_des_cac_-_exercice_2024_-_africa_global_logistics_ci.pdf
- [SDSC-9M25] https://www.brvm.org/sites/default/files/20251205_-_rapport_dactivites_-_3eme_trimestre_2025_-_africa_global_logistics_ci.pdf
- [SEMC-FY23] https://www.brvm.org/sites/default/files/20241216_-_etats_financiers_de_synthese_-exercice_2023_-_eviosys_packaging_siem_ci.pdf
- [SIVC-FY25] https://www.brvm.org/sites/default/files/20260626_-_etats_financiers_-_exercice_2025_-_erium_ci.pdf
- [SIVC-T125] (date de publication) https://www.brvm.org/sites/default/files/20251219_-_rapport_dactivites_-_1er_trimestre_2025_-_erium_ci_ex_air_liquide_ci.pdf
- [STAC-FY24] https://www.brvm.org/sites/default/files/20250410_-_etats_financiers_provisoires_-_exercice_2024_-_setao_ci.pdf
- [STAC-9M26] https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_setao_ci.pdf

### 8.4 Documents internes du projet
- `docs/research/01-structure-marche.md` : nombre de titres, flottant, IRVM, splits, mécanique du détachement
- `docs/research/04-rigueur-quantitative.md` : validation walk-forward, PBO, Sharpe dégonflé (à appliquer à ce score)
- `docs/research/05-macro-geopolitique-uemoa.md` : risque souverain et contexte UEMOA

---

## 9. Questions ouvertes

1. Actionnariat à jour au 31/12/2025 pour ORAC, SMBC, SCRC, LNBB, SDSC (contrôle ultime d'AGL), SIVC (repreneur d'Erium) et SDCC/CIEC (contrôle ultime d'Eranove). Les fiches BRVM sont périmées et la recherche web n'a pas été possible (quota épuisé).
2. Unilever CI : aucun état financier 2024 ni 2025 publié, et suspension d'août 2025 sans motif public. Une opération de retrait est-elle prévue ? Non vérifié.
3. SODECI : termes du nouveau contrat d'affermage et ampleur du « besoin de financement » annoncé (augmentation de capital possible).
4. SITAB : date d'entrée en vigueur du paquet neutre et effet sur les marges 2027.
5. AGL CI : pourquoi aucun rapport trimestriel 2026 n'a été publié, et cause de la hausse de 77 % du cours en 2026 malgré un RN 2025 de 0,79 Md.
6. ~~Onatel : part de l'État (26 % selon la fiche, ce qui donne un total de 110 %).~~ **Résolu le 22/11/2026** : 16 % selon le rapport de gestion 2025.
7. Données 2023 non extraites (ABJC, NEIC, UNXC, SDSC, SIVC, STAC) et données 2024 de NEIC : documents scannés. Il faut un OCR ou une saisie manuelle.
8. Le score n'a **pas encore été testé historiquement**. Il faut reconstituer les fondamentaux point-in-time 2018-2025 (dates de publication réelles) pour éviter le biais d'anticipation, puis appliquer la validation walk-forward de `04-rigueur-quantitative.md`.

---

## Vérification adversariale (2026-11-22)

**Méthode.** Un vérificateur indépendant a tenté de réfuter les affirmations les plus coûteuses en cas d'erreur, en priorité les **paramètres codés**. Il s'est appuyé sur trois sources : les documents primaires re-téléchargés sur brvm.org (curl GET simple, lecture visuelle des scans), les BOC locaux (`data/boc_text/`) et le panel `data/panel/`. **Limite** : le quota de recherche web de la session était épuisé quand la vérification a commencé, donc aucune source secondaire ni réglementaire hors brvm.org n'a pu être consultée. Le document ne cite **aucune étude académique**, donc aucune étude n'est à authentifier.

| # | Élément vérifié | Verdict | Valeur correcte / commentaire | Preuve |
|---|---|---|---|---|
| 1 | Contexte BOC 20/11/2026 : 48 sociétés (secteurs 3/4/2/9/7/6 + 17 financières), Composite 492,89 (+42,56 %), PER moyen 15,79 hors Unilever, BOC n° 222 | **Confirmé** | — | BOC local `boc_20261120.txt.gz` (https://www.brvm.org/sites/default/files/boc_20261120_2.pdf) |
| 2 | `split_factors` SNTS 0,1 au 26/10/2026 | **Confirmé** | Référence théorique de 4 385 au BOC du 23/10 (43 850 / 10), première cotation divisée le 26/10 ; AGE du 08/10/2026 | BOC 23/10 et 26/10/2026 ; [SNTS-9M26] |
| 3 | `split_factors` SLBC 0,1 au 30/09/2024 | **Confirmé** | Avis 242-2024. Le BOC n'a pas ajusté le dividende (rendement affiché de 36,9 %) : anomalie A14 | BOC 27/09 et 30/09/2024 |
| 4 | `ex_div_offset_bd: -1` | **Corrigé** | −1 jour ouvré seulement depuis le passage au règlement J+2 (04/12/2025) ; **−2 avant** (colonne « T-2 » de CAL24 ; SNTS ex le 20/05/2025 pour un paiement le 22/05/2025 ; STBC et SDSC ex le 27/08/2025 pour le 29/08/2025). Le paramètre fixe faussait toute l'histoire 2017-2025 | [CAL24], [CAL25], BOC 19-22/05/2025, 26-29/08/2025, 21-26/05/2026 |
| 5 | `irvm_gross_up` CI 12 % (personnes physiques) / 10 % (personnes morales), part exceptionnelle 17 % | **Confirmé** (et précisé : 15 % pour les personnes morales sur l'exceptionnel) | Notes (*) et (#) des calendriers | [CAL24], [CAL25] |
| 6 | `irvm_gross_up` SN 10 % ; BF 12,5 % | **Confirmé** | Sonatel : 1 933 brut → 1 740 net « retenue de 10 % » ; Onatel : 166,0816 → 145,3214 « net de l'IRCM » | [SNTS-FY25] p. 25 ; [ONTBF-RG25] |
| 7 | `irvm_gross_up` BJ ≈ 5 % | **Invérifiable** | Aucune source primaire trouvée (recherche web épuisée). Marqué [NON VÉRIFIÉ] | — |
| 8 | Flottants UNLC 0,2 % et CFAC 4,2 % (`free_float_pct_lt: 5.0`) | **Confirmé** | Valeurs exactes de l'avis : 0,22 % et 4,15 % ; SEMC 10,29 % ; SICC 12,26 % ; PRSC 100,00 %. **Ajout** : le seuil **réglementaire** est de **15 %** (colonne « Diffusion de 15 % du capital dans le public » ; 4 sociétés en défaut). Le seuil de 5 % reste un choix du projet | [AV303] (scan lu visuellement) |
| 9 | Suspension de SICC et SEMC depuis le 16/09/2026 (`universe.exclude.status`) | **Confirmé** | Avis 268 : article 1511 des règles, « jusqu'à la régularisation » ; BOC « SP » jusqu'au 20/11 | [AVIS-268-2026] ; BOC 16/09-20/11/2026 |
| 10 | Sucrivoire « réadmise le 21/09/2026 » | **Corrigé** | Avis daté du 21/09, **reprise de cotation le 22/09/2026** (BOC du 21/09 encore « SP »), après publication du rapport du **T1** 2026 | [AVIS-276-2026] ; BOC 21-22/09/2026 |
| 11 | `div_yield_window_months: 15` (« DY = 0 si le dernier dividende ordinaire a plus de 15 mois ») et test FTSC | **Réfuté tel que formulé, corrigé** | Le dividende ordinaire de FTSC (1 320 brut) a été payé le 30/09/2025, 13,7 mois avant le 20/11/2026. La règle seule donnerait DY ≈ 72,6 %. La bonne règle porte sur le **dernier exercice dont l'AGO est connue** (FTSC exercice 2025 : aucun dividende), avec 15 mois comme simple garde-fou | [CAL24] ; [FTSC-FY25] (projet d'affectation : dividendes « - ») |
| 12 | FTSC : 2 000,67 brut (1 320 + 680,67 exceptionnel), net de 1 726,56 payé le 30/09/2025 ; aucun dividende pour 2025 ; RN 9 mois 2026 de −0,354 Md | **Confirmé** | Arithmétique exacte : 1 320 × 0,88 + 680,67 × 0,83 = 1 726,56 | [CAL24], [FTSC-FY25], [FTSC-9M26] |
| 13 | Sonatel : RN 2025 de 413,6 Md (342,0 part du groupe), CA 1 923,1, capitaux propres 1 399,3 ; 9 mois 2026 : CA 1 583 (+10,5 %), EBITDAaL 769, RN 354 (+12,9 %) | **Confirmé** | — | [SNTS-FY25], [SNTS-9M26] |
| 14 | SITAB : RN 9 mois = S1 + T3 = 17,906 + 8,667 = 26,57 Md (−14,3 %) ; le rapport « T3 » couvre le trimestre seul | **Confirmé** | CA 9 mois de 216,3 Md (+10,5 %). T3 2025 = 12,94 Md, comparable | [STBC-S126], [STBC-9M26] (scans) |
| 15 | SMB : RN 9 mois de 8,904 Md (+57 %), CA de 179,2 Md (+15 %) ; EY prospectif de 14,6 % | **Confirmé** | (1/10,73) × 1,57 = 14,6 % | [SMBC-9M26] (scan) |
| 16 | AGL CI : RN 2025 de 0,785 Md contre 21,07 ; dividende de 5,008 Md ; payout de 638 % ; trésorerie nette de +66,6 | **Confirmé (chiffres)**, interprétation **corrigée** | La trésorerie (76,8 Md) vient d'une hausse de +79,8 Md du passif circulant, pour une CAF de 7,5 Md. Elle n'est **pas** excédentaire : ajout du garde-fou `quality_net_cash_guard` | [SDSC-FY25] (scan) |
| 17 | Onatel : RN 2025 de 15,89 Md, payout de 70 %, dividende net de 145,32 | **Confirmé** | — | [ONTBF-RG25] |
| 18 | Onatel : actionnariat État 26 % (total de 110 %) | **Corrigé** | **État 16 %** (Maroc Telecom 61 %, public 23 %). La fiche BRVM est erronée | [ONTBF-RG25], « Composition du capital au 31-12-2025 » |
| 19 | Table des dividendes 2021-2026 (§2.1) | **Corrigé (4 cellules)** | ORAC 2023 : 752,76 (et non « — ») ; ONTBF 2024 : 266,45 (et non 226,45) ; CIEC 2021 : 167,14 (et non 176,14) ; STAC 2021 : 66,15 (et non « — »). Les autres cellules sont conformes au panel `dividends.parquet` | BOC 30/12/2021, 29/12/2023, 31/12/2024 |
| 20 | Orange CI : BPA part du groupe 2025 de 857,2 FCFA, P/E part du groupe ≈ 22,5 ; 9 mois 2026 : CA 1 012 (+15,5 %), RN 141 (+18,3 %) ; payout ≈ 93 % | **Confirmé** | 800 × 150,66 M titres = 120,5 Md / 129,1 = 93 % | [ORAC-FY25], [ORAC-9M26], [AV303] |
| 21 | Valeur médiane par séance en 2026 (SNTS 252,3 ; STBC 47,6 ; ORAC 27,4 ; BNBC 2,7 ; PRSC 3,3) et seuil de 2,0 M | **Confirmé** | Recalculé sur 220 séances. Contrôle du parsing des valeurs SNTS après le split (valeur ≈ volume × cours) | `data/panel/equities.parquet` |
| 22 | Robustesse : Spearman de 0,986 à 0,992 ; top 3 stable | **Confirmé (cohérence interne)**, portée **limitée** | Recalcul : 0,990 / 0,993 / 0,991 / 0,986. Mais avec le PER part du groupe (anomalie A1), SNTS (0,911) et STBC (0,910) sont à égalité et ORAC passe du 7e au 9e rang. Le n° 1 n'est pas robuste à la définition des entrées | calcul du vérificateur, à partir des tableaux §5.2 et §3.1 |
| 23 | `rebalance_dates` 03-15 / 06-15 / 08-31 / 11-30 (« vagues fin février, fin mai, mi-août, fin novembre ») | **Réfuté (justification), corrigé** | En 2026 : 3 comptes annuels au 15/03 ; 18 au 30/04 ; 3 S1 sur 25 au 31/08 ; 21 S1 et la plupart des 9 mois entre le 01/10 et le 02/11. Proposition : mise à jour événementielle + revues les `05-15`, `07-15` et `11-20` (non testée) | pages `brvm.org/fr/rapports-societe-cotes/<société>` (dates des fichiers) |
| 24 | `last_financials_age_days_gt: 400` | **Corrigé (ambigu)** | Mesuré depuis la clôture, ce seuil excluait toute la cote du 04/02 jusqu'à la publication des comptes N−1. Remplacé par `last_annual_fs_period_end_age_days_gt: 546`. UNLC et SEMC n'ont toujours pas publié après l'exercice 2023 (confirmé sur leurs pages) | pages `unilever-ci` et `crown-siem-ci` sur brvm.org |
| 25 | SODECI : contrat d'affermage en attente de notification, « besoins de financement », RN 9 mois de 2,133 Md (+12,1 %), résultat d'exploitation T3 de −0,677 Md | **Confirmé** | — | [SDCC-9M26] |
| 26 | SAPH : RN 9 mois de 9,703 Md (−58 %), CA de 232,5 Md (−8 %) | **Confirmé** | P/E prospectif ≈ 7,82 / 0,42 ≈ 18,6 | [SPHC-9M26] (scan) |

**Non vérifié par manque de temps ou de source** (inchangé, à traiter) : la décomposition de la dette de SHEC, CIEC et ORAC ; le RN 2025 et la trésorerie de SITAB (scan non relu) ; les chiffres de Solibra (ordre des colonnes ambigu, déjà signalé en medium) ; les poids du score (choix de conception, non réfutables, sans validation historique) ; le taux IRVM béninois.

**Conclusion du vérificateur.** Les chiffres financiers lus dans les documents primaires sont **fiables** : les 9 sociétés re-contrôlées (items 12 à 17, 20, 25 et 26) sont confirmées à la décimale près. Les erreurs portent sur les **règles à coder** :
- la date ex dépend de la période ;
- la règle du rendement en dividende échoue sur FTSC ;
- les dates de révision ne correspondent pas au calendrier réel ;
- l'âge des comptes est ambigu.

S'y ajoutent quatre cellules de la table des dividendes, l'actionnariat d'Onatel et la date de reprise de Sucrivoire. Le classement n'est qu'un **filtre de départ** : SNTS et STBC sont à égalité quand le PER est défini proprement. **Aucun gain n'est garanti**, et le score reste à valider en walk-forward avec des fondamentaux point-in-time.

Sources supplémentaires consultées par le vérificateur le 22/11/2026 :
- https://www.brvm.org/sites/default/files/20261006_-_calendrier_de_paiement_des_dividendes_-_exercice_2025.pdf
- https://www.brvm.org/sites/default/files/20251224_-_calendrier_de_paiement_des_dividendes_-_exercice_2024.pdf
- https://www.brvm.org/sites/default/files/20261012_-_avis_ndeg303_brvmdg_-_flottant_des_societes_cotees_a_la_brvm.pdf
- https://www.brvm.org/sites/default/files/20260921_-_avis_ndeg276_brvmdg_-_levee_de_la_suspension_sucrivoire_s.a.pdf
- https://www.brvm.org/sites/default/files/20260916_-_avis_ndeg268_brvmdg_-_suspension_-_sicor_ci.pdf
- https://www.brvm.org/sites/default/files/20260611_-_rapport_de_gestion_-_exercice_2025_-_onatel_bf.pdf
- https://www.brvm.org/sites/default/files/20260917_-_etats_financiers_certifies_-_exercice_2025_-_africa_global_logistics_ci.pdf
- https://www.brvm.org/sites/default/files/20260610_-_etats_financiers_-_exercice_2025_-_filtisac_ci.pdf
- https://www.brvm.org/fr/emetteurs/societes-cotees/moov-africa-burkina-faso (fiche émetteur : État à 26 %, erroné)
- https://www.brvm.org/fr/rapports-societes-cotees et les pages `https://www.brvm.org/fr/rapports-societe-cotes/<société>` (dates de publication 2026)
- BOC locaux : 2021-12-30, 2023-12-29, 2024-09-25 → 2024-10-02, 2024-12-31, 2025-05-16 → 2025-05-22, 2025-08-25 → 2025-08-29, 2026-05-20 → 2026-05-26, 2026-09-15 → 2026-09-22, 2026-10-21 → 2026-10-27, 2026-11-20
