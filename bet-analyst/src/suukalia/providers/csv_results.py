"""Lecture d'historiques au format football-data.co.uk.

Ce format (Date, HomeTeam, AwayTeam, FTHG, FTAG) est le standard de fait des
archives gratuites de resultats. Les colonnes supplementaires sont ignorees.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from ..models import MatchResult
from .base import ProviderError

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d")


class CsvResultsProvider:
    """Charge un ou plusieurs CSV de resultats depuis le disque."""

    name = "csv"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def fetch_results(self, league: str = "") -> list[MatchResult]:
        files = sorted(self.path.glob("*.csv")) if self.path.is_dir() else [self.path]
        results: list[MatchResult] = []
        for file in files:
            if not file.exists():
                raise ProviderError(f"fichier de resultats introuvable : {file}")
            results.extend(self._read(file, league or file.stem))
        return sorted(results, key=lambda r: r.date)

    def _read(self, file: Path, league: str) -> list[MatchResult]:
        out: list[MatchResult] = []
        with file.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                parsed = self._parse_row(row, league)
                if parsed:
                    out.append(parsed)
        return out

    @staticmethod
    def _parse_row(row: dict[str, str], league: str) -> MatchResult | None:
        home, away = row.get("HomeTeam"), row.get("AwayTeam")
        if not home or not away:
            return None
        try:
            home_goals = int(float(row["FTHG"]))
            away_goals = int(float(row["FTAG"]))
        except (KeyError, TypeError, ValueError):
            return None  # match reporte ou ligne incomplete
        date = _parse_date(row.get("Date", ""))
        if date is None:
            return None
        return MatchResult(
            date=date,
            league=row.get("Div") or league,
            home=home,
            away=away,
            home_goals=home_goals,
            away_goals=away_goals,
        )


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
