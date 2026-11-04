"""Perfil de disponibilidade que praticamente nunca exclui.

Os três patamares do cenário padrão **não** precisam de ajuda: a configuração
os deriva de W_a quando o cenário não declara os seus (`config.default_availability`),
justamente porque a moda é absoluta e uma constante dimensionada para 360 h
recusaria todo cenário de teto menor.

O que ainda precisa ser escrito à mão é o controle sem exclusão, porque ele não
é um patamar — é o caso degenerado.
"""
from __future__ import annotations

from leilao.config import AvailabilityProfile


def always_available(max_hours: int) -> tuple[AvailabilityProfile, ...]:
    """Um perfil só, que praticamente nunca exclui.

    Note o que a chance tão alta custa à forma: com a moda logo abaixo de W_a,
    exigir que quase toda a massa fique **acima** dele força um desvio
    logarítmico enorme, e a mediana vai para longe. É consistente, e para este
    controle é o que se quer — mas mostra que "quase sempre cheio" e
    "tipicamente perto de W_a" são pedidos incompatíveis nesta família.
    """
    return (
        AvailabilityProfile(
            name="cheia", mode_hours=max_hours - 1, full_load_rate=0.9999
        ),
    )
