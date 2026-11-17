"""O horário de cada turma — a distribuição circular.

    n-ésima turma diurna  →  Diurno  (n mod |G_diurno|) + 1
    n-ésima turma noturna →  Noturno (n mod |G_noturno|) + 1

`n` conta a partir de 0, **dentro do turno**, varrendo a grade na ordem em que
ela é declarada: período, disciplina, turma, com as optativas no fim.

Cada horário é um grupo de **exclusão mútua** entre turmas (eq. 5): ninguém
cursa duas disciplinas no mesmo horário. Com os horários, o conjunto `X` do
anteprojeto deixa de ser só a disciplina e passa a ser `E = M ∪ G` — as
turmas da mesma disciplina mais as turmas do mesmo horário.

AS DUAS GARANTIAS
-----------------

**Equilíbrio.** O número de turmas por horário difere em no máximo 1, na grade
inteira e dentro de cada período — é o que a varredura circular dá de graça.
Na grade padrão: 17 a 18 turmas por horário diurno e 12 a 13 por noturno.

**Uma turma de cada obrigatória.** Em todo período existe uma grade sem
choque, inclusive só no diurno ou só no noturno. Com `D` turmas diurnas por
disciplina e a varredura circular, cada horário aparece no máximo `⌈D/2⌉`
vezes entre as diurnas de uma disciplina do período; então `t` disciplinas
ocupam ao menos `t` horários distintos, e o teorema de Hall garante o
emparelhamento. Nas noturnas o limite é `N`.

As **condições** para isso valerem são do cenário, não desta função: até 6
disciplinas por período, disciplinas do mesmo período declaradas em
sequência, e no máximo `|G_diurno|` turmas diurnas e `|G_noturno|` noturnas
por disciplina.

**Uma turma ocupa um horário**, seja de 2 h ou de 3 h. É simplificação
declarada: o choque é de encontro, não de minuto.

Não está no anteprojeto, que não modela horário.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from .class_shift import NIGHT

DAY_LABEL = "Diurno"
NIGHT_LABEL = "Noturno"


def class_schedules(
    *, shifts: Iterable[str], day_slots: int, night_slots: int
) -> tuple[str, ...]:
    """Um horário por turma, na ordem de `shifts` — que é a ordem da grade."""
    slots = {True: max(night_slots, 1), False: max(day_slots, 1)}
    seen = {True: 0, False: 0}
    schedules: list[str] = []
    for shift in shifts:
        nocturnal = shift == NIGHT
        index = seen[nocturnal]
        seen[nocturnal] = index + 1
        label = NIGHT_LABEL if nocturnal else DAY_LABEL
        schedules.append(f"{label} {index % slots[nocturnal] + 1}")
    return tuple(schedules)


def schedule_names(*, day_slots: int, night_slots: int) -> tuple[str, ...]:
    """Todos os horários do cenário, diurnos antes dos noturnos. É `G`."""
    return tuple(
        f"{DAY_LABEL} {i + 1}" for i in range(max(day_slots, 0))
    ) + tuple(f"{NIGHT_LABEL} {i + 1}" for i in range(max(night_slots, 0)))


def schedule_cliques(
    schedule_of: dict[str, str], order: Sequence[str] = ()
) -> tuple[frozenset[str], ...]:
    """Os grupos de `G` com mais de uma turma — os únicos que restringem algo.

    `order` fixa a ordem da saída; omitida, sai na ordem de primeiro
    aparecimento em `schedule_of`.
    """
    members: dict[str, set[str]] = {}
    for name, schedule in schedule_of.items():
        members.setdefault(schedule, set()).add(name)
    keys = [key for key in order if key in members] or list(members)
    return tuple(frozenset(members[key]) for key in keys if len(members[key]) > 1)
