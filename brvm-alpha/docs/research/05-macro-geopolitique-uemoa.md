# 05 — Macroéconomie, géographie et risque politique de l'UEMOA, et liens avec les sociétés cotées (état au 22/11/2026)

> **Périmètre** : politique monétaire de la BCEAO, inflation, croissance, notations souveraines, dette, marché obligataire régional (taux sans risque local), parité FCFA/euro et projet ECO, risque politique pays par pays (AES, élections, Sénégal), exposition des sociétés cotées aux matières premières, répartition de la capitalisation par pays, et méthode chiffrée de prime de risque pays et de pondération géographique.
> **Date de rédaction** : 22/11/2026.
> **Données locales** : 1 354 séances de BOC (11/01/2021 → 20/11/2026) passées dans le parseur du projet (`brvm_alpha.data.store.build_panel`). Tous les calculs de ce document sont reproductibles à partir de `data/boc_text/`.
> **Avertissement** : aucun modèle, aucun analyste et aucune information macroéconomique ne permettent de **garantir** un gain. Le risque politique de la zone (coups d'État, sanctions, crise budgétaire) produit précisément des pertes brutales et imprévisibles. Ce document sert à **mesurer et limiter** ce risque, pas à le faire disparaître.
>
> **Après vérification adversariale (22/11/2026, dernière section)** : 27 éléments ont été contrôlés à nouveau sur les BOC locaux et sur les PDF de brvm.org. Les faits tirés des BOC (capitalisations, formule et niveau de la prime, taux de référence 5,75 %, coupons et dates de cotation des emprunts d'État, trajectoire de BOA Niger, limite de ±7,5 %) et des fiches de notation sont **confirmés**. Six paramètres codés sont **corrigés** :
> (1) `jump_loss.severe` passe de 0,25 à **0,21** (0,26 en stress). Le chercheur n'avait calibré que sur le Niger 2023 et avait oublié les sanctions UEMOA contre le Mali en janvier 2022 (creux de −16,9 %).
> (2) Le « délai de 6 séances » **n'est pas une règle** : au Mali en 2022, la baisse au plafond a commencé dès la première séance (t+1).
> (3) Les spreads locaux du YAML sont remplacés par les valeurs calculées, et non plus arrondies.
> (4) L'exposition λ de Sonatel reçoit une variante pondérée par le taux de détention des filiales (Mali 69,40 %).
> (5) Le déclencheur « décote obligataire » exige au moins 5 transactions : au Niger en 2026, la médiane repose sur 3 ou 4 transactions.
> (6) La confiance d'EUR/USD 1,164 passe de H à M (±0,006, valeur dérivée de chiffres arrondis).
> **Restent non vérifiés**, parce que WebSearch était épuisé et que bceao.int et pages.stern.nyu.edu ne se résolvent pas : les taux de la BCEAO, l'inflation, les notes souveraines, les chiffres de la Cour des comptes du Sénégal, les dates d'événements politiques et le multiplicateur de Damodaran. Ils sont marqués **[NON VÉRIFIÉ]**.

### Conditions de la recherche : à lire avant tout

1. **Le budget de recherche web (WebSearch) de la session était déjà épuisé** au début de ce travail (limite partagée entre agents). Aucune recherche web n'a donc pu être faite.
2. **Les sites `www.bceao.int` et `www.imf.org` sont bloqués** dans l'environnement réseau de cette session (le nom de domaine ne se résout pas). Pour vérifier les décisions 2026 de la BCEAO, l'inflation 2026, les notes souveraines et les spreads des eurobonds, **il faut autoriser ces domaines dans les paramètres réseau de la session**. Le même problème touche probablement `umoatitres.org`, `worldbank.org` et les agences de notation.
3. Seul **`www.brvm.org`** était joignable. Ce document repose donc d'abord sur des **sources primaires de la BRVM** : BOC, communiqués, rapports d'activité et fiches de notation des émetteurs publiés sur brvm.org. Ces sources contiennent beaucoup d'informations macroéconomiques indirectes, que nous avons exploitées.
4. Les faits macroéconomiques qui n'ont **pas** pu être revérifiés viennent de la connaissance antérieure du rédacteur (arrêtée à mi-2026). Ils sont signalés **M** ou **L** et accompagnés de la page officielle où il faut les contrôler. **Aucun de ces chiffres ne doit être codé en dur** : la plate-forme doit les charger depuis un fichier de configuration daté et sourcé (§14).

**Légende de confiance**
- **H** (haute) : vérifié dans cette session sur une source primaire (BOC, brvm.org, rapport ou notation publié sur brvm.org), ou calculé par nous sur ces données.
- **M** (moyenne) : connaissance antérieure concordante avec plusieurs sources, mais non revérifiée en ligne ici. À confirmer avant tout usage en production.
- **L** (basse) : souvenir partiel, chiffre peut-être périmé ou contesté. À ne pas utiliser sans vérification.

---

## 0. Synthèse en 18 points

| # | Constat | Valeur | Date | Conf. | Source |
|---|---|---|---|---|---|
| 1 | Capitalisation actions BRVM | **19 328,8 Md FCFA** ; obligations 13 425,0 Md ; 48 sociétés ; 210 lignes obligataires | 20/11/2026 | H | BOC 20/11/2026 |
| 2 | Poids des pays dans la capitalisation (pays du siège) | **CI 57,8 %**, SN 22,9 %, BF 7,3 %, TG 6,2 %, BJ 4,6 %, ML 0,7 %, NE 0,5 %, GW 0 % | 20/11/2026 | H (calcul) | BOC + nombre de titres (doc 01, §11) |
| 3 | Poids « économique » (Sonatel réparti par pays de clientèle, ETIT isolé) | CI 57,8 %, SN 9,1 %, BF 7,3 %, **ML 6,8 %**, Guinée 5,4 %, panafricain (ETIT) 5,3 %, BJ 4,6 % … | 2025-2026 | H/M | §11 |
| 4 | PIB nominal UEMOA implicite | **≈ 134 900 Md FCFA** (2025) | 31/12/2025 | H (dérivé) | BRVM : capitalisation totale 24 781,32 Md = 18,37 % du PIB |
| 5 | Taux de référence des emprunts d'État utilisé par la BRVM dans le BOC | **5,75 %** depuis le 05/01/2024 (5,90 % du 22/02/2021 au 29/12/2023 ; ≈ 5,98 % du 02 au 04/01/2024, transition) | 20/11/2026 | H (déduit de la formule BOC, revérifié le 22/11) | BOC du 22/02/2021, légende : « Prime de risque du marché = (1 / le PER moyen du marché) − le taux de référence actuel des emprunts d'Etat » |
| 6 | Prime de risque du marché publiée par le BOC | **0,58 %** (minimum 2026 : **−0,33 %** le 14/09/2026) contre **4,11 %** en moyenne 2021-2025 | 20/11/2026 | H | BOC |
| 7 | Assouplissement monétaire de la BCEAO en 2025 | Sens confirmé par 4 sources primaires (BRVM, 2 fiches Bloomfield, et BOA Niger de façon indirecte par la « baisse du coût des ressources ») | 2025-2026 | H | §2 |
| 8 | Dernière baisse de taux BCEAO connue | −25 pb, effet au 16/06/2025 (taux minimum de soumission 3,25 %, guichet de prêt marginal 5,25 %) **[NON VÉRIFIÉ]** (niveaux) | 06/2025 | M | bceao.int (non joignable) ; le sens est confirmé par le communiqué BRVM du 20/06/2025 |
| 9 | Décisions BCEAO entre septembre 2025 et novembre 2026 | **non vérifiées** | — | — | bceao.int bloqué |
| 10 | Spread local des emprunts d'État (APE 2026, 7-8 ans) par rapport à la Côte d'Ivoire | ML +0,57 pt ; TG +0,92 ; SN +0,97 ; BF +1,07 ; (2025 : NE +0,95 ; BJ +0,05) | 2025-2026 | H (calcul) | BOC |
| 11 | Coupons 2026 de la Côte d'Ivoire sur le marché régional | 5,45 % (5 ans), 5,70-5,85 % (7 ans), 6,00 % (10 ans) | 2026 | H | BOC |
| 12 | Emprunts du Sénégal sur la BRVM | Record de **405 Md FCFA** (juillet 2025) ; 4 tranches de 6,40 % à 6,95 % reconduites à l'identique en 12/2025, 06/2026 et 09/2026 ; décote de 2 à 15 % sur le secondaire en 2026 | 2025-2026 | H | brvm.org, BOC |
| 13 | Marché obligataire régional segmenté | Le Sénégal emprunte localement à moins de 7 % alors que ses notes ont été fortement dégradées (M) : le spread local ne mesure pas le risque de défaut | 2025-2026 | H/M | §6 |
| 14 | Chocs politiques les plus forts mesurés | Coup d'État et sanctions au Niger (07/2023) : BOA Niger **−26 %** en 9 séances, dont 3 séances à −7,5 % ; la réaction a commencé **6 séances après** le coup. **Ajout de la vérification** : sanctions CEDEAO/UEMOA contre le Mali (09/01/2022) : BOA Mali −7,47 % **dès t+1**, puis −16,9 % au creux en 3 séances, et −8,4 % à 20 séances. Levée de ces sanctions (07/2022) : **+35,7 % en 5 séances**. Le délai n'est donc **pas** systématique | 2022-2023 | H (calcul) / M (dates) | BOC |
| 15 | Corrélations hebdomadaires entre pays | 0,03 à 0,33 : la diversification géographique est réelle | 2021-2026 | H (calcul) | BOC |
| 16 | Caoutchouc naturel (TSR20 SICOM) | moyenne **2,13 USD/kg** (1,83 EUR/kg) à fin septembre 2026, +20 % sur un an ; mais résultat net SAPH −58 % (achats de matière première plus chers) | 30/09/2026 | H | rapport SAPH T3 2026 |
| 17 | Sociétés agro-industrielles cotées en 2026 | Résultats en baisse (SAPH −58 %, SOGB −34 %, PALM CI −12 % sur 9 mois) ; cours 2026 : PALC −8,2 %, SOGC −3,8 %, SPHC −3,2 % alors que le marché fait +42,6 % | 09-11/2026 | H | rapports T3 2026, BOC |
| 18 | Parité | 1 EUR = 655,957 FCFA (fixe) ; EUR/USD moyen ≈ 1,164 (intervalle 1,158-1,170, car le rapport SAPH donne des prix arrondis) sur janvier-septembre 2026 | 2026 | M / M (dérivé) | §7 |

**Lecture d'ensemble.** La BRVM est un marché **ivoiro-sénégalais** (80,7 % de la capitalisation), avec une queue AES (Burkina, Mali, Niger) de 8,5 % par pays de siège, mais d'environ **15 %** en exposition économique, parce que Sonatel tire près de 29 % de sa clientèle mobile du Mali. Le marché vient de connaître deux années exceptionnelles (+25,3 % en 2025, +42,6 % en 2026 au 20/11), en partie portées par l'assouplissement monétaire. Le **rendement bénéficiaire du marché (6,33 %) ne dépasse plus le taux de référence des emprunts d'État (5,75 %) que de 0,58 point**, contre 4 points en moyenne entre 2021 et 2025. Le risque politique est concentré, brutal, et mal reflété dans les taux locaux. Il doit être modélisé par des **règles d'événements** plutôt que par une simple prime lissée.

---

## 1. Ce que les sources primaires de la BRVM révèlent sur la macroéconomie

### 1.1 Taille de l'économie et poids de la bourse (H)

| Date | Capitalisation totale (actions + obligations) | % du PIB UEMOA annoncé | PIB implicite | Source |
|---|---|---|---|---|
| 20/06/2025 | 22 516 Md | « environ 17 % » | ≈ 132 400 Md | brvm.org (actualité du 20/06/2025) |
| 15/10/2025 | 23 979,92 Md | 17,78 % | ≈ 134 870 Md | brvm.org (actualité du 15/10/2025) |
| 31/12/2025 | 24 781,32 Md | 18,37 % | **≈ 134 900 Md** | brvm.org (bilan 2025) |
| 20/11/2026 | 32 753,8 Md (19 328,8 actions + 13 425,0 obligations) | ≈ 24,3 % du PIB 2025 | — | BOC 20/11/2026 (calcul) |

Autres faits primaires (H) :
- **2025** : BRVM Composite +25,26 % ; capitalisation actions 13 330,71 Md au 31/12/2025 (+32,27 %) ; capitalisation obligataire 11 450,61 Md ; **4 204,7 Md FCFA mobilisés sur le marché financier régional, un record, « dominé par les émissions obligataires souveraines »** ; une introduction en bourse (BIIC, 323,45 Md à l'introduction).
- **20/08/2026** : la capitalisation actions franchit **20 036,18 Md** (+50,30 % depuis le 01/01/2026). Services financiers 44,16 %, télécoms 33,36 %, consommation de base 12,54 %. Les 5 premières valeurs (Sonatel, Orange CI, SGBCI, ETI, Coris) pèsent **49,16 %** du total.
- La BRVM attribue explicitement la hausse de 2025 à « *les bonnes perspectives de croissance des pays de l'UEMOA, **l'assouplissement des conditions monétaires par la BCEAO**, l'introduction en bourse de deux nouvelles sociétés … les augmentations du capital de certaines banques* » (communiqués des 20/06/2025 et 15/10/2025).

### 1.2 Le « taux de référence des emprunts d'État » et la prime de risque du BOC (H)

Le BOC publie chaque jour une « **Prime de risque du marché** », définie dans sa légende comme : **(1 / PER moyen du marché) − taux de référence actuel des emprunts d'État**. Nous pouvons donc retrouver le taux de référence : `taux = 100/PER − prime`.

| Période | Taux de référence implicite | Remarque |
|---|---|---|
| 08/01/2018 → 02/07/2019 | ≈ 6,00 % | *Corrigé par la vérification* : le chercheur indiquait 6,50 % pour toute l'année 2019. Valeurs aberrantes autour des fins d'année 2017 et 2018 |
| 03/07/2019 → 28/04/2020 | 6,50 % | |
| 29/04/2020 → 19/02/2021 | incohérent (10,3 à 11,7 %) | Autre définition ou erreurs de saisie : période exclue |
| 22/02/2021 → 29/12/2023 | **5,90 %** | Le 02, le 03 et le 04/01/2024, le taux implicite vaut ≈ 5,98 % (transition) |
| 05/01/2024 → 20/11/2026 | **5,75 %** | Inchangé malgré la baisse de taux de la BCEAO en 2025 : taux administré « collant » |

**Impressions erronées de la prime dans le BOC (vérification du 22/11/2026)** : certains jours, la prime publiée vaut 0,00 ou 0,01 alors que le PER implique environ 0,1 à 0,5 point. C'est le cas le 19/10/2026 (PER 16,90), le 23/10/2026 (PER 17,04) et le 17/11/2026 (PER 15,98, prime 0,01, donc un taux implicite de 6,25 %). D'autres écarts ponctuels existent, par exemple 5,27 % le 13/07/2026. **Règle de code** : `ref_govt_rate` = médiane glissante sur 20 séances de `100/PER − prime`. Un jour isolé qui s'écarte de plus de 0,10 point de cette médiane est ignoré, et le taux n'est déclaré « changé » qu'après au moins 5 séances consécutives au nouveau niveau.

| Année | PER moyen | Prime BOC moyenne | Rendement net moyen des dividendes |
|---|---:|---:|---:|
| 2021 | 11,70 | 2,85 % | 7,10 % |
| 2022 | 9,73 | 4,92 % | 6,49 % |
| 2023 | 9,12 | 5,24 % | 8,03 % |
| 2024 | 9,66 | 4,73 % | 8,47 % |
| 2025 | 14,25 | 2,18 % | 7,68 % |
| 2026 (au 20/11) | 14,77 | **1,13 %** (min −0,33 % le 14/09) | 6,50 % |

Sur 2021-2025, la prime moyenne est de **4,11 %** (médiane 3,91 %, 10e centile 1,58 %, 90e centile 6,76 %). Elle n'a été sous 1 % que **2,9 %** des jours. En 2026, elle est passée sous zéro. Le marché est donc, selon sa propre mesure, au **plus cher de la période observée**.

**Test de pouvoir prédictif (H, calcul)** : sur 2021-2026, la corrélation entre cette prime en fin de mois et le rendement total du marché à 6 et 12 mois est **négative** (−0,34 et −0,33 ; 64 et 58 observations qui se chevauchent). *Vérification* : avec l'indice de prix BRVM Composite au lieu du rendement total, et sur moins d'observations (41 et 35, à cause de mois manquants dans le téléchargement local), on obtient −0,39 et −0,65. Le **signe** est confirmé, la magnitude ne l'est pas. Les périodes de prime élevée (2022-2024) ont été suivies de rendements plus faibles que les périodes de prime basse. Cela contredit la théorie, mais l'échantillon est court et en tendance haussière. **Conclusion : la prime BOC est un indicateur de valorisation et de risque, pas un signal de market timing démontré.** Il faut la tester sur un historique plus long (les BOC remontent au moins à 2019-2020) avant tout usage tactique.

### 1.3 Ce que disent les notations et rapports 2026 des émetteurs (H, qualitatif)

| Source (date) | Pays | Extrait pertinent |
|---|---|---|
| Bloomfield, BOA Mali (fiche 06/2026-05/2027, publiée le 18/08/2026) | ML | Facteur positif : « **Un allègement des taux directeurs de la Banque centrale** ». Fragilité : « un contexte bancaire difficile au Mali en raison de la **crise sécuritaire et énergétique** » |
| Bloomfield, Ecobank CI (22/10/2026) | CI | Facteur positif : « **Un assouplissement de la politique monétaire [de la BCEAO] en 2025** » |
| BOA Niger, rapport T3 2026 (20/10/2026) | NE | Marge portée par « **une baisse du coût des ressources** » ; « redressement … après une année 2025 difficile » |
| Bloomfield, BOA Niger (14/10/2026) | NE | « environnement économique globalement favorable, **porté par les activités extractives et une inflation maîtrisée** » ; « secteur bancaire **encore marqué par les effets des sanctions prises par la CEDEAO** » ; la BOAD a cédé toute sa participation à la SONIMEX en 2025 |
| Bloomfield, Coris Bank (26/08/2026) | BF | « climat des affaires impacté par une **situation politique et sécuritaire encore fragile** au Burkina Faso » |
| Bloomfield, BOA Sénégal (06/10/2026) | SN | « environnement politique **marqué par des tensions** » ; « **dégradation de la situation des finances publiques**, impactant la dynamique économique du pays » |
| GCR, Sonatel (30/06/2026) | SN | Relèvement à AAA(WU), mais « l'environnement macroéconomique au Sénégal s'est détérioré, en raison d'un **niveau d'endettement public désormais considéré comme préoccupant** » |
| Sonatel, résultats T3 2026 | SN, ML, GN… | « **Dépréciation du franc guinéen** » ; « évolution en vue de la **taxe applicable à la monnaie électronique au Sénégal** » ; BCEAO : transferts gratuits de 0 à 8 000 FCFA, frais plafonnés à 0,8 % au-delà ; contraintes d'approvisionnement en énergie |
| Sonatel, états financiers 2025 | ML | Clients au Mali **−13,7 %** en 2025 (11,6 M contre 13,5 M) ; nouvelles taxes au Mali (+2 % sur l'accès au réseau, 10 % sur les recharges, 1 % sur les retraits, 0,5 % sur le chiffre d'affaires : « Contribution spéciale de solidarité ») |
| ONATEL, rapport de gestion 2025 | BF | « contexte sécuritaire difficile » ; signature d'un **protocole de « free roaming » AES** (Mali, Niger, Burkina) |

**Lien banques–souverain (H)** : les banques détiennent beaucoup de dette de leur propre État. Fin 2025, les effets publics représentent **31,3 %** du bilan de BOA Mali (185,7 Md sur 593,5 Md) et les obligations et effets publics **35,7 %** de celui de Coris Bank (1 070,4 Md sur 2 997,8 Md), selon les fiches Bloomfield (ratios revérifiés le 22/11/2026 : 185 699 / 593 455 = 31,3 % ; 1 070 425 / 2 997 779 = 35,7 %). Or le secteur « services financiers » compte 17 des 48 sociétés cotées et pèse environ 44 % de la capitalisation (44,16 % au 20/08/2026). *Correction* : ces 17 sociétés comprennent 14 banques, 2 holdings bancaires (ETIT, ORGT) et une société de crédit-bail et de crédit à la consommation (SAFCA), qui n'est pas une banque. **Un stress souverain se transmet donc directement aux actions bancaires du pays.** C'est le canal principal de risque pays à la BRVM.

---

## 2. Politique monétaire de la BCEAO

### 2.1 Cadre (M)

- Instruments : **taux minimum de soumission** aux appels d'offres d'injection de liquidité (taux directeur principal) et **taux du guichet de prêt marginal** (plafond du corridor, habituellement 200 pb au-dessus). Coefficient de réserves obligatoires : **3 %** depuis 2017 (M).
- Objectif : stabilité des prix, cible d'inflation **2 % ± 1 point** (zone 1-3 %) (M).
- Ancrage : parité fixe avec l'euro (§7). La BCEAO suit donc en partie la BCE. Un écart de taux trop défavorable fragilise les réserves de change.
- Calendrier : le Comité de politique monétaire (CPM) se réunit **4 fois par an** (en général en mars, juin, septembre et décembre), avec effet le 16 du mois dans la plupart des cas récents (M).

### 2.2 Décisions récentes

| Date d'effet | Taux minimum de soumission | Guichet de prêt marginal | Sens | Conf. | Source à vérifier |
|---|---:|---:|---|---|---|
| 16/06/2022 | 2,25 % | 4,25 % | +25 pb | M | bceao.int, communiqués du CPM |
| 16/09/2022 | 2,50 % | 4,50 % | +25 pb | M | idem |
| 16/12/2022 | 2,75 % | 4,75 % | +25 pb | M | idem |
| 16/03/2023 | 3,00 % | 5,00 % | +25 pb | M | idem |
| 16/06/2023 | 3,25 % | 5,25 % | +25 pb | M | idem |
| 16/12/2023 | **3,50 %** | **5,50 %** | +25 pb (sommet du cycle) | M | idem |
| 2024 | inchangés | inchangés | pause | M | idem |
| 16/06/2025 | **3,25 %** | **5,25 %** | −25 pb | M (le **sens** est H) **[NON VÉRIFIÉ]** (niveaux et date) | idem ; le sens est confirmé par BRVM 20/06/2025 et 15/10/2025, Bloomfield (BOA Mali, Ecobank CI) |
| 09/2025 → 11/2026 | **non vérifié** | **non vérifié** | La fiche Bloomfield de BOA Mali (2026) cite « un allègement des taux directeurs », sans date ni niveau (le pluriel désigne simplement les deux taux du corridor). D'autres baisses après juin 2025 sont **possibles mais non confirmées** | — | bceao.int (bloqué) |

**Vérification du 22/11/2026** : tout le tableau 2022-2025 est **[NON VÉRIFIÉ]** en source primaire. bceao.int ne se résout pas, et le budget WebSearch était épuisé pour le vérificateur aussi. Les valeurs concordent avec la connaissance antérieure du vérificateur, mais cela ne vaut pas preuve. Elles ne doivent pas être codées sans contrôle.
**Introuvable dans cette session** : le niveau exact des taux directeurs au 22/11/2026, le calendrier des CPM de 2026 et les volumes d'injection de liquidité. **Action** : autoriser `www.bceao.int` puis remplir `config/macro_uemoa.yaml` (§14).

### 2.3 Transmission vers la BRVM : ce que montrent les données (H, calcul)

| Événement | Fenêtre | Marché (rendement total pondéré par la capitalisation) |
|---|---|---|
| Hausse de 25 pb (effet 16/12/2023) | [0 ; +20] séances | 0,0 % |
| Hausse de 25 pb (effet 16/12/2023) | [0 ; +60] | +2,1 % |
| Baisse de 25 pb (effet 16/06/2025) | [0 ; +20] | +0,1 % |
| Baisse de 25 pb (effet 16/06/2025) | [0 ; +60] | +7,3 % |

Pas de réaction immédiate : les décisions sont attendues, et elles agissent par le coût de refinancement des banques et la revalorisation de leurs portefeuilles de titres publics, qui se reflètent dans les résultats des trimestres suivants (BOA Niger 2026 : PNB +7,9 %, coût des ressources en baisse). **Pour la plate-forme** : la variable utile est le **cycle** (cumul des variations sur 12 mois), en particulier pour les banques, et non le jour de la décision.

---

## 3. Inflation et croissance

### 3.1 Inflation (UEMOA, moyenne annuelle)

| Année | Inflation | Conf. | Source à vérifier |
|---|---|---|---|
| 2022 | ≈ 7,4 % (pic) | M | BCEAO, rapports sur la politique monétaire |
| 2023 | ≈ 3,7 % | M | idem |
| 2024 | ≈ 3,5 % | M | idem |
| 2025 | nettement plus basse, de l'ordre de 0 à 1,5 % selon les relevés trimestriels | L | idem |
| 2026 | **introuvable dans cette session** (Bloomfield parle d'« inflation maîtrisée » au Niger, H) | — | idem |

Les chiffres 2022-2024 ci-dessus sont **[NON VÉRIFIÉ]** : aucune source primaire n'était accessible au vérificateur.

**Ajout de la vérification (source secondaire datée)** : les états financiers 2025 de Sonatel (p. 5, « Données économiques : source FMI DEC 2025 ») donnent, pour l'année 2025 probablement :

| Pays | Croissance du PIB | Inflation |
|---|---:|---:|
| Sénégal | 8,4 % | +2 % |
| Mali | 4,9 % | +3 % |
| Guinée | 7 % | +3,7 % |
| Guinée-Bissau | 5,0 % | +2 % |
| Sierra Leone | 4,6 % | +13 % |

Confiance M : c'est le FMI cité par un émetteur, l'année n'est pas précisée, et le chiffre de la Sierra Leone semble élevé. URL : https://www.brvm.org/sites/default/files/20260216_-_etats_financiers_2025_et_attestation_des_cac_-_sonatel_sn.pdf

### 3.2 Croissance du PIB réel

| Zone / pays | Ordre de grandeur 2024 | Moteur ou frein principal | Conf. |
|---|---|---|---|
| UEMOA | ≈ 6 % (≈ 5,3 % en 2023) | investissement public, hydrocarbures (SN, NE), agriculture | M |
| Côte d'Ivoire | ≈ 6 % | services, BTP, cacao ; programme FMI 2023-2026 | M |
| Sénégal | ≈ 6 %, avec une accélération attendue en 2025 grâce au pétrole (Sangomar, 1er baril en juin 2024) et au gaz (GTA, 2025) | hydrocarbures ; crise budgétaire | M |
| Niger | très forte en 2024 (exportations de pétrole par l'oléoduc Niger–Bénin) | pétrole, uranium ; sanctions en 2023-2024 | M |
| Bénin | ≈ 6,5-7,5 % | port de Cotonou, zone industrielle de Glo-Djigbé | M |
| Togo | ≈ 5-5,5 % | port de Lomé, logistique | M |
| Burkina Faso | ≈ 3-5 % | or ; insécurité | L |
| Mali | ≈ 4-5 % en 2024 ; crise énergétique et sécuritaire en 2025-2026 (H, Bloomfield) | or ; conflit minier ; blocus des carburants (L) | L |
| Guinée-Bissau | ≈ 4,5-5 % | noix de cajou | L |

**Introuvable dans cette session** : les chiffres 2025 réalisés et les prévisions 2026 par pays. Sources à charger : BCEAO (rapport annuel, rapport sur la politique monétaire), FMI (base WEO d'avril et d'octobre). La plate-forme doit stocker chaque **millésime** de prévision avec sa date de publication, pour éviter tout biais d'anticipation.

---

## 4. Notations souveraines et eurobonds

### 4.1 Notations des grandes agences (non revérifiées) [NON VÉRIFIÉ]

| Pays | Situation connue (mi-2026) | Tendance 2024-2026 | Conf. |
|---|---|---|---|
| Côte d'Ivoire | Catégorie BB (S&P BB ; Moody's Ba2 depuis 2024 ; Fitch BB-/BB) : meilleur crédit de l'Union | relèvements en 2024-2025 | M (agences) / L (crans exacts) |
| Bénin | Catégorie BB- / Ba3 environ | relèvements récents | L |
| Togo | Catégorie B | stable | L |
| Sénégal | Forte dégradation après la révélation, en 2024-2025, de déficits et d'une dette sous-déclarés : de B+/Ba3 vers **B- à CCC+ / Caa** | **forte baisse** (plusieurs crans en 2024-2025) | M (sens) / L (crans exacts) |
| Burkina Faso | S&P CCC+ | — | L |
| Mali, Niger, Guinée-Bissau | Pas de note S&P/Fitch publique connue ; Niger noté Caa par Moody's après le coup d'État | — | L |

**Notations régionales (H)** : les agences agréées citées par la BRVM sont **Bloomfield Investment Corporation** et **EMR–WARA** ; GCR note aussi des émetteurs de l'Union (Sonatel, Senelec). Leurs échelles sont **régionales** : un AAA(WU) n'est pas un AAA mondial. Aucune note souveraine régionale n'a été trouvée dans la rubrique « notations financières » de brvm.org pour 2025-2026 : les pages TPCI, TPBF et TPBJ existent mais sont vides.

### 4.2 Eurobonds (non revérifiés) [NON VÉRIFIÉ]

| Émetteur | Opérations connues | Conf. |
|---|---|---|
| Côte d'Ivoire | Retour en janvier 2024 (≈ 2,6 Md USD, échéances 2033 et 2037) puis émissions en 2025 | M (2024) / L (2025) |
| Bénin | Eurobond en dollars à long terme (2038) en 2024 | M |
| Sénégal | Eurobond 2031 en 2024 ; rendements secondaires à **deux chiffres** en 2025, dans la zone de détresse, après les révélations sur la dette | M (sens) / L (niveaux) |

**Introuvable dans cette session** : les spreads EMBI ou z-spreads au 22/11/2026. Source recommandée : prix Bloomberg/Refinitiv, ou à défaut les publications de JP Morgan EMBI. **Conséquence pour le modèle** : la prime de risque pays ne peut pas reposer en temps réel sur les eurobonds. Elle repose sur les **spreads locaux mesurés dans le BOC (H)**, corrigés par une surcote politique (§12).

---

## 5. Dette publique et règles budgétaires

| Élément | Valeur | Conf. | Source à vérifier |
|---|---|---|---|
| Critères de convergence de l'UEMOA (1er rang) | solde budgétaire global dons compris ≥ −3 % du PIB ; inflation ≤ 3 % ; dette ≤ 70 % du PIB | M | uemoa.int |
| Suspension puis retour des critères | suspendus après le COVID ; retour visé en 2025 | M/L | uemoa.int |
| Sénégal : audit publié le 26/09/2024 | déficit et dette 2019-2023 sous-déclarés | M | gouvernement du Sénégal |
| Sénégal : Cour des comptes (12/02/2025) | dette fin 2023 ≈ **99,7 % du PIB** (contre ≈ 74 % publié) ; déficit 2023 ≈ **12,3 %** (contre 4,9 %) **[NON VÉRIFIÉ]** (concorde avec la connaissance du vérificateur ; aucune URL consultable) | M | courdescomptes.sn |
| Sénégal : FMI | programme d'environ 1,8 Md USD (2023) suspendu après la fausse déclaration ; nouveau programme négocié en 2025-2026, **état au 22/11/2026 non vérifié** | M / L | imf.org/en/Countries/SEN |
| Sénégal : situation 2026 | « dégradation de la situation des finances publiques » (Bloomfield, 10/2026) ; endettement « préoccupant » (GCR, 06/2026) | **H** | fiches BOA SN et Sonatel sur brvm.org |
| Côte d'Ivoire | dette autour de 55-60 % du PIB ; programme FMI 2023-2026 | L | imf.org/en/Countries/CIV |

---

## 6. Marché obligataire régional : le vrai « taux sans risque local »

Le BOC liste toutes les obligations d'État par appel public à l'épargne (APE). La date de première cotation et le coupon de chaque ligne permettent de reconstruire une **courbe des coupons primaires par pays**. Ces emprunts sont placés au pair par syndication : le coupon est donc le taux d'émission. Les adjudications d'UMOA-Titres (bons et obligations assimilables du Trésor) ne sont pas dans le BOC et `umoatitres.org` n'était pas joignable.

### 6.1 Coupons moyens des emprunts d'État par pays, maturité et année d'émission (H, calcul sur 196 lignes, BOC 2020-2026)

Maturité = année d'échéance − année d'émission.

| Maturité | Année | BF | BJ | CI | ML | NE | SN | TG |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5-6 ans | 2023 | 6,00 | — | 5,90 | — | 6,25 | 6,08 | — |
| | 2024 | 6,40 | — | 5,90 | 6,35 | — | 6,25 | — |
| | 2025 | 6,60 | — | 5,80 | 6,35 | 6,60 | 6,60 | 6,45 |
| | 2026 | 6,75 | — | **5,45** | — | — | 6,60 | 6,50 |
| 7-8 ans | 2022 | — | — | 5,65 | 6,20 | — | — | — |
| | 2023 | 6,30 | 5,70 | 5,95 | 6,45 | — | 6,22 | — |
| | 2024 | 6,68 | — | 6,00 | 6,55 | — | 6,45 | — |
| | 2025 | 6,80 | 6,00 | 5,95 | 6,55 | 6,90 | 6,75 | 6,60 |
| | 2026 | 6,85 | — | **5,78** | 6,35 | — | 6,75 | 6,70 |
| 9 ans et plus | 2025 | 7,00 | 6,15 | — | — | — | 6,95 | — |
| | 2026 | — | — | **6,00** | 6,55 | — | 6,95 | — |

Lignes 2026 les plus récentes (H) : TPCI 5,45 % 2026-2031 et 5,70 % 2026-2033 (cotées le 25/09/2026) ; TPCI 5,85 % 2026-2033 et 6,00 % 2026-2036 (11/06/2026) ; Sénégal 6,40/6,60/6,75/6,95 % 2026-2029/31/33/36 (22/09/2026) ; Mali 6,35 % 2026-2033 et 6,55 % 2026-2036 (27/08/2026) ; Burkina « Diaspora Bonds » 6,75 % 2026-2031 et 6,85 % 2026-2033 (03/09/2026) ; Togo 6,50 % 2026-2031 et 6,70 % 2026-2033 (23/04/2026) ; Bénin 6,00 % 2025-2032 et 6,15 % 2025-2035 (30/01/2026) ; Niger 6,60 % 2025-2030 et 6,90 % 2025-2032 (22/04/2025 et 22/07/2025).

### 6.2 Spreads locaux par rapport à la Côte d'Ivoire, maturité 7-8 ans (points de %) (H, calcul)

| Pays | 2023 | 2024 | 2025 | 2026 | Variation 2025→2026 |
|---|---:|---:|---:|---:|---:|
| Bénin | −0,25 | — | +0,05 | — | — |
| Mali | +0,50 | +0,55 | +0,60 | +0,57 | −0,03 |
| Togo | — | — | +0,65 | +0,92 | **+0,27** |
| Sénégal | +0,27 | +0,45 | +0,80 | +0,97 | **+0,17** |
| Burkina Faso | +0,35 | +0,68 | +0,85 | +1,07 | **+0,22** |
| Niger | — | — | +0,95 | — | — |

### 6.3 Prix sur le marché secondaire : un signal de stress tardif mais réel (H, calcul)

Médiane trimestrielle de (cours traité / valeur nominale restante) des lignes souveraines échangées :

| Trimestre | BF | BJ | CI | ML | NE | SN | TG |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 T1-T4 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 |
| 2025 T4 | 1,000 | 1,000 | 1,000 | 1,000 | **0,980** | 1,000 | 1,000 |
| 2026 T2 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 0,995 | 1,000 |
| 2026 T3 | 1,000 | 1,000 | 1,000 | 1,000 | **0,950** | **0,980** | 1,000 |
| 2026 T4 (au 20/11) | 1,000 | 1,000 | 1,000 | 1,000 | 0,975 | **0,980** | 1,000 |

**Vérification (22/11/2026)** : un recalcul indépendant (première transaction de chaque ligne par séance) reproduit ces médianes : SN 0,985 au T3 et 0,980 au T4 2026 ; NE 0,980 au T4 2025, 0,95 au T3 et 0,975 au T4 2026. **Mais** les médianes du Niger reposent sur **3 à 4 transactions par trimestre** en 2026, contre 64 à 84 pour le Sénégal. Un déclencheur fondé sur la médiane doit donc exiger un nombre minimal de transactions (§13.4).

Exemples au 20/11/2026 (BOC) : **EOS.O27** (Sénégal 6,60 % 2025-2030) traité à **9 400** pour 10 000 de nominal ; **EOS.O19** (6,60 % 2025) à 8 255,63 pour 8 750 de nominal (94,4 %) ; **EOS.O24** (6,75 % 2025-2032) avec un cours de référence de **8 500**, soit 85 %. Les lignes ivoiriennes, maliennes et burkinabè restent au pair.

### 6.4 Interprétation

1. **Segmentation** : les spreads locaux (≤ 1,1 point) sont très inférieurs à ce que suggèrent les notes internationales du Sénégal ou du Burkina (M). Explications plausibles (M) : investisseurs captifs (banques de l'Union, qui peuvent refinancer ces titres auprès de la BCEAO), absence de vendeurs à découvert, prix d'émission administrés par syndication, et marché secondaire très illiquide où les cours sont « collants ».
2. **Le taux sans risque local à utiliser** :
   - **5,75 %** : taux de référence officiel du BOC, stable depuis janvier 2024 (H). C'est le choix le plus simple et le plus traçable.
   - **Courbe ivoirienne** : 5,45 % à 5 ans, 5,70-5,85 % à 7 ans, 6,00 % à 10 ans (H, 2026). C'est la meilleure proxy « sans risque » de l'Union (meilleur crédit, marché le plus profond).
   - **Taux par pays** = courbe CI + spread local du §6.2. Ce n'est **pas** un taux sans risque, mais le coût de financement souverain local.
   - **Fiscalité** : les intérêts des emprunts d'État de l'Union sont souvent exonérés pour les personnes physiques résidentes (M, à vérifier dans chaque note d'information). Les comparaisons avec les dividendes, eux taxés (doc 01, §4), doivent se faire **après impôt**.
3. **Signal pour la plate-forme** : la **variation** du spread local entre deux émissions (Sénégal +0,17, Burkina +0,22, Togo +0,27 point en 2026) et la **décote de prix** sur le secondaire (Sénégal et Niger en 2026) sont des indicateurs de stress souverain disponibles **gratuitement et sans délai** dans le BOC. Ils doivent alimenter le score pays (§13).

---

## 7. Parité FCFA/euro et projet ECO

| Fait | Valeur / date | Conf. | Source à vérifier |
|---|---|---|---|
| Parité fixe | **1 EUR = 655,957 FCFA** depuis le 01/01/1999 | M (parité légale, quasi certaine) | bceao.int ; banque-france.fr (rapports de la Zone franc) |
| Garantie de convertibilité | assurée par le Trésor français | M | idem |
| Réforme annoncée le 21/12/2019 | fin du dépôt de 50 % des réserves au compte d'opérations du Trésor français ; retrait de la France des instances de la BCEAO ; garantie maintenue ; changement de nom en « ECO » prévu mais **non réalisé** | M | idem |
| ECO de la CEDEAO (15 pays) | lancement plusieurs fois reporté ; horizon 2027 évoqué | M/L | ecowas.int |
| Monnaie de l'AES | discours politiques sur une monnaie commune ; **aucune sortie de l'UEMOA ou de la BCEAO constatée** au 20/11/2026 (H indirect, voir §8.1) | L (projet) / H (pas de sortie) | §8.1 |
| EUR/USD moyen sur janvier-septembre 2026 | **≈ 1,164** (rapport des prix SICOM publiés par SAPH : 2,13 USD/kg = 1,83 EUR/kg). Texte revérifié par OCR le 22/11/2026. Les deux prix étant arrondis au centime, l'intervalle est **1,158 à 1,170**. C'est en outre une moyenne pondérée par les prix du caoutchouc, pas un fixing BCE | **M** (dérivé ; corrigé de H à M) | rapport SAPH T3 2026 |
| USD/FCFA moyen sur janvier-septembre 2026 | ≈ 655,957 / 1,164 ≈ **563,5** (intervalle 560,6 à 566,5) | M (dérivé) | idem |

**Mécanisme clé (H)** : les matières premières sont cotées en dollars, mais les sociétés cotées comptent en FCFA, donc en euros. SAPH l'écrit explicitement : TSR20 « *en progression de près de 20 % … Exprimée en monnaie locale, cette progression est ramenée à +16 % en raison du repli du dollar US face à l'euro* ». La plate-forme doit convertir tout prix de matière première en FCFA via EUR/USD.

**Risque de rupture de la parité** : faible à court terme dans le scénario central (M), mais c'est le risque extrême majeur pour un investisseur hors zone. Une sortie d'un pays de l'AES de l'UEMOA créerait un risque de change et de redénomination pour les titres de ce pays (BOAM, BOAN, BOABF, CBIBF, ONTBF, et Sonatel pour ses filiales). **Règle de la plate-forme** : un signal officiel de sortie (communiqué d'un chef d'État ou de la BCEAO) déclenche la règle « choc extrême » du §13.4.

---

## 8. Situation politique, pays par pays

### 8.1 L'Alliance des États du Sahel (Mali, Burkina Faso, Niger)

| Date | Événement | Conf. |
|---|---|---|
| 26/07/2023 | Coup d'État au Niger | M |
| 30/07/2023 | Sanctions de la CEDEAO et de l'UEMOA contre le Niger (dont le gel des opérations avec la BCEAO) | M |
| 16/09/2023 | Charte du Liptako-Gourma : création de l'AES | M |
| 28/01/2024 | Annonce conjointe du retrait de la CEDEAO | M |
| 24/02/2024 | Levée de l'essentiel des sanctions de la CEDEAO contre le Niger | M |
| 06/07/2024 | Traité de Niamey : Confédération AES | M |
| 29/01/2025 | Retrait effectif de la CEDEAO | M |
| 2025-2026 | Mali : crise sécuritaire et **énergétique** (pénuries de carburant) | **H** (Bloomfield, 08/2026) ; détails L |
| 2025 | Mali : nouvelles taxes télécoms ; parc Sonatel Mali −13,7 % | **H** (Sonatel) |
| 2025 | Niger : la BOAD cède sa participation dans BOA Niger à la SONIMEX | **H** (Bloomfield) |
| 2025-2026 | Protocole de « free roaming » AES | **H** (ONATEL) |

Les dates M de ce tableau sont **[NON VÉRIFIÉ]** en source primaire dans cette session. Elles concordent avec la connaissance du vérificateur, mais aucune URL n'a pu être consultée. Ajouts de la vérification, dates M également **[NON VÉRIFIÉ]**, réactions H calculées sur les BOC (§9) : coup d'État au Mali le 18/08/2020 ; sanctions CEDEAO et UEMOA contre le Mali, avec gel des opérations avec la BCEAO, annoncées le dimanche 09/01/2022 et levées début juillet 2022 ; coups d'État au Burkina Faso les 24/01/2022 et 30/09/2022, sans sanctions économiques UEMOA.

**Maintien dans l'UEMOA (H, preuves indirectes)** : les trois pays continuent d'émettre sur le marché régional en FCFA (Mali en avril et août 2026 ; Burkina en mars et septembre 2026 ; Niger en avril et juillet 2025). Leurs banques cotées citent « l'allègement des taux directeurs de la Banque centrale » (BOA Mali, 2026). **Rien dans les sources consultées n'indique une sortie de l'UEMOA ou de la BCEAO au 20/11/2026.** Le projet de monnaie AES reste un risque de queue (L).

### 8.2 Côte d'Ivoire

- Élection présidentielle du 25/10/2025 : réélection d'Alassane Ouattara ; plusieurs opposants majeurs exclus (M, **[NON VÉRIFIÉ]**). Réaction du marché ivoirien : **+1,5 %** sur [0 ; +5] et **+3,7 %** sur [0 ; +20] séances (H, calcul). Le scénario de crise post-électorale (souvenir de 2010-2011) ne s'est pas produit.
- La Côte d'Ivoire est le « pays ancre » : meilleure signature régionale, 57,8 % de la capitalisation, coupons les plus bas (5,45-6,00 %, H).
- Agriculture : la BMPA-CI (bourse des matières premières agricoles) a démarré le 28/05/2025 avec la noix de cajou (440 FCFA/kg en moyenne), la noix de cola et le maïs (H). La Côte d'Ivoire est le 1er producteur mondial de cajou (≈ 1,05 Mt par an en moyenne sur 5 ans) et de cola (≈ 250 kt) (H, BRVM/ARRE).

### 8.3 Sénégal

- Présidentielle du 24/03/2024 : victoire de Bassirou Diomaye Faye au 1er tour (M). Réaction : +0,1 % sur 5 jours, +3,5 % sur 20 jours par rapport à la CI (H) : le marché a bien accueilli une alternance sans violence.
- 26/09/2024 : audit des finances publiques (M). Réaction : **−5,0 %** sur 20 séances et **−8,9 %** sur 60 séances par rapport à la CI (H).
- 12/02/2025 : rapport de la Cour des comptes (M). Réaction : −2,7 % sur 20 séances (H) : l'information était en grande partie déjà dans les prix.
- 2026 : tensions politiques et dégradation des finances publiques (H, Bloomfield 10/2026) ; endettement « préoccupant » (H, GCR 06/2026) ; projet de taxe sur la monnaie électronique (H, Sonatel T3 2026), défavorable à Orange Money ; Jeux olympiques de la jeunesse de Dakar 2026 (H).
- Hydrocarbures : Sangomar (pétrole, depuis 2024) et GTA (gaz, depuis 2025) (M). TotalEnergies Marketing SN distribue des carburants à prix encadrés : peu de lien direct avec la production.
- **Paradoxe 2026 (H)** : les actions sénégalaises ont fait **+63 %** (pondération par la capitalisation, rendement total au 20/11/2026), mieux que la Côte d'Ivoire (+34 %), alors que le souverain se dégrade. Sonatel, premier poids du pays, est une machine à dividendes diversifiée géographiquement et notée AAA(WU) par GCR. Pour Sonatel, le risque sénégalais passe par la **fiscalité** (taxes sur la monnaie électronique) plus que par le défaut.

### 8.4 Bénin, Togo, Guinée-Bissau

| Pays | Faits | Conf. |
|---|---|---|
| Bénin | Présidentielle d'avril 2026 ; tentative de coup d'État signalée en décembre 2025 ; **résultats et détails non vérifiés** | L |
| Bénin (marché) | Spread local quasi nul par rapport à la CI (+0,05 point en 2025) ; BIIC introduite en 2025 (323,45 Md), LNB et BOA Bénin cotées | H |
| Togo | Passage en 2024-2025 à une Constitution parlementaire (Faure Gnassingbé président du Conseil des ministres) | M |
| Togo (marché) | Spread en hausse (+0,65 → +0,92 point) ; ETIT et Oragroup sont des holdings régionales, peu exposées au Togo lui-même | H |
| Guinée-Bissau | Élections de novembre 2025 suivies d'une prise de pouvoir par l'armée (L) ; **aucune société cotée** (H) ; exposition indirecte via Sonatel (4 % des clients, nouvelle licence de 10 ans en 2026, H) | L / H |

---

## 9. Réactions mesurées du marché aux chocs pays (H, calcul sur les BOC)

Méthode : indice pays pondéré par la capitalisation (nombre de titres au 31/12/2025, cours ajustés, rendement total). Rendement anormal = indice pays − indice Côte d'Ivoire. Pour les événements « ALL » et « CI », le rendement est brut. Les dates d'événements sont **M** ; les rendements sont **H**. Avec 1 à 3 titres par pays, ce sont des **cas illustratifs, pas des tests statistiques**.

| Séance de référence | Événement | Pays | [−5 ; −1] | [0 ; +5] | [0 ; +20] | [0 ; +60] |
|---|---|---|---:|---:|---:|---:|
| 26/07/2023 | Coup d'État au Niger | NE | −1,6 | −8,3 | **−22,8** | **−32,2** |
| 31/07/2023 | Sanctions CEDEAO/UEMOA (sommet du 30/07) | NE | −3,7 | **−24,2** | −20,9 | −28,6 |
| 29/01/2024 | Annonce du retrait AES de la CEDEAO (28/01) | ML | −5,3 | −6,0 | −2,7 | +20,9 |
| 29/01/2024 | idem | BF | −0,6 | −4,9 | −4,3 | +0,4 |
| 29/01/2024 | idem | NE | −0,2 | −11,5 | −2,3 | +9,4 |
| 05/02/2024 | Report de la présidentielle sénégalaise (03/02) | SN | −0,5 | 0,0 | +3,4 | +10,4 |
| 28/02/2024 | Levée des sanctions contre le Niger (24/02) | NE | +3,5 | **+14,5** | +16,5 | +11,9 |
| 25/03/2024 | Présidentielle sénégalaise | SN | −0,7 | +0,1 | +3,5 | +3,3 |
| 26/09/2024 | Sénégal : audit des finances publiques | SN | −1,4 | −2,7 | −5,0 | −8,9 |
| 29/01/2025 | Retrait AES effectif | ML | −5,9 | −3,1 | +5,7 | +49,2 |
| 29/01/2025 | idem | BF | −1,3 | +2,3 | +1,9 | +6,0 |
| 29/01/2025 | idem | NE | −10,0 | −0,8 | +20,4 | +24,3 |
| 12/02/2025 | Sénégal : rapport de la Cour des comptes | SN | +1,7 | −2,9 | −2,7 | +0,2 |
| 27/10/2025 | Présidentielle ivoirienne (25/10) | CI (brut) | +1,9 | +1,5 | +3,7 | +6,7 |

**Cas ajoutés par la vérification (prix bruts de clôture tirés des BOC locaux, pas des rendements anormaux ; dates M [NON VÉRIFIÉ])**

| Séance de référence | Événement | Titre | Trajectoire observée (BOC) | Classe |
|---|---|---|---|---|
| 18/08/2020 | Coup d'État au Mali (sanctions CEDEAO, sans gel BCEAO) | BOAM | 975 → plus bas 960 (−1,5 %) sur 10 séances | modéré, faible |
| 10/01/2022 | Sanctions CEDEAO et UEMOA contre le Mali, gel BCEAO (sommet du 09/01) | BOAM | 1 540 → 1 425 (**−7,47 % dès t+1**) → 1 320 (−7,37 %) → plus bas 1 280 (**−16,9 %** en 3 séances) ; 1 410 à 20 séances (−8,4 %) | **sévère** |
| 24/01/2022 | Coup d'État au Burkina (pas de sanctions UEMOA) | BOABF / CBIBF / ONTBF | BOABF 6 500 → 5 950 (−8,5 %) ; CBIBF −8 % puis rattrapage ; ONTBF stable | modéré |
| 30/09/2022 | 2e coup d'État au Burkina | BOABF / CBIBF / ONTBF | CBIBF −7,14 % à t+1 ; ONTBF 4 100 → 3 565 (−13 %) en 10 séances ; BOABF −4 à −6 % | modéré |
| 04/07/2022 | Levée des sanctions contre le Mali (début juillet 2022) | BOAM | 1 400 (01/07) → 1 900 (08/07) : **+35,7 % en 5 séances** (3 séances au plafond de +7,5 %) | soulagement |

Remarque sur la ligne « Levée des sanctions contre le Niger » ci-dessus : le +14,5 % est un rendement **anormal** par rapport à la CI. Le prix brut de BOAN passe de 5 190 (clôture du 27/02/2024) à 5 790 (06/03/2024), soit **+11,6 %**. Les BOC des 26 et 27/02/2024 manquent dans le téléchargement local.

**Trajectoire de BOA Niger après le coup d'État (H, BOC)** : 5 900 FCFA le 26/07/2023 ; −1,78 % le 27/07 ; puis **−7,46 %, −7,47 %, −7,44 %** les 03, 04 et 08/08 (plafond de baisse) ; plus bas à 4 355 (−26 %) ; rebond à 4 915 (+12,9 %) en 2 séances ; stabilisation vers 4 700 (−20 %).

**Enseignements quantitatifs (H ; corrigés par la vérification du 22/11/2026)**
1. **Choc « sévère »** : un coup d'État ou une crise suivis de **sanctions financières UEMOA, avec gel des opérations avec la BCEAO**. Deux cas seulement : Niger 2023 (creux −26,2 %, encore −20 % après un mois) et Mali 2022 (creux −16,9 %, −8,4 % à 20 séances). La moyenne des creux est de **≈ −21 %**. Le chercheur avait retenu −20 à −32 % en se fondant sur le seul cas nigérien.
2. **Choc « modéré »** : coup d'État **sans** sanctions UEMOA (Mali 2020, Burkina 01/2022 et 09/2022 : de −1,5 à −13 %), rupture diplomatique ou révélation budgétaire (−5 à −11 % à 5-20 séances). Ces baisses sont souvent **rattrapées en 60 séances**.
3. **Vitesse de réaction variable.** La limite de ±7,5 % par jour et la faible liquidité étalent l'ajustement sur plusieurs séances. Au Niger en 2023, la vraie baisse n'a commencé que **6 séances** après le coup. **Mais** au Mali en 2022, le titre a touché le plafond de baisse **dès la première séance** suivant l'annonce des sanctions. On ne peut donc **pas** compter sur un délai pour sortir avant la baisse. Le seul avantage robuste est d'étaler les ventes sur plusieurs séances, sachant qu'en séance de plafond de baisse les vendeurs ne sont souvent pas servis (doc 01).
4. Les **bonnes nouvelles** aussi peuvent être intégrées sur plusieurs séances : levée des sanctions contre le Niger, +14,5 % anormal en 5 séances ; levée de celles contre le Mali, **+35,7 % brut en 5 séances**.
5. Avec **2 chocs sévères et 3 coups « modérés »** observés, les paramètres de saut sont des **ordres de grandeur**, pas des estimations statistiques.

### 9.1 Performance et risque par pays, 11/01/2021 → 20/11/2026 (H, calcul)

Rendement total pondéré par la capitalisation (nombre de titres fixé au 31/12/2025 : approximation).

| Pays (nb de titres) | 2021* | 2022 | 2023 | 2024 | 2025 | 2026 (au 20/11) | TCAC | Volatilité ann. | Perte max. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CI (35) | 98,9 | 3,9 | 9,7 | 47,2 | 39,7 | 34,4 | 40,7 % | 13,4 % | −13,7 % |
| SN (3) | 24,2 | 19,0 | 29,4 | 43,4 | 18,6 | 63,2 | 36,4 % | 19,2 % | −13,6 % |
| BF (3) | 50,5 | −12,7 | 9,8 | 8,9 | 20,6 | 118,8 | 30,3 % | 20,3 % | −23,6 % |
| BJ (3) | 65,2 | 21,9 | 18,4 | 22,1 | 21,6 | 51,8 | 36,7 % | 26,4 % | −33,3 % |
| TG (2) | 20,2 | 3,0 | −12,6 | −19,8 | 37,8 | 110,3 | 18,7 % | 36,2 % | −50,3 % |
| ML (1 : BOAM) | 35,0 | −5,7 | 5,4 | 109,8 | 130,7 | 35,3 | 49,8 % | 45,3 % | −42,2 % |
| NE (1 : BOAN) | 69,2 | 22,8 | 3,4 | −15,1 | 9,5 | 69,3 | 25,5 % | 35,3 % | −44,2 % |
| Marché | 58,0 | 6,2 | 12,2 | 38,2 | 32,6 | 49,0 | 35,6 % | 10,2 % | −11,3 % |

\* 2021 partiel (à partir du 11/01/2021). Les chiffres 2021 de la CI sont gonflés par des micro-capitalisations et des opérations sur titres de 2021 (NTLC, STBC, SIVC, BNBC) : à interpréter avec prudence.

**Corrélations des rendements hebdomadaires (H)** : CI-SN 0,21 ; CI-BF 0,24 ; CI-ML 0,18 ; CI-NE 0,27 ; CI-TG 0,15 ; SN-TG 0,08 ; BJ-TG 0,03. **Les marchés nationaux sont très peu corrélés entre eux** : une gestion par pays apporte une vraie diversification, et le risque pays est surtout **idiosyncratique**.

**Valorisation et momentum par pays au 20/11/2026 (H)**

| Pays | PER médian | Rendement bénéficiaire médian | Rendement net médian des dividendes | Momentum 12-1 mois |
|---|---:|---:|---:|---:|
| CI | 14,86 | 6,73 % | 4,66 % | +44,2 % |
| SN | 12,65 | 7,91 % | 4,93 % | +77,9 % |
| BF | 13,44 | 7,44 % | 5,16 % | +141,9 % |
| BJ | 16,87 | 5,93 % | 4,21 % | +71,5 % |
| ML | 12,63 | 7,92 % | 5,98 % | +54,7 % |
| NE | (224,6 : non significatif) | — | 4,73 % | +110,4 % |
| TG | 5,50 (ETIT 2,98 : anomalie probable, ETIT publie en USD) | — | 2,00 % | +130,3 % |

---

## 10. Matières premières et sociétés cotées

### 10.1 Carte des expositions

| Matière première | Sociétés cotées (symbole) | Sens et canal | Conf. |
|---|---|---|---|
| **Caoutchouc naturel** (TSR20, SICOM Singapour) | SAPH (SPHC), SOGB (SOGC) | + prix de vente ; **−** coût d'achat du caoutchouc des planteurs villageois (concurrence « débridée » des usiniers) : la marge dépend de l'écart et non du prix seul | H (rapports SAPH et SOGB) |
| **Huile de palme brute et palmiste** | PALM CI (PALC), SOGB (activité palmier) | + prix ; − coût des régimes achetés aux planteurs ; ventes surtout locales | H (rapports 2026) |
| **Sucre** | SUCRIVOIRE (SCRC) | **prix plafonnés par l'État** (+7 % en moyenne en 2024) ; concurrence de sucre hors circuits officiels ; dépend de la pluie et de la main-d'œuvre de coupe | H (GCR 12/2025 ; rapport S1 2026) |
| **Cacao** | Pas de producteur coté. Exposition indirecte : AGL (SDSC, ports et logistique), FILTISAC (FTSC, sacs), NESTLE CI (NTLC, intrants cacao et café), banques ivoiriennes (crédit de campagne), consommation ivoirienne (revenus ruraux) | indirect | M |
| **Cajou, cola, maïs** | Pas de société cotée ; BMPA-CI gérée par la BRVM pendant la phase pilote de 24 mois | — | H |
| **Pétrole et produits pétroliers** | TotalEnergies Marketing CI (TTLC) et SN (TTLS), Vivo Energy CI (SHEC), SMB (SMBC, bitumes) | marges de distribution encadrées par des structures de prix d'État : sensibilité au **délai d'ajustement** des prix, plus qu'au prix du brut ; SMB plus directement liée au brut | M |
| **Gaz et électricité** | CIE (CIEC, électricité, CI), SODECI (SDCC, eau) | concessions à tarifs régulés ; parc thermique au gaz en CI | M |
| **Énergie (coût)** | Sonatel, ONATEL, Orange CI ; SUCRIVOIRE (gazole, réseau : coûts énergétiques +22 % au S1 2026) | − hausse du gazole et coupures d'électricité | H |
| **Or** | Pas de minière cotée. Exposition indirecte : économies du Mali et du Burkina (BOAM, BOABF, CBIBF, ONTBF ; Sonatel Mali) | recettes publiques et liquidité bancaire | M |
| **Coton** | Pas de société cotée ; UNIWAX (UNXC, textiles wax) en aval | indirect | M |
| **Minerai de fer et bauxite (Guinée)** | Sonatel (Orange Guinée, ≈ 26 % des clients) : « dynamique économique favorable portée par le projet Simandou (1re exportation prévue en janvier 2026) » ; mais dépréciation du franc guinéen | + activité ; − change | H (Sonatel) |
| **Tabac** | SITAB (STBC) | intrants importés ; fiscalité | M |

### 10.2 Prix et résultats récents (H sauf mention)

| Indicateur | Valeur | Date | Source |
|---|---|---|---|
| TSR20 SICOM, moyenne cumulée | **2,13 USD/kg** (1,83 EUR/kg), +20 % en USD et +16 % en EUR sur un an (1,78 USD/kg à fin septembre 2025) ; hausse qui « s'accentue sur la période récente » | 30/09/2026 | SAPH T3 2026 |
| SAPH, prix moyen de vente 2024 | 1,61 EUR/kg contre 1,27 EUR/kg en 2023 (+27 % d'effet prix) | 2024 | GCR, notation SAPH (10/2025) |
| SAPH, 9 mois 2026 | CA 232,5 Md (−8 %) ; volumes −9,5 % (congestion portuaire à San-Pedro) ; résultat net 9,7 Md (**−58 %**) ; prévision 2026 « nettement supérieure » au budget de 10,67 Md ; règlement européen anti-déforestation (EUDR) applicable au 30/12/2026 | 30/09/2026 | SAPH T3 2026 |
| SOGB, 9 mois 2026 | CA 67,3 Md (−11 %) ; caoutchouc : volumes −18 % ; palmier : CA +11 %, huile de palme +11 % en volume et −1 % en prix ; résultat net 7,6 Md (−34 %) | 30/09/2026 | SOGB T3 2026 |
| PALM CI, 9 mois 2026 | CA 174,9 Md (+4 %) ; résultat net 15,9 Md (−12 %, « hausse des coûts des approvisionnements ») ; au S1 2026 : CA −15 %, résultat net −41 % | 30/09/2026 | PALM CI T3 et S1 2026 |
| SUCRIVOIRE, campagne 2025/26 | 91 626 t de sucre (+16 %) ; 6,40 t/ha ; ventes du S1 2026 73 252 t (+0,9 %) ; prix moyen −1,2 % ; résultat net du S1 −4,79 Md (en amélioration) ; obligation convertible de 36 Md à 8,55 % (2025-2031) | 30/06/2026 | SUCRIVOIRE S1 2026 |
| Cacao, prix bord champ CI 2025/26 | 2 800 FCFA/kg (campagne principale) | 10/2025 | M (Conseil Café-Cacao) |
| Cacao (ICE/Londres), or (LBMA), Brent, coton, huile de palme (Bursa Malaysia), sucre (ICE n° 11) au 22/11/2026 | **introuvables dans cette session** | — | à charger par flux de données (§14) |

**Constat de marché (H)** : en 2026, l'indice « Consommation de base » ne fait que +17,8 % (« Consommation discrétionnaire » −7,3 %), contre +52,1 % pour les services financiers et +88,8 % pour les services publics. Les valeurs agro-industrielles ont baissé (PALC −8,15 %, SOGC −3,80 %, SPHC −3,23 %) malgré la remontée du TSR20, parce que **leurs marges sont prises en étau entre le prix mondial et le prix d'achat local de la matière première**. Un signal « prix mondial en hausse ⇒ achat » serait donc trompeur. Il faut modéliser la **marge** (prix mondial en FCFA − prix d'achat local estimé).

---

## 11. Répartition de la capitalisation par pays (H, calcul au 20/11/2026)

Méthode : cours du BOC au 20/11/2026 × nombre de titres (avis BRVM, doc 01 §11). Total recalculé : **19 331 Md**, contre 19 328,8 Md au BOC (écart 0,01 %).

### 11.1 Par pays du siège (référence de cotation)

| Pays | Capitalisation (Md FCFA) | Poids | Nombre de sociétés | Principales valeurs |
|---|---:|---:|---:|---|
| Côte d'Ivoire | 11 169 | **57,78 %** | 35 | ORAC 2 900, SGBC 1 207, SIBC 820, ECOC 814, SLBC 667 |
| Sénégal | 4 434 | **22,94 %** | 3 | SNTS 4 040, BOAS 277, TTLS 117 |
| Burkina Faso | 1 410 | 7,29 % | 3 | CBIBF 880, BOABF 339, ONTBF 191 |
| Togo | 1 206 | 6,24 % | 2 | ETIT 1 031, ORGT 175 |
| Bénin | 880 | 4,55 % | 3 | BICB 433, BOAB 369, LNBB 78 |
| Mali | 140 | 0,72 % | 1 | BOAM |
| Niger | 92 | 0,48 % | 1 | BOAN |
| Guinée-Bissau | 0 | 0 % | 0 | — |

### 11.2 Par exposition économique (H/M)

Sonatel (20,9 % du marché à elle seule) est répartie selon sa base de clients mobiles 2025 (H, états financiers 2025) : Sénégal 33,7 %, **Mali 28,9 %**, Guinée 25,9 %, Sierra Leone 7,5 %, Guinée-Bissau 4,0 %. La répartition du **chiffre d'affaires** par pays n'a pas été trouvée : l'ARPU sénégalais est probablement plus élevé, donc le poids réel du Sénégal est sans doute sous-estimé ici (M). ETIT (holding panafricaine, surtout hors UEMOA) est isolée.

| Exposition | Md FCFA | Poids |
|---|---:|---:|
| Côte d'Ivoire | 11 169 | 57,8 % |
| Sénégal | 1 757 | 9,1 % |
| Burkina Faso | 1 410 | 7,3 % |
| **Mali** | **1 306** | **6,8 %** |
| Guinée (hors UEMOA) | 1 047 | 5,4 % |
| Panafricain (ETIT) | 1 031 | 5,3 % |
| Bénin | 880 | 4,6 % |
| Sierra Leone (hors UEMOA) | 303 | 1,6 % |
| Togo | 175 | 0,9 % |
| Guinée-Bissau | 160 | 0,8 % |
| Niger | 92 | 0,5 % |

**Vérification (22/11/2026)** : le tableau des clients mobiles 2025 de Sonatel est confirmé, à l'unité près, dans les états financiers 2025 (p. 9). Sénégal 13 615 100, Mali 11 647 625, Guinée 10 450 947, Bissau 1 599 922, Sierra Leone 3 027 600 ; total 40 341 194. Mais la même publication (périmètre de consolidation) montre que Sonatel ne détient que **69,40 % d'Orange Mali**, 88,92 % d'Orange Guinée, 89,85 % d'Orange Bissau et **50 % d'Orange Sierra Leone** (consolidée en intégration globale). Pour l'actionnaire de Sonatel, la part attribuable des résultats de chaque filiale est plus pertinente. **Variante λ pondérée par la détention** (clients × taux de détention) : SN 0,401 ; ML 0,238 ; GN 0,274 ; GW 0,042 ; SL 0,045. L'exposition économique au Mali passe alors à **≈ 5,7 %** du marché (contre 6,8 %) et celle du Sénégal à ≈ 10,4 %. Les deux variantes restent des proxys (ni chiffre d'affaires ni résultat par pays) : confiance M.

**Conséquences** : (1) l'exposition réelle au risque malien est environ **8 à 9 fois** plus élevée que ne le suggère la cotation (6,8 % contre 0,7 %) ; (2) environ **12 %** du marché est exposé à des pays **hors zone FCFA** (Guinée, Sierra Leone, et une grande partie d'ETIT), donc à un vrai risque de change ; (3) les holdings régionales (ETIT, ORGT) et Orange CI (filiales hors CI possibles, **non vérifié**) devraient aussi être ventilées dès que leurs données par pays seront disponibles.

---

## 12. Prime de risque pays : méthode chiffrée

### 12.1 Principe

Pour un investisseur qui raisonne en FCFA, le taux sans risque local (5,75 %, ou la courbe ivoirienne) **contient déjà le risque souverain ivoirien**. Ce qui compte pour choisir entre pays de la BRVM, c'est la prime **relative à la Côte d'Ivoire**. Nous la décomposons en deux parties :

```
CRP_c = m × LS_c + PJ_c(relatif CI)
k_i   = rf_local + β_i × ERP_BRVM + Σ_c λ_ic × CRP_c
```

- `LS_c` : spread local par rapport à la courbe ivoirienne de même maturité, calculé automatiquement sur les nouvelles émissions du BOC (§6.2). **H.**
- `m` : rapport entre la volatilité des actions et celle des obligations, qui sert à passer d'un spread obligataire à une prime action. C'est la convention de Damodaran (méthode publiée sur son site, multiplicateur souvent proche de 1,5 historiquement). Nous retenons **m = 1,5** (hypothèse M, à calibrer). **[NON VÉRIFIÉ]** : la valeur actuelle du multiplicateur de Damodaran n'a pas pu être relue (pages.stern.nyu.edu ne se résout pas). Il la recalcule à chaque mise à jour, et elle a varié selon les années. Il faut la charger depuis sa page datée. Le marché obligataire régional est trop illiquide pour mesurer directement la volatilité des obligations.
- `PJ_c` : **surcote de saut politique** = p_sév × L_sév + p_mod × L_mod. Elle corrige la segmentation du §6.4 : les spreads locaux sous-estiment le risque de coup d'État et de sanctions.
  - L_sév = **21 %** (*corrigé par la vérification* ; le chercheur avait mis 25 %). C'est la moyenne des creux des deux chocs avec sanctions UEMOA : Niger 2023, −26,2 %, et Mali 2022, −16,9 % (H, §9). **Stress : 26 %.**
  - L_mod = **8 %** (calibré sur le retrait de l'AES, l'audit sénégalais et les coups d'État burkinabè de 2022 sans sanctions : −1,5 à −13 %, H).
  - `ERP_BRVM` est mesurée par l'écart E/P − r_f, qui ne contient pas de croissance. Avec une croissance nominale positive des bénéfices, cet écart **sous-estime** la prime implicite de Gordon (D/P × (1 + g) + g − r_f). D'où la plage de sensibilité de 3 à 6 %.
  - p_sév et p_mod : probabilités annuelles choisies **à dire d'expert** (hypothèses de modélisation, pas des faits). Elles reflètent la fréquence des coups d'État réussis dans la région depuis 2020 (Mali 2020 et 2021, Burkina 2022 deux fois, Niger 2023 : M).
- `λ_ic` : poids du pays c dans l'activité de la société i (§11.2). Par défaut, 1 pour le pays du siège.
- `ERP_BRVM` : prime de risque actions du marché. Par défaut **4,0 %**, soit environ la moyenne 2021-2025 de la prime publiée par le BOC (4,11 %, H). Sensibilité à tester : 3 % à 6 %.

### 12.2 Calibration par défaut (novembre 2026)

*Tableau recalculé par la vérification du 22/11/2026* : L_sév passe de 25 à 21 %, et les LS_c sont les valeurs calculées du §6.2 et non plus arrondies. L'ancienne valeur figure entre crochets.

| Pays | LS_c (H, calcul) | p_sév (hyp.) | p_mod (hyp.) | PJ absolu | PJ relatif CI | **CRP_c relatif CI** |
|---|---:|---:|---:|---:|---:|---:|
| Côte d'Ivoire | 0,00 | 2 % | 10 % | 1,22 % | 0,00 % | **0,0 %** |
| Bénin | 0,05 (2025) | 4 % | 15 % | 2,04 % | 0,82 % | **0,9 %** [1,0] |
| Togo | 0,92 | 4 % | 15 % | 2,04 % | 0,82 % | **2,2 %** [2,25] |
| Sénégal | 0,97 | 2 % | 30 % | 2,82 % | 1,60 % | **3,05 %** [3,1] |
| Mali | 0,57 | 10 % | 30 % | 4,50 % | 3,28 % | **4,1 %** [4,4] |
| Niger | 0,95 (2025) | 12 % | 30 % | 4,92 % | 3,70 % | **5,1 %** [5,45] |
| Burkina Faso | 1,07 | 12 % | 30 % | 4,92 % | 3,70 % | **5,3 %** [5,6] |
| Guinée-Bissau | n. d. (1,0 supposé) | 15 % | 30 % | 5,55 % | 4,33 % | ≈ 5,8 % [6,0] (si une société est cotée un jour) |
| Hors UEMOA (Guinée, Sierra Leone, ETIT) | — | — | — | — | — | **4,0 %** (hypothèse, risque de change compris) |

Les p_sév et p_mod restent des **hypothèses d'expert** non vérifiables. Repère empirique : 2 chocs « sévères » (sanctions UEMOA) en environ 21 pays-années pour les trois pays de l'AES entre 2020 et 2026, soit ≈ 10 % par pays et par an. C'est cohérent avec les 10 à 12 % retenus pour ML, NE et BF.

Exemple (Sonatel) : CRP = 0,337 × 3,05 + 0,289 × 4,1 + 0,259 × 4,0 + 0,075 × 4,0 + 0,040 × 5,8 ≈ **3,8 %** ; ≈ **3,7 %** avec la variante λ pondérée par la détention (§11.2). Avec β ≈ 1, le coût des fonds propres vaut 5,75 + 4,0 + 3,75 ≈ **13,5 %**. Le rendement net de dividende de Sonatel au 20/11/2026 est de 4,31 % (BOC, revérifié). Il faut donc une croissance du dividende d'environ 8,8 % par an pour justifier le cours. C'est un ordre de grandeur, pas une recommandation.

### 12.3 Variante « notation » (à activer quand les données seront disponibles)

`CRP_c = m × max(LS_c, α × DS_c)` + surcote, où `DS_c` est le *default spread* associé à la note souveraine (table publiée chaque année par A. Damodaran) **moins** celui de la Côte d'Ivoire, avec `α = 0,5` : la notation internationale n'est que partiellement pertinente pour un investisseur local. **Ne pas coder les spreads de notation en dur** : les charger depuis la mise à jour de Damodaran (URL dans les sources) et les notes depuis les communiqués des agences, avec leur date.

### 12.4 Sensibilité et limites

- La prime est dominée par la surcote politique pour les pays de l'AES : un p_sév de 5 % au lieu de 12 % abaisse la CRP du Burkina de 5,3 % à 3,8 % (avec L_sév = 21 % ; c'était 5,6 % → 3,85 % avec 25 %). **C'est le paramètre le plus incertain du modèle.** Il doit être revu chaque trimestre et testé en walk-forward (gain d'information mesuré, pas supposé).
- Les primes ne sont **pas additives avec un signal de valorisation** déjà calculé sur des multiples sectoriels régionaux (double comptage possible).
- BOA Mali a fait le meilleur parcours du marché (TCAC de 49,8 % depuis 2021) **malgré** le risque malien : une prime élevée n'implique pas une mauvaise performance. Elle signifie qu'il faut **exiger** davantage et **dimensionner** plus petit.

---

## 13. Surpondération et sous-pondération géographique : méthode chiffrée

### 13.1 Référence

Poids de référence `b_c` = poids par pays du siège (§11.1). Les plafonds et seuils d'alerte s'appliquent à l'**exposition économique** (§11.2).

### 13.2 Score pays (mensuel, sans biais d'anticipation)

```
S_c = 0,35·z(V_c) + 0,25·z(M_c) + 0,20·z(−ΔLS_c) + 0,20·z(P_c)
```

| Composante | Définition | Source | Délai de publication |
|---|---|---|---|
| `V_c` valorisation | rendement bénéficiaire médian des titres du pays (E/P de chaque titre plafonné à 12 %) − (rf_local + CRP_c) | BOC (PER) | J+0 (attention : PER calculé sur le dernier bénéfice publié) |
| `M_c` momentum pays | rendement total 12-1 mois de l'indice pays pondéré par la capitalisation | BOC | J+0 |
| `ΔLS_c` stress souverain | variation sur 12 mois du spread local (§6.2), plus 0,5 point par tranche de 1 % de décote médiane sur le secondaire sous 0,99 (§6.3) | BOC | à chaque nouvelle émission ou séance |
| `P_c` état politique | 0 normal ; −1 fenêtre électorale (J−30 à J+10), tensions signalées par une agence, ou sanctions passées encore actives ; −2 crise budgétaire ou de dette déclarée, programme FMI suspendu, ou crise sécuritaire ou énergétique déclarée ; −3 coup d'État, sanctions en cours, défaut ou annonce de sortie de l'UEMOA | calendrier et flux d'actualité (`data/news.py`), fiches de notation (brvm.org) | J+0 à J+1 |

`z(·)` : score z transversal sur les 7 pays, borné à ±2 (valeur manquante = 0). Pondérations initiales à **re-estimer** par l'IC (coefficient d'information) en walk-forward (doc 03). *Nuance de la vérification* : de Groot, Pang & Swinkels (2012, *Journal of Empirical Finance* 19(5)) étudient le momentum **au niveau des titres** dans 24 marchés frontières. Le doc 03 rapporte qu'une partie de ce momentum disparaît quand on neutralise l'effet pays, ce qui ne constitue qu'une indication **indirecte** de momentum pays. Le momentum d'**indices pays** frontières est **[NON VÉRIFIÉ]** dans cette session. Avec seulement 7 pays, dont 6 n'ont que 1 à 3 titres, le signal M_c est surtout du bruit idiosyncratique. Son poids de 0,25 doit être justifié par l'IC hors échantillon, sinon ramené à 0.

### 13.3 Des scores aux poids

```
w_c* = b_c × (1 + 0,5 × tanh(S_c))
bornes : |w_c − b_c| ≤ min( max(0,5·b_c ; 1 pt) ; 5 pts ),  w_c ≥ 0
bloc AES (BF+ML+NE) par pays du siège ≤ 1,25 × sa référence (1,25 × 8,5 % ≈ 10,6 % aujourd'hui)
bloc AES en exposition économique (λ, Sonatel Mali compris) ≤ 1,25 × sa référence (1,25 × 14,6 % ≈ 18 %)
puis renormalisation à 100 % par itérations de projection
```

**Exemple de calcul au 20/11/2026** (illustratif : les P_c sont nos lectures des fiches de notation H, à valider) :

| Pays | b_c | V_c | S_c | Poids cible | Écart |
|---|---:|---:|---:|---:|---:|
| CI | 57,78 | +0,98 | +0,22 | 62,30 | **+4,52** |
| TG | 6,24 | +4,23 | +0,76 | 8,18 | +1,94 |
| BJ | 4,55 | −0,87 | +0,17 | 4,89 | +0,34 |
| NE | 0,48 | n. d. | +0,28 | 0,54 | +0,06 |
| ML | 0,72 | −2,26 | −0,47 | 0,56 | −0,16 |
| BF | 7,29 | −3,91 | −0,49 | 5,58 | −1,71 |
| SN | 22,94 | −0,94 | −0,47 | 17,94 | **−5,00** |

Hypothèses de l'exemple : P = −2 pour SN, ML et BF ; −1 pour NE ; 0 pour les autres. Bloc AES par pays du siège : 6,7 % (limite de 10,6 % non atteinte). Remarque : le score du Togo dépend fortement du PER d'ETIT (2,98, valeur confirmée dans le BOC du 20/11/2026), à vérifier avant usage. *Vérification* : l'arithmétique de l'exemple est cohérente (poids qui somment à 99,99 %, bande de ±5 points saturée pour CI et SN). Mais l'exemple a été calculé avec l'**ancienne** calibration de la CRP (L_sév 25 %, LS arrondis). Les V_c changent de 0,05 à 0,35 point avec la nouvelle : l'exemple reste **illustratif** et doit être recalculé par le code.

### 13.4 Règles d'événements (prioritaires sur le score)

| Déclencheur | Action | Durée | Justification (H) |
|---|---|---|---|
| Sanctions financières UEMOA/BCEAO (gel), défaut souverain, annonce de sortie de l'UEMOA/BCEAO, ou coup d'État suivi de telles sanctions | poids du pays plafonné à **0,25 × b_c** ; aucun nouvel achat ; ventes à partir de l'ouverture **t+1** en ordres limités échelonnés (la limite de ±7,5 % empêche de tout vendre en un jour) | 60 séances, puis retour progressif sur 20 séances si le prix est stabilisé (volatilité sur 20 jours < 1,5 × la normale) | Niger 2023 : −26 % en 9 séances, avec 6 séances de délai ; **Mali 2022 : −7,47 % dès t+1, −16,9 % en 3 séances, sans délai** (vérification). Le backtest doit supposer que la 1re séance peut être au plafond de baisse, sans vendeur servi |
| Coup d'État **sans** sanctions UEMOA (ajout de la vérification) | P_c = −2 ; aucun nouvel achat ; poids ≤ b_c | 20 séances | Burkina 01/2022 et 09/2022 : −4 à −13 % ; Mali 08/2020 : −1,5 % |
| Levée de sanctions ou accord avec le FMI | P_c relevé de 2 crans ; achats autorisés jusqu'à b_c | 20 séances | Niger 02/2024 : +14,5 % anormal (+11,6 % brut) en 5 séances ; **Mali 07/2022 : +35,7 % brut en 5 séances** (vérification). Un retour progressif sur 20 séances rate une grande partie du rebond : à tester en walk-forward |
| Élection présidentielle | P_c = −1 de J−30 à J+10 ; aucune surpondération du pays | 40 séances | CI 2025, SN 2024 : pas de crise, mais risque extrême non nul |
| Dégradation souveraine de 2 crans ou plus, ou révélation budgétaire | ΔLS_c majoré de 0,5 point | 120 séances | Sénégal 09/2024 : −8,9 % en 60 séances |
| Décote médiane des obligations du pays < 0,97 sur 20 séances, **calculée sur au moins 5 transactions** (sinon, la règle est inactive) | P_c −1 | tant que la condition dure | Sénégal 2026 (64 à 84 transactions par trimestre) ; Niger 2026 (seulement 3 à 4 transactions par trimestre : non concluant) |

---

## 14. Implications pour la plate-forme (paramètres prêts à coder)

### 14.1 Fichier `config/macro_uemoa.yaml` (proposition)

```yaml
# Toutes les valeurs datées et sourcées ; conf: H/M/L. Ne jamais lire une valeur sans sa date.
as_of: "2026-11-22"
fx:
  eur_xof: {value: 655.957, conf: M, source: "parité légale BCEAO/zone franc"}
  eurusd_avg_2026_9m: {value: 1.164, range: [1.158, 1.170], conf: M, source: "SAPH T3 2026: 2,13 USD/kg = 1,83 EUR/kg (arrondis) ; vérif. 22/11: H->M"}
rates:
  brvm_reference_govt_rate:            # déduit chaque jour du BOC : 100/PER - prime
    method: "médiane glissante 20 séances ; jour isolé écarté si |écart| > 0,10 pt ; changement validé après 5 séances"   # vérif. 22/11 : primes erronées (0,00/0,01) les 19/10, 23/10 et 17/11/2026
    regimes:
      - {from: "2018-01-08", to: "2019-07-02", value: 0.0600, conf: H, note: "ajout vérif."}
      - {from: "2019-07-03", to: "2020-04-28", value: 0.0650, conf: H}
      - {from: "2021-02-22", to: "2023-12-29", value: 0.0590, conf: H}   # 02-04/01/2024 ≈ 5,98 % (transition)
      - {from: "2024-01-05", to: null,         value: 0.0575, conf: H}
  ci_curve_2026: {5y: 0.0545, 7y: 0.0570, 7y_bis: 0.0585, 10y: 0.0600, conf: H, source: "BOC: TPCI.O101-O104 (revérifié 22/11)"}
  bceao_policy:                        # [NON VÉRIFIÉ] À COMPLÉTER depuis bceao.int (bloqué pour le chercheur ET le vérificateur)
    - {effective: "2023-12-16", tms: 0.0350, gpm: 0.0550, conf: M, verified: false}
    - {effective: "2025-06-16", tms: 0.0325, gpm: 0.0525, conf: M, verified: false}
    - {effective: null, tms: null, gpm: null, conf: "TODO: décisions 09/2025 -> 11/2026"}
  reserve_ratio: {value: 0.03, conf: M, verified: false}
  inflation_target_band: [0.01, 0.03]   # [NON VÉRIFIÉ]
local_spread_vs_ci_pp:                 # recalculé automatiquement à chaque nouvelle émission APE ; vérif. 22/11 : valeurs calculées (et non arrondies)
  CI: 0.00
  BJ: 0.05      # 2025 (TPBJ 6,00 % 2025-2032 vs CI 5,95)
  ML: 0.57      # 2026
  TG: 0.92      # 2026
  NE: 0.95      # 2025
  SN: 0.97      # 2026
  BF: 1.07      # 2026
crp:
  equity_bond_vol_ratio_m: 1.5         # hypothèse (Damodaran), à calibrer ; valeur actuelle de Damodaran [NON VÉRIFIÉ]
  erp_brvm: 0.040                      # ≈ moyenne 2021-2025 de la prime BOC (4,107 %, revérifiée) ; E/P - rf : borne basse
  jump_loss: {severe: 0.21, severe_stress: 0.26, moderate: 0.08}   # vérif. 22/11 : 0,25 -> 0,21 (creux Niger 2023 -26,2 % et Mali 2022 -16,9 %)
  jump_prob:                           # HYPOTHÈSES à dire d'expert, revue trimestrielle
    CI: {severe: 0.02, moderate: 0.10}
    BJ: {severe: 0.04, moderate: 0.15}
    TG: {severe: 0.04, moderate: 0.15}
    SN: {severe: 0.02, moderate: 0.30}
    ML: {severe: 0.10, moderate: 0.30}
    NE: {severe: 0.12, moderate: 0.30}
    BF: {severe: 0.12, moderate: 0.30}
    GW: {severe: 0.15, moderate: 0.30}
  non_uemoa_crp: 0.040                 # GN, SL, panafricain (change compris), hypothèse
  rating_overlay: {enabled: false, alpha: 0.5, source: "Damodaran ctryprem (à charger)"}
exposure:                              # λ_ic ; défaut : 1.0 pour le pays du siège
  SNTS: {SN: 0.337, ML: 0.289, GN: 0.259, SL: 0.075, GW: 0.040}   # clients mobiles 2025 (H, revérifié), proxy du CA
  SNTS_ownership_adj: {SN: 0.401, ML: 0.238, GN: 0.274, SL: 0.045, GW: 0.042}   # ajout vérif. : clients × détention (ML 69,40 %, GN 88,92 %, GW 89,85 %, SL 50 %) ; recommandé pour la CRP actionnaire (M)
  ETIT: {PAN: 1.0}                     # ventilation par pays à chercher dans le rapport annuel ETI
  ORGT: {TG: 0.2, UEMOA_OTHER: 0.5, CEMAC_GN: 0.3}                # HYPOTHÈSE L, à remplacer
geo_tilt:
  benchmark: cap_weight_by_domicile
  score_weights: {valuation: 0.35, momentum_12_1: 0.25, sovereign_stress: 0.20, political: 0.20}
  zscore_clip: 2.0
  ep_cap_per_stock: 0.12
  tilt_strength: 0.5                   # w* = b*(1+0.5*tanh(S))
  max_active_pp: 5.0
  min_band_pp: 1.0
  rel_band: 0.5
  aes_bloc_cap_multiple: 1.25         # appliqué deux fois : poids par siège (≈10,6 %) et exposition λ (≈18 %)
  rebalance: monthly
event_rules:
  severe:   {trigger: "sanctions financières UEMOA/BCEAO, défaut, annonce de sortie UEMOA", weight_cap_x_bench: 0.25, freeze_buys: true, hold_sessions: 60, rampback_sessions: 20, execute: "t+1 open, limit orders, ladder over sessions", backtest_assume_first_session_limit_down: true}   # vérif. : Mali 2022 sans délai
  coup_no_sanctions: {political_step: -2, freeze_buys: true, max_weight_x_bench: 1.0, sessions: 20}   # ajout vérif. : BF 2022, ML 2020 (-1,5 à -13 %)
  relief:   {political_step: +2, max_weight_x_bench: 1.0, sessions: 20}   # Mali 07/2022 +35,7 % brut en 5 séances ; Niger 02/2024 +11,6 % brut
  election: {window: [-30, 10], max_weight_x_bench: 1.0}
  downgrade_2notches_or_fiscal_revelation: {spread_addon_pp: 0.5, sessions: 120}
  bond_discount_trigger: {median_price_ratio_lt: 0.97, lookback_sessions: 20, min_trades: 5, political_step: -1}   # vérif. : NE 2026 = 3-4 transactions par trimestre
valuation_regime:                      # information/risque, PAS un signal de timing (corrélation négative en échantillon, signe revérifié)
  boc_equity_risk_premium_bands: {expensive_lt: 1.0, neutral: [1.0, 4.0], cheap_gt: 4.0}
  stress_test_on_expensive: "chocs -15 % marché et -26 % pays AES appliqués au portefeuille"   # -26 % = creux Niger 2023
```

### 14.2 Fonctions à ajouter (contrats proposés)

| Module | Fonction | Rôle |
|---|---|---|
| `data/boc_parser.py` | `parse_sovereign_bonds(text) -> DataFrame` (symbole, pays, coupon, années, nominal, cours, volume) | alimente §6 ; le préfixe donne le pays : EOM=ML, EOS=SN, TPBF=BF, TPBJ=BJ, TPCI=CI, TPNE=NE, TPTG=TG |
| `data/boc_parser.py` | extraire `per_market`, `market_risk_premium`, `avg_div_yield` de l'en-tête | alimente §1.2 ; `ref_govt_rate = 100/per − prime` |
| `quant/macro.py` (nouveau) | `local_spread_curve(bonds, asof)`, `bond_price_stress(bonds, asof)`, `country_crp(cfg, spreads)`, `country_scores(...)` | §6, §12, §13 |
| `portfolio/construct.py` | contrainte `country_bounds(w_bench, scores, cfg)` + plafond du bloc AES sur l'exposition λ | §13.3 |
| `strategy/alpha.py` | coût des fonds propres `k_i` par titre ; signal « rendement attendu − k_i » | §12 |
| `data/news.py` | classification des événements pays (`severe`, `moderate`, `election`, `relief`) ; horodatage ; exécution au plus tôt en t+1 | §13.4 |
| `reference.py` | ajouter la matrice `EXPOSURE` (λ) et la carte matières premières par titre | §10, §11 |

### 14.3 Tests unitaires à écrire

1. `ref_govt_rate` vaut 5,75 % ± 0,01 sur le BOC du 20/11/2026 (PER 15,79 ; prime 0,58).
2. `parse_sovereign_bonds` trouve TPCI.O103 (5,45 %, 2026-2031) et EOS.O37 (6,95 %, 2026-2036) dans le BOC du 20/11/2026.
3. La somme des capitalisations par pays vaut 19 331 ± 5 Md au 20/11/2026.
4. `country_crp` renvoie 0 pour CI et augmente avec p_sév.
5. Les poids géographiques somment à 100 %, respectent les bandes, et le bloc AES respecte son plafond.
6. Règle « severe » : aucun achat sur le pays pendant 60 séances ; les ventes sont réparties sur plusieurs séances.
7. (Vérification) `ref_govt_rate` robuste vaut 5,75 % le 17/11/2026, alors que le calcul naïf donne 6,25 % (prime imprimée 0,01, PER 15,98). Il vaut 5,90 % le 29/12/2023 et 5,75 % le 08/01/2024.
8. (Vérification) `bond_price_stress` renvoie « inactif » pour le Niger au T4 2026 (3 transactions, moins que `min_trades` = 5) et 0,98 pour le Sénégal.
9. (Vérification) Sur les BOC, BOAM perd 7,47 % le 10/01/2022 et 7,37 % le 11/01/2022 ; BOAN perd 7,46 %, 7,47 % et 7,44 % les 03, 04 et 08/08/2023. Ces cas servent de tests de non-régression du simulateur d'exécution (plafond de baisse, vendeurs non servis).

### 14.4 Flux de données à brancher (ordre de priorité)

| Donnée | Source primaire | Fréquence | Délai | Statut |
|---|---|---|---|---|
| BOC (cours, PER, prime, obligations) | brvm.org | quotidienne | J+0 soir | **déjà disponible** |
| Fiches de notation des émetteurs | brvm.org, rubrique « notations financières » | événementielle | — | disponible (PDF) |
| Rapports trimestriels des émetteurs | brvm.org, « rapports sociétés cotées » | trimestrielle | 30 à 45 jours | disponible (PDF, parfois scannés : OCR à prévoir) |
| Décisions du CPM, inflation, réserves | bceao.int | trimestrielle / mensuelle | inflation ≈ 1-2 mois | **domaine à autoriser** |
| Adjudications UMOA-Titres (taux marginaux et moyens) | umoatitres.org | hebdomadaire | J+1 | **domaine à autoriser** |
| Croissance, dette, programmes | imf.org (WEO, rapports pays) | semestrielle | — | **domaine à autoriser** |
| Matières premières (cacao, caoutchouc, huile de palme, sucre, or, Brent) et EUR/USD | fournisseur de données (ICE, SICOM, LBMA, BCE) | quotidienne | J+0 | à acheter ou à trouver en source ouverte |

---

## 15. Questions ouvertes et informations introuvables dans cette session

1. **Taux directeurs de la BCEAO au 22/11/2026** et décisions depuis septembre 2025 : introuvables (bceao.int bloqué). Les sources H confirment l'assouplissement de 2025, mais ne permettent pas de savoir s'il s'est poursuivi en 2026.
2. **Inflation 2025-2026** par pays et pour l'Union : introuvable.
3. **Croissance 2025 réalisée et prévisions 2026** par pays : introuvables (WEO non accessible).
4. **Notes S&P/Moody's/Fitch au 22/11/2026** et **spreads des eurobonds** : introuvables. Les crans exacts du Sénégal en 2025-2026 sont incertains (L).
5. **État du programme FMI du Sénégal** en novembre 2026 : non vérifié.
6. **Résultats de la présidentielle béninoise d'avril 2026** et suites de la tentative de coup d'État de décembre 2025 : non vérifiés.
7. **Guinée-Bissau** après novembre 2025 : non vérifié (aucune société cotée, impact limité à 4 % des clients de Sonatel).
8. **Répartition du chiffre d'affaires de Sonatel, d'ETIT, d'Oragroup et d'Orange CI par pays** : introuvable. Seule la base de clients de Sonatel est disponible.
9. **PER d'ETIT (2,98)** : probable incohérence de devise (ETIT publie en USD). À vérifier avant d'utiliser la valorisation du Togo.
10. **Prix des matières premières** (cacao, or, Brent, coton, sucre, huile de palme) au 22/11/2026 : introuvables. Seul le TSR20 (SICOM) est disponible, via SAPH.
11. **Prime BOC comme signal** : à tester sur l'historique complet (2019 → 2026) une fois le téléchargement des BOC terminé. La définition semble différente en 2020.

---

## Sources

### Sources primaires consultées dans cette session (confiance H)

**Bulletins officiels de la cote (données locales `data/boc_text/`)**
- BOC du 20/11/2026 : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf
- Page des BOC : https://www.brvm.org/fr/bulletins-officiels-de-la-cote
- Séries calculées : 1 354 BOC du 11/01/2021 au 20/11/2026 (actions) ; 196 lignes souveraines (2020-2026) ; prime de risque et PER (2019-2026).

**Communiqués de la BRVM**
- https://www.brvm.org/fr/mediacentre/actualites/la-brvm-franchit-le-cap-des-20-000-milliards-de-fcfa (20/08/2026)
- https://www.brvm.org/fr/mediacentre/actualites/2025-la-consolidation-quinquennale-9915-de-progression-en-5-ans (bilan 2025)
- https://www.brvm.org/fr/mediacentre/actualites/bilan-2025-de-la-brvm-des-performances-consolidees-et-une-vision-strategique (20/01/2026)
- https://www.brvm.org/fr/mediacentre/actualites/la-brvm-accentue-son-dynamisme-en-ce-debut-dannee (30/01/2026)
- https://www.brvm.org/fr/mediacentre/actualites/la-capitalisation-boursiere-de-la-brvm-progresse-de-1000-milliards-fcfa-en-4 (15/10/2025)
- https://www.brvm.org/fr/mediacentre/actualites/la-capitalisation-boursiere-de-la-brvm-progresse-de-2000-milliards-fcfa-en-6 (20/06/2025)
- https://www.brvm.org/fr/mediacentre/actualites/des-nouveaux-emprunts-obligataires-de-letat-du-senegal-admis-la-cote-de-la (17/07/2025)
- https://www.brvm.org/fr/mediacentre/actualites/premiere-cotation-sur-la-bmpa-ci-un-demarrage-prometteur-pour-le-marche (28/05/2025)
- https://www.brvm.org/fr/mediacentre/actualites/salon-international-de-lagriculture-la-brvm-et-larre-presentent-la-bourse-des (24/02/2025)
- https://www.brvm.org/fr/autres-acteurs/agences-de-notation
- https://www.brvm.org/fr/emetteurs/type-annonces/notations-financieres

**Rapports d'activité des émetteurs (publiés sur brvm.org)**
- SAPH T3 2026 : https://www.brvm.org/sites/default/files/20261013_-_rapport_dactivites_-_3e_trimestre_2026_-_saph_ci.pdf
- SOGB T3 2026 : https://www.brvm.org/sites/default/files/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_sogb_ci.pdf
- PALM CI T3 2026 : https://www.brvm.org/sites/default/files/20261027_-_rapport_dactivites_-_3e_trimestre_2026_-_palm_ci.pdf
- PALM CI S1 2026 : https://www.brvm.org/sites/default/files/20261007_-_rapport_dactivites_-_1er_semestre_2026_-_palm_ci.pdf
- SUCRIVOIRE S1 2026 : https://www.brvm.org/sites/default/files/20261102_-_rapport_dactivites_-_1er_semestre_2026_-_sucrivoire_ci.pdf
- Sonatel T3 2026 : https://www.brvm.org/sites/default/files/20261029_-_rapport_dactivites_-_3e_trimestre_2026_-_sonatel_sn.pdf
- Sonatel, états financiers 2025 : https://www.brvm.org/sites/default/files/20260216_-_etats_financiers_2025_et_attestation_des_cac_-_sonatel_sn.pdf
- BOA Niger T3 2026 : https://www.brvm.org/sites/default/files/20261026_-_rapport_dactivites_-_3e_trimestre_2026_-_boa_ng.pdf
- BOA Mali S1 2026 : https://www.brvm.org/sites/default/files/20260923_-_rapport_dactivites_-_1er_semestre_2026_-_boa_mali.pdf
- ONATEL, rapport de gestion 2025 : https://www.brvm.org/sites/default/files/20260611_-_rapport_de_gestion_-_exercice_2025_-_onatel_bf.pdf

**Fiches de notation (Bloomfield, GCR) publiées sur brvm.org**
- BOA Mali (18/08/2026) : https://www.brvm.org/sites/default/files/20260818_-_notation_financiere_-_boa_ml.pdf
- BOA Niger (14/10/2026) : https://www.brvm.org/sites/default/files/20261014_-_notation_financiere_-_boa_ng.pdf
- Coris Bank International (26/08/2026) : https://www.brvm.org/sites/default/files/20260826_-_notation_financiere_-_coris_bank_international_bf.pdf
- BOA Sénégal (06/10/2026) : https://www.brvm.org/sites/default/files/20261006_-_notation_financiere_-_boa_sn.pdf
- Ecobank CI (22/10/2026) : https://www.brvm.org/sites/default/files/20261022_-_notation_financiere_-_ecobank_ci.pdf
- Sonatel, GCR (30/06/2026) : https://www.brvm.org/sites/default/files/20260630_-_notation_financiere_-_sonatel_sn.pdf
- FCTC Senelec 2025-2030, GCR (28/09/2026) : https://www.brvm.org/sites/default/files/20260929_-_notation_financiere_-_fctc_senelec_2025-2030.pdf
- PALM CI (26/08/2026) : https://www.brvm.org/sites/default/files/20260826_-_notation_financiere_-_palm_ci.pdf
- SAPH, GCR (16/10/2025) : https://www.brvm.org/sites/default/files/20251016_-_notation_financiere_-_saph_ci.pdf
- SUCRIVOIRE, GCR (30/12/2025) : https://www.brvm.org/sites/default/files/20251230_-_notation_financiere_-_sucrivoire_ci.pdf

**Documents internes du projet**
- `docs/research/01-structure-marche.md` (§11 : nombre de titres, flottant, pays) ; `docs/research/03-facteurs-marches-frontieres.md` (momentum pays, de Groot et al.).

### Sources à consulter pour les faits M/L (non joignables ou non consultées dans cette session)

- BCEAO, communiqués du Comité de politique monétaire, rapports sur la politique monétaire, statistiques d'inflation : https://www.bceao.int
- UMOA-Titres, résultats des adjudications : https://www.umoatitres.org
- FMI, Sénégal : https://www.imf.org/en/Countries/SEN ; Côte d'Ivoire : https://www.imf.org/en/Countries/CIV ; base WEO : https://www.imf.org/en/Publications/WEO
- Cour des comptes du Sénégal : https://www.courdescomptes.sn
- UEMOA (critères de convergence) : https://www.uemoa.int
- CEDEAO (AES, sanctions, ECO) : https://www.ecowas.int
- Banque de France, rapports annuels de la Zone franc : https://www.banque-france.fr
- A. Damodaran, primes de risque pays (mise à jour annuelle) : https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html
- Banque mondiale, prix des matières premières (« Pink Sheet ») : https://www.worldbank.org/en/research/commodity-markets
- ICCO (cacao) : https://www.icco.org

---

## Vérification adversariale (2026-11-22)

**Rôle** : vérificateur sceptique du domaine macro-géo. **Moyens** : 2 089 BOC locaux (`data/boc_text/`, 19/12/2017 → 20/11/2026), reparsés avec des scripts indépendants du parseur du projet ; PDF et pages de brvm.org lus avec curl, pdftotext et OCR (tesseract). **Limites** : le budget WebSearch de la session était épuisé dès le premier appel, et `www.bceao.int` et `pages.stern.nyu.edu` ne se résolvent pas (domaines à autoriser dans les paramètres réseau). Aucune source hors brvm.org n'a donc pu être consultée. Les faits non BRVM restent « unverifiable ».

| # | Élément vérifié | Valeur du chercheur | Résultat de la vérification | Verdict | Preuve |
|---|---|---|---|---|---|
| 1 | Capitalisations, sociétés et lignes au 20/11/2026 | 19 328,8 / 13 425,0 Md ; 48 ; 210 | 19 328 818 938 929 / 13 424 990 989 851 FCFA ; 48 ; 210 | **confirmé** | BOC 20/11/2026 |
| 2 | Définition de la prime BOC | 1/PER − taux de référence des emprunts d'État | Légende du BOC du 22/02/2021 : « (1 / le PER moyen du marché) − le taux de référence actuel des emprunts d'Etat » | **confirmé** | boc_20210222 |
| 3 | `rf_local` = taux de référence implicite | 5,75 % depuis le 05/01/2024 ; 5,90 % du 22/02/2021 au 02/01/2024 | 5,75 % depuis le 05/01/2024 (20/11/2026 : 100/15,79 − 0,58 = 5,753) ; 5,90 % jusqu'au **29/12/2023** ; ≈ 5,98 % du 02 au 04/01/2024 | **corrigé** (bornes) | BOC 2021-2026 |
| 4 | Régime d'avant 2021 | 6,50 % de 2019 à début 2020 | 6,00 % du 08/01/2018 au 02/07/2019, puis 6,50 % du 03/07/2019 au 28/04/2020 | **corrigé** | BOC 2018-2020 |
| 5 | Statistiques de la prime | moyenne 2021-2025 4,11 % ; médiane 3,91 ; p10 1,58 ; p90 6,76 ; < 1 % : 2,9 % des jours ; 2026 : 1,13 % ; min −0,33 % le 14/09/2026 | 4,107 ; 3,91 ; 1,58 ; 6,76 ; 2,93 % ; 1,135 ; −0,33 le 14/09/2026 (PER 18,43) | **confirmé**. Ajout : primes erronées imprimées les 19/10, 23/10 et 17/11/2026, d'où une règle de médiane robuste | BOC |
| 6 | `erp_brvm` = 4,0 % | moyenne de la prime BOC | moyenne recalculée à 4,107 %. Mais E/P − r_f est une borne basse de la prime implicite (pas de croissance) | **confirmé** (chiffre), réserve méthodologique ajoutée | BOC |
| 7 | Limite de variation quotidienne | ±7,5 % | Maximum de \|variation\| par an sur 2021-2026 : 7,50 %, hors opérations sur titres et pas minimal d'ETIT | **confirmé** | BOC 2021-2026 |
| 8 | Trajectoire de BOA Niger après le coup d'État | 5 900 le 26/07/2023 ; −1,78 % ; −7,46/−7,47/−7,44 % les 03, 04 et 08/08 ; plus bas 4 355 (−26 %) ; 4 915 (+12,9 %) | identique au FCFA près | **confirmé** | BOC 07-08/2023 |
| 9 | « La réaction commence ~6 séances après » (justification de la règle severe) | présenté comme enseignement général | vrai pour le Niger 2023. **Faux pour le Mali 2022** : sanctions annoncées le 09/01/2022, BOAM −7,47 % dès le 10/01 et −7,37 % le 11/01 | **réfuté** comme règle générale (supprimé des enseignements) | BOC 01/2022 |
| 10 | `jump_loss.severe` = 0,25 | calibré sur le seul Niger 2023 | Mali 2022 (sanctions UEMOA) : creux −16,9 % ; moyenne des deux cas ≈ −21,5 % | **corrigé** → 0,21 (stress 0,26) | BOC |
| 11 | `jump_loss.moderate` = 0,08 | AES 2024, audit Sénégal | Confirmé et élargi : coups d'État sans sanctions UEMOA, BF 01/2022 (−8,5 %), BF 09/2022 (−4 à −13 %), ML 08/2020 (−1,5 %) | **confirmé** | BOC |
| 12 | Règle de soulagement (+14,5 % en 5 séances, Niger 02/2024) | rendement non qualifié | +14,5 % est un rendement **anormal** ; brut +11,6 % (5 190 → 5 790). Cas oublié : levée des sanctions contre le Mali, 07/2022, **+35,7 % brut en 5 séances** | **corrigé** (précisé et complété) | BOC 02-03/2024, 07/2022 |
| 13 | Coupons 2026 de la CI (`ci_curve_2026`) | 5,45 / 5,70 / 5,85 / 6,00 % | TPCI.O103 5,45 % 2026-2031 et O104 5,70 % 2026-2033, cotées le 25/09/2026 ; O101 5,85 % 2026-2033 et O102 6,00 % 2026-2036, cotées le 11/06/2026 | **confirmé** | BOC |
| 14 | Coupons et dates de cotation des autres États | SN 22/09/2026, ML 27/08/2026, BF 03/09/2026, TG 23/04/2026, BJ 30/01/2026, NE 22/04 et 22/07/2025 | identiques (première apparition dans les BOC) ; Sénégal : tranches identiques cotées les 09 et 12/12/2025, le 10/06/2026 et le 22/09/2026 | **confirmé** | BOC |
| 15 | `local_spread_vs_ci_pp` (YAML) | BJ 0,10 ; ML 0,55 ; TG 0,90 ; NE 0,90 ; SN 1,00 ; BF 1,00 | valeurs calculées : 0,05 ; 0,57 ; 0,92 ; 0,95 ; 0,97 ; 1,07 (le YAML arrondissait jusqu'à 0,07 point) | **corrigé** | BOC |
| 16 | Prix secondaires des obligations sénégalaises | EOS.O27 à 9 400 ; EOS.O19 à 8 255,63 / 8 750 ; EOS.O24 référence 8 500 | identiques | **confirmé** | BOC 20/11/2026 |
| 17 | `bond_discount_trigger` (médianes SN 0,98, NE 0,95-0,975) | médianes trimestrielles | reproduites (SN 0,985 au T3 et 0,98 au T4 ; NE 0,95 et 0,975), mais le Niger repose sur **3 à 4 transactions par trimestre** | **corrigé** (ajout de `min_trades: 5`) | BOC 2025-2026 |
| 18 | Lien banques–souverain | 31,3 % (BOA Mali) ; 35,7 % (Coris) ; « les banques font 17 des 48 sociétés » | 185 699 / 593 455 = 31,3 % ; 1 070 425 / 2 997 779 = 35,7 %. Les 17 sont des **services financiers** : 14 banques, ETIT et ORGT (holdings), SAFCA (non bancaire) | **corrigé** (libellé) | fiches Bloomfield ; BOC |
| 19 | Citations des fiches de notation (allègement des taux, tensions au SN, sanctions au NE, BOAD et SONIMEX) | extraits | tous retrouvés mot pour mot | **confirmé** | PDF brvm.org |
| 20 | λ Sonatel (clients mobiles 2025) | SN 0,337 ; ML 0,289 ; GN 0,259 ; SL 0,075 ; GW 0,040 ; Mali −13,7 % ; taxes maliennes | clients identiques à l'unité près. **Omission** : Sonatel ne détient que 69,40 % d'Orange Mali et 50 % d'Orange SL. Variante pondérée par la détention : SN 0,401 ; ML 0,238 ; GN 0,274 ; GW 0,042 ; SL 0,045 | **confirmé** (chiffres), variante ajoutée | états financiers Sonatel 2025 |
| 21 | `eurusd_avg_2026_9m` = 1,164, conf H | 2,13 USD/kg = 1,83 EUR/kg | texte SAPH confirmé par OCR. Les arrondis donnent l'intervalle 1,158-1,170, pour une moyenne pondérée par les prix | **corrigé** (H → M, intervalle ajouté) | rapport SAPH T3 2026 |
| 22 | Agrégats BRVM (PIB implicite, 2025, 20/08/2026) | 24 781,32 Md = 18,37 % ; 4 204,7 Md levés ; 405 Md SN ; 20 036,18 Md (+50,30 %) ; services financiers 44,16 % ; top 5 49,16 % | tous retrouvés dans les communiqués. Nuance : le communiqué du 20/08/2026 compte 47 sociétés, contre 48 au 20/11 (BBGC cotée entre-temps) | **confirmé** | communiqués brvm.org |
| 23 | BMPA-CI (28/05/2025 ; cajou 440 FCFA/kg ; 1,05 Mt ; cola 250 kt ; pilote de 24 mois) | — | retrouvé | **confirmé** | brvm.org, 28/05/2025 et 24/02/2025 |
| 24 | Prime BOC et rendements futurs : corrélation négative | −0,34 / −0,33 (rendement total) | indice de prix, échantillon partiel : −0,39 / −0,65. Signe confirmé, magnitude non | **confirmé** (signe) | BOC |
| 25 | Taux directeurs BCEAO 2022-2025 (3,50/5,50 puis 3,25/5,25 au 16/06/2025) ; réserves obligatoires 3 % ; cible 1-3 % | M | concorde avec la connaissance du vérificateur ; **aucune URL primaire consultable**. Le sens « assouplissement 2025 » est confirmé par le communiqué BRVM du 20/06/2025 | **unverifiable** | bceao.int bloqué |
| 26 | Inflation UEMOA 2022-2024 ; croissance par pays | M/L | non vérifiable en source primaire. Ajout d'une source secondaire datée : FMI (déc. 2025) cité par Sonatel : SN 8,4 %, ML 4,9 %, GW 5,0 % de croissance ; inflation SN +2 %, ML +3 % | **unverifiable** (complété) | états financiers Sonatel 2025, p. 5 |
| 27 | Faits non BRVM : Cour des comptes SN (99,7 % ; 12,3 %), dates AES, élections CI/SN/BJ, coup d'État en GW, notes S&P/Moody's/Fitch, eurobonds, multiplicateur de Damodaran m = 1,5, momentum pays frontières (de Groot et al.) | M/L | aucune source consultable. de Groot et al. (2012) porte sur le momentum **des titres** et n'apporte qu'une indication indirecte de momentum pays | **unverifiable** (marqués [NON VÉRIFIÉ]) | — |

**Paramètres codés modifiés** : `jump_loss.severe` 0,25 → 0,21 (+ `severe_stress` 0,26) ; `local_spread_vs_ci_pp` (6 valeurs) ; `eurusd_avg_2026_9m.conf` H → M ; `brvm_reference_govt_rate` (bornes, régimes d'avant 2021, méthode robuste) ; `bond_discount_trigger.min_trades` = 5 ; nouvelles règles `coup_no_sanctions` et `relief` ; nouvelle exposition `SNTS_ownership_adj` ; stress AES −25 % → −26 %. Le tableau des CRP du §12.2 a été recalculé : CI 0 ; BJ 0,9 ; TG 2,2 ; SN 3,05 ; ML 4,1 ; NE 5,1 ; BF 5,3 ; GW ≈ 5,8 ; hors UEMOA 4,0 %.

**Rien n'a été supprimé** : aucune affirmation tirée des BOC ou de brvm.org n'a été réfutée sur le fond. Le seul élément réfuté, le délai de réaction de 6 séances présenté comme règle générale, a été reformulé.

**Ce qui reste à faire** pour lever les marques [NON VÉRIFIÉ] : autoriser `www.bceao.int`, `pages.stern.nyu.edu`, `www.imf.org` et `www.courdescomptes.sn` dans les paramètres réseau, ou relancer la recherche web avec un budget disponible.

**Sources de la vérification** (en plus de celles listées plus haut) :
- BOC locaux : https://www.brvm.org/fr/bulletins-officiels-de-la-cote (BOC du 22/02/2021 pour la légende ; 09-13/01/2022, 01-08/07/2022, 26/07-18/08/2023, 20/02-08/03/2024, 20/11/2026)
- https://www.brvm.org/sites/default/files/boc_20261120_2.pdf
- https://www.brvm.org/sites/default/files/20260216_-_etats_financiers_2025_et_attestation_des_cac_-_sonatel_sn.pdf (p. 5 : indicateurs FMI ; p. 9 : clients ; périmètre de consolidation)
- https://www.brvm.org/sites/default/files/20261013_-_rapport_dactivites_-_3e_trimestre_2026_-_saph_ci.pdf (lu par OCR)
- https://www.brvm.org/sites/default/files/20261026_-_rapport_dactivites_-_3e_trimestre_2026_-_boa_ng.pdf (lu par OCR : PNB +7,92 %)
- https://www.brvm.org/sites/default/files/20260818_-_notation_financiere_-_boa_ml.pdf
- https://www.brvm.org/sites/default/files/20260826_-_notation_financiere_-_coris_bank_international_bf.pdf
- https://www.brvm.org/sites/default/files/20261006_-_notation_financiere_-_boa_sn.pdf
- https://www.brvm.org/sites/default/files/20261014_-_notation_financiere_-_boa_ng.pdf
- https://www.brvm.org/sites/default/files/20261022_-_notation_financiere_-_ecobank_ci.pdf
- https://www.brvm.org/fr/mediacentre/actualites/la-capitalisation-boursiere-de-la-brvm-progresse-de-2000-milliards-fcfa-en-6
- https://www.brvm.org/fr/mediacentre/actualites/la-capitalisation-boursiere-de-la-brvm-progresse-de-1000-milliards-fcfa-en-4
- https://www.brvm.org/fr/mediacentre/actualites/des-nouveaux-emprunts-obligataires-de-letat-du-senegal-admis-la-cote-de-la
- https://www.brvm.org/fr/mediacentre/actualites/la-brvm-franchit-le-cap-des-20-000-milliards-de-fcfa
- https://www.brvm.org/fr/mediacentre/actualites/bilan-2025-de-la-brvm-des-performances-consolidees-et-une-vision-strategique
- https://www.brvm.org/fr/mediacentre/actualites/2025-la-consolidation-quinquennale-9915-de-progression-en-5-ans
- https://www.brvm.org/fr/mediacentre/actualites/premiere-cotation-sur-la-bmpa-ci-un-demarrage-prometteur-pour-le-marche
