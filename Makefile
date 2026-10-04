SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# =============================================================================
# 타깃 이름 규칙: <대상><동작>, 소문자 붙여쓰기 (예: iweb = 강사 앱 웹 실행)
#   대상  api 백엔드 | web 관리자·강사 웹 | c 고객 앱 | i 강사 앱 | db 데이터베이스
#         mig 마이그레이션 | dock Docker | git 브랜치·배포 | aws AWS 도구 | stg / prod Copilot 환경
#   예외  help, check(전체 검증), grep
# =============================================================================

# -----------------------------
# Config (override like: make api PORT=9000)
# -----------------------------
PORT ?= 8000
HOST ?= 0.0.0.0
APP ?= app.main:app

# Docker
IMAGE ?= crm-backend
ENV_FILE ?= .env
NAME ?= crm-backend

# Grep
Q ?=

define require_var
	@if [ -z "$($1)" ]; then echo "❌ Missing required var: $1"; exit 1; fi
endef

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)} /^[a-zA-Z0-9_]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ 실행
.PHONY: api
api: ## Run backend dev server (reload, uses backend/.env)
	@cd backend && poetry run uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

.PHONY: web
web: ## Run admin/instructor web (Next.js dev, clears .next cache)
	@cd frontend && rm -rf .next && npm run dev

.PHONY: cweb
cweb: ## Run customer app in browser (Expo web)
	@cd apps/customer && npx expo start --web

.PHONY: ctunnel
ctunnel: ## Run customer app with tunnel (QR code for real device)
	@NGROK_TOKEN=$$(grep -s '^NGROK_AUTHTOKEN=' apps/.env | cut -d= -f2); \
	if [ -n "$$NGROK_TOKEN" ]; then \
		apps/customer/node_modules/@expo/ngrok-bin-linux-x64/ngrok authtoken "$$NGROK_TOKEN" 2>/dev/null || true; \
	fi; \
	cd apps/customer && npx expo start --tunnel

.PHONY: iweb
iweb: ## Run instructor app in browser (Expo web, port 8082)
	@cd apps/instructor && npx expo start --web --port 8082

.PHONY: itunnel
itunnel: ## Run instructor app with tunnel (QR code for real device)
	@NGROK_TOKEN=$$(grep -s '^NGROK_AUTHTOKEN=' apps/.env | cut -d= -f2); \
	if [ -n "$$NGROK_TOKEN" ]; then \
		apps/customer/node_modules/@expo/ngrok-bin-linux-x64/ngrok authtoken "$$NGROK_TOKEN" 2>/dev/null || true; \
	fi; \
	cd apps/instructor && npx expo start --tunnel --port 8082

##@ 검사·테스트 (로컬 DB, 원격 연결 없음)
.PHONY: check
check: apitest webcheck ccheck icheck ## Run all checks (before PR)
	@echo "✅ All checks passed"

.PHONY: apitest
apitest: ## Backend tests on local DB (fresh DB + alembic check + pytest). Args: ARGS="-k calendar"
	@cd backend && bash scripts/test_local.sh -q $(ARGS)

.PHONY: apiverify
apiverify: ## One-click local verify: local DB -> server -> tokens -> main flow (run_flow.sh)
	@cd backend && bash scripts/verify.sh

.PHONY: webcheck
webcheck: ## Web lint + type check
	@cd frontend && npm run lint && npx tsc --noEmit

.PHONY: ccheck
ccheck: ## Customer app type check
	@cd apps/customer && npx tsc --noEmit

.PHONY: icheck
icheck: ## Instructor app type check
	@cd apps/instructor && npx tsc --noEmit

##@ 백엔드 API 점검 (실행 중인 서버 대상)
.PHONY: apitoken
apitoken: ## Issue a real Supabase access token interactively
	@cd backend && bash scripts/get_token.sh

.PHONY: apiflow
apiflow: ## Run main flow on a running server (needs BASE_URL, HOST_TOKEN, GUEST_TOKEN, HOST_ID)
	@cd backend && bash scripts/run_flow.sh

.PHONY: apismoke
apismoke: ## Booking smoke test with real Supabase accounts (needs API_URL, SUPABASE_URL, SUPABASE_ANON_KEY)
	@bash backend/scripts/smoke_booking.sh

##@ 데이터베이스
.PHONY: dbup
dbup: ## Start local Postgres container (127.0.0.1:55433)
	@bash backend/scripts/local_db.sh up

.PHONY: dbdown
dbdown: ## Stop local Postgres container
	@bash backend/scripts/local_db.sh down

.PHONY: dbcheck
dbcheck: ## Check connection to the DB in backend/.env
	@cd backend && poetry run python -m scripts.check_db_connection

.PHONY: dbschema
dbschema: ## Compare model tables/columns with the DB in backend/.env
	@cd backend && poetry run python -m scripts.check_schema

.PHONY: dbreset
dbreset: ## Reset LOCAL db only (drop public schema + alembic upgrade head, asks DB name)
	@cd backend && poetry run python -m scripts.reset_db

##@ 마이그레이션 (backend/.env 의 DB 대상)
.PHONY: mignew
mignew: ## Create new migration (usage: make mignew M="message"). Review every op before commit
	@$(call require_var,M)
	@cd backend && poetry run alembic revision --autogenerate -m "$(M)"

.PHONY: migup
migup: ## Upgrade to head
	@cd backend && poetry run alembic upgrade head

.PHONY: migcur
migcur: ## Show current migration
	@cd backend && poetry run alembic current

.PHONY: migheads
migheads: ## Show heads
	@cd backend && poetry run alembic heads

.PHONY: migcheck
migcheck: ## Check models vs DB (alembic check, read-only)
	@cd backend && poetry run alembic check

##@ Docker (backend/Dockerfile)
.PHONY: dockbuild
dockbuild: ## Build backend image
	@cd backend && docker build -t $(IMAGE) .

.PHONY: dockrun
dockrun: ## Run backend image on :$(PORT) using backend/.env
	@cd backend && docker run --rm -p $(PORT):8080 --env-file $(ENV_FILE) $(IMAGE)

.PHONY: dockdev
dockdev: ## Run backend image with ./backend mounted and auto reload (dev)
	@cd backend && docker run --rm -p $(PORT):8080 --env-file $(ENV_FILE) -v "$$(pwd)":/app $(IMAGE) \
		sh -c "poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"

.PHONY: dockps
dockps: ## List containers filtered by name (usage: make dockps NAME=crm-backend)
	docker ps -a --filter name=$(NAME)

.PHONY: dockstop
dockstop: ## Stop container by ID or name (usage: make dockstop ID=<container_id_or_name>)
	@$(call require_var,ID)
	docker stop "$(ID)"

##@ Git · 배포
.PHONY: gitbranch
gitbranch: ## Sync staging, delete a branch (local+remote), create a new one (interactive)
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

.PHONY: gitci
gitci: ## Trigger CI with empty commit (then push)
	git commit --allow-empty -m "chore: trigger ci"
	git push

.PHONY: gitpr
gitpr: ## Create staging->main release PR (AWS offline workaround)
	gh pr create --base main --head staging \
		--title "🚀 Release: Staging to Main" \
		--body "Manual release PR (AWS offline)" \
		|| echo "PR already exists"

.PHONY: gitrelease
gitrelease: ## Tag latest main as a version (vX.Y.Z) and push the tag (rollback point), then return
	@bash -eu -o pipefail -c '\
		if [ -n "$$(git status --porcelain)" ]; then echo "❌ Working tree is not clean. Commit or stash first."; exit 1; fi; \
		orig="$$(git symbolic-ref --short -q HEAD || git rev-parse HEAD)"; \
		trap "git switch \"$$orig\" >/dev/null 2>&1 || git checkout \"$$orig\" >/dev/null 2>&1; echo \"==> Back on $$orig\"" EXIT; \
		git fetch origin main --tags; \
		git switch main; \
		git pull --ff-only origin main; \
		echo "📜 Recent tags:"; git tag -l "v*" --sort=-v:refname | head -n 5; \
		read -r -p "New tag (e.g. v0.2.0): " TAG; \
		if ! [[ "$$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$$ ]]; then echo "❌ Tag must look like v1.2.3"; exit 1; fi; \
		if git rev-parse -q --verify "refs/tags/$$TAG" >/dev/null; then echo "❌ Tag $$TAG already exists"; exit 1; fi; \
		git tag -a "$$TAG" -m "release $$TAG"; \
		git push origin "$$TAG"; \
		echo "✅ Tagged main as $$TAG (rollback point: make gitrollback)"; \
	'

.PHONY: gitrollbackdry
gitrollbackdry: ## [Safe] Show what a rollback to a tag would change (no changes)
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
		echo "👉 To execute for real: make gitrollback"; \
	'

.PHONY: gitrollback
gitrollback: ## [Danger] Rollback main to a tag (new commit on main, triggers deploy)
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

##@ 검색
.PHONY: grep
grep: ## Search string, excluding .venv/.git/node_modules and env/secret files (usage: make grep Q="text")
	@$(call require_var,Q)
	@grep -RIn --exclude-dir=.venv --exclude-dir=.git --exclude-dir=node_modules \
		--exclude='.env' --exclude='.env.*' --exclude='*.env' --exclude='*.pem' --exclude='*.key' \
		"$(Q)" .

##@ AWS · Copilot
.PHONY: awsinstall
awsinstall: ## Install AWS CLI / Copilot via script
	@cd backend && ./scripts/install_aws_tools.sh

.PHONY: awscheck
awscheck: ## Check aws/copilot versions (and hint PATH if missing)
	@set -e; \
	if command -v aws >/dev/null 2>&1; then aws --version; else echo "aws: command not found (try: export PATH=\"$$HOME/.local/bin:$$PATH\")"; fi; \
	if command -v copilot >/dev/null 2>&1; then copilot --version; else echo "copilot: command not found (try: export PATH=\"$$HOME/.local/bin:$$PATH\")"; fi

.PHONY: awswho
awswho: ## Check current AWS identity
	aws sts get-caller-identity

.PHONY: awsenvs
awsenvs: ## List copilot environments
	@cd backend && copilot env ls

.PHONY: stgstatus
stgstatus: ## Show staging service status
	@cd backend && copilot svc status --name api --env staging

.PHONY: stglogs
stglogs: ## Follow staging logs
	@cd backend && copilot svc logs --name api --env staging --follow

.PHONY: stgexec
stgexec: ## Exec into staging task
	@cd backend && copilot svc exec --name api --env staging

.PHONY: stgdeploy
stgdeploy: ## Manually deploy to staging
	@cd backend && copilot svc deploy --name api --env staging

.PHONY: stgalarm
stgalarm: ## Print STAGING ALB/TG suffix (for CloudWatch dimensions)
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

.PHONY: prodstatus
prodstatus: ## Show prod service status
	@cd backend && copilot svc status --name api --env prod

.PHONY: prodlogs
prodlogs: ## Follow prod logs
	@cd backend && copilot svc logs --name api --env prod --follow

.PHONY: proddeploy
proddeploy: ## Manually deploy to prod (use with caution)
	@cd backend && copilot svc deploy --name api --env prod

.PHONY: prodalarm
prodalarm: ## Print PROD ALB/TG suffix (for CloudWatch dimensions)
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
