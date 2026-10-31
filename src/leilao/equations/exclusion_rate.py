"""Desperdício de vaga: quanto do que foi alocado não chegou a ser cursado.

    ε = |excluídas| / |obtidas|

O numerador e o denominador contam **vagas**, não alunos, e o denominador é o
que o mecanismo entregou — incluída a matrícula garantida, que também pode ser
excluída.

É a leitura direta do vão entre as duas ocupações: a vaga saiu da oferta de
qualquer jeito (θ não se mexe), mas só a parte retida virou carga cursada. Em 0
ninguém largou nada; perto de 1 o mecanismo distribuiu vagas que ninguém usou.

Recorte sem vaga obtida devolve 0, não divisão por zero: não houve o que
desperdiçar. Isso difere de "não havia ninguém", que o recorte vazio já trata
publicando métrica nenhuma.

Não está no anteprojeto.
"""
from __future__ import annotations


def exclusion_rate(*, excluded: int, allocated: int) -> float:
    if excluded < 0 or allocated < 0:
        raise ValueError("as contagens de vagas não podem ser negativas")
    if excluded > allocated:
        raise ValueError("não se pode excluir mais vagas do que se obteve")
    return excluded / allocated if allocated else 0.0
