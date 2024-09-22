from itertools import chain
from typing import Optional

import click
import pandas as pd
from click.exceptions import Exit
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from sqlalchemy import text
from sqlalchemy.orm import (
    Query,
    joinedload,
)

from orm import (
    EqeConditions,
    EqeSession,
    Wafer,
)
from utils import (
    eqe_session_date,
    get_indexed_filename,
    wafer_loader,
)

from ..context import (
    AnalyzerContext,
    pass_analyzer_context,
)


@click.command(name="eqe")
@pass_analyzer_context
@click.option(
    "-w",
    "--wafer",
    help="Name of wafer to analyze. Multiple EQE sessions may be found.",
    callback=wafer_loader,
)
@click.option(
    "--session",
    "eqe_session",
    help="Date of EQE session or special word 'last'",
    type=click.DateTime(formats=["%Y-%m-%d", "last"]),
    callback=eqe_session_date,
)
@click.option(
    "--no-ref",
    is_flag=True,
    default=False,
    help="Exclude reference measurements from the plots",
)
def summary_eqe(
    ctx: AnalyzerContext,
    wafer: Wafer | None,
    eqe_session: Optional[EqeSession],
    no_ref: bool,
):
    """
    "Make summary (.png and .xlsx) for EQE measurements' data."
    """
    if eqe_session and wafer:
        raise click.UsageError(
            "--wafer and --session options are not allowed to use simultaneously"
        )
    if not eqe_session and not wafer:
        raise click.UsageError("Neither --wafer nor --session are specified")
    title = f"{wafer.name} wafer" if wafer else f"{eqe_session.date} session"
    
    conditions = query_eqe_conditions(eqe_session, wafer.name)
    if not conditions:
        ctx.logger.warning("No measurements found.")
        raise Exit(0)
    ctx.logger.info("EQE data is loaded.")
    
    file_name = f"Summary-EQE-{title.replace(' ', '-')}"
    file_name = get_indexed_filename(file_name, ("png", "xlsx"))
    png_file_name, exel_file_name = f"{file_name}.png", f"{file_name}.xlsx"
    
    fig = get_eqe_plot_figure(eqe_session, no_ref)
    fig.suptitle(f"EQE summary for {title}")
    fig.savefig(png_file_name, dpi=300)
    ctx.logger.info(f"EQE data is plotted to {png_file_name}")
    
    sheets_data = get_sheets_eqe_data(conditions)
    with pd.ExcelWriter(exel_file_name) as writer:
        for sheet_data in sheets_data:
            sheet_data["df"].to_excel(writer, sheet_name=sheet_data["name"])
    
    ctx.logger.info(f"Summary data is saved to {exel_file_name}")


def get_eqe_plot_figure(sheets_data, no_ref=False) -> Figure:
    plottable_sheets = [sheet for sheet in sheets_data if sheet.get("prop") is not None]
    fig, axes = plt.subplots(len(plottable_sheets), 1, figsize=(10, 15))
    
    for sheet_data, ax in zip(plottable_sheets, axes.ravel()):
        ax: Axes
        last_rows = sheet_data["df"].groupby(by=["Wafer", "Chip"]).last()
        for (wafer_name, chip_name), series in last_rows.iterrows():
            if wafer_name.upper() == "REF" and no_ref:
                continue
            xs = [key for key in series.dropna().keys() if isinstance(key, int)]
            ys = [series[x] for x in xs]
            ax.plot(xs, ys, label=f"{wafer_name} {chip_name}")
            ax.set_xlabel("Wavelength, nm")
            ax.set_ylabel(f"{sheet_data['name']}, {sheet_data['unit']}")
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        fig.tight_layout()
    return fig


@pass_analyzer_context
def query_eqe_conditions(ctx: AnalyzerContext, eqe_session, wafer_name) -> list[EqeConditions]:
    """
    Query EQE conditions based on the provided EQE session or wafer name.

    :param ctx: The context object (provided by the click decorator).
    :param eqe_session: The EQE session to filter the conditions.
    :param wafer_name: The name of the wafer to filter the conditions.
    :return:
    """
    query: Query = (
        ctx.session.query(EqeConditions)
        .options(joinedload(EqeConditions.chip))
        .options(joinedload(EqeConditions.measurements))
    )
    if eqe_session:
        query = query.filter(EqeConditions.session == eqe_session)
    if wafer_name:
        eqe_session_ids = ctx.session.execute(
            text("""
        SELECT DISTINCT eqe_conditions.session_id FROM eqe_conditions
        WHERE eqe_conditions.chip_id IN (
            SELECT chip.id FROM chip WHERE chip.wafer_id = (
                SELECT wafer.id FROM wafer WHERE wafer.name = :wafer_name
            )
        )
        """), {"wafer_name": wafer_name},
        ).all()
        
        if not eqe_session_ids:
            ctx.logger.warning("No EQE sessions were found for given wafer name")
            raise Exit(0)
        query = query.filter(EqeConditions.session_id.in_(chain.from_iterable(eqe_session_ids)))
    conditions = query.all()
    return conditions


def get_sheets_eqe_data(conditions: list[EqeConditions]) -> list[dict]:
    """
    Process EQE conditions and organize them into a structured format suitable for Excel sheets.

    :param conditions: A list of EQEConditions objects to be processed.
    :return: A list of dictionaries, each containing a DataFrame and metadata for an Excel sheet.
    """
    all_sheets = []
    
    series_list = []
    for condition in conditions:
        series_list.append(pd.Series({
            "Datetime": condition.datetime,
            "Wafer": condition.chip.wafer.name,
            "Chip": condition.chip.name,
            "Bias": condition.bias,
            "Averaging": condition.averaging,
            "Dark current": condition.dark_current,
            "Temperature": condition.temperature,
        }))
    df_info = pd.concat(series_list, axis=1, ignore_index=True).T
    df_info.set_index("Datetime", inplace=True)
    df_info = df_info.sort_index()
    all_sheets.append({"df": df_info, "name": "Info"})
    
    for prop, name, unit in (
        ("eqe", "EQE", "%"),
        ("light_current", "Light current", "A"),
        ("dark_current", "Dark current", "A"),
        ("responsivity", "Responsivity", "A/W"),
        ("std", "Standard deviation", "A"),
    ):
        series_list = []
        for condition in conditions:
            measurements = sorted(condition.measurements, key=lambda m: m.wavelength)
            series = pd.Series({
                "Datetime": condition.datetime,
                "Wafer": condition.chip.wafer.name,
                "Chip": condition.chip.name,
                **{m.wavelength: getattr(m, prop) for m in measurements},
            })
            series_list.append(series)
        df = pd.concat(series_list, axis=1, ignore_index=True).T
        if df.dropna(axis=1, how="all").empty:
            continue
        df.set_index("Datetime", inplace=True)
        df = df.sort_index()
        all_sheets.append({"name": name, "df": df, "prop": prop, "unit": unit})
    
    return all_sheets
