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
	@cd backend && poetry run uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

.PHONY: verify
verify: ## One-click verify (auto start server if needed + tokens + flow)
	@cd backend && ./scripts/verify.sh

.PHONY: verify-setup
verify-setup: ## chmod +x scripts/verify.sh (first time only)
	@cd backend && chmod +x scripts/verify.sh

# -----------------------------
# Supabase access token (password grant) / Flow
# -----------------------------
.PHONY: token
token: ## Issue access token interactively (loads URL/Key from .env)
	@cd backend && bash scripts/get_token.sh

.PHONY: flow
flow: ## Run flow (assumes server is running and tokens are available inside scripts)
	@cd backend && ./scripts/run_flow.sh

# -----------------------------
# Docker (dev/prod)
# -----------------------------
.PHONY: docker-dev-build
docker-dev-build: ## Build dev image (Dockerfile.dev)
	@cd backend && docker build -f Dockerfile.dev -t $(DEV_IMAGE) .

.PHONY: docker-dev-run
docker-dev-run: ## Run dev image on :8000 using .env
	@cd backend && docker run --rm -p $(PORT):8000 --env-file $(ENV_FILE) $(DEV_IMAGE)

.PHONY: docker-prod-build
docker-prod-build: ## Build prod image (Dockerfile)
	@cd backend && docker build -t $(PROD_IMAGE) .

.PHONY: docker-prod-run
docker-prod-run: ## Run prod image on :8000 using .env
	@cd backend && docker run --rm -p $(PORT):8000 --env-file $(ENV_FILE) $(PROD_IMAGE)

# -----------------------------
# Alembic migrations
# -----------------------------
.PHONY: mig-new
mig-new: ## Create new migration (usage: make mig-new M="message")
	@$(call require_var,M)
	@cd backend && poetry run alembic revision --autogenerate -m "$(M)"

.PHONY: mig-up
mig-up: ## Upgrade to head
	@cd backend && poetry run alembic upgrade head

.PHONY: mig-current
mig-current: ## Show current migration
	@cd backend && poetry run alembic current

.PHONY: mig-heads
mig-heads: ## Show heads
	@cd backend && poetry run alembic heads

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
# AWS tools install/check
# -----------------------------
.PHONY: aws-tools
aws-tools: ## Install AWS tools via script
	@cd backend && ./scripts/install_aws_tools.sh

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

.PHONY: aws-whoami
aws-whoami: ## Check current AWS identity
	aws sts get-caller-identity

.PHONY: copilot-envs
copilot-envs: ## List copilot environments
	@cd backend && copilot env ls

.PHONY: copilot-status-staging
copilot-status-staging: ## Show staging service status
	@cd backend && copilot svc status --name api --env staging

.PHONY: copilot-status-prod
copilot-status-prod: ## Show prod service status
	@cd backend && copilot svc status --name api --env prod

.PHONY: copilot-deploy-staging
copilot-deploy-staging: ## Manually deploy to staging
	@cd backend && copilot svc deploy --name api --env staging

.PHONY: copilot-deploy-prod
copilot-deploy-prod: ## Manually deploy to prod (use with caution)
	@cd backend && copilot svc deploy --name api --env prod

.PHONY: copilot-logs-staging
copilot-logs-staging: ## Follow staging logs
	@cd backend && copilot svc logs --name api --env staging --follow

.PHONY: copilot-logs-prod
copilot-logs-prod: ## Follow prod logs
	@cd backend && copilot svc logs --name api --env prod --follow

.PHONY: copilot-exec-staging
copilot-exec-staging: ## Exec into staging task
	@cd backend && copilot svc exec --name api --env staging

.PHONY: check-db
check-db: ## Check database connection status
	@cd backend && poetry run python -m scripts.check_db_connection

.PHONY: check-schema
check-schema: ## Verify if database tables and columns are created correctly
	@cd backend && poetry run python -m scripts.check_schema

.PHONY: reset-db
reset-db: ## db reset
	@cd backend && poetry run python -m scripts.reset_db

.PHONY: release
release: ## Interactive: switch to main, pull, tag & push; then return to previous ref
	@set -e; \
	# remember current ref (branch or detached) \
	ORIG_BRANCH="$$(git symbolic-ref --short -q HEAD || true)"; \
	ORIG_COMMIT="$$(git rev-parse --verify HEAD)"; \
	RETURNED=0; \
	restore() { \
		if [ "$$RETURNED" = "1" ]; then exit 0; fi; \
		RETURNED=1; \
		echo "==> Restoring previous state..."; \
		if [ -n "$$ORIG_BRANCH" ]; then \
			git switch "$$ORIG_BRANCH" >/dev/null 2>&1 || true; \
		else \
			git switc

.PHONY: branch-reset
branch-reset: ## Switch to staging, pull latest, delete local+remote branch, create new branch (interactive)
	@bash -eu -o pipefail -c '\
		# 1. 현재 상태 확인 및 Main 브랜치 동기화 \
		echo "==> Current branch:"; \
		current="$$(git rev-parse --abbrev-ref HEAD)"; \
		echo "    $$current"; \
		echo ""; \
		echo "🔄 Syncing local MAIN branch..."; \
		git fetch origin main:main 2>/dev/null || (git switch main >/dev/null && git pull origin main && git switch - >/dev/null); \
		echo "   ✅ Main is up-to-date."; \
		echo ""; \
		\
		# 2. Staging 브랜치 동기화 \
		echo "🔄 Switching to staging & pulling latest..."; \
		git switch staging >/dev/null; \
		git pull --prune origin staging; \
		echo ""; \
		\
		# 3. 브랜치 목록 출력 \
		echo "==> Local branches:"; \
		git branch --format="%(refname:short)" | sed "s/^/   - /"; \
		echo ""; \
		echo "==> Remote branches (origin):"; \
		git branch -r --format="%(refname:short)" | sed "s/^/   - /"; \
		echo ""; \
		\
		# 4. 브랜치 삭제 로직 \
		read -r -p "Branch to DELETE (name only, e.g. feature/posts). Leave empty to cancel: " del; \
		if [ -z "$$del" ]; then \
			echo "Cancelled."; \
			exit 0; \
		fi; \
		if [ "$$del" = "main" ]; then \
			echo "ERROR: refusing to delete '\''main'\''."; \
			exit 1; \
		fi; \
		if [ "$$del" = "staging" ]; then \
			echo "ERROR: refusing to delete '\''staging'\''."; \
			exit 1; \
		fi; \
		if [ "$$del" = "$$current" ]; then \
			echo "NOTE: you were on '\''$$current'\''; already switched to staging."; \
		fi; \
		\
		# 5. 새 브랜치 이름 입력 \
		read -r -p "New branch to CREATE (e.g. feature/posts): " new; \
		if [ -z "$$new" ]; then \
			echo "ERROR: new branch name is required."; \
			exit 1; \
		fi; \
		echo ""; \
		\
		# 6. 실제 삭제 실행 \
		echo "==> Deleting local branch (if exists): $$del"; \
		git branch -D "$$del" 2>/dev/null || echo "  (local branch not found)"; \
		echo "==> Deleting remote branch (if exists): origin/$$del"; \
		git push origin --delete "$$del" 2>/dev/null || echo "  (remote branch not found)"; \
		echo ""; \
		\
		# 7. 새 브랜치 생성 및 이동 \
		echo "==> Creating and switching to: $$new (from updated staging)"; \
		git switch -c "$$new"; \
		echo "==> Creating remote branch + setting upstream: origin/$$new"; \
		git push -u origin "$$new"; \
		echo ""; \
		echo "Done. Now on branch: $$(git rev-parse --abbrev-ref HEAD)"; \
	'

.PHONY: rollback-dry
rollback-dry: ## [Safe] Simulate rollback: Show file changes without modifying anything
	@bash -eu -o pipefail -c '\
		echo "🔍 [DRY RUN] checking rollback diff..."; \
		# 1. Main 최신화 (변경사항 없이 확인만) \
		git fetch origin main; \
		\
		# 2. 태그 목록 보여주기 \
		echo ""; \
		echo "📜 Recent Tags:"; \
		git tag -l "v*" --sort=-v:refname | head -n 10; \
		echo ""; \
		read -r -p "Enter TAG to rollback to (e.g. v0.1.0): " TARGET_TAG; \
		if [ -z "$$TARGET_TAG" ]; then echo "❌ Error: Tag is required."; exit 1; fi; \
		\
		# 3. 변경사항 미리보기 (Diff Stat) \
		echo ""; \
		echo "📊 If you rollback to $$TARGET_TAG, these files will change:"; \
		echo "-------------------------------------------------------------"; \
		git diff --stat origin/main "$$TARGET_TAG"; \
		echo "-------------------------------------------------------------"; \
		echo ""; \
		echo "✅ Dry run complete. Nothing changed."; \
		echo "👉 To execute for real: make rollback"; \
	'

.PHONY: rollback
rollback: ## [Danger] Rollback Main branch to specific Tag/Commit (Triggers Deploy)
	@bash -eu -o pipefail -c '\
		echo "⚠️  [DANGER] Rolling back MAIN branch content..."; \
		if [ -n "$$(git status --porcelain)" ]; then \
			echo "❌ Error: Working tree is not clean. Commit or stash changes first."; \
			exit 1; \
		fi; \
		\
		echo "🔄 Switching to main and pulling latest..."; \
		git switch main; \
		git pull origin main; \
		\
		echo ""; \
		echo "📜 Recent Tags:"; \
		git tag -l "v*" --sort=-v:refname | head -n 10; \
		echo ""; \
		read -r -p "Enter TAG to rollback to (e.g. v0.1.0): " TARGET_TAG; \
		if [ -z "$$TARGET_TAG" ]; then echo "❌ Error: Tag is required."; exit 1; fi; \
		\
		if ! git rev-parse "$$TARGET_TAG" >/dev/null 2>&1; then \
			echo "❌ Error: Tag $$TARGET_TAG not found."; \
			exit 1; \
		fi; \
		\
		echo ""; \
		echo "=================================================="; \
		echo "🚨 ROLLBACK CONFIRMATION"; \
		echo "Target Tag  : $$TARGET_TAG"; \
		echo "Action      : Overwrite Main code with $$TARGET_TAG content"; \
		echo "Result      : This will create a NEW commit on Main and TRIGGER DEPLOY."; \
		echo "=================================================="; \
		read -r -p "Type YES to proceed: " CONFIRM; \
		if [ "$$CONFIRM" != "YES" ]; then echo "🚫 Aborted."; exit 1; fi; \
		\
		echo "🔄 Reverting code to $$TARGET_TAG..."; \
		git checkout "$$TARGET_TAG" -- . ; \
		echo "📦 Committing rollback..."; \
		git commit -m "revert: rollback to $$TARGET_TAG"; \
		\
		echo "🚀 Pushing to Main (Deploy will start)..."; \
		git push origin main; \
		echo "✅ Rollback initiated successfully!"; \
	'

.PHONY: alarms-prod-dim
alarms-prod-dim: ## Print PROD ALB/TG suffix (for CloudWatch dimensions)
	@bash -eu -o pipefail -c '\
		STACK_NAME="$$(aws cloudformation list-stacks \
		  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
		  --query "StackSummaries[?contains(StackName, \`crm-prod-api\`) == \`true\`].StackName" \
		  --output text | tr "\t" "\n" | grep -v AddonsStack | head -n 1)"; \
		if [ -z "$$STACK_NAME" ]; then echo "ERROR: prod stack not found (crm-prod-api)"; exit 1; fi; \
		echo "==> Stack: $$STACK_NAME"; \
		echo "==> TargetGroups:"; \
		aws cloudformation describe-stack-resources \
		  --stack-name "$$STACK_NAME" \
		  --query "StackResources[?ResourceType==\`AWS::ElasticLoadBalancingV2::TargetGroup\`].[LogicalResourceId,PhysicalResourceId]" \
		  --output table; \
		echo ""; \
		read -r -p "Enter TG_ARN from table: " TG_ARN; \
		if [ -z "$$TG_ARN" ]; then echo "ERROR: TG_ARN is required."; exit 1; fi; \
		LB_ARN="$$(aws elbv2 describe-target-groups --target-group-arns "$$TG_ARN" --query "TargetGroups[0].LoadBalancerArns[0]" --output text)"; \
		PROD_TG_SUFFIX="$$(echo "$$TG_ARN" | sed "s#^.*targetgroup/##")"; \
		PROD_LB_SUFFIX="$$(echo "$$LB_ARN" | sed "s#^.*loadbalancer/##")"; \
		echo "PROD_LB_SUFFIX=$$PROD_LB_SUFFIX"; \
		echo "PROD_TG_SUFFIX=$$PROD_TG_SUFFIX"; \
	'

.PHONY: alarms-stg-dim
alarms-stg-dim: ## Print STAGING ALB/TG suffix (for CloudWatch dimensions)
	@bash -eu -o pipefail -c '\
		STACK_NAME="$$(aws cloudformation list-stacks \
		  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
		  --query "StackSummaries[?contains(StackName, \`crm-staging-api\`) == \`true\`].StackName" \
		  --output text | tr "\t" "\n" | grep -v AddonsStack | head -n 1)"; \
		if [ -z "$$STACK_NAME" ]; then echo "ERROR: staging stack not found (crm-staging-api)"; exit 1; fi; \
		echo "==> Stack: $$STACK_NAME"; \
		echo "==> TargetGroups:"; \
		aws cloudformation describe-stack-resources \
		  --stack-name "$$STACK_NAME" \
		  --query "StackResources[?ResourceType==\`AWS::ElasticLoadBalancingV2::TargetGroup\`].[LogicalResourceId,PhysicalResourceId]" \
		  --output table; \
		echo ""; \
		read -r -p "Enter TG_ARN from table: " TG_ARN; \
		if [ -z "$$TG_ARN" ]; then echo "ERROR: TG_ARN is required."; exit 1; fi; \
		LB_ARN="$$(aws elbv2 describe-target-groups --target-group-arns "$$TG_ARN" --query "TargetGroups[0].LoadBalancerArns[0]" --output text)"; \
		STG_TG_SUFFIX="$$(echo "$$TG_ARN" | sed "s#^.*targetgroup/##")"; \
		STG_LB_SUFFIX="$$(echo "$$LB_ARN" | sed "s#^.*loadbalancer/##")"; \
		echo "STG_LB_SUFFIX=$$STG_LB_SUFFIX"; \
		echo "STG_TG_SUFFIX=$$STG_TG_SUFFIX"; \
	'