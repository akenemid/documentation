# Ordre de bataille BRVM Alpha au 20/11/2026

> **Performance passée ≠ garantie. Aucun gain n'est garanti. Statut : REJETÉ.**

**Recommandation à titre d'étude ; suivi réel (paper trading) requis avant tout engagement d'argent réel.**

> ⚠ ACHAT BLOQUÉ par une note : ETIT (R2, annulation ou report d'AG : −1 en gouvernance, aucun achat (60 séances)) — note 4a46238f820f du 23/10/2026 « ETI TG : Communiqué - Annulation de l'Assemblée Générale Ordinaire », jusqu'au 19/01/2027. Effet : aucun achat (poids cible 6,16 % sans les notes, 0 % avec) ; ce poids est redistribué aux autres lignes par les règles de construction (voir le tableau d'effet). Pour lever le blocage : archiver la note (python -m brvm_alpha notes archive 4a46238f820f, ou bouton « Archiver » de sa fiche dans l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé.

> ⚠ Biais rétrospectif : poids actuels et sélection d'aujourd'hui (plus grosses capitalisations au 20/11/2026) appliqués à toute l'histoire 2017-2026 ; les titres alors en difficulté ou radiés n'y figurent pas, ce qui flatte la distribution. Lignes sans historique complet : ORAC (18,2 %, depuis le 06/01/2023), ECOC (5,1 %, depuis le 15/12/2017), BICB (2,7 %, depuis le 02/05/2025), NSBC (2,3 %, depuis le 27/10/2017), soit 28,4 % du portefeuille ; 790 valeur(s) antérieure(s) à la cotation : poids renormalisés sur les lignes cotées (et non comptées à 0 %). 0 valeur(s) manquante(s) après cotation (suspensions) comptée(s) à 0 %.

> ⚠ Résultat du test unique S1 (metrics.json, fait de simulation) : la variante appliquée REF fait −5,6 % par an contre le Composite TR (statut REJETÉ). La P(battre le TR) de la distribution à 12 mois est une fréquence historique aux poids actuels, pas une probabilité de surperformance future.

Décision à la clôture du BOC du 20/11/2026 ; exécution à partir du 23/11/2026. Capital 50 000 000 FCFA ; valeur du portefeuille avant ordres 50 000 000 FCFA, dont liquidités 50 000 000 FCFA.

Notes connues au 22/11/2026 16:02 UTC, appliquées à la séance du 23/11/2026 : 114 en vigueur (dont 0 manuelles), 6 filtre(s) de risque actif(s) ; achats bloqués : ETIT, SEMC, SICC.

## 1. Variante et statut de validation

- Variante retenue : **REF** — indice discipliné (D8) : 20 plus grosses capitalisations éligibles, annuel
- Motif : A est REJETÉ sur S1 : mode « indice discipliné » (§8.3, D8), aucune promesse d'alpha
- Statut de A sur S1 : REJETÉ ; registre : 20 essai(s) S1 au statut « exécuté »
- Variante en comparaison : aucune

## 2. Ordres (au titre et au franc près)

| Titre | Sens | Quantité | Détenus | Cible | Poids cible | Poids réalisé | Cours réf. | Bornes | Limite | Brut | Coûts | Net | Séances |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SNTS | ACHAT | 3 149 | 0 | 3 149 | 25,44 % | 25,44 % | 4 040 | 3 740 – 4 340 | 4 080 | 12 721 960 FCFA | 196 651 FCFA | 12 918 611 FCFA | 1 |
| ORAC | ACHAT | 474 | 0 | 474 | 18,27 % | 18,25 % | 19 250 | 17 810 – 20 690 | 19 440 | 9 124 500 FCFA | 191 080 FCFA | 9 315 580 FCFA | 2 |
| SGBC | ACHAT | 97 | 0 | 97 | 7,60 % | 7,53 % | 38 795 | 35 890 – 41 700 | 39 180 | 3 763 115 FCFA | 59 073 FCFA | 3 822 188 FCFA | 1 |
| CBIBF | ACHAT | 100 | 0 | 100 | 5,54 % | 5,50 % | 27 505 | 25 445 – 29 565 | 27 780 | 2 750 500 FCFA | 57 864 FCFA | 2 808 364 FCFA | 1 |
| SIBC | ACHAT | 314 | 0 | 314 | 5,16 % | 5,15 % | 8 200 | 7 585 – 8 815 | 8 280 | 2 574 800 FCFA | 46 504 FCFA | 2 621 304 FCFA | 1 |
| ECOC | ACHAT | 173 | 0 | 173 | 5,13 % | 5,12 % | 14 795 | 13 690 – 15 900 | 14 940 | 2 559 535 FCFA | 50 210 FCFA | 2 609 745 FCFA | 1 |
| SLBC | ACHAT | 51 | 0 | 51 | 4,20 % | 4,13 % | 40 500 | 37 465 – 43 535 | 40 905 | 2 065 500 FCFA | 44 449 FCFA | 2 109 949 FCFA | 2 |
| BICC | ACHAT | 52 | 0 | 52 | 3,25 % | 3,22 % | 31 000 | 28 675 – 33 325 | 31 310 | 1 612 000 FCFA | 33 494 FCFA | 1 645 494 FCFA | 2 |
| BOAC | ACHAT | 125 | 0 | 125 | 2,77 % | 2,75 % | 10 995 | 10 175 – 11 815 | 11 100 | 1 374 375 FCFA | 22 376 FCFA | 1 396 751 FCFA | 1 |
| BICB | ACHAT | 181 | 0 | 181 | 2,73 % | 2,71 % | 7 500 | 6 940 – 8 060 | 7 575 | 1 357 500 FCFA | 23 275 FCFA | 1 380 775 FCFA | 1 |
| STBC | ACHAT | 56 | 0 | 56 | 2,41 % | 2,39 % | 21 325 | 19 730 – 22 920 | 21 535 | 1 194 200 FCFA | 20 713 FCFA | 1 214 913 FCFA | 1 |
| NSBC | ACHAT | 77 | 0 | 77 | 2,34 % | 2,31 % | 15 000 | 13 875 – 16 125 | 15 150 | 1 155 000 FCFA | 18 813 FCFA | 1 173 813 FCFA | 1 |
| BOAB | ACHAT | 127 | 0 | 127 | 2,32 % | 2,31 % | 9 095 | 8 415 – 9 775 | 9 185 | 1 155 065 FCFA | 20 922 FCFA | 1 175 987 FCFA | 1 |
| BOABF | ACHAT | 138 | 0 | 138 | 2,13 % | 2,13 % | 7 700 | 7 125 – 8 275 | 7 775 | 1 062 600 FCFA | 19 758 FCFA | 1 082 358 FCFA | 1 |
| NTLC | ACHAT | 69 | 0 | 69 | 1,78 % | 1,77 % | 12 800 | 11 840 – 13 760 | 12 925 | 883 200 FCFA | 17 302 FCFA | 900 502 FCFA | 1 |
| BOAS | ACHAT | 113 | 0 | 113 | 1,75 % | 1,74 % | 7 700 | 7 125 – 8 275 | 7 775 | 870 100 FCFA | 13 639 FCFA | 883 739 FCFA | 1 |
| CIEC | ACHAT | 176 | 0 | 176 | 1,55 % | 1,55 % | 4 400 | 4 070 – 4 730 | 4 440 | 774 400 FCFA | 14 233 FCFA | 788 633 FCFA | 1 |
| SPHC | ACHAT | 80 | 0 | 80 | 1,23 % | 1,22 % | 7 645 | 7 075 – 8 215 | 7 720 | 611 600 FCFA | 11 886 FCFA | 623 486 FCFA | 1 |
| ONTBF | ACHAT | 214 | 0 | 214 | 1,20 % | 1,20 % | 2 805 | 2 595 – 3 015 | 2 830 | 600 270 FCFA | 12 817 FCFA | 613 087 FCFA | 1 |
| TTLC | ACHAT | 198 | 0 | 198 | 1,19 % | 1,18 % | 2 990 | 2 770 – 3 210 | 3 015 | 592 020 FCFA | 12 314 FCFA | 604 334 FCFA | 1 |

- ONTBF : coûts implicites plafonnés par le prix limite (écart limite − cours : l'ordre peut ne pas être servi)
- TTLC : coûts implicites plafonnés par le prix limite (écart limite − cours : l'ordre peut ne pas être servi)

### Achats bloqués par les notes de l'analyste et effet sur les poids

| Titre | Règle | Note | Blocage | Effet sur l'ordre | Pour lever le blocage |
|---|---|---|---|---|---|
| ETIT | R2 — annulation ou report d'AG : −1 en gouvernance, aucun achat (60 séances) | note 4a46238f820f du 23/10/2026 : « ETI TG : Communiqué - Annulation de l'Assemblée Générale Ordinaire » (source brvm_list, https://www.brvm.org/sites/default/files/20261023_-_communique_-_annulation_ago_-_eti_tg.pdf) | depuis le 26/10/2026, jusqu'au 19/01/2027 (encore 39 séance(s)) | aucun achat (poids cible 6,16 % sans les notes, 0 % avec) ; ce poids est redistribué aux autres lignes par les règles de construction (voir le tableau d'effet) | archiver la note (python -m brvm_alpha notes archive 4a46238f820f, ou bouton « Archiver » de sa fiche dans l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé |
| SEMC | R1 — suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances) | note e648d82ebd87 du 16/09/2026 : « SEMC : cotation suspendue (mention SP depuis le BOC du 16/09/2026) » (source boc, https://www.brvm.org/sites/default/files/boc_20260916_2.pdf) | depuis le 17/09/2026, jusqu'à la reprise de cotation + 5 séances | titre hors de la sélection : aucun effet sur cet ordre | archiver la note (python -m brvm_alpha notes archive e648d82ebd87, ou bouton « Archiver » de sa fiche dans l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé |
| SICC | R1 — suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances) | note 6771f0ac46eb du 16/09/2026 : « SICC : cotation suspendue (mention SP depuis le BOC du 16/09/2026) » (source boc, https://www.brvm.org/sites/default/files/boc_20260916_2.pdf) | depuis le 17/09/2026, jusqu'à la reprise de cotation + 5 séances | titre hors de la sélection : aucun effet sur cet ordre | archiver la note (python -m brvm_alpha notes archive 6771f0ac46eb, ou bouton « Archiver » de sa fiche dans l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé |

Effet des notes sur les poids cibles (même décision recalculée sans aucune note, pour information) : 21 ligne(s) modifiée(s) ; total investi cible 98,00 % sans les notes, 98,00 % avec : le poids retiré est redistribué aux autres lignes par les règles de construction existantes. Les notes ne changent aucune règle : elles retirent un titre des achats ou inclinent un score, dans les bornes de la spécification (indice discipliné : l'inclinaison n'entre pas dans la sélection par capitalisation).

| Titre | Poids cible sans les notes | Poids cible avec les notes | Écart | Motif |
|---|---|---|---|---|
| ETIT | 6,16 % | 0,00 % | −6,16 % | filtre R2 |
| ONTBF | 1,14 % | 1,20 % | +0,06 % | redistribution (construction) |
| SPHC | 1,17 % | 1,23 % | +0,06 % | redistribution (construction) |
| CIEC | 1,47 % | 1,55 % | +0,08 % | redistribution (construction) |
| BOAS | 1,66 % | 1,75 % | +0,09 % | redistribution (construction) |
| NTLC | 1,69 % | 1,78 % | +0,09 % | redistribution (construction) |
| BOABF | 2,02 % | 2,13 % | +0,11 % | redistribution (construction) |
| BOAB | 2,20 % | 2,32 % | +0,12 % | redistribution (construction) |
| NSBC | 2,22 % | 2,34 % | +0,12 % | redistribution (construction) |
| STBC | 2,29 % | 2,41 % | +0,12 % | redistribution (construction) |
| BICB | 2,59 % | 2,73 % | +0,14 % | redistribution (construction) |
| BOAC | 2,63 % | 2,77 % | +0,14 % | redistribution (construction) |
| BICC | 3,09 % | 3,25 % | +0,17 % | redistribution (construction) |
| SLBC | 3,98 % | 4,20 % | +0,22 % | redistribution (construction) |
| ECOC | 4,87 % | 5,13 % | +0,26 % | redistribution (construction) |
| SIBC | 4,90 % | 5,16 % | +0,27 % | redistribution (construction) |
| CBIBF | 5,26 % | 5,54 % | +0,28 % | redistribution (construction) |
| SGBC | 7,21 % | 7,60 % | +0,39 % | redistribution (construction) |
| ORAC | 17,33 % | 18,27 % | +0,94 % | redistribution (construction) |
| TTLC | 0,00 % | 1,19 % | +1,19 % | redistribution (construction) |
| SNTS | 24,14 % | 25,44 % | +1,31 % | redistribution (construction) |

### Coûts détaillés par ordre (estimation au cours de référence)

| Titre | Sens | Courtage | TVA | BRVM | DC/BR | Demi-spread | Impact | Total | Demi-spread % | Particip. max | Pire cas (provision) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SNTS | achat | 101 776 FCFA | 18 320 FCFA | 25 444 FCFA | 12 722 FCFA | 13 520 FCFA | 24 869 FCFA | 196 651 FCFA | 0,106 % | 1,5 % | 13 007 748 FCFA |
| ORAC | achat | 72 996 FCFA | 13 140 FCFA | 18 250 FCFA | 9 124 FCFA | 36 872 FCFA | 40 698 FCFA | 191 080 FCFA | 0,404 % | 7,8 % | 9 329 188 FCFA |
| SGBC | achat | 30 105 FCFA | 5 419 FCFA | 7 526 FCFA | 3 763 FCFA | 2 933 FCFA | 9 327 FCFA | 59 073 FCFA | 0,078 % | 2,4 % | 3 847 738 FCFA |
| CBIBF | achat | 22 004 FCFA | 3 961 FCFA | 5 501 FCFA | 2 751 FCFA | 10 047 FCFA | 13 600 FCFA | 57 864 FCFA | 0,365 % | 9,6 % | 2 812 558 FCFA |
| SIBC | achat | 20 598 FCFA | 3 708 FCFA | 5 150 FCFA | 2 575 FCFA | 6 940 FCFA | 7 533 FCFA | 46 504 FCFA | 0,270 % | 3,3 % | 2 632 263 FCFA |
| ECOC | achat | 20 476 FCFA | 3 686 FCFA | 5 119 FCFA | 2 560 FCFA | 7 239 FCFA | 11 130 FCFA | 50 210 FCFA | 0,283 % | 7,4 % | 2 616 773 FCFA |
| SLBC | achat | 16 524 FCFA | 2 974 FCFA | 4 131 FCFA | 2 066 FCFA | 9 786 FCFA | 8 968 FCFA | 44 449 FCFA | 0,474 % | 7,5 % | 2 112 107 FCFA |
| BICC | achat | 12 896 FCFA | 2 322 FCFA | 3 224 FCFA | 1 612 FCFA | 6 460 FCFA | 6 980 FCFA | 33 494 FCFA | 0,401 % | 7,3 % | 1 648 372 FCFA |
| BOAC | achat | 10 995 FCFA | 1 979 FCFA | 2 749 FCFA | 1 374 FCFA | 2 451 FCFA | 2 828 FCFA | 22 376 FCFA | 0,178 % | 1,7 % | 1 404 761 FCFA |
| BICB | achat | 10 860 FCFA | 1 955 FCFA | 2 715 FCFA | 1 358 FCFA | 2 760 FCFA | 3 627 FCFA | 23 275 FCFA | 0,203 % | 2,8 % | 1 388 131 FCFA |
| STBC | achat | 9 554 FCFA | 1 720 FCFA | 2 388 FCFA | 1 194 FCFA | 2 582 FCFA | 3 275 FCFA | 20 713 FCFA | 0,216 % | 2,9 % | 1 220 963 FCFA |
| NSBC | achat | 9 240 FCFA | 1 663 FCFA | 2 310 FCFA | 1 155 FCFA | 1 824 FCFA | 2 621 FCFA | 18 813 FCFA | 0,158 % | 2,0 % | 1 181 062 FCFA |
| BOAB | achat | 9 241 FCFA | 1 663 FCFA | 2 310 FCFA | 1 155 FCFA | 2 797 FCFA | 3 756 FCFA | 20 922 FCFA | 0,242 % | 4,1 % | 1 181 006 FCFA |
| BOABF | achat | 8 501 FCFA | 1 530 FCFA | 2 125 FCFA | 1 063 FCFA | 2 919 FCFA | 3 620 FCFA | 19 758 FCFA | 0,275 % | 4,5 % | 1 086 298 FCFA |
| NTLC | achat | 7 066 FCFA | 1 272 FCFA | 1 766 FCFA | 883 FCFA | 2 822 FCFA | 3 493 FCFA | 17 302 FCFA | 0,319 % | 6,1 % | 902 920 FCFA |
| BOAS | achat | 6 961 FCFA | 1 253 FCFA | 1 740 FCFA | 870 FCFA | 1 185 FCFA | 1 630 FCFA | 13 639 FCFA | 0,136 % | 1,4 % | 889 505 FCFA |
| CIEC | achat | 6 195 FCFA | 1 115 FCFA | 1 549 FCFA | 774 FCFA | 2 736 FCFA | 1 864 FCFA | 14 233 FCFA | 0,353 % | 2,3 % | 791 161 FCFA |
| SPHC | achat | 4 893 FCFA | 881 FCFA | 1 223 FCFA | 612 FCFA | 2 732 FCFA | 1 545 FCFA | 11 886 FCFA | 0,447 % | 2,5 % | 625 283 FCFA |
| ONTBF | achat | 4 802 FCFA | 864 FCFA | 1 201 FCFA | 600 FCFA | 3 440 FCFA | 1 910 FCFA | 12 817 FCFA | 0,642 % | 5,0 % | 613 154 FCFA |
| TTLC | achat | 4 736 FCFA | 852 FCFA | 1 184 FCFA | 592 FCFA | 2 895 FCFA | 2 055 FCFA | 12 314 FCFA | 0,535 % | 5,6 % | 604 397 FCFA |

- Achats : brut 48 802 240 FCFA, coûts 887 373 FCFA (explicites 607 104 FCFA, implicites estimés 280 269 FCFA), net 49 689 613 FCFA ; provision pire cas 49 895 388 FCFA
- Ventes : brut 0 FCFA, coûts 0 FCFA (explicites 0 FCFA, implicites estimés 0 FCFA), net 0 FCFA
- Coûts totaux du plan : 887 373 FCFA (1,77 % de la valeur du portefeuille)
- Frais fixes annuels estimés : garde 122 006 FCFA (0,25 % de l'encours) + tenue de compte 100 000 FCFA (20 lignes × 5 000 FCFA)
- Investi après ordres (au cours de référence) : 48 802 240 FCFA (97,60 %) pour une cible atteignable de 98,00 % (cible de la spécification : 98,00 %) ; reliquat de l'arrondi vers le bas 197 760 FCFA (reste en liquidités, §6) ; liquidités restantes estimées 310 387 FCFA (pire cas 104 612 FCFA)
- Scénario de coûts : central (courtage 0,80 % × (1 + TVA 18 %), BRVM 0,20 %, DC/BR 0,10 %, impact κ = 0,016)

### Messages du modèle (signalés)

- fenêtres comptées en séances (additif v1.1, D1) : 1 BOC manquants dans les 126 dernières séances ; seuils minimaux au prorata des BOC disponibles (planchers 40 / 20), bornes de rendement à 5 séances au plus
- modulateur du momentum : séries de performance des modulateurs (spread du momentum, TR de marché) restreintes à S0 (≥ 17/11/2022) : échantillon vierge S1 protégé ; validation_s1=True est réservé au test pré-enregistré
- notes de l'analyste prises en compte : 0 veto(s), 0 inclinaison(s), 6 titre(s) avec filtre R (mode direct : notes connues au 22/11/2026 16:02 UTC, appliquées à la séance du 23/11/2026)
- indice discipliné (additif v1.1, D8) : 20 plus grosses capitalisations éligibles, poids proportionnels à la capitalisation sous plafonds, 98,00 % investis (aucune promesse d'alpha)

## 3. Exécution : échéancier par séance

- 2 séance(s) du 23/11/2026 au 24/11/2026 ; participation ≤ 10 % de la MDV63 en valeur par séance
- Ventes d'abord ; règlement J+2 (depuis le 04/12/2025) : le produit d'une vente ne finance un achat qu'à partir de sa date de règlement ; liquidités initiales utilisées d'abord
- Prix limites : achat = min(borne haute ; dernier cours × 1,01) au pas inférieur ; vente = max(borne basse ; dernier cours × 0,99) au pas supérieur. Aucun achat si le titre cote à la borne haute, aucune vente à la borne basse : ordre reporté (au plus 10 séances, puis réévaluation)
- Jour ex et jour de division : la BRVM annule les ordres en attente ; les ressaisir le jour même
- Calendrier futur : jours ouvrés hors fériés à date fixe observés 2017-2026 (01/01, 01/05, 07/08, 15/08, 01/11, 15/11, 25/12) ; fêtes mobiles inconnues (hypothèse)

| Séance | Date | Titre | Sens | Titres | Limite | Montant réf. | Pire cas | Règlement | Financement |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 23/11/2026 | BICB | achat | 181 | 7 575 | 1 357 500 FCFA | 1 388 131 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | BICC | achat | 26 | 31 310 | 806 000 FCFA | 824 186 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | BOAB | achat | 127 | 9 185 | 1 155 065 FCFA | 1 181 006 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | BOABF | achat | 138 | 7 775 | 1 062 600 FCFA | 1 086 298 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | BOAC | achat | 125 | 11 100 | 1 374 375 FCFA | 1 404 761 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | BOAS | achat | 113 | 7 775 | 870 100 FCFA | 889 505 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | CBIBF | achat | 100 | 27 780 | 2 750 500 FCFA | 2 812 558 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | CIEC | achat | 176 | 4 440 | 774 400 FCFA | 791 161 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | ECOC | achat | 173 | 14 940 | 2 559 535 FCFA | 2 616 773 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | NSBC | achat | 77 | 15 150 | 1 155 000 FCFA | 1 181 062 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | NTLC | achat | 69 | 12 925 | 883 200 FCFA | 902 920 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | ONTBF | achat | 214 | 2 830 | 600 270 FCFA | 613 154 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | ORAC | achat | 237 | 19 440 | 4 562 250 FCFA | 4 664 594 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | SGBC | achat | 97 | 39 180 | 3 763 115 FCFA | 3 847 738 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | SIBC | achat | 314 | 8 280 | 2 574 800 FCFA | 2 632 263 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | SLBC | achat | 26 | 40 905 | 1 053 000 FCFA | 1 076 760 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | SNTS | achat | 3 149 | 4 080 | 12 721 960 FCFA | 13 007 748 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | SPHC | achat | 80 | 7 720 | 611 600 FCFA | 625 283 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | STBC | achat | 56 | 21 535 | 1 194 200 FCFA | 1 220 963 FCFA | 25/11/2026 | liquidités initiales |
| 1 | 23/11/2026 | TTLC | achat | 198 | 3 015 | 592 020 FCFA | 604 397 FCFA | 25/11/2026 | liquidités initiales |
| 2 | 24/11/2026 | BICC | achat | 26 | 31 310 | 806 000 FCFA | 824 186 FCFA | 26/11/2026 | liquidités initiales |
| 2 | 24/11/2026 | ORAC | achat | 237 | 19 440 | 4 562 250 FCFA | 4 664 594 FCFA | 26/11/2026 | liquidités initiales |
| 2 | 24/11/2026 | SLBC | achat | 25 | 40 905 | 1 012 500 FCFA | 1 035 347 FCFA | 26/11/2026 | liquidités initiales |

## 4. Revenus attendus : dividendes sur 12 mois (estimation)

| Titre | Titres | Date ex prévue | Paiement prévu | Dernier net/titre | IRVM | Brut | IRVM (FCFA) | Net | Statut |
|---|---|---|---|---|---|---|---|---|---|
| BOABF | 138 | 29/04/2027 | 03/05/2027 | 397,00 | 12,5 % | 62 613 FCFA | 7 827 FCFA | 54 786 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM 12,5 % [NON VÉRIFIÉ] |
| BOAC | 125 | 10/05/2027 | 12/05/2027 | 594,53 | 12,0 % | 84 450 FCFA | 10 134 FCFA | 74 316 FCFA | prévu (estimation : dernier dividende reconduit) |
| SNTS | 3 149 | 17/05/2027 | 19/05/2027 | 174,00 | 10,0 % | 608 807 FCFA | 60 881 FCFA | 547 926 FCFA | prévu (estimation : dernier dividende reconduit) |
| BOAB | 127 | 24/05/2027 | 26/05/2027 | 585,00 | 10,0 % | 82 550 FCFA | 8 255 FCFA | 74 295 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM selon l'émetteur (inférences) |
| ECOC | 173 | 24/05/2027 | 26/05/2027 | 781,44 | 12,0 % | 153 624 FCFA | 18 435 FCFA | 135 189 FCFA | prévu (estimation : dernier dividende reconduit) |
| BOAS | 113 | 31/05/2027 | 02/06/2027 | 450,00 | 10,0 % | 56 500 FCFA | 5 650 FCFA | 50 850 FCFA | prévu (estimation : dernier dividende reconduit) |
| ORAC | 474 | 07/06/2027 | 09/06/2027 | 704,00 | 12,0 % | 379 200 FCFA | 45 504 FCFA | 333 696 FCFA | prévu (estimation : dernier dividende reconduit) |
| ONTBF | 214 | 14/06/2027 | 16/06/2027 | 145,32 | 12,5 % | 35 541 FCFA | 4 443 FCFA | 31 098 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM 12,5 % [NON VÉRIFIÉ] |
| CBIBF | 100 | 05/07/2027 | 07/07/2027 | 900,00 | 12,5 % | 102 857 FCFA | 12 857 FCFA | 90 000 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM 12,5 % [NON VÉRIFIÉ] |
| NSBC | 77 | 05/07/2027 | 07/07/2027 | 675,98 | 12,0 % | 59 148 FCFA | 7 098 FCFA | 52 050 FCFA | prévu (estimation : dernier dividende reconduit) |
| BICC | 52 | 14/07/2027 | 16/07/2027 | 1 157,20 | 12,0 % | 68 380 FCFA | 8 206 FCFA | 60 174 FCFA | prévu (estimation : dernier dividende reconduit) |
| SGBC | 97 | 20/07/2027 | 22/07/2027 | 2 298,75 | 12,0 % | 253 385 FCFA | 30 406 FCFA | 222 979 FCFA | prévu (estimation : dernier dividende reconduit) |
| STBC | 56 | 22/07/2027 | 26/07/2027 | 1 707,20 | 12,0 % | 108 640 FCFA | 13 037 FCFA | 95 603 FCFA | prévu (estimation : dernier dividende reconduit) |
| CIEC | 176 | 23/07/2027 | 27/07/2027 | 205,92 | 12,0 % | 41 184 FCFA | 4 942 FCFA | 36 242 FCFA | prévu (estimation : dernier dividende reconduit) |
| SIBC | 314 | 29/07/2027 | 02/08/2027 | 374,00 | 12,0 % | 133 450 FCFA | 16 014 FCFA | 117 436 FCFA | prévu (estimation : dernier dividende reconduit) |
| SLBC | 51 | 29/07/2027 | 02/08/2027 | 1 871,76 | 12,0 % | 108 477 FCFA | 13 017 FCFA | 95 460 FCFA | prévu (estimation : dernier dividende reconduit) |
| BICB | 181 | 30/07/2027 | 02/08/2027 | 254,60 | 5,0 % | 48 508 FCFA | 2 425 FCFA | 46 083 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM selon l'émetteur (inférences) |
| SPHC | 80 | 09/08/2027 | 11/08/2027 | 430,32 | 12,0 % | 39 120 FCFA | 4 694 FCFA | 34 426 FCFA | prévu (estimation : dernier dividende reconduit) |
| NTLC | 69 | 13/08/2027 | 17/08/2027 | 369,60 | 12,0 % | 28 980 FCFA | 3 478 FCFA | 25 502 FCFA | prévu (estimation : dernier dividende reconduit) |
| TTLC | 198 | 21/09/2027 | 23/09/2027 | 139,77 | 12,0 % | 31 448 FCFA | 3 774 FCFA | 27 674 FCFA | prévu (estimation : dernier dividende reconduit) |

Revenu net attendu 2 205 785 FCFA (brut 2 486 862 FCFA, IRVM 281 077 FCFA) ; rendement net du portefeuille 4,41 % de la valeur (4,52 % de l'investi). Dernier dividende reconduit : hypothèse, pas une promesse ; un dividende n'est acquis que si les titres sont détenus la veille du détachement.

Valorisation du marché « cher » (prime du BOC 0,58 < 1 %) : les stress sont affichés en premier (§4.5) ; l'exposition ne change pas.

## 6. Scénarios de stress (§9.3)

Source : brvm_alpha.portfolio.stress.stress_tests.

| Code | Scénario | Perte | En % de la valeur | Hypothèse | Base |
|---|---|---|---|---|---|
| ST1 | marché baissier long : chemin du TR du 01/03/2017 au 26/10/2020 (−46,7 %) — TR | −21 739 902 FCFA | −43,5 % | β 104 semaines (hebdomadaire) 0,95, borné à 0,95, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) | [C-SPEC] §1.1 (fait mesuré) |
| ST1 | marché baissier long : Composite prix depuis fin 2015 (−59,8 % en 58 mois) — prix | −27 838 247 FCFA | −55,7 % | β 104 semaines (hebdomadaire) 0,95, borné à 0,95, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) ; dividendes non comptés | [R08] §4.3 |
| ST2 | pire année (2018 : TR reconstruit −25,1 %) — TR | −11 684 615 FCFA | −23,4 % | β 104 semaines (hebdomadaire) 0,95, borné à 0,95, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) | [C-SPEC] ; [R08] |
| ST2 | pire année (2018 : baisse intra-annuelle maximale du Composite −33,0 %) — intra-annuel | −15 362 243 FCFA | −30,7 % | β 104 semaines (hebdomadaire) 0,95, borné à 0,95, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) | [R08] |
| ST3 | correction rapide (−15 % en 8 semaines ; pire 8 semaines observé −14,3 %) | −6 982 838 FCFA | −14,0 % | β 104 semaines (hebdomadaire) 0,95, borné à 0,95, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) | [R04] §12.4 |
| ST4 | choc pays sévère AES (sanctions, gel BCEAO) : −21 % sur BF, ML, NE — sévère 21 % | −1 562 651 FCFA | −3,1 % | exposition λ AES 14,88 % du capital (siège ; filiales pour SNTS : ML 0,238) | §4.3 ; §11 macro.jump_loss ; [R05] §12 |
| ST4 | choc pays sévère AES : −26 % en 9 séances, dont 3 au plancher sans vendeur servi (rejeu Niger 2023) — stress 26 % (Niger 2023) | −1 934 711 FCFA | −3,9 % | exposition λ AES 14,88 % du capital (siège ; filiales pour SNTS : ML 0,238) ; aucune vente possible avant la 4ᵉ séance | [R05] §9 |
| ST4 | variante Mali 2022 : plancher dès t+1, −16,9 % en 3 séances sur ML — Mali 2022 | −511 703 FCFA | −1,0 % | exposition λ ML 6,06 % du capital | [R05] §9 |
| ST4 | coup d'État sans sanctions UEMOA : −8 % sur BF, ML, NE — modéré 8 % | −595 296 FCFA | −1,2 % | exposition λ AES 14,88 % du capital (siège ; filiales pour SNTS : ML 0,238) | §4.3 ; [R05] §12 |
| ST5 | stress souverain Sénégal : −9 % relatif en 60 séances (audit 2024) sur les titres sénégalais — relatif −9 % | −1 223 285 FCFA | −2,4 % | titres SN détenus : SNTS, BOAS (27,18 %) ; marché supposé stable | [R05] §9 |
| ST5 | stress souverain Sénégal : −26 % sur BOAS et SNTS — stress −26 % | −3 533 936 FCFA | −7,1 % | BOAS + SNTS : 27,18 % du capital (hypothèse de stress) | [R05] §9, §12 |
| ST6 | liquidité : participation divisée par 2 (5 %) et demi-spread × 2 pendant 20 séances (liquidation complète) | −1 032 953 FCFA | −2,1 % | coût de sortie 2,12 % de la valeur investie (normal, 10 % de participation : 2,01 %) ; non liquidable en 20 séances : 0 FCFA ; ligne la plus lente : SLBC (3,1 séances à 5 %) | hypothèse de conception ; §7.2 |
| ST7 | coûts : scénario sévère du §7.2 sur 12 mois (courtage 1,5 %, demi-spread × 2, κ = 0,05, garde 0,5 %, 10 000 FCFA par ligne) | −5 763 192 FCFA | −11,5 % | rotation 15 %/mois aller (objectif du §6, hypothèse) ; coûts centraux sur 12 mois : 3 108 757 FCFA ; surcoût du scénario sévère : 2 654 434 FCFA | §7.2 |
| ST8 | suspension de la plus grosse ligne (SNTS, 25,44 %) pendant 60 séances, valorisée −10 % — −10 % | −1 272 196 FCFA | −2,5 % | valorisation de risque (§7.1.7) | [R07] §4.7 |
| ST8 | suspension de la plus grosse ligne (SNTS) : valorisée −30 % (stress) — −30 % | −3 816 588 FCFA | −7,6 % | hypothèse de stress | [R07] §4.7 |
| ST9 | erreur de données : division non ajustée sur SNTS (faux −89,3 %) | 0 FCFA | 0,0 % | contrôle BLOQUANT vérifié (BrvmAlpha.risk_flags : data_guard (\|rendement\| > 50 %)) : signaux de SNTS bloqués ; perte apparente évitée 11 360 710 FCFA | [R08] §1 |
| ST10 | rupture de parité ou sortie de l'UEMOA : règle « sévère » sur les titres AES et les filiales de SNTS — sévère 21 % | −2 527 103 FCFA | −5,1 % | exposition 24,07 % du capital (AES ; SNTS : ML, GN, SL, GW) ; perte de change NON chiffrée (aucune source) | [R05] §7 |
| ST10 | rupture de parité ou sortie de l'UEMOA : règle « sévère » sur les titres AES et les filiales de SNTS — stress 26 % | −3 128 794 FCFA | −6,3 % | exposition 24,07 % du capital (AES ; SNTS : ML, GN, SL, GW) ; perte de change NON chiffrée (aucune source) | [R05] §7 |

## 5. Distribution historique à 12 mois (pas une prévision)

Bootstrap stationnaire (5 000 tirages, blocs moyens de 8 semaines, graine 0) des rendements hebdomadaires TR des lignes aux poids réalisés et du Composite TR, tirés ensemble ; fenêtre toute l'histoire 2017-2026 (le registre indique que le test unique S1 a été exécuté) (492 semaines, du 06/01/2017 au 20/11/2026). Nets des coûts du plan et des frais fixes de l'horizon (2,22 %). C'est une distribution historique, pas une prévision.

> ⚠ Biais rétrospectif : poids actuels et sélection d'aujourd'hui (plus grosses capitalisations au 20/11/2026) appliqués à toute l'histoire 2017-2026 ; les titres alors en difficulté ou radiés n'y figurent pas, ce qui flatte la distribution. Lignes sans historique complet : ORAC (18,2 %, depuis le 06/01/2023), ECOC (5,1 %, depuis le 15/12/2017), BICB (2,7 %, depuis le 02/05/2025), NSBC (2,3 %, depuis le 27/10/2017), soit 28,4 % du portefeuille ; 790 valeur(s) antérieure(s) à la cotation : poids renormalisés sur les lignes cotées (et non comptées à 0 %). 0 valeur(s) manquante(s) après cotation (suspensions) comptée(s) à 0 %.

> ⚠ Résultat du test unique S1 (metrics.json, fait de simulation) : la variante appliquée REF fait −5,6 % par an contre le Composite TR (statut REJETÉ). La P(battre le TR) de la distribution à 12 mois est une fréquence historique aux poids actuels, pas une probabilité de surperformance future.

| Mesure | Portefeuille (net) | Composite TR |
|---|---|---|
| Médiane | +12,7 % (56 355 971 FCFA) | +10,1 % |
| P10 | −9,4 % (45 314 701 FCFA) | −10,9 % |
| P90 | +39,1 % (69 548 226 FCFA) | +35,4 % |
| P(perte) | 24,4 % | — |
| P(battre le TR) | 69,3 % (fréquence historique aux poids actuels) | test S1 : REF −5,6 %/an contre le TR (REJETÉ) |
| Rendement des dividendes (net) | 4,41 % | inclus dans le TR |
| Rendement annualisé du TR sur la fenêtre (fait) | — (poids actuels : biais rétrospectif) | +10,2 % |
| Volatilité annualisée (hebdo) | 11,9 % | 11,6 % |
| β hebdomadaire contre le TR (06/01/2017 → 20/11/2026) | 0,95 | 1 |

## 7. Déclencheurs de revue

- Prochaine revue mensuelle (dernière séance du mois) : 30/11/2026
- Rebalancement annuel de l'indice discipliné (première décision de janvier) : 29/01/2027 ; entre deux, seules les sorties forcées s'appliquent
- Début du suivi réel S2 (§8.1) : 01/12/2026
- Filtres R actifs sur les lignes : NSBC (R10); BOAB (R11×1); BOABF (R11×1); TTLC (R12)
- Drawdown relatif contre le TR : aucun historique de suivi réel (mesuré depuis le premier jour investi, D5) ; seuils à surveiller : −10 % alerte, −15 % exposition active ÷ 2, −20 % arrêt et indice discipliné
- Notes de l'analyste : 0 veto(s), 0 inclinaison(s), 6 titre(s) avec filtre R issu des notes
- Notes connues au 22/11/2026 16:02 UTC, appliquées à la séance du 23/11/2026 : 114 en vigueur (dont 0 manuelles), 6 filtre(s) de risque actif(s) ; achats bloqués : ETIT, SEMC, SICC.
- Scores des notes : 42 note(s) en vigueur sur 114 portent un score directionnel non nul.
- Filtre R2 sur ETIT (annulation ou report d'AG : −1 en gouvernance, aucun achat (60 séances)) depuis le 26/10/2026, jusqu'au 19/01/2027 — note 4a46238f820f du 23/10/2026 « ETI TG : Communiqué - Annulation de l'Assemblée Générale Ordinaire » ; achats bloqués ; titre hors du plan
- Filtre R10 sur NSBC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 03/11/2026, jusqu'au 21/04/2027 — note a7b94e0c53cd du 02/11/2026 « NSIA BANQUE CI : Rapport d'activités - 3e trimestre 2026 »
- Filtre R10 sur PALC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 09/10/2026, jusqu'au 29/03/2027 — note 9b1cd08a8448 du 08/10/2026 « PALM CI : Rapport d'activités - 1er semestre 2026 » ; titre hors du plan
- Filtre R1 sur SEMC (suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances)) depuis le 17/09/2026, jusqu'à la reprise de cotation + 5 séances — note e648d82ebd87 du 16/09/2026 « SEMC : cotation suspendue (mention SP depuis le BOC du 16/09/2026) » ; achats bloqués ; titre hors du plan
- Filtre R1 sur SICC (suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances)) depuis le 17/09/2026, jusqu'à la reprise de cotation + 5 séances — note 6771f0ac46eb du 16/09/2026 « SICC : cotation suspendue (mention SP depuis le BOC du 16/09/2026) » ; achats bloqués ; titre hors du plan
- Filtre R10 sur SOGC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 03/11/2026, jusqu'au 21/04/2027 — note 67f51ea73342 du 02/11/2026 « SOGB CI : Rapport d'activités - 3e trimestre 2026 » ; titre hors du plan
- Règles pays actives : aucune ; aucun événement pays daté à venir dans reference.COUNTRY_EVENTS (horizon 12 mois)

### Événements à venir (12 mois)

| Date | Type | Cible | Description | Nature |
|---|---|---|---|---|
| 01/12/2026 | suivi réel | plate-forme | début du suivi réel S2 (paper trading, §8.1) | fait (protocole) |
| 04/01/2027 | révision du BRVM 30 | IDX:BRVM-30 | révision trimestrielle de la composition (information seulement, §5.5) | fait (calendrier ; date de séance estimée) |
| 01/02/2027 | publication attendue | CIEC | activité du T3 (dernière connue : 01/02/2024, + 3 an(s)) | estimation (historique des notes) |
| 17/02/2027 | publication attendue | SNTS | comptes annuels (dernière connue : 17/02/2026, + 1 an(s)) | estimation (historique des notes) |
| 18/03/2027 | AGO estimée | BOABF | date ex − 42 jours (médiane §5.4) | estimation |
| 18/03/2027 | publication attendue | BOAS | comptes annuels (dernière connue : 18/03/2026, + 1 an(s)) | estimation (historique des notes) |
| 19/03/2027 | publication attendue | SPHC | comptes annuels (dernière connue : 19/03/2026, + 1 an(s)) | estimation (historique des notes) |
| 24/03/2027 | publication attendue | BOABF | comptes annuels (dernière connue : 24/03/2026, + 1 an(s)) | estimation (historique des notes) |
| 29/03/2027 | AGO estimée | BOAC | date ex − 42 jours (médiane §5.4) | estimation |
| 01/04/2027 | révision du BRVM 30 | IDX:BRVM-30 | révision trimestrielle de la composition (information seulement, §5.5) | fait (calendrier ; date de séance estimée) |
| 05/04/2027 | AGO estimée | SNTS | date ex − 42 jours (médiane §5.4) | estimation |
| 12/04/2027 | AGO estimée | BOAB | date ex − 42 jours (médiane §5.4) | estimation |
| 12/04/2027 | AGO estimée | ECOC | date ex − 42 jours (médiane §5.4) | estimation |
| 15/04/2027 | publication attendue | ECOC | comptes annuels (dernière connue : 15/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 16/04/2027 | publication attendue | BOAB | comptes annuels (dernière connue : 16/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 17/04/2027 | publication attendue | SGBC | comptes annuels (dernière connue : 17/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 19/04/2027 | AGO estimée | BOAS | date ex − 42 jours (médiane §5.4) | estimation |
| 20/04/2027 | publication attendue | BICC | comptes annuels (dernière connue : 20/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 20/04/2027 | publication attendue | SNTS | activité du T1 (dernière connue : 20/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 22/04/2027 | publication attendue | SIBC | comptes annuels (dernière connue : 22/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 23/04/2027 | publication attendue | BOAS | activité du T1 (dernière connue : 23/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 23/04/2027 | publication attendue | TTLC | activité du T1 (dernière connue : 23/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 26/04/2027 | AGO estimée | ORAC | date ex − 42 jours (médiane §5.4) | estimation |
| 29/04/2027 | détachement prévu | BOABF | 397,00 FCFA net/titre, soit 54 786 FCFA payés vers le 03/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 30/04/2027 | publication attendue | ECOC | activité du T1 (dernière connue : 30/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/04/2027 | publication attendue | SPHC | activité du T1 (dernière connue : 30/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/04/2027 | échéance de publication | toutes les lignes | comptes annuels de l'exercice précédent et activité du T1 (échéance R7) ; alerte orange le lendemain, rouge à +61 jours | fait (règle R7) |
| 02/05/2027 | publication attendue | CIEC | activité du T1 (dernière connue : 02/05/2024, + 3 an(s)) | estimation (historique des notes) |
| 03/05/2027 | AGO estimée | ONTBF | date ex − 42 jours (médiane §5.4) | estimation |
| 04/05/2027 | publication attendue | BICC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | BOABF | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | CBIBF | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | NSBC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | NTLC | comptes annuels (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | NTLC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | ONTBF | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | ORAC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | SGBC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | SLBC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | STBC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 05/05/2027 | publication attendue | BOAB | activité du T1 (dernière connue : 05/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 07/05/2027 | publication attendue | SIBC | activité du T1 (dernière connue : 07/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 10/05/2027 | détachement prévu | BOAC | 594,53 FCFA net/titre, soit 74 316 FCFA payés vers le 12/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 15/05/2027 | publication attendue | NSBC | comptes annuels (dernière connue : 15/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 17/05/2027 | détachement prévu | SNTS | 174,00 FCFA net/titre, soit 547 926 FCFA payés vers le 19/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 20/05/2027 | publication attendue | SLBC | comptes annuels (dernière connue : 20/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 21/05/2027 | publication attendue | CIEC | comptes annuels (dernière connue : 21/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 24/05/2027 | AGO estimée | CBIBF | date ex − 42 jours (médiane §5.4) | estimation |
| 24/05/2027 | AGO estimée | NSBC | date ex − 42 jours (médiane §5.4) | estimation |
| 24/05/2027 | détachement prévu | BOAB | 585,00 FCFA net/titre, soit 74 295 FCFA payés vers le 26/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 24/05/2027 | détachement prévu | ECOC | 781,44 FCFA net/titre, soit 135 189 FCFA payés vers le 26/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 31/05/2027 | détachement prévu | BOAS | 450,00 FCFA net/titre, soit 50 850 FCFA payés vers le 02/06/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 02/06/2027 | AGO estimée | BICC | date ex − 42 jours (médiane §5.4) | estimation |
| 02/06/2027 | publication attendue | BOAC | activité du T1 (dernière connue : 02/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/06/2027 | publication attendue | TTLC | comptes annuels (dernière connue : 02/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 07/06/2027 | détachement prévu | ORAC | 704,00 FCFA net/titre, soit 333 696 FCFA payés vers le 09/06/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 08/06/2027 | AGO estimée | SGBC | date ex − 42 jours (médiane §5.4) | estimation |
| 09/06/2027 | publication attendue | ORAC | comptes annuels (dernière connue : 09/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 10/06/2027 | AGO estimée | STBC | date ex − 42 jours (médiane §5.4) | estimation |
| 11/06/2027 | AGO estimée | CIEC | date ex − 42 jours (médiane §5.4) | estimation |
| 12/06/2027 | publication attendue | ONTBF | comptes annuels (dernière connue : 12/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 14/06/2027 | détachement prévu | ONTBF | 145,32 FCFA net/titre, soit 31 098 FCFA payés vers le 16/06/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 15/06/2027 | publication attendue | BOAC | comptes annuels (dernière connue : 15/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 17/06/2027 | AGO estimée | SIBC | date ex − 42 jours (médiane §5.4) | estimation |
| 17/06/2027 | AGO estimée | SLBC | date ex − 42 jours (médiane §5.4) | estimation |
| 18/06/2027 | AGO estimée | BICB | date ex − 42 jours (médiane §5.4) | estimation |
| 22/06/2027 | publication attendue | BICB | comptes annuels (dernière connue : 22/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 26/06/2027 | publication attendue | STBC | convocation d'AG (dernière connue : 26/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 28/06/2027 | AGO estimée | SPHC | date ex − 42 jours (médiane §5.4) | estimation |
| 01/07/2027 | révision du BRVM 30 | IDX:BRVM-30 | révision trimestrielle de la composition (information seulement, §5.5) | fait (calendrier ; date de séance estimée) |
| 02/07/2027 | AGO estimée | NTLC | date ex − 42 jours (médiane §5.4) | estimation |
| 05/07/2027 | détachement prévu | CBIBF | 900,00 FCFA net/titre, soit 90 000 FCFA payés vers le 07/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 05/07/2027 | détachement prévu | NSBC | 675,98 FCFA net/titre, soit 52 050 FCFA payés vers le 07/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 08/07/2027 | publication attendue | CBIBF | comptes annuels (dernière connue : 08/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 14/07/2027 | détachement prévu | BICC | 1 157,20 FCFA net/titre, soit 60 174 FCFA payés vers le 16/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 16/07/2027 | publication attendue | STBC | comptes annuels (dernière connue : 16/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 20/07/2027 | détachement prévu | SGBC | 2 298,75 FCFA net/titre, soit 222 979 FCFA payés vers le 22/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 22/07/2027 | détachement prévu | STBC | 1 707,20 FCFA net/titre, soit 95 603 FCFA payés vers le 26/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 23/07/2027 | détachement prévu | CIEC | 205,92 FCFA net/titre, soit 36 242 FCFA payés vers le 27/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 23/07/2027 | publication attendue | BICB | activité du T1 (dernière connue : 23/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 24/07/2027 | publication attendue | BOAB | comptes semestriels (dernière connue : 24/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 27/07/2027 | publication attendue | SNTS | comptes semestriels (dernière connue : 27/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 29/07/2027 | détachement prévu | SIBC | 374,00 FCFA net/titre, soit 117 436 FCFA payés vers le 02/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 29/07/2027 | détachement prévu | SLBC | 1 871,76 FCFA net/titre, soit 95 460 FCFA payés vers le 02/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 30/07/2027 | détachement prévu | BICB | 254,60 FCFA net/titre, soit 46 083 FCFA payés vers le 02/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 06/08/2027 | publication attendue | BOABF | comptes semestriels (dernière connue : 06/08/2026, + 1 an(s)) | estimation (historique des notes) |
| 09/08/2027 | détachement prévu | SPHC | 430,32 FCFA net/titre, soit 34 426 FCFA payés vers le 11/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 10/08/2027 | AGO estimée | TTLC | date ex − 42 jours (médiane §5.4) | estimation |
| 13/08/2027 | détachement prévu | NTLC | 369,60 FCFA net/titre, soit 25 502 FCFA payés vers le 17/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 01/09/2027 | publication attendue | CBIBF | comptes semestriels (dernière connue : 01/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 01/09/2027 | publication attendue | SGBC | comptes semestriels (dernière connue : 01/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 10/09/2027 | publication attendue | ECOC | comptes semestriels (dernière connue : 10/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 18/09/2027 | publication attendue | SNTS | convocation d'AG (dernière connue : 18/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 21/09/2027 | détachement prévu | TTLC | 139,77 FCFA net/titre, soit 27 674 FCFA payés vers le 23/09/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 22/09/2027 | publication attendue | BICB | comptes semestriels (dernière connue : 22/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 22/09/2027 | publication attendue | BOAS | comptes semestriels (dernière connue : 22/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 29/09/2027 | publication attendue | SIBC | comptes semestriels (dernière connue : 29/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 01/10/2027 | révision du BRVM 30 | IDX:BRVM-30 | révision trimestrielle de la composition (information seulement, §5.5) | fait (calendrier ; date de séance estimée) |
| 02/10/2027 | publication attendue | BOAC | comptes semestriels (dernière connue : 02/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/10/2027 | publication attendue | ONTBF | comptes semestriels (dernière connue : 02/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 06/10/2027 | publication attendue | SPHC | comptes semestriels (dernière connue : 06/10/2025, + 2 an(s)) | estimation (historique des notes) |
| 09/10/2027 | publication attendue | ORAC | comptes semestriels (dernière connue : 09/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 14/10/2027 | publication attendue | BICC | comptes semestriels (dernière connue : 14/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 14/10/2027 | publication attendue | SPHC | activité du T3 (dernière connue : 14/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 22/10/2027 | publication attendue | BOAS | activité du T3 (dernière connue : 22/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 23/10/2027 | publication attendue | NTLC | comptes semestriels (dernière connue : 23/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 23/10/2027 | publication attendue | NTLC | activité du T3 (dernière connue : 23/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 26/10/2027 | publication attendue | NSBC | comptes semestriels (dernière connue : 26/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 26/10/2027 | publication attendue | ONTBF | activité du T3 (dernière connue : 26/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 27/10/2027 | publication attendue | BOABF | activité du T3 (dernière connue : 27/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 28/10/2027 | publication attendue | ECOC | activité du T3 (dernière connue : 28/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 28/10/2027 | publication attendue | TTLC | comptes semestriels (dernière connue : 28/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 28/10/2027 | publication attendue | TTLC | activité du T3 (dernière connue : 28/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 29/10/2027 | publication attendue | ORAC | activité du T3 (dernière connue : 29/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/10/2027 | publication attendue | CBIBF | activité du T3 (dernière connue : 30/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/10/2027 | publication attendue | CIEC | comptes semestriels (dernière connue : 30/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/10/2027 | publication attendue | SNTS | activité du T3 (dernière connue : 30/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 31/10/2027 | échéance de publication | toutes les lignes | comptes semestriels et activité du T3 (échéance R7) ; alerte orange le lendemain, rouge à +61 jours | fait (règle R7) |
| 02/11/2027 | publication attendue | BICC | activité du T3 (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | NSBC | activité du T3 (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | SGBC | activité du T3 (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | SLBC | comptes semestriels (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | STBC | comptes semestriels (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | STBC | activité du T3 (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 03/11/2027 | publication attendue | BOAB | activité du T3 (dernière connue : 03/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 03/11/2027 | publication attendue | BOAC | activité du T3 (dernière connue : 03/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 03/11/2027 | publication attendue | SIBC | activité du T3 (dernière connue : 03/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 10/11/2027 | publication attendue | BICB | activité du T3 (dernière connue : 10/11/2026, + 1 an(s)) | estimation (historique des notes) |

### Évaluation des indices (notes.index_eval, information)

| Indice | Position | Confiance | Score | Lecture |
|---|---|---|---|---|
| BRVM Composite | NEUTRE (sans les notes : SOUS-PONDÉRER) | 0,51 | −0,44 | Score composite −0,44 (tendance −0,42 × 0,30 ; valorisation −0,97 × 0,25 ; largeur −1,56 × 0,15 ; régime +1,00 × 0,15 ; notes +0,09 × 0,15) → NEUTRE (penche à la baisse) (seuils ±0,5) ; confiance 0,51 (accord des composantes avec la position 0,43, marge au seuil 0,06, couverture 1,00, qualité des données 1,00). Effet des notes : sans la composante notes, le score composite serait −0,53 (SOUS-PONDÉRER) ; avec elle, −0,44 (NEUTRE) : la position change à cause de cette composante (elle pèse 15 % du score dès qu'une note porte un score, même faible). |
| BRVM Composite Total Return | NEUTRE (sans les notes : SOUS-PONDÉRER) | 0,45 | −0,44 | Score composite −0,44 (tendance −0,43 × 0,30 ; valorisation −0,97 × 0,25 ; largeur −1,56 × 0,15 ; régime +1,00 × 0,15 ; notes +0,09 × 0,15) → NEUTRE (penche à la baisse) (seuils ±0,5) ; confiance 0,45 (accord des composantes avec la position 0,42, marge au seuil 0,06, couverture 1,00, qualité des données 0,90). Effet des notes : sans la composante notes, le score composite serait −0,54 (SOUS-PONDÉRER) ; avec elle, −0,44 (NEUTRE) : la position change à cause de cette composante (elle pèse 15 % du score dès qu'une note porte un score, même faible). |
| BRVM 30 | SOUS-PONDÉRER | 0,76 | −0,71 | Score composite −0,71 (tendance −0,20 × 0,30 ; valorisation −2,42 × 0,25 ; largeur −1,37 × 0,15 ; régime +1,00 × 0,15 ; notes +0,09 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,76 (accord des composantes avec la position 0,84, marge au seuil 0,21, couverture 1,00, qualité des données 1,00). |
| BRVM Prestige | SOUS-PONDÉRER | 0,68 | −0,59 | Score composite −0,59 (tendance −0,37 × 0,30 ; valorisation −1,88 × 0,25 ; largeur −1,22 × 0,15 ; régime +1,00 × 0,15 ; notes +0,15 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,68 (accord des composantes avec la position 0,82, marge au seuil 0,09, couverture 1,00, qualité des données 1,00). |
| BRVM Principal | SOUS-PONDÉRER | 0,95 | −1,03 | Score composite −1,03 (tendance −1,37 × 0,30 ; valorisation −2,07 × 0,25 ; largeur −1,67 × 0,15 ; régime +1,00 × 0,15 ; notes +0,02 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,95 (accord des composantes avec la position 0,89, marge au seuil 0,53, couverture 1,00, qualité des données 1,00). |
| sectoriel Services financiers | SOUS-PONDÉRER | 0,73 | −0,77 | Score composite −0,77 (tendance −0,36 × 0,30 ; valorisation −2,28 × 0,25 ; largeur −1,66 × 0,15 ; régime +1,00 × 0,15 ; notes +0,05 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,73 (accord des composantes avec la position 0,86, marge au seuil 0,27, couverture 1,00, qualité des données 0,90). |
| sectoriel Télécommunications | NEUTRE | 0,80 | −0,19 | Score composite −0,19 (tendance +1,07 × 0,30 ; valorisation −2,39 × 0,25 ; largeur −0,63 × 0,15 ; régime +1,00 × 0,15 ; notes +0,22 × 0,15) → NEUTRE (seuils ±0,5) ; confiance 0,80 (accord des composantes avec la position 0,84, marge au seuil 0,31, couverture 1,00, qualité des données 0,97). |
| sectoriel Consommation de base | SOUS-PONDÉRER | 0,78 | −0,67 | Score composite −0,67 (tendance −1,62 × 0,30 ; valorisation −0,24 × 0,25 ; largeur −0,72 × 0,15 ; régime +0,00 × 0,15 ; notes −0,09 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,78 (accord des composantes avec la position 1,00, marge au seuil 0,17, couverture 1,00, qualité des données 0,97). |
| sectoriel Consommation discrétionnaire | SOUS-PONDÉRER | 0,95 | −1,29 | Score composite −1,29 (tendance −2,31 × 0,30 ; valorisation −0,50 × 0,25 ; largeur −1,30 × 0,15 ; régime −2,00 × 0,15 ; notes +0,16 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,95 (accord des composantes avec la position 0,98, marge au seuil 0,79, couverture 1,00, qualité des données 0,97). |
| sectoriel Énergie | SOUS-PONDÉRER | 0,68 | −0,62 | Score composite −0,62 (tendance −0,69 × 0,30 ; valorisation −2,25 × 0,25 ; largeur −0,13 × 0,15 ; régime +1,00 × 0,15 ; notes +0,14 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,68 (accord des composantes avec la position 0,82, marge au seuil 0,12, couverture 1,00, qualité des données 0,97). |
| sectoriel Industriels | SOUS-PONDÉRER | 0,90 | −1,28 | Score composite −1,28 (tendance −0,31 × 0,30 ; valorisation −2,91 × 0,25 ; largeur −0,93 × 0,15 ; régime −2,00 × 0,15 ; notes −0,14 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,90 (accord des composantes avec la position 1,00, marge au seuil 0,78, couverture 1,00, qualité des données 0,90). |
| sectoriel Services publics | SOUS-PONDÉRER | 0,71 | −1,19 | Score composite −1,19 (tendance −0,30 × 0,30 ; valorisation −2,82 × 0,25 ; largeur −0,85 × 0,15 ; régime −2,00 × 0,15 ; notes +0,22 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,71 (accord des composantes avec la position 0,97, marge au seuil 0,69, couverture 1,00, qualité des données 0,72). |

Position fragile : BRVM Composite, BRVM Composite Total Return — la position ne change que par le poids donné à la composante « notes » dans le score (voir « Effet des notes » dans la lecture), pas par un signal fort des notes. À lire avec la position « sans les notes ».

## 8. Explications (titres retenus et 5 premiers écartés)

| Titre | Statut | Rang | Poids | Explication |
|---|---|---|---|---|
| SNTS | retenu | 1 | 25,44 % | plafond de ligne max(10 % × 0,85 ; min(30 % ; 1,25 × b_i = 26,12 %)) = 26,12 % ; indice discipliné : capitalisation n° 1 parmi les éligibles |
| ORAC | retenu | 2 | 18,27 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 18,75 %)) = 18,75 % ; indice discipliné : capitalisation n° 2 parmi les éligibles |
| SGBC | retenu | 3 | 7,60 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 7,80 %)) = 10,00 % ; indice discipliné : capitalisation n° 3 parmi les éligibles |
| CBIBF | retenu | 5 | 5,54 % | plafond de ligne max(10 % × 0,75 ; min(30 % ; 1,25 × b_i = 5,69 %)) = 7,50 % ; indice discipliné : capitalisation n° 4 parmi les éligibles |
| SIBC | retenu | 6 | 5,16 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 5,30 %)) = 10,00 % ; indice discipliné : capitalisation n° 5 parmi les éligibles |
| ECOC | retenu | 7 | 5,13 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 5,27 %)) = 10,00 % ; indice discipliné : capitalisation n° 6 parmi les éligibles |
| SLBC | retenu | 8 | 4,20 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 4,31 %)) = 10,00 % ; indice discipliné : capitalisation n° 7 parmi les éligibles |
| BICC | retenu | 9 | 3,25 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 3,34 %)) = 10,00 % ; indice discipliné : capitalisation n° 8 parmi les éligibles |
| BOAC | retenu | 10 | 2,77 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,84 %)) = 10,00 % ; indice discipliné : capitalisation n° 9 parmi les éligibles |
| BICB | retenu | 11 | 2,73 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,80 %)) = 10,00 % ; indice discipliné : capitalisation n° 10 parmi les éligibles |
| STBC | retenu | 12 | 2,41 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,48 %)) = 10,00 % ; indice discipliné : capitalisation n° 11 parmi les éligibles |
| NSBC | retenu | 13 | 2,34 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,40 %)) = 10,00 % ; indice discipliné : capitalisation n° 12 parmi les éligibles ; filtres : R10 |
| BOAB | retenu | 14 | 2,32 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,39 %)) = 10,00 % × 0,5 (R11×1) = 5,00 % ; indice discipliné : capitalisation n° 13 parmi les éligibles ; filtres : R11×1 |
| BOABF | retenu | 15 | 2,13 % | plafond de ligne max(10 % × 0,75 ; min(30 % ; 1,25 × b_i = 2,19 %)) = 7,50 % × 0,5 (R11×1) = 3,75 % ; indice discipliné : capitalisation n° 14 parmi les éligibles ; filtres : R11×1 |
| NTLC | retenu | 16 | 1,78 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 1,83 %)) = 10,00 % ; indice discipliné : capitalisation n° 15 parmi les éligibles |
| BOAS | retenu | 17 | 1,75 % | plafond de ligne max(10 % × 0,85 ; min(30 % ; 1,25 × b_i = 1,79 %)) = 8,50 % ; indice discipliné : capitalisation n° 16 parmi les éligibles |
| CIEC | retenu | 18 | 1,55 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 1,59 %)) = 10,00 % ; indice discipliné : capitalisation n° 17 parmi les éligibles |
| SPHC | retenu | 19 | 1,23 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 1,26 %)) = 10,00 % ; indice discipliné : capitalisation n° 18 parmi les éligibles |
| ONTBF | retenu | 20 | 1,20 % | plafond de ligne max(10 % × 0,75 ; min(30 % ; 1,25 × b_i = 1,23 %)) = 7,50 % ; indice discipliné : capitalisation n° 19 parmi les éligibles |
| TTLC | retenu | 21 | 1,19 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 1,22 %)) = 10,00 % × 0,5 (R12) = 5,00 % ; indice discipliné : capitalisation n° 20 parmi les éligibles ; filtres : R12 |
| ETIT | écarté | 4 | 0,00 % | capitalisation n° 4 parmi les éligibles : achat bloqué par un filtre de risque, titre non détenu écarté de la sélection (D8) ; filtres : R2 |
| ORGT | écarté | 22 | 0,00 % | capitalisation n° 22 parmi les éligibles : hors des 20 plus grosses (D8) ; filtres : R11×1 |
| SOGC | écarté | 23 | 0,00 % | capitalisation n° 23 parmi les éligibles : hors des 20 plus grosses (D8) ; filtres : R10 |
| SDSC | écarté | 24 | 0,00 % | capitalisation n° 24 parmi les éligibles : hors des 20 plus grosses (D8) |
| SMBC | écarté | 25 | 0,00 % | capitalisation n° 25 parmi les éligibles : hors des 20 plus grosses (D8) |

## 10. Faits, estimations, hypothèses

### Faits (publiés ou réglementaires)

- Cours de clôture et cours de référence du BOC du 20/11/2026 (source : BOC, data/panel).
- Bornes de ±7,5 % autour de la référence ajustée ; pas de cotation 1 FCFA sous 100 FCFA, 5 FCFA au-delà ; quotité 1 titre (instruction I-A, §7.1, §11).
- Règlement-livraison J+2 depuis le 04/12/2025 (instruction 03-2025) ; la BRVM annule les ordres en attente le jour ex.
- Dividendes : derniers montants nets publiés au BOC (ligne (d) ou correction publiée) ; IRVM CI 12 %, SN 10 % (2026), NE 7 %, ML 7 % (§7.3).
- Commissions BRVM 0,20 % et DC/BR 0,10 % par côté (barèmes primaires).
- Statut du test S1 : REJETÉ (registre : 20 essai(s) S1 au statut « exécuté »).
- Variante appliquée : REF (A est REJETÉ sur S1 : mode « indice discipliné » (§8.3, D8), aucune promesse d'alpha).
- Prime de risque du BOC 0,58 : marché « cher » (information, jamais un signal, §4.5).

### Estimations (calculées, incertaines)

- Demi-spread par titre : ½ × spread médian de clôture sur 120 séances (carnet du BOC), plancher d'un demi-pas ; défaut 0,35 % si non mesuré.
- Impact de marché κ·√π par tranche, π = montant de la tranche / MDV63 (valeur médiane échangée sur 63 séances, séances sans échange comptées à 0).
- Montants bruts et nets au cours de référence (le prix d'exécution réel peut différer jusqu'au prix limite) ; provision « pire cas » au prix limite.
- Dates de détachement et de paiement projetées sur le mois habituel ; AGO = date ex − 42 jours (médiane).
- Distribution à 12 mois par bootstrap stationnaire (toute l'histoire 2017-2026 (le registre indique que le test unique S1 a été exécuté)) : distribution historique, pas une prévision.
- Stress du §9.3 : pertes calculées sous hypothèse de linéarité (β) ou de choc direct par pays.

### Hypothèses (supposées, non vérifiées)

- Scénario de coûts « central » : courtage 0,80 % × (1 + taxe 18 %) — taxe [NON VÉRIFIÉ] (TVA ou TAF) ; redevance AMF-UMOA nulle (introuvable).
- Impact κ = 0,016 (« 50 pb à 10 % de participation », aucune étude d'impact BRVM).
- Droits de garde 0,25 % par an et tenue de compte 5 000 FCFA par ligne et par an (SGI de type BICI ; 0 chez FGI).
- Dernier dividende reconduit à l'identique (aucune prévision de résultat) ; IRVM BF 12,5 %, BJ par émetteur, TG inconnu : [NON VÉRIFIÉ] ; aucun impôt sur les plus-values (personne physique résidente, NV).
- Calendrier futur des séances : jours ouvrés hors fériés à date fixe (fêtes mobiles inconnues).
- Personne physique résidente ; aucun ordre au-delà de la cible ; la décision du jour est reconduite jusqu'à la revue mensuelle.

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
