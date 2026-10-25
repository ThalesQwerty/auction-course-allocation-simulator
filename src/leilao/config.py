"""Configuração de um cenário de simulação (Seção 7.2 do anteprojeto).

O usuário descreve o cenário em dois blocos — parâmetros gerais e disciplinas —
e a simulação deriva o resto (alunos, nomes, matriz de utilidades, notas)
aleatoriamente a partir da `seed`.

**Não há perfis de aluno.** Toda a população sai das mesmas duas normais — a das
notas (a Beta da aptidão) e a das utilidades
(`utility_sigma`) —, e o que distingue um aluno do outro é só o que a seed
sorteou para ele. Os eixos de aptidão e afinidade existiram até
08/10/2026 e foram removidos a pedido: a heterogeneidade continua, mas deixa de
ser *sistemática*, e com ela sai o recorte dos relatórios por perfil.

Não há cursos: todo aluno é da universidade e cursa a mesma grade, e **toda
disciplina é obrigatória** — só se forma quem aprova em todas. O que ordena a
grade são os **sucessores** (`unlocks`): cada disciplina declara quais outras
ela desbloqueia. A **altura** s_x sai por indução nessa DAG — 0 se não
desbloqueia nada, senão 1 + max das alturas dos sucessores — e substitui a
senioridade da eq. (38) na invariante de preferência. O **período da grade**
(matrícula garantida, gráficos) continua contado a partir do ingresso, sobre a
aresta inversa: quem ninguém desbloqueia é 1º período.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Mecanismo de alocação. `credits` é o leilão por créditos proposto (Seção 7.1),
# em que o aluno reparte um orçamento entre lances e um PLI decide a alocação.
# `ranking` é a linha de base tradicional (Seção 7.3.1, eqs. 49-50): não há
# leilão nem PLI — as solicitações são atendidas em ordem decrescente do CR do
# aluno, e a carga horária faz o papel do orçamento.
Mechanism = Literal["credits", "ranking"]

# Quem decide a alocação, dada a mensagem dos alunos — o segundo eixo da
# comparação. Cruzado com `mechanism`, dá as quatro células:
#
#                  ordenação (guloso)            PLI (global)
#   CR        matrícula por CR (a linha      CR como peso num ótimo
#             de base brasileira)            global
#   lance     *bidding points* dos           o leilão do anteprojeto
#             business schools
#
# As duas células de fora da diagonal são mecanismos reais, não construções:
# o *bidding points* é o mais implantado do mundo. Os dois resolvedores só
# divergem onde a restrição de carga aperta — sem ela o problema se separa por
# disciplina e o guloso é ótimo —, então o eixo só tem conteúdo em cenário com
# conjunto elegível maior que W_a.
Resolver = Literal["ilp", "greedy"]

# Política de retorno de créditos f_gamma — eq. (34). O anteprojeto deixa a
# forma concreta em aberto e trata as políticas como eixo de experimentação
# (Seção 7.3.2) — as quatro comparadas estão em `grading.credit_return`.
CreditReturnPolicy = Literal["none", "unit", "full", "ratio"]

# Quanta memória o orçamento tem de um período para o outro — o eixo da ideia 1.
#
# `"none"`: o período começa sempre em Gamma_min. O leilão não tem memória
# nenhuma, e é o único braço em que o passado do aluno não entra no poder de
# compra dele por via alguma.
# `"carry"`: a eq. (36) — o que sobrou é carregado. Note que isso **não** é
# poupança: o aluno aposta o orçamento inteiro e paga o segundo preço, então o
# que sobra é o que ele não foi cobrado, não o que ele guardou.
#
# Cruzado com `credit_return`, dá a escada de três degraus: sem acúmulo
# ("none"), só sobra ("carry" + retorno "none") e sobra + retorno ("carry" +
# "ratio"). O degrau do meio separa as duas fontes de memória, que têm sinais
# opostos de incentivo: a sobra premia quem pagou barato, o retorno premia quem
# aprovou.
CreditMemory = Literal["none", "carry"]

@dataclass(frozen=True)
class Discipline:
    """Uma disciplina ofertada — o bem escasso x in B (Tabela 1).

    `unlocks` é a lista de sucessores. Vazia = terminal (altura 0). `entry`
    marca a matrícula garantida de quem ingressa; exige que a disciplina não
    tenha pré-requisito, e o inverso não vale.

    `elective` marca a **optativa**, e é ortogonal a `entry`: uma não implica a
    outra. A optativa não tem pré-requisito, não desbloqueia nada (`unlocks`
    vazia, altura 0) e não é de entrada. Concluir não exige aprovar em cada uma
    delas — exige somar `SimulationConfig.elective_hours` entre as que foram
    aprovadas, e é isso que as torna substituíveis entre si.

    As duas flags respondem perguntas diferentes sobre a mesma disciplina:
    `entry` é "o ingressante ganha esta de graça?"; `elective` é "ela conta
    individualmente para a conclusão, ou só pela carga?". Nenhuma das duas se
    deriva de não ter pré-requisito, que é o erro que a versão anterior
    cometia ao chamar de "1º período" o que era entrada.
    """

    name: str
    seats: int  # q_x — vagas
    hours: int  # w_x — carga horária
    # D_x — a dificuldade, lida em **quantas tentativas a disciplina custa**
    # para render o que uma de dificuldade 1 rende de primeira: na fórmula da
    # nota ela entra como a razão D/t, então D = 2 na 2ª tentativa equivale a
    # D = 1 na 1ª. Ela não precisa ser pública: o que o aluno lê é a taxa de
    # aprovação do período anterior, que é D filtrada pela população.
    difficulty: float = 1.0
    unlocks: tuple[str, ...] = ()
    entry: bool = False
    elective: bool = False
    # Quanto do gosto por esta disciplina é permanente, de 0 a 1. `None` cai no
    # valor do cenário. Declarar por disciplina é o que **sincroniza** a
    # persistência entre concorrentes — se todos que querem uma disciplina
    # continuam querendo ao mesmo tempo, a disputa por ela congela inteira em
    # vez de girar, e é essa sincronia (e não a persistência em si) que trava a
    # fila. Por aluno ou por célula o efeito se dilui.
    stability: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("disciplina sem nome")
        if self.seats < 0:
            raise ValueError(f"disciplina {self.name!r}: vagas (q_x) deve ser >= 0")
        if self.hours <= 0:
            raise ValueError(f"disciplina {self.name!r}: carga horária (w_x) deve ser > 0")
        if self.difficulty <= 0:
            raise ValueError(f"disciplina {self.name!r}: dificuldade deve ser > 0")
        if self.stability is not None and not 0.0 <= self.stability <= 1.0:
            raise ValueError(
                f"disciplina {self.name!r}: a estabilidade deve estar em [0, 1]"
            )
        if self.name in self.unlocks:
            raise ValueError(f"disciplina {self.name!r} é sucessora de si mesma")
        if len(set(self.unlocks)) != len(self.unlocks):
            raise ValueError(f"disciplina {self.name!r}: sucessores repetidos")
        if self.elective and self.unlocks:
            raise ValueError(
                f"optativa {self.name!r} não pode desbloquear nada: a cadeia passaria "
                "a depender de uma disciplina que ninguém é obrigado a cursar"
            )
        if self.elective and self.entry:
            raise ValueError(
                f"optativa {self.name!r} não pode ser de entrada: a matrícula garantida "
                "entregaria parte da exigência em horas antes de o aluno disputar nada"
            )


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
    # tem vaga garantida nas disciplinas de entrada, então o ritmo de entrada
    # não pode passar da menor oferta entre elas — senão a garantia não caberia.
    # A população é este número vezes L.
    students_per_period: int = 1
    # --- as duas distribuições que descrevem um aluno -----------------------
    #
    # Todo aluno é igual a todos os outros *em distribuição*: não há mais perfis,
    # e o que o distingue dos colegas é só o que saiu da seed para ele. São duas
    # distribuições, e nenhuma delas consta no anteprojeto.
    #
    # **Notas**: a nota sai da aptidão elevada à demanda da disciplina — ver
    # `grading`. A aptidão de cada par (aluno, disciplina) vem de uma Beta,
    # sorteada uma vez e persistente: é traço, não sorte.
    #
    # **Beta(4, 2)** é a calibragem contra o modelo que ela substitui: média
    # 0,67 (nota 6,7, contra 6,5 da normal antiga) e 82% de aprovação numa
    # disciplina de dificuldade 1 (contra ~84%). Sem isso a população fica
    # boa demais, ninguém reprova e a recursada some do cenário.
    aptitude_alpha: float = 4.0
    aptitude_beta: float = 2.0
    # O quanto o interesse mexe no desempenho, como expoente sobre u_rel.
    # **Padrão 0: desligado.** É a única peça da fórmula de nota sem forma
    # justificada, e a única que mexe no resultado principal — em 1 ela
    # fabrica sozinha ~40% de vão em aprovações a favor do lance. Em zero a
    # função de nota é neutra entre os mecanismos, e qualquer vão em conclusões
    # é do modelo, inteiro. Reportá-lo ao lado do resultado é o que
    # transforma a suposição em número declarado.
    interest_coupling: float = 0.0
    # O desvio do choque log-normal sobre o expoente, por tentativa. Sem ele a
    # nota seria exata e recursar garantiria nota maior.
    grade_noise: float = 0.25
    # Quanto do gosto do aluno é **permanente**, de 0 a 1 — a fração da
    # variância que não é resorteada a cada período.
    #
    # 0 é o que o modelo fazia antes: a preferência inteira recomeça todo
    # semestre, e o que o aluno quis no passado não diz nada sobre o que quer
    # agora. 1 congela a linha dele para o curso inteiro. No meio, cada
    # semestre é o gosto permanente mais um chacoalhão — o horário, quem dá a
    # disciplina, quanto ele está sobrecarregado.
    #
    # Ela é **ortogonal ao sigma**: a divisão preserva a variância, então cada
    # período continua tendo exatamente a mesma dispersão qualquer que seja
    # este valor. O que muda é só a correlação entre semestres, que é
    # literalmente este número.
    #
    # **Padrão 0**, que reproduz o modelo anterior. Como ela é a hipótese mais
    # exposta que resta — é o valor que mais protege o lado fraco da tese, já
    # que a preferência que não persiste desfaz a fila sozinha —, qualquer
    # resultado em conclusões deveria vir com o valor dela declarado.
    utility_stability: float = 0.0
    # **Utilidades** (u, eqs. 41-43): o desvio da log-normal de onde saem os
    # valores preliminares, antes da normalização de `behavior.draw_utilities`.
    # É o único parâmetro: a média do logaritmo é fixa em 0 porque some na
    # normalização (deslocá-la multiplica a linha inteira por uma constante).
    #
    # sigma diz o quanto o aluno diferencia uma disciplina da outra — **grande
    # concentra, pequeno achata**, ao contrário da forma da Gamma que havia
    # antes. O coeficiente de variação é sqrt(exp(sigma^2) - 1), que cresce
    # depressa: a faixa útil inteira cabe entre ~0,25 e ~3.
    #
    # Depois do sorteio, `draw_utilities` impõe a invariante de altura:
    # s_x > s_y ⇒ u_x > u_y. O sigma continua mandando *dentro* da mesma altura.
    utility_sigma: float = 1.0
    # W_a — carga horária máxima por período, eq. (4). Igual para todos.
    max_hours: int = 360
    rounds: int = 1  # |R| — rodadas de alocação por período
    min_grade: float = 5.0  # n_min — nota mínima de aprovação
    # X — carga horária optativa exigida para concluir, somada entre as
    # optativas aprovadas. Concluir é aprovar em **todas** as obrigatórias e
    # chegar a este total nas optativas (eq. 40 estendida). O aluno escolhe
    # *quais*, e é essa substituibilidade — "qualquer X horas serve" — que a
    # ordenação por CR não consegue capturar e o lance consegue.
    elective_hours: int = 0
    # Os dois parâmetros abaixo são do leilão por créditos e **não têm efeito**
    # com `mechanism="ranking"`: ali não há orçamento a repor nem preço pago a
    # devolver. Ficam no cenário assim mesmo porque a comparação entre os dois
    # mecanismos roda a mesma configuração nos dois lados.
    base_credits: int = 10  # Gamma_min — créditos base por período, eq. (35)/(37)
    credit_return: CreditReturnPolicy = "none"
    credit_memory: CreditMemory = "carry"
    mechanism: Mechanism = "credits"
    resolver: Resolver = "ilp"
    seed: int = 0

    @property
    def uses_credits(self) -> bool:
        """Se o crédito existe neste cenário. Na linha de base por CR ele não
        existe — e as grandezas de crédito saem `None` nos relatórios, não zero:
        zero se leria como "ninguém gastou", e o certo é "não há o que gastar".
        """
        return self.mechanism == "credits"

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
        if self.aptitude_alpha <= 0 or self.aptitude_beta <= 0:
            raise ValueError("os parâmetros da Beta da aptidão devem ser > 0")
        if self.interest_coupling < 0:
            raise ValueError("o acoplamento interesse-desempenho deve ser >= 0")
        if self.grade_noise < 0:
            raise ValueError("o desvio do choque de nota deve ser >= 0")
        if not 0.0 <= self.utility_stability <= 1.0:
            raise ValueError("a estabilidade da preferência deve estar em [0, 1]")
        if self.utility_sigma <= 0:
            raise ValueError("desvio da utilidade (sigma) deve ser > 0")
        if self.max_hours < 1:
            raise ValueError("carga horária máxima (W_a) deve ser >= 1")

        names = [d.name for d in self.disciplines]
        if len(set(names)) != len(names):
            raise ValueError("há disciplinas com nomes repetidos")
        known = set(names)
        for discipline in self.disciplines:
            unknown = set(discipline.unlocks) - known
            if unknown:
                raise ValueError(
                    f"disciplina {discipline.name!r} tem sucessores inexistentes: "
                    f"{sorted(unknown)}"
                )

        # Ciclo: a cadeia que se fecha não tem altura nem período.
        self.heights()
        requires = self.prerequisites_by_discipline()
        for discipline in self.disciplines:
            if discipline.entry and requires[discipline.name]:
                raise ValueError(
                    f"disciplina {discipline.name!r} é de entrada e tem pré-requisitos"
                )
            # A optativa existe para estar sempre ao alcance; um pré-requisito
            # a tiraria do elegível justamente de quem está atrasado. O outro
            # sentido — optativa não desbloqueia nada — é checado na própria
            # `Discipline`, que já enxerga os `unlocks` dela.
            if discipline.elective and requires[discipline.name]:
                raise ValueError(
                    f"optativa {discipline.name!r} não pode ter pré-requisito: "
                    f"{sorted(requires[discipline.name])} a desbloqueia"
                )
        entry = self.entry_disciplines()
        if not entry:
            raise ValueError("o cenário precisa de pelo menos uma disciplina de entrada")

        if self.elective_hours < 0:
            raise ValueError("elective_hours (X) deve ser >= 0")
        offered = sum(d.hours for d in self.disciplines if d.elective)
        if self.elective_hours > offered:
            raise ValueError(
                f"a exigência de {self.elective_hours} h optativas não cabe nas "
                f"{offered} h ofertadas em optativas: ninguém concluiria"
            )

        seats = {d.name: d.seats for d in self.disciplines}
        hours = {d.name: d.hours for d in self.disciplines}
        smallest = min(seats[name] for name in entry)
        if self.students_per_period > smallest:
            tightest = min(entry, key=lambda name: (seats[name], name))
            raise ValueError(
                f"alunos por período ({self.students_per_period}) passa da menor oferta "
                f"entre as disciplinas de entrada ({smallest} vagas em {tightest!r}): "
                "o ingressante tem vaga garantida em todas elas"
            )
        entry_hours = sum(hours[name] for name in entry)
        if entry_hours > self.max_hours:
            raise ValueError(
                f"as {len(entry)} disciplinas de entrada somam {entry_hours} h e não "
                f"cabem na carga horária máxima (W_a = {self.max_hours}) — eq. (4); o "
                "ingressante cursa todas elas de uma vez"
            )

    @property
    def entry_span(self) -> int:
        """L — quantos períodos recebem geração nova, resolvido o `None`."""
        return self.periods if self.entry_periods is None else self.entry_periods

    def total_students(self) -> int:
        """|A| — uma geração do mesmo tamanho em cada um dos L períodos."""
        return self.students_per_period * self.entry_span

    def prerequisites_by_discipline(self) -> dict[str, tuple[str, ...]]:
        """Aresta inversa dos sucessores: quem precisa estar aprovado para
        disputar cada disciplina. Mantém a ordem do cenário entre os
        predecessores."""
        preds: dict[str, list[str]] = {d.name: [] for d in self.disciplines}
        for discipline in self.disciplines:
            for successor in discipline.unlocks:
                preds[successor].append(discipline.name)
        return {name: tuple(parents) for name, parents in preds.items()}

    def heights(self) -> dict[str, int]:
        """Altura s_x na DAG de sucessores: 0 se não desbloqueia nada; senão
        1 + max das alturas dos sucessores. Ciclo é rejeitado — a disciplina
        nunca ficaria elegível."""
        unlocks = {d.name: d.unlocks for d in self.disciplines}
        height: dict[str, int] = {}
        on_path: set[str] = set()
        for start in unlocks:
            if start in height:
                continue
            stack = [(start, False)]
            while stack:
                name, expanded = stack.pop()
                if expanded:
                    on_path.discard(name)
                    height[name] = 1 + max((height[s] for s in unlocks[name]), default=-1)
                    continue
                if name in height:
                    continue
                if name in on_path:
                    raise ValueError(
                        f"há um ciclo de sucessores envolvendo {name!r}: a disciplina "
                        "nunca ficaria elegível"
                    )
                on_path.add(name)
                stack.append((name, True))
                stack.extend((s, False) for s in unlocks[name])
        return height

    def curriculum_periods(self) -> dict[str, int]:
        """O período de cada disciplina na grade, por indução sobre a aresta
        inversa dos sucessores: quem ninguém desbloqueia é 1º período; quem é
        desbloqueada por outras é o período seguinte ao mais tardio delas.

        Contagem a partir das raízes, usada nos gráficos. A matrícula garantida
        é `entry`, não este período. A altura (s_x) conta do outro extremo.
        """
        requires = self.prerequisites_by_discipline()
        period: dict[str, int] = {}
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
                        f"há um ciclo de sucessores envolvendo {name!r}: a disciplina "
                        "nunca ficaria elegível"
                    )
                on_path.add(name)
                stack.append((name, True))
                stack.extend((p, False) for p in requires[name])
        return period

    def reach(self) -> dict[str, int]:
        """Quantas disciplinas cada uma desbloqueia, **transitivamente** — o
        "quanto avanço se passar" do termo de progresso.

        Não é a altura: altura é o comprimento da cadeia mais longa à frente,
        alcance é o tamanho do que fica para trás destravado. Uma disciplina
        pode ter altura 1 e alcance 10 se destrava dez terminais de uma vez, e
        o que interessa ao aluno que quer avançar é o alcance.
        """
        unlocks = {d.name: d.unlocks for d in self.disciplines}
        memo: dict[str, set[str]] = {}

        def descend(name: str) -> set[str]:
            if name in memo:
                return memo[name]
            memo[name] = set()  # corta ciclo; a validação já o rejeita
            out: set[str] = set()
            for successor in unlocks.get(name, ()):
                out.add(successor)
                out |= descend(successor)
            memo[name] = out
            return out

        return {name: len(descend(name)) for name in unlocks}

    def entry_disciplines(self) -> list[str]:
        """Disciplinas de matrícula garantida, na ordem do cenário.

        Vem da flag `entry`, e **não** de não ter pré-requisito: a optativa
        também não tem e não é entrada. É este conjunto que dimensiona as
        validações de `students_per_period` e `max_hours` — o que a oferta
        precisa comportar é a geração inteira entrando de uma vez.
        """
        return [d.name for d in self.disciplines if d.entry]

    def eligible_disciplines(self, approved: set[str]) -> list[str]:
        """Disciplinas que o aluno ainda precisa cursar e já pode disputar:
        não aprovadas, com todos os predecessores (aresta inversa) cumpridos,
        e — no caso da optativa — **enquanto a exigência X não estiver
        cumprida**.

        O teto nas optativas não é detalhe de calibragem, é o que faz `X`
        significar alguma coisa. Sem ele a optativa fica elegível para sempre
        (nunca aprovada, sem pré-requisito), o aluno continua apostando nela
        por utilidade, e medindo-se o cenário quem conclui tinha aprovado o
        catálogo **inteiro**: 1 560 h de optativa onde 480 h eram exigidas.
        A exigência não restringia nada e a substituibilidade — escolher
        *quais* optativas — nunca chegava a ser exercida.

        Com `elective_hours = 0` nenhuma optativa é elegível, o que é a leitura
        consistente: sem exigência, elas não contam para coisa alguma.
        """
        requires = self.prerequisites_by_discipline()
        met = (
            sum(d.hours for d in self.disciplines if d.elective and d.name in approved)
            >= self.elective_hours
        )
        return [
            d.name
            for d in self.disciplines
            if d.name not in approved
            and all(p in approved for p in requires[d.name])
            and not (d.elective and met)
        ]

    def hours_by_discipline(self) -> dict[str, int]:
        return {d.name: d.hours for d in self.disciplines}

    def required_disciplines(self) -> set[str]:
        """As obrigatórias — o que a eq. (40) exige aprovar uma a uma."""
        return {d.name for d in self.disciplines if not d.elective}

    def elective_hours_by_discipline(self) -> dict[str, int]:
        """Carga de cada optativa, para somar o que o aluno já cumpriu de X."""
        return {d.name: d.hours for d in self.disciplines if d.elective}

    def hours_to_graduate(self) -> int:
        """S — a carga horária mínima para concluir: a soma de w_x de **todas
        as obrigatórias** mais a exigência optativa X.

        Não é a carga da grade inteira desde que há optativa: o catálogo delas
        é maior que a exigência de propósito, e é essa folga que dá ao aluno o
        que escolher.
        """
        required = sum(d.hours for d in self.disciplines if not d.elective)
        return required + self.elective_hours

    def minimum_periods_to_graduate(self) -> int:
        """Piso de períodos para concluir: nem quem nunca reprova nem perde uma
        vaga fecha a grade antes disso.

        São dois limites, e vale o maior. A **carga horária** impede cursar mais
        de W_a por período, o que dá ceil(S / W_a). A **cadeia** impõe que a
        disciplina de n-ésimo período não pode ser cursada antes do n-ésimo
        período do aluno.

        Serve para dimensionar a fase de drenagem: abaixo disso nenhuma geração
        tem tempo de chegar ao fim, e a série por geração mediria o horizonte em
        vez do mecanismo.
        """
        by_hours = -(-self.hours_to_graduate() // self.max_hours)
        by_chain = max(self.curriculum_periods().values(), default=0)
        return max(by_hours, by_chain)
