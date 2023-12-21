import re
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from analyzer import analyzer
from analyzer.compare import compare_wafers
from orm import (
    Chip,
    IVMeasurement,
    IvConditions,
    Wafer,
)


@pytest.mark.isolate_files(dir="wafers-comparisons")
class TestCompareWafers:
    wafer_name = "ABCD"
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
    
    @pytest.fixture(scope="class")
    def wafer(self):
        yield Wafer(name=self.wafer_name)
    
    @pytest.fixture(scope="class")
    def chips(self):
        yield [Chip(name=chip_name) for chip_name in self.chip_names]
    
    @pytest.fixture(scope="class")
    def iv_conditions(self, chips):
        yield [
            IvConditions(
                instrument_id=1,
                chip_state_id=i // 4 + 1,
            )
            for i in range(len(self.chip_names))
        ]
    
    @pytest.fixture(autouse=True, scope="class")
    def db(self, wafer, chips, iv_thresholds, session):
        voltage_measure = {
            "-1": [1, 2, 3, 4, 1, 2, 3, 4],
            "-0.01": list(range(8)),
            "0": [0, 0, 0, 0, 0, 0, 0, 0],
            "0.01": list(range(8)),
            "6": list(range(8)),
        }
        wafer.chips = chips
        session.add(wafer)
        session.commit()
        for i, chip in enumerate(chips):
            chip.iv_conditions.append(
                IvConditions(
                    instrument_id=1,
                    chip_state_id=i // 4 + 1,
                )
            )
            for voltage, measures in voltage_measure.items():
                chip.iv_conditions[0].measurements.append(
                    IVMeasurement(voltage_input=voltage, anode_current=measures.pop())
                )
        session.add(wafer)
        session.commit()
    
    @pytest.fixture()
    def execution(self, runner: CliRunner, ctx_obj):
        result = runner.invoke(compare_wafers, ["--wafers", self.wafer_name], obj=ctx_obj)
        return result
    
    @pytest.fixture()
    def created_file(self, log_handler, execution):
        assert len(log_handler.records) == 1
        matcher = re.compile(r"Wafers comparison is saved to (?P<file_name>[\w-]+\.xlsx)", re.I)
        match = matcher.match(log_handler.records[0].message)
        assert match is not None
        file_path = match.group("file_name")
        return Path(file_path)
    
    def test_help_ok(self, runner, session, ctx_obj):
        result = runner.invoke(compare_wafers, ["--help"], obj=ctx_obj)
        assert result.exit_code == 0
    
    def test_invoke_from_root_group(self, runner, session):
        result = runner.invoke(analyzer, ["compare", "wafers", "-w", self.wafer_name])
        assert result.exit_code == 0
    
    def test_exit_code(self, execution):
        assert execution.exit_code == 0
    
    def test_empty_result(self, runner, ctx_obj, log_handler):
        result = runner.invoke(compare_wafers, ["-w", "NONE"], obj=ctx_obj)
        assert result.exit_code == 0
        assert len(log_handler.records) == 2
        assert log_handler.records[0].message == "Wafers not found: NONE"
        assert log_handler.records[1].message == "No data to compare"
    
    def test_create_excel_file(self, created_file):
        assert created_file.exists()
    
    def test_excel_file_content(self, created_file):
        stub = pd.read_excel("./stub.xlsx")
        actual = pd.read_excel(created_file)
        assert stub.equals(actual)
