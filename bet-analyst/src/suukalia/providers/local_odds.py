"""Fournisseur hors-ligne : lit des cotes depuis un fichier JSON.

Sert a deux choses : faire tourner le moteur sans cle API (demo, tests, CI), et
rejouer un jeu de cotes fige pour deboguer une recommandation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models import BookmakerQuote, Market, Match, Team
from .base import ProviderError


class LocalOddsProvider:
    """Charge des matchs depuis `data/sample_odds.json` (ou tout fichier equivalent)."""

    name = "local"

    def __init__(self, path: str | Path = "data/sample_odds.json") -> None:
        self.path = Path(path)

    def fetch_matches(self, league: str = "") -> list[Match]:
        if not self.path.exists():
            raise ProviderError(f"fichier de cotes introuvable : {self.path}")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProviderError(f"JSON invalide dans {self.path} : {exc}") from exc

        matches = []
        for raw in payload:
            if league and raw.get("league") != league:
                continue
            quotes = [
                BookmakerQuote(
                    bookmaker=q["bookmaker"],
                    market=Market(q.get("market", "1X2")),
                    odds={k: float(v) for k, v in q["odds"].items()},
                )
                for q in raw.get("quotes", [])
            ]
            matches.append(
                Match(
                    match_id=raw["match_id"],
                    league=raw.get("league", "demo"),
                    kickoff=datetime.fromisoformat(raw["kickoff"]),
                    home=Team(raw["home"]),
                    away=Team(raw["away"]),
                    quotes=quotes,
                )
            )
        return matches
