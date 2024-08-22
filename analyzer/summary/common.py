import decimal
from decimal import Decimal
from time import (
    localtime,
    strftime,
)
from typing import (
    Any,
    Collection,
    Iterable,
    Mapping,
    Sequence,
    TypeGuard,
    cast,
)

import click
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.colors import (
    Colormap,
    ListedColormap,
    Normalize,
)
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator
from openpyxl.cell import Cell
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Fill
from openpyxl.worksheet.worksheet import Worksheet

from analyzer.context import (
    AnalyzerContext,
    pass_analyzer_context,
)
from orm import (
    CVMeasurement,
    ChipState,
    IVMeasurement,
    Wafer,
)

date_formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
date_formats_help = f"Supported formats are: {', '.join((strftime(f) for f in date_formats))}."


@pass_analyzer_context
def get_slice_by_voltages(
    ctx: AnalyzerContext,
    df: pd.DataFrame,
    voltages: Iterable[Decimal]
) -> pd.DataFrame:
    columns = sorted(voltages)
    slice_df = cast(pd.DataFrame, df[df.columns.intersection(columns)].copy())
    
    empty_cols = cast(pd.Series, slice_df.isna().all(axis=0))
    if empty_cols.any():
        ctx.logger.warning(
            "The following voltages are not present in the data: %s.",
            [float(cast(Decimal, col)) for col, val in empty_cols.items() if val]
        )
    slice_df.dropna(axis=1, how="all", inplace=True)
    return slice_df


def get_voltage_column_cell(header_row: tuple[Cell, ...], v: Decimal) -> Cell:
    for cell in header_row:
        try:
            if Decimal(cast(str, cell.value)) == v:
                return cell
        except (ValueError, TypeError, decimal.DecimalException):
            pass
    raise StopIteration


def apply_conditional_formatting(
    sheet: Worksheet,
    rules: Mapping[str, Fill],
    thresholds: Mapping[str, Mapping[Decimal, float]],
):
    chip_row_index = [(i + 1, cell.value) for i, cell in enumerate(sheet["A"]) if cell.value]
    header_row: tuple[Cell, ...] = sheet["1"]
    
    for chip_type, chip_type_thresholds in thresholds.items():
        def is_current_type(chip_name: str) -> bool:
            return chip_name.startswith(chip_type)
        
        for voltage, threshold in chip_type_thresholds.items():
            try:
                column_cell = get_voltage_column_cell(header_row, voltage)
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
    measurements: list[IVMeasurement] | list[CVMeasurement],
) -> pd.Series:
    format_date = strftime("%A, %d %b %Y", localtime())
    chip_states_str = "; ".join([state.name for state in chip_states])
    
    first_measurement_date = min(map(lambda m: m.datetime, measurements))
    last_measurement_date = max(map(lambda m: m.datetime, measurements))
    
    return pd.Series(
        {
            "Wafer": wafer.name,
            "Summary generation date": format_date,
            "Chip state": chip_states_str,
            "First measurement date": first_measurement_date,
            "Last measurement date": last_measurement_date,
            "Number of measurements": len(measurements),
        }
    )


def plot_hist(ax: Axes, data: np.ndarray):
    ax.set_ylabel("Number of chips")
    ax.hist(data * 1e12, bins=15)


def plot_map(
    ax: Axes,
    colors: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    widths: np.ndarray,
    heights: np.ndarray,
    cmap: Colormap,
):
    for x, y, w, h, v in zip(xs, ys, widths, heights, colors):
        rect = Rectangle(
            (x, y), w, h,
            linewidth=0.5,
            edgecolor=(0, 0, 0, 0.5),
            facecolor=cmap(v)
        )
        ax.add_patch(rect)
    
    ax.set_xlim(xs.min() - 0.5, (xs + widths).max() + 0.5)
    ax.set_ylim(ys.min() - 0.5, (ys + heights).max() + 0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=0))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=0))
    ax.set_ylabel("Y coordinate")
    ax.set_xlabel("X coordinate")
    ax.invert_yaxis()


def get_iv_plot_data(measurements: Collection[IVMeasurement]):
    data = np.array([value.get_anode_current_value() for value in measurements])
    chips = [measurement.conditions.chip for measurement in measurements]
    xs = np.array([chip.x_coordinate for chip in chips])
    ys = np.array([chip.y_coordinate for chip in chips])
    widths = np.array([chip.width for chip in chips])
    heights = np.array([chip.height for chip in chips])
    return data, xs, ys, widths, heights


def get_cv_plot_data(measurements: Collection[CVMeasurement]):
    data = np.array([value.capacitance for value in measurements])
    xs = np.array([measurement.chip.x_coordinate for measurement in measurements])
    ys = np.array([measurement.chip.y_coordinate for measurement in measurements])
    return data, xs, ys


def is_iv_measurements(value: Sequence[Any]) -> TypeGuard[Sequence[IVMeasurement]]:
    return isinstance(value[0], IVMeasurement)


def is_cv_measurements(value: Sequence[Any]) -> TypeGuard[Sequence[CVMeasurement]]:
    return isinstance(value[0], CVMeasurement)


def plot_data(
    values: Sequence[IVMeasurement] | Sequence[CVMeasurement],
    voltages: Sequence[Decimal],
    quantile: tuple[float, float],
    thresholds: dict[Decimal, float],
) -> tuple[Figure, Sequence[Sequence[Axes]]]:
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
    
    with click.progressbar(
        zip(axes, sorted(voltages), strict=True), label="Plotting...", length=len(voltages)
    ) as progress:
        for v_axes, voltage in progress:
            target_values = [value for value in values if value.voltage_input == voltage]
            if len(target_values) == 0:
                continue
            if is_iv_measurements(target_values):
                data, xs, ys, widths, heights = get_iv_plot_data(target_values)
                hist_xlabel = 'Anode current [pA]'
            elif is_cv_measurements(target_values):
                data, xs, ys = get_cv_plot_data(target_values)
                hist_xlabel = 'Capacitance [pF]'
            else:
                raise RuntimeError("Unknown object type was provided")
            
            for ax in v_axes:
                ax.set_title(f"{voltage}V")
            
            if failure_map:
                if voltage not in thresholds:
                    click.get_current_context().obj.logger.warning(
                        f"Thresholds for {voltage}V are not found. Skipping."
                    )
                    continue
                
                map_ax = v_axes[0]
                colors = (data > thresholds[voltage]).astype(np.float32)
                cmap = ListedColormap(["#ff3030", "#30ff30"], "red_green")
                plot_map(map_ax, colors, xs, ys, widths, heights, cmap)
                map_ax.legend(
                    handles=[
                        mpatches.Patch(color=cmap(0), label="Failure"),
                        mpatches.Patch(color=cmap(1), label="Success"),
                    ],
                    loc="best",
                )
            else:
                hist_ax, map_ax = v_axes
                lower_bound, upper_bound = np.quantile(data, quantile)
                clipped_data = np.clip(data, lower_bound, upper_bound)
                plot_hist(hist_ax, clipped_data)
                hist_ax.set_xlabel(hist_xlabel)
                # increase upper bound so the highest level does not look white on hot cmap
                upper_bound += (upper_bound - lower_bound) * 0.2
                
                norm = Normalize(vmin=lower_bound, vmax=upper_bound)
                cmap: Colormap = plt.get_cmap('hot')
                colors = cmap(norm(clipped_data))
                plot_map(map_ax, colors, xs, ys, widths, heights, cmap)
                ax.figure.colorbar(plt.cm.ScalarMappable(cmap=cmap, norm=norm), ax=ax)
    
    return fig, axes
