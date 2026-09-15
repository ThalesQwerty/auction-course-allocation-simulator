# Simulador — Leilão por Créditos (versão simples)

Motor de simulação para o TCC *"Modelagem e simulação computacional de
mecanismos de leilão por créditos aplicadas à matrícula universitária"*
(UFBA, 2026).

## Escopo desta versão

Deliberadamente mínimo: **um período, uma rodada, sem cursos, sem notas** —
só o problema central de alocação e o leilão por créditos resolvido via PLI.

```
Simulador/
├── src/leilao/
│   ├── entities.py       # Problema central P = (A, B, D, p, q, w, W, X) — Seção 3
│   ├── wdp_solver.py       # Resolvedor exato via PLI (Winner Determination Problem)
│   ├── tie_breaking.py     # Desempate, viés administrativo e perturbação — 7.1.2
│   └── auction.py          # Leilão por créditos de 1 rodada — 7.1
└── tests/                 # pytest
```

Não incluído ainda (propositalmente, para manter o núcleo simples e
validado antes de crescer):

- Múltiplas rodadas dentro de um período, ou múltiplos períodos letivos.
- Mecanismo tradicional por CR (linha de base para comparação).
- Métricas de avaliação (eficiência, equidade/Jain, correlação).
- Cursos, grade curricular, notas, retorno de créditos (Seção 7.2).
- API e interface web.

## Como funciona

1. Você define agentes (`Agent`: id + capacidade `W_a`), bens (`Good`: id +
   vagas `q_x` + peso `w_x`) e, opcionalmente, exclusões mútuas
   (`MutualExclusion`, para choque de horário).
2. Cada agente distribui seu orçamento de créditos em lances (`Bid`:
   agente, bem, créditos), respeitando o próprio orçamento (`AuctionInput`
   valida isso na criação — eq. 19).
3. `run_auction(...)` resolve o Problema de Determinação de Vencedores via
   PLI (`wdp_solver.solve_wdp`), calcula o preço de mercado de cada bem
   (2º preço — maior lance mal-sucedido) e o consumo de créditos de cada
   vencedor.

Exemplo mínimo:

```python
from leilao.auction import AuctionInput, Bid, run_auction
from leilao.entities import Agent, Good

result = run_auction(AuctionInput(
    agents=[Agent("ana", capacity=10), Agent("bia", capacity=10)],
    goods=[Good("calc1", quantity=1, weight=4)],
    budgets={"ana": 100, "bia": 100},
    bids=[Bid("ana", "calc1", 70), Bid("bia", "calc1", 40)],
    seed=42,
))

print(result.allocation)         # {("ana", "calc1"): 1, ("bia", "calc1"): 0}
print(result.prices)             # {"calc1": 40.0}  — preço = maior lance perdedor
print(result.consumption)        # {("ana", "calc1"): 40.0}  — vencedor paga o 2º preço
print(result.remaining_budget)   # {"ana": 60.0, "bia": 100}  — quem perde não gasta créditos
```

## Como rodar

```powershell
cd Simulador
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

## Convenções de código

Os módulos citam explicitamente os números das equações do anteprojeto
(`../TCC1_Anteprojeto_Thales_Brito_Rodrigues.pdf`) em docstrings, para
rastreabilidade entre a formalização matemática e a implementação.
