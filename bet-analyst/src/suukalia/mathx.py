"""Primitives numeriques (stdlib uniquement, aucune dependance externe)."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence

EPS = 1e-12


def poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) pour X ~ Poisson(lam). Stable via le log."""
    if k < 0:
        return 0.0
    lam = max(lam, EPS)
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def normalise(values: Iterable[float]) -> list[float]:
    """Ramene un vecteur positif a une somme de 1."""
    vals = [max(v, 0.0) for v in values]
    total = sum(vals)
    if total <= EPS:
        n = len(vals) or 1
        return [1.0 / n] * n
    return [v / total for v in vals]


def normalise_dict(mapping: dict[str, float]) -> dict[str, float]:
    keys = list(mapping)
    return dict(zip(keys, normalise(mapping[k] for k in keys), strict=True))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def bisect(
    f: Callable[[float], float],
    low: float,
    high: float,
    tol: float = 1e-10,
    max_iter: int = 200,
) -> float:
    """Recherche de racine par dichotomie.

    Retourne la borne la plus proche de zero si la fonction ne change pas de
    signe sur l'intervalle : les appelants ont tous un repli sain, on prefere
    une valeur degradee a une exception au milieu d'un run de production.
    """
    f_low, f_high = f(low), f(high)
    if f_low * f_high > 0:
        return low if abs(f_low) <= abs(f_high) else high
    for _ in range(max_iter):
        mid = 0.5 * (low + high)
        f_mid = f(mid)
        if abs(f_mid) < tol or (high - low) < tol:
            return mid
        if f_low * f_mid <= 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return 0.5 * (low + high)


def log_pool(
    distributions: Sequence[dict[str, float]],
    weights: Sequence[float],
) -> dict[str, float]:
    """Aggregation logarithmique (moyenne geometrique ponderee) de lois.

    Preferee a la moyenne arithmetique pour combiner un modele et un marche :
    elle est externally bayesian et ne cree pas de probabilite superieure a
    toutes les sources sur une meme issue.
    """
    if not distributions:
        return {}
    keys = list(distributions[0])
    total_w = sum(weights)
    if total_w <= EPS:
        return normalise_dict(dict.fromkeys(keys, 1.0))
    pooled: dict[str, float] = {}
    for key in keys:
        acc = 0.0
        for dist, w in zip(distributions, weights, strict=True):
            acc += (w / total_w) * math.log(max(dist.get(key, 0.0), EPS))
        pooled[key] = math.exp(acc)
    return normalise_dict(pooled)


def shrink_towards(
    dist: dict[str, float], target: dict[str, float], strength: float
) -> dict[str, float]:
    """Tire `dist` vers `target` (0 = inchange, 1 = egal a la cible).

    La cible est explicite et jamais implicitement l'uniforme : retrecir vers
    l'uniforme une distribution issue du marche revient a gonfler la
    probabilite des gros outsiders, ce qui fabrique des edges fantomes exacte-
    ment la ou ils sont le plus couteux.
    """
    strength = clamp(strength, 0.0, 1.0)
    return normalise_dict(
        {k: (1 - strength) * v + strength * target.get(k, 0.0) for k, v in dist.items()}
    )


def brier_score(probabilities: dict[str, float], actual: str) -> float:
    """Score de Brier multi-classe (0 = parfait, plus bas = mieux)."""
    return sum((p - (1.0 if k == actual else 0.0)) ** 2 for k, p in probabilities.items())


def log_loss(probabilities: dict[str, float], actual: str) -> float:
    """Log-loss, la metrique qui compte pour du pari (elle punit la certitude)."""
    return -math.log(max(probabilities.get(actual, 0.0), EPS))
