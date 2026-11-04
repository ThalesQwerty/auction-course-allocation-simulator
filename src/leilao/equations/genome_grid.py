"""A população inicial do algoritmo genético: um exemplar de cada combinação.

    |grade| = |β_u| · |β_v| · |β_n| · |α_u|

O produto cartesiano dos níveis declarados, na ordem em que eles vêm. É
**fatorial completo**, de modo que todo efeito principal e toda interação de
pares são identificáveis na 1ª geração, e cada aluno da coorte é um genótipo
distinto — fácil de explicar e de desenhar.

O tamanho da grade tem de bater com o da coorte: com os níveis padrão são
5 · 4 · 3 · 3 = 180, que é o `students_per_period` do cenário evolutivo. Sobrar
genótipo faria parte da grade não rodar; faltar faria alguns genótipos
aparecerem duas vezes e pesarem o dobro na seleção.

A GRADE SÓ EXISTE NA 1ª GERAÇÃO
--------------------------------

Depois da primeira seleção e mutação a população deixa de ser fatorial e vira
o que a evolução produziu — os genes passam a ser contínuos, e os níveis
fixam apenas o ponto de partida. A análise de efeitos principais e interações
vale para a geração 1 e só para ela; das demais sai trajetória, não desenho.

OS NÍVEIS DE α_u SÃO O FUNDO DE [0, 1]
---------------------------------------

Como as utilidades elegíveis de uma linha somam 1, `α_u` carrega um teto
embutido: no máximo `⌊1/α_u⌋` disciplinas passam do corte. E o que decide se
*alguma* passa é a maior participação da linha — numa divisão aleatória de 1
em n partes, a maior vale em média `H_n/n`, cerca de 0,31 para n = 9.

Por isso níveis "redondos" como {0, ⅓, ⅔, 1} não servem: ⅔ e 1 não são
estratégias, são desligamentos, e metade da coorte não pediria nada nunca. Os
níveis padrão — {0, 0,05, 0,1, 0,2} — são múltiplos da participação média (1/n
por construção, ~0,11 com nove elegíveis), arredondados: nada, metade da média,
a média, o dobro. O arredondamento não custa nada aqui, porque o que separa um
nível do outro é a ordem de grandeza, não a terceira casa.

Não está no anteprojeto.
"""
from __future__ import annotations

from itertools import product

from .decision_score import Behavior


def genome_grid(
    *,
    beta_u: tuple[float, ...],
    beta_v: tuple[float, ...],
    beta_n: tuple[float, ...],
    alpha_u: tuple[float, ...],
) -> tuple[Behavior, ...]:
    if not (beta_u and beta_v and beta_n and alpha_u):
        raise ValueError("todo gene precisa de ao menos um nível")
    return tuple(
        Behavior(beta_u=u, beta_v=v, beta_n=n, alpha_u=a)
        for u, v, n, a in product(beta_u, beta_v, beta_n, alpha_u)
    )
