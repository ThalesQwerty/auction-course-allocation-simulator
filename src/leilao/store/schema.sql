-- Um banco por comparação: a comparação é um cenário com N seeds × M braços e
-- contém N×M simulações. Toda tabela de detalhe pendura em `simulacao`, porque
-- a unidade que se apaga e se refaz é a simulação. A `turma` não pendura em
-- nada: a oferta é a mesma nas N×M, e há uma oferta por arquivo.

-- `unica` não é identidade, é guarda: com um banco por comparação a tabela tem
-- uma linha, e a chave primária é o que recusa a segunda.
CREATE TABLE comparacao (
  unica          INTEGER NOT NULL PRIMARY KEY DEFAULT 1 CHECK (unica = 1),
  rotulo         TEXT,
  criada_em      TEXT    NOT NULL,
  iniciada_em    TEXT,
  terminada_em   TEXT,
  duracao_ms     INTEGER,
  estado         TEXT    NOT NULL
    CHECK (estado IN ('pendente','rodando','pausada','concluida','falhou')),
  cenario        TEXT    NOT NULL,
  seeds          INTEGER NOT NULL,
  bracos         TEXT    NOT NULL,
  coorte_medida  INTEGER,
  rodadas_teto   INTEGER NOT NULL,
  -- O teto de passos da comparação: simulações × períodos × rodadas × 2. É teto
  -- porque a rodada que não concede nada fecha o período antes do teto.
  etapas_total   INTEGER,
  erro           TEXT
);

CREATE TABLE turma (
  turma            TEXT    NOT NULL,
  disciplina       TEXT    NOT NULL,
  carga            INTEGER NOT NULL,
  horario          TEXT    NOT NULL,
  periodo_da_grade INTEGER,
  optativa         INTEGER NOT NULL,
  entrada          INTEGER NOT NULL,
  vagas            INTEGER NOT NULL,
  PRIMARY KEY (turma)
);

CREATE TABLE simulacao (
  id             INTEGER PRIMARY KEY,
  braco          TEXT    NOT NULL,
  seed           INTEGER NOT NULL,
  estado         TEXT    NOT NULL
    CHECK (estado IN ('pendente','rodando','concluida','falhou')),
  dono           TEXT,
  tentativas     INTEGER NOT NULL DEFAULT 0,
  iniciada_em    TEXT,
  terminada_em   TEXT,
  duracao_ms     INTEGER,
  periodos       INTEGER,
  etapas         INTEGER NOT NULL DEFAULT 0,
  erro           TEXT,
  UNIQUE (braco, seed)
);

CREATE TABLE aluno (
  simulacao_id           INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
  aluno                  TEXT    NOT NULL,
  ingresso               INTEGER NOT NULL,
  medido                 INTEGER NOT NULL,
  ancora_disponibilidade REAL,
  ancora_seletividade    REAL,
  concluiu_em            INTEGER,
  jubilou_em             INTEGER,
  cr_final               REAL,
  carga_aprovada         INTEGER NOT NULL,
  nome                   TEXT,
  PRIMARY KEY (simulacao_id, aluno)
);

-- Sem coluna de estado: `terminado_em` nulo já diz que está em curso, e
-- alocando × cursando é se alguma `rodada` do período está sem fechar.
CREATE TABLE periodo (
  simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
  periodo       INTEGER NOT NULL,
  medido        INTEGER NOT NULL,
  iniciado_em   TEXT,
  terminado_em  TEXT,
  duracao_ms    INTEGER,
  rodadas       INTEGER NOT NULL,
  ativos        INTEGER NOT NULL,
  medidos       INTEGER NOT NULL,
  concluiram    INTEGER NOT NULL,
  jubilaram     INTEGER NOT NULL,
  PRIMARY KEY (simulacao_id, periodo)
);

CREATE TABLE rodada (
  simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
  periodo       INTEGER NOT NULL,
  rodada        INTEGER NOT NULL,
  iniciada_em   TEXT,
  terminada_em  TEXT,
  duracao_ms    INTEGER,
  concedidas    INTEGER NOT NULL,
  PRIMARY KEY (simulacao_id, periodo, rodada)
);

CREATE TABLE aluno_periodo (
  simulacao_id     INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
  aluno            TEXT    NOT NULL,
  periodo          INTEGER NOT NULL,
  cr               REAL    NOT NULL,
  reserva          REAL    NOT NULL,
  satisfacao       REAL    NOT NULL,
  aproveitamento   REAL,
  progresso        REAL    NOT NULL,
  rodada_media     REAL,
  vagas            INTEGER NOT NULL,
  carga_obtida     INTEGER NOT NULL,
  carga_cursada    INTEGER NOT NULL,
  carga_aprovada   INTEGER NOT NULL,
  carga_efetiva    INTEGER NOT NULL,
  creditos_inicio  INTEGER,
  creditos_gasto   INTEGER,
  creditos_retorno INTEGER,
  PRIMARY KEY (simulacao_id, aluno, periodo)
);

CREATE TABLE solicitacao (
  simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
  aluno         TEXT    NOT NULL,
  periodo       INTEGER NOT NULL,
  turma         TEXT    NOT NULL,
  utilidade     REAL    NOT NULL,
  lances        TEXT,
  rodada_ganha  INTEGER,
  pago          INTEGER NOT NULL DEFAULT 0,
  excluida      INTEGER NOT NULL DEFAULT 0,
  tentativa     INTEGER,
  nota          REAL,
  aprovada      INTEGER NOT NULL DEFAULT 0,
  retorno       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (simulacao_id, aluno, periodo, turma)
);

-- A turma num período: o ambiente que a demanda de fundo produziu. Por período
-- e não por rodada porque é assim que o motor a publica; o que é fixo na turma
-- (disciplina, carga, horário, nível da grade) está em `turma`.
CREATE TABLE turma_periodo (
  simulacao_id INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
  periodo      INTEGER NOT NULL,
  turma        TEXT    NOT NULL,
  vagas        INTEGER NOT NULL,
  pedidos      INTEGER NOT NULL,   -- de todo mundo, medido ou não
  preenchidas  INTEGER NOT NULL,   -- vaga consumida, **inclusive a garantida**
  concedidas   INTEGER NOT NULL,   -- só as concedidas nas rodadas
  exclusoes    INTEGER NOT NULL,
  aprovacoes   INTEGER NOT NULL,
  preco_medio  REAL,               -- NULL no braço por CR
  PRIMARY KEY (simulacao_id, periodo, turma)
);

CREATE INDEX ix_turma_periodo   ON turma_periodo(simulacao_id, periodo);
CREATE INDEX ix_simulacao_fila  ON simulacao(estado);
CREATE INDEX ix_aluno_periodo   ON aluno_periodo(simulacao_id, periodo);
CREATE INDEX ix_aluno_medido    ON aluno(simulacao_id, medido);
CREATE INDEX ix_solicitacao_var ON solicitacao(simulacao_id, aluno, periodo);
