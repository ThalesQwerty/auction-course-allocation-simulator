"""Desempenho base: o único sorteio de que a nota depende (Seção 7.2.2).

A nota não sai de uma normal comum, nem da aptidão elevada à demanda que a
disciplina faz — sai do **quantil** do aluno naquela matéria, lido na normal
dividida daquela tentativa (`equations.grade_for_attempt`). Aqui fica só o
sorteio, porque é a única parte que não é pura; a forma da distribuição, a
transformação por dificuldade e o retorno de créditos estão em `equations/`.

Nada é sorteado dentro do laço: o quantil sai da seed na inicialização, como
exige a Seção 7.3.

Substituiu a aptidão em Beta elevada a um expoente (eq. 33) em 04/11/2026. O
motivo foi o teto: numa distribuição contínua sobre (0, 1), a nota 10 ocupa os
últimos 0,5% do suporte e saía com probabilidade da ordem de 10⁻⁷ mesmo para o
perfil mais forte — ou seja, nunca. O limite da escala é do **instrumento**, não
do aluno: quem mereceria 11 recebe 10 porque a prova vale 10. Modelar o latente
como ilimitado e censurá-lo em [0, 10] põe o limite onde ele existe, e faz da
chance de tirar 10 um parâmetro declarado em vez de consequência escondida da
forma.
"""
from __future__ import annotations

import numpy as np

from .config import Discipline, PerformanceShape, SimulationConfig
from .equations import (
    attempt_rates,
    base_quantile,
    credit_return,
    grade_for_attempt,
    grade_sds,
)
from .equations.grade_histogram import BINS as DISTRIBUTION_BINS
from .equations.grade_histogram import grade_histogram as grade_distribution
from .population import Student

__all__ = [
    "DISTRIBUTION_BINS",
    "GradeShapes",
    "credit_return",
    "draw_base_quantiles",
    "grade_distribution",
    "grade_for_attempt",
]


def draw_base_quantiles(
    students: list[Student],
    disciplines: list[Discipline],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, str], float]:
    """q_{a,x} — a posição de cada par (aluno, disciplina), sorteada uma vez.

        q_{a,x} = Φ( √s · Z_a + √(1−s) · Z_{a,x} )

    O **nível basilar** `Z_a` é do aluno e vale em toda matéria; o desvio
    `Z_{a,x}` é da matéria. `s` (`performance_stability`) é a correlação entre
    os quantis dele em duas disciplinas quaisquer — ver
    `equations.base_quantile`, onde está o porquê de ele não poder ser zero.

    É traço, não sorte: não é resorteada por período nem por tentativa. O
    quantil é a forma certa de guardá-lo porque a distribuição **muda** com a
    dificuldade e com a recursada: a posição relativa do aluno sobrevive à
    mudança, e a nota que ela vale é que se move.

    A marginal continua **uniforme em (0, 1)** por construção, então a
    calibragem da nota não se move com `s`.
    """
    deviations = rng.normal(0.0, 1.0, size=(len(students), len(disciplines)))
    stability = config.performance_stability
    return {
        (student.id, discipline.name): base_quantile(
            level=student.performance_level,
            deviation=float(deviations[i, j]),
            stability=stability,
        )
        for i, student in enumerate(students)
        for j, discipline in enumerate(disciplines)
    }


class GradeShapes:
    """A forma da normal dividida por (dificuldade, tentativa).

    A inversão de `grade_shape` é uma bisseção, e a nota é calculada uma vez
    por (aluno, disciplina, tentativa) — mas as formas **distintas** são
    poucas: as dificuldades da grade vezes as tentativas que alguém chega a
    gastar. Memorizar troca dezenas de milhares de bisseções por algumas
    dezenas.

    Não é estado da simulação: é cache de função pura, e dois `GradeShapes`
    devolvem exatamente a mesma coisa.
    """

    def __init__(self) -> None:
        self._shapes: dict[
            tuple[PerformanceShape, float, int], tuple[float, float, float]
        ] = {}

    def mode(self, shape: PerformanceShape) -> float:
        """A moda da distribuição — fixa, e é ela que a transformação segura."""
        return shape.mode_grade

    def of(
        self, shape: PerformanceShape, difficulty: float, attempt: int
    ) -> tuple[float, float, float]:
        key = (shape, difficulty, attempt)
        if key not in self._shapes:
            mode = self.mode(shape)
            zero_rate, max_rate = attempt_rates(
                zero_rate=shape.zero_rate,
                max_rate=shape.max_rate,
                difficulty=difficulty,
                attempt=attempt,
            )
            left_sd, right_sd = grade_sds(
                mode=mode, zero_rate=zero_rate, max_rate=max_rate
            )
            self._shapes[key] = (mode, left_sd, right_sd)
        return self._shapes[key]
