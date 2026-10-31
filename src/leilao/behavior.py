"""O sorteio da matriz de utilidades e o recorte dela (Seção 7.2.4).

A matriz é **parâmetro de entrada**, como a aptidão: todo o sorteio acontece
na inicialização, a partir da seed, para todos os alunos e todos os períodos
de uma vez. Em tempo de execução só se recorta o que já foi sorteado, e os
lances saem deterministicamente dali — nenhuma aleatoriedade dentro do laço,
como exige a Seção 7.3.

Isso importa para comparar cenários: com o sorteio dentro do laço, mexer numa
vaga deslocaria o fluxo do gerador e mudaria as preferências de todo mundo, e
a diferença entre dois cenários deixaria de ser atribuível ao mecanismo. Há
um teste que triplica as vagas e confirma que nenhuma utilidade se mexe.

**Uma linha por (aluno, período).** O gosto é resorteado a cada período, na
proporção que `utility_stability` deixa para o ruído do semestre — a conta
está em `equations.preference_split`. Com uma preferência fixa, perder uma
vaga disputada condenava o aluno a querer a mesma disciplina com a mesma
intensidade até consegui-la, e a fila se acumulava.

As três contas feitas sobre o sorteio têm arquivo próprio:
`equations.preference_split` (repartição da variância),
`equations.utility_row` (altura e normalização) e `equations.eligible_set`
(os zeros da eq. 42).

ORDEM DE DESEMPATE
------------------

Quando duas disciplinas valem o mesmo para um aluno, ganha a **listada
primeiro** no cenário. É uma ordem global — a mesma para todo aluno, período
e rodada — e vale nas duas decisões que o aluno toma sozinho: a mochila
côncava do lance e a lista ordenada do pedido por CR.

Ela se propaga sem ninguém carregá-la de propósito: `eligible_set` varre as
disciplinas na ordem do cenário, `utility_matrix` constrói o dicionário nessa
varredura, e dicionário em Python preserva a ordem de inserção. Por isso as
duas mochilas leem o posto a partir de `utilities`, nunca de `available`, que
é só um filtro e pode chegar em qualquer ordem.

Com utilidade sorteada o empate tem probabilidade zero, então a regra quase
nunca é acionada. Ela existe para que um cenário escrito à mão — uma grade
simétrica, um teste — não dependa da ordem de iteração, que é a mesma
exigência de determinismo que mantém os sorteios fora do laço. Não se confunde
com α/ε (eq. 20): aquilo desempata **entre alunos**, dentro do leilão; isto,
**entre disciplinas**, dentro da cabeça de um aluno.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import numpy as np

from .config import SimulationConfig
from .equations import (
    NEUTRAL,
    Behavior,
    Signals,
    concave_bids,
    decision_scores,
    normalize_with_height_shift,
    preference_split,
)
from .equations.utility_histogram import BINS as DISTRIBUTION_BINS
from .equations.utility_histogram import utility_histogram

if TYPE_CHECKING:  # `population` importa `Behavior` daqui; o ciclo só existe
    from .population import Student  # em tempo de verificação de tipo.

# Guarda contra underflow, **não** parâmetro de modelagem. A log-normal só
# chegaria a 0,0 com expoente abaixo de −745, o que não acontece em σ nenhum
# que faça sentido — ela é seguro, não mecanismo.
#
# Existe porque utilidade zero é o que marca o **inelegível**, e as duas
# mochilas filtram por `utilidade > 0`: um zero aqui tiraria a disciplina do
# conjunto de escolha e o aluno nunca a cursaria, nem sendo a única disponível.
UNDERFLOW_GUARD = sys.float_info.min

__all__ = [
    "DISTRIBUTION_BINS",
    "NEUTRAL",
    "UNDERFLOW_GUARD",
    "Behavior",
    "Signals",
    "compute_bids",
    "decision_scores",
    "draw_utilities",
    "utility_distribution",
    "utility_matrix",
]


def _stability_by_discipline(config: SimulationConfig) -> np.ndarray:
    """A estabilidade de cada disciplina, com o valor do cenário como padrão.

    Declarar por disciplina é o que **sincroniza** a persistência entre
    concorrentes: se todos que querem uma disciplina continuam querendo ao
    mesmo tempo, a disputa por ela congela inteira em vez de girar, e é essa
    sincronia — não a persistência em si — que trava a fila.
    """
    return np.array(
        [
            config.utility_stability if d.stability is None else d.stability
            for d in config.disciplines
        ],
        dtype=float,
    ).reshape(1, 1, -1)


def _attractiveness(config: SimulationConfig) -> np.ndarray:
    """A_x de cada disciplina, pronta para somar no logaritmo.

    É a **componente comum** do gosto: todo aluno a recebe igual, enquanto
    sigma reparte o que é privado de cada um. A razão entre as duas é
    literalmente a correlação de preferência entre dois alunos no mesmo
    período — a irmã do que `stability` faz entre dois períodos do mesmo aluno.

    Entra como deslocamento do log porque a utilidade preliminar é log-normal:
    multiplicar o sorteio por A é somar ln A antes de exponenciar, e aí A
    continua sendo "múltiplos da disciplina média" em vez de virar um segundo
    botão de dispersão.
    """
    return np.log(
        np.array([d.attractiveness for d in config.disciplines], dtype=float)
    ).reshape(1, 1, -1)


def draw_utilities(
    students: list["Student"], config: SimulationConfig, rng: np.random.Generator
) -> dict[tuple[str, int], dict[str, float]]:
    """Sorteia a matriz inteira: uma linha por (aluno, período), sobre a grade.

    O valor preliminar vem de uma **log-normal** de média logarítmica 0 e
    desvio σ, repartida entre uma peça permanente e um ruído do semestre
    (`preference_split`). A log-normal é o que se obtém quando a grandeza é
    **produto** de muitos fatores independentes — e é assim que se forma o
    quanto alguém quer uma disciplina: interesse no tema vezes afinidade com a
    área vezes horário vezes dificuldade percebida. É uma afirmação sobre
    alunos, não sobre a ignorância de quem modela.

    σ é o único parâmetro de dispersão, e **grande concentra, pequeno
    achata**: o coeficiente de variação é √(e^{σ²} − 1), que cresce depressa,
    de modo que a faixa útil inteira cabe entre ~0,25 (aluno quase
    indiferente) e ~3 (quer uma disciplina e despreza o resto). A média do
    logaritmo não é configurável porque some na normalização — deslocá-la
    multiplica a linha por uma constante. E a moda do sorteio cru é e^{−σ²},
    sempre positiva: não há limiar de σ a respeitar.

    **A atratividade da disciplina desloca esse logaritmo** (`_attractiveness`):
    sigma é a dispersão privada de cada aluno, A_x é o nível comum a todos. Com
    A uniforme as linhas são independentes e a disputa por uma disciplina não
    tem como ser antecipada pelo próprio gosto; com A espalhado, gostar muito de
    algo passa a ser sinal de que os colegas também gostam.

    O que vem depois do sorteio — deslocamento por altura e normalização —
    está em `equations.utility_row`. Note que **a invariante de altura domina a
    atratividade**: o degrau entre camadas é a amplitude da linha mais 1, maior
    que qualquer A, de modo que A ordena dentro de uma altura e não entre
    alturas. Como optativa tem altura 0, nenhuma atratividade a faz passar à
    frente de uma obrigatória.
    """
    names = [d.name for d in config.disciplines]
    shape = (len(students), config.periods, len(names))
    log = preference_split(
        permanent=rng.normal(0.0, 1.0, size=(len(students), 1, len(names))),
        seasonal=rng.normal(0.0, 1.0, size=shape),
        stability=_stability_by_discipline(config),
        sigma=config.utility_sigma,
    ) + _attractiveness(config)
    heights = config.heights()
    normalized = normalize_with_height_shift(
        np.maximum(np.exp(log), UNDERFLOW_GUARD),
        np.array([heights[name] for name in names], dtype=float),
    )
    return {
        (student.id, period + 1): {
            name: float(normalized[a, period, j]) for j, name in enumerate(names)
        }
        for a, student in enumerate(students)
        for period in range(config.periods)
    }


def utility_distribution(
    rows: dict[tuple[str, int], dict[str, float]], bins: int = DISTRIBUTION_BINS
) -> list[float]:
    """O histograma da matriz — ver `equations.utility_histogram`."""
    return utility_histogram(rows.values(), bins)


def utility_matrix(
    *, row: dict[str, float], student: "Student", config: SimulationConfig
) -> dict[str, float]:
    """u_{a,·}^(t): o recorte elegível da linha do aluno — eqs. (41)-(43).

    Determinística: mesma linha e mesmo estado do aluno, mesma saída. Devolve
    só as disciplinas do conjunto elegível (`equations.eligible_set`); as já
    aprovadas e as ainda bloqueadas valem zero por construção e não aparecem.

    **Os valores não são renormalizados.** São os mesmos da linha sorteada, e
    a soma deles é o U_a^(t) da eq. (43) — menor que 1 sempre que algo estiver
    fora do alcance do aluno. Isso não muda alocação nenhuma: as duas mochilas
    comparam só razões.

    A **ordem das chaves** é a da grade no cenário, e é carga: é dela que as
    duas mochilas tiram o desempate. Reordenar a saída muda resultado.
    """
    return {
        name: row[name]
        for name in config.eligible_disciplines(student.approved(config.min_grade))
    }


def compute_bids(
    *,
    utilities: dict[str, float],
    available: list[str],
    budget: int,
    behavior: Behavior = NEUTRAL,
    signals: Signals | None = None,
    catalogue: int = 0,
) -> dict[str, int]:
    """c_{a,·}^(t,r): a estratégia do aluno no leilão.

    `available` é B_a^(t,r) (eq. 15) e `budget` é C_a^(t,r). O score vem de
    `equations.decision_score` e a repartição, de `equations.concave_bids`.
    """
    return concave_bids(
        scores=decision_scores(
            utilities=utilities,
            behavior=behavior,
            signals=signals,
            catalogue=catalogue,
        ),
        available=available,
        budget=budget,
        reserve=behavior.reserve,
    )
