"""A perturbação do gosto entre períodos, refletida nas bordas."""
from __future__ import annotations

import math


def reflect(value: float) -> float:
    """Dobra um real qualquer para dentro de [0, 1] pela onda triangular."""
    folded = math.fmod(value, 2.0)
    if folded < 0.0:
        folded += 2.0
    return 1.0 - abs(1.0 - folded)


def reflected_anchor(*, anchor: float, shock: float) -> float:
    """A posição do período: a âncora abalada e dobrada de volta."""
    if not 0.0 <= anchor <= 1.0:
        raise ValueError("a âncora deve estar em [0, 1]")
    return reflect(anchor + shock)


FULL_SHOCK = 2.0


def shock_scale(stability: float) -> float:
    """O desvio do abalo, a partir da estabilidade declarada."""
    return FULL_SHOCK * (1.0 - min(1.0, max(0.0, stability)))


def reflect_array(values):
    """A mesma dobra, sobre um array inteiro."""
    import numpy as np

    folded = np.mod(np.asarray(values, dtype=float), 2.0)
    return 1.0 - np.abs(1.0 - folded)
