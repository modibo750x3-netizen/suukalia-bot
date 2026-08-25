"""Gestion de bankroll : le seul composant qui empeche reellement de tout perdre.

Un modele mediocre avec une bonne gestion de bankroll survit. Un excellent
modele en Kelly plein sans plafond d'exposition finit a zero sur une serie
noire parfaitement normale statistiquement.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..mathx import clamp


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Bornes dures. Aucune recommandation ne peut les franchir.

    Valeurs calibrees pour une petite bankroll de depart (200 EUR), ou la ruine
    est le risque numero un :
    - 2% max par pari : il faut ~50 pertes consecutives pour tout perdre ;
    - 12% d'exposition simultanee : un week-end de championnat entier peut
      partir en meme temps, les resultats sont correles (meteo, arbitrage) ;
    - frein au-dela de 15% de drawdown : reduit la taille quand le modele est
      peut-etre casse, sans arreter completement ;
    - arret a 35% de drawdown : au-dela, c'est le modele qu'il faut revoir,
      pas la chance qu'il faut attendre.
    """

    max_stake_pct: float = 0.02
    max_open_exposure_pct: float = 0.12
    max_bets_per_day: int = 8
    drawdown_throttle_at: float = 0.15
    drawdown_stop_at: float = 0.35
    min_bankroll: float = 20.0


@dataclass
class BankrollState:
    """Etat courant, reconstruit depuis le grand livre des paris."""

    starting: float
    current: float
    peak: float
    open_exposure: float = 0.0
    bets_today: int = 0
    settled_bets: int = 0

    @property
    def drawdown(self) -> float:
        """Baisse depuis le plus haut historique, en fraction."""
        if self.peak <= 0:
            return 0.0
        return max(0.0, 1.0 - self.current / self.peak)

    @property
    def profit(self) -> float:
        return self.current - self.starting

    @property
    def roi(self) -> float:
        return self.profit / self.starting if self.starting > 0 else 0.0


class BankrollManager:
    """Applique les limites de risque et calcule le frein a appliquer aux mises."""

    def __init__(self, state: BankrollState, limits: RiskLimits | None = None) -> None:
        self.state = state
        self.limits = limits or RiskLimits()

    def is_trading_allowed(self) -> tuple[bool, str]:
        """Le moteur doit-il encore produire des recommandations ?"""
        if self.state.current < self.limits.min_bankroll:
            return False, (
                f"bankroll {self.state.current:.2f} EUR sous le plancher "
                f"{self.limits.min_bankroll:.2f} EUR"
            )
        if self.state.drawdown >= self.limits.drawdown_stop_at:
            return False, (
                f"drawdown {self.state.drawdown:.1%} au-dela de la limite "
                f"{self.limits.drawdown_stop_at:.0%} : revoir le modele avant de continuer"
            )
        if self.state.bets_today >= self.limits.max_bets_per_day:
            return False, f"plafond de {self.limits.max_bets_per_day} paris/jour atteint"
        return True, "ok"

    def risk_multiplier(self, confidence: float = 1.0) -> float:
        """Frein multiplicatif applique a la mise de Kelly.

        Combine trois facteurs, tous dans [0,1] : le drawdown en cours, la
        confiance du modele, et l'exposition deja engagee.
        """
        dd = self.state.drawdown
        if dd <= self.limits.drawdown_throttle_at:
            drawdown_factor = 1.0
        else:
            span = max(self.limits.drawdown_stop_at - self.limits.drawdown_throttle_at, 1e-9)
            drawdown_factor = clamp(1.0 - (dd - self.limits.drawdown_throttle_at) / span, 0.1, 1.0)

        budget = self.state.current * self.limits.max_open_exposure_pct
        remaining = clamp((budget - self.state.open_exposure) / max(budget, 1e-9), 0.0, 1.0)

        return drawdown_factor * clamp(confidence, 0.0, 1.0) * remaining

    def remaining_exposure(self) -> float:
        """Montant encore engageable avant d'atteindre le plafond d'exposition."""
        budget = self.state.current * self.limits.max_open_exposure_pct
        return max(0.0, budget - self.state.open_exposure)

    def cap_stake(self, stake: float) -> float:
        """Rabote une mise pour respecter le plafond unitaire et l'exposition."""
        per_bet_cap = self.state.current * self.limits.max_stake_pct
        return max(0.0, min(stake, per_bet_cap, self.remaining_exposure()))

    def register(self, stake: float) -> None:
        """Enregistre un pari place (met a jour exposition et compteur du jour)."""
        self.state.open_exposure += stake
        self.state.bets_today += 1

    def settle(self, stake: float, payout: float) -> None:
        """Solde un pari : `payout` = retour total (0 si perdu, mise*cote si gagne)."""
        self.state.open_exposure = max(0.0, self.state.open_exposure - stake)
        self.state.current += payout - stake
        self.state.peak = max(self.state.peak, self.state.current)
        self.state.settled_bets += 1
