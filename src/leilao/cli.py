"""A comparação pelo terminal, para os cenários que não cabem numa requisição."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .api.schemas import CompareRequest
from .api.service import compare_scenario
from .api.storage import save_result
from .comparison import ARM_BY_KEY, DEFAULT_WORKERS, MAX_RUNS, Arm

__all__ = ["main"]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m leilao.cli",
        description=(
            "Roda a comparação entre os modelos fora do servidor e grava o "
            "resultado em resultados/, no formato que a interface carrega."
        ),
    )
    parser.add_argument(
        "--scenario",
        required=True,
        type=Path,
        metavar="ARQUIVO",
        help=(
            "JSON com o cenário: um resultado já gravado em resultados/ (lê o "
            "campo 'config') ou um cenário solto."
        ),
    )
    parser.add_argument(
        "--runs",
        type=int,
        metavar="N",
        help=(
            f"Quantas simulações por braço, com as seeds de 1 a N (1 a "
            f"{MAX_RUNS}). Sem isto, vale o que está no arquivo."
        ),
    )
    parser.add_argument(
        "--arms",
        nargs="+",
        choices=sorted(ARM_BY_KEY),
        metavar="BRACO",
        help=(
            "Quais modelos rodar — "
            + ", ".join(sorted(ARM_BY_KEY))
            + ". Sem isto, vale o que está no arquivo."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help=(
            f"Quantas simulações ao mesmo tempo (padrão: {DEFAULT_WORKERS}). "
            "No cenário cheio cada uma pede uns 1,3 GB (Python mais o CBC) e "
            "elas picam juntas: o teto é a memória livre, não os núcleos. "
            "1 roda em linha, sem paralelismo."
        ),
    )
    return parser.parse_args(argv)


def _read_scenario(path: Path) -> CompareRequest:
    """O cenário do arquivo, seja ele um resultado gravado ou um cenário solto."""
    if not path.is_file():
        raise SystemExit(
            f"não achei o cenário em {path} — informe um arquivo JSON, "
            "por exemplo um resultado de resultados/."
        )
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"não consegui ler {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} não é JSON válido: {exc}") from exc

    if isinstance(payload, dict) and isinstance(payload.get("config"), dict):
        payload = payload["config"]
    try:
        return CompareRequest.model_validate(payload)
    except ValidationError as exc:
        raise SystemExit(f"{path} não descreve um cenário válido:\n{exc}") from exc


def _with_overrides(
    request: CompareRequest, *, runs: int | None, arms: list[str] | None
) -> CompareRequest:
    """O cenário com o que veio da linha de comando, revalidado."""
    changes = {}
    if runs is not None:
        changes["runs"] = runs
    if arms is not None:
        changes["arms"] = arms
    if not changes:
        return request
    try:
        return CompareRequest.model_validate({**request.model_dump(), **changes})
    except ValidationError as exc:
        raise SystemExit(f"opção inválida:\n{exc}") from exc


def _count(amount: int, singular: str, plural: str) -> str:
    return f"{amount} {singular if amount == 1 else plural}"


def _minutes(since: float) -> str:
    return f"{(time.perf_counter() - since) / 60:.1f}".replace(".", ",")


def _progress(total: int, started: float):
    """Imprime uma linha por simulação concluída."""
    done = 0

    def report(arm: Arm, seed: int) -> None:
        nonlocal done
        done += 1
        print(
            f"[{done:>3}/{total}] {arm.key} seed {seed} — {_minutes(started)} min",
            flush=True,
        )

    return report


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    request = _with_overrides(
        _read_scenario(args.scenario), runs=args.runs, arms=args.arms
    )
    total = request.runs * len(request.arms)

    print(
        f"{args.scenario}: {len(request.disciplines)} disciplinas, "
        f"{request.periods} períodos, {_count(request.rounds, 'rodada', 'rodadas')}",
        f"braços: {', '.join(request.arms)}",
        f"{_count(request.runs, 'simulação', 'simulações')} em cada, "
        f"{total} no total, {args.workers} por vez",
        sep="\n",
        flush=True,
    )

    started = time.perf_counter()
    try:
        response = compare_scenario(
            request,
            workers=args.workers,
            on_run_done=_progress(total, started),
        )
    except KeyboardInterrupt:
        print("\ninterrompido — nada foi gravado.", file=sys.stderr)
        return 130
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    response.saved_to = save_result(
        kind="comparison", config=request, result=response
    )
    if response.saved_to is None:
        print(
            f"\nterminou em {_minutes(started)} min, mas a gravação falhou — "
            "confira a pasta de resultados.",
            file=sys.stderr,
        )
        return 1
    print(f"\n{_minutes(started)} min — gravado em {response.saved_to}")
    print('Carregue na interface por "Carregar resultado".')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
