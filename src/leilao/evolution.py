"""O algoritmo genético: coortes evoluindo independentes sobre o mesmo cenário.

A camada estocástica da evolução — torneio, elitismo e mutação —, ao lado de
`behavior.draw_interest` e `grading.draw_base_quantiles`: as contas puras ficam em
`equations.genome_grid` e `equations.genome_drift`.

VOCABULÁRIO
-----------

**Coorte** é a turma de ingresso: os alunos que entram no mesmo período.
**Observação** é uma execução da simulação. **Geração** é exclusivamente do
algoritmo genético — uma rodada de seleção e mutação. Antes os dois últimos
sentidos dividiam a palavra "geração" em níveis diferentes, e a aritmética
ficava ilegível.

O desenho se escreve de uma vez: **N observações, M gerações, e as coortes
evoluem independentes entre si.**

AS COORTES SÃO INDEPENDENTES
-----------------------------

A seleção acontece **dentro** de cada coorte, e por um motivo que não é
óbvio: quem entra tarde tem a carreira truncada pelo horizonte, então a
aptidão bruta é enviesada pelo período de ingresso. Como o truncamento é
constante dentro da coorte, a seleção local o cancela.

Isso dá oito linhagens evolutivas paralelas, e convergirem para a mesma
região é evidência forte. Mas elas **não enfrentam o mesmo ambiente** — a
primeira coorte entra numa universidade vazia, a última numa cheia e já
drenada. Divergência entre linhagens confunde "a paisagem tem vários picos"
com "o período de ingresso é outro", e por isso cada linhagem se compara
consigo mesma ao longo das gerações.

A RÉGUA É A MÉDIA DA COORTE
----------------------------

Com a grade ocupando a coorte inteira não sobra lugar para um genótipo de
linha de base servir de referência. A aptidão é medida **relativa à média da
própria coorte** — o que, além de resolver, é o que se queria: dependência de
frequência explícita, e o resultado se escreve como *estratégia estável*, não
como ótimo.

O CONTROLE NEGATIVO
-------------------

Com `neutral=True`, os alunos rodam todos na linha de base: o genoma é
carregado, selecionado e mutado, mas **não é expresso**. As diferenças de
aptidão passam a ser puro ruído, e o que a população andar é deriva.

É o modelo nulo de neutralidade — seleção só se demonstra como desvio em
relação a um nulo neutro —, e serve para duas coisas: separar o que a seleção
produziu do que o ambiente produziu sozinho, e calibrar o ε do critério de
parada. **Rode-o antes do experimento real**: se a população varrer a faixa
inteira dos genes sob o nulo, nenhum resultado do real seria interpretável, e
você descobre isso gastando uma rodada em vez de todas.

A DERIVA NÃO É PEQUENA
-----------------------

Torneio sobre aptidão ruidosa escolhe quase ao acaso, o que é deriva de
Wright-Fisher: a média de uma população de P indivíduos se move por geração
com desvio `σ_população/√P`. Com 180 alunos e `β_u` espalhado em [−1, 3],
isso dá ~0,10 por geração, e `0,10·√50 ≈ 0,7` em cinquenta gerações — um
sexto da faixa do gene, sem seleção nenhuma. Nulo barulhento significa
experimento com pouca resolução, e o conserto é aumentar `observations` ou
diminuir `step`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import numpy as np

from .config import SimulationConfig
from .equations import Behavior, fitness, genome_drift, genome_grid
from .population import generate_students
from .simulation import run_simulation

__all__ = [
    "GENES",
    "EvolutionConfig",
    "EvolutionResult",
    "GenerationReport",
    "GenomeLevels",
    "run_evolution",
]

# A ordem é carga: define o eixo do vetor de médias e o da escala.
GENES = ("beta_u", "beta_v", "beta_n", "alpha_u")


@dataclass(frozen=True)
class GenomeLevels:
    """Os valores fixados da 1ª geração, um conjunto por gene.

    O produto deles é o tamanho da população inicial, e precisa bater com
    `students_per_period`. Os padrões dão 5 · 4 · 3 · 3 = 180.
    """

    beta_u: tuple[float, ...] = (-1.0, 0.0, 1.0, 2.0, 3.0)
    beta_v: tuple[float, ...] = (-1.0, 0.0, 1.0)
    beta_n: tuple[float, ...] = (-1.0, 0.0, 1.0)
    # Múltiplos arredondados da participação média com ~9 elegíveis: nada,
    # metade da média, a média, o dobro. Ver `equations.genome_grid` para por
    # que não ⅓ e ⅔.
    alpha_u: tuple[float, ...] = (0.0, 0.05, 0.1, 0.2)

    def grid(self) -> tuple[Behavior, ...]:
        return genome_grid(
            beta_u=self.beta_u,
            beta_v=self.beta_v,
            beta_n=self.beta_n,
            alpha_u=self.alpha_u,
        )


@dataclass(frozen=True)
class EvolutionConfig:
    levels: GenomeLevels = GenomeLevels()
    # N — execuções da simulação por geração. Com desvio 1,36, o erro padrão
    # da aptidão de um genótipo é 1,36/√N: 0,61 com 5, 0,30 com 20. O efeito
    # extremo-a-extremo é 0,7, então com N baixo o torneio vira quase sorteio.
    observations: int = 5
    min_generations: int = 5
    max_generations: int = 30
    # A janela do critério de parada, em gerações.
    window: int = 5
    # ε: o limiar de deriva. `None` desliga o gatilho e a rodada vai até
    # `max_generations`. Sob `neutral` ele é ignorado, porque é o controle
    # negativo quem *produz* o ε — ver `run_evolution`.
    epsilon: float | None = None
    # Torneio pequeno de propósito: seleção agressiva sobre aptidão ruidosa
    # amplifica deriva.
    tournament: int = 2
    elites: int = 10
    # c — o passo da mutação como fração do espaçamento de cada gene. Um botão
    # só gerando quatro passos corretos: um σ único seria imperceptível num
    # expoente e um salto para o outro lado do espaço em `alpha_u`.
    step: float = 0.3
    # Controle negativo: carrega o genoma sem expressá-lo.
    neutral: bool = False


@dataclass(frozen=True)
class CohortGeneration:
    entry_period: int
    # A média de cada gene, na ordem de `GENES`.
    mean: tuple[float, ...]
    best_fitness: float
    mean_fitness: float


@dataclass(frozen=True)
class GenerationReport:
    generation: int
    cohorts: tuple[CohortGeneration, ...] = ()
    # A deriva agregada das coortes nesta janela. `inf` enquanto a janela não
    # fecha. Agregar antes de testar, nunca exigir "todas as coortes abaixo de
    # ε": com 75% de chance por coorte, oito juntas dão 10%, e cinco gerações
    # seguidas, 10⁻⁵ — o gatilho nunca agiria.
    drift: float = float("inf")


@dataclass(frozen=True)
class EvolutionResult:
    generations: list[GenerationReport] = field(default_factory=list)
    # "convergiu", "teto" ou "sem gatilho".
    stopped_by: str = "teto"
    neutral: bool = False
    # O espalhamento de cada gene na 1ª geração — a escala fixa da deriva, e o
    # que torna o ε de uma rodada comparável ao de outra.
    scales: tuple[float, ...] = ()


def _spacing(levels: tuple[float, ...]) -> float:
    """O espaçamento entre níveis consecutivos, ou 1 se houver um nível só."""
    if len(levels) < 2:
        return 1.0
    ordered = sorted(levels)
    return (ordered[-1] - ordered[0]) / (len(ordered) - 1)


def _genes(behavior: Behavior) -> tuple[float, ...]:
    return tuple(getattr(behavior, gene) for gene in GENES)


def _mean_genome(population: list[Behavior]) -> tuple[float, ...]:
    if not population:
        return tuple(0.0 for _ in GENES)
    columns = zip(*(_genes(b) for b in population))
    return tuple(sum(values) / len(population) for values in columns)


def _fitness_by_student(result, *, horizon: int) -> dict[str, float]:
    """f_a de cada aluno — `equations.fitness` sobre o resumo da execução.

    Jubilado entra, e tende a pontuar baixo: pouca carga numa idade que
    continua contando. Quem nunca chegou a cursar fica de fora, porque idade
    não positiva não tem razão.
    """
    scores: dict[str, float] = {}
    for student in result.students:
        left = student.graduated_at or student.dismissed_at or horizon
        age = left - student.entry_period + 1
        if age <= 0:
            continue
        scores[student.id] = fitness(
            approved_hours=student.approved_hours, periods_enrolled=age
        )
    return scores


def _tournament(
    population: list[Behavior],
    scores: list[float],
    *,
    size: int,
    rng: np.random.Generator,
) -> Behavior:
    picked = rng.integers(0, len(population), size=max(2, size))
    best = max(picked, key=lambda index: scores[index])
    return population[best]


def _mutate(
    behavior: Behavior, *, sigma: tuple[float, ...], rng: np.random.Generator
) -> Behavior:
    """Passo gaussiano aditivo nos quatro genes, sempre.

    Não há fronteira a tratar: os três expoentes aceitam qualquer real, porque
    potência de base positiva é sempre positiva. `alpha_u` é a única restrição
    do genoma, e um corte em zero basta — abaixo dele a reserva não cortaria
    nada, de modo que 0 e −0,3 seriam o mesmo comportamento.
    """
    values = [
        gene + float(rng.normal(0.0, step))
        for gene, step in zip(_genes(behavior), sigma)
    ]
    return Behavior(
        beta_u=values[0],
        beta_v=values[1],
        beta_n=values[2],
        alpha_u=max(0.0, values[3]),
    )


def run_evolution(
    config: SimulationConfig, evolution: EvolutionConfig = EvolutionConfig()
) -> EvolutionResult:
    """M gerações de N observações, com as coortes evoluindo independentes.

    São **N × M** execuções da simulação ao todo: cada observação é uma
    simulação inteira, com todas as coortes dentro dela, e cada coorte extrai
    da mesma observação a aptidão da sua própria linhagem.

    As seeds das observações são 1..N, como na comparação: a mesma população e
    as mesmas notas em todas as gerações, de modo que o que muda entre elas é
    o genoma e nada mais.
    """
    grid = evolution.levels.grid()
    # Fluxo próprio: o sorteio da evolução não pode deslocar o do cenário, ou
    # ligar o GA mudaria as utilidades de todo mundo.
    rng = np.random.default_rng(config.seed).spawn(1)[0]

    students = generate_students(config, np.random.default_rng(config.seed))
    entries = sorted({s.entry_period for s in students})
    seats = {entry: sum(1 for s in students if s.entry_period == entry) for entry in entries}
    # De que coorte e em que posição dentro dela está cada aluno — é por aqui
    # que a aptidão de uma execução volta para o genótipo que a produziu.
    position: dict[str, tuple[int, int]] = {}
    seen = {entry: 0 for entry in entries}
    for student in students:
        position[student.id] = (student.entry_period, seen[student.entry_period])
        seen[student.entry_period] += 1

    population = {entry: [grid[i % len(grid)] for i in range(seats[entry])] for entry in entries}
    sigma = tuple(
        evolution.step * _spacing(getattr(evolution.levels, gene)) for gene in GENES
    )
    scales = tuple(
        float(np.std([getattr(b, gene) for b in grid])) for gene in GENES
    )

    reports: list[GenerationReport] = []
    history: dict[int, list[tuple[float, ...]]] = {entry: [] for entry in entries}
    # O controle negativo não para pela deriva: é dele que o ε sai, e um nulo
    # interrompido mediria a deriva de uma janela escolhida por ela mesma —
    # sempre a mais parada que apareceu. Ele vai ao teto, e um ε que venha
    # junto de `neutral` é ignorado em vez de recusado, para que ligar e
    # desligar a caixa não exija mexer em mais nada.
    epsilon = None if evolution.neutral else evolution.epsilon
    stopped_by = "teto"

    for generation in range(1, evolution.max_generations + 1):
        genomes = () if evolution.neutral else tuple(
            tuple(population[entry]) for entry in entries
        )
        totals: dict[str, float] = {}
        for seed in range(1, evolution.observations + 1):
            result = run_simulation(
                dataclasses.replace(config, seed=seed, genomes=genomes)
            )
            for student_id, score in _fitness_by_student(
                result, horizon=config.periods
            ).items():
                totals[student_id] = totals.get(student_id, 0.0) + score

        cohorts: list[CohortGeneration] = []
        for entry in entries:
            size = seats[entry]
            scores = [0.0] * size
            for student_id, total in totals.items():
                where = position.get(student_id)
                if where is not None and where[0] == entry:
                    scores[where[1]] = total / evolution.observations
            average = sum(scores) / size if size else 0.0
            # Aptidão relativa à média da própria coorte: dependência de
            # frequência explícita, e é o que torna o resultado uma estratégia
            # estável em vez de um ótimo.
            relative = [score - average for score in scores]

            mean = _mean_genome(population[entry])
            history[entry].append(mean)
            cohorts.append(
                CohortGeneration(
                    entry_period=entry,
                    mean=mean,
                    best_fitness=max(scores) if scores else 0.0,
                    mean_fitness=average,
                )
            )

            ranked = sorted(range(size), key=lambda i: relative[i], reverse=True)
            elite = [population[entry][i] for i in ranked[: evolution.elites]]
            children = [
                _mutate(
                    _tournament(
                        population[entry],
                        relative,
                        size=evolution.tournament,
                        rng=rng,
                    ),
                    sigma=sigma,
                    rng=rng,
                )
                for _ in range(size - len(elite))
            ]
            population[entry] = elite + children

        drift = float("inf")
        if all(len(history[entry]) >= evolution.window for entry in entries):
            per_cohort = [
                genome_drift(window=history[entry][-evolution.window :], scales=scales)
                for entry in entries
            ]
            drift = sum(per_cohort) / len(per_cohort)

        reports.append(
            GenerationReport(
                generation=generation, cohorts=tuple(cohorts), drift=drift
            )
        )

        if (
            epsilon is not None
            and generation >= evolution.min_generations
            and drift <= epsilon
        ):
            stopped_by = "convergiu"
            break
    else:
        stopped_by = "teto" if epsilon is not None else "sem gatilho"

    return EvolutionResult(
        generations=reports,
        stopped_by=stopped_by,
        neutral=evolution.neutral,
        scales=scales,
    )
