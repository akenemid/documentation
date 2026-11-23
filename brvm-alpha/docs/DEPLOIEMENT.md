# BRVM Alpha — Déploiement à côté d'Odoo

Ce document dit comment faire tourner le moteur BRVM Alpha sur un serveur qui porte Odoo 17, sans
toucher à l'environnement Python d'Odoo.

- **Partie A (production)** : le moteur est **embarqué** dans le module Odoo `rz_brvm_alpha`. Odoo
  l'appelle **en ligne de commande**, en sous-processus. C'est le seul mode utilisé en production.
- **Partie B (non utilisée en production)** : le moteur à part, avec son interface web (`serve`)
  derrière un relais Odoo. Elle reste décrite pour mémoire et pour un usage local.

> Performance passée ≠ garantie. Aucun gain n'est garanti. BRVM Alpha est une aide à l'analyse, pas
> un conseil en investissement personnalisé.

## Partie A — Mode embarqué dans Odoo (appels en ligne de commande)

### A.1 En bref

- Le code du moteur est **copié dans le module Odoo** par `deploiement/exporter-moteur.sh` : le paquet
  `brvm_alpha/`, `configs/`, les résultats livrés de la validation (`reports/validation_S1/`,
  `reports/diagnostic_S0*/`, `reports/trials.parquet`), `deploiement/requirements-moteur-py311.txt`, la déclaration
  signée du suivi `reports/suivi_S2/` une fois signée, et un fichier `VERSION` ; la liste exacte est au § A.4. Rien
  d'autre.
- Il tourne sur son **propre interpréteur** : CPython 3.11.15 autonome dans `/opt/rz-brvm-alpha/python`
  (l'image `odoo:17.0` est en Python 3.10, pandas 3 exige 3.11). Ses 16 paquets sont installés **hors
  ligne** dans `/opt/rz-brvm-alpha/lib`.
- Odoo lance `python3.11 -I -B -m brvm_alpha COMMANDE … --format json` et lit **un objet JSON** sur la
  sortie standard. Appels courts en synchrone, appels longs en travail détaché (§ A.9).
- **Aucun serveur web du moteur en production** : ni `serve` permanent, ni `serve` à la demande, ni
  relais (§ A.16).
- Le code de sortie **3 n'est jamais rendu** : dans le conteneur, le processus 1 est le maître Odoo, qui
  s'arrête s'il récolte un enfant sorti avec ce code (§ A.7).

### A.2 Détection du mode embarqué

Le mode embarqué est actif si la variable `BRVM_ALPHA_EMBARQUE` vaut `1`, **ou** si un fichier `VERSION`
se trouve à la racine du code (dossier parent du paquet `brvm_alpha`, écrit par l'export). Une seule
fonction le décide : `brvm_alpha.paths.est_embarque()`. Alors :

- `BRVM_ALPHA_DONNEES` et `BRVM_ALPHA_RAPPORTS` sont **obligatoires**, en chemins **absolus**, hors du
  dossier du code, et désignent des **dossiers existants** : le module Odoo les crée à l'installation, le
  moteur ne les crée jamais (une faute de frappe enverrait sinon la collecte et le journal des notes au
  mauvais endroit). Sinon, **toute** commande (sauf `--help`) sort en code 8 avant la moindre écriture ;
- **aucune écriture dans l'arbre du code** : journal des notes, bulletins, panel, rapports, exports,
  verrous et fichiers temporaires vont dans les dossiers de données et de rapports, ou dans le dossier
  temporaire du système ; les fichiers `.pyc` ne sont pas écrits (`-B`, et `sys.dont_write_bytecode`) ;
- un chemin **relatif** donné en option (`--panel-dir`, `--boc-dir`, `--racine`, `--portefeuille`,
  `--fichier`, `--titre-fichier`, `--motif-fichier`) s'entend depuis `BRVM_ALPHA_DONNEES` (un `data/` de tête est
  retiré) ; `--sortie` depuis `BRVM_ALPHA_RAPPORTS` ; « .. » est refusé (code 2). `--sortie` doit rester dans le
  dossier des rapports ou celui des fichiers temporaires du système, et jamais sur un fichier du moteur (`notes/`,
  `panel/`, `boc_text/` des données), chemin **réel** compris (liens symboliques et « .. » résolus : un lien placé
  dans les rapports vers un dossier extérieur est refusé, avant : `recommend`, `report`, `plan`, `suivi bulletin` et
  `suivi exporter` écrivaient au bout du lien) ; `--fichier`, `--portefeuille`, `--grille FICHIER`, `--titre-fichier`
  et `--motif-fichier` ne lisent que dans les dossiers de données, de rapports ou temporaire, chemin **réel** compris,
  et un lien symbolique en dernière place est refusé, même vers un fichier permis (code 2 ; avant : `--fichier` et
  `--grille` suivaient un lien de `<D>` vers un fichier extérieur, `notes add` en recopiait le texte dans la note,
  `suivi saisir` l'inscrivait au carnet ; § A.9). Un fichier lu qui est un dossier, un tube, un texte non UTF-8 ou
  trop volumineux (grille : 64 Kio ; avis d'opéré, déclaration, `--portefeuille` : 1 Mo ; texte d'une note : 2 Mo) est
  refusé en code 2, jamais en 7 ni en 1. Côté Odoo, la règle reste : chemins fabriqués par le module seul ;
- `--racine`, `--panel-dir` et `--boc-dir` désignent toujours un **sous-dossier** de `BRVM_ALPHA_DONNEES`,
  liens symboliques et « .. » résolus : un chemin absolu qui en sort (ou un lien qui mène ailleurs) est refusé en
  code 2, avant toute écriture (avant : `notes add --racine /ailleurs` y créait un journal). `--panel-dir` ne
  recouvre ni `notes/` ni `boc_text/`, car le panel est remplacé d'un bloc à chaque construction. **Odoo ne
  passe jamais ces trois options** : les dossiers par défaut (`<données>/notes`, `panel`, `boc_text`) suffisent.
  Hors mode embarqué, rien ne change ;
- une option de chemin (`--racine`, `--panel-dir`, `--boc-dir`, `--fichier`, `--portefeuille`, `--titre-fichier`,
  `--motif-fichier`, `--sortie`) **vide ou faite seulement d'espaces** est refusée en code 2, avant toute écriture (avant : `--racine ' '` désignait le dossier
  courant, et `notes add` y créait un journal). `--sortie -` ne veut dire « sortie standard » que pour `notes export` :
  pour `recommend` et `report`, `-` est un nom de fichier, écrit dans le dossier des rapports (avant : dans le dossier
  courant). Hors mode embarqué, rien ne change ;
- `pdftotext` (paquet système **poppler-utils**) est **obligatoire** : sans lui, `update`, `notes
  research --pdf N` (N > 0) et `notes lire` sortent en code 8 avec le message « pdftotext absent :
  installer poppler-utils » ; `etat` le signale (clé `extracteur_pdf.manquant`) ;
- `requests` ne lit pas l'environnement (`trust_env=False`) : aucun mandataire implicite ; un mandataire
  explicite se donne par `BRVM_ALPHA_PROXY` ;
- un fil de calcul (BLAS, Arrow), le pool mémoire « system » d'Arrow et deux arènes de malloc :
  réservation de mémoire virtuelle divisée par 2 à 3 (§ A.10) ;
- la version est lue dans `VERSION` (clé `version` de `etat`) ;
- `validate`, `backtest` et `serve` sont **refusés** (code 8, avant même l'analyse des arguments) : la
  validation n'est pas livrée dans Odoo, et aucun serveur web du moteur ne tourne en production (§ A.16) ;
- `recommend` et `report` **refusent un historique incomplet** (code 1, § A.11), sauf
  `--accepter-historique-incomplet`.

Hors mode embarqué, les commandes gardent leur comportement d'avant, sauf les corrections listées
au § A.15.

### A.3 Variables lues par le moteur

| Variable | Rôle | Mode embarqué |
|---|---|---|
| `BRVM_ALPHA_EMBARQUE` | `1` : mode embarqué (inutile si `VERSION` est présent) | — |
| `BRVM_ALPHA_DONNEES` | dossier des données : `boc_text/`, `panel/`, `notes/` (journal, cache, verrous) | **obligatoire**, absolu |
| `BRVM_ALPHA_RAPPORTS` | rapports écrits (`rapport_AAAA-MM-JJ.html`, exports, `--sortie`) | **obligatoire**, absolu |
| `BRVM_ALPHA_PROXY` | mandataire HTTPS explicite pour www.brvm.org | facultatif |
| `BRVM_ALPHA_ATTENTE_VERROU` | attente maximale d'un verrou, en secondes (défaut 10) ; vaut pour **tous** les verrous, journal des notes compris | facultatif |
| `BRVM_ALPHA_MEMOIRE_MIN` | limite de mémoire virtuelle minimale, en Mo (défaut 1024 ; `0` : aucun contrôle) ; en dessous, code 6 sans rien charger (§ A.10) | facultatif |
| `BRVM_ALPHA_CPU_MIN` | marge minimale de temps de calcul, en secondes (défaut 900 ; `0` : aucun contrôle) : limite souple `RLIMIT_CPU` moins le temps déjà consommé ; en dessous, code 8 sans rien charger (§ A.6). Une valeur négative ou illisible (`-5`, `abc`, `nan`) prend le défaut de 900 s, et le message de refus le dit : seul `0` coupe le contrôle | facultatif, à laisser vide |
| `TMPDIR` | dossier des fichiers temporaires (défaut `/tmp`) ; un dossier **dédié** au moteur est conseillé (§ A.6) | conseillé |

Avec `python3 -I`, les variables `PYTHON…` (dont `PYTHONPATH` et `PYTHONDONTWRITEBYTECODE`) sont
ignorées : c'est voulu. Le code est trouvé par le fichier `.pth` (§ A.5), et `-B` remplace
`PYTHONDONTWRITEBYTECODE`.

### A.4 Export du code

```sh
sh deploiement/exporter-moteur.sh /chemin/hors/du/depot/moteur
```

- Copie **seulement** `brvm_alpha/` (fichiers suivis par git et nouveaux fichiers non ignorés ; jamais
  `__pycache__`, `*.pyc` ni fichier caché), `configs/`, `reports/validation_S1/`, `reports/diagnostic_S0*/`,
  `reports/trials.parquet` et `deploiement/requirements-moteur-py311.txt`. Ni tests, ni documentation
  (`docs/research` et ses scripts d'étude compris), ni données, ni scripts de déploiement. S'il existe,
  `reports/suivi_S2/` (déclaration signée du suivi sur papier, § A.17) part aussi.
- Écrit `VERSION` : première ligne = commit court (suivi de `+modifie` si le code exporté diffère du
  commit), puis la date UTC, le commit long, le nombre de fichiers et l'empreinte sha256 de chaque fichier.
  Vérification, dans le dossier exporté : les empreintes, puis la liste des fichiers (un fichier ajouté, un `.pyc`
  dans `__pycache__` compris, n'est pas vu par les seules empreintes ; avec `-B`, un `.pyc` déjà présent serait lu) :

  ```sh
  grep -E '^[0-9a-f]{64}  ' VERSION | sha256sum -c --quiet \
    && [ "$(find . -type f ! -path ./VERSION | sed 's#^\./##' | sort)" = "$(grep -E '^[0-9a-f]{64}  ' VERSION | cut -c67- | sort)" ] \
    && echo export conforme
  ```
- Refuse un dossier situé dans le code ou non vide (code 2), liens symboliques et « .. » résolus (chemin réel du
  dossier existant le plus proche ; un « .. » après un dossier absent est refusé) : avant `a58b4c8` compris, la
  comparaison se faisait sur le texte, et `…/../brvm-alpha/brvm_alpha/x` ou un lien vers le paquet passaient.
  Sans git, la liste vient de l'arbre, sous la version « inconnu », sans contrôle des fichiers en trop : un
  avertissement le dit ; les copies de secours (`*~`, `*.orig`, `*.rej`, `*.swp`) sont écartées. Mesuré : 110 fichiers,
  11 Mo.
- Le module Odoo garde ces fichiers **frères** (`brvm_alpha/`, `configs/`, `reports/` au même niveau) : le
  moteur les lit à côté de son code. Le code peut être en lecture seule.

### A.5 Interpréteur et paquets (hors ligne)

Références versionnées dans `deploiement/` :

- `python-autonome.txt` : CPython **3.11.15** (python-build-standalone, publication 20260718), archive
  `cpython-3.11.15+20260718-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`, **30 930 344 octets**,
  sha256 `23ccae6f1ff73e8aa8378436f869da003b8eb7d6c95f2bc706f494115ba1447d` (conforme au `SHA256SUMS`
  publié), adresse https://github.com/astral-sh/python-build-standalone/releases/download/20260718/cpython-3.11.15%2B20260718-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz ;
- `requirements-moteur-py311.txt` : le **jeu minimal**, 16 paquets en versions exactes (pandas 3.1.1,
  numpy 2.4.6, scipy 1.17.1, pyarrow 26.0.1, pyyaml 6.0.4, requests 2.34.2, beautifulsoup4 4.15.0,
  lxml 6.1.3, python-dateutil 4.0.0, tzdata 2026.6, soupsieve 4.1.3, certifi 2026.11.20,
  charset-normalizer 3.5.2, idna 3.20, urllib3 2.8.0, typing-extensions 4.16.0). Absents exprès :
  statsmodels et scikit-learn (`validate`, `backtest`), pdfplumber et ses dépendances (repli quand
  pdftotext manque, interdit en mode embarqué) ;
- `roues-py311-x86_64.tsv` : nom exact, taille et sha256 de chacune des 16 roues (cp311, manylinux,
  x86_64 ; 127,0 Mo en tout, la plus grosse 55 Mo : aucune au-delà de 100 Mo) ;
- `requirements-tests-py311.txt` : le jeu complet (38 paquets, pytest compris) de la suite de tests
  sous Python 3.11 ; ce n'est pas le moteur.

**Préparation** (préproduction, machine reliée à Internet) :

```sh
sh deploiement/preparer-python-et-roues.sh /chemin/depot-prive-erp/brvm-alpha-paquets
```

Télécharge l'archive (curl) et les roues (`pip download --only-binary=:all: --platform
manylinux_2_28_x86_64 --platform manylinux_2_27_x86_64 --platform manylinux_2_17_x86_64 --platform
manylinux2014_x86_64 --python-version 3.11.15 --implementation cp --abi cp311 --abi abi3 --abi none
--no-deps --require-hashes`), vérifie taille et sha256 de chaque fichier et refuse tout écart (le fichier
fautif est retiré, code 1). N'installe rien. Refuse un dossier relatif ou situé dans le dépôt (code 2) :
l'archive et les roues vont dans le dépôt **privé** de l'ERP, jamais ici (`.gitignore` écarte `*.whl` et
`cpython-*.tar.gz`). `BRVM_DEPUIS=/dossier` reprend des fichiers déjà téléchargés au lieu de les
télécharger (ils sont vérifiés de la même façon). `BRVM_PIP_PYTHON` (défaut `python3`) : interpréteur qui lance
`pip download` sur la machine de préparation (il n'a pas besoin d'être en 3.11 : les options `--platform` et
`--python-version` fixent les roues). Mesuré ici : 8 s.

**Installation** (dans un `RUN` du Dockerfile de l'image Odoo, sans réseau) :

```sh
sh deploiement/installer-python-et-roues.sh /opt/rz-brvm-alpha /chemin/paquets /chemin/module/moteur
# PREFIXE vaut /opt/rz-brvm-alpha s'il est omis : sh installer-python-et-roues.sh DOSSIER CODE
```

1. vérifie taille et sha256 de l'archive et des 16 roues, **et rien d'autre dans le dossier des roues** (tout
   fichier de plus est refusé, `*.whl` ou non, fichiers cachés compris), avant toute extraction ;
2. extrait l'archive dans `PREFIXE/python` (dossier temporaire voisin, puis renommage) et contrôle que
   c'est CPython 3.11.15 ;
3. installe les roues **hors ligne** :
   `PREFIXE/python/bin/python3.11 -I -m pip install --no-index --find-links DOSSIER/roues --require-hashes
   --no-deps --only-binary=:all: --target PREFIXE/lib -r <exigences avec empreintes>` (mandataire
   volontairement invalide : tout accès réseau échouerait) ;
4. écrit `PREFIXE/python/lib/python3.11/site-packages/rz_brvm_alpha.pth`, qui liste `PREFIXE/lib` puis le
   dossier du code (le code reste dans le module Odoo) ;
5. **contrôle final** : import des 16 paquets et de `brvm_alpha`, puis `PREFIXE/python/bin/python3.11 -I -B -m
   brvm_alpha etat --format json` en mode embarqué, avec des dossiers de données et de rapports
   temporaires (créés d'abord : le moteur ne les crée pas) : code 0 ou 1 **et** un objet JSON portant la clé
   `bandeau`, sinon échec.

Codes : 0 installé et vérifié ; 1 échec ; 2 mauvaise utilisation ; jamais 3. Refuse un `PREFIXE/python`
déjà présent ou un `PREFIXE/lib` non vide. `BRVM_LIB` (défaut `PREFIXE/lib`, chemin absolu exigé) : dossier où
les roues sont installées (`pip --target`), listé dans le `.pth`. Mesuré ici : 15 s. Paquet système à ajouter à l'image :
**poppler-utils** (`apt-get install -y --no-install-recommends poppler-utils`, puis `pdftotext -v` pour
faire échouer la construction s'il manque). Le script le signale s'il est absent, sans échouer.

### A.6 Lancement par Odoo

Ligne exacte (environnement explicite, rien hérité d'Odoo) :

```sh
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 HOME=/var/lib/odoo/rz_brvm_alpha TMPDIR=/var/lib/odoo/rz_brvm_alpha/tmp \
    BRVM_ALPHA_DONNEES=/var/lib/odoo/rz_brvm_alpha/donnees \
    BRVM_ALPHA_RAPPORTS=/var/lib/odoo/rz_brvm_alpha/rapports \
    /opt/rz-brvm-alpha/python/bin/python3.11 -I -B -m brvm_alpha etat --format json
```

(Les dossiers sont des exemples : ceux du volume de données d'Odoo, jamais dans le module.)

Règles du lanceur :

- **`-I -B`** : `-I` ignore `PYTHONPATH` et le dossier courant (seul le `.pth` donne le chemin du code) ;
  `-B` : aucun `.pyc` écrit ;
- **mémoire** : Odoo ne pose que la limite **douce** de `RLIMIT_AS` (`limit_memory_hard`), dont hérite le
  sous-processus ; le lanceur la **relève à 3 Go** (sans dépasser la limite dure). Toutes les commandes
  embarquées tiennent sous 0,9 Go de mémoire virtuelle, enfants compris (§ A.10) ;
- **temps de calcul** : un travailleur Odoo pose sur lui-même une limite **souple** de temps de calcul
  (`RLIMIT_CPU` = temps déjà consommé + `limit_time_cpu`, la limite dure ne change pas), dont hérite le
  sous-processus ; le lanceur la **relève à la limite dure** (souple = dure). Temps de calcul mesurés :
  `recommend` 14 s, `report` 16 s, `panel --force` 13 s pour le processus principal et 40 s pour **chaque**
  processus de travail (chacun a sa propre limite). Au démarrage, si la marge (limite souple moins temps déjà
  consommé) est sous 900 s (`BRVM_ALPHA_CPU_MIN`), le moteur sort aussitôt en **8** (« limite de temps de calcul
  trop basse … : le lanceur doit relever RLIMIT_CPU ») ; il ne relève jamais la limite lui-même. Limite atteinte en
  cours de commande (signal `SIGXCPU`) : sortie propre en 8 avec un objet JSON ; processus de travail du panel tué
  par `SIGXCPU` : 8 « temps de calcul » (avant : −24 sans objet JSON, ou 6 « memoire »). Le `preexec_fn` du lanceur
  reste **court** (quelques appels système) : le temps de calcul consommé entre `fork` et `exec` compte pour le
  moteur, et un `SIGXCPU` reçu dans ses toutes premières millisecondes, avant que sa garde ne soit posée, donne −24
  sans objet JSON (§ A.7) ;
- **dossier temporaire** : donner au moteur un `TMPDIR` **dédié** (par exemple
  `/var/lib/odoo/rz_brvm_alpha/tmp`, créé par le module, 70 caractères au plus). `--fichier`, `--portefeuille` et
  `--sortie` acceptent le dossier temporaire du système : avec `TMPDIR=/tmp`, partagé avec Odoo, un chemin relayé
  pourrait y lire ou y écrire un fichier d'Odoo. Au-delà de 70 caractères, le socket des processus de travail du
  panel ne tient plus dans un chemin de socket Unix (`/tmp` est alors pris le temps du panel) ;
- **purge de `<T>`** (le `TMPDIR` dédié) : conseillée après chaque lancement (fichiers de titre ou de motif écrits par
  le module, § A.9 ; restes d'un moteur arrêté par `KILL`, comme le dossier du socket des processus de travail du
  panel), quand aucun autre lancement n'utilise ce même `<T>` ;
- **`HOME`** : le dossier des données (`<D>`), son parent comme dans la ligne ci-dessus, ou `<D>/home` (créé par le
  module) sont admis. Le moteur ne lit rien sous `HOME`, sauf par `expanduser` d'un chemin donné en option
  (`~/…`), qu'Odoo ne passe pas. Mesuré le 23/11/2026 (code exporté, CPython 3.11.15 autonome, `env -i`,
  `HOME=<D>/home` vide, accès aux fichiers relevés par `strace -f`) : `panel`, `etat`, `notes add`, `notes list`,
  `recommend`, `indices` et une extraction par `pdftotext` n'ouvrent aucun fichier sous `HOME`, qui reste vide ;
  seul `etat` parcourt `<D>/home` en mesurant la taille du dossier des données (`donnees.taille_octets`) ;
- **dossiers** : le module crée `BRVM_ALPHA_DONNEES`, `BRVM_ALPHA_RAPPORTS` et le `TMPDIR` dédié à
  l'installation (code 8 si les deux premiers manquent) ;
- **groupe de processus** : nouveau groupe (`start_new_session=True`) ; au-delà du délai, `TERM` au
  **groupe** (le moteur s'arrête proprement : code 130, dès le démarrage, chargement de pandas compris), puis
  `KILL` au groupe après 15 s. Le `KILL` au groupe est **obligatoire** : un processus figé dans une
  bibliothèque compilée (OpenBLAS, Arrow) sous une mémoire trop basse ne traite plus `TERM`. Toujours tuer le
  **groupe**, jamais le seul PID : les processus de travail du panel et leur serveur de processus meurent avec
  le processus principal (`PR_SET_PDEATHSIG`, § A.7), mais seul un `KILL` au groupe nettoie tout à coup sûr (cas du
  tueur de mémoire du noyau) ;
- **sorties** : sortie standard et sortie d'erreur redirigées vers des **fichiers** (jamais un tube non
  lu, qui figerait le moteur) ; lire l'objet JSON dans le fichier de sortie standard ;
- **récolte des processus** : la règle dépend de l'endroit où tourne le lanceur.
  - Lanceur **dans le travailleur Odoo** (l'exemple ci-dessous) : n'attendre que l'enfant direct (`p.wait`), **jamais**
    `PR_SET_CHILD_SUBREAPER`, **jamais** `waitpid(-1)`. Le travailleur récolterait sinon les autres enfants d'Odoo
    (leur `Popen.wait` perdrait leur code) et deviendrait le parent d'orphelins qu'il ne récolte pas. Un petit-enfant
    orphelin du moteur revient alors au processus 1 du conteneur (§ A.7).
  - Lanceur **processus dédié** (petit programme lancé par Odoo, qui n'attend que lui ; il lance le moteur et ne fait
    rien d'autre) : il **peut** se faire récolteur (`prctl(PR_SET_CHILD_SUBREAPER, 1)`), ce qui retire le risque d'un
    code 3 récolté par le processus 1, à **trois conditions** :
    (a) il attend d'abord son enfant direct par `Popen.wait`, dans **un seul fil**, **sans gestionnaire de
    `SIGCHLD`** (un autre fil ou un gestionnaire qui récolterait le moteur avant `Popen.wait` lui ferait perdre le
    code du moteur : `Popen` rend alors 0) ;
    (b) il récolte **jusqu'à `ECHILD`** avant toute sortie (`os.waitpid(-1, …)` jusqu'à `ChildProcessError`), y
    compris après le `KILL` ciblé du groupe du moteur et sur erreur ou arrêt du lanceur (bloc `finally`, TERM et
    Ctrl+C du lanceur changés en exception) ;
    (c) sa propre sortie vaut **0 ou 1, jamais 3** (`os._exit` dans le `finally`) : le code et l'objet JSON du
    moteur passent par des fichiers, et un lanceur resté orphelin (travailleur Odoo tué) peut être récolté sans
    risque par le maître Odoo.
    Un seul fil : `preexec_fn` y est sûr. Exemple essayé (`test_controle_retouches.py`) : second bloc ci-dessous ;
- **une seule opération longue à la fois** côté Odoo (§ A.12 : verrous du moteur).

Exemple de lanceur Odoo (Python), à adapter :

```python
import json, os, resource, signal, subprocess

MOTEUR = "/opt/rz-brvm-alpha/python/bin/python3.11"
TROIS_GO = 3 * 1024 ** 3

def _limite():  # dans l'enfant, avant exec
    _soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    soft = TROIS_GO if hard == resource.RLIM_INFINITY else min(TROIS_GO, hard)
    resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    # Temps de calcul : le travailleur Odoo a baissé sa limite souple (limit_time_cpu), le moteur en hérite ;
    # elle est relevée à la limite dure, qu'Odoo ne touche pas.
    _soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
    resource.setrlimit(resource.RLIMIT_CPU, (hard, hard))

def lancer(args, delai_s, sortie, erreurs, donnees, rapports, tmp):
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": donnees, "TMPDIR": tmp,  # TMPDIR dédié
           "BRVM_ALPHA_DONNEES": donnees, "BRVM_ALPHA_RAPPORTS": rapports}
    with open(sortie, "wb") as out, open(erreurs, "wb") as err:
        p = subprocess.Popen([MOTEUR, "-I", "-B", "-m", "brvm_alpha", *args, "--format", "json"],
                             env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                             preexec_fn=_limite, start_new_session=True, close_fds=True)
        try:
            code = p.wait(delai_s)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                code = p.wait(15)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                code = p.wait()
    try:
        with open(sortie, encoding="utf-8") as fh:
            resultat = json.load(fh)  # un objet : {"ok": …, "bandeau": …}, erreur comprise
    except ValueError:  # aucun objet : tué par KILL (ou par le chargeur, § A.7) avant d'avoir pu répondre
        resultat = {"ok": False, "code": 7, "erreur": "interne", "message": "moteur arrêté sans réponse"}
    return code, resultat
```

Dans un Odoo multi-fils (mode développement), `preexec_fn` n'est pas sûr : préfixer plutôt la commande par
`prlimit --as=3221225472: --cpu=unlimited: --` (util-linux ; si la limite dure de temps de calcul est finie,
donner sa valeur à la place de `unlimited`).

Exemple de **lanceur dédié** récolteur (programme à part, conditions (a), (b) et (c) ci-dessus), à adapter. Odoo le
lance, n'attend que lui (`p.wait`, délai plus large que `delai_s + grace_s` + 10 s), puis lit `resultat`
(`{"code": …, "orphelins": […]}`) et l'objet JSON du moteur dans `sortie` :

```python
# Lanceur dédié : processus à part, en un seul fil, sans gestionnaire de SIGCHLD. Il lance le moteur, récolte les
# orphelins du moteur et sort toujours en 0 ou 1 (jamais 3). Code du moteur et objet JSON : dans des fichiers.
import contextlib, ctypes, json, os, signal, subprocess, time

PR_SET_CHILD_SUBREAPER = 36


class ArretLanceur(Exception):
    """TERM ou Ctrl+C reçu par le lanceur : le moteur est arrêté, ses processus récoltés, puis sortie en 1."""


def _arret(signum, _frame):
    raise ArretLanceur(signal.Signals(signum).name)


def _recolter(groupe, attente_s=10.0):
    """(b) Récolte jusqu'à ECHILD ; un orphelin encore vivant après attente_s : KILL au seul groupe du moteur."""
    codes, fin, tue = [], time.monotonic() + attente_s, groupe is None
    while True:
        try:
            pid, statut = os.waitpid(-1, 0 if tue else os.WNOHANG)
        except ChildProcessError:  # ECHILD : plus aucun enfant
            return codes
        if pid:
            codes.append(os.waitstatus_to_exitcode(statut))
        elif time.monotonic() < fin:
            time.sleep(0.05)
        else:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(groupe, signal.SIGKILL)
            tue = True


def lancer_dedie(cmd, env, delai_s, sortie, erreurs, resultat, preexec_fn=None, grace_s=15.0):
    """Lance le moteur, écrit {"code", "orphelins"} dans resultat ; ne rend jamais la main (os._exit 0 ou 1)."""
    signal.signal(signal.SIGTERM, _arret)
    signal.signal(signal.SIGINT, _arret)
    code = groupe = None
    sortie_lanceur = 1
    try:
        if ctypes.CDLL(None, use_errno=True).prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER refusé")
        with open(sortie, "wb") as out, open(erreurs, "wb") as err:
            p = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 preexec_fn=preexec_fn, start_new_session=True, close_fds=True)
            groupe = p.pid
            try:
                code = p.wait(delai_s)  # (a) l'enfant direct d'abord, par Popen.wait
            except subprocess.TimeoutExpired:
                os.killpg(groupe, signal.SIGTERM)  # le moteur sort en 130 avec son objet JSON
                try:
                    code = p.wait(grace_s)
                except subprocess.TimeoutExpired:
                    os.killpg(groupe, signal.SIGKILL)  # KILL ciblé : le seul groupe du moteur
                    code = p.wait()
    except BaseException:
        if groupe is not None and code is None:  # arrêt du lanceur ou erreur : le moteur ne lui survit pas
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(groupe, signal.SIGKILL)
        raise
    finally:
        try:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            orphelins = _recolter(groupe)  # (b) avant toute sortie, erreur comprise
            with open(resultat, "w", encoding="utf-8") as fh:
                json.dump({"code": code, "orphelins": orphelins}, fh)
            sortie_lanceur = 0 if code is not None else 1
        finally:
            os._exit(sortie_lanceur)  # (c) 0 ou 1, jamais 3
```

Un code négatif, 120, 127 ou un objet JSON absent se traitent comme 7 (§ A.7) ; `orphelins` liste les codes des
processus du moteur récoltés par le lanceur (un 3 d'un outil de poppler y apparaît sans effet sur rien).

### A.7 Codes de retour

Mêmes codes pour toutes les commandes, en mode normal comme embarqué (`brvm_alpha.erreurs`). Le
moteur ne sort **jamais** en 3 : aucune commande, aucun script de `deploiement/` (test
`test_no_exit_code_3_anywhere_in_the_package_and_the_scripts`) ; un `SystemExit(3)` venu d'une
bibliothèque devient 7.

| Code | `erreur` (JSON) | Sens | Exemples |
|---|---|---|---|
| 0 | — | succès | |
| 1 | `donnees_absentes`, `historique_incomplet` | données absentes ou illisibles, historique non prêt, quota de requêtes atteint | panel introuvable ou abîmé (`.parquet` illisible : « panel illisible ») ; `panel` sans aucun bulletin dans `boc_text/` (installation neuve : « aucun bulletin dans … : lancer d'abord update » ; avant : 7, « KeyError : file ») ; journal des notes présent mais illisible ; `recommend` sur un historique incomplet (mode embarqué) ; `update` arrêté au quota |
| 2 | `saisie_invalide` | saisie invalide ou refusée, erreurs d'arguments comprises ; **seulement** les saisies | option inconnue, `--couts inconnu`, `--delai nan`, date dans S1, URL invalide, `--racine` inexistant, cible inconnue, `--sortie` vers un dossier ; en mode embarqué, chemin hors des dossiers permis ou option de chemin vide (§ A.2) |
| 4 | `verrou_occupe` | verrou tenu par une autre opération au-delà du délai | deux `panel`, deux `update`, deux `notes research` à la fois ; requête d'une autre session vers le site encore en cours après plus de 32 min (verrou d'envoi, § A.15) |
| 5 | `acces_refuse` | accès refusé ou réseau | HTTP 403 ou 429, site bloqué, liste blanche, délai dépassé |
| 6 | `memoire` | mémoire insuffisante | `MemoryError` (jamais avalée : aucun résultat dégradé en code 0) ; bibliothèque compilée impossible à charger faute de mémoire (« failed to map segment ») ; processus de travail du panel tué par `SIGKILL` sous une limite de mémoire, ou mort sans cause connue sous cette limite (le message dit « cause inconnue ») ; limite `RLIMIT_AS` sous 1 Go (refus au démarrage) |
| 7 | `interne` | erreur interne (exception non prévue) ; trace sur la sortie d'erreur | défaut du moteur ; `ValueError` ou `KeyError` d'une bibliothèque ; processus de travail du panel tué par `SIGSEGV`, `SIGABRT` ou un autre signal qui n'est pas un manque de mémoire |
| 8 | `configuration` | configuration manquante ou invalide | dossiers absents, relatifs ou inexistants en mode embarqué, pdftotext absent, paquet Python manquant, dossier de données ou de rapports non inscriptible (lecture seule, droits, disque plein), état de politesse illisible, `politeness.json`, son verrou, le verrou d'envoi `politeness.envoi.<site>.lock` ou la marque « envoi en cours » impossibles à écrire (disque plein, lecture seule, droits : rien n'est envoyé, § A.15), disque plein ou volume en lecture seule même sans nom de fichier dans l'erreur (avant : 7), `validate`, `backtest` ou `serve` en mode embarqué ; limite de temps de calcul (`RLIMIT_CPU`) trop basse au démarrage, ou atteinte en cours de commande (`SIGXCPU`), processus de travail du panel compris (« temps de calcul ») |
| 130 | `interruption` | interruption : Ctrl+C ou signal TERM | délai du lanceur dépassé |

Le moteur ramène tout autre code à 7 (un `SystemExit(259)` sortirait sinon en 3, car le statut d'un
processus est le code modulo 256). Un code hors table vient de l'interpréteur ou du chargeur, pas du moteur :
120 (sortie standard impossible à vider), 127 (« cannot allocate memory for thread-local data » : le chargeur
dynamique n'a pas pu démarrer l'interpréteur), 1 sans objet JSON (OpenBLAS ou l'interpréteur avant le
moteur), ou une valeur négative côté Python (tué par un signal : −9 pour `KILL`, −11 pour une erreur de
segmentation sous une mémoire trop basse, −15 pour un `TERM` ou −24 pour un `SIGXCPU` reçus dans les toutes
premières millisecondes, avant que la garde du démarrage ne soit posée). Sous les limites du § A.6 (3 Go, temps de
calcul relevé), aucun de ces cas n'a été observé. Les traiter comme 7. Avec `--format json`, une sortie standard
fermée par le lecteur donne 1 (l'objet n'a pas pu être lu).

**Petits-enfants.** Les processus que lance le moteur sont liés à lui par `PR_SET_PDEATHSIG` : s'il est tué seul
(`KILL` au seul PID, tueur de mémoire du noyau), ils meurent avec lui.

- **Outils de poppler** (`pdftotext`, `pdfinfo`, `pdffonts`, `pdfimages`) : un outil **en cours** meurt avec le
  moteur (code −9). Vérifié : un `pdftotext` lent (faux outil qui dort puis sort en 3) meurt avec le moteur (avant :
  récolté 4 s plus tard par le processus 1, avec le code 3). Un outil **déjà sorti** est récolté par le moteur dès sa
  fin (le noyau le réveille : `pidfd_open`) ; avant, il restait jusqu'à 50 ms en attente. Mesuré : de 0 à 0,4 ms
  (avant : 0,4 à 49,5 ms). **Le risque reste** : si le moteur est tué seul dans ce court instant, l'outil sorti est
  récolté par le processus 1 avec son propre code, et poppler documente un code 3 (PDF protégé contre la copie ;
  poppler 24.02 sort pourtant en 0 sur un tel PDF).
- **Panel** : le serveur de processus est lié au moteur, et chaque processus de travail à ce serveur. Un processus
  de travail qui pose son lien alors que le serveur est déjà mort (moteur tué juste au démarrage du pool) s'arrête
  aussitôt, en code 1 (avant : il restait vivant, orphelin, avec le `resource_tracker`, plus de 90 s). Le
  `resource_tracker` sort de lui-même, en code 0, quand le dernier processus de travail est mort. Mesuré : KILL du
  seul moteur de 0 à 100 ms après le premier processus de travail, 12 essais : aucun processus vivant 8 s plus tard,
  aucun code 3 (avant : des orphelins dans 10 essais sur 13).

Le module Odoo doit de toute façon lancer le moteur dans un **nouveau groupe de processus** et tuer le **groupe**. Un
lanceur qui tourne **dans le travailleur Odoo** ne se fait jamais **récolteur des petits-enfants** (pas de
`PR_SET_CHILD_SUBREAPER`, pas de `waitpid(-1)`) : il n'attend que son enfant direct. Un petit-enfant orphelin est
alors récolté par le processus 1 du conteneur : si c'est le maître Odoo, le risque d'un code 3 récolté ne disparaît
qu'avec un vrai processus 1 (par exemple `tini` ou `dumb-init` en tête de l'image), qui récolte les orphelins sans
s'arrêter (non vérifié dans l'image odoo:17.0), **ou** avec un **lanceur dédié** qui se fait récolteur aux trois
conditions du § A.6 : il attend d'abord le moteur par `Popen.wait` dans un seul fil sans gestionnaire de `SIGCHLD`,
récolte jusqu'à `ECHILD` avant toute sortie (après le `KILL` ciblé du groupe et sur erreur compris), et ne sort
jamais en 3 (`os._exit(0)` ou `os._exit(1)`). Les orphelins du moteur lui reviennent alors, jamais au processus 1.
La règle « jamais de récolteur » ne vaut donc que pour un lanceur qui tourne dans le travailleur Odoo.

### A.8 Sortie JSON

Avec `--format json`, la sortie standard porte **exactement un objet JSON**, erreur comprise ;
avertissements et progression vont sur la sortie d'erreur. Pendant l'écriture de l'objet, TERM et `SIGXCPU` sont
reportés : l'objet n'est jamais coupé, ni suivi d'un second objet (avant : un signal reçu pendant l'écriture d'un gros
objet vers un tube donnait un objet coupé puis un second objet). Une fois l'objet écrit, TERM et `SIGXCPU` ne changent
plus le code de sortie : c'est celui de l'objet. Pour `notes add`, `notes archive`, `notes export`, `recommend
--sortie` et `report`, dont l'écriture est la dernière étape, TERM et `SIGXCPU` sont aussi reportés du dernier instant
de l'écriture (ligne ajoutée au journal, renommage du fichier) jusqu'à l'objet : une note enregistrée sort en 0 avec son
objet, jamais en 8 « arrêtée » (avant : 3 fois en 40 essais). Avant cet instant, TERM arrête la commande comme avant (130),
y compris pendant l'attente d'un verrou. Les écritures de `plan`, `plan grille` et `suivi` (§ A.17) ne sont jamais
coupées non plus : l'écriture se termine, puis la commande rend son résultat si c'était sa dernière étape, ou s'arrête
en 130 (8 pour `SIGXCPU`) si elle avait encore à faire. Si la sortie standard est un tube que personne ne lit, le moteur reste bloqué
sur l'écriture, et seul `KILL` l'arrête : d'où la règle du § A.6 (sorties dans des fichiers). Succès : `{"ok": true, …, "bandeau": "…"}`.
Erreur : `{"ok": false, "code": N, "erreur": "<type>", "message": "<texte français>", "bandeau": "…"}`,
parfois avec un bilan en plus (`update`, `notes research`, `report`). Une erreur d'arguments donne aussi
cet objet (code 2), comme un échec au démarrage (mémoire trop basse : 6 ; paquet manquant : 8 ; TERM : 130).
`--help` avec `--format json` : l'aide sur la sortie d'erreur et `{"ok": true, "aide": "…", "bandeau": "…"}`
sur la sortie standard (code 0). Exemple réel :

```json
{
 "ok": false,
 "code": 1,
 "erreur": "historique_incomplet",
 "message": "refusé : le rapport sur un historique incomplet (2 180 jour(s) ouvré(s) sans bulletin ni marqueur depuis le 02/01/2017). Mode embarqué : compléter d'abord la collecte (update, puis panel), ou relancer avec --accepter-historique-incomplet.",
 "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti."
}
```

La clé `bandeau` porte toujours la phrase « Performance passée ≠ garantie. Aucun gain n'est garanti. » :
l'afficher avec tout résultat montré à l'utilisateur.

### A.9 Commandes utiles à Odoo

Durées mesurées le 23/11/2026 sur la machine de développement (4 processeurs, pas le serveur) : CPython
3.11.15 autonome, jeu minimal, mode embarqué, code exporté en lecture seule, copie des données réelles
(2 334 bulletins, 861 notes), `RLIMIT_AS` à 3 Go. Compter plus long sur un processeur modeste. Toutes les
lignes finissent par `--format json`. « Court » : appel synchrone (moins de 45 s) ; « long » : travail
détaché.

| Commande | Durée | Nature | Écrit | Verrous |
|---|---|---|---|---|
| `etat` | 1,9 s | court | rien | panel partagé (5 s) |
| `notes add --cible SNTS --titre-fichier <T>/titre.txt --fichier <T>/texte.txt [--avis] [--conviction] [--publie-le] [--veto]` (ou `--titre …`, `--texte …`) | 1,1 s | court | `notes/notes.jsonl` (ajout d'une ligne, fsync) | `notes/notes.jsonl.lock` |
| `notes list [--cible] [--depuis] [--statut] [--limite]` | 0,6 s | court | rien | — |
| `notes show ID` | 0,5 s | court | rien | — |
| `notes archive ID [--motif-fichier <T>/motif.txt]` (ou `--motif …`) | 0,7 s | court | `notes/notes.jsonl` (nouvelle version) | `notes/notes.jsonl.lock` |
| `indices` | 4,9 s | court | rien | — |
| `indices dossier IDX:BRVM-30` | 3,8 s | court | rien | — |
| `explain SNTS` | 6,8 s | court | rien | — |
| `recommend --capital 10000000 [--portefeuille f.csv] [--cash] [--couts central]` | 14,6 s | court | rien, ou `--sortie` (écriture atomique) | — |
| `report --capital 10000000 --sortie nom.html` | 18,7 s | long | `--sortie` (atomique) ; sans `--sortie`, `<rapports>/rapport_AAAA-MM-JJ.html`, **même nom pour tout capital** : Odoo passe toujours `--sortie` | — |
| `update --sans-panel [--max-requetes 200] [--delai 10] [--rouvrir AAAA-MM-JJ[..AAAA-MM-JJ]]` | minutes | long | `boc_text/boc_*.txt.gz`, `.meta.json`, `.missing`, `.bad` ; `notes/cache/politeness.json`, `notes/fetch_log.jsonl` | `boc_text/.telechargement.lock`, `notes/cache/politeness.json.lock`, `notes/cache/politeness.envoi.www.brvm.org.lock` (tenu pendant chaque requête) |
| `update --simulation` | 0,6 s | court | rien | — |
| `panel` (rien de nouveau) | 5,8 s | long | `panel/` (construction à côté, puis bascule) | `.panel.construction.lock`, attend `.panel.lecture.lock` |
| `panel --force` (tout l'historique) | 50 s | long | `panel/` | idem |
| `notes research [--pdf 20]` | jusqu'à 30 min | long | `notes/notes.jsonl` (au fil de l'eau), `notes/cache/`, `notes/fetch_log.jsonl` | `notes/.recherche.lock`, `notes/notes.jsonl.lock`, `politeness.json.lock`, `politeness.envoi.www.brvm.org.lock` |
| `notes research --hors-ligne --pdf 0` | 4,8 s | court | `notes/notes.jsonl` s'il y a du nouveau | idem |
| `notes lire [--max 20] [--hors-ligne]` | 10 s hors ligne ; ≈ 10 s par document en ligne | long | `notes/notes.jsonl`, `notes/cache/docs/` ; en ligne, aussi `notes/cache/politeness.json`, `notes/fetch_log.jsonl` | `notes/.recherche.lock`, `notes/notes.jsonl.lock` ; en ligne, aussi `notes/cache/politeness.json.lock` et `notes/cache/politeness.envoi.www.brvm.org.lock` (tenu pendant chaque requête) |
| `live [--symbole SNTS] [--hors-ligne]` | au moins 10 s en ligne si robots.txt n'est pas en cache (robots.txt, puis la page 10 s après) ; non mesuré contre le vrai site | long | `notes/cache/` (cache HTTP), `notes/cache/politeness.json`, `notes/fetch_log.jsonl` | en ligne : `notes/cache/politeness.json.lock`, `notes/cache/politeness.envoi.www.brvm.org.lock` (tenu pendant chaque requête) |

Les verrous sont des `flock` : jamais supprimés, rendus par le système à la mort du processus ; au-delà
de `BRVM_ALPHA_ATTENTE_VERROU` secondes (10 par défaut, pour tous les verrous, journal des notes compris),
code 4. Les commandes de **lecture** (`recommend`, `report`, `indices`, `explain`) ne prennent **pas** le verrou
de lecture du panel (seul `etat` le prend) : lancées pendant un `panel`, elles pourraient lire deux versions
du panel ; Odoo enchaîne donc ses travaux (§ A.12). Les chemins s'entendent dans
`BRVM_ALPHA_DONNEES` (`<rapports>` : `BRVM_ALPHA_RAPPORTS`). Les fichiers temporaires d'une écriture
atomique (`.<nom>.<pid>.<jeton>.part`, même dossier) disparaissent au renommage ; les processus de travail
du panel ouvrent un socket dans le dossier temporaire du système (un `TMPDIR` de plus de 70 caractères est
remplacé, le temps du panel, par `/tmp`).

**Clés JSON** (exemples réels, abrégés ; toutes les sorties portent `ok` et `bandeau`) :

- `etat` : `pret` (panel lisible **et** historique complet), `raison`, `historique_complet`, `version`,
  `releve_le`, `panel` {`derniere_seance`, `seances_presentes`, `seances_manquantes`, `seances_en_retard`,
  `retard`, `premiere_seance`, `lisible`, `erreur`, `dossier`}, `bulletins` {`en_cache`, `sans_bulletin`,
  `dernier`, `premier`, `jours_a_telecharger`, `jours_a_telecharger_depuis_2017`, `sans_bulletin_definitif`,
  `a_reessayer`, `jours_manquants`, `historique_complet`, `premier_jour_cherche`, `dossier`}, `site`
  {`bloque`, `depuis`, `code_http`}, `notes` {`journal_present`, `au_journal`, `en_vigueur`}, `rapport`
  {`nom`, `date`}, `donnees` {`taille_octets`, `taille`}, `extracteur_pdf` {`pdftotext`, `chemin`,
  `obligatoire`, `manquant`}, `limite_memoire` {`mo`, `seuil_mo`, `trop_basse`}, `embarque`, `avertissements`
  (phrases : pdftotext absent, lignes illisibles du journal, dossier non inscriptible, jours à réessayer, limite
  de mémoire trop basse, état de politesse illisible). `bulletins` porte aussi `sans_fichier`,
  `sans_bulletin_lisible` (marqueurs à réessayer, comptés comme manquants) et `prochaine_relance` ; `notes` porte
  `lisible`, `erreur` et `lignes_illisibles` (journal présent mais illisible : `pret` faux) ; `donnees` et
  `rapport` portent `inscriptible` ; `site` porte `etat_illisible` si `politeness.json` ne se lit pas. Code 0
  même si rien n'est prêt (8 sans dossiers en mode embarqué).

  ```json
  {"ok": true, "pret": true, "raison": null, "historique_complet": true, "version": "a3defe0+modifie",
   "releve_le": "2026-11-23T00:17:06Z",
   "panel": {"derniere_seance": "2026-11-20", "seances_presentes": 2334, "seances_manquantes": 129,
             "seances_en_retard": 0, "retard": null, "premiere_seance": "2017-01-02", "lisible": true, "erreur": null},
   "bulletins": {"en_cache": 2334, "sans_bulletin": 246, "dernier": "2026-11-20", "jours_a_telecharger": 1,
                 "jours_a_telecharger_depuis_2017": 1, "jours_manquants": 0, "historique_complet": true},
   "site": {"bloque": false, "depuis": null, "code_http": null},
   "notes": {"journal_present": true, "au_journal": 861, "en_vigueur": 114},
   "extracteur_pdf": {"pdftotext": true, "chemin": "/usr/bin/pdftotext", "obligatoire": true, "manquant": false},
   "embarque": true, "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti."}
  ```

- `notes add` : `note_id` (la note **au journal** : créée, ou déjà là), `note_id_saisie` (identifiant de la
  saisie), `cree` (faux : rien n'a été écrit), `doublon_id` (note existante : même identifiant, ou même
  contenu actif depuis moins de 30 jours), `meme_identifiant` (vrai si la saisie a exactement l'identifiant de
  la note existante : même contenu **et** même date de publication ; faux pour un doublon de contenu publié à
  une autre date), `deja_enregistree`,
  `score`, `filtres` (filtres de risque déclenchés), `veto`, `premiere_seance_negociable`,
  `seance_application` (première séance où la note compte en mode direct), `des_maintenant`,
  `notes_connues` (ligne « Notes connues au … »), `prise_en_compte`, `note` (fiche complète). Un doublon
  sort en code 0 avec `cree: false` (`--forcer` l'enregistre quand même). `--publie-le` est gardé tel
  quel. Saisie invalide : code 2, y compris une note dont **aucune** cible n'est reconnue (`--cible ZZZZ`,
  `--cible ""` : elle n'aurait aucun effet) ou sans titre ni texte.

  **Titre et motif lus dans un fichier** (pour qu'Odoo ne passe aucun texte libre en argument) :
  `notes add --titre-fichier CHEMIN` remplace `--titre`, `notes archive --motif-fichier CHEMIN` remplace `--motif`
  (le texte de la note se lit déjà par `--fichier`). Le module écrit le texte saisi dans un fichier de son `TMPDIR`
  dédié (ou des données), passe le chemin, puis le supprime. Règles, en mode normal comme embarqué (code 2 pour
  chacune, rien n'est écrit) :
  - lecture en **UTF-8 strict** (octets invalides refusés ; une marque d'ordre en tête est retirée) ; caractère nul
    refusé ; **bords retirés** (espaces, tabulations, sauts de ligne) ; contenu vide ou fait de blancs refusé ;
  - même borne que `--titre` : **500 caractères**, une fois les blancs répétés ramenés à une espace ; pour le motif,
    **200 caractères** (borne du formulaire de l'interface ; `--motif` lui-même n'en a pas, inchangé) ; fichier de
    **8 Kio** (8 192 octets) au plus, refusé avant d'être lu ;
  - chemin vide ou fait d'espaces refusé ; **lien symbolique**, dossier, tube ou périphérique refusés ; en mode
    embarqué, mêmes dossiers que `--fichier` (données, rapports, `TMPDIR`), chemin relatif compté depuis les données,
    et chemin réel contrôlé (§ A.2) ;
  - `--titre` avec `--titre-fichier`, ou `--motif` avec `--motif-fichier` : refusé (même `--titre ""`) ; aucune des
    deux n'est obligatoire (une note sans titre garde un texte ; un archivage peut se passer de motif) ;
  - la valeur lue suit ensuite **exactement** le chemin de `--titre` ou `--motif` (mêmes contrôles, même note : une
    saisie par fichier identique à une saisie par `--titre` est reconnue comme doublon). Objets JSON inchangés.

  ```json
  {"ok": true, "note_id": "a23383a04d2d12c10c0fe6328f2b2009a457d0c3", "cree": true, "doublon_id": null,
   "meme_identifiant": false, "score": 0.376, "filtres": [], "veto": false,
   "premiere_seance_negociable": "2026-11-23", "seance_application": "2026-11-23", "des_maintenant": true,
   "notes_connues": "Notes connues au 23/11/2026 00:17 UTC, appliquées à la séance du 23/11/2026",
   "prise_en_compte": "Prise en compte : dès maintenant, à la séance du 23/11/2026 (cours du 20/11/2026), …",
   "note": {"…": "…"}, "bandeau": "…"}
  ```

- `notes list` : `n`, `lignes_illisibles`, `notes` [{`note_id`, `version`, `published_at`,
  `first_tradable_session`, `author`, `source`, `title`, `all_targets`, `stance`, `conviction`, `status`,
  `score`, `materiality`, `confidence`, `risk_flags`}]. `notes show` : `note`, `versions`. `notes archive` :
  `note_id`, `version`, `statut`, `archivee`.
- `indices` : `asof`, `historique_complet`, `avertissement_historique`, `avertissement_panel`, `notes`
  {`ligne`, `mode`, `connues_au`, `seance_application`, `n_en_vigueur`, `filtres`, `notes_en_vigueur`…},
  `indices` [une ligne par indice : `label`, `level`, rendements, `stance`, `confidence`, `composite`,
  `reasons`…]. `indices dossier CODE` : `index`, `label`, `evaluation`, `composition`, `constituents`,
  `contributions`, `recent_notes`, `calendar`, `change_my_mind`, `reasons`, plus les mêmes clés de tête.
- `explain SYMBOLE` : `bandeau`, `historique_complet`, `avertissement_historique`, `avertissement_panel`,
  `notes` (état des notes), `decomposition` (blocs de signaux : `raw`, `z`, `weight`, `contribution`,
  `research_only`), `symbol`, `asof`, `variant`, `eligible`, `universe`, `score`, `weight`, `caps`,
  `risk_flags`, `valuation`, `text`, `choix_variante`.
- `recommend` : l'ordre de bataille complet (`statut`, `variante`, `choix`, `lignes`, `tranches`,
  `execution`, `couts`, `dividendes`, `revenus`, `distribution`, `stress`, `declencheurs`, `explications`,
  `faits`, `estimations`, `hypotheses`, `avertissements`, `meta`) plus `historique_complet` et
  `avertissement_historique`. Avec `--sortie`, le fichier porte cet objet et la sortie standard
  `{"ok": true, "chemin", "octets", "historique_complet", …}`.
- `report` : `chemin`, `date`, `capital`, `sections` [{`id`, `titre`, `statut` (`ok`, `indisponible`,
  `erreur`), `ok`, `message`, `code`, `duree_s`}], `sections_en_echec`, `historique_complet`,
  `avertissement_historique`, `notes_connues_au`, `avertissement_panel`. **Code non nul si la section
  « ordre » échoue** (son code : 1 indisponible, 8 configuration, 7 sinon), le rapport étant écrit quand
  même (`ok: false`, `chemin` donné).

  ```json
  {"ok": true, "chemin": "<rapports>/rapport_preuve.html", "date": "2026-11-20", "capital": 10000000.0,
   "sections": [{"id": "bandeau", "titre": "Bandeau", "statut": "ok", "ok": true, "message": null,
                 "code": null, "duree_s": 10.89}, "…"],
   "sections_en_echec": [], "historique_complet": true, "avertissement_historique": null,
   "notes_connues_au": "2026-11-23T00:17:40.932066+00:00", "avertissement_panel": null, "bandeau": "…"}
  ```

- `update` : `simulation`, `debut`, `fin`, `jours_cherches`, `bulletins_telecharges`, `requetes`, `quota`,
  `quota_restant`, `arret`, `raison_arret` (`bloque`, `robots`, `serveur`, `quota`, `politique`, `erreur`),
  `motif_arret`, `panel_reconstruit`, `panel`, `jours_restants`, `marqueurs` {`definitifs`, `a_reessayer`,
  `bulletins_en_cache`}, `dossier`. Arrêt au quota : code 1 (relancer) ; refus du site ou réseau : code 5.
  Par défaut, **tout jour manquant depuis le 02/01/2017** est cherché, du plus récent au plus ancien :
  une collecte interrompue reprend sans `--from`. `--sans-panel` : jamais de reconstruction du panel ;
  `--workers N` : processus du panel. Avec `--simulation` : `jours_a_chercher`, `jours`, `quota`.
  `--delai S` : nombre **fini** de 10 à 3600 (sinon code 2, aucune requête). `--rouvrir AAAA-MM-JJ[..AAAA-MM-JJ]` :
  décision explicite, retire les marqueurs « sans bulletin » (même définitifs, anciens marqueurs vides
  compris) de la période, cherchée de nouveau dans ce lancement (clé `marqueurs_rouverts` ; avec
  `--simulation`, rien n'est retiré, mais les jours rouverts sont comptés dans `jours_a_chercher` et listés dans
  `jours`, comme dans un vrai lancement).
- `panel` : `panel` {`fichiers`, `analyses`, `en_cache`, `erreurs`, `seances`, `premiere_seance`,
  `derniere_seance`, `symboles`, `lignes_actions`, `seances_sans_boc`, `trous`, `dossier`}. `--workers`
  vaut par défaut `min(2, processeurs disponibles)` (quota du cgroup compris).
- `notes research` : `hors_ligne`, `simulation`, `recherche` {`notes_ajoutees`, `notes_recrites`,
  `requetes`, `quota`, `quota_restant`, `arret`, `raison_arret`, `motif_arret`, `blocage`, `elements_lus`,
  `nouvelles_notes`, `doublons`, `ecartes`, `incidents`, `listes`, `non_resolus`, `reconstitution`},
  `notes` [{`note_id`, `publiee_le`, `cibles`, `titre`}], `lecture_documents` (bilan de la lecture des PDF),
  `lignes_lecture`. Refus du site : code 5 (le bilan est dans l'objet d'erreur). Quota atteint : code 0,
  `raison_arret: "quota"`, `motif_arret` rempli, et **aucune** lecture de documents (aucune requête au-delà
  du quota). Un document trop lent pour le lien (délai total dépassé, qui croît avec la taille annoncée : 300 s
  plus 1 s par 8 Ko, 30 min au plus) est mis de côté sept jours (`status: "a_reessayer"`) ; la lecture passe
  au suivant.
- `notes lire` : `lecture_documents` {`n_candidates`, `n_read`, `n_enriched`, `n_scanned`, `n_failed`,
  `n_skipped`, `n_written`, `n_requests`, `stopped`, `details`…}, `lignes`. Arrêt au quota : 1 ; refus : 5.

### A.10 Mémoire (limite de 3 Go)

Mesures du 23/11/2026 (§ A.9), relevées dans `/proc` toutes les 50 ms, processus et enfants, sous
`RLIMIT_AS` à 3 Go : **toutes les commandes passent**. Pic de mémoire virtuelle (VmPeak) et résidente
(VmHWM), en Mo :

| Commande | VmPeak | VmHWM |
|---|---|---|
| `etat` | 402 | 233 |
| `notes add` | 391 | 194 |
| `notes list` | 340 | 163 |
| `indices` | 454 | 296 |
| `indices dossier` | 468 | 306 |
| `explain` | 699 | 368 |
| `recommend` | 800 | 447 |
| `report` | 789 | 457 |
| `update --simulation` | 342 | 162 |
| `panel` (rien de nouveau) | 475 | 314 |
| `panel --force` | 803 (parent) ; 337 par enfant (4 enfants) | 625 ; 151 par enfant |
| `notes research --hors-ligne --pdf 0` | 428 | 233 |
| `notes lire --hors-ligne` | 386 | 187 |
| `plan` (export, contrôle de `a58b4c8`) | 700 | 371 |
| `plan --enregistrer` (export) | 698 | — |
| `suivi bulletin` (export) | 698 | 326 |
| `suivi maj` (export) | 694 | 322 |
| `suivi verifier` (export) | 366 | 131 |
| `suivi demarrer`, `suivi saisir` (export) | 338 | — |

Avant les réglages du mode embarqué (un fil, pool « system » d'Arrow, deux arènes de malloc), les pics
étaient de 1,9 Go (`etat`) à 2,3 Go (`recommend`, `report`), et 1,5 Go par enfant du panel : trop près des
2,5 Go par défaut d'Odoo. La limite est **par processus** : chaque enfant du panel a la sienne.

**Limite trop basse.** Sous **1 Go** (`BRVM_ALPHA_MEMOIRE_MIN`, en Mo), la commande sort aussitôt en **6**
(objet JSON « memoire »), sans rien charger : en dessous, le chargement de numpy, OpenBLAS ou Arrow échouait
sans objet JSON (codes 1, 127, −11) ou se figeait sans répondre à `TERM`. Au-dessus, une `MemoryError` n'est
jamais avalée : essayé sur les données réelles avec le contrôle désactivé, `recommend` sous 650, 550 et 450 Mo
sort en 6 à chaque fois (avant : code 0 avec un ordre de bataille dégradé, ou −11). Hors mode embarqué, la
réservation est de 2,3 Go : une limite de 1 à 3 Go peut encore figer OpenBLAS ; y préférer 3 Go ou le mode
embarqué. Un processus de **pdftotext** (et `pdfinfo`, `pdffonts`, `pdfimages`) a sa propre limite : 512 Mo de
mémoire virtuelle, 32 Mo de sortie (fichier temporaire, jamais en mémoire), 60 s pour un bulletin ; il meurt avec
le moteur (§ A.7).

### A.11 Historique incomplet

`etat` dit `historique_complet: false` tant qu'il reste un jour ouvré sans bulletin lisible depuis le
02/01/2017 (jours récents exceptés) ou que le panel ne couvre pas les bulletins ; `pret` est alors faux. Un jour
marqué « introuvable » (404 partout) compte comme connu ; un jour au marqueur **à réessayer** (réponse HTML
d'un site en maintenance, PDF trop gros, extraction ratée, réseau) compte comme **manquant**, avec la date de
la prochaine relance dans `raison`.
Dans ce cas :

- `recommend`, `report`, `indices` et `explain` portent un **avertissement fort** (« HISTORIQUE
  INCOMPLET : … ») et les clés `historique_complet: false` et `avertissement_historique` ; le rapport le
  met en tête, en encadré rouge, et date la fenêtre réelle (« historique disponible seulement du … au … ») ;
- en mode embarqué, `recommend` et `report` **refusent** : code 1, `"erreur": "historique_incomplet"`,
  sauf `--accepter-historique-incomplet` (l'avertissement reste) ;
- hors mode embarqué : avertissement seulement.

Pour compléter : relancer `update` (il reprend seul depuis le 02/01/2017) tant que
`bulletins.jours_a_telecharger_depuis_2017` dépasse 3, puis `panel`.

### A.12 Tâches de nuit (côté Odoo)

Chaque soir de bourse, après la parution du bulletin (22 h 30 UTC par exemple), **l'une après
l'autre**, en travaux détachés, à basse priorité :

1. `update --sans-panel --format json` : le bulletin du jour (1 à 5 requêtes) et, dans la limite du quota
   (200 requêtes, 10 s au moins entre deux), les trous de l'historique. Code 1 au quota : normal tant que
   l'historique n'est pas complet ; code 5 avec `site.bloque` (lu par `etat`) : **ne plus rien envoyer** ;
2. `panel --format json` (6 s s'il n'y a qu'un bulletin de plus) ;
   2 bis. `suivi maj --format json` (suivi sur papier, § A.17 ; calcul local, aucune requête, 4 s environ) : un
   échec n'arrête pas la suite (il est consigné, et le code de la tâche le dit) ;
3. si le site n'a pas refusé : `notes research --pdf 20 --format json` (150 requêtes au plus, 25 minutes
   au plus, puis 20 documents) ;
4. `etat --format json`, puis, seulement si `pret` est vrai : `report --capital … --format json`.

Ne jamais lancer deux de ces commandes à la fois : les verrous du moteur refusent en code 4 deux
**écritures** concurrentes (deux `update`, deux `panel`, deux `notes research`), mais pas une lecture
pendant une écriture (un `recommend` lancé pendant le `panel` de nuit peut lire deux versions du panel) :
Odoo enchaîne ses travaux et évite les appels de l'utilisateur pendant `panel`. Délais conseillés : 2 h pour `update`, 10 min pour `panel`, 1 h pour `notes
research`, 5 min pour `report`. `deploiement/quotidien.sh` fait la même chose pour une installation hors
Odoo (il n'est pas exporté).

### A.13 Collecte initiale

Depuis zéro : 2 580 jours ouvrés du 02/01/2017 au 20/11/2026 (2 334 bulletins, 246 jours sans
bulletin), soit près de **4 000 requêtes** (jusqu'à 5 adresses essayées par jour), 10 s au moins entre deux :
environ **11 heures** de téléchargement, en une **vingtaine** de lancements de `update --sans-panel
--max-requetes 200` (33 minutes chacun au plus). Odoo les enchaîne : relancer tant que
`bulletins.jours_a_telecharger_depuis_2017` baisse et dépasse 3 ; s'arrêter au premier code 5 avec
`site.bloque` (ne pas insister : le blocage ne se lève qu'avec l'accord du site) ou si un lancement
n'avance plus. Puis `panel` (1 minute), `notes research --pdf 20`, et `report` quand `pret` est vrai.

**Reprise** : la collecte peut être arrêtée à tout moment (TERM, panne) et relancée : les bulletins déjà
écrits restent (écriture atomique), `update` cherche de lui-même tout jour manquant depuis 2017, du plus
récent au plus ancien. Un jour sans bulletin (404 partout) n'est marqué définitif qu'après trois passages
espacés d'un jour **et** d'au moins 20 heures (deux passages à dix minutes d'écart de part et d'autre de minuit
comptent pour un) ; une réponse illisible laisse un marqueur à réessayer. Les anciens marqueurs vides
(avant le 22/11/2026, 246 sur l'historique réel) restent définitifs : `update --rouvrir AAAA-MM-JJ..AAAA-MM-JJ`
les retire, sur décision explicite. `deploiement/collecte-initiale.sh`
fait la même boucle hors Odoo.

### A.14 Ce qui reste non vérifié

- **aucun essai dans un vrai Odoo** : ni le lanceur, ni `limit_memory_hard`, ni `limit_time_cpu`, ni le maître
  Odoo comme processus 1, ni les travaux détachés ; la commande a été lancée ici comme Odoo le fera (même
  interpréteur autonome, `-I -B`, `env -i`, `RLIMIT_AS` 3 Go, nouveau groupe, sorties dans des fichiers), et la
  limite de temps de calcul d'un travailleur a été jouée par `RLIMIT_CPU` (5 et 20 s) ; la façon dont Odoo 17
  pose cette limite est tirée de son code, pas d'un essai ;
- l'image `odoo:17.0` elle-même (Ubuntu jammy, glibc 2.35) : l'interpréteur et les roues manylinux_2_28 y
  sont compatibles sur le papier, mais n'y ont pas tourné ; le poppler de jammy (22.02) n'est pas celui de la
  machine de développement (24.02) : la mise en page du texte des nouveaux bulletins peut différer ;
- aucun téléchargement réel depuis www.brvm.org (aucune requête vers l'extérieur n'était permise) : les
  essais réseau ont tourné contre des serveurs locaux et des doublures ;
- la reprise d'une collecte de 11 heures n'a été essayée que par morceaux (doublures, quota, arrêt) ;
- les durées viennent d'une machine à 4 processeurs, pas du serveur ;
- les blocages ne sont gardés que dans `politeness.json` (pas de copie à part en ajout seul) : s'il devient
  illisible, plus rien n'est envoyé (code 8) jusqu'à sa réparation à la main ; le cache HTTP n'a ni plafond
  de taille ni âge maximal (seuls les PDF en double sont retirés) ;
- `etat` ne cite pas, dans `raison`, les séances que le panel sait manquantes sous un ancien marqueur vide
  (129 sur l'historique réel) : `update --rouvrir` permet de les relancer sur décision ;
- **limites de la politesse entre sessions** (§ A.15, P6) : le verrou d'envoi `politeness.envoi.<site>.lock` est un
  `flock` local, qui ne vaut que sur **une seule machine** : un dossier de données partagé entre deux machines
  (disque réseau, NFS) n'est pas protégé, et ne doit pas servir à deux moteurs à la fois ; si
  `politeness.json` lui-même ne s'écrit pas (disque plein, dossier du cache en lecture seule), **rien n'est envoyé**
  (code 8, depuis le contrôle de `a58b4c8` ; avant : mode dégradé, seul le délai propre à chaque session était tenu,
  et deux sessions partaient sans délai, voire ensemble) ; une session tuée pendant une
  requête (`KILL`) laisse sa marque « envoi en cours », et la suivante attend alors un délai entier **plus 10 s** à
  partir de la prise du verrou : l'instant exact de la coupure n'est pas connu ; le délai est compté depuis la
  coupure faite par le moteur (connexion fermée, puis fin notée), mais le site ne voit la coupure qu'à sa deuxième
  écriture sur la connexion fermée : 0,12 à 0,16 s plus tard avec un faux site qui écrit toutes les 0,1 s, 1 à 2 s
  avec un faux site qui écrit une fois par seconde, 6 s avec un faux site qui écrit toutes les 3 s. D'où la **marge
  de coupure** de 10 s (un délai entier, § A.15) : une requête qui ne s'est pas terminée normalement compte comme
  finie 10 s après sa coupure ; un délai de lecture dépassé (site muet), 50 s après. Historique : la marge de 2 s
  (après `d99bbbc`) faisait partir la suivante 12,02 à 12,03 s après le signal, mais ne laissait que 0,02 s de réserve
  avec un site qui écrit une fois par seconde ; un site qui écrit toutes les 3 s ne voyait que 6,0 à 7,5 s, et après
  un délai de lecture dépassé (site muet 75 s) la requête suivante chevauchait de 2,9 s la réponse encore servie
  (contrôle de `a58b4c8`). Mesuré le 23/11/2026 avec la marge de coupure de 10 s (espace réseau privé, faux
  www.brvm.org en TLS de recette, vrais processus, CPython 3.13) : la requête suivante part 20,00 à 20,04 s après le
  signal (TERM, Ctrl+C, `KILL`, et `update` arrêté par TERM : 20,00 s), et le site voit 18,02 à 18,59 s (site qui
  écrit une fois par seconde), 14,03 à 15,51 s (toutes les 3 s), entre la coupure qu'il constate et la requête
  suivante ; aucun chevauchement. Site muet 75 s, délai de lecture de 60 s (essai fait avec une marge de coupure de
  5 s ; la marge d'un délai dépassé, 50 s, ne dépend pas d'elle) : la requête suivante arrive au site 45 s après la
  fin de la réponse qu'il servait (avant : chevauchement de 2,9 s). Fin normale : 10,00 à 10,03 s, inchangée ; le site voit au moins 10,01 s. Un site qui écrit moins d'une
  fois toutes les 5 s, ou un mandataire, réduirait l'écart : non vérifié avec le vrai site ; un `Crawl-delay` supérieur à 10 s n'est pas transmis d'une session
  à l'autre (sans effet aujourd'hui : brvm.org annonce 10 s, qui est aussi le plancher).

### A.15 Changements visibles hors mode embarqué

Chaque point avec le constat ou la demande qui l'a amené. Les sorties chiffrées (ordre de bataille, panel,
distribution) sont inchangées.

- `update` sans `--from` cherche désormais **tout jour manquant depuis le 02/01/2017** (avant : à partir
  du lendemain du dernier fichier local, ce qui laissait des trous jamais comblés) ; `--delai` : nombre fini
  de 10 à 3600 (avant : `nan` supprimait toute attente, une valeur sous 10 était relevée à 10 sans le dire) ;
  nouvelle option `--rouvrir` ;
- codes de sortie de la table du § A.7 (avant : 0, 1, 2) ; un doublon de `notes add` sort en 0
  (`cree: false`) au lieu de 2 (choix du contrat de la ligne de commande : rien n'est écrit, ce n'est pas une
  erreur) ; **le code 2 est réservé aux saisies** : une `ValueError` ou une `KeyError` venue d'une bibliothèque
  sort en 7, un panel abîmé en 1 (avant : 2, « saisie invalide ») ; `recommend --couts` n'accepte que
  `optimistic`, `central`, `stress`, `severe` (alias français gardés) ;
- **journal des notes présent mais illisible** (dossier à sa place, droits) : `recommend`, `report`,
  `indices`, `explain`, `notes list` et `notes add` sortent en 1 (avant : code 0 **sans aucune note**, vetos et
  achats bloqués ignorés ; ou 7) ; un journal absent reste sans effet ;
- **`MemoryError` jamais avalée** (avant : un `except Exception` en faisait un résultat dégradé en code 0) ;
  limite de mémoire virtuelle sous 1 Go : code 6 au démarrage ;
- `notes add` refuse une note dont aucune cible n'est reconnue, ou une cible vide (code 2 ; avant : note
  enregistrée sans effet, sans avertissement) ; nouvelle clé `note_id_saisie` ;
- nouvelles options `notes add --titre-fichier` et `notes archive --motif-fichier` (demande de l'intégrateur Odoo,
  23/11/2026) : titre ou motif lus dans un fichier UTF-8 de 8 Kio au plus, bords retirés, vide refusé, lien
  symbolique et dossier refusés, exclusives de `--titre` et `--motif` (règles au § A.9). Rien ne change pour
  `--titre` et `--motif`, sauf l'aide (`--titre` y annonce sa borne de 500 caractères) ;
- `--format json` : objet `{"ok": …}` toujours, erreurs comprises (échec au démarrage et `--help` compris) ;
  nouvelles options `--format` pour `update`, `panel`, `report`, `notes archive`, `notes research`,
  `notes lire` ; `update --workers` ; une sortie fermée par le lecteur (`| head`) donne 1 en JSON (avant : 0) ;
- `etat` : `pret` exige maintenant un historique complet **et** un journal des notes lisible ;
  `bulletins.premier_jour_cherche` vaut `2017-01-02` ; nouvelles clés `raison`, `historique_complet`,
  `extracteur_pdf`, `limite_memoire`, `embarque`, `avertissements`, `panel.{premiere_seance, lisible, erreur}`,
  `bulletins.{premier, sans_bulletin_definitif, a_reessayer, sans_fichier, sans_bulletin_lisible,
  prochaine_relance, jours_manquants, historique_complet}`, `notes.{lisible, erreur, lignes_illisibles}`,
  `donnees.inscriptible`, `rapport.inscriptible` (relecture de l'état « prêt » strict) ;
- `explain --format json` : la clé `banner` devient `bandeau` ; nouvelles clés `decomposition` et `notes` ;
- `report` sort avec un code non nul si la section « ordre » échoue (avant : 0) ; `--sortie` vers un dossier :
  code 2 (avant : 7) ;
- avertissement « HISTORIQUE INCOMPLET » sur `recommend`, `report`, `indices`, `explain` ;
- `panel` : `--workers` vaut par défaut `min(2, processeurs)` (avant : `os.cpu_count()`), un fil BLAS par
  processus de travail, construction à côté puis bascule ; les processus de travail meurent avec le processus
  principal ;
- marqueurs `.missing` en JSON : définitifs seulement après 3 passages espacés d'un jour et de 20 heures (un
  jour férié coûte donc 15 requêtes au lieu de 5) ; nouveaux fichiers `boc_*.meta.json` ;
- fichiers de verrou qui restent dans les données (`flock`, jamais supprimés) : `.panel.construction.lock`,
  `.panel.lecture.lock`, `boc_text/.telechargement.lock`, `notes/.recherche.lock`, `notes/notes.jsonl.lock`,
  `notes/cache/politeness.json.lock`, `notes/cache/politeness.envoi.<site>.lock` ; **ne jamais faire tourner deux versions du moteur sur le même dossier de
  données** : l'ancien code (avant le 22/11/2026) prend un `notes.jsonl.lock` laissé en place pour un verrou
  tenu (attente de 10 s, puis échec), et les deux protocoles ne s'excluent pas. Pour revenir à une ancienne
  version : arrêter toute commande, puis supprimer les `*.lock` des données ;
- `validate` ou `backtest` sans statsmodels : code 8 au lieu du repli CSS silencieux (choix des couches
  internes : un résultat de validation ne doit pas changer de méthode sans le dire) ;
- écritures atomiques du rapport, de `recommend --sortie` et de `notes export --sortie` ; un **lien
  symbolique** est suivi (sa cible est remplacée, le lien reste) et un périphérique ou un tube nommé
  (`/dev/null`, `/dev/stdout`) est écrit directement (avant le 23/11/2026 : le lien était remplacé par un
  fichier ordinaire, `/dev/stdout` refusé hors root) ; chemins relatifs des options rendus absolus depuis le
  dossier courant dès le départ ;
- le signal TERM arrête une commande proprement (code 130), dès le démarrage ;
- **temps de calcul** : une limite `RLIMIT_CPU` qui laisse moins de 900 s de marge au démarrage donne 8, sans rien
  charger (`BRVM_ALPHA_CPU_MIN=0` désactive le contrôle ; une valeur négative ou illisible prend le défaut) ; `SIGXCPU` en cours de commande donne 8 avec un objet JSON
  (avant : −24, sans objet) ; un processus de travail du panel mort prend le code de sa cause : `SIGXCPU` 8,
  `SIGKILL` sous une limite de mémoire 6, `SIGSEGV` ou autre signal 7 (avant : 6 dès qu'une limite de mémoire était
  posée) ;
- outils de poppler liés au moteur (`PR_SET_PDEATHSIG`) : ils meurent avec lui ; un outil fini est récolté aussitôt
  (`pidfd_open`), au lieu d'attendre jusqu'à 50 ms ;
- `panel` sans aucun bulletin : code 1, « aucun bulletin dans … : lancer d'abord update » (avant : 7, « KeyError :
  file ») ;
- `--format json` : TERM et `SIGXCPU` reportés pendant l'écriture de l'objet, et sans effet sur le code une fois
  l'objet écrit ; reportés aussi du dernier instant de l'écriture jusqu'à l'objet pour `notes add`, `notes archive`,
  `notes export`, `recommend --sortie` et `report` (§ A.8) ;
- `update --simulation --rouvrir` compte les jours rouverts dans `jours_a_chercher` (avant : 1 jour pour 35
  marqueurs rouverts) ;
- `recommend` sur un tout petit panel (7 séances) : code 0, avec l'évaluation des indices « n.d. » (avant : 7,
  `TypeError`) ;
- réseau : délai, réservation et blocage comptés **par site** (`www.brvm.org` et `brvm.org` partagent une
  même clé) ; un nom résolu en adresse interdite est signalé comme refus de politique (code 5, `politique`),
  plus comme « robots.txt interdit », et n'est plus compté comme requête ; adresse réellement jointe contrôlée
  après la connexion ; délai total tenu jusqu'aux en-têtes ; `politeness.json` illisible : aucune requête,
  code 8, fichier non réécrit (avant : le blocage 403 était oublié et le fichier réécrit sans lui) ;
  `fetch_log.jsonl` tourne au-delà de 10 Mo ; les PDF en double du cache HTTP sont retirés ; `live` sort en 5
  pour un site bloqué ou un réseau en défaut (avant : 1) ; une page HTML servie avec un type PDF est lue comme
  une page (avant : note vide) ;
- **politesse entre sessions** (P6, revu le 23/11/2026) : la liste blanche et l'adresse obtenue par résolution DNS
  sont contrôlées **avant** de réserver un créneau ou d'attendre : une requête refusée à ce stade ne réserve rien
  dans `politeness.json`, n'attend pas et sort aussitôt en 5 `politique` (avant : 10 s d'attente, puis le refus) ;
  un refus constaté seulement à la connexion (adresse réellement jointe) **garde** sa réservation (prudent : une
  attente de plus au lancement suivant ; une réservation n'est plus jamais retirée ni remplacée par une date plus
  ancienne) ; la fin de chaque vraie requête est toujours notée (`fin`, `fin_session`), même si une autre session a
  réservé plus tard pendant cette requête ; une seule requête à la fois vers le site, toutes sessions confondues
  (verrou `notes/cache/politeness.envoi.www.brvm.org.lock`, tenu pendant la requête ; une session dont le créneau
  arrive pendant la requête d'une autre attend sa fin, puis 10 s) : aucune requête ne part moins de 10 s après la
  **fin** d'une autre. Avant : trois sessions simultanées (X envoie une requête de 6 s ; Y réserve le créneau
  suivant puis est refusée ; Z arrive ensuite) faisaient partir Z 4,0 s après la fin de X, et une vraie requête de
  Y partait pendant celle de X si X durait plus de 10 s. Le journal `fetch_log.jsonl` note ces attentes
  (`"event": "attente"`) ;
- **requête interrompue** (contrôle du commit `1a1fd28`) : la fin d'une requête est notée à **toute** sortie du bloc
  d'envoi, verrou d'envoi tenu : fin normale, erreur, TERM du lanceur, Ctrl+C, `SIGXCPU`, `MemoryError` ; et, juste
  avant l'envoi, la session écrit dans `politeness.json` une marque « envoi en cours » (clé `envoi` : `debut`,
  `session`), retirée avec la fin. Une session qui prend le verrou d'envoi et trouve la marque d'une autre session
  (processus tué par `KILL` pendant sa requête, panne) attend un délai **entier** avant de partir. Avant : une
  session interrompue pendant sa requête ne notait pas sa fin, et la session qui attendait le verrou partait
  aussitôt, 0,02 à 0,07 s après le signal, pendant que le site servait encore la réponse coupée. Mesuré dans
  l'espace réseau privé (faux www.brvm.org en TLS de recette), sur deux vrais processus : la suivante part 10,0 à
  10,1 s après TERM, Ctrl+C ou `KILL` (voir § A.14 pour l'écart vu par le site) ;
- **marge de coupure** (demande de l'intégrateur, 23/11/2026, après `d99bbbc` ; portée de 2 s à 10 s par le
  contrôle de `a58b4c8`) : une requête qui ne s'est **pas terminée normalement** (ni réponse lue en entier, ni
  erreur HTTP reçue : TERM du lanceur, Ctrl+C, `SIGXCPU`, `MemoryError`, erreur du transport, connexion impossible)
  compte comme finie **10 s après sa coupure** : `politeness.json` note l'instant réel dans `fin` et la clé
  `fin_coupee` (retirée par la fin normale suivante), et toute session, la même comprise (nouvel essai après une
  erreur), part au plus tôt 20 s après la coupure ; une marque « envoi en cours » orpheline (`KILL`) fait attendre un
  délai plus 10 s (20 s) depuis la prise du verrou. Un **délai dépassé** (site muet plus longtemps que le délai de
  lecture, ou réponse plus lente que le délai total) compte comme fini le délai de lecture après la coupure, borné à
  50 s (`fin_coupee` porte alors ce nombre de secondes) : la suivante part 60 s après. Une requête terminée
  normalement garde **exactement** 10 s. Une valeur illisible de `fin_coupee` compte comme une coupure ; une fin
  coupée illisible ou datée dans le futur coûte un délai plus la marge, jamais plus. Raison : le site ne voit la
  coupure qu'à sa deuxième écriture sur la connexion fermée (jusqu'à 6 s plus tard pour un site qui écrit toutes les
  3 s), et un site muet ne la voit qu'en reprenant ses écritures. Mesuré (§ A.14) : la suivante part 20,00 à 20,04 s
  après TERM, Ctrl+C ou `KILL`, et le site voit au moins 14,03 s ; fin normale : 10,00 à 10,03 s. Rien ne change
  dans les codes de sortie ni dans le lanceur ;
- un blocage 403/429 noté par une autre session pendant l'attente est relu **dès la prise du verrou d'envoi** : la
  session qui attendait s'arrête aussitôt, sans attendre encore jusqu'à un délai (avant : jusqu'à 10 s de plus, sans
  rien envoyer) ;
- verrou d'envoi impossible à prendre (un dossier à sa place, fichier d'un autre utilisateur) ou marque impossible
  à écrire, alors que `politeness.json` s'écrit : **rien n'est envoyé**, code 8 (`configuration`), événement
  `politesse_non_garantie` dans `fetch_log.jsonl` (avant : la requête partait quand même, deux requêtes pouvaient se
  chevaucher, seul un avertissement sur la sortie d'erreur le disait) ;
- une date illisible dans `politeness.json` (`"NaT"`, `"nan"`, texte, nombre, pour `fin` comme pour `last`) coûte un
  délai d'attente (avant : `fin` à `"NaT"` ou `"nan"` faisait sortir toute commande réseau en 7, « cannot convert
  float NaN to integer » ; une réservation `last` illisible était ignorée, sans aucune attente). Depuis le contrôle
  de `a58b4c8`, la **présence** de la clé compte, quelle que soit sa valeur : `fin`, `last` ou `envoi` posés à la main
  à `""`, `0`, `false` ou `{}` coûtent un délai (plus la marge pour `envoi`), et `fin_coupee` à `0` compte comme une
  coupure (avant : ces valeurs « fausses » pour Python étaient ignorées, sans aucune attente) ;
- `politeness.json` (ou son verrou) impossible à écrire : disque plein, cache en lecture seule, droits : **rien n'est
  envoyé**, code 8, avant toute requête (contrôle de `a58b4c8` ; avant : mode dégradé, la requête partait avec le
  seul délai de la session, et deux sessions partaient à 0,01 s d'écart, ou en même temps). Disque plein, quota ou
  volume en lecture seule donnent 8 même quand l'erreur ne porte pas de nom de fichier (avant : `live` sur un disque
  plein sortait en 7, « erreur interne : OSError ») ;
- repli pdfplumber lancé avec `python -I`, depuis le dossier temporaire et avec un environnement réduit ;
- `python -m brvm_alpha.data.boc_download` passe par le client poli commun (quota de 200 requêtes, blocage
  partagé) ;
- scripts de `deploiement/` : verrou `flock` (code 4 si une autre tâche tourne, jamais 3), chemins
  relatifs refusés (code 2), TERM transmis à la commande en cours, `ionice -c 2 -n 7`, refus du site
  seulement si `etat` le dit (code 5), pas de rapport sur un historique incomplet ; l'installateur refuse
  tout fichier de plus dans le dossier des roues.

### A.16 `serve` et le relais : non utilisés en production

En production, **aucun serveur web du moteur** ne tourne : ni `serve` permanent (`deploiement/service.sh`),
ni `serve` lancé à la demande, ni relais Odoo. Le moteur ne fait que répondre à des appels en ligne de
commande. La partie B décrit ce mode pour mémoire. Si un jour il revenait, préalables **non faits** :

- écoute sur un **socket Unix en 0600** (ou un secret partagé exigé dans un en-tête à chaque requête), au
  lieu d'un port TCP joignable par tout processus local (aperçu de liens d'Odoo compris) ;
- **arrêt sur inactivité** et sur `SIGTERM` (un seul exemplaire, pas de concurrence entre travailleurs
  Odoo pour le port) ;
- **délai**, **annulation** et **regroupement** des requêtes lourdes (aujourd'hui calculées en synchrone,
  sans délai ni annulation, sous un verrou global) ;
- `handle_error` silencieux quand le navigateur ou le relais a fermé la socket (aujourd'hui une trace
  sur la sortie d'erreur) ;
- et les points de la partie B : origine exigée sur tout POST avec `--origine-relais`, chemins retirés de
  `/etat.json`, dernier calcul du portefeuille visible de tout le groupe.

### A.17 Rendement net et pertes : commandes `plan` et `suivi`

Le module « Rendement net et pertes » (`docs/RENDEMENT_NET.md`) ajoute deux commandes et des options à
`recommend` et `report`. Elles suivent le même contrat (codes du § A.7, un objet JSON du § A.8, écritures
atomiques, mode embarqué). Étude seulement : aucune ne passe d'ordre, aucune ne promet un gain. Le suivi sur
papier (sans argent réel) commence le mardi 01/12/2026.

Durées mesurées le 23/11/2026 sur la machine de développement (4 processeurs) : CPython 3.11 (environnement
virtuel de test, code du dépôt, pas l'export), mode embarqué (`BRVM_ALPHA_EMBARQUE=1`, `env -i`, `-B`), copie
des données réelles (2 334 bulletins, 861 notes). Toutes les lignes finissent par `--format json`. Les chemins
écrits s'entendent dans `BRVM_ALPHA_DONNEES` (`<rapports>` : `BRVM_ALPHA_RAPPORTS`).

Mesures sur l'**export** (contrôle de `a58b4c8`, 23/11/2026) : CPython 3.11.15 autonome, code et interpréteur en
lecture seule, `RLIMIT_AS` 3 Go, lanceur du § A.6 sous un faux travailleur Odoo ; durée, et pic de mémoire
virtuelle (VmPeak) : `plan` 12,9 s (700 Mo) ; `plan --enregistrer` 16,6 s (698 Mo) ; `plan grille` 1,9 s sous
`strace` (336 Mo) ; `suivi bulletin` 4,5 s (698 Mo) ; `suivi maj` 3,7 s (694 Mo) ; `suivi verifier` 0,7 s
(366 Mo) ; `suivi demarrer` et `suivi saisir` 0,55 s (338 Mo) ; `recommend` 17,5 s (800 Mo) ; `report` 19,9 s
(799 Mo). Aucun fichier n'est écrit hors de `<D>`, `<R>` et `<T>` ; aucun fichier n'est **laissé** dans `TMPDIR`
(`notes add`, `notes archive` et `report` y créent puis retirent un fichier d'essai : sonde de `tempfile`).

| Commande | Durée | Nature | Écrit | Codes |
|---|---|---|---|---|
| `plan [--capital K] [--grille ma_sgi\|central\|FICHIER] [--taux-reserve T]` | 10,6 s | court | `profil/plan_cache.json` | 0 ; 1 panel absent ou historique incomplet ; 2 saisie (taux de la réserve hors de 0 à 15 %, perte acceptée au-delà du capital, `--grille` vide) |
| `plan --perte-toleree 1000000` | 17,8 s | court | idem | idem |
| `plan … --enregistrer [--besoin-dans MOIS]` | 11,6 s | court | idem et `profil/plan.json` | idem |
| `plan grille` (lecture) ; `plan grille --comparer` (lignes du cache) | 0,4 s | court | rien | 0 |
| `plan grille --courtage T --taxe T --par-ligne M --forfait M [--source TEXTE] [--statut ecrit\|avis]` | 0,4 s | court | `profil/grille_sgi.yaml` | 0 ; 2 valeur hors plage, statut écrit sans source |
| `plan questions` | 0,4 s | court | rien | 0 |
| `suivi maj` | 3,2 s (semaine 0) | long (tâche de nuit) | `suivi/<nom>/` (ajout seul) | 0 ; 1 panel absent ; code du premier portefeuille en échec (4 : journal tenu par une autre écriture) |
| `suivi bulletin [--nom NOM]` | 3,6 s | court | rien | 0 |
| `suivi verifier` | 0,4 s | court | rien | 0 ; 1 chaîne rompue |
| `suivi demarrer --nom MOI [--capital K] [--mode papier\|reel]` | 0,4 s | court | `suivi/MOI/carnet.jsonl` | 0 ; 2 déjà démarré ; 4 journal tenu |
| `suivi saisir --nom MOI --apport M \| --retrait M \| --fichier avis.csv [--confirmer-grille]` | 0,4 s | court | carnet ; grille si l'avis concorde, ou confirmée | 0 ; 1 carnet absent ; 2 saisie, doublon, retrait plus grand que les liquidités du carnet ; 4 journal tenu |
| `suivi revue --nom MOI --alerte ID --decision garder\|ne-plus-acheter\|reduire --texte "…"` | 0,4 s | court | carnet | 0 ; 1 carnet absent ; 2 code d'alerte inconnu (ID : W1 à W9, perte, fuites, donnees, ou le symbole d'une ligne), texte vide ; 4 journal tenu |
| `suivi exporter --sortie DOSSIER [--avec-moi]` | 0,4 s | court | `<rapports>/DOSSIER` (d'un bloc) | 0 ; 1 rien à copier (MOI seul, sans `--avec-moi`), aucun dossier créé ; 2 dossier non vide, `--sortie` vide, lien symbolique, dossier des rapports, temporaire ou des données lui-même |
| `suivi declarer …` | 0,4 s | — | rien | **2 toujours** sur l'installation |
| `recommend --capital 10000000 --perte-toleree 1000000` | 21,6 s | court | rien, ou `--sortie` | 0 ; 2 saisie, refusée avant le calcul (`--arrondi restes` sur un tarif supposé sans `--forcer`, taux ou perte hors plage) |
| `report --capital 10000000 [--sortie nom.html]` | 16,9 s | long | rapport | 0 |

- **Sans option nouvelle**, `recommend` et `report` rendent les mêmes titres, quantités, prix limites, frais et
  distribution qu'avant ; s'ajoutent la clé `rendement_net` (environ 1 s de calcul) et des blocs d'affichage.
  Options : `--grille ma_sgi|central|FICHIER`, `--perte-toleree MONTANT|P%` (l'ordre rendu est celui du montant
  en actions ; une vérification relance l'ordre complet, 10 fois au plus), `--taux-reserve T` (en %),
  `--sans-rendement` (sans la clé, plus court ; avant `a58b4c8` compris, une clé vide `{}` était écrite) ;
  `recommend` seulement : `--arrondi bas|restes [--forcer]`, `--apport M`, `--completer`, `--reinvestir`,
  `--continuite`, `--suivi NOM`. Taux en pourcentage : des chiffres, une virgule ou un point, un « % » facultatif
  (« 0,5 » = 0,5 %) ; signe, exposant (« 1e-1 ») ou soulignés (« 0_7 ») : code 2. Une grille donnée en fichier
  vide, faite de commentaires ou de plus de 64 Kio : code 2 (avant : tarif par défaut pris sous le nom « Ma
  grille »). Un nom vide (`--suivi ''`, `suivi maj --nom ''`, `suivi bulletin --nom ''`) : code 2, jamais le
  défaut (avant : `suivi maj --nom ''` mettait à jour tous les portefeuilles).
- Saisies simultanées : `plan grille` et `plan --enregistrer` lisent, fusionnent et écrivent `profil/grille_sgi.yaml`
  et `profil/plan.json` sous un verrou du profil (`flock` sur le dossier lui-même, aucun fichier ajouté) ; une
  saisie lancée en même temps attend, ou sort en 4, et aucune valeur confirmée en 0 n'est perdue. `suivi demarrer`
  refait son contrôle « déjà démarré » sous le verrou du portefeuille : deux démarrages simultanés n'inscrivent
  jamais deux mandats (le second sort en 2). `suivi maj` écrit chaque séance d'un bloc (mouvements, puis
  `papier.json`) : TERM ou SIGXCPU reçus pendant une séance attendent sa fin ; après un arrêt brutal (KILL, panne),
  la relance reconnaît les mouvements déjà inscrits pour la séance en cours (clé `en_cours` de `papier.json`) et
  n'inscrit que ce qui manque (avant : une division, un dividende ou des frais pouvaient être inscrits deux fois).
- `suivi exporter --sortie` : le dossier des rapports, le dossier temporaire ou celui des données eux-mêmes, et un
  lien symbolique, sont refusés en code 2 (avant : le dossier des rapports était remplacé par la copie, ou code 7
  pour un lien). `suivi revue --texte ''` (ou fait d'espaces) : code 2 ; pour `--alerte SYMBOLE`, seul le format est
  contrôlé (la ligne peut n'être pas détenue : « ne-plus-acheter » vise aussi une ligne proposée par l'ordre).
- `plan` sans `--capital` reprend le capital de `profil/plan.json`, sinon 10 000 000 FCFA ; sans `--grille`,
  la grille enregistrée si elle existe, sinon le tarif supposé « central ». `--tranches` (entrée en plusieurs
  fois) n'est pas disponible : seule la valeur 1 est acceptée (code 2 sinon). `--besoin-dans` est gardé dans le
  plan ; la durée n'est pas encore calculée (`duree.statut` : « non calculé »).
- **Carte « Mon plan » dans Odoo** : lire `profil/plan_cache.json` (clés `plan`, `capital`, `asof`,
  `calcule_utc`, `ordre`, `rendement_net`, `bandeau`), sans relancer le calcul ; le rafraîchir par `plan`
  (travail détaché). Le rapport de nuit ne l'écrit pas. Afficher l'écran `plan` tel quel (montants du capital
  total) : avec `--perte-toleree`, `rendement_net` décrit l'ordre du montant en actions (`contexte.poche` vrai),
  pas le capital total ; l'écran ne se refait jamais depuis `rendement_net`.
- **Taux de la réserve** (`--taux-reserve`, champ « taux » de l'interface) : de 0 à 15 % (`reserve.taux_max` de
  `configs/rendement_net.yaml`) ; au-delà, refus en code 2 (400 dans l'interface), rien n'est écrit. Ce que
  j'accepte de risquer ne dépasse pas le capital total (code 2).
- **Écritures simultanées** : chaque journal du suivi (carnet, semaines, exécution sur papier, déclaration et
  registre) s'écrit sous un verrou de son dossier (`flock` sur le dossier lui-même : aucun fichier ajouté). Une
  commande qui trouve le verrou tenu attend jusqu'à 10 s (`BRVM_ALPHA_ATTENTE_VERROU`), puis sort en **code 4**
  (`verrou_occupe`) sans rien écrire : la relancer plus tard. `suivi maj` tient le verrou d'un portefeuille le
  temps de son exécution sur papier et de ses écritures ; le calcul du moteur du témoin reste hors du verrou.
  Fichiers d'état (`controles.json`, état de l'exécution sur papier, en-têtes des CSV) : écriture atomique ;
  lignes ajoutées : `fsync`.
- **TERM et `SIGXCPU` pendant une écriture** (`profil/plan.json`, `profil/plan_cache.json`, `profil/grille_sgi.yaml`,
  carnet, semaines, déclaration, registre, copie de `suivi exporter`) : ils sont reportés jusqu'à la fin de
  l'écriture, qui n'est jamais coupée (fichier complet et valide ; un mandat n'est jamais écrit sans son apport).
  Ensuite : si l'écriture était la dernière étape (`plan` après son calcul, `plan grille` sans `--comparer`, `suivi
  demarrer`, `saisir`, `revue`, `declarer`, `exporter`, `bulletin --sortie`), la commande rend son vrai résultat
  (0 et son objet), comme `notes add` (§ A.8) ; sinon (`plan --enregistrer` avant le calcul, `plan grille
  --comparer`, `suivi maj` entre deux portefeuilles), elle s'arrête en 130 (8 pour `SIGXCPU`), un seul objet JSON.
  Avant l'écriture (attente d'un verrou, calcul), TERM arrête la commande comme avant, sans rien écrire.
- **Saisies refusées** (code 2, rien n'est écrit) : un retrait plus grand que les liquidités du carnet (un retrait
  égal reste accepté ; l'interface répond 400 avec le même message) ; une revue d'un code d'alerte inconnu (par
  exemple W99 : le message cite les codes connus) ; `--grille` vide ou faite d'espaces (`plan`, `recommend`,
  `report`) ; `suivi exporter --sortie` vide ou faite d'espaces (avant : code 7). Un taux saisi « 0,7 » est
  enregistré 0,007 exactement (avant : 0,006999999999999999 ; montants arrondis inchangés).
- **Ordre du montant en actions** (`--perte-toleree`) : la vérification reprend le mode de l'appel (notes,
  grille, arrondi, continuité), mais ni `--suivi` (mémoire), ni `--apport`, ni `--completer`, ni `--reinvestir`,
  ni la comparaison des variantes ; l'évaluation des indices est celle de l'ordre du capital total (même date,
  mêmes notes). Si cet ordre n'est pas obtenu (aucun montant possible, vérification arrêtée, module en échec),
  l'ordre du capital total est rendu avec, en fin d'avertissements, « ordre du montant en actions non calculé :
  ordre du capital total affiché ».
- **Tâche de nuit** (§ A.12) : après `panel`, lancer `suivi maj --format json`. Un échec n'arrête pas la suite
  (notes, puis rapport). Rien n'est écrit tant que le bulletin du 30/11/2026 (première décision du panier de
  référence) n'est pas dans le panel. Au-delà, chaque mise à jour rejoue le moteur depuis le départ : durée non
  mesurée, à suivre.
- **Déclaration du suivi** : `suivi declarer` ne sert que dans le dépôt de développement ; sur l'installation
  il sort toujours en code 2. Avec `--registre`, la phrase de `--confirmer` et le registre sont contrôlés avant
  toute signature (refus : rien n'est signé) ; des articles identiques à ceux déjà signés sont refusés (code 2),
  quelles que soient les initiales. La déclaration signée est livrée par l'export (`reports/suivi_S2/`, § A.4) ;
  `suivi verifier`, le bulletin et l'ordre la lisent en lecture seule.

**Clés JSON** (exemples réels du 23/11/2026, abrégés ; toutes les sorties portent `ok` et `bandeau`) :

- `plan` : `date`, `capital`, `grille`, `plan_cache`, `plan_enregistre`, `duree`, `historique_complet`,
  `avertissement_historique`, `rendement_net` {`version`, `contexte`, `etude`, `grille`, `bilan`, `risque`,
  `perte`, `reserve`, `liquidites`, `leviers`, `passer_l_ordre`, `alertes`, `avertissements_a_ajouter`, `suivi`,
  `plan` {`lignes` [{`bloc`, `type`, `texte`, `texte_detail`, `montant`, `montant_ecran`, `statut`…}],
  `une_chose`, `feux`}, `duree_s`}. Montants au franc (`montant`) et arrondis pour l'écran (`montant_ecran`) ;
  chaque montant porte son statut (`compté`, `estimé`, `supposé`). Environ 50 ko.

  ```json
  {"ok": true, "date": "2026-11-20", "capital": 10000000.0, "grille": "central",
   "plan_cache": "<données>/profil/plan_cache.json", "plan_enregistre": null, "duree": null,
   "historique_complet": true, "avertissement_historique": null,
   "rendement_net": {"version": 1,
     "contexte": {"capital": 10000000.0, "asof": "2026-11-20", "variante": "REF", "statut": "REJETÉ",
                  "panel_en_retard": null, "n_lignes_cibles": 20},
     "bilan": {"totaux": {"frais_an1": 284714, "annuels": 124126, "reste_an1": 151274, "reste_suivant": 311862,
                          "supposee_fcfa": 311289, "…": "…"}, "…": "…"},
     "reserve": {"montant": 10000000, "taux": null, "valeur_d_un_point": 100000, "deduit_de_la_perte": false,
                 "mention": "taux inconnu : compté à 0 %", "…": "…"},
     "plan": {"lignes": [{"bloc": "courtier", "type": "paragraphe",
                          "texte": "Si vous achetiez tout : environ 290 000 FCFA de frais la 1re année, puis 130 000 par an.",
                          "montant": 284714, "montant_ecran": "290 000 FCFA de frais", "statut": "supposé"}, "…"],
              "une_chose": "envoyez les 8 questions à votre courtier.", "feux": {"suivi_commence": false}},
     "duree_s": 0.56, "…": "…"},
   "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti."}
  ```

- `plan grille` : `grille` {`nom`, `investisseur`, `pays_residence`, `statut_global`, `champs` {`courtage`,
  `taxe_courtage`, `garde`, `tenue_par_ligne`, `forfait_compte`, … : {`valeur`, `statut`, `source`, `date`}}},
  `enregistree`, `chemin`, `avertissements`, `comparaison` (avec `--comparer` : `capital`, `capital_ordre`,
  `source`, `lignes` [{`cle`, `nom`, `statut`, `frais_achat`, `frais_annuels`, `premiere_annee`,
  `ecart_premiere_annee`, `sens_ecart`, `provision_pire_cas`, `marge`, `mention`}], `phrases`), `questions`.
  `plan questions` : `questions` (8 textes).
- `suivi maj` : `date`, `dossier`, `portefeuilles` [{`nom`, `ok`, `ecrit`, `semaine_0`, `mention`, `ajoutees`,
  `identiques`, `passe_a_change`, `derniere_semaine` ; en échec : `code`, `message`}], `en_echec`.

  ```json
  {"ok": true, "date": "2026-11-23", "dossier": "<données>/suivi",
   "portefeuilles": [{"nom": "REF-S2", "ok": true, "ecrit": false, "semaine_0": true,
     "mention": "semaine 0 : le bulletin du 30/11/2026 (première décision) n'est pas encore dans le panel ; rien n'est écrit",
     "ajoutees": 0, "identiques": 0, "passe_a_change": false, "derniere_semaine": null}],
   "en_echec": [], "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti."}
  ```

- `suivi bulletin` : `nom`, `semaine`, `vendredi`, `lignes` (texte du bulletin, 100 colonnes au plus), `valeurs`
  (ligne du journal), `feux` {`perte`, `fuites`, `donnees` : {`etat`, `affichage`, `phrase`, `conditions`},
  `suivi_commence`}, `a_revoir`, `rendez_vous`, `papier`, `ecart_au_marche`. Aujourd'hui : semaine 0, feux
  « — » (« le suivi n'a pas commencé »).
- `suivi verifier` : `declaration` {`fichier`, `existe`, `n_lignes`, `chaine_ok`, `anomalies`, `mention`},
  `portefeuilles` [{`nom`, `semaines`, `carnet`, `ok`}], `rompues`. Une chaîne rompue : code 1, objet d'erreur
  avec les mêmes clés.
- `suivi demarrer` : `nom`, `carnet`, `mouvements`, `mode`, `capital` ; `suivi saisir` : `nom`, `mouvement`
  (apport, retrait) ou `concorde`, `lignes`, `postes_nouveaux`, `grille_enregistree`, `grille_proposee`
  (avis d'opéré) ; `suivi revue` : `nom`, `mouvement`, `phrase` ; `suivi exporter` : `chemin`, `fichiers`,
  `exclus` (MOI, privé, sans `--avec-moi`).
- `suivi declarer` sur l'installation (exemple réel) :

  ```json
  {"ok": false, "code": 2, "erreur": "saisie_invalide",
   "message": "refusé : La déclaration se signe dans le dépôt de développement, puis se livre par un commit.",
   "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti."}
  ```

---

## Partie B — Moteur à part, interface web derrière un relais (non utilisée en production)

Les sections 1 à 14 décrivent l'installation du moteur **à part**, avec son interface web (`serve`) derrière
un relais Odoo. Ce mode n'est **pas** celui de la production (partie A). Les règles communes (codes de
sortie, verrous `flock`, historique) suivent la partie A.

## 1. En bref

- Le moteur tourne **à part** : son propre interpréteur (Python 3.12), ses propres paquets.
- Il écoute sur **127.0.0.1 seulement**. Il n'a **pas d'authentification**.
- Odoo fait l'authentification. Un contrôleur Odoo **relaie** les requêtes du navigateur vers le
  moteur, sous un sous-chemin, par exemple `/rz_brvm_alpha/ui/`.
- Les données vivent **hors du code**, dans un dossier à part (`BRVM_ALPHA_DONNEES`).
- Sans option nouvelle, le moteur se comporte exactement comme avant.

## 2. Schéma de l'ensemble

```
Navigateur d'un utilisateur du groupe autorisé
   |
   |  https://erp.exemple.com/rz_brvm_alpha/ui/...        (session Odoo)
   v
cloudflared --> nginx --> Odoo 17  (Python d'Odoo : non modifié)
                             |
                             |  module Odoo : menu réservé à un groupe
                             |  contrôleur à authentification Odoo  =  LE RELAIS
                             |
                             |  http://127.0.0.1:8765/rz_brvm_alpha/ui/...
                             |  (requête côté serveur, chemin complet gardé)
                             v
                    Moteur BRVM Alpha  (Python 3.12 à part, compte sans privilège)
                    deploiement/service.sh  ->  python -m brvm_alpha serve
                    écoute 127.0.0.1:8765, préfixe /rz_brvm_alpha/ui
                             |
                             +-- BRVM_ALPHA_DONNEES   boc_text/  panel/  notes/  journaux/
                             +-- BRVM_ALPHA_RAPPORTS  rapport_AAAA-MM-JJ.html

Tâches de fond (même interpréteur, même dossier de données, un seul verrou)
   deploiement/collecte-initiale.sh   une fois, environ 11 heures
   deploiement/quotidien.sh           chaque nuit, priorité basse
             |
             v
   www.brvm.org  (seul site interrogé ; 10 s au moins entre deux requêtes ;
                  arrêt définitif au premier refus HTTP 403 ou 429)
```

## 3. Ce qui a été essayé, et ce qui ne l'a pas été

Essayé sur la machine de développement (Python 3.13, hors ligne) :

- préfixe, origine du relais, cadre de même origine, `/etat.json`, commande `etat`, variables de
  données : tests automatiques (`tests/test_deploiement_*.py`) ;
- un **relais de référence** en Python, qui suit le contrat du § 9, de bout en bout
  (`tests/test_deploiement_ui.py`, classe `ReferenceRelay`) ;
- `service.sh` lancé pour de bon sur un port local, avec préfixe et origine de relais, sur une copie
  du journal des notes : pages, formulaires et rapport servis sous préfixe ;
- un **vrai navigateur** (Chrome sans écran, tout en local) : une page de même origine que le relais
  de référence affiche l'interface dans un cadre, y saisit une note, puis ouvre le tableau de bord et
  son rapport (cadre dans le cadre). Avec `--cadre-meme-origine` tout s'affiche ; sans l'option, le
  navigateur refuse le cadre, comme prévu ;
- `collecte-initiale.sh` : mode `--simulation` avec le vrai moteur, puis déroulé complet sur une
  copie minuscule, **sans réseau** (les téléchargements étaient remplacés par des copies de fichiers,
  `notes research` tournait hors ligne) ;
- syntaxe des scripts (`sh -n`, shell `dash`) et du code sous Python 3.12 (`py_compile`).

**Non essayé** (à faire à l'installation) :

- le moteur derrière un **vrai Odoo** (session, groupe, route sans contrôle CSRF d'Odoo, nginx,
  cloudflared) ;
- la construction de l'image **Docker** (`Dockerfile.moteur`) : aucun démon Docker ni téléchargement
  n'était disponible ;
- l'installation des paquets de `requirements-moteur.txt` sous **Python 3.12** (versions relevées
  sous Python 3.13) ;
- les exemples supervisor, cron et Docker Compose de ce document : ce sont des modèles à adapter ;
- un vrai téléchargement depuis www.brvm.org par ces scripts (aucune requête vers l'extérieur
  n'était permise).

## 4. Installation avec un interpréteur isolé

Odoo garde son Python. Le moteur a le sien.

1. **Python 3.12 à part.** Debian 11 ne le fournit pas en paquet : l'installer dans un dossier à
   soi (compilation ou distribution autonome). Ne pas remplacer le `python3` du système. Ne rien
   installer dans l'environnement d'Odoo.
2. **Environnement isolé et paquets** :

   ```sh
   /chemin/vers/python3.12 -m venv /chemin/venv-brvm
   /chemin/venv-brvm/bin/python -m pip install -r brvm-alpha/deploiement/requirements-moteur.txt
   ```

3. **Facultatif hors mode embarqué** : `pdftotext` (paquet `poppler-utils`) rend la conversion des
   bulletins plus rapide. Sans lui, le moteur se sert de `pdfplumber`. En mode embarqué (partie A),
   `pdftotext` est obligatoire.
4. **Code** : le dossier `brvm-alpha/` du dépôt, tel quel. Il n'y a pas d'installation du paquet :
   les scripts se placent dans ce dossier avant de lancer `python -m brvm_alpha`.
5. **Compte** : un compte sans privilège, autre que `root`. Il doit pouvoir lire le code et écrire
   dans le dossier de données.
6. **Contrôle** :

   ```sh
   cd brvm-alpha
   BRVM_ALPHA_DONNEES=/chemin/donnees-brvm /chemin/venv-brvm/bin/python -m brvm_alpha etat
   ```

   La commande répond toujours (code 0). Avant la première collecte elle dit « Prêt : non ».

Avec Docker : `deploiement/Dockerfile.moteur` fait les étapes 1 à 5 dans une image
(`python:3.12-slim`, compte `brvm`, données dans le volume `/donnees`). Voir § 6.

## 5. Variables

Lues par le moteur (une fois, au démarrage ; une option de la ligne de commande l'emporte) :

| Variable | Rôle | Défaut |
|---|---|---|
| `BRVM_ALPHA_DONNEES` | dossier des données : `boc_text/`, `panel/`, `notes/` (journal et cache) | `data/` dans le code |
| `BRVM_ALPHA_RAPPORTS` | dossier des rapports écrits (`rapport_AAAA-MM-JJ.html`, export des notes) | `reports/` dans le code |
| `BRVM_ALPHA_PREFIXE` | préfixe d'adresse de l'interface (option `serve --prefixe`) | aucun |
| `BRVM_ALPHA_ORIGINES_RELAIS` | origines du relais acceptées pour les formulaires, séparées par des virgules (option `serve --origine-relais`, répétable) | aucune |
| `BRVM_ALPHA_VERSION` | version affichée par `etat` quand le code n'a pas de dossier `.git` (image Docker) | « inconnue » |
| `BRVM_ALPHA_EMBARQUE`, `BRVM_ALPHA_PROXY`, `BRVM_ALPHA_ATTENTE_VERROU` | mode embarqué, mandataire, attente des verrous : voir § A.3 | — |

Lues par les scripts de `deploiement/` (chemins **absolus** seulement : un chemin relatif pour
`BRVM_ALPHA_DONNEES`, `BRVM_ALPHA_RAPPORTS` ou `BRVM_JOURNAL` est refusé, code 2 ; `BRVM_MAX_REQUETES` et
`BRVM_CAPITAL` sont des entiers) :

| Variable | Rôle | Défaut |
|---|---|---|
| `BRVM_PYTHON` | interpréteur du moteur (**obligatoire**) | — |
| `BRVM_CODE` | dossier du code (celui qui contient `brvm_alpha/`) | parent de `deploiement/` |
| `BRVM_JOURNAL` | dossier des journaux et du verrou | `journaux/` dans les données |
| `BRVM_PORT` | port du service sur 127.0.0.1 | 8765 |
| `BRVM_CADRE_MEME_ORIGINE` | `oui` : ajoute `--cadre-meme-origine` au service | non |
| `BRVM_MAX_REQUETES` | requêtes au plus par lancement de `update` (première collecte) | 200 |
| `BRVM_CAPITAL` | capital du rapport, en FCFA | 10000000 |

Ce qui ne bouge jamais : `reports/validation_S1/`, `reports/diagnostic_S0/`, `reports/trials.parquet`
et `configs/strategy_v1.yaml` restent lus **dans le code**. Ils sont livrés avec lui.

Les options existantes l'emportent sur les variables : `--panel-dir`, `--boc-dir`, `--racine`
(journal des notes), `--sortie`.

## 6. Service

`deploiement/service.sh` lance l'interface, liée à 127.0.0.1. Il ne prend jamais d'autre adresse.

Modèle pour **supervisor** (préproduction), à adapter :

```ini
[program:brvm-alpha]
command=sh /chemin/brvm-alpha/deploiement/service.sh
environment=BRVM_PYTHON="/chemin/venv-brvm/bin/python",BRVM_ALPHA_DONNEES="/chemin/donnees-brvm",BRVM_ALPHA_RAPPORTS="/chemin/donnees-brvm/rapports",BRVM_ALPHA_PREFIXE="/rz_brvm_alpha/ui",BRVM_ALPHA_ORIGINES_RELAIS="https://preprod.exemple.com"
user=brvm
autostart=true
autorestart=true
stopsignal=TERM
redirect_stderr=true
stdout_logfile=/chemin/donnees-brvm/journaux/service.sortie.log
```

Modèle pour **Docker Compose** (production), à adapter :

```yaml
services:
  brvm-moteur:
    build:
      context: ./brvm-alpha
      dockerfile: deploiement/Dockerfile.moteur
    network_mode: "service:odoo"   # même espace réseau qu'Odoo : 127.0.0.1:8765 leur est commun
    depends_on: [odoo]
    restart: unless-stopped
    environment:
      BRVM_ALPHA_PREFIXE: /rz_brvm_alpha/ui
      BRVM_ALPHA_ORIGINES_RELAIS: https://erp.exemple.com
    volumes:
      - brvm_donnees:/donnees
    # Jamais de « ports: » : le moteur n'a pas d'authentification.
volumes:
  brvm_donnees:
```

Avec `network_mode: "service:odoo"`, le moteur et Odoo partagent 127.0.0.1. Le relais appelle
`http://127.0.0.1:8765`, comme en préproduction. Aucun autre conteneur (nginx, cloudflared) ne peut
joindre le moteur. Deux conséquences : le port 8765 doit être libre dans le conteneur Odoo ; quand le
conteneur Odoo est recréé, celui du moteur doit l'être aussi. Si le volume est un dossier du NAS
(montage direct), ce dossier doit appartenir au compte 10001 de l'image.

Variante déconseillée : mettre le moteur sur un réseau interne et le faire écouter sur toutes les
adresses du conteneur (`python -m brvm_alpha serve --hote 0.0.0.0`, avec l'avertissement du moteur).
Tout conteneur de ce réseau peut alors lire et écrire les notes sans authentification. Le relais doit
en plus envoyer l'en-tête `Host: 127.0.0.1:8765`, sinon le moteur refuse (400).

Arrêt : le signal TERM arrête le service tout de suite. Une opération longue en cours (rapport,
recherche) est alors perdue. Le journal des notes est écrit par ajout de lignes entières, chacune
forcée sur le disque ; une ligne coupée par un arrêt brutal est ignorée à la lecture et signalée.

## 7. Première collecte

```sh
export BRVM_PYTHON=/chemin/venv-brvm/bin/python
export BRVM_ALPHA_DONNEES=/chemin/donnees-brvm
export BRVM_ALPHA_RAPPORTS=/chemin/donnees-brvm/rapports
sh brvm-alpha/deploiement/collecte-initiale.sh --simulation   # d'abord : ne rien envoyer
sh brvm-alpha/deploiement/collecte-initiale.sh                # ensuite : pour de bon
```

Ce que fait le script :

1. il lit dans `etat --format json` le nombre de jours ouvrés qui restent à chercher depuis le
   02/01/2017 ;
2. il lance `update --from 2017-01-02 --sans-panel` tant qu'il en reste **et** que chaque lancement
   avance ;
3. il s'arrête proprement **au premier refus du site** (seulement si `etat` dit `site.bloque` ; aucune
   autre requête, pas de notes, pas de rapport) ou **si un lancement n'avance plus** ; une mauvaise
   utilisation de `update` (code 2) est dite comme telle, ce n'est pas un refus ;
4. puis il lance `panel`, `notes research --pdf 20` et, **seulement si `etat` dit « prêt »** (historique
   complet), `report --capital 10000000` : jamais de rapport sur un historique incomplet.

**Durée.** Environ **11 heures** de téléchargement : près de 4 000 requêtes (relevé sur
l'historique du 02/01/2017 au 20/11/2026 : 2 334 bulletins, 246 jours sans bulletin), 10 secondes au
moins entre deux. Cela fait une vingtaine de lancements de `update` de 200 requêtes. Le délai de
10 secondes est une règle de politesse envers le site : il ne se règle pas plus bas.

Le script peut être arrêté (Ctrl+C, ou signal TERM au script : la commande en cours reçoit TERM et
s'arrête proprement) et relancé : il reprend où il en était (`update` cherche tout jour manquant depuis
le 02/01/2017). Un seul exemplaire tourne à la fois : verrou `flock` sur `brvm-alpha.verrou` dans le
dossier des journaux, tenu aussi par la commande en cours, rendu par le système à la mort du dernier
processus (aucun verrou « périmé » à retirer à la main). Le journal horodaté est `collecte-initiale.log`
dans le dossier des journaux.

Codes de sortie (jamais 3) : 0 terminé ; 1 collecte incomplète ou étape en échec ; 2 mauvaise
utilisation ; 4 une autre tâche tourne déjà ; 5 refus du site ; 8 configuration (`flock` absent, moteur
mal configuré) ; 130 ou 143 arrêt demandé.

Après un refus du site (HTTP 403 ou 429), **ne pas insister**. Le moteur n'envoie plus rien à
www.brvm.org tant que le blocage n'est pas levé, et il ne se lève qu'avec l'accord du site.

Avec Docker : `docker exec -d <conteneur du moteur> sh deploiement/collecte-initiale.sh`. Les
tâches se lancent **dans le conteneur du moteur** (le verrou est un `flock` sur un fichier du volume).

## 8. Tâche quotidienne

`deploiement/quotidien.sh` lance `update --sans-panel` (le bulletin du jour et, dans la limite du quota,
les trous de l'historique depuis le 02/01/2017), `panel`, `suivi maj` (suivi sur papier ; un échec n'arrête pas
la suite), `notes research --pdf 20`, puis `report` si `etat` dit « prêt ». Il prend le même verrou que la
première collecte. Il tourne en priorité basse
(`nice -n 19`, et `ionice -c 2 -n 7` s'il existe : la classe « inactive » pouvait affamer la tâche).

Modèle cron (heure UTC, soirs de bourse, après la parution du bulletin) :

```cron
30 22 * * 1-5  BRVM_PYTHON=/chemin/venv-brvm/bin/python BRVM_ALPHA_DONNEES=/chemin/donnees-brvm BRVM_ALPHA_RAPPORTS=/chemin/donnees-brvm/rapports sh /chemin/brvm-alpha/deploiement/quotidien.sh >/dev/null
```

Avec Docker : `docker exec <conteneur du moteur> sh deploiement/quotidien.sh`, depuis le
planificateur de tâches du NAS.

Durée habituelle : quelques minutes. Le bulletin du jour demande une à cinq requêtes. La collecte
des notes en envoie jusqu'à 150 (25 minutes au plus, surtout de l'attente). Si le bulletin du jour
n'est pas encore paru, la tâche réussit quand même ; l'interface affiche alors « Données en retard ».

Codes de sortie (jamais 3) : 0 tout va bien ; 1 une étape a échoué ou l'historique est incomplet (pas de
rapport) ; 2 mauvaise utilisation ; 4 une autre tâche tourne déjà ; 5 refus du site ; 8 configuration ;
130 ou 143 arrêt demandé. Journal : `quotidien.log`.

## 9. Préfixe et relais

### 9.1 Réglages du moteur

```sh
python -m brvm_alpha serve --prefixe /rz_brvm_alpha/ui --origine-relais https://erp.exemple.com
```

- `--prefixe /chemin` : le moteur ne sert que les chemins qui commencent par ce préfixe. Il le
  retire avant d'aiguiller. **Tout autre chemin répond 404**, sans exception (`/etat.json` aussi).
  Tous les liens, actions de formulaire, adresses de fichiers et de rapports, exports, appels
  JavaScript et en-têtes `Location` portent le préfixe. Le préfixe commence par `/`, ne finit pas par
  `/`, sans `//`, sans `..`, sans `?` ni `#` ; lettres non accentuées, chiffres, `-`, `_`, `.`, `~`.
- `--origine-relais URL` (répétable) : origine que le **navigateur** voit, par exemple
  `https://erp.exemple.com`. Elle s'ajoute aux origines acceptées pour les formulaires. Donner chaque
  adresse par laquelle les utilisateurs arrivent (nom public, adresse du réseau local…). Forme :
  `schéma://hôte[:port]`, sans chemin, sans joker.
- `--cadre-meme-origine` : nécessaire **seulement** si Odoo affiche l'interface dans un cadre
  (`iframe`). Par défaut le moteur interdit tout cadre. Avec l'option il autorise un cadre de la même
  origine que la page (`X-Frame-Options: SAMEORIGIN`, `frame-ancestors 'self'`), jamais d'un autre
  site.

Sans ces options, rien ne change : pas de préfixe, origine locale seule, aucun cadre.

### 9.2 Contrat du relais

Le relais reçoit `https://erp.exemple.com/rz_brvm_alpha/ui/<suite>?<paramètres>` et appelle
`http://127.0.0.1:8765/rz_brvm_alpha/ui/<suite>?<paramètres>` : **même chemin, mêmes paramètres**.

Avant tout appel, à chaque requête (GET, HEAD et POST, y compris `/rapport/voir`, `/api/travail` et
`/etat.json`) : **vérifier la session Odoo et l'appartenance au groupe**. Sans cela, ne rien relayer.

Requête, du relais vers le moteur :

| Élément | Règle |
|---|---|
| Méthode | GET, HEAD, POST seulement. Les autres : ne pas relayer. |
| Chemin et paramètres | Tels quels, préfixe compris. Ne relayer que ce qui est sous le préfixe. Relayer aussi le préfixe seul, avec ou sans `/` final : c'est le tableau de bord. Les chemins du moteur sont en caractères simples : rien à encoder. |
| `Host` | Celui de l'adresse locale du moteur : `127.0.0.1:8765`. **Jamais** celui du navigateur (le moteur répond 400). |
| `Origin` | **Transmettre tel quel.** Ne pas l'inventer, ne pas le réécrire, ne pas le retirer. |
| `Sec-Fetch-Site` | **Transmettre tel quel.** |
| `Content-Type` (POST) | Transmettre. Le moteur n'accepte que `application/x-www-form-urlencoded` (415 sinon). |
| Corps (POST) | Les champs du formulaire, **inchangés**, champ `_jeton` compris, en UTF-8. `Content-Length` exact (411 s'il manque). 256 Ko au plus (413 au-delà), 64 champs au plus. |
| `Cookie`, `Authorization` | **Retirer.** Le moteur n'en a pas besoin ; la session Odoo ne doit pas sortir d'Odoo. |
| `Referer` | Retirer. Le moteur ne le lit pas. |
| `X-Forwarded-*` | Inutiles : le moteur les ignore. |
| Délai d'attente | 60 secondes au moins (120 sur un NAS). Les pages les plus lourdes ont répondu en 3 à 6 secondes sur la machine de développement. |

Réponse, du moteur vers le navigateur :

| Élément | Règle |
|---|---|
| Code | Tel quel (200, 303, 400, 403, 404, 409, 411, 413, 415, 500). |
| Redirections | **Ne pas les suivre** côté serveur. Le moteur répond 303 avec `Location: /rz_brvm_alpha/ui/...` (chemin seul, préfixe compris) : transmettre le code et l'en-tête **tels quels**. |
| Corps | Tel quel, sans réécriture : les adresses portent déjà le préfixe. |
| `Content-Type` | Tel quel (pages HTML, JSON, texte pour l'export Markdown). |
| `Content-Security-Policy` | **Tel quel. Ne jamais le retirer ni le remplacer.** Pour le rapport (`/rapport/voir`), il porte un bac à sable (`sandbox`, sans `allow-same-origin`) : c'est lui qui empêche les scripts du rapport d'agir au nom de l'utilisateur dans Odoo. |
| `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Cache-Control`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`, `Permissions-Policy` | Tels quels. `Cache-Control: no-store` interdit toute mise en cache (nginx, Cloudflare) : les pages portent le jeton des formulaires. |
| `Connection`, `Content-Length`, `Server`, `Date`, `Transfer-Encoding` | Ceux du relais (ne pas recopier). |
| `Set-Cookie` | Le moteur n'en envoie jamais. |

Points propres à Odoo :

- La route POST du relais doit être déclarée **sans le contrôle CSRF d'Odoo** (`csrf=False`) : les
  formulaires du moteur ne portent pas le jeton d'Odoo. La protection vient alors de trois contrôles
  du moteur, qui restent tous en place : l'origine (`Origin` dans la liste déclarée), `Sec-Fetch-Site`
  (`same-origin` ou `none`), et le jeton `_jeton` du formulaire. C'est pour cela que `Origin`,
  `Sec-Fetch-Site` et le corps doivent arriver intacts.
- Odoo lit le formulaire avant d'appeler le contrôleur. Le corps brut peut donc être vide à ce
  moment : dans ce cas, **ré-encoder tous les champs reçus** (valeurs répétées comprises) en
  `application/x-www-form-urlencoded`, UTF-8, sans en ajouter ni en retirer.
- Le jeton `_jeton` est propre à un lancement du moteur. Après un redémarrage du moteur, une page
  restée ouverte a un jeton périmé : le moteur répond 403 et réaffiche le formulaire avec la saisie
  (notes, portefeuille) ou une page d'erreur. Il suffit de renvoyer ou de recharger.
- Si l'interface est dans un cadre : lancer le moteur avec `--cadre-meme-origine`, et ne pas mettre
  d'attribut `sandbox` sur le cadre d'Odoo. Si nginx ajoute son propre `X-Frame-Options`, vérifier
  qu'il n'y en a pas deux qui se contredisent.
- Si le moteur ne répond pas (arrêté, en cours de redémarrage) : afficher un message clair, par
  exemple « moteur indisponible », plutôt qu'une trace.
- Le moteur ne connaît pas l'utilisateur. Toutes les notes saisies portent l'auteur « analyste ».
  Si l'on veut savoir qui a fait quoi, c'est au relais de le journaliser.

Le relais de référence (`tests/test_deploiement_ui.py`, classe `ReferenceRelay`, 40 lignes) applique
ces règles et passe les tests. Il peut servir de modèle.

### 9.3 État du moteur

`GET <préfixe>/etat.json` rend le même contenu que `python -m brvm_alpha etat --format json` : `pret`,
`version`, `panel` (dernière séance, séances présentes et manquantes, retard), `bulletins` (en cache,
jours à télécharger), `site` (blocage éventuel), `notes`, `rapport`, `donnees` (dossier, taille).
Lecture seule, aucune requête vers l'extérieur. Le relevé est gardé 10 secondes en mémoire. Il passe
par le relais comme les autres pages : il montre les chemins des dossiers du serveur.

## 10. Points de sécurité

- **Pas d'authentification dans le moteur.** Toute personne qui atteint son port peut lire et écrire
  les notes. Il reste lié à 127.0.0.1. Ne jamais publier son port. Ne pas utiliser `--hote`.
- **L'en-tête `Host` est vérifié** (`localhost`, `127.0.0.1`, `[::1]` et le port du service). Cela
  ne change pas derrière un relais.
- **Les formulaires gardent leurs trois contrôles** : origine, `Sec-Fetch-Site`, jeton. L'option
  `--origine-relais` ajoute des origines ; elle n'en retire aucune et ne dispense de rien.
- **Aucune redirection ouverte** : `Location` est toujours un chemin construit par le moteur, avec
  le préfixe. Jamais une adresse complète, jamais une valeur venue du navigateur.
- **Aucun chemin de fichier venu du navigateur** : un rapport est choisi par son nom dans la liste
  que le moteur dresse lui-même. Le préfixe vient de la configuration, pas de la requête.
- **Le relais met l'interface dans l'origine d'Odoo.** Une faille de type XSS dans Odoo donnerait
  donc accès à l'interface, aux droits de l'utilisateur connecté. À l'inverse, les pages du moteur
  n'exécutent que leur propre script (politique de contenu stricte), et le rapport est isolé par son
  bac à sable — tant que le relais transmet `Content-Security-Policy`.
- **Le groupe Odoo est la seule barrière d'accès.** Tous les membres voient les mêmes notes et
  peuvent en saisir, en archiver, lancer une recherche (jusqu'à 150 requêtes vers www.brvm.org) ou un
  rapport.
- **Compte sans privilège** pour le service et les tâches. Le code peut être en lecture seule.
- **Aucun secret** dans le code, les scripts ou l'image. Rien à protéger de ce côté.
- **Sauvegarde** : le seul fichier irremplaçable est `notes/notes.jsonl` (les notes saisies). Tout le
  reste se reconstruit (les bulletins en 11 heures).

## 11. Charge machine

Mesures sur la machine de développement (4 processeurs). **Ce n'est pas le NAS** : compter plus
long sur un processeur modeste. Pour le moteur embarqué (production), voir les mesures des § A.9 et A.10.

| Activité | Durée | Mémoire | Remarque |
|---|---|---|---|
| Service au repos | — | 110 Mo au démarrage ; 440 à 520 Mo après usage | aucun calcul sans requête ; le panel reste en mémoire après la première page lourde |
| Page courante | moins de 0,1 s | — | tableau de bord, recherche, indices déjà calculés |
| Page lourde, premier appel | 3 à 6 s | — | notes en vigueur, dossier d'indice, explication d'un titre |
| `etat` ou `/etat.json` | 1,5 s | 260 Mo (commande) | parcourt le dossier de données |
| `panel`, rien de nouveau | 6 s | 350 Mo | seuls les nouveaux bulletins sont relus |
| `panel`, tout l'historique | 1 minute | 560 Mo | 2 processus ; une fois, à la fin de la première collecte |
| `report` | 20 s | 500 Mo | un processeur |
| `update` et `notes research` | minutes à heures | faible | presque tout le temps en attente (10 s entre deux requêtes) |

- Disque : environ 185 Mo pour l'historique complet (bulletins 44 Mo, panel 12 Mo, notes et cache
  des documents 128 Mo), plus 0,5 Mo par rapport et les journaux. Prévoir 500 Mo.
- Le service traite 32 connexions au plus à la fois et **une seule opération longue** (recherche,
  rapport, ordre de bataille). Une seconde demande reçoit « opération en cours ».
- Pendant une opération longue, la page ouverte interroge le moteur toutes les 2 secondes. Chaque
  appel passe par le relais et occupe un processus Odoo quelques millisecondes.
- Les tâches de fond tournent en priorité basse et ne se chevauchent pas (verrou).

## 12. Mise à jour du code

1. Récupérer le code (dépôt git privé). Les données ne sont pas dans le code : elles ne bougent pas.
2. Si `deploiement/requirements-moteur.txt` a changé : relancer l'installation des paquets dans
   l'environnement du moteur (ou reconstruire l'image).
3. Redémarrer le service (`supervisorctl restart brvm-alpha`, ou recréer le conteneur).
4. Vérifier : `python -m brvm_alpha etat` affiche la nouvelle version du code (commit court) et
   « Prêt : oui ».
5. Ne jamais lancer `validate` ni `backtest` sur le serveur : les résultats de la validation sont
   livrés avec le code (en mode embarqué, ces commandes sont refusées, code 8).
6. Ne jamais faire tourner deux versions du moteur sur le même dossier de données (§ A.15 : verrous `flock`
   contre l'ancien protocole). Pour revenir à une version d'avant le 22/11/2026 : arrêter toute commande, puis
   supprimer les fichiers `*.lock` du dossier de données.

## 13. Désinstallation

1. Retirer le menu et le relais côté Odoo (désinstaller le module).
2. Arrêter et retirer le service (programme supervisor, ou service Compose) et la tâche planifiée.
3. Sauvegarder `notes/notes.jsonl` si les notes saisies doivent être gardées.
4. Supprimer le dossier de données, le dossier du code et l'environnement Python du moteur (ou
   l'image et le volume Docker).
5. Rien d'autre n'a été installé : ni service système, ni fichier hors de ces dossiers, ni paquet
   dans l'environnement d'Odoo (hors `poppler-utils`, s'il a été ajouté).

## 14. Dépannage

| Symptôme | Cause probable |
|---|---|
| 400 « Hôte refusé » | Le relais transmet l'en-tête `Host` du navigateur. Il doit appeler `127.0.0.1:PORT`. |
| 403 sur tous les formulaires | L'origine du navigateur n'est pas déclarée (`--origine-relais`), ou le relais réécrit `Origin` / `Sec-Fetch-Site`, ou le jeton `_jeton` n'arrive pas dans le corps. |
| 404 sur toutes les pages | Le relais retire le préfixe, ou le moteur n'a pas été lancé avec le même préfixe. |
| 415 ou 411 | Le corps n'est pas un formulaire urlencodé, ou `Content-Length` manque. |
| Page blanche dans le cadre d'Odoo | Le moteur n'a pas `--cadre-meme-origine`, ou un autre `X-Frame-Options` est ajouté en chemin. |
| « Prêt : non » | La première collecte n'a pas été faite, ou `BRVM_ALPHA_DONNEES` n'est pas le même pour le service et pour les tâches. `etat` affiche les dossiers lus. |
| Tâche qui sort avec le code 4 | Une autre tâche tient le verrou (`flock` sur `brvm-alpha.verrou` dans le dossier des journaux, ou un verrou du moteur). `fuser brvm-alpha.verrou` montre qui le tient ; il est rendu à la fin de ce processus, rien à retirer à la main. |
| Code 8 | Configuration : en mode embarqué, `BRVM_ALPHA_DONNEES` ou `BRVM_ALPHA_RAPPORTS` absent, relatif ou inexistant ; `pdftotext` absent (installer `poppler-utils`) ; paquet Python manquant ; dossier de données non inscriptible (volume en lecture seule, droits, disque plein) ; `politeness.json` illisible. Le message JSON le dit. |
| Code 6 | Mémoire : limite de mémoire virtuelle sous 1 Go (la relever à 3 Go), ou mémoire réellement insuffisante. |
