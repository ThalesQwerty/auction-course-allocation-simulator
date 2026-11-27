"""Como se abre o banco de uma comparação."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

__all__ = [
    "SCHEMA_VERSION",
    "open_store",
    "owner_token",
    "schema_version",
    "store",
    "transaction",
]

SCHEMA_VERSION = 6
"""Mora no cabeçalho do arquivo, nos bytes 60 a 63, e o SQLite não o interpreta."""

MIGRATIONS: dict[int, tuple[str, ...]] = {
    2: (
        "ALTER TABLE comparacao ADD COLUMN etapas_total INTEGER",
        "ALTER TABLE simulacao ADD COLUMN etapas INTEGER NOT NULL DEFAULT 0",
    ),
    3: ("ALTER TABLE aluno ADD COLUMN nome TEXT",),
    4: (
        "CREATE VIEW simulacao_valida AS"
        " SELECT * FROM simulacao m"
        "  WHERE m.estado = 'concluida'"
        "    AND NOT EXISTS ("
        "      SELECT 1 FROM simulacao o"
        "       WHERE o.seed = m.seed AND o.estado IN ('falhou', 'estourou'))",
    ),
    5: (
        "ALTER TABLE aluno_periodo ADD COLUMN disciplinas_elegiveis INTEGER",
        "ALTER TABLE aluno_periodo ADD COLUMN disciplinas_pedidas INTEGER",
        "CREATE INDEX ix_solicitacao_turma ON solicitacao(simulacao_id, turma)",
        "CREATE INDEX ix_turma_disciplina ON turma(disciplina)",
    ),
}
"""O que leva um banco da versão da chave para a seguinte. A comparação antiga
fica sem teto de passos, e a tela cai na contagem de simulações. O banco subido
à 5 mantém o `CHECK` sem `estourou`: refazer a tabela arrastaria seis tabelas
filhas, e comparação antiga não tem teto de tempo no cenário, então nunca
produz o estado. Na 6 os dois contadores da intensidade de demanda nascem
nulos, e ficam: não se recalculam fora de uma execução."""

SCHEMA = Path(__file__).with_name("schema.sql")

BUSY_TIMEOUT_MS = 30_000
"""Quanto um escritor espera o outro: há um worker por simulação e eles brigam
pelo lock de escrita em commits de poucos milissegundos."""


def owner_token() -> str:
    """Quem está rodando. Identifica o processo sem identificar a máquina."""
    return f"{os.getpid()}-{uuid4().hex[:8]}"


def schema_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def open_store(path: str | Path, *, create: bool = True) -> sqlite3.Connection:
    """Abre o banco, aplica os pragmas e recusa esquema de outra versão."""
    path = Path(path)
    fresh = not path.exists()
    if fresh and not create:
        raise FileNotFoundError(f"não há banco em {path}")
    if fresh:
        path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path, isolation_level=None, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    # Sem `auto_vacuum`: há um banco por comparação, então nada é apagado de
    # dentro de um e não há espaço a reaver. Se um dia houver, o pragma tem de
    # vir ANTES do WAL e da primeira tabela, senão é ignorado em silêncio.
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")

    found = schema_version(connection)
    if found == 0:
        # `executescript` fecha a transação corrente, então o esquema nasce fora
        # de uma. A versão é a última coisa a entrar: tabela sem versão é criação
        # interrompida, e a próxima abertura recusa em vez de fingir que deu.
        if not _empty(connection):
            connection.close()
            raise ValueError(
                f"{path} tem tabelas mas nenhuma versão de esquema: criação interrompida"
            )
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return connection
    if found != SCHEMA_VERSION:
        _upgrade(connection, found=found, path=path)
    return connection


def _upgrade(connection: sqlite3.Connection, *, found: int, path: Path) -> None:
    """Sobe de versão em versão, ou recusa o banco que não se sabe subir."""
    while found != SCHEMA_VERSION:
        statements = MIGRATIONS.get(found)
        if statements is None:
            connection.close()
            raise ValueError(
                f"{path} tem esquema versão {found}, e este código fala a {SCHEMA_VERSION}"
            )
        with transaction(connection):
            for statement in statements:
                connection.execute(statement)
            found += 1
            connection.execute(f"PRAGMA user_version = {found}")


@contextmanager
def store(path: str | Path, *, create: bool = True):
    """Abre e **fecha**. O `with` do próprio sqlite3 só confirma a transação, e
    deixar a conexão aberta impede apagar o arquivo no Windows."""
    connection = open_store(path, create=create)
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection):
    """A fronteira de commit, que é o fechamento de uma rodada ou de um período."""
    connection.execute("BEGIN")
    try:
        yield connection
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")


def _empty(connection: sqlite3.Connection) -> bool:
    found = connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
    ).fetchone()[0]
    return found == 0
