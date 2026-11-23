#!/bin/sh
# Installation HORS LIGNE de l'interpréteur du moteur embarqué (CPython 3.11 autonome) et de ses 16 roues.
# Pensé pour servir tel quel dans un RUN de Dockerfile (image Odoo) : aucun accès réseau, échec au moindre
# écart, jamais le code de sortie 3.
#
# Usage :  sh deploiement/installer-python-et-roues.sh [PREFIXE] DOSSIER CODE
#   PREFIXE  dossier d'installation (défaut : /opt/rz-brvm-alpha) : interpréteur dans PREFIXE/python,
#            roues installées dans PREFIXE/lib (variable BRVM_LIB pour un autre dossier)
#   DOSSIER  fichiers préparés par preparer-python-et-roues.sh : l'archive CPython et roues/*.whl
#   CODE     dossier du code embarqué (celui qui contient brvm_alpha/ et VERSION), qui reste à part, dans
#            le module Odoo
# Chemins absolus seulement.
#
# Étapes : (1) vérifie taille et sha256 de l'archive (deploiement/python-autonome.txt) et de chaque roue
# (deploiement/roues-py311-x86_64.tsv), exactement les 16 roues et rien d'autre, AVANT toute extraction ; (2) extrait
# l'archive dans PREFIXE/python ; (3) installe les roues avec pip --no-index --find-links --require-hashes
# --no-deps --target PREFIXE/lib (mandataire réseau volontairement invalide : tout accès réseau échouerait) ;
# (4) écrit dans le site-packages de l'interpréteur le fichier rz_brvm_alpha.pth, qui liste PREFIXE/lib et
# CODE (avec « python3 -I », PYTHONPATH est ignoré : c'est ce fichier qui rend brvm_alpha importable) ;
# (5) contrôle final, qui fait échouer l'installation s'il ne répond pas : imports des paquets, puis
# « PREFIXE/python/bin/python3.11 -I -B -m brvm_alpha etat --format json » en mode embarqué avec des
# dossiers de données et de rapports temporaires (créés avant) : code 0 ou 1 ET un objet JSON portant la clé
# « bandeau ».
#
# Codes de sortie (jamais 3) : 0 installé et vérifié ; 1 échec ; 2 mauvaise utilisation.
# Performance passée ≠ garantie. Aucun gain n'est garanti.
set -eu

echec() {
    printf 'échec : %s\n' "$*" >&2
    exit 1
}
usage() {
    printf '%s\n' "$*" >&2
    exit 2
}

case $# in
    2) PREFIXE=/opt/rz-brvm-alpha; DOSSIER=$1; CODE=$2 ;;
    3) PREFIXE=$1; DOSSIER=$2; CODE=$3 ;;
    *) usage "usage : sh deploiement/installer-python-et-roues.sh [PREFIXE] DOSSIER CODE" ;;
esac
LIB=${BRVM_LIB:-$PREFIXE/lib}
for valeur in "$PREFIXE" "$DOSSIER" "$CODE" "$LIB"; do
    case "$valeur" in
        /*) ;;
        *) usage "refusé : chemin relatif « $valeur » (PREFIXE, DOSSIER, CODE et BRVM_LIB sont absolus)." ;;
    esac
done
ICI=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REF_PY=$ICI/python-autonome.txt
REF_ROUES=$ICI/roues-py311-x86_64.tsv
for f in "$REF_PY" "$REF_ROUES"; do [ -f "$f" ] || echec "référence absente : $f"; done
[ -f "$CODE/brvm_alpha/__init__.py" ] || echec "CODE ($CODE) ne contient pas le paquet brvm_alpha."
if command -v sha256sum >/dev/null 2>&1; then
    empreinte() { sha256sum "$1" | cut -d ' ' -f 1; }
elif command -v shasum >/dev/null 2>&1; then
    empreinte() { shasum -a 256 "$1" | cut -d ' ' -f 1; }
else
    echec "ni sha256sum ni shasum : impossible de vérifier les empreintes."
fi
taille() { wc -c <"$1" | tr -d ' '; }
champ() { sed -n "s/^$1=//p" "$REF_PY" | head -n 1; }
ARCHIVE=$(champ archive)
OCTETS=$(champ octets)
SHA=$(champ sha256)
VERSION=$(champ version)
[ -n "$ARCHIVE" ] && [ -n "$OCTETS" ] && [ -n "$SHA" ] && [ -n "$VERSION" ] || echec "python-autonome.txt incomplet."

# 1. Vérifications, avant toute extraction ou installation.
[ -f "$DOSSIER/$ARCHIVE" ] || echec "archive absente : $DOSSIER/$ARCHIVE (lancer d'abord preparer-python-et-roues.sh)."
if [ "$(taille "$DOSSIER/$ARCHIVE")" != "$OCTETS" ] || [ "$(empreinte "$DOSSIER/$ARCHIVE")" != "$SHA" ]; then
    echec "archive $ARCHIVE : taille ou sha256 inattendu (attendu : $OCTETS octets, $SHA)."
fi
ROUES=$DOSSIER/roues
[ -d "$ROUES" ] || ROUES=$DOSSIER
attendues=$(grep -v '^#' "$REF_ROUES" | cut -f 1 | sort)
# Tout ce que contient le dossier des roues (fichiers cachés compris), pas seulement les *.whl : un fichier de
# plus (sdist, sitecustomize.py…) est refusé, même s'il serait sans effet (--only-binary, --require-hashes).
if [ "$ROUES" = "$DOSSIER" ]; then
    attendues=$(printf '%s\n%s\n' "$attendues" "$ARCHIVE" | sort)
fi
presentes=$(cd "$ROUES" && ls -1A | sort)
if [ "$attendues" != "$presentes" ]; then
    printf 'Fichiers attendus :\n%s\nFichiers présents :\n%s\n' "$attendues" "$presentes" >&2
    echec "$ROUES ne contient pas exactement les 16 roues de la liste de référence (et rien d'autre)."
fi
TMPREQ=$(mktemp)
CONTROLE=""
trap 'rm -f "$TMPREQ"; if [ -n "$CONTROLE" ]; then rm -rf "$CONTROLE"; fi' EXIT
grep -v '^#' "$REF_ROUES" | while IFS="$(printf '\t')" read -r roue octets sha; do
    [ -n "$roue" ] || continue
    if [ "$(taille "$ROUES/$roue")" != "$octets" ] || [ "$(empreinte "$ROUES/$roue")" != "$sha" ]; then
        echec "roue $roue : taille ou sha256 inattendu (attendu : $octets octets, $sha)."
    fi
    printf '%s==%s --hash=sha256:%s\n' "$(printf '%s' "$roue" | cut -d - -f 1)" \
        "$(printf '%s' "$roue" | cut -d - -f 2)" "$sha"
done >"$TMPREQ"
[ "$(wc -l <"$TMPREQ" | tr -d ' ')" -eq 16 ] || echec "vérification des roues interrompue."
printf 'Archive et 16 roues vérifiées (tailles et sha256).\n'

# 2. Interpréteur : extraction dans un dossier temporaire voisin, puis renommage (jamais d'installation à moitié).
[ ! -e "$PREFIXE/python" ] || echec "$PREFIXE/python existe déjà : retirer d'abord l'ancienne installation."
if [ -e "$LIB" ] && [ -n "$(ls -A "$LIB" 2>/dev/null)" ]; then
    echec "$LIB existe et n'est pas vide : retirer d'abord l'ancienne installation."
fi
mkdir -p "$PREFIXE"
EXTRAIT=$(mktemp -d "$PREFIXE/.python.XXXXXX")
tar -xzf "$DOSSIER/$ARCHIVE" -C "$EXTRAIT" || { rm -rf "$EXTRAIT"; echec "extraction de $ARCHIVE impossible."; }
[ -x "$EXTRAIT/python/bin/python3.11" ] || { rm -rf "$EXTRAIT"; echec "l'archive ne contient pas python/bin/python3.11."; }
mv -- "$EXTRAIT/python" "$PREFIXE/python"
rmdir -- "$EXTRAIT"
PY=$PREFIXE/python/bin/python3.11
"$PY" -I -c "import sys; v = '.'.join(map(str, sys.version_info[:3])); sys.exit(0 if v == '$VERSION' else 1)" \
    || echec "l'interpréteur extrait n'est pas CPython $VERSION."
printf 'Interpréteur extrait : %s (CPython %s).\n' "$PY" "$VERSION"

# 3. Roues, hors ligne strict : --no-index, dossier local seul, empreintes exigées, aucun mandataire valable.
mkdir -p "$LIB"
env PIP_CONFIG_FILE=/dev/null PIP_NO_INPUT=1 HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
    https_proxy=http://127.0.0.1:9 http_proxy=http://127.0.0.1:9 NO_PROXY= no_proxy= \
    "$PY" -I -m pip install --no-index --find-links "$ROUES" --require-hashes --no-deps --only-binary=:all: \
    --target "$LIB" --disable-pip-version-check --no-cache-dir --no-warn-script-location --root-user-action=ignore \
    -r "$TMPREQ" \
    || echec "installation hors ligne des roues impossible (pip)."

# 4. Fichier .pth dans le site-packages de l'interpréteur autonome : dossier des roues, puis dossier du code.
SITE=$("$PY" -I -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
[ -d "$SITE" ] || echec "site-packages introuvable : $SITE"
printf '%s\n%s\n' "$LIB" "$CODE" >"$SITE/rz_brvm_alpha.pth"
printf 'Fichier %s/rz_brvm_alpha.pth : %s et %s.\n' "$SITE" "$LIB" "$CODE"

# 5. Contrôle final : imports, puis « etat --format json » en mode embarqué (dossiers temporaires).
"$PY" -I -B -c "import pandas, numpy, scipy, pyarrow, yaml, requests, bs4, lxml, dateutil, certifi, idna, urllib3, \
charset_normalizer, soupsieve, typing_extensions, tzdata, brvm_alpha" || echec "un paquet ne s'importe pas."
CONTROLE=$(mktemp -d)
# Le moteur ne crée jamais ses dossiers en mode embarqué (code 8 s'ils manquent) : le module Odoo les crée.
mkdir "$CONTROLE/donnees" "$CONTROLE/rapports"
code=0
env -i PATH="$PATH" HOME="$CONTROLE" LANG=C.UTF-8 BRVM_ALPHA_EMBARQUE=1 BRVM_ALPHA_DONNEES="$CONTROLE/donnees" \
    BRVM_ALPHA_RAPPORTS="$CONTROLE/rapports" "$PY" -I -B -m brvm_alpha etat --format json \
    >"$CONTROLE/etat.json" 2>"$CONTROLE/etat.err" || code=$?
case "$code" in
    0|1) ;;
    *) cat "$CONTROLE/etat.err" >&2; echec "contrôle final : « etat --format json » est sorti avec le code $code." ;;
esac
"$PY" -I -B -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(0 if isinstance(d, dict) and "bandeau" in d else 1)' "$CONTROLE/etat.json" \
    || { cat "$CONTROLE/etat.err" >&2; echec "contrôle final : la sortie de « etat » n'est pas un objet JSON avec « bandeau »."; }
if ! command -v pdftotext >/dev/null 2>&1; then
    printf '%s\n' "Attention : pdftotext absent : installer poppler-utils (obligatoire en mode embarqué)." >&2
fi
printf 'Installation vérifiée : %s -I -B -m brvm_alpha etat --format json répond (code %s).\n' "$PY" "$code"
