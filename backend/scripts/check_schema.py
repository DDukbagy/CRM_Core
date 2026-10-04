"""모델(app/db/models.py 에 등록된 테이블)과 실제 DB의 테이블·컬럼이 맞는지 확인한다.

사용: make dbschema  (= cd backend && poetry run python -m scripts.check_schema)
- 모델에는 있는데 DB에 없는 테이블·컬럼 → ❌ (마이그레이션 누락 의심)
- DB에만 있는 컬럼 → ⚠️ (참고용. 모델에서 뺐거나 다른 경로로 추가된 것)
- passes, chat 은 app/db/models.py 에 등록하지 않으므로 여기서도 따로 확인한다.
"""
import asyncio
import os
import sys

# backend/ 를 모듈 경로에 추가 (python scripts/check_schema.py 로 실행해도 동작)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlmodel import SQLModel

import app.db.models  # noqa: F401  (등록된 모델 전부)
import app.domains.passes.models  # noqa: F401
import app.domains.chat.models  # noqa: F401
from app.db.session import engine


async def check_schema() -> int:
    async with engine.connect() as conn:
        print(f"\n[DB 연결 성공: {engine.url.database}]\n")
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    """
                )
            )
        ).all()

    db_cols: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        db_cols.setdefault(table_name, set()).add(column_name)

    problems = 0
    for name, table in sorted(SQLModel.metadata.tables.items()):
        model_cols = {c.name for c in table.columns}
        if name not in db_cols:
            print(f"❌ {name}: 테이블 없음")
            problems += 1
            continue
        missing = sorted(model_cols - db_cols[name])
        extra = sorted(db_cols[name] - model_cols)
        if missing:
            print(f"❌ {name}: 컬럼 없음 {missing}")
            problems += 1
        else:
            print(f"✅ {name} ({len(model_cols)}개 컬럼)")
        if extra:
            print(f"   ⚠️  DB에만 있는 컬럼 {extra}")

    if problems:
        print(f"\n⚠️ 경고: {problems}개 테이블이 모델과 다릅니다. 마이그레이션을 확인하세요.")
    else:
        print(f"\n🎉 모델 테이블 {len(SQLModel.metadata.tables)}개가 모두 DB에 있습니다.")
    return problems


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(check_schema()) else 0)
