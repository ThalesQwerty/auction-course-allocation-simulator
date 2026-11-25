"""Disponibilidade: a carga horária que o aluno tem para o período.

    log δ_a^(t) = μ + σ · ( √s · P_a + √(1−s) · Q_{a,t} )

`μ` e `σ` são os da log-normal do cenário (`equations.availability_shape`),
`P_a` é o **nível basilar** do aluno — permanente, um por pessoa — e
`Q_{a,t}` é o ruído do semestre. `s` é `availability_stability`, e vale
exatamente a correlação entre dois períodos do mesmo aluno.

Aqui fica só o sorteio, porque é a única parte que não é pura; a conversão em
horas inteiras e a mochila do que o aluno leva estão em
`equations.effective_load` e `equations.retained_set`. O que ele exclui não
devolve crédito nenhum, e por isso não tem conta; a forma da log-normal está em
`equations.availability_shape`, e a repartição da variância em
`equations.preference_split` — a mesma do interesse.

**Em horas, não em fração de W_a.** O teto de carga é do **sistema**, não do
aluno: nada impede alguém de ter tempo para 30 h num curso que oferece 24, e
quem impede a matrícula é o alocador, que nunca entrega mais que W_a durante as
rodadas.

**Uma distribuição só, com nível basilar.** Houve três *perfis* de
disponibilidade até 19/11/2026, e era deles que vinha a persistência: sem eles
e sem `s`, a disponibilidade seria ruído i.i.d. e todos os alunos seriam
idênticos *ex ante* nesse eixo — um corte por quantil fatiaria o sorteio
daquele período, não um tipo de aluno, e as faixas convergiriam para a mesma
curva.

Nada é sorteado dentro do laço: a grade inteira sai da seed na inicialização,
para todos os alunos e todos os períodos de uma vez, como exige a Seção 7.3.

O aluno **não conhece** a própria distribuição nem o sorteio do período
corrente. Se conhecesse a forma, a adaptação da estratégia a ela seria petição
de princípio; se conhecesse o valor realizado antes de pedir, os dois
mecanismos cortariam o pedido no teto certo e a exclusão sumiria dos dois.
"""
from __future__ import annotations

import numpy as np

from .config import SimulationConfig
from .equations import preference_split
from .population import Student

__all__ = ["draw_availability"]


def draw_availability(
    students: list[Student],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, int], float]:
    """δ_{a,t} — as horas disponíveis de cada par (aluno, período)."""
    mean_log, sigma = config.availability_shape()
    levels = np.array([student.availability_level for student in students])
    seasonal = rng.normal(0.0, 1.0, size=(len(students), config.periods))
    combined = preference_split(
        permanent=levels[:, None],
        seasonal=seasonal,
        stability=np.array(config.availability_stability),
        sigma=sigma,
    )
    draws = np.exp(mean_log + combined)
    return {
        (student.id, period + 1): float(draws[i, period])
        for i, student in enumerate(students)
        for period in range(config.periods)
    }


def draw_selectivity(
    students: list[Student],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, int], float]:
    """S_{a,t} — a seletividade de cada par (aluno, período).

        log S_a^(t) = log(mediana) + σ · ( √s · P_a + √(1−s) · Q_{a,t} )

    Mesma família e mesma repartição da disponibilidade, e pela mesma razão:
    sem componente permanente, "este aluno é exigente" não significaria nada
    e o corte por quantil não teria o que separar.

    A diferença é o que o número faz. A disponibilidade é **traço** e age
    depois da vaga — se o aluno larga ou não. A seletividade é **estratégia** e
    age dentro do mecanismo, ao pedir e ao gastar. Ver
    `equations.reserve_threshold`.
    """
    if config.selectivity_median <= 0.0:
        return {
            (student.id, period + 1): 0.0
            for student in students
            for period in range(config.periods)
        }
    levels = np.array([student.selectivity_level for student in students])
    seasonal = rng.normal(0.0, 1.0, size=(len(students), config.periods))
    combined = preference_split(
        permanent=levels[:, None],
        seasonal=seasonal,
        stability=np.array(config.selectivity_stability),
        sigma=config.selectivity_sigma,
    )
    draws = np.exp(np.log(config.selectivity_median) + combined)
    return {
        (student.id, period + 1): float(draws[i, period])
        for i, student in enumerate(students)
        for period in range(config.periods)
    }
