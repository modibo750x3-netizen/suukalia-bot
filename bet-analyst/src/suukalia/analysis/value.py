"""Detection de value : ou le prix propose s'ecarte-t-il du vrai prix ?"""

from __future__ import annotations

from dataclasses import dataclass

from ..mathx import EPS


@dataclass(frozen=True, slots=True)
class ValueOpportunity:
    selection: str
    bookmaker: str
    odds: float
    probability: float
    fair_odds: float
    edge: float
    expected_value: float
    breakeven_probability: float

    def as_percent(self) -> str:
        return f"{self.edge * 100:+.2f}%"


def expected_value(probability: float, odds: float, stake: float = 1.0) -> float:
    """EV d'une mise en cotes decimales : p*(o-1)*s - (1-p)*s = s*(p*o - 1)."""
    return stake * (probability * odds - 1.0)


def edge(probability: float, odds: float) -> float:
    """Avantage relatif : p*o - 1. 0.03 = +3% d'EV par euro mise."""
    return probability * odds - 1.0


def find_value(
    probabilities: dict[str, float],
    best_odds: dict[str, tuple[str, float]],
    min_edge: float = 0.03,
    min_odds: float = 1.30,
    max_odds: float = 8.0,
) -> list[ValueOpportunity]:
    """Liste les issues dont la cote depasse le prix "fair" d'au moins min_edge.

    Les bornes sur la cote ne sont pas cosmetiques :
    - sous 1.30, l'edge est mange par le moindre biais de modele et la mise
      Kelly devient enorme pour un gain derisoire ;
    - au-dela de 8.0, l'estimation de probabilite est trop bruitee et la
      variance rend le resultat ininterpretable avant des milliers de paris.
    """
    found: list[ValueOpportunity] = []
    for selection, (bookmaker, odds) in best_odds.items():
        p = probabilities.get(selection, 0.0)
        if p <= EPS or not (min_odds <= odds <= max_odds):
            continue
        e = edge(p, odds)
        if e < min_edge:
            continue
        found.append(
            ValueOpportunity(
                selection=selection,
                bookmaker=bookmaker,
                odds=odds,
                probability=p,
                fair_odds=1.0 / p,
                edge=e,
                expected_value=expected_value(p, odds),
                breakeven_probability=1.0 / odds,
            )
        )
    return sorted(found, key=lambda v: v.edge, reverse=True)


def closing_line_value(taken_odds: float, closing_odds: float) -> float:
    """CLV : de combien la cote prise bat-elle la cote de cloture ?

    C'est LA metrique a suivre. Le P&L sur 200 paris ne dit presque rien (la
    variance domine), alors qu'un CLV moyen positif sur 200 paris prouve que la
    selection a de la valeur. Un CLV negatif avec un P&L positif = chance.
    """
    if closing_odds <= 1.0 or taken_odds <= 1.0:
        return 0.0
    return taken_odds / closing_odds - 1.0
