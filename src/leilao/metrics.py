"""Métricas de avaliação das alocações (Seção 7.3.3, eqs. 51-57)."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Metrics:
    """Métricas de um recorte (a universidade, uma geração ou um perfil) numa
    rodada/período."""

    students: int  # |A^(t)| do recorte
    allocated: int  # total de vagas obtidas pelo recorte
    allocations_per_student: float
    efficiency: float  # psi-barra — satisfação média, eq. (53)
    # Aproveitamento — carga horária obtida no período dividida por W_a, média
    # dos alunos medidos. É a contraparte em **carga** do psi, que é em
    # **utilidade**, e as duas se separam exatamente onde está a patologia que
    # importa: o aluno que concentra o lance, ganha uma disciplina que amava e
    # deixa o resto de W_a ocioso pontua psi alto e aproveitamento baixo.
    # Em [0, 1] por construção — a eq. (4) é restrição dos dois mecanismos.
    utilization: float
    fairness: float  # phi — índice de equidade de Jain, eq. (55)
    occupancy: float  # theta — fração das vagas ofertadas, eq. (54)
    # As duas têm a mesma forma — `demand_per_seat` — sobre conjuntos
    # diferentes: a escassez conta quem *poderia* cursar cada disciplina, a
    # concorrência quem de fato a pediu. Demanda potencial e demanda efetiva.
    scarcity: float  # escassez — elegíveis por vaga, média dos alunos
    contention: float  # concorrência — solicitantes por vaga, média dos alunos
    mean_grade_average: float  # N-barra — CR médio, eq. (56)
    correlation: float  # lambda — correlação de Pearson entre CR e satisfação, eq. (57)
    semestralization: float  # sigma-barra — semestralização média, ver `semestralization`


def satisfaction(*, utilities: dict[str, float], allocated: list[str]) -> float:
    """psi_a = soma_x u_{a,x} * z_{a,x} — eq. (51), em [0, 1]: a fração do
    **desejo total** do aluno naquele período que foi atendida.

    O denominador da eq. (51) é a linha inteira da matriz de utilidades, e ela
    **vale 1 por construção** — `behavior.draw_utilities` normaliza sobre a
    grade —, então a divisão some e psi é a soma simples das utilidades
    atendidas. A invariante está travada em
    `test_a_utility_row_sums_to_one_over_the_whole_curriculum`: se a
    normalização mudar, aquele teste quebra antes de psi passar a mentir.

    **Mudou em relação à versão anterior**, e vale saber qual você está lendo.
    Antes o denominador era `U_a` — a soma só sobre o conjunto **elegível**
    (eq. 43) —, e psi media "do que eu podia cursar, quanto cursei". Como U_a
    varia de ~0,002 a ~0,65 entre linhas, aquilo era uma razão de denominador
    móvel: maximizá-la premiava estar num período pobre de opções, o que a
    inviabilizava como função de aptidão num experimento evolutivo.

    As duas leituras são recuperáveis uma da outra enquanto `U_a` estiver no
    relatório: `psi_elegível = psi / U_a`. O que se perde com o denominador
    fixo é que **psi = 1 deixa de ser atingível** — ela exigiria cursar a grade
    inteira num período —, e o que se ganha é que a escala é a mesma para todo
    mundo, em todo período.

    `allocated` pode trazer disciplina fora de `utilities` (já aprovada, por
    exemplo); `.get(name, 0.0)` a ignora, que é o certo: ela não é desejo deste
    período.
    """
    return sum(utilities.get(name, 0.0) for name in allocated)


def demand_per_seat(*, demands: list[float]) -> float:
    """Média de (quantos querem) / (quantas vagas) sobre um conjunto de
    disciplinas — a razão candidato/vaga do vestibular, disciplina a disciplina.

    É a forma comum das duas métricas de pressão sobre a oferta, que só se
    distinguem por quem entra em "quantos querem" e por quais disciplinas entram
    no conjunto:

    - **escassez**: as disciplinas elegíveis para o aluno (as da grade que ele
      ainda não aprovou — eq. 42), contando quantos alunos são elegíveis a cada
      uma. É a demanda *potencial*, e quase não depende do mecanismo.
    - **concorrência**: as disciplinas em que ele deu lance no período,
      contando quantos deram lance em cada uma. É a demanda *efetiva*, e a razão
      entre as duas diz quanto da demanda potencial virou pedido.

    Contar quem quer cada disciplina — e não só somar as vagas ao alcance — é o
    que faz as duas enxergarem **sobreposição**: dois alunos diante dos mesmos
    60 lugares disputam o dobro de dois alunos diante de 60 lugares cada um, e
    uma medida que só olhasse o tamanho da oferta daria o mesmo nos dois casos.

    Por isso o recorte agrega por **média**, nunca por soma: a contagem de quem
    quer já traz a população dentro do valor de cada aluno, e somar sobre os
    alunos a contaria duas vezes — o número deixaria de se ler como alunos por
    vaga. Não há aditividade (um recorte não é parcela do global), e em troca
    recortes de tamanhos diferentes se comparam direto: uma geração com mais
    alunos não aparece mais apertada só por ser maior.

    Disciplinas sem vaga no período ficam de fora do conjunto pelo chamador —
    não são oferta, e dividir por zero não tem leitura. Conjunto vazio dá 0,
    tanto para quem não tem nada elegível quanto para quem não pediu nada.
    """
    if not demands:
        return 0.0
    return sum(demands) / len(demands)


def semestralization(*, approved_hours: int, max_hours: int, periods_completed: int) -> float:
    """sigma_a = H~_a / (W_a * idade_a) — o quanto o aluno andou na grade em
    relação ao máximo que poderia ter andado desde que ingressou.

    Não consta no anteprojeto: mede o atraso na progressão, que é justamente o
    que a matrícula por créditos deveria reduzir. Vale 1 para quem encheu a
    carga horária e foi aprovado em tudo desde o ingresso, e 0 para quem ainda
    não completou período nenhum (idade 0), caso em que a razão seria 0/0.

    `periods_completed` é a idade do aluno em períodos *no instante do
    recorte*: durante as rodadas de t ele completou t - t_a períodos, e ao fim
    de t completou t - t_a + 1 — que é exatamente o intervalo coberto pela
    carga horária aprovada do mesmo recorte.
    """
    if periods_completed <= 0 or max_hours <= 0:
        return 0.0
    return approved_hours / (max_hours * periods_completed)


def jain_index(values: list[float]) -> float:
    """phi = (soma v)^2 / (n * soma v^2) — eq. (55).

    Vale 1 quando todos têm a mesma satisfação e 1/n quando um único agente
    concentra tudo. A indeterminação 0/0 (ninguém alocado) é tomada como 0.
    """
    if not values:
        return 0.0
    square_sum = sum(value**2 for value in values)
    if square_sum == 0:
        return 0.0
    return sum(values) ** 2 / (len(values) * square_sum)


def pearson(xs: list[float], ys: list[float]) -> float:
    """Correlação de Pearson — eq. (57). Sem variância em algum dos lados, 0."""
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    variance_y = sum((y - mean_y) ** 2 for y in ys)
    if variance_x == 0 or variance_y == 0:
        return 0.0
    return covariance / math.sqrt(variance_x * variance_y)


def compute_metrics(
    *,
    satisfactions: list[float],
    utilizations: list[float],
    grade_averages: list[float],
    semestralizations: list[float],
    scarcities: list[float],
    contentions: list[float],
    allocated: int,
    total_seats: int,
) -> Metrics:
    """Agrega as métricas de um recorte de alunos.

    Para um recorte, `total_seats` continua sendo a oferta total da
    universidade: a ocupação vira então a fração das vagas ofertadas que foi
    para aquele grupo, e a soma dos grupos reproduz a eq. (54). A
    escassez e a concorrência **não** seguem essa convenção: são médias dos
    alunos, pelo motivo explicado em `demand_per_seat`.
    """
    count = len(satisfactions)
    return Metrics(
        students=count,
        allocated=allocated,
        allocations_per_student=allocated / count if count else 0.0,
        efficiency=sum(satisfactions) / count if count else 0.0,
        utilization=sum(utilizations) / count if count else 0.0,
        fairness=jain_index(satisfactions),
        occupancy=allocated / total_seats if total_seats else 0.0,
        scarcity=sum(scarcities) / count if count else 0.0,
        contention=sum(contentions) / count if count else 0.0,
        mean_grade_average=sum(grade_averages) / count if count else 0.0,
        correlation=pearson(grade_averages, satisfactions),
        semestralization=sum(semestralizations) / count if count else 0.0,
    )
