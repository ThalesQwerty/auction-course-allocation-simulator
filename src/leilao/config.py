"""Configuração de um cenário de simulação (Seção 7.2 do anteprojeto).

O usuário descreve o cenário em três blocos — parâmetros gerais, disciplinas e
cursos — e a simulação deriva o resto (alunos, nomes, matriz de utilidades,
notas) aleatoriamente a partir da `seed`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Política de retorno de créditos f_gamma — eq. (34). O anteprojeto deixa a
# forma concreta em aberto e trata as políticas como eixo de experimentação
# (Seção 7.3.2) — as quatro comparadas estão em `grading.credit_return`.
CreditReturnPolicy = Literal["none", "unit", "full", "ratio"]


@dataclass(frozen=True)
class Discipline:
    """Uma disciplina ofertada — o bem escaso x in B (Tabela 1)."""

    name: str
    seats: int  # q_x — vagas
    hours: int  # w_x — carga horária

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("disciplina sem nome")
        if self.seats < 0:
            raise ValueError(f"disciplina {self.name!r}: vagas (q_x) deve ser >= 0")
        if self.hours <= 0:
            raise ValueError(f"disciplina {self.name!r}: carga horária (w_x) deve ser > 0")


@dataclass(frozen=True)
class Course:
    """Um curso k in K, com sua grade curricular (Seção 7.2.3).

    `required` é M_k (obrigatórias) e `electives` é O_k (optativas); o que
    sobra das disciplinas do cenário é L_k (livres), que não conta para a
    conclusão do curso.
    """

    name: str
    # Alunos que ingressam a cada período letivo com ingresso: o curso recebe
    # uma geração nova em cada um dos L primeiros períodos, então sua população
    # é este número vezes `SimulationConfig.entry_span`.
    students_per_generation: int
    hours_to_graduate: int  # S_k — eq. (39)
    required: tuple[str, ...] = ()  # M_k
    electives: tuple[str, ...] = ()  # O_k

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("curso sem nome")
        if self.students_per_generation < 0:
            raise ValueError(
                f"curso {self.name!r}: alunos por geração deve ser >= 0"
            )
        overlap = set(self.required) & set(self.electives)
        if overlap:
            raise ValueError(
                f"curso {self.name!r}: disciplinas em obrigatórias e optativas ao "
                f"mesmo tempo: {sorted(overlap)}"
            )


@dataclass(frozen=True)
class SimulationConfig:
    """Cenário completo. Tudo que não está aqui é sorteado a partir de `seed`."""

    disciplines: list[Discipline] = field(default_factory=list)
    courses: list[Course] = field(default_factory=list)
    periods: int = 1  # |T| — períodos letivos
    # L — em quantos dos |T| períodos entra geração nova, contados do primeiro.
    # `None` = em todos, e aí o último período recebe uma geração que só vive
    # esse período. Com L < |T| a simulação ganha uma fase de drenagem: depois
    # do último ingresso a população só diminui, e as gerações tardias têm
    # tempo de chegar ao fim do curso em vez de serem cortadas pelo horizonte.
    entry_periods: int | None = None
    # T_max — quantos períodos letivos o aluno pode permanecer antes de ser
    # desligado por decurso de prazo (jubilamento). **0 desliga a regra**: o
    # jubilamento é opcional, e permanecer zero períodos não significaria nada,
    # então o valor fica livre para servir de sentinela. É global, não por
    # aluno: o prazo é regra da instituição, não escolha de quem estuda. Ver
    # `Student.dismissed_at`.
    max_residence: int = 0
    rounds: int = 1  # |R| — rodadas de alocação por período
    min_grade: float = 5.0  # n_min — nota mínima de aprovação
    base_credits: int = 10  # Gamma_min — créditos base por período, eq. (35)/(37)
    max_hours: int = 360  # W_a — carga horária máxima por período, eq. (4)
    learning_gain: float = 2.5  # ganho de nota por recursada — eq. (33)
    credit_return: CreditReturnPolicy = "none"
    seed: int = 0

    def __post_init__(self) -> None:
        if self.periods < 1:
            raise ValueError("é preciso simular ao menos 1 período")
        if self.entry_periods is not None and not 1 <= self.entry_periods <= self.periods:
            raise ValueError(
                "períodos com ingresso deve estar entre 1 e o total de períodos "
                f"({self.periods})"
            )
        if self.max_residence < 0:
            raise ValueError(
                "tempo máximo de permanência deve ser >= 0 (0 = sem jubilamento)"
            )
        if self.rounds < 1:
            raise ValueError("é preciso simular ao menos 1 rodada por período")
        if not 0 < self.min_grade <= 10:
            raise ValueError("nota mínima deve estar em (0, 10]")
        if self.base_credits < 1:
            raise ValueError("créditos base (Gamma_min) deve ser >= 1")
        if self.max_hours < 1:
            raise ValueError("carga horária máxima (W_a) deve ser >= 1")
        if not 0 < self.learning_gain <= 10:
            raise ValueError("Incremento de aprendizado deve estar em (0, 10]")
        # Sem disciplina ou sem aluno não há o que alocar: a simulação não
        # produziria período nenhum, e toda métrica sairia indefinida.
        if not self.disciplines:
            raise ValueError("o cenário precisa de pelo menos uma disciplina")
        if self.total_students() < 1:
            raise ValueError("o cenário precisa de pelo menos um aluno")

        names = [d.name for d in self.disciplines]
        if len(set(names)) != len(names):
            raise ValueError("há disciplinas com nomes repetidos")
        course_names = [c.name for c in self.courses]
        if len(set(course_names)) != len(course_names):
            raise ValueError("há cursos com nomes repetidos")

        known = set(names)
        for course in self.courses:
            unknown = (set(course.required) | set(course.electives)) - known
            if unknown:
                raise ValueError(
                    f"curso {course.name!r} referencia disciplinas inexistentes: {sorted(unknown)}"
                )
            # eq. (39): a carga exigida fica entre a soma das obrigatórias e a
            # soma de obrigatórias + optativas — senão o curso é impossível de
            # concluir, ou conclui-se sem cursar todas as obrigatórias.
            required_hours = self.total_hours(course.required)
            reachable_hours = self.total_hours(course.required + course.electives)
            if not required_hours <= course.hours_to_graduate <= reachable_hours:
                raise ValueError(
                    f"curso {course.name!r}: horas para conclusão (S_k = "
                    f"{course.hours_to_graduate}) devem ficar entre a carga das "
                    f"obrigatórias ({required_hours}) e a das obrigatórias + "
                    f"optativas ({reachable_hours}) — eq. (39)"
                )

    @property
    def entry_span(self) -> int:
        """L — quantos períodos recebem geração nova, resolvido o `None`."""
        return self.periods if self.entry_periods is None else self.entry_periods

    def total_students(self) -> int:
        """|A| — cada curso recebe uma geração nos L primeiros períodos, todas
        do mesmo tamanho, então a população é o produto dos dois números."""
        return sum(c.students_per_generation for c in self.courses) * self.entry_span

    def minimum_periods_to_graduate(self) -> int:
        """Piso de períodos para concluir o curso mais longo: nem o aluno que
        nunca reprova nem perde uma vaga fecha S_k em menos de ceil(S_k / W_a).

        Serve para dimensionar `max_residence` e a fase de drenagem — um prazo
        abaixo disso jubila a população inteira por construção.
        """
        if not self.courses:
            return 0
        return max(
            -(-course.hours_to_graduate // self.max_hours) for course in self.courses
        )

    def hours_by_discipline(self) -> dict[str, int]:
        return {d.name: d.hours for d in self.disciplines}

    def total_hours(self, discipline_names: tuple[str, ...] | list[str]) -> int:
        hours = self.hours_by_discipline()
        return sum(hours[name] for name in discipline_names)

    def free_disciplines(self, course: Course) -> list[str]:
        """L_k = B \\ (M_k u O_k) — livres, não contam para a conclusão."""
        classified = set(course.required) | set(course.electives)
        return [d.name for d in self.disciplines if d.name not in classified]
