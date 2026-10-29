"""Quanto o sistema cobra do ingressante por cada vaga garantida.

    share = ⌊ C_a^(t,1) / |entrada| ⌋

Quem ingressa não dá lance: recebe vaga em todas as disciplinas de entrada
antes de o leilão abrir. O sistema ainda assim lança o gasto na conta dele,
repartindo o orçamento **igualmente** entre essas disciplinas e deixando o
resto da divisão no saldo.

Sem isso o retorno de créditos (eq. 34) não teria preço sobre o que
trabalhar: o calouro atravessaria o primeiro período com o orçamento intacto
e entraria no segundo com mais poder de compra que qualquer veterano, só por
nunca ter disputado nada.

Na linha de base por CR não há crédito, e nada é cobrado — a vaga garantida é
a mesma nos dois mecanismos; o que muda é só se ela custa algo.

A divisão é inteira porque crédito é indivisível; a validação do cenário já
garante que há pelo menos uma disciplina de entrada.
"""
from __future__ import annotations


def guaranteed_share(*, budget: int, entry_count: int) -> int:
    return budget // entry_count
