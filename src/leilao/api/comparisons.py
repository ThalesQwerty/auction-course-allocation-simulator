"""As rotas das comparações.

**Um banco por comparação**, em `resultados/comparacao-<carimbo>.db`
(git-ignored, pasta em `LEILAO_RESULTS_DIR`), endereçado pelo nome do arquivo.
Apagar é `unlink` e arquivar é guardar um arquivo, e por isso a tabela
`comparacao` tem uma linha só e não carrega identidade: quem identifica é o
arquivo.

Criar e rodar são separados. É o que torna pausa e retomada endereçáveis, e é o
que deixa uma execução de horas caber fora de uma requisição.

A tela não transforma dado: cada visualização é uma consulta que já devolve o
que vai ser desenhado.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ..config import SimulationConfig
from ..store import create_comparison, pause_comparison, run_into_store, store
from ..store import queries, views
from .schemas import CompareRequest
from .service import build_config
from .storage import UNSAFE, results_dir

__all__ = [
    "Missing",
    "Running",
    "bank_path",
    "create",
    "delete",
    "listing",
    "pause",
    "read_boxes",
    "read_curve",
    "read_result",
    "read_series",
    "read_state",
    "read_student",
    "run",
]

PREFIX = "comparacao-"


class Running(Exception):
    """Pedido que não se atende com a comparação em curso."""


class Missing(Exception):
    """Não há comparação com esse nome."""


def bank_path(name: str) -> Path:
    """O caminho de um banco, recusando nome que escape da pasta."""
    if not name or name != UNSAFE.sub("-", name) or name.startswith("."):
        raise ValueError(f"nome de comparação inválido: {name!r}")
    return results_dir() / f"{name}.db"


def create(request: CompareRequest, *, label: str | None = None) -> dict:
    """Cria o banco e a fila. Não roda nada."""
    config = build_config(request)
    name = _free_name()
    with store(bank_path(name)) as connection:
        create_comparison(
            connection,
            config=config,
            scenario=request.model_dump_json(),
            seeds=request.runs,
            arms=list(request.arms),
            label=label,
        )
    return read_state(name)


def run(name: str, *, workers: int = 1) -> dict:
    """Roda o que falta. Serve de começo e de retomada depois de pausa ou queda."""
    with _open(name) as connection:
        return asdict(
            run_into_store(
                connection,
                config=_config_of(connection),
                bank=bank_path(name),
                workers=workers,
            )
        )


def pause(name: str) -> dict:
    with _open(name) as connection:
        _head(connection)
        pause_comparison(connection)
    return read_state(name)


def listing() -> list[dict]:
    """Toda comparação da pasta, da mais recente para a mais antiga."""
    folder = results_dir()
    if not folder.is_dir():
        return []
    found = []
    for path in sorted(folder.glob(f"{PREFIX}*.db")):
        try:
            with store(path, create=False) as connection:
                head = queries.comparison_head(connection)
        except (ValueError, sqlite3.DatabaseError):
            continue
        if head is not None:
            found.append({"nome": path.stem, "bytes": path.stat().st_size, **asdict(head)})
    return sorted(found, key=lambda row: row["criada_em"], reverse=True)


def read_state(name: str) -> dict:
    """O cabeçalho e o estado de cada simulação: o que a tela consulta para acompanhar."""
    path = bank_path(name)
    with _open(name) as connection:
        head = _head(connection)
        return {
            "nome": name,
            "bytes": path.stat().st_size,
            **asdict(head),
            "simulacoes": [
                asdict(row) for row in queries.simulation_heads(connection)
            ],
        }


def read_result(name: str) -> dict:
    """O cenário e o cabeçalho. As visualizações têm rota própria."""
    path = bank_path(name)
    with _open(name) as connection:
        head = _head(connection)
    return {"nome": name, "bytes": path.stat().st_size, **asdict(head)}


def read_series(name: str, *, axis: str = "overall", cuts: str = "") -> dict:
    """A série por período, já recortada em faixas e reduzida entre as seeds."""
    low, high, decimals = _SCALES.get(axis, (0.0, 1.0, 0))
    with _open(name) as connection:
        _head(connection)
        return views.band_series(
            connection,
            axis=axis,
            cuts=_cuts(cuts),
            low=low,
            high=high,
            decimals=decimals,
        )


def read_curve(name: str, *, axis: str, bins: int = 40) -> dict:
    """A métrica sobre uma grandeza de vida inteira, em faixas de quantil."""
    with _open(name) as connection:
        _head(connection)
        return views.quantile_curve(connection, axis=axis, bins=bins)


def read_boxes(name: str, *, baseline: str = "ranking_greedy") -> dict:
    """Uma caixa por (braço, métrica) sobre as seeds: o eixo X colapsado."""
    with _open(name) as connection:
        _head(connection)
        return views.boxes(connection, baseline=baseline)


def read_trace(name: str, *, arm: str, seed: int) -> dict:
    """Uma simulação inteira, aluno a aluno, lida do banco.

    Não reconstrói o cenário nem refaz a simulação: o que o traço mostra já foi
    gravado quando ela rodou, e refazer custaria o mesmo que rodar de novo.
    """
    with _open(name) as connection:
        _head(connection)
        return queries.trace_script(connection, arm=arm, seed=seed)


def read_student(name: str, simulation_id: int, student: str) -> dict:
    """Tudo que um aluno fez: período a período, turma a turma."""
    with _open(name) as connection:
        _head(connection)
        return queries.student_script(
            connection, simulation_id=simulation_id, student=student
        )


def delete(name: str) -> None:
    """Apaga o arquivo. Não abre o banco: o arquivo **é** a comparação.

    Depois que a comparação termina ninguém segura o arquivo, e o `unlink` passa.
    Com ela em curso o laço segura, o sistema recusa, e isso vira 409. No Linux,
    que deixa apagar arquivo aberto, o laço seguiria escrevendo num inode já
    sem nome e o trabalho se perderia em silêncio — lá a garantia é a pausa.
    """
    path = bank_path(name)
    if not path.exists():
        raise Missing(name)
    for extra in (path, *(path.with_name(path.name + s) for s in ("-wal", "-shm"))):
        try:
            extra.unlink()
        except FileNotFoundError:
            pass
        except OSError as erro:
            raise Running(
                f"a comparação {name!r} está em uso: pause antes de apagar ({erro})"
            ) from erro


_SCALES = {"grade_average": (0.0, 10.0, 1), "reserve": (0.0, 1.0, 3)}
"""O domínio e a casa decimal com que o rótulo da faixa se escreve."""


def _open(name: str):
    path = bank_path(name)
    if not path.exists():
        raise Missing(name)
    return store(path, create=False)


def _cuts(raw: str) -> tuple[float, ...]:
    if not raw.strip():
        return ()
    try:
        return tuple(float(part) for part in raw.split(",") if part.strip())
    except ValueError as erro:
        raise ValueError(f"cortes inválidos: {raw!r}") from erro


def _head(connection):
    head = queries.comparison_head(connection)
    if head is None:
        raise Missing("o banco não tem comparação")
    return head


def _config_of(connection) -> SimulationConfig:
    return build_config(CompareRequest(**json.loads(_head(connection).cenario)))


def _free_name() -> str:
    """O primeiro nome livre. Duas comparações no mesmo segundo acontecem."""
    moment = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    candidate, index = f"{PREFIX}{moment}", 2
    while bank_path(candidate).exists():
        candidate = f"{PREFIX}{moment}-{index}"
        index += 1
    return candidate
