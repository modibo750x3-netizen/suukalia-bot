"""Notation Elo adaptee au football (avec nul et marge de victoire)."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..mathx import normalise_dict
from ..models import MatchResult, normalise_team

DEFAULT_RATING = 1500.0


@dataclass
class EloModel:
    """Elo classique + deux ajustements indispensables en football.

    - `home_advantage` en points Elo (~65 correspond a l'avantage terrain
      historique des grands championnats europeens).
    - multiplicateur de marge de victoire : gagner 4-0 informe plus que 1-0,
      mais avec un rendement decroissant, sinon les gros scores font exploser
      les notes.
    """

    k_factor: float = 20.0
    home_advantage: float = 65.0
    draw_parameter: float = 1.05
    ratings: dict[str, float] = field(default_factory=dict)
    matches_seen: dict[str, int] = field(default_factory=dict)

    def rating(self, team: str) -> float:
        return self.ratings.get(normalise_team(team), DEFAULT_RATING)

    def fit(self, results: Iterable[MatchResult]) -> EloModel:
        """Parcourt l'historique dans l'ordre chronologique."""
        for result in sorted(results, key=lambda r: r.date):
            self.update(result)
        return self

    def update(self, result: MatchResult) -> None:
        home, away = normalise_team(result.home), normalise_team(result.away)
        r_home = self.ratings.get(home, DEFAULT_RATING)
        r_away = self.ratings.get(away, DEFAULT_RATING)

        expected = self._expected_score(r_home + self.home_advantage, r_away)
        goal_diff = result.home_goals - result.away_goals
        actual = 1.0 if goal_diff > 0 else (0.5 if goal_diff == 0 else 0.0)

        # Rendement decroissant sur la marge : ln(1 + |diff|).
        multiplier = math.log1p(abs(goal_diff)) if goal_diff else 1.0
        # Amortisseur d'Elo : une grosse victoire d'un favori informe moins.
        multiplier *= 2.2 / (2.2 + 0.001 * abs(r_home + self.home_advantage - r_away))

        delta = self.k_factor * multiplier * (actual - expected)
        self.ratings[home] = r_home + delta
        self.ratings[away] = r_away - delta
        self.matches_seen[home] = self.matches_seen.get(home, 0) + 1
        self.matches_seen[away] = self.matches_seen.get(away, 0) + 1

    @staticmethod
    def _expected_score(r_a: float, r_b: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / 400.0))

    def predict_1x2(self, home: str, away: str) -> dict[str, float]:
        """Modele de Davidson : le nul est un troisieme resultat parametre.

        p(H) ∝ 10^(d/2), p(A) ∝ 10^(-d/2), p(N) ∝ nu * sqrt(p(H)p(A)).
        Le nul est donc le plus probable quand les equipes sont proches, ce que
        l'Elo binaire classique ne sait pas exprimer.
        """
        diff = (self.rating(home) + self.home_advantage - self.rating(away)) / 400.0
        e_home = 10.0 ** (diff / 2.0)
        e_away = 10.0 ** (-diff / 2.0)
        e_draw = self.draw_parameter * math.sqrt(e_home * e_away)
        return normalise_dict({"HOME": e_home, "DRAW": e_draw, "AWAY": e_away})

    def confidence(self, home: str, away: str, full_at: int = 20) -> float:
        """0 -> equipes inconnues, 1 -> historique suffisant pour les deux."""
        seen = min(
            self.matches_seen.get(normalise_team(home), 0),
            self.matches_seen.get(normalise_team(away), 0),
        )
        return min(seen / full_at, 1.0)
