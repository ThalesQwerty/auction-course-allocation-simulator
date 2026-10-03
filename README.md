# Simulador — Leilão por Créditos

Motor de simulação e interface de configuração para o TCC *"Modelagem e
simulação computacional de mecanismos de leilão por créditos aplicadas à
matrícula universitária"* (UFBA, 2026).

## O que o simulador faz

Simula a matrícula de uma universidade inteira ao longo de vários períodos
letivos: o usuário configura a grade de disciplinas e os perfis de aluno, e a
simulação gera os alunos (nome, utilidades, notas) a partir de uma seed, roda
as rodadas de leilão de cada período e devolve as métricas de eficiência,
equidade e correlação da Seção 7.3.

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
│   ├── config.py         # Cenário: geral, grade, pré-requisitos e perfis de aluno
│   ├── names.py          # 256 nomes x 256 sobrenomes para batizar os alunos
│   ├── population.py     # Alunos e seu histórico acadêmico
│   ├── behavior.py       # Utilidades e lances — eqs. (41)-(48)
│   ├── grading.py        # Notas e retorno de créditos — eqs. (33)-(37)
│   ├── metrics.py        # Eficiência, Jain, correlação, semestralização
│   ├── simulation.py     # Loop multi-período — Seção 7.2
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
    ├── profiles.ts       # Repartição da geração entre os perfis (maior resto)
    ├── Project.tsx       # Visão teórica do projeto
    ├── Results.tsx       # Gráficos e tabelas de uma execução
    ├── StudentList.tsx   # Barra lateral direita: busca, filtro e ordenação
    ├── StudentDetail.tsx # Tela individual do aluno (depuração)
    ├── charts.tsx        # Paleta, eixos e tooltip dos gráficos
    └── history.ts        # Histórico de execuções (localStorage)
```

**Front-end (TypeScript) → API (FastAPI/Python) → Motor (Python)**: a
interface monta a configuração inteira no navegador e manda para `/simulate`,
que devolve as séries por período, por rodada e por recorte (geração, perfil de
aptidão ou perfil de afinidade). Não há banco de dados — cada execução é
independente e reprodutível pela seed.

## Como a simulação funciona

Para cada período letivo `t`:

1. Quem ingressa em `t` recebe **vaga garantida** em todas as disciplinas de
   1º período, e essas vagas saem do estoque antes de o leilão abrir.
2. Cada aluno ativo lê sua linha da matriz de utilidades `u^(t)` — já sorteada
   na inicialização — sobre o seu **conjunto elegível**: as disciplinas que
   ainda não aprovou e cujos pré-requisitos já cumpriu (eqs. 41-43). Fora dele a
   utilidade é zero. A matriz é então elevada ao expoente do perfil de afinidade
   do aluno e renormalizada.
3. Para cada rodada `r`, os lances saem deterministicamente das utilidades
   (eqs. 44-46), o leilão resolve o WDP por PLI (eqs. 22-25) e vagas, carga
   horária e orçamento são descontados (eqs. 13, 14, 27).
4. Ao fim do período saem as notas — da normal do perfil de aptidão do aluno —,
   o retorno de créditos (eqs. 33-36) e as conclusões de curso (eq. 40).

Tudo que é aleatório vem da `seed` e é sorteado **na inicialização**, antes do
primeiro período — nada é sorteado dentro do loop, como exige a Seção 7.3:

| Matriz | O que é | Onde |
| --- | --- | --- |
| `n^0` | nota de primeira tentativa de cada par (aluno, disciplina) | `grading.initial_grades` |
| `u^(t)` | utilidade de cada par (aluno, disciplina) em cada período | `behavior.draw_utilities` |
| `alpha`, `epsilon` | ordem de desempate e perturbação | `tie_breaking` |

Duas coisas **não** vêm da seed, de propósito: o período de ingresso `t_a` e o
par de perfis de cada aluno. Os dois são repartições exatas do cenário
(`population.generate_students`, `config.generation_profiles`), idênticas sob
qualquer seed — assim duas execuções que só diferem na seed têm a mesma
composição, e a diferença entre elas não é a sorte de quem entrou.

Cada recursada soma à tentativa anterior o *Incremento de aprendizado* do cenário
(`learning_gain`, 2,5 pontos por padrão).

A matriz de utilidades é sorteada como um **peso por disciplina** (Gamma(1)) em
vez de uma Dirichlet já normalizada. Em tempo de execução, `utility_matrix` só
normaliza os pesos do conjunto elegível — e, pela propriedade de agregação da
Dirichlet, normalizar um subconjunto de pesos Gamma(1) dá exatamente uma
Dirichlet(1) sobre esse subconjunto. O resultado é o mesmo modelo, mas com a
preferência do aluno fixa desde o início.

**Zerar a utilidade fora do elegível torna a escala de `U_a` redundante.** A
soma das utilidades é exatamente `U_a` (eq. 43), então a satisfação da eq. (51)
divide por ela e o fator se cancela; os lances das eqs. (44)-(46) usam só razões
entre utilidades, que também o cancelam. `U_a` segue multiplicando em
`utility_matrix` porque é o que faz valer a eq. (43), mas depois dela só pesa de
fato como fração do orçamento em `compute_bids`. Em troca, `psi_a` passa a ser a
fração do que o aluno **podia** cursar: antes a utilidade se espalhava por
disciplinas fora do alcance dele, e `psi = 1` era inatingível por construção.

Isso importa para comparar cenários. Com o sorteio dentro do loop, mexer numa
vaga deslocava o fluxo do gerador e mudava as utilidades de todo mundo, de modo
que a diferença entre dois cenários não era atribuível ao mecanismo. Agora dois
cenários com a mesma seed compartilham a matriz inteira — há um teste
(`test_utilities_come_from_the_seed_not_from_the_simulation_path`) que triplica
as vagas e confirma que nenhuma utilidade se mexe.

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
- **Matrícula garantida do ingressante**: quem entra num período recebe vaga em
  **todas** as disciplinas de 1º período e não participa dos lances. O sistema
  ainda assim lança o gasto na conta dele, repartindo o orçamento igualmente
  entre essas disciplinas e deixando o resto da divisão no saldo — e é esse
  valor que alimenta o retorno de créditos da eq. (34). A garantia vale só no
  ingresso: recursar uma delas é disputá-la no leilão como qualquer outra. Daí
  as duas validações do ritmo de entrada: a geração não pode passar da menor
  oferta entre as disciplinas de 1º período, nem a carga somada delas pode
  passar do `W_a` **mais apertado entre os perfis** — a matrícula garantida não
  escolhe quem a recebe.
- **Perfis de aluno**, em dois eixos independentes:

  | Eixo | O que define | Parâmetros |
  | --- | --- | --- |
  | aptidão | a normal de onde saem as notas, e o que cada recursada acrescenta | média, desvio padrão, incremento de aprendizado |
  | afinidade | o expoente aplicado a `u^(t)`, e quanto o aluno carrega por período | tipo (concentrado/diluído), intensidade, `W_a` |

  Expoente maior que 1 (**concentrado**) afasta as utilidades entre si — o aluno
  quer muito uma ou duas disciplinas e quase nada o resto; menor que 1
  (**diluído**, o inverso de um inteiro) as aproxima; intensidade 1 é o perfil
  neutro, que não distorce nada. Depois da distorção a matriz é dividida pelo
  somatório, de modo que `U_a` continue valendo a eq. (43).

  A aptidão existe porque sem heterogeneidade de desempenho o CR vira ruído e a
  eq. (57) não mede nada. A afinidade existe porque concentrar preferência é
  **exatamente** a informação que o leilão diz captar e a ordenação por CR não
  vê. Nenhum dos dois está no anteprojeto.

  Os dois parâmetros que antes eram globais moraram para dentro dos perfis,
  cada um para o eixo de que é a mesma grandeza. O **incremento de
  aprendizado** (eq. 33) é do perfil de aptidão: é o quanto o aluno aprende, e
  um perfil que erra muito na primeira tentativa pode ser justamente o que mais
  ganha ao repetir — com um valor global não havia como dizer isso. A **carga
  horária máxima** `W_a` (eq. 4) é do perfil de afinidade: anda junto da
  concentração, porque querer poucas disciplinas com intensidade e querer
  muitas por igual não descrevem só preferência, mas também quanto se consegue
  carregar num período. Como `W_a` passa a variar entre alunos, a
  semestralização mede cada um contra o próprio teto, e o piso de períodos
  (`minimum_periods_to_graduate`) usa o `W_a` mais folgado — é o do aluno mais
  rápido possível.

  Cada perfil tem um nome e uma **% dos alunos**, e as fatias de cada eixo somam
  100% (o cenário é recusado fora disso — normalizar em silêncio esconderia um
  erro de digitação). Os eixos são independentes, então a fatia de uma
  combinação é o produto das duas: dois perfis de 50% em cada eixo dão 25% para
  cada uma das quatro combinações. A repartição inteira é feita pelo método do
  **maior resto** sobre a combinação (não eixo a eixo, que não garantiria o
  produto) e é a mesma em **toda geração** — sem isso o perfil ficaria
  correlacionado com o período de ingresso, e o recorte por geração passaria a
  medir perfil junto com senioridade.
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
  conjunto pedido depende do orçamento: o truncamento da eq. (44) derruba os
  lances que arredondam para zero, então aluno com pouco crédito pede menos
  disciplinas. (3) A concorrência é demanda revelada *sob este mecanismo*;
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
- **U_a** (fração do orçamento que o aluno se dispõe a gastar) é sorteada em
  [0,5; 1,0]; as utilidades sobre o conjunto elegível seguem uma Dirichlet
  uniforme, distorcida pelo expoente da afinidade.
- **Ingresso escalonado** (`t_a`, eq. 31): o cenário diz quantos alunos entram
  **por período** (`students_per_period`), e uma geração entra a cada período
  letivo, do primeiro ao `L`-ésimo (`entry_periods`, padrão `|T|`). A população
  é, portanto, `students_per_period * L`, e todas as gerações têm exatamente o
  mesmo tamanho e a mesma composição de perfis. O anteprojeto não fixa a
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

- Mecanismo tradicional por CR como linha de base — eqs. (49)-(50), Seção 7.3.1.
- Choque de horário: existe no motor (`MutualExclusion`), mas a simulação não
  gera horários.
- Persistência de cenários no servidor: o histórico de execuções fica no
  navegador, mas não há como salvar, nomear ou exportar um cenário.
- **Qualquer saída sem diploma.** A conclusão (eq. 40) é a única porta: quem
  não concluiu continua disputando até o fim do horizonte. Nem jubilamento por
  decurso de prazo, nem evasão comportamental. A evasão em particular responde
  ao mecanismo, e por isso é contra a linha de base por CR que ela precisaria
  ser medida — antes dela existir, não haveria com o que comparar.

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
**Simulações** já executadas, cada uma identificada por data e hora.

Em "Configurar", a barra lateral **direita** lista os presets — cenários
prontos. Clicar num deles carrega o cenário no formulário; clicar no que já
está carregado não faz nada. Qualquer alteração no formulário passa a valer
como **Personalizado**, que fica guardado: dá para experimentar um preset e
voltar ao seu cenário sem perdê-lo.

Hoje há um preset, **Computação**: uma grade de 6 períodos com 6 disciplinas
cada (36 no total, 2700 h), encadeada por pré-requisitos, em 12 períodos —
ingresso nos 6 primeiros (60 alunos por período, 360 no total) e drenagem nos 6
últimos.

Cada período da grade soma exatamente 450 h, que é a carga horária máxima dos
dois perfis de afinidade (`W_a`): o aluno em dia cursa as seis disciplinas do
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
em dia. Rodando o cenário, `psi` anda entre 0,82 e 1,00 e ~28% concluem em 12
períodos, com a conclusão mais rápida em 6 — o piso da cadeia. No recorte por
vagas, as de 40 chegam a 1,3 candidato por vaga e preço 2,5, enquanto as de 120
ficam em 0,4 e no piso de 1 crédito. Com 30 ingressantes por período a
universidade inteira fica frouxa (`psi` = 1,00, preço sempre 1); com 70 a fila
nas de 40 vagas passa de 1,7 e a conclusão cai para 22%.

Os perfis do preset — os dois parâmetros extras são iguais em todos, para que a
diferença entre perfis seja só o eixo que cada um nomeia:

| Aptidão | Média | Desvio | Ganho por recursada | % |
| --- | --- | --- | --- | --- |
| Exemplar | 8,0 | 1,0 | 2,5 | 25% |
| Regular | 6,5 | 1,5 | 2,5 | 50% |
| Instável | 5,0 | 2,0 | 2,5 | 25% |

| Afinidade | Tipo | Intensidade | `W_a` | % |
| --- | --- | --- | --- | --- |
| Focados | concentrado | 2 | 450 h | 50% |
| Dispersos | diluído | 2 | 450 h | 50% |

Ou monte o seu: configure os parâmetros gerais, os perfis e a grade. Na tabela
de disciplinas, a coluna **Período** é derivada (não se edita) e a célula de
pré-requisitos abre a lista de chips para marcar de quais disciplinas aquela
depende. O painel de perfis mostra a composição de uma geração — toda
combinação (aptidão × afinidade), com a fatia e quantos alunos inteiros ela dá.
Ao executar, a simulação entra no histórico e a tela abre nela.

Os gráficos são a representação principal e saem em **dois lados do mercado**.

Os **gráficos por aluno** perguntam quem foi bem servido. Uma linha por
recorte, com eixo por período ou por rodada, em três blocos: **métricas
principais** (eficiência, equidade, correlação, ocupação e semestralização),
**progressão** (vagas por aluno, CR, ativos, formados e carga aprovada) e
**economia de créditos** (créditos por aluno e fração gasta). O seletor
**Linhas do gráfico** troca o recorte entre **geração**, **perfil de aptidão** e
**perfil de afinidade**. Os três partem a mesma população, então somar qualquer
um reproduz a universidade; o que muda é a pergunta. A geração é série ordenada
e leva a rampa de cor; os perfis são categorias e levam a paleta categórica.

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
variar um parâmetro e rodar de novo. O filtro de séries é por eixo: esconder uma
geração não desfaz o que estava escondido no eixo dos perfis nem no das
disciplinas.

#### Tela individual do aluno

Na vista de uma execução, a barra lateral **direita** lista os alunos, com
busca por nome, filtro por geração e pelos dois perfis, e ordenação por geração
e/ou nome. Clicar num aluno troca o conteúdo pela tela individual dele:
gráficos de progressão (carga horária aprovada contra a grade inteira, CR,
satisfação, créditos e disciplinas por período) e, período a período, a tabela
de tudo o que ele pediu.

Cada linha dessa tabela é uma disciplina elegível no período, com uma das
quatro saídas — **vaga garantida** (o ingressante, fora do leilão),
**atendida** (e em que rodada), **recusada** (deu lance e perdeu) ou **sem
lance** (a disciplina saiu de `B_a^(t,r)` antes do leilão: sem vaga, sem carga
horária ou sem orçamento). É a tela de depuração do projeto: quando um agregado
sai fora do esperado, é aqui que se vê por quê.

O histórico fica no `localStorage` do navegador — sobrevive a um
recarregamento, guarda as 20 execuções mais recentes e é apagado por "Limpar
histórico". O detalhe por aluno (`histories` na resposta) é a parte pesada do
resultado — ~1 MB contra 51 kB do resto, num cenário de 8 períodos — e por isso
**não** é persistido: ao abrir um aluno de uma execução de outra sessão, a
interface reexecuta a simulação, que a seed garante idêntica.

## Convenções de código

Os módulos do motor citam explicitamente os números das equações do
anteprojeto (`../TCC1_Anteprojeto_Thales_Brito_Rodrigues.pdf`) em
docstrings, para rastreabilidade entre a formalização matemática (Seções 3 e
7) e a implementação.
