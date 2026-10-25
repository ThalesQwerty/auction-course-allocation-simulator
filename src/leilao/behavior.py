"""Comportamento dos alunos: utilidades percebidas e lances (Seção 7.2.4).

A matriz de utilidades é **parâmetro de entrada**, como as notas: todo o sorteio
acontece na inicialização, a partir da `seed`, para todos os alunos e todos os
períodos de uma vez (`draw_utilities`). Em tempo de execução, `utility_matrix`
só recorta o que já foi sorteado, e os lances saem deterministicamente das
utilidades — nenhuma aleatoriedade dentro do loop, como exige a Seção 7.3.

Isso importa para comparar cenários: se a utilidade fosse sorteada dentro do
loop, mexer numa vaga deslocaria o fluxo do gerador e mudaria as preferências
dos alunos, e a diferença entre dois cenários deixaria de ser atribuível ao
mecanismo.

**Uma linha por (aluno, período).** O gosto do aluno é sorteado de novo a cada
período letivo: o que ele quis no semestre passado não determina o que quer
neste. Sobre essa linha agem os **zeros** da eq. (42) — a disciplina já aprovada
ou ainda bloqueada por pré-requisito sai do conjunto elegível. Cada linha já vem
normalizada para somar 1 sobre a grade inteira, e o recorte não a renormaliza: a
soma sobre o elegível é o U_a^(t) da eq. (43), que portanto fica abaixo de 1
sempre que algo estiver fora do alcance do aluno.

O resorteio por período é o que separa este modelo do de uma preferência fixa:
com a matriz única, perder uma vaga disputada condenava o aluno a querer a mesma
disciplina com a mesma intensidade até consegui-la; agora a disputa recomeça com
preferências novas, e a fila por uma disciplina muito concorrida se desfaz sozinha
em vez de se acumular.

Isso não afeta alocação nenhuma, e vale saber por quê: as duas mochilas do
aluno comparam só **razões** entre utilidades, e a satisfação da eq. (51) divide
pela soma do elegível. Multiplicar a linha inteira por uma constante não muda
lance, pedido nem psi. O U_a existe como leitura — quanto do que o aluno quer
está ao alcance dele agora —, não como alavanca.

Sobre poupar: não há. A eq. (42) prevê um U_a que é a fração do que o aluno tem
em mãos que ele se dispõe a comprometer, mas nem crédito nem carga horária
passam de um período para o outro, então guardar não é estratégia, é perda — o
aluno gasta todo o orçamento no leilão e pede até o W_a cheio na linha de base.

**Não há perfis de aluno.** Até 08/10/2026 a linha era distorcida por um
expoente de afinidade, que concentrava ou diluía a preferência conforme o perfil.
Isso saiu: todos os alunos sorteiam da mesma normal, e a diferença entre duas
linhas é só a sorte. O que o expoente fazia — concentrar ou diluir a preferência
— agora é a **forma k** da Gamma, e vale igual para todo mundo.

ORDEM DE DESEMPATE
------------------

Quando duas disciplinas valem o mesmo para um aluno, ganha a **listada
primeiro** no cenário — `SimulationConfig.disciplines`, que é a ordem em que a
interface as mostra e em que foram acrescentadas. É uma ordem **global**: a
mesma para todos os alunos, todos os períodos e todas as rodadas, e vale nas
duas decisões que o aluno toma sozinho — a mochila côncava daqui e a mochila 0-1
da linha de base (`ranking.request_set`).

A ordem se propaga sem ninguém carregá-la de propósito: `config.eligible_disciplines`
varre `self.disciplines`, `utility_matrix` constrói o dicionário nessa varredura
e dicionário em Python preserva a ordem de inserção. Por isso as duas mochilas
leem o posto a partir de `utilities`, nunca de `available` — este é só um filtro,
e pode chegar em qualquer ordem.

Com utilidade sorteada o empate tem probabilidade zero, então a regra quase
nunca é acionada de fato. Ela existe para que um cenário escrito à mão (uma
grade simétrica, um teste) não dependa da ordem de iteração para dar sempre o
mesmo resultado — a mesma exigência de determinismo da Seção 7.3 que mantém os
sorteios fora do loop. Note que ela é **do aluno**: o desempate do leilão entre
alunos continua sendo alpha/epsilon (eq. 20, `tie_breaking`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import heapq

import numpy as np

from .config import SimulationConfig
if TYPE_CHECKING:  # pragma: no cover - só para a anotação
    # `population` importa `Behavior` daqui, então a dependência só pode
    # existir em tempo de verificação de tipo — senão fecha ciclo no import.
    from .population import Student

# Guarda contra underflow, **não** parâmetro de modelagem. A log-normal só
# chega a 0,0 com expoente abaixo de -745, o que não acontece em sigma nenhum
# que faça sentido — ela é insurance, não mecanismo (a Gamma que havia antes
# precisava dela de verdade, e por isso a faixa de k utilizável era limitada).
#
# Existe porque utilidade zero é o que marca o **inelegível**, e as duas
# mochilas filtram por `utilidade > 0`: um zero aqui tiraria a disciplina do
# conjunto de escolha e o aluno nunca a cursaria, nem quando fosse a única
# disponível.
UNDERFLOW_GUARD = float(np.finfo(float).tiny)

# Faixas do histograma de utilidades (`utility_distribution`). Dez, as mesmas
# das notas: sobre [0, 1] as divisas caem em 0, 0,1, 0,2 ... 1, que se lê de
# relance. Com nove elas cairiam em 0,11, 0,22, 0,33 — números sem significado,
# e mais largos de imprimir num eixo apertado.
DISTRIBUTION_BINS = 10


@dataclass(frozen=True)
class Behavior:
    """O comportamento de um aluno: como ele traduz utilidade em mensagem.

    **É função, não matriz.** A utilidade é resorteada a cada período, então um
    genoma com um valor por par (aluno, disciplina) descreveria o que fazer com
    a linha deste semestre e não diria nada sobre a do próximo. Comportamento
    tem de ser uma regra que funcione sobre uma linha que ela nunca viu.

    São três coeficientes, e os dois primeiros são o dilema que atravessa o
    trabalho:

    - **`concentration`** — o viés de satisfação: o quanto o aluno exagera
      as diferenças de gosto ao apostar. Um é apostar as intensidades
      relativas verdadeiras; acima de 1 concentra, perto de 0 achata até a mensagem
      virar um conjunto, que é exatamente o que a linha de base por CR envia.
      É, portanto, a **razão de distorção**, medida em unidades do desvio
      da preferência.
    - **`progress`** — o viés de progresso: o peso do *avanço esperado* da
      vaga, que é uma grandeza só — `P(obter) · P(aprovar) · (quanto avanço se
      passar)`. Um coeficiente sobre ela é melhor que quatro sobre as partes, e
      como as partes ficam dentro do mesmo produto elas podem se correlacionar
      sem criar crista entre genes.
    - **`reserve`** — a utilidade de reserva: o aluno compra crédito
      enquanto o ganho marginal exceder `r`. Numa regra só ela decide *quais*
      disciplinas entram (as de ganho acima de r), *quantos* créditos cada uma
      recebe e *quanto* se gasta no total — o orçamento vira teto, não meta.

    Os valores neutros reproduzem o modelo sem comportamento, bit a bit: a
    concentração em 1 deixa o score igual à utilidade, o progresso em 0 apaga
    aquele termo, e a reserva em 0 nunca para a compra. **É assim que a população roda hoje** —
    a evolução desses coeficientes é experimento à parte.
    """

    concentration: float = 1.0
    progress: float = 0.0
    reserve: float = 0.0


NEUTRAL = Behavior()


@dataclass(frozen=True)
class Signals:
    """O que a universidade publicou no período anterior, por disciplina.

    É todo o conjunto de informação do aluno, e ele é deliberadamente pobre:
    nada de conhecer a dificuldade declarada nem a própria aptidão por matéria.
    O que existe é o que um aluno real lê — a concorrência e a taxa de
    aprovação do semestre passado — mais o próprio histórico.

    `win` é P̂(obter): vagas ÷ solicitantes no leilão, ou a comparação do CR do
    aluno com a nota de corte na linha de base. `pass_rate` é P̂(aprovar): a
    taxa publicada da disciplina, que é a dificuldade já filtrada pela
    população. **Sem histórico (1º período) os dois valem 1**, e o termo de
    progresso cai no neutro sozinho.

    Um efeito colateral que é bom: o sinal é enviesado de forma diferente em
    cada mecanismo. No CR a disciplina escassa é cursada por quem tem CR alto,
    então ela *parece* mais fácil do que é.
    """

    win: dict[str, float] = field(default_factory=dict)
    pass_rate: dict[str, float] = field(default_factory=dict)
    hours: dict[str, int] = field(default_factory=dict)
    reach: dict[str, int] = field(default_factory=dict)


def decision_scores(
    *,
    utilities: dict[str, float],
    behavior: Behavior = NEUTRAL,
    signals: Signals | None = None,
    catalogue: int = 0,
) -> dict[str, float]:
    """O score que o aluno usa para decidir, em cima da linha de utilidades:

        ln score_x = β·ln u_rel_x + ρ·ln[ P̂(obter)·P̂(aprovar)·w_x·(1+d_x) ]

    `u_rel` é a utilidade em múltiplos da indiferença (`u · |disciplinas|`), a
    mesma normalização da fórmula de nota: ela vale 1 quando o aluno é
    indiferente, e sobrevive ao catálogo crescer.

    Com os valores neutros o score **é** `u_rel`, que é
    proporcional à utilidade — então a mochila côncava decide exatamente o que
    decidia antes, e a ordem de desempate da grade é preservada porque a
    iteração segue a ordem de `utilities`.
    """
    scale = catalogue or len(utilities) or 1
    out: dict[str, float] = {}
    for name, utility in utilities.items():
        if utility <= 0.0:
            continue
        value = (utility * scale) ** behavior.concentration
        if behavior.progress and signals is not None:
            advance = (
                signals.win.get(name, 1.0)
                * signals.pass_rate.get(name, 1.0)
                * max(signals.hours.get(name, 1), 1)
                * (1 + signals.reach.get(name, 0))
            )
            value *= max(advance, UNDERFLOW_GUARD) ** behavior.progress
        out[name] = value
    return out


def draw_utilities(
    students: list["Student"], config: SimulationConfig, rng: np.random.Generator
) -> dict[tuple[str, int], dict[str, float]]:
    """Sorteia a matriz de utilidades inteira na inicialização, a partir da
    seed: uma linha por (aluno, período), sobre a grade inteira.

    Três passos (eqs. 41-43 + invariante de altura):

    1. **Valor preliminar** de cada par (aluno, disciplina), tirado de uma
       **log-normal** de média logarítmica 0 e desvio `utility_sigma`. Contínuo,
       portanto distinto dos demais com probabilidade 1, e sempre positivo.
    2. **Deslocamento por altura** s_x: `raw' = raw + M·s_x`, com
       `M = (max − min) + ε` na linha. Garante s_x > s_y ⇒ u_x > u_y; dentro
       da mesma altura a ordem do sorteio permanece. O sigma manda *dentro* da
       camada; entre camadas a ordem é curricular.
    3. **Divisão pelo somatório da linha**, que faz a grade inteira valer 1.
       A normalização preserva as desigualdades estritas entre positivos.

    A log-normal é o que se obtém quando a grandeza é **produto** de muitos
    fatores independentes — e é assim que se forma o quanto alguém quer uma
    disciplina: interesse no tema vezes afinidade com a área vezes horário vezes
    dificuldade percebida. É uma afirmação sobre alunos, e não sobre a ignorância
    de quem modela.

    `sigma` é o único parâmetro, e **grande concentra, pequeno achata**:

    - o coeficiente de variação é `sqrt(exp(sigma^2) - 1)`, que cresce depressa,
      de modo que a faixa útil inteira cabe entre ~0,25 (aluno quase indiferente)
      e ~3 (aluno que quer uma disciplina e despreza o resto);
    - a média do logaritmo não é configurável porque some: deslocá-la multiplica
      a linha inteira por uma constante, e a constante morre na normalização;
    - a moda do sorteio cru é `exp(-sigma^2)`, **sempre positiva** — não há
      limiar de sigma a respeitar para que a utilidade mais provável de uma
      disciplina não seja zero.

    A normalização **não é necessária** para o mecanismo: as duas mochilas do
    aluno comparam só razões entre utilidades e psi divide pela soma do
    elegível, de modo que a simulação sai idêntica com ou sem ela. Ela fica
    porque é o que mantém o número legível no relatório (0,11 é "11% do que o
    aluno quer"; 1,94 não é nada) e o U_a^(t) da eq. (43) com significado.
    """
    names = [d.name for d in config.disciplines]
    shape = (len(students), config.periods, len(names))
    # A preferência se reparte em duas peças: uma **permanente** por par
    # (aluno, disciplina), sorteada uma vez, e um **ruído do semestre**,
    # sorteado a cada período. A estabilidade diz quanto da variância fica na
    # primeira.
    #
    # Os pesos são raiz(s) e raiz(1 - s), e não s e 1 - s, porque as duas
    # peças são independentes: o que se soma são as variâncias, não as
    # amplitudes. Com os pesos "intuitivos" a dispersão vazaria a cada período
    # (0,58 do original em s = 0,5), e a estabilidade viraria um segundo botão
    # de sigma — confundida justamente com o parâmetro de que ela precisa ser
    # independente. Assim, cada período continua tendo exatamente a dispersão
    # de sigma, e o que s controla é só a correlação entre semestres, que vale
    # literalmente s.
    #
    # A estabilidade é por disciplina quando o cenário a declara: é a
    # sincronia entre concorrentes que trava a fila, não a persistência em si.
    stability = np.array(
        [
            config.utility_stability if d.stability is None else d.stability
            for d in config.disciplines
        ],
        dtype=float,
    ).reshape(1, 1, -1)
    permanent = rng.normal(0.0, 1.0, size=(len(students), 1, len(names)))
    seasonal = rng.normal(0.0, 1.0, size=shape)
    log = config.utility_sigma * (
        np.sqrt(stability) * permanent + np.sqrt(1.0 - stability) * seasonal
    )
    raw = np.maximum(np.exp(log), UNDERFLOW_GUARD)
    # Invariante s_x > s_y ⇒ u_x > u_y: desloca cada camada acima da amplitude
    # da linha. ε = 1 garante desigualdade estrita no empate max−min.
    heights = config.heights()
    height = np.array([heights[name] for name in names], dtype=float)
    row_max = raw.max(axis=2, keepdims=True)
    row_min = raw.min(axis=2, keepdims=True)
    shifted = raw + (row_max - row_min + 1.0) * height.reshape(1, 1, -1)
    normalized = shifted / shifted.sum(axis=2, keepdims=True)

    return {
        (student.id, period + 1): {
            name: float(normalized[a, period, j]) for j, name in enumerate(names)
        }
        for a, student in enumerate(students)
        for period in range(config.periods)
    }


def utility_distribution(
    rows: dict[tuple[str, int], dict[str, float]],
    bins: int = DISTRIBUTION_BINS,
) -> list[float]:
    """Como a utilidade se reparte dentro da linha de um aluno, em `bins` faixas.

    Cada linha (aluno, período) é reescalada ao **próprio** [mínimo, máximo] e
    dividida em faixas de mesma largura; a saída é a fração de utilidades que
    cai em cada faixa, somando 1. Utilidade zero não entra — ela marca o
    inelegível, não uma preferência fraca.

    **A escala é por linha, e não global, porque global degenera.** Com a faixa
    tomada do menor ao maior valor da matriz inteira, um único extremo define o
    intervalo e, de sigma = 1 em diante, 94% dos valores caem na primeira faixa:
    todos os gráficos saem iguais e nenhum descreve um aluno. Por linha, a
    leitura é "como *um* aluno reparte a preferência dele", que é a grandeza que
    sigma controla — e aí a forma muda visivelmente ao longo da varredura.

    A última faixa guarda sempre o máximo da linha, então ela nunca é vazia: num
    conjunto de n disciplinas ela vale pelo menos 1/n.
    """
    totals = [0.0] * bins
    counted = 0
    for row in rows.values():
        values = [value for value in row.values() if value > 0]
        if len(values) < 2:
            continue
        low, high = min(values), max(values)
        span = high - low
        for value in values:
            # Faixa de mesma largura; o máximo cai na última por convenção, e
            # não numa faixa a mais.
            index = bins - 1 if span <= 0 else min(bins - 1, int((value - low) / span * bins))
            totals[index] += 1
        counted += len(values)
    if not counted:
        return [0.0] * bins
    return [total / counted for total in totals]


def utility_matrix(
    *, row: dict[str, float], student: "Student", config: SimulationConfig
) -> dict[str, float]:
    """u_{a,·}^(t): o recorte elegível da linha do aluno — eqs. (41)-(43).

    Função determinística: mesma linha e mesmo estado do aluno, mesma saída.
    Devolve apenas as disciplinas de utilidade positiva — o conjunto elegível da
    eq. (42), que aqui é "não aprovada e com os pré-requisitos cumpridos". As já
    aprovadas e as ainda bloqueadas valem zero por construção (Seção 7.2.4) e
    simplesmente não aparecem.

    **Os valores não são renormalizados.** São os mesmos da linha sorteada, e a
    soma deles é o U_a^(t) da eq. (43) — menor que 1 sempre que algo estiver
    fora do alcance do aluno, e igual a 1 só na situação-limite em que a grade
    inteira lhe é elegível. Isso não muda alocação nenhuma: ver a nota sobre
    razões no topo do módulo.

    Sem grupos de grade: como toda disciplina é obrigatória, a hierarquia
    obrigatórias > optativas > livres das eqs. (47)-(48) não tem o que ordenar.
    Quem ordena a grade é o pré-requisito, que diz *quando* a disciplina entra no
    conjunto, não quanto ela vale dentro dele.

    A **ordem das chaves** do dicionário devolvido é a da grade no cenário, e é
    carga: é dela que as duas mochilas tiram o desempate (ver `ORDEM DE
    DESEMPATE`, no topo do módulo). Reordenar a saída muda resultado.
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
    """Converte utilidades em lances inteiros numa rodada — a estratégia do
    aluno no leilão.

    `available` é B_a^(t,r) (disciplinas em que ainda é possível obter vaga) e
    `budget` é C_a^(t,r), o saldo de créditos no início da rodada.

    O aluno resolve **em casa** um Problema da Mochila côncava: a capacidade é o
    orçamento, cada crédito pesa 1, e o valor de investir o N-ésimo crédito numa
    disciplina é `u_{a,x} / N`. É a lei da utilidade marginal decrescente — o
    primeiro crédito numa disciplina é o que mais compra chance de vaga, e cada
    um depois dele compra menos. O valor total de c créditos postos em x é,
    portanto, `u_{a,x}` vezes o c-ésimo número harmônico.

    Isso **substitui as eqs. (44)-(46)** do anteprojeto, que repartiam o
    orçamento proporcionalmente à utilidade, truncavam e distribuíam a sobra em
    ordem de preferência. O lance proporcional é o ótimo da relaxação contínua
    desta mochila — maximizar a soma de u_x·ln(c_x) com a soma dos c_x fixa dá
    c_x proporcional a u_x —, de modo que a mochila é a versão inteira e exata
    do mesmo critério, e resolve sozinha o arredondamento que as eqs. (45)-(46)
    tratavam à parte.

    Como todos os pesos são 1 e o ganho marginal cai dentro de cada disciplina,
    **o guloso é ótimo**: basta tomar os `budget` maiores ganhos marginais, que é
    o que a fila de prioridade abaixo faz. Não há tabela de programação dinâmica
    a montar, como há na mochila 0-1 da linha de base (`ranking.request_set`).

    O aluno gasta **todo** o saldo: todo crédito a mais tem ganho marginal
    positivo, e crédito não gasto não é carregado para o período seguinte.
    Guardar para a rodada seguinte também não se sustenta — lance perdedor não
    consome crédito nenhum, então apostar não custa nada.

    A alocação depende só das **razões** entre utilidades, como as eqs. (44)-(46)
    dependiam: multiplicar a matriz inteira por uma constante não muda lance
    nenhum.

    **Empate vai para a disciplina listada primeiro** — a ordem de `utilities`,
    que é a ordem da grade no cenário (ver `ORDEM DE DESEMPATE` no módulo).
    `available` pode chegar em qualquer ordem: quem decide é a matriz.
    """
    wanted = set(available)
    scores = decision_scores(
        utilities=utilities,
        behavior=behavior,
        signals=signals,
        catalogue=catalogue,
    )
    # Iterar `utilities`, e não `available`, é o que ancora o desempate na ordem
    # da grade: a posição no `pool` passa a ser a posição no cenário, restrita
    # ao que ainda está em disputa.
    pool = [name for name in utilities if name in wanted and scores.get(name, 0.0) > 0.0]
    if not pool or budget <= 0:
        return {}

    # Fronteira: o ganho do *próximo* crédito de cada disciplina. Negativo
    # porque `heapq` é min-heap; o posto entra como segundo campo e resolve
    # qualquer empate, inclusive o de ganhos marginais que coincidem vindos de
    # utilidades diferentes (u_x/2 = u_y/1, por exemplo). Como o posto é único,
    # a comparação nunca chega aos dois últimos campos.
    rank = {name: index for index, name in enumerate(pool)}
    frontier = [(-scores[name], rank[name], name, 1) for name in pool]
    heapq.heapify(frontier)

    bids: dict[str, int] = {}
    for _ in range(budget):
        gain, _, name, position = heapq.heappop(frontier)
        # A **utilidade de reserva**: o aluno compra enquanto o ganho marginal
        # exceder `r`, e para quando não. Numa regra só isso decide quais
        # disciplinas entram (as de ganho acima de r, no 1º crédito), quantos
        # créditos cada uma recebe e quanto se gasta no total — o orçamento
        # vira teto, e não meta. Com reserva 0 (o neutro) ela nunca dispara, e o
        # aluno gasta tudo como antes.
        if -gain <= behavior.reserve:
            break
        bids[name] = bids.get(name, 0) + 1
        following = position + 1
        heapq.heappush(
            frontier, (-scores[name] / following, rank[name], name, following)
        )

    # Toda disciplina presente recebeu ao menos um crédito, então a eq. (18) —
    # lance nulo não é demanda — já vale por construção.
    return bids
