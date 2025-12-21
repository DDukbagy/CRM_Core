FROM python:3.11-slim

# OS 패키지 설치 (git + git-lfs)
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    && rm -rf /var/lib/apt/lists/*

# git-lfs 초기화 (전역 1회)
RUN git lfs install

# Poetry 설치
RUN pip install poetry

WORKDIR /workspace

# 의존성 파일 복사
COPY pyproject.toml poetry.lock* ./

# Python 의존성 설치
RUN poetry install --no-root

# 전체 코드 복사
COPY . .

# FastAPI 실행
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
