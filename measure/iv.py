from time import sleep
from typing import cast

import click
import numpy as np

from orm import (
    AbstractChip,
    ChipRepository,
    ChipState,
    IVMeasurement,
    InstrumentRepository,
    IvConditionsRepository,
    Matrix,
    MatrixRepository,
)
from utils import (
    EntityOption,
)
from .common import (
    apply_configs,
    get_raw_measurements,
    preprocess_measurements,
    validate_chip_names,
    validate_measurements,
)
from .context import (
    MeasureContext,
    from_config,
    pass_measure_context,
)
from .exceptions import InvalidMeasurementError
from .instrument import (
    PyVisaInstrument,
    TemperatureInstrument,
)


@click.command(name="iv")
@from_config("instruments.main.name")
@pass_measure_context
@click.option("-n",
              "--chip-name",
              "chip_names",
              help="Chip name.",
              multiple=True,
              callback=validate_chip_names)
@click.option("-w", "--wafer", "wafer_name", prompt="Input wafer name", help="Wafer name.")
@click.option(
    "-s",
    "--chip-state",
    "chip_state",
    prompt="Input chip state",
    help="State of the chips.",
    cls=EntityOption,
    entity_type=ChipState,
)
@click.option(
    "--auto",
    "automatic",
    is_flag=True,
    help="Automatic measurement mode. Invalid measurements will be skipped.",
)
def measure_iv_command(
    ctx: MeasureContext,
    instrument_name: str,
    chip_names: tuple[str, ...],
    wafer_name: str,
    chip_state: ChipState,
    automatic: bool,
):
    """
    Measure IV characteristics of the chips.
    """
    instrument_id = InstrumentRepository(ctx.session).get_id(name=instrument_name)
    if (matrix_config := ctx.configs.get("matrix")) is not None:
        matrix = MatrixRepository(ctx.session).get_or_create_from_configs(
            matrix_name=chip_names[0], wafer_name=wafer_name, matrix_config=matrix_config
        )
        ctx.session.add(matrix)
    else:
        chips = ChipRepository(ctx.session).get_or_create_chips_for_wafer(chip_names, wafer_name)
        ctx.session.add_all(chips)
    ctx.session.commit()
    
    for setup_config in ctx.configs["setups"]:
        ctx.logger.info(f'Executing setup {setup_config["name"]}')
        apply_configs(setup_config["instrument"])
        conditions_kwargs = {
            "instrument_id": instrument_id,
            "chip_state_id": chip_state.id,
            **setup_config["program"]["condition_kwargs"]
        }
        
        if (matrix := locals().get('matrix')) is not None:
            measure_matrix(matrix, automatic, setup_config, conditions_kwargs)
        else:
            measure_setup(automatic, chips, setup_config, conditions_kwargs)
    ctx.session.commit()
    ctx.logger.info("Measurements saved")


@pass_measure_context
def measure_matrix(
    ctx: MeasureContext,
    matrix: Matrix,
    automatic: bool,
    setup_config: dict,
    conditions_kwargs,
):
    """
    Measure IV characteristics for a matrix of pixels (saved as different chips).
    
    :param ctx: The context object (provided by the click decorator).
    :param matrix: The matrix object containing the chips to be measured.
    :param automatic: Flag to enable automatic measurement mode
    :param setup_config: `setup` section of the config file
    :param conditions_kwargs: Additional keyword arguments for the measurement conditions.
    :return:
    """
    scanner = cast(PyVisaInstrument, ctx.instruments["scanner"])
    scanner.write("RX")  # open all channels
    chips = sorted(matrix.chips, key=lambda c: c.name)
    for i, chip in enumerate(chips, start=1):
        scanner.write(f"B{i}C{i}X")  # close and display channel
        sleep(0.1)  # wait for the channel to open
        
        try:
            measure_setup(automatic, [chip], setup_config, conditions_kwargs)
        except InvalidMeasurementError:
            if automatic:
                ...  # do nothing, measure next pixel
            else:
                click.confirm("Do you want to continue measuring other pixels?",
                              abort=True, default=True)
        scanner.write("RX")  # open all channels
        ctx.session.commit()  # commit after each chip


@from_config("chips")
@pass_measure_context
def measure_setup(
    ctx: MeasureContext,
    chip_configs: dict,
    automatic: bool,
    chips: list[AbstractChip],
    setup_config: dict,
    conditions_kwargs: dict,
):
    """
    Measure IV characteristics for a given setup configuration and chips.
    
    :param ctx: The context object (provided by the click decorator).
    :param chip_configs: Configuration for each measured chip, maps measurements to the properties
        of IVMeasurement entry. Provided by the config file.
    :param automatic: Flag to enable automatic measurement mode
    :param chips: List of chips to be linked with the ongoing measurements
    :param setup_config: `setup` section of the config file, containing the instrument configuration
    :param conditions_kwargs: Additional keyword arguments for the measurement conditions.
    :return:
    """
    thermometer = cast(TemperatureInstrument, ctx.instruments["temperature"])
    temperature = thermometer.get_temperature()
    ctx.logger.info(f"Temperature: {temperature}°C")
    validate_temperature(temperature, automatic)
    
    ctx.logger.info(f"Measuring {', '.join([c.name for c in chips])}")
    if (minimization_config := setup_config["program"].get("minimum")) is not None:
        raw_measurements = get_minimal_measurements(minimization_config)
    else:
        raw_measurements = get_raw_measurements()
    
    iv_cond_repo = IvConditionsRepository(ctx.session)
    for chip, chip_config in zip(chips, chip_configs, strict=True):
        measurements_dict = preprocess_measurements(raw_measurements, chip_config)
        validate_measurements(measurements_dict, setup_config, automatic)
        iv_conditions = iv_cond_repo.create(
            chip=chip, temperature=temperature, **conditions_kwargs,
            measurements=create_measurements(measurements_dict, temperature),
        )
        ctx.session.add(iv_conditions)


@from_config("instruments.main")
def create_measurements(
    instrument_config: dict,
    measurements_dict: dict[str, list[float]],
    temperature: float,
) -> list[IVMeasurement]:
    """
    Create a list of IVMeasurement objects from preprocessed measurement data.
    
    :param instrument_config: Configuration for the main instrument. Provided by the config file.
    :param measurements_dict: Preprocessed measurements data
    :param temperature: The temperature during measurement
    :return:
    """
    measurements = []
    
    for values in zip(*measurements_dict.values(), strict=True):
        data = dict(zip(measurements_dict.keys(), values, strict=True))
        
        if (anode_current := data.get("anode_current")) is not None:
            data["anode_current_corrected"] = compute_corrected_current(temperature, anode_current)
        
        if instrument_config.get("invert_voltage", False):
            data["voltage_input"] *= -1
        
        measurements.append(IVMeasurement(**data))
    return measurements


def get_minimal_measurements(config: dict):
    """
    Repeatedly measure the IV characteristics until the offset of the linear fit is minimized.
    
    :param config: Configuration for the minimization process, containing the x and y values to be measured
    :return:
    """
    x, y, timeout = config["x"], config["y"], config["timeout"]
    prev_measurements = {}
    while True:
        raw_measurements = get_raw_measurements()
        xdata = raw_measurements[x]
        ydata = raw_measurements[y]
        
        slope, offset = np.polyfit(xdata, ydata, 1)
        if prev_measurements and abs(offset) >= prev_measurements["offset"]:
            prev_measurements.pop("offset")
            return prev_measurements
        prev_measurements = dict(offset=abs(offset), **raw_measurements)
        sleep(timeout)


def compute_corrected_current(temp: float, current: float):
    target_temperature = 25
    return 1.15 ** (target_temperature - temp) * current


@pass_measure_context
def validate_temperature(ctx: MeasureContext, temperature: float, automatic: bool):
    if 18 <= temperature <= 30:
        return True
    
    if temperature < 0:
        raise click.Abort(
            f"Temperature value is too low. temp: {temperature:.2f}. Check sensor connection!"
        )
    
    ctx.logger.warning(
        f"Current temperature is too {'low' if temperature < 18 else 'high'}. temp: {temperature:.2f}"
    )
    if not automatic:
        confirm = click.confirm("Do you want to continue?")
        if not confirm:
            raise click.Abort()
