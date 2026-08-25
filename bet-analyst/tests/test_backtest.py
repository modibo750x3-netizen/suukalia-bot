"""Backtest walk-forward et simulation de risque."""

from __future__ import annotations

import pytest

from suukalia.backtest import simulate_bankroll, walk_forward
from suukalia.staking.kelly import KellyConfig


def test_walk_forward_bat_l_uniforme(synthetic_history):
    """Le modele doit apporter de l'information hors echantillon.

    Test le plus important du fichier : il valide la chaine complete
    (ajustement + melange) sur des matchs jamais vus a l'entrainement.
    """
    report = walk_forward(synthetic_history[:800], train_size=300, step=100)
    assert report.predictions > 0
    assert report.log_loss < report.baseline_log_loss
    assert report.skill > 0.02


def test_walk_forward_ne_predit_jamais_le_passe(synthetic_history):
    """Le nombre de predictions correspond exactement aux matchs post-fenetre."""
    report = walk_forward(synthetic_history[:500], train_size=300, step=100)
    assert report.predictions == 200


def test_walk_forward_sans_donnees_suffisantes():
    assert walk_forward([], train_size=200).predictions == 0


def test_rendu_du_rapport_de_backtest(synthetic_history):
    report = walk_forward(synthetic_history[:600], train_size=400, step=200)
    texte = report.render()
    assert "Log-loss" in texte and "Calibration" in texte


# ------------------------------------------------------- simulation de risque
def test_edge_positif_donne_une_mediane_gagnante():
    simulation = simulate_bankroll(200.0, bets=300, edge=0.05, odds=2.10, trials=800)
    assert simulation.percentile(0.50) > 200.0


def test_edge_nul_ne_fait_pas_croitre_la_bankroll():
    """Sans avantage reel, aucune methode de mise ne cree de profit."""
    simulation = simulate_bankroll(200.0, bets=300, edge=0.0, odds=2.10, trials=800)
    assert simulation.percentile(0.50) <= 200.5


def test_kelly_refuse_de_miser_sans_avantage():
    """Avec un edge negatif, Kelly ne mise rien : la bankroll est intacte."""
    simulation = simulate_bankroll(200.0, bets=400, edge=-0.05, odds=2.10, trials=200)
    assert simulation.percentile(0.50) == pytest.approx(200.0)
    assert simulation.ruin_rate == 0.0


def test_mise_a_plat_a_la_marge_du_book_detruit_la_bankroll():
    """Le scenario du parieur moyen, simule honnetement.

    Miser 2% de bankroll a plat en subissant la marge du bookmaker (-5% d'edge)
    n'est pas neutre : c'est une perte quasi certaine a l'echelle de quelques
    centaines de paris. C'est le comportement par defaut de la quasi-totalite
    des parieurs, et la raison pour laquelle ce projet detecte l'edge AVANT de
    dimensionner la mise.
    """
    simulation = simulate_bankroll(
        200.0, bets=400, edge=-0.05, odds=2.10, flat_fraction=0.02, trials=800
    )
    assert simulation.percentile(0.50) < 150.0
    perdantes = sum(1 for f in simulation.finals if f < 200.0) / len(simulation.finals)
    assert perdantes > 0.85


def test_kelly_plein_amplifie_le_risque():
    """Meme edge, meme nombre de paris : seule la taille de mise change.

    Le Kelly plein offre une mediane plus haute mais un drawdown bien pire.
    C'est l'arbitrage que le quart de Kelly resout en faveur de la survie.
    """
    prudent = simulate_bankroll(
        200.0, bets=300, edge=0.04, odds=2.10,
        kelly=KellyConfig(fraction=0.25, max_stake_pct=0.02), trials=800, seed=7,
    )
    agressif = simulate_bankroll(
        200.0, bets=300, edge=0.04, odds=2.10,
        kelly=KellyConfig(fraction=1.0, max_stake_pct=0.25), trials=800, seed=7,
    )
    assert agressif.percentile(0.05) < prudent.percentile(0.05)
    import statistics

    assert statistics.median(agressif.max_drawdowns) > statistics.median(prudent.max_drawdowns)


def test_variance_domine_sur_petit_echantillon():
    """Verite inconfortable a garder sous les yeux.

    Avec un edge REEL de +3%, une part importante des trajectoires de 200 paris
    finit quand meme perdante. Un bilan negatif sur quelques centaines de paris
    ne prouve donc pas que la methode est mauvaise -- ni un bilan positif
    qu'elle est bonne.
    """
    simulation = simulate_bankroll(200.0, bets=200, edge=0.03, odds=2.10, trials=1500)
    perdantes = sum(1 for f in simulation.finals if f < 200.0) / len(simulation.finals)
    assert 0.20 < perdantes < 0.50


def test_rendu_de_simulation():
    texte = simulate_bankroll(200.0, bets=100, trials=200).render()
    assert "Risque de ruine" in texte and "Mediane" in texte


def test_percentiles_ordonnes():
    simulation = simulate_bankroll(200.0, bets=150, trials=500)
    assert (
        simulation.percentile(0.05)
        <= simulation.percentile(0.50)
        <= simulation.percentile(0.95)
    )
