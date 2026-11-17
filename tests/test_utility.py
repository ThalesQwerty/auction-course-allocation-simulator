"""A utilidade: o interesse da elegível mais o do que ela destrava."""
from __future__ import annotations

import pytest

from leilao.equations import utility

# Cadeia linear: A destrava B, que destrava C.
CHAIN_SUCCESSORS = {"A": ("B",), "B": ("C",), "C": ()}
CHAIN_PREREQUISITES = {"A": (), "B": ("A",), "C": ("B",)}


def chain(interest, eligible, **overrides):
    return utility(
        interest=interest,
        eligible=eligible,
        successors=overrides.get("successors", CHAIN_SUCCESSORS),
        prerequisites=overrides.get("prerequisites", CHAIN_PREREQUISITES),
    )


def test_a_soma_das_elegiveis_e_um():
    """A invariante que dispensa o denominador de ψ."""
    result = chain({"A": 0.2, "B": 0.3, "C": 0.5}, ["A"])

    assert result == {"A": pytest.approx(1.0)}


def test_a_heranca_e_de_um_nivel():
    """O aluno olha um período à frente: C, que está a dois passos de A, não
    entra nem no numerador nem no denominador."""
    successors = {"A": ("B",), "B": ("C",), "C": (), "D": ()}
    prerequisites = {"A": (), "B": ("A",), "C": ("B",), "D": ()}
    interest = {"A": 0.1, "B": 0.4, "C": 0.5, "D": 0.1}

    result = chain(
        interest, ["A", "D"], successors=successors, prerequisites=prerequisites
    )

    # Denominador: 0,1 (A) + 0,1 (D) + 0,4 (B) = 0,6. O 0,5 de C é ignorado.
    assert result["A"] == pytest.approx(0.5 / 0.6)
    assert result["D"] == pytest.approx(0.1 / 0.6)
    assert sum(result.values()) == pytest.approx(1.0)


def test_a_parcela_se_reparte_entre_as_porteiras_elegiveis():
    """C exige A e B, e as duas estão elegíveis: cada uma herda metade. O
    pré-requisito é conjuntivo, então as duas são igualmente necessárias, e
    dar o interesse inteiro a cada uma contaria C duas vezes."""
    successors = {"A": ("C",), "B": ("C",), "C": ()}
    prerequisites = {"A": (), "B": (), "C": ("A", "B")}

    result = chain(
        {"A": 0.1, "B": 0.1, "C": 0.8},
        ["A", "B"],
        successors=successors,
        prerequisites=prerequisites,
    )

    assert result["A"] == pytest.approx(0.5)
    assert result["B"] == pytest.approx(0.5)


def test_pre_requisito_ja_aprovado_nao_divide():
    """C exige A e B, o aluno já passou em A: C trava só por B, e B herda o
    interesse de C inteiro. O interesse de A simplesmente não entra."""
    successors = {"A": ("C",), "B": ("C",), "C": ()}
    prerequisites = {"A": (), "B": (), "C": ("A", "B")}

    result = chain(
        {"A": 0.1, "B": 0.3, "C": 0.6},
        ["B"],
        successors=successors,
        prerequisites=prerequisites,
    )

    assert result == {"B": pytest.approx(1.0)}


def test_a_aprovada_e_a_dispensada_nao_sao_redistribuidas():
    """Fora da grade do aluno é fora da conta: o interesse delas não vai para
    lugar nenhum, e o denominador não as enxerga."""
    successors = {"A": (), "B": (), "C": ()}
    prerequisites = {"A": (), "B": (), "C": ()}

    result = chain(
        {"A": 0.4, "B": 0.2, "C": 0.4},
        ["B", "C"],
        successors=successors,
        prerequisites=prerequisites,
    )

    assert result["B"] == pytest.approx(0.2 / 0.6)
    assert result["C"] == pytest.approx(0.4 / 0.6)


def test_a_disciplina_vale_a_media_das_turmas():
    """A média, e não o máximo: abrir uma turma a mais não muda o quanto a
    matéria vale para o aluno."""
    classes = {"X": ("X T1", "X T2"), "Y": ("Y T1",)}
    interest = {"X T1": 0.6, "X T2": 0.2, "Y T1": 0.4}

    result = utility(
        interest=interest,
        eligible=["X", "Y"],
        successors={"X": (), "Y": ()},
        prerequisites={"X": (), "Y": ()},
        classes=classes,
    )

    # I_X = 0,4 e I_Y = 0,4: as duas valem o mesmo, 0,5 cada.
    assert result["X T1"] == pytest.approx(0.5)
    assert result["Y T1"] == pytest.approx(0.5)
    # A irmã vale a fração do interesse dela sobre o da melhor turma.
    assert result["X T2"] == pytest.approx(0.5 * 0.2 / 0.6)


def test_a_melhor_turma_de_cada_disciplina_soma_um():
    """É esta soma que ψ mede, e é por isso que ela dispensa denominador."""
    classes = {"X": ("X T1", "X T2"), "Y": ("Y T1", "Y T2", "Y T3")}
    interest = {
        "X T1": 0.3,
        "X T2": 0.1,
        "Y T1": 0.2,
        "Y T2": 0.25,
        "Y T3": 0.15,
    }

    result = utility(
        interest=interest,
        eligible=["X", "Y"],
        successors={"X": (), "Y": ()},
        prerequisites={"X": (), "Y": ()},
        classes=classes,
    )

    melhores = sum(
        max(result[name] for name in names) for names in classes.values()
    )
    assert melhores == pytest.approx(1.0)


def test_a_ordem_das_chaves_e_a_da_grade():
    """É dela que as duas mochilas tiram o desempate: reordenar muda
    resultado."""
    successors = {"A": (), "B": (), "C": ()}
    prerequisites = {"A": (), "B": (), "C": ()}

    result = chain(
        {"A": 0.3, "B": 0.3, "C": 0.4},
        ["C", "A"],
        successors=successors,
        prerequisites=prerequisites,
    )

    assert list(result) == ["C", "A"]


def test_sem_elegivel_nao_ha_utilidade():
    assert chain({"A": 1.0}, []) == {}
