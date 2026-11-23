"""Preço de mercado de cada bem, a segundo preço — anteprojeto, eq. (24).

    π_x = max{ c_{a,x} : z_{a,x} = 0 }     (1 se ninguém perdeu)

O preço é o **maior lance mal-sucedido** naquele bem: quem vence paga o que
teria sido preciso para deslocá-lo, e não o que ofereceu. Sem lance perdedor
não houve disputa, e o piso de 1 crédito é o valor da equação nesse caso —
inclusive quando o bem não recebeu lance nenhum.

QUEM CONTA COMO PERDEDOR
------------------------

**Quem não levou aquela turma, e ponto.** Não importa se o autor do lance
levou outra turma da mesma disciplina, nem se levou outra turma no mesmo
horário: o lance foi feito naquela turma e não foi atendido nela, então ele
é o que um vencedor dali teve de superar.

Houve uma regra mais fina até 19/11/2026: quem fosse servido em qualquer
grupo de `E = M ∪ G` saía do conjunto de perdedores das turmas conflitantes,
sob o argumento de que ele não tinha sido *recusado* — tinha sido atendido.
Ela saiu por duas razões. A primeira é que o argumento só se sustenta em `M`:
quem queria a disciplina e levou outra turma dela está atendido, mas quem
levou uma disciplina às terças de manhã e perdeu outra no mesmo horário
**continua querendo a que perdeu**. A segunda é que a regra fazia o preço
depender de um emparelhamento alheio ao bem, e com isso o mesmo lance
contava ou não contava conforme o que o seu autor tivesse ganho em outro
lugar.

O efeito da troca é conhecido e aceito: o preço sobe mais nas disciplinas com
muitas turmas, porque é lá que existem lances irmãos a rejeitar. Como o lance
é repartido pela mochila côncava (`equations.concave_bids`), a turma preferida
leva o maior deles — e é ele que passa a precificar as irmãs quando o aluno é
roteado para outra.

Sempre inteiro: os lances (eq. 18) e o piso já o são.
"""
from __future__ import annotations


FLOOR = 1


def market_prices(
    *,
    good_ids: list[str],
    bids: dict[tuple[str, str], int],
    allocation: dict[tuple[str, str], int],
) -> dict[str, int]:
    highest_loser: dict[str, int] = {}
    for (agent_id, good_id), credits in bids.items():
        if allocation.get((agent_id, good_id)):
            continue
        highest_loser[good_id] = max(highest_loser.get(good_id, 0), credits)
    return {good_id: highest_loser.get(good_id, FLOOR) for good_id in good_ids}
