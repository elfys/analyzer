import logging
import sys
from logging.config import fileConfig

from orm import Base

import click
from alembic import context
from sqlalchemy import create_engine, engine_from_config
from sqlalchemy.engine import URL

from analyzer.db import dump_db

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    if "connection" in context.config.attributes:
        # pytest-alembic
        engine = context.config.attributes["connection"]
    elif "production" in context.get_x_argument():
        logger = logging.getLogger("alembic.runtime.migration")
        logger.warning("Running migrations in production mode.")
        click.confirm("Do you want to continue?", abort=True)
        db_url_or_error_code = dump_db(
            args=[],
            windows_expand_args=False,
            standalone_mode=False,
            obj={"logger": logger},
        )
        if not isinstance(db_url_or_error_code, URL):
            sys.exit(db_url_or_error_code)
        engine = create_engine(db_url_or_error_code)
    else:
        engine = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
        )

    with engine.begin() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():  # mysql doesn't support DDL transactions anyway =(
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
