import logging
from time import sleep

import click
import numpy as np
from sqlalchemy.orm import Session

from orm import (
    ChipState,
    IVMeasurement,
    Instrument,
    IvConditions,
)
from utils import (
    EntityOption,
    from_context,
)
from .common import (
    get_chips_for_names,
    get_raw_measurements,
    set_configs,
    validate_measurements,
)
from .instrument import (
    PyVisaInstrument,
    TemperatureInstrument,
)


@click.command(name="iv", help="Measure IV data of the current chip.")
@click.option("-n", "--chip-name", "chip_names", help="Chip name.", multiple=True)
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
@from_context("configs.instruments.main.name", "instrument_name")
@from_context("session", "session")
@from_context("logger", "logger")
@from_context("configs", "configs")
def measure_iv_command(
    chip_names: tuple[str],
    wafer_name: str,
    chip_state: ChipState,
    automatic: bool,
    instrument_name: str,
    session: Session,
    logger: logging.Logger,
    configs: dict,
):
    instrument_id, = (
        session.query(Instrument.id)
        .filter(Instrument.name == instrument_name)
        .first()
    )
    
    chips = get_chips_for_names(chip_names, wafer_name, len(configs["chips"]), session)
    
    for setup_config in configs["setups"]:
        logger.info(f'Executing measurement {setup_config["name"]}')
        set_configs(setup_config["instrument"])
        conditions_kwargs = {
            "instrument_id": instrument_id,
            "chip_state_id": chip_state.id,
            **setup_config["program"]["condition_kwargs"]
        }
        
        if "matrix" in configs:
            measure_matrix(automatic, chips, setup_config, conditions_kwargs)
        else:
            measure_setup(automatic, chips, setup_config, conditions_kwargs)
    session.commit()
    logger.info("Measurements saved")


@from_context("instruments.scanner", "scanner")
@from_context("configs.matrix", "matrix_config")
def measure_matrix(*measure_args, scanner: PyVisaInstrument, matrix_config):
    scanner.write("RX")  # open all channels
    
    for i in np.arange(matrix_config["start"], matrix_config["stop"]):
        scanner.write(f"B{i}C{i}X")  # close and display channel
        sleep(0.1)  # wait for the channel to open, just in case
        measure_setup(*measure_args)
        scanner.write("RX")  # open all channels


@from_context("instruments.temperature", "thermometer")
@from_context("session", "session")
@from_context("configs.chips", "chip_configs")
def measure_setup(
    automatic,
    chips,
    setup_config,
    conditions_kwargs,
    chip_configs,
    session: Session,
    thermometer: TemperatureInstrument,
):
    temperature = thermometer.get_temperature()
    validate_temperature(temperature, automatic)
    
    if setup_config["program"].get("minimum", False):
        raw_measurements = get_minimal_measurements()
    else:
        raw_measurements = get_raw_measurements()
    validate_measurements(raw_measurements, setup_config, automatic)
    
    for chip, chip_config in zip(chips, chip_configs, strict=True):
        conditions = IvConditions(chip=chip, temperature=temperature, **conditions_kwargs)
        conditions.measurements = create_measurements(
            raw_measurements, temperature, chip_config,
        )
        session.add(conditions)  # thus, chip/wafer etc will be added to session indirectly


@from_context("configs.instruments.main", "instrument_config")
def create_measurements(
    raw_measurements: dict[str, list[float]],
    temperature: float,
    chip_config: dict,
    instrument_config: dict,
) -> list[IVMeasurement]:
    kwarg_keys = list(chip_config.keys())
    raw_numbers = zip(*[raw_measurements[chip_config[key]] for key in kwarg_keys], strict=True)
    measurements = []
    
    for data in raw_numbers:
        measurement_kwargs = dict(zip(kwarg_keys, data))
        
        if "anode_current" in measurement_kwargs:
            anode_current = measurement_kwargs["anode_current"]
            anode_current_corrected = compute_corrected_current(temperature, anode_current)
            measurement_kwargs["anode_current_corrected"] = anode_current_corrected
        
        if instrument_config.get("invert_voltage", False):
            measurement_kwargs["voltage_input"] *= -1
        
        # measurements.append(IVMeasurement(**measurement_kwargs))
        m = IVMeasurement(**measurement_kwargs)
        measurements.append(m)
    return measurements


def get_minimal_measurements():
    prev_measurements: dict[str, list] = dict()
    while True:
        raw_measurements = get_raw_measurements()
        xdata = raw_measurements["voltage_input"]
        if "anode_current" in raw_measurements:
            ydata = raw_measurements["anode_current"]
        elif "cathode_current" in raw_measurements:
            ydata = raw_measurements["cathode_current"]
        else:
            raise ValueError("No current measurement found")
        slope, offset = np.polyfit(xdata, ydata, 1)
        if prev_measurements and abs(offset) >= prev_measurements["offset"]:
            prev_measurements.pop("offset")
            return prev_measurements
        prev_measurements = dict(offset=abs(offset), **raw_measurements)
        sleep(0.5)


def compute_corrected_current(temp: float, current: float):
    target_temperature = 25
    return 1.15 ** (target_temperature - temp) * current


@from_context("logger", "logger")
def validate_temperature(temperature, automatic, logger):
    if 18 <= temperature <= 30:
        return True
    
    if temperature < 0:
        logger.error(
            f"Temperature value is too low. temp: {temperature:.2f}. Check sensor connection!"
        )
        raise click.Abort(
            f"Temperature value is too low. temp: {temperature:.2f}. Check sensor connection!"
        )
    
    logger.warning(
        f"Current temperature is too {'low' if temperature < 18 else 'high'}. temp: {temperature:.2f}"
    )
    if not automatic:
        confirm = click.confirm("Do you want to continue?")
        if not confirm:
            raise click.Abort()
