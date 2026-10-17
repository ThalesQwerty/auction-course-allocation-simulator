# Simulador — Leilão por Créditos

Motor de simulação e interface de configuração para o TCC *"Modelagem e
simulação computacional de mecanismos de leilão por créditos aplicadas à
matrícula universitária"* (UFBA, 2026).

## O que o simulador faz

Simula a matrícula de uma universidade inteira ao longo de vários períodos
letivos: o usuário configura a grade de disciplinas e a população, e a
simulação gera os alunos (nome, utilidades, notas) a partir de uma seed, roda
as rodadas de alocação de cada período e devolve as métricas de eficiência,
equidade e correlação da Seção 7.3.

São **dois mecanismos de alocação** sobre o mesmo modelo de universidade: o
**leilão por créditos** proposto (Seção 7.1) e a **ordenação por CR** que serve
de linha de base (Seção 7.3.1, eqs. 49-50). E, por isso, dois modos de
execução — uma simulação, que detalha um mecanismo por dentro, e uma
**comparação**, que roda o mesmo cenário em **três modelos**, N vezes em cada
um, e mostra só as métricas de alocação em boxplot. Os três são a ordenação por
CR e o leilão **com** e **sem** retorno de créditos: o retorno entra como eixo
do experimento porque é ele que pode devolver ao leilão algum senso
meritocrático.

Não há cursos: todo aluno é da universidade e cursa a mesma grade, e **toda
disciplina é obrigatória** — conclui quem aprova em todas. O que ordena a grade
são os **pré-requisitos**, e o período de cada disciplina sai deles por indução:
sem pré-requisito é 1º período, com pré-requisitos é o período seguinte ao mais
tardio deles.

```
Simulador/
├── src/leilao/
│   ├── entities.py       # Problema central P = (A, B, D, p, q, w, W, X) — Seção 3
│   ├── wdp_solver.py     # Resolvedor exato via PLI (Winner Determination Problem)
│   ├── tie_breaking.py   # Desempate, viés administrativo e perturbação — 7.1.2
│   ├── auction.py        # Leilão por créditos de uma rodada — 7.1
│   ├── config.py         # Cenário: geral, grade, pré-requisitos e as duas normais
│   ├── names.py          # 256 nomes x 256 sobrenomes para batizar os alunos
│   ├── population.py     # Alunos e seu histórico acadêmico
│   ├── behavior.py       # Utilidades e lances — eqs. (41)-(48)
│   ├── ranking.py        # Linha de base por CR — eqs. (49)-(50), Seção 7.3.1
│   ├── grading.py        # Notas e retorno de créditos — eqs. (33)-(37)
│   ├── metrics.py        # Eficiência, Jain, correlação, semestralização
│   ├── simulation.py     # Loop multi-período — Seção 7.2
│   ├── comparison.py     # N execuções pareadas dos dois mecanismos — Seção 7.3
│   └── api/              # Ponte FastAPI (sem persistência — stateless)
├── tests/                # pytest (motor + simulação + API)
├── examples/             # Script de exemplo executável
└── web/src/              # Interface React + TypeScript
    ├── App.tsx           # Shell: barra lateral, navegação e histórico
    ├── Sidebar.tsx       # Menu, lista de simulações e limpeza do histórico
    ├── Config.tsx        # Formulário do cenário
    ├── PresetList.tsx    # Barra lateral direita: cenários prontos
    ├── presets.ts        # Catálogo de presets e regra de seleção
    ├── curriculum.ts     # Período de cada disciplina, induzido dos pré-requisitos
    ├── Project.tsx       # Visão teórica do projeto
    ├── Results.tsx       # Gráficos e tabelas de uma execução
    ├── Comparison.tsx    # Boxplots e tabelas de uma comparação
    ├── StudentList.tsx   # Barra lateral direita: busca, filtro e ordenação
    ├── StudentDetail.tsx # Tela individual do aluno (depuração)
    ├── charts.tsx        # Paleta, eixos, tooltip e o boxplot da comparação
    └── history.ts        # Histórico de execuções (localStorage)
```

**Front-end (TypeScript) → API (FastAPI/Python) → Motor (Python)**: a
interface monta a configuração inteira no navegador e manda para `/simulate`,
que devolve as séries por período, por rodada e por recorte (geração), ou para
`/compare`, que devolve N resumos de
cada mecanismo. Não há banco de dados — cada execução é independente e
reprodutível pela seed.

## Como a simulação funciona

Para cada período letivo `t`:

1. Quem ingressa em `t` recebe **vaga garantida** em todas as disciplinas de
   1º período, e essas vagas saem do estoque antes de o leilão abrir.
2. Cada aluno ativo lê sua linha da matriz de utilidades `u^(t)` — já sorteada
   na inicialização — sobre o seu **conjunto elegível**: as disciplinas que
   ainda não aprovou e cujos pré-requisitos já cumpriu (eqs. 41-43). Fora dele a
   utilidade é zero. Fora isso a linha dele não muda: ela é sorteada uma vez só,
   para a simulação inteira.
3. Para cada rodada `r`, os lances saem deterministicamente das utilidades
   (mochila côncava), o leilão resolve o WDP por PLI (eqs. 22-25) e vagas, carga
   horária e orçamento são descontados (eqs. 13, 14, 27).
4. Ao fim do período saem as notas — da normal do cenário —,
   o retorno de créditos (eqs. 33-36) e as conclusões de curso (eq. 40).

Tudo que é aleatório vem da `seed` e é sorteado **na inicialização**, antes do
primeiro período — nada é sorteado dentro do loop, como exige a Seção 7.3:

| Matriz | O que é | Onde |
| --- | --- | --- |
| `n` | sorteio de nota de cada par (aluno, disciplina) em cada período | `grading.draw_grades` |
| `u^(t)` | utilidade de cada par (aluno, disciplina) em cada período | `behavior.draw_utilities` |
| `alpha`, `epsilon` | ordem de desempate e perturbação | `tie_breaking` |

Uma coisa **não** vem da seed, de propósito: o período de ingresso `t_a`. As
gerações têm todas o mesmo tamanho, em períodos consecutivos
(`population.generate_students`) — assim duas execuções que só diferem na seed
têm a mesma estrutura de entrada, e a diferença entre elas não é quem entrou
quando.

**A matriz de notas é sorteada por período, e a recursada desloca a média.** O
aluno que repete uma disciplina não recebe a nota anterior mais um incremento:
ele tira uma nota nova, de uma normal cuja média subiu o *Incremento de
aprendizado* (`learning_gain`, 2,5 por padrão) por tentativa já feita. Em
distribuição é o mesmo que somar o incremento ao sorteio daquele período, e é
assim que a conta é feita — `draw_grades` devolve o sorteio cru e
`grade_for_attempt` desloca, arredonda a 0,1 e trunca em [0, 10].

Duas consequências. A recursada **deixa de garantir nota maior**: o aluno
aprende, mas pode ter um dia pior. E `Student.grades` continua guardando a
**maior** nota já obtida — é ela que conta para o CR e para a aprovação —,
enquanto o histórico por período guarda a nota **daquela** tentativa, que é o que
a tela individual precisa mostrar. A monotonicidade da eq. (33) passa a valer no
esperado e no registro, não em cada sorteio; como a média sobe a cada tentativa,
a probabilidade de aprovar tende a 1 e ninguém fica preso numa disciplina.

A matriz de utilidades é sorteada como **uma linha por (aluno, período)**, em
dois passos:

1. Um **valor preliminar** por par (aluno, disciplina), tirado de uma
   **log-normal** de média logarítmica 0 e desvio `utility_sigma`.
2. **Divisão pelo somatório**, que faz a linha valer 1 sobre a grade inteira.

A log-normal é o que se obtém quando a grandeza é **produto** de muitos fatores
independentes — e é assim que se forma o quanto alguém quer uma disciplina:
interesse no tema vezes afinidade com a área vezes horário vezes dificuldade
percebida. É uma afirmação sobre alunos, e não sobre a ignorância de quem modela.

`sigma` é o único parâmetro, e **grande concentra, pequeno achata**:

- o coeficiente de variação é `sqrt(exp(σ²) − 1)`, que cresce depressa, de modo
  que a faixa útil inteira cabe entre ~0,25 (aluno quase indiferente) e ~3 (quer
  uma disciplina e despreza o resto) — em passos **lineares**;
- a média do logaritmo não é configurável porque some: deslocá-la multiplica a
  linha por uma constante, e a constante morre na normalização;
- a moda do sorteio cru é `exp(−σ²)`, **sempre positiva** — não há limiar de
  sigma a respeitar para que a utilidade mais provável de uma disciplina não
  seja zero.

**A normalização não é necessária para o mecanismo.** As duas mochilas do aluno
comparam só razões entre utilidades e `psi` divide pela soma do elegível, de
modo que a simulação sai idêntica com ou sem ela (há medição: mesma alocação
aluno a aluno, mesmas séries). Ela fica porque é o que mantém o número legível no
relatório — 0,11 é "11% do que o aluno quer", 1,94 não é nada — e o `U_a^(t)` da
eq. (43) com significado.

Há uma **guarda contra underflow** (`behavior.UNDERFLOW_GUARD`) que não é
parâmetro de modelagem: utilidade zero é o que marca o *inelegível*, filtrado por
`utilidade > 0` nas duas mochilas, e um zero tiraria a disciplina do conjunto de
escolha. Com a log-normal ela nunca dispara — só chegaria a zero com expoente
abaixo de −745 —, e fica como invariante.

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

Sobre a linha do período agem os zeros da eq. (42). `utility_matrix` recorta ao
conjunto elegível e **não renormaliza**: os valores que sobram são os mesmos da
linha sorteada, e a soma deles é o `U_a^(t)` da eq. (43) — menor que 1 sempre
que algo estiver fora do alcance do aluno.

Isso não muda alocação nenhuma, e vale saber por quê: as duas mochilas do aluno
comparam só **razões** entre utilidades, e a satisfação da eq. (51) divide pela
soma do elegível. Multiplicar a linha por uma constante não muda lance, pedido
nem `psi`. O `U_a` existe como leitura — quanto do que o aluno quer está ao
alcance dele agora —, não como alavanca. E `psi = 1` continua atingível, que é o
que o ingressante com matrícula garantida obtém.

Sobre poupar: não há. A eq. (42) prevê um `U_a` que é a fração do que o aluno
tem em mãos que ele se dispõe a comprometer, mas nem crédito nem carga horária
passam de um período para o outro, então guardar não é estratégia, é perda — o
aluno gasta todo o orçamento no leilão e pede até o `W_a` cheio na linha de base.

Isso importa para comparar cenários. Com o sorteio dentro do loop, mexer numa
vaga deslocava o fluxo do gerador e mudava as utilidades de todo mundo, de modo
que a diferença entre dois cenários não era atribuível ao mecanismo. Agora dois
cenários com a mesma seed compartilham a matriz inteira — há um teste
(`test_utilities_come_from_the_seed_not_from_the_simulation_path`) que triplica
as vagas e confirma que nenhuma utilidade se mexe.

### Os dois mecanismos

O cenário, a população, as utilidades, as notas, os pré-requisitos, a matrícula
garantida do ingressante, a conclusão do curso e as métricas são **os mesmos**
nos dois. O que `mechanism` troca é só o miolo da rodada — e é por isso que a
diferença entre eles se lê como efeito do mecanismo.

| | `credits` (leilão, Seção 7.1) | `ranking` (linha de base, Seção 7.3.1) |
|---|---|---|
| **Moeda** | créditos, `C_a^(t,r)` | carga horária, `W_a^(t,r)` |
| **O que o aluno decide** | quanto apostar em cada disciplina | quais pedir, dado o teto `W_a` — eq. (50) |
| **Estratégia** | mochila **côncava** de pesos unitários: o N-ésimo crédito posto em `x` vale `u_{a,x}/N` | mochila **0-1**: `w_x` é peso, `u_{a,x}` é valor |
| **Quem decide a alocação** | PLI exata sobre todos os lances (eq. 22) | varredura por `N_a^(t) + ε` — eq. (49) |
| **Onde as restrições são resolvidas** | globalmente, no resolvedor | localmente e *ex-ante*, por cada aluno |
| **Preço** | 2º preço, eq. (24) | não existe |
| **Retorno de créditos** | `f_γ`, eq. (34) | não existe — não houve preço a devolver |

Em **empate de utilidade**, as duas mochilas preferem a disciplina **listada
primeiro** no cenário — ver abaixo. Os dois lados gastam **tudo**, cada um na sua
moeda, e é o que mantém a
comparação honesta: o que os separa tem de ser o mecanismo, não quanto cada um
resolveu guardar. A perda de expressividade é o ponto da comparação — a mochila
0-1 só lê a *ordem* das utilidades, enquanto a côncava carrega o *quanto*: ela
decide não só quais disciplinas, mas quantos créditos cada uma merece.

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
"ninguém gastou", e o certo é "não há o que gastar". `base_credits` e
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
| sem optativa | só as de entrada — exatamente o pacote | **1,000**, sem exceção |
| com optativa | entrada + todo o catálogo de optativas | **~0,2**, nunca 1,000 |

Com optativa a garantia deixa de cobrir o elegível: no preset são 6 vagas
garantidas contra 30 elegíveis, e as 450 h do pacote já esgotam `W_a`, então o
calouro não disputa o resto. O `ψ` dele passa a medir o quanto a preferência
sorteada coincidiu com o pacote — **ruído**, onde antes era constante. A regra
de excluí-lo não muda; o motivo, sim.

No preset Computação ele é **11% de todas as linhas aluno-período**, e sozinho
invertia o sinal da correlação da eq. (57):

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
  `None`): ali todo mundo é calouro. A série de uma geração começa no período
  *seguinte* ao seu ingresso.

### A comparação

`run_comparison` roda o mesmo cenário em **três braços** (`ARMS`), `N` vezes em
cada um, com as **seeds de 1 a N**:

| Braço | Mecanismo | `f_γ` | O que ele é |
|---|---|---|---|
| `ranking` | ordenação por CR | — | a linha de base: o histórico *é* o critério |
| `credits_return` | leilão | `ratio` | quem aprova recupera a fatia do preço correspondente à nota |
| `credits` | leilão | `none` | o leilão puro: o crédito gasto sai do sistema |

O leilão entra duas vezes porque o **retorno de créditos é o eixo do
experimento**, não um parâmetro do cenário: a política proporcional é a única
que premia desempenho acima da nota de corte, e portanto a única com chance de
recriar o incentivo que o CR dá de graça. Os dois braços do leilão rodam a mesma
população com a mesma seed e diferem em uma única coisa, de modo que a diferença
entre eles **é** o efeito do retorno, isolado. Por isso o `credit_return` que
vier na configuração é ignorado, como a seed.

As duas condições da Seção 7.3 saem daí:

1. **Mesma inicialização em todos os braços.** A seed gera a população, as
   utilidades e as notas, então rodar a mesma seed nos três é literalmente a
   mesma gente encontrando regras diferentes. As listas da resposta são
   **pareadas**: o i-ésimo elemento de cada uma é a mesma população.
2. **Múltiplas configurações de entrada.** As N seeds são essas configurações.
   Uma execução só não diria nada — a diferença poderia ser daquela população.

São **quatro métricas**: eficiência (ψ̄), equidade (φ), correlação (λ) e
**tempo de formatura**. Nada de crédito, porque não há contraparte do outro
lado, e nenhum recorte por geração, porque o que está em comparação é
o mecanismo, não o que acontece dentro de cada um.

As três primeiras são de período, e uma execução vira um número pela média
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

#### O segundo eixo: a varredura da forma da preferência

A hipótese do trabalho é que o leilão capta **intensidade** de preferência que a
ordenação por CR não enxerga. Se é isso, o quanto a população diferencia as
disciplinas não é um parâmetro a calibrar — é a **variável independente**. Por
isso `run_sweep` roda a comparação inteira em vários `utility_sigma`, numa faixa
**linear**, e devolve um ponto por `σ`.

Linear basta porque o coeficiente de variação da log-normal cresce depressa em
`σ`: a faixa útil inteira cabe entre ~0,25 e ~3 em passos iguais. (Era a Gamma
que precisava de progressão geométrica e eixo logarítmico, porque exigia quatro
ordens de grandeza do parâmetro.) O `utility_sigma` do cenário é o **canônico** —
o que os boxplots medem — e é marcado no eixo com uma linha de referência, sem
precisar cair exatamente num ponto varrido.

| | σ canônico (boxplot) | varredura (linhas) |
| --- | --- | --- |
| pergunta | a diferença supera o ruído amostral? | como o vão depende de σ? |
| execuções | muitas (`runs`, 20 por padrão) | poucas (3 por padrão), por ponto |
| forma | caixa por modelo | linha por modelo, eixo x linear |

Cada ponto traz também o **histograma da própria matriz de utilidades** — o
gráfico da causa ao lado do da consequência. Ele mostra como a preferência de um
aluno se reparte entre as disciplinas: cada linha (aluno, período) é reescalada
ao **próprio** mínimo e máximo e dividida em 9 faixas de mesma largura, e a
altura é a fração de utilidades em cada faixa. A escala é por linha, e não do
menor ao maior valor da matriz inteira, porque global degenera — um único extremo
define o intervalo e, de `σ = 1` em diante, 94% dos valores caem na primeira
faixa, de modo que todos os gráficos sairiam iguais.

A varredura acrescenta uma métrica que **não** está no boxplot: a contagem de
**formandos**. Ela é obrigatória aqui porque `ψ̄` é cega para a patologia que a
varredura revela — `ψ̄` cresce monotonicamente conforme a preferência concentra e
chega perto de 1 na ponta, justamente onde ninguém se forma: o aluno quer uma
disciplina só, consegue, e a satisfação dele é plena. `ψ̄` é satisfação *relativa
ao que o aluno queria*. Lado a lado no mesmo eixo, as duas contam a troca que o
mecanismo faz.

Ficaram de fora, por motivos diferentes. A **ocupação** (θ) porque, com o
calouro fora do recorte, ela deixou de se ler como "o quanto a universidade
encheu" — as vagas garantidas continuam ocupadas e não entram mais no
numerador; essa leitura está nos gráficos por disciplina de uma execução. E a
**semestralização** (σ̄) porque o tempo de formatura mede a mesma coisa —
progressão na grade — num número que se lê direto, em períodos. As duas
continuam nos relatórios de uma execução única.

### Garantias dos relatórios

Duas invariantes que os testes travam, porque métrica sobre conjunto vazio é
pior que métrica ausente — ela vira zero, e zero num gráfico se lê como queda:

1. **Todo período publicado tem pelo menos um aluno ativo**, e a numeração vai
   de 1 a `len(periods)` sem buraco. Vale por construção: os ingressos ocorrem
   em períodos consecutivos a partir do primeiro e, passado o último (`L`), a
   população só diminui — então o primeiro período vazio, se houver, só é
   seguido de períodos vazios, e a simulação para ali. Com ingresso em todo
   período o relatório traz os `|T|` períodos inteiros; com uma fase de
   drenagem (`L < |T|`) a parada é o fim natural dela, quando o último aluno
   sai. Na entrada, cenários sem nenhum aluno ou sem nenhuma disciplina são
   recusados.
2. **Recorte sem aluno no período não reporta métrica**: `metrics`,
   `mean_credits` e `mean_approved_hours` vêm `null`, não 0,0 — não havia
   ninguém, o que é diferente de ninguém ter ficado satisfeito. O acumulado de
   concluintes (`graduated`) continua valendo, que é o que ainda faz sentido
   contar. Nos gráficos o ponto some; nas tabelas aparece um traço.

O mesmo vale no tempo para o **retorno de créditos** (`mean_credit_return`): as
notas saem depois da última rodada, então o recorte de uma rodada traz `null` e
só o agregado do período traz número. No eixo "por rodada" esse gráfico segue
em período, com o aviso no subtítulo.

### Escolhas de modelagem não fixadas pelo anteprojeto

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

  Com utilidade sorteada o empate tem probabilidade zero, então a regra quase
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
  as duas validações do ritmo de entrada: a geração não pode passar da menor
  oferta entre as disciplinas de 1º período, nem a carga somada delas pode
  passar do `W_a` — a matrícula garantida não escolhe quem a recebe.
- **As duas normais da população**, no lugar dos perfis de aluno:

  | Normal | O que define | Parâmetros |
  | --- | --- | --- |
  | notas | de onde sai cada sorteio de nota, e o quanto a recursada desloca a média | `grade_mean`, `grade_stddev`, `learning_gain` |
  | utilidades | o quanto o aluno diferencia as disciplinas | `utility_sigma` (o desvio da log-normal; a média do log some na normalização) |

  Toda a população sai delas, e o que distingue um aluno do outro é só o que a
  seed sorteou para ele. A das notas existe porque sem dispersão de desempenho o
  CR vira ruído e a eq. (57) não mede nada. A das utilidades existe porque
  diferenciar preferência é **exatamente** a informação que o leilão diz captar e
  a ordenação por CR não vê. Nenhuma das duas está no anteprojeto.

  `W_a` (eq. 4) também é do cenário e igual para todos, o que faz a
  semestralização comparar todo mundo contra o mesmo teto e dá à validação da
  matrícula garantida um número só a conferir.

  **Os perfis de aluno existiram entre 03/10 e 08/10/2026** e foram removidos a
  pedido. Eram dois eixos independentes — aptidão (a normal das notas) e
  afinidade (um expoente sobre `u`) —, cada um com nome, parâmetros e % da
  população, repartidos exatamente pelo método do maior resto. Com eles saíram os
  recortes dos relatórios por perfil: a heterogeneidade continua, mas deixou de
  ser *sistemática*, e sem grupo não há o que separar além da senioridade.

- **Retorno de créditos** (`f_gamma`, eq. 34): o anteprojeto deixa a forma
  concreta em aberto — é o eixo de experimentação da Seção 7.3.2. São quatro
  políticas, escolhidas na configuração e aplicadas ao fim de cada período
  sobre o preço pago (`paid`) e a nota obtida:

  | Política | `gamma_{a,x}` | O que ela premia |
  | --- | --- | --- |
  | `none` (nenhum) | 0 | nada — linha de base, o crédito gasto sai do sistema |
  | `unit` (unitário) | 1 se aprovado, 0 se não | aprovar, independente do preço |
  | `full` (integral) | `paid` se aprovado, 0 se não | aprovar; o crédito só se perde na reprovação |
  | `ratio` (proporcional) | `round(nota / 10 x paid)` | desempenho acima da nota de corte, e devolve algo mesmo a quem reprova |

  A única entrada de crédito fora disso é o `Gamma_min` do período (eq. 35), de
  modo que o saldo de um período é
  `C_a^(t,1) - gasto + Gamma_min + soma gamma_{a,x}` — conta que o histórico
  individual mostra aberta e que os testes travam. Em `ratio`, o
  arredondamento do Python desempata para o par (`round(2,5) == 2`); o empate
  exato é frequente porque as notas andam de 0,1 em 0,1 e os preços são
  inteiros pequenos, mas o viés é o mesmo para todo aluno.
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
  vaga com o aluno não é só quem está na geração dele — e a matrícula garantida
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
  se comparam direto: uma geração maior não aparece mais apertada só por ser
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
- **Conclusão de curso**: toda disciplina é obrigatória, então a eq. (40) vira
  aprovar na grade inteira — não há carga horária mínima a somar à parte, e
  `hours_to_graduate` é a soma de `w_x` sobre a grade, igual para todos.
- **Utilidades**: um valor por par (aluno, disciplina, período), tirado de uma
  log-normal de desvio `utility_sigma` e dividido pelo somatório da linha — uma
  linha por (aluno, período). O anteprojeto não fixa a distribuição nem
  o valor de `U_a`; aqui `U_a^(t)` é a soma do que está ao alcance do aluno
  naquele período, e ele gasta tudo o que tem, porque não há transferência de
  saldo entre períodos que justificasse poupar.
- **Ingresso escalonado** (`t_a`, eq. 31): o cenário diz quantos alunos entram
  **por período** (`students_per_period`), e uma geração entra a cada período
  letivo, do primeiro ao `L`-ésimo (`entry_periods`, padrão `|T|`). A população
  é, portanto, `students_per_period * L`, e todas as gerações têm exatamente o
  mesmo tamanho. O anteprojeto não fixa a
  distribuição dos ingressos; esta é a que imita um vestibular por semestre.
- **Fase de drenagem** (`L < |T|`): depois do `L`-ésimo período ninguém mais
  entra e a população só diminui. Existem **`L` gerações**, não `|T|` — os
  períodos de drenagem não têm geração correspondente. Sem ela a última geração
  vivia um período só e nunca chegava a se formar, de modo que a série por
  geração media quanto tempo de simulação sobrou em vez de medir o mecanismo.
  Em troca, as gerações deixam de ser intercambiáveis: a primeira encontra uma
  universidade quase vazia e a `L`-ésima encontra a cheia, e depois a
  esvaziando. Pelo mesmo motivo, as curvas **por período** caem no fim porque
  há menos gente disputando, não porque o mecanismo melhorou — o recorte por
  geração não tem essa distorção.

### Ainda não incluído

- Escolha do mecanismo numa execução **única**: a linha de base só aparece
  dentro do modo de comparação, então não há como abrir os gráficos por período
  nem a tela por aluno de uma execução por CR.
- Teste estatístico sobre as duas amostras: a comparação mostra a dispersão e a
  contagem pareada, mas não calcula p-valor nem intervalo de confiança.
- Choque de horário: existe no motor (`MutualExclusion`), mas a simulação não
  gera horários.
- **Poupança.** O aluno gasta sempre tudo: todo o orçamento de créditos no
  leilão, todo o `W_a` na linha de base. Guardar não teria para onde ir — nem
  crédito nem hora passam de um período para o outro —, mas guardar *entre
  rodadas do mesmo período* seria uma estratégia de verdade, e não existe: hoje
  o aluno reparte na rodada 1 tudo o que tem. Enquanto o lance perdedor não
  consome crédito, apostar cedo não custa nada, então essa estratégia só
  apareceria com uma regra que cobrasse a aposta.
- Persistência de cenários no servidor: o histórico de execuções fica no
  navegador, mas não há como salvar, nomear ou exportar um cenário.
- **Qualquer saída sem diploma.** A conclusão (eq. 40) é a única porta: quem
  não concluiu continua disputando até o fim do horizonte. Nem jubilamento por
  decurso de prazo, nem evasão comportamental. A evasão em particular responde
  ao mecanismo, e é contra a linha de base por CR que ela precisaria ser
  medida — agora que ela existe, é comparação possível.

## Como rodar

```powershell
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
| `make install` | venv e dependências |

Os alvos só delegam para o PowerShell (o trabalho está em `dev.ps1`), então
funcionam igual chamados do PowerShell, do `cmd` ou do Git Bash.

### Usando a interface

Em `http://localhost:5173`, a barra lateral tem **Configurar** (o formulário do
cenário), **Projeto** (visão teórica do modelo e das métricas) e a lista de
**Execuções** já feitas, cada uma identificada por data e hora — as comparações
levam uma etiqueta, porque abrem numa tela diferente.

No topo de "Configurar", **Modo de execução** escolhe o que o botão faz:

- **uma simulação do leilão por créditos** — o cenário roda uma vez, com a seed
  do formulário, e a tela traz todos os gráficos por período, o recorte por
  geração e a tela de depuração por aluno.
- **comparar os três modelos** — o mesmo cenário roda nos três, `N` vezes em
  cada um, com as seeds de 1 a `N`. Somem dois campos: o da **seed** (ali ela
  vira o eixo da amostra) e o do **retorno de créditos** (ali ele vira o eixo do
  experimento, e cada braço impõe o seu). No lugar entra **execuções por modelo
  (N)**. São `3N` simulações completas: com o preset Computação e `N = 20`,
  cerca de meio minuto.

O cenário é o mesmo nos dois modos — trocar de modo não mexe em nada do que
está configurado.

Em "Configurar", a barra lateral **direita** lista os presets — cenários
prontos. Clicar num deles carrega o cenário no formulário; clicar no que já
está carregado não faz nada. Qualquer alteração no formulário passa a valer
como **Personalizado**, que fica guardado: dá para experimentar um preset e
voltar ao seu cenário sem perdê-lo.

Hoje há um preset, **Computação**: uma grade de 6 períodos com 6 disciplinas
cada (36 no total, 2700 h), encadeada por pré-requisitos, em 12 períodos —
ingresso nos 6 primeiros (60 alunos por período, 360 no total) e drenagem nos 6
últimos.

Cada período da grade soma exatamente 450 h, que é a carga horária máxima
(`W_a`): o aluno em dia cursa as seis disciplinas do
seu período e nada mais. Isso faz a disputa ser por *quais* seis, e não por
quantas — quem fica para trás escolhe entre recuperar o atraso e avançar —, e
deixa a matrícula garantida do ingressante caber em `W_a`.

A oferta é desenhada para os gráficos por disciplina terem o que mostrar: do 2º
período em diante, cada período repete as **seis combinações** de 40/80/120
vagas × 60/90 h. Assim, agrupar por carga horária dá dois grupos de 15
disciplinas e agrupar por período dá cinco de 6, e em qualquer recorte os
outros eixos estão igualmente distribuídos dentro de cada grupo — uma diferença
entre séries é da grandeza em tela, não de um desequilíbrio de composição. O
**1º período é a exceção**: ali tudo tem 120 vagas, porque a geração inteira
entra de uma vez por matrícula garantida e ainda precisa sobrar lugar para quem
recursa.

As 40 vagas são o gargalo: em regime, cada período da grade tem ~60 alunos em
dia querendo as mesmas seis disciplinas, e as de 40 não comportam nem a turma
em dia. Rodando o cenário em σ = 1, **29% concluem** em 12 períodos. No recorte por
vagas, as de 40 são o gargalo e as de 120 nunca apertam — é essa gradação que os
gráficos por disciplina existem para mostrar. Com 30 ingressantes por período a
universidade fica frouxa; com 70 a conclusão despenca. Os números exatos variam
com σ, e é a varredura que os põe em contexto.

A população do preset, nas duas normais do cenário:

| Normal | Parâmetros |
| --- | --- |
| notas | média 6,5, desvio 1,5, ganho por recursada 2,5 |
| utilidades | desvio `σ` = 1 (log-normal normalizada) |

A média das notas é a da mistura dos três perfis de aptidão que existiam antes
(0,25·8 + 0,50·6,5 + 0,25·5 = 6,5), e o desvio é menor que o dela — ali parte da
dispersão vinha da distância *entre* os perfis, que é a diferença sistemática
que saiu do modelo.

Ou monte o seu: configure os parâmetros gerais, a população e a grade. Na tabela
de disciplinas, a coluna **Período** é derivada (não se edita) e a célula de
pré-requisitos abre a lista de chips para marcar de quais disciplinas aquela
depende. Ao executar, a simulação entra no histórico e a tela abre nela.

Os gráficos são a representação principal e saem em **dois lados do mercado**.

Os **gráficos por aluno** perguntam quem foi bem servido. Uma linha por
recorte, com eixo por período ou por rodada, em três blocos: **métricas
principais** (eficiência, equidade, correlação, ocupação e semestralização),
**progressão** (vagas por aluno, CR, ativos, formados e carga aprovada) e
**economia de créditos** (créditos por aluno e fração gasta). O recorte de aluno
é a **geração**, que parte a mesma população do agregado — somá-la reproduz a
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
independente do das disciplinas: esconder uma geração não desfaz o que estava
escondido lá.

#### Tela individual do aluno

Na vista de uma execução, a barra lateral **direita** lista os alunos, com
busca por nome, filtro por geração e ordenação por geração e/ou nome. Clicar num aluno troca o conteúdo pela tela individual dele:
gráficos de progressão (carga horária aprovada contra a grade inteira, CR,
satisfação, créditos e disciplinas por período) e, período a período, a tabela
de tudo o que ele pediu.

Cada linha dessa tabela é uma disciplina elegível no período, com uma das
quatro saídas — **vaga garantida** (o ingressante, fora do leilão),
**atendida** (e em que rodada), **recusada** (deu lance e perdeu) ou **sem
lance** (a disciplina saiu de `B_a^(t,r)` antes do leilão: sem vaga, sem carga
horária ou sem orçamento). É a tela de depuração do projeto: quando um agregado
sai fora do esperado, é aqui que se vê por quê.

#### Tela de comparação

Uma comparação não tem gráfico por período, recorte nem tela por aluno: tem
**quatro boxplots** de alocação, um por métrica, mais **um por rodada** na seção
de saturação — todos com **uma caixa por modelo**. A linha
grossa é a mediana, a caixa é a metade central da amostra (1º ao 3º quartil),
os bigodes vão até 1,5 IQR e o que sobra aparece como ponto solto. Cada valor
dentro de uma caixa é uma execução.

O que se lê é a **sobreposição**: caixas que não se tocam separam os modelos;
caixas sobrepostas dizem que a diferença entre as medianas cabe dentro da
variação entre populações. Abaixo vêm três tabelas.

**O que o retorno de créditos muda** isola a pergunta que motivou o terceiro
braço: os dois braços do leilão lado a lado, a diferença entre as medianas e a
contagem pareada de em quantas seeds a métrica **subiu** com o retorno — uma
contagem descritiva, que não diz se subir é bom. A mediana da linha de base fica
ao lado, para localizar os dois no caminho entre ignorar o histórico e deixá-lo
decidir tudo.

**Resumo das distribuições** traz os cinco números de cada uma, com a diferença
e a contagem de **seeds a favor** medidas contra a linha de base (em quantas
aquele modelo saiu *melhor* que o CR — maior em ψ̄ e φ, menor no tempo). Em λ as
duas colunas vêm vazias: ela descreve se a alocação segue o CR, e qual lado é
melhor ali depende de alocar por mérito passado ou por necessidade.

**Execução a execução** põe o pareamento à vista: cada linha é uma seed, e os
três valores de cada coluna são a mesma população sob regras diferentes. A
coluna **formados** está ali porque o tempo de formatura não se lê sem ela; as
rodadas ficam de fora desta tabela, que já tem três valores por célula, e estão
nas duas de cima.

As duas leituras não são equivalentes. Uma diferença pequena de medianas com
quase todas as seeds a favor é um efeito consistente e pequeno — coisa bem
diferente de um empate.

O histórico fica no `localStorage` do navegador — sobrevive a um
recarregamento, guarda as 20 execuções mais recentes (simulações e
comparações na mesma lista) e é apagado por "Limpar histórico". O detalhe por
aluno (`histories` na resposta) é a parte pesada do
resultado — ~1 MB contra 51 kB do resto, num cenário de 8 períodos — e por isso
**não** é persistido: ao abrir um aluno de uma execução de outra sessão, a
interface reexecuta a simulação, que a seed garante idêntica.

## Convenções de código

Os módulos do motor citam explicitamente os números das equações do
anteprojeto (`../TCC1_Anteprojeto_Thales_Brito_Rodrigues.pdf`) em
docstrings, para rastreabilidade entre a formalização matemática (Seções 3 e
7) e a implementação.
