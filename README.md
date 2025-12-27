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
