# Simulador — Leilão por Créditos

Motor de simulação e interface de configuração para o TCC *"Modelagem e
simulação computacional de mecanismos de leilão por créditos aplicadas à
matrícula universitária"* (UFBA, 2026).

> **A especificação do modelo não está aqui.** A fonte de verdade é a
> [`Monografia.tex`](Monografia.tex): o que cada mecanismo faz, como as notas,
> o interesse e a disponibilidade são gerados, o que cada métrica mede e por
> quê. Este arquivo cobre só como rodar e como o código está organizado.

Simula a matrícula de uma universidade ao longo de vários períodos letivos: o
usuário configura a grade de disciplinas e a população, e a simulação gera os
alunos a partir de uma seed, roda as rodadas de alocação de cada período e
devolve as métricas. São dois mecanismos sobre o mesmo cenário, o leilão por
créditos e a ordenação por CR, e a comparação roda ambos N vezes com as mesmas
seeds.

## Como rodar

```sh
cd Simulador
make install   # venv + dependências do motor e da interface (só na primeira vez)
make dev       # sobe tudo
```

`make dev` roda a API e a interface no mesmo terminal, com a saída prefixada
por `[api]` e `[web]`; `Ctrl+C` derruba as duas.

| Comando | O que faz |
| --- | --- |
| `make dev` | API + interface juntas |
| `make api` | só o servidor — `http://localhost:8000`, Swagger em `/docs` |
| `make web` | só a interface — `http://localhost:5173` |
| `make test` | suíte pytest |
| `make example` | cenário de exemplo direto no terminal |
| `make compare` | uma comparação fora do servidor, ver abaixo |
| `make install` | venv e dependências |

No Windows os alvos delegam para o PowerShell (`dev.ps1`), então funcionam
igual chamados do PowerShell, do `cmd` ou do Git Bash. No Mac, Linux e UNIX os
mesmos alvos rodam no `sh`; o `make install` cria o venv com o `python3` do
`PATH`.

Um teste só, já que não há alvo no Makefile:

```sh
./.venv/Scripts/python.exe -m pytest tests/test_simulation.py::test_nome -v   # Windows
./.venv/bin/python -m pytest tests/test_simulation.py -k "trecho" -v          # Unix
```

Checagem de tipos do front: `cd web && npm run build`, que roda `tsc -b` antes
do Vite. Não há linter configurado.

### Comparação grande: fora do servidor

A rota `/compare` roda a comparação inteira dentro de um POST, e no cenário
cheio 20 simulações por braço são horas de CPU. Para esses casos a mesma
comparação tem uma porta de terminal:

```sh
make compare SCENARIO=resultados/comparison-20261111-102551.json RUNS=20
# ou, direto:
python -m leilao.cli --scenario <arquivo>.json --runs 20 --workers 3
```

`SCENARIO` é um JSON: um resultado já gravado (de que se lê o `config`) ou um
cenário solto. Ela imprime cada simulação quando termina, grava em
`resultados/` no mesmo formato de sempre, e o arquivo entra na interface por
**Carregar resultado**. Quem monta a resposta é `api/service.py`, o mesmo
módulo que a rota usa.

`--workers` é quantas simulações correm ao mesmo tempo, e o teto é a **memória
livre, não o número de núcleos**: cada worker pede o pico do processo Python e
o do `cbc.exe` ao mesmo tempo, e como as simulações começam juntas elas picam
juntas. Se a máquina começar a paginar, o lote deixa de terminar.
`--workers 1` roda em linha, e é como se depura uma simulação que falha.

## Organização do código

Três camadas no motor (`src/leilao/`):

**`equations/`** — uma conta por arquivo, uma função pura por conta, sem
importar nada do resto do motor. O `__init__.py` traz o índice completo
mapeando cada arquivo à equação da monografia, incluindo o que foi substituído
e o que não foi implementado.

**`auction.py`, `wdp_solver.py`, `entities.py`, `ranking.py`** — uma rodada
isolada: lances, alocação (PLI exata ou varredura gulosa, mesma assinatura),
segundo preço, consumo. Não sabem o que é aluno, nota ou grade.

**`simulation/`, `config.py`, `population.py`, `behavior.py`, `availability.py`,
`grading.py`, `metrics.py`** — a matrícula multi-período: `setup` sorteia,
`period`/`rounds`/`closing` rodam, `snapshots`/`reports` recortam.
`comparison.py` roda o mesmo cenário em cada braço de `ARMS`, N vezes.

### API e interface

`api/main.py` tem quatro rotas; `api/service.py` é o miolo delas sem HTTP
(`build_config`, `compare_scenario`), compartilhado com `cli.py`. Cada
requisição carrega o cenário inteiro, e o estado vive no navegador.

- `/run` — um leilão de uma rodada
- `/compare` — os braços da comparação, a rota mais cara; grava em
  `resultados/` (git-ignored, caminho em `LEILAO_RESULTS_DIR`) e devolve
  `saved_to`. Nenhuma rota lê de lá: quem carrega o arquivo é a interface.
- `/trace` — refaz um par braço + seed e devolve o pedido de cada aluno
- `/playground` — alocação isolada

`web/src/` é React + Vite + Recharts. `types.ts` **espelha** `api/schemas.py`:
mudou um, mude o outro. `App.tsx` guarda o histórico de execuções no
`localStorage`; `presets.ts` traz a grade e o cenário padrão; `equations/`
repete em TS as contas que a tela precisa fazer sozinha, com a mesma regra de
função pura; `charts/` embrulha o Recharts.

### Usando a interface

Em `http://localhost:5173`, a barra lateral tem **Configurar** (o formulário do
cenário), **Grade** (a oferta desenhada), **Submochila** (a decisão de um
aluno, passo a passo) e a lista de **Execuções** já feitas, cada uma
identificada por data e hora.

## Convenções de código

- Uma conta por arquivo em `equations/`, função pura, sem estado.
- Tudo em português: código, docstrings, interface, mensagens de commit.
- **Sem especificação em comentário.** Docstring curta ou nenhuma; a
  justificativa de uma regra mora na monografia. Comentário só onde a intenção
  não for inferível por um programador experiente.
- No formulário, todo `input[type=number]` precisa de
  `(valor − min) % step === 0`. O `min` é a **base** da escada do stepper, não
  só um piso de validação.
