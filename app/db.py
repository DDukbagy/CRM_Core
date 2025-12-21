from typing import Generator
from sqlmodel import create_engine, Session
from sqlalchemy.engine import Engine
from app.core.config import settings


def create_db_engine() -> Engine:
    return create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

engine: Engine = create_db_engine()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
