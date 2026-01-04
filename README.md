# crm_backend
# uvicorn app.main:app --roload

# 개발용
# docker build -f Dockerfile.dev -t crm-dev .
# docker run --rm -p 8000:8000 --env-file .env crm-dev

# 배포용
# docker build -t crm-prod .
# docker run --rm -p 8000:8000 --env-file .env crm-prod

# 서버 구동 확인
# poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 테스트 토큰 실행 코드
# source scripts/dev_tokens.sh
# source scripts/load_tokens.sh
#  ㄴ 토큰 만료시 실행
# ./scripts/run_flow.sh

# autogenerate로 new migration만들기
# poetry run alembic revision --autogenerate -m "..."
# poetry run alembic upgrade head
# 버전 일치하는지 확인하기
# poetry run alembic current
# poetry run alembic heads

# 수정없이 CI돌리는법
# git commit --allow-empty -m "chore: trigger ci"
# git push


# 문자열 찾기
# grep -R "찾을문자열" . 
