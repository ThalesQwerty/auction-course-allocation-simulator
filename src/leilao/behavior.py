"""Comportamento dos alunos: utilidades percebidas e lances (Seção 7.2.4).

A matriz de utilidades u^(t) é **parâmetro de entrada**, como as notas: todo o
sorteio acontece na inicialização, a partir da `seed`, para todos os alunos e
todos os períodos de uma vez (`draw_utilities`). Em tempo de execução,
`utility_matrix` só filtra e normaliza o que já foi sorteado, e os lances saem
deterministicamente das utilidades (eqs. 44-46) — nenhuma aleatoriedade dentro
do loop, como exige a Seção 7.3.

Isso importa para comparar cenários: se a utilidade fosse sorteada dentro do
loop, mexer numa vaga deslocaria o fluxo do gerador e mudaria as preferências
dos alunos, e a diferença entre dois cenários deixaria de ser atribuível ao
mecanismo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import Course, SimulationConfig
from .population import Student

# U_a^(t) = soma das utilidades = fração do orçamento que o aluno se dispõe a
# gastar no período (eq. 43). O anteprojeto não fixa distribuição; usa-se uma
# uniforme nesta faixa, que mantém U_a em (0, 1] sem gerar alunos que mal
# gastam créditos.
SPEND_FRACTION_RANGE = (0.5, 1.0)


@dataclass(frozen=True)
class UtilityDraw:
    """O sorteio bruto de u_{a,·}^(t) para um par (aluno, período).

    Guarda um peso por disciplina e um por grupo da grade, ambos Gamma(1), em
    vez da Dirichlet já normalizada. A normalização fica para o tempo de
    execução porque o conjunto elegível muda conforme o aluno é aprovado — e,
    pela propriedade de agregação da Dirichlet, normalizar um subconjunto de
    pesos Gamma(1) dá exatamente uma Dirichlet(1) sobre esse subconjunto. O
    sorteio é fixo; o recorte é determinístico.
    """

    spend_fraction: float  # U_a^(t) — eq. (42)
    group_weights: tuple[float, float, float]  # obrigatórias, optativas, livres
    weights: dict[str, float]  # peso bruto de cada disciplina do cenário


def draw_utilities(
    students: list[Student], config: SimulationConfig, rng: np.random.Generator
) -> dict[tuple[str, int], UtilityDraw]:
    """Sorteia a matriz de utilidades inteira — todos os alunos, todos os
    períodos — na inicialização, a partir da seed."""
    periods = config.periods
    names = [d.name for d in config.disciplines]
    shape = (len(students), periods)
    spend = rng.uniform(*SPEND_FRACTION_RANGE, size=shape)
    # Gamma(1) = Exponencial(1): normalizado, dá Dirichlet(1) — eq. (41).
    groups = rng.standard_exponential(size=(*shape, 3))
    weights = rng.standard_exponential(size=(*shape, len(names)))

    return {
        (student.id, period + 1): UtilityDraw(
            spend_fraction=float(spend[a, period]),
            group_weights=tuple(float(w) for w in groups[a, period]),
            weights={name: float(weights[a, period, j]) for j, name in enumerate(names)},
        )
        for a, student in enumerate(students)
        for period in range(periods)
    }


def utility_matrix(
    *,
    draw: UtilityDraw,
    student: Student,
    course: Course,
    config: SimulationConfig,
) -> dict[str, float]:
    """u_{a,·}^(t) a partir do sorteio já feito — eqs. (41)-(43), (47)-(48).

    Função determinística: mesmo `draw` e mesmo estado do aluno, mesma saída.
    Retorna apenas as disciplinas com utilidade positiva — as já aprovadas têm
    utilidade zero por construção (Seção 7.2.4) e simplesmente não aparecem.

    A hierarquia obrigatórias > optativas > livres das eqs. (47)-(48) é
    garantida ordenando as massas dos grupos de forma decrescente na ordem dos
    grupos presentes.
    """
    approved = student.approved(config.min_grade)
    groups = [
        [name for name in course.required if name not in approved],
        [name for name in course.electives if name not in approved],
        [name for name in config.free_disciplines(course) if name not in approved],
    ]
    present = [index for index, names in enumerate(groups) if names]
    if not present:
        return {}

    # Massas decrescentes: o grupo mais prioritário entre os presentes fica com
    # a maior fatia, satisfazendo soma_M u >= soma_O u >= soma_L u.
    group_total = sum(draw.group_weights[index] for index in present)
    masses = sorted(
        (draw.group_weights[index] / group_total * draw.spend_fraction for index in present),
        reverse=True,
    )

    utilities: dict[str, float] = {}
    for mass, index in zip(masses, present):
        names = groups[index]
        # Normalizar os pesos Gamma(1) do grupo reparte a massa sem privilegiar
        # nenhuma disciplina a priori — valores contínuos e distintos, eq. (41).
        total = sum(draw.weights[name] for name in names)
        for name in names:
            utilities[name] = mass * draw.weights[name] / total
    return utilities


def compute_bids(
    *,
    utilities: dict[str, float],
    available: list[str],
    budget: int,
    spend_fraction: float,
) -> dict[str, int]:
    """Converte utilidades em lances inteiros numa rodada — eqs. (44)-(46).

    `available` é B_a^(t,r) (disciplinas em que ainda é possível obter vaga) e
    `spend_fraction` é U_a^(t) (eq. 42), calculado sobre o período inteiro e,
    portanto, constante entre as rodadas.
    """
    pool = [name for name in available if utilities.get(name, 0.0) > 0.0]
    if not pool or budget <= 0:
        return {}

    total_utility = sum(utilities[name] for name in pool)
    to_spend = budget * spend_fraction

    # eq. (44): lances preliminares proporcionais à utilidade, truncados.
    preliminary = {
        name: math.floor(to_spend * utilities[name] / total_utility) for name in pool
    }
    # eq. (45): o truncamento sobra créditos...
    leftover = math.floor(to_spend) - sum(preliminary.values())
    # ...distribuídos um a um em ordem decrescente de preferência — eq. (46),
    # em que u^ é a utilidade ordinal (1 = disciplina preferida da rodada).
    ordinal = sorted(pool, key=lambda name: utilities[name], reverse=True)
    for name in ordinal[:leftover]:
        preliminary[name] += 1

    # Lance nulo não é demanda — eq. (18).
    return {name: credits for name, credits in preliminary.items() if credits > 0}
