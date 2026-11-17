"""Retorno de créditos por disciplina cursada — anteprojeto, eq. (34).

    γ_{a,x}^(t) = round( nota/10 · k · preço pago )

O anteprojeto deixa `f_γ` em aberto — ela é o eixo de experimentação da
Seção 7.3.2 — e aqui ela tem **uma forma só**, com um parâmetro contínuo. O
que o retorno devolve é o preço pago corrigido por dois fatores: a nota, que
diz quão bem o aluno usou a vaga, e o multiplicador `k`, que diz quanto o
sistema devolve no total.

Quatro políticas discretas (`none`, `unit`, `full`, `ratio`) ocupavam este
lugar. Saíram: `unit` e `full` não liam a nota, e com elas o retorno não
separava dois aprovados — era o que a comparação com a ordenação por CR
precisa justamente demonstrar que o lance consegue. E `none` não precisa de
nome próprio: é `k = 0`, que é também como um braço da comparação desliga o
retorno sem deixar de ser o mesmo modelo.

O MULTIPLICADOR (k)
--------------------

Com `k = 1` o retorno devolve **no máximo** o preço pago, e como o gasto é esse
mesmo preço o saldo nunca cresce: o orçamento desce até `C_min` e fica lá, o
teto `C_max` vira letra morta e o retorno deixa de separar aluno de aluno —
medido, o braço com retorno saía idêntico ao sem retorno, seed a seed. Isso
passou a importar quando o crédito base somado todo período (Γ_min do
anteprojeto) saiu e o retorno virou a única entrada de crédito novo.

Com `k = 2`, o padrão, a **nota de corte é o ponto neutro** da conta contínua:
nota 5 devolve exatamente o que se pagou, acima disso o aluno sai ganhando e
abaixo sai perdendo.

O ARREDONDAMENTO, E NÃO O PISO
-------------------------------

A conta **arredonda** (meio para cima). Truncava até 17/11/2026, e a troca é
sobre a **resolução da moeda**: γ é inteiro, então a conta erra, e a pergunta
é se o erro tem viés.

O piso errava sempre para baixo — até um crédito a menos por vaga, em toda
vaga. Onde a disputa forma preço isso é ruído; onde o preço fica no piso de 1
crédito é a conta inteira, porque ali um crédito *é* a resolução. Medido no
cenário cheio com `k = 2` (23 períodos, 185.030 vagas obtidas, 84,7% delas a
1 crédito): o retorno somava **0,625** do que foi pago, 52,1% das vagas
empatavam e só 3,8% rendiam mais do que custaram. O saldo descia todo período
e o piso `C_min` o levantava de volta — 92% das aberturas de período ficavam
exatamente em `C_min`, e o braço acumulativo saía quase idêntico ao
igualitário. O retorno existe para separar aluno de aluno, e ali ele não
separava ninguém.

Arredondar faz o erro ficar **sem viés** e em no máximo meio crédito. A
preço 1 e `k = 2` a vaga passa a render 2 a partir da nota 7,5 — o prêmio
existe —, e passa a custar mais do que rende só abaixo de 2,5.

O que se perdeu, e vale declarar: **o teto `k · paid` deixou de ser exclusivo
da nota máxima**. Com `k = 2` a vaga dobra a partir de `10 · (1 − 1/(2·2·paid))`
— 7,5 num lance de 1 crédito, 9,5 num de 5, 9,75 num de 10. O prêmio máximo
ainda distingue a nota alta, mas só distingue a nota *máxima* onde o preço é
alto. É o preço de o crédito ser inteiro, e a alternativa medida era um
retorno que não premiava ninguém.

A nota de corte também deixou de ser o último ponto em que não se perde: ela
o é no limite do preço grande, e a preço 1 a faixa neutra é [2,5, 7,5). Quem
reprova barato não perde crédito — é a mesma meia unidade de erro, vista do
outro lado.

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
0,1 (`grade_for_attempt` a quantiza) e o multiplicador tem três casas, de modo
que tudo cabe em `int` e o meio-para-cima passa a ser exato.
"""
from __future__ import annotations

DEFAULT_MULTIPLIER = 2.0

# As casas que cada fator contribui: a nota tem uma decimal e o multiplicador
# entra com três. O produto dos dois sobre `paid` divide por 10^5 porque a
# fórmula ainda tem o /10 da nota sobre a escala.
_DECIMOS_DA_NOTA = 10
_MILESIMOS_DO_FATOR = 1000
_ESCALA = 100_000


def credit_return(
    *, paid: int, grade: float, multiplier: float = DEFAULT_MULTIPLIER
) -> int:
    if paid < 0:
        raise ValueError("o preço pago não pode ser negativo")
    decimos = round(grade * _DECIMOS_DA_NOTA)
    milesimos = round(multiplier * _MILESIMOS_DO_FATOR)
    return (decimos * milesimos * paid + _ESCALA // 2) // _ESCALA
