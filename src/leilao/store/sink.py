"""O destino que recebe cada período fechado e o grava.

Escrever no fechamento de **cada período**, e não no fim, é o que impede o
worker de acumular: o que crescia era a lista de relatórios de período e o
histórico de todo aluno, e os dois são soltos assim que a linha entra. Dentro
de um período só cabe a coorte medida, que são algumas centenas de linhas.

O worker abre a própria conexão. Um pickle de 30 MB por simulação some, e vários
escritores convivem porque o WAL serializa a escrita em commits de milissegundos.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import SimulationConfig
from ..simulation import SimulationResult
from .connection import open_store, transaction
from .rows import (
    classes_of,
    period_of,
    requests_of,
    rounds_of,
    student_periods_of,
    student_rows,
)
from .writes import INSERTS

__all__ = ["PeriodSink"]


class PeriodSink:
    """Recebe um período fechado por vez e grava numa transação."""

    def __init__(self, path: str | Path, *, simulation_id: int, first_measured: int):
        self.connection: sqlite3.Connection = open_store(path, create=False)
        self.simulation_id = simulation_id
        self.first_measured = first_measured
        self.written: dict[str, int] = {}

    def __enter__(self) -> "PeriodSink":
        return self

    def __exit__(self, *_) -> None:
        self.connection.close()

    def period(self, outcome) -> None:
        """A fronteira de commit: um período e as rodadas dele, de uma vez."""
        grupos = {
            "periodo": [period_of(self.simulation_id, outcome, self.first_measured)],
            "rodada": rounds_of(self.simulation_id, outcome),
            "aluno_periodo": student_periods_of(self.simulation_id, outcome),
            "solicitacao": requests_of(self.simulation_id, outcome),
            "turma_periodo": classes_of(self.simulation_id, outcome),
        }
        self._insert(grupos)

    def steps(self, done: int) -> None:
        """Quantos passos esta simulação já deu. Uma linha, fora da transação do
        período: é o que a tela lê para desenhar a porcentagem enquanto roda."""
        with transaction(self.connection):
            self.connection.execute(
                "UPDATE simulacao SET etapas = ? WHERE id = ?",
                (done, self.simulation_id),
            )

    def students(self, result: SimulationResult, config: SimulationConfig) -> None:
        """A tabela `aluno`, no fim: CR final e desfecho só se sabem no fim."""
        self._insert({"aluno": student_rows(self.simulation_id, result, config)})

    def _insert(self, grupos: dict[str, list[tuple]]) -> None:
        with transaction(self.connection):
            for tabela, linhas in grupos.items():
                if linhas:
                    self.connection.executemany(INSERTS[tabela], linhas)
        for tabela, linhas in grupos.items():
            self.written[tabela] = self.written.get(tabela, 0) + len(linhas)
