"""Aplicação FastAPI: ponte entre o motor Python e a interface TypeScript.

Executar localmente:
    uvicorn leilao.api.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import scenarios, simulations

app = FastAPI(
    title="Leilão por Créditos — API",
    description=(
        "Ponte entre o motor de simulação (Python) e a interface de "
        "configuração/execução (TypeScript) do mecanismo de leilão por "
        "créditos aplicado à matrícula universitária."
    ),
    version="0.1.0",
)

# Front-end (Vite) roda por padrão em http://localhost:5173 durante o desenvolvimento.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios.router)
app.include_router(simulations.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
