SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# -----------------------------
# Config (override like: make server PORT=9000)
# -----------------------------
PORT ?= 8000
HOST ?= 0.0.0.0
BASE_URL ?= http://127.0.0.1:$(PORT)
APP ?= app.main:app

# Docker
DEV_IMAGE ?= crm-dev
PROD_IMAGE ?= crm-prod
ENV_FILE ?= .env

# Grep
Q ?=
EXCLUDE_VENV ?= 1

# Supabase (set in env or inline)
SUPABASE_URL ?=
SUPABASE_ANON_KEY ?=
EMAIL ?=
PASSWORD ?=

# Docker container name filter for stop
NAME ?= crm-backend

# -----------------------------
# Helpers
# -----------------------------
.PHONY: help
help: ## Show this help
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: _require
_require:
	@true

define require_var
	@if [ -z "$($1)" ]; then echo "❌ Missing required var: $1"; exit 1; fi
endef

# -----------------------------
# Server
# -----------------------------
.PHONY: server
server: ## Run backend server (reload)
	poetry run uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

.PHONY: verify
verify: ## One-click verify (auto start server if needed + tokens + flow)
	./scripts/verify.sh

.PHONY: verify-setup
verify-setup: ## chmod +x scripts/verify.sh (first time only)
	chmod +x scripts/verify.sh

# -----------------------------
# Tokens / Flow
# -----------------------------
.PHONY: tokens
tokens: ## Issue dev tokens (source scripts/dev_tokens.sh + load_tokens.sh)
	@set -euo pipefail; \
	source scripts/dev_tokens.sh; \
	source scripts/load_tokens.sh; \
	echo "BASE_URL=$${BASE_URL:-$(BASE_URL)}"; \
	echo "HOST_TOKEN length=$${#HOST_TOKEN}"; \
	echo "GUEST_TOKEN length=$${#GUEST_TOKEN}"; \
	echo "HOST_ID=$${HOST_ID}"

.PHONY: flow
flow: ## Run flow (assumes server is running and tokens are available inside scripts)
	./scripts/run_flow.sh

# -----------------------------
# Docker (dev/prod)
# -----------------------------
.PHONY: docker-dev-build
docker-dev-build: ## Build dev image (Dockerfile.dev)
	docker build -f Dockerfile.dev -t $(DEV_IMAGE) .

.PHONY: docker-dev-run
docker-dev-run: ## Run dev image on :8000 using .env
	docker run --rm -p $(PORT):8000 --env-file $(ENV_FILE) $(DEV_IMAGE)

.PHONY: docker-prod-build
docker-prod-build: ## Build prod image (Dockerfile)
	docker build -t $(PROD_IMAGE) .

.PHONY: docker-prod-run
docker-prod-run: ## Run prod image on :8000 using .env
	docker run --rm -p $(PORT):8000 --env-file $(ENV_FILE) $(PROD_IMAGE)

# -----------------------------
# Alembic migrations
# -----------------------------
.PHONY: mig-new
mig-new: ## Create new migration (usage: make mig-new M="message")
	@$(call require_var,M)
	poetry run alembic revision --autogenerate -m "$(M)"

.PHONY: mig-up
mig-up: ## Upgrade to head
	poetry run alembic upgrade head

.PHONY: mig-current
mig-current: ## Show current migration
	poetry run alembic current

.PHONY: mig-heads
mig-heads: ## Show heads
	poetry run alembic heads

# -----------------------------
# CI trigger
# -----------------------------
.PHONY: ci-trigger
ci-trigger: ## Trigger CI with empty commit (then push)
	git commit --allow-empty -m "chore: trigger ci"
	git push

# -----------------------------
# Grep helpers
# -----------------------------
.PHONY: grep
grep: ## Search string (usage: make grep Q="text")
	@$(call require_var,Q)
	@if [ "$(EXCLUDE_VENV)" = "1" ]; then \
		grep -RIn --exclude-dir=.venv --exclude-dir=.git "$(Q)" . ; \
	else \
		grep -RIn "$(Q)" . ; \
	fi

# -----------------------------
# Supabase access token (password grant)
# -----------------------------
.PHONY: supabase-token
supabase-token: ## Prompt for SUPABASE_URL/ANON_KEY/EMAIL/PASSWORD then fetch token
	@set -euo pipefail; \
	if [ -z "$${SUPABASE_URL:-}" ]; then \
	  read -r -p "SUPABASE_URL (e.g. https://xxxx.supabase.co): " SUPABASE_URL; \
	fi; \
	if [ -z "$${SUPABASE_ANON_KEY:-}" ]; then \
	  read -r -s -p "SUPABASE_ANON_KEY: " SUPABASE_ANON_KEY; echo; \
	fi; \
	if [ -z "$${EMAIL:-}" ]; then \
	  read -r -p "EMAIL: " EMAIL; \
	fi; \
	if [ -z "$${PASSWORD:-}" ]; then \
	  read -r -s -p "PASSWORD: " PASSWORD; echo; \
	fi; \
	\
	# basic guard against placeholders \
	case "$$SUPABASE_URL" in *"..."*|*"<"*">"*) echo "❌ SUPABASE_URL looks like a placeholder. Use a real https://<ref>.supabase.co"; exit 1;; esac; \
	\
	curl -sS "$$SUPABASE_URL/auth/v1/token?grant_type=password" \
	  -H "apikey: $$SUPABASE_ANON_KEY" \
	  -H "Authorization: Bearer $$SUPABASE_ANON_KEY" \
	  -H "Content-Type: application/json" \
	  -d "{\"email\":\"$$EMAIL\",\"password\":\"$$PASSWORD\"}" | python -m json.tool

# -----------------------------
# AWS tools install/check
# -----------------------------
.PHONY: aws-tools
aws-tools: ## Install AWS tools via script
	./scripts/install_aws_tools.sh

.PHONY: aws-check
aws-check: ## Check aws/copilot versions (and hint PATH if missing)
	@set -e; \
	if command -v aws >/dev/null 2>&1; then aws --version; else echo "aws: command not found (try: export PATH=\"$$HOME/.local/bin:$$PATH\")"; fi; \
	if command -v copilot >/dev/null 2>&1; then copilot --version; else echo "copilot: command not found (try: export PATH=\"$$HOME/.local/bin:$$PATH\")"; fi

# -----------------------------
# Docker process helpers
# -----------------------------
.PHONY: docker-ps
docker-ps: ## List containers filtered by name (usage: make docker-ps NAME=crm-backend)
	docker ps -a --filter name=$(NAME)

.PHONY: docker-stop
docker-stop: ## Stop container by ID or name (usage: make docker-stop ID=<container_id_or_name>)
	@$(call require_var,ID)
	docker stop "$(ID)"

# =============================
# 기존 Makefile 내용은 절대 수정하지 말 것
# 아래는 AWS / Copilot 운영 편의용 추가 타겟
# =============================

.PHONY: aws-whoami
aws-whoami: ## Check current AWS identity
	aws sts get-caller-identity

.PHONY: copilot-envs
copilot-envs: ## List copilot environments
	copilot env ls

.PHONY: copilot-status-staging
copilot-status-staging: ## Show staging service status
	copilot svc status --name api --env staging

.PHONY: copilot-status-prod
copilot-status-prod: ## Show prod service status
	copilot svc status --name api --env prod

.PHONY: copilot-deploy-staging
copilot-deploy-staging: ## Manually deploy to staging
	copilot svc deploy --name api --env staging

.PHONY: copilot-deploy-prod
copilot-deploy-prod: ## Manually deploy to prod (use with caution)
	copilot svc deploy --name api --env prod

.PHONY: copilot-logs-staging
copilot-logs-staging: ## Follow staging logs
	copilot svc logs --name api --env staging --follow

.PHONY: copilot-logs-prod
copilot-logs-prod: ## Follow prod logs
	copilot svc logs --name api --env prod --follow

.PHONY: copilot-exec-staging
copilot-exec-staging: ## Exec into staging task
	copilot svc exec --name api --env staging
