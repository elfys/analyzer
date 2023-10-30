import pprint
from random import random
from time import sleep

import click
import numpy as np
from pyvisa.resources import GPIBInstrument
from scipy.optimize import curve_fit
from sqlalchemy.orm import Session, joinedload
from yoctopuce.yocto_temperature import YAPI, YRefParam, YTemperature

from orm import IVMeasurement, IvConditions, Instrument, Wafer, ChipState
from utils import (
    get_or_create_wafer,
    get_or_create_chips,
    EntityOption,
)
from .common import (
    get_raw_measurements,
    set_configs,
    validate_raw_measurements,
)


@click.command(name="iv", help="Measure IV data of the current chip.")
@click.pass_context
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
    "automatic_mode",
    is_flag=True,
    help="Automatic measurement mode. Invalid measurements will be skipped.",
)
def measure_iv(
    ctx: click.Context,
    chip_names: tuple[str],
    wafer_name: str,
    chip_state: ChipState,
    automatic_mode: bool,
):
    instrument: GPIBInstrument = ctx.obj["instrument"]
    session: Session = ctx.obj["session"]
    configs: dict = ctx.obj["configs"]

    if ctx.obj["simulate"]:
        temperature = random() * 10 + 20
    else:
        temperature = get_temperature(configs["instruments"]["temperature_resource"])
    validate_temperature(temperature, ctx)
    instrument_id = (
        session.query(Instrument.id)
        .filter(Instrument.name == configs["instruments"]["pyvisa"]["name"])
        .scalar()
    )

    if len(configs["chips"]) != len(chip_names):
        if len(chip_names) > 0:
            ctx.obj["logger"].warning(
                f"Number of chip names does not match number of chips in config file. {len(configs['chips'])} chip names expected"
            )
        for i in range(len(configs["chips"]) - len(chip_names)):
            chip_name = click.prompt(f"Input chip name {i + 1}", type=str)
            chip_names += (chip_name,)

    wafer = get_or_create_wafer(wafer_name, session=session, query_options=joinedload(Wafer.chips))
    chips = get_or_create_chips(session, wafer, chip_names)

    for measurement_config in configs["measurements"]:
        ctx.obj["logger"].info(f'Executing measurement {measurement_config["name"]}')
        set_configs(instrument, measurement_config["instrument"])

        if measurement_config["program"].get("minimum"):
            raw_measurements = get_minimal_measurements(instrument, configs["measure"])
        else:
            raw_measurements = get_raw_measurements(instrument, configs["measure"])

        if measurement_config["program"].get("validation"):
            validation_config = measurement_config["program"]["validation"]
            error_msg = validate_raw_measurements(raw_measurements, validation_config)
            if error_msg is not None:
                ctx.obj["logger"].warning(error_msg)
                if automatic_mode:
                    raise RuntimeError("Measurement is invalid")
                ctx.obj["logger"].info(
                    "\n" + pprint.pformat(raw_measurements, compact=True, indent=4)
                )
                click.confirm("Do you want to save these measurements?", abort=True, default=True)

        for chip, chip_config in zip(chips, configs["chips"], strict=True):
            conditions = IvConditions(
                chip_state_id=chip_state.id,
                chip=chip,
                temperature=temperature,
                instrument_id=instrument_id,
                **measurement_config["program"]["measurements_kwargs"],
            )
            conditions.measurements = create_measurements(
                raw_measurements, temperature, chip_config, configs
            )
            session.add(conditions)
    session.commit()
    ctx.obj["logger"].info("Measurements saved")


def create_measurements(
    raw_measurements: dict[str, list[float]],
    temperature: float,
    chip_config: dict,
    configs: dict,
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

        if configs["instruments"]["pyvisa"].get("invert_voltage", False):
            measurement_kwargs["voltage_input"] *= -1

        measurements.append(IVMeasurement(**measurement_kwargs))
    return measurements


def get_minimal_measurements(instrument: GPIBInstrument, configs: dict):
    def linear(x, a, b):
        return a + b * x

    prev_measurements: dict[str, list] = dict()
    while True:
        raw_measurements = get_raw_measurements(instrument, configs)
        xdata = raw_measurements["voltage_input"]
        if "anode_current" in raw_measurements:
            ydata = raw_measurements["anode_current"]
        elif "cathode_current" in raw_measurements:
            ydata = raw_measurements["cathode_current"]
        else:
            raise ValueError("No current measurement found")
        popt, pcov = curve_fit(
            f=linear, xdata=xdata, ydata=ydata, p0=[0, 0], bounds=(-np.inf, np.inf)
        )
        offset = abs(popt[0])
        if prev_measurements and offset >= prev_measurements["offset"]:
            prev_measurements.pop("offset")
            return prev_measurements
        prev_measurements = dict(offset=offset, **raw_measurements)
        sleep(0.5)


def compute_corrected_current(temp: float, current: float):
    target_temperature = 25
    return 1.15 ** (target_temperature - temp) * current


def get_temperature(sensor_id) -> float:
    try:
        errmsg = YRefParam()
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            raise RuntimeError("RegisterHub (temperature sensor) error: " + errmsg.value)

        # TODO: does it work with simple 'temperature' instead of sensor_id?
        sensor: YTemperature = YTemperature.FindTemperature(sensor_id)
        if not (sensor.isOnline()):
            raise RuntimeError("Temperature sensor is not connected")

        temperature = sensor.get_currentValue()

    finally:
        YAPI.FreeAPI()
    return temperature


def validate_temperature(temperature, ctx: click.Context):
    if 18 <= temperature <= 30:
        return True

    if temperature < 0:
        ctx.obj["logger"].error(
            f"Temperature value is too low. temp: {temperature:.2f}. Check sensor connection!"
        )
        raise click.Abort(
            f"Temperature value is too low. temp: {temperature:.2f}. Check sensor connection!"
        )

    ctx.obj["logger"].warning(
        f"Current temperature is too {'low' if temperature < 18 else 'high'}. temp: {temperature:.2f}"
    )
    if not ctx.params["automatic_mode"]:
        confirm = click.confirm("Do you want to continue?")
        if not confirm:
            raise click.Abort()
