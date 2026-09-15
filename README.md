# Simulador — Leilão por Créditos (versão simples)

Motor de simulação e interface de configuração para o TCC *"Modelagem e
simulação computacional de mecanismos de leilão por créditos aplicadas à
matrícula universitária"* (UFBA, 2026).

## Escopo desta versão

Deliberadamente mínimo: **um período, uma rodada, sem cursos, sem notas** —
só o problema central de alocação, o leilão por créditos resolvido via PLI,
e uma interface para montar cenários e ver o resultado.

```
Simulador/
├── src/leilao/
│   ├── entities.py       # Problema central P = (A, B, D, p, q, w, W, X) — Seção 3
│   ├── wdp_solver.py       # Resolvedor exato via PLI (Winner Determination Problem)
│   ├── tie_breaking.py     # Desempate, viés administrativo e perturbação — 7.1.2
│   ├── auction.py          # Leilão por créditos de 1 rodada — 7.1
│   └── api/                 # Ponte FastAPI (sem persistência — stateless)
├── tests/                 # pytest (motor + API)
├── examples/               # Script de exemplo executável
└── web/                    # Interface React + TypeScript
```

**Front-end (TypeScript) → API (FastAPI/Python) → Motor (Python)**: a
interface monta o cenário inteiro no navegador (alunos, disciplinas, lances)
e manda para o endpoint `/run`, que devolve a alocação, os preços e o
consumo de créditos. Não há banco de dados nem cenários salvos — cada
execução é independente.

Não incluído ainda (propositalmente, para manter o núcleo simples):

- Múltiplas rodadas dentro de um período, ou múltiplos períodos letivos.
- Mecanismo tradicional por CR (linha de base para comparação).
- Métricas de avaliação (eficiência, equidade/Jain, correlação).
- Cursos, grade curricular, notas, retorno de créditos (Seção 7.2).
- Persistência de cenários (histórico, salvar/carregar).

## Como rodar

### Motor + testes (Python)

```powershell
cd Simulador
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

### Script de exemplo (sem interface, direto no terminal)

```powershell
.\.venv\Scripts\python.exe examples\simple_scenario.py
```

### API (servidor local)

```powershell
.\.venv\Scripts\python.exe -m uvicorn leilao.api.main:app --reload --port 8000
```

Documentação interativa (Swagger) em `http://localhost:8000/docs`.

### Interface web

Com a API rodando em outro terminal:

```powershell
cd web
npm install
npm run dev
```

Abre em `http://localhost:5173`. Use o botão "Carregar exemplo" para
preencher com o mesmo cenário do `examples/simple_scenario.py`, ou monte o
seu: adicione alunos (com carga horária máxima e orçamento de créditos),
disciplinas (vagas e carga horária) e lances (quanto cada aluno aposta em
cada disciplina), depois clique em "Executar leilão".

## Convenções de código

Os módulos do motor citam explicitamente os números das equações do
anteprojeto (`../TCC1_Anteprojeto_Thales_Brito_Rodrigues.pdf`) em
docstrings, para rastreabilidade entre a formalização matemática (Seção 3,
7.1) e a implementação.
