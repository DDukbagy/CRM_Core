# ---------- Builder: 의존성 설치 ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app

# (HTTPS 다운로드용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Poetry 설치(빌드 단계에서만)
RUN pip install --no-cache-dir poetry

# 의존성 파일만 복사(캐시 최적화)
COPY pyproject.toml poetry.lock* ./

# 운영용 의존성만 설치(dev group 제외)
RUN poetry install --only main --no-root

# 소스 복사
COPY . .


# ---------- Runtime: 실행만 담당(경량) ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# builder에서 만든 .venv + 앱 코드 복사
COPY --from=builder /app /app

# venv 우선
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
