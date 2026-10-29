"""A inicialização: tudo o que vem da seed, antes do primeiro período.

A Seção 7.3 exige que nada seja sorteado dentro do laço, e este módulo é onde
essa exigência se cumpre. Depois daqui o gerador não é mais tocado: a
população, a aptidão, as utilidades, a ordem de desempate e as perturbações
já existem inteiras.

O motivo é comparabilidade. Com o sorteio dentro do laço, mexer numa vaga
deslocaria o fluxo do gerador e mudaria as preferências de todo mundo, e a
diferença entre dois cenários deixaria de ser atribuível ao mecanismo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..behavior import draw_utilities
from ..config import SimulationConfig
from ..grading import draw_aptitudes
from ..equations import stochastic_perturbations
from ..population import Student, generate_students


@dataclass(frozen=True)
class Draws:
    """O que a seed produziu, mais o que se deriva do cenário uma vez só.

    Tudo aqui é imutável durante a simulação inteira — é a diferença entre
    isto e o estado de período, que anda a cada rodada.
    """

    students: list[Student]
    # a_{a,x} — traço, não sorte: uma aptidão por par, persistente.
    aptitudes: dict[tuple[str, str], float]
    # u^(t) inteira: uma linha por (aluno, período), sobre a grade.
    utility_rows: dict[tuple[str, int], dict[str, float]]
    # α: uma ordem de desempate por disciplina, fixa para a simulação inteira,
    # como exige a Seção 7.1.2.
    tie_break_order: dict[str, list[str]]
    # ε: idem, sorteada uma vez para todos os pares (a, x).
    epsilon: dict[tuple[str, str], float]

    # Derivados do cenário, calculados uma vez porque são lidos em todo laço.
    hours: dict[str, int]
    difficulty: dict[str, float]
    curriculum: dict[str, int]
    reach: dict[str, int]
    entry_courses: list[str]
    required: set[str]
    elective_hours_by_discipline: dict[str, int]
    hours_to_graduate: int
    total_seats: int
    # |disciplinas| — põe a indiferença em 1 na utilidade relativa, e é o que
    # faz os parâmetros de nota e de score sobreviverem ao catálogo crescer.
    catalogue: int
    entry_periods: list[int]


def prepare(config: SimulationConfig) -> Draws:
    rng = np.random.default_rng(config.seed)
    students = generate_students(config, rng)
    aptitudes = draw_aptitudes(students, config.disciplines, config, rng)
    utility_rows = draw_utilities(students, config, rng)

    student_ids = [s.id for s in students]
    tie_break_order = {
        discipline.name: [student_ids[i] for i in rng.permutation(len(students))]
        for discipline in config.disciplines
    }
    epsilon = stochastic_perturbations(
        [(s.id, d.name) for s in students for d in config.disciplines],
        num_agents=max(len(students), 1),
        num_goods=max(len(config.disciplines), 1),
        seed=config.seed,
    )

    return Draws(
        students=students,
        aptitudes=aptitudes,
        utility_rows=utility_rows,
        tie_break_order=tie_break_order,
        epsilon=epsilon,
        hours=config.hours_by_discipline(),
        difficulty={d.name: d.difficulty for d in config.disciplines},
        curriculum=config.curriculum_periods(),
        reach=config.reach(),
        entry_courses=config.entry_disciplines(),
        required=config.required_disciplines(),
        elective_hours_by_discipline=config.elective_hours_by_discipline(),
        hours_to_graduate=config.hours_to_graduate(),
        total_seats=sum(d.seats for d in config.disciplines),
        catalogue=len(config.disciplines),
        entry_periods=sorted({s.entry_period for s in students}),
    )
