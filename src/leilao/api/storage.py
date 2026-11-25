"""Grava o resultado de uma execução em disco, como JSON."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["results_dir", "save_result"]

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
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
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
