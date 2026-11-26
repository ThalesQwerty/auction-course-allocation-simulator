"""Rodar uma comparação dentro do banco, de ponta a ponta."""
from __future__ import annotations

import json

import pytest

from disciplines import disciplines_from_predecessors
from profiles import single_axis
from leilao.config import SimulationConfig
from leilao.steps import total_steps
from leilao.store import (
    create_comparison,
    open_store,
    pause_comparison,
    progress_of,
    run_into_store,
)

GRADE = disciplines_from_predecessors(
    ("D1", 12, 60),
    ("D2", 12, 60),
    ("D3", 12, 60, ("D1",)),
    ("D4", 12, 60, ("D2",)),
)

WORKLOAD = 180

ARMS = ("ranking_greedy", "credits_return")


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=7,
        warmup_periods=3,
        measured_cohorts=1,
        max_residence=4,
        students_per_entry_class=3,
        rounds=2,
        max_hours=WORKLOAD,
        elective_hours=0,
        **single_axis(WORKLOAD),
        seed=1,
    )
    return SimulationConfig(**{**base, **overrides})


@pytest.fixture
def ready(tmp_path):
    """Um banco com uma comparação de 2 seeds × 2 braços, nada rodado."""
    config = make_config()
    bank = tmp_path / "leilao.db"
    connection = open_store(bank)
    comparison = create_comparison(
        connection,
        config=config,
        scenario=json.dumps({"runs": 2}),
        seeds=2,
        arms=ARMS,
    )
    yield connection, comparison, config, bank
    connection.close()


def test_the_steps_given_add_up_to_the_ceiling_computed_at_creation(ready):
    """O andamento fecha em 100%: o teto sai da criação e a execução o alcança,
    ainda que períodos tenham fechado antes do teto de rodadas."""
    connection, _, config, bank = ready

    teto = connection.execute("SELECT etapas_total FROM comparacao").fetchone()
    assert teto["etapas_total"] == total_steps(config, seeds=2, arms=len(ARMS))

    run_into_store(connection, config=config, bank=bank)

    dadas = connection.execute("SELECT SUM(etapas) AS etapas FROM simulacao").fetchone()
    assert dadas["etapas"] == teto["etapas_total"]


def test_running_empties_the_queue_and_closes_the_comparison(ready):
    connection, comparison, config, bank = ready

    vistas = []
    andamento = run_into_store(
        connection,
        config=config,
        bank=bank,
        on_done=lambda claim, _: vistas.append((claim.arm, claim.seed)),
    )

    assert andamento.concluida == 4
    assert andamento.falhou == 0
    assert andamento.done
    assert sorted(vistas) == [(arm, seed) for arm in sorted(ARMS) for seed in (1, 2)]

    linha = connection.execute(
        "SELECT estado, terminada_em, duracao_ms FROM comparacao"
    ).fetchone()
    assert linha["estado"] == "concluida"
    assert linha["terminada_em"] is not None
    assert linha["duracao_ms"] > 0

    for simulacao in connection.execute(
        "SELECT * FROM simulacao"
    ):
        assert simulacao["estado"] == "concluida"
        assert simulacao["dono"] is None
        assert simulacao["periodos"] == config.periods
        assert simulacao["duracao_ms"] >= 0


def test_the_rows_reproduce_what_the_engine_measured(ready):
    """O banco tem de dizer o mesmo que o motor diria: é o que torna a consulta
    substituta legítima do `summarize`."""
    from leilao.comparison import ARM_BY_KEY, arm_config
    from leilao.simulation import run_simulation

    connection, comparison, config, bank = ready
    run_into_store(connection, config=config, bank=bank)

    for arm in ARMS:
        result = run_simulation(
            arm_config(config, arm=ARM_BY_KEY[arm], seed=1), histories="medidos"
        )
        simulacao = connection.execute(
            "SELECT id FROM simulacao WHERE braco = ? AND seed = 1", (arm,),
        ).fetchone()["id"]

        esperado = {
            (point.student_id, point.period): point
            for period in result.observed
            for point in period.points
        }
        linhas = connection.execute(
            "SELECT * FROM aluno_periodo WHERE simulacao_id = ?", (simulacao,)
        ).fetchall()
        assert len(linhas) == len(esperado) > 0

        for linha in linhas:
            point = esperado[(linha["aluno"], linha["periodo"])]
            assert linha["cr"] == pytest.approx(point.grade_average)
            assert linha["satisfacao"] == pytest.approx(point.satisfaction)
            assert linha["reserva"] == pytest.approx(point.reserve)
            assert linha["progresso"] == pytest.approx(point.progress)
            assert linha["vagas"] == point.won
            if point.attendance is None:
                assert linha["aproveitamento"] is None
            else:
                assert linha["aproveitamento"] == pytest.approx(point.attendance)


def test_only_the_measured_cohort_has_a_script(ready):
    connection, comparison, config, bank = ready
    run_into_store(connection, config=config, bank=bank)

    alunos = connection.execute(
        "SELECT medido, COUNT(*) AS quantos FROM aluno"
        " WHERE simulacao_id = (SELECT MIN(id) FROM simulacao)"
        " GROUP BY medido"
    ).fetchall()
    por_flag = {linha["medido"]: linha["quantos"] for linha in alunos}
    assert por_flag[0] > 0, "a demanda de fundo tem de estar lá para a flag significar algo"
    assert por_flag[1] > 0

    fora = connection.execute(
        "SELECT COUNT(*) FROM aluno_periodo ap"
        "  JOIN aluno a ON a.simulacao_id = ap.simulacao_id AND a.aluno = ap.aluno"
        " WHERE a.medido = 0",
    ).fetchone()[0]
    assert fora == 0, "só a coorte medida tem linha de período"


def test_every_request_row_points_at_a_class_of_the_offer(ready):
    connection, comparison, config, bank = ready
    run_into_store(connection, config=config, bank=bank)

    orfas = connection.execute(
        "SELECT COUNT(*) FROM solicitacao s"
        "  JOIN simulacao m ON m.id = s.simulacao_id"
        "  LEFT JOIN turma t ON t.turma = s.turma"
        " WHERE t.turma IS NULL"
    ).fetchone()[0]
    assert orfas == 0

    assert (
        connection.execute("SELECT COUNT(*) FROM solicitacao").fetchone()[0] > 0
    )


def test_pausing_stops_at_the_boundary_and_running_again_resumes(ready):
    connection, comparison, config, bank = ready

    def pausar(claim, andamento):
        if andamento.concluida == 1:
            pause_comparison(connection)

    primeiro = run_into_store(
        connection, config=config, bank=bank, on_done=pausar
    )
    assert primeiro.concluida == 1
    assert primeiro.pendente == 3
    assert not primeiro.done
    assert (
        connection.execute(
            "SELECT estado FROM comparacao"
        ).fetchone()["estado"]
        == "pausada"
    )

    segundo = run_into_store(connection, config=config, bank=bank)
    assert segundo.done
    assert segundo.concluida == 4


def test_an_interrupted_simulation_is_redone_without_duplicating_rows(ready):
    """A retomada apaga as linhas parciais antes de refazer, senão a chave
    primária recusaria o INSERT da segunda tentativa."""
    connection, comparison, config, bank = ready

    def derrubar(claim, andamento):
        if andamento.concluida == 1:
            connection.execute(
                "UPDATE simulacao SET estado = 'rodando', dono = 'outro-processo'"
                " WHERE id = ?",
                (claim.simulation_id,),
            )
            pause_comparison(connection)

    run_into_store(
        connection, config=config, bank=bank, on_done=derrubar
    )
    andamento = run_into_store(connection, config=config, bank=bank)

    assert andamento.done
    assert andamento.concluida == 4
    assert (
        connection.execute(
            "SELECT MAX(tentativas) FROM simulacao"
        ).fetchone()[0]
        == 1
    )
    duplicadas = connection.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT simulacao_id, aluno, periodo FROM aluno_periodo"
        "   GROUP BY simulacao_id, aluno, periodo HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    assert duplicadas == 0


def test_the_offer_of_each_period_is_recorded(ready):
    """A turma por período é o ambiente que a demanda de fundo produziu."""
    connection, comparison, config, bank = ready
    run_into_store(connection, config=config, bank=bank)

    linhas = connection.execute(
        "SELECT tp.*, m.braco FROM turma_periodo tp"
        "  JOIN simulacao m ON m.id = tp.simulacao_id"
    ).fetchall()
    assert linhas

    for linha in linhas:
        assert linha["concedidas"] <= linha["preenchidas"] <= linha["vagas"]
        assert linha["aprovacoes"] <= linha["preenchidas"]
        assert linha["exclusoes"] <= linha["preenchidas"]
        if linha["braco"] == "ranking_greedy":
            assert linha["preco_medio"] is None, "sem moeda não há preço"

    orfas = connection.execute(
        "SELECT COUNT(*) FROM turma_periodo tp"
        "  JOIN simulacao m ON m.id = tp.simulacao_id"
        "  LEFT JOIN turma t ON t.turma = tp.turma"
        " WHERE t.turma IS NULL"
    ).fetchone()[0]
    assert orfas == 0


def test_handing_each_period_over_means_nothing_is_accumulated():
    """É o ganho que a escrita incremental compra: o que crescia era a lista de
    relatórios e o histórico de todo aluno, e os dois param de existir."""
    from leilao.simulation import run_simulation

    config = make_config()
    guardados = []
    enxuto = run_simulation(
        config, histories="medidos", on_period=guardados.append
    )

    assert enxuto.periods == [], "o relatório de período não fica"
    assert enxuto.histories == [], "o histórico não fica"
    assert len(guardados) == config.periods, "cada período foi entregue uma vez"
    assert enxuto.students, "o resumo por aluno continua saindo"

    cheio = run_simulation(config, histories="medidos")
    assert [s.grade_average for s in cheio.students] == [
        s.grade_average for s in enxuto.students
    ], "entregar o período não muda o que a simulação faz"


def test_the_reserve_band_follows_the_student_lifetime_mean(tmp_path):
    """A faixa da utilidade de reserva não é a do período: é a média dos
    períodos do aluno, e por isso ele não troca de faixa ao longo da série."""
    from leilao.store.views import band_series

    config = make_config(
        selectivity_mean=0.7, selectivity_fluctuation=0.3, students_per_entry_class=6
    )
    bank = tmp_path / "uma.db"
    connection = open_store(bank)
    create_comparison(
        connection,
        config=config,
        scenario=json.dumps({"runs": 1}),
        seeds=1,
        arms=ARMS,
    )
    run_into_store(connection, config=config, bank=bank)

    cortes = (0.15, 0.33)
    serie = band_series(
        connection, axis="reserve", cuts=cortes, low=0.0, high=1.0, decimals=3
    )
    nomes = serie["groups"]

    medias = {
        (linha["simulacao_id"], linha["aluno"]): linha["media"]
        for linha in connection.execute(
            "SELECT simulacao_id, aluno, AVG(reserva) AS media"
            "  FROM aluno_periodo GROUP BY simulacao_id, aluno"
        )
    }
    primeiro = connection.execute(
        "SELECT MIN(periodo) FROM periodo WHERE medido = 1"
    ).fetchone()[0]
    esperado: dict[tuple[str, str, int], int] = {}
    for linha in connection.execute(
        "SELECT m.braco, ap.simulacao_id, ap.aluno, ap.periodo"
        "  FROM aluno_periodo ap JOIN simulacao m ON m.id = ap.simulacao_id"
    ):
        media = medias[(linha["simulacao_id"], linha["aluno"])]
        faixa = nomes[sum(1 for corte in cortes if media >= corte)]
        chave = (linha["braco"], faixa, linha["periodo"] - primeiro + 1)
        esperado[chave] = esperado.get(chave, 0) + 1

    assert len({faixa for _, faixa, _ in esperado}) > 1, (
        "o cenário tem de povoar mais de uma faixa, senão nada se afere"
    )
    atravessa = connection.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT simulacao_id, aluno FROM aluno_periodo"
        "   GROUP BY simulacao_id, aluno"
        "  HAVING MIN(reserva) < ? AND MAX(reserva) >= ?)",
        (cortes[0], cortes[0]),
    ).fetchone()[0]
    assert atravessa, "o corte por período tem de mover alguém, senão dá no mesmo"

    visto = 0
    for braco, grupos in serie["arms"].items():
        for grupo in grupos:
            for periodo, quartis in zip(grupo["x"], grupo["values"]["students"]):
                assert quartis[1] == esperado[(braco, grupo["group"], periodo)]
                visto += 1

    assert visto == len(esperado) > 0
    connection.close()


def test_the_series_counts_the_periods_of_the_cohort(ready):
    """O eixo começa no ingresso da coorte: o aquecimento não aparece, e o
    primeiro ponto é 1 e não o período absoluto em que a coorte entrou."""
    from leilao.store.views import band_series

    connection, comparison, config, bank = ready
    run_into_store(connection, config=config, bank=bank)

    serie = band_series(connection)
    medidos = config.periods - config.first_measured_period + 1

    assert config.first_measured_period > 1, "o cenário tem de ter aquecimento"
    assert serie["arms"]
    for grupos in serie["arms"].values():
        for grupo in grupos:
            # O último período do horizonte pode não ter medido ninguém: a
            # coorte se esvazia antes dele. O que se afere é a origem.
            assert grupo["x"] == list(range(1, len(grupo["x"]) + 1))
            assert 1 < len(grupo["x"]) <= medidos


def test_the_cohorts_observed_stack_on_the_same_axis(tmp_path):
    """Com mais de uma coorte observada, o eixo continua sendo o período local:
    todas as coortes contribuem para o ponto 1, qualquer que seja o ingresso."""
    from leilao.store.views import band_series

    config = make_config(periods=8, warmup_periods=3, measured_cohorts=2)
    bank = tmp_path / "duas.db"
    connection = open_store(bank)
    create_comparison(
        connection,
        config=config,
        scenario=json.dumps({"runs": 1}),
        seeds=1,
        arms=ARMS,
    )
    run_into_store(connection, config=config, bank=bank)

    ingressos = {
        linha["ingresso"]
        for linha in connection.execute(
            "SELECT DISTINCT ingresso FROM aluno WHERE medido = 1"
        )
    }
    assert ingressos == {4, 5}

    por_braco = {
        linha["braco"]: linha["alunos"]
        for linha in connection.execute(
            "SELECT m.braco, COUNT(*) AS alunos"
            "  FROM aluno a JOIN simulacao m ON m.id = a.simulacao_id"
            " WHERE a.medido = 1 GROUP BY m.braco"
        )
    }

    serie = band_series(connection)
    assert serie["arms"]
    for braco, grupos in serie["arms"].items():
        for grupo in grupos:
            assert grupo["x"][0] == 1
            assert grupo["values"]["students"][0][1] == por_braco[braco], (
                "no período local 1 estão as duas coortes inteiras"
            )
    connection.close()


def test_the_trace_comes_from_the_bank_and_not_from_a_rerun(ready):
    """O traço é consulta, não simulação: o que ele mostra já foi gravado.

    O que o banco não tem fica declarado aqui: só a coorte medida tem roteiro,
    e dela só a turma que ela moveu — a elegível e não pedida não virou linha.
    """
    from leilao.store.queries import SemSimulacao, trace_script

    connection, comparison, config, bank = ready
    run_into_store(connection, config=config, bank=bank)

    traco = trace_script(connection, arm=ARMS[0], seed=1)

    assert traco["arm"] == ARMS[0] and traco["seed"] == 1
    assert traco["disciplines"], "a oferta vem da tabela de turmas"
    assert set(traco["classes"]) == set(traco["disciplines"])
    assert traco["periods"], "cada período traz a oferta dele"
    assert all(ponto["disciplines"] for ponto in traco["periods"])

    medida = {
        linha["aluno"]
        for linha in connection.execute(
            "SELECT aluno FROM aluno a JOIN simulacao m ON m.id = a.simulacao_id"
            " WHERE m.braco = ? AND m.seed = 1 AND a.medido = 1",
            (ARMS[0],),
        )
    }
    assert {aluno["id"] for aluno in traco["students"]} == medida
    assert all(aluno["name"] for aluno in traco["students"])
    assert {h["student_id"] for h in traco["histories"]} <= medida

    linhas = sum(
        len(periodo["requests"])
        for historia in traco["histories"]
        for periodo in historia["periods"]
    )
    gravadas = connection.execute(
        "SELECT COUNT(*) FROM solicitacao s JOIN simulacao m ON m.id = s.simulacao_id"
        " WHERE m.braco = ? AND m.seed = 1",
        (ARMS[0],),
    ).fetchone()[0]
    assert linhas == gravadas > 0

    with pytest.raises(SemSimulacao):
        trace_script(connection, arm=ARMS[0], seed=99)


def test_a_timed_out_allocation_marks_the_simulation_and_the_queue_goes_on(
    ready, monkeypatch
):
    """O ponto do teto é a simulação travada não segurar a fila: ela fica com
    estado próprio, a fila continua, e a seed sai do resultado nos dois braços.
    """
    from leilao import auction
    from leilao.wdp_solver import AllocationTimeout

    connection, _, config, bank = ready

    def estoura(problem, **kwargs):
        raise AllocationTimeout("alocação não resolvida em 900 s")

    monkeypatch.setattr(auction, "solve_wdp", estoura)

    andamento = run_into_store(connection, config=config, bank=bank)

    assert andamento.estourou == 2
    assert andamento.concluida == 2
    assert andamento.falhou == 0
    assert andamento.done

    estados = {
        (row["braco"], row["seed"]): row["estado"]
        for row in connection.execute("SELECT braco, seed, estado FROM simulacao")
    }
    assert estados[("credits_return", 1)] == "estourou"
    assert estados[("credits_return", 2)] == "estourou"
    assert estados[("ranking_greedy", 1)] == "concluida"

    erro = connection.execute(
        "SELECT erro FROM simulacao WHERE braco = 'credits_return' AND seed = 1"
    ).fetchone()
    assert "900 s" in erro["erro"]

    assert connection.execute("SELECT estado FROM comparacao").fetchone()[
        "estado"
    ] == "concluida"
    assert connection.execute(
        "SELECT COUNT(*) AS quantas FROM simulacao_valida"
    ).fetchone()["quantas"] == 0
