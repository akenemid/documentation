# BRVM Alpha — Déploiement à côté d'Odoo

Ce document dit comment installer le moteur BRVM Alpha sur un serveur qui porte déjà Odoo 17, sans
toucher à l'environnement Python d'Odoo. Il décrit aussi le contrat que doit respecter le **relais**
(le contrôleur Odoo qui montre l'interface du moteur aux utilisateurs autorisés).

> Performance passée ≠ garantie. Aucun gain n'est garanti. BRVM Alpha est une aide à l'analyse, pas
> un conseil en investissement personnalisé.

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

3. **Facultatif** : `pdftotext` (paquet `poppler-utils`) rend la conversion des bulletins plus
   rapide. Sans lui, le moteur se sert de `pdfplumber`.
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

Lues par les scripts de `deploiement/` :

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
3. il s'arrête proprement **au premier refus du site** (aucune autre requête, pas de notes, pas de
   rapport) ou **si un lancement n'avance plus** ;
4. puis il lance `panel`, `notes research --pdf 20` et `report --capital 10000000`.

**Durée.** Environ **11 heures** de téléchargement : près de 4 000 requêtes (relevé sur
l'historique du 02/01/2017 au 20/11/2026 : 2 334 bulletins, 246 jours sans bulletin), 10 secondes au
moins entre deux. Cela fait une vingtaine de lancements de `update` de 200 requêtes. Le délai de
10 secondes est une règle de politesse envers le site : il ne se règle pas plus bas.

Le script peut être arrêté et relancé : il reprend où il en était. Un seul exemplaire tourne à la
fois (verrou). Le journal horodaté est `collecte-initiale.log` dans le dossier des journaux.

Codes de sortie : 0 terminé ; 1 collecte incomplète ou refus du site ; 2 mauvaise utilisation ;
3 une autre tâche tourne déjà.

Après un refus du site (HTTP 403 ou 429), **ne pas insister**. Le moteur n'envoie plus rien à
www.brvm.org tant que le blocage n'est pas levé, et il ne se lève qu'avec l'accord du site.

Avec Docker : `docker exec -d <conteneur du moteur> sh deploiement/collecte-initiale.sh`. Les
tâches se lancent **dans le conteneur du moteur** (le verrou repose sur les numéros de processus).

## 8. Tâche quotidienne

`deploiement/quotidien.sh` lance `update`, `panel`, `notes research --pdf 20`, puis `report`. Il
prend le même verrou que la première collecte. Il tourne en priorité basse (`nice`, et `ionice` s'il
existe).

Modèle cron (heure UTC, soirs de bourse, après la parution du bulletin) :

```cron
30 22 * * 1-5  BRVM_PYTHON=/chemin/venv-brvm/bin/python BRVM_ALPHA_DONNEES=/chemin/donnees-brvm BRVM_ALPHA_RAPPORTS=/chemin/donnees-brvm/rapports sh /chemin/brvm-alpha/deploiement/quotidien.sh >/dev/null
```

Avec Docker : `docker exec <conteneur du moteur> sh deploiement/quotidien.sh`, depuis le
planificateur de tâches du NAS.

Durée habituelle : quelques minutes. Le bulletin du jour demande une à cinq requêtes. La collecte
des notes en envoie jusqu'à 150 (25 minutes au plus, surtout de l'attente). Si le bulletin du jour
n'est pas encore paru, la tâche réussit quand même ; l'interface affiche alors « Données en retard ».

Codes de sortie : 0 tout va bien ; 1 une étape a échoué ou le site a refusé ; 3 une autre tâche
tourne déjà. Journal : `quotidien.log`.

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
long sur un processeur modeste.

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
   livrés avec le code.

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
| Tâche qui sort avec le code 3 | Une autre tâche tient le verrou (`brvm-alpha.verrou` dans le dossier des journaux). |
