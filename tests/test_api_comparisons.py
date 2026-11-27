"""As rotas das comparações: um banco por comparação, endereçadas pelo nome."""
from __future__ import annotations

import json
import logging
import sys

import pytest
from fastapi.testclient import TestClient

from leilao.api.main import app
from test_api import COMPARE_SCENARIO


@pytest.fixture(autouse=True)
def banks(tmp_path, monkeypatch):
    monkeypatch.setenv("LEILAO_RESULTS_DIR", str(tmp_path / "resultados"))
    return tmp_path / "resultados"


@pytest.fixture
def client():
    return TestClient(app)


def create(client, runs: int = 2, **overrides):
    response = client.post(
        "/comparacoes", json={**COMPARE_SCENARIO, "runs": runs, **overrides}
    )
    assert response.status_code == 201, response.text[:400]
    return response.json()


def test_the_polling_route_is_the_only_one_the_access_log_drops():
    """A tela repete essa consulta a cada 5 s, e uma linha por consulta afogaria
    no terminal o progresso que o motor imprime."""
    from leilao.api.main import QuietPolling

    filtro = QuietPolling()

    def linha(metodo: str, caminho: str) -> logging.LogRecord:
        return logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            "",
            0,
            '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1:1", metodo, caminho, "1.1", 200),
            None,
        )

    assert not filtro.filter(linha("GET", "/comparacoes/comparacao-1"))
    assert filtro.filter(linha("GET", "/comparacoes/comparacao-1/series"))
    assert filtro.filter(linha("GET", "/comparacoes"))
    assert filtro.filter(linha("POST", "/comparacoes/comparacao-1"))
    assert filtro.filter(linha("DELETE", "/comparacoes/comparacao-1"))


def test_creating_lays_the_queue_without_running_anything(client):
    criada = create(client)
    assert criada["estado"] == "pendente"
    assert criada["pendentes"] == 4
    assert criada["concluidas"] == 0
    assert criada["iniciada_em"] is None
    assert {s["estado"] for s in criada["simulacoes"]} == {"pendente"}


def test_each_comparison_gets_its_own_file(client, banks):
    """Apagar é `unlink` e arquivar é guardar um arquivo."""
    primeira = create(client, runs=1)
    segunda = create(client, runs=2)
    assert primeira["nome"] != segunda["nome"]

    lista = client.get("/comparacoes").json()
    assert {row["nome"] for row in lista} == {primeira["nome"], segunda["nome"]}
    assert len(list(banks.glob("comparacao-*.db"))) == 2, "um arquivo por comparação"


def test_running_empties_the_queue(client):
    nome = create(client)["nome"]
    assert client.post(f"/comparacoes/{nome}/rodar").status_code == 202

    estado = client.get(f"/comparacoes/{nome}").json()
    assert estado["estado"] == "concluida"
    assert (estado["concluidas"], estado["falhas"]) == (4, 0)
    assert estado["duracao_ms"] > 0
    assert all(s["periodos_gravados"] > 0 for s in estado["simulacoes"])


def test_the_result_is_the_head_the_screen_opens_with(client):
    """A tela abre com o cabeçalho: dele saem o cenário, as seeds e os braços."""
    criada = create(client, runs=2)
    nome = criada["nome"]
    resultado = client.get(f"/comparacoes/{nome}/resultado").json()

    assert resultado["nome"] == nome
    assert resultado["seeds"] == 2
    assert resultado["bracos"] == criada["bracos"]
    assert json.loads(resultado["cenario"])["runs"] == 2
    assert set(resultado) | {"simulacoes"} == set(criada)


def test_the_series_comes_reduced_from_the_api(client):
    """A tela não transforma: a consulta já devolve mediana e interquartil."""
    nome = create(client, runs=3)["nome"]
    client.post(f"/comparacoes/{nome}/rodar")

    geral = client.get(f"/comparacoes/{nome}/series").json()
    assert geral["axis"] == "overall"
    assert geral["groups"] == ["overall"]
    assert set(geral["arms"]) == {"ranking_greedy", "credits_return"}

    for grupos in geral["arms"].values():
        grupo = grupos[0]
        assert grupo["x"], "os períodos medidos"
        assert grupo["n"] == [3] * len(grupo["x"]), "as três seeds daquele braço"
        for faixa in grupo["values"]["satisfaction"]:
            assert faixa is None or faixa[0] <= faixa[1] <= faixa[2]
        assert any(grupo["values"]["fairness"])


def test_the_bands_are_cut_in_sql_with_the_asked_cuts(client):
    nome = create(client, runs=2)["nome"]
    client.post(f"/comparacoes/{nome}/rodar")

    recorte = client.get(
        f"/comparacoes/{nome}/series?eixo=grade_average&cortes=5,7"
    ).json()
    assert recorte["groups"] == ["0–5", "5–7", "7–10"]
    assert recorte["arms"], "cada braço com os seus grupos"

    outro = client.get(
        f"/comparacoes/{nome}/series?eixo=grade_average&cortes=3.5,5,6.5,8"
    ).json()
    assert outro["groups"] == ["0–3,5", "3,5–5", "5–6,5", "6,5–8", "8–10"]


def test_the_curve_shares_its_x_between_the_arms(client):
    """As bordas saem dos quantis dos dois braços juntos: sem isso as linhas
    não se comparam ponto a ponto."""
    nome = create(client, runs=3)["nome"]
    client.post(f"/comparacoes/{nome}/rodar")

    curva = client.get(f"/comparacoes/{nome}/curva?eixo=grade_average&pontos=4").json()
    assert curva["axis"] == "grade_average"
    posicoes = {
        braco: [ponto["x"] for ponto in metricas["satisfaction"]]
        for braco, metricas in curva["arms"].items()
    }
    assert len(posicoes) == 2
    assert len(set(map(tuple, posicoes.values()))) == 1, posicoes
    for metricas in curva["arms"].values():
        assert set(metricas) == {
            "satisfaction",
            "attendance",
            "progress",
            "mean_round",
        }
        for ponto in metricas["satisfaction"]:
            assert ponto["q1"] <= ponto["median"] <= ponto["q3"]
            assert ponto["n"] >= 1


def test_the_history_is_a_query_and_not_a_rerun(client):
    """O histórico sai do banco. Nada de reconstruir o cenário: um cenário
    gravado que a validação de hoje recusaria ainda assim tem o que mostrar.

    São quatro consultas estreitas, e não uma simulação inteira: o índice não
    carrega roteiro, e o roteiro não carrega os outros alunos.
    """
    nome = create(client)["nome"]
    client.post(f"/comparacoes/{nome}/rodar")
    sufixo = "braco=ranking_greedy&seed=1"

    alunos = client.get(f"/comparacoes/{nome}/traco/alunos?{sufixo}")
    assert alunos.status_code == 200, alunos.text[:400]
    indice = alunos.json()
    assert indice["braco"] == "ranking_greedy" and indice["seed"] == 1
    assert indice["alunos"] and indice["carga_obrigatoria"] > 0
    assert all(linha["nome"] for linha in indice["alunos"])
    assert all(
        linha["saida"] in ("formado", "jubilado") for linha in indice["alunos"]
    )

    oferta = client.get(f"/comparacoes/{nome}/traco/disciplinas?{sufixo}").json()
    assert oferta["disciplinas"]

    aluno = indice["alunos"][0]["aluno"]
    roteiro = client.get(f"/comparacoes/{nome}/traco/aluno/{aluno}?{sufixo}").json()
    assert roteiro["aluno"]["aluno"] == aluno
    assert all(periodo["solicitacoes"] for periodo in roteiro["periodos"])

    disciplina = oferta["disciplinas"][0]["disciplina"]
    historia = client.get(
        f"/comparacoes/{nome}/traco/disciplina/{disciplina}?{sufixo}"
    ).json()
    assert historia["disciplina"]["disciplina"] == disciplina
    assert all(periodo["solicitacoes"] for periodo in historia["periodos"])

    vazio = client.get(f"/comparacoes/{nome}/traco/alunos?braco=ranking_greedy&seed=99")
    assert vazio.status_code == 404


def test_the_boxes_come_ready_with_the_pairing(client):
    nome = create(client, runs=3)["nome"]
    client.post(f"/comparacoes/{nome}/rodar")

    caixas = client.get(f"/comparacoes/{nome}/caixas").json()
    assert caixas["baseline"] == "ranking_greedy"
    assert len(caixas["seeds"]) == 6, "uma linha por (braço, seed)"

    for braco, metricas in caixas["arms"].items():
        caixa = metricas["satisfaction"]
        assert (
            caixa["min"] <= caixa["q1"] <= caixa["median"] <= caixa["q3"] <= caixa["max"]
        )
        assert caixa["n"] == 3
        assert caixa["paired"]["comparable"] == 3
        assert 0 <= caixa["paired"]["up"] <= 3
        if braco == caixas["baseline"]:
            assert caixa["paired"]["up"] == 0, "ninguém supera a si mesmo"


def test_the_graduation_fraction_never_passes_one(client):
    """`periodo.concluiram` conta toda coorte; a fração só olha a medida."""
    nome = create(client)["nome"]
    client.post(f"/comparacoes/{nome}/rodar")
    geral = client.get(f"/comparacoes/{nome}/series").json()

    for grupos in geral["arms"].values():
        fracoes = [
            faixa[1] for faixa in grupos[0]["values"]["graduation_rate"] if faixa
        ]
        assert all(0.0 <= fracao <= 1.0 for fracao in fracoes), fracoes
        assert fracoes == sorted(fracoes), "é acumulada, então não desce"


def test_pausing_marks_the_state_and_running_again_is_the_resume(client):
    nome = create(client)["nome"]
    assert client.post(f"/comparacoes/{nome}/pausar").json()["estado"] == "pausada"

    client.post(f"/comparacoes/{nome}/rodar")
    retomada = client.get(f"/comparacoes/{nome}").json()
    assert retomada["estado"] == "concluida"
    assert retomada["concluidas"] == 4


def test_deleting_takes_the_file_and_everything_in_it(client, banks):
    from leilao.api import comparisons
    from leilao.store import store

    nome = create(client, runs=1)["nome"]
    client.post(f"/comparacoes/{nome}/rodar")

    tabelas = ("turma", "simulacao", "aluno", "periodo", "rodada",
               "aluno_periodo", "solicitacao", "turma_periodo")
    with store(comparisons.bank_path(nome), create=False) as connection:
        antes = {
            t: connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in tabelas
        }
    assert all(quantas > 0 for quantas in antes.values()), antes

    assert client.delete(f"/comparacoes/{nome}").status_code == 204
    assert not comparisons.bank_path(nome).exists(), "o arquivo inteiro foi embora"
    assert client.get("/comparacoes").json() == []
    assert client.delete(f"/comparacoes/{nome}").status_code == 404


def test_deleting_one_comparison_leaves_the_other(client):
    fica = create(client, runs=1)["nome"]
    sai = create(client, runs=1)["nome"]
    client.post(f"/comparacoes/{fica}/rodar")
    client.post(f"/comparacoes/{sai}/rodar")

    assert client.delete(f"/comparacoes/{sai}").status_code == 204
    assert [row["nome"] for row in client.get("/comparacoes").json()] == [fica]
    assert client.get(f"/comparacoes/{fica}").json()["concluidas"] == 2
    assert client.get(f"/comparacoes/{fica}/series").json()["arms"]


def test_deleting_a_bank_in_use_depends_on_the_system(client):
    """Apagar não abre o banco: a guarda é o sistema de arquivos.

    No Windows o `unlink` de um arquivo aberto é recusado, e isso vira 409. No
    Linux ele passa, o arquivo perde o nome e o laço segue escrevendo num inode
    órfão — lá quem protege é pausar antes.
    """
    from leilao.api import comparisons
    from leilao.store import open_store

    nome = create(client, runs=1)["nome"]
    segurando = open_store(comparisons.bank_path(nome), create=False)
    try:
        resposta = client.delete(f"/comparacoes/{nome}")
        if sys.platform.startswith("win"):
            assert resposta.status_code == 409
            assert "em uso" in resposta.json()["detail"]
            assert comparisons.bank_path(nome).exists()
        else:
            assert resposta.status_code == 204
    finally:
        segurando.close()


def test_deleting_a_stale_bank_is_allowed(client):
    """Estado `rodando` sem processo vivo é interrupção, não execução: o arquivo
    não está preso e apagar é o certo."""
    from leilao.api import comparisons
    from leilao.store import claim_simulation, owner_token, store

    nome = create(client, runs=1)["nome"]
    with store(comparisons.bank_path(nome), create=False) as connection:
        claim_simulation(connection, owner=owner_token())
    assert client.get(f"/comparacoes/{nome}").json()["rodando"] == 1

    assert client.delete(f"/comparacoes/{nome}").status_code == 204
    assert not comparisons.bank_path(nome).exists()


def test_bad_requests_answer_clearly(client):
    nome = create(client, runs=1)["nome"]
    for rota in ("", "/resultado", "/series", "/caixas"):
        assert client.get(f"/comparacoes/nao-existe{rota}").status_code == 404
    assert client.get(f"/comparacoes/{nome}/series?eixo=xyz").status_code == 400
    assert (
        client.get(
            f"/comparacoes/{nome}/series?eixo=grade_average&cortes=a,b"
        ).status_code
        == 400
    )
    assert client.get(f"/comparacoes/{nome}/curva?eixo=xyz").status_code == 400
    for ruim in ("..", ".oculto", "sub%2Fdir"):
        assert client.get(f"/comparacoes/{ruim}").status_code in (400, 404)
