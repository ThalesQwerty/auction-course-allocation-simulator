"""Comportamento dos alunos: utilidades percebidas e lances (Seção 7.2.4).

A matriz de utilidades u^(t) é **parâmetro de entrada**, como as notas: todo o
sorteio acontece na inicialização, a partir da `seed`, para todos os alunos e
todos os períodos de uma vez (`draw_utilities`). Em tempo de execução,
`utility_matrix` só filtra e normaliza o que já foi sorteado, e os lances saem
deterministicamente das utilidades (eqs. 44-46) — nenhuma aleatoriedade dentro
do loop, como exige a Seção 7.3.

Isso importa para comparar cenários: se a utilidade fosse sorteada dentro do
loop, mexer numa vaga deslocaria o fluxo do gerador e mudaria as preferências
dos alunos, e a diferença entre dois cenários deixaria de ser atribuível ao
mecanismo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import SimulationConfig
from .population import Student

# U_a^(t) = soma das utilidades = fração do orçamento que o aluno se dispõe a
# gastar no período (eq. 43). O anteprojeto não fixa distribuição; usa-se uma
# uniforme nesta faixa, que mantém U_a em (0, 1] sem gerar alunos que mal
# gastam créditos.
SPEND_FRACTION_RANGE = (0.5, 1.0)


@dataclass(frozen=True)
class UtilityDraw:
    """O sorteio bruto de u_{a,·}^(t) para um par (aluno, período).

    Guarda um peso Gamma(1) por disciplina, em vez da Dirichlet já normalizada.
    A normalização fica para o tempo de execução porque o conjunto elegível
    muda conforme o aluno é aprovado e libera pré-requisitos — e, pela
    propriedade de agregação da Dirichlet, normalizar um subconjunto de pesos
    Gamma(1) dá exatamente uma Dirichlet(1) sobre esse subconjunto. O sorteio é
    fixo; o recorte é determinístico.
    """

    spend_fraction: float  # U_a^(t) — eq. (42)
    weights: dict[str, float]  # peso bruto de cada disciplina do cenário


def draw_utilities(
    students: list[Student], config: SimulationConfig, rng: np.random.Generator
) -> dict[tuple[str, int], UtilityDraw]:
    """Sorteia a matriz de utilidades inteira — todos os alunos, todos os
    períodos — na inicialização, a partir da seed."""
    periods = config.periods
    names = [d.name for d in config.disciplines]
    shape = (len(students), periods)
    spend = rng.uniform(*SPEND_FRACTION_RANGE, size=shape)
    # Gamma(1) = Exponencial(1): normalizado, dá Dirichlet(1) — eq. (41).
    weights = rng.standard_exponential(size=(*shape, len(names)))

    return {
        (student.id, period + 1): UtilityDraw(
            spend_fraction=float(spend[a, period]),
            weights={name: float(weights[a, period, j]) for j, name in enumerate(names)},
        )
        for a, student in enumerate(students)
        for period in range(periods)
    }


def utility_matrix(
    *, draw: UtilityDraw, student: Student, config: SimulationConfig
) -> dict[str, float]:
    """u_{a,·}^(t) a partir do sorteio já feito — eqs. (41)-(43).

    Função determinística: mesmo `draw` e mesmo estado do aluno, mesma saída.
    Retorna apenas as disciplinas com utilidade positiva — o conjunto elegível
    da eq. (42), que aqui é "não aprovada e com os pré-requisitos cumpridos".
    As já aprovadas e as ainda bloqueadas têm utilidade zero por construção
    (Seção 7.2.4) e simplesmente não aparecem.

    Sem grupos de grade: como toda disciplina é obrigatória, a hierarquia
    obrigatórias > optativas > livres das eqs. (47)-(48) não tem o que ordenar,
    e a massa U_a se reparte numa Dirichlet(1) única sobre o elegível. Quem
    ordena a grade agora é o pré-requisito, que diz *quando* a disciplina entra
    no conjunto, não quanto ela vale dentro dele.

    **Zerar fora do elegível torna a escala de U_a redundante.** Como a soma das
    utilidades é exatamente U_a (eq. 43), a satisfação da eq. (51) divide por
    ela e o fator se cancela; os lances das eqs. (44)-(46) usam só razões entre
    utilidades, que também o cancelam. O `spend_fraction` continua multiplicando
    aqui porque é ele que faz valer a eq. (43) — mas, depois dela, U_a só pesa
    de fato como fração do orçamento em `compute_bids`. Em troca, psi_a passa a
    ser a fração do que o aluno **podia** cursar: antes a utilidade se espalhava
    por disciplinas fora do alcance dele, e psi = 1 era inatingível por
    construção.

    O **perfil de afinidade** entra como um expoente sobre os pesos antes da
    normalização. Expoente > 1 afasta as utilidades entre si (o aluno
    concentrado), < 1 as aproxima (o disperso), e 1 não muda nada. Elevar o peso
    bruto e normalizar depois dá exatamente o mesmo que elevar a utilidade já
    normalizada e renormalizar — w^e / soma(w^e) não depende da escala de w —,
    então a conta é feita de uma vez só, no peso.
    """
    eligible = config.eligible_disciplines(student.approved(config.min_grade))
    if not eligible:
        return {}

    # Normalizar os pesos Gamma(1) do conjunto reparte U_a sem privilegiar
    # nenhuma disciplina a priori — valores contínuos e distintos, eq. (41).
    exponent = student.affinity.exponent
    weights = {name: draw.weights[name] ** exponent for name in eligible}
    # A divisão pelo somatório é o que mantém a eq. (43) valendo depois da
    # distorção: sem ela o expoente mandaria U_a para qualquer lado.
    total = sum(weights.values())
    return {
        name: draw.spend_fraction * weight / total for name, weight in weights.items()
    }


def compute_bids(
    *,
    utilities: dict[str, float],
    available: list[str],
    budget: int,
    spend_fraction: float,
) -> dict[str, int]:
    """Converte utilidades em lances inteiros numa rodada — eqs. (44)-(46).

    `available` é B_a^(t,r) (disciplinas em que ainda é possível obter vaga) e
    `spend_fraction` é U_a^(t) (eq. 42), calculado sobre o período inteiro e,
    portanto, constante entre as rodadas.
    """
    pool = [name for name in available if utilities.get(name, 0.0) > 0.0]
    if not pool or budget <= 0:
        return {}

    total_utility = sum(utilities[name] for name in pool)
    to_spend = budget * spend_fraction

    # eq. (44): lances preliminares proporcionais à utilidade, truncados.
    preliminary = {
        name: math.floor(to_spend * utilities[name] / total_utility) for name in pool
    }
    # eq. (45): o truncamento sobra créditos...
    leftover = math.floor(to_spend) - sum(preliminary.values())
    # ...distribuídos um a um em ordem decrescente de preferência — eq. (46),
    # em que u^ é a utilidade ordinal (1 = disciplina preferida da rodada).
    ordinal = sorted(pool, key=lambda name: utilities[name], reverse=True)
    for name in ordinal[:leftover]:
        preliminary[name] += 1

    # Lance nulo não é demanda — eq. (18).
    return {name: credits for name, credits in preliminary.items() if credits > 0}
