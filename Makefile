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
			git switch --detach "$$ORIG_COMMIT" >/dev/null 2>&1 || true; \
		fi; \
	}; \
	trap 'restore' EXIT INT TERM; \
	\
	# working tree must be clean \
	if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: Working tree is not clean. Commit/stash first."; \
		git status --porcelain; \
		exit 1; \
	fi; \
	\
	echo "==> Switching to main & pulling latest..."; \
	git switch main >/dev/null; \
	git pull origin main; \
	\
	LATEST_TAG="$$(git tag -l 'v*' --sort=-v:refname | head -n 1)"; \
	if [ -z "$$LATEST_TAG" ]; then LATEST_TAG="(none)"; fi; \
	echo "Latest tag: $$LATEST_TAG"; \
	\
	read -p "Enter version tag (e.g. v0.1.1 or 0.1.1): " VERSION; \
	# trim spaces \
	VERSION="$$(printf "%s" "$$VERSION" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$$//')"; \
	if [ -z "$$VERSION" ]; then \
		echo "ERROR: version is required."; \
		exit 1; \
	fi; \
	# auto-prefix v \
	case "$$VERSION" in v*) ;; *) VERSION="v$$VERSION";; esac; \
	echo "==> Using tag: $$VERSION"; \
	\
	# local tag exists? \
	if git rev-parse "$$VERSION" >/dev/null 2>&1; then \
		echo "ERROR: tag '$$VERSION' already exists (local). Choose a new version."; \
		exit 1; \
	fi; \
	# remote tag exists? (covers 'exists on origin but not locally') \
	if git ls-remote --tags origin "$$VERSION" | grep -q "$$VERSION"; then \
		echo "ERROR: tag '$$VERSION' already exists on origin. Choose a new version."; \
		exit 1; \
	fi; \
	\
	echo "==> Creating annotated tag $$VERSION (message: Release $$VERSION)"; \
	git tag -a "$$VERSION" -m "Release $$VERSION"; \
	echo "==> Pushing tag $$VERSION to origin (this triggers prod deploy)..."; \
	git push origin "$$VERSION"; \
	echo "✅ Done. Pushed tag $$VERSION."; \
	\
	# (optional) show where we will return \
	if [ -n "$$ORIG_BRANCH" ]; then \
		echo "==> Will return to branch: $$ORIG_BRANCH"; \
	else \
		echo "==> Will return to detached commit: $$ORIG_COMMIT"; \
	fi

.PHONY: branch-reset
branch-reset: ## Switch to main, pull latest, delete local+remote branch, create new branch (interactive)
	@bash -eu -o pipefail -c '\
		echo "==> Current branch:"; \
		current="$$(git rev-parse --abbrev-ref HEAD)"; \
		echo "    $$current"; \
		echo ""; \
		echo "==> Switching to main & pulling latest..."; \
		git switch main >/dev/null; \
		git pull origin main; \
		echo ""; \
		echo "==> Local branches:"; \
		git branch --format="%(refname:short)" | sed "s/^/  - /"; \
		echo ""; \
		echo "==> Remote branches (origin):"; \
		git branch -r --format="%(refname:short)" | sed "s/^/  - /"; \
		echo ""; \
		read -r -p "Branch to DELETE (name only, e.g. feature/posts). Leave empty to cancel: " del; \
		if [ -z "$$del" ]; then \
			echo "Cancelled."; \
			exit 0; \
		fi; \
		if [ "$$del" = "main" ]; then \
			echo "ERROR: refusing to delete '\''main'\''."; \
			exit 1; \
		fi; \
		if [ "$$del" = "$$current" ]; then \
			echo "NOTE: you were on '\''$$current'\''; already switched to main."; \
		fi; \
		read -r -p "New branch to CREATE (e.g. feature/posts): " new; \
		if [ -z "$$new" ]; then \
			echo "ERROR: new branch name is required."; \
			exit 1; \
		fi; \
		echo ""; \
		echo "==> Deleting local branch (if exists): $$del"; \
		git branch -D "$$del" 2>/dev/null || echo "  (local branch not found)"; \
		echo "==> Deleting remote branch (if exists): origin/$$del"; \
		git push origin --delete "$$del" 2>/dev/null || echo "  (remote branch not found)"; \
		echo ""; \
		echo "==> Creating and switching to: $$new (from updated main)"; \
		git switch -c "$$new"; \
		echo "==> Creating remote branch + setting upstream: origin/$$new"; \
		git push -u origin "$$new"; \
		echo ""; \
		echo "Done. Now on branch: $$(git rev-parse --abbrev-ref HEAD)"; \
	'

.PHONY: rollback-dry
rollback-dry: ## Interactive: show what rollback would do (NO tag created, NO push)
	@set -e; \
	# 작업트리 깨끗한지 확인 \
	if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: Working tree is not clean. Commit/stash first."; \
		git status --porcelain; \
		exit 1; \
	fi; \
	echo "==> Switching to main & pulling latest..."; \
	git switch main >/dev/null; \
	git pull origin main; \
	echo "==> Fetching tags..."; \
	git fetch --tags; \
	echo "Recent tags:"; \
	git tag -l 'v*' --sort=-v:refname | head -n 10; \
	read -p "Enter FROM tag to rollback to (e.g. v0.1.3): " FROM; \
	if [ -z "$$FROM" ]; then \
		echo "ERROR: FROM tag is required."; \
		exit 1; \
	fi; \
	case "$$FROM" in v*) ;; *) echo "ERROR: FROM tag must start with 'v' (e.g. v0.1.3)"; exit 1;; esac; \
	if ! git rev-parse "$$FROM" >/dev/null 2>&1; then \
		echo "ERROR: FROM tag '$$FROM' does not exist (local). Did you fetch tags?"; \
		exit 1; \
	fi; \
	read -p "Enter NEW tag to create for rollback (e.g. v0.1.4): " TO; \
	if [ -z "$$TO" ]; then \
		echo "ERROR: TO tag is required."; \
		exit 1; \
	fi; \
	case "$$TO" in v*) ;; *) echo "ERROR: TO tag must start with 'v' (e.g. v0.1.4)"; exit 1;; esac; \
	if git rev-parse "$$TO" >/dev/null 2>&1; then \
		echo "ERROR: tag '$$TO' already exists (local). Choose a new version."; \
		exit 1; \
	fi; \
	FROM_SHA="$$(git rev-list -n 1 "$$FROM")"; \
	echo ""; \
	echo "=== DRY RUN (no changes will be made) ==="; \
	echo "Would create annotated tag: $$TO"; \
	echo "  points to tag: $$FROM"; \
	echo "  FROM sha: $$FROM_SHA"; \
	echo "  message : rollback: $$FROM -> $$TO"; \
	echo "Would push: git push origin $$TO"; \
	echo "========================================"; \
	echo ""; \
	echo "✅ Dry run complete. To execute for real: make rollback"


.PHONY: rollback
rollback-safe:
	@set -e; \
	# 작업트리 깨끗한지 확인(운영 사고 시 실수 방지) \
	if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: Working tree is not clean. Commit/stash first."; \
		git status --porcelain; \
		exit 1; \
	fi; \
	echo "==> Switching to main & pulling latest..."; \
	git switch main >/dev/null; \
	git pull origin main; \
	echo "==> Fetching tags..."; \
	git fetch --tags; \
	echo "Recent tags:"; \
	git tag -l 'v*' --sort=-v:refname | head -n 10; \
	read -p "Enter FROM tag to rollback to (e.g. v0.1.3): " FROM; \
	if [ -z "$$FROM" ]; then \
		echo "ERROR: FROM tag is required."; \
		exit 1; \
	fi; \
	case "$$FROM" in v*) ;; *) echo "ERROR: FROM tag must start with 'v' (e.g. v0.1.3)"; exit 1;; esac; \
	if ! git rev-parse "$$FROM" >/dev/null 2>&1; then \
		echo "ERROR: FROM tag '$$FROM' does not exist (local). Did you fetch tags?"; \
		exit 1; \
	fi; \
	read -p "Enter NEW tag to create for rollback (e.g. v0.1.4): " TO; \
	if [ -z "$$TO" ]; then \
		echo "ERROR: TO tag is required."; \
		exit 1; \
	fi; \
	case "$$TO" in v*) ;; *) echo "ERROR: TO tag must start with 'v' (e.g. v0.1.4)"; exit 1;; esac; \
	if git rev-parse "$$TO" >/dev/null 2>&1; then \
		echo "ERROR: tag '$$TO' already exists (local). Choose a new version."; \
		exit 1; \
	fi; \
	FROM_SHA="$$(git rev-list -n 1 "$$FROM")"; \
	echo ""; \
	echo "=== FINAL CONFIRMATION REQUIRED ==="; \
	echo "You are about to ROLLBACK prod by pushing a NEW tag:"; \
	echo "  FROM tag : $$FROM (sha: $$FROM_SHA)"; \
	echo "  NEW  tag : $$TO"; \
	echo "This will trigger prod deploy via deploy.yml"; \
	echo ""; \
	read -p "Type YES to continue: " CONFIRM; \
	if [ "$$CONFIRM" != "YES" ]; then \
		echo "Aborted. (You did not type YES)"; \
		exit 1; \
	fi; \
	echo "==> Creating annotated tag $$TO pointing to $$FROM (message: rollback: $$FROM -> $$TO)"; \
	git tag -a "$$TO" "$$FROM" -m "rollback: $$FROM -> $$TO"; \
	echo "==> Pushing tag $$TO to origin (this triggers prod deploy)..."; \
	git push origin "$$TO"; \
	echo "✅ Done. Rolled back by pushing tag $$TO (points to $$FROM)."

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
