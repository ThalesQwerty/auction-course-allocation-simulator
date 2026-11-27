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
    "discipline_index",
    "discipline_trace",
    "observation_columns",
    "period_points",
    "simulation_heads",
    "simulation_of",
    "student_index",
    "student_points",
    "student_trace",
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
    estouros: int


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
    demanda: float | None
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
            JOIN simulacao_valida m ON m.id = ap.simulacao_id
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
               AVG(CASE WHEN ap.disciplinas_elegiveis > 0
                    THEN CAST(ap.disciplinas_pedidas AS REAL)
                       / ap.disciplinas_elegiveis END) AS demanda,
               AVG(ap.satisfacao)     AS satisfacao,
               AVG(ap.aproveitamento) AS aproveitamento,
               MAX(ap.progresso)      AS progresso,
               SUM(ap.rodada_media * ap.vagas) AS rodadas_peso,
               SUM(CASE WHEN ap.rodada_media IS NOT NULL THEN ap.vagas ELSE 0 END)
                                      AS vagas_peso
          FROM aluno_periodo ap
          JOIN simulacao_valida m ON m.id = ap.simulacao_id
          JOIN aluno a ON a.simulacao_id = ap.simulacao_id AND a.aluno = ap.aluno
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
            demanda=row["demanda"],
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
        SELECT m.braco, m.seed, ap.periodo, ap.cr,
               CASE WHEN ap.disciplinas_elegiveis > 0
                    THEN CAST(ap.disciplinas_pedidas AS REAL)
                       / ap.disciplinas_elegiveis END AS demanda, ap.satisfacao,
               ap.aproveitamento, ap.progresso, ap.rodada_media, ap.vagas
          FROM aluno_periodo ap
          JOIN simulacao_valida m ON m.id = ap.simulacao_id
         ORDER BY m.braco, m.seed, ap.periodo, ap.aluno
        """,
    )
    colunas = ("period", "grade_average", "demand", "satisfaction",
               "attendance", "progress", "mean_round", "won")
    out: dict[tuple[str, int], dict[str, list]] = {}
    for row in rows:
        tabela = out.setdefault(
            (row["braco"], row["seed"]), {chave: [] for chave in colunas}
        )
        tabela["period"].append(row["periodo"])
        tabela["grade_average"].append(row["cr"])
        tabela["demand"].append(row["demanda"])
        tabela["satisfaction"].append(row["satisfacao"])
        tabela["attendance"].append(row["aproveitamento"])
        tabela["progress"].append(row["progresso"])
        tabela["mean_round"].append(row["rodada_media"])
        tabela["won"].append(row["vagas"])
    return out


class SemSimulacao(LookupError):
    """O par (braço, seed) não está no banco, ou não terminou."""


def simulation_of(connection: sqlite3.Connection, *, arm: str, seed: int) -> int:
    """A simulação de um par (braço, seed).

    Exige `concluida` e **não** passa pela vista `simulacao_valida`: ali se
    olha uma simulação só, e uma seed que falhou do outro lado não torna esta
    ilegível — o que a vista guarda é a comparação pareada entre braços.
    """
    row = connection.execute(
        "SELECT id FROM simulacao"
        " WHERE braco = ? AND seed = ? AND estado = 'concluida'",
        (arm, seed),
    ).fetchone()
    if row is None:
        raise SemSimulacao(
            f"não há simulação concluída do modelo {arm!r} na seed {seed}"
        )
    return int(row["id"])


def student_index(
    connection: sqlite3.Connection, *, simulation_id: int
) -> dict:
    """O índice da coorte medida: uma linha por aluno, pronta para a tabela."""
    return {
        "carga_obrigatoria": _required_hours(connection),
        "alunos": _student_rows(connection, simulation_id=simulation_id),
    }


def discipline_index(
    connection: sqlite3.Connection, *, simulation_id: int
) -> dict:
    """O índice da oferta: uma linha por **disciplina**, não por turma."""
    return {
        "disciplinas": _discipline_rows(connection, simulation_id=simulation_id)
    }


def student_trace(
    connection: sqlite3.Connection, *, simulation_id: int, student: str
) -> dict:
    """O histórico de um aluno, sem os períodos em que ele não pediu nada."""
    cabecalho = _student_rows(
        connection, simulation_id=simulation_id, student=student
    )
    if not cabecalho:
        raise LookupError(f"não há aluno medido {student!r} nesta simulação")

    pedidos: dict[int, list[dict]] = {}
    for row in connection.execute(
        """
        SELECT s.*, t.disciplina, t.horario
          FROM solicitacao s JOIN turma t USING (turma)
         WHERE s.simulacao_id = :sim AND s.aluno = :aluno
         ORDER BY s.periodo, t.disciplina, s.turma
        """,
        {"sim": simulation_id, "aluno": student},
    ):
        pedidos.setdefault(row["periodo"], []).append(_request(row))

    periodos = [
        {
            **{
                chave: row[chave]
                for chave in (
                    "periodo",
                    "cr",
                    "satisfacao",
                    "aproveitamento",
                    "progresso",
                    "rodada_media",
                    "vagas",
                    "carga_obtida",
                    "carga_cursada",
                    "carga_aprovada",
                    "carga_efetiva",
                    "creditos_inicio",
                    "creditos_gasto",
                    "creditos_retorno",
                    "disciplinas_elegiveis",
                    "disciplinas_pedidas",
                )
            },
            "creditos_fim": _balance(row),
            "solicitacoes": pedidos.get(row["periodo"], []),
        }
        for row in connection.execute(
            """
            SELECT ap.* FROM aluno_periodo ap
             WHERE ap.simulacao_id = :sim AND ap.aluno = :aluno
               AND EXISTS (
                 SELECT 1 FROM solicitacao s
                  WHERE s.simulacao_id = ap.simulacao_id
                    AND s.aluno = ap.aluno AND s.periodo = ap.periodo
               )
             ORDER BY ap.periodo
            """,
            {"sim": simulation_id, "aluno": student},
        )
    ]
    return {
        "aluno": cabecalho[0],
        "carga_obrigatoria": _required_hours(connection),
        "periodos": periodos,
    }


def discipline_trace(
    connection: sqlite3.Connection, *, simulation_id: int, discipline: str
) -> dict:
    """O histórico de uma disciplina: o período, as turmas dela e quem pediu."""
    cabecalho = _discipline_rows(
        connection, simulation_id=simulation_id, discipline=discipline
    )
    if not cabecalho:
        raise LookupError(f"não há disciplina {discipline!r} nesta oferta")

    turmas: dict[int, list[dict]] = {}
    for row in connection.execute(
        """
        SELECT tp.periodo, tp.turma, t.horario, tp.vagas, tp.preenchidas,
               tp.concedidas, tp.pedidos, tp.aprovacoes, tp.exclusoes,
               tp.preco_medio
          FROM turma_periodo tp JOIN turma t USING (turma)
         WHERE tp.simulacao_id = :sim AND t.disciplina = :disciplina
           AND EXISTS (
             SELECT 1 FROM solicitacao s JOIN turma u USING (turma)
              WHERE s.simulacao_id = tp.simulacao_id
                AND s.periodo = tp.periodo AND u.disciplina = t.disciplina
           )
         ORDER BY tp.periodo, tp.turma
        """,
        {"sim": simulation_id, "disciplina": discipline},
    ):
        turmas.setdefault(row["periodo"], []).append(dict(row))

    pedidos: dict[int, list[dict]] = {}
    for row in connection.execute(
        """
        SELECT s.*, t.disciplina, a.nome, a.ingresso, ap.cr
          FROM solicitacao s
          JOIN turma t USING (turma)
          JOIN aluno a ON a.simulacao_id = s.simulacao_id AND a.aluno = s.aluno
          LEFT JOIN aluno_periodo ap
            ON ap.simulacao_id = s.simulacao_id
           AND ap.aluno = s.aluno AND ap.periodo = s.periodo
         WHERE s.simulacao_id = :sim AND t.disciplina = :disciplina
         ORDER BY s.periodo, s.turma, s.aluno
        """,
        {"sim": simulation_id, "disciplina": discipline},
    ):
        pedidos.setdefault(row["periodo"], []).append(
            {
                **_request(row),
                "aluno": row["aluno"],
                "nome": row["nome"] or row["aluno"],
                "ingresso": row["ingresso"],
                "cr": row["cr"],
            }
        )

    return {
        "disciplina": cabecalho[0],
        "turmas": [
            dict(row)
            for row in connection.execute(
                "SELECT turma, horario, vagas FROM turma"
                " WHERE disciplina = ? ORDER BY turma",
                (discipline,),
            )
        ],
        "periodos": [
            {
                "periodo": periodo,
                "resumo": _summary(turmas[periodo]),
                "turmas": turmas[periodo],
                "solicitacoes": pedidos.get(periodo, []),
            }
            for periodo in sorted(turmas)
        ],
    }


def _request(row: sqlite3.Row) -> dict:
    """Uma solicitação como a tabela a desenha: o vetor de lances já aberto."""
    return {
        "turma": row["turma"],
        "disciplina": row["disciplina"],
        "utilidade": row["utilidade"],
        "lances": json.loads(row["lances"]) if row["lances"] else [],
        "rodada_ganha": row["rodada_ganha"],
        "pago": row["pago"],
        "excluida": bool(row["excluida"]),
        "tentativa": row["tentativa"],
        "nota": row["nota"],
        "aprovada": bool(row["aprovada"]),
        "retorno": row["retorno"],
    }


def _summary(turmas: list[dict]) -> dict:
    """A disciplina num período: a soma das turmas dela."""
    return {
        chave: sum(turma[chave] for turma in turmas)
        for chave in (
            "vagas",
            "preenchidas",
            "concedidas",
            "pedidos",
            "aprovacoes",
            "exclusoes",
        )
    }


def _balance(row: sqlite3.Row) -> int | None:
    """O saldo no fim do período. `None` no braço por CR, onde não há crédito."""
    if row["creditos_inicio"] is None:
        return None
    return (
        row["creditos_inicio"] - (row["creditos_gasto"] or 0)
        + (row["creditos_retorno"] or 0)
    )


def _required_hours(connection: sqlite3.Connection) -> int:
    """A carga que conclui o curso pelas obrigatórias, da própria oferta."""
    row = connection.execute(
        "SELECT SUM(carga) AS carga FROM ("
        " SELECT disciplina, MAX(carga) AS carga FROM turma"
        "  WHERE optativa = 0 GROUP BY disciplina)"
    ).fetchone()
    return int(row["carga"] or 0)


def _student_rows(
    connection: sqlite3.Connection,
    *,
    simulation_id: int,
    student: str | None = None,
) -> list[dict]:
    """A linha de índice de cada aluno medido, ou de um só."""
    rows = connection.execute(
        _STUDENT_INDEX.format(filtro=" AND a.aluno = :aluno" if student else ""),
        {"sim": simulation_id, "aluno": student},
    ).fetchall()
    return [
        {
            "aluno": row["aluno"],
            "nome": row["nome"] or row["aluno"],
            "ingresso": row["ingresso"],
            "periodos": row["periodos"] or 0,
            "cr": row["cr_final"],
            "intensidade": row["intensidade"],
            "carga_aprovada": row["carga_aprovada"],
            "matriculas": row["matriculas"] or 0,
            "aprovacoes": row["aprovacoes"] or 0,
            "satisfacao": row["satisfacao"],
            "rodada_media": (
                row["rodadas_peso"] / row["vagas_peso"] if row["vagas_peso"] else None
            ),
            "disponibilidade": row["disponibilidade"],
            "creditos_fim": row["creditos_fim"],
            "creditos_gasto": row["creditos_gasto"],
            "saida": "formado" if row["concluiu_em"] is not None else "jubilado",
            "saida_periodo": (
                row["concluiu_em"]
                if row["concluiu_em"] is not None
                else row["jubilou_em"]
            ),
        }
        for row in rows
    ]


def _discipline_rows(
    connection: sqlite3.Connection,
    *,
    simulation_id: int,
    discipline: str | None = None,
) -> list[dict]:
    """A linha de índice de cada disciplina da oferta, ou de uma só.

    As duas fontes não se cruzam numa razão: `turma_periodo` conta todo mundo,
    medido ou de fundo, e `solicitacao` só a coorte medida.
    """
    rows = connection.execute(
        _DISCIPLINE_INDEX.format(
            filtro=" WHERE oferta.disciplina = :disciplina" if discipline else ""
        ),
        {"sim": simulation_id, "disciplina": discipline},
    ).fetchall()
    return [
        {
            "disciplina": row["disciplina"],
            "nivel": row["nivel"],
            "optativa": bool(row["optativa"]),
            "carga": row["carga"],
            "turmas": row["turmas"],
            "vagas": row["vagas"],
            "pedidos": (
                row["pedidos"] / row["periodos"]
                if row["periodos"] and row["pedidos"] is not None
                else None
            ),
            "demanda_por_vaga": (
                row["pedidos"] / row["periodos"] / row["vagas"]
                if row["periodos"] and row["vagas"] and row["pedidos"] is not None
                else None
            ),
            "preenchimento": (
                row["preenchidas"] / row["vagas_ofertadas"]
                if row["vagas_ofertadas"]
                else None
            ),
            "preco_medio": row["preco_medio"],
            "nota_media": row["nota_media"],
            "aprovacoes": row["aprovacoes"] or 0,
            "exclusoes": row["exclusoes"] or 0,
        }
        for row in rows
    ]


_STUDENT_INDEX = """
WITH periodos AS (
  SELECT ap.aluno,
         COUNT(*)              AS periodos,
         SUM(ap.vagas)         AS matriculas,
         AVG(ap.satisfacao)    AS satisfacao,
         AVG(ap.carga_efetiva) AS disponibilidade,
         AVG(CASE WHEN ap.disciplinas_elegiveis > 0
                  THEN CAST(ap.disciplinas_pedidas AS REAL)
                     / ap.disciplinas_elegiveis END) AS intensidade,
         SUM(ap.creditos_gasto) AS creditos_gasto,
         SUM(ap.rodada_media * ap.vagas) AS rodadas_peso,
         SUM(CASE WHEN ap.rodada_media IS NOT NULL THEN ap.vagas ELSE 0 END)
                               AS vagas_peso,
         MAX(ap.periodo)       AS ultimo
    FROM aluno_periodo ap
   WHERE ap.simulacao_id = :sim
   GROUP BY ap.aluno
),
aprovacoes AS (
  SELECT aluno, COUNT(*) AS aprovacoes FROM solicitacao
   WHERE simulacao_id = :sim AND aprovada = 1
   GROUP BY aluno
),
-- O saldo de saída é o do último período vivido, e não a soma de nada: o
-- crédito atravessa o período, então somar os saldos contaria o mesmo duas
-- vezes.
saldo AS (
  SELECT ap.aluno,
         ap.creditos_inicio - ap.creditos_gasto + ap.creditos_retorno
           AS creditos_fim
    FROM aluno_periodo ap
    JOIN periodos ON periodos.aluno = ap.aluno AND periodos.ultimo = ap.periodo
   WHERE ap.simulacao_id = :sim
)
SELECT a.aluno, a.nome, a.ingresso, a.cr_final, a.carga_aprovada,
       a.concluiu_em, a.jubilou_em,
       periodos.periodos, periodos.matriculas, periodos.satisfacao,
       periodos.disponibilidade, periodos.intensidade, periodos.creditos_gasto,
       periodos.rodadas_peso, periodos.vagas_peso,
       aprovacoes.aprovacoes, saldo.creditos_fim
  FROM aluno a
  LEFT JOIN periodos   ON periodos.aluno = a.aluno
  LEFT JOIN aprovacoes ON aprovacoes.aluno = a.aluno
  LEFT JOIN saldo      ON saldo.aluno = a.aluno
 WHERE a.simulacao_id = :sim AND a.medido = 1{filtro}
 ORDER BY a.aluno
"""

_DISCIPLINE_INDEX = """
WITH oferta AS (
  SELECT disciplina,
         MAX(periodo_da_grade) AS nivel,
         MAX(optativa)         AS optativa,
         MAX(carga)            AS carga,
         COUNT(*)              AS turmas,
         SUM(vagas)            AS vagas
    FROM turma GROUP BY disciplina
),
mercado AS (
  SELECT t.disciplina,
         COUNT(DISTINCT tp.periodo) AS periodos,
         SUM(tp.pedidos)            AS pedidos,
         SUM(tp.preenchidas)        AS preenchidas,
         SUM(tp.vagas)              AS vagas_ofertadas,
         SUM(tp.aprovacoes)         AS aprovacoes,
         SUM(tp.exclusoes)          AS exclusoes,
         AVG(tp.preco_medio)        AS preco_medio
    FROM turma_periodo tp JOIN turma t USING (turma)
   WHERE tp.simulacao_id = :sim
   GROUP BY t.disciplina
),
notas AS (
  SELECT t.disciplina, AVG(s.nota) AS nota_media
    FROM solicitacao s JOIN turma t USING (turma)
   WHERE s.simulacao_id = :sim AND s.nota IS NOT NULL
   GROUP BY t.disciplina
)
SELECT oferta.disciplina, oferta.nivel, oferta.optativa, oferta.carga,
       oferta.turmas, oferta.vagas,
       mercado.periodos, mercado.pedidos, mercado.preenchidas,
       mercado.vagas_ofertadas, mercado.aprovacoes, mercado.exclusoes,
       mercado.preco_medio, notas.nota_media
  FROM oferta
  LEFT JOIN mercado USING (disciplina)
  LEFT JOIN notas   USING (disciplina)
{filtro}
 ORDER BY oferta.optativa, COALESCE(oferta.nivel, 1 << 20), oferta.disciplina
"""


_HEAD_SELECT = """
SELECT c.*,
       SUM(m.estado = 'pendente')  AS pendentes,
       SUM(m.estado = 'rodando')   AS rodando,
       SUM(m.estado = 'concluida') AS concluidas,
       SUM(m.estado = 'falhou')    AS falhas,
       SUM(m.estado = 'estourou')  AS estouros,
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
        estouros=row["estouros"] or 0,
    )


def _jain(total: float | None, squares: float | None, count: int) -> float:
    """φ = (Σψ)² / (n · Σψ²) — anteprojeto, eq. (55)."""
    if not count or not squares:
        return 0.0
    return min(1.0, (total or 0.0) ** 2 / (count * squares))
