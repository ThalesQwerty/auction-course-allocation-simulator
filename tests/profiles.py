"""Distribuições de população para os testes.

A população do cenário é descrita por **três distribuições** mais o nível
basilar de cada uma; não há mais perfis a declarar, e a configuração deriva a
disponibilidade de W_a quando o cenário não a declara
(`config.default_availability`) — a moda é absoluta, e uma constante fixa
recusaria todo cenário de teto menor.

O que ainda precisa ser escrito à mão é o controle **sem exclusão**, porque ele
não é um patamar da calibragem: é o caso degenerado, e serve para isolar o
mecanismo da disponibilidade.
"""
from __future__ import annotations

from leilao.config import AvailabilityShape, default_availability


def always_available(max_hours: int) -> AvailabilityShape:
    """A distribuição que praticamente nunca exclui.

    Note o que a chance tão alta custa à forma: com a moda logo abaixo de W_a,
    exigir que quase toda a massa fique **acima** dele força um desvio
    logarítmico enorme, e a mediana vai para longe. É consistente, e para este
    controle é o que se quer — mas mostra que "quase sempre cheio" e
    "tipicamente perto de W_a" são pedidos incompatíveis nesta família.
    """
    return AvailabilityShape(mode_hours=max_hours - 1, full_load_rate=0.9999)


def single_axis(max_hours: int) -> dict:
    """Os eixos da população num cenário de teste.

    A seletividade sai **desligada** (`selectivity_median = 0`), de modo que
    construir um cenário sem dizer nada sobre estratégia não liga o corte do
    pedido sem avisar — era o papel do perfil neutro.

    Uma faixa só em cada eixo de estado: quem testa o recorte declara os seus cortes.
    """
    return {
        "availability": default_availability(max_hours),
        "selectivity_median": 0.0,
        "grade_cuts": (),
        "reserve_cuts": (),
        "credit_cuts": (),
    }
