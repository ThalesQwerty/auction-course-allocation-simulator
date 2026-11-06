"""A turma de entrada de um calouro.

    turma(i) = T_{⌊i·k / |A|⌋}

O ingressante não escolhe turma: a matrícula garantida não passa pelo
mecanismo, nem num braço nem no outro. A coorte é repartida em blocos
contíguos de tamanho |A|/k, na ordem em que os alunos foram gerados — os |A|/k
primeiros na primeira turma, os seguintes na segunda, e assim por diante.

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

A MESMA FATIA EM TODA DISCIPLINA DE ENTRADA
-------------------------------------------

O bloco não gira entre as disciplinas: quem é do bloco 0 leva a primeira turma
de **toda** disciplina de entrada. É o que a regra diz, e tem uma consequência
a declarar: se a escada de dificuldade (`class_difficulty`) estiver ligada, o
primeiro bloco cursa a turma fácil de tudo e o último, a difícil de tudo.
Girar o bloco por disciplina desfaria isso, mas quebraria a correspondência
entre o tamanho do bloco e o da turma — que é o que torna a validação de
`_check_guaranteed_enrolment` suficiente. Com a escada desligada (o padrão)
não há diferença alguma entre os blocos.

Não está no anteprojeto, que é de turma única: lá a matrícula garantida
(Seção 5.3) concede a própria disciplina.
"""
from __future__ import annotations

from collections.abc import Sequence


def entry_class(*, ordinal: int, cohort: int, classes: Sequence[str]) -> str:
    if not classes:
        raise ValueError("uma disciplina de entrada precisa de pelo menos uma turma")
    if cohort <= 0:
        return classes[0]
    block = ordinal * len(classes) // cohort
    return classes[min(max(block, 0), len(classes) - 1)]


def entry_class_load(*, cohort: int, classes: Sequence[str]) -> dict[str, int]:
    """Quantos calouros cada turma recebe — a contagem dos blocos.

    É o que `config` compara com a oferta de cada turma: a validação da
    matrícula garantida é por turma, não por disciplina, porque é a turma que
    tem vaga.
    """
    load = {name: 0 for name in classes}
    for ordinal in range(max(cohort, 0)):
        load[entry_class(ordinal=ordinal, cohort=cohort, classes=classes)] += 1
    return load
