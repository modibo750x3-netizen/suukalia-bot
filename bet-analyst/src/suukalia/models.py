"""Modeles de donnees du domaine.

Tout le pipeline manipule ces objets : les fournisseurs produisent des `Match`
et des `BookmakerQuote`, le moteur produit des `Prediction` puis des `BetTicket`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

# Ordre canonique des issues 1X2. Il est utilise partout : ne jamais le changer
# sans mettre a jour les serialisations en base.
OUTCOMES_1X2 = ("HOME", "DRAW", "AWAY")


class Market(str, Enum):
    """Marches supportes par le moteur."""

    ONE_X_TWO = "1X2"
    OVER_UNDER_25 = "OU2.5"
    BTTS = "BTTS"


@dataclass(frozen=True, slots=True)
class Team:
    name: str

    def key(self) -> str:
        """Cle de rapprochement entre fournisseurs (noms ecrits differemment)."""
        return normalise_team(self.name)


def normalise_team(name: str) -> str:
    """Normalise un nom d'equipe pour rapprocher deux sources heterogenes.

    'Paris Saint-Germain FC' et 'PSG' resteront differents : le mapping
    d'alias est la responsabilite de `providers.aliases`. Ici on se limite a
    une normalisation typographique deterministe.
    """
    lowered = name.strip().lower()
    for accented, plain in (
        ("à", "a"), ("â", "a"), ("ä", "a"), ("é", "e"), ("è", "e"), ("ê", "e"),
        ("ë", "e"), ("î", "i"), ("ï", "i"), ("ô", "o"), ("ö", "o"), ("ù", "u"),
        ("û", "u"), ("ü", "u"), ("ç", "c"),
    ):
        lowered = lowered.replace(accented, plain)
    keep = [c for c in lowered if c.isalnum() or c == " "]
    tokens = "".join(keep).split()
    # Suffixes juridiques sans valeur discriminante.
    noise = {"fc", "cf", "sc", "ac", "as", "afc", "club", "de", "the"}
    tokens = [t for t in tokens if t not in noise] or tokens
    return " ".join(tokens)


@dataclass(frozen=True, slots=True)
class BookmakerQuote:
    """Cotes proposees par un bookmaker sur un marche donne, a un instant t."""

    bookmaker: str
    market: Market
    odds: dict[str, float]
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def overround(self) -> float:
        """Somme des probabilites implicites brutes (1.0 = marche sans marge)."""
        return sum(1.0 / o for o in self.odds.values() if o > 1.0)

    def margin(self) -> float:
        """Marge du bookmaker, en fraction (0.05 = 5%)."""
        return self.overround() - 1.0


@dataclass(frozen=True, slots=True)
class Match:
    """Une rencontre, avec toutes les cotes collectees."""

    match_id: str
    league: str
    kickoff: datetime
    home: Team
    away: Team
    quotes: list[BookmakerQuote] = field(default_factory=list)

    def quotes_for(self, market: Market) -> list[BookmakerQuote]:
        return [q for q in self.quotes if q.market is market]

    def label(self) -> str:
        return f"{self.home.name} - {self.away.name}"


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Resultat historique, utilise pour l'entrainement et le backtest."""

    date: datetime
    league: str
    home: str
    away: str
    home_goals: int
    away_goals: int

    def outcome(self) -> str:
        if self.home_goals > self.away_goals:
            return "HOME"
        if self.home_goals < self.away_goals:
            return "AWAY"
        return "DRAW"


@dataclass(frozen=True, slots=True)
class Prediction:
    """Probabilites finales du moteur pour un marche."""

    match_id: str
    market: Market
    probabilities: dict[str, float]
    # Composantes, conservees pour l'audit : on veut pouvoir expliquer pourquoi
    # le moteur s'ecarte du marche.
    model_probabilities: dict[str, float] = field(default_factory=dict)
    market_probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class BetTicket:
    """Une recommandation de pari, prete a etre jouee ou archivee."""

    match_id: str
    label: str
    league: str
    kickoff: datetime
    market: Market
    selection: str
    bookmaker: str
    odds: float
    fair_odds: float
    probability: float
    edge: float
    expected_value: float
    stake: float
    kelly_fraction: float
    confidence: float

    def to_row(self) -> dict[str, object]:
        return {
            "match_id": self.match_id,
            "label": self.label,
            "league": self.league,
            "kickoff": self.kickoff.isoformat(),
            "market": self.market.value,
            "selection": self.selection,
            "bookmaker": self.bookmaker,
            "odds": self.odds,
            "fair_odds": self.fair_odds,
            "probability": self.probability,
            "edge": self.edge,
            "expected_value": self.expected_value,
            "stake": self.stake,
            "kelly_fraction": self.kelly_fraction,
            "confidence": self.confidence,
        }
