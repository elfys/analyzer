from datetime import (
    date,
    datetime,
)
from decimal import Decimal
from typing import (
    Any,
    Iterable,
    List,
)

import click
import pandas as pd
from openpyxl.styles import PatternFill
from pandas import DataFrame
from sqlalchemy.orm import (
    InstrumentedAttribute,
    Session,
    joinedload,
)
from sqlalchemy.orm.base import _T_co

from analyzer.summary.common import (
    apply_conditional_formatting,
    date_formats,
    date_formats_help,
    get_info,
    get_slice_by_voltages,
    plot_data,
)
from orm import (
    CVMeasurement,
    Chip,
    ChipState,
    Wafer,
)
from utils import (
    EntityOption,
    get_indexed_filename,
    get_thresholds,
)


@click.command(name="cv", help="Make summary (png and xlsx) for CV measurements' data.")
@click.pass_context
@click.option("-t", "--chips-type", help="Type of the chips to analyze.")
@click.option("-w", "--wafer", "wafer_name", prompt="Wafer name", help="Wafer name.")
@click.option(
    "-s",
    "--chip-state",
    "chip_states",
    help="State of the chips to summarize.",
    default=["ALL"],
    show_default=True,
    multiple=True,
    cls=EntityOption,
    entity_type=ChipState,
)
@click.option(
    "-q",
    "--quantile",
    default=(0.01, 0.99),
    show_default=True,
    type=click.Tuple([float, float]),
    help="Min and max plotted values cutoff.",
)
@click.option(
    "--before",
    type=click.DateTime(formats=date_formats),
    help=f"Include measurements before (exclusive) provided date and time. {date_formats_help}",
)
@click.option(
    "--after",
    type=click.DateTime(formats=date_formats),
    help=f"Include measurements after (inclusive) provided date and time. {date_formats_help}",
)
def summary_cv(
    ctx: click.Context,
    chips_type: str | None,
    wafer_name: str,
    chip_states: list[ChipState],
    quantile: tuple[float, float],
    before: datetime | None,
    after: datetime | None,
):
    session: Session = ctx.obj["session"]
    if ctx.obj["default_wafer"].name != wafer_name:
        wafer = session.query(Wafer).filter(Wafer.name == wafer_name).first()
    else:
        wafer = ctx.obj["default_wafer"]
    query = (
        session.query(CVMeasurement)
        .filter(CVMeasurement.chip.has(Chip.wafer.__eq__(wafer)))
        .options(joinedload(CVMeasurement.chip))
    )
    
    # TODO: use EntityChoice with default=ALL instead
    if chips_type is not None:
        query = query.filter(CVMeasurement.chip.has(Chip.type.__eq__(chips_type)))
    else:
        ctx.obj["logger"].info(
            "Chips type (-t or --chips-type) is not specified. Analyzing all chip types."
        )
    
    query = query.filter(CVMeasurement.chip_state_id.in_((c.id for c in chip_states)))
    
    if before is not None or after is not None:
        after = after if after is not None else date.min
        before = before if before is not None else date.max
        query = query.filter(CVMeasurement.datetime.between(after, before))
    
    measurements: list[CVMeasurement] = query.all()
    
    if not measurements:
        ctx.obj["logger"].warning("No measurements found.")
        return
    
    chips_types = (
        {chips_type}
        if chips_type is not None
        else {measurement.chip.type for measurement in measurements}
    )
    
    sheets_data = get_sheets_cv_data(measurements)
    voltages = sorted(Decimal(v) for v in ["-5", "0", "-35"])
    thresholds = get_thresholds(session, "CV")
    
    file_name = get_indexed_filename(f"Summary-CV-{wafer_name}", ("png", "xlsx"))
    
    if len(chips_types) > 1:
        ctx.obj["logger"].warning(
            f"Multiple chip types are found ({chips_types}). Plotting is not supported and will be skipped."
        )
    else:
        chips_type = next(iter(chips_types))
        fig, axes = plot_data(measurements, voltages, quantile, thresholds.get(chips_type, {}))
        fig.suptitle(wafer_name, fontsize=14)
        for ax_row in axes:
            ax_row[0].set_xlabel("Capacitance [pF]")
        
        png_file_name = f"{file_name}.png"
        
        fig.savefig(png_file_name, dpi=300)
        ctx.obj["logger"].info(f"Summary data is plotted to {png_file_name}")
    
    exel_file_name = f"{file_name}.xlsx"
    info = get_info(wafer=wafer, chip_states=chip_states, measurements=measurements)
    save_cv_summary_to_excel(sheets_data, info, exel_file_name, voltages, thresholds)
    
    ctx.obj["logger"].info(f"Summary data is saved to {exel_file_name}")


# class SheetsCVData(TypedDict): # TODO: finish this
#     capacitance: DataFrame
#     chip_names: List[str]
#     voltages: List[Decimal]

def save_cv_summary_to_excel(
    sheets_data: dict,
    info: pd.Series,
    file_name: str,
    voltages: Iterable[Decimal],
    thresholds: dict[str, dict[Decimal, float]],
):
    summary_df = get_slice_by_voltages(sheets_data["capacitance"], voltages)
    rules = {
        "greaterThanOrEqual": PatternFill(bgColor="ee9090", fill_type="solid"),
        "lessThan": PatternFill(bgColor="90ee90", fill_type="solid"),
    }
    
    with pd.ExcelWriter(file_name) as writer:
        summary_df.to_excel(writer, sheet_name="Summary")
        apply_conditional_formatting(
            writer.book["Summary"],
            rules,
            thresholds,
        )
        
        sheets_data["capacitance"].rename(columns=float).to_excel(writer, sheet_name="All data")
        info.to_excel(writer, sheet_name="Info")


def get_sheets_cv_data(
    measurements: list[CVMeasurement],
) -> dict[str, pd.DataFrame | Any]:
    chip_names: list[str] = sorted({measurement.chip.name for measurement in measurements})
    voltages: list[Decimal] = sorted({measurement.voltage_input for measurement in measurements})
    capacitance_df: DataFrame = pd.DataFrame(dtype="float64", index=chip_names, columns=voltages)
    with click.progressbar(measurements, label="Processing measurements...") as progress:
        for measurement in progress:
            measurement: CVMeasurement
            cell_location = (measurement.chip.name, measurement.voltage_input)
            capacitance_df.loc[cell_location] = measurement.capacitance
    return {
        "capacitance": capacitance_df,
        "chip_names": chip_names,
        "voltages": voltages,
    }
