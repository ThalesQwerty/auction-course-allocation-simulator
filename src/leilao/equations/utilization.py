"""Aproveitamento de carga horária no período.

    aproveitamento_a = Σ_{x ∈ obtidas} w_x / W_a

A contraparte em **carga** do ψ, que é em **utilidade** — e as duas se separam
exatamente onde está a patologia que interessa: o aluno que concentra o lance,
ganha a disciplina que amava e deixa o resto de W_a ocioso pontua ψ alto e
aproveitamento baixo.

Conta a vaga **obtida**, não a aprovada: mede alocação, não desempenho. Fica
em [0, 1] por construção, porque a eq. (4) é restrição dos dois mecanismos.

Não consta no anteprojeto.
"""
from __future__ import annotations

from collections.abc import Iterable


def utilization(*, won: Iterable[str], hours: dict[str, int], max_hours: int) -> float:
    if not max_hours:
        return 0.0
    return sum(hours[name] for name in won) / max_hours
