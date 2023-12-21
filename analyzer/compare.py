from decimal import Decimal
from time import strftime
from typing import Iterable

import click
import numpy as np
import pandas as pd
from openpyxl.styles.numbers import FORMAT_PERCENTAGE_00
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import (
    bindparam,
    select,
)
from sqlalchemy.orm import Session

from orm import (
    Chip,
    ChipState,
    IVMeasurement,
    IvConditions,
    Wafer,
)
from utils import (
    EntityOption,
    flatten_options_type,
    get_thresholds,
)


@click.command(name="wafers", help="Compare wafers")
@click.pass_context
@click.option(
    "-w",
    "--wafers",
    "wafer_names",
    type=flatten_options_type,
    help="Wafers to compare",
    prompt=True,
)
@click.option(
    "-s",
    "--chip-state",
    "chip_states",
    help="States of chips to analyze",
    default=["ALL"],
    show_default=True,
    multiple=True,
    cls=EntityOption,
    entity_type=ChipState,
)
@click.option(
    "-o",
    "--output",
    "file_name",
    default=lambda: f"wafers-comparison-{strftime('%y%m%d-%H%M%S')}.xlsx",
    help="Output file name.",
    show_default="wafers-comparison-{datetime}.xlsx",
)
def compare_wafers(
    ctx: click.Context, wafer_names: set[str], chip_states: tuple[EntityOption], file_name: str
):
    session: Session = ctx.obj["session"]
    wafer_names = set(map(lambda x: x.upper(), wafer_names))
    wafers = session.execute(select(Wafer).filter(Wafer.name.in_(wafer_names))).scalars().all()
    
    not_found_wafers = wafer_names - set(wafer.name for wafer in wafers)
    if not_found_wafers:
        ctx.obj["logger"].warning(f"Wafers not found: {', '.join(not_found_wafers)}")
        wafer_names -= not_found_wafers
    
    sheets_data = get_sheets_data(ctx, session, wafers)
    
    if not sheets_data["frame_keys"]:
        ctx.obj["logger"].warning("No data to compare")
        return
    
    save_compare_wafers_report(file_name, sheets_data, chip_states)
    ctx.obj["logger"].info(f"Wafers comparison is saved to {file_name}")


def save_compare_wafers_report(file_name, sheets_data, chip_states):
    chip_states_dict = {state.id: state.name for state in chip_states}
    frame_keys = sheets_data.pop("frame_keys")
    with pd.ExcelWriter(file_name) as writer:
        for key, data in sheets_data.items():
            df = pd.concat(data["frames"], keys=frame_keys, copy=False)
            df.dropna(how="all", axis=1, inplace=True)
            df.columns = pd.MultiIndex.from_tuples(
                df.columns.values, names=["Voltage", "Chip type"]
            )
            df.sort_index(axis=1, inplace=True, level=[0, 1])
            
            df.index = pd.MultiIndex.from_tuples(
                df.index.map(lambda idx: (idx[0], chip_states_dict[idx[1]])),
                names=["Wafer", "Chip state"],
            )
            if key != "yield":
                df.columns = add_perimeter_area_level(df.columns)
            
            df.to_excel(writer, sheet_name=data["title"])
            
            ws: Worksheet = writer.sheets[data["title"]]
            start_col = get_column_letter(df.index.nlevels + 1)
            start_row = df.columns.nlevels + 1
            values_slice = f"{start_col}{start_row}:{get_column_letter(ws.max_column)}{ws.max_row}"
            
            number_format = FORMAT_PERCENTAGE_00 if key == "yield" else "0.00E+00"
            for row in ws[values_slice]:
                for cell in row:
                    cell.number_format = number_format


def get_sheets_data(ctx: click.Context, session, wafers: Iterable[Wafer]) -> dict[str, dict]:
    thresholds = get_thresholds(session, "IV")
    
    threshold_voltages = set({v for x in thresholds.values() for v in x.keys()})
    conditions_query = (
        select(IvConditions, Chip.type.label("chip_type"), IVMeasurement)
        .join(IvConditions.measurements)
        .join(IvConditions.chip)
        .filter(
            Chip.wafer_id == bindparam("wafer_id"),
            Chip.test_structure.is_(False),
            IVMeasurement.voltage_input.in_(threshold_voltages),
        )
        .order_by(IvConditions.datetime)
    )
    
    sheets_data = {
        "yield": {"frames": [], "title": "Yield"},
        "std": {"frames": [], "title": "Standard Deviation"},
        "leakage": {"frames": [], "title": "Leakage"},
        "density": {"frames": [], "title": "Density"},
        "frame_keys": [],
    }
    
    for wafer in wafers:
        values_frame = pd.read_sql_query(
            conditions_query.params(wafer_id=wafer.id), session.connection()
        )
        
        if values_frame.empty:
            ctx.obj["logger"].warning(f"Not found measurements for {wafer.name}")
            continue
        sheets_data["frame_keys"].append(wafer.name)
        
        values_frame["value"] = values_frame["anode_current_corrected"].fillna(
            values_frame["anode_current"]
        )
        
        values_frame.drop_duplicates(
            subset=["voltage_input", "chip_id", "chip_state_id"],
            keep="last",
            inplace=True,
        )
        
        values_frame = values_frame.pivot_table(
            values="value",
            columns="voltage_input",
            index=["chip_type", "chip_state_id", "chip_id"],
        )
        values_frame.rename(
            columns=lambda x: Decimal(x).quantize(next(iter(threshold_voltages))),
            inplace=True,
        )
        
        def remove_cols_wo_thresholds(frame: pd.DataFrame):
            chip_type = frame.name
            cols_to_drop = set(frame.columns.values) - set(thresholds[chip_type].keys())
            frame.loc[:, list(cols_to_drop)] = np.nan
            return frame
        
        values_frame = values_frame.groupby(["chip_type"]).apply(remove_cols_wo_thresholds)
        
        sheets_data["yield"]["frames"].append(get_yield_frame(thresholds, values_frame))
        sheets_data["std"]["frames"].append(get_std_frame(values_frame))
        sheets_data["leakage"]["frames"].append(get_leakage_frame(values_frame))
        sheets_data["density"]["frames"].append(get_density_frame(values_frame))
    
    return sheets_data


def get_density_frame(values_frame):
    def divide_by_area(frame):
        chip_type = frame.name
        return frame / Chip.get_area(chip_type)
    
    density_frame = (
        values_frame.groupby("chip_type")
        .apply(divide_by_area)
        .groupby(["chip_type", "chip_state_id"])
        .median()
    )
    density_frame = density_frame.unstack(level="chip_type")
    return density_frame


def get_yield_frame(thresholds, values_frame) -> pd.DataFrame:
    row_thresholds = {
        chip_type: np.array(
            [chip_type_thresholds.get(column, np.nan) for column in values_frame.columns]
        )
        for chip_type, chip_type_thresholds in thresholds.items()
    }
    
    def pass_threshold(frame):
        chip_type = frame.name
        th: np.ndarray = row_thresholds[chip_type]
        return pd.DataFrame(
            np.where(np.isnan(frame), np.nan, frame >= th),
            columns=frame.columns,
            index=frame.index,
            copy=False,
        )
    
    pass_frame = values_frame.groupby("chip_type").apply(pass_threshold)
    total_series = pass_frame.min(axis=1).groupby("chip_state_id").mean()
    total_series.name = ("Total", "")
    yield_frame = pass_frame.groupby(["chip_type", "chip_state_id"]).mean()
    yield_frame = yield_frame.unstack(level="chip_type")
    return pd.concat(
        [
            yield_frame,
            total_series,
        ],
        axis=1,
        copy=False,
    )


def get_leakage_frame(values_frame) -> pd.DataFrame:
    leakage_frame = (
        values_frame.groupby(["chip_type", "chip_state_id"]).median().unstack(level="chip_type")
    )
    return leakage_frame


def add_perimeter_area_level(index: pd.MultiIndex) -> pd.MultiIndex:
    idx_tuples = []
    for col in index.values:
        voltage, chip_type = col
        perimeter_area = Chip.get_perimeter(chip_type) / Chip.get_area(chip_type)
        idx_tuples.append((voltage, chip_type, Decimal(perimeter_area).quantize(Decimal("0.001"))))
    return pd.MultiIndex.from_tuples(idx_tuples, names=[*index.names, "Perimeter / area"])


def get_std_frame(values_frame) -> pd.DataFrame:
    std_frame = (
        values_frame.groupby(["chip_type", "chip_state_id"]).std().unstack(level="chip_type")
    )
    return std_frame


@click.group(
    name="compare",
    help="Set of commands to compare entities",
    commands=[compare_wafers],
)
def compare_group():
    ...
