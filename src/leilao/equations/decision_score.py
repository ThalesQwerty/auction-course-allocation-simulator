"""O score com que o aluno decide, em cima da utilidade dele.

    score_x = ũ_x^β_u · oferta_x^β_v · aprovação_x^β_n

Ou, em logaritmo:

    ln score_x = β_u·ln ũ_x + β_v·ln oferta_x + β_n·ln aprovação_x

O modelo é **log-linear**: os três genes são expoentes sobre três sinais, os
efeitos ficam aditivos em log, e é exatamente isso que uma regressão sobre a
primeira coorte estima.

OS TRÊS EXPOENTES
-----------------

- **ũ** é a utilidade (`equations.utility`): a participação da
  disciplina no que o aluno ainda quer, somando 1 sobre o elegível. Nunca o
  interesse cru — a decisão só vê o que o histórico deixou de pé.
- **oferta** e **aprovação** são os sinais que a universidade publicou no
  período anterior (`equations.supply_index`, `equations.approval_index`),
  ambos em (0, 1) com 1/2 como ausência de informação.

Em **0 o gene ignora o sinal**, porque `x⁰ = 1` para todos — é a leitura
comum aos quatro genes do genoma. A linha de base é `β_u = 1` (pede
proporcional à utilidade) com os outros dois em 0, e nela as duas mochilas
decidem exatamente o que decidiriam sem comportamento nenhum.

| β | efeito |
| > 1 | concentra no sinal alto |
| 1 | proporcional ao sinal |
| 0 | ignora o sinal |
| < 0 | inverte: concentra no sinal baixo |

É uma regra de Luce temperada — o expoente é o inverso da temperatura.

POR QUE POTÊNCIA, E NÃO FATOR LINEAR
-------------------------------------

A forma anterior sobre os sinais era `1 + β·(2·índice − 1)`, e ela só fica
positiva com β preso em [−1, 1]: em β = 2 com índice 0 o fator vale −1, peso
negativo, que não significa nada. **Potência de base positiva é sempre
positiva**, então o gene aceita qualquer real e não existe fronteira para
tratar — nem clipe, nem reflexão, nem rejeição. No genoma inteiro sobra uma
só restrição, `alpha_u ≥ 0`, e ela é da reserva, não daqui.

`approval_index` garante base estritamente entre 0 e 1 pela suavização de
Laplace, então aquela potência nunca estoura. A utilidade e a oferta podem
zerar, e para elas a guarda de positividade vale.

Disciplina de utilidade não positiva não entra: o zero marca o inelegível.
A **ordem da saída** é a de `utilities`, que é a ordem da grade — é dela que
as duas mochilas tiram o desempate.

Substitui o score anterior, que era `u_rel^β · avanço^ρ`. O composto `avanço`
(chance de obter × chance de aprovar × carga × alcance transitivo) foi
desmontado: o alcance migrou para a utilidade (a redistribuição), as duas
chances viraram índices explícitos com um gene cada, e a carga foi
descartada — ela respondia por 1,8% da variância intralinha e não pagava um
gene.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

# A potência exige base estritamente positiva: expoente negativo sobre zero
# divide por zero. O menor positivo normalizado é a guarda mais barata que não
# muda conta nenhuma.
POSITIVE_GUARD = sys.float_info.min

# Ausência de informação nos dois sinais — ver `supply_index`.
NEUTRAL_SIGNAL = 0.5


@dataclass(frozen=True)
class Behavior:
    """O genoma: como um aluno traduz utilidade e sinais em mensagem.

    **É função, não matriz.** A utilidade é resorteada a cada período, então
    um genoma com um valor por par (aluno, disciplina) descreveria o que
    fazer com a linha deste semestre e não diria nada sobre a do próximo.

    Nos quatro, **0 quer dizer "ignora esse sinal"**. Três são expoentes; o
    quarto corta o conjunto de escolha.
    """

    # Viés de utilidade: o quanto o aluno exagera as diferenças de gosto.
    beta_u: float = 1.0
    # Viés de oferta: positivo foge de lotação, negativo caça vaga escassa.
    beta_v: float = 0.0
    # Viés de aprovação: positivo busca disciplina que aprova mais.
    beta_n: float = 0.0
    # Utilidade de reserva: a participação mínima para a disciplina entrar no
    # pedido. Na mesma unidade da utilidade — ver `admitted_set`.
    alpha_u: float = 0.0


NEUTRAL = Behavior()


@dataclass(frozen=True)
class Signals:
    """O que a universidade publicou no período anterior, por disciplina.

    É todo o conjunto de informação do aluno sobre a disciplina, e ele é
    deliberadamente pobre: nada de conhecer a dificuldade declarada nem a
    própria aptidão por matéria. O que existe é o que um aluno real lê — a
    folga e a taxa de aprovação do semestre passado.

    **Sem histórico (1º período) os dois índices valem 1/2**, e os dois genes
    caem no neutro sozinhos.
    """

    supply: dict[str, float] = field(default_factory=dict)
    approval: dict[str, float] = field(default_factory=dict)


def decision_scores(
    *,
    utilities: dict[str, float],
    behavior: Behavior = NEUTRAL,
    signals: Signals | None = None,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for name, utility in utilities.items():
        if utility <= 0.0:
            continue
        score = max(utility, POSITIVE_GUARD) ** behavior.beta_u
        if signals is not None:
            if behavior.beta_v:
                supply = signals.supply.get(name, NEUTRAL_SIGNAL)
                score *= max(supply, POSITIVE_GUARD) ** behavior.beta_v
            if behavior.beta_n:
                approval = signals.approval.get(name, NEUTRAL_SIGNAL)
                score *= max(approval, POSITIVE_GUARD) ** behavior.beta_n
        scores[name] = score
    return scores
