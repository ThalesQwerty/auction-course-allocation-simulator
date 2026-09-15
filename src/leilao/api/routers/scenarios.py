"""CRUD de cenários — a interface monta aqui alunos, disciplinas e demandas."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import storage
from ..schemas import ScenarioIn, ScenarioOut

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioOut])
def list_scenarios() -> list[ScenarioOut]:
    return [ScenarioOut.from_scenario(s) for s in storage.list_scenarios()]


@router.post("", response_model=ScenarioOut, status_code=201)
def create_scenario(body: ScenarioIn) -> ScenarioOut:
    scenario = body.to_scenario(storage.new_id())
    storage.save_scenario(scenario)
    return ScenarioOut.from_scenario(scenario)


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: str) -> ScenarioOut:
    scenario = storage.load_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return ScenarioOut.from_scenario(scenario)


@router.put("/{scenario_id}", response_model=ScenarioOut)
def update_scenario(scenario_id: str, body: ScenarioIn) -> ScenarioOut:
    existing = storage.load_scenario(scenario_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    scenario = body.to_scenario(scenario_id)
    storage.save_scenario(scenario)
    return ScenarioOut.from_scenario(scenario)


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: str) -> None:
    if not storage.delete_scenario(scenario_id):
        raise HTTPException(status_code=404, detail="scenario not found")
