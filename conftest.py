import logging
import os
from logging import (
    Handler,
    LogRecord,
)
from typing import Generator
from unittest.mock import patch

import pytest
import pytest_alembic
from alembic.config import Config as AlembicConfig
from click.testing import CliRunner
from pytest_alembic import Config as PytestAlembicConfig
from pytest_alembic.tests import (
    test_model_definitions_match_ddl,
    test_single_head_revision,
    test_upgrade,
)
from sqlalchemy import (
    create_engine,
    make_url,
    text,
)
from sqlalchemy.orm import Session
from typeguard import (
    TypeguardFinder,
    install_import_hook,
)


def pytest_addoption(parser):
    parser.addoption("--db-url", action="store", default="mysql://root:pwd@127.0.0.1:3306/test")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "invoke: mark test to invoke commands",
    )
    config.addinivalue_line(
        "markers",
        "isolate_files: mark test to isolate files in a temporary directory",
    )
    url = make_url(config.getoption("db_url"))
    
    # patch("utils.get_db_url", return_value=make_url(url)).start()
    # patch("analyzer.get_db_url", return_value=make_url(url)).start()
    def get_password(service, name):
        assert service == "ELFYS_DB"
        if name == "USER":
            return url.username
        if name == "PASSWORD":
            return url.password
        if name == "HOST":
            return url.host
        raise ValueError(f"Unexpected name: {name}")
    
    patch("keyring.get_password", get_password).start()


@pytest.fixture(scope="session")
def db_url(request):
    url = request.config.getoption("db_url")
    os.environ["DB_URL"] = url
    return url


@pytest.fixture(scope="session")
def alembic_config(db_url):
    config = PytestAlembicConfig.from_raw_config({"sqlalchemy.url": db_url})
    config.alembic_config = AlembicConfig("alembic.ini")
    config.alembic_config.set_main_option("disable_logging", "true")
    yield config


@pytest.fixture(scope="session")
def alembic_engine(db_url, alembic_config):
    url = make_url(db_url)
    database = url.database
    uri = url._replace(database=None)
    engine = create_engine(uri, pool_size=1, max_overflow=0, pool_timeout=60, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {database}"))
        conn.execute(text(f"CREATE DATABASE {database}"))
    engine.dispose(close=True)
    
    engine = create_engine(db_url, pool_size=2, max_overflow=0, pool_timeout=5, pool_pre_ping=True)
    yield engine
    engine.dispose(close=True)


@pytest.fixture(scope="session")
def apply_migrations(alembic_config, alembic_engine):
    with pytest_alembic.runner(config=alembic_config, engine=alembic_engine) as runner:
        test_single_head_revision(runner)
        test_upgrade(runner)
        yield
        test_model_definitions_match_ddl(runner)
        # test_up_down_consistency(runner)


@pytest.fixture(scope="module")
def session(apply_migrations, alembic_engine):
    with alembic_engine.connect():
        session = Session(bind=alembic_engine, autoflush=False, autocommit=False, future=True)
        session.begin()
        yield session
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def runner():
    return CliRunner()


class CustomFinder(TypeguardFinder):
    def should_instrument(self, module_name: str):
        parts = module_name.split('.')
        should = parts[0] in ('analyzer', 'orm', 'measure', 'utils') and 'tests' not in parts
        return should


install_import_hook(None, cls=CustomFinder)


class LogMemHandler(Handler):
    def __init__(self):
        self.records = []
        super().__init__()
    
    def handle(self, record: LogRecord) -> bool:
        self.records.append(record)
        return True
    
    def handleError(self, record: LogRecord) -> None:
        self.handle(record)


@pytest.fixture(scope="module")
def test_logger(logger_name) -> Generator[logging.Logger, None, None]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    yield logger
    logger.handlers.clear()


@pytest.fixture
def log_handler(test_logger) -> Generator[LogMemHandler, None, None]:
    handler = LogMemHandler()
    test_logger.addHandler(handler)
    yield handler
    test_logger.removeHandler(handler)
