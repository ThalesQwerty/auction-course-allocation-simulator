"""Retorno de créditos por disciplina cursada — anteprojeto, eq. (34).

    γ_{a,x}^(t) = round( nota/10 · 2 · preço pago )

O anteprojeto deixa `f_γ` em aberto. Aqui ela tem uma forma só, e o que o
retorno devolve é o preço pago corrigido pela nota, que diz quão bem o aluno
usou a vaga.

Quatro políticas discretas (`none`, `unit`, `full`, `ratio`) ocupavam este
lugar. Saíram: `unit` e `full` não liam a nota, e com elas o retorno não
separava dois aprovados — era o que a comparação com a ordenação por CR
precisa justamente demonstrar que o lance consegue.

POR QUE O MULTIPLICADOR É 2, E POR QUE NÃO É PARÂMETRO
-------------------------------------------------------

O fator 2 foi parâmetro de cenário até 24/11/2026. Virou constante porque não
havia o que variar: ele tem **dois** argumentos independentes apontando para o
mesmo valor, e a faixa em volta dele é estreita.

O primeiro é de simetria. O aluno que aposta `δ` perde exatamente `δ` no pior
caso (nota 0, ou exclusão, que não devolve nada) e ganha exatamente `δ` no
melhor (nota 10, que devolve `2δ`). Nenhum outro valor tem essa propriedade, e
com `n_min = 5` o ponto neutro da conta contínua cai em cima da nota de corte.

O segundo é medido, e é o mais forte. Em 14 períodos com 24 alunos por
período, a fração das aberturas de período que caem **estritamente entre**
`C_min` e `C_max` — que é onde o orçamento tem o que discriminar — por valor
do multiplicador:

    k      no piso    no teto    entre os dois
    0,0     100,0%       0,0%        0,0%
    1,0     100,0%       0,0%        0,0%
    1,5      56,1%       0,0%       43,9%
    2,0      23,5%       2,7%       73,8%
    3,0       7,6%      54,3%       38,1%

Com 1 o retorno nunca supera o gasto e o saldo desce até o piso e fica lá: o
teto vira letra morta, o retorno deixa de separar aluno de aluno, e o braço
com retorno sai idêntico ao sem retorno, seed a seed. Com 3 a metade da
população encosta no teto e o orçamento volta a não discriminar, pelo outro
lado. 2 é o único valor da faixa em que a economia de crédito não degenera.

O ARREDONDAMENTO, E NÃO O PISO
-------------------------------

A conta **arredonda** (meio para cima). Truncava até 17/11/2026, e a troca é
sobre a **resolução da moeda**: γ é inteiro, então a conta erra, e a pergunta
é se o erro tem viés.

O piso errava sempre para baixo — até um crédito a menos por vaga, em toda
vaga. Onde a disputa forma preço isso é ruído; onde o preço fica no piso de 1
crédito é a conta inteira, porque ali um crédito *é* a resolução. Medido no
cenário cheio (23 períodos, 185.030 vagas obtidas, 84,7% delas a 1 crédito): o
retorno somava **0,625** do que foi pago, 52,1% das vagas empatavam e só 3,8%
rendiam mais do que custaram. O saldo descia todo período e o piso `C_min` o
levantava de volta — 92% das aberturas ficavam exatamente em `C_min`.

Arredondar faz o erro ficar **sem viés** e em no máximo meio crédito. A preço
1 a vaga passa a render 2 a partir da nota 7,5, e passa a custar mais do que
rende só abaixo de 2,5.

O que se perdeu, e vale declarar: **o teto `2 · paid` deixou de ser exclusivo
da nota máxima**. A vaga dobra a partir de `10 · (1 − 1/(4·paid))` — 7,5 num
lance de 1 crédito, 9,5 num de 5, 9,75 num de 10. O prêmio máximo ainda
distingue a nota alta, mas só distingue a nota *máxima* onde o preço é alto.

A nota de corte também deixou de ser o último ponto em que não se perde: ela
o é no limite do preço grande, e a preço 1 a faixa neutra é [2,5, 7,5). Quem
reprova barato não perde crédito — é a mesma meia unidade de erro, vista do
outro lado. A simetria dos **extremos**, essa vale em qualquer preço.

A nota de corte `n_min` **não entra na conta**. O retorno é contínuo na nota:
quem reprova com 4,9 recebe quase tanto quanto quem passa com 5,0. Aprovar é o
que decide a grade (eq. 40); o retorno decide o poder de compra, e são
perguntas diferentes — amarrá-las faria o degrau da aprovação aparecer duas
vezes.

A CONTA É INTEIRA
------------------

A conta corre em inteiros, e continua tendo de correr: em ponto flutuante o
produto cai um ulp abaixo do inteiro que deveria dar — medido, 30 combinações
em 18.876 de (nota, preço, k) —, e com isso a fronteira do arredondamento sai
errada por um crédito exatamente onde ela é um empate. A nota anda de 0,1 em
0,1 (`grade_for_attempt` a quantiza), de modo que tudo cabe em `int` e o
meio-para-cima passa a ser exato.
"""
from __future__ import annotations

# O multiplicador da eq. (34). Constante, não parâmetro: ver a docstring.
MULTIPLIER = 2

# As casas que a nota contribui: ela tem uma decimal. O produto sobre `paid`
# divide por 10^2 porque a fórmula ainda tem o /10 da nota sobre a escala.
_DECIMOS_DA_NOTA = 10
_ESCALA = 100


def credit_return(*, paid: int, grade: float) -> int:
    if paid < 0:
        raise ValueError("o preço pago não pode ser negativo")
    decimos = round(grade * _DECIMOS_DA_NOTA)
    return (decimos * MULTIPLIER * paid + _ESCALA // 2) // _ESCALA
