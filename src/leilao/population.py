"""Os alunos da simulação — o conjunto A (Seção 7.2) e seu estado ao longo dos períodos.

Os alunos não são configurados um a um: o usuário diz quantos alunos cada
curso tem e a população inteira é gerada a partir da `seed` (nomes, aptidão
acadêmica e, a cada período, a matriz de utilidades).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import SimulationConfig
from .names import sample_names


@dataclass
class Student:
    """Um aluno a in A e todo o seu histórico acadêmico.

    `ability` é uma aptidão latente em [0, 1] que determina a distribuição das
    notas do aluno. Não consta no anteprojeto: foi acrescentada porque sem
    heterogeneidade de desempenho o CR vira ruído e a correlação entre CR e
    satisfação (eq. 57) não mede coisa alguma.
    """

    id: str
    name: str
    course: str
    ability: float
    credits: int  # C_a^{(t,1)} — orçamento no início do período, eq. (36)/(37)
    entry_period: int = 1  # t_a — período em que ingressa, eq. (31)
    grades: dict[str, float] = field(default_factory=dict)  # n_{a,x} — maior nota obtida
    attempts: dict[str, int] = field(default_factory=dict)  # quantas vezes cursou cada disciplina
    graduated_at: int | None = None  # período em que concluiu o curso — eq. (40)
    # Período em que foi desligado por decurso de prazo (jubilamento), tendo
    # permanecido `SimulationConfig.max_residence` períodos sem concluir (0
    # desliga a regra e este campo nunca sai de `None`). Sai
    # do conjunto ativo como quem se forma, e é essa saída que faz o
    # jubilamento ser modelagem e não filtro de relatório: um a menos
    # disputando alivia a concorrência de quem fica.
    dismissed_at: int | None = None

    @property
    def taken(self) -> set[str]:
        """H_a — disciplinas já cursadas."""
        return set(self.attempts)

    def approved(self, min_grade: float) -> set[str]:
        """H~_a = {x in H_a : n_{a,x} >= n_min} — disciplinas aprovadas."""
        return {name for name, grade in self.grades.items() if grade >= min_grade}

    def approved_hours(self, hours_by_discipline: dict[str, int], min_grade: float) -> int:
        """Soma_{x in H~_a} w_x — carga horária aprovada, usada na eq. (40)."""
        return sum(hours_by_discipline[name] for name in self.approved(min_grade))

    def grade_average(self, hours_by_discipline: dict[str, int]) -> float:
        """Coeficiente de rendimento N_a — eq. (49): média das notas ponderada
        pela carga horária das disciplinas cursadas.

        Sem disciplinas cursadas a média é 0/0; adota-se 0,0 (o aluno ainda não
        tem histórico, como no primeiro período de todo mundo).
        """
        if not self.taken:
            return 0.0
        total_hours = sum(hours_by_discipline[name] for name in self.taken)
        weighted = sum(hours_by_discipline[name] * self.grades.get(name, 0.0) for name in self.taken)
        return weighted / total_hours


def generate_students(config: SimulationConfig, rng: np.random.Generator) -> list[Student]:
    """Cria a população inteira a partir da seed: nomes, aptidão e período de
    ingresso. Todos começam com o orçamento base (eq. 37).

    O ingresso (t_a, eq. 31) é escalonado: cada curso recebe uma geração nova
    a cada período letivo, do primeiro ao L-ésimo (`config.entry_span`), com
    exatamente `students_per_generation` alunos — como numa universidade, que
    abre vestibular todo semestre em vez de matricular toda a população de uma
    vez. Quando L < |T| os períodos seguintes não recebem ninguém: é a fase de
    drenagem, em que a população só diminui.

    A geração de cada aluno é determinística; da seed vem só quem ele é (nome e
    aptidão). Antes o tamanho das gerações saía de uma divisão que podia ser
    inexata; agora é dado direto, e todas as gerações têm o mesmo tamanho por
    construção.
    """
    total = config.total_students()
    names = sample_names(total, rng)
    abilities = rng.uniform(0.0, 1.0, size=total)

    students: list[Student] = []
    for course in config.courses:
        for entry_period in range(1, config.entry_span + 1):
            for _ in range(course.students_per_generation):
                index = len(students)
                students.append(
                    Student(
                        id=f"a{index:05d}",
                        name=names[index],
                        course=course.name,
                        ability=float(abilities[index]),
                        credits=config.base_credits,
                        entry_period=entry_period,
                    )
                )
    return students
