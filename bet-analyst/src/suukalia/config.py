"""Configuration : variables d'environnement + fichier JSON optionnel."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from .analysis.devig import DevigMethod
from .modelling.ensemble import BlendConfig
from .staking.bankroll import RiskLimits
from .staking.kelly import KellyConfig

DEFAULT_LEAGUES = [
    "soccer_epl",
    "soccer_france_ligue_one",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league",
]


@dataclass
class Settings:
    """Tous les reglages du moteur, en un objet unique et serialisable."""

    odds_api_key: str = ""
    football_data_key: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    db_path: str = "data/bankroll.sqlite3"

    leagues: list[str] = field(default_factory=lambda: list(DEFAULT_LEAGUES))
    regions: str = "eu"
    devig_method: DevigMethod = "shin"

    starting_bankroll: float = 200.0
    min_edge: float = 0.03
    min_odds: float = 1.30
    max_odds: float = 8.0
    min_books: int = 3
    max_dispersion: float = 0.06
    max_disagreement: float = 0.15

    blend: BlendConfig = field(default_factory=BlendConfig)
    kelly: KellyConfig = field(default_factory=KellyConfig)
    limits: RiskLimits = field(default_factory=RiskLimits)

    # ------------------------------------------------------------ chargement
    @classmethod
    def load(cls, path: str | Path | None = None) -> Settings:
        """Charge le fichier JSON s'il existe, puis surcharge par l'environnement.

        L'environnement gagne toujours : c'est ce qui permet de garder les cles
        API hors du depot tout en versionnant le reste de la configuration.
        """
        settings = cls()
        if path:
            file = Path(path)
            if file.exists():
                settings = cls.from_dict(json.loads(file.read_text(encoding="utf-8")))
        settings._apply_environment()
        return settings

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        nested = {
            "blend": BlendConfig,
            "kelly": KellyConfig,
            "limits": RiskLimits,
        }
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                continue
            if key in nested and isinstance(value, dict):
                kwargs[key] = nested[key](**value)
            else:
                kwargs[key] = value
        return cls(**kwargs)

    def _apply_environment(self) -> None:
        mapping = {
            "SUUKALIA_ODDS_API_KEY": "odds_api_key",
            "SUUKALIA_FOOTBALL_DATA_KEY": "football_data_key",
            "SUUKALIA_TELEGRAM_TOKEN": "telegram_token",
            "SUUKALIA_TELEGRAM_CHAT_ID": "telegram_chat_id",
            "SUUKALIA_DB_PATH": "db_path",
        }
        for env_key, attribute in mapping.items():
            value = os.environ.get(env_key)
            if value:
                setattr(self, attribute, value)
        bankroll = os.environ.get("SUUKALIA_STARTING_BANKROLL")
        if bankroll:
            try:
                self.starting_bankroll = float(bankroll)
            except ValueError:
                pass

    def validate(self) -> None:
        self.blend.validate()
        if not 0.0 < self.min_edge < 0.5:
            raise ValueError("min_edge doit etre dans ]0, 0.5[ ; 0.03 a 0.05 est realiste")
        if self.min_odds >= self.max_odds:
            raise ValueError("min_odds doit etre strictement inferieur a max_odds")
        if self.starting_bankroll <= 0:
            raise ValueError("starting_bankroll doit etre positif")
