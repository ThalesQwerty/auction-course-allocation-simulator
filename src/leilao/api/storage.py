"""Grava o resultado de uma execução em disco, como JSON.

A API continua **sem estado**: nenhuma rota lê daqui, nenhuma depende de o
arquivo existir, e apagar a pasta inteira não muda o comportamento de nada. O
que se grava é um registro do que já foi devolvido na resposta — o motor roda
em Python, então a máquina que roda é a que guarda.

O formato é o mesmo que o histórico do navegador usa, de propósito: um arquivo
gravado aqui é uma entrada de histórico, e carregá-lo na interface é só
acrescentá-lo à lista. Sem conversão, sem segundo esquema.

    { "kind": "comparison", "at": ISO 8601,
      "config": o cenário recebido, "result": a resposta devolvida }

**Por que disco e não `localStorage`.** Uma comparação custa `N` simulações
completas por braço — minutos no cenário cheio — e o `localStorage` tem uns
poucos megabytes para o domínio inteiro, disputados com todas as execuções
anteriores. Perder uma rodada dessas por falta de cota é caro demais para o
conforto de não ter arquivo.

A pasta sai de `LEILAO_RESULTS_DIR` ou, sem ela, de `resultados/` ao lado de
onde a API foi iniciada. É criada na primeira gravação.

**Falha de escrita não derruba a requisição.** Disco cheio, pasta somente
leitura ou caminho inválido devolvem `None`, e a resposta sai sem `saved_to`:
quem pediu a simulação quer o resultado, e perder o resultado inteiro porque o
registro não coube seria o pior dos dois mundos. A interface mostra o caminho
quando ele existe e silencia quando não.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["results_dir", "save_result"]

# O nome do arquivo entra em linha de comando e em barra de endereço; manter
# só o que é seguro nos dois evita ter de escapar nos dois.
UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def results_dir() -> Path:
    return Path(os.environ.get("LEILAO_RESULTS_DIR", "resultados"))


def save_result(*, kind: str, config: Any, result: Any) -> str | None:
    """Grava `{kind, at, config, result}` e devolve o caminho, ou `None`.

    `config` e `result` são modelos do Pydantic ou qualquer coisa que
    `model_dump` ou `json.dumps` saibam serializar.
    """
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
