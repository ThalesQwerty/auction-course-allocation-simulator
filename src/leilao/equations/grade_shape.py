"""A forma da normal dividida da nota, a partir das três grandezas que se leem.

    entra: nota mais provável, chance de tirar 0, chance de tirar 10
    sai:   (moda, desvio esquerdo, desvio direito)

Os três parâmetros nativos da normal dividida são forma pura, e forma pura não
se lê: ninguém olha `(9; 2,55; 0,51)` e enxerga "pico em 9, quase nunca zera,
tira 10 em 3% das vezes". A interface edita as três grandezas que *se* leem, e
a conversão acontece aqui, na entrada do modelo. É o mesmo papel que
`availability_shape` faz do lado da disponibilidade.

A **moda é a locação da distribuição**, então ela entra direto: o número
digitado é literalmente o pico da curva, e a conversão só precisa achar os dois
desvios. Cada cauda fixa o seu — a chance de zero fixa a esquerda, a de dez
fixa a direita —, e como a moda está sempre dentro da escala o zero cai sempre
no ramo esquerdo e o dez sempre no direito. O sistema é bem-condicionado em
todo o espaço de parâmetros, e **toda trinca existe**: não há combinação a
recusar.

A média sai derivada, e fica **abaixo** da moda — tipicamente 1 a 2 pontos,
porque a cauda esquerda é longa (quem vai mal vai muito mal). Parametrizar pela
média, ao contrário, deixaria combinações inviáveis: com a moda presa dentro da
escala, média alta com poucos dezes não fecha.

A taxa de aprovação **não** entra aqui de propósito. `n_min` é regra de
cenário, não propriedade do aluno: se ele definisse o perfil, mudar a linha de
corte redefiniria a população em silêncio. Aqui a aprovação é o que de fato é
— resultado —, e sai calculada do perfil.

Os limiares são os da nota **arredondada**, não os da escala: a nota sai 0
quando o latente fica em 0,05 ou abaixo, e sai 10 quando chega a 9,95. Casar a
inversão com eles é o que faz "chance de tirar 10" significar exatamente isso,
e não "chance de o latente passar de 10".

Não está no anteprojeto.
"""
from __future__ import annotations

from statistics import NormalDist

_STANDARD = NormalDist()

# O latente que a nota arredondada em décimos ainda leva às pontas da escala.
ZERO_THRESHOLD = 0.05
MAX_THRESHOLD = 9.95

_BISECTIONS = 200


def grade_sds(
    *, mode: float, zero_rate: float, max_rate: float
) -> tuple[float, float]:
    """Os dois desvios, com a moda dada — cada cauda fixa o seu.

    Resolve pela fração de massa à esquerda: dado esse peso, cada desvio sai em
    forma fechada da sua própria cauda, e sobra uma equação escalar em que o
    peso tem de bater com `e/(e+d)`. Troca um sistema de duas incógnitas por uma
    bisseção, que não depende de chute inicial.

    É por aqui que a dificuldade e a tentativa entram: elas transformam as duas
    chances (`attempt_rates`) e a forma é refeita com a **moda do perfil
    mantida**. Segurar a moda é o que a mantém dentro da escala — com a média
    fixa ela sairia de [0, 10] assim que a dificuldade passasse de 2, e
    deixaria de existir nota que a realizasse.
    """
    if not ZERO_THRESHOLD < mode < MAX_THRESHOLD:
        raise ValueError("a nota mais provável deve estar dentro da escala")
    if not 0.0 < zero_rate < 1.0:
        raise ValueError("a chance de tirar 0 deve estar em (0, 1)")
    if not 0.0 < max_rate < 1.0:
        raise ValueError("a chance de tirar 10 deve estar em (0, 1)")
    if zero_rate + max_rate >= 1.0:
        raise ValueError("as chances de tirar 0 e de tirar 10 somam 1 ou mais")

    def sds(left_mass: float) -> tuple[float, float]:
        left = (mode - ZERO_THRESHOLD) / -_STANDARD.inv_cdf(
            zero_rate / (2.0 * left_mass)
        )
        right = (MAX_THRESHOLD - mode) / -_STANDARD.inv_cdf(
            max_rate / (2.0 * (1.0 - left_mass))
        )
        return left, right

    # Fora destes limites a cauda pedida não cabe na meia-normal do seu lado.
    low, high = zero_rate, 1.0 - max_rate
    margin = (high - low) * 1e-12
    low, high = low + margin, high - margin
    for _ in range(_BISECTIONS):
        middle = 0.5 * (low + high)
        left, right = sds(middle)
        if left / (left + right) - middle > 0.0:
            low = middle
        else:
            high = middle
    return sds(0.5 * (low + high))


def grade_shape(
    *, mode_grade: float, zero_rate: float, max_rate: float
) -> tuple[float, float, float]:
    """A trinca de forma do perfil: a moda, que entra, mais os dois desvios."""
    left_sd, right_sd = grade_sds(
        mode=mode_grade, zero_rate=zero_rate, max_rate=max_rate
    )
    return mode_grade, left_sd, right_sd
