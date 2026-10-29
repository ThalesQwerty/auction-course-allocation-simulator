"""Retificação do viés administrativo — anteprojeto, eq. (21).

    β̂_{a,x} = β_{a,x} − β_min

Desloca a matriz inteira até o menor viés valer zero, de modo que nenhum β̂
seja negativo e a preferência final (eq. 22) não possa cair abaixo do lance.
Viés positivo aumenta a prioridade do agente; zero não a influencia.
"""
from __future__ import annotations


def rectify_bias(bias: dict[tuple[str, str], int]) -> dict[tuple[str, str], int]:
    if not bias:
        return {}
    floor = min(bias.values())
    return {key: value - floor for key, value in bias.items()}
