import math

from leilao.entities import Good
from leilao.metrics import (
    academic_satisfaction_correlation,
    average_satisfaction,
    jain_fairness_index,
    occupation_rate,
    satisfaction_by_agent,
)


def test_satisfaction_full_allocation_gives_one():
    utilities = {("a1", "x1"): 0.6, ("a1", "x2"): 0.4}
    allocation = {("a1", "x1"): 1, ("a1", "x2"): 1}
    result = satisfaction_by_agent(utilities=utilities, allocation=allocation)
    assert math.isclose(result["a1"], 1.0)


def test_satisfaction_partial_allocation():
    utilities = {("a1", "x1"): 0.6, ("a1", "x2"): 0.4}
    allocation = {("a1", "x1"): 1, ("a1", "x2"): 0}
    result = satisfaction_by_agent(utilities=utilities, allocation=allocation)
    assert math.isclose(result["a1"], 0.6)


def test_satisfaction_no_allocation_is_zero():
    utilities = {("a1", "x1"): 1.0}
    result = satisfaction_by_agent(utilities=utilities, allocation={})
    assert result["a1"] == 0.0


def test_average_satisfaction():
    assert average_satisfaction({"a1": 1.0, "a2": 0.5}) == 0.75
    assert average_satisfaction({}) == 0.0


def test_jain_index_perfect_equality_is_one():
    assert math.isclose(jain_fairness_index({"a1": 0.5, "a2": 0.5, "a3": 0.5}), 1.0)


def test_jain_index_full_concentration_is_lower_bound():
    # Um agente concentra tudo, os demais zero -> phi = 1/|A|
    satisfaction = {"a1": 1.0, "a2": 0.0, "a3": 0.0}
    assert math.isclose(jain_fairness_index(satisfaction), 1 / 3)


def test_jain_index_zero_when_all_zero():
    assert jain_fairness_index({"a1": 0.0, "a2": 0.0}) == 0.0


def test_occupation_rate():
    goods = [Good("x1", quantity=2, weight=1), Good("x2", quantity=2, weight=1)]
    allocation = {("a1", "x1"): 1, ("a2", "x1"): 1, ("a1", "x2"): 0}
    assert occupation_rate(goods=goods, allocation=allocation) == 0.5


def test_occupation_rate_no_goods_is_zero():
    assert occupation_rate(goods=[], allocation={}) == 0.0


def test_pearson_correlation_perfect_positive():
    academic_index = {"a1": 1.0, "a2": 2.0, "a3": 3.0}
    satisfaction = {"a1": 0.1, "a2": 0.2, "a3": 0.3}
    corr = academic_satisfaction_correlation(academic_index=academic_index, satisfaction=satisfaction)
    assert math.isclose(corr, 1.0)


def test_pearson_correlation_perfect_negative():
    academic_index = {"a1": 1.0, "a2": 2.0, "a3": 3.0}
    satisfaction = {"a1": 0.9, "a2": 0.5, "a3": 0.1}
    corr = academic_satisfaction_correlation(academic_index=academic_index, satisfaction=satisfaction)
    assert math.isclose(corr, -1.0)


def test_pearson_correlation_undefined_returns_zero():
    assert academic_satisfaction_correlation(academic_index={"a1": 1.0}, satisfaction={"a1": 0.5}) == 0.0
    assert academic_satisfaction_correlation(
        academic_index={"a1": 1.0, "a2": 1.0}, satisfaction={"a1": 0.5, "a2": 0.5}
    ) == 0.0
