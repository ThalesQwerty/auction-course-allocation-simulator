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
        aluno precisa de cada vaga. Um aluno a uma disciplina da formatura e um aluno em busca de
        uma optativa qualquer entram na mesma fila, e vence quem tem o histórico melhor — não quem
        perderia mais com a recusa.
      </p>
      <p>
        A hipótese do trabalho é que um mecanismo de <strong>leilão por créditos</strong> aloca
        melhor essa escassez. Cada aluno recebe um orçamento de créditos por período e o distribui
        entre as disciplinas que deseja; os lances revelam preferência relativa, algo que a
        ordenação por CR não captura. A pergunta da pesquisa é se isso melhora a satisfação agregada
        sem destruir a equidade entre os alunos.
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
        notas e retorno de créditos (eqs. 33–37), senioridade, grade curricular e conclusão de curso
        (eqs. 38–40) e o comportamento dos alunos ao transformar utilidade em lance (eqs. 41–48).
      </p>

      <h2>O que a simulação faz em cada período</h2>
      <ol>
        <li>
          Cada aluno ativo lê sua linha da matriz de utilidades — já sorteada na inicialização —
          respeitando a hierarquia obrigatórias &gt; optativas &gt; livres (eqs. 41–43, 47–48).
        </li>
        <li>
          Em cada rodada, os lances saem deterministicamente das utilidades (eqs. 44–46), o leilão
          resolve o WDP e vagas, carga horária e orçamento são descontados (eqs. 13, 14, 27).
          Empates são resolvidos pela regra de desempate, viés administrativo e perturbação da
          Seção 7.1.2.
        </li>
        <li>
          Ao fim do período saem as notas, o retorno de créditos (eqs. 33–36) e as conclusões de
          curso (eq. 40).
        </li>
      </ol>
      <p>
        Tudo é reprodutível: alunos, nomes, aptidões, utilidades, notas e períodos de ingresso vêm
        da <em>seed</em>, e todos são sorteados <strong>antes</strong> do primeiro período. A mesma
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
        O resultado de cada período é medido pelas métricas da Seção 7.3.3, e elas se dividem em
        duas famílias. As <strong>do aluno</strong> — eficiência, equidade, correlação,
        semestralização, progressão, créditos — são agregadas por curso ou por geração: é aí que a
        diferença entre populações aparece, e com dezenas de alunos qualquer recorte mais granular
        vira ruído. As <strong>do mercado</strong> — ocupação, demanda por vaga e preço — não se
        recortam: medem a oferta contra as vagas de toda a universidade, o mesmo denominador para
        qualquer curso, de modo que o recorte devolveria a fatia daquele curso no lugar de uma taxa
        comparável entre cursos. Essas saem numa linha só.
      </p>
      <dl className="metric-list">
        <div>
          <dt>Eficiência de alocação (ψ̄) — eq. (53)</dt>
          <dd>
            Satisfação média dos alunos ativos: quanto da utilidade que o aluno queria ele de fato
            conseguiu. É a medida principal da hipótese.
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
          <dd>Fração das vagas ofertadas que foi efetivamente preenchida.</dd>
        </div>
        <div>
          <dt>Demanda por vaga — fora do anteprojeto</dt>
          <dd>
            Alunos por vaga, disciplina a disciplina, na média das disciplinas de cada aluno — a
            razão candidato/vaga do vestibular. A <em>escassez</em> conta quem poderia cursar cada
            disciplina da sua grade: é a demanda <em>potencial</em>, e quase não depende do
            mecanismo. A <em>concorrência</em> faz a mesma conta sobre as disciplinas em que o aluno
            de fato deu lance: é a <em>efetiva</em>. O vão entre as duas é a demanda que não virou
            pedido — por isso as duas dividem o mesmo gráfico.
          </dd>
        </div>
        <div>
          <dt>Preço de disciplina (π) — eq. (24)</dt>
          <dd>
            O maior lance mal-sucedido de cada disciplina, ou 1 crédito quando ninguém ficou de
            fora. O gráfico mostra a faixa — a disciplina mais cara, a média e a mais barata —,
            porque a média sozinha não distingue um crédito concentrado em poucas disputas de um
            espalhado por todas as vagas. Só entram as disciplinas que ainda tinham vaga no
            instante: a esgotada não recebe mais lance e cairia no piso de 1, o que leria como
            barata justamente a que todo mundo quis.
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
            A oferta que o curso levou ao leilão (C<sub>a</sub><sup>(t,1)</sup>, antes de qualquer
            lance) dividida pelos alunos ativos dá os <em>créditos por aluno</em>; dividida pelas
            vagas ofertadas dá o <em>preço esperado</em> da vaga, o que ela custaria se todo o
            crédito em mãos fosse gasto — um teto de referência, não o preço que o leilão formou
            (esse é o π acima). O <em>saldo médio</em> é outra coisa: é o que sobrou depois das
            rodadas.
          </dd>
        </div>
      </dl>

      <h2>Escolhas de modelagem não fixadas pelo anteprojeto</h2>
      <ul>
        <li>
          <strong>Aptidão latente do aluno:</strong> define a distribuição das notas de primeira
          tentativa. Sem heterogeneidade de desempenho o CR vira ruído e a eq. (57) não mede nada.
        </li>
        <li>
          <strong>Notas como parâmetro de entrada:</strong> a matriz com a nota de primeira
          tentativa de cada par (aluno, disciplina) é gerada junto com a população, e cada recursada
          soma exatamente 1 ponto à tentativa anterior.
        </li>
        <li>
          <strong>Carga horária máxima por período (W<sub>a</sub>):</strong> parâmetro global,
          idêntico para todos os alunos.
        </li>
        <li>
          <strong>Conclusão de curso:</strong> exige aprovação em todas as obrigatórias <em>e</em> a
          carga horária curricular da eq. (39). Disciplinas livres não contam.
        </li>
        <li>
          <strong>Orçamento gasto (U<sub>a</sub>):</strong> fração sorteada em [0,5; 1,0]; as
          utilidades dentro de cada grupo seguem uma Dirichlet uniforme.
        </li>
        <li>
          <strong>Ingresso escalonado (t<sub>a</sub>):</strong> cada curso recebe uma geração
          nova a cada período, do primeiro ao último, com o número de alunos que o cenário
          definir — como um vestibular por semestre. A população do curso é esse número vezes
          |T|, e todas as gerações têm o mesmo tamanho. O anteprojeto não fixa a distribuição
          dos ingressos.
        </li>
      </ul>

      <h2>Ainda não incluído</h2>
      <ul>
        <li>Mecanismo tradicional por CR como linha de base — eqs. (49)–(50), Seção 7.3.1.</li>
        <li>Políticas de retorno de créditos além da nula — f<sub>γ</sub>, eq. (34).</li>
        <li>Senioridade das disciplinas (s<sub>x</sub>) — eq. (38).</li>
        <li>Choque de horário: existe no motor, mas a simulação ainda não gera horários.</li>
      </ul>

      <h2>Como ler os resultados</h2>
      <p>
        Cada execução guardada na barra lateral abre os gráficos do cenário — uma linha por curso,
        com o eixo horizontal por período ou por rodada, divididos em métricas principais,
        progressão e economia de créditos — seguidos das tabelas por período, por
        curso, por disciplina e por aluno. Os gráficos são a representação principal; as tabelas
        servem para conferir números específicos. O histórico fica no navegador, então execuções
        antigas sobrevivem a um recarregamento da página.
      </p>
      <p>
        A barra lateral à direita lista os alunos daquela execução. Clicar num deles abre a tela
        individual: a progressão dele período a período e, em cada período, tudo o que pediu. Cada
        pedido tem uma de três saídas — <strong>atendida</strong> (e em que rodada),{" "}
        <strong>recusada</strong> (deu lance e perdeu o desempate) ou <strong>sem lance</strong>, que
        significa que a disciplina saiu de B<sub>a</sub><sup>(t,r)</sup> antes do leilão por falta de
        vaga, de carga horária ou de orçamento. É a tela para investigar um agregado que saiu
        diferente do esperado: ela desce ao nível em que a causa é visível, que os gráficos por curso
        deliberadamente escondem.
      </p>
    </article>
  );
}
