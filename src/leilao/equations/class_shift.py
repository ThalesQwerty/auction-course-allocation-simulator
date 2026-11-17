"""O turno das turmas de uma disciplina.

    N = ⌊k / 3⌋   turmas noturnas
    D = k − N     turmas diurnas

Um terço da oferta, arredondado para baixo, é noturno. A divisão para baixo é
o que preserva a **assimetria real** entre os turnos: o curso noturno é a
minoria, e disciplina de turma única é diurna, não meio-a-meio.

| k | onde está na grade padrão | D | N |
| 9 | 1º período | 6 | 3 |
| 8 | 2º período | 6 | 2 |
| 7 | 3º período | 5 | 2 |
| 6 | 4º período | 4 | 2 |
| 5 | 5º período | 4 | 1 |
| 4 | 6º período | 3 | 1 |
| 3 | optativa de 3 turmas | 2 | 1 |
| 2 | optativa de 2 turmas | 2 | 0 |
| 1 | optativa de 1 turma | 1 | 0 |

**As diurnas vêm primeiro**, e isso é convenção de ordem, não de valor: as
turmas de uma disciplina são `T1..Tk` na ordem da grade, e o turno é lido
dessa posição. Quem distingue as turmas para o aluno é o interesse — o
sorteio por turma de `behavior.draw_interest` e o multiplicador do perfil de
rotina (`equations.routine_weight`) —, não o índice.

O turno é o que liga a turma ao **horário** (`equations.class_schedule`): a
diurna cai num dos horários diurnos, a noturna num dos noturnos, e horário é
grupo de exclusão mútua (eq. 5).

Não está no anteprojeto, que é de turma única.
"""
from __future__ import annotations

DAY = "day"
NIGHT = "night"


def class_shifts(count: int) -> tuple[str, ...]:
    """Os turnos das `count` turmas, na ordem da grade: diurnas, depois
    noturnas."""
    if count <= 0:
        return ()
    night = count // 3
    return (DAY,) * (count - night) + (NIGHT,) * night
