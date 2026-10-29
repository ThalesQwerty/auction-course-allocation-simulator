"""O score com que o aluno decide, em cima da linha de utilidades.

    ln score_x = β · ln u_rel_x + ρ · ln[ P̂(obter)_x · P̂(aprovar)_x · w_x · (1 + d_x) ]

Ou, sem logaritmo:

    score_x = u_rel_x^β · (avanço esperado_x)^ρ

- **u_rel** é a utilidade em múltiplos da indiferença (`u · |disciplinas|`), a
  mesma normalização da fórmula de nota: vale 1 quando o aluno é indiferente,
  e sobrevive ao catálogo crescer.
- **β** (`concentration`) é o viés de satisfação: o quanto o aluno exagera as
  diferenças de gosto. Em 1 o score **é** `u_rel`; acima de 1 concentra; perto
  de 0 achata até a mensagem virar um conjunto, que é exatamente o que a linha
  de base por CR envia.
- **ρ** (`progress`) é o viés de progresso, sobre o *avanço esperado* da
  vaga — uma grandeza só: chance de obter, vezes chance de aprovar, vezes
  carga, vezes um mais o que ela destrava. Um coeficiente sobre o produto é
  melhor que quatro sobre as partes, e deixa as partes se correlacionarem sem
  criar crista entre genes.

Com os valores neutros (β = 1, ρ = 0) o score é proporcional à utilidade, e
as duas mochilas decidem exatamente o que decidiriam sem comportamento
nenhum. **É assim que a população roda hoje.**

Disciplina de utilidade não positiva não entra: o zero marca o inelegível.
A **ordem da saída** é a de `utilities`, que é a ordem da grade — é dela que
as duas mochilas tiram o desempate.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Behavior:
    """Como um aluno traduz utilidade em mensagem.

    **É função, não matriz.** A utilidade é resorteada a cada período, então
    um genoma com um valor por par (aluno, disciplina) descreveria o que fazer
    com a linha deste semestre e não diria nada sobre a do próximo.
    """

    concentration: float = 1.0
    progress: float = 0.0
    # Utilidade de reserva: o aluno compra crédito enquanto o ganho marginal
    # exceder `r`, e deixa de pedir o que vale menos que ela. Numa regra só
    # decide *quais* disciplinas entram, *quantos* créditos cada uma recebe e
    # *quanto* se gasta no total — o orçamento vira teto, não meta.
    reserve: float = 0.0


NEUTRAL = Behavior()


@dataclass(frozen=True)
class Signals:
    """O que a universidade publicou no período anterior, por disciplina.

    É todo o conjunto de informação do aluno, e ele é deliberadamente pobre:
    nada de conhecer a dificuldade declarada nem a própria aptidão por
    matéria. O que existe é o que um aluno real lê — a concorrência e a taxa
    de aprovação do semestre passado — mais o próprio histórico.

    **Sem histórico (1º período) os dois P̂ valem 1**, e o termo de progresso
    cai no neutro sozinho.
    """

    win: dict[str, float] = field(default_factory=dict)
    pass_rate: dict[str, float] = field(default_factory=dict)
    hours: dict[str, int] = field(default_factory=dict)
    reach: dict[str, int] = field(default_factory=dict)


# O produto do avanço esperado nunca chega a zero com sinais plausíveis, mas
# elevá-lo a um expoente exige que ele seja estritamente positivo. O menor
# positivo normalizado é a guarda mais barata que não muda conta nenhuma.
POSITIVE_GUARD = sys.float_info.min


def expected_advance(name: str, signals: Signals) -> float:
    """P̂(obter) · P̂(aprovar) · w_x · (1 + d_x) — o avanço esperado da vaga."""
    return (
        signals.win.get(name, 1.0)
        * signals.pass_rate.get(name, 1.0)
        * max(signals.hours.get(name, 1), 1)
        * (1 + signals.reach.get(name, 0))
    )


def decision_scores(
    *,
    utilities: dict[str, float],
    behavior: Behavior = NEUTRAL,
    signals: Signals | None = None,
    catalogue: int = 0,
) -> dict[str, float]:
    scale = catalogue or len(utilities) or 1
    scores: dict[str, float] = {}
    for name, utility in utilities.items():
        if utility <= 0.0:
            continue
        score = (utility * scale) ** behavior.concentration
        if behavior.progress and signals is not None:
            advance = max(expected_advance(name, signals), POSITIVE_GUARD)
            score *= advance**behavior.progress
        scores[name] = score
    return scores
