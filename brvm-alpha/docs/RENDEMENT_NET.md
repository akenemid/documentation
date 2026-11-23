# Rendement net et pertes — cahier des charges et protocole du suivi sur papier (S2)

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
>
> Ce module ne promet aucun gain et ne rend aucune perte impossible.
> Statut de la plate-forme : toutes les variantes (A à I) et la référence REF sont **REJETÉES** sur leur test (S1).
> La plate-forme fonctionne en « indice discipliné », **à titre d'étude**.
> Le suivi sans argent réel (S2) commence le **mardi 01/12/2026**.
> Rien dans ce document n'autorise un achat avec de l'argent réel.

Ce fichier a deux parties.

- **Partie A — Le suivi sur papier, en français clair.** Un résumé du protocole (§8 et §13 du cahier), de la
  signature et des fichiers. Il n'ajoute aucune règle.
- **Partie B — Le cahier des charges, copie intégrale.** C'est le texte qui fait foi pour le code : les tests des
  portefeuilles `N`, `E-C`, `E-D` et `PLAN` sont écrits d'après lui (§8.7, étape 6). Seuls les chemins de travail du
  paragraphe « Dossiers cités » et du §15 sont remplacés par des repères neutres : `<mesures>/` (dossier des mesures,
  hors dépôt) et `<dépôt>/` (ce dépôt, dossier `brvm-alpha`).

En cas de différence entre les deux parties, la partie B fait foi, avec les notes de la copie ci-dessous.

L'empreinte SHA-256 de ce fichier est écrite dans chaque ligne de la déclaration signée (`empreinte_cahier`). Modifier
ce fichier après la signature change son empreinte : la date du commit fait foi.

Statut des chiffres : **Fait** (recalculable), **Estimation** (méthode citée, incertain), **Hypothèse** (supposé, non
vérifié). Les seuils marqués « Hypothèse de travail » sont des propositions : vous les validez ou les corrigez.

## Notes de la copie

Le recalcul indépendant du module a relevé trois écarts du texte d'origine. Le texte de la partie B n'est pas modifié ;
ces notes disent ce que le module applique.

1. **« Environ 26 % à 40 % »** (§0.3, maquette du §F1, §F6, §14). La règle du §F6, point 5 (bornes arrondies au point
   entier), appliquée à la plus petite médiane mesurée (25,48 %), donne **25 %**. Le module écrit « environ 25 % à
   40 % ». Le « 26 % » vient d'un arrondi en deux temps (25,48 → 25,5 → 26).
2. **Choc de 2018 subi par la référence (s_ref)** (§F4, étape 2). La mesure sur les fichiers publiés donne 0,293209. Le
   module retient la mesure **arrondie à 4 décimales (0,2932)**, comme le cahier ; la mesure brute reste dans le JSON
   (`valeur_mesuree`). Les tables du §F4 (bornes « haut », P_vérifiée) sont ainsi retrouvées au franc.
3. **Première ligne de l'écran quand les frais dépassent les dividendes** (§F1, cas limites). Sur l'écran, les montants
   supposés sont arrondis et précédés de « environ », avec leur statut (règle 10 du §1) : « environ 110 000 FCFA de
   frais par an pour environ 38 000 FCFA de dividendes attendus [supposé] ». Les montants au franc (102 166 pour
   38 458, soit 63 708 FCFA de moins par an) restent dans le détail (Markdown, JSON).

---

# Partie A — Le suivi sur papier, en français clair

## A1. En deux mots

1. On ne peut ni garantir un gain ni empêcher une perte.
2. Le suivi sur papier ne prouvera aucune règle par ses gains avant plusieurs années.
3. Il vérifie la « plomberie » : frais payés, ordres servis, argent qui dort, données manquantes.
4. Toute règle nouvelle doit être **écrite, datée et signée avant** d'être suivie. Sinon, elle ne pourra pas être jugée
   honnêtement.
5. La plate-forme ne passe aucun ordre, ne vend jamais seule et ne recommande pas d'argent réel avec les règles
   actuelles.

---

## A2. Ce que le suivi peut montrer, et ce qu'il ne peut pas [§8.1]

- **Le suivi ne peut pas prouver la référence par ses gains avant plusieurs années.** Dans son test, l'écart de suivi de
  la référence face au marché était de 4,31 % par an [Fait publié, `reports/validation_S1/metrics.json`]. Neuf fois sur
  dix, le hasard seul déplace donc son retard cumulé de moins de 5 points à 6 mois, 7 points à 12 mois et 12 points à
  36 mois [Estimation, hypothèse normale].
- **Le suivi vérifie la plomberie** : frais, exécution, argent qui dort, données.
- **Aucun essai ne sera prouvé par ses gains en un an.** Le plus petit avantage visible après un an est de 1,6 à
  3,3 points par an pour un seul essai [Estimation].
- **On ne classe jamais des essais par leur rendement.** Avec trois essais sans avantage réel, la chance qu'au moins un
  dépasse la référence par hasard est d'au plus 87,5 % ; avec cinq, d'au plus 96,9 % [Estimation, bornes hautes].

---

## A3. Les portefeuilles suivis [§8.6]

| Nom | Règle | Taille et tarif | Rôle | Compte dans m |
|---|---|---|---|---|
| `REF-S2` | article 1 : la règle telle qu'elle a été testée | 10 000 000 FCFA, tarif supposé | témoin | non |
| `N` | article 5 : la référence avec les notes de l'analyste | 10 000 000 FCFA, tarif supposé | essai à prétention de rendement | oui |
| `E-C`, `E-D` | articles 6 et 7 : la référence plus un seul écart (option 1 seulement) | 10 000 000 FCFA, tarif supposé | essais jugés sur le suivi | E-D oui ; E-C dès son premier écart au témoin |
| `PLAN` | l'ordre par défaut, avec la mémoire de la remise à niveau de janvier et les écarts déclarés « oui » | 10 000 000 FCFA, tarif supposé | vérification comptable | non |
| `MOI` | la même règle que `PLAN`, à votre taille et avec votre grille ; papier ou réel | votre montant en actions, votre grille | analyse de sensibilité, pas un essai | non |

`m` est le nombre d'essais à prétention de rendement : il durcit le seuil de chaque décision (§A5 ci-dessous).

---

## A4. Les articles de la déclaration

La commande `suivi declarer --modele` écrit ces articles dans un fichier, avec la proposition par défaut de chacun. Vous
remplissez la réponse de chaque article, puis vous signez (§A9).

### Article 1 — `REF-S2`, la référence telle qu'elle a été testée [§8.2]

Phrase : *Le panier de référence suit la règle testée : les 20 plus grosses sociétés éligibles, remises à niveau fin
janvier, sans les notes.*

| Élément | Valeur figée |
|---|---|
| Sélection et poids | variante REF (D8) : 20 plus grosses capitalisations éligibles, poids proportionnels à la capitalisation, plafonds de D8, 98 % investi |
| Calendrier | remise à niveau à la première décision de janvier ; positions gardées entre deux ; sorties forcées de la règle (filtres de risque, inéligibilité) |
| Dividendes | crédités nets à la date de paiement ; gardés en liquidités jusqu'à la remise à niveau |
| Arrondi, bande | vers le bas, ligne par ligne ; bande de 2 points par ligne |
| Exécution | cours moyen du jour suivant si le titre est échangé ; 10 % du volume du jour au plus ; report 10 séances |
| Notes de l'analyste | aucune (elles n'ont joué aucun rôle dans le test) |
| Coûts, capital | scénario « central » ; 10 000 000 FCFA |
| Départ | première décision le lundi 30/11/2026 (dernière séance avant le début du suivi, date figée, écrite dans l'article) ; première exécution à la première séance à partir du 01/12/2026 |
| Code | le moteur du test, plus un seul refus explicite : forfait de compte non nul (§4.3 du cahier) ; fabrique `brvm_alpha.suivi.temoin.temoin_model`, sans modification de `validation/runner.py` |

Ce témoin n'a pas besoin de signature : sa définition est celle du test. Un test automatique prouve que sa fabrique
redonne, au franc, les mêmes valeurs et les mêmes ordres que la fabrique du test.

**Budget de retard, écrit d'avance** [Estimation] : 3,3 à 4,2 points de moins que le marché la première année (frais
d'entrée compris), puis 1,7 à 2,6 points de moins par an. Aucune conclusion sur la référence avant 36 mois. L'alerte de
la spécification (retard relatif de 10 %) reste le seul seuil.

**Ce que le suivi vérifie sur la référence** : P1 identité comptable de chaque semaine (écart de 0 FCFA) ; P2 frais payés
contre frais prévus ; P3 part investie moyenne ; P4 part des titres servis ; P5 ordres déclenchés par un trou de
bulletins ; P6 coût de la remise à niveau de janvier ; P7 écart au marché en valeur de part ; P8 exécution sur papier en
mode « test » contre le moteur (les écarts sont publiés).

### Articles 2 à 4 — écarts d'exécution : des décisions humaines datées [§8.3]

> Ces écarts ne sont pas jugés sur leurs gains. Leur effet sur le rendement est celui d'être plus ou moins investi : il a
> le signe du marché. La décision se prend maintenant, par vous. Le suivi vérifie seulement que la règle fait ce qu'elle
> dit et ne coûte pas plus que prévu.

Chaque écart accepté s'applique dans `PLAN`, jamais dans `REF-S2`. Chaque clause de retrait peut échouer.

| Article | Écart | Ce qu'on compte | Clause de retrait, écrite d'avance | Durée | Proposition |
|---|---|---|---|---|---|
| E-L | Ordres à cours limité, exécution sur papier avec test de limite (plus stricte que l'exécution du test) | part des titres servis à 1, 3 et 10 séances ; prix payé contre cours moyen du jour et contre dernier cours | aucune : c'est une mesure | 12 mois | **oui** |
| E-B | Compléter un ordre servi en partie ; placer un apport d'argent frais hors de la bande | part investie après les ordres ; ordres en plus ; frais en plus | retiré si un complément coûte, en frais facturés par franc, plus de deux fois l'ordre d'origine | 12 mois | **oui** |
| E-A | Arrondi « plus forts restes » avec une marge de deux trimestres de frais | francs placés en plus ; marge du pire cas à chaque ordre | retiré si, une seule fois, la provision au prix limite dépasse les liquidités, ou si la grille réelle rend la marge négative | 12 mois | **au choix** |

Une entrée en plusieurs fois, si vous l'appliquez, s'ajoute comme article E-T de même nature.

### Article 5 — `N`, la référence avec les notes [§8.4]

Phrase : *Le panier de référence avec les notes de l'analyste : le seul essai sur papier qui cherche à faire mieux que le
panier sans les notes.*

| Élément | Contenu |
|---|---|
| Règle | REF-S2, plus les notes de l'analyste (veto, filtres de risque, inclinaisons), en règle stricte à la date de décision |
| Mesure | `d_t` = rendement hebdomadaire net de N − celui de REF-S2 |
| Statistique | t de Newey-West de la moyenne de `d_t` (4 retards) ; intervalle par bootstrap stationnaire (blocs de 8 semaines, 5 000 tirages, graine 0) |
| Durée | aucune lecture de rendement avant 52 semaines ; aucune affirmation avant 156 semaines |
| Notes retirées de l'ordre | à un point d'étape d'au moins 52 semaines, si t ≤ −2,0 ou si le retard cumulé de N sur REF-S2 atteint 3 points **[Hypothèse de travail : à valider]** |
| Notes confirmées | seulement à 156 semaines ou plus, si t ≥ 3,0 **et** p unilatérale ≤ 0,05 ÷ m **et** DSR ≥ 0,95 |
| Sinon | « indéterminé » : rien ne change ; l'écran écrit « les notes n'ont pas fait leurs preuves » |
| Prédiction écrite d'avance | « indéterminé » est le résultat le plus probable, même si les notes sont utiles |

### Articles 6 et 7 — `E-C` et `E-D` : essais, ou dérogation signée [§8.4]

La spécification de la stratégie (§8.5, dernier paragraphe) classe deux questions comme « décisions humaines attendues
(non tranchées ici, **nouvel essai à juger sur S2 seulement**) » : (i) le plancher D1 et l'âge des ordres après un trou de
bulletins ; (ii) le repli D8 (dividendes gardés en liquidités jusqu'à la remise à niveau annuelle).

| Article | Essai | Règle | Critère écrit d'avance |
|---|---|---|---|
| 6 | E-C, continuité des données | REF-S2 + option `--continuite` : pas de vente pour une inéligibilité calculée sur une fenêtre de 126 séances où des bulletins manquent | **retenue** dans PLAN si aucun titre réellement suspendu ou radié n'a été gardé à tort plus de 20 séances ; **retirée** sinon ; compte dans m dès son premier écart au témoin |
| 7 | E-D, réinvestissement mensuel | REF-S2 + option `--reinvestir` : à la dernière séance du mois, une seule ligne, aucune vente | **retirée** au 31/01/2028 si les frais par franc réinvesti dépassent 1,5 fois ceux de l'ordre d'entrée, ou s'il y a plus de 6 ordres par an ; **confirmée** seulement à 156 semaines ou plus, avec les conditions de N |

Réponses possibles pour chacun :

- **option 1 (proposée)** : essai déclaré, inscrit au registre (`S2-EC`, `S2-ED`), avec son portefeuille « REF-S2 plus
  l'écart seul » exécuté sur papier en mode « test » ;
- **option 2 : oui** ou **option 2 : non** : dérogation signée au §8.5 de la spécification (son texte est cité dans la
  ligne). L'écart devient une décision d'exécution, appliquée (oui) ou non dans PLAN ; il n'est pas inscrit au registre
  et ne compte ni dans N ni dans m ;
- **non déclaré** : aucune ligne. Sans signature de l'une ou l'autre option avant le 01/12/2026, E-C et E-D restent
  **éteints** dans PLAN.

Déclarer E-D, c'est choisir d'être plus exposé au marché de mai à janvier.

### Le plan `PLAN` [§8.6]

Phrase : *Le plan suivi sur papier : l'ordre par défaut, avec la mémoire de la remise à niveau de janvier et les écarts
que vous acceptez.*

C'est l'ordre par défaut (avec les notes, sauf si vous choisissez « sans les notes ») + la mémoire annuelle (`--suivi`)
+ les écarts déclarés « oui ». Ce n'est pas « ce que fait la commande par défaut », qui n'a pas de mémoire. PLAN n'est
jamais comparé au témoin sur le rendement, seulement sur des faits comptés.

---

## A5. Correction pour comparaisons multiples [§8.5]

1. m = nombre d'essais à prétention de rendement inscrits pour S2. Option 1 : m = 2 au départ (N et E-D), puis 3 dès que
   E-C s'écarte du témoin. Option 2 : m = 1 (N seul).
2. Seuil unilatéral de 0,05 ÷ m (Bonferroni), **en plus** de t ≥ 3,0.
3. Tout essai ajouté plus tard augmente m pour toutes les décisions à venir. Aucun seuil n'est relâché après coup.
4. Le DSR est calculé avec tous les essais du registre (98 aujourd'hui, plus les trois à cinq lignes S2).
5. Un portefeuille identique au témoin (E-C sans bulletin manquant) entre dans N pour le DSR, mais pas dans m tant qu'il
   reste identique.
6. Aucun classement par rendement n'est affiché avant un point d'étape.

---

## A6. Points d'étape [§8.8]

| Date | Ce qu'on lit | Ce qu'on peut décider |
|---|---|---|
| 01/12/2026 | début du suivi sur papier | — |
| chaque semaine | bulletin : trois feux | une revue, jamais une vente automatique |
| 29/01/2027 | remise à niveau de la référence | coût mesuré (P6) |
| 01/06/2027 | comptabilité seulement : P1 à P7, clauses de retrait | retrait d'un écart ; première date possible pour **examiner** une décision humaine sur l'argent réel |
| 01/12/2027 | première lecture de `d_t` (52 semaines) | retrait éventuel des notes |
| 31/01/2028 | E-D après une saison de dividendes et une remise à niveau | retrait de E-D, ou « en cours » (jamais « confirmé » avant 156 semaines) |
| 01/12/2029 | 156 semaines | première affirmation possible |

Entre deux points d'étape : aucune décision sur une règle, aucun changement sans nouvel article.

---

## A7. Vers l'argent réel : ce que le module affiche, et ce qu'il ne décide pas [§8.9]

Le texte actuel de la spécification exige, pour le statut PROMU, des filtres verts sur S1 **et** sur S2. Tout est rejeté
sur S1 : **avec ce texte, rien ne peut être promu, et la plate-forme ne recommandera pas d'argent réel.** Changer ce
texte serait votre décision, jamais avant 6 mois de suivi sur papier (01/06/2027).

Conditions **nécessaires, non suffisantes**, proposées pour qu'une telle décision puisse seulement être examinée
[Hypothèse de travail] : 26 semaines de journal sans rupture de chaîne ; grille du courtier au statut « grille écrite » ;
contrôles P1 à P5 et P8 conformes ; retard de la référence dans son budget ; montant que vous acceptez de risquer, réserve
et durée choisis ; un changement écrit de la règle de promotion, daté, avec sa raison ; une décision écrite et signée de
votre part.

---

## A8. Décisions humaines en attente [§13]

À trancher **avant le 01/12/2026** :

| N° | Décision | Proposition par défaut | Où elle s'écrit |
|---|---|---|---|
| 1 | Les notes dans l'ordre pendant le suivi : garder l'ordre « avec notes », ou revenir à la règle testée « sans notes » ? | **garder « avec les notes »** (défaut actuel) | article PLAN |
| 2 | Écarts d'exécution : oui ou non pour E-L, E-B, E-A | **E-L oui ; E-B oui ; E-A au choix** | articles E-L, E-B, E-A |
| 3 | E-C et E-D : essais (option 1) ou dérogation signée (option 2) ; déclarer E-D ou non | **option 1 pour les deux** (conforme au §8.5 de la spécification) | articles E-C, E-D |
| 3 bis | Seuils de l'article 5 : retrait des notes à t ≤ −2,0 ou à 3 points de retard cumulé | **valider** (ou corriger dans le fichier avant de signer) | article N |
| 3 ter | Trois exceptions aux tests existants (pages de l'interface, couverture des routes, tâche de nuit) | **accord** ; sinon les routes nouvelles et l'étape de nuit sont retirées et `suivi maj` se lance à la main | décision écrite, hors déclaration |
| 3 quater | Signature : initiales ou pseudonyme (jamais le nom complet : le fichier est suivi par git) | **initiales** dans `<données>/profil/signature.json` | profil, hors dépôt |
| 4 | Grille du courtier : envoyer les 8 questions ; garder le courtier actuel ou un courtier sans frais par ligne | **envoyer les 8 questions** (`plan questions`) | grille, hors déclaration |
| 5 | Statut de l'investisseur : personne physique résidente ? de quel pays ? | **personne physique résidente** (supposé par tout le module) | grille |
| 6 | Ce que j'accepte de risquer, taux de la réserve, durée | **« pas encore »** : la table de choix s'affiche | plan, hors déclaration |

À trancher plus tard : chemin vers l'argent réel pour une règle née après S1 ; seuils des feux (tous sans base
statistique) ; correction de la date de paiement projetée (accord écrit demandé) ; impôt sur les plus-values, taxe sur
le courtage et sur les frais annuels (à faire confirmer) ; taux et sûreté du placement d'attente (hors du champ de la
plate-forme) ; comparaison avec l'alternative simple (ne pas investir, ou un fonds actions de la place).

---

## A9. Signer la déclaration, avant le 01/12/2026

La signature se fait **dans le dépôt de développement** (là où `reports/` et `docs/` sont suivis par git), jamais sur le
serveur d'installation. Sur une installation, la commande refuse avec le code 2 : « La déclaration se signe dans le dépôt
de développement, puis se livre par un commit. »

### A9.1 La commande, telle qu'elle sera

La commande `suivi declarer` est ajoutée à la ligne de commande dans la phase suivante. Elle s'emploiera ainsi :

```
# 1. Écrire le projet de déclaration (articles 1 à 7 et PLAN, propositions par défaut) :
python -m brvm_alpha suivi declarer --modele > projet_declaration.json

# 2. Ouvrir projet_declaration.json et remplir le champ "reponse" de chaque article
#    (valeurs permises dans "choix" ; seuils « Hypothèse de travail » à valider ou corriger).

# 3. Choisir vos initiales (1 à 12 lettres, chiffres ou tirets), par exemple dans
#    <données>/profil/signature.json : {"signe_par": "AB"}

# 4. Signer et inscrire au registre des essais (dépôt de développement seulement) :
python -m brvm_alpha suivi declarer --fichier projet_declaration.json --signer AB \
    --registre --confirmer "J'INSCRIS AU REGISTRE"

# 5. Vérifier la chaîne :
python -m brvm_alpha suivi verifier

# 6. Commit AVANT le 01/12/2026 (sa date fait foi) :
git add brvm-alpha/reports/suivi_S2/declaration.jsonl brvm-alpha/reports/trials.parquet \
        brvm-alpha/configs/rendement_net.yaml brvm-alpha/docs/RENDEMENT_NET.md
git commit -m "[ADD] brvm-alpha: déclaration signée du suivi sur papier"
```

L'étape 4 écrit `reports/suivi_S2/declaration.jsonl` (une ligne par article) et ajoute trois à cinq lignes au registre
`reports/trials.parquet` : `S2-REF`, `S2-N`, `S2-PLAN`, et `S2-EC`, `S2-ED` si vous avez choisi l'option 1. Les 98
lignes existantes du registre ne changent pas (leur empreinte est vérifiée avant de remplacer le fichier).

### A9.2 Si la ligne de commande n'est pas encore prête

Les mêmes fonctions existent déjà dans le paquet. Depuis le dossier `brvm-alpha` du dépôt de développement :

```python
import json
from pathlib import Path
from brvm_alpha import paths
from brvm_alpha.suivi import declaration as D

# 1. Projet : à remplir à la main (champ "reponse"), puis relu.
Path("projet_declaration.json").write_text(json.dumps(D.modele(), ensure_ascii=False, indent=1), encoding="utf-8")
articles = json.loads(Path("projet_declaration.json").read_text(encoding="utf-8"))

# 2. Signature et inscription (chemins explicites, aucun défaut) :
dossier = paths.REPO_ROOT / "reports" / "suivi_S2"
D.signer(articles, "AB", dossier)
registre = paths.REPO_ROOT / "reports" / "trials.parquet"
D.inscrire_au_registre(dossier, registre, confirmer=D.CONFIRMATION_REGISTRE)
print(D.verifier(dossier, registre=registre))   # chaîne et sceaux du registre (troncature comprise)
```

### A9.3 Les règles de la déclaration

- Une ligne ne se modifie jamais. Chaque ligne porte l'empreinte SHA-256 de la ligne précédente (`precedente`) et de son
  propre contenu (`empreinte`) : toute réécriture rompt la chaîne, `suivi verifier` le signale et le feu « Données »
  passe au rouge. Une chaîne rompue bloque tout ajout avant une décision humaine écrite.
- Une règle se remplace par une nouvelle ligne de type `remplace`, qui ne vaut que pour l'avenir.
- Une ligne signée après le 01/12/2026 est acceptée, mais ne vaut qu'à partir de la séance suivante ; la page Validation
  écrit « déclarée après le début du suivi ».
- Chaque ligne porte : l'empreinte des paramètres de la stratégie (`configs/strategy_v1.yaml`), celle des réglages du
  module (`configs/rendement_net.yaml`), celle de ce document, et le commit du code.
- Aucune donnée personnelle : la signature est faite d'initiales ou d'un pseudonyme, ou de l'empreinte d'un texte que
  vous seul connaissez (`{"signe_par_empreinte": "<SHA-256>"}`). Jamais un nom complet ni une adresse.
- Sans déclaration au 01/12/2026, seul le témoin `REF-S2` est suivi, et l'écran l'écrit.

---

## A10. Où vivent les fichiers

| Fichier | Où | Suivi par git |
|---|---|---|
| Déclaration signée | `reports/suivi_S2/declaration.jsonl` (dépôt de développement) | oui |
| Registre des essais | `reports/trials.parquet` (ajout de lignes seulement, sur votre commande) | oui |
| Signature choisie | `<données>/profil/signature.json` | **non** |
| Journal d'un portefeuille | `<données>/suivi/<nom>/` : `semaines.csv`, `empreintes.jsonl`, `operations.csv`, `positions.csv`, `anomalies.jsonl`, `controles.json` ; `carnet.jsonl` pour PLAN, MOI, E-C, E-D | **non** |

`<données>` est le dossier de données de l'installation (variable `BRVM_ALPHA_DONNEES`). Le suivi n'écrit jamais sous
`reports/` de lui-même : seule la déclaration, signée par vous, y entre.

---

## A11. Le journal de la semaine et le bulletin [§F10, §F12]

Chaque semaine (vendredi v ; t = dernière séance disponible au plus tard ce vendredi) :

- **valeur** = titres au cours + liquidités ; **argent engagé** = apports − retraits ; **écart** = valeur − argent
  engagé ;
- **pont, une seule base** : le cours de référence avant l'ordre. L'écart se décompose exactement, au franc près, en :
  effet des cours + dividendes reçus − frais d'achat et de vente (frais facturés et coût dans le prix) − frais annuels
  prélevés + intérêts ;
- **frais partis pour de bon** (frais de transaction et frais annuels) et **baisses de cours non vendues** (elles peuvent
  se retourner ou s'aggraver) ;
- **valeur de part** (rendement pondéré par le temps) : l'écart au marché ne dépend pas des dates de vos apports ;
- **dividendes à recevoir** (détachés, pas encore payés) : montrés à part, hors du pont ;
- une division d'actions ne crée aucune fausse perte ; un titre absent du bulletin est valorisé au dernier cours − 10 %.

Deux lancements la même semaine donnent une seule ligne. Une semaine déjà écrite n'est jamais réécrite : si son recalcul
diffère, une entrée « le passé a changé » est ajoutée et le feu « Données » passe au rouge.

Le bulletin porte trois feux : **Perte**, **Fuites**, **Données**. Vert : rien à faire. Orange : une revue. Rouge : une
décision écrite. **Un feu ouvre une revue, jamais une vente. Aucune de ces décisions n'a été testée.** Les seuils ont été
choisis après lecture de la période 2022-2026, sans base statistique ; leur utilité est inconnue.

---

## A12. Ce que le module ne fait pas

- Il ne promet aucun gain et ne présente aucune perte comme impossible.
- Il ne passe aucun ordre réel, ne vend jamais seul et ne transmet rien à un courtier.
- Il n'active aucune variante rejetée et ne change pas l'ordre de bataille par défaut.
- Il ne simule aucune règle sur l'échantillon S1 (jusqu'au 16/11/2022) ; il lit seulement les résultats publiés.
- Il ne lance ni `validate` ni `backtest`, et ne modifie ni `validation/runner.py` ni
  `configs/strategy_v1.yaml`. Le moteur du test ne reçoit qu'un seul ajout : le refus explicite d'un forfait
  de compte non nul (§4.3 et §8.2 du cahier).
- Il ne signe rien à votre place : la déclaration et l'inscription au registre ne se font que sur votre commande
  explicite, dans le dépôt de développement.
- Il ne classe aucun essai par son rendement avant un point d'étape.
- Il n'envoie aucune requête réseau ; vos données (grille, portefeuille, avis d'opéré, signature) restent dans le dossier
  de données local.
- Il ne connaît aucun taux de placement et ne conseille aucun placement.

---

# Partie B — Le cahier des charges, copie intégrale

# Cahier des charges — module « Rendement net et pertes »

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
> Ce module ne promet aucun gain et ne rend aucune perte impossible. Il ne le dira jamais.
> Statut de la plate-forme au 22/11/2026 : toutes les variantes (A à I) et la référence REF sont **REJETÉES** sur leur test (S1). La plate-forme fonctionne en « indice discipliné », **à titre d'étude**. Le suivi sans argent réel (S2) commence le 01/12/2026. Rien dans ce document n'autorise un achat avec de l'argent réel.

Document unique, **version finale** du 22/11/2026 (dernier bulletin du panel : 20/11/2026). Il part de la proposition « particulier » (la mieux notée par le jury : 19,5 sur 30), y greffe le bilan et la grille de « fuites », le suivi des pertes et le mode apport de « pertes », applique les corrections des trois juges (§2.1), puis celles de la contre-expertise « chiffres » et « protocole » (§2.2). Les chiffres contestés ont été recalculés dans `F/`. Ce qui n'est pas retenu de la contre-expertise est expliqué au §16.

**Convention.** Chaque chiffre porte un statut :
- **Fait** : recalculable ; le script ou la commande est cité ;
- **Estimation** : calculé avec une méthode citée, incertain ;
- **Hypothèse** : supposé, non vérifié.

Un montant calculé exactement à partir d'un tarif supposé est une **Hypothèse (tarif)**. Une somme prend le statut le plus faible de ses termes.

**Dossiers cités.**
- `M/` = `<mesures>/` (mesures `M/frais/`, `M/liquidites/`, `M/pertes/`, `M/rendement/` ; propositions `M/designs/` ; contrôles du jury `M/jury/`) ;
- `S/` = `M/spec_travail/` (contrôles de la version précédente, avec l'ancien choc 0,278 ; ils restent valables pour le bilan, les leviers de frais et le taux de réserve : `s1_bilan.py`, `s2_poches.py`, `s3_blocs.py`, sorties `s1_sortie.txt` à `s4_sortie.txt`, deux ordres exacts dans `S/reco/`) ;
- `F/` = `M/final/` (contrôles de la version finale : `f1_sref.py` à `f7_divers.py`, sorties `f1_sortie.txt` à `f7_sortie.txt`, six ordres exacts dans `F/reco/`) ;
- `Rv/` = `M/revue/chiffres/` et `Ra/` = `M/relecture_adverse/` (scripts de la contre-expertise) ;
- `D/` = `<dépôt>/` (dépôt, lu sans aucune écriture ; état lu pour la version finale : commit `d256e26` ; les ordres de `F/reco/` ont été produits sur ce commit).

---

## 0. L'essentiel

### 0.1 La demande et la réponse honnête

« Maximiser les profits. Aucune perte ne doit devenir une fuite. »

On ne peut ni garantir un gain ni empêcher une perte. On peut faire trois choses, et seulement celles-là :

1. **Fermer les fuites évitables** : frais, impôts, argent qui dort, arrondis, exécution. Elles se comptent en francs.
2. **Donner à l'utilisateur la maîtrise de ce qu'il risque** : montant en actions, réserve, durée, alertes de revue.
3. **N'ajouter une source de rendement que si elle découle de l'arithmétique**, ou si elle est déclarée à l'avance pour être jugée sur le suivi S2.

### 0.2 Ce que l'utilisateur voit : un écran, trois décisions, trois feux

| | Décision | Ce qu'il saisit | Ce que la plate-forme rend |
|---|---|---|---|
| 1 | **Ce que prend mon courtier** | les chiffres de sa grille écrite | la facture en FCFA, l'écart avec le tarif supposé, ce qui reste supposé |
| 2 | **Ce que j'accepte de risquer sur 12 mois** | un montant en FCFA, choisi dans une table de quatre lignes | le montant en actions, la réserve, la perte estimée de plusieurs façons, le prix de cette prudence |
| 3 | **Où dort le reste, et à quel taux** | le taux net de son compte ou de son placement d'attente | ce que rapporterait la réserve, et ce que chaque point de taux vaut ; ces intérêts ne sont **jamais** déduits de la perte estimée |

Puis, chaque semaine, trois feux : **Perte**, **Fuites**, **Données**. Vert : rien à faire. Orange : une revue. Rouge : une décision écrite. Aucun feu ne vend.

La déclaration des règles du suivi S2 n'est pas une décision d'investisseur. C'est une formalité à part (§8), à faire avant le 01/12/2026.

### 0.3 Les chiffres qui fondent le module (10 000 000 FCFA, cours du 20/11/2026, tarif supposé « central »)

| Constat | Valeur | Statut | Preuve |
|---|---:|---|---|
| Frais et impôt de la 1re année si l'on achetait tout | 340 241 FCFA (3,40 % du capital ; 69 % des dividendes bruts attendus) | Hypothèse (tarif) ; recalcul à 0 FCFA d'écart | `S/s1_bilan.py` ; `M/frais/01_decomposition.py` |
| Part de cette facture qui est supposée ou estimée (règle : une somme prend le statut le plus faible de ses termes) | 311 289 FCFA, soit 91,5 % ; sur les seuls frais (284 714 FCFA) : 255 762 FCFA, soit 89,8 % | Fait de calcul | `F/f7_divers.py` (seules les commissions BRVM et DC/BR sont des faits ; l'impôt est un taux vérifié appliqué à des dividendes estimés) |
| Part que la grille écrite du courtier remplacerait par des faits | 215 226 FCFA (courtage, taxe, garde, tenue de compte) | Fait de calcul | `F/f7_divers.py` |
| Tenue de compte par ligne | 100 000 FCFA par an ; 0 si le courtier ne facture pas par ligne | Hypothèse (tarif) | `M/frais/rapport.md` §4 |
| Écart avec la seule grille connue sans frais par ligne (FGI aux plafonds) | 73 224 FCFA de moins la 1re année, puis 96 000 FCFA de moins par an | Hypothèse (tarif) | `M/frais/03_grille.py` (barème U1) ; `S/s2_poches.py` |
| Argent laissé par l'arrondi vers le bas | 149 440 FCFA ; 65 485 FCFA plaçables avec une marge de sécurité | Fait | `M/liquidites/scripts/a_arrondis.py` |
| L'outil ne propose aucun rachat avec 6,1 % puis 10,2 % de liquidités | 0 ordre | Fait | `M/liquidites/reco/reco_detenu_*.json` |
| Après un ordre servi en partie, l'outil ne complète pas les lignes | 469 430 FCFA jamais rachetés dans l'essai | Fait (outil) ; Hypothèse (scénario) | `M/jury/marche/j3_sortie.txt` |
| Choc de 2018 subi par REF dans son test publié, par franc investi, hors frais | 0,2932 (méthodes approchées : 0,290 à 0,304) | Estimation (lecture d'un résultat publié, pas un test) | `F/f1_sref.py` |
| Perte d'une année comme 2018, tout en actions, frais compris | 2 598 431 à 3 114 258 FCFA | Estimation | `F/f2_poches.py` |
| Avec 1 000 000 FCFA de perte acceptée | 3 000 000 FCFA en actions, 7 000 000 FCFA en réserve | Estimation (règle du §F4) | `F/f2_poches.py` ; `F/reco/reco_3000000.json` |
| Périodes de 12 mois finies en perte dans le passé connu | environ 26 % à 40 % selon la façon de compter et le tirage ; 37 périodes réelles sur 107 | Estimation descriptive, un seul passé | `F/f4_graines.py` ; `F/f3_periodes.py` |
| Retard de REF sur le marché dans son test (S1) | −5,6 points par an (REF sans les notes) | Fait publié | `D/reports/validation_S1/resultats.md` |

### 0.4 Ce que le module ne fait pas

Il n'active aucune variante rejetée. Il ne vend jamais seul. Il ne change pas l'ordre de bataille par défaut : mêmes titres, mêmes quantités, mêmes prix limites, mêmes frais qu'aujourd'hui. Il **ajoute** des blocs d'information et des options, toutes éteintes par défaut.

---

## 1. Règles de conduite du module

1. **Aucune promesse.** La phrase « Performance passée ≠ garantie. Aucun gain n'est garanti. » (constante `BANNER` existante) figure sur chaque sortie nouvelle : écran, ordre, rapport, bulletin, JSON, aide des commandes.
2. **Étude seulement, et aucun achat à la prochaine séance.** Tant que le statut est REJETÉ, chaque sortie du module porte `PH_ETUDE` et `PH_SEANCE` (§1.2). `PH_SEANCE` ne promet aucune date de feu vert : avec les règles actuelles, la plate-forme ne recommandera pas d'argent réel (le statut PROMU exige des filtres verts sur S1 **et** sur S2, spécification §8.3 ; tout est REJETÉ sur S1). Elle dit seulement qu'un changement de ces règles serait une décision de l'utilisateur, jamais avant 6 mois de suivi sur papier (spécification §8.1 : au moins 6 mois de suivi S2 avant toute recommandation d'argent réel, 36 mois avant toute affirmation de performance [Fait de la spécification]). Les dates et le temps du verbe sont calculés à l'affichage, jamais écrits en dur.
3. **La perte acceptée n'est pas une limite.** C'est une taille de poche calculée pour une année comme 2018. Les mots « plafond », « perte maximale », « au plus » ne servent jamais à la décrire. Le dépassement possible est écrit sur la même ligne, en FCFA.
4. **Une économie de frais n'est pas un gain.** On écrit « frais évités par rapport au tarif supposé ; 0 si votre courtier ne facture pas ce poste ». Jamais « certain », « sûr », « gagné », « rapporte ».
5. **Des francs placés ne sont pas des francs gagnés.** Les montants « placés en plus » ou « remis au travail » ne sont jamais dans la même colonne que des frais évités. Ils portent toujours « gain ou perte selon le marché ».
6. **Aucune vente automatique.** Un feu ouvre une revue. La spécification interdit le stop sur le prix (§9.1).
7. **Aucune règle nouvelle présentée comme validée.** Tout ce qui change la sélection, les poids, les sorties, le calendrier ou l'exécution de la règle testée est une option éteinte par défaut, déclarée avant le 01/12/2026 (§8).
8. **S1 reste fermé.** Aucune fonction du module ne simule une règle sur une date ≤ 16/11/2022. Le module lit les résultats S1 publiés. Ses statistiques sur l'historique complet rejouent le panier d'aujourd'hui et les indices : elles portent la phrase fixe `PH_DESCRIPTIF` (« Descriptif, pas un test. »), et un test l'impose partout où une fréquence, une médiane ou « une année sur dix » est affichée.
9. **Chaque montant porte son statut**, écrit en un mot sur l'écran : « compté » (Fait), « estimé » (Estimation), « supposé » (Hypothèse).
10. **Des francs d'abord, arrondis sur l'écran, au franc dans le détail.** Tout montant est en FCFA ; le pourcentage suit, entre parenthèses.
    - *Écran* (texte de `plan`, carte « Mon plan » du Tableau de bord, carte du rapport) : un montant « compté » s'affiche au franc ; un montant « estimé » ou « supposé » passe par `reglages.arrondi_ecran(x)` et s'écrit « environ … ». `x` est compté du point de vue de l'utilisateur : gain positif, coût ou perte négatif. Pas de 10 000 FCFA si |x| ≥ 100 000, de 1 000 FCFA sinon ; arrondi **vers le bas** (vers −∞) : `pas × floor(x ÷ pas)`. Une perte grossit donc toujours (−501 430 → « −510 000 »), un gain se réduit (+118 001 → « +110 000 »), un coût écrit sans signe grossit (284 714 FCFA de frais → « 290 000 FCFA de frais »). Le signe est écrit, sauf après « de frais » ou « de perte ». Un gain non nul qui s'arrondirait à 0 s'écrit « entre 0 et +1 000 » ; un montant négatif ne peut pas s'afficher 0. Les comparaisons (« dépasse ce que vous acceptez ») se font sur les montants exacts, jamais sur les montants arrondis. La somme de lignes arrondies peut différer de la ligne de total : l'écran l'écrit une fois (« montants arrondis »).
    - *Détail* (Markdown de l'ordre, `plan --format md`, JSON, rapport hors carte) : montants au franc, arrondis par `recommend.round_fcfa` (demi vers le haut : 93 094,5 → 93 095).
11. **Aucun réseau.** Le module n'envoie aucune requête. Les données de l'utilisateur (grille, portefeuille, avis d'opéré, signature) restent sous le dossier de données local ; rien de personnel n'entre dans un fichier suivi par git (§F9).

### 1.1 Lexique imposé (écran « Mon plan » et bulletin)

Un test refuse les mots de gauche dans le texte de l'écran et du bulletin. Le reste de l'ordre de bataille garde son vocabulaire actuel.

| Interdit sur l'écran | Employé |
|---|---|
| SGI (seul) | votre courtier (SGI) |
| IRVM | impôt sur les dividendes |
| P10, quantile | une année sur dix |
| médiane | une année ordinaire du passé |
| bootstrap, distribution | le passé rejoué |
| stress, ST2 | une année comme 2018 |
| drawdown | baisse depuis le plus haut |
| challenger | essai sur papier |
| S2, paper trading | suivi sur papier |
| REF | le panier de référence (les 20 plus grosses sociétés) |
| reliquat | argent qui dort |
| rebalancement | remise à niveau de fin janvier |
| poche, mandat | montant en actions ; ce que j'accepte de risquer |
| garanti, sûr, certain, sans risque, protégé, plafond, perte maximale | (jamais, sauf dans une phrase négative) |
| gagné, rapporte (pour des frais) | frais évités par rapport au tarif supposé |
| tracking error, alpha, DSR, PBO, bêta | (jamais sur l'écran) |

Forme de l'écran : 45 lignes au plus en 100 colonnes ; trois saisies ; phrases de 25 mots au plus ; un statut par ligne de montant.

**Comment le test du lexique compte** (`reglages.mots_interdits(texte) -> list[str]`) :
1. Texte normalisé : minuscules, accents retirés (`unicodedata`, forme NFKD), apostrophes typographiques remplacées par « ' ».
2. Recherche par **mots entiers ou expressions entières** (limites de mots `\b`, sur le texte normalisé) : « sûr » ne trouve pas « Sûreté », « certain » ne trouve pas « Certaines », « au plus » ne trouve pas « au plus tôt » (l'expression interdite est « au plus » suivie d'un montant ou d'un pourcentage : motif `\bau plus\b(?!\s+tot)`).
3. **Liste blanche**, retirée du texte avant la recherche : les noms propres (« BRVM Alpha », noms de sociétés), les phrases fixes du §1.2 et les libellés de l'ordre existant (hors bloc « L'essentiel »).
4. **Phrase négative** : un mot de la ligne « garanti, sûr, certain, sans risque, protégé, plafond, perte maximale » est permis seulement dans une phrase (texte entre deux points) qui contient « aucun », « aucune », « jamais », « n'est pas », « ne sont pas », « n'… pas » ou « ni ».
5. Le test F4-7 (« au plus », « plafond », « perte maximale », « sous la perte acceptée ») porte sur le bloc « Ce que j'accepte de risquer », phrases fixes retirées.

### 1.2 Phrases fixes (constantes du module, reprises telles quelles)

| Code | Texte |
|---|---|
| `BANNER` | Performance passée ≠ garantie. Aucun gain n'est garanti. |
| `PH_ETUDE` | Étude seulement : aucune méthode de la plate-forme n'a réussi son test. Sur 2017-2022, la règle de référence, sans les notes, a fait 5,6 points de moins par an que le marché ; les notes n'ont jamais été testées. |
| `PH_SEANCE` | Gabarit, rendu par `reglages.phrase_seance(aujourd_hui)`. Avant le 01/12/2026 : « Prochaine séance : aucun achat. Aucune méthode n'est validée : avec les règles actuelles, la plate-forme ne recommandera pas d'argent réel. Changer ces règles serait votre décision, jamais avant le 01/06/2027 (6 mois de suivi sur papier à partir du 01/12/2026). » Du 01/12/2026 au 31/05/2027 : « … jamais avant le 01/06/2027 (6 mois de suivi sur papier depuis le 01/12/2026). » À partir du 01/06/2027 : « … Changer ces règles serait votre décision, écrite et signée (suivi sur papier depuis le 01/12/2026). » Les deux dates viennent de `dates.debut_suivi` et `dates.premiere_decision_argent_reel`. |
| `PH_DESCRIPTIF` | Descriptif, pas un test. |
| `PH_INTERETS` | Les intérêts de la réserve ne sont jamais déduits de la perte estimée. |
| `PH_NE_PAS_TRANSMETTRE` | Étude : ne transmettez pas ces ordres à votre courtier. |
| `PH_FRAIS` | Ces frais n'existent que si vous achetez. Montants calculés sur un tarif supposé tant que la grille de votre courtier n'est pas saisie. |
| `PH_ECONOMIE` | Frais évités par rapport au tarif supposé ; 0 si votre courtier ne facture pas ce poste. |
| `PH_RISQUE` | Ce que vous acceptez de risquer n'est pas une limite. Une baisse plus forte a existé : le marché a perdu 46,7 % de mars 2017 à octobre 2020. |
| `PH_PASSE` | Fréquences d'un seul passé (2017-2026 : quatre années de baisse, puis six de hausse). Ce ne sont pas des probabilités. |
| `PH_FLATTE` | La lecture « passé rejoué » rejoue les gagnants d'aujourd'hui : elle flatte. Le seul test réel de la règle de référence a donné 5,6 points de moins par an que le marché. (Placée partout où la lecture flatteuse apparaît : détail seulement, jamais sur l'écran.) |
| `PH_PLACE` | Placer plus, c'est gagner plus si le marché monte et perdre plus s'il baisse. |
| `PH_COURS` | Les cours peuvent monter ou baisser bien plus que ces montants. |
| `PH_REVUE` | Un feu ouvre une revue, jamais une vente. Aucune de ces décisions n'a été testée. |
| `PH_ESSAI` | Un essai sur papier n'est pas validé. Douze mois de suivi ne prouveront aucune règle par ses gains. |
| `PH_RESERVE` | Taux saisi par vous. Sûreté, frais, impôt et disponibilité du placement non vérifiés. |
| `PH_ETALER` | Étaler l'entrée, c'est être moins investi pendant quelques mois. Le gain ou le coût dépend du sens du marché pendant ce délai : personne ne le connaît. |

---

## 2. Base retenue, greffes, corrections

### 2.1 Base, greffes et corrections du jury

**Base : « particulier ».** Un écran, un lexique, un bulletin à trois feux, un recalcul immédiat de la facture, une règle « frais compris » pour le montant en actions.

**Greffes.**
- De « fuites » : le tableau du brut au net avec, pour chaque ligne, son statut et ce qu'on peut y faire ; la grille à statuts par champ ; le comparateur ; les alertes de fuite ; la provision d'entrée ; l'arrondi avec marge ; le journal d'exécution ; le coût d'un aller-retour sur chaque vente.
- De « pertes » : la table de choix quand l'utilisateur ne dit rien ; le prix de la prudence en FCFA dans deux lectures ; les lectures du risque côte à côte ; le carnet, la règle d'exécution sur papier avec test de limite, le pont « fuites / pertes latentes » ; la vie d'une alerte ; le mode apport recalculé à chaque tranche ; le choc sur un titre ; la question de la durée.

**Corrections du jury appliquées.**

| N° | Reproche | Correction dans ce document |
|---|---|---|
| J1 | La règle « part ≤ X ÷ 23 % » oublie les frais (dépassement de 14 à 63 %) | Supprimée. Une seule règle, frais compris (§F4) |
| J2 | Le choc « 2018 » retenu (−23,98 % par franc investi) est plus doux que ce que la règle a subi dans son test | Le dimensionnement prend le plus sévère des deux. Le choc subi par REF est **mesuré** sur les positions publiées : 0,2932 (§F4, corrigé par la contre-expertise K1). 1 000 000 FCFA acceptés donnent 3 000 000 FCFA en actions (3 400 000 avec la grille connue sans frais par ligne) |
| J3 | Vocabulaire de plafond (`--perte-max`, « au plus », « sous la perte acceptée : oui ») | Option `--perte-toleree` ; libellé « ce que j'accepte de risquer sur 12 mois » ; dépassements écrits sur la même ligne ; test de vocabulaire |
| J4 | Chiffre vedette « 130 158 » ou « 144 633 » tiré d'un tarif qu'aucune grille lue n'offre | Fourchette affichée à partir de la grille connue (73 224 la 1re année, puis 96 000 par an) ; le tarif composé n'est cité que comme borne non attestée ; aucune addition à la main |
| J5 | « Certain », « gagné à coup sûr », « perdu à coup sûr » sur un tarif supposé | Règles 4 et 5 du §1 ; phrase `PH_ECONOMIE` |
| J6 | « 75 % non vérifié » compte l'impôt du Burkina et du Bénin comme vérifié | Règle du statut le plus faible appliquée aussi à l'impôt : 91,5 % (311 289 FCFA) supposé ou estimé ; 89,8 % des seuls frais ; liste des pays vérifiés en paramètre (corrigé par K4) |
| J7 | Le « un cas sur dix » dépend du choix de blocs de 8 semaines | Sensibilité aux blocs de 26 et 52 semaines en P0, fourchette affichée (§F6) ; médiane sur 20 graines (K5) |
| J8 | « Une chance sur quatre à une sur trois » : fausse précision | Phrase `PH_PASSE` ; « environ 26 % à 40 % selon la façon de compter et le tirage » ; rappel que les pertes se sont suivies |
| J9 | La ligne « P(battre le TR) 62,4 % » contredit le test | Libellé réécrit (§F6) ; la clé JSON reste |
| J10 | Unités mélangées : francs placés dans la colonne des gains | Deux tableaux séparés (§F3) ; trois lectures pour l'effet du marché |
| J11 | Étalement jugé « moins bien dans 64 à 76 % des cas » : résultat mécanique, signe inconnu | Pourcentages retirés ; phrase `PH_ETALER` (§F15) |
| J12 | Critères « comptables » qui ne peuvent pas rejeter (acquis par construction) | Les changements d'exécution sont des **décisions humaines datées**, avec une clause de retrait qui peut échouer (§8.3). Aucun critère « part investie plus proche de 98 % », aucune marge de 2 points |
| J13 | La référence S2 doit être la règle testée (annuelle, à mémoire, sans notes) | Définition figée de REF-S2 (§8.2) ; l'ordre « avec notes » devient le seul essai à prétention de rendement |
| J14 | Trop d'essais (six en réunissant les trois propositions) ; « 87,5 % / 96,9 % » donnés comme des faits | Un seul essai à prétention de rendement ; C4, E3, P15, C5 non ouverts ; bornes écrites « au plus » et retirées de l'écran |
| J15 | Les essais doivent être inscrits au registre de la spécification | Commande explicite `suivi declarer`, lancée par l'humain (§8.7) |
| J16 | Seuils d'alerte dits « fixés a priori » alors qu'ils ont été triés sur S0 | Étiquette « choisis après lecture de S0, sans base statistique ; utilité inconnue » |
| J17 | Feu « Fuites » vert par construction sur papier, orange par construction huit mois par an | Feu comparé à ce que la règle déclarée prévoit ; état « revue faite » (§F11) |
| J18 | Règle d'exécution sur papier dite « reprise du §7.1 » alors qu'elle ajoute un test de limite | Déclarée comme écart au test ; le témoin REF-S2 garde l'exécution du §7.1 (§8) |
| J19 | Après un service partiel, l'outil ne complète pas ; l'alerte « aucun ordre proposé » reste muette | Mode « compléter » (§F13) ; alerte calculée sur les liquidités **après** les ordres proposés, cause « ordres non servis » (§F7) |
| J20 | « Années suivantes » présenté comme attendu alors que c'est un plancher | Mention « sans transaction » et ligne estimée pour la remise à niveau de janvier (§F3) |
| J21 | Revenu net donné comme un point | Lignes « si les dividendes baissent de 7,5 % » et « de 20 % » (§F3) |
| J22 | La réserve (6,5 M à 0 %) est la plus grosse somme qui dort ; rangée en P2 | Troisième décision de l'écran, P0 (§F5) |
| J23 | Message double : « que faire lundi » à côté de « étude seulement » | Phrase `PH_SEANCE` en tête ; la ligne « si vous ne faites qu'une chose cette semaine » ne propose jamais un achat |
| J24 | Découpe en tranches figée au premier jour | Chaque tranche est recalculée en mode apport (§F15) |
| J25 | Le journal refuse toute date avant le 01/12/2026 | Le portefeuille de l'utilisateur ne refuse que les dates de S1 |
| J26 | Date de paiement projetée à ex + 2 jours ouvrés (observé en 2026 : 1 jour, 35 cas sur 35) | Correction proposée en P2 (§F16) ; l'alerte « dividende non reçu » part de l'avis de paiement publié |
| J27 | Portefeuille papier à 10 M alors que la poche conseillée est de 3,0 M | Portefeuille papier « MOI » à la taille et au tarif de l'utilisateur (§8.6) |
| J28 | Aucun critère pour REF lui-même ; aucun chemin vers l'argent réel | §8.1 et §8.8 : ce que S2 peut montrer, budget de retard, conditions nécessaires proposées ; la décision reste humaine |
| J29 | Fiscalité et statut de l'investisseur absents | Champs de la grille : personne physique ou morale, pays de résidence, impôt sur les plus-values (non vérifié), taxe sur les frais annuels |
| J30 | Consignes d'exécution absentes | Bloc « Passer l'ordre » (§F7) |

### 2.2 Corrections de la contre-expertise (version finale)

Chaque chiffre contesté a été recalculé dans `F/` avant d'être repris. Ce qui n'est pas retenu est au §16.

| N° | Gravité | Problème relevé | Correction (où) | Recalcul |
|---|---|---|---|---|
| K1 | majeur | Le choc « 2018 subi par REF » (0,278) reposait sur des frais supposés de 3,0 % à 3,9 % (moyenne de tout S1) ; les frais de 2018 publiés ne font que 0,65 % | Choc mesuré directement : rendement TR 2018 de la partie investie, poids de la veille = **0,2932**, calculé par le module à partir des fichiers publiés (§F4) ; tables de F1, F4, F5, F14, §0.3, §11, §14 refaites : 500 000 → 1 400 000 ; 1 000 000 → 3 000 000 ; 2 000 000 → 6 300 000 (FGI : 1 700 000 ; 3 400 000 ; 6 600 000) | `F/f1_sref.py`, `F/f2_poches.py`, `F/f2b_ordres.py` |
| K2 | majeur | Entrée en 3 tranches : frais déjà payés recrédités par `--capital` sans `--cash` ; invariant « mêmes quantités » faux | V = titres au cours + liquidités réelles, jamais capital − titres (§5, F13b, F15) ; sans option : 7 368 680 FCFA investis, 2 514 330 FCFA de liquidités ; avec `--apport` : 9 556 525 FCFA investis ; recette ⌊w × (K − frais déjà payés) ÷ p⌋ ; alerte W9 (§F8) | `F/f5_tranches.py` |
| K3 | majeur | « 36 sur 107 » ne suit pas la règle de `return_distribution` | 37 sur 107 (34,6 %), une année sur dix −19,5 %, « 2022 : 2 » ; règle écrite, tolérance ±1 période (§F6, F14) | `F/f3_periodes.py` |
| K4 | majeur | « 77 % supposé » contredit la règle du statut le plus faible ; la grille ne remplace pas 262 843 FCFA | 91,5 % de la facture, 89,8 % des seuls frais ; la grille remplace jusqu'à 215 226 FCFA (§0.3, F1, F2, F3, F8, F12) | `F/f7_divers.py` |
| K5 | mineur | Borne haute « 38 % » dépendante de la graine | Lectures bootstrap : médiane sur 20 graines affichée, graine 0 pour la recette ; « environ 26 % à 40 % » (§F6) | `F/f4_graines.py` |
| K6 | mineur | « Au moins une fois et demie » faux pour 500 000 | Phrase supprimée ; montants en FCFA sur chaque ligne ; rapport ligne par ligne (1,39 à 1,47 fois) (§F1, F4) | `F/f2_poches.py` |
| K7 | mineur | Seuil de réinvestissement inopérant face au minimum par ordre | Seuil appliqué au montant permis par la borne de poids (§F13d) | `F/f5_tranches.py` (4) |
| K8 | mineur | Valeurs décalées de 1 à 5 FCFA | 93 095 ; 76 625 ; 166 505 ; −11 697 ; −14 720 ; arrondi par `round_fcfa` (§F7, F13) | `F/f7_divers.py` |
| K9 | mineur | « Périodes indépendantes » non défini | Règle sans calcul : aucune fréquence tirée du passé à 24 et 36 mois (§F14, §12) | — |
| K10 | majeur | Trois familles de tests existants échouent par construction | Exceptions déclarées, commit séparé, empreintes avant et après (§9.1) | lecture de `D/tests/` |
| K11 | majeur | Le pont de F10 compte deux fois le coût dans le prix | Une seule base : effet de cours mesuré contre le cours de référence avant l'ordre ; exemple chiffré (§F10) | exemple vérifié à la main |
| K12 | majeur | Le témoin ne peut pas passer par `execute_run` tel qu'écrit (`SAMPLES` sans « S2 ») | Fabrique `suivi.temoin.temoin_model` passée par `ctx["factory"]`, `ctx` écrit en entier, test de non-régression (§F10) | lecture de `D/brvm_alpha/validation/runner.py` |
| K13 | majeur | `--suivi` contenait l'écart E-C sans le dire ; aucune interface pour la mémoire | `--suivi` = règle testée seule (D1 et D8 tels que codés) ; paramètre public `memoire_ref`, nul par défaut (§4.3, F13a) | lecture de `D/brvm_alpha/strategy/alpha.py` |
| K14 | majeur | E-C et E-D déclarés « non-essais » contre la spécification §8.5 | Inscrits comme essais, jugés sur S2 par un critère écrit d'avance, comptés dans N (DSR) et dans m ; dérogation signée possible au lot 0 (§8.3 à §8.7, §13) | lecture de `D/docs/SPECIFICATION_STRATEGIE.md` §8.5 |
| K15 | majeur | `PH_LUNDI` laissait croire à un feu vert au 01/06/2027 | `PH_SEANCE` : la plate-forme ne recommandera pas d'argent réel avec les règles actuelles ; dates calculées à l'affichage (§1.2, §8.9) | — |
| K16 | majeur | « Année ordinaire » de la lecture flatteuse sur l'écran, sans `PH_PASSE` | Écran : lecture prudente seule ; `PH_PASSE` et `PH_DESCRIPTIF` sous la décision 2 dans les quatre formes ; prix de la prudence sur la lecture prudente (§F1, F4) | `F/f2_poches.py` |
| K17 | majeur | Maquette contraire à la règle 3 | Pire moment de 2018 et baisse de 2017-2020 en FCFA sur chaque ligne, avec « dépasse » (§F1) | `F/f2_poches.py` |
| K18 | majeur | Un taux de réserve non vérifié gonflait le montant en actions | Les intérêts ne sont jamais déduits de P(A) ; ils sont montrés à part (§F4, F5, §12) | `F/f2_poches.py` |
| K19 | majeur | W4 appelait « FUITE » le comportement de la règle testée | W4 comparé à l'argent qui dort prévu ; information sans « FUITE » quand la cause est la règle testée (§F8) | — |
| K20 | majeur | W7 lisait le retard du panel au lieu des bulletins manquants | Condition sur `sessions.available` dans la fenêtre de 126 séances (§F8) | lecture de `D/brvm_alpha/portfolio/recommend.py` et de `sessions.parquet` |
| K21 | majeur | Règle 10 contraire à la maquette et à la recette | Écran arrondi (sens prudent, signe gardé) ; détail et JSON au franc ; recettes au franc sur le JSON (§1, F1) | — |
| K22 | mineur | « 77 % » à côté de 284 714 FCFA de frais | « 90 % de ces frais sont supposés ou estimés » (§F1) | `F/f7_divers.py` |
| K23 | mineur | Test du lexique mal défini | Mots entiers, normalisation, liste blanche, phrase négative définie (§1.1) | — |
| K24 | mineur | `--apport` : invariant faux | Voir K2 | `F/f5_tranches.py` |
| K25 | mineur | Étape 6 de F4 imprécise | Boucle bornée à 10 appels, ordre interne `rendement=False`, appel juste avant le `return`, `rendement_ctx` retiré (§4.3, F4) | — |
| K26 | mineur | Précisions statistiques des §8.1 et §8.2 | « neuf fois sur dix » ; statut Estimation ; bulletin « 3,3 à 4,2 points » ; budget de S0 à S1 (§8.1, §8.2, F10) | — |
| K27 | mineur | « 60 mois sous le plus haut » imprécis | 59 mois avec les dividendes, 95 mois sans (§F14) | `F/f6_indices.py` |
| K28 | mineur | Nom de l'utilisateur dans un fichier suivi par git | Initiales ou pseudonyme ; `suivi declarer` seulement dans le dépôt de développement (§F9, §8.7) | — |
| K29 | mineur | Textes à rendre plus francs | `PH_ETUDE` ; ligne « tout en actions » ; « se retourner ou s'aggraver » ; `PH_NE_PAS_TRANSMETTRE` ; phrase sur S1 retirée (§1.2, F1, F10, F13, §7.3) | — |
| K30 | mineur | Contraintes de code omises | Python 3.11 (§9) ; « moteur du test, plus un refus » (§8.2) ; cache de la carte (§4.2, F1) ; définition de PLAN (§8.6) ; retard en valeur de part (§F10) | lecture de `D/tests/test_compat_python311.py` |

---

## 3. Classement des changements : arithmétique pure, ou changement de règle

Règle de classement : un changement est « arithmétique pure » s'il ne modifie aucune quantité, aucun prix limite et aucun montant de l'ordre par défaut, ou s'il corrige une date affichée d'après un fait. Tout changement qui modifie les titres achetés, leur nombre, le moment des achats ou des ventes change la règle REF ou son exécution : c'est une option éteinte par défaut, déclarée avant le 01/12/2026 et suivie sur S2.

| N° | Changement | Effet sur l'ordre par défaut | Classe | Décision | Justification |
|---|---|---|---|---|---|
| 1 | Section « Rendement net et pertes », bloc « L'essentiel », clé JSON `rendement_net` | Texte ajouté. Quantités, prix, frais identiques | Arithmétique pure (affichage) | **Par défaut** | N'entre dans aucun calcul de l'ordre |
| 2 | Avertissements « FUITE : » et « À VÉRIFIER : » ajoutés en fin de liste | Texte ajouté | Arithmétique pure | **Par défaut** | L'avertissement actuel se tait à 10 M alors que les frais annuels mangent 28,5 % des dividendes nets attendus |
| 3 | Lectures du risque ; libellé de « P(battre le TR) » | Texte ajouté ou réécrit ; clé JSON `p_battre_tr` inchangée | Arithmétique pure | **Par défaut** | Corrige une lecture trop favorable |
| 4 | Provision d'entrée et part investie maximale affichées | Texte ajouté | Arithmétique pure | **Par défaut** | La cible de 98 % n'est pas atteignable avec la règle du pire cas (97,81 %) |
| 5 | Date de paiement projetée : détachement + 1 jour ouvré | Une date affichée change d'un jour | Arithmétique pure (correction d'un fait) | Par défaut **après accord écrit** (P2) | 35 cas sur 35 en 2026 [Fait, `M/jury/marche/j2_microstructure.py`] |
| 6 | Grille du courtier | Change les frais affichés ; les quantités seulement si la provision ne tient plus | Paramètre de coûts, pas la règle | **Option** `--grille` ; la commande `plan` l'emploie si elle existe | Le défaut de `recommend` reste `--couts central` |
| 7 | Perte acceptée → montant en actions | Change le capital confié à la règle | Décision de mandat (§6 de la spécification : aucun modèle ne décide de la part en actions) | **Option** `--perte-toleree` | La règle REF s'applique sans changement à la poche |
| 8 | Arrondi « plus forts restes » avec marge | +65 485 FCFA investis à 10 M (+0,65 point), +61 025 à 1 M (+6,1 points) | **Change l'exécution de REF** | **Option non par défaut** `--arrondi restes` ; écart déclaré E-A (§8.3) ; absent du témoin REF-S2 | Le §6 dit « arrondi vers le bas » ; deux tests le vérifient ; S1 a été joué ainsi ; la marge du pire cas tombe de 133 269 à 66 323 FCFA et devient négative (−14 720 FCFA) si le courtage réel est de 1,5 % |
| 9 | Compléter un ordre servi en partie ; apport d'argent frais hors bande | Achats en plus | **Change la règle** (bande du §6) | **Option** `--completer`, `--apport` ; écart déclaré E-B | Sans cela, après trois tranches de 3 333 333 FCFA : 7 368 680 FCFA investis (74,3 % de la valeur) et 2 514 330 FCFA de liquidités, en comptant les vraies liquidités (`--cash`) [Fait, outil, `Rv/echelon/t3_B.json`, `F/f5_tranches.py`] |
| 10 | Réinvestissement mensuel des liquidités | Achats en cours d'année | **Change la règle** (§7.1.6, D8) | **Option** `--reinvestir` ; **essai** E-D, jugé sur S2 (spécification §8.5, décision (ii)) | Aucun appui dans le passé : c'est une question ouverte par la spécification, à juger sur S2 seulement |
| 11 | Continuité des données | Supprime des ventes dues à un trou de bulletins | **Change la règle** (D1) | Dans `recommend` : alerte W7 seulement, par défaut. Option `--continuite` (jamais comprise dans `--suivi`) ; **essai** E-C, jugé sur S2 (spécification §8.5, décision (i)) | Un épisode a coûté 314 040 FCFA de frais sur S1 (55 ordres, août à octobre 2021) [Fait publié, `D/reports/validation_S1/trades.parquet`] |
| 12 | Mémoire annuelle `--suivi` | Avec un portefeuille suivi, aucun ordre hors remise à niveau de janvier et sorties forcées de la règle | Reproduit la règle testée (D1 et D8 tels que codés), **sans aucun écart** | **Option** ; l'avertissement W8 est ajouté au mode par défaut quand un portefeuille est fourni | Le comportement par défaut des commandes existantes ne change pas ; interface : paramètre `memoire_ref` (§4.3) |
| 13 | Réserve en francs au lieu de 2 % | — | Change un paramètre figé (`gross_equity`) | **Écarté** ; la réserve de fonctionnement est seulement affichée | Un essai de plus pour quelques milliers de FCFA de dividendes par an |
| 14 | Notes de l'analyste dans l'ordre | L'ordre par défaut les applique déjà | Écart **existant** à la règle testée (D11 : aucun rôle sur S1) | Défaut inchangé ; déclaré comme essai « N » (§8.4) | Les notes retirent aujourd'hui ETIT : 6,16 points de poids |
| 15 | Alerte « portefeuille fourni sans `--cash` » (W9) | Texte ajouté | Arithmétique pure (affichage) | **Par défaut** | Sans `--cash`, l'outil prend liquidités = capital − titres : avant la 3e tranche, la valeur réelle est de 9 913 769 FCFA et non 10 000 000 ; 86 231 FCFA de frais déjà payés (49 484 + 36 746, plus 1 FCFA d'arrondi des tranches) seraient comptés comme disponibles [Fait, `Rv/echelon/t3_B.json`, `F/f5_tranches.py`] |
| 16 | Ligne `PH_NE_PAS_TRANSMETTRE` au-dessus de la table des ordres | Texte ajouté ; titres, quantités, prix inchangés | Arithmétique pure (affichage) | **Par défaut** | L'ordre garde 20 lignes « achat » à côté de « aucun achat » |

---

## 4. Architecture

### 4.1 Fichiers nouveaux

```
brvm_alpha/rendement/__init__.py     # construire(ordre, ...) : assemble la clé rendement_net ; ne lève jamais
brvm_alpha/rendement/reglages.py     # lecture de configs/rendement_net.yaml, constantes de texte (§1.2), lexique
brvm_alpha/rendement/grille.py       # F2 : GrilleSGI, lecture, contrôle, vers_cost_model, exemples, questions
brvm_alpha/rendement/bilan.py        # F3 : brut au net, part supposée, fourchettes, lignes, aller-retour, leviers
brvm_alpha/rendement/perte.py        # F4, F5 : poche, table de choix, montant en actions, réserve
brvm_alpha/rendement/risque.py       # F6 : lectures du risque, blocs, périodes réelles, concentration
brvm_alpha/rendement/liquidites.py   # F7, F13c : argent qui dort, projection, provision, arrondi « restes »
brvm_alpha/rendement/alertes.py      # F8, F11 : avertissements de fuite, trois feux, vie d'une alerte
brvm_alpha/rendement/plan.py         # F1 : écran « Mon plan », rendus texte, Markdown, HTML
brvm_alpha/rendement/rendu.py        # blocs Markdown et HTML communs (section de l'ordre, sous-blocs du rapport)
brvm_alpha/suivi/__init__.py
brvm_alpha/suivi/declaration.py      # F9 : déclaration S2, chaîne d'empreintes, inscription au registre
brvm_alpha/suivi/temoin.py           # F10 : fabrique temoin_model ; portefeuilles REF-S2 et N par le moteur existant
brvm_alpha/suivi/carnet.py           # F12 : journal en ajout seul, prix de revient
brvm_alpha/suivi/papier.py           # F12 : exécution sur papier avec test de limite
brvm_alpha/suivi/etat.py             # F12 : valeur, pont « fuites / pertes latentes »
brvm_alpha/suivi/bulletin.py         # F10 : ligne de la semaine, bulletin texte / Markdown / JSON
configs/rendement_net.yaml           # paramètres du module (§4.4)
reports/suivi_S2/declaration.jsonl   # déclaration signée (suivie par git, datée par un commit)
tests/test_rendement_*.py, tests/test_suivi_*.py
```

Aucun paramètre du module n'entre dans `configs/strategy_v1.yaml` : un test compare ce fichier au texte de la spécification (`D/tests/test_settings_reference.py`), et son empreinte date les essais.

### 4.2 Données de l'installation (jamais dans le dépôt)

Les chemins passent par `brvm_alpha.paths.DATA_DIR` (variable `BRVM_ALPHA_DONNEES`), comme le reste de l'installation.

```
<données>/profil/grille_sgi.yaml         # grille du courtier
<données>/profil/plan.json               # perte acceptée, taux de la réserve, besoin d'argent, options choisies
<données>/profil/plan_cache.json         # écran « Mon plan » calculé (rendement_net de l'ordre du jour), écrit par le
                                         # rapport de nuit et par `plan` ; lu par la carte du Tableau de bord
<données>/profil/signature.json          # initiales ou pseudonyme choisis pour signer la déclaration (jamais dans git)
<données>/suivi/REF-S2/                  # témoin : semaines.csv, operations.csv, positions.csv, empreintes.jsonl
<données>/suivi/N/                       # essai « avec notes »
<données>/suivi/E-C/, <données>/suivi/E-D/   # essais « REF-S2 + un écart », seulement s'ils sont déclarés (§8.4)
<données>/suivi/PLAN/                    # ordre par défaut + écarts déclarés « oui » + mémoire (10 M, tarif supposé)
<données>/suivi/MOI/                     # portefeuille de l'utilisateur, papier ou réel (privé)
```

La carte « Mon plan » ne lance jamais `recommend` : elle lit `plan_cache.json` (empreinte de l'ordre et date du bulletin dans le fichier). Une saisie de grille recalcule seulement les frais sur les lignes du cache (`grille.comparer`), en moins d'une seconde. Si le cache date d'un bulletin plus ancien que le panel, la carte l'écrit (« calculé sur le bulletin du jj/mm ») et propose de recalculer dans le fil de travail existant.

Chaque fonction qui lit ou écrit ces dossiers accepte un paramètre `dossier` : les tests n'ouvrent jamais les données réelles.

### 4.3 Points de raccord dans le code existant

| Fichier | Addition | Défaut | Risque pour les tests existants |
|---|---|---|---|
| `config.py`, `CostModel` | champ `account_fee_fixed_fcfa: float = 0.0` (forfait de compte par an) | 0 | nul : `test_costmodel_fields_cover_yaml_scenario_fields` vérifie une inclusion |
| `portfolio/recommend.py`, `OrdreDeBataille` | champ `rendement_net: dict = field(default_factory=dict)` ajouté **après** `bandeau` ; clé `rendement_net` dans `to_dict()` | `{}` si le calcul échoue | nul : champ facultatif en fin de classe |
| `recommend.py`, `recommend()` | paramètres nommés : `grille=None`, `arrondi="bas"`, `apport=None`, `completer=None`, `reinvestir=False`, `continuite=False`, `memoire=None` (dictionnaire de `carnet.memoire()`), `perte_toleree=None`, `taux_reserve=None`, `rendement=True`. **Juste avant le `return`** (coûts, dividendes, distribution, stress et avertissements déjà calculés), si `rendement` est vrai : `rendement.construire(ordre, panels=…, asof=t, capital=capital, costs=cm, grille=grille, perte_toleree=…, taux_reserve=…, plan_enregistre=…, suivi=…, appel=dict(variant=…, notes_store=…, notes_known_at=…, validation_dir=…, n_boot=…, seed=…, panel_dir=…, sessions=…, today=…))` dans un `try`. `appel` sert seulement à relancer `recommend(..., rendement=False)` pour la vérification de F4 (étape 6) ; il n'y a pas de paramètre `rendement_ctx` | comportement actuel | nul |
| `strategy/alpha.py`, `BrvmAlpha.__init__` | un seul paramètre nommé nouveau, `memoire_ref: Optional[Mapping] = None` (`{"annee": int, "date": Timestamp}`) : s'il est fourni, il amorce `self._sleeves["ref"] = {"year": annee, "t": date}`, exactement l'état que le moteur garde entre deux décisions (`_reference_portfolio`) ; `None` laisse le comportement actuel | `None` | nul : aucun appel existant ne le passe ; empreinte de configuration inchangée |
| `recommend.py`, `_cost_summary` | clé `forfait_compte_annuel` = `round_fcfa(costs.account_fee_fixed_fcfa)` | 0 | nul |
| `recommend.py`, `_distribution_for` | frais fixes déduits = garde + tenue de compte + forfait | inchangé quand le forfait vaut 0 | nul |
| `recommend.py`, `_build_plan` | branches `arrondi == "restes"`, `apport`, `completer`, `reinvestir`, `continuite`, `memoire` (passe `memoire_ref` au modèle) | éteintes | nul par défaut |
| `recommend.py`, `_blocks` | bloc « L'essentiel » (titre de niveau 3) après les avertissements ; section « Rendement net et pertes » (niveau 2) après « Revenus attendus » ; libellé « P(battre le TR) » réécrit ; une ligne dans « Exécution » ; ligne `PH_NE_PAS_TRANSMETTRE` juste au-dessus de la table des ordres (le titre de la table ne change pas) | — | faible : `_renumber_sections` renumérote ; le titre de niveau 1 reste premier ; l'ordre des avertissements existants ne change pas |
| `backtest/engine.py` | une seule addition : refus explicite si `costs.account_fee_fixed_fcfa != 0` (`NotImplementedError` : « forfait de compte non simulé »). Aucune option nouvelle : les écarts d'exécution vivent dans `recommend --suivi` et dans l'exécution sur papier | — | nul : les quatre scénarios du YAML ont un forfait nul |
| `cli.py` | commandes `plan` et `suivi` ; options nouvelles de `recommend` et `report` (§6) | — | nul |
| `report/html.py` | sous-blocs **à la fin** des sections existantes (§7.2) ; `SECTIONS` garde 11 entrées | — | faible |
| `ui/pages.py`, `ui/server.py` | carte « Mon plan » en tête du Tableau de bord ; champs de la page Portefeuille ; tableau sur la page Validation ; routes du §7.1 ; `NAV` garde 7 entrées | — | **certain** : les empreintes `GOLDEN` de `tests/test_deploiement_ui.py` (lignes 36-51, 146-152) et la couverture des routes (lignes 155-162, 315-322) échouent par construction. Exception déclarée au §9.1 |
| `deploiement/quotidien.sh` | étape `suivi maj` entre `panel` et `report` | — | **certain** : les listes exactes d'appels de `tests/test_deploiement_scripts.py` (lignes 225-226 et 236-237) échouent par construction. Exception déclarée au §9.1 |

`rendement.construire` ne lève jamais d'exception. Chaque bloc est calculé à part ; un bloc en échec vaut `{"erreur": "<message>"}` et s'affiche « non calculé », jamais comme un zéro.

### 4.4 Paramètres : `configs/rendement_net.yaml`

| Clé | Défaut | Statut | Origine |
|---|---|---|---|
| `dates.debut_suivi` | 2026-12-01 | Fait | YAML de stratégie, `S2_live_from` |
| `dates.premiere_decision_argent_reel` | 2027-06-01 | Fait | spécification §8.1 (6 mois) |
| `dates.affirmation_performance` | 2029-12-01 | Fait | spécification §8.1 (36 mois) |
| `frais.irvm_verifies` | [CI, SN] | Fait | recherche 01 ; BF, BJ, TG, GW : non vérifiés |
| `frais.seuils_frais_annuels_sur_dividendes` | [0,15 ; 0,50 ; 1,00] | Hypothèse | choisis sans base statistique |
| `frais.chutes_dividendes` | [0,075 ; 0,20] | Estimation | total des dividendes : −7,5 % en 2020 ; par titre, une baisse sur dix atteint −18 % (`M/jury/rigueur/j5_dividendes.py`) |
| `frais.rotation_basse_mensuelle` | 0,0087 | Estimation | diagnostic S0 contaminé (`M/rendement/rapport.md` §6.2) |
| `frais.remise_a_niveau_haute` | 0,0123 | Estimation | S1 publié : 0,66 + 0,57 point par an (`M/rendement/a2_ref_decomposition.py`) |
| `frais.horizon_ans` | 3 | Hypothèse | choix d'affichage |
| `frais.grilles_exemple` | voir §F2 | Fait pour les fourchettes homologuées ; Hypothèse pour l'utilisateur | recherche 01 §5.1 |
| `perte.pas_fcfa` | 100 000 | Hypothèse | choix d'affichage |
| `perte.choc_2018_ref_publie` | 0,2932 (valeur de repli) | Estimation (lecture d'un résultat publié, pas un test) | calculé à chaque appel par `perte.choc_ref_publie(validation_dir, panels)` (§F4, étape 2) ; la valeur du fichier ne sert que si les fichiers publiés sont illisibles, avec la mention « choc de repli » ; `F/f1_sref.py` |
| `perte.choix_parts` | [0,05 ; 0,10 ; 0,20] | Hypothèse | lignes de la table de choix |
| `reserve.taux` | vide (compté à 0) | Hypothèse | saisi par l'utilisateur ; **n'entre jamais dans la perte estimée** P(A) |
| `risque.blocs_semaines` | [8 ; 26 ; 52] | Estimation | 8 = valeur de la spécification ; 26 et 52 = sensibilité |
| `risque.graines` | 20 (graines 0 à 19) | Hypothèse | médiane affichée ; graine 0 gardée pour la recette (`F/f4_graines.py`) |
| `affichage.pas_fcfa` | 1 000 sous 100 000 ; 10 000 au-dessus | Hypothèse | règle 10 du §1 |
| `feux.fenetre_trou_seances` | 126 | Fait | plus longue fenêtre des filtres D1 du YAML de stratégie (`universe.min_history_sessions`) ; sert à W7 |
| `risque.choc_titre` | 0,30 | Hypothèse | stress ST8 existant |
| `liquidites.trimestres_reserve` | 2 (affiche aussi 3) | Hypothèse | deux prélèvements avant les dividendes de mai |
| `liquidites.seuil_argent_qui_dort_fcfa` | 100 000 | Hypothèse | choisi sans base statistique |
| `liquidites.delai_argent_qui_dort_seances` | 20 | Hypothèse | idem |
| `liquidites.marge_arrondi_trimestres` | 2 | Hypothèse | `M/liquidites/rapport.md` §2.3 |
| `liquidites.surcout_courtage_test` | 0,002 | Hypothèse | alerte de marge du pire cas |
| `feux.perte_paliers` | [0,5 ; 1,0 ; 1,5 ; 2,0] de la perte acceptée | Hypothèse | choisis après lecture de S0, sans base statistique |
| `feux.perte_sans_choix` | [0,10 ; 0,20] de l'argent engagé en actions | Hypothèse | idem |
| `feux.ligne_baisse_paliers` | [0,25 ; 0,35 ; 0,45] depuis l'achat | Hypothèse | idem ; 1,0 ligne par an sur S0 (contaminé) |
| `feux.ligne_part_perte` | 0,10 de la perte acceptée (sans choix : 0,01 de la valeur) | Hypothèse | idem |
| `feux.frais_ecart` | 1 000 FCFA et 5 % | Hypothèse | idem |
| `feux.bulletins_manquants` | orange 1, rouge 3 | Hypothèse | idem |
| `feux.retard_journal_jours` | 9 | Hypothèse | idem |
| `suivi.capital_temoin_fcfa` | 10 000 000 | Fait | capital de référence de la spécification |
| `suivi.validite_ordre_seances` | 10 | Fait | spécification §7.1.1 |
| `suivi.participation_volume` | 0,10 | Fait | spécification §7.1.2 |

### 4.5 Clé JSON `rendement_net` de l'ordre de bataille

```
"rendement_net": {
  "version": 1,
  "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti.",
  "etude": {"statut": "REJETÉ", "phrases": [PH_ETUDE, PH_SEANCE rendue à la date du jour], "debut_suivi": "2026-12-01",
            "premiere_decision_argent_reel": "2027-06-01", "argent_reel_recommande": false},
  "grille": {"nom", "statut_global", "champs": {"courtage": {"valeur", "statut", "source", "date"}, ...}},
  "bilan": {"lignes": [{"code", "libelle", "montant", "frequence", "statut", "action", "levee_par"}],
            "totaux": {"fuites_an1", "fuites_suivantes", "reste_an1", "reste_suivant",
                       "part_supposee",            // statut le plus faible, sur la facture (impôt compris)
                       "part_supposee_frais",      // sur les seuls frais de la 1re année
                       "levee_par": {"grille", "execution", "taux_impot_non_verifie", "dividendes_estimes"},
                       "par_action", "controle_ecart"},
            "dividendes_en_baisse": [{"chute", "reste_an1", "reste_suivant"}],
            "remise_a_niveau": {"bas", "haut"}, "aller_retour": {...}, "lignes_petites": [...]},
  "leviers": {"frais_evites": [...], "inconnues": [...], "argent_place": [...]},
  "perte": {"chocs": {"beta", "ref_publie", "ref_publie_source": "mesuré" | "repli", "retenu",
                      "en_cours_d_annee", "2017_2020"},
            "table": [{"perte_toleree", "en_actions", "reserve", "investi", "frais_an1", "annee_2018": [bas, haut],
                       "pire_moment_2018", "baisse_2017_2020", "depasse": {"pire_moment": bool, "2017_2020": bool},
                       "rapport_2017_2020_sur_2018": float, "reste_an1", "reste_suivant",
                       "annee_ordinaire": {"prudente", "flatteuse"}, "prix_prudence": float, "mention"}],
            "choix": null | {...ligne retenue, "verifie_par_ordre": true, "appels": int}},
  "reserve": {"montant", "taux", "statut", "interets", "valeur_d_un_point", "deduit_de_la_perte": false},
  "risque": {"lectures": [{"nom", "bloc", "graine_0": {...}, "mediane_graines": {...}, "min_max_graines": {...}}],
             "periodes_reelles": {...}, "phrases": [PH_PASSE, PH_DESCRIPTIF], "concentration": [...]},
  "liquidites": {"decomposition": {...}, "reserve_fonctionnement": {...}, "argent_qui_dort": {...},
                 "projection": {...}, "provision": {...}, "arrondi_possible": {...}},
  "passer_l_ordre": {"consignes": [...], "carnet": {...}},
  "alertes": [{"code", "niveau", "prefixe": "FUITE" | "À VÉRIFIER" | null, "texte", "cause"}],
  "suivi": null | {"feux": {...}, "semaine": {...}},
  "plan": {"lignes": [...], "une_chose": "..."}
}
```

Aucune clé existante de l'ordre n'est renommée ni retirée.

---

## 5. Les fonctions

Priorités : **P0** = arithmétique ou affichage, aucune règle changée, à livrer d'abord ; **P1** = suivi et options d'exécution déclarées ; **P2** = confort.

| N° | Fonction | Priorité | Nature |
|---|---|---|---|
| F1 | Écran « Mon plan » | P0 | affichage |
| F2 | Ce que prend mon courtier : la grille réelle | P0 | paramètres de coûts |
| F3 | Du brut au net : la facture, ce qui est supposé, les leviers | P0 | arithmétique |
| F4 | Ce que j'accepte de risquer → montant en actions | P0 | décision de mandat |
| F5 | Où dort le reste, et à quel taux | P0 | saisie, arithmétique |
| F6 | Lectures du risque | P0 | statistique descriptive |
| F7 | Argent qui dort, provision d'entrée, « passer l'ordre » | P0 | arithmétique, affichage |
| F8 | Avertissements de fuite dans l'ordre | P0 | affichage |
| F9 | Déclaration du suivi S2 | P0, avant le 01/12/2026 | protocole |
| F10 | Journal de suivi et bulletin de la semaine | P0 (témoin) puis P1 | comptabilité |
| F11 | Trois feux et revue guidée | P1 | affichage, revue humaine |
| F12 | Carnet, exécution sur papier, pont « fuites / pertes latentes », avis d'opéré | P1 | comptabilité |
| F13 | Options d'exécution (toutes éteintes par défaut) | P1 | changements d'exécution déclarés |
| F14 | Durée : « quand aurez-vous besoin de cet argent ? » | P1 | descriptif, arithmétique |
| F15 | Entrer en plusieurs fois | P2 | changement de calendrier, non validé |
| F16 | Date de paiement projetée | P2 | correction d'un fait |

Notations communes. K : capital total (argent engagé : apports − retraits). V : valeur du portefeuille = titres au cours de référence + **liquidités réelles** (lues dans le carnet, ou données par `--cash`) ; jamais « capital − titres » quand un portefeuille est fourni, car ce calcul recrédite les frais déjà payés (§F8, W9). O : ordre de bataille. Pour une ligne i de O : poids cible `w_i` (`poids_cible`), cours de référence `p_i` (`cours_reference`), limite d'achat `L_i` (`limite_achat`), quantité cible `q_i` (`cibles`), valeur après ordres `v_i` (`valeur_apres`). Tous les arrondis au franc passent par `recommend.round_fcfa`.

---

### F1 — Écran « Mon plan » (P0)

**Objet.** Un écran pour un particulier pressé. Il répond à : que faire à la prochaine séance (rien acheter), ce que chaque choix change en FCFA, quoi regarder chaque semaine. Il existe en quatre formes au même contenu : commande `plan`, première carte du Tableau de bord, carte en tête du rapport HTML, bloc « L'essentiel » de l'ordre de bataille (version courte, 14 lignes au plus). Les trois premières sont des formes « écran » (montants arrondis, règle 10) ; le bloc « L'essentiel » et `plan --format md` sont des formes « détail » (montants au franc).

**Calcul.** L'écran ne calcule rien. Il assemble les sorties de F2 à F7 et de F10-F11.

- Entrées : l'ordre du capital total (`rendement_net`), le plan enregistré (`<données>/profil/plan.json` : perte acceptée, taux de la réserve, besoin d'argent), la grille, la dernière ligne du journal. La carte du Tableau de bord lit ces entrées dans `<données>/profil/plan_cache.json` (§4.2), jamais en relançant `recommend`.
- Ordre des blocs : `BANNER` ; `PH_ETUDE` ; `PH_SEANCE` ; décision 1 (courtier) ; décision 2 (ce que j'accepte de risquer : la table de choix, ou la ligne retenue), **suivie de `PH_PASSE`, de `PH_DESCRIPTIF` et de la phrase de synthèse de F6** ; décision 3 (réserve, avec `PH_INTERETS`) ; « Si vous ne faites qu'une chose cette semaine » ; tableau « Ce que vous recevriez et ce qui partirait » ; `PH_COURS` ; les trois feux.
- Table de la décision 2, une ligne par choix, et sur la **même ligne** (ou la ligne qui la suit immédiatement, dans le même bloc) : en actions ; en réserve ; « année comme 2018 » (fourchette) ; « année ordinaire » en **lecture prudente seulement** (marché chargé des mêmes frais, F6) ; « pire moment de 2018 » et « si 2017-2020 revenait » en FCFA, suivis de « (dépasse) » ou « (les deux dépassent) » quand le montant exact dépasse X. La lecture flatteuse (passé rejoué) n'apparaît que dans le détail (Markdown, JSON). La dernière ligne s'intitule « tout » et la phrase sous la table dit « « tout » : tout en actions ».
- « Si vous ne faites qu'une chose cette semaine » : le premier geste non fait dans cet ordre fixe : (1) envoyer les 8 questions au courtier ; (2) choisir ce que j'accepte de risquer ; (3) saisir le taux de la réserve ; (4) lire le bulletin de la semaine. **Jamais un achat.**
- Tableau « Ce que vous recevriez et ce qui partirait » : montants de la poche retenue (ou de K si rien n'est choisi) **et** de la grille en vigueur, ensemble. Lignes : dividendes attendus, impôt déduit ; frais d'achat ; frais annuels du courtier ; « dividendes moins frais » la 1re année, avec la variante « si les dividendes baissent de 20 % » ; « années suivantes, sans transaction », avec la fourchette de la remise à niveau de janvier (F3). Le libellé est « dividendes moins frais », jamais « il reste » ni « gain ». Phrase « Montants arrondis. » une fois sous le tableau.
- Arrondi : `reglages.arrondi_ecran(x)` (règle 10), `x` signé du point de vue de l'utilisateur : frais, pertes, remise à niveau et prix de la prudence entrent avec le signe moins ; dividendes, « dividendes moins frais », frais évités et année ordinaire avec leur signe propre.

**Sortie.** `rendement_net.plan` : `{"lignes": [{"bloc", "texte", "montant", "montant_ecran", "statut"}], "une_chose": str, "feux": {...}}` ; `montant` au franc, `montant_ecran` = texte arrondi. Fonctions : `plan.construire_plan(rendement_net, plan_enregistre, suivi, aujourd_hui) -> dict` ; `plan.rendre_plan(plan, fmt)` avec `fmt` ∈ {`texte`, `md`, `html`} (`texte` et `html` : formes écran ; `md` : forme détail).

**Cas limites.**
- Aucun plan enregistré : la table de choix à quatre lignes s'affiche ; la grille est « tarif supposé, non vérifié » ; le taux de la réserve est « inconnu : compté à 0 % ».
- Panel en retard : l'avertissement existant « PANEL EN RETARD » reste au-dessus de l'écran.
- Capital sous le minimum d'un titre par ligne (964 573 FCFA au 20/11/2026) ou frais annuels supérieurs aux dividendes attendus : la première ligne de l'écran devient « À ce tarif, 20 lignes coûtent plus qu'elles ne rapportent : X FCFA de frais par an pour Y FCFA de dividendes attendus. » (à 1 M : 102 166 pour 38 458, soit 63 708 FCFA de moins par an à cours inchangés).
- Journal absent : feux « — », mention « le suivi n'a pas commencé ».
- Bloc en échec : « non calculé » sur la ligne, jamais 0.
- Cache absent ou plus ancien que le dernier bulletin : la carte l'écrit et propose « Recalculer » (fil de travail existant) ; elle n'affiche jamais un montant d'un autre bulletin sans sa date.

**Maquette de référence, avant toute saisie (10 000 000 FCFA, 20/11/2026, forme écran, rendue le 22/11/2026).** 44 lignes, 100 colonnes au plus. Montants arrondis par la règle 10 à partir des valeurs exactes des §F3, F4 et F6 (`F/f2_poches.py`) ; gabarit vérifié par `F/maquette/fabrique.py`.

```
MON PLAN — 10 000 000 FCFA — cours du vendredi 20/11/2026
Performance passée ≠ garantie. Aucun gain n'est garanti.
Étude seulement : aucune méthode de la plate-forme n'a réussi son test. Sur 2017-2022, la règle
de référence, sans les notes, a fait 5,6 points de moins par an que le marché ; les notes n'ont
jamais été testées. Prochaine séance : aucun achat. Aucune méthode n'est validée : avec les
règles actuelles, la plate-forme ne recommandera pas d'argent réel. Changer ces règles serait
votre décision, jamais avant le 01/06/2027 (6 mois de suivi sur papier à partir du 01/12/2026).

1. CE QUE PREND MON COURTIER (SGI)                              [ tarif supposé, non vérifié ]
   Si vous achetiez tout : environ 290 000 FCFA de frais la 1re année, puis 130 000 par an.
   Dont 100 000 FCFA par an de tenue de compte [supposé]. 90 % de ces frais : supposés ou estimés.
   -> Envoyez les 8 questions à votre courtier. Avec la seule grille connue sans frais par ligne :
      environ 73 000 FCFA de moins la 1re année, puis 96 000 de moins par an [supposé].
      0 si votre courtier ne facture pas ce poste.

2. CE QUE J'ACCEPTE DE RISQUER SUR 12 MOIS                     [ à choisir ; montants estimés ]
   Je risque  En actions  En réserve   Année comme 2018          Année ordinaire (prudente)
     500 000   1 400 000   8 600 000   −420 000 à −480 000       −11 000 ; frais > dividendes
      pire moment de 2018 : −510 000 ; si 2017-2020 revenait : −660 000 (les deux dépassent)
   1 000 000   3 000 000   7 000 000   −830 000 à −980 000       +110 000
      pire moment de 2018 : −1 040 000 ; si 2017-2020 revenait : −1 410 000 (les deux dépassent)
   2 000 000   6 300 000   3 700 000   −1 660 000 à −1 980 000   +370 000
      pire moment de 2018 : −2 110 000 ; si 2017-2020 revenait : −2 900 000 (les deux dépassent)
        tout  10 000 000           0   −2 600 000 à −3 120 000   +660 000
      pire moment de 2018 : −3 330 000 ; si 2017-2020 revenait : −4 590 000
   « tout » : tout en actions. Ce ne sont pas des limites. Fréquences d'un seul passé (2017-2026 :
   quatre années de baisse, puis six de hausse). Ce ne sont pas des probabilités. Descriptif, pas
   un test. Environ 26 % à 40 % des périodes de 12 mois ont fini en perte.

3. OÙ DORT LE RESTE, ET À QUEL TAUX                             [ taux inconnu : compté à 0 % ]
   Pendant l'étude, vos 10 000 000 FCFA attendent : un point d'intérêt vaut 100 000 FCFA par an.
   Les intérêts de la réserve ne sont jamais déduits de la perte estimée. -> Question 7.

SI VOUS NE FAITES QU'UNE CHOSE CETTE SEMAINE : envoyez les 8 questions à votre courtier.

CE QUE VOUS RECEVRIEZ ET CE QUI PARTIRAIT (FCFA) — 1re année, cours inchangés, tout en actions
   Dividendes attendus, impôt déduit   environ +430 000  [estimé : dernier dividende reconduit]
   Frais d'achat                       environ −170 000  [supposé et estimé]
   Frais annuels du courtier           environ −130 000  [supposé]
   Dividendes moins frais              environ +150 000  [estimé] +64 000 si dividendes −20 %
   Années suivantes, sans transaction  environ +310 000  [estimé] remise à niveau −35 000 à −130 000
   Montants arrondis. Les cours peuvent monter ou baisser bien plus que ces montants.

TROIS FEUX CHAQUE SEMAINE    Perte : —    Fuites : —    Données : —    (le suivi n'a pas commencé)
```

Valeurs exactes derrière la maquette (clés JSON, au franc) : frais 284 714 puis 124 126 ; part supposée ou estimée des frais 89,8 % ; écart avec la grille connue 73 224 puis 96 000 ; table du §F4 ; dividendes 435 988 ; frais d'achat 160 588 ; dividendes moins frais 151 274 (64 076 avec −20 %) ; ensuite 311 862 ; remise à niveau 34 745 à 123 000.

**Intégration.** Module `rendement/plan.py`. Commande `plan` (§6). Interface : carte « Mon plan » en tête du Tableau de bord (§7.1). Rapport : carte dans la section `bandeau` (§7.2). Ordre de bataille : bloc « L'essentiel » (§7.3). JSON : `rendement_net.plan`.

**Tests** (`tests/test_rendement_plan.py`).
1. `BANNER`, `PH_ETUDE`, `PH_SEANCE`, `PH_PASSE` et `PH_DESCRIPTIF` présents dans les quatre formes ; `PH_PASSE` et `PH_DESCRIPTIF` placés après la table de la décision 2.
2. Aucun mot interdit du §1.1 (comptés comme au §1.1) dans le texte de l'écran ; le mot « achetez » n'apparaît que dans une phrase au conditionnel ou négative ; « une chose cette semaine » ne contient jamais « acheter ».
3. 45 lignes au plus, 100 colonnes au plus.
4. Un statut (`compté`, `estimé`, `supposé`) sur chaque ligne de montant.
5. Mêmes montants exacts dans le JSON et le Markdown ; les formes écran (texte, HTML) affichent `arrondi_ecran` de ces montants.
6. Sans plan enregistré : la table de choix a quatre lignes ; chaque ligne porte « pire moment de 2018 » et « si 2017-2020 revenait » en FCFA, avec « dépasse » quand le montant exact dépasse X.
7. Recette au 20/11/2026 (ignorée si le panel est absent). Clés JSON, au franc : 284 714 ; 124 126 ; 151 274 ; 311 862 ; 64 076 ; part des frais 0,898 ; montants en actions 1 400 000, 3 000 000, 6 300 000, 10 000 000. Écran : « environ 290 000 » ; « −830 000 à −980 000 » ; « +110 000 » ; « 90 % ».
8. Arrondi et signe : `arrondi_ecran(−501 430)` = « −510 000 » ; `arrondi_ecran(−10 489)` = « −11 000 » (un résultat négatif reste négatif) ; `arrondi_ecran(118 001)` = « +110 000 » ; `arrondi_ecran(−284 714)` rendu « 290 000 FCFA de frais » ; `arrondi_ecran(400)` = « entre 0 et +1 000 » ; aucun montant non nul affiché « 0 ».
9. `PH_SEANCE` rendue un mardi (24/11/2026), le 02/12/2026 et le 02/06/2027 : jamais « lundi », jamais « au plus tôt » ; « à partir du » avant le 01/12/2026, « depuis le » ensuite ; la troisième forme ne cite plus le 01/06/2027 comme date future.
10. La lecture flatteuse (passé rejoué) n'apparaît dans aucune forme écran ; au détail, elle est toujours suivie de `PH_FLATTE`.
11. Le rapport garde 11 sections et la section `bandeau` reste au statut `ok` même si `construire_plan` lève une exception.

**Critères d'acceptation.** Un lecteur qui ne lit que l'écran sait : qu'il ne doit rien acheter à la prochaine séance et que la plate-forme ne lui recommandera pas d'argent réel avec les règles actuelles ; quel est son premier geste ; ce que chaque choix de risque change en FCFA, en perte (dont les dépassements) et en gain d'une année ordinaire prudente ; que rien n'est garanti.

**Gain attendu.** Aucun gain direct.

---

### F2 — Ce que prend mon courtier : la grille réelle (P0)

**Objet.** L'utilisateur saisit une fois la grille écrite de son courtier. Tous les calculs du module la reprennent. Chaque valeur garde son origine : `supposé`, `grille écrite`, `avis d'opéré`.

**Objet de données `GrilleSGI`** (`rendement/grille.py`, fichier `<données>/profil/grille_sgi.yaml`).

| Champ | Unité | Défaut (tarif supposé « central ») | Saisie acceptée | Fourchette homologuée connue [Fait, recherche 01 §5.1] | Dans `CostModel` |
|---|---|---|---|---|---|
| `courtage` | part du montant | 0,008 | 0 à 0,03 | 0,004 à 0,010 | `sgi_commission` |
| `courtage_min_par_ordre` | FCFA | 0 | 0 à 50 000 | aucune dans les grilles lues | `min_ticket_fcfa` |
| `taxe_courtage` | part du courtage | 0,18 | 0 à 0,25 | non vérifiée (10 % ou 18 %) | `vat_on_commission` |
| `garde` | part de l'encours par an | 0,0025 | 0 à 0,01 | 0,001 à 0,005 | `annual_custody` |
| `tenue_par_ligne` | FCFA par ligne et par an | 5 000 | 0 à 50 000 | 0 (FGI) ; 5 000 (BICI Bourse, personne physique) ; 10 000 (personne morale) | `account_fee_per_line_fcfa` |
| `forfait_compte` | FCFA par an | 0 | 0 à 200 000 | 4 000 (FGI « bourse en ligne ») | `account_fee_fixed_fcfa` (nouveau) |
| `taxe_frais_annuels` | part de (garde + tenue + forfait) | 0 | 0 à 0,25 | inconnue | hors modèle |
| `garde_minimum` | FCFA par an | 0 | 0 à 100 000 | inconnue | hors modèle |
| `encaissement_taux` | part du dividende net | 0 | 0 à 0,05 | inconnue | hors modèle |
| `encaissement_fixe` | FCFA par paiement | 0 | 0 à 10 000 | inconnue | hors modèle |
| `transfert_par_ligne` | FCFA | 0 | 0 à 100 000 | 5 000 à 34 375 | hors modèle (affiché seulement) |
| `impot_plus_values` | part de la plus-value | 0 | 0 à 0,30 | non vérifié | hors modèle (affiché seulement) |
| `investisseur` | texte | « personne physique résidente » | ou « personne morale » | — | — |
| `pays_residence` | texte | vide | — | — | — |
| pour chaque champ chiffré : `statut`, `source`, `date` | texte | `supposé` | `supposé` / `grille écrite` / `avis d'opéré` | — | — |

**Fonctions publiques.**
- `charger(dossier=None) -> GrilleSGI` : fichier absent → grille par défaut, tous les champs `supposé`. Fichier illisible → `ValueError` avec le chemin ; aucun calcul silencieux.
- `enregistrer(grille, dossier=None) -> Path` : écrit le YAML ; refuse une valeur hors de la saisie acceptée (message : « courtage : 4 % est hors de la plage acceptée (0 à 3 %) ») ; avertit sans refuser hors de la fourchette homologuée.
- `vers_cost_model(grille, base: CostModel) -> CostModel` : `recommend.replace_costs(base, sgi_commission=…, vat_on_commission=…, min_ticket_fcfa=…, annual_custody=…, account_fee_per_line_fcfa=…, account_fee_fixed_fcfa=…)`. Les coûts dans le prix (demi-écart, impact) restent ceux de `base`.
- `frais_hors_modele(grille, couts, revenus, dividendes) -> dict` : `taxe_annuelle = round_fcfa(taxe_frais_annuels × (garde_annuelle + tenue_compte_annuelle + forfait))` ; `garde_complement = max(0 ; garde_minimum − garde_annuelle)` ; `encaissement = round_fcfa(encaissement_taux × dividendes nets) + encaissement_fixe × nombre de paiements`.
- `statut_global(grille) -> str` : `supposé` si au moins un des cinq champs principaux (courtage, taxe, garde, tenue par ligne, forfait) est `supposé` ; sinon `grille écrite` ; `avis d'opéré` si les cinq le sont.
- `exemples() -> dict[str, GrilleSGI]` : grilles d'exemple, étiquetées « exemples construits sur des grilles homologuées ; non confirmés pour vous » :

| Nom affiché | Courtage | Taxe | Garde | Par ligne | Forfait | 1re année à 10 M | Ensuite par an | Écart avec le tarif supposé |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Tarif supposé (central) | 0,80 % | 18 % | 0,25 % | 5 000 | 0 | 284 714 | 124 126 | — |
| Grille connue sans frais par ligne (FGI aux plafonds) | 1,00 % | 18 % | 0,25 % | 0 | 4 000 | 211 490 | 28 126 | −73 224 la 1re année, puis −96 000 par an |
| Bas de fourchette avec frais par ligne (BICI Bourse) | 0,40 % | 18 % | 0,10 % | 5 000 | 0 | 224 692 | 109 651 | −60 022, puis −14 475 |
| Borne non attestée (aucune grille lue ne cumule ces avantages) | 0,50 % | 18 % | 0,25 % | 0 | 4 000 | 154 556 | 28 126 | −130 158, puis −96 000 |

  [Hypothèse (tarif) ; recalcul avec les fonctions de l'outil : `S/s5_reserve_leviers.py`.]
- `comparer(ordre, grilles) -> list[dict]` : pour chaque grille, frais recalculés ligne par ligne avec `order_costs` aux quantités et tranches de l'ordre ; sorties : frais d'achat, frais annuels, 1re année, écart avec la grille en vigueur, provision du pire cas, marge. Si la provision dépasse les liquidités, mention « quantités à recalculer » et relance de l'ordre complet à la demande.
- `questions() -> list[str]` : les 8 questions, texte prêt à copier.

**Les 8 questions au courtier.**
1. Quel est mon taux de courtage sur les actions ? Y a-t-il un minimum par ordre ? Ce taux comprend-il les commissions de la BRVM (0,20 %) et du dépositaire (0,10 %) ?
2. Quelle taxe s'applique, à quel taux ? Sur le courtage seul ou sur tous les frais ? Vos tarifs sont-ils hors taxes ?
3. Droits de garde : quel taux, sur quelle base (valeur de marché à quelle date), prélevés à quelles dates ? Y a-t-il un minimum ?
4. Tenue de compte : par compte ou par ligne de titres ? Combien par an ? Le tarif change-t-il pour une personne morale ?
5. Y a-t-il des frais d'encaissement des dividendes, de virement, de transfert de titres, de modification ou d'annulation d'un ordre ?
6. Puis-je avoir un avis d'opéré type, avec toutes les lignes de frais ?
7. Le compte espèces est-il rémunéré ? À quel taux net ? Faut-il provisionner avant l'ordre ? Quand le produit d'une vente et les dividendes sont-ils disponibles ?
8. Un impôt sur les plus-values s'applique-t-il à ma situation ?

**Cas limites.** Grille partielle : les champs absents gardent le défaut et le statut `supposé`. Grille plus chère que le tarif supposé : l'écart est écrit « surcoût ». Minimum par ordre non nul : appliqué par tranche et par séance (comportement existant de `fee_breakdown`). Personne morale : avertissement « taux d'impôt sur les dividendes et tenue de compte différents : non modélisés ».

**Intégration.** Commande `plan grille` (§6). Option `--grille ma_sgi|central|FICHIER` sur `plan`, `recommend`, `report`. **Le défaut de `recommend` et de `report` reste `--couts central`.** Le défaut de `plan` est `ma_sgi` si le fichier existe, sinon `central`. Si une grille est enregistrée et que `recommend` ne l'emploie pas, la section ajoute : « Votre grille enregistrée n'est pas employée ici. Option `--grille ma_sgi`. » Interface : formulaire sur la carte « Mon plan » (cinq champs principaux, « plus de champs » repliable) et bouton « Voir les 8 questions ». Ordre et rapport : ligne « Tarif employé : … (statut : …) ». JSON : `rendement_net.grille`.

**Tests** (`tests/test_rendement_grille.py`).
1. Écriture, relecture : mêmes valeurs et mêmes statuts.
2. Une valeur refusée (courtage 4 %), une valeur avertie (courtage 0,3 %).
3. Grille par défaut : frais identiques au franc à `--couts central`.
4. Égalité au franc avec `recommend.fee_breakdown` sur 200 montants tirés au hasard, avec et sans minimum.
5. Recette au 20/11/2026 : les quatre lignes du tableau ci-dessus ; minimum de 2 500 FCFA : +13 841 à 10 M ; minimum de 1 000 FCFA : +172 ; taxe à 10 % : −6 175 ; taxe de 18 % sur les frais annuels : +22 343 par an.
6. Le dossier de profil est remplaçable : aucun test ne lit `<données>/profil/`.
7. Source `avis d'opéré` sur les cinq champs : `statut_global` vaut `avis d'opéré`.

**Critères d'acceptation.** L'utilisateur saisit cinq chiffres et voit sa facture en FCFA en moins d'une seconde (recalcul sur les lignes de l'ordre lues dans `plan_cache.json`, sans relancer `recommend`). Aucun montant de frais n'est affiché sans son statut.

**Statut des chiffres.** Commissions BRVM et DC/BR : Fait. Fourchettes homologuées : Fait. Tarif de l'utilisateur : Hypothèse tant qu'il n'est pas saisi avec une source. **Gain attendu.** 0 FCFA par elle-même. À 10 M, elle remplace par des faits **jusqu'à 215 226 FCFA** de suppositions : courtage 77 204, taxe 13 896, garde 24 126, tenue de compte 100 000 [Fait de calcul, `F/f7_divers.py`]. Elle ne touche ni aux coûts dans le prix (40 536 FCFA, estimés jusqu'aux avis d'opéré, F12), ni à l'impôt sur les dividendes (55 527 FCFA, estimé jusqu'au paiement). Elle peut aussi révéler une facture plus lourde.

---

### F3 — Du brut au net : la facture, ce qui est supposé, les leviers (P0)

**Objet.** Un tableau répond à : « sur ce que mon portefeuille verserait, combien m'arriverait, et qui prend le reste ? ». Chaque ligne dit : combien, une fois ou chaque année, compté ou supposé, et ce qu'on peut y faire.

**Calcul exact.** Entrées : `couts`, `revenus`, `dividendes`, `lignes` de l'ordre ; la grille ; `horizon_ans` H (défaut 3).

| Code | Ligne affichée | Formule | Fréquence | Statut par défaut | Action possible |
|---|---|---|---|---|---|
| B | Dividendes bruts attendus | `revenus.brut` | par an | Estimation (dernier dividende reconduit) | — |
| T | Impôt sur les dividendes | `revenus.irvm` ; par pays : taux Fait si le pays est dans `irvm_verifies`, sinon Hypothèse ; le montant est toujours au moins une **Estimation**, car il s'applique à des dividendes estimés | par an | Estimation (CI, SN) / Hypothèse (autres pays) | aucune (retenu à la source) |
| E1 | Courtage | `couts.courtage` | une fois | selon la grille | négociable |
| E2 | Taxe sur le courtage | `couts.tva` | une fois | selon la grille | à vérifier (une taxe ne se négocie pas) |
| E3 | Commission de la BRVM | `couts.brvm` | une fois | Fait | aucune |
| E4 | Commission du dépositaire (DC/BR) | `couts.dcbr` | une fois | Fait | aucune |
| E5 | Écart entre acheteurs et vendeurs | `couts.demi_spread` | une fois | Estimation | exécution |
| E6 | Effet de l'ordre sur le prix | `couts.impact` | une fois | Estimation | exécution |
| A1 | Droits de garde | `couts.garde_annuelle` + complément de minimum | par an | selon la grille | négociable |
| A2 | Tenue de compte par ligne | `couts.tenue_compte_annuelle` | par an | selon la grille | selon le courtier |
| A3 | Forfait de compte | `couts.forfait_compte_annuel` | par an | selon la grille | selon le courtier |
| A4 | Taxe sur les frais annuels | `frais_hors_modele.taxe_annuelle` | par an | selon la grille | à vérifier |
| A5 | Encaissement des dividendes | `frais_hors_modele.encaissement` | par an | selon la grille | selon le courtier |

- N = B − T. Entrée = E1 + … + E6 (= `couts.total`). Annuels = A1 + … + A5.
- **Frais et impôt de la 1re année** = T + Entrée + Annuels. **Années suivantes, sans transaction** = T + Annuels.
- **Dividendes moins frais, 1re année** = N − Entrée − Annuels. **Années suivantes, sans transaction** = N − Annuels.
- Chaque montant est aussi donné en % du capital et en % de B.
- **Part supposée ou estimée** = (somme des lignes dont le statut n'est pas Fait) ÷ (frais et impôt de la 1re année), avec la règle du statut le plus faible : seules E3 et E4 sont des Faits tant qu'aucune grille ni aucun avis d'opéré n'est saisi. **Part des seuls frais** = (Entrée + Annuels − E3 − E4) ÷ (Entrée + Annuels) : c'est elle que l'écran affiche à côté des frais.
- **Levée par** (chaque franc non Fait est rangé dans une seule case, la somme redonne la part supposée au franc) : `grille` (E1, E2, A1 à A5 : la grille écrite les rend Faits) ; `execution` (E5, E6 : l'avis d'opéré les mesure) ; `taux_impot_non_verifie` (T des pays hors `irvm_verifies`) ; `dividendes_estimes` (T des pays vérifiés : devient Fait au paiement).
- **Par action possible** : somme des lignes par catégorie (aucune ; négociable ; selon le courtier ; à vérifier ; exécution).
- **Contrôle d'identité**, calculé et affiché : B − (frais et impôt) = dividendes moins frais, écart 0 FCFA.
- **Si les dividendes baissent** : pour chaque chute c de `chutes_dividendes` : N_c = `round_fcfa(N × (1 − c))` ; « dividendes moins frais » recalculé avec N_c.
- **Remise à niveau de janvier et sorties forcées** (ligne d'information, hors totaux) : taux d'un aller a = Entrée ÷ `couts.investi_apres` ; bas = 2 × 12 × `rotation_basse_mensuelle` × V × a ; haut = `remise_a_niveau_haute` × V. Libellé : « Estimation ; à mesurer pendant le suivi sur papier ».
- **Lignes fixes toujours présentes** : « Variations de cours : non comptées. » (`PH_COURS`) ; « Impôt sur les plus-values : non compté (0 supposé, non vérifié). » ; `PH_FRAIS`.
- **Aller-retour** : coût = 2 × Entrée ; en % de l'investi ; coût par an = aller-retour ÷ H pour H = 1, 3, 5. Sur chaque **vente** proposée par un ordre : « Cette vente coûterait X FCFA. Racheter plus tard le même montant coûterait Y FCFA. »
- **Ligne par ligne** : frais annuels de la ligne = `round_fcfa(garde × v_i)` + tenue par ligne ; dividende net attendu de la ligne ; rapport = frais ÷ dividende. Rouge si le rapport ≥ 100 % ; orange si ≥ 50 %.

**Leviers : deux tableaux séparés, plus les inconnues.** Chaque ligne est **recalculée** par `grille.comparer` ; rien n'est additionné à la main.

*Tableau A — « Frais évités par rapport au tarif supposé ; 0 si votre courtier ne facture pas ce poste. »*

| Geste | Une fois | Par an | Condition | Contrepartie |
|---|---:|---:|---|---|
| Courtier sans tenue de compte par ligne | 0 | 100 000 | si votre courtier facture 5 000 FCFA par ligne | changer de courtier ; courtage peut-être plus élevé ; transfert de 5 000 à 34 375 FCFA par ligne si des titres sont déjà détenus |
| Droits de garde à 0,10 % au lieu de 0,25 % | 0 | 14 475 | si le taux est obtenu par écrit | aucune connue |
| Courtage à 0,50 % au lieu de 0,80 % | 34 158 | sur chaque ordre futur | si le taux est obtenu par écrit | aucune connue ; le taux réel de départ est inconnu |
| **Ensemble, avec la grille connue sans frais par ligne (courtage 1,00 %, forfait 4 000)** | — | **73 224 de moins la 1re année, puis 96 000 de moins par an** | grille homologuée lue ; non confirmée pour vous | courtage plus élevé à l'entrée (+22 776) |
| Borne non attestée (0,50 % et aucun frais par ligne) | — | 130 158 puis 96 000 | aucune grille lue ne cumule ces avantages | — |

Équivalent annuel sur H ans = par an + une fois ÷ H (34 158 ÷ 3 = 11 386).

*Inconnues à lever (ni gestes, ni gains).* Taxe sur le courtage : de 0 à 13 896 FCFA à 10 M (6 175 de moins si elle est de 10 %). Minimum par ordre : +13 841 FCFA à 10 M et +50 822 à 1 M s'il est de 2 500 FCFA. Taxe sur les frais annuels : +22 343 FCFA par an si elle est de 18 %. Impôt sur les plus-values : non compté.

*Tableau B — « Argent placé en plus : gain ou perte selon le marché. »* (`PH_PLACE`)

| Changement | Francs placés en plus | Dividendes attendus sur ces francs [estimé] | Année ordinaire du passé (prudente à flatteuse) | Une année sur dix (flatteuse ; prudente ; périodes réelles) | Nature |
|---|---:|---:|---|---|---|
| Arrondi « plus forts restes » (F13c) | 65 485 | +2 960 par an | +4 350 à +7 700 | −6 500 ; −8 550 ; −12 700 | option, écart déclaré |
| Réinvestissement mensuel (F13d, règle corrigée) | 127 497 en moyenne | +5 760 par an à terme | +8 400 à +15 000 | −12 600 ; −16 700 ; −24 800 | option, essai E-D |

Calcul : francs × rendement net de l'investi (4,52 %) pour les dividendes ; francs × (médiane, une année sur dix) de chaque lecture de F6 à la graine 0 (prudente +6,6 %, flatteuse +11,8 % ; −9,9 %, −13,1 %, périodes réelles −19,45 %) pour le marché [Estimation ; 127 497 : `F/f8_reinvestir.py`]. Les deux lignes se recoupent : elles ne s'additionnent pas. Sur l'écran, ces montants suivent la règle 10.

**Sortie.** `rendement_net.bilan` et `rendement_net.leviers` (§4.5). Fonctions : `bilan.bilan_fuites(ordre, grille, horizon_ans) -> dict` ; `bilan.lignes_petites(ordre, grille) -> list` ; `bilan.aller_retour(ordre, horizon_ans) -> dict` ; `bilan.leviers(ordre, grille, lectures) -> dict`.

**Cas limites.** N = 0 : les rapports aux dividendes valent « sans objet ». Portefeuille détenu sans ordre : Entrée = 0. Ordre avec ventes : Entrée compte achats et ventes. Ligne bloquée ou hors bulletin : elle garde ses frais annuels. Grille sans frais par ligne : les lignes « tenue de compte » valent 0 et le geste correspondant affiche « sans objet : votre courtier ne facture pas ce poste ». Coûts dans le prix plafonnés par la limite : repris tels quels, avec la mention existante.

**Valeurs de contrôle au 20/11/2026, tarif supposé** [`S/s1_bilan.py`, `S/s5_reserve_leviers.py` ; parts recalculées par `F/f7_divers.py`].

| Capital | Frais et impôt, 1re année | Années suivantes | Dividendes moins frais, 1re année | Années suivantes | Part supposée ou estimée (facture ; frais seuls) | Dividendes −20 %, 1re année | Remise à niveau (bas à haut) | Aller-retour |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 000 000 | 120 531 (12,05 %) | 107 041 | −77 198 | −63 708 | 97,8 % ; 97,8 % | −84 890 | 3 252 à 12 300 | 26 980 |
| 10 000 000 | 340 241 (3,40 %) | 179 653 | +151 274 | +311 862 | 91,5 % ; 89,8 % | +64 076 | 34 745 à 123 000 | 321 176 (3,33 % de l'investi) |
| 50 000 000 | 1 390 456 (2,78 %) | 503 083 | +1 096 406 | +1 983 779 | 89,5 % ; 86,8 % | +655 249 | 189 831 à 615 000 | 1 774 746 |

Levée par, au franc : à 1 M, grille 110 344, exécution 2 714, taux d'impôt non vérifié 623, dividendes estimés 4 252 (somme 117 933) ; à 10 M, 215 226, 40 536, 7 081, 48 446 (somme 311 289) ; à 50 M, 682 702, 280 269, 35 807, 245 270 (somme 1 244 048) [Fait de calcul, `F/f7_divers.py`].

À 10 M, par action possible : aucune 84 479 ; négociable 101 330 ; selon le courtier 100 000 ; à vérifier 13 896 ; exécution 40 536 ; somme 340 241. Avec −7,5 % de dividendes : +118 575 la 1re année. Lignes à 10 M : rouge NTLC (frais 5 416, dividende 4 805) ; orange BICB, NSBC, BOABF, BOAS, CIEC, SPHC, ONTBF, TTLC. À 1 M : 18 lignes rouges, SNTS et ORAC orange. À 50 M : aucune.

**Intégration.** Section « Rendement net et pertes » de l'ordre, sous-partie « Du brut au net » (§7.3). Rapport : fin de la section `revenus`. Écran : tableau « Ce que vous recevriez et ce qui partirait ». Commande : `plan --format md` donne le détail.

**Tests** (`tests/test_rendement_bilan.py`).
1. Identité : somme des lignes = total, écart 0, à 1 M, 10 M, 50 M sur le panel réel et sur le panel de synthèse.
2. Valeurs du tableau de contrôle au franc près (estimations de la remise à niveau : à 1 FCFA près) ; parts à 0,1 point près ; la somme des quatre cases « levée par » égale la part supposée au franc.
3. N = 0 : aucune division par zéro.
4. Portefeuille détenu sans ordre : Entrée = 0.
5. Chaque ligne a un statut et une action possible.
6. La ligne « taxe sur le courtage » n'apparaît jamais dans le tableau A.
7. Les lignes du tableau B n'apparaissent jamais dans le tableau A ; aucun texte du tableau A ne contient un mot interdit.
8. Grille « FGI aux plafonds » : 211 490 puis 28 126 ; écart −73 224 puis −96 000.
9. Avec `tenue_par_ligne = 0` : le premier geste affiche « sans objet ».

**Critères d'acceptation.** Les totaux de la plate-forme sont retrouvés à 0 FCFA d'écart. Aucun montant vedette ne vient d'un tarif non attesté sans que ce soit écrit sur la même ligne.

**Gain attendu.** 0 FCFA directement. Il rend visible la facture et dit que 91,5 % repose sur des suppositions ou des estimations (89,8 % des seuls frais), et ce qui peut lever chacune. Les frais évités ne protègent pas d'une baisse des cours.

---

### F4 — Ce que j'accepte de risquer → montant en actions (P0)

**Objet.** L'utilisateur choisit ce qu'il accepte de risquer sur 12 mois, en FCFA, dans une table de quatre lignes (ou saisit un montant). La plate-forme répond : tant en actions, tant en réserve, la perte estimée d'une année comme 2018 de deux façons, ce qui se passerait si une baisse plus forte revenait, et le prix de cette prudence.

**Ce que la règle change.** Elle fixe le capital confié à la règle REF. La règle REF s'applique sans changement à ce capital. La réserve est un montant fixé par l'utilisateur ; l'outil ne la rééquilibre jamais.

**Calcul exact.**

1. **Ordre du capital total.** O_K = `recommend(asof, K, …)` dans le même mode que la commande (notes en mode direct, même grille). L'écran et l'ordre doivent porter les mêmes lignes.
2. **Chocs par franc investi**, lus dans O_K (`stress`), I_K = `couts.investi_apres` :
   - `s_beta` = |perte ST2, variante TR| ÷ I_K (0,23975) : le marché de 2018 multiplié par la sensibilité du panier [Estimation] ;
   - `s_ref` = `perte.choc_ref_publie(validation_dir, panels)` = **0,2932** : ce que la règle a subi en 2018 dans son test publié, par franc investi, hors frais [Estimation : lecture d'un résultat publié, pas un test]. Méthode, en lecture seule de `reports/validation_S1/trades.parquet` et `nav.parquet` (série `REF_central_10M`) et de `adjusted_prices` (`adj_close`, `tr_index`) : positions = cumul par titre de la colonne `qty` des ordres publiés (unités ajustées des divisions) ; pour chaque séance d de 2018 (de la dernière séance de 2017 à la dernière de 2018), poids de la veille `w_{i,d−1}` = titres × `adj_close` ÷ valeur des titres ; rendement de la partie investie `r_d = Σ w_{i,d−1} × r^TR_{i,d}` ; `s_ref = |Π(1 + r_d) − 1|`. Contrôles publiés : VL de REF en 2018 −25,74 % ; part investie moyenne reconstituée 82,5 % (la même méthode redonne les 82,0 % publiés sur S1) ; frais de transaction de 2018 61 077 FCFA (0,65 % de la VL). Méthodes approchées, pour la fourchette seulement : (|perte VL| − frais de transaction) ÷ part investie = 0,304 ; (|perte VL| − frais de transaction, garde et tenue estimées) ÷ part investie = 0,290 [`F/f1_sref.py`]. Fichiers publiés illisibles : valeur de repli 0,2932 du fichier de réglages, mention « choc de repli » ;
   - `s_dim` = max(`s_beta` ; `s_ref`) = 0,2932 : **le choc qui dimensionne** ;
   - `s_cours` = |perte ST2, variante intra-annuel| ÷ I_K (0,31521) : le pire moment de 2018 ;
   - `s_long` = |perte ST1, variante TR| ÷ I_K (0,44607) : la baisse de mars 2017 à octobre 2020.
3. **Poche A** (fonction `perte.poche(ordre, A, costs, grille)`) : pour chaque ligne cible, `q_i(A) = ⌊w_i × A ÷ p_i + 1e-9⌋` ; tranches `participation_schedule(q_i, p_i, mdv63_i, 0,10)` ; coûts `order_costs(q_i, p_i, costs, side="achat", half_spread=demi_spread_pct_i, mdv63=mdv63_i, tranches=…, limit=L_i)`.
   - investi I(A) = Σ `brut` ; frais d'achat e(A) = Σ `total` ; lignes n(A) = nombre de `q_i > 0` ;
   - frais annuels a(A) = `round_fcfa(garde × I(A))` + `round_fcfa(tenue_par_ligne × n(A))` + forfait + frais hors modèle ;
   - provision du pire cas pc(A) = Σ `_worst_case(tranches, L_i, costs, "achat")` ;
   - dividendes nets attendus d(A) = Σ `round_fcfa(q_i(A) × dividende net prévu par titre)`.
   Fait vérifié : cette arithmétique redonne les ordres exacts de la plate-forme (investi, frais, dividendes, pire cas) pour les poches de 1,4 M, 3,0 M et 6,3 M (`F/f2b_ordres.py`), de 1,5 M, 3,5 M et 7 M, et pour 14 poches dans `M/designs/pertes_travail/p0_poches.py`.
4. **Perte estimée d'une année comme 2018**, frais de la 1re année compris : `P(A) = s_dim × I(A) + e(A) + a(A)`. **Les intérêts de la réserve n'y entrent jamais** : un taux saisi sans preuve ferait presque tripler la somme exposée (§12), et ces intérêts ne sont pas acquis au moment d'une baisse. Ils sont montrés à part, dans la décision 3 (F5).
5. **Montant en actions.** A* = le plus grand A de {pas, 2 × pas, …, K} (pas = 100 000 FCFA) tel que : P(A) ≤ X ; n(A) = nombre de lignes cibles de O_K ; pc(A) ≤ A. S'il n'en existe aucun : A* = 0.
6. **Vérification par l'ordre complet** (seulement quand X est choisi) : O_A = `recommend(asof, A*, …, rendement=False)` avec les arguments de `appel` (§4.3), sans récursion ; `P_vérifiée = max(s_ref × investi de O_A ; |ST2 TR de O_A|) + frais d'achat + frais annuels de O_A`. Boucle : tant que `P_vérifiée > X` et `A* > 0`, A* ← A* − pas et nouvel ordre, **10 appels au plus**. Si la boucle s'arrête au plafond, A* = dernière valeur vérifiée sous X, ou 0, et le message « vérification arrêtée après 10 ordres : montant en actions à confirmer » s'affiche. L'ordre à afficher est le dernier O_A vérifié ; `choix.appels` donne le nombre d'appels.
7. **Ce qui est affiché pour chaque ligne** (écran : arrondi de la règle 10 ; détail : au franc) :
   - « Année comme 2018 » : fourchette [`s_beta_A × I + e + a` ; `s_ref × I + e + a`], où `s_beta_A` vient de l'ordre de la poche quand il existe, sinon de O_K ;
   - « Pire moment de 2018 » : `s_cours × I + e + a`, suivi de « (dépasse) » si ce montant exact dépasse X ;
   - « Si la baisse de 2017-2020 revenait » : `s_long × I + e + a`, suivi de « (dépasse) » si ce montant exact dépasse X ; quand les deux dépassent : « (les deux dépassent) » ;
   - rapport `(s_long × I + e + a) ÷ (s_ref × I + e + a)`, au détail seulement (1,39 à 1,47 au 20/11/2026) ; aucune phrase générale du type « au moins une fois et demie » ;
   - « Dividendes moins frais » la 1re année : d − e − a ; années suivantes : d − a ; mention « frais > dividendes » si d − a < 0, « la 1re année, les frais dépassent les dividendes » si d − e − a < 0 ≤ d − a ;
   - « Année ordinaire du passé » : sur l'écran, **lecture prudente seulement** (marché chargé des mêmes frais, F6, blocs de 8 semaines, graine 0), résultat médian de la poche en FCFA ; au détail, les deux lectures, la flatteuse suivie de `PH_FLATTE` ;
   - **Prix de cette prudence** = année ordinaire prudente de « tout en actions » − celle de la ligne (lecture prudente seulement) ;
   - « Un titre en moins » : 0,30 × valeur de la plus grosse ligne de la poche.
8. **Table de choix** (quand X n'est pas saisi) : une ligne pour chaque part de `perte.choix_parts` (X = part × K), plus la ligne « tout » (tout en actions, sans X).

**Paramètres.** `perte.pas_fcfa` 100 000 ; `perte.choc_2018_ref_publie` 0,2932 (repli seulement) [Estimation] ; `perte.choix_parts` [0,05 ; 0,10 ; 0,20] ; horizon fixé à 12 mois.

**Sortie.** `rendement_net.perte` (§4.5). Fonctions : `perte.choc_ref_publie(validation_dir, panels) -> dict` (`{"valeur", "source", "vl_2018", "part_investie_2018", "frais_2018"}`) ; `perte.chocs(ordre, choc_ref) -> dict` ; `perte.poche(ordre, A, costs, grille) -> dict` ; `perte.montant_actions(ordre, X, costs, grille, chocs) -> dict` ; `perte.table_de_choix(ordre, costs, grille, chocs, lectures) -> list` ; `perte.verifier_par_ordre(A, X, chocs, appel) -> dict`.

**Valeurs de contrôle au 20/11/2026, K = 10 000 000** [`F/f2_poches.py` ; ordres exacts `F/reco/reco_1400000.json`, `reco_3000000.json`, `reco_6300000.json`, contrôlés par `F/f2b_ordres.py`].

*Tarif supposé (central). Table de choix : formule de l'étape 4, chocs lus dans l'ordre de K, s_ref = 0,2932.*

| X | A* | Réserve | Investi | Frais 1re année (achat + annuels) | Année comme 2018 (bas ; haut) | Pire moment de 2018 | Baisse 2017-2020 | Rapport 2017-2020 ÷ haut | Dividendes moins frais, 1re année ; ensuite | Année ordinaire (prudente ; flatteuse) |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|
| 500 000 | 1 400 000 | 8 600 000 | 1 204 610 | 121 727 (18 715 + 103 012) | 410 532 ; 474 919 | 501 430 (dépasse) | 659 065 (dépasse) | 1,39 | −67 825 ; −49 110 | −10 489 ; +46 172 |
| 1 000 000 | 3 000 000 | 7 000 000 | 2 807 310 | 151 702 (44 684 + 107 018) | 824 753 ; 974 805 | 1 036 590 (dépasse) | 1 403 953 (dépasse) | 1,44 | −25 707 ; +18 977 | +118 001 ; +263 350 |
| 2 000 000 | 6 300 000 | 3 700 000 | 6 009 445 | 212 863 (97 839 + 115 024) | 1 653 624 ; 1 974 832 | 2 107 091 (dépasse) | 2 893 483 (dépasse) | 1,47 | +59 016 ; +156 855 | +374 746 ; +690 914 |
| tout | 10 000 000 | 0 | 9 650 560 | 284 714 (160 588 + 124 126) | 2 598 431 ; 3 114 258 | 3 326 652 | 4 589 518 | 1,47 | +151 274 ; +311 862 | +664 187 ; +1 179 300 |

Contrôle de la règle : pour chaque X, P(A*) ≤ X et P(A* + pas) > X (474 919 et 512 908 ; 974 805 et 1 010 753 ; 1 974 832 et 2 004 461). Avec le choc mesuré, les poches de l'ancienne version (1 500 000 ; 3 200 000 ; 6 600 000) donnaient 512 908, 1 041 526 et 2 059 495 FCFA : plus que le montant accepté.

*Après le choix : valeurs de l'ordre exact de la poche (étape 6), qui remplacent celles de la formule.* Les quantités des trois ordres exacts sont identiques à celles de l'arithmétique.

| A* | Investi | Frais 1re année | Stress 2018 de l'ordre + frais | 0,2932 × investi + frais = P_vérifiée | Pire moment de 2018 + frais | Baisse 2017-2020 + frais | Dividendes nets attendus |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 400 000 | 1 204 610 | 121 727 | 414 934 | 474 919 | 507 219 | 667 256 | 53 902 |
| 3 000 000 | 2 807 310 | 151 702 | 827 267 | 974 805 | 1 039 895 | 1 408 629 | 125 995 |
| 6 300 000 | 6 009 445 | 212 863 | 1 654 403 | 1 974 832 | 2 108 114 | 2 894 931 | 271 879 |

Prix de la prudence pour X = 1 000 000 (lecture prudente) : 546 187 FCFA de résultat d'une année ordinaire en moins (écran : « environ 550 000 ») ; au détail, lecture flatteuse : 915 950. Un titre en moins (Sonatel −30 %) : 227 856 FCFA pour 3 000 000 en actions ; 762 348 FCFA tout en actions.

*Grille connue sans frais par ligne (FGI aux plafonds).* X = 500 000 → 1 700 000 ; X = 1 000 000 → **3 400 000** (frais de la 1re année 69 611 ; dividendes moins frais +72 345 puis +130 064 ; année comme 2018 : 826 420 à 995 145) ; X = 2 000 000 → 6 600 000.

*Sensibilité au choc (tarif supposé)* [`F/f2_poches.py`]. s_ref = 0,290 : 1 400 000 ; 3 000 000 ; 6 400 000. s_ref = 0,304 : 1 400 000 ; 2 900 000 ; 6 100 000. L'ancienne valeur 0,278 : 1 500 000 ; 3 200 000 ; 6 600 000.

*Autres repères.* Capital minimal pour un titre de chaque ligne : 964 573 FCFA (fixé par Solibra). Première poche, au pas de 100 000, dont les dividendes attendus couvrent les frais annuels au tarif supposé : 2 600 000 FCFA (108 522 pour 106 030).

**Textes affichés quand X est choisi (exemple : 1 000 000 FCFA, tarif supposé ; forme écran).**

> Vous acceptez de risquer **1 000 000 FCFA** sur 12 mois. Ce n'est pas une limite.
> - En actions : **3 000 000 FCFA**. En réserve : **7 000 000 FCFA**.
> - Une année comme 2018 : environ **−830 000 à −980 000 FCFA**, frais compris [estimé]. Au pire moment de l'année : environ −1 040 000 FCFA. Cela dépasse ce que vous acceptez.
> - Si la baisse de 2017-2020 revenait : environ **−1 410 000 FCFA**, sur plusieurs années. Cela dépasse ce que vous acceptez.
> - Prix de cette prudence : dans une année ordinaire du passé, lecture prudente, environ +110 000 FCFA au lieu de +660 000 (environ 550 000 FCFA de moins).
> - Au tarif supposé, la 1re année, les frais dépassent les dividendes attendus d'environ 26 000 FCFA. Voir « ce que prend mon courtier ».
> - Un tarif plus bas permet plus d'actions pour le même risque accepté : la somme exposée au marché augmente aussi.
> - Ce que vous acceptez de risquer ne se recharge pas chaque année. Après une perte, relisez ce choix.
> - `PH_PASSE` ; `PH_DESCRIPTIF` ; `PH_RISQUE` ; `PH_INTERETS` ; `BANNER`.

**Cas limites.**
1. X non saisi : table de choix ; rien n'est choisi à la place de l'utilisateur ; l'ordre affiché reste celui de K.
2. Aucune poche possible (X inférieur à P de la plus petite poche à lignes complètes) : A* = 0 ; « À ce tarif, la plus petite poche de 20 lignes risque plus que ce que vous acceptez. »
3. X ≥ P(K) : tout en actions ; rappel `PH_RISQUE`.
4. Titres déjà détenus pour plus que A* : l'écart est affiché ; **aucune vente n'est proposée**.
5. Taux de la réserve saisi : A* et P(A) ne changent pas ; les intérêts sont affichés dans la décision 3 seulement (F5).
6. Stress ST2 ou ST1 absent de l'ordre : `s_beta` et `s_long` valent « non calculé » ; `s_dim` = `s_ref`.
6 bis. Fichiers S1 publiés absents ou illisibles : `s_ref` = valeur de repli, `chocs.ref_publie_source` = « repli », mention sur la ligne.
7. Poche où la provision réduit des quantités (tarif cher) : l'ordre exact de l'étape 6 fait foi, avec la mention « quantités réduites par la provision ».
8. Capital supérieur à 10 M : le plancher de liquidité du modèle dépend du capital ; l'ordre exact fait foi.

**Intégration.** Options `--perte-toleree MONTANT|P%` sur `plan`, `recommend`, `report`. Avec cette option, `recommend` produit l'ordre de la poche et l'en-tête de l'ordre devient : « Capital total 10 000 000 FCFA ; en actions 3 000 000 FCFA ; en réserve 7 000 000 FCFA. » Interface : la table de choix est cliquable sur la carte « Mon plan » ; champ « Ce que j'accepte de risquer sur 12 mois (FCFA) » sur la page Portefeuille. Ordre : sous-partie « Ce que j'accepte de risquer ». Rapport : sous-bloc à la fin de la section `risques`. JSON : `rendement_net.perte`.

**Tests** (`tests/test_rendement_perte.py`).
1. Poche de K = ordre de K au franc : investi 9 650 560, frais 160 588, garde 24 126, tenue 100 000, pire cas 9 866 731.
2. Poches de 1 400 000, 3 000 000, 6 300 000 (et 1 500 000, 3 500 000, 7 000 000) : quantités, investi, frais, dividendes et pire cas égaux aux ordres exacts.
3. Recette : les quatre lignes du tableau de contrôle (A*, investi, frais au franc ; estimations à 1 000 FCFA près).
4. Monotonie : A* ne baisse jamais quand X monte ; A* et P(A) ne dépendent pas du taux de la réserve.
5. Nom du test de cohérence : `test_estimation_2018_sous_le_montant_choisi` (pour tout X de 100 000 à 3 000 000 sur le panel de synthèse, `P_vérifiée ≤ X`, ou A* = 0 avec le message d'arrêt). Le mot « garantie » n'apparaît ni dans le nom ni dans le message. La boucle de l'étape 6 ne fait jamais plus de 10 appels et ne rappelle jamais `rendement.construire` (compteur d'appels).
6. Pour chaque ligne de la table, le texte contient en FCFA « pire moment de 2018 » et « si 2017-2020 revenait », et « dépasse » exactement quand le montant exact dépasse X ; aucune phrase « une fois et demie ».
7. Le bloc « Ce que j'accepte de risquer », phrases fixes retirées, ne contient ni « plafond », ni « perte maximale », ni « au plus », ni « sous la perte acceptée » (comptés comme au §1.1).
8. Sans `--perte-toleree`, l'ordre est identique à aujourd'hui (quantités, prix, frais).
9. Avec la grille « FGI aux plafonds » : X = 1 000 000 → 3 400 000.
10. `perte.choc_ref_publie` sur les fichiers publiés : 0,2932 ± 0,0005 ; sur un dossier vide : valeur de repli et `source = "repli"` ; la fonction n'ouvre aucun fichier en écriture et ne simule rien.
11. La lecture flatteuse n'entre ni dans le prix de la prudence ni dans une forme écran.

**Critères d'acceptation.** L'utilisateur peut choisir sans saisir un chiffre. Chaque choix montre la perte (avec ses dépassements) et le gain d'une année ordinaire prudente côte à côte, en FCFA. Aucun texte ne laisse croire à une limite.

**Statut des chiffres.** Quantités, investi, frais : calcul exact sur tarif supposé. Chocs, fourchettes, année ordinaire : Estimation (un seul passé ; stress linéaire ; le choc 0,2932 est une lecture d'un résultat publié, sensible à la méthode : 0,290 à 0,304). **Gain attendu.** Aucun gain. Une maîtrise de la taille de la perte, au prix d'un résultat ordinaire plus petit. La fréquence des pertes ne baisse pas ; elle monte pour une petite poche à cause des frais fixes (41,6 % à 51,8 % pour 1 400 000 FCFA, contre 25,6 % à 34,1 % tout en actions, graine 0) [Estimation, `F/f2_poches.py`].

---

### F5 — Où dort le reste, et à quel taux (P0)

**Objet.** La somme qui n'est pas en actions est la plus grosse somme du plan. Pendant l'étude, c'est tout le capital. L'utilisateur saisit le taux net qu'il obtient ; l'écran montre ce que cela change.

**Calcul.**
- Réserve = K − A* (K entier tant qu'aucun achat n'est fait).
- Valeur d'un point de taux = réserve × 0,01 par an. Intérêts attendus = r × réserve.
- **r n'entre jamais dans la formule P(A) de F4**, ni dans A*. r vide est compté à 0, avec la mention « taux inconnu ».
- Tout chiffre qui dépend de r > 0 est « supposé » tant que le champ `statut` du taux n'est pas `relevé`, et porte `PH_RESERVE`. Même relevé, il reste à part : `PH_INTERETS`.

**Entrées enregistrées** (`plan.json`) : `taux_reserve` (part par an, vide par défaut, 0 à 0,15 accepté), `support_reserve` (texte), `statut_taux` (`supposé` / `relevé`), `date_taux`.

**Valeurs de contrôle** (K = 10 M, tarif supposé) [`F/f2_poches.py`]. Pendant l'étude : 100 000 FCFA par an et par point. Avec 3 000 000 FCFA en actions : 70 000 FCFA par an et par point. Avec r = 3 % [Hypothèse] et 3 000 000 en actions : intérêts attendus 210 000 FCFA par an, affichés à part ; A* reste 3 000 000.

**Textes.** « Où dort l'argent qui n'est pas en actions, et à quel taux ? » ; « Chaque point d'intérêt vaut 70 000 FCFA par an sur votre réserve. C'est du même ordre que la tenue de compte. » ; `PH_RESERVE` ; `PH_INTERETS`.

**Cas limites.** r saisi au-delà de 15 % : refusé. Réserve nulle : bloc masqué. La plate-forme ne conseille aucun placement et ne connaît aucun taux.

**Intégration.** Option `--taux-reserve` sur `plan`, `recommend`, `report`. Champ sur la carte « Mon plan ». JSON : `rendement_net.reserve` (`deduit_de_la_perte` vaut toujours `false`). Fonction : `perte.reserve(K, A, r, statut) -> dict`.

**Tests.** r vide, 0, 3 % ou 15 % : A*, P(A) et la table de F4 identiques au franc. Étiquette « supposé » et `PH_RESERVE` dès que r > 0 sans relevé ; `PH_INTERETS` toujours présent. 70 000 et 100 000 FCFA par point.

**Gain attendu.** 30 000 FCFA par an et par million de réserve à 3 % [Hypothèse]. Rien tant que le taux réel n'est pas connu.

---

### F6 — Lectures du risque (P0)

**Objet.** L'ordre ne dit plus seulement « 25,6 % de chances de perte ». Il montre plusieurs lectures du même passé, leur fourchette, et dit qu'il s'agit d'un seul passé.

**Calcul.** Pour l'ordre affiché, avec les fonctions existantes `weekly_tr_returns`, `stationary_bootstrap_indices`, `return_distribution` (5 000 tirages, même fenêtre) :

1. **Passé rejoué** (lecture existante, flatteuse ; toujours suivie de `PH_FLATTE`) : blocs moyens de 8 semaines. Ajouts : la fréquence sous le seuil de 5 % (« une année sur vingt ») et le pire tirage.
2. **Sensibilité aux blocs** : le même calcul avec des blocs moyens de 26 et de 52 semaines.
3. **Marché chargé des mêmes frais** (lecture prudente) : mêmes indices de tirage ; rendement hebdomadaire = `investi_pct` × rendement du Composite TR ; mêmes frais déduits (`frais_deduits`) ; blocs de 8, 26 et 52 semaines.
   **Graines.** Chaque lecture bootstrap (1 à 3) est calculée pour les graines 0 à 19 (`risque.graines`). L'affichage et la phrase de synthèse prennent la **médiane des 20 graines** ; le JSON garde aussi la graine 0 (recette, reproductible) et le minimum et le maximum des 20. La lecture 1 à la graine 0 reste identique à la distribution existante de l'ordre. Durée mesurée : moins d'une seconde pour 20 graines × 6 lectures (`F/f4_graines.py`).
4. **Périodes réellement observées** : série quotidienne du panier d'aujourd'hui (indices TR des lignes aux poids réalisés). **Règle de renormalisation de `return_distribution`** : une ligne compte à partir de son **premier rendement** (le lendemain de sa première cote) ; 0 % les jours sans cours après cotation ; poids renormalisés sur les lignes qui comptent. Dernière séance de chaque mois m_0 … m_n ; pour chaque i : `m_{i+12} ÷ m_i × (1 − frais_deduits) − 1`. Sorties : nombre de périodes, nombre en perte, niveau dépassé neuf fois sur dix, pire période, répartition des périodes en perte par année de départ. Le décompte est au bord du zéro (la période qui part de fin mars 2022 vaut −0,10 % avec cette règle, +0,07 % si la ligne compte dès le jour de sa première cote) : la recette accepte ±1 période.
5. **Phrase de synthèse** : `PH_PASSE`, `PH_DESCRIPTIF`, puis « Selon la façon de compter et le tirage, environ {min} % à {max} % des périodes de 12 mois ont fini en perte, et une année sur dix a fini sous {haut} % à {bas} %. » Les bornes sont le minimum et le maximum des lectures 1 à 4 (médianes des 20 graines pour 1 à 3), arrondies au point entier.
6. **Concentration** : pour les deux premières lignes et toute ligne de plus de 5 % : perte d'un choc de `risque.choc_titre` (30 %) = 0,30 × `valeur_apres`, en FCFA, en % du capital total et en part de X ; poids cumulé des deux premières lignes ; lignes effectives = 1 ÷ Σ (v_i ÷ investi)².
7. **Libellé réécrit.** Dans la table de la distribution, « P(battre le TR) » devient : « Fréquence passée au-dessus du marché, aux poids d'aujourd'hui (flatteuse : le test S1 a donné −5,6 points par an) ». La clé JSON `p_battre_tr` ne change pas.

**Valeurs de contrôle au 20/11/2026, 10 M, tout en actions** [`F/f4_graines.py` (5 000 tirages par graine, graines 0 à 19) ; `F/f3_periodes.py` ; pires tirages : `S/s3_blocs.py`]. Chaque case donne « graine 0 ; médiane des 20 graines ».

| Lecture | Périodes en perte | Année ordinaire | Une année sur dix | Une année sur vingt | Pire (graine 0) |
|---|---:|---:|---:|---:|---:|
| Passé rejoué, blocs de 8 semaines | 25,6 % ; 25,5 % | +11,8 % ; +11,8 % | −9,9 % ; −9,9 % | −15,0 % ; −15,4 % | −39,1 % |
| Passé rejoué, blocs de 26 semaines | 30,0 % ; 30,6 % | +13,0 % ; +12,6 % | −14,8 % ; −14,8 % | −22,1 % ; −21,8 % | −42,2 % |
| Passé rejoué, blocs de 52 semaines | 31,8 % ; 32,8 % | +16,0 % ; +13,7 % | −16,4 % ; −16,6 % | −24,6 % ; −24,9 % | −44,1 % |
| Marché chargé des mêmes frais, blocs de 8 | 34,1 % ; 34,6 % | +6,6 % ; +6,4 % | −13,1 % ; −13,1 % | −17,5 % ; −17,9 % | — |
| Marché chargé des mêmes frais, blocs de 26 | 37,6 % ; 38,2 % | +7,4 % ; +6,9 % | −17,1 % ; −17,3 % | −22,9 % ; −22,9 % | — |
| Marché chargé des mêmes frais, blocs de 52 | 38,1 % ; 39,6 % | +9,1 % ; +7,3 % | −19,0 % ; −19,3 % | −24,4 % ; −24,5 % | — |
| Périodes réellement observées | 37 sur 107 (34,6 %) | — | −19,45 % | — | −26,7 % (départ fin mars 2018) |

Écart dû au seul tirage (min à max des 20 graines) : jusqu'à 2,8 points pour la fréquence de perte (marché chargé, blocs de 52 : 38,1 % à 40,9 %) [`F/f4_graines.py`]. Synthèse attendue : « environ 26 % à 40 % » et « −10 % à −19 % ». Périodes en perte par année de départ : 2017 12 sur 12 ; 2018 12 sur 12 ; 2019 10 sur 12 ; 2020 1 ; 2022 2 ; aucune ensuite. Concentration : Sonatel + Orange CI = 43,5 % de la valeur ; Sonatel −30 % = 762 348 FCFA ; 7,9 lignes effectives.

**Cas limites.** Moins de 24 mois d'historique : pas de périodes réelles. Distribution indisponible (`disponible` faux) : seul le bloc de concentration s'affiche. Ligne récente : règle de renormalisation de `return_distribution` (point 4).

**Intégration.** `rendement/risque.py` : `lectures(ordre, panels, …) -> dict` ; `periodes_reelles(...)` ; `concentration(ordre, X) -> list`. Ordre : lignes ajoutées sous la table de la section « Distribution historique », et phrase de synthèse. Rapport : tuiles à la fin de la section `distribution` (après le texte existant « Rendement net à 12 mois ») ; concentration à la fin de la section `risques`. JSON : `rendement_net.risque`.

**Tests** (`tests/test_rendement_risque.py`). Lecture 1 à la graine 0 identique à `distribution` de l'ordre (médiane, une année sur dix, fréquence de perte). Valeurs du tableau à 0,1 point près (recette ; graine 0 et médiane des 20). Périodes réelles : 37 ± 1 sur 107 ; une année sur dix −19,45 % ± 0,1 point ; « 2022 : 2 » ± 1. Sur un panel de synthèse avec une ligne cotée en cours de route : la ligne compte à partir de son premier rendement. Les lectures, `PH_PASSE` et `PH_DESCRIPTIF` sont présentes dans le Markdown, le JSON et le HTML. Somme des poids de concentration cohérente. Le libellé « P(battre le TR) » n'apparaît plus seul dans le Markdown. La clé `p_battre_tr` existe toujours.

**Statut.** Estimation descriptive : un seul passé de 9,9 ans, une seule grande baisse ; les lectures viennent du même historique, leur écart n'est pas une marge d'erreur. **Gain attendu.** Aucun en FCFA. Corrige une fréquence de perte trop favorable de jusqu'à 14 points (25,6 % contre 39,6 %) et un « une année sur dix » trop favorable de jusqu'à 10 points (−9,9 % contre −19,45 %).

---

### F7 — Argent qui dort, provision d'entrée, « passer l'ordre » (P0)

**Objet.** Dire combien d'argent ne travaille pas, pourquoi, et jusqu'à quand. Dire la provision à avoir sur le compte avant l'ordre. Dire comment passer un ordre à cours limité à la BRVM.

**Calcul.**

*(a) Décomposition à l'ordre.* `liquidités après` = `liquidités initiales − achats nets + ventes nettes`. Pour un premier achat : `liquidités après = (V − cible investie) + reliquat d'arrondi − frais d'achat`. À 10 M : 200 000 + 149 440 − 160 588 = 188 852 FCFA.

*(b) Argent qui dort au-delà de la réserve de la règle.* `D = liquidités après les ordres proposés − cash_buffer × V` (réserve de 2 % de la spécification ; V au sens du §5, liquidités réelles). Chaque franc de D est rangé dans une cause, en FCFA quand elle est connue :
- **prévu par la règle testée** : dividendes reçus depuis la dernière remise à niveau de janvier et produit des sorties forcées, gardés jusqu'à la remise à niveau suivante (§7.1.6, D8) ; reliquat d'arrondi vers le bas de l'ordre en cours ;
- **non prévu** : ordres non servis ou servis en partie (titres de l'ordre d'origine non détenus, lus dans le carnet ou dans `memoire`) ; reliquat d'arrondi au-delà de la marge de F13c ; cause inconnue (reste).
`D_prevu` = somme des causes prévues ; `D_hors_regle = D − D_prevu`. Sans carnet, les dividendes reçus sont estimés à partir de `dividends.parquet` (paiements entre la dernière décision de janvier et la date de l'ordre, titres détenus aujourd'hui) et portent « estimé ». Phrase type avec un portefeuille détenu : « Liquidités 624 840 FCFA (6,1 %). Aucun ordre proposé : la règle n'achète pas hors de la remise à niveau de janvier, et la bande de 2 points gèle chaque ligne. Cet argent est prévu par la règle testée (dividendes gardés jusqu'à fin janvier). »

*(c) Réserve de fonctionnement (information, pas une règle).* `R_n = round_fcfa(n × (frais annuels) ÷ 4)` pour n = 2 et n = 3 (demi vers le haut). À 10 M : 62 063 et 93 095 FCFA (93 094,5 arrondi) ; à 1 M : 51 083 et 76 625 ; à 50 M : 111 003 et 166 505 [Fait de calcul, `F/f7_divers.py`].

*(d) Projection à cours constants* (compte des francs ; ne prévoit rien). Jour par jour, du premier jour d'exécution au dernier jour ouvré de janvier de l'année N+2 :
- départ : `liquidités après` ;
- à chaque date de paiement prévue (`dividendes.date_paiement_prevue`) : + `round_fcfa(titres × dividende net prévu par titre)` ;
- à chaque fin de trimestre civil : − `(garde × investi + tenue par ligne × lignes + forfait) × jours écoulés depuis le dernier prélèvement ÷ 365` (premier prélèvement compté depuis le premier jour d'exécution) ;
- sorties : liquidités en fin de mois ; moyenne sur les jours civils du 1er février N+1 à la veille de la remise à niveau suivante ; pointe ; montant à la remise à niveau.
Cette projection suit la règle testée (dividendes gardés jusqu'à janvier). Elle sert de **référence au feu « Fuites »** (F11).

*(e) Provision d'entrée et part investie maximale.* ρ = Σ q_i × L_i ÷ Σ q_i × p_i (1,00984 à 10 M). τ = `costs.rate()` = courtage × (1 + taxe) + BRVM + DC/BR (1,244 % au tarif supposé). **Part investie maximale = 1 ÷ (ρ × (1 + τ)).** Affichage : provision du pire cas (`couts.achats_pire_cas`), marge = liquidités − provision, et la même marge recalculée avec un courtage plus cher de `surcout_courtage_test` (0,2 point).

*(f) Arrondi possible (information).* Résultat de l'algorithme de F13c **sans l'appliquer** : « Avec l'arrondi "plus forts restes" : +65 485 FCFA placés (97,16 % au lieu de 96,51 %), marge du pire cas 66 323 FCFA. Option `--arrondi restes`, écart à la règle testée. »

*(g) « Passer l'ordre »* (texte fixe, sources : recherche 01, [Fait]) :
1. « Vos ordres sont à cours limité. Certaines lignes peuvent ne pas être servies le jour même, ou seulement en partie. »
2. « Horaires (heure d'Abidjan) : saisie avant l'ouverture de 9 h 00 à 9 h 45 ; cotation en continu jusqu'à 14 h 00 ; fixing de clôture à 14 h 30 ; négociation au dernier cours jusqu'à 15 h 00. »
3. « Demandez une validité de plusieurs séances (10 au plus). La plate-forme réévalue ensuite. »
4. « Le jour d'un détachement de dividende ou d'une division, la BRVM annule les ordres en attente : il faut les ressaisir. »
5. « Le produit d'une vente n'est disponible que deux jours de bourse plus tard. »
6. « Après quelques séances, relancez la commande avec ce que vous détenez vraiment. »
7. Si le carnet de clôture est dans le panel (`order_book` : `ask`, `ask_qty`) : « Au dernier carnet, {n1} lignes ont un prix demandé au-dessus de votre limite et {n2} n'offrent pas assez de titres au meilleur prix. » Au 20/11/2026 à 10 M : 5 et 5 [Fait, `M/frais/04_limites.py`].

**Valeurs de contrôle** [`M/liquidites/`, `S/s1_bilan.py`, `S/s5_reserve_leviers.py`].

| Grandeur | 1 M | 10 M | 50 M |
|---|---:|---:|---:|
| Liquidités après l'achat | 120 250 | 188 852 | 310 387 |
| dont reliquat d'arrondi | 113 740 | 149 440 | 197 760 |
| Provision du pire cas | 885 665 | 9 866 731 | 49 895 388 |
| Marge | 114 335 | 133 269 | 104 612 |
| Marge avec un courtage plus cher de 0,2 point | 112 267 | 110 269 | négative (il manquerait 11 697) |
| Arrondi possible (marge de 2 trimestres) | +61 025 | +65 485 | 0 |

Part investie maximale : 98,19 % (optimiste), **97,81 %** (central), 97,58 % (stress), 97,02 % (sévère). Projection à 10 M : dividendes 435 988 FCFA en 20 paiements du 03/05 au 23/09/2027 (mai 176 222 ; juin 82 179 ; juillet 109 374 ; août 62 762 ; septembre 5 451) ; 183 259 FCFA en moyenne du 23/11/2026 au 28/01/2027 ; 388 420 FCFA en moyenne de février 2027 à janvier 2028 ; pointe 550 364 ; 487 791 au 31/01/2028 [Estimation]. Portefeuille détenu + 624 840 FCFA : D = 419 332 FCFA, aucun ordre proposé [Fait, `M/liquidites/reco/reco_detenu_plus_dividendes.json` : 624 840 − 2 % × 10 275 400].

**Sortie.** `rendement_net.liquidites`, `rendement_net.passer_l_ordre`. Fonctions : `liquidites.decomposition(ordre)` ; `liquidites.argent_qui_dort(ordre, carnet=None)` ; `liquidites.reserve_fonctionnement(ordre, grille, n)` ; `liquidites.projection(ordre, grille) -> dict` ; `liquidites.provision_entree(ordre, costs) -> dict` ; `liquidites.consignes(ordre, panels) -> list[str]`.

**Cas limites.** Date de prélèvement des frais inconnue : hypothèse « fin de trimestre civil », écrite. Ordre sur plusieurs séances : provision par tranche (valeurs existantes). Grille `supposé` : « provision calculée sur un tarif supposé ». Panel sans `order_book` : la consigne 7 est omise.

**Intégration.** Sous-partie « Argent qui dort et provision » de la section de l'ordre ; une ligne dans la section « Exécution » : « Provision à avoir avant l'ordre : 9 866 731 FCFA. Part investie maximale à ce tarif : 97,81 % (la cible de 98 % n'est pas atteignable). » Rapport : fin de la section `ordre`, avec un graphique des liquidités par mois (`bar_chart` existant).

**Tests** (`tests/test_rendement_liquidites.py`). Identité de décomposition à 0 FCFA, à 1 M, 10 M, 50 M. Quatre parts maximales à 0,01 point près. Somme des dividendes de la projection = 435 988. Moyenne de février à janvier = 388 420 à 1 000 FCFA près (recette). Portefeuille détenu + 624 840 FCFA : phrase et montant présents. D = D_prevu + D_hors_regle au franc. R_n au franc, demi vers le haut (93 095, 76 625, 166 505). Aucune date de paiement dans le passé. Les 6 premières consignes sont toujours présentes.

**Gain attendu.** 0 FCFA directement. Évite un compte débiteur le jour de l'achat et rend visible une fuite que l'outil tait.

---

### F8 — Avertissements de fuite dans l'ordre (P0)

**Objet.** L'outil parle quand une fuite devient lourde. L'avertissement existant `_capital_warnings` n'est pas modifié.

**Règles.** Seuils dans `configs/rendement_net.yaml` (Hypothèses, choisies sans base statistique).

| Code | Alerte | Condition | Niveau | Valeurs au 20/11/2026 |
|---|---|---|---|---|
| W1 | Frais annuels lourds | r = frais annuels ÷ dividendes nets attendus | orange si r ≥ 15 % ; rouge si r ≥ 50 % ; critique si r ≥ 100 % | 1 M : 265,7 % ; 10 M : 28,5 % ; 50 M : 10,1 % (aucune) ; 10 M avec la grille sans frais par ligne : 6,5 % (aucune) |
| W2 | Tarif non vérifié | `statut_global` = `supposé` | information | 10 M : 90 % des frais de la 1re année supposés ou estimés (255 762 sur 284 714 FCFA) |
| W3 | Ligne qui coûte plus qu'elle ne rapporte | frais annuels de la ligne ≥ dividende net attendu | orange | 10 M : NTLC ; 1 M : 18 lignes |
| W4 | Argent qui dort | calculé **après** les ordres proposés (F7b). Si `D_hors_regle` ≥ `seuil_argent_qui_dort_fcfa` : orange, préfixe « FUITE », avec la cause (« ordres non servis », « arrondi au-delà de la marge », « inconnue »). Sinon, si D ≥ seuil : **information sans préfixe** « Argent qui dort : X FCFA, prévu par la règle testée (dividendes gardés jusqu'à la remise à niveau de fin janvier) » | orange ou information | portefeuille détenu + 624 840 FCFA (D = 419 332) : information, cause « dividendes gardés » ; après un service partiel (674 633 FCFA de liquidités, `M/jury/marche/pf_partiel.csv`) : FUITE, cause « ordres non servis » |
| W5 | Marge du pire cas trop mince | marge recalculée avec le courtage + 0,2 point < 0 | orange, préfixe « À VÉRIFIER » | 50 M : oui (−11 697 FCFA) |
| W6 | Ordres sous le minimum du courtier | la grille a un minimum F et une tranche vaut moins de F ÷ courtage | orange, préfixe « FUITE », avec le surcoût | selon la grille |
| W7 | Vente proposée alors que des bulletins manquent | une vente proposée a pour motif l'inéligibilité (`forced_exits` contient `ineligible`, ou motif « inéligible » de la ligne) **et** la table `sessions` du panel contient au moins une séance `available = False` parmi les `feux.fenetre_trou_seances` (126) dernières séances du calendrier jusqu'à la date de décision. Le champ `execution.seances_manquantes` n'est **pas** employé : il mesure le retard du panel, déjà signalé « ORDRES PÉRIMÉS » | rouge, préfixe « À VÉRIFIER » : « Ne vendez pas à cause d'un trou de données : N bulletins manquent entre le jj/mm et le jj/mm. » | affichage seulement ; 2021 : 52 séances sans bulletin du 08/01 au 11/10 [Fait, `data/panel/sessions.parquet`] |
| W8 | Portefeuille fourni sans mémoire | `holdings` fourni et ni `memoire` ni `completer` | information : « Hors remise à niveau de janvier, la règle testée ne propose aucun ordre. Cet ordre est recalculé : écart à la règle testée. Option `--suivi`. » | — |
| W9 | Portefeuille fourni sans liquidités réelles | `holdings` fourni et `cash` absent | orange, préfixe « À VÉRIFIER » : « Liquidités prises égales à capital − titres : les frais déjà payés sont comptés comme disponibles. Donnez vos liquidités réelles (option `--cash`). » | 3e tranche d'une entrée en trois fois : 86 231 FCFA comptés à tort (§3, ligne 15) |

Texte type de W1 critique : « Les frais annuels (102 166 FCFA) dépassent les dividendes nets attendus (38 458 FCFA). À cours inchangés, ce portefeuille perd 63 708 FCFA par an. »
Texte type de W1 orange : « Les frais annuels du courtier (124 126 FCFA) prennent 28 % des dividendes nets attendus (435 988 FCFA) [supposé]. »

**Placement.** Dans la liste `avertissements` de l'ordre : **à la fin**, trois au plus, avec leur préfixe (« FUITE : » ou « À VÉRIFIER : »), dans cet ordre de priorité : W7, W9, W1 rouge ou critique, W4 « FUITE », W5, W6, W1 orange. Les informations (W2, W4 sans préfixe, W8) n'entrent jamais dans `avertissements`. Toutes les alertes figurent dans `rendement_net.alertes` et dans la section de l'ordre, sous « Points à vérifier ».

**Cas limites.** Dividendes nets nuls : W1 compare les frais annuels au capital (seuil 1 %, règle existante). Aucune alerte du module ne passe avant un avertissement existant. Panel sans table `sessions` : W7 écrit « bulletins manquants non vérifiables » au lieu de se taire.

**Intégration.** `rendement/alertes.py` : `alertes_fuite(ordre, rendement_net, grille, panels) -> list[dict]`.

**Tests** (`tests/test_rendement_alertes.py`). Trois niveaux de W1 sur 1 M, 10 M, 50 M. W3 : NTLC seule à 10 M. W4 : portefeuille détenu dont les liquidités sont des dividendes reçus depuis janvier → information sans « FUITE » ; portefeuille servi en partie → « FUITE », cause « ordres non servis ». W7 sur panel de synthèse : (a) trou de 3 séances à l'intérieur des 126 dernières séances et vente pour inéligibilité → rouge ; (b) même trou 200 séances avant → muet ; (c) panel à jour sans trou mais en retard de 3 jours → W7 muet, « ORDRES PÉRIMÉS » présent. W9 : `holdings` sans `cash` → présent ; avec `cash` → absent. Le premier avertissement reste « PANEL EN RETARD » quand il existe. Seuils lus dans le fichier de réglages. Trois alertes du module au plus dans `avertissements`.

**Gain attendu.** 0 FCFA directement.

---

### F9 — Déclaration du suivi S2 (P0 ; doit exister avant le 01/12/2026)

**Objet.** Écrire, dater et signer, avant le début du suivi, ce qui sera suivi et comment on en jugera. Le contenu est au §8. Cette fonction est l'outil ; ce n'est pas une décision de l'écran.

**Objet de données.** `reports/suivi_S2/declaration.jsonl` : fichier texte en **ajout seul**, une ligne JSON par article.

| Champ | Contenu |
|---|---|
| `n` | numéro d'ordre |
| `date_utc` | date et heure de l'écriture |
| `type` | `reference`, `essai`, `ecart_execution`, `regle_papier`, `decision_humaine`, `derogation`, `retrait`, `remplace` |
| `id` | `REF-S2`, `N`, `E-C`, `E-D`, `PLAN`, `E-A`, `E-B`, `E-L` (§8) |
| `phrase` | la règle en une phrase simple, sans mot interdit |
| `regle` | la règle exacte (texte du §8) |
| `parametres` | dictionnaire |
| `mesure`, `duree_min`, `decision_ecrite` | ce qu'on compte, pendant combien de temps, ce qu'on fera selon le résultat |
| `source_spec` | paragraphe de la spécification |
| `effet_a_partir_du` | date ; une ligne écrite après le 01/12/2026 ne vaut que pour l'avenir |
| `empreinte_config` | `settings.config_fingerprint` du YAML de stratégie |
| `empreinte_reglages` | SHA-256 de `configs/rendement_net.yaml` |
| `empreinte_cahier` | SHA-256 de ce cahier des charges, copié dans `docs/RENDEMENT_NET.md` |
| `version_code` | commit git court |
| `signe_par` | **initiales ou pseudonyme** choisis par l'humain (au plus 12 caractères, lettres, chiffres et tirets), lus dans `<données>/profil/signature.json` ; jamais un nom complet ni une adresse. Option : `signe_par_empreinte` = SHA-256 d'un texte que seul l'humain connaît, à la place des initiales |
| `precedente` | SHA-256 de la ligne précédente (chaîne de contrôle) |

**Où la commande tourne.** `suivi declarer` ne tourne que dans le **dépôt de développement** (là où `reports/` et `docs/` sont suivis par git), jamais sur le serveur d'installation : `paths.py` range `reports/trials.parquet` dans le code livré. Sur une installation, la commande refuse avec : « La déclaration se signe dans le dépôt de développement, puis se livre par un commit. » Le test : avec `BRVM_ALPHA_DONNEES` pointant hors du dépôt et sans dossier `.git` à la racine, `suivi declarer --signer` sort avec le code 2 et n'écrit rien.

**Règles.** Une ligne ne se modifie jamais. Une règle déclarée se remplace par une nouvelle ligne de type `remplace`, qui ne vaut que pour l'avenir. Toute réécriture rompt la chaîne : `declaration.verifier()` le signale et le feu « Données » passe au rouge.

**Fonctions.** `declaration.modele() -> list[dict]` (les articles proposés au §8, non signés) ; `declaration.signer(articles, signe_par, dossier) -> Path` ; `declaration.verifier(dossier) -> dict` ; `declaration.inscrire_au_registre(dossier, registre) -> list[str]` ; `declaration.en_vigueur(date) -> dict`.

**Inscription au registre des essais.** `inscrire_au_registre` **ajoute** trois à cinq lignes à `reports/trials.parquet` (colonnes `REGISTRY_COLUMNS`) : `S2-REF` (famille `S2-temoin`), `S2-N` (famille `S2-rendement`), `S2-EC` et `S2-ED` (famille `S2-rendement`, seulement si E-C et E-D sont déclarés comme essais, §8.4), `S2-PLAN` (famille `S2-execution`) ; `echantillon` = `S2` ; `statut` = `pré-enregistré` ; `parametres` = la règle déclarée ; `empreinte_config` ; `source` = `reports/suivi_S2/declaration.jsonl#<n>`. Si l'humain signe la dérogation du §8.4 (option 2), E-C et E-D ne sont pas inscrits et la ligne `derogation` de la déclaration cite le texte du §8.5 de la spécification. Les lignes existantes ne sont ni modifiées ni réordonnées. C'est la **seule** écriture du module dans ce fichier, et elle n'a lieu que sur commande explicite de l'humain (§8.7).

**Cas limites.** Aucune déclaration au 01/12/2026 : seul le témoin REF-S2 est suivi (sa définition est celle du test, elle n'a pas besoin de signature), et l'écran l'écrit. Déclaration signée après le 01/12/2026 : acceptée, avec `effet_a_partir_du` = prochaine séance ; la page Validation écrit « déclarée après le début du suivi ». Chaîne rompue : aucune ligne ne peut être ajoutée avant une décision humaine écrite.

**Intégration.** Commande `suivi declarer` (§6). Page Validation : tableau « Suivi sur papier : ce qui est déclaré » (§7.1). Rapport : liste dans la section `methode`.

**Tests** (`tests/test_suivi_declaration.py`). Ajout seul : une réécriture fait échouer `verifier`. Ligne tardive : `effet_a_partir_du` postérieur. Inscription : l'empreinte des 98 premières lignes du registre est identique avant et après ; trois lignes ajoutées (cinq avec E-C et E-D) ; seconde inscription : aucune ligne en double. `signe_par` refuse un texte de plus de 12 caractères ou contenant une espace ou « @ ». Hors dépôt de développement : refus, code 2, aucune écriture. Les phrases simples ne contiennent aucun mot interdit. Tous les tests travaillent sur une copie du registre dans un dossier temporaire.

**Gain attendu.** Aucun. Sans déclaration datée, aucune règle nouvelle ne pourra être jugée honnêtement.

---

### F10 — Journal de suivi et bulletin de la semaine (P0 pour le témoin, P1 pour le reste)

**Objet.** Donner au suivi S2 le journal durable qui lui manque. Sortir chaque semaine, sans commande à taper, un bulletin qui dit d'où vient chaque franc gagné ou perdu.

**Portefeuilles suivis** (définitions au §8.6).

| Nom | Qui le produit | Taille, tarif | Lot |
|---|---|---|---|
| `REF-S2` | le moteur de simulation existant | 10 M, tarif supposé | P0 |
| `N` | le moteur, avec les notes | 10 M, tarif supposé | P1 |
| `E-C`, `E-D` | l'exécution sur papier en mode « test » (F12), REF-S2 plus un seul écart ; seulement si déclarés comme essais (§8.4) | 10 M, tarif supposé | P1 |
| `PLAN` | `recommend --suivi PLAN` et l'exécution sur papier (F12) | 10 M, tarif supposé | P1 |
| `MOI` | idem, ou saisie des avis d'opéré | taille et grille de l'utilisateur | P1 |

**Calcul du témoin** (`suivi/temoin.py`). `temoin.maj(nom, panels, dossier)` relance le moteur de la première décision (dernière séance ≤ 30/11/2026 ; première exécution à la première séance ≥ 01/12/2026) jusqu'au dernier bulletin, avec `validation.runner.execute_run(spec, panels, ctx)`. `runner.SAMPLES` ne connaît que « S1 » et « S0 », et la fabrique par défaut `brvm_alpha_model` lit `SAMPLES[sample]` et fixe `notes=None` : le module ne l'emploie pas et **ne modifie pas `runner.py`**. Il fournit sa propre fabrique :

```python
def temoin_model(spec: RunSpec, cfg, sample: str, *, notes=None, history_start=None):
    """REF-S2 : notes=None. N : NoteStore du journal, mode historique strict (notes_known_at = date de décision)."""
    from brvm_alpha.strategy import BrvmAlpha
    kw = dict(capital=float(spec.capital), notes=notes, window_basis="sessions",
              validation_s1=False, history_start=history_start)
    try:
        return BrvmAlpha(cfg, variant="REF", **kw)
    except ValueError:                       # même repli que runner.brvm_alpha_model
        return runner._IndexModeModel(BrvmAlpha(cfg, variant="A", **kw))

spec = RunSpec("REF", costs="central", capital=10_000_000)
ctx = {"sample": "S2", "start": "2026-11-30", "end": dernier_bulletin, "decision_mode": "evenementiel",
       "strategy_params": settings.load_strategy_config(),          # comme run_validation (runner.py, ligne 844)
       "factory": functools.partial(temoin_model, notes=None),       # N : notes=NoteStore(..., strict)
       "capture": ()}
```

`ctx["sample"]` vaut « S2 » : seule la fabrique le lit, et elle ne consulte pas `SAMPLES`. `start` = dernière séance ≤ 30/11/2026 (le 30/11/2026 si c'est une séance). Le module n'appelle ni `run_validation` ni la commande `validate`, et n'écrit rien sous `reports/`. Il refuse toute date ≤ 16/11/2022.

**Test de non-régression de la fabrique** (`tests/test_suivi_temoin.py`, panel de synthèse) : `execute_run` avec `ctx["factory"] = temoin_model` et `ctx["sample"] = "S0"` redonne, au franc, la même série de valeurs et les mêmes ordres qu'avec `brvm_alpha_model` et `sample = "S0"` sur la même fenêtre (pour ce test, `temoin_model` reçoit `history_start` = début de S0, la valeur que `brvm_alpha_model` emploie). Un second test vérifie que `ok` vaut `True` avec `sample = "S2"`.

**Fichiers d'un portefeuille** (`<données>/suivi/<nom>/`).
- `operations.csv` : `date, type, symbole, titres, prix, courtage, taxe, brvm, dcbr, autres_frais, cout_prix, montant_net, source` ; `type` ∈ {achat, vente, dividende, frais_fixes, apport, retrait, division} ; `source` ∈ {moteur, papier, avis_opere}.
- `positions.csv` : `date, symbole, titres, cours, valeur`, une ligne par titre et par séance.
- `semaines.csv` : une ligne par semaine (colonnes ci-dessous).
- `empreintes.jsonl` : SHA-256 de chaque ligne de `semaines.csv`, chaînées.

**Ligne de la semaine.** Pour la semaine qui finit le vendredi v ; t = dernière séance disponible ≤ v :
- `valeur_titres` T = Σ titres × clôture en t (titre sans cours ce jour : dernier cours connu ; titre hors bulletin : dernier cours − 10 %, règle existante) ;
- `liquidites` L = L de départ + apports − retraits + dividendes nets crédités − frais fixes prélevés − achats nets + ventes nettes ;
- `valeur` V = T + L (+ réserve hors actions pour `MOI`) ; `argent_engage` K = apports − retraits (titres apportés au départ comptés à leur clôture du jour d'apport, T_0) ; `ecart` E = V − K ;
- **pont, une seule base : le cours de référence avant l'ordre.** Pour chaque exécution j (n_j titres, prix d'exécution x_j, cours de référence r_j = dernière clôture connue à la décision de l'ordre) :
  - `cout_prix_j` = n_j × (x_j − r_j) pour un achat, n_j × (r_j − x_j) pour une vente (peut être négatif) ;
  - `effet_cours` = T_t − T_0 − Σ_achats n_j × r_j + Σ_ventes n_j × r_j (les cours bougent par rapport au cours de référence ; aucun frais n'y entre) ;
  - `frais_transaction` = Σ frais facturés + Σ `cout_prix_j` ;
  - `dividendes_recus`, `frais_fixes`, `interets` (saisis, `MOI` seulement) ;
  - identité **E = effet_cours + dividendes_recus − frais_transaction − frais_fixes + interets**, au franc près.
  Exemple de recette : apport 2 000 ; achat de 10 titres, cours de référence 100, exécution à 101, frais facturés 10 ; clôture 105. L = 2 000 − 1 010 − 10 = 980 ; V = 1 050 + 980 = 2 030 ; E = 30. `effet_cours` = 1 050 − 0 − 1 000 = 50 ; `frais_transaction` = 10 + 10 × (101 − 100) = 20 ; 50 − 20 = 30. Avec une vente ensuite des 10 titres (référence 110, exécution 109, frais f₂) : `effet_cours` = 0 − 1 000 + 1 100 = 100 ; `frais_transaction` = 10 + f₂ + 10 + 10 ; E = 80 − 10 − f₂, égal à V − K. L'ancienne écriture (effet de cours contre le prix d'exécution **et** coût dans le prix dans les frais) comptait le coût dans le prix deux fois : elle donnait 20 au lieu de 30 ;
  - entre un détachement et le paiement, l'effet de cours contient la baisse du détachement ; le dividende à recevoir est affiché à part (« à recevoir »), hors identité ;
- `fuites_definitives` = `frais_transaction` + `frais_fixes` ; `pertes_non_realisees` = Σ des écarts négatifs de cours des lignes détenues ; `pertes_realisees` ;
- `part_investie` = T ÷ V ; `argent_qui_dort` = L − 2 % × V ; `argent_qui_dort_prevu` = projection de F7(d) à la même date pour la règle déclarée ;
- `indice_tr` (Composite TR du panel) ; **valeur de part** u_t (rendement pondéré par le temps) : u = 1 au départ ; à chaque apport ou retrait, des parts sont créées ou détruites à la valeur de part de la veille ; u_t = V_t ÷ parts ; `ecart_au_marche` = (u_t ÷ u_0) ÷ (indice en t ÷ indice au départ) − 1. L'ancien calcul V ÷ K ÷ indice est faux dès qu'il y a plusieurs apports ;
- `ordres_emis`, `ordres_servis`, `titres_demandes`, `titres_servis` ; `bulletins_manquants` (séances de la semaine sans bulletin) ;
- `variation_semaine` = E − E de la semaine précédente, avec le même pont.

**Reproductibilité.** Deux lancements la même semaine : une seule ligne. Semaine sautée : lignes reconstruites. Pour `REF-S2` et `N`, chaque relance doit retrouver à l'identique les lignes déjà écrites ; sinon la ligne n'est pas réécrite, une entrée est ajoutée à `anomalies.jsonl` (« le passé a changé », date, cause probable : donnée corrigée) et le feu « Données » passe au rouge.

**Bulletin** (`suivi/bulletin.py`, gabarit ; les valeurs viennent du journal).

```
BULLETIN DE LA SEMAINE — vendredi jj/mm/aaaa — semaine n — portefeuille sur papier
Performance passée ≠ garantie. Aucun gain n'est garanti. Étude seulement.

Mon portefeuille vaut {V} FCFA. Depuis le départ : {E} FCFA. Depuis la semaine dernière : {e} FCFA.
   cours {c} ; dividendes reçus {d} ; frais d'achat et de vente {f} ; frais annuels prélevés {g}
   Frais partis pour de bon : {F} FCFA. Baisses de cours non vendues : {P} FCFA (elles peuvent se retourner
   ou s'aggraver).

FEU PERTE     {état}   {phrase}
FEU FUITES    {état}   {phrase}
FEU DONNÉES   {état}   {phrase}

À REVOIR (pas à vendre) : {n} lignes ...
PROCHAINS RENDEZ-VOUS : {prochain dividende attendu, montant} ; {prochain prélèvement de frais, montant} ; remise à niveau le 29/01/2027
LE PANIER DE RÉFÉRENCE FACE AU MARCHÉ : {écart au marché, en valeur de part} depuis le 01/12/2026 (retard attendu
   la 1re année : 3,3 à 4,2 points ; avant plusieurs années, cet écart ne prouve rien).
Un feu ouvre une revue, jamais une vente. Aucune de ces décisions n'a été testée.
```

Semaine 0 (avant le 01/12/2026 ou sans opération) : état avant achat et prochains rendez-vous seulement. Compteurs ajoutés pour `MOI` en mode réel : « frais évités depuis le début par rapport au tarif supposé : X FCFA [compté sur avis d'opéré] » ; « part de la facture encore supposée : Y % ».

**Sans commande à taper.** `deploiement/quotidien.sh` appelle `suivi maj` après l'étape `panel` ; le rapport du jour et le Tableau de bord affichent le dernier bulletin. La commande `suivi bulletin` l'affiche à la demande. Cette étape change la liste exacte des appels attendue par `tests/test_deploiement_scripts.py` : exception déclarée au §9.1. Comme les étapes réseau, `suivi maj` ne doit pas arrêter la tâche de nuit : en cas d'échec, elle écrit son erreur dans le journal et la tâche continue vers `report`.

**Cas limites.** Division d'actions (lue dans `corporate_actions`) : titres × rapport, prix de revient ÷ rapport, le jour de la division ; la valeur ne bouge pas ce jour-là. Vendredi sans bulletin : cours de la dernière séance disponible, feu « Données » orange. Dividende : crédité net à la date de paiement publiée, pour les titres détenus la veille du détachement. Dates : `MOI` accepte toute date postérieure au 16/11/2022 (un achat réel du 23/11/2026 peut être saisi) ; `REF-S2`, `N` et `PLAN` commencent au 01/12/2026.

**Intégration.** Commande `suivi` (§6). Interface : trois feux sur la carte « Mon plan » ; bulletin complet sur la page Portefeuille ; tableau des portefeuilles sur la page Validation. Rapport : feux dans la carte du `bandeau` ; bulletin à la fin de la section `risques`. Ordre : la mention « aucun historique de suivi réel » de la section des déclencheurs est remplacée par l'état du journal quand il existe. JSON : `rendement_net.suivi`.

**Tests** (`tests/test_suivi_journal.py`, panel de synthèse). Identité du pont au franc, dont l'exemple de recette ci-dessus (achat puis vente) et un coût dans le prix négatif. Valeur de part : deux apports à des dates différentes, marché plat, aucun frais → `ecart_au_marche` = 0. Division d'actions : valeur inchangée le jour de la division (cas réel à reproduire en synthèse : Sonatel, 10 pour 1, le 26/10/2026 ; sans ajustement, l'erreur dépasse 20 M FCFA [Fait, prototype `M/designs/particulier_travail/p4_bulletin.py`]). Vendredi sans bulletin : une ligne, feu orange. Idempotence. « Le passé a changé » détecté. Refus d'une date de S1. Le témoin n'écrit rien sous `reports/`. Le bulletin ne contient aucun mot interdit. Aucun test ne fige un exemple tiré d'une date réelle choisie après coup.

**Gain attendu.** Aucun gain direct. Le journal transforme le suivi S2 en faits comptés : frais payés, argent qui dort, taux d'exécution, retard sur le marché.

---

### F11 — Trois feux et revue guidée (P1)

**Objet.** Trois feux, pas onze codes. Un feu allumé a une sortie : la revue. Aucune vente n'est proposée.

**Avertissement fixe.** « Seuils choisis après lecture de la période 2022-2026, sans base statistique. Leur utilité est inconnue. Ils sonneraient plus souvent en marché baissier. »

**Feu « Perte »** (portefeuille `MOI` ; `PLAN` à défaut). Perte en cours p = max(0 ; K − V), mesurée depuis l'argent engagé, **sans remise à zéro au 1er janvier**.
- Avec un choix X (F4) : orange quand p ≥ 0,5 × X ; rouge quand p ≥ X ; paliers suivants à 1,5 × X et 2 × X.
- Sans choix : orange quand p ≥ 10 % de l'argent engagé en actions ; rouge quand p ≥ 20 %.
- Phrase : « {p} FCFA sous l'argent engagé. Vous avez accepté de risquer {X} FCFA. Une année comme 2018 dépasse ce montant en cours d'année. »

**Feu « Fuites ».**
- Orange si l'une de ces conditions est vraie : (a) sur un avis d'opéré, frais lus > frais prévus par la grille de plus de 1 000 FCFA **et** de 5 % ; (b) `argent_qui_dort − argent_qui_dort_prevu` > 100 000 FCFA pendant plus de 20 séances ; (c) un ordre non servi a expiré (10 séances) ; (d) un dividende n'est pas crédité 30 jours après la date de son **avis de paiement publié**.
- Rouge si : les liquidités ne couvrent pas le prochain prélèvement de frais fixes ; ou W1 critique (frais annuels > dividendes attendus).
- Sur un portefeuille sur papier au tarif supposé, la condition (a) affiche « sans objet (papier) » : elle n'est pas « verte ».
- La condition (b) compare à ce que la **règle déclarée** prévoit : un portefeuille qui suit la règle testée n'allume pas le feu parce que ses dividendes attendent janvier.

**Feu « Données ».** Orange : 1 ou 2 bulletins manquants dans la semaine ; ou journal en retard de plus de 9 jours. Rouge : 3 bulletins manquants ou plus (« aucun ordre de vente ne doit partir ») ; ou chaîne du journal ou de la déclaration rompue ; ou « le passé a changé » ; ou un ordre proposé contredit une décision déclarée.

**Lignes « à revoir, pas à vendre ».** L1 : baisse depuis l'achat, dividendes compris, ≥ 25 % (paliers 35 %, 45 %). L2 : perte de la ligne ≥ 10 % de X (sans choix : ≥ 1 % de V). L3 : règle existante du §9.1 (−25 % contre le marché en 63 séances). L4 : la ligne coûte plus qu'elle ne rapporte (W3). Les cours employés comprennent les dividendes : un détachement n'allume rien.

**Vie d'une alerte.** `ouverte` → `revue faite le jj/mm` (décision écrite) → `close`. Elle ne se rouvre qu'au palier suivant. Le feu affiche alors « ORANGE — revue faite le 12/03 ». Une alerte rouge sans revue depuis 14 jours ajoute un rappel.

**La revue** (`suivi revue`, formulaire de la page Portefeuille). Cinq questions, réponse écrite dans le carnet (type `revue`) :
1. La baisse vient-elle du marché ou du titre ?
2. Une note, un filtre de risque ou une publication l'explique-t-il ?
3. Le dividende attendu est-il menacé ?
4. Votre besoin d'argent ou votre durée ont-ils changé ?
5. Décision : garder ; ne plus acheter ; réduire par ordres à cours limité sur plusieurs séances.
Pour le feu « Perte » rouge s'ajoute : « Ce que vous acceptez de risquer est-il toujours le bon montant ? » (un nouveau choix s'écrit comme une nouvelle ligne `mandat`).

**Le prix de chaque décision**, affiché avant la réponse :

| Décision | Coût calculé |
|---|---|
| Garder | 0 FCFA de frais ; on reste exposé |
| Ne plus acheter | 0 FCFA ; la ligne s'écarte de son poids |
| Réduire ou vendre | frais de sortie (`order_costs`, vente) + perte réalisée (prix de revient) + dividende attendu abandonné ; si l'on rachète plus tard : un aller-retour, 3,33 % du montant à 10 M [Estimation] |

Phrase fixe : `PH_REVUE`. Copie facultative de la décision dans le journal des notes (avis neutre, étiquette `revue`, sans veto) : seulement sur action de l'utilisateur.

**Fonctions.** `alertes.feux(semaine, plan, declaration, alertes_ouvertes) -> dict` ; `alertes.lignes_a_revoir(etat, plan) -> list` ; `alertes.ouvrir`, `alertes.clore`, `alertes.prix_des_decisions(etat, symbole, costs) -> dict`.

**Tests** (`tests/test_suivi_feux.py`). Seuils exacts (49,9 % de X : vert ; 50,0 % : orange). Aucune fonction ne produit d'ordre : `recommend` rend les mêmes ordres avec ou sans alertes ouvertes. Palier et réarmement. Un jour de détachement n'ouvre pas L1. Portefeuille suivant la règle testée, dividendes reçus de mai à septembre : le feu « Fuites » reste vert (condition b). Papier : (a) « sans objet ». Le coût d'aller-retour affiché égale deux fois les frais d'achat.

**Statut.** Fréquences mesurées sur S0 (diagnostic contaminé, période très haussière) : L1 1,0 ligne par an ; L3 3,6 ; ensemble environ 4 lignes par an [Estimation, `M/pertes/08_alertes.py`]. **Gain attendu.** Aucun effet direct. Coût évité si une vente de panique est écartée : un aller-retour de 321 176 FCFA à 10 M [Estimation].

---

### F12 — Carnet, exécution sur papier, pont, avis d'opéré (P1)

**Objet.** L'outil se souvient de ce qui a été acheté, à quel prix, avec quels frais. Sur papier, il applique la règle que l'utilisateur pourrait vraiment suivre. En réel, il remplace les suppositions par les frais lus sur l'avis d'opéré.

**Carnet** (`suivi/carnet.py`, `<données>/suivi/<nom>/carnet.jsonl`, ajout seul). Mouvements :

| Type | Champs |
|---|---|
| `mandat` | capital total, ce que j'accepte de risquer, montant en actions, réserve, taux de la réserve, grille, mode (`papier` ou `reel`), options d'exécution |
| `apport`, `retrait` | date, montant |
| `ordre` | date de décision, titre, sens, titres, limite, validité, empreinte de configuration |
| `execution` | date, titre, sens, titres, prix, frais détaillés, heure ou phase de marché (facultatif), source (`papier`, `avis_opere`) |
| `expiration` | date, titre, titres non servis |
| `dividende` | date de paiement, titre, net par titre, titres, montant net |
| `frais` | date, nature (garde, tenue de compte, forfait, autre), montant |
| `division` | date, titre, rapport |
| `revue` | alerte, réponses, décision |
| `correction` | mouvement annulé, motif |

Prix de revient par ligne = coût moyen pondéré, frais facturés compris : `PR = Σ(titres × prix + frais) ÷ Σ titres`. Une vente ne change pas PR ; résultat réalisé = titres × (prix − PR) − frais. Division : titres × rapport, PR ÷ rapport. Refus : saisie en double ; vente de plus de titres que détenus ; date ≤ 16/11/2022.

**Exécution sur papier** (`suivi/papier.py`). Deux modes.
- Mode `limite` (défaut) : règle **plus stricte que le §7.1 de la spécification** (elle ajoute un test de limite) ; elle est déclarée comme telle (§8.3, article E-L). Elle sert `PLAN` et `MOI`.
- Mode `test` : exécution du §7.1 sans test de limite (cours moyen du jour suivant si le titre est échangé, 10 % du volume du jour, report 10 séances), pour les essais `E-C` et `E-D` (§8.4), afin qu'ils ne diffèrent du témoin que par leur écart. Contrôle P8 (§8.2) : en mode `test`, sans écart, le carnet redonne les ordres et les valeurs hebdomadaires de `REF-S2` au franc près ; sinon, les écarts sont publiés et `E-C`, `E-D` sont lus avec cette réserve.
Le témoin `REF-S2` garde l'exécution du moteur.

Règles du mode `limite` :
- Un ordre décidé à la clôture de t est saisi pour la séance suivante, avec la limite de `limit_prices`.
- À la séance d, un achat est servi si le titre a coté et si son cours moyen du jour (valeur ÷ volume) est ≤ la limite ; une vente, s'il est ≥ la limite.
- Titres servis = min(reste ; ⌊0,10 × volume du jour⌋). Prix = cours moyen du jour. Frais facturés = `fee_breakdown` de la grille.
- Le reste est reporté. Après 10 séances : `expiration`.
- Jour de détachement ou de division du titre : l'ordre est annulé et ressaisi le jour même, avec une limite recalculée sur la référence ajustée.
- Un achat financé par une vente n'est possible qu'à partir du règlement de la vente (deux séances).
- Dividendes crédités nets à la date de paiement publiée. Frais fixes prélevés en fin de trimestre civil [Hypothèse].
- Mesures tenues à jour : part des titres servis à 1, 3 et 10 séances ; prix payé contre dernier cours ; prix payé contre cours moyen du jour ; séances pour finir un ordre.

**État et pont** (`suivi/etat.py`). Par ligne : valeur, coût (titres × PR), dividendes nets reçus, résultat non réalisé, résultat réalisé, plus bas depuis l'achat (dividendes compris), frais annuels contre dividende attendu, et « si l'on vendait aujourd'hui » : frais de sortie, perte réalisée, dividende attendu abandonné. Portefeuille : le pont de F10.

**Avis d'opéré (mode réel).** Saisie par ligne : date, titre, sens, titres, prix, courtage, taxe, commissions, autres frais, total. Taux déduits : courtage ÷ montant ; taxe ÷ courtage ; commissions ÷ montant. Comparaison à la grille à 1 FCFA près par ligne. Si tout concorde : les champs de la grille passent au statut `avis d'opéré`. Sinon : l'écart est affiché en FCFA et une correction de la grille est **proposée**, appliquée seulement après confirmation. Frais inconnus de la grille : ajoutés comme postes nouveaux, jamais ignorés. Coût dans le prix mesuré = (prix payé − dernier cours avant l'ordre) × titres, comparé à l'estimation de l'ordre.

**Fonctions.** `carnet.ouvrir(nom, dossier)`, `carnet.ajouter(mouvement)`, `carnet.positions(date)`, `carnet.memoire() -> dict` (pour `recommend --suivi`) ; `papier.executer(carnet, panels, jusqu_a)` ; `etat.etat(carnet, panels, date) -> dict` ; `carnet.saisir_avis(lignes, grille) -> dict`.

**Tests** (`tests/test_suivi_carnet.py`, `tests/test_suivi_papier.py`). Identité comptable au franc : apports − retraits + résultat = titres + liquidités. Mode `test` sans écart, sur panel de synthèse : mêmes ordres et mêmes valeurs hebdomadaires que le moteur (contrôle P8). Division 10 pour 1 : 64 titres deviennent 640, PR divisé par 10. Ordre sur papier non servi (cours moyen au-dessus de la limite) puis expiré après 10 séances. Annulation et ressaisie le jour d'un détachement. Achat différé jusqu'au règlement d'une vente. Avis fabriqué avec le tarif supposé : tout concorde, statut `avis d'opéré`. Avis avec un courtage de 1 % : écart affiché, statut inchangé tant que l'utilisateur ne confirme pas. Coût dans le prix négatif : accepté et affiché tel quel. Aucune écriture hors du dossier du portefeuille.

**Gain attendu.** Aucun direct. Les avis saisis deviennent des Faits ; avec le relevé annuel des frais, ils portent sur les 255 762 FCFA de frais non vérifiés de la 1re année à 10 M (dont 40 536 FCFA de coûts dans le prix, que seul l'avis mesure). L'impôt sur les dividendes (55 527 FCFA) devient un Fait au paiement, par l'avis de paiement.

---

### F13 — Options d'exécution (P1 ; toutes éteintes par défaut ; toutes déclarées au §8)

Chaque sortie produite avec une de ces options porte : « Écart à la règle testée : {nom}. Décision d'exécution déclarée le {date} ; non jugée. » Pour E-C et E-D, déclarés comme essais (§8.4) : « Essai sur papier : {nom}. Déclaré le {date} ; jugé sur le suivi seulement. »

**(a) Mémoire annuelle : `recommend --suivi NOM`.** Ce mode reproduit la règle testée, **sans aucun écart** : il ne contient pas la continuité des données (E-C), qui reste une option à part (e).
- L'état vient du carnet (`carnet.memoire()` : titres détenus, liquidités réelles, date et année de la dernière remise à niveau de janvier, quantités de l'ordre d'origine non servies).
- Interface avec le modèle : `recommend` passe `memoire_ref = {"annee": …, "date": …}` à `BrvmAlpha` (§4.3). Le modèle amorce alors `self._sleeves["ref"]` comme le moteur l'aurait laissé après cette décision : à une date de la même année, avec des titres détenus, `_reference_portfolio` prend le chemin `_index_hold` (conservation) ; à la première décision de l'année suivante, il remet à niveau. Aucune autre interface n'est créée, et l'état privé n'est jamais modifié depuis `recommend`.
- Sorties restantes entre deux remises à niveau : **exactement** celles que le code de la règle produit (`forced_exits` du YAML : `R_filters`, `ineligible`, calculés selon D1 tel que codé, y compris quand des bulletins manquent) et les règles pays. Si des bulletins manquent dans la fenêtre, l'alerte W7 s'affiche ; la vente reste proposée (c'est la règle testée).
- Si elles sont déclarées, les options (b), (d) et (e) s'ajoutent, chacune avec sa mention.

**(b) Compléter et apporter : `--completer`, `--apport MONTANT`.**
- `--completer` : pour chaque ligne de l'ordre d'origine dont les titres détenus sont inférieurs à la quantité d'origine, achat du manque, **sans la bande de 2 points**, avec une limite recalculée du jour, sous le contrôle du pire cas et les plafonds existants. Sur papier (`PLAN`), la ressaisie a lieu à la dernière séance de chaque mois tant que la quantité d'origine n'est pas atteinte.
- `--apport MONTANT` : V = titres au cours de référence + **liquidités réelles** (carnet, ou `--cash` qui comprend l'apport) ; jamais capital − titres. Cibles `q_i = ⌊w_i × V ÷ p_i⌋` avec les poids cibles du jour ; achat = max(0 ; q_i − détenus) ; **aucune vente** ; pas de bande pour ces achats ; contrôle du pire cas et plafonds inchangés. Les ventes de remise à niveau gardent la bande. Sans `--cash` ni carnet, l'option est refusée (« liquidités réelles nécessaires »).
- Conséquence écrite : les frais déjà payés ne sont pas recrédités. Après N apports aux mêmes cours, `q_i = ⌊w_i × (K − frais des N − 1 premières tranches) ÷ p_i⌋` : quelques lignes ont un titre de moins qu'un achat en une fois. C'est un écart de calendrier déclaré (E-T, §8.3).

**(c) Arrondi « plus forts restes » : `--arrondi restes`.** Appliqué aux lignes en achat, non gelées, non bloquées, et seulement si le contrôle du pire cas existant n'a réduit aucune quantité.
1. Départ : `q0_i = ⌊x_i + 1e-9⌋`, `x_i = w_i × V ÷ p_i` ; reste `f_i = x_i − q0_i`.
2. Marge `M = n × (garde × cible investie + tenue par ligne × lignes cibles + forfait) ÷ 4`, n = `marge_arrondi_trimestres` (2), cible investie = `cible_pct` × V. À 10 M : 2 × (24 500 + 100 000) ÷ 4 = 62 250 FCFA.
3. Parcours des lignes par reste décroissant, puis par code de titre. Pour chaque ligne de reste > 1e-9 : essayer `q0_i + 1` ; garder si **toutes** les conditions tiennent : (C1) Σ provisions du pire cas des achats ≤ ⌊liquidités⌋ + encaissement minimal des ventes − M ; (C2) Σ titres × cours ≤ cible investie ; (C3) plafonds de ligne, de secteur, de pays et du bloc AES (siège et exposition, `_lambda`) respectés ; une ligne sans plafond connu ne reçoit rien ; un groupe déjà au-dessus de son plafond ne reçoit rien ; (C4) le titre en plus n'allonge pas l'ordre au-delà de 10 séances ; (C5) un seul titre de plus par ligne.
4. Si M ne tient pas avec les quantités de départ : rien n'est ajouté, et le motif est écrit.
5. L'option est refusée si `statut_global(grille)` vaut `supposé`, sauf `--forcer` (emploi sur papier).
Sorties : quantités, francs ajoutés, part investie, marge du pire cas, somme des écarts aux poids cibles avant et après.

**(d) Réinvestissement mensuel : `--reinvestir`** (essai E-D, §8.4). À la dernière séance du mois, avec `D = liquidités − 2 % × V` : choisir la ligne dont le manque `w_i × V − titres_i × p_i` est le plus grand parmi les lignes non bloquées (note, filtre de risque, suspension, borne haute) ; calculer le **montant permis** `M_i = min(D ; (min(plafond de la ligne ; w_i + 0,01)) × V − titres_i × p_i)` ; acheter seulement si `M_i ≥ S`, avec `S = max(100 000 ; minimum par ordre ÷ taux de courtage)` ; sinon, ne rien faire ce mois-ci (aucun report sur une autre ligne). Quantité : le plus grand nombre de titres dont le coût net ≤ `M_i` et pour lequel le contrôle du pire cas tient. **Une seule ligne** par mois. Aucune vente. Le seuil porte sur le montant permis, et non sur D : à 10 M, la borne « w_i + 1 point » limite l'ordre à 218 586 FCFA au plus (SNTS), sous les 312 500 FCFA qu'exigerait un minimum de 2 500 FCFA par ordre ; avec ce minimum, l'option ne passe donc aucun ordre, au lieu de payer 1,65 % de frais explicites contre 1,39 % à l'entrée [Hypothèse (tarif), `F/f5_tranches.py` (4)]. **La règle ne regarde pas le calendrier des dividendes** : elle achètera souvent un titre qui vient de détacher ; l'enjeu est estimé à 5 000 à 11 000 FCFA par an au plus [Estimation, `M/rendement/rapport.md` §5.1].

**(e) Continuité des données : `--continuite`** (essai E-C, §8.4 ; jamais compris dans `--suivi`). « Bulletin manquant » = séance du calendrier sans bulletin dans le panel (table `sessions`, `available = False`), et non « titre absent d'un bulletin présent ». (1) Un titre n'est pas vendu pour une inéligibilité calculée sur une fenêtre de 126 séances où des bulletins manquent : la position est gardée, aucun achat, alerte. (2) L'âge d'un ordre se compte en bulletins disponibles. (3) Les sorties pour cause réelle restent : suspension, veto, deux drapeaux R11, inéligibilité sur une fenêtre complète. Sans épisode de bulletins manquants, le résultat est identique à celui de la règle testée.

**Valeurs de contrôle.**

| Option | Contrôle | Statut, preuve |
|---|---|---|
| (a) | 20 lignes de l'ordre détenues, 624 840 FCFA de liquidités, au 20/11/2026, `memoire_ref` = décision de janvier 2026 : aucun ordre ; W4 en information (dividendes gardés, règle testée) | Fait attendu (comportement de la règle testée), à vérifier par le test |
| (b) compléter | portefeuille servi en partie de `M/jury/marche/pf_partiel.csv` : achats ECOC 10, STBC 4, NTLC 7, SPHC 15 (manque de 469 430 FCFA avec CBIBF 1 et CIEC 1) ; sans l'option : aucun de ces quatre achats, 92,6 % investi | Fait (outil actuel) ; Hypothèse (scénario de service) |
| (b) apport | trois apports de 3 333 333 FCFA aux cours du 20/11/2026, liquidités réelles : après le troisième, **9 556 525 FCFA investis** (achat en une fois : 9 650 560), 152 382 FCFA de frais d'entrée cumulés ; six lignes ont un ou plusieurs titres de moins (SNTS −6 ; ORAC, CBIBF, BOAC, CIEC, SPHC −1), soit 94 035 FCFA de titres en moins, à cause des frais déjà payés ; formule ⌊w_i × (K − frais des deux premières tranches) ÷ p_i⌋ vérifiée ligne à ligne | Estimation (règle écrite, option non codée), `F/f5_tranches.py` (2) |
| (b) sans option | outil actuel, mêmes trois apports, liquidités réelles (`--cash`) : 7 368 680 FCFA investis (74,3 % de la valeur avant le 3e ordre), 2 514 330 FCFA de liquidités. Avec la convention « capital nominal » (`--capital` sans `--cash`) : 7 403 675 FCFA et 2 566 367 FCFA, parce que les frais déjà payés sont recrédités | Fait (outil), `Rv/echelon/t3_B.json`, `t3_A.json` ; `F/f5_tranches.py` (1) |
| (c) | 10 M : +65 485 FCFA (8 titres), investi 9 716 045 (97,16 %), marge du pire cas 66 323, frais d'achat +1 205, somme des écarts 1,052 point au lieu de 1,494 ; 1 M : +61 025 (92,73 %) ; 50 M : 0 ; 3,5 M : +114 005 ; 1,5 M : +90 045 | Fait (`M/liquidites/scripts/a_arrondis.py`, 36 combinaisons contrôlées avec les fonctions de l'outil ; recalcul `Rv/c4_sortie.txt`) |
| (c) limite | courtage réel de 1,5 % : marge du pire cas de −14 720 FCFA à 10 M | Fait de calcul (`F/f7_divers.py`) |
| (d) | simulation à cours constants, 10 M, règle corrigée (seuil sur le montant permis) : 2 ordres (SGBC fin mai, 3 titres ; SNTS fin août, 30) ; liquidités moyennes 260 923 FCFA au lieu de 388 420 (127 497 FCFA de moins) ; 3 250 FCFA de frais pour 237 585 achetés. Avec un minimum de 2 500 FCFA par ordre : aucun ordre (montant permis ≤ 218 586 < 312 500) | Estimation (`F/f8_reinvestir.py` ; l'ancienne règle donnait 3 ordres et 221 100 FCFA) |
| (e) | sans bulletin manquant : mêmes ordres qu'avec l'option éteinte | à vérifier par le test |

**Tests** (`tests/test_rendement_execution.py`). Sans option : sortie identique à aujourd'hui (quantités, prix limites, frais) sur les trois capitaux. (a) : sur panel de synthèse sans trou de bulletins, le moteur tourne de janvier à juin ; à une date de mai, `recommend --suivi` avec les titres et les liquidités du moteur et `memoire_ref` = sa décision de janvier rend **les mêmes ordres que le moteur** pour REF ce jour-là (aucun, sauf sortie forcée) ; avec un trou de bulletins et une inéligibilité, la vente reste proposée et W7 s'affiche ; `BrvmAlpha(..., memoire_ref=None)` laisse tous les tests existants verts. (c) : quantité ≤ `q0 + 1` ; investi ≤ cible ; provision ≤ liquidités − M ; valeurs du tableau ; plafond saturé : la ligne ne reçoit rien ; somme des écarts aux poids jamais plus grande. (b) : aucune vente ; part investie après ≥ avant ; `--apport` sans liquidités réelles refusé ; après N apports aux mêmes cours, `q_i = ⌊w_i × (K − frais des N − 1 premières tranches) ÷ p_i⌋` au titre près. (d) : une ligne par appel ; jamais au-dessus de la cible + 1 point ; aucun ordre quand le montant permis est sous S. (e) : sans trou, mêmes ordres qu'option éteinte ; jamais activée par `--suivi` seul. Les deux tests existants sur l'arrondi vers le bas restent verts.

**Gain attendu.** Aucun gain démontré. Ces options placent plus d'argent ; elles gagnent plus si le marché monte et perdent plus s'il baisse (tableau B de F3). E-C et E-D sont jugés sur le suivi seulement (§8.4).

---

### F14 — Durée : « quand aurez-vous besoin de cet argent ? » (P1)

**Objet.** L'argent de court terme ne va pas en actions. L'utilisateur donne un nombre de mois ; l'écran répond par deux faits et une règle simple.

**Calcul.** Revenu net annuel attendu = d − a (dividendes nets attendus − frais annuels). Mois pour couvrir les frais d'achat = 12 × e ÷ (d − a). Mois pour couvrir un achat suivi d'une revente = 24 × e ÷ (d − a). « Jamais » si d ≤ a. Point de repère : (2e + H × a − H × d) ÷ investi = hausse des cours nécessaire pour ne rien perdre en revendant après H ans.
- Si le besoin M est inférieur aux mois d'un achat-revente : « Cet argent devrait rester en réserve : les revenus attendus ne couvrent pas les frais d'un achat suivi d'une revente. »
- Si M < 96 : « Avec les dividendes, le marché est resté près de 5 ans (59 mois) sous son plus haut de 2017 ; sans les dividendes, près de 8 ans (95 mois). » [Fait descriptif : Composite TR reconstruit, plus haut le 01/03/2017, retour le 25/02/2022 ; Composite prix, retour le 20/02/2025 ; `F/f6_indices.py`]
- Périodes réellement observées de 12, 24 et 36 mois : nombre, nombre en perte, pire période (règle de renormalisation de F6, point 4). **Règle fixe, sans calcul** : à 24 et 36 mois, aucune fréquence ni aucun pourcentage n'est affiché, ni tiré du passé rejoué, ni tiré des périodes réelles ; le tableau donne seulement le nombre de périodes, le pire cas et la phrase « trop peu de périodes qui ne se chevauchent pas pour un chiffre fiable ». (Les périodes de 24 mois prises dans 119 fins de mois se recouvrent presque toutes : il n'en tient que 4 sans chevauchement.)

**Valeurs de contrôle** [`S/s5_reserve_leviers.py`, `F/f2_poches.py`, `F/f3_periodes.py`]. 10 M, tarif supposé : 6,2 mois pour les frais d'achat, 12,4 mois pour un achat-revente ; hausse nécessaire +0,10 % sur 1 an. Poche de 3 000 000 FCFA, tarif supposé : 28,3 et 56,5 mois. Poche de 3 400 000 FCFA, grille sans frais par ligne : 5,3 et 10,7 mois. 1 M : « jamais » ; +10,47 % sur 1 an, +25,18 % sur 3 ans. Périodes réelles du panier, net de frais [descriptif, pas un test] : 12 mois 37 sur 107 en perte, pire −26,7 % ; 24 mois 95 périodes, pire −36,7 % ; 36 mois 83 périodes, pire −43,1 %.

**Intégration.** Option `--besoin-dans MOIS` de `plan` ; champ « J'aurai besoin de cet argent dans … mois » sur la carte ; sous-bloc de la section de l'ordre. Fonctions : `bilan.amortissement(poche) -> dict` ; `risque.durees(ordre, panels) -> dict`. JSON : `rendement_net.bilan.amortissement`, `rendement_net.risque.durees`.

**Tests.** Valeurs ci-dessus. « Jamais » à 1 M. Aucun pourcentage, ni du passé rejoué ni des périodes réelles, pour 24 et 36 mois. La phrase des 59 et 95 mois porte les deux durées.

---

### F15 — Entrer en plusieurs fois (P2)

**Objet.** Si l'utilisateur veut entrer en N fois, la plate-forme prépare chaque tranche correctement et ne lui vend pas l'étalement comme un gain.

**Calcul.** Chaque tranche est un appel `recommend … --apport` (F13b) le jour de la tranche, avec V = titres au cours + **liquidités réelles** du carnet : les cibles, les limites et la provision sont **recalculées à chaque fois**. Aucune découpe figée au premier jour. Le plan de tranches (dates, montants égaux) est écrit dans le carnet. Si la grille a un minimum par ordre m : surcoût = Σ, par tranche d'exécution, de (frais avec minimum − frais sans minimum) ; à 10 M et m = 2 500 FCFA : +13 841 FCFA en une fois, **+109 740** en trois tranches en mode apport [Estimation, tarif supposé, `F/f5_tranches.py` (3)]. Les frais d'entrée cumulés des trois tranches sont 152 382 FCFA (160 588 en une fois) ; les frais déjà payés ne sont pas réinvestis, d'où 94 035 FCFA de titres en moins après la troisième (F13b).

**Textes.** `PH_ETALER`. « Douze tranches reviennent à être investi à moitié la première année : choisissez plutôt le montant en actions. » « Chaque tranche se calcule sur vos liquidités réelles : les frais déjà payés ne reviennent pas. » Aucun « fait mieux dans X % des cas » : ce résultat ne dépend que du sens du marché pendant le délai, qui est inconnu.

**Intégration.** Option `--tranches N` de `plan` (écrit le plan) ; réglage sous « Autres réglages » de la carte. Dépend de F13b. Si l'utilisateur l'applique, c'est un écart de calendrier à déclarer (§8.3, E-T). Une tranche lancée avec `--capital` sans `--cash` ni carnet déclenche W9.

**Tests.** Après N tranches aux mêmes cours : `q_i = ⌊w_i × (K − frais des N − 1 premières tranches) ÷ p_i⌋` au titre près (à 10 M, N = 3 : 9 556 525 FCFA investis). Une tranche sans liquidités réelles : W9. Le texte contient `PH_ETALER` et aucun pourcentage de réussite.

---

### F16 — Date de paiement projetée (P2 ; après accord écrit)

**Objet.** L'outil projette le paiement d'un dividende deux jours ouvrés après le détachement. En 2026, il a suivi le détachement d'un jour ouvré dans 35 cas sur 35 [Fait, `M/jury/marche/j2_microstructure.py`].

**Changement.** Dans `dividend_schedule` : date de paiement prévue = détachement prévu + 1 jour ouvré. Aucun montant ne change. Les dates affichées dans la table des dividendes et dans la projection de F7 avancent d'un jour ou deux (premier paiement prévu : 30/04/2027 au lieu du 03/05/2027). Les valeurs de recette par mois de F7 sont alors à recalculer ; le total (435 988 FCFA à 10 M) ne change pas.

**Tests.** Sur le panel réel : SNTS, détachement prévu le 17/05/2027, paiement prévu le 18/05/2027. Somme des dividendes inchangée (435 988 FCFA à 10 M).

---

## 6. Commandes en ligne

Toutes les commandes nouvelles refusent une date de décision ≤ 16/11/2022 (`in_s1`, comme `recommend`). Toutes portent `BANNER` en pied d'aide. Montants : formats de `parse_capital` (« 10M », « 1 000 000 »). Taux : en pourcentage, virgule ou point (« 0,5 » = 0,5 %).

```
python -m brvm_alpha plan [--capital K] [--perte-toleree MONTANT|P%] [--taux-reserve T] [--besoin-dans MOIS]
                          [--grille ma_sgi|central|FICHIER] [--tranches N] [--format texte|md|json] [--sortie CHEMIN]
                          [--date AAAA-MM-JJ] [--panel-dir D] [--racine D] [--notes-au INSTANT] [--enregistrer]
python -m brvm_alpha plan grille [--afficher] [--comparer --capital K]
                          [--courtage T --taxe T --min-ordre M --garde T --par-ligne M --forfait M]
                          [--taxe-frais T --garde-min M --encaissement T --encaissement-fixe M --transfert M]
                          [--investisseur physique|morale] [--pays P] [--source TEXTE] [--statut suppose|ecrit|avis]
python -m brvm_alpha plan questions

python -m brvm_alpha suivi demarrer --nom MOI [--capital K] [--mode papier|reel]
python -m brvm_alpha suivi maj [--nom NOM]            # met à jour tous les portefeuilles, écrit la ligne de la semaine
python -m brvm_alpha suivi bulletin [--nom NOM] [--format texte|md|json] [--sortie CHEMIN]
python -m brvm_alpha suivi saisir --nom MOI --fichier avis.csv | --apport M | --retrait M
python -m brvm_alpha suivi revue --nom MOI --alerte ID --decision garder|ne-plus-acheter|reduire --texte "..."
python -m brvm_alpha suivi declarer --modele | --fichier F --signer INITIALES [--registre --confirmer "J'INSCRIS AU REGISTRE"]
                                                     # dépôt de développement seulement (§F9)
python -m brvm_alpha suivi verifier                  # chaînes de la déclaration et des journaux
python -m brvm_alpha suivi exporter --sortie DOSSIER # copie des journaux, pour un commit aux points d'étape
```

Options ajoutées aux commandes existantes (défaut : comportement actuel) :

| Commande | Option | Défaut | Effet |
|---|---|---|---|
| `recommend`, `report` | `--grille ma_sgi\|central\|FICHIER` | absent (= `--couts`) | F2 |
| `recommend`, `report` | `--perte-toleree MONTANT\|P%` | absent | F4 : ordre de la poche |
| `recommend`, `report` | `--taux-reserve T` | absent | F5 |
| `recommend` | `--arrondi bas\|restes` [`--forcer`] | `bas` | F13c |
| `recommend` | `--apport MONTANT`, `--completer`, `--reinvestir`, `--continuite`, `--suivi NOM` | absents | F13 (`--suivi` seul = règle testée avec mémoire, sans écart) |
| `recommend`, `report` | (aucune option) | — | W9 quand `--portefeuille` est donné sans `--cash` |
| `recommend`, `report` | `--sans-rendement` | absent | n'ajoute pas la clé `rendement_net` (calcul plus court) |

Sans option nouvelle, `recommend` et `report` rendent les mêmes titres, quantités, prix limites, frais et distribution qu'aujourd'hui ; seuls s'ajoutent les blocs d'affichage du §3 (lignes 1 à 4, 15 et 16).

`plan` sans `--capital` reprend le capital du plan enregistré, à défaut 10 000 000 FCFA. `plan --enregistrer` écrit `plan.json` (perte acceptée, taux, besoin).

---

## 7. Interface, rapport, ordre de bataille

### 7.1 Interface (7 pages, `NAV` inchangé)

| Page | Ajout | Routes |
|---|---|---|
| Tableau de bord | Première carte « Mon plan », lue dans `plan_cache.json` : `PH_ETUDE`, `PH_SEANCE` ; décision 1 (cinq champs de la grille, lien « plus de champs », bouton « Voir les 8 questions ») ; décision 2 (table de choix cliquable, champ libre) ; décision 3 (taux de la réserve, placement) ; « si vous ne faites qu'une chose » ; trois feux et lien vers le bulletin | `POST /plan/enregistrer` ; `POST /plan/grille` ; `GET /plan/questions` ; `GET /plan/resultat` |
| Portefeuille | Champs « Ce que j'accepte de risquer sur 12 mois (FCFA) », « Taux net de ma réserve (% par an) », liste « Tarif » (supposé / ma grille) ; cases non cochées « Arrondi "plus forts restes" », « J'apporte de l'argent frais », « Compléter un ordre servi en partie » ; bulletin de la semaine ; formulaire de revue ; saisie d'un avis d'opéré | `POST /suivi/revue` ; `POST /suivi/saisir` ; `GET /suivi/bulletin` |
| Validation | Tableau « Suivi sur papier : ce qui est déclaré » : témoin, essai « avec notes », écarts d'exécution, mesures comptées, date du prochain point d'étape ; phrase `PH_ESSAI` ; aucun classement par rendement avant le point d'étape | — |

Les formulaires suivent le modèle des notes : jeton (`csrf_field`), refus des formulaires périmés, calcul long dans le fil de travail existant. La carte reprend les composants de la maquette en cours (`D/tests/ui_reference_pages.py`). Les trois montants « capital total », « en actions », « en réserve » sont toujours affichés ensemble.

Contraintes des tests existants (`D/tests/test_deploiement_ui.py`) :
- **Aucun formulaire GET nouveau** : l'ensemble des formulaires GET doit rester exactement `/notes`, `/indices`, `/expliquer` (lignes 321-322). `GET /plan/questions`, `GET /plan/resultat` et `GET /suivi/bulletin` sont atteints par des **liens**, jamais par un `<form method="get">`.
- Chaque route nouvelle, GET ou POST, doit avoir un lien ou un formulaire dans une page de référence (lignes 155-162) ; chaque route POST nouvelle doit avoir son formulaire dans une page de `PAGES` (lignes 315-320). Les formulaires nouveaux vivent donc sur des pages déjà listées dans `PAGES` (`/` et `/portefeuille`), et `tests/ui_reference_pages.py` reçoit l'état « avec plan » de ces pages.
- Les empreintes `GOLDEN` changent pour `tableau_de_bord`, `tableau_de_bord_vide`, `tableau_de_bord_notes`, `portefeuille`, `portefeuille_en_cours`, `validation` (et toute page dont le gabarit commun change). Exception déclarée au §9.1.

### 7.2 Rapport HTML (11 sections, `SECTIONS` inchangé)

| Section existante | Sous-bloc ajouté **à la fin** |
|---|---|
| `bandeau` | carte « Mon plan » (version de l'écran) et trois feux ; la section reste `ok` si la carte échoue |
| `ordre` | « Argent qui dort et provision » (F7), graphique des liquidités par mois, « Passer l'ordre » |
| `revenus` | « Du brut au net » (F3), « Frais évités », « Inconnues à lever », « Argent placé en plus » |
| `distribution` | lectures du risque (F6), après le texte existant |
| `risques` | « Ce que j'accepte de risquer » (F4), concentration, bulletin de la semaine (F10), lignes à revoir |
| `methode` | déclaration du suivi S2 (F9), statut des chiffres, limites du module |

Tous les tableaux passent par l'assistant `_table` (bloc `tablewrap`, exigé par un test). Chaque sous-bloc porte `BANNER`.

### 7.3 Ordre de bataille (Markdown, HTML, JSON)

- **Bloc « L'essentiel »** : titre de niveau 3, placé après les avertissements et avant le paragraphe « Décision à la clôture… ». Quatorze lignes au plus, montants au franc : `PH_SEANCE` ; frais de la 1re année et part supposée ou estimée des frais ; le premier geste ; les quatre lignes de la table de choix (ou la ligne retenue), chacune avec ses deux dépassements en FCFA ; `PH_PASSE` et `PH_DESCRIPTIF` ; la valeur d'un point de taux sur la réserve et `PH_INTERETS` ; les trois feux.
- **Table des ordres** : une ligne `PH_NE_PAS_TRANSMETTRE` juste au-dessus, tant que le statut est REJETÉ. Le titre de la table, les quantités et les prix ne changent pas.
- **Section « Rendement net et pertes »** : titre de niveau 2, placé après « Revenus attendus » ; la numérotation se refait seule (`_renumber_sections`). Sous-parties, dans cet ordre : « Du brut au net » ; « Frais évités par rapport au tarif supposé » ; « Inconnues à lever » ; « Ce que j'accepte de risquer » ; « Où dort le reste » ; « Argent qui dort et provision » ; « Argent placé en plus : gain ou perte selon le marché » ; « Passer l'ordre » ; « Points à vérifier » (alertes). Détail ligne par ligne et projection par mois : en fin de section.
- **Section « Exécution »** : une ligne ajoutée (provision à avoir, part investie maximale).
- **Section « Distribution »** : lignes des lectures ajoutées ; libellé réécrit (F6).
- **Liste `avertissements`** : alertes « FUITE : » en fin de liste, trois au plus.
- **JSON** : clé `rendement_net` (§4.5).
- Le Markdown commence toujours par « # Ordre de bataille » ; le premier avertissement reste « PANEL EN RETARD » quand il existe.

---

## 8. Protocole du suivi S2 : ce qui est déclaré avant le 01/12/2026

### 8.1 Ce que le suivi peut montrer, et ce qu'il ne peut pas

À écrire tel quel sur la page Validation.

- **Le suivi ne peut pas prouver la référence par ses gains avant plusieurs années.** Dans son test, l'écart de suivi de REF face au marché était de 4,31 % par an [Fait publié, `metrics.json`, `runs.REF_central_10M.te_tr`]. Neuf fois sur dix, le hasard seul déplace donc son retard cumulé de moins de 5 points à 6 mois, 7 points à 12 mois et 12 points à 36 mois (1,645 × 4,31 % × √durée en années) ; le retard attendu est de 1,7 à 2,6 points par an, plus 1,6 point la première année [Estimation sous hypothèse normale, `M/jury/rigueur/j3_comparaisons.py`, `M/rendement/rapport.md` §6.2].
- **Le suivi vérifie la plomberie** : frais, exécution, argent qui dort, données.
- **Aucun essai ne sera prouvé par ses gains en un an.** Le plus petit avantage visible après un an est de 1,6 à 3,3 points par an pour un seul essai [Estimation : 1,645 × écart de suivi, seuil unilatéral de 5 %, hypothèse normale, avec un écart de suivi de l'essai face au témoin supposé de 1 % à 2 % par an].
- **On ne classe jamais des essais par leur rendement.** Avec trois essais sans avantage réel, la chance qu'au moins un dépasse la référence par hasard est d'au plus 87,5 % ; avec cinq, d'au plus 96,9 % (bornes hautes, essais supposés indépendants ; environ 72 % et 80 % s'ils sont corrélés à 0,6) [Estimation].

### 8.2 Article 1 — La référence : REF-S2, la règle telle qu'elle a été testée

| Élément | Valeur figée | Source |
|---|---|---|
| Sélection et poids | variante REF (D8) : 20 plus grosses capitalisations éligibles, poids proportionnels à la capitalisation, plafonds de D8, 98 % investi | spécification §8.4, YAML `disciplined_index` |
| Calendrier | remise à niveau à la première décision de janvier ; mémoire des positions entre deux ; sorties forcées de la règle (filtres de risque, inéligibilité) | D8 |
| Dividendes | crédités nets à la date de paiement ; gardés en liquidités jusqu'à la remise à niveau | §7.1.6 |
| Arrondi | vers le bas, ligne par ligne | §6 |
| Bande | 2 points par ligne | §6 |
| Exécution | cours moyen du jour suivant si le titre est échangé ; 10 % du volume du jour au plus ; report 10 séances | §7.1 |
| Notes de l'analyste | **aucune** | D11 : aucun rôle dans le test |
| Coûts | scénario `central` | §7.2 |
| Capital | 10 000 000 FCFA | YAML |
| Départ | première décision à la dernière séance ≤ 30/11/2026 ; première exécution à la première séance ≥ 01/12/2026 | YAML `S2_live_from` |
| Code | le moteur du test, plus un seul refus explicite (forfait de compte non nul, §4.3) ; fabrique `suivi.temoin.temoin_model`, sans modification de `runner.py` (§F10) | — |

**Budget de retard, écrit d'avance** [Estimation] : au tarif supposé, REF-S2 devrait faire 3,3 à 4,2 points de moins que le marché la première année (1,7 à 2,6 points par an, plus 1,6 point de frais d'entrée), puis 1,7 à 2,6 points de moins par an. Le bas de la fourchette (1,7 point) suppose la rotation mesurée sur S0 (0,87 % par mois, période contaminée et haussière) ; le haut (2,6 points) suppose la remise à niveau publiée de S1 (1,23 point par an). Ni l'un ni l'autre n'est un test. L'alerte existante de la spécification (retard relatif de 10 %) reste le seul seuil. Aucune conclusion sur la référence avant 36 mois.

**Ce que le suivi vérifie sur la référence** (contrôles « plomberie », lus au point d'étape) :

| N° | Contrôle | Attendu |
|---|---|---|
| P1 | identité comptable de chaque semaine | écart de 0 FCFA |
| P2 | frais payés par poste contre frais prévus par le tarif | égalité sur papier ; écart publié en réel |
| P3 | part investie moyenne | publiée chaque semaine |
| P4 | part des titres servis (test S1 : 80,9 % des ordres) | publiée |
| P5 | ordres déclenchés par un trou de bulletins | chaque cas documenté |
| P6 | coût de la remise à niveau de janvier | comparé à la fourchette de F3 |
| P7 | écart au marché en valeur de part (§F10) | comparé au budget ci-dessus |
| P8 | exécution sur papier en mode `test`, sans écart, contre le moteur | mêmes ordres et mêmes valeurs ; sinon écarts publiés (condition de lecture de E-C et E-D) |

### 8.3 Articles 2 à 4 — Écarts d'exécution non listés par la spécification : des décisions humaines datées

Texte affiché : « Ces écarts ne sont pas jugés sur leurs gains. Leur effet sur le rendement est celui d'être plus ou moins investi : il a le signe du marché. La décision se prend maintenant, par vous. Le suivi vérifie seulement que la règle fait ce qu'elle dit et ne coûte pas plus que prévu. »

Ces trois écarts ne figurent pas parmi les « décisions humaines attendues » de la spécification (§8.5). Chacun est appliqué dans le portefeuille `PLAN`, jamais dans `REF-S2`, et inscrit sous la ligne `S2-PLAN` du registre. Chaque clause de retrait peut échouer.

| Article | Écart | Règle exacte | Ce qu'on compte | Clause de retrait, écrite d'avance | Durée minimale | Proposition |
|---|---|---|---|---|---|---|
| E-L | Ordres à cours limité, exécution sur papier avec test de limite | F12, mode `limite` (plus stricte que le §7.1) | part des titres servis à 1, 3 et 10 séances ; prix payé contre cours moyen du jour et contre dernier cours | aucune : c'est une mesure. Changer la règle des prix limites serait un nouvel article | 12 mois | oui : c'est ce que l'utilisateur ferait |
| E-B | Compléter un ordre servi en partie ; apport hors bande | F13b | part investie après les ordres ; ordres en plus ; frais en plus | retiré si un complément coûte, en frais facturés par franc, plus de deux fois l'ordre d'origine (cas d'un minimum par ordre) | 12 mois | oui |
| E-A | Arrondi « plus forts restes » avec marge de deux trimestres | F13c | francs placés en plus ; marge du pire cas à chaque ordre | retiré si, une seule fois, la provision au prix limite dépasse les liquidités, ou si la grille réelle rend la marge négative | 12 mois | au choix de l'utilisateur |

Une entrée en plusieurs fois (F15), si l'utilisateur l'applique, s'ajoute comme article E-T de même nature.

### 8.4 Articles 5 à 7 — Les essais jugés sur S2 : « N », « E-C », « E-D »

La spécification (§8.5, dernier paragraphe) classe deux questions comme « décisions humaines attendues (non tranchées ici, **nouvel essai à juger sur S2 seulement**) » : (i) le plancher D1 et l'âge des ordres après un trou de bulletins ; (ii) la mise en œuvre du repli D8 (dividendes gardés en liquidités jusqu'au rebalancement annuel). Les options E-C (F13e) et E-D (F13d) y répondent : ce cahier les traite donc **comme des essais**, conformément à ce texte, et non comme de simples décisions d'exécution.

**Option 1 (proposée) : essais déclarés.** Chacun a sa ligne au registre (`S2-EC`, `S2-ED`), son portefeuille « REF-S2 + l'écart seul » (ordres de `recommend --sans-notes --suivi E-C --continuite`, ou `--suivi E-D --reinvestir`, exécutés sur papier en mode `test`, 10 M, tarif supposé ; contrôle P8 du §8.2), son critère écrit d'avance, et compte dans N pour le DSR.

| Article | Essai | Règle exacte | Mesure | Critère écrit d'avance | Compte dans m |
|---|---|---|---|---|---|
| 6 | E-C, continuité des données | REF-S2 + F13e | épisodes de bulletins manquants ; ventes évitées ; titres gardés et leur sort dans les 20 séances suivantes ; `d_t` contre REF-S2, publié | **retenue** dans `PLAN` si aucun titre réellement suspendu ou radié n'a été gardé à tort plus de 20 séances ; **retirée** sinon. Aucune prétention de rendement avant 156 semaines ; à 156 semaines, mêmes conditions que N pour toute affirmation | non tant que son portefeuille est identique au témoin (clone, proposition E5 de la spécification) ; **oui dès son premier écart au témoin** |
| 7 | E-D, réinvestissement mensuel | REF-S2 + F13d | argent qui dort moyen ; ordres par an ; frais par franc réinvesti ; `d_t` contre REF-S2 ; « effet d'exposition » = (part investie de E-D − part investie de REF-S2) × variation du marché, publié | **retirée** au 31/01/2028 si les frais par franc réinvesti dépassent 1,5 fois ceux de l'ordre d'entrée, ou s'il y a plus de 6 ordres par an ; sinon « en cours ». **Confirmée** seulement à 156 semaines ou plus, avec les conditions de N (t ≥ 3,0, p ≤ 0,05 ÷ m, DSR ≥ 0,95) ; sinon « indéterminé » | oui, dès sa déclaration |

**Option 2 : dérogation signée.** Au lot 0, l'humain signe une ligne `derogation` de la déclaration, qui cite le texte du §8.5 de la spécification (« nouvel essai à juger sur S2 seulement ») et décide d'y déroger : E-C et E-D deviennent des décisions d'exécution du §8.3, ne sont pas inscrits au registre, ne comptent ni dans N ni dans m, et le texte affiché du §8.3 s'applique. La page Validation écrit alors « E-C et E-D : dérogation signée le jj/mm/aaaa à la spécification §8.5 ».

Sans signature de l'une ou l'autre option avant le 01/12/2026, E-C et E-D restent **éteints** dans `PLAN`.

#### Article 5 — Le premier essai à prétention de rendement : « N », la référence avec les notes

| Élément | Contenu |
|---|---|
| Règle exacte | REF-S2, plus les notes de l'analyste (veto, filtres de risque, inclinaisons), en règle stricte à la date de décision. Tout le reste est identique |
| Pourquoi | L'ordre par défaut applique les notes. Elles n'ont jamais été testées (D11). Aujourd'hui elles retirent ETIT : 6,16 points de poids [Fait] |
| Mesure principale | `d_t` = rendement hebdomadaire net de N − celui de REF-S2 (semaines finissant le vendredi ; semaines de plus de 6 séances traitées comme en E1 de la spécification) |
| Statistique | t de Newey-West de la moyenne de `d_t` (4 retards) ; intervalle par bootstrap stationnaire (blocs de 8 semaines, 5 000 tirages, graine 0) |
| Durée | aucune lecture de rendement avant 52 semaines ; aucune affirmation avant 156 semaines (§8.1 de la spécification) |
| Décision « notes retirées de l'ordre » | à un point d'étape d'au moins 52 semaines, si t ≤ −2,0, **ou** si le retard cumulé de N sur REF-S2 atteint 3 points. L'ordre revient alors à la règle testée ; les notes restent un journal d'information [seuils : Hypothèse de travail, à valider par l'humain] |
| Décision « notes confirmées » | seulement à 156 semaines ou plus, si t ≥ 3,0 (`min_t.new` du YAML) **et** p unilatérale ≤ 0,05 ÷ m **et** DSR ≥ 0,95 calculé avec tous les essais du registre |
| Sinon | « indéterminé » : rien ne change ; l'écran écrit « les notes n'ont pas fait leurs preuves » |
| Prédiction écrite d'avance | avec un écart de suivi d'environ 1 % par an [Hypothèse] et un avantage réel de 1 point par an, le t attendu après trois ans vaut environ 1,7. « Indéterminé » est donc le résultat le plus probable, même si les notes sont utiles |
| Mesure secondaire, descriptive | pour chaque achat bloqué par une note : rendement du titre contre le marché sur les 60 séances suivantes ; lecture seulement après 30 blocages sur des titres et des périodes qui ne se chevauchent pas ; aucune décision n'en dépend |

### 8.5 Correction pour comparaisons multiples

1. m = nombre d'essais à prétention de rendement inscrits au registre pour S2. Avec l'option 1 du §8.4 : m = 2 au départ (N et E-D), puis 3 dès que E-C s'écarte du témoin. Avec l'option 2 (dérogation signée) : m = 1 (N seul).
2. Seuil unilatéral de 0,05 ÷ m (Bonferroni), **en plus** de t ≥ 3,0.
3. Tout essai ajouté plus tard augmente m pour toutes les décisions à venir. Aucun seuil n'est relâché après coup.
4. Le DSR est calculé avec tous les essais du registre (98 aujourd'hui, plus les trois à cinq lignes S2, E-C et E-D compris avec l'option 1) et la plus grande des deux variances (proposition E4 de la spécification).
5. Un portefeuille identique au témoin tant que rien ne se passe (E-C sans bulletin manquant) est déclaré comme clone : il entre dans N pour le DSR, mais ni dans m ni dans la PBO (proposition E5) tant qu'il reste identique ; dès son premier écart au témoin, il entre dans m pour toutes les décisions à venir.
6. `PLAN` n'est jamais comparé au témoin sur le rendement, seulement sur des faits comptés.
7. Aucun classement par rendement n'est affiché avant un point d'étape.
8. Si l'on tire un jour un essai de la mesure descriptive des notes (par type de note), la famille est corrigée par la méthode de Benjamini-Hochberg-Yekutieli, déjà prévue par le YAML (`haircut.method: bhy`).

### 8.6 Portefeuilles suivis

| Nom | Règle | Taille et tarif | Rôle | Compte dans m |
|---|---|---|---|---|
| `REF-S2` | article 1 | 10 M, tarif supposé | témoin | non |
| `N` | article 5 | 10 M, tarif supposé | essai à prétention de rendement | oui |
| `E-C`, `E-D` | articles 6 et 7 : REF-S2 plus un seul écart (option 1 du §8.4 seulement) | 10 M, tarif supposé | essais jugés sur S2 | E-D oui ; E-C dès son premier écart |
| `PLAN` | **ordre par défaut** (`recommend` sans option, donc avec les notes) **+ mémoire annuelle** (`--suivi`) **+ les écarts déclarés « oui »** (E-L, E-B, E-A, et E-C, E-D s'ils sont déclarés) ; ce n'est pas « ce que fait la commande par défaut », qui n'a pas de mémoire | 10 M, tarif supposé | vérification comptable | non |
| `MOI` | la même règle que `PLAN`, à la taille et à la grille de l'utilisateur ; papier ou réel | montant en actions et grille de l'utilisateur | analyse de sensibilité, pas un essai | non |

### 8.7 Inscription et datation (commande lancée par l'humain)

1. Le développeur copie ce cahier des charges dans `docs/RENDEMENT_NET.md`.
2. `python -m brvm_alpha suivi declarer --modele` écrit le projet de déclaration (articles 1 à 7, propositions des §8.3 et §8.4, options 1 et 2 du §8.4).
3. L'utilisateur répond « oui » ou « non » à chaque écart, et valide ou corrige les seuils marqués « Hypothèse de travail ».
4. Dans le **dépôt de développement** seulement : `python -m brvm_alpha suivi declarer --fichier F --signer INITIALES --registre --confirmer "J'INSCRIS AU REGISTRE"` écrit `reports/suivi_S2/declaration.jsonl` et ajoute trois à cinq lignes à `reports/trials.parquet` (F9). La signature est faite d'initiales ou d'un pseudonyme, jamais du nom complet : le fichier est suivi par git.
5. Un commit contenant `reports/suivi_S2/declaration.jsonl`, `reports/trials.parquet`, `configs/rendement_net.yaml` et `docs/RENDEMENT_NET.md` est fait **avant le 01/12/2026**. Sa date fait foi (proposition E8 de la spécification : empreinte enregistrée dans un commit antérieur).
6. Le code des portefeuilles `N`, `E-C`, `E-D` et `PLAN` peut être écrit après cette date : il doit passer les tests écrits d'après le texte déclaré. Tout détail que le texte ne fixe pas fait l'objet d'un nouvel article, valable pour l'avenir.

### 8.8 Points d'étape

| Date | Ce qu'on lit | Ce qu'on peut décider |
|---|---|---|
| 01/12/2026 | début du suivi sur papier | — |
| chaque semaine | bulletin : trois feux | une revue, jamais une vente automatique |
| 29/01/2027 | remise à niveau de la référence | coût mesuré (P6) |
| 01/06/2027 | comptabilité seulement : P1 à P7, clauses de retrait | retrait d'un écart ; première date possible pour une décision humaine sur l'argent réel (§8.9) |
| 01/12/2027 | première lecture de `d_t` (52 semaines) | retrait éventuel des notes |
| 31/01/2028 | E-D après une saison de dividendes et une remise à niveau | retrait de E-D sur ses critères comptables, ou « en cours » (jamais « confirmé » avant 156 semaines) |
| 01/12/2029 | 156 semaines | première affirmation possible |

Entre deux points d'étape : aucune décision sur une règle, aucun changement sans nouvel article.

### 8.9 Vers l'argent réel : ce que le module affiche, et ce qu'il ne décide pas

Le texte actuel de la spécification exige, pour le statut PROMU, des filtres verts sur S1 **et** sur S2 (§8.3 de la spécification). Tout est rejeté sur S1 : **avec ce texte, rien ne peut être promu, et la plate-forme ne recommandera pas d'argent réel.** Changer ce texte, ou ouvrir un chemin pour une règle née après S1, est une **décision humaine**, que ce module ne prend pas (§13), et que la spécification interdit avant 6 mois de suivi S2 (§8.1).

Le module affiche seulement :
- `PH_SEANCE` (§1.2), rendue à la date du jour, qui ne présente jamais le 01/06/2027 comme une date de feu vert ;
- la liste des conditions **nécessaires, non suffisantes**, proposées pour qu'une telle décision humaine puisse seulement être examinée [Hypothèse de travail] : 26 semaines de journal sans rupture de chaîne ; grille du courtier au statut `grille écrite` ; contrôles P1 à P5 et P8 conformes ; retard de la référence dans son budget ; « ce que j'accepte de risquer », réserve et durée choisis ; un changement écrit de la règle de promotion, daté, avec sa raison ; une décision écrite et signée de l'utilisateur.

Tant que le statut est REJETÉ, toutes les sorties gardent « Étude seulement ». La plate-forme n'émet jamais d'elle-même une recommandation d'argent réel.

### 8.10 Ce qui n'est pas ouvert

Plancher de ligne à 2 % ; panier de 10, 12 ou 15 lignes ; plafond de 15 % par ligne ; calendrier d'achat lié aux détachements ; réserve en francs ; limite d'achat au dernier cours ; variantes A à I. Les ouvrir demanderait un nouvel article, augmenterait m, et ne donnerait aucune réponse lisible avant plusieurs années.

---

## 9. Ce qui ne doit pas changer

| Élément | Règle | Test de garde |
|---|---|---|
| `reports/validation_S1/*`, `reports/diagnostic_S0*` | jamais ouverts en écriture | empreintes des fichiers identiques avant et après chaque commande nouvelle |
| `reports/trials.parquet` | lignes existantes jamais modifiées ; seule `suivi declarer --registre --confirmer` ajoute des lignes | empreinte des 98 premières lignes identique ; aucune autre fonction n'ouvre le fichier en écriture |
| `configs/strategy_v1.yaml` | inchangé | `config_fingerprint` identique ; `tests/test_settings_reference.py` vert |
| Journal des notes (`<données>/notes`) | aucune écriture sans action de l'utilisateur | les tests travaillent dans des dossiers temporaires |
| Panel (`<données>/panel`) | lecture seule | idem |
| Commandes `validate` et `backtest` | non modifiées ; jamais appelées par le module | recherche de texte dans le paquet `rendement` et `suivi` |
| Ordre par défaut de `recommend` et `report` | mêmes titres, quantités, prix limites, frais, distribution, stress, statut ; ajouts d'affichage du §3 seulement | comparaison champ par champ avant et après, à 1 M, 10 M, 50 M |
| Moteur de simulation | non modifié, sauf le refus d'un forfait de compte non nul | un passage court sur le panel de synthèse, comparé à l'identique avant et après |
| Stratégie (`strategy/alpha.py`) | un seul paramètre nommé nouveau, `memoire_ref=None` (§4.3) ; aucun autre changement | suite existante verte ; empreinte de configuration identique |
| `validation/runner.py` | non modifié (`SAMPLES` garde « S1 » et « S0 ») | recherche de texte ; test de la fabrique du témoin (§F10) |
| Suite de tests existante | aucun fichier de test existant modifié, **sauf les trois exceptions du §9.1** | suite complète verte après chaque lot |
| Python 3.11 | tout le code nouveau, tests compris, se compile en Python 3.11 (production sous Odoo 17) : pas de f-string avec barre oblique inverse ni même guillemet dans la partie expression (PEP 701), pas de syntaxe 3.12 (`type X = …`, génériques `def f[T]`) | `tests/test_compat_python311.py` couvre déjà `brvm_alpha/` et `tests/` : il s'applique aux fichiers nouveaux sans changement |
| Rapport HTML | 11 sections, dans le même ordre | `tests/test_report_html.py` |
| Interface | 7 pages, mêmes protections des formulaires | `tests/test_ui.py` |
| Arrondi par défaut | vers le bas | `tests/test_recommend.py` |
| Tête de l'ordre | titre « # Ordre de bataille », bandeau, statut, phrase d'étude ; premier avertissement inchangé | `tests/test_fix_all_product.py`, `tests/test_recette_ordre_rapport.py` |
| Réseau | aucune requête | aucun import de `urllib`, `requests` ni `socket` dans `rendement` et `suivi` |
| Échantillon S1 | aucune règle simulée sur une date ≤ 16/11/2022 | `temoin`, `papier`, `carnet` refusent ces dates |

Exceptions décidées et justifiées dans ce document : l'ajout de trois à cinq lignes au registre (§8.7) ; l'ajout d'un champ à `CostModel`, nul par défaut (§4.3) ; le paramètre `memoire_ref` de `BrvmAlpha`, nul par défaut (§4.3) ; les ajouts d'affichage du §3 ; les trois exceptions de tests du §9.1.

### 9.1 Trois exceptions déclarées aux tests existants

Trois familles de tests existants échouent **par construction** dès que l'interface et la tâche de nuit changent. Elles ne sont pas contournées : elles sont mises à jour, dans un **commit séparé**, relu, dont le message liste les empreintes avant et après. Aucun autre fichier de test existant n'est touché.

| N° | Test existant | Pourquoi il échoue | Changement permis, et seulement celui-là |
|---|---|---|---|
| X1 | `tests/test_deploiement_ui.py`, `GOLDEN` (lignes 36-51) et `test_without_prefix_each_reference_page_is_byte_identical_to_the_previous_release` (lignes 146-152) | la carte « Mon plan », les champs de la page Portefeuille et le tableau de la page Validation changent les octets des pages de référence | relever les empreintes avec `python tests/ui_reference_pages.py` et remplacer les valeurs de `GOLDEN` ; le commentaire au-dessus de `GOLDEN` reçoit le commit de relevé. Les empreintes des pages que le module ne touche pas (`notes`, `notes_en_vigueur`, `fiche_note`, `recherche`, `indices`, `dossier`, `dossier_erreur`, `expliquer`, `erreur_404`) **ne doivent pas changer** : si l'une change, le gabarit commun a été touché par erreur |
| X2 | `tests/ui_reference_pages.py` (couverture des routes, lignes 155-162 de `test_deploiement_ui.py` ; formulaires, lignes 315-322) | chaque route de `GET_ROUTES` et `POST_ROUTES` doit avoir un lien ou un formulaire dans une page de référence | ajouter à `reference_pages()` l'état « avec plan » des pages existantes, avec les liens `/plan/questions`, `/plan/resultat`, `/suivi/bulletin` et les formulaires POST `/plan/enregistrer`, `/plan/grille`, `/suivi/revue`, `/suivi/saisir`. **Aucun formulaire GET nouveau** (§7.1) : l'assertion des lignes 321-322 reste inchangée |
| X3 | `tests/test_deploiement_scripts.py`, listes exactes d'appels de `quotidien.sh` (lignes 225-226 et 236-237) | l'étape `suivi maj` s'ajoute entre `panel` et la suite | ajouter `"suivi maj"` à la place voulue dans les deux listes attendues, et un test nouveau (fichier nouveau) qui vérifie qu'un échec de `suivi maj` n'arrête pas la tâche |

Si l'humain refuse ces exceptions, le lot retire de son contenu les routes nouvelles et l'étape de nuit : la carte « Mon plan » s'affiche alors seulement dans le rapport et la commande `plan`, et `suivi maj` se lance à la main.

---

## 10. Ordre de réalisation

Le suivi commence le mardi 01/12/2026. Ce qui doit exister avant cette date est en gras.

| Lot | Contenu | Échéance | Dépend de | Change une règle ? |
|---|---|---|---|---|
| 0 | **Décisions humaines du §13 (dont : E-C et E-D, option 1 ou 2 du §8.4 ; accord sur les trois exceptions de tests du §9.1 ; initiales de signature) ; envoi des 8 questions au courtier.** Aucun code | 23-24/11/2026 | — | non |
| 1 | F2 (grille), F3 (bilan, leviers), F8 (W1 à W3), clé JSON et section de l'ordre, F4 (table de choix) et F5 par arithmétique, commande `plan` en texte | 27/11/2026 | lot 0 pour les textes | non |
| 2 | **F9 : `docs/RENDEMENT_NET.md`, `configs/rendement_net.yaml`, déclaration signée, inscription au registre, commit.** F10 pour `REF-S2` (semaine 0), avec la fabrique `temoin_model` et son test de non-régression ; tests de garde du §9 | **30/11/2026** | lot 0 | non (protocole) |
| 3 | F6 (lectures, 20 graines), F7 (argent qui dort, provision, « passer l'ordre »), F4 étape 6 (vérification par ordre complet), F1 dans l'interface et le rapport (cache `plan_cache.json`), bulletin dans la tâche de nuit, **commit séparé des exceptions X1 à X3 (§9.1)**, portefeuille `N` | décembre 2026 | lots 1 et 2 | non |
| 4 | F12 (carnet, papier en modes `limite` et `test`, avis d'opéré), F11 (feux, revue), F13 (mémoire `memoire_ref`, compléter, apport, arrondi, réinvestir, continuité), W9, portefeuilles `PLAN`, `MOI`, et `E-C`, `E-D` s'ils sont déclarés, rejoués depuis le 01/12/2026 | avant le 29/01/2027 | lot 2 (règles déclarées) | options, éteintes par défaut |
| 5 | F14, F15, F16 | février 2027 | lot 4 | F15 : écart à déclarer ; F16 : après accord |

Après chaque lot : suite de tests complète, puis régénération des livrables avec `--sortie` hors de `reports/` et comparaison avec les livrables actuels.

Parade au délai court : seul le lot 2 est indispensable avant le 01/12/2026. Les journaux de `N`, `E-C`, `E-D` et `PLAN` se reconstruisent ensuite à partir des bulletins archivés, parce que leurs règles sont déclarées avant.

---

## 11. Tests

**Fichiers nouveaux.** `tests/test_rendement_plan.py`, `test_rendement_grille.py`, `test_rendement_bilan.py`, `test_rendement_perte.py`, `test_rendement_risque.py`, `test_rendement_liquidites.py`, `test_rendement_alertes.py`, `test_rendement_execution.py`, `test_rendement_integration.py`, `test_suivi_declaration.py`, `test_suivi_journal.py`, `test_suivi_carnet.py`, `test_suivi_papier.py`, `test_suivi_feux.py`, `test_suivi_temoin.py`, `test_cli_rendement.py`, `test_ui_rendement.py`, `test_report_rendement.py`, `test_deploiement_suivi.py`. Les trois fichiers existants modifiés sont ceux du §9.1, et seulement eux.

**Quatre familles.**
1. **Unitaires sur panel de synthèse** (toujours lancés) : arithmétique des poches, identités comptables, monotonies, paliers des feux, cas limites, refus des dates de S1.
2. **Recette sur les données du 20/11/2026** (ignorés si le panel est absent, comme les recettes existantes) : les valeurs de contrôle de chaque fonction, au franc sur les clés JSON. Elles reprennent la fenêtre de l'ordre existant et la graine 0 ; elles ne testent aucune règle de stratégie.
3. **Honnêteté** : `BANNER` sur chaque sortie ; `PH_ETUDE` et `PH_SEANCE` sur l'écran, le bulletin et la section ; `PH_PASSE` et `PH_DESCRIPTIF` partout où une fréquence, une médiane ou « une année sur dix » est affichée ; mots interdits absents de l'écran et du bulletin (comptés comme au §1.1) ; « garanti », « sûr », « certain », « sans risque », « plafond » seulement dans une phrase négative ; aucune forme écran ne montre la lecture flatteuse ; aucune sortie ne présente une date comme feu vert pour l'argent réel ; tout chiffre qui dépend du tarif porte « supposé » tant que la grille n'a pas de source ; tout chiffre qui dépend du taux de la réserve porte « supposé » ; aucun montant « placé en plus » dans un tableau de frais évités.
4. **Garde** (§9) : non-régression de l'ordre par défaut, 11 sections, empreintes des fichiers S1 et du registre, aucune alerte ne crée d'ordre, aucune écriture hors des dossiers prévus, aucun réseau, compilation Python 3.11, `runner.py` inchangé, empreintes `GOLDEN` des pages non touchées inchangées.

**Critères d'acceptation par fonction.**

| Fonction | Acceptée si |
|---|---|
| F1 | l'écran tient en 45 lignes, ne contient aucun mot interdit, dit « aucun achat » à la prochaine séance sans promettre de date, montre perte (avec dépassements en FCFA) et gain prudent côte à côte pour chaque choix, porte `PH_PASSE` et `PH_DESCRIPTIF` sous la décision 2 |
| F2 | cinq chiffres saisis donnent la facture en moins d'une seconde ; chaque montant de frais porte son statut ; le défaut de `recommend` est inchangé |
| F3 | les totaux de la plate-forme sont retrouvés à 0 FCFA d'écart ; frais évités et francs placés ne sont jamais dans le même tableau ; la fourchette part de la grille connue |
| F4 | les quatre lignes de la table de choix sont retrouvées avec le choc mesuré ; le taux de la réserve ne change rien ; aucun texte ne décrit une limite ; sans l'option, l'ordre est inchangé |
| F5 | un taux, vide ou saisi, ne change ni A* ni la perte estimée ; un taux saisi porte « supposé » |
| F6 | la première lecture (graine 0) est identique à la distribution de l'ordre ; la fourchette (médianes des 20 graines), `PH_PASSE` et `PH_DESCRIPTIF` sont affichées ; les périodes réelles suivent la règle de `return_distribution` |
| F7 | l'identité des liquidités tient à 0 FCFA ; la part investie maximale est juste à 0,01 point ; l'argent qui dort est expliqué par ses causes |
| F8 | les alertes sonnent à 1 M et 10 M, pas à 50 M ; elles arrivent après les avertissements existants ; la règle testée n'allume jamais « FUITE » ; W7 lit `sessions` |
| F9 | la chaîne détecte toute réécriture ; le registre garde ses 98 lignes intactes ; le commit est antérieur au 01/12/2026 ; aucune donnée personnelle dans le fichier suivi par git |
| F10 | le pont est exact au franc chaque semaine (une seule base) ; l'écart au marché se calcule en valeur de part ; le témoin passe par sa propre fabrique ; le bulletin sort sans commande ; une division d'actions ne crée aucune fausse perte |
| F11 | aucun feu ne crée d'ordre ; un portefeuille qui suit la règle déclarée reste vert ; chaque feu a un état « revue faite » |
| F12 | un ordre sur papier n'est servi que sous sa limite ; un avis d'opéré fait passer les champs de la grille à « avis d'opéré » |
| F13 | sans option, sortie identique ; `--suivi` seul rend les ordres du moteur pour REF ; chaque option porte sa mention ; les valeurs de contrôle sont retrouvées |
| F14 | « jamais » à 1 M ; aucun pourcentage du passé rejoué au-delà de 12 mois |
| F15 | après N tranches aux mêmes cours, quantités = ⌊w × (K − frais déjà payés) ÷ p⌋ ; aucun pourcentage de réussite affiché |
| F16 | le total des dividendes est inchangé ; l'accord écrit existe |

**Valeurs de contrôle principales** (10 M, 20/11/2026, tarif supposé, sauf mention).

| Grandeur | Valeur | Fonction |
|---|---:|---|
| Frais d'achat ; frais annuels ; 1re année | 160 588 ; 124 126 ; 284 714 | F3 |
| Frais et impôt de la 1re année ; années suivantes | 340 241 ; 179 653 | F3 |
| Dividendes moins frais, 1re année ; ensuite ; avec −20 % de dividendes | 151 274 ; 311 862 ; 64 076 | F3 |
| Part supposée ou estimée : facture ; frais seuls ; levée par la grille | 91,5 % (311 289) ; 89,8 % (255 762) ; 215 226 | F3 |
| Remise à niveau estimée | 34 745 à 123 000 | F3 |
| Aller-retour | 321 176 | F3 |
| Grille connue sans frais par ligne : 1re année ; ensuite | 211 490 ; 28 126 | F2 |
| Minimum de 2 500 FCFA par ordre : en une fois ; trois tranches en mode apport | +13 841 ; +109 740 | F2, F15 |
| Chocs par franc investi : marché × sensibilité ; test publié (mesuré) ; pire moment ; 2017-2020 | 0,23975 ; 0,2932 ; 0,31521 ; 0,44607 | F4 |
| Montant en actions pour 500 000 ; 1 000 000 ; 2 000 000 | 1 400 000 ; 3 000 000 ; 6 300 000 | F4 |
| Poche de 3 000 000 : investi ; frais 1re année ; dividendes ; P_vérifiée | 2 807 310 ; 151 702 ; 125 995 ; 974 805 | F4 |
| Idem, grille sans frais par ligne, 500 000 ; 1 000 000 ; 2 000 000 acceptés | 1 700 000 ; 3 400 000 ; 6 600 000 | F4 |
| Taux de réserve de 3 %, 1 000 000 accepté | 3 000 000 (inchangé) ; intérêts affichés à part 210 000 | F5 |
| Périodes en perte : blocs de 8, 26, 52 semaines (graine 0 ; médiane des 20 graines) | 25,6 % ; 30,0 % ; 31,8 % (25,5 % ; 30,6 % ; 32,8 %) | F6 |
| Une année sur dix : blocs de 8, 26, 52 ; périodes réelles | −9,9 % ; −14,8 % ; −16,4 % ; −19,45 % | F6 |
| Marché chargé des mêmes frais, blocs de 8 : perte ; ordinaire ; une sur dix (graine 0) | 34,1 % ; +6,6 % ; −13,1 % | F6 |
| Marché chargé des mêmes frais, blocs de 52 : perte (graine 0 ; médiane des 20) | 38,1 % ; 39,6 % | F6 |
| Périodes réelles en perte (12 mois) | 37 sur 107 (± 1) ; par année de départ 12, 12, 10, 1, 0, 2 | F6 |
| Provision du pire cas ; marge ; marge à +0,2 point (50 M) | 9 866 731 ; 133 269 ; −11 697 | F7 |
| Part investie maximale | 97,81 % | F7 |
| Réserve de fonctionnement (3 trimestres) : 1 M ; 10 M ; 50 M | 76 625 ; 93 095 ; 166 505 | F7 |
| Argent qui dort moyen, février 2027 à janvier 2028 | 388 420 (260 923 avec E-D) | F7, F13 |
| Frais annuels sur dividendes nets : 1 M ; 10 M ; 50 M | 265,7 % ; 28,5 % ; 10,1 % | F8 |
| Arrondi « plus forts restes » : 1 M ; 10 M ; 50 M ; marge à 10 M avec un courtage de 1,5 % | +61 025 ; +65 485 ; 0 ; −14 720 | F13 |
| Trois apports de 3 333 333 : avec `--apport` ; sans option (liquidités réelles) | 9 556 525 investis ; 7 368 680 investis et 2 514 330 de liquidités | F13, F15 |
| Amortissement d'un achat-revente : 10 M ; poche de 3 000 000 ; poche de 3 400 000 avec la grille sans frais par ligne | 12,4 mois ; 56,5 mois ; 10,7 mois | F14 |

---

## 12. Ce qui est écarté, et pourquoi

| Idée | Raison |
|---|---|
| Promettre un gain, un capital « protégé », une perte impossible | Faux. Le marché a perdu 46,7 % de mars 2017 à octobre 2020 [Fait] |
| Vente automatique sous un seuil ; assurance de portefeuille ; rééquilibrage automatique entre réserve et actions | Interdit par la spécification (§9.1) ou règle de sortie jamais testée ; sous des bornes de ±7,5 %, on vend au plus bas, souvent sans être servi ; chaque aller-retour coûte 3,33 % |
| Activer une variante A à I ; capturer le dividende ; doser par le régime de marché | Rejetées sur S1 (7,6 à 9,7 points de moins par an que le marché) ; la capture coûte 3,2 % d'aller-retour pour un effet brut de 2,9 % en déclin |
| Régler l'entrée sur le PER, la largeur du marché ou l'avis sur les indices | Indicateurs jamais validés comme signaux |
| Règle « part en actions ≤ perte tolérée ÷ 23 % » | Oublie les frais : dépassement de 14 à 63 % [Fait de calcul, `M/jury/rigueur/j4_budget.py`] |
| Choisir la part en actions par interpolation sur quatre lectures ; option « prudence renforcée » | Complexité sans effet : la même lecture décidait toujours. Une seule règle, la plus sévère des deux estimations de 2018 |
| Garder le choc de 2018 « 0,278 » tiré de frais supposés de 3,0 % à 3,9 % | Ces frais sont la moyenne de tout S1 (frais d'entrée de 2017 et aller-retour de 2021 compris) ; ceux de 2018 publiés font 0,65 %. Avec le choc mesuré (0,2932), les poches de 1,5 M, 3,2 M et 6,6 M dépassaient le montant accepté de 12 908, 41 526 et 59 495 FCFA [`F/f2_poches.py`] |
| Déduire les intérêts de la réserve de la perte estimée | Un taux saisi sans preuve gonflerait le montant en actions : pour 500 000 FCFA acceptés, 1 400 000 à 0 %, 2 200 000 à 3 %, 3 500 000 à 10 %, 4 300 000 à 15 % ; pour 1 000 000, 3 700 000 à 3 % et 4 100 000 à 5,5 %. Les intérêts ne sont pas acquis au moment d'une baisse, et le placement d'attente peut lui-même perdre [Hypothèse (taux), `F/f2_poches.py`] |
| Afficher « 144 633 puis 110 475 FCFA » ou « 130 158 » comme économie attendue | Tarifs qu'aucune grille lue n'offre ; addition à la main. La fourchette part de la grille connue |
| Mots « certain », « gagné à coup sûr », « perdu à coup sûr », « perte maximale », option `--perte-max` | Promesses implicites sur un tarif supposé ou sur une estimation |
| Placer la limite d'achat au dernier cours ou au meilleur prix demandé | Aucun gain mesuré ; plutôt un surcoût de 3 921 à 51 070 FCFA pour 9,65 M ; ordre servi le lendemain dans au moins 65 % des cas au lieu de 94 % [Estimation, S0 contaminé]. À mesurer par E-L |
| Choisir les titres selon l'impôt sur les dividendes | Règle de sélection nouvelle, jamais testée ; l'impôt (55 527 FCFA par an à 10 M) est retenu à la source |
| Resserrer à 10, 12 ou 15 lignes ; plancher de ligne à 2 % | Règle de sélection nouvelle ; économie nulle si le courtier ne facture pas par ligne ; la spécification refuse moins de 12 lignes |
| Plafond de 15 % ou 20 % par ligne | Règle de pondération nouvelle ; ne réduit pas la volatilité mesurée ; porte les banques de 41 % à 51 % |
| Réserve en francs au lieu de 2 % | Change un paramètre figé ; un essai de plus pour quelques milliers de FCFA par an. La réserve de fonctionnement est affichée, pas appliquée |
| Calendrier d'achat lié aux détachements | 5 000 à 11 000 FCFA par an au plus ; non mesurable sur S2 |
| Programme en nombres entiers pour l'arrondi | 2 000 FCFA de mieux à 10 M, et il éloigne les poids des cibles |
| Découpe en tranches figée au premier jour ; « l'étalement fait mieux dans X % des cas » | Les cours bougent entre les tranches ; le pourcentage ne reflète que la hausse du passé rejoué |
| Critères d'adoption « part investie plus proche de 98 % », « retard pas pire de 2 points » | Acquis par construction : ils ne peuvent pas rejeter une mauvaise règle |
| Registre S2 séparé du registre des essais | Sous-compterait le nombre d'essais |
| Chiffrer par défaut le rendement de la réserve | Aucune donnée vérifiée. Champ saisi par l'utilisateur, étiqueté « supposé » |
| Donner une fréquence de perte à 24 ou 36 mois | Les périodes se recouvrent presque toutes (4 périodes de 24 mois sans chevauchement en 119 fins de mois) : règle fixe, aucun pourcentage, sans calcul de seuil |
| Part « marché / titre » de chaque ligne (sensibilité supposée de 1) | Aucune action en FCFA pour l'utilisateur |
| Douzième section du rapport, huitième page de l'interface | Un test compte 11 sections ; l'écran va en tête de ce qui existe |
| Alertes à −5 % sous l'argent engagé, à −15 % ou −20 % depuis le plus haut | Sonnent sans cesse : 44 % des années ; 9,1 et 5,7 lignes par an |
| Afficher sur l'écran l'« année ordinaire » du passé rejoué | Elle rejoue les gagnants d'aujourd'hui et flatte ; le seul test réel publié dit −5,6 points par an contre le marché. L'écran montre la lecture prudente ; la flatteuse reste au détail, étiquetée |
| Présenter le 01/06/2027 comme « première date possible pour engager de l'argent réel » | Avec les règles actuelles, rien ne peut être promu (spécification §8.3) ; la date n'est qu'un plancher pour une décision humaine de changer ces règles (`PH_SEANCE`) |
| Appeler « FUITE » l'argent que la règle testée garde jusqu'à janvier | C'est le comportement testé ; le changer est l'essai E-D, jugé sur S2. W4 n'appelle « FUITE » que l'argent qui dort hors de la règle |
| Alertes par courriel ou SMS ; connexion au courtier | Aucun réseau dans le module |
| Relancer S1 avec des règles corrigées ; régler une règle ou un seuil sur S0 | Interdit par le protocole |
| Exemples d'écran ou de test tirés d'une date choisie après coup (achat au plus haut du 14/09/2026) | Ils mettent une fonction en valeur ; les tests se font sur un panel de synthèse |

---

## 13. Questions ouvertes : décisions humaines à prendre

À trancher avant le 01/12/2026 (lot 0) :

1. **Les notes dans l'ordre.** Garder l'ordre par défaut « avec notes » pendant le suivi (proposition de ce document, défaut actuel), ou revenir à la règle testée « sans notes » ?
2. **Écarts d'exécution (§8.3).** Oui ou non pour chacun : E-L, E-B (proposés « oui ») ; E-A (au choix).
3. **E-C et E-D (§8.4) : essais ou dérogation.** Option 1 (proposée, conforme au §8.5 de la spécification) : les déclarer comme essais jugés sur S2, avec leurs portefeuilles et leurs critères ; m passe à 2 (puis 3 si E-C s'écarte du témoin), ce qui durcit le seuil de N. Option 2 : signer une dérogation explicite au §8.5, en citant son texte. Sans signature, E-C et E-D restent éteints. Pour E-D : le déclarer, ou non (c'est choisir d'être plus exposé de mai à janvier).
3 bis. **Seuils de l'article 5.** Retrait des notes à t ≤ −2,0 ou à 3 points de retard cumulé : à valider ou à corriger.
3 ter. **Les trois exceptions de tests du §9.1** : accord, ou retrait des routes nouvelles et de l'étape de nuit.
3 quater. **Signature** : initiales ou pseudonyme à employer (jamais le nom complet, le fichier est suivi par git).
4. **Grille du courtier.** Envoyer les 8 questions. Quel courtier : l'actuel, ou un courtier sans frais par ligne ? Un changement après l'achat coûterait 5 000 à 34 375 FCFA par ligne, soit 100 000 à 687 500 FCFA pour 20 lignes [Fait, grilles lues].
5. **Statut de l'investisseur.** Personne physique résidente ? De quel pays ? Tout le module le suppose.
6. **Ce que j'accepte de risquer**, **taux de la réserve**, **durée** : ou « pas encore ».

À trancher plus tard :

7. **Chemin vers l'argent réel** pour une règle née après S1 (§8.9), et conventions statistiques de S2 proposées par la spécification (E4, E5, E8).
8. **Seuils des feux** (§4.4) : tous sont des propositions sans base statistique.
9. **Correction de la date de paiement projetée** (F16) : accord écrit demandé, parce qu'elle change une date affichée par défaut.
10. **Impôt sur les plus-values, taxe sur le courtage, taxe sur les frais annuels** : à faire confirmer par le courtier ou un fiscaliste ; non vérifiés.
11. **Taux et sûreté du placement d'attente** : aucune donnée dans le dépôt ; hors du champ de la plate-forme.
12. **Comparaison avec l'alternative simple** (ne pas investir, ou un fonds actions de la place) : l'étalon « médiane des fonds » prévu par la spécification n'est pas disponible dans les données.

---

## 14. Registre des chiffres clés

| Affirmation | Valeur | Statut | Méthode | Preuve |
|---|---|---|---|---|
| Frais et impôt de la 1re année à 10 M, tarif supposé | 340 241 FCFA | Hypothèse (tarif) ; calcul exact | somme des postes de l'ordre ; écart 0 FCFA avec la plate-forme | `S/s1_bilan.py` |
| Part supposée ou estimée de cette facture | 91,5 % (311 289 FCFA) ; 89,8 % des seuls frais (255 762 sur 284 714) ; dont 215 226 FCFA levés par la grille écrite | Fait de calcul | règle du statut le plus faible ; seules BRVM et DC/BR sont des faits | `F/f7_divers.py` |
| Écart avec la grille connue sans frais par ligne | −73 224 FCFA la 1re année ; −96 000 par an ensuite | Hypothèse (tarif) | frais recalculés avec les fonctions de l'outil | `S/s5_reserve_leviers.py` |
| Borne non attestée | −130 158 ; −96 000 | Hypothèse | idem | idem |
| Dividendes moins frais si les dividendes baissent de 20 % | +64 076 FCFA la 1re année | Estimation | N × 0,8 − frais | `S/s1_bilan.py` |
| Choc de 2018 par franc investi : marché × sensibilité | 0,23975 | Estimation | stress ST2 de l'ordre ÷ investi | `F/f2_poches.py` |
| Choc de 2018 subi par la règle dans son test | 0,2932 (méthodes approchées : 0,290 à 0,304) | Estimation (lecture d'un résultat publié, pas un test) | rendement TR 2018 de la partie investie de REF_central_10M, positions publiées, poids de la veille ; contrôles : VL −25,74 %, part investie 82,5 %, frais de transaction 2018 : 61 077 FCFA | `F/f1_sref.py` |
| Montant en actions pour 500 000 ; 1 000 000 ; 2 000 000 FCFA acceptés | 1 400 000 ; 3 000 000 ; 6 300 000 FCFA (grille sans frais par ligne : 1 700 000 ; 3 400 000 ; 6 600 000) | Estimation | règle du §F4 ; ordres exacts recalculés, quantités identiques | `F/f2_poches.py` ; `F/f2b_ordres.py` ; `F/reco/reco_3000000.json` |
| Perte d'une année comme 2018 pour la poche de 3 000 000 | 827 267 à 974 805 FCFA | Estimation | stress de l'ordre exact ; 0,2932 × investi ; frais compris | `F/f2b_ordres.py` |
| Pire moment de 2018 et baisse de 2017-2020 pour cette poche | 1 039 895 et 1 408 629 FCFA (les deux dépassent 1 000 000) | Estimation | stress ST2 intra-annuel et ST1 de l'ordre exact + frais | `F/f2b_ordres.py` |
| Prix de cette prudence (1 000 000 acceptés) | 546 187 FCFA d'une année ordinaire, lecture prudente (915 950 en lecture flatteuse, au détail seulement) | Estimation, descriptif | médianes, poche contre tout en actions | `F/f2_poches.py` |
| Valeur d'un point de taux sur la réserve | 70 000 FCFA par an (100 000 pendant l'étude) ; jamais déduite de la perte estimée | Fait arithmétique | réserve × 1 % | `F/f2_poches.py` |
| Périodes de 12 mois en perte | environ 26 % à 40 % selon la lecture et le tirage (médianes de 20 graines : 25,5 % à 39,6 %) ; 37 sur 107 observées | Estimation descriptive | bootstrap (blocs de 8, 26, 52 semaines), marché chargé des mêmes frais, périodes réelles (règle de `return_distribution`) | `F/f4_graines.py` ; `F/f3_periodes.py` |
| Une année sur dix | −9,9 % à −19,45 % selon la lecture | Estimation descriptive | idem | idem |
| Durée sous le plus haut de 2017 | 59 mois avec les dividendes (Composite TR) ; 95 mois sans (Composite prix, −57,9 %) | Fait descriptif | niveaux du panel | `F/f6_indices.py` |
| Arrondi « plus forts restes » à 10 M | +65 485 FCFA placés ; marge du pire cas 66 323 (−14 720 avec un courtage de 1,5 %) | Fait | algorithme du §F13c ; 36 combinaisons contrôlées | `M/liquidites/scripts/a_arrondis.py` ; `F/f7_divers.py` |
| Argent qui dort avec la règle testée | 388 420 FCFA en moyenne de février 2027 à janvier 2028 (260 923 avec le réinvestissement corrigé) | Estimation | simulation à cours constants | `M/liquidites/scripts/c_dividendes.py` ; `F/f8_reinvestir.py` |
| Entrée en trois tranches | `--apport` : 9 556 525 FCFA investis ; outil actuel avec liquidités réelles : 7 368 680 investis, 2 514 330 de liquidités | Estimation (option) ; Fait (outil) | règle F13b ; commandes `recommend --portefeuille --cash` | `F/f5_tranches.py` ; `Rv/echelon/` |
| Service partiel non complété par l'outil | 469 430 FCFA jamais rachetés ; 92,6 % investi | Fait (outil) ; Hypothèse (scénario) | commande `recommend` relancée sur le portefeuille servi en partie | `M/jury/marche/j3_sortie.txt` |
| Bruit sur le retard de la référence | neuf fois sur dix, moins de 5 points à 6 mois, 7 à 12 mois, 12 à 36 mois | Estimation | écart de suivi publié de 4,31 % par an × 1,645 × √durée, hypothèse normale | `M/jury/rigueur/j3_comparaisons.py` |
| Retard de REF dans son test (sans les notes) | −5,6 points par an ; écart de suivi 4,31 % ; taux d'exécution 80,9 % | Fait publié | lecture des résultats S1 | `D/reports/validation_S1/resultats.md`, `metrics.json` |
| Épisode du trou de bulletins de 2021 | 314 040 FCFA de frais (55 ordres, août à octobre 2021) ; 52 séances sans bulletin du 08/01 au 11/10/2021 | Fait publié | somme de `cost` des ordres REF_central_10M ; table `sessions` | `D/reports/validation_S1/trades.parquet` ; `D/data/panel/sessions.parquet` |

---

## 15. Reproduire les contrôles de ce document

**Version finale (fait foi)** : scripts de `F/`, chacun en moins de 3 secondes, sortie dans `F/fN_sortie.txt`.

```
cd <mesures>/final
python3 -B f1_sref.py                                     # choc 2018 de REF mesuré sur les fichiers S1 publiés
PYTHONDONTWRITEBYTECODE=1 python3 -B f2_poches.py         # table de choix, grille FGI, sensibilité, taux de réserve
python3 -B f2b_ordres.py                                  # poches retenues contre les ordres exacts
python3 -B f3_periodes.py                                 # périodes réelles de 12, 24, 36 mois (règle de l'outil)
python3 -B f4_graines.py                                  # lectures du risque, graines 0 à 19
PYTHONDONTWRITEBYTECODE=1 python3 -B f5_tranches.py       # entrée en trois tranches, minimum par ordre, seuil E-D
PYTHONDONTWRITEBYTECODE=1 python3 -B f6_indices.py        # 59 et 95 mois sous le plus haut, années (descriptif)
PYTHONDONTWRITEBYTECODE=1 python3 -B f7_divers.py         # part supposée, R_n, marges au franc
python3 -B f8_reinvestir.py                               # projection des liquidités, réinvestissement corrigé
python3 maquette/fabrique.py                              # maquette de F1 : 44 lignes, 100 colonnes au plus
```

Ordres exacts (sorties hors dépôt, environ 11 secondes chacun, commit `d256e26`) :

```
cd <dépôt>
for K in 10000000 3000000 1400000 6300000 1000000 50000000; do
  PYTHONDONTWRITEBYTECODE=1 python -B -m brvm_alpha recommend --capital $K --format json --sans-indices \
    --sortie <mesures>/final/reco/reco_$K.json
done
```

`f1_sref.py`, `f3_periodes.py` lisent seulement les fichiers publiés et le panel. `f2_poches.py`, `f5_tranches.py`, `f7_divers.py` importent le paquet en lecture seule, sans cache de bytecode, pour employer `order_costs`, `participation_schedule`, `_worst_case` et `round_fcfa`. `f4_graines.py` et `f2_poches.py` emploient la copie du générateur de l'outil (`M/pertes/commun.py`). `f6_indices.py` reprend `Ra/r4_faits_indices.py` ; `f8_reinvestir.py` reprend `Rv/c4_liquidites.py` avec la règle F13d corrigée. Les scripts de `S/` reproduisent la version précédente (choc 0,278) et ne font plus foi pour la table de choix. Aucune écriture dans le dépôt. Aucune commande `validate` ni `backtest`. Aucune règle testée sur une date de S1 : les lectures de S1 sont des lectures de résultats publiés. Aucune requête réseau.

**Limites de ce document.** Les mesures des quatre rapports d'origine n'ont pas toutes été relancées : les valeurs de l'arrondi « plus forts restes » et de la projection des liquidités viennent de la mesure « liquidités », contrôlées par la contre-expertise (`Rv/c4_sortie.txt`) et, pour les marges, par `F/f7_divers.py`. Les options `--suivi`, `--completer`, `--apport`, `--continuite` n'ont pas de prototype dans le paquet : leurs contrôles sont fixés par les tests et par les scripts de `F/`. Un autre agent modifie le dépôt : les valeurs de recette sont celles du commit `d256e26` et sont à recalculer après stabilisation.

---

## 16. Contre-expertise : ce qui n'est pas retenu, et pourquoi

| Proposition de la contre-expertise | Décision | Raison |
|---|---|---|
| Retenir pour le choc de 2018 « le haut de la fourchette » : 0,304 si l'on ne retire que les frais de transaction (protocole, K1) | **Non retenu** ; 0,2932 retenu, 0,304 affiché en sensibilité (1 000 000 → 2 900 000) | 0,304 attribue au choc les droits de garde et la tenue de compte de 2018, et divise une perte annuelle par une part investie moyenne : c'est une approximation. La mesure directe (rendement TR de la partie investie, poids de la veille) est la définition même d'un choc « par franc investi, hors frais », et la contre-expertise « chiffres » l'a obtenue indépendamment (0,2932). Le dimensionnement garde la règle `max(s_beta ; s_ref)` |
| Garder « 77 % » avec un libellé « part qui dépend d'un tarif ou d'une exécution non vérifiés » (chiffres, K4, première option) | **Non retenu** | Deux pourcentages proches pour la même facture embrouilleraient un non-spécialiste. Le cahier applique sa propre règle de statut (91,5 %) et montre, au franc, ce qui peut lever chaque part (grille, exécution, taux d'impôt, dividendes estimés) : l'information des 77 % reste lisible (215 226 + 40 536 + 7 081 = 262 843) |
| Calculer les cibles de `--apport` sur l'argent engagé K moins la réserve de 2 % (protocole, mineur sur F13b, première option) | **Non retenu** ; seconde option retenue (cibles sur V réel, recette ⌊w × (K − frais déjà payés) ÷ p⌋) | Viser K ferait acheter avec de l'argent déjà parti en frais : la provision se calculerait sur des francs qui n'existent plus, exactement le défaut relevé par K2. V réel est ce que le carnet contient |
| Renommer le titre de la table des ordres « Ordres (étude : ne pas transmettre) » (protocole, textes, point 4) | **Retenu en partie** : ligne `PH_NE_PAS_TRANSMETTRE` ajoutée au-dessus de la table, titre inchangé | Le titre « 2. Ordres (au titre et au franc près) » (`recommend.py`, ligne 1393) est le repère de la section dans les livrables et leur documentation ; aucun test ne le lit, mais le §9 demande de ne changer que l'affichage ajouté. Une ligne placée juste au-dessus de la table donne le même message, aussi visible, et disparaît avec le statut REJETÉ |
| Retirer du lot les routes nouvelles et l'étape de nuit plutôt que modifier trois tests (protocole, K10, seconde option) | **Gardé comme repli** si l'humain refuse les exceptions (§9.1) | L'écran, le bulletin sans commande et la tâche de nuit sont le cœur de la demande (« aucune perte ne doit devenir une fuite » sans commande à taper) ; les exceptions sont étroites, listées, et vérifiables par empreintes |
| Paramètre public de mémoire **ou** rejeu des décisions depuis janvier (protocole, K13) | **Paramètre public retenu** (`memoire_ref`) | L'état de REF entre deux décisions se réduit à `{année, date}` (`_reference_portfolio`) ; le rejeu demanderait les exécutions de toute l'année et un calcul long pour redonner le même état |
| Faire signer une dérogation au §8.5 au lieu de compter E-C et E-D comme essais (protocole, K14, seconde option) | **Proposée comme option 2**, pas comme défaut | Le défaut doit suivre le texte de la spécification ; la dérogation reste possible, signée et datée, au lot 0 |
| Plafonner le taux de réserve à un taux documenté (protocole, K18, première option) | **Non retenu** ; option plus simple retenue : les intérêts ne sont jamais déduits | Aucun taux documenté n'existe dans le dépôt ; ne jamais déduire supprime le problème sans seuil à justifier |
| Écrire « environ 26 % à 41 % » (chiffres, K5, seconde option) | **Non retenu** ; médiane de 20 graines retenue (« environ 26 % à 40 % ») | Une médiane sur 20 graines est reproductible et moins sensible au tirage qu'un maximum ; le maximum (40,9 %) reste dans le JSON |
| Donner la formule exacte des « périodes indépendantes » (chiffres, mineur, première option) | **Non retenu** ; règle sans calcul retenue | Une formule au bord du seuil (4,9 ou 5,0) changerait le sens de la règle ; l'interdiction fixe à 24 et 36 mois dit la même chose sans seuil |

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
