"""Combinaison modele maison + marche.

Regle cardinale : le marche est le prior, pas le concurrent. Un modele entraine
sur quelques centaines de matchs ne bat pas la ligne de cloture de Pinnacle. Il
sert a detecter les ecarts d'UN bookmaker par rapport au consensus.

On combine donc par pooling logarithmique avec un poids marche dominant, puis
on ramene le resultat vers le marche proportionnellement au manque de donnees.
Deux verrous contre le piege classique : "mon modele dit 45%, le book paie 3.00,
donc +35% d'edge" -- non, le modele a tort.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..mathx import clamp, log_pool, normalise_dict, shrink_towards


@dataclass(frozen=True, slots=True)
class BlendConfig:
    """Poids de melange.

    `market_weight` a 0.65 signifie : le consensus explique 65% de la decision.
    Descendre sous 0.5 revient a parier que le modele maison est mieux informe
    que l'ensemble du marche -- a ne faire qu'avec un backtest qui le prouve.
    """

    market_weight: float = 0.65
    dixon_coles_weight: float = 0.25
    elo_weight: float = 0.10
    # Retour maximal vers le marche quand les equipes sont peu connues.
    max_shrink: float = 0.35

    def validate(self) -> None:
        total = self.market_weight + self.dixon_coles_weight + self.elo_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"les poids doivent sommer a 1.0 (recu {total:.4f})")
        if not 0.0 <= self.max_shrink <= 1.0:
            raise ValueError("max_shrink doit etre dans [0, 1]")


def blend(
    market: dict[str, float],
    dixon_coles: dict[str, float] | None,
    elo: dict[str, float] | None,
    confidence: float,
    config: BlendConfig | None = None,
) -> dict[str, float]:
    """Melange les sources disponibles et applique le retrecissement.

    `confidence` (0..1) mesure la quantite de donnees derriere le modele. A 0,
    les composantes maison sont ignorees et la fonction ressort exactement le
    marche : ne jamais parier contre le marche sur la base d'un modele a
    l'aveugle.
    """
    config = config or BlendConfig()
    config.validate()
    confidence = clamp(confidence, 0.0, 1.0)

    distributions = [normalise_dict(market)]
    weights = [config.market_weight]

    # Les poids maison sont attenues par la confiance ; le reliquat retourne
    # au marche, seule source toujours fiable.
    reclaimed = 0.0
    for dist, weight in ((dixon_coles, config.dixon_coles_weight), (elo, config.elo_weight)):
        if dist:
            distributions.append(normalise_dict(dist))
            weights.append(weight * confidence)
            reclaimed += weight * (1.0 - confidence)
        else:
            reclaimed += weight
    weights[0] += reclaimed

    pooled = log_pool(distributions, weights)
    # Securite finale : moins le modele a de donnees, plus on revient vers le
    # marche -- jamais vers l'uniforme, qui n'est pas une croyance defendable.
    return shrink_towards(
        pooled, normalise_dict(market), config.max_shrink * (1.0 - confidence)
    )


def disagreement(model: dict[str, float], market: dict[str, float]) -> float:
    """Distance de variation totale entre modele et marche.

    Un desaccord superieur a ~0.15 sur un 1X2 est presque toujours le signe
    d'un bug de donnees (mauvais appariement d'equipes, cotes perimees) plutot
    que d'une inefficience de marche. Le moteur s'en sert comme garde-fou.
    """
    keys = set(model) | set(market)
    return 0.5 * sum(abs(model.get(k, 0.0) - market.get(k, 0.0)) for k in keys)
