"""Índice de oferta: a folga que a disciplina anuncia para o período seguinte.

    oferta_x = q_x / (q_x + n_x),     n_x = quantos pediram x no período anterior

Um dos dois sinais que a universidade publica, ao lado de `approval_index`.
Substitui `win_estimate`, que era `min(1, q/n)`.

POR QUE A SOMA NO DENOMINADOR, E NÃO A RAZÃO CRUA
--------------------------------------------------

Uma razão crua tem uma cauda que explode e outra esmagada em [0, 1], e a
explosão cai do lado errado: `n/q` estoura quando sobra uma vaga de
quatrocentos pedidos, `q/n` estoura quando ninguém pediu. Normalizar pela
soma fecha as duas pontas, põe o equilíbrio exatamente em 1/2 e nunca fica
indefinida.

Perde-se distinguir 10× de 100× de sobredemanda — e isso é ganho, porque a
dissuasão real satura também: o aluno não diferencia "sem chance" de "menos
chance ainda".

O NEUTRO É AUSÊNCIA DE INFORMAÇÃO, NÃO FOLGA MÁXIMA
----------------------------------------------------

Quando uma disciplina de período alto fica elegível pela primeira vez,
ninguém a pediu antes. Pela fórmula crua isso daria folga 1 — bônus máximo
exatamente na disciplina que vai lotar, e o sinal erraria justo quando o
funil abre.

Por isso **sem ninguém elegível o índice é 1/2**: ausência de informação, não
folga. Se havia elegíveis e mesmo assim veio pouco pedido, a demanda baixa é
informação de verdade e entra na conta. A regra também cobre o 1º período,
onde nada tem histórico e o gene de oferta simplesmente não age.

Aqui a suavização de Laplace não resolveria o que resolve em
`approval_index`: as contagens de vaga são grandes, e uma pseudocontagem
some diante delas.

Não está no anteprojeto.
"""
from __future__ import annotations

NEUTRAL_INDEX = 0.5


def supply_index(*, seats: int, requests: int, eligible: int) -> float:
    if eligible <= 0:
        return NEUTRAL_INDEX
    total = seats + requests
    if total <= 0:
        return NEUTRAL_INDEX
    return seats / total
