"""A utilidade de reserva: a seletividade repartida entre as elegíveis.

    s_a^(t) = S_a / |M_a^(t)|,        Σ_{X ∈ M_a^(t)} s_a^(t) = S_a

`S_a` é a **seletividade**, traço fixo do perfil, e é o único eixo de
estratégia do aluno. `s_a^(t)` é o limiar contra o qual ele compara cada
disciplina naquele período:

- **pede X** se `U_{a,X} ≥ s_a^(t)` (`equations.admitted_set`);
- **investe o k-ésimo crédito em X** se `U_{a,X}/k ≥ s_a^(t)`
  (`equations.concave_bids`).

Uma regra, dois usos, um por mecanismo: no CR não há investimento marginal
que se possa interromper, então lá o corte do conjunto é tudo o que existe.

POR QUE DIVIDIDA PELAS ELEGÍVEIS
---------------------------------

Porque `equations.utility` faz `Σ_{X ∈ M_a} U_{a,X} = 1`: a utilidade média de
uma disciplina elegível é exatamente `1/|M_a|`, e `S_a` se lê direto como
**múltiplo da indiferença** — "a disciplina precisa valer o dobro de uma
disciplina média" é 2, e não um número sem escala.

Dito ao contrário, `S_a` é a soma das reservas: o aluno reparte a própria
exigência entre as disciplinas que tem diante de si. Um limiar absoluto não
sobreviveria ao catálogo crescer — dobrar o número de disciplinas corta a
participação média pela metade, e o mesmo valor passaria a cortar o dobro —,
nem se adaptaria ao calouro e ao veterano, que têm conjuntos elegíveis de
tamanhos bem diferentes.

Com `S_a = 0` a reserva é zero e o aluno pede tudo que é elegível: é o
especulador, e é o perfil que a Seção 2.2 do anteprojeto diz que o CR
incentiva.

Não está no anteprojeto.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Behavior:
    """O perfil de estratégia: como o aluno traduz utilidade em mensagem.

    **É função, não matriz.** A utilidade é resorteada a cada período, então
    um perfil com um valor por par (aluno, disciplina) descreveria o que
    fazer com a linha deste semestre e não diria nada sobre a do próximo.

    O valor é declarado pelo cenário e distribuído pela posição do aluno — é
    um eixo de perfil, ao lado de desempenho, disponibilidade e rotina.
    """

    # S_a — a seletividade. 0 desliga o corte: o aluno pede tudo que é
    # elegível e gasta o orçamento inteiro.
    selectivity: float = 0.0


NEUTRAL = Behavior()


def reserve_threshold(*, selectivity: float, eligible: int) -> float:
    """`eligible` é `|M_a^(t)|` — quantas **disciplinas** o aluno pode cursar
    neste período, não quantas turmas."""
    if selectivity <= 0.0 or eligible <= 0:
        return 0.0
    return selectivity / eligible
