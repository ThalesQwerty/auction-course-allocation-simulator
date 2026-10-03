"""Os alunos da simulação — o conjunto A (Seção 7.2) e seu estado ao longo dos períodos.

Os alunos não são configurados um a um: o usuário diz quantos ingressam por
período e a população inteira é gerada a partir da `seed` (nomes, aptidão
acadêmica e, a cada período, a matriz de utilidades). Não há curso: todo aluno
é da universidade e cursa a mesma grade.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import AffinityProfile, AptitudeProfile, SimulationConfig
from .names import sample_names


@dataclass
class Student:
    """Um aluno a in A e todo o seu histórico acadêmico.

    Os dois perfis são o que o distingue dos colegas, e nenhum deles consta no
    anteprojeto. `aptitude` dá a distribuição das notas de primeira tentativa:
    sem heterogeneidade de desempenho o CR vira ruído e a correlação entre CR e
    satisfação (eq. 57) não mede coisa alguma. `affinity` diz o quanto ele
    concentra a preferência, que é justamente a informação que o leilão diz
    captar e a ordenação por CR não.
    """

    id: str
    name: str
    aptitude: AptitudeProfile
    affinity: AffinityProfile
    credits: int  # C_a^{(t,1)} — orçamento no início do período, eq. (36)/(37)
    entry_period: int = 1  # t_a — período em que ingressa, eq. (31)
    grades: dict[str, float] = field(default_factory=dict)  # n_{a,x} — maior nota obtida
    attempts: dict[str, int] = field(default_factory=dict)  # quantas vezes cursou cada disciplina
    # Período em que concluiu o curso — eq. (40). É a **única** porta de saída:
    # quem não concluiu continua disputando até o fim do horizonte.
    graduated_at: int | None = None

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

    O ingresso (t_a, eq. 31) é escalonado: entra uma geração nova a cada período
    letivo, do primeiro ao L-ésimo (`config.entry_span`), com exatamente
    `students_per_period` alunos — como numa universidade, que abre vestibular
    todo semestre em vez de matricular toda a população de uma vez. Quando
    L < |T| os períodos seguintes não recebem ninguém: é a fase de drenagem, em
    que a população só diminui.

    Nem o período de ingresso nem o perfil vêm da seed: os dois são repartições
    exatas (`config.generation_profiles`), idênticas em toda geração. Da seed
    vem só o nome. Isso importa para comparar cenários — duas execuções com
    seeds diferentes têm a mesma composição de perfis, então a diferença entre
    elas não é a sorte de quem entrou.
    """
    total = config.total_students()
    names = sample_names(total, rng)
    mix = config.generation_profiles()

    students: list[Student] = []
    for entry_period in range(1, config.entry_span + 1):
        for aptitude, affinity in mix:
            index = len(students)
            students.append(
                Student(
                    id=f"a{index:05d}",
                    name=names[index],
                    aptitude=aptitude,
                    affinity=affinity,
                    credits=config.base_credits,
                    entry_period=entry_period,
                )
            )
    return students
