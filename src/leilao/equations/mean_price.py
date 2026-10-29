"""O preço do período de uma disciplina.

    π̄_x = Σ_r π_x^(t,r) / |{ r : q_x^(t,r) > 0 }|

A média de π_x (eq. 24) **só sobre as rodadas em que a disciplina ainda tinha
vaga**. O denominador é essa contagem, e não |R|, por um motivo que muda o
sinal da leitura: uma disciplina esgotada na rodada 1 não recebe mais lance
nenhum e cairia no piso de 1 crédito até o fim do período, o que a faria
aparecer **barata** justamente por ter sido a mais disputada.

`None` quando ela nunca esteve no mercado — q_x = 0, ou esgotada pelos
ingressantes antes da primeira rodada. Zero ali se leria como "de graça".
"""
from __future__ import annotations


def mean_price(*, price_sum: int, rounds_on_market: int) -> float | None:
    if not rounds_on_market:
        return None
    return price_sum / rounds_on_market
