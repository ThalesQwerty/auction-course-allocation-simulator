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


# Grade de dois períodos: "Cálculo I" e "Programação" de entrada (matrícula
# garantida) e "Física I" desbloqueada por "Cálculo I".
COMPARE_SCENARIO = {
    "disciplines": [
        {"name": "Cálculo I", "seats": 6, "hours": 60, "unlocks": ["Física I"], "entry": True},
        {"name": "Programação", "seats": 6, "hours": 60, "unlocks": [], "entry": True},
        {"name": "Física I", "seats": 6, "hours": 60, "unlocks": [], "entry": False},
    ],
    "periods": 3,
    "students_per_period": 4,
    "rounds": 2,
    "seed": 5,
}

# As duas normais que descrevem a população, no lugar dos perfis que existiram
# até 08/10/2026. Notas baixas e ganho alto para o cenário produzir recursadas
# dentro do horizonte; W_a de 120 h para o teto morder.
POPULATION = {
    # Aptidão dura: média 0,4 (a Beta(2, 3) de antes), então reprova-se
    # bastante e há recursada o bastante para o teste da razão D/t ter amostra.
    "aptitude_mean": 0.4,
    "aptitude_concentration": 5,
    "utility_sigma": 1,
    "max_hours": 120,
}

def test_compare_returns_one_summary_per_seed_in_every_arm(client):
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 3}).json()

    assert payload["runs"] == 3
    # Seis modelos: as quatro células do cruzamento moeda x resolvedor, mais
    # as duas pontas da escada de acúmulo (o degrau do meio é `credits_ilp`).
    assert [a["key"] for a in payload["arms"]] == [
        "ranking_greedy",
        "ranking_ilp",
        "credits_greedy",
        "credits_ilp",
        "credits_no_memory",
        "credits_return",
    ]
    # As seeds vão de 1 a N e são pareadas: a i-ésima execução de cada braço
    # parte da mesma população.
    for arm in payload["arms"]:
        assert [r["seed"] for r in arm["runs"]] == [1, 2, 3]


def test_compare_returns_only_the_allocation_metrics(client):
    """Nada de crédito: orçamento, preço e retorno não existem do lado da linha
    de base, e nenhum recorte — o que se compara é o mecanismo. `periods` e
    `graduates` não são métricas: são o contexto para ler as que são."""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 2}).json()

    assert set(payload["arms"][0]["runs"][0]) == {
        "seed",
        "periods",
        "graduates",
        "efficiency",
        "utilization",
        "fidelity",
        "fairness",
        "correlation",
        "time_to_graduate",
        "allocations_per_round",
    }


def test_compare_reports_the_time_to_graduate_with_its_denominator(client):
    """O tempo de formatura tem viés de seleção — só existe sobre quem
    concluiu —, então `graduates` anda junto. Sem concluinte, o tempo é nulo,
    não zero: zero se leria como 'formou na hora'."""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 2}).json()

    for run in [r for arm in payload["arms"] for r in arm["runs"]]:
        assert (run["time_to_graduate"] is None) == (run["graduates"] == 0)
        if run["time_to_graduate"] is not None:
            # Ninguém conclui em menos de um período, nem em mais do que o
            # horizonte simulado.
            assert 1 <= run["time_to_graduate"] <= run["periods"]


def test_compare_ignores_the_scenario_seed_and_credit_return(client):
    """Nenhum dos dois entra: a seed vira o eixo da amostra e o retorno vira o
    eixo do experimento, imposto por cada braço."""
    first = client.post(
        "/compare", json={**COMPARE_SCENARIO, "seed": 1, "credit_return": "none", "runs": 2}
    ).json()
    second = client.post(
        "/compare", json={**COMPARE_SCENARIO, "seed": 77, "credit_return": "unit", "runs": 2}
    ).json()

    assert first == second


def test_compare_reports_one_allocation_figure_per_round(client):
    """A saturação tem uma posição por rodada do cenário, igual em todo braço —
    é o decaimento entre elas que responde "satura mais rápido?"."""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 2}).json()

    rounds = COMPARE_SCENARIO["rounds"]
    for run in [r for arm in payload["arms"] for r in arm["runs"]]:
        assert len(run["allocations_per_round"]) == rounds
        assert all(value is None or value >= 0 for value in run["allocations_per_round"])

def test_compare_rejects_an_invalid_run_count(client):
    assert client.post("/compare", json={**COMPARE_SCENARIO, "runs": 0}).status_code == 422
    assert client.post("/compare", json={**COMPARE_SCENARIO, "runs": 500}).status_code == 422


def test_compare_rejects_an_invalid_scenario(client):
    response = client.post(
        "/compare", json={**COMPARE_SCENARIO, "students_per_period": 7, "runs": 2}
    )

    assert response.status_code == 400
    assert "vaga garantida" in response.json()["detail"]
