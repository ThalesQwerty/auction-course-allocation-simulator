"""O corte da seletividade — quais disciplinas entram no pedido.

    admitidas = { X : U_{a,X} ≥ s_a^(t) }

O limiar vem de `equations.reserve_threshold`: a seletividade do perfil
repartida entre as elegíveis do período. O termo "reserva" é o da literatura
de desenho de mecanismos — o payoff da opção externa, contra o qual se
escreve a restrição de participação. Não é o preço de reserva do vendedor: é
o lado do agente.

O MESMO LIMIAR NOS DOIS MECANISMOS
-----------------------------------

Aqui ele **filtra**: o que não passa não é pedido e não recebe crédito. No
leilão ele também **para o gasto**, em `equations.concave_bids` — o aluno
deixa de comprar crédito quando o ganho marginal do próximo cai abaixo dele.

Uma regra, dois usos, um por mecanismo. No CR não há investimento marginal
que se possa interromper, então lá o filtro é tudo o que existe.

A parada da mochila compara contra a **própria chave do heap**, que é o
ganho marginal `U_{a,X}/k`: se o topo não passa do limiar, nada passa, e o
`break` fica correto.

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
