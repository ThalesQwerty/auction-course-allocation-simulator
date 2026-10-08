"""Notas e retorno de créditos (Seção 7.2.2).

As notas são um parâmetro de entrada, não um sorteio em tempo de execução: a
matriz com o sorteio de cada par (aluno, disciplina) em **cada período** é
gerada junto com a população, a partir da normal do cenário. Em tempo de
execução só se aplica o deslocamento da recursada, que é determinístico — nenhum
sorteio dentro do loop, como exige a Seção 7.3.

**Uma matriz por período, e a recursada desloca a média.** O aluno que repete
uma disciplina não recebe a nota anterior mais um incremento: ele tira uma nota
nova, de uma normal cuja **média** subiu `learning_gain` por tentativa já feita.
Em distribuição é a mesma coisa que somar o incremento ao sorteio do período, e
é assim que a conta é feita — o sorteio sai cru de `draw_grades` e
`grade_for_attempt` desloca, arredonda e trunca.

A diferença em relação ao modelo anterior (um sorteio por par, fixo, mais o
incremento) é que **a recursada deixa de garantir nota maior**: o aluno aprende,
mas pode ter um dia pior. O que continua garantido é que `Student.grades` guarda
a **maior** nota já obtida, então o histórico não regride, e que a média sobe a
cada tentativa — de modo que a probabilidade de aprovar tende a 1 e ninguém fica
preso numa disciplina para sempre. A monotonicidade da eq. (33) vale no
esperado e no registro, não em cada sorteio.
"""
from __future__ import annotations

import numpy as np

from .config import CreditReturnPolicy, Discipline, SimulationConfig
from .population import Student


def draw_grades(
    students: list[Student],
    disciplines: list[Discipline],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, str, int], float]:
    """Sorteia a matriz de notas inteira — todo par (aluno, disciplina), todo
    período — na inicialização, a partir da seed.

    O valor sai **cru**: da normal do cenário (`grade_mean`, `grade_stddev`),
    sem deslocamento, sem arredondamento e sem truncagem. Quem o transforma em
    nota é `grade_for_attempt`, porque o deslocamento da recursada depende de
    quantas vezes o aluno já cursou aquela disciplina — informação que só existe
    em tempo de execução. Truncar aqui e deslocar depois mudaria a conta: uma
    nota negativa viraria 0 antes de receber o incremento.

    Todo par sorteia da **mesma** normal: dois alunos diferem por sorteio, não
    por construção. A dispersão que o CR precisa para não virar ruído vem de
    `grade_stddev`. A distribuição não é fixada pelo anteprojeto; a normal é
    escolha de modelagem, e seus parâmetros são do cenário.
    """
    draws = rng.normal(
        config.grade_mean,
        config.grade_stddev,
        size=(len(students), len(disciplines), config.periods),
    )
    return {
        (student.id, discipline.name, period + 1): float(draws[i, j, period])
        for i, student in enumerate(students)
        for j, discipline in enumerate(disciplines)
        for period in range(config.periods)
    }


# Faixas do histograma de notas — as mesmas dez das utilidades, de modo que os
# dois gráficos se leiam do mesmo jeito. Aqui elas também caem bem na escala:
# as divisas são 0, 1, 2 ... 10, que é como se lê uma nota.
DISTRIBUTION_BINS = 10


def grade_distribution(
    draws: dict[tuple[str, str, int], float],
    config: SimulationConfig,
    bins: int = DISTRIBUTION_BINS,
) -> list[float]:
    """Como as notas de **primeira tentativa** se distribuem, em `bins` faixas
    de mesma largura sobre [0, 10].

    É a normal do cenário já passada por `grade_for_attempt` — truncada e
    arredondada —, que é o que a torna visível: o truncamento empilha massa nas
    pontas sempre que a média estiver perto delas, e isso não se lê dos
    parâmetros.

    Primeira tentativa, e não todas: a recursada desloca a média pelo incremento
    de aprendizado, então misturar as tentativas somaria distribuições
    diferentes e o gráfico deixaria de descrever a normal do cenário. Quantas
    recursadas acontecem é resultado, não entrada.
    """
    counts = [0] * bins
    for drawn in draws.values():
        grade = grade_for_attempt(drawn, 1, config.learning_gain)
        counts[min(bins - 1, int(grade / 10 * bins))] += 1
    total = sum(counts)
    if not total:
        return [0.0] * bins
    return [count / total for count in counts]


def grade_for_attempt(drawn: float, attempt: int, gain: float) -> float:
    """Nota da `attempt`-ésima tentativa (1 = primeira), a partir do sorteio
    cru daquele período — eq. (33).

    O deslocamento é de `gain` pontos por tentativa **já feita**, o que equivale
    a sortear de uma normal de média `grade_mean + gain * (attempt - 1)`. Só
    depois a nota é arredondada a 0,1 e truncada em [0, 10], que é o domínio das
    notas da Seção 7.2.2.
    """
    if attempt < 1:
        raise ValueError("attempt deve ser >= 1")
    return min(10.0, max(0.0, round(drawn + gain * (attempt - 1), 1)))


def credit_return(
    policy: CreditReturnPolicy, *, paid: int, grade: float, min_grade: float
) -> int:
    """gamma_{a,x}^(t) — retorno de créditos por disciplina cursada, eq. (34).

    f_gamma é função do preço pago e da nota obtida. O anteprojeto deixa a
    forma concreta em aberto (é o eixo de experimentação da Seção 7.3.2);
    estas são as quatro políticas comparadas, da mais restritiva à mais
    generosa:

    - `none`: nunca devolve nada. O crédito gasto sai do sistema, e a única
      entrada é o Gamma_min de cada período — é a linha de base.
    - `unit`: 1 crédito por aprovação, qualquer que tenha sido o preço. Premia
      aprovar, não o quanto se pagou: quem brigou por uma vaga disputada
      recupera o mesmo que quem pegou uma vaga sobrando.
    - `full`: devolve o preço inteiro a quem aprova. O crédito só se perde de
      fato na reprovação, de modo que a disputa não empobrece quem passa.
    - `ratio`: devolve a fatia do preço correspondente à nota, sem exigir
      aprovação — quem foi mal recupera pouco, quem foi bem recupera quase
      tudo. É a única que premia desempenho acima da nota de corte.
    """
    if policy == "none":
        return 0
    if policy == "unit":
        return 1 if grade >= min_grade else 0
    if policy == "full":
        return paid if grade >= min_grade else 0
    if policy == "ratio":
        # round() do Python desempata para o par (round(2.5) == 2), e o empate
        # exato em 0,5 é comum aqui — as notas andam de 0,1 em 0,1 e os preços
        # são inteiros pequenos. O viés é o mesmo para todo aluno, que é o que
        # importa na comparação entre políticas.
        return round(grade / 10 * paid)
    raise ValueError(f"política de retorno de créditos desconhecida: {policy!r}")
