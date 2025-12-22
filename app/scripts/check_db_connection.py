import asyncio
from sqlalchemy import text

from app.db import engine


async def test_connection():
    async with engine.connect() as conn:
        result = await conn.execute(text("select 1"))
        print(result.scalar())


if __name__ == "__main__":
    asyncio.run(test_connection())
