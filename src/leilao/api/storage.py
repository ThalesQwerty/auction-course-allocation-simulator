"""Grava o resultado de uma execução em disco, como JSON."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "delete_result",
    "list_results",
    "read_result",
    "result_path",
    "results_dir",
    "save_result",
]

UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def results_dir() -> Path:
    return Path(os.environ.get("LEILAO_RESULTS_DIR", "resultados"))


def save_result(*, kind: str, config: Any, result: Any) -> str | None:
    """Grava `{kind, at, config, result}` e devolve o caminho, ou `None`."""
    moment = datetime.now(timezone.utc)
    payload = {
        "kind": kind,
        "at": moment.isoformat(),
        "config": _plain(config),
        "result": _plain(result),
    }
    name = UNSAFE.sub("-", f"{kind}-{moment.strftime('%Y%m%d-%H%M%S')}")
    try:
        folder = results_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = _free_path(folder, name)
        path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        return str(path)
    except OSError:
        return None


def _free_path(folder: Path, name: str) -> Path:
    """O primeiro caminho livre — duas execuções no mesmo segundo acontecem."""
    candidate = folder / f"{name}.json"
    index = 2
    while candidate.exists():
        candidate = folder / f"{name}-{index}.json"
        index += 1
    return candidate


def _plain(value: Any) -> Any:
    dump = getattr(value, "model_dump", None)
    return dump(mode="json") if callable(dump) else value


def result_path(name: str) -> Path:
    """O caminho de um resultado gravado, recusando nome que escape da pasta."""
    if not name or name != UNSAFE.sub("-", name) or name.startswith("."):
        raise ValueError(f"nome de resultado inválido: {name!r}")
    return results_dir() / f"{name}.json"


def list_results() -> list[dict[str, Any]]:
    """O que há gravado, do mais recente para o mais antigo, sem o resultado."""
    folder = results_dir()
    if not folder.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for path in folder.glob("*.json"):
        payload = _load(path)
        if payload is None:
            continue
        found.append(
            {
                "name": path.stem,
                "kind": payload.get("kind", ""),
                "at": payload.get("at", ""),
                "config": payload.get("config"),
                "bytes": path.stat().st_size,
            }
        )
    return sorted(found, key=lambda row: row["at"], reverse=True)


def read_result(name: str) -> dict[str, Any] | None:
    """Um resultado gravado, inteiro, ou `None` se não houver."""
    return _load(result_path(name))


def delete_result(name: str) -> bool:
    """Apaga um resultado gravado. `False` se já não estava lá."""
    try:
        result_path(name).unlink()
        return True
    except FileNotFoundError:
        return False


def _load(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None
