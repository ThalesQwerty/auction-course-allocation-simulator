"""Tempo de formatura: períodos do ingresso ao diploma.

    tempo = Σ_{a : concluiu} (t_formatura(a) − t_a + 1) / |{a : concluiu}|

Conta inclusive o período da formatura: quem entra em t e conclui ao fim de t
levou 1 período, não 0.

**Tem viés de seleção, e por isso não se lê sozinho.** A média só existe
sobre quem concluiu: um mecanismo que forma menos gente pode exibir um tempo
*menor* só porque sobraram os rápidos. Quem não concluiu não entra como
"muito lento", porque não há valor que o represente — é a contagem de
concluintes, publicada ao lado, que diz quantos ficaram de fora.

`None` quando ninguém concluiu: a média não existe, e 0 ali se leria como
"formou na hora", que é o contrário do que aconteceu.
"""
from __future__ import annotations

from collections.abc import Iterable


def time_to_graduate(spans: Iterable[int]) -> float | None:
    values = list(spans)
    return sum(values) / len(values) if values else None
