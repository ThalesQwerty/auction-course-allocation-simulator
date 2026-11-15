"""O retorno de crédito de uma disciplina excluída.

    γ_excluída = round(fração · preço pago)

A **fração é zero por padrão**: excluir não devolve nada. É o que torna a
exclusão socialmente cara, e ela
precisa ser — a vaga não volta para a oferta, porque se exclui depois de
encerradas as alocações do período. Sem isso, sob `none` — em que nada volta
nunca — excluir seria o melhor resultado possível do sistema.

Excluir também não é reprovar: é abstenção, fora da dicotomia
aprovado/reprovado, e por isso a regra é **própria**, e não um caso particular
de `f_γ`. Em especial, o multiplicador do retorno não entra aqui: ele
existe para premiar desempenho em disciplina **cursada**, e excluir não cursa.

A fração existe para quem quiser medir o degrau entre punir a exclusão por
inteiro e amortecê-la. O arredondamento é o do Python, e o que ele implica é
que frações pequenas zeram em lance pequeno: com fração 0,25 um lance de 1
crédito devolve 0, e `paid = 1` é o caso mais frequente, porque o orçamento
limita o aluno a lances em no máximo C_a disciplinas. A penalidade é, nesse
sentido, levemente regressiva — lance pequeno é punido proporcionalmente mais,
e lance pequeno é de quem tem pouco orçamento.

Não está no anteprojeto.
"""
from __future__ import annotations

DEFAULT_RATE = 0.0


def exclusion_refund(*, paid: int, rate: float = DEFAULT_RATE) -> int:
    if paid < 0:
        raise ValueError("o preço pago não pode ser negativo")
    return round(rate * paid)
