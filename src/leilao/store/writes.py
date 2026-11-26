"""Os INSERT das tabelas de detalhe.

Cada grupo entra por `executemany` dentro da transação do período: são centenas
de linhas, e linha por linha com commit próprio seria ordens de magnitude pior.
"""
from __future__ import annotations

__all__ = ["INSERTS"]

INSERTS = {
    "aluno": "INSERT INTO aluno VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    "periodo": "INSERT INTO periodo VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    "rodada": "INSERT INTO rodada VALUES (?,?,?,?,?,?,?)",
    "aluno_periodo": "INSERT INTO aluno_periodo VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    "solicitacao": "INSERT INTO solicitacao VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
    "turma_periodo": "INSERT INTO turma_periodo VALUES (?,?,?,?,?,?,?,?,?,?)",
}
