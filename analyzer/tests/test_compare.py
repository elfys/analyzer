import re
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from analyzer import analyzer
from analyzer.compare import compare_wafers

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


@pytest.mark.parametrize("wafer, chips", [(wafer_name, chip_names)], indirect=True)
@pytest.mark.isolate_files(dir="wafers-comparisons")
class TestCompareWafers:
    # set db to autouse it in all tests
    @pytest.fixture(scope="class", autouse=True)
    def db(self, wafer, chips, db):
        ...
    
    @pytest.fixture
    def execution(self, runner: CliRunner, ctx_obj):
        result = runner.invoke(compare_wafers, ["--wafers", wafer_name], obj=ctx_obj)
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

    def test_invoke_from_root_group(self, runner, wafer):
        result = runner.invoke(analyzer, ["compare", "wafers", "-w", wafer.name])
        assert result.exit_code == 0
    
    def test_exit_code(self, execution):
        assert execution.exit_code == 0
    
    def test_empty_result(self, runner, ctx_obj, log_handler):
        result = runner.invoke(compare_wafers, ["-w", "NONE"], obj=ctx_obj)
        assert result.exit_code == 0
        assert len(log_handler.records) == 2
        assert log_handler.records[0].message.startswith("Wafers {'NONE'} not found. Continuing")
        assert log_handler.records[1].message == "No data to compare"

    def test_create_excel_file(self, created_file):
        assert created_file.exists()

    def test_excel_file_content(self, created_file):
        stub = pd.read_excel("./stub.xlsx")
        actual = pd.read_excel(created_file)
        assert stub.equals(actual)
