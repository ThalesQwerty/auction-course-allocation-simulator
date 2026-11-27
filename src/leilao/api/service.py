"""O que as rotas fazem, sem HTTP."""
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
    StudentPointOut,
    ScenarioIn,
)

__all__ = ["build_config", "compare_scenario"]


def build_config(req: ScenarioIn, *, seed: int = 0) -> SimulationConfig:
    """Converte o cenário recebido no `SimulationConfig` do motor."""
    return SimulationConfig(
        disciplines=[
            Discipline(
                name=d.name,
                seats=d.classes * req.class_size,
                classes=d.classes,
                hours=d.hours,
                unlocks=tuple(d.unlocks),
                entry=d.entry,
                elective=d.elective,
                fluctuation=d.fluctuation,
            )
            for d in req.disciplines
        ],
        approval_rate=req.approval_rate,
        grade_sd=req.grade_sd,
        repetition_gain=req.repetition_gain,
        schedule_mean=req.schedule_mean,
        schedule_sigma=req.schedule_sigma,
        schedule_fluctuation=req.schedule_fluctuation,
        first_seed=req.first_seed,
        availability=req.availability.to_shape(),
        availability_fluctuation=req.availability_fluctuation,
        selectivity_mean=req.selectivity_mean,
        selectivity_sigma=req.selectivity_sigma,
        selectivity_fluctuation=req.selectivity_fluctuation,
        grade_cuts=tuple(req.grade_cuts),
        demand_cuts=tuple(req.demand_cuts),
        slots=req.slots,
        interest_mean=req.interest_mean,
        interest_sigma=req.interest_sigma,
        interest_fluctuation=req.interest_fluctuation,
        max_hours=req.max_hours,
        periods=req.periods,
        warmup_periods=req.warmup,
        measured_cohorts=req.measured_cohorts,
        max_residence=req.max_residence,
        students_per_entry_class=req.students_per_entry_class,
        rounds=req.rounds,
        min_grade=req.min_grade,
        elective_hours=req.elective_hours,
        min_credits=req.min_credits,
        max_credits=req.max_credits,
        allocation_time_limit=(
            None
            if req.allocation_time_limit_min is None
            else req.allocation_time_limit_min * 60
        ),
        seed=seed,
    )


def compare_scenario(
    req: CompareRequest,
    *,
    workers: int = DEFAULT_WORKERS,
    on_run_done: RunDone | None = None,
) -> CompareResponse:
    """Roda a comparação descrita por `req` e devolve a resposta da API."""
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
        runs=[RunSummaryOut.model_validate(run) for run in arm.runs],
        points=[StudentPointOut.model_validate(point) for point in arm.points],
        series=[AxisBandsOut.model_validate(axis) for axis in arm.series],
    )
