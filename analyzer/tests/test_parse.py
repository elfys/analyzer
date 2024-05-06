import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import (
    desc,
    text,
)
from sqlalchemy.orm import Session

from analyzer import analyzer
from analyzer.parse import (
    parse_cv,
    parse_eqe,
    parse_group,
    parse_iv,
    parse_ts,
)
from orm import (
    CVMeasurement,
    Chip,
    EqeConditions,
    TestStructureChip,
    TsConditions,
    TsMeasurement,
    Wafer,
)


def should_parse_files(file_items: list[tuple[str, str]]):
    for file_path, content in file_items:
        assert Path(file_path).exists() is False
        assert Path(f"{file_path}.parsed").exists() is True
        assert Path(f"{file_path}.parsed").read_bytes() == content


def should_not_parse_file(file_items: list[tuple[str, str]]):
    for file_path, content in file_items:
        assert Path(file_path).exists() is True
        assert Path(file_path).read_bytes() == content
        assert Path(f"{file_path}.parsed").exists() is False


@pytest.fixture(autouse=True, scope="class")
def reset_db(session: Session):
    session.query(Chip).delete()
    session.query(Wafer).delete()
    session.execute(text("ALTER TABLE wafer AUTO_INCREMENT = 1"))  # reset id generator
    session.commit()
    yield


class TestParseGroup:
    def setup_class(self):
        pass
    
    def teardown_class(self):
        pass
    
    def test_help_ok(self, runner):
        result = runner.invoke(parse_group, ["--help"])
        assert result.exit_code == 0
    
    def test_help_text(self, runner):
        result = runner.invoke(parse_group, ["--help"])
        assert re.search(r"cv\s+parse cv", result.output, re.I) is not None
        assert re.search(r"iv\s+parse iv", result.output, re.I) is not None
        assert re.search(r"eqe\s+parse eqe", result.output, re.I) is not None
        assert re.search(r"ts\s+Parse Test Structure", result.output, re.I) is not None
        assert len(result.output.split("\n")) == 13


@pytest.mark.isolate_files(dir="cv")
class TestParseCV:
    @pytest.fixture
    def execution(self, request, runner: CliRunner, ctx_obj, file_items):
        params = request.node.get_closest_marker("invoke").kwargs.get("params", None)
        assert params is not None
        return runner.invoke(
            parse_cv,
            [file_name for file_name, _ in file_items],
            obj=ctx_obj,
            input="\n".join(params),
        )
    
    def test_help_ok(self, runner):
        result = runner.invoke(parse_cv, ["--help"])
        assert result.exit_code == 0
    
    def test_invoke_from_root_group(self, runner, session):
        result = runner.invoke(analyzer, ["parse", "cv", "nothing.dat"])
        assert result.exit_code == 0
    
    @pytest.mark.isolate_files(files=["CV BC6 Y0115.dat"])
    @pytest.mark.invoke(params=["", "y", "", "1"])
    def test_guess_chip_and_wafer_from_filename(self, execution, log_handler, file_items):
        assert execution.exit_code == 0
        logs = log_handler.records
        assert len(logs) == 3
        assert logs[0].message.startswith("Found 1 files matching pattern")
        assert logs[1].message == "Guessed from filename: wafer=BC6, chip=Y0115"
        assert logs[2].message.startswith("File was saved to database and renamed")
        
        should_parse_files(file_items)
    
    @pytest.mark.isolate_files(files=["2_columns.dat"])
    @pytest.mark.invoke(params=["AB1", "y", "U0101", "1"])
    def test_parse_dat_file_with_2_columns(self, execution, log_handler, file_items):
        assert execution.exit_code == 0
        logs = log_handler.records
        assert len(logs) == 3
        assert logs[0].message.startswith("Found 1 files matching pattern")
        assert logs[1].message == "Could not guess chip and wafer from filename"
        assert logs[2].message.startswith("File was saved to database and renamed")
        
        should_parse_files(file_items)
    
    @pytest.mark.isolate_files(files=["6_columns_with_asterisks.dat"])
    def test_parse_dat_file_with_6_columns_with_asterisks(
        self, runner: CliRunner, session, log_handler, file_items, ctx_obj
    ):
        num_of_measurements = session.query(CVMeasurement).count()
        result = runner.invoke(
            parse_cv,
            [file_name for file_name, _ in file_items],
            obj=ctx_obj,
            input="\n".join(["AB1", "y", "U0101", "1"]),
        )
        
        assert result.exit_code == 0
        assert len(log_handler.records) == 3
        should_parse_files(file_items)
        assert session.query(CVMeasurement).count() == num_of_measurements + 6
    
    @pytest.mark.isolate_files(files=["2_tables.dat"])
    def test_parse_dat_file_with_2_tables(
        self, runner: CliRunner, session, log_handler, file_items, ctx_obj
    ):
        num_of_measurements = session.query(CVMeasurement).count()
        result = runner.invoke(
            parse_cv,
            [file_name for file_name, _ in file_items],
            obj=ctx_obj,
            input="\n".join(["AB1", "y", "U0101", "1"]),
        )
        
        assert result.exit_code == 0
        assert len(log_handler.records) == 3
        should_parse_files(file_items)
        assert session.query(CVMeasurement).count() == num_of_measurements + 12
    
    @pytest.mark.isolate_files(files=["unknown_table_format.dat"])
    @pytest.mark.invoke(params=["AB1", "y", "U0101", "1"])
    def test_parse_unknown_table_format_prints_warning(self, execution, log_handler, file_items):
        assert execution.exit_code == 0
        
        logs = log_handler.records
        assert len(logs) == 4
        assert logs[2].message == "No data was found in given file. Does it use the unusual format?"
        assert logs[2].levelname == "WARNING"
        
        assert logs[3].message == "Skipping file..."
        assert logs[3].levelname == "INFO"
        
        should_not_parse_file(file_items)


class TestParseIV:
    def test_help_ok(self, runner):
        result = runner.invoke(parse_iv, ["--help"])
        assert result.exit_code == 0
    
    def test_invoke_from_root_group(self, runner, session):
        result = runner.invoke(analyzer, ["parse", "iv", "nothing.dat"])
        assert result.exit_code == 0


@pytest.mark.isolate_files(dir="eqe")
class TestParseEQE:
    def run_command(self, runner, file_names, obj, input: dict):
        default_params = (
            ("wafer", ""),
            ("confirm_wafer_creation", None),
            ("chip", ""),
            ("comment", ""),
            ("chip_state", ""),
            ("chip_state_for_all", "n"),
            ("carrier", ""),
            ("carrier_for_all", "n"),
        )
        input = "\n".join(
            value
            for value in (input.get(key, default) for key, default in default_params)
            if value is not None
        )
        return runner.invoke(parse_eqe, file_names, obj=obj, input=input)
    
    def test_help_ok(self, runner):
        result = runner.invoke(parse_eqe, ["--help"])
        assert result.exit_code == 0
    
    def test_invoke_from_root_group(self, runner, session):
        result = runner.invoke(analyzer, ["parse", "eqe", "nothing.dat"])
        assert result.exit_code == 0
    
    @pytest.mark.isolate_files(files=["EQE REF FDG50.dat"])
    def test_parse_ref_with_defaults(self, runner, session, log_handler, file_items, ctx_obj):
        result = self.run_command(
            runner,
            [file_name for file_name, _ in file_items],
            ctx_obj,
            {
                "chip_state": None,
                "chip_state_for_all": None,
                "carrier": None,
                "carrier_for_all": None,
            },
        )
        assert result.exit_code == 0
        logs = log_handler.records
        assert len(logs) == 6
        assert logs[0].message.startswith("Found 1 files matching pattern")
        assert logs[1].message == "Guessed from filename: wafer=REF, chip=FDG50"
        assert logs[2].message.startswith("Default values were applied to chip FDG50")
        assert logs[3].message.startswith("No sessions were found for measurement date")
        assert logs[4].message.startswith("New eqe session was created")
        assert logs[5].message.startswith("File was saved to database and renamed")
        
        new_conditions = session.query(EqeConditions).order_by(desc(EqeConditions.id)).first()
        assert new_conditions.chip_state_id == 8
        assert new_conditions.carrier_id == 11
        should_parse_files(file_items)
    
    @pytest.mark.isolate_files(files=["labview_filename.dat"])
    def test_parse_dat_file_with_labview_filename(
        self, runner: CliRunner, session, log_handler, file_items, ctx_obj
    ):
        result = self.run_command(
            runner,
            ["*.dat"],
            ctx_obj,
            {
                "wafer": "AB1",
                "confirm_wafer_creation": "y",
                "chip": "U0101",
                "comment": "My comments",
                "chip_state": "1",
                "carrier": "4",
            },
        )
        assert result.exit_code == 0
        should_parse_files(file_items)
        
        new_conditions = session.query(EqeConditions).order_by(desc(EqeConditions.id)).first()
        assert (
            new_conditions.comment
            == """Parsing comment: My comments
Parsed file: labview_filename.dat
Delay after wl change (ms): 	200
Delay between current readings (ms): 	200
Used reference measurement file: 	EQE REF NEWPORT2 begin2 -000V000 calNP2b1.dat
Calibration used: 	Yes
Name of operating VI-code: 	Spectral response measurement - 2023-01-18.vi
Operating VI-code last modified: 	2023-01-18 10:19:00
Name of saving VI-code: 	Save data to file - 2023-01-18.vi
Saving VI-code last modified: 	2023-01-18 10:19:01
Model and Firmware U0X: 237A06 237A06
Error Status Word U1X: ERS00000000000000000000000000 ERS00000000000000000000000000
Stored ASCII String U2X: DSP DSP
Machine Status Word U3X: MSTG01,0,0K0M008,0N1R1T0,0,0,0V1Y0 MSTG15,0,0K0M008,0N1R1T0,0,0,0V1Y0
Measurement Parameters U4X: IMPL,00F0,0O0P5S3W1Z0 IMPL,00F0,0O0P5S3W1Z0
Compliance Value U5X: ICP010.000E-06 ICP010.000E-06
Suppression Value U6X: ISP+00.0000E+00 ISP+00.0000E+00
Calibration Status Word U7X: CSP00,1,1 CSP00,1,1
Defined Sweep Size U8X: DSS0000 DSS0000
Warning Status Word U9X: WRS0000000000 WRS0000000000
First Sweep Point in Compliance U10X:  
Sweep Measure Size U11X: SMS0000 SMS0000
"""
        )  # noqa: W291
        assert len(new_conditions.measurements) == 7


@pytest.mark.isolate_files(dir="ts")
class TestParseTs:
    wafer_name = "AB1"
    
    @pytest.fixture(autouse=True, scope="class")
    def populate_db_with_wafer(self, session):
        wafer = Wafer(name=self.wafer_name)
        session.add(wafer)
        session.commit()
    
    def test_help_ok(self, runner):
        result = runner.invoke(parse_ts, ["--help"])
        assert result.exit_code == 0
    
    @pytest.mark.parametrize(
        "file,ts_type,number,step",
        [
            ("AL11.dat", "AL", 1, 1),
            ("AL31.dat", "AL", 3, 1),
            ("TLM14.dat", "TLM", 1, 4),
        ],
    )
    def test_guess_structure_number_and_step_from_filename(
        self,
        runner: CliRunner,
        session,
        log_handler,
        ctx_obj,
        file,
        ts_type,
        step,
        number,
        file_items,
    ):
        num_of_measurements = session.query(TsMeasurement).count()
        chip_name = "X0507"
        result = runner.invoke(
            parse_ts, file, obj=ctx_obj, input="\n".join([self.wafer_name, chip_name])
        )
        
        assert result.exit_code == 0
        
        conditions = session.query(TsConditions).order_by(TsConditions.id.desc()).first()
        assert log_handler.records[0].message == f"Found 1 files matching pattern {file}"
        assert conditions.chip.name == chip_name
        assert conditions.chip.type == "TS"
        assert isinstance(conditions.chip, TestStructureChip)
        assert conditions.chip.wafer.name == self.wafer_name
        assert conditions.ts_step == step
        assert conditions.ts_number == number
        assert conditions.structure_type == ts_type
        
        assert session.query(TsMeasurement).count() == num_of_measurements + 21
        
        should_parse_files([file_item for file_item in file_items if file_item[0] == file])
