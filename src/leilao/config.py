"""Configuração de um cenário de simulação (Seção 7.2 do anteprojeto)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from .equations import (
    grade_mean,
    Behavior,
    availability_shape,
    class_schedules,
    curriculum_heights,
    curriculum_periods,
    curriculum_reach,
    eligible_set,
    inverse_edges,
    rotated_index,
    schedule_cliques,
    schedule_names,
    transitive_closure,
)

@lru_cache(maxsize=16)
def _curriculum_closures(
    edges: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    forward = transitive_closure(dict(edges))
    return forward, inverse_edges(forward)

Mechanism = Literal["credits", "ranking"]

MAX_BANDS = 5
MAX_CUTS = MAX_BANDS - 1

GRADE_DOMAIN = (0.0, 10.0)
RESERVE_DOMAIN = (0.0, 1.0)


@dataclass(frozen=True)
class AvailabilityShape:
    """A distribuição de disponibilidade da população — **uma só**."""

    hours_sd: float = 1.2
    full_load_rate: float = 0.10

    def shape(self, max_hours: float) -> tuple[float, float]:
        """(média, desvio padrão) da normal das horas."""
        return availability_shape(
            hours_sd=self.hours_sd,
            full_load_rate=self.full_load_rate,
            max_hours=max_hours,
        )


DEFAULT_MAX_HOURS = 24


def default_availability(max_hours: float) -> AvailabilityShape:
    """A distribuição de disponibilidade, dimensionada para um W_a."""
    return AvailabilityShape(
        hours_sd=max(0.1, round(max_hours * 0.10, 1)), full_load_rate=0.10
    )


DEFAULT_AVAILABILITY = default_availability(DEFAULT_MAX_HOURS)


@dataclass(frozen=True)
class Discipline:
    """Uma disciplina ofertada — o bem escasso x in B (Tabela 1)."""

    name: str
    seats: int
    hours: int
    classes: int = 1
    unlocks: tuple[str, ...] = ()
    entry: bool = False
    elective: bool = False
    fluctuation: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("disciplina sem nome")
        if self.seats < 0:
            raise ValueError(f"disciplina {self.name!r}: vagas (q_x) deve ser >= 0")
        if self.hours <= 0:
            raise ValueError(f"disciplina {self.name!r}: carga horária (w_x) deve ser > 0")
        if self.fluctuation is not None and self.fluctuation < 0.0:
            raise ValueError(
                f"disciplina {self.name!r}: a flutuação deve ser >= 0"
            )
        if self.name in self.unlocks:
            raise ValueError(f"disciplina {self.name!r} é sucessora de si mesma")
        if len(set(self.unlocks)) != len(self.unlocks):
            raise ValueError(f"disciplina {self.name!r}: sucessores repetidos")
        if self.elective and self.unlocks:
            raise ValueError(
                f"optativa {self.name!r} não pode desbloquear nada: a cadeia passaria "
                "a depender de uma disciplina que ninguém é obrigado a cursar"
            )
        if self.elective and self.entry:
            raise ValueError(
                f"optativa {self.name!r} não pode ser de entrada: a matrícula garantida "
                "entregaria parte da exigência em horas antes de o aluno disputar nada"
            )


@dataclass(frozen=True)
class SimulationConfig:
    """Cenário completo. Tudo que não está aqui é sorteado a partir de `seed`."""

    disciplines: list[Discipline] = field(default_factory=list)
    periods: int = 1
    warmup_periods: int = 0
    students_per_entry_class: int = 8
    max_residence: int | None = None

    approval_rate: float = 0.7
    grade_sd: float = 2.0
    repetition_gain: float = 1.0
    availability: AvailabilityShape | None = None
    availability_fluctuation: float = 0.5
    schedule_mean: float = 0.0
    schedule_sigma: float = 0.6
    schedule_fluctuation: float = 0.25
    selectivity_mean: float = 0.7
    selectivity_sigma: float = 0.6
    selectivity_fluctuation: float = 0.0
    grade_cuts: tuple[float, ...] = (5.0, 7.0)
    reserve_cuts: tuple[float, ...] = (0.01, 0.03)
    slots: int = 11
    first_seed: int = 1
    interest_mean: float = 1.0
    interest_sigma: float = 1.0
    interest_fluctuation: float = 0.25
    max_hours: int = DEFAULT_MAX_HOURS
    rounds: int = 1
    min_grade: float = 5.0
    elective_hours: int = 0
    min_credits: int = 12
    max_credits: int | None = 30
    mechanism: Mechanism = "credits"
    seed: int = 0

    @property
    def uses_credits(self) -> bool:
        """Se o crédito existe neste cenário. Na linha de base por CR ele não"""
        return self.mechanism == "credits"

    def band_cuts(self, axis: str) -> tuple[float, ...]:
        """Os cortes de um eixo de recorte, pelo nome com que a API o chama."""
        cuts = {
            "grade_average": tuple(float(c) for c in self.grade_cuts),
            "reserve": tuple(float(c) for c in self.reserve_cuts),
        }
        if axis not in cuts:
            raise ValueError(f"eixo de recorte desconhecido: {axis}")
        return cuts[axis]

    def band_domain(self, axis: str) -> tuple[float, float]:
        """O domínio de um eixo de recorte — ver `equations.value_band`."""
        domains = {
            "grade_average": GRADE_DOMAIN,
            "reserve": RESERVE_DOMAIN,
        }
        if axis not in domains:
            raise ValueError(f"eixo de recorte desconhecido: {axis}")
        return domains[axis]

    def __post_init__(self) -> None:
        """Recusa o cenário que não produziria simulação legível."""
        if self.availability is None:
            object.__setattr__(
                self, "availability", default_availability(self.max_hours)
            )
        self._check_horizon()
        self._check_population()
        self._check_curriculum()
        self._check_graduation()
        self._check_guaranteed_enrolment()

    def _check_horizon(self) -> None:
        if self.periods < 1:
            raise ValueError("é preciso simular ao menos 1 período")
        if self.rounds < 1:
            raise ValueError("é preciso simular ao menos 1 rodada por período")
        if not 5 <= self.min_grade <= 10:
            raise ValueError("nota mínima deve estar em [5, 10]")
        if self.min_credits < 1:
            raise ValueError("orçamento mínimo (C_min) deve ser >= 1")
        if self.max_credits is not None and self.max_credits < self.min_credits:
            raise ValueError(
                "orçamento máximo (C_max) não pode ser menor que o mínimo "
                f"(C_min = {self.min_credits})"
            )
        if self.max_hours < 1:
            raise ValueError("carga horária máxima (W_a) deve ser >= 1")
        if self.max_residence is not None and self.max_residence < 1:
            raise ValueError("o tempo até o jubilamento deve ser >= 1")

    def _check_population(self) -> None:
        if not self.disciplines:
            raise ValueError("o cenário precisa de pelo menos uma disciplina")
        if self.students_per_entry_class < 1:
            raise ValueError(
                "o cenário precisa de pelo menos um ingressante por turma de entrada"
            )
        self._check_band_cuts()
        try:
            grade_mean(
                min_grade=self.min_grade,
                grade_sd=self.grade_sd,
                approval_rate=self.approval_rate,
            )
        except ValueError as erro:
            raise ValueError(f"distribuição de desempenho: {erro}") from erro
        try:
            self.availability_shape()
        except ValueError as erro:
            raise ValueError(f"distribuição de disponibilidade: {erro}") from erro
        if self.selectivity_sigma <= 0:
            raise ValueError("o desvio da seletividade deve ser > 0")
        for nome, valor in (
            ("do interesse por disciplinas", self.interest_fluctuation),
            ("do interesse por horários", self.schedule_fluctuation),
            ("da disponibilidade", self.availability_fluctuation),
            ("da seletividade", self.selectivity_fluctuation),
        ):
            if valor < 0.0:
                raise ValueError(f"a flutuação {nome} deve ser >= 0")
        if self.schedule_sigma < 0.0:
            raise ValueError("o desvio do interesse por horário deve ser >= 0")
        if not 0 <= self.warmup_periods < self.periods:
            raise ValueError(
                "a pré-população tem de caber no horizonte e deixar ao menos um "
                "período medido"
            )
        if self.slots < 1:
            raise ValueError("é preciso ao menos um horário")
        maior_turma = max(d.classes for d in self.disciplines)
        if self.slots < maior_turma:
            raise ValueError(
                f"são precisos ao menos {maior_turma} horários: é o maior número de "
                "turmas entre as disciplinas, e com menos duas turmas da mesma "
                "disciplina cairiam no mesmo horário"
            )
        if self.interest_sigma <= 0:
            raise ValueError("desvio do interesse (sigma) deve ser > 0")
        if not math.isfinite(self.interest_mean):
            raise ValueError("a média do interesse deve ser um número finito")

    def _check_band_cuts(self) -> None:
        """Os cortes de cada eixo: distintos, dentro do domínio, e no teto."""
        for axis, nome in (
            ("grade_average", "do CR"),
            ("reserve", "da reserva"),
        ):
            cuts = self.band_cuts(axis)
            low, high = self.band_domain(axis)
            if len(cuts) > MAX_CUTS:
                raise ValueError(
                    f"os cortes {nome} são no máximo {MAX_CUTS}, que abrem "
                    f"{MAX_BANDS} faixas"
                )
            if len(set(cuts)) != len(cuts):
                raise ValueError(f"há cortes {nome} repetidos")
            for cut in cuts:
                if not math.isfinite(cut):
                    raise ValueError(f"os cortes {nome} devem ser números finitos")
                if not low < cut < high:
                    teto = "∞" if math.isinf(high) else f"{high:g}"
                    raise ValueError(
                        f"os cortes {nome} devem ficar entre {low:g} e {teto}, "
                        f"exclusive: {cut:g} está fora"
                    )

    def _check_curriculum(self) -> None:
        names = [d.name for d in self.disciplines]
        if len(set(names)) != len(names):
            raise ValueError("há disciplinas com nomes repetidos")
        known = set(names)
        for discipline in self.disciplines:
            unknown = set(discipline.unlocks) - known
            if unknown:
                raise ValueError(
                    f"disciplina {discipline.name!r} tem sucessores inexistentes: "
                    f"{sorted(unknown)}"
                )

        self.heights()

        requires = self.prerequisites_by_discipline()
        for discipline in self.disciplines:
            if not requires[discipline.name]:
                continue
            if discipline.entry:
                raise ValueError(
                    f"disciplina {discipline.name!r} é de entrada e tem pré-requisitos"
                )
            if discipline.elective:
                raise ValueError(
                    f"optativa {discipline.name!r} não pode ter pré-requisito: "
                    f"{sorted(requires[discipline.name])} a desbloqueia"
                )

    def _check_graduation(self) -> None:
        if self.elective_hours < 0:
            raise ValueError("elective_hours (X) deve ser >= 0")
        offered = sum(d.hours for d in self.disciplines if d.elective)
        if self.elective_hours > offered:
            raise ValueError(
                f"a exigência de {self.elective_hours} h optativas não cabe nas "
                f"{offered} h ofertadas em optativas: ninguém concluiria"
            )

    def _check_guaranteed_enrolment(self) -> None:
        """A matrícula garantida não escolhe quem a recebe, então a oferta de"""
        entry = self.entry_disciplines()
        if not entry:
            raise ValueError("o cenário precisa de pelo menos uma disciplina de entrada")

        counts = {len(self.classes_by_discipline()[name]) for name in entry}
        if len(counts) > 1:
            raise ValueError(
                "as disciplinas de entrada precisam ter o mesmo número de turmas, e "
                f"têm {sorted(counts)}: o ingresso é por turma de entrada, então "
                "contagens distintas implicariam uma coorte por disciplina"
            )

        offsets = self.entry_offsets()
        if offsets is None:
            raise ValueError(
                "a matrícula garantida põe duas turmas no mesmo horário para o "
                "mesmo ingressante, e giro nenhum do bloco de entrada desfaz o "
                "choque: o pacote de entrada é entregue inteiro e não pode "
                "chocar consigo mesmo — mude o número de turmas das disciplinas "
                "de entrada ou o número de horários"
            )

        newcomers = self.students_per_entry_class
        seats = self.seats_by_class()
        classes = self.classes_by_discipline()
        for discipline in entry:
            for name in classes[discipline]:
                if newcomers > seats[name]:
                    raise ValueError(
                        f"{newcomers} ingressantes por turma de entrada não cabem em "
                        f"{name!r}, que tem {seats[name]} vagas: o ingressante tem vaga "
                        "garantida em toda disciplina de entrada"
                    )

        hours = self.hours_by_discipline()
        entry_hours = sum(hours[name] for name in entry)
        if entry_hours > self.max_hours:
            raise ValueError(
                f"as {len(entry)} disciplinas de entrada somam {entry_hours} h e não "
                f"cabem na carga horária máxima (W_a = {self.max_hours}) — eq. (4); o "
                "ingressante cursa todas elas de uma vez"
            )

    def entry_offsets(self) -> dict[str, int] | None:
        """O giro do bloco de entrada de cada disciplina — ver"""
        entry = self.entry_disciplines()
        if not entry:
            return None
        classes = self.classes_by_discipline()
        schedule = self.schedule_by_class()
        blocks = max(len(classes[name]) for name in entry)

        def clash_free(step: int) -> bool:
            for block in range(blocks):
                taken: set[str] = set()
                for position, discipline in enumerate(entry):
                    names = classes[discipline]
                    index = rotated_index(
                        block=min(block, len(names) - 1),
                        offset=position * step,
                        classes=len(names),
                    )
                    slot = schedule[names[index]]
                    if slot in taken:
                        return False
                    taken.add(slot)
            return True

        for step in range(blocks):
            if clash_free(step):
                return {
                    discipline: position * step
                    for position, discipline in enumerate(entry)
                }
        return None

    def dismissal_period(self, entry_period: int) -> int | None:
        """O último período em que o aluno que entrou em `entry_period` ainda"""
        if self.max_residence is None:
            return None
        return entry_period + self.max_residence - 1

    @property
    def entry_span(self) -> int:
        """Quantos períodos recebem coorte nova — **todos**."""
        return self.periods

    def attempt_cap(self) -> int:
        """Quantas vezes, no máximo, um aluno pode cursar a mesma disciplina."""
        return self.periods

    @property
    def students_per_period(self) -> int:
        """|A_cal| — quantos ingressam por período. **Derivado** do ingresso"""
        return self.students_per_entry_class * self.entry_classes()

    def total_students(self) -> int:
        """|A| — uma coorte do mesmo tamanho em cada período."""
        return self.students_per_period * self.entry_span

    @property
    def measured_cohort(self) -> int | None:
        """A coorte medida: a que ingressa no último período de aquecimento."""
        return self.warmup_periods or None

    @property
    def first_measured_period(self) -> int:
        """O primeiro período medido: o **de ingresso** da coorte medida.

        O período de ingresso entra na medição apesar de a matrícula ali ser
        garantida, e portanto igual nos dois mecanismos. Sem aquecimento não há
        coorte medida, e aí mede-se do começo.
        """
        return self.warmup_periods or 1

    def availability_shape(self) -> tuple[float, float]:
        """(média, desvio padrão) da normal das horas, com o W_a do cenário."""
        shape = self.availability or default_availability(self.max_hours)
        return shape.shape(self.max_hours)

    def steady_population(self) -> int:
        """Quantos alunos a universidade tem **em regime**."""
        if self.max_residence is None:
            return self.total_students()
        return self.students_per_period * min(self.max_residence, self.periods)

    def _edges(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """As arestas declaradas, na ordem da grade. Serve de chave do memo"""
        return tuple((d.name, d.unlocks) for d in self.disciplines)

    def successors_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """O que cada disciplina desbloqueia **imediatamente**."""
        return dict(self._edges())

    def prerequisites_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """Aresta inversa dos sucessores: quem precisa estar aprovado"""
        return inverse_edges(self.successors_by_discipline())

    def reachable_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """seq(X) — tudo que a disciplina desbloqueia, **transitivamente**."""
        return _curriculum_closures(self._edges())[0]

    def required_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """req(X) — tudo que a disciplina exige, **transitivamente**."""
        return _curriculum_closures(self._edges())[1]

    def heights(self) -> dict[str, int]:
        """s_x — ver `equations.curriculum_height`."""
        return curriculum_heights(self.successors_by_discipline())

    def curriculum_periods(self) -> dict[str, int]:
        """O período de cada disciplina — ver `equations.curriculum_period`."""
        return curriculum_periods(self.prerequisites_by_discipline())

    def reach(self) -> dict[str, int]:
        """d_x — ver `equations.curriculum_reach`."""
        return curriculum_reach(self.successors_by_discipline())

    def entry_disciplines(self) -> list[str]:
        """Disciplinas de matrícula garantida, na ordem do cenário."""
        return [d.name for d in self.disciplines if d.entry]

    def entry_classes(self) -> int:
        """Em quantas turmas cada disciplina de entrada está repartida."""
        entry = self.entry_disciplines()
        if not entry:
            return 0
        return len(self.classes_by_discipline()[entry[0]])

    def eligible_disciplines(self, approved: set[str]) -> list[str]:
        """O conjunto elegível — ver `equations.eligible_set`."""
        return eligible_set(
            names=[d.name for d in self.disciplines],
            approved=approved,
            prerequisites=self.prerequisites_by_discipline(),
            elective_hours_by_discipline=self.elective_hours_by_discipline(),
            elective_hours_needed=self.elective_hours,
        )

    def hours_by_discipline(self) -> dict[str, int]:
        return {d.name: d.hours for d in self.disciplines}


    def classes_of(self, discipline: Discipline) -> tuple[str, ...]:
        """As turmas de uma disciplina, na ordem da escada de dificuldade."""
        if discipline.classes <= 1:
            return (discipline.name,)
        return tuple(
            f"{discipline.name} T{i}" for i in range(1, discipline.classes + 1)
        )

    def classes_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """Grupo → turmas, na ordem da grade."""
        return {d.name: self.classes_of(d) for d in self.disciplines}

    def discipline_by_class(self) -> dict[str, str]:
        """Turma → grupo. Como o grafo de conflito é uma **partição**, este"""
        return {
            name: d.name for d in self.disciplines for name in self.classes_of(d)
        }

    def seats_by_class(self) -> dict[str, int]:
        """q_x — a oferta repartida entre as turmas do grupo."""
        seats: dict[str, int] = {}
        for discipline in self.disciplines:
            names = self.classes_of(discipline)
            base, extra = divmod(discipline.seats, len(names))
            for i, name in enumerate(names):
                seats[name] = base + (1 if i < extra else 0)
        return seats

    def hours_by_class(self) -> dict[str, int]:
        """`w_x` replicado: cada turma custa a carga inteira da disciplina —"""
        return {
            name: d.hours for d in self.disciplines for name in self.classes_of(d)
        }

    def _difficulty_by_class_REMOVIDO(self) -> dict[str, float]:
        """A dificuldade da disciplina, replicada em cada turma dela."""
        return {
            name: d.difficulty
            for d in self.disciplines
            for name in self.classes_of(d)
        }

    def schedule_by_class(self) -> dict[str, str]:
        """Turma → horário — ver `equations.class_schedule`."""
        names = [
            name
            for discipline in self.disciplines
            for name in self.classes_of(discipline)
        ]
        return dict(zip(names, class_schedules(count=len(names), slots=self.slots)))

    def schedules(self) -> tuple[str, ...]:
        """`G` — todos os horários do cenário, na ordem da tela."""
        return schedule_names(slots=self.slots)

    def discipline_cliques(self) -> tuple[frozenset[str], ...]:
        """`M` — um clique por disciplina com mais de uma turma."""
        return tuple(
            frozenset(names)
            for d in self.disciplines
            if len(names := self.classes_of(d)) > 1
        )

    def schedule_cliques(self) -> tuple[frozenset[str], ...]:
        """`G` — um clique por horário com mais de uma turma."""
        return schedule_cliques(self.schedule_by_class(), self.schedules())

    def exclusion_cliques(self) -> tuple[frozenset[str], ...]:
        """`E = M ∪ G` — o que a eq. (5) proíbe levar junto."""
        return self.discipline_cliques() + self.schedule_cliques()

    def conflict_groups(self) -> dict[str, tuple[str, ...]]:
        """Turma → os grupos de `E` a que ela pertence: a disciplina e o"""
        schedule = self.schedule_by_class()
        return {
            name: (d.name, schedule[name])
            for d in self.disciplines
            for name in self.classes_of(d)
        }

    def required_disciplines(self) -> set[str]:
        """As obrigatórias — o que a eq. (40) exige aprovar uma a uma."""
        return {d.name for d in self.disciplines if not d.elective}

    def elective_hours_by_discipline(self) -> dict[str, int]:
        """Carga de cada optativa, para somar o que o aluno já cumpriu de X."""
        return {d.name: d.hours for d in self.disciplines if d.elective}

    def hours_to_graduate(self) -> int:
        """S — a carga horária mínima para concluir: a soma de w_x de **todas"""
        required = sum(d.hours for d in self.disciplines if not d.elective)
        return required + self.elective_hours

    def minimum_periods_to_graduate(self) -> int:
        """Piso de períodos para concluir: nem quem nunca reprova nem perde uma"""
        by_hours = -(-self.hours_to_graduate() // self.max_hours)
        by_chain = max(self.curriculum_periods().values(), default=0)
        return max(by_hours, by_chain)


def horizon_for_window(*, max_residence: int) -> int:
    """|T| — o horizonte, com uma coorte medida."""
    return 2 * max_residence - 1
