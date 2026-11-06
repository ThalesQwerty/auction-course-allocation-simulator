"""A escada de dificuldade entre as turmas de uma disciplina.

    n_baixa = n_alta = round(k / 3)
    n_média = k − 2 · round(k / 3)

O princípio é **minimizar a diferença entre as contagens dos três níveis**,
com a restrição de que para cada turma fácil haja uma difícil. As duas metades
fazem trabalhos diferentes:

- **`n_baixa = n_alta`** fixa a média **geométrica** no nível do meio, para
  todo `k`. É a garantia de calibragem, e a geométrica é o invariante certo
  porque a dificuldade entra em `equations.attempt_rates` como expoentes
  recíprocos (`zero_rate^(t/d)` e `max_rate^(d/t)`): `d` e `1/d` aparecem
  simetricamente, e o centro natural da escala é multiplicativo.

- **Contagens iguais** seguram a variância dentro do grupo em
  `≈ (2/3)·ln(razão)²`, que é a intensidade do tratamento — o tamanho do
  prêmio por ganhar a turma boa.

Com níveis fixos e contagens inteiras dá para segurar exatamente *o centro* ou
*a amplitude*, não os dois. O centro é o que vale segurar: o resíduo da
amplitude é ruído de arredondamento, fica dentro de ±25% do alvo e **não
acompanha o período**.

É isso que a regra por índice não fazia. Atribuindo as altas às primeiras
turmas, o grupo encolhe **pela ponta fácil** e a média sobe com o funil — de
1,17 com 9 turmas para 1,75 com 4 —, correlacionando dificuldade com o período
e, nas optativas, com o número de vagas.

`k/3` nunca cai exatamente em `x,5`, então não há empate de arredondamento a
desempatar.

A saída é uma tupla de **multiplicadores** sobre a dificuldade declarada da
disciplina: com os três níveis iguais a 1 — o padrão — ela some, e todas as
turmas herdam a dificuldade do grupo.

Não está no anteprojeto: a simulação dele é de turma única.
"""
from __future__ import annotations


def class_difficulty(
    *, count: int, levels: tuple[float, float, float]
) -> tuple[float, ...]:
    """`levels` é (baixa, média, alta). A ordem da saída é a das turmas."""
    if count < 1:
        raise ValueError("a disciplina precisa de pelo menos uma turma")
    low, middle, high = levels
    extremes = round(count / 3)
    return (
        (low,) * extremes + (middle,) * (count - 2 * extremes) + (high,) * extremes
    )
