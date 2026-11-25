"""O funil de uma solicitação em quatro frações condicionais."""
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
