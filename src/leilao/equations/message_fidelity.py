"""Fidelidade da mensagem: quanto da preferência sobrevive à tradução.

    fidelidade_a = (u · m) / (‖u‖ · ‖m‖)

O cosseno entre o que o aluno quer (`u`) e o que o mecanismo de fato recebeu
(`m`), sobre o conjunto elegível. O mecanismo **nunca vê `u`**: ele vê a
mensagem — os créditos apostados no leilão, ou 1 por disciplina pedida na
linha de base, onde o peso é uniforme por construção porque um conjunto não
sabe dizer *quanto*.

O cosseno é invariante a escala (só a direção importa, que é o que sobrevive à
normalização), fica em [0, 1] com vetores não-negativos e é a régua mais
simples de defender. Serviriam também a distância de variação total ou a
divergência KL; a leitura não muda.

**Como ler.** O piso depende de quantas disciplinas estão em jogo: com a
mensagem uniforme ele vale 1 quando o aluno é indiferente entre todas e cai a
1/√n quando ele quer uma só. Compare braços **dentro do mesmo período**, onde
n é comparável; a série ao longo do tempo sobe em parte só porque o conjunto
elegível encolheu.

Duas ressalvas de escrita. Ela mistura duas decisões — com que peso o aluno
pede e *quais* ele pede. E hoje mede a **resolução da linguagem**, porque o
aluno é sincero por construção; com os coeficientes de comportamento
evoluindo, ela passa a misturar resolução com deturpação deliberada, e aí
precisa de outro nome.

Não consta no anteprojeto. **Descreve, não pontua** — como λ.
"""
from __future__ import annotations

import math


def message_fidelity(
    *, utilities: dict[str, float], message: dict[str, float]
) -> float:
    names = [name for name, utility in utilities.items() if utility > 0.0]
    if not names:
        return 0.0
    wanted = [utilities[name] for name in names]
    sent = [message.get(name, 0.0) for name in names]
    norm_wanted = math.sqrt(sum(value * value for value in wanted))
    norm_sent = math.sqrt(sum(value * value for value in sent))
    if norm_wanted <= 0.0 or norm_sent <= 0.0:
        return 0.0
    return sum(a * b for a, b in zip(wanted, sent)) / (norm_wanted * norm_sent)
