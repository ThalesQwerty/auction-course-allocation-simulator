import pytest
from fastapi.testclient import TestClient

from leilao.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


SAMPLE_REQUEST = {
    "agents": [
        {"id": "ana", "capacity": 10, "budget": 100},
        {"id": "bia", "capacity": 10, "budget": 100},
    ],
    "goods": [{"id": "calc1", "quantity": 1, "weight": 4}],
    "bids": [
        {"agent_id": "ana", "good_id": "calc1", "credits": 70},
        {"agent_id": "bia", "good_id": "calc1", "credits": 40},
    ],
    "seed": 42,
}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_run_returns_allocation_prices_and_consumption(client):
    response = client.post("/run", json=SAMPLE_REQUEST)
    assert response.status_code == 200
    payload = response.json()

    assert payload["allocation"]["ana|calc1"] == 1
    assert payload["allocation"]["bia|calc1"] == 0
    assert payload["prices"]["calc1"] == 40
    assert payload["consumption"]["ana|calc1"] == 40
    assert payload["remaining_budget"]["ana"] == 60
    assert payload["remaining_budget"]["bia"] == 100
    # ana venceu calc1 (peso 4) e tinha capacidade 10 -> restam 6; bia perdeu e mantém 10
    assert payload["remaining_capacity"]["ana"] == 6
    assert payload["remaining_capacity"]["bia"] == 10
    # créditos são sempre inteiros (eq. 18) — a API não deve devolver casas decimais
    assert isinstance(payload["prices"]["calc1"], int)
    assert isinstance(payload["remaining_budget"]["ana"], int)


def test_run_respects_mutual_exclusion(client):
    request = {
        "agents": [{"id": "ana", "capacity": 100, "budget": 100}],
        "goods": [{"id": "x1", "quantity": 1, "weight": 1}, {"id": "x2", "quantity": 1, "weight": 1}],
        "bids": [
            {"agent_id": "ana", "good_id": "x1", "credits": 30},
            {"agent_id": "ana", "good_id": "x2", "credits": 30},
        ],
        "exclusions": [["x1", "x2"]],
        "seed": 1,
    }
    response = client.post("/run", json=request)
    assert response.status_code == 200
    allocation = response.json()["allocation"]
    assert sum(allocation.values()) == 1


def test_run_rejects_overspent_budget(client):
    request = {
        "agents": [{"id": "ana", "capacity": 10, "budget": 10}],
        "goods": [{"id": "x1", "quantity": 1, "weight": 1}, {"id": "x2", "quantity": 1, "weight": 1}],
        "bids": [
            {"agent_id": "ana", "good_id": "x1", "credits": 6},
            {"agent_id": "ana", "good_id": "x2", "credits": 6},
        ],
        "seed": 1,
    }
    response = client.post("/run", json=request)
    assert response.status_code == 400


SIMULATE_REQUEST = {
    "disciplines": [
        {"name": "Cálculo I", "seats": 3, "hours": 60},
        {"name": "Física I", "seats": 3, "hours": 60},
        {"name": "Programação", "seats": 3, "hours": 60},
    ],
    "courses": [
        {
            "name": "Computação",
            "students_per_generation": 4,
            "hours_to_graduate": 120,
            "required": ["Cálculo I", "Programação"],
            "electives": ["Física I"],
        }
    ],
    "periods": 3,
    "rounds": 2,
    "seed": 5,
}


def test_simulate_returns_series_by_period_and_course(client):
    response = client.post("/simulate", json=SIMULATE_REQUEST)
    assert response.status_code == 200
    payload = response.json()

    assert payload["courses"] == ["Computação"]
    assert len(payload["periods"]) == 3
    # 4 por geração em 3 períodos: uma geração nova entra a cada período.
    assert len(payload["students"]) == 12

    period = payload["periods"][0]
    assert len(period["rounds"]) == 2
    assert period["aggregate"]["round"] == 0
    assert [s["course"] for s in period["aggregate"]["by_course"]] == ["Computação"]
    assert 0 <= period["aggregate"]["overall"]["efficiency"] <= 1
    # nomes de disciplina com acento e espaço sobrevivem ao solver
    assert {d["name"] for d in period["disciplines"]} == {"Cálculo I", "Física I", "Programação"}


def test_simulate_omits_histories_unless_asked(client):
    """O detalhe por aluno é quase toda a resposta num cenário grande, então só
    vai quando pedido — a tela individual é a única que precisa dele."""
    payload = client.post("/simulate", json=SIMULATE_REQUEST).json()
    assert payload["histories"] == []
    # o resto da resposta continua inteiro
    assert len(payload["students"]) == 12
    assert len(payload["periods"]) == 3


def test_simulate_returns_a_history_per_student(client):
    """A tela individual lê `histories`; um aluno por histórico, na mesma ordem."""
    payload = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "include_histories": True}
    ).json()

    assert [h["student_id"] for h in payload["histories"]] == [
        s["id"] for s in payload["students"]
    ]
    records = [r for h in payload["histories"] for r in h["periods"]]
    assert records, "a simulação deveria ter períodos registrados"
    for record in records:
        assert 1 <= record["period"] <= 3
        assert 0 <= record["satisfaction"] <= 1
        for request in record["requests"]:
            assert request["kind"] in {"required", "elective", "free"}
            # um lance por rodada — |R| = 2 nesta requisição
            assert len(request["bids"]) == 2
            assert (request["won_round"] is None) == (request["grade"] is None)


def test_simulate_rejects_impossible_curriculum(client):
    request = {
        **SIMULATE_REQUEST,
        "courses": [{**SIMULATE_REQUEST["courses"][0], "hours_to_graduate": 9999}],
    }
    response = client.post("/simulate", json=request)
    assert response.status_code == 400


def test_run_with_no_bids_returns_empty_allocation(client):
    request = {
        "agents": [{"id": "ana", "capacity": 10, "budget": 10}],
        "goods": [{"id": "x1", "quantity": 1, "weight": 1}],
        "bids": [],
        "seed": 1,
    }
    response = client.post("/run", json=request)
    assert response.status_code == 200
    assert response.json()["allocation"] == {}


def test_simulate_accepts_an_entry_window_and_a_deadline(client):
    """L e T_max chegam ao motor pela API, e o resultado traz as duas portas de
    saída — `dismissed` nos recortes e `dismissed_at` em cada aluno."""
    payload = client.post(
        "/simulate",
        json={**SIMULATE_REQUEST, "periods": 5, "entry_periods": 2, "max_residence": 2},
    ).json()

    # 4 por geração em 2 gerações: a janela de ingresso, não o horizonte.
    assert len(payload["students"]) == 8
    assert {s["entry_period"] for s in payload["students"]} == {1, 2}

    # Prazo de 2 períodos: ninguém fica em aberto ao fim.
    for student in payload["students"]:
        assert (student["graduated_at"] is None) != (student["dismissed_at"] is None)

    last = payload["periods"][-1]["aggregate"]["by_course"][0]
    assert last["population"] == 8
    assert last["graduated"] + last["dismissed"] == 8
    assert sum(p["dismissed_now"] for p in payload["periods"]) == last["dismissed"]


def test_simulate_rejects_an_entry_window_wider_than_the_horizon(client):
    response = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "periods": 3, "entry_periods": 4}
    )
    assert response.status_code == 400
    assert "ingresso" in response.json()["detail"]


def test_simulate_without_the_new_fields_keeps_the_previous_behaviour(client):
    """Omitir L e T_max = ingresso em todos os períodos e sem prazo, que é o que
    as requisições montadas antes destes campos mandam."""
    payload = client.post("/simulate", json=SIMULATE_REQUEST).json()
    assert {s["entry_period"] for s in payload["students"]} == {1, 2, 3}
    assert all(s["dismissed_at"] is None for s in payload["students"])
    assert all(p["dismissed_now"] == 0 for p in payload["periods"])


def test_simulate_treats_a_zero_deadline_as_no_deadline(client):
    """0 é o desligado do jubilamento, e é o que a interface manda quando o
    usuário zera o campo."""
    payload = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "periods": 5, "max_residence": 0}
    ).json()
    assert all(s["dismissed_at"] is None for s in payload["students"])
    assert all(p["dismissed_now"] == 0 for p in payload["periods"])


def test_simulate_rejects_a_negative_deadline(client):
    response = client.post("/simulate", json={**SIMULATE_REQUEST, "max_residence": -1})
    assert response.status_code == 422
