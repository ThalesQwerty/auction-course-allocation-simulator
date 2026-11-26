"""O banco de uma comparação: um arquivo SQLite por comparação.

A unidade de recuperação é a **simulação**, o par (braço, seed), porque ela é
determinística e independente: perder uma custa só o tempo dela, e refazê-la dá
bit a bit o mesmo resultado. Por isso não há checkpoint dentro de uma simulação,
e por isso toda tabela de detalhe pendura em `simulacao` com `ON DELETE CASCADE`.

O que se guarda é o que o **mecanismo decidiu**. O que saiu da seed, que é a
população, as matrizes de interesse, a disponibilidade, a seletividade e os
quantis de nota, volta chamando `simulation.setup.prepare()` sozinho, bem mais
barato que simular, e por isso não ocupa o banco.
"""
from __future__ import annotations

from .connection import (
    SCHEMA_VERSION,
    open_store,
    owner_token,
    schema_version,
    store,
    transaction,
)
from .lifecycle import (
    Claim,
    Progress,
    claim_simulation,
    create_comparison,
    fail_comparison,
    fail_simulation,
    finish_comparison,
    finish_simulation,
    pause_comparison,
    progress_of,
    requeue_stale,
    resume_comparison,
    timeout_simulation,
)
from .runner import run_into_store

__all__ = [
    "SCHEMA_VERSION",
    "Claim",
    "Progress",
    "claim_simulation",
    "create_comparison",
    "fail_comparison",
    "fail_simulation",
    "finish_comparison",
    "finish_simulation",
    "open_store",
    "owner_token",
    "pause_comparison",
    "progress_of",
    "requeue_stale",
    "resume_comparison",
    "run_into_store",
    "schema_version",
    "store",
    "timeout_simulation",
    "transaction",
]
