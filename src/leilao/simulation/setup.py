"""A inicialização: tudo o que vem da seed, antes do primeiro período.

A Seção 7.3 exige que nada seja sorteado dentro do laço, e este módulo é onde
essa exigência se cumpre. Depois daqui o gerador não é mais tocado: a
população, a aptidão, o interesse, a ordem de desempate e as perturbações
já existem inteiras.

O motivo é comparabilidade. Com o sorteio dentro do laço, mexer numa vaga
deslocaria o fluxo do gerador e mudaria as preferências de todo mundo, e a
diferença entre dois cenários deixaria de ser atribuível ao mecanismo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..availability import draw_availability
from ..behavior import draw_interest
from ..config import SimulationConfig
from ..grading import GradeShapes, draw_base_quantiles
from ..equations import stochastic_perturbations
from ..population import Student, generate_students


@dataclass(frozen=True)
class Draws:
    """O que a seed produziu, mais o que se deriva do cenário uma vez só.

    Tudo aqui é imutável durante a simulação inteira — é a diferença entre
    isto e o estado de período, que anda a cada rodada.
    """

    students: list[Student]
    # q_{a,x} — traço, não sorte: uma posição por par, persistente. A nota
    # sai de ler este quantil na distribuição da tentativa.
    base_quantiles: dict[tuple[str, str], float]
    # A forma da normal dividida por (perfil, dificuldade, tentativa). Cache
    # de função pura, não estado: ver `grading.GradeShapes`.
    grade_shapes: GradeShapes
    # δ_a^(t) — circunstância, não traço: uma por (aluno, período). O que é
    # traço é a média de onde ela sai, que é o perfil.
    availability: dict[tuple[str, int], float]
    # O interesse u^(t): uma linha por (aluno, período), sobre a grade inteira.
    # Não é o que o aluno decide — a utilidade sai daqui a cada período, pelo
    # histórico dele (`behavior.utility_matrix`). Fora isso, só relatório lê.
    interest_rows: dict[tuple[str, int], dict[str, float]]
    # α: uma ordem de desempate por disciplina, fixa para a simulação inteira,
    # como exige a Seção 7.1.2.
    tie_break_order: dict[str, list[str]]
    # ε: idem, sorteada uma vez para todos os pares (a, x).
    epsilon: dict[tuple[str, str], float]

    # Derivados do cenário, calculados uma vez porque são lidos em todo laço.
    #
    # **O que é por turma e o que é por disciplina.** O bem alocado é a
    # turma, então tudo que indexa o que o aluno ganhou — carga, vaga,
    # dificuldade — é por turma. O histórico acadêmico é por disciplina:
    # nota, tentativa e conclusão não sabem em que seção ele cursou.
    hours: dict[str, int]  # por turma, replicada inteira
    difficulty: dict[str, float]  # por turma, pela escada do grupo
    seats: dict[str, int]  # por turma
    discipline_hours: dict[str, int]  # por disciplina, para o histórico
    classes: dict[str, tuple[str, ...]]  # grupo -> turmas
    discipline_of: dict[str, str]  # turma -> grupo
    exclusions: tuple[frozenset[str], ...]  # X, os cliques da eq. (5)
    curriculum: dict[str, int]
    entry_courses: list[str]
    required: set[str]
    elective_hours_by_discipline: dict[str, int]
    hours_to_graduate: int
    total_seats: int
    entry_periods: list[int]


def prepare(config: SimulationConfig) -> Draws:
    rng = np.random.default_rng(config.seed)
    students = generate_students(config, rng)
    base_quantiles = draw_base_quantiles(students, config.disciplines, config, rng)
    availability = draw_availability(students, config, rng)
    interest_rows = draw_interest(students, config, rng)

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
        base_quantiles=base_quantiles,
        grade_shapes=GradeShapes(),
        availability=availability,
        interest_rows=interest_rows,
        tie_break_order=tie_break_order,
        epsilon=epsilon,
        hours=config.hours_by_class(),
        difficulty=config.difficulty_by_class(),
        seats=config.seats_by_class(),
        discipline_hours=config.hours_by_discipline(),
        classes=config.classes_by_discipline(),
        discipline_of=config.discipline_by_class(),
        exclusions=config.class_exclusions(),
        curriculum=config.curriculum_periods(),
        entry_courses=config.entry_disciplines(),
        required=config.required_disciplines(),
        elective_hours_by_discipline=config.elective_hours_by_discipline(),
        hours_to_graduate=config.hours_to_graduate(),
        total_seats=sum(d.seats for d in config.disciplines),
        entry_periods=sorted({s.entry_period for s in students}),
    )
