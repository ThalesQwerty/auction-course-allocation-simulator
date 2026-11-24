"""O que o aluno solicita na linha de base — anteprojeto, eq. (50).

    D_a^(t,r) = argmax { Σ_{x ∈ K} u_{a,x} : K ⊆ B_a^(t,r),
                         Σ_{x ∈ K} w_x ≤ W_a^(t,r),
                         |K ∩ X| ≤ 1 ∀ X ∈ E }

Uma **Mochila 0-1 com Grafo de Conflito** resolvida em casa: a carga horária
`w_x` é o peso, a utilidade `u_{a,x}` é o ganho, a carga máxima restante
`W_a^(t,r)` é a capacidade, e os cliques de `E = M ∪ G` são o grafo de
conflito. As turmas que entram na mochila são as turmas solicitadas; a saída
sai ordenada por utilidade decrescente, que é a ordem de preferência que a
caminhada de `equations.serial_dictatorship` consome.

É aqui que está a **primeira deficiência do CR**: o aluno é obrigado a
resolver a restrição de carga *ex-ante*, sobre o que ele ainda não sabe que
vai conseguir. Ele auto-restringe o pedido a uma grade que caiba, perde parte
dela na concessão, e só recupera a carga liberada na rodada seguinte. É essa
auto-restrição heurística sob incerteza que o leilão dispensa, ao mandar a
restrição para o resolvedor global — e é o que a comparação mede.

A MOCHILA É UMA SÓ, E É SOBRE TURMAS
-------------------------------------

Carga e choque de horário saem da **mesma** tabela: os itens são as turmas, e
os dois cliques de `E` são o grafo de conflito dela — `M` garante uma turma
por disciplina, `G` garante um horário por turma. O aluno não escolhe a seção
antes de ver se ela cabe; ele escolhe o pacote inteiro de uma vez, que é o que
a eq. (50) pede.

Deste lado o aluno resolve as duas restrições **em casa**, antes de saber o
que vai conseguir. Do lado do leilão quem resolve as duas é a PLI,
globalmente, depois de ver a demanda inteira. É aí também que a assimetria no
nível da turma aparece: no leilão há *quanto* a dizer, e o aluno reparte a
fatia da disciplina entre as turmas dela — inclusive entre turmas que colidem,
já que apostar não é levar. Aqui só há *qual*, e a mochila diz uma. Perdida
ela na rodada 1, `available_goods` devolve as irmãs na rodada 2.

O que a mochila **não** faz é ordenar: ela só lê os pesos e a soma das
utilidades, não *quanto* cada disciplina vale em relação às outras. Essa perda
de expressividade é a hipótese que a comparação testa.

A tabela em si está em `equations._knapsack`, compartilhada com
`equations.retained_set` — a mesma mochila, sobre o que foi conquistado em vez
do que é elegível, e lá sem conflito a respeitar. É lá que estão o desempate
pela ordem da grade, o corte pelo MDC dos pesos e a razão de o conflito tornar
a resposta um ótimo local.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from ._knapsack import knapsack


def request_set(
    *,
    utilities: Mapping[str, float],
    available: Iterable[str],
    hours: Mapping[str, int],
    capacity: int,
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """`available` é B_a^(t,r), `capacity` é W_a^(t,r) e `conflicts` mapeia
    cada turma nos cliques de `E` a que ela pertence.

    A ordem de `utilities` é a da grade no cenário, e é dela que sai o
    desempate — tanto o da mochila quanto o da ordenação final, que é estável.
    """
    wanted = set(available)
    items: Sequence[str] = [
        name
        for name in utilities
        if name in wanted and utilities[name] > 0.0
    ]
    if not items:
        return []
    chosen = knapsack(
        items=items,
        values=utilities,
        weights=hours,
        capacity=capacity,
        conflicts=conflicts,
    )
    return sorted(chosen, key=lambda name: -utilities[name])
