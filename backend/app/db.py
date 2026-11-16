from collections.abc import Iterator

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Meal tables live in their own Postgres schema so they can move into Buoy's database untouched.
MEAL_SCHEMA = "meal"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PLENTY_")

    # Postgres everywhere (docker compose locally, Neon in production).
    database_url: str = "postgresql+psycopg://plenty:plenty@localhost:5433/plenty"
    cors_origins: list[str] = ["http://localhost:5173"]
    # Anyone may sign up only while no account exists, unless this is turned on.
    allow_signup: bool = False
    # If set, the first account must use this email, so nobody can claim a fresh deploy.
    owner_email: str | None = None
    # Send the session cookie over HTTPS only. Must be true in production.
    cookie_secure: bool = False
    session_days: int = 30
    # Directory with the built web app to serve (set in the Docker image).
    static_dir: str | None = None

    @field_validator("database_url")
    @classmethod
    def _use_psycopg(cls, url: str) -> str:
        # Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url


config = Config()

engine = create_engine(
    config.database_url,
    pool_pre_ping=True,  # serverless Postgres (Neon) drops idle connections
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

# Stable constraint names, so Alembic migrations stay reproducible.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
