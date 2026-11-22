# 02 — Littérature académique et empirique sur la BRVM

> **Projet** : BRVM Alpha · **Module** : recherche / revue de littérature
> **Rédigé le** : 2026-11-22 · **Statut** : v1 (à réviser quand les textes intégraux seront accessibles)
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
| 2 | **Le retour à la moyenne à court terme est l'inefficience la mieux documentée.** Gbenro & Moussa (2019) estiment une demi-vie d'environ **7 jours pour le Composite** et d'environ **2 jours pour le BRVM 10** (2005-2018), avec une asymétrie faible et une vitesse de retour qui diminue légèrement dans le temps. | medium |
| 3 | **Les effets calendaires sont instables.** Selon les études, on trouve un effet lundi, un effet mercredi, un effet vendredi, un effet décembre ou un Ramadan à volatilité plus faible, mais ces effets disparaissent dans les modèles à fenêtre glissante (Obalade et al. 2022) ou dans les spécifications les mieux ajustées (RMEEF 2016). Ils ne sont **pas exploitables** comme signaux autonomes. | medium |
| 4 | **Aucune étude publiée sur le momentum transversal (Jegadeesh-Titman) propre à la BRVM n'a été trouvée.** Sur les marchés frontières en général, la valeur et le momentum sont les principaux moteurs de rendement (Zaremba et co-auteurs), mais ce résultat n'est pas spécifique à la BRVM. | medium (absence constatée) |
| 5 | **Le CAPM explique mal la BRVM.** La prime de risque est positive mais non significative en GARCH-M sur 2010-2018. Le modèle de Fama-French à 3 facteurs atteint un R² ajusté moyen de 20,4 % (28 titres, 2001-2008) et laisse au moins 60 % de la variance inexpliquée. | medium |
| 6 | **La volatilité est persistante et asymétrique (effet de levier).** L'EGARCH avec une loi de Student asymétrique est le meilleur modèle d'après Djahoué (2018). Le sentiment des investisseurs améliore les prévisions de volatilité (Djahoué 2025). | medium |
| 7 | **Le trading peu fréquent était extrême avant 2013** (plus de 90 % de rendements journaliers nuls selon Hearn 2014). La cotation en continu existe depuis le **16/09/2013**. Dans nos BOC 2025-2026, **chaque titre non suspendu affiche un volume non nul chaque jour**, et 19,7 % des séances-titres ont une variation nulle. Le régime de liquidité a donc changé, et les résultats anciens doivent être réestimés. | high (BOC) / medium (Hearn) |
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
| Limite de variation statique (actions et obligations) | ±7,5 % par rapport au cours de référence ; au-delà, la cotation est reportée | Instruction I-A (document non daté) | https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf | high (règle) / medium (version en vigueur) |
| Vérification empirique de la limite | max = +7,50 %, min = −7,50 % sur 21 528 séances-titres | 03/01/2025 → 20/11/2026 | calcul interne sur les BOC | high |
| Passage du fixing à la cotation en continu | 16/09/2013 | 2013 | https://www.financialafrik.com/2013/09/17/bourse-afrique-abidjan-bascule-dans-la-cotation-en-continu/ | high |
| Commissions BRVM / DC-BR | 0,2 % et 0,1 % du montant, payées par l'acheteur et par le vendeur | consulté le 22/11/2026 | https://www.brvm.org/fr/node/312 | high |
| Courtage des SGI | environ 0,2 % à 1,5 % selon la SGI ; tarifs homologués par le régulateur | 2026 | https://www.richbourse.com/common/apprendre/ouvrir-compte-titres ; https://www.westbourse.com/comparateur-sgi | low (sources secondaires) |

> Conséquence directe : l'indice **BRVM Composite est un indice de prix**, sans dividendes, alors que le rendement moyen du marché est d'environ 7 %. Pour savoir si une stratégie « bat les indices », il faut la comparer au **Composite Total Return**, sinon la surperformance est artificiellement gonflée d'environ 7 points par an.

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
| Gbenro & Moussa (2019), *Journal of Risk and Financial Management* 12(1), 38 | BRVM Composite et BRVM 10, journaliers, environ 2005-2018 | AR non linéaire asymétrique (Nam et al. 2006) avec innovations EGARCH, fenêtres glissantes de 2, 4, 6 et 8 ans | **Retour à la moyenne** ; **demi-vie d'environ 7 jours (Composite) et d'environ 2 jours (BRVM 10)** ; asymétrie faible ; la vitesse de retour du Composite diminue légèrement | https://doi.org/10.3390/jrfm12010038 | medium |
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

**Verdict.** Ces effets ne résistent ni au changement d'indice, ni au changement de période, ni à la fenêtre glissante. Ils sont **trop petits face à un coût aller-retour de l'ordre de 1,5 à 3 %** (section 2). Dans la plate-forme, on les garde comme **variables de contrôle**, pas comme signaux.

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
| « Applying the CAPM and the Fama–French models to the BRVM stock market », *Applied Financial Economics* 23(4), 275-285 (2013) ; auteur non vérifié | 28 sociétés, juillet 2001 à décembre 2008 | CAPM, Fama-French à 3 facteurs | Le CAPM est validé pour 11 titres ; avec Fama-French, le **R² ajusté moyen est de 20,40 %** ; **au moins 60 % de la variance reste inexpliquée** | https://www.tandfonline.com/doi/abs/10.1080/09603107.2012.718062 | medium |
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

- **Effet du détachement de dividende** : **aucune étude systématique trouvée**, seulement des anecdotes de presse. Exemple : Tractafric Motors CI a perdu 11,42 % sur la semaine de son détachement en octobre 2026 (https://dabafinance.com/en/news/brvm-stocks-fall-for-second-week-as-sonatel-stock-split-nears ; low).
- **Dérive post-annonce de résultats (PEAD)** : **aucune étude BRVM trouvée**.
- **Interaction avec les limites** : le rendement initial d'une IPO est plafonné à +7,5 % par séance. La sous-évaluation se répartit donc sur **plusieurs séances consécutives au plafond**. Il faut la mesurer sur plusieurs jours, pas sur le premier seul (déduction mécanique de la règle I-A, non testée dans la littérature).

---

## 7. Limites de variation : effet aimant et continuation

- **Règle** : écart maximal de ±7,5 % par séance par rapport au cours de référence. Si le fixing dépasse le seuil, la cotation est reportée et un prix indicatif est affiché au seuil franchi (Instruction I-A : https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf ; high). Un support pédagogique mentionne aussi un **seuil dynamique de ±2 %** (±3 % si le pas de cotation est inférieur à 5 FCFA), avec réservation de 5 minutes en séance continue (https://www.gpe-afrique.com/moodledata/filedir/c5/9b/c59ba17efa07ba3df075a7cdb160fee4a33f571e ; low, version en vigueur à confirmer).
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

**Autres statistiques de la même vérification :**

- Part des séances-titres à variation nulle : 24,0 % en 2025, 15,0 % en 2026.
- Part des séances-titres à ±7 % ou plus : 5,2 %.
- Corrélation d'ordre 1 des rendements journaliers des titres (empilés) : **+0,096**.
- BRVM Composite, rendements logarithmiques du 04/11/2024 au 20/11/2026 (n = 503) :
  - ρ1 = 0,012 ;
  - **VR(10) = 1,40 (z\* robuste = 2,00)** ;
  - **VR(20) = 1,77 (z\* = 2,87)** ;
  - VR(2) = 1,01 (z\* = 0,17).

**Interprétation prudente :**

1. **Plafond haut.** La continuation existe, mais elle est surtout **dans le gap de la nuit**, qu'on ne peut pas capter. Depuis l'ouverture de t+1, la médiane sur 5 jours (+0,14 %) est proche de celle sans condition (+0,07 %). **Courir après les plafonds hauts ne présente pas d'avantage démontré.**
2. **Plafond bas.** Le gap prolonge la baisse, puis vient un **rebond depuis l'ouverture de t+1**. L'effet est visible en 2025 comme en 2026 et plus marqué sur les titres liquides. Il est cohérent avec le retour à la moyenne de Gbenro & Moussa (2019), mais comporte des biais possibles :
   - échantillon de seulement 23 mois, en **marché fortement haussier** (Composite +42,6 % en 2026) ;
   - événements regroupés : jusqu'à 14 plafonds bas le même jour ;
   - ouverture parfois établie sur un **très petit volume**, donc non exécutable en taille ;
   - effets de *bid-ask bounce* ;
   - détachements de dividendes et opérations sur titres mal identifiés ;
   - **aucun coût déduit** : il faut compter un aller-retour de 1,6 à 3 %.
3. **Indice.** VR(10) et VR(20) supérieurs à 1 et significatifs indiquent une **persistance (tendance) sur plusieurs semaines** dans le régime 2024-2026. Ce n'est plus la marche aléatoire de N'Dri (2015, période 2002-2004). Les causes possibles : le régime de marché ou une dépendance qui varie dans le temps, comme le prévoit l'hypothèse des marchés adaptatifs. Ce résultat doit être **réestimé en fenêtre glissante**, pas extrapolé.

---

## 8. Volatilité (GARCH, asymétrie, mémoire longue)

| Étude | Période | Méthode | Résultat | Lien | Confiance |
|---|---|---|---|---|---|
| N'Dri (2007), *AJBM* 1(5) | 1999-2005, hebdomadaire | GARCH, GJR, EGARCH (lois N, t, GED) | Forte persistance de la volatilité | https://academicjournals.org/article/article1380545342_N%E2%80%99dri.pdf | medium |
| Djahoué, M. G. (2018), *Journal of Applied Finance & Banking* 8(6), 91-109 | BRVM 10 et Composite, journalier ; janvier 2010 à mai 2016 selon un résumé | 3 GARCH asymétriques, plusieurs lois | Rendements **asymétriques** avec **effet de levier** ; **EGARCH avec loi de Student asymétrique** meilleur pour le BRVM 10 ; EGARCH meilleur que GARCH pour le Composite | http://www.scienpress.com/Upload/JAFB/Vol%208_6_4.pdf | medium |
| Djahoué (prépublication, environ 2025-2026), « Investor Sentiment and Stock Market Volatility: Evidence from the West African Regional Stock Exchange » | n.d. | Famille FIGARCH, indice de sentiment | Forte persistance, asymétrie, **mémoire longue** ; l'indice de sentiment **améliore les prévisions de volatilité** | https://www.researchgate.net/publication/404732210 | low-medium |
| Ouattara, Z. & Koy, A. (2024), *Journal of International Trade, Logistics and Law* 10(1), 149-158 | Mars 2005 à septembre 2023 | GARCH(1,1) avec variables macroéconomiques | Relation inverse entre la volatilité et les taux USD, CNY et le taux moyen des crédits ; **l'inflation a un effet significatif** | https://www.jital.org/index.php/jital/article/view/461 | medium |
| Gueyie, Diallo & Diallo (2022), *International Journal of Financial Studies* 10(4), 113 | 05/01/2015 au 31/10/2022, indice et volume journaliers | Relation contemporaine, causalité de Granger | Pas de lien contemporain significatif ; **les rendements causent le volume (au sens de Granger)**, pas l'inverse | https://www.mdpi.com/2227-7072/10/4/113 | medium |

**Verdict.** Pour la prévision de volatilité (dimensionnement des positions, VaR), le modèle par défaut est un **EGARCH(1,1) avec loi de Student asymétrique**, comparé à GJR et FIGARCH. Le volume **ne prédit pas** les rendements de l'indice ; on l'utilise comme indicateur de régime ou de liquidité, pas comme signal directionnel.

---

## 9. Trading peu fréquent et liquidité

- **Hearn (2014)**, *Research in International Business and Finance* 30(1), 91-110 : sur l'échantillon étudié, **plus de 90 % de rendements journaliers nuls** à la BRVM. Mesures utilisées : spread, part de rendements nuls (Lesmond et al. 1999), indicateur de Liu (2006). Source : https://www.sciencedirect.com/science/article/abs/pii/S0275531913000287 (medium).
- **Mlambo & Biekpe (2005)**, *Investment Analysts Journal* 61, 29-40 : le trading peu fréquent fausse les tests d'efficience ; il faut utiliser des rendements d'une transaction à l'autre. Source : https://www.researchgate.net/publication/290792299 (medium).
- **Ouattara (2016)**, MPRA n°75391 : impact du passage à la cotation en continu sur la liquidité de la BRVM. Résultats chiffrés non lus. Source : https://econpapers.repec.org/RePEc:pra:mprapa:75391 (low).
- **Hikouatcha et al. (2016)**, cité dans des sources secondaires : sur la BRVM, le **ratio d'illiquidité d'Amihud** décrit mieux la liquidité que la rotation. Source : https://www.researchgate.net/figure/Amihud-2002-illiquidity-ratio_tbl2_309815405 (low).
- **Situation en 2025-2026 (BOC, high)** :
  - tous les titres non suspendus ont un volume non nul chaque jour (le 20/11/2026, 46 titres échangés sur 48) ;
  - la valeur médiane échangée par titre et par jour (médiane des médianes) est d'environ **10 MFCFA** ;
  - elle va d'environ 155 MFCFA (SNTS) à moins de 0,5 MFCFA (UNLC, SICC).
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
| Retour à la moyenne à court terme (indices) | Gbenro & Moussa 2019 ; Diallo et al. 2021 ; Smith 2008 | Moyenne : la vitesse varie et diminue avec le temps | Difficile au niveau de l'indice (pas de produit indiciel liquide) ; possible au niveau des titres | **Signal candidat n°1**, à valider titre par titre |
| Rebond après plafond bas (−7,5 %) | Aucune étude publiée ; vérification interne 2025-2026 | Faible : échantillon court, marché haussier, événements regroupés | Avantage brut médian d'environ 3 % sur 5 jours contre environ 2 % de coûts : **marginal** | **Hypothèse à tester** en walk-forward, avec filtres de liquidité |
| Continuation après plafond haut | Aucune étude publiée ; vérification interne | Concentrée dans le gap, qu'on ne peut pas capter | **Non** | Ne pas courir après ; garder comme indicateur d'excès de demande |
| Tendance de l'indice sur plusieurs semaines (VR(10) et VR(20) > 1) | Vérification interne 2024-2026 ; hypothèse des marchés adaptatifs | Faible à moyenne : dépend du régime | Possible en **allocation tactique** (exposition actions ou liquidités) | Filtre de régime, pas signal de sélection |
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
  price_limit_pct: 7.5            # Instruction I-A BRVM ; vérifié empiriquement (max |var| = 7.50 %, 2025-2026)
  limit_hit_threshold_pct: 7.0    # seuil "touché" utilisé dans la vérification (pas de cotation ≈ arrondis)
  dynamic_band_pct: 2.0           # ±2 % en continu (±3 % si pas de cotation < 5 FCFA), source pédagogique, à confirmer
  continuous_trading_since: "2013-09-16"
costs:                            # par côté, en % du montant
  brvm_fee_pct: 0.20              # brvm.org/fr/node/312
  dcbr_fee_pct: 0.10              # brvm.org/fr/node/312
  sgi_commission_pct: 0.80        # hypothèse centrale ; fourchette secondaire 0,2-1,5 % ; à remplacer par le barème réel de la SGI
  taxes_on_commission_pct: 18.0   # TVA/TAF sur commissions : SOURCE SECONDAIRE, à vérifier
  round_trip_baseline_pct: 2.0    # ≈ 2 x (0,30 + 0,80 x 1,18)
  round_trip_stress_pct: 3.0
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
  current_estimates_2024_2026: {VR10: 1.40, z10: 2.00, VR20: 1.77, z20: 2.87}
mean_reversion:
  prior_half_life_days: {composite: 7, brvm10_or_30: 2}   # Gbenro & Moussa 2019 (2005-2018)
  reestimate_window_years: [2, 4]                          # fenêtres de l'article : 2/4/6/8 ans
  asymmetry_term: true            # asymétrie faible mais modélisée
signals_candidate:
  limit_down_rebound:
    trigger: "close_var_pct <= -7.0 and not ex_dividend_window(t-1..t+2) and not corporate_action"
    entry: "open_t+1 (limit order <= open + 1 tick)"
    hold_days: 5
    in_sample_2025_2026: {median_ret_pct: 3.09, hit_rate: 0.62, n: 391, uncond_median_pct: 0.07}
    in_sample_liquid_half: {median_ret_pct: 3.55, hit_rate: 0.71, n: 91}
    status: "HYPOTHESE - walk-forward + couts obligatoires avant activation"
  limit_up_chase:
    status: "REJETE - continuation concentree dans le gap overnight (median o->c5 = +0.14 % vs +0.07 %)"
calendar_effects:
  use_as: "controls_only"         # instables : Obalade et al. 2022 ; Djahoué 2025
  dummies: [weekday, month, ramadan, december]
volatility_model:
  default: "EGARCH(1,1)-skewt"    # Djahoué 2018
  alternatives: ["GJR-GARCH(1,1)-t", "FIGARCH"]
  exogenous: ["sentiment_index", "inflation_uemoa", "usd_xof", "cny_xof"]   # Djahoué 2025 ; Ouattara & Koy 2024
factor_model:
  candidates: ["FF5", "FF6", "FF3+ILLIQ"]   # Hearn et al. 2025 (Afrique frontière)
  rebalance: "monthly"
  min_names_per_leg: 8            # 48 titres seulement : portefeuilles tertiles, pas déciles
macro_semi_strong:
  predictors: ["M1", "M2"]        # Toe et al. 2023 (Granger/Johansen)
  publication_lag_months: 2       # hypothèse prudente, à vérifier sur le calendrier de la BCEAO
validation:
  min_oos_t_stat: 3.0             # discipline multi-tests (seuil de type Harvey-Liu-Zhu)
  reality_check: ["White RC", "Hansen SPA"]   # contrôle du data snooping
  subperiod_stability: ["pre-2013 fixing", "2013-2019", "2020-2022 covid", "2023+ new indices"]
  embargo_days: 5
  require_positive_after_stress_costs: true
```

**Règles d'implémentation :**

1. **Rendements.** Calculer les rendements d'une transaction à l'autre et marquer les jours où la variation est nulle ou le volume quasi nul. Sur l'historique d'avant 2013, ne jamais utiliser les rendements d'indice bruts dans un test d'efficience sans correction du trading non synchrone (Mlambo & Biekpe 2005).
2. **Ajustement des cours.** Neutraliser les détachements de dividendes et les opérations sur titres (fractionnements comme celui de Sonatel, droits) avant de calculer un signal. Sinon on obtient de faux plafonds bas et de faux rebonds.
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
