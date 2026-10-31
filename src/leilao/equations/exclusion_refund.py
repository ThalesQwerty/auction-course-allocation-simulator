"""O retorno de crédito de uma disciplina excluída.

    γ_excluída = paid // 2      (política `ratio`)
    γ_excluída = 0              (políticas `none`, `unit`, `full`)

A metade é o **meio-termo exato** entre perder com 0 e passar com 10, e é a
âncora certa porque `ratio` é `round(nota/10 · paid)` — n_min não aparece nela.
Excluir não é reprovar bem: é abstenção, fora da dicotomia aprovado/reprovado,
e o centro do intervalo é o lugar dela.

A divisão **inteira** é o que garante que excluir custe. Ancorar na maior nota
que reprova (n_min − 0,1) parece mais principiado, mas abre um buraco onde ele
mais dói: com n_min ≥ 6, `round(0,59 · 1) = 1`, e o aluno exclui um lance de 1
crédito sem perder nada. E `paid = 1` é o caso mais frequente, porque o
orçamento limita o aluno a lances em no máximo C_a disciplinas. Aqui a perda é
⌈paid/2⌉ ≥ 1 sempre.

Nas outras três políticas devolve 0: as três só pagam por aprovação, e excluir
não aprova. Sem essa cláusula, sob `none` — em que nada volta nunca — excluir
seria o melhor resultado possível do sistema.

A perda proporcional **não é constante**: 100% em paid=1, 50% em 2, 67% em 3,
50% em 4. Lance pequeno é punido proporcionalmente mais, e lance pequeno é de
quem tem pouco orçamento, de modo que a penalidade é levemente regressiva. É a
única forma de cobrar algo de 1 crédito em aritmética inteira, mas vale saber
ao ler a penalidade por perfil: parte do efeito vem da quantização.

O único caso em que a metade se comporta mal é `n_min < 5`, onde excluir
passaria a render mais que a aprovação raspada. `SimulationConfig` recusa isso
na entrada.

Não está no anteprojeto.
"""
from __future__ import annotations

from .credit_return import Policy


def exclusion_refund(policy: Policy, *, paid: int) -> int:
    if paid < 0:
        raise ValueError("o preço pago não pode ser negativo")
    return paid // 2 if policy == "ratio" else 0
