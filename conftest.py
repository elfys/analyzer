import logging
from typing import (
    Any,
    Generator,
)

import keyring
import pytest  # noqa F401
import pytest  # noqa F401
import pytest_alembic
from click.testing import CliRunner
from pytest_alembic import Config
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

from analyzer.tests.log_mem_handler import LogMemHandler


def pytest_addoption(parser):
    parser.addoption("--db-url", action="store", default="mysql://root:pwd@127.0.0.1:3306/test")


def set_keyring(user, password, host):
    def get_password(service, name):
        assert service == "ELFYS_DB"
        if name == "USER":
            return user
        if name == "PASSWORD":
            return password
        if name == "HOST":
            return host
        raise ValueError(f"Unexpected name: {name}")
    
    keyring.get_password = get_password


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
    set_keyring(url.username, url.password, url.host)


@pytest.fixture(scope="session")
def db_url(request):
    return request.config.getoption("db_url")


@pytest.fixture(scope="session", autouse=True)
def setup_db(db_url):
    url = make_url(db_url)
    database = url.database
    uri = url._replace(database=None)
    engine = create_engine(uri)
    with engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {database}"))
        conn.execute(text(f"CREATE DATABASE {database}"))
    engine.dispose(close=True)
    yield


@pytest.fixture(scope="session")
def alembic_config(db_url):
    """Override this fixture to configure the exact alembic context setup required."""
    config = Config.from_raw_config({"sqlalchemy.url": db_url})
    yield config


@pytest.fixture(scope="session")
def alembic_engine(setup_db, db_url, alembic_config):
    """Override this fixture to provide pytest-alembic powered tests with a database handle."""
    engine = create_engine(db_url, pool_size=2, max_overflow=0, pool_timeout=5, pool_pre_ping=True)
    yield engine
    engine.dispose(close=True)


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(alembic_config, alembic_engine):
    # clear database
    with pytest_alembic.runner(config=alembic_config, engine=alembic_engine) as runner:
        test_single_head_revision(runner)
        test_upgrade(runner)
        yield
        test_model_definitions_match_ddl(runner)
        # test_up_down_consistency(runner)


@pytest.fixture(scope="module")
def session(alembic_engine):
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


@pytest.fixture(scope="session", autouse=True)
def test_logger():
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    yield logger
    logger.handlers.clear()


@pytest.fixture
def log_handler(test_logger) -> Generator[LogMemHandler, Any, Any]:
    handler = LogMemHandler()
    test_logger.addHandler(handler)
    yield handler
    test_logger.removeHandler(handler)
