"""Satisfação do aluno num período — anteprojeto, eq. (51).

    ψ_a = Σ_{x ∈ B} u_{a,x} · z_{a,x}

A fração do que o aluno queria naquele período e de fato obteve. **Não há
denominador**: `equations.utility` faz `Σ_{X ∈ M_a} U_{a,X} = 1`, e a melhor
turma de cada disciplina vale exatamente `U_{a,X}` — então a soma do que ele
poderia levar, uma turma por disciplina, é 1 por construção.

É utilidade, e não interesse, porque disciplina que ele não podia cursar não
é desejo atendível.

**O `U_a` da eq. (43) saiu de cena**, e vale saber qual leitura você está
olhando. Houve duas antes desta: a soma sobre o conjunto elegível, que variava
de ~0,002 a ~0,65 entre linhas e premiava estar num período pobre de opções; e
a soma das melhores turmas, que era `≤ 1` e ficava abaixo de 1 porque a
redistribuição espalhava massa pelas irmãs. Agora o teto é 1 e é **atingível**:
o ingressante que recebe a matrícula garantida inteira num cenário sem
optativa marca exatamente 1.

`allocated` pode trazer disciplina fora de `utilities` (já aprovada, por
exemplo); ela é ignorada, que é o certo — não é desejo deste período.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping


def satisfaction(
    *, utilities: Mapping[str, float], allocated: Iterable[str]
) -> float:
    return sum(utilities.get(name, 0.0) for name in allocated)
