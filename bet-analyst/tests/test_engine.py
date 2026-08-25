"""Tests d'integration du moteur : de la cote brute au ticket dimensionne."""

from __future__ import annotations

import pytest

from suukalia.config import Settings
from suukalia.engine import BettingEngine
from suukalia.models import BookmakerQuote, Market
from suukalia.staking.bankroll import BankrollManager, BankrollState, RiskLimits

BANKROLL_EUR = 1000.0


@pytest.fixture
def bankroll() -> BankrollManager:
    """Bankroll de 1000 EUR pour les tests de logique.

    A 200 EUR, le quart de Kelly sur un edge realiste tombe sous la mise
    minimale des bookmakers et aucun ticket n'est emis -- comportement correct,
    teste separement, mais qui masquerait la logique testee ici.
    """
    return BankrollManager(
        BankrollState(starting=BANKROLL_EUR, current=BANKROLL_EUR, peak=BANKROLL_EUR)
    )


@pytest.fixture
def settings() -> Settings:
    # Desactive le garde-fou de desaccord : les tests fournissent leurs propres
    # cotes, sans modele entraine derriere.
    return Settings(max_disagreement=1.0)


def test_marche_efficient_ne_produit_aucun_ticket(
    settings, bankroll, match_factory, balanced_quotes
):
    engine = BettingEngine(settings, bankroll)
    report = engine.analyse([match_factory(balanced_quotes)])
    assert report.tickets == []
    assert report.matches_analysed == 1
    assert any("edge" in r.reason for r in report.rejections)


def test_book_decale_produit_un_ticket(settings, bankroll, match_factory, value_quotes):
    engine = BettingEngine(settings, bankroll)
    report = engine.analyse([match_factory(value_quotes)])
    assert len(report.tickets) == 1
    ticket = report.tickets[0]
    assert ticket.selection == "AWAY"
    assert ticket.bookmaker == "betclic"
    assert ticket.odds == 4.60
    assert ticket.stake > 0
    assert ticket.edge >= settings.min_edge
    # Edge purement de marche (un book hors consensus) : pleine confiance.
    assert ticket.confidence == pytest.approx(1.0)


def test_un_seul_ticket_par_match(settings, bankroll, match_factory, value_quotes):
    """Deux issues du meme 1X2 sont anti-correlees : Kelly ne sait pas les cumuler."""
    report = BettingEngine(settings, bankroll).analyse([match_factory(value_quotes)])
    assert len({t.match_id for t in report.tickets}) == len(report.tickets)


def test_mise_bornee_par_le_plafond_unitaire(settings, bankroll, match_factory, value_quotes):
    report = BettingEngine(settings, bankroll).analyse([match_factory(value_quotes)])
    assert report.total_stake <= BANKROLL_EUR * settings.limits.max_stake_pct + 1e-9


def test_petite_bankroll_ne_produit_rien_sur_un_edge_modeste(
    settings, match_factory, balanced_quotes
):
    """Realite d'un depart a 200 EUR, a documenter plutot qu'a masquer.

    Un edge de ~4% sur une cote a 4.20 donne une mise de quart de Kelly
    d'environ 0.55 EUR, sous la mise minimale des bookmakers : aucun ticket
    n'est emis. C'est voulu. Arrondir la mise vers le haut pour "atteindre le
    minimum" reviendrait a sur-dimensionner, ce qui detruit la croissance a
    long terme (cf. test_kelly.py).

    La meme opportunite sur 1000 EUR produit bien un pari : la contrainte vient
    de la taille de la bankroll, pas de la detection.
    """
    quotes = [
        *[q for q in balanced_quotes if q.bookmaker != "betclic"],
        BookmakerQuote("betclic", Market.ONE_X_TWO, {"HOME": 2.05, "DRAW": 3.38, "AWAY": 4.20}),
    ]
    match = match_factory(quotes)

    petite = BankrollManager(BankrollState(starting=200.0, current=200.0, peak=200.0))
    rapport_petit = BettingEngine(settings, petite).analyse([match])
    assert rapport_petit.tickets == []
    assert any("trop faible" in r.reason for r in rapport_petit.rejections)

    grande = BankrollManager(
        BankrollState(starting=BANKROLL_EUR, current=BANKROLL_EUR, peak=BANKROLL_EUR)
    )
    rapport_grand = BettingEngine(settings, grande).analyse([match])
    assert len(rapport_grand.tickets) == 1


def test_drawdown_severe_bloque_le_moteur(settings, match_factory, value_quotes):
    manager = BankrollManager(BankrollState(starting=1000.0, current=600.0, peak=1000.0))
    report = BettingEngine(settings, manager).analyse([match_factory(value_quotes)])
    assert report.tickets == []
    assert report.blocked_reason is not None
    assert "drawdown" in report.blocked_reason


def test_marche_illiquide_est_rejete(settings, bankroll, match_factory, value_quotes):
    solo = value_quotes[:1]
    report = BettingEngine(settings, bankroll).analyse([match_factory(solo)])
    assert report.tickets == []
    assert any("peu fiable" in r.reason for r in report.rejections)


def test_garde_fou_de_desaccord(bankroll, match_factory, value_quotes, synthetic_history):
    """Un modele en fort desaccord avec le marche signale des donnees suspectes.

    Ici le modele est entraine sur Alpha/Echo alors que les cotes decrivent un
    match beaucoup plus serre : le moteur doit refuser de parier plutot que de
    croire a un edge de 20%.
    """
    strict = Settings(max_disagreement=0.05)
    engine = BettingEngine.train(strict, bankroll, synthetic_history)
    report = engine.analyse([match_factory(value_quotes, home="Alpha", away="Echo")])
    assert report.tickets == []
    assert any("desaccord" in r.reason for r in report.rejections)


def test_budget_d_exposition_limite_le_nombre_de_paris(settings, match_factory, value_quotes):
    """Dix matchs a value, mais l'exposition totale reste sous le plafond."""
    limits = RiskLimits(max_stake_pct=0.02, max_open_exposure_pct=0.01, max_bets_per_day=100)
    manager = BankrollManager(
        BankrollState(starting=BANKROLL_EUR, current=BANKROLL_EUR, peak=BANKROLL_EUR), limits
    )
    matches = [
        match_factory(value_quotes, home=f"Equipe{i}", away=f"Adversaire{i}") for i in range(10)
    ]
    for index, match in enumerate(matches):
        object.__setattr__(match, "match_id", f"m{index}")

    report = BettingEngine(settings, manager).analyse(matches)
    assert report.total_stake <= BANKROLL_EUR * 0.01 + 1e-9
    assert len(report.tickets) < 10
    assert any("exposition" in r.reason for r in report.rejections)


def test_le_rapport_est_lisible(settings, bankroll, match_factory, value_quotes):
    from suukalia.report import render_analysis, render_telegram

    report = BettingEngine(settings, bankroll).analyse([match_factory(value_quotes)])
    texte = render_analysis(report, bankroll.state, verbose=True)
    assert "BANKROLL" in texte and "betclic" in texte
    assert "AWAY" in render_telegram(report, bankroll.state)


def test_sans_modele_le_moteur_suit_le_marche(settings, bankroll, match_factory, value_quotes):
    """Aucun modele entraine : les probabilites sont celles du consensus."""
    engine = BettingEngine(settings, bankroll)
    report = engine.analyse([match_factory(value_quotes)])
    prediction = report.predictions[0]
    assert prediction.confidence == 0.0   # confiance du MODELE, pas de l'estimation
    for key, value in prediction.market_probabilities.items():
        assert prediction.probabilities[key] == pytest.approx(value, abs=1e-6)
