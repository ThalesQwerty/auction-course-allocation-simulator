"""A mochila da eq. (50) contra a enumeração exaustiva."""
import itertools
import random

import pytest

from leilao.equations._knapsack import knapsack


def best_by_enumeration(items, values, weights, capacity, conflicts):
    """O ótimo por força bruta, que é o padrão contra o qual o solver responde."""
    best = 0.0
    for size in range(len(items) + 1):
        for combo in itertools.combinations(items, size):
            if sum(weights[name] for name in combo) > capacity:
                continue
            taken = [
                clique for name in combo for clique in conflicts.get(name, ())
            ]
            if len(taken) != len(set(taken)):
                continue
            best = max(best, sum(values[name] for name in combo))
    return best


def test_the_clique_does_not_hide_the_better_pair():
    """O contraexemplo da recorrência que havia antes: ela guardava um estado
    por célula de capacidade e perdia o par melhor quando o item de maior valor
    ocupava o horário de que o outro precisava.
    """
    items = ["A T1", "A T2", "B T1"]
    values = {"A T1": 0.50, "A T2": 0.45, "B T1": 0.40}
    weights = dict.fromkeys(items, 60)
    conflicts = {
        "A T1": ("A", "Diurno 1"),
        "A T2": ("A", "Diurno 2"),
        "B T1": ("B", "Diurno 1"),
    }

    chosen = knapsack(
        items=items,
        values=values,
        weights=weights,
        capacity=120,
        conflicts=conflicts,
    )
    assert chosen == ["A T2", "B T1"]
    assert sum(values[name] for name in chosen) == pytest.approx(0.85)


def test_the_optimum_matches_enumeration_with_two_clique_families():
    """Cada item num clique de disciplina e num de horário, que é a forma de
    `E = M ∪ Q`.
    """
    rng = random.Random(7)
    for _ in range(300):
        disciplines, slots = rng.randint(1, 5), rng.randint(1, 4)
        items, values, weights, conflicts = [], {}, {}, {}
        for discipline in range(disciplines):
            hours = rng.randint(1, 6)
            for sister in range(rng.randint(1, 3)):
                name = f"d{discipline}t{sister}"
                items.append(name)
                weights[name] = hours
                values[name] = round(rng.random(), 3)
                conflicts[name] = (f"D{discipline}", f"H{rng.randrange(slots)}")
        capacity = rng.randint(0, 12)

        chosen = knapsack(
            items=items,
            values=values,
            weights=weights,
            capacity=capacity,
            conflicts=conflicts,
        )
        assert sum(values[name] for name in chosen) == pytest.approx(
            best_by_enumeration(items, values, weights, capacity, conflicts)
        )


def test_the_optimum_matches_enumeration_without_conflicts():
    """Sem clique é a mochila 0-1 clássica, que é a da exclusão ex-post."""
    rng = random.Random(11)
    for _ in range(200):
        items = [f"x{i}" for i in range(rng.randint(1, 10))]
        weights = {name: rng.randint(1, 6) for name in items}
        values = {name: round(rng.random(), 4) for name in items}
        capacity = rng.randint(0, 18)

        chosen = knapsack(
            items=items, values=values, weights=weights, capacity=capacity
        )
        assert sum(weights[name] for name in chosen) <= capacity
        assert sum(values[name] for name in chosen) == pytest.approx(
            best_by_enumeration(items, values, weights, capacity, {})
        )


def test_an_item_in_three_cliques_is_respected():
    """A formulação não depende de quantos cliques cabem num item."""
    items = ["x", "y", "z"]
    values = {"x": 0.5, "y": 0.4, "z": 0.3}
    weights = dict.fromkeys(items, 1)
    conflicts = {"x": ("a", "b", "c"), "y": ("a",), "z": ("c",)}

    assert knapsack(
        items=items,
        values=values,
        weights=weights,
        capacity=3,
        conflicts=conflicts,
    ) == ["y", "z"]


def test_the_item_worth_nothing_stays_out():
    items = ["util", "nulo"]
    assert knapsack(
        items=items,
        values={"util": 0.3, "nulo": 0.0},
        weights=dict.fromkeys(items, 1),
        capacity=9,
    ) == ["util"]


def test_a_negative_capacity_is_refused():
    with pytest.raises(ValueError):
        knapsack(items=["x"], values={"x": 1.0}, weights={"x": 1}, capacity=-1)
