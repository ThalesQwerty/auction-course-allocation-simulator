"""P̂(obter): a chance de vaga que a disciplina anuncia para o período seguinte.

    P̂(obter x) = min(1, q_x / n_x),    n_x = quantos pediram x

Um dos dois sinais que a universidade publica, e metade do conjunto de
informação do aluno sobre a disciplina — o outro é `pass_rate_estimate`. É
deliberadamente pobre: o aluno não conhece a dificuldade declarada nem a
própria aptidão por matéria, só a concorrência do semestre passado.

**Sem histórico vale 1**, e o termo de progresso de `decision_score` cai no
neutro sozinho: ninguém pediu quer dizer que não houve disputa a relatar.

O corte em 1 importa: uma disciplina com mais vagas que pedidos tem razão
acima de 1, e probabilidade não passa de 1.
"""
from __future__ import annotations


def win_estimate(*, seats: int, requests: int) -> float:
    if requests <= 0:
        return 1.0
    return min(1.0, seats / requests)
