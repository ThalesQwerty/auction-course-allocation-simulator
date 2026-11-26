"""O passo da execução: a conta do teto e o que o motor anuncia."""
from __future__ import annotations

from disciplines import disciplines_from_predecessors
from profiles import single_axis
from leilao.config import SimulationConfig
from leilao.simulation import run_simulation
from leilao.steps import (
    Position,
    Step,
    StepTracker,
    steps_per_period,
    steps_per_simulation,
    total_steps,
)

GRADE = disciplines_from_predecessors(
    ("D1", 12, 60),
    ("D2", 12, 60),
    ("D3", 12, 60, ("D1",)),
    ("D4", 12, 60, ("D2",)),
)

WORKLOAD = 180

POSITION = Position(label="Leilao", seed=1, ordinal=1, count=20)


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=7,
        warmup_periods=4,
        max_residence=4,
        students_per_entry_class=3,
        rounds=2,
        max_hours=WORKLOAD,
        elective_hours=0,
        **single_axis(WORKLOAD),
        seed=1,
    )
    return SimulationConfig(**{**base, **overrides})


def test_the_ceiling_is_two_phases_per_round_plus_the_closing():
    config = make_config(periods=7, rounds=2)

    assert steps_per_period(config) == 5
    assert steps_per_simulation(config) == 35
    assert total_steps(config, seeds=20, arms=2) == 1_400


def test_the_engine_announces_the_two_phases_of_every_round_and_the_closing():
    config = make_config()
    vistos: list[Step] = []

    run_simulation(config, histories="nenhum", on_step=vistos.append)

    primeiro = [step for step in vistos if step.period == 1]
    assert [step.stage for step in primeiro][:4] == [
        "periodo",
        "rodada",
        "lances",
        "alocacao",
    ]
    assert [step.stage for step in primeiro][-2:] == ["fechamento", "periodo"]
    for rodada in {step.round for step in primeiro if step.stage == "rodada"}:
        fases = [
            step.stage
            for step in primeiro
            if step.round == rodada and step.stage != "periodo"
        ]
        assert fases == ["rodada", "lances", "alocacao"]


def test_the_skipped_round_is_credited_when_the_period_closes():
    """A rodada que não houve conta como concluída: senão a porcentagem pararia
    abaixo de 100% em todo período que fechou antes do teto de rodadas."""
    config = make_config(rounds=6)
    tracker = StepTracker(position=POSITION, config=config, log=lambda _: None)
    por_periodo = steps_per_period(config)
    fechados = []

    run_simulation(
        config,
        histories="nenhum",
        on_step=lambda step: (
            tracker.step(step),
            fechados.append(tracker.done)
            if step.stage == "periodo" and step.finished
            else None,
        ),
    )

    assert fechados == [por_periodo * (ordem + 1) for ordem in range(len(fechados))]
    assert tracker.done == tracker.total
    assert tracker.share == "100%"


def test_the_tracker_reports_every_step_to_whoever_writes():
    config = make_config()
    gravados: list[int] = []
    tracker = StepTracker(
        position=POSITION,
        config=config,
        report=gravados.append,
        log=lambda _: None,
    )

    run_simulation(config, histories="nenhum", on_step=tracker.step)

    assert gravados == sorted(gravados)
    assert gravados[-1] == steps_per_simulation(config)


def test_the_line_says_the_arm_the_position_the_share_and_where_it_is():
    """O terminal recebe ASCII: a saída do Windows troca de codificação quando
    passa por um cano, e acento ali sai quebrado."""
    config = make_config(periods=7, rounds=2)
    linhas: list[str] = []
    tracker = StepTracker(position=POSITION, config=config, log=linhas.append)

    tracker.begin()
    tracker.step(Step("periodo", 3))
    tracker.step(Step("rodada", 3, 2))
    tracker.step(Step("alocacao", 3, 2, finished=True, count=7))

    assert linhas[0] == "[1/20] Leilao (0%) - iniciando simulacao com seed 1"
    assert linhas[1] == "[1/20] Leilao (0%, t: 3) - periodo iniciado"
    assert linhas[2] == "[1/20] Leilao (0%, t: 3, r: 2) - calculando lances"
    assert linhas[3].startswith(
        "[1/20] Leilao (3%, t: 3, r: 2) - alocou 7 vagas em "
    )
    assert all(linha.isascii() for linha in linhas)
