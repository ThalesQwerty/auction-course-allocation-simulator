"""A redistribuição da utilidade do que o aluno não pode cursar agora."""
from __future__ import annotations

import pytest

from leilao.equations import approval_index, eligible_utility, fitness, supply_index

# Cadeia linear: C depende de B, que depende de A.
CHAIN = {"A": (), "B": ("A",), "C": ("B",)}


def test_a_massa_total_se_conserva():
    row = {"A": 0.2, "B": 0.3, "C": 0.5}

    result = eligible_utility(
        row=row, eligible=["A"], approved=set(), prerequisites=CHAIN
    )

    assert result == {"A": pytest.approx(1.0)}


def test_a_cadeia_inteira_desce_ate_a_porteira():
    """Nenhuma órfã: C não tem pré-requisito elegível *direto*, e mesmo assim
    encontra A subindo a cadeia. É o que a cascata fazia em vários passos."""
    row = {"A": 0.1, "B": 0.4, "C": 0.5}

    result = eligible_utility(
        row=row, eligible=["A"], approved=set(), prerequisites=CHAIN
    )

    assert result["A"] == pytest.approx(1.0)


def test_pre_requisito_ja_aprovado_nao_recebe():
    """Se C exige A e B e o aluno já passou em A, C trava só por B. Mandar
    utilidade para A gastaria o sinal onde ele não tem efeito."""
    prerequisites = {"A": (), "B": (), "C": ("A", "B")}
    row = {"A": 0.1, "B": 0.3, "C": 0.6}

    result = eligible_utility(
        row=row, eligible=["B"], approved={"A"}, prerequisites=prerequisites
    )

    # B fica com a própria utilidade, mais a de C inteira (é a única que
    # trava), mais a de A, que já saiu da grade.
    assert result == {"B": pytest.approx(1.0)}


def test_ja_aprovada_divide_entre_todas_as_elegiveis():
    prerequisites = {"A": (), "B": (), "C": ()}
    row = {"A": 0.4, "B": 0.2, "C": 0.4}

    result = eligible_utility(
        row=row, eligible=["B", "C"], approved={"A"}, prerequisites=prerequisites
    )

    assert result["B"] == pytest.approx(0.2 + 0.2)
    assert result["C"] == pytest.approx(0.4 + 0.2)


def test_divide_igual_entre_os_ancestrais_elegiveis_da_cadeia():
    """O exemplo da docstring: C exige B1 e B2, B1 exige A1 e B2 exige A2, A3
    e A4. Distribuindo no destino, os quatro recebem 1/4 — a cascata daria
    1/2 a A1 contra 1/6 aos outros."""
    prerequisites = {
        "A1": (), "A2": (), "A3": (), "A4": (),
        "B1": ("A1",), "B2": ("A2", "A3", "A4"),
        "C": ("B1", "B2"),
    }
    row = {"A1": 0.0, "A2": 0.0, "A3": 0.0, "A4": 0.0, "B1": 0.0, "B2": 0.0, "C": 1.0}

    result = eligible_utility(
        row=row,
        eligible=["A1", "A2", "A3", "A4"],
        approved=set(),
        prerequisites=prerequisites,
    )

    assert all(result[name] == pytest.approx(0.25) for name in ("A1", "A2", "A3", "A4"))


def test_a_ordem_das_chaves_e_a_da_grade():
    """É dela que as duas mochilas tiram o desempate: reordenar muda
    resultado."""
    prerequisites = {"A": (), "B": (), "C": ()}
    row = {"A": 0.3, "B": 0.3, "C": 0.4}

    result = eligible_utility(
        row=row, eligible=["C", "A"], approved={"B"}, prerequisites=prerequisites
    )

    assert list(result) == ["C", "A"]


def test_sem_elegivel_nao_ha_para_onde_redistribuir():
    row = {"A": 1.0}

    assert eligible_utility(
        row=row, eligible=[], approved={"A"}, prerequisites={"A": ()}
    ) == {}


def test_o_indice_de_oferta_e_neutro_sem_ninguem_elegivel():
    """O artefato do funil: disciplina que ninguém podia pedir daria folga
    máxima pela razão crua, e o bônus cairia justo onde vai lotar."""
    assert supply_index(seats=40, requests=0, eligible=0) == 0.5
    # Com elegíveis e nenhum pedido, a demanda baixa é informação de verdade.
    assert supply_index(seats=40, requests=0, eligible=12) == 1.0


def test_o_indice_de_oferta_satura_nas_duas_pontas():
    assert supply_index(seats=1, requests=400, eligible=400) < 0.01
    assert supply_index(seats=40, requests=40, eligible=40) == 0.5


def test_a_suavizacao_de_laplace_resolve_o_cold_start():
    """Disciplina nunca ofertada dá exatamente o neutro: a prior uniforme *é*
    ausência de informação."""
    assert approval_index(approvals=0, allocations=0) == 0.5
    # Contagem pequena não vale 100%.
    assert approval_index(approvals=1, allocations=1) == pytest.approx(2 / 3)


def test_o_indice_de_aprovacao_nunca_chega_as_pontas():
    """É o que torna a potência de `decision_score` sempre segura."""
    for allocations in (1, 10, 1000):
        assert 0.0 < approval_index(approvals=0, allocations=allocations) < 1.0
        assert 0.0 < approval_index(approvals=allocations, allocations=allocations) < 1.0


def test_a_aptidao_e_carga_por_periodo():
    assert fitness(approved_hours=120, periods_enrolled=6) == 20.0
    # Jubilado cedo com pouca carga pontua baixo, que é o desejado.
    assert fitness(approved_hours=10, periods_enrolled=5) == 2.0


def test_a_aptidao_recusa_idade_nao_positiva():
    with pytest.raises(ValueError):
        fitness(approved_hours=10, periods_enrolled=0)
