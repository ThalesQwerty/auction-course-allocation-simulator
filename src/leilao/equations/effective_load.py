"""A carga horária que o aluno vai de fato cursar no período.

    Ŵ_a^(t) = round(δ_a^(t))

**δ** (`availability`) é a disponibilidade **em horas**, sorteada da log-normal
do perfil do aluno. Não é fração de nada: é o tempo que ele tem para este
período, na mesma unidade da carga das disciplinas.

Arredonda-se para o **inteiro mais próximo** porque hora é inteira no modelo.

**Não há teto.** A disponibilidade pode passar de W_a, e isso não é
inconsistência: o limite de carga é do **sistema**, e quem o aplica é o
alocador, que nunca entrega mais que W_a durante as rodadas. O dado do aluno
não precisa estar alinhado a priori com a regra da instituição — quem tem
tempo para 400 h num curso que oferece 360 simplesmente não exclui nada.

Foi justamente o alinhamento forçado que a versão anterior errava: com δ como
fração de W_a, a carga cheia exigia `δ ≥ 1`, que numa distribuição sobre [0, 1]
é evento de borda. O piso sumiu com o `round`, mas o teto artificial só sumiu
quando a disponibilidade deixou de ser fração.

O piso natural continua sendo 0 — nada impede que alguém largue o semestre
inteiro —, e a log-normal nunca desce abaixo dele.

Não é o mesmo que W_a^(t,r), a carga que o alocador desconta a cada vaga: essa
continua valendo durante as rodadas e vale o teto cheio. A carga efetiva só é
consultada **depois** da última rodada, quando o aluno decide o que leva.

Não está no anteprojeto: a disponibilidade e tudo o que ela produz são
posteriores a ele.
"""
from __future__ import annotations


def effective_load(*, availability: float) -> int:
    if availability < 0.0:
        raise ValueError("a disponibilidade deve ser >= 0")
    return round(availability)
