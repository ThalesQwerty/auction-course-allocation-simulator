import pytest
from fastapi.testclient import TestClient

from leilao.api import storage
from leilao.api.main import app


@pytest.fixture(autouse=True)
def isolate_storage(tmp_path, monkeypatch):
    """Redireciona a persistência para um diretório temporário por teste."""
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "SCENARIOS_DIR", tmp_path / "scenarios")
    monkeypatch.setattr(storage, "RESULTS_DIR", tmp_path / "results")
    yield


@pytest.fixture
def client():
    return TestClient(app)


SAMPLE_SCENARIO = {
    "name": "cenário de teste",
    "agents": [
        {"id": "a1", "capacity": 10, "budget": 100, "academic_index": 9.0},
        {"id": "a2", "capacity": 10, "budget": 100, "academic_index": 4.0},
    ],
    "goods": [{"id": "x1", "quantity": 1, "weight": 4}],
    "demands": [
        {"agent_id": "a1", "good_id": "x1", "utility": 1.0},
        {"agent_id": "a2", "good_id": "x1", "utility": 1.0},
    ],
    "num_rounds": 1,
    "seed": 42,
}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get_scenario(client):
    created = client.post("/scenarios", json=SAMPLE_SCENARIO)
    assert created.status_code == 201
    scenario_id = created.json()["id"]

    fetched = client.get(f"/scenarios/{scenario_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "cenário de teste"


def test_list_scenarios(client):
    client.post("/scenarios", json=SAMPLE_SCENARIO)
    client.post("/scenarios", json={**SAMPLE_SCENARIO, "name": "segundo cenário"})
    response = client.get("/scenarios")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_missing_scenario_returns_404(client):
    assert client.get("/scenarios/does-not-exist").status_code == 404


def test_run_simulation_end_to_end(client):
    created = client.post("/scenarios", json=SAMPLE_SCENARIO)
    scenario_id = created.json()["id"]

    run = client.post(f"/scenarios/{scenario_id}/run")
    assert run.status_code == 200
    payload = run.json()

    assert payload["scenario_id"] == scenario_id
    assert payload["cr"]["allocation"]["a1|x1"] == 1
    assert payload["cr"]["allocation"].get("a2|x1", 0) == 0
    assert payload["auction_metrics"]["occupation_rate"] == 1.0

    # resultado persistido e recuperável
    fetched = client.get(f"/scenarios/{scenario_id}/result")
    assert fetched.status_code == 200
    assert fetched.json()["scenario_id"] == scenario_id


def test_run_simulation_missing_scenario_returns_404(client):
    assert client.post("/scenarios/does-not-exist/run").status_code == 404


def test_run_simulation_rejects_invalid_reference(client):
    bad_scenario = {
        **SAMPLE_SCENARIO,
        "demands": [{"agent_id": "a1", "good_id": "does-not-exist", "utility": 1.0}],
    }
    created = client.post("/scenarios", json=bad_scenario)
    scenario_id = created.json()["id"]
    response = client.post(f"/scenarios/{scenario_id}/run")
    assert response.status_code == 400


def test_delete_scenario(client):
    created = client.post("/scenarios", json=SAMPLE_SCENARIO)
    scenario_id = created.json()["id"]
    assert client.delete(f"/scenarios/{scenario_id}").status_code == 204
    assert client.get(f"/scenarios/{scenario_id}").status_code == 404
