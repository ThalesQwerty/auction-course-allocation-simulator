"""Os alunos — o conjunto A (Seção 7.2) e o estado que anda com os períodos.

Eles não são configurados um a um: o usuário diz quantos ingressam por período
e a população inteira sai da seed.

Cada aluno carrega **três níveis basilares**, um por eixo: desempenho,
disponibilidade e seletividade. São posições na normal padrão, sorteadas uma
vez e permanentes, e é sobre elas que os relatórios recortam os quantis.

Os dois primeiros são **traço** — governam sorteios e o aluno não os conhece.
O terceiro é **estratégia**: dele sai, período a período, o `Behavior` com que
ele decide.

Houve **perfis** nomeados até 19/11/2026, repartidos igualmente entre as
combinações. Os níveis basilares os substituíram, e estes **saem da seed** —
ao contrário dos perfis, que eram atribuídos por posição.
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
    # Os **níveis basilares**: a posição permanente do aluno em cada eixo, na
    # normal padrão. Zero é a mediana da população, e é o default porque quem
    # constrói um aluno à mão não está escolhendo uma ponta.
    #
    # Os dois primeiros são traço e entram só em sorteio; o terceiro vira a
    # seletividade do período. Os relatórios **não** os recortam mais: o corte
    # passou a ser por valor corrente em 24/11/2026 (ver
    # `simulation.snapshots.Axis.states`), e o que sai deles agora é a dispersão
    # que faz o CR ordenar e o cabeçalho da tela individual.
    performance_level: float = 0.0
    availability_level: float = 0.0
    selectivity_level: float = 0.0
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
    # Como este aluno traduz utilidade em mensagem — o valor do perfil de
    # estratégia. O default é o neutro, que reproduz o modelo sem
    # comportamento bit a bit, para quem constrói um aluno à mão.
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
    """Cria a população inteira a partir da seed. Todos começam em C_min
    (eq. 37).

    O ingresso (t_a, eq. 31) é escalonado: entra uma coorte nova **em todo
    período letivo**, com exatamente `students_per_period` alunos — como numa
    universidade, que abre vestibular todo semestre em vez de matricular toda
    a população de uma vez.

    O período de ingresso **não** vem da seed: as coortes têm todas o mesmo
    tamanho, em períodos consecutivos, e isso importa para comparar cenários —
    duas simulações com seeds diferentes têm a mesma estrutura de entrada,
    então a diferença entre elas não é quem entrou quando. Da seed vêm o nome
    e os três níveis basilares — e, fora daqui, as notas, a disponibilidade, a
    seletividade e as utilidades.
    """
    names = sample_names(config.total_students(), rng)
    # Os três níveis basilares, de uma vez: uma matriz (alunos × 3) da normal
    # padrão. Sair tudo de um sorteio só mantém o fluxo do gerador
    # independente de qual eixo se mexe depois.
    levels = rng.normal(0.0, 1.0, size=(config.total_students(), 3))
    students = []
    for index in range(config.total_students()):
        students.append(
            Student(
                id=f"a{index:05d}",
                name=names[index],
                credits=config.min_credits,
                entry_period=1 + index // config.students_per_period,
                performance_level=float(levels[index, 0]),
                availability_level=float(levels[index, 1]),
                selectivity_level=float(levels[index, 2]),
            )
        )
    return students
