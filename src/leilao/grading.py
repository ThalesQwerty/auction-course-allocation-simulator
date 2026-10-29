"""Notas e retorno de créditos (Seção 7.2.2).

A nota não sai de uma normal: ela sai da **aptidão** do aluno naquela
disciplina, elevada à demanda que a disciplina lhe faz.

    nota = round( 100 · a ^ expoente ) / 10

        expoente   = D / ( u_rel ^ ganho_utilidade · tentativas )
        tentativas = 1 + ganho_recursada · (t - 1)

- **a** é a aptidão, sorteada de uma Beta por par (aluno, disciplina) e
  **persistente**: é o traço, não a sorte. Com expoente 1 a nota *é* a
  aptidão, o que lhe dá leitura direta — "a nota que este aluno tiraria nesta
  disciplina, de dificuldade padrão, de primeira".
- **D** é a dificuldade da disciplina: o quanto ela exige, em múltiplos da
  disciplina padrão.
- **u_rel** é a utilidade da disciplina para o aluno, em múltiplos da
  indiferença (`u · |disciplinas|`, que vale 1 quando ele é indiferente).
- **t** é a tentativa, e `tentativas` é a tentativa *efetiva*: quanto cada
  repetição acrescenta é o ganho por recursada.

**Os dois ganhos dividem o mesmo lugar** — o denominador do expoente — e por
isso se leem juntos: cada um diz o quanto um fator desconta da demanda que a
disciplina faz. Com os dois em 1, o expoente é `D/t`, então **dificuldade 2 na
segunda tentativa equivale a dificuldade 1 na primeira**, e a dificuldade se lê
em *quantas tentativas a disciplina custa* para render o que uma de dificuldade
1 rende de saída. É a lei de potência da prática.

**O ganho por recursada substituiu um choque log-normal por tentativa** em
29/10/2026. O choque existia para que recursar não *garantisse* nota maior, mas
medido ele não entregava isso: com desvio 0,25 e `D = 1,2`, a segunda tentativa
piorava a nota em 0,8% dos casos. O que ele de fato fazia era atrasar o cenário
— ~5% menos formados em **todos** os braços, sem mexer em psi, aproveitamento,
fidelidade nem phi — e borrar a leitura de que a nota *é* a aptidão em
dificuldade 1 e primeira tentativa, porque o choque também caía sobre ela. No
lugar dele ficou um coeficiente, que diz a mesma coisa sem sorteio.

**Ganho por recursada 0 prende o aluno para sempre**: a nota é determinística,
de modo que quem reprova uma vez reprova sempre, e sem jubilamento ele ocupa
vaga até o horizonte acabar. É permitido de propósito — é um extremo que se
pode querer medir.

**Por que a forma de potência.** Ela tem história generativa, da mesma classe
da que sustenta a log-normal das utilidades: se a disciplina são E unidades
independentes e o aluno domina cada uma com probabilidade `a`, então `a^E` é a
chance de dominar todas. De quebra ela respeita os limites **por construção** —
`a^E` nunca sai de (0, 1) —, ao contrário da normal truncada, que empilhava
massa nas pontas sempre que a média chegava perto delas.

**O ganho por utilidade não é opcional, e é por isso que ele é parâmetro de
cenário.** Que a utilidade mexa no desempenho é a única peça da fórmula sem
forma justificada, e é a única que mexe no resultado principal: medido, ganho
zero deixa a função de nota neutra entre os mecanismos (vão de 0% em
aprovações) e ganho 1 fabrica sozinho ~40% de vão a favor do leilão, antes de
qualquer alocação ter sido avaliada. Com o ganho reportado ao lado, a suposição
deixa de ser ad-hoc e vira sensibilidade medida.

Nada é sorteado dentro do loop: a aptidão sai da seed na inicialização, como
exige a Seção 7.3.
"""
from __future__ import annotations

import numpy as np

from .config import CreditReturnPolicy, Discipline, SimulationConfig
from .population import Student

# Abaixo disto a aptidão produziria 0,0 ou 1,0 exatos, e a nota degeneraria. O
# gerador de Beta devolve as duas pontas para parâmetros pequenos.
APTITUDE_GUARD = 1e-9


def beta_shape(*, mean: float, concentration: float) -> tuple[float, float]:
    """Os dois **parâmetros de forma** da Beta, a partir da média e da
    concentração com que a interface descreve a população.

        forma_1 = média · concentração
        forma_2 = (1 - média) · concentração

    A Beta não tem locação nem escala — o suporte é fixo em (0, 1) —, de modo
    que os dois números que ela pede são forma pura, e forma pura não se lê:
    ninguém olha `(4, 2)` e enxerga "média 0,67, moderadamente espalhada". A
    interface edita as duas grandezas que *se* leem e a conversão acontece
    aqui, na entrada do modelo; `SimulationConfig` guarda a forma, que é o que
    o sorteio pede.

    As duas grandezas respondem a perguntas independentes, e as duas importam.
    A **média** calibra o cenário contra a taxa de aprovação — é ela que decide
    se a universidade forma 30% ou 80%. A **concentração** diz quão apertada a
    população fica em torno dela: mesma média com concentração maior é uma
    população mais homogênea, e homogeneidade demais apaga a ordenação por CR,
    que precisa de dispersão para ter o que ordenar.
    """
    if not 0.0 < mean < 1.0:
        raise ValueError("a média da aptidão deve estar em (0, 1)")
    if concentration <= 0.0:
        raise ValueError("a concentração da aptidão deve ser > 0")
    return mean * concentration, (1.0 - mean) * concentration


def draw_aptitudes(
    students: list[Student],
    disciplines: list[Discipline],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, str], float]:
    """a_{a,x} — a aptidão de cada par (aluno, disciplina), sorteada **uma vez**
    na inicialização.

    É traço, não sorte: ela não é resorteada por período nem por tentativa, e é
    o que faz "este aluno é bom em matemática e ruim em escrita" significar
    alguma coisa. A Beta é a família natural porque aptidão é uma fração
    limitada — que parcela do máximo esta pessoa alcança —, e ela já nasce em
    (0, 1) sem truncagem.
    """
    draws = rng.beta(
        config.aptitude_alpha,
        config.aptitude_beta,
        size=(len(students), len(disciplines)),
    )
    draws = np.clip(draws, APTITUDE_GUARD, 1.0 - APTITUDE_GUARD)
    return {
        (student.id, discipline.name): float(draws[i, j])
        for i, student in enumerate(students)
        for j, discipline in enumerate(disciplines)
    }


def grade_for_attempt(
    *,
    aptitude: float,
    difficulty: float,
    relative_utility: float,
    attempt: int,
    utility_gain: float,
    retake_gain: float,
) -> float:
    """A nota da `attempt`-ésima tentativa (1 = primeira) — eq. (33).

    Os dois ganhos ocupam o mesmo lugar, o denominador do expoente. O **ganho
    por utilidade** é expoente sobre `u_rel`: em 0 a utilidade some da conta
    (qualquer coisa elevada a 0 é 1) e a nota passa a depender só de aptidão,
    dificuldade e tentativa, que é o controle a reportar ao lado de qualquer
    resultado em conclusões. O **ganho por recursada** diz quanta tentativa
    efetiva cada repetição acrescenta: em 1 o denominador é o próprio `t`.

    O arredondamento é `round`, e não `floor`: com `a < 1` e expoente positivo
    o produto nunca chega a 100, e truncando o teto da escala seria 9,9.
    """
    if attempt < 1:
        raise ValueError("attempt deve ser >= 1")
    a = min(1.0 - APTITUDE_GUARD, max(APTITUDE_GUARD, aptitude))
    utility = relative_utility**utility_gain if relative_utility > 0.0 else 1.0
    if utility <= 0.0:
        utility = 1.0
    attempts = 1.0 + retake_gain * (attempt - 1)
    if attempts <= 0.0:
        raise ValueError("o ganho por recursada zerou as tentativas efetivas")
    exponent = difficulty / (utility * attempts)
    return round(100.0 * a**exponent) / 10.0


# Faixas do histograma de notas — as mesmas dez das utilidades, de modo que os
# dois gráficos se leiam do mesmo jeito. Aqui elas também caem bem na escala:
# as divisas são 0, 1, 2 ... 10, que é como se lê uma nota.
DISTRIBUTION_BINS = 10


def grade_distribution(
    grades: list[float],
    bins: int = DISTRIBUTION_BINS,
) -> list[float]:
    """Como as notas de **primeira tentativa** se distribuem, em `bins` faixas
    de mesma largura sobre [0, 10].

    Recebe as notas já calculadas, e não o sorteio cru: com a nota saindo de
    uma potência da aptidão, não há mais "valor cru" que se leia como nota. O
    que o gráfico mostra é o que a fórmula de fato produz.
    """
    if not grades:
        return [0.0] * bins
    counts = [0] * bins
    for grade in grades:
        index = min(bins - 1, max(0, int(grade / 10.0 * bins)))
        counts[index] += 1
    total = len(grades)
    return [count / total for count in counts]


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
