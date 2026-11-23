"""Alcance: quantas disciplinas cada uma destrava, transitivamente.

    d_x = | seq(x) |

O "quanto avanço se passar" de uma disciplina. Não é lido por decisão
nenhuma hoje — o termo de progresso que o consumia saiu com o algoritmo
genético —, e fica como leitura da grade.

**Não é a altura.** Altura é o comprimento da cadeia mais longa à frente;
alcance é o tamanho do que fica destravado. Uma disciplina pode ter altura 1
e alcance 10 se destrava dez terminais de uma vez — e o que interessa ao
aluno que quer avançar é o alcance.

É a contagem do mesmo conjunto que `equations.utility` soma: o fecho mora em
`curriculum_closure`, e aqui só se mede o tamanho dele.
"""
from __future__ import annotations

from .curriculum_closure import transitive_closure


def curriculum_reach(unlocks: dict[str, tuple[str, ...]]) -> dict[str, int]:
    return {
        name: len(reached) for name, reached in transitive_closure(unlocks).items()
    }
