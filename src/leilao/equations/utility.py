"""A utilidade: o interesse do aluno sobre o que ele pode cursar agora.

    ũ_t = u_t + Σ_{d inelegível} max_s u_s / |alvos(d)|,   t turma elegível

    alvos(d) = ancestrais elegíveis de d, se d trava por pré-requisito
             = todas as elegíveis,        se d já saiu da grade do aluno

    u = interesse  (o sorteio normalizado — `behavior.draw_interest`)
    ũ = utilidade  (o que esta função devolve)

O índice é a **turma**, mas a elegibilidade e a herança são da
**disciplina** — o grafo de pré-requisitos não enxerga turma.

INTERESSE E UTILIDADE
---------------------

São duas palavras para dois objetos, e a fronteira entre eles é o
**histórico do aluno**. O **interesse** é o quanto ele quer cada disciplina:
sorteado por (aluno, período, disciplina) na inicialização, a partir da seed,
normalizado sobre a grade inteira e nunca mais tocado — parâmetro de entrada,
como a aptidão. A **utilidade** é esse interesse filtrado pelo que ele já
aprovou e pelo que isso destravou, recalculada a cada período — derivada em
tempo de execução.

Os zeros da eq. (42) não são máscara: são a **definição** da utilidade. Uma
disciplina que o aluno está proibido de cursar não tem utilidade para ele
naquele período, por construção, e o interesse dela vai para o que ele pode
cursar. Daí uma assimetria: o interesse se move por um motivo só (o gosto
derivou no semestre, por `interest_stability`); a utilidade, por dois, porque
o estado do aluno também mudou.

**A decisão vê utilidade, nunca interesse.** O lance, o pedido, a reserva e
ψ leem a saída daqui. O interesse cru só é lido como relatório (o histograma
de `equations.interest_histogram`).

A LINHA FICA NA ELEGIBILIDADE, NÃO NA DISPONIBILIDADE
-----------------------------------------------------

Travada por pré-requisito ou fora da grade do aluno: utilidade **zero**, e o
interesse é redistribuído. Sem vaga, sem carga, já conquistada na rodada:
utilidade **inalterada**, e nada se move. O segundo grupo é o filtro de
`available_goods` (eq. 15), que diz o que se pode pedir *nesta rodada* — não
é afirmação sobre valor: o aluno continua querendo a disciplina que lotou.
Zerar utilidade dentro daquele filtro quebraria a conservação de massa abaixo
sem erro nenhum, e ψ sairia errado.

Substitui a invariante de altura da eq. (41). Lá a utilidade era ordenada
pela posição na grade, de modo que a disciplina-porteira valia mais por
imposição. Aqui ela vale mais porque **acumulou o interesse de tudo que
destrava** — quem não quer nada à frente não é empurrado para lá, e o gosto
volta a ser gosto.

OS DOIS CASOS
-------------

**Travada por pré-requisito.** O interesse desce para as elegíveis que estão
na cadeia de pré-requisitos dela — as que, aprovadas, abrem caminho até ela.
Pré-requisito já aprovado não entra: não trava nada, e mandar interesse para
lá gastaria o sinal onde ele não tem efeito.

**Fora da grade do aluno.** Já aprovada, ou optativa que a cota dispensou:
divide igualmente entre todas as elegíveis. Adição igual não muda a ordem de
preferência — só o nível —, e é o que impede o veterano de ficar com pouca
massa de utilidade e perder todo leilão.

POR QUE NO DESTINO, E NÃO AO LONGO DO CAMINHO
---------------------------------------------

A alternativa seria cascatear em ordem topológica reversa, cada disciplina
repassando o acumulado aos seus pré-requisitos faltantes. As duas regras só
divergem quando a ramificação é assimétrica dentro de uma mesma cadeia: se C
exige B1 e B2, B1 exige A1 e B2 exige A2, A3 e A4, a cascata dá 1/2 a A1
contra 1/6 aos outros; distribuindo no destino, 1/4 para cada.

Como os pré-requisitos são **conjuntivos** — precisa de todos —, os quatro
são igualmente necessários para chegar em C, e o peso da cascata reflete
posição na árvore, não necessidade. E, como cada inelegível reparte o
**próprio interesse**, e não um acumulado, não há ordem de processamento a
resolver.

NÃO EXISTE ÓRFÃ
---------------

Se uma disciplina está travada, algum pré-requisito dela falta; subindo a
cadeia, ou se chega a uma sem pré-requisito faltante — elegível por
definição — ou o grafo tem ciclo. Sendo acíclico e finito, o conjunto de
destino nunca é vazio e a massa total se conserva sem regra de exceção. A
cláusula de guarda existe só para o caso degenerado de a cadeia terminar
numa disciplina que saiu da grade por outro motivo.

**A utilidade soma o que o interesse somava** — 1, depois da normalização do
sorteio. É isso que põe `alpha_u` na mesma unidade da utilidade: o aluno
compara participações, e `alpha_u` é um valor nessa mesma escala.

A **ordem das chaves** é a de `eligible`, que é a ordem da grade, e é carga:
é dela que as duas mochilas tiram o desempate.

Não está no anteprojeto: substitui a eq. (41).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence, Set


def utility(
    *,
    interest: dict[str, float],
    eligible: Sequence[str],
    approved: Set[str],
    prerequisites: dict[str, tuple[str, ...]],
    classes: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, float]:
    """`interest` é por **turma**; `eligible` e `prerequisites` são por
    **disciplina**. `classes` mapeia cada disciplina nas turmas dela; omitido,
    cada disciplina é a própria turma e a função devolve exatamente o que
    devolvia antes de as turmas existirem.

    A DISCIPLINA VALE O DA TURMA MAIS ÚTIL
    ---------------------------------------

    Não há sorteio no nível da disciplina: o valor dela é `max_t u_t`, porque
    o aluno só pode levar uma turma e leva a melhor que conseguir. É esse
    valor que desce quando ela está travada.

    E é por isso que a parcela entra **inteira** em cada turma do alvo, em vez
    de ser repartida entre elas: somando a mesma parcela a todas, o máximo do
    grupo sobe exatamente nela, e `Σ_d max_t` se conserva. Repartir trataria
    as turmas como partes da disciplina, e elas são **alternativas**.

    A adição igual tem três razões, e as três valem aqui:

    - a herança é o valor de **passar** na disciplina, e você passa em
      qualquer turma — ela é turma-invariante por natureza;
    - quem pegou a porteira numa turma ruim perdeu pouco, e ψ é bem-estar;
    - proporcional distribuiria massa fixa segundo razões log-normais sem
      limite superior, e quase todo o valor curricular cairia numa turma
      escolhida pela cauda.

    O preço é que ela **comprime o contraste** onde a herança é pesada: numa
    porteira as turmas ficam quase indiferentes. Por isso a qualidade da turma
    se mede no **interesse**, não aqui.
    """
    chosen = list(eligible)
    if not chosen:
        return {}

    groups = {name: tuple(classes[name]) for name in classes} if classes else None

    def names_of(discipline: str) -> tuple[str, ...]:
        return groups[discipline] if groups else (discipline,)

    open_now = set(chosen)
    result = {
        name: interest.get(name, 0.0)
        for discipline in chosen
        for name in names_of(discipline)
    }
    unlocking: dict[str, frozenset[str]] = {}

    def unlockers(name: str) -> frozenset[str]:
        """As elegíveis na cadeia de pré-requisitos de `name`."""
        cached = unlocking.get(name)
        if cached is not None:
            return cached
        # Marca antes de descer: grade cíclica seria erro de cenário, e a
        # marca a transforma em conjunto vazio em vez de recursão infinita.
        unlocking[name] = frozenset()
        found: set[str] = set()
        for previous in prerequisites.get(name, ()):
            if previous in approved:
                continue
            if previous in open_now:
                found.add(previous)
            else:
                found |= unlockers(previous)
        unlocking[name] = frozenset(found)
        return unlocking[name]

    blocked = list(groups) if groups else list(interest)
    # A parcela que vai para **todas** as elegíveis é a mesma em toda entrada,
    # então ela se acumula num escalar e entra uma vez só no fim. É aritmética
    # idêntica à do laço, e poupa um passeio pela grade inteira por disciplina
    # fora dela — com turmas, esse passeio é |elegíveis| × |turmas|.
    uniform = 0.0
    for discipline in blocked:
        if discipline in open_now:
            continue
        value = max(
            (interest.get(name, 0.0) for name in names_of(discipline)), default=0.0
        )
        if value <= 0.0:
            continue
        missing = any(p not in approved for p in prerequisites.get(discipline, ()))
        targets = sorted(unlockers(discipline)) if missing else []
        if not targets:
            uniform += value / len(chosen)
            continue
        share = value / len(targets)
        for target in targets:
            for name in names_of(target):
                result[name] += share

    if uniform:
        for name in result:
            result[name] += uniform

    return result
