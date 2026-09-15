"""Execução da simulação: dispara os dois mecanismos sobre um cenário salvo."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ... import simulation
from .. import storage
from ..schemas import ComparisonOut, AuctionResultOut, CRResultOut, MetricsOut

router = APIRouter(tags=["simulations"])


def _validate_scenario(scenario) -> None:
    agent_ids = {a.id for a in scenario.agents}
    good_ids = {g.id for g in scenario.goods}
    if not agent_ids:
        raise HTTPException(status_code=400, detail="cenário não tem nenhum agente (aluno)")
    if not good_ids:
        raise HTTPException(status_code=400, detail="cenário não tem nenhum bem (disciplina)")
    for d in scenario.demands:
        if d.agent_id not in agent_ids:
            raise HTTPException(status_code=400, detail=f"demanda referencia agente inexistente: {d.agent_id!r}")
        if d.good_id not in good_ids:
            raise HTTPException(status_code=400, detail=f"demanda referencia bem inexistente: {d.good_id!r}")
    for clique in scenario.exclusions:
        unknown = set(clique) - good_ids
        if unknown:
            raise HTTPException(status_code=400, detail=f"exclusão mútua referencia bens inexistentes: {unknown}")


@router.post("/scenarios/{scenario_id}/run", response_model=ComparisonOut)
def run_simulation(scenario_id: str) -> ComparisonOut:
    scenario = storage.load_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    _validate_scenario(scenario)

    try:
        result = simulation.run_comparison(scenario)
    except Exception as exc:  # noqa: BLE001 — reporta erro de solver/instância inviável
        raise HTTPException(status_code=422, detail=f"falha ao resolver o cenário: {exc}") from exc

    payload = ComparisonOut(
        scenario_id=result.scenario_id,
        auction=AuctionResultOut.from_result(result.auction),
        auction_metrics=MetricsOut.from_report(result.auction_metrics),
        cr=CRResultOut.from_result(result.cr),
        cr_metrics=MetricsOut.from_report(result.cr_metrics),
    )
    storage.save_result(scenario_id, payload.model_dump())
    return payload


@router.get("/scenarios/{scenario_id}/result", response_model=ComparisonOut)
def get_last_result(scenario_id: str) -> ComparisonOut:
    payload = storage.load_result(scenario_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="nenhum resultado disponível — execute a simulação primeiro")
    return ComparisonOut(**payload)
