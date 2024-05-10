from typing import (
    Optional,
    Sequence,
    cast,
)

import click
import pyvisa
import pandas as pd
from jsonpath_ng import parse
from pyvisa.constants import VI_ERROR_TMO

from .context import (
    MeasureContext,
    from_config,
    pass_measure_context,
)
from .exceptions import InvalidMeasurementError
from .instrument import PyVisaInstrument


@pass_measure_context
def apply_configs(ctx: MeasureContext, commands: list[str]):
    instrument: PyVisaInstrument = cast(PyVisaInstrument, ctx.instruments["main"])
    for command in commands:
        instrument.write(command)


def execute_command(
    instrument: PyVisaInstrument,
    command: str,
    command_type: str
):
    command_types = {
        "write": instrument.write,
        "query": instrument.query,
        "query_ascii_values": instrument.query_ascii_values,
        "query_csv_values": lambda cmd: [float(value) for value in instrument.query(cmd).split(",")]
    }
    
    if command_type not in command_types:
        raise click.BadParameter(f"Invalid command type \"{command_type}\".")
    
    try:
        return command_types[command_type](command)
    except pyvisa.VisaIOError as e:
        advice = ""
        if e.error_code == VI_ERROR_TMO:
            advice = ("\nTry to increase `kwargs.timeout`, `smub.measure.delay` or "
                      "`trigger.timer[1].delay` in the config file.")
        
        raise RuntimeError(f"PyVisaError: {e}{advice}")


@from_config("measure")
@pass_measure_context
def get_raw_measurements(ctx: MeasureContext, commands: list[dict]) -> dict[str, list]:
    instrument: PyVisaInstrument = cast(PyVisaInstrument, ctx.instruments["main"])
    measurements: dict[str, list] = {}
    for command in commands:
        value = execute_command(instrument, command["command"], command["type"])
        if "name" in command:
            measurements[command["name"]] = value
    return measurements


@pass_measure_context
def validate_measurements(
    ctx: MeasureContext,
    raw_measurements,
    config: dict,
    automatic_mode: bool
):
    validation_config = config["program"].get("validation")
    if not validation_config:
        return
    
    error_msg = do_validation(raw_measurements, validation_config)
    if error_msg is None:
        return
    
    ctx.logger.warning("%s\n%s", error_msg, pd.DataFrame(raw_measurements).to_string(
        index=False, float_format="%.2e",
    ))
    if automatic_mode:
        raise InvalidMeasurementError()
    
    click.confirm(
        "Do you want to save these measurements?",
        abort=True, default=True, err=True)


def do_validation(measurements: dict[str, list], rules: dict) -> Optional[str]:
    for value_name, config in rules.items():
        for validator_name, rules in config.items():
            path = parse(value_name)
            values = path.find(measurements)
            if not values:
                raise click.BadParameter(
                    f"Value \"{value_name}\" not found in measurements, but it is required for validation.")
            if len(values) > 1:
                raise click.BadParameter(f"Value \"{value_name}\" is ambiguous in measurements.")
            value = values[0].value
            if rules.get("abs"):
                value = abs(value)
            if validator_name == "min":
                if value < rules["value"]:
                    return rules["message"]
            elif validator_name == "max":
                if value > rules["value"]:
                    return rules["message"]
            else:
                raise click.BadParameter(f"Unknown validator format in \"{validator_name}\"")
    return None


def validate_chip_names(ctx: click.Context, param: click.Parameter, chip_names: Sequence[str]):
    configs = ctx.find_object(MeasureContext).configs
    chip_names = [name.upper() for name in chip_names]
    base_error_msg = f"{param.opts[0]} parameter is invalid. %s"
    
    if "matrix" in configs:
        if len(chip_names) != 1:
            raise click.BadParameter("Matrix measurement requires exactly one chip name")
    else:
        if len(set(chip_names)) != len(chip_names):
            raise click.BadParameter(base_error_msg % "Chip names must be unique.")
        expected_chips_number = len(configs["chips"])
        if len(chip_names) != expected_chips_number:
            raise click.BadParameter(base_error_msg % f"{expected_chips_number} chip names expected, based on provided config file.")
    
    return tuple(chip_names)


def preprocess_measurements(
    raw_measurements: dict[str, list], chip_config: dict
) -> dict[str, list]:
    measurements_dict = {}
    
    for prop_name, prop_config in chip_config.items():
        if not prop_config:
            measurements_dict[prop_name] = raw_measurements[prop_name]
        elif isinstance(prop_config, str):
            measurements_dict[prop_name] = raw_measurements[prop_config]
        elif isinstance(prop_config, dict):
            try:
                p, s = prop_config["prop"], slice(*prop_config["slice"])
            except KeyError:
                raise click.BadParameter(f"""Invalid chip config for property "{prop_name}".
                    \rExpected a string, a dict with 'prop' and 'slice' keys, or None.""")
            measurements_dict[prop_name] = raw_measurements[p][s]
    
    return measurements_dict
