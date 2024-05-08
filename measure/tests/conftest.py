import pytest

from measure import MeasureContext


@pytest.fixture
def ctx_obj(session, log_handler, test_logger):
    ctx = MeasureContext()
    ctx.session = session
    ctx.logger = test_logger
    yield ctx
