import pytest
from click.testing import (
    CliRunner,
    Result,
)

from measure import measure_group
from orm import (
    Chip,
    IvConditions,
    Wafer,
)


class TestMeasureIVAutomatic:
    chip_name = "X0506"
    wafer_name = "AB4"
    
    @pytest.fixture(autouse=True, scope="class")
    def measure(self, runner: CliRunner, db_url) -> Result:
        result = runner.invoke(
            measure_group,
            [
                "--config",
                "measure/iv-innopoli.yaml",
                "--simulate",
                "--db-url",
                db_url,
                "iv",
                "--auto",
                "--chip-name",
                self.chip_name,
                "--chip-state",
                "5",
                "--wafer",
                self.wafer_name,
            ],
        )
        yield result
    
    @pytest.fixture
    def wafer(self, session):
        return session.query(Wafer).filter(Wafer.name == self.wafer_name).one_or_none()
    
    @pytest.fixture
    def chip(self, session, wafer):
        return session.query(Chip).filter(Chip.wafer == wafer).one_or_none()
    
    @pytest.fixture
    def iv_conditions(self, session, chip):
        return session.query(IvConditions).filter(IvConditions.chip == chip).all()
    
    def test_exit_code(self, measure):
        assert measure.exit_code == 0
    
    def test_create_new_wafer(self, wafer):
        assert wafer
    
    def test_create_new_chip(self, chip):
        assert chip
    
    def test_save_measurements(self, iv_conditions):
        assert len(iv_conditions) == 2
        for iv_condition in iv_conditions:
            assert iv_condition.instrument_id == 4
            assert iv_condition.chip_state_id == 5
            assert len(iv_condition.measurements) == 4
