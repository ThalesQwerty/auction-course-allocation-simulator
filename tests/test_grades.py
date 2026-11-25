"""As contas novas da nota e da perturbação, e o que elas prometem."""
import numpy as np
import pytest

from leilao.equations import (
    attempt_approval,
    attendance,
    grade_for_attempt,
    grade_mean,
    mean_round,
    reflect,
    reflect_array,
    reflected_anchor,
    standard_normal_quantiles,
)


def test_the_reflection_folds_anything_into_the_unit_interval():
    for value in (-7.3, -1.0, -0.2, 0.0, 0.5, 1.0, 1.3, 2.0, 2.4, 9.9):
        assert 0.0 <= reflect(value) <= 1.0


def test_the_reflection_mirrors_at_both_edges():
    assert reflect(1.2) == pytest.approx(0.8)
    assert reflect(-0.2) == pytest.approx(0.2)
    assert reflect(0.3) == pytest.approx(reflect(2.3))
    assert reflect(0.3) == pytest.approx(reflect(-1.7))


def test_the_reflection_preserves_the_uniform_marginal():
    """A promessa que faz a distribuição realizada ser a declarada: âncora"""
    rng = np.random.default_rng(0)
    anchors = rng.random(200_000)
    for sd in (0.1, 0.5, 1.0, 2.0):
        folded = reflect_array(anchors + rng.normal(0.0, sd, anchors.shape))
        counts, _ = np.histogram(folded, bins=10, range=(0.0, 1.0))
        shares = counts / len(folded)
        assert np.all(np.abs(shares - 0.1) < 0.005), sd


def test_the_anchor_rejects_a_position_outside_the_interval():
    with pytest.raises(ValueError):
        reflected_anchor(anchor=1.5, shock=0.0)


def test_without_a_shock_the_anchor_is_the_position():
    for anchor in (0.0, 0.2, 0.5, 0.9, 1.0):
        assert reflected_anchor(anchor=anchor, shock=0.0) == pytest.approx(anchor)


def test_the_mean_puts_the_declared_share_above_the_threshold():
    """A inversão mira o limiar da nota **arredondada**, que é meio décimo"""
    for rate in (0.2, 0.5, 0.8):
        mean = grade_mean(min_grade=5.0, grade_sd=2.0, approval_rate=rate)
        realized = 1.0 - float(
            np.mean(
                np.array(
                    [
                        grade_for_attempt(
                            quantile=q / 50_000, grade_mean=mean, grade_sd=2.0
                        )
                        for q in range(1, 50_000)
                    ]
                )
                < 5.0
            )
        )
        assert abs(realized - rate) < 0.01


def test_the_mean_rejects_an_impossible_parameter():
    with pytest.raises(ValueError):
        grade_mean(min_grade=5.0, grade_sd=0.0, approval_rate=0.5)
    with pytest.raises(ValueError):
        grade_mean(min_grade=5.0, grade_sd=2.0, approval_rate=1.0)


def test_the_repetition_gain_has_both_ends_meaningful():
    base = dict(approval_rate=0.4)
    sem = [
        attempt_approval(**base, repetition_gain=0.0, previous_attempts=k)
        for k in range(4)
    ]
    assert len(set(sem)) == 1, "sem ganho, toda tentativa é a primeira"

    cheio = [
        attempt_approval(**base, repetition_gain=1.0, previous_attempts=k)
        for k in range(4)
    ]
    assert cheio == sorted(cheio), "repetir nunca piora"
    assert cheio[0] == pytest.approx(0.4)
    assert cheio[1] == pytest.approx(0.4 ** (1 / 2))


def test_the_expected_attempts_barely_move_when_approval_is_high():
    """A alavanca é fraca com aprovação alta, e é por isso que quem controla a"""

    def expected(rate: float, gain: float) -> float:
        total, survival = 1.0, 1.0
        for k in range(1, 40):
            survival *= 1.0 - attempt_approval(
                approval_rate=rate, repetition_gain=gain, previous_attempts=k - 1
            )
            total += survival
        return total

    assert abs(expected(0.7, 0.0) - 1.43) < 0.01
    assert abs(expected(0.7, 1.0) - 1.36) < 0.01
    assert abs(expected(0.35, 0.0) - 2.86) < 0.01
    assert abs(expected(0.35, 1.0) - 2.02) < 0.01


def test_the_vectorized_inverse_matches_the_scalar_one():
    from statistics import NormalDist

    p = np.array([1e-9, 1e-4, 0.02, 0.1, 0.5, 0.9, 0.98, 0.9999, 1 - 1e-9])
    got = standard_normal_quantiles(p)
    want = np.array([NormalDist().inv_cdf(float(x)) for x in p])
    assert np.max(np.abs(got - want)) < 1e-8


def test_the_attendance_is_in_hours_and_can_invert_the_seat_count():
    """A unidade não é detalhe: por vaga um braço ganha, por carga o outro."""
    hours = {f"x{i}": h for i, h in enumerate([6, 1, 1, 1] + [3] * 6)}
    won = list(hours)

    a = [name for name in won if name != "x0"]
    b = [name for name in won if name not in ("x1", "x2", "x3")]

    por_vaga_a, por_vaga_b = len(a) / len(won), len(b) / len(won)
    por_carga_a = attendance(won=won, attended=a, hours=hours)
    por_carga_b = attendance(won=won, attended=b, hours=hours)

    assert por_vaga_a > por_vaga_b
    assert por_carga_a < por_carga_b


def test_the_attendance_has_no_value_without_a_denominator():
    assert attendance(won=[], attended=[], hours={}) is None


def test_the_mean_round_weighs_by_what_each_round_granted():
    assert mean_round(allocations_per_round=[10, 10]) == pytest.approx(1.5)
    assert mean_round(allocations_per_round=[30, 0, 0]) == pytest.approx(1.0)
    assert mean_round(allocations_per_round=[0, 0, 5]) == pytest.approx(3.0)
    assert mean_round(allocations_per_round=[0, 0]) is None
