"""Os parâmetros da log-normal da disponibilidade, a partir de moda e chance.

    entra: moda (em horas), chance de alcançar a carga máxima, W_a
    sai:   (média logarítmica, desvio logarítmico)

    μ = ln(moda) + σ²
    σ = (−z + √(z² + 4L)) / 2,     L = ln(teto / moda),  z = Φ⁻¹(1 − p)

        teto = W_a − 0,5

Forma fechada: σ sai da raiz positiva de `σ² + σz − L = 0`, que é o que resta
quando se substitui `μ = ln(moda) + σ²` na condição `P(X ≥ teto) = p`.

A disponibilidade é a carga que o aluno tem para o período, **em horas**, e não
uma fração de W_a. A diferença é a mesma que a da nota: o teto de carga é do
**sistema**, não do aluno. Nada impede alguém de ter tempo para 400 h num
curso que só oferece 360 — o que impede é a matrícula, e isso o alocador já
garante durante as rodadas. Modelar a disponibilidade como fração punha o
limite da instituição dentro da pessoa, e com isso tornava a carga cheia um
evento de probabilidade zero por construção.

A log-normal é a família natural: o suporte é (0, ∞), de modo que a
disponibilidade **nunca fica negativa e não tem máximo artificial**. Os dois
parâmetros que ela pede são da escala logarítmica e não se leem; os dois que a
interface edita são a **moda** — o pico da curva, em horas — e a **chance de
alcançar a carga máxima**, que é a frequência com que o aluno não precisa
excluir nada.

A chance referencia W_a, que é do cenário e não do aluno. É uma dependência
assumida: "quantas vezes eu consigo encher a carga" só significa alguma coisa
contra uma carga concreta. Mudar W_a reescala o que o perfil diz, e por isso a
forma é calculada com W_a na mão, e não guardada no perfil.

O limiar é o da carga **arredondada**, não o da carga cheia: `effective_load`
devolve `round(δ)`, então 29,5 h já conta como 30 h. Casar a inversão com ele é
o que faz "chance de alcançar a carga máxima" significar exatamente isso — sem
ele o valor realizado sai alguns pontos acima do declarado.

A única exigência é **moda < W_a − 0,5**: com o pico em cima ou acima desse
limiar, `L ≤ 0` e a raiz não existe — não há log-normal cuja moda esteja no
teto e que ainda assim o alcance com a frequência pedida.

Não está no anteprojeto: a disponibilidade é posterior a ele.
"""
from __future__ import annotations

import math
from statistics import NormalDist

_STANDARD = NormalDist()


def availability_shape(
    *, mode_hours: float, full_load_rate: float, max_hours: float
) -> tuple[float, float]:
    if mode_hours <= 0.0:
        raise ValueError("a moda da disponibilidade deve ser > 0")
    if not 0.0 < full_load_rate < 1.0:
        raise ValueError("a chance de alcançar a carga máxima deve estar em (0, 1)")
    if max_hours <= 0.0:
        raise ValueError("a carga horária máxima deve ser > 0")
    # A carga efetiva arredonda, então meia hora abaixo de W_a já a alcança.
    threshold = max_hours - 0.5
    if mode_hours >= threshold:
        raise ValueError(
            "a moda da disponibilidade deve ficar abaixo da carga horária máxima"
        )
    span = math.log(threshold / mode_hours)
    z = _STANDARD.inv_cdf(1.0 - full_load_rate)
    sigma = 0.5 * (-z + math.sqrt(z * z + 4.0 * span))
    return math.log(mode_hours) + sigma * sigma, sigma
