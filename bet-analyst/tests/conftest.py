"""Fixtures partagees : donnees synthetiques a verite terrain connue."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from suukalia.models import BookmakerQuote, Market, Match, MatchResult, Team

TRUE_ATTACK = {"Alpha": 1.45, "Bravo": 1.20, "Charlie": 1.00, "Delta": 0.85, "Echo": 0.70}
TRUE_DEFENCE = {"Alpha": 0.75, "Bravo": 0.95, "Charlie": 1.00, "Delta": 1.10, "Echo": 1.35}
TRUE_BASE = 1.30
TRUE_HOME_ADVANTAGE = 1.30


def _poisson(lam: float, rng: random.Random) -> int:
    limit, k, product = math.exp(-lam), 0, 1.0
    while True:
        product *= rng.random()
        if product <= limit:
            return k
        k += 1


@pytest.fixture(scope="session")
def synthetic_history() -> list[MatchResult]:
    """3000 matchs generes par un Poisson bivarie de parametres connus.

    Permet de tester la RECUPERATION des parametres, pas seulement le fait que
    le code s'execute : un modele qui tourne sans planter mais qui n'estime
    rien est un modele casse.
    """
    rng = random.Random(1234)
    names = list(TRUE_ATTACK)
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    results = []
    for i in range(3000):
        home, away = rng.sample(names, 2)
        lam = TRUE_BASE * TRUE_ATTACK[home] * TRUE_DEFENCE[away] * TRUE_HOME_ADVANTAGE
        mu = TRUE_BASE * TRUE_ATTACK[away] * TRUE_DEFENCE[home]
        results.append(
            MatchResult(
                date=start + timedelta(hours=6 * i),
                league="TEST",
                home=home,
                away=away,
                home_goals=_poisson(lam, rng),
                away_goals=_poisson(mu, rng),
            )
        )
    return results


@pytest.fixture
def balanced_quotes() -> list[BookmakerQuote]:
    """Cinq books d'accord entre eux, marges realistes."""
    return [
        BookmakerQuote("pinnacle", Market.ONE_X_TWO, {"HOME": 2.08, "DRAW": 3.52, "AWAY": 3.78}),
        BookmakerQuote("bet365", Market.ONE_X_TWO, {"HOME": 2.02, "DRAW": 3.45, "AWAY": 3.65}),
        BookmakerQuote("unibet", Market.ONE_X_TWO, {"HOME": 2.00, "DRAW": 3.40, "AWAY": 3.70}),
        BookmakerQuote("betclic", Market.ONE_X_TWO, {"HOME": 2.05, "DRAW": 3.38, "AWAY": 3.60}),
        BookmakerQuote("winamax", Market.ONE_X_TWO, {"HOME": 2.03, "DRAW": 3.44, "AWAY": 3.68}),
    ]


@pytest.fixture
def value_quotes(balanced_quotes: list[BookmakerQuote]) -> list[BookmakerQuote]:
    """Les memes books, sauf un qui sur-cote nettement l'exterieur."""
    outlier = BookmakerQuote(
        "betclic", Market.ONE_X_TWO, {"HOME": 2.05, "DRAW": 3.38, "AWAY": 4.60}
    )
    return [q for q in balanced_quotes if q.bookmaker != "betclic"] + [outlier]


@pytest.fixture
def match_factory():
    def build(quotes: list[BookmakerQuote], home: str = "Alpha", away: str = "Echo") -> Match:
        return Match(
            match_id=f"{home}-{away}",
            league="TEST",
            kickoff=datetime(2026, 9, 1, 19, 0, tzinfo=timezone.utc),
            home=Team(home),
            away=Team(away),
            quotes=quotes,
        )

    return build
