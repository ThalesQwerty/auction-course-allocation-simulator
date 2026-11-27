"""O banco de uma comparação: esquema, fila e retomada."""
from __future__ import annotations

import json
import sqlite3

import pytest

from disciplines import disciplines_from_predecessors
from profiles import single_axis
from leilao.config import SimulationConfig
from leilao.steps import steps_per_simulation
from leilao.store import (
    SCHEMA_VERSION,
    Progress,
    claim_simulation,
    create_comparison,
    fail_simulation,
    finish_comparison,
    finish_simulation,
    open_store,
    owner_token,
    pause_comparison,
    progress_of,
    requeue_stale,
    resume_comparison,
    schema_version,
    timeout_simulation,
)
from leilao.store.lifecycle import DETAIL_TABLES

GRADE = disciplines_from_predecessors(
    ("D1", 12, 60),
    ("D2", 12, 60),
    ("D3", 12, 60, ("D1",)),
    ("D4", 12, 60, ("D2",)),
)

WORKLOAD = 180


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=5,
        students_per_entry_class=3,
        rounds=2,
        max_hours=WORKLOAD,
        **single_axis(WORKLOAD),
        seed=1,
    )
    return SimulationConfig(**{**base, **overrides})


@pytest.fixture
def store(tmp_path):
    with open_store(tmp_path / "leilao.db") as connection:
        yield connection


def start(connection, *, seeds=2, arms=("ranking_greedy", "credits_return"), **kwargs):
    config = make_config(**kwargs)
    return config, create_comparison(
        connection,
        config=config,
        scenario=json.dumps({"runs": seeds}),
        seeds=seeds,
        arms=arms,
    )


def test_a_new_file_gets_the_schema_and_stamps_the_version(tmp_path):
    caminho = tmp_path / "novo.db"
    with open_store(caminho) as connection:
        assert schema_version(connection) == SCHEMA_VERSION
        tabelas = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"comparacao", "simulacao", "aluno_periodo", "solicitacao"} <= tabelas


def test_a_bank_from_another_schema_version_is_refused(tmp_path):
    caminho = tmp_path / "velho.db"
    with open_store(caminho) as connection:
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 7}")
    with pytest.raises(ValueError, match="esquema versão"):
        open_store(caminho)


def test_a_bank_from_the_previous_version_gains_the_new_columns(tmp_path):
    """A comparação antiga continua abrindo: ela sobe de versão em versão. Fica
    sem teto de passos, que a tela trata caindo na contagem, e sem o nome dos
    alunos que já gravou, que o índice trata caindo na matrícula. Fica também
    sem os contadores da intensidade de demanda, que nascem nulos: elegibilidade
    é estado de simulação, e nada fora de uma execução a recalcula."""
    caminho = tmp_path / "anterior.db"
    with open_store(caminho) as connection:
        connection.execute("ALTER TABLE comparacao DROP COLUMN etapas_total")
        connection.execute("ALTER TABLE simulacao DROP COLUMN etapas")
        connection.execute("ALTER TABLE aluno DROP COLUMN nome")
        connection.execute("DROP VIEW simulacao_valida")
        connection.execute("DROP INDEX ix_solicitacao_turma")
        connection.execute("DROP INDEX ix_turma_disciplina")
        connection.execute(
            "ALTER TABLE aluno_periodo DROP COLUMN disciplinas_elegiveis"
        )
        connection.execute(
            "ALTER TABLE aluno_periodo DROP COLUMN disciplinas_pedidas"
        )
        connection.execute("PRAGMA user_version = 2")

    with open_store(caminho) as connection:
        assert schema_version(connection) == SCHEMA_VERSION
        config, _ = start(connection, seeds=1, arms=("ranking_greedy",))
        linha = connection.execute(
            "SELECT c.etapas_total, m.etapas FROM comparacao c, simulacao m"
        ).fetchone()
        colunas = {
            row["name"] for row in connection.execute("PRAGMA table_info(aluno)")
        }
        visoes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'view'"
            )
        }
        contadores = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(aluno_periodo)")
        }
    assert linha["etapas_total"] == steps_per_simulation(config)
    assert linha["etapas"] == 0
    assert "nome" in colunas
    assert "simulacao_valida" in visoes
    assert {"disciplinas_elegiveis", "disciplinas_pedidas"} <= contadores


def test_tables_without_a_version_mean_an_interrupted_creation(tmp_path):
    caminho = tmp_path / "meio.db"
    connection = sqlite3.connect(caminho)
    connection.execute("CREATE TABLE comparacao (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="criação interrompida"):
        open_store(caminho)


def test_creating_a_comparison_lays_the_offer_and_the_queue(store):
    config, comparacao = start(store, seeds=3)

    linha = store.execute(
        "SELECT * FROM comparacao"
    ).fetchone()
    assert linha["estado"] == "pendente"
    assert linha["iniciada_em"] is None
    assert linha["seeds"] == 3
    assert linha["rodadas_teto"] == config.rounds
    assert linha["coorte_medida"] == config.measured_cohort

    turmas = store.execute(
        "SELECT COUNT(*) FROM turma"
    ).fetchone()[0]
    assert turmas == len(config.discipline_by_class())

    fila = store.execute(
        "SELECT braco, seed, estado FROM simulacao ORDER BY braco, seed"
    ).fetchall()
    assert len(fila) == 3 * 2
    assert {row["estado"] for row in fila} == {"pendente"}
    assert sorted({row["seed"] for row in fila}) == [
        config.first_seed,
        config.first_seed + 1,
        config.first_seed + 2,
    ]


def test_the_offer_carries_what_the_scenario_already_knows(store):
    config, comparacao = start(store)
    por_nome = {d.name: d for d in config.disciplines}

    for linha in store.execute(
        "SELECT * FROM turma"
    ):
        disciplina = por_nome[linha["disciplina"]]
        assert linha["carga"] == disciplina.hours
        assert linha["optativa"] == int(disciplina.elective)
        assert linha["entrada"] == int(disciplina.entry)
        assert linha["vagas"] >= 1
        assert linha["horario"]
        if disciplina.elective:
            assert linha["periodo_da_grade"] is None
        else:
            assert linha["periodo_da_grade"] >= 1

    vagas = store.execute(
        "SELECT disciplina, SUM(vagas) AS total FROM turma GROUP BY disciplina"
    ).fetchall()
    for linha in vagas:
        assert linha["total"] == por_nome[linha["disciplina"]].seats


def test_two_owners_never_claim_the_same_simulation(store):
    _, comparacao = start(store, seeds=2)
    primeiro, segundo = owner_token(), owner_token()

    pegas = []
    while True:
        dono = primeiro if len(pegas) % 2 == 0 else segundo
        claim = claim_simulation(store, owner=dono)
        if claim is None:
            break
        pegas.append(claim.simulation_id)

    assert len(pegas) == 4
    assert len(set(pegas)) == 4
    assert progress_of(store).rodando == 4


def test_the_queue_empties_and_claiming_returns_none(store):
    _, comparacao = start(store, seeds=1, arms=("ranking_greedy",))
    dono = owner_token()
    claim = claim_simulation(store, owner=dono)
    assert claim is not None
    assert claim.attempt == 1
    assert claim_simulation(store, owner=dono) is None


def test_a_dead_owner_is_what_denounces_an_interruption(store):
    """Ninguém está vivo para escrever "interrompida", então quem a denuncia é o
    dono que não está mais rodando."""
    _, comparacao = start(store, seeds=1, arms=("ranking_greedy",))
    morto = owner_token()
    claim = claim_simulation(store, owner=morto)
    assert claim is not None

    # o processo caiu aqui, deixando linhas pela metade
    store.execute(
        "INSERT INTO periodo"
        " (simulacao_id, periodo, medido, rodadas, ativos, medidos,"
        "  concluiram, jubilaram) VALUES (?, 1, 1, 2, 10, 9, 0, 0)",
        (claim.simulation_id,),
    )

    vivo = owner_token()
    assert requeue_stale(store, owner=vivo) == 1

    linha = store.execute(
        "SELECT * FROM simulacao WHERE id = ?", (claim.simulation_id,)
    ).fetchone()
    assert linha["estado"] == "pendente"
    assert linha["dono"] is None
    assert linha["iniciada_em"] is None
    assert linha["tentativas"] == 1

    for tabela in DETAIL_TABLES:
        sobrou = store.execute(
            f"SELECT COUNT(*) FROM {tabela} WHERE simulacao_id = ?",
            (claim.simulation_id,),
        ).fetchone()[0]
        assert sobrou == 0, tabela

    de_novo = claim_simulation(store, owner=vivo)
    assert de_novo is not None
    assert de_novo.attempt == 2


def test_my_own_running_simulation_is_not_requeued(store):
    """Senão um worker derrubaria o trabalho do vizinho no meio."""
    _, comparacao = start(store, seeds=1, arms=("ranking_greedy",))
    dono = owner_token()
    claim_simulation(store, owner=dono)
    assert requeue_stale(store, owner=dono) == 0
    assert progress_of(store).rodando == 1


def test_a_failed_simulation_keeps_its_rows_and_is_not_requeued(store):
    """As linhas parciais servem de autópsia, e uma exceção determinística se
    repetiria igual: tentar de novo viraria laço."""
    _, comparacao = start(store, seeds=1, arms=("ranking_greedy",))
    dono = owner_token()
    claim = claim_simulation(store, owner=dono)
    store.execute(
        "INSERT INTO periodo"
        " (simulacao_id, periodo, medido, rodadas, ativos, medidos,"
        "  concluiram, jubilaram) VALUES (?, 1, 1, 2, 10, 9, 0, 0)",
        (claim.simulation_id,),
    )
    fail_simulation(
        store, simulation_id=claim.simulation_id, error="PLI inviável", duration_ms=120
    )

    linha = store.execute(
        "SELECT * FROM simulacao WHERE id = ?", (claim.simulation_id,)
    ).fetchone()
    assert linha["estado"] == "falhou"
    assert linha["erro"] == "PLI inviável"
    assert linha["dono"] is None
    assert (
        store.execute(
            "SELECT COUNT(*) FROM periodo WHERE simulacao_id = ?",
            (claim.simulation_id,),
        ).fetchone()[0]
        == 1
    )

    assert requeue_stale(store, owner=owner_token()) == 0
    assert claim_simulation(store, owner=dono) is None
    assert progress_of(store).done


def test_progress_counts_every_state_and_knows_when_the_queue_is_empty(store):
    _, comparacao = start(store, seeds=2, arms=("ranking_greedy",))
    dono = owner_token()

    assert progress_of(store) == Progress(pendente=2)
    assert not progress_of(store).done

    primeira = claim_simulation(store, owner=dono)
    finish_simulation(
        store, simulation_id=primeira.simulation_id, periods=5, duration_ms=66_000
    )
    segunda = claim_simulation(store, owner=dono)
    fail_simulation(store, simulation_id=segunda.simulation_id, error="x")

    andamento = progress_of(store)
    assert (andamento.concluida, andamento.falhou, andamento.total) == (1, 1, 2)
    assert andamento.done


def test_the_comparison_sums_its_duration_across_pauses(store):
    _, comparacao = start(store, seeds=1, arms=("ranking_greedy",))

    resume_comparison(store)
    primeiro = store.execute(
        "SELECT iniciada_em, estado FROM comparacao"
    ).fetchone()
    assert primeiro["estado"] == "rodando"
    assert primeiro["iniciada_em"] is not None

    pause_comparison(store)
    finish_comparison(store, elapsed_ms=1_000)

    resume_comparison(store)
    depois = store.execute(
        "SELECT iniciada_em FROM comparacao"
    ).fetchone()
    assert depois["iniciada_em"] == primeiro["iniciada_em"], "o início é carimbado uma vez"

    finish_comparison(store, elapsed_ms=2_500)
    fechada = store.execute(
        "SELECT estado, duracao_ms, terminada_em FROM comparacao"
    ).fetchone()
    assert fechada["estado"] == "concluida"
    assert fechada["duracao_ms"] == 3_500
    assert fechada["terminada_em"] is not None


def test_an_unknown_state_is_refused_by_the_check(store):
    _, comparacao = start(store, seeds=1, arms=("ranking_greedy",))
    with pytest.raises(sqlite3.IntegrityError):
        store.execute(
            "UPDATE comparacao SET estado = 'rampeamento'"
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.execute(
            "UPDATE simulacao SET estado = 'pausada'"
        )


def test_the_comparison_table_refuses_a_second_row(store):
    """Há uma comparação por arquivo: `unica` não é identidade, é guarda."""
    start(store, seeds=1, arms=("ranking_greedy",))
    assert store.execute("SELECT COUNT(*) FROM comparacao").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        store.execute(
            "INSERT INTO comparacao"
            " (criada_em, estado, cenario, seeds, bracos, rodadas_teto)"
            " VALUES ('agora', 'pendente', '{}', 1, 'x', 1)"
        )


def test_a_comparison_needs_a_seed_and_an_arm(store):
    config = make_config()
    with pytest.raises(ValueError, match="uma seed"):
        create_comparison(
            store, config=config, scenario="{}", seeds=0, arms=("ranking_greedy",)
        )
    with pytest.raises(ValueError, match="um braço"):
        create_comparison(store, config=config, scenario="{}", seeds=1, arms=())


def test_a_timed_out_seed_leaves_the_result_in_both_arms(store):
    """O descarte é pareado: a seed que estourou de um lado sai dos dois, senão
    os braços seriam reduzidos sobre conjuntos de seeds diferentes."""
    start(store, seeds=2)
    store.execute(
        "UPDATE simulacao SET estado = 'concluida' WHERE seed IN (1, 2)"
    )
    store.execute(
        "UPDATE simulacao SET estado = 'estourou'"
        " WHERE seed = 1 AND braco = 'credits_return'"
    )
    sobraram = {
        (row["braco"], row["seed"])
        for row in store.execute("SELECT braco, seed FROM simulacao_valida")
    }
    assert sobraram == {("credits_return", 2), ("ranking_greedy", 2)}


def test_the_timeout_is_a_state_of_its_own_in_the_progress(store):
    _, _ = start(store, seeds=1)
    claim = claim_simulation(store, owner=owner_token())
    timeout_simulation(
        store, simulation_id=claim.simulation_id, error="alocação não resolvida em 900 s"
    )
    andamento = progress_of(store)
    assert andamento.estourou == 1
    assert andamento.falhou == 0
    assert andamento.total == 2
    linha = store.execute(
        "SELECT estado, erro FROM simulacao WHERE id = ?", (claim.simulation_id,)
    ).fetchone()
    assert linha["estado"] == "estourou"
    assert "900 s" in linha["erro"]
