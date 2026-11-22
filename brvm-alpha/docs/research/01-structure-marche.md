# 01 — Structure et microstructure de la BRVM (état au 22/11/2026)

> **Périmètre** : règles de marché, frais, fiscalité, opérations sur titres, introductions en bourse, indices et liste des actions cotées à la Bourse Régionale des Valeurs Mobilières (BRVM, Abidjan, 8 pays de l'UEMOA).
> **Date de rédaction** : 22/11/2026. **Données locales utilisées** : Bulletins Officiels de la Cote (BOC) du 02/01/2026 au 20/11/2026 (`data/boc_text/boc_AAAAMMJJ.txt.gz`, 220 séances lisibles).
> **Méthode** : les faits viennent en priorité de documents primaires (avis BRVM, instructions, BOC, décisions AMF-UMOA), téléchargés depuis `www.brvm.org`. Plusieurs points de méthodologie (pondération des indices, indice Total Return, arrondis des bornes de cours) ont été **vérifiés empiriquement** sur les BOC. Quand une information n'a pas été trouvée, c'est écrit.
> **Avertissement** : rien dans ce document ne permet de « garantir » un gain. Les règles décrites ici (frais, plafonds de variation, liquidité) sont précisément ce qui rend toute surperformance difficile et incertaine. Elles doivent être intégrées au backtest, sinon les résultats seront trop optimistes.

Légende de confiance : **H** (haute : document primaire ou vérification sur les données), **M** (moyenne : source secondaire concordante ou inférence solide), **B** (basse : source unique non primaire ou contradictoire).

---

## 0. Synthèse en 15 chiffres

| # | Fait | Valeur | Date | Conf. | Source |
|---|---|---|---|---|---|
| 1 | Sociétés cotées (actions) | **48** (12 Prestige + 36 Principal ; aucune au compartiment Croissance) | 20/11/2026 | H | BOC 20/11/2026 |
| 2 | Horaires (UTC = heure d'Abidjan) | pré-ouverture 9h00–9h45, continu 9h45–14h00, pré-clôture 14h00–14h30, fixing de clôture 14h30, négociation au dernier cours 14h30–15h00 (±60 s aléatoires) | page consultée le 22/11/2026 | H | brvm.org/horaires |
| 3 | Plafond de variation journalière | **±7,5 %** autour du cours de référence (actions et obligations) | règle de 2016, toujours appliquée en 2026 | H | Instruction I-A ; BOC 2026 : 0 clôture hors ±7,5 % sur 10 374 lignes |
| 4 | Pas de cotation | **5 FCFA** (actions cotant ≥ 100 FCFA) ; **1 FCFA sous 100 FCFA** (règle empirique : ETIT, et NEIC en 2017-2018 ; le texte I-E ne prévoit que 5 FCFA) | 2016 / 2017-2026 | H (texte) / H (observation, corrigé le 22/11) | Instruction I-E ; BOC 2017-2026 |
| 5 | Quotité | **1 titre** | 2016 | H | Instruction I-E, art. 1125 |
| 6 | Règlement-livraison | **J+2** depuis le **04/12/2025** (J+3 avant) | 02/12/2025 | H (texte) / M (date) | Instruction N°03-2025/BRVM/DG |
| 7 | Date ex-dividende | 1er jour ouvré **avant** la date de fermeture des registres depuis le passage à J+2 ; **2e jour ouvré avant** sous J+3 (jusqu'au 03/12/2025) | 2025 | H | même instruction, art. 2 ; BOC 2023-2026 (77/80 cas à 2 jours avant, 35/35 à 1 jour en 2026) |
| 8 | Commission BRVM + DC/BR | **0,20 % + 0,10 %** du montant, payées par l'acheteur **et** le vendeur | en vigueur | H | brvm.org « frais applicables » ; tarification 2014 |
| 9 | Courtage SGI | libre mais homologué ; grilles observées **0,4 %–1 %** (max 1 %) | 2024–2025 | H | décisions PAMF-UMOA (BICI Bourse, FGI) |
| 10 | IRVM Côte d'Ivoire (sociétés cotées) | **12 %** personnes physiques / **10 %** personnes morales | 2025–2026 | H | calendriers BRVM 2026 ; note DGI 2025 (via ENS) |
| 11 | BRVM Composite | toutes les actions, **pondération par capitalisation totale (non flottante)**, base 100 le 15/09/1998 | vérifié 2026 | H (empirique) | BOC ; test §10 |
| 12 | BRVM 30 | 30 valeurs les plus échangées, révision **trimestrielle**, pondération capitalisation totale **non plafonnée** | vérifié T4-2026 | H (empirique) | avis 289-2026 ; test §10 |
| 13 | BRVM Composite Total Return | base 100 le 02/01/2025, **dividendes nets réinvestis** | vérifié 2026 | H (empirique) | avis 308-2025 ; test §10 |
| 14 | Coût aller-retour réaliste (hors impact) | **≈1,7 % à 2,8 %** + demi-spread (médiane 0,69 % de spread à la clôture) | 2026 | M | calcul §5 |
| 15 | Ventes à découvert / marge | **interdites** | 2016 | H | Règles de négociation, art. 1123 |

---

## 1. Cadre institutionnel

| Acteur | Rôle | Note | Conf. |
|---|---|---|---|
| **BRVM** (Abidjan) | Bourse unique des 8 pays de l'UEMOA (Bénin, Burkina Faso, Côte d'Ivoire, Guinée-Bissau, Mali, Niger, Sénégal, Togo), avec des antennes nationales de bourse dans chaque pays | Elle publie chaque jour le BOC, qui fait foi | H |
| **DC/BR** (Dépositaire Central / Banque de Règlement) | Conservation centrale, règlement-livraison, paiement des dividendes | Passage à J+2 approuvé par son CA le 21/10/2025 | H/M |
| **AMF-UMOA** (ex-CREPMF) | Régulateur régional : agrément des SGI, homologation des tarifs, visas | Changement de nom prévu par le Traité révisé de l'UMOA du 12/07/2019, **entré en vigueur le 01/10/2022** (visas de la décision PAMF-UMOA 2024-326). La date du 01/01/2021 citée par la presse est corrigée | H |
| **SGI** (Sociétés de Gestion et d'Intermédiation) | Seuls intermédiaires habilités à transmettre des ordres ; teneurs de compte-conservateurs ; elles garantissent l'exécution des ordres de leurs clients | **36 SGI participantes** au 20/11/2026 (BOC). Une **SGI spécialiste** (animateur) est désignée par valeur. Un contrat d'animation est obligatoire en Prestige et Principal (RG 2021, art. 35 et 65) | H |

**Compartiments actions** (depuis le 02/01/2023, RG BRVM modifié par la décision CREPMF/2021/196) :

| Compartiment | Critères d'admission principaux (RG art. 62, 63, 63 bis) | Nb au 20/11/2026 |
|---|---|---|
| **Prestige** | capitalisation ≥ 50 Md FCFA ; 10 ans d'activité ; 3 exercices bénéficiaires sur 5 ; ≥ 20 % du capital diffusé (≥ 4 M titres, ≥ 200 actionnaires) ; engagement RSE | 12 |
| **Principal** | capitalisation ≥ 1 Md FCFA ; 3 exercices certifiés ; ≥ 15 % du capital diffusé (≥ 2 M titres, ≥ 100 actionnaires) | 36 |
| **Croissance** | PME : ≥ 500 000 titres et ≥ 10 % du capital diffusés ; Listing Sponsor obligatoire | 0 |

Flottant minimal de 15 % : l'avis 303-2026 (données au 31/12/2025) indique que 44 sociétés sur 48 le respectent. Les quatre exceptions sont **SICC 12,26 %, SEMC 10,29 %, CFAC 4,15 % et UNLC 0,22 %** (H).

---

## 2. Séance de cotation et mode de cotation

### 2.1 Horaires (page officielle, consultée le 22/11/2026, H)

| Phase | Horaire normal (UTC) | Veille de fête (sur avis) |
|---|---|---|
| Pré-ouverture (saisie des ordres, sans exécution) | 09:00 – 09:45 | 09:00 – 09:30 |
| Fixing d'ouverture | 09:45 | 09:30 |
| Négociation en continu | 09:45 – 14:00 | 09:30 – 11:00 |
| Pré-clôture | 14:00 – 14:30 | 11:00 – 11:30 |
| Fixing de clôture | 14:30 | 11:30 |
| Négociation au dernier cours | 14:30 – 15:00 | 11:30 – 12:00 |
| Fermeture et officialisation | 15:00 | 12:00 |

Chaque horaire comporte une composante aléatoire de **±60 s**. Abidjan est à UTC+0 toute l'année. En 2026, des horaires réduits ont été publiés par avis pour les 03/04, 30/04, 26/05, 06/08 et 14/08 (avis 080, 113, 140, 230 et 243-2026). L'ancien règlement de 2016 prévoyait 3 séances par semaine en fixing seul. Ce texte est obsolète sur ce point : depuis la décision CREPMF 2013-060, l'article 29 du RG prévoit une cotation « soit par fixing, soit en continu ».

**Jours de fermeture** : les jours ouvrés sont ceux du pays du site central (Côte d'Ivoire), et les fermetures sont annoncées par avis. *(Corrigé le 22/11/2026.)* Le BOC du 20/11/2026 porte le **n° 222** alors que 220 fichiers sont présents localement : **deux séances ont eu lieu mais leur BOC manque**. La numérotation le montre. Le 01/10 porte le n° 186 et le 05/10 le n° 188, donc le **02/10/2026 était une séance** (BOC n° 187, introuvable sous `boc_20261002.pdf` et `boc_20261002_2.pdf`, HTTP 404). Le 18/03 porte le n° 53 et le 23/03 le n° 55, donc l'un des jours **19/03 ou 20/03** a eu une séance (n° 54). Les jours ouvrés sans séance (numérotation continue) sont : 01/01, 16/03, l'un des jours 19-20/03, 06/04 (lundi de Pâques), 01/05, 14/05 (Ascension), 25/05 (Pentecôte), 27/05 (Tabaski), 07/08 (fête nationale CI) et 25/08 (Mawlid, avis 250-2026). **Règle pour le pipeline** : un BOC absent n'est pas un jour férié. Il faut contrôler la continuité des numéros de BOC.

### 2.2 Ordres et exécution (Règles de négociation 2016 ; RG 2021)

- **Marché au comptant**. L'acheteur doit les capitaux et le vendeur doit les titres dès la passation de l'ordre. La SGI peut exiger la provision avant de transmettre l'ordre. **Comptes sur marge et ventes à découvert interdits** (art. 1123). La plate-forme doit donc être **long-only, sans levier** (H).
- **Types d'ordres** : au mieux, à cours limité, « tout ou rien ». Validité : jour, durée déterminée, à révocation (art. 1222-1237) (H, texte 2016).
- **Fixing** (ouverture et clôture) : le cours retenu maximise le volume échangé. En cas d'égalité, il minimise le déséquilibre, puis l'écart au dernier cours (art. 1321) (H).
- **Unicité de cotation** : un seul carnet régional par valeur (H).
- **Cours officiel** : utiliser le BOC (colonnes « Clôt. » et « Cours de référence »). Le bandeau du site brvm.org affiche des prix différents (le 20/11/2026 : ORAC 19 495 sur le site contre 19 250 au BOC) (H, constat).
- **Transactions sur dossier** : il s'agit de transferts hors carnet, publiés par avis, parfois à des prix symboliques. Exemple : avis 296-2026, 92 actions NSBC à **5 FCFA** l'unité. Ces transactions **ne doivent jamais servir de prix** (H).
- **Acheté/Vendu** : il existe des seuils minimaux par opération, publiés chaque semestre. Pour le S2-2026 (avis 192-2026) : **500 M FCFA** pour presque toutes les actions, **100 M FCFA** pour SICC et UNLC (H).

### 2.3 Pas de cotation et quotité

| Instrument | Pas | Quotité | Conf. |
|---|---|---|---|
| Actions | **5 FCFA** (Instruction I-E) | 1 titre | H |
| Actions cotant **moins de 100 FCFA** | **1 FCFA** (règle empirique). Clôtures non multiples de 5 observées uniquement pour ETIT (13 à 78 FCFA, 2017-2026) et NEIC (37 à 94 FCFA, 2017-2018) | 1 | H (observation) / texte non trouvé |
| Obligations | 0,10 % du nominal | 1 | H |

*(Corrigé le 22/11/2026.)* Le seuil est observable sur l'historique. Sur les BOC 2017-2026 (≈ 96 000 lignes), **toutes** les clôtures comprises entre 100 et 999 FCFA sont des multiples de 5 : environ 11 000 lignes, dont NEIC (100-199 FCFA, 315 séances), STAC, SEMC, SIVC, SAFC, CABC et CFAC. Les clôtures non multiples de 5 n'apparaissent que sous 100 FCFA. L'affirmation précédente selon laquelle « aucune action ne cote entre 100 et 1 000 FCFA en 2026 » est fausse : SEMC a coté 750-990 FCFA du 02 au 08/01/2026. Règle à coder : `pas = 1 si cours < 100 FCFA, sinon 5`. Elle est **empirique**, car l'Instruction I-E de 2016 ne mentionne que 5 FCFA. Pour les cours compris entre 95 et 99 FCFA, la frontière exacte n'a pas été observée.

---

## 3. Limites de variation journalière (« écarts maximaux »)

### 3.1 Règle (H)

Instruction I-A (Règles de négociation, version 2016) : *« le cours coté d'un titre de capital ne peut s'écarter de plus de 7,5 %, à la hausse ou à la baisse, du cours de référence »*. La même borne s'applique aux titres de créance. Si le fixing produit un cours hors bornes, la cotation est **reportée** (c'est la « réservation »). La BRVM affiche alors un prix indicatif égal au seuil franchi. Les ordres restent saisissables et sont confrontés à la fin de la période de report.

**Cours de référence** = dernier cours coté (en pratique le cours de référence publié au BOC de la veille). Les jours d'opération sur titre, c'est le cours ajusté (voir §7 et §8).

### 3.2 Arrondi des bornes : vérifié sur 11 avis (H)

```
borne_basse = ceil (ref × 0,925 / pas) × pas
borne_haute = floor(ref × 1,075 / pas) × pas
```
Les bornes sont arrondies **vers l'intérieur** de la fourchette. Exemples tirés des avis officiels :

| Cas | Réf. | Bornes publiées | Calcul brut |
|---|---|---|---|
| SNTS split (avis 309-2026) | 4 385 | [4 060 ; 4 710] | [4 056,1 ; 4 713,9] |
| SLBC split (avis 242-2024) | 10 215 | [9 450 ; 10 980] | [9 448,9 ; 10 981,1] |
| BOAM attribution (avis 208-2024) | 1 345 | [1 245 ; 1 445] | [1 244,1 ; 1 445,9] |
| BOAC attribution (avis 267-2024) | 5 150 | [4 765 ; 5 535] | [4 763,8 ; 5 536,3] |
| SAFC DPS (avis 108-2026) | 3 890 | [3 600 ; 4 180] | [3 598,3 ; 4 181,8] |

Les avis BOABF, BOAS, BOAB, BOAN et SIBC de 2024 vérifient la même règle.

**Contre-vérification sur les BOC 2018-2026 (22/11/2026)**. Sur environ 87 000 lignes, il y a **1 638 clôtures** exactement à `floor(réf×1,075/pas)×pas` dans des cas où un arrondi au plus proche aurait donné un cours plus haut. Il y a de même **1 262 clôtures** à la borne basse `ceil` là où l'arrondi au plus proche aurait donné un cours plus bas. Les seuls dépassements de ces bornes sont de trois types :
1. des jours de détachement dans les BOC 2018-2022, où « Cours précédent » n'est pas ajusté du dividende (voir §7) ;
2. une erreur de mise en page (BOAC le 19/12/2024) ;
3. **ETIT 13 → 14 FCFA (+7,69 %)**, à 10 reprises en 2019-2021.

Ce dernier cas montre que la bande autorise **au minimum un pas** quand l'arrondi vers l'intérieur la réduirait à zéro (13×1,075 = 13,98, plancher 13). La règle de borne doit donc inclure `haute = max(haute, réf + pas)`. Par symétrie, on code aussi `basse = min(basse, réf − pas)`, ce qui n'a pas été observé. **H** pour l'arrondi, **M** pour le pas minimal.

### 3.3 Introductions en bourse (H)

Le premier jour suit la **« procédure ordinaire »** : cours de référence = prix de l'offre, et la même bande de ±7,5 % s'applique. Constats :

| Titre | Prix d'offre | 1er cours | Écart | Source |
|---|---|---|---|---|
| ORAC (30/12/2022) | 9 500 | 10 210 | +7,47 % (borne haute) | avis 256 et 261-2022 |
| LNBB (13/12/2024) | 4 800 | 5 160 | +7,50 % (borne haute) | avis 310 et 322-2024 |
| BICB (28/04/2025) | 5 250 | 5 600 | +6,67 % | avis 073 et 088-2025 |
| BBGC (24/09/2026) | 6 750 | 7 255 | +7,48 % (borne haute), puis 3 autres séances à la borne haute (25, 28 et 29/09) | avis 263 et 285-2026 ; BOC |

Conséquence : une demande excédentaire à l'introduction se résorbe **sur plusieurs séances bloquées à la hausse**, sans exécution pour la plupart des acheteurs.

### 3.4 Historique de la règle

Aucune modification du seuil de 7,5 % n'a été trouvée entre le texte de 2016 et les données de 2026 (recherche web, y compris sur la période Covid de 2020). Seuls les horaires ont été temporairement modifiés en mars 2020. **Un historique antérieur à 2016 n'a pas été trouvé** (B). Vérification du 22/11/2026 sur les BOC 2018-2026 : aucun écart à la référence ajustée supérieur à 7,5 %, hors le cas du pas minimal d'ETIT (§3.2). Le seuil est donc stable sur toute la période des données (H).

### 3.5 Statistiques 2026 sur les BOC (H, calcul local)

- Lignes action×séance (02/01–20/11/2026) : **10 374**. Clôtures hors ±7,5 % : **0**.
- Clôtures à la borne (|var| ≥ 7,4 %) : **315, soit 3,0 %** des lignes.
- Titres les plus souvent à la borne : UNLC (30 séances), SAFC (28), STAC (21), SICC (18), CABC (18), SCRC (12), SEMC (11), PRSC, SIVC et SDCC (10 chacun).
- Ce sont surtout des petites capitalisations peu liquides. Un backtest doit supposer **aucune exécution** côté acheteur à la borne haute, et côté vendeur à la borne basse.

---

## 4. Règlement-livraison

| Élément | Règle | Date | Conf. | Source |
|---|---|---|---|---|
| Cycle | **J+2 ouvrés** (J+3 auparavant, instruction 01-2007) | instruction signée le 02/12/2025, en vigueur à sa publication au BOC. La presse indique que les transactions passent à J+2 **dès le 04/12/2025** | H (texte) / M (date) | Instruction N°03-2025/BRVM/DG ; BOC du 03/12/2025 (cité par la presse) ; DC/BR |
| Ex-droit / ex-coupon / ex-dividende | 1er jour ouvré précédant la date de fermeture des registres. Si ce jour est férié : le 2e jour ouvré précédent | idem | H | Instruction 03-2025, art. 2 |
| Ex-date **avant** le 04/12/2025 (régime J+3) | **2e jour ouvré** précédant la date de fermeture des registres. Exemples : SNTS, registres le 22/05/2025 et ex le 20/05/2025 ; registres le 17/05/2024 et ex le 15/05/2024. Mesure sur les lignes (V) des BOC : 16/18 cas en 2023, 30/31 en 2024, 31/31 en 2025 à 2 jours ouvrés, contre 35/35 à 1 jour ouvré en 2026 | 2023-2025 | H (empirique) | BOC locaux, vérification du 22/11/2026 |
| Garantie | La SGI garantit l'exécution des obligations de son client, y compris en cas de défaillance de celui-ci | 2016 | H | art. 1123 |
| Transfert de propriété | par inscription en compte | 2016 | H | art. 1122 |
| Fonds de garantie | Fonds de garantie du marché et fonds de protection des épargnants (textes de 2016) | 2016 | H | brvm.org textes |

---

## 5. Barème complet des frais d'une transaction

### 5.1 Composantes

| Composante | Taux / montant | Payé par | Conf. | Source |
|---|---|---|---|---|
| Commission BRVM (« rétrocession de courtage ») | **0,20 %** du montant (actions, comptes clients) | acheteur **et** vendeur | H | brvm.org/fr/node/312 ; Tarification BRVM-DC/BR (MAJ 01/01/2014) |
| Commission DC/BR (règlement/livraison) | **0,10 %** | acheteur et vendeur | H | idem |
| Variante FCP / SICAV inscrites au DC/BR | 0,15 % BRVM + 0,05 % DC/BR | — | H | Tarification 2014 |
| Contrat de liquidité / spécialiste | exempté | — | H | Tarification 2014 |
| Droits (DPS/DA) | 0,15 % + 0,05 % | — | H | Tarification 2014 |
| **Courtage SGI**, transactions ordinaires | libre mais homologué. Exemples : BICI Bourse **0,4 %–1 %** (décision 326-2024) ; FGI **≤ 1 %** (décision 124-2025) | chaque client | H | décisions PAMF-UMOA |
| Courtage acheté/vendu | BICI Bourse 0,3 %–0,75 % | — | H | décision 326-2024 |
| Courtage transactions sur dossier | BICI Bourse 0,1 %–0,70 % ; FGI ≤ 0,8 % | — | H | idem |
| Droits de garde (conservation) | BICI Bourse **0,1 %–0,5 % par an** de la valeur conservée (prélèvement trimestriel) ; FGI ≤ 0,25 % par an | titulaire | H | idem |
| Tenue de compte | BICI Bourse **5 000 FCFA par an et PAR LIGNE de titres** (personne physique) et 10 000 FCFA par ligne (personne morale), base « forfait par ligne », prélèvement trimestriel ; FGI gratuit, mais « bourse en ligne » à 1 000 FCFA par trimestre. *(Corrigé le 22/11/2026 : il s'agit d'un forfait par ligne, pas par compte.)* | titulaire | H | annexes des décisions 326-2024 (04/12/2024) et 124-2025 (28/03/2025), lues par OCR |
| Ouverture / clôture de compte | gratuit (BICI Bourse) | — | H | idem |
| Transfert de titres | 5 000 FCFA (FGI) ; 10 000 à 34 375 FCFA (BICI Bourse) par ligne | — | H | idem |
| Redevance AMF-UMOA par transaction | **Non trouvée**. Elle n'apparaît ni sur la page officielle des frais, ni dans les grilles homologuées consultées | — | B | — |
| Taxe sur le courtage (TVA ou TAF selon le pays) | La page BRVM mentionne des « taxes » sur l'avis d'opéré, **sans taux**. Des sources secondaires évoquent la TAF en Côte d'Ivoire. **[NON VÉRIFIÉ]** : aucun taux dans la tarification BRVM-DC/BR 2014 ni dans les grilles BICI Bourse et FGI (vérification du 22/11/2026) | — | B | brvm.org node/312 ; guides tiers |

### 5.2 Exemple chiffré (achat de 1 000 000 FCFA, courtage 1 %)

| Poste | Montant |
|---|---|
| Courtage SGI 1 % | 10 000 |
| BRVM 0,20 % | 2 000 |
| DC/BR 0,10 % | 1 000 |
| Taxe sur courtage (hypothèse 10 %, non vérifiée) | 1 000 |
| **Total** | **≈ 14 000 FCFA, soit 1,4 %** |

Aller-retour : **≈ 2,8 %** au plafond, et **≈ 1,7 %** avec un courtage négocié à 0,5 %. Sans la taxe hypothétique, ces montants sont de 2,6 % et 1,6 %. À cela s'ajoutent le spread et l'impact de marché : le spread médian de fin de séance est de 0,69 % sur 48 titres en 2026, de 0,21 % (BOAM) à 4,3 % (UNLC). Ce spread est recalculé à l'identique le 22/11/2026, mais il n'est mesuré que les jours où le carnet a les deux côtés, ce qui le sous-estime pour les titres illiquides. Il faut aussi compter les droits de garde (jusqu'à 0,5 % par an) et, chez BICI Bourse, **5 000 FCFA par ligne et par an**. Pour 20 lignes, cela fait 100 000 FCFA par an, soit 1 % par an sur un portefeuille de 10 M FCFA : ce coût fixe pénalise les petits portefeuilles diversifiés.

---

## 6. Fiscalité

### 6.1 IRVM (retenue à la source sur dividendes des sociétés cotées)

Principe : la retenue est appliquée **au taux du pays du siège de l'émetteur**, à la source, par l'émetteur ou le teneur de compte. La BRVM indique que le régime est encadré par la **Directive 02/2010/CM/UEMOA**, une directive d'harmonisation. Les taux restent pourtant différents d'un pays à l'autre.

| Pays (code) | Taux observé sur les dividendes des sociétés cotées | Preuve | Date | Conf. |
|---|---|---|---|---|
| Côte d'Ivoire (CI) | **12 % personnes physiques / 10 % personnes morales** pour les paiements de **2025 et 2026**. Pour les paiements **jusqu'en 2024, 10 %** pour les personnes physiques | Calendrier des dividendes BRVM du 06/10/2026 : *« IRVM applicable de 12 % pour les personnes physiques et 10 % pour les personnes morales »* ; avis SGBC 231-2026. Montants nets du BOC = brut × 0,88 pour 12 émetteurs en 2026 (ORAC 800 → 704 ; NTLC 420 → 369,6 ; SLBC 2 127 → 1 871,76 ; STBC 1 940 → 1 707,2…). Historique déduit des nets du BOC, qui donnent un brut rond à 10 % en 2024 (NTLC 675 = 750×0,9 ; ECOC 594 = 660×0,9 ; STBC 675 = 750×0,9 ; SIBC 495 = 550×0,9 ; CIEC 171 = 190×0,9) et à 12 % dès mai-juin 2025 (ECOC 707,52 = 804×0,88 ; ORAC 660 = 750×0,88). Exception : **SGBC 2026, net publié 2 298,75** alors que 2 606 × 0,88 = 2 293,28. La BRVM a utilisé 2 298,75 pour la référence ex. **Toujours prendre le net du BOC** | 2024–2026 | H (2025-2026) / M (historique, par inférence) |
| Sénégal (SN) | **10 % pour 2026** | Avis 111-2026 : 1 740 FCFA net (SONATEL), cohérent avec un brut de 1 933 (résolution AG, non relue : sonatel.sn inaccessible dans cette session) ; BOAS 2026 : 450 = 500 × 0,90. **Historique [NON VÉRIFIÉ]** : plusieurs nets antérieurs correspondent à des bruts ronds à 12,5 % (SNTS 2021 : 1 225 = 1 400×0,875 ; SNTS 2022 : 1 400 = 1 600×0,875 ; BOAS 2025 : 350 = 400×0,875) | 2026 | H (2026) / B (avant 2026) |
| Burkina Faso (BF) | **12,5 % [NON VÉRIFIÉ en source primaire]** | Presse : AG BOA BF 2025, net 397,25 « après IRVM 12,5 % ». L'avis 072-2026 donne 397 FCFA net (arrondi). Nets cohérents avec 12,5 % : CBIBF 2021-2023 (406, 448, 525 = 464, 512, 600 × 0,875). Incohérent : **CBIBF 2026, 900 net = 1 000 × 0,90**. Le taux peut varier selon l'émetteur ou l'année | 03–04/2026 | M− |
| Mali (ML) | **7 % en 2025-2026** | BOAM : 305,04 = 328 × 0,93 (avis 129-2026) et 237,15 = 255 × 0,93 (2025). En 2024, 144 = 160 × 0,90, ce qui suggère 10 % avant 2025 **[NON VÉRIFIÉ]** | 2025–2026 | M+ |
| Niger (NE, « NG » à la BRVM) | **7 %** | Communiqué BOA NG déposé à la BRVM (29/04/2026) : dividende brut 2024 de 225 → net BOC 209,25 = 225 × 0,93. Nets BOAN 2021-2024 = 462, 610, 660, 655 × 0,93 (bruts ronds) | 2021–2025 | **H** (relevé le 22/11/2026) |
| Bénin (BJ, « BN » à la BRVM) | **Selon l'émetteur, PAS un taux unique de 5 %** *(corrigé le 22/11/2026)* : ≈ 5 % pour LNBB (2025 : 275,5 = 290 × 0,95 ; 2026 : 164,1709 pour 173 brut selon la presse) et BICB (254,6 = 268 × 0,95) ; **≈ 10 % pour BOAB** (585 = 650 × 0,90 en 2026 ; 468 = 520 × 0,90 en 2025) | Avis 121, 199 et 211-2026 (nets) ; bruts déduits | 2025–2026 | B (inférence). Utiliser le net du BOC |
| Togo (TG) | **Inconnu** : 7 % selon un agrégateur, ≈ 3 % selon un article de 2026. ORGT 2020 : 59,52 = 64 × 0,93 (cohérent avec 7 %, par inférence). ETI déclare en USD (0,16 cent net selon le chercheur), et le calendrier BRVM 2026 le convertit en 0,9184 FCFA net, ce qui est cohérent avec ≈ 575 FCFA par USD | — | 2026 | B |
| Guinée-Bissau (GW) | Sans objet : aucune action cotée | — | — | H |

Important pour le code : au BOC, la colonne « Dernier dividende payé — Montant net » correspond au **net d'IRVM pour les personnes physiques**. Les avis BRVM des émetteurs non ivoiriens ne donnent que le net. Les avis des émetteurs ivoiriens donnent le brut avec le taux d'IRVM.

### 6.2 Plus-values

**Aucune source primaire à jour trouvée** sur l'imposition des plus-values de cession d'actions cotées, pays par pays. Une source secondaire ancienne (mémoire universitaire citant l'*Année boursière* de la BRVM) indique une exonération pour les particuliers et une imposition à l'IS/BIC pour les sociétés. **Confiance basse : à faire valider par un fiscaliste**. Paramètre par défaut proposé : 0 % pour une personne physique résidente, avec un indicateur « non vérifié ».

---

## 7. Mécanique du détachement de dividende (vérifiée sur les BOC 2026, H)

1. **Calendrier** : l'avis BRVM fixe la date de fermeture des registres, qui est en pratique la date de paiement. Le titre cote **ex-dividende le jour ouvré précédent** (instruction 03-2025, art. 2). Exemples : SNTS, registres le 26/05/2026 (25/05 férié), ex-dividende le vendredi 22/05 ; SGBC, registres le lundi 24/08, ex-dividende le vendredi 21/08.
2. **Ordres** : *« tous les ordres de bourse en attente dans le système de négociation à cette date seront annulés »* (tous les avis de dividende 2026). En 2026, cette pratique prime sur l'ancien article 1224 (déduction automatique).
3. **Cours de référence ajusté** : il est publié dans le BOC du dernier jour avec droit, ligne marquée **(d)** :
   `réf_ex = arrondi_au_pas( clôture_avec_droit − dividende_net_personne_physique )`

   | Titre | Clôture avec droit | Dividende net | Réf. publiée | Calcul |
   |---|---|---|---|---|
   | SNTS (21/05/2026) | 28 900 | 1 740 | 27 160 | exact |
   | BOAB (21/05/2026) | 9 420 | 585 | 8 835 | exact |
   | ORAC (04/06/2026) | 16 975 | 704 | 16 275 | 16 271 arrondi vers le haut |
   | SLBC (28/07/2026) | 39 500 | 1 871,76 | 37 630 | 37 628,2 arrondi vers le haut |
   | ETIT (26/06/2026) | 37 | 0,9184 | 36 | arrondi au plus proche (pas de 1) |

   Pour un pas de 5, l'arrondi observé est **vers le haut**. La contre-vérification du 22/11/2026 porte sur **45 lignes (d) de 2025-2026** : 44 sont exactes ou arrondies vers le haut. La seule exception, BOAC le 04/05/2026, s'explique par le montant : la BRVM a utilisé le net du calendrier (594,528), alors que le BOC affiche ensuite 597,53. Avec 594,528, l'arrondi est bien vers le haut (8 845).
   **Attributions gratuites (2024)** : la référence théorique est au contraire arrondie **vers le bas**. BOAM 2 020 × 2/3 = 1 346,7 donne 1 345 ; BOAS 4 690 × 2/3 = 3 126,7 donne 3 125 ; BOAB 7 775/2 = 3 887,5 donne 3 885 ; BOAN 5 220 × 5/8 = 3 262,5 donne 3 260.
4. Le **jour ex** (ligne marquée **(V)**), la colonne « Cours précédent » du BOC contient **en général (2025-2026)** le **cours ajusté**, pas la clôture de la veille. La « Variation jour » est calculée par rapport à ce cours ajusté. Les bornes de ±7,5 % s'appliquent autour de ce cours ajusté. *(Nuance ajoutée le 22/11/2026.)* Ce n'est **pas toujours** le cas. SNTS le 15/05/2024 affiche 18 995 au lieu de 17 925, et SOGC le 10/07/2025 affiche 7 640 au lieu de 7 115. Dans les **BOC 2018-2022**, « Cours précédent » et « Variation jour » ne sont pas ajustés les jours de détachement (exemples : SCRC le 26/09/2018 à −8,72 % ; SLBC le 18/08/2022 à −10,27 % ; BOABF le 29/04/2019 à −13 %). La bande s'applique pourtant bien autour de la référence ajustée : SLBC 135 000 − 4 050 = 130 950, et la borne basse 121 130 a été atteinte. **Ne jamais utiliser « Variation jour » ni « Cours précédent » de la ligne (V) comme rendement.** Utiliser la référence de la ligne (d) ou la recalculer.
5. **La « Variation de l'année » du BOC n'est pas ajustée des dividendes** : elle compare le cours brut à la clôture de l'année précédente. Pour SNTS, 10,64 % puis 9,11 % le jour ex.
6. **Rendement total exact** : `TR_t = (Clôt_t + D_net·1[t = jour ex]) / Clôt_{t-1} − 1`, où `Clôt_{t-1}` est la clôture **non ajustée** de la veille.

---

## 8. Opérations sur titres (2020 → 11/2026)

Sources : liste des avis BRVM 2019-2026 parcourue (≈ 1 330 PDF indexés) et BOC 2026. La couverture de la liste des avis n'est pas exhaustive : environ 50–75 % des numéros sont présents selon l'année. Pour 2026, le contrôle de toutes les ruptures de cours de référence dans les BOC confirme la liste ci-dessous.

### 8.1 Fractionnements (splits)

| Titre | Ratio | Nominal | Dernier jour ancien / 1er jour nouveau | Réf. théorique et bornes | Source | Conf. |
|---|---|---|---|---|---|---|
| **SOLIBRA CI (SLBC)** | 10 pour 1 | 2 500 → 250 FCFA ; 1 646 084 → 16 460 840 actions | 27/09/2024 → **30/09/2024** | 10 215 [9 450 ; 10 980] | avis 242-2024 | H |
| **SONATEL SN (SNTS)** | 10 pour 1 | 500 → 50 FCFA (presse) ; 100 M → 1 Md d'actions | 23/10/2026 (clôture 43 850, ligne Val-T) → **26/10/2026** | 4 385 [4 060 ; 4 710]. Ordres en attente annulés. 1re séance : ouverture 4 710, clôture 4 700 | avis 304 et 309-2026 ; AGE du 08/10/2026 ; BOC | H |

Pas de fractionnement trouvé pour **SGBC** ni pour **ORANGE CI (ORAC)** sur 2020–2026. Un fractionnement SONATEL antérieur, en 2012, est cité par la presse mais n'a pas été vérifié (B).

### 8.2 Attributions gratuites (incorporation de réserves), 2024 (H : avis « valeur théorique du droit d'attribution »)

| Titre | Ratio (nouvelles : anciennes) | Jour ex | Réf. ex | Valeur du DA | Bornes |
|---|---|---|---|---|---|
| BOA Mali (BOAM) | 1 : 2 | 28/08/2024 | 1 345 | 675 | [1 245 ; 1 445] |
| BOA Burkina (BOABF) | 1 : 1 | 28/08/2024 | 3 400 | 3 400 | [3 145 ; 3 655] |
| BOA Sénégal (BOAS) | 1 : 2 | 29/08/2024 | 3 125 | 1 565 | [2 895 ; 3 355] |
| BOA Bénin (BOAB) | 1 : 1 | 03/09/2024 | 3 885 | 3 890 | [3 595 ; 4 175] |
| BOA Niger (BOAN) | 3 : 5 | 04/09/2024 | 3 260 | 1 960 | [3 020 ; 3 500] |
| BOA CI (BOAC) | 1 : 1 | 25/10/2024 | 5 150 | 5 150 | [4 765 ; 5 535] |
| SIB CI (SIBC) | 1 : 1 | 14/11/2024 | 3 550 | 3 550 | [3 285 ; 3 815] |

Facteur d'ajustement historique : `f = réf_ex / (réf_ex + valeur_DA)`. Par exemple f = 0,5 pour un ratio de 1 pour 1, et ≈ 0,666 pour BOAM.

### 8.3 Augmentations de capital, retraits de la cote, autres

| Événement | Détail | Date | Source | Conf. |
|---|---|---|---|---|
| SAFCA CI : augmentation de capital avec DPS | 6 nouvelles pour 13 anciennes ; ex-DPS le 24/04/2026 (réf. 3 890, DPS 1 615) ; DPS négocié du 27/04 au 09/06/2026 ; 3 750 000 actions nouvelles admises le **11/08/2026** (8 119 750 → 11 869 750 actions) | 2026 | avis 108 et 237-2026 | H |
| MOVIS CI (SVOC) : offre publique de retrait puis radiation | OPR ouverte le 07/04/2025 ; avis de radiation 142-2025 publié au BOC du 25/06/2025. Le titre figure encore au BOC du **26/06/2025** (suspendu, SP, 2 395 FCFA) et disparaît le **27/06/2025** | 2025 | avis 069 et 142-2025 ; BOC | H |
| BOA Mali : augmentation de capital avec DPS | valeur théorique du DPS (avis 191-2021) ; clôture le 10/11/2021 | 2021 | avis 191 et 211-2021 | H (titre de l'avis) |
| NSIA Banque CI : augmentation par apport partiel d'actifs | clôture des souscriptions le 05/01/2021 | 2020–2021 | avis 002-2021 | H (titre de l'avis) |
| Suspensions 2026 | SICC, SCRC et SEMC suspendus le 16/09/2026 (SCRC repris le 21/09). SICC et SEMC toujours suspendus le 20/11/2026. Motif non vérifié (un avis 214-2026 du 22/07/2026 porte sur le respect de la diffusion de l'information financière) | 2026 | avis 268, 269, 270 et 276-2026 ; BOC | H (fait) / B (motif) |
| Changement de nom | SEMC apparaît sous « EVIOSYS PACKAGING SIEM CI » dans les avis 341-2024 et 192-2026, mais « SONOCO METAL PACKAGING SIEM » au BOC. CFAC est nommée « CFAO MOBILITY CI » dans l'avis 303-2026 | — | avis | H |

---

## 9. Introductions en bourse 2022–2026 (actions)

| Date de 1re cotation | Société (symbole) | Pays | Opération | Prix | Titres offerts | 1er cours | Capi. au 1er jour | Compartiment | Source |
|---|---|---|---|---|---|---|---|---|---|
| 30/12/2022 | Orange Côte d'Ivoire (ORAC) | CI | OPV de 14 990 207 actions (05–07/12/2022) | 9 500 (7 600 pour le personnel) | 14,99 M | 10 210 | 1 538,19 Md | Premier compartiment, puis Prestige | avis 256 et 261-2022 |
| 13/12/2024 | Loterie Nationale du Bénin (LNBB) | BJ | OPV par l'État (07–25/10/2024) | 4 800 | 9 M | 5 160 | 103,20 Md | Principal | avis 310 et 322-2024 |
| 28/04/2025 | BIIC Bénin (BICB) | BJ | OPV par l'État (13/01–28/02/2025) | 5 250 | 19 133 345 | 5 600 | 323,45 Md | Principal | avis 073 et 088-2025 |
| 24/09/2026 | Bridge Bank Group CI (BBGC) | CI | OPV par Bridge Group West Africa (20–21/07/2026), 20 % du capital | 6 750 | 10 M | 7 255 | 362,75 Md | **Principal** (et non Prestige comme l'écrit une source de presse) | avis 263 et 285-2026 |

Aucune introduction d'actions n'a été trouvée en 2023. Bilan net 2022→2026 : +4 introductions, −1 radiation (MOVIS), pour 48 sociétés au 20/11/2026.

---

## 10. Méthodologie des indices

### 10.1 Calendrier des réformes (H)

| Date | Réforme | Source |
|---|---|---|
| 15/09/1998 | BRVM Composite (et ancien BRVM 10) en base 100 **[NON VÉRIFIÉ le 22/11/2026 : les BOC locaux 2017-2026 ne mentionnent pas cette base, et la source lefaso.net n'était pas accessible]**. Cela n'affecte que la normalisation du niveau | BOC historiques (« Base = 100 au 15 septembre 1998 ») |
| 02/01/2023 | Nouveaux compartiments Prestige, Principal et Croissance. Lancement des indices **BRVM Prestige** et **BRVM 30** en base 100 (le BRVM 30 remplace le BRVM 10). Niveaux du 1er jour : Prestige 100,54, BRVM 30 100,13, Composite 206,34. L'indice BRVM Principal apparaît au BOC avec la même base | communiqué BRVM du 02/01/2023 ; BOC |
| 02/01/2025 | **7 nouveaux indices sectoriels** (avis 341-2024 du 26/12/2024), en base 100 au 02/01/2025. **BRVM Composite Total Return** disponible sur la plate-forme de négociation | avis 341-2024 ; avis 308-2025 |
| 02/01/2026 | Les anciens indices sectoriels sont supprimés des supports après un an de transition (avis 307-2025). Le Total Return est affiché au BOC (avis 308-2025). Nouveau format du BOC | avis 307 et 308-2025 ; article BRVM sur le BOC |

> **Correction de la consigne** : la reclassification sectorielle n'a **pas** eu lieu en 2023. L'année 2023 correspond aux compartiments et aux indices Prestige et BRVM 30. La nouvelle nomenclature sectorielle à 7 secteurs date de l'avis 341-2024, effectif le 02/01/2025. Avant cette réforme, les secteurs étaient Finances, Transport, Agriculture, Distribution, Industrie, Services publics et Autres secteurs (BOC du 12/01/2023).

### 10.2 Règles de construction : textes et vérification empirique

La BRVM ne publie pas, sur son site, de document méthodologique détaillé (formule, diviseur, plafonnement) : **aucun n'a été trouvé**. Les règles ci-dessous ont donc été **reconstruites** à partir des BOC 2026, du nombre de titres de l'avis 303-2026 et des compositions officielles. L'écart mesuré est celui entre la variation quotidienne de l'indice publié et celle de l'indice reconstruit.

| Indice | Composition | Révision | Pondération reconstruite | Écart quotidien | Conf. |
|---|---|---|---|---|---|
| **BRVM Composite** | les 48 actions | à chaque nouvelle cotation ou radiation | **capitalisation totale** (cours × nombre total de titres, sans facteur de flottant ni plafond) | moyenne 1,07 pb (flottant : 19,4 pb ; équipondéré : 40,9 pb), 72 séances (janv.–avr. 2026) | **H** |
| **BRVM 30** | 30 valeurs « les plus échangées sur un trimestre » | **trimestrielle** (1er jour ouvré de janvier, avril, juillet et octobre) | **capitalisation totale, non plafonnée** | médiane 0,11 pb, moyenne 1,7 pb (oct.–nov. 2026). Le flottant donne 8,4 pb | **H** |
| **BRVM Prestige** | toutes les valeurs du compartiment Prestige (12) | **annuelle** (avis 001-2026) | capitalisation totale **plafonnée à environ 20 % par titre**, facteurs figés à la révision (hypothèse) | T1 : médiane 0,28 pb ; T2 : 0,95 pb ; T3 : 2,5 pb ; T4 : moins bon (4,8 pb avec un plafond de 25 %) | **M** (règle exacte non publiée) |
| **BRVM Principal** | les 36 valeurs du compartiment Principal | — | non testé | — | — |
| **BRVM Composite Total Return** | comme le Composite | « révisé à chaque paiement de dividende » | **dividendes NETS réinvestis** | le jour ex, l'écart TR − Composite vaut 150,2 / 62,2 / 36,1 / 16,6 pb, contre 148,2 / 62,6 / 35,7 / 16,6 pb prévus avec les dividendes nets, et 164,5 / 71,1 / 40,5 / 18,8 pb avec les bruts | **H** |
| **Indices sectoriels** (7) | selon la nomenclature 2025 | — | non testé (probablement la capitalisation totale, comme le Composite) | — | B |

**Contre-vérification indépendante (22/11/2026)** :
- **Composite** : sur 465 séances de 2025-2026, la variation quotidienne du Composite et celle de la capitalisation « Actions & Droits » publiée au BOC diffèrent en médiane de **0,09 pb** (moins de 1 pb dans 98 % des séances). Les seuls écarts notables tombent les jours d'introduction (28/04/2025, 24/09/2026), d'admission d'actions nouvelles (SAFC le 11/08/2026) et de négociation de DPS. Cela confirme la pondération par capitalisation totale.
- **Total Return** : l'excédent TR − Composite les jours ex vaut 150,2 / 62,2 / 36,1 / 16,6 pb. La prédiction avec les dividendes nets est de 148,2 / 62,5 / 35,7 / 16,6 pb, et celle avec les bruts de 168,4 / 71,0 / 40,6 / 18,8 pb. Cela confirme le réinvestissement des dividendes **nets**.

Au 20/11/2026, la capitalisation reconstruite (cours BOC × nombre de titres) vaut 19 330 Md FCFA, contre **19 328,8 Md FCFA publiés** (écart de 0,007 %). Le nombre de titres de l'avis 303-2026 est donc fiable, une fois mis à jour pour SNTS (×10) et SAFC (11 869 750).

### 10.3 Niveaux au 20/11/2026 (BOC n°222, H)

| Indice | Base | Niveau | Var. jour | Var. depuis le 31/12/2025 | PER moyen |
|---|---|---|---|---|---|
| BRVM Composite | 100 au 15/09/1998 | 492,89 | −0,21 % | +42,56 % | 15,79 (hors UNLC) |
| BRVM 30 | 100 au 02/01/2023 | 238,73 | −0,29 % | +43,61 % | — |
| BRVM Prestige (12) | 100 au 02/01/2023 | 186,61 | −0,03 % | +29,37 % | 13,21 |
| BRVM Principal (36) | 100 au 02/01/2023 | 337,96 | −0,35 % | +55,28 % | 19,73 |
| Composite Total Return (48) | 100 au 02/01/2025 | 198,63 | −0,22 % | **+49,19 %** | — |
| Télécommunications (3) | 100 au 02/01/2025 | 137,33 | −0,17 % | +44,71 % | 12,91 |
| Services financiers (17) | idem | 221,79 | −0,90 % | +52,06 % | 14,51 |
| Consommation de base (9) | idem | 254,63 | +1,20 % | +17,84 % | 12,51 |
| Consommation discrétionnaire (7) | idem | 160,36 | +0,95 % | −7,32 % | 36,40 |
| Industriels (6) | idem | 198,70 | +2,19 % | +50,15 % | 131,01 |
| Énergie (4) | idem | 158,29 | +0,16 % | +42,72 % | 17,21 |
| Services publics (2) | idem | 199,96 | +2,78 % | +88,82 % | 18,34 |

En 2026, l'écart entre le Total Return et le Composite atteint **+6,6 points**, soit la contribution des dividendes nets. **Le benchmark honnête est donc le Total Return**. Battre l'indice prix (Composite) ne prouve rien.

Anomalie à connaître : la page brvm.org/fr/indices affiche une colonne « Variation 31 décembre (%) » de +1,70 % pour le Composite, incompatible avec le BOC. **Utiliser le BOC**.

### 10.4 Compositions officielles en vigueur

- **BRVM 30, T4-2026** (avis 289-2026 du 01/10/2026) : SDSC, BOABF, BOAB, BOAC, BOAM, BOAN, BOAS, BICB, CFAC, CIEC, CBIBF, ECOC, ETIT, SIVC, LNBB, NSBC, ONTBF, ORGT, ORAC, SAFC, SPHC, STBC, SGBC, SIBC, SOGC, SLBC, SNTS, TTLC, UNXC, SHEC.
  - Sorties : NEIC, SCRC, SEMC, STAC. Entrées : LNBB, ONTBF, SHEC, SLBC.
  - Révisions 2026 : avis 002 (02/01), 081 (01/04), 191 (01/07) et 289 (01/10).
- **BRVM Prestige 2026** (avis 001-2026 du 02/01/2026) : ECOC, NTLC, ONTBF, ORAC, PALC, SGBC, SIBC, SMBC, SNTS, SPHC, TTLC, TTLS.
  - Sortie : NSBC. Entrées : SPHC, SIBC, SMBC.

---

## 11. Liste complète des actions cotées au 20/11/2026

Sources : BOC du 20/11/2026 (symbole, libellé, secteur, compartiment, cours) ; avis 303-2026 (nombre de titres et flottant au 31/12/2025 ; SNTS ajusté ×10 après le split, SAFC à 11 869 750 titres après l'augmentation de capital) ; avis 289-2026 (BRVM 30). Les deux dernières colonnes sont calculées sur les BOC 2026 (220 séances) : valeur médiane échangée par séance, et spread médian de la meilleure limite à la clôture. Les codes pays suivent la norme ISO, alors que la BRVM utilise « BN » pour le Bénin et « NG » pour le Niger. ETIT est classé TG (holding incorporée au Togo).

| Symbole | Société (libellé BOC) | Pays | Secteur BRVM (2025) | Compartiment | BRVM 30 (T4-2026) | Cours 20/11/2026 (FCFA) | Nb titres | Flottant % (31/12/2025) | Capi. (Md FCFA) | Valeur médiane/séance 2026 (M FCFA) | Spread médian clôture 2026 (%) |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| NTLC | NESTLE CI | CI | Consommation de base | Prestige | non | 12 800 | 22 070 400 | 20,0 | 283 | 9,9 | 0,80 |
| PALC | PALM CI | CI | Consommation de base | Prestige | non | 7 440 | 15 459 316 | 32,9 | 115 | 20,8 | 0,67 |
| SPHC | SAPH CI | CI | Consommation de base | Prestige | oui | 7 645 | 25 558 005 | 59,5 | 195 | 17,7 | 0,66 |
| SMBC | SMB CI | CI | Énergie | Prestige | non | 17 995 | 7 794 850 | 51,8 | 140 | 11,6 | 0,67 |
| TTLC | TOTALENERGIES MARKETING CI | CI | Énergie | Prestige | oui | 2 990 | 62 961 600 | 27,0 | 188 | 11,8 | 1,03 |
| TTLS | TOTALENERGIES MARKETING SN | SN | Énergie | Prestige | non | 3 580 | 32 577 700 | 30,9 | 117 | 6,6 | 1,23 |
| ECOC | ECOBANK COTE D'IVOIRE | CI | Services financiers | Prestige | oui | 14 795 | 55 050 600 | 23,8 | 814 | 28,3 | 0,60 |
| SGBC | SOCIETE GENERALE COTE D'IVOIRE | CI | Services financiers | Prestige | oui | 38 795 | 31 111 110 | 43,4 | 1 207 | 105,5 | 0,28 |
| SIBC | SOCIETE IVOIRIENNE DE BANQUE | CI | Services financiers | Prestige | oui | 8 200 | 100 000 000 | 20,0 | 820 | 62,2 | 0,57 |
| ONTBF | ONATEL BF | BF | Télécommunications | Prestige | oui | 2 805 | 68 000 000 | 23,0 | 191 | 8,6 | 1,02 |
| ORAC | ORANGE COTE D'IVOIRE | CI | Télécommunications | Prestige | oui | 19 250 | 150 655 350 | 20,2 | 2 900 | 27,4 | 0,67 |
| SNTS | SONATEL SN | SN | Télécommunications | Prestige | oui | 4 040 | 1 000 000 000 | 23,9 | 4 040 | 179,2 | 0,26 |
| SCRC | SUCRIVOIRE | CI | Consommation de base | Principal | non | 1 230 | 19 600 000 | 23,0 | 24 | 19,9 | 0,68 |
| SICC | SICOR CI | CI | Consommation de base | Principal | non | 8 400 (suspendu) | 600 000 | 12,3 | 5 | 0,3 | 4,22 |
| SLBC | SOLIBRA CI | CI | Consommation de base | Principal | oui | 40 500 | 16 460 840 | 18,6 | 667 | 12,5 | 1,05 |
| SOGC | SOGB CI | CI | Consommation de base | Principal | oui | 7 600 | 21 601 840 | 26,8 | 164 | 17,6 | 0,63 |
| STBC | SITAB CI | CI | Consommation de base | Principal | oui | 21 325 | 17 955 000 | 26,4 | 383 | 47,6 | 0,41 |
| UNLC | UNILEVER CI | CI | Consommation de base | Principal | non | 44 000 | 9 183 400 | 0,2 | 404 | 1,0 | 4,26 |
| ABJC | SERVAIR ABIDJAN CI | CI | Consommation discrétionnaire | Principal | non | 3 000 | 10 912 000 | 20,0 | 33 | 7,6 | 0,82 |
| BNBC | BERNABE CI | CI | Consommation discrétionnaire | Principal | non | 1 750 | 6 624 000 | 34,9 | 12 | 2,7 | 1,24 |
| CFAC | CFAO MOTORS CI | CI | Consommation discrétionnaire | Principal | oui | 1 190 | 181 371 900 | 4,2 | 216 | 4,6 | 0,83 |
| LNBB | LOTERIE NATIONALE DU BENIN | BJ | Consommation discrétionnaire | Principal | oui | 3 900 | 20 000 000 | 45,0 | 78 | 7,9 | 1,24 |
| NEIC | NEI-CEDA CI | CI | Consommation discrétionnaire | Principal | non | 1 900 | 12 765 825 | 20,0 | 24 | 4,9 | 1,16 |
| PRSC | TRACTAFRIC MOTORS CI | CI | Consommation discrétionnaire | Principal | non | 3 720 | 10 240 000 | 100,0 (déclaré) | 38 | 3,3 | 1,22 |
| UNXC | UNIWAX CI | CI | Consommation discrétionnaire | Principal | oui | 1 705 | 20 750 000 | 27,7 | 35 | 17,5 | 0,38 |
| SHEC | VIVO ENERGY CI | CI | Énergie | Principal | oui | 1 850 | 63 000 000 | 28,3 | 117 | 8,2 | 0,70 |
| BBGC | BRIDGE BANK GROUP CI | CI | Services financiers | Principal | non | 8 145 | 50 000 000 | 20,0 | 407 | 81,5 (40 séances) | 0,52 |
| BICB | BIIC BN | BJ | Services financiers | Principal | oui | 7 500 | 57 759 800 | 33,1 | 433 | 23,7 | 0,48 |
| BICC | BICI CI | CI | Services financiers | Principal | non | 31 000 | 16 666 670 | 32,5 | 517 | 13,6 | 0,69 |
| BOAB | BANK OF AFRICA BN | BJ | Services financiers | Principal | oui | 9 095 | 40 561 048 | 45,9 | 369 | 31,0 | 0,48 |
| BOABF | BANK OF AFRICA BF | BF | Services financiers | Principal | oui | 7 700 | 44 000 000 | 43,5 | 339 | 23,7 | 0,46 |
| BOAC | BANK OF AFRICA CI | CI | Services financiers | Principal | oui | 10 995 | 40 000 000 | 30,3 | 440 | 82,1 | 0,33 |
| BOAM | BANK OF AFRICA ML | ML | Services financiers | Principal | oui | 5 100 | 27 450 000 | 35,8 | 140 | 24,6 | 0,21 |
| BOAN | BANK OF AFRICA NG | NE | Services financiers | Principal | oui | 4 420 | 20 800 000 | 40,9 | 92 | 25,2 | 0,62 |
| BOAS | BANK OF AFRICA SENEGAL | SN | Services financiers | Principal | oui | 7 700 | 36 000 000 | 38,3 | 277 | 46,1 | 0,27 |
| CBIBF | CORIS BANK INTERNATIONAL | BF | Services financiers | Principal | oui | 27 505 | 32 000 000 | 30,4 | 880 | 21,2 | 0,77 |
| ETIT | ECOBANK TRANS. INCORP. TG | TG | Services financiers | Principal | oui | 57 | 18 084 106 722 | 33,5 | 1 031 | 45,8 | 2,99 |
| NSBC | NSIA BANQUE COTE D'IVOIRE | CI | Services financiers | Principal | oui | 15 000 | 24 734 572 | 20,0 | 371 | 30,2 | 0,37 |
| ORGT | ORAGROUP TOGO | TG | Services financiers | Principal | oui | 2 500 | 69 986 131 | 19,8 | 175 | 11,6 | 0,52 |
| SAFC | SAFCA CI | CI | Services financiers | Principal | oui | 3 030 | 11 869 750 | 29,2 | 36 | 18,5 | 0,79 |
| CABC | SICABLE CI | CI | Industriels | Principal | non | 2 720 | 5 920 000 | 48,7 | 16 | 4,8 | 1,14 |
| FTSC | FILTISAC CI | CI | Industriels | Principal | non | 1 600 | 14 103 740 | 33,7 | 23 | 6,5 | 0,50 |
| SDSC | AFRICA GLOBAL LOGISTICS CI | CI | Industriels | Principal | oui | 2 685 | 54 435 300 | 25,0 | 146 | 25,9 | 0,79 |
| SEMC | SONOCO METAL PACKAGING SIEM S. | CI | Industriels | Principal | non | 1 495 (suspendu) | 25 189 600 | 10,3 | 38 | 8,8 | 0,76 |
| SIVC | ERIUM CI (Ex AIR LIQUIDE CI) | CI | Industriels | Principal | oui | 1 600 | 8 734 000 | 27,9 | 14 | 9,8 | 0,87 |
| STAC | SETAO CI | CI | Industriels | Principal | non | 2 180 | 13 440 000 | 20,8 | 29 | 9,3 | 1,27 |
| CIEC | CIE CI | CI | Services publics | Principal | oui | 4 400 | 56 000 000 | 45,9 | 246 | 23,5 | 0,64 |
| SDCC | SODE CI | CI | Services publics | Principal | non | 11 300 | 9 000 000 | 49,5 | 102 | 8,1 | 0,83 |

Piège de parsing repéré pendant cette étude : les libellés « TOTALENERGIES… » contiennent la chaîne « TOTAL ». Un filtre naïf des lignes « TOTAL » du BOC les supprime donc. Il faut filtrer sur le **symbole** (`== "TOTAL"`), pas sur une sous-chaîne.

Répartition :
- **Pays** : CI 35, SN 3, BF 3, BJ 3, TG 2, ML 1, NE 1, GW 0.
- **Secteurs** : Services financiers 17, Consommation de base 9, Consommation discrétionnaire 7, Industriels 6, Énergie 4, Télécommunications 3, Services publics 2.

---

## 12. Implications pour la plate-forme (paramètres prêts à coder)

### 12.1 Configuration (YAML)

```yaml
market:
  timezone: "Africa/Abidjan"          # UTC+0, sans heure d'été
  sessions:
    normal:   {preopen: "09:00", open_auction: "09:45", continuous_end: "14:00",
               preclose: "14:00", close_auction: "14:30", trade_at_last_end: "15:00"}
    half_day: {preopen: "09:00", open_auction: "09:30", continuous_end: "11:00",
               preclose: "11:00", close_auction: "11:30", trade_at_last_end: "12:00"}
    random_end_seconds: 60
  holidays_source: "avis BRVM 'Jour férié' + absence de BOC"   # liste à maintenir dans les données
  price_limit_pct: 0.075             # actions ET obligations, ±7,5 % autour de la référence
  price_limit_applies_on_ipo_day: true      # référence = prix d'offre
  band_rounding: "inward"            # basse = ceil, haute = floor au pas (vérifié BOC 2018-2026)
  band_min_one_tick: true            # ETIT 13 -> 14 (+7,69 %) observé 10 fois ; haute >= ref + pas
  tick:
    equity_rule: [{below: 100, tick: 1}, {else: 5}]   # FCFA ; empirique 2017-2026 (ETIT, NEIC), texte I-E = 5 seulement
    bond_pct_nominal: 0.001
  lot_size: 1
  short_selling: false
  margin: false
  settlement_lag_days: 2             # J+2 depuis le 2025-12-04 (J+3 avant)
  settlement_lag_history: [{until: "2025-12-03", lag: 3}, {from: "2025-12-04", lag: 2}]
  ex_date_rule: "business_day_before_record_date"
  ex_date_rule_history:              # vérifié sur les lignes (V) des BOC 2023-2026
    - {until: "2025-12-03", business_days_before_record: 2}
    - {from: "2025-12-04", business_days_before_record: 1}
  cancel_open_orders_on_corporate_action: true
  missing_boc_is_not_holiday: true   # contrôler la continuité des n° de BOC (2026 : n° 54 et 187 manquants)

costs:                                # par côté (achat ET vente)
  brvm_fee: 0.0020
  dcbr_fee: 0.0010
  broker_commission: {default: 0.0100, min_observed: 0.0040, negotiated_case: 0.0050}
  tax_on_commission: {rate: 0.10, verified: false}   # TAF/TVA : taux NON vérifié
  amf_levy: {rate: 0.0, verified: false}             # aucune redevance trouvée
  custody_annual: {default: 0.0025, range: [0.0, 0.005]}
  account_fee_annual_fcfa_per_line: {default: 5000, range: [0, 10000]}   # BICI : 5 000 PP / 10 000 PM PAR LIGNE ; FGI : 0
  slippage_model: "half_spread + impact"
  half_spread_default: 0.0035        # spread médian de clôture 0,69 % en 2026
  max_participation_of_adv: 0.10     # hypothèse prudente de recherche

tax:
  irvm_dividend:                      # taux du pays du siège de l'émetteur
    # RÈGLE PRIORITAIRE : utiliser le montant NET publié au BOC ; ces taux ne servent qu'au brut <-> net
    CI: {individual: 0.12, corporate: 0.10, confidence: H,
         history: [{until: "2024-12-31", individual: 0.10, confidence: M}]}   # inféré des nets BOC 2024
    SN: {individual: 0.10, confidence: H, valid_from: "2026-01-01",
         history_verified: false}            # nets antérieurs compatibles avec 0,125
    BF: {individual: 0.125, confidence: B, verified: false}   # CBIBF 2026 compatible avec 0,10
    ML: {individual: 0.07, confidence: M, valid_from: "2025-01-01",
         history: [{until: "2024-12-31", individual: 0.10, confidence: B}]}
    NE: {individual: 0.07, confidence: H}
    BJ: {individual: null, by_issuer: {LNBB: 0.05, BICB: 0.05, BOAB: 0.10}, confidence: B}  # inféré
    TG: {individual: null, confidence: B}   # inconnu : utiliser les montants NETS du BOC
  capital_gains_individual: {rate: 0.0, verified: false}

indices:
  BRVM_C:  {members: all, weight: full_market_cap, cap: null, base: {date: "1998-09-15", value: 100}}
  BRVM_30: {members: top30_traded, review: quarterly, weight: full_market_cap, cap: null,
            base: {date: "2023-01-02", value: 100}}
  BRVM_PRESTIGE: {members: compartment_prestige, review: annual, weight: full_market_cap,
                  cap: 0.20, cap_verified: "partial"}
  BRVM_C_TR: {dividends: net_reinvested, base: {date: "2025-01-02", value: 100}}
  benchmark_for_alpha: "BRVM_C_TR"    # benchmark honnête (dividendes inclus)
```

### 12.2 Fonctions de référence (Python)

```python
import math

def tick(symbol: str, price: float) -> int:
    return 1 if price < 100 else 5                # §2.3 : règle empirique 2017-2026 (ETIT, NEIC)

def price_band(ref: float, symbol: str, pct: float = 0.075) -> tuple[int, int]:
    t = tick(symbol, ref)
    lo = math.ceil(ref * (1 - pct) / t - 1e-9) * t
    hi = math.floor(ref * (1 + pct) / t + 1e-9) * t
    hi = max(hi, ref + t)                         # pas minimal (ETIT 13 -> 14 observé)
    lo = min(lo, ref - t)                         # par symétrie (non observé)
    return lo, hi                                 # vérifié : 11 avis + BOC 2018-2026

def ex_dividend_reference(close_cum: float, div_net_individual: float, symbol: str) -> int:
    t = tick(symbol, close_cum)
    x = close_cum - div_net_individual
    return math.ceil(x / t - 1e-9) * t if t == 5 else round(x)   # 44/45 cas 2025-2026 ; préférer la réf. (d) du BOC

def bonus_reference(close_cum: float, new: int, old: int, t: int = 5) -> int:
    return math.floor(close_cum * old / (old + new) / t) * t       # attributions 2024 : arrondi vers le bas

def side_cost(notional: float, broker=0.01, tax_on_broker=0.10) -> float:
    return notional * (broker * (1 + tax_on_broker) + 0.002 + 0.001)
```

### 12.3 Règles pour le pipeline de données et le backtest

1. **Source de vérité** : BOC (« Clôt. », « Cours de référence », colonnes volume et valeur). Ne jamais utiliser le bandeau du site, ni les « transactions sur dossier ».
2. **Lignes spéciales du BOC** :
   - **(d)** = dernier jour avec droit. Le cours de référence de la ligne est ajusté du dividende net.
   - **(V)** = jour ex. « Cours précédent » est **en général** la référence ajustée, avec des exceptions (SNTS 15/05/2024, SOGC 10/07/2025). Dans les BOC 2018-2022, il n'est jamais ajusté. Il faut prendre la référence de la ligne (d).
   - **Val-T** = valeur théorique (split ou attribution).
   - **SP** = suspendu.
   - **NC** = non coté.
3. **Ajustement historique** : appliquer des facteurs multiplicatifs aux prix antérieurs.
   - Split SNTS 10 pour 1, le 26/10/2026 : f = 0,1.
   - Split SLBC 10 pour 1, le 30/09/2024 : f = 0,1.
   - Attributions de 2024 : facteurs du §8.2.
   - DPS SAFC du 24/04/2026 : f = 3 890 / 5 505 = 0,7066 (référence ex-DPS divisée par la clôture avec droit).
   - Dividendes : `f = réf_ex / clôture_avec_droit`.
4. **Rendement total** : `(Clôt_t + D_net) / Clôt_{t-1} − 1` le jour ex. C'est la convention du BRVM Composite TR (dividendes nets).
5. **Exécution simulée** :
   - aucun achat si la clôture est à la borne haute avec excès de demande (bid ≥ borne haute sans offre) ;
   - aucune vente symétrique à la borne basse ;
   - décision en J, exécution au plus tôt au fixing d'ouverture de J+1 ;
   - liquidité disponible en J+2 (règlement), J+3 avant le 04/12/2025.
6. **Univers investissable** :
   - exclure les titres suspendus (SICC et SEMC au 20/11/2026) et ceux dont le flottant est inférieur à 15 % (UNLC 0,22 %, CFAC 4,15 %, SEMC, SICC) ;
   - filtrer sur la liquidité : valeur médiane par séance ≥ 5 M FCFA (41 titres sur 48 en 2026 ; en dessous : NEIC, CABC, CFAC, PRSC, BNBC, UNLC, SICC) ;
   - limiter chaque ordre à 10 % de la valeur médiane quotidienne.
7. **Jours d'introduction** : ignorer au moins les 5 premières séances pour les signaux. BBGC est resté bloqué à la borne haute pendant 4 séances.
8. **Fiscalité dans les rendements** : modéliser des **dividendes nets** (taux du pays de l'émetteur). Pour TG, utiliser le net publié au BOC.
9. **Benchmark** : BRVM Composite Total Return. Comparer à l'indice prix surestime l'alpha d'environ le rendement en dividendes, soit **+6,6 points en 2026**.
10. **Réplication des indices** : Composite et BRVM 30 en capitalisation totale ; Prestige avec un plafond d'environ 20 %, à recalibrer à chaque révision.

---

## 13. Questions ouvertes (à traiter dans d'autres tâches)

- ~~Seuil exact du pas de cotation de 1 FCFA~~ : **résolu empiriquement le 22/11/2026**, pas de 1 FCFA sous 100 FCFA (§2.3). Le texte officiel qui fixe ce seuil reste à trouver.
- Taux d'IRVM historiques (SN avant 2026, ML avant 2025, BF, BJ par émetteur). Les valeurs ont été déduites des nets du BOC et doivent être confirmées par des sources primaires (AG, CGI).
- Écart SGBC 2026 : le net publié au BOC (2 298,75) diffère de 2 606 × 0,88 (2 293,28).
- Taux de la taxe sur le courtage (TAF/TVA) par pays, et existence d'une redevance AMF-UMOA. Il faut un vrai avis d'opéré de SGI.
- Taux d'IRVM au Togo (ETIT, ORGT). Régime appliqué aux non-résidents UEMOA et hors UEMOA.
- Fiscalité des plus-values sur actions cotées, pays par pays (CGI 2026 de chaque État).
- Méthodologie officielle (formule et plafonnement) des indices Prestige, Principal et sectoriels. Composition BRVM 30 du T1-2026 (avis 002-2026, non lu).
- Règle de report (« réservation ») en cotation continue : durée de la période de report et traitement des ordres hors bornes pendant le continu (le texte de 2016 décrit surtout le fixing).
- ~~Cause de l'absence du BOC du 02/10/2026~~ : **c'était une séance** (BOC n° 187, d'après la numérotation). Il faut récupérer ce fichier ainsi que le n° 54 (19 ou 20/03/2026).
- Motif officiel des suspensions de SICC et SEMC du 16/09/2026.

---

## Sources

### Documents primaires BRVM / AMF-UMOA (consultés le 22/11/2026)
- Horaires de cotation : https://www.brvm.org/fr/horaires-de-cotation
- « Quels sont les frais applicables ? » : https://www.brvm.org/fr/node/312
- Tarification BRVM – DC/BR (version du 01/07/2010, MAJ du 01/01/2014) : https://www.brvm.org/sites/default/files/9_pj_tarification_-_v_010710_maj_01012014_v4_-_valide_ca_002.pdf
- Règles de négociation, d'admission et de radiation (2016 ; instructions I-A et I-E) : https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf
- Règlement général de la BRVM (après approbation CREPMF, sept. 2021) : https://www.brvm.org/sites/default/files/rg_brvm_-_apres_approbation_crepmf_sept_2021_version_finale.pdf
- Liste des textes BRVM : https://www.brvm.org/fr/textes-reglementaires/reglement-general-instructions-circulaires-et-autres-textes-publies-par-la
- Instruction N°03-2025/BRVM/DG (J+3 → J+2) : https://www.brvm.org/sites/default/files/instruction_03_2025_brvm_dg_reduction_delai_j3_j2_0.pdf
- Page fiscalité BRVM (Directive 02/2010/CM/UEMOA) : https://www.brvm.org/fr/node/313
- Communiqué du 02/01/2023 (compartiments, BRVM 30, Prestige) : https://www.brvm.org/fr/mediacentre/actualites/communique-la-brvm-reorganise-ses-compartiments-et-demarre-lannee-avec-de
- Article « Le BOC : des évolutions majeures » (2026) : https://www.brvm.org/fr/mediacentre/actualites/le-bulletin-officiel-de-la-cote-de-la-brvm-des-evolutions-majeures-pour-une
- Page indices : https://www.brvm.org/fr/indices
- BOC du 20/11/2026 : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (copie locale `data/boc_text/boc_20261120.txt.gz`), ainsi que les BOC du 02/01 au 19/11/2026 (copies locales)
- Avis 341-2024 (nouveaux indices sectoriels) : https://www.brvm.org/sites/default/files/20241226_-_avis_ndeg341_brvmdg_-_nouveaux_indices_de_la_brvm.pdf
- Avis 307-2025 (suppression des anciens indices) : https://www.brvm.org/sites/default/files/20251224_-_avis_ndeg307_brvmdg_-_suppression_des_anciens_indices_au_profit_des_nouveaux_indices_sectoriels.pdf
- Avis 308-2025 (affichage du Total Return) : https://www.brvm.org/sites/default/files/20251224_-_avis_ndeg308_brvmdg_-_affichage_de_lindice_brvm_composite_total_return_index.pdf
- Avis 001-2026 (Prestige) : https://www.brvm.org/sites/default/files/20260102_-_avis_ndeg001_brvmdg_-_composition_de_lindice_brvm_prestige.pdf
- Avis 081, 191 et 289-2026 (BRVM 30) :
  - https://www.brvm.org/sites/default/files/20260401_-_avis_ndeg081_brvmdg_-_composition_de_lindice_brvm_30.pdf
  - https://www.brvm.org/sites/default/files/20260701_-_avis_ndeg191_brvmdg_-_composition_de_lindice_brvm_30.pdf
  - https://www.brvm.org/sites/default/files/20261001_-_avis_ndeg289_brvmdg_-_composition_de_lindice_brvm_30.pdf
- Avis 303-2026 (flottant au 31/12/2025) : https://www.brvm.org/sites/default/files/20261012_-_avis_ndeg303_brvmdg_-_flottant_des_societes_cotees_a_la_brvm.pdf
- Avis 192-2026 (seuils acheté/vendu) : https://www.brvm.org/sites/default/files/20260701_-_avis_ndeg192_brvmdg_-_seuils_minimaux_des_transactions_par_operation_dachete_-_vendu.pdf
- Avis 296-2026 (transactions sur dossier) : https://www.brvm.org/sites/default/files/20261008_-_avis_ndeg296_brvmdg_-_transactions_sur_dossier.pdf
- Avis 309-2026 (split SONATEL) : https://www.brvm.org/sites/default/files/20261023_-_avis_ndeg309_brvmdg_-_fractionnement_dactions_valeur_theorique_-_sonatel_sn.pdf
- Avis 242-2024 (split SOLIBRA) : https://www.brvm.org/sites/default/files/20240927_-_avis_ndeg242_brvmdg_-_fractionnement_dactions_valeur_theorique_-_solibra_ci.pdf
- Attributions gratuites 2024 :
  - https://www.brvm.org/sites/default/files/20240827_-_avis_ndeg208_brvmdg_-_valeur_theorique_-_droit_dattribution_-_boa_ml.pdf
  - https://www.brvm.org/sites/default/files/20240827_-_avis_ndeg209_brvmdg_-_valeur_theorique_-_droit_dattribution_-_boa_bf.pdf
  - https://www.brvm.org/sites/default/files/20240828_-_avis_ndeg212_brvmdg_-_valeur_theorique_-_droit_dattribution_-_boa_sn.pdf
  - https://www.brvm.org/sites/default/files/20240902_-_avis_ndeg216_brvmdg_-_valeur_theorique_-_droit_dattribution_-_boa_bn.pdf
  - https://www.brvm.org/sites/default/files/20240903_-_avis_ndeg217_brvmdg_-_valeur_theorique_-_droit_dattribution_-_boa_ng.pdf
  - https://www.brvm.org/sites/default/files/20241024_-_avis_ndeg267_brvmdg_-_valeur_theorique_-_droit_dattribution_-_boa_ci.pdf
  - https://www.brvm.org/sites/default/files/20241113_-_avis_ndeg293_brvmdg_-_valeur_theorique_-_droit_dattribution_-_sib_ci.pdf
- SAFCA CI :
  - https://www.brvm.org/sites/default/files/20260423_-_avis_ndeg108_brvmdg_-_valeur_theorique_-_dps_-_augmentation_de_k_-_safca_ci.pdf
  - https://www.brvm.org/sites/default/files/20260811_-_avis_ndeg237_brvmdg_-_admission_a_la_cote_actions_nouvelles_safca_ci.pdf
- MOVIS CI :
  - https://www.brvm.org/sites/default/files/20250407-_avis_ndeg_069_brvmdg-_ouverture_de_loffre_publique_de_retrait_movis.pdf
  - https://www.brvm.org/sites/default/files/20250625_-_avis_ndeg142_brvmdg_-_radiation_movis_ci.pdf
- Introductions en bourse :
  - https://www.brvm.org/sites/default/files/20221223_-_avis_ndeg256_brvmdg_-_premiere_cotation_-_orange_ci.pdf
  - https://www.brvm.org/sites/default/files/20221230_-_avis_ndeg261_brvmdg_-_resultat_de_premiere_cotation_-_orange_ci.pdf
  - https://www.brvm.org/sites/default/files/20241128_-_avis_ndeg310_brvmdg_-_premiere_cotation_-_loterie_nationale_du_benin.pdf
  - https://www.brvm.org/sites/default/files/20241213_-_avis_ndeg322_brvmdg_-_resultat_de_premiere_cotation_-_lnb_bn.pdf
  - https://www.brvm.org/sites/default/files/20250410_-_avis_ndeg073_brvmdg_-_premiere_cotation_-biic.pdf
  - https://www.brvm.org/sites/default/files/20250428_-_avis_ndeg088_brvmdg_-_resultat_de_premiere_cotation_-_biic_benin.pdf
  - https://www.brvm.org/sites/default/files/20260908_-_avis_ndeg263_brvmdg_-_premiere_cotation_-bridge_bank_group_cote_divoire.pdf
  - https://www.brvm.org/sites/default/files/20260924_-_avis_ndeg285_brvmdg_-_resultats_de_premiere_cotation_-_bridge_bank_group_cote_divoire_bbgc.pdf
- Calendrier de paiement des dividendes (06/10/2026) : https://www.brvm.org/sites/default/files/20261006_-_calendrier_de_paiement_des_dividendes_-_exercice_2025.pdf
- Avis de dividendes 2026 :
  - https://www.brvm.org/sites/default/files/20260423_-_avis_ndeg111_brvmdg_-_paiement_de_dividendes_exo_2025_-_sonatel_sn.pdf
  - https://www.brvm.org/sites/default/files/20260331_-_avis_ndeg072_brvmdg_-_paiement_de_dividendes_exo_2025_-_boa_bf.pdf
  - https://www.brvm.org/sites/default/files/20260508_-_avis_ndeg121_brvmdg_-_paiement_de_dividendes_exo_2025_-_boab.pdf
  - https://www.brvm.org/sites/default/files/20260511_-_avis_ndeg129_brvmdg_-_paiement_de_dividendes_exo_2025_-_boam.pdf
  - https://www.brvm.org/sites/default/files/20260508_-_avis_ndeg122_brvmdg_-_paiement_de_dividendes_exo_2025_-_boa_sn.pdf
  - https://www.brvm.org/sites/default/files/20260519_-_avis_ndeg137_brvmdg_-_paiement_de_dividendes_-_onatel_bf.pdf
  - https://www.brvm.org/sites/default/files/20260603_-_avis_n154_brvmdg_-_paiement_de_dividendes_-_exercice_2025_-_coris_bank_international_bf.pdf
  - https://www.brvm.org/sites/default/files/20260616_-_avis_ndeg170_brvmdg_-_paiement_de_dividendes_exercice_2025_-_eti_tg.pdf
  - https://www.brvm.org/sites/default/files/20250720_-_avis_ndeg211_brvmdg_-_paiement_de_dividendes_exo_2025_-_loterie_nationale_du_benin.pdf
  - https://www.brvm.org/sites/default/files/20260703_-_avis_ndeg199_brvmdg_-_paiement_de_dividendes_exo_2025_-_biic_bn.pdf
  - https://www.brvm.org/sites/default/files/20260624_-_avis_ndeg185_brvmdg_-_paiement_de_dividendes_exercice_2025_-_totalenergies_marketing_sn.pdf
  - https://www.brvm.org/sites/default/files/20260806_-_avis_ndeg231_brvmdg_-_paiement_de_dividendes_exercice_2025_-_societe_generale_ci.pdf
- Communiqué de presse BOA Niger (29/04/2026 ; dividende brut 2024 de 225 FCFA) : https://www.brvm.org/sites/default/files/20260429_-_communique_de_presse_-_boa_ng.pdf
- Homologation des tarifs SGI :
  - FGI (décision PAMF-UMOA 124-2025) : https://www.brvm.org/sites/default/files/decision_ndegpamf-umoa_-_124_-_2025_-_homologation_des_tarifs_de_la_sgi_fgi.pdf
  - BICI Bourse (décision 326-2024) : https://www.brvm.org/sites/default/files/decision_ndeg326_sgi_bici_bourse_homologation_des_tarifs_de_la_sgi_bici_bourse.pdf

### Sources secondaires (presse, analyses)
- Passage à J+2 au 04/12/2025 :
  - https://hub24.info/uemoa-brvm-transactions-boursieres-j2-decembre-2025/
  - https://www.financialafrik.com/2025/12/04/le-dc-br-lance-le-passage-officiel-de-t3-a-t2-dans-lumoa/
  - https://dcbruemoa.org/actualites/umoa-le-conseil-dadministration-du-dcbr-approuve-le-passage-du-cycle-de
  - https://leconomistedufaso.com/2025/12/04/le-bulletin-officiel-de-la-cote-de-la-brvm-du-03-decembre-2025/
- IRVM CI 12 %/10 % (note DGI 2025) : https://www.ensafrica.com/news/detail/10530/africa-tax-in-brief-
- Sonatel 1 933 brut → 1 740 net :
  - https://sonatel.sn/wp-content/uploads/2026/03/Projet-OJ-resolutions-AG-SNT-Exercice-2025-.pdf
  - https://osiris.sn/le-geant-senegalais-des-telecommunications-sonatel-versera-des-dividendes-le-26.html
- BOA Burkina, IRVM 12,5 % :
  - https://fr.allafrica.com/stories/202604150436.html
  - https://dabafinance.com/fr/nouvelles/boa-burkina-faso-dividende-2025-paiement-brvm-boabf-ouagadougou
- BOA Mali, IRVM 7 % : https://www.financialafrik.com/2026/03/26/dividende-2025-la-boa-mali-versera-plus-de-9-milliards-de-fcfa-a-ses-actionnaires-a-compter-du-31-mai-2026/
- BOA Niger : https://www.financialafrik.com/2026/04/02/banques-les-actionnaires-de-la-boa-niger-prives-de-dividendes-pour-lexercice-2025/
- LNB, 173 brut / 164 net : https://www.financialafrik.com/2026/05/07/dividende-2025-les-actionnaires-de-la-loterie-nationale-du-benin-percevront-3438-milliards-de-fcfa/
- Togo (taux contradictoires) :
  - https://www.richbourse.com/dossier/dividendes-brvm
  - https://lesafriques.com/2026/10/dividendes-de-la-brvm-ce-que-la-saison-2026-montre-et-les-quatre-chiffres-qui-manquent/
- Split Sonatel (presse) :
  - https://dabafinance.com/fr/nouvelles/Sonatel-va-procder--une-division-de-ses-actions-BRVM--raison-de-10-pour-1--compter-du-26-octobre
  - https://www.osiris.sn/brvm-sonatel-veut-diviser-par-10-son-action-pour-la-rendre-plus-accessible-aux.html
- Bridge Bank, OPV de 67,5 Md FCFA :
  - https://www.african-markets.com/fr/bourse/brvm/bridge-bank-cloture-en-un-jour-son-ipo-de-67-5-milliards-fcfa-a-la-brvm
  - https://www.capmad.com/article/bridge-bank-group-cote-divoire-officialise-son-introduction-a-la-brvm-avec-une-opv-de-20-du-capital
- Indices sectoriels 2025 :
  - https://droitmediasfinance.com/index.php/actualites/droit-des-marches-financiers/1170-brvm-la-suppression-actee-des-anciens-indices-au-profit-des-nouveaux-indices-sectoriels
  - https://www.financialafrik.com/2024/12/31/brvm-mise-en-place-de-sept-nouveaux-indices-sectoriels-a-compter-du-2-janvier-2025/
- Base 100 du Composite au 15/09/1998 (BOC historique) : https://lefaso.net/IMG/pdf/BOC_20120404.pdf
- CREPMF → AMF-UMOA : https://african-markets.com/fr/bourse/brvm/uemoa-le-crepmf-change-de-denomination-pour-amf-umoa
- Flottant (presse) : https://droitmediasfinance.com/index.php/actualites/droit-des-marches-financiers/1437-brvm-44-societes-respectent-le-seuil-de-flottant-4-restent-en-dehors-du-seuil-sicor-ci-sonoco-metal-packaging-siem-ci-cfao-mobility-ci-et-unilever-ci

### Calculs locaux (reproductibles)
Scripts (bac à sable de session, non versionnés) : analyse des 220 BOC 2026, comprenant
- l'analyse des variations, des bornes et des pas ;
- la reconstruction des indices Composite, BRVM 30, Prestige et TR ;
- le calcul des spreads et des valeurs médiane échangées.

Les résultats chiffrés sont reproduits dans le texte (§3.5, §10.2, §11). Pour les rendre permanents, il faut les réimplémenter dans le module `brvm_alpha` du projet.

---

## Vérification adversariale (2026-11-22)

**Rôle** : vérificateur sceptique indépendant. **Méthode** : chaque élément a été vérifié à nouveau, sans reprendre les calculs du chercheur, de trois façons :
1. relecture des documents primaires téléchargés depuis `www.brvm.org` par `curl`, avec OCR (tesseract, français) pour les PDF scannés ;
2. re-parsing complet des BOC locaux 2017-2026 (≈ 96 700 lignes action×séance ; 2017 et 2021 partiellement lisibles) ;
3. tests arithmétiques.

**Limites de la session** :
- seul `www.brvm.org` était joignable. financialafrik, allafrica, ensafrica, sonatel.sn et hub24 ont été refusés par le proxy, et le quota de recherche web était épuisé. Les sources secondaires citées par le chercheur **n'ont donc pas pu être relues** ;
- ce document ne cite aucune étude académique, il n'y avait donc aucune référence bibliographique à contrôler.

| # | Élément vérifié | Verdict | Valeur retenue | Preuve |
|---|---|---|---|---|
| 1 | Plafond ±7,5 % (actions **et** obligations) | **Confirmé** + nuance | 0,075 ; au minimum un pas de cotation (ETIT 13 → 14 = +7,69 %, 10 fois en 2019-2021) | Instruction I-A (texte relu) ; BOC 2018-2026 : aucun dépassement hors jours ex mal ajustés et pas minimal |
| 2 | Arrondi des bornes vers l'intérieur (ceil / floor) | **Confirmé** | inchangé | Avis 309-2026 et 108-2026 relus ; 1 638 + 1 262 cas discriminants dans les BOC, 0 contre-exemple |
| 3 | Pas de cotation 5 FCFA ; 1 FCFA pour ETIT, « seuil inconnu » | **Corrigé** | 1 FCFA si cours < 100 FCFA, sinon 5 | BOC 2017-2026 : ≈ 11 000 clôtures entre 100 et 999 FCFA, toutes multiples de 5 ; non-multiples seulement sous 100 FCFA (ETIT, NEIC). « Aucune action entre 100 et 1 000 FCFA en 2026 » est **réfuté** (SEMC 750-990 FCFA en janvier 2026) |
| 4 | Règlement J+2 au 04/12/2025 (J+3 avant) | **Confirmé** | inchangé | Instruction 03-2025 du 02/12/2025, relue par OCR (en vigueur à sa publication au BOC) ; listée au BOC du 03/12/2025 ; changement visible dans les dates ex |
| 5 | Règle ex-date (1er jour ouvré avant les registres) | **Confirmé (2026) + corrigé (historique)** | 2 jours ouvrés avant jusqu'au 03/12/2025, puis 1 jour | Lignes (V) des BOC : 77/80 cas à 2 jours en 2023-2025, 35/35 à 1 jour en 2026 ; avis 072, 111, 121, 129, 154 et 199-2026 |
| 6 | Horaires de séance (UTC) et veille de fête | **Confirmé** | inchangé | brvm.org/fr/horaires-de-cotation (relu le 22/11/2026, ±60 s) |
| 7 | Commission BRVM 0,20 % et DC/BR 0,10 % par côté | **Confirmé** | 0,0020 + 0,0010, acheteur ET vendeur | brvm.org/fr/node/312 (« payables par l'Acheteur et par le Vendeur ») ; tarification 2014, tableau B.1 |
| 8 | Courtage SGI 0,4-1 % (BICI Bourse), ≤ 1 % (FGI) | **Confirmé** | inchangé | Décisions PAMF-UMOA 2024-326 (04/12/2024) et 2025-124 (28/03/2025), relues par OCR |
| 9 | Droits de garde et tenue de compte | **Corrigé** | garde 0,1-0,5 % par an (BICI), ≤ 0,25 % (FGI) ; tenue de compte **5 000 FCFA par LIGNE** et par an (BICI, personne physique) | Annexe de la décision 326-2024 : « Forfait par ligne » |
| 10 | Taxe de 10 % sur le courtage (TAF/TVA) | **Invérifiable** | [NON VÉRIFIÉ], conservée comme hypothèse | Absente de la tarification BRVM et des grilles SGI ; sources secondaires inaccessibles |
| 11 | IRVM CI 12 % (personne physique) / 10 % (personne morale) | **Confirmé** + historique ajouté | 0,12 (paiements 2025-2026) ; 0,10 jusqu'en 2024 (inférence) | Calendrier BRVM du 06/10/2026 ; avis 231-2026 ; nets BOC = brut × 0,88 (12 émetteurs) ; nets 2024 = brut rond × 0,90 |
| 12 | IRVM SN 10 % | **Confirmé pour 2026** ; historique [NON VÉRIFIÉ] | 0,10 depuis 2026 | Avis 111-2026 (1 740 net) ; BOAS 450 = 500 × 0,9. Nets antérieurs compatibles avec 12,5 % |
| 13 | IRVM NE 7 % | **Confirmé** (M+ → H) | 0,07 | Communiqué BOA NG (brut 225) et BOC 209,25 ; nets BOAN 2021-2024 = bruts ronds × 0,93 |
| 14 | IRVM ML 7 % | **Confirmé pour 2025-2026** | 0,07 (2024 : 0,10 [NON VÉRIFIÉ]) | Avis 129-2026 (305,04 = 328 × 0,93) ; 237,15 = 255 × 0,93 |
| 15 | IRVM BJ ≈ 5 % | **Corrigé** (taux unique réfuté) | selon l'émetteur : LNBB et BICB ≈ 5 %, BOAB ≈ 10 % (inférence) | Nets des avis 121, 199 et 211-2026 ; 585 = 650 × 0,9 ; 254,6 = 268 × 0,95 |
| 16 | IRVM BF 12,5 % | **Invérifiable** (plausible) | 0,125 [NON VÉRIFIÉ] | Avis 072-2026 : 397 net, sans le brut ; CBIBF 2026 (900 = 1 000 × 0,9) contredit un taux uniforme |
| 17 | Split SONATEL 10 pour 1 au 26/10/2026, f = 0,1 | **Confirmé** | inchangé | Avis 309-2026 relu (réf. 4 385, bornes [4 060 ; 4 710]) ; BOC : clôture 43 850 le 23/10, ouverture 4 710 le 26/10 |
| 18 | Split SOLIBRA 10 pour 1 au 30/09/2024 | **Confirmé** | inchangé | BOC du 30/09/2024 : ligne (V), précédent 10 215 |
| 19 | DPS SAFCA 6 pour 13, f = 0,7066 | **Confirmé** | 3 890 / 5 505 = 0,7066 | Avis 108-2026 relu (DPS 1 615, réf. 3 890, bornes [3 600 ; 4 180]) ; BOC du 23/04/2026, clôture 5 505 |
| 20 | Attributions gratuites 2024 (7 titres, ratios et dates ex) | **Confirmé** + précision | références arrondies **vers le bas** | BOC : clôtures avec droit et références ex (BOAM 2 020 → 1 345, BOAN 5 220 → 3 260, etc.) |
| 21 | Introductions : bande de ±7,5 % le 1er jour, prix et 1ers cours | **Confirmé** | inchangé | BOC : ORAC 10 210 (30/12/2022), LNBB 5 160, BICB 5 600, BBGC 7 255 puis 7 795, 8 375 et 9 000 (bornes exactes) |
| 22 | Radiation de MOVIS le 25/06/2025 | **Précisé** | avis du 25/06/2025 ; dernière ligne (SP) au BOC du 26/06/2025 | BOC des 25, 26 et 27/06/2025 |
| 23 | Composite pondéré par la capitalisation totale | **Confirmé** | inchangé | ΔComposite − ΔCapitalisation : médiane 0,09 pb sur 465 séances |
| 24 | Total Return avec dividendes nets réinvestis | **Confirmé** | inchangé | 4 jours ex : écart observé = prédiction avec les nets (à ± 2 pb près), loin de la prédiction avec les bruts |
| 25 | Niveaux des indices au 20/11/2026, écart de +6,6 pts du TR | **Confirmé** | inchangé | BOC n° 222 |
| 26 | Compositions BRVM 30 (T4-2026) et Prestige 2026 | **Confirmé** | inchangé | Avis 289-2026 et 001-2026, relus par OCR |
| 27 | Exceptions au flottant (SICC 12,26 %, SEMC 10,29 %, CFAC 4,15 %, UNLC 0,22 %) | **Confirmé** | inchangé | Avis 303-2026 relu par OCR (CFAC : 181 371 900 titres) |
| 28 | Spread médian 0,69 % ; 41/48 titres ≥ 5 M FCFA par séance | **Confirmé** + réserve | inchangé | Recalcul indépendant (BOAM 0,21 %, UNLC 4,26 %). Spread mesuré seulement quand le carnet a les deux côtés |
| 29 | BOC absents de 2026 = jours fériés ; 02/10 « sans explication » | **Corrigé** | le 02/10/2026 et l'un des jours 19-20/03 étaient des séances (BOC manquants) | Numérotation des BOC : 186 → 188 et 53 → 55 ; 220 fichiers pour 222 séances |
| 30 | AMF-UMOA « depuis le 01/01/2021 » | **Corrigé** | Traité révisé du 12/07/2019, en vigueur le 01/10/2022 | Visas de la décision PAMF-UMOA 2024-326 |
| 31 | Ventes à découvert et marge interdites (art. 1123) | **Confirmé** | long-only | Texte de l'art. 1123 relu |
| 32 | Critères des compartiments (RG art. 62, 63, 63 bis) | **Confirmé** | inchangé | RG BRVM 2021 (texte) |
| 33 | Base 100 du Composite au 15/09/1998 | **Invérifiable** dans la session | [NON VÉRIFIÉ] | Absente des BOC locaux ; lefaso.net inaccessible |
| 34 | Référence ex-dividende = ceil_5(clôture − net) | **Confirmé** | inchangé (44/45 cas en 2025-2026) | Lignes (d) des BOC ; exception BOAC expliquée par le montant net utilisé |
| 35 | « Cours précédent » de la ligne (V) = référence ajustée | **Corrigé** (pas toujours vrai) | utiliser la référence de la ligne (d) | SNTS 15/05/2024, SOGC 10/07/2025 ; BOC 2018-2022 non ajustés |

**Bilan** : 35 éléments contrôlés.
- Aucun paramètre de coût ou de microstructure à fort impact n'a été réfuté.
- 9 corrections ou précisions intégrées : pas de cotation, règle ex-date historique, tenue de compte par ligne, IRVM BJ et historiques, date AMF-UMOA, BOC manquants, (V) non fiable, MOVIS, arrondi des attributions.
- 4 éléments restent invérifiables et sont marqués [NON VÉRIFIÉ] : taxe sur le courtage, IRVM BF, plus-values, base 1998.

**Sources ajoutées par la vérification** (consultées le 22/11/2026) :
- https://www.brvm.org/fr/node/312 ; https://www.brvm.org/fr/horaires-de-cotation ; https://www.brvm.org/fr/node/313
- https://www.brvm.org/sites/default/files/instruction_03_2025_brvm_dg_reduction_delai_j3_j2_0.pdf
- https://www.brvm.org/sites/default/files/9_pj_tarification_-_v_010710_maj_01012014_v4_-_valide_ca_002.pdf
- https://www.brvm.org/sites/default/files/decision_ndeg326_sgi_bici_bourse_homologation_des_tarifs_de_la_sgi_bici_bourse.pdf
- https://www.brvm.org/sites/default/files/decision_ndegpamf-umoa_-_124_-_2025_-_homologation_des_tarifs_de_la_sgi_fgi.pdf
- https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf (Instructions I-A et I-E ; art. 1123)
- https://www.brvm.org/sites/default/files/20261006_-_calendrier_de_paiement_des_dividendes_-_exercice_2025.pdf
- Avis de dividendes 072, 111, 121, 129, 154, 199 et 231-2026 (URL dans la section Sources ci-dessus)
- https://www.brvm.org/sites/default/files/20260429_-_communique_de_presse_-_boa_ng.pdf
- https://www.brvm.org/sites/default/files/20261023_-_avis_ndeg309_brvmdg_-_fractionnement_dactions_valeur_theorique_-_sonatel_sn.pdf
- https://www.brvm.org/sites/default/files/20260423_-_avis_ndeg108_brvmdg_-_valeur_theorique_-_dps_-_augmentation_de_k_-_safca_ci.pdf
- https://www.brvm.org/sites/default/files/20261012_-_avis_ndeg303_brvmdg_-_flottant_des_societes_cotees_a_la_brvm.pdf
- https://www.brvm.org/sites/default/files/20261001_-_avis_ndeg289_brvmdg_-_composition_de_lindice_brvm_30.pdf
- https://www.brvm.org/sites/default/files/20260102_-_avis_ndeg001_brvmdg_-_composition_de_lindice_brvm_prestige.pdf
- BOC locaux `data/boc_text/boc_2017*.txt.gz` à `boc_20261120.txt.gz`, re-parsés de façon indépendante
