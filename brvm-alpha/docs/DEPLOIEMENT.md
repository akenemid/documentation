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
  `reports/diagnostic_S0*/`, `reports/trials.parquet`) et un fichier `VERSION`. Rien d'autre.
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
  `--fichier`) s'entend depuis `BRVM_ALPHA_DONNEES` (un `data/` de tête est retiré) ; `--sortie` depuis
  `BRVM_ALPHA_RAPPORTS` ; « .. » est refusé (code 2). `--sortie` doit rester dans le dossier des rapports ou
  celui des fichiers temporaires du système, et jamais sur un fichier du moteur (`notes/`, `panel/`,
  `boc_text/` des données) ; `--fichier` et `--portefeuille` ne lisent que dans les dossiers de données, de
  rapports ou temporaire (code 2 sinon). Côté Odoo, la règle reste : chemins fabriqués par le module seul ;
- `--racine`, `--panel-dir` et `--boc-dir` désignent toujours un **sous-dossier** de `BRVM_ALPHA_DONNEES`,
  liens symboliques et « .. » résolus : un chemin absolu qui en sort (ou un lien qui mène ailleurs) est refusé en
  code 2, avant toute écriture (avant : `notes add --racine /ailleurs` y créait un journal). `--panel-dir` ne
  recouvre ni `notes/` ni `boc_text/`, car le panel est remplacé d'un bloc à chaque construction. **Odoo ne
  passe jamais ces trois options** : les dossiers par défaut (`<données>/notes`, `panel`, `boc_text`) suffisent.
  Hors mode embarqué, rien ne change ;
- une option de chemin (`--racine`, `--panel-dir`, `--boc-dir`, `--fichier`, `--portefeuille`, `--sortie`) **vide ou
  faite seulement d'espaces** est refusée en code 2, avant toute écriture (avant : `--racine ' '` désignait le dossier
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
  (`docs/research` et ses scripts d'étude compris), ni données, ni scripts de déploiement.
- Écrit `VERSION` : première ligne = commit court (suivi de `+modifie` si le code exporté diffère du
  commit), puis la date UTC, le commit long, le nombre de fichiers et l'empreinte sha256 de chaque fichier.
  Vérification : `grep -E '^[0-9a-f]{64}  ' VERSION | sha256sum -c --quiet`.
- Refuse un dossier situé dans le code ou non vide (code 2). Mesuré : 88 fichiers, 11 Mo.
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
| 4 | `verrou_occupe` | verrou tenu par une autre opération au-delà du délai | deux `panel`, deux `update`, deux `notes research` à la fois |
| 5 | `acces_refuse` | accès refusé ou réseau | HTTP 403 ou 429, site bloqué, liste blanche, délai dépassé |
| 6 | `memoire` | mémoire insuffisante | `MemoryError` (jamais avalée : aucun résultat dégradé en code 0) ; bibliothèque compilée impossible à charger faute de mémoire (« failed to map segment ») ; processus de travail du panel tué par `SIGKILL` sous une limite de mémoire, ou mort sans cause connue sous cette limite (le message dit « cause inconnue ») ; limite `RLIMIT_AS` sous 1 Go (refus au démarrage) |
| 7 | `interne` | erreur interne (exception non prévue) ; trace sur la sortie d'erreur | défaut du moteur ; `ValueError` ou `KeyError` d'une bibliothèque ; processus de travail du panel tué par `SIGSEGV`, `SIGABRT` ou un autre signal qui n'est pas un manque de mémoire |
| 8 | `configuration` | configuration manquante ou invalide | dossiers absents, relatifs ou inexistants en mode embarqué, pdftotext absent, paquet Python manquant, dossier de données ou de rapports non inscriptible (lecture seule, droits, disque plein), état de politesse illisible, `validate`, `backtest` ou `serve` en mode embarqué ; limite de temps de calcul (`RLIMIT_CPU`) trop basse au démarrage, ou atteinte en cours de commande (`SIGXCPU`), processus de travail du panel compris (« temps de calcul ») |
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

Le module Odoo doit de toute façon lancer le moteur dans un **nouveau groupe de processus**, tuer le **groupe**, et
ne jamais se faire **récolteur des petits-enfants** (pas de `PR_SET_CHILD_SUBREAPER`, pas de `waitpid(-1)`) : il
n'attend que son enfant direct. Un petit-enfant orphelin est alors récolté par le processus 1 du conteneur : si c'est
le maître Odoo, le risque d'un code 3 récolté ne disparaît qu'avec un vrai processus 1 (par exemple `tini` ou
`dumb-init` en tête de l'image), qui récolte les orphelins sans s'arrêter. Non vérifié dans l'image odoo:17.0.

### A.8 Sortie JSON

Avec `--format json`, la sortie standard porte **exactement un objet JSON**, erreur comprise ;
avertissements et progression vont sur la sortie d'erreur. Pendant l'écriture de l'objet, TERM et `SIGXCPU` sont
reportés : l'objet n'est jamais coupé, ni suivi d'un second objet (avant : un signal reçu pendant l'écriture d'un gros
objet vers un tube donnait un objet coupé puis un second objet). Une fois l'objet écrit, TERM et `SIGXCPU` ne changent
plus le code de sortie : c'est celui de l'objet. Pour `notes add`, `notes archive`, `notes export`, `recommend
--sortie` et `report`, dont l'écriture est la dernière étape, TERM et `SIGXCPU` sont aussi reportés du dernier instant
de l'écriture (ligne ajoutée au journal, renommage du fichier) jusqu'à l'objet : une note enregistrée sort en 0 avec son
objet, jamais en 8 « arrêtée » (avant : 3 fois en 40 essais). Avant cet instant, TERM arrête la commande comme avant (130),
y compris pendant l'attente d'un verrou. Si la sortie standard est un tube que personne ne lit, le moteur reste bloqué
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
| `notes add --cible SNTS --titre … --texte … [--avis] [--conviction] [--publie-le] [--veto]` | 1,1 s | court | `notes/notes.jsonl` (ajout d'une ligne, fsync) | `notes/notes.jsonl.lock` |
| `notes list [--cible] [--depuis] [--statut] [--limite]` | 0,6 s | court | rien | — |
| `notes show ID` | 0,5 s | court | rien | — |
| `notes archive ID [--motif]` | 0,7 s | court | `notes/notes.jsonl` (nouvelle version) | `notes/notes.jsonl.lock` |
| `indices` | 4,9 s | court | rien | — |
| `indices dossier IDX:BRVM-30` | 3,8 s | court | rien | — |
| `explain SNTS` | 6,8 s | court | rien | — |
| `recommend --capital 10000000 [--portefeuille f.csv] [--cash] [--couts central]` | 14,6 s | court | rien, ou `--sortie` (écriture atomique) | — |
| `report --capital 10000000 --sortie nom.html` | 18,7 s | long | `--sortie` (atomique) ; sans `--sortie`, `<rapports>/rapport_AAAA-MM-JJ.html`, **même nom pour tout capital** : Odoo passe toujours `--sortie` | — |
| `update --sans-panel [--max-requetes 200] [--delai 10] [--rouvrir AAAA-MM-JJ[..AAAA-MM-JJ]]` | minutes | long | `boc_text/boc_*.txt.gz`, `.meta.json`, `.missing`, `.bad` ; `notes/cache/politeness.json`, `notes/fetch_log.jsonl` | `boc_text/.telechargement.lock`, `notes/cache/politeness.json.lock` |
| `update --simulation` | 0,6 s | court | rien | — |
| `panel` (rien de nouveau) | 5,8 s | long | `panel/` (construction à côté, puis bascule) | `.panel.construction.lock`, attend `.panel.lecture.lock` |
| `panel --force` (tout l'historique) | 50 s | long | `panel/` | idem |
| `notes research [--pdf 20]` | jusqu'à 30 min | long | `notes/notes.jsonl` (au fil de l'eau), `notes/cache/`, `notes/fetch_log.jsonl` | `notes/.recherche.lock`, `notes/notes.jsonl.lock`, `politeness.json.lock` |
| `notes research --hors-ligne --pdf 0` | 4,8 s | court | `notes/notes.jsonl` s'il y a du nouveau | idem |
| `notes lire [--max 20] [--hors-ligne]` | 10 s hors ligne ; ≈ 10 s par document en ligne | long | `notes/notes.jsonl`, `notes/cache/docs/` | `notes/.recherche.lock`, `notes/notes.jsonl.lock` |

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
  (129 sur l'historique réel) : `update --rouvrir` permet de les relancer sur décision.

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
  `notes/cache/politeness.json.lock` ; **ne jamais faire tourner deux versions du moteur sur le même dossier de
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
  plus comme « robots.txt interdit », n'est plus compté comme requête et ne réserve plus de créneau dans
  `politeness.json` (avant : 10 s d'attente de trop au lancement suivant) ; adresse réellement jointe contrôlée
  après la connexion ; délai total tenu jusqu'aux en-têtes ; `politeness.json` illisible : aucune requête,
  code 8, fichier non réécrit (avant : le blocage 403 était oublié et le fichier réécrit sans lui) ;
  `fetch_log.jsonl` tourne au-delà de 10 Mo ; les PDF en double du cache HTTP sont retirés ; `live` sort en 5
  pour un site bloqué ou un réseau en défaut (avant : 1) ; une page HTML servie avec un type PDF est lue comme
  une page (avant : note vide) ;
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
les trous de l'historique depuis le 02/01/2017), `panel`, `notes research --pdf 20`, puis `report` si
`etat` dit « prêt ». Il prend le même verrou que la première collecte. Il tourne en priorité basse
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
