"""Os alunos da simulação — o conjunto A (Seção 7.2) e seu estado ao longo dos períodos.

Os alunos não são configurados um a um: o usuário diz quantos ingressam por
período e a população inteira é gerada a partir da `seed` (nomes, notas e
utilidades). Não há curso: todo aluno é da universidade e cursa a mesma grade,
e **não há perfis**: todos saem das mesmas duas normais do cenário, de modo que
a diferença entre dois alunos é só o que a seed sorteou para cada um.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .behavior import NEUTRAL, Behavior

import numpy as np

from .config import SimulationConfig
from .names import sample_names


@dataclass
class Student:
    """Um aluno a in A e todo o seu histórico acadêmico.

    O que o distingue dos colegas não está aqui: são a linha dele na matriz de
    notas e a linha dele na matriz de utilidades, as duas sorteadas na
    inicialização e guardadas fora do aluno (`grading.draw_grades`,
    `behavior.draw_utilities`). O que está aqui é só o estado que anda com os
    períodos — saldo, notas obtidas, tentativas e a conclusão.
    """

    id: str
    name: str
    credits: int  # C_a^{(t,1)} — orçamento no início do período, eq. (36)/(37)
    entry_period: int = 1  # t_a — período em que ingressa, eq. (31)
    grades: dict[str, float] = field(default_factory=dict)  # n_{a,x} — maior nota obtida
    attempts: dict[str, int] = field(default_factory=dict)  # quantas vezes cursou cada disciplina
    # Período em que concluiu o curso — eq. (40). É a **única** porta de saída:
    # quem não concluiu continua disputando até o fim do horizonte.
    graduated_at: int | None = None
    # Como este aluno traduz utilidade em mensagem — ver `behavior.Behavior`.
    # Hoje **todo mundo carrega o neutro**, que reproduz o modelo sem
    # comportamento bit a bit; o campo existe para que a evolução desses
    # coeficientes seja um experimento, e não uma reescrita.
    behavior: Behavior = NEUTRAL

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

    O período de ingresso **não** vem da seed: as gerações têm todas o mesmo
    tamanho, em períodos consecutivos. Da seed vem o nome — e, fora daqui, as
    notas e as utilidades. Isso importa para comparar cenários: duas execuções
    com seeds diferentes têm a mesma estrutura de entrada, então a diferença
    entre elas não é quem entrou quando.
    """
    total = config.total_students()
    names = sample_names(total, rng)

    students: list[Student] = []
    for entry_period in range(1, config.entry_span + 1):
        for _ in range(config.students_per_period):
            index = len(students)
            students.append(
                Student(
                    id=f"a{index:05d}",
                    name=names[index],
                    credits=config.base_credits,
                    entry_period=entry_period,
                )
            )
    return students
