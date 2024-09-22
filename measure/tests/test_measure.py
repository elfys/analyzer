import traceback
from itertools import chain
from pathlib import Path

import pytest
from click.testing import (
    CliRunner,
    Result,
)

from measure import measure_group
from orm import (
    AbstractChip,
    IvConditions,
    Wafer,
)

config_paths = [f.as_posix() for f in Path("measure").glob("iv-*.yaml")]


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
        
        if result.exception is not None and result.exc_info is not None:
            traceback.print_exception(*result.exc_info)
        yield result
    
    @pytest.fixture
    def wafer(self, session):
        return session.query(Wafer).filter(Wafer.name == self.wafer_name).one_or_none()
    
    @pytest.fixture
    def chip(self, session, wafer):
        return session.query(AbstractChip).filter(AbstractChip.wafer == wafer).one_or_none()
    
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
    
    @pytest.mark.parametrize("config_path, input", [
        ('measure/iv-innopoli.yaml', None),
        ('measure/iv-one-sweep.yaml', None),
        ('measure/iv-micronova.yaml', 'y\n'),
        ('measure/iv-tst.yaml', None),
        ('measure/iv-guard-ring.yaml', None)
    ])
    def test_config_return_ok(self, runner: CliRunner, db_url, config_path: str, input: str):
        result = runner.invoke(
            measure_group,
            [
                "--config",
                config_path,
                "--simulate",
                "--db-url",
                db_url,
                "iv",
                "--chip-name",
                self.chip_name,
                "--chip-state",
                "5",
                "--wafer",
                self.wafer_name,
            ],
            input=input
        )
        
        if result.exception is not None and result.exc_info is not None:
            traceback.print_exception(*result.exc_info)
        assert result.exit_code == 0
    
    @pytest.mark.parametrize("config_path, input, chip_names", [
        ('measure/iv-to-can.yaml', None, ["X0506", "X0507", "X0508"]),
        ('measure/iv-matrix.yaml', None, ["R0509"]),
    ])
    def test_multichip_config_return_ok(self, runner: CliRunner, db_url, config_path: str, input: str, chip_names: list[str]):
        result = runner.invoke(
            measure_group,
            [
                "--config",
                config_path,
                "--simulate",
                "--db-url",
                db_url,
                "iv",
                *chain.from_iterable([["--chip-name", chip_name] for chip_name in chip_names]),
                "--chip-state",
                "5",
                "--wafer",
                self.wafer_name,
            ],
            input=input
        )
        
        if result.exception is not None and result.exc_info is not None:
            traceback.print_exception(*result.exc_info)
        assert result.exit_code == 0
