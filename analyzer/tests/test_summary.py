import pytest
from click.testing import CliRunner

from analyzer.summary import summary_group

wafer_name = "PD5"
chip_names = [
    "G0506",
    "X0507",
    "G0508",
    "X0509",
    "G0510",
    "X0511",
    "G0512",
    "X0513",
]


@pytest.fixture
def execution(request, runner: CliRunner, ctx_obj):
    params = request.node.get_closest_marker("invoke").kwargs.get("params", None)
    assert params is not None
    return runner.invoke(
        summary_group,
        params,
        obj=ctx_obj,
    )


@pytest.mark.parametrize("wafer, chips", [(wafer_name, chip_names)], indirect=True)
class TestSummaryIV:
    # set db to autouse it in all tests
    @pytest.fixture(scope="class", autouse=True)
    def db(self, wafer, chips, db):
        ...
    
    @pytest.mark.invoke(params=["iv", "-w", wafer_name])
    def test_exit_code(self, execution):
        assert execution.exit_code == 0


@pytest.mark.parametrize("wafer, chips", [(wafer_name, chip_names)], indirect=True)
class TestSummaryCV:
    # set db to autouse it in all tests
    @pytest.fixture(scope="class", autouse=True)
    def db(self, wafer, chips, db):
        ...
    
    @pytest.mark.invoke(params=["cv", "-w", "PD5"])
    def test_exit_code(self, execution):
        assert execution.exit_code == 0


@pytest.mark.parametrize("wafer, chips", [(wafer_name, chip_names)], indirect=True)
class TestSummaryEQE:
    # set db to autouse it in all tests
    @pytest.fixture(scope="class", autouse=True)
    def db(self, wafer, chips, db):
        ...
    
    @pytest.mark.invoke(params=["eqe", "-w", "PD5"])
    def test_exit_code(self, execution):
        assert execution.exit_code == 0
