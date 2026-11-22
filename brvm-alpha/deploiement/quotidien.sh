#!/bin/sh
# Tâche quotidienne de BRVM Alpha, pensée pour la nuit : nouveaux bulletins, panel, notes, rapport.
#
# Usage :  sh quotidien.sh
# Exemple de planification (cron, heure UTC, après la parution du BOC du soir) :
#   30 22 * * 1-5  BRVM_PYTHON=... BRVM_ALPHA_DONNEES=... sh .../deploiement/quotidien.sh
#
# Priorité basse (nice, et ionice s'il existe) : la tâche laisse la machine aux utilisateurs.
# Durée habituelle : quelques minutes (une à cinq requêtes pour le bulletin, 10 s au moins entre
# deux ; la collecte des notes envoie jusqu'à 150 requêtes, soit 25 minutes au plus).
#
# Variables : voir commun.sh. En plus :
#   BRVM_CAPITAL  capital du rapport, en FCFA (défaut : 10000000)
#
# Codes de sortie : 0 tout s'est bien passé ; 1 une étape a échoué ou le site a refusé ;
# 3 une autre tâche tourne déjà (par exemple la première collecte).
# Performance passée ≠ garantie. Aucun gain n'est garanti.
set -eu
. "$(dirname -- "$0")/commun.sh"

brvm_init quotidien
brvm_priorite_basse
brvm_verrou

CAPITAL=${BRVM_CAPITAL:-10000000}
echecs=0
reseau=oui
journal "tâche quotidienne : début."

# 1. Nouveaux bulletins (du lendemain du dernier bulletin local à aujourd'hui).
lancer update --sans-panel
if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi
etat_releve
if [ "$BRVM_CODE_RETOUR" -eq 2 ] || [ "$(etat_champ site.bloque)" = true ]; then
    reseau=non
    journal "www.brvm.org a refusé l'accès : aucune autre requête cette nuit. Ne pas insister."
fi

# 2. Panel : calcul local (seuls les bulletins nouveaux sont relus).
lancer panel
if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi

# 3. Notes : collecte polie des publications, puis lecture de 20 documents au plus.
if [ "$reseau" = oui ]; then
    lancer notes research --pdf 20
    if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi
fi

# 4. Rapport du jour, si le panel existe.
etat_releve
if [ "$(etat_champ pret)" = true ]; then
    lancer report --capital "$CAPITAL"
    if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi
else
    journal "panel absent ou vide : le rapport n'est pas écrit (lancer d'abord collecte-initiale.sh)."
    echecs=1
fi

if [ "$echecs" -ne 0 ]; then
    journal "tâche quotidienne : fin, avec au moins une étape en échec (voir plus haut)."
    exit 1
fi
journal "tâche quotidienne : fin, tout s'est bien passé."
