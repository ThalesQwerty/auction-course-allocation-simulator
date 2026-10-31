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
    # Os quatro passos do caminho, na ordem do eixo. Não há braço que rode
    # sem aparecer nos resultados.
    assert [a["key"] for a in payload["arms"]] == [
        "ranking_greedy",
        "credits_greedy",
        "credits_ilp",
        "credits_return",
    ]
    # As seeds vão de 1 a N e são pareadas: a i-ésima execução de cada braço
    # parte da mesma população.
    for arm in payload["arms"]:
        assert [r["seed"] for r in arm["runs"]] == [1, 2, 3]


def test_compare_returns_only_the_allocation_metrics(client):
    """Nada de crédito: orçamento, preço e retorno não existem do lado da linha
    de base, e nenhum recorte — o que se compara é o mecanismo. `periods`,
    `graduates`, `dismissed` e `population` não são métricas: são o contexto
    para ler as que são — as duas frações da tela saem deles."""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 2}).json()

    assert set(payload["arms"][0]["runs"][0]) == {
        "seed",
        "periods",
        "graduates",
        "dismissed",
        "population",
        "efficiency",
        "utilization",
        "fidelity",
        "fairness",
        "correlation",
        "time_to_graduate",
        "allocations_per_round",
        "by_period",
        "by_cohort",
    }
    # A série por período é o mesmo recorte sem reduzir: as mesmas métricas —
    # a saturação inclusive, que ali vira uma linha por período —, mais o peso
    # de cada ponto e o número do período a que ele pertence. O tempo de
    # formatura não entra: é da execução inteira.
    assert set(payload["arms"][0]["runs"][0]["by_period"]) == {
        "period",
        "students",
        "efficiency",
        "utilization",
        "fidelity",
        "fairness",
        "correlation",
        "allocations_per_round",
    }
    # O recorte por geração leva as mesmas, mais o tempo de formatura — que ali
    # existe, porque cada aluno pertence a uma geração só — e os concluintes,
    # que são o denominador dele.
    assert set(payload["arms"][0]["runs"][0]["by_cohort"]) == {
        "cohort",
        "graduates",
        "graduation_rate",
        "dismissal_rate",
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

def test_trace_reproduces_the_execution_the_comparison_summarized(client):
    """O par (braço, seed) endereça uma execução do boxplot, e o traço é ela —
    não uma parecida. A simulação é determinística, então refazê-la custa tempo
    e não fidelidade: o que se confere aqui é que o braço entra dos dois lados
    pela mesma porta (`arm_config`)."""
    comparison = client.post("/compare", json={**COMPARE_SCENARIO, **POPULATION, "runs": 2}).json()

    for arm in comparison["arms"]:
        for run in arm["runs"]:
            payload = client.post(
                "/trace",
                json={**COMPARE_SCENARIO, **POPULATION, "arm": arm["key"], "seed": run["seed"]},
            ).json()

            assert payload["arm"] == arm["key"]
            assert payload["seed"] == run["seed"]
            assert len(payload["periods"]) == run["periods"]
            graduated = [s for s in payload["students"] if s["graduated_at"] is not None]
            assert len(graduated) == run["graduates"]


def test_trace_records_every_eligible_discipline_round_by_round(client):
    """Cada linha é uma disciplina elegível no período, com uma posição por
    rodada do cenário — inclusive as que ficaram em zero, que são o caso que
    costuma explicar um resultado inesperado."""
    payload = client.post(
        "/trace", json={**COMPARE_SCENARIO, **POPULATION, "arm": "credits_return", "seed": 1}
    ).json()

    rounds = COMPARE_SCENARIO["rounds"]
    records = [
        record
        for history in payload["histories"]
        for period in history["periods"]
        for record in period["requests"]
    ]
    assert records
    for record in records:
        assert len(record["bids"]) == rounds
        assert record["utility"] > 0
        # Vaga obtida tem nota — o período fecha antes do relatório —, e só ela.
        assert (record["grade"] is None) == (record["won_round"] is None)
    # Vaga ganha numa rodada tem lance **naquela** rodada: é o que a tabela de
    # cada rodada mostra lado a lado. (A vaga garantida é a exceção declarada:
    # ela não veio de rodada nenhuma e leva `won_round` 0.)
    won_in_round = [r for r in records if r["won_round"] is not None and r["won_round"] > 0]
    assert won_in_round
    for record in won_in_round:
        assert record["bids"][record["won_round"] - 1] > 0


def test_trace_marks_the_guaranteed_enrollment_of_the_newcomer(client):
    """A vaga garantida não veio de rodada nenhuma: `won_round` 0 a distingue de
    uma disputada e ganhada na primeira."""
    payload = client.post(
        "/trace", json={**COMPARE_SCENARIO, **POPULATION, "arm": "credits_return", "seed": 1}
    ).json()

    entry = {s["id"]: s["entry_period"] for s in payload["students"]}
    guaranteed = [
        record
        for history in payload["histories"]
        for period in history["periods"]
        if period["period"] == entry[history["student_id"]]
        for record in period["requests"]
        if record["won_round"] == 0
    ]
    assert guaranteed


def test_trace_rejects_an_unknown_arm(client):
    response = client.post(
        "/trace", json={**COMPARE_SCENARIO, "arm": "leilao_imaginario", "seed": 1}
    )

    assert response.status_code == 400
    assert "credits_return" in response.json()["detail"]


def test_compare_rejects_an_invalid_run_count(client):
    assert client.post("/compare", json={**COMPARE_SCENARIO, "runs": 0}).status_code == 422
    assert client.post("/compare", json={**COMPARE_SCENARIO, "runs": 500}).status_code == 422


def test_compare_rejects_an_invalid_scenario(client):
    response = client.post(
        "/compare", json={**COMPARE_SCENARIO, "students_per_period": 7, "runs": 2}
    )

    assert response.status_code == 400
    assert "vaga garantida" in response.json()["detail"]
