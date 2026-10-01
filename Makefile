# Atalhos do simulador. Todos delegam para o PowerShell, que e o shell de
# verdade do projeto -- assim os alvos funcionam chamados do PowerShell,
# do cmd ou do Git Bash, sem depender de qual shell o make escolheu.

PS := powershell -NoProfile -ExecutionPolicy Bypass
PY := ./.venv/Scripts/python.exe

.PHONY: dev api web test example install

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
