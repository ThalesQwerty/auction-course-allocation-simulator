"""O multiplicador do interesse pelo turno da turma — o perfil de rotina.

    peso(x) = m_diurno,   se x é turma diurna
            = m_noturno,  se x é turma noturna

Entra no sorteio do interesse como `ln(peso)` somado ao expoente da
log-normal (`behavior.draw_interest`), que é a mesma conta dita na unidade em
que se lê: multiplicar o sorteio por `m` é somar `ln m`.

O QUE A ROTINA É, E O QUE ELA NÃO É
------------------------------------

É **traço**, não estratégia: o aluno não escolhe trabalhar de dia, e o turno
não entra numa decisão de lance — ele entra antes, no quanto cada turma vale
para aquela pessoa. Daí ser multiplicador do interesse, e não corte no
pedido: quem trabalha de dia continua podendo cursar uma turma diurna, só
prefere menos.

Os três perfis padrão, e a assimetria deles é a leitura:

| rotina | diurnas | noturnas |
| Diurno | × 2 | × 1 |
| Noturno | × 1 | × 2 |
| Indiferente | × 1 | × 1 |

O **indiferente é o neutro**, e os outros dois dobram o lado que lhes
convém — em vez de penalizar o outro. As duas formas dão a mesma preferência
depois da normalização da linha (`equations.interest_row`), porque o que
sobrevive é a razão; dobrar é a que se lê sem decimal.

**O peso não se cancela na normalização**, ao contrário do `interest_mean`:
ele varia dentro da linha, então o que ele faz é redistribuir o interesse
entre as turmas de um mesmo aluno. É nisso que ele difere de uma constante de
escala.

Não está no anteprojeto, que não modela turno.
"""
from __future__ import annotations

from collections.abc import Iterable

from .class_shift import NIGHT


def routine_weights(
    *, shifts: Iterable[str], day: float, night: float
) -> tuple[float, ...]:
    """Um peso por turma, na ordem de `shifts`."""
    return tuple(night if shift == NIGHT else day for shift in shifts)
