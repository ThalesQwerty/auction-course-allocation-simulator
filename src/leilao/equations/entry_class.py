"""A turma de entrada de um calouro.

    bloco(i)       = ⌊i·k / |A|⌋
    turma(i, g, D) = T_{(bloco(i) + g) mod D}          , se bloco(i) < D
                   = T_{D + ((bloco(i) − D) + g) mod N}, caso contrário

    k = turmas da disciplina;  D = diurnas;  N = noturnas;  g = o giro da
    disciplina, dado por `config.entry_offsets`

O ingressante não escolhe turma: a matrícula garantida não passa pelo
mecanismo, nem num braço nem no outro. A coorte é repartida em blocos
contíguos de tamanho |A|/k, na ordem em que os alunos foram gerados — os |A|/k
primeiros no primeiro bloco, os seguintes no segundo, e assim por diante.

POR QUE EM BLOCOS, E NÃO SORTEADO
----------------------------------

Porque não há sorteio em tempo de execução (ver `simulation.setup`), e porque
o bloco é o único jeito de a repartição ser **exata** sem consultar nada: a
soma dos blocos é a coorte, e cada turma recebe ⌊|A|/k⌋ ou ⌈|A|/k⌉. Sortear
deixaria uma turma de entrada estourada e outra vazia em coortes pequenas.

O ordinal é a posição do aluno na coorte, e o rodízio de perfis
(`config.profile_index`) é sobre o índice **global**, não sobre este: dois
calouros vizinhos têm perfis diferentes, de modo que o bloco não concentra um
perfil numa turma.

POR QUE O BLOCO GIRA ENTRE AS DISCIPLINAS
------------------------------------------

Sem giro, quem é do bloco 0 levaria a **primeira** turma de toda disciplina de
entrada — e, como o horário é atribuído varrendo a grade disciplina a
disciplina (`equations.class_schedule`), as primeiras turmas de disciplinas
distintas voltam a cair no mesmo horário assim que a varredura dá a volta. O
pacote garantido sairia em choque consigo mesmo, violando a eq. (5) antes de o
leilão abrir.

O giro desloca o bloco em `g` posições, e com isso dois pacotes do mesmo bloco
deixam de coincidir no horário. Ele é uma **permutação** das turmas dentro da
disciplina, então a repartição continua exata: a mesma lista de cargas,
pareada com outra turma.

Quem escolhe `g` é `config.entry_offsets`, que procura o menor passo de uma
progressão aritmética — a j-ésima disciplina de entrada gira `j · passo` — que
deixe todos os blocos sem choque. **O passo 0 é tentado primeiro**, de modo que
a grade que já saía sem choque não é girada e continua bit a bit igual. Onde
passo nenhum resolve, o cenário é recusado: a garantia da varredura circular é
de que *existe* uma grade sem choque no período, não de que uma progressão
aritmética a encontra em toda grade concebível.

O giro é **dentro do turno**: o bloco diurno continua diurno e o noturno
continua noturno, porque girar através da fronteira faria o mesmo calouro
receber metade do pacote de manhã e metade à noite. A consequência de o turno
seguir o bloco permanece declarada: o calouro de bloco baixo entra no diurno e
o de bloco alto no noturno, independentemente da rotina dele.

Não está no anteprojeto, que é de turma única: lá a matrícula garantida
(Seção 5.3) concede a própria disciplina.
"""
from __future__ import annotations

from collections.abc import Sequence

from .class_shift import NIGHT, class_shifts


def entry_block(*, ordinal: int, cohort: int, classes: int) -> int:
    """O bloco da coorte a que o ordinal pertence."""
    if classes <= 0:
        raise ValueError("uma disciplina de entrada precisa de pelo menos uma turma")
    if cohort <= 0:
        return 0
    return min(max(ordinal * classes // cohort, 0), classes - 1)


def rotated_index(*, block: int, offset: int, classes: int) -> int:
    """O índice da turma que o bloco recebe, girado `offset` posições **dentro
    do turno** dele."""
    night = class_shifts(classes).count(NIGHT)
    day = classes - night
    if block < day:
        return (block + offset) % day
    return day + ((block - day) + offset) % night


def entry_class(
    *, ordinal: int, cohort: int, classes: Sequence[str], offset: int = 0
) -> str:
    if not classes:
        raise ValueError("uma disciplina de entrada precisa de pelo menos uma turma")
    block = entry_block(ordinal=ordinal, cohort=cohort, classes=len(classes))
    return classes[rotated_index(block=block, offset=offset, classes=len(classes))]


def entry_class_load(
    *, cohort: int, classes: Sequence[str], offset: int = 0
) -> dict[str, int]:
    """Quantos calouros cada turma recebe — a contagem dos blocos, já girada.

    É o que `config` compara com a oferta de cada turma: a validação da
    matrícula garantida é por turma, não por disciplina, porque é a turma que
    tem vaga.
    """
    load = {name: 0 for name in classes}
    for ordinal in range(max(cohort, 0)):
        load[
            entry_class(
                ordinal=ordinal, cohort=cohort, classes=classes, offset=offset
            )
        ] += 1
    return load
