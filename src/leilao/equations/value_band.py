"""A faixa de valor a que um aluno pertence, e o nome dela."""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence

WHOLE = "Geral"


def ordered_cuts(cuts: Sequence[float]) -> list[float]:
    """Os cortes em ordem crescente, que é a ordem dos índices de faixa."""
    unique = sorted(set(cuts))
    if len(unique) != len(cuts):
        raise ValueError("os pontos de corte devem ser distintos")
    return unique


def value_band(*, value: float, cuts: Sequence[float]) -> int:
    """O índice da faixa, de 0 (a mais baixa) a `len(cuts)`."""
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
    """O número como a interface o escreve: vírgula decimal, sem zero à toa."""
    if decimals <= 0:
        return f"{round(value):d}"
    texto = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return (texto or "0").replace(".", ",")
