"""Em que estado terminou cada disciplina que ainda falta ao aluno.

    catálogo \\ aprovadas-antes
        = não elegível ⊎ não solicitada ⊎ indeferida ⊎ excluída ⊎ reprovada ⊎ aprovada

Os seis estados **particionam** o que ainda falta, de modo que a soma deles é o
tamanho do denominador e nenhuma disciplina é contada duas vezes. A cadeia é um
funil, cada estado o resto do anterior:

    ainda falta ─┬─ não elegível   pré-requisito pendente, ou optativa que a
                 │                 cota já dispensou
                 └─ elegível ──┬── não solicitada
                               └─ solicitada ─┬─ indeferida
                                              └─ obtida ─┬─ excluída
                                                         └─ cursada ─┬─ reprovada
                                                                     └─ aprovada

**O denominador tira as já aprovadas**, e isso não é detalhe. O complemento da
eq. (42) juntaria "já aprovada" com "bloqueada" num estado só, e os dois andam
em sentidos opostos: o primeiro cresce com o progresso do aluno, o segundo
encolhe com ele. Somados, se cancelam em parte — e a faixa esconderia a própria
história. Tirando as aprovadas do denominador, "não elegível" passa a significar
só *bloqueada*, e cai monotonicamente conforme ele destrava a grade.

A contagem é de **pares (aluno, disciplina)**, e quem agrega tira a média por
aluno, nunca a soma: a soma seria governada pela população, que sobe no
escalonamento de ingresso e despenca na drenagem, e o gráfico mostraria o
tamanho da universidade em vez do mecanismo.

**A unidade é a disciplina, não a turma**, e por isso `groups` existe: o que o
aluno pede, ganha e retém vem por turma, e aqui é dobrado no grupo dela antes
de classificar. Sem isso o estado seria de turma e a cadeia se partiria no
meio — `aprovada` compararia turmas contra o histórico, que é por disciplina,
e não acharia nenhuma. Sem `groups` cada bem é o próprio grupo, como em
`equations.available_goods`, e o caso de turma única fica idêntico.

Não está no anteprojeto.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestStates:
    """Os seis estados de um recorte.

    Os campos são `float` porque a mesma estrutura carrega a contagem de um
    aluno (inteiros) e a média de um grupo. A ordem dos campos é a do funil, do
    mais distante ao mais bem-sucedido — e é a ordem em que a interface
    empilha as faixas.
    """

    not_eligible: float
    not_requested: float
    refused: float
    excluded: float
    failed: float
    approved: float

    @property
    def total(self) -> float:
        """O denominador: quanto da grade ainda falta ao aluno."""
        return (
            self.not_eligible
            + self.not_requested
            + self.refused
            + self.excluded
            + self.failed
            + self.approved
        )

    @classmethod
    def average(cls, rows: "list[RequestStates]") -> "RequestStates":
        """A média por aluno de um recorte — nunca a soma.

        Recorte vazio dá tudo zero, e quem decide se publica ou não é o
        chamador: aqui não há como distinguir "ninguém largou nada" de "não
        havia ninguém".
        """
        if not rows:
            return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        size = len(rows)
        return cls(
            not_eligible=sum(r.not_eligible for r in rows) / size,
            not_requested=sum(r.not_requested for r in rows) / size,
            refused=sum(r.refused for r in rows) / size,
            excluded=sum(r.excluded for r in rows) / size,
            failed=sum(r.failed for r in rows) / size,
            approved=sum(r.approved for r in rows) / size,
        )


def request_states(
    *,
    catalogue: Iterable[str],
    approved: Set[str],
    eligible: Iterable[str],
    requested: Set[str],
    won: Set[str],
    retained: Set[str],
    groups: Mapping[str, str] | None = None,
) -> RequestStates:
    """Classifica o período de **um** aluno.

    `catalogue` e `approved` são por disciplina; `eligible`, `requested`, `won`
    e `retained` vêm por turma e são dobrados por `groups`.

    `approved` é o acumulado ao **fim** do período, com as notas já saídas;
    `eligible` é o conjunto do **início** dele, que é contra o que as decisões
    do aluno se leem.
    """

    def fold(names: Iterable[str]) -> set[str]:
        return {groups.get(name, name) if groups else name for name in names}

    retained = fold(retained)
    won = fold(won)
    requested = fold(requested)
    approved_now = retained & approved
    eligible_set = fold(eligible)
    # O que ele já tinha aprovado antes deste período: sai do denominador,
    # porque não é algo que lhe falta.
    previously = approved - approved_now
    return RequestStates(
        not_eligible=len(set(catalogue) - previously - eligible_set),
        not_requested=len(eligible_set - requested),
        refused=len(requested - won),
        excluded=len(won - retained),
        failed=len(retained - approved),
        approved=len(approved_now),
    )
