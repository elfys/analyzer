import logging
from pathlib import Path

import keyring
import pytest  # noqa F401
import pytest_alembic
from click.testing import CliRunner
from pytest_alembic import Config
from pytest_alembic.tests import test_model_definitions_match_ddl
from pytest_alembic.tests import test_single_head_revision
from pytest_alembic.tests import test_upgrade
from sqlalchemy import text, create_engine, make_url
from sqlalchemy.orm import Session

from analyzer.tests.log_mem_handler import LogMemHandler
from .fixtures import *  # noqa F401


def set_keyring():
    def get_password(service, name):
        assert service == "ELFYS_DB"
        if name == "USER":
            return "root"
        if name == "PASSWORD":
            return "pwd"
        if name == "HOST":
            return "127.0.0.1"
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
    set_keyring()


@pytest.fixture(scope="session")
def db_url():
    return "mysql://root:pwd@127.0.0.1:3306/test"


@pytest.fixture(scope="session", autouse=True)
def test_logger():
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    yield logger
    logger.handlers.clear()


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
    yield create_engine(db_url)


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(alembic_config, alembic_engine):
    # clear database
    with pytest_alembic.runner(config=alembic_config, engine=alembic_engine) as runner:
        test_single_head_revision(runner)
        test_upgrade(runner)
        yield
        test_model_definitions_match_ddl(runner)
        # test_up_down_consistency(runner)


@pytest.fixture(scope="class")
def session(alembic_engine):
    with alembic_engine.connect():
        session = Session(bind=alembic_engine, autoflush=False, autocommit=False, future=True)
        session.begin()
        yield session
        session.rollback()


@pytest.fixture(scope="session")
def runner():
    return CliRunner()


@pytest.fixture(autouse=True, scope="function")
def file_items(request, runner: CliRunner):
    markers = tuple(request.node.iter_markers("isolate_files"))
    if not markers:
        yield None
        return
    data_dir = Path(__file__).parent / "data"
    merged_kwargs = {k: v for marker in markers for k, v in marker.kwargs.items()}
    dir_name = merged_kwargs["dir"]
    file_names = merged_kwargs.get("files")
    if file_names:
        files = [data_dir / dir_name / file_name for file_name in file_names]
    else:
        files = (data_dir / dir_name).iterdir()
    file_items = [(file.name, file.read_bytes()) for file in files]
    with runner.isolated_filesystem():
        for name, content in file_items:
            temp_file = Path(name)
            temp_file.write_bytes(content)
        yield file_items


@pytest.fixture
def log_handler(test_logger):
    handler = LogMemHandler()
    test_logger.addHandler(handler)
    yield handler
    test_logger.removeHandler(handler)


@pytest.fixture
def ctx_obj(session, log_handler, test_logger):
    return {"session": session, "logger": test_logger}
