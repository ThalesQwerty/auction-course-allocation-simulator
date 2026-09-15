# Simulador — Leilão por Créditos para Matrícula Universitária

Motor de simulação e interface de configuração/execução para o TCC
*"Modelagem e simulação computacional de mecanismos de leilão por créditos
aplicadas à matrícula universitária"* (UFBA, 2026).

## Arquitetura

```
Simulador/
├── src/leilao/          # Motor (Python) + API de ponte (FastAPI)
│   ├── entities.py       # Problema central P = (A,B,D,p,q,w,W,X) — Seção 3
│   ├── wdp_solver.py      # Resolvedor de PLI (Winner Determination Problem)
│   ├── tie_breaking.py    # Desempate, viés e perturbação estocástica — 7.1.2
│   ├── auction.py          # Mecanismo de leilão por créditos — 7.1
│   ├── cr_mechanism.py     # Linha de base tradicional por CR — 7.3.1
│   ├── metrics.py           # Eficiência, ocupação, Jain, Pearson — 7.3.3
│   ├── scenario.py           # Entrada unificada (JSON) para os dois mecanismos
│   ├── simulation.py          # Roda os dois mecanismos e compara métricas
│   └── api/                    # FastAPI: CRUD de cenários + execução
├── tests/                # pytest (motor + API)
├── data/                 # Cenários e resultados salvos em JSON
└── web/                  # Interface React + TypeScript (configuração + execução)
```

**Front-end (TypeScript) → API (FastAPI/Python) → Motor (Python)**: a interface
web monta o cenário (alunos, disciplinas, solicitações, utilidades) e o
dispara via HTTP; o servidor local FastAPI é a única ponte entre as duas
linguagens — toda a lógica de alocação/PLI vive exclusivamente no motor Python.

## Escopo implementado nesta versão

Implementado e testado (40 testes, `pytest`):

- Problema central `P` e resolvedor exato via PLI (Seção 3, `wdp_solver.py`).
- Mecanismo de leilão por créditos multi-rodada: lances proporcionais à
  utilidade percebida, preços de mercado (2º preço), consumo de créditos,
  desempate/viés/perturbação (Seção 7.1).
- Linha de base tradicional por CR: mochila local por aluno + alocação
  global por prioridade de CR (Seção 7.3.1).
- Métricas de avaliação: eficiência, ocupação, Índice de Jain, correlação de
  Pearson (Seção 7.3.3).
- API FastAPI com CRUD de cenários e execução comparativa dos dois
  mecanismos, persistindo cenários/resultados em JSON.
- Interface React/TypeScript para montar cenários (alunos, disciplinas,
  solicitações, exclusões de horário) e visualizar os resultados comparados.

**Ainda não implementado** (próxima camada, Seção 7.2 do anteprojeto): a
simulação multi-período completa da universidade — cursos com grade
obrigatória/optativa/livre, senioridade de disciplinas, entrada de novos
alunos ao longo do tempo, notas e retorno de créditos por desempenho. O
motor atual resolve um único "leilão" (possivelmente com várias rodadas
internas) para uma instância transversal de alunos/disciplinas; a camada
temporal multi-período deve ser construída por cima dos módulos existentes
(`auction.py`, `cr_mechanism.py`, `metrics.py`), reaproveitando-os a cada
período letivo.

## Como rodar

### Motor + testes (Python)

```powershell
cd Simulador
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

### API (servidor local)

```powershell
.\.venv\Scripts\python.exe -m uvicorn leilao.api.main:app --reload --port 8000
```

Documentação interativa (Swagger) em `http://localhost:8000/docs`.

### Interface web

```powershell
cd web
npm install
npm run dev
```

Abre em `http://localhost:5173` (espera a API em `http://localhost:8000`;
ajustável via variável de ambiente `VITE_API_URL`).

## Convenções de código

Os módulos do motor citam explicitamente os números das equações do
anteprojeto (`TCC1_Anteprojeto_Thales_Brito_Rodrigues.pdf`) em docstrings,
para rastreabilidade entre a formalização matemática (Seção 3, 7.1, 7.3) e a
implementação.
