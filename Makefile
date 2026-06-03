# Load .env as make variables and export to child processes
-include .env
export

.PHONY: setup install install-etl install-dashboard install-api install-dev \
        etl dashboard api train-model \
        lint lint-fix format test clean

UV     := uv
RUN    := uv run
STREAM := src/icfes/dashboard/app.py
API    := icfes.api.main:app

# ── Bootstrap ─────────────────────────────────────────────────────────────────

# First-time setup: copy .env.example → .env (if missing) then install all deps
setup: .env install

.env:
	cp .env.example .env
	@echo ">> .env created. Fill in credentials before running cloud targets."

# ── Install ───────────────────────────────────────────────────────────────────

install:
	$(UV) sync --all-extras

install-etl:
	$(UV) sync --extra etl

install-dashboard:
	$(UV) sync --extra etl --extra dashboard

install-api:
	$(UV) sync --extra etl --extra api

install-dev:
	$(UV) sync --all-extras

# ── Run ───────────────────────────────────────────────────────────────────────

etl:
	$(RUN) python main.py

dashboard:
	$(UV) run --extra dashboard streamlit run $(STREAM)

api:
	$(UV) run --extra api uvicorn $(API) --reload --host $(API_HOST) --port $(API_PORT)

train-model:
	$(UV) run --extra etl --extra dashboard python scripts/train_simulador.py

# ── Quality ───────────────────────────────────────────────────────────────────

lint:
	$(UV) run --extra dev ruff check src/

lint-fix:
	$(UV) run --extra dev ruff check --fix src/

format:
	$(UV) run --extra dev ruff format src/

test:
	$(UV) run --extra dev pytest tests/ -v --cov=src/icfes

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	$(RUN) python -c "import shutil, pathlib; \
	  [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]; \
	  [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
	$(RUN) python -c "import shutil; \
	  [shutil.rmtree(d, ignore_errors=True) for d in ('dist','build') \
	   if __import__('pathlib').Path(d).exists()]"
