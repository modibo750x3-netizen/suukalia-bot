# Suukalia Bet Analyst

Moteur d'analyse quantitative pour paris sportifs football : retrait de la marge
des bookmakers, modelisation Dixon-Coles + Elo, detection de value bets,
dimensionnement de Kelly fractionne et gestion de bankroll.

**Zero dependance a l'execution** — uniquement la bibliotheque standard Python.

---

## Avertissement, a lire en premier

Ce projet n'est pas une machine a gagner. Il repose sur trois constats mesures,
pas sur des promesses :

1. **La marge du bookmaker est structurelle.** Sur un 1X2 elle vaut 4 a 8%.
   Un parieur sans avantage reel perd cette marge, mecaniquement. La commande
   `suukalia simulate --edge -0.05 --flat 0.02` le montre : partant de 200 EUR
   sur 400 paris, la mediane finit autour de 123 EUR et **88% des trajectoires
   sont perdantes**.

2. **Un avantage reel reste petit et lent.** Avec un edge authentique de +3%,
   300 paris depuis 200 EUR donnent une mediane d'environ 210 EUR — et **un
   tiers des trajectoires perd quand meme de l'argent**. La variance domine
   l'edge en dessous de plusieurs centaines de paris.

3. **Une bankroll de 200 EUR est une contrainte forte.** Au quart de Kelly, un
   edge de 3.34% sur une cote a 2.71 donne une mise de 0.98 EUR — sous la mise
   minimale des bookmakers. Le moteur n'emet alors aucun ticket, et c'est
   volontaire : arrondir vers le haut pour "atteindre le minimum" revient a
   miser plus que ce que Kelly autorise, sur presque chaque pari, ce qui suffit
   a annuler l'edge. Concretement, 200 EUR servent surtout a **roder la methode
   et a mesurer son CLV** ; les mises deviennent significatives a partir de
   quelques centaines d'euros.

Ce que l'outil fait reellement bien : **mesurer**. Ou est l'edge, quelle taille
de mise il justifie, et si la selection bat la cote de cloture. Le reste est
de la patience.

---

## Installation

```bash
git clone <url-du-depot>
cd suukalia-bet-analyst
pip install -e ".[dev]"        # `-e .` seul suffit pour l'usage courant
```

Python 3.10 ou superieur. Aucune dependance a l'execution.

## Demarrage rapide (hors-ligne, sans cle API)

```bash
suukalia init --bankroll 200          # cree le grand livre SQLite
suukalia analyse -v                   # analyse le jeu de cotes de demonstration
suukalia backtest                     # qualite predictive hors echantillon
suukalia simulate --edge 0.03         # risque de ruine et croissance attendue
```

Sur les donnees de demonstration, avec une bankroll de 200 EUR :

```
------------------------------------------------------------------------------
BANKROLL    200.00 EUR   (depart 200.00 | P&L +0.00 | ROI +0.0% | drawdown 0.0%)
------------------------------------------------------------------------------

Aucun pari retenu. C'est le resultat le plus frequent, et c'est normal :
un marche efficient ne laisse pas d'edge tous les jours.

6 matchs analyses, 0 paris retenus, 0.00 EUR engages
```

Le moteur a pourtant bien trouve une opportunite — mais au quart de Kelly elle
vaut 0.98 EUR, sous la mise minimale des bookmakers. La meme analyse sur une
bankroll de 500 EUR :

```
MATCH                          PARI     COTE   JUSTE    EDGE    MISE BOOK
------------------------------------------------------------------------------
Rennes - Monaco                AWAY     2.71    2.62 +3.34%   2.00e winamax
------------------------------------------------------------------------------
TOTAL                                                          2.00e   EV +0.07 EUR

Matchs ecartes :
  - Paris SG - Lyon         mise calculee trop faible (0.00 EUR)
  - Marseille - Nice        desaccord modele/marche 20.4% au-dela de 15%
  - Lille - Metz            aucun edge suffisant
  - Lens - Nantes           aucun edge suffisant
  - Brest - Clermont        aucun edge suffisant
```

Deux choses a retenir de cette sortie. D'abord **la taille reelle des mises** :
2 EUR sur 500 EUR de bankroll pour un edge de 3.34%, avec une esperance de gain
de 7 centimes. C'est a cette echelle que travaille un parieur discipline.
Ensuite, **les rejets sont affiches et expliques** : savoir pourquoi un match est
ecarte vaut autant que la recommandation elle-meme, et c'est ce qui permet de
reperer un fournisseur casse plutot qu'un marche simplement calme.

## Passage en donnees reelles

```bash
cp .env.example .env       # puis renseigner SUUKALIA_ODDS_API_KEY
set -a && source .env && set +a
suukalia analyse --live --record --notify
```

Cle gratuite sur [the-odds-api.com](https://the-odds-api.com) (500 requetes par
mois). Une requete couvre **tous** les matchs d'un championnat : un run quotidien
sur 6 championnats coute environ 180 requetes par mois. Ne jamais boucler par
match.

---

## Comment ca marche

```
cotes brutes de N bookmakers
   |
   +-- devig            retrait de la marge, methode de Shin      analysis/devig.py
   +-- consensus        agregation ponderee, sharp books en tete  analysis/consensus.py
   +-- modele           Dixon-Coles + Elo                         modelling/
   +-- melange          pooling logarithmique, marche prioritaire modelling/ensemble.py
   +-- filtres          liquidite, dispersion, desaccord          engine.py
   +-- value            p x cote - 1 > seuil                      analysis/value.py
   +-- Kelly bride      quart de Kelly, plafonds, freins          staking/
   |
   v
tickets dimensionnes + grand livre SQLite
```

### 1. Devigging — une cote n'est pas une probabilite

Somme des probabilites implicites d'un 1X2 : environ 1.05. La facon de
redistribuer ces 5% change le classement des value bets, surtout sur les
outsiders. Trois methodes sont implementees ; **Shin** est la valeur par defaut
car elle corrige le biais favori/outsider que la methode multiplicative ignore.

| Cotes 1.50 / 4.20 / 6.50 | HOME | DRAW | AWAY |
|---|---|---|---|
| Multiplicatif | 0.6298 | 0.2249 | 0.1453 |
| Shin | 0.6427 | 0.2201 | 0.1372 |

L'ecart sur l'outsider parait minime : 0.1453 contre 0.1372. A une cote de 6.50,
il represente pourtant **5.3 points d'edge apparent** (-5.5% contre -10.8%). De
quoi faire passer pour une "value bet" un pari nettement perdant — c'est
exactement l'erreur que commet la methode multiplicative sur chaque outsider.

### 2. Le marche est le prior, pas le concurrent

Un modele entraine sur quelques centaines de matchs ne bat pas la ligne de
cloture de Pinnacle. Le poids par defaut du marche dans le melange est de
**65%**. L'edge vient d'un bookmaker qui s'ecarte du consensus des autres, pas
d'une intuition du modele.

Deux verrous :

- si le modele manque de donnees, son poids retombe vers le marche ;
- si le desaccord modele/marche depasse 15%, le match est rejete — un tel ecart
  est presque toujours un mauvais appariement d'equipes ou une cote perimee.

Le moteur distingue d'ailleurs les deux origines d'un edge : un edge **de
marche** (un book hors consensus) est mise a pleine taille, un edge **de modele**
a taille reduite de moitie.

### 3. Modele Dixon-Coles

Poisson bivarie avec correction des petits scores (les 0-0 et 1-1 sont
sous-estimes par un Poisson independant) et ponderation temporelle
exponentielle. Ajustement par point fixe sequentiel, sans dependance externe.

Sur donnees synthetiques a verite terrain connue (3000 matchs), le modele
retrouve les parametres :

| Parametre | Vrai | Estime |
|---|---|---|
| Avantage du terrain | 1.300 | 1.296 |
| Niveau de buts | 1.393 | 1.391 |
| Attaque (5 equipes) | — | a 2% pres |
| Defense (5 equipes) | — | a 2% pres |

Backtest walk-forward sur l'historique fourni (`suukalia backtest`, 412
predictions hors echantillon) :

```
Log-loss              0.9819   (reference uniforme 1.0986)
Score de Brier        0.5831
Taux de bonne issue   53.9%
Apport d'information  +10.63%
```

La calibration est quasi diagonale : ce qui est annonce dans la tranche 60-70%
se realise 62% du temps. Un modele bien calibre vaut mieux qu'un modele
souvent "juste" : c'est la calibration, pas le taux de bonne issue, qui
determine si un edge calcule est reel.

### 4. Quart de Kelly, et pourquoi pas Kelly plein

Le Kelly plein maximise la croissance **si les probabilites sont exactes**.
Elles ne le sont jamais. Surestimer p de 3 points suffit a rendre le Kelly plein
perdant :

| Mise (p reel 0.52, misee comme 0.55, cote 2.00) | Croissance log |
|---|---|
| Kelly plein | **-0.00101** |
| Quart de Kelly | **+0.00069** |

On echange environ un quart de la croissance theorique contre une reduction
massive du risque de ruine. Ce comportement est verrouille par un test.

### 5. Limites de risque

| Limite | Defaut | Raison |
|---|---|---|
| Mise par pari | 2% | ~50 pertes consecutives avant la ruine |
| Exposition simultanee | 12% | les resultats d'un week-end sont correles |
| Paris par jour | 8 | evite le sur-trading sur marches bruyants |
| Frein a partir de | 15% de drawdown | reduit la taille sans tout arreter |
| Arret complet a | 35% de drawdown | c'est le modele qu'il faut revoir |

## Suivre la performance : le CLV avant le P&L

```bash
suukalia bets                          # paris ouverts
suukalia settle 1 --won --closing 2.45 # solder en notant la cote de cloture
suukalia perf                          # bilan
```

Le P&L sur 200 paris ne dit presque rien : la variance domine. Le **CLV**
(Closing Line Value) mesure de combien la cote prise bat la cote de cloture, et
converge bien plus vite.

- CLV moyen positif = la selection a de la valeur, meme si le P&L est encore negatif.
- CLV negatif avec un P&L positif = de la chance, et elle ne durera pas.

Renseigner `--closing` a chaque reglement est le geste le plus rentable de tout
le workflow. En dessous de 50 paris, l'outil refuse d'interpreter le signe du
CLV.

## Commandes

| Commande | Role |
|---|---|
| `suukalia init --bankroll 200` | initialise le grand livre SQLite |
| `suukalia analyse [--live] [--record] [-v]` | cherche les value bets |
| `suukalia bets` | liste les paris ouverts |
| `suukalia settle <id> --won\|--lost\|--void [--closing X]` | solde un pari |
| `suukalia perf` | bilan : yield, drawdown, CLV |
| `suukalia backtest [--train N] [--step N]` | qualite predictive hors echantillon |
| `suukalia simulate [--edge X] [--flat F]` | risque de ruine et croissance |

## Automatisation

```cron
# Tous les jours a 10h00 : analyse, enregistrement, notification Telegram
0 10 * * * cd /chemin/suukalia-bet-analyst && \
  set -a && . ./.env && set +a && \
  .venv/bin/suukalia analyse --live --record --notify >> logs/daily.log 2>&1
```

## Structure

```
src/suukalia/
  mathx.py            primitives numeriques (Poisson, pooling, scores)
  models.py           objets du domaine
  config.py           configuration JSON + variables d'environnement
  analysis/
    devig.py          retrait de marge : multiplicatif, power, Shin
    consensus.py      agregation multi-bookmakers, meilleure cote
    value.py          edge, EV, closing line value
  modelling/
    dixon_coles.py    Poisson bivarie + correction petits scores
    elo.py            Elo avec marge de victoire et modele de Davidson
    ensemble.py       pooling logarithmique modele/marche
  staking/
    kelly.py          Kelly fractionne, plafonds, croissance logarithmique
    bankroll.py       limites de risque, freins, drawdown
  providers/          the-odds-api, CSV historique, cotes locales
  storage/db.py       grand livre SQLite
  engine.py           orchestration
  backtest.py         walk-forward + Monte-Carlo de bankroll
  report.py           rendu console et Telegram
  cli.py              interface en ligne de commande
```

## Developpement

```bash
pytest              # 113 tests
ruff check src tests
```

Les tests ne se contentent pas de verifier que le code s'execute : les modeles
sont ajustes sur des donnees synthetiques a **verite terrain connue** et doivent
retrouver les parametres generateurs. Un modele qui tourne sans planter mais
n'estime rien est un modele casse.

## Limites connues

- **Football uniquement.** Le modele Dixon-Coles suppose des scores de type
  Poisson ; il ne se transpose pas au tennis ni au basket.
- **Marche 1X2 uniquement** cote moteur. Over/Under et BTTS sont modelises mais
  pas encore branches sur la detection de value.
- **Pas de placement automatique de paris.** L'outil recommande et enregistre ;
  la mise est passee a la main. C'est un choix : la plupart des bookmakers
  interdisent l'automatisation et limitent les comptes gagnants.
- **Les comptes gagnants sont limites.** C'est le vrai plafond du scaling, bien
  avant le modele : un parieur regulierement gagnant voit ses mises maximales
  reduites, parfois a quelques euros.
- **Pas d'appariement d'alias d'equipes** entre fournisseurs. `normalise_team`
  gere la typographie, pas "PSG" contre "Paris Saint-Germain".

## Licence

MIT.

## Jeu responsable

Ne miser que de l'argent dont la perte est supportable. En France, aide et
auto-exclusion : **09 74 75 13 13** (appel non surtaxe) ou
[joueurs-info-service.fr](https://www.joueurs-info-service.fr).
