"""Disponibilidade: a fração de W_a que o aluno vai de fato cursar.

    δ_a^(t) ~ Beta(perfil de disponibilidade de a)

Aqui fica só o sorteio, porque é a única parte que não é pura; a carga efetiva
que ele produz, a mochila do que o aluno leva e o retorno do que ele exclui
estão em `equations.effective_load`, `equations.retained_set` e
`equations.exclusion_refund`.

**Uma por (aluno, período)**, ao contrário da aptidão, que é uma só para o
curso inteiro. A aptidão é traço — quem é bom em cálculo continua bom —, mas o
tempo disponível é circunstância: muda de semestre para semestre, com o
trabalho, a família, a saúde. O que é traço é a *média* de onde ela sai, e essa
é o perfil.

Nada é sorteado dentro do laço: a grade inteira sai da seed na inicialização,
para todos os alunos e todos os períodos de uma vez, como exige a Seção 7.3. É
sorteada também para o período anterior ao ingresso do aluno, que ele nunca
chega a viver — o custo é uma coluna a mais e o ganho é que o fluxo do gerador
não dependa de quem entrou quando.

O aluno **não conhece** o próprio perfil nem o sorteio do período corrente. Se
conhecesse a média, a adaptação da estratégia a ele seria petição de princípio:
a conclusão entraria como entrada. Se conhecesse o valor realizado antes de
pedir, os dois mecanismos cortariam o pedido no teto certo e a exclusão
sumiria dos dois.
"""
from __future__ import annotations

import numpy as np

from .config import SimulationConfig
from .population import Student

__all__ = ["draw_availability"]


def draw_availability(
    students: list[Student],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, int], float]:
    """δ_{a,t} — a disponibilidade de cada par (aluno, período)."""
    # Uma forma por linha, difundida sobre os períodos — mesma convenção do
    # sorteio da aptidão, um valor consumido por célula.
    shapes = np.array([student.availability.shape for student in students])
    draws = rng.beta(
        shapes[:, 0:1],
        shapes[:, 1:2],
        size=(len(students), config.periods),
    )
    return {
        (student.id, period + 1): float(draws[i, period])
        for i, student in enumerate(students)
        for period in range(config.periods)
    }
