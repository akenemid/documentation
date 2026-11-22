# 07 — Actualité, sentiment et événements à la BRVM (état au 22/11/2026)

> **Périmètre** : (1) les sources d'actualité BRVM qu'un programme peut lire automatiquement, avec leurs URL exactes et leur structure HTML ; (2) les méthodes d'analyse de sentiment adaptées aux textes financiers en français, et un lexique de départ propre à la BRVM ; (3) des études d'événements mesurées sur nos propres données : détachements de dividendes, avis de paiement, assemblées générales, publications financières, suspensions ; (4) le calendrier type de l'information (AG, états financiers, rapports trimestriels, dividendes) ; (5) une spécification chiffrée du module « actualité + événements ».
> **Date de rédaction** : 22/11/2026. **Dernier BOC utilisé** : 20/11/2026 (`data/boc_text/boc_20261120.txt.gz`). Panel : `data/panel/*.parquet` (2 334 séances, du 02/01/2017 au 20/11/2026).
> **Méthode** : lecture directe de pages publiques de `www.brvm.org` avec `curl`, en respectant le `Crawl-delay: 10` de son `robots.txt` (environ 200 pages lues, une toutes les 10 s). Lecture du `sitemap.xml` et de quatre pages publiques de `www.richbourse.com` (pages autorisées par son `robots.txt`). Analyse des BOC texte et du panel du projet. Les études d'événements sont **nos propres calculs** ; les scripts sont décrits au §4.2.
> **Limites (à lire)** : (1) le **quota de recherche web de la session était épuisé** avant le début de cette tâche (message de l'outil : « web search budget is used up »). Aucune recherche bibliographique nouvelle n'a pu être faite. (2) Le réseau de la session ne joint que `www.brvm.org`, `www.richbourse.com` et `pypi.org`. `financialafrik.com`, `agenceecofin.com`, `news.abidjan.net`, `amf-umoa.org`, `bceao.int`, `sraf.nd.edu`, `huggingface.co` et `arxiv.org` sont **bloqués par le proxy** : ces sources n'ont donc **pas pu être vérifiées**. (3) `www.sikafinance.com` renvoie une page de protection Cloudflare (« Attention Required ! », HTTP 403). Nous **ne l'avons pas contournée**. (4) Les références académiques du §3 sont des travaux connus, cités avec leur DOI ou leur identifiant arXiv, mais **non relus en ligne pendant cette session** : leur confiance est notée « medium ». (5) **Aucun chiffre n'a été inventé** : quand une information manque, c'est écrit « introuvable » ou « non vérifié ».
> **Avertissement** : les effets mesurés ici sont des **moyennes historiques, dans l'échantillon**. Ce ne sont pas des promesses. Aucune méthode ne « garantit » un gain, et un effet publié dans ce document peut s'affaiblir dès qu'il est exploité. On voit d'ailleurs l'effet « avis → détachement » diminuer en 2025-2026 (§4.4). Chaque signal doit être validé hors échantillon, net de coûts, selon le protocole du document 04.

Légende de confiance : **H** = fait primaire observé (page brvm.org, BOC, calcul direct sur le panel) ; **M** = calcul ou inférence avec hypothèses explicites, ou référence académique connue non relue dans cette session ; **B** = information partielle, indirecte ou non vérifiée.

---

## 0. Synthèse en 16 points

| # | Constat | Valeur | Date des faits | Conf. | Source |
|---|---|---|---|---|---|
| 1 | Source primaire d'actualité exploitable | `www.brvm.org` : 6 listes d'annonces des émetteurs, 6 listes d'opérations sur titres, liste des avis, rapports par émetteur. Tables HTML Drupal 7 régulières, pagination `?page=N` | 22/11/2026 | H | §1.2 |
| 2 | Règle de politesse | `robots.txt` de brvm.org : **`Crawl-delay: 10`** | 22/11/2026 | H | https://www.brvm.org/robots.txt |
| 3 | Flux RSS | Le seul flux RSS de brvm.org (`/fr/taxonomy/term/1/feed`) est **vide** (canal sans `<item>`). Richbourse `/common/rss` est une page HTML, pas un flux RSS. Il faut donc **interroger les pages régulièrement** | 22/11/2026 | H | §1.6 |
| 4 | Calendrier officiel des dividendes | `/fr/esv/paiement-de-dividendes` : **433 lignes** (44 pages). Colonnes : émetteur, exercice, date de paiement, **date ex-dividende**, montant net, lien vers l'avis BRVM. Ce lien contient la **date de l'avis** (`/files/AAAAMMJJ_...`) | 2017-2026 | H | §1.2 |
| 5 | Délai entre l'avis de paiement et le détachement | médiane **14 jours calendaires** (p10 = 10 ; p90 = 28), soit **8 séances** (médiane) entre la première séance qui suit l'avis et le jour du détachement | 2017-2026 | H | §4.4 |
| 6 | Le cours baisse moins que le dividende au détachement | rapport baisse/dividende (PDR) à la clôture : **médiane 0,46** (279 détachements). Le prix ne baisse en moyenne que d'environ la moitié du dividende net | 2017-2026 | H | §4.3 |
| 7 | Rendement anormal du jour de détachement (dividende inclus, moins le Composite) | **+2,48 %** en moyenne, médiane +2,65 %, 79 % de cas positifs, t = 12,4. t « par mois-grappe » = 8,1 | 2017-2026 | H | §4.3 |
| 8 | Montée avant le détachement | CAR[−20,−1] = **+2,54 %** (médiane +2,33 %, t = 6,3, t par grappe = 4,2). Le signe est le même sur 2017-2021 et 2022-2026 | 2017-2026 | H | §4.3 |
| 9 | Baisse après le détachement | CAR[+1,+20] = **−2,54 %** (médiane −3,46 %, t = −4,3, t par grappe = −2,0) | 2017-2026 | H | §4.3 |
| 10 | Fenêtre négociable « avis → détachement » | achat à la clôture de la 1re séance après l'avis, vente à la clôture du jour de détachement : **+4,07 %** en moyenne contre le Composite, médiane +4,19 %, 78 % de cas positifs (276 cas). **Net de 1,7 à 2,8 % de coûts : +1,3 % à +2,4 %** en moyenne. L'effet **diminue** : +2,8 % en 2025 et +1,5 % en 2026, bruts | 2017-2026 | H (calcul) / M (coûts) | §4.4 |
| 11 | L'avis de paiement n'est pas une « nouvelle » | Rendement anormal de la 1re séance après l'avis : +0,20 % (t = 1,5, non significatif). L'information sur le montant est déjà connue (AG, communiqué) ; la hausse vient de la **demande de dividende** pendant les jours qui suivent | 2017-2026 | H | §4.4 |
| 12 | Saison des AG ordinaires | **43 % en juin**, 20 % en avril, 17 % en mai. **88 % avant le 30 juin** (hors 2020, année Covid) | 2017-2026 | H | §5 |
| 13 | Délai entre l'AGO et le détachement | médiane **42 jours** (p25 = 28 ; p75 = 67) | 2017-2026 | H | §4.5 |
| 14 | Saison des détachements | juillet 31 %, mai 20 %, juin 14 %, septembre 13 %, août 12 % : **90 % entre mai et septembre** | 2017-2026 | H | §5 |
| 15 | Publication des états financiers annuels (relais richbourse) | 13 % publiés fin mars, **44 % fin avril**, 61 % fin mai, 76 % fin juin. Rapports T1 en avril-mai, S1 surtout en octobre, T3 d'octobre à décembre | 2018-2025 | H (relais) / M (date) | §5 |
| 16 | Heure de diffusion | Sur richbourse, **72 %** des publications du jour sont mises en ligne **après 16h UTC**, donc après la fin de séance (15h00 UTC). Un autre pic se situe à 8h UTC. Conséquence pour le code : une nouvelle du jour J ne peut se négocier qu'à **J+1, au fixing d'ouverture** | 2021-2026 | M | §2 |

**Ce qui est unique ici** : à notre connaissance, aucune étude publiée ne mesure le cycle complet du dividende à la BRVM (montée avant, baisse incomplète au détachement, baisse après). Le document 02 n'en a trouvé aucune. Ce document le fait sur 313 détachements officiels et le traduit en règles chiffrées (§6). Il montre aussi les limites de ces règles : coûts, capacité, déclin récent.

---

## 1. Sources d'actualité exploitables automatiquement

### 1.1 Accessibilité testée le 22/11/2026

| Source | URL testée | Résultat | Utilisable par la plate-forme ? | Conf. |
|---|---|---|---|---|
| BRVM (site officiel) | https://www.brvm.org/fr | HTTP 200 | **Oui** : source primaire, à lire à 1 requête / 10 s | H |
| Richbourse | https://www.richbourse.com | HTTP 200 | **Oui, avec modération** : son `robots.txt` autorise les pages publiques (y compris pour les agents « Claude-User ») et interdit `/investisseur/`, `/api/`, `/site/premium`. Le site mentionne une « garde anti-aspiration » | H |
| Sika Finance | https://www.sikafinance.com | HTTP 403, page Cloudflare « Attention Required! » | **Non** sans accord ou API officielle. On **ne contourne pas** une protection anti-robot | H |
| Financial Afrik | https://www.financialafrik.com | bloqué par le proxy de la session | Non testé : à revoir si le domaine est autorisé | H (fait du blocage) |
| Agence Ecofin | https://www.agenceecofin.com | bloqué par le proxy | Non testé directement. Ses dépêches BRVM sont **reprises** dans la revue de presse de richbourse (§1.5) | H (fait du blocage) |
| Abidjan.net | https://news.abidjan.net | bloqué par le proxy | Non testé | H (fait du blocage) |
| AMF-UMOA (régulateur) | https://www.amf-umoa.org | bloqué par le proxy | Non testé. Ses décisions (agréments, visas) sont **reprises** dans les publications officielles de richbourse (ex. 17/11/2026 : agrément du FCTC BIDC) | H (fait du blocage) |
| BCEAO | https://www.bceao.int | bloqué par le proxy | Non testé (voir document 05) | H (fait du blocage) |

### 1.2 brvm.org : inventaire des flux (lus le 22/11/2026)

Toutes ces pages sont des **vues Drupal 7** (`<table class="views-table cols-N table table-hover table-striped">`). Chaque cellule `<td>` porte une classe stable `views-field-<nom>`. Les dates ont un attribut ISO lisible par machine (`<span class="date-display-single" content="2026-11-16T00:00:00+00:00">`). La pagination se fait par `?page=N`, avec N à partir de 0. Le numéro de la dernière page se lit dans `<li class="pager-last"><a href="...?page=N">`.

| Flux | URL exacte | Colonnes (classes `views-field-…`) | Lignes/page | Dernière page (22/11/2026) | Volume estimé | Horodatage | Plus récent |
|---|---|---|---:|---:|---:|---|---|
| Communiqués des émetteurs | https://www.brvm.org/fr/emetteurs/type-annonces/communiques | `field-date-annonce` (date ISO), `og-group-ref` (société), `title`, `field-fichier-annonce` (PDF) | 15 | 26 | ≈ 400 | date seule | 16/11/2026 SOGB CI |
| Convocations d'AG | https://www.brvm.org/fr/emetteurs/type-annonces/convocations-assemblees-generales | idem | 15 | 59 | ≈ 900 | date | 02/10/2026 ETI TG |
| Changements de dirigeants | https://www.brvm.org/fr/emetteurs/type-annonces/changements-de-dirigeants | idem | 15 | 7 | ≈ 120 | date | 16/11/2026 FILTISAC, SOGB |
| Franchissements de seuil | https://www.brvm.org/fr/emetteurs/type-annonces/franchissements-de-seuil | idem | 15 | 2 | ≈ 40 | date | 09/05/2025 ALIOS/SAFCA |
| Notations financières | https://www.brvm.org/fr/emetteurs/type-annonces/notations-financieres | idem | 15 | 31 | ≈ 470 | date | 13/11/2026 CIE CI |
| Projets de résolution | https://www.brvm.org/fr/emetteurs/type-annonces/projets-de-resolution | idem | 15 | 18 | ≈ 280 | date | 03/08/2026 AGL CI |
| Paiement de dividendes | https://www.brvm.org/fr/esv/paiement-de-dividendes | `field-emetteur-esv`, `body-1` (obligation), `body` (action), `field-exercice-comptable-esv`, `field-date-de-paiement-esv`, **`field-date-ex-dividende`**, `field-montant-du-dividende-net`, `field-avis-dividende-esv` (PDF) | 10 | 43 | **433** (relevé complet) | dates ISO | AGL CI, ex 26/10/2026, 92 FCFA |
| Augmentations de capital | https://www.brvm.org/fr/esv/augmentation-de-capital | émetteur, `field-date-de-fermeture-des-regi`, `field-autre-parite`, `field-nature-du-droit-esv`, `field-periode-de-negociation-esv`, avis, communiqué | 10 | 2 | ≈ 30 | date | SIB, registres au 19/11/2024 |
| Fractionnements | https://www.brvm.org/fr/esv/fractionnement | émetteur, `field-date-de-fractionnement`, `field-parite-esv`, `field-valeur-theorique`, avis, communiqué | 10 | 4 | ≈ 50 | date | SONATEL 10:1 le 26/10/2026 |
| Radiations | https://www.brvm.org/fr/esv/radiation | émetteur, obligation, action, `field-date-de-radiation`, avis | 10 | 1 | ≈ 20 | date | BIDC-EBID 6,40 %, 12/07/2026 |
| Consolidation, réduction de capital | https://www.brvm.org/fr/esv/consolidation ; https://www.brvm.org/fr/esv/reduction-de-capital | même gabarit « esv » | — | — | faible | — | non relevé |
| Avis de la BRVM | https://www.brvm.org/fr/marche/avis-et-publications/avis | `title`, **`field-date-avis` (date + heure, ex. `2026-11-17T18:18:00`)**, `field-fichier-avis` | 10 | 192 | ≈ 1 930 | **date et heure** | 17/11/2026 (SWAS.O1) |
| Publications (décisions, homologations) | https://www.brvm.org/fr/marche/avis-et-publications/publications | `title`, `field-date-pub`, `field-fichier-publication` | 10 | 3 | ≈ 40 | date | page peu tenue à jour (la plus récente date de 2017) |
| Rapports des sociétés cotées (index) | https://www.brvm.org/fr/rapports-societes-cotees | `field-code-emetteur`, `title` (lien vers la page de l'émetteur), `field-description-emetteur` | 30 | 2 | 75 émetteurs (actions, obligations, FCTC) | — | — |
| Rapports d'un émetteur | https://www.brvm.org/fr/rapports-societe-cotes/<slug> (ex. `/bank-africa-ci`) | `nothing` (titre du document), `field-fichier` (PDF) | ≈ 19 | 3 (BOA CI) | ≈ 20 à 60 par émetteur | **aucune colonne de date** : la date se lit dans le nom du PDF (`/files/AAAAMMJJ_-_...`) | 02/11/2026 BOA CI, rapport T3 2026 |
| Actualités de la BRVM (institutionnelles) | https://www.brvm.org/fr/mediacentre/actualites | pas de table `views-table` | — | — | faible valeur pour le trading | — | ex. « La BRVM franchit le cap des 20 000 milliards de FCFA » |
| BOC quotidien (PDF) | https://www.brvm.org/fr/bulletins-officiels-de-la-cote ; fichier type https://www.brvm.org/sites/default/files/boc_20261120_2.pdf | voir §1.4 | 1/jour | — | 2 334 BOC dans le projet | date | 20/11/2026 |

Les volumes sont estimés comme (dernière page + 1) × lignes par page. Seule la liste des dividendes a été lue en entier (433 lignes). Pour les communiqués, les convocations et les avis, nous avons lu respectivement 27, 20 et 30 pages (§2). Conf. **H**.

**Remarques utiles pour le code (H) :**
- La colonne « Société » (`og-group-ref`) contient des **libellés historiques** : « BOLLORE TRANSPORT & LOGISTICS » pour AGL CI, « AIR LIQUIDE CI » pour ERIUM CI, « SGCI » pour SGBC… Il faut une **table de correspondance libellé → symbole**. Celle utilisée ici en compte environ 140 entrées, dont celles des AG du BOC (script `names.py`, §4.2).
- Les noms de fichiers PDF commencent presque toujours par la date du document (`20261116_-_communique_de_presse_-_sogb_ci.pdf`). C'est la seule date disponible pour les rapports par émetteur.
- La liste des dividendes contient quelques erreurs de saisie : une date ex-dividende tombe un dimanche (SOGC, 05/07/2026) et quelques montants diffèrent du BOC (§4.3). Il faut donc **recouper avec le BOC** (mention « (d) Ex-dividende » et colonne « Dernier dividende payé »).

### 1.3 Gabarit d'analyse HTML (testé sur toutes les listes ci-dessus)

```python
# Extrait du script de recherche parse_views.py : regex simples, sans dépendance.
# En production, utiliser selectolax (MIT) ou lxml.
TABLE   = r'<table class="views-table[^"]*"[^>]*>(.*?)</table>'
ROW     = r'<tr[^>]*>(.*?)</tr>'                         # ignorer la 1re ligne (<thead>)
CELL    = r'<td class="views-field ([^"]*)"[^>]*>(.*?)</td>'
ISO     = r'content="([^"]+)"'                           # date ISO 8601 dans la cellule
LINK    = r'href="([^"]+)"'                              # PDF : https://www.brvm.org/sites/default/files/...
LASTPG  = r'pager-last"><a[^>]*href="[^"]*page=(\d+)"'
FILEDT  = r'/files/(\d{8})'                              # date AAAAMMJJ dans le nom du PDF
```

### 1.4 Le BOC, première source d'événements (lecture des BOC texte)

Chaque BOC quotidien contient, en plus des cours, des **sections d'événements** que `boc_parser` peut extraire. Contenu vérifié sur le BOC du 20/11/2026 (H) :

| Section du BOC | Contenu | Exemple au 20/11/2026 | Usage |
|---|---|---|---|
| Mentions du tableau des cours | `(d) Ex-dividende`, `Ex-c` (ex-coupon), `Ex-d` (ex-droit), `SP` (suspendu), `Val-T` (valeur théorique) | — | date exacte de détachement, suspensions |
| « Dernier dividende payé » | montant net et date de paiement | TTLS : 176,65 FCFA, 17/07/2026 | historique des dividendes |
| « OPERATIONS EN COURS » | opérations annoncées | AFINHAB : première cotation du social bond le 01/12/2026 | calendrier |
| « AVIS » et « COMMUNIQUES » | tableaux (entité, n°, nature, objet) | vides le 20/11/2026 | alertes |
| Calendrier des AG de l'année (p. 16-18) | société, nature (Ordinaire, Extraordinaire, Mixte), date, heure, lieu, mentions « Annulé » ou « reportée » | ETI TG, AGO du 26/10/2026 « Annulé - communiqué du 23/10/2026 » | dates d'AG (§4.5) |

Le calendrier des AG est présent dans **tous** les BOC de fin d'année testés (2017 à 2025) et dans le BOC du 20/11/2026. Nous en avons extrait **487 AG** (354 ordinaires, 106 mixtes, 27 extraordinaires) pour 2017-2026. Conf. **H**.

### 1.5 Richbourse : les publications officielles et la presse rassemblées en un seul endroit

| Page | URL | Contenu et structure | Usage |
|---|---|---|---|
| Sitemap | https://www.richbourse.com/sitemap.xml | **6 325 URL** `/common/actualite/details/<date>-<slug>`, avec `<lastmod>`, de 2017-10-06 au 20/11/2026. Le slug contient la date et le titre : « 2019-04-04-boa-bf-etats-financiers-certifies-exercice-2018 », « 20-11-2026-note-dinformation-offre-publique-de-vente-des-actions-de-coris-bank-international-cote-divoire ». **Attention** : deux formats de date coexistent, AAAA-MM-JJ et JJ-MM-AAAA | historique des publications et des délais (§2, §5), **en une seule requête** |
| Publications officielles | https://www.richbourse.com/common/actualite | lignes `<div class="col-xs-12 ligne_paire|ligne_impaire">` avec date `JJ/MM/AAAA` et lien `/common/actualite/afficher-fichier/<slug>` (PDF). Liste déroulante par société. Pagination `?page=N` (317 pages) | relais quotidien des documents BRVM et AMF-UMOA |
| Catégories | https://www.richbourse.com/common/actualite-categorie/index/<cat> | 14 catégories : `etats-financiers`, `dividendes`, `convocations-projets-ago`, `communiques`, `notations-societes`, `augmentations-capital`, `fractionnements-actions`, `compositions-indice-brvm10`, `flottants-societes-brvm`, `commissaires-aux-comptes`, `infos-sgi-sgo`, `jours-feries`, `bilan-contrats-liquidite`, `obligations` | étiquetage gratuit des types d'événements |
| Revue de presse | https://www.richbourse.com/common/news/index | articles datés à la minute (« 20 Novembre 2026 - 17h:42 »), source entre parenthèses. Sur la 1re page lue, **les 20 articles viennent tous d'Agence Ecofin** | presse et sentiment (§3) |
| « Autres actualités » | https://www.richbourse.com/common/rss | malgré son URL, page **HTML** de dépêches régionales (allAfrica, APS, Togonews, Le Soleil) | contexte macro, peu utile par titre |
| Calendrier | https://www.richbourse.com/outils/calendrier/index | contenu chargé dynamiquement (non lisible par `curl`) | non utilisé |

Exemples de titres de la revue de presse (repris d'Agence Ecofin, lus le 22/11/2026, H) : « Oragroup accroît son bénéfice de 14 %, malgré le recul des crédits » (14/11/2026) ; « Bénin : le bénéfice de la BIIC bondit de 64 % à 35,8 millions $ » (12/11/2026) ; « FILTISAC : les ventes bondissent de 40 %, mais le résultat courant reste déficitaire » (03/11/2026) ; « Côte d'Ivoire : SMB renoue avec la croissance après son arrêt de maintenance » (02/11/2026) ; « BRVM : Coris Bank CI ouvre son capital aux investisseurs dès le lundi 30 novembre » (20/11/2026). Ces titres montrent les **connecteurs de contraste** (« malgré », « mais ») dont le lexique doit tenir compte (§3.4).

**Événement en cours (H, richbourse 20/11/2026, d'après Agence Ecofin et la note d'information)** : offre publique de vente de 20 % de Coris Bank International Côte d'Ivoire à **7 720 FCFA** par action, du 30/11 au 04/12/2026, pour environ 62,7 milliards de FCFA. Il faut créer un symbole et un historique pour cette nouvelle valeur dès sa première cotation.

### 1.6 Flux RSS : aucun flux utilisable

- `https://www.brvm.org/fr/taxonomy/term/1/feed` : RSS 2.0 valide, mais **sans aucun `<item>`** (522 octets, canal « newsletter categories »). Conf. H.
- Aucun lien `<link rel="alternate" type="application/rss+xml">` dans les pages de brvm.org et de richbourse lues. Conf. H.
- Flux RSS de Sika Finance, Financial Afrik, Agence Ecofin et Abidjan.net : **non vérifiés** (domaines inaccessibles, voir §1.1).
- **Conséquence** : la collecte se fait en **lisant régulièrement** les premières pages des listes. C'est léger : une page par liste suffit au quotidien.

### 1.7 Volume réel d'information (pour dimensionner le module)

Publications d'émetteurs relayées par richbourse (sitemap, H) : 564 en 2018, 626 en 2020, 741 en 2022, 776 en 2024, 713 en 2025, 725 en 2026 (au 20/11). Cela fait **environ 3 documents par séance** pour une cinquantaine de sociétés et quelques centaines de lignes obligataires. Le flux est **faible et surtout officiel** (PDF). Le défi n'est pas le volume, c'est l'**extraction des chiffres** contenus dans des PDF, parfois scannés.

---

## 2. Délai de diffusion de l'information (mesuré)

### 2.1 Délais mesurés (date du document → mise en ligne)

| Flux | Échantillon | Écart entre la date du nom de fichier et la date de mise en ligne | Heure de mise en ligne | Conf. |
|---|---|---|---|---|
| Communiqués (brvm.org) | 360 lignes, 2001-2026 | médiane **0 jour** ; 99 % le jour même ou le lendemain | non fournie (date seule) | H |
| Convocations d'AG (brvm.org) | 281 lignes, 2022-2026 | médiane 0 jour ; 97 % à J ou J+1 | non fournie | H |
| Avis BRVM | 300 avis, du 26/08/2025 au 17/11/2026 | médiane 0 jour ; 92 % à J ou J+1 | **55 % à 15h UTC ou plus tard** (après la séance), **38 % avant 9h45** (avant l'ouverture), **8 % pendant la séance continue** | H |
| Publications relayées par richbourse | 6 325 slugs, 2017-2026 | `<lastmod>` le jour même de la date du document : 42 % en 2017, 69 % en 2018, 77-80 % en 2019-2020, **93 à 96 % depuis 2021** | **72 % après 16h UTC** ; un second pic à 8h UTC (lot du matin) | M (`lastmod` peut correspondre à une mise à jour) |
| Convocation → date de l'AG | 252 AG appariées, 2022-2026 | médiane **18 jours** (p10 = 14 ; p25 = 15 ; p75 = 21 ; p90 = 24) | — | H |
| Avis de paiement → détachement | 299 cas, 2017-2026 | médiane **14 jours** (p10 = 10 ; p90 = 28) | — | H |

### 2.2 Presse contre source officielle

«TBD_PRESSLAG»

### 2.3 Ce que cela implique pour le code (H pour les faits, M pour la règle)
1. **Une information de la BRVM est presque toujours en ligne le jour même**, et le plus souvent **hors séance** : le soir (55 % des avis) ou tôt le matin (38 %). La règle de prudence est donc : un événement mis en ligne le jour J à `published_at` n'est négociable qu'**au fixing d'ouverture suivant** (9h45 UTC). Si `published_at` tombe avant 9h00 UTC, c'est le jour même ; sinon c'est le lendemain.
2. Avec seulement 8 % des avis publiés pendant la séance, il n'y a **pas d'avantage de vitesse à la seconde**. Il suffit de collecter **toutes les 2 à 3 heures** et de calculer les signaux **avant 9h00 UTC**.
3. L'avantage possible n'est pas la vitesse, c'est le **traitement** : lire un PDF de 80 pages, en extraire le résultat net et le dividende, et les comparer à l'historique, plus vite que l'investisseur moyen. Cet avantage n'est **pas mesuré** ici (§4.6).

---

## 3. Analyse de sentiment en français financier

### 3.1 Ce que dit la littérature (références connues, non relues en ligne dans cette session)

| Référence | Apport | Ce qu'on en retient pour la BRVM | Conf. |
|---|---|---|---|
| Loughran, T. & McDonald, B. (2011), « When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks », *Journal of Finance* 66(1), 35-65. https://doi.org/10.1111/j.1540-6261.2010.01625.x | Les dictionnaires généralistes (Harvard GI) classent à tort des mots financiers neutres comme négatifs (*liability*, *tax*, *cost*…). Les auteurs proposent des listes financières : négatif, positif, incertitude, litige, modalité forte et faible, contraignant | En français, « charges », « impôt », « dette », « provision pour risques », « capital » ne sont **pas négatifs en eux-mêmes**. Il faut un lexique **construit pour la finance**, pas une traduction d'un lexique général | M |
| Tetlock, P. (2007), « Giving Content to Investor Sentiment: The Role of Media in the Stock Market », *Journal of Finance* 62(3), 1139-1168. https://doi.org/10.1111/j.1540-6261.2007.01232.x | Un ton pessimiste de la presse annonce une baisse des cours, suivie d'un retour vers le niveau initial | À la BRVM, la presse est rare et décrit surtout des résultats déjà publiés. On s'attend à un effet **faible**, à tester | M |
| Malo, P. et al. (2014), « Good debt or bad debt: Detecting semantic orientations in economic texts », *JASIST* 65(4), 782-796. https://doi.org/10.1002/asi.23062 | Corpus « Financial PhraseBank » : phrases financières **en anglais** annotées positif/neutre/négatif | Modèle pour annoter un petit corpus BRVM en français (§3.6) | M |
| Araci, D. (2019), « FinBERT: Financial Sentiment Analysis with Pre-trained Language Models », arXiv:1908.10063. https://arxiv.org/abs/1908.10063 | BERT spécialisé sur des textes financiers anglais, entraîné sur la Financial PhraseBank | En **anglais seulement** : utilisable via traduction, mais les erreurs de traduction des chiffres et des négations sont un risque | M |
| Huang, A., Wang, H. & Yang, Y. (2023), « FinBERT: A Large Language Model for Extracting Information from Financial Text », *Contemporary Accounting Research* 40(2). https://doi.org/10.1111/1911-3846.12832 | Le FinBERT dédié au ton fait mieux que les dictionnaires et les méthodes classiques d'apprentissage sur des phrases de rapports | Confirme qu'un modèle affiné surpasse le lexique **quand on dispose de données annotées**. C'est la principale contrainte à la BRVM | M |
| Martin, L. et al. (2020), « CamemBERT: a Tasty French Language Model », ACL 2020. https://arxiv.org/abs/1911.03894 | Modèle BERT (RoBERTa) français, environ 110 M de paramètres en version *base* | Modèle de base recommandé pour un classifieur français affiné (§3.5, niveau 3) | M |
| Le, H. et al. (2020), « FlauBERT: Unsupervised Language Model Pre-training for French », LREC 2020. https://arxiv.org/abs/1912.05372 | Autre modèle de langue français | Alternative à CamemBERT | M |
| Djahoué, M. G. (2025), *Modern Economy* 16(11), 1802-1826. https://www.scirp.org/journal/paperinformation?paperid=147179 ; prépublication FIGARCH : https://www.researchgate.net/publication/404732210 | Un indice de **sentiment des investisseurs** construit sur la BRVM aide à prévoir la volatilité | Le sentiment est utile **pour le risque** (volatilité) plus que pour la direction du cours (document 02) | M / B (repris du document 02) |
| Adaptation française publiée du dictionnaire Loughran-McDonald | — | **Introuvable dans cette session** (aucune recherche possible). Nous ne citons aucune traduction « officielle ». Le lexique du §3.3 est **construit ici** | — |
| Modèle de sentiment financier en français prêt à l'emploi (type « FinBERT-FR ») | — | **Non vérifié** (huggingface.co inaccessible). Ne pas supposer qu'il existe. Prévoir d'annoter et d'affiner nous-mêmes | — |

### 3.2 Ce qui est propre au corpus BRVM : le sentiment est d'abord dans les chiffres

1. **La source principale est officielle** : états financiers, rapports d'activité, avis BRVM, convocations. Leur rédaction est normée, presque sans adjectifs. Le « ton » y apporte peu ; les **variations chiffrées** apportent beaucoup : résultat net (RN) N contre N−1, PNB, chiffre d'affaires, dividende proposé contre dividende précédent.
2. **La presse** (Agence Ecofin, Financial Afrik, Sika Finance, Abidjan.net) **reformule surtout les chiffres officiels**, avec des verbes de mouvement : « bondit », « accroît », « recule », « renoue avec la croissance », « reste déficitaire ». Pour les résultats, elle publie **après** le document officiel (§2). Son intérêt est d'ajouter du contexte (« malgré le recul des crédits ») et de résumer un PDF scanné.
3. **Les titres officiels sont des étiquettes d'événements** : « Changement important dans la Direction », « Notation Financière », « Franchissement de seuil », « Annulation de l'Assemblée Générale Ordinaire », « Levée de la suspension ». La première étape est donc de **classer l'événement** par expressions régulières (§6.4). Le sentiment ne vient qu'après.
4. **Conséquence pour l'architecture** : (a) classer le type d'événement (règles, environ 25 types) ; (b) extraire les nombres (RN, dividende, variation en %) ; (c) calculer un **sentiment numérique**, par exemple ΔRN en % et Δdividende en % ; (d) **ensuite seulement**, mesurer le ton lexical, surtout pour la presse et les communiqués libres.

### 3.3 Lexique BRVM-FR v0 (construit pour ce projet ; à valider sur annotations)

Poids : +2 ou −2 = signal fort ; +1 ou −1 = signal modéré ; « I » = incertitude (augmente le risque, pas la direction) ; « E » = étiquette d'événement (déclenche un type, pas un sentiment). Les expressions sont normalisées en minuscules, sans accents (`unidecode`), avec lemmatisation légère (« hausse », « hausses »).

**Positif**

| Expression (variantes) | Poids | Remarque |
|---|---:|---|
| hausse / progression / croissance / amélioration du résultat net, bénéfice en hausse, RN en hausse | +2 | à combiner avec la variation chiffrée quand elle existe |
| bénéfice record, résultat record, plus haut historique | +2 | |
| retour aux bénéfices, retour à la rentabilité, renoue avec les bénéfices ou la croissance | +2 | |
| bondit, s'envole, double, triple (appliqué à un bénéfice, un PNB ou un chiffre d'affaires) | +2 | verbes de presse (Ecofin) |
| hausse / progression du PNB, du produit net bancaire, du chiffre d'affaires, de la marge, de l'EBE | +1 | |
| dividende en hausse, relèvement du dividende, dividende record, acompte sur dividende | +2 | |
| attribution gratuite d'actions, augmentation de capital par incorporation de réserves | +1 | souvent liée au relèvement du capital minimum bancaire à 20 Md (document 06a) ; effet de cours à tester |
| fractionnement (du nominal, de l'action) | +1 | effet de liquidité, à tester (SONATEL 10:1, 26/10/2026) |
| relèvement / rehaussement de la notation, perspective positive, note confirmée à un niveau élevé | +1 | notation financière |
| baisse du coût du risque, baisse des créances en souffrance, amélioration du coefficient d'exploitation | +1 | banques |
| levée de la suspension, reprise de la cotation | +1 | |
| offre publique d'achat (OPA), offre publique de retrait (OPR), prime de … % | +2 | **pour la société visée** : une prime est probable |
| nouveau contrat, nouvelle concession, renouvellement de la convention, partenariat stratégique | +1 | |

**Négatif**

| Expression (variantes) | Poids | Remarque |
|---|---:|---|
| baisse / recul / repli / chute / contraction du résultat net, bénéfice en baisse | −2 | |
| perte nette, résultat net négatif, résultat déficitaire, reste déficitaire, déficit | −2 | « déficit » seul peut viser un État : vérifier le sujet |
| absence de dividende, pas de dividende, aucun dividende, suspension du dividende | −2 | ex. BOAN exercice 2025 (document 06a) |
| baisse / réduction du dividende | −2 | |
| hausse / dotation du coût du risque, dotations aux provisions en hausse, dépréciation, créances douteuses ou en souffrance en hausse | −1 | « provision » **seul** est neutre (piège Loughran-McDonald) |
| suspension de la cotation, titre suspendu | −2 | + filtre de risque (§6.6) |
| redressement judiciaire, liquidation, cessation d'activité, procédure collective | −2 | |
| capitaux propres inférieurs à la moitié du capital social, reconstitution des capitaux propres | −2 | règle de droit OHADA des sociétés (article non revérifié ici) |
| réserves des commissaires aux comptes, certification avec réserves, refus ou impossibilité de certifier, incertitude sur la continuité d'exploitation | −2 | |
| dégradation / abaissement de la notation, perspective négative, mise sous surveillance négative | −1 | |
| annulation / report de l'assemblée générale, sur instruction de la Commission Bancaire | −1 | ex. ETI, communiqué du 23/10/2026 |
| retard de publication, non-respect des obligations d'information, mise en demeure, sanction, amende, contentieux, litige | −1 | |
| augmentation de capital **en numéraire** (avec droits préférentiels de souscription) | −1 | dilution : à tester, ne pas supposer |
| démission du directeur général ou du PDG, départ, intérim | I | incertitude, pas direction |
| réduction de capital (pour apurer des pertes), radiation, retrait de la cote | −2 | |

**Incertitude (I)** : incertitude, contexte difficile, conjoncture défavorable, crise sécuritaire, sanctions (CEDEAO), tensions de trésorerie, sous réserve de, éventuel, susceptible de, en attente de l'autorisation, révision.

**Étiquettes d'événements (E)**, qui déclenchent un type (§6.4) : avis de convocation, projet de résolutions, paiement de dividendes, date ex-dividende, changement important dans la direction, franchissement de seuil, notation financière, rapport d'activité, états financiers, rapport des commissaires aux comptes, examen limité, première cotation, offre publique de vente, note d'information, augmentation de capital, fractionnement, regroupement, radiation, suspension, levée de la suspension.

### 3.4 Règles de calcul (à coder)

1. **Négation** : « pas de », « absence de », « aucun », « sans », « ne … pas », « non » jusqu'à 3 mots avant le terme : on **inverse** le signe. « Pas de dividende » vaut −2 ; « sans impact sur le résultat » vaut 0.
2. **Contraste** : avec « malgré », « en dépit de », « mais », « toutefois », « cependant », la proposition principale pèse ×1,0 et la proposition concédée ×0,5. « Oragroup accroît son bénéfice de 14 %, malgré le recul des crédits » donne +2 − 0,5 = +1,5.
3. **Intensité** : « fortement », « nettement », « significativement », « record », ou un pourcentage supérieur à 20 % : ×1,5. « Légèrement », « léger », « stable » : ×0,5.
4. **Nombres d'abord** : si l'expression `(résultat net|bénéfice net|RN|PNB|chiffre d'affaires)[^.]{0,80}?([+−-]?\d+[,.]?\d*)\s?%` est trouvée, le sentiment numérique vaut `s_num = clip(Δ%/25, −2, +2)`, qui **remplace** le sentiment lexical sur cet indicateur. Pour un dividende : `s_div = clip(Δdiv%/20, −2, +2)`, et s_div = −2 si le dividende est absent alors qu'il était versé l'an passé.
5. **Score d'un document** : `tone = (P − N) / (P + N + 1)`, où P et N sont les sommes pondérées. Score final de l'événement : `s = 0,7·s_num + 0,3·tone` si un nombre a été extrait, sinon `s = tone`.
6. **Agrégation par titre** : score de nouvelles du titre `S_i(t) = Σ_k s_k · exp(−(t − t_k)/τ)`, avec **τ = 10 séances** (hypothèse à valider). Prise en compte de la nouvelle à la **première séance qui suit sa date de mise en ligne**, ou à J+1 si elle est publiée après 14h30 UTC.

### 3.5 Modèles : du plus léger au plus lourd (tout doit tourner sans GPU)

| Niveau | Méthode | Matériel | Coût estimé | Quand l'utiliser | Paquets (vérifiés sur PyPI le 22/11/2026) |
|---|---|---|---|---|---|
| 0 | Règles + lexique §3.3 + extraction de nombres | CPU, < 1 ms par titre | nul | **par défaut**, explicable, adapté aux documents officiels | `rapidfuzz` 3.14.6 (MIT), `unidecode` 1.4.0 (**GPL**), `dateparser` 1.5.1 (BSD) |
| 1 | TF-IDF sur n-grammes de caractères (2-5) + régression logistique | CPU, < 5 ms | faible | dès qu'on a environ 500 titres ou paragraphes annotés | `scikit-learn` 1.9.1 (BSD-3) |
| 2 | Plongements multilingues (*sentence embeddings*) + régression logistique | CPU, environ 10 à 50 ms par phrase (ordre de grandeur, non mesuré ici) | faible | quand le vocabulaire varie (presse) | `sentence-transformers` 6.3.0 (Apache-2.0) ; **nom exact du modèle à vérifier** (Hugging Face inaccessible) |
| 3 | CamemBERT-base affiné, inférence ONNX quantifiée sur CPU | CPU pour l'inférence ; affinage possible sur CPU avec environ 1 000 exemples, mais lent | moyen | si le niveau 1 ou 2 plafonne et qu'on a au moins 1 000 annotations | `transformers` 5.24.0 (Apache-2.0), `onnxruntime` 1.32.0 (MIT) |
| — | Extraction de texte des PDF | CPU | — | **indispensable** (états financiers, avis) | `pdftotext` (poppler, installé dans la session) ; `pdfplumber` 0.11.11 ; `pymupdf` 2.1 (**AGPL** : attention à la licence) ; OCR des PDF scannés : `ocrmypdf` 17.14.2 (MPL-2.0) + Tesseract |
| — | Collecte HTML et RSS | CPU | — | — | `selectolax` 1.0.2 (MIT), `trafilatura` 2.3.1 (Apache-2.0), `feedparser` 6.0.14 (BSD-2) |

Versions et licences relevées via l'API JSON documentée de PyPI (`https://pypi.org/pypi/<paquet>/json`). Conf. **H**.

**Recommandation** : niveau 0 en production dès le départ. Niveau 1 après annotation. Les niveaux 2 et 3 ne servent que si la validation (§3.6) montre un gain réel **sur la prédiction des rendements**, et pas seulement sur l'exactitude de la classification. Un modèle de langage par API peut aider à **résumer et étiqueter** des PDF, mais seulement si chaque appel est journalisé avec sa date pour garder un historique « point-in-time ». Il ne sert jamais de signal de trading direct.

### 3.6 Protocole d'évaluation du sentiment

1. **Corpus** : 600 titres et premiers paragraphes, tirés au hasard et répartis par année (2018-2026) et par type, dans les publications richbourse, la revue de presse et les communiqués brvm.org.
2. **Annotation** : deux annotateurs, trois classes (négatif, neutre, positif), plus une classe « incertitude ». Objectif : **κ de Cohen ≥ 0,7**. Sinon, revoir le guide d'annotation.
3. **Métriques de classification** : F1 macro, avec un objectif de **≥ 0,75** pour le niveau 0 et de **≥ 0,80** pour le niveau 1.
4. **Métrique de valeur (décisive)** : corrélation de rang entre le score `s` et le rendement anormal [+1,+5] ou [+1,+20] après la mise en ligne, en walk-forward. On ne retient un niveau que si son IC est **> 0,05** et stable sur au moins 3 années.

---

## 4. Études d'événements à la BRVM

### 4.1 Littérature disponible

D'après le document 02, qui a pu faire des recherches avant l'épuisement du quota :
- une étude d'événement sur les **annonces de dividendes** (fenêtre [−20,+20], modèle de marché sur le BRVM Composite) a été publiée dans l'*European Scientific Journal* 13(22) en 2017 (https://eujournal.org/index.php/esj/article/download/9793/9297). Ses **chiffres n'ont pas été vérifiés**. Conf. B ;
- **aucune étude systématique sur le détachement** de dividende à la BRVM n'a été trouvée, seulement des anecdotes de presse (document 02, §4) ;
- aucune étude sur la dérive après publication des résultats (PEAD) à la BRVM n'a été trouvée.

Références générales sur la méthode (connues, non relues ici, conf. M) : Fama, Fisher, Jensen & Roll (1969), *International Economic Review* 10(1), 1-21, https://doi.org/10.2307/2525569 ; MacKinlay (1997), « Event Studies in Economics and Finance », *Journal of Economic Literature* 35(1), 13-39 ; Ball & Brown (1968), *Journal of Accounting Research* 6(2), 159-178, https://doi.org/10.2307/2490232 ; Bernard & Thomas (1989), « Post-Earnings-Announcement Drift », *Journal of Accounting Research* 27, 1-36, https://doi.org/10.2307/2491062 ; Elton & Gruber (1970), « Marginal Stockholder Tax Rates and the Clientele Effect », *Review of Economics and Statistics* 52(1), 68-74, https://doi.org/10.2307/1927599 ; Kalay (1982), *Journal of Finance* 37(4), 1059-1070 ; Lakonishok & Vermaelen (1986), *Journal of Financial Economics* 16(3), 287-319 ; Hartzmark & Solomon (2013), « The dividend month premium », *Journal of Financial Economics* 109(3), 640-660, https://doi.org/10.1016/j.jfineco.2013.03.011.

Ce dernier article documente sur les marchés américains un rendement anormal positif les mois où un dividende est attendu, qu'il attribue à une demande des investisseurs pour le dividende lui-même. C'est exactement le mécanisme que suggèrent nos résultats à la BRVM. Mais **l'ampleur y est bien plus faible**, et on ne peut pas transposer ses chiffres.

### 4.2 Méthode (reproductible)

- **Données** : `data/panel/adjusted_prices.parquet` (cours ajustés des divisions ; `tr_ret` = rendement **dividende net inclus** le jour du détachement), `equities.parquet` (ouverture, clôture, volume, valeur), `indices.parquet` (BRVM Composite).
- **Rendement anormal** : AR = `tr_ret` du titre − rendement du **BRVM Composite** (modèle « ajusté du marché », sans estimation de bêta, plus robuste sur des titres peu liquides). Limite : le Composite est un indice de prix. Il baisse lui-même pendant la saison des dividendes, ce qui gonfle légèrement les AR (environ 0,03 % par séance en moyenne, d'après un rendement moyen du marché d'environ 7 % par an ; estimation M).
- **Exclusions** : séances suivant un trou de plus de 7 jours calendaires dans le calendrier du titre (le **trou de mai à novembre 2021** dans les BOC téléchargés), AR absolus supérieurs à 50 % (artefacts). Toute fenêtre qui contient une telle séance est écartée.
- **Événements** : (a) **313 détachements officiels** (liste brvm.org, §1.2) d'actions cotées, de 04/2017 à 10/2026 ; (b) 294 détachements détectés dans les BOC (`dividends.parquet`), utilisés pour recouper ; (c) 459 AG ordinaires ou mixtes (calendrier des BOC) ; (d) publications de rapports (pages des émetteurs, §4.6).
- **Statistiques** : moyenne, médiane, t de Student en coupe et **t « par grappe »**. Pour ce dernier, on fait d'abord la moyenne des événements d'un même mois civil (beaucoup de détachements tombent les mêmes semaines), puis on calcule le t sur ces moyennes mensuelles.
- **Scripts** (dossier de travail de la session, à reprendre dans `brvm_alpha/events/`) : `evlib.py` (fenêtres et statistiques), `div_pages.py` (dividendes brvm.org), `ag_calendar.py` (AG des BOC), `official_div_study.py`, `listings.py`, `names.py` (table libellé → symbole).

**Recoupement des dates (H)** : sur les 274 détachements présents dans les deux sources, la date détectée dans les BOC est **identique** à la date officielle dans **246 cas (90 %)**. Les écarts viennent surtout du trou de 2021 et des événements détectés par simple estimation. Les montants concordent à 1 % près dans 78 % des cas : les écarts viennent des montants bruts ou nets selon le pays, et de saisies incohérentes. **Règle** : date officielle d'abord, BOC ensuite ; montant net du BOC d'abord.

### 4.3 Détachement de dividende : la baisse est incomplète, puis se rattrape

**Rendements anormaux autour de la date ex-dividende officielle** (313 événements ; rendement **dividende net inclus**, moins le Composite ; en %) :

| Fenêtre (séances) | n | Moyenne | Médiane | t | t par grappe (mois) | % > 0 |
|---|---:|---:|---:|---:|---:|---:|
| [−20,−1] | 292 | **+2,54** | +2,33 | 6,28 | 4,15 | 64 % |
| [−5,−1] | 302 | +0,88 | +0,54 | 3,36 | 2,91 | 55 % |
| **[0]** (jour du détachement) | 295 | **+2,48** | +2,65 | 12,42 | 8,10 | 79 % |
| [+1] | 302 | −0,44 | −0,39 | −2,46 | −0,74 | 39 % |
| [+1,+5] | 299 | −1,32 | −1,49 | −3,96 | −2,51 | 33 % |
| [+1,+20] | 283 | **−2,54** | −3,46 | −4,26 | −2,01 | 31 % |
| [+1,+60] | 275 | −2,21 | −2,46 | −2,26 | −0,34 | 40 % |

**Par sous-période** (moyenne / médiane, en %) :

| Fenêtre | 2017-2021 (n ≈ 120-136) | 2022-2026 (n ≈ 157-166) |
|---|---|---|
| [−20,−1] | +3,25 / +3,15 | +2,01 / +1,74 |
| [0] | +2,16 / +2,01 | +2,73 / +3,02 |
| [+1,+20] | −2,53 / −2,38 | −2,55 / −4,47 |

**Rapport baisse du cours / dividende (PDR)** = (clôture veille − clôture du jour de détachement) / dividende net, pour les titres échangés ce jour-là (279 cas) : **moyenne 0,51 ; médiane 0,46** (0,50 à l'ouverture). Par rendement du dividende : < 4 % → médiane **0,00** (51 cas) ; 4-7 % → 0,39 (94) ; 7-7,5 % → 0,46 (29) ; > 7,5 % → 0,57 (105). Le rendement net moyen des événements est de 6,7 % (médiane 6,8 %). Conf. **H**.

**Lecture** :
1. Le jour du détachement, le cours ne baisse qu'**environ de moitié du dividende net**. Celui qui détient le titre la veille encaisse le dividende et ne perd qu'environ la moitié en cours : il gagne **environ +2,5 %** de plus que le marché.
2. Cet écart **se résorbe ensuite** : −1,3 % en 5 séances et −2,5 % en 20 séances. Sur [0,+20], l'effet net est proche de zéro. Ce n'est donc pas un « cadeau » durable : le marché ajuste lentement.
3. Avant le détachement, les titres **montent** (+2,5 % en 20 séances). C'est cohérent avec une demande d'acheteurs qui veulent toucher le dividende, comme l'« effet du mois du dividende » de Hartzmark & Solomon (2013), mais nettement plus fort.
4. Explications possibles, **non testées** : clientèle locale qui achète pour le dividende ; faible liquidité et carnet d'ordres peu profond (document 01) ; absence de vente à découvert, qui empêche l'arbitrage de la baisse après le détachement ; fiscalité (IRVM retenu à la source, taux différent selon le pays de l'émetteur, document 01). Les PDR proches de 0 pour les petits dividendes suggèrent un **effet d'échelon de cotation et d'inertie** : un dividende de 2 % est vite noyé dans le bruit d'un titre peu échangé.

### 4.4 Fenêtre négociable : de l'avis de paiement au détachement

L'avis BRVM de paiement de dividendes (lien dans la liste officielle) fixe la date ex-dividende. **Délai avis → détachement** : médiane 14 jours calendaires (moyenne 20,2 ; p10 = 10 ; p25 = 12 ; p75 = 19 ; p90 = 28 ; n = 299). Cela fait **8 séances** (médiane, p10 = 6, p90 = 16) entre la première séance qui suit l'avis et le détachement. **Délai détachement → paiement** : médiane 2 jours (1 à 5 jours dans 97 % des cas). Conf. **H**.

| Stratégie testée (hors coûts, en %) | n | Moyenne | Médiane | t | % > 0 |
|---|---:|---:|---:|---:|---:|
| AR de la 1re séance après l'avis (réaction à l'annonce) | 275 | +0,20 | +0,08 | 1,46 | 53 % |
| Achat à la clôture de la 1re séance après l'avis, vente la veille du détachement (sans dividende) | 290 | +1,64 | +1,09 | 4,38 | 59 % |
| **Achat à la clôture de la 1re séance après l'avis, vente à la clôture du jour de détachement (dividende inclus), contre le Composite** | 276 | **+4,07** | **+4,19** | 9,80 | **78 %** |
| Idem, rendement brut sans soustraire le Composite | 294 | +5,08 | +4,57 | 10,66 | 79 % |
| Idem, mais vente 20 séances après le détachement | 267 | +1,14 | +0,69 | 1,69 | 53 % |

**Par année** (moyenne / médiane de la stratégie principale, en %) : 2017 : 3,5 / 5,0 ; 2018 : 5,9 / 6,0 ; 2019 : 5,0 / 5,0 ; 2020 : 2,7 / 1,0 ; 2021 : 5,0 / 5,0 (10 cas) ; 2022 : 5,2 / 5,6 ; 2023 : 6,4 / 6,2 ; 2024 : 3,4 / 4,2 ; **2025 : 2,8 / 3,1 ; 2026 : 1,5 / 2,1**. L'effet **diminue nettement** depuis 2024.

**Par rendement du dividende** : < 4 % → +1,3 % (54 % positifs, 50 cas) ; 4-7 % → +4,9 % (79 %, 92 cas) ; > 7 % → +4,5 % (76 %, 134 cas).

**Par liquidité** (valeur médiane échangée par séance sur les 60 séances précédentes) : < 5 M FCFA → +4,3 % (175 cas) ; 5-20 M → +4,5 % (72) ; **> 20 M → +1,7 %** (29). L'effet est **plus faible sur les titres liquides**, là où l'arbitrage est possible. La capacité de la stratégie est donc **limitée**.

**Après coûts** : avec un aller-retour de 1,7 % à 2,8 % hors demi-écart (document 01, §5), le gain net moyen est de **+2,4 % à +1,3 %** par opération (64 % à 56 % de cas gagnants). En ne gardant que les rendements ≥ 4 % (226 cas) : **+3,0 % à +1,9 %** (68 % à 59 % de cas gagnants). Un dividende ne se capte qu'une fois par an et par titre, et 90 % des détachements tombent entre mai et septembre. Ce signal **ne peut donc pas porter une stratégie à lui seul** : c'est une **surcouche saisonnière** (§6.5, S1). Conf. **H** pour les calculs bruts, **M** pour les coûts.

### 4.5 Assemblées générales ordinaires

459 AGO ou AG mixtes (BOC, 2017-2026). **Délai AGO → détachement** pour les 310 AG suivies d'un détachement dans les 150 jours : **médiane 42 jours** (moyenne 50,4 ; p10 = 22 ; p25 = 28 ; p75 = 67 ; p90 = 91). Conf. **H**.

| Fenêtre autour de la date de l'AGO (en %) | Toutes (n = 459) : moyenne / médiane / t | Avec dividende ensuite (n = 310) | Sans dividende (n = 149) |
|---|---|---|---|
| [−20,−1] | +1,84 / +1,20 / 2,80 (n = 453) | **+2,91 / +2,12 / 4,44** (t par grappe 3,91) | −0,42 / −0,61 / −0,28 |
| [0,+1] | +0,36 / +0,04 / 1,89 | +0,20 / +0,03 / 0,98 (t par grappe 0,46) | +0,67 / +0,08 / 1,73 |
| [+1,+20] | +2,43 / +1,42 / 4,28 | +2,07 / +2,03 / 3,79 ; **prix seul : −0,07 / +0,02 / −0,13** | +3,18 / −0,41 / 2,40 (moyenne tirée par quelques valeurs extrêmes) |

**Lecture (H pour les chiffres, M pour l'interprétation)** :
1. **L'AG elle-même n'est pas une nouvelle** : le rendement anormal sur [0,+1] est nul (+0,20 %, t par grappe 0,46). Le dividende proposé est en général connu avant, par le communiqué des résultats annuels ou le projet de résolutions.
2. **Les titres qui versent ensuite un dividende montent avant l'AG** : +2,9 % sur les 20 séances qui précèdent (61 % de cas positifs, t par grappe 3,9). Ceux qui n'en versent pas ne montent pas (−0,4 %). C'est la même demande liée au dividende qu'au §4.3, qui commence **environ 2 mois avant le détachement**.
3. Le gain apparent sur [+1,+20] après l'AG (+2,1 %) **disparaît en prix seul** (−0,07 %). Il vient du dividende encaissé quand le détachement tombe dans la fenêtre (26 % des AG ont un détachement dans les 28 jours). Ce n'est pas un signal séparé.
4. **Utilisation possible (à tester)** : ce qu'on sait à l'avance, c'est si le titre a versé un dividende l'an passé et la date de l'AG. Le délai entre convocation et AG (§2) fixe le moment le plus tôt où l'on peut agir.

### 4.6 Publication des états financiers et des rapports d'activité

«TBD_SECTION46»

### 4.7 Suspensions de cotation

Épisodes de suspension (statut `suspended` dans le panel, 2017-2026) : **14 épisodes**, sur 10 titres. Certains durent des années : SVOC (MOVIS) 1 359 séances de 2019 à 2025 ; SEMC 490 séances de 2024 à 2026, puis de nouveau suspendu depuis le 16/09/2026 ; TTRC en liquidation. Exemples courts : SCRC suspendu 4 séances en septembre 2026 (−5,8 % à la reprise) ; UNLC 18 séances en 2025 (−7,0 % à la reprise). Le 20/11/2026, **SICC et SEMC sont toujours suspendus** (document 01). Conf. **H**.

**Règle** : une suspension est un **risque de liquidité** (on ne peut plus vendre), pas un signal statistique. L'échantillon est trop petit pour mesurer un rendement moyen. On exclut le titre des nouveaux achats et on l'alerte au premier avis de suspension (§6.6).

### 4.8 Lecture critique de ces études

1. **Échantillon** : de 283 à 313 détachements, regroupés dans le temps (67 mois-grappes). Les t par grappe (de 2 à 8) restent significatifs pour [0], [−20,−1] et [+1,+5]. [+1,+20] est à la limite (t = −2,0).
2. **Choix multiples** : nous avons testé environ 10 fenêtres et 4 découpages. Avec la correction de Bonferroni (10 tests, seuil |t| > 2,8), [0], [−20,−1] et la fenêtre négociable restent significatifs ; [+1,+20] **ne l'est plus** en t par grappe.
3. **Marché haussier** : 2021-2026 a été très haussier (Composite +42,6 % depuis le 1er janvier 2026, BOC du 20/11/2026). L'ajustement par le Composite neutralise l'essentiel, mais pas tout.
4. **Déclin** : la fenêtre « avis → détachement » passe de +6,4 % (2023) à +1,5 % (2026). C'est cohérent avec une anomalie de plus en plus connue et exploitée (richbourse publie par exemple un « suivi des dates » et un outil de « saisonnalité »). **Hypothèse de travail : l'effet futur vaut au mieux la moitié de la moyenne historique.**
5. **Exécution** : les calculs utilisent la clôture. Le fixing de clôture (14h30 UTC) et la file d'attente aux limites ±7,5 % peuvent empêcher d'acheter au prix voulu (document 01).

---

## 5. Calendrier type de l'information

### 5.1 Répartition mensuelle observée (part des événements de chaque type, en %)

Sources : AG = calendriers des BOC 2017-2026 (459 AGO ou mixtes, H) ; détachements = liste officielle brvm.org (313, H) ; publications = slugs datés du sitemap richbourse, 2018-2025 (catégories déduites du titre par mots-clés : la date est celle du document relayé, conf. M).

| Mois | AGO / mixtes | Détachements | États financiers annuels | Rapports T1 | S1 (activité et comptes) | T3 | Avis « dividendes » (relais) | Notations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Janv. | 0 | 0 | 0 | 0 | 9 | 3 | 0 | 13 |
| Févr. | 0 | 0 | 3 | 0 | 1 | 0 | 0 | 10 |
| Mars | 5 | 0 | 10 | 0 | 1 | 0 | 0 | 2 |
| **Avril** | 20 | 4 | **30** | **46** | 1 | 0 | 18 | 2 |
| **Mai** | 17 | 20 | 17 | **41** | 1 | 1 | 13 | 3 |
| **Juin** | **43** | 14 | 15 | 7 | 0 | 0 | 20 | 7 |
| **Juillet** | 3 | **31** | 9 | 2 | 15 | 0 | **27** | 12 |
| Août | 1 | 12 | 4 | 1 | 6 | 0 | 11 | 10 |
| Sept. | 2 | 13 | 3 | 1 | 10 | 0 | 7 | 8 |
| **Oct.** | 3 | 2 | 3 | 1 | **40** | **55** | 2 | 9 |
| Nov. | 3 | 1 | 3 | 0 | 12 | 25 | 1 | 8 |
| Déc. | 3 | 2 | 2 | 0 | 3 | 15 | 1 | 17 |
| **Effectif** | 459 | 313 | 556 | 290 | 676 | 266 | 289 | 277 |

**Cumul des états financiers annuels** : 3 % fin février, 13 % fin mars, **44 % fin avril**, 61 % fin mai, 76 % fin juin, 85 % fin juillet, 92 % fin septembre. Une partie des publications tardives correspond à des **rediffusions** : comptes « certifiés et approuvés » après l'AG, rapports des commissaires aux comptes, états consolidés IFRS. Exemple : BOA CI a publié ses états financiers 2024 le 02/04/2025, et le fichier « rapport des commissaires aux comptes et états financiers annuels – exercice 2025 » est daté du 12/06/2026. Conf. M.

### 5.2 Calendrier type d'une société qui verse un dividende (médianes observées)

| Étape | Date type | Écart | Source | Conf. |
|---|---|---|---|---|
| Clôture de l'exercice | 31/12/N | — | — | H |
| Publication des comptes annuels N, souvent avec le dividende proposé | **mars-avril N+1** (44 % avant fin avril) | — | §5.1 | M |
| Rapport d'activité T1 | **avril-mai N+1** (87 %) | — | §5.1 | M |
| Convocation de l'AGO (mise en ligne sur brvm.org) | AGO − **18 jours** (médiane ; p10 = 14 ; p90 = 24 ; 252 cas, 2022-2026) | — | §2 | H |
| AGO (approbation des comptes, vote du dividende) | **juin** (43 %) ; 88 % avant le 30/06 (hors 2020) | — | §4.5 | H |
| Avis BRVM de paiement de dividendes | environ AGO + 4 semaines | — | §4.4-4.5 | M |
| Détachement (date ex-dividende) | AGO + **42 jours** (médiane) ; avis + **14 jours** ; mai-septembre (90 %) | — | §4.4 | H |
| Paiement | ex + **2 jours** (médiane) | — | §4.4 | H |
| Rapport S1 (activité, puis comptes semestriels avec examen limité) | juillet (activité) ; **octobre** (comptes) | — | §5.1 | M |
| Rapport T3 | **octobre-novembre** (80 %) | — | §5.1 | M |

**Règles juridiques (à vérifier sur les textes)** : le droit OHADA des sociétés impose une AGO dans les six mois qui suivent la clôture. Les 88 % d'AGO tenues avant le 30 juin vont dans ce sens, mais **l'article n'a pas été relu dans cette session** (conf. B). Les délais de publication de l'information périodique imposés par l'AMF-UMOA et le Règlement général de la BRVM (comptes annuels, semestriels, trimestriels) n'ont **pas pu être lus** : `amf-umoa.org` est inaccessible, et les textes de brvm.org n'ont pas été ouverts. Un avis BRVM n° 214-2026 du 22/07/2026 porte sur le respect de la diffusion de l'information financière (document 01), ce qui montre que des retards existent. **Pour le code**, il faut des seuils empiriques, pas juridiques : comptes annuels « en retard » s'ils ne sont pas publiés au **31 mai** (61 % publiés à cette date) et « très en retard » au **30 juin** (76 %).

### 5.3 Saisonnalité qui en découle pour le portefeuille

- **Mars à juin** : période des résultats annuels et des montants de dividende → contrôles fondamentaux et mise à jour des facteurs (documents 03 et 06a).
- **Avril à septembre** : période des dividendes → signaux S1 et S2 (§6.5). Les détachements de juillet (31 %) font baisser mécaniquement le Composite, qui est un indice de prix.
- **Octobre-novembre** : comptes S1 et rapports T3 → révision des bénéfices sur 12 mois glissants.
- **Décembre à février** : peu d'information propre aux émetteurs. Notations financières (13 à 17 % en décembre-janvier), avis d'indices, macro (document 05).

---

## 6. Spécification chiffrée du module « actualité + événements »

### 6.1 Architecture (paquet proposé : `brvm_alpha/events/`)

```
collect/        collecteurs polis (brvm.org, BOC, richbourse), cache HTTP, journal des requêtes
  brvm_lists.py     listes Drupal (annonces, OST, avis, dividendes), page 0 → N jusqu'à une URL déjà vue
  brvm_issuers.py   pages /fr/rapports-societe-cotes/<slug> (1 passage par nuit)
  boc_events.py     sections du BOC : AG, OPERATIONS EN COURS, AVIS, COMMUNIQUES, mentions (d)/SP
  richbourse.py     sitemap.xml (delta quotidien), /common/actualite, /common/news/index
docs/           téléchargement unique des PDF (clé = sha256 de l'URL), pdftotext, OCR si < 200 caractères/page
normalize/      libellé → symbole (table + rapidfuzz ≥ 90), dates (ISO, nom de fichier, slug), fuseau UTC
classify/       type d'événement par règles (§6.4), puis lexique et nombres (§3.3-3.4)
store/          tables parquet point-in-time : events, documents, fetch_log
signals/        S1 à S5 (§6.5), filtres de risque R1 à R8 (§6.6)
report/         alertes quotidiennes, calendrier des 30 prochains jours (AG, détachements, publications attendues)
```

### 6.2 Collecte : URL, fréquences, politesse

| Collecteur | URL | Fréquence (jours de séance) | Requêtes/jour | Arrêt de la pagination | Conf. |
|---|---|---|---:|---|---|
| BOC | page des BOC + PDF du jour (déjà dans `boc_download.py`) | 1 fois, vers 19h UTC, nouvel essai à 23h | 2-3 | — | H |
| Annonces (6 listes) | `/fr/emetteurs/type-annonces/{communiques, convocations-assemblees-generales, changements-de-dirigeants, franchissements-de-seuil, notations-financieres, projets-de-resolution}` | toutes les 3 h, de 8h à 23h UTC (6 passages) | 36 | arrêt à la 1re URL de PDF déjà connue | H |
| OST (4 listes) | `/fr/esv/{paiement-de-dividendes, augmentation-de-capital, fractionnement, radiation}` | 6 passages | 24 | idem | H |
| Avis | `/fr/marche/avis-et-publications/avis` | 6 passages | 6 | idem | H |
| Rapports des émetteurs | `/fr/rapports-societe-cotes/<slug>` (50 actions) | 1 fois par nuit (3h UTC) | 50 | page 0 seulement | H |
| PDF nouveaux | `https://www.brvm.org/sites/default/files/...` | dès détection | environ 3 à 10 | — | H |
| Richbourse | `/sitemap.xml` (1 fois par jour) ; `/common/actualite` et `/common/news/index`, page 0 | 1 + 2 × 6 | 13 | — | H |
| Sika Finance, Financial Afrik, Agence Ecofin, Abidjan.net | **désactivés par défaut** | — | 0 | à activer seulement avec un flux RSS ou une API officielle, ou une autorisation écrite ; **jamais de contournement anti-robot** | — |

Total : environ 130 à 140 requêtes par jour vers brvm.org. Avec 10 s entre deux requêtes, cela fait environ 23 minutes de collecte par jour, étalées. `User-Agent` explicite avec un contact, cache `ETag` / `If-Modified-Since`, et arrêt automatique sur une réponse HTTP 403, 429 ou 5xx (3 essais avec attente exponentielle, puis alerte).

### 6.3 Table `events` (point-in-time)

| Colonne | Type | Description |
|---|---|---|
| `event_id` | str | sha1(source, url_document, type) |
| `symbol` | str | symbole BRVM (NaN pour un événement de marché) |
| `event_type` | enum | §6.4 |
| `source` | enum | `brvm_list`, `brvm_issuer`, `boc`, `richbourse_pub`, `richbourse_press` |
| `source_url`, `doc_url` | str | page et PDF |
| `doc_date` | date | date du document : nom du fichier, colonne date ou slug |
| `published_at` | datetime UTC | **première fois où notre collecteur l'a vu**. Pour l'historique antérieur à la collecte : `doc_date` + 1 séance, par prudence |
| `first_tradable_session` | date | 1re séance dont le fixing d'ouverture (9h45 UTC) suit `published_at` |
| `title`, `text_sha256`, `n_pages`, `ocr` | — | traçabilité |
| `fiscal_period` | str | `2025A`, `2026Q1`, `2026S1`, `2026Q3` |
| `rn`, `rn_prev`, `rn_growth` | float | résultat net extrait et variation |
| `div_net`, `div_prev`, `div_growth`, `ex_date`, `pay_date` | float/date | dividende |
| `ag_date`, `ag_type` | date/enum | AG |
| `s_num`, `tone`, `score` | float | §3.4 |
| `extract_conf` | float 0-1 | confiance de l'extraction (1 = champ structuré, 0,6 = regex sur un PDF texte, 0,3 = OCR) |
| `version` | int | nouvelle version si le document est corrigé (on garde toutes les versions) |

### 6.4 Types d'événements et règles de détection (sur le titre, insensibles à la casse et aux accents)

| Type | Expression régulière (titre) | Source principale |
|---|---|---|
| `DIV_NOTICE` | `paiement de dividendes?` | `/fr/esv/paiement-de-dividendes`, avis |
| `AG_CONVOCATION` | `avis de convocation` | liste des convocations |
| `AG_RESOLUTIONS` | `projets? de r[eé]solutions?` | liste des projets de résolution |
| `AG_CANCEL` | `annulation.*assembl|report.*assembl` | communiqués, calendrier des AG du BOC (« Annulé ») |
| `RES_ANNUAL` | `[eé]tats financiers.*exercice|commissaires aux comptes|comptes annuels` (sans `trimestre|semestre`) | rapports des émetteurs |
| `RES_S1` | `semestre|semestriel|examen limit[eé]` | idem |
| `ACT_Q1`, `ACT_Q3` | `1er trimestre`, `3(e|[eè]me) trimestre` | idem |
| `RATING` | `notation financi[eè]re` | liste des notations |
| `MGMT_CHANGE` | `changement important dans la direction|nomination` | liste des dirigeants, communiqués |
| `THRESHOLD` | `franchissement de seuils?` | liste des seuils |
| `CAP_INC` | `augmentation de capital` (+ `num[eé]raire` → dilution ; `incorporation de r[eé]serves` → gratuite) | `/fr/esv/augmentation-de-capital` |
| `SPLIT` / `REVERSE_SPLIT` | `fractionnement` / `regroupement|consolidation` | `/fr/esv/fractionnement` |
| `OPV_IPO` | `offre publique de vente|introduction en bourse|premi[eè]re cotation` | avis, richbourse |
| `TAKEOVER` | `offre publique d'achat|OPA|offre publique de retrait|OPR` | avis, communiqués |
| `SUSPENSION` / `RESUMPTION` | `suspension` / `lev[eé]e de la suspension|reprise de la cotation` | avis, mention `SP` du BOC |
| `DELISTING` | `radiation` | `/fr/esv/radiation` |
| `INDEX_CHANGE` | `composition.*(BRVM ?30|prestige|BRVM ?10)` | avis |
| `REGULATOR` | `AMF-UMOA|CREPMF|sanction|mise en demeure` | richbourse (publications officielles) |
| `PRESS` | tout article de la revue de presse | richbourse |

### 6.5 Signaux (paramètres de départ, **tous à valider hors échantillon**)

**S1 — Capture du dividende (surcouche saisonnière)**
- Déclencheur : `DIV_NOTICE` avec `ex_date` connue.
- Conditions : rendement net `div_net / close` **≥ 4 %** ; valeur médiane échangée sur 60 séances **≥ 1 M FCFA** ; pas de filtre R1-R8 actif ; au moins **3 séances** entre `first_tradable_session` et `ex_date`.
- Entrée : achat à la **1re séance négociable après l'avis**. Ordre à cours limité = clôture de la veille × 1,02, valable jusqu'à 3 séances avant le détachement.
- Sortie : vente au **fixing de clôture du jour de détachement**. Le dividende est payé environ 2 jours plus tard.
- Taille : ≤ **5 %** du portefeuille par titre ; ≤ **20 %** au total pour S1 ; ≤ **10 %** de la valeur médiane échangée × nombre de séances jusqu'au détachement (limite de capacité).
- Performance historique, dans l'échantillon, contre le Composite : +4,1 % brut par opération (médiane +4,2 %) ; **+1,3 à +2,4 % net** de 1,7 à 2,8 % de coûts. **Hypothèse de planification : +0,5 à +1,0 % net par opération**, soit la moitié, à cause du déclin observé en 2025-2026.
- Critères d'arrêt : si, sur les 30 dernières opérations, le gain net moyen est ≤ 0 ou la part de gagnants < 50 %, S1 est suspendu.

**S2 — Ne pas acheter juste après un détachement**
- Pendant **20 séances** après `ex_date` : malus de −0,5 écart-type sur le score d'achat du titre dans le modèle multifacteur (document 04). Base : CAR[+1,+20] = −2,5 % en moyenne, médiane −3,5 %.
- On **ne force pas de vente** à cause de S2 (le coût d'un aller-retour dépasse l'effet). Mais si le modèle prévoit déjà de vendre un titre dans la saison, la vente est **avancée au jour du détachement**.

**S3 — Montée avant l'AGO pour les titres qui versent un dividende (variante précoce de S1)**
- Déclencheur : `AG_CONVOCATION` pour une AGO, si le titre a versé un dividende l'an passé et qu'aucun communiqué n'annonce une baisse ou une absence de dividende.
- Signal : bonus de +0,25 écart-type sur le score d'achat entre la convocation et le jour de l'AG. Base : CAR[−20,−1] avant l'AGO = +2,9 % pour les titres qui versent ensuite un dividende. **Ne pas cumuler** avec S1 au-delà de la limite de taille de S1.
- **Test de faisabilité (H)** : la convocation n'est publiée que **18 jours** (médiane) avant l'AG, soit environ 10 séances. Sur la fenêtre réellement négociable (achat à la clôture de la séance qui suit la convocation, vente la veille de l'AG ; 146 AG de 2022-2026 pour des titres qui avaient versé un dividende l'année précédente), le gain est de **+1,36 % en moyenne** (médiane +1,19 %, 56 % de cas positifs). C'est **en dessous des coûts** d'un aller-retour. Conclusion : S3 n'est **pas une stratégie autonome**. On le garde au mieux comme bonus de score pour un titre que l'on achèterait de toute façon (désactivé par défaut).

**S4 — Réaction aux publications de résultats**
«TBD_S4»

**S5 — Score de nouvelles (variable explicative)**
- `S_i(t) = Σ_k s_k · exp(−(t − t_k)/10)` (§3.4), calculé à `first_tradable_session`.
- Poids initial **0** dans le modèle multifacteur. Il ne devient positif que si l'IC walk-forward est **> 0,05** sur au moins 3 années (document 04, §IC).

### 6.6 Filtres de risque (priorité sur les signaux)

| Code | Événement | Action | Durée |
|---|---|---|---|
| R1 | `SUSPENSION` (avis ou mention `SP`) | aucun achat ; alerte sur les positions détenues ; valorisation au dernier cours avec une décote de risque de liquidité de 10 % pour le calcul du risque | jusqu'à `RESUMPTION` + 5 séances |
| R2 | `AG_CANCEL`, surtout sur instruction d'un régulateur (ex. ETI, 23/10/2026, Commission Bancaire de l'UMOA) | −1 sur le score de gouvernance ; aucun nouvel achat avant le communiqué suivant | 60 séances |
| R3 | Réserves ou refus de certification, doute sur la continuité d'exploitation, capitaux propres < ½ du capital (lexique §3.3) | exclusion des achats ; révision manuelle | jusqu'aux comptes suivants |
| R4 | `RATING` avec dégradation ou perspective négative | poids maximal × 0,5 | 120 séances |
| R5 | `CAP_INC` en numéraire (droits) | pas de nouvel achat avant le détachement des droits ; recalcul du nombre d'actions | jusqu'au détachement |
| R6 | `TAKEOVER` (OPA, OPR) ou `OPV_IPO` sur le titre | gel des signaux automatiques ; analyse manuelle de la prime | jusqu'au résultat de l'offre |
| R7 | Comptes annuels non publiés au 31/05 (au 30/06 pour le niveau rouge) | alerte « retard » ; −0,5 sur le score de qualité | jusqu'à la publication |
| R8 | `SPLIT` / `REVERSE_SPLIT` | contrôle du facteur d'ajustement (`detect_corporate_actions`) avant tout calcul de signal | 5 séances |

### 6.7 Configuration (prête à coder)

```yaml
events:
  collect:
    brvm:
      base_url: "https://www.brvm.org"
      crawl_delay_s: 10                 # robots.txt (22/11/2026)
      user_agent: "BRVM-Alpha/0.1 (recherche; contact: <a renseigner>)"
      schedule_utc: ["08:00","11:00","14:00","17:00","20:00","23:00"]
      lists:
        - /fr/emetteurs/type-annonces/communiques
        - /fr/emetteurs/type-annonces/convocations-assemblees-generales
        - /fr/emetteurs/type-annonces/changements-de-dirigeants
        - /fr/emetteurs/type-annonces/franchissements-de-seuil
        - /fr/emetteurs/type-annonces/notations-financieres
        - /fr/emetteurs/type-annonces/projets-de-resolution
        - /fr/esv/paiement-de-dividendes
        - /fr/esv/augmentation-de-capital
        - /fr/esv/fractionnement
        - /fr/esv/radiation
        - /fr/marche/avis-et-publications/avis
      issuer_reports: {path: "/fr/rapports-societe-cotes/{slug}", schedule_utc: "03:00", pages: [0]}
      stop_on_http: [403, 429]
      max_retries: 3
    richbourse:
      sitemap: "https://www.richbourse.com/sitemap.xml"   # 1 fois par jour
      pages: ["/common/actualite", "/common/news/index"]
      min_delay_s: 10
      disallow_prefixes: ["/investisseur/", "/api/", "/site/premium", "/garde/"]
    disabled_sources: [sikafinance, financialafrik, agenceecofin, abidjan_net]   # pas de contournement anti-robot
  docs:
    pdf_text_tool: pdftotext
    ocr_if_chars_per_page_below: 200
    ocr_tool: ocrmypdf
  timing:
    session_close_utc: "15:00"
    news_cutoff_utc: "14:30"          # après le fixing de clôture → exploitable à J+1
    first_tradable: "next_open_fixing" # 09:45 UTC
  sentiment:
    level: 0                          # 0 = lexique + nombres ; 1 = TF-IDF + logit après annotation
    negation_window_tokens: 3
    concession_weight: 0.5
    intensifier_mult: 1.5
    attenuator_mult: 0.5
    num_scale_rn_pct: 25              # s_num = clip(Δ%/25, -2, 2)
    num_scale_div_pct: 20
    w_num: 0.7
    w_tone: 0.3
    decay_tau_sessions: 10
  signals:
    S1_dividend_capture:
      enabled: true
      min_net_yield: 0.04
      min_median_value_60d_fcfa: 1_000_000
      min_sessions_to_ex: 3
      entry: "first_tradable_after_notice"
      limit_price_mult: 1.02
      exit: "close_fixing_ex_date"
      max_weight_per_name: 0.05
      max_weight_total: 0.20
      max_participation: 0.10         # du volume médian × séances jusqu'au détachement
      expected_net_per_trade: [0.005, 0.010]   # hypothèse prudente (½ de l'historique)
      kill_switch: {lookback_trades: 30, min_mean_net: 0.0, min_hit_rate: 0.50}
    S2_post_ex_penalty: {enabled: true, sessions: 20, score_penalty_sd: -0.5, force_sell: false}
    S3_pre_ago: {enabled: false, score_bonus_sd: 0.25, require_prev_year_dividend: true}   # à activer après validation
    S4_earnings_reaction: «TBD_S4YAML»
    S5_news_score: {weight: 0.0, min_ic: 0.05, min_years: 3}
  risk_filters:
    R1_suspension: {block_buys: true, resume_buffer_sessions: 5, liquidity_haircut: 0.10}
    R2_ag_cancel: {governance_penalty: -1, sessions: 60}
    R3_audit_going_concern: {exclude: true}
    R4_rating_downgrade: {max_weight_mult: 0.5, sessions: 120}
    R5_rights_issue: {block_buys_until_rights_detached: true}
    R6_takeover_ipo: {freeze_auto_signals: true}
    R7_late_annual_accounts: {amber: "05-31", red: "06-30", quality_penalty: -0.5}
    R8_split_check: {sessions: 5}
```

### 6.8 Plan de validation (cohérent avec le document 04)

1. **Données point-in-time** : avant la mise en service du collecteur, `published_at` = `doc_date` + 1 séance. Après, horodatage réel. Les écarts entre les deux sont mesurés tous les mois.
2. **Découpage** : apprentissage 2017-2022 ; test 2023-2026, **sans réglage** des paramètres du §6.7 sur la période de test. Les seuils de rendement (4 %) et de durée (20 séances) ont été choisis **en voyant tout l'échantillon** : ils sont donc **optimistes**. La validation doit au minimum tester les valeurs voisines (3 %, 5 % ; 10 et 30 séances) et garder le même signe.
3. **Exécution simulée** : entrée au fixing de la séance négociable, à cours limité. Rejet de l'ordre si le cours touche la limite +7,5 % (file d'attente). Coûts de 1,7 à 2,8 % + demi-écart (document 01). Participation ≤ 10 % du volume.
4. **Critères d'acceptation de S1** : gain net moyen ≥ **+0,5 %** par opération sur 2023-2026 ; part de gagnants ≥ **55 %** ; t par grappe ≥ **2** ; pas plus de 2 années négatives sur 4.
5. **Suivi en production** : tableau mensuel des AR réalisés par type d'événement, comparés aux attentes du §4, et application du critère d'arrêt de S1.

---

## 7. Limites et questions ouvertes

**Limites de ce document**
1. **Aucune recherche web possible** (quota épuisé) et **réseau restreint** à brvm.org, richbourse.com et pypi.org. Les sites de presse (Sika Finance, Financial Afrik, Agence Ecofin, Abidjan.net), du régulateur (AMF-UMOA), de la BCEAO, des modèles (Hugging Face) et des articles (arXiv, SSRN, sraf.nd.edu) **n'ont pas été vérifiés**. Leur structure HTML et leurs flux RSS éventuels restent à décrire.
2. **Études d'événements dans l'échantillon** : les paramètres de §6.5 ont été choisis en voyant toutes les données 2017-2026. Il y a donc un biais d'optimisme (document 04).
3. **Trou de données de mai à novembre 2021** dans les BOC téléchargés : les événements correspondants sont écartés, ce qui fait environ 20 détachements perdus.
4. **Dates de publication approximatives** : pour les rapports par émetteur, la date vient du **nom du fichier PDF**. Elle peut différer de l'heure réelle de mise en ligne d'un jour ou plus, et certains fichiers sont des rediffusions. Pour richbourse, `<lastmod>` peut être une date de **mise à jour**, pas de première publication.
5. **Sentiment** : le lexique du §3.3 est une **première version non validée**. Aucune annotation n'a encore été faite et aucune mesure de précision n'existe.
6. **Coûts** : ce sont ceux du document 01 (1,7 à 2,8 % par aller-retour, hors impact). L'impact sur le prix d'un achat concentré avant un détachement n'est **pas modélisé**.

**Questions ouvertes (par ordre de priorité)**
1. Autoriser dans les réglages réseau de l'environnement `amf-umoa.org`, `agenceecofin.com`, `financialafrik.com`, `news.abidjan.net`, `huggingface.co`, `arxiv.org` et `sraf.nd.edu`, puis : (a) lire les **délais réglementaires de publication** (Règlement général de la BRVM, instructions de l'AMF-UMOA sur l'information périodique) ; (b) vérifier les flux RSS de la presse ; (c) vérifier l'existence de modèles de sentiment financier en français ; (d) relire les références du §3.1.
2. **Dérive après les résultats avec un vrai « surprise »** : extraire RN N et N−1 des PDF (pdftotext, puis OCR) pour les environ 50 sociétés depuis 2017, puis refaire le §4.6 avec le signe et l'ampleur de la variation, au lieu du signe de la réaction initiale.
3. **Pourquoi le PDR vaut 0,46 ?** Tester l'échelon de cotation, l'effet des petits dividendes, la clientèle fiscale (IRVM 7 à 12,5 % selon le pays) et la profondeur du carnet (`order_book.parquet`) le jour du détachement.
4. Retrouver les chiffres de l'étude ESJ 2017 (annonces de dividendes) et rechercher des mémoires locaux (CESAG, UFHB, BCEAO) sur le détachement.
5. Télécharger à nouveau les BOC manquants de 2021 (246 fichiers marqués `.missing` dans `data/boc_text`), puis refaire les calculs.
6. Mesurer la **capacité** de S1 : volume réellement disponible sur les 8 séances entre l'avis et le détachement, et impact d'un ordre de 5 M, 20 M ou 50 M FCFA.
7. Suivre le déclin de S1 en 2027 : si la moyenne brute passe sous +2 %, S1 ne couvre plus les coûts.

---

## 8. Sources

**Sources primaires lues pendant cette session (22/11/2026)**

*BRVM : règles et flux*
- robots.txt (`Crawl-delay: 10`) : https://www.brvm.org/robots.txt
- Accueil et plan du site : https://www.brvm.org/fr ; https://www.brvm.org/fr/sitemap
- Flux RSS (vide) : https://www.brvm.org/fr/taxonomy/term/1/feed

*BRVM : annonces des émetteurs*
- Communiqués : https://www.brvm.org/fr/emetteurs/type-annonces/communiques (pages 0 à 26)
- Convocations d'AG : https://www.brvm.org/fr/emetteurs/type-annonces/convocations-assemblees-generales (pages 0 à 19)
- Changements de dirigeants : https://www.brvm.org/fr/emetteurs/type-annonces/changements-de-dirigeants
- Franchissements de seuil : https://www.brvm.org/fr/emetteurs/type-annonces/franchissements-de-seuil
- Notations financières : https://www.brvm.org/fr/emetteurs/type-annonces/notations-financieres
- Projets de résolution : https://www.brvm.org/fr/emetteurs/type-annonces/projets-de-resolution

*BRVM : opérations sur titres et avis*
- Paiement de dividendes : https://www.brvm.org/fr/esv/paiement-de-dividendes (pages 0 à 43, 433 lignes)
- Autres opérations sur titres : https://www.brvm.org/fr/esv/augmentation-de-capital ; https://www.brvm.org/fr/esv/fractionnement ; https://www.brvm.org/fr/esv/radiation
- Avis : https://www.brvm.org/fr/marche/avis-et-publications/avis (pages 0 à 29)
- Publications : https://www.brvm.org/fr/marche/avis-et-publications/publications

*BRVM : rapports, actualités, BOC*
- Rapports des sociétés cotées : https://www.brvm.org/fr/rapports-societes-cotees (pages 0 à 2) et pages des émetteurs `https://www.brvm.org/fr/rapports-societe-cotes/<slug>` (50 sociétés, page 0), par exemple https://www.brvm.org/fr/rapports-societe-cotes/bank-africa-ci
- Actualités institutionnelles : https://www.brvm.org/fr/mediacentre/actualites
- BOC du 20/11/2026 : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (copie texte `data/boc_text/boc_20261120.txt.gz`) ; BOC de fin d'année 2017 à 2025 (calendriers des AG), dans `data/boc_text/`

*BRVM : exemples de documents cités*
- Avis de paiement AGL CI : https://www.brvm.org/sites/default/files/20261009_-_avis_ndeg297_brvmdg_-_paiement_de_dividendes_exo_2025_-_agl_ci.pdf
- Communiqué d'annulation de l'AGO d'ETI : https://www.brvm.org/sites/default/files/20261023_-_communique_-_annulation_ago_-_eti_tg.pdf
- Fractionnement SONATEL : https://www.brvm.org/sites/default/files/20261012_-_avis_ndeg304_brvmdg_-_fractionnement_de_laction_sonatel_sn.pdf

*Richbourse*
- robots.txt : https://www.richbourse.com/robots.txt
- Sitemap (6 325 publications) : https://www.richbourse.com/sitemap.xml
- Publications officielles : https://www.richbourse.com/common/actualite
- Revue de presse (articles d'Agence Ecofin, dont l'OPV de Coris Bank CI du 20/11/2026) : https://www.richbourse.com/common/news/index ; par exemple https://www.richbourse.com/common/apprendre/article/2026-11-20-brvm-coris-bank-ci-ouvre-son-capital-aux-investisseurs-des-le-lundi-30-novembre
- « Autres actualités » : https://www.richbourse.com/common/rss
- Calendrier (dynamique) : https://www.richbourse.com/outils/calendrier/index

*Autres sources*
- Sika Finance (page Cloudflare, HTTP 403) : https://www.sikafinance.com
- PyPI, API JSON (versions et licences des paquets) : https://pypi.org/pypi/feedparser/json, et de même pour `trafilatura`, `pdfplumber`, `pymupdf`, `rapidfuzz`, `scikit-learn`, `transformers`, `onnxruntime`, `sentence-transformers`, `spacy`, `unidecode`, `selectolax`, `pytesseract`, `ocrmypdf`, `dateparser`

**Données et calculs internes**
- Panel BOC : `data/panel/adjusted_prices.parquet`, `equities.parquet`, `indices.parquet`, `dividends.parquet` (2 334 séances, 2017-2026)
- Scripts de cette recherche (dossier de travail de la session) : `parse_views.py`, `listings.py`, `div_pages.py`, `ag_calendar.py`, `names.py`, `evlib.py`, `official_div_study.py`, `pub_study.py`. À intégrer dans `brvm_alpha/events/` (§6.1).

**Documents du projet cités**
- 01 (structure du marché : horaires, coûts, IRVM, suspensions) : `docs/research/01-structure-marche.md`
- 02 (littérature BRVM, dont l'étude ESJ 2017 et Djahoué 2025) : `docs/research/02-litterature-brvm.md`
- 04 (validation walk-forward, IC) : `docs/research/04-rigueur-quantitative.md`
- 05 (macro, sources BCEAO) : `docs/research/05-macro-geopolitique-uemoa.md`
- 06a (sociétés financières : ETI, BOAN, capital minimum bancaire) : `docs/research/06a-societes-financieres.md`

**Références académiques (connues ; non relues en ligne dans cette session, conf. M)**
- Loughran & McDonald (2011), *Journal of Finance* 66(1) : https://doi.org/10.1111/j.1540-6261.2010.01625.x
- Tetlock (2007), *Journal of Finance* 62(3) : https://doi.org/10.1111/j.1540-6261.2007.01232.x
- Malo et al. (2014), *JASIST* 65(4) : https://doi.org/10.1002/asi.23062
- Araci (2019), FinBERT : https://arxiv.org/abs/1908.10063
- Huang, Wang & Yang (2023), *Contemporary Accounting Research* 40(2) : https://doi.org/10.1111/1911-3846.12832
- Martin et al. (2020), CamemBERT : https://arxiv.org/abs/1911.03894
- Le et al. (2020), FlauBERT : https://arxiv.org/abs/1912.05372
- Fama, Fisher, Jensen & Roll (1969) : https://doi.org/10.2307/2525569
- Ball & Brown (1968) : https://doi.org/10.2307/2490232
- Bernard & Thomas (1989) : https://doi.org/10.2307/2491062
- Elton & Gruber (1970) : https://doi.org/10.2307/1927599
- Hartzmark & Solomon (2013), *Journal of Financial Economics* 109(3) : https://doi.org/10.1016/j.jfineco.2013.03.011
- MacKinlay (1997), *Journal of Economic Literature* 35(1) ; Kalay (1982), *Journal of Finance* 37(4) ; Lakonishok & Vermaelen (1986), *Journal of Financial Economics* 16(3) (DOI non vérifiés)
- Étude d'événement BRVM, *European Scientific Journal* 13(22), 2017 (repris du document 02, conf. B) : https://eujournal.org/index.php/esj/article/download/9793/9297
- Djahoué (2025), *Modern Economy* 16(11) (repris du document 02) : https://www.scirp.org/journal/paperinformation?paperid=147179
