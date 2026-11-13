"""Ditadura serial: a distribuição da linha de base — Seção 7.3.1.

Os alunos entram em ordem decrescente de prioridade e cada um leva o que
quer, na **própria ordem de preferência**, enquanto houver vaga e carga:

    para a em ordem decrescente de N_a:
        para x na ordem de preferência de a:
            se q_x > 0 e w_x ≤ W_a:  concede, q_x −= 1, W_a −= w_x

`requests` vem já na ordem de preferência de cada aluno, e `priority` é por
**aluno** (N_a da eq. 49 mais a perturbação de desempate), não por par. Essa
separação é o que torna a regra lexicográfica de verdade: o CR decide *quem*
escolhe antes, e a utilidade decide *o que* cada um escolhe. Com uma
ordenação achatada sobre os pares, o ε por par embaralharia a ordem interna
do aluno e ele levaria o que calhasse, não o que preferia.

**A carga horária é verificada aqui, não em casa.** O aluno pede tudo que lhe
é elegível (eq. 50) e a restrição da eq. (4) é resolvida *ex-post* — que é o
que torna comparável esta célula com a de PLI: as duas recebem a mesma
mensagem e só diferem em quem decide.

O ROTEAMENTO
------------

`groups` mapeia cada turma na disciplina dela, e o conjunto `served` é o que
impede o aluno de levar duas turmas do mesmo grupo: a caminhada **pula** o
que ele já atendeu em vez de conceder de novo.

`requests` vem com **uma turma por disciplina** (`equations.best_class`), de
modo que dentro de uma rodada a caminhada não tem grupo repetido a pular e o
roteamento fica como guarda — `serial_dictatorship` não checa clique nenhum
por si. O que ele cobre de fato é o pedido que listasse irmãs.

O conjunto cobre a **rodada**; entre rodadas quem cobre é o filtro por grupo
de `equations.available_goods`.

`seats` e `capacity` não são modificados: a concessão é descontada em cópias.
"""
from __future__ import annotations


def serial_dictatorship(
    *,
    requests: list[tuple[str, str]],
    priority: dict[str, float],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: dict[str, int],
    groups: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    remaining = dict(seats)
    room = dict(capacity)
    wanted: dict[str, list[str]] = {}
    for student_id, name in requests:
        wanted.setdefault(student_id, []).append(name)

    granted: list[tuple[str, str]] = []
    for student_id in sorted(wanted, key=lambda s: (-priority[s], s)):
        served: set[str] = set()
        for name in wanted[student_id]:
            group = groups[name] if groups else name
            if group in served:
                continue
            if remaining.get(name, 0) > 0 and room.get(student_id, 0) >= hours[name]:
                remaining[name] -= 1
                room[student_id] -= hours[name]
                served.add(group)
                granted.append((student_id, name))
    return granted
