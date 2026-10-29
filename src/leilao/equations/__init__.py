"""Uma fórmula por arquivo, uma função pura por fórmula.

Cada módulo deste pacote implementa **uma** conta do modelo. A docstring traz
a fórmula e o porquê da forma escolhida; a função é determinística e não toca
em estado. O resto do motor monta o laço, guarda o resultado e decide quando
chamar — a conta mora aqui, para que revisá-la seja abrir um arquivo.

O recorte é o **código**, não o anteprojeto: há conta aqui que ele não prevê,
e previsão dele que o código substituiu. Onde a correspondência existe, o
número está na primeira linha da docstring.

ÍNDICE
------

Uma rodada de leilão (Seção 7.1)

    tie_break_factor          α̂ = (|A| − α)/|A|                  eq. (20)
    rectified_bias            β̂ = β − β_min                      eq. (21)
    stochastic_perturbation   ε ∈ (0, 1/(|A|²·|B|)), distintos    7.1.2
    final_preference          p = c + β̂ + α̂ + ε                   eq. (22)
    greedy_allocation         varredura por preferência           —
    market_price              π = maior lance perdedor            eq. (24)
    credit_consumption        δ = min(c, π)                       eq. (25)
    remaining_seats           q − Σz                              eq. (13)
    remaining_capacity        W − Σ w·z                           eq. (14)
    remaining_budget          C − Δ                               eq. (27)

    A alocação exata por PLI não tem forma fechada e vive em `wdp_solver`;
    o objetivo Σ p·z (eq. 8) é montado lá, simbolicamente.

Decisão do aluno (Seção 7.2.4)

    decision_score            u_rel^β · avanço^ρ                  —
    available_goods           B_a^(t,r)                           eq. (15)
    concave_bids              mochila côncava do lance        substitui 44-46
    request_set               D_a^(t,r), tudo em ordem            eq. (50)
    serial_dictatorship       ditadura serial por CR              7.3.1

Preferência e grade

    preference_split          √s·permanente + √(1−s)·sazonal      —
    utility_row               deslocamento por altura + norma     eq. (41)
    eligible_set              não aprovada, liberada, X em aberto eq. (42)
    reachable_utility         U_a = Σ_elegível u                  eq. (43)
    curriculum_height         s_x, a cadeia à frente          substitui 38
    curriculum_period         o período induzido dos pré-req.     —
    curriculum_reach          quantas destrava, transitivamente   —

Notas, créditos e saída (Seção 7.2.2)

    aptitude_shape            forma da Beta a partir de média     —
    grade_for_attempt         n = round(100·a^E)/10               eq. (33)
    credit_return             γ = f_γ(preço, nota)                eq. (34)
    guaranteed_share          ⌊C / |entrada|⌋                     —
    period_return             Γ = Γ_min + Σγ                      eq. (35)
    next_budget               C − gasto + Γ, ou Γ_min          eqs. (36)-(37)
    graduation                obrigatórias ⊆ aprovadas ∧ X        eq. (40)
    grade_average             N_a ponderado por carga             eq. (49)

Sinais publicados

    win_estimate              P̂(obter) = min(1, q/n)              —
    pass_rate_estimate        P̂(aprovar) = aprovações/matrículas  —

Métricas de um recorte (Seção 7.3.3)

    satisfaction              ψ_a = Σ u·z                         eq. (51)
    mean_satisfaction         ψ̄                                   eq. (53)
    occupancy                 θ = alocadas/ofertadas              eq. (54)
    jain_index                φ de Jain                           eq. (55)
    mean_grade_average        N̄                                   eq. (56)
    pearson_correlation       λ de Pearson                        eq. (57)
    utilization               carga obtida / W_a                  —
    message_fidelity          cosseno(mensagem, preferência)      —
    semestralization          σ_a = H̃/(W·idade)                   —
    demand_per_seat           escassez e concorrência             —
    credits_per_seat          oferta de crédito / vagas           —
    mean_price                π̄ sobre as rodadas com vaga         —

Agregação de uma execução (Seção 7.3)

    weighted_mean             média ponderada pelos medidos       —
    time_to_graduate          períodos do ingresso ao diploma     —
    grade_histogram           faixas de [0, 10]                   —
    utility_histogram         faixas da linha, escala por linha   —

Não implementadas, e por quê

    eq. (31)   t_a: o ingresso é escalonado por construção, em `population`
    eqs. (47)-(48)  grupos da grade: toda obrigatória pesa igual, não há o
                    que hierarquizar
"""
from __future__ import annotations

from .aptitude_shape import beta_shape
from .available_goods import available_goods
from .concave_bids import concave_bids
from .credit_consumption import consumption
from .credit_return import credit_return
from .credits_per_seat import credits_per_seat
from .curriculum_height import curriculum_heights
from .curriculum_period import curriculum_periods
from .curriculum_reach import curriculum_reach
from .decision_score import NEUTRAL, Behavior, Signals, decision_scores
from .demand_per_seat import demand_per_seat
from .eligible_set import eligible_set
from .final_preference import final_preference
from .grade_average import grade_average
from .grade_for_attempt import APTITUDE_GUARD, grade_for_attempt
from .grade_histogram import grade_histogram
from .graduation import has_graduated
from .greedy_allocation import greedy_allocation
from .guaranteed_share import guaranteed_share
from .jain_index import jain_index
from .market_price import market_prices
from .mean_grade_average import mean_grade_average
from .mean_price import mean_price
from .mean_satisfaction import mean_satisfaction
from .message_fidelity import message_fidelity
from .next_budget import next_budget
from .occupancy import occupancy
from .pass_rate_estimate import pass_rate_estimate
from .pearson_correlation import pearson
from .period_return import period_return
from .preference_split import preference_split
from .reachable_utility import reachable_utility
from .rectified_bias import rectify_bias
from .remaining_budget import remaining_budget
from .remaining_capacity import remaining_capacity
from .remaining_seats import remaining_seats
from .request_set import request_set
from .satisfaction import satisfaction
from .semestralization import semestralization
from .serial_dictatorship import serial_dictatorship
from .stochastic_perturbation import stochastic_perturbations
from .tie_break_factor import tie_break_factor
from .time_to_graduate import time_to_graduate
from .utility_histogram import utility_histogram
from .utility_row import normalize_with_height_shift
from .utilization import utilization
from .weighted_mean import weighted_mean
from .win_estimate import win_estimate

__all__ = [
    "APTITUDE_GUARD",
    "Behavior",
    "NEUTRAL",
    "Signals",
    "available_goods",
    "beta_shape",
    "concave_bids",
    "consumption",
    "credit_return",
    "credits_per_seat",
    "curriculum_heights",
    "curriculum_periods",
    "curriculum_reach",
    "decision_scores",
    "demand_per_seat",
    "eligible_set",
    "final_preference",
    "grade_average",
    "grade_for_attempt",
    "grade_histogram",
    "greedy_allocation",
    "guaranteed_share",
    "has_graduated",
    "jain_index",
    "market_prices",
    "mean_grade_average",
    "mean_price",
    "mean_satisfaction",
    "message_fidelity",
    "next_budget",
    "normalize_with_height_shift",
    "occupancy",
    "pass_rate_estimate",
    "pearson",
    "period_return",
    "preference_split",
    "reachable_utility",
    "rectify_bias",
    "remaining_budget",
    "remaining_capacity",
    "remaining_seats",
    "request_set",
    "satisfaction",
    "semestralization",
    "serial_dictatorship",
    "stochastic_perturbations",
    "tie_break_factor",
    "time_to_graduate",
    "utility_histogram",
    "utilization",
    "weighted_mean",
    "win_estimate",
]
