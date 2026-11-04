"""O corte da utilidade de reserva — quais disciplinas entram no pedido.

    admitidas = { x : ũ_x ≥ α_u }

`α_u` é a **utilidade de reserva**, e o termo é o da literatura de desenho de
mecanismos: o payoff da opção externa, contra o qual se escreve a restrição
de participação (racionalidade individual). Não é o preço de reserva do
vendedor — é o lado do agente.

A COMPARAÇÃO É DIRETA
---------------------

`α_u` está na **mesma unidade** da utilidade, que soma 1 sobre o elegível.
Com duas elegíveis valendo 0,6 e 0,4 e `α_u = 0,5`, o aluno pede só a
primeira. Sem normalizar por nada, sem denominador escondido — é isso que
torna o gene legível e portátil entre cenários, onde a reserva em unidades de
interesse cru variava 350× entre linhas da mesma observação.

Como as participações somam 1, no máximo `⌊1/α_u⌋` disciplinas passam do
corte: o gene é, na prática, um **teto de amplitude** do pedido. E o que
decide se *alguma* passa é a maior participação da linha — numa divisão
aleatória de 1 em n partes, a maior vale em média `H_n/n`, cerca de 0,31 para
n = 9. Acima disso o aluno típico não pede nada, de modo que a faixa útil do
gene é o fundo de [0, 1].

POR QUE FILTRAR O CONJUNTO, E NÃO PARAR O GASTO
------------------------------------------------

A reserva já foi um limiar sobre o *ganho marginal* dentro da mochila
côncava, que parava de comprar crédito quando o ganho caía abaixo dela. A
fila da mochila é ordenada pelo **score**, e o critério de parada passou a
ser a **utilidade**: a sequência que sai da fila não é monótona no critério,
então parar na primeira reprovada excluía disciplinas que ainda passariam.

Filtrando a entrada, o problema desaparece: a mochila recebe só o que foi
admitido e gasta o orçamento inteiro ali. O gene decide *quais* disciplinas,
e só isso — uma regra, um efeito.

**Nada impede que nada passe.** Perfil achatado com `α_u` alto zera o pedido
do período, e o aluno não solicita nada. É consequência da regra, não
acidente; se vier a incomodar, o conserto é um piso explícito de uma
disciplina, declarado aqui.

A **ordem das chaves** é a de `utilities`, que é a ordem da grade — é dela
que as duas mochilas tiram o desempate.

Não está no anteprojeto.
"""
from __future__ import annotations


def admitted_set(
    *, utilities: dict[str, float], reserve: float = 0.0
) -> dict[str, float]:
    if reserve <= 0.0:
        return utilities
    return {name: u for name, u in utilities.items() if u >= reserve}
