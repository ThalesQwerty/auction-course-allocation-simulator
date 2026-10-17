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

# As duas normais que descrevem a população, no lugar dos perfis que existiram
# até 08/10/2026. Notas baixas e ganho alto para o cenário produzir recursadas
# dentro do horizonte; W_a de 120 h para o teto morder.
POPULATION = {
    "grade_mean": 5,
    "grade_stddev": 2,
    "learning_gain": 3,
    "utility_sigma": 1,
    "max_hours": 120,
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
    # No primeiro período só existe a geração 1 — e, como ela acabou de
    # ingressar, o período publica a contagem e nenhuma métrica.
    assert [g["group"] for g in period["aggregate"]["by_cohort"]] == ["1"]
    assert period["aggregate"]["overall"]["active"] == 4
    assert period["aggregate"]["overall"]["metrics"] is None
    # A partir do 2º há veteranos, e aí sim há o que medir.
    assert 0 <= payload["periods"][1]["aggregate"]["overall"]["metrics"]["efficiency"] <= 1
    # nomes de disciplina com acento e espaço sobrevivem ao solver
    assert {d["name"] for d in period["disciplines"]} == {
        "Cálculo I", "Física I", "Programação"
    }


def test_simulate_grants_the_entrants_their_entry_seats(client):
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
            # psi é a soma das utilidades atendidas (eq. 51 com denominador 1,
            # a linha é normalizada sobre a grade). Para o calouro é a
            # utilidade do pacote de entrada, menor que 1.
            served = sum(r["utility"] for r in record["requests"])
            assert record["satisfaction"] == pytest.approx(served)
            assert 0 < record["satisfaction"] < 1


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
    """Omitir L = ingresso em todos os períodos; omitir as duas normais = os
    defaults do cenário."""
    payload = client.post("/simulate", json=SIMULATE_REQUEST).json()
    assert {s["entry_period"] for s in payload["students"]} == {1, 2, 3}
    assert payload["students"], "o cenário deveria produzir alunos"


def test_simulate_returns_the_cohort_cut(client):
    """O recorte vem pronto na resposta e parte a mesma população do agregado —
    é o que o seletor de agregação da tela usa."""
    payload = client.post("/simulate", json={**SIMULATE_REQUEST, **POPULATION}).json()

    for period in payload["periods"]:
        for report in [*period["rounds"], period["aggregate"]]:
            groups = [g["group"] for g in report["by_cohort"]]
            assert groups == sorted(groups, key=int)
            assert all(g is not None for g in groups)
            assert sum(g["active"] for g in report["by_cohort"]) == (
                report["overall"]["active"]
            )


def test_simulate_rejects_an_out_of_range_utility_sigma(client):
    response = client.post("/simulate", json={**SIMULATE_REQUEST, "utility_sigma": 0})
    assert response.status_code == 422


def test_the_workload_cap_bounds_every_student(client):
    """W_a é do cenário e vale para todo mundo: ninguém cursa mais que ele num
    período."""
    payload = client.post(
        "/simulate", json={**SIMULATE_REQUEST, **POPULATION, "include_histories": True}
    ).json()
    assert payload["histories"]
    for history in payload["histories"]:
        for record in history["periods"]:
            assert record["enrolled_hours"] <= POPULATION["max_hours"]


def test_simulate_rejects_entry_disciplines_heavier_than_the_workload_cap(client):
    """A matrícula garantida não escolhe quem a recebe, então a carga das
    disciplinas de entrada tem de caber em W_a."""
    response = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "max_hours": 90}
    )
    assert response.status_code == 400
    assert "não cabem na carga horária máxima" in response.json()["detail"]


def test_the_scenario_sets_the_learning_gain(client):
    """O incremento por recursada é do cenário e vale para todo aluno — mas ele
    desloca a **média** do sorteio, não a nota anterior: a matriz de notas é
    sorteada por período, então a recursada é uma nota nova, de uma normal
    centrada `learning_gain` acima.

    Por isso a prova é sobre a média e não sobre cada par: a nota média da
    tentativa n+1 fica um ganho acima da n (menos o que satura em 10), e nenhuma
    nota isolada precisa subir. Que a recursada *pode* sair pior está em
    `test_population.py::test_a_retake_shifts_the_mean_of_the_draw` — aqui não,
    porque um cenário deste tamanho tem poucas recursadas e o caso é raro
    demais para não virar teste intermitente.
    """
    payload = client.post(
        "/simulate",
        json={**SIMULATE_REQUEST, **POPULATION, "periods": 8, "include_histories": True},
    ).json()
    step = POPULATION["learning_gain"]

    by_attempt: dict[int, list[float]] = {}
    for history in payload["histories"]:
        for record in history["periods"]:
            for request in record["requests"]:
                if request["attempt"] is not None:
                    by_attempt.setdefault(request["attempt"], []).append(request["grade"])

    assert len(by_attempt.get(2, [])) > 20, "o cenário deveria ter recursadas"
    mean = lambda values: sum(values) / len(values)  # noqa: E731
    # Monotônica na média, e o salto da 1ª para a 2ª é o ganho — a saturação em
    # 10 come um pedaço, daí a folga.
    assert mean(by_attempt[2]) > mean(by_attempt[1])
    assert mean(by_attempt[2]) - mean(by_attempt[1]) == pytest.approx(step, abs=0.8)


def test_compare_returns_the_sweep_when_asked(client):
    """A varredura é opcional: pedida, vem um ponto por expoente, cada um com os
    três modelos; omitida, o campo vem nulo e o resultado é só o k canônico."""
    body = {**SIMULATE_REQUEST, **POPULATION, "utility_sigma": 1, "runs": 2}
    payload = client.post(
        "/compare",
        json={**body, "sweep": {"min_sigma": 0.5, "max_sigma": 2.5, "points": 3, "runs": 2}},
    ).json()

    sweep = payload["sweep"]
    assert sweep["canonical"] == 1
    assert [p["sigma"] for p in sweep["points"]] == [0.5, 1.5, 2.5]
    for point in sweep["points"]:
        assert [a["key"] for a in point["arms"]] == ["ranking", "credits_return", "credits"]
        # O histograma da causa vem junto de cada ponto.
        assert len(point["distribution"]) == 10
        assert sum(point["distribution"]) == pytest.approx(1.0)

    assert client.post("/compare", json=body).json()["sweep"] is None


def test_compare_rejects_an_invalid_sweep_range(client):
    """Faixa inválida é erro de requisição (400), não falha de simulação."""
    response = client.post(
        "/compare",
        json={
            **SIMULATE_REQUEST,
            **POPULATION,
            "runs": 2,
            "sweep": {"min_sigma": 3.0, "max_sigma": 0.5, "points": 4, "runs": 1},
        },
    )
    assert response.status_code == 400
    assert "máximo" in response.json()["detail"]


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


# --- /compare: o mesmo cenário nos dois mecanismos (Seção 7.3) -------------


def test_compare_returns_one_summary_per_seed_in_every_arm(client):
    payload = client.post("/compare", json={**SIMULATE_REQUEST, "runs": 3}).json()

    assert payload["runs"] == 3
    # Três modelos: a linha de base por CR e o leilão com e sem retorno.
    assert [(a["key"], a["mechanism"], a["credit_return"]) for a in payload["arms"]] == [
        ("ranking", "ranking", "none"),
        ("credits_return", "credits", "ratio"),
        ("credits", "credits", "none"),
    ]
    # As seeds vão de 1 a N e são pareadas: a i-ésima execução de cada braço
    # parte da mesma população.
    for arm in payload["arms"]:
        assert [r["seed"] for r in arm["runs"]] == [1, 2, 3]


def test_compare_returns_only_the_allocation_metrics(client):
    """Nada de crédito: orçamento, preço e retorno não existem do lado da linha
    de base, e nenhum recorte — o que se compara é o mecanismo. `periods` e
    `graduates` não são métricas: são o contexto para ler as que são."""
    payload = client.post("/compare", json={**SIMULATE_REQUEST, "runs": 2}).json()

    assert set(payload["arms"][0]["runs"][0]) == {
        "seed",
        "periods",
        "graduates",
        "efficiency",
        "fairness",
        "correlation",
        "time_to_graduate",
        "allocations_per_round",
    }


def test_compare_reports_the_time_to_graduate_with_its_denominator(client):
    """O tempo de formatura tem viés de seleção — só existe sobre quem
    concluiu —, então `graduates` anda junto. Sem concluinte, o tempo é nulo,
    não zero: zero se leria como 'formou na hora'."""
    payload = client.post("/compare", json={**SIMULATE_REQUEST, "runs": 2}).json()

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
        "/compare", json={**SIMULATE_REQUEST, "seed": 1, "credit_return": "none", "runs": 2}
    ).json()
    second = client.post(
        "/compare", json={**SIMULATE_REQUEST, "seed": 77, "credit_return": "unit", "runs": 2}
    ).json()

    assert first == second


def test_compare_reports_one_allocation_figure_per_round(client):
    """A saturação tem uma posição por rodada do cenário, igual em todo braço —
    é o decaimento entre elas que responde "satura mais rápido?"."""
    payload = client.post("/compare", json={**SIMULATE_REQUEST, "runs": 2}).json()

    rounds = SIMULATE_REQUEST["rounds"]
    for run in [r for arm in payload["arms"] for r in arm["runs"]]:
        assert len(run["allocations_per_round"]) == rounds
        assert all(value is None or value >= 0 for value in run["allocations_per_round"])


def test_the_rounds_add_up_to_the_period_allocation(client):
    """Cada rodada conta o que foi ganho nela, não o acumulado: somadas, dão as
    vagas por aluno do período inteiro. Se a soma passasse do total, o relatório
    de rodada estaria publicando o acumulado e o decaimento seria ilusório."""
    payload = client.post(
        "/simulate", json={**SIMULATE_REQUEST, "include_histories": True}
    ).json()

    for period in payload["periods"]:
        aggregate = period["aggregate"]["overall"]["metrics"]
        if aggregate is None:
            continue
        by_round = [
            r["overall"]["metrics"]["allocated"]
            for r in period["rounds"]
            if r["overall"]["metrics"] is not None
        ]
        assert sum(by_round) == aggregate["allocated"]


def test_compare_rejects_an_invalid_run_count(client):
    assert client.post("/compare", json={**SIMULATE_REQUEST, "runs": 0}).status_code == 422
    assert client.post("/compare", json={**SIMULATE_REQUEST, "runs": 500}).status_code == 422


def test_compare_rejects_an_invalid_scenario(client):
    response = client.post(
        "/compare", json={**SIMULATE_REQUEST, "students_per_period": 7, "runs": 2}
    )

    assert response.status_code == 400
    assert "vaga garantida" in response.json()["detail"]
