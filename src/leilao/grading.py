"""Notas e retorno de créditos (Seção 7.2.2).

A nota não sai de uma normal: ela sai da **aptidão** do aluno naquela
disciplina, elevada à demanda que a disciplina lhe faz.

    nota = round( 100 · a ^ ( D · ruído / (u_rel^w · t) ) ) / 10

- **a** é a aptidão, sorteada de uma Beta por par (aluno, disciplina) e
  **persistente**: é o traço, não a sorte. Com expoente 1 a nota *é* a
  aptidão, o que lhe dá leitura direta — "a nota que este aluno tiraria nesta
  disciplina, de dificuldade padrão, de primeira".
- **D** é a dificuldade da disciplina, e **t** a tentativa. Eles entram como a
  razão `D/t`, então **dificuldade 2 na segunda tentativa equivale a
  dificuldade 1 na primeira**: a dificuldade se lê em *quantas tentativas a
  disciplina custa* para render o que uma de dificuldade 1 rende de saída. É
  a lei de potência da prática, e substitui o incremento aditivo por recursada
  do modelo anterior, que não tinha respaldo nenhum.
- **u_rel** é a utilidade da disciplina para o aluno, em múltiplos da
  indiferença (`u · |disciplinas|`, que vale 1 quando ele é indiferente), e
  **w** é o quanto o interesse mexe no desempenho.
- **ruído** é um choque log-normal por tentativa, sem o qual a nota seria
  determinística dado `(a, D, u_rel, t)` — e aí recursar *garantiria* nota
  maior, revertendo uma decisão deliberada do modelo.

**Por que a forma de potência.** Ela tem história generativa, da mesma classe
da que sustenta a log-normal das utilidades: se a disciplina são E unidades
independentes e o aluno domina cada uma com probabilidade `a`, então `a^E` é a
chance de dominar todas. De quebra ela respeita os limites **por construção** —
`a^E` nunca sai de (0, 1) —, ao contrário da normal truncada, que empilhava
massa nas pontas sempre que a média chegava perto delas.

**O `w` não é opcional, e é por isso que ele é parâmetro de cenário.** O
acoplamento entre interesse e desempenho é a única peça da fórmula sem forma
justificada, e é a única que mexe no resultado principal: medido, `w = 0`
deixa a função de nota neutra entre os mecanismos (vão de 0% em aprovações) e
`w = 1` fabrica sozinha ~40% de vão a favor do leilão, antes de qualquer
alocação ter sido avaliada. Com `w` varrido e `w = 0` reportado ao lado, a
suposição deixa de ser ad-hoc e vira sensibilidade medida.

Nada é sorteado dentro do loop: a aptidão e os choques saem da seed na
inicialização, como exige a Seção 7.3.
"""
from __future__ import annotations

import math

import numpy as np

from .config import CreditReturnPolicy, Discipline, SimulationConfig
from .population import Student

# Abaixo disto a aptidão produziria 0,0 ou 1,0 exatos, e a nota degeneraria. O
# gerador de Beta devolve as duas pontas para parâmetros pequenos.
APTITUDE_GUARD = 1e-9


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


def draw_grade_noise(
    students: list[Student],
    disciplines: list[Discipline],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, str, int], float]:
    """O choque normal padrão de cada (aluno, disciplina, período) — o dia bom
    ou ruim.

    Sem ele a nota seria exata dado `(a, D, u_rel, t)`, e duas coisas
    quebrariam: a recursada voltaria a **garantir** nota maior, e a variância
    das notas passaria a vir só do resorteio da utilidade, de modo que o
    parâmetro de estabilidade da preferência controlaria também o acaso das
    notas — dois botões que devem ser independentes.

    Sai padrão (média 0, desvio 1); a escala é `config.grade_noise`, aplicada
    em `grade_for_attempt`. É a mesma separação do `ε` das utilidades: a régua
    fica num lugar só.
    """
    draws = rng.normal(
        0.0, 1.0, size=(len(students), len(disciplines), config.periods)
    )
    return {
        (student.id, discipline.name, period + 1): float(draws[i, j, period])
        for i, student in enumerate(students)
        for j, discipline in enumerate(disciplines)
        for period in range(config.periods)
    }


def grade_for_attempt(
    *,
    aptitude: float,
    difficulty: float,
    relative_utility: float,
    attempt: int,
    coupling: float,
    noise: float,
    noise_sigma: float,
) -> float:
    """A nota da `attempt`-ésima tentativa (1 = primeira) — eq. (33).

    `relative_utility` é `u_rel`, a utilidade em múltiplos da indiferença. Com
    `coupling = 0` ela some da conta (qualquer coisa elevada a 0 é 1) e a nota
    passa a depender só de aptidão, dificuldade e tentativa — que é o controle
    a reportar ao lado de qualquer resultado em conclusões.

    O arredondamento é `round`, e não `floor`: com `a < 1` e expoente positivo
    o produto nunca chega a 100, e truncando o teto da escala seria 9,9.
    """
    if attempt < 1:
        raise ValueError("attempt deve ser >= 1")
    a = min(1.0 - APTITUDE_GUARD, max(APTITUDE_GUARD, aptitude))
    weight = relative_utility**coupling if relative_utility > 0.0 else 1.0
    if weight <= 0.0:
        weight = 1.0
    exponent = difficulty * math.exp(noise_sigma * noise) / (weight * attempt)
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
