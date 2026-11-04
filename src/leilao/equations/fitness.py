"""Aptidão do aluno no algoritmo genético: carga aprovada por período.

    f_a = Σ_{x ∈ H̃_a} w_x / idade_a          [h/período]

    idade_a = (saída_a ou T) − ingresso_a + 1

Mede **vazão**: quanta grade o aluno venceu por período que passou na
universidade. Jubilado e concluinte entram pela mesma conta, com a idade
truncada no período em que saíram.

POR QUE NÃO A SATISFAÇÃO
-------------------------

ψ chegou a ser candidata. O argumento contra ela era que, sem a invariante de
altura, maximizar ψ seria cursar o que se gosta sem nunca avançar — e com a
utilidade redistribuindo o inelegível isso deixou de valer, porque a porteira
carrega o interesse do que destrava. Ficou carga/período mesmo: mede vazão direto, e é a
mais simples de defender num texto.

O JUBILADO ENTRA
-----------------

E tende a pontuar baixo, que é o comportamento desejado: ele acumulou pouca
carga numa idade que continua contando. Excluí-lo selecionaria por
sobreviver, que é viés de sobrevivência posto na própria função objetivo.

O aluno ainda ativo no fim do horizonte também entra. O truncamento é
constante dentro da coorte de ingresso, e some na seleção local.

É UMA TAXA, E ISSO TEM UM BURACO
---------------------------------

Carreira curta com bom começo pontua alto: dois períodos cheios e uma saída
no terceiro dão uma razão melhor que a de quem levou doze períodos regulares.
O que fecha esse buraco não é a fórmula, é a regra de jubilamento — ela exige
reprovação acumulada, e quem vai bem não sai cedo. Vale conferir ao mudar a
regra.

NÃO SE REPORTA RESULTADO NO EIXO DA APTIDÃO
--------------------------------------------

Selecionar por carga/período e anunciar que a carga/período melhorou não diz
nada. A aptidão aparece para atestar que a evolução andou; o resultado se lê
em ψ, Jain, ocupação e no vão entre os mecanismos.

Não está no anteprojeto: o algoritmo genético é posterior a ele.
"""
from __future__ import annotations


def fitness(*, approved_hours: int, periods_enrolled: int) -> float:
    if periods_enrolled <= 0:
        raise ValueError("a idade em períodos tem de ser positiva")
    if approved_hours < 0:
        raise ValueError("a carga aprovada não pode ser negativa")
    return approved_hours / periods_enrolled
