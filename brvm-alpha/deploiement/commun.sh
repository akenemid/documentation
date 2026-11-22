# Fonctions communes aux scripts de déploiement de BRVM Alpha. À inclure avec « . », pas à lancer.
# Shell POSIX (sh). Aucun secret, aucun chemin en dur : tout vient des variables ci-dessous.
#
#   BRVM_PYTHON          interpréteur Python du moteur (obligatoire) : celui de son environnement
#                        isolé, jamais celui d'Odoo
#   BRVM_CODE            dossier du code, celui qui contient brvm_alpha/ (défaut : parent de ce dossier)
#   BRVM_ALPHA_DONNEES   dossier des données, lu par le moteur (défaut : data/ dans le code)
#   BRVM_ALPHA_RAPPORTS  dossier des rapports écrits, lu par le moteur (défaut : reports/ dans le code)
#   BRVM_JOURNAL         dossier des journaux et du verrou (défaut : journaux/ dans les données)
#
# Performance passée ≠ garantie. Aucun gain n'est garanti.

BRVM_PRIORITE=""

brvm_echec() {
    printf '%s\n' "$*" >&2
    exit 2
}

# Contrôle les variables, se place dans le dossier du code, prépare le journal « <nom>.log ».
brvm_init() {
    BRVM_NOM=$1
    if [ -z "${BRVM_PYTHON:-}" ]; then
        brvm_echec "BRVM_PYTHON n'est pas défini : donner l'interpréteur Python du moteur."
    fi
    if [ -z "${BRVM_CODE:-}" ]; then
        BRVM_CODE=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
    fi
    if [ ! -d "$BRVM_CODE/brvm_alpha" ]; then
        brvm_echec "BRVM_CODE ($BRVM_CODE) ne contient pas le paquet brvm_alpha."
    fi
    if [ -n "${BRVM_ALPHA_DONNEES:-}" ]; then export BRVM_ALPHA_DONNEES; fi
    if [ -n "${BRVM_ALPHA_RAPPORTS:-}" ]; then export BRVM_ALPHA_RAPPORTS; fi
    BRVM_JOURNAL=${BRVM_JOURNAL:-${BRVM_ALPHA_DONNEES:-$BRVM_CODE/data}/journaux}
    mkdir -p "$BRVM_JOURNAL"
    BRVM_FICHIER=$BRVM_JOURNAL/$BRVM_NOM.log
    BRVM_ETAT=$BRVM_JOURNAL/$BRVM_NOM.etat.json
    PYTHONUNBUFFERED=1
    export PYTHONUNBUFFERED
    cd "$BRVM_CODE"
}

# Écrit une ligne horodatée (UTC) à l'écran et dans le journal.
journal() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$BRVM_FICHIER"
}

# Priorité basse pour les tâches de fond : nice, et ionice s'il existe et s'il est permis.
brvm_priorite_basse() {
    if nice -n 19 true 2>/dev/null; then BRVM_PRIORITE="nice -n 19"; fi
    if command -v ionice >/dev/null 2>&1 && ionice -c 3 true 2>/dev/null; then
        BRVM_PRIORITE="ionice -c 3 $BRVM_PRIORITE"
    fi
}

# Verrou contre le double lancement : un dossier (création atomique) qui porte le numéro du processus.
# Le même verrou sert à la première collecte et à la tâche quotidienne : jamais les deux à la fois.
brvm_verrou() {
    BRVM_VERROU=$BRVM_JOURNAL/brvm-alpha.verrou
    if ! mkdir "$BRVM_VERROU" 2>/dev/null; then
        autre=$(cat "$BRVM_VERROU/pid" 2>/dev/null || true)
        if [ -z "$autre" ]; then
            sleep 2   # verrou en cours de pose par une autre tâche : on lui laisse le temps d'écrire
            autre=$(cat "$BRVM_VERROU/pid" 2>/dev/null || true)
        fi
        if [ -n "$autre" ] && kill -0 "$autre" 2>/dev/null; then
            journal "arrêt : une autre tâche tourne déjà (processus $autre, verrou $BRVM_VERROU)."
            exit 3
        fi
        journal "verrou périmé (processus ${autre:-inconnu} absent) : repris."
        rm -rf "$BRVM_VERROU"
        if ! mkdir "$BRVM_VERROU" 2>/dev/null; then
            journal "arrêt : le verrou vient d'être repris par une autre tâche."
            exit 3
        fi
    fi
    printf '%s\n' "$$" > "$BRVM_VERROU/pid"
    trap 'rm -rf "$BRVM_VERROU"' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP
}

# Lance une commande du moteur. Sa sortie va dans le journal, entre deux lignes horodatées.
# Le code de sortie est rangé dans BRVM_CODE_RETOUR (la fonction, elle, réussit toujours).
lancer() {
    journal "début : brvm_alpha $*"
    BRVM_CODE_RETOUR=0
    # shellcheck disable=SC2086 # BRVM_PRIORITE porte plusieurs mots, exprès
    $BRVM_PRIORITE "$BRVM_PYTHON" -m brvm_alpha "$@" >>"$BRVM_FICHIER" 2>&1 || BRVM_CODE_RETOUR=$?
    journal "fin : brvm_alpha $1 (code $BRVM_CODE_RETOUR)"
}

# Relève l'état de l'installation (« etat --format json » : lecture seule, aucune requête).
etat_releve() {
    # shellcheck disable=SC2086
    if ! $BRVM_PRIORITE "$BRVM_PYTHON" -m brvm_alpha etat --format json >"$BRVM_ETAT" 2>>"$BRVM_FICHIER"; then
        journal "échec : état de l'installation illisible (commande « etat »)."
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
