"""Motor de simulação do leilão por créditos aplicado à matrícula universitária.

Duas camadas. O **leilão** (`auction`, `wdp_solver`, `tie_breaking`, `entities`)
resolve uma rodada isolada do problema central P da Seção 3, por PLI exata — é o
mecanismo da Seção 7.1, e não sabe nada de aluno, nota ou grade. A **simulação**
(`simulation`, `config`, `population`, `behavior`, `grading`, `metrics`) o
envolve na matrícula multi-período da Seção 7.2: uma universidade sem cursos,
com uma grade em que toda disciplina é obrigatória e os pré-requisitos ordenam o
que o aluno pode cursar.
"""
