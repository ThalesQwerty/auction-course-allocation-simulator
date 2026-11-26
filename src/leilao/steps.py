"""O passo de uma execução: a conta do total, o evento e a linha do terminal.

Um passo é uma fase. Cada rodada tem duas — os lances, em que cada aluno resolve
a mochila dele, e a alocação —, e o período tem mais uma no fim, o fechamento,
que é a mochila da exclusão e as notas. São `rodadas × 2 + 1` por período.

O total de uma simulação é `períodos × (rodadas × 2 + 1)`, e é um **teto**: a
rodada que não concede nada fecha o período antes do teto, e por isso o
fechamento credita de uma vez as rodadas que não houve — senão o andamento
pararia nos 90% e só saltaria no fim.

A linha do terminal é **ASCII**: o console do Windows troca a codificação quando
a saída passa por um cano, e acento ali sai quebrado.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from .config import SimulationConfig

__all__ = [
    "CLOSING_STEPS",
    "STAGES_PER_ROUND",
    "OnStep",
    "PeriodSteps",
    "Position",
    "Step",
    "StepTracker",
    "steps_per_period",
    "steps_per_simulation",
    "total_steps",
    "to_terminal",
]

STAGES_PER_ROUND = 2
"""Os lances e a alocação."""

CLOSING_STEPS = 1
"""O fechamento do período: a mochila da exclusão e as notas."""

Stage = Literal["periodo", "rodada", "lances", "alocacao", "fechamento"]


@dataclass(frozen=True)
class Step:
    """Uma fase começando ou terminando. `count` é o que a fase contou: os
    lances que entraram, nos lances, e as vagas que saíram, na alocação."""

    stage: Stage
    period: int
    round: int = 0
    finished: bool = False
    count: int | None = None


@dataclass(frozen=True)
class Position:
    """Onde a simulação está na fila do braço dela, que é o que o log diz."""

    label: str
    seed: int
    ordinal: int
    count: int


OnStep = Callable[[Step], None]
Report = Callable[[int], None]
Log = Callable[[str], None]


def steps_per_period(config: SimulationConfig) -> int:
    return config.rounds * STAGES_PER_ROUND + CLOSING_STEPS


def steps_per_simulation(config: SimulationConfig) -> int:
    return config.periods * steps_per_period(config)


def total_steps(config: SimulationConfig, *, seeds: int, arms: int) -> int:
    """O teto de passos de uma comparação inteira, que se sabe antes de rodar."""
    return steps_per_simulation(config) * seeds * arms


class PeriodSteps:
    """O que um período anuncia. Sem destino, não anuncia nada."""

    def __init__(self, on_step: OnStep | None, *, period: int):
        self.on_step = on_step
        self.period = period

    def started(self) -> None:
        self._emit(Step("periodo", self.period))

    def closing(self) -> None:
        self._emit(Step("fechamento", self.period))

    def closed(self) -> None:
        self._emit(Step("periodo", self.period, finished=True))

    def round_started(self, number: int) -> None:
        self._emit(Step("rodada", self.period, number))

    def bids_ready(self, number: int, *, count: int) -> None:
        self._emit(
            Step("lances", self.period, number, finished=True, count=count)
        )

    def allocated(self, number: int, *, granted: int) -> None:
        self._emit(
            Step("alocacao", self.period, number, finished=True, count=granted)
        )

    def _emit(self, step: Step) -> None:
        if self.on_step is not None:
            self.on_step(step)


def to_terminal(message: str) -> None:
    print(message, flush=True)


class StepTracker:
    """Conta os passos de uma simulação, loga cada fase e avisa quem grava.

    A linha é `[<n>/<N>] <braço> (<pct>%, t: <período>, r: <rodada>) - <o que>`.
    Com vários workers as linhas se intercalam, e é o prefixo que as separa.
    """

    def __init__(
        self,
        *,
        position: Position,
        config: SimulationConfig,
        report: Report | None = None,
        log: Log = to_terminal,
    ):
        self.position = position
        self.per_period = steps_per_period(config)
        self.total = steps_per_simulation(config)
        self.done = 0
        self.rounds = 0
        self._report = report
        self._log = log
        self._phase = perf_counter()
        self._period = perf_counter()
        self._began = perf_counter()

    @property
    def share(self) -> str:
        return f"{100 * self.done / self.total:.0f}%"

    def begin(self) -> None:
        self._began = perf_counter()
        self._say(f"iniciando simulacao com seed {self.position.seed}")

    def end(self) -> None:
        self._say(
            f"simulacao com seed {self.position.seed} concluida em"
            f" {_seconds(perf_counter() - self._began)}"
        )

    def step(self, event: Step) -> None:
        now = perf_counter()
        if event.stage == "periodo" and not event.finished:
            self._period = now
            self.rounds = 0
            self._say("periodo iniciado", event)
        elif event.stage == "periodo":
            self._reach(event.period * self.per_period)
            self._say(
                f"periodo fechado em {_rounds(self.rounds)},"
                f" {_seconds(now - self._period)}",
                event,
            )
        elif event.stage == "fechamento":
            self._phase = now
            self._say("fechando periodo", event)
        elif event.stage == "rodada":
            self.rounds = event.round
            self._phase = now
            self._say("calculando lances", event)
        elif event.stage == "lances":
            self._advance()
            self._say(
                f"{event.count} lances em {_seconds(now - self._phase)}, alocando",
                event,
            )
            self._phase = now
        elif event.stage == "alocacao":
            self._advance()
            self._say(
                f"alocou {_seats(event.count or 0)} em"
                f" {_seconds(now - self._phase)}",
                event,
            )

    def _say(self, message: str, event: Step | None = None) -> None:
        self._log(f"{self._prefix(event)} - {message}")

    def _prefix(self, event: Step | None) -> str:
        head = (
            f"[{self.position.ordinal}/{self.position.count}]"
            f" {self.position.label}"
        )
        where = ""
        if event is not None:
            where = f", t: {event.period}"
            if event.round:
                where += f", r: {event.round}"
        return f"{head} ({self.share}{where})"

    def _advance(self) -> None:
        self._reach(self.done + 1)

    def _reach(self, mark: int) -> None:
        self.done = min(max(self.done, mark), self.total)
        if self._report is not None:
            self._report(self.done)


def _seats(amount: int) -> str:
    return f"{amount} vaga{'' if amount == 1 else 's'}"


def _rounds(amount: int) -> str:
    return f"{amount} rodada{'' if amount == 1 else 's'}"


def _seconds(value: float) -> str:
    return f"{value:.1f} s".replace(".", ",")
