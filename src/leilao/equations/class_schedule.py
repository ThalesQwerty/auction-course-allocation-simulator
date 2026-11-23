"""O horário de cada turma — a distribuição circular.

    n-ésima turma da grade  →  Horário (n mod |G|) + 1

`n` conta a partir de 0, varrendo a grade na ordem em que ela é declarada:
período, disciplina, turma, com as optativas no fim.

Cada horário é um grupo de **exclusão mútua** entre turmas (eq. 5): ninguém
cursa duas disciplinas no mesmo horário. Com os horários, o conjunto `X` do
anteprojeto deixa de ser só a disciplina e passa a ser `E = M ∪ G` — as
turmas da mesma disciplina mais as turmas do mesmo horário.

**Não há turno.** Houve uma divisão entre horários diurnos e noturnos, com
um terço da oferta à noite e um multiplicador de interesse por turno (o
perfil de rotina), até 19/11/2026. Ela saiu inteira: o horário passou a ser
posição numa régua só, e o que distingue uma turma da outra para o aluno é
apenas o sorteio do interesse (`behavior.draw_interest`, repartido por
`class_stability`). A consequência aceita é que turmas da mesma disciplina
ficam estatisticamente intercambiáveis — o congestionamento que interessa
passa a vir da **dificuldade**, pelos repetentes que continuam elegíveis.

AS DUAS GARANTIAS
-----------------

**Equilíbrio.** O número de turmas por horário difere em no máximo 1 na grade
inteira — é o que a varredura circular dá de graça.

**Uma turma de cada disciplina sem choque.** Como a varredura é contígua, as
`k` turmas de uma disciplina caem em `k` horários **consecutivos**, e portanto
distintos, desde que `k ≤ |G|`. Essa é a condição que o cenário valida
(`SimulationConfig.__post_init__`): sem ela duas turmas da mesma disciplina
dividiriam horário e a oferta efetiva encolheria em silêncio.

Para que todo *período* tenha uma grade sem choque — uma turma de cada
obrigatória do período, todas em horários distintos — é preciso também que
`|G|` não seja menor que o número de disciplinas do período, e que as
disciplinas de um mesmo período sejam declaradas em sequência. Essa segunda
condição é **documentada, não verificada**: o emparelhamento depende de como
as corridas de turmas se sobrepõem ao dar a volta, e um cenário que a viole
apenas torna algumas combinações impossíveis, o que não é estado inválido.

**Uma turma ocupa um horário**, seja de 2 h ou de 3 h. É simplificação
declarada: o choque é de encontro, não de minuto.

Não está no anteprojeto, que não modela horário.
"""
from __future__ import annotations

from collections.abc import Sequence

LABEL = "Horário"


def class_schedules(*, count: int, slots: int) -> tuple[str, ...]:
    """Os horários das `count` turmas, na ordem da grade."""
    total = max(slots, 1)
    return tuple(f"{LABEL} {index % total + 1}" for index in range(max(count, 0)))


def schedule_names(*, slots: int) -> tuple[str, ...]:
    """Todos os horários do cenário, na ordem da régua. É `G`."""
    return tuple(f"{LABEL} {index + 1}" for index in range(max(slots, 0)))


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
