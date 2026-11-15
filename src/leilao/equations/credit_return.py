"""Retorno de créditos por disciplina cursada — anteprojeto, eq. (34).

    γ_{a,x}^(t) = ⌊ nota/10 · k · preço pago ⌋

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

Com `k = 2`, o padrão, a **nota de corte vira o ponto neutro**: nota 5 devolve
exatamente o que se pagou, acima disso o aluno sai ganhando e abaixo sai
perdendo.

O PISO, E NÃO O ARREDONDAMENTO
-------------------------------

A conta **trunca**. É o que faz do `k · paid` um teto que só a nota máxima
alcança: com `k = 2` o aluno dobra o que investiu se tirar 10, e só se tirar
10 — com 9,9 ele leva ⌊1,98·paid⌋, que fica abaixo. Arredondar daria o dobro a
quem tirou 9,8 num lance de 5, e o prêmio máximo deixaria de distinguir a nota
máxima.

O piso também garante que a nota de corte seja o **último** ponto em que o
aluno não perde: em 4,9 ele já recebe menos do que pagou, sempre.

A nota de corte `n_min` **não entra na conta**. O retorno é contínuo na nota:
quem reprova com 4,9 recebe quase tanto quanto quem passa com 5,0. Aprovar é o
que decide a grade (eq. 40); o retorno decide o poder de compra, e são
perguntas diferentes — amarrá-las faria o degrau da aprovação aparecer duas
vezes.

A CONTA É INTEIRA
------------------

`⌊nota/10 · k · paid⌋` em ponto flutuante erra por um crédito nos casos em que
o produto deveria cair exatamente sobre um inteiro e cai um ulp abaixo —
medido, 30 combinações em 18.876 de (nota, preço, k), entre elas nota 1,4 com
preço 25 e `k = 2`, onde `6,999999999999999` truncaria para 6 em vez de 7. A
nota anda de 0,1 em 0,1 (`grade_for_attempt` a quantiza), de modo que a conta
cabe inteira em `int` e o piso passa a ser exato.
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
    return decimos * milesimos * paid // _ESCALA
