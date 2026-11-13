"""O funil de uma solicitação em quatro frações condicionais.

    solicitadas = (todas − não solicitadas − não elegíveis) / todas
    deferidas   = (aprovadas + reprovadas + excluídas) / solicitadas
    cursadas    = (aprovadas + reprovadas) / deferidas
    aprovadas   = aprovadas / cursadas

Os denominadores são as **contagens** do nó anterior do funil de
`equations.request_states`: `solicitadas` é o que ele pediu, `deferidas` o que
lhe foi concedido, `cursadas` o que ele não largou.

Cada fração responde por **um** nó, e só por ele. É o que separa as quatro
perguntas que as seis contagens respondem juntas e nenhuma responde sozinha:
ele pediu pouco? pediu e não conseguiu? conseguiu e largou? cursou e não
passou?

Por que condicional, e não a fração do catálogo em cada estado: no catálogo as
seis andam juntas, porque todas dividem pelo mesmo denominador. Um aluno que
destrava a grade vê "não elegível" cair e as outras cinco subirem sem que nada
tenha mudado no mecanismo. Condicional, cada fração se mexe só quando o nó
dela se mexe.

**Todas vão de 0 a 1**, e mais alto é mais longe no funil. Não é juízo de
valor em todas: pedir mais não é melhor — a seletividade existe para cortar —,
e nem toda exclusão é falha do mecanismo.

**`None` quando o nó está vazio**, nunca 0: "ninguém pediu nada" é diferente
de "ninguém foi deferido". É a regra de ausência de `simulation.reports`.

A redundância com `equations.exclusion_rate` é exata: `cursadas = 1 − ε`. A
primeira é o funil visto de dentro, a segunda o desperdício visto da vaga.

Não consta no anteprojeto.
"""
from __future__ import annotations

from dataclasses import dataclass

from .request_states import RequestStates


@dataclass(frozen=True)
class RequestFunnel:
    """As quatro frações de um recorte, na ordem do funil."""

    requested_share: float | None
    granted_share: float | None
    attended_share: float | None
    approved_share: float | None


def request_funnel(states: RequestStates) -> RequestFunnel:
    requested = states.refused + states.excluded + states.failed + states.approved
    granted = states.excluded + states.failed + states.approved
    attended = states.failed + states.approved

    def share(part: float, whole: float) -> float | None:
        return part / whole if whole > 0.0 else None

    return RequestFunnel(
        requested_share=share(requested, states.total),
        granted_share=share(granted, requested),
        attended_share=share(attended, granted),
        approved_share=share(states.approved, attended),
    )
