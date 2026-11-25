"""A grade de correlações — o que anda junto com o quê, num recorte.

    λ_{x,y} = Σ(x−x̄)(y−ȳ) / √( Σ(x−x̄)² · Σ(y−ȳ)² )

Três grandezas **de estado do aluno** de um lado — o CR, a utilidade de reserva
e o orçamento de crédito — contra três do resultado dele: satisfação,
progresso e desperdício. Nove células, e cada uma tem previsão; é isso que faz
a tabela valer leitura.

| | satisfação | progresso | desperdício |
| CR | a eq. (57): a alocação segue o histórico? | mérito acelera a formatura? | quem ganha mais descarta mais? |
| reserva | o retorno da estratégia | exigir atrasa? | exigir protege de largar? |
| crédito | orçamento compra satisfação? | orçamento acelera? | quem tem mais sobra desperdiça? |

A célula **CR × satisfação** é a eq. (57) do anteprojeto e continua se
chamando λ onde o texto a cita. As outras oito não têm número lá.

OS EIXOS SÃO DE ESTADO, E É DE PROPÓSITO
-----------------------------------------

A seletividade `S` era o segundo eixo até 24/11/2026 e saiu em favor da
**reserva** `s = S/(S+ΣI)`, que é a mesma estratégia posta no bolo das
elegíveis. Dois motivos: `S` está na escala do interesse, que a normalização
da linha faz depender do tamanho da grade, enquanto `s` é uma participação em
[0, 1); e `s` é o limiar que a decisão de fato lê, nos dois mecanismos. Ver
`reserve_threshold`.

O **crédito** só existe no leilão, então as três células dele saem `None` no
`ranking` — e não zeradas, que se leriam como "não há correlação" em vez de
"não há moeda". É a mesma regra das demais grandezas de crédito.

Atenção a uma leitura: o orçamento de abertura é ele próprio resultado do
período anterior (eq. 36), então a linha do crédito correlaciona um desfecho
acumulado com outro. É leitura de associação, como as demais, e não de efeito.

**Reserva × desperdício não é tautológica**, embora pareça. A reserva decide
quanto o aluno pede; o desperdício acontece depois, quando o que ele ganhou
não cabe na carga que ele tem. O canal existe — pedir menos reduz a chance de
estourar a carga — mas é comportamental e mediado pela alocação, não uma
identidade: um aluno exigente pode ganhar tudo que pediu e não largar nada, e
um pouco exigente pode não ganhar nada e também não largar.

O QUE FICOU DE FORA
--------------------

A **ocupação** (carga obtida / W_a) era a coluna do meio e deu lugar ao
progresso. As duas medem coisas próximas no período, mas só o progresso
acumula: a pergunta "o mecanismo forma mais rápido?" é sobre o horizonte, e a
ocupação de um período não a responde.

A **carga efetiva** não entra como eixo. O aluno não conhece a própria
disponibilidade na hora de pedir (ver `availability`), então nenhum canal do
mecanismo pode responder a ela: do lado do que foi *obtido* o coeficiente é
zero por construção, não por resultado. Do lado do que foi *retido* ele é
mecânico, porque a carga efetiva é literalmente a capacidade da mochila.

O desperdício entra pela **razão** `ψ_retida/ψ_alocada`, e não pela diferença
que a métrica publica: aqui se quer condicionar em quanto o aluno ganhou,
senão o coeficiente mede em parte "ganhou mais". O preço é que a razão não
existe para quem não obteve nada, e esses saem da amostra — daí
`dissipation_students` sair junto.

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
    """As nove células, na ordem em que a tela as lista.

    As três de crédito são `None` onde não há moeda — ver o cabeçalho.
    """

    cr_satisfaction: float  # λ — anteprojeto, eq. (57)
    cr_progress: float
    cr_dissipation: float
    reserve_satisfaction: float
    reserve_progress: float
    reserve_dissipation: float
    credits_satisfaction: float | None
    credits_progress: float | None
    credits_dissipation: float | None
    # Quantos alunos entraram nas células de desperdício. Elas usam a razão,
    # que não existe para quem não obteve nada, então a amostra é menor que a
    # das outras e enviesada para quem ganhou alguma coisa.
    dissipation_students: int


def correlations(
    *,
    grade_averages: Sequence[float],
    reserves: Sequence[float],
    credits: Sequence[float] | None,
    satisfactions: Sequence[float],
    progresses: Sequence[float],
    allocated_satisfactions: Sequence[float],
    retained_satisfactions: Sequence[float],
) -> Correlations:
    """Todas as sequências vêm na **mesma ordem de aluno**.

    `credits` é `None` no cenário sem moeda, e é o que apaga a linha inteira
    do crédito em vez de publicá-la zerada.
    """
    kept = [
        index
        for index, allocated in enumerate(allocated_satisfactions)
        if allocated > 0.0
    ]
    ratios = [retained_satisfactions[i] / allocated_satisfactions[i] for i in kept]

    def among_kept(values: Sequence[float]) -> list[float]:
        return [values[i] for i in kept]

    return Correlations(
        cr_satisfaction=pearson(grade_averages, satisfactions),
        cr_progress=pearson(grade_averages, progresses),
        cr_dissipation=pearson(among_kept(grade_averages), ratios),
        reserve_satisfaction=pearson(reserves, satisfactions),
        reserve_progress=pearson(reserves, progresses),
        reserve_dissipation=pearson(among_kept(reserves), ratios),
        credits_satisfaction=(
            pearson(credits, satisfactions) if credits is not None else None
        ),
        credits_progress=(
            pearson(credits, progresses) if credits is not None else None
        ),
        credits_dissipation=(
            pearson(among_kept(credits), ratios) if credits is not None else None
        ),
        dissipation_students=len(kept),
    )
