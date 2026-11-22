# 02 — Littérature académique et empirique sur la BRVM

> **Projet** : BRVM Alpha · **Module** : recherche / revue de littérature
> **Rédigé le** : 2026-11-22 · **Statut** : v1.1, après vérification adversariale du 2026-11-22 (voir la dernière section). À réviser quand les textes intégraux seront accessibles.
> **Après vérification** : les paramètres de marché (limite de ±7,5 %, frais BRVM et DC/BR, date de la cotation en continu, chiffres du BOC) sont confirmés sur des sources primaires. Trois valeurs codées ont été **corrigées** : le coût aller-retour de base passe de 2,0 % à 2,5 % (erreur de calcul), les ratios de variance sont recalculés (persistance limitée à 2026), et l'affirmation « chaque titre non suspendu cote chaque jour » est fausse (166 séances-titres « NC », non coté, en 2025-2026). Les chiffres tirés d'articles académiques (demi-vies, R², etc.) sont **restés invérifiables** ce jour, faute d'accès réseau aux éditeurs. Ils sont marqués [NON VÉRIFIÉ].
> **Portée** : efficience faible, anomalies (calendrier, momentum/retournement, taille, dividendes, IPO), limites de variation, volatilité, trading peu fréquent, intégration et contagion, analyse technique. Le document couvre la BRVM et, à titre de comparaison, quelques marchés africains.

---

## 0. Avertissement

1. **Aucune étude publiée ne montre de gain garanti sur la BRVM.** La littérature trouve des *écarts* à l'efficience : autocorrélations, retour à la moyenne, effets calendaires instables, sous-évaluation à l'introduction en bourse. Ces écarts sont **instables dans le temps**, **sensibles à la méthode** et souvent **trop faibles une fois les coûts déduits**. Une plate-forme sérieuse s'en sert comme d'hypothèses à valider hors échantillon, jamais comme de promesses.
2. **Limite d'accès.** Pendant cette revue, la récupération directe des pages (WebFetch) a été refusée par le réseau de la session pour `ideas.repec.org` et `www.mdpi.com`. Les détails viennent donc des **résumés et extraits renvoyés par le moteur de recherche**, et des pages publiques de `www.brvm.org` (lues avec curl). Quand un chiffre ne figurait pas dans ces extraits, il est marqué **« non vérifié »** ; aucun chiffre n'a été inventé. Pour lire les textes intégraux, il faudrait autoriser ces hôtes dans les réglages réseau de la session.
3. **Niveaux de confiance** :
   - **high** : fait lu dans une source primaire (brvm.org, résumé éditeur) ;
   - **medium** : résumé d'éditeur ou de RePEc relayé par le moteur de recherche, cohérent entre plusieurs sources ;
   - **low** : source secondaire, extrait fragmentaire ou sources contradictoires.

---

## 1. Résumé exécutif

| # | Conclusion | Confiance |
|---|---|---|
| 1 | **L'efficience faible de la BRVM n'est pas tranchée.** Les tests de ratio de variance sur l'indice composite ne rejettent souvent pas la marche aléatoire (N'Dri 2015, période 2002-2004). En revanche, les tests qui tiennent compte de la non-linéarité, du trading peu fréquent ou de l'échelle (Appiah-Kusi & Menyah 2003 ; Smith 2008 ; Mlambo & Biekpe 2007 ; Diallo et al. 2021) concluent à l'inefficience. | medium |
| 2 | **Le retour à la moyenne à court terme est l'inefficience la mieux documentée.** Gbenro & Moussa (2019) estiment une demi-vie d'environ **7 jours pour le Composite** et d'environ **2 jours pour le BRVM 10** (2005-2018), avec une asymétrie faible et une vitesse de retour qui diminue légèrement dans le temps. **[NON VÉRIFIÉ]** : les chiffres de demi-vie viennent d'extraits de moteur de recherche, et le texte n'a pu être lu ni par le chercheur ni par le vérificateur. Le BRVM 10 n'est plus publié depuis le 30/12/2022. | low |
| 3 | **Les effets calendaires sont instables.** Selon les études, on trouve un effet lundi, un effet mercredi, un effet vendredi, un effet décembre ou un Ramadan à volatilité plus faible, mais ces effets disparaissent dans les modèles à fenêtre glissante (Obalade et al. 2022) ou dans les spécifications les mieux ajustées (RMEEF 2016). Ils ne sont **pas exploitables** comme signaux autonomes. | medium |
| 4 | **Aucune étude publiée sur le momentum transversal (Jegadeesh-Titman) propre à la BRVM n'a été trouvée.** Sur les marchés frontières en général, la valeur et le momentum sont les principaux moteurs de rendement (Zaremba et co-auteurs), mais ce résultat n'est pas spécifique à la BRVM. | medium (absence constatée) |
| 5 | **Le CAPM explique mal la BRVM.** La prime de risque est positive mais non significative en GARCH-M sur 2010-2018. Le modèle de Fama-French à 3 facteurs atteint un R² ajusté moyen de 20,4 % (28 titres, 2001-2008) et laisse au moins 60 % de la variance inexpliquée [NON VÉRIFIÉ]. | low-medium |
| 6 | **La volatilité est persistante et asymétrique (effet de levier).** L'EGARCH avec une loi de Student asymétrique est le meilleur modèle d'après Djahoué (2018) [NON VÉRIFIÉ]. Le sentiment des investisseurs améliore les prévisions de volatilité (Djahoué 2025) [NON VÉRIFIÉ]. | low-medium |
| 7 | **Le trading peu fréquent était extrême avant 2013** (plus de 90 % de rendements journaliers nuls selon Hearn 2014 [NON VÉRIFIÉ]). La cotation en continu existe depuis le **16/09/2013** (confirmé par brvm.org). Dans nos BOC 2025-2026, **presque** tous les titres non suspendus cotent chaque jour. Il reste toutefois **166 séances-titres « NC » (non coté)** hors suspensions, sur 466 séances. Environ 19 % des séances-titres ont une variation nulle. Le changement de régime est **récent** : la part de variations nulles était encore de 27 à 35 % chaque année de 2018 à 2024, puis de 22,9 % en 2025 et de 14,9 % en 2026. Les résultats anciens, y compris ceux de 2014-2024, doivent être réestimés. | high (BOC) / low (Hearn) |
| 8 | **L'intégration avec les autres marchés est faible.** Il n'y a pas de causalité entre la BRVM et le Ghana, mais une rétroaction avec le Nigeria (Emenike 2021). Les flux d'information depuis les marchés ESG mondiaux sont surtout non significatifs (Kyei et al. 2024). La contagion est surtout apparue pendant la crise de 2008. | medium |
| 9 | **Aucune étude académique publiée sur l'effet aimant des limites de ±7,5 % de la BRVM n'a été trouvée.** Notre vérification exploratoire sur les BOC 2025-2026 montre : (a) après un plafond haut, la continuation se fait surtout **dans le gap de la nuit**, qu'on ne peut pas capter ; (b) après un plafond bas, on observe un **rebond sur 5 séances mesuré depuis l'ouverture du lendemain** (médiane +3,1 % contre +0,07 % sans condition). C'est une piste à valider, pas un résultat établi. | low (exploratoire, interne) |
| 10 | **L'analyse technique simple (moyennes mobiles) n'a pas battu l'achat-conservation** dans le seul test BRVM trouvé, un mémoire. Ailleurs en Afrique, les résultats sont mitigés et dépendent des coûts. | low |

---

## 2. Contexte de marché utile pour interpréter la littérature

| Fait | Valeur | Date | Source | Confiance |
|---|---|---|---|---|
| Nombre de sociétés cotées | 48 | 20/11/2026 | BOC n°222, `data/boc_text/boc_20261120.txt.gz` (source : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf) | high |
| BRVM Composite | 492,89 (+42,56 % sur l'année) | 20/11/2026 | idem | high |
| BRVM Composite Total Return (base 100 au 02/01/2025) | 198,63 (+49,19 % sur l'année) | 20/11/2026 | idem | high |
| PER moyen du marché, hors Unilever CI | 15,79 | 20/11/2026 | idem | high |
| Taux de rendement moyen du marché | 7,12 % | 20/11/2026 | idem | high |
| Taux de rotation moyen du marché | 0,16 | 20/11/2026 | idem | high |
| Limite de variation statique (actions et obligations) | ±7,5 % par rapport au **cours de référence** ; au-delà, la cotation est reportée | Instruction I-A, dans un PDF **créé le 22/01/2013**, donc antérieur à la cotation en continu. Ce document est obsolète sur d'autres points : il décrit encore des séances le lundi, le mercredi et le vendredi, alors que la cotation est quotidienne depuis le 12/11/2001 | https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf | high (règle) / medium (version en vigueur) |
| Vérification empirique de la limite | max = +7,50 %, min = −7,50 % sur 21 362 à 21 528 séances-titres selon le parseur ; **aucun dépassement de 2023 à 2026**. De 2018 à 2022, il y a 14 dépassements apparents. Les 6 examinés s'expliquent tous :
<br>• détachements de dividendes : BOABF le 29/04/2019, SMBC le 28/08/2019, CABC le 28/07/2020, SLBC le 18/08/2022. La variation publiée est alors calculée sur le cours précédent **non ajusté**. SLBC clôture exactement à 0,925 × (135 000 − 4 050) ;
<br>• fractionnement : STBC le 31/07/2018 ;
<br>• effet de pas de cotation : ETIT, 13 → 14 FCFA = +7,69 %.
<br>Les 8 autres cas n'ont pas été examinés | 03/01/2025 → 20/11/2026 ; contrôle 2018-2026 par le vérificateur | BOC locaux `data/boc_text/` | high |
| Limite appliquée dès la 1re séance d'une introduction en bourse | oui : Bridge Bank Group CI (BBGC), introduit le 25/09/2026, fait +7,44 %, +7,44 % et +7,46 % sur ses 3 premières séances, puis 0,00 % | 25/09/2026 → 30/09/2026 | BOC locaux (ex. https://www.brvm.org/sites/default/files/boc_20260925_2.pdf) | high |
| Passage du fixing à la cotation en continu | 16/09/2013 (article 29 du Règlement général modifié par la décision CREPMF n° 2013-060 du 29/06/2013) | 2013 | https://www.brvm.org/fr/historique ; https://www.brvm.org/sites/default/files/rg_brvm_-_apres_approbation_crepmf_sept_2021_01_07_2022_bis.pdf ; https://www.financialafrik.com/2013/09/17/bourse-afrique-abidjan-bascule-dans-la-cotation-en-continu/ | high |
| Commissions BRVM / DC-BR | 0,2 % et 0,1 % du montant, payées par l'acheteur et par le vendeur (« actuellement », page non datée) | consulté le 22/11/2026 | https://www.brvm.org/fr/node/312 | high |
| Courtage des SGI | environ 0,2 % à 1,5 % selon la SGI ; tarifs homologués par le régulateur | 2026 | https://www.richbourse.com/common/apprendre/ouvrir-compte-titres ; https://www.westbourse.com/comparateur-sgi | low (sources secondaires) [NON VÉRIFIÉ] |
| Taxes sur l'avis d'opéré | brvm.org mentionne des « taxes » **sans en donner le taux**. La page Fiscalité renvoie seulement à la directive 02/2010/CM/UEMOA. Le taux de 18 % utilisé en section 13 n'est **pas sourcé**, et la revue 01 utilise 10 % (TAF) | consulté le 22/11/2026 | https://www.brvm.org/fr/node/312 ; https://www.brvm.org/fr/node/313 | [NON VÉRIFIÉ] |
| Indices phares | Le BRVM 10 est publié pour la dernière fois le 30/12/2022. Il est remplacé par le **BRVM 30** (base 100 au 02/01/2023 ; 100,13 ce jour-là) et le BRVM Prestige | 2022-2023 | BOC du 30/12/2022 et du 02/01/2023 (https://www.brvm.org/sites/default/files/boc_20230102_2.pdf) | high |
| Fractionnement Sonatel (SNTS) | **1 pour 10** : dernier cours avant fractionnement 43 850 le 23/10/2026 (cours de référence ajusté 4 385), 1re séance fractionnée le 26/10/2026 ; dividende retraité de 1 740 à 174 FCFA | 23-26/10/2026 | BOC du 23/10/2026 et du 26/10/2026 | high |

> Conséquence directe : l'indice **BRVM Composite est un indice de prix**, sans dividendes, alors que le rendement moyen du marché est d'environ 7 %. Pour savoir si une stratégie « bat les indices », il faut la comparer au **Composite Total Return**. Sinon, la surperformance est artificiellement gonflée de plusieurs points par an. Contrôle sur les BOC : en 2025, le Composite passe de 276,13 (02/01) à 345,75 (31/12), soit +25,2 %, contre environ +33,1 % pour le Total Return (133,14 implicite au 31/12/2025). En 2026, jusqu'au 20/11, c'est +42,56 % contre +49,19 %. L'écart est donc de 6,6 à 7,9 points, soit environ 4,7 à 6,3 % en relatif (confirmé).

---

## 3. Efficience au sens faible (marche aléatoire, autocorrélation, ratio de variance)

| Étude | Période / données | Méthode | Résultat (chiffres disponibles) | Lien | Confiance |
|---|---|---|---|---|---|
| Appiah-Kusi & Menyah (2003), *Review of Financial Economics* 12(3), 247-270 | 11 marchés africains, rendements hebdomadaires d'indices **ajustés du trading peu fréquent** (Côte d'Ivoire incluse) | AR non linéaire + EGARCH-M | **Côte d'Ivoire non efficiente au sens faible**, comme le Botswana, le Ghana et le Swaziland | https://onlinelibrary.wiley.com/doi/10.1016/S1058-3300%2802%2900073-3 | medium |
| Mlambo, Biekpe & Smit (2003), *African Finance Journal* 5(1), 16-35 | 4 marchés africains ; présence de la BRVM **non confirmée** | Marche aléatoire avec correction du trading peu fréquent | Près de la moitié des titres de chaque marché ont une autocorrélation significative | https://ideas.repec.org/a/afj/journl/v5y2003i1p16-35.html | low (pour la BRVM) |
| Mlambo & Biekpe (2007), *Investment Analysts Journal* n°66, pp. 5-17 (ou 5-18 selon la version MPRA) | 10 marchés africains, BRVM incluse | Test des runs, correction du trading peu fréquent (rapport de prix d'une transaction à l'autre) | Seuls la Namibie, le Kenya et le Zimbabwe sont « relativement efficients ». Pour la BRVM, la possibilité de détecter des motifs « n'est pas nulle » | https://mpra.ub.uni-muenchen.de/25968/ ; https://www.tandfonline.com/doi/abs/10.1080/10293523.2007.11082489 | medium |
| Smith (2008), *South African Journal of Economics* 76(2), 161-175 | 11 marchés africains (Côte d'Ivoire incluse), janvier 2000 à septembre 2006 | Ratios de variance joints avec valeurs critiques en échantillon fini | **Marche aléatoire i.i.d. rejetée sur les 11 marchés** ; pas de statistique publiée pour la Côte d'Ivoire seule | https://onlinelibrary.wiley.com/doi/10.1111/j.1813-6982.2008.00171.x | medium |
| Léon (N'Dri) (2007), communication (supplément, Univ. Bergame) | BRVM (détails non vérifiés) | Box-Pierce, test des runs | Impossible de prévoir les rendements à partir du passé, ce qui est **compatible avec l'efficience faible** | https://aisberg.unibg.it/retrieve/e40f7b84-1278-afca-e053-6605fe0aeaf2/LEON%20suppl.%202007.pdf | low |
| N'Dri, K. L. (2015), *Applied Economics and Finance* 2(2), 118-125 | Indice BRVM **journalier, du 02/01/2002 au 31/12/2004** | Lo-MacKinlay (1988), Chow-Denning (1993), Wright (2000) sur les rangs | **Marche aléatoire non rejetée** par les trois tests, d'où la conclusion d'efficience faible | https://redfame.com/journal/index.php/aef/article/view/751 | medium |
| Diallo, Mendy & Burlea-Schiopoiu (2021), *Heliyon* 7(1), e05858 | **7 indices sectoriels**, journaliers, du 31/12/2013 au 04/01/2019 | Exposant de Hurst généralisé par ondelettes (DWT et WLT) | **Efficience faible rejetée pour tous les secteurs sauf l'agriculture** : les rendements des autres secteurs sont prévisibles | https://pubmed.ncbi.nlm.nih.gov/33553713/ ; https://www.cell.com/heliyon/fulltext/S2405-8440(20)32700-6 | medium |
| Toe, Toe & Zoungrana (2023), *SN Business & Economics* 3, 170 | Données BRVM et BCEAO, 1998-2020 | ADF, runs, ratio de variance (forme faible) ; Johansen et Granger (forme semi-forte) | Le ratio de variance et les runs **ne rejettent pas** la marche aléatoire, mais les auteurs concluent à l'inefficience sur la base de l'ADF (conclusion **discutable** : l'absence de racine unitaire dans les rendements ne prouve rien). En forme semi-forte, **M1 et M2 ont un pouvoir prédictif sur les cours** | https://link.springer.com/article/10.1007/s43546-023-00550-0 | medium (données) / low (interprétation) |
| Houndalidji, Tchindro & Hounkou (2024), *Journal of Financial Risk Management* 13(4), 769-797 | Composite, **1 618 observations journalières** (janvier 2016 à juin 2022), 45 titres | Test des runs, ARIMA (Box-Jenkins) | Conclusion **formulée de façon contradictoire** dans le résumé ; à la lecture des extraits, elle va vers l'inefficience faible | https://www.scirp.org/journal/paperinformation?paperid=138677 | low |
| Gil-Alana, Mudida & Kariuki (2025), *Journal of Economic Studies* 52(9), 146-160 | 14 pays africains, indices **mensuels** (Côte d'Ivoire incluse) | Intégration fractionnaire | Marche aléatoire **non rejetée** sauf pour le Maroc et l'Afrique du Sud | https://doi.org/10.1108/JES-04-2022-0238 | medium |
| Gbenro & Moussa (2019), *Journal of Risk and Financial Management* 12(1), 38 | BRVM Composite et BRVM 10, journaliers, environ 2005-2018 | AR non linéaire asymétrique (Nam et al. 2006) avec innovations EGARCH, fenêtres glissantes de 2, 4, 6 et 8 ans | **Retour à la moyenne** ; **demi-vie d'environ 7 jours (Composite) et d'environ 2 jours (BRVM 10)** ; asymétrie faible ; la vitesse de retour du Composite diminue légèrement. **[NON VÉRIFIÉ]** : texte inaccessible (hôte mdpi.com bloqué), chiffres issus d'extraits. Mise en garde du vérificateur : l'autocorrélation d'ordre 1 des rendements du Composite vaut ρ1 = 0,012 sur 2024-2026. Une demi-vie de 7 jours ne peut donc pas porter sur un AR(1) des rendements, qui demanderait un coefficient d'environ 0,91. Elle porte sur une autre grandeur, à identifier dans le texte avant tout codage | https://doi.org/10.3390/jrfm12010038 | low (chiffres) / medium (existence) |
| Doumbia (2023), mémoire (Univ. Glasgow) | BRVM comparée à d'autres marchés africains | n.d. | Résultats non lus | https://www.researchgate.net/publication/374899681 | low |
| *Dirassat Iqtissadiya* 12(1) (2025), pp. 380-402 | 5 marchés africains, BRVM incluse | Tests de forme faible | La BRVM serait efficiente au sens faible, contrairement aux 4 autres marchés (extrait fragmentaire) | https://asjp.cerist.dz/en/downArticle/67/12/1/267468 | low |

**Lecture critique.**

- Les tests **linéaires sur l'indice** (ratio de variance, runs) penchent vers « pas de rejet ». Les tests **non linéaires, multi-échelles ou corrigés du trading peu fréquent** penchent vers « rejet ». L'indice moyenne des prix de titres qui ne se négocient pas de façon synchrone : cela crée une autocorrélation positive artificielle, et inversement le *bid-ask bounce* crée une autocorrélation négative au niveau des titres. Il faut donc tester **au niveau des titres et au niveau des indices**, avec correction.
- Plusieurs articles récents (Toe et al. 2023 ; Houndalidji et al. 2024) ont des **conclusions incohérentes avec leurs propres tests**. Il ne faut pas les utiliser pour calibrer des paramètres.
- Les synthèses de la littérature africaine (revue systématique d'*Emerging Markets Review* 55, 2023 : https://ideas.repec.org/a/eee/ememar/v55y2023ics1566014123000353.html ; chapitre IntechOpen « Are African Stock Markets Inefficient or Adaptive? » : https://www.intechopen.com/chapters/73879) vont dans le sens de l'**hypothèse des marchés adaptatifs**, c'est-à-dire d'une efficience qui varie dans le temps.

---

## 4. Anomalies calendaires

| Étude | Période | Méthode | Résultat BRVM | Lien | Confiance |
|---|---|---|---|---|---|
| Tachiwou, A. M. (2010), *International Journal of Economics and Finance* 2(2), 167-173 | Septembre 1998 à décembre 2007, journalier | Régressions sur des variables indicatrices des jours | Effet jour de la semaine présent. D'après des sources secondaires, rendements les plus faibles le mardi et le mercredi, les plus élevés le vendredi (non vérifié dans le texte) | https://pdfs.semanticscholar.org/08f5/b4d4d967d38cb55236965669ea05af4889c2.pdf | medium (existence) / low (détail) |
| MPRA n°24907 (2010), « Management of Stock Price and it Effect on Economic Growth: Case study of West African Financial Markets » (auteurs non vérifiés) | n.d. | Propriétés statistiques des rendements | Effet jour de la semaine signalé | https://mpra.ub.uni-muenchen.de/24907/1/MPRA_paper_24907.pdf | low |
| Ben Mrad Douagi, Chaouachi & Mory (2019), *Asian Journal of Empirical Research* 9(2), 38-45 | Janvier 2002 à décembre 2016 | GARCH | Le résumé RePEc annonce des effets jour et mois ; la version ResearchGate parle de « pas de preuve forte » d'anomalies générales, avec un effet lundi sur un sous-indice. **Sources contradictoires** | https://ideas.repec.org/a/asi/ajoerj/v9y2019i2p38-45id4274.html ; https://www.researchgate.net/publication/357351015 | low |
| Ferrouhi, Kharbouch, Aguenaou & Naeem (2021), *Cogent Economics & Finance* 9, 1978639 | 2009-2019 | MCO avec variables indicatrices | **Effet lundi (BRVM Composite)**, effet mercredi sur l'indice « BRVM » (sous-indice non précisé dans l'extrait), **effet décembre (BRVM)** | https://www.tandfonline.com/doi/full/10.1080/23322039.2021.1978639 | medium |
| *Review of Middle East Economics and Finance* 12(1), 65-113 (2016), « More on Calendar Effects on Islamic Stock Markets » | n.d. | GARCH, deux approches | **Volatilité plus faible pendant le Ramadan** pour la BRVM avec une approche, mais **non significative** dans les modèles les mieux ajustés | https://doi.org/10.1515/rmeef-2015-0039 | medium |
| Obalade, Tshutsha, Mvuyana, Ndlovu & Muzindutsi (2022), *Journal of Economics and Financial Analysis* 6(1), 19-35 | 2000:1 à 2020:6, journalier (Ghana, Kenya, Botswana, BRVM) | GARCH en fenêtre glissante, hypothèse des marchés adaptatifs | **L'effet jour de la semaine ne peut pas être validé pour la BRVM** (ni pour le Ghana) ; il varie dans le temps au Kenya et au Botswana | https://ojs.tripaledu.com/jefa/article/view/71 | medium |
| Alloul & Ferrouhi (2025), *Organizations and Markets in Emerging Economies* 16(1), 155-192 | Avant et pendant le Covid ; BRVM Composite et 11 indices | GJR-GARCH | Certaines anomalies apparaissent ou disparaissent pendant le Covid ; résultat propre au Composite non lu | https://www.journals.vu.lt/omee/article/view/36475 | low (pour la BRVM) |
| Djahoué, M. G. (2025), *Modern Economy* 16(11), 1802-1826 | Journalier, du 04/01/2014 au 26/02/2025, 5 indices | Régressions linéaires et logit binomial, indice de sentiment | **Pas de consensus** sur l'effet jour de la semaine : il change selon l'indice. Le **sentiment des investisseurs** joue un rôle important | https://www.scirp.org/journal/paperinformation?paperid=147179 | medium |

**Verdict.** Ces effets ne résistent ni au changement d'indice, ni au changement de période, ni à la fenêtre glissante. Ils sont **trop petits face à un coût aller-retour de l'ordre de 2,2 à 3 %, avec 2,5 % comme base** (section 13, valeur corrigée). Dans la plate-forme, on les garde comme **variables de contrôle**, pas comme signaux.

---

## 5. Coupe transversale : momentum, retournement, taille, valeur, CAPM

### 5.1 Momentum et retournement

- **Aucune étude publiée sur le momentum de type Jegadeesh-Titman ou sur la surréaction de type De Bondt-Thaler propre à la BRVM n'a été trouvée.** Des recherches en français et en anglais (Google Scholar via WebSearch, SSRN, RePEc) ont été faites le 2026-11-22. C'est une **lacune de la littérature**, donc un terrain de recherche propre à la plate-forme.
- Le seul résultat dynamique propre à la BRVM est le **retour à la moyenne à très court terme** sur les indices (Gbenro & Moussa 2019, section 3).
- **Marchés frontières (hors BRVM)** : sur 23 marchés frontières, Zaremba et co-auteurs trouvent une forte persistance des rendements d'anomalies et identifient **la valeur et le momentum comme principaux moteurs de rendement**. Ces résultats ne sont pas spécifiques à la BRVM. Sources : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3060876 ; https://quantpedia.com/equity-factor-strategies-in-frontier-markets/ (medium).
- **Nigeria, Égypte, Afrique du Sud** : des règles de momentum, contrôlées pour le *data snooping*, génèrent des profits significatifs au Nigeria, moins en Égypte et en Afrique du Sud (*Global Business and Economics Review* 30(3), 259-282, 2024 : https://www.inderscience.com/info/inarticle.php?artid=137616). Le résumé ne dit pas si les profits tiennent après coûts (medium).

### 5.2 Prime de risque, CAPM, multifacteurs

| Étude | Période / données | Méthode | Résultat | Lien | Confiance |
|---|---|---|---|---|---|
| N'Dri (2007), *African Journal of Business Management* 1(5), 107-112 | Hebdomadaire, 1999-2005 | GARCH-M, EGARCH-M, GJR (lois normale, Student et GED) | Persistance de la volatilité élevée. Relation rendement-volatilité **non significative** selon le résumé ; une source secondaire dit l'inverse | https://academicjournals.org/article/article1380545342_N%E2%80%99dri.pdf | medium |
| « Applying the CAPM and the Fama–French models to the BRVM stock market », *Applied Financial Economics* 23(4), 275-285 (2013) ; auteur non vérifié | 28 sociétés, juillet 2001 à décembre 2008 | CAPM, Fama-French à 3 facteurs | Le CAPM est validé pour 11 titres ; avec Fama-French, le **R² ajusté moyen est de 20,40 %** ; **au moins 60 % de la variance reste inexpliquée** [NON VÉRIFIÉ : auteur inconnu, texte non lu ; un R² moyen de 20,4 % laisse en fait près de 80 % inexpliqué, d'où un « au moins 60 % » à vérifier dans le texte] | https://www.tandfonline.com/doi/abs/10.1080/09603107.2012.718062 | low |
| Kolani & Ekoue (Vikpossi) (2014), *Research in World Economy* 5(1) | 17 sociétés, mensuel, 2000-2008 | Tests du CAPM | **CAPM rejeté** : constante non nulle, pente différente de la prime de marché | https://www.researchgate.net/publication/315042349 | medium |
| Olasehinde-Williams (2018), *Journal of International Business Research and Marketing* 3(5), 7-11 | n.d. | ARMA(1,2)-GARCH(1,1)-M | Les investisseurs **ne sont pas rémunérés** pour le risque | https://researchleap.com/examination-relationship-volatility-expected-returns-brvm-stock-market/ | medium |
| « Do Africa stock markets exhibit any evidence of risk-return trade-off? », *Int. J. of Bonds and Derivatives* 4(3), 221-235 (2021) | 04/01/2010 au 30/11/2018, 7 marchés | AR(p)-GARCH(1,1)-M | Prime de risque de la BRVM **positive mais non significative** | https://www.inderscience.com/info/inarticle.php?artid=116970 | medium |
| Essingone & Diallo (2022), *Journal of Financial Risk Management* 11(1), 220-243 | Composite, 16/09/1998 au 31/12/2016 (version de travail) | Modèle à réponse asymétrique (ARM) comparé au CAPM | Les rendements sont **asymétriques** ; l'ARM convient mieux que le CAPM | https://doi.org/10.4236/jfrm.2022.111011 | medium |
| Hearn & Piesse (2010), *Applied Financial Economics* 20(13), 1011-1030 | 5 marchés d'Afrique de l'Ouest plus Londres et Paris | CAPM multifactoriel avec taille et illiquidité (rotation, Amihud) | Les stratégies sur les marchés francophones font mieux que sur les anglophones, malgré des rendements moyens plus faibles ; bénéfices limités des actifs ivoiriens et ghanéens, très illiquides | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1342031 | medium |
| Hearn, Tauringana, Ntim, Malagila & Mishra (2025), *International Review of Financial Analysis* 97, 103752 | 375 valeurs vedettes de 8 marchés africains, 23 ans, mensuel (présence de la BRVM **non confirmée**) | Comparaison de CAPM, FF3, Carhart, FF5, FF6, ILLIQ2F | **FF5 et FF6 ont le meilleur pouvoir explicatif** ; la croissance des actifs (facteur investissement) compte | https://www.sciencedirect.com/science/article/pii/S1057521924006847 | medium |

**Verdict.** La BRVM est mal décrite par le CAPM. Un modèle de type FF5 avec un facteur d'illiquidité est l'hypothèse de travail la plus soutenue pour l'Afrique frontière. **Aucune estimation publiée des primes taille, valeur ou momentum propres à la BRVM après 2013 n'a été trouvée** : la plate-forme devra les estimer elle-même.

---

## 6. Dividendes, publications de résultats, introductions en bourse

| Étude | Période | Méthode | Résultat | Lien | Confiance |
|---|---|---|---|---|---|
| *European Scientific Journal* 13(22) (2017) | n.d. | Étude d'événement, fenêtre [−20, +20] autour des annonces de dividendes, modèle de marché sur le BRVM Composite | Les cours réagissent autour de l'annonce ; **chiffres non vérifiés** | https://eujournal.org/index.php/esj/article/download/9793/9297 | low |
| Ouattara, A. (2017), MPRA n°79839 | Résultats et dividendes 2011-2016 | Politique de distribution | Étude descriptive de la politique de dividendes | https://mpra.ub.uni-muenchen.de/79839/1/MPRA_paper_79839.pdf | medium |
| « Sous-évaluation à l'introduction en bourse : cas des entreprises cotées sur le marché de la BRVM », *Revue du Chercheur* | 10 IPO avant la crise ivoirienne de 2011, 8 après | Rendement initial, test de Student | Sous-évaluation dans les deux échantillons, **significative seulement après 2011** ; l'échantillon total est aussi sous-évalué | https://zenodo.org/records/4009093 | medium |
| Étude sur les banques UEMOA cotées | n.d. | Rendements anormaux cumulés | Sous-évaluation des IPO bancaires « bien réelle » | https://zenodo.org/records/5052654 | low |
| Communication financière, secteur distribution (Servair, Bernabé) | n.d. | E-views et questionnaire | Corrélation significative entre BPA, DPA, endettement, PER, ROE et les cours | https://zenodo.org/records/21847511 | low |

- **Effet du détachement de dividende** : **aucune étude systématique trouvée**, seulement des anecdotes de presse. Exemple : Tractafric Motors CI (PRSC) a perdu 11,42 % sur la semaine de son détachement en octobre 2026 (https://dabafinance.com/en/news/brvm-stocks-fall-for-second-week-as-sonatel-stock-split-nears). **Vérifié sur les BOC** : 4 290 le 16/10/2026, puis 3 800 le 23/10/2026, soit −11,42 %. Mais le dividende net de 183,92 FCFA, détaché le 22/10/2026 (cours de référence 3 970), représente environ 4,3 points de cette baisse. **Net du dividende, la baisse n'est que d'environ −7,1 %** (high pour le chiffre, l'anecdote ne prouve rien sur l'effet de détachement).
- **Dérive post-annonce de résultats (PEAD)** : **aucune étude BRVM trouvée**.
- **Interaction avec les limites** : le rendement initial d'une IPO est plafonné à +7,5 % par séance. La sous-évaluation se répartit donc sur **plusieurs séances consécutives au plafond**. Il faut la mesurer sur plusieurs jours, pas sur le premier seul. C'est une déduction mécanique de la règle I-A, non testée dans la littérature, mais **observée dans les BOC** : BBGC a fait +7,44 %, +7,44 % et +7,46 % du 25 au 29/09/2026, ECOC a fait +7,49 %, +5,80 %, +6,32 % et +7,48 % sur ses 4 premières séances, du 13 au 18/12/2017.

---

## 7. Limites de variation : effet aimant et continuation

- **Règle** : écart maximal de ±7,5 % par séance par rapport au cours de référence. Si le fixing dépasse le seuil, la cotation est reportée et un prix indicatif est affiché au seuil franchi (Instruction I-A : https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf ; high). Un support pédagogique mentionne aussi un **seuil dynamique de ±2 %** (±3 % si le pas de cotation est inférieur à 5 FCFA), avec réservation de 5 minutes en séance continue (https://www.gpe-afrique.com/moodledata/filedir/c5/9b/c59ba17efa07ba3df075a7cdb160fee4a33f571e ; low). **[NON VÉRIFIÉ]** : ce seuil ne figure ni dans l'Instruction I-A (PDF de janvier 2013), ni dans le Règlement général du 01/07/2022. L'article 37 de ce dernier renvoie les « écarts de cours » propres à chaque compartiment à une Instruction qui n'a pas été trouvée sur brvm.org. Le BOC ne publie pas de données intrajournalières, donc on ne peut pas le tester.
- **Cours de référence ajusté** : la limite s'applique au cours de référence **ajusté** des dividendes et des fractionnements (voir section 2). Les jours de détachement, la variation publiée dans le BOC de 2018-2022 peut dépasser 7,5 % en valeur absolue. Pour les titres à très faible prix, le pas de 1 FCFA peut aussi produire plus de 7,5 % (ETIT à 13 FCFA en 2021).
- **Littérature propre à la BRVM** : **aucune étude trouvée** sur l'effet aimant, l'effet de refroidissement, la propagation de la volatilité ou la découverte de prix retardée.
- **Littérature internationale** : les résultats sont mitigés.
  - Effet aimant mis en évidence à Taïwan : https://www.researchgate.net/publication/222684404.
  - Sur ChiNext, découverte de prix retardée et propagation de la volatilité, plus fortes aux limites basses ; pas d'effet aimant après la réforme : https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0287548.
  - Effet aimant rejeté en Tunisie (Dabbou 2013, cité dans https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4395215/).
  - Confiance : medium.

### 7.1 Vérification exploratoire interne sur les BOC (pas une étude publiée)

- **Données** : BOC journaliers, du **03/01/2025 au 20/11/2026** (466 séances, 49 titres, 21 528 séances-titres ; les fichiers 2024 ne sont pas encore analysés par le script). Cours précédent, ouverture, clôture, variation et volume sont tirés des tableaux d'actions.
- **Événement** : clôture à ±7 % ou plus.
- **Entrée tradable** : **ouverture de t+1**. Le gap entre la clôture de t et l'ouverture de t+1 est mesuré à part, car un ordre au plafond peut rester non exécuté.
- **Script** : `/tmp/claude-0/-home-user-documentation/b095b722-74b3-5e89-8589-8e6133bd6c39/scratchpad/scripts/` (fichiers `parse_boc.py`, `analyze2.py`, `analyze4.py`, `vr.py`). Ce dossier est temporaire.

| Mesure | Plafond haut (≥ +7 %) | Plafond bas (≤ −7 %) | Sans condition |
|---|---|---|---|
| Nombre d'événements | 712 | 401 | 21 216 |
| Gap clôture t → ouverture t+1 (moyenne / médiane) | **+2,97 % / +1,54 %** (65 % positifs) | **−2,44 % / −0,83 %** (25 % positifs) | +0,06 % / 0,00 % |
| Ouverture t+1 → clôture t+5 (moyenne / médiane / part positive) | +2,63 % / +0,14 % / 50 % | **+3,43 % / +3,09 % / 62 %** | +0,96 % / +0,07 % / 51 % |
| Ouverture t+1 → clôture t+10 (médiane) | +0,94 % | **+3,26 %** | +0,69 % |
| Plafond bas, moitié liquide (valeur médiane échangée par jour ≥ ~10 MFCFA) : ouverture t+1 → clôture t+5 | — | +4,84 % / **+3,55 %** / 71 % (91 événements, 72 dates distinctes) | +0,84 % / +0,21 % / 53 % |
| Plafond bas, moitié liquide, en excluant les dates à 3 événements ou plus | — | médiane +3,09 %, 68 % positifs (78 événements) | — |
| **Réplication indépendante du vérificateur** (parseur distinct, mêmes BOC) : ouverture t+1 → clôture t+5 | médiane +0,07 % (+0,15 % en chaînant les variations ajustées), 50 % positifs, n = 714 | **médiane +3,09 % (+3,10 % chaîné), 62 % positifs, n = 396** sur 402 événements | médiane +0,06 %, n = 21 122 |
| Réplication, sous-échantillon liquide (valeur médiane ≥ 10 MFCFA, 26 titres) | — | médiane +4,34 %, 72 % positifs, n = 125 : même sens, mais **le chiffre dépend du seuil de liquidité** | — |

**Autres statistiques de la même vérification :**

- Part des séances-titres à variation nulle : 24,0 % en 2025, 15,0 % en 2026. La réplication donne 22,9 % et 14,9 %. Ces chiffres incluent les séances « NC » (non coté), affichées à 0,00 %.
- Part des séances-titres à ±7 % ou plus : 5,2 % (confirmé par la réplication).
- Corrélation d'ordre 1 des rendements journaliers des titres (empilés) : +0,096. **Corrigé** : la réplication donne +0,071 avec les variations publiées. Le chiffre dépend de la définition (log ou simple, séances NC incluses ou non) ; retenir « environ +0,07 à +0,10 ».
- Regroupement des plafonds bas : jusqu'à 14 le même jour, le 23/09/2026 (confirmé).
- BRVM Composite, rendements logarithmiques du 04/11/2024 au 20/11/2026 (n = 503) :
  - ρ1 = 0,012 (confirmé) ;
  - VR(2) = 1,01 (z\* = 0,17 ; réplication : z\* = 0,19) ;
  - VR(10) = 1,40 (z\* robuste = 2,00). **Corrigé** : la réplication Lo-MacKinlay robuste à l'hétéroscédasticité donne **VR(10) = 1,37, z\* = 1,84, non significatif à 5 %** ;
  - VR(20) = 1,77 (z\* = 2,87). **Corrigé** : réplication **VR(20) = 1,70, z\* = 2,59** ;
  - VR(5) = 1,13 (z\* = 0,90) dans la réplication ;
  - **Sous-périodes (réplication)** :
    - du 04/11/2024 au 31/12/2025 : VR(10) = 0,84 (z\* = −0,72), VR(20) = 0,76 (z\* = −0,76) ;
    - du 01/01/2026 au 20/11/2026 : VR(10) = 1,74 (z\* = 2,45), VR(20) = 2,34 (z\* = 3,36).
  - **La persistance vient entièrement de 2026.**
  - Avec 4 horizons testés, la valeur critique de Chow-Denning à 5 % est d'environ 2,49 : seul VR(20) la dépasse.

**Interprétation prudente :**

1. **Plafond haut.** La continuation existe, mais elle est surtout **dans le gap de la nuit**, qu'on ne peut pas capter. Depuis l'ouverture de t+1, la médiane sur 5 jours (+0,14 %) est proche de celle sans condition (+0,07 %). **Courir après les plafonds hauts ne présente pas d'avantage démontré.**
2. **Plafond bas.** Le gap prolonge la baisse, puis vient un **rebond depuis l'ouverture de t+1**. L'effet est visible en 2025 comme en 2026 et plus marqué sur les titres liquides. Il est cohérent avec le retour à la moyenne de Gbenro & Moussa (2019), mais comporte des biais possibles :
   - échantillon de seulement 23 mois, en **marché fortement haussier** (Composite +42,6 % en 2026) ;
   - événements regroupés : jusqu'à 14 plafonds bas le même jour ;
   - ouverture parfois établie sur un **très petit volume**, donc non exécutable en taille ;
   - effets de *bid-ask bounce* ;
   - détachements de dividendes et opérations sur titres mal identifiés ;
   - **aucun coût déduit** : il faut compter un aller-retour d'environ **2,5 % en base** (2,2 à 3 %, valeur corrigée en section 13). La médiane nette tombe donc à environ **+0,6 %**.
3. **Indice (corrigé après vérification).** Sur 2024-2026, seul VR(20) est significatif (1,70, z\* = 2,59). VR(10) ne l'est pas (z\* = 1,84). Surtout, **toute la persistance vient de 2026** (VR(20) = 2,34), année très haussière : +42,6 % au 20/11. La fin 2024 et 2025 montrent au contraire des VR inférieurs à 1, non significatifs. On ne peut donc pas parler d'un « régime 2024-2026 » de tendance. C'est un épisode de 2026, cohérent avec l'hypothèse des marchés adaptatifs, à **réestimer en fenêtre glissante** et à ne jamais extrapoler.

---

## 8. Volatilité (GARCH, asymétrie, mémoire longue)

| Étude | Période | Méthode | Résultat | Lien | Confiance |
|---|---|---|---|---|---|
| N'Dri (2007), *AJBM* 1(5) | 1999-2005, hebdomadaire | GARCH, GJR, EGARCH (lois N, t, GED) | Forte persistance de la volatilité | https://academicjournals.org/article/article1380545342_N%E2%80%99dri.pdf | medium |
| Djahoué, M. G. (2018), *Journal of Applied Finance & Banking* 8(6), 91-109 | BRVM 10 et Composite, journalier ; janvier 2010 à mai 2016 selon un résumé | 3 GARCH asymétriques, plusieurs lois | Rendements **asymétriques** avec **effet de levier** ; **EGARCH avec loi de Student asymétrique** meilleur pour le BRVM 10 ; EGARCH meilleur que GARCH pour le Composite [NON VÉRIFIÉ : texte non lu par le vérificateur] | http://www.scienpress.com/Upload/JAFB/Vol%208_6_4.pdf | low-medium |
| Djahoué (prépublication, environ 2025-2026), « Investor Sentiment and Stock Market Volatility: Evidence from the West African Regional Stock Exchange » | n.d. | Famille FIGARCH, indice de sentiment | Forte persistance, asymétrie, **mémoire longue** ; l'indice de sentiment **améliore les prévisions de volatilité** | https://www.researchgate.net/publication/404732210 | low-medium |
| Ouattara, Z. & Koy, A. (2024), *Journal of International Trade, Logistics and Law* 10(1), 149-158 | Mars 2005 à septembre 2023 | GARCH(1,1) avec variables macroéconomiques | Relation inverse entre la volatilité et les taux USD, CNY et le taux moyen des crédits ; **l'inflation a un effet significatif** | https://www.jital.org/index.php/jital/article/view/461 | medium |
| Gueyie, Diallo & Diallo (2022), *International Journal of Financial Studies* 10(4), 113 | 05/01/2015 au 31/10/2022, indice et volume journaliers | Relation contemporaine, causalité de Granger | Pas de lien contemporain significatif ; **les rendements causent le volume (au sens de Granger)**, pas l'inverse | https://www.mdpi.com/2227-7072/10/4/113 | medium |

**Verdict.** Pour la prévision de volatilité (dimensionnement des positions, VaR), le modèle par défaut est un **EGARCH(1,1) avec loi de Student asymétrique**, comparé à GJR et FIGARCH. Le volume **ne prédit pas** les rendements de l'indice ; on l'utilise comme indicateur de régime ou de liquidité, pas comme signal directionnel.

---

## 9. Trading peu fréquent et liquidité

- **Hearn (2014)**, *Research in International Business and Finance* 30(1), 91-110 : sur l'échantillon étudié, **plus de 90 % de rendements journaliers nuls** à la BRVM [NON VÉRIFIÉ : texte non lu, période de l'échantillon inconnue. À titre de comparaison, les BOC 2018-2024 donnent 27 à 35 % de variations nulles]. Mesures utilisées : spread, part de rendements nuls (Lesmond et al. 1999), indicateur de Liu (2006). Source : https://www.sciencedirect.com/science/article/abs/pii/S0275531913000287 (medium).
- **Mlambo & Biekpe (2005)**, *Investment Analysts Journal* 61, 29-40 : le trading peu fréquent fausse les tests d'efficience ; il faut utiliser des rendements d'une transaction à l'autre. Source : https://www.researchgate.net/publication/290792299 (medium).
- **Ouattara (2016)**, MPRA n°75391 : impact du passage à la cotation en continu sur la liquidité de la BRVM. Résultats chiffrés non lus. Source : https://econpapers.repec.org/RePEc:pra:mprapa:75391 (low).
- **Hikouatcha et al. (2016)**, cité dans des sources secondaires : sur la BRVM, le **ratio d'illiquidité d'Amihud** décrit mieux la liquidité que la rotation. Source : https://www.researchgate.net/figure/Amihud-2002-illiquidity-ratio_tbl2_309815405 (low).
- **Situation en 2025-2026 (BOC, high)** :
  - **Corrigé** : il n'est pas vrai que tous les titres non suspendus ont un volume non nul chaque jour. Sur les 466 séances du 03/01/2025 au 20/11/2026, on compte **166 séances-titres « NC »** (non coté : ouverture et clôture affichées « NC », variation 0,00 %, aucun volume), en plus de 452 séances-titres suspendues (« SP »). Exemple : le 15/01/2025, SICC, NEIC et SAFC sont NC, et 41 titres sont échangés. Le 20/11/2026, 46 titres sont échangés sur 48 (confirmé) ;
  - la valeur médiane échangée par titre et par jour (médiane des médianes) est d'environ **10 MFCFA** (réplication : 10,24 MFCFA sur 47 titres, avec la valeur estimée par volume × clôture) ;
  - elle va d'environ 152 à 155 MFCFA (SNTS) à moins de 0,5 MFCFA (UNLC 0,38 ; SICC 0,16).
  - Note de parsing : la colonne « Valeur » du BOC peut déborder sur la ligne suivante pour les très gros montants (SNTS le 20/11/2026 : « 2 988 573 » puis « 270 » à la ligne). Il faut la contrôler par volume × cours.
  - Contexte historique (BOC, vérificateur) : part des séances-titres à variation nulle de 26,9 % (2018) à 34,8 % (2020), 30,6 % en 2024, 22,9 % en 2025 et 14,9 % en 2026. **L'amélioration de la liquidité date surtout de 2025-2026, pas de 2013.**
  - Le problème n'est donc plus l'absence de cotation, mais la **profondeur** : de petits volumes suffisent à fixer les cours.

---

## 10. Intégration régionale et internationale, contagion, comportement grégaire

| Étude | Période | Méthode | Résultat | Lien | Confiance |
|---|---|---|---|---|---|
| Emenike (2021), *African Development Review* 33(2), 288-299 | n.d. | Corrélations, Granger, BEKK-GARCH(1,1) | Interdépendance **faible** en Afrique de l'Ouest ; **pas de causalité BRVM-Ghana** ; **rétroaction BRVM-Nigeria** ; la région est liée surtout via le Nigeria | https://onlinelibrary.wiley.com/doi/abs/10.1111/1467-8268.12575 | medium |
| Kyei, Ampong, N'Da & Owusu Junior (2024), *Research in Globalization* | n.d. | Entropie de transfert de Rényi, CEEMDAN, DCC-GARCH | L'information circule surtout **de l'ESG mondial vers la BRVM** ; la plupart des flux par échelle de temps sont **non significatifs** | https://www.sciencedirect.com/science/article/pii/S2590051X24000017 | medium |
| *International Review of Financial Analysis* 82 (2022), 102128 (auteurs non relevés) | 2005-2020 | Tests de contagion sur plusieurs crises | Contagion significative **seulement pendant la crise de 2008** du point de vue régional ; contagion Covid signalée pour la Côte d'Ivoire, mais pas significative en moyenne | https://thuvienso.hoasen.edu.vn/server/api/core/bitstreams/5eb96cca-3863-4850-a46e-4b7c3a702db6/content | low |
| « The resilience and vulnerability of WAEMU stock market amid COVID-19 », *Cogent Economics & Finance* 13(1) (2025) | Covid | Étude d'événement, Markov à changement de régime, régression à seuil | Effets **qui dépendent du régime et du secteur** : industrie et transport fragiles, agriculture résiliente ; les cas confirmés et les mesures strictes réduisent les rendements | https://www.tandfonline.com/doi/abs/10.1080/23322039.2025.2555413 | medium |
| Bassène, Diallo & Ba (2024), *Bankers, Markets & Investors* | n.d. | Régression quantile (fondamentaux UEMOA, facteurs mondiaux dont le CAC 40) | La dynamique de la BRVM est difficile à lire, ce qui réduit son attractivité ; coefficient du CAC 40 non lu | https://shs.cairn.info/revue-bankers-markets-et-investors-2024-1-page-3?lang=en | low |
| Kamagaté (2025), mémoire HEC Montréal | n.d. | VAR, VECM | La faible intégration protège à court terme des chocs mondiaux, mais des liens de long terme existent | https://biblos.hec.ca/biblio/memoires/kamagate_abdoul_aziz_m2025.pdf | low |
| Nyakurukwa & Seetharam (2023), *International Finance* 26(1), 2-18 | 7 marchés africains (classement MSCI), 2011-2021 ; présence de la BRVM non confirmée | Entropie de transfert | Intégration africaine **faible** ; l'Afrique du Sud est l'émetteur principal | https://onlinelibrary.wiley.com/doi/full/10.1111/infi.12419 | medium (Afrique) |
| Guney, Kallinterakis & Komba (2017), *JIFMIM* 47, 152-175 | 8 marchés frontières africains, janvier 2002 à juillet 2015 (BRVM incluse selon une source secondaire) | Dispersion transversale (CSAD, CSSD) | **Comportement grégaire significatif** sur toute la période, lié à l'opacité de l'information ; les États-Unis et l'Afrique du Sud ne le déclenchent qu'occasionnellement | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2860897 | medium |

**Verdict.** La faible corrélation avec l'extérieur est un **atout de diversification**, pas un signal. Les variables externes (Nigeria, CAC 40, stress mondial) n'ont qu'un pouvoir prédictif faible et sont à tester comme variables de régime. Le comportement grégaire et le sentiment sont des pistes **comportementales** cohérentes avec le retour à la moyenne observé.

---

## 11. Analyse technique et apprentissage automatique

- **BRVM, mémoire de Tamandja (environ 2007)** : quelle que soit la combinaison de filtres et de longueurs de moyennes mobiles testée, la règle **n'a pas battu l'achat-conservation**. Source : https://www.memoireonline.com/04/07/410/m_efficience-boursiere-gestion-de-portefeuille-brvm5.html (low : mémoire, période ancienne du fixing).
- **Marchés émergents (BRICS et autres, 2000-2015)** : peu de combinaisons de moyennes mobiles battent l'achat-conservation. Source : https://www.sciencedirect.com/science/article/abs/pii/S1062940816300742 (medium).
- **Nairobi** : des règles contrariantes battraient l'achat-conservation après coûts ; extrait fragmentaire. Source : https://www.researchgate.net/publication/285996873 (low).
- **Nigeria** : des règles de momentum profitables avec contrôle du *data snooping* (*GBER* 2024, section 5.1 ; medium).
- **Coûts en Afrique** : le coût aller-retour peut atteindre **4 %** dans plusieurs marchés d'Afrique de l'Est et au Ghana, selon l'OCDE. Source : https://www.oecd.org/content/dam/oecd/en/publications/reports/2025/11/africa-capital-markets-report-2025_a973e07d/7d26e1d3-en.pdf (medium ; la BRVM n'est pas chiffrée dans l'extrait).
- **Apprentissage automatique (LSTM, etc.) appliqué à la BRVM** : **aucune étude évaluée par les pairs trouvée**. Les plates-formes commerciales (richbourse, brvm-analytics…) ne publient pas de validation hors échantillon.

---

## 12. Synthèse : inefficiences exploitables et robustesse

| Inefficience candidate | Appui dans la littérature | Robustesse | Exploitable après coûts ? | Décision pour la plate-forme |
|---|---|---|---|---|
| Retour à la moyenne à court terme (indices) | Gbenro & Moussa 2019 [chiffres NON VÉRIFIÉS] ; Diallo et al. 2021 ; Smith 2008 | Moyenne : la vitesse varie et diminue avec le temps. Sur 2024-2026, ρ1 du Composite vaut 0,012, donc pas de retour à la moyenne visible au pas journalier | Difficile au niveau de l'indice (pas de produit indiciel liquide) ; possible au niveau des titres | **Signal candidat n°1**, à valider titre par titre |
| Rebond après plafond bas (−7,5 %) | Aucune étude publiée ; vérification interne 2025-2026, **répliquée** par le vérificateur (médiane +3,09 %, n = 396) | Faible : échantillon court, marché haussier, événements regroupés (jusqu'à 14 le même jour) | Avantage brut médian d'environ 3,1 % sur 5 jours contre environ **2,5 %** de coûts (valeur corrigée), soit environ +0,6 % net en médiane : **très marginal** | **Hypothèse à tester** en walk-forward, avec filtres de liquidité |
| Continuation après plafond haut | Aucune étude publiée ; vérification interne | Concentrée dans le gap, qu'on ne peut pas capter | **Non** | Ne pas courir après ; garder comme indicateur d'excès de demande |
| Tendance de l'indice sur plusieurs semaines (VR(20) > 1) | Vérification interne ; **réplication : significatif seulement en 2026**, VR inférieurs à 1 en 2024-2025 | **Faible** : un seul épisode haussier | Possible en **allocation tactique** (exposition actions ou liquidités), à prouver hors échantillon | Filtre de régime, pas signal de sélection |
| Effets calendaires (jour, mois, Ramadan) | Tachiwou 2010 ; Ferrouhi et al. 2021 ; RMEEF 2016 | **Faible** : contredits par Obalade et al. 2022 et Djahoué 2025 | **Non** | Variables de contrôle seulement |
| Sous-évaluation à l'introduction en bourse | *Revue du Chercheur* ; Zenodo 5052654 | Moyenne : significative après 2011 | Oui si l'on obtient une allocation, souvent réduite en cas de sursouscription | Module « IPO » : souscrire, puis gérer la sortie sur plusieurs séances au plafond |
| Prévisibilité par M1 et M2 (forme semi-forte) | Toe et al. 2023 | Faible à moyenne | À tester, en tenant compte du **délai de publication** BCEAO | Variable macro mensuelle |
| Facteurs valeur, investissement, illiquidité | Hearn et al. 2025 (Afrique frontière) ; Zaremba (frontières) | Moyenne hors BRVM ; **non estimée** sur la BRVM | Probable à horizon long (mensuel), coûts faibles par rotation | **Moteur principal du portefeuille long terme**, à estimer localement |
| Comportement grégaire et sentiment | Guney et al. 2017 ; Djahoué 2025 | Moyenne | Indirect : volatilité, retournements | Indicateur de risque |

**Conclusion générale.** Les inefficiences les plus solides sont **lentes** (facteurs, rendement du dividende, valeur) ou **microstructurelles** (retour à la moyenne près des limites, sur des titres peu profonds). Les secondes sont **difficiles à exécuter** à cause de la profondeur et des coûts. Pour un investisseur particulier, l'avantage durable vient plus probablement :

1. d'une **sélection multifactorielle disciplinée** (valeur, rendement, qualité, faible volatilité) rééquilibrée peu souvent ;
2. d'**entrées opportunistes** sur les excès à la baisse ;
3. d'un **contrôle strict des coûts et du risque**.

Les règles techniques fréquentes ne sont pas la piste privilégiée. Rien de tout cela ne garantit un gain.

---

## 13. Implications pour la plate-forme : paramètres prêts à coder

```yaml
# brvm_alpha/config/research_priors.yaml (proposition, issue de la revue 02)
market_rules:
  price_limit_pct: 7.5            # Instruction I-A BRVM (PDF du 22/01/2013) ; VÉRIFIÉ : 0 dépassement 2023-2026 dans les BOC
  limit_reference: "adjusted_reference_price"   # VÉRIFIÉ : la limite porte sur le cours de référence ajusté (dividende, split) ;
                                  # BOC 2018-2022 : la variation publiée les jours de détachement est calculée sur le cours non ajusté (> 7,5 % possible)
  limit_applies_to_new_listings: true   # VÉRIFIÉ : BBGC 25-29/09/2026, 3 séances à ~+7,45 %
  tick_rounding_can_exceed_limit: true  # ETIT 13 -> 14 FCFA = +7,69 % (2021)
  limit_hit_threshold_pct: 7.0    # seuil "touché" utilisé dans la vérification (pas de cotation ≈ arrondis)
  dynamic_band_pct: 2.0           # [NON VÉRIFIÉ] ±2 % en continu (±3 % si pas de cotation < 5 FCFA), source pédagogique seule ; absent de l'I-A 2013 et du RG 2022
  continuous_trading_since: "2013-09-16"   # VÉRIFIÉ brvm.org/fr/historique
  daily_sessions_since: "2001-11-12"       # brvm.org/fr/historique (l'I-A de 2013 décrit encore lundi, mercredi et vendredi : obsolète)
  boc_row_flags: ["SP", "NC", "(d)", "(V)", "(Val-T)"]   # suspendu ; non coté ; marqueurs observés autour des dividendes et du split Sonatel
corporate_actions_verified:
  - {symbol: SNTS, type: split, ratio: 10, last_pre_split_session: "2026-10-23", first_split_session: "2026-10-26"}   # BOC
indices:
  brvm10_last_published: "2022-12-30"      # BOC ; remplacé par BRVM 30 (base 100 le 02/01/2023)
costs:                            # par côté, en % du montant
  brvm_fee_pct: 0.20              # VÉRIFIÉ brvm.org/fr/node/312 (consulté le 22/11/2026)
  dcbr_fee_pct: 0.10              # VÉRIFIÉ brvm.org/fr/node/312
  sgi_commission_pct: 0.80        # [NON VÉRIFIÉ] hypothèse centrale ; fourchette secondaire 0,2-1,5 % ; à remplacer par le barème réel de la SGI
  taxes_on_commission_pct: 18.0   # [NON VÉRIFIÉ] taux non publié par brvm.org ; la revue 01 utilise 10 % (TAF) : à trancher sur un avis d'opéré réel
  round_trip_baseline_pct: 2.5    # CORRIGÉ (était 2.0) : 2 x (0,30 + 0,80 x 1,18) = 2,49 % ; 2,36 % si taxe à 10 % ; 2,20 % sans taxe
  round_trip_stress_pct: 3.0      # ≈ 2 x (0,30 + 1,00 x 1,18) = 2,96 % ; avec un courtage de 1,5 % : 4,14 %
  slippage_bps_per_10pct_adv: 50  # hypothèse à calibrer sur le carnet ; aucune source publiée
liquidity_filters:
  min_median_daily_value_fcfa: 10_000_000   # ≈ médiane des titres 2025-2026 (BOC)
  hard_min_median_daily_value_fcfa: 2_000_000
  max_position_pct_of_adv: 10
  illiquidity_metric: amihud      # Hikouatcha et al. 2016 (cité) ; Hearn 2014 : part des rendements nuls
benchmarks:
  primary: "BRVM COMPOSITE TOTAL RETURN"   # l'indice de prix exclut des dividendes de l'ordre de 7 %/an
  secondary: ["BRVM COMPOSITE", "BRVM 30", "BRVM PRESTIGE"]
efficiency_monitor:               # tests réestimés chaque semaine, fenêtre glissante
  window_days: 250
  variance_ratio_q: [2, 5, 10, 20]   # Lo-MacKinlay z* robuste + Chow-Denning + Wright (N'Dri 2015)
  runs_test: true
  hurst_wavelet_on_sector_indices: true   # Diallo et al. 2021
  alert_abs_z: 1.96
  current_estimates_2024_2026: {VR10: 1.37, z10: 1.84, VR20: 1.70, z20: 2.59}   # CORRIGÉ par réplication (était 1.40/2.00 ; 1.77/2.87)
  subperiod_estimates:            # réplication du vérificateur, Lo-MacKinlay z* robuste
    "2024-11-04_2025-12-31": {VR10: 0.84, z10: -0.72, VR20: 0.76, z20: -0.76}
    "2026-01-01_2026-11-20": {VR10: 1.74, z10: 2.45, VR20: 2.34, z20: 3.36}
  chow_denning_crit_5pct_4q: 2.49
mean_reversion:
  prior_half_life_days: {composite: 7, brvm10: 2}   # [NON VÉRIFIÉ] Gbenro & Moussa 2019 (2005-2018), texte non lu ;
                                  # ne PAS appliquer au BRVM 30 (indice différent, créé en 2023) ;
                                  # grandeur modélisée à identifier (incompatible avec un AR(1) des rendements : rho1 = 0,012)
  use_prior: false                # tant que le texte n'est pas lu : estimer la demi-vie localement
  reestimate_window_years: [2, 4]                          # fenêtres de l'article : 2/4/6/8 ans [NON VÉRIFIÉ]
  asymmetry_term: true            # asymétrie faible mais modélisée
signals_candidate:
  limit_down_rebound:
    trigger: "close_var_pct <= -7.0 and not ex_dividend_window(t-1..t+2) and not corporate_action"
    entry: "open_t+1 (limit order <= open + 1 tick)"
    hold_days: 5
    in_sample_2025_2026: {median_ret_pct: 3.09, hit_rate: 0.62, n: 391, uncond_median_pct: 0.07}
    replication_verifier: {median_ret_pct: 3.09, hit_rate: 0.62, n: 396, uncond_median_pct: 0.06}   # CONFIRMÉ
    in_sample_liquid_half: {median_ret_pct: 3.55, hit_rate: 0.71, n: 91}   # sensible au seuil : 4.34 / 0.72 / n = 125 avec seuil 10 MFCFA (26 titres)
    median_net_of_baseline_cost_pct: 0.6   # 3,09 - 2,5 : avantage très marginal
    status: "HYPOTHESE - walk-forward + couts obligatoires avant activation"
  limit_up_chase:
    status: "REJETE - continuation concentree dans le gap overnight (median o->c5 = +0.14 % vs +0.07 %)"
calendar_effects:
  use_as: "controls_only"         # instables : Obalade et al. 2022 ; Djahoué 2025
  dummies: [weekday, month, ramadan, december]
volatility_model:
  default: "EGARCH(1,1)-skewt"    # Djahoué 2018 [NON VÉRIFIÉ : texte non lu] ; choisir par critère d'information sur nos données
  alternatives: ["GJR-GARCH(1,1)-t", "FIGARCH"]
  exogenous: ["sentiment_index", "inflation_uemoa", "usd_xof", "cny_xof"]   # Djahoué 2025 ; Ouattara & Koy 2024
factor_model:
  candidates: ["FF5", "FF6", "FF3+ILLIQ"]   # Hearn et al. 2025 (Afrique frontière ; présence de la BRVM NON VÉRIFIÉE)
  rebalance: "monthly"
  min_names_per_leg: 8            # 48 titres seulement : portefeuilles tertiles, pas déciles
macro_semi_strong:
  predictors: ["M1", "M2"]        # Toe et al. 2023 (Granger/Johansen) [NON VÉRIFIÉ ; conclusions de l'article jugées fragiles]
  publication_lag_months: 2       # hypothèse prudente, à vérifier sur le calendrier de la BCEAO
validation:
  min_oos_t_stat: 3.0             # discipline multi-tests (seuil de type Harvey-Liu-Zhu)
  reality_check: ["White RC", "Hansen SPA"]   # contrôle du data snooping
  subperiod_stability: ["pre-2013 fixing", "2013-2019", "2020-2022 covid", "2023+ new indices"]
  embargo_days: 5
  require_positive_after_stress_costs: true
```

**Règles d'implémentation :**

1. **Rendements.** Calculer les rendements d'une transaction à l'autre et marquer les jours où la variation est nulle ou le volume quasi nul. Traiter à part les lignes « NC » (non coté : pas une variation nulle, mais une absence de cotation) et « SP » (suspendu). Utiliser le **cours précédent publié** (ajusté en 2025-2026) plutôt que la clôture de la veille, et contrôler les jours de BOC manquants (fichiers `.missing`). Sur l'historique d'avant 2013, ne jamais utiliser les rendements d'indice bruts dans un test d'efficience sans correction du trading non synchrone (Mlambo & Biekpe 2005).
2. **Ajustement des cours.** Neutraliser les détachements de dividendes et les opérations sur titres avant de calculer un signal : fractionnements (comme celui de Sonatel, 1 pour 10, effectif le 26/10/2026), droits. Sinon on obtient de faux plafonds bas et de faux rebonds.
3. **Exécution.** Modéliser la file d'attente au plafond : un ordre au cours limite peut rester non exécuté. Le prix d'entrée simulé après un événement est **l'ouverture de t+1**, jamais la clôture de t.
4. **Sélection.** Avec 48 titres, utiliser des tertiles ou des rangs et exiger au moins 8 titres par jambe. Ventes à découvert : non disponibles en pratique, donc on construit des stratégies **acheteuses avec surpondérations**.
5. **Rapport utilisateur.** Afficher en permanence la performance nette des frais face au **Composite Total Return**, l'intervalle de confiance et le message : **« performance passée ≠ garantie »**.

---

## 14. Questions ouvertes

1. Textes intégraux à lire dès que l'accès réseau le permet :
   - Gbenro & Moussa 2019 : seuils, coefficients d'asymétrie, période exacte ;
   - Ferrouhi et al. 2021 : coefficients ;
   - Djahoué 2018 : période ;
   - l'article d'*Applied Financial Economics* 2013 : auteur ;
   - Toe et al. 2023 : statistiques de ratio de variance ;
   - Hearn et al. 2025 : liste des pays, présence de la BRVM.
2. Version en vigueur du **seuil dynamique** (±2 % ou ±3 %) et du mécanisme de réservation en continu : à confirmer dans les instructions BRVM les plus récentes.
3. Barème réel du courtage de la SGI retenue, et assiette de la TVA ou de la TAF.
4. Existence d'études non indexées (mémoires CESAG, UFHB, BCEAO, Revue Africaine de Gestion) sur le momentum, le détachement de dividendes et la dérive post-résultats à la BRVM. Rien n'a été trouvé via WebSearch.
5. Le rebond après plafond bas survit-il :
   - à l'extension de l'échantillon à 2014-2024 (fichiers BOC en cours de téléchargement) ;
   - à une phase baissière ;
   - aux coûts réels ?
6. Effet des changements d'indices de 2023 (BRVM 30, Prestige, Principal) sur la comparabilité des séries BRVM 10.

---

## 15. Sources

**Primaires BRVM**

- BOC du 20/11/2026 : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (copie locale `data/boc_text/boc_20261120.txt.gz`)
- Règles de négociation, Instruction I-A sur les écarts maximaux : https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf
- Règlement général (1er juillet 2022) : https://www.brvm.org/sites/default/files/rg_brvm_-_apres_approbation_crepmf_sept_2021_01_07_2022_bis.pdf
- Frais applicables : https://www.brvm.org/fr/node/312
- Fiscalité (renvoi à la directive 02/2010/CM/UEMOA, sans taux) : https://www.brvm.org/fr/node/313
- Historique de la BRVM (cotation quotidienne le 12/11/2001, T+3 le 02/07/2007, cotation en continu le 16/09/2013) : https://www.brvm.org/fr/historique
- BOC utilisés par le vérificateur (copies locales dans `data/boc_text/`) : https://www.brvm.org/sites/default/files/boc_20221230_2.pdf ; https://www.brvm.org/sites/default/files/boc_20230102_2.pdf ; https://www.brvm.org/sites/default/files/boc_20250102_2.pdf ; https://www.brvm.org/sites/default/files/boc_20251231_2.pdf ; https://www.brvm.org/sites/default/files/boc_20260925_2.pdf ; https://www.brvm.org/sites/default/files/boc_20261023_2.pdf ; https://www.brvm.org/sites/default/files/boc_20261026_2.pdf
- Passage à la cotation en continu : https://www.financialafrik.com/2013/09/17/bourse-afrique-abidjan-bascule-dans-la-cotation-en-continu/ ; https://african-markets.com/fr/bourse/brvm/la-brvm-passe-a-la-cotation-en-continu

**Efficience**

- Appiah-Kusi & Menyah 2003 : https://onlinelibrary.wiley.com/doi/10.1016/S1058-3300%2802%2900073-3
- Mlambo, Biekpe & Smit 2003 : https://ideas.repec.org/a/afj/journl/v5y2003i1p16-35.html
- Mlambo & Biekpe 2005 : https://www.researchgate.net/publication/290792299
- Mlambo & Biekpe 2007 : https://mpra.ub.uni-muenchen.de/25968/ ; https://www.tandfonline.com/doi/abs/10.1080/10293523.2007.11082489
- Smith 2008 : https://onlinelibrary.wiley.com/doi/10.1111/j.1813-6982.2008.00171.x
- Léon 2007 : https://aisberg.unibg.it/retrieve/e40f7b84-1278-afca-e053-6605fe0aeaf2/LEON%20suppl.%202007.pdf
- N'Dri 2015 : https://redfame.com/journal/index.php/aef/article/view/751 ; https://www.researchgate.net/publication/276122762
- Diallo, Mendy & Burlea-Schiopoiu 2021 : https://pubmed.ncbi.nlm.nih.gov/33553713/ ; https://www.cell.com/heliyon/fulltext/S2405-8440(20)32700-6
- Toe, Toe & Zoungrana 2023 : https://link.springer.com/article/10.1007/s43546-023-00550-0
- Houndalidji et al. 2024 : https://www.scirp.org/journal/paperinformation?paperid=138677
- Gil-Alana et al. 2025 : https://doi.org/10.1108/JES-04-2022-0238
- Gbenro & Moussa 2019 : https://doi.org/10.3390/jrfm12010038 ; https://www.researchgate.net/publication/331558567
- Doumbia 2023 : https://www.researchgate.net/publication/374899681
- *Dirassat Iqtissadiya* 2025 : https://asjp.cerist.dz/en/downArticle/67/12/1/267468
- Revues de littérature : https://ideas.repec.org/a/eee/ememar/v55y2023ics1566014123000353.html ; https://www.intechopen.com/chapters/73879

**Calendrier**

- Tachiwou 2010 : https://pdfs.semanticscholar.org/08f5/b4d4d967d38cb55236965669ea05af4889c2.pdf
- MPRA 24907 : https://mpra.ub.uni-muenchen.de/24907/1/MPRA_paper_24907.pdf
- Ben Mrad Douagi et al. 2019 : https://ideas.repec.org/a/asi/ajoerj/v9y2019i2p38-45id4274.html ; https://www.researchgate.net/publication/357351015
- Ferrouhi et al. 2021 : https://www.tandfonline.com/doi/full/10.1080/23322039.2021.1978639
- RMEEF 2016 : https://doi.org/10.1515/rmeef-2015-0039
- Obalade et al. 2022 : https://ojs.tripaledu.com/jefa/article/view/71
- Alloul & Ferrouhi 2025 : https://www.journals.vu.lt/omee/article/view/36475
- Djahoué 2025 : https://www.scirp.org/journal/paperinformation?paperid=147179

**Coupe transversale, risque et rendement**

- N'Dri 2007 : https://academicjournals.org/article/article1380545342_N%E2%80%99dri.pdf
- *Applied Financial Economics* 2013 : https://www.tandfonline.com/doi/abs/10.1080/09603107.2012.718062
- Kolani & Ekoue 2014 : https://www.researchgate.net/publication/315042349
- Olasehinde-Williams 2018 : https://researchleap.com/examination-relationship-volatility-expected-returns-brvm-stock-market/
- IJBD 2021 : https://www.inderscience.com/info/inarticle.php?artid=116970
- Essingone & Diallo 2022 : https://doi.org/10.4236/jfrm.2022.111011
- Hearn & Piesse 2010 : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1342031
- Hearn et al. 2025 : https://www.sciencedirect.com/science/article/pii/S1057521924006847
- Zaremba (marchés frontières) : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3060876 ; https://quantpedia.com/equity-factor-strategies-in-frontier-markets/
- GBER 2024 (Afrique, règles techniques) : https://www.inderscience.com/info/inarticle.php?artid=137616

**Dividendes et IPO**

- ESJ 2017 : https://eujournal.org/index.php/esj/article/download/9793/9297
- Ouattara 2017 : https://mpra.ub.uni-muenchen.de/79839/1/MPRA_paper_79839.pdf
- Sous-évaluation des IPO : https://zenodo.org/records/4009093
- IPO bancaires : https://zenodo.org/records/5052654
- Communication financière : https://zenodo.org/records/21847511
- Détachement Tractafric (anecdote) : https://dabafinance.com/en/news/brvm-stocks-fall-for-second-week-as-sonatel-stock-split-nears

**Limites de variation (international)**

- Taïwan : https://www.researchgate.net/publication/222684404
- ChiNext : https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0287548
- Chine et Tunisie (revue) : https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4395215/
- Seuil dynamique (support pédagogique) : https://www.gpe-afrique.com/moodledata/filedir/c5/9b/c59ba17efa07ba3df075a7cdb160fee4a33f571e

**Volatilité et volume**

- Djahoué 2018 : http://www.scienpress.com/Upload/JAFB/Vol%208_6_4.pdf
- Djahoué (prépublication) : https://www.researchgate.net/publication/404732210
- Ouattara & Koy 2024 : https://www.jital.org/index.php/jital/article/view/461
- Gueyie et al. 2022 : https://www.mdpi.com/2227-7072/10/4/113

**Liquidité**

- Hearn 2014 : https://www.sciencedirect.com/science/article/abs/pii/S0275531913000287
- Ouattara 2016 : https://econpapers.repec.org/RePEc:pra:mprapa:75391

**Intégration, contagion, comportement grégaire**

- Emenike 2021 : https://onlinelibrary.wiley.com/doi/abs/10.1111/1467-8268.12575
- Kyei et al. 2024 : https://www.sciencedirect.com/science/article/pii/S2590051X24000017
- IRFA 2022 : https://thuvienso.hoasen.edu.vn/server/api/core/bitstreams/5eb96cca-3863-4850-a46e-4b7c3a702db6/content
- Cogent 2025 (Covid) : https://www.tandfonline.com/doi/abs/10.1080/23322039.2025.2555413
- Bassène et al. 2024 : https://shs.cairn.info/revue-bankers-markets-et-investors-2024-1-page-3?lang=en
- Kamagaté 2025 : https://biblos.hec.ca/biblio/memoires/kamagate_abdoul_aziz_m2025.pdf
- Nyakurukwa & Seetharam 2023 : https://onlinelibrary.wiley.com/doi/full/10.1111/infi.12419
- Guney et al. 2017 : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2860897

**Analyse technique et coûts**

- Tamandja (mémoire) : https://www.memoireonline.com/04/07/410/m_efficience-boursiere-gestion-de-portefeuille-brvm5.html
- BRICS (moyennes mobiles) : https://www.sciencedirect.com/science/article/abs/pii/S1062940816300742
- Nairobi : https://www.researchgate.net/publication/285996873
- OCDE 2025 : https://www.oecd.org/content/dam/oecd/en/publications/reports/2025/11/africa-capital-markets-report-2025_a973e07d/7d26e1d3-en.pdf
- Courtage des SGI (secondaire) : https://www.richbourse.com/common/apprendre/ouvrir-compte-titres ; https://www.westbourse.com/comparateur-sgi

---

## Vérification adversariale (2026-11-22)

> **Rôle** : vérificateur sceptique (domaine « brvm-academic »). **But** : essayer de réfuter les affirmations dont une erreur coûterait le plus cher, en priorité les paramètres codés en section 13.
>
> **Méthode et limites**
>
> - **Sources utilisables.** Seul `www.brvm.org` était joignable : Instruction I-A, Règlement général 2022, pages « frais », « fiscalité » et « historique ». S'y ajoutent les **BOC locaux 2017-2026** (`data/boc_text/`), relus avec un **parseur indépendant**, distinct des scripts du chercheur.
> - **Sources inaccessibles.** Le budget de recherche web partagé (WebSearch) était épuisé dès la première requête. Les hôtes `www.mdpi.com`, `pubmed.ncbi.nlm.nih.gov`, `redfame.com` et `www.scirp.org` sont refusés par le réseau de la session, et curl n'atteint ni Crossref, ni Wiley, ni Taylor & Francis, ni ScienceDirect, ni Springer. **Aucune étude académique n'a donc pu être revérifiée en ligne.** Elles sont classées « invérifiable », jamais « confirmées ». Aucune n'est déclarée réfutée faute de trace, puisque la recherche elle-même était impossible.
> - **Scripts du vérificateur** (dossier temporaire) : `/tmp/claude-0/-home-user-documentation/b095b722-74b3-5e89-8589-8e6133bd6c39/scratchpad/verif02/` (`varcheck2.py`, `panel.py`, `stats.py`).

| # | Élément vérifié | Valeur du chercheur | Résultat de la vérification | Verdict | Source |
|---|---|---|---|---|---|
| 1 | Limite statique `price_limit_pct` | 7,5 % | Le texte de l'I-A, article 2, dit bien ±7,5 % (actions et obligations). Les BOC 2023-2026 ne montrent aucun dépassement. Le PDF date du 22/01/2013 et non d'une date inconnue | **confirmé** | https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf ; BOC locaux |
| 2 | Base de la limite | « cours de référence » | La limite porte sur le cours de référence **ajusté**. Dans les BOC 2018-2022, on trouve 14 variations publiées au-delà de ±7,5 %. Les 6 examinées s'expliquent toutes : détachements BOABF, SMBC, CABC, SLBC ; fractionnement STBC ; pas de cotation ETIT. Paramètres ajoutés : `limit_reference`, `tick_rounding_can_exceed_limit` | **corrigé** (précision) | BOC du 29/04/2019, 28/08/2019, 28/07/2020, 18/08/2022, 31/07/2018, 20/12/2021 |
| 3 | Limite dès la 1re séance d'une IPO, gain d'introduction étalé | déduction non testée | BBGC fait +7,44 %, +7,44 % et +7,46 % du 25 au 29/09/2026 ; ECOC fait +7,49 % le 13/12/2017 | **confirmé** | https://www.brvm.org/sites/default/files/boc_20260925_2.pdf |
| 4 | `dynamic_band_pct` | 2,0 (3,0) | Absent de l'I-A 2013 et du RG 2022. L'article 37 du RG renvoie à une Instruction non trouvée. Pas de données intrajournalières pour le tester | **invérifiable** | https://www.brvm.org/sites/default/files/rg_brvm_-_apres_approbation_crepmf_sept_2021_01_07_2022_bis.pdf |
| 5 | `continuous_trading_since` | 2013-09-16 | brvm.org indique : « 16 Septembre 2013 : passage à la cotation en continu ». L'article 29 du RG a été modifié par la décision CREPMF 2013-060 du 29/06/2013 | **confirmé** | https://www.brvm.org/fr/historique |
| 6 | `brvm_fee_pct` / `dcbr_fee_pct` | 0,20 / 0,10 par côté | Texte exact : « actuellement 0.2 % et 0.1 % du montant de la transaction payables par l'Acheteur et par le Vendeur ». La page n'est pas datée | **confirmé** | https://www.brvm.org/fr/node/312 |
| 7 | `sgi_commission_pct` | 0,80 | brvm.org dit seulement que chaque SGI fixe ses tarifs, homologués par le régulateur. Aucun barème primaire consulté | **invérifiable** | https://www.brvm.org/fr/node/312 |
| 8 | `taxes_on_commission_pct` | 18 | Taux non publié par brvm.org ; la page Fiscalité renvoie seulement à la directive 02/2010/CM/UEMOA. La revue 01 du projet utilise 10 % (TAF) : **contradiction interne** | **invérifiable** | https://www.brvm.org/fr/node/313 |
| 9 | `round_trip_baseline_pct` | 2,0, « ≈ 2 × (0,30 + 0,80 × 1,18) » | **Erreur de calcul** : la formule donne 2,49 %. On obtient 2,36 % avec une taxe de 10 % et 2,20 % sans taxe. Le 2,0 % sous-estime les coûts | **réfuté → corrigé à 2,5** | calcul à partir de https://www.brvm.org/fr/node/312 |
| 10 | Chiffres du BOC du 20/11/2026 | 48 sociétés ; Composite 492,89 (+42,56 %) ; TR 198,63 (+49,19 %) ; PER 15,79 ; rendement 7,12 % ; rotation 0,16 ; 46 titres échangés | Tous identiques dans le BOC n° 222 | **confirmé** | https://www.brvm.org/sites/default/files/boc_20261120_2.pdf |
| 11 | Indice de référence TR (base 100 au 02/01/2025) et écart d'« environ 7 points par an » | — | Base confirmée. En 2025 : Composite +25,2 % (276,13 → 345,75) contre environ +33,1 % pour le TR. En 2026, au 20/11 : +42,56 % contre +49,19 %. Écart de 6,6 à 7,9 points | **confirmé** | BOC du 02/01/2025, du 31/12/2025 et du 20/11/2026 |
| 12 | `current_estimates_2024_2026` (VR) | VR(10) = 1,40, z\* = 2,00 ; VR(20) = 1,77, z\* = 2,87 | Réplication Lo-MacKinlay robuste (n = 503) : VR(10) = 1,37, **z\* = 1,84, non significatif** ; VR(20) = 1,70, z\* = 2,59. **La persistance vient entièrement de 2026** : VR(20) = 2,34 en 2026, contre 0,76 sur fin 2024-2025 | **corrigé** | BOC locaux, du 04/11/2024 au 20/11/2026 |
| 13 | Rebond après plafond bas `limit_down_rebound` | médiane +3,09 %, 62 % positifs, n = 391 | Réplication : médiane +3,09 % (+3,10 % chaîné), 62 % positifs, n = 396 sur 402 événements. Seuls 5 événements tombent un jour d'ajustement de cours. Sous-échantillon liquide : même sens, mais le chiffre dépend du seuil (+4,34 %, n = 125 avec un seuil de 10 MFCFA, contre +3,55 %, n = 91). **Net d'un coût de 2,5 %, la médiane tombe à environ +0,6 %** | **confirmé** (chiffres bruts) | BOC locaux 2025-2026 |
| 14 | Rejet de la poursuite des plafonds hauts `limit_up_chase` | médiane o→c5 +0,14 % contre +0,07 % | Réplication : +0,07 % (+0,15 % chaîné) contre +0,06 % sans condition, n = 714 | **confirmé** | BOC locaux 2025-2026 |
| 15 | « Chaque titre non suspendu a un volume non nul chaque jour » (2025-2026) | affirmation high | **Faux** : 166 séances-titres « NC » (non coté) hors suspensions sur 466 séances, par exemple SICC, NEIC et SAFC le 15/01/2025 | **réfuté** | https://www.brvm.org/sites/default/files/boc_20250115_2.pdf (copie locale) |
| 16 | Parts de variations nulles et datation du changement de liquidité | 19,7 % ; 24,0 % (2025) ; 15,0 % (2026) ; « régime changé depuis 2013 » | Réplication : 19,1 %, 22,9 % et 14,9 %, confirmés à l'arrondi près. Mais la part était de **27 à 35 % chaque année de 2018 à 2024** : le changement est récent (2025-2026) | **corrigé** (interprétation) | BOC locaux 2018-2026 |
| 17 | Autocorrélation d'ordre 1 empilée des titres | +0,096 | Réplication : +0,071, chiffre qui dépend de la définition | **corrigé** | BOC locaux 2025-2026 |
| 18 | `min_median_daily_value_fcfa` (médiane des médianes) | ≈ 10,2 MFCFA ; SNTS ≈ 155 ; UNLC et SICC < 0,5 | 10,24 MFCFA sur 47 titres ; SNTS 152 ; UNLC 0,38 ; SICC 0,16 | **confirmé** | BOC locaux 2025-2026 |
| 19 | Anecdote Tractafric : −11,42 % sur la semaine du détachement | −11,42 % | 4 290 le 16/10/2026, puis 3 800 le 23/10/2026, soit −11,42 %. Mais le dividende net de 183,92 FCFA représente environ 4,3 points : net, la baisse est d'environ −7,1 % | **confirmé** (avec réserve) | BOC du 16/10/2026 au 23/10/2026 |
| 20 | Fractionnement Sonatel (non chiffré dans la revue) | — | 1 pour 10 ; 43 850 le 23/10/2026, référence 4 385 ; 1re séance le 26/10/2026 ; dividende retraité de 1 740 à 174 | **confirmé** (fait ajouté) | https://www.brvm.org/sites/default/files/boc_20261026_2.pdf |
| 21 | Clé YAML `prior_half_life_days.brvm10_or_30` | demi-vie de 2 jours transposée au BRVM 30 | Le BRVM 10 est publié pour la dernière fois le 30/12/2022, puis remplacé par le BRVM 30 (base 100 le 02/01/2023). Rien ne justifie de transposer la demi-vie au BRVM 30 | **réfuté → clé renommée `brvm10`** | https://www.brvm.org/sites/default/files/boc_20230102_2.pdf |
| 22 | Demi-vies de Gbenro & Moussa (2019) : 7 jours (Composite) et 2 jours (BRVM 10) | medium | Texte inaccessible (hôte mdpi.com bloqué). Une demi-vie de 7 jours est incompatible avec un AR(1) des rendements (ρ1 = 0,012), donc la grandeur modélisée est à identifier. `use_prior: false` ajouté | **invérifiable** | https://doi.org/10.3390/jrfm12010038 (non consulté) |
| 23 | Djahoué (2018) : EGARCH avec Student asymétrique comme modèle par défaut | medium | Hôte non joignable | **invérifiable** | http://www.scienpress.com/Upload/JAFB/Vol%208_6_4.pdf (non consulté) |
| 24 | *Applied Financial Economics* 2013 : R² moyen de 20,40 % | medium | Hôte non joignable, auteur inconnu. Incohérence apparente : 20,4 % de R² laisse environ 80 % inexpliqué, pas « au moins 60 % » | **invérifiable** | https://www.tandfonline.com/doi/abs/10.1080/09603107.2012.718062 (non consulté) |
| 25 | Hearn (2014) : plus de 90 % de rendements journaliers nuls | medium | Hôte non joignable ; période de l'échantillon inconnue | **invérifiable** | https://www.sciencedirect.com/science/article/abs/pii/S0275531913000287 (non consulté) |
| 26 | Existence et détails des autres études citées : Appiah-Kusi & Menyah 2003, Smith 2008, Mlambo & Biekpe 2007, N'Dri 2015, Diallo et al. 2021, Toe et al. 2023, Hearn et al. 2025, Obalade et al. 2022, Ferrouhi et al. 2021, Djahoué 2025 | medium | Aucune ne peut être consultée ce jour. Les références restent celles du chercheur ; aucune n'est confirmée par le vérificateur | **invérifiable** | voir section 15 |

**Bilan** : 26 éléments contrôlés.

- **11 confirmés**, dont 8 sur sources primaires brvm.org ou BOC (n° 1, 3, 5, 6, 10, 11, 19, 20) et 3 par réplication indépendante (n° 13, 14, 18).
- **4 corrigés** : base de la limite (n° 2), interprétation et chiffres des ratios de variance (n° 12), datation du changement de liquidité (n° 16), autocorrélation (n° 17).
- **3 réfutés et corrigés dans le fichier** : coût aller-retour de 2,0 % porté à 2,5 % (n° 9), « cotation quotidienne de tous les titres » (n° 15), clé `brvm10_or_30` (n° 21).
- **8 invérifiables** :
  - 3 paramètres de marché ou de coût sans source primaire : seuil dynamique, courtage SGI, taxe (n° 4, 7, 8) ;
  - 5 groupes de résultats académiques (n° 22 à 26).

**Actions restantes avant de coder** :

1. Autoriser l'accès réseau à `doi.org`, `www.mdpi.com`, `www.tandfonline.com`, `www.sciencedirect.com`, `onlinelibrary.wiley.com`, `link.springer.com`, `www.scirp.org`, `redfame.com` et `pubmed.ncbi.nlm.nih.gov`, puis relire Gbenro & Moussa (2019), Djahoué (2018) et l'article d'*Applied Financial Economics* (2013).
2. Obtenir un avis d'opéré réel d'une SGI pour fixer le courtage et le taux de taxe, et aligner les revues 01 et 02.
3. Trouver l'Instruction BRVM en vigueur sur les écarts de cours par compartiment (seuil dynamique).
4. Déterminer à partir de quelle date le BOC publie un « cours précédent » ajusté les jours de détachement : non ajusté en 2018-2022, ajusté en 2025-2026, 2023-2024 non examinés.
