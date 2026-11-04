"""A nota de uma tentativa — substitui a eq. (33) do anteprojeto.

    n = min(10, max(0, round(10 · latente) / 10))
    latente = quantil do desempenho base na normal dividida da tentativa

O aluno carrega um **quantil** por disciplina: a posição dele naquela matéria,
sorteada uma vez e permanente (ver `grading`). A disciplina e a tentativa
determinam a distribuição; o quantil diz onde ele cai dentro dela. Trocar a
dificuldade move a distribuição inteira e, com ela, a nota — sem mexer na
posição relativa do aluno, que é o que faz o desempenho ser traço.

O latente **não** é a nota: ele vive na reta inteira e pode sair da escala. As
duas operações finais são o instrumento, não o aluno:

- **arredonda** em décimos, que é a resolução em que a nota existe;
- **clipa** em [0, 10], porque a escala para aí. Quem mereceria 11 recebe 10.

É o clipe que torna o 10 alcançável. Uma distribuição contínua dá probabilidade
desprezível ao último décimo da escala — a forma anterior (aptidão em (0,1)
elevada à demanda) punha o 10 em 1,2 × 10⁻⁷ mesmo para o perfil mais forte,
ou seja, nunca. Censurar na borda concentra ali toda a massa que o instrumento
não consegue distinguir, e a chance de tirar 10 vira parâmetro declarado em
vez de consequência escondida da forma. O mesmo vale para o 0, do outro lado.

A substituição também apagou a influência da utilidade sobre a nota: ela já
governa o que o aluno pede e o que ele exclui.
"""
from __future__ import annotations

from .split_normal_quantile import split_normal_quantile

MIN_GRADE = 0.0
MAX_GRADE = 10.0


def grade_for_attempt(
    *, quantile: float, mode: float, left_sd: float, right_sd: float
) -> float:
    latent = split_normal_quantile(
        quantile=quantile, mode=mode, left_sd=left_sd, right_sd=right_sd
    )
    return min(MAX_GRADE, max(MIN_GRADE, round(10.0 * latent) / 10.0))
