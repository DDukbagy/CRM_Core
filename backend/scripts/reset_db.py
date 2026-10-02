"""로컬 DB 초기화: public 스키마를 비우고 alembic upgrade head 로 처음부터 다시 만든다.

사용: make dbreset  (= cd backend && poetry run python -m scripts.reset_db)
      확인 입력 없이 실행: poetry run python -m scripts.reset_db --yes

안전장치
- DATABASE_URL 의 호스트가 localhost / 127.0.0.1 / ::1 이 아니면 거부한다 (원격 Supabase 보호).
- --yes 가 없으면 DB 이름을 직접 입력해야 진행한다.
- 모든 데이터가 지워진다. 개발 데이터는 scripts/seed_dev_data.sql 로 다시 넣는다.
"""
import asyncio
import os
import subprocess
import sys

# backend/ 를 모듈 경로에 추가 (python scripts/reset_db.py 로 실행해도 동작)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.engine.url import make_url

from app.core.config import settings
from app.db.session import engine

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


async def drop_public_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


def main() -> int:
    url = make_url(settings.ASYNC_DATABASE_URL)
    target = f"{url.host}:{url.port or 5432}/{url.database}"

    if url.host not in LOCAL_HOSTS:
        print(f"❌ 로컬 DB가 아니라서 초기화하지 않습니다: {url.host}")
        print("   reset_db 는 localhost / 127.0.0.1 / ::1 DB에서만 동작합니다.")
        return 1

    print(f"⚠️  로컬 DB {target} 의 모든 테이블과 데이터를 지우고 마이그레이션을 처음부터 다시 적용합니다.")
    if "--yes" not in sys.argv[1:]:
        answer = input(f"계속하려면 DB 이름({url.database})을 입력하세요: ").strip()
        if answer != url.database:
            print("취소했습니다.")
            return 1

    asyncio.run(drop_public_schema())
    print("🗑️  public 스키마를 비웠습니다.")

    result = subprocess.run(["alembic", "upgrade", "head"], cwd=BACKEND_DIR)
    if result.returncode != 0:
        print("❌ alembic upgrade head 실패")
        return result.returncode

    print("✨ 초기화 완료. 개발 데이터가 필요하면 scripts/seed_dev_data.sql 을 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
