"""Notas e retorno de créditos (Seção 7.2.2).

As notas são um parâmetro de entrada, não um sorteio em tempo de execução: a
matriz n^0 com a nota que cada aluno tiraria na primeira tentativa de cada
disciplina é gerada junto com a população, a partir do perfil de aptidão de
cada um. Quando o aluno repete uma disciplina que reprovou, a nota sobe pelo
incremento de aprendizado **do perfil dele** (`AptitudeProfile.learning_gain`)
em relação à tentativa anterior, modelando aprendizado progressivo e garantindo
a monotonicidade da eq. (33) — e que ninguém fique preso numa disciplina para
sempre.
"""
from __future__ import annotations

import numpy as np

from .config import CreditReturnPolicy, Discipline
from .population import Student


def initial_grades(
    students: list[Student], disciplines: list[Discipline], rng: np.random.Generator
) -> dict[tuple[str, str], float]:
    """Matriz n^0: nota de primeira tentativa de cada par (aluno, disciplina).

    Cada aluno sorteia da normal do seu perfil de aptidão (`AptitudeProfile`),
    truncada em [0, 10] e arredondada a 0,1 — o domínio das notas da
    Seção 7.2.2. A distribuição não é fixada pelo anteprojeto; a normal é
    escolha de modelagem, e seus parâmetros são do cenário, não do código.
    """
    means = np.array([s.aptitude.mean for s in students])
    stddevs = np.array([s.aptitude.stddev for s in students])
    draws = rng.normal(
        means[:, None], stddevs[:, None], size=(len(students), len(disciplines))
    )
    draws = np.clip(np.round(draws, 1), 0.0, 10.0)
    return {
        (student.id, discipline.name): float(draws[i, j])
        for i, student in enumerate(students)
        for j, discipline in enumerate(disciplines)
    }


def grade_for_attempt(first_attempt_grade: float, attempt: int, gain: float) -> float:
    """Nota da `attempt`-ésima tentativa (1 = primeira).

    Cada recursada soma `gain` pontos (o Incremento de aprendizado do cenário) à
    tentativa anterior, saturando em 10.
    """
    if attempt < 1:
        raise ValueError("attempt deve ser >= 1")
    return min(10.0, round(first_attempt_grade + gain * (attempt - 1), 1))


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
