# Fonctions communes aux scripts de déploiement de BRVM Alpha. À inclure avec « . », pas à lancer.
# Shell POSIX (sh). Aucun secret, aucun chemin en dur : tout vient des variables ci-dessous.
#
#   BRVM_PYTHON          interpréteur Python du moteur (obligatoire) : celui de son environnement
#                        isolé, jamais celui d'Odoo ; chemin absolu, ou nom d'une commande du PATH
#   BRVM_CODE            dossier du code, celui qui contient brvm_alpha/ (défaut : parent de ce dossier)
#   BRVM_ALPHA_DONNEES   dossier des données, lu par le moteur (défaut : data/ dans le code) ; chemin absolu
#   BRVM_ALPHA_RAPPORTS  dossier des rapports écrits, lu par le moteur (défaut : reports/ dans le code) ;
#                        chemin absolu
#   BRVM_JOURNAL         dossier des journaux et du verrou (défaut : journaux/ dans les données) ; chemin absolu
#
# Codes de sortie des scripts (jamais 3 : dans le conteneur Odoo, le processus 1 s'arrête s'il récolte un
# enfant sorti avec ce code) : 0 succès ; 1 étape en échec ou collecte incomplète ; 2 mauvaise utilisation ;
# 4 une autre tâche tient le verrou ; 5 refus du site ; 8 configuration (flock absent, moteur mal configuré) ;
# 130 ou 143 arrêt demandé (Ctrl+C, signal TERM).
#
# Performance passée ≠ garantie. Aucun gain n'est garanti.

BRVM_PRIORITE=""
BRVM_ENFANT=""

brvm_echec() {
    printf '%s\n' "$*" >&2
    exit 2
}

# Refuse un chemin relatif : il serait lu avant et après le « cd » dans le dossier du code.
brvm_absolu() {
    case "$2" in
        /*) ;;
        *) brvm_echec "$1 doit être un chemin absolu (reçu : « $2 »)." ;;
    esac
}

# Contrôle les variables, se place dans le dossier du code, prépare le journal « <nom>.log ».
brvm_init() {
    BRVM_NOM=$1
    if [ -z "${BRVM_PYTHON:-}" ]; then
        brvm_echec "BRVM_PYTHON n'est pas défini : donner l'interpréteur Python du moteur."
    fi
    case "$BRVM_PYTHON" in
        /*) ;;
        */*) brvm_echec "BRVM_PYTHON doit être un chemin absolu ou le nom d'une commande (reçu : « $BRVM_PYTHON »)." ;;
    esac
    if [ -z "${BRVM_CODE:-}" ]; then
        BRVM_CODE=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
    elif [ -d "$BRVM_CODE" ]; then
        BRVM_CODE=$(CDPATH='' cd -- "$BRVM_CODE" && pwd)
    fi
    if [ ! -d "$BRVM_CODE/brvm_alpha" ]; then
        brvm_echec "BRVM_CODE ($BRVM_CODE) ne contient pas le paquet brvm_alpha."
    fi
    if [ -n "${BRVM_ALPHA_DONNEES:-}" ]; then
        brvm_absolu BRVM_ALPHA_DONNEES "$BRVM_ALPHA_DONNEES"
        export BRVM_ALPHA_DONNEES
    fi
    if [ -n "${BRVM_ALPHA_RAPPORTS:-}" ]; then
        brvm_absolu BRVM_ALPHA_RAPPORTS "$BRVM_ALPHA_RAPPORTS"
        export BRVM_ALPHA_RAPPORTS
    fi
    BRVM_JOURNAL=${BRVM_JOURNAL:-${BRVM_ALPHA_DONNEES:-$BRVM_CODE/data}/journaux}
    brvm_absolu BRVM_JOURNAL "$BRVM_JOURNAL"
    mkdir -p "$BRVM_JOURNAL"
    BRVM_FICHIER=$BRVM_JOURNAL/$BRVM_NOM.log
    BRVM_ETAT=$BRVM_JOURNAL/$BRVM_NOM.etat.json
    PYTHONUNBUFFERED=1
    export PYTHONUNBUFFERED
    cd "$BRVM_CODE"
}

# Contrôle qu'une variable est un entier strictement positif (sinon : mauvaise utilisation, code 2).
brvm_entier() {
    case "$2" in
        ''|*[!0-9]*|0) brvm_echec "$1 doit être un entier strictement positif (reçu : « $2 »)." ;;
    esac
}

# Écrit une ligne horodatée (UTC) à l'écran et dans le journal.
journal() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$BRVM_FICHIER"
}

# Priorité basse pour les tâches de fond : nice, et ionice s'il existe et s'il est permis. Classe « au mieux »,
# priorité la plus basse (-c 2 -n 7) : la classe « inactive » (-c 3) pouvait affamer la tâche sur un disque chargé.
brvm_priorite_basse() {
    if nice -n 19 true 2>/dev/null; then BRVM_PRIORITE="nice -n 19"; fi
    if command -v ionice >/dev/null 2>&1 && ionice -c 2 -n 7 true 2>/dev/null; then
        BRVM_PRIORITE="ionice -c 2 -n 7 $BRVM_PRIORITE"
    fi
}

# Arrêt demandé (TERM, INT, HUP) : le signal TERM est transmis à la commande du moteur en cours (elle s'arrête
# proprement : verrous rendus, aucun fichier à moitié écrit), on attend sa fin, puis on sort.
brvm_arret() {
    if [ -n "$BRVM_ENFANT" ]; then
        kill -TERM "$BRVM_ENFANT" 2>/dev/null || true
        wait "$BRVM_ENFANT" 2>/dev/null || true
        BRVM_ENFANT=""
    fi
    journal "arrêt demandé (signal $1) : la commande en cours a été arrêtée ; fin de la tâche."
    exit "$2"
}

# Verrou contre le double lancement : flock(1) sur un fichier qui n'est jamais supprimé. Le système le rend à
# la mort du dernier processus qui le tient (aucun numéro de processus à deviner, aucun verrou « périmé »).
# Les commandes du moteur héritent du verrou : une commande restée seule (tâche tuée par KILL) le garde
# jusqu'à sa fin, et une relance attend. Même verrou pour la première collecte et la tâche quotidienne.
brvm_verrou() {
    BRVM_VERROU=$BRVM_JOURNAL/brvm-alpha.verrou
    if ! command -v flock >/dev/null 2>&1; then
        journal "arrêt : la commande flock (paquet util-linux) est introuvable ; elle sert au verrou des tâches."
        exit 8
    fi
    # Descripteur 9 ouvert en ajout : le fichier n'est ni vidé ni supprimé.
    exec 9>>"$BRVM_VERROU"
    if ! flock -n 9; then
        journal "arrêt : une autre tâche tourne déjà (verrou $BRVM_VERROU tenu) ; rien n'est lancé."
        exit 4
    fi
    trap 'brvm_arret TERM 143' TERM
    trap 'brvm_arret INT 130' INT
    trap 'brvm_arret HUP 129' HUP
}

# Lance une commande du moteur. Sa sortie va dans le journal, entre deux lignes horodatées.
# Le code de sortie est rangé dans BRVM_CODE_RETOUR (la fonction, elle, réussit toujours). La commande tourne
# en arrière-plan, attendue par « wait », pour qu'un signal d'arrêt lui soit transmis (brvm_arret).
lancer() {
    journal "début : brvm_alpha $*"
    BRVM_CODE_RETOUR=0
    # shellcheck disable=SC2086 # BRVM_PRIORITE porte plusieurs mots, exprès
    $BRVM_PRIORITE "$BRVM_PYTHON" -m brvm_alpha "$@" >>"$BRVM_FICHIER" 2>&1 &
    BRVM_ENFANT=$!
    wait "$BRVM_ENFANT" || BRVM_CODE_RETOUR=$?
    BRVM_ENFANT=""
    journal "fin : brvm_alpha $1 (code $BRVM_CODE_RETOUR)"
}

# Relève l'état de l'installation (« etat --format json » : lecture seule, aucune requête).
etat_releve() {
    # shellcheck disable=SC2086
    if ! $BRVM_PRIORITE "$BRVM_PYTHON" -m brvm_alpha etat --format json >"$BRVM_ETAT" 2>>"$BRVM_FICHIER"; then
        journal "échec : état de l'installation illisible (commande « etat », voir le journal)."
        exit 1
    fi
}

# Affiche un champ du dernier état relevé. Exemple : etat_champ bulletins.jours_a_telecharger
etat_champ() {
    "$BRVM_PYTHON" -c '
import json, sys
valeur = json.load(open(sys.argv[1], encoding="utf-8"))
for cle in sys.argv[2].split("."):
    valeur = valeur[cle]
print(str(valeur).lower() if isinstance(valeur, bool) else valeur)' "$BRVM_ETAT" "$1"
}

# Après « update » : conclut d'après son code et l'état relevé (site.bloque). Rend 0 pour continuer.
#   0 ou 1 (quota atteint, historique pas encore complet) : on continue ;
#   2 : mauvaise utilisation (voir le journal) ; 4 : un autre téléchargement tient son verrou ;
#   5 : refus du site SEULEMENT si etat dit site.bloque = true, sinon erreur réseau ; 8 : configuration.
# Positionne BRVM_CONCLUSION (continuer, usage, verrou, refus, reseau, configuration, echec).
brvm_conclure_update() {
    case "$BRVM_CODE_RETOUR" in
        0|1) BRVM_CONCLUSION=continuer ;;
        2) BRVM_CONCLUSION=usage
           journal "échec : mauvaise utilisation de « update » (code 2), voir le journal ; ce n'est pas un refus du site." ;;
        4) BRVM_CONCLUSION=verrou
           journal "arrêt : un autre téléchargement des bulletins tient son verrou (code 4) ; réessayer plus tard." ;;
        8) BRVM_CONCLUSION=configuration
           journal "arrêt : configuration du moteur invalide (code 8 : dossiers, pdftotext…), voir le journal." ;;
        *) BRVM_CONCLUSION=echec
           journal "échec : « update » est sorti avec le code $BRVM_CODE_RETOUR, voir le journal." ;;
    esac
    if [ "$(etat_champ site.bloque)" = true ]; then
        BRVM_CONCLUSION=refus
        journal "arrêt : www.brvm.org a refusé l'accès (HTTP $(etat_champ site.code_http)). Aucune autre requête n'est envoyée."
    elif [ "$BRVM_CODE_RETOUR" -eq 5 ]; then
        BRVM_CONCLUSION=reseau
        journal "échec : erreur réseau ou refus de la liste blanche (code 5), sans blocage du site ; voir le journal."
    fi
}
