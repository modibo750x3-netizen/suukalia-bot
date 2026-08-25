"""Les limites de risque sont la derniere ligne de defense : elles doivent tenir."""

from __future__ import annotations

import pytest

from suukalia.staking.bankroll import BankrollManager, BankrollState, RiskLimits


def state(current: float, peak: float | None = None, **kwargs) -> BankrollState:
    return BankrollState(starting=200.0, current=current, peak=peak or current, **kwargs)


def test_drawdown_et_roi():
    s = state(150.0, peak=250.0)
    assert s.drawdown == pytest.approx(0.40)
    assert s.profit == pytest.approx(-50.0)
    assert s.roi == pytest.approx(-0.25)


def test_trading_autorise_au_depart():
    allowed, _ = BankrollManager(state(200.0)).is_trading_allowed()
    assert allowed


def test_arret_sur_drawdown_severe():
    manager = BankrollManager(state(120.0, peak=200.0))  # -40%
    allowed, reason = manager.is_trading_allowed()
    assert not allowed and "drawdown" in reason


def test_arret_sous_le_plancher_de_bankroll():
    allowed, reason = BankrollManager(state(15.0)).is_trading_allowed()
    assert not allowed and "plancher" in reason


def test_arret_au_plafond_de_paris_quotidien():
    manager = BankrollManager(state(200.0, bets_today=8))
    allowed, reason = manager.is_trading_allowed()
    assert not allowed and "paris/jour" in reason


def test_frein_progressif_sur_drawdown():
    """Entre le seuil de frein (15%) et l'arret (35%), la mise decroit."""
    sain = BankrollManager(state(200.0, peak=200.0)).risk_multiplier()
    modere = BankrollManager(state(150.0, peak=200.0)).risk_multiplier()   # -25%
    severe = BankrollManager(state(135.0, peak=200.0)).risk_multiplier()   # -32.5%
    assert sain == pytest.approx(1.0)
    assert 0.0 < severe < modere < sain


def test_le_frein_integre_la_confiance():
    manager = BankrollManager(state(200.0))
    assert manager.risk_multiplier(confidence=0.5) == pytest.approx(
        manager.risk_multiplier(confidence=1.0) * 0.5
    )


def test_l_exposition_engagee_reduit_le_frein():
    limits = RiskLimits(max_open_exposure_pct=0.10)
    vide = BankrollManager(state(200.0), limits).risk_multiplier()
    charge = BankrollManager(state(200.0, open_exposure=10.0), limits).risk_multiplier()
    assert charge == pytest.approx(vide * 0.5)


def test_plafond_d_exposition_est_une_borne_dure():
    """Meme demande enorme, on ne depasse jamais l'exposition maximale."""
    limits = RiskLimits(max_stake_pct=0.50, max_open_exposure_pct=0.12)
    manager = BankrollManager(state(200.0, open_exposure=20.0), limits)
    # Budget total 24 EUR, deja 20 engages -> 4 EUR disponibles au maximum.
    assert manager.cap_stake(100.0) == pytest.approx(4.0)


def test_budget_d_exposition_restant():
    limits = RiskLimits(max_open_exposure_pct=0.10)
    manager = BankrollManager(state(200.0, open_exposure=12.0), limits)
    assert manager.remaining_exposure() == pytest.approx(8.0)
    manager.register(8.0)
    assert manager.remaining_exposure() == pytest.approx(0.0)


def test_exposition_saturee_bloque_toute_mise():
    limits = RiskLimits(max_open_exposure_pct=0.10)
    manager = BankrollManager(state(200.0, open_exposure=20.0), limits)
    assert manager.cap_stake(5.0) == 0.0
    assert manager.risk_multiplier() == pytest.approx(0.0)


def test_cycle_pari_gagnant():
    manager = BankrollManager(state(200.0))
    manager.register(10.0)
    assert manager.state.open_exposure == pytest.approx(10.0)
    manager.settle(stake=10.0, payout=25.0)
    assert manager.state.current == pytest.approx(215.0)
    assert manager.state.peak == pytest.approx(215.0)
    assert manager.state.open_exposure == pytest.approx(0.0)


def test_cycle_pari_perdant_met_a_jour_le_drawdown():
    manager = BankrollManager(state(200.0))
    manager.register(10.0)
    manager.settle(stake=10.0, payout=0.0)
    assert manager.state.current == pytest.approx(190.0)
    assert manager.state.peak == pytest.approx(200.0)
    assert manager.state.drawdown == pytest.approx(0.05)


def test_serie_de_pertes_declenche_l_arret():
    """Scenario realiste : la serie noire doit stopper le bot, pas le ruiner."""
    manager = BankrollManager(state(200.0))
    for _ in range(40):
        if not manager.is_trading_allowed()[0]:
            break
        stake = manager.cap_stake(manager.state.current * 0.02)
        manager.register(stake)
        manager.settle(stake=stake, payout=0.0)
    assert not manager.is_trading_allowed()[0]
    # L'arret intervient largement avant la ruine.
    assert manager.state.current > 100.0
