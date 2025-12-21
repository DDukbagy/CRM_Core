FROM python:3.11-slim

# OS 패키지 (git 필요)
RUN apt-get update && apt-get install -y git \
    && rm -rf /var/lib/apt/lists/*

# Poetry 설치
RUN pip install poetry

# 작업 디렉토리
WORKDIR /workspace

# 의존성 파일 복사 (캐시 최적화)
COPY pyproject.toml poetry.lock* ./

# 의존성 설치
RUN poetry install --no-root

# 전체 코드 복사
COPY . .

# FastAPI 실행
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
