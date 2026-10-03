"""Configuração de um cenário de simulação (Seção 7.2 do anteprojeto).

O usuário descreve o cenário em dois blocos — parâmetros gerais e disciplinas —
e a simulação deriva o resto (alunos, nomes, matriz de utilidades, notas)
aleatoriamente a partir da `seed`.

Não há cursos: todo aluno é da universidade e cursa a mesma grade, e **toda
disciplina é obrigatória** — só se forma quem aprova em todas. O que ordena a
grade são os **pré-requisitos**: uma disciplina sem pré-requisito é de 1º
período, e uma com pré-requisitos é do período seguinte ao mais tardio deles.
Essa indução substitui a senioridade da eq. (38): em vez de um número dado a
cada disciplina, o período sai da própria estrutura da grade.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

# Política de retorno de créditos f_gamma — eq. (34). O anteprojeto deixa a
# forma concreta em aberto e trata as políticas como eixo de experimentação
# (Seção 7.3.2) — as quatro comparadas estão em `grading.credit_return`.
CreditReturnPolicy = Literal["none", "unit", "full", "ratio"]

# Sentido da distorção da matriz de utilidades num perfil de afinidade.
# "concentrated" eleva a um inteiro positivo e afasta as utilidades entre si;
# "diluted" eleva ao inverso dele e as aproxima.
AffinityKind = Literal["concentrated", "diluted"]

# Teto da intensidade da afinidade. Acima disso a transformação não muda mais
# nada de útil: com expoente 10 a massa já está praticamente toda na disciplina
# preferida, e o inverso já achatou a matriz em quase uniforme.
MAX_AFFINITY_INTENSITY = 10


@dataclass(frozen=True)
class AptitudeProfile:
    """Um perfil de aptidão: a distribuição das notas de primeira tentativa.

    É sempre uma normal, parametrizada por média e desvio padrão, truncada em
    [0, 10] e arredondada a 0,1 no sorteio (`grading.initial_grades`). Substitui
    a aptidão latente contínua que havia antes: com perfis, a heterogeneidade de
    desempenho vira um eixo *configurável* do cenário, em vez de um sorteio
    uniforme que ninguém controla.
    """

    name: str
    mean: float  # média da normal, em [0, 10]
    stddev: float  # desvio padrão, > 0
    # Quanto a nota sobe a cada recursada — eq. (33). Fica aqui, e não no
    # cenário, porque é a mesma grandeza que a média e o desvio: o quanto o
    # aluno aprende. Um perfil que erra muito na primeira tentativa pode ser
    # justamente o que mais ganha ao repetir, e com um valor global não havia
    # como dizer isso.
    learning_gain: float = 2.5
    share: float = 100.0  # % dos alunos que recebem este perfil

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("perfil de aptidão sem nome")
        if not 0 <= self.mean <= 10:
            raise ValueError(f"perfil {self.name!r}: média das notas deve estar em [0, 10]")
        if self.stddev <= 0:
            raise ValueError(f"perfil {self.name!r}: desvio padrão das notas deve ser > 0")
        if not 0 < self.learning_gain <= 10:
            raise ValueError(
                f"perfil {self.name!r}: incremento de aprendizado deve estar em (0, 10]"
            )
        if self.share <= 0:
            raise ValueError(f"perfil {self.name!r}: a fatia de alunos deve ser > 0")


@dataclass(frozen=True)
class AffinityProfile:
    """Um perfil de afinidade: o quanto o aluno concentra a preferência.

    A matriz de utilidades sorteada é elevada a um expoente antes de ser
    normalizada. Expoente > 1 (`concentrated`) afasta as utilidades entre si — o
    aluno quer muito uma ou duas disciplinas e quase nada o resto. Expoente < 1
    (`diluted`, o inverso de um inteiro) as aproxima — o aluno é indiferente
    entre o que lhe resta.

    Importa porque é exatamente a informação que o leilão por créditos diz
    captar e a ordenação por CR não: um aluno concentrado aposta tudo no que
    precisa, e é dele que o mecanismo deveria cuidar melhor.
    """

    name: str
    kind: AffinityKind
    intensity: int  # inteiro positivo
    # W_a — carga horária máxima por período, eq. (4). Fica aqui porque anda
    # junto da concentração: quem quer poucas disciplinas com intensidade e quem
    # quer muitas por igual não estão descrevendo só preferência, mas também
    # quanto conseguem carregar num período.
    max_hours: int = 360
    share: float = 100.0  # % dos alunos que recebem este perfil

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("perfil de afinidade sem nome")
        if self.max_hours < 1:
            raise ValueError(
                f"perfil {self.name!r}: carga horária máxima (W_a) deve ser >= 1"
            )
        if self.kind not in ("concentrated", "diluted"):
            raise ValueError(
                f"perfil {self.name!r}: tipo de interesse deve ser 'concentrated' ou 'diluted'"
            )
        if not 1 <= self.intensity <= MAX_AFFINITY_INTENSITY:
            raise ValueError(
                f"perfil {self.name!r}: intensidade deve ser um inteiro entre 1 e "
                f"{MAX_AFFINITY_INTENSITY}"
            )
        if self.share <= 0:
            raise ValueError(f"perfil {self.name!r}: a fatia de alunos deve ser > 0")

    @property
    def exponent(self) -> float:
        """O expoente aplicado a u_{a,x} antes da normalização. Intensidade 1
        dá 1 nos dois sentidos — o perfil neutro, que não distorce nada."""
        return float(self.intensity) if self.kind == "concentrated" else 1 / self.intensity


# Perfis neutros, usados quando o cenário não define nenhum: uma aptidão média
# e uma afinidade de expoente 1, que não distorce a matriz sorteada.
DEFAULT_APTITUDE = AptitudeProfile(
    "Padrão", mean=6.5, stddev=1.5, learning_gain=2.5, share=100.0
)
DEFAULT_AFFINITY = AffinityProfile(
    "Padrão", kind="concentrated", intensity=1, max_hours=360, share=100.0
)


def apportion(total: int, weights: list[float]) -> list[int]:
    """Reparte `total` unidades inteiras entre as fatias de `weights`, pelo
    método do maior resto: cada uma leva a parte inteira da sua fatia e as
    sobras vão às maiores frações.

    É o que faz a distribuição de perfis ser **exata** em vez de sorteada. Com
    sorteio, uma geração de 40 alunos e uma fatia de 25% poderia sair com 8 ou
    com 13, e a comparação entre perfis mediria o sorteio junto do mecanismo.
    Empate de resto é desfeito pela ordem do cenário, que é determinística.
    """
    if total <= 0 or not weights:
        return [0] * len(weights)
    scale = sum(weights)
    exact = [total * weight / scale for weight in weights]
    counts = [math.floor(value) for value in exact]
    for index in sorted(
        range(len(weights)), key=lambda i: (-(exact[i] - counts[i]), i)
    )[: total - sum(counts)]:
        counts[index] += 1
    return counts


@dataclass(frozen=True)
class Discipline:
    """Uma disciplina ofertada — o bem escaso x in B (Tabela 1).

    `prerequisites` é a lista de disciplinas que o aluno precisa ter aprovado
    para ficar elegível a disputar vaga aqui. Vazia = disciplina de 1º período.
    """

    name: str
    seats: int  # q_x — vagas
    hours: int  # w_x — carga horária
    prerequisites: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("disciplina sem nome")
        if self.seats < 0:
            raise ValueError(f"disciplina {self.name!r}: vagas (q_x) deve ser >= 0")
        if self.hours <= 0:
            raise ValueError(f"disciplina {self.name!r}: carga horária (w_x) deve ser > 0")
        if self.name in self.prerequisites:
            raise ValueError(f"disciplina {self.name!r} é pré-requisito de si mesma")
        if len(set(self.prerequisites)) != len(self.prerequisites):
            raise ValueError(f"disciplina {self.name!r}: pré-requisitos repetidos")


@dataclass(frozen=True)
class SimulationConfig:
    """Cenário completo. Tudo que não está aqui é sorteado a partir de `seed`."""

    disciplines: list[Discipline] = field(default_factory=list)
    periods: int = 1  # |T| — períodos letivos
    # L — em quantos dos |T| períodos entra geração nova, contados do primeiro.
    # `None` = em todos, e aí o último período recebe uma geração que só vive
    # esse período. Com L < |T| a simulação ganha uma fase de drenagem: depois
    # do último ingresso a população só diminui, e as gerações tardias têm
    # tempo de chegar ao fim do curso em vez de serem cortadas pelo horizonte.
    entry_periods: int | None = None
    # Alunos que ingressam em cada um dos L períodos com ingresso. O ingressante
    # tem vaga garantida em todas as disciplinas de 1º período, então o ritmo de
    # entrada não pode passar da menor oferta entre elas — senão a garantia não
    # caberia. A população é este número vezes L.
    students_per_period: int = 1
    # Os dois eixos de perfil do aluno. São **independentes**: a fatia de cada
    # perfil de aptidão é a mesma dentro de cada perfil de afinidade e
    # vice-versa, então a fatia de uma combinação é o produto das duas (dois
    # perfis de 50% em cada eixo dão 25% para cada uma das quatro combinações).
    # Vazio não é aceito; omitir dá o perfil neutro do eixo.
    aptitude_profiles: list[AptitudeProfile] = field(
        default_factory=lambda: [DEFAULT_APTITUDE]
    )
    affinity_profiles: list[AffinityProfile] = field(
        default_factory=lambda: [DEFAULT_AFFINITY]
    )
    rounds: int = 1  # |R| — rodadas de alocação por período
    min_grade: float = 5.0  # n_min — nota mínima de aprovação
    base_credits: int = 10  # Gamma_min — créditos base por período, eq. (35)/(37)
    credit_return: CreditReturnPolicy = "none"
    seed: int = 0

    def __post_init__(self) -> None:
        if self.periods < 1:
            raise ValueError("é preciso simular ao menos 1 período")
        if self.entry_periods is not None and not 1 <= self.entry_periods <= self.periods:
            raise ValueError(
                "períodos com ingresso deve estar entre 1 e o total de períodos "
                f"({self.periods})"
            )
        if self.rounds < 1:
            raise ValueError("é preciso simular ao menos 1 rodada por período")
        if not 0 < self.min_grade <= 10:
            raise ValueError("nota mínima deve estar em (0, 10]")
        if self.base_credits < 1:
            raise ValueError("créditos base (Gamma_min) deve ser >= 1")
        # Sem disciplina ou sem aluno não há o que alocar: a simulação não
        # produziria período nenhum, e toda métrica sairia indefinida.
        if not self.disciplines:
            raise ValueError("o cenário precisa de pelo menos uma disciplina")
        if self.students_per_period < 1:
            raise ValueError("o cenário precisa de pelo menos um aluno por período de ingresso")

        for axis, profiles in (
            ("aptidão", self.aptitude_profiles),
            ("afinidade", self.affinity_profiles),
        ):
            if not profiles:
                raise ValueError(f"o cenário precisa de pelo menos um perfil de {axis}")
            profile_names = [p.name for p in profiles]
            if len(set(profile_names)) != len(profile_names):
                raise ValueError(f"há perfis de {axis} com nomes repetidos")
            # As fatias somam 100% porque é assim que elas se leem: cada eixo
            # reparte a população inteira. Normalizar silenciosamente esconderia
            # um erro de digitação que muda o cenário sem avisar.
            total = sum(p.share for p in profiles)
            if abs(total - 100) > 1e-6:
                raise ValueError(
                    f"as fatias dos perfis de {axis} somam {total:g}%, e precisam somar 100%"
                )

        names = [d.name for d in self.disciplines]
        if len(set(names)) != len(names):
            raise ValueError("há disciplinas com nomes repetidos")
        known = set(names)
        for discipline in self.disciplines:
            unknown = set(discipline.prerequisites) - known
            if unknown:
                raise ValueError(
                    f"disciplina {discipline.name!r} tem pré-requisitos inexistentes: "
                    f"{sorted(unknown)}"
                )

        # Levanta se houver ciclo: uma cadeia de pré-requisitos que se fecha não
        # tem período nenhum, e as disciplinas dela seriam inalcançáveis para
        # sempre — o cenário não se conclui por construção.
        first = self.first_period_disciplines()

        seats = {d.name: d.seats for d in self.disciplines}
        hours = {d.name: d.hours for d in self.disciplines}
        # O ingressante entra direto nas disciplinas de 1º período, sem leilão:
        # a oferta tem de comportar a geração inteira, e a carga somada tem de
        # caber em W_a — senão a matrícula garantida violaria a eq. (4).
        smallest = min(seats[name] for name in first)
        if self.students_per_period > smallest:
            tightest = min(first, key=lambda name: (seats[name], name))
            raise ValueError(
                f"alunos por período ({self.students_per_period}) passa da menor oferta "
                f"entre as disciplinas de 1º período ({smallest} vagas em {tightest!r}): "
                "o ingressante tem vaga garantida em todas elas"
            )
        entry_hours = sum(hours[name] for name in first)
        # A carga tem de caber em **todo** perfil de afinidade: a matrícula
        # garantida não escolhe quem a recebe, então vale o W_a mais apertado.
        tightest_profile = min(self.affinity_profiles, key=lambda p: p.max_hours)
        if entry_hours > tightest_profile.max_hours:
            raise ValueError(
                f"as {len(first)} disciplinas de 1º período somam {entry_hours} h e não "
                f"cabem na carga horária máxima do perfil {tightest_profile.name!r} "
                f"(W_a = {tightest_profile.max_hours}) — eq. (4); o ingressante cursa "
                "todas elas de uma vez"
            )

    @property
    def entry_span(self) -> int:
        """L — quantos períodos recebem geração nova, resolvido o `None`."""
        return self.periods if self.entry_periods is None else self.entry_periods

    def total_students(self) -> int:
        """|A| — uma geração do mesmo tamanho em cada um dos L períodos."""
        return self.students_per_period * self.entry_span

    def generation_profiles(self) -> list[tuple[AptitudeProfile, AffinityProfile]]:
        """O par (aptidão, afinidade) de cada aluno de **uma** geração.

        Os dois eixos são independentes, então a fatia de uma combinação é o
        produto das duas fatias — e é sobre esse produto que a repartição
        inteira é feita (`apportion`), não sobre cada eixo em separado: repartir
        eixo a eixo e cruzar depois não garante o produto.

        A repartição é a mesma em **toda geração**, e não uma só sobre a
        população inteira. Sem isso o perfil acabaria correlacionado com o
        período de ingresso — a geração 1 toda de um perfil, a 2 de outro —, e o
        recorte por geração passaria a medir perfil junto com senioridade.
        """
        combinations = [
            (aptitude, affinity)
            for aptitude in self.aptitude_profiles
            for affinity in self.affinity_profiles
        ]
        counts = apportion(
            self.students_per_period,
            [aptitude.share * affinity.share for aptitude, affinity in combinations],
        )
        return [
            combination
            for combination, count in zip(combinations, counts)
            for _ in range(count)
        ]

    def curriculum_periods(self) -> dict[str, int]:
        """O período de cada disciplina na grade, por indução sobre os
        pré-requisitos: sem pré-requisito é 1º período; com pré-requisitos é o
        maior período entre eles mais um.

        Substitui a senioridade s_x da eq. (38): o número não é dado, sai da
        estrutura da grade. Um ciclo de pré-requisitos não tem solução e é
        rejeitado aqui — é o único lugar em que a grade é percorrida inteira.
        """
        requires = {d.name: d.prerequisites for d in self.disciplines}
        period: dict[str, int] = {}
        # DFS iterativa com marcação de caminho: a recursiva estouraria a pilha
        # numa cadeia longa, e é o caminho aberto que denuncia o ciclo.
        on_path: set[str] = set()
        for start in requires:
            if start in period:
                continue
            stack = [(start, False)]
            while stack:
                name, expanded = stack.pop()
                if expanded:
                    on_path.discard(name)
                    period[name] = 1 + max((period[p] for p in requires[name]), default=0)
                    continue
                if name in period:
                    continue
                if name in on_path:
                    raise ValueError(
                        f"há um ciclo de pré-requisitos envolvendo {name!r}: a disciplina "
                        "nunca ficaria elegível"
                    )
                on_path.add(name)
                stack.append((name, True))
                stack.extend((p, False) for p in requires[name])
        return period

    def first_period_disciplines(self) -> list[str]:
        """As disciplinas sem pré-requisito, na ordem do cenário — a matrícula
        garantida de quem ingressa."""
        period = self.curriculum_periods()
        return [d.name for d in self.disciplines if period[d.name] == 1]

    def eligible_disciplines(self, approved: set[str]) -> list[str]:
        """Disciplinas que o aluno ainda precisa cursar e já pode disputar:
        não aprovadas e com todos os pré-requisitos cumpridos."""
        return [
            d.name
            for d in self.disciplines
            if d.name not in approved and all(p in approved for p in d.prerequisites)
        ]

    def hours_by_discipline(self) -> dict[str, int]:
        return {d.name: d.hours for d in self.disciplines}

    def hours_to_graduate(self) -> int:
        """S — a carga horária da grade inteira. Como toda disciplina é
        obrigatória, concluir é aprovar em todas, e a meta é a soma de w_x."""
        return sum(d.hours for d in self.disciplines)

    def minimum_periods_to_graduate(self) -> int:
        """Piso de períodos para concluir: nem quem nunca reprova nem perde uma
        vaga fecha a grade antes disso.

        São dois limites, e vale o maior. A **carga horária** impede cursar mais
        de W_a por período, o que dá ceil(S / W_a) — com o W_a mais folgado
        entre os perfis, porque o piso é o do aluno mais rápido possível. Os
        **pré-requisitos** impõem a cadeia: a disciplina de n-ésimo período não
        pode ser cursada antes do n-ésimo período do aluno.

        Serve para dimensionar a fase de drenagem: abaixo disso nenhuma geração
        tem tempo de chegar ao fim, e a série por geração mediria o horizonte em
        vez do mecanismo.
        """
        roomiest = max(p.max_hours for p in self.affinity_profiles)
        by_hours = -(-self.hours_to_graduate() // roomiest)
        by_chain = max(self.curriculum_periods().values(), default=0)
        return max(by_hours, by_chain)
