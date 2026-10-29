"""A preferência que o resolvedor de fato maximiza — anteprojeto, eq. (22).

    p_{a,x} = c_{a,x} + β̂_{a,x} + α̂_{a,x} + ε_{a,x}

O lance é inteiro; os três termos somados a ele são as três camadas de
desempate da Seção 7.1.2, em ordem decrescente de força:

- **β̂** (eq. 21) é política declarada — pode valer mais que um crédito e
  mover a disputa de propósito;
- **α̂** (eq. 20) fica em [0, 1) e só decide entre lances iguais;
- **ε** fica em (0, 1/(|A|²·|B|)) e só decide quando lance, viés e ordem
  empatam, garantindo solução ótima única (Seção 6.3).

As escalas não se cruzam, e é isso que faz a soma funcionar como uma regra
lexicográfica sem precisar ser escrita como uma.
"""
from __future__ import annotations


def final_preference(
    *, bid: int, rectified_bias: int, tie_break: float, perturbation: float
) -> float:
    return bid + rectified_bias + tie_break + perturbation
