# Simulador — Leilão por Créditos

Motor de simulação e interface de configuração para o TCC *"Modelagem e
simulação computacional de mecanismos de leilão por créditos aplicadas à
matrícula universitária"* (UFBA, 2026).

## O que o simulador faz

Simula a matrícula de uma universidade inteira ao longo de vários períodos
letivos: o usuário configura disciplinas e cursos, e a simulação gera os
alunos (nome, aptidão, utilidades, notas) a partir de uma seed, roda as
rodadas de leilão de cada período e devolve as métricas de eficiência,
equidade e correlação da Seção 7.3.

```
Simulador/
├── src/leilao/
│   ├── entities.py       # Problema central P = (A, B, D, p, q, w, W, X) — Seção 3
│   ├── wdp_solver.py     # Resolvedor exato via PLI (Winner Determination Problem)
│   ├── tie_breaking.py   # Desempate, viés administrativo e perturbação — 7.1.2
│   ├── auction.py        # Leilão por créditos de uma rodada — 7.1
│   ├── config.py         # Configuração do cenário (geral, disciplinas, cursos)
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
    ├── Project.tsx       # Visão teórica do projeto
    ├── Results.tsx       # Gráficos e tabelas de uma execução
    ├── StudentList.tsx   # Barra lateral direita: busca, filtro e ordenação
    ├── StudentDetail.tsx # Tela individual do aluno (depuração)
    ├── charts.tsx        # Paleta, eixos e tooltip dos gráficos
    └── history.ts        # Histórico de execuções (localStorage)
```

**Front-end (TypeScript) → API (FastAPI/Python) → Motor (Python)**: a
interface monta a configuração inteira no navegador e manda para `/simulate`,
que devolve as séries por período, por rodada e por curso. Não há banco de
dados — cada execução é independente e reprodutível pela seed.

## Como a simulação funciona

Para cada período letivo `t`:

1. Cada aluno ativo lê sua linha da matriz de utilidades `u^(t)` — já sorteada
   na inicialização — respeitando a hierarquia obrigatórias > optativas >
   livres (eqs. 41-43, 47-48).
2. Para cada rodada `r`, os lances saem deterministicamente das utilidades
   (eqs. 44-46), o leilão resolve o WDP por PLI (eqs. 22-25) e vagas, carga
   horária e orçamento são descontados (eqs. 13, 14, 27).
3. Ao fim do período saem as notas, o retorno de créditos (eqs. 33-36) e as
   conclusões de curso (eq. 40).

Tudo que é aleatório vem da `seed` e é sorteado **na inicialização**, antes do
primeiro período — nada é sorteado dentro do loop, como exige a Seção 7.3:

| Matriz | O que é | Onde |
| --- | --- | --- |
| `n^0` | nota de primeira tentativa de cada par (aluno, disciplina) | `grading.initial_grades` |
| `u^(t)` | utilidade de cada par (aluno, disciplina) em cada período | `behavior.draw_utilities` |
| `t_a` | período de ingresso de cada aluno | `population.generate_students` |
| `alpha`, `epsilon` | ordem de desempate e perturbação | `tie_breaking` |

Cada recursada soma à tentativa anterior o *Incremento de aprendizado* do cenário
(`learning_gain`, 2,5 pontos por padrão).

A matriz de utilidades é sorteada como um **peso por disciplina** (Gamma(1)) em
vez de uma Dirichlet já normalizada. Em tempo de execução, `utility_matrix` só
normaliza os pesos das disciplinas que o aluno ainda não aprovou — e, pela
propriedade de agregação da Dirichlet, normalizar um subconjunto de pesos
Gamma(1) dá exatamente uma Dirichlet(1) sobre esse subconjunto. O resultado é o
mesmo modelo, mas com a preferência do aluno fixa desde o início.

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
2. **Curso sem aluno no período não reporta métrica**: `metrics`,
   `mean_credits` e `mean_approved_hours` vêm `null`, não 0,0 — não havia
   ninguém, o que é diferente de ninguém ter ficado satisfeito. O acumulado de
   concluintes (`graduated`) continua valendo, que é o que ainda faz sentido
   contar. Nos gráficos o ponto some; nas tabelas aparece um traço.

O mesmo vale no tempo para o **retorno de créditos** (`mean_credit_return`): as
notas saem depois da última rodada, então o recorte de uma rodada traz `null` e
só o agregado do período traz número. No eixo "por rodada" esse gráfico segue
em período, com o aviso no subtítulo.

### Escolhas de modelagem não fixadas pelo anteprojeto

- **Aptidão latente do aluno** (`Student.ability`): define a distribuição das
  notas de primeira tentativa. Sem heterogeneidade de desempenho o CR vira
  ruído e a correlação da eq. (57) não mede nada.
- **Carga horária máxima por período** (`W_a`): parâmetro global de
  configuração, igual para todos os alunos.
- **Incremento de aprendizado** (`learning_gain`): quanto a nota sobe a cada
  recursada. É global e constante; o anteprojeto só exige que a eq. (33) seja
  monotônica, então qualquer valor positivo serve.
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
  vaga com o aluno não é só quem está no curso dele — e é justamente isso que
  distingue dois cursos que pedem o mesmo bem de dois que pedem bens
  diferentes. Contar quem quer, em vez de somar as vagas ao alcance, é o que faz
  as duas enxergarem **sobreposição**: dois alunos diante dos mesmos 60 lugares
  disputam o dobro de dois alunos diante de 60 lugares cada um, e uma medida do
  tamanho da oferta daria o mesmo nos dois casos.

  Como têm a mesma unidade, leem-se juntas: **a razão concorrência ÷ escassez é
  a fração da demanda potencial que virou pedido** (no preset Campus ela sobe de
  22% no primeiro período a 38% no décimo, conforme os alunos acumulam crédito e
  represam disciplina). Só se pede o que é elegível, então a concorrência fica
  abaixo da escassez.

  A agregação é média, nunca soma: a contagem de quem quer já traz a população
  dentro do valor de cada aluno, e somar sobre os alunos a contaria duas vezes —
  o número deixaria de se ler como alunos por vaga. Não há aditividade (um curso
  não é parcela do global) e, em troca, cursos de tamanhos diferentes se comparam
  direto: um curso maior não aparece mais apertado só por ser maior. As duas são
  do período inteiro e usam a oferta do início dele (`q_x^(t,1)`), então não
  andam entre as rodadas. Disciplinas sem vaga ficam de fora — não são oferta, e
  a razão seria divisão por zero; conjunto vazio dá 0.

  Três ressalvas para o texto. (1) O conjunto elegível inclui as livres `L_k`,
  que são todo o resto do catálogo, e isso faz a escassez quase não distinguir
  cursos — no Campus os três ficam em 75,0 / 74,5 / 75,1 no último período,
  contra 68,2 / 74,6 / 67,9 se a conta se restringir à grade `M_k ∪ O_k`. (2) O
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
  mãos fosse gasto, e a soma dos cursos dá o preço esperado global (mesma
  convenção da ocupação da eq. 54).
- **CR do período**: o `N_a^(t)` usado nas métricas é o vigente no início do
  período — as notas do período só entram no CR do período seguinte, como numa
  matrícula real.
- **Conclusão de curso**: exige aprovação em todas as obrigatórias *e* a carga
  horária curricular da eq. (39). Disciplinas livres não contam.
- **U_a** (fração do orçamento que o aluno se dispõe a gastar) é sorteada em
  [0,5; 1,0]; as utilidades dentro de cada grupo seguem uma Dirichlet uniforme.
- **Ingresso escalonado** (`t_a`, eq. 31): o cenário diz quantos alunos cada
  curso recebe **por geração**, e uma geração entra a cada período letivo, do
  primeiro ao `L`-ésimo (`entry_periods`, padrão `|T|`). A população de um curso
  é, portanto, `students_per_generation * L`, e todas as gerações têm exatamente
  o mesmo tamanho. A geração de cada aluno é determinística; da seed vêm só o
  nome e a aptidão. O anteprojeto não fixa a distribuição dos ingressos; esta é
  a que imita um vestibular por semestre.
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
- **Jubilamento** (`max_residence`, não está no anteprojeto): quem completa
  `T_max` períodos desde o ingresso sem concluir é desligado e sai do conjunto
  ativo. A regra é **opcional e vem desligada**: `max_residence = 0` (o padrão)
  significa sem prazo — permanecer zero períodos não significaria nada, então o
  valor fica livre para servir de sentinela. É prazo da instituição, então é
  global e não por aluno. A conclusão
  (eq. 40) é decidida antes: quem fecha o curso no último período a que tem
  direito se forma, não é jubilado. O desligamento vale a partir do fim do
  período, de modo que a satisfação do aluno naquele período ainda entra nas
  métricas — contar só quem fica faria um mecanismo parecer melhor por ter
  expulsado justamente quem ele serviu pior.

  O que torna isso modelagem e não filtro de relatório é a saída: um a menos
  disputando é menos concorrência para quem fica, e esse retorno não sai de uma
  leitura pós-hoc de `graduated_at - entry_period`. Com `|T| = L - 1 + T_max`
  toda geração é observada até sair, e nenhuma fica em aberto no fim do
  horizonte. Um prazo abaixo de `ceil(S_k / W_a)`
  (`SimulationConfig.minimum_periods_to_graduate`) jubila a população inteira
  por construção.

### Ainda não incluído

- Mecanismo tradicional por CR como linha de base — eqs. (49)-(50), Seção 7.3.1.
- Senioridade das disciplinas (`s_x`) — eq. (38).
- Choque de horário: existe no motor (`MutualExclusion`), mas a simulação não
  gera horários.
- Persistência de cenários no servidor: o histórico de execuções fica no
  navegador, mas não há como salvar, nomear ou exportar um cenário.
- **Evasão comportamental** — deixada de fora de propósito. O aluno sai por
  prazo (jubilamento), nunca por frustração acumulada. São fenômenos
  diferentes: o prazo é regra da instituição e não responde ao mecanismo; a
  evasão responde, e por isso é contra a linha de base por CR que ela
  precisaria ser medida — antes dela existir, não haveria com o que comparar.

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

Hoje há um preset, **Campus**: três cursos cujas grades se cruzam, 38
disciplinas e 762 vagas, em 10 períodos — ingresso nos 5 primeiros (150 alunos
por período, 750 no total) e drenagem nos 5 últimos.

O Campus vai com o jubilamento desligado (`max_residence: 0`): ele é
deliberadamente escasso e em 10 períodos só ~6% concluem o curso, de modo que
qualquer prazo desligaria quase toda a população — mediria a calibragem do
cenário, não o mecanismo.

| Curso | Por geração | Total (5 gerações) | Obrigatórias |
| --- | --- | --- | --- |
| Computação | 60 | 300 | matemática básica + todo o grupo de código |
| Matemática | 40 | 200 | toda a matemática (básica, intermediária e avançada) |
| Engenharia | 50 | 250 | física/eletrônica inteira + matemática até a intermediária |

As optativas de cada curso são os grupos que ele não exige, e `S_k` pede as
obrigatórias inteiras mais 20% da carga das optativas — é o que força a
escolha entre elas. As cargas horárias vão de 30 h a 90 h, com 60 h
predominando (23 das 38) e 45 h e 75 h como minoria (3 cada).

Ou monte o seu: configure os parâmetros gerais, cadastre as disciplinas e, em
cada curso, clique nas disciplinas para alternar entre livre, obrigatória e
optativa. Ao executar, a simulação entra no histórico e a tela abre nela.

Cada execução guardada sai em gráficos (a representação principal, uma linha
por curso, com eixo por período ou por rodada), divididos em três blocos —
**métricas principais** (eficiência, equidade, correlação, ocupação e
semestralização), **progressão** (vagas por aluno, CR, ativos, concluintes e
carga aprovada) e **economia de créditos** (saldo, créditos por aluno e preço
esperado da vaga) — e em tabelas por período, por curso, por disciplina e por
aluno; "Reabrir esta configuração" devolve o
cenário ao formulário para variar um parâmetro e rodar de novo.

#### Tela individual do aluno

Na vista de uma execução, a barra lateral **direita** lista os alunos, com
busca por nome, filtro por curso e ordenação por curso e/ou nome. Clicar num
aluno troca o conteúdo pela tela individual dele: gráficos de progressão
(carga horária aprovada contra a meta, CR, satisfação, créditos e disciplinas
por período) e, período a período, a tabela de tudo o que ele pediu.

Cada linha dessa tabela é uma disciplina com utilidade positiva no período, com
uma das três saídas — **atendida** (e em que rodada), **recusada** (deu lance e
perdeu) ou **sem lance** (a disciplina saiu de `B_a^(t,r)` antes do leilão: sem
vaga, sem carga horária ou sem orçamento). É a tela de depuração do projeto:
quando um agregado sai fora do esperado, é aqui que se vê por quê.

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
