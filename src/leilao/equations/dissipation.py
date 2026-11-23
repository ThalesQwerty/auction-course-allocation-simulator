"""Dissipação: o valor que foi alocado e não chegou a ser consumido.

    Δψ_a^(t) = ψ_a(alocado) − ψ_a(retido)

É a **diferença entre duas leituras do mesmo ψ**: a satisfação do que o
mecanismo entregou, menos a do que o aluno ficou depois de descartar o que não
cabia na carga efetiva (`equations.retained_set`). Lê-se na escala de ψ, onde
0,08 é "largou 8% do que queria no período".

DIFERENÇA, E NÃO RAZÃO
-----------------------

A razão `ψ_retida / ψ_alocada` responde à mesma pergunta por aluno, mas perde
três coisas que a diferença tem:

1. **Ela agrega exatamente.** A média da diferença é a diferença das médias.
   Na razão sobra a covariância entre quanto se ganha e quanto se larga — e
   essa covariância é justamente o achado que se quer medir (quem é servido
   primeiro ganha mais e esbarra mais na própria disponibilidade), de modo que
   o erro da agregação seria do tamanho do resultado.
2. **Não tem caso indefinido.** Quem não obteve nada marca 0, que é a leitura
   certa: não largou nada. A razão daria 0/0 e teria de sair da amostra —
   justamente quem o mecanismo não atendeu.
3. **Lê-se na escala de ψ**, e some ao lado dele: `ψ_retida = ψ_alocada − Δψ`.

A razão sobrevive onde ela é melhor: **dentro da correlação**
(`equations.pearson`), onde se quer condicionar em quanto o aluno ganhou — se
não, o coeficiente mede em parte "ganhou mais", que já está em CR × ocupação.

NÃO SUBSTITUI O ε
------------------

`equations.exclusion_rate` conta **vagas**: a vaga saiu da oferta e ninguém a
cursou, e esse custo é **social**. A dissipação é o custo **privado**, em
utilidade. As duas andam juntas e medem coisas diferentes; em contagem, aliás,
a "retenção" seria exatamente `1 − ε`, e em carga seria quase isso também,
porque a mochila enche até a carga efetiva.

Em carga o número seria `≈ min(1, Ŵ / carga obtida)` — função de duas
grandezas que a tela já publica. É por isso que a métrica é em **valor**.

Não consta no anteprojeto.
"""
from __future__ import annotations


def dissipation(*, allocated: float, retained: float) -> float:
    """`allocated` e `retained` são os dois ψ do mesmo aluno no mesmo período."""
    return max(0.0, allocated - retained)
