from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

import app.models  # noqa: F401  (registers tables)
from alembic import context
from app.db import MEAL_SCHEMA, Base
from app.db import config as app_config

config = context.config
config.set_main_option("sqlalchemy.url", app_config.database_url.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    # Only manage public (auth) and our own schema; ignore anything else in a shared database.
    if type_ == "schema":
        return name in (None, MEAL_SCHEMA)
    return True


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {MEAL_SCHEMA}"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline migrations aren't supported; run against a database.")
run_migrations_online()
