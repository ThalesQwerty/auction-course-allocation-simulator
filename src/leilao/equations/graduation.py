"""Conclusão de curso, estendida pelas optativas — anteprojeto, eq. (40).

    concluiu ⟺ obrigatórias ⊆ aprovadas  ∧  Σ_{x ∈ optativas ∩ aprovadas} w_x ≥ X

Toda disciplina obrigatória tem de ser aprovada **uma a uma** — não há carga
mínima a somar no lugar delas. A exigência optativa X é o oposto: nenhuma
optativa é obrigatória, e o que conta é a carga somada entre as aprovadas.
É essa substituibilidade — "quaisquer X horas servem" — que a ordenação por
CR não consegue capturar e o lance consegue.

As duas condições são independentes: dá para fechar as obrigatórias e
continuar no curso só por causa de X, e é isso que obriga o aluno a gastar
carga com optativa em vez de empurrá-la para sempre.

Sem optativa no cenário a segunda condição é vacuamente verdadeira (0 ≥ 0) e
a regra volta a ser "aprovar na grade inteira".

É a **única porta de saída** do conjunto ativo: quem não concluiu continua
disputando até o fim do horizonte.
"""
from __future__ import annotations

from collections.abc import Set


def has_graduated(
    *,
    approved: Set[str],
    required: Set[str],
    elective_hours_by_discipline: dict[str, int],
    elective_hours_needed: int,
) -> bool:
    if not required <= approved:
        return False
    earned = sum(
        hours
        for name, hours in elective_hours_by_discipline.items()
        if name in approved
    )
    return earned >= elective_hours_needed
