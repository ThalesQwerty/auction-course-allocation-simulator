"""Alcance: quantas disciplinas cada uma destrava, transitivamente.

    d_x = | fecho transitivo de unlocks(x) |

O "quanto avanço se passar" do termo de progresso de `decision_score`.

**Não é a altura.** Altura é o comprimento da cadeia mais longa à frente;
alcance é o tamanho do que fica destravado. Uma disciplina pode ter altura 1
e alcance 10 se destrava dez terminais de uma vez — e o que interessa ao
aluno que quer avançar é o alcance.

O memo é preenchido com o conjunto vazio **antes** de descer, o que corta
ciclo sem travar; a validação do cenário já os rejeita.
"""
from __future__ import annotations


def curriculum_reach(unlocks: dict[str, tuple[str, ...]]) -> dict[str, int]:
    memo: dict[str, set[str]] = {}

    def descend(name: str) -> set[str]:
        if name in memo:
            return memo[name]
        memo[name] = set()
        reached: set[str] = set()
        for successor in unlocks.get(name, ()):
            reached.add(successor)
            reached |= descend(successor)
        memo[name] = reached
        return reached

    return {name: len(descend(name)) for name in unlocks}
