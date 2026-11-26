"""O laço que esvazia a fila de uma comparação, gravando no banco."""
from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor

from pathlib import Path

from ..config import SimulationConfig
from ..simulation import run_simulation
from ..steps import Position, StepTracker, steps_per_simulation
from .connection import owner_token
from .lifecycle import (
    Claim,
    Progress,
    claim_simulation,
    fail_comparison,
    fail_simulation,
    finish_comparison,
    finish_simulation,
    progress_of,
    requeue_stale,
    resume_comparison,
)
from .sink import PeriodSink

__all__ = ["run_into_store"]

Done = Callable[[Claim, Progress], None]


def simulate(
    config: SimulationConfig,
    arm: str,
    bank: str,
    simulation_id: int,
    position: Position,
) -> tuple[int, int, int]:
    """Uma simulação, gravando período a período. Devolve (períodos, passos, ms).

    Roda no worker, e por isso é de módulo. O worker abre a própria conexão e
    grava no fechamento de cada período: nada se acumula, e o pai não recebe
    resultado nenhum pelo pickle. Vários workers convivem porque o WAL serializa
    a escrita, e cada commit é de milissegundos contra 66 s de simulação.
    """
    from ..comparison import ARM_BY_KEY, arm_config

    scenario = arm_config(config, arm=ARM_BY_KEY[arm], seed=position.seed)
    started = time.perf_counter()
    with PeriodSink(
        bank, simulation_id=simulation_id, first_measured=scenario.first_measured_period
    ) as sink:
        tracker = StepTracker(
            position=position, config=scenario, report=sink.steps
        )
        tracker.begin()
        result = run_simulation(
            scenario,
            histories="medidos",
            on_period=sink.period,
            on_step=tracker.step,
        )
        sink.students(result, scenario)
        tracker.end()
        periods = sink.written.get("periodo", 0)
    return periods, steps_per_simulation(scenario), round(
        (time.perf_counter() - started) * 1000
    )


def run_into_store(
    connection: sqlite3.Connection,
    *,
    config: SimulationConfig,
    bank: str | Path,
    workers: int = 1,
    on_done: Done | None = None,
) -> Progress:
    """Roda o que falta e devolve o andamento. Serve de começo e de retomada.

    Quem grava é este processo, não os workers: o SQLite admite um escritor por
    vez, e a fronteira de transação tem de coincidir com a de simulação para a
    retomada funcionar.
    """
    owner = owner_token()
    requeue_stale(connection, owner=owner)
    resume_comparison(connection)
    started = time.perf_counter()

    try:
        if workers <= 1:
            _one_at_a_time(connection, config, owner, str(bank), on_done)
        else:
            _in_parallel(connection, config, owner, str(bank), workers, on_done)
    except BaseException as erro:
        fail_comparison(
            connection, error=f"{type(erro).__name__}: {erro}"
        )
        raise

    andamento = progress_of(connection)
    if andamento.done:
        finish_comparison(
            connection,
                        elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
    return andamento


def _one_at_a_time(connection, config, owner, bank, on_done) -> None:
    queue = _Queue(connection)
    while not _paused(connection):
        claim = claim_simulation(
            connection, owner=owner
        )
        if claim is None:
            return
        try:
            periods, steps, duration = simulate(
                config,
                claim.arm,
                bank,
                claim.simulation_id,
                queue.position(claim),
            )
        except Exception as erro:
            _failed(connection, claim, erro)
        else:
            finish_simulation(
                connection,
                simulation_id=claim.simulation_id,
                periods=periods,
                duration_ms=duration,
                steps=steps,
            )
        if on_done is not None:
            on_done(claim, progress_of(connection))


def _in_parallel(connection, config, owner, bank, workers, on_done) -> None:
    """Cada worker grava o seu. O pai só cuida da fila e do estado."""
    queue = _Queue(connection)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        em_voo: dict[Future, Claim] = {}
        while True:
            while len(em_voo) < workers and not _paused(connection):
                claim = claim_simulation(
                    connection, owner=owner
                )
                if claim is None:
                    break
                em_voo[
                    pool.submit(
                        simulate,
                        config,
                        claim.arm,
                        bank,
                        claim.simulation_id,
                        queue.position(claim),
                    )
                ] = claim
            if not em_voo:
                return
            claim = em_voo.pop(pronto := _wait_any(em_voo))
            try:
                periods, steps, duration = pronto.result()
            except Exception as erro:
                _failed(connection, claim, erro)
            else:
                finish_simulation(
                    connection,
                    simulation_id=claim.simulation_id,
                    periods=periods,
                    duration_ms=duration,
                    steps=steps,
                )
            if on_done is not None:
                on_done(claim, progress_of(connection))


class _Queue:
    """Em que ponto da fila do braço uma simulação entrou, para o log.

    É a ordem de execução, não a dos ids: a fila roda por seed e os ids são por
    braço. Numa retomada a contagem continua de onde a anterior parou.
    """

    def __init__(self, connection: sqlite3.Connection):
        row = connection.execute("SELECT seeds FROM comparacao").fetchone()
        self.count = int(row["seeds"]) if row is not None else 0
        self.started = {
            linha["braco"]: int(linha["prontas"])
            for linha in connection.execute(
                "SELECT braco, SUM(estado IN ('concluida', 'falhou')) AS prontas"
                "  FROM simulacao GROUP BY braco"
            )
        }

    def position(self, claim: Claim) -> Position:
        from ..comparison import ARM_BY_KEY

        self.started[claim.arm] = self.started.get(claim.arm, 0) + 1
        return Position(
            label=ARM_BY_KEY[claim.arm].short,
            seed=claim.seed,
            ordinal=self.started[claim.arm],
            count=self.count,
        )


def _wait_any(em_voo: dict[Future, Claim]) -> Future:
    from concurrent.futures import FIRST_COMPLETED, wait

    pronto, _ = wait(list(em_voo), return_when=FIRST_COMPLETED)
    return next(iter(pronto))


def _failed(connection, claim: Claim, erro: BaseException) -> None:
    fail_simulation(
        connection,
        simulation_id=claim.simulation_id,
        error=f"{type(erro).__name__}: {erro}",
    )


def _paused(connection: sqlite3.Connection) -> bool:
    estado = connection.execute("SELECT estado FROM comparacao").fetchone()
    return estado is not None and estado["estado"] == "pausada"
