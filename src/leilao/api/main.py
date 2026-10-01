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
from ..config import Course, Discipline, SimulationConfig
from ..entities import Agent, Good, MutualExclusion
from ..simulation import run_simulation
from .schemas import (
    PeriodReportOut,
    RunRequest,
    RunResponse,
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


@app.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest) -> SimulateResponse:
    """Roda uma simulação multi-período completa a partir da configuração."""
    try:
        config = SimulationConfig(
            disciplines=[Discipline(d.name, d.seats, d.hours) for d in req.disciplines],
            courses=[
                Course(
                    name=c.name,
                    students_per_generation=c.students_per_generation,
                    hours_to_graduate=c.hours_to_graduate,
                    required=tuple(c.required),
                    electives=tuple(c.electives),
                )
                for c in req.courses
            ],
            periods=req.periods,
            entry_periods=req.entry_periods,
            max_residence=req.max_residence,
            rounds=req.rounds,
            min_grade=req.min_grade,
            base_credits=req.base_credits,
            max_hours=req.max_hours,
            learning_gain=req.learning_gain,
            credit_return=req.credit_return,
            seed=req.seed,
        )
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
        courses=result.courses,
        disciplines=result.disciplines,
    )


def main() -> None:
    """Entry point do comando `dev` (ver pyproject.toml)."""
    uvicorn.run("leilao.api.main:app", host="127.0.0.1", port=8000, reload=True)
