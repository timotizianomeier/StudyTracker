from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Pull the DB path from our application module so there's a single source of truth.
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db as app_db

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

DB_URL = f"sqlite:///{app_db.DB_PATH}"


def run_migrations_offline() -> None:
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(DB_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
