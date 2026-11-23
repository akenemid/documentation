#!/bin/sh
# Première collecte de BRVM Alpha : télécharge tout l'historique des bulletins (BOC) depuis le
# 02/01/2017, puis construit le panel, collecte les notes et écrit un premier rapport.
#
# Usage :  sh collecte-initiale.sh [--simulation]
#   --simulation : n'envoie aucune requête et n'écrit aucune donnée ; dit ce qui serait fait.
#
# Durée : environ 11 heures de téléchargement (près de 4 000 requêtes, 10 s au moins entre deux),
# en une vingtaine de lancements de « update ». Le script peut être arrêté (Ctrl+C, signal TERM : la
# commande en cours reçoit TERM et s'arrête proprement) et relancé : il reprend où il en était, car
# « update » cherche tout jour manquant depuis le 02/01/2017. Il s'arrête de lui-même au premier refus
# du site, ou si un lancement n'avance plus. Aucun rapport sur un historique incomplet.
#
# Variables : voir commun.sh. En plus :
#   BRVM_MAX_REQUETES  requêtes au plus par lancement de « update » (défaut : 200)
#   BRVM_CAPITAL       capital du premier rapport, en FCFA (défaut : 10000000)
#
# Codes de sortie (jamais 3) : 0 collecte terminée ; 1 collecte incomplète ou étape en échec ;
# 2 mauvaise utilisation ; 4 une autre tâche tourne déjà ; 5 refus du site ; 8 configuration ;
# 130 ou 143 arrêt demandé.
# Performance passée ≠ garantie. Aucun gain n'est garanti.
set -eu
. "$(dirname -- "$0")/commun.sh"

SIMULATION=non
case "${1:-}" in
    --simulation) SIMULATION=oui ;;
    "") ;;
    *) brvm_echec "usage : sh collecte-initiale.sh [--simulation]" ;;
esac

QUOTA=${BRVM_MAX_REQUETES:-200}
CAPITAL=${BRVM_CAPITAL:-10000000}
brvm_entier BRVM_MAX_REQUETES "$QUOTA"
brvm_entier BRVM_CAPITAL "$CAPITAL"

brvm_init collecte-initiale
brvm_priorite_basse
brvm_verrou

DEBUT=2017-01-02   # premier jour de l'historique : celui que compte « etat »
TOLERANCE=3        # jours récents sans bulletin : le BOC du jour paraît le soir

# Nombre de jours ouvrés qui restent à chercher, lu dans « etat » (aucune requête).
jours_restants() {
    etat_releve
    restant=$(etat_champ bulletins.jours_a_telecharger_depuis_2017)
    case "$restant" in
        ''|*[!0-9]*) journal "échec : nombre de jours à chercher illisible."; exit 1 ;;
    esac
}

jours_restants
journal "première collecte : $restant jour(s) ouvré(s) à chercher depuis le $DEBUT."

if [ "$SIMULATION" = oui ]; then
    lancer update --from "$DEBUT" --simulation
    journal "simulation : aucune requête envoyée, aucune donnée écrite (seul ce journal est tenu)."
    journal "viendraient ensuite : update (répété), panel, notes research --pdf 20, report --capital $CAPITAL."
    exit 0
fi

# 1. Bulletins : on relance « update » tant qu'il reste des jours et que chaque lancement avance.
refus=non
while [ "$restant" -gt 0 ]; do
    avant=$restant
    lancer update --from "$DEBUT" --sans-panel --max-requetes "$QUOTA"
    jours_restants
    brvm_conclure_update
    case "$BRVM_CONCLUSION" in
        refus) refus=oui; break ;;
        usage) exit 2 ;;
        verrou) exit 4 ;;
        configuration) exit 8 ;;
        reseau|echec) journal "arrêt : la collecte reprendra au prochain lancement ($restant jour(s) restent)."
                      break ;;
    esac
    if [ "$restant" -ge "$avant" ]; then
        journal "arrêt : ce lancement n'a pas avancé ($restant jour(s) restent)."
        break
    fi
    journal "avancement : $restant jour(s) restent."
done

# 2. Panel : calcul local, sans réseau, dès qu'il y a des bulletins.
echecs=0
if [ "$(etat_champ bulletins.en_cache)" -gt 0 ]; then
    lancer panel
    if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi
else
    journal "aucun bulletin en cache : le panel n'est pas construit."
fi

if [ "$refus" = oui ]; then
    journal "fin : collecte interrompue par un refus du site ; $restant jour(s) restent. Ne pas insister :"
    journal "le blocage ne se lève qu'avec l'accord du site. Notes et rapport non lancés."
    exit 5
fi

# 3. Notes : collecte polie des publications, puis lecture de 20 documents au plus.
lancer notes research --pdf 20
if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi

# 4. Premier rapport, seulement si l'installation est prête (panel lisible ET historique complet).
etat_releve
if [ "$(etat_champ pret)" = true ]; then
    lancer report --capital "$CAPITAL"
    if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi
else
    journal "pas de rapport : installation pas prête ($(etat_champ raison)). Un rapport sur un historique"
    journal "incomplet aurait des chiffres faux ; relancer ce script plus tard."
    echecs=1
fi

if [ "$restant" -gt "$TOLERANCE" ]; then
    journal "fin : collecte incomplète, $restant jour(s) restent. Relancer ce script plus tard."
    exit 1
fi
if [ "$echecs" -ne 0 ]; then
    journal "fin : bulletins collectés, mais une étape a échoué (voir plus haut dans ce journal)."
    exit 1
fi
journal "fin : première collecte terminée ($restant jour(s) récent(s) encore sans bulletin)."
