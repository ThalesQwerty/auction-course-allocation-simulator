"""Ponte FastAPI entre o motor Python e a interface web.

Quatro rotas, sem persistência nenhuma: `/run` resolve um leilão de uma rodada
montado à mão, `/compare` roda o cenário nos braços da Seção 7.3, `/trace`
refaz **uma** execução da comparação e devolve o que cada aluno pediu, e
`/playground` roda uma alocação isolada. O estado vive só no navegador — cada
requisição carrega o cenário inteiro, e a seed torna o resultado reprodutível.

Executar localmente:
    uvicorn leilao.api.main:app --reload --port 8000

ou, mais curto (após `pip install -e ".[dev]"`):
    dev
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from ..auction import AuctionInput, Bid, run_auction
from ..comparison import ARM_BY_KEY, arm_config, run_comparison
from ..config import Discipline, SimulationConfig
from ..entities import Agent, Good, MutualExclusion
from ..grading import beta_shape
from ..playground import PlaygroundDiscipline, PlaygroundStudent, run_playground
from ..simulation import run_simulation
from .schemas import (
    ArmResultOut,
    CompareRequest,
    CompareResponse,
    PlaygroundGradeOut,
    PlaygroundRequest,
    PlaygroundResponse,
    PlaygroundRoundOut,
    PlaygroundRoundStudentOut,
    RunRequest,
    RunResponse,
    RunSummaryOut,
    ScenarioIn,
    TracePeriodOut,
    TraceRequest,
    TraceResponse,
)

app = FastAPI(
    title="Leilão por Créditos — API",
    description="Ponte entre o motor de simulação (Python) e a interface de configuração/execução (TypeScript).",
    version="0.1.0",
)

# O traço de uma execução é a resposta grande da API — uns 10 MB de JSON no
# preset Computação, que comprimidos viram cerca de 1. O limite deixa de fora as
# respostas pequenas, em que o gasto de comprimir não se paga.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Front-end (Vite) roda por padrão em http://localhost:5173 durante o desenvolvimento.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
def run(req: RunRequest) -> RunResponse:
    try:
        auction_input = AuctionInput(
            agents=[Agent(a.id, a.capacity) for a in req.agents],
            goods=[Good(g.id, g.quantity, g.weight) for g in req.goods],
            budgets={a.id: a.budget for a in req.agents},
            bids=[Bid(b.agent_id, b.good_id, b.credits) for b in req.bids],
            exclusions=[MutualExclusion(frozenset(clique)) for clique in req.exclusions if len(clique) >= 2],
            seed=req.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = run_auction(auction_input)
    except Exception as exc:  # noqa: BLE001 — reporta falha do solver/instância inviável
        raise HTTPException(status_code=422, detail=f"falha ao resolver o cenário: {exc}") from exc

    return RunResponse.from_result(result)


def build_config(req: ScenarioIn, *, seed: int = 0) -> SimulationConfig:
    """Converte o cenário recebido no `SimulationConfig` do motor.

    A comparação passa cada seed da amostra, de modo que todos os braços veem
    o mesmo cenário — que é o que a Seção 7.3 exige dela.
    """
    # A interface descreve a aptidão por média e concentração; a Beta pede a
    # forma.
    aptitude_alpha, aptitude_beta = beta_shape(
        mean=req.aptitude_mean, concentration=req.aptitude_concentration
    )
    return SimulationConfig(
        disciplines=[
            Discipline(
                name=d.name,
                seats=d.seats,
                hours=d.hours,
                difficulty=d.difficulty,
                unlocks=tuple(d.unlocks),
                entry=d.entry,
                elective=d.elective,
                stability=d.stability,
                attractiveness=d.attractiveness,
            )
            for d in req.disciplines
        ],
        aptitude_alpha=aptitude_alpha,
        aptitude_beta=aptitude_beta,
        utility_gain=req.utility_gain,
        retake_gain=req.retake_gain,
        utility_stability=req.utility_stability,
        resolver=req.resolver,
        credit_memory=req.credit_memory,
        utility_sigma=req.utility_sigma,
        max_hours=req.max_hours,
        periods=req.periods,
        entry_periods=req.entry_periods,
        max_residence=req.max_residence,
        students_per_period=req.students_per_period,
        rounds=req.rounds,
        min_grade=req.min_grade,
        elective_hours=req.elective_hours,
        base_credits=req.base_credits,
        credit_return=req.credit_return,
        seed=seed,
    )


@app.post("/compare", response_model=CompareResponse)
def compare(req: CompareRequest) -> CompareResponse:
    """Roda o mesmo cenário nos três modelos, N vezes em cada um.

    As seeds vão de 1 a N e são pareadas: a execução i de um braço e a do outro
    partem da mesma população, das mesmas utilidades e das mesmas notas. A
    resposta traz só as métricas de alocação, já reduzidas a um valor por
    execução — nada de crédito e nenhum recorte, porque o que se compara aqui é
    o modelo, não o que acontece dentro de cada um.

    É uma simulação completa por braço e por seed; com um cenário grande a
    requisição leva dezenas de segundos.
    """
    try:
        config = build_config(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = run_comparison(config, runs=req.runs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — reporta falha do solver/instância inviável
        raise HTTPException(
            status_code=422, detail=f"falha ao comparar os mecanismos: {exc}"
        ) from exc

    return CompareResponse(
        runs=result.runs,
        utility_distribution=result.utility_distribution,
        grade_distribution=result.grade_distribution,
        arms=[
            ArmResultOut(
                key=arm.key,
                mechanism=arm.mechanism,
                credit_return=arm.credit_return,
                runs=[RunSummaryOut.model_validate(r) for r in arm.runs],
            )
            for arm in result.arms
        ],
    )


@app.post("/trace", response_model=TraceResponse)
def trace(req: TraceRequest) -> TraceResponse:
    """Refaz uma execução da comparação e devolve o que cada aluno pediu.

    O par `(braço, seed)` endereça uma das execuções que `/compare` resumiu num
    ponto do boxplot, e a configuração passa pelo mesmo `arm_config` que ela
    usou — então o que volta aqui é literalmente a simulação de que aquele
    ponto saiu, e não uma parecida.

    É uma simulação completa por requisição (segundos, no preset Computação), e
    a resposta é a maior da API: vem período a período, aluno a aluno.
    """
    arm = ARM_BY_KEY.get(req.arm)
    if arm is None:
        raise HTTPException(
            status_code=400,
            detail=f"modelo desconhecido: {req.arm!r} — os válidos são {sorted(ARM_BY_KEY)}",
        )

    try:
        config = arm_config(build_config(req), arm=arm, seed=req.seed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = run_simulation(config)
    except Exception as exc:  # noqa: BLE001 — reporta falha do solver/instância inviável
        raise HTTPException(
            status_code=422, detail=f"falha ao refazer a execução: {exc}"
        ) from exc

    return TraceResponse(
        arm=arm.key,
        seed=req.seed,
        periods=[
            TracePeriodOut(period=period.period, disciplines=period.disciplines)
            for period in result.periods
        ],
        students=result.students,
        histories=result.histories,
        disciplines=result.disciplines,
        curriculum_periods=result.curriculum_periods,
    )


@app.post("/playground", response_model=PlaygroundResponse)
def playground(req: PlaygroundRequest) -> PlaygroundResponse:
    aptitude_alpha, aptitude_beta = beta_shape(
        mean=req.aptitude_mean, concentration=req.aptitude_concentration
    )
    try:
        result = run_playground(
            mechanism=req.mechanism,
            rounds=req.rounds,
            seed=req.seed,
            aptitude_alpha=aptitude_alpha,
            aptitude_beta=aptitude_beta,
            disciplines=[
                PlaygroundDiscipline(d.name, d.seats, d.hours) for d in req.disciplines
            ],
            students=[
                PlaygroundStudent(
                    s.id,
                    s.credits,
                    s.cr,
                    s.max_hours,
                    s.utilities,
                    tuple(s.eligible),
                )
                for s in req.students
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"falha no playground: {exc}") from exc

    return PlaygroundResponse(
        rounds=[
            PlaygroundRoundOut(
                number=round_.number,
                prices=round_.prices,
                students=[
                    PlaygroundRoundStudentOut(
                        id=student.id,
                        bids=student.bids,
                        utilities=student.utilities,
                        won=list(student.won),
                        remaining_hours=student.remaining_hours,
                        remaining_credits=student.remaining_credits,
                    )
                    for student in round_.students
                ],
            )
            for round_ in result.rounds
        ],
        grades=[
            PlaygroundGradeOut(
                student_id=grade.student_id,
                discipline=grade.discipline,
                grade=grade.grade,
            )
            for grade in result.grades
        ],
    )


def main() -> None:
    """Entry point do comando `dev` (ver pyproject.toml)."""
    uvicorn.run("leilao.api.main:app", host="127.0.0.1", port=8000, reload=True)
