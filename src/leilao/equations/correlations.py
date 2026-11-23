"""A grade de correlações — o que anda junto com o quê, num recorte.

    λ_{x,y} = Σ(x−x̄)(y−ȳ) / √( Σ(x−x̄)² · Σ(y−ȳ)² )

Duas grandezas **do aluno** de um lado — o CR e a seletividade — contra três
do resultado dele: satisfação, ocupação e dissipação. Seis células, e cada uma
tem previsão; é isso que faz a tabela valer leitura.

| | satisfação | ocupação | dissipação |
| CR | a eq. (57): a alocação segue o histórico? | mérito compra carga? | quem ganha mais descarta mais? |
| seletividade | o retorno da estratégia | concentrar custa carga? | exigir protege de largar? |

A célula **CR × satisfação** é a eq. (57) do anteprojeto e continua se
chamando λ onde o texto a cita. As outras cinco não têm número lá.

O QUE FICOU DE FORA
--------------------

A **carga efetiva** não entra como eixo. O aluno não conhece a própria
disponibilidade na hora de pedir (ver `availability`), então nenhum canal do
mecanismo pode responder a ela: do lado do que foi *obtido* o coeficiente é
zero por construção, não por resultado. Do lado do que foi *retido* ele é
mecânico, porque a carga efetiva é literalmente a capacidade da mochila.

A dissipação entra pela **razão** `ψ_retida/ψ_alocada`, e não pela diferença
que a métrica publica: aqui se quer condicionar em quanto o aluno ganhou,
senão o coeficiente mede em parte "ganhou mais", que já está na coluna da
ocupação. O preço é que a razão não existe para quem não obteve nada, e esses
saem da amostra — daí `dissipation_students` sair junto.

**Descreve, não pontua.** Qual lado é melhor depende de alocar por mérito
passado ou por necessidade, e essa é escolha do leitor.

Sem variância em algum dos lados o coeficiente não existe, e vale 0.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .pearson_correlation import pearson


@dataclass(frozen=True)
class Correlations:
    """As seis células, na ordem em que a tela as lista."""

    cr_satisfaction: float  # λ — anteprojeto, eq. (57)
    cr_occupancy: float
    cr_dissipation: float
    selectivity_satisfaction: float
    selectivity_occupancy: float
    selectivity_dissipation: float
    # Quantos alunos entraram nas duas células de dissipação. Elas usam a
    # razão, que não existe para quem não obteve nada, então a amostra é menor
    # que a das outras quatro e enviesada para quem ganhou alguma coisa.
    dissipation_students: int


def correlations(
    *,
    grade_averages: Sequence[float],
    selectivities: Sequence[float],
    satisfactions: Sequence[float],
    occupancies: Sequence[float],
    allocated_satisfactions: Sequence[float],
    retained_satisfactions: Sequence[float],
) -> Correlations:
    """Todas as sequências vêm na **mesma ordem de aluno**."""
    kept = [
        index
        for index, allocated in enumerate(allocated_satisfactions)
        if allocated > 0.0
    ]
    ratios = [retained_satisfactions[i] / allocated_satisfactions[i] for i in kept]
    return Correlations(
        cr_satisfaction=pearson(grade_averages, satisfactions),
        cr_occupancy=pearson(grade_averages, occupancies),
        cr_dissipation=pearson([grade_averages[i] for i in kept], ratios),
        selectivity_satisfaction=pearson(selectivities, satisfactions),
        selectivity_occupancy=pearson(selectivities, occupancies),
        selectivity_dissipation=pearson([selectivities[i] for i in kept], ratios),
        dissipation_students=len(kept),
    )
