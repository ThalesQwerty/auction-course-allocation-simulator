"""A preferência que o resolvedor de fato maximiza.

    p_{a,x} = c_{a,x} + ε_{a,x}

**Substitui a eq. (22) do anteprojeto**, que somava ao lance mais duas
camadas: o viés retificado β̂ (eq. 21) e o fator de desempate α̂ (eq. 20),
este em [0, 1) — "estritamente menor que 1 crédito", de modo que o desempate
nunca invertesse uma diferença de lance.

**A garantia vale entre dois pares e não sobrevive à soma.** O WDP não
compara preferências duas a duas: ele maximiza Σ p_{a,x}·z_{a,x} sobre
milhares de pares ao mesmo tempo (eq. 8). Com α̂ ∈ [0, 1) por par e milhares
de pares alocados, a massa de desempate do objetivo alcança a ordem de
milhares de créditos, e a soma passa a comprar prioridade com lance. Medido
numa rodada do cenário cheio (2.268 alunos, 69.033 pares, 6.400 vagas
preenchidas): massa de lance 29.494 contra **3.704 de desempate**, e o ótimo
da formulação antiga aloca **30.014** em lances onde o máximo possível é
**30.029** — quinze créditos entregues a quem foi superado no lance.

O que resta é o lance, que é a mensagem do aluno, e ε, que não é camada de
preferência: fica em (0, 1/(|A|²·|B|)), não tem leitura institucional e
existe só para que o ótimo seja único (Seção 6.3). Sendo ordens de grandeza
menor que um crédito **somado sobre todos os pares**, ele não inverte nada.

Com isso o objetivo passa a ser inteiro a menos de ε, e o ramifica-e-corta
poda com corte de um crédito: a mesma rodada que levava 194 s cai para 66 s.
"""
from __future__ import annotations


def final_preference(*, bid: int, perturbation: float) -> float:
    return bid + perturbation
