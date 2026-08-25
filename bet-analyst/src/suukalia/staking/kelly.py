"""Dimensionnement des mises : critere de Kelly, en version prudente."""

from __future__ import annotations

from dataclasses import dataclass

from ..mathx import clamp


@dataclass(frozen=True, slots=True)
class KellyConfig:
    """Parametres de mise.

    `fraction` = 0.25 (quart de Kelly) est la valeur de travail standard. Le
    Kelly plein maximise la croissance logarithmique SI les probabilites sont
    exactes -- elles ne le sont jamais. Surestimer p de 2 points suffit a
    transformer le Kelly plein en strategie perdante, alors que le quart de
    Kelly reste positif : on echange ~25% de croissance theorique contre une
    reduction massive du risque de ruine.
    """

    fraction: float = 0.25
    max_stake_pct: float = 0.02      # 2% de bankroll maximum par pari
    min_stake: float = 1.0           # mise minimale acceptee par le book
    round_to: float = 0.5            # pas d'arrondi des tickets (toujours vers le bas)


def kelly_fraction(probability: float, odds: float) -> float:
    """Fraction optimale de bankroll pour un pari binaire.

    f* = (p*b - q) / b, avec b = cote - 1. Negatif ou nul => ne pas parier.
    """
    if odds <= 1.0:
        return 0.0
    b = odds - 1.0
    p = clamp(probability, 0.0, 1.0)
    f = (p * b - (1.0 - p)) / b
    return max(f, 0.0)


def stake_for(
    probability: float,
    odds: float,
    bankroll: float,
    config: KellyConfig | None = None,
    risk_multiplier: float = 1.0,
) -> tuple[float, float]:
    """Retourne (mise en euros, fraction de Kelly retenue).

    `risk_multiplier` (0..1) est le frein applique par la gestion de bankroll :
    drawdown en cours, exposition deja engagee, faible confiance du modele.
    """
    config = config or KellyConfig()
    raw = kelly_fraction(probability, odds)
    if raw <= 0.0 or bankroll <= 0.0:
        return 0.0, 0.0

    applied = raw * config.fraction * clamp(risk_multiplier, 0.0, 1.0)
    applied = min(applied, config.max_stake_pct)

    stake = bankroll * applied
    if stake < config.min_stake:
        # Test AVANT arrondi : arrondir 0.83 EUR a 1.00 EUR pour atteindre le
        # minimum du bookmaker, c'est miser 20% de plus que ce que Kelly
        # autorise. Sur les petites bankrolls ce biais s'applique a presque
        # chaque pari et suffit a annuler l'edge.
        return 0.0, 0.0
    if config.round_to > 0:
        # Arrondi vers le BAS : la mise calculee est un plafond, jamais un
        # objectif a atteindre.
        stake = (stake // config.round_to) * config.round_to
        if stake < config.min_stake:
            return 0.0, 0.0
    return round(stake, 2), applied


def growth_rate(probability: float, odds: float, fraction: float) -> float:
    """Croissance logarithmique attendue par pari, pour une fraction donnee.

    Sert a verifier qu'une strategie est bien dans la zone de croissance :
    si ce nombre est negatif, la strategie detruit la bankroll a long terme
    meme quand l'EV par pari est positive (c'est le sur-dimensionnement).
    """
    import math

    if not 0.0 <= fraction < 1.0 or odds <= 1.0:
        return 0.0
    p = clamp(probability, 0.0, 1.0)
    win = math.log(1.0 + fraction * (odds - 1.0))
    lose = math.log(max(1.0 - fraction, 1e-12))
    return p * win + (1.0 - p) * lose
