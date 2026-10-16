from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def build_database(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine_options = {"connect_args": connect_args}
    if database_url.endswith(":memory:"):
        engine_options["poolclass"] = StaticPool
    engine = create_engine(database_url, **engine_options)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session
