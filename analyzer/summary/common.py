import re
import decimal
from decimal import Decimal
from time import (
    localtime,
    strftime,
)
from typing import (
    Iterable,
    Mapping,
    Sequence,
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
    SimpleChip,
    Wafer,
)
from orm.cv_measurement import is_cv_measurements
from orm.iv_measurement import is_iv_measurements

date_formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
date_formats_help = f"Supported formats are: {', '.join((strftime(f) for f in date_formats))}."


@pass_analyzer_context
def get_slice_by_voltages(
    ctx: AnalyzerContext,
    df: pd.DataFrame,
    voltages: Iterable[Decimal]
) -> pd.DataFrame:
    """
    Extract a slice of the DataFrame based on the specified voltages.
    
    :param ctx: The context object (provided by the click decorator).
    :param df: The DataFrame containing the data to be sliced.
    :param voltages: The voltages to be included in the slice.
    :return:
    """
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
    """
    Apply conditional formatting to an Excel sheet based on specified rules and thresholds.
    :param sheet: The Excel worksheet to which the conditional formatting will be applied.
    :param rules: A dictionary mapping rule names to their corresponding fill styles.
    :param thresholds: A dictionary mapping chip types to their voltage thresholds.
    :return:
    """
    chip_row_index = [(i + 1, cell.value) for i, cell in enumerate(sheet["A"]) if cell.value]
    header_row: tuple[Cell, ...] = sheet["1"]
    
    for chip_type, chip_type_thresholds in thresholds.items():
        def is_current_type(chip_name: str) -> bool:
            prefix = re.match(r'^[A-Za-z]+', chip_name)
            return chip_type == prefix.group(0)
          # Old version below that checks only the first letter of chip name
          # This is a problem when chip type has 2 letters because it may
          # end up using acceptance limits of another chip type with same first letter
          #  return chip_name.startswith(chip_type)
        
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
    """
    Generate a summary of information for a given wafer, chip states, and measurements.

    :param wafer:
    :param chip_states:
    :param measurements:
    :return:
    """
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


def plot_grid(
    ax: Axes,
    colors: np.ndarray,
    rectangles: Iterable[tuple[float, float, float, float] | None],
    cmap: Colormap,
):
    """
    Plot a grid of rectangles with colors based on the provided data.
    :param ax: Axes object to plot the grid.
    :param colors: 1d numpy array containing the colors to be used for the rectangles.
    :param rectangles: A sequence of tuples containing the x, y, width, and height of the rectangles.
    :param cmap: The colormap to be used for the colors.
    """
    for rect, v in zip(rectangles, colors, strict=True):
        if rect is None:
            continue
        x, y, w, h = rect
        rect = Rectangle(
            (x, y), w, h,
            linewidth=0.5,
            edgecolor=(0, 0, 0, 0.5),
            facecolor=cmap(v)
        )
        ax.add_patch(rect)
    ax.relim()
    ax.autoscale_view()
    
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=0))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=0))
    ax.set_ylabel("Y coordinate")
    ax.set_xlabel("X coordinate")
    ax.invert_yaxis()


@pass_analyzer_context
def get_chip_rectangles(ctx: AnalyzerContext, chips: Sequence[SimpleChip]):
    """
    Generate a sequence of chip rectangles based on the provided chips.
    :param ctx: The context object (provided by the click decorator).
    :param chips: A sequence of chip objects.
    :return:
    """
    for chip in chips:
        try:
            yield chip.x_coordinate, chip.y_coordinate, chip.width, chip.height
        except (AttributeError, ValueError) as e:
            ctx.logger.warning(f"Failed to get chip rectangle for {chip}. {e}")
            yield None


@pass_analyzer_context
def plot_measurements_by_voltage(
    ctx: AnalyzerContext,
    values: Sequence[IVMeasurement] | Sequence[CVMeasurement],
    voltages: Sequence[Decimal],
    quantile: tuple[float, float],
    thresholds: dict[Decimal, float],
) -> (Figure, Sequence[Sequence[Axes]]):
    """
    Plot data for IV or CV measurements across different voltages.
    :param ctx: The context object (provided by the click decorator).
    :param values: A sequence of IV or CV measurement objects.
    :param voltages: A sequence of voltages to plot.
    :param quantile: A tuple representing the lower and upper quantiles for data clipping.
    :param thresholds: A dictionary mapping voltages to threshold values for failure map mode.
                       Used only if quantile is [0, 0].
    :return: A tuple containing the figure and 2d axes array.
    """
    failure_map = quantile == (0, 0)
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
            target_measurements = [m for m in values if m.voltage_input == voltage]
            if len(target_measurements) == 0:
                continue
            
            if is_iv_measurements(target_measurements):
                chips = [measurement.conditions.chip for measurement in target_measurements]
                data = np.array([value.get_anode_current_value() for value in target_measurements])
                
                hist_xlabel = 'Anode current [pA]'
            elif is_cv_measurements(target_measurements):
                data = np.array([value.capacitance for value in target_measurements])
                chips = [measurement.chip for measurement in target_measurements]
                
                hist_xlabel = 'Capacitance [pF]'
            else:
                raise RuntimeError("Unknown object type was provided")
            
            rectangles = get_chip_rectangles(chips)
            
            if failure_map:
                v_thresholds = thresholds.get(voltage)
                if v_thresholds is None:
                    ctx.logger.warning(f"Thresholds for {voltage}V are not found. Skipping.")
                    continue
                
                plot_failure_map(v_axes[0], data, rectangles, v_thresholds)
            else:
                hist_ax, map_ax = v_axes
                plot_heatmap_and_histogram((hist_ax, map_ax), data, rectangles, quantile)
                hist_ax.set_xlabel(hist_xlabel)
            
            for ax in v_axes:
                ax.set_title(f"{voltage}V")
    
    return fig, axes


def plot_heatmap_and_histogram(
    v_axes: (Axes, Axes),
    data: np.ndarray,
    rectangles: Iterable[tuple[float, float, float, float]],
    quantile: tuple[float, float]
) -> None:
    """
    Plot the heatmap and histogram for IV or CV measurements with clipping based on quantiles.
    
    :param v_axes:  A tuple containing the histogram and heatmap axes.
    :param data: 2d numpy array containing the data to be plotted.
    :param rectangles: A sequence of tuples containing the x, y, width, and height of the chips.
    :param quantile: A tuple representing the lower and upper quantiles for data clipping.
    """
    hist_ax, map_ax = v_axes
    lower_bound, upper_bound = np.quantile(data, quantile)
    clipped_data = np.clip(data, lower_bound, upper_bound)
    
    # Plot histogram
    hist_ax.hist(clipped_data * 1e12, bins=15)
    hist_ax.set_ylabel("Number of chips")
    
    # Adjust the upper bound for better color scaling
    upper_bound += (upper_bound - lower_bound) * 0.2
    norm = Normalize(vmin=lower_bound, vmax=upper_bound)
    cmap: Colormap = plt.get_cmap('hot')
    
    # Normalize colors and plot the heatmap
    colors = norm(clipped_data)
    plot_grid(map_ax, colors, rectangles, cmap)
    
    # Add colorbar
    hist_ax.figure.colorbar(plt.cm.ScalarMappable(cmap=cmap, norm=norm), ax=hist_ax)


def plot_failure_map(
    ax: Axes,
    data: np.ndarray,
    rectangles: Iterable[tuple[float, float, float, float]],
    threshold: float,
) -> None:
    """
    Plot a failure map based on the provided threshold.
    :param ax: Axes object to plot the failure map.
    :param data: 2d numpy array containing the data to be plotted.
    :param rectangles: A sequence of tuples containing the x, y, width, and height of the chips.
    :param threshold: The threshold value for the failure map.
    :return:
    """
    colors = (data > threshold).astype(np.float32)
    cmap = ListedColormap(["#ff3030", "#30ff30"], "red_green")
    
    # Plot the failure map with red/green based on thresholds
    plot_grid(ax, colors, rectangles, cmap)
    
    # Add legend to indicate "Failure" and "Success"
    ax.legend(
        handles=[
            mpatches.Patch(color=cmap(0), label="Failure"),
            mpatches.Patch(color=cmap(1), label="Success"),
        ],
        loc="best",
    )
