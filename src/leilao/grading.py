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

    O corte nas pontas evita o 0,0 e o 1,0 exatos que o gerador devolve para
    parâmetros pequenos, e que degenerariam a nota.
    """
    draws = np.clip(
        rng.beta(
            config.aptitude_alpha,
            config.aptitude_beta,
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
