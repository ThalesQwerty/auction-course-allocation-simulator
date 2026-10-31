"""O que uma simulação publica: os registros do relatório.

Só estrutura — nenhuma conta. A regra que atravessa todos eles é a mesma:
**ausência é `None`, nunca 0,0**. Recorte sem aluno, grandeza de crédito num
mecanismo sem crédito, preço de uma disciplina que nunca esteve no mercado —
em todos, zero se leria como um fato medido ("ninguém ficou satisfeito",
"ninguém gastou", "de graça") em vez da ausência que é. Nos gráficos o ponto
some; nas tabelas aparece um traço.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..metrics import Metrics

# `RequestRecord.won_round` quando a vaga não veio de rodada nenhuma: é a
# matrícula garantida do ingressante, concedida antes de o leilão abrir.
GUARANTEED_ROUND = 0


@dataclass(frozen=True)
class PriceStats:
    """Dispersão de π_x (eq. 24) entre as disciplinas num instante.

    O preço não é grandeza de aluno nem de geração: é do mercado. O que se lê
    dele ao longo do tempo é a faixa — a mais cara, a média e a mais barata —,
    porque uma média sozinha esconde se o crédito está concentrado em poucas
    disputas ou espalhado por todas.
    """

    min: float
    mean: float
    max: float

    @classmethod
    def of(cls, prices: list[int] | list[float]) -> "PriceStats | None":
        if not prices:
            return None
        return cls(min=min(prices), mean=sum(prices) / len(prices), max=max(prices))


@dataclass(frozen=True)
class GroupSnapshot:
    """Um recorte de alunos num instante — a unidade dos gráficos.

    **O calouro conta como gente, não como dado.** Quem ingressa no período
    não disputou nada: recebeu um pacote fixo — as disciplinas de entrada —,
    igual para todo mundo e independente da preferência. Entra, portanto, com
    CR = 0,000 sempre, e com um ψ que não diz nada sobre alocação: ele mede só
    o quanto a preferência sorteada por acaso coincidiu com o pacote.

    Sem optativa no cenário o pacote *é* o conjunto elegível inteiro e o ψ do
    calouro vale 1,000 sem exceção. Com optativa, não: ela é elegível desde o
    ingresso e fica fora da garantia, então o ψ dele cai para a faixa de 0,2,
    variando com o sorteio. A regra não muda por isso; o motivo muda, de
    "constante por construção" para "ruído por construção".

    No preset Computação ele é ~11% das linhas aluno-período e sozinho
    invertia o sinal da correlação da eq. (57). Por isso fica de fora de
    **toda média por aluno** e permanece nas **contagens de pessoas**. Daí
    `metrics.students ≤ active`, e o primeiro período de uma simulação não ter
    métrica nenhuma: ali todo mundo é calouro.
    """

    # `None` na universidade inteira; o período de ingresso (t_a) por geração.
    # É texto porque o eixo é genérico — um recorte novo entra como outra
    # lista de `GroupSnapshot`, sem mexer na estrutura.
    group: str | None
    metrics: Metrics | None
    active: int  # |A^(t)| do recorte no início do período
    # Alunos do recorte que já ingressaram, tenham concluído ou não. **Não** é
    # `active + graduated`: quem se forma ao fim de t conta nos dois lados
    # dessa soma, porque disputou o período inteiro antes de sair. É sobre
    # este número que se tira a fração de formados.
    population: int
    graduated: int  # concluintes acumulados até aqui
    # Jubilados acumulados até aqui. Com `graduated`, reparte `population` em
    # três: quem saiu por cima, quem saiu por baixo e quem ainda disputa. As
    # duas frações que a tela mostra saem daqui, e somam 1 só no fim do
    # horizonte — antes dele o resto ainda está em curso.
    dismissed: int
    mean_credits: float | None  # saldo médio ao fim do recorte
    mean_approved_hours: float | None
    # Oferta de crédito do início do período (C_a^(t,1), antes de qualquer
    # lance) — distinta de `mean_credits`, que é o que sobrou.
    credits_per_student: float | None
    credits_per_seat: float | None
    # Créditos apostados no período por aluno, somando as rodadas. **Pode
    # passar do orçamento**: lance perdido não consome nada (eq. 25), então o
    # crédito que não virou vaga volta a ser apostado na rodada seguinte. A
    # matrícula garantida entra pelo valor que o sistema lançou na conta, para
    # que lance e gasto fiquem na mesma régua.
    mean_bids: float | None
    # Σγ do período (eq. 34) por aluno. Só existe no recorte de fim de
    # período: em plena rodada as notas ainda não saíram.
    mean_credit_return: float | None


@dataclass(frozen=True)
class RoundReport:
    """Um ponto da série: uma rodada, ou o agregado de um período (`round` 0)."""

    period: int
    round: int
    overall: GroupSnapshot
    # O mesmo instante por geração. Só as que já ingressaram, então a série de
    # uma geração começa no período do seu t_a — e o aluno fica na mesma
    # geração do início ao fim, que é o que torna essa leitura mais estável
    # que a idade. O recorte **particiona** a população do agregado: somá-lo
    # reproduz `overall`.
    by_cohort: list[GroupSnapshot]
    prices: PriceStats | None


@dataclass(frozen=True)
class DisciplineSnapshot:
    name: str
    curriculum_period: int
    hours: int  # w_x — repetido para o recorte por carga horária
    seats: int  # q_x no início do período
    filled: int  # vagas preenchidas, contando as garantidas
    # Vagas entregues à matrícula garantida, antes do leilão. Só é diferente
    # de zero nas disciplinas de entrada — e é o que explica uma disciplina
    # chegar à primeira rodada já quase cheia.
    granted: int
    # Quantos pediram no período: deram lance em alguma rodada ou a receberam
    # na matrícula garantida. Dividido por `seats` dá a concorrência dela.
    requests: int
    mean_price: float | None
    approvals: int


@dataclass(frozen=True)
class PeriodReport:
    period: int
    rounds: list[RoundReport]
    aggregate: RoundReport
    disciplines: list[DisciplineSnapshot]
    graduated_now: int
    dismissed_now: int


@dataclass(frozen=True)
class RequestRecord:
    """O que aconteceu com uma disciplina que o aluno quis num período.

    Registra **toda** disciplina de utilidade positiva, inclusive as em que
    ele nem chegou a dar lance — `bids` todo zero significa que ela saiu de
    B_a^(t,r) antes (sem vaga, sem carga ou sem orçamento), e é justamente o
    caso que costuma explicar um resultado inesperado.
    """

    discipline: str
    utility: float  # u_{a,x}^(t)
    bids: list[int]  # c_{a,x}^(t,r) por rodada; 0 = não pediu
    won_round: int | None  # `None` = recusada; `GUARANTEED_ROUND` = garantida
    paid: int  # eq. (27)
    attempt: int | None
    # Nota **desta** tentativa (eq. 33). Pode ser menor que a de uma anterior.
    # O que não regride é `Student.grades`, a maior já obtida, que alimenta o
    # CR — e é essa diferença que a tela individual existe para mostrar.
    grade: float | None
    approved: bool
    returned: int  # γ_{a,x}^(t) — eq. (34)


@dataclass(frozen=True)
class StudentPeriodRecord:
    """A linha do histórico de um aluno num período letivo.

    As quatro grandezas de crédito fecham a conta da eq. (36):
    `credits_end = credits_start − credits_spent + Γ_min + credits_returned`.
    """

    period: int
    credits_start: int
    credits_spent: int
    credits_returned: int  # Σγ, sem o Γ_min
    credits_end: int
    satisfaction: float  # ψ_a^(t)
    grade_average: float  # N_a no início do período
    approved_hours: int  # acumulado ao fim do período
    enrolled_hours: int  # carga obtida neste período
    requests: list[RequestRecord]
    graduated: bool


@dataclass(frozen=True)
class StudentHistory:
    """Só os períodos em que o aluno participou da matrícula: quem já se
    formou simplesmente não aparece dali em diante."""

    student_id: str
    periods: list[StudentPeriodRecord]


@dataclass(frozen=True)
class StudentSummary:
    id: str
    name: str
    entry_period: int  # t_a
    grade_average: float  # N_a
    approved_hours: int
    hours_to_graduate: int  # S — igual para todos
    credits: int
    enrollments: int
    approvals: int
    mean_satisfaction: float
    graduated_at: int | None
    dismissed_at: int | None


@dataclass(frozen=True)
class SimulationResult:
    periods: list[PeriodReport] = field(default_factory=list)
    students: list[StudentSummary] = field(default_factory=list)
    histories: list[StudentHistory] = field(default_factory=list)
    disciplines: list[str] = field(default_factory=list)
    curriculum_periods: dict[str, int] = field(default_factory=dict)
    # As duas distribuições de **entrada**, como histogramas. Saem das
    # matrizes que esta execução de fato usou, e não de uma amostra à parte.
    utility_distribution: list[float] = field(default_factory=list)
    grade_distribution: list[float] = field(default_factory=list)
