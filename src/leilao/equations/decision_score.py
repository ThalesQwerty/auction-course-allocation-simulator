"""O score com que o aluno decide, em cima da utilidade dele.

    score_x = ũ_x ^ concentração

A **utilidade** (`equations.utility`) é a participação da disciplina no que o
aluno ainda quer. Nunca o interesse cru — a decisão só vê o que o histórico
deixou de pé.

A **concentração** é o expoente, e é metade do perfil de estratégia do aluno;
a outra metade é a seletividade, em `equations.reserve_threshold`. Ela não é
sorteada nem evoluída: é declarada, como o perfil de desempenho e o de
disponibilidade, e o aluno a recebe pela posição dele em `profile_index`.

| concentração | o que o aluno faz |
| −1 | aposta mais no que quer **menos** — o absurdo, de propósito |
| 0 | reparte igual entre tudo que admitiu |
| 1 | proporcional à utilidade — o lance sincero |
| 2, 3 | exagera as diferenças, investe no topo |

**1 é sincero num sentido exato**, não por convenção: é o ótimo da relaxação
contínua da mochila côncava (maximizar `Σ ũ·ln c` com `Σ c` fixo dá `c`
proporcional a `ũ`), de modo que o eixo se lê como *para que lado distorcer
compensa*. Ver `equations.concave_bids`.

POR QUE ELA É INERTE NO CR
---------------------------

Para concentração > 0, `ũ^c` é transformação **monótona**, e o `request_set`
ordena por score: a lista sai na mesma ordem qualquer que seja o expoente. É
resultado, não defeito — mede a expressividade que só a mochila côncava lê,
e a linha chapada do lado do CR é o controle.

O caso negativo é o único que mexe na ordem lá, e é o que o perfil Invertido
existe para mostrar.

A SATURAÇÃO
-----------

Os créditos saem proporcionais ao score, então o número **efetivo** de
disciplinas financiadas é `n · exp(−(c·σ)²)`. Com σ = 1 e c = 2 isso já é
quase tudo numa só: acima daí o expoente não gradua mais, só satura. A faixa
útil escala com `1/σ`.

Os dois genes de sinal — oferta e aprovação do período anterior — saíram com
o algoritmo genético. Sem eles o aluno não percebe folga nem taxa de
aprovação, e a dificuldade por turma afeta a nota sem ser caçada.

Não está no anteprojeto: substitui a eq. (41) e o score `u_rel^β · avanço^ρ`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

# A potência exige base estritamente positiva: expoente negativo sobre zero
# divide por zero, e o perfil Invertido usa expoente negativo. O menor
# positivo normalizado é a guarda mais barata que não muda conta nenhuma.
POSITIVE_GUARD = sys.float_info.min


@dataclass(frozen=True)
class Behavior:
    """O perfil de estratégia: como o aluno traduz utilidade em mensagem.

    **É função, não matriz.** A utilidade é resorteada a cada período, então
    um perfil com um valor por par (aluno, disciplina) descreveria o que
    fazer com a linha deste semestre e não diria nada sobre a do próximo.

    Os dois valores são declarados pelo cenário e distribuídos pela posição
    do aluno — são dois eixos de perfil, ao lado de desempenho e
    disponibilidade.
    """

    # O expoente do score. 1 é o lance sincero.
    concentration: float = 1.0
    # Múltiplo do score médio abaixo do qual o aluno não pede nem financia.
    # 0 desliga o corte: ele pede tudo que é elegível.
    selectivity: float = 0.0


NEUTRAL = Behavior()


def decision_scores(
    *, utilities: dict[str, float], behavior: Behavior = NEUTRAL
) -> dict[str, float]:
    """Disciplina de utilidade não positiva não entra: o zero marca o
    inelegível.

    A **ordem das chaves** é a de `utilities`, que é a ordem da grade — é dela
    que as duas mochilas tiram o desempate.
    """
    return {
        name: max(utility, POSITIVE_GUARD) ** behavior.concentration
        for name, utility in utilities.items()
        if utility > 0.0
    }
