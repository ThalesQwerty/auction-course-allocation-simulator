"""A turma em que o aluno aposta os créditos de uma disciplina.

    turma escolhida = argmax_{t ∈ disponíveis} score_t

O segundo nível da mochila do leilão **não é outra mochila**: é uma escolha.
Decidido quanto a disciplina merece, o aluno põe tudo na turma mais bem
pontuada entre as que ainda dá para pedir.

POR QUE NÃO REPARTIR
---------------------

Pelo mesmo motivo que a mochila de fora é sobre disciplinas, e não sobre
turmas: o ganho marginal `score/N` vale **por bem**, então o 1º crédito na
turma B ganha do 2º na turma A sempre que `score_B > score_A/2` — o que, entre
turmas da mesma disciplina, é quase sempre. Repartir ali reproduz um nível
abaixo exatamente a pulverização que o nível de fora existe para evitar: o
aluno chega à rodada com 1/k da força em cada turma.

E repartir não compra o seguro que parece comprar. O aluno **só pode levar uma
turma** (eq. 5), de modo que o clique desfaz na alocação o que o lance
espalhou; o que ele ganha dividindo é a chance de pegar a segunda turma na
mesma rodada, e o que perde é poder nas duas. O seguro verdadeiro são as
**rodadas**: perdida a turma na rodada 1, `available_goods` devolve as irmãs na
rodada 2, com o orçamento que não foi gasto.

O preço disso é medido, e é o que decidiu: numa coorte de 324 ao longo de
4 períodos, repartir produziu 33 856 lances e 43,9 s de PLI contra 14 250
lances e 1,9 s concentrando — 23×. Repartir enche o modelo de restrições de
clique que a alocação depois tem de desfazer.

A ASSIMETRIA COM A LINHA DE BASE É DO MECANISMO
------------------------------------------------

Em `ranking` o aluno lista **todas** as turmas da disciplina, em ordem, e não
há nada a concentrar: pedido recusado não custa nada, e a caminhada da ditadura
serial já roteia para a primeira com vaga. Aqui cada crédito posto numa turma é
um crédito que não está em outra.

É a mesma diferença que separa as duas mochilas um nível acima — mensagem cara
contra mensagem gratuita —, e não um caminho que só existe de um lado.

O desempate é a **ordem da grade**, como em toda decisão que o aluno toma
sozinho. Com estabilidade entre turmas igual a 1 as turmas de uma disciplina
valem exatamente o mesmo, e aí o desempate manda todo mundo para a primeira:
é configuração degenerada, e é o que `class_stability < 1` existe para evitar.

Não está no anteprojeto, que é de turma única.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def best_class(
    *, scores: Mapping[str, float], available: Sequence[str]
) -> str | None:
    """`available` já vem na ordem da grade, e é dela que sai o desempate:
    `max` devolve o primeiro dos empatados."""
    candidates = [name for name in available if name in scores]
    if not candidates:
        return None
    return max(candidates, key=lambda name: scores[name])
