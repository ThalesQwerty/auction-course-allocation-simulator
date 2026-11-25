"""Retorno de créditos por disciplina cursada — anteprojeto, eq. (34)."""
from __future__ import annotations

MULTIPLIER = 2

_DECIMOS_DA_NOTA = 10
_ESCALA = 100


def credit_return(*, paid: int, grade: float) -> int:
    if paid < 0:
        raise ValueError("o preço pago não pode ser negativo")
    decimos = round(grade * _DECIMOS_DA_NOTA)
    return (decimos * MULTIPLIER * paid + _ESCALA // 2) // _ESCALA
