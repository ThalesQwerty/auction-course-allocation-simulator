"""Progresso do aluno na grade.

    progresso_a^(t) = ( Σ_{X ∈ H_a ∩ M_obg} w_X
                        + min(Σ_{X ∈ H_a ∩ M_opt} w_X, W_opt) )
                      ÷ (W_obg + W_opt)

As duas parcelas do numerador contam de formas diferentes porque a conclusão
as exige de formas diferentes: a **obrigatória** entra inteira, uma a uma, e a
**optativa** entra só até a exigência `W_opt` — aprovar o catálogo não adianta.
Com isso o teto é 1, e chegar a 1 **é** a conclusão do curso: a soma das
obrigatórias aprovadas só fecha `W_obg` quando nenhuma ficou para trás, e a
parcela optativa só fecha `W_opt` quando a exigência foi cumprida. É a eq. (40)
escrita como fração.

Sem o corte da optativa, um aluno que trocou obrigatória por optativa passaria
de 1 sem ter concluído, e a métrica mediria carga em vez de progresso — era o
que ela fazia até 23/11/2026, quando o numerador era a carga aprovada inteira.

**Não é a semestralização.** Aquela divide pelo que o aluno *poderia* ter
aprovado desde que entrou (`W_a × idade`) e mede **ritmo**: quem acabou de
entrar e foi bem marca alto. Esta divide pelo curso inteiro e mede **quanto
falta**: quem acabou de entrar marca baixo por definição, por mais que tenha
ido bem. As duas sobem com aprovação e respondem a perguntas diferentes.

**A média sobre o recorte tem viés de sobrevivência**, e é a mesma ressalva do
tempo de formatura: quem chega a 1 deixa de ser medido no período seguinte, de
modo que a média dos que ficam para de subir (e pode cair) na fase de
drenagem. Lê-se com a fração de concluintes ao lado, não sozinha.

Não está no anteprojeto.
"""
from __future__ import annotations


def progress(
    *,
    approved_required_hours: int,
    approved_elective_hours: int,
    required_hours: int,
    elective_hours_needed: int,
) -> float:
    total = required_hours + elective_hours_needed
    if total <= 0:
        return 0.0
    counted = approved_required_hours + min(
        approved_elective_hours, elective_hours_needed
    )
    return counted / total
