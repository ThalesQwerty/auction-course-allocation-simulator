"""A faixa de quantil a que um aluno pertence, e o nome dela.

    faixa(z, q) = ⌊ Φ(z) · q ⌋,  limitada a [0, q−1]
    nome(k, q)  = "⌊100k/q⌋–⌊100(k+1)/q⌋%"

`z` é o **nível basilar** do aluno no eixo — a posição permanente dele, na
normal padrão —, e `q` é quantas faixas o cenário pede.

**O corte é teórico, não empírico.** Como `z` é padrão-normal por construção,
`Φ(z)` é exatamente uniforme, e cortar em `k/q` dá faixas de tamanho esperado
igual **com as mesmas fronteiras em toda execução**. Cortar nos quantis
amostrais daria faixas exatamente iguais em cada simulação, mas fronteiras
diferentes em cada seed — e a média sobre N execuções estaria somando faixas
que não são a mesma coisa.

**O nome é o intervalo que a faixa cobre**, em percentil da população. O
percentil é a única unidade que serve aos três eixos de uma vez e que não se
move entre execuções: a nota, as horas e a exigência estão em escalas
diferentes, e as fronteiras delas dependem da calibragem do cenário. O valor
nessas unidades é leitura de painel, não rótulo de linha.

Com `q = 1` há uma faixa só, que é a universidade inteira, e o nome dela diz
isso em vez de "0–100%".

Não está no anteprojeto, que não recorta a população.
"""
from __future__ import annotations

import math

WHOLE = "Geral"


def quantile_band(*, level: float, bands: int) -> int:
    """O índice da faixa, de 0 (a mais baixa) a `bands − 1`."""
    if bands < 1:
        raise ValueError("é preciso ao menos uma faixa")
    share = 0.5 * math.erfc(-level / math.sqrt(2.0))
    return min(max(int(share * bands), 0), bands - 1)


def quantile_name(*, band: int, bands: int) -> str:
    """O rótulo da faixa — o intervalo de percentil que ela cobre."""
    if bands < 1:
        raise ValueError("é preciso ao menos uma faixa")
    if bands == 1:
        return WHOLE
    low = round(100 * band / bands)
    high = round(100 * (band + 1) / bands)
    return f"{low}–{high}%"


def quantile_names(bands: int) -> list[str]:
    """Os rótulos das faixas, da mais baixa para a mais alta."""
    return [quantile_name(band=band, bands=bands) for band in range(max(bands, 1))]
