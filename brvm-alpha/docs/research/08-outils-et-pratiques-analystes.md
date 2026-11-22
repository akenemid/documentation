# 08 — Outils, données et pratiques professionnelles : ce qui existe pour la BRVM, et ce qu'il faut battre

> **Projet** : BRVM Alpha · **Module** : recherche / données, référentiels de performance, pratiques des analystes
> **Rédigé le** : 2026-11-22 · **Statut** : v1.1 (vérification adversariale du 22/11/2026 intégrée)
> **Portée** : (1) outils et sources de données existants pour la BRVM et leurs pièges ; (2) pratiques des SGI, des analystes et des gérants d'OPCVM, et **performance réelle des fonds actions de l'UEMOA face aux indices** ; (3) performance historique des indices BRVM de 2010 à 2026 (rendements annuels, dividendes, volatilité, drawdowns) ; (4) ouvrages de référence et ce qu'il faut en retenir concrètement pour la BRVM.
> **Documents liés** : `01-structure-marche.md` (indices, splits, frais), `02-litterature-brvm.md`, `03-facteurs-marches-frontieres.md`, `04-rigueur-quantitative.md` (prix périmés, DSR, PBO), `05-macro-geopolitique-uemoa.md` (taux sans risque 5,75 %, CRP), `06a/06b` (sociétés), `07-actualite-sentiment-evenements.md` (accès aux sites tiers).
>
> **Après vérification adversariale (22/11/2026, dernière section)** : 30 éléments ont été recontrôlés sur les BOC locaux, le panel reconstruit et les pages et PDF de brvm.org, PyPI et le miroir CRAN. La plupart des faits primaires sont **confirmés** : indices, drawdowns, volatilité mensuelle, catalogue 2019, paquets R et Python, Awards, filtre de Graham et taux de 5,75 %. Les corrections sont les suivantes.
> - **Splits** : le panel actuel en compte **50**, et non 47.
> - **SGI** : la liste de brvm.org compte **37 noms distincts sur 10 pages**, et non 34 sur 9.
> - **Valorisation** : l'affirmation « marché le plus cher de la décennie » est **réfutée**, car le PER de 2017 était plus élevé.
> - **Fonds et TR 2026** : l'affirmation « Attijari Actions bat le TR en 2026 » est **réfutée** une fois les fenêtres alignées, et le repère TR des cumuls longs est corrigé.
> - **Taux de réussite des fonds** : ils sont **ramenés à des fourchettes**, car leur valeur exacte dépend de la lecture des catégories.
> - **Références bibliographiques** : elles restent **[NON VÉRIFIÉ]** dans cette session (pas de recherche web ; doi.org et Crossref bloqués).

---

## 0. Avertissement et méthode

1. **Aucun outil, aucun livre et aucun analyste ne garantit un gain.** Ce document montre au contraire que les **gérants professionnels de la région ne battent pas régulièrement l'indice dividendes réinvestis** (section 3.3). Un objectif de « 100 % de gains garantis » est impossible. Notre engagement est d'être mesurable : chaque recommandation de la plate-forme sera comparée publiquement au **BRVM Composite Total Return** et à la **médiane des fonds actions**.
2. **Limites d'accès pendant cette revue (à lire)** :
   - Le **budget de recherche web était épuisé** dès le début de cette tâche (message de l'outil : « this turn's web search budget is used up »). **Aucune recherche par moteur n'a pu être faite.**
   - Hôtes **refusés par le réseau de la session** : `cran.r-project.org`, `cloud.r-project.org`, `www.rdocumentation.org`, `r-universe.dev`, `en.wikipedia.org`, `pages.stern.nyu.edu` (Damodaran), `papers.ssrn.com`, `www.bceao.int`, `www.amf-umoa.org`, `www.african-markets.com`, `www.investing.com`, `www.hudson-cie.com`.
   - `www.sikafinance.com` et `www.richbourse.com` répondent **HTTP 403** à une requête simple. WebFetch ne résout pas ces domaines. Pour Sika Finance, le doc 07 a observé une page Cloudflare « Attention Required! ». **Nous ne contournons aucune protection anti-robot.**
   - Hôtes accessibles et utilisés : `www.brvm.org` (pages et PDF publics), `pypi.org` (API JSON documentée), `raw.githubusercontent.com` (miroir GitHub officiel de CRAN, `cran/BRVM`).
   - La vérification adversariale du 22/11/2026 a eu les **mêmes limites** : budget de recherche web épuisé, `doi.org` et `api.crossref.org` refusés. Elle s'est appuyée sur les BOC locaux et le panel, sur brvm.org (pages HTML, rapports annuels 2015-2016, catalogue 2019), sur `pypi.org` et sur `raw.githubusercontent.com`.
   - Conséquence : **les notes de recherche des SGI (Hudson & Cie, Bridge Securities, etc.) et leurs recommandations n'ont pas pu être lues**. Leur performance historique est **introuvable dans cette session**. Rien n'est inventé à leur sujet.
3. **Ce qui compense** : deux sources primaires très riches ont été exploitées.
   - (a) Les **rapports annuels BRVM 2013-2016**, téléchargés sur brvm.org, donnent les indices de 2010 à 2016.
   - (b) Nos **2 581 BOC** (du 02/01/2017 au 20/11/2026). Ils contiennent, en plus des cours, la **section OPCVM** avec les **valeurs liquidatives** de 168 fonds. Nous en avons tiré une **mesure systématique de la performance des fonds actions UEMOA face au Composite** (section 3.3). Faute de recherche web, nous n'avons pas pu vérifier si une mesure équivalente a déjà été publiée.
4. **Étiquettes de vérification** :
   - **[P]** : source primaire lue dans cette session (brvm.org, BOC, PDF, code du paquet) ;
   - **[C]** : calcul interne reproductible sur les BOC parsés (`data/panel/*.parquet`, scripts décrits en annexe) ;
   - **[D]** : dérivation arithmétique ;
   - **[R]** : fait rapporté par un autre document de recherche du projet, avec son URL ;
   - **[B]** : référence bibliographique classique, **non relue dans cette session**.
5. **Confiance** : **high** = primaire lu ou calcul reproductible ; **medium** = calcul avec hypothèse explicite, ou lecture partielle ; **low** = lecture incertaine (image floue), source unique secondaire, ou jugement.

---

## 1. Résumé exécutif

| # | Conclusion | Conf. |
|---|---|---|
| 1 | **La seule source gratuite, complète et traçable est le BOC quotidien de brvm.org.** Le catalogue officiel le classe comme « produit gratuit » (BR-013). Les flux en temps réel ou différé sont payants (de 600 à 2 500 €/an par service, plus 5 000 à 7 500 €/an de souscription ; catalogue de mars 2019). La base BDFIN coûte 500 000 FCFA/an pour un particulier. Les rediffuseurs officiels sont **Bloomberg, FactSet, Refinitiv et SIX**. | high [P] |
| 2 | **Le paquet R « BRVM » (CRAN, v5.3.0, publié le 21/02/2024) ne produit pas ses propres données.** Il **aspire** richbourse (lecture des lignes 600 à 650 d'une page HTML) et appelle l'**API interne non documentée** `sikafinance.com/api/general/GetHistos`. Sa liste de tickers est **figée à 46 titres** : il manque BBGC, BICB et LNBB, et il contient SVOC, radié en 2025. **À ne pas utiliser en production.** | high [P] |
| 3 | **Python : un seul paquet trouvé, `brvmpy` 0.1.0 (04/12/2025).** Il pilote Selenium et Chrome sans interface pour lire l'instantané du jour sur brvm.org, **sans historique**. Les sorties d'exemple de sa documentation affichent un « BRVM 10 » (indice remplacé le 02/01/2023) et un Composite à 210,45 le 04/12/2025, alors que le BOC donne **353,29**. Notre pipeline BOC lui est très supérieur. | high [P] |
| 4 | **Le piège n° 1 des données est le fractionnement non ajusté.** Nous détectons **50 splits** (confiance high) entre 2017 et 2026, dans le panel reconstruit le 22/11/2026 à 02:45 ; la v1 de ce document en annonçait 47, sur une version antérieure du panel. Une vague de splits a suivi, en 2017-2019, les décisions de décembre 2015 (flottant ≥ 20 % et 2 à 10 millions de titres). Sonatel a été divisé par 10 le 26/10/2026 : une série non ajustée montre un faux **−89,3 %** en une séance. | high [P/C] |
| 5 | **Les prix périmés ont fortement reculé.** La part des lignes titre×séance **sans échange** est passée de 21,8 % (2017) et 24,7 % (2020) à **1,0 % (2026)**. La part des variations nulles est passée de 44 % à 16 %. Toute statistique antérieure à 2022 est donc biaisée par le lissage (voir doc 04). | high [C] |
| 6 | **Indices de 2010 à 2026** : le Composite a fait +19,95 % (2012), +39,28 % (2013), +11,23 % (2014), +17,77 % (2015), −3,87 % (2016), −16,81 %, −29,14 %, −7,55 %, −8,71 % (2017-2020), puis +39,15 %, +0,46 %, +5,38 %, +28,89 %, +25,26 % (2021-2025). En 2026, il fait **+42,56 % au 20/11**. Le Composite Total Return officiel a fait environ **+33,1 % en 2025** et **+49,19 %** en 2026 (au 20/11). | high [P] |
| 7 | **Le marché baissier 2016-2020 a été profond et long.** De 303,93 (31/12/2015) à **122,19 (26/10/2020) : −59,8 %**. Dans nos données, le recul vaut −57,9 % depuis le plus haut de 290,44 (01/03/2017), sur **1 334 jours** de baisse. Le niveau de fin 2015 n'a été retrouvé que le **10/06/2025**, soit environ **9 ans et demi sous l'eau** en prix. En rendement total équipondéré, le drawdown maximal a été de **−47,9 %**, rattrapé en septembre 2021. | high [P/C] |
| 8 | **Volatilité annualisée du Composite (2017-2026)** : 11,0 % en journalier, 11,8 à 12,0 % en hebdomadaire (selon le traitement des semaines sans BOC) et **15,5 % en mensuel**. L'écart vient des prix périmés : il faut utiliser le chiffre mensuel pour dimensionner le risque. **43 %** des fenêtres glissantes de 12 mois sont négatives. Les rendements sur 12 mois vont de −29,1 % à +69,4 %. | high [C] |
| 9 | **Le dividende est la moitié de l'histoire.** Le taux de rendement moyen publié par le BOC (« Taux de rendement moyen du marché ») a varié de 5,4 % à 10,1 % en fin d'année entre 2017 et 2026. Il vaut **7,12 %** au 20/11/2026. Sur 2025-2026, **TR − prix ≈ 0,88 × rendement de début d'année** (0,878 et 0,876). En cumul 2017-2026, cela donne **+5,4 %/an en prix** contre **environ +12,2 %/an dividendes réinvestis** (estimation). | high (officiel 2025-26) / medium (estimation avant 2025) [P/C] |
| 10 | **Les gérants professionnels ne battent pas l'indice dividendes réinvestis.** Sur 93 années-fonds de fonds actions (catégorie « A » du BOC, 2017-2026), **48 à 52 (52 à 56 %) battent le Composite prix**, mais seulement **26 à 28 (28 à 30 %) battent le Composite TR** (estimé avant 2025). L'écart médian vaut de +0,2 à +1,8 point contre le prix et **de −6,0 à −4,8 points** contre le TR. Les fourchettes viennent de la vérification : une reproduction indépendante, qui lit la catégorie à la date de fin et compare le TR sur la même fenêtre, donne 52/93, 27/93 et −4,8 points. | medium [C] |
| 11 | **Asymétrie** : les fonds actions **perdent moins en baisse** (24 sur 30 battent le prix en 2017-2020, écart médian +3,9 points) mais **retardent en hausse** (15 sur 45 en 2021, 2024, 2025 et 2026, écart médian −4,9 points). Sur 2022 → 11/2026, le meilleur fonds lisible (FCP BOA Actions) fait +191 % jusqu'au 13/11/2026. Sur la **même fenêtre**, le Composite prix fait +155 % et le TR estimé **environ +235 %** (+221 % si l'on prend le TR au 20/11, ce qui mélange les fenêtres). | medium [C] |
| 12 | **SGI** : 36 SGI participaient à la séance du 20/11/2026 (BOC). La liste de brvm.org compte **39 fiches et 37 noms distincts, sur 10 pages** (`?page=0` à `?page=9`), dont Hudson & Cie, Bridge Securities, EDC Investment Corporation, Atlantique Finance, BOA Capital Securities et CGF Bourse (« SGI de l'année » aux BRVM Awards 2026). **« Sika Capital » ne figure pas dans la liste consultée.** Sika Finance a reçu le prix de « Média financier de l'année ». | high [P] |
| 13 | **Méthodes de valorisation des analystes locaux** : notes de recherche **non lisibles** dans cette session. Nous proposons de **reproduire les 4 méthodes standard** (DDM/Gordon, PER relatif, P/B contre ROE par le revenu résiduel, actif net) comme **lignes de base**. Elles seront **testées** (IC, DSR) comme n'importe quel signal, pas crues sur parole. | low (pratiques) / high (méthodes) [B] |
| 14 | **Les livres de référence se traduisent en règles concrètes.** Graham fournit des filtres (PER ≤ 15, historique de dividendes) : au 20/11/2026, **8 titres sur 48** passent un filtre de Graham adapté. Damodaran fournit le coût des fonds propres par pays. Grinold-Kahn fournit l'alpha = σ × IC × score. López de Prado fournit la validation purgée et le DSR. Chan fournit la demi-vie de retour à la moyenne et la discipline de backtest. | high (règles) / [B] (ouvrages) |
| 15 | **Référentiel à battre (« hurdle »)** : le **Composite Total Return net de frais**, officiel depuis le 02/01/2025. Pour les années antérieures, on utilise la reconstruction prix + 0,88 × rendement. Le second repère est la **médiane des fonds actions du BOC**. Battre seulement le Composite prix **ne prouve rien** : c'est l'écart de 6 à 9 points de dividendes qu'il faut d'abord combler. | high |

---

## 2. Outils et sources de données pour la BRVM

### 2.1 Tableau comparatif

| Outil / source | Nature | Couverture | Accès, coût | Ajustement splits / dividendes | Verdict pour BRVM Alpha | Vérif., conf. |
|---|---|---|---|---|---|---|
| **BOC quotidien** (`brvm.org/sites/default/files/boc_AAAAMMJJ{_2,…}.pdf`) | officiel, PDF | toutes les actions, obligations, indices, **OPCVM (valeurs liquidatives)**, dividendes, PER, rendement net, ratios de marché. Chez nous : **2 581 BOC du 02/01/2017 au 20/11/2026** | gratuit (catalogue BRVM, code BR-013 « Produit gratuit ») | **aucun ajustement** ; mais le BOC publie, le jour d'une opération, un **cours de référence ajusté** (ex. SNTS 4 385 le 23/10/2026), ce qui permet un ajustement automatique fiable | **Source primaire n° 1** (déjà en place : `brvm_alpha/data/boc_download.py`, `boc_parser.py`) | [P] high |
| **Pages publiques de brvm.org** (`/fr/cours-actions/0`, `/fr/indices`, `/fr/capitalisations/0`, `/fr/flux-en-temps-reel`) | officiel, HTML | instantané du jour | gratuit | sans objet | instantané intrajournalier (déjà `brvm_alpha/data/live.py`) ; **ne pas** utiliser la colonne « Variation 31 décembre » de `/fr/indices`, incohérente avec le BOC (doc 01) | [P] high |
| **Services payants BRVM** (catalogue « produits et services à valeur ajoutée », version mars 2019) | officiel | BDFIN (base financière des sociétés cotées) ; CD de données historiques ; flux temps réel ou différé | BDFIN : **500 000 FCFA/an** (particulier), **2 000 000 FCFA/an** (autres), accès temporaire gratuit pour la recherche ; CD historique : **50 000 à 75 000 FCFA** (année N-1), **150 000 FCFA** (toutes années) ; redistribution temps réel : souscription **7 500 €/an** + service A1 (carnet d'ordres) **2 500 €/an** ; différé : souscription 5 000 €/an + B1 **1 250 €/an** ou B2 (fin de journée) **600 €/an** | inconnu | à envisager **uniquement** pour combler les années antérieures à 2017 et les comptes (BDFIN). **Tarifs de 2019, à reconfirmer** | [P] high (tarifs 2019) / low (tarifs actuels) |
| **Données historiques et de fin de journée « à la demande »** (`/fr/donnees-historiques`, `/fr/donnees-de-fin-de-journee`) | officiel | cours, indices, volumes et valeurs | sur demande (« Nous contacter ») | inconnu | voie **légale et propre** pour obtenir les années 1998-2016 | [P] high |
| **Bloomberg, FactSet, Refinitiv, SIX Financial Information** | rediffuseurs officiels (page `/fr/rediffuseurs-de-donnees`) | flux BRVM | abonnement terminal | politiques d'ajustement **non vérifiées** | utile pour un contrôle croisé. Tickers **non vérifiés** dans cette session : à confirmer sur le terminal | [P] high (liste) / low (détails) |
| **MSCI, S&P Dow Jones** | fournisseurs d'indices | indice MSCI « standalone » UEMOA créé le **10/06/2014** ; intégration aux indices MSCI et S&P DJ le **14/06/2014** ; **MSCI Frontier Markets depuis le 14/11/2016** | licence | indices TR disponibles chez ces fournisseurs (non vérifié) | repère international, pas une source de cours | [P] high (dates, page `/fr/historique`) |
| **Paquet R `BRVM`** (CRAN) | communautaire, MIT | fonctions `BRVM_get`, `BRVM_get1`, `BRVM_index`, `BRVM_cap`, `BRVM_tickers`, `BRVM_company_info`, `BRVM_plot`, `normality_test`, `stationarity_test`, etc. | gratuit | **aucun ajustement codé** ; dépend de la source aspirée | **à éviter** (section 2.2) | [P] high |
| **`brvmpy`** (PyPI) | communautaire, MIT | instantané du jour (actions, obligations, indices, volumes) par **Selenium + Chrome sans interface** | gratuit | sans objet (pas d'historique) | inutile pour nous | [P] high |
| **Sika Finance** (`sikafinance.com`) | média financier privé, « Média financier de l'année » aux BRVM Awards 2026 | historiques par titre et par indice. La consigne mentionne un téléchargement CSV : **non vérifiable ici** (403) | site public protégé par Cloudflare (doc 07) | inconnu | **pas d'aspiration, pas d'API interne**. À utiliser seulement par un accord ou une API officielle | [P] (prix) / [R] (403) ; CSV : low |
| **Richbourse** (`richbourse.com`) | site privé, contenus gratuits et premium | publications officielles relayées (sitemap de **6 325 URL**, 2017-2026), revue de presse, pages techniques | le `robots.txt` autorise les pages publiques et interdit `/api/` et `/site/premium` ; « garde anti-aspiration » (doc 07) | inconnu | relais d'actualités **avec modération** (doc 07) ; **pas** comme source de cours | [R] high |
| **African Markets**, **investing.com** | agrégateurs privés | cours, actualités | inaccessibles dans cette session | **non vérifié** | contrôle croisé manuel au mieux | low |
| **abourse.com** | site tiers | utilisé par `BRVM_boc()` du paquet R (requête POST sur `histoActionsJour.html`) | non testé | — | inutile : nous lisons le BOC à la source | [P] (code) |
| **Autres paquets Python** | — | **aucun** paquet trouvé parmi les noms testés : `brvm`, `pybrvm`, `brvm-py`, `brvm-api`, `brvm-scraper`, `brvm-data`, `brvm-stocks`, `brvmapi` (API JSON de PyPI). Recherche **non exhaustive** (pas de moteur de recherche) | — | — | — | [P] medium |

### 2.2 Le paquet R `BRVM` en détail (lecture du code source)

Le code a été lu sur le miroir GitHub officiel de CRAN : fichiers `DESCRIPTION`, `NAMESPACE`, `NEWS.md` et `MD5`, et sources `R/brvm-get.R`, `R/brvm_get1.R`, `R/brvm-index.R`, `R/brvm-boc.R`, `R/brvm-ticker.R` et `R/brvm-cap.R`.

| Élément | Constat | Conséquence |
|---|---|---|
| Version, date | 5.3.0, « Date/Publication: 2024-02-21 » ; auteurs : Sessie Koffi Frederic (mainteneur), Diakité Abdoul Oudouss, Steven Sanderson ; licence MIT | Le statut actuel sur CRAN (actif ou archivé) n'a **pas pu être vérifié** : `cran.r-project.org` est bloqué |
| `BRVM_get()` | télécharge `https://www.richbourse.com/common/mouvements/technique/<TICKER>/status/200`, puis cherche les **lignes 600 à 650** (ou 550 à 700) du HTML qui commencent par `data:` | **Extrêmement fragile** : il casse au moindre changement de page. Il aspire un site qui déclare une « garde anti-aspiration » |
| `BRVM_get1()` | requête JSON vers `https://www.sikafinance.com/api/general/GetHistos` (champs `ticker`, `datedeb`, `xperiod`), par tranches de **89 jours** ; `Period` vaut 0, 1, 5, 30, 91 ou 365 | **API interne non documentée** : son usage est **interdit par nos règles**. Le site est aujourd'hui derrière Cloudflare |
| `BRVM_index()`, `BRVM_cap()` | lecture HTML de `brvm.org/en/indices` et `brvm.org/en/capitalisations/0` | instantané seulement |
| `BRVM_boc()` | POST sur `http://www.abourse.com/histoActionsJour.html` | tiers non officiel |
| Liste des tickers | **46 symboles codés en dur** (avec un commentaire `#, "TTRC"`) ; `BRVM_tickers()` lit une **feuille Google Sheets** | Au 20/11/2026, il **manque BBGC, BICB et LNBB**. **SVOC**, radié (dernier BOC le 26/06/2025), est encore présent. Il y a donc des **biais de survie et de couverture** |
| Statistiques | `normality_test()` et `stationarity_test()` (via tseries, nortest, goftest, fBasics) | tests de base, sans correction des prix périmés |

**Verdict** : utile pour l'enseignement, **inutilisable comme socle d'une plate-forme sérieuse**. Notre pipeline BOC fait déjà mieux : source primaire, historique complet, dividendes, splits, OPCVM. (confiance high)

### 2.3 Pièges de qualité des données, mesurés sur nos BOC [C]

| # | Piège | Mesure (2017-2026) | Exemple daté | Règle de code |
|---|---|---|---|---|
| 1 | **Prix périmés** : cours affiché sans échange | Lignes titre×séance **sans volume** : 21,8 % (2017), 17,5 % (2018), 20,9 % (2019), **24,7 % (2020)**, 14,2 % (2021), 9,8 % (2022), 9,4 % (2023), 10,6 % (2024), 4,4 % (2025), **1,0 % (2026)**. Variation nulle : 44,4 % → 15,8 %. Par titre, le p90 de la part de séances sans échange vaut **73 %** en 2019-2020 et 0 % en 2026 | — | marquer `stale=True` si volume = 0 ; exclure du calcul des rendements journaliers et passer à l'hebdomadaire ou au mensuel (doc 04) |
| 2 | **Splits non ajustés** | **50 splits** (confiance high, panel du 22/11/2026 à 02:45 ; 47 dans la v1) : **vague de 2017-2019** (BICC ×10, BNBC ×20, CABC ×40, CFAC ×100, STAC ×100, PRSC ×64, SDSC ×50, NTLC ×20…) ; **2024** : BOAB ×2, BOABF ×2, BOAC ×2, BOAM ×1,5, BOAN ×1,6, BOAS ×1,5, SIBC ×2, SLBC ×10 ; **2026** : SNTS ×10 | SNTS : clôture 43 850 le 23/10/2026, cours de référence 4 385 ; une série brute affiche **−89,3 %** le 26/10/2026 | ajustement par le cours de référence du BOC (déjà `corporate_actions.parquet`) ; alerte si \|rendement\| > 7,5 % hors introduction en bourse (limite statique, doc 01) |
| 3 | **Origine de la vague de splits** | Décembre 2015 : le conseil d'administration de la BRVM impose, sous **2 ans**, un **flottant ≥ 20 %** et un flottant de **2 à 10 millions de titres**, « le cas échéant, au fractionnement de leurs titres ». Cours moyen visé : **5 385 FCFA** | Rapport annuel BRVM 2015 | prévoir d'autres vagues de splits liées à des changements de règles |
| 4 | **Dividendes absents des indices de prix** | TR − prix = **+7,88 points en 2025** et **+6,63 points en 2026** (au 20/11) ; contribution des dividendes au panier équipondéré : de 2,3 à 9,1 points par an | — | toujours comparer au **TR** ; utiliser `tr_ret` (dividendes nets) |
| 5 | **Trous de données** | 2021 : écarts de **50, 26, 16, 13 et 12 jours** entre deux BOC disponibles | 25/06/2021 (50 jours après le BOC précédent) | ne jamais calculer un rendement « d'une séance » à travers un trou de plus de 4 jours calendaires |
| 6 | **Biais de survie** | radiés : **TTRC** (dernier BOC le 05/10/2022), **SVOC** (26/06/2025) ; entrées : ORAC (12/2022), LNBB (12/2024), BICB (04/2025), BBGC (09/2026) | — | univers **à date** (point-in-time) reconstruit à partir des BOC, jamais à partir de la liste du jour |
| 7 | **Champs absurdes** | PER UNLC = 631, BNBC = 519 (bénéfices quasi nuls) ; PER d'ETIT incohérent en devise (doc 05) ; saut du PER moyen du marché de 11,9 à 9,1 fin avril 2022 (probablement la mise à jour des bénéfices annuels) | BOC 20/11/2026 | plafonner E/P et winsoriser ; traiter le PER comme un rapport « dernier bénéfice publié », **daté** |
| 8 | **Contradictions entre publications officielles** | Les rendements de 2012 sont **inversés** entre le rapport annuel 2013 (BRVM 10 +16,12 %, Composite +19,95 %) et l'« Année boursière 2013 » (+19,95 % et +16,12 %). Le tableau 3 du rapport 2015 (BRVM 10 : 158,49 → 184,04) tranche **en faveur du rapport annuel** | — | toujours **recalculer** à partir des niveaux, jamais recopier un pourcentage |
| 9 | **Définitions divergentes** | Valeur transigée 2025 : **351,29 Md FCFA** selon le communiqué BRVM, contre **264,9 Md** en sommant les valeurs « actions et droits » des BOC (2024 : 461,53 contre 165,5) | communiqué « 2025, la consolidation quinquennale » | ne pas mélanger les sources ; garder la définition BOC « Actions & Droits » |
| 10 | **Valeurs liquidatives d'OPCVM** | publication irrégulière, beaucoup de « ND ». Valeurs figées pendant des mois (FCP Atlantique Actions : dernière VL au 16/01/2025, encore affichée le 20/11/2026). Coquilles (date « 05/12/5025 » pour FCP BOA Actions). Changements de catégorie (FCP Actions Pharmacie : A en 2019, D en 2026) | BOC 20/11/2026 | VL acceptée seulement si elle date de 15 jours au plus ; dates hors bornes rejetées ; catégorie lue à la date |
| 11 | **Changements de base d'indice** | BRVM 10 → **BRVM 30** le 02/01/2023 ; nouveaux indices sectoriels en base 100 au 02/01/2025 ; TR en base 100 au 02/01/2025, affiché au BOC à partir de 2026 | — | chaîner les séries avec des facteurs de raccord, et documenter |
| 12 | **Exemples faux dans la documentation d'outils tiers** | `brvmpy` affiche un « BRVM 10 » et un Composite à 210,45 « le 2025-12-04 » (BOC : **353,29**) | README PyPI | ne jamais intégrer un outil tiers sans test de concordance avec le BOC |

---

## 3. Pratiques des analystes, des SGI et des gérants

### 3.1 Le paysage professionnel (faits primaires)

| Fait | Valeur | Date | Source | Conf. |
|---|---|---|---|---|
| Rôle des SGI | Seules habilitées à négocier les titres cotés pour le compte de tiers ; capital minimum **1 milliard FCFA** ; agrément par l'Instruction 4/97 du CREPMF | consulté le 22/11/2026 | https://www.brvm.org/fr/intervenants/sgi/tous | high |
| Nombre de SGI actives | « Nombre de SGI participantes » : **36** | 20/11/2026 | BOC n°222 | high |
| Liste brvm.org (**37 noms distincts, 39 fiches dont 2 doublons** : Oragroup Securities ×2 et Phoenix Capital Management ×2 ; la v1 avait omis la page `?page=9`) | ABCO Bourse ; AGI ; **Atlantique Finance** ; Attijari Securities West Africa ; **BOA Capital Securities** ; **Bridge Securities** ; BSIC Capital ; CIFA Bourse ; Everest Finance ; FGI ; GEK Capital ; Global Capital ; Image Finances Internationales ; Invictus Capital & Finance ; Matha Securities ; NSIA Finance ; Oragroup Securities ; Phoenix Capital Management ; SGI Africabourse ; SGI Bénin ; SGI BICI Bourse ; BIIC Financial Services ; BNI Finances ; **CGF Bourse** ; Coris Bourse ; **EDC Investment Corporation** ; **Hudson & Cie** ; Impaxis Securities ; Mac African ; SGI Mali ; SGI Niger ; SBIF ; SGI Togo ; Sirius Capital ; **Société Africaine d'Ingénierie et d'Intermédiation Financières (SA2IF)** ; **Société Générale Capital Securities West Africa** ; **United Capital for Africa** | consulté le 22/11/2026 | idem, pages `?page=0` à `?page=9` | high |
| « Sika Capital » | **absente** de la liste consultée. Sika Finance est un **média** | 22/11/2026 | idem ; BRVM Awards 2026 | high (absence dans la liste) / low (existence ailleurs) |
| Conseil en investissements boursiers | activité agréée (Instruction 6/97 du CREPMF) ; le conseiller « oriente les choix de ses clients sans se substituer à eux » | consulté le 22/11/2026 | https://www.brvm.org/fr/conseils-en-investissements-boursiers | high |
| BRVM Awards 2026 (année 2025) | SGI de l'année : **CGF Bourse** ; SGO de l'année : **NSIA Asset Management** ; OPC de l'année : SICAV Attijari Oblig ; média financier : **Sika Finance** ; arrangeur : Invictus Capital & Finance | 26-27/03/2026 | https://www.brvm.org/fr/mediacentre/actualites/brvm-awards-2026 | high |
| Lien SGI → gérant de fonds (BOC) | CGF Gestion → CGF Bourse ; BOA Asset Management → BOA Capital Securities ; Atlantic Asset Management → Atlantique Finance ; Coris Asset Management → Coris Bourse ; Bridge Asset Management → Bridge Securities ; Africabourse AM → Africabourse ; EDC Asset Management (FCP Ecobank Actions UEMOA) ; Enko Capital West Africa → EDC Investment Corporation (dépositaire) ; SGCAMWA → SGCSWA (FCP Sogevalor, Sogedynamique) ; NSIA AM → dépositaires BOA CI et UBA CI (Aurore Opportunités) ; Phoenix Africa AM (FCP PAM Actions) ; Attijari AM (Attijari Actions) | 20/11/2026 | BOC n°222, section OPCVM | high |

Note : la liste des SGO publiée sur brvm.org (`/fr/societes-de-gestion-d-opcvm`) confirme notamment Africabourse AM, Baobab AM, BNI Gestion, BRM AM, CGF Gestion, Coris AM et Ecobank AM (consultée le 22/11/2026).

### 3.2 Recherche publiée et méthodes de valorisation

**Ce qui n'a pas pu être trouvé (dit explicitement)** :
- les notes de recherche, les recommandations (achat/vente, cours cibles) et leur historique pour Hudson & Cie, Bridge Securities, EDC, Atlantique Finance, BOA Capital Securities, CGF Bourse ou toute autre SGI. Les domaines sont bloqués et le budget de recherche est épuisé ;
- **toute mesure publiée de la performance des recommandations des SGI** ;
- les notes d'information des introductions en bourse récentes (Orange CI 2022, BIIC 2025, Bridge Bank 2026, Coris Bank CI 2026), qui décriraient les méthodes de valorisation des arrangeurs. Le doc 07 signale la note de Coris Bank CI via richbourse, sans en extraire la méthode.

**Ce que le BOC impose de fait aux commentaires de marché** [P] : pour chaque titre, le BOC publie **le dernier dividende net et sa date, le rendement net et le PER**. Au niveau du marché, il publie le **PER moyen, le taux de rendement moyen, le « taux de rentabilité moyen » et une « prime de risque du marché »**, dont la définition n'est pas publiée. C'est la boîte à outils minimale de tout commentaire local : rendement et PER relatif.

**Méthodes standard de valorisation, à reproduire comme lignes de base** [B pour l'attribution ; formules standard, high] :

| Méthode | Formule | Données BRVM disponibles | Usage proposé | Piège BRVM |
|---|---|---|---|---|
| **DDM / Gordon** (Williams 1938 ; Gordon 1962) | P = D₁ / (k − g) ; rendement implicite k = D₀(1+g)/P + g | dividende net BOC, historique de 10 ans dans `dividends.parquet` | prix « juste » et **rendement espéré implicite** par titre | dividendes nets d'IRVM (taux variables selon les pays, doc 01) ; g à plafonner (choix interne : g ≤ 5 % nominal) |
| **PER relatif** | PER_titre / PER_secteur ou PER_marché | PER BOC et PER moyen sectoriel du BOC (7 secteurs) | signal value relatif | PER fondé sur le dernier bénéfice publié (décalage jusqu'à 16 mois) ; PER aberrants (UNLC, BNBC) |
| **P/B contre ROE** (revenu résiduel ; Penman) | P/B juste ≈ 1 + (ROE − k)/(k − g) | capitaux propres et ROE (docs 06a/06b, rapports des sociétés) | **banques** (17 des 48 titres sont des services financiers) | ROE gonflé par les revenus de titres d'État (doc 06a) |
| **Actif net (ANR)** | (actifs − dettes) / nombre d'actions | comptes annuels | holdings et sociétés à actifs réels (agro-industrie) | comptes publiés tard (44 % fin avril, doc 07) |
| **DCF** | Σ FCF_t / (1+k)^t + VT | rarement disponible (pas de prévisions publiques) | **non prioritaire** | dépend d'hypothèses invérifiables |

**Règle pour la plate-forme** : ces cinq méthodes forment une « **valeur de consensus des méthodes** ». Elle n'est **jamais** un signal en soi : elle entre comme un facteur value à tester (IC, PBO, DSR ; docs 03 et 04).

### 3.3 Fonds actions UEMOA contre les indices : ce que « battre le marché » veut dire [C]

**Méthode.** Nous avons parsé la section « OPCVM : fonds communs de placement et sociétés d'investissement à capital variable » des 2 581 BOC. Cela donne **168 fonds** : 79 diversifiés (D), 51 obligataires à moyen et long terme (OMLT), **20 actions (A)**, 10 obligataires à court terme (OCT) et quelques autres.
- **Rendement calendaire** d'un fonds : rapport des valeurs liquidatives (VL) en fin d'année. On retient la dernière VL connue au plus 15 jours avant le 31/12 de chaque borne ; pour 2026, la borne de fin est le 20/11.
- **Comparaison au Composite prix** : sur **exactement la même fenêtre de dates**.
- **TR estimé** : prix + 0,88 × rendement de début d'année jusqu'en 2024, puis TR officiel en 2025 et 2026.
- **[Correction du vérificateur]** Dans la v1, le TR était comparé sur l'**année civile** (TR au 20/11 pour 2026), alors que le prix l'était sur la fenêtre des VL. Cela favorise les fonds dont la dernière VL précède la baisse de fin novembre 2026 : le TR officiel passe de 207,92 le 13/11 à 198,63 le 20/11. **Règle à coder : le TR doit être comparé sur la même fenêtre que la VL.**
- Les rendements hors de l'intervalle [−80 % ; +200 %] sont exclus (aucun cas parmi les fonds actions).

**Biais à garder en tête** :
- (i) Les **FCP distribuants** voient leur VL baisser au versement (la BRVM publie des avis de paiement de dividendes de FCP SOGEVALOR et SOGEDYNAMIQUE). Leur performance est donc **sous-estimée**.
- (ii) Les VL sont **nettes de frais**. C'est le bon point de comparaison pour un investisseur.
- (iii) La catégorie « A » du BOC n'empêche pas une part de liquidités ou d'obligations.
- (iv) Le TR antérieur à 2025 est une **estimation**.

**Tableau 3.3.a : synthèse annuelle des fonds actions (catégorie A)**

| Année | Nb fonds | Médiane | Meilleur | Pire | Composite prix | TR (estimé ≤ 2024, officiel 2025-26) | Battent le prix (même fenêtre) | Battent le TR |
|---|---|---|---|---|---|---|---|---|
| 2017 | 5 | −16,5 % | −14,8 % | −23,7 % | −16,8 % | −11,6 % | 3 | 0 |
| 2018 | 8 | −15,3 % | +0,7 % | −29,8 % | −29,1 % | −24,4 % | 7 | 6 |
| 2019 | 8 | −6,2 % | +2,7 % | −19,3 % | −7,5 % | −1,2 % | 6 | 2 |
| 2020 | 9 | +1,1 % | +3,6 % | −7,6 % | −8,7 % | +0,2 % | 8 | 5 |
| 2021 | 9 | +35,3 % | +69,2 % | +26,8 % | +39,1 % | +46,9 % | 4 | 3 |
| 2022 | 7 | +4,1 % | +9,8 % | −6,4 % | +0,5 % | +5,7 % | 5 | 1 |
| 2023 | 11 | +1,6 % | +23,7 % | −12,1 % | +5,4 % | +12,0 % | 4 | 2 |
| 2024 | 12 | +18,2 % | +33,1 % | +7,9 % | +28,9 % | +36,3 % | 2 | **0** |
| 2025 | 12 | +32,1 % | +48,3 % | +7,0 % | +25,3 % | +33,1 % | 8 | 6 |
| 2026 (au 20/11) | 12 | +36,2 % | +54,7 % | +17,5 % | +42,6 % | +49,2 % | 1 | 1 en année civile ; **0 sur la même fenêtre** (vérif.) |
| **Total** | **93 années-fonds** | — | — | — | — | — | **48 (52 %)** ; reproduction : 52 (56 %) | **26 (28 %)** ; reproduction : 27 (29 %) |

Note de vérification : la reproduction indépendante retrouve **93 années-fonds**, mais avec une composition annuelle un peu différente (2017 : 6 ; 2018 : 9 ; 2019 : 9 ; 2020 : 10 ; 2025 : 10 ; 2026 : 10). La catégorie y est lue à la date de fin, et FCP Walo et FCP BNDE Valeurs sortent de la catégorie A en 2025-2026. Les valeurs ponctuelles revérifiées sur les BOC sont toutes exactes : AAM 2026 +36,7 %, BOA Actions 2026 +49,0 %, Placement Croissance 2026 +32,5 %, Aurore Opportunités 2026 +41,8 % et 2025 +23,2 %, Attijari Actions 2026 +54,7 %. **Le message (« battre le TR est rare, environ 3 années-fonds sur 10 ») est robuste ; les décimales ne le sont pas.**

**Tableau 3.3.b : rendements calendaires par fonds actions (VL, %)** ; « — » = VL absente ou trop ancienne aux bornes

| Fonds (gérant ; SGI ou dépositaire) | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|---|
| FCP AAM Épargne Action (Africabourse AM ; Africabourse) | — | −23,2 | −12,5 | +3,6 | +69,2 | +9,8 | +2,0 | +15,1 | +45,9 | +36,7 |
| FCP BOA Actions (BOA AM ; BOA Capital Securities) | — | — | — | −1,7 | +35,3 | +4,3 | +14,2 | +27,4 | +28,7 | +49,0 |
| FCP Coris Actions (Coris AM ; Coris Bourse) | — | — | — | — | +49,5 | −6,4 | +8,0 | +9,5 | +36,6 | +39,8 |
| FCP Placement Croissance (CGF Gestion ; CGF Bourse) | −14,8 | −16,7 | −4,4 | +1,1 | — | — | −3,6 | +9,8 | +27,8 | +32,5 |
| FCP Atlantique Actions (Atlantic AM ; Atlantique Finance) | — | — | — | — | +26,8 | −0,3 | +23,7 | +22,0 | — | — |
| Aurore Opportunités (NSIA AM ; UBA CI) | — | — | — | — | — | +5,2 | +1,6 | +22,8 | +23,2 | +41,8 |
| Attijari Actions (Attijari AM) | — | −13,8 | — | — | +33,9 | +4,1 | — | — | +36,2 | +54,7 |
| FCP SOAGA Épargne Actions (SOAGA) | — | — | — | — | +49,5 | +4,1 | +0,2 | +7,9 | +19,9 | +36,6 |
| FCP PAM Actions (Phoenix Africa AM) | — | — | −19,3 | −5,9 | — | — | — | +21,2 | +44,8 | +33,7 |
| FCP Sogevalor (SGCAMWA ; SGCSWA) — distribuant | −23,7 | −25,1 | −11,1 | −7,6 | +32,6 | — | — | +24,9 | — | — |
| FCP Sogedynamique (SGCAMWA ; SGCSWA) | −20,2 | −29,8 | −6,2 | −6,6 | +45,7 | — | — | +13,4 | — | — |
| FCP Valoris (Africam ; SBIF) | −16,5 | −12,2 | −6,2 | +3,4 | +30,8 | — | — | — | +48,3 | — |
| FCP Ecobank Actions UEMOA (EDC AM) | −15,4 | — | — | — | — | — | +8,6 | — | — | — |
| FCP-1 Opti Placement (OAM ; SGI Togo) | — | — | — | — | — | — | −8,6 | +33,1 | — | — |
| FCP BAM Wurus (Baobab AM) | — | — | — | — | — | — | — | — | +35,6 | +35,9 |
| FCP SOAGA Épargne Dynamique (SOAGA) | — | — | — | — | — | — | — | — | — | +34,6 |
| FCP BNDE Valeurs (catégorie changeante) | — | +0,3 | +1,4 | +1,6 | — | — | +0,7 | +8,3 | +7,5 | +19,9 |
| FCP Al Baraka | — | +0,7 | +2,7 | +2,8 | — | — | −12,1 | — | — | — |
| FCP Walo | — | — | — | — | — | — | — | — | +7,0 | +17,5 |
| **Composite prix (année civile)** | −16,8 | −29,1 | −7,5 | −8,7 | +39,1 | +0,5 | +5,4 | +28,9 | +25,3 | +42,6 |

\* 2026 : jusqu'au 20/11 (ou dernière VL disponible avant). Les performances de FCP BNDE Valeurs, FCP Al Baraka et FCP Walo ressemblent à celles de fonds peu exposés aux actions, malgré la catégorie affichée. Celle de FCP Atlantique Actions en 2023 (+23,7 % contre +6,7 % pour le Composite sur la même fenêtre) est à vérifier, car sa VL est parfois restée figée longtemps.

**Tableau 3.3.c : cumuls longs (VL disponibles aux deux bornes)**

| Fonds | Fenêtre | Fonds | Composite prix (même fenêtre) | Commentaire |
|---|---|---|---|---|
| FCP BOA Actions | 31/12/2021 → 13/11/2026 | **+191,1 %** (24,5 %/an) | +155,1 % (21,2 %/an) | meilleur cumul lisible ; reste **sous** le TR estimé : environ **+235 % sur la même fenêtre** (au 13/11), +221 % au 20/11 |
| FCP AAM Épargne Action | 30/12/2021 → 19/11/2026 | +157,0 % (21,3 %/an) | +145,0 % | bat le prix, pas le TR |
| FCP Sogevalor (distribuant) | 29/12/2021 → 19/11/2026 | +140,3 % | +147,8 % | VL sous-estimée par les distributions |
| Aurore Opportunités | 28/12/2021 → 19/11/2026 | +129,4 % | +148,0 % | — |
| FCP Coris Actions | 30/12/2021 → 18/11/2026 | +111,5 % | +148,4 % | — |
| FCP Sogedynamique | 29/12/2021 → 19/11/2026 | +97,6 % | +147,8 % | — |
| FCP SOAGA Épargne Actions | 31/12/2021 → 19/11/2026 | +84,4 % | +144,2 % | — |
| FCP Ecobank Actions UEMOA | 28/12/2016 → 04/11/2026 | +94,8 % (7,0 %/an) | +80,9 % (6,2 %/an) | traverse tout le marché baissier |
| FCP Sogevalor | 30/12/2016 → 19/11/2026 | +49,5 % (4,2 %/an) | +69,1 % (5,5 %/an) | — |
| FCP Placement Croissance | 30/12/2016 → 19/11/2026 | +45,5 % (3,9 %/an) | +69,1 % | — |
| Repère : Composite **TR estimé** | 2017 → 11/2026 | — | **≈ +211 % (≈ 12,2 %/an)** | voir section 4.5 |

**Ce qu'il faut en retenir** (medium) :
1. **Battre le Composite prix est un pile ou face** pour un gérant professionnel : de 52 à 56 % des années-fonds y parviennent.
2. **Battre le Composite TR est rare** : de 28 à 30 % des années-fonds. Aucun fonds n'y est parvenu en 2024. **Aucun non plus en 2026, sur la même fenêtre.** Attijari Actions fait +54,7 % du 26/12/2025 au 13/11/2026, contre environ +58 % pour le TR sur cette fenêtre. Elle ne « bat » le TR qu'en comparaison avec le TR au 20/11 (+49,2 %), ce qui était une erreur de fenêtre dans la v1.
3. **Profil défensif** : en baisse (2017-2020), 24 années-fonds sur 30 battent le prix, avec un écart médian de +3,9 points. En hausse (2021, 2024, 2025, 2026), 15 sur 45 y parviennent, avec un écart médian de −4,9 points. Ce profil s'explique très probablement par les liquidités, les contraintes de liquidité et les règles de dispersion.
4. **Le prix de SGO de l'année n'implique pas la surperformance** : Aurore Opportunités (NSIA AM, SGO de l'année 2025) fait +23,2 % en 2025, contre +25,3 % pour le Composite prix et +33,1 % pour le TR.
5. **Seuil pour BRVM Alpha** : pour être « le meilleur », il faut **battre le TR après frais, sur plusieurs années, en hausse comme en baisse**. Aucun acteur local observable ne le fait de façon régulière.

---

## 4. Performance historique des indices BRVM (2010-2026)

### 4.1 Rendements annuels

| Année | Composite (clôture) | Var. Composite | BRVM 10 (≤ 2022) / **BRVM 30** (≥ 2023) | Prestige | Principal | Composite TR | Source | Conf. |
|---|---|---|---|---|---|---|---|---|
| 2010 | ≈ 159,10 (lecture incertaine) | n.d. (clôture 2009 non trouvée) | ≈ 182,96 (lecture incertaine) | — | — | — | RA 2015, tableau 3 (image basse résolution) | low |
| 2011 | 138,88 (déduit) | ≈ −12,7 % | 158,49 (déduit) ; ≈ −13,4 % | — | — | — | déduit de 2012 (RA 2013) ; cohérent avec RA 2015 | medium (niveaux) / low (var.) |
| 2012 | 166,58 | **+19,95 %** | 184,04 ; +16,12 % | — | — | — | RA 2013 (l'Année boursière 2013 inverse les deux chiffres) | high |
| 2013 | 232,02 | **+39,28 %** | 246,34 ; +33,85 % | — | — | — | RA 2013 | high |
| 2014 | 258,08 | **+11,23 %** | 267,53 ; +8,60 % | — | — | — | RA 2014 (record de l'année : 258,54 le 22/09/2014) | high |
| 2015 | 303,93 | **+17,77 %** | 290,38 ; +8,54 % | — | — | — | RA 2015 | high |
| 2016 | 292,17 | **−3,87 %** | 261,95 ; −9,79 % | — | — | — | RA 2016 | high |
| 2017 | 243,06 | **−16,81 %** | 219,65 ; −16,15 % | — | — | — | BOC 29/12/2017 | high |
| 2018 | 172,24 | **−29,14 %** | 154,36 ; −29,72 % | — | — | — | BOC 31/12/2018 | high |
| 2019 | 159,24 | **−7,55 %** | 149,11 ; −3,40 % | — | — | — | BOC 31/12/2019 | high |
| 2020 | 145,37 | **−8,71 %** | 130,88 ; −12,23 % | — | — | — | BOC 31/12/2020 | high |
| 2021 | 202,28 | **+39,15 %** | 153,51 ; +17,29 % | — | — | — | BOC 31/12/2021 ; communiqué BRVM | high |
| 2022 | 203,22 | **+0,46 %** | 165,58 ; +7,86 % | — | — | — | BOC 30/12/2022 ; communiqué | high |
| 2023 | 214,15 | **+5,38 %** | **107,85 ; +7,85 %** (base 100 au 02/01/2023) | 101,47 ; +1,47 % | 103,96 ; +3,96 % | — | BOC 29/12/2023 ; communiqué | high |
| 2024 | 276,02 | **+28,89 %** | 138,74 ; +28,64 % | 114,84 ; +13,18 % | 138,11 ; +32,85 % | — | BOC 31/12/2024 ; communiqué | high |
| 2025 | 345,75 | **+25,26 %** | 166,24 ; +19,82 % | 144,25 ; +25,61 % | 217,65 ; +57,59 % | **≈ +33,1 %** (133,14 ; base 100 au 02/01/2025) | BOC 31/12/2025 ; communiqué ; TR déduit du BOC 2026 (198,63 / 1,4919) | high |
| 2026 (au 20/11) | 492,89 | **+42,56 %** | 238,73 ; +43,61 % | 186,61 ; +29,37 % | 337,96 ; +55,28 % | **198,63 ; +49,19 %** | BOC n°222 du 20/11/2026 | high |

Contrôles :
- Le communiqué BRVM de fin 2025 confirme mot pour mot la série 2021-2025 (+39,15 %, +0,46 %, +5,38 %, +28,89 %, +25,26 %) et le cumul **+99,15 %**, de 145,37 à 345,75.
- Nos niveaux de fin d'année recalculés sur les BOC coïncident avec les variations annuelles publiées au centième près (calcul [C]).

**Cumuls et taux annuels moyens (prix)** [D] :
- du 30/12/2011 au 20/11/2026 : 138,88 → 492,89, soit **+8,9 %/an** ;
- du 30/12/2016 au 20/11/2026 : 292,17 → 492,89, soit **+5,4 %/an** ;
- du 31/12/2021 au 20/11/2026 : **+20,0 %/an** (+143,7 % au total).

**Panier équipondéré (EW) des actions, calculé sur les BOC [C]** (non investissable pour les petites capitalisations peu liquides ; repère de dispersion) :

| | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|---|
| EW prix | −25,3 % | −16,6 % | −15,5 % | +3,8 % | +84,1 % | +4,9 % | +0,9 % | +16,7 % | +65,4 % | +46,6 % |
| EW rendement total (dividendes nets) | −23,1 % | −13,4 % | −11,3 % | +8,4 % | +93,2 % | +10,0 % | +6,5 % | +23,4 % | +74,4 % | +51,6 % |

\* au 20/11. Confiance medium : 9 rendements journaliers supérieurs à 50 % en valeur absolue (erreurs probables de parsing) ont été exclus, et 2021 contient des trous de données.

### 4.2 Volatilité annualisée du Composite [C]

| Période | Journalière × √252 | Hebdomadaire × √52 | **Mensuelle × √12** |
|---|---|---|---|
| 2017-2026 | 11,0 % | 12,0 % (11,8 % en recalcul ; sensible au traitement des semaines sans BOC de 2021) | **15,5 %** |
| 2017-2020 (baissier) | 12,5 % | 12,7 % | **16,7 %** |
| 2021-2026 | 9,7 % | 11,0 % | **13,2 %** |
| 2022-2026 | 9,6 % | 10,0 % | **13,0 %** |

| Année | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| Vol. journalière annualisée | 14,9 % | 10,5 % | 11,1 % | 12,9 % | 10,6 %† | 9,1 % | 8,1 % | 8,0 % | 9,6 % | 12,6 % |
| Vol. mensuelle annualisée | 13,9 % | 16,0 % | 19,7 % | 17,3 % | 14,1 % | 12,2 % | 7,8 % | 7,8 % | 8,9 % | **22,1 %** |
| Pire mois | −4,6 % | −8,6 % | −7,9 % | −8,2 % | −7,9 % | −4,6 % | −2,7 % | −3,0 % | −1,7 % | −7,8 % |
| Meilleur mois | +8,8 % | +3,6 % | +12,4 % | +11,1 % | +7,4 % | +7,5 % | +4,3 % | +6,3 % | +5,8 % | +14,5 % |

† 2021 : 146 rendements journaliers seulement (trous de données).

Autocorrélation d'ordre 1 du Composite (2017-2026) : 0,01 en journalier, **0,18 en hebdomadaire**, 0,12 à 0,13 en mensuel (0,12 en recalcul). Le rapport entre volatilité mensuelle et journalière (15,5 / 11,0 = 1,41) est la signature du **trading peu fréquent** (doc 04). **2026 est l'année la plus volatile de l'échantillon en mensuel (22,1 %)** : hausse de +14,5 % puis baisse de −7,8 % autour du sommet de septembre.

Pires séances : −4,31 % (18/05/2020), −3,66 % (23/09/2026), −3,14 % (26/05/2017), −2,80 % (10/05/2019), −2,76 % (31/12/2018). Meilleures : +3,55 % (30/10/2020), +3,54 % (24/12/2019), +3,49 % (24/05/2017).

### 4.3 Drawdowns

| Épisode | Sommet | Creux | Baisse | Durée de baisse | Retour au sommet | Source |
|---|---|---|---|---|---|---|
| **Marché baissier 2016-2020** (depuis la clôture 2015) | 303,93 (31/12/2015) | **122,19 (26/10/2020)** | **−59,8 %** | environ 4 ans et 10 mois | **10/06/2025** (304,34) | RA 2015 + BOC [P/C] |
| idem, sommet observé dans nos BOC | 290,44 (01/03/2017) | 122,19 (26/10/2020) | **−57,9 %** | 1 334 jours | 20/02/2025 | BOC [C] |
| Rendement total **équipondéré** | 03/01/2017 | 06/04/2020 | **−47,9 %** | 3,3 ans | 08/09/2021 | BOC [C] |
| **Correction en cours** | **555,90 (14/09/2026, plus haut historique)** | 492,89 au 20/11/2026 (pas encore de creux confirmé) | **−11,3 %** | 66 jours à ce stade | pas encore | BOC [C] |
| Correction 2026 (T1) | 03/03/2026 | 16/04/2026 | −5,1 % | 43 jours | 21/05/2026 | BOC [C] |
| Correction 2025 | 21/02/2025 | 18/04/2025 | −4,2 % | 53 jours | 09/05/2025 | BOC [C] |

Plus forte baisse intra-annuelle du Composite : 2017 −24,4 % ; **2018 −33,0 %** ; 2019 −22,4 % ; 2020 −22,4 % ; 2021 −7,6 % ; 2022 −13,9 % ; 2023 −6,2 % ; 2024 −3,4 % ; 2025 −4,2 % ; 2026 −11,3 % [C]. Ces valeurs sont reproduites exactement, en partant de la première séance de l'année. Si l'on part de la clôture de l'année précédente, on obtient 2017 −24,8 %, 2020 −23,3 % et 2021 −10,0 % : la convention doit être fixée dans le code.

Rendements glissants sur 12 mois (fins de mois, 2017-2026, 108 fenêtres) : min **−29,1 %**, médiane +5,2 à +5,4 %, max **+69,4 %** ; **43 %** des fenêtres sont négatives (0,435 en recalcul) [C].

Leçon pour le risque : un investisseur entré fin 2015 a attendu **environ 9 ans et demi** pour retrouver son capital **en prix**. Dividendes réinvestis, le rattrapage a été bien plus rapide (2021 pour le panier équipondéré). Cela confirme encore que le **TR est le seul repère pertinent**, et qu'une plate-forme sérieuse doit prévoir des **scénarios de baisse de 50 à 60 % sur 3 à 5 ans**.

### 4.4 Rendement de dividende et valorisation du marché (BOC) [C]

| Année | Taux de rendement moyen du marché au début de l'année | Taux de rendement moyen médian de l'année | PER moyen médian | PER moyen en fin d'année | Contribution des dividendes (EW, points) | Détachements détectés | Rendement médian au détachement |
|---|---|---|---|---|---|---|---|
| 2017 | 5,87 %‡ | 5,67 %‡ | 19,9 | 17,3 | 2,3 | 30 | 3,9 % |
| 2018 | 5,38 % | 6,78 % | 13,3 | 11,6 | 3,2 | 32 | 5,6 % |
| 2019 | 7,27 % | 8,82 % | 10,1 | 10,3 | 4,2 | 31 | 7,5 % |
| 2020 | 10,11 % | 10,25 % | 9,6 | 10,0 | 4,6 | 24 | 9,4 % |
| 2021 | 8,75 % | 7,64 % | 11,2 | 13,7 | 9,1 | 31 | 8,1 % |
| 2022 | 6,01 % | 6,23 % | 8,3 | 8,0 | 5,1 | 31 | 7,3 % |
| 2023 | 7,51 % | 8,08 % | 9,3 | 10,6 | 5,7 | 32 | 7,6 % |
| 2024 | 8,44 % | 8,50 % | 10,0 | 10,9 | 6,7 | 34 | 7,6 % |
| 2025 | 8,97 % | 7,57 % | 11,7 | 11,9 | 9,0 | 32 | 6,6 % |
| 2026 | 7,57 % | 6,41 % | 14,1 | **15,79** (20/11) | 5,0 (au 20/11) | 35 | 4,3 % |

‡ 2017 : indicateur présent dans 3 % des BOC seulement.

Lecture : sur 2018-2026, le rendement moyen tourne autour de **7,8 %** (moyenne des médianes annuelles : 7,81 % en recalcul). Au 20/11/2026, le marché est **cher**, à son plus haut depuis **mai 2018** hors valeurs aberrantes, mais **pas le plus cher de la décennie**. [Correction du vérificateur : l'affirmation de la v1 est réfutée.] Le PER moyen du BOC dépassait 15,79 dans **228 séances sur 238 en 2017** (médiane 19,9 ; 23,83 le 03/01/2017) et dans **89 séances de janvier à mai 2018**. En 2026, il a culminé à **18,43 le 14/09/2026**. Deux séries de valeurs sont aberrantes et à exclure : 22,01 le 17/02/2021, et 16,6 à 40,9 du 17/07 au 26/08/2025. Au 20/11/2026 : PER 15,79 hors Unilever, rendement 7,12 %, « prime de risque du marché » publiée de **0,58** contre 2,65 fin 2025. Cela ne prédit pas mécaniquement une baisse : le doc 05 trouve une corrélation **négative** entre cette prime et les rendements futurs sur 2021-2026. C'est une information de **dosage du risque**, pas de timing.

### 4.5 Le référentiel à battre

| Période | Composite prix | Composite TR (estimé ≤ 2024 ; officiel 2025-26) | Écart dû aux dividendes |
|---|---|---|---|
| 30/12/2016 → 20/11/2026 | +68,7 % (**5,4 %/an**) | ≈ +211 % (**≈ 12,2 %/an**) | ≈ 6,8 points/an |
| 31/12/2021 → 20/11/2026 | +143,7 % (20,0 %/an) | ≈ +221 % (≈ 26,9 %/an) | ≈ 6,9 points/an |
| 2025 | +25,26 % | +33,1 % (officiel) | 7,9 points |
| 2026 (au 20/11) | +42,56 % | +49,19 % (officiel) | 6,6 points |

**Estimation du TR avant 2025** [C/D] : TR_a ≈ P_a + k × Y_{a−1}. Ici, Y_{a−1} est le « taux de rendement moyen du marché » au dernier BOC de l'année précédente, et **k = 0,88**, calibré sur 2025 (0,878) et 2026 (0,876).
- TR estimés : 2017 −11,6 % ; 2018 −24,4 % ; 2019 −1,2 % ; 2020 +0,2 % ; 2021 +46,9 % ; 2022 +5,7 % ; 2023 +12,0 % ; 2024 +36,3 %.
- Confiance **medium** : deux points de calibration seulement, tous deux en marché haussier. Les entrées sont revérifiées sur les BOC : k₂₀₂₅ = (33,14 − 25,26) / 8,97 = 0,878 ; k₂₀₂₆ = (49,19 − 42,56) / 7,57 = 0,876.
- **[NON VÉRIFIÉ] pour 2017** : aucun BOC de fin 2016 ne publie le rendement moyen du marché. La valeur Y = 5,87 % utilisée est la **première valeur observée, le 19/12/2017**, ce qui revient à anticiper sur l'année. Le TR 2017 estimé (−11,6 %) est donc une approximation. En années de baisse, les coupes de dividendes peuvent rendre k < 0,88.
- La reconstruction exacte (dividendes × capitalisations, sur le modèle du TR officiel vérifié dans le doc 01) reste à faire (section 7).

---

## 5. Livres et ressources de référence : ce qu'il faut en retenir pour la BRVM

Les ouvrages sont des références **classiques, non relues dans cette session [B]**. Les règles et formules citées sont standard. **[NON VÉRIFIÉ]** : la vérification adversariale du 22/11/2026 n'a pas pu les contrôler non plus (budget de recherche web épuisé ; `doi.org` et `api.crossref.org` refusés par le réseau). Les critères de Graham listés ci-dessous, notamment « dividendes ininterrompus depuis 20 ans » et « PER × P/B ≤ 22,5 », sont donc **non vérifiés dans le texte**. Pour trois articles, le doc 04 fournit volume, pages et URL [R] : Harvey, Liu & Zhu 2016 (*RFS* 29(1), 5-68), Lo 2002 (*FAJ* 58(4), 36-52), Clarke, de Silva & Thorley 2002 (*FAJ* 58(5), 48-66). La colonne « Application » est **notre** traduction, chiffrée sur les données du projet.

### 5.1 Valorisation fondamentale

| Référence | Idée clé | Application concrète BRVM |
|---|---|---|
| **B. Graham & D. Dodd, *Security Analysis*** (McGraw-Hill, 1934 ; 6ᵉ éd. 2008) [B] | analyse des comptes, **marge de sécurité**, normalisation des bénéfices sur plusieurs années | utiliser un **PER sur bénéfice moyen de 3 ans** plutôt que le PER BOC (dernier exercice) ; décote exigée plus forte pour les pays à risque de saut politique (doc 05) |
| **B. Graham, *The Intelligent Investor*** (1949 ; éd. révisée 1973 ; commentaires de J. Zweig, 2003) [B] | critères de l'investisseur défensif : taille suffisante, situation financière solide, bénéfices positifs sur 10 ans, **dividendes ininterrompus depuis 20 ans**, croissance du BPA, **PER ≤ 15** (sur 3 ans), **P/B ≤ 1,5** ou PER × P/B ≤ 22,5 | **filtre adapté sur le BOC du 20/11/2026** : PER ≤ 15, rendement net ≥ 5 % et dividende versé au moins 8 années sur 10 (2017-2026). **8 titres sur 48 passent** : SOGC (rdt 6,60 %, PER 13,1), PALC (5,93 %, 7,4), SGBC (5,93 %, 11,9), BOAS (5,84 %, 12,7), CABC (5,59 %, 11,2), BOAC (5,43 %, 12,4), ECOC (5,28 %, 12,8), ONTBF (5,18 %, 13,1). **Illustration, pas une recommandation** : le critère P/B n'est pas appliqué, faute de capitaux propres dans le BOC [C] |
| **A. Damodaran, *Investment Valuation*** (Wiley, 3ᵉ éd. 2012) ; *Narrative and Numbers* (2017) ; *The Little Book of Valuation* (2011) [B] | coût des fonds propres = r_f + β × ERP mature + λ × CRP ; **CRP = default spread × (σ_actions / σ_obligations)** ; cohérence de devise (r_f et flux dans la même monnaie) | en FCFA : **r_f = 5,75 %** (taux de référence BOC, doc 05) ; ERP_BRVM par défaut 4,0 % (doc 05) ; multiplicateur m = 1,5 (hypothèse, doc 05). Exemple : β = 0,8 et λ = 1 avec CRP relatif CI = 0 pour une société ivoirienne → k ≈ 5,75 + 0,8 × 4,0 = **8,95 %** ; avec un rendement net de 7 % et g = 2 %, Gordon donne k_implicite ≈ 7,0 × 1,02 + 2 = **9,1 %** [D] |
| **A. Damodaran, mises à jour annuelles** : « Equity Risk Premiums » (SSRN) et table des primes pays (`pages.stern.nyu.edu/~adamodar/`) [B] | primes implicites calculées à partir des prix (pas des moyennes historiques) | **prime implicite BRVM** = rendement des dividendes × (1 + g) + g − r_f, recalculée chaque jour sur le BOC ; ne **jamais** utiliser une moyenne historique de rendements (doc 04 : James-Stein c = 0) |
| **T. Koller, M. Goedhart, D. Wessels, *Valuation*** (McKinsey, Wiley) [B] | valeur = f(ROIC − WACC, croissance) | la croissance ne crée de la valeur que si ROE > k : rejeter les « croissances » de sociétés dont le ROE est inférieur à 9 % |
| **S. Penman, *Financial Statement Analysis and Security Valuation*** [B] | **revenu résiduel** ; P/B juste ≈ 1 + (ROE − k)/(k − g) | **banques** (17 titres sur 48) : avec ROE = 20 %, k = 10 % et g = 3 %, P/B juste ≈ 2,4. Un P/B de 4,0 (doc 06a) suppose donc un ROE durable bien supérieur [D] |
| **J. B. Williams, *The Theory of Investment Value*** (1938) ; **M. Gordon** (1962) [B] | valeur = actualisation des dividendes | adapté à un marché où le dividende représente **la moitié du rendement total** (section 4.5) |

### 5.2 Gestion quantitative et rigueur statistique

| Référence | Idée clé | Application concrète BRVM |
|---|---|---|
| **R. Grinold & R. Kahn, *Active Portfolio Management*** (McGraw-Hill, 2ᵉ éd. 2000) [B] ; Grinold (1989, 1994), voir doc 04 | **IR = IC × √BR** ; **α = σ_résiduelle × IC × score** | avec environ 45 titres et un rééquilibrage mensuel, BR ≈ 45 × 12 / (corrélation des signaux). Un IC de 0,05 donne un IR théorique de 0,05 × √540 ≈ **1,16** avant le coefficient de transfert et les coûts [D]. Avec un coefficient de transfert de 0,3 (contraintes long-only et liquidité, hypothèse), l'IR tombe à **0,35** |
| **R. Clarke, H. de Silva, S. Thorley (2002)**, « Portfolio Constraints and the Fundamental Law of Active Management », *Financial Analysts Journal* [B] | **IR = TC × IC × √BR** ; le coefficient de transfert (TC) mesure la perte due aux contraintes | sur la BRVM, l'interdiction de la vente à découvert et la liquidité font chuter le TC : il faut **mesurer TC** dans le backtest (corrélation entre poids actifs et alphas) |
| **M. López de Prado, *Advances in Financial Machine Learning*** (Wiley, 2018) ; *Machine Learning for Asset Managers* (Cambridge UP, 2020) [B ; ch. 7 et 12 attestés au doc 04] | validation croisée purgée avec embargo, CPCV, PBO, **Deflated Sharpe**, HRP, triple barrière, méta-étiquetage, pondération des observations par unicité | purge = horizon du label, **embargo ≥ 21 séances** ; PBO < 0,2 et DSR > 0,95 exigés (doc 04). Méta-étiquetage : modèle n° 1 = règle fondamentale (section 3.2), modèle n° 2 = décider d'agir ou non selon la liquidité et le régime |
| **E. Chan, *Quantitative Trading*** (Wiley, 2008 ; 2ᵉ éd. 2021) ; *Algorithmic Trading* (Wiley, 2013) [B] | test ADF, exposant de Hurst, **demi-vie** de retour à la moyenne (λ dans Δy = λ·y + ε, demi-vie = −ln 2 / λ), Kelly, pièges de backtest (biais d'anticipation, de survie, coûts) | estimer la demi-vie **par titre en hebdomadaire** (les prix périmés biaisent le journalier). Ne trader le retour à la moyenne que si la demi-vie est inférieure à environ 8 semaines **et** que l'écart attendu dépasse les coûts aller-retour (1,7 à 2,8 %, doc 03) |
| **A. Lo (2002)**, « The Statistics of Sharpe Ratios », *FAJ* [B, utilisé au doc 04] ; **Lo & MacKinlay, *A Non-Random Walk Down Wall Street*** (Princeton UP, 1999) [B] | Sharpe corrigé de l'autocorrélation ; ratios de variance | **ne jamais annualiser un Sharpe journalier BRVM par √252** (surestimation de 30 % pour le Composite, de 72 % pour le panier EW, doc 04) |
| **C. Harvey, Y. Liu, H. Zhu (2016)**, « … and the Cross-Section of Expected Returns », *Review of Financial Studies* [B] | seuil **t > 3** pour un nouveau facteur | appliquer ce seuil à toute découverte « propre à la BRVM » |
| **A. Ilmanen, *Expected Returns*** (Wiley, 2011) [B] | les rendements espérés viennent des **rendements de portage** (dividendes, carry) et des primes de risque, pas des performances passées | à la BRVM, la base du rendement espéré = **rendement des dividendes (≈ 7 %) + croissance**. Les « paris » de prix viennent ensuite |
| **L. H. Pedersen, *Efficiently Inefficient*** (Princeton UP, 2015) [B] | les marchés sont « efficacement inefficaces » : l'alpha rémunère des coûts et des risques réels | l'alpha BRVM, s'il existe, rémunère surtout la **liquidité** et l'**information lente** : il faut donc le mesurer **après coûts et capacité** |
| **P. Tetlock & D. Gardner, *Superforecasting*** (Crown, 2015) ; **D. Kahneman, *Thinking, Fast and Slow*** (2011) ; **N. Taleb, *Fooled by Randomness*** (2001) [B] | calibration, score de Brier, biais cognitifs, rôle du hasard | publier chaque prévision avec une **probabilité** et la noter (Brier). Afficher dans l'interface « probabilité d'une année négative » plutôt qu'un « gain garanti » |
| **E. Thorp ; J. Kelly (1956)** [B, voir doc 04] | dimensionnement par croissance logarithmique | **¼ Kelly, plafond ½**, sur un alpha **rétréci** (doc 04) |

### 5.3 Spécificités des marchés émergents et frontières

| Référence | Apport | Usage BRVM |
|---|---|---|
| **Y. Amihud (2002)**, *Journal of Financial Markets* [B] | mesure d'illiquidité \|r\| / volume en valeur | filtre de liquidité et facteur de risque (doc 03) |
| **D. Lesmond, J. Ogden, C. Trzcinka (1999)**, *RFS* [B] | coût implicite estimé à partir des **jours à rendement nul** | à la BRVM, 16 à 44 % de variations nulles selon l'année (section 2.3) : estimateur LOT naturel |
| Études BRVM et frontières | voir docs 02 et 03 | — |

---

## 6. Implications pour la plate-forme (paramètres prêts à coder)

### 6.1 Configuration (YAML)

```yaml
# brvm_alpha/config/tools_benchmarks.yaml  (proposition, issue de la revue 08)
data_sources:
  primary:
    boc_pdf:
      url_pattern: "https://www.brvm.org/sites/default/files/boc_{yyyymmdd}{suffix}.pdf"
      first_available: "2017-01-02"        # aucun BOC trouvé en 2010-2016 avec ce motif (sondage)
      free: true                           # catalogue BRVM BR-013
  live:
    brvm_org_pages: ["/fr/cours-actions/0", "/fr/indices", "/fr/capitalisations/0"]
    ignore_fields: ["Variation 31 décembre"]   # incohérent avec le BOC (doc 01)
  backfill_pre_2017:
    method: "demande officielle BRVM (données historiques) ou CD historique"
    cost_fcfa: {cd_all_years: 150000, cd_previous_year_other: 75000}   # tarifs 2019, à reconfirmer
  forbidden:                                # règles du projet
    - "sikafinance.com/api/*"               # API interne non documentée (utilisée par le paquet R BRVM)
    - "richbourse.com scraping de cours"    # garde anti-aspiration ; relais d'actualités seulement (doc 07)
    - "contournement Cloudflare / anti-robot"
  third_party_policy:
    require_concordance_test: true          # comparer au BOC avant tout usage
    concordance_tolerance_pct: 0.01         # 1 pb sur les cours de clôture

data_quality:
  stale:
    flag_if_volume_zero: true
    max_stale_share_universe: 0.20          # titre exclu de l'univers si > 20 % de séances sans échange sur 60 séances (choix interne)
    returns_frequency_for_risk: "monthly"   # vol mensuelle 15,5 % vs journalière 11,0 % (2017-2026)
  gaps:
    max_calendar_days_between_sessions: 4   # au-delà : pas de rendement « 1 séance »
  corporate_actions:
    use_boc_reference_price: true
    alert_abs_return_gt: 0.075              # limite statique ±7,5 % hors IPO
    known_split_count_2017_2026: 50         # vérif. 22/11/2026 (panel 02:45) ; 47 dans la v1. Test de non-régression : ne pas coder en dur, recalculer depuis corporate_actions.parquet (kind == "split", confidence == "high")
  survivorship:
    point_in_time_universe: true
    delisted_examples: {TTRC: "2022-10-05", SVOC: "2025-06-26"}
  ratios:
    per_cap: 60                             # au-delà : PER non significatif (UNLC 631, BNBC 519)
    earnings_yield_cap: 0.12                # aligné sur le doc 05
  opcvm_nav:
    max_nav_age_days: 15
    valid_date_range: ["2005-01-01", "today"]

benchmarks:
  primary: "BRVM_COMPOSITE_TR"              # officiel, base 100 au 02/01/2025
  pre_2025_proxy:
    formula: "TR_y = P_y + k * Y_{y-1}"
    k: 0.88                                 # calibré 2025 (0,878) et 2026 (0,876)
    y_field: "avg_yield_pct (dernier BOC de l'année précédente)"
    confidence: "medium"
  secondary:
    - "BRVM_COMPOSITE"                      # indice prix : battre ce seul indice ne prouve rien
    - "BRVM_30"
    - "EW_TOTAL_RETURN_LIQUID"              # panier équipondéré des titres liquides
    - "OPCVM_EQUITY_MEDIAN"                 # médiane des fonds catégorie A du BOC
  reporting:
    show_vs_price_and_tr: true
    show_vs_opcvm_peer_rank: true
    rolling_windows_months: [12, 36, 60]

hurdles:
  target: "excès de rendement net > 0 contre Composite TR sur 36 mois glissants"
  historical_facts:
    opcvm_equity_beat_price_rate: [0.52, 0.56]   # 48/93 (v1) à 52/93 (reproduction du vérificateur) ; dépend de la lecture des catégories
    opcvm_equity_beat_tr_rate: [0.28, 0.30]      # 26/93 (v1) à 27-28/93 (reproduction)
    opcvm_median_excess_vs_tr_pts: [-6.0, -4.8]
    opcvm_tr_comparison_window: "same_as_nav"    # le TR se compare sur la fenêtre des VL, jamais sur l'année civile (erreur de la v1 pour 2026)
  min_track_record_months_before_claim: 36  # cohérent avec MinTRL (doc 04)

risk_scenarios:                             # pour les tests de résistance
  bear_2016_2020: {drawdown: -0.598, months_to_trough: 58, years_to_recover_price: 9.4}
  worst_calendar_year: {year: 2018, return: -0.2914, intra_year_dd: -0.330}
  worst_month: -0.086                       # 2018
  current_drawdown_from_ath: {ath: 555.90, ath_date: "2026-09-14", level: 492.89, dd: -0.113}
  monthly_vol_annualized: {full: 0.155, bear: 0.167, recent: 0.130}
  prob_negative_12m_window: 0.43            # 2017-2026, Composite prix

valuation_baselines:                        # lignes de base à TESTER, pas des signaux validés
  rf_local: 0.0575                          # doc 05
  erp_brvm_default: 0.040                   # doc 05
  ddm: {g_cap_nominal: 0.05, g_default: 0.02, dividend: "net"}
  relative_per: {benchmark: "secteur BOC (7 secteurs)", eps_basis: "moyenne 3 ans si dispo"}
  residual_income_banks: {roe_source: "comptes annuels", k_bank_default: 0.10}
  graham_screen: {per_max: 15, net_yield_min: 0.05, dividend_years_min_of_10: 8, pb_max: 1.5}
  consensus: "moyenne des z-scores des méthodes disponibles ; entre comme facteur value (doc 03)"
```

### 6.2 Fonctions de référence (Python)

```python
# brvm_alpha/data/opcvm.py  (proposition)
import re, datetime as dt
NUM = r"(\d+(?: \d{3})*(?:,\d+)?|ND)"
DATE = r"(\d{2}/\d{2}/\d{2,4}|ND)"
ROW = re.compile(r"\s{2,}(A|D|OMLT|OCT|OATC|O|M|C|OPCR|FCPR)\s{2,}(\d[\d ]*)\s{2,}"
                 + NUM + r"\s+" + DATE + r"\s+" + NUM + r"\s+" + DATE)

def parse_opcvm_section(boc_text: str) -> list[dict]:
    """Extrait (fonds, catégorie, VL précédente/date, VL actuelle/date) de la section OPCVM du BOC.
    Le nom du fonds = dernier bloc séparé par >= 2 espaces avant la catégorie."""
    i = boc_text.find("OPCVM: FONDS COMMUNS")
    out = []
    if i < 0:
        return out
    for line in boc_text[i:].splitlines():
        m = ROW.search(line)
        if not m:
            continue
        chunks = [c for c in re.split(r"\s{2,}", line[:m.start()].strip()) if c]
        if chunks:
            out.append({"fund": " ".join(chunks[-1].split()).upper(), "cat": m.group(1),
                        "nav_prev": m.group(3), "date_prev": m.group(4),
                        "nav_cur": m.group(5), "date_cur": m.group(6)})
    return out

def tr_proxy_annual(price_ret: float, yield_prev_year_end_pct: float, k: float = 0.88) -> float:
    """Composite TR approché pour les années < 2025 : P + k * Y(t-1). Calibré 2025-2026."""
    return price_ret + k * yield_prev_year_end_pct / 100.0

def calendar_return(nav, start, end, tol_days=15):
    """Rendement d'un fonds entre deux bornes ; None si une VL a plus de tol_days."""
    a, b = nav[:start], nav[:end]
    if a.empty or b.empty or (start - a.index[-1]).days > tol_days or (end - b.index[-1]).days > tol_days:
        return None
    return b.iloc[-1] / a.iloc[-1] - 1.0
```

### 6.3 Règles opérationnelles

1. **Toute performance affichée** dans l'interface doit montrer, côte à côte : stratégie nette de frais, **Composite TR**, Composite prix, **rang parmi les fonds actions du BOC** (percentile) et probabilité estimée d'une année négative.
2. **Aucune donnée tierce sans test de concordance** avec le BOC : écart de clôture ≤ 1 pb sur 60 séances, et splits identiques.
3. **Pipeline OPCVM** : ajouter `opcvm.parquet` à `build_panel` (fonds, catégorie, gérant, dépositaire, date, VL). Recalculer chaque mois le **groupe de pairs** (catégorie A) et sa médiane.
4. **Univers à date** : construire l'univers et les compositions d'indices **à la date** à partir des BOC (radiations, introductions, changements de compartiment).
5. **Risque** : volatilité **mensuelle** (au moins 13 à 16 % pour le marché), scénario de baisse de −60 % sur 5 ans, et tests de résistance sur 2018 (−29 %, −33 % de baisse intra-annuelle maximale).
6. **Communication honnête** : refuser toute formulation de type « gain garanti ». Afficher le fait historique : **environ 3 années-fonds professionnelles sur 10 (28 à 30 %) battent le TR**.

---

## 7. Questions ouvertes

1. **Recherche des SGI** (Hudson & Cie, Bridge Securities, EDC, Atlantique Finance, BOA Capital Securities, CGF Bourse) : méthodes, recommandations, historique. À rechercher quand le budget web et les domaines seront disponibles. Il faudra autoriser `www.hudson-cie.com`, `www.bridge-securities.com`, `www.cgfbourse.com`, `www.boacapital.com` et `www.atlantiquefinance.net` dans les réglages réseau de la session.
2. **Notes d'information des introductions récentes** (méthodes de valorisation des arrangeurs) : à lire sur richbourse (doc 07) ou sur le site de l'AMF-UMOA (domaine à autoriser).
3. **Statut actuel du paquet R `BRVM` sur CRAN** (actif ou archivé) : `cran.r-project.org` à autoriser.
4. **Sika Finance** : existence réelle et conditions d'un téléchargement CSV ou d'une API **officielle**. Demander un accord écrit plutôt que d'aspirer le site.
5. **Composite TR exact avant 2025** : reconstruire avec les nombres de titres (avis BRVM) et les dividendes nets, sur la méthode vérifiée au doc 01. Remplacer alors k = 0,88.
6. **2010 et années antérieures** : niveaux exacts du Composite (le tableau 3 du rapport 2015 n'est lisible qu'en image floue) ; demander l'historique officiel à la BRVM.
7. **Frais des OPCVM** (gestion, souscription) et **politique de distribution** de chaque fonds : nécessaires pour une comparaison TR contre TR exacte.
8. **Tickers et politique d'ajustement de Bloomberg et Refinitiv** pour la BRVM : à vérifier sur un terminal.
9. **Définitions BOC** du « taux de rendement moyen », du « taux de rentabilité moyen » et de la « prime de risque du marché » (pondération, net ou brut) : non publiées.
10. **« Sika Capital »** : absent de la liste des SGI de brvm.org ; vérifier s'il s'agit d'une autre entité (SGO, conseil) ou d'une confusion avec Sika Finance.

---

## Annexe : reproductibilité des calculs [C]

- **Indices, volatilité, drawdowns** : `data/panel/indices.parquet` (indice `BRVM COMPOSITE`, 2 334 séances du 02/01/2017 au 20/11/2026). Rendements journaliers seulement quand l'écart entre deux BOC est ≤ 4 jours ; rendements hebdomadaires sur les vendredis ; rendements mensuels en fin de mois. Clôture 2016 = 292,17 (rapport annuel 2016).
- **Rendement de dividende, PER, liquidité** : `data/panel/market.parquet` (champs `avg_yield_pct`, `avg_per`, `value`, `n_sgi`).
- **Panier équipondéré, splits, dividendes** : `data/panel/adjusted_prices.parquet` (`ret`, `tr_ret`, rendements \|r\| ≥ 50 % exclus), `corporate_actions.parquet` (50 splits de confiance high dans le panel du 22/11/2026 à 02:45 ; 47 dans la v1), `dividends.parquet`.
- **OPCVM** : parsing des 2 581 fichiers `data/boc_text/boc_*.txt.gz` avec l'expression régulière de la section 6.2 (168 fonds, 20 en catégorie A). Bornes de fin d'année avec une tolérance de 15 jours. Composite comparé sur la même fenêtre de dates.
- **Prix périmés** : `data/panel/equities.parquet` (volume nul ou absent ; `change_pct` = 0).

---

## Sources

### Sources primaires BRVM (consultées le 22/11/2026)

- Rapport annuel BRVM 2013 (indices 2012-2013) : https://www.brvm.org/sites/default/files/rapport_annuel_brvm_2013.pdf
- Rapport annuel BRVM 2014 (indices 2014 ; record du 22/09/2014) : https://www.brvm.org/sites/default/files/rapport_annuel_brvm_2014_0.pdf
- Rapport annuel BRVM 2015 (indices 2015 ; tableau 3 « Évolution récente de la BRVM (2010-2015) » ; décisions de décembre 2015 sur le flottant et le fractionnement) : https://www.brvm.org/sites/default/files/rapport_annuel_brvm_2015.pdf
- Rapport annuel BRVM 2016 (Composite 303,93 → 292,17 ; BRVM 10 290,38 → 261,95) : https://www.brvm.org/sites/default/files/rapport_annuel_brvm_2016.pdf
- Année boursière 2013 (contradiction sur les chiffres de 2012) : https://www.brvm.org/sites/default/files/stats-trim/annee_boursiere_2013_v2.pdf
- Page des rapports : https://www.brvm.org/fr/rapports-0 ; années boursières : https://www.brvm.org/fr/annees-boursieres ; statistiques trimestrielles : https://www.brvm.org/fr/statistiques-trimestrielles
- Communiqué « 2025 : la consolidation quinquennale, 99,15 % de progression en 5 ans » : https://www.brvm.org/fr/mediacentre/actualites/2025-la-consolidation-quinquennale-9915-de-progression-en-5-ans
- BRVM Awards 2026 : https://www.brvm.org/fr/mediacentre/actualites/brvm-awards-2026
- Historique (MSCI 2014 et 2016, S&P DJ 2014, cotation en continu 2013) : https://www.brvm.org/fr/historique
- Rediffuseurs de données (Bloomberg, FactSet, Refinitiv, SIX) : https://www.brvm.org/fr/rediffuseurs-de-donnees
- Données historiques : https://www.brvm.org/fr/donnees-historiques ; données de fin de journée : https://www.brvm.org/fr/donnees-de-fin-de-journee
- Catalogue des produits et services à valeur ajoutée de la BRVM (mars 2019) : http://www.brvm.org/sites/default/files/20190329-projet_brvm_-_catalogue_produits_valeur_ajoutee_version_finale.pdf ; page : https://www.brvm.org/fr/services/catalogues-de-services
- SGI : https://www.brvm.org/fr/intervenants/sgi/tous (pages `?page=0` à `?page=8`)
- SGO : https://www.brvm.org/fr/societes-de-gestion-d-opcvm
- Conseils en investissements boursiers : https://www.brvm.org/fr/conseils-en-investissements-boursiers
- Avis de fractionnement Sonatel (n°309, 23/10/2026 ; PDF image) : https://www.brvm.org/sites/default/files/20261023_-_avis_ndeg309_brvmdg_-_fractionnement_dactions_valeur_theorique_-_sonatel_sn.pdf
- Avis de paiement de dividendes de FCP (exemples : Sogevalor, Sogedynamique, exercice 2016) : https://www.brvm.org/fr/marche/avis-et-publications/publications
- BOC n°222 du 20/11/2026 (indices, ratios, OPCVM, 36 SGI) : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (copie locale : `data/boc_text/boc_20261120.txt.gz`)
- BOC 2017-2026 (2 581 fichiers, motif `https://www.brvm.org/sites/default/files/boc_AAAAMMJJ{suffixe}.pdf`) : copies locales dans `data/boc_text/`

### Outils de données (consultés le 22/11/2026)

- Paquet R `BRVM`, fichier DESCRIPTION (v5.3.0, publié le 21/02/2024) : https://raw.githubusercontent.com/cran/BRVM/master/DESCRIPTION
- NAMESPACE (fonctions exportées) : https://raw.githubusercontent.com/cran/BRVM/master/NAMESPACE ; liste des fichiers : https://raw.githubusercontent.com/cran/BRVM/master/MD5
- Sources lues : https://raw.githubusercontent.com/cran/BRVM/master/R/brvm-get.R ; https://raw.githubusercontent.com/cran/BRVM/master/R/brvm_get1.R ; https://raw.githubusercontent.com/cran/BRVM/master/R/brvm-boc.R ; https://raw.githubusercontent.com/cran/BRVM/master/R/brvm-index.R ; https://raw.githubusercontent.com/cran/BRVM/master/R/brvm-ticker.R ; https://raw.githubusercontent.com/cran/BRVM/master/R/brvm-cap.R
- Page CRAN (non accessible dans cette session) : https://cran.r-project.org/package=BRVM
- `brvmpy` (PyPI, v0.1.0 du 04/12/2025) : https://pypi.org/pypi/brvmpy/json ; https://pypi.org/project/brvmpy/ ; dépôt déclaré : https://github.com/idrissbado/BRVMpy (non consulté)
- Noms de paquets testés sans résultat : `https://pypi.org/pypi/{brvm,pybrvm,brvm-py,brvm-api,brvm-scraper,brvm-data,brvm-stocks,brvmapi}/json` (HTTP 404)
- Sika Finance (HTTP 403 ; non lu) : https://www.sikafinance.com/marches/historiques/BRVMC
- Richbourse (HTTP 403 ici ; lu par le doc 07) : https://www.richbourse.com/common/mouvements/technique/SNTS

### Documents du projet cités [R]

- `docs/research/01-structure-marche.md` : méthode des indices, TR à dividendes nets, anomalie de `/fr/indices`, splits.
- `docs/research/04-rigueur-quantitative.md` : prix périmés, corrections de Lo et Dimson, DSR, PBO, Kelly, Grinold.
- `docs/research/05-macro-geopolitique-uemoa.md` : r_f = 5,75 %, ERP = 4 %, m = 1,5, prime BOC et rendements futurs.
- `docs/research/06a-societes-financieres.md` : P/B et ROE des banques.
- `docs/research/07-actualite-sentiment-evenements.md` : accessibilité de richbourse et Sika Finance, calendrier des publications.

### Références bibliographiques (non relues dans cette session) [B] — [NON VÉRIFIÉ] par le vérificateur (pas d'accès web)

Les URL de notice suivantes sont citées par le doc 04 [R] et n'ont pas été rouvertes ici : Harvey, Liu & Zhu (2016), https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html ; Lo (2002), https://ideas.repec.org/a/taf/ufajxx/v58y2002i4p36-52.html ; Clarke, de Silva & Thorley (2002), https://ideas.repec.org/a/taf/ufajxx/v58y2002i5p48-66.html.

- Graham, B. & Dodd, D. (1934). *Security Analysis*. McGraw-Hill.
- Graham, B. (1949 ; éd. révisée 1973 ; commentaires de J. Zweig, 2003). *The Intelligent Investor*. Harper / HarperBusiness.
- Williams, J. B. (1938). *The Theory of Investment Value*. Harvard University Press.
- Gordon, M. J. (1962). *The Investment, Financing, and Valuation of the Corporation*. Irwin.
- Damodaran, A. (2012). *Investment Valuation*, 3ᵉ éd. Wiley ; (2017). *Narrative and Numbers*. Columbia Business School Publishing ; (2011). *The Little Book of Valuation*. Wiley ; mises à jour annuelles « Equity Risk Premiums » et « Country Risk » : https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html (hôte bloqué ici).
- Koller, T., Goedhart, M. & Wessels, D. *Valuation: Measuring and Managing the Value of Companies*. McKinsey & Company / Wiley.
- Penman, S. *Financial Statement Analysis and Security Valuation*. McGraw-Hill.
- Grinold, R. & Kahn, R. (2000). *Active Portfolio Management*, 2ᵉ éd. McGraw-Hill.
- Clarke, R., de Silva, H. & Thorley, S. (2002). « Portfolio Constraints and the Fundamental Law of Active Management ». *Financial Analysts Journal*.
- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley ; (2020). *Machine Learning for Asset Managers*. Cambridge University Press.
- Chan, E. (2008 ; 2ᵉ éd. 2021). *Quantitative Trading*. Wiley ; (2013). *Algorithmic Trading: Winning Strategies and Their Rationale*. Wiley.
- Lo, A. (2002). « The Statistics of Sharpe Ratios ». *Financial Analysts Journal*.
- Lo, A. & MacKinlay, A. C. (1999). *A Non-Random Walk Down Wall Street*. Princeton University Press.
- Harvey, C., Liu, Y. & Zhu, H. (2016). « … and the Cross-Section of Expected Returns ». *Review of Financial Studies*.
- Ilmanen, A. (2011). *Expected Returns*. Wiley.
- Pedersen, L. H. (2015). *Efficiently Inefficient*. Princeton University Press.
- Tetlock, P. & Gardner, D. (2015). *Superforecasting*. Crown ; Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus and Giroux ; Taleb, N. N. (2001). *Fooled by Randomness*.
- Amihud, Y. (2002). « Illiquidity and Stock Returns ». *Journal of Financial Markets*.
- Lesmond, D., Ogden, J. & Trzcinka, C. (1999). « A New Estimate of Transaction Costs ». *Review of Financial Studies*.
- Kelly, J. L. (1956). « A New Interpretation of Information Rate ». *Bell System Technical Journal*.

---

## Vérification adversariale (2026-11-22)

**Rôle** : vérificateur sceptique, domaine « landscape-practice ». **Méthode** : chaque élément a été recontrôlé de façon indépendante. Les recalculs ont été faits sur les 2 581 BOC texte (`data/boc_text/`) et sur le panel reconstruit le 22/11/2026 à 02:45 (`data/panel/*.parquet`, identique à `data/panel_verify/`). Les sources primaires ont été relues : pages HTML et PDF de brvm.org, API JSON de PyPI, miroir GitHub de CRAN. Les scripts de vérification se trouvent dans le dossier de travail de la session ; ils ne font pas partie du projet. **Limites** : recherche web impossible (budget épuisé) ; `doi.org` et `api.crossref.org` refusés. Les références bibliographiques n'ont donc pas pu être contrôlées.

### Synthèse des verdicts

| Verdict | Nombre |
|---|---|
| Confirmé | 22 |
| Corrigé | 5 |
| Réfuté (supprimé ou remplacé) | 2 |
| Non vérifiable | 1 |
| **Total** | **30** |

### Détail des vérifications

| # | Élément (valeur v1) | Verdict | Valeur retenue / commentaire | Preuve | Conf. |
|---|---|---|---|---|---|
| 1 | BOC n°222 du 20/11/2026 : Composite 492,89 (+42,56 %), BRVM 30 238,73 (+43,61 %), Prestige 186,61 (+29,37 %), Principal 337,96 (+55,28 %), TR 198,63 (+49,19 %), PER 15,79, rendement 7,12 %, prime 0,58, 36 SGI, 48 sociétés | **confirmé** | identique | https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (copie locale `boc_20261120.txt.gz`) | high |
| 2 | Clôtures annuelles du Composite 2017-2025 (243,06 → 345,75) ; série 2021-2025 et cumul +99,15 % | **confirmé** | identique ; le communiqué donne 145,37 → 345,75 | `indices.parquet` ; https://www.brvm.org/fr/mediacentre/actualites/2025-la-consolidation-quinquennale-9915-de-progression-en-5-ans | high |
| 3 | RA 2015-2016 : 303,93 (31/12/2015) → 292,17 (30/12/2016) ; BRVM 10 290,38 → 261,95 | **confirmé** | texte du RA 2016 | https://www.brvm.org/sites/default/files/rapport_annuel_brvm_2016.pdf | high |
| 4 | Décisions de décembre 2015 : flottant ≥ 20 %, 2 à 10 millions de titres, délai de 2 ans, fractionnement, cours moyen visé 5 385 FCFA | **confirmé** | texte du RA 2015 | https://www.brvm.org/sites/default/files/rapport_annuel_brvm_2015.pdf | high |
| 5 | `bear_2016_2020` : −59,8 %, creux 122,19 le 26/10/2020, 58 mois, retour au prix le 10/06/2025 (304,34), 9,4 ans ; sommet BOC 290,44 le 01/03/2017, retrouvé le 20/02/2025 | **confirmé** | identique | `indices.parquet` | high |
| 6 | `current_drawdown_from_ath` : plus haut 555,90 le 14/09/2026 ; −11,3 % | **confirmé** | 492,89 / 555,90 − 1 = −11,3 % | `indices.parquet` | high |
| 7 | `composite_monthly_vol_annualized` 0,155 / 0,167 / 0,130 ; journalière 0,110 | **confirmé** | 0,155 / 0,166 / 0,130 ; journalière 0,110 (2 316 rendements, écart ≤ 4 jours) | `indices.parquet` | high |
| 8 | Volatilité hebdomadaire 12,0 % ; autocorrélation mensuelle 0,13 ; médiane des rendements sur 12 mois +5,4 % | **corrigé (mineur)** | 11,8 % ; 0,12 ; +5,2 %. Écarts de convention (semaines et mois sans BOC en 2021), sans effet sur les paramètres codés | `indices.parquet` | medium |
| 9 | `prob_negative_12m_window` 0,43 ; min −29,1 % ; max +69,4 % | **confirmé** | 0,435 (47 fenêtres sur 108) ; −29,1 % ; +69,4 % | `indices.parquet` | high |
| 10 | `worst_calendar_year` 2018 −29,14 % ; baisse intra-annuelle −33,0 % ; pire mois −8,6 % ; pires et meilleures séances | **confirmé** | identique (convention « première séance de l'année ») | `indices.parquet` | high |
| 11 | `tr_proxy_k_pre_2025` 0,88 (0,878 ; 0,876) | **confirmé (entrées)** | Les entrées se recalculent : TR fin 2025 = 133,14 (BOC du 02/01/2026 : 132,65, −0,37 %), Y fin 2024 = 8,97, Y fin 2025 = 7,57. **Réserve ajoutée** : Y₂₀₁₆ n'existe pas dans les BOC, et le 5,87 % utilisé date du 19/12/2017 (anticipation) | `indices.parquet`, `market.parquet` | medium |
| 12 | Rendement moyen du marché : 5,4 % à 10,1 % en fin d'année ; moyenne des médianes 2018-2026 ≈ 7,8 % | **confirmé** | 5,38 % à 10,11 % ; 7,81 % | `market.parquet` | high |
| 13 | « Au 20/11/2026, le marché est le plus cher de la décennie (PER 15,79) » | **réfuté** | PER > 15,79 dans 228 séances sur 238 en 2017 et dans 89 séances de janvier à mai 2018 ; pic de 2026 : 18,43 le 14/09/2026. Remplacé par « plus haut depuis mai 2018, hors valeurs aberrantes » | `market.parquet` (champ `avg_per`) | high |
| 14 | `stale_share_no_trade_2026` 0,010 (2020 : 0,247) ; variations nulles de 44,4 % à 15,8 % | **confirmé** | identique, année par année (0,218 ; 0,175 ; 0,209 ; 0,247 ; 0,142 ; 0,098 ; 0,094 ; 0,106 ; 0,044 ; 0,010) | `equities.parquet` | high |
| 15 | `split_count_2017_2026` = 47 | **corrigé** | **50** splits de confiance high dans le panel actuel (reconstruit après la rédaction de la v1). Liste nominative (BICC ×10, CFAC ×100, PRSC ×64, SNTS ×10, vague 2024 BOA, etc.) confirmée. Ne pas coder ce nombre en dur | `corporate_actions.parquet` | high |
| 16 | Split Sonatel ×10 : clôture 43 850 le 23/10/2026, cours de référence 4 385, faux −89,3 % en série brute le 26/10/2026 | **confirmé** | 4 700 / 43 850 − 1 = −89,3 % | BOC du 23/10 et du 26/10/2026 (copies locales) | high |
| 17 | Limite statique de ±7,5 % (`alert_abs_return_gt` 0,075) | **confirmé (empiriquement)** | Aucune variation > 7,5 % en séance échangée depuis 2024. Les 30 exceptions de 2017-2023 sont des détachements de dividende, des effets de pas de cotation (ETIT, 13 → 14 FCFA) ou des splits. Le texte réglementaire n'a pas été relu ici (le doc 05 le confirme [R]) | `equities.parquet` | medium-high |
| 18 | Radiations et entrées : TTRC 05/10/2022, SVOC 26/06/2025, ORAC 12/2022, LNBB 12/2024, BICB 04/2025, BBGC 09/2026 ; BRVM 10 → BRVM 30 le 02/01/2023 | **confirmé** | ORAC 30/12/2022, LNBB 13/12/2024, BICB 28/04/2025, BBGC 24/09/2026 ; dernière séance du BRVM 10 : 30/12/2022 | `equities.parquet`, `indices.parquet` | high |
| 19 | Paquet R `BRVM` : v5.3.0 du 21/02/2024, auteurs, richbourse lignes 600:650 (550:700), API `sikafinance.com/api/general/GetHistos` par tranches de 89 jours, 46 tickers (TTRC commenté, SVOC présent, BBGC/BICB/LNBB absents) | **confirmé** | identique | https://raw.githubusercontent.com/cran/BRVM/master/DESCRIPTION ; https://raw.githubusercontent.com/cran/BRVM/master/R/brvm-get.R ; https://raw.githubusercontent.com/cran/BRVM/master/R/brvm_get1.R | high |
| 20 | `brvmpy` 0.1.0 du 04/12/2025, Selenium et Chrome sans interface, exemple « BRVM 10 » et Composite 210,45 ; BOC du 04/12/2025 : 353,29 | **confirmé** | téléversé le 2025-12-04 à 07:30:18 ; Composite BOC 353,29 | https://pypi.org/pypi/brvmpy/json ; `indices.parquet` | high |
| 21 | `official_data_costs_2019` : BOC gratuit (BR-013), BDFIN 500 000 / 2 000 000 FCFA/an, CD N-1 50 000 / 75 000, CD toutes années 150 000, temps réel 7 500 € + A1 2 500 €, différé 5 000 € + B1 1 250 € / B2 600 € | **confirmé** | identique (tarifs de mars 2019 ; tarifs actuels non vérifiés) | http://www.brvm.org/sites/default/files/20190329-projet_brvm_-_catalogue_produits_valeur_ajoutee_version_finale.pdf | high (2019) / low (2026) |
| 22 | Rediffuseurs (Bloomberg, FactSet, Refinitiv, SIX) ; MSCI standalone le 10/06/2014, MSCI et S&P DJ le 14/06/2014, MSCI Frontier le 14/11/2016 | **confirmé** | identique | https://www.brvm.org/fr/rediffuseurs-de-donnees ; https://www.brvm.org/fr/historique | high |
| 23 | SGI : capital minimum de 1 milliard FCFA, Instruction 4/97 ; conseils en investissements boursiers : Instruction 6/97, « sans se substituer à eux » | **confirmé** | identique | https://www.brvm.org/fr/intervenants/sgi/tous ; https://www.brvm.org/fr/conseils-en-investissements-boursiers | high |
| 24 | Liste des SGI : « 34 noms distincts, 36 fiches, pages 0 à 8 » | **corrigé** | **39 fiches, 37 noms distincts, pages 0 à 9**. Ajouts : SA2IF, Société Générale Capital Securities West Africa, United Capital for Africa | https://www.brvm.org/fr/intervenants/sgi/tous?page=9 | high |
| 25 | BRVM Awards 2026 (26-27/03/2026, Dakar) : CGF Bourse, NSIA AM, SICAV Attijari Oblig, Sika Finance, Invictus | **confirmé** | identique (en plus : société cotée de l'année, Ecobank CI ; opération actions, BIIC Bénin) | https://www.brvm.org/fr/mediacentre/actualites/brvm-awards-2026 | high |
| 26 | `opcvm_equity_beat_price_rate` 0,52 ; `beat_tr_rate` 0,28 ; `median_excess_vs_tr` −6,0 (93 années-fonds, 168 fonds) | **corrigé (fourchettes)** | 168 fonds et 93 années-fonds reproduits. Avec la catégorie lue à la date de fin et le TR sur la même fenêtre : **0,56 ; 0,29 ; −4,8**. Paramètres codés en fourchettes [0,52-0,56], [0,28-0,30], [−6,0 ; −4,8]. Conclusion qualitative inchangée | parsing des BOC (regex de la section 6.2) | medium |
| 27 | « Un seul fonds (Attijari Actions) bat le TR en 2026 au 20/11 » | **réfuté** | Attijari Actions fait +54,7 % du 26/12/2025 au 13/11/2026 ; le TR fait ≈ +58,4 % sur cette fenêtre (207,92 le 13/11). **Aucun fonds** ne bat le TR en 2026 sur fenêtre identique. Erreur de méthode : TR pris en année civile | BOC du 06/01/2026 et du 20/11/2026 ; `indices.parquet` | high |
| 28 | FCP BOA Actions du 31/12/2021 au 13/11/2026 : +191,1 % ; prix +155,1 % ; « TR estimé ≈ +221 % » | **corrigé** | +191,1 % et +155,1 % confirmés (11 035,74 → 32 122,84 ; 202,28 → 515,94). TR estimé **≈ +235 % sur la même fenêtre** (+221 % au 20/11) | BOC ; `indices.parquet` | medium |
| 29 | `graham_screen` : 8 titres sur 48 (SOGC, PALC, SGBC, BOAS, CABC, BOAC, ECOC, ONTBF) ; `rf_local` 5,75 % | **confirmé (calcul)** | 8/48 identiques. 5,75 % = 100 / 15,79 − 0,58 = 5,753 (formule de la légende du BOC) | `equities.parquet`, `dividends.parquet` ; BOC n°222 | high (calcul) |
| 30 | Références bibliographiques : Graham (critères défensifs), Clarke, de Silva & Thorley 2002, Harvey, Liu & Zhu 2016, Lo 2002, Amihud 2002, Lesmond, Ogden & Trzcinka 1999, Kelly 1956 | **non vérifiable** | Aucune recherche ni résolution de DOI possible dans cette session. Marquées [NON VÉRIFIÉ] ; volumes et pages de trois articles repris du doc 04 [R]. Aucun élément ne laisse penser qu'elles soient fausses, mais aucun contrôle primaire n'a été fait | — | low (vérif.) |

### Autres contrôles (mineurs, sans changement)

- La **valeur transigée 2025** du communiqué (351 292 910 484 FCFA, contre 461 530 599 968 en 2024) est confirmée. La somme des BOC donne 264,4 et 165,2 Md, contre 264,9 et 165,5 Md dans la v1 ; l'écart vient de l'arrondi ou du parsing.
- Les **cumuls de prix** se recalculent : +5,4 %/an (292,17 → 492,89) et +20,0 %/an depuis fin 2021. Le **TR estimé 2017-2026** donne +211,5 %, soit environ 12,2 %/an.
- Le BOC compte **17 titres** dans les services financiers et **7 secteurs**.

### Ce qui change pour le code

1. `known_split_count_2017_2026: 50`. Mieux encore : un test qui **recalcule** ce nombre au lieu de le figer.
2. `opcvm_tr_comparison_window: "same_as_nav"`. Les taux de surperformance des OPCVM sont codés en **fourchettes**.
3. Aucun libellé de l'interface ne doit dire « marché le plus cher de la décennie ». Il faut **exclure les PER moyens aberrants** du BOC (17/02/2021 et 17/07-26/08/2025) avant tout percentile historique.
4. **Fixer et documenter** la convention de drawdown intra-annuel : première séance de l'année, ou clôture de l'année précédente.
5. Pour le TR estimé de 2017, garder la **réserve d'anticipation**. Ne jamais utiliser ce point pour calibrer k.
