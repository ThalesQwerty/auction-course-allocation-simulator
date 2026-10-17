# Atalhos do simulador.
# Windows: delega para o PowerShell (dev.ps1), então o alvo funciona no
# PowerShell, no cmd e no Git Bash.
# Mac/Linux/UNIX: os mesmos alvos rodam direto no sh.

ifeq ($(OS),Windows_NT)
PY := ./.venv/Scripts/python.exe
PS := powershell -NoProfile -ExecutionPolicy Bypass
else
PY := ./.venv/bin/python
endif

.PHONY: dev api web test example install

ifeq ($(OS),Windows_NT)

# sobe API + interface juntas (Ctrl+C derruba as duas)
dev:
	$(PS) -File dev.ps1

# so o servidor FastAPI, em http://localhost:8000
api:
	$(PS) -Command "& $(PY) -m uvicorn leilao.api.main:app --reload --port 8000"

# so a interface Vite, em http://localhost:5173
web:
	$(PS) -Command "Set-Location web; npm run dev"

# suite pytest
test:
	$(PS) -Command "& $(PY) -m pytest tests/ -v"

# cenario de exemplo direto no terminal
example:
	$(PS) -Command "& $(PY) examples/simple_scenario.py"

# venv + dependencias do motor e da interface
install:
	$(PS) -Command "if (-not (Test-Path .venv)) { py -3.13 -m venv .venv }"
	$(PS) -Command "& $(PY) -m pip install -e .[dev]"
	$(PS) -Command "Set-Location web; npm install"

else

# sobe API + interface juntas (Ctrl+C derruba as duas)
dev:
	@test -x $(PY) || { printf '%s\n' "Virtualenv não encontrada em '$(PY)'. Rode: make install"; exit 1; }
	@command -v npm >/dev/null 2>&1 || { printf '%s\n' "npm não encontrado no PATH. Instale o Node.js."; exit 1; }
	@if [ ! -d web/node_modules ]; then \
		printf '%s\n' "[dev] web/node_modules ausente — rodando npm install..."; \
		(cd web && npm install) || exit 1; \
	fi
	@printf '%s\n' "[dev] API  -> http://localhost:8000  (docs em /docs)" "[dev] Web  -> http://localhost:5173" "[dev] Ctrl+C encerra os dois."
	@set -eu; \
	tmpdir=$$(mktemp -d); \
	mkfifo "$$tmpdir/api" "$$tmpdir/web"; \
	prefix() { \
		tag=$$1; \
		while IFS= read -r line || [ -n "$$line" ]; do \
			printf '[%s] %s\n' "$$tag" "$$line"; \
		done; \
	}; \
	prefix api < "$$tmpdir/api" & \
	api_log=$$!; \
	prefix web < "$$tmpdir/web" & \
	web_log=$$!; \
	PYTHONUNBUFFERED=1 $(PY) -m uvicorn leilao.api.main:app --reload --port 8000 > "$$tmpdir/api" 2>&1 & \
	api_pid=$$!; \
	(cd web && npm run dev -- --port 5173 --strictPort) > "$$tmpdir/web" 2>&1 & \
	web_pid=$$!; \
	kill_tree() { \
		_pid=$$1; \
		_kids=$$(pgrep -P "$$_pid" 2>/dev/null || true); \
		for _child in $$_kids; do \
			kill_tree "$$_child"; \
		done; \
		kill -KILL "$$_pid" 2>/dev/null || true; \
	}; \
	cleaned=0; \
	cleanup() { \
		if [ "$$cleaned" -eq 1 ]; then \
			return; \
		fi; \
		cleaned=1; \
		kill_tree "$$api_pid"; \
		kill_tree "$$web_pid"; \
		wait "$$api_pid" "$$web_pid" 2>/dev/null || true; \
		wait "$$api_log" "$$web_log" 2>/dev/null || true; \
		rm -rf "$$tmpdir"; \
		printf '%s\n' "[dev] encerrado."; \
	}; \
	trap 'cleanup; exit 130' INT; \
	trap 'cleanup; exit 143' TERM; \
	trap cleanup EXIT; \
	while kill -0 "$$api_pid" 2>/dev/null && kill -0 "$$web_pid" 2>/dev/null; do \
		sleep 0.2; \
	done; \
	status=0; \
	if ! kill -0 "$$api_pid" 2>/dev/null; then \
		wait "$$api_pid" || status=$$?; \
	fi; \
	if ! kill -0 "$$web_pid" 2>/dev/null; then \
		wait "$$web_pid" || status=$$?; \
	fi; \
	printf '%s\n' "[dev] um dos processos terminou (código $$status); encerrando o outro."; \
	exit "$$status"

# so o servidor FastAPI, em http://localhost:8000
api:
	$(PY) -m uvicorn leilao.api.main:app --reload --port 8000

# so a interface Vite, em http://localhost:5173
web:
	cd web && npm run dev

# suite pytest
test:
	$(PY) -m pytest tests/ -v

# cenario de exemplo direto no terminal
example:
	$(PY) examples/simple_scenario.py

# venv + dependencias do motor e da interface
install:
	test -d .venv || python3 -m venv .venv
	$(PY) -m pip install -e '.[dev]'
	cd web && npm install

endif
