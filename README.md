# Simulador — Leilão por Créditos

Motor de simulação e interface de configuração para o TCC *"Modelagem e
simulação computacional de mecanismos de leilão por créditos aplicadas à
matrícula universitária"* (UFBA, 2026).

## O que o simulador faz

Simula a matrícula de uma universidade inteira ao longo de vários períodos
letivos: o usuário configura a grade de disciplinas e a população, e a
simulação gera os alunos (nome, interesse, notas) a partir de uma seed, roda
as rodadas de alocação de cada período e devolve as métricas de eficiência,
equidade e correlação da Seção 7.3.

São **dois mecanismos de alocação** sobre o mesmo modelo de universidade: o
**leilão por créditos** proposto (Seção 7.1) e a **ordenação por CR** que serve
de linha de base (Seção 7.3.1, eqs. 49-50). A **comparação** roda o mesmo
cenário em cada **braço**, N vezes, e mostra as métricas de alocação período a
período, recortadas por coorte ou por um dos quatro eixos de perfil.

São **três braços**, e o leilão entra em dois deles:

    CR  ──mensagem──▶  Bidding points  ──resolução──▶  Leilão igualitário
                                                   ──acúmulo──▶  Leilão acumulativo

- **Ordenação por CR** — a linha de base. Traçado **pontilhado** nos gráficos.
- **Leilão igualitário** — o leilão com orçamento fixo: todo aluno abre todo
  período com `C_min`, nada atravessa o período e o retorno fica desligado
  (`k = 0`). Traçado **tracejado**.
- **Leilão acumulativo** — o modelo proposto: o saldo atravessa o período
  (eq. 36) e o f_γ da eq. (34) o alimenta. Traçado **contínuo**.

Os dois leilões são o **mesmo** mecanismo — mesma moeda, mesmo resolvedor,
mesmo segundo preço — e diferem só em de onde vem o orçamento. Com eles o vão
se lê em duas parcelas em vez de uma: CR × igualitário diz o que a **moeda**
compra, igualitário × acumulativo diz o que o **acúmulo** compra.

A **mensagem** é um número por *aluno* (o CR) contra um por *par* aluno-disciplina
(o lance). A **resolução** é ordinal (só a ordem dos lances importa; qualquer
transformação monótona dá a mesma alocação) contra cardinal (a PLI usa as
magnitudes e derruba um lance alto para acomodar dois médios). O **acúmulo** é
a memória do orçamento com o f_γ que a alimenta, a única fonte de mérito do
leilão.

Entre o CR e o leilão igualitário ainda há duas mudanças somadas — a mensagem
e a resolução —, e o degrau que as separa continua no motor, em
`comparison.ABLATION_ARMS`, rodando por `run_comparison(..., arms=ARMS +
ABLATION_ARMS)`: custa tempo de execução e não complexidade conceitual — é a
mesma simulação com um campo trocado. Ele é o *bidding points* clássico das
business schools —
orçamento de pontos, lances por disciplina, disciplina fechando no menor lance
atendido (Sönmez & Ünver 2010, sobre Michigan e Yale SOM). Não confundir com o
**Course Match** de Wharton, que substituiu o bidding points de lá: aquele
também é cardinal e resolve por MIP, mas é outro mecanismo — preferências sobre
*cestas*, orçamentos aproximadamente iguais e preços de equilíbrio. É trabalho
relacionado, não célula deste desenho.

Não há cursos: todo aluno é da universidade e cursa a mesma grade, e **toda
disciplina é obrigatória** — conclui quem aprova em todas. O que ordena a grade
são os **pré-requisitos**, e o período de cada disciplina sai deles por indução:
sem pré-requisito é 1º período, com pré-requisitos é o período seguinte ao mais
tardio deles.

**O bem alocado é a turma.** A disciplina declara quantas oferece, a oferta
dela é repartida entre essas turmas, e a disciplina passa a ser o **clique**
do grafo de conflito: o único critério de conflito na simulação é serem duas
turmas da mesma disciplina, e ninguém leva duas (eq. 5). Com uma turma por
disciplina — o padrão — o nome da turma é o da disciplina, não há clique
nenhum a impor e o modelo é exatamente o de antes de elas existirem.

A divisão de trabalho é: a **turma** tem vaga, preço, demanda e dificuldade; a
**disciplina** tem nota, tentativa, pré-requisito e conclusão. O aluno não
fica melhor por trocar de seção — o quantil de desempenho dele é na matéria —,
e o que a turma move é a distribuição sob esse quantil.

```
Simulador/
├── src/leilao/
│   ├── equations/        # UMA fórmula por arquivo, uma função pura por fórmula
│   ├── entities.py       # Problema central P = (A, B, D, p, q, w, W, X) — Seção 3
│   ├── wdp_solver.py     # Os dois resolvedores: PLI exata e varredura gulosa
│   ├── auction.py        # Uma rodada do leilão por créditos — Seção 7.1
│   ├── ranking.py        # Linha de base por CR — Seção 7.3.1
│   ├── config.py         # Cenário: geral, grade, pré-requisitos e as duas distribuições
│   ├── names.py          # 256 nomes x 256 sobrenomes para batizar os alunos
│   ├── population.py     # Alunos e seu histórico acadêmico
│   ├── behavior.py       # Sorteio do interesse e a utilidade que sai dele
│   ├── grading.py        # Sorteio do desempenho base
│   ├── availability.py   # Sorteio da disponibilidade (horas), uma por período
│   ├── metrics.py        # O registro de métricas de um recorte
│   ├── simulation/       # O laço multi-período — Seção 7.2
│   ├── comparison.py     # N simulações pareadas de cada braço — Seção 7.3
│   ├── api/storage.py    # Grava a execução em disco, no formato do histórico
│   ├── playground.py     # Uma alocação isolada, sem períodos
│   └── api/              # Ponte FastAPI (sem persistência — stateless)
├── tests/                # pytest (motor + simulação + API)
├── examples/             # Script de exemplo executável
└── web/src/
    ├── equations/        # O espelho das fórmulas no navegador
    ├── charts/           # Tema, formatos e as marcas (séries, densidade, histograma)
    ├── App.tsx           # Shell: barra lateral, navegação e histórico
    ├── Sidebar.tsx       # Menu, lista de execuções e limpeza do histórico
    ├── Config.tsx        # Formulário do cenário, com as três prévias
    ├── ProfileList.tsx   # Editor dos perfis de um eixo: criar, mexer, remover
    ├── SaveScenario.tsx  # Salvar o cenário atual, na barra de ações
    ├── PresetList.tsx    # Barra lateral direita: cenários prontos e salvos
    ├── presets.ts        # A grade, o cenário padrão e a regra de seleção
    ├── savedPresets.ts   # Cenários do usuário, em localStorage
    ├── curriculum.ts     # Migração da grade e os recortes que as telas usam
    ├── distributions.ts  # Encadeia as equações nas duas curvas de prévia
    ├── GradeGraph.tsx    # A grade desenhada, com a cadeia de pré-requisitos
    ├── Playground.tsx    # A decisão de um aluno, passo a passo
    ├── Project.tsx       # Visão teórica do projeto
    ├── Comparison.tsx    # Séries (régua × recorte) e tabelas de uma comparação
    ├── Trace.tsx         # O caso individual: um aluno ou uma disciplina, rodada a rodada
    ├── history.ts        # Histórico de execuções: formato, migrações e leitura
    └── historyStore.ts   # Onde o histórico mora: IndexedDB
```

**Onde ficam as contas.** Nenhuma fórmula do modelo mora dentro de um laço:
cada uma tem arquivo e função própria em `src/leilao/equations/`, com a
fórmula na docstring e nada de estado. O `__init__.py` do pacote traz o
índice inteiro, com o número da equação do anteprojeto onde a correspondência
ainda vale — e com o que o código mudou em relação a ele. O front tem o seu
espelho em `web/src/equations/`, pelas contas que a prévia precisa fazer
antes de existir execução a quem perguntar.

**Front-end (TypeScript) → API (FastAPI/Python) → Motor (Python)**: a
interface monta a configuração inteira no navegador e manda para `/compare`,
que roda o cenário em cada braço, N vezes, e devolve os resumos pareados. Não
há banco de dados — cada execução é independente e reprodutível pela seed.

O detalhe de **uma** das simulações fica numa rota à parte, `/trace`: o mesmo
cenário mais o par (braço, seed) que a endereça, e de volta o que cada aluno
pediu em cada rodada. Ele é pedido sob demanda porque é a resposta grande da
API — uns 10 MB contra uns 450 kB do resumo —, e refazer a simulação é legítimo
porque ela é determinística: a mesma configuração dá a mesma execução.

## Como a simulação funciona

Para cada período letivo `t`:

1. Quem ingressa em `t` recebe **vaga garantida** em todas as disciplinas de
   1º período, e essas vagas saem do estoque antes de o leilão abrir. O calouro
   não escolhe turma: a coorte é repartida entre as turmas de cada disciplina
   de entrada em blocos contíguos (`equations.entry_class`), os primeiros na
   primeira turma e assim por diante.
2. Cada aluno ativo converte sua linha de **interesse** `i^(t)` — já sorteada
   na inicialização — em **utilidade** `U^(t)` sobre o seu **conjunto
   elegível**: as disciplinas que ainda não aprovou e cujos pré-requisitos já
   cumpriu (eqs. 41-43). Fora dele a utilidade é zero; a elegível vale a média
   das turmas dela mais o que ela destrava um período à frente, e a linha é
   normalizada para somar 1 sobre as disciplinas. O interesse não muda dentro
   do laço: é sorteado uma vez só, para a simulação inteira.
3. Para cada rodada `r`, os lances saem deterministicamente das utilidades
   (mochila côncava **em dois níveis**: entre disciplinas, depois entre as
   turmas de cada uma), o leilão resolve o WDP por PLI (eqs. 22-25) — com as
   restrições de clique que impedem duas turmas da mesma disciplina e duas
   turmas no mesmo horário (eq. 5) — e vagas, carga horária e orçamento são
   descontados (eqs. 13, 14, 27).
4. Encerradas as rodadas, o aluno **exclui**: descarta disciplinas obtidas
   até que a carga retida caiba nas horas que a disponibilidade
   daquele período lhe deu (`equations.retained_set`). A vaga descartada
   **não volta** para a oferta — a esta altura as alocações já se encerraram.
5. Só então saem as notas do que ficou (eq. 33), o retorno de créditos
   (eqs. 34-36) e as conclusões de curso (eq. 40). Aqui a turma **colapsa na
   disciplina**: a tentativa, a nota e a aprovação são do histórico, e a
   dificuldade, que move a distribuição sob o quantil do aluno, é da
   disciplina — toda turma dela a herda.

Tudo que é aleatório vem da `seed` e é sorteado **na inicialização**, antes do
primeiro período — nada é sorteado dentro do loop, como exige a Seção 7.3:

| Matriz | O que é | Onde |
| --- | --- | --- |
| `q` | quantil de desempenho de cada par (aluno, disciplina), persistente | `grading.draw_base_quantiles` |
| `δ^(t)` | disponibilidade em horas de cada par (aluno, período) | `availability.draw_availability` |
| `i^(t)` | interesse de cada par (aluno, turma) em cada período | `behavior.draw_interest` |
| `epsilon` | perturbação estocástica, uma por par (aluno, disciplina) | `simulation.setup` |

Três coisas **não** vêm da seed, de propósito: o período de ingresso `t_a`, a
combinação de perfis e a turma de entrada do calouro. As coortes têm todas o mesmo tamanho, em períodos consecutivos,
e os perfis se repartem igualmente entre as combinações
(`population.generate_students`), com a turma de entrada saindo da posição do
aluno na coorte — assim duas simulações que só diferem na seed
têm a mesma estrutura de entrada e os mesmos grupos, e a diferença entre elas
não é quem entrou quando nem quem calhou de ser frágil. Da seed vêm os
escalares que as distribuições dos perfis produzem, não o grupo.

**A nota não é sorteada: é lida.** O único sorteio é o do **quantil** `q` do
par (aluno, disciplina) — um uniforme em (0, 1), feito uma vez na
inicialização. A posição é o traço; a distribuição é que se move.

A distribuição é uma **normal dividida censurada em [0, 10]**: dois desvios em
torno de uma moda comum, à esquerda e à direita. O perfil a descreve pelas três
grandezas que se leem — **nota mais provável, chance de tirar 0 e chance de
tirar 10** — e `equations.grade_shape` converte isso nos três parâmetros de
forma. A moda é a locação, e o número declarado é literalmente o pico da curva;
a chance de zero fixa a cauda esquerda e a de dez fixa a direita. Como a moda
entra direto, **toda trinca existe** — não há combinação a recusar, o que não
valeria se o parâmetro fosse a média.

A **média sai derivada**, e fica 1 a 2 pontos *abaixo* da moda: a cauda
esquerda é longa (quem vai mal vai muito mal), e numa distribuição assim a
média não coincide com o pico.

A nota de uma tentativa é o quantil lido nessa distribuição, **arredondado em
décimos e clipado em [0, 10]** — `equations.grade_for_attempt`. O latente é
ilimitado; o que limita é o instrumento: a prova vale 10, então quem mereceria
11 recebe 10. É essa censura que torna o 0 e o 10 alcançáveis, e com a
frequência que o perfil declarou.

A dificuldade e a tentativa transformam as duas chances por expoentes
**recíprocos** (`equations.attempt_rates`):

    chance de 0  = chance_base ^ (tentativa / dificuldade)
    chance de 10 = chance_base ^ (dificuldade / tentativa)

e a forma é refeita com a **moda do perfil mantida**. Segurar a moda, e não a
média, é o que a mantém dentro da escala: com a média fixa ela sai de [0, 10]
assim que a dificuldade passa de 2.

Três consequências. A recursada rende pela **lei de potência da prática**:
dificuldade 2 na segunda tentativa reproduz exatamente dificuldade 1 na
primeira — e é por isso que não há botão de ganho por recursada, já que quem
calibra isso é a dificuldade da disciplina, do outro lado da mesma razão. A
**taxa de aprovação não é parâmetro**: `n_min` é regra de cenário, não
propriedade do aluno, e se definisse o perfil mudar a linha de corte
redefiniria a população em silêncio — ela sai calculada. E `Student.grades`
guarda a **maior** nota já obtida
— é ela que conta para o CR e para a aprovação —, enquanto o histórico por
período guarda a nota **daquela** tentativa, que é o que a tela individual
precisa mostrar.

Disciplina **excluída não tem nota**: o aluno obteve a vaga e não cursou, então
ela não entra no histograma, nem no CR, nem na média de notas — e não gasta
tentativa. Quem exclui e refaz no semestre seguinte volta como primeira
tentativa, sem o ganho de recursada.

### Interesse e utilidade

São duas palavras para dois objetos, e a fronteira entre eles é o **histórico
do aluno**:

| | O que é | Soma | Depende do histórico | Quando |
| --- | --- | --- | --- | --- |
| **interesse** `i` | o sorteio normalizado: o quanto o aluno quer cada turma | 1 sobre as turmas todas | não | sorteado na inicialização, nunca mais tocado |
| **utilidade** `U` | o que a disciplina elegível vale, com o que ela destrava | 1 sobre as disciplinas elegíveis | sim | recalculada a cada período |

As três fórmulas estão em `equations.utility`:

    I_{a,X} = (1/|X|) · Σ_{x ∈ X} i_{a,x}

                I_{a,X} + Σ_{Y ∈ seq(X)} I_{a,Y} / |M_a ∩ req(Y)|
    U_{a,X} = ───────────────────────────────────────────────────
                     Σ_{Z ∈ M_a ∪ seq(M_a)} I_{a,Z}

    u_{a,x} = U_{a,X} · i_{a,x} / max_{y ∈ X} i_{a,y}

A **disciplina vale a média das turmas dela**, não o máximo: quanto a matéria
vale para o aluno não depende de quantas seções a universidade abriu, e a
média é a única estatística que não se move ao abrir uma turma a mais. Na
volta, a turma vale a fatia da disciplina na proporção em que o aluno a
prefere — de modo que **a melhor turma de cada disciplina vale exatamente
`U_{a,X}`** e as irmãs valem menos.

**A herança é de um nível.** A elegível acumula o interesse do que ela
destrava **imediatamente**, um período à frente, e a parcela de `Y` se reparte
entre os pré-requisitos de `Y` que estão elegíveis agora. Como o pré-requisito
é conjuntivo, cada porteira é igualmente necessária, e repartir é o que impede
que destravar `Y` seja contado uma vez por porteira. O aluno olha o próximo
passo: querer o que vem depois de amanhã não é previsão que ele faça, e
cascatear a grade inteira faria toda porteira da raiz herdar o curso todo.

A porteira continua valendo mais que a terminal, mas **porque acumulou o
interesse do que destrava**, e não porque uma desigualdade o impôs — era isso
que a invariante de altura da eq. (41) fazia.

**`Σ_{X ∈ M_a} U_{a,X} = 1`, e isso é aritmética, não calibragem.** O
numerador somado sobre `M_a` conta cada `I_{a,Y}` de um sucessor exatamente
`|M_a ∩ req(Y)|` vezes, uma por porteira elegível, e as frações se recompõem
inteiras; sobra o próprio denominador. A união é **disjunta**: se `Y` é
sucessor de um elegível `X`, então `X` é pré-requisito não aprovado de `Y`, e
`Y` não é elegível.

A consequência é que **ψ dispensa denominador** (`equations.satisfaction`): a
soma do que o aluno poderia levar, uma turma por disciplina, é 1 por
construção, e ψ volta a ser a soma simples das utilidades atendidas. O `U_a`
da eq. (43) saiu de cena, e com ele o `reachable_utility`. O teto 1 é
**atingível**: o ingressante que recebe a matrícula garantida inteira num
cenário sem optativa marca exatamente 1.

O que fica **fora** da conta: a disciplina já aprovada, a optativa que a cota
dispensou e tudo que está a dois ou mais níveis de distância. O interesse
delas não é redistribuído — ele simplesmente não entra, e o denominador o
ignora. É a diferença entre esta regra e a **redistribuição** que existiu até
16/11/2026, que conservava a massa da linha inteira espalhando o inelegível
sobre o elegível.

**A decisão vê utilidade, nunca interesse.** Lance, pedido, reserva e ψ leem a
saída de `utility_matrix`, o único ponto onde um vira o outro. O interesse cru
só aparece em relatório — o histograma do cenário.

A terceira linha da tabela abaixo é o `available_goods` (eq. 15): filtro do
que se pode pedir *nesta rodada*, não afirmação sobre valor — o aluno continua
querendo a disciplina que lotou.

| Não pode cursar porque… | Utilidade |
| --- | --- |
| travada por pré-requisito | zero; o interesse dela desce para as porteiras elegíveis, se ela estiver a um nível |
| fora da grade dele (aprovada, ou optativa dispensada pela cota) | zero, e o interesse não vai para lugar nenhum |
| sem vaga, carga não cabe, já conquistada na rodada, **ou conflita com uma já conquistada** | inalterada |

#### O sorteio do interesse

O interesse é sorteado como **uma linha por (aluno, período)**, sobre as
**turmas**, em dois passos:

1. Um valor por par (aluno, turma), tirado de uma **log-normal** de média
   logarítmica `interest_mean + ln(peso do turno)` e desvio `interest_sigma`.
2. **Divisão pelo somatório**, que faz a linha valer 1 sobre as turmas todas.

O passo 1 é composto em **dois níveis**: um valor da disciplina, comum às
turmas dela, mais um desvio por turma, repartidos por `class_stability` com
pesos `√s` e `√(1−s)` — a mesma repartição que `interest_stability` faz no
tempo, e que preserva σ. Em `class_stability = 1` não há desvio a sortear e
todas as turmas de uma disciplina valem o mesmo; em 0 cada uma tem valor
próprio. O desvio da turma passa pela **mesma** repartição temporal da
disciplina, de modo que estabilidade entre períodos igual a 1 congela também
as turmas.

Baixar a estabilidade entre turmas **alarga** a distribuição do interesse sem
que ninguém tenha mexido em σ, e não é defeito: normalizar subtrai `log(Σ)` da
linha inteira, e quanto mais correlacionadas as entradas, mais da variância vai
parar nesse termo comum — que some na subtração.

A log-normal é o que se obtém quando a grandeza é **produto** de muitos fatores
independentes — e é assim que se forma o quanto alguém quer uma disciplina:
interesse no tema vezes afinidade com a área vezes horário vezes dificuldade
percebida. É uma afirmação sobre alunos, e não sobre a ignorância de quem modela.

`sigma` é o único parâmetro de dispersão que chega à alocação, e **grande
concentra, pequeno achata**:

- o coeficiente de variação é `sqrt(exp(σ²) − 1)`, que cresce depressa, de modo
  que a faixa útil inteira cabe entre ~0,25 (aluno quase indiferente) e ~3 (quer
  uma disciplina e despreza o resto) — em passos **lineares**;
- a média do logaritmo (`interest_mean`, μ) é configurável, mas **some**:
  deslocá-la multiplica a linha por `e^μ`, e a constante morre na normalização.
  Ela existe para a prévia da interface, que desenha a log-normal fonte antes
  de normalizar — em μ = 0 a massa se espreme entre 0 e 1 e a forma não se lê.
  Há um teste (`test_the_mean_is_only_scale`) que garante que ela não mexe em
  nada;
- a moda do sorteio cru é `exp(μ − σ²)`, **sempre positiva** — não há limiar de
  sigma a respeitar para que o interesse mais provável de uma disciplina não
  seja zero.

Os padrões são **μ = 1 e σ = 1**: a moda da fonte cai em 1 e o coeficiente de
variação fica em ~1,3.

O **peso do turno** é a única coisa que sobrevive à normalização além de σ, e
por um motivo exato: ele **varia dentro da linha**. É o perfil de rotina
(`equations.routine_weight`) multiplicando as turmas diurnas ou as noturnas,
conforme a vida que o aluno tem fora da grade — e é isso que o distingue de
μ, que é comum à linha inteira e por isso se cancela.

**A invariante de altura da eq. (41) saiu.** Ela impunha `s_x > s_y ⇒ u_x > u_y`:
a disciplina que destrava uma cadeia mais longa valia sempre mais que a terminal,
qualquer que tivesse sido o sorteio. Isso punha valor curricular dentro do que
deveria ser gosto, e a correlação resultante entre interesse e posição na grade
tornava indistinguíveis dois genes que precisavam ser eixos separados. No lugar
dela entrou a **herança** de `equations.utility`.

**Esta é a terceira distribuição do projeto**, e as duas anteriores caíram por
motivos estruturais. A normal cortada em `[ε, 1]` não produzia aluno
concentrado: com suporte limitado e média no meio, a maior cota normalizada não
passava de `~1/(n·média)`, um teto que nenhum parâmetro removia. A Gamma (cuja
normalização é uma Dirichlet) resolvia isso, mas exigia `k` variando por quatro
ordens de grandeza para cobrir a mesma faixa, devolvia `0,0` exato por underflow
abaixo de `k = 2⁻⁶`, e tinha moda no zero para `k ≤ 1`.

**O gosto do aluno é resorteado a cada período.** O que ele quis no semestre
passado não determina o que quer neste — e isso muda o comportamento da fila:
com uma preferência fixa, perder uma vaga disputada condenava o aluno a querer a
mesma disciplina com a mesma intensidade até consegui-la, e a fila se acumulava;
agora a disputa recomeça com preferências novas.

Há uma **guarda contra underflow** (`behavior.UNDERFLOW_GUARD`) que não é
parâmetro de modelagem: utilidade zero é o que marca o *inelegível*, filtrado por
`utilidade > 0` nas duas mochilas, e um interesse zero viraria utilidade zero e
tiraria a disciplina do conjunto de escolha. Com a log-normal ela nunca
dispara — só chegaria a zero com expoente abaixo de −745 —, e fica como
invariante.

Sobre poupar: **depende da seletividade**. No leilão o aluno investe enquanto o
ganho marginal do próximo crédito ficar acima da reserva, e abaixo dela para de
gastar; com `credit_memory = "carry"` (eq. 36) o saldo passa para o período
seguinte, então poupar é decisão. Em seletividade 0 — o especulador — não há
corte e ele gasta tudo. Na linha de base não há nada a poupar: carga horária
não passa de um período para o outro, e ele pede até o `W_a` cheio.

Isso importa para comparar cenários. Com o sorteio dentro do loop, mexer numa
vaga deslocava o fluxo do gerador e mudava as utilidades de todo mundo, de modo
que a diferença entre dois cenários não era atribuível ao mecanismo. Agora dois
cenários com a mesma seed compartilham o interesse inteiro — há um teste
(`test_utilities_come_from_the_seed_not_from_the_simulation_path`) que triplica
as vagas e confirma que a utilidade só muda onde o conjunto elegível mudou.

### Os dois mecanismos

O cenário, a população, o interesse, as notas, os pré-requisitos, a matrícula
garantida do ingressante, a conclusão do curso e as métricas são **os mesmos**
nos dois. O que `mechanism` troca é só o miolo da rodada — e é por isso que a
diferença entre eles se lê como efeito do mecanismo.

| | `credits` (leilão, Seção 7.1) | `ranking` (linha de base, Seção 7.3.1) |
|---|---|---|
| **Moeda** | créditos, `C_a^(t,r)` | carga horária, `W_a^(t,r)` |
| **O que o aluno decide** | quanto apostar em cada disciplina, e como repartir entre as turmas dela | quais pedir, dado o teto `W_a` — eq. (50), e qual turma de cada uma |
| **Estratégia** | mochila **côncava** de pesos unitários: o N-ésimo crédito posto em `x` vale `u_{a,x}/N` | mochila **0-1**: `w_x` é peso, `u_{a,x}` é valor |
| **Quem decide a alocação** | PLI exata sobre todos os lances (eq. 22) | varredura por `N_a^(t) + ε` — eq. (49) |
| **Onde as restrições são resolvidas** | globalmente, no resolvedor | localmente e *ex-ante*, por cada aluno |
| **A exclusão mútua `E = M ∪ G` (eq. 5)** | restrições de clique dentro da PLI, sobre as apostas repartidas | o pedido já sai sem irmã e sem choque de horário; o roteamento da caminhada é a guarda |
| **Preço** | 2º preço, eq. (24) | não existe |
| **Retorno de créditos** | `f_γ`, eq. (34) | não existe — não houve preço a devolver |
| **Custo de excluir** | o preço pago se perde por inteiro (`exclusion_refund_rate`, padrão 0) | nenhum — não há moeda a perder |

Em **empate de utilidade**, as duas mochilas preferem a disciplina **listada
primeiro** no cenário — ver abaixo. A perda de expressividade é o ponto da
comparação: a mochila 0-1 só lê a *ordem* das utilidades, enquanto a côncava
carrega o *quanto* — ela decide não só quais disciplinas, mas quantos créditos
cada uma merece.

**As duas decisões são em dois níveis**, e o nível de fora é o mesmo nos dois
braços: **disciplinas**, com `max_t ũ_t` como valor. Plano — todas as turmas
como bens independentes —, o orçamento da disciplina seguiria o **número de
turmas** dela no leilão, e no CR a caminhada consumiria `W_a` em ordem de
turma; nos dois casos o funil da oferta entraria na decisão do aluno. Com dois
níveis, o quanto (ou o se) da disciplina é decidido antes de as turmas serem
vistas, e o número delas não o toca.

O **segundo nível difere entre os braços, e a diferença é do mecanismo**. No
leilão ele é **outra mochila côncava**, agora entre as turmas da disciplina,
com a fatia dela como orçamento e sem limiar — o corte foi feito no nível de
fora, e a fatia sai inteira, de modo que a soma por grupo é exatamente a do
nível de fora. O aluno aposta mais na turma que prefere e guarda apostas
menores nas irmãs: ele só pode **levar** uma (eq. 5), mas pode **pedir** em
várias, e é esse hedge dentro da rodada que o segundo nível expressa.

Na linha de base ele é uma **escolha** (`equations.best_class`): uma turma por
disciplina, a melhor disponível que não choca com o que ele já pediu. Não há
*quanto* a dizer, só *qual*, e pedir duas turmas da mesma disciplina — ou duas
no mesmo horário — seria pedir o que ele não pode cursar junto. **O aluno
resolve o conflito em casa**, na ordem de preferência dele; do lado do leilão
quem resolve é o clique dentro da PLI, globalmente. Perdida
a turma na rodada 1, `available_goods` devolve as irmãs na rodada 2 — do lado
do CR o seguro é a rodada; do lado do leilão, a repartição e a rodada.

É a mesma assimetria que separa as duas mochilas um nível acima — mensagem
cara contra mensagem gratuita: no leilão cada crédito posto numa turma é um
crédito que não está em outra, e é por isso que ali existe uma repartição a
fazer.

**O preço disso é tempo de PLI**, e é preciso declará-lo: cada restrição de
clique nasce de um aluno que apostou em mais de uma turma do grupo, e repartir
dentro do grupo faz com que quase todo aluno o faça. Medido no cenário padrão
— 63 disciplinas, 288 turmas, coorte de 270, 23 períodos e 3 rodadas, uma
simulação do braço `credits_return`: **1 193 356 lances e 492 s** repartindo,
contra 526 336 lances e 120 s se a fatia da disciplina fosse inteira para uma
turma só. São 2,3× os lances e 4,1× o tempo, e é o custo da expressividade que
o segundo nível acrescenta — o que pesa é o número de **turmas por
disciplina**, não o de disciplinas.

**O roteamento** é o análogo da restrição de clique na ditadura serial: a
caminhada guarda os grupos já atendidos e, ao chegar numa turma cuja disciplina
já foi concedida, pula para a próxima. Com o pedido de uma turma por
disciplina ele não tem o que fazer dentro de uma rodada, e continua lá como
**guarda**: `serial_dictatorship` não checa clique nenhum por si, e o braço
precisa dela se o pedido voltar a listar irmãs.

**O preço também conhece o grupo**: quem apostou em três turmas da mesma
disciplina e foi atendido numa delas não é perdedor nas outras duas. Contá-lo
ali faria cada membro do grupo encarecer as turmas do próprio grupo, e o efeito
apareceria como "turmas encarecem tudo", que é artefato.

**A mochila côncava substitui as eqs. (44)-(46)**, que repartiam o orçamento
proporcionalmente à utilidade, truncavam e distribuíam a sobra em ordem de
preferência. O lance proporcional é o ótimo da relaxação contínua da mochila
(maximizar `Σ u_x·ln(c_x)` com `Σ c_x` fixo dá `c_x` proporcional a `u_x`), de
modo que a mochila é a versão **inteira e exata** do mesmo critério e resolve
sozinha o arredondamento que as eqs. (45)-(46) tratavam à parte. Como os pesos
são unitários e o ganho marginal cai dentro de cada disciplina, o guloso sobre
os ganhos marginais é ótimo — não há tabela de programação dinâmica a montar,
como há na mochila 0-1 da linha de base.

Como ali não há crédito, as grandezas de crédito saem **nulas** dos relatórios
(orçamento, saldo, lances, retorno e preço), não zeradas: zero se leria como
"ninguém gastou", e o certo é "não há o que gastar". `min_credits` e
`credit_return` continuam no cenário — a comparação roda a mesma configuração
dos dois lados — mas não têm efeito em `ranking`.

### O calouro conta como gente, não como dado

Quem ingressa num período recebe vaga garantida nas **disciplinas de entrada**
— as obrigatórias sem pré-requisito. É um **pacote fixo**, igual para todo
mundo e indiferente à preferência, e ele entra com `CR = 0,000` sempre. Medi-lo
é medir a matrícula garantida, não a alocação, e isso vale igual nos dois
mecanismos.

O `ψ` do calouro depende de haver optativa no cenário, e vale saber qual dos
dois casos você está lendo:

| | conjunto elegível do calouro | ψ |
| --- | --- | --- |
| sem optativa, turma única | só as de entrada — exatamente o pacote | **1,000**, sem exceção |
| sem optativa, várias turmas | o mesmo pacote, mas a turma é sorteada por bloco | ≤ 1, e abaixo quando a turma recebida não é a preferida |
| com optativa | entrada + todo o catálogo de optativas | bem abaixo de 1, e nunca 1,000 |

Com optativa a garantia deixa de cobrir o elegível: no cenário padrão são 6
garantidas contra 33 elegíveis, porque as 27 optativas não têm pré-requisito e
estão abertas desde o 1º período. O `ψ` do calouro passa a medir o quanto a
preferência sorteada coincidiu com o pacote — **ruído**, onde antes era
constante. A regra de excluí-lo não muda; o motivo, sim.

Com `W_a = 24` contra as 15 h do pacote, o calouro ainda **disputa**: sobram
9 h, e é com elas que ele pede optativa. Era o que a folga existia para
produzir — teto colado no pacote não deixa pedido nenhum para observar.

Num preset com 6 coortes ele chega a **11% de todas as linhas
aluno-período**, e sozinho invertia o sinal da correlação da eq. (57):

| λ (seed 1) | com calouros | sem calouros |
| --- | --- | --- |
| CR (legado) | +0,267 | +0,587 |
| Créditos | −0,122 | +0,066 |

A regra, portanto: o calouro **fica nas contagens de pessoas** (`active`,
`population`, `graduated`) e **sai de toda média por aluno** — as métricas e as
grandezas de crédito. Um recorte só, para que `ψ̄` e "créditos por aluno" na
mesma tela não falem de populações diferentes.

Duas consequências visíveis:

- `metrics.students <= active`, e os dois números não são o mesmo.
- **O 1º período de uma simulação não publica métrica nenhuma** (`metrics` é
  `None`): ali todo mundo é calouro. A série de uma coorte começa no período
  *seguinte* ao seu ingresso.

### A comparação

`run_comparison` roda o mesmo cenário em cada braço (`ARMS`), `N` vezes em
cada um, com as **seeds de 1 a N**:

| Braço | Interface | Moeda | Resolvedor | Memória | `k` da eq. (34) | Roda |
|---|---|---|---|---|---|---|
| `ranking_greedy` | Ordenação por CR | CR | varredura | — | 0 (inerte: não há crédito) | **sempre** |
| `credits_greedy` | Bidding points | lance | varredura | `none` | 0 | ablação |
| `credits_ilp` | Leilão igualitário | lance | PLI | `none` | 0 | **sempre** |
| `credits_return` | Leilão acumulativo | lance | PLI | `carry` | o do cenário (padrão 2) | **sempre** |

A chave `credits_ilp` é **histórica** — nasceu nomeando o resolvedor, quando o
braço existia para isolá-lo da varredura, e hoje nomeia o leilão igualitário.
Ficou porque a chave é identificador estável: comparação gravada antes disto
continua casando com o braço.

`credits_greedy` está em `ABLATION_ARMS` e não roda por padrão. Ele separa as
duas mudanças que há entre o CR e o leilão igualitário — mensagem e resolução
—, e é a resposta pronta para "o ganho vem da moeda ou do resolvedor?".

`credits_ilp` e `credits_return` diferem em **uma única coisa**, o acúmulo de
créditos, de modo que a diferença entre eles *é* o efeito do acúmulo, isolado.
Ele é a única parte do leilão que premia desempenho, e portanto a única com
chance de recriar o incentivo que o CR dá de graça. Por isso o `resolver` que
vier na configuração é ignorado, como a seed; o `return_multiplier` vale onde
o braço não o fixa, e os demais o fixam em 0.

**Memória e retorno são um canal só.** O braço igualitário fixa os dois
(`credit_memory = "none"` e `k = 0`), e os dois campos dizem a mesma coisa:
medido, `"carry"` com `k = 0` sai idêntico a `"none"` — relatório por
relatório, em todas as seeds —, porque o orçamento abre em `C_min` (eq. 37) e,
sem retorno, só pode cair; o piso o traz de volta. A sobra só tem o que
carregar depois de o retorno erguer o saldo acima do piso. Fixar os dois é
redundância deliberada: o braço fica dizendo o que é em vez de depender dessa
prova. Há teste que guarda.

As duas condições da Seção 7.3 saem daí:

1. **Mesma inicialização em todos os braços.** A seed gera a população, o
   interesse e as notas, então rodar a mesma seed nos três é literalmente a
   mesma gente encontrando regras diferentes. As listas da resposta são
   **pareadas**: o i-ésimo elemento de cada uma é a mesma população.
2. **Múltiplas configurações de entrada.** As N seeds são essas configurações.
   Uma simulação só não diria nada — a diferença poderia ser daquela população.

São **sete métricas**: satisfação (ψ̄), **ocupação** (θ), **progresso**,
equidade (φ), correlação (λ), **desperdício de vaga** (ε) e **tempo de
formatura**. Nada de crédito, porque não há contraparte do outro lado.

Três delas mudaram de nome em 17/11/2026, e vale saber o que é o quê. A
**satisfação** é o que se chamava "eficiência de alocação" — mesmo ψ̄ da
eq. (53), mesmo campo `efficiency` na API. A **ocupação** é o que se chamava
"aproveitamento da carga" — mesma conta (carga obtida no período ÷ W_a,
contando a vaga obtida tenha ela sido excluída depois ou não) e mesmo campo
`utilization`. O símbolo θ veio junto, e com ele uma colisão a declarar: no
anteprojeto θ é a eq. (54), a fração das vagas ofertadas que encheu. Essa
grandeza continua existindo e continua se chamando `occupancy` na API, mas
não é desenhada em lugar nenhum da tela e, na interface, passou a ser o
**preenchimento das vagas**.

O **progresso** é novo: a carga aprovada do histórico sobre a carga que fecha
o curso (`config.hours_to_graduate()` — todas as obrigatórias mais a exigência
optativa X). É a única métrica de recorte que **acumula**, de modo que sobe ao
longo do horizonte em qualquer mecanismo e o que separa os braços é a
inclinação. Tem o mesmo viés de seleção do tempo de formatura, e pela mesma
razão: quem fecha a grade sai da simulação, então a média dos que ficam para
de subir na drenagem — lê-se com a fração de concluintes ao lado. Não é a
semestralização, que divide pelo que o aluno *poderia* ter aprovado desde que
entrou e mede ritmo.

Desde 14/11/2026 a tela traz também o **CR médio** (N̄), na mesma maquinaria de
régua e recorte das demais. Ele **descreve, não pontua** — como λ e a saturação
—, e por um motivo que vale escrever: o CR médio sobe tanto quando o aluno vai
melhor quanto quando o mecanismo o roteia para turma mais fácil, e separar as
duas coisas exige a dificuldade da turma, que está nos gráficos por disciplina
e não aqui. Dizer qual lado "ganhou" em N̄ seria afirmar o que o número não
mostra.

**E um gráfico que não é métrica**: o *tempo de alocação*, em segundos, para
cada (período, rodada) de cada mecanismo. Ele é o único da tela que não mede o
que o mecanismo produziu, e sim quanto custou produzi-lo — por isso não tem
recorte por coorte nem por perfil, e não é omissão: o resolvedor decide a
rodada inteira de uma vez, então não existe parcela do tempo atribuível a um
grupo de alunos. A régua é **logarítmica** porque os dois mecanismos ficam a
ordens de grandeza um do outro (medido no cenário de teste: 203,7 ms da PLI
contra 0,4 ms da varredura); em régua linear a linha do CR encostaria no zero.
Rodada que não alocou nada sai como buraco na linha, não como zero — zero
segundo se leria como "foi instantâneo", e o que houve foi não acontecer.

Ele é **tempo de parede**: muda de máquina para máquina e entre duas execuções
da mesma seed. Por isso fica fora de toda igualdade — `compare=False` nos
relatórios e nas séries, e removido antes da comparação nos testes que exigem
que a mesma configuração produza o mesmo resultado.

### Economia de créditos — a seção que só o leilão tem

Quatro gráficos, e a seção inteira some quando não há leilão na comparação. Os
três primeiros são por aluno e usam a régua e o recorte da tela, como os
demais:

| gráfico | o que é | de onde sai |
|---|---|---|
| orçamento | C_a^(t,1), a oferta de abertura, antes de qualquer lance | `GroupSnapshot.credits_per_student` |
| gastos | o consumo da eq. (25) acumulado até o instante | `GroupSnapshot.mean_credits_spent` |
| retornados | Σγ da eq. (34) — só existe no fim do período | `GroupSnapshot.mean_credit_return` |

O **gasto** não é medido à parte: é a oferta de abertura menos o saldo, que é
exatamente o consumo somado. Derivar em vez de propagar é o que torna as duas
pontas impossíveis de divergir. E ele é **distinto do apostado** (`mean_bids`):
lance perdido não consome nada, então o apostado passa do gasto sempre que
houve disputa perdida.

Nenhum dos três pontua. Gastar mais não é melhor nem pior — é o que o mecanismo
faz com o orçamento —, e por isso eles ficam fora das tabelas de comparação,
que existem para dizer qual lado ganhou. Na linha de base por CR saem `null`, e
a linha some do gráfico em vez de virar um piso que ninguém pagou.

**O quarto é de outra natureza: o preço, recortado por turma.** É o único
gráfico da tela cujas linhas não são grupos de gente — o que elas repartem é a
**oferta**:

| recorte | grupos |
|---|---|
| turmas | quantas turmas a disciplina tem: 1, 2, … |
| carga horária | os valores de `hours` que a grade usa |
| dificuldade | os valores de `difficulty` que a grade usa — é da **disciplina**, e toda turma dela a herda |
| turno | diurna ou noturna; é o único atributo que varia **dentro** de uma disciplina |
| período | o período da grade, com a **optativa** como grupo à parte: ela não tem período, é elegível desde o ingresso |

Os grupos saem dos valores que o cenário de fato usa, e não de uma lista fixa:
grade com duas cargas horárias produz duas linhas, com cinco produz cinco. A
média é **simples entre as turmas** do grupo, e não ponderada pelas vagas — a
pergunta é quanto custou a turma, não quanto pagou o aluno médio. Turma que não
chegou ao mercado no período não entra.

Por que ele vem à parte de `series`, e não como mais um eixo dela: cruzar
"disciplina de 2 turmas" com uma métrica por aluno não produziria leitura
nenhuma, porque um aluno não pertence a esse grupo. Pelo mesmo motivo a régua é
sempre o **período** — as outras duas (idade, coorte) são do tempo do aluno, e
uma turma não tem idade nem coorte.

A chave de cada grupo vai na API como **o valor**, sem idioma (`"2"`, `"60"`,
`"1.4"`, `"elective"`); quem rotula em português é a interface, como em
`COMPARISON_ARMS`.

**Duas escolhas governam todos os gráficos da tela**, e são independentes: a
**régua** do eixo X e o **recorte** das linhas. O modelo é a terceira dimensão
e não é escolha — ele é sempre o traçado: pontilhado no CR, tracejado no
leilão igualitário, contínuo no acumulativo.

| Régua (eixo X) | Um ponto é | Para que serve |
|---|---|---|
| período | um período da simulação | o calendário da universidade: é aqui que se veem o aquecimento, o estado estacionário e a drenagem |
| idade | quantos períodos o aluno completou | o tempo do **aluno**: alinha as coortes pelo ingresso e tira a fase do horizonte de dentro da curva |
| coorte | um período de ingresso | um corte transversal: a vida inteira de cada turma resumida num ponto |

O recorte é o **Geral** (uma linha por modelo) ou um dos quatro eixos de perfil
— desempenho, disponibilidade, seletividade, rotina.

A **Amplitude** é o recorte que a API não manda — a interface o calcula sobre os
outros. Em vez de uma linha por grupo, uma linha por **eixo**, e o valor é o vão
entre a maior e a menor mediana dos grupos daquele eixo naquele ponto
(`equations/amplitude.ts`): desempenho em verde, disponibilidade em azul,
seletividade em amarelo, rotina em vermelho. Ela responde outra pergunta — não
"quanto cada perfil colheu" mas "quanto o perfil importou" —, e é onde se vê de
relance qual eixo o mecanismo separa e qual ele ignora. Três consequências: a
linha não tem faixa, porque a amplitude é um número só e não uma redução entre
as seeds; a régua se ajusta aos dados em vez de ser o contradomínio da grandeza,
porque o vão é pequeno perto dele e em [0, 1] ficaria colado no eixo; e o ponto
medido num grupo só sai da linha em vez de valer zero, que se leria como
"os perfis empataram".

A coorte era recorte até 11/11/2026 e virou régua: ela é um corte do **tempo**,
e tê-la como cor obrigava a ler duas dimensões temporais no mesmo gráfico.

As duas réguas novas saem das **células** — cada eixo de perfil cruzado com a
coorte, medido período a período. É o cruzamento que permite escolher régua e
recorte independentemente; sem ele, a régua da idade só existiria no Geral.
Dentro de um período a idade e a coorte são a mesma partição (`idade = t − t_a`),
e o que distingue as duas réguas é só como as células são reagrupadas ao longo
do horizonte. O reagrupamento é a **média ponderada pelos alunos medidos**, a
mesma da redução por período, com uma exceção: a fração de concluintes é
acumulada, então na régua da coorte vale a do último período medido da coorte,
não a média da subida dela.

O **desperdício** é a quinta, e é a que a disponibilidade existe para produzir:
as vagas obtidas e largadas sobre as obtidas. É o vão entre as duas leituras de
ocupação — a vaga saiu da oferta de qualquer jeito, mas só a parte retida virou
carga cursada. Daí a divisão de trabalho nas métricas de recorte: as grandezas
de **contagem** (vagas alocadas, preenchimento, ocupação) ficam no alocado, as de
**valor** (ψ, φ, λ) ficam no retido, porque o aluno não consumiu a utilidade do
que largou.

As três primeiras são de período, e uma simulação vira um número pela média
**ponderada pelos alunos medidos** (`metrics.students`, não `active`): a
simulação termina numa fase de drenagem, e uma média simples daria a um período
final de vinte alunos o mesmo peso de um período cheio de trezentos. O 1º
período, sem métrica, simplesmente não entra.

O **tempo de formatura** não é de período: é a média, sobre os concluintes, de
quantos períodos cada um levou do ingresso ao diploma (contando o da formatura).
Ele tem **viés de seleção** — só existe sobre quem concluiu, então um mecanismo
que forma menos gente pode exibir um tempo *menor* só porque sobraram os
rápidos. Por isso o resumo carrega `graduates` junto: a média não se lê sem ele.

Além dessas quatro, uma série de **saturação**: as vagas obtidas por aluno em
**cada rodada**, uma posição por rodada do cenário. Cada posição conta o que foi
ganho *naquela* rodada, não o acumulado, de modo que as posições somadas dão as
vagas por aluno do período. O que se lê é o **decaimento** entre elas — um
mecanismo que atende mais demanda de saída começa alto e cai rápido, porque
pouco ficou por alocar; um que leva a disputa adiante distribui as vagas pelas
rodadas. Nenhuma rodada isolada tem lado "melhor": na primeira, mais alto é
atender mais; nas seguintes, mais alto é ter deixado mais para trás. E a
matrícula garantida não infla a primeira, porque o calouro está fora do recorte.

Além delas, a seção **Solicitações de disciplinas**: o funil de cada
disciplina que ainda falta ao aluno. Seis estados o particionam, e a unidade é
a **disciplina**, não a turma — o que o aluno pede e leva vem por turma e é
dobrado no grupo dela antes de classificar, senão o histórico (que é por
disciplina) nunca casaria com o que foi retido:

    ainda falta ─┬─ não elegível   pré-requisito pendente, ou optativa que a
                 │                 cota já dispensou
                 └─ elegível ──┬── não solicitada
                               └─ solicitada ─┬─ indeferida
                                              └─ obtida ─┬─ excluída
                                                         └─ cursada ─┬─ reprovada
                                                                     └─ aprovada

**A tela mostra quatro frações condicionais**, não as seis contagens
(`equations.request_funnel`). Cada uma divide pelo **nó anterior**:

| Fração | Conta | Sobre |
|---|---|---|
| solicitadas | o que ele pediu | o que lhe faltava |
| deferidas | o que lhe foi concedido | o que ele pediu |
| cursadas | o que ele não largou | o que lhe foi concedido |
| aprovadas | o que ele passou | o que ele cursou |

Três decisões de leitura sustentam esse gráfico.

**Condicional, e não fração do catálogo.** Com o mesmo denominador nas seis, um
aluno que destrava a grade vê "não elegível" cair e as outras cinco subirem sem
que nada tenha mudado no mecanismo: as seis andam juntas e nenhuma isola um nó.
Dividindo pelo nó anterior, cada painel se mexe só quando o nó dele se mexe — e
as quatro passam a dividir a mesma régua, de 0 a 1, o que as torna comparáveis
entre si e entre os braços. A fração de cursadas é, por construção, `1 − ε`: a
mesma conta que o desperdício de vaga, vista do funil em vez da vaga.

**O já aprovado sai do denominador.** O complemento da eq. (42) juntaria "já
aprovada" com "bloqueada" num estado só, e os dois andam em sentidos opostos: o
primeiro cresce com o progresso do aluno, o segundo encolhe com ele. Somados,
cancelam-se em parte — a leitura esconderia a própria história. Com as
aprovadas fora, "não elegível" significa só *bloqueada*, e cai conforme ele
destrava a grade.

**Nó vazio não tem fração.** Quem não pediu nada não tem fração de deferidas, e
ali o ponto **falta** em vez de valer zero — zero diria que ele pediu e foi
recusado. As seis contagens continuam na resposta da API, e é a elas que se
recorre para saber por que uma fração sumiu.

A comparação traz também o **histograma do interesse** do cenário —
o gráfico da causa ao lado do da consequência. Ele mostra como a preferência de
um aluno se reparte entre as disciplinas: cada linha (aluno, período) é
reescalada ao **próprio** mínimo e máximo e dividida em 9 faixas de mesma
largura, e a altura é a fração de valores em cada faixa. É o interesse, e não
a utilidade, porque é ele que σ e o peso do turno governam. A escala é por
linha, e não do menor ao maior valor da matriz inteira, porque global degenera —
um único extremo define o intervalo e, de `σ = 1` em diante, 94% dos valores
caem na primeira faixa, de modo que todos os gráficos sairiam iguais.

Ficaram de fora, por motivos diferentes. A **ocupação** (θ) porque, com o
calouro fora do recorte, ela deixou de se ler como "o quanto a universidade
encheu" — as vagas garantidas continuam ocupadas e não entram mais no
numerador; essa leitura está nos gráficos por disciplina de uma simulação. E a
**semestralização** (σ̄) porque o tempo de formatura mede a mesma coisa —
progressão na grade — num número que se lê direto, em períodos. As duas
continuam nos relatórios de uma execução única.

### Garantias dos relatórios

Duas invariantes que os testes travam, porque métrica sobre conjunto vazio é
pior que métrica ausente — ela vira zero, e zero num gráfico se lê como queda:

1. **Todo período publicado tem pelo menos um aluno ativo**, e a numeração vai
   de 1 a `len(periods)` sem buraco. Vale por construção: os ingressos ocorrem
   em períodos consecutivos a partir do primeiro e, passado o último deles, a
   população só diminui — então o primeiro período vazio, se houver, só é
   seguido de períodos vazios, e a simulação para ali. Com ingresso em todo
   período o relatório traz os `|T|` períodos inteiros; com uma fase de
   drenagem a parada é o fim natural dela, quando o último aluno
   sai. Na entrada, cenários sem nenhum aluno ou sem nenhuma disciplina são
   recusados.
2. **Recorte sem aluno no período não reporta métrica**: `metrics`,
   `mean_credits` e `mean_approved_hours` vêm `null`, não 0,0 — não havia
   ninguém, o que é diferente de ninguém ter ficado satisfeito. O acumulado de
   concluintes (`graduated`) continua valendo, que é o que ainda faz sentido
   contar. Nos gráficos o ponto some; nas tabelas aparece um traço.

O mesmo vale no tempo para o **retorno de créditos** (`mean_credit_return`) e
para as três grandezas da exclusão (`excluded`, `exclusion_rate`,
`effective_utilization`) e os seis estados de solicitação: a exclusão e as
notas são posteriores à última rodada, então o recorte de uma rodada traz
`null` e só o agregado do período traz número. No eixo "por rodada" esses
gráficos seguem em período, com o aviso no subtítulo.

Uma ressalva de leitura sobre o `mean_credit_return`: ele passou a somar duas
coisas de natureza diferente — retorno por desempenho e retorno por exclusão.
Um braço com muita exclusão pode exibir retorno médio **alto** sem que ninguém
tenha ido bem, de modo que ele se lê ao lado da taxa de exclusão, nunca
sozinho.

### Escolhas de modelagem não fixadas pelo anteprojeto

- **A turma como bem alocado** (`Discipline.classes`, `class_size`): o
  anteprojeto é de turma única, e a exclusão mútua da eq. (5) está lá sem
  critério declarado. Aqui são **dois** critérios de conflito, e juntos são o
  `E = M ∪ G`: duas turmas da mesma disciplina, ou duas turmas no mesmo
  **horário**. A oferta da disciplina é repartida entre as turmas, com a sobra
  da divisão nas primeiras.

  O que isso acrescenta ao modelo é a **escolha dentro da disciplina**. Numa
  obrigatória sem turmas não há nada a ganhar além da vaga; com turnos e
  horários, escolher a seção passa a ser decisão — e aí os dois mecanismos se
  separam de novo: sob CR a vantagem é posicional e se acumula (quem tem CR
  alto pega a turma que lhe serve), sob leilão a turma disputada tem preço e a
  vantagem se dilui.
- **O turno e o horário** (`equations.class_shift`, `equations.class_schedule`):
  um terço das turmas de cada disciplina, arredondado **para baixo**, é
  noturno — a divisão para baixo é o que preserva a assimetria real entre os
  turnos, e deixa a disciplina de turma única sendo diurna em vez de
  meio-a-meio. As turmas são então repartidas em círculo entre `day_slots`
  horários diurnos e `night_slots` noturnos, varrendo a grade na ordem em que
  ela é declarada.

  A varredura circular dá **duas garantias de graça**. O número de turmas por
  horário difere em no máximo 1 (na grade padrão, 17 a 18 por horário diurno e
  12 a 13 por noturno). E em todo período existe uma grade sem choque,
  inclusive só no diurno ou só no noturno: cada horário aparece no máximo
  `⌈D/2⌉` vezes entre as diurnas de uma disciplina do período, então `t`
  disciplinas ocupam ao menos `t` horários distintos e o teorema de Hall
  garante o emparelhamento.

  As **condições** disso são do cenário: até 6 disciplinas por período,
  disciplinas do mesmo período declaradas em sequência, e no máximo
  `day_slots` turmas diurnas e `night_slots` noturnas por disciplina. E há uma
  simplificação declarada: **cada turma ocupa um horário**, seja de 2 h ou de
  3 h — o choque é de encontro, não de minuto.
- **A dificuldade é da disciplina** (`Discipline.difficulty`): toda turma dela
  a herda inteira. Houve uma escada por turma (`class_difficulty_levels`) até
  16/11/2026, que repartia as turmas entre fáceis, médias e difíceis mantendo
  a média geométrica no nível do meio; ela saiu junto com a atratividade, e o
  que distingue as turmas entre si passou a ser o **turno**. A grade padrão
  cruza carga × dificuldade, com (1; 1,4; 2) — centro geométrico 1,41, o mesmo
  que a escada fixava.
- **A turma de entrada do calouro** (`equations.entry_class`): a matrícula
  garantida não escolhe turma, então a coorte é repartida em blocos contíguos,
  na ordem em que os alunos foram gerados. Em blocos e não sorteada porque não
  há sorteio em tempo de execução, e porque o bloco é o único jeito de a
  repartição ser exata sem consultar nada. O bloco **não gira** entre as
  disciplinas de entrada: quem é do bloco 0 leva a primeira turma de todas elas.
  **O bloco gira entre as disciplinas de entrada**, e esse giro não é enfeite:
  sem ele, as primeiras turmas de disciplinas distintas voltam ao mesmo
  horário assim que a varredura circular dá a volta, e o pacote garantido —
  que é entregue inteiro, fora do mecanismo — sairia em choque consigo mesmo,
  violando a eq. (5) antes de o leilão abrir. O giro é uma progressão
  aritmética cujo passo `config.entry_offsets` procura, **começando pelo
  passo 0**: a grade que já saía sem choque não é girada e continua bit a bit
  igual. Onde passo nenhum resolve, o cenário é recusado.

  O que permanece: o turno segue o bloco, porque o giro é dentro do turno —
  o calouro de bloco baixo entra no diurno e o de bloco alto no noturno,
  independentemente da rotina dele.
- **Pré-requisitos** (`Discipline.prerequisites`): tomam o lugar da senioridade
  `s_x` da eq. (38). O período de uma disciplina não é configurado — sai da
  indução `1 + max(período dos pré-requisitos)`, com 1 para quem não tem
  nenhum —, e o aluno só fica elegível a disputá-la quando aprovou tudo que ela
  exige. Um ciclo de pré-requisitos é recusado na entrada: as disciplinas dele
  não teriam período e nunca ficariam elegíveis.
- **Ordem de desempate entre disciplinas**: quando duas valem o mesmo para um
  aluno, ganha a **listada primeiro** em `SimulationConfig.disciplines` — a
  ordem em que a interface as mostra, que é a ordem em que foram acrescentadas.
  É uma ordem **global**: a mesma para todo aluno, período e rodada, e vale nas
  duas decisões que o aluno toma sozinho — a mochila côncava do lance e a
  mochila 0-1 do pedido por CR. Ela se propaga sem ninguém carregá-la de
  propósito, porque `utility_matrix` constrói a linha do aluno varrendo a grade
  e dicionário em Python preserva a ordem de inserção; por isso as duas mochilas
  leem o posto de `utilities`, nunca de `available`, que é só um filtro.

  Com interesse sorteado o empate tem probabilidade zero, então a regra quase
  nunca é acionada. Ela existe para que um cenário escrito à mão — uma grade
  simétrica, um teste — não dependa da ordem de iteração para dar sempre o mesmo
  resultado, que é a mesma exigência de determinismo da Seção 7.3 que mantém os
  sorteios fora do loop. Não se confunde com `alpha`/`epsilon` (eq. 20): aquilo
  desempata **entre alunos**, dentro do leilão; isto desempata **entre
  disciplinas**, dentro da cabeça de um aluno.
- **Matrícula garantida do ingressante**: quem entra num período recebe vaga em
  **todas** as disciplinas de 1º período e não participa dos lances. O sistema
  ainda assim lança o gasto na conta dele, repartindo o orçamento igualmente
  entre essas disciplinas e deixando o resto da divisão no saldo — e é esse
  valor que alimenta o retorno de créditos da eq. (34). A garantia vale só no
  ingresso: recursar uma delas é disputá-la no leilão como qualquer outra. Daí
  as duas validações do ritmo de entrada: a coorte não pode passar da menor
  oferta entre as disciplinas de 1º período, nem a carga somada delas pode
  passar do `W_a` — a matrícula garantida não escolhe quem a recebe.
- **Os três eixos de traço**, mais o sigma do interesse:

  | Eixo | O que governa | Sorteio |
  | --- | --- | --- |
  | desempenho | a normal dividida da nota, e por aí a frequência com que o aluno reprova | uma por par (aluno, disciplina), persistente |
  | disponibilidade | a log-normal das horas que ele tem para o período, e por aí a frequência com que exclui | uma por par (aluno, período) |
  | rotina | o peso do turno no interesse de cada turma | nenhum: multiplica o sorteio do interesse |
  | interesse | o quanto o aluno diferencia as disciplinas | `interest_sigma`, uma linha por (aluno, período) |

  Estes três eixos descrevem o aluno **fora do mecanismo** — se ele vai bem na
  disciplina, se a larga, em que turno ele consegue estudar. São **traço
  imutável**: não respondem a sinal e o aluno não os conhece. O quarto eixo de
  perfil, a seletividade, é de **estratégia** e age *dentro* do mecanismo, ao
  pedir — são coisas separadas de propósito.

  Não há eixo de perfil para **interesse**: `interest_sigma` já é o parâmetro
  de o quanto o aluno diferencia as disciplinas, e dois botões para a mesma
  coisa tornariam qualquer resultado ambíguo de ler.

  A repartição é **igualitária entre as combinações**, e **exata**: a coorte é
  `students_per_profile × combinações`, então não há porcentagem a configurar
  nem sobra a girar entre as coortes. O que o cenário escolhe é quantos grupos
  existem.

  A dispersão de **desempenho** existe porque sem ela ninguém reprova, a
  recursada some do cenário e o CR vira ruído — a eq. (57) não mediria nada. A
  de **interesse** existe porque diferenciar preferência é **exatamente** a
  informação que o leilão diz captar e a ordenação por CR não vê. Nenhuma está
  no anteprojeto.

  `W_a` (eq. 4) também é do cenário e igual para todos, o que faz a
  semestralização comparar todo mundo contra o mesmo teto e dá à validação da
  matrícula garantida um número só a conferir.

  **Os perfis já existiram entre 03/10 e 08/10/2026** e foram removidos a
  pedido; voltaram em 31/10/2026 com outro recorte. Antes eram aptidão e
  **afinidade** (um expoente sobre `u`), com % da população configurável por
  grupo; agora são **desempenho** e **disponibilidade**, com as fatias saindo
  da contagem de grupos. O que se recupera é o mesmo: a heterogeneidade volta a ser
  *sistemática*, e com ela o recorte dos relatórios por grupo.

- **Disponibilidade e exclusão**: as horas que o aluno tem para o período,
  sorteadas da log-normal do perfil dele **a cada período**. O desempenho é
  traço — quem é bom em cálculo continua bom —, mas o tempo disponível é
  circunstância: muda com o trabalho, a família, a saúde. O que é traço é a
  *forma* de onde ela sai, e essa é o perfil.

  **Em horas, não em fração de `W_a`** (04/11/2026). O teto de carga é do
  **sistema**, não do aluno: nada impede alguém de ter tempo para 400 h num
  curso que oferece 360, e quem impede a matrícula é o alocador, que nunca
  entrega mais que `W_a` durante as rodadas. O dado do aluno não precisa estar
  alinhado a priori com a regra da instituição.

  O perfil é descrito por **moda** (em horas) e **chance de alcançar a carga
  máxima** — `equations.availability_shape` converte nos dois parâmetros
  logarítmicos, em forma fechada. A log-normal dá suporte `(0, ∞)`: a
  disponibilidade nunca fica negativa e **não tem máximo artificial**.

  A única restrição é **moda < `W_a` − 0,5**. E há um custo a conhecer: "quase
  sempre cheio" e "tipicamente perto de `W_a`" são pedidos incompatíveis nesta
  família — forçar quase toda a massa acima do teto com a moda logo abaixo dele
  exige um desvio logarítmico enorme, e a mediana vai para longe.

  Como a moda é **absoluta**, os perfis padrão valem contra o `W_a` padrão
  (360 h). Um cenário de teto menor precisa dos seus próprios perfis, e é
  recusado se as modas não couberem.

  Encerradas as rodadas, o aluno descarta disciplinas obtidas até que a carga
  retida caiba em `round(δ · W_a)`. Quem decide o que fica é uma **mochila 0-1**
  (`equations.retained_set`), a mesma da eq. (50): valor = utilidade, peso =
  carga. Não é uma ordenação por utilidade crescente, e a diferença é real —
  com teto de 122 h e as obtidas Algoritmos (90 h, u 0,22), Cálculo (60 h,
  0,13) e Física (60 h, 0,11), a heurística sacrifica as duas baratas para
  salvar a cara e retém 0,22; a mochila retém Cálculo + Física, 120 h e 0,24.

  O arredondamento é para o **inteiro mais próximo**, e não para baixo, porque
  hora é inteira no modelo. **Não há teto**: a carga efetiva é `round(δ)` sem
  clipe, e passar de `W_a` apenas significa não excluir nada.

  É também o limiar com que a chance declarada é calibrada: como `round(29,5)`
  já é 30, a inversão mira `W_a − 0,5`, e sem isso o valor realizado sairia
  alguns pontos acima do pedido.

  A versão anterior media a disponibilidade como **fração** de `W_a`, e aí
  alcançar a carga cheia exigia `δ ≈ 1` — evento de borda numa Beta. O perfil
  feito para encher a carga a enchia em 0,03% dos semestres com `W_a = 360`. O
  piso sumiu com o `round`; o teto artificial só sumiu quando a disponibilidade
  deixou de ser fração.

  A meia hora entre arredondar e truncar ainda decide casos, porque as somas de
  carga são inteiras: um conjunto que cabe por meia hora é admitido. Mas deixou
  de ser o que governa a frequência de carga cheia — essa agora é **declarada**
  no perfil, e a calibragem do limiar garante que o declarado seja o
  realizado. Medido no preset (`W_a = 24`), o perfil *Alta disponibilidade*
  pede 50% e entrega 50,0%.

  Excluir **não** mexe no CR, **não** soma carga cursada e **não** incrementa a
  tentativa. A vaga **não volta** para a oferta: exclui-se depois de encerradas
  as alocações do período, e é isso que torna a exclusão socialmente cara e dá
  sentido à penalidade do leilão. O **calouro exclui como qualquer outro** —
  imunizar a primeira coorte faria dela uma anomalia, e o sistema já lança o
  gasto na conta dele, de modo que o retorno funciona sem código novo.

  **O aluno não conhece o próprio perfil nem o sorteio do período.** Dar-lhe a
  média seria petição de princípio: a conclusão entraria como entrada, e o que
  a comparação precisa *demonstrar* é que os incentivos do sistema fazem
  perfis diferentes se saírem diferente. Dar-lhe o valor realizado antes de
  pedir seria pior: os dois mecanismos cortariam o pedido no teto certo e a
  exclusão sumiria dos dois.

  Nada disso está no anteprojeto.

- **Retorno de créditos** (`f_gamma`, eq. 34): o anteprojeto deixa a forma
  concreta em aberto — é o eixo de experimentação da Seção 7.3.2. Aqui ela tem
  **uma forma só**, aplicada ao fim de cada período sobre o preço pago
  (`paid`) e a nota obtida:

      gamma_{a,x} = round( nota / 10 · k · paid )

  O que o retorno devolve é o preço pago corrigido por dois fatores: a nota,
  que diz quão bem o aluno usou a vaga, e o multiplicador `k`
  (`return_multiplier`, padrão 2), que diz quanto o sistema devolve no total.

  **Quatro políticas discretas ocupavam este lugar** — `none` (nada volta),
  `unit` (1 crédito por aprovação), `full` (o preço inteiro a quem aprova) e
  `ratio` (a fatia correspondente à nota). Saíram em 15/11/2026: `unit` e
  `full` não liam a nota, e com elas o retorno não separava dois aprovados —
  que é justamente o que a comparação precisa demonstrar que o lance consegue e
  a ordenação por CR dá de graça. E `none` não precisa de nome próprio: é
  `k = 0`, que é também como um braço da comparação desliga o retorno sem
  deixar de ser o mesmo modelo.

  **A calibragem de `k = 2`.** Sem multiplicador o sistema não injeta crédito
  nenhum: com `k = 1` o retorno devolve no máximo o preço pago, o gasto é esse
  mesmo preço, e o saldo nunca cresce — ver a consequência medida logo abaixo.
  Com 2, a **nota de corte vira o ponto neutro**: nota 5 devolve exatamente o
  que se pagou, acima disso o aluno sai ganhando e abaixo sai perdendo.

  **A conta arredonda** (meio para cima). Truncava até 17/11/2026, e a troca
  é sobre a **resolução da moeda**: γ é inteiro, a conta erra, e o que mudou é
  o viés do erro. O piso errava sempre para baixo, até um crédito por vaga —
  ruído onde a disputa forma preço, e a conta inteira onde o preço fica no
  piso de 1 crédito, porque ali um crédito *é* a resolução.

  Medido no cenário cheio, com `k = 2` e 185 mil vagas obtidas (84,7% delas a
  1 crédito):

  | | truncando | arredondando |
  |---|---|---|
  | retorno ÷ pago | 0,625 | 1,009 |
  | vagas que renderam mais do que custaram | 3,8% | 21,2% |
  | vagas que empataram | 52,1% | 59,9% |
  | vagas que custaram mais do que renderam | 44,0% | 18,9% |
  | abertura média do período | 12,1 | 15,8 |
  | aberturas em `C_min` | 92% | 43% |

  Com o piso, o retorno somava menos do que o gasto e o saldo descia todo
  período até `C_min` o levantar de volta — o braço acumulativo saía quase
  idêntico ao igualitário, e o retorno não separava aluno nenhum. Arredondando,
  o erro fica **sem viés** e em meio crédito, e a preço 1 a vaga passa a render
  2 a partir da nota 7,5.

  O que se perdeu, e vale declarar: **o teto `k · paid` deixou de ser exclusivo
  da nota máxima**. Ele começa em `10 · (1 − 1/(2·k·paid))` — 7,5 num lance de
  1 crédito, 9,5 num de 5, 9,8 num de 10 —, de modo que o prêmio máximo só
  distingue a nota máxima onde o preço é alto. Pela mesma razão, a nota de
  corte deixou de ser o último ponto em que não se perde: a preço 1 a faixa
  neutra é [2,5, 7,5). É o custo de o crédito ser inteiro, e a alternativa
  medida era um retorno que não premiava ninguém.

  A conta é feita em **aritmética inteira** porque em ponto flutuante o produto
  cai um ulp abaixo do inteiro que deveria dar — medido, 30 combinações em
  18.876 de (nota, preço, `k`) —, e isso põe a fronteira do arredondamento do
  lado errado justamente onde ela é um empate.

  **A nota de corte `n_min` não entra na conta.** O retorno é contínuo na nota:
  quem reprova com 4,9 recebe quase tanto quanto quem passa com 5,0. Aprovar é
  o que decide a grade (eq. 40); o retorno decide o poder de compra, e são
  perguntas diferentes — amarrá-las faria o degrau da aprovação aparecer duas
  vezes.

  A **exclusão** tem regra própria (`equations.exclusion_refund`): devolve
  `round(fração · paid)`, e a **fração é zero por padrão**
  (`exclusion_refund_rate`). Excluir não devolve
  nada — é o que torna a exclusão socialmente cara, e ela precisa ser, porque a
  vaga não volta para a oferta. Sem isso, sob `none` — em que nada volta
  nunca — excluir seria o melhor resultado possível do sistema. Excluir também
  não é reprovar: é abstenção, fora da dicotomia aprovado/reprovado, e por isso
  a regra é própria em vez de um caso particular de `f_gamma`. Em especial, o
  multiplicador **não entra aqui**: ele premia desempenho em disciplina
  cursada, e excluir não cursa.

  A fração existe para quem quiser medir o degrau entre punir a exclusão por
  inteiro e amortecê-la, e é validada em `[0, 1]`. Ela arredonda, como o
  retorno. Uma ressalva de leitura:
  frações pequenas **zeram em lance pequeno** — com 0,25 um lance de 1 crédito
  devolve 0 —, e lance de 1 é o caso mais frequente, porque o orçamento limita
  o aluno a lances em no máximo `C_a` disciplinas. A penalidade é, nesse
  sentido, levemente regressiva: lance pequeno é punido proporcionalmente mais,
  e lance pequeno é de quem tem pouco orçamento.

  `n_min` continua validado em `[5, 10]`, agora porque é o piso que segura a
  ordem entre aprovar e excluir: com `k = 2`, aprovar raspando devolve
  `n_min/10 · 2 · paid`, que em `n_min = 5` é o preço inteiro — acima de
  qualquer fração de exclusão em `[0, 1]`.

  **O retorno é a única entrada de crédito novo.** O `Gamma_min` do anteprojeto
  — um crédito base somado a todo aluno todo período, eq. (35) — saiu. O
  parâmetro continua, com outro papel: virou `C_min`, o **piso** do orçamento.
  O saldo de um período é
  `clamp(C_a^(t,1) - gasto + soma gamma_{a,x}, C_min, C_max)` — conta que o
  histórico individual mostra aberta e que os testes travam. Em `ratio`, o
  arredondamento do Python desempata para o par (`round(2,5) == 2`); o empate
  exato é frequente porque as notas andam de 0,1 em 0,1 e os preços são
  inteiros pequenos, mas o viés é o mesmo para todo aluno.

  **A faixa do orçamento (`C_min`, `C_max`).** Não está no anteprojeto, que
  somava Γ_min todo período e não tinha teto. Os dois parâmetros delimitam a
  mesma grandeza — o orçamento com que o aluno abre o período —, e a conta do
  meio é livre para passar dos dois lados. O piso **não é ganho**: quem termina
  acima dele não recebe nada por existir, e quem gasta tudo sem aprovar reabre
  em `C_min`, não em zero. O teto corta o acúmulo: sem ele a eq. (36) acumula
  sem limite, e medido no cenário cheio com um ganho base de 60 o saldo chegava
  a **900 créditos** — quinze vezes a base — em quem é seletivo o bastante para
  não gastar, que é poder de compra vindo da abstenção e não do desempenho. Os
  dois cortam **depois** da conta, de modo que gasto e retorno continuam
  creditados por inteiro. Com `credit_memory = "none"` ambos são inertes,
  porque ali o orçamento é `C_min` por construção. `max_credits = None`
  desliga o teto; o piso não se desliga.

  **É isso que obriga o multiplicador a existir.** Com `k = 1` o retorno
  devolve no máximo o preço pago, e como o gasto é esse mesmo preço tem-se
  `restante + soma gamma <= C_a^(t,1)`: o saldo nunca cresce, e como o aluno
  entra em `C_min` o orçamento fica em `C_min` para sempre. Medido no cenário
  dos testes antes do multiplicador: os 15 alunos terminavam com 12 créditos
  nas quatro políticas de então, o teto nunca cortava e o braço
  `credits_return` saía idêntico ao `credits_ilp` em eficiência, seed a seed —
  o eixo de experimentação da Seção 7.3.2 desaparecia. Com `k = 2` o saldo
  volta a subir, e com 3,5 sobe mais; há teste que guarda os dois lados.

  O padrão passou de um ganho base de 60 sem teto para **piso 12 e teto 30**, e
  o troco está medido no cenário cheio (63 disciplinas, 288 turmas, 23
  períodos), ainda com o ganho base no lugar:

  | | base 60 / sem teto | base 12 / teto 30 |
  | --- | --- | --- |
  | pares (aluno, turma) pedidos | 1.185.127 | 713.083 |
  | lances de 1 crédito | 53,4% | 88,1% |
  | turmas pedidas por aluno (média / p95 / max) | 28,5 / 72 / 102 | 15,2 / 30 / 30 |
  | disciplinas pedidas por aluno (média / max) | 12,7 / 33 | 9,1 / 30 |
  | saldo (média / max) | 372 / 900 | 23 / 30 |

  O teto corta 40% das variáveis da PLI e prende o p95 de pedidos em 30, mas
  **sobe o empate de 53% para 88%**: com o orçamento abaixo do conjunto
  disponível, a mochila côncava não chega a dar um segundo crédito a quase
  ninguém, e quase todo lance fica em 1. Os dois efeitos puxam o custo da PLI em
  sentidos opostos — ver "O que custa caro na PLI".

- **Semestralização** (`sigma_a`): carga horária aprovada dividida por
  `W_a x idade_a`, onde a idade é quantos períodos o aluno completou desde
  `t_a`. Mede o atraso na progressão — 1 é quem nunca deixou de encher a carga
  horária, e quem acabou de ingressar (idade 0) entra como 0, não como 0/0. Não
  está no anteprojeto; a métrica do recorte é a média dos alunos.
- **Escassez** (`scarcity`) e **concorrência** (`contention`): duas medidas da
  pressão sobre a oferta, com a mesma forma — a razão candidato/vaga do
  vestibular, disciplina a disciplina — sobre conjuntos diferentes. Para cada
  disciplina, `(quantos a querem) / q_x`; a métrica do aluno é a **média** dessas
  razões sobre o seu conjunto, e a do recorte é a média dos seus alunos.

  | | conjunto | quem conta em "quantos querem" | mede |
  | --- | --- | --- | --- |
  | escassez | elegíveis (eq. 42) | quantos são elegíveis à disciplina | demanda **potencial** |
  | concorrência | em que deu lance no período | quantos deram lance nela | demanda **efetiva** |

  "Quantos querem" conta toda a universidade, não o recorte: quem disputa uma
  vaga com o aluno não é só quem está na coorte dele — e a matrícula garantida
  conta como pedido, porque o ingressante não disputou mas ocupa a vaga, e para
  quem recursa a pressão é a mesma. Contar quem quer, em vez de somar as vagas ao alcance, é o que faz
  as duas enxergarem **sobreposição**: dois alunos diante dos mesmos 60 lugares
  disputam o dobro de dois alunos diante de 60 lugares cada um, e uma medida do
  tamanho da oferta daria o mesmo nos dois casos.

  Como têm a mesma unidade, leem-se juntas: **a razão concorrência ÷ escassez é
  a fração da demanda potencial que virou pedido**. Só se pede o que é elegível,
  então a concorrência fica abaixo da escassez.

  Nos gráficos sobrou só a **concorrência**, e do lado das disciplinas: ali ela
  é razão de contagens sobre um bem concreto (`requests / q_x`), e agrupar
  disciplinas por vagas ou por carga mostra exatamente onde a pressão se
  concentra. A escassez segue na tabela por período — é a leitura de demanda
  potencial, que quase não se mexe com o mecanismo e por isso não ganha curva.

  A agregação é média, nunca soma: a contagem de quem quer já traz a população
  dentro do valor de cada aluno, e somar sobre os alunos a contaria duas vezes —
  o número deixaria de se ler como alunos por vaga. Não há aditividade (um
  recorte não é parcela do global) e, em troca, recortes de tamanhos diferentes
  se comparam direto: uma coorte maior não aparece mais apertada só por ser
  maior. As duas são
  do período inteiro e usam a oferta do início dele (`q_x^(t,1)`), então não
  andam entre as rodadas. Disciplinas sem vaga ficam de fora — não são oferta, e
  a razão seria divisão por zero; conjunto vazio dá 0.

  Três ressalvas para o texto. (1) O conjunto elegível é estreito e anda com a
  progressão do aluno: os pré-requisitos deixam elegíveis, no caso típico, as
  disciplinas do período corrente mais as atrasadas, então a escassez de um
  aluno fala do trecho da grade em que ele está, não do catálogo inteiro. (2) O
  conjunto pedido depende do orçamento: a mochila côncava reparte `C_a^(t,r)`
  créditos indivisíveis, então um aluno com `B` créditos dá lance em no máximo
  `B` disciplinas — quem tem pouco crédito pede menos, e não menos em cada uma. (3) A concorrência é demanda revelada *sob este mecanismo*;
  quando o baseline por CR entrar (eqs. 49-50), "pedir" significará outra coisa,
  e comparar a concorrência entre os dois mecanismos compara linguagens de
  pedido, não qualidade de alocação — a escassez não tem esse problema. Nenhuma
  das duas está no anteprojeto.
- **Economia de créditos**: `credits_per_student` e `credits_per_seat` medem a
  *oferta* do início do período (`C_a^(t,1)`, antes de qualquer lance), não o
  que sobrou — esse é o `mean_credits`. Dividida pelas vagas de toda a
  universidade, a oferta dá o preço que uma vaga teria se todo o crédito em
  mãos fosse gasto, e a soma dos recortes dá o preço esperado global (mesma
  convenção da ocupação da eq. 54).
- **CR do período**: o `N_a^(t)` usado nas métricas é o vigente no início do
  período — as notas do período só entram no CR do período seguinte, como numa
  matrícula real.
- **Conclusão de curso**: a eq. (40) vira aprovar em **todas as obrigatórias**
  e somar `elective_hours` entre as optativas aprovadas — não aprovar em cada
  optativa, e é essa substituibilidade que dá ao aluno o que escolher. O
  `hours_to_graduate` é a carga das obrigatórias mais a exigência optativa,
  igual para todos.
- **Jubilamento**: quem chega ao fim dos períodos de residência
  (`max_residence`) sem fechar a grade sai da simulação. É a segunda porta de
  saída, e vem **depois** da conclusão: quem fecha a grade no último período
  permitido conta como concluinte. Com ele e os períodos de ingresso o
  horizonte deixa de ser escolha — `|T| = entry_periods + max_residence − 1` é
  quando a última coorte sai e a universidade fica vazia.
- **A rotina** (`routine_profiles`): o peso do **turno** no interesse de cada
  turma. É a parte do gosto comum a quem tem a mesma vida fora da grade,
  contra o `interest_sigma`, que é a privada de cada aluno. Entra como
  `ln(peso)` somado ao expoente da log-normal, e **não se cancela na
  normalização** porque varia dentro da linha — é nisso que difere de μ.

  Ela tomou o lugar da **atratividade** (`A_x`), que era o nível comum a toda
  a população, por disciplina, e saiu em 16/11/2026. A atratividade dizia "a
  população quer mais esta matéria"; a rotina diz "esta parte da população
  consegue estudar neste turno", que é a heterogeneidade que o modelo precisa
  para que a escolha de turma seja decisão.
- **Interesse e utilidade**: o interesse é um valor por par (aluno, turma,
  período), tirado de uma log-normal de média `interest_mean + ln(peso do
  turno)` e desvio `interest_sigma`, dividido pelo somatório da linha. A
  utilidade é ele visto pelo histórico do aluno: a disciplina elegível vale a
  média das turmas dela mais o que ela destrava um período à frente, tudo
  normalizado sobre `M_a ∪ seq(M_a)`. O anteprojeto não fixa a distribuição
  nem o valor de `U_a`; aqui `Σ_X U_X = 1` por construção, de modo que a
  eq. (43) deixou de ser leitura e virou aritmética.
- **Oferta em turmas** (`q_x`): a grade declara **quantas turmas** cada
  disciplina abre, e o cenário diz **quantos cabem em cada uma**
  (`class_size`, padrão 25). As vagas são o produto. A separação é o que torna
  a lotação um tratamento: a mesma grade sob 20 ou sob 40 por turma é o mesmo
  currículo com o dobro de aperto, sem que nenhuma disciplina mude de
  tamanho relativo às outras. O anteprojeto trata `q_x` como dado; aqui ele é
  fatorado.
- **Ingresso escalonado** (`t_a`, eq. 31): o cenário diz quantos alunos entram
  **por período** (`students_per_period`), e uma coorte entra a cada período
  letivo, do primeiro ao último com ingresso (`entry_periods`, padrão `|T|`). A
  população é, portanto, `students_per_period * entry_periods`, e todas as
  coortes têm exatamente o
  mesmo tamanho. O anteprojeto não fixa a
  distribuição dos ingressos; esta é a que imita um vestibular por semestre.
- **Fase de drenagem** (`entry_periods < |T|`): passado o último período com
  ingresso ninguém mais entra e a população só diminui. Há **uma coorte por
  período com ingresso**, não `|T|` — os
  períodos de drenagem não têm coorte correspondente. Sem ela a última coorte
  vivia um período só e nunca chegava a se formar, de modo que a série por
  coorte media quanto tempo de simulação sobrou em vez de medir o mecanismo.
  Em troca, as coortes deixam de ser intercambiáveis: a primeira encontra uma
  universidade quase vazia e a última encontra a cheia, e depois a
  esvaziando. Pelo mesmo motivo, as curvas **por período** caem no fim porque
  há menos gente disputando, não porque o mecanismo melhorou — o recorte por
  coorte não tem essa distorção.

### Ainda não incluído

- Escolha do mecanismo numa execução **única**: a linha de base só aparece
  dentro do modo de comparação, então não há como abrir os gráficos por período
  nem a tela por aluno de uma execução por CR.
- Teste estatístico sobre as duas amostras: a comparação mostra a dispersão e a
  contagem pareada, mas não calcula p-valor nem intervalo de confiança.
- **Horário no sandbox**: a tela de alocação isolada não tem grade, e o
  horário sai da varredura circular sobre ela — lá a única exclusão mútua que
  resta é a disciplina.
- **Horário de duração variável**: cada turma ocupa um horário, seja de 2 h ou
  de 3 h. O choque é de encontro, não de minuto.
- **Poupança entre rodadas.** Poupar *entre períodos* existe desde que a
  seletividade entrou: o aluno para de investir quando o ganho marginal cai
  abaixo da reserva, e com `credit_memory = "carry"` o saldo passa adiante.
  Poupar **entre rodadas do mesmo período** não: ele reparte na rodada 1 tudo o
  que a reserva deixa gastar. Enquanto o lance perdedor não consome crédito,
  apostar cedo não custa nada, então essa estratégia só apareceria com uma
  regra que cobrasse a aposta.
- Persistência de cenários no servidor: o histórico de execuções fica no
  navegador, mas não há como salvar, nomear ou exportar um cenário.
- **Evasão comportamental.** Há duas portas de saída — concluir e ser jubilado
  por decurso de prazo —, mas nenhuma delas é decisão do aluno. A exclusão é a
  primeira decisão de *desistir* que o modelo tem, mas é de uma disciplina e é
  exógena: sai da log-normal do perfil, não de um cálculo do aluno. A evasão do curso
  responde ao mecanismo, e é contra a linha de base por CR que ela precisaria
  ser medida — agora que ela existe, é comparação possível.
- **O nível comum por disciplina.** A rotina sincroniza o gosto por turno, e
  não há análogo dela um andar acima — o "todo mundo quer esta matéria", que
  era a atratividade. O que separa as disciplinas hoje é só o desvio privado
  de cada aluno, governado por `interest_sigma`.
- **A fama da turma fácil.** A dificuldade é da disciplina, então não há turma
  fácil a descobrir dentro de uma matéria. Recuperá-la exigiria devolver a
  dificuldade ao nível da turma e publicar algum sinal sobre ela.
- **A varredura do teste de invasão.** O eixo de estratégia já põe as frações
  coexistindo e disputando entre si — exemplares de cada perfil na mesma
  coorte —, mas a **proporção** é fixa: 1/5 em cada nível. Varrer a fração de
  seletivos de 0 a 100% é o que distinguiria estratégia posicional (uma
  corrida que redistribui sem mudar o bolo) de mecanismo que premia a espera.

## Os quatro eixos de perfil

Todo aluno carrega quatro rótulos, e a coorte contém o **mesmo número de
exemplares de cada combinação**: nos padrões, 3 × 3 × 5 × 3 = 135 combinações
com 2 exemplares, 270 alunos por período com ingresso. O tamanho da coorte não
é digitado — ele é `exemplares por perfil × número de combinações` —, e é
assim que todo perfil recebe o mesmo número de exemplares em toda coorte, sem
sobra a girar entre elas.

Três são **traço**: governam sorteios, e o aluno não os conhece.

| Eixo | O que governa |
| --- | --- |
| desempenho | a normal dividida da nota — nota mais provável, chance de 0, chance de 10 |
| disponibilidade | a log-normal das horas do período, resorteada a cada um |
| rotina | o multiplicador do interesse por **turno** da turma |

A **rotina** é a vida do aluno fora da grade, e entra no sorteio do interesse
como `ln(peso)` somado ao expoente — a mesma conta dita na unidade em que se
lê. Os três perfis padrão:

| rotina | diurnas | noturnas |
| --- | --- | --- |
| Diurno | × 2 | × 1 |
| Noturno | × 1 | × 2 |
| Indiferente | × 1 | × 1 |

O **indiferente é o neutro**, e os outros dois dobram o lado que lhes convém
em vez de penalizar o outro — depois da normalização da linha as duas formas
dão a mesma preferência, e dobrar é a que se lê sem decimal. Ela não é corte
no pedido: quem trabalha de dia continua podendo cursar uma turma diurna, só a
quer menos.

O quarto é **estratégia**: entra na decisão do aluno, e por isso é valor fixo
em vez de distribuição. Um perfil de estratégia é tratamento, não descrição —
não se mede a frequência de especuladores no mundo, declara-se quais existem
para ver como cada mecanismo os trata.

| Eixo | Campo | O que faz | Neutro |
| --- | --- | --- | --- |
| seletividade | `selectivity` | a exigência `S_a`, repartida entre as elegíveis | 0 |

```
reserva s_a = S_a / |elegíveis do período|
pede X                 enquanto U_X     ≥ s_a
investe o k-ésimo em X enquanto U_X / k ≥ s_a
```

A **seletividade** é a utilidade de reserva no sentido da literatura de
desenho de mecanismos — o payoff da opção externa, contra o qual se escreve a
restrição de participação. Dividida pelas elegíveis porque `Σ_X U_X = 1`: a
utilidade média de uma elegível é exatamente `1/|M_a|`, e `S_a` se lê direto
como **múltiplo da disciplina média**. Dito ao contrário, `S_a` é a soma das
reservas — o aluno reparte a própria exigência entre as disciplinas que tem
diante de si.

Os cinco níveis padrão **têm os próprios valores como nome**, porque o que
separa os grupos é literalmente quantas disciplinas cada um pede. Na grade
padrão, com 33 elegíveis por período:

| S | disciplinas pedidas | fração das elegíveis |
| --- | --- | --- |
| 0 | 33 | 100% |
| 0,5 | 20,5 | 62% |
| 1 | 11,7 | 35% |
| 1,5 | 6,7 | 20% |
| 2 | 4,0 | 12% |

Ela age em **dois lugares**, e é essa a diferença entre os mecanismos:

- **corta o conjunto** — o que está abaixo da reserva não é pedido, nos dois
  braços;
- **para o gasto** — na mochila do leilão, o aluno investe enquanto o ganho
  marginal do próximo crédito ficar acima da reserva, e depois **poupa**. Como
  o orçamento carrega entre períodos (eq. 36), poupar é decisão, não desperdício.
  Na linha de base por CR não há análogo: lá não há investimento marginal que
  se interrompa.

Em 0 não há corte nenhum: é o **especulador**, que pede tudo e gasta o
orçamento inteiro. Acima de 1 o aluno fica mais exigente que a média e
acumula saldo para um período em que valha a pena.

**A concentração saiu em 16/11/2026.** Ela era o expoente do score sobre a
utilidade — 1 no lance sincero, acima concentrando, negativo invertendo —, e
com ela saiu a pergunta de *para que lado distorcer compensa*. Concentrar
crédito no que mais se quer passou a ser **premissa** do modelo: o lance é
proporcional à utilidade, que é o ótimo da relaxação contínua da mochila
côncava. O que se ganha, além da leitura, é tempo de solver — ver *O que a
concentração 0 custava ao resolvedor*.

### O desempate e o viés saíram da preferência

A eq. (22) do anteprojeto somava ao lance três camadas — o viés retificado
β̂ (eq. 21), o fator de desempate α̂ (eq. 20) e a perturbação ε —, e
justificava α̂ ∈ [0, 1) assim: *estritamente menor que 1 crédito*, de modo
que o desempate nunca invertesse uma diferença de lance.

**A garantia vale entre dois pares e não sobrevive à soma.** O WDP não
compara preferências duas a duas: ele maximiza `Σ p·z` sobre todos os pares
ao mesmo tempo (eq. 8). Com α̂ até 1 por par e milhares de pares alocados, a
massa de desempate do objetivo chega à ordem de milhares de créditos. Medido
numa rodada do cenário cheio (2.268 alunos, 69.033 pares de demanda, 6.400
vagas preenchidas):

| camada do objetivo | massa |
| --- | --- |
| lance | 29.494 |
| desempate (α̂) | **3.704** |

E a consequência não é teórica. Resolvendo a mesma instância duas vezes, as
duas até o ótimo provado:

| objetivo | tempo | créditos de lance alocados |
| --- | --- | --- |
| `lance + α̂ + ε` (eq. 22) | 194,4 s | 30.014 |
| só o lance, inteiro | **65,8 s** | **30.029** |

A formulação antiga entregava **quinze créditos a quem foi superado no
lance** — não é arredondamento, são vagas mudando de dono — e cobrava três
vezes o tempo de solver por isso, porque a camada fracionária cria um
contínuo de soluções quase ótimas que o ramifica-e-corta tem de varrer.

Então **α̂ e β̂ saíram**. Com β̂ vai junto a política universitária explícita
no lance; ela continua expressável pelo cenário — oferta de vagas e
pré-requisitos —, que age antes do leilão. A matriz α some de
`simulation.setup`; como ela era o **último** sorteio da inicialização,
tirá-la não desloca o gerador: população, notas, disponibilidade e interesse
saem bit a bit iguais, e a diferença entre o antes e o depois é só do modelo.

### O desempate saiu da PLI

Tirar as camadas da soma deixa a pergunta de pé: o ε ainda tem de desempatar.
A resposta é que, na PLI, ele **não** desempata — e as duas saídas possíveis
foram implementadas e medidas antes de se chegar nisso.

**Somar** é o que a eq. (22) fazia, e não tinha como funcionar. Para o
desempate nunca inverter uma unidade da grandeza principal, a soma dele sobre
os pares alocados precisa ficar abaixo de 1 — cada termo abaixo de `1/(total
de vagas)`, o que no cenário cheio dá `9·10⁻⁵`. Só que **metade das demandas
são lances de 1 crédito**: 35.684 pares exatamente empatados, de 69.033. Para
separá-los o passo teria de ser `2,5·10⁻⁹`, uns 400× abaixo da tolerância de
`10⁻⁶` do CBC. Não é questão de calibrar a escala — entre o teto e a
tolerância cabem ~90 níveis distintos, e seriam precisos 35 mil.

**Resolver em dois estágios** era a saída elegante, e chegou a ser o desenho
do `wdp_solver`:

```
1.  max Σ lance·z     sujeito a vagas, carga, exclusão          → M
2.  max Σ ε·z         sujeito a vagas, carga, exclusão
                      e Σ lance·z ≥ M
```

Com a camada de lance presa pela restrição, a escala do ε fica livre e o
problema numérico desaparece de fato. Só que ele troca um problema numérico
por um combinatório pior: `Σ lance·z ≥ M` prende a região viável à **face
ótima** do problema, e dentro dela todo nó do *branch and bound* tem
praticamente o mesmo limitante. Nada poda, e o resolvedor enumera a face
inteira.

Medido em 14/11/2026, nos modelos extraídos dos processos travados:

| variáveis binárias | restrições | tempo sem fechar |
| --- | --- | --- |
| **1.168** | 3.185 | **5 h 38** |
| 9.640 | 21.896 | 3 h 10 |

Mil cento e sessenta e oito variáveis binárias. Não é porte — é a
degenerescência da face ótima, e ela é **pior justamente quando há mais
empate**, que é o caso para o qual o estágio 2 existiria. Uma comparação de
20 execuções por braço passou cinco horas sem produzir resultado nenhum.

Por isso o ε ficou **fora da PLI**. Ele continua decidindo onde custa nada:
na varredura gulosa, que ordena por `(-preferência, -desempate)`, e na
ditadura serial, que compara dois a dois. `Demand` segue carregando os dois
números em campos separados — o que mudou é que a PLI lê só o primeiro.

**O que isso custa, declarado:** o ótimo da PLI não é único, e qual deles o
CBC devolve depende do caminho de busca dele. O *valor* do objetivo é único —
e é ele que a comparação mede —, e a alocação é reprodutível para um mesmo
binário do CBC. Entre plataformas diferentes não há garantia: o PuLP embarca
um binário por sistema, e nada assegura que duas compilações ramifiquem
igual.

**E isso deixa o CR assimétrico em relação aos dois leilões, de propósito.**
`ranking_greedy` resolve por ditadura serial e desempata por ε; os dois
leilões resolvem por PLI e não desempatam — entre alocações de mesmo lance
agregado, quem escolhe é a busca do CBC. Pôr o guloso também no braço
de créditos restauraria a simetria, a unicidade e a reprodutibilidade entre
máquinas, mas custaria a **maximização de bem-estar**, que é o que a PLI
entrega e o guloso não: ele nunca recusa um lance de 30 para atender dois de
20. Entre as duas perdas, preferiu-se a assimetria. O eixo do resolvedor
segue medível em `credits_greedy` × `credits_ilp`, que é onde ele mora por
desenho.

Para a redação, afirma-se o que se tem: o **valor** alocado é único e
reprodutível; a **alocação** é reprodutível para um mesmo binário do CBC.
A medição que fecharia a questão — forçar dois ótimos distintos da mesma
instância e comparar as métricas agregadas — ainda não foi feita.

**Em troca, o estágio que sobrou ficou mais rápido.** Sem o ε no objetivo,
toda preferência do braço de créditos é inteira — é o lance em créditos —,
então o objetivo só pode melhorar de 1 em 1. O `wdp_solver` passa isso ao CBC
(`increment 0,99`), que então poda todo nó cujo limitante não supere o
incumbente por uma unidade inteira. A poda é exata: não existe solução entre
o incumbente e o próximo valor possível. No braço do CR a preferência é o
coeficiente de rendimento, que não é inteiro, e a opção não é passada.

### Por que o ε nunca funcionou na PLI

Fica registrado porque o diagnóstico vale e as tentativas descartadas poupam
quem for refazê-las.

A perturbação estocástica existe para tornar **única** a solução ótima: ela
decide onde os lances empatam. O teto do anteprojeto é `1/(|A|²·|B|)`, justo
para o argumento que o sustenta — somados todos os ε de uma solução o total
fica muito abaixo de um crédito, então a perturbação nunca desloca uma solução
de lance agregado maior.

O problema é o outro lado: em escala realista esse teto fica **abaixo da
tolerância numérica do resolvedor**.

| |A| | |B| | teto de ε | some em 10⁻⁶? |
| --- | --- | --- | --- |
| 3 | 3 | 3,7·10⁻² | não |
| 40 | 63 | 9,9·10⁻⁶ | não |
| 180 | 63 | 4,9·10⁻⁷ | **sim** |
| 270 | 288 | 4,8·10⁻⁸ | **sim** |

O CBC trabalha com tolerância de integralidade de 10⁻⁶, então em qualquer
preset de tamanho real ele **não vê** o ε: onde o modelo diz que há
desempate, o resolvedor vê empate e devolve um ótimo qualquer entre os
empatados. Isso **não é novidade das turmas** — já valia com |A| = 180 e 63
disciplinas. O resolvedor guloso, que trabalha em ponto flutuante de dupla
precisão e não tem tolerância de integralidade, sempre enxergou o ε
normalmente — era uma assimetria entre os dois braços, e hoje é uma
assimetria declarada.

Enquanto o ε esteve no mesmo objetivo, a execução continuava reprodutível
(o CBC é determinístico dado o mesmo modelo), mas não era o ε que decidia
entre empatados, e sim o caminho interno do resolvedor. Medido na época: dar
ao CBC um incumbente inicial — a mesma PLI, só com um piso conhecido —
**mudava a alocação**, que é exatamente o sintoma de ótimos múltiplos.

**A correção óbvia foi testada e não serve.** Escalar a função objetivo por
uma constante preserva o argmax e põe o ε de volta acima da tolerância, e por
isso parecia resolver os dois problemas de uma vez. Medido no mesmo período:

| escala | total | pior PLI | mediana |
| --- | --- | --- | --- |
| 1 (como está) | 32,0 s | 28,0 s | 0,07 s |
| 10⁶ | 4,2 s | 0,7 s | 0,07 s |
| 10⁸ | 57,2 s | **52,6 s** | 0,07 s |
| 10¹⁰ | 10,6 s | 6,3 s | 0,07 s |

Não é monotônico — 10⁸ é pior que a escala 1 —, e **cada escala devolve uma
alocação diferente**. O ganho de 10⁶ foi sorte da árvore de busca naquela
instância, não condicionamento.

O que o teste mostra é que **nenhuma escala resolve enquanto as duas camadas
dividem um objetivo**: aumentar a escala tira o ε da tolerância e, no mesmo
movimento, aumenta o peso dele contra o lance. Separá-las em dois estágios
escapa disso — e esbarra na degenerescência descrita na seção anterior. As
três saídas estão fechadas, e é por isso que a PLI não desempata.

### O que a concentração 0 custava ao resolvedor

Esta seção é **histórico**: a concentração saiu do modelo em 16/11/2026, e
com ela o caso patológico abaixo. Fica registrada porque a medição é a razão
de o eixo ter saído.

Medido em 06/11/2026, coorte de 324, 288 turmas, 3 períodos, braço com PLI:

| população | total | pior PLI | mediana |
| --- | --- | --- | --- |
| os quatro eixos completos | 30,9 s | **27,0 s** | 0,06 s |
| só o perfil sincero (mesma coorte) | 4,2 s | 0,5 s | 0,39 s |
| sem a seletividade 0 | 14,5 s | 11,3 s | 0,30 s |
| sem a concentração 0 e −1 | 2,6 s | 0,2 s | 0,07 s |

A leitura é a mediana contra o pior caso: **quase toda rodada fecha em
centésimos de segundo, e uma em cada dez come trinta**. Não é tamanho — a
rodada de 27 s tem o mesmo número de lances que as de meio segundo.

A causa é a **concentração 0**. Com expoente zero todo score vale 1, a mochila
côncava reparte o orçamento igualmente por tudo o que está disponível, e o
aluno chega à rodada com algumas dezenas de lances de valor idêntico. Com a
preferência final em `lance + ε`, as preferências ficam quase iguais num
conjunto enorme: a relaxação linear fica degenerada e o *branch and bound*
não tem o que podar. É a simetria, não a escala. (A medição desta seção é de
06/11/2026, quando α̂ ainda estava na preferência e agravava o efeito; a
causa — lances idênticos — não mudou.)

Vale dizer o que **não** é a causa, porque os dois suspeitos naturais foram
descartados por medição: não é a coorte (com os mesmos 324 alunos sinceros o
pior caso cai para 0,5 s) e não é a seletividade (tirá-la deixa 11,3 s).

É propriedade do problema, não defeito: o WDP é uma mochila múltipla 0-1 com
itens compartilhados e grafo de conflito, NP-difícil, e o tempo de um
resolvedor exato nela tem variância alta por natureza. O que a concentração 0
faz é produzir instâncias que caem no lado ruim dessa variância com frequência
que importa — e o empate numérico do ε (seção anterior) é o que as deixa sem
o que podar.

**A consequência prática é de escopo, e é decisão de quem calibra**: com os
seis níveis de concentração, uma comparação de N seeds nos dois braços não
fecha em tempo útil. As saídas medidas são tirar a concentração 0 e −1 do
eixo (2,6 s, mas perde dois controles), rodar o braço guloso para explorar
(linear e previsível: 0,8 s para a coorte cheia em dois períodos), ou dar ao
CBC um limite de nós — determinístico, mas aí a PLI deixa de ser exata.

### O que custa caro na PLI

Medido em 14/11/2026 sobre instâncias reais do cenário cheio, extraídas de uma
comparação que não fechava.

**Não é a grade não pedida.** O modelo é dimensionado pelo conjunto de
demandas, não pelo produto aluno × turma: `wdp_solver._model` cria uma variável
por par **que recebeu lance**, e pula a linha de vaga da turma sem lance
(`if by_good.get`), a de carga horária do aluno sem lance (`if terms`) e a de
conflito de quem não pediu duas turmas da mesma disciplina (`if len(clique) >
1`). A restrição de elegibilidade já está inteiramente aproveitada — o par que
ninguém pediu é 0 por definição (eq. 2) e não chega ao CBC.

**Não é o tamanho.** É o **empate**. Nas duas instâncias que ficaram 2h24 sem
fechar, metade ou mais das variáveis tinha coeficiente 1:

| instância | variáveis | coeficiente 1 |
| --- | --- | --- |
| menor | 24.633 | 14.957 (60,7%) |
| maior | 85.600 | 40.871 (47,7%) |

Com dezenas de milhares de variáveis valendo o mesmo, trocar duas delas não
muda o objetivo, a face ótima é enorme e o limitante da relaxação não cai ao
ramificar. É a mesma degenerescência que derrubou o segundo estágio do
desempate (ver "O desempate saiu da PLI"), agora no primeiro.

**O caro é provar, não achar.** Rodando a menor com 90 s de limite, o CBC chega
ao incumbente **6.224** com limitante **6.226,33** em segundos e depois fica:
6.500 → 6.700 nós com 1.376 nós abertos, estáveis. Falta fechar **2 unidades**
em 6.224 — 0,03% — e é isso que não termina.

Medido o atalho, para registro:

| instância | objetivo | exata | `allowableGap 3` |
| --- | --- | --- | --- |
| 12.136 vars | 6.224 (limite 6.226,33) | não fechou | **4,3 s**, 116 nós |
| 85.600 vars | 54.843 (limite 54.845) | não fechou em 2h24 | **45,6 s**, 128 nós |

Com `allowableGap 1` não fecha (300 s, árvore aberta). **A folga não foi
adotada**: a PLI do trabalho é exata, e o custo disso está aqui declarado em
vez de contornado. O que se faz pelo lado do modelo é reduzir o pedido — ver o
teto do orçamento `C_max`, que corta 40% das variáveis.

### Onde a memória de uma simulação está

Medido em 14/11/2026, cenário cheio, um worker:

| | pico |
| --- | --- |
| processo Python | 738 MB |
| `cbc.exe` que ele espera | 526 MB |
| **por worker** | **~1,3 GB** |

Os dois picam **juntos**, porque o Python segura tudo enquanto espera o
solver — por isso somam, e por isso o teto de `--workers` é a memória livre
dividida por 1,3 GB, e não o número de núcleos.

Do lado do Python, quase tudo é **uma estrutura só**: o interesse, que é uma
linha por (aluno, período) sobre a grade inteira. No cenário cheio são
2.592 × 23 × 288 = 17,2 milhões de valores, e em dicionários aninhados cada
float custava ~47 bytes contra os 8 do array — 767 MB dos 817 MB que o
`prepare()` alocava.

`behavior.InterestMatrix` guarda o array que o sorteio **já produzia** e monta
a linha no acesso. Como ela é um `Mapping`, lê-se igual ao dicionário que
substituiu (`matriz[(aluno, período)]`, `.values()`, `set(matriz)`) e nenhum
chamador mudou. O `prepare()` caiu de 817 para 175 MB, e o custo é 10 µs por
linha — 0,62 s numa simulação de 7,2 min, 0,14%. Os valores são bit a bit os
mesmos: a troca foi verificada comparando o SHA-256 dos 17,2 milhões antes e
depois, que bateu.

A matriz existe inteira na memória porque **nada é sorteado dentro do laço** —
é o preço da propriedade de que mexer numa vaga não desloca as preferências de
todo mundo. E ela escala com alunos × períodos × turmas: dobrar a coorte e a
grade multiplica por quatro.

### Por que não há algoritmo genético

Houve um, sobre quatro genes, com as coortes evoluindo independentes. Saiu em
05/11/2026, e o motivo é de escopo: a pergunta que ele existia para responder
— *compensa reportar torto?* — fica respondida com **tipos fixos** em vez de
busca. Evolução diria *qual* distorção é a melhor; tipos fixos dizem *se* uma
distorção dada compensa, que é o que o trabalho precisa e o que se lê sem
aparato.

Com ele saíram os dois **genes de sinal** — viés de oferta e viés de aprovação
—, e com eles os índices publicados por disciplina. A consequência a declarar:
o aluno não percebe que uma turma aprova mais que a outra. A dificuldade por
turma continua afetando a nota, então o efeito bola de neve sobrevive, mas some
o comportamento de caçar o professor leve.

### Onde o resultado fica

`/compare` grava a execução em **`resultados/`** (git-ignored;
outro caminho em `LEILAO_RESULTS_DIR`) e devolve `saved_to`; a porta de
terminal (`make compare`) grava no mesmo lugar e no mesmo formato. O formato é
o mesmo do histórico do navegador — `{kind, at, config, result}` —, de modo que
carregar um arquivo na interface é só acrescentá-lo à lista, sem conversão.

A API continua **sem estado**: nenhuma rota lê de lá, nenhuma depende de o
arquivo existir, e apagar a pasta não muda comportamento nenhum. Falha de
escrita não derruba a requisição — `saved_to` sai nulo e o resultado vai
inteiro, porque perder uma comparação de muitos minutos pelo registro que não
coube seria o pior dos dois mundos.

Disco em vez de `localStorage` porque uma comparação custa `N × braços`
simulações completas, e o navegador tem poucos megabytes para o domínio
inteiro, disputados com todas as outras.

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
| `make compare` | uma comparação fora do servidor — ver abaixo |
| `make install` | venv e dependências |

### Comparação grande: fora do servidor

A rota `/compare` roda a comparação inteira dentro de um POST, e no cenário
cheio 20 simulações por braço são horas de CPU — tempo demais para uma
requisição sobreviver a um `--reload`, a um navegador que desiste ou a um
Ctrl+C, e tempo demais para ficar sem sinal de progresso. Para esses casos a
mesma comparação tem uma porta de terminal:

```sh
make compare SCENARIO=resultados/comparison-20261111-102551.json RUNS=20
# ou, direto:
python -m leilao.cli --scenario <arquivo>.json --runs 20 --workers 3
```

`SCENARIO` é um JSON: um resultado já gravado (de que se lê o `config`) ou um
cenário solto. Ela imprime cada simulação quando termina, grava em
`resultados/` no mesmo formato de sempre, e o arquivo entra na interface por
**Carregar resultado**. Quem monta a resposta é `api/service.py`, o mesmo
módulo que a rota usa — não há duas implementações da comparação.

`--workers` é quantas simulações correm ao mesmo tempo, e o teto é a **memória
livre, não o número de núcleos**. No cenário cheio cada worker pede dois picos
ao mesmo tempo — 738 MB do processo Python e 526 MB do `cbc.exe` que ele está
esperando —, e como as simulações são o mesmo trabalho começado junto, elas
picam juntas: a conta é a memória livre dividida por uns 1,3 GB. Se a máquina
começar a paginar, o lote deixa de terminar. `--workers 1` roda em linha, sem
paralelismo, e é como se depura uma simulação que falha.

No Windows os alvos delegam para o PowerShell (`dev.ps1`), então funcionam
igual chamados do PowerShell, do `cmd` ou do Git Bash. No Mac, Linux e UNIX
os mesmos alvos rodam no `sh`; o `make install` cria o venv com o `python3`
do `PATH`.

### Usando a interface

Em `http://localhost:5173`, a barra lateral tem **Configurar** (o formulário do
cenário), **Projeto** (visão teórica do modelo e das métricas), **Grade** (a
oferta desenhada), **Submochila** (a decisão de um aluno, passo a passo) e a
lista de **Execuções** já feitas, cada uma identificada por data e hora.

A tela **Grade** traz duas grades, porque são duas regras de conclusão. A das
**obrigatórias** é a cadeia de pré-requisitos lida da esquerda para a direita:
cada coluna é um período, que não se configura — sai da indução sobre os
pré-requisitos. A das **optativas** não tem período a mostrar (nenhuma destrava
nada), e sem eixo o bloco tende ao quadrado: o número de colunas é a raiz do
catálogo. Com o mouse sobre uma disciplina, a cadeia inteira dela se acende — o
que ela exige e o que ela destrava, no mesmo tom, porque quem separa os dois
lados é a coluna de cada um — e o resto da grade recua. Os conectores não levam
ponta pelo mesmo motivo: a grade corre num sentido só.

O botão de "Configurar" faz uma coisa só: **comparar os modelos** — o mesmo
cenário roda em cada braço, `N` vezes, com as seeds de 1 a `N`. Três campos do
cenário não vão para lá: a **seed** (ali ela vira o eixo da amostra) e o
**resolvedor** (ali ele vira eixo do experimento, e cada braço impõe o seu). O
**multiplicador do retorno** vai, mas só vale no braço que acumula — os outros
o zeram. No lugar entram **quais modelos rodar** e **simulações por modelo
(N)**.

Os modelos são **caixas de seleção**, uma por braço, cada uma com o traçado
com que o modelo aparece nos gráficos. Rodar menos modelos custa
proporcionalmente menos tempo, e é o que se faz enquanto se calibra o cenário;
os painéis que comparam os ausentes simplesmente não aparecem. A última caixa
marcada não se desmarca: sem braço nenhum não há o que rodar.

A **carga de optativas para concluir** (X) entrou no formulário em 17/11/2026,
junto com o gráfico de progresso — ela é o que separa o denominador dele da
carga das obrigatórias. O campo recusa exigir mais do que o catálogo oferta:
a folga entre os dois é o que dá ao aluno o que escolher, e sem ela ninguém
concluiria.

O **tamanho da coorte não se digita**: ele sai de *exemplares por perfil* vezes
o número de combinações, e o painel mostra o número derivado. É a conta que
dimensiona `class_size` — a coorte repartida entre as turmas de cada disciplina
de entrada tem de caber nelas, e o formulário recusa quando não cabe.

Em "Configurar", a barra lateral **direita** lista os **cenários salvos** —
não há catálogo fixo. O formulário abre nos **valores padrão**, que são o
fatorial descrito abaixo, e qualquer alteração passa a valer como
**Personalizado**, que fica guardado: dá para carregar um salvo e voltar ao seu
cenário sem perdê-lo. Clicar em *Personalizado* sem ter mexido em nada devolve
os valores padrão.

O botão *Salvar cenário* está na barra de ações,
à direita do *Comparar modelos* e contornado em vez de preenchido: a ação
primária é comparar, e salvar é o que se faz antes ou depois dela. Ele abre em
dois tempos — o primeiro clique revela o campo do nome, o segundo (ou Enter)
grava —, porque salvar num clique só encheria a lista de "Cenário 1".

**O nome é a identidade.** Salvar com um nome que já existe *substitui* aquele
cenário, preservando o id, e é assim que se edita um salvo: carregue, mexa,
salve com o mesmo nome. O botão avisa antes do clique, trocando "Salvar" por
"Substituir". A comparação não distingue maiúsculas nem espaços nas pontas —
"Meu cenário" e "meu cenário" como duas entradas seria confusão, não liberdade.

Guardam-se até 30, em `localStorage`, numa chave **separada** da do histórico:
limpar execuções não apaga cenários, e um formato que mude de um lado não
derruba o outro. Cada um é a **entrada** e não o resultado — uns poucos kB
contra os megabytes de uma execução —, e por isso cabem muito mais aqui.

**A grade não vai junto.** Ela é a mesma para todos os cenários, e o formulário
não a edita, então um salvo guarda só os parâmetros: população, horizonte,
rodadas, a faixa de crédito, perfis e σ. Guardar uma cópia da oferta seria
guardar algo que
pode divergir da única que existe — recarregar um salvo pega a grade corrente,
e mexer nela muda todos os cenários de uma vez. É também por isso que a lista
não mostra contagem de disciplinas: ela seria a mesma em toda linha e não
separaria nada. Mostra alunos, períodos e a data.

O cenário padrão é o **fatorial**. Ele não imita um currículo real: é um
delineamento experimental. Dois eixos — carga e dificuldade — cruzados, com
**todas as seis combinações presentes em todo período da grade**, de modo que
os dois ficam balanceados dentro de cada período e, portanto, ortogonais tanto
ao período quanto às vagas. Uma diferença entre grupos nos gráficos é da
grandeza em tela, nunca de composição.

São 36 obrigatórias (6 × 6) em cadeia triangular e 27 optativas, com a oferta
em **funil** — 9 turmas no 1º período, 4 no 6º —, 270 alunos por coorte em 8
coortes (2 160 ao todo), 3 rodadas por período e 23 períodos — 16 de
residência, o que faz o jubilamento morder. O preço do desenho é que **vagas
sai do fatorial no obrigatório**: elas variam por período, então ali não dá
para separar "tem poucas vagas" de "é avançada". Quem recupera o eixo são as
optativas, que não têm período: os três patamares de oferta cruzam o mesmo
cruzamento de carga × dificuldade.

O terceiro eixo é **dentro** da disciplina: o **turno** da turma. Um terço
delas, arredondado para baixo, é noturno, e cada turma cai num dos 12 horários
diurnos ou dos 6 noturnos. É esse eixo que a rotina do aluno lê.

**O tamanho da coorte vem dos perfis, não da oferta.** São 270 alunos por
período com ingresso — 3 × 3 × 5 × 3 combinações, dois exemplares de cada —, e
é a oferta que tem de acompanhar. Medido numa seed, com os parâmetros de
03/11/2026, ir de 40 para 180 por coorte derrubava a conclusão de 77% para 40%
e subia o jubilamento de 23% para 60%; multiplicando toda a oferta por 4,5 ela
voltava a 76% com o mesmo tempo de formatura. É escassez de vaga, não efeito do
tamanho da coorte.

A lotação é campo do cenário (`class_size`, 45 por padrão) e é o botão que
acompanha a coorte sem mexer na estrutura: as 9 turmas de cada disciplina de
entrada dão 405 vagas, a coorte repartida põe 30 em cada uma e sobram 15 por
turma para quem recursa.

Isso mexe na leitura do jubilamento: enquanto ele morde, o tempo de formatura é
censurado e volta a medir quem sobreviveu em vez de quem foi rápido.

O preset **Computação** saiu em 31/10/2026. Ele imitava um currículo real — 6
períodos × 6 disciplinas encadeadas mais 24 optativas —, e o que o derrubou foi
justamente o que o Fatorial resolve: ali carga, dificuldade e vagas andavam
juntas, de modo que nenhum recorte por disciplina separava os eixos.

A população do cenário padrão, nos dois eixos de traço com distribuição. **O
nome carrega o eixo** de propósito: "Alto" e "Alta" nos dois lados fariam "alto-baixo" virar charada em
legenda de gráfico, e com o eixo no rótulo a combinação se lê sozinha.

| Perfil de desempenho | moda · chance de 0 · chance de 10 | O que ele produz |
| --- | --- | --- |
| Alto desempenho | 9,0 · 0,05% · 3,0% | média 7,44 · aprova 90,3% |
| Médio desempenho | 8,0 · 0,50% · 0,8% | média 6,40 · aprova 77,4% |
| Baixo desempenho | 6,5 · 3,00% · 0,15% | média 4,96 · aprova **55,1%** |

| Perfil de disponibilidade | moda · chance de encher | O que ele produz |
| --- | --- | --- |
| Alta disponibilidade | 22 h · 50% | teto mediano 23 h · enche de fato 50,0% |
| Média disponibilidade | 16 h · 5% | teto mediano 17 h · enche de fato 5,1% |
| Baixa disponibilidade | 8 h · 0,1% | teto mediano 9 h · enche de fato 0,1% |

São 9 combinações entre os dois, e 135 com a seletividade e a rotina. A
aprovação é em dificuldade 1 e primeira tentativa, que é a situação que os três
parâmetros descrevem, e é **derivada**, não editada; a carga cheia é a fração
dos semestres em que o teto alcança `W_a = 24`, medida sobre 40 mil sorteios.

A média fica bem abaixo da moda em todos os três, e isso não é desajuste: a
cauda esquerda é longa — quem vai mal vai muito mal —, e numa distribuição
assim o pico não é o centro de massa. É por isso que a moda é o parâmetro e a
média é derivada: com a média presa, moda alta com poucos dezes não fecharia, e
o formulário teria faixa a recusar.

O **Baixo desempenho** está calibrado por essa média derivada: 4,96 encosta em
`n_min = 5`, e ele reprova em torno de metade das vezes. É a calibragem
que dá à ordenação por CR o que ordenar — sem dispersão ninguém reprova, a
recursada some do cenário e a eq. (57) não mede nada.

A troca da Beta pela normal dividida (04/11/2026) **recalibrou a aprovação para
baixo** nos dois grupos de cima: o Alto saiu de 99,9% para 90,3% e o Médio de
89,5% para 77,4%, enquanto o Baixo subiu de 51,5% para 55,1%. A causa é a cauda
esquerda, que a Beta sobre (0, 1) não conseguia produzir sem derrubar a média
junto.

Ou monte o seu: a tela de configuração tem **Configurações gerais** (o N da
comparação, o horizonte e o ritmo de ingresso, as rodadas e a faixa de
crédito), **Interesse**, **Notas** e **Disponibilidade** — cada uma destas ao
lado da prévia da distribuição que seus parâmetros produzem —, e mais três sem
prévia: **Seletividade**, **Rotina** e **Horários**. As duas primeiras não
descrevem distribuição nenhuma, e sim uma regra de decisão e um par de pesos;
a de horários é o par `day_slots` × `night_slots`, com o número de turmas por
horário na nota do painel. Cinco delas editam listas de **perfis**, e editam
coisas diferentes porque descrevem objetos diferentes: cada linha de **Notas**
traz nome, nota mais provável e as duas chances de ponta; cada linha de
**Disponibilidade** traz nome, moda em horas e chance de encher a carga; cada
linha de **Seletividade** traz nome e um número; cada linha de **Rotina** traz
nome e os dois pesos. Os botões criam e removem grupos. Não há campo de porcentagem — a repartição é
igualitária. O rodapé de cada seção fala do **próprio** eixo: quantos grupos
ele tem e que fatia da coorte cabe a cada um (com três, 33,3%), e só então
quantas combinações isso dá com o outro eixo. A fatia da combinação não entra
ali porque a seção não a edita. A linha selecionada é a que a prévia ao lado
desenha, uma curva por vez. A **oferta não se edita ali**: a grade é **única
no aplicativo** (`presets.GRADE`), igual em todo cenário, e quem a mostra é a
tela Grade. Ao executar, a simulação entra no histórico e a tela abre nela.

Ao lado dos campos de **notas** e de **interesse**, a tela desenha a
distribuição que aqueles parâmetros produzem, recalculada a cada tecla
(`web/src/distributions.ts`). São as mesmas dez faixas que a simulação reporta,
de modo que a prévia e o histograma do resultado se leem lado a lado. A das
notas sai em forma fechada da acumulada da normal dividida — exata, e por isso
não treme enquanto se digita —, e traz ao pé a nota mais provável, a aprovação
e as **duas chances de ponta já transformadas** pelo recorte, que são o que
aquela disciplina de fato produz.

As duas pontas da curva **não** fecham no eixo, e é o ponto da distribuição: a
nota 0 e a nota 10 carregam toda a massa que o latente põe fora da escala. São
os dois átomos da censura, e aparecem tão altos quanto a chance que o perfil
declarou.

Ela desenha **um caso de cada vez**, escolhido nos campos abaixo do próprio
gráfico: uma disciplina de uma dada dificuldade (decimal) numa dada tentativa
(inteiro). O padrão é dificuldade 1, tentativa 1, que é a situação que os três
parâmetros do perfil descrevem. Os campos ficam junto da curva de propósito:
eles **são** a legenda do caso, e sem isso duas leituras diferentes do mesmo
gráfico ficariam indistinguíveis.

Como os dois entram nos expoentes pela razão `tentativa/dificuldade` (e pela
sua recíproca), dificuldade 2 na segunda tentativa desenha exatamente o mesmo
gráfico que dificuldade 1 na primeira — o que serve de conferência da própria
prévia. A **utilidade saiu** da fórmula da nota em 04/11/2026: ela já governa o
que o aluno pede e o que ele exclui, e deixá-la mexer também na nota era a
única peça sem forma justificada e a única que fabricava vão entre os
mecanismos por conta própria.

Em `t > 1` o gráfico é a nota que a **população inteira** tiraria naquela
tentativa, e não a dos recursantes: quem recursa é quem foi mal, então a
amostra real de uma segunda tentativa é a cauda de baixo. A prévia responde
"quanto a tentativa vale", não "como ficou a turma de repetentes". Ela
sai **pintada pela nota mínima**, que por isso mora na seção de notas e não nas
configurações gerais: faixa inteira acima dela em verde, inteira abaixo em
vermelho, e em amarelo a faixa que `n_min` corta ao meio (com `n_min` = 5 não há
nenhuma; com 5,5 é a `[5, 6)`). As faixas são fechadas à esquerda e abertas à
direita — **menos a última**, fechada dos dois lados porque é nela que o máximo
do domínio cai —, e o tooltip de qualquer um dos dois histogramas nomeia a faixa
nessa notação: `[7, 8)`, `[9, 10]`, `[0,1; 0,2)`. Onde a vírgula já é a decimal,
o par vai separado por ponto e vírgula. A legenda em palavras não é enfeite — cor de
estado nunca diz sozinha o que quer dizer, e a amarela fica abaixo de 3:1 contra
o fundo claro.

A prévia **do interesse** desenha a **log-normal fonte**, antes da
normalização — `exp(μ + σ·Z)` —, em forma fechada, com o eixo de 0 ao
percentil 95. É a fonte, e não o interesse normalizado, porque a normalização
apaga μ: a prévia anterior, em **interesse relativo** (a fração vezes o número
de disciplinas, sorteada linha a linha), era invariante a μ por construção, e
mostrar μ foi o motivo de abri-lo ao cenário. σ aparece nas duas do mesmo
jeito: grande concentra, pequeno achata.

O **peso do turno** não entra nessa prévia: ele multiplica a linha por turma,
e o que faz é redistribuir interesse entre diurnas e noturnas — não muda a
forma da fonte.

Os gráficos são a representação principal e saem em **dois lados do mercado**.

Os **gráficos por aluno** perguntam quem foi bem servido. Uma linha por
recorte, com eixo por período ou por rodada, em três blocos: **métricas
principais** (satisfação, ocupação, progresso, equidade e correlação),
**progressão** (vagas por aluno, CR, ativos, formados e carga aprovada) e
**economia de créditos** (créditos por aluno e fração gasta). O recorte de aluno
é a **coorte**, que parte a mesma população do agregado — somá-la reproduz a
universidade. É série ordenada (quem entrou antes está mais adiante na grade) e
por isso leva a rampa de cor, não a paleta categórica.

Os **gráficos por disciplina** perguntam o que foi disputado. Ali o recorte é da
oferta: as disciplinas se agrupam por **período da grade**, por **número de
vagas** ou por **carga horária**, e disciplinas com o mesmo valor caem no mesmo
grupo. São quatro — concorrência por vaga, preço (π), taxa de ocupação e taxa de
aprovação —, sempre por período, porque a disciplina só fecha esses números ao
fim dele. Concorrência e preço são do bem, então o grupo é a **média** delas;
ocupação e aprovação são razões de contagens, então o grupo é a **razão das
somas** — senão uma disciplina de 40 vagas pesaria o mesmo que uma de 120.

Depois dos gráficos vêm as tabelas por período, por recorte, por disciplina e
por aluno; "Reabrir esta configuração" devolve o cenário ao formulário para
variar um parâmetro e rodar de novo. O filtro de séries dos alunos é
independente do das disciplinas: esconder uma coorte não desfaz o que estava
escondido lá.

#### Tela de comparação

Todo gráfico tem o **período** no eixo X: um por métrica de alocação, um por
rodada na seção de saturação e um por estado de solicitação. A linha é a
mediana entre as simulações e a faixa é o intervalo interquartil — a redução
entre as seeds é feita pela API (`ArmResult.series`), porque a série de cada
simulação por grupo e por período não caberia no histórico do navegador.

O **recorte** vale para a tela inteira: Geral (a universidade toda), Coorte
(período de ingresso) ou um dos quatro eixos de perfil — desempenho,
disponibilidade, seletividade e rotina. A **cor** é o grupo do recorte,
com a cor que o cenário deu a cada perfil (as coortes usam a paleta
categórica); o **traçado** é o modelo — contínuo para o leilão, tracejado para
o CR. A legenda alterna cores e traçados separadamente.

O tempo de formatura não tem gráfico: é da simulação inteira, e a versão por
período teria viés de sobrevivência. A fração de concluintes, por período, é
**acumulada** — quem concluiu até ali sobre quem já tinha entrado.

O que se lê é a **sobreposição** das faixas: faixas que não se tocam separam os
modelos; faixas sobrepostas dizem que a diferença entre as medianas cabe dentro
da variação entre populações. Abaixo vêm três tabelas.

**O que o acúmulo de créditos muda** isola a pergunta que motivou o terceiro
braço: os dois leilões lado a lado, a diferença entre as medianas e a contagem
pareada de em quantas seeds a métrica **subiu** com o acúmulo — uma contagem
descritiva, que não diz se subir é bom. A mediana da linha de base fica ao
lado, para localizar os dois no caminho entre ignorar o histórico e deixá-lo
decidir tudo. A tabela só aparece quando os dois leilões rodaram.

**Resumo das distribuições** traz os cinco números de cada uma, com a diferença
e a contagem de **seeds a favor** medidas contra a linha de base (em quantas
aquele modelo saiu *melhor* que o CR — maior em ψ̄ e φ, menor no tempo). Em λ as
duas colunas vêm vazias: ela descreve se a alocação segue o CR, e qual lado é
melhor ali depende de alocar por mérito passado ou por necessidade.

**Simulação a simulação** põe o pareamento à vista: cada linha é uma seed, e os
três valores de cada coluna são a mesma população sob regras diferentes. A
coluna **formados** está ali porque o tempo de formatura não se lê sem ela; as
rodadas ficam de fora desta tabela, que já tem três valores por célula, e estão
nas duas de cima.

As duas leituras não são equivalentes. Uma diferença pequena de medianas com
quase todas as seeds a favor é um efeito consistente e pequeno — coisa bem
diferente de um empate.

O histórico fica no **IndexedDB** do navegador — sobrevive a um
recarregamento, guarda as 20 execuções mais recentes e é apagado por "Limpar
histórico". O que ele guarda é o **resumo** da comparação (uns 450 kB com as
séries de todos os recortes), e foi esse tamanho que o tirou do
`localStorage`: com uns 5 MB por origem, ali só cabia uma dezena. O histórico
antigo do `localStorage` é copiado para o IndexedDB na primeira abertura. O
detalhe aluno a aluno não é guardado, e é o assunto da seção a seguir.

#### Histórico de um aluno ou de uma disciplina

No fim da tela de comparação está a saída para o outro extremo do agregado: um
aluno, uma disciplina, uma rodada. Dois seletores endereçam **uma** simulação —
o **modelo** e a **seed**, que juntos são uma linha da tabela "Simulação a
simulação" —, e a interface pede ao `/trace` a simulação daquele par. Ela não vem
junto do resultado nem é guardada: são uns 10 MB de JSON num cenário do
tamanho do preset (cerca de 1 comprimido) contra uns 450 kB do resumo, e a
simulação é
determinística, então refazê-la custa segundos e não fidelidade. A configuração
passa pelo mesmo `arm_config` que a comparação usou, e é isso que garante que o
traço seja a simulação de que o ponto saiu, e não uma parecida.

Trocar o modelo **mantém o aluno escolhido**: a população, o interesse e as
notas saem da seed, então o aluno 42 de uma seed é a mesma pessoa nos quatro
modelos — é a comparação pareada da Seção 7.3 lida numa pessoa só.

A vista por **aluno** traz os **quatro perfis** dele junto do nome — os três de
traço (desempenho, disponibilidade e rotina) e o de estratégia (seletividade)
—, porque é ali que se pergunta "por que *este* aluno foi assim",
e o perfil é metade da resposta, com a seed sendo a outra. Traz também o cabeçalho (coorte, CR, carga aprovada,
conclusão) e, período a período, **uma tabela por rodada** com as disciplinas
que lhe eram elegíveis: a utilidade, o lance daquela rodada, o resultado, a
nota, o que pagou e o que o retorno devolveu. A vista por **disciplina** troca
o eixo: cada rodada lista quem a pediu, com CR, utilidade e lance, na ordem em
que o mecanismo os olhou — pelo lance, e pelo CR onde não há lance que os
separe —, sob o cabeçalho da oferta do período (vagas, preenchidas, garantidas,
solicitantes, preço médio e aprovações).

O **resultado** de uma linha é sempre o daquela rodada, em cinco saídas:
**aprovada** (verde: obteve a vaga e passou), **reprovada** (vermelha: obteve e
não passou), **excluída** (azul: obteve e largou — a disponibilidade do período
não comportou, então não houve nota nem tentativa), **recusada** (amarela:
pediu e não obteve) e **não solicitada** (cinza: elegível e sem lance — ou o
aluno não quis, ou a disciplina saiu de `B_a^(t,r)` antes, por falta de vaga,
de carga ou de orçamento). A vaga do ingressante sai marcada como
**garantida**, que é como ela veio, não uma saída a mais. A palavra está sempre
na célula: cor de estado não diz sozinha o que quer dizer, e o amarelo não
alcança 3:1 sobre o fundo claro.

A disciplina **já obtida numa rodada anterior sai da tabela**. Ela deixou
`B_a^(t,r)` e não está mais em disputa, de modo que repeti-la em toda rodada
seguinte afogaria o que ainda se decide ali — e o que ela produziu já aparece
na rodada em que foi ganha e no fechamento do período. Era a única linha que
nem era estado de solicitação nem estava em jogo.

As cinzas só existem na vista por aluno — na por disciplina elas seriam a
população inteira em toda linha — e são **ocultáveis**: num período de ingresso
são quase todas, porque as optativas são elegíveis desde o começo e a matrícula
garantida já tomou 15 das 24 h do calouro. Cada linha é uma **turma**, e as
irmãs de uma já conquistada saem junto com ela: o clique as tirou de disputa.

É a tela de depuração do projeto: quando um agregado sai fora do esperado, é
aqui que se vê por quê.

## Convenções de código

**Uma fórmula, um arquivo, uma função pura.** Toda conta do modelo vive em
`src/leilao/equations/`, num módulo com o nome da grandeza que ela calcula. A
docstring abre com a fórmula e, quando a correspondência ainda vale, com o
número da equação do anteprojeto
(`../TCC1_Anteprojeto_Thales_Brito_Rodrigues.pdf`, Seções 3 e 7) — mas o
recorte é o **código**: há conta aqui que o anteprojeto não prevê, e previsão
dele que o código substituiu, e as duas coisas estão declaradas no índice do
pacote.

A função não toca em estado e não importa nada do resto do motor: ela recebe
números e dicionários e devolve um valor. Quem monta o laço, guarda o
resultado e decide quando chamar é o módulo de cima — `auction`, `simulation`,
`metrics`. Isso é o que torna a revisão possível equação a equação, e o que
deixa cada uma testável sozinha.

No formulário, todo `input[type=number]` precisa de `(valor − min) % step === 0`.
O `min` é a **base** da escada do stepper, e não só um piso de validação: fora
da grade, o primeiro clique na seta anda só até a próxima casa — era por isso
que o σ, com `min=0,01` e `step=0,25`, saía de 1 para 1,01, e o W<sub>a</sub>,
com `min=1` e `step=30`, saía de 450 para 451.
