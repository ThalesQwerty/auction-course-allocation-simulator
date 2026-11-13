"""O que as rotas fazem, sem HTTP.

Existe porque a comparação tem **duas portas**: a rota `/compare`, que o
navegador chama, e o terminal (`leilao.cli`), para quando o cenário é grande
demais para caber numa requisição. As duas têm de produzir exatamente o mesmo
arquivo — mesmo cenário de entrada, mesmo resultado de saída —, e a única
forma de garantir isso é não haver duas implementações.

Aqui não entra `fastapi`: o que mora neste módulo é a tradução entre o
esquema que o navegador fala (`schemas`) e o motor (`comparison`). Quem
transforma erro em código de status é a rota.
"""
from __future__ import annotations

from ..comparison import (
    DEFAULT_WORKERS,
    ArmResult,
    RunDone,
    arms_from_keys,
    run_comparison,
)
from ..config import Discipline, SimulationConfig
from .schemas import (
    ArmResultOut,
    AxisBandsOut,
    CompareRequest,
    CompareResponse,
    RunSummaryOut,
    ScenarioIn,
)

__all__ = ["build_config", "compare_scenario"]


def build_config(req: ScenarioIn, *, seed: int = 0) -> SimulationConfig:
    """Converte o cenário recebido no `SimulationConfig` do motor.

    A comparação passa cada seed da amostra, de modo que todos os braços veem
    o mesmo cenário — que é o que a Seção 7.3 exige dela.
    """
    return SimulationConfig(
        disciplines=[
            Discipline(
                name=d.name,
                # `seats` é a oferta da **disciplina**; `classes` a reparte
                # entre as turmas, que são os bens de fato alocados.
                seats=d.classes * req.class_size,
                classes=d.classes,
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
        performance_profiles=tuple(p.to_profile() for p in req.performance_profiles),
        availability_profiles=tuple(
            p.to_profile() for p in req.availability_profiles
        ),
        selectivity_profiles=tuple(p.to_profile() for p in req.selectivity_profiles),
        concentration_profiles=tuple(
            p.to_profile() for p in req.concentration_profiles
        ),
        interest_stability=req.interest_stability,
        class_stability=req.class_stability,
        class_difficulty_levels=req.class_difficulty_levels,
        resolver=req.resolver,
        credit_memory=req.credit_memory,
        interest_mean=req.interest_mean,
        interest_sigma=req.interest_sigma,
        max_hours=req.max_hours,
        periods=req.periods,
        entry_periods=req.entry_periods,
        max_residence=req.max_residence,
        students_per_profile=req.students_per_profile,
        rounds=req.rounds,
        min_grade=req.min_grade,
        elective_hours=req.elective_hours,
        base_credits=req.base_credits,
        credit_return=req.credit_return,
        seed=seed,
    )


def compare_scenario(
    req: CompareRequest,
    *,
    workers: int = DEFAULT_WORKERS,
    on_run_done: RunDone | None = None,
) -> CompareResponse:
    """Roda a comparação descrita por `req` e devolve a resposta da API.

    Não grava nada: quem decide registrar em disco é quem chamou. `saved_to`
    sai `None` daqui.
    """
    result = run_comparison(
        build_config(req),
        runs=req.runs,
        arms=arms_from_keys(req.arms),
        workers=workers,
        on_run_done=on_run_done,
    )
    return CompareResponse(
        runs=result.runs,
        interest_distribution=result.interest_distribution,
        grade_distribution=result.grade_distribution,
        arms=[_arm_out(arm) for arm in result.arms],
    )


def _arm_out(arm: ArmResult) -> ArmResultOut:
    return ArmResultOut(
        key=arm.key,
        mechanism=arm.mechanism,
        credit_return=arm.credit_return,
        runs=[RunSummaryOut.model_validate(run) for run in arm.runs],
        series=[AxisBandsOut.model_validate(axis) for axis in arm.series],
    )
