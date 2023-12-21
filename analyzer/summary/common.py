from decimal import Decimal
from time import localtime, strftime
from typing import Any, Collection, Iterable, Union

import click
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from numpy import ndarray
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Fill
from openpyxl.worksheet.worksheet import Worksheet

from orm import CVMeasurement, ChipState, IVMeasurement, IvConditions, Wafer

date_formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
date_formats_help = f"Supported formats are: {', '.join((strftime(f) for f in date_formats))}."


def get_slice_by_voltages(df: pd.DataFrame, voltages: Iterable[Decimal]) -> pd.DataFrame:
    columns = sorted(voltages)
    slice_df = df[df.columns.intersection(columns)].copy()

    empty_cols = slice_df.isna().all(axis=0)
    if empty_cols.any():
        click.get_current_context().obj["logger"].warning(
            f"""The following voltages are not present in the data: {
            [float(col) for col, val in empty_cols.items() if val]}."""
        )
    slice_df.dropna(axis=1, how="all", inplace=True)
    return slice_df


def apply_conditional_formatting(
    sheet: Worksheet,
    rules: dict[str, Fill],
    thresholds: dict[str, dict[Decimal, float]],
):
    chip_row_index = [(i + 1, cell.value) for i, cell in enumerate(sheet["A"]) if cell.value]

    for chip_type, chip_type_thresholds in thresholds.items():
        def is_current_type(chip_name: str) -> bool:
            return chip_name.startswith(chip_type)

        for voltage, threshold in chip_type_thresholds.items():
            try:
                column_cell = next(
                    (
                        cell
                        for cell in sheet["1"]
                        if cell.value is not None and Decimal(str(cell.value)) == voltage
                    )
                )
                first_row_index = next(i for i, v in chip_row_index if is_current_type(v))
                last_row_index = next(i for i, v in reversed(chip_row_index) if is_current_type(v))
            except (ValueError, StopIteration):
                continue

            column_letter = column_cell.column_letter
            cell_range = f"{column_letter}{first_row_index}:{column_letter}{last_row_index}"
            for rule_name, rule in rules.items():
                cells_rule = CellIsRule(operator=rule_name, formula=[threshold], fill=rule)
                sheet.conditional_formatting.add(cell_range, cells_rule)


def get_info(
    wafer: Wafer,
    chip_states: Iterable[ChipState],
    measurements: Union[list[IvConditions], list[CVMeasurement]],
) -> pd.Series:
    format_date = strftime("%A, %d %b %Y", localtime())
    chip_states_str = "; ".join([state.name for state in chip_states])

    first_measurement = min(measurements, key=lambda m: m.datetime)
    last_measurement = max(measurements, key=lambda m: m.datetime)

    return pd.Series(
        {
            "Wafer": wafer.name,
            "Summary generation date": format_date,
            "Chip state": chip_states_str,
            "First measurement date": first_measurement.datetime,
            "Last measurement date": last_measurement.datetime,
        }
    )


def plot_hist(ax: Axes, data: np.ndarray):
    ax.set_ylabel("Number of chips")
    ax.hist(data * 1e12, bins=15)


def plot_heat_map(ax: Axes, values: np.ndarray, xs: np.ndarray, ys: np.ndarray, vmin, vmax):
    width = xs.max() - xs.min() + 1
    height = ys.max() - ys.min() + 1
    grid = np.full((height, width), np.nan)
    grid[ys - ys.min(), xs - xs.min()] = values

    X = np.linspace(min(xs) - 0.5, max(xs) + 0.5, width + 1)
    Y = np.linspace(min(ys) - 0.5, max(ys) + 0.5, height + 1)
    mesh = ax.pcolormesh(X, Y, grid, cmap="hot", shading="flat", vmin=vmin, vmax=vmax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=0))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=0))
    ax.set_ylabel("Y coordinate")
    ax.set_xlabel("X coordinate")
    ax.figure.colorbar(mesh, ax=ax)


def get_iv_plot_data(measurements: Collection[IVMeasurement]):
    data = np.array([value.get_anode_current_value() for value in measurements])
    xs = np.array([measurement.conditions.chip.x_coordinate for measurement in measurements])
    ys = np.array([measurement.conditions.chip.y_coordinate for measurement in measurements])
    return data, xs, ys


def get_cv_plot_data(measurements: Collection[CVMeasurement]):
    data = np.array([value.capacitance for value in measurements])
    xs = np.array([measurement.chip.x_coordinate for measurement in measurements])
    ys = np.array([measurement.chip.y_coordinate for measurement in measurements])
    return data, xs, ys


def plot_data(
    values: Collection[Union[IVMeasurement, CVMeasurement]],
    voltages: Collection[Decimal],
    quantile: tuple[float, float],
    thresholds: dict[Decimal, float],
) -> (Figure, ndarray[Any, Axes]):
    # enable failure map mode if quantile is [0, 0] (red/green based on thresholds)
    failure_map = np.isclose(quantile, [0, 0], atol=1e-5).all()
    
    cols_num = 1 if failure_map else 2
    fig, axes = plt.subplots(
        nrows=len(voltages),
        ncols=cols_num,
        figsize=(5 * cols_num, 5 * len(voltages)),
        gridspec_kw={
            "left": 0.1,
            "right": 0.95,
            "bottom": 0.05,
            "top": 0.95,
            "wspace": 0.3,
            "hspace": 0.35,
        },
    )
    axes = axes.reshape(-1, cols_num)

    with click.progressbar(tuple(enumerate(sorted(voltages))), label="Plotting...") as progress:
        for i, voltage in progress:
            target_values = [value for value in values if value.voltage_input == voltage]
            if len(target_values) == 0:
                continue
            if isinstance(target_values[0], IVMeasurement):
                data, xs, ys = get_iv_plot_data(target_values)
            elif isinstance(target_values[0], CVMeasurement):
                data, xs, ys = get_cv_plot_data(target_values)
            else:
                raise RuntimeError("Unknown object type was provided")

            axes[i][0].set_title(f"{voltage}V")

            if failure_map:
                if voltage not in thresholds:
                    click.get_current_context().obj["logger"].warning(
                        f"Thresholds for {voltage}V are not found. Skipping."
                    )
                    continue
                clipped_data = data > thresholds[voltage]
                lower_bound, upper_bound = -1, 1.2
                plot_heat_map(axes[i][0], clipped_data, xs, ys, lower_bound, upper_bound)
            else:
                axes[i][1].set_title(f"{voltage}V")
                lower_bound, upper_bound = np.quantile(data, quantile)
                clipped_data = np.clip(data, lower_bound, upper_bound)
                plot_hist(axes[i][0], clipped_data)
                plot_heat_map(axes[i][1], clipped_data, xs, ys, lower_bound, upper_bound)
    return fig, axes
