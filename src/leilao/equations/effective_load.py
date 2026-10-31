"""A carga horária que o aluno vai de fato cursar no período.

    Ŵ_a^(t) = round(δ_a^(t) · W_a)

**δ** (`availability`) é a disponibilidade: a fração de W_a que este aluno tem
para este período, sorteada da Beta do perfil dele. Em 1 ele enche a carga; em
0,5 cursa metade do teto.

Arredonda-se para o **inteiro mais próximo**, e não para baixo. Com piso, a
carga cheia ficava inalcançável *por construção*: `⌊δ·W_a⌋ = W_a` exige
`δ ≥ 1`, que numa Beta tem probabilidade zero — de modo que todo aluno que
ganhasse W_a inteiro sempre excluiria alguma coisa, inclusive o perfil feito
para encher a carga. O erro que o arredondamento introduz é de meia hora, o que
sobre W_a é ruído; o viés do piso era estrutural.

O piso natural continua sendo 0 — nada impede que alguém largue o semestre
inteiro — e o teto nunca passa de W_a, porque `δ ≤ 1` e o arredondamento sobe
no máximo meia hora.

O `round` do Python desempata para o par, como no retorno de créditos. Aqui
quase não se aciona: o empate exato exigiria `δ·W_a` cair precisamente num
meio, e δ vem de um sorteio contínuo.

Não é o mesmo que W_a^(t,r), a carga que o alocador desconta a cada vaga: essa
continua valendo durante as rodadas e vale o teto cheio. A carga efetiva só é
consultada **depois** da última rodada, quando o aluno decide o que leva.

Não está no anteprojeto: a disponibilidade e tudo o que ela produz são
posteriores a ele.
"""
from __future__ import annotations


def effective_load(*, availability: float, max_hours: int) -> int:
    if not 0.0 <= availability <= 1.0:
        raise ValueError("a disponibilidade deve estar em [0, 1]")
    if max_hours < 0:
        raise ValueError("a carga horária máxima deve ser >= 0")
    return round(availability * max_hours)
