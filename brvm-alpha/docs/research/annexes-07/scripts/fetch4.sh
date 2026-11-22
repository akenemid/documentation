#!/bin/bash
D="$(dirname "$0")"
until grep -q DONE3 "$D/fetch3.log"; do sleep 15; done
cd "$D/pdf"
UA="Mozilla/5.0 (research bot; polite crawl)"
for u in "https://www.brvm.org/sites/default/files/20261009_-_avis_ndeg297_brvmdg_-_paiement_de_dividendes_exo_2025_-_agl_ci.pdf" \
         "https://www.brvm.org/sites/default/files/20261116_-_communique_de_presse_-_sogb_ci.pdf" \
         "https://www.brvm.org/sites/default/files/20261023_-_communique_-_annulation_ago_-_eti_tg.pdf"; do
  n=$(basename "$u"); curl -s --max-time 60 -A "$UA" "$u" -o "$n" -w "$n %{http_code} %{size_download}\n"; sleep 10; done
echo DONE4
