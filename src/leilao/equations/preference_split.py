"""A repartição do gosto entre o permanente e o do semestre.

    log u'_{a,x,t} = σ · ( √s · P_{a,x} + √(1−s) · Q_{a,x,t} )

A preferência se parte em duas peças independentes: uma **permanente** por
par (aluno, disciplina), sorteada uma vez, e um **ruído do semestre**,
sorteado a cada período. `s` (a estabilidade) é quanto da variância fica na
primeira — e vale exatamente a correlação entre dois semestres.

**Os pesos são √s e √(1−s), não s e 1−s**, porque as duas peças são
independentes: o que se soma são as variâncias, não as amplitudes. Com os
pesos "intuitivos" a dispersão vazaria a cada período (0,58 do original em
s = 0,5), e a estabilidade viraria um segundo botão de σ — confundida
justamente com o parâmetro de que ela precisa ser independente. Assim, cada
período continua tendo exatamente a dispersão de σ.

A estabilidade é **por disciplina** quando o cenário a declara: é a sincronia
entre concorrentes que trava a fila, não a persistência em si. Se todos que
querem uma disciplina continuam querendo ao mesmo tempo, a disputa por ela
congela inteira em vez de girar; por aluno ou por célula o efeito se dilui.

Recebe dois arrays já sorteados da normal padrão — `permanent` com forma
(alunos, 1, disciplinas) e `seasonal` com (alunos, períodos, disciplinas) — e
devolve o **logaritmo** do valor preliminar. Exponenciá-lo é o passo seguinte,
em `behavior.draw_utilities`.
"""
from __future__ import annotations

import numpy as np


def preference_split(
    *,
    permanent: np.ndarray,
    seasonal: np.ndarray,
    stability: np.ndarray,
    sigma: float,
) -> np.ndarray:
    return sigma * (
        np.sqrt(stability) * permanent + np.sqrt(1.0 - stability) * seasonal
    )
