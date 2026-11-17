"""Comparação entre os modelos de alocação (Seção 7.3).

O anteprojeto impõe duas condições metodológicas à comparação, e este módulo
existe para fazer as duas valerem de uma vez:

1. **Mesma inicialização dos dois lados.** "Sempre que os mecanismos forem
   comparados entre si, ambos serão inicializados com a mesma configuração de
   parâmetros iniciais, tais como alunos, cursos, períodos, disciplinas,
   utilidades, notas, entre outros." Como tudo isso é derivado da seed, basta
   rodar o mesmo cenário com a mesma seed nos dois mecanismos — é literalmente
   a mesma população, o mesmo interesse e a mesma matriz de notas
   encontrando regras de alocação diferentes.
2. **Múltiplas configurações de entrada.** "Serão testadas múltiplas
   configurações de entrada diferentes para cada comparação, e o resultado
   médio das simulações será avaliado." As seeds de 1 a N são essas
   configurações: N populações diferentes, cada uma vista pelos dois
   mecanismos.

Juntas, as duas isolam o nexo causal no mecanismo. Uma simulação só não diria
nada — a diferença poderia ser daquela população; e N simulações sem parear as
seeds mediriam a variação entre populações junto da variação entre mecanismos.

**São três braços** (`ARMS`): a ordenação por CR, o leilão igualitário e o
leilão acumulativo. Os dois leilões são o mesmo mecanismo — mesma moeda, mesmo
resolvedor, mesmo segundo preço — e diferem em **de onde vem o orçamento**: no
igualitário todo aluno abre todo período com `C_min`, e no acumulativo o saldo
atravessa o período e o retorno da eq. (34) o alimenta.

Com eles o vão se lê em duas parcelas em vez de uma: CR × igualitário diz o
que a **moeda** compra, igualitário × acumulativo diz o que o **acúmulo**
compra. Sobra um degrau fora dos três, em `ABLATION_ARMS`:

    CR  ──mensagem──▶  Bidding points  ──resolução──▶  Leilão igualitário
                                                   ──acúmulo──▶  Leilão acumulativo

1. **A mensagem.** O CR dá um número por *aluno*; o lance dá um número por
   *par* (aluno, disciplina). É a intensidade entrando no que o mecanismo
   recebe. Os dois lados resolvem ordinalmente, então o passo isola a moeda.
   Não é o mesmo algoritmo dos dois lados (`serial_dictatorship` contra
   `greedy_allocation`), e não poderia ser: um número por aluno não dá para
   ordenar pares. "Ordinal" descreve a **propriedade** — nenhum dos dois
   troca magnitudes —, não a implementação.
2. **A resolução.** Ordinal usa só a *ordem* dos lances: qualquer
   transformação monótona do vetor dá a mesma alocação. Cardinal (PLI) usa as
   *magnitudes*, e derruba um lance alto para acomodar dois médios, o que a
   varredura nunca faz. Os dois só divergem onde a carga horária aperta — sem
   ela o problema se separa por disciplina e a varredura é ótima —, então o
   passo só tem conteúdo em cenário com conjunto elegível maior que W_a.
3. **O acúmulo.** A eq. (36) carrega o saldo de um período para o outro e o
   `f_γ` da eq. (34) o alimenta: quem aprova recupera a fatia do preço
   correspondente à nota, de modo que ir bem compra poder de compra no período
   seguinte. É a única fonte de mérito do leilão — a ordenação por CR faz isso
   por construção, o histórico *é* o critério, e o leilão igualitário não faz
   de jeito nenhum.

**Memória e retorno são um canal só, não dois.** O braço igualitário fixa os
dois (`credit_memory="none"` e `k = 0`), e os dois campos dizem a mesma coisa:
medido, `carry` com `k = 0` sai **idêntico** a `none` — relatório por
relatório, em todas as seeds —, porque o orçamento abre em `C_min` (eq. 37) e,
sem retorno, só pode cair; o piso o traz de volta. Não há sobra a carregar
enquanto não houver retorno que erga o saldo acima do piso. Fixar os dois é,
então, redundância deliberada: o braço fica dizendo o que é em vez de depender
dessa prova.

**Por que o acúmulo virou braço e não ablação.** A sobra é a eq. (36), dada
pelo anteprojeto; a forma do retorno a Seção 7.3.2 deixa explicitamente em
aberto, como eixo de experimentação. Ligá-lo é decisão de quem escreve, e o
passo 3 é onde ela se paga — cara demais para ficar fora do padrão.

Por isso o acúmulo e o resolvedor **não são do cenário aqui**: são eixos do
experimento. O resolvedor que vier na configuração é ignorado, como a seed; o
multiplicador do retorno vale onde o braço não o fixa, e os demais o fixam em
0 — ver `Arm.multiplier_over`.

**Uma simulação vira um número por métrica**, que é a linha das tabelas. Para as
três métricas de período a redução é a média **ponderada pelos alunos medidos**:
a simulação termina numa fase de drenagem, em que a população só diminui, e uma
média simples daria a um período final de vinte alunos o mesmo peso de um
período cheio de trezentos. Ponderar pela população corrige isso sem recortar o
horizonte à mão.

O peso são os alunos **medidos** (`metrics.students`), não os ativos: o calouro
conta como gente e não como dado (ver `simulation.GroupSnapshot`), e o primeiro
período, em que todo mundo acabou de ingressar, simplesmente não entra na média.

**As quatro métricas.** Satisfação (psi-barra), equidade (phi) e correlação
(lambda) são de período e passam pela média ponderada. O **tempo de formatura**
não é: é propriedade da simulação inteira, a média de quantos períodos cada
concluinte levou do ingresso ao diploma.

Ficaram de fora, e por motivos diferentes. Nada de **crédito**: orçamento, preço
e retorno não existem do lado da linha de base, e comparar um mecanismo com o
vazio não é comparação. A **ocupação** (theta) saiu porque, com o calouro fora do
recorte, ela deixou de se ler como "o quanto a universidade encheu" — as vagas
garantidas continuam ocupadas e não entram mais no numerador; quem quer essa
leitura a tem nos gráficos por disciplina. E a **semestralização** deu lugar ao
tempo de formatura, que mede a mesma coisa — progressão na grade — num número
que se lê direto, em períodos.

**O tempo de formatura tem viés de seleção, e por isso não anda sozinho.** A
média só existe sobre quem concluiu: um mecanismo que forma menos gente pode
exibir um tempo *menor* só porque sobraram os rápidos. Daí `graduates` vir junto
no resumo — a média não se lê sem ele.

**A saturação** sai de `allocations_per_round`: as vagas obtidas por aluno em
cada rodada, uma média por rodada em vez de uma só para o período. O que se lê
é o **decaimento** entre elas. Um mecanismo que atende mais demanda cedo começa
alto e cai rápido; um que leva a disputa adiante distribui as vagas pelas
rodadas. É o perfil, não o nível, que responde "satura mais rápido?" — e o
nível, somado, é a mesma `allocations_per_student` do período.

Conta-se o que foi ganho **naquela rodada**, não o acumulado: `RoundReport` traz
o `won_now`, não o `won`. E, como o calouro está fora do recorte, a matrícula
garantida não infla a primeira rodada — o número é só o que o mecanismo alocou.
"""
from __future__ import annotations

import dataclasses
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .behavior import draw_interest
from .equations import (
    DAY,
    RequestStates,
    grade_for_attempt,
    grade_histogram,
    interest_histogram,
    request_funnel,
    weighted_mean,
)
from .equations import time_to_graduate as mean_span
from .grading import GradeShapes, draw_base_quantiles
from .config import (
    CreditMemory,
    Mechanism,
    Resolver,
    SimulationConfig,
)
from .metrics import Metrics
from .population import generate_students
from .simulation import (
    CELL_SEP,
    DisciplineSnapshot,
    GroupSnapshot,
    SimulationResult,
    run_simulation,
)

# Teto de simulações por braço. Não é limitação técnica: é que a faixa para de
# ganhar informação muito antes disso, e cada simulação a mais custa uma
# simulação inteira em cada braço.
MAX_RUNS = 100

# Quantas simulações correm ao mesmo tempo. Quatro não é o número de núcleos:
# é quanta memória cabe. No cenário cheio (63 disciplinas, 288 turmas, 2592
# alunos, 23 períodos) cada worker pede **dois** picos ao mesmo tempo — 738 MB
# do processo Python e 526 MB do `cbc.exe` que ele está esperando —, e como as
# simulações são o mesmo trabalho começado junto, elas picam juntas. A conta é
# a memória **livre** dividida por uns 1,3 GB, não o número de núcleos: acima
# disso o lote pagina e deixa de terminar, que foi o que motivou isto tudo.
# (Medido em 14/11/2026. Era o dobro antes de o estágio 2 sair do
# `wdp_solver` e de `behavior.InterestMatrix` guardar o interesse como array.)
DEFAULT_WORKERS = min(4, os.cpu_count() or 1)

# Chamado a cada simulação concluída: (braço, seed).
RunDone = Callable[["Arm", int], None]


@dataclass(frozen=True)
class Arm:
    """Um dos modelos comparados.

    Um modelo é a combinação de quatro escolhas: a **moeda** (ordenação por CR
    ou lance em créditos), o **resolvedor** (varredura gulosa ou PLI global),
    a **memória do orçamento** (se a sobra atravessa o período) e o
    **retorno de créditos**. As duas últimas andam juntas: desligar uma torna
    a outra inerte, e por isso o braço igualitário desliga as duas.

    `return_multiplier` é o k da eq. (34) que o braço impõe ao cenário; `None`
    quer dizer "o do cenário", e é como o braço que **acumula** não fixa
    quanto. Zero desliga o retorno, e é assim que um braço fica sem acúmulo
    sem deixar de ser o mesmo modelo — ver `multiplier_over`.

    `key` é o identificador estável que a interface usa para rotular a série —
    o rótulo em si é dela, não daqui.
    """

    key: str
    mechanism: Mechanism
    return_multiplier: float | None
    resolver: Resolver = "ilp"
    credit_memory: CreditMemory = "carry"

    def multiplier_over(self, config: SimulationConfig) -> float:
        """O k que este braço roda sobre este cenário."""
        if self.return_multiplier is None:
            return config.return_multiplier
        return self.return_multiplier


# Os braços na ordem do caminho — é também a ordem do eixo, da legenda e das
# cores, e nela a correlação (eq. 57) se lê de uma vez: do mecanismo em que o
# CR é o próprio critério ao que o ignora por completo.
#
# **Só entra aqui o que sai nos resultados**: cada braço é um traçado dos
# gráficos e uma linha das tabelas, e nada roda para não ser mostrado. Uma
# célula que já foi braço saiu por não ser passo do caminho — o CR resolvido
# por PLI, que tem defeito declarado: como todo pedido do aluno tem o mesmo
# peso N_a, a PLI é indiferente sobre qual cortar, e o aluno não tem voz sobre
# o que perde. Ela segue alcançável por `SimulationConfig` (`resolver="ilp"`
# com `mechanism="ranking"`) se um dia for precisa para um apêndice.
#
# A chave `credits_ilp` é **histórica**: nasceu nomeando o resolvedor, quando
# o braço existia para isolá-lo da varredura. Hoje ela nomeia o leilão
# igualitário, e o resolvedor dele é o mesmo do acumulativo. O nome ficou
# porque a chave é identificador estável — comparação gravada antes disto
# continua casando com o braço.
#
# **Os dois não usam o mesmo resolvedor, e isso é deliberado.** O CR roda por
# ditadura serial, que desempata por ε; o leilão roda por PLI, que não lê o ε
# (ver `wdp_solver`) e deixa a escolha entre ótimos de mesmo valor para a
# busca do CBC. Igualar os resolvedores custaria a maximização de bem-estar,
# que é o que a PLI entrega e o guloso não — preferiu-se a assimetria a isso.
ARMS: tuple[Arm, ...] = (
    Arm("ranking_greedy", "ranking", 0.0, resolver="greedy"),
    Arm("credits_ilp", "credits", 0.0, resolver="ilp", credit_memory="none"),
    Arm("credits_return", "credits", None),
)

# O degrau que sobrou do caminho, e que **não** roda por padrão.
#
# Entre o CR e o leilão igualitário há duas mudanças de uma vez — a mensagem
# (um número por aluno vira um por par) e a resolução (ordinal vira cardinal)
# —, e este braço as separa: ele tem a mensagem do leilão e a resolução do CR.
# Fica fora do padrão porque o trabalho compara três modelos e a escada
# inteira não cabe no texto; fica aqui porque custa tempo de execução e não
# complexidade conceitual — é a mesma simulação com um campo trocado. Para a
# ablação, `run_comparison(..., arms=ARMS + ABLATION_ARMS)`.
#
# `credits_greedy` é o *bidding points* clássico — orçamento de pontos, lances
# por disciplina, disciplina fechando no menor lance atendido (Sönmez & Ünver
# 2010, sobre Michigan e Yale SOM). Não confundir com o **Course Match** de
# Wharton, que substituiu o bidding points de lá: aquele é cardinal e resolve
# por MIP, mas é outro mecanismo — preferências sobre *cestas*, orçamentos
# aproximadamente iguais e preços de equilíbrio, não lance pago a segundo
# preço. É trabalho relacionado, não célula deste desenho.
ABLATION_ARMS: tuple[Arm, ...] = (
    Arm("credits_greedy", "credits", 0.0, resolver="greedy", credit_memory="none"),
)


# Os braços por chave — como a interface se refere a um deles ao pedir o traço
# de uma simulação. Inclui a ablação: o traço de um braço que não rodou por
# padrão continua reproduzível.
ARM_BY_KEY: dict[str, Arm] = {arm.key: arm for arm in ARMS + ABLATION_ARMS}


def arms_from_keys(keys: list[str]) -> tuple[Arm, ...]:
    """Os braços que essas chaves nomeiam, na ordem canônica de `ARM_BY_KEY`.

    A ordem em que as chaves chegam é ignorada de propósito: a tela acha o
    braço pela chave, e fixar a ordem aqui faz o resumo sair idêntico seja
    qual for a ordem do pedido. Chave repetida entra uma vez só.

    Existe porque rodar **um** braço é o caso comum enquanto se mexe no
    cenário: a comparação custa uma simulação completa por braço e por seed, e
    quem está calibrando a grade não precisa do outro lado a cada tentativa.
    O que sai daqui serve direto em `run_comparison(..., arms=...)` — a
    resposta traz menos braços, e a tela desenha o que veio.
    """
    wanted = set(keys)
    unknown = sorted(wanted - ARM_BY_KEY.keys())
    if unknown:
        raise ValueError(f"braço desconhecido: {', '.join(unknown)}")
    chosen = tuple(arm for key, arm in ARM_BY_KEY.items() if key in wanted)
    if not chosen:
        raise ValueError("escolha ao menos um braço para comparar")
    return chosen


@dataclass(frozen=True)
class RulerSeries:
    """As métricas de uma simulação ao longo de **uma régua**, sem reduzir.

    A régua é o eixo X (`RULERS`): o período da simulação, a idade do aluno ou
    a coorte dele. `x[i]` é o ponto da régua a que a posição `i` se refere, e
    para a régua do período ele é o número do período — o caso em que esta
    classe nasceu, e a razão de todo o resto dela falar em período.

    É o mesmo material de que `summarize` tira a média ponderada — a diferença
    é que aqui ele não vira um número. A média esconde que o horizonte tem três
    trechos: o **aquecimento**, com a universidade enchendo; o **estado
    estacionário**; e a **drenagem**, depois do último ingresso, em que a
    população só diminui. De um vão entre mecanismos a pergunta seguinte é em
    qual dos três ele mora — um leilão que só ganha do CR na drenagem disse
    algo sobre a drenagem, não sobre o mecanismo.

    As listas são **paralelas** e trazem só os pontos **medidos**: `x[i]` é o
    ponto da régua a que `efficiency[i]` se refere, e posição nenhuma é nula. O
    primeiro período não aparece — nele todo mundo acabou de ingressar e não há
    o que medir (ver `summarize`) —, e por isso o ponto da régua vem explícito
    em vez de sair do índice.

    `students` é o peso daquele ponto na redução. Ele cai à vista na drenagem, e
    é o que torna a ponderação verificável em vez de confiável: quem lê o
    gráfico vê o período final de vinte alunos que a média ponderada se recusou
    a tratar como um período cheio.

    A saturação também está aqui, e com uma dimensão a mais: ela já é uma série
    por rodada, e por período vira uma matriz. Lê-se uma rodada de cada vez —
    como a tela faz, um gráfico por rodada —, e aí cada uma é outra série sobre
    o mesmo eixo.

    O tempo de formatura não está aqui, e não por recorte de escopo: é
    propriedade da simulação inteira. A versão por período — quanto levou quem
    concluiu em t — seria outra grandeza, com viés de sobrevivência, porque
    quem conclui cedo é rápido por construção.
    """

    x: list[int]
    # O peso de cada ponto, e o que cada régua conta nele: na do período, os
    # alunos medidos ali; na da idade, quantos alunos chegaram àquela idade
    # (cada um entra uma vez por idade); na da coorte, os aluno-períodos
    # medidos daquela turma. É a soma das células reagrupadas, e é ela que
    # mantém a identidade do recorte — ver `_regroup`.
    students: list[float]
    # A fração de concluintes **acumulada**: quem já concluiu até o fim do
    # período sobre quem já tinha ingressado. Sobe ao longo do horizonte, e no
    # último período é a fração final.
    graduation_rate: list[float]
    efficiency: list[float]
    utilization: list[float]
    # Quanto da grade o recorte já fechou — carga aprovada sobre a carga que
    # conclui. **Acumula**: é a única série aqui que olha o histórico inteiro
    # e não o período, e por isso sobe ao longo do horizonte em qualquer
    # mecanismo. O que se compara entre braços é a inclinação, não o nível.
    progress: list[float]
    fidelity: list[float]
    fairness: list[float]
    correlation: list[float]
    # N̄ — o CR médio do recorte. **Descreve, não pontua**: ele sobe tanto
    # quando o aluno vai melhor quanto quando o mecanismo o roteia para
    # turma mais fácil, e separar as duas coisas exige a dificuldade, que
    # está nos gráficos por disciplina.
    grade_average: list[float]
    # A fração das vagas obtidas que foi largada — ver `equations.exclusion_rate`.
    exclusion_rate: list[float]
    # --- a economia de créditos, só do leilão ----------------------------
    #
    # As três saem `None` na linha de base por CR, e não zeradas: ali não há
    # moeda, e zero se leria como "ninguém gastou". A redução entre seeds
    # devolve faixa vazia nessas posições, e a linha some do gráfico em vez
    # de virar um piso que ninguém pagou.
    credits_supply: list[float | None]  # C_a^(t,1) por aluno
    credits_spent: list[float | None]  # consumo da eq. (25) por aluno
    credits_returned: list[float | None]  # Σγ da eq. (34) por aluno
    # Os seis estados de solicitação, em média por aluno. É a série da seção
    # "Solicitações de disciplinas": uma linha por estado, não empilhada, cada
    # braço no seu painel.
    request_states: list[RequestStates]
    # A saturação do período, rodada a rodada: `allocations_per_round[i][r]` é o
    # que foi ganho por aluno na rodada r+1 do período `period[i]`. Uma linha
    # por período medido, sempre com |R| posições — `None` onde aquele período
    # não publicou a rodada, ou não teve o que medir nela.
    #
    # O peso desta série é o **mesmo** `students` acima, e isso não é
    # coincidência: o recorte de um período é o mesmo em todas as rodadas — a
    # rodada muda o que foi alocado, não quem é medido.
    allocations_per_round: list[list[float | None]]


@dataclass(frozen=True)
class GroupSeries:
    """A `RulerSeries` de um grupo de um recorte espacial — um perfil.

    O recorte **espacial** é quem a métrica corre; a régua é sobre o que ela
    corre. O recorte particiona a população, então os grupos de um mesmo eixo
    somam o agregado em cada ponto da régua.
    """

    group: str
    series: RulerSeries


# As **réguas** do eixo X, na ordem do seletor. Duas leituras diferentes do
# mesmo material, e é por isso que elas são escolha e não gráficos separados:
#
# - `period` é o calendário da universidade. É onde se veem as três fases do
#   horizonte — aquecimento, estado estacionário e drenagem —, e é a régua em
#   que cada ponto tem uma coorte diferente em cada idade.
# - `age` é o tempo do **aluno**: quantos períodos ele já completou. Alinha as
#   coortes pelo ingresso e tira a fase do horizonte de dentro da curva — o
#   que cai aqui cai na vida do aluno, não no calendário.
# - `cohort` é um corte transversal: um ponto por turma de ingresso, com a
#   vida inteira dela resumida. É onde se vê se entrar cedo ou tarde no
#   horizonte muda o que a pessoa recebeu.
RULERS: tuple[str, ...] = ("period", "age", "cohort")

# Os recortes **espaciais** da tela, na ordem do seletor: os quatro eixos de
# perfil (`simulation.Axis.profiles`). O agregado (`overall`) não está aqui
# porque não é recorte — é a ausência de um.
#
# A coorte saiu daqui em 11/11/2026 e virou régua: ela é um corte do **tempo**,
# e tê-la como cor obrigava a ler duas dimensões temporais no mesmo gráfico.
CUT_AXES: tuple[str, ...] = (
    "performance",
    "availability",
    "selectivity",
    "routine",
)


# Os recortes do gráfico de **preço**, e a única família de recortes que não
# reparte gente: o que se reparte aqui é a oferta. Por isso ela não entra em
# `CUT_AXES` — cruzá-la com as métricas por aluno não produziria leitura
# nenhuma, já que um aluno não pertence a "disciplina de 2 turmas".
CLASS_CUTS: tuple[str, ...] = (
    "classes",
    "hours",
    "difficulty",
    "shift",
    "curriculum_period",
)

# A optativa não tem período na grade — é elegível desde o ingresso —, então no
# recorte por período ela é um grupo à parte, no fim da ordem.
ELECTIVE_GROUP = "elective"


def _number_key(value: float) -> str:
    """O número como chave: sem zeros à direita e com ponto decimal, porque é
    chave de dado e não texto de tela."""
    return f"{value:g}"


def _class_group(snapshot: DisciplineSnapshot, axis: str) -> tuple[float, str]:
    """`(ordem, chave)` do grupo em que a turma cai, num recorte.

    A chave é **estável e sem idioma** — o rótulo em português é da interface,
    como em `COMPARISON_ARMS`. E os grupos saem dos valores que o cenário de
    fato usa, não de uma lista fixa: grade com duas cargas horárias produz
    duas linhas, com cinco produz cinco.
    """
    if axis == "classes":
        return (snapshot.classes, str(snapshot.classes))
    if axis == "hours":
        return (snapshot.hours, str(snapshot.hours))
    if axis == "difficulty":
        return (snapshot.difficulty, _number_key(snapshot.difficulty))
    if axis == "shift":
        # Diurno antes de noturno, que é a ordem da grade.
        return (0.0 if snapshot.shift == DAY else 1.0, snapshot.shift)
    if axis == "curriculum_period":
        if snapshot.elective:
            return (float("inf"), ELECTIVE_GROUP)
        return (snapshot.curriculum_period, str(snapshot.curriculum_period))
    raise ValueError(f"recorte de turma desconhecido: {axis!r}")


@dataclass(frozen=True)
class ClassPriceSeries:
    """O preço médio da turma num grupo de um recorte da oferta, por período."""

    axis: str
    group: str
    x: list[int]
    price: list[float]


@dataclass(frozen=True)
class GroupBands:
    """Um grupo de um recorte reduzido **entre as seeds**, ponto a ponto.

    Cada grandeza vira `(q1, mediana, q3)` em cada ponto da régua — o que o
    gráfico desenha como linha e faixa. A redução acontece aqui, e não na tela,
    porque a amostra inteira (seed × grupo × ponto) não cabe no histórico do
    navegador; a mediana e os quartis cabem, e não dependem de N.

    `n` é quantas seeds mediram o grupo naquele ponto. Na cauda do horizonte
    parte delas já esvaziou, e ali a amostra não é a mesma do começo do eixo.
    """

    group: str
    x: list[int]
    n: list[int]
    # Uma lista paralela a `x` por grandeza. `None` onde nenhuma seed mediu
    # aquela grandeza no ponto (uma rodada que não aconteceu).
    values: dict[str, list[tuple[float, float, float] | None]]


@dataclass(frozen=True)
class ClassPriceBands:
    """Um recorte da oferta, com os grupos dele reduzidos entre as seeds.

    Os grupos são `GroupBands` como os das demais séries — mesma forma, mesmo
    gráfico do outro lado —, com uma grandeza só: `mean_price`.
    """

    axis: str
    groups: list[GroupBands]


@dataclass(frozen=True)
class AxisBands:
    """Os grupos de um recorte sob uma régua, na ordem em que o cenário os
    declara.

    `ruler` é o eixo X (`RULERS`) e `axis` o recorte espacial (`CUT_AXES`),
    com `overall` para a universidade inteira, que tem um grupo só. As duas
    escolhas são independentes na tela, e é por isso que o braço traz as
    combinações todas em vez de uma série por recorte.
    """

    ruler: str
    axis: str
    groups: list[GroupBands]


@dataclass(frozen=True)
class RunSummary:
    """Uma simulação reduzida a um ponto por métrica.

    `periods` é quantos períodos a simulação de fato publicou — pode ser menor
    que |T| se a população se esvaziou antes do horizonte —, e serve para
    conferir que todos os braços viveram o mesmo intervalo. `graduates` é o
    contexto sem o qual `time_to_graduate` não se lê.
    """

    seed: int
    periods: int
    graduates: int  # quantos concluíram o curso — eq. (40)
    # Quantos foram **jubilados**: esgotaram os períodos de residência sem
    # fechar a grade. Com `graduates`, reparte `population` em três — saiu por
    # cima, saiu por baixo, e (só se o horizonte não esgotou) continua em curso.
    dismissed: int
    # Quantos ingressaram ao todo, que é o denominador das duas frações. Sem
    # ele os dois números acima são contagens sem escala: 40 formados é muito
    # ou pouco conforme a coorte tenha 60 ou 600 pessoas.
    population: int
    efficiency: float  # psi-barra — eq. (53)
    # Aproveitamento: a contraparte em carga do psi, que é em utilidade. As
    # duas se separam onde está a patologia que interessa — quem concentra o
    # lance, ganha a disciplina que amava e deixa o resto de W_a ocioso pontua
    # psi alto e aproveitamento baixo.
    utilization: float
    # Progresso na grade: carga aprovada sobre a carga que conclui, na média
    # ponderada dos períodos. Lê-se com `graduates` ao lado, pela mesma razão
    # do tempo de formatura — quem fecha a grade sai da medida, de modo que a
    # média dos que ficam para de subir na drenagem.
    progress: float
    # Fidelidade da mensagem: quanto da preferência sobrevive à tradução para
    # o que o mecanismo de fato recebe. **Descreve, não pontua** — como a
    # correlação, ela não ganha "seeds a favor": dizer qual lado é melhor
    # exigiria escolher entre expressar intensidade e ser simples de usar.
    fidelity: float
    fairness: float  # phi de Jain — eq. (55)
    correlation: float  # lambda — eq. (57)
    # N̄ — o CR médio, na mesma média ponderada das demais. Descreve, não
    # pontua: ver `RulerSeries.grade_average`.
    grade_average: float
    # Desperdício: a fração das vagas obtidas que foi largada antes de virar
    # aula. É a quinta métrica da comparação — e a que a disponibilidade
    # existe para produzir. Ver `equations.exclusion_rate`.
    exclusion_rate: float
    # Os seis estados em média por aluno, reduzidos a um ponto cada. A série
    # sem reduzir está em `by_period` e `by_group`.
    request_states: RequestStates
    # Períodos do ingresso ao diploma, na média dos concluintes. `None` quando
    # ninguém concluiu: a média não existe, e 0 ali se leria como "formou na
    # hora", que é o contrário do que aconteceu.
    time_to_graduate: float | None
    # Vagas obtidas por aluno **em cada rodada**, na ordem delas: o índice r-1 é
    # a rodada r. Tem |R| posições, iguais em todos os braços porque o cenário é
    # o mesmo. `None` numa posição significa que nenhum período teve o que medir
    # naquela rodada.
    allocations_per_round: list[float | None]
    # Segundos do alocador em cada (período, rodada) — ver `allocation_seconds`.
    # É a única série da comparação que **não** é do modelo: mede o custo de
    # rodar o mecanismo, não o que ele produz. Fora da igualdade
    # (`compare=False`) porque é tempo de parede: há teste que exige que duas
    # comparações da mesma configuração saiam idênticas, e elas saem — menos
    # no relógio.
    allocation_seconds: list[list[float]] = field(compare=False)
    # O preço médio por recorte da **oferta**, período a período. Vazio fora
    # do leilão: sem moeda não há preço a recortar.
    class_prices: list[ClassPriceSeries]
    # As mesmas métricas de período, período a período — o que a média ponderada
    # resume. É o recorte por período da tela; a redução continua sendo a dos
    # campos acima, e as duas leituras saem do mesmo material.
    by_period: RulerSeries
    # A mesma série por grupo, régua a régua: `by_group[régua][recorte]`, com
    # as réguas de `RULERS` e os recortes de `CUT_AXES` mais `overall`. É o
    # material das faixas do braço (`ArmResult.series`).
    by_group: dict[str, dict[str, list[GroupSeries]]]


@dataclass(frozen=True)
class ArmResult:
    """As N simulações de um braço, na ordem das seeds."""

    key: str
    mechanism: Mechanism
    # O k efetivamente rodado, já resolvido contra o cenário — e não o `None`
    # que o braço carrega. Quem lê um resultado quer saber o que rodou.
    return_multiplier: float
    runs: list[RunSummary]
    # As séries reduzidas entre as seeds: cada régua cruzada com cada recorte.
    # É o que os gráficos desenham — ver `bands`.
    series: list[AxisBands] = field(default_factory=list)
    # O tempo médio do alocador em cada (período, rodada), entre as seeds.
    # Fora da igualdade: é relógio, não resultado — ver `RunSummary`.
    allocation_seconds: list[list[float]] = field(default_factory=list, compare=False)
    # O preço reduzido entre as seeds, um recorte da oferta por entrada.
    class_prices: list[ClassPriceBands] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonResult:
    """As N simulações de cada braço, pareadas pela seed.

    Todas as listas têm o mesmo tamanho e a mesma ordem de seeds: o i-ésimo
    elemento de cada uma é a *mesma* população sob regras diferentes. Quem lê
    pode tanto tratar cada lista como uma amostra (é o que a faixa dos gráficos faz) quanto
    comparar par a par — e a comparação par a par é a que responde "o retorno
    mudou alguma coisa?", porque ali a população é literalmente a mesma.
    """

    runs: int
    arms: list[ArmResult]
    # As duas distribuições de entrada do cenário, para a tela mostrar de onde
    # vieram os números. Não variam entre braços nem entre seeds — são do
    # cenário, não da simulação.
    interest_distribution: list[float] = field(default_factory=list)
    grade_distribution: list[float] = field(default_factory=list)


def time_to_graduate(result: SimulationResult) -> float | None:
    """Períodos do ingresso ao diploma — ver `equations.time_to_graduate`."""
    return mean_span(
        s.graduated_at - s.entry_period + 1
        for s in result.students
        if s.graduated_at is not None
    )


def allocations_per_round(result: SimulationResult) -> list[float | None]:
    """Vagas obtidas por aluno em cada rodada, na ordem delas.

    Uma posição por rodada do cenário, e a mesma média ponderada pelos alunos
    medidos que as métricas de período usam. O valor é o que foi ganho *naquela*
    rodada — `RoundReport` traz o `won_now` —, de modo que a série decai: a
    primeira rodada pega o que estava livre, as seguintes o que sobrou.
    """
    rounds = max((len(period.rounds) for period in result.periods), default=0)
    series: list[float | None] = []
    for index in range(rounds):
        series.append(
            weighted_mean(
                [
                    (metrics.allocations_per_student, metrics.students)
                    for period in result.periods
                    if index < len(period.rounds)
                    for metrics in [period.rounds[index].overall.metrics]
                    if metrics is not None and metrics.students > 0
                ]
            )
        )
    return series


def allocation_seconds(result: SimulationResult) -> list[list[float]]:
    """Segundos do alocador em cada rodada, período a período.

    `série[p][r]` é a rodada r+1 do período p+1. É **tempo de parede**, não
    grandeza do modelo: muda de máquina para máquina e entre duas execuções da
    mesma seed, e nenhuma decisão da simulação o lê.

    Sem recorte por coorte ou perfil, e não por omissão: o resolvedor decide a
    rodada inteira de uma vez, então não existe parcela do tempo atribuível a
    um grupo de alunos.
    """
    return [
        [report.allocation_seconds for report in period.rounds]
        for period in result.periods
    ]


def mean_allocation_seconds(runs: list["RunSummary"]) -> list[list[float]]:
    """A média entre as seeds, posição a posição.

    Uma simulação pode publicar menos períodos que outra se a população se
    esvaziou antes do horizonte, então cada posição é a média **das seeds que
    chegaram até ela** — e não uma divisão por N que leria a ausência como
    zero segundos.
    """
    if not runs:
        return []
    periods = max(len(run.allocation_seconds) for run in runs)
    series: list[list[float]] = []
    for index in range(periods):
        rows = [run.allocation_seconds[index] for run in runs if index < len(run.allocation_seconds)]
        rounds = max((len(row) for row in rows), default=0)
        series.append(
            [
                sum(values) / len(values)
                for position in range(rounds)
                for values in [[row[position] for row in rows if position < len(row)]]
                if values
            ]
        )
    return series


def class_prices(result: SimulationResult) -> list[ClassPriceSeries]:
    """O preço médio da turma por recorte da oferta, período a período.

    A média é **simples entre as turmas** do grupo, e não ponderada pelas
    vagas: a pergunta é quanto custou a turma, não quanto pagou o aluno médio.
    Turma que não chegou ao mercado no período sai `mean_price = None` e não
    entra; grupo sem nenhuma turma com preço não publica o ponto.

    Fora do leilão não há preço, e a lista sai vazia — como as demais
    grandezas de crédito saem `None`.
    """
    out: list[ClassPriceSeries] = []
    for axis in CLASS_CUTS:
        points: dict[str, dict[int, list[float]]] = {}
        order: dict[str, float] = {}
        for period in result.periods:
            for snapshot in period.disciplines:
                if snapshot.mean_price is None:
                    continue
                rank, group = _class_group(snapshot, axis)
                order[group] = rank
                points.setdefault(group, {}).setdefault(period.period, []).append(
                    snapshot.mean_price
                )
        for group in sorted(points, key=lambda name: (order[name], name)):
            periods = sorted(points[group])
            out.append(
                ClassPriceSeries(
                    axis=axis,
                    group=group,
                    x=periods,
                    price=[
                        sum(points[group][point]) / len(points[group][point])
                        for point in periods
                    ],
                )
            )
    return out


def class_price_bands(runs: list[RunSummary]) -> list[ClassPriceBands]:
    """Os quartis do preço em cada ponto, grupo a grupo.

    É a mesma redução das demais séries e devolve a mesma forma (`GroupBands`),
    de modo que o gráfico do outro lado é o mesmo — muda o que a linha
    significa, não como ela se desenha.
    """
    out: list[ClassPriceBands] = []
    for axis in CLASS_CUTS:
        order: list[str] = []
        samples: dict[str, dict[int, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for run in runs:
            for entry in run.class_prices:
                if entry.axis != axis:
                    continue
                if entry.group not in order:
                    order.append(entry.group)
                for point, value in zip(entry.x, entry.price):
                    samples[entry.group][point].append(value)
        groups = [
            GroupBands(
                group=group,
                x=sorted(samples[group]),
                n=[len(samples[group][point]) for point in sorted(samples[group])],
                values={
                    "mean_price": [
                        _quartiles(samples[group][point])
                        for point in sorted(samples[group])
                    ]
                },
            )
            for group in order
        ]
        if groups:
            out.append(ClassPriceBands(axis=axis, groups=groups))
    return out


def weighted_states(pairs: list[tuple[Metrics, int]]) -> RequestStates:
    """A média ponderada dos seis estados, campo a campo.

    O peso é o mesmo das demais métricas — os alunos medidos —, de modo que um
    período final de vinte alunos não pesa como um período cheio. Instante sem
    os estados (uma rodada, onde a exclusão ainda não aconteceu) simplesmente
    não entra.
    """
    return _mean_states(
        [(m.request_states, w) for m, w in pairs if m.request_states is not None]
    )


def _mean_states(rows: list[tuple[RequestStates, float]]) -> RequestStates:
    """A média ponderada dos seis estados, campo a campo. Saco vazio dá tudo
    zero, e quem decide se publica é o chamador — como em `RequestStates`."""
    if not rows:
        return RequestStates(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def of(field_name: str) -> float:
        return weighted_mean([(getattr(r, field_name), w) for r, w in rows]) or 0.0

    return RequestStates(
        not_eligible=of("not_eligible"),
        not_requested=of("not_requested"),
        refused=of("refused"),
        excluded=of("excluded"),
        failed=of("failed"),
        approved=of("approved"),
    )


def _measured(snapshot: GroupSnapshot | None) -> bool:
    """O recorte tem métrica: alguém, além dos calouros, disputou o instante."""
    return (
        snapshot is not None
        and snapshot.metrics is not None
        and snapshot.metrics.students > 0
    )


def _period_series(
    instants: list[tuple[int, GroupSnapshot | None, list[GroupSnapshot | None]]],
    rounds: int,
) -> RulerSeries:
    """A série de um recorte ao longo dos períodos em que ele foi medido.

    `instants` traz, para cada período, o recorte no fim dele e o mesmo
    recorte em cada rodada. Só entram os períodos em que o recorte foi medido
    — nem os vazios, nem aquele em que todo o grupo acabou de ingressar.

    É a série da régua do período e, para as outras duas, a matéria-prima:
    `_regroup` reagrupa estas posições em idades ou coortes.
    """
    measured = [
        (period, snapshot, by_round)
        for period, snapshot, by_round in instants
        if _measured(snapshot)
    ]

    def series(of) -> list:
        return [of(snapshot.metrics) for _, snapshot, _ in measured]

    def snapshots(of) -> list:
        """As grandezas que ficam no recorte, e não em `Metrics` — as de
        crédito. Podem sair `None`, e saem na linha de base por CR."""
        return [of(snapshot) for _, snapshot, _ in measured]

    def saturation(by_round: list[GroupSnapshot | None]) -> list[float | None]:
        """Uma posição por rodada do cenário. Período que publicou menos
        rodadas é completado com `None`, para a coluna r ser a mesma rodada em
        todos os períodos."""
        row: list[float | None] = []
        for index in range(rounds):
            snapshot = by_round[index] if index < len(by_round) else None
            row.append(
                snapshot.metrics.allocations_per_student
                if _measured(snapshot)
                else None
            )
        return row

    return RulerSeries(
        x=[period for period, _, _ in measured],
        students=series(lambda m: float(m.students)),
        graduation_rate=[
            snapshot.graduated / snapshot.population if snapshot.population else 0.0
            for _, snapshot, _ in measured
        ],
        efficiency=series(lambda m: m.efficiency),
        utilization=series(lambda m: m.utilization),
        progress=series(lambda m: m.progress),
        fidelity=series(lambda m: m.fidelity),
        fairness=series(lambda m: m.fairness),
        correlation=series(lambda m: m.correlation),
        grade_average=series(lambda m: m.mean_grade_average),
        exclusion_rate=series(lambda m: m.exclusion_rate or 0.0),
        credits_supply=snapshots(lambda s: s.credits_per_student),
        credits_spent=snapshots(lambda s: s.mean_credits_spent),
        credits_returned=snapshots(lambda s: s.mean_credit_return),
        request_states=series(
            lambda m: m.request_states or RequestStates(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        ),
        allocations_per_round=[saturation(by_round) for _, _, by_round in measured],
    )


def _cut(report, axis: str) -> list[GroupSnapshot]:
    """Os grupos de um recorte espacial num instante."""
    return report.by_profile.get(axis, [])


def _cells(report, axis: str) -> list[GroupSnapshot]:
    """As células de um recorte espacial num instante — ver `Axis.crossed`.

    No agregado as células **são** as coortes: cruzar "a universidade inteira"
    com a coorte não dá nada além do recorte por coorte, que já vem pronto.
    """
    return report.by_cohort if axis == "overall" else report.by_cell.get(axis, [])


def _cell_key(axis: str, group: str) -> tuple[str, int]:
    """`(grupo espacial, coorte)` de uma célula.

    A coorte é sempre o último segmento, de modo que o nome de um perfil com o
    separador dentro não quebra a leitura.
    """
    if axis == "overall":
        return "overall", int(group)
    spatial, _, cohort = group.rpartition(CELL_SEP)
    return spatial, int(cohort)


# Uma célula num período: a coorte dela, o período, o recorte no fim dele e o
# mesmo recorte em cada rodada.
Instant = tuple[int, int, GroupSnapshot, list[GroupSnapshot | None]]


def _cell_instants(
    result: SimulationResult, axis: str
) -> tuple[list[str], dict[str, list[Instant]]]:
    """As células de um recorte, período a período.

    Devolve a ordem dos grupos espaciais — a de primeira aparição, que é a do
    cenário — e, por grupo, os instantes de todas as células dele, em ordem de
    período. É a matéria-prima das réguas de idade e de coorte.
    """
    order: list[str] = []
    out: dict[str, list[Instant]] = defaultdict(list)
    for period in result.periods:
        by_round = [
            {s.group: s for s in _cells(report, axis) if s.group is not None}
            for report in period.rounds
        ]
        for snapshot in _cells(period.aggregate, axis):
            if snapshot.group is None:
                continue
            group, cohort = _cell_key(axis, snapshot.group)
            if group not in order:
                order.append(group)
            out[group].append(
                (
                    cohort,
                    period.period,
                    snapshot,
                    [found.get(snapshot.group) for found in by_round],
                )
            )
    return order, out


def _regroup(
    instants: list[tuple[int, Instant]], *, ruler: str, rounds: int
) -> RulerSeries:
    """Reagrupa as células de um grupo numa série por ponto da régua.

    Cada item traz o ponto da régua em que a célula cai e o instante dela.
    Várias células caem no mesmo ponto — uma idade é alcançada por muitas
    coortes, uma coorte vive muitos períodos —, e é o saco de cada ponto que
    vira uma posição da série.

    A redução dentro do saco é a **média ponderada pelos alunos medidos**, a
    mesma de `summarize`: um período de vinte alunos não pesa como um cheio.
    Para as métricas por aluno — ψ, aproveitamento, fidelidade, desperdício,
    os seis estados, a saturação — a média ponderada das células **é** a média
    por aluno do conjunto. Para φ e λ não é: é a média dos índices de cada
    célula, a mesma aproximação que a redução por período já faz, e vale a
    mesma ressalva — eles descrevem o recorte, não se somam dele.

    `graduation_rate` é a exceção, porque é **acumulada**. Na régua da coorte o
    valor é o do último período em que a coorte foi medida, não a média da
    subida dela; na da idade a média é justamente o que se quer, porque ali
    cada coorte contribui com a situação em que estava naquela idade.
    """
    buckets: dict[int, list[Instant]] = defaultdict(list)
    for point, instant in sorted(instants, key=lambda item: item[1][1]):
        buckets[point].append(instant)
    points = sorted(buckets)
    bags = {
        point: _period_series(
            [(period, snapshot, by_round) for _, period, snapshot, by_round in bag],
            rounds,
        )
        for point, bag in buckets.items()
    }
    points = [point for point in points if bags[point].x]

    def weighed(point: int, of) -> float:
        bag = bags[point]
        return weighted_mean(list(zip(of(bag), bag.students))) or 0.0

    def optional(point: int, of) -> float | None:
        """A mesma média ponderada, para grandeza que pode não existir.

        Sem moeda no braço, toda posição é `None` e o reagrupamento devolve
        `None` — não 0, que se leria como "gastou zero".
        """
        bag = bags[point]
        pairs = [
            (value, weight)
            for value, weight in zip(of(bag), bag.students)
            if value is not None
        ]
        return weighted_mean(pairs) if pairs else None

    def graduation(point: int) -> float:
        bag = bags[point]
        if ruler != "cohort":
            return weighed(point, lambda s: s.graduation_rate)
        return bag.graduation_rate[-1]

    def states(point: int) -> RequestStates:
        bag = bags[point]
        return _mean_states(list(zip(bag.request_states, bag.students)))

    def saturation(point: int) -> list[float | None]:
        bag = bags[point]
        row: list[float | None] = []
        for index in range(rounds):
            pairs = [
                (values[index], weight)
                for values, weight in zip(bag.allocations_per_round, bag.students)
                if index < len(values) and values[index] is not None
            ]
            row.append(weighted_mean(pairs) if pairs else None)
        return row

    return RulerSeries(
        x=points,
        # A **soma** das contagens do saco, e é ela que torna o reagrupamento
        # exato: o peso de um ponto é o de todas as células que caíram nele, de
        # modo que os grupos de um recorte continuam repartindo o agregado.
        #
        # E ela se lê, em cada régua: na da idade é quanta gente chegou àquela
        # idade (cada aluno entra uma vez por idade); na da coorte, quantos
        # aluno-períodos daquela turma foram medidos.
        students=[sum(bags[point].students) for point in points],
        graduation_rate=[graduation(point) for point in points],
        efficiency=[weighed(point, lambda s: s.efficiency) for point in points],
        utilization=[weighed(point, lambda s: s.utilization) for point in points],
        progress=[weighed(point, lambda s: s.progress) for point in points],
        fidelity=[weighed(point, lambda s: s.fidelity) for point in points],
        fairness=[weighed(point, lambda s: s.fairness) for point in points],
        correlation=[weighed(point, lambda s: s.correlation) for point in points],
        grade_average=[weighed(point, lambda s: s.grade_average) for point in points],
        exclusion_rate=[weighed(point, lambda s: s.exclusion_rate) for point in points],
        credits_supply=[optional(point, lambda s: s.credits_supply) for point in points],
        credits_spent=[optional(point, lambda s: s.credits_spent) for point in points],
        credits_returned=[
            optional(point, lambda s: s.credits_returned) for point in points
        ],
        request_states=[states(point) for point in points],
        allocations_per_round=[saturation(point) for point in points],
    )


def group_series(
    result: SimulationResult, *, by_period: RulerSeries
) -> dict[str, dict[str, list[GroupSeries]]]:
    """As séries de cada grupo de cada recorte, régua a régua —
    `by_group[régua][recorte]`.

    A régua do período sai dos recortes prontos de cada instante, e é exata. As
    de idade e de coorte saem das células (`_cell_instants`) reagrupadas por
    `_regroup`, e é esse cruzamento que permite escolher régua e recorte
    independentemente.

    A ordem dos grupos é a de primeira aparição, que é a do cenário.
    """
    rounds = max((len(period.rounds) for period in result.periods), default=0)
    out: dict[str, dict[str, list[GroupSeries]]] = {ruler: {} for ruler in RULERS}
    out["period"]["overall"] = [GroupSeries(group="overall", series=by_period)]

    for axis in CUT_AXES:
        order: list[str] = []
        for period in result.periods:
            for snapshot in _cut(period.aggregate, axis):
                if snapshot.group is not None and snapshot.group not in order:
                    order.append(snapshot.group)

        def find(report, group: str, axis: str = axis) -> GroupSnapshot | None:
            return next((s for s in _cut(report, axis) if s.group == group), None)

        out["period"][axis] = [
            GroupSeries(
                group=group,
                series=_period_series(
                    [
                        (
                            period.period,
                            find(period.aggregate, group),
                            [find(report, group) for report in period.rounds],
                        )
                        for period in result.periods
                    ],
                    rounds,
                ),
            )
            for group in order
        ]

    for axis in ("overall", *CUT_AXES):
        order, instants = _cell_instants(result, axis)
        for ruler in ("age", "cohort"):
            out[ruler][axis] = [
                GroupSeries(
                    group=group,
                    series=_regroup(
                        [
                            (
                                cohort if ruler == "cohort" else period - cohort,
                                instant,
                            )
                            for instant in instants[group]
                            for cohort, period, _, _ in [instant]
                        ],
                        ruler=ruler,
                        rounds=rounds,
                    ),
                )
                for group in order
            ]
    return out


# As grandezas de uma faixa, na ordem em que a tela as lê. As seis de estado
# levam o nome do estado; as quatro frações do funil, o nome do nó; as de
# saturação, `round_<r>`.
STATE_KEYS: tuple[str, ...] = (
    "not_eligible",
    "not_requested",
    "refused",
    "excluded",
    "failed",
    "approved",
)

# As quatro frações condicionais de `equations.request_funnel`. São elas que a
# tela desenha; as seis contagens acima continuam na resposta porque são o
# material de que estas saem, e porque um nó vazio só se explica olhando-as.
FUNNEL_KEYS: tuple[str, ...] = (
    "requested_share",
    "granted_share",
    "attended_share",
    "approved_share",
)


def _quantities(series: RulerSeries, index: int) -> dict[str, float | None]:
    """O que uma posição de uma série mede, grandeza a grandeza.

    As frações do funil saem **daqui**, e não de dividir as faixas na tela: a
    razão das medianas não é a mediana das razões, e o que se quer é a fração
    de cada simulação, reduzida depois como qualquer outra grandeza.
    """
    states = series.request_states[index]
    values: dict[str, float | None] = {
        "students": float(series.students[index]),
        "graduation_rate": series.graduation_rate[index],
        "efficiency": series.efficiency[index],
        "utilization": series.utilization[index],
        "progress": series.progress[index],
        "fidelity": series.fidelity[index],
        "fairness": series.fairness[index],
        "correlation": series.correlation[index],
        "grade_average": series.grade_average[index],
        "exclusion_rate": series.exclusion_rate[index],
        "credits_supply": series.credits_supply[index],
        "credits_spent": series.credits_spent[index],
        "credits_returned": series.credits_returned[index],
    }
    for key in STATE_KEYS:
        values[key] = getattr(states, key)
    funnel = request_funnel(states)
    for key in FUNNEL_KEYS:
        values[key] = getattr(funnel, key)
    for r, value in enumerate(series.allocations_per_round[index], start=1):
        values[f"round_{r}"] = value
    return values


def _quartiles(values: list[float]) -> tuple[float, float, float]:
    """`(q1, mediana, q3)` por interpolação linear — o método 7, o mesmo do
    `quantile` da interface e o padrão do numpy.

    Quatro casas: a tela mostra no máximo três, e a resposta inteira vai para
    o histórico do navegador, onde cada casa a mais custa espaço."""
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    return (round(float(q1), 4), round(float(median), 4), round(float(q3), 4))


def _group_bands(group: str, samples: list[RulerSeries]) -> GroupBands:
    """Reduz as séries de um grupo, uma por seed, a quartis por ponto da
    régua."""
    by_point: dict[int, list[dict[str, float | None]]] = defaultdict(list)
    for series in samples:
        for index, point in enumerate(series.x):
            by_point[point].append(_quantities(series, index))
    points = sorted(by_point)
    keys: list[str] = []
    for point in points:
        for row in by_point[point]:
            keys.extend(k for k in row if k not in keys)

    def band(point: int, key: str) -> tuple[float, float, float] | None:
        values = [row[key] for row in by_point[point] if row.get(key) is not None]
        return _quartiles(values) if values else None

    return GroupBands(
        group=group,
        x=points,
        n=[len(by_point[point]) for point in points],
        values={key: [band(point, key) for point in points] for key in keys},
    )


def bands(runs: list[RunSummary]) -> list[AxisBands]:
    """As séries de um braço reduzidas entre as seeds, régua por recorte.

    Sai uma entrada por combinação: as réguas de `RULERS` cruzadas com
    `overall` e os recortes de `CUT_AXES`. Um grupo que falte numa seed entra
    com as seeds que o têm.
    """
    out: list[AxisBands] = []
    for ruler in RULERS:
        for axis in ("overall", *CUT_AXES):
            order: list[str] = []
            samples: dict[str, list[RulerSeries]] = defaultdict(list)
            for run in runs:
                for entry in run.by_group.get(ruler, {}).get(axis, []):
                    if entry.group not in order:
                        order.append(entry.group)
                    samples[entry.group].append(entry.series)
            out.append(
                AxisBands(
                    ruler=ruler,
                    axis=axis,
                    groups=[_group_bands(group, samples[group]) for group in order],
                )
            )
    return out


def summarize(result: SimulationResult, *, seed: int) -> RunSummary:
    """Reduz uma simulação inteira a um ponto por métrica.

    As três de período passam pela média ponderada pelos alunos medidos; o tempo
    de formatura é da simulação inteira; a saturação é uma média dessas por
    rodada. O ponto não substitui o material de que saiu: `by_period` leva as
    mesmas métricas sem reduzir, e as duas leituras ficam conferíveis uma contra
    a outra. `by_group` leva a mesma série por grupo de cada recorte.

    Períodos sem métrica não entram — nem os vazios, nem aquele em que todo
    mundo acabou de ingressar. Um zero ali seria um período em que ninguém ficou
    satisfeito, que é coisa diferente de um período que não se mede.
    """
    graduates = sum(1 for s in result.students if s.graduated_at is not None)
    dismissed = sum(1 for s in result.students if s.dismissed_at is not None)
    rounds = max((len(period.rounds) for period in result.periods), default=0)
    by_period = _period_series(
        [
            (
                period.period,
                period.aggregate.overall,
                [report.overall for report in period.rounds],
            )
            for period in result.periods
        ],
        rounds,
    )
    weights = by_period.students

    def mean(values: list[float]) -> float:
        return weighted_mean(list(zip(values, weights))) or 0.0

    states = [
        (metrics, metrics.students)
        for period in result.periods
        for metrics in [period.aggregate.overall.metrics]
        if _measured(period.aggregate.overall)
    ]

    return RunSummary(
        seed=seed,
        periods=len(result.periods),
        graduates=graduates,
        dismissed=dismissed,
        population=len(result.students),
        efficiency=mean(by_period.efficiency),
        utilization=mean(by_period.utilization),
        progress=mean(by_period.progress),
        fidelity=mean(by_period.fidelity),
        fairness=mean(by_period.fairness),
        correlation=mean(by_period.correlation),
        grade_average=mean(by_period.grade_average),
        exclusion_rate=mean(by_period.exclusion_rate),
        request_states=weighted_states(states),
        time_to_graduate=time_to_graduate(result),
        allocations_per_round=allocations_per_round(result),
        allocation_seconds=allocation_seconds(result),
        class_prices=class_prices(result),
        by_period=by_period,
        by_group=group_series(result, by_period=by_period),
    )


# A seed da amostra dos histogramas. É a **primeira da comparação**, e não a do
# cenário: numa comparação a seed do cenário é ignorada (ela vira o eixo da
# amostra), e usar `config.seed` faria dois cenários idênticos a menos da seed
# devolverem resultados diferentes — justamente o que a comparação promete que
# não acontece. Com 1, o histograma descreve literalmente a primeira população
# que a comparação rodou.
SAMPLE_SEED = 1


def sample_interest_distribution(config: SimulationConfig) -> list[float]:
    """O histograma de interesse do cenário, sorteado à parte da simulação.

    Descreve a **entrada**, não o resultado: a mesma distribuição que a
    simulação usa, numa amostra própria. Vem daqui, e não de uma simulação,
    porque numa comparação há 3N matrizes, todas da mesma distribuição, sem uma
    que seja "a" certa. (Na execução única, ao contrário, o histograma sai da
    matriz que a simulação de fato usou.)
    """
    students = generate_students(config, np.random.default_rng(SAMPLE_SEED))
    rows = draw_interest(students, config, np.random.default_rng(SAMPLE_SEED))
    return interest_histogram(rows.values())


def sample_grade_distribution(config: SimulationConfig) -> list[float]:
    """O histograma de notas de primeira tentativa, pelo mesmo motivo e do mesmo
    jeito que `sample_interest_distribution`.

    A nota mostrada é a de **primeira tentativa em disciplina de dificuldade
    1**, que é a situação que os três parâmetros do perfil descrevem. É o
    retrato da população que o cenário declara, antes de a grade entrar.
    """
    students = generate_students(config, np.random.default_rng(SAMPLE_SEED))
    quantiles = draw_base_quantiles(
        students, config.disciplines, config, np.random.default_rng(SAMPLE_SEED)
    )
    shapes = GradeShapes()
    by_id = {student.id: student for student in students}

    def grade(student_id: str, quantile: float) -> float:
        mode, left_sd, right_sd = shapes.of(by_id[student_id].performance, 1.0, 1)
        return grade_for_attempt(
            quantile=quantile, mode=mode, left_sd=left_sd, right_sd=right_sd
        )

    grades = [
        grade(student_id, quantile)
        for (student_id, _), quantile in quantiles.items()
    ]
    return grade_histogram(grades)


def arm_config(config: SimulationConfig, *, arm: Arm, seed: int) -> SimulationConfig:
    """O cenário como um braço o roda: as quatro escolhas do braço e a seed.

    É o **único** lugar em que um braço vira configuração, e é o que torna o
    traço de uma simulação conferível: a tela individual pede a mesma
    `(braço, seed)` que a comparação resumiu e recebe a simulação idêntica, porque
    a configuração passa por aqui dos dois lados.
    """
    return dataclasses.replace(
        config,
        mechanism=arm.mechanism,
        return_multiplier=arm.multiplier_over(config),
        resolver=arm.resolver,
        credit_memory=arm.credit_memory,
        seed=seed,
    )


def _run_one(config: SimulationConfig, arm: Arm, seed: int) -> RunSummary:
    # Sem histórico: nada do que `summarize` lê sai dele, e guardá-lo custa
    # 1,1 GB por simulação — ver `run_simulation`.
    return summarize(
        run_simulation(arm_config(config, arm=arm, seed=seed), keep_histories=False),
        seed=seed,
    )


def _run_arms(
    config: SimulationConfig,
    *,
    arms: tuple[Arm, ...],
    seeds: list[int],
    workers: int,
    on_run_done: RunDone | None,
) -> list[list[RunSummary]]:
    """As `len(arms) × len(seeds)` simulações, na ordem em que foram pedidas.

    Com `workers <= 1` roda em linha, sem executor nenhum: é o modo de
    depurar, porque o traceback de uma simulação que falha chega inteiro e no
    lugar certo.
    """
    if workers <= 1:
        done: list[list[RunSummary]] = []
        for arm in arms:
            summaries: list[RunSummary] = []
            for seed in seeds:
                summaries.append(_run_one(config, arm, seed))
                if on_run_done is not None:
                    on_run_done(arm, seed)
            done.append(summaries)
        return done

    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = [
            [pool.submit(_run_one, config, arm, seed) for seed in seeds] for arm in arms
        ]
        if on_run_done is not None:
            where = {
                job: (arm, seed)
                for arm, arm_jobs in zip(arms, jobs)
                for seed, job in zip(seeds, arm_jobs)
            }
            for job in as_completed(where):
                on_run_done(*where[job])
        return [[job.result() for job in arm_jobs] for arm_jobs in jobs]


def run_comparison(
    config: SimulationConfig,
    *,
    runs: int,
    workers: int = DEFAULT_WORKERS,
    arms: tuple[Arm, ...] = ARMS,
    on_run_done: RunDone | None = None,
) -> ComparisonResult:
    """Roda `runs` simulações em cada braço, com as seeds de 1 a `runs`.

    `arms` é o conjunto comparado, e o padrão são os dois do trabalho. Para a
    ablação que separa mensagem, resolução e retorno, passe
    `arms=ARMS + ABLATION_ARMS` — custa uma simulação a mais por braço e por
    seed, e nada mais.

    Dois campos do cenário recebido são ignorados de propósito. A **seed**,
    porque numa comparação ela deixa de ser parâmetro e passa a ser o eixo da
    amostra. E o **resolvedor**, porque é eixo do experimento: os braços o
    impõem. O **multiplicador do retorno** vale, mas só onde o braço não o
    fixa. O resto — disciplinas, população, horizonte, rodadas — vale igual em
    todos, que é o que torna a diferença atribuível ao modelo.

    As simulações saem em paralelo por `ProcessPoolExecutor`. O tempo do
    leilão está quase todo dentro do CBC, que já roda como processo externo e
    devolve a GIL — mas o que sobra (sortear, pontuar, fechar o período,
    resumir) é Python puro, e em threads ele serializaria: no cenário cheio
    são uns 40 s por simulação, que em 40 simulações viram meia hora de espera
    que não se paraleliza. Processos também isolam o pico de memória de cada
    simulação, que o coletor de um processo só não devolve ao sistema entre
    uma e outra.

    O preço é que `config` e cada `RunSummary` vão e voltam serializados, e
    que uma simulação que falhe chega como `BrokenProcessPool` em vez do erro
    verdadeiro — para esse caso existe `workers=1`, que roda em linha.

    `on_run_done` é chamado a cada simulação concluída, para quem roda isto
    num terminal e quer ver progresso. Em paralelo ele chega **fora de
    ordem**, que é a ordem em que as simulações de fato terminaram.

    A ordem das seeds é preservada no resultado, de modo que o i-ésimo
    elemento de cada lista é a mesma população.
    """
    if not 1 <= runs <= MAX_RUNS:
        raise ValueError(f"o número de simulações deve estar entre 1 e {MAX_RUNS}")
    seeds = list(range(1, runs + 1))
    jobs = _run_arms(
        config, arms=arms, seeds=seeds, workers=workers, on_run_done=on_run_done
    )
    return ComparisonResult(
        runs=runs,
        interest_distribution=sample_interest_distribution(config),
        grade_distribution=sample_grade_distribution(config),
        arms=[
            ArmResult(
                key=arm.key,
                mechanism=arm.mechanism,
                return_multiplier=arm.multiplier_over(config),
                runs=summaries,
                series=bands(summaries),
                allocation_seconds=mean_allocation_seconds(summaries),
                class_prices=class_price_bands(summaries),
            )
            for arm, summaries in zip(arms, jobs)
        ],
    )
