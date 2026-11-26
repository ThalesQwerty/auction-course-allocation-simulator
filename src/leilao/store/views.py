"""As visualizações, prontas para desenhar.

O SQL faz toda a transformação que cabe nele: agrupa por (braço, seed, período,
faixa) e reduz os milhões de linhas de `aluno_periodo` a uma média por grupo. A
tela não recebe dado para transformar, recebe o que vai desenhar.

A única redução que não fica em SQL é o quartil **entre as seeds**, porque o
SQLite não tem `PERCENTILE` e porque ali já são poucas linhas: seeds × períodos
× faixas. A dispersão **entre alunos** da curva, essa é grande, e sai em SQL por
função de janela.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence

import numpy as np

__all__ = ["BAND_AXES", "CURVE_AXES", "METRICS", "band_series", "boxes", "quantile_curve"]

METRICS = (
    "students",
    "satisfaction",
    "attendance",
    "progress",
    "fairness",
    "mean_round",
    "graduation_rate",
)
"""As grandezas que uma série publica, nos nomes que a tela usa."""

BAND_AXES = {"grade_average": "ap.cr", "reserve": "reservas.media"}
"""Por qual coluna o recorte em faixas corta.

O CR corta no valor corrente; a utilidade de reserva corta na média dos
períodos do aluno, que não depende do período e por isso não o faz trocar de
faixa ao longo da série.
"""

CURVE_AXES = {"grade_average": "cr_final", "reserve": "reserva_media"}
"""Por qual grandeza de vida inteira a curva ordena os alunos."""

CURVE_METRICS = {
    "satisfaction": "satisfacao",
    "attendance": "aproveitamento",
    "progress": "progresso",
    "mean_round": "rodada_media",
}
"""O que a curva desenha. A equidade não entra: é do conjunto, não do aluno."""


def band_series(
    connection: sqlite3.Connection,
    *,
    axis: str = "overall",
    cuts: Sequence[float] = (),
    low: float = 0.0,
    high: float = 1.0,
    decimals: int = 0,
) -> dict:
    """A série por período, recortada em faixas e reduzida entre as seeds.

    Os grupos saem **por braço**: a mediana entre as seeds de um braço não se
    mistura com a do outro, senão a comparação some dentro do próprio quartil.
    """
    if axis != "overall" and axis not in BAND_AXES:
        raise ValueError(f"eixo de recorte desconhecido: {axis!r}")
    ordered = _ordered(cuts) if axis != "overall" else ()
    names = _band_names(ordered, low, high, decimals)

    rows = connection.execute(
        _aggregate(axis, ordered),
        {f"c{i}": cut for i, cut in enumerate(ordered)},
    ).fetchall()

    por_braco: dict[str, dict[str, dict[int, list[dict]]]] = {}
    for row in rows:
        grupo = names[row["faixa"]]
        por_braco.setdefault(row["braco"], {}).setdefault(grupo, {}).setdefault(
            row["periodo_da_coorte"], []
        ).append(_measures(row))

    return {
        "axis": axis,
        "groups": names,
        "arms": {
            braco: [
                _reduce(grupo, grupos[grupo]) for grupo in names if grupo in grupos
            ]
            for braco, grupos in por_braco.items()
        },
    }


def quantile_curve(
    connection: sqlite3.Connection,
    *,
    axis: str,
    bins: int,
) -> dict:
    """A métrica sobre uma grandeza de vida inteira, em faixas de quantil.

    As bordas saem dos quantis dos **dois braços juntos**, pelo `NTILE`, de modo
    que ambos usem as mesmas e as linhas se comparem ponto a ponto. A faixa só
    rende ponto se todo braço a sustenta, senão as linhas desalinham.
    """
    if axis not in CURVE_AXES:
        raise ValueError(f"eixo de curva desconhecido: {axis!r}")
    bins = max(1, min(int(bins), 300))

    series: dict[str, dict[str, list[dict]]] = {}
    for metric, coluna in CURVE_METRICS.items():
        rows = connection.execute(
            _CURVE.format(x=CURVE_AXES[axis], metrica=coluna),
            {"faixas": bins},
        ).fetchall()
        completos = _shared_bins(rows)
        for row in rows:
            if row["faixa"] not in completos:
                continue
            series.setdefault(row["braco"], {}).setdefault(metric, []).append(
                {
                    "x": row["x"],
                    "q1": row["q1"],
                    "median": row["mediana"],
                    "q3": row["q3"],
                    "n": row["alunos"],
                }
            )
    return {"axis": axis, "bins": bins, "arms": series}


def boxes(
    connection: sqlite3.Connection, *, baseline: str = ""
) -> dict:
    """Uma caixa por (braço, métrica) sobre as seeds: o eixo X colapsado.

    Traz junto o **pareamento** contra a linha de base: em quantas seeds o braço
    ficou acima dela. É a evidência que o pareamento por seed compra, e ela se
    calcula aqui para a tela não ter valor por seed para reduzir.
    """
    rows = connection.execute(_aggregate("overall", ())).fetchall()

    por_seed: dict[str, dict[int, list[dict]]] = {}
    for row in rows:
        por_seed.setdefault(row["braco"], {}).setdefault(row["seed"], []).append(
            _measures(row)
        )

    cruas: dict[str, dict[str, list[tuple[int, float]]]] = {}
    for braco, seeds in por_seed.items():
        for seed, pontos in seeds.items():
            pesos = [ponto["students"] for ponto in pontos]
            for metric in METRICS:
                if metric == "students":
                    continue
                valor = _weighted([ponto[metric] for ponto in pontos], pesos)
                if valor is not None:
                    cruas.setdefault(braco, {}).setdefault(metric, []).append(
                        (seed, valor)
                    )

    seeds = [
        {
            "arm": braco,
            "seed": seed,
            "periods": len(pontos),
            "graduates": round(
                (pontos[-1]["graduation_rate"] or 0.0) * (pontos[-1]["students"] or 0)
            ),
            **{
                metric: _weighted(
                    [ponto[metric] for ponto in pontos],
                    [ponto["students"] for ponto in pontos],
                )
                for metric in METRICS
                if metric != "students"
            },
        }
        for braco, por in por_seed.items()
        for seed, pontos in sorted(por.items())
    ]

    return {
        "baseline": baseline,
        "seeds": seeds,
        "arms": {
            braco: {
                metric: {
                    **_box([valor for _, valor in valores]),
                    "paired": _paired(valores, cruas.get(baseline, {}).get(metric)),
                }
                for metric, valores in metricas.items()
            }
            for braco, metricas in cruas.items()
        },
    }


def _paired(
    values: list[tuple[int, float]], against: list[tuple[int, float]] | None
) -> dict | None:
    """Em quantas seeds este braço ficou acima da linha de base, par a par."""
    if not against:
        return None
    base = dict(against)
    pares = [(valor, base[seed]) for seed, valor in values if seed in base]
    if not pares:
        return None
    return {
        "up": sum(1 for meu, dele in pares if meu > dele),
        "comparable": len(pares),
    }


# --------------------------------------------------------------------- SQL

_AGGREGATE = """
WITH {reservas}medidas AS (
  SELECT m.braco, m.seed, ap.simulacao_id, ap.periodo,
         {faixa}                            AS faixa,
         COUNT(*)                           AS alunos,
         AVG(ap.satisfacao)                 AS satisfacao,
         SUM(ap.satisfacao)                 AS soma,
         SUM(ap.satisfacao * ap.satisfacao) AS soma_quadrados,
         AVG(ap.aproveitamento)             AS aproveitamento,
         AVG(ap.progresso)                  AS progresso,
         SUM(ap.rodada_media * ap.vagas)    AS rodadas_peso,
         SUM(CASE WHEN ap.rodada_media IS NOT NULL THEN ap.vagas ELSE 0 END)
                                            AS vagas_peso
    FROM aluno_periodo ap
    JOIN simulacao m ON m.id = ap.simulacao_id
         {juncao}
   WHERE m.estado = 'concluida'
   GROUP BY m.braco, m.seed, ap.periodo, faixa
),
coorte AS (
  SELECT simulacao_id, COUNT(*) AS tamanho FROM aluno
   WHERE medido = 1 GROUP BY simulacao_id
),
formados AS (
  SELECT a.simulacao_id, p.periodo,
         SUM(CASE WHEN a.concluiu_em IS NOT NULL AND a.concluiu_em <= p.periodo
                  THEN 1 ELSE 0 END) AS concluiram_ate
    FROM aluno a JOIN periodo p ON p.simulacao_id = a.simulacao_id
   WHERE a.medido = 1
   GROUP BY a.simulacao_id, p.periodo
)
-- O eixo conta os periodos da COORTE: o de ingresso dela e o primeiro, e o
-- aquecimento nao aparece. O periodo absoluto fica, porque e por ele que as
-- juncoes casam.
SELECT medidas.*, formados.concluiram_ate, coorte.tamanho,
       medidas.periodo - (SELECT MIN(periodo) FROM periodo WHERE medido = 1) + 1
         AS periodo_da_coorte
  FROM medidas
  LEFT JOIN formados USING (simulacao_id, periodo)
  LEFT JOIN coorte   USING (simulacao_id)
 ORDER BY medidas.faixa, medidas.periodo, medidas.braco, medidas.seed
"""

_RESERVAS_CTE = """reservas AS (
  SELECT simulacao_id, aluno, AVG(reserva) AS media
    FROM aluno_periodo
   GROUP BY simulacao_id, aluno
),
"""

_RESERVAS_JOIN = """JOIN reservas
           ON reservas.simulacao_id = ap.simulacao_id
          AND reservas.aluno = ap.aluno"""

_CURVE = """
WITH alunos AS (
  SELECT m.braco, a.cr_final, AVG(ap.reserva) AS reserva_media,
         AVG(ap.satisfacao)     AS satisfacao,
         AVG(ap.aproveitamento) AS aproveitamento,
         MAX(ap.progresso)      AS progresso,
         CASE WHEN SUM(CASE WHEN ap.rodada_media IS NOT NULL THEN ap.vagas ELSE 0 END) > 0
              THEN SUM(ap.rodada_media * ap.vagas)
                 / SUM(CASE WHEN ap.rodada_media IS NOT NULL THEN ap.vagas ELSE 0 END)
         END AS rodada_media
    FROM aluno_periodo ap
    JOIN simulacao m ON m.id = ap.simulacao_id
    JOIN aluno a ON a.simulacao_id = ap.simulacao_id AND a.aluno = ap.aluno
   WHERE m.estado = 'concluida'
   GROUP BY m.braco, m.seed, ap.aluno
),
-- O NTILE corre sobre os dois braços juntos: é o que faz as bordas serem as
-- mesmas nos dois e as linhas coincidirem ponto a ponto.
classificados AS (
  SELECT braco, {x} AS x, {metrica} AS valor,
         NTILE(:faixas) OVER (ORDER BY {x}) AS faixa
    FROM alunos
   WHERE {metrica} IS NOT NULL AND {x} IS NOT NULL
),
posicoes AS (
  SELECT faixa, AVG(x) AS x FROM classificados GROUP BY faixa
),
ordenados AS (
  SELECT braco, faixa, valor,
         ROW_NUMBER() OVER (PARTITION BY braco, faixa ORDER BY valor) AS pos,
         COUNT(*)     OVER (PARTITION BY braco, faixa)                AS n
    FROM classificados
)
SELECT ordenados.braco, ordenados.faixa, posicoes.x, ordenados.n AS alunos,
       MAX(CASE WHEN pos = MAX(1, CAST(n * 0.25 AS INTEGER)) THEN valor END) AS q1,
       MAX(CASE WHEN pos = MAX(1, CAST(n * 0.50 AS INTEGER)) THEN valor END) AS mediana,
       MAX(CASE WHEN pos = MAX(1, CAST(n * 0.75 AS INTEGER)) THEN valor END) AS q3
  FROM ordenados JOIN posicoes USING (faixa)
 GROUP BY ordenados.braco, ordenados.faixa
 ORDER BY ordenados.braco, ordenados.faixa
"""


# ---------------------------------------------------------------- Python

def _aggregate(axis: str, cuts: Sequence[float]) -> str:
    """A agregação, com a média da reserva por aluno só quando ela é o eixo do
    recorte: é uma varredura a mais sobre `aluno_periodo`."""
    por_aluno = axis == "reserve" and bool(cuts)
    return _AGGREGATE.format(
        faixa=_band_sql(axis, cuts),
        reservas=_RESERVAS_CTE if por_aluno else "",
        juncao=_RESERVAS_JOIN if por_aluno else "",
    )


def _band_sql(axis: str, cuts: Sequence[float]) -> str:
    if axis == "overall" or not cuts:
        return "0"
    coluna = BAND_AXES[axis]
    ramos = " ".join(
        f"WHEN {coluna} < :c{i} THEN {i}" for i in range(len(cuts))
    )
    return f"CASE {ramos} ELSE {len(cuts)} END"


def _ordered(cuts: Sequence[float]) -> tuple[float, ...]:
    unique = sorted({float(cut) for cut in cuts})
    if len(unique) != len(cuts):
        raise ValueError("os pontos de corte devem ser distintos")
    return tuple(unique)


def _band_names(
    cuts: Sequence[float], low: float, high: float, decimals: int
) -> list[str]:
    """O rótulo da faixa — o intervalo que ela cobre, nas unidades da grandeza."""
    if not cuts:
        return ["overall"]
    bordas = [low, *cuts, high]
    return [
        f"{_number(bordas[i], decimals)}–{_number(bordas[i + 1], decimals)}"
        for i in range(len(bordas) - 1)
    ]


def _number(value: float, decimals: int) -> str:
    if decimals <= 0:
        return f"{round(value):d}"
    texto = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return (texto or "0").replace(".", ",")


def _measures(row: sqlite3.Row) -> dict[str, float | None]:
    """As grandezas de um grupo num período de uma seed."""
    return {
        "students": float(row["alunos"]),
        "satisfaction": row["satisfacao"],
        "attendance": row["aproveitamento"],
        "progress": row["progresso"],
        "fairness": _jain(row["soma"], row["soma_quadrados"], row["alunos"]),
        "mean_round": (
            row["rodadas_peso"] / row["vagas_peso"] if row["vagas_peso"] else None
        ),
        "graduation_rate": (
            (row["concluiram_ate"] or 0) / row["tamanho"] if row["tamanho"] else None
        ),
    }


def _reduce(group: str, by_period: dict[int, list[dict]]) -> dict:
    """Mediana e interquartil **entre as seeds**, ponto a ponto."""
    periods = sorted(by_period)
    return {
        "group": group,
        "x": periods,
        "n": [len(by_period[period]) for period in periods],
        "values": {
            metric: [
                _quartiles(
                    [
                        row[metric]
                        for row in by_period[period]
                        if row[metric] is not None
                    ]
                )
                for period in periods
            ]
            for metric in METRICS
        },
    }


def _box(values: list[float]) -> dict:
    """Os cinco números da caixa. A tela desenha, não calcula."""
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    return {
        "min": round(float(min(values)), 4),
        "q1": round(float(q1), 4),
        "median": round(float(median), 4),
        "q3": round(float(q3), 4),
        "max": round(float(max(values)), 4),
        "n": len(values),
    }


def _quartiles(values: list[float]) -> list[float] | None:
    """`(q1, mediana, q3)` por interpolação linear — o método 7, o do motor."""
    if not values:
        return None
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    return [round(float(q1), 4), round(float(median), 4), round(float(q3), 4)]


def _shared_bins(rows: list[sqlite3.Row]) -> set[int]:
    """As faixas que **todo** braço povoa: só essas rendem ponto."""
    bracos = {row["braco"] for row in rows}
    por_faixa: dict[int, set[str]] = {}
    for row in rows:
        por_faixa.setdefault(row["faixa"], set()).add(row["braco"])
    return {faixa for faixa, vistos in por_faixa.items() if vistos == bracos}


def _weighted(values: list[float | None], weights: list[float]) -> float | None:
    pares = [
        (value, weight)
        for value, weight in zip(values, weights)
        if value is not None and weight
    ]
    if not pares:
        return None
    total = sum(weight for _, weight in pares)
    return sum(value * weight for value, weight in pares) / total


def _jain(total: float | None, squares: float | None, count: int) -> float:
    """φ = (Σψ)² / (n · Σψ²) — anteprojeto, eq. (55)."""
    if not count or not squares:
        return 0.0
    return min(1.0, (total or 0.0) ** 2 / (count * squares))
