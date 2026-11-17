"""A turma que o aluno solicita na linha de base.

    turma escolhida = argmax { u_t : t disponível, t não choca com o já pedido }

No braço CR o aluno **solicita uma turma por disciplina**, e solicita a mais
útil entre as que ainda dá para pedir **sem choque de horário** com o que ele
já escolheu neste pedido. Não há o que repartir: o pedido não tem moeda, e
pedir duas turmas no mesmo horário seria pedir o que ele não poderia cursar
junto — o clique da eq. (5) reduziria o par a uma delas de todo modo.

`blocked` são os grupos de `E` já comprometidos no pedido, e `conflicts`
mapeia cada turma nos grupos dela. Montar o pedido assim é o análogo, deste
lado, da restrição de clique que a PLI resolve sozinha: aqui o aluno resolve
o conflito **em casa**, porque é ele quem escolhe a seção.

A ASSIMETRIA COM O LEILÃO É DO MECANISMO
-----------------------------------------

No leilão o segundo nível é **outra mochila côncava**: os créditos que a
disciplina recebeu se repartem entre as turmas dela na proporção do ganho
marginal, e o aluno chega à rodada com uma aposta em cada uma — inclusive em
turmas que colidem entre si, porque ali apostar não é levar. Aqui não há
quanto a dizer — só qual —, e o aluno diz a melhor que ainda cabe.

É a mesma diferença que separa as duas mochilas um nível acima — mensagem
cara contra mensagem gratuita: lá cada crédito posto numa turma é um crédito
que não está em outra, e é por isso que há uma repartição a fazer.

O seguro, aqui, são as **rodadas**: perdida a turma na rodada 1,
`available_goods` devolve as irmãs na rodada 2.

O desempate é a **ordem da grade**, como em toda decisão que o aluno toma
sozinho. Com estabilidade entre turmas igual a 1 e rotina indiferente as
turmas de uma disciplina valem exatamente o mesmo, e aí o desempate manda
todo mundo para a primeira: é configuração degenerada, e é o que
`class_stability < 1` e os perfis de rotina existem para evitar.

Não está no anteprojeto, que é de turma única.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence, Set


def best_class(
    *,
    scores: Mapping[str, float],
    available: Sequence[str],
    blocked: Set[str] = frozenset(),
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> str | None:
    """`available` já vem na ordem da grade, e é dela que sai o desempate:
    `max` devolve o primeiro dos empatados."""
    candidates = [
        name
        for name in available
        if name in scores
        and blocked.isdisjoint(conflicts[name] if conflicts else (name,))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda name: scores[name])
