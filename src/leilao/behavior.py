"""O sorteio do interesse e a utilidade que sai dele (Seção 7.2.4).

**Interesse** é o quanto o aluno quer cada disciplina: o sorteio normalizado
sobre a grade inteira, que soma 1 e não depende do histórico. **Utilidade** é
esse interesse com o inelegível zerado e redistribuído sobre o que ele pode
cursar — soma 1 no elegível e depende do histórico. A fronteira entre os dois
está em `equations.utility`.

O interesse é **parâmetro de entrada**, como a aptidão: todo o sorteio
acontece na inicialização, a partir da seed, para todos os alunos e todos os
períodos de uma vez. Em tempo de execução ele só é convertido em utilidade
pelo estado do aluno, e os lances saem deterministicamente dali — nenhuma
aleatoriedade dentro do laço, como exige a Seção 7.3.

Isso importa para comparar cenários: com o sorteio dentro do laço, mexer numa
vaga deslocaria o fluxo do gerador e mudaria as preferências de todo mundo, e
a diferença entre dois cenários deixaria de ser atribuível ao mecanismo. Há
um teste que triplica as vagas e confirma que nenhum interesse se mexe.

**Uma linha por (aluno, período).** O gosto é resorteado a cada período, na
proporção que `interest_stability` deixa para o ruído do semestre — a conta
está em `equations.preference_split`. Com uma preferência fixa, perder uma
vaga disputada condenava o aluno a querer a mesma disciplina com a mesma
intensidade até consegui-la, e a fila se acumulava.

As contas feitas sobre o sorteio têm arquivo próprio. Do lado do interesse,
`equations.preference_split` (repartição da variância) e
`equations.interest_row` (normalização); do lado da utilidade,
`equations.eligible_set` (os zeros da eq. 42) e `equations.utility` (a
redistribuição).

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

Com interesse sorteado o empate tem probabilidade zero, então a regra quase
nunca é acionada. Ela existe para que um cenário escrito à mão — uma grade
simétrica, um teste — não dependa da ordem de iteração, que é a mesma
exigência de determinismo que mantém os sorteios fora do laço. Não se confunde
com α/ε (eq. 20): aquilo desempata **entre alunos**, dentro do leilão; isto,
**entre disciplinas**, dentro da cabeça de um aluno.
"""
from __future__ import annotations

import sys
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

import numpy as np

from .config import SimulationConfig
from .equations import (
    NEUTRAL,
    Behavior,
    admitted_set,
    concave_bids,
    normalize_rows,
    preference_split,
    reserve_threshold,
    routine_weights,
    utility,
)
from .equations.interest_histogram import BINS as DISTRIBUTION_BINS
from .equations.interest_histogram import interest_histogram

if TYPE_CHECKING:  # `population` importa `Behavior` daqui; o ciclo só existe
    from .population import Student  # em tempo de verificação de tipo.

# Guarda contra underflow, **não** parâmetro de modelagem. A log-normal só
# chegaria a 0,0 com expoente abaixo de −745, o que não acontece em σ nenhum
# que faça sentido — ela é seguro, não mecanismo.
#
# Existe porque utilidade zero é o que marca o **inelegível**, e as duas
# mochilas filtram por `utilidade > 0`: um interesse zero aqui viraria utilidade
# zero, tiraria a disciplina do conjunto de escolha e o aluno nunca a cursaria,
# nem sendo a única disponível.
UNDERFLOW_GUARD = sys.float_info.min

__all__ = [
    "DISTRIBUTION_BINS",
    "NEUTRAL",
    "UNDERFLOW_GUARD",
    "Behavior",
    "InterestMatrix",
    "compute_bids",
    "decide",
    "draw_interest",
    "interest_distribution",
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
            config.interest_stability if d.stability is None else d.stability
            for d in config.disciplines
        ],
        dtype=float,
    ).reshape(1, 1, -1)


def _routine_log_weights(
    students: list["Student"], shifts: list[str]
) -> np.ndarray:
    """ln do multiplicador de turno de cada par (aluno, turma).

    É a **componente privada do turno**: dois alunos com a mesma rotina a
    recebem igual, e é por isso que ela não se cancela na normalização —
    varia dentro da linha, entre turmas diurnas e noturnas. Ver
    `equations.routine_weight`.

    O cálculo é cacheado por par (diurno, noturno) porque são três perfis
    para milhares de alunos; o `np.log` entra porque é lá que a log-normal
    mora, e multiplicar o sorteio por `m` é somar `ln m` ao expoente.
    """
    cache: dict[tuple[float, float], np.ndarray] = {}

    def row(profile) -> np.ndarray:
        key = (profile.day, profile.night)
        cached = cache.get(key)
        if cached is None:
            cached = np.log(
                np.array(
                    routine_weights(
                        shifts=shifts, day=profile.day, night=profile.night
                    ),
                    dtype=float,
                )
            )
            cache[key] = cached
        return cached

    return np.array([row(student.routine) for student in students])[:, None, :]


class InterestMatrix(Mapping[tuple[str, int], dict[str, float]]):
    """O interesse sorteado, guardado como o array que o sorteio produz.

    Lê-se como o dicionário que sempre foi — `matriz[(aluno, período)]` devolve
    a linha sobre a grade —, mas o que está guardado é o **array**, e a linha é
    montada na hora.

    É a diferença entre caber e não caber na memória. São alunos × períodos ×
    turmas valores, e em dicionários aninhados cada float custa ~47 bytes
    contra os 8 do array: no cenário cheio (2.592 × 23 × 288) são 767 MB
    contra 131 MB, de longe o maior item de `Draws`. Montar uma linha custa
    ~10 µs, 0,14% de uma simulação — o array troca memória por um custo de
    CPU que não se mede.

    O eixo do período é 0-based, porque array é 0-based; a chave segue 1-based,
    como o resto do motor. A conversão é a mesma que estava na saída de
    `draw_interest` e continua acontecendo num lugar só.

    **A linha é construída a cada acesso**, então duas leituras da mesma chave
    dão dicionários iguais e distintos. Escrever num deles não altera a
    matriz — o que é a regra de `Draws` de todo modo: nada ali muda depois do
    sorteio.
    """

    __slots__ = ("_values", "_columns", "_row_of_student")

    def __init__(
        self,
        values: np.ndarray,
        columns: tuple[str, ...],
        row_of_student: dict[str, int],
    ) -> None:
        self._values = values
        self._columns = columns
        self._row_of_student = row_of_student

    @property
    def periods(self) -> int:
        return int(self._values.shape[1])

    def __getitem__(self, key: tuple[str, int]) -> dict[str, float]:
        student_id, period = key
        row = self._row_of_student.get(student_id)
        if row is None or not 1 <= period <= self.periods:
            raise KeyError(key)
        return dict(zip(self._columns, self._values[row, period - 1].tolist()))

    def __iter__(self) -> Iterator[tuple[str, int]]:
        for student_id in self._row_of_student:
            for period in range(1, self.periods + 1):
                yield (student_id, period)

    def __len__(self) -> int:
        return len(self._row_of_student) * self.periods


def draw_interest(
    students: list["Student"], config: SimulationConfig, rng: np.random.Generator
) -> InterestMatrix:
    """Sorteia o interesse: uma linha por (aluno, período), sobre a grade.

    O interesse vem de uma **log-normal** de média logarítmica μ + A_x e
    desvio σ, repartida entre uma peça permanente e um ruído do semestre
    (`preference_split`). A log-normal é o que se obtém quando a grandeza é
    **produto** de muitos fatores independentes — e é assim que se forma o
    quanto alguém quer uma disciplina: interesse no tema vezes afinidade com a
    área vezes horário vezes dificuldade percebida. É uma afirmação sobre
    alunos, não sobre a ignorância de quem modela.

    σ é o único parâmetro de dispersão, e **grande concentra, pequeno
    achata**: o coeficiente de variação é √(e^{σ²} − 1), que cresce depressa,
    de modo que a faixa útil inteira cabe entre ~0,25 (aluno quase
    indiferente) e ~3 (quer uma disciplina e despreza o resto). E a moda do
    sorteio cru é e^{μ + A_x − σ²}, sempre positiva: não há limiar de σ a
    respeitar.

    **μ (`interest_mean`) é só escala.** Comum a todas as disciplinas, ele
    multiplica a linha inteira por e^μ, e a normalização desfaz o fator — nada
    abaixo daqui o vê. Existe para a prévia da interface desenhar a fonte numa
    escala que se lê.

    **O que sobra da média desse logaritmo é o peso do turno**
    (`_routine_log_weights`): o perfil de rotina do aluno multiplica o
    interesse das turmas diurnas ou das noturnas, conforme a vida que ele tem
    fora da grade. Ao contrário de μ, ele não se cancela na normalização —
    varia dentro da linha, e é exatamente isso que o faz redistribuir o
    interesse entre os turnos.

    A linha é sobre **turmas**, e o sorteio é composto em dois níveis: o valor
    da disciplina, comum às turmas dela, mais um desvio por turma, repartidos
    por `class_stability`. O desvio passa pela **mesma** repartição temporal da
    disciplina, senão estabilidade entre períodos igual a 1 deixaria a
    disciplina parada e a turma oscilando.

    A normalização vem depois e está em `equations.interest_row`: a linha
    inteira soma 1, e é sobre as **turmas** que ela soma. Quem converte isso
    no valor da disciplina é `equations.utility`, pela média das turmas
    dela.
    """
    groups = [d.name for d in config.disciplines]
    classes = config.classes_by_discipline()
    # Cada turma herda a coluna da disciplina dela; `spread` repete a coluna do
    # grupo tantas vezes quantas forem as turmas.
    columns = [name for group in groups for name in classes[group]]
    spread = np.array(
        [g for g, group in enumerate(groups) for _ in classes[group]], dtype=int
    )

    shape = (len(students), config.periods, len(groups))
    # O nível da disciplina, repartido no tempo pela estabilidade entre
    # períodos. `sigma=1` porque σ entra **uma vez só**, no nível de fora.
    level = preference_split(
        permanent=rng.normal(0.0, 1.0, size=(len(students), 1, len(groups))),
        seasonal=rng.normal(0.0, 1.0, size=shape),
        stability=_stability_by_discipline(config),
        sigma=1.0,
    )[:, :, spread]

    stability = config.class_stability
    if stability < 1.0:
        # O desvio da turma passa pela **mesma** repartição temporal, senão
        # estabilidade entre períodos igual a 1 deixaria a disciplina parada e
        # a turma oscilando. Com estabilidade entre turmas em 1 não há desvio
        # a sortear, e o gerador não é tocado: a simulação sem turmas fica bit
        # a bit igual à de antes de elas existirem.
        wide = (len(students), config.periods, len(columns))
        deviation = preference_split(
            permanent=rng.normal(0.0, 1.0, size=(len(students), 1, len(columns))),
            seasonal=rng.normal(0.0, 1.0, size=wide),
            stability=_stability_by_discipline(config)[:, :, spread],
            sigma=1.0,
        )
        level = np.sqrt(stability) * level + np.sqrt(1.0 - stability) * deviation

    shifts = config.shift_by_class()
    log = (
        config.interest_sigma * level
        + config.interest_mean
        + _routine_log_weights(students, [shifts[name] for name in columns])
    )
    normalized = normalize_rows(np.maximum(np.exp(log), UNDERFLOW_GUARD))
    return InterestMatrix(
        values=normalized,
        columns=tuple(columns),
        row_of_student={student.id: a for a, student in enumerate(students)},
    )


def interest_distribution(
    rows: InterestMatrix, bins: int = DISTRIBUTION_BINS
) -> list[float]:
    """O histograma do interesse — ver `equations.interest_histogram`."""
    return interest_histogram(rows.values(), bins)


def utility_matrix(
    *, interest: dict[str, float], student: "Student", config: SimulationConfig
) -> dict[str, float]:
    """ũ_{a,·}^(t): a utilidade do aluno no período — o interesse dele, visto
    pelo histórico.

    Determinística: mesmo interesse e mesmo estado do aluno, mesma saída.
    Devolve só as turmas das disciplinas do conjunto elegível
    (`equations.eligible_set`); as já aprovadas e as ainda bloqueadas têm
    utilidade zero por definição e não aparecem, e a elegível herda o
    interesse do que ela destrava um período à frente (`equations.utility`).

    A soma sobre as **disciplinas** — a melhor turma de cada uma — é 1, e é
    essa invariante que dispensa o denominador de ψ. Sobre as *turmas* a soma
    é maior, porque as irmãs somam junto e o aluno só pode levar uma.

    É o **único** ponto onde o interesse vira utilidade, e tudo o que decide —
    lance, pedido, reserva, ψ — lê daqui.

    A **ordem das chaves** é a da grade no cenário, e é carga: é dela que as
    duas mochilas tiram o desempate. Reordenar a saída muda resultado.
    """
    approved = student.approved(config.min_grade)
    return utility(
        interest=interest,
        eligible=config.eligible_disciplines(approved),
        successors=config.successors_by_discipline(),
        prerequisites=config.prerequisites_by_discipline(),
        classes=config.classes_by_discipline(),
    )


def decide(
    *,
    utilities: dict[str, float],
    behavior: Behavior = NEUTRAL,
    classes: dict[str, tuple[str, ...]] | None = None,
) -> tuple[dict[str, float], dict[str, float], float]:
    """A mensagem do aluno, antes de o mecanismo lê-la.

    Devolve **(utilidade por disciplina admitida, utilidade por turma,
    limiar)**.

    Os dois mecanismos chamam esta função, e é isso que garante que eles
    recebem a mesma mensagem — o que muda é só o que cada um faz com ela. O
    CR ordena; o leilão reparte crédito e para no limiar.

    **A mensagem é a própria utilidade.** Não há expoente a aplicar: o aluno
    lança proporcionalmente ao que quer, que é o ótimo da relaxação contínua
    da mochila côncava (`equations.concave_bids`). Distorcer de propósito foi
    um eixo de perfil até 16/11/2026, e saiu — concentrar crédito no que mais
    se quer passou a ser **premissa** do modelo, não tratamento.

    **A disciplina vale o da turma mais útil dela.** O aluno só pode levar
    uma, e leva a melhor que conseguir — então é esse valor que a seletividade
    corta e que a mochila de fora reparte. Cortar no nível da turma faria o
    número de turmas decidir o que ele pede.

    Dois passos, um por equação: `reserve_threshold` reparte a seletividade
    entre as disciplinas elegíveis, e `admitted_set` corta.
    """
    scores = {name: value for name, value in utilities.items() if value > 0.0}
    if classes:
        groups = {
            discipline: max(
                (scores[name] for name in names if name in scores), default=0.0
            )
            for discipline, names in classes.items()
        }
        groups = {name: value for name, value in groups.items() if value > 0.0}
    else:
        groups = scores
    # |M_a^(t)| é contado **antes** do corte: a reserva reparte a seletividade
    # entre o que o aluno podia cursar, não entre o que sobrou dela.
    reserve = reserve_threshold(
        selectivity=behavior.selectivity, eligible=len(groups)
    )
    return admitted_set(scores=groups, reserve=reserve), scores, reserve


def compute_bids(
    *,
    utilities: dict[str, float],
    available: list[str],
    budget: int,
    behavior: Behavior = NEUTRAL,
    classes: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, int]:
    """c_{a,·}^(t,r): a estratégia do aluno no leilão.

    `available` é B_a^(t,r) (eq. 15), por **turma**, e `budget` é C_a^(t,r).

    A MOCHILA É EM DOIS NÍVEIS
    ---------------------------

    A **mesma** mochila côncava (`equations.concave_bids`) duas vezes, uma
    dentro da outra. De fora, sobre as **disciplinas**, com `max_t ũ_t` como
    valor: quantos créditos cada uma merece. De dentro, uma vez por
    disciplina, sobre as **turmas** dela: como aqueles créditos se repartem
    entre as seções, com o score de cada turma como valor.

    O nível de fora é sobre disciplinas, e não sobre turmas, porque num nível
    só a mochila repartiria o orçamento entre disciplinas na proporção do
    **número de turmas** de cada uma — o ganho marginal `score/N` vale por
    bem, então o 1º crédito na turma B ganha do 2º na turma A sempre que
    `score_B > score_A/2`, o que entre turmas da mesma disciplina é quase
    sempre. O funil da oferta entraria no lance. Com dois níveis o quanto da
    disciplina é decidido antes de as turmas serem vistas, e o número delas
    não o toca.

    Dentro do grupo, o mesmo retorno decrescente reparte entre as turmas: o
    aluno aposta mais na que prefere e guarda uma aposta menor nas irmãs. Ele
    só pode **levar** uma (eq. 5), mas pode **pedir** em várias, e é esse
    hedge dentro da rodada que o nível de dentro expressa.

    O limiar da seletividade entra duas vezes, **as duas no nível de fora**:
    cortando o conjunto e parando o gasto. Dentro do grupo não há o que
    parar — os créditos daquela disciplina já foram decididos, e a repartição
    gasta exatamente eles (`reserve = 0`), de modo que a soma por grupo é a
    do nível de fora, crédito a crédito.
    """
    groups, scores, reserve = decide(
        utilities=utilities, behavior=behavior, classes=classes
    )
    if not classes:
        return concave_bids(
            scores=groups, available=available, budget=budget, reserve=reserve
        )

    reachable = set(available)
    open_classes = {
        discipline: [name for name in classes[discipline] if name in reachable]
        for discipline in groups
    }
    per_group = concave_bids(
        scores=groups,
        available=[d for d, names in open_classes.items() if names],
        budget=budget,
        reserve=reserve,
    )
    bids: dict[str, int] = {}
    for discipline, credits in per_group.items():
        # Sem limiar aqui: o corte foi feito no nível de fora, e o que esta
        # chamada recebe é uma fatia já aprovada que precisa sair inteira.
        bids.update(
            concave_bids(
                scores=scores, available=open_classes[discipline], budget=credits
            )
        )
    return bids
