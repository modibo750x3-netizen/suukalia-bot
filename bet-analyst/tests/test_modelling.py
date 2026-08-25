"""Tests de RECUPERATION de parametres, pas de simples tests de fumee.

Les donnees synthetiques sont generees par un Poisson bivarie de parametres
connus (voir conftest). Un modele correct doit les retrouver.
"""

from __future__ import annotations

import pytest

from suukalia.mathx import log_loss
from suukalia.modelling.dixon_coles import DixonColesModel
from suukalia.modelling.elo import EloModel
from suukalia.modelling.ensemble import BlendConfig, blend, disagreement
from tests.conftest import TRUE_ATTACK, TRUE_DEFENCE, TRUE_HOME_ADVANTAGE


@pytest.fixture(scope="module")
def fitted_dc(synthetic_history):
    # xi=0 : pas de decroissance temporelle, toutes les observations comptent.
    return DixonColesModel(xi=0.0).fit(synthetic_history)


def test_dixon_coles_retrouve_l_avantage_du_terrain(fitted_dc):
    assert fitted_dc.home_advantage == pytest.approx(TRUE_HOME_ADVANTAGE, rel=0.10)


def test_dixon_coles_retrouve_les_forces_relatives(fitted_dc):
    """Attaques et defenses estimees, a l'echelle de normalisation pres."""
    mean_attack = sum(TRUE_ATTACK.values()) / len(TRUE_ATTACK)
    mean_defence = sum(TRUE_DEFENCE.values()) / len(TRUE_DEFENCE)
    for name in TRUE_ATTACK:
        team = fitted_dc.teams[name.lower()]
        assert team.attack == pytest.approx(TRUE_ATTACK[name] / mean_attack, rel=0.15)
        assert team.defence == pytest.approx(TRUE_DEFENCE[name] / mean_defence, rel=0.15)


def test_dixon_coles_classe_correctement_les_equipes(fitted_dc):
    ordered = sorted(TRUE_ATTACK, key=lambda n: fitted_dc.teams[n.lower()].attack, reverse=True)
    assert ordered == ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]


def test_l_ajustement_ne_diverge_pas(fitted_dc):
    """Garde-fou de non-regression.

    Une mise a jour simultanee de tous les blocs faisait diverger l'ajustement
    (defenses -> 0, avantage terrain -> 0). Ce test verrouille le comportement
    stable de la version sequentielle.
    """
    assert 0.5 < fitted_dc.home_advantage < 3.0
    assert 0.5 < fitted_dc.base_rate < 4.0
    for team in fitted_dc.teams.values():
        assert 0.05 < team.attack < 20.0
        assert 0.05 < team.defence < 20.0


def test_probabilites_1x2_coherentes(fitted_dc):
    fort = fitted_dc.predict_1x2("Alpha", "Echo")
    faible = fitted_dc.predict_1x2("Echo", "Alpha")
    assert sum(fort.values()) == pytest.approx(1.0)
    assert fort["HOME"] > 0.6
    assert faible["AWAY"] > faible["HOME"]


def test_avantage_du_terrain_visible_dans_les_predictions(fitted_dc):
    """La meme affiche inversee doit favoriser l'equipe qui recoit."""
    a_domicile = fitted_dc.predict_1x2("Charlie", "Bravo")["HOME"]
    a_l_exterieur = fitted_dc.predict_1x2("Bravo", "Charlie")["AWAY"]
    assert a_domicile > a_l_exterieur


def test_marches_derives_sont_des_distributions(fitted_dc):
    over_under = fitted_dc.predict_over_under("Alpha", "Echo")
    btts = fitted_dc.predict_btts("Alpha", "Echo")
    assert sum(over_under.values()) == pytest.approx(1.0)
    assert sum(btts.values()) == pytest.approx(1.0)
    # Une grosse attaque contre une defense faible : Over 2.5 majoritaire.
    assert over_under["OVER"] > 0.5


def test_equipe_inconnue_retombe_sur_la_moyenne(fitted_dc):
    """Une promue jamais vue ne doit pas faire planter le moteur."""
    probabilities = fitted_dc.predict_1x2("Equipe Inconnue", "Autre Inconnue")
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert fitted_dc.confidence("Equipe Inconnue", "Alpha") == 0.0


def test_scorelines_les_plus_probables(fitted_dc):
    scorelines = fitted_dc.top_scorelines("Alpha", "Echo", 5)
    assert len(scorelines) == 5
    assert scorelines[0][1] >= scorelines[-1][1]


def test_dixon_coles_bat_l_uniforme(fitted_dc, synthetic_history):
    """Test de valeur reelle : le modele doit apporter de l'information."""
    recent = synthetic_history[-300:]
    model = sum(log_loss(fitted_dc.predict_1x2(m.home, m.away), m.outcome()) for m in recent)
    uniform = sum(
        log_loss({"HOME": 1 / 3, "DRAW": 1 / 3, "AWAY": 1 / 3}, m.outcome()) for m in recent
    )
    assert model < uniform


def test_historique_vide_ne_plante_pas():
    model = DixonColesModel().fit([])
    assert sum(model.predict_1x2("A", "B").values()) == pytest.approx(1.0)


# ------------------------------------------------------------------------ Elo
def test_elo_classe_correctement(synthetic_history):
    model = EloModel().fit(synthetic_history)
    ordered = sorted(TRUE_ATTACK, key=model.rating, reverse=True)
    assert ordered[0] == "Alpha"
    assert ordered[-1] == "Echo"


def test_elo_produit_une_distribution(synthetic_history):
    model = EloModel().fit(synthetic_history)
    probabilities = model.predict_1x2("Alpha", "Echo")
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert probabilities["HOME"] > probabilities["AWAY"]


def test_elo_le_nul_domine_entre_equipes_egales():
    """Modele de Davidson : deux equipes identiques -> le nul est l'issue la
    plus probable apres l'avantage du terrain."""
    model = EloModel(home_advantage=0.0)
    probabilities = model.predict_1x2("X", "Y")
    assert probabilities["HOME"] == pytest.approx(probabilities["AWAY"])
    assert probabilities["DRAW"] > probabilities["HOME"]


# ------------------------------------------------------------------- ensemble
def test_le_melange_reste_une_distribution():
    market = {"HOME": 0.45, "DRAW": 0.28, "AWAY": 0.27}
    model = {"HOME": 0.55, "DRAW": 0.25, "AWAY": 0.20}
    blended = blend(market, model, None, confidence=1.0)
    assert sum(blended.values()) == pytest.approx(1.0)
    # Le resultat est encadre par les deux sources : pas d'extrapolation.
    assert market["HOME"] < blended["HOME"] < model["HOME"]


def test_confiance_nulle_renvoie_le_marche():
    """Sans donnees, ne jamais parier contre le marche."""
    market = {"HOME": 0.45, "DRAW": 0.28, "AWAY": 0.27}
    model = {"HOME": 0.75, "DRAW": 0.15, "AWAY": 0.10}
    blended = blend(market, model, None, confidence=0.0)
    for key, value in market.items():
        assert blended[key] == pytest.approx(value, abs=0.02)


def test_poids_invalides_rejetes():
    with pytest.raises(ValueError, match="sommer a 1.0"):
        blend({"A": 1.0}, None, None, 1.0, BlendConfig(market_weight=0.9, elo_weight=0.9))


def test_desaccord_mesure_l_ecart():
    identique = {"HOME": 0.5, "DRAW": 0.3, "AWAY": 0.2}
    assert disagreement(identique, identique) == pytest.approx(0.0)
    oppose = disagreement({"HOME": 1.0, "AWAY": 0.0}, {"HOME": 0.0, "AWAY": 1.0})
    assert oppose == pytest.approx(1.0)
