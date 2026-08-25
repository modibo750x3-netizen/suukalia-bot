"""Le dimensionnement est ce qui separe une strategie viable d'une ruine."""

from __future__ import annotations

import pytest

from suukalia.staking.kelly import KellyConfig, growth_rate, kelly_fraction, stake_for


def test_formule_de_kelly_valeur_de_reference():
    # p=0.55, cote 2.00 -> f* = (0.55*1 - 0.45)/1 = 0.10
    assert kelly_fraction(0.55, 2.00) == pytest.approx(0.10)


def test_pas_de_mise_sans_avantage():
    assert kelly_fraction(0.50, 2.00) == 0.0
    assert kelly_fraction(0.40, 2.00) == 0.0
    assert kelly_fraction(0.90, 1.00) == 0.0


def test_kelly_croit_avec_l_avantage():
    assert kelly_fraction(0.60, 2.00) > kelly_fraction(0.55, 2.00)


def test_plafond_de_mise_respecte():
    """Meme un edge enorme ne doit jamais depasser le plafond par pari."""
    config = KellyConfig(fraction=1.0, max_stake_pct=0.02, min_stake=0.5)
    stake, fraction = stake_for(0.90, 3.00, 1000.0, config)
    assert fraction <= 0.02
    assert stake <= 20.0


def test_mise_sous_le_minimum_est_annulee():
    """Un edge minuscule sur une petite bankroll ne produit pas de ticket."""
    stake, fraction = stake_for(0.505, 2.00, 50.0, KellyConfig(min_stake=1.0))
    assert stake == 0.0 and fraction == 0.0


def test_le_frein_de_risque_reduit_la_mise():
    """Edge modere choisi a dessein : a fort edge les deux mises butent sur le
    plafond de 2% et le frein devient invisible."""
    plein, _ = stake_for(0.53, 2.00, 1000.0, risk_multiplier=1.0)
    freine, _ = stake_for(0.53, 2.00, 1000.0, risk_multiplier=0.5)
    assert 0.0 < freine < plein
    assert freine == pytest.approx(plein * 0.5, rel=0.05)


def test_le_plafond_prime_sur_le_frein():
    """Le plafond par pari est une borne dure : il s'applique apres le frein."""
    config = KellyConfig(max_stake_pct=0.02, round_to=0.0)
    stake, fraction = stake_for(0.60, 2.00, 1000.0, config, risk_multiplier=1.0)
    assert fraction == pytest.approx(0.02)
    assert stake == pytest.approx(20.0)


def test_kelly_plein_devient_perdant_si_la_proba_est_surestimee():
    """Le resultat central qui justifie le quart de Kelly.

    On mise comme si p valait 0.55 alors qu'en verite p = 0.52. En Kelly plein
    la croissance logarithmique devient negative : la bankroll tend vers zero
    malgre un edge reel positif. Au quart de Kelly, elle reste positive.
    """
    misplaced = kelly_fraction(0.55, 2.00)      # 0.10, calculee sur une proba fausse
    assert growth_rate(0.52, 2.00, misplaced) < 0.0
    assert growth_rate(0.52, 2.00, misplaced * 0.25) > 0.0


def test_croissance_nulle_hors_domaine():
    assert growth_rate(0.6, 2.0, 1.0) == 0.0
    assert growth_rate(0.6, 1.0, 0.1) == 0.0
