"""A utilidade: o interesse da elegível mais o de tudo que ela destrava."""
from __future__ import annotations

import pytest

from leilao.equations import inverse_edges, transitive_closure, utility

CHAIN = {"A": ("B",), "B": ("C",), "C": ()}


def chain(interest, eligible, unlocks=None, classes=None,
          schedule_interest=None, schedule_of=None):
    """Monta os dois fechos a partir das arestas declaradas, como faz o"""
    reachable = transitive_closure(unlocks if unlocks is not None else CHAIN)
    return utility(
        interest=interest,
        eligible=eligible,
        reachable=reachable,
        required=inverse_edges(reachable),
        classes=classes,
        schedule_interest=schedule_interest,
        schedule_of=schedule_of,
    )


def test_a_soma_das_elegiveis_e_um():
    """A invariante que dispensa o denominador de ψ."""
    result = chain({"A": 0.2, "B": 0.3, "C": 0.5}, ["A"])

    assert result == {"A": pytest.approx(1.0)}


def test_a_heranca_e_transitiva():
    """A cadeia inteira à frente entra, não só o próximo passo. Com A e B"""
    unlocks = {"A": ("C",), "B": (), "C": ("E",), "E": ()}
    interest = {"A": 1.0, "B": 1.0, "C": 1.0, "E": 1.0}

    result = chain(interest, ["A", "B"], unlocks=unlocks)

    assert result["A"] == pytest.approx(0.75)
    assert result["B"] == pytest.approx(0.25)
    assert result["A"] != pytest.approx(2 / 3)


def test_a_cadeia_mais_funda_vale_mais():
    """Duas porteiras idênticas em tudo menos na profundidade do que abrem:"""
    rasa = {"A": ("C",), "B": ("D",), "C": (), "D": ()}
    funda = {"A": ("C",), "B": ("D",), "C": (), "D": ("E",), "E": ()}
    interest = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0, "E": 1.0}

    sem_cauda = chain(interest, ["A", "B"], unlocks=rasa)
    com_cauda = chain(interest, ["A", "B"], unlocks=funda)

    assert sem_cauda["A"] == pytest.approx(sem_cauda["B"])
    assert com_cauda["B"] > com_cauda["A"]


def test_a_soma_e_um_em_qualquer_profundidade():
    """O argumento da normalização só usa que seq e req são inversas, então"""
    unlocks = {"A": ("C",), "B": ("E",), "C": ("E",), "E": ("F",), "F": ()}
    interest = {"A": 0.3, "B": 0.1, "C": 0.2, "E": 0.25, "F": 0.15}

    result = chain(interest, ["A", "B"], unlocks=unlocks)

    assert sum(result.values()) == pytest.approx(1.0)


def test_a_parcela_se_reparte_entre_as_porteiras_elegiveis():
    """C exige A e B, e as duas estão elegíveis: cada uma herda metade. O"""
    unlocks = {"A": ("C",), "B": ("C",), "C": ()}

    result = chain({"A": 0.1, "B": 0.1, "C": 0.8}, ["A", "B"], unlocks=unlocks)

    assert result["A"] == pytest.approx(0.5)
    assert result["B"] == pytest.approx(0.5)


def test_a_reparticao_conta_os_ancestrais_de_qualquer_profundidade():
    """E está a dois passos de A e a um de B. Sob o fecho, req(E) traz as"""
    unlocks = {"A": ("C",), "B": ("E",), "C": ("E",), "E": ()}
    interest = {"A": 0.1, "B": 0.1, "C": 0.2, "E": 0.6}

    result = chain(interest, ["A", "B"], unlocks=unlocks)

    assert result["A"] == pytest.approx(0.6)
    assert result["B"] == pytest.approx(0.4)


def test_pre_requisito_ja_aprovado_nao_divide():
    """C exige A e B, o aluno já passou em A: C trava só por B, e B herda o"""
    unlocks = {"A": ("C",), "B": ("C",), "C": ()}

    result = chain({"A": 0.1, "B": 0.3, "C": 0.6}, ["B"], unlocks=unlocks)

    assert result == {"B": pytest.approx(1.0)}


def test_a_aprovada_e_a_dispensada_nao_sao_redistribuidas():
    """Fora da grade do aluno é fora da conta: o interesse delas não vai para"""
    unlocks = {"A": (), "B": (), "C": ()}

    result = chain({"A": 0.4, "B": 0.2, "C": 0.4}, ["B", "C"], unlocks=unlocks)

    assert result["B"] == pytest.approx(0.2 / 0.6)
    assert result["C"] == pytest.approx(0.4 / 0.6)


def test_o_interesse_da_disciplina_nao_depende_de_quantas_turmas_ela_tem():
    """`I` é sorteado por disciplina, não derivado das turmas: abrir uma turma"""
    interest = {"X": 0.4, "Y": 0.4}

    uma = chain(interest, ["X", "Y"], unlocks={"X": (), "Y": ()},
                classes={"X": ("X T1",), "Y": ("Y T1",)})
    duas = chain(interest, ["X", "Y"], unlocks={"X": (), "Y": ()},
                 classes={"X": ("X T1", "X T2"), "Y": ("Y T1",)})

    assert uma["X T1"] == pytest.approx(0.5)
    assert duas["X T1"] == pytest.approx(0.5)
    assert duas["X T2"] == pytest.approx(0.5)


def test_o_horario_reparte_entre_as_irmas_e_o_fator_da_materia_cancela():
    """A turma vale a disciplina vezes o horário dela sobre o melhor horário do"""
    result = chain(
        {"X": 0.4, "Y": 0.4},
        ["X", "Y"],
        unlocks={"X": (), "Y": ()},
        classes={"X": ("X T1", "X T2"), "Y": ("Y T1",)},
        schedule_interest={"H1": 1.0, "H2": 0.25, "H3": 0.5},
        schedule_of={"X T1": "H1", "X T2": "H2", "Y T1": "H3"},
    )

    assert result["X T1"] == pytest.approx(0.5)
    assert result["X T2"] == pytest.approx(0.5 * 0.25)
    assert result["Y T1"] == pytest.approx(0.5 * 0.5)


def test_a_melhor_turma_de_cada_disciplina_soma_um():
    """É esta soma que ψ mede, e é por isso que ela dispensa denominador. Com o"""
    classes = {"X": ("X T1", "X T2"), "Y": ("Y T1", "Y T2", "Y T3")}
    interest = {"X": 0.4, "Y": 0.6}

    result = chain(
        interest, ["X", "Y"], unlocks={"X": (), "Y": ()}, classes=classes
    )
    melhores = {
        grupo: max(result[name] for name in nomes)
        for grupo, nomes in classes.items()
    }
    assert sum(melhores.values()) == pytest.approx(1.0)

    com_horario = chain(
        interest,
        ["X", "Y"],
        unlocks={"X": (), "Y": ()},
        classes=classes,
        schedule_interest={"H1": 1.0, "H2": 0.5},
        schedule_of={
            "X T1": "H2", "X T2": "H2",
            "Y T1": "H1", "Y T2": "H2", "Y T3": "H2",
        },
    )
    teto = sum(
        max(com_horario[name] for name in nomes) for nomes in classes.values()
    )
    assert teto < 1.0
    assert com_horario["Y T1"] == pytest.approx(0.6)


def test_a_ordem_das_chaves_e_a_da_grade():
    """É dela que as duas mochilas tiram o desempate: reordenar muda"""
    result = chain(
        {"A": 0.3, "B": 0.3, "C": 0.4},
        ["C", "A"],
        unlocks={"A": (), "B": (), "C": ()},
    )

    assert list(result) == ["C", "A"]


def test_sem_elegivel_nao_ha_utilidade():
    assert chain({"A": 1.0}, []) == {}


def test_o_fecho_atravessa_a_cadeia_inteira():
    reachable = transitive_closure({"A": ("C",), "C": ("E",), "E": ()})

    assert reachable["A"] == ("C", "E")
    assert reachable["C"] == ("E",)
    assert reachable["E"] == ()


def test_a_inversa_do_fecho_e_exata():
    """`Y ∈ seq(X) ⟺ X ∈ req(Y)` é o único fato que a normalização da"""
    unlocks = {
        "A": ("C", "D"),
        "B": ("D",),
        "C": ("E",),
        "D": ("E", "F"),
        "E": ("G",),
        "F": (),
        "G": (),
    }
    reachable = transitive_closure(unlocks)
    required = inverse_edges(reachable)

    pares_diretos = {(x, y) for x, heirs in reachable.items() for y in heirs}
    pares_inversos = {(x, y) for y, gates in required.items() for x in gates}
    assert pares_diretos == pares_inversos


def test_a_ordem_do_fecho_e_a_da_declaracao():
    """Ela entra na soma do numerador, onde muda o último dígito — e com ele"""
    unlocks = {"Z": ("M", "A"), "M": ("A",), "A": ()}

    assert transitive_closure(unlocks)["Z"] == ("M", "A")


def test_um_ciclo_nao_trava_o_fecho():
    """Guarda, não caso de uso: a validação do cenário rejeita ciclo antes."""
    assert transitive_closure({"A": ("B",), "B": ("A",)})["A"] == ("A", "B")
