"""O que a tela lê do banco.

A divisão de trabalho é esta: o SQL faz a redução pesada, que é a média sobre
milhões de linhas de `aluno_periodo`, e o Python faz a leve, que é dobrar as
seeds em mediana e interquartil. A segunda fica fora do SQL porque o SQLite não
tem `PERCENTILE`, e porque ali já são poucas linhas.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

__all__ = [
    "ComparisonHead",
    "PeriodPoint",
    "SemSimulacao",
    "SimulationHead",
    "StudentPoint",
    "comparison_head",
    "observation_columns",
    "period_points",
    "simulation_heads",
    "student_points",
    "student_script",
    "trace_script",
]


@dataclass(frozen=True)
class ComparisonHead:
    """A comparação sem o resultado: o que a lista mostra.

    Sem identidade: há uma comparação por banco, e quem a identifica é o arquivo.
    """

    rotulo: str | None
    criada_em: str
    iniciada_em: str | None
    terminada_em: str | None
    duracao_ms: int | None
    estado: str
    cenario: str
    seeds: int
    bracos: list[str]
    coorte_medida: int | None
    rodadas_teto: int
    etapas: int
    etapas_total: int | None
    erro: str | None
    pendentes: int
    rodando: int
    concluidas: int
    falhas: int


@dataclass(frozen=True)
class SimulationHead:
    """Uma simulação e o andamento dela."""

    id: int
    braco: str
    seed: int
    estado: str
    tentativas: int
    iniciada_em: str | None
    terminada_em: str | None
    duracao_ms: int | None
    periodos: int | None
    etapas: int
    erro: str | None
    periodos_gravados: int


@dataclass(frozen=True)
class PeriodPoint:
    """Um período de uma simulação, já agregado sobre a coorte medida."""

    braco: str
    seed: int
    periodo: int
    alunos: int
    satisfacao: float
    aproveitamento: float | None
    progresso: float
    equidade: float
    rodada_media: float | None
    cr: float
    exclusao: float | None
    concluintes: float
    coorte: int
    rodadas: int
    no_teto: bool


@dataclass(frozen=True)
class StudentPoint:
    """Um aluno medido, com as grandezas de vida inteira dele."""

    braco: str
    seed: int
    aluno: str
    cr_final: float
    reserva: float
    satisfacao: float
    aproveitamento: float | None
    progresso: float
    rodada_media: float | None
    concluiu: bool


def comparison_head(connection: sqlite3.Connection) -> ComparisonHead | None:
    row = connection.execute(_HEAD_SELECT).fetchone()
    return _head(row) if row else None


def simulation_heads(
    connection: sqlite3.Connection
) -> list[SimulationHead]:
    rows = connection.execute(
        "SELECT m.*,"
        "  (SELECT COUNT(*) FROM periodo p WHERE p.simulacao_id = m.id) AS gravados"
        " FROM simulacao m ORDER BY m.braco, m.seed"
    )
    return [
        SimulationHead(
            id=row["id"],
            braco=row["braco"],
            seed=row["seed"],
            estado=row["estado"],
            tentativas=row["tentativas"],
            iniciada_em=row["iniciada_em"],
            terminada_em=row["terminada_em"],
            duracao_ms=row["duracao_ms"],
            periodos=row["periodos"],
            etapas=row["etapas"],
            erro=row["erro"],
            periodos_gravados=row["gravados"],
        )
        for row in rows
    ]


def period_points(
    connection: sqlite3.Connection
) -> list[PeriodPoint]:
    """Uma linha por (braço, seed, período medido).

    A equidade sai da identidade de Jain montada no SQL, `(Σψ)² / (n · Σψ²)`,
    porque a de um recorte **não** é a média das dos pedaços. E `rodada_media`
    sai ponderada por vaga concedida, que é o que a torna r̄ de verdade.
    """
    rows = connection.execute(
        """
        WITH medidas AS (
          SELECT m.braco, m.seed, ap.simulacao_id, ap.periodo,
                 COUNT(*)                     AS alunos,
                 AVG(ap.satisfacao)           AS satisfacao,
                 SUM(ap.satisfacao)           AS soma,
                 SUM(ap.satisfacao * ap.satisfacao) AS soma_quadrados,
                 AVG(ap.aproveitamento)       AS aproveitamento,
                 AVG(ap.progresso)            AS progresso,
                 AVG(ap.cr)                   AS cr,
                 SUM(ap.rodada_media * ap.vagas) AS rodadas_peso,
                 SUM(CASE WHEN ap.rodada_media IS NOT NULL THEN ap.vagas ELSE 0 END)
                                              AS vagas_peso,
                 SUM(ap.vagas)                AS vagas
            FROM aluno_periodo ap
            JOIN simulacao m ON m.id = ap.simulacao_id
           WHERE m.estado = 'concluida'
           GROUP BY m.braco, m.seed, ap.periodo
        ),
        descartes AS (
          SELECT s.simulacao_id, s.periodo, SUM(s.excluida) AS excluidas
            FROM solicitacao s GROUP BY s.simulacao_id, s.periodo
        ),
        rodadas_do_periodo AS (
          SELECT p.simulacao_id, p.periodo, p.rodadas FROM periodo p
        ),
        -- `periodo.concluiram` conta toda coorte; aqui só a medida, que é a
        -- que o denominador mede.
        formados AS (
          SELECT a.simulacao_id, p.periodo,
                 SUM(CASE WHEN a.concluiu_em IS NOT NULL
                           AND a.concluiu_em <= p.periodo THEN 1 ELSE 0 END)
                   AS concluiram_ate
            FROM aluno a
            JOIN periodo p ON p.simulacao_id = a.simulacao_id
           WHERE a.medido = 1
           GROUP BY a.simulacao_id, p.periodo
        ),
        coorte AS (
          SELECT a.simulacao_id, COUNT(*) AS tamanho
            FROM aluno a WHERE a.medido = 1 GROUP BY a.simulacao_id
        )
        SELECT medidas.*, descartes.excluidas, rodadas_do_periodo.rodadas,
               formados.concluiram_ate, coorte.tamanho,
               (SELECT rodadas_teto FROM comparacao) AS teto
          FROM medidas
          LEFT JOIN descartes          USING (simulacao_id, periodo)
          LEFT JOIN rodadas_do_periodo USING (simulacao_id, periodo)
          LEFT JOIN formados           USING (simulacao_id, periodo)
          LEFT JOIN coorte             USING (simulacao_id)
         ORDER BY medidas.braco, medidas.seed, medidas.periodo
        """,
    )
    return [
        PeriodPoint(
            braco=row["braco"],
            seed=row["seed"],
            periodo=row["periodo"],
            alunos=row["alunos"],
            satisfacao=row["satisfacao"],
            aproveitamento=row["aproveitamento"],
            progresso=row["progresso"],
            equidade=_jain(row["soma"], row["soma_quadrados"], row["alunos"]),
            rodada_media=(
                row["rodadas_peso"] / row["vagas_peso"] if row["vagas_peso"] else None
            ),
            cr=row["cr"],
            exclusao=(
                row["excluidas"] / row["vagas"]
                if row["vagas"] and row["excluidas"] is not None
                else None
            ),
            concluintes=(
                (row["concluiram_ate"] or 0) / row["tamanho"] if row["tamanho"] else 0.0
            ),
            coorte=row["tamanho"] or 0,
            rodadas=row["rodadas"] or 0,
            no_teto=bool(row["rodadas"] and row["rodadas"] >= row["teto"]),
        )
        for row in rows
    ]


def student_points(
    connection: sqlite3.Connection
) -> list[StudentPoint]:
    """Um ponto por (aluno medido, simulação), com as médias de vida inteira dele."""
    rows = connection.execute(
        """
        SELECT m.braco, m.seed, ap.aluno,
               a.cr_final, a.concluiu_em,
               AVG(ap.reserva)        AS reserva,
               AVG(ap.satisfacao)     AS satisfacao,
               AVG(ap.aproveitamento) AS aproveitamento,
               MAX(ap.progresso)      AS progresso,
               SUM(ap.rodada_media * ap.vagas) AS rodadas_peso,
               SUM(CASE WHEN ap.rodada_media IS NOT NULL THEN ap.vagas ELSE 0 END)
                                      AS vagas_peso
          FROM aluno_periodo ap
          JOIN simulacao m ON m.id = ap.simulacao_id
          JOIN aluno a ON a.simulacao_id = ap.simulacao_id AND a.aluno = ap.aluno
         WHERE m.estado = 'concluida'
         GROUP BY m.braco, m.seed, ap.aluno
         ORDER BY m.braco, m.seed, ap.aluno
        """,
    )
    return [
        StudentPoint(
            braco=row["braco"],
            seed=row["seed"],
            aluno=row["aluno"],
            cr_final=row["cr_final"],
            reserva=row["reserva"],
            satisfacao=row["satisfacao"],
            aproveitamento=row["aproveitamento"],
            progresso=row["progresso"],
            rodada_media=(
                row["rodadas_peso"] / row["vagas_peso"] if row["vagas_peso"] else None
            ),
            concluiu=row["concluiu_em"] is not None,
        )
        for row in rows
    ]


def observation_columns(
    connection: sqlite3.Connection
) -> dict[tuple[str, int], dict[str, list]]:
    """As linhas cruas em colunas paralelas, por (braço, seed).

    É o que a interface recorta em faixas sem simular de novo. Cresce com a
    coorte: em 1000 seeds são 4,7 milhões de linhas, e aí o recorte precisa
    virar consulta em vez de viajar inteiro.
    """
    rows = connection.execute(
        """
        SELECT m.braco, m.seed, ap.periodo, ap.cr, ap.reserva, ap.satisfacao,
               ap.aproveitamento, ap.progresso, ap.rodada_media, ap.vagas
          FROM aluno_periodo ap
          JOIN simulacao m ON m.id = ap.simulacao_id
         WHERE m.estado = 'concluida'
         ORDER BY m.braco, m.seed, ap.periodo, ap.aluno
        """,
    )
    colunas = ("period", "grade_average", "reserve", "satisfaction",
               "attendance", "progress", "mean_round", "won")
    out: dict[tuple[str, int], dict[str, list]] = {}
    for row in rows:
        tabela = out.setdefault(
            (row["braco"], row["seed"]), {chave: [] for chave in colunas}
        )
        tabela["period"].append(row["periodo"])
        tabela["grade_average"].append(row["cr"])
        tabela["reserve"].append(row["reserva"])
        tabela["satisfaction"].append(row["satisfacao"])
        tabela["attendance"].append(row["aproveitamento"])
        tabela["progress"].append(row["progresso"])
        tabela["mean_round"].append(row["rodada_media"])
        tabela["won"].append(row["vagas"])
    return out


def student_script(
    connection: sqlite3.Connection, *, simulation_id: int, student: str
) -> dict:
    """Tudo que um aluno fez: o período a período e a turma a turma."""
    periods = connection.execute(
        "SELECT * FROM aluno_periodo WHERE simulacao_id = ? AND aluno = ?"
        " ORDER BY periodo",
        (simulation_id, student),
    ).fetchall()
    requests = connection.execute(
        "SELECT * FROM solicitacao WHERE simulacao_id = ? AND aluno = ?"
        " ORDER BY periodo, turma",
        (simulation_id, student),
    ).fetchall()
    head = connection.execute(
        "SELECT * FROM aluno WHERE simulacao_id = ? AND aluno = ?",
        (simulation_id, student),
    ).fetchone()
    return {
        "aluno": dict(head) if head else None,
        "periodos": [dict(row) for row in periods],
        "solicitacoes": [dict(row) for row in requests],
    }


class SemSimulacao(LookupError):
    """O par (braço, seed) não está no banco, ou não terminou."""


def trace_script(
    connection: sqlite3.Connection, *, arm: str, seed: int
) -> dict:
    """Uma simulação inteira como o traço a lê, sem refazer nada.

    O que o banco não tem é o que o `_acted` de `rows.py` descartou: a turma que
    o aluno podia cursar e não pediu não virou linha, então a vista por aluno
    lista o que ele moveu, não tudo que lhe era elegível. E só a coorte medida
    tem roteiro, de modo que a demanda de fundo aparece nos totais da turma e
    não na tabela de quem pediu.
    """
    simulacao = connection.execute(
        "SELECT id FROM simulacao WHERE braco = ? AND seed = ? AND estado = 'concluida'",
        (arm, seed),
    ).fetchone()
    if simulacao is None:
        raise SemSimulacao(
            f"não há simulação concluída do modelo {arm!r} na seed {seed}"
        )
    identificador = simulacao["id"]
    rodadas = connection.execute(
        "SELECT rodadas_teto FROM comparacao"
    ).fetchone()["rodadas_teto"]

    turmas = connection.execute(
        "SELECT * FROM turma"
        " ORDER BY optativa, COALESCE(periodo_da_grade, 1 << 20), turma"
    ).fetchall()
    return {
        "arm": arm,
        "seed": seed,
        "disciplines": [turma["turma"] for turma in turmas],
        "classes": {turma["turma"]: turma["disciplina"] for turma in turmas},
        "curriculum_periods": {
            turma["disciplina"]: turma["periodo_da_grade"] or 0 for turma in turmas
        },
        "periods": _trace_periods(connection, identificador),
        "students": _trace_students(connection, identificador, turmas),
        "histories": _trace_histories(connection, identificador, rodadas),
    }


def _trace_periods(
    connection: sqlite3.Connection, simulation_id: int
) -> list[dict]:
    """A oferta período a período: a turma e o que aconteceu com ela."""
    por_periodo: dict[int, list[dict]] = {}
    for row in connection.execute(
        """
        SELECT tp.*, t.disciplina, t.carga, t.periodo_da_grade
          FROM turma_periodo tp JOIN turma t USING (turma)
         WHERE tp.simulacao_id = ?
         ORDER BY tp.periodo, COALESCE(t.periodo_da_grade, 1 << 20), tp.turma
        """,
        (simulation_id,),
    ):
        por_periodo.setdefault(row["periodo"], []).append(
            {
                "name": row["turma"],
                "discipline": row["disciplina"],
                "curriculum_period": row["periodo_da_grade"] or 0,
                "hours": row["carga"],
                "seats": row["vagas"],
                "filled": row["preenchidas"],
                "granted": row["concedidas"],
                "requests": row["pedidos"],
                "mean_price": row["preco_medio"],
                "approvals": row["aprovacoes"],
                "exclusions": row["exclusoes"],
            }
        )
    return [
        {"period": periodo, "disciplines": turmas}
        for periodo, turmas in sorted(por_periodo.items())
    ]


def _trace_students(
    connection: sqlite3.Connection, simulation_id: int, turmas: list[sqlite3.Row]
) -> list[dict]:
    """A coorte medida, que é quem tem roteiro. O crédito de saída sai do último
    período, e a carga de conclusão da própria oferta obrigatória."""
    carga_obrigatoria = sum(
        {
            turma["disciplina"]: turma["carga"]
            for turma in turmas
            if not turma["optativa"]
        }.values()
    )
    rows = connection.execute(
        """
        SELECT a.*,
               AVG(ap.satisfacao)  AS satisfacao_media,
               SUM(ap.vagas)       AS matriculas,
               MAX(ap.periodo)     AS ultimo
          FROM aluno a LEFT JOIN aluno_periodo ap
            ON ap.simulacao_id = a.simulacao_id AND ap.aluno = a.aluno
         WHERE a.simulacao_id = ? AND a.medido = 1
         GROUP BY a.aluno
         ORDER BY a.aluno
        """,
        (simulation_id,),
    ).fetchall()
    aprovacoes = dict(
        connection.execute(
            "SELECT aluno, COUNT(*) FROM solicitacao"
            " WHERE simulacao_id = ? AND aprovada = 1 GROUP BY aluno",
            (simulation_id,),
        ).fetchall()
    )
    creditos = {
        row["aluno"]: (row["creditos_inicio"] or 0)
        - (row["creditos_gasto"] or 0)
        + (row["creditos_retorno"] or 0)
        for row in connection.execute(
            "SELECT ap.* FROM aluno_periodo ap"
            " WHERE ap.simulacao_id = ? ORDER BY ap.aluno, ap.periodo",
            (simulation_id,),
        )
    }
    return [
        {
            "id": row["aluno"],
            "name": row["nome"] or row["aluno"],
            "entry_period": row["ingresso"],
            "availability_anchor": row["ancora_disponibilidade"] or 0.0,
            "selectivity_anchor": row["ancora_seletividade"] or 0.0,
            "grade_average": row["cr_final"] or 0.0,
            "approved_hours": row["carga_aprovada"],
            "hours_to_graduate": carga_obrigatoria,
            "credits": creditos.get(row["aluno"], 0),
            "enrollments": row["matriculas"] or 0,
            "approvals": aprovacoes.get(row["aluno"], 0),
            "mean_satisfaction": row["satisfacao_media"] or 0.0,
            "graduated_at": row["concluiu_em"],
            "dismissed_at": row["jubilou_em"],
        }
        for row in rows
    ]


def _trace_histories(
    connection: sqlite3.Connection, simulation_id: int, rounds: int
) -> list[dict]:
    """O período a período de cada aluno medido, com as turmas que ele moveu."""
    pedidos: dict[tuple[str, int], list[dict]] = {}
    for row in connection.execute(
        "SELECT * FROM solicitacao WHERE simulacao_id = ?"
        " ORDER BY aluno, periodo, turma",
        (simulation_id,),
    ):
        pedidos.setdefault((row["aluno"], row["periodo"]), []).append(
            {
                "discipline": row["turma"],
                "utility": row["utilidade"],
                "bids": (
                    json.loads(row["lances"])
                    if row["lances"]
                    else [0] * max(1, rounds)
                ),
                "won_round": row["rodada_ganha"],
                "paid": row["pago"],
                "excluded": bool(row["excluida"]),
                "attempt": row["tentativa"],
                "grade": row["nota"],
                "approved": bool(row["aprovada"]),
                "returned": row["retorno"],
            }
        )

    concluiu = dict(
        connection.execute(
            "SELECT aluno, concluiu_em FROM aluno WHERE simulacao_id = ?",
            (simulation_id,),
        ).fetchall()
    )
    por_aluno: dict[str, list[dict]] = {}
    for row in connection.execute(
        "SELECT * FROM aluno_periodo WHERE simulacao_id = ? ORDER BY aluno, periodo",
        (simulation_id,),
    ):
        inicio = row["creditos_inicio"] or 0
        por_aluno.setdefault(row["aluno"], []).append(
            {
                "period": row["periodo"],
                "credits_start": inicio,
                "credits_spent": row["creditos_gasto"] or 0,
                "credits_returned": row["creditos_retorno"] or 0,
                "credits_end": inicio
                - (row["creditos_gasto"] or 0)
                + (row["creditos_retorno"] or 0),
                "satisfaction": row["satisfacao"],
                "grade_average": row["cr"],
                "approved_hours": row["carga_aprovada"],
                "enrolled_hours": row["carga_obtida"],
                "retained_hours": row["carga_cursada"],
                "effective_load": row["carga_efetiva"],
                "requests": pedidos.get((row["aluno"], row["periodo"]), []),
                "graduated": concluiu.get(row["aluno"]) == row["periodo"],
            }
        )
    return [
        {"student_id": aluno, "periods": periodos}
        for aluno, periodos in sorted(por_aluno.items())
    ]


_HEAD_SELECT = """
SELECT c.*,
       SUM(m.estado = 'pendente')  AS pendentes,
       SUM(m.estado = 'rodando')   AS rodando,
       SUM(m.estado = 'concluida') AS concluidas,
       SUM(m.estado = 'falhou')    AS falhas,
       SUM(m.etapas)               AS etapas
  FROM comparacao c LEFT JOIN simulacao m
"""


def _head(row: sqlite3.Row) -> ComparisonHead:
    return ComparisonHead(
        rotulo=row["rotulo"],
        criada_em=row["criada_em"],
        iniciada_em=row["iniciada_em"],
        terminada_em=row["terminada_em"],
        duracao_ms=row["duracao_ms"],
        estado=row["estado"],
        cenario=row["cenario"],
        seeds=row["seeds"],
        bracos=row["bracos"].split(",") if row["bracos"] else [],
        coorte_medida=row["coorte_medida"],
        rodadas_teto=row["rodadas_teto"],
        etapas=row["etapas"] or 0,
        etapas_total=row["etapas_total"],
        erro=row["erro"],
        pendentes=row["pendentes"] or 0,
        rodando=row["rodando"] or 0,
        concluidas=row["concluidas"] or 0,
        falhas=row["falhas"] or 0,
    )


def _jain(total: float | None, squares: float | None, count: int) -> float:
    """φ = (Σψ)² / (n · Σψ²) — anteprojeto, eq. (55)."""
    if not count or not squares:
        return 0.0
    return min(1.0, (total or 0.0) ** 2 / (count * squares))
