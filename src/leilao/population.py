"""Os alunos — o conjunto A (Seção 7.2) e o estado que anda com os períodos.

Eles não são configurados um a um: o usuário diz quantos ingressam por
período e a população inteira sai da seed. **Não há perfis** — todos saem das
mesmas distribuições do cenário, de modo que a diferença entre dois alunos é
só o que a seed sorteou para cada um.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import SimulationConfig
from .equations import NEUTRAL, Behavior, grade_average
from .names import sample_names


@dataclass
class Student:
    """Um aluno a ∈ A e todo o seu histórico acadêmico.

    O que o distingue dos colegas não está aqui: são a linha dele na matriz de
    utilidades e a aptidão dele por disciplina, as duas sorteadas na
    inicialização e guardadas fora do aluno. Aqui fica só o estado que anda
    com os períodos — saldo, notas, tentativas e a conclusão.
    """

    id: str
    name: str
    credits: int  # C_a^(t,1) — eqs. (36)/(37)
    entry_period: int = 1  # t_a — eq. (31)
    # n_{a,x}: a **maior** nota já obtida, que é a que conta para o CR e para
    # a aprovação. A nota de cada tentativa vive no histórico do período.
    grades: dict[str, float] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    # Período em que concluiu — eq. (40).
    graduated_at: int | None = None
    # Período em que foi **jubilado**: chegou ao fim da residência sem fechar a
    # grade. A segunda (e última) porta de saída, e só existe quando o cenário
    # declara `max_residence`. Quem conclui *no* último período de residência
    # sai concluinte — a conclusão é testada antes.
    dismissed_at: int | None = None

    @property
    def left_at(self) -> int | None:
        """O período em que o aluno deixou a simulação, por qualquer das duas
        portas. `None` enquanto ele ainda disputa."""
        return self.graduated_at if self.graduated_at is not None else self.dismissed_at
    # Como este aluno traduz utilidade em mensagem. Hoje todo mundo carrega o
    # neutro, que reproduz o modelo sem comportamento bit a bit; o campo
    # existe para que a evolução desses coeficientes seja um experimento, e
    # não uma reescrita.
    behavior: Behavior = NEUTRAL

    @property
    def taken(self) -> set[str]:
        """H_a — disciplinas já cursadas, aprovadas ou não."""
        return set(self.attempts)

    def approved(self, min_grade: float) -> set[str]:
        """H̃_a = { x ∈ H_a : n_{a,x} ≥ n_min }."""
        return {name for name, grade in self.grades.items() if grade >= min_grade}

    def approved_hours(self, hours: dict[str, int], min_grade: float) -> int:
        """Σ_{x ∈ H̃_a} w_x — carga horária aprovada."""
        return sum(hours[name] for name in self.approved(min_grade))

    def grade_average(self, hours: dict[str, int]) -> float:
        """N_a — ver `equations.grade_average`."""
        return grade_average(taken=self.taken, grades=self.grades, hours=hours)


def generate_students(
    config: SimulationConfig, rng: np.random.Generator
) -> list[Student]:
    """Cria a população inteira a partir da seed. Todos começam em Γ_min
    (eq. 37).

    O ingresso (t_a, eq. 31) é escalonado: entra uma geração nova a cada
    período letivo, do primeiro ao último com ingresso, com exatamente
    `students_per_period` alunos — como numa universidade, que abre vestibular
    todo semestre em vez de matricular toda a população de uma vez. Quando são
    menos que |T|, os períodos seguintes não recebem ninguém: é a fase de
    drenagem.

    O período de ingresso **não** vem da seed. As gerações têm todas o mesmo
    tamanho, em períodos consecutivos, e isso importa para comparar cenários:
    duas execuções com seeds diferentes têm a mesma estrutura de entrada,
    então a diferença entre elas não é quem entrou quando. Da seed vem o nome
    — e, fora daqui, a aptidão e as utilidades.
    """
    names = sample_names(config.total_students(), rng)
    return [
        Student(
            id=f"a{index:05d}",
            name=names[index],
            credits=config.base_credits,
            entry_period=1 + index // config.students_per_period,
        )
        for index in range(config.total_students())
    ]
