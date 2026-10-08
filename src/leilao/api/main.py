"""Ponte FastAPI entre o motor Python (leilao.auction) e a interface web.

Sem persistência: cada requisição a /run carrega o cenário inteiro (agentes,
bens, lances, exclusões) e recebe de volta o resultado do leilão. O estado
do cenário vive só no navegador (React), não no servidor.

Executar localmente:
    uvicorn leilao.api.main:app --reload --port 8000

ou, mais curto (após `pip install -e ".[dev]"`):
    dev
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..auction import AuctionInput, Bid, run_auction
from ..comparison import run_comparison
from ..config import (
    DEFAULT_AFFINITY,
    DEFAULT_APTITUDE,
    AffinityProfile,
    AptitudeProfile,
    Discipline,
    SimulationConfig,
)
from ..entities import Agent, Good, MutualExclusion
from ..simulation import run_simulation
from .schemas import (
    CompareRequest,
    CompareResponse,
    PeriodReportOut,
    RunRequest,
    RunResponse,
    RunSummaryOut,
    ScenarioIn,
    SimulateRequest,
    SimulateResponse,
    StudentHistoryOut,
    StudentSummaryOut,
)

app = FastAPI(
    title="Leilão por Créditos — API",
    description="Ponte entre o motor de simulação (Python) e a interface de configuração/execução (TypeScript).",
    version="0.1.0",
)

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

    Compartilhada pelos dois modos: a execução única passa a seed do formulário
    e a comparação passa cada seed da amostra. É o mesmo cenário dos dois lados,
    que é o que a Seção 7.3 exige da comparação.
    """
    # Lista de perfis vazia cai no perfil neutro do eixo — o mesmo default do
    # motor, repetido aqui porque uma lista vazia *apagaria* esse default em vez
    # de pedi-lo, e requisições montadas antes dos perfis existirem mandam [].
    aptitude = [
        AptitudeProfile(p.name, p.mean, p.stddev, p.learning_gain, p.share)
        for p in req.aptitude_profiles
    ] or [DEFAULT_APTITUDE]
    affinity = [
        AffinityProfile(p.name, p.kind, p.intensity, p.max_hours, p.share)
        for p in req.affinity_profiles
    ] or [DEFAULT_AFFINITY]
    return SimulationConfig(
        disciplines=[
            Discipline(d.name, d.seats, d.hours, tuple(d.prerequisites))
            for d in req.disciplines
        ],
        aptitude_profiles=aptitude,
        affinity_profiles=affinity,
        periods=req.periods,
        entry_periods=req.entry_periods,
        students_per_period=req.students_per_period,
        rounds=req.rounds,
        min_grade=req.min_grade,
        base_credits=req.base_credits,
        credit_return=req.credit_return,
        seed=seed,
    )


@app.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest) -> SimulateResponse:
    """Roda uma simulação multi-período completa a partir da configuração."""
    try:
        config = build_config(req, seed=req.seed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = run_simulation(config)
    except Exception as exc:  # noqa: BLE001 — reporta falha do solver/instância inviável
        raise HTTPException(status_code=422, detail=f"falha ao simular o cenário: {exc}") from exc

    # `histories` é montado só quando pedido: converter 1500 históricos custa
    # tempo e memória à toa quando quem chamou só quer as séries agregadas.
    return SimulateResponse(
        periods=[PeriodReportOut.model_validate(p) for p in result.periods],
        students=[StudentSummaryOut.model_validate(s) for s in result.students],
        histories=(
            [StudentHistoryOut.model_validate(h) for h in result.histories]
            if req.include_histories
            else []
        ),
        disciplines=result.disciplines,
        curriculum_periods=result.curriculum_periods,
        aptitude_profiles=result.aptitude_profiles,
        affinity_profiles=result.affinity_profiles,
    )


@app.post("/compare", response_model=CompareResponse)
def compare(req: CompareRequest) -> CompareResponse:
    """Roda o mesmo cenário nos dois mecanismos, N vezes de cada lado.

    As seeds vão de 1 a N e são pareadas: a execução i de um mecanismo e a do
    outro partem da mesma população, das mesmas utilidades e das mesmas notas.
    A resposta traz só as cinco métricas principais, já reduzidas a um valor por
    execução — nada de crédito e nenhum recorte, porque o que se compara aqui é
    o mecanismo, não o que acontece dentro de cada um.

    São 2N simulações completas; com um cenário grande a requisição leva
    dezenas de segundos.
    """
    try:
        config = build_config(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = run_comparison(config, runs=req.runs)
    except Exception as exc:  # noqa: BLE001 — reporta falha do solver/instância inviável
        raise HTTPException(
            status_code=422, detail=f"falha ao comparar os mecanismos: {exc}"
        ) from exc

    return CompareResponse(
        runs=result.runs,
        credits=[RunSummaryOut.model_validate(r) for r in result.credits],
        ranking=[RunSummaryOut.model_validate(r) for r in result.ranking],
    )


def main() -> None:
    """Entry point do comando `dev` (ver pyproject.toml)."""
    uvicorn.run("leilao.api.main:app", host="127.0.0.1", port=8000, reload=True)
