/** Visão teórica do projeto: o que o modelo é e como a simulação o executa.
 * O conteúdo acompanha o anteprojeto — a numeração das equações é a dele. */
export function Project() {
  return (
    <article className="prose">
      <h1>O projeto</h1>
      <p className="lead">
        Modelagem e simulação computacional de mecanismos de leilão por créditos aplicados à
        matrícula universitária — TCC, Ciência da Computação, UFBA, 2026.
      </p>

      <h2>O problema</h2>
      <p>
        Em toda matrícula universitária há disciplinas em que a demanda supera as vagas. O critério
        usual de desempate é o coeficiente de rendimento: ordena-se a fila por CR e atende-se de
        cima para baixo. O critério é simples e transparente, mas ignora <em>o quanto</em> cada
        aluno precisa de cada vaga. Um aluno a uma disciplina da formatura e um aluno que
        tanto faz qual vai cursar entram na mesma fila, e vence quem tem o histórico melhor — não
        quem perderia mais com a recusa.
      </p>
      <p>
        A hipótese do trabalho é que um mecanismo de <strong>leilão por créditos</strong> aloca
        melhor essa escassez. Cada aluno recebe um orçamento de créditos por período e o distribui
        entre as disciplinas que deseja; os lances revelam preferência relativa, algo que a
        ordenação por CR não captura. A pergunta da pesquisa é se isso melhora a satisfação agregada
        sem destruir a equidade entre os alunos.
      </p>
      <p>
        O simulador implementa os <strong>dois</strong> mecanismos sobre o mesmo modelo de
        universidade, e é essa a razão de existir do modo de <strong>comparação</strong>: a
        hipótese não se verifica olhando um mecanismo isolado, só na diferença entre ele e a linha
        de base rodando o mesmo cenário. A comparação põe <strong>três modelos</strong> lado a
        lado, porque o leilão entra duas vezes — com e sem retorno de créditos. O retorno é o que
        pode devolver ao mecanismo algum senso meritocrático, e os dois braços rodando a mesma
        população isolam exatamente o quanto.
      </p>

      <h2>A formalização</h2>
      <p>
        O problema central é a tupla <code>P = (A, B, D, p, q, w, W, X)</code> — alunos, disciplinas,
        demandas, lances, vagas, carga horária das disciplinas, carga horária máxima do aluno e as
        restrições de exclusão mútua (eqs. 1–10). A alocação de uma rodada é o{" "}
        <strong>Winner Determination Problem</strong>: maximizar a soma dos lances atendidos sujeito
        a vagas, carga horária e orçamento (eqs. 22–25). O simulador resolve esse WDP de forma
        exata, por programação linear inteira — não por heurística —, de modo que a alocação de cada
        rodada é ótima em relação aos lances submetidos.
      </p>
      <p>
        Sobre esse núcleo estático somam-se as camadas que o anteprojeto formaliza: múltiplas
        rodadas por período (eqs. 11–17), a dimensão temporal dos períodos letivos (eqs. 31–32),
        notas e retorno de créditos (eqs. 33–37), grade curricular e conclusão de curso (eqs.
        38–40) e o comportamento dos alunos ao transformar utilidade em lance (eqs. 41–48).
      </p>

      <h2>Os dois mecanismos</h2>
      <p>
        A <strong>linha de base</strong> (Seção 7.3.1, eqs. 49–50) é o mecanismo tradicional: não
        há lance, não há orçamento de créditos, não há preço e o resolvedor não usa PLI. Todas as
        solicitações do período são ordenadas pelo CR de quem as fez — N<sub>a</sub>
        <sup>(t)</sup>, a média das notas ponderada pela carga horária, mais a mesma perturbação
        estocástica que desempata no leilão — e cada uma recebe a vaga se ainda houver.
      </p>
      <p>
        A diferença de fundo está em <em>onde</em> as restrições são resolvidas. No leilão, carga
        horária e exclusão mútua são restrições do PLI, e é o resolvedor global que as satisfaz. Na
        linha de base elas são resolvidas <strong>localmente e ex-ante</strong> por cada aluno,
        dentro das próprias solicitações: ele só pede um conjunto que já lhe cabe, e por isso
        atender todos os pedidos dele é sempre viável.
      </p>
      <p>
        O que substitui o orçamento é a carga horária. Os dois lados gastam tudo o que têm, cada
        um na sua moeda: no leilão o aluno reparte C<sub>a</sub>
        <sup>(t,r)</sup> créditos; aqui ele gasta W<sub>a</sub>
        <sup>(t,r)</sup> em horas, até o teto cheio (eq. 50) — hora não cursada não passa para o
        período seguinte. O que muda é a <em>forma</em> da mochila. Aqui é uma{" "}
        <strong>mochila 0-1</strong>, com a carga horária como peso e a utilidade percebida como
        valor: o aluno decide "quais pedir". No leilão é uma <strong>mochila côncava</strong> de
        pesos unitários, em que ele ainda decide "quanto em cada uma". É aí que ele perde a
        capacidade de dizer <em>o quanto</em> quer cada disciplina — a mochila 0-1 só lê a ordem
        das utilidades —, e é exatamente essa perda que a comparação põe à prova.
      </p>
      <p>
        Tudo o mais é idêntico: população, utilidades, notas, pré-requisitos, matrícula garantida,
        conclusão e métricas. Como ali não existe crédito, as grandezas de crédito saem{" "}
        <strong>nulas</strong> dos relatórios — orçamento, saldo, lances, retorno e preço —, e não
        zeradas: zero se leria como "ninguém gastou", e o certo é "não há o que gastar".
      </p>

      <h2>A universidade simulada</h2>
      <p>
        Não há cursos: todo aluno é da universidade e cursa a mesma grade, e{" "}
        <strong>toda disciplina é obrigatória</strong> — conclui quem aprova em todas. O que ordena
        a grade são os <strong>pré-requisitos</strong>: uma disciplina sem pré-requisito é de 1º
        período, e uma com pré-requisitos é do período seguinte ao mais tardio deles. Essa indução
        toma o lugar da senioridade s<sub>x</sub> da eq. (38) — em vez de um número atribuído a cada
        disciplina, o período sai da própria estrutura da grade, e o aluno só fica elegível a
        disputar uma vaga quando aprovou tudo que ela exige.
      </p>
      <p>
        Quem <strong>ingressa</strong> não disputa nada: recebe vaga garantida nas{" "}
        <strong>disciplinas de entrada</strong> — as obrigatórias sem pré-requisito — e fica de
        fora do leilão naquele período. Optativa não entra na garantia, mesmo não tendo
        pré-requisito. O sistema ainda assim
        lança o gasto na conta dele, repartindo o orçamento igualmente entre essas disciplinas e
        deixando o resto da divisão no saldo — é esse valor que alimenta o retorno de créditos da
        eq. (34). A garantia vale só no ingresso: recursar uma dessas disciplinas é disputá-la no
        leilão como qualquer outra. Daí os dois limites do ritmo de entrada: a geração não pode
        passar da menor oferta entre as disciplinas de entrada, nem a carga somada delas pode
        passar de W<sub>a</sub>.
      </p>
      <p>
        E, justamente por isso, <strong>o calouro não entra nas métricas</strong>. As disciplinas
        de 1º período são exatamente as elegíveis para quem acaba de ingressar, e ele recebe todas:
        pontua ψ = 1 contra CR = 0 por construção, sem ter disputado coisa alguma. No preset
        Computação ele é 11% de todas as linhas aluno-período e, sozinho, invertia o sinal da
        correlação da eq. (57) — −0,09 com ele, +0,04 sem. A regra é que ele{" "}
        <strong>conta como gente, não como dado</strong>: fica nas contagens de pessoas (ativos,
        ingressos, formados) e sai de toda média por aluno. Consequência visível: o 1º período de
        uma simulação não publica métrica nenhuma, porque ali todo mundo é calouro.
      </p>
      <p>
        <strong>Não há perfis de aluno.</strong> Toda a população sai de duas distribuições do
        cenário, e o que distingue um aluno do outro é só o que a <em>seed</em> sorteou para ele. A{" "}
        <em>normal das notas</em> é de onde cada par (aluno, disciplina) sorteia a nota em cada
        período, por média e desvio, e a recursada desloca essa média (eq. 33) — sem dispersão de
        desempenho o CR vira ruído e a eq. (57) não mede nada. A <em>log-normal das utilidades</em> tem
        um parâmetro só, o desvio <em>σ</em>, e é ele que diz o quanto o aluno diferencia uma
        disciplina da outra: <em>σ</em> grande concentra a preferência e <em>σ</em> pequeno a
        achata. Diferenciar preferência é justamente a informação
        que o leilão diz captar e a ordenação por CR não vê.
      </p>
      <p>
        A carga horária máxima (W<sub>a</sub>, eq. 4) também é do cenário e igual para todos, então
        a semestralização compara todo mundo contra o mesmo teto. Até 08/10/2026 os alunos se
        dividiam em perfis de <em>aptidão</em> e <em>afinidade</em>, cada um com os seus parâmetros
        e a sua fatia da população; isso saiu a pedido, e com ele saiu o recorte dos relatórios por
        perfil. A heterogeneidade continua — ela só deixou de ser sistemática.
      </p>
      <p>
        A conclusão do curso é a <strong>única</strong> porta de saída: quem não concluiu continua
        disputando até o fim do horizonte.
      </p>

      <h2>O que a simulação faz em cada período</h2>
      <ol>
        <li>
          Quem ingressa no período recebe a matrícula garantida nas disciplinas de 1º período, e as
          vagas saem do estoque antes de o leilão abrir.
        </li>
        <li>
          Cada aluno ativo lê sua linha da matriz de utilidades — já sorteada na inicialização —
          sobre o seu conjunto elegível: as disciplinas que ainda não aprovou e cujos
          pré-requisitos já cumpriu (eqs. 41–43). Fora dele a utilidade é zero. A linha é
          sorteada de novo a cada período — o que ele quis no semestre passado não determina o que
          quer neste — e não é renormalizada, então a soma do que está ao alcance dele é o
          U<sub>a</sub><sup>(t)</sup> da eq. (43). Não há poupança: saldo de créditos e carga
          horária não passam de um período para o outro.
        </li>
        <li>
          Em cada rodada, os lances saem deterministicamente das utilidades: o aluno resolve uma
          mochila côncava em que cada crédito pesa 1 e o N-ésimo crédito posto numa disciplina
          vale u<sub>a,x</sub>/N. Depois o leilão resolve o WDP e vagas, carga horária e orçamento
          são descontados (eqs. 13, 14, 27).
          Empates são resolvidos pela regra de desempate, viés administrativo e perturbação da
          Seção 7.1.2.
        </li>
        <li>
          Ao fim do período saem as notas — sorteadas da normal do cenário, com a média
          deslocada pelo incremento de aprendizado de quem recursa —, o
          retorno de créditos (eqs. 33–36) e as conclusões de curso (eq. 40).
        </li>
      </ol>
      <p>
        Tudo é reprodutível: nomes, utilidades e notas vêm da <em>seed</em>, e todos são
        sorteados <strong>antes</strong> do primeiro período. O período de ingresso não
        vêm dela — são repartições exatas do cenário, idênticas sob qualquer seed. A mesma
        configuração produz sempre a mesma simulação, como exige a Seção 7.3 — uma vez
        inicializado, o modelo não sorteia mais nada em tempo de execução.
      </p>
      <p>
        Isso é o que torna dois cenários comparáveis. Se a utilidade fosse sorteada dentro do loop,
        mexer numa única vaga deslocaria o fluxo do gerador e mudaria a preferência de todos os
        alunos — e a diferença entre dois cenários deixaria de ser atribuível ao mecanismo. Com a
        matriz fixa desde o início, dois cenários com a mesma seed disputam exatamente as mesmas
        preferências.
      </p>

      <h2>As métricas</h2>
      <p>
        O resultado de cada período é medido pelas métricas da Seção 7.3.3, e elas se dividem
        pelos dois lados do mercado. As <strong>do aluno</strong> — eficiência, equidade,
        correlação, semestralização, progressão, créditos — são agregadas pelo recorte da{" "}
        <strong>geração</strong>, que parte a mesma população do agregado: somá-la reproduz a
        universidade. Com dezenas de alunos, qualquer recorte mais granular vira ruído.
      </p>
      <p>
        As <strong>da disciplina</strong> — concorrência, preço, ocupação e taxa de aprovação —
        pedem o recorte oposto: as disciplinas se agrupam por uma propriedade que compartilham, e
        disciplinas com o mesmo valor caem no mesmo grupo. São três eixos: o período na grade (que
        vem dos pré-requisitos), o número de vagas e a carga horária. É assim que se vê, por
        exemplo, que as disciplinas de turma pequena formam preço e as de turma grande ficam no
        piso — uma média sobre a universidade inteira esconderia a gradação. Concorrência e preço
        são do bem, então o grupo é a média delas; ocupação e aprovação são razões de contagens,
        então o grupo é a razão das somas, senão uma disciplina de 40 vagas pesaria o mesmo que uma
        de 120.
      </p>
      <dl className="metric-list">
        <div>
          <dt>Eficiência de alocação (ψ̄) — eq. (53)</dt>
          <dd>
            Satisfação média dos alunos que disputaram: quanto da utilidade que o aluno queria
            ele de fato conseguiu. Como a utilidade é zero fora do conjunto elegível, é a fração do
            que ele <em>podia</em> cursar — então 1 é atingível. É a medida principal da hipótese.
          </dd>
        </div>
        <div>
          <dt>Equidade (índice de Jain, φ) — eq. (55)</dt>
          <dd>
            1 quando todos estão igualmente satisfeitos; cai conforme a satisfação se concentra em
            poucos. Serve de contrapeso: eficiência alta com equidade baixa não sustenta a hipótese.
          </dd>
        </div>
        <div>
          <dt>Ocupação (θ) — eq. (54)</dt>
          <dd>
            Fração das vagas ofertadas que foi efetivamente preenchida. Aparece dos dois lados:
            por aluno é a <em>fatia</em> das vagas da universidade que cada recorte levou, e os
            parciais somam o total; por disciplina é a <em>taxa</em> com que cada tipo de oferta
            encheu, que não é fatia de nada.
          </dd>
        </div>
        <div>
          <dt>Demanda por vaga — fora do anteprojeto</dt>
          <dd>
            Alunos por vaga — a razão candidato/vaga do vestibular. A <em>escassez</em> conta quem
            poderia cursar cada disciplina (não aprovada e com os pré-requisitos cumpridos): é a
            demanda <em>potencial</em>, e quase não depende do mecanismo. A{" "}
            <em>concorrência</em> faz a mesma conta sobre quem de fato a pediu: é a{" "}
            <em>efetiva</em>, e a razão entre as duas diz quanto da potencial virou pedido. Nos
            gráficos sobrou só a concorrência, e do lado das disciplinas, onde ela é razão de
            contagens sobre um bem concreto; a escassez segue na tabela por período.
          </dd>
        </div>
        <div>
          <dt>Preço de disciplina (π) — eq. (24)</dt>
          <dd>
            O maior lance mal-sucedido de cada disciplina, ou 1 crédito quando ninguém ficou de
            fora. Só entram as disciplinas que ainda tinham vaga no instante: a esgotada não
            recebe mais lance e cairia no piso de 1, o que leria como barata justamente a que todo
            mundo quis. O gráfico mostra a média de cada grupo de disciplinas — é a comparação
            entre grupos que diz onde o crédito se concentrou.
          </dd>
        </div>
        <div>
          <dt>Taxa de aprovação — fora do anteprojeto</dt>
          <dd>
            Aprovados ÷ matriculados de um grupo de disciplinas ao fim do período. Não mede
            alocação: serve para distinguir um tipo de disciplina que represa a fila por
            reprovação de outro que a represa por falta de vaga.
          </dd>
        </div>
        <div>
          <dt>Semestralização (σ̄) — fora do anteprojeto</dt>
          <dd>
            Por aluno, a carga horária aprovada dividida por W<sub>a</sub> × idade em períodos: 1 é
            quem nunca deixou de encher a carga horária desde que ingressou. Quem acabou de
            ingressar (idade 0) entra como 0. A métrica do recorte é a média dos alunos — é o atraso
            na progressão que a matrícula por créditos deveria reduzir.
          </dd>
        </div>
        <div>
          <dt>CR médio (N̄) — eq. (56)</dt>
          <dd>
            Coeficiente de rendimento médio no início do período — as notas do período só entram no
            CR do período seguinte, como numa matrícula real.
          </dd>
        </div>
        <div>
          <dt>Correlação CR × satisfação (λ) — eq. (57)</dt>
          <dd>
            Correlação de Pearson entre CR e satisfação. Positiva significa que quem tem histórico
            melhor se sai melhor na matrícula — é o que o mecanismo por CR impõe por construção e o
            leilão não precisa reproduzir.
          </dd>
        </div>
        <div>
          <dt>Economia de créditos — fora do anteprojeto</dt>
          <dd>
            A oferta que o recorte levou ao leilão (C<sub>a</sub><sup>(t,1)</sup>, antes de
            qualquer lance) dividida pelos alunos ativos dá os <em>créditos por aluno</em>;
            dividida pelas vagas ofertadas dá o <em>preço esperado</em> da vaga, o que ela custaria se todo o
            crédito em mãos fosse gasto — um teto de referência, não o preço que o leilão formou
            (esse é o π acima). O <em>saldo médio</em> é outra coisa: é o que sobrou depois das
            rodadas.
          </dd>
        </div>
      </dl>

      <h2>Escolhas de modelagem não fixadas pelo anteprojeto</h2>
      <ul>
        <li>
          <strong>A normal das notas:</strong> as notas saem de uma normal do cenário,
          parametrizada por média e desvio padrão. Sem dispersão de desempenho o CR vira ruído e a
          eq. (57) não mede nada.
        </li>
        <li>
          <strong>Notas como parâmetro de entrada:</strong> a matriz com o sorteio de cada par
          (aluno, disciplina) em cada <em>período</em> é gerada junto com a população. A recursada
          desloca a <strong>média</strong> do sorteio pelo incremento de aprendizado, então ela
          não garante nota maior — o aluno aprende, mas pode ter um dia pior. O que não regride é
          a maior nota já obtida, que é a que conta para o CR.
        </li>

        <li>
          <strong>Matrícula garantida do ingressante:</strong> entra sem leilão em todas as
          disciplinas de 1º período, com o orçamento repartido igualmente entre elas e o resto da
          divisão no saldo. O anteprojeto não trata do ingresso.
        </li>
        <li>
          <strong>Conclusão de curso:</strong> toda disciplina é obrigatória, então a eq. (40) vira
          aprovar na grade inteira — não há carga horária mínima a somar separadamente.
        </li>
        <li>
          <strong>Utilidades (u):</strong> um valor por par (aluno, disciplina, período), tirado
          de uma log-normal de desvio <em>σ</em> e dividido pelo
          somatório do conjunto elegível — a soma dá 1. O anteprojeto não fixa a distribuição nem
          o valor de U<sub>a</sub>; aqui ele é 1 para todo aluno, porque nada de saldo passa de um
          período para o outro e poupar seria só perder.
        </li>
        <li>
          <strong>Ordem de desempate entre disciplinas:</strong> quando duas valem o mesmo para um
          aluno, ganha a <strong>listada primeiro</strong> — a ordem em que a grade aparece nesta
          interface, que é a ordem em que as disciplinas foram acrescentadas. É global: a mesma
          para todo aluno, período e rodada, e vale tanto no lance quanto no pedido por CR. Com
          utilidade sorteada o empate tem probabilidade zero; a regra existe para que um cenário
          escrito à mão dê sempre o mesmo resultado. Não se confunde com o desempate do leilão
          (eq. 20), que é <em>entre alunos</em>.
        </li>
        <li>
          <strong>Ingresso escalonado (t<sub>a</sub>):</strong> entra uma geração nova a cada
          período, do primeiro ao L-ésimo, com o número de alunos que o cenário definir — como um
          vestibular por semestre. Todas as gerações têm o mesmo tamanho. O anteprojeto não fixa
          a distribuição dos ingressos.
        </li>
      </ul>

      <h2>Ainda não incluído</h2>
      <ul>
        <li>
          Escolha do mecanismo numa execução única: a linha de base só aparece dentro do modo de
          comparação, então não há como abrir os gráficos por período nem a tela por aluno de uma
          execução por CR.
        </li>
        <li>
          Teste estatístico sobre as duas amostras: a comparação mostra a dispersão e a contagem
          pareada, mas não calcula p-valor nem intervalo de confiança.
        </li>
        <li>Choque de horário: existe no motor, mas a simulação ainda não gera horários.</li>
        <li>
          Qualquer saída sem diploma: a conclusão é a única porta, então não há jubilamento por
          decurso de prazo nem evasão comportamental. A evasão responde ao mecanismo, e é contra a
          linha de base por CR que ela precisaria ser medida.
        </li>
      </ul>

      <h2>Como ler os resultados</h2>
      <p>
        Uma <strong>comparação</strong> abre quatro boxplots — satisfação (ψ̄), equidade (φ),
        correlação (λ) e tempo de formatura —, com uma caixa por modelo: a linha grossa é a
        mediana, a caixa é a metade central das N execuções, os bigodes vão até 1,5 IQR. Nas três
        primeiras, cada valor é uma execução reduzida à média dos períodos ponderada pelos alunos
        medidos; o tempo de formatura é da execução inteira. O que se lê é a sobreposição — caixas
        que não se tocam separam os mecanismos; caixas sobrepostas dizem que a diferença entre as
        medianas cabe dentro da variação entre populações. Como as seeds são pareadas, a tabela
        ainda informa em quantas delas o leilão saiu melhor, que é uma leitura independente da
        primeira.
      </p>
      <p>
        Uma seção à parte mede a <strong>saturação da demanda</strong>: as vagas obtidas por aluno
        em cada rodada, um boxplot por rodada. Cada um conta o que foi ganho <em>naquela</em>
        rodada, não o acumulado, então o que se lê é o <strong>decaimento</strong> entre eles. Uma
        das hipóteses do trabalho é que o leilão satura mais rápido — atende mais demanda em menos
        rodadas —, e é aqui que isso aparece: quem atende mais de saída começa alto e cai rápido,
        porque pouco ficou por alocar. Nenhuma rodada isolada tem lado melhor; na primeira, mais
        alto é atender mais, e nas seguintes é ter deixado mais para trás.
      </p>
      <p>
        É na <strong>correlação</strong> que o terceiro braço se lê. A ordenação por CR a impõe
        por construção, o leilão sem retorno a ignora, e o leilão com retorno fica em algum ponto
        entre os dois — a distância até cada ponta diz o quanto o f<sub>γ</sub> consegue recriar o
        incentivo que o CR dá de graça. Uma tabela à parte isola essa diferença, porque os dois
        braços do leilão rodam a mesma população e só diferem na política de retorno.
      </p>
      <p>
        O <strong>tempo de formatura</strong> tem viés de seleção e não se lê sozinho: a média só
        existe sobre quem concluiu, então um mecanismo que forma menos gente pode exibir um tempo
        menor só porque sobraram os rápidos. Por isso a tabela traz, ao lado dele, quantos se
        formaram em cada execução.
      </p>
      <p>
        A comparação tem um <strong>segundo eixo, opcional</strong>: a varredura da forma da
        preferência. A hipótese do trabalho é que o leilão capta intensidade que a ordenação por
        CR não enxerga — e se é isso, o quanto a população diferencia as disciplinas não é um
        parâmetro a calibrar, é a variável independente. A varredura roda a comparação inteira em
        vários <em>σ</em>, numa faixa linear, com poucas execuções por ponto: ali se lê a{" "}
        <strong>forma da curva</strong>, enquanto os boxplots respondem, no <em>σ</em> canônico e
        com muitas execuções, se a diferença supera o ruído amostral. O resultado sai em duas
        seções próprias — as linhas por métrica e, ao lado, o histograma de como a utilidade se
        reparte em cada <em>σ</em>, que é o gráfico da causa.
      </p>
      <p>
        Uma <strong>simulação</strong> abre os gráficos do cenário, em dois blocos. Os{" "}
        <strong>gráficos por aluno</strong> trazem uma linha por geração, com o eixo
        horizontal por período ou por rodada, divididos em métricas principais, progressão e
        economia de créditos. Os <strong>gráficos por disciplina</strong> trazem uma linha por
        período da grade, por número de vagas ou por carga horária, sempre em período. Depois vêm
        as tabelas por período, por recorte, por disciplina e por aluno. Os gráficos são a
        representação principal; as tabelas servem para conferir números específicos. O histórico
        fica no navegador, então execuções antigas sobrevivem a um recarregamento da página.
      </p>
      <p>
        A barra lateral à direita lista os alunos daquela execução, e filtra por geração. Clicar
        num deles abre a tela individual: a progressão dele período a período
        e, em cada período, tudo o que pediu. Cada pedido tem uma de quatro saídas —{" "}
        <strong>vaga garantida</strong> (o ingressante, fora do leilão),{" "}
        <strong>atendida</strong> (e em que rodada), <strong>recusada</strong> (deu lance e perdeu
        o desempate) ou <strong>sem lance</strong>, que significa que a disciplina saiu de B
        <sub>a</sub><sup>(t,r)</sup> antes do leilão por falta de vaga, de carga horária ou de
        orçamento. É a tela para investigar um agregado que saiu diferente do esperado: ela desce
        ao nível do aluno e da disciplina, que os dois blocos de gráficos agregam de propósito.
      </p>
    </article>
  );
}
