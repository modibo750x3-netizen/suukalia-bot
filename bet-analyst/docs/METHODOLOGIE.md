# Methodologie

Notes de reference sur les choix statistiques du moteur, et sur ce qu'ils
impliquent en pratique.

## 1. De la cote a la probabilite

Une cote decimale `o` correspond a une probabilite implicite `1/o`, **marge
incluse**. La somme sur les trois issues d'un 1X2 vaut typiquement 1.04 a 1.08.

### Multiplicatif

`p_i = (1/o_i) / somme(1/o_j)`

Suppose que le bookmaker applique une marge proportionnelle a la probabilite.
C'est empiriquement faux : la marge est plus lourde sur les outsiders. La
methode leur attribue donc trop de probabilite, ce qui fabrique des value bets
fantomes sur les grosses cotes — precisement la ou le parieur amateur est deja
le plus attire.

### Power

Cherche `k` tel que `somme(p_i^k) = 1`. Corrige une partie du biais
favori/outsider.

### Shin (1993) — methode par defaut

Modelise la marge comme la reponse du bookmaker a la presence de parieurs
informes, de proportion `z`. L'inversion se resout numeriquement en `z` :

```
p_i = [ sqrt(z² + 4(1-z)·pi_i²/B) - z ] / [ 2(1-z) ]     avec B = somme(pi_i)
```

`z` est aussi un indicateur utile en soi : un `z` eleve signale un marche que le
bookmaker juge risque, ou les edges apparents sont plus souvent illusoires.

## 2. Consensus de marche

Chaque bookmaker est deviggue separement, puis agrege avec un poids qui
combine :

- **la reputation** — Pinnacle, Betfair et Smarkets pesent 2 a 3 fois plus. Ils
  acceptent les gros volumes et ajustent vite ; leur ligne est plus proche du
  vrai prix ;
- **la marge** — un bookmaker a marge elevee est peu informatif, son poids est
  divise par `1 + 10 x marge`.

Deux garde-fous de fiabilite :

- **nombre de books** (defaut : 3 minimum) ;
- **dispersion** (defaut : 0.06 maximum). Une forte dispersion signifie que les
  books n'ont pas la meme information — blessure, compo de derniere minute. Le
  "value bet" apparent est alors le plus souvent un book qui n'a pas encore mis
  a jour sa ligne : il refusera le pari ou limitera la mise.

## 3. Modele Dixon-Coles

### Structure

```
lambda (buts domicile) = base x attaque_dom x defense_ext x avantage_terrain
mu     (buts exterieur) = base x attaque_ext x defense_dom
```

### Correction des petits scores

Un Poisson independant sous-estime 0-0 et 1-1, sur-estime 1-0 et 0-1. Ces
quatre scores representent environ un quart des matchs ; l'erreur se voit
directement sur le marche du nul et sur les Under. Dixon-Coles applique un
facteur `tau` sur ces quatre cellules, parametre par `rho`.

### Ponderation temporelle

Poids `exp(-xi x jours)`, avec `xi = 0.0065` par defaut, soit une demi-vie
d'environ 107 jours. Une saison de plus de deux ans ne decrit plus le meme
effectif.

### Ajustement

Point fixe **sequentiel** (Gauss-Seidel) sur la vraisemblance de Poisson
ponderee : attaques, puis defenses, puis avantage du terrain, puis niveau
general de buts. Chaque bloc utilise les valeurs deja rafraichies des
precedents.

Ce detail n'est pas cosmetique. Une premiere version mettait tous les blocs a
jour **simultanement** (Jacobi) : le modele oscillait en divergeant — les
defenses explosaient pendant que l'avantage du terrain s'effondrait, jusqu'a
produire des probabilites degenerees. Le modele s'ajustait "sans erreur" tout en
n'estimant rien. Deux contraintes d'identification (moyenne des attaques = 1,
moyenne des defenses = 1) et la mise a jour sequentielle rendent l'iteration
stable. Un test de non-regression verrouille ce comportement.

## 4. Melange modele / marche

Pooling logarithmique (moyenne geometrique ponderee), preferee a la moyenne
arithmetique : elle est *externally bayesian* et ne peut pas produire, sur une
issue, une probabilite superieure a toutes les sources.

Poids par defaut : **marche 65%, Dixon-Coles 25%, Elo 10%**. Descendre le poids
du marche sous 50% revient a parier que l'on est mieux informe que l'ensemble
du marche — a ne faire qu'avec un backtest qui le demontre.

Quand la confiance dans le modele baisse (equipes peu vues), son poids retourne
au marche, puis le resultat est ramene **vers le marche** — jamais vers
l'uniforme. Retrecir vers l'uniforme gonflerait la probabilite des gros
outsiders et fabriquerait des edges fantomes exactement la ou ils coutent le
plus cher.

## 5. Origine de l'edge

Deux edges de meme taille ne se valent pas :

- **edge de marche** : un bookmaker est hors du consensus des autres. Ne
  suppose rien d'autre que "les autres books ont raison". Mise a pleine taille.
- **edge de modele** : le consensus paie le prix juste, mais le modele estime
  une autre probabilite. Suppose que l'on sait mieux que le marche entier.
  Parfois vrai, souvent non. Mise reduite de moitie.

Le moteur mesure la part de chaque origine et dimensionne entre les deux.

## 6. Dimensionnement

Kelly : `f* = (p x b - q) / b`, avec `b = cote - 1`.

Kelly plein maximise la croissance logarithmique **a probabilites exactes**.
Elles ne le sont jamais. Avec `p` reel de 0.52 mise comme 0.55 a la cote 2.00 :

| Fraction | Croissance logarithmique |
|---|---|
| Kelly plein | -0.00101 |
| Quart de Kelly | +0.00069 |

Le Kelly plein detruit la bankroll malgre un edge reel positif. Le quart de
Kelly sacrifie environ un quart de la croissance theorique contre une reduction
massive du risque de ruine.

Deux details de mise en oeuvre qui comptent sur petite bankroll :

- la mise est comparee au minimum du bookmaker **avant** arrondi. Arrondir
  0.83 EUR a 1.00 EUR pour atteindre le minimum, c'est miser 20% de plus que ce
  que Kelly autorise ; sur une petite bankroll ce biais s'applique a presque
  chaque pari et suffit a annuler l'edge ;
- l'arrondi se fait **vers le bas**. La mise calculee est un plafond, pas un
  objectif.

## 7. Mesurer : le CLV avant le P&L

Le P&L sur quelques centaines de paris est domine par la variance. Avec un edge
reel de +3% sur 200 paris, environ un tiers des trajectoires finit perdante.

Le **CLV** (Closing Line Value) mesure de combien la cote prise bat la cote de
cloture : `cote_prise / cote_cloture - 1`. La cote de cloture est le meilleur
estimateur public de la vraie probabilite. La battre regulierement est la
preuve la plus rapide qu'une methode a de la valeur.

- CLV positif, P&L negatif : la methode est bonne, il faut du volume.
- CLV negatif, P&L positif : c'est de la chance, elle ne durera pas.

Sous 50 paris, le signe du CLV n'est pas encore interpretable ; l'outil refuse
de conclure.

## References

- Dixon, M. & Coles, S. (1997). *Modelling Association Football Scores and
  Inefficiencies in the Football Betting Market*. Applied Statistics 46(2).
- Shin, H. S. (1993). *Measuring the Incidence of Insider Trading in a Market
  for State-Contingent Claims*. The Economic Journal 103(420).
- Kelly, J. L. (1956). *A New Interpretation of Information Rate*. Bell System
  Technical Journal 35(4).
- Davidson, R. R. (1970). *On Extending the Bradley-Terry Model to Accommodate
  Ties*. JASA 65(329).
