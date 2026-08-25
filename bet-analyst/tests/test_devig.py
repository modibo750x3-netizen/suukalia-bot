"""Le devigging est la brique la plus critique : une erreur ici fausse tout."""

from __future__ import annotations

import pytest

from suukalia.analysis.devig import devig, fair_odds, implied_probabilities, shin_z

FAVOURITE = {"HOME": 1.50, "DRAW": 4.20, "AWAY": 6.50}
BALANCED = {"HOME": 2.10, "DRAW": 3.40, "AWAY": 3.60}


@pytest.mark.parametrize("method", ["multiplicative", "power", "shin"])
@pytest.mark.parametrize("odds", [FAVOURITE, BALANCED])
def test_devig_produit_une_distribution(method, odds):
    probabilities = devig(odds, method)
    assert sum(probabilities.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(0.0 < p < 1.0 for p in probabilities.values())


@pytest.mark.parametrize("method", ["multiplicative", "power", "shin"])
def test_devig_preserve_l_ordre_des_issues(method):
    probabilities = devig(FAVOURITE, method)
    assert probabilities["HOME"] > probabilities["DRAW"] > probabilities["AWAY"]


def test_devig_retire_bien_la_marge():
    """Les probabilites brutes somment a plus de 1 ; les probabilites fair a 1."""
    assert sum(implied_probabilities(BALANCED).values()) > 1.0
    assert sum(devig(BALANCED, "shin").values()) == pytest.approx(1.0)


def test_shin_et_power_corrigent_le_biais_outsider():
    """Le multiplicatif attribue trop de probabilite aux gros outsiders.

    Shin et power redistribuent la marge de facon non uniforme : l'outsider
    recoit moins, le favori davantage. C'est exactement la correction du
    favourite-longshot bias, et c'est ce qui evite de croire a une value bet
    sur chaque cote a 6.50.
    """
    multiplicative = devig(FAVOURITE, "multiplicative")
    for method in ("shin", "power"):
        corrected = devig(FAVOURITE, method)
        assert corrected["AWAY"] < multiplicative["AWAY"]
        assert corrected["HOME"] > multiplicative["HOME"]


def test_marche_sans_marge_est_inchange():
    """Un marche deja fair ne doit pas etre deforme."""
    exact = {"HOME": 2.0, "DRAW": 4.0, "AWAY": 4.0}
    assert devig(exact, "shin")["HOME"] == pytest.approx(0.5, abs=1e-6)


def test_shin_z_croit_avec_la_marge():
    serre = {"HOME": 2.05, "DRAW": 3.50, "AWAY": 3.75}
    large = {"HOME": 1.85, "DRAW": 3.10, "AWAY": 3.30}
    assert shin_z(large) > shin_z(serre) >= 0.0


def test_fair_odds_est_l_inverse_des_probabilites():
    probabilities = devig(BALANCED, "shin")
    assert fair_odds(probabilities)["HOME"] == pytest.approx(1.0 / probabilities["HOME"])


def test_entrees_degenerees_ne_plantent_pas():
    assert sum(devig({"HOME": 0.0, "AWAY": 0.0}).values()) == pytest.approx(1.0)


def test_methode_inconnue_leve_une_erreur():
    with pytest.raises(ValueError, match="methode de devig inconnue"):
        devig(BALANCED, "magique")
