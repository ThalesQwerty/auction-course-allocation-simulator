"""A nota de uma tentativa — anteprojeto, eq. (33).

    n = round(100 · a^E) / 10

        E           = dificuldade / (u_rel^g_u · esforço)
        esforço     = 1 + g_t · (tentativa − 1)

- **a** é a aptidão do aluno naquela disciplina, em (0, 1), sorteada uma vez
  e persistente. Com E = 1 a nota *é* a aptidão, o que lhe dá leitura direta:
  "a nota que este aluno tiraria nesta disciplina, de dificuldade padrão, de
  primeira".
- A **dificuldade** entra em múltiplos da disciplina padrão.
- **u_rel** é a utilidade da disciplina para o aluno em múltiplos da
  indiferença (`u · |disciplinas|`), e **g_u** o ganho por utilidade.
- A **tentativa** é a vez em que ele está cursando, e **g_t** o ganho por
  recursada.

Os dois ganhos dividem o denominador do expoente, e por isso se leem juntos:
cada um diz quanto um fator desconta da demanda que a disciplina faz. Com os
dois em 1 o expoente é a dificuldade dividida pela tentativa, de modo que
**dificuldade 2 na segunda tentativa equivale a dificuldade 1 na primeira** —
a lei de potência da prática.

A forma de potência tem história generativa: se a disciplina são E unidades
independentes e o aluno domina cada uma com probabilidade `a`, então `a^E` é a
chance de dominar todas. De quebra ela respeita os limites por construção —
`a^E` nunca sai de (0, 1) —, ao contrário da normal truncada, que empilhava
massa nas pontas.

Arredonda-se com `round`, e não com `floor`: com `a < 1` e expoente positivo o
produto nunca chega a 100, e truncando o teto da escala seria 9,9.
"""
from __future__ import annotations

# Abaixo disto a aptidão produziria 0,0 ou 1,0 exatos e a nota degeneraria.
# O gerador de Beta devolve as duas pontas para parâmetros pequenos.
APTITUDE_GUARD = 1e-9


def grade_for_attempt(
    *,
    aptitude: float,
    difficulty: float,
    relative_utility: float,
    attempt: int,
    utility_gain: float,
    retake_gain: float,
) -> float:
    if attempt < 1:
        raise ValueError("attempt deve ser >= 1")
    a = min(1.0 - APTITUDE_GUARD, max(APTITUDE_GUARD, aptitude))
    utility = relative_utility**utility_gain if relative_utility > 0.0 else 1.0
    if utility <= 0.0:
        utility = 1.0
    attempts = 1.0 + retake_gain * (attempt - 1)
    if attempts <= 0.0:
        raise ValueError("o ganho por recursada zerou as tentativas efetivas")
    return round(100.0 * a ** (difficulty / (utility * attempts))) / 10.0
