"""Disponibilidade: a carga horária que o aluno tem para o período.

    δ_a^(t) ~ log-normal(perfil de disponibilidade de a, W_a)

Aqui fica só o sorteio, porque é a única parte que não é pura; a conversão em
horas inteiras, a mochila do que o aluno leva e o retorno do que ele exclui
estão em `equations.effective_load`, `equations.retained_set` e
`equations.exclusion_refund`; a forma da log-normal está em
`equations.availability_shape`.

**Em horas, não em fração de W_a.** O teto de carga é do **sistema**, não do
aluno: nada impede alguém de ter tempo para 400 h num curso que oferece 360, e
quem impede a matrícula é o alocador, que nunca entrega mais que W_a durante as
rodadas. O dado do aluno não precisa estar alinhado a priori com a regra da
instituição.

Foi a fração que a versão anterior errava. Com δ em [0, 1], alcançar a carga
cheia exigia δ ≈ 1, que numa Beta é evento de borda — e o perfil feito para
encher a carga a enchia em 0,03% dos semestres. Agora a chance de alcançar W_a
é **parâmetro declarado** do perfil, e a log-normal a entrega sem teto
artificial e sem nunca descer abaixo de zero.

**Uma por (aluno, período)**, ao contrário do desempenho, que é um só para o
curso inteiro. O desempenho é traço — quem é bom em cálculo continua bom —, mas
o tempo disponível é circunstância: muda de semestre para semestre, com o
trabalho, a família, a saúde. O que é traço é a *forma* de onde ela sai, e essa
é o perfil.

Nada é sorteado dentro do laço: a grade inteira sai da seed na inicialização,
para todos os alunos e todos os períodos de uma vez, como exige a Seção 7.3. É
sorteada também para o período anterior ao ingresso do aluno, que ele nunca
chega a viver — o custo é uma coluna a mais e o ganho é que o fluxo do gerador
não dependa de quem entrou quando.

O aluno **não conhece** o próprio perfil nem o sorteio do período corrente. Se
conhecesse a forma, a adaptação da estratégia a ela seria petição de princípio:
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
    """δ_{a,t} — as horas disponíveis de cada par (aluno, período)."""
    # Uma forma por linha, difundida sobre os períodos: o gerador consome
    # exatamente um valor por célula, de modo que o desenho da matriz não
    # depende do perfil de ninguém.
    shapes = np.array(
        [student.availability.shape(config.max_hours) for student in students]
    )
    draws = rng.lognormal(
        shapes[:, 0:1],
        shapes[:, 1:2],
        size=(len(students), config.periods),
    )
    return {
        (student.id, period + 1): float(draws[i, period])
        for i, student in enumerate(students)
        for period in range(config.periods)
    }
