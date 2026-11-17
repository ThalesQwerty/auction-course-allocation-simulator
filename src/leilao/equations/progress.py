"""Progresso do aluno na grade.

    progresso_a^(t) = H̃_a^(t) / S

`H̃_a` é a carga **aprovada** do histórico até ali e `S` é a carga mínima para
concluir — a soma de todas as obrigatórias mais a exigência optativa X
(`SimulationConfig.hours_to_graduate`). Vai de 0, no ingresso, a 1, que é
exatamente a condição de conclusão medida em horas.

**Não é a semestralização.** Aquela divide pelo que o aluno *poderia* ter
aprovado desde que entrou (`W_a × idade`) e mede **ritmo**: quem acabou de
entrar e foi bem marca alto. Esta divide pelo curso inteiro e mede **quanto
falta**: quem acabou de entrar marca baixo por definição, por mais que tenha
ido bem. As duas sobem com aprovação e respondem a perguntas diferentes.

**Não é a mesma coisa que a conclusão (eq. 40).** Chegar a 1 aqui é condição
necessária e não suficiente: a eq. (40) exige aprovar **cada** obrigatória e
somar X em optativas, e a carga total só coincide com isso quando o aluno não
trocou obrigatória por optativa pelo caminho. Em cenário sem optativa as duas
coincidem; com optativa, um aluno pode passar de 1 em horas e não ter
concluído. O teto, portanto, **não é 1** — a média do recorte fica abaixo
disso na prática, porque quem conclui sai da simulação.

**A média sobre o recorte tem viés de sobrevivência**, e é a mesma ressalva do
tempo de formatura: quem fecha a grade deixa de ser medido, de modo que a
média dos que ficam para de subir (e pode cair) na fase de drenagem. Lê-se com
a fração de concluintes ao lado, não sozinha.

Não está no anteprojeto.
"""
from __future__ import annotations


def progress(*, approved_hours: int, hours_to_graduate: int) -> float:
    if hours_to_graduate <= 0:
        return 0.0
    return approved_hours / hours_to_graduate
