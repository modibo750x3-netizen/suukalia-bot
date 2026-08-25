"""Client the-odds-api.com : cotes multi-bookmakers en temps reel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import BookmakerQuote, Market, Match, Team
from .base import ProviderError, http_get_json

BASE_URL = "https://api.the-odds-api.com/v4"

# Correspondance entre les cles de marche de l'API et nos marches internes.
MARKET_KEYS = {"h2h": Market.ONE_X_TWO, "totals": Market.OVER_UNDER_25}


class TheOddsApiProvider:
    """Recupere les cotes a venir pour un championnat.

    L'offre gratuite plafonne a 500 requetes/mois : une requete rend TOUS les
    matchs d'un championnat, donc un run quotidien sur 6 championnats coute
    ~180 requetes/mois. Ne pas boucler par match.
    """

    name = "the-odds-api"

    def __init__(self, api_key: str, regions: str = "eu") -> None:
        if not api_key:
            raise ProviderError("cle the-odds-api manquante (SUUKALIA_ODDS_API_KEY)")
        self.api_key = api_key
        self.regions = regions

    def fetch_matches(self, league: str) -> list[Match]:
        payload = http_get_json(
            f"{BASE_URL}/sports/{league}/odds",
            params={
                "apiKey": self.api_key,
                "regions": self.regions,
                "markets": "h2h,totals",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        if not isinstance(payload, list):
            raise ProviderError("format inattendu : une liste de matchs etait attendue")
        return [m for m in (self._parse_match(raw, league) for raw in payload) if m]

    def _parse_match(self, raw: dict[str, Any], league: str) -> Match | None:
        try:
            home_name = raw["home_team"]
            away_name = raw["away_team"]
            kickoff = datetime.fromisoformat(raw["commence_time"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            return None

        quotes: list[BookmakerQuote] = []
        for book in raw.get("bookmakers", []):
            key = book.get("key", "?")
            for market in book.get("markets", []):
                parsed = self._parse_market(market, home_name, away_name)
                if parsed:
                    quotes.append(BookmakerQuote(bookmaker=key, market=parsed[0], odds=parsed[1]))
        if not quotes:
            return None
        return Match(
            match_id=raw.get("id", f"{league}:{home_name}:{away_name}"),
            league=league,
            kickoff=kickoff,
            home=Team(home_name),
            away=Team(away_name),
            quotes=quotes,
        )

    @staticmethod
    def _parse_market(
        market: dict[str, Any], home: str, away: str
    ) -> tuple[Market, dict[str, float]] | None:
        key = market.get("key")
        outcomes = market.get("outcomes") or []
        if key == "h2h":
            odds: dict[str, float] = {}
            for outcome in outcomes:
                name, price = outcome.get("name"), outcome.get("price")
                if price is None:
                    continue
                if name == home:
                    odds["HOME"] = float(price)
                elif name == away:
                    odds["AWAY"] = float(price)
                elif name == "Draw":
                    odds["DRAW"] = float(price)
            return (Market.ONE_X_TWO, odds) if len(odds) == 3 else None
        if key == "totals":
            # On ne retient que la ligne 2.5, la seule assez liquide partout.
            odds = {}
            for outcome in outcomes:
                if abs(float(outcome.get("point", 0)) - 2.5) > 1e-9:
                    continue
                name = str(outcome.get("name", "")).upper()
                if name in {"OVER", "UNDER"} and outcome.get("price") is not None:
                    odds[name] = float(outcome["price"])
            return (Market.OVER_UNDER_25, odds) if len(odds) == 2 else None
        return None
