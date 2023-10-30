from datetime import datetime

import pytest
from click.testing import CliRunner
from sqlalchemy import text
from sqlalchemy.orm import Session

from analyzer.summary import summary_group
from orm import (
    Chip,
    Wafer,
)


@pytest.fixture
def execution(request, runner: CliRunner, ctx_obj):
    params = request.node.get_closest_marker("invoke").kwargs.get("params", None)
    assert params is not None
    return runner.invoke(
        summary_group,
        params,
        obj=ctx_obj,
    )


@pytest.fixture(autouse=True, scope="module")
def db(session: Session):
    session.query(Chip).delete()
    session.query(Wafer).delete()
    session.execute(text("ALTER TABLE wafer AUTO_INCREMENT = 1"))  # reset id generator
    session.commit()

    wafers = [
        Wafer(name="PD4", record_created_at=datetime(2022, 5, 26)),
        Wafer(name="PD5", record_created_at=datetime(2022, 12, 6)),
        Wafer(name="PD6", record_created_at=datetime(2023, 2, 11)),
    ]

    session.add_all(wafers)
    session.commit()
    yield


class TestSummaryIV:
    @pytest.mark.invoke(params=["iv", "-w", "PD5"])
    def test_exit_code(self, execution):
        assert execution.exit_code == 0


class TestSummaryCV:
    @pytest.mark.invoke(params=["cv", "-w", "PD5"])
    def test_exit_code(self, execution):
        assert execution.exit_code == 0


class TestSummaryEQE:
    @pytest.mark.invoke(params=["eqe", "-w", "PD5"])
    def test_exit_code(self, execution):
        assert execution.exit_code == 0
