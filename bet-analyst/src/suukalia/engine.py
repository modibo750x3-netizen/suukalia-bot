"""Moteur : de la collecte des cotes a la liste de paris dimensionnes.

Le pipeline, dans l'ordre :

    cotes brutes
      -> devig par bookmaker           (analysis.devig)
      -> consensus pondere du marche   (analysis.consensus)
      -> probabilites du modele        (modelling.dixon_coles + elo)
      -> melange modele/marche         (modelling.ensemble)
      -> filtres de qualite            (ici)
      -> detection de value            (analysis.value)
      -> dimensionnement Kelly bride   (staking.kelly + staking.bankroll)
      -> tickets

Chaque etape peut rejeter un match. Les rejets sont conserves et expliques :
savoir POURQUOI un match a ete ecarte vaut autant que la recommandation, c'est
ce qui permet de detecter un fournisseur casse plutot qu'un marche calme.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis.consensus import MarketConsensus, build_consensus
from .analysis.value import ValueOpportunity, find_value
from .config import Settings
from .mathx import EPS, clamp
from .modelling.dixon_coles import DixonColesModel
from .modelling.elo import EloModel
from .modelling.ensemble import blend, disagreement
from .models import BetTicket, Market, Match, MatchResult, Prediction
from .staking.bankroll import BankrollManager
from .staking.kelly import stake_for


@dataclass
class Rejection:
    """Un match ecarte, et la raison exacte."""

    match_id: str
    label: str
    reason: str


@dataclass
class AnalysisReport:
    """Resultat complet d'un run."""

    tickets: list[BetTicket] = field(default_factory=list)
    predictions: list[Prediction] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)
    matches_analysed: int = 0
    total_stake: float = 0.0
    blocked_reason: str | None = None

    def summary(self) -> str:
        if self.blocked_reason:
            return f"Trading suspendu : {self.blocked_reason}"
        return (
            f"{self.matches_analysed} matchs analyses, "
            f"{len(self.tickets)} paris retenus, "
            f"{self.total_stake:.2f} EUR engages"
        )


class BettingEngine:
    """Orchestre modeles, filtres et gestion de bankroll."""

    def __init__(
        self,
        settings: Settings,
        bankroll: BankrollManager,
        dixon_coles: DixonColesModel | None = None,
        elo: EloModel | None = None,
    ) -> None:
        settings.validate()
        self.settings = settings
        self.bankroll = bankroll
        self.dixon_coles = dixon_coles
        self.elo = elo

    # ------------------------------------------------------------ entrainement
    @classmethod
    def train(
        cls,
        settings: Settings,
        bankroll: BankrollManager,
        history: list[MatchResult],
    ) -> BettingEngine:
        """Entraine les deux modeles maison sur un historique."""
        dc = DixonColesModel().fit(history) if history else None
        elo = EloModel().fit(history) if history else None
        return cls(settings, bankroll, dc, elo)

    # ------------------------------------------------------------------- run
    def analyse(self, matches: list[Match]) -> AnalysisReport:
        """Analyse une liste de matchs et retourne les paris a jouer."""
        report = AnalysisReport()

        allowed, reason = self.bankroll.is_trading_allowed()
        if not allowed:
            report.blocked_reason = reason
            return report

        for match in sorted(matches, key=lambda m: m.kickoff):
            report.matches_analysed += 1
            self._analyse_match(match, report)
            # Le budget d'exposition se consomme au fil de l'eau : les matchs
            # les plus proches du coup d'envoi sont servis en premier.
            if self.bankroll.risk_multiplier() <= EPS:
                report.rejections.append(
                    Rejection(match.match_id, match.label(), "budget d'exposition epuise")
                )
                break
        return report

    def _analyse_match(self, match: Match, report: AnalysisReport) -> None:
        consensus = build_consensus(
            match.quotes, Market.ONE_X_TWO, self.settings.devig_method
        )
        if consensus is None:
            report.rejections.append(
                Rejection(match.match_id, match.label(), "aucune cote 1X2 exploitable")
            )
            return

        if not consensus.is_liquid(self.settings.min_books, self.settings.max_dispersion):
            report.rejections.append(
                Rejection(
                    match.match_id,
                    match.label(),
                    f"marche peu fiable ({consensus.book_count} books, "
                    f"dispersion {consensus.dispersion:.3f})",
                )
            )
            return

        prediction = self._predict(match, consensus)
        report.predictions.append(prediction)

        gap = disagreement(prediction.model_probabilities, consensus.probabilities)
        if prediction.model_probabilities and gap > self.settings.max_disagreement:
            # Un ecart enorme est presque toujours une erreur d'appariement
            # d'equipes ou une cote perimee, pas une inefficience.
            report.rejections.append(
                Rejection(
                    match.match_id,
                    match.label(),
                    f"desaccord modele/marche {gap:.1%} au-dela de "
                    f"{self.settings.max_disagreement:.0%} : donnees suspectes",
                )
            )
            return

        opportunities = find_value(
            prediction.probabilities,
            consensus.best_odds,
            min_edge=self.settings.min_edge,
            min_odds=self.settings.min_odds,
            max_odds=self.settings.max_odds,
        )
        if not opportunities:
            report.rejections.append(
                Rejection(match.match_id, match.label(), "aucun edge suffisant")
            )
            return

        # Un seul pari par match : deux issues du meme 1X2 sont anti-correlees,
        # les cumuler brouille le dimensionnement de Kelly.
        best = opportunities[0]
        staking_confidence = self._staking_confidence(best, consensus)
        multiplier = self.bankroll.risk_multiplier(staking_confidence)
        stake, fraction = stake_for(
            best.probability,
            best.odds,
            self.bankroll.state.current,
            self.settings.kelly,
            multiplier,
        )
        stake = self.bankroll.cap_stake(stake)
        if stake < self.settings.kelly.min_stake:
            # Distinguer les deux causes : une mise sous le minimum parce que
            # l'edge est petit n'appelle pas la meme reaction qu'un budget
            # d'exposition deja consomme par les matchs precedents.
            if self.bankroll.remaining_exposure() < self.settings.kelly.min_stake:
                reason = (
                    "budget d'exposition epuise "
                    f"({self.bankroll.state.open_exposure:.2f} EUR deja engages)"
                )
            else:
                reason = f"mise calculee trop faible ({stake:.2f} EUR)"
            report.rejections.append(Rejection(match.match_id, match.label(), reason))
            return

        ticket = BetTicket(
            match_id=match.match_id,
            label=match.label(),
            league=match.league,
            kickoff=match.kickoff,
            market=Market.ONE_X_TWO,
            selection=best.selection,
            bookmaker=best.bookmaker,
            odds=best.odds,
            fair_odds=best.fair_odds,
            probability=best.probability,
            edge=best.edge,
            expected_value=stake * best.edge,
            stake=stake,
            kelly_fraction=fraction,
            confidence=staking_confidence,
        )
        report.tickets.append(ticket)
        report.total_stake += stake
        self.bankroll.register(stake)

    @staticmethod
    def _staking_confidence(
        opportunity: ValueOpportunity, consensus: MarketConsensus
    ) -> float:
        """Fiabilite de l'edge detecte, selon son origine.

        Deux edges de meme taille ne se valent pas :

        - un edge de MARCHE (un bookmaker est hors du consensus des autres) est
          le signal le plus solide du metier ; il ne suppose rien d'autre que
          "les autres books ont raison". Mise a pleine taille.
        - un edge de MODELE (le consensus paie le prix juste, mais notre modele
          estime une autre probabilite) suppose que l'on sait mieux que
          l'ensemble du marche. C'est parfois vrai, souvent non. Mise reduite.

        On mesure la part de chaque origine et on dimensionne entre les deux.
        """
        market_probability = consensus.probabilities.get(opportunity.selection, 0.0)
        market_edge = market_probability * opportunity.odds - 1.0
        if opportunity.edge <= EPS:
            return 0.0
        model_share = clamp(1.0 - market_edge / opportunity.edge, 0.0, 1.0)
        return 1.0 - 0.5 * model_share

    def _predict(self, match: Match, consensus: MarketConsensus) -> Prediction:
        """Melange les modeles maison avec le consensus du marche."""
        home, away = match.home.name, match.away.name

        dc_probs = self.dixon_coles.predict_1x2(home, away) if self.dixon_coles else None
        elo_probs = self.elo.predict_1x2(home, away) if self.elo else None

        # Confiance dans le MODELE : elle pilote uniquement son poids dans le
        # melange. Elle ne doit pas servir a dimensionner la mise -- sans
        # modele, la prediction est le consensus du marche, qui est justement
        # la source la plus fiable dont on dispose.
        confidences = [
            m.confidence(home, away)
            for m in (self.dixon_coles, self.elo)
            if m is not None
        ]
        model_confidence = min(confidences) if confidences else 0.0

        final = blend(
            consensus.probabilities, dc_probs, elo_probs, model_confidence, self.settings.blend
        )
        return Prediction(
            match_id=match.match_id,
            market=Market.ONE_X_TWO,
            probabilities=final,
            model_probabilities=dc_probs or {},
            market_probabilities=consensus.probabilities,
            confidence=model_confidence,
        )
