"""A utilidade: o interesse do aluno sobre o que ele pode cursar agora.

    I_{a,X} = (1/|X|) · Σ_{x ∈ X} i_{a,x}

                I_{a,X} + Σ_{Y ∈ seq(X)} I_{a,Y} / |M_a ∩ req(Y)|
    U_{a,X} = ───────────────────────────────────────────────────
                     Σ_{Z ∈ M_a ∪ seq(M_a)} I_{a,Z}

    u_{a,x} = U_{a,X} · i_{a,x} / max_{y ∈ X} i_{a,y}

    i = interesse   (o sorteio normalizado — `behavior.draw_interest`)
    I = o interesse da **disciplina**: a média das turmas dela
    U = a utilidade da disciplina;  u = a utilidade da turma
    M_a = as disciplinas elegíveis no período (eq. 42)
    seq(X) = os sucessores diretos de X;  req(Y) = os pré-requisitos de Y

INTERESSE E UTILIDADE
---------------------

São duas palavras para dois objetos, e a fronteira entre eles é o
**histórico do aluno**. O **interesse** é o quanto ele quer cada turma:
sorteado por (aluno, período, turma) na inicialização, a partir da seed,
normalizado sobre a grade inteira e nunca mais tocado — parâmetro de entrada,
como o quantil de desempenho. A **utilidade** é esse interesse filtrado pelo
que ele já aprovou e pelo que isso destravou, recalculada a cada período —
derivada em tempo de execução.

Os zeros da eq. (42) não são máscara: são a **definição** da utilidade. Uma
disciplina que o aluno está proibido de cursar não tem utilidade para ele
naquele período, por construção.

**A decisão vê utilidade, nunca interesse.** O lance, o pedido, a reserva e
ψ leem a saída daqui. O interesse cru só é lido como relatório (o histograma
de `equations.interest_histogram`).

A DISCIPLINA É A MÉDIA DAS TURMAS, A TURMA É A FRAÇÃO DA DISCIPLINA
--------------------------------------------------------------------

`I_{a,X}` é a **média**, não o máximo: o valor da matéria para o aluno não
depende de quantas seções dela a universidade abriu, e a média é a única
estatística que não se move quando se abre uma turma a mais. O máximo faria
disciplina com muitas turmas valer mais só por ter mais sorteios.

Na volta, `u_{a,x}` é `U_{a,X}` escalado pela razão entre a turma e a melhor
turma do grupo. Daí **a melhor turma de cada disciplina vale exatamente
`U_{a,X}`** e as irmãs valem menos, na proporção em que o aluno as prefere
menos. É o que dá sentido à segunda mochila de `concave_bids`: o aluno
reparte a fatia da disciplina entre as seções, e o hedge custa utilidade.

A HERANÇA É DE UM NÍVEL
-----------------------

A disciplina elegível acumula o interesse das que ela **destrava
imediatamente** — um período à frente, não a cadeia inteira. O aluno olha o
próximo passo: querer o que vem depois de amanhã não é previsão que ele
faça, e cascatear a grade inteira faria toda porteira da raiz herdar o curso
todo.

A parcela de `Y` é repartida entre os pré-requisitos de `Y` que **estão
elegíveis agora** (`M_a ∩ req(Y)`). Como o pré-requisito é conjuntivo —
precisa de todos —, cada um é igualmente necessário, e repartir é o que
impede que destravar `Y` seja contado uma vez por porteira. Pré-requisito já
aprovado não entra na conta: ele não trava nada.

A porteira vale mais que a terminal, mas **porque acumulou o interesse do que
destrava**, e não porque uma desigualdade o impôs — era isso que a invariante
de altura da eq. (41) fazia, e é o que ela deixou de fazer.

A SOMA É 1, E ISSO É ARITMÉTICA, NÃO CALIBRAGEM
------------------------------------------------

`Σ_{X ∈ M_a} U_{a,X} = 1`, em todo período e para todo aluno. O numerador
somado sobre `M_a` conta cada `I_{a,Y}` de um sucessor exatamente
`|M_a ∩ req(Y)|` vezes, uma por porteira elegível, e as frações se recompõem
em `I_{a,Y}` inteiro; sobra `Σ_{M_a} I + Σ_{seq(M_a)} I`, que é o
denominador.

A união é **disjunta**: se `Y` é sucessor de um elegível `X`, então `X` é
pré-requisito não aprovado de `Y`, e `Y` não é elegível. Por isso o
denominador soma os dois conjuntos sem risco de contar duas vezes — e por
isso o laço pode pular o sucessor que, por grade malformada, aparecesse
elegível.

A consequência é que **ψ dispensa denominador**: `Σ_d max_t u = Σ_d U = 1`,
de modo que a satisfação volta a ser a soma simples das utilidades atendidas
(`equations.satisfaction`). O aluno que levasse a melhor turma de toda
disciplina elegível marcaria exatamente 1.

O que fica **fora** da conta: a disciplina já aprovada, a optativa que a cota
dispensou e tudo que está a dois ou mais níveis de distância. O interesse
delas não é redistribuído — ele simplesmente não entra, e o denominador o
ignora. É a diferença entre esta regra e a redistribuição que existiu até
16/11/2026, que conservava a massa da linha inteira.

A **ordem das chaves** é a de `eligible`, que é a ordem da grade, e é carga:
é dela que as duas mochilas tiram o desempate.

Não está no anteprojeto: substitui as eqs. (41) e (43).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def utility(
    *,
    interest: Mapping[str, float],
    eligible: Sequence[str],
    successors: Mapping[str, Sequence[str]],
    prerequisites: Mapping[str, Sequence[str]],
    classes: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, float]:
    """`interest` é por **turma**; `eligible`, `successors` e `prerequisites`
    são por **disciplina**. `classes` mapeia cada disciplina nas turmas dela;
    omitido, cada disciplina é a própria turma.
    """
    chosen = list(eligible)
    if not chosen:
        return {}
    open_now = set(chosen)

    def names_of(discipline: str) -> Sequence[str]:
        return classes[discipline] if classes else (discipline,)

    mean: dict[str, float] = {}

    def discipline_interest(discipline: str) -> float:
        """I_{a,X} — a média do interesse sobre as turmas da disciplina."""
        cached = mean.get(discipline)
        if cached is not None:
            return cached
        names = names_of(discipline)
        value = (
            sum(interest.get(name, 0.0) for name in names) / len(names)
            if names
            else 0.0
        )
        mean[discipline] = value
        return value

    numerator: dict[str, float] = {}
    denominator = sum(discipline_interest(discipline) for discipline in chosen)
    counted: set[str] = set()
    for discipline in chosen:
        accumulated = discipline_interest(discipline)
        for heir in successors.get(discipline, ()):
            # Sucessor de elegível não é elegível — ver a docstring. A guarda
            # existe para a grade malformada não quebrar a soma 1.
            if heir in open_now:
                continue
            gates = sum(
                1 for previous in prerequisites.get(heir, ()) if previous in open_now
            )
            if not gates:
                continue
            accumulated += discipline_interest(heir) / gates
            if heir not in counted:
                counted.add(heir)
                denominator += discipline_interest(heir)
        numerator[discipline] = accumulated

    result: dict[str, float] = {}
    for discipline in chosen:
        names = names_of(discipline)
        best = max((interest.get(name, 0.0) for name in names), default=0.0)
        share = numerator[discipline] / denominator if denominator > 0.0 else 0.0
        for name in names:
            result[name] = (
                share * interest.get(name, 0.0) / best if best > 0.0 else 0.0
            )
    return result
