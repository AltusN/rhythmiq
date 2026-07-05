from collections.abc import Generator
from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

POSTGRESQL_DATABASE_URL = os.environ.get("POSTGRESQL_DATABASE_URL", None)

if POSTGRESQL_DATABASE_URL is None:
    raise ValueError("POSTGRESQL_DATABASE_URL environment variable is not set")

engine = create_engine(POSTGRESQL_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from app import models

    models.Base.metadata.create_all(bind=engine)


# Fastapi dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app):
    init_db()
    # Return control to FastAPI to start the server
    yield
    # Add tear down code here if needed in the future
    engine.dispose()
