"""Motor de simulação do leilão por créditos aplicado à matrícula universitária.

Três camadas.

As **equações** (`equations`) são as contas do modelo, uma por arquivo, em
funções puras que não importam nada do resto do motor.

O **leilão** (`auction`, `wdp_solver`, `entities`) resolve uma rodada isolada
do problema central P da Seção 3, por PLI exata ou por varredura gulosa — é o
mecanismo da Seção 7.1, e não sabe nada de aluno, nota ou grade. A linha de
base por CR (`ranking`) ocupa o mesmo lugar do outro lado da comparação.

A **simulação** (`simulation`, `config`, `population`, `behavior`, `grading`,
`metrics`) envolve os dois na matrícula multi-período da Seção 7.2: uma
universidade sem cursos, com uma grade em que toda obrigatória tem de ser
aprovada e os pré-requisitos ordenam o que o aluno pode cursar. E `comparison`
roda o mesmo cenário em cada braço, N vezes, que é o experimento da Seção 7.3.
"""
