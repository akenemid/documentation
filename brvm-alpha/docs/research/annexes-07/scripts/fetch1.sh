#!/bin/bash
cd "$(dirname "$0")/pages"
UA="Mozilla/5.0 (research bot; polite crawl)"
while read name path; do
  [ -z "$name" ] && continue
  curl -s --max-time 40 -A "$UA" "https://www.brvm.org$path" -o "$name.html" -w "$name %{http_code} %{size_download}\n"
  sleep 10
done <<LIST
communiques /fr/emetteurs/type-annonces/communiques
convocations /fr/emetteurs/type-annonces/convocations-assemblees-generales
dirigeants /fr/emetteurs/type-annonces/changements-de-dirigeants
seuils /fr/emetteurs/type-annonces/franchissements-de-seuil
notations /fr/emetteurs/type-annonces/notations-financieres
resolutions /fr/emetteurs/type-annonces/projets-de-resolution
dividendes /fr/esv/paiement-de-dividendes
augcap /fr/esv/augmentation-de-capital
avis /fr/marche/avis-et-publications/avis
publications /fr/marche/avis-et-publications/publications
rapports /fr/rapports-societes-cotees
feed /fr/taxonomy/term/1/feed
actualites /fr/mediacentre/actualites
fractionnement /fr/esv/fractionnement
radiation /fr/esv/radiation
societes /fr/emetteurs/societes-cotees
LIST
echo DONE
