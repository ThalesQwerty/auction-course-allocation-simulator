"""Comparação entre os dois mecanismos (Seção 7.3).

O anteprojeto impõe duas condições metodológicas à comparação, e este módulo
existe para fazer as duas valerem de uma vez:

1. **Mesma inicialização dos dois lados.** "Sempre que os mecanismos forem
   comparados entre si, ambos serão inicializados com a mesma configuração de
   parâmetros iniciais, tais como alunos, cursos, períodos, disciplinas,
   utilidades, notas, entre outros." Como tudo isso é derivado da seed, basta
   rodar o mesmo cenário com a mesma seed nos dois mecanismos — é literalmente
   a mesma população, a mesma matriz de utilidades e a mesma matriz de notas
   encontrando regras de alocação diferentes.
2. **Múltiplas configurações de entrada.** "Serão testadas múltiplas
   configurações de entrada diferentes para cada comparação, e o resultado
   médio das simulações será avaliado." As seeds de 1 a N são essas
   configurações: N populações diferentes, cada uma vista pelos dois
   mecanismos.

Juntas, as duas isolam o nexo causal no mecanismo. Uma execução só não diria
nada — a diferença poderia ser daquela população; e N execuções sem parear as
seeds mediriam a variação entre populações junto da variação entre mecanismos.

**Uma execução vira um número por métrica**, que é o ponto do boxplot. A
redução é a média dos períodos **ponderada pelos alunos ativos**: a simulação
termina numa fase de drenagem, em que a população só diminui, e uma média
simples daria a um período final de vinte alunos o mesmo peso de um período
cheio de trezentos. Ponderar pela população corrige isso sem recortar o
horizonte à mão. Vale também para a ocupação, que é razão sobre as vagas da
universidade e não média de alunos: o peso ali não normaliza a métrica, só diz
quanto aquele período conta na vida da simulação.

Só entram as cinco métricas principais — as que avaliam a *alocação*. Nada de
crédito: orçamento, preço e retorno não existem do lado da linha de base, e
comparar um mecanismo com o vazio não é comparação.
"""
from __future__ import annotations

import dataclasses
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .config import Mechanism, SimulationConfig
from .simulation import SimulationResult, run_simulation

# Teto de execuções por mecanismo. Não é limitação técnica: é que o boxplot
# para de ganhar informação muito antes disso, e cada execução a mais custa uma
# simulação inteira dos dois lados.
MAX_RUNS = 100


@dataclass(frozen=True)
class RunSummary:
    """Uma execução reduzida a um ponto por métrica.

    `periods` é quantos períodos a simulação de fato publicou — pode ser menor
    que |T| se a população se esvaziou antes do horizonte —, e serve para
    conferir que os dois mecanismos viveram o mesmo intervalo.
    """

    seed: int
    periods: int
    efficiency: float  # psi-barra — eq. (53)
    fairness: float  # phi de Jain — eq. (55)
    correlation: float  # lambda — eq. (57)
    occupancy: float  # theta — eq. (54)
    semestralization: float  # sigma-barra


@dataclass(frozen=True)
class ComparisonResult:
    """As N execuções de cada mecanismo, pareadas pela seed.

    As duas listas têm o mesmo tamanho e a mesma ordem de seeds: o i-ésimo
    elemento de uma e o da outra são a *mesma* população sob regras diferentes.
    Quem lê pode tanto tratar cada lista como uma amostra (é o que o boxplot
    faz) quanto comparar par a par.
    """

    runs: int
    credits: list[RunSummary]
    ranking: list[RunSummary]


def summarize(result: SimulationResult, *, seed: int) -> RunSummary:
    """Reduz uma simulação inteira a um ponto por métrica — a média dos
    períodos ponderada pelos alunos ativos.

    Períodos sem ninguém ativo não entram: não têm métrica, e um zero ali seria
    um período em que todo mundo ficou insatisfeito, que é coisa diferente.
    """
    weights: list[int] = []
    snapshots = []
    for period in result.periods:
        snapshot = period.aggregate.overall
        if snapshot.metrics is None or snapshot.active <= 0:
            continue
        weights.append(snapshot.active)
        snapshots.append(snapshot.metrics)

    total = sum(weights)
    if not total:
        return RunSummary(seed, len(result.periods), 0.0, 0.0, 0.0, 0.0, 0.0)

    def mean(of) -> float:
        return sum(of(m) * w for m, w in zip(snapshots, weights)) / total

    return RunSummary(
        seed=seed,
        periods=len(result.periods),
        efficiency=mean(lambda m: m.efficiency),
        fairness=mean(lambda m: m.fairness),
        correlation=mean(lambda m: m.correlation),
        occupancy=mean(lambda m: m.occupancy),
        semestralization=mean(lambda m: m.semestralization),
    )


def _run_one(config: SimulationConfig, mechanism: Mechanism, seed: int) -> RunSummary:
    return summarize(
        run_simulation(dataclasses.replace(config, mechanism=mechanism, seed=seed)),
        seed=seed,
    )


def run_comparison(
    config: SimulationConfig, *, runs: int, workers: int = 4
) -> ComparisonResult:
    """Roda `runs` simulações de cada mecanismo, com as seeds de 1 a `runs`.

    A seed do cenário recebido é ignorada de propósito: numa comparação ela
    deixa de ser um parâmetro e passa a ser o eixo da amostra. O resto do
    cenário — disciplinas, perfis, horizonte, rodadas — vale igual nos dois
    lados, que é o que torna a diferença atribuível ao mecanismo.

    As execuções saem em paralelo por `ThreadPoolExecutor`, e não por processos:
    o tempo do leilão está quase todo dentro do CBC, que roda como processo
    externo e devolve a GIL enquanto se espera por ele. Threads também evitam
    reimportar numpy e pulp em cada worker, que custaria mais do que a
    simulação. A ordem das seeds é preservada pelo `map`, de modo que o i-ésimo
    elemento das duas listas é a mesma população.
    """
    if not 1 <= runs <= MAX_RUNS:
        raise ValueError(f"o número de execuções deve estar entre 1 e {MAX_RUNS}")
    seeds = list(range(1, runs + 1))

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = [
            pool.submit(_run_one, config, mechanism, seed)
            for mechanism in ("credits", "ranking")
            for seed in seeds
        ]
    done = [job.result() for job in jobs]
    return ComparisonResult(runs=runs, credits=done[:runs], ranking=done[runs:])
