"""Le grand livre est la source de verite : il ne doit jamais mentir."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from suukalia.models import BetTicket, Market
from suukalia.storage.db import Ledger


@pytest.fixture
def ledger(tmp_path) -> Ledger:
    ledger = Ledger(tmp_path / "test.sqlite3")
    ledger.set_starting_bankroll(200.0)
    return ledger


def ticket(match_id: str = "m1", selection: str = "HOME", stake: float = 10.0) -> BetTicket:
    return BetTicket(
        match_id=match_id, label="Alpha - Echo", league="TEST",
        kickoff=datetime(2026, 9, 1, tzinfo=timezone.utc), market=Market.ONE_X_TWO,
        selection=selection, bookmaker="winamax", odds=2.50, fair_odds=2.20,
        probability=0.4545, edge=0.136, expected_value=1.36, stake=stake,
        kelly_fraction=0.02, confidence=0.9,
    )


def test_enregistrement_et_etat(ledger):
    assert ledger.record(ticket()) is True
    state = ledger.state()
    assert state.current == pytest.approx(200.0)   # rien de solde
    assert state.open_exposure == pytest.approx(10.0)
    assert state.bets_today == 1


def test_doublon_refuse(ledger):
    """Relancer le moteur deux fois ne doit jamais doubler une position."""
    assert ledger.record(ticket()) is True
    assert ledger.record(ticket()) is False
    assert len(ledger.open_bets()) == 1


def test_meme_match_issue_differente_accepte(ledger):
    assert ledger.record(ticket(selection="HOME")) is True
    assert ledger.record(ticket(selection="AWAY")) is True


def test_solde_gagnant(ledger):
    ledger.record(ticket(stake=10.0))
    bet_id = ledger.open_bets()[0]["id"]
    assert ledger.settle(bet_id, won=True, closing_odds=2.30) is True
    state = ledger.state()
    assert state.current == pytest.approx(215.0)   # 10 mises -> 25 rendus
    assert state.open_exposure == pytest.approx(0.0)
    assert state.settled_bets == 1


def test_solde_perdant(ledger):
    ledger.record(ticket(stake=10.0))
    ledger.settle(ledger.open_bets()[0]["id"], won=False)
    assert ledger.state().current == pytest.approx(190.0)


def test_match_annule_rembourse_la_mise(ledger):
    ledger.record(ticket(stake=10.0))
    ledger.settle(ledger.open_bets()[0]["id"], won=False, void=True)
    assert ledger.state().current == pytest.approx(200.0)


def test_solder_deux_fois_est_refuse(ledger):
    ledger.record(ticket())
    bet_id = ledger.open_bets()[0]["id"]
    assert ledger.settle(bet_id, won=True) is True
    assert ledger.settle(bet_id, won=True) is False


def test_solder_un_pari_inexistant_est_refuse(ledger):
    assert ledger.settle(999, won=True) is False


def test_le_pic_est_rejoue_dans_l_ordre(ledger):
    """Le drawdown doit refleter la trajectoire, pas seulement l'ecart final.

    Gain puis perte : la bankroll finit a son point de depart, mais elle est
    passee par 230 EUR. Le drawdown reel est de 13%, pas de 0%.
    """
    ledger.record(ticket(match_id="a", stake=20.0))            # gagne : +30
    ledger.settle(ledger.open_bets()[0]["id"], won=True)
    ledger.record(ticket(match_id="b", stake=30.0))            # perdu : -30
    ledger.settle(ledger.open_bets()[0]["id"], won=False)
    state = ledger.state()
    assert state.current == pytest.approx(200.0)
    assert state.peak == pytest.approx(230.0)
    assert state.drawdown == pytest.approx(30.0 / 230.0, rel=1e-6)


def test_bankroll_de_depart_persiste(tmp_path):
    path = tmp_path / "persist.sqlite3"
    Ledger(path).set_starting_bankroll(350.0)
    assert Ledger(path).starting_bankroll() == pytest.approx(350.0)
