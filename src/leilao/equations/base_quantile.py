"""O quantil de desempenho: o nível basilar do aluno mais o desvio da matéria.

    q_{a,x} = Φ( √s · Z_a + √(1−s) · Z_{a,x} )

    Z_a    ~ N(0,1), um por **aluno** — o nível basilar, permanente
    Z_{a,x} ~ N(0,1), um por **par** (aluno, disciplina)
    s       = `performance_stability`, a correlação entre duas matérias dele

A combinação é padrão-normal exatamente — os pesos são `√s` e `√(1−s)`, e não
`s` e `1−s`, porque o que se soma são variâncias, não amplitudes. Passá-la por
Φ devolve um **uniforme em (0, 1)**, que é o que `grading` espera: a
distribuição marginal das notas não se move: o que `s` move é só quanto do
quantil é do aluno e quanto é da matéria.

POR QUE O NÍVEL BASILAR É OBRIGATÓRIO
--------------------------------------

Com `s = 0` o quantil é resorteado em cada matéria, e a média dos quantis de
um aluno converge para 0,5: **a dispersão do CR entre alunos não tem piso** —
ela cai como `1/√D` conforme ele cursa mais disciplinas. Medido na grade de
36 obrigatórias, o desvio padrão do CR entre alunos cai de ~1,05 (com os três
perfis que existiam até 19/11/2026) para ~0,37, e continua caindo. A
ordenação por CR passaria a ordenar acúmulo de sorte, e a correlação da
eq. (57) deixaria de medir mérito.

Com `s = 1` o aluno tem uma posição só, igual em toda matéria, e "bom em
cálculo e ruim em escrita" deixa de existir. O meio é onde as duas coisas
convivem.

É traço, não sorte: nada aqui é resorteado por período nem por tentativa. A
dificuldade e a recursada movem a *distribuição* sob o quantil
(`equations.attempt_rates`); a posição relativa do aluno sobrevive a elas.

Não está no anteprojeto, que trazia a aptidão em Beta elevada à demanda da
disciplina (eq. 33).
"""
from __future__ import annotations

import math


def base_quantile(*, level: float, deviation: float, stability: float) -> float:
    """`level` é `Z_a`, `deviation` é `Z_{a,x}`; os dois da normal padrão."""
    if not 0.0 <= stability <= 1.0:
        raise ValueError("o nível basilar deve estar em [0, 1]")
    combined = math.sqrt(stability) * level + math.sqrt(1.0 - stability) * deviation
    return 0.5 * math.erfc(-combined / math.sqrt(2.0))
