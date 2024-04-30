from time import sleep

import click
import numpy as np

from orm import (
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
    validate_chip_names,
    validate_measurements,
)
from .context import (
    MeasureContext,
    from_config,
    pass_measure_context,
)
from .instrument import (
    PyVisaInstrument,
    TemperatureInstrument,
)


@click.command(name="iv", help="Measure IV data of the current chip.")
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
@from_config("instruments.main.name", "instrument_name")
def measure_iv_command(
    ctx: MeasureContext,
    chip_names: tuple[str, ...],
    wafer_name: str,
    chip_state: ChipState,
    automatic: bool,
    instrument_name: str,
):
    instrument_id = InstrumentRepository(ctx.session).get_id(name=instrument_name)
    if (matrix_config := ctx.configs.get("matrix")) is not None:
        matrix = MatrixRepository(ctx.session).get_or_create_from_configs(
            matrix_name=chip_names[0], wafer_name=wafer_name, matrix_config=matrix_config
        )
    else:
        chips = ChipRepository(ctx.session).get_or_create_chips_for_wafer(chip_names, wafer_name)
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
    automatic,
    setup_config,
    conditions_kwargs,
):
    scanner: PyVisaInstrument = ctx.instruments["scanner"]
    scanner.write("RX")  # open all channels
    chips = sorted(matrix.chips, key=lambda c: c.name)
    for i, chip in enumerate(chips, start=1):
        scanner.write(f"B{i}C{i}X")  # close and display channel
        sleep(0.1)  # wait for the channel to open
        
        try:
            measure_setup(automatic, [chip], setup_config, conditions_kwargs)
        except RuntimeError as e:
            if str(e) == "Measurement is invalid":
                if automatic:
                    ...  # do nothing, measure next pixel
                else:
                    click.confirm(
                        "Do you want to continue measuring other pixels?", abort=True, default=True)
        scanner.write("RX")  # open all channels
        ctx.session.commit()  # commit after each chip


@pass_measure_context
@from_config("chips", "chip_configs")
def measure_setup(
    ctx: MeasureContext,
    automatic: bool,
    chips,
    setup_config,
    conditions_kwargs,
    /,
    chip_configs,
):
    thermometer: TemperatureInstrument = ctx.instruments["temperature"]
    temperature = thermometer.get_temperature()
    validate_temperature(temperature, automatic)
    
    ctx.logger.info(f"Measuring {', '.join([c.name for c in chips])}")
    if setup_config["program"].get("minimum", False):
        raw_measurements = get_minimal_measurements()
    else:
        raw_measurements = get_raw_measurements()
    validate_measurements(raw_measurements, setup_config, automatic)
    
    iv_cond_repo = IvConditionsRepository(ctx.session)
    for chip, chip_config in zip(chips, chip_configs, strict=True):
        iv_conditions = iv_cond_repo.create(
            chip=chip, temperature=temperature, **conditions_kwargs,
            measurements=create_measurements(raw_measurements, temperature, chip_config),
        )
        ctx.session.add(iv_conditions)


@from_config("instruments.main", "instrument_config")
def create_measurements(
    raw_measurements: dict[str, list[float]],
    temperature: float,
    chip_config: dict,
    /,
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
        
        measurements.append(IVMeasurement(**measurement_kwargs))
    return measurements


def get_minimal_measurements():
    prev_measurements = {}
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
