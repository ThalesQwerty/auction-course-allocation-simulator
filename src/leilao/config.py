"""Configuração de um cenário de simulação (Seção 7.2 do anteprojeto).

O usuário descreve o cenário em dois blocos — parâmetros gerais e disciplinas —
e a simulação deriva o resto (alunos, nomes, interesse, notas)
aleatoriamente a partir da `seed`.

**A população é descrita por três distribuições, não por grupos.** O
desempenho governa a normal dividida da nota, e portanto a frequência com que
o aluno reprova; a disponibilidade governa a log-normal da carga, e portanto a
frequência com que ele exclui; a seletividade é a opção externa dele, e entra
na decisão de pedir e de gastar.

Cada eixo tem um **nível basilar** (`*_stability`): a fração da variância que é
permanente do aluno, contra a que é resorteada por período ou por disciplina.
É isso que faz "este aluno é bom", "este aluno tem pouco tempo" e "este aluno
é exigente" significarem alguma coisa — e é sobre o nível basilar que os
relatórios cortam os **quantis**.

Houve **perfis** nomeados em cada eixo até 19/11/2026, com a coorte derivada do
produto das combinações. Os quantis os substituíram: eles saem de um valor
contínuo e não há grupo a declarar. O que se digita é o ingresso **por turma de
entrada** (`students_per_entry_class`), e a coorte sai dele.

Não há cursos: todo aluno é da universidade e cursa a mesma grade. A
obrigatória tem de ser aprovada uma a uma; a **optativa** (`elective`) conta só
pela carga, e concluir exige somar `elective_hours` entre as aprovadas — é essa
substituibilidade que dá ao aluno o que escolher. O que ordena a
grade são os **sucessores** (`unlocks`): cada disciplina declara quais outras
ela desbloqueia. A **altura** s_x sai por indução nessa DAG — 0 se não
desbloqueia nada, senão 1 + max das alturas dos sucessores — e substitui a
senioridade da eq. (38) na invariante de preferência. O **período da grade**
(matrícula garantida, gráficos) continua contado a partir do ingresso, sobre a
aresta inversa: quem ninguém desbloqueia é 1º período.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from .equations import (
    Behavior,
    availability_shape,
    class_schedules,
    curriculum_heights,
    curriculum_periods,
    curriculum_reach,
    eligible_set,
    inverse_edges,
    rotated_index,
    grade_shape,
    schedule_cliques,
    schedule_names,
    transitive_closure,
)

# Fecho transitivo da grade: `seq` e `req` de `equations.utility`.
#
# Memoizado porque a utilidade é recalculada por (aluno, período) e o fecho
# não depende de nenhum dos dois — é propriedade só da grade. A chave é a
# lista de arestas declarada, que é hashável e identifica a grade inteira.
#
# `req` sai de **inverter o fecho**, e não de um segundo fecho sobre as
# arestas opostas: é a inversão exata que sustenta `Σ U = 1`. Ver
# `equations.curriculum_closure`.
@lru_cache(maxsize=16)
def _curriculum_closures(
    edges: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    forward = transitive_closure(dict(edges))
    return forward, inverse_edges(forward)

# Mecanismo de alocação. `credits` é o leilão por créditos proposto (Seção 7.1),
# em que o aluno reparte um orçamento entre lances e um PLI decide a alocação.
# `ranking` é a linha de base tradicional (Seção 7.3.1, eqs. 49-50): não há
# leilão nem PLI — as solicitações são atendidas em ordem decrescente do CR do
# aluno, e a carga horária faz o papel do orçamento.
Mechanism = Literal["credits", "ranking"]

# Quantas faixas os relatórios podem recortar. Cinco é o limite da paleta
# ordenada da interface (violeta, azul, verde, amarelo, vermelho) e também o
# ponto a partir do qual uma faixa deixa de ter gente bastante para a mediana
# dela significar alguma coisa numa coorte típica.
MAX_BANDS = 5
# Daí o teto de cortes: `q` cortes abrem `q + 1` faixas.
MAX_CUTS = MAX_BANDS - 1

# O domínio de cada eixo de recorte, que é contra o que os cortes se validam.
# O do crédito não está aqui porque não é fixo: é `[min_credits, max_credits]`,
# e sai de `credit_domain`.
GRADE_DOMAIN = (0.0, 10.0)
RESERVE_DOMAIN = (0.0, 1.0)


@dataclass(frozen=True)
class PerformanceShape:
    """A distribuição de desempenho da população — **uma só**.

    A nota sai de uma **normal dividida censurada** em [0, 10], descrita pelas
    três grandezas que se leem — nota mais provável, chance de tirar 0 e chance
    de tirar 10 —, não pelos três parâmetros de forma. A conversão está em
    `equations.grade_shape`.

    Cada uma governa uma parte: a moda é a locação, e o número digitado é
    literalmente o pico da curva; a chance de zero fixa a cauda esquerda e a de
    dez fixa a direita. As três valem para a **disciplina de dificuldade 1 na
    primeira tentativa** — a dificuldade e a recursada transformam as duas
    chances em `equations.attempt_rates`.

    A **média sai derivada**, e fica tipicamente 1 a 2 pontos abaixo da moda,
    porque a cauda esquerda é longa. A taxa de aprovação também é derivada:
    `n_min` é regra de cenário, não propriedade do aluno.

    Houve três **perfis** de desempenho até 19/11/2026, e era deles que vinha a
    dispersão de CR entre alunos: o quantil `q_{a,x}` é sorteado por par
    (aluno, disciplina), de modo que, com uma distribuição só e sem nada mais,
    a média dos quantis de um aluno convergiria para 0,5 e o CR deixaria de
    ordenar ninguém. Quem sustenta essa dispersão agora é o **nível basilar**
    (`SimulationConfig.performance_stability`).
    """

    mode_grade: float = 8.0
    zero_rate: float = 0.005
    max_rate: float = 0.008

    @property
    def shape(self) -> tuple[float, float, float]:
        """(moda, desvio esquerdo, desvio direito) — ver `equations.grade_shape`."""
        return grade_shape(
            mode_grade=self.mode_grade,
            zero_rate=self.zero_rate,
            max_rate=self.max_rate,
        )


@dataclass(frozen=True)
class AvailabilityShape:
    """A distribuição de disponibilidade da população — **uma só**.

    A disponibilidade é a carga que o aluno tem para o período, **em horas**, e
    sai de uma log-normal — suporte (0, ∞), de modo que ela nunca fica negativa
    e **não tem máximo artificial**. Duas grandezas a descrevem: a **moda**, o
    pico da curva em horas, e a **chance de alcançar a carga máxima**, que é a
    frequência com que o aluno não precisa excluir nada. A conversão está em
    `equations.availability_shape`.

    Passar de W_a é permitido e não é inconsistência: o teto de carga é do
    sistema, e quem o aplica é o alocador.

    A forma depende de **W_a**, que é do cenário — "quantas vezes eu encho a
    carga" só significa algo contra uma carga concreta. Por isso `shape` é
    método, e não propriedade.
    """

    mode_hours: float = 306.0
    full_load_rate: float = 0.10

    def shape(self, max_hours: float) -> tuple[float, float]:
        """(média logarítmica, desvio logarítmico) da log-normal."""
        return availability_shape(
            mode_hours=self.mode_hours,
            full_load_rate=self.full_load_rate,
            max_hours=max_hours,
        )


# A calibragem dos dois eixos, agora como uma distribuição só em cada um.
#
# No desempenho, a moda de 8,0 põe a média derivada perto de 6,4 — o patamar
# "médio" dos três perfis antigos, que era o do meio da população que eles
# produziam juntos. As chances de 0 e de 10 são as dele também.
#
# Na disponibilidade, a moda é **absoluta**, em horas, e por isso o padrão é
# uma **função de W_a**: um cenário de teto menor recusaria uma constante
# dimensionada para um teto maior.
DEFAULT_PERFORMANCE = PerformanceShape()

DEFAULT_MAX_HOURS = 24


def default_availability(max_hours: float) -> AvailabilityShape:
    """A distribuição de disponibilidade, dimensionada para um W_a."""
    return AvailabilityShape(
        mode_hours=round(max_hours * 0.85), full_load_rate=0.10
    )


DEFAULT_AVAILABILITY = default_availability(DEFAULT_MAX_HOURS)


@dataclass(frozen=True)
class Discipline:
    """Uma disciplina ofertada — o bem escasso x in B (Tabela 1).

    `unlocks` é a lista de sucessores. Vazia = terminal (altura 0). `entry`
    marca a matrícula garantida de quem ingressa; exige que a disciplina não
    tenha pré-requisito, e o inverso não vale.

    `elective` marca a **optativa**, e é ortogonal a `entry`: uma não implica a
    outra. A optativa não tem pré-requisito, não desbloqueia nada (`unlocks`
    vazia, altura 0) e não é de entrada. Concluir não exige aprovar em cada uma
    delas — exige somar `SimulationConfig.elective_hours` entre as que foram
    aprovadas, e é isso que as torna substituíveis entre si.

    As duas flags respondem perguntas diferentes sobre a mesma disciplina:
    `entry` é "o ingressante ganha esta de graça?"; `elective` é "ela conta
    individualmente para a conclusão, ou só pela carga?". Nenhuma das duas se
    deriva de não ter pré-requisito, que é o erro que a versão anterior
    cometia ao chamar de "1º período" o que era entrada.
    """

    name: str
    seats: int  # vagas somadas de todas as turmas
    hours: int  # w_x — carga horária, replicada inteira em cada turma
    # Em **quantas turmas** a oferta está repartida. O bem alocado é a turma,
    # e a disciplina é o clique do grafo de conflito (eq. 5): ninguém leva duas
    # turmas da mesma disciplina.
    #
    # Com 1 a turma **é** a disciplina — mesmo nome, mesmas vagas —, e a
    # simulação se comporta exatamente como antes de as turmas existirem. É o
    # que torna o modelo sem turmas um caso particular deste, e não um modelo
    # anterior a ele.
    classes: int = 1
    # A **dificuldade**, lida em **quantas tentativas a disciplina custa** para
    # render o que uma de dificuldade 1 rende de primeira: na fórmula da nota
    # ela entra dividida pela tentativa, então dificuldade 2 na 2ª tentativa
    # equivale a dificuldade 1 na 1ª. Ela não precisa ser pública: o que o
    # aluno lê é a taxa de aprovação do período anterior, que é a dificuldade
    # filtrada pela população.
    #
    # É atributo da **disciplina**, e toda turma dela a herda inteira. Houve
    # uma escada por turma (`class_difficulty_levels`) até 16/11/2026; ela
    # saiu junto com a atratividade. O turno, que a substituiu, saiu por sua
    # vez em 19/11/2026 — hoje o que distingue as turmas entre si é o
    # **horário** e o sorteio do interesse.
    difficulty: float = 1.0
    unlocks: tuple[str, ...] = ()
    entry: bool = False
    elective: bool = False
    # Quanto do gosto por esta disciplina é permanente, de 0 a 1. `None` cai no
    # valor do cenário. Declarar por disciplina é o que **sincroniza** a
    # persistência entre concorrentes — se todos que querem uma disciplina
    # continuam querendo ao mesmo tempo, a disputa por ela congela inteira em
    # vez de girar, e é essa sincronia (e não a persistência em si) que trava a
    # fila. Por aluno ou por célula o efeito se dilui.
    stability: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("disciplina sem nome")
        if self.seats < 0:
            raise ValueError(f"disciplina {self.name!r}: vagas (q_x) deve ser >= 0")
        if self.hours <= 0:
            raise ValueError(f"disciplina {self.name!r}: carga horária (w_x) deve ser > 0")
        if self.difficulty <= 0:
            raise ValueError(f"disciplina {self.name!r}: dificuldade deve ser > 0")
        if self.stability is not None and not 0.0 <= self.stability <= 1.0:
            raise ValueError(
                f"disciplina {self.name!r}: a estabilidade deve estar em [0, 1]"
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
    periods: int = 1  # |T| — períodos letivos
    # Quantos dos |T| períodos iniciais são **pré-população**: rodam inteiros,
    # com o mesmo mecanismo, mas ficam fora da medição. É o aquecimento da
    # janela estacionária.
    #
    # Com ingresso em todo período e residência máxima R, no período `t` estão
    # vivas as coortes que entraram em `t, t−1, …, t−R+1`: antes de `t = R`
    # ninguém é velho o bastante para sair, e a população cresce uma coorte
    # por período. A partir de `t = R` entra uma e sai outra, e só aí ela é
    # constante — daí a pré-população ser **fixada em `max_residence`** por
    # quem monta o cenário (`api.service.build_config`).
    #
    # 0, o padrão, mede tudo: é o que o motor fazia antes de a janela existir,
    # e é o que os testes de uma simulação isolada querem.
    #
    # O motor **não joga nada fora** — a simulação devolve todos os períodos, e
    # quem recorta é a comparação (`comparison.observed_periods`). O gráfico
    # de `students` dentro da janela é o teste de validade do aquecimento: se
    # não for plano, ele foi curto.
    warmup_periods: int = 0
    # **Quantos ingressantes entram em cada turma de disciplina de entrada.**
    # É o que se digita, e é também quantas vagas da turma de entrada a
    # matrícula garantida toma: o calouro não disputa a vaga de ingresso, ela
    # abre o período com `z = 1` fixado. O teto é a lotação da turma.
    #
    # A **coorte é derivada** daqui (`students_per_period`): este número vezes
    # as turmas de uma disciplina de entrada. Era a coorte que se digitava até
    # 24/11/2026, e a repartição dela entre as turmas saía com resto — duas
    # vagas numa turma, uma na vizinha —, de modo que o número digitado não se
    # comparava com a lotação sem refazer a divisão.
    students_per_entry_class: int = 8
    # **Jubilamento**: quantos períodos o aluno tem para concluir, contados do
    # ingresso. Quem chega ao fim do último sem concluir sai da simulação e não
    # disputa mais nada. `None` desliga, e aí a conclusão (eq. 40) volta a ser a
    # única porta de saída.
    #
    # É também o que **faz o estado estacionário existir**: com ingresso em
    # todo período, se ninguém saísse a população cresceria sem limite. E é o
    # que fixa o aquecimento, porque a população só é constante a partir de
    # `t = max_residence` — ver `warmup_periods` e `horizon_for_window`.
    #
    # A ordem importa no fechamento do período: quem conclui **no** último
    # período de residência conta como concluinte, não como jubilado — o
    # jubilamento só alcança quem chegou ao fim dele sem fechar a grade.
    max_residence: int | None = None
    # --- os três eixos da população ----------------------------------------
    #
    # Cada um é **uma distribuição só** mais um **nível basilar**: a fração da
    # variância que é permanente do aluno, contra a que é resorteada. É a
    # mesma repartição do interesse (`equations.preference_split`), e a mesma
    # razão — sem componente permanente o eixo descreve o sorteio do período,
    # não um tipo de aluno, e o corte por quantil fatiaria ruído.
    #
    # Havia **perfis** nomeados em cada eixo até 19/11/2026, e era deles que
    # vinha a persistência. Os quantis os substituíram: eles saem do nível
    # basilar, que é contínuo, e por isso não há grupo a declarar.

    # **Desempenho**: a nota sai de uma normal dividida censurada em [0, 10] —
    # ver `grading`. O que o aluno carrega por disciplina é o **quantil** dele
    # naquela matéria. A calibragem importa — sem dispersão de desempenho
    # ninguém reprova, a recursada some do cenário e o CR vira ruído, de modo
    # que a eq. (57) não mede nada.
    performance: PerformanceShape = DEFAULT_PERFORMANCE
    # Quanto do desempenho é **do aluno**, e não da matéria: a correlação entre
    # os quantis dele em duas disciplinas quaisquer.
    #
    # Em 0 o quantil é sorteado de novo em cada matéria, a média dos quantis de
    # um aluno converge para 0,5 e **a dispersão do CR entre alunos não tem
    # piso** — ela cai como 1/√D conforme ele cursa mais disciplinas, e a
    # ordenação por CR passa a ordenar acúmulo de sorte. Em 1 o aluno tem uma
    # posição só, igual em tudo. No meio, "bom em cálculo e ruim em escrita"
    # continua significando alguma coisa sem que o CR deixe de ordenar.
    performance_stability: float = 0.5
    # **Disponibilidade**: a carga que o aluno vai de fato cursar, em horas,
    # sorteada da log-normal **a cada período**. Depois da última rodada ele
    # descarta o que não couber nela (`equations.retained_set`), e o descartado
    # vira solicitação **excluída**: não conta carga, não conta tentativa, não
    # mexe no CR, e no leilão não devolve crédito nenhum.
    #
    # A vaga excluída **não volta para a oferta** — exclui-se depois de
    # encerradas as alocações do período. É o que torna a exclusão socialmente
    # cara e dá sentido à penalidade do leilão.
    #
    # `None` quer dizer **derive de W_a** (`default_availability`): a moda é
    # absoluta, e uma constante fixa recusaria todo cenário de teto menor.
    availability: AvailabilityShape | None = None
    # Quanto da disponibilidade é **permanente**: a correlação entre dois
    # períodos do mesmo aluno. Em 0 o tempo livre é pura circunstância e
    # ninguém é sistematicamente mais ocupado que ninguém.
    availability_stability: float = 0.5
    # **Seletividade**: o eixo de estratégia, e o único que entra na decisão
    # em vez de num sorteio. É o valor da opção externa do aluno — quanto vale
    # não cursar nada —, na **escala do interesse**, que
    # `equations.interest_row` normaliza sobre a grade inteira. A reserva é
    # `S / (S + ΣI)` (`equations.reserve_threshold`).
    #
    # A referência para calibrar: com `S = 1/(turmas da grade)` o limiar fica
    # na utilidade média de uma elegível. Na grade padrão são 288 turmas, daí
    # o default — medido, ele admite 29% das elegíveis.
    #
    # Sai de uma log-normal, como o interesse. A mediana é o que se lê; o
    # sigma é a dispersão em log.
    selectivity_median: float = 0.0035
    selectivity_sigma: float = 0.6
    # Quanto da seletividade é permanente, entre períodos.
    selectivity_stability: float = 0.7
    # Os **pontos de corte** com que os relatórios recortam a população, um
    # eixo por grandeza de estado. Com `q` cortes saem `q + 1` faixas, e sem
    # corte nenhum há uma faixa só, que é a universidade inteira.
    #
    # O corte é no **valor corrente**, e não no quantil do nível basilar: ver
    # `equations.value_band` para por que a pergunta mudou e por que a
    # fronteira tem de ser declarada em vez de amostral.
    #
    # Cada eixo vive no seu domínio, e é contra ele que os cortes se validam:
    # o CR em [0, 10], a reserva em [0, 1) e o saldo entre `min_credits` e
    # `max_credits`. Os cortes **não** são portáveis entre cenários — a
    # reserva se mede em milésimos e desloca com o tamanho da grade (ver
    # `equations.reserve_threshold`), e o saldo depende do orçamento —, então
    # trocar de cenário pede recalibrá-los como já pede recalibrar a mediana
    # da seletividade.
    grade_cuts: tuple[float, ...] = (5.0, 7.0)
    reserve_cuts: tuple[float, ...] = (0.01, 0.03)
    credit_cuts: tuple[int, ...] = (15, 20)
    # **Estabilidade entre turmas**: quanto da variância do interesse fica no
    # nível da disciplina, de 0 a 1. É a irmã espacial da estabilidade entre
    # períodos — uma reparte a variância no tempo, a outra no espaço —, e as
    # duas preservam σ, que é o que mantém a calibragem.
    #
    # Em **1** todas as turmas de uma disciplina recebem necessariamente o
    # mesmo interesse: o gosto é inteiramente pela matéria, e o sorteio da
    # turma nem acontece. Em **0** cada turma é um sorteio independente, e
    # turmas da mesma disciplina não se parecem mais entre si do que turmas
    # de disciplinas diferentes.
    #
    # O parâmetro decide, portanto, se o gosto é **por matéria ou por
    # seção**: em 1 a turma não existe como objeto de preferência, em 0 a
    # disciplina não existe.
    class_stability: float = 1.0
    # Quantos **horários** o cenário tem. Cada horário é um grupo de exclusão
    # mútua entre turmas (eq. 5), e as turmas da grade são repartidas entre
    # eles circularmente — ver `equations.class_schedule`.
    #
    # É o botão de aperto do choque: menos horários é mais turma por horário,
    # e mais escolha do aluno travada por conflito. O **piso** é o maior
    # número de turmas de uma disciplina, senão duas turmas da mesma
    # disciplina dividiriam horário e a oferta efetiva encolheria em silêncio.
    #
    # Não há turno: a divisão entre diurno e noturno, e o eixo de perfil de
    # rotina que a acompanhava, saíram em 19/11/2026.
    slots: int = 12
    # Quanto do gosto do aluno é **permanente**, de 0 a 1 — a fração da
    # variância que não é resorteada a cada período.
    #
    # 0 é o que o modelo fazia antes: a preferência inteira recomeça todo
    # semestre, e o que o aluno quis no passado não diz nada sobre o que quer
    # agora. 1 congela a linha dele para o curso inteiro. No meio, cada
    # semestre é o gosto permanente mais um chacoalhão — o horário, quem dá a
    # disciplina, quanto ele está sobrecarregado.
    #
    # Ela é **ortogonal ao sigma**: a divisão preserva a variância, então cada
    # período continua tendo exatamente a mesma dispersão qualquer que seja
    # este valor. O que muda é só a correlação entre semestres, que é
    # literalmente este número.
    #
    # **Padrão 0,5**: metade do gosto persiste, metade recomeça. 0 reproduz o
    # modelo anterior e é o valor que mais protege o lado fraco da tese — a
    # preferência que não persiste desfaz a fila sozinha —, então ele continua
    # sendo o contraste a rodar. Como esta é a hipótese mais exposta que
    # resta, qualquer resultado em conclusões deve vir com o valor declarado.
    interest_stability: float = 0.5
    # **Interesse** (u, eq. 41): a média (μ) e o desvio (σ) do logaritmo da
    # log-normal de onde ele sai, antes da normalização de
    # `behavior.draw_interest`. A utilidade não tem parâmetro próprio: é o
    # interesse visto pelo histórico do aluno.
    #
    # **μ não mexe em alocação nenhuma.** Somá-lo ao log multiplica a linha
    # inteira por e^μ, e a normalização desfaz o fator: o interesse
    # normalizado, a utilidade, o lance e o histograma saem idênticos para
    # qualquer μ. Ele existe para a **prévia** da interface, que desenha a
    # log-normal fonte antes de normalizar — em μ = 0 a massa se espreme entre
    # 0 e 1 e a curva não se lê. A atratividade A_x de cada disciplina soma-se
    # a ele: a média do log de x é μ + A_x.
    #
    # σ diz o quanto o aluno diferencia uma disciplina da outra — **grande
    # concentra, pequeno achata**, ao contrário da forma da Gamma que havia
    # antes. O coeficiente de variação é sqrt(exp(σ²) − 1), que cresce
    # depressa: a faixa útil inteira cabe entre ~0,25 e ~3.
    #
    # **Padrões μ = 1 e σ = 1**: a moda da fonte cai em e^{μ−σ²} = 1, e o
    # coeficiente de variação fica em ~1,3 — o aluno distingue as disciplinas
    # sem desprezar quase todas.
    interest_mean: float = 1.0
    interest_sigma: float = 1.0
    # W_a — carga horária máxima por período, eq. (4). Igual para todos.
    max_hours: int = DEFAULT_MAX_HOURS
    rounds: int = 1  # |R| — rodadas de alocação por período
    min_grade: float = 5.0  # n_min — nota mínima de aprovação
    # X — carga horária optativa exigida para concluir, somada entre as
    # optativas aprovadas. Concluir é aprovar em **todas** as obrigatórias e
    # chegar a este total nas optativas (eq. 40 estendida). O aluno escolhe
    # *quais*, e é essa substituibilidade — "qualquer X horas serve" — que a
    # ordenação por CR não consegue capturar e o lance consegue.
    elective_hours: int = 0
    # Os dois parâmetros abaixo são do leilão por créditos e **não têm efeito**
    # com `mechanism="ranking"`: ali não há orçamento a repor nem preço pago a
    # devolver. Ficam no cenário assim mesmo porque a comparação entre os dois
    # mecanismos roda a mesma configuração nos dois lados.
    # C_min e C_max delimitam o orçamento com que o aluno abre cada período:
    # a conta da eq. (36) roda livre e o resultado é cortado nos dois extremos.
    # O piso não é ganho — ele só impede que o saldo caia abaixo dele, e é o
    # que torna o retorno da eq. (34) a única entrada de crédito novo.
    # `max_credits=None` desliga o teto. Ver `equations.next_budget`.
    min_credits: int = 12  # C_min — orçamento mínimo do período, eq. (36)/(37)
    max_credits: int | None = 30  # C_max — orçamento máximo do período
    mechanism: Mechanism = "credits"
    seed: int = 0

    @property
    def uses_credits(self) -> bool:
        """Se o crédito existe neste cenário. Na linha de base por CR ele não
        existe — e as grandezas de crédito saem `None` nos relatórios, não zero:
        zero se leria como "ninguém gastou", e o certo é "não há o que gastar".
        """
        return self.mechanism == "credits"

    @property
    def credit_domain(self) -> tuple[float, float]:
        """O domínio do eixo de crédito: o orçamento de abertura vive nele.

        É `C_a^(t,1)` que o eixo recorta, e não o saldo: a eq. (36) o prende
        entre `C_min` e `C_max`, que é o que dá fronteira fixa ao corte. Com
        `max_credits=None` o teto está desligado e o domínio não fecha — ali o
        corte se valida só pelo piso.

        """
        return (float(self.min_credits), float(self.max_credits or math.inf))

    def band_cuts(self, axis: str) -> tuple[float, ...]:
        """Os cortes de um eixo de recorte, pelo nome com que a API o chama."""
        cuts = {
            "grade_average": tuple(float(c) for c in self.grade_cuts),
            "reserve": tuple(float(c) for c in self.reserve_cuts),
            "credits": tuple(float(c) for c in self.credit_cuts),
        }
        if axis not in cuts:
            raise ValueError(f"eixo de recorte desconhecido: {axis}")
        return cuts[axis]

    def band_domain(self, axis: str) -> tuple[float, float]:
        """O domínio de um eixo de recorte — ver `equations.value_band`."""
        domains = {
            "grade_average": GRADE_DOMAIN,
            "reserve": RESERVE_DOMAIN,
            "credits": self.credit_domain,
        }
        if axis not in domains:
            raise ValueError(f"eixo de recorte desconhecido: {axis}")
        return domains[axis]

    def __post_init__(self) -> None:
        """Recusa o cenário que não produziria simulação legível.

        São quatro grupos de verificação, nesta ordem porque cada um depende
        do anterior: os números soltos, a grade, a conclusão e a matrícula
        garantida.
        """
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
        # O piso em 5 é o que mantém "aprovar não custa crédito". Com o
        # multiplicador 2 da eq. (34), aprovar raspando devolve
        # n_min/10 · 2 · preço, que em n_min = 5 é o preço inteiro: o ponto
        # neutro da conta cai em cima da nota de corte. Abaixo de 5 o aluno
        # passaria perdendo saldo — ver `equations.credit_return`.
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
        # Sem disciplina ou sem aluno não há o que alocar: a simulação não
        # produziria período nenhum, e toda métrica sairia indefinida.
        if not self.disciplines:
            raise ValueError("o cenário precisa de pelo menos uma disciplina")
        if self.students_per_entry_class < 1:
            raise ValueError(
                "o cenário precisa de pelo menos um ingressante por turma de entrada"
            )
        self._check_band_cuts()
        # As duas distribuições são de famílias diferentes: a nota é uma normal
        # dividida censurada, a disponibilidade é uma log-normal.
        try:
            self.performance.shape
        except ValueError as erro:
            raise ValueError(f"distribuição de desempenho: {erro}") from erro
        try:
            self.availability_shape()
        except ValueError as erro:
            raise ValueError(f"distribuição de disponibilidade: {erro}") from erro
        if self.selectivity_median < 0:
            raise ValueError("a mediana da seletividade deve ser >= 0")
        if self.selectivity_sigma <= 0:
            raise ValueError("o desvio da seletividade deve ser > 0")
        for nome, valor in (
            ("desempenho", self.performance_stability),
            ("disponibilidade", self.availability_stability),
            ("seletividade", self.selectivity_stability),
        ):
            if not 0.0 <= valor <= 1.0:
                raise ValueError(f"o nível basilar de {nome} deve estar em [0, 1]")
        if not 0.0 <= self.interest_stability <= 1.0:
            raise ValueError("a estabilidade entre períodos deve estar em [0, 1]")
        if not 0.0 <= self.class_stability <= 1.0:
            raise ValueError("a estabilidade entre turmas deve estar em [0, 1]")
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
        """Os cortes de cada eixo: distintos, dentro do domínio, e no teto.

        O crédito se valida contra o orçamento configurado, e não contra um
        teto fixo: um corte fora de `[C_min, C_max]` abriria uma faixa
        garantidamente vazia, que é erro de cenário e não resultado.
        """
        for axis, nome in (
            ("grade_average", "do CR"),
            ("reserve", "da reserva"),
            ("credits", "do saldo"),
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
                # O extremo inferior é a base da faixa de baixo, então cortar
                # nele deixaria essa faixa vazia por construção; o superior
                # fecha a de cima pelo mesmo motivo.
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

        # Ciclo: a cadeia que se fecha não tem altura nem período, e a
        # indução levanta por conta própria.
        self.heights()

        requires = self.prerequisites_by_discipline()
        for discipline in self.disciplines:
            if not requires[discipline.name]:
                continue
            if discipline.entry:
                raise ValueError(
                    f"disciplina {discipline.name!r} é de entrada e tem pré-requisitos"
                )
            # A optativa existe para estar sempre ao alcance; um pré-requisito
            # a tiraria do elegível justamente de quem está atrasado. O outro
            # sentido — optativa não desbloqueia nada — é checado na própria
            # `Discipline`, que já enxerga os `unlocks` dela.
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
        """A matrícula garantida não escolhe quem a recebe, então a oferta de
        entrada tem de comportar a coorte inteira de uma vez.

        São três verificações: que as disciplinas de entrada concordem no
        número de turmas, sem o que a coorte não é um produto; que o ingresso
        por turma caiba na turma; e que o pacote inteiro caiba em W_a.
        """
        entry = self.entry_disciplines()
        if not entry:
            raise ValueError("o cenário precisa de pelo menos uma disciplina de entrada")

        # A coorte é `students_per_entry_class × turmas de entrada`. Com
        # contagens diferentes entre as disciplinas de entrada, cada uma diria
        # uma coorte, e o calouro do bloco excedente de uma ficaria sem vaga na
        # outra.
        counts = {len(self.classes_by_discipline()[name]) for name in entry}
        if len(counts) > 1:
            raise ValueError(
                "as disciplinas de entrada precisam ter o mesmo número de turmas, e "
                f"têm {sorted(counts)}: o ingresso é por turma de entrada, então "
                "contagens distintas implicariam uma coorte por disciplina"
            )

        # O pacote garantido é entregue inteiro e fora do mecanismo, então
        # ele precisa respeitar a eq. (5) por construção. `entry_offsets`
        # procura o giro que o deixa sem choque; não havendo, o cenário é
        # recusado em vez de alocar um pacote impossível de cursar.
        offsets = self.entry_offsets()
        if offsets is None:
            raise ValueError(
                "a matrícula garantida põe duas turmas no mesmo horário para o "
                "mesmo ingressante, e giro nenhum do bloco de entrada desfaz o "
                "choque: o pacote de entrada é entregue inteiro e não pode "
                "chocar consigo mesmo — mude o número de turmas das disciplinas "
                "de entrada ou o número de horários"
            )

        # Por **turma**, não por disciplina: é a turma que tem vaga, e a coorte
        # é repartida entre elas em blocos girados (`equations.entry_class`) de
        # `students_per_entry_class` cada. A oferta declarada na disciplina
        # pode não ser divisível pelas turmas, e aí uma delas tem uma vaga a
        # menos que as outras — é essa que manda.
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
        """O giro do bloco de entrada de cada disciplina — ver
        `equations.entry_class`.

        O pacote garantido é entregue inteiro e fora do mecanismo, então ele
        tem de respeitar a eq. (5) sozinho: nenhum bloco da coorte pode
        receber duas turmas no mesmo horário. Como o horário é atribuído
        varrendo a grade disciplina a disciplina, sem giro as primeiras turmas
        de disciplinas distintas voltam a cair no mesmo horário assim que a
        varredura dá a volta.

        O giro é uma **progressão aritmética**: a j-ésima disciplina de
        entrada gira `j · passo` posições. Procura-se o menor passo que deixe
        todos os blocos sem choque, e **o passo 0 é tentado primeiro** — a
        grade que já saía sem choque não é girada, e continua bit a bit igual.
        `None` quando passo nenhum resolve, e aí o cenário é recusado.

        É função pura do cenário: a mesma grade dá sempre o mesmo giro.
        """
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
        """O último período em que o aluno que entrou em `entry_period` ainda
        disputa. `None` quando o cenário não jubila.

        Ele cursa os períodos de residência a partir do t_a, e é ao fim do
        último deles que o jubilamento o alcança, se não tiver concluído antes.
        """
        if self.max_residence is None:
            return None
        return entry_period + self.max_residence - 1

    @property
    def entry_span(self) -> int:
        """Quantos períodos recebem coorte nova — **todos**.

        Houve um `entry_periods` menor que |T| até 19/11/2026, e com ele uma
        fase de drenagem no fim do horizonte, em que a população só diminuía.
        A janela estacionária a substituiu: o ingresso é contínuo, e quem
        separa o regime do transitório é a pré-população.
        """
        return self.periods

    @property
    def students_per_period(self) -> int:
        """|A_cal| — quantos ingressam por período. **Derivado** do ingresso
        por turma vezes as turmas de uma disciplina de entrada.

        As disciplinas de entrada concordam no número de turmas (o cenário é
        recusado se não concordarem), então o produto não depende de qual delas
        se olha, e a coorte cabe exatamente em blocos de
        `students_per_entry_class` por turma — sem resto, que era o que fazia o
        bloco de uma turma não se comparar com a lotação dela.
        """
        return self.students_per_entry_class * self.entry_classes()

    def total_students(self) -> int:
        """|A| — uma coorte do mesmo tamanho em cada período."""
        return self.students_per_period * self.entry_span

    def availability_shape(self) -> tuple[float, float]:
        """(média logarítmica, desvio logarítmico) da log-normal, com o W_a
        deste cenário."""
        shape = self.availability or default_availability(self.max_hours)
        return shape.shape(self.max_hours)

    def steady_population(self) -> int:
        """Quantos alunos a universidade tem **em regime**.

        Com ingresso de N por período e residência máxima R, no período t
        estão vivas as coortes que entraram em t, t−1, …, t−R+1: a partir de
        `t = R` entra uma e sai outra, e a população fica em `N × R`. Sem
        jubilamento não há regime, e o número é o da população inteira.
        """
        if self.max_residence is None:
            return self.total_students()
        return self.students_per_period * min(self.max_residence, self.periods)

    def _edges(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """As arestas declaradas, na ordem da grade. Serve de chave do memo
        do fecho, e por isso é tupla e não dicionário."""
        return tuple((d.name, d.unlocks) for d in self.disciplines)

    def successors_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """O que cada disciplina desbloqueia **imediatamente**.

        É a `unlocks` do cenário, indexada por nome e completa: disciplina
        terminal aparece com tupla vazia. É a aresta crua, de onde saem a
        altura, o alcance e os dois fechos; o `seq` da monografia é o fecho,
        e está em `reachable_by_discipline`.
        """
        return dict(self._edges())

    def prerequisites_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """Aresta inversa dos sucessores: quem precisa estar aprovado
        **imediatamente antes** para disputar cada disciplina. Mantém a ordem
        do cenário entre os predecessores.

        É o que a elegibilidade lê. Elegibilidade e fecho dão o mesmo
        conjunto — exigir os diretos implica, por indução, todos os
        ancestrais —, e aqui a aresta direta basta e é mais barata.
        """
        return inverse_edges(self.successors_by_discipline())

    def reachable_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """seq(X) — tudo que a disciplina desbloqueia, **transitivamente**.

        É o que `equations.utility` herda: a cadeia inteira à frente, não só
        o próximo passo.
        """
        return _curriculum_closures(self._edges())[0]

    def required_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """req(X) — tudo que a disciplina exige, **transitivamente**.

        É por quantos destes estão elegíveis que `equations.utility` reparte
        a parcela de um sucessor.
        """
        return _curriculum_closures(self._edges())[1]

    def heights(self) -> dict[str, int]:
        """s_x — ver `equations.curriculum_height`."""
        return curriculum_heights(self.successors_by_discipline())

    def curriculum_periods(self) -> dict[str, int]:
        """O período de cada disciplina — ver `equations.curriculum_period`.

        Contagem a partir das raízes, usada nos gráficos. A matrícula
        garantida é a flag `entry`, não este número; a altura conta do outro
        extremo da mesma DAG.
        """
        return curriculum_periods(self.prerequisites_by_discipline())

    def reach(self) -> dict[str, int]:
        """d_x — ver `equations.curriculum_reach`."""
        return curriculum_reach(self.successors_by_discipline())

    def entry_disciplines(self) -> list[str]:
        """Disciplinas de matrícula garantida, na ordem do cenário.

        Vem da flag `entry`, e **não** de não ter pré-requisito: a optativa
        também não tem e não é entrada. É este conjunto que dimensiona a coorte
        e a validação de `max_hours` — o que a oferta precisa comportar é a
        coorte inteira entrando de uma vez.
        """
        return [d.name for d in self.disciplines if d.entry]

    def entry_classes(self) -> int:
        """Em quantas turmas cada disciplina de entrada está repartida.

        É um número só porque o cenário exige que todas concordem: o ingresso é
        por turma de entrada, de modo que contagens distintas implicariam uma
        coorte por disciplina. Zero quando não há disciplina de entrada, que é
        cenário recusado.
        """
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

    # --- turmas: o bem alocado -------------------------------------------
    #
    # A disciplina deixa de ser o bem e vira o **clique** do grafo de conflito
    # (eq. 5): ninguém leva duas turmas dela. O que se replica inteiro em cada
    # turma é a carga horária; o que se reparte é a vaga.
    #
    # Com `classes = 1` a turma **é** a disciplina, com o mesmo nome e as
    # mesmas vagas, e nenhum clique é gerado — a simulação roda idêntica à de
    # antes de as turmas existirem.

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
        """Turma → grupo. Como o grafo de conflito é uma **partição**, este
        dicionário basta: não é preciso varrer cliques para saber se dois bens
        se excluem."""
        return {
            name: d.name for d in self.disciplines for name in self.classes_of(d)
        }

    def seats_by_class(self) -> dict[str, int]:
        """q_x — a oferta repartida entre as turmas do grupo.

        As primeiras `seats % classes` turmas levam uma vaga a mais, de modo
        que a soma devolve exatamente a oferta declarada.

        **Toda vaga entra aqui**, inclusive a que a matrícula garantida vai
        tomar: numa turma de entrada, `students_per_entry_class` das vagas saem
        com `z = 1` fixado na abertura do período, e o que vai a mecanismo é o
        que resta. Separá-las em duas pilhas foi tentado em 24/11/2026 e
        desfeito no mesmo dia: a vaga fora de `q_x` deixava o aluno cursando
        turma que o relatório não dizia ter sido entregue.
        """
        seats: dict[str, int] = {}
        for discipline in self.disciplines:
            names = self.classes_of(discipline)
            base, extra = divmod(discipline.seats, len(names))
            for i, name in enumerate(names):
                seats[name] = base + (1 if i < extra else 0)
        return seats

    def hours_by_class(self) -> dict[str, int]:
        """`w_x` replicado: cada turma custa a carga inteira da disciplina —
        ninguém cursa um terço das horas."""
        return {
            name: d.hours for d in self.disciplines for name in self.classes_of(d)
        }

    def difficulty_by_class(self) -> dict[str, float]:
        """A dificuldade da disciplina, replicada em cada turma dela.

        É atributo do grupo: a escada por turma saiu, e o que distingue as
        turmas é o **turno**.
        """
        return {
            name: d.difficulty
            for d in self.disciplines
            for name in self.classes_of(d)
        }

    def schedule_by_class(self) -> dict[str, str]:
        """Turma → horário — ver `equations.class_schedule`.

        A varredura é na ordem da grade, que é a ordem em que o cenário
        declara as disciplinas: é dela que sai o equilíbrio entre horários e
        o fato de as turmas de uma disciplina caírem em horários consecutivos,
        e portanto distintos.
        """
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
        """`M` — um clique por disciplina com mais de uma turma.

        Disciplina de turma única não gera clique — a restrição
        `Σ z ≤ 1` sobre um bem só já é a restrição binária dele.
        """
        return tuple(
            frozenset(names)
            for d in self.disciplines
            if len(names := self.classes_of(d)) > 1
        )

    def schedule_cliques(self) -> tuple[frozenset[str], ...]:
        """`G` — um clique por horário com mais de uma turma."""
        return schedule_cliques(self.schedule_by_class(), self.schedules())

    def exclusion_cliques(self) -> tuple[frozenset[str], ...]:
        """`E = M ∪ G` — o que a eq. (5) proíbe levar junto.

        São duas famílias e a mesma restrição: ninguém leva duas turmas da
        mesma disciplina, nem duas turmas no mesmo horário.
        """
        return self.discipline_cliques() + self.schedule_cliques()

    def conflict_groups(self) -> dict[str, tuple[str, ...]]:
        """Turma → os grupos de `E` a que ela pertence: a disciplina e o
        horário.

        É a forma que a varredura usa — `available_goods`,
        `serial_dictatorship` e o preço —, porque ali a pergunta é "este aluno
        já levou algo que conflita com isto?", e não "quais bens formam um
        clique".
        """
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
        """S — a carga horária mínima para concluir: a soma de w_x de **todas
        as obrigatórias** mais a exigência optativa X.

        Não é a carga da grade inteira desde que há optativa: o catálogo delas
        é maior que a exigência de propósito, e é essa folga que dá ao aluno o
        que escolher.
        """
        required = sum(d.hours for d in self.disciplines if not d.elective)
        return required + self.elective_hours

    def minimum_periods_to_graduate(self) -> int:
        """Piso de períodos para concluir: nem quem nunca reprova nem perde uma
        vaga fecha a grade antes disso.

        São dois limites, e vale o maior. A **carga horária** impede cursar mais
        de W_a por período, o que dá ceil(S / W_a). A **cadeia** impõe que a
        disciplina de n-ésimo período não pode ser cursada antes do n-ésimo
        período do aluno.

        Serve para dimensionar a fase de drenagem: abaixo disso nenhuma coorte
        tem tempo de chegar ao fim, e a série por coorte mediria o horizonte em
        vez do mecanismo.
        """
        by_hours = -(-self.hours_to_graduate() // self.max_hours)
        by_chain = max(self.curriculum_periods().values(), default=0)
        return max(by_hours, by_chain)


def horizon_for_window(*, max_residence: int, observation_periods: int) -> int:
    """|T| — o horizonte da janela estacionária.

    A **pré-população é o próprio prazo de jubilamento**: com ingresso em todo
    período e residência máxima R, a população só fica constante — exatamente
    `N × R` — a partir de `t = R`, porque antes disso nenhuma coorte é velha o
    bastante para sair e entra uma por período sem sair nenhuma. Medir antes
    disso seria medir a rampa, e as métricas deste modelo são muito sensíveis
    ao tamanho da população.

    Depois vêm os períodos **observados**, que são os que as tabelas e os
    gráficos mostram.

    Substituiu o `horizon_for_lifecycle` em 19/11/2026, junto com a fase de
    drenagem que ele existia para acomodar.

    É função solta, e não método de `SimulationConfig`, porque a tela de
    configuração precisa do número **antes** de haver cenário — ela mostra o |T|
    enquanto o usuário mexe nos dois controles de que ele sai.
    """
    return max_residence + observation_periods
