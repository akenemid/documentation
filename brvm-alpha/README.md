# BRVM Alpha

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

Plate-forme d'analyse quantitative des actions de la BRVM (Bourse régionale des valeurs mobilières,
Abidjan), en français. Elle lit les Bulletins officiels de la cote (BOC), construit un panel de données
point-in-time, calcule des signaux, simule une stratégie nette de tous les coûts, valide cette stratégie
selon un protocole écrit d'avance, puis produit un **ordre de bataille** au titre et au franc près, un
**rapport HTML** autonome et une **interface locale**. Un module de **notes de l'analyste** permet de
saisir, collecter et analyser l'information qualitative.

## Avertissement

- **Aucun gain n'est garanti**, ni en absolu ni contre l'indice. Les chiffres de ce dépôt sont des
  **faits** (cours publiés, règles du marché), des **estimations** (simulations, distributions,
  coûts implicites) ou des **hypothèses** (taxes non vérifiées, dividende reconduit). Les sorties
  le précisent à chaque ligne.
- **Fait** : la variante principale A a été **REJETÉE** par le test unique sur l'échantillon vierge
  S1 (voir « Méthode »). La plate-forme fonctionne donc en mode « indice discipliné » (REF), lui aussi
  rejeté à titre informatif. Les ordres produits sont une **recommandation à titre d'étude** :
  un suivi réel (paper trading, S2) est requis avant tout engagement d'argent réel.
- Ce dépôt est une aide à l'analyse. Ce n'est pas un conseil en investissement personnalisé.

## Installation

Python 3.13 (le code vise 3.11 ou plus). Aucune dépendance réseau n'est nécessaire pour les tests.

```bash
cd brvm-alpha
python -m pip install "pandas>=3" numpy scipy statsmodels scikit-learn pyarrow PyYAML requests beautifulsoup4 pdfplumber
# facultatif, plus rapide que pdfplumber pour convertir les PDF des BOC :
sudo apt-get install poppler-utils   # fournit pdftotext
python -m brvm_alpha --help
```

Versions utilisées le 22/11/2026 : pandas 3.0.5, numpy 2.5.3, scipy 1.18.1, statsmodels 0.15.0,
scikit-learn 1.9.1, pyarrow 26.0.1, PyYAML 6.0.3. Il n'y a pas de fichier d'installation : on lance
les commandes depuis la racine `brvm-alpha/`.

## Données

- **Source** : les Bulletins officiels de la cote publiés par la BRVM
  ([bulletins officiels de la cote](https://www.brvm.org/fr/bulletins-officiels-de-la-cote)), un PDF
  par séance, converti en texte (`data/boc_text/boc_AAAAMMJJ.txt.gz`).
- **Panel** : `data/panel/*.parquet` (`equities`, `indices`, `market`, `order_book`, `dividends`,
  `corporate_actions`, `adjusted_prices`, `sessions`), du **02/01/2017 au 20/11/2026**. Le schéma est
  décrit dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **Séances manquantes (fait)** : le calendrier des numéros de BOC compte **2 463 séances**, dont
  **2 334** ont un BOC téléchargeable. **129 séances** n'en ont pas : 9 en 2017, 4 en 2018, 3 en 2019,
  2 en 2020, **96 en 2021**, 3 en 2022, 2 en 2023, 6 en 2024, 2 en 2025 et 2 en 2026.
- **Trous de 2021** : le plus long trou couvre **32 séances consécutives** (N° 89 à 120, du 07/05 au
  24/06/2021). Les rendements qui couvrent plusieurs séances sont gardés pour chaîner les séries,
  mais retirés des statistiques de dispersion. La fenêtre du 06/05 au 25/06/2021 est exclue de toutes
  les mesures de validation (§8.1 de la spécification). Les fenêtres des signaux sont comptées en
  séances, avec des seuils au prorata des BOC disponibles (additif v1.1, D1) : un BOC manquant est une
  perte de **nos** données, pas une absence de cotation.
- `data/` n'est **pas suivi** par git (BOC, panel, journal des notes : environ 85 Mo). On le
  reconstruit avec `update` puis `panel`.

## Commandes (CLI)

Toutes les commandes s'écrivent `python -m brvm_alpha COMMANDE` ; `-h` affiche l'aide en français.
Code de sortie : 0 succès, 1 échec, 2 refus ou saisie invalide. **Toute date de décision dans S1
(au plus tard le 16/11/2022) est refusée**, sauf par la commande `validate`, verrouillée.

| Commande | Rôle |
|---|---|
| `update` | télécharge les BOC manquants sur www.brvm.org (robots.txt, 10 s au moins entre deux requêtes, arrêt au premier 403 ou 429), puis reconstruit le panel |
| `panel` | reconstruit `data/panel` depuis les BOC locaux (cache incrémental) |
| `live` | cours du jour (page publique de brvm.org, un instantané ; le BOC du soir fait foi) |
| `notes` | journal des notes : `add`, `list`, `show`, `archive`, `export`, `research` (collecte, puis lecture des documents : `--pdf N`), `lire` (lecture seule des documents), `analyze` |
| `indices` | évaluation des indices (position, confiance, raisons) ; `indices dossier CODE` |
| `universe` | univers éligible U1-U10 à une date (comptage, permis sur toute la période) |
| `explain` | décomposition du score et des contraintes d'un titre |
| `backtest` | backtest net de coûts (S0 ; S1 refusé sans `--validation-s1`) |
| `validate` | test unique S1 (verrouillé) ou diagnostic S0 (contaminé) |
| `recommend` | ordre de bataille complet pour un capital (Markdown, JSON ou HTML) |
| `report` | rapport HTML autonome (marché, S1, ordre de bataille, revenus, distribution, indices, notes, risques, univers, méthode) |
| `serve` | interface web locale |

Exemples :

```bash
# Données
python -m brvm_alpha update --simulation            # liste les jours à chercher, sans requête
python -m brvm_alpha update                         # télécharge poliment, puis reconstruit le panel
python -m brvm_alpha panel --workers 3

# Ordre de bataille au 20/11/2026 pour 10 M FCFA, sans titres détenus
python -m brvm_alpha recommend --capital 10000000 --format md > reports/ordre_de_bataille_2026-11-20.md
# avec un portefeuille existant (CSV « symbole,titres ») et des liquidités
python -m brvm_alpha recommend --capital 10M --portefeuille mon_portefeuille.csv --cash 250000 --format json

# Rapport final et explication d'une ligne
python -m brvm_alpha report --capital 10000000 --sortie reports/rapport_2026-11-20.html
python -m brvm_alpha explain SNTS --capital 10000000

# Indices et univers
python -m brvm_alpha indices --detail
python -m brvm_alpha indices dossier IDX:BRVM-30
python -m brvm_alpha universe --date 2026-11-20 --capital 10000000

# Notes : les notes connues maintenant comptent (mode direct) ; --notes-au fixe l'instant (UTC)
python -m brvm_alpha recommend --capital 10M                                 # notes connues maintenant
python -m brvm_alpha recommend --capital 10M --notes-au 2026-11-22T21:00     # notes connues à cet instant
python -m brvm_alpha indices --date 2026-11-13                               # date passée : règle stricte
python -m brvm_alpha notes research --pdf 20     # collecte polie, puis lecture d'au plus 20 documents
python -m brvm_alpha notes lire --max 10 --hors-ligne    # documents déjà en cache, aucune requête

# Validation (le test S1 a déjà été exécuté : la commande refuse de se relancer)
python -m brvm_alpha validate --sample S0
```

Ordres de bataille publiés pour le 20/11/2026 (aucun titre détenu) :
[10 M FCFA](reports/ordre_de_bataille_2026-11-20.md),
[1 M FCFA](reports/ordre_de_bataille_2026-11-20_1M.md),
[50 M FCFA](reports/ordre_de_bataille_2026-11-20_50M.md). Le rapport HTML
`reports/rapport_2026-11-20.html` n'est pas suivi par git : on le régénère avec la commande `report`.

## Interface locale

```bash
python -m brvm_alpha serve            # http://127.0.0.1:8765
python -m brvm_alpha serve --port 0   # port libre
```

L'interface écoute sur **127.0.0.1 seulement** : elle n'a pas d'authentification, et une autre adresse
exige `--hote`, ce qui est déconseillé. Pages : tableau de bord (état de S1, variante, notes prises en
compte, dernier rapport), notes (saisie manuelle, notes en vigueur à la séance d'application, filtres
actifs, 10 notes les plus positives et les plus négatives, composante « notes » de chaque indice, journal,
fiche, archivage), recherche automatique (hors ligne ou en ligne, avec quota, et case « lire le contenu
des documents récents »), indices et dossiers d'indice, portefeuille (capital, titres détenus,
liquidités, puis ordre de bataille avec exports Markdown et JSON), explication d'un titre, validation
(S1 lu ; S0 replié et marqué contaminé), rapports. Quand la date est la dernière séance du panel,
l'interface travaille en **mode direct** : les notes saisies ou collectées jusqu'à l'instant de la
requête comptent, et chaque page affiche la ligne « Notes connues au …, appliquées à la séance du … ». Protections : contrôle de l'en-tête `Host`, jeton anti-CSRF sur chaque
envoi, corps de requête borné, politique de sécurité de contenu stricte, délai d'expiration de 20 s,
32 connexions au plus, une seule opération longue à la fois. Thème clair ou sombre, mise en page
lisible sur téléphone.

## Notes de l'analyste

Le journal est un fichier JSON Lines en ajout seul (`data/notes/notes.jsonl`). Une modification crée
une nouvelle version et l'historique est conservé. Codes de cibles : `SNTS` (symbole), `IDX:BRVM-C`,
`IDX:BRVM-30`, `IDX:PRESTIGE`, `IDX:PRINCIPAL`, `IDX:BRVM-C-TR`, `IDX:SECT:FIN`, `PAYS:CI`,
`SECT:TEL`, `THEME:CACAO`, `MARCHE`.

- **Saisie manuelle** :

  ```bash
  python -m brvm_alpha notes add --cible SNTS --titre "Résultats annuels" \
      --texte "Résultat net en hausse de 12 %, dividende relevé." \
      --avis haussier --conviction 3 --source "rapport annuel" --publie-le 2026-11-20
  python -m brvm_alpha notes list --cible SNTS
  python -m brvm_alpha notes analyze --texte "Avertissement sur résultats : baisse attendue de 30 %"
  ```

  Une date de publication future est refusée et l'URL d'une source doit être en http ou https. À la
  lecture du journal, un enregistrement sans titre ni texte, ou sans date, est écarté et signalé.
- **Recherche automatique polie** : `notes research` lit les listes publiques de **www.brvm.org**
  (annonces, opérations sur titres, avis, dividendes, rapports des émetteurs) et les événements des
  BOC locaux. Règles : robots.txt lu et respecté, **au moins 10 s** entre deux requêtes (Crawl-delay),
  d'une session à l'autre ; arrêt définitif au premier HTTP 403 ou 429, sans contournement ; quota de
  requêtes (150 par défaut) ; aucune API non documentée. Sika Finance, Richbourse et la presse sont
  **désactivés par défaut**. `--hors-ligne` n'utilise que le cache et les BOC locaux ; `--simulation`
  n'enregistre rien.
- **Lecture du contenu des documents** : après la collecte, `notes research --pdf N` (défaut 20 ; `0` :
  aucun) lit le contenu d'au plus N documents PDF récents de www.brvm.org (alertes sur résultats,
  résultats, rapports d'activité, notations, communiqués), un par émetteur d'abord, et écrit une
  **nouvelle version** de chaque note avec l'analyse du texte. `notes lire [--max N] [--hors-ligne]
  [--cibles CODES]` fait la même lecture sans nouvelle collecte. Le bilan affiche les documents lus, les
  notes enrichies, les documents scannés (images sans texte, **à lire à la main**) et les erreurs. Les
  règles de politesse sont les mêmes (une requête par document, 10 s au moins, arrêt au premier 403 ou
  429).
- **Analyse** : chaque note reçoit un type d'événement (dividende, résultats, alerte sur résultats,
  macro…), un ton, les chiffres extraits (variation du résultat net, du dividende…), une matérialité,
  une confiance, des filtres de risque R1-R10 et une lecture en phrases courtes. Le score suit le
  document 07 §3.4 : `clip(0,7 × s_num + 0,3 × ton, −1, 1)`.
- **Deux instants : la date des cours et l'instant de connaissance des notes.** Les cours sont ceux du
  dernier BOC. Les notes, elles, peuvent être plus récentes : une note saisie le dimanche soir doit
  compter pour la séance du lundi.
  - **Mode direct** (défaut de `indices`, `explain`, `recommend`, `report` et de l'interface quand la
    date est la dernière séance du panel) : l'instant de connaissance est l'heure réelle. Les notes
    connues à cet instant sont appliquées à la **séance qui suit le dernier BOC**, ou à la suivante si sa
    coupure de 09h00 UTC est déjà passée. Une note datée de demain n'agit pas. L'âge d'une note
    (décroissance, durée d'un filtre) se compte depuis sa publication pour une note collectée
    automatiquement, depuis sa saisie pour une note de l'analyste.
  - **Mode historique** (`--date` antérieure à la dernière séance, backtests, validation, tout appel
    programmatique sans `notes_known_at`) : règle stricte à la date demandée, **sans anticipation** ; une
    note saisie ou collectée après cette date n'agit pas.
  - `--notes-au AAAA-MM-JJ[THH:MM]` fixe l'instant de connaissance (UTC ; une date seule désigne la fin
    de la journée).
  - Chaque sortie écrit la ligne « Notes connues au JJ/MM/AAAA HH:MM UTC, appliquées à la séance du
    JJ/MM/AAAA : N en vigueur (dont M manuelles), F filtre(s) de risque actif(s) ». Quand une note
    **bloque un achat** (filtre R), l'ordre de bataille l'écrit en clair : titre, règle, note (date,
    titre, source, adresse), fin du blocage, effet sur les poids cibles et façon de lever le blocage
    (**archiver la note** : `notes archive ID`, ou le bouton « Archiver » de sa fiche).
  - Exemple (fait, journal collecté le 22/11/2026) : l'annulation de l'assemblée générale d'ETI (note du
    23/10/2026, filtre R2, 60 séances, jusqu'au 19/01/2027) bloque l'achat d'ETIT. Dans l'ordre REF de
    10 M FCFA, son poids cible de 6,16 % passe à 0 % ; les règles de construction existantes (D8) le
    **redistribuent** : TotalEnergies Marketing CI (TTLC) entre comme vingtième ligne et les autres
    poids montent en proportion ; le total investi cible reste de 98 %. Les ordres publiés dans
    `reports/` avant ce changement achètent encore ETIT : ils sont à régénérer avec `recommend`.
- **Effet sur les indices** : les scores des notes, datés et point-in-time (une note agit à la première
  séance négociable après sa publication, coupure de 09h00, décroissance τ = 10 séances), forment la
  composante « notes » de l'évaluation des indices (poids 0,15, à côté de la tendance 0,30, de la
  valorisation 0,25, de la largeur 0,15 et du régime 0,15). Cette composante n'est retenue que si une
  note en vigueur a une contribution non nulle ; dès qu'elle l'est, elle pèse 15 % du score, même si son
  z est proche de zéro : chaque indice affiche donc son score **sans et avec** les notes (« Effet des
  notes »), et les notes qui portent la composante. Quand elle est absente, la raison est écrite
  (« aucune note en vigueur » ou « score nul »). La position (SURPONDÉRER, NEUTRE, SOUS-PONDÉRER) est
  une **aide à la décision, pas un signal validé** : elle n'entre pas dans l'ordre de bataille.
- **Effet sur la position** : les notes ne pilotent jamais seules le portefeuille. Un **veto** manuel
  exclut un titre. Une **inclinaison** est bornée à ±0,5 écart-type et s'ajoute au score des variantes
  factorielles. Les **filtres R** issus des notes bloquent les achats ou réduisent les plafonds. En
  mode « indice discipliné » (REF), la sélection se fait par capitalisation : l'inclinaison n'y change
  pas la sélection, mais le veto et les filtres R s'appliquent. Les notes n'ont **aucun rôle sur S1**
  (D11) : aucune note n'existait en temps réel sur 2017-2022.

## Méthode

- **Spécification** : [docs/SPECIFICATION_STRATEGIE.md](docs/SPECIFICATION_STRATEGIE.md). L'étalon
  est le **BRVM Composite Total Return** (dividendes nets réinvestis), officiel depuis le 02/01/2025 et
  reconstruit avant ; battre l'indice prix ne prouve rien. La variante principale A est un composite
  factoriel acheteur seul : valeur (E/P, D/P), momentum 6-1, faible volatilité, qualité, avec 12 à 20
  lignes équipondérées, un plafond de 10 % par ligne, un signal mensuel, une bande 30/50 et une
  participation de 10 % au plus de la valeur échangée. Les coûts complets sont simulés : courtage ×
  (1 + taxe), BRVM 0,20 %, DC/BR 0,10 %, demi-spread et impact, plus garde et tenue de compte.
  Les paramètres sont figés dans [configs/strategy_v1.yaml](configs/strategy_v1.yaml).
- **Additif v1.1** (§8.4, décisions D1-D12 figées le 22/11/2026 **avant** toute exécution sur S1 ;
  il fait foi) : fenêtres comptées en séances (D1), fenêtre d'évaluation depuis la première séance
  investie t0 (D2), mode « indice discipliné » REF (20 plus grosses capitalisations éligibles, D8),
  variante I « cœur-satellite » (D9, famille N = 9), chronologie des événements pays (D10), aucune
  note sur S1 (D11), exécution unique et verrou (D12). Le §8.5 (errata E1-E9, écrits après le premier
  test) ne change aucune décision ni aucun seuil.
- **Échantillons** : S1 = 02/01/2017 → 16/11/2022 (vierge, test unique) ; S0 = 17/11/2022 →
  20/11/2026 (contaminé, diagnostic seulement) ; S2 = suivi réel à partir du 01/12/2026 (seul test
  réellement hors échantillon).
- **Validation S1, résultat réel** (faits de simulation, estimations ; détails dans
  [reports/validation_S1/resultats.md](reports/validation_S1/resultats.md) et
  [tentatives.md](reports/validation_S1/tentatives.md)). Le test a tourné une première fois le
  22/11/2026 (état figé `a2bfeb4`). Un audit a démontré deux bogues de comptabilité des statistiques :
  semaines multi-séances retirées du chaînage, et garde-fou de couverture tautologique. Une **relance
  motivée** (D12, commit `1819997`) a créé de nouveaux essais (N passe de 88 à 98) sans changer aucun
  paramètre de stratégie. Les deux résultats sont publiés ; le premier est dans
  `reports/validation_S1/precedent_20261122T121328Z/`. Résultat de la relance, sur la fenêtre
  [01/08/2017 ; 16/11/2022], nette de coûts, coûts centraux, 10 M FCFA :
  - Composite TR : −0,8 %/an.
  - **A** : −10,1 %/an, soit **−9,3 %/an contre le TR** (IR −1,14, intervalle bootstrap à 95 %
    [−1,86 ; −0,40]). Actif aux coûts de stress : −10,8 %/an. IR des sous-périodes : −1,14 et −1,27.
    Drawdown relatif : −40,2 %. Drawdown absolu : −54,0 %, contre −40,8 % pour le TR.
  - **Statut de A : REJETÉ**, car les cinq conditions de rejet R1 à R5 du §8.3 sont vraies.
  - Les variantes B à I sont toutes REJETÉES. Aucune ne remplace A (règle du §3.4) : DSR (N = 9)
    d'environ 0,002, sous 0,95 ; PBO de 0,845, au-dessus de 0,25.
  - **REF** (référence informative, hors PBO) : −6,4 %/an, soit −5,6 %/an contre le TR. Drawdown
    relatif : −27,1 %. Statut : REJETÉ (R1 à R4).
  - Couverture : 97,4 % des semaines attendues (seuil de 95 %). Registre : N = 98 essais.
  - Cela était annoncé comme plausible : la prédiction écrite d'avance (§8.3) jugeait le rejet de A
    possible, et le statut le plus probable était « candidat ».
- **Statut de la plate-forme** : mode « indice discipliné » (REF, D8), **sans promesse d'alpha**.
  **PROMU est impossible sans suivi réel S2** : au moins 12 mois, et la condition G7 sur au moins
  36 mois d'IC, S1 et S2 bout à bout (D7). Toute modification des règles serait un **nouvel essai**,
  à juger sur S2, jamais une relance de S1.

## Ordre de bataille au 20/11/2026 (10 M FCFA, estimation)

Variante retenue : **REF** (A REJETÉ sur S1). Ce sont 20 ordres d'achat, exécutables en une séance
le 23/11/2026, pour un brut de 9 631 643 FCFA (96,32 % investis), 163 365 FCFA de coûts d'entrée
(1,63 %) et 124 079 FCFA de frais fixes par an. Revenu de dividendes net attendu sur 12 mois :
416 535 FCFA (4,17 %), sous l'hypothèse du dernier dividende reconduit. La distribution historique à
12 mois n'est pas une prévision : médiane +11,9 %, P10 −9,3 %, P90 +38,0 %, P(perte) 25 %. Elle est
tirée de toute l'histoire 2017-2026 avec les poids actuels, donc avec un biais rétrospectif. Le détail
est dans [reports/ordre_de_bataille_2026-11-20.md](reports/ordre_de_bataille_2026-11-20.md).

## Limites

- **Pas d'alpha démontré** : A et ses variantes sont rejetées sur S1. Il faudrait environ 30 ans de
  données hebdomadaires pour établir un IR de 0,3 à 95 % (§10.2).
- **Données** : pas de BOC avant 2017 ; 129 séances sans BOC, dont 96 en 2021 ; fondamentaux en
  partie scannés ; taxes, IRVM et redevance AMF-UMOA en partie **[NON VÉRIFIÉ]** ; fonds actions
  non extraits.
- **Liquidité et capacité** : la valeur échangée a été multipliée par environ 30 depuis 2019-2020.
  Les chiffres de capacité à 100 M et 1 Md FCFA sont mécaniques : beaucoup de liquidités face à un
  TR baissier.
- **Petit capital** : à 1 M FCFA, 80 % seulement est investi, sur 18 lignes, et la tenue de compte
  coûte environ 9 % par an. L'ordre de bataille l'avertit.
- **Points ouverts** (documentés au §8.5 et dans `tentatives.md`) :
  - Les signaux de momentum et de faible volatilité lisent un indice TR qui intègre le dividende
    corrigé dès le jour ex, avant la publication de la correction. Aucun effet n'a été trouvé sur S1 ;
    c'est à corriger avant S2.
  - REF n'est investi qu'à 82 % en moyenne sur S1, contre une cible de 98 % : les dividendes et le
    produit des sorties forcées restent en liquidités jusqu'au rebalancement annuel. C'est une
    décision humaine, et un nouvel essai.
  - Le plancher D1 des filtres d'univers et l'âge des ordres après un trou de BOC (épisode de 2021)
    attendent aussi une décision humaine.
- **Distribution et stress** : la distribution est une fréquence historique, pas une probabilité
  future. Les stress supposent un comportement linéaire (β) ou un choc direct par pays.
- **Calendrier futur** : jours ouvrés hors fériés fixes ; les fêtes mobiles sont inconnues.

## Structure du code

```
brvm_alpha/
  cli.py, __main__.py        ligne de commande
  config.py, settings.py     paramètres (frais, taxes) et lecture de configs/strategy_v1.yaml
  reference.py               métadonnées des titres, pays, fiscalité, événements pays
  data/                      téléchargement poli et lecture des BOC, panel parquet, cours du jour
  notes/                     notes de l'analyste : modèle, journal, analyse, recherche, signaux, indices
  quant/                     caractéristiques, scores, statistiques (PSR, DSR, PBO, bootstrap), régime, macro
  portfolio/                 risque, construction, ordre de bataille, stress
  backtest/                  moteur quotidien, métriques hebdomadaires, walk-forward et registre
  validation/                test unique S1 et diagnostic S0 : exécuteur, verrou, étalons, contrôles
  strategy/alpha.py          le modèle (variantes A à I et REF)
  report/html.py             rapport HTML autonome
  ui/                        interface web locale
configs/strategy_v1.yaml     paramètres figés
docs/                        spécification, architecture, annexes, revues de recherche 01 à 08
reports/                     validation S1, diagnostic S0, registre des essais, ordres de bataille
tests/                       tests pytest hors ligne
```

Les contrats des modules et l'arborescence complète sont décrits dans
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tests

```bash
cd brvm-alpha
python -m pytest -q -p no:cacheprovider        # suite complète, environ 10 minutes
python -m pytest -q -p no:cacheprovider tests/test_report_html.py
```

Les tests n'envoient **aucune requête réseau**. Ils utilisent des données synthétiques, des extraits de
BOC et des pages de brvm.org enregistrées (`tests/fixtures/`), ou la période S0. **Aucun backtest,
aucune performance et aucun IC n'est évalué sur S1** dans les tests. Le 22/11/2026, la suite complète
compte 1 380 tests, tous verts (dont 36 pour le mode direct des notes, `tests/test_notes_direct.py`).

## Sources

Sources primaires et données :

- [Bulletins officiels de la cote (BRVM)](https://www.brvm.org/fr/bulletins-officiels-de-la-cote)
- [Paquet R « BRVM » 5.3.0 (rdocumentation.org)](https://www.rdocumentation.org/packages/BRVM/versions/5.3.0)
- [Téléchargement des cours BRVMFI (Sika Finance)](https://www.sikafinance.com/marches/download/BRVMFI) :
  référence seulement, la collecte depuis ce site est désactivée par défaut.
- [Frais applicables (BRVM)](https://www.brvm.org/fr/node/312)
- [Règles de négociation, d'admission et de radiation](https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf)
- [Instruction 03-2025 : règlement-livraison J+2](https://www.brvm.org/sites/default/files/instruction_03_2025_brvm_dg_reduction_delai_j3_j2_0.pdf)
- [Avis 308-2025 : BRVM Composite Total Return](https://www.brvm.org/sites/default/files/20251224_-_avis_ndeg308_brvmdg_-_affichage_de_lindice_brvm_composite_total_return_index.pdf)
- [Instruction 01-2025 : alerte sur résultats](https://www.brvm.org/sites/default/files/instruction_ndeg01-2025-brvm-dg_-_profit_warning_1.pdf)
- [Paiements de dividendes](https://www.brvm.org/fr/esv/paiement-de-dividendes)
- [Indices de la BRVM](https://www.brvm.org/fr/indices)
- [Horaires de cotation](https://www.brvm.org/fr/horaires-de-cotation)
- [Textes réglementaires](https://www.brvm.org/fr/textes-reglementaires/reglement-general-instructions-circulaires-et-autres-textes-publies-par-la)
- [robots.txt de brvm.org (Crawl-delay : 10 s)](https://www.brvm.org/robots.txt)

Revues de recherche du dépôt (versions vérifiées le 22/11/2026, avec leurs propres listes de sources) :
[01 structure du marché](docs/research/01-structure-marche.md),
[02 littérature BRVM](docs/research/02-litterature-brvm.md),
[03 facteurs des marchés frontières](docs/research/03-facteurs-marches-frontieres.md),
[04 rigueur quantitative](docs/research/04-rigueur-quantitative.md),
[05 macro et géopolitique UEMOA](docs/research/05-macro-geopolitique-uemoa.md),
[06a sociétés financières](docs/research/06a-societes-financieres.md),
[06b sociétés non financières](docs/research/06b-societes-non-financieres.md),
[07 actualité et événements](docs/research/07-actualite-sentiment-evenements.md),
[08 outils et pratiques](docs/research/08-outils-et-pratiques-analystes.md).

Références académiques citées par ces revues (non relues en ligne dans cette session) :

- [Bailey et López de Prado (2014), Deflated Sharpe Ratio](https://papers.ssrn.com/abstract=2460551)
- [Bailey, Borwein, López de Prado et Zhu (2017), Probability of Backtest Overfitting](https://papers.ssrn.com/abstract=2326253)
- [Harvey, Liu et Zhu (2016), « …and the Cross-Section of Expected Returns »](https://www.nber.org/papers/w20592)
- [Harvey et Liu (2015), Backtesting](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- [López de Prado (2016), Hierarchical Risk Parity](https://papers.ssrn.com/abstract=2708678)
- [Ledoit et Wolf (2004), « Honey, I Shrunk the Sample Covariance Matrix »](https://econ-papers.upf.edu/papers/691.pdf)
- [Patton, Politis et White (2009), longueur de bloc du bootstrap](https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf)
- [Asness, Moskowitz et Pedersen (2013), Value and Momentum Everywhere](https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere)
- [de Groot, Pang et Swinkels (2012), value et momentum dans les marchés frontières](https://econpapers.repec.org/RePEc:eee:empfin:v:19:y:2012:i:5:p:796-818)
- [Zaremba et Maydybura (2019), facteurs dans les marchés frontières](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3332958)
- [Blitz, Pang et van Vliet (2013), faible volatilité dans les émergents](https://ideas.repec.org/a/eee/ememar/v16y2013icp31-45.html)
- [Barroso et Santa-Clara (2015), Momentum has its moments](https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120)
- [Daniel et Moskowitz (2016), Momentum crashes](https://www.nber.org/papers/w20439)
- [Novy-Marx et Velikov (2016), anomalies et coûts de transaction](https://www.nber.org/papers/w20721)
- [DeMiguel, Garlappi et Uppal (2009), Optimal versus Naive Diversification](https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html)
- [McLean et Pontiff (2016), résumé du CFA Institute](https://rpc.cfainstitute.org/research/cfa-digest/2016/06/does-academic-research-destroy-stock-return-predictability-digest-summary)

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
