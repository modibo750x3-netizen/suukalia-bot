"""Construction du "vrai prix" du marche a partir de plusieurs bookmakers.

Principe directeur : le marche agrege est le meilleur predicteur unique
disponible. Un modele maison ne le bat pas en moyenne ; il sert a reperer les
moments ou UN bookmaker s'ecarte du consensus. C'est de la que vient l'edge.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from ..mathx import EPS, normalise_dict
from ..models import BookmakerQuote, Market
from .devig import DevigMethod, devig

# Bookmakers a faible marge : leur ligne est plus proche du vrai prix, on leur
# donne plus de poids dans le consensus. Les autres prennent un poids de base.
SHARP_BOOKS = {
    "pinnacle": 3.0,
    "betfair_ex_eu": 2.5,
    "smarkets": 2.0,
    "matchbook": 2.0,
    "betfair": 2.5,
}
DEFAULT_WEIGHT = 1.0


@dataclass(frozen=True, slots=True)
class MarketConsensus:
    """Le prix de reference d'un marche, et sa dispersion."""

    market: Market
    probabilities: dict[str, float]
    best_odds: dict[str, tuple[str, float]]
    book_count: int
    mean_margin: float
    dispersion: float

    def fair_odds(self, selection: str) -> float:
        p = self.probabilities.get(selection, 0.0)
        return 1.0 / p if p > EPS else float("inf")

    def is_liquid(self, min_books: int = 3, max_dispersion: float = 0.06) -> bool:
        """Un marche fiable : assez de books, et qui sont d'accord entre eux.

        Une forte dispersion veut dire que les books n'ont pas la meme info
        (compo, blessure de derniere minute). Le "value bet" apparent est alors
        le plus souvent un book qui n'a pas encore mis a jour sa ligne, et il
        refusera ou limitera la mise.
        """
        return self.book_count >= min_books and self.dispersion <= max_dispersion


def build_consensus(
    quotes: list[BookmakerQuote],
    market: Market,
    method: DevigMethod = "shin",
) -> MarketConsensus | None:
    """Agrege les cotes de tous les books en un prix de reference pondere."""
    relevant = [q for q in quotes if q.market is market and len(q.odds) >= 2]
    if not relevant:
        return None

    selections = list(relevant[0].odds)
    weighted: dict[str, float] = dict.fromkeys(selections, 0.0)
    per_selection: dict[str, list[float]] = {s: [] for s in selections}
    total_weight = 0.0
    margins: list[float] = []

    for quote in relevant:
        if set(quote.odds) != set(selections):
            continue  # ligne incompatible (ex : handicap different)
        fair = devig(quote.odds, method)
        weight = SHARP_BOOKS.get(quote.bookmaker.lower(), DEFAULT_WEIGHT)
        # Un book a marge enorme est peu informatif : on le penalise.
        margin = quote.margin()
        weight /= 1.0 + max(margin, 0.0) * 10.0
        for sel, p in fair.items():
            weighted[sel] += weight * p
            per_selection[sel].append(p)
        total_weight += weight
        margins.append(margin)

    if total_weight <= EPS:
        return None

    probabilities = normalise_dict({s: v / total_weight for s, v in weighted.items()})
    best = _best_odds(relevant, selections)
    dispersion = max(
        (statistics.pstdev(v) if len(v) > 1 else 0.0) for v in per_selection.values()
    )
    return MarketConsensus(
        market=market,
        probabilities=probabilities,
        best_odds=best,
        book_count=len(margins),
        mean_margin=statistics.fmean(margins) if margins else 0.0,
        dispersion=dispersion,
    )


def _best_odds(
    quotes: list[BookmakerQuote], selections: list[str]
) -> dict[str, tuple[str, float]]:
    """Meilleure cote disponible par issue, avec le book qui la propose.

    Jouer systematiquement la meilleure cote du marche vaut plusieurs points de
    ROI par an. C'est le levier le plus rentable et le plus simple du metier.
    """
    best: dict[str, tuple[str, float]] = {}
    for quote in quotes:
        for sel in selections:
            odd = quote.odds.get(sel)
            if odd is None or odd <= 1.0:
                continue
            if sel not in best or odd > best[sel][1]:
                best[sel] = (quote.bookmaker, odd)
    return best
