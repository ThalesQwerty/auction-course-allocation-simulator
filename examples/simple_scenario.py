"""Exemplo executável: monta um cenário simples e imprime os resultados do leilão.

Rodar com:
    .venv\\Scripts\\python.exe examples\\simple_scenario.py

Cenário: 3 alunos disputando 2 disciplinas com vagas limitadas. Ana e Bia
concorrem pela mesma vaga em "calc1"; Caio pega "fis1" sem concorrência.
"""
from leilao.auction import AuctionInput, Bid, run_auction
from leilao.entities import Agent, Good


def main() -> None:
    auction_input = AuctionInput(
        agents=[
            Agent("ana", capacity=8),
            Agent("bia", capacity=8),
            Agent("caio", capacity=8),
        ],
        goods=[
            Good("calc1", quantity=1, weight=4),  # só 1 vaga — vai ter disputa
            Good("fis1", quantity=2, weight=4),
        ],
        budgets={"ana": 100, "bia": 100, "caio": 100},
        bids=[
            Bid("ana", "calc1", 70),   # ana concentra crédito em calc1
            Bid("ana", "fis1", 20),
            Bid("bia", "calc1", 55),   # bia disputa calc1, mas aposta menos
            Bid("bia", "fis1", 30),
            Bid("caio", "fis1", 40),   # caio nem disputa calc1
        ],
        seed=42,
    )

    result = run_auction(auction_input)

    print("=== Alocação (quem ganhou o quê) ===")
    for (agent_id, good_id), won in sorted(result.allocation.items()):
        status = "DEFERIDO" if won else "INDEFERIDO"
        print(f"  {agent_id:6s} x {good_id:6s} -> {status}")

    print("\n=== Preços de mercado (2º preço por bem) ===")
    for good_id, price in result.prices.items():
        print(f"  {good_id:6s}: {price} créditos")

    print("\n=== Consumo de créditos (só quem ganhou paga) ===")
    for (agent_id, good_id), consumed in result.consumption.items():
        print(f"  {agent_id:6s} pagou {consumed} créditos por {good_id}")

    print("\n=== Orçamento restante por aluno ===")
    for agent_id, remaining in result.remaining_budget.items():
        print(f"  {agent_id:6s}: {remaining} créditos restantes")


if __name__ == "__main__":
    main()
