"""Primitives numeriques."""

from __future__ import annotations

import math

import pytest

from suukalia.mathx import (
    brier_score,
    clamp,
    log_loss,
    log_pool,
    normalise,
    normalise_dict,
    poisson_pmf,
    shrink_towards,
)


def test_poisson_somme_a_un():
    assert sum(poisson_pmf(k, 1.5) for k in range(40)) == pytest.approx(1.0, abs=1e-9)


def test_poisson_valeurs_connues():
    assert poisson_pmf(0, 2.0) == pytest.approx(math.exp(-2.0))
    assert poisson_pmf(1, 2.0) == pytest.approx(2.0 * math.exp(-2.0))
    assert poisson_pmf(-1, 2.0) == 0.0


def test_normalisation():
    assert normalise([1, 1, 2]) == pytest.approx([0.25, 0.25, 0.5])
    assert normalise([0, 0, 0]) == pytest.approx([1 / 3, 1 / 3, 1 / 3])
    assert normalise([-1, 1]) == pytest.approx([0.0, 1.0])


def test_clamp():
    assert clamp(5, 0, 1) == 1
    assert clamp(-5, 0, 1) == 0
    assert clamp(0.5, 0, 1) == 0.5


def test_pooling_logarithmique_reste_encadre():
    """Le pool ne doit jamais sortir de l'enveloppe des sources."""
    a = {"X": 0.7, "Y": 0.3}
    b = {"X": 0.4, "Y": 0.6}
    pooled = log_pool([a, b], [0.5, 0.5])
    assert sum(pooled.values()) == pytest.approx(1.0)
    assert b["X"] < pooled["X"] < a["X"]


def test_pooling_respecte_les_poids():
    a = {"X": 0.8, "Y": 0.2}
    b = {"X": 0.2, "Y": 0.8}
    assert log_pool([a, b], [0.9, 0.1])["X"] > log_pool([a, b], [0.5, 0.5])["X"]


def test_shrink_vers_une_cible_explicite():
    source = {"A": 0.8, "B": 0.2}
    cible = {"A": 0.4, "B": 0.6}
    assert shrink_towards(source, cible, 0.0)["A"] == pytest.approx(0.8)
    assert shrink_towards(source, cible, 1.0)["A"] == pytest.approx(0.4)
    assert shrink_towards(source, cible, 0.5)["A"] == pytest.approx(0.6)


def test_scores_de_qualite():
    parfait = {"A": 1.0, "B": 0.0}
    assert brier_score(parfait, "A") == pytest.approx(0.0)
    assert log_loss(parfait, "A") == pytest.approx(0.0)
    # Une certitude fausse est severement punie.
    assert log_loss(parfait, "B") > 20.0


def test_log_loss_penalise_la_sur_confiance():
    prudent = {"A": 0.6, "B": 0.4}
    confiant = {"A": 0.95, "B": 0.05}
    assert log_loss(confiant, "B") > log_loss(prudent, "B")


def test_normalise_dict_preserve_les_cles():
    result = normalise_dict({"A": 2.0, "B": 2.0})
    assert set(result) == {"A", "B"}
    assert result["A"] == pytest.approx(0.5)
