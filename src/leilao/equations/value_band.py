"""A faixa de valor a que um aluno pertence, e o nome dela.

    faixa(y, κ) = |{ c ∈ κ : c ≤ y }|
    nome(k, κ)  = "[κ_{k−1}, κ_k)", com os extremos fechados pelo domínio

`y` é o valor **corrente** da grandeza no aluno — o CR, a utilidade de
reserva, o saldo de créditos — e `κ` são os pontos de corte que o cenário
declara. Com `q` cortes saem `q + 1` faixas, e a de índice 0 é a mais baixa,
como em todo recorte ordenado do projeto.

O CORTE É NO VALOR, NÃO NO QUANTIL
-----------------------------------

Houve um corte por quantil sobre o **nível basilar** do aluno até 24/11/2026,
e a diferença entre os dois não é de escala: é de pergunta.

O corte basilar nomeava um **tipo de aluno** — posição permanente, fixada pela
seed, idêntica nos dois braços —, e era o que tornava a diferença entre
mecanismos atribuível ao mecanismo. O corte por valor nomeia um **estado do
sistema**: o que acontece com quem chega com CR alto, independentemente de
como chegou. Condicionar no basilar seria errado para essa pergunta, porque o
basilar é um latente que o mecanismo não lê — o que a alocação lê é o valor
corrente.

O preço é que a faixa deixa de ser a mesma gente nos dois braços: cada
mecanismo produz CR alto em quem tem perfil diferente. A leitura que isso
sustenta é "quem se apresenta com CR alto se sai assim de cada lado", e não
"o mecanismo ajudou os alunos fortes" — essa segunda exigiria o corte por
tipo, que saiu.

A FRONTEIRA É FIXA; QUEM SE MOVE É A POPULAÇÃO
-----------------------------------------------

O corte por quantil **amostral** foi recusado nas duas versões do recorte, e
pelo mesmo motivo: ele daria faixas de tamanho igual dentro de cada simulação
e fronteiras diferentes a cada seed, e a média sobre N execuções estaria
somando faixas que não designam a mesma coisa. O corte basilar escapava disso
de graça, porque o basilar é normal padrão e o quantil teórico dele é fixo por
construção; o valor corrente não tem essa sorte e precisa da fronteira
declarada.

O que **não** é problema é o aluno mudar de faixa no decorrer dos períodos:
isso é o conteúdo da medida, não ruído nela. Fronteira fixa com população
móvel é o que deixa a mobilidade visível — re-sortear a cada período pelo
valor corrente a esconderia, porque aí a faixa persegue o aluno e a média dela
fica plana por construção.

A consequência aceita é que as faixas têm **tamanhos diferentes**, e os
extremos costumam ser os finos. Isso não ameaça a validade (a média de uma
faixa estima `E[Y | y ∈ faixa]`, que não exige n igual), mas torna o `n` de
cada faixa grandeza de leitura em vez de detalhe de implementação: sem ele não
se distingue efeito de seis alunos.

O NOME É O INTERVALO, NAS UNIDADES DA GRANDEZA
-----------------------------------------------

O recorte basilar rotulava em percentil porque era a única unidade que servia
aos três eixos de uma vez. Aqui cada eixo tem unidade própria e ela é mais
informativa: "CR 8,5–10" diz o que "80–100%" não dizia. As faixas das pontas
são fechadas pelo **domínio** da grandeza (`low`/`high`), e não por infinito,
porque o domínio é conhecido: o CR vive em [0, 10], a reserva em [0, 1) e o
saldo entre `C_min` e `C_max`.

Sem corte nenhum há uma faixa só, que é a população inteira, e o nome dela diz
isso em vez de repetir o domínio.

Não está no anteprojeto, que não recorta a população.
"""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence

WHOLE = "Geral"


def ordered_cuts(cuts: Sequence[float]) -> list[float]:
    """Os cortes em ordem crescente, que é a ordem dos índices de faixa.

    A interface os coleta do maior para o menor, porque é assim que a legenda
    se lê; o índice da faixa cresce com o valor, porque é assim que todo
    recorte ordenado do projeto se indexa. A conversão mora aqui para que os
    dois lados possam falar cada um na sua ordem.
    """
    unique = sorted(set(cuts))
    if len(unique) != len(cuts):
        raise ValueError("os pontos de corte devem ser distintos")
    return unique


def value_band(*, value: float, cuts: Sequence[float]) -> int:
    """O índice da faixa, de 0 (a mais baixa) a `len(cuts)`.

    A comparação é `corte ≤ valor`, de modo que o corte pertence à faixa que
    ele abre: com cortes 5 e 8, um CR exatamente 8 está em "8–10".
    """
    return bisect_right(ordered_cuts(cuts), value)


def value_band_name(
    *,
    band: int,
    cuts: Sequence[float],
    low: float,
    high: float,
    decimals: int = 0,
) -> str:
    """O rótulo da faixa — o intervalo que ela cobre, nas unidades da grandeza."""
    ordered = ordered_cuts(cuts)
    if not ordered:
        return WHOLE
    if not 0 <= band <= len(ordered):
        raise ValueError("faixa fora do intervalo dos cortes")
    start = low if band == 0 else ordered[band - 1]
    end = high if band == len(ordered) else ordered[band]
    return f"{_number(start, decimals)}–{_number(end, decimals)}"


def value_band_names(
    *,
    cuts: Sequence[float],
    low: float,
    high: float,
    decimals: int = 0,
) -> list[str]:
    """Os rótulos das faixas, da mais baixa para a mais alta."""
    return [
        value_band_name(band=band, cuts=cuts, low=low, high=high, decimals=decimals)
        for band in range(len(ordered_cuts(cuts)) + 1)
    ]


def _number(value: float, decimals: int) -> str:
    """O número como a interface o escreve: vírgula decimal, sem zero à toa.

    `decimals` é o **teto** de casas, e não um gabarito: um corte em 8,5 sai
    "8,5" e um em 5 sai "5", de modo que o rótulo não carregue precisão que o
    corte não tem.
    """
    if decimals <= 0:
        return f"{round(value):d}"
    texto = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return (texto or "0").replace(".", ",")
