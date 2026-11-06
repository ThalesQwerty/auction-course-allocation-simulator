"""Configuração de um cenário de simulação (Seção 7.2 do anteprojeto).

O usuário descreve o cenário em dois blocos — parâmetros gerais e disciplinas —
e a simulação deriva o resto (alunos, nomes, interesse, notas)
aleatoriamente a partir da `seed`.

**Os perfis de aluno descrevem o comportamento fora do mecanismo.** São dois
eixos independentes — `performance_profiles`, que governa a Beta da aptidão e
portanto a frequência com que o aluno reprova, e `availability_profiles`, que
governa a Beta da disponibilidade e portanto a frequência com que ele exclui.
Cada eixo é uma lista de grupos, e o aluno carrega **dois escalares** sorteados
das Betas dos grupos que lhe couberam.

O perfil é **traço imutável**: não evolui, não responde a sinal, não entra no
genoma e o aluno não o conhece. Ele age *depois* da vaga — se o aluno vai bem
na disciplina ou se a larga. A estratégia (`equations.decision_score`) age
*dentro* do mecanismo, ao pedir. Não há eixo de perfil para interesse: o β do
score já é o parâmetro de o quanto o aluno diferencia as disciplinas, e dois
botões para a mesma coisa tornariam qualquer resultado ambíguo de ler.

A repartição é **igualitária entre as combinações** — ver `profile_index`.

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
from typing import Literal

from .equations import (
    Behavior,
    availability_shape,
    class_difficulty,
    curriculum_heights,
    curriculum_periods,
    curriculum_reach,
    eligible_set,
    entry_class_load,
    grade_shape,
)

# Mecanismo de alocação. `credits` é o leilão por créditos proposto (Seção 7.1),
# em que o aluno reparte um orçamento entre lances e um PLI decide a alocação.
# `ranking` é a linha de base tradicional (Seção 7.3.1, eqs. 49-50): não há
# leilão nem PLI — as solicitações são atendidas em ordem decrescente do CR do
# aluno, e a carga horária faz o papel do orçamento.
Mechanism = Literal["credits", "ranking"]

# Quem decide a alocação, dada a mensagem dos alunos — o passo do meio do
# caminho da comparação (ver `comparison.ARMS`).
#
# A diferença é **ordinal x cardinal**, e não "guloso x exato": a varredura
# usa só a *ordem* das preferências, de modo que qualquer transformação
# monótona do vetor dá a mesma alocação; a PLI usa as *magnitudes*, e derruba
# um lance alto para acomodar dois médios, o que a varredura nunca faz.
#
# Com lance e varredura sai o *bidding points* clássico das business schools
# (Sönmez & Ünver 2010, sobre Michigan e Yale SOM). Cuidado com a afirmação de
# que é "o mais implantado do mundo": Wharton o substituiu pelo **Course
# Match** (A-CEEI resolvido por MIP), que é cardinal — então a direção
# histórica é do ordinal para o cardinal, e não o contrário.
#
# Os dois resolvedores só divergem onde a restrição de carga aperta — sem ela
# o problema se separa por disciplina e o guloso é ótimo —, então o passo só
# tem conteúdo em cenário com conjunto elegível maior que W_a.
Resolver = Literal["ilp", "greedy"]

# Política de retorno de créditos f_gamma — eq. (34). O anteprojeto deixa a
# forma concreta em aberto e trata as políticas como eixo de experimentação
# (Seção 7.3.2) — as quatro comparadas estão em `grading.credit_return`.
CreditReturnPolicy = Literal["none", "unit", "full", "ratio"]

# Quanta memória o orçamento tem de um período para o outro — o eixo da ideia 1.
#
# `"none"`: o período começa sempre em Gamma_min. O leilão não tem memória
# nenhuma, e é o único braço em que o passado do aluno não entra no poder de
# compra dele por via alguma.
# `"carry"`: a eq. (36) — o que sobrou é carregado. Note que isso **não** é
# poupança: o aluno aposta o orçamento inteiro e paga o segundo preço, então o
# que sobra é o que ele não foi cobrado, não o que ele guardou.
#
# Cruzado com `credit_return`, dá a escada de três degraus: sem acúmulo
# ("none"), só sobra ("carry" + retorno "none") e sobra + retorno ("carry" +
# "ratio"). O degrau do meio separa as duas fontes de memória, que têm sinais
# opostos de incentivo: a sobra premia quem pagou barato, o retorno premia quem
# aprovou.
CreditMemory = Literal["none", "carry"]


@dataclass(frozen=True)
class PerformanceProfile:
    """Um grupo da população no eixo de desempenho.

    A nota sai de uma **normal dividida censurada** em [0, 10], e o grupo a
    descreve pelas três grandezas que se leem — nota mais provável, chance de
    tirar 0 e chance de tirar 10 —, não pelos três parâmetros de forma. A
    conversão está em `equations.grade_shape`.

    Cada uma governa uma parte: a moda é a locação, e o número digitado é
    literalmente o pico da curva; a chance de zero fixa a cauda esquerda e a de
    dez fixa a direita. As três valem para a **disciplina de dificuldade 1 na
    primeira tentativa** — a dificuldade e a recursada transformam as duas
    chances em `equations.attempt_rates`.

    A **média sai derivada**, e fica tipicamente 1 a 2 pontos abaixo da moda,
    porque a cauda esquerda é longa. A taxa de aprovação também é derivada:
    `n_min` é regra de cenário, não propriedade do aluno, e se definisse o
    perfil mudar a linha de corte redefiniria a população em silêncio.

    Toda trinca existe — não há combinação a recusar. Parametrizar pela média,
    ao contrário, deixaria casos inviáveis: com a moda presa dentro da escala,
    média alta com poucos dezes não fecha.

    O nome é rótulo de relatório, e precisa ser único dentro do seu eixo — é
    por ele que o recorte por perfil separa os grupos.
    """

    name: str
    mode_grade: float
    zero_rate: float
    max_rate: float

    @property
    def shape(self) -> tuple[float, float, float]:
        """(moda, desvio esquerdo, desvio direito) — ver `equations.grade_shape`."""
        return grade_shape(
            mode_grade=self.mode_grade,
            zero_rate=self.zero_rate,
            max_rate=self.max_rate,
        )


@dataclass(frozen=True)
class AvailabilityProfile:
    """Um grupo da população no eixo de disponibilidade.

    A disponibilidade é a carga que o aluno tem para o período, **em horas**, e
    sai de uma log-normal — suporte (0, ∞), de modo que ela nunca fica negativa
    e **não tem máximo artificial**. O grupo a descreve pelas duas grandezas
    que se leem: a **moda**, o pico da curva em horas, e a **chance de alcançar
    a carga máxima**, que é a frequência com que ele não precisa excluir nada.
    A conversão está em `equations.availability_shape`.

    Passar de W_a é permitido e não é inconsistência: o teto de carga é do
    sistema, e quem o aplica é o alocador. Quem tem tempo para mais do que o
    curso oferece simplesmente não exclui nada.

    A forma depende de **W_a**, que é do cenário e não do perfil — "quantas
    vezes eu encho a carga" só significa algo contra uma carga concreta. Por
    isso `shape` é método, e não propriedade: o perfil guarda o que é dele, e a
    conversão recebe o resto na hora.

    O nome é rótulo de relatório, e precisa ser único dentro do seu eixo — é
    por ele que o recorte por perfil separa os grupos.
    """

    name: str
    mode_hours: float
    full_load_rate: float

    def shape(self, max_hours: float) -> tuple[float, float]:
        """(média logarítmica, desvio logarítmico) da log-normal."""
        return availability_shape(
            mode_hours=self.mode_hours,
            full_load_rate=self.full_load_rate,
            max_hours=max_hours,
        )


# A calibragem dos dois eixos. A nota mais provável do perfil de desempenho é o
# pico da curva numa disciplina de dificuldade padrão, de primeira; a **média**
# sai 1 a 2 pontos abaixo dela, porque a cauda esquerda é longa. O "baixo" fica
# calibrado por essa média derivada: ela encosta em `n_min = 5` (4,96), de modo
# que ele reprova em torno de metade das vezes.
#
# As chances de 0 e de 10 separam os grupos onde a média sozinha não separa:
# o forte quase nunca zera e tira 10 em 3% das disciplinas; o fraco zera em 3%
# e quase nunca tira 10. É a assimetria entre as duas caudas que dá ao CR o
# que ordenar.
#
# O nome carrega o eixo de propósito. "Alto" e "Alta" nos dois lados fariam
# "alto-baixo" virar charada em legenda de gráfico; com o eixo no rótulo, a
# combinação se lê sozinha.
DEFAULT_PERFORMANCE: tuple[PerformanceProfile, ...] = (
    PerformanceProfile(
        name="Alto desempenho", mode_grade=9.0, zero_rate=0.0005, max_rate=0.030
    ),
    PerformanceProfile(
        name="Médio desempenho", mode_grade=8.0, zero_rate=0.0050, max_rate=0.008
    ),
    PerformanceProfile(
        name="Baixo desempenho", mode_grade=6.5, zero_rate=0.0300, max_rate=0.0015
    ),
)

# A chance de alcançar a carga máxima é o que separa os três de verdade:
# "Alta" enche a carga em dois de cada cinco semestres, "Baixa" quase nunca — e
# é essa chance, não a moda, que governa a frequência de exclusão.
#
# A moda é **absoluta**, em horas, e por isso o padrão é uma **função de W_a**
# e não uma constante: um cenário de teto menor recusaria modas dimensionadas
# para 360 h. Quem declara os próprios perfis os declara em horas, e aí a
# responsabilidade de caber é de quem declarou.
#
# As frações (0,95, 0,85 e 0,60) são as médias que os três patamares tinham
# quando a disponibilidade ainda era medida em fração de W_a. Elas entram como
# **moda**, não como média — a log-normal é assimétrica, então os dois não
# coincidem —, mas mantêm os patamares onde estavam.
def default_availability(max_hours: float) -> tuple[AvailabilityProfile, ...]:
    """Os três patamares de disponibilidade, dimensionados para um W_a."""
    return (
        AvailabilityProfile(
            name="Alta disponibilidade",
            mode_hours=round(max_hours * 0.95),
            full_load_rate=0.40,
        ),
        AvailabilityProfile(
            name="Média disponibilidade",
            mode_hours=round(max_hours * 0.85),
            full_load_rate=0.10,
        ),
        AvailabilityProfile(
            name="Baixa disponibilidade",
            mode_hours=round(max_hours * 0.60),
            full_load_rate=0.005,
        ),
    )


DEFAULT_MAX_HOURS = 360
DEFAULT_AVAILABILITY: tuple[AvailabilityProfile, ...] = default_availability(
    DEFAULT_MAX_HOURS
)

# O perfil de quem é construído **fora** de `generate_students` — um aluno de
# teste, um cenário escrito à mão. Não descreve grupo nenhum: reproduz o grupo
# médio no desempenho e disponibilidade praticamente cheia, de modo que
# construir um aluno sem dizer o perfil dele não liga a exclusão sem querer.
NEUTRAL_PERFORMANCE = PerformanceProfile(
    name="—", mode_grade=8.0, zero_rate=0.0050, max_rate=0.008
)
# Praticamente nunca exclui, de modo que construir um aluno à mão não liga a
# exclusão sem querer. A moda é relativa porque este perfil é usado fora de um
# cenário, sem W_a a que se ancorar; quem o consome o reescala.
NEUTRAL_AVAILABILITY = AvailabilityProfile(
    name="—", mode_hours=round(DEFAULT_MAX_HOURS * 0.99), full_load_rate=0.999
)


@dataclass(frozen=True)
class SelectivityProfile:
    """Um grupo da população no eixo de **seletividade**.

    O valor é um múltiplo do score médio: o aluno não pede — nem financia —
    nada abaixo de `valor × média`. Ver `equations.reserve_threshold`.

    Em 0 não há corte: ele pede tudo que é elegível e gasta o orçamento
    inteiro. É o especulador, e é o perfil que a Seção 2.2 do anteprojeto diz
    que o CR incentiva.
    """

    name: str
    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"seletividade {self.name!r}: o valor deve ser >= 0")


@dataclass(frozen=True)
class ConcentrationProfile:
    """Um grupo da população no eixo de **concentração**.

    O valor é o expoente do score sobre a utilidade. 1 é o lance sincero — o
    ótimo da relaxação contínua da mochila côncava —, e os extremos existem
    para mostrar o que acontece fora dele. Ver `equations.decision_score`.
    """

    name: str
    value: float


# Seis níveis em cada eixo novo, e com os três de cada eixo antigo dão
# 3 · 3 · 6 · 6 = 324 combinações. Elas é que fixam o tamanho da coorte: ver
# `students_per_period`.
DEFAULT_SELECTIVITY: tuple[SelectivityProfile, ...] = (
    SelectivityProfile(name="Neutra", value=0.0),
    SelectivityProfile(name="Baixíssima", value=0.125),
    SelectivityProfile(name="Baixa", value=0.25),
    SelectivityProfile(name="Média", value=0.5),
    SelectivityProfile(name="Alta", value=1.0),
    SelectivityProfile(name="Altíssima", value=2.0),
)

# O Invertido e o Homogêneo são controles: um demonstra o absurdo de reportar
# torto, o outro testa a premissa da Seção 2.2 sobre revelação de preferência.
# Acima de 2 o expoente satura e deixa de graduar — o 3 mostra a saturação.
DEFAULT_CONCENTRATION: tuple[ConcentrationProfile, ...] = (
    ConcentrationProfile(name="Invertida", value=-1.0),
    ConcentrationProfile(name="Homogênea", value=0.0),
    ConcentrationProfile(name="Diluída", value=0.5),
    ConcentrationProfile(name="Neutra", value=1.0),
    ConcentrationProfile(name="Concentrada", value=2.0),
    ConcentrationProfile(name="Muito concentrada", value=3.0),
)

NEUTRAL_SELECTIVITY = SelectivityProfile(name="—", value=0.0)
NEUTRAL_CONCENTRATION = ConcentrationProfile(name="—", value=1.0)


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
    # A_x — a **atratividade**: o multiplicador do interesse sorteado, comum a
    # toda a população. Em 1 a disciplina é a média; 2 vale o dobro dela, 0,5
    # a metade. Entra como ln(A) somado ao expoente da log-normal, que é a
    # mesma conta dita na unidade em que se lê.
    #
    # É a componente do gosto **comum a toda a população**, enquanto sigma é a
    # privada de cada aluno, e as duas estão na mesma unidade — por isso A/σ se
    # lê direto como a correlação de preferência entre alunos. Com A uniforme as
    # linhas são independentes e ninguém pode prever a disputa pelo próprio
    # gosto; com A espalhado, querer muito uma disciplina passa a ser sinal de
    # que os colegas também a querem.
    #
    # Ela é a irmã estática de `stability`: aquela sincroniza a persistência
    # entre concorrentes no *tempo*, esta sincroniza o *nível*.
    attractiveness: float = 1.0

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
    # Em quantos dos |T| períodos entra coorte nova, contados do primeiro.
    # `None` = em todos, e aí o último período recebe uma coorte que só vive
    # esse período. Quando são menos que |T|, a simulação ganha uma fase de
    # drenagem: depois do último ingresso a população só diminui, e as coortes
    # tardias têm tempo de chegar ao fim do curso em vez de serem cortadas pelo
    # horizonte.
    entry_periods: int | None = None
    # **Exemplares de cada perfil em cada coorte** — é por aqui que se controla
    # o tamanho da população.
    #
    # A coorte não é digitada: ela é `students_per_profile × combinações`, e
    # com os padrões de 3 · 3 · 6 · 6 isso dá 324 alunos por exemplar. Deixar
    # o controle aqui faz a divisibilidade sair de graça — a repartição do
    # `profile_index` é exata por construção, e some a classe inteira de
    # cenários em que a sobra gira entre as coortes e os perfis ficam
    # desiguais.
    students_per_profile: int = 1
    # **Jubilamento**: quantos períodos o aluno tem para concluir, contados do
    # ingresso. Quem chega ao fim do último sem concluir sai da simulação e não
    # disputa mais nada. `None` desliga, e aí a conclusão (eq. 40) volta a ser a
    # única porta de saída.
    #
    # É o que fecha o ciclo de vida da população: o último ingressante sai um
    # período de residência depois do último ingresso, menos a sobreposição do
    # primeiro, e depois dele não há mais ninguém. Daí o horizonte derivado em
    # `horizon_for_lifecycle`, que é o |T| que a tela de configuração mostra.
    #
    # A ordem importa no fechamento do período: quem conclui **no** último
    # período de residência conta como concluinte, não como jubilado — o
    # jubilamento só alcança quem chegou ao fim dele sem fechar a grade.
    max_residence: int | None = None
    # --- os dois eixos de perfil --------------------------------------------
    #
    # **Desempenho**: a nota sai de uma normal dividida censurada em [0, 10] —
    # ver `grading`. O que o aluno carrega por disciplina é o **quantil** dele
    # naquela matéria, sorteado uma vez e persistente: é traço, não sorte. A
    # dificuldade e a recursada movem a distribuição sob esse quantil. A
    # calibragem importa — sem dispersão de desempenho ninguém reprova, a
    # recursada some do cenário e o CR vira ruído, de modo que a eq. (57) não
    # mede nada.
    performance_profiles: tuple[PerformanceProfile, ...] = DEFAULT_PERFORMANCE
    # **Disponibilidade**: a fração de W_a que o aluno vai de fato cursar,
    # sorteada da Beta do perfil **a cada período** — ao contrário da aptidão,
    # que é uma só para o curso inteiro. Depois da última rodada ele descarta
    # o que não couber nessa fração (`equations.retained_set`), e o descartado
    # vira solicitação **excluída**: não conta carga, não conta tentativa, não
    # mexe no CR, e no leilão devolve metade do preço pago
    # (`equations.exclusion_refund`).
    #
    # A vaga excluída **não volta para a oferta** — exclui-se depois de
    # encerradas as alocações do período. É o que torna a exclusão socialmente
    # cara e dá sentido à penalidade do leilão.
    # Vazio quer dizer **derive de W_a** (`default_availability`): as modas
    # são absolutas, e uma constante dimensionada para 360 h recusaria todo
    # cenário de teto menor. Declarar explicitamente desliga a derivação.
    availability_profiles: tuple[AvailabilityProfile, ...] = ()
    # Os dois eixos de **estratégia**. Ao contrário dos dois de cima, que
    # são traço e entram só no sorteio, estes viram o `Behavior` do aluno e
    # entram na decisão: a seletividade corta o pedido e para o gasto, a
    # concentração reparte o crédito. Ver `equations.reserve_threshold` e
    # `equations.decision_score`.
    # **Estabilidade entre turmas**: quanto da variância do interesse fica no
    # nível da disciplina, de 0 a 1. É a irmã espacial da estabilidade entre
    # períodos — uma reparte a variância no tempo, a outra no espaço —, e as
    # duas preservam σ, que é o que mantém a calibragem.
    #
    # Em **1** todas as turmas de uma disciplina recebem necessariamente o
    # mesmo interesse: o gosto é inteiramente pela matéria, e o sorteio da
    # turma nem acontece. Em **0** cada turma é um sorteio independente, e
    # turmas da mesma disciplina não se parecem mais entre si do que turmas
    # de disciplinas diferentes — o agrupamento some *do gosto*, e continua
    # valendo para clique, pré-requisito, carga e nota.
    #
    # O parâmetro decide, portanto, se o gosto é **por matéria ou por
    # seção**: em 1 a turma não existe como objeto de preferência, em 0 a
    # disciplina não existe.
    class_stability: float = 1.0
    # Os multiplicadores (baixa, média, alta) da escada de dificuldade entre
    # turmas do mesmo grupo. Iguais a 1 — o padrão — desligam a escada.
    #
    # A escada preserva a **média geométrica** da disciplina em todo `k`,
    # então mexer nela é mexer na amplitude, não no centro: o cenário não
    # fica mais difícil nem mais fácil por abrir mais turmas.
    class_difficulty_levels: tuple[float, float, float] = (1.0, 1.0, 1.0)
    selectivity_profiles: tuple[SelectivityProfile, ...] = DEFAULT_SELECTIVITY
    concentration_profiles: tuple[ConcentrationProfile, ...] = DEFAULT_CONCENTRATION
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
    base_credits: int = 10  # Gamma_min — créditos base por período, eq. (35)/(37)
    credit_return: CreditReturnPolicy = "none"
    credit_memory: CreditMemory = "carry"
    mechanism: Mechanism = "credits"
    resolver: Resolver = "ilp"
    seed: int = 0

    @property
    def uses_credits(self) -> bool:
        """Se o crédito existe neste cenário. Na linha de base por CR ele não
        existe — e as grandezas de crédito saem `None` nos relatórios, não zero:
        zero se leria como "ninguém gastou", e o certo é "não há o que gastar".
        """
        return self.mechanism == "credits"

    def __post_init__(self) -> None:
        """Recusa o cenário que não produziria simulação legível.

        São quatro grupos de verificação, nesta ordem porque cada um depende
        do anterior: os números soltos, a grade, a conclusão e a matrícula
        garantida.
        """
        if not self.availability_profiles:
            object.__setattr__(
                self,
                "availability_profiles",
                default_availability(self.max_hours),
            )
        self._check_horizon()
        self._check_population()
        self._check_curriculum()
        self._check_graduation()
        self._check_guaranteed_enrolment()

    def _check_horizon(self) -> None:
        if self.periods < 1:
            raise ValueError("é preciso simular ao menos 1 período")
        if self.entry_periods is not None and not 1 <= self.entry_periods <= self.periods:
            raise ValueError(
                "períodos com ingresso deve estar entre 1 e o total de períodos "
                f"({self.periods})"
            )
        if self.rounds < 1:
            raise ValueError("é preciso simular ao menos 1 rodada por período")
        # O piso em 5 é do retorno por exclusão: ele devolve metade do preço
        # pago, e abaixo de 5 a metade passaria a render mais que a aprovação
        # raspada — excluir bateria passar. Ver `equations.exclusion_refund`.
        if not 5 <= self.min_grade <= 10:
            raise ValueError("nota mínima deve estar em [5, 10]")
        if self.base_credits < 1:
            raise ValueError("créditos base (Gamma_min) deve ser >= 1")
        if self.max_hours < 1:
            raise ValueError("carga horária máxima (W_a) deve ser >= 1")
        if self.max_residence is not None and self.max_residence < 1:
            raise ValueError("o tempo até o jubilamento deve ser >= 1")

    def _check_population(self) -> None:
        # Sem disciplina ou sem aluno não há o que alocar: a simulação não
        # produziria período nenhum, e toda métrica sairia indefinida.
        if not self.disciplines:
            raise ValueError("o cenário precisa de pelo menos uma disciplina")
        if self.students_per_profile < 1:
            raise ValueError(
                "o cenário precisa de pelo menos um exemplar de cada perfil"
            )
        for eixo, perfis in (
            ("desempenho", self.performance_profiles),
            ("disponibilidade", self.availability_profiles),
            ("seletividade", self.selectivity_profiles),
            ("concentração", self.concentration_profiles),
        ):
            if not perfis:
                raise ValueError(f"o eixo de {eixo} precisa de pelo menos um perfil")
            nomes = [p.name.strip() for p in perfis]
            if any(not nome for nome in nomes):
                raise ValueError(f"todo perfil de {eixo} precisa de um nome")
            if len(set(nomes)) != len(nomes):
                raise ValueError(f"os nomes dos perfis de {eixo} devem ser únicos")
        # Os números de cada eixo são de famílias diferentes: a nota é uma
        # normal dividida censurada, a disponibilidade é uma Beta.
        for perfil in self.performance_profiles:
            try:
                perfil.shape
            except ValueError as erro:
                raise ValueError(
                    f"perfil de desempenho '{perfil.name}': {erro}"
                ) from erro
        for perfil in self.availability_profiles:
            try:
                perfil.shape(self.max_hours)
            except ValueError as erro:
                raise ValueError(
                    f"perfil de disponibilidade '{perfil.name}': {erro}"
                ) from erro
        if not 0.0 <= self.interest_stability <= 1.0:
            raise ValueError("a estabilidade entre períodos deve estar em [0, 1]")
        if not 0.0 <= self.class_stability <= 1.0:
            raise ValueError("a estabilidade entre turmas deve estar em [0, 1]")
        for nivel in self.class_difficulty_levels:
            if nivel <= 0:
                raise ValueError(
                    "os níveis da escada de dificuldade devem ser > 0"
                )
        if self.interest_sigma <= 0:
            raise ValueError("desvio do interesse (sigma) deve ser > 0")
        if not math.isfinite(self.interest_mean):
            raise ValueError("a média do interesse deve ser um número finito")

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
        entrada tem de comportar a coorte inteira de uma vez."""
        entry = self.entry_disciplines()
        if not entry:
            raise ValueError("o cenário precisa de pelo menos uma disciplina de entrada")

        # Por **turma**, não por disciplina: é a turma que tem vaga, e a
        # coorte é repartida entre elas em blocos (`equations.entry_class`).
        # Quando a disciplina de entrada tem turma única os dois conferem.
        seats = self.seats_by_class()
        classes = self.classes_by_discipline()
        cohort = self.students_per_period
        for discipline in entry:
            load = entry_class_load(cohort=cohort, classes=classes[discipline])
            for name, newcomers in load.items():
                if newcomers > seats[name]:
                    raise ValueError(
                        f"a coorte de {cohort} alunos põe {newcomers} ingressantes em "
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
        """Quantos períodos recebem coorte nova, resolvido o `None`."""
        return self.periods if self.entry_periods is None else self.entry_periods

    def total_students(self) -> int:
        """|A| — uma coorte do mesmo tamanho em cada período com ingresso."""
        return self.students_per_period * self.entry_span

    @property
    def students_per_period(self) -> int:
        """Alunos que ingressam em cada período com ingresso.

        **Derivado**, não digitado: é `students_per_profile` vezes o número de
        combinações de perfil, de modo que toda coorte contém exatamente o
        mesmo número de exemplares de cada perfil.
        """
        return self.students_per_profile * self.profile_combinations()

    def profile_combinations(self) -> int:
        """Quantas combinações dos quatro eixos de perfil existem."""
        return (
            len(self.performance_profiles)
            * len(self.availability_profiles)
            * len(self.selectivity_profiles)
            * len(self.concentration_profiles)
        )

    def profile_index(self, student_index: int) -> tuple[int, int, int, int]:
        """A combinação (desempenho, disponibilidade, seletividade,
        concentração) do aluno de índice global.

        A repartição é **igualitária entre as combinações**, e exata: como a
        coorte é `students_per_profile × combinações`, cada perfil recebe o
        mesmo número de exemplares em toda coorte, sem sobra a girar.

        O rodízio é sobre o índice **global**, não o índice dentro da coorte.
        Com a coorte sendo múltipla exata das combinações os dois dão a mesma
        resposta; o global é o que continua valendo se alguém construir um
        cenário à mão com outro tamanho.

        Os dois primeiros eixos são **traço**: o aluno não os escolhe nem os
        conhece, e eles governam o sorteio da aptidão e da disponibilidade.
        Os dois últimos são **estratégia**: viram o `Behavior` dele e entram
        na decisão de lance e de pedido.

        O perfil **não sai da seed**, pelo mesmo motivo que o período de
        ingresso não sai: duas simulações com seeds diferentes têm a mesma
        estrutura de perfis, então a diferença entre elas não é quem calhou de
        ser frágil nem quem calhou de ser especulador.
        """
        combination = student_index % self.profile_combinations()
        concentration = combination % len(self.concentration_profiles)
        combination //= len(self.concentration_profiles)
        selectivity = combination % len(self.selectivity_profiles)
        combination //= len(self.selectivity_profiles)
        availability = combination % len(self.availability_profiles)
        performance = combination // len(self.availability_profiles)
        return performance, availability, selectivity, concentration

    def prerequisites_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """Aresta inversa dos sucessores: quem precisa estar aprovado para
        disputar cada disciplina. Mantém a ordem do cenário entre os
        predecessores."""
        preds: dict[str, list[str]] = {d.name: [] for d in self.disciplines}
        for discipline in self.disciplines:
            for successor in discipline.unlocks:
                preds[successor].append(discipline.name)
        return {name: tuple(parents) for name, parents in preds.items()}

    def heights(self) -> dict[str, int]:
        """s_x — ver `equations.curriculum_height`."""
        return curriculum_heights({d.name: d.unlocks for d in self.disciplines})

    def curriculum_periods(self) -> dict[str, int]:
        """O período de cada disciplina — ver `equations.curriculum_period`.

        Contagem a partir das raízes, usada nos gráficos. A matrícula
        garantida é a flag `entry`, não este número; a altura conta do outro
        extremo da mesma DAG.
        """
        return curriculum_periods(self.prerequisites_by_discipline())

    def reach(self) -> dict[str, int]:
        """d_x — ver `equations.curriculum_reach`."""
        return curriculum_reach({d.name: d.unlocks for d in self.disciplines})

    def entry_disciplines(self) -> list[str]:
        """Disciplinas de matrícula garantida, na ordem do cenário.

        Vem da flag `entry`, e **não** de não ter pré-requisito: a optativa
        também não tem e não é entrada. É este conjunto que dimensiona as
        validações de `students_per_period` e `max_hours` — o que a oferta
        precisa comportar é a coorte inteira entrando de uma vez.
        """
        return [d.name for d in self.disciplines if d.entry]

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
        """A oferta repartida entre as turmas do grupo.

        As primeiras `seats % classes` turmas levam uma vaga a mais, de modo
        que a soma devolve exatamente a oferta declarada.
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
        """A dificuldade da disciplina vezes o multiplicador da escada.

        Com os três níveis em 1 — o padrão — a escada some e toda turma herda
        a dificuldade do grupo. Ver `equations.class_difficulty`.
        """
        result: dict[str, float] = {}
        for discipline in self.disciplines:
            names = self.classes_of(discipline)
            ladder = class_difficulty(
                count=len(names), levels=self.class_difficulty_levels
            )
            for name, factor in zip(names, ladder):
                result[name] = discipline.difficulty * factor
        return result

    def class_exclusions(self) -> tuple[frozenset[str], ...]:
        """Os cliques de `X` (eq. 5): um por disciplina com mais de uma turma.

        Disciplina de turma única não gera clique — a restrição
        `Σ z ≤ 1` sobre um bem só já é a restrição binária dele.
        """
        return tuple(
            frozenset(names)
            for d in self.disciplines
            if len(names := self.classes_of(d)) > 1
        )

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


def horizon_for_lifecycle(*, entry_periods: int, max_residence: int) -> int:
    """|T| — o horizonte que esgota a população, dado o ciclo de vida dela.

    A última coorte entra no último período com ingresso e sai, concluída ou
    jubilada, ao fim da residência dela. Depois disso não resta ninguém para
    disputar, e simular além seria medir uma universidade vazia.

    O **menos um** é a sobreposição do primeiro período: a coorte que entra em
    t = 1 já gasta ali o primeiro período de residência dela. Sem ele o
    horizonte teria sempre um período final sem aluno nenhum.

    É função solta, e não método de `SimulationConfig`, porque a tela de
    configuração precisa do número **antes** de haver cenário — ela mostra o |T|
    enquanto o usuário mexe nos dois controles de que ele sai.
    """
    return entry_periods + max_residence - 1
