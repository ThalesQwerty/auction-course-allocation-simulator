"""O que o aluno solicita na linha de base — anteprojeto, eq. (50).

    D_a^(t,r) = { x ∈ B_a^(t,r) : score_x > r },  ordenado por score decrescente

Ele pede **tudo** que lhe é elegível, da que mais quer para a que menos quer.
A restrição de carga (eq. 4) não é resolvida aqui — é resolvida na concessão.

**A mochila 0-1 saiu daqui**, e três razões sustentam isso:

1. **Sem isso o eixo ordenação × PLI não existe deste lado.** Com o pedido já
   cabendo em W_a por construção, a carga nunca apertava no alocador, o
   problema se separava por disciplina e os dois resolvedores davam sempre a
   mesma alocação.
2. **É à prova de estratégia.** Pedido recusado não custa nada e a prioridade
   do aluno não depende do que ele pede, então listar tudo na ordem verdadeira
   é dominante.
3. **É o que a universidade real faz**: o aluno se inscreve numa lista
   ordenada maior do que cabe, e o sistema para quando a grade enche.

Pedir tudo não é levar tudo: quem corta é o alocador, e o aluno perde o que
menos queria (na ditadura serial) ou o que o ótimo global dispensar (na PLI).

A ordenação é **estável** sobre um dicionário que já vem na ordem da grade,
de modo que scores empatados saem na ordem de listagem do cenário — a mesma
que desempata o lance. Pôr o nome na chave desempataria por alfabeto, que não
é critério nenhum.
"""
from __future__ import annotations

from collections.abc import Iterable


def request_set(
    *, scores: dict[str, float], available: Iterable[str], reserve: float = 0.0
) -> list[str]:
    wanted = set(available)
    ordered = sorted(
        ((name, score) for name, score in scores.items() if name in wanted),
        key=lambda item: -item[1],
    )
    return [name for name, score in ordered if score > reserve]
