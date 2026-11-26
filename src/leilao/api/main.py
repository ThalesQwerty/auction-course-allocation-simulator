"""Ponte FastAPI entre o motor Python e a interface web."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from ..auction import AuctionInput, Bid, run_auction
from ..comparison import ARM_BY_KEY, arm_config
from ..entities import Agent, Good, MutualExclusion
from ..playground import PlaygroundClass, PlaygroundStudent, run_playground
from ..simulation import run_simulation
from . import comparisons
from .service import build_config, compare_scenario
from .storage import delete_result, list_results, read_result, save_result
from .schemas import (
    CompareRequest,
    CompareResponse,
    PlaygroundClosingOut,
    PlaygroundGradeOut,
    PlaygroundRequest,
    PlaygroundResponse,
    PlaygroundRoundOut,
    PlaygroundRoundStudentOut,
    RunRequest,
    RunResponse,
    SavedResultOut,
    TracePeriodOut,
    TraceRequest,
    TraceResponse,
)

app = FastAPI(
    title="Leilão por Créditos — API",
    description="Ponte entre o motor de simulação (Python) e a interface de configuração/simulação (TypeScript).",
    version="0.1.0",
)

POLLED = re.compile(r"^/comparacoes/[^/]+$")


class QuietPolling(logging.Filter):
    """Tira do access log a consulta de acompanhamento.

    A tela a repete a cada segundo enquanto uma comparação roda, e uma linha
    por segundo afogaria no terminal o progresso que o motor imprime. As outras
    requisições continuam aparecendo, inclusive as que falham.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 3:
            return True
        return not (args[1] == "GET" and POLLED.match(str(args[2])))


logging.getLogger("uvicorn.access").addFilter(QuietPolling())

app.add_middleware(GZipMiddleware, minimum_size=1024)

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
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"falha ao resolver o cenário: {exc}") from exc

    return RunResponse.from_result(result)


@app.post("/compare", response_model=CompareResponse)
def compare(req: CompareRequest) -> CompareResponse:
    """Roda o mesmo cenário nos três modelos, N vezes em cada um."""
    try:
        response = compare_scenario(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"falha ao comparar os mecanismos: {exc}"
        ) from exc

    saved = save_result(kind="comparison", config=req, result=response)
    response.saved_to = saved
    response.saved_as = Path(saved).stem if saved else None
    return response


@app.get("/results", response_model=list[SavedResultOut])
def results() -> list[SavedResultOut]:
    """O que há gravado em disco, do mais recente para o mais antigo."""
    return [SavedResultOut(**row) for row in list_results()]


@app.get("/results/{name}")
def result(name: str) -> dict:
    """Uma execução gravada, inteira."""
    try:
        payload = read_result(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail=f"não há resultado {name!r}")
    return payload


@app.delete("/results/{name}", status_code=204)
def discard(name: str) -> Response:
    """Apaga uma execução gravada."""
    try:
        existed = delete_result(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not existed:
        raise HTTPException(status_code=404, detail=f"não há resultado {name!r}")
    return Response(status_code=204)


@app.get("/comparacoes")
def comparison_list() -> list[dict]:
    """Todas as comparações, da mais recente para a mais antiga."""
    return comparisons.listing()


@app.post("/comparacoes", status_code=201)
def comparison_create(req: CompareRequest, rotulo: str | None = None) -> dict:
    """Cria a comparação e a fila de simulações. **Não roda nada.**"""
    try:
        return comparisons.create(req, label=rotulo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/comparacoes/{name}")
def comparison_state(name: str) -> dict:
    """Cabeçalho, estado de cada simulação e progresso. Serve para acompanhar."""
    return _bank(comparisons.read_state, name)


@app.get("/comparacoes/{name}/resultado")
def comparison_result(name: str) -> dict:
    """O cenário e o cabeçalho. As visualizações têm rota própria."""
    return _bank(comparisons.read_result, name)


@app.get("/comparacoes/{name}/series")
def comparison_series(
    name: str, eixo: str = "overall", cortes: str = ""
) -> dict:
    """A série por período, recortada em faixas e reduzida entre as seeds.

    O SQL agrupa e tira a média sobre os milhões de linhas de `aluno_periodo`;
    o Python só dobra as seeds em mediana e interquartil, porque o SQLite não
    tem `PERCENTILE` e ali já são poucas linhas.
    """
    return _bank(comparisons.read_series, name, axis=eixo, cuts=cortes)


@app.get("/comparacoes/{name}/curva")
def comparison_curve(name: str, eixo: str, pontos: int = 40) -> dict:
    """A métrica sobre CR final ou utilidade de reserva, em faixas de quantil."""
    return _bank(comparisons.read_curve, name, axis=eixo, bins=pontos)


@app.get("/comparacoes/{name}/caixas")
def comparison_boxes(name: str, base: str = "ranking_greedy") -> dict:
    """Uma caixa por (braço, métrica) sobre as seeds: o eixo X colapsado."""
    return _bank(comparisons.read_boxes, name, baseline=base)


@app.get("/comparacoes/{name}/traco", response_model=TraceResponse)
def comparison_trace(name: str, braco: str, seed: int = 1) -> dict:
    """Uma simulação inteira, aluno a aluno, direto do banco."""
    return _bank(comparisons.read_trace, name, arm=braco, seed=seed)


@app.get("/comparacoes/{name}/alunos/{simulation_id}/{student}")
def comparison_student(name: str, simulation_id: int, student: str) -> dict:
    """Tudo que um aluno fez: período a período, turma a turma."""
    return _bank(comparisons.read_student, name, simulation_id, student)


@app.post("/comparacoes/{name}/rodar", status_code=202)
def comparison_run(
    name: str, tasks: BackgroundTasks, workers: int = 1
) -> dict:
    """Roda o que falta, em segundo plano. Serve de começo e de retomada."""
    state = _bank(comparisons.read_state, name)
    tasks.add_task(comparisons.run, name, workers=workers)
    return state


@app.post("/comparacoes/{name}/pausar")
def comparison_pause(name: str) -> dict:
    """Pede a pausa. O laço para na próxima fronteira, não na hora."""
    return _bank(comparisons.pause, name)


@app.delete("/comparacoes/{name}", status_code=204)
def comparison_delete(name: str) -> Response:
    """Apaga a comparação e, em cascata, as oito tabelas de detalhe."""
    _bank(comparisons.delete, name)
    return Response(status_code=204)


def _bank(action, *args, **kwargs):
    """Traduz o que as funções de banco levantam para o que o HTTP diz."""
    try:
        return action(*args, **kwargs)
    except comparisons.Running as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except comparisons.Missing as exc:
        raise HTTPException(
            status_code=404, detail=f"não há comparação {exc}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="não há banco de comparações") from exc


@app.post("/trace", response_model=TraceResponse)
def trace(req: TraceRequest) -> TraceResponse:
    """Refaz uma simulação da comparação e devolve o que cada aluno pediu."""
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
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"falha ao refazer a simulação: {exc}"
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
        classes=result.classes,
        curriculum_periods=result.curriculum_periods,
    )


@app.post("/playground", response_model=PlaygroundResponse)
def playground(req: PlaygroundRequest) -> PlaygroundResponse:
    try:
        result = run_playground(
            mechanism=req.mechanism,
            rounds=req.rounds,
            seed=req.seed,
            mode_grade=req.mode_grade,
            zero_rate=req.zero_rate,
            max_rate=req.max_rate,
            classes=[
                PlaygroundClass(c.name, c.seats, c.hours, c.discipline)
                for c in req.classes
            ],
            students=[
                PlaygroundStudent(
                    s.id,
                    s.credits,
                    s.cr,
                    s.max_hours,
                    s.utilities,
                    tuple(s.eligible),
                    availability=s.availability,
                    selectivity=s.selectivity,
                )
                for s in req.students
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
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
        closing=[
            PlaygroundClosingOut(
                student_id=row.student_id,
                load=row.load,
                retained=list(row.retained),
                excluded=list(row.excluded),
            )
            for row in result.closing
        ],
        grades=[
            PlaygroundGradeOut(
                student_id=grade.student_id,
                name=grade.name,
                grade=grade.grade,
            )
            for grade in result.grades
        ],
    )


def main() -> None:
    """Entry point do comando `dev` (ver pyproject.toml)."""
    uvicorn.run("leilao.api.main:app", host="127.0.0.1", port=8000, reload=True)
