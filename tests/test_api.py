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


# Grade de dois períodos: "Cálculo I" e "Programação" sem pré-requisito (a
# matrícula garantida de quem ingressa) e "Física I" atrás de "Cálculo I".
SIMULATE_REQUEST = {
    "disciplines": [
        {"name": "Cálculo I", "seats": 6, "hours": 60, "prerequisites": []},
        {"name": "Programação", "seats": 6, "hours": 60, "prerequisites": []},
        {"name": "Física I", "seats": 6, "hours": 60, "prerequisites": ["Cálculo I"]},
    ],
    "periods": 3,
    "students_per_period": 4,
    "rounds": 2,
    "seed": 5,
}

PROFILES = {
    "aptitude_profiles": [
        {"name": "Exemplar", "mean": 8, "stddev": 1, "learning_gain": 3, "share": 50},
        {"name": "Instável", "mean": 5, "stddev": 2, "learning_gain": 1, "share": 50},
    ],
    "affinity_profiles": [
        {
            "name": "Focados",
            "kind": "concentrated",
            "intensity": 2,
            "max_hours": 180,
            "share": 50,
        },
        {
            "name": "Dispersos",
            "kind": "diluted",
            "intensity": 2,
            "max_hours": 120,
            "share": 50,
        },
    ],
}


def test_simulate_returns_series_by_period_and_cohort(client):
    response = client.post("/simulate", json=SIMULATE_REQUEST)
    assert response.status_code == 200
    payload = response.json()

    assert len(payload["periods"]) == 3
    # 4 por geração em 3 períodos: uma geração nova entra a cada período.
    assert len(payload["students"]) == 12
    # O período de cada disciplina sai dos pré-requisitos, por indução.
    assert payload["curriculum_periods"] == {
        "Cálculo I": 1, "Programação": 1, "Física I": 2
    }

    period = payload["periods"][0]
    assert len(period["rounds"]) == 2
    assert period["aggregate"]["round"] == 0
    assert period["aggregate"]["overall"]["group"] is None
    # No primeiro período só existe a geração 1.
    assert [g["group"] for g in period["aggregate"]["by_cohort"]] == ["1"]
    assert 0 <= period["aggregate"]["overall"]["metrics"]["efficiency"] <= 1
    # nomes de disciplina com acento e espaço sobrevivem ao solver
    assert {d["name"] for d in period["disciplines"]} == {
        "Cálculo I", "Física I", "Programação"
    }


def test_simulate_grants_the_entrants_their_first_period_seats(client):
    """Quem ingressa entra sem leilão nas disciplinas sem pré-requisito, e o
    sistema lança o gasto correspondente."""
    payload = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "include_histories": True}
    ).json()

    first = payload["periods"][0]
    granted = {d["name"]: d["granted"] for d in first["disciplines"]}
    assert granted == {"Cálculo I": 4, "Programação": 4, "Física I": 0}

    entry = {s["id"]: s["entry_period"] for s in payload["students"]}
    for history in payload["histories"]:
        for record in history["periods"]:
            if record["period"] != entry[history["student_id"]]:
                continue
            assert {r["discipline"] for r in record["requests"]} == {
                "Cálculo I", "Programação"
            }
            # won_round 0 = vaga garantida, fora do leilão.
            assert all(r["won_round"] == 0 for r in record["requests"])
            # 10 créditos repartidos em duas disciplinas: 5 em cada.
            assert all(r["paid"] == 5 for r in record["requests"])
            assert record["credits_spent"] == 10
            assert record["satisfaction"] == pytest.approx(1.0)


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
            # um lance por rodada — |R| = 2 nesta requisição
            assert len(request["bids"]) == 2
            assert (request["won_round"] is None) == (request["grade"] is None)


def test_simulate_rejects_a_prerequisite_cycle(client):
    request = {
        **SIMULATE_REQUEST,
        "disciplines": [
            {"name": "A", "seats": 6, "hours": 60, "prerequisites": ["B"]},
            {"name": "B", "seats": 6, "hours": 60, "prerequisites": ["A"]},
        ],
    }
    response = client.post("/simulate", json=request)
    assert response.status_code == 400
    assert "ciclo" in response.json()["detail"]


def test_simulate_rejects_a_generation_that_does_not_fit_the_guarantee(client):
    response = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "students_per_period": 7}
    )
    assert response.status_code == 400
    assert "menor oferta" in response.json()["detail"]


def test_simulate_accepts_an_entry_window(client):
    """L chega ao motor pela API: só os L primeiros períodos recebem geração
    nova, e os demais drenam."""
    payload = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "periods": 6, "entry_periods": 2}
    ).json()

    # 4 por geração em 2 gerações: a janela de ingresso, não o horizonte.
    assert len(payload["students"]) == 8
    assert {s["entry_period"] for s in payload["students"]} == {1, 2}

    last = payload["periods"][-1]["aggregate"]["overall"]
    assert last["population"] == 8
    # A conclusão é a única porta de saída, e o acumulado bate com o por período.
    assert sum(p["graduated_now"] for p in payload["periods"]) == last["graduated"]


def test_simulate_rejects_an_entry_window_wider_than_the_horizon(client):
    response = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "periods": 3, "entry_periods": 4}
    )
    assert response.status_code == 400
    assert "ingresso" in response.json()["detail"]


def test_simulate_without_the_optional_fields_keeps_the_defaults(client):
    """Omitir L e os perfis = ingresso em todos os períodos e um perfil neutro
    em cada eixo."""
    payload = client.post("/simulate", json=SIMULATE_REQUEST).json()
    assert {s["entry_period"] for s in payload["students"]} == {1, 2, 3}
    assert payload["aptitude_profiles"] == ["Padrão"]
    assert payload["affinity_profiles"] == ["Padrão"]
    assert {s["aptitude"] for s in payload["students"]} == {"Padrão"}




def test_simulate_returns_a_cut_per_profile_axis(client):
    """Os três recortes vêm prontos na resposta, na ordem em que o cenário
    declara os perfis — é o que o seletor de agregação da tela usa."""
    payload = client.post("/simulate", json={**SIMULATE_REQUEST, **PROFILES}).json()

    assert payload["aptitude_profiles"] == ["Exemplar", "Instável"]
    assert payload["affinity_profiles"] == ["Focados", "Dispersos"]
    assert {s["aptitude"] for s in payload["students"]} == {"Exemplar", "Instável"}
    assert {s["affinity"] for s in payload["students"]} == {"Focados", "Dispersos"}

    for period in payload["periods"]:
        for report in [*period["rounds"], period["aggregate"]]:
            assert [g["group"] for g in report["by_aptitude"]] == ["Exemplar", "Instável"]
            assert [g["group"] for g in report["by_affinity"]] == ["Focados", "Dispersos"]
            # Cada eixo parte a mesma população.
            for axis in ("by_cohort", "by_aptitude", "by_affinity"):
                assert sum(g["active"] for g in report[axis]) == report["overall"]["active"]


def test_simulate_rejects_profile_shares_that_do_not_add_up(client):
    response = client.post(
        "/simulate",
        json={
            **SIMULATE_REQUEST,
            "aptitude_profiles": [{"name": "X", "mean": 6, "stddev": 1, "share": 40}],
        },
    )
    assert response.status_code == 400
    assert "somar 100%" in response.json()["detail"]


def test_simulate_rejects_an_out_of_range_affinity_intensity(client):
    response = client.post(
        "/simulate",
        json={
            **SIMULATE_REQUEST,
            "affinity_profiles": [
                {"name": "X", "kind": "concentrated", "intensity": 0, "share": 100}
            ],
        },
    )
    assert response.status_code == 422


def test_the_affinity_profile_caps_the_workload_of_its_students(client):
    """W_a saiu do cenário e virou parâmetro do perfil de afinidade: cada aluno
    é limitado pelo teto do perfil dele, não por um teto global."""
    payload = client.post(
        "/simulate", json={**SIMULATE_REQUEST, **PROFILES, "include_histories": True}
    ).json()
    cap = {p["name"]: p["max_hours"] for p in PROFILES["affinity_profiles"]}
    affinity = {s["id"]: s["affinity"] for s in payload["students"]}

    seen = set()
    for history in payload["histories"]:
        limit = cap[affinity[history["student_id"]]]
        for record in history["periods"]:
            assert record["enrolled_hours"] <= limit
            seen.add(affinity[history["student_id"]])
    assert seen == set(cap), "os dois perfis deveriam aparecer"


def test_simulate_rejects_a_first_period_heavier_than_the_tightest_profile(client):
    """A matrícula garantida não escolhe quem a recebe, então a carga das
    disciplinas de 1º período tem de caber no perfil mais apertado."""
    response = client.post(
        "/simulate",
        json={
            **SIMULATE_REQUEST,
            "affinity_profiles": [
                {"name": "Apertado", "kind": "concentrated", "intensity": 1,
                 "max_hours": 90, "share": 100},
            ],
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "não cabem na carga horária máxima" in detail
    assert "Apertado" in detail


def test_the_aptitude_profile_sets_the_learning_gain(client):
    """O incremento por recursada saiu do cenário e virou parâmetro do perfil de
    aptidão: quem repete ganha o que o perfil dele promete."""
    payload = client.post(
        "/simulate",
        json={**SIMULATE_REQUEST, **PROFILES, "periods": 6, "include_histories": True},
    ).json()
    gain = {p["name"]: p["learning_gain"] for p in PROFILES["aptitude_profiles"]}
    aptitude = {s["id"]: s["aptitude"] for s in payload["students"]}

    retakes = 0
    for history in payload["histories"]:
        step = gain[aptitude[history["student_id"]]]
        # Maior nota obtida em cada tentativa de cada disciplina.
        best: dict[str, tuple[int, float]] = {}
        for record in history["periods"]:
            for request in record["requests"]:
                if request["attempt"] is None:
                    continue
                previous = best.get(request["discipline"])
                if previous and request["attempt"] == previous[0] + 1:
                    # eq. (33): a nota da tentativa n+1 é a da n mais o ganho,
                    # saturando em 10.
                    assert request["grade"] == pytest.approx(
                        min(10.0, round(previous[1] + step, 1))
                    )
                    retakes += 1
                best[request["discipline"]] = (request["attempt"], request["grade"])
    assert retakes > 0, "o cenário deveria ter recursadas"


def test_the_discipline_snapshot_carries_the_three_grouping_axes(client):
    """Os gráficos por disciplina agrupam por período da grade, vagas e carga
    horária — os três têm de vir na resposta, com os pedidos para a
    concorrência."""
    payload = client.post("/simulate", json=SIMULATE_REQUEST).json()
    by_name = {
        d["name"]: d for period in payload["periods"] for d in period["disciplines"]
    }
    assert by_name["Cálculo I"]["curriculum_period"] == 1
    assert by_name["Física I"]["curriculum_period"] == 2
    assert {d["hours"] for d in by_name.values()} == {60}
    assert {d["seats"] for d in by_name.values()} == {6}

    for period in payload["periods"]:
        for discipline in period["disciplines"]:
            # Quem pediu é pelo menos quem conseguiu: a vaga sai de um pedido.
            assert discipline["requests"] >= discipline["filled"]
            assert discipline["filled"] <= discipline["seats"]
