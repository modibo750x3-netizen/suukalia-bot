"""Retrait de la marge du bookmaker ("devigging").

C'est l'etape la plus sous-estimee du pari quantitatif : une cote brute n'est
pas une probabilite. Sur un 1X2 la somme des probabilites implicites vaut
typiquement 1.05-1.08. La facon dont on redistribue ces 5-8% change
completement le classement des value bets, surtout sur les outsiders.

Trois methodes sont implementees, du plus naif au plus realiste :

- ``multiplicative`` : divise tout par la somme. Suppose une marge
  proportionnelle a la probabilite -> sur-estime systematiquement les outsiders.
- ``power``          : cherche k tel que sum(p_i^k) = 1. Corrige une partie du
  favorite-longshot bias.
- ``shin``           : modele de Shin (1993), la marge vient de la presence de
  parieurs informes. C'est la reference du secteur pour le 1X2.
"""

from __future__ import annotations

import math
from typing import Literal

from ..mathx import EPS, bisect, normalise_dict

DevigMethod = Literal["multiplicative", "power", "shin"]


def implied_probabilities(odds: dict[str, float]) -> dict[str, float]:
    """Probabilites implicites brutes (marge incluse) : 1 / cote."""
    return {k: (1.0 / o if o > 1.0 else 0.0) for k, o in odds.items()}


def devig(odds: dict[str, float], method: DevigMethod = "shin") -> dict[str, float]:
    """Convertit des cotes en probabilites "fair" (somme = 1)."""
    raw = implied_probabilities(odds)
    if len(raw) < 2 or sum(raw.values()) <= EPS:
        return normalise_dict(dict.fromkeys(odds, 1.0))
    if method == "multiplicative":
        return normalise_dict(raw)
    if method == "power":
        return _power_devig(raw)
    if method == "shin":
        return _shin_devig(raw)
    raise ValueError(f"methode de devig inconnue : {method}")


def _power_devig(raw: dict[str, float]) -> dict[str, float]:
    """Trouve k tel que sum(p_i ** k) = 1. k < 1 gonfle les petites probas."""
    values = list(raw.values())
    if min(values) <= EPS:
        return normalise_dict(raw)

    def gap(k: float) -> float:
        return sum(v**k for v in values) - 1.0

    # gap(1) = overround > 0 ; gap(k grand) -> 0 par le bas puisque p_i < 1.
    k = bisect(gap, 1.0, 12.0)
    return normalise_dict({key: v**k for key, v in raw.items()})


def _shin_devig(raw: dict[str, float]) -> dict[str, float]:
    """Inversion du modele de Shin, resolue en z (part de flux informe)."""
    booksum = sum(raw.values())
    if booksum <= 1.0 + EPS:
        return normalise_dict(raw)

    def probabilities(z: float) -> dict[str, float]:
        z = min(z, 1.0 - 1e-9)
        out = {}
        for key, pi in raw.items():
            inner = z * z + 4.0 * (1.0 - z) * pi * pi / booksum
            out[key] = (math.sqrt(max(inner, 0.0)) - z) / (2.0 * (1.0 - z))
        return out

    def gap(z: float) -> float:
        return sum(probabilities(z).values()) - 1.0

    # gap(0) = sqrt(booksum) - 1 > 0 ; gap(z->1) = sum(p_i^2)/booksum - 1 < 0.
    z = bisect(gap, 0.0, 1.0 - 1e-9)
    return normalise_dict(probabilities(z))


def fair_odds(probabilities: dict[str, float]) -> dict[str, float]:
    """Cotes sans marge correspondant a une distribution de probabilites."""
    return {k: (1.0 / p if p > EPS else math.inf) for k, p in probabilities.items()}


def shin_z(odds: dict[str, float]) -> float:
    """Estimation de z : proportion de flux "informe" percue par le book.

    Utile comme proxy de liquidite / nervosite du marche. Un z eleve sur un
    match signale un marche que le book juge risque : les edges y sont plus
    souvent illusoires.
    """
    raw = implied_probabilities(odds)
    booksum = sum(raw.values())
    if booksum <= 1.0 + EPS:
        return 0.0

    def gap(z: float) -> float:
        zz = min(z, 1.0 - 1e-9)
        total = 0.0
        for pi in raw.values():
            inner = zz * zz + 4.0 * (1.0 - zz) * pi * pi / booksum
            total += (math.sqrt(max(inner, 0.0)) - zz) / (2.0 * (1.0 - zz))
        return total - 1.0

    return bisect(gap, 0.0, 1.0 - 1e-9)
