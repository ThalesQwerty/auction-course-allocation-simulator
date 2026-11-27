import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from leilao.api.main import app
from leilao.api.schemas import CompareRequest
from leilao.api.service import build_config
from leilao.comparison import ARMS, run_comparison


@pytest.fixture(autouse=True)
def results_dir(tmp_path, monkeypatch):
    """Toda rota que roda grava a execução em disco. Sem isto a suíte deixaria"""
    monkeypatch.setenv("LEILAO_RESULTS_DIR", str(tmp_path / "resultados"))
    return tmp_path / "resultados"


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
    assert payload["remaining_capacity"]["ana"] == 6
    assert payload["remaining_capacity"]["bia"] == 10
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


COMPARE_SCENARIO = {
    "disciplines": [
        {"name": "Cálculo I", "classes": 6, "hours": 60, "unlocks": ["Física I"], "entry": True},
        {"name": "Programação", "classes": 6, "hours": 60, "unlocks": [], "entry": True},
        {"name": "Física I", "classes": 6, "hours": 60, "unlocks": [], "entry": False},
    ],
    "class_size": 2,
    "performance": {"mode_grade": 8.0, "zero_rate": 0.005, "max_rate": 0.008},
    "max_hours": 360,
    "availability": {"hours_sd": 17.5, "full_load_rate": 0.9},
    "selectivity_mean": -50.0,
    "grade_cuts": [],
    "demand_cuts": [],
    "credit_cuts": [],
    "periods": 3,
    "students_per_entry_class": 1,
    "rounds": 2,
    "seed": 5,
}

def test_the_saved_runs_are_listed_read_and_deleted_through_the_api(client):
    """O histórico é o disco: a interface lista, abre e apaga pela API."""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 1}).json()
    name = payload["saved_as"]
    assert name

    listing = client.get("/results").json()
    assert [row["name"] for row in listing] == [name]
    row = listing[0]
    assert row["kind"] == "comparison"
    assert row["bytes"] > 0
    assert row["config"]["runs"] == 1

    inteiro = client.get(f"/results/{name}").json()
    assert inteiro["config"]["runs"] == 1
    assert inteiro["result"]["arms"][0]["runs"][0]["observations"]["period"]

    assert client.delete(f"/results/{name}").status_code == 204
    assert client.get("/results").json() == []
    assert client.get(f"/results/{name}").status_code == 404
    assert client.delete(f"/results/{name}").status_code == 404


def test_a_result_name_cannot_escape_the_results_folder(client):
    """O nome vem da URL, e é só o que a pasta de resultados contém."""
    for nome in ("..", ".oculto", "sub%2Fdir"):
        assert client.get(f"/results/{nome}").status_code in (400, 404)
        assert client.delete(f"/results/{nome}").status_code in (400, 404)


def test_the_raw_rows_travel_in_the_response(client):
    """O recorte em faixas é conta de interface, e por isso as linhas cruas vão
    na resposta e o motor publica só o agregado da coorte."""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 2}).json()

    for arm in payload["arms"]:
        assert [axis["axis"] for axis in arm["series"]] == ["overall"]
        for run in arm["runs"]:
            rows = run["observations"]
            tamanhos = {len(values) for values in rows.values()}
            assert len(tamanhos) == 1, "as colunas saíram de tamanhos diferentes"
            assert all(1 <= p for p in rows["period"])
            assert all(0 <= value <= 10 for value in rows["grade_average"])
            assert all(0 <= value <= 1 for value in rows["demand"])
            assert all(won >= 0 for won in rows["won"])


def _engine_comparison(runs: int = 2):
    """A comparação pelo motor, para o que a resposta da API já não carrega."""
    request = CompareRequest(**{**COMPARE_SCENARIO, "runs": runs})
    return run_comparison(
        build_config(request), runs=runs, arms=ARMS, workers=1
    )


POPULATION = {
    "performance": {"mode_grade": 4.0, "zero_rate": 0.05, "max_rate": 0.002},
    "interest_sigma": 1,
    "max_hours": 120,
    "availability": {"hours_sd": 5.5, "full_load_rate": 0.4},
}

def test_compare_returns_one_summary_per_seed_in_every_arm(client):
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 3}).json()

    assert payload["runs"] == 3
    assert [a["key"] for a in payload["arms"]] == [
        "ranking_greedy",
        "credits_return",
    ]
    for arm in payload["arms"]:
        assert [r["seed"] for r in arm["runs"]] == [1, 2, 3]


def test_compare_runs_only_the_arms_asked_for(client):
    """Um braço só é o caso de quem está calibrando cenário: metade do tempo."""
    payload = client.post(
        "/compare", json={**COMPARE_SCENARIO, "runs": 2, "arms": ["credits_return"]}
    ).json()

    assert [a["key"] for a in payload["arms"]] == ["credits_return"]
    assert [r["seed"] for r in payload["arms"][0]["runs"]] == [1, 2]


def test_compare_orders_the_arms_canonically_whatever_the_request_says(client):
    """A tela acha o braço pela chave, então a ordem do pedido não pode vazar"""
    payload = client.post(
        "/compare",
        json={**COMPARE_SCENARIO, "runs": 1, "arms": ["credits_return", "ranking_greedy"]},
    ).json()

    assert [a["key"] for a in payload["arms"]] == ["ranking_greedy", "credits_return"]


def test_compare_rejects_an_unknown_arm(client):
    response = client.post(
        "/compare", json={**COMPARE_SCENARIO, "runs": 1, "arms": ["xpto"]}
    )

    assert response.status_code == 400
    assert "xpto" in response.json()["detail"]


def test_a_run_is_written_to_disk_in_the_history_format(client, results_dir):
    """O arquivo gravado é uma entrada de histórico: carregá-lo na interface é"""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 1}).json()

    saved = pathlib.Path(payload["saved_to"])
    assert saved.parent == results_dir
    stored = json.loads(saved.read_text(encoding="utf-8"))
    assert sorted(stored) == ["at", "config", "kind", "result"]
    assert stored["kind"] == "comparison"
    assert stored["result"]["arms"] == payload["arms"]


def test_two_runs_in_the_same_second_do_not_overwrite_each_other(client, results_dir):
    scenario = {**COMPARE_SCENARIO, "runs": 1}
    first = client.post("/compare", json=scenario).json()["saved_to"]
    second = client.post("/compare", json=scenario).json()["saved_to"]

    assert first != second
    assert len(list(results_dir.glob("*.json"))) == 2


def test_a_disk_that_refuses_does_not_fail_the_request(client, tmp_path, monkeypatch):
    """Quem pediu a simulação quer o resultado: perder uma rodada de dezenas"""
    blocked = tmp_path / "arquivo"
    blocked.write_text("não é pasta", encoding="utf-8")
    monkeypatch.setenv("LEILAO_RESULTS_DIR", str(blocked))

    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 1}).json()

    assert payload["saved_to"] is None
    assert payload["arms"]


def test_compare_reports_the_time_to_graduate_with_its_denominator(client):
    """O tempo de formatura tem viés de seleção — só existe sobre quem"""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 2}).json()

    for run in [r for arm in payload["arms"] for r in arm["runs"]]:
        assert (run["time_to_graduate"] is None) == (run["graduates"] == 0)
        if run["time_to_graduate"] is not None:
            assert 1 <= run["time_to_graduate"] <= run["periods"]


def test_compare_ignores_the_scenario_seed(client):
    """A seed do cenário não entra: ali ela vira o eixo da amostra, e as seeds"""
    first = client.post(
        "/compare", json={**COMPARE_SCENARIO, "seed": 1, "runs": 2}
    ).json()
    second = client.post(
        "/compare", json={**COMPARE_SCENARIO, "seed": 77, "runs": 2}
    ).json()

    assert first.pop("saved_to") != second.pop("saved_to")
    assert first.pop("saved_as") != second.pop("saved_as")

    assert first == second


def test_credit_quantities_exist_only_where_there_is_currency(client):
    """As três grandezas da economia saem `null` na linha de base por CR."""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 2}).json()
    chaves = ("credits_supply", "credits_spent", "credits_returned")

    for arm in payload["arms"]:
        eixo = next(
            a for a in arm["series"] if a["axis"] == "overall"
        )
        valores = eixo["groups"][0]["values"]
        for chave in chaves:
            faixas = valores[chave]
            if arm["mechanism"] == "credits":
                assert any(f is not None for f in faixas), f"{arm['key']}/{chave} vazio"
            else:
                assert all(f is None for f in faixas), f"{arm['key']}/{chave} tem moeda"


def test_the_price_cuts_split_the_offer_and_only_exist_in_the_auction():
    """O preço recorta **turmas**, não alunos — a única família assim.

    Fica no motor e não na resposta: a interface não desenha preço.
    """
    result = _engine_comparison()

    for arm in result.arms:
        cortes = arm.class_prices
        if arm.mechanism != "credits":
            assert cortes == [], f"{arm.key} tem preço sem ter moeda"
            continue
        assert {cut.axis for cut in cortes} == {
            "classes",
            "hours",
            "curriculum_period",
        }
        for cut in cortes:
            assert cut.groups, f"recorte {cut.axis} sem grupo"
            for group in cut.groups:
                faixas = group.values["mean_price"]
                assert len(faixas) == len(group.x) == len(group.n)
                assert any(f is not None for f in faixas)
                assert all(f is None or f[0] >= 1 for f in faixas)


def test_compare_reports_the_allocation_time_of_every_round():
    """O custo de rodar o mecanismo sai por braço, um ponto por (período, rodada).

    Fica no motor e não na resposta, pelo mesmo motivo do preço.
    """
    result = _engine_comparison()

    for arm in result.arms:
        series = arm.allocation_seconds
        assert series, f"braço {arm.key} saiu sem tempo de alocação"
        for period in series:
            assert 1 <= len(period) <= COMPARE_SCENARIO["rounds"]
            assert all(value >= 0 for value in period)


def test_compare_reports_one_allocation_figure_per_round(client):
    """A saturação tem uma posição por rodada do cenário, igual em todo braço —"""
    payload = client.post("/compare", json={**COMPARE_SCENARIO, "runs": 2}).json()

    rounds = COMPARE_SCENARIO["rounds"]
    for run in [r for arm in payload["arms"] for r in arm["runs"]]:
        assert len(run["allocations_per_round"]) == rounds
        assert all(value is None or value >= 0 for value in run["allocations_per_round"])

def test_trace_reproduces_the_execution_the_comparison_summarized(client):
    """O par (braço, seed) endereça uma execução do boxplot, e o traço é ela —"""
    comparison = client.post("/compare", json={**COMPARE_SCENARIO, **POPULATION, "runs": 2}).json()

    for arm in comparison["arms"]:
        for run in arm["runs"]:
            payload = client.post(
                "/trace",
                json={**COMPARE_SCENARIO, **POPULATION, "arm": arm["key"], "seed": run["seed"]},
            ).json()

            assert payload["arm"] == arm["key"]
            assert payload["seed"] == run["seed"]
            assert len(payload["periods"]) >= run["periods"]
            warmup = len(payload["periods"]) - run["periods"]
            graduated = [
                s
                for s in payload["students"]
                if s["graduated_at"] is not None and s["graduated_at"] > warmup
            ]
            assert len(graduated) == run["graduates"]


def test_trace_records_every_eligible_discipline_round_by_round(client):
    """Cada linha é uma disciplina elegível no período, com uma posição por"""
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
        has_grade = record["won_round"] is not None and not record["excluded"]
        assert (record["grade"] is not None) == has_grade
    won_in_round = [r for r in records if r["won_round"] is not None and r["won_round"] > 0]
    assert won_in_round
    for record in won_in_round:
        assert record["bids"][record["won_round"] - 1] > 0


def test_trace_marks_the_guaranteed_enrollment_of_the_newcomer(client):
    """A vaga garantida não veio de rodada nenhuma: `won_round` 0 a distingue de"""
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
        "/compare", json={**COMPARE_SCENARIO, "students_per_entry_class": 7, "runs": 2}
    )

    assert response.status_code == 400
    assert "vaga garantida" in response.json()["detail"]
