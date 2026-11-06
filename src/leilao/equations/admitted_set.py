"""O corte da seletividade — quais disciplinas entram no pedido.

    admitidas = { x : score_x ≥ limiar }

O limiar vem de `equations.reserve_threshold`: a seletividade do perfil em
múltiplos do score médio. O termo "reserva" é o da literatura de desenho de
mecanismos — o payoff da opção externa, contra o qual se escreve a restrição
de participação. Não é o preço de reserva do vendedor: é o lado do agente.

O MESMO LIMIAR NOS DOIS MECANISMOS
-----------------------------------

Aqui ele **filtra**: o que não passa não é pedido e não recebe crédito. No
leilão ele também **para o gasto**, em `equations.concave_bids` — o aluno
deixa de comprar crédito quando o ganho marginal do próximo cai abaixo dele.

Uma regra, dois usos, um por mecanismo. No CR não há investimento marginal
que se possa interromper, então lá o filtro é tudo o que existe.

**A parada já existiu e foi removida uma vez**, porque comparava o ganho
marginal (ordenado por score) contra a utilidade: a sequência que saía da
fila não era monótona no critério, e parar na primeira reprovada excluía
disciplinas que ainda passariam. Comparando contra o **score**, que é a
própria chave do heap, a monotonicidade volta e o `break` fica correto.

**Nada impede que nada passe.** Perfil achatado com seletividade alta zera o
pedido do período, e o aluno não solicita nada. É consequência da regra, não
acidente.

A **ordem das chaves** é a de `scores`, que é a ordem da grade — é dela que
as duas mochilas tiram o desempate.

Não está no anteprojeto.
"""
from __future__ import annotations


def admitted_set(
    *, scores: dict[str, float], reserve: float = 0.0
) -> dict[str, float]:
    if reserve <= 0.0:
        return scores
    return {name: score for name, score in scores.items() if score >= reserve}
