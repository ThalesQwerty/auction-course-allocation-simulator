"""O algoritmo genético: grade inicial, atribuição, seleção e parada."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from leilao.config import Discipline, SimulationConfig
from leilao.equations import Behavior, genome_drift, genome_grid
from leilao.evolution import EvolutionConfig, GenomeLevels, run_evolution
from leilao.simulation import run_simulation
from leilao.simulation.setup import prepare

# Disputa real: a entrada cabe todo mundo (matrícula garantida), e o funil
# aperta depois — é onde o genoma tem o que decidir.
DISCIPLINES = [
    Discipline("A", seats=16, hours=60, entry=True, unlocks=("C", "D", "E")),
    Discipline("B", seats=16, hours=60, entry=True),
    Discipline("C", seats=5, hours=60),
    Discipline("D", seats=5, hours=60),
    Discipline("E", seats=5, hours=60),
]

LEVELS = GenomeLevels(
    beta_u=(0.0, 3.0), beta_v=(-1.0, 1.0), beta_n=(-1.0, 1.0), alpha_u=(0.0, 0.3)
)


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=DISCIPLINES,
        students_per_period=16,
        entry_periods=2,
        periods=10,
        max_hours=120,
        seed=3,
        mechanism="credits",
    )
    return SimulationConfig(**{**base, **overrides})


def test_the_grid_is_the_product_of_the_levels():
    """O tamanho da grade tem de bater com o da coorte: sobrar genótipo faria
    parte dela não rodar, faltar faria alguns pesarem o dobro."""
    grid = genome_grid(
        beta_u=(-1.0, 0.0, 1.0, 2.0, 3.0),
        beta_v=(-1.0, 0.0, 1.0),
        beta_n=(-1.0, 0.0, 1.0),
        alpha_u=(0.0, 0.05, 0.1, 0.2),
    )
    assert len(grid) == 5 * 3 * 3 * 4 == 180
    assert len(set(grid)) == len(grid)


def test_the_default_levels_fill_a_cohort_of_180():
    assert len(GenomeLevels().grid()) == 180


def test_the_drift_is_zero_on_a_still_population():
    assert genome_drift(window=[(1.0, 0.0)] * 5, scales=(1.0, 1.0)) == 0.0
    # Janela de um ponto só não tem o que medir.
    assert genome_drift(window=[(1.0, 0.0)], scales=(1.0, 1.0)) == float("inf")


def test_the_drift_normalizes_each_gene_by_its_own_scale():
    """Sem normalizar, o gene de faixa larga seria a única coisa que a métrica
    enxergaria."""
    wide = genome_drift(window=[(0.0, 0.0), (2.0, 0.0)], scales=(2.0, 0.1))
    narrow = genome_drift(window=[(0.0, 0.0), (0.0, 0.1)], scales=(2.0, 0.1))
    assert wide == pytest.approx(narrow)


def test_a_gene_without_spread_does_not_enter_the_drift():
    """Nível único não tem para onde derivar, e dividir por zero o faria
    dominar tudo."""
    assert genome_drift(window=[(0.0, 5.0), (1.0, 5.0)], scales=(1.0, 0.0)) > 0.0


def test_the_genome_lands_on_the_student_by_position_in_the_cohort():
    picky = Behavior(alpha_u=0.9)
    config = make_config(genomes=((picky,) * 16, (Behavior(),) * 16))

    students = prepare(config).students
    first = [s for s in students if s.entry_period == 1]
    second = [s for s in students if s.entry_period == 2]

    assert all(s.behavior == picky for s in first)
    assert all(s.behavior == Behavior() for s in second)


def test_an_empty_genome_leaves_everyone_on_the_baseline():
    """É assim que a simulação ingênua roda — e é a regressão que garante que
    o campo novo não mexe em cenário que não o usa."""
    assert prepare(make_config()).students[0].behavior == Behavior()
    assert run_simulation(make_config()) == run_simulation(make_config(genomes=()))


def test_the_genome_changes_the_outcome():
    """Reserva alta corta quase tudo do conjunto de escolha, e o resultado
    desaba — a prova de que o gene é expresso."""
    base = sum(s.approved_hours for s in run_simulation(make_config()).students)
    picky = sum(
        s.approved_hours
        for s in run_simulation(
            make_config(genomes=((Behavior(alpha_u=0.9),) * 16,) * 2)
        ).students
    )
    assert picky < base / 2


def test_turning_on_the_genome_does_not_move_the_scenario_draws():
    """Seção 7.3: nenhum sorteio dentro do laço, e o sorteio da evolução sai
    de um fluxo próprio. Ligar os genes não pode deslocar as utilidades nem os
    quantis de desempenho de ninguém."""
    plain = prepare(make_config())
    with_genes = prepare(make_config(genomes=((Behavior(beta_u=2.0),) * 16,) * 2))

    assert plain.utility_rows == with_genes.utility_rows
    assert plain.base_quantiles == with_genes.base_quantiles
    assert plain.availability == with_genes.availability


def test_the_loop_runs_to_the_ceiling_without_a_trigger():
    result = run_evolution(
        make_config(),
        EvolutionConfig(levels=LEVELS, observations=1, max_generations=3, window=2),
    )
    assert len(result.generations) == 3
    assert result.stopped_by == "sem gatilho"
    # Uma linhagem por coorte, em toda geração.
    assert all(len(g.cohorts) == 2 for g in result.generations)


def test_the_floor_holds_the_trigger_back():
    """Um ε enorme dispararia na primeira janela; o mínimo é o que impede uma
    rodada de terminar antes de ter trajetória."""
    result = run_evolution(
        make_config(),
        EvolutionConfig(
            levels=LEVELS,
            observations=1,
            min_generations=4,
            max_generations=8,
            window=2,
            epsilon=10.0,
        ),
    )
    assert len(result.generations) == 4
    assert result.stopped_by == "convergiu"


def test_the_negative_control_ignores_the_threshold_it_exists_to_produce():
    """Um nulo interrompido mediria a deriva da janela mais parada que
    apareceu, e o ε sairia enviesado para baixo — ele vai sempre ao teto."""
    settings = dict(
        levels=LEVELS,
        observations=1,
        min_generations=2,
        max_generations=4,
        window=2,
        epsilon=10.0,
    )
    null = run_evolution(make_config(), EvolutionConfig(**settings, neutral=True))
    real = run_evolution(make_config(), EvolutionConfig(**settings))

    assert len(null.generations) == 4
    assert null.stopped_by == "sem gatilho"
    # O mesmo ε que o nulo ignorou é o que para o real na primeira janela.
    assert real.stopped_by == "convergiu"
    assert len(real.generations) == 2


def test_the_negative_control_carries_the_genome_without_expressing_it():
    """Com o nulo, o genoma é selecionado e mutado mas não chega à simulação:
    as diferenças de aptidão viram ruído, e o que a população andar é deriva."""
    settings = dict(levels=LEVELS, observations=2, max_generations=4, window=2)
    real = run_evolution(make_config(), EvolutionConfig(**settings))
    null = run_evolution(make_config(), EvolutionConfig(**settings, neutral=True))

    assert null.neutral and not real.neutral
    assert len(null.generations) == len(real.generations)
    # A trajetória do nulo não é a do real: ali a seleção não tem o que seguir.
    real_path = [g.cohorts[0].mean for g in real.generations]
    null_path = [g.cohorts[0].mean for g in null.generations]
    assert real_path != null_path


def test_selection_pushes_the_reserve_down():
    """`alpha_u` alto corta o conjunto de escolha e custa carga. A seleção tem
    de empurrá-lo para baixo mais rápido do que a deriva sozinha empurraria."""
    settings = dict(levels=LEVELS, observations=3, max_generations=6, window=3)
    real = run_evolution(make_config(), EvolutionConfig(**settings))
    null = run_evolution(make_config(), EvolutionConfig(**settings, neutral=True))

    reserve = lambda r: r.generations[-1].cohorts[0].mean[3]
    assert reserve(real) < reserve(null)


def test_the_scales_come_from_the_initial_grid():
    result = run_evolution(
        make_config(),
        EvolutionConfig(levels=LEVELS, observations=1, max_generations=1, window=2),
    )
    expected = tuple(
        float(np.std([getattr(b, gene) for b in LEVELS.grid()]))
        for gene in ("beta_u", "beta_v", "beta_n", "alpha_u")
    )
    assert result.scales == pytest.approx(expected)
