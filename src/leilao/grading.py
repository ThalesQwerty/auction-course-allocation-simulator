"""Aptidão: o único sorteio de que a nota depende (Seção 7.2.2).

A nota não sai de uma normal — sai da **aptidão** do aluno naquela
disciplina, elevada à demanda que ela lhe faz (`equations.grade_for_attempt`).
Aqui fica só o sorteio, porque é a única parte que não é pura; a fórmula da
nota, a conversão da Beta e as políticas de retorno estão em `equations/`.

Nada é sorteado dentro do laço: a aptidão sai da seed na inicialização, como
exige a Seção 7.3.
"""
from __future__ import annotations

import numpy as np

from .config import Discipline, SimulationConfig
from .equations import APTITUDE_GUARD, beta_shape, credit_return, grade_for_attempt
from .equations.grade_histogram import BINS as DISTRIBUTION_BINS
from .equations.grade_histogram import grade_histogram as grade_distribution
from .population import Student

__all__ = [
    "APTITUDE_GUARD",
    "DISTRIBUTION_BINS",
    "beta_shape",
    "credit_return",
    "draw_aptitudes",
    "grade_distribution",
    "grade_for_attempt",
]


def draw_aptitudes(
    students: list[Student],
    disciplines: list[Discipline],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, str], float]:
    """a_{a,x} — a aptidão de cada par (aluno, disciplina), sorteada uma vez.

    É traço, não sorte: não é resorteada por período nem por tentativa, e é o
    que faz "este aluno é bom em matemática e ruim em escrita" significar
    alguma coisa. A Beta é a família natural porque aptidão é uma fração
    limitada — que parcela do máximo esta pessoa alcança —, e ela já nasce em
    (0, 1) sem truncagem.

    Cada aluno sorteia da Beta do **perfil de desempenho** dele, de modo que a
    heterogeneidade é sistemática: há grupos a separar no relatório, e não só
    dispersão. O perfil em si não vem da seed — ver `population`.

    O corte nas pontas evita o 0,0 e o 1,0 exatos que o gerador devolve para
    parâmetros pequenos, e que degenerariam a nota.
    """
    # Uma forma por linha, difundida sobre as colunas: o gerador consome
    # exatamente um sorteio por par (aluno, disciplina), como quando a
    # população inteira saía de uma Beta só.
    shapes = np.array([student.performance.shape for student in students])
    draws = np.clip(
        rng.beta(
            shapes[:, 0:1],
            shapes[:, 1:2],
            size=(len(students), len(disciplines)),
        ),
        APTITUDE_GUARD,
        1.0 - APTITUDE_GUARD,
    )
    return {
        (student.id, discipline.name): float(draws[i, j])
        for i, student in enumerate(students)
        for j, discipline in enumerate(disciplines)
    }
