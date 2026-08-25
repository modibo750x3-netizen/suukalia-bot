"""Backtest walk-forward et simulation de croissance de bankroll.

Deux outils distincts, souvent confondus :

- `walk_forward` mesure la QUALITE DE PREDICTION sur l'historique, sans jamais
  laisser le modele voir le futur. Il sort du log-loss et du Brier, pas un
  P&L : sans cotes historiques, un P&L de backtest est une fiction.
- `simulate_bankroll` mesure le RISQUE. Connaissant un edge et une strategie de
  mise, il repond a la seule question qui compte quand on part de 200 EUR :
  quelle est la probabilite de tout perdre avant que l'edge ne paie ?
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

from .mathx import brier_score, log_loss
from .modelling.dixon_coles import DixonColesModel
from .modelling.elo import EloModel
from .modelling.ensemble import blend
from .models import MatchResult
from .staking.kelly import KellyConfig, kelly_fraction


@dataclass
class BacktestReport:
    """Qualite predictive mesuree hors echantillon."""

    predictions: int = 0
    log_loss: float = 0.0
    brier: float = 0.0
    accuracy: float = 0.0
    baseline_log_loss: float = 0.0
    calibration: list[tuple[float, float, int]] = field(default_factory=list)

    @property
    def skill(self) -> float:
        """Gain de log-loss face a une prediction constante (1/3, 1/3, 1/3).

        Positif = le modele apporte de l'information. C'est un plancher tres
        bas : un modele qui ne le franchit pas est inutilisable.
        """
        if self.baseline_log_loss <= 0:
            return 0.0
        return 1.0 - self.log_loss / self.baseline_log_loss

    def render(self) -> str:
        lines = [
            f"Predictions hors echantillon : {self.predictions}",
            f"Log-loss                     : {self.log_loss:.4f} "
            f"(reference uniforme {self.baseline_log_loss:.4f})",
            f"Score de Brier               : {self.brier:.4f}",
            f"Taux de bonne issue          : {self.accuracy:.1%}",
            f"Apport d'information         : {self.skill:+.2%}",
        ]
        if self.calibration:
            lines.append("")
            lines.append("Calibration (proba predite -> frequence observee) :")
            for low, observed, count in self.calibration:
                lines.append(
                    f"  [{low:.0%}-{low + 0.1:.0%})  observe {observed:6.1%}  n={count}"
                )
        return "\n".join(lines)


def walk_forward(
    results: Sequence[MatchResult],
    train_size: int = 200,
    step: int = 20,
) -> BacktestReport:
    """Re-entraine periodiquement et predit uniquement des matchs futurs.

    C'est la seule facon honnete d'evaluer : entrainer sur tout l'historique
    puis "predire" ce meme historique donne des scores flatteurs et faux.
    """
    ordered = sorted(results, key=lambda r: r.date)
    if len(ordered) <= train_size:
        return BacktestReport()

    report = BacktestReport()
    total_ll = total_brier = correct = 0.0
    buckets: dict[int, list[int]] = {}

    cursor = train_size
    while cursor < len(ordered):
        train = ordered[:cursor]
        test = ordered[cursor : cursor + step]
        if not test:
            break

        dc = DixonColesModel().fit(train)
        elo = EloModel().fit(train)

        for match in test:
            dc_probs = dc.predict_1x2(match.home, match.away)
            elo_probs = elo.predict_1x2(match.home, match.away)
            confidence = min(
                dc.confidence(match.home, match.away), elo.confidence(match.home, match.away)
            )
            # Pas de marche dans un backtest historique : on melange les deux
            # modeles maison entre eux, a poids egaux.
            probs = blend(dc_probs, elo_probs, None, confidence)

            actual = match.outcome()
            total_ll += log_loss(probs, actual)
            total_brier += brier_score(probs, actual)
            if max(probs, key=probs.get) == actual:
                correct += 1
            report.predictions += 1

            bucket = min(int(probs[actual] * 10), 9)
            buckets.setdefault(bucket, []).append(1)
            for outcome, p in probs.items():
                if outcome != actual:
                    buckets.setdefault(min(int(p * 10), 9), []).append(0)

        cursor += step

    if report.predictions:
        report.log_loss = total_ll / report.predictions
        report.brier = total_brier / report.predictions
        report.accuracy = correct / report.predictions
        report.baseline_log_loss = math.log(3.0)
        report.calibration = [
            (b / 10, statistics.fmean(v), len(v)) for b, v in sorted(buckets.items()) if v
        ]
    return report


# --------------------------------------------------------------------------
@dataclass
class GrowthSimulation:
    """Distribution des trajectoires de bankroll sur N paris."""

    starting: float
    bets: int
    trials: int
    finals: list[float]
    ruin_rate: float
    max_drawdowns: list[float]

    def percentile(self, q: float) -> float:
        if not self.finals:
            return 0.0
        ordered = sorted(self.finals)
        index = min(int(q * (len(ordered) - 1)), len(ordered) - 1)
        return ordered[index]

    def render(self) -> str:
        median = self.percentile(0.50)
        return "\n".join(
            [
                f"Simulation : {self.trials} trajectoires de {self.bets} paris, "
                f"depart {self.starting:.0f} EUR",
                "",
                f"  Pire 5%      : {self.percentile(0.05):8.2f} EUR",
                f"  1er quartile : {self.percentile(0.25):8.2f} EUR",
                f"  Mediane      : {median:8.2f} EUR  ({median / self.starting - 1:+.1%})",
                f"  3e quartile  : {self.percentile(0.75):8.2f} EUR",
                f"  Meilleur 5%  : {self.percentile(0.95):8.2f} EUR",
                "",
                f"  Risque de ruine        : {self.ruin_rate:.1%}",
                f"  Drawdown median subi   : {statistics.median(self.max_drawdowns):.1%}",
                f"  Trajectoires perdantes : "
                f"{sum(1 for f in self.finals if f < self.starting) / len(self.finals):.1%}",
            ]
        )


def simulate_bankroll(
    starting: float = 200.0,
    bets: int = 300,
    edge: float = 0.03,
    odds: float = 2.10,
    kelly: KellyConfig | None = None,
    trials: int = 5000,
    ruin_threshold: float = 0.20,
    seed: int = 12345,
    flat_fraction: float | None = None,
) -> GrowthSimulation:
    """Monte-Carlo de la strategie de mise, a edge suppose CONNU et constant.

    Hypothese volontairement genereuse : on suppose que l'edge annonce est
    reel. Si le resultat est deja mediocre dans ces conditions, il le sera bien
    davantage en pratique, ou l'edge est estime avec erreur.

    `ruin_threshold` : fraction du capital initial en dessous de laquelle on
    considere la bankroll detruite (20% de 200 EUR = 40 EUR, en dessous
    desquels les mises minimales des bookmakers rendent la strategie
    inapplicable).

    `flat_fraction` : mise a plat (fraction constante de la bankroll) au lieu
    de Kelly. C'est ce que fait la grande majorite des parieurs, et c'est le
    seul moyen de simuler un edge NEGATIF : Kelly, lui, refuse simplement de
    miser. Passer `edge=-0.05, flat_fraction=0.02` reproduit fidelement un
    parieur qui mise 2% de sa bankroll a la marge du bookmaker.
    """
    kelly = kelly or KellyConfig()
    rng = random.Random(seed)
    probability = (1.0 + edge) / odds  # p telle que p*o - 1 = edge
    ruin_level = starting * ruin_threshold

    finals: list[float] = []
    drawdowns: list[float] = []
    ruined = 0

    for _ in range(trials):
        bankroll = starting
        peak = starting
        worst = 0.0
        for _ in range(bets):
            if flat_fraction is not None:
                fraction = flat_fraction
            else:
                fraction = min(
                    kelly_fraction(probability, odds) * kelly.fraction, kelly.max_stake_pct
                )
            stake = bankroll * fraction
            if stake < kelly.min_stake:
                break  # mise sous le minimum du book : la strategie s'arrete
            bankroll += stake * (odds - 1.0) if rng.random() < probability else -stake
            peak = max(peak, bankroll)
            worst = max(worst, 1.0 - bankroll / peak)
            if bankroll <= ruin_level:
                ruined += 1
                break
        finals.append(bankroll)
        drawdowns.append(worst)

    return GrowthSimulation(
        starting=starting,
        bets=bets,
        trials=trials,
        finals=finals,
        ruin_rate=ruined / trials if trials else 0.0,
        max_drawdowns=drawdowns,
    )
