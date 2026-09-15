"""Persistência simples em arquivos JSON para cenários e resultados.

Escolhida por simplicidade e reprodutibilidade (cada cenário é um arquivo
versionável e legível), evitando a complexidade de um banco de dados para o
escopo deste projeto.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from ..scenario import Scenario

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"
RESULTS_DIR = DATA_DIR / "results"


def _ensure_dirs() -> None:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def scenario_path(scenario_id: str) -> Path:
    return SCENARIOS_DIR / f"{scenario_id}.json"


def result_path(scenario_id: str) -> Path:
    return RESULTS_DIR / f"{scenario_id}.json"


def save_scenario(scenario: Scenario) -> None:
    _ensure_dirs()
    scenario.save(scenario_path(scenario.id))


def load_scenario(scenario_id: str) -> Scenario | None:
    path = scenario_path(scenario_id)
    if not path.exists():
        return None
    return Scenario.load(path)


def list_scenarios() -> list[Scenario]:
    _ensure_dirs()
    return [Scenario.load(p) for p in sorted(SCENARIOS_DIR.glob("*.json"))]


def delete_scenario(scenario_id: str) -> bool:
    path = scenario_path(scenario_id)
    if not path.exists():
        return False
    path.unlink()
    result = result_path(scenario_id)
    if result.exists():
        result.unlink()
    return True


def save_result(scenario_id: str, payload: dict) -> None:
    _ensure_dirs()
    result_path(scenario_id).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_result(scenario_id: str) -> dict | None:
    path = result_path(scenario_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
