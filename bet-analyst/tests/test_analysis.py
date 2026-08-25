"""Consensus de marche et detection de value."""

from __future__ import annotations

import pytest

from suukalia.analysis.consensus import build_consensus
from suukalia.analysis.value import closing_line_value, edge, expected_value, find_value
from suukalia.models import BookmakerQuote, Market


def test_consensus_agrege_les_books(balanced_quotes):
    consensus = build_consensus(balanced_quotes, Market.ONE_X_TWO)
    assert consensus is not None
    assert consensus.book_count == 5
    assert sum(consensus.probabilities.values()) == pytest.approx(1.0)
    assert 0.03 < consensus.mean_margin < 0.08


def test_consensus_retient_la_meilleure_cote(balanced_quotes):
    """Jouer la meilleure cote disponible est le levier de ROI le plus simple."""
    consensus = build_consensus(balanced_quotes, Market.ONE_X_TWO)
    assert consensus.best_odds["AWAY"] == ("pinnacle", 3.78)
    assert consensus.best_odds["HOME"] == ("pinnacle", 2.08)


def test_books_alignes_donnent_une_faible_dispersion(balanced_quotes):
    consensus = build_consensus(balanced_quotes, Market.ONE_X_TWO)
    assert consensus.is_liquid(min_books=3, max_dispersion=0.06)


def test_book_isole_fait_monter_la_dispersion(value_quotes):
    consensus = build_consensus(value_quotes, Market.ONE_X_TWO)
    aligned = build_consensus(
        [q for q in value_quotes if q.bookmaker != "betclic"], Market.ONE_X_TWO
    )
    assert consensus.dispersion > aligned.dispersion


def test_marche_trop_etroit_est_rejete():
    quotes = [BookmakerQuote("solo", Market.ONE_X_TWO, {"HOME": 2.0, "DRAW": 3.4, "AWAY": 3.9})]
    consensus = build_consensus(quotes, Market.ONE_X_TWO)
    assert not consensus.is_liquid(min_books=3)


def test_aucune_cote_retourne_none():
    assert build_consensus([], Market.ONE_X_TWO) is None


def test_lignes_incompatibles_sont_ignorees(balanced_quotes):
    """Un book qui ne cote que deux issues ne doit pas polluer le consensus."""
    bancal = BookmakerQuote("bizarre", Market.ONE_X_TWO, {"HOME": 9.9, "AWAY": 9.9})
    quotes = [*balanced_quotes, bancal]
    consensus = build_consensus(quotes, Market.ONE_X_TWO)
    assert consensus.book_count == 5


# --------------------------------------------------------------------- value
def test_edge_et_ev():
    assert edge(0.55, 2.00) == pytest.approx(0.10)
    assert expected_value(0.55, 2.00, stake=10.0) == pytest.approx(1.0)
    assert edge(0.50, 2.00) == pytest.approx(0.0)


def test_marche_efficient_ne_produit_aucune_value(balanced_quotes):
    """Sur un marche coherent, les cotes ne battent pas le prix fair."""
    consensus = build_consensus(balanced_quotes, Market.ONE_X_TWO)
    assert find_value(consensus.probabilities, consensus.best_odds, min_edge=0.03) == []


def test_book_decale_produit_une_value(value_quotes):
    consensus = build_consensus(value_quotes, Market.ONE_X_TWO)
    opportunities = find_value(consensus.probabilities, consensus.best_odds, min_edge=0.03)
    assert len(opportunities) == 1
    assert opportunities[0].selection == "AWAY"
    assert opportunities[0].bookmaker == "betclic"
    assert opportunities[0].edge > 0.03


def test_bornes_de_cotes_appliquees():
    probabilities = {"A": 0.80, "B": 0.10, "C": 0.10}
    best = {"A": ("x", 1.25), "B": ("x", 12.0), "C": ("x", 2.0)}
    # A : cote trop basse ; B : cote trop haute ; C : pas d'edge.
    assert find_value(probabilities, best, min_edge=0.01, min_odds=1.30, max_odds=8.0) == []


def test_opportunites_triees_par_edge_decroissant():
    probabilities = {"A": 0.40, "B": 0.35, "C": 0.25}
    best = {"A": ("x", 2.80), "B": ("y", 3.20), "C": ("z", 4.60)}
    found = find_value(probabilities, best, min_edge=0.01)
    assert [o.edge for o in found] == sorted((o.edge for o in found), reverse=True)


def test_clv():
    """Prendre 2.20 sur un match qui cloture a 2.00 = +10% de CLV."""
    assert closing_line_value(2.20, 2.00) == pytest.approx(0.10)
    assert closing_line_value(1.90, 2.00) < 0.0
    assert closing_line_value(2.0, 0.0) == 0.0
