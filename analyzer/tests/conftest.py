import logging
from pathlib import Path

import pytest  # noqa F401
from click.testing import CliRunner

from .fixtures import *  # noqa F401
from .log_mem_handler import LogMemHandler
from ..context import AnalyzerContext


@pytest.fixture(scope="session", autouse=True)
def test_logger():
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    yield logger
    logger.handlers.clear()


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
    ctx = AnalyzerContext()
    ctx.session = session
    ctx.logger = test_logger
    yield ctx
