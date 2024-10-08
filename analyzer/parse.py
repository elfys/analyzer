import contextlib
import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generator,
    Literal,
    TypedDict,
)

import click
import numpy as np
import pandas as pd
import sentry_sdk
from click.exceptions import Exit
from sqlalchemy.orm import (
    Session,
)

from orm import (
    AbstractChip,
    CVMeasurement,
    Carrier,
    ChipRepository,
    ChipState,
    EqeConditions,
    EqeMeasurement,
    EqeSession,
    IVMeasurement,
    Instrument,
    InstrumentRepository,
    IvConditions,
    TsConditions,
    TsMeasurement,
    Wafer,
    WaferRepository,
)
from utils import (
    eqe_defaults,
    remember_choice,
    select_one,
    validate_files_glob,
)
from .context import (
    AnalyzerContext,
    pass_analyzer_context,
)


class EPGData(TypedDict):
    timestamp: datetime
    data: list[pd.DataFrame]


@click.command(name="iv")
@pass_analyzer_context
@click.argument("file_paths", default="./*.dat", callback=validate_files_glob)
def parse_iv(ctx: AnalyzerContext, file_paths: tuple[Path]):
    """
    Parse IV measurements from FILE_PATHS files. The measurements are saved to the database and
    processed files are renamed to FILENAME.parsed.
    """
    instrument_id = InstrumentRepository(ctx.session).get_id(name="EPG")
    for file_path in file_paths:
        with parsing_file(file_path):
            chip, wafer = guess_chip_and_wafer(file_path.name, "iv")
            chip_state = ask_chip_state(ctx.session)
            columns = ["VCA", "IAN", "ICA"]
            data = parse_epg_dat_file(file_path, columns)
            for raw_measurements in data["data"]:
                measurements = create_iv_measurements(raw_measurements)
                conditions = IvConditions(
                    chip=chip,
                    int_time="MED",
                    chip_state=chip_state,
                    datetime=data["timestamp"],
                    measurements=measurements,
                    instrument_id=instrument_id,
                )
                ctx.session.add(conditions)


@click.command(name="cv")
@pass_analyzer_context
@click.argument("file_paths", default="./*.dat", callback=validate_files_glob)
def parse_cv(ctx: AnalyzerContext, file_paths: tuple[Path]):
    """
    Parse CV measurements from FILE_PATHS files. The measurements are saved to the database and
    processed files are renamed to FILENAME.parsed.
    """
    for file_path in file_paths:
        with parsing_file(file_path):
            chip, _ = guess_chip_and_wafer(file_path.name, "cv")
            chip_state = ask_chip_state(ctx.session)
            columns = ["BIAS", "C"]
            data = parse_epg_dat_file(file_path, columns)
            measurements = create_cv_measurements(
                pd.concat(data["data"], copy=False), data["timestamp"], chip, chip_state
            )
            ctx.session.add_all(measurements)


@click.command(name="ts")
@pass_analyzer_context
@click.argument("file_paths", default="./*.dat", callback=validate_files_glob)
def parse_ts(ctx: AnalyzerContext, file_paths: tuple[Path]):
    """
    Parse TS measurements from FILE_PATHS files. The measurements are saved to the database and
    processed files are renamed to FILENAME.parsed.
    """
    wafer_name = ask_wafer_name()
    wafer = WaferRepository(ctx.session).get_or_create(name=wafer_name)
    if not wafer.id:
        confirm_wafer_creation(wafer)
    
    ctx.logger.info(f"{wafer.name} will be used for every parsed measurement")
    chip_name = ask_chip_name()
    chip = ChipRepository(ctx.session).get_or_create(name=chip_name, wafer=wafer, type="TS")
    
    for file_path in file_paths:
        with parsing_file(file_path):
            columns = ["ISR", "V1", "V2", "R"]
            data = parse_epg_dat_file(file_path, columns)
            conditions = create_ts_conditions(file_path.name, chip)
            conditions.measurements = create_ts_measurements(pd.concat(data["data"], copy=False))
            conditions.datetime = data["timestamp"]
            ctx.session.add(conditions)


@click.command(name="eqe")
@pass_analyzer_context
@click.argument("file_paths", default="./*.dat", callback=validate_files_glob)
def parse_eqe(ctx: AnalyzerContext, file_paths: tuple[Path]):
    """
    Parse EQE measurements from FILE_PATHS files. The measurements are saved to the database and
    processed files are renamed to FILENAME.parsed.
    """
    instrument_map: dict[str, Instrument] = {i.name: i for i in ctx.session.query(Instrument).all()}
    
    for file_path in file_paths:
        with parsing_file(file_path):
            data = parse_eqe_dat_file(file_path)
            measurements = create_eqe_measurements(data["data"])
            chip, _ = guess_chip_and_wafer(file_path.name, "eqe")
            conditions = create_eqe_conditions(
                data["conditions"], instrument_map, file_path, chip
            )
            conditions.measurements.extend(measurements)
            ctx.session.add(conditions)


@click.group(
    name="parse",
    help="Parse files with measurements and save to database",
    commands=[parse_iv, parse_cv, parse_eqe, parse_ts],
)
def parse_group():
    pass


@contextlib.contextmanager
@pass_analyzer_context
def parsing_file(ctx: AnalyzerContext, file_path: Path):
    """
    Context manager that handles file parsing. It prints the filename, starts a nested transaction
    and commits it if parsing was successful. If an exception is raised, the transaction is rolled
    back and the user is prompted to continue or abort.
    """
    print_filename_title(file_path)
    try:
        transaction = ctx.session.begin_nested()
        yield file_path
        transaction.commit()
        mark_file_as_parsed(file_path)
    except click.exceptions.Abort:
        transaction.rollback()
        ctx.logger.info("Skipping file...")
    except click.exceptions.Exit as e:
        raise e
    except Exception as e:
        sentry_sdk.capture_exception(e)
        transaction.rollback()
        ctx.logger.exception(f"Could not parse file {file_path} due to error: {e}")
        click.confirm("Do you want to continue?", abort=True)


def create_ts_conditions(filename: str, chip: AbstractChip) -> TsConditions:
    structure_types = ["TLM", "AL", "COMB"]
    prefix = "|".join(structure_types)
    matcher = re.compile(rf"^(?P<ts_type>{prefix})(?P<ts_number>\d)(?P<ts_step>\d).*$", re.I)
    match = matcher.match(filename)
    
    if match is None:
        click.get_current_context().obj.logger.warning(
            "Could not guess TS parameters from the filename"
        )
        raise click.Abort()
    ts_number = int(match.group("ts_number"))
    ts_step = int(match.group("ts_step"))
    ts_type = match.group("ts_type").upper()
    click.get_current_context().obj.logger.info(
        f"Guessed from filename: Structure type={ts_type}, Number={ts_number}, Step={ts_step}"
    )
    
    conditions = TsConditions(
        structure_type=ts_type,
        ts_step=ts_step,
        ts_number=ts_number,
        chip=chip,
    )
    return conditions


@pass_analyzer_context
def guess_chip_and_wafer(
    ctx: AnalyzerContext, filename: str, prefix: Literal["iv", "cv", "eqe"]
) -> tuple[AbstractChip, Wafer]:
    """
    Attempt to guess the chip and wafer names from the filename. If the names cannot be guessed,
    the user is prompted to input them manually.
    :param ctx:
    :param filename: file name to parse
    :param prefix: prefix for the file type
    :return:
    """
    matcher = re.compile(rf"^{prefix}\s+(?P<wafer>[\w\d]+)\s+(?P<chip>[\w\d-]+)(\s.*)?\..*$", re.I)
    match = matcher.match(filename)
    
    if match is None:
        chip_name = None
        wafer_name = None
        ctx.logger.warning("Could not guess chip and wafer from filename")
    else:
        chip_name = match.group("chip").upper()
        wafer_name = match.group("wafer").upper()
        ctx.logger.info(f"Guessed from filename: wafer={wafer_name}, chip={chip_name}")
    
    wafer_name = ask_wafer_name(default=wafer_name)
    wafer = WaferRepository(ctx.session).get_or_create(name=wafer_name)
    
    if not hasattr(wafer, 'id') or not wafer.id:
        confirm_wafer_creation(wafer)
    chip_name = ask_chip_name(default=chip_name)
    if wafer.name == "REF":
        chip = ChipRepository(ctx.session).get_or_create(name=chip_name, wafer=wafer, type="REF")
    else:
        chip = ChipRepository(ctx.session).get_or_create(name=chip_name, wafer=wafer)
    
    return chip, wafer


def ask_chip_name(default: str | None = None) -> str:
    chip_name = None
    while chip_name is None:
        chip_name = click.prompt("Input chip name", default=default, show_default=True)
    return chip_name.upper()


def ask_wafer_name(default: str | None = None) -> str:
    wafer_name = click.prompt(
        f"Input wafer name ({'press Enter to confirm default value ' if default else ''}or type 'skip' or 'exit')",
        type=str,
        default=default,
        show_default=True,
    ).upper()
    if wafer_name == "SKIP":
        raise click.Abort()
    if wafer_name == "EXIT":
        raise Exit(0)
    return wafer_name


@pass_analyzer_context
def confirm_wafer_creation(ctx: AnalyzerContext, wafer):
    click.confirm(
        f"There is no wafers with name={wafer.name} in the database. Do you want to create one?",
        default=True,
        abort=True,
    )
    ctx.session.add(wafer)
    ctx.session.flush([wafer])  # force id generation


@pass_analyzer_context
def ask_eqe_session(ctx: AnalyzerContext, timestamp: datetime) -> EqeSession:
    """
    Get or create an EQE session for the given timestamp. If no session is found, a new one is
    created. If multiple sessions are found, the user is prompted to select one.
    :param ctx:
    :param timestamp:
    :return:
    """
    found_eqe_sessions: list[EqeSession] = (
        ctx.session.query(EqeSession).filter(EqeSession.date == timestamp.date()).all()
    )
    if len(found_eqe_sessions) == 0:
        click.get_current_context().obj.logger.info(
            f"No sessions were found for measurement date {timestamp.date()}"
        )
        eqe_session = EqeSession(date=timestamp.date())
        ctx.session.add(eqe_session)
        ctx.session.flush([eqe_session])
        click.get_current_context().obj.logger.info(
            f"New eqe session was created: {repr(eqe_session)}"
        )
    elif len(found_eqe_sessions) == 1:
        eqe_session = found_eqe_sessions.pop()
        click.get_current_context().obj.logger.info(
            f"Existing eqe session will be used: {repr(eqe_session)}"
        )
    else:
        eqe_session = select_one(found_eqe_sessions,
                                 "Select eqe session",
                                 lambda s: (s.id, str(s.date)))
    return eqe_session


@remember_choice("Use {} for all parsed measurements")
def ask_carrier(session: Session) -> Carrier:
    carriers = session.query(Carrier).order_by(Carrier.id).all()
    carrier = select_one(carriers, "Select carrier")
    return carrier


@remember_choice("Apply {} to all parsed measurements")
def ask_chip_state(session: Session) -> ChipState:
    chip_states = session.query(ChipState).order_by(ChipState.id).all()
    chip_state = select_one(chip_states, "Select chip state")
    return chip_state


def parse_eqe_dat_file(file_path: Path) -> dict:
    """
    Parse EQE measurements from a .dat file. The file is expected to have a header with
    conditions and a table with measurements. The conditions are extracted first and then the
    measurements are read into a DataFrame.
    :param file_path:
    :return:
    """
    patterns: tuple[tuple[str, str, Callable[[str], Any]], ...] = (
        (
            "datetime",
            r"^(\d{2}/\d{2}/\d{4}\s\d{2}:\d{2})$",
            lambda m: datetime.strptime(m, "%d/%m/%Y %H:%M"),
        ),
        ("bias", r"^Bias \(V\):\s+([\d.-]+)$", float),
        ("averaging", r"^Averaging:\s+(\d+)$", int),
        ("dark_current", r"^Dark current \(A\):\s+([\d\.+-E]+)$", float),
        ("temperature", r"^Temperature \(C\):\s+([\d\.]+)$", float),
        ("calibration_file", r"^Used reference calibration file:\s+(.*)$", str),
        ("instrument", r"^Chosen SMU device:\s+(.+)$", str),
        ("ddc", r"^Sent DDC:\s+(.+)$", str),
        # FIXME(LEGACY): remove later
        (
            "datetime",
            r"^(\d{2}/\d{2}/\d{4}\s\d{2}\.\d{2})$",  # FOR OLD FILES WITH WRONG DATE FORMAT
            lambda m: datetime.strptime(m, "%d/%m/%Y %H.%M"),
        ),
    )
    conditions: dict[str, Any] = {"comment": ""}
    contents = file_path.read_text()
    for prop, pattern, factory in patterns:
        match = re.compile(pattern, re.MULTILINE).search(contents)
        if match:
            conditions[prop] = factory(match.group(1))
            contents = contents[: match.span(0)[0]] + contents[match.span(0)[1] + 1:]
    
    table_matcher = re.compile(r"MEASUREMENT DATA STARTS\s*(?P<table>[\s\S]*)", re.M | re.I)
    match = table_matcher.search(contents)
    data = pd.read_csv(StringIO(match.group("table")), sep="\t").replace(float("nan"), None)
    contents = contents[: match.span(0)[0]] + contents[match.span(0)[1] + 1:]
    conditions["comment"] = contents
    return {"conditions": conditions, "data": data}


def parse_epg_dat_file(file_path: Path, columns) -> EPGData:
    """
    Parse EPG measurements from a .dat file. The file is expected to have a header with conditions
    and a table with measurements. The conditions are extracted first and then the measurements are
    read into a DataFrame.
    :param file_path:
    :param columns:
    :return:
    """
    content = file_path.read_text()
    
    date_matcher = re.compile(r"^Date:\s*(?P<date>[\d/]+)\s*$", re.M | re.I)
    date_match = date_matcher.search(content)
    
    if date_match is None:
        click.get_current_context().obj.logger.warning("Could not guess date from file")
        date = click.prompt(
            "Input date",
            type=click.DateTime(formats=["%Y-%m-%d"]),
            default=datetime.now(),
            show_default=True,
        )
    else:
        date = datetime.strptime(date_match.group("date"), "%m/%d/%Y")
    
    time_matcher = re.compile(r"^Time:\s*(?P<time>[\d:]+)\s*$", re.M | re.I)
    time_match = time_matcher.search(content)
    if time_match is None:
        click.get_current_context().obj.logger.warning("Could not guess time from file")
        time = click.prompt(
            "Input time",
            type=click.DateTime(formats=["%H:%M:%S"]),
            default=datetime.now(),
            show_default=True,
        )
    else:
        time = datetime.strptime(time_match.group("time"), "%H:%M:%S")
    timestamp = datetime.combine(date, datetime.time(time))
    
    data: list[pd.DataFrame] = []
    for chunk in re.split(r"[\n\r]{2}", content, 0, re.M):
        if not chunk.strip():
            continue
        df = pd.read_csv(StringIO(chunk.strip()), sep="\t")
        if np.all([c in df.columns for c in columns]):
            data.append(df)
    
    if len(data) == 0:
        click.get_current_context().obj.logger.warning(
            "No data was found in given file. Does it use the unusual format?"
        )
        raise click.Abort()
    return {"timestamp": timestamp, "data": data}


def create_iv_measurements(data: pd.DataFrame) -> list[IVMeasurement]:
    return [
        IVMeasurement(
            voltage_input=row["VCA"],
            anode_current=row["IAN"],
            cathode_current=row["ICA"],
        )
        for idx, row in data.iterrows()
    ]


def create_cv_measurements(
    data: pd.DataFrame, timestamp: datetime, chip: AbstractChip, chip_state: ChipState
) -> Generator[CVMeasurement, None, None]:
    for idx, row in data.iterrows():
        yield CVMeasurement(
            chip=chip,
            chip_state=chip_state,
            voltage_input=row["BIAS"],
            capacitance=row["C"],
            datetime=timestamp,
        )


def create_eqe_measurements(
    data: pd.DataFrame,
) -> Generator[EqeMeasurement, None, None]:
    header_to_prop_map = {
        "Wavelength (nm)": "wavelength",
        "EQE (%)": "eqe",
        "Current (A)": "light_current",
        "Current Light (A)": "light_current",
        "Current Dark (A)": "dark_current",
        "Standard deviation (A)": "std",
        "Responsivity (A/W)": "responsivity",
    }
    
    for _, row in data.iterrows():
        yield EqeMeasurement(
            **{header_to_prop_map[header]: row[header] for header in data.columns},
        )


def create_ts_measurements(data: pd.DataFrame) -> list[TsMeasurement]:
    return [
        TsMeasurement(
            current=row["ISR"],
            voltage_1=row["V1"],
            voltage_2=row["V2"],
            resistance=row["R"],
        )
        for idx, row in data.iterrows()
    ]


@pass_analyzer_context
def create_eqe_conditions(
    ctx: AnalyzerContext,
    raw_data: dict,
    instrument_map: dict[str, Instrument],
    file_path: Path,
    chip: AbstractChip,
) -> EqeConditions:
    """
    Create EQE conditions from raw data and user input. The user is prompted to select an instrument
    and add comments to the conditions. Default values are applied to REF chips.
    :param ctx:
    :param raw_data:
    :param instrument_map:
    :param file_path:
    :param chip:
    :return:
    """
    existing = ctx.session.query(EqeConditions).filter_by(datetime=raw_data["datetime"]).all()
    if existing:
        existing_str = "\n".join([f"{i}. {repr(c)}" for i, c in enumerate(existing, start=1)])
        click.get_current_context().obj.logger.info(
            f"Found existing eqe measurements at {raw_data['datetime']}:\n{existing_str}"
        )
        click.confirm("Are you sure you want to add new measurements?", abort=True)
    
    instrument = instrument_map.get(raw_data.pop("instrument"), None)
    if instrument is None:
        click.get_current_context().obj.logger.warning(
            "Could not find instrument in provided file"
        )
        instrument = select_one(list(instrument_map.values()), "Select instrument")
    
    user_comment = click.prompt("Add comments for measurements", default="", show_default=False)
    comment = (
        f"Parsing comment: {user_comment}\n"
        f"Parsed file: {file_path.name}\n"
        f"{raw_data.get('comment', '')}"
    )
    
    conditions_data = {
        **raw_data,
        "chip": chip,
        "comment": comment or None,
        "instrument": instrument,
    }
    
    if chip.wafer.name == "REF":
        defaults = eqe_defaults.get(chip.name, None)
        if defaults is not None:
            click.get_current_context().obj.logger.info(
                f"Default values were applied to chip {chip.name}: {defaults}"
            )
            conditions_data.update(defaults)
    
    if "chip_state" not in conditions_data and "chip_state_id" not in conditions_data:
        conditions_data["chip_state"] = ask_chip_state(ctx.session)
    if "carrier" not in conditions_data and "carrier_id" not in conditions_data:
        conditions_data["carrier"] = ask_carrier(ctx.session)
    
    conditions_data["session"] = ask_eqe_session(raw_data["datetime"])
    
    return EqeConditions(**conditions_data)


def print_filename_title(path: Path, top_margin: int = 2, bottom_margin: int = 1):
    """
    Print a title for the file being processed.
    :param path:
    :param top_margin:
    :param bottom_margin:
    :return:
    """
    if top_margin:
        click.echo("\n" * top_margin, nl=False)
    
    click.get_current_context().obj.logger.debug(f"Processing file: {path.name}")
    click.echo("╔" + "═" * (len(path.name) + 2) + "╗")
    click.echo("║ " + path.name + " ║")
    click.echo("╚" + "═" * (len(path.name) + 2) + "╝")
    if bottom_margin:
        click.echo("\n" * bottom_margin, nl=False)


def mark_file_as_parsed(file_path: Path):
    """
    Rename the file to indicate that it was parsed and saved to the database.
    :param file_path:
    :return:
    """
    file_path = file_path.rename(file_path.with_suffix(file_path.suffix + ".parsed"))
    click.get_current_context().obj.logger.info(
        f"File was saved to database and renamed to '{file_path.name}'"
    )
