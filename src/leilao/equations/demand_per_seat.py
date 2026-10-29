"""Pressão sobre a oferta: candidatos por vaga, disciplina a disciplina.

    pressão_a = (1/|S|) · Σ_{x ∈ S} (quantos querem x) / q_x

A razão candidato/vaga do vestibular, calculada por disciplina e promediada
sobre um conjunto `S`. É a forma comum de duas métricas, que só se distinguem
por quem entra em "quantos querem" e por quais disciplinas formam `S`:

    escassez      S = elegíveis (eq. 42)      quantos são elegíveis a x
    concorrência  S = em que deu lance        quantos deram lance em x

A primeira é demanda **potencial** e quase não depende do mecanismo; a
segunda é demanda **efetiva**. Como têm a mesma unidade, leem-se juntas: a
razão concorrência ÷ escassez é a fração da demanda potencial que virou
pedido, e fica abaixo de 1 porque só se pede o que é elegível.

**Contar quem quer** — e não somar as vagas ao alcance — é o que faz as duas
enxergarem sobreposição: dois alunos diante dos mesmos 60 lugares disputam o
dobro de dois alunos diante de 60 lugares cada um, e uma medida do tamanho da
oferta daria o mesmo nos dois casos.

Por isso o recorte agrega por **média**, nunca por soma: a contagem de quem
quer já traz a população dentro do valor de cada aluno, e somar sobre os
alunos a contaria duas vezes. Não há aditividade — um recorte não é parcela do
global — e, em troca, recortes de tamanhos diferentes se comparam direto.

Disciplinas sem vaga ficam de fora de `S` pelo chamador: não são oferta, e a
razão seria divisão por zero. Conjunto vazio dá 0. Nenhuma das duas consta no
anteprojeto.
"""
from __future__ import annotations

from collections.abc import Sequence

from ._mean import mean


def demand_per_seat(*, demands: Sequence[float]) -> float:
    return mean(demands)
