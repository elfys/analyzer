import contextlib
import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Generator

import click
import numpy as np
import pandas as pd
import sentry_sdk
from sqlalchemy.orm import (
    Session,
)

from orm import (
    CVMeasurement,
    Carrier,
    Chip,
    ChipRepository,
    ChipState,
    EqeConditions,
    EqeMeasurement,
    EqeSession,
    IVMeasurement,
    Instrument,
    IvConditions,
    TsConditions,
    TsMeasurement,
    Wafer,
    WaferRepository,
)
from utils import (
    eqe_defaults,
    from_context,
    remember_choice,
    select_one,
    validate_files_glob,
)


@click.command(name="iv", help="Parse IV measurements")
@click.pass_context
@click.argument("file_paths", default="./*.dat", callback=validate_files_glob)
def parse_iv(ctx: click.Context, file_paths: tuple[Path]):
    session = ctx.obj["session"]
    instrument_id = session.query(Instrument.id).filter(Instrument.name == "EPG").scalar()
    for file_path in file_paths:
        with parsing_file(file_path, ctx):
            chip, wafer = guess_chip_and_wafer(file_path.name, "iv", session)
            chip_state = ask_chip_state(session)
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
                session.add(conditions)


@click.command(name="cv", help="Parse CV measurements")
@click.pass_context
@click.argument("file_paths", default="./*.dat", callback=validate_files_glob)
def parse_cv(ctx: click.Context, file_paths: tuple[Path]):
    session = ctx.obj["session"]
    for file_path in file_paths:
        with parsing_file(file_path, ctx):
            chip, _ = guess_chip_and_wafer(file_path.name, "cv", session)
            chip_state = ask_chip_state(session)
            columns = ["BIAS", "C"]
            data = parse_epg_dat_file(file_path, columns)
            measurements = create_cv_measurements(
                pd.concat(data["data"], copy=False), data["timestamp"], chip, chip_state
            )
            session.add_all(measurements)


@click.command(name="ts", help="Parse Test Structure measurements")
@click.argument("file_paths", default="./*.dat", callback=validate_files_glob)
@click.pass_context
def parse_ts(ctx: click.Context, file_paths: tuple[Path]):
    session = ctx.obj["session"]
    wafer_name = ask_wafer_name()
    wafer = WaferRepository(session).get_or_create(name=wafer_name)
    if not wafer.id:
        confirm_wafer_creation(wafer)
    
    ctx.obj["logger"].info(f"{wafer.name} will be used for every parsed measurement")
    chip_name = ask_chip_name()
    chip = ChipRepository(session).get_or_create(name=chip_name, wafer=wafer, type="TS")
    
    for file_path in file_paths:
        with parsing_file(file_path, ctx):
            columns = ["ISR", "V1", "V2", "R"]
            data = parse_epg_dat_file(file_path, columns)
            conditions = create_ts_conditions(file_path.name, chip)
            conditions.measurements = create_ts_measurements(pd.concat(data["data"], copy=False))
            conditions.datetime = data["timestamp"]
            session.add(conditions)


@click.command(name="eqe", help="Parse EQE measurements")
@click.pass_context
@click.argument("file_paths", default="./*.dat", callback=validate_files_glob)
def parse_eqe(ctx: click.Context, file_paths: tuple[Path]):
    session: Session = ctx.obj["session"]
    instrument_map: dict[str, Instrument] = {i.name: i for i in session.query(Instrument).all()}
    
    
    for file_path in file_paths:
        with parsing_file(file_path, ctx):
            data = parse_eqe_dat_file(file_path)
            measurements = create_eqe_measurements(data["data"])
            chip, _ = guess_chip_and_wafer(file_path.name, "eqe", session)
            conditions = create_eqe_conditions(
                data["conditions"], instrument_map, file_path, session, chip
            )
            conditions.measurements.extend(measurements)
            session.add(conditions)


@click.group(
    name="parse",
    help="Parse files with measurements and save to database",
    commands=[parse_iv, parse_cv, parse_eqe, parse_ts],
)
def parse_group():
    pass


@contextlib.contextmanager
def parsing_file(file_path: Path, ctx):
    session: Session = ctx.obj["session"]
    
    print_filename_title(file_path)
    try:
        transaction = session.begin_nested()
        yield file_path
        transaction.commit()
        mark_file_as_parsed(file_path)
    except click.exceptions.Abort:
        transaction.rollback()
        ctx.obj["logger"].info("Skipping file...")
    except click.exceptions.Exit as e:
        ctx.obj["logger"].info("Exiting...")
        ctx.exit(e.exit_code)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        transaction.rollback()
        ctx.obj["logger"].exception(f"Could not parse file {file_path} due to error: {e}")
        click.confirm("Do you want to continue?", abort=True)


def create_ts_conditions(filename: str, chip: Chip) -> TsConditions:
    structure_types = ["TLM", "AL", "COMB"]
    prefix = "|".join(structure_types)
    matcher = re.compile(rf"^(?P<ts_type>{prefix})(?P<ts_number>\d)(?P<ts_step>\d).*$", re.I)
    match = matcher.match(filename)
    
    if match is None:
        click.get_current_context().obj["logger"].warning(
            "Could not guess TS parameters from the filename"
        )
        raise click.Abort()
    ts_number = int(match.group("ts_number"))
    ts_step = int(match.group("ts_step"))
    ts_type = match.group("ts_type").upper()
    click.get_current_context().obj["logger"].info(
        f"Guessed from filename: Structure type={ts_type}, Number={ts_number}, Step={ts_step}"
    )
    
    conditions = TsConditions(
        structure_type=ts_type,
        ts_step=ts_step,
        ts_number=ts_number,
        chip=chip,
    )
    return conditions


@from_context("logger", "logger")
def guess_chip_and_wafer(
    filename: str, prefix: str, session: Session, logger
) -> tuple[Chip, Wafer]:
    matcher = re.compile(rf"^{prefix}\s+(?P<wafer>[\w\d]+)\s+(?P<chip>[\w\d-]+)(\s.*)?\..*$", re.I)
    match = matcher.match(filename)
    
    if match is None:
        chip_name = None
        wafer_name = None
        logger.warning("Could not guess chip and wafer from filename")
    else:
        chip_name = match.group("chip").upper()
        wafer_name = match.group("wafer").upper()
        logger.info(f"Guessed from filename: wafer={wafer_name}, chip={chip_name}")
    
    wafer_name = ask_wafer_name(default=wafer_name)
    wafer = WaferRepository(session).get_or_create(name=wafer_name)
    
    if not hasattr(wafer, 'id') or not wafer.id:
        confirm_wafer_creation(wafer)
    chip_name = ask_chip_name(default=chip_name)
    if wafer.name == "REF":
        chip = ChipRepository(session).get_or_create(name=chip_name, wafer=wafer, type="REF")
    else:
        chip = ChipRepository(session).get_or_create(name=chip_name, wafer=wafer)
    
    return chip, wafer


def ask_chip_name(default: str = None) -> str:
    chip_name = None
    while chip_name is None:
        chip_name = click.prompt("Input chip name", default=default, show_default=True)
    return chip_name.upper()


def ask_wafer_name(default: str = None) -> str:
    wafer_name = click.prompt(
        f"Input wafer name ({'press Enter to confirm default value ' if default else ''}or type 'skip' or 'exit')",
        type=str,
        default=default,
        show_default=True,
    ).upper()
    if wafer_name == "SKIP":
        raise click.Abort()
    if wafer_name == "EXIT":
        click.get_current_context().exit(0)
    return wafer_name


@from_context("session", "session")
def confirm_wafer_creation(wafer, session: Session):
    click.confirm(
        f"There is no wafers with name={wafer.name} in the database. Do you want to create one?",
        default=True,
        abort=True,
    )
    session.add(wafer)
    session.flush([wafer])  # force id generation


def ask_session(timestamp: datetime, session: Session) -> EqeSession:
    found_eqe_sessions: list[EqeSession] = (
        session.query(EqeSession).filter(EqeSession.date == timestamp.date()).all()
    )
    if len(found_eqe_sessions) == 0:
        click.get_current_context().obj["logger"].info(
            f"No sessions were found for measurement date {timestamp.date()}"
        )
        eqe_session = EqeSession(date=timestamp.date())
        session.add(eqe_session)
        session.flush([eqe_session])
        click.get_current_context().obj["logger"].info(
            f"New eqe session was created: {repr(eqe_session)}"
        )
    elif len(found_eqe_sessions) == 1:
        eqe_session = found_eqe_sessions.pop()
        click.get_current_context().obj["logger"].info(
            f"Existing eqe session will be used: {repr(eqe_session)}"
        )
    else:
        eqe_session = select_one(found_eqe_sessions, "Select eqe session", lambda s: (s.id, s.date))
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
    patterns = (
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
    conditions = {"comment": ""}
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


def parse_epg_dat_file(file_path: Path, columns) -> dict[str, datetime | list[pd.DataFrame]]:
    content = file_path.read_text()
    
    date_matcher = re.compile(r"^Date:\s*(?P<date>[\d/]+)\s*$", re.M | re.I)
    date_match = date_matcher.search(content)
    
    if date_match is None:
        click.get_current_context().obj["logger"].warning("Could not guess date from file")
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
        click.get_current_context().obj["logger"].warning("Could not guess time from file")
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
        click.get_current_context().obj["logger"].warning(
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
    data: pd.DataFrame, timestamp: datetime, chip: Chip, chip_state: ChipState
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


def create_eqe_conditions(
    raw_data: dict,
    instrument_map: dict[str, Instrument],
    file_path: Path,
    session: Session,
    chip: Chip,
) -> EqeConditions:
    existing = session.query(EqeConditions).filter_by(datetime=raw_data["datetime"]).all()
    if existing:
        existing_str = "\n".join([f"{i}. {repr(c)}" for i, c in enumerate(existing, start=1)])
        click.get_current_context().obj["logger"].info(
            f"Found existing eqe measurements at {raw_data['datetime']}:\n{existing_str}"
        )
        click.confirm("Are you sure you want to add new measurements?", abort=True)
    
    instrument = instrument_map.get(raw_data.pop("instrument"), None)
    if instrument is None:
        click.get_current_context().obj["logger"].warning(
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
            click.get_current_context().obj["logger"].info(
                f"Default values were applied to chip {chip.name}: {defaults}"
            )
            conditions_data.update(defaults)
    
    if "chip_state" not in conditions_data and "chip_state_id" not in conditions_data:
        conditions_data["chip_state"] = ask_chip_state(session)
    if "carrier" not in conditions_data and "carrier_id" not in conditions_data:
        conditions_data["carrier"] = ask_carrier(session)
    
    conditions_data["session"] = ask_session(raw_data["datetime"], session)
    
    return EqeConditions(**conditions_data)


def print_filename_title(path: Path, top_margin: int = 2, bottom_margin: int = 1):
    if top_margin:
        click.echo("\n" * top_margin, nl=False)
    
    click.get_current_context().obj["logger"].debug(f"Processing file: {path.name}")
    click.echo("╔" + "═" * (len(path.name) + 2) + "╗")
    click.echo("║ " + path.name + " ║")
    click.echo("╚" + "═" * (len(path.name) + 2) + "╝")
    if bottom_margin:
        click.echo("\n" * bottom_margin, nl=False)


def mark_file_as_parsed(file_path: Path):
    file_path = file_path.rename(file_path.with_suffix(file_path.suffix + ".parsed"))
    click.get_current_context().obj["logger"].info(
        f"File was saved to database and renamed to '{file_path.name}'"
    )
