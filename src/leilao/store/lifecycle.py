"""O ciclo de vida de uma comparação e das simulações dela."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import SimulationConfig
from ..steps import total_steps
from .connection import transaction

__all__ = [
    "Claim",
    "Progress",
    "claim_simulation",
    "create_comparison",
    "fail_comparison",
    "fail_simulation",
    "finish_comparison",
    "finish_simulation",
    "pause_comparison",
    "progress_of",
    "requeue_stale",
    "resume_comparison",
    "timeout_simulation",
]

DETAIL_TABLES = (
    "solicitacao",
    "aluno_periodo",
    "turma_periodo",
    "rodada",
    "periodo",
    "aluno",
)
"""As tabelas que uma simulação enche. O `ON DELETE CASCADE` as limparia, mas
apagá-las na mão deixa a limpeza funcionar mesmo sem `foreign_keys = ON`."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Claim:
    """Uma simulação que este processo pegou para rodar."""

    simulation_id: int
    arm: str
    seed: int
    attempt: int


@dataclass(frozen=True)
class Progress:
    """Quantas simulações da comparação estão em cada estado."""

    pendente: int = 0
    rodando: int = 0
    concluida: int = 0
    falhou: int = 0
    estourou: int = 0

    @property
    def total(self) -> int:
        return (
            self.pendente
            + self.rodando
            + self.concluida
            + self.falhou
            + self.estourou
        )

    @property
    def done(self) -> bool:
        """A fila esvaziou: nada pendente nem rodando."""
        return self.pendente == 0 and self.rodando == 0


def create_comparison(
    connection: sqlite3.Connection,
    *,
    config: SimulationConfig,
    scenario: str,
    seeds: int,
    arms: Sequence[str],
    label: str | None = None,
) -> None:
    """Cria a comparação `pendente`, a oferta e a fila de simulações.

    Não roda nada: separar criar de rodar é o que torna pausa e retomada
    endereçáveis. `scenario` é o pedido inteiro já serializado, de modo que o
    banco não conhece os tipos da API.
    """
    if seeds <= 0:
        raise ValueError("uma comparação precisa de ao menos uma seed")
    if not arms:
        raise ValueError("uma comparação precisa de ao menos um braço")

    with transaction(connection):
        connection.execute(
            "INSERT INTO comparacao"
            " (rotulo, criada_em, estado, cenario, seeds, bracos,"
            "  coorte_medida, rodadas_teto, etapas_total)"
            " VALUES (?, ?, 'pendente', ?, ?, ?, ?, ?, ?)",
            (
                label,
                now(),
                scenario,
                seeds,
                ",".join(arms),
                config.measured_cohort,
                config.rounds,
                total_steps(config, seeds=seeds, arms=len(arms)),
            ),
        )
        connection.executemany(
            "INSERT INTO turma"
            " (turma, disciplina, carga, horario,"
            "  periodo_da_grade, optativa, entrada, vagas)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            _classes(config),
        )
        connection.executemany(
            "INSERT INTO simulacao (braco, seed, estado)"
            " VALUES (?, ?, 'pendente')",
            [
                (arm, seed)
                for arm in arms
                for seed in range(config.first_seed, config.first_seed + seeds)
            ],
        )


def _classes(config: SimulationConfig) -> list[tuple]:
    """A oferta expandida em turmas, que o cenário já sabe sem simular."""
    discipline_of = config.discipline_by_class()
    hours = config.hours_by_class()
    seats = config.seats_by_class()
    schedule = config.schedule_by_class()
    curriculum = config.curriculum_periods()
    by_name = {d.name: d for d in config.disciplines}
    return [
        (
            name,
            discipline,
            hours[name],
            schedule[name],
            None if by_name[discipline].elective else curriculum.get(discipline),
            int(by_name[discipline].elective),
            int(by_name[discipline].entry),
            seats[name],
        )
        for name, discipline in discipline_of.items()
    ]


def claim_simulation(
    connection: sqlite3.Connection, *, owner: str
) -> Claim | None:
    """Pega a próxima simulação `pendente`, ou `None` se a fila esvaziou.

    A tomada é uma transação só, para dois processos não pegarem a mesma.
    """
    with transaction(connection):
        row = connection.execute(
            "SELECT id, braco, seed, tentativas FROM simulacao"
            " WHERE estado = 'pendente'"
            " ORDER BY seed, braco LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE simulacao"
            " SET estado = 'rodando', dono = ?, iniciada_em = ?, terminada_em = NULL,"
            "     duracao_ms = NULL, etapas = 0, erro = NULL"
            " WHERE id = ?",
            (owner, now(), row["id"]),
        )
    return Claim(
        simulation_id=int(row["id"]),
        arm=row["braco"],
        seed=int(row["seed"]),
        attempt=int(row["tentativas"]) + 1,
    )


def requeue_stale(
    connection: sqlite3.Connection, *, owner: str
) -> int:
    """Devolve à fila o que ficou `rodando` sob outro dono, e diz quantas.

    `rodando` num processo que não é este é a interrupção: ninguém está vivo
    para escrever "interrompida", então é o dono morto que a denuncia. As linhas
    dessas simulações estão parciais e vão embora; `tentativas` guarda que
    aquela seed já foi interrompida antes.
    """
    with transaction(connection):
        rows = connection.execute(
            "SELECT id FROM simulacao"
            " WHERE estado = 'rodando' AND (dono IS NULL OR dono <> ?)",
            (owner,),
        ).fetchall()
        if not rows:
            return 0
        stale = [(int(row["id"]),) for row in rows]
        for table in DETAIL_TABLES:
            connection.executemany(
                f"DELETE FROM {table} WHERE simulacao_id = ?", stale
            )
        connection.executemany(
            "UPDATE simulacao"
            " SET estado = 'pendente', dono = NULL, iniciada_em = NULL,"
            "     terminada_em = NULL, duracao_ms = NULL, etapas = 0,"
            "     tentativas = tentativas + 1"
            " WHERE id = ?",
            stale,
        )
    return len(stale)


def finish_simulation(
    connection: sqlite3.Connection,
    *,
    simulation_id: int,
    periods: int,
    duration_ms: int,
    steps: int | None = None,
) -> None:
    """Fecha a simulação. `steps` é o teto dela, para o andamento bater em 100%:
    a simulação que parou antes do teto de rodadas deu menos passos do que a
    conta previa, e o que faltou entra aqui de uma vez."""
    with transaction(connection):
        connection.execute(
            "UPDATE simulacao"
            " SET estado = 'concluida', dono = NULL, terminada_em = ?,"
            "     duracao_ms = ?, periodos = ?,"
            "     etapas = COALESCE(?, etapas)"
            " WHERE id = ?",
            (now(), duration_ms, periods, steps, simulation_id),
        )


def fail_simulation(
    connection: sqlite3.Connection,
    *,
    simulation_id: int,
    error: str,
    duration_ms: int | None = None,
) -> None:
    """Marca a falha e **mantém** as linhas parciais, que servem de autópsia.

    A retomada não tenta de novo: uma exceção determinística se repetiria igual
    na mesma seed, e tentar viraria laço.
    """
    _stop(connection, simulation_id, "falhou", error, duration_ms)


def timeout_simulation(
    connection: sqlite3.Connection,
    *,
    simulation_id: int,
    error: str,
    duration_ms: int | None = None,
) -> None:
    """Marca o tempo esgotado, que não é falha: a instância era resolvível.

    A retomada também não tenta de novo, e a seed sai do resultado nos dois
    braços — quem a tira é a view `simulacao_valida`, na leitura.
    """
    _stop(connection, simulation_id, "estourou", error, duration_ms)


def _stop(
    connection: sqlite3.Connection,
    simulation_id: int,
    state: str,
    error: str,
    duration_ms: int | None,
) -> None:
    with transaction(connection):
        connection.execute(
            "UPDATE simulacao"
            " SET estado = ?, dono = NULL, terminada_em = ?,"
            "     duracao_ms = ?, erro = ?"
            " WHERE id = ?",
            (state, now(), duration_ms, error, simulation_id),
        )


def progress_of(connection: sqlite3.Connection) -> Progress:
    rows = connection.execute(
        "SELECT estado, COUNT(*) AS quantas FROM simulacao GROUP BY estado"
    ).fetchall()
    return Progress(**{row["estado"]: int(row["quantas"]) for row in rows})


def resume_comparison(connection: sqlite3.Connection) -> None:
    """Põe a comparação a rodar, começando ou retomando. Carimba o início uma vez."""
    with transaction(connection):
        connection.execute(
            "UPDATE comparacao"
            " SET estado = 'rodando', erro = NULL,"
            "     iniciada_em = COALESCE(iniciada_em, ?)",
            (now(),),
        )


def pause_comparison(connection: sqlite3.Connection) -> None:
    """Pede a pausa. O laço para na próxima fronteira, não na hora."""
    with transaction(connection):
        connection.execute(
            "UPDATE comparacao SET estado = 'pausada'"
        )


def finish_comparison(
    connection: sqlite3.Connection, *, elapsed_ms: int
) -> None:
    """Fecha a comparação, somando o trecho ao que já havia corrido antes da pausa."""
    with transaction(connection):
        connection.execute(
            "UPDATE comparacao"
            " SET estado = 'concluida', terminada_em = ?,"
            "     duracao_ms = COALESCE(duracao_ms, 0) + ?",
            (now(), elapsed_ms),
        )


def fail_comparison(
    connection: sqlite3.Connection, *, error: str
) -> None:
    """O próprio laço quebrou, que é diferente de uma simulação ter falhado."""
    with transaction(connection):
        connection.execute(
            "UPDATE comparacao SET estado = 'falhou', erro = ?", (error,)
        )
