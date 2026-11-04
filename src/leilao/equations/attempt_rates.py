"""O que a dificuldade e a tentativa fazem com as duas chances da nota.

    chance de 0  = chance_base_de_0 ^ (tentativa / dificuldade)
    chance de 10 = chance_base_de_10 ^ (dificuldade / tentativa)

As chances do perfil descrevem a **disciplina de dificuldade 1 na primeira
tentativa**. Aqui elas viram as chances daquela disciplina naquela tentativa, e
a forma da distribuição sai delas por `grade_shape`, com a moda do perfil
mantida — é a distribuição que se move sob o aluno, não o aluno sob ela.

Os dois expoentes são **recíprocos**, e é daí que vêm as três propriedades que
importam. Dificuldade maior empurra a chance de zero para cima e a de dez para
baixo, porque elevar um número em (0, 1) a um expoente menor que 1 o aumenta;
tentativa maior faz o contrário. E, como os expoentes são `t/d` e `d/t`,
**dificuldade 2 na segunda tentativa reproduz exatamente dificuldade 1 na
primeira** — a lei de potência da prática, que a forma anterior da nota também
tinha e que esta preserva de graça.

Quanto a recursada rende **não** é botão à parte: quem calibra isso é a
dificuldade da disciplina, que está do outro lado dos mesmos dois expoentes.
Um botão separado seria a mesma grandeza editada duas vezes.

A utilidade não entra. Ela já decide o que o aluno pede e o que ele exclui;
deixá-la mexer também na nota era a única peça da fórmula sem forma
justificada, e a única que fabricava vão entre os mecanismos por conta própria.

Substituiu o expoente `dificuldade / (u_rel^g_u · esforço)` sobre a aptidão.
Não está no anteprojeto.
"""
from __future__ import annotations


def attempt_rates(
    *, zero_rate: float, max_rate: float, difficulty: float, attempt: int
) -> tuple[float, float]:
    if difficulty <= 0.0:
        raise ValueError("a dificuldade deve ser > 0")
    if attempt < 1:
        raise ValueError("attempt deve ser >= 1")
    return zero_rate ** (attempt / difficulty), max_rate ** (difficulty / attempt)
