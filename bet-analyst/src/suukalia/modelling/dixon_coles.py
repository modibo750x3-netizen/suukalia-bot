"""Modele Dixon-Coles (1997) : Poisson bivarie avec correction des petits scores.

Pourquoi celui-la plutot qu'un Poisson simple :

1. Un Poisson independant sous-estime les 0-0 et 1-1 et sur-estime les 1-0/0-1.
   Or ces quatre scores representent ~25% des matchs : l'erreur se voit
   directement sur le marche du nul et sur les Under.
2. La ponderation temporelle exponentielle (parametre xi) fait oublier au
   modele les saisons anciennes, ou l'effectif n'a plus rien a voir.

L'ajustement se fait par point fixe multiplicatif sur la vraisemblance de
Poisson ponderee (equivalent a un IRLS mais sans dependance externe), puis
recherche unidimensionnelle sur rho.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..mathx import EPS, clamp, normalise_dict, poisson_pmf
from ..models import MatchResult, normalise_team

MAX_GOALS = 10


@dataclass
class TeamStrength:
    attack: float = 1.0
    defence: float = 1.0
    matches: int = 0


@dataclass
class DixonColesModel:
    """Force d'attaque / de defense par equipe + avantage du terrain + rho."""

    xi: float = 0.0065          # demi-vie d'environ 107 jours
    max_iter: int = 200
    tolerance: float = 1e-9
    home_advantage: float = 1.35
    rho: float = 0.0
    teams: dict[str, TeamStrength] = field(default_factory=dict)
    base_rate: float = 1.35
    reference_date: datetime | None = None

    # ------------------------------------------------------------------ fit
    def fit(self, results: Sequence[MatchResult]) -> DixonColesModel:
        results = [r for r in results if r.home_goals >= 0 and r.away_goals >= 0]
        if not results:
            return self
        self.reference_date = max(r.date for r in results)
        weights = [self._time_weight(r.date) for r in results]

        names = {normalise_team(r.home) for r in results} | {
            normalise_team(r.away) for r in results
        }
        self.teams = {name: TeamStrength() for name in names}
        for r in results:
            self.teams[normalise_team(r.home)].matches += 1
            self.teams[normalise_team(r.away)].matches += 1

        self._fit_strengths(results, weights)
        self.rho = self._fit_rho(results, weights)
        return self

    def _fit_strengths(self, results: Sequence[MatchResult], weights: Sequence[float]) -> None:
        """Point fixe sequentiel sur la vraisemblance de Poisson ponderee.

        Le modele s'ecrit lam = base * A_h * D_a * gamma et mu = base * A_a * D_h.
        Tel quel il est sur-parametre : (A*c, D/c) laisse lam inchange, et une
        mise a jour simultanee de tous les blocs oscille en divergeant (la
        defense explose pendant que gamma s'effondre, et reciproquement).

        On leve l'indetermination par deux contraintes -- moyenne des attaques
        = 1 et moyenne des defenses = 1 -- et on met les blocs a jour l'un
        apres l'autre (Gauss-Seidel), chacun avec les valeurs deja rafraichies
        des precedents. C'est ce qui rend l'iteration stable.
        """
        names = list(self.teams)
        prior = 6.0  # force du lissage vers 1.0 pour les equipes peu vues

        for _ in range(self.max_iter):
            shift = 0.0

            # -- bloc 1 : attaques (defenses, gamma et base figes) ------------
            scored: dict[str, float] = dict.fromkeys(names, 0.0)
            exposure: dict[str, float] = dict.fromkeys(names, 0.0)
            for r, w in zip(results, weights, strict=True):
                h, a = normalise_team(r.home), normalise_team(r.away)
                scored[h] += w * r.home_goals
                scored[a] += w * r.away_goals
                exposure[h] += w * self.base_rate * self.teams[a].defence * self.home_advantage
                exposure[a] += w * self.base_rate * self.teams[h].defence
            for name in names:
                team = self.teams[name]
                value = scored[name] / max(exposure[name], EPS)
                value = (team.matches * value + prior) / (team.matches + prior)
                shift += abs(value - team.attack)
                team.attack = max(value, EPS)
            self._rescale("attack")

            # -- bloc 2 : defenses (attaques fraiches) ------------------------
            conceded: dict[str, float] = dict.fromkeys(names, 0.0)
            exposure = dict.fromkeys(names, 0.0)
            for r, w in zip(results, weights, strict=True):
                h, a = normalise_team(r.home), normalise_team(r.away)
                conceded[a] += w * r.home_goals
                conceded[h] += w * r.away_goals
                exposure[a] += w * self.base_rate * self.teams[h].attack * self.home_advantage
                exposure[h] += w * self.base_rate * self.teams[a].attack
            for name in names:
                team = self.teams[name]
                value = conceded[name] / max(exposure[name], EPS)
                value = (team.matches * value + prior) / (team.matches + prior)
                shift += abs(value - team.defence)
                team.defence = max(value, EPS)
            self._rescale("defence")

            # -- bloc 3 : avantage du terrain --------------------------------
            home_goals = 0.0
            home_exposure = 0.0
            for r, w in zip(results, weights, strict=True):
                h, a = normalise_team(r.home), normalise_team(r.away)
                home_goals += w * r.home_goals
                home_exposure += w * self.base_rate * self.teams[h].attack * self.teams[a].defence
            if home_exposure > EPS:
                new_ha = clamp(home_goals / home_exposure, 0.5, 3.0)
                shift += abs(new_ha - self.home_advantage)
                self.home_advantage = new_ha

            # -- bloc 4 : niveau de buts global ------------------------------
            total_goals = 0.0
            total_exposure = 0.0
            for r, w in zip(results, weights, strict=True):
                h, a = normalise_team(r.home), normalise_team(r.away)
                th, ta = self.teams[h], self.teams[a]
                total_goals += w * (r.home_goals + r.away_goals)
                total_exposure += w * (
                    th.attack * ta.defence * self.home_advantage + ta.attack * th.defence
                )
            if total_exposure > EPS:
                new_base = max(total_goals / total_exposure, EPS)
                shift += abs(new_base - self.base_rate)
                self.base_rate = new_base

            if shift < self.tolerance:
                break

    def _rescale(self, attribute: str) -> None:
        """Impose une moyenne de 1 sur attaque ou defense (identification)."""
        values = [getattr(t, attribute) for t in self.teams.values()]
        mean = sum(values) / len(values) if values else 1.0
        if mean <= EPS:
            return
        for team in self.teams.values():
            setattr(team, attribute, getattr(team, attribute) / mean)
        # Le niveau retire des forces est reporte sur le taux de base, pour que
        # les buts attendus soient inchanges par la renormalisation.
        self.base_rate *= mean

    def _fit_rho(self, results: Sequence[MatchResult], weights: Sequence[float]) -> float:
        """Balayage 1D sur rho.

        rho ne touche que les scores ou les deux equipes marquent 0 ou 1 but :
        une fois attaque/defense figees, il se calibre proprement seul. Les
        intensites sont precalculees, le balayage ne fait plus que 51 passes de
        pmf au lieu de re-deriver le modele a chaque pas.
        """
        intensities = [self.expected_goals(r.home, r.away) for r in results]
        best_rho, best_ll = 0.0, -math.inf
        for step in range(51):
            rho = -0.25 + step * 0.01
            ll = 0.0
            for r, w, (lam, mu) in zip(results, weights, intensities, strict=True):
                p = self._joint_pmf(r.home_goals, r.away_goals, lam, mu, rho)
                ll += w * math.log(max(p, EPS))
            if ll > best_ll:
                best_ll, best_rho = ll, rho
        return best_rho

    def _time_weight(self, date: datetime) -> float:
        ref = self.reference_date or datetime.now(timezone.utc)
        days = max((ref - date).days, 0)
        return math.exp(-self.xi * days)

    # -------------------------------------------------------------- predict
    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        h = self.teams.get(normalise_team(home))
        a = self.teams.get(normalise_team(away))
        if h is None or a is None:
            # Equipe jamais vue (promue, coupe) : on retombe sur l'equipe moyenne.
            base = self.base_rate
            return base * self.home_advantage, base
        lam = self.base_rate * h.attack * a.defence * self.home_advantage
        mu = self.base_rate * a.attack * h.defence
        return max(lam, EPS), max(mu, EPS)

    @staticmethod
    def _tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
        """Correction Dixon-Coles sur les quatre scores les plus frequents."""
        if x == 0 and y == 0:
            return 1.0 - lam * mu * rho
        if x == 0 and y == 1:
            return 1.0 + lam * rho
        if x == 1 and y == 0:
            return 1.0 + mu * rho
        if x == 1 and y == 1:
            return 1.0 - rho
        return 1.0

    def _joint_pmf(self, x: int, y: int, lam: float, mu: float, rho: float) -> float:
        tau = max(self._tau(x, y, lam, mu, rho), EPS)
        return tau * poisson_pmf(x, lam) * poisson_pmf(y, mu)

    def score_matrix(self, home: str, away: str) -> list[list[float]]:
        """Loi jointe des scores, tronquee et renormalisee."""
        lam, mu = self.expected_goals(home, away)
        matrix = [
            [self._joint_pmf(x, y, lam, mu, self.rho) for y in range(MAX_GOALS + 1)]
            for x in range(MAX_GOALS + 1)
        ]
        total = sum(sum(row) for row in matrix)
        if total <= EPS:
            return matrix
        return [[cell / total for cell in row] for row in matrix]

    def predict_1x2(self, home: str, away: str) -> dict[str, float]:
        matrix = self.score_matrix(home, away)
        probs = {"HOME": 0.0, "DRAW": 0.0, "AWAY": 0.0}
        for x, row in enumerate(matrix):
            for y, p in enumerate(row):
                key = "HOME" if x > y else ("AWAY" if x < y else "DRAW")
                probs[key] += p
        return normalise_dict(probs)

    def predict_over_under(self, home: str, away: str, line: float = 2.5) -> dict[str, float]:
        matrix = self.score_matrix(home, away)
        over = sum(p for x, row in enumerate(matrix) for y, p in enumerate(row) if x + y > line)
        return normalise_dict({"OVER": over, "UNDER": 1.0 - over})

    def predict_btts(self, home: str, away: str) -> dict[str, float]:
        matrix = self.score_matrix(home, away)
        yes = sum(p for x, row in enumerate(matrix) for y, p in enumerate(row) if x > 0 and y > 0)
        return normalise_dict({"YES": yes, "NO": 1.0 - yes})

    def confidence(self, home: str, away: str, full_at: int = 20) -> float:
        h = self.teams.get(normalise_team(home))
        a = self.teams.get(normalise_team(away))
        if h is None or a is None:
            return 0.0
        return min(min(h.matches, a.matches) / full_at, 1.0)

    def top_scorelines(self, home: str, away: str, n: int = 5) -> list[tuple[str, float]]:
        matrix = self.score_matrix(home, away)
        cells = [
            (f"{x}-{y}", p) for x, row in enumerate(matrix) for y, p in enumerate(row)
        ]
        return sorted(cells, key=lambda c: c[1], reverse=True)[:n]


def train(results: Iterable[MatchResult], xi: float = 0.0065) -> DixonColesModel:
    return DixonColesModel(xi=xi).fit(list(results))
