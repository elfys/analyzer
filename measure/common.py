from typing import (
    Optional,
    Sequence,
    cast,
)

import click
import pandas as pd
import pyvisa
from jsonpath_ng import parse

from .context import (
    MeasureContext,
    from_config,
    pass_measure_context,
)
from .exceptions import InvalidMeasurementError
from .instrument import PyVisaInstrument


@pass_measure_context
def apply_configs(ctx: MeasureContext, commands: list[str]):
    """
    Iteratively execute a list of commands on the main instrument.
    
    :param ctx: The context object (provided by the click decorator).
    :param commands: List of commands to execute.
    :return:
    """
    instrument: PyVisaInstrument = cast(PyVisaInstrument, ctx.instruments["main"])
    for command in commands:
        instrument.write(command)


def execute_command(
    instrument: PyVisaInstrument,
    command: str,
    command_type: str
):
    """
    Execute a command on the given instrument based on the command type.
    :param instrument: The instrument to execute the command on.
    :param command: The command to be executed.
    :param command_type: The type of the command. It can be one of the following:
            - "write": Write the command to the instrument.
            - "query": Query the instrument and return the response.
            - "query_ascii_values": Query the instrument and return the response as ASCII values.
            - "query_csv_values": Query the instrument and return the response as CSV values.
    :return: The result of the command execution, which can be a string or a list of floating values depending on the command type.
    """
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
        instrument.handle_error(e)


@from_config("measure")
@pass_measure_context
def get_raw_measurements(ctx: MeasureContext, commands: list[dict]) -> dict[str, list]:
    """
    Retrieve raw measurement data by executing a list of commands on the main instrument.
    :param ctx:  The context object (provided by the click decorator).
    :param commands: list of commands to execute.
    :return: dict[str, list]: A dictionary containing the measurement data, with keys as specified by the "name" field in the commands.
    """
    instrument: PyVisaInstrument = cast(PyVisaInstrument, ctx.instruments["main"])
    measurements: dict[str, list] = {}
    for command in commands:
        value = execute_command(instrument, command["command"], command["type"])
        if "name" in command:
            if isinstance(value, list):
                measurements[command["name"]] = value
            else:
                raise click.BadParameter(
                    f"Invalid output for command {command['type']}:{command['command']}: {repr(value)}."
                    f"A list of values was expected.")
    return measurements


@pass_measure_context
def validate_measurements(
    ctx: MeasureContext,
    raw_measurements,
    config: dict,
    automatic_mode: bool
):
    """
    Validate raw measurement data based on the provided configuration.
    :param ctx: The context object (provided by the click decorator).
    :param raw_measurements: The raw measurement data to be validated.
    :param config: The configuration dictionary containing validation rules.
    :param automatic_mode: If True, raises an InvalidMeasurementError on validation failure.
    :return:
    """
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
    """
    Validate the provided chip names based on the measurement context configuration.
    The number of chip names must match the expected number of chips based on the configuration.
    :param ctx:
    :param param:
    :param chip_names:
    :return: tuple: A tuple of validated chip names.
    """
    configs = ctx.find_object(MeasureContext).configs
    chip_names = [name.upper() for name in chip_names]
    expected_chips_number = 1 if "matrix" in configs else len(configs["chips"])
    if len(chip_names) == 0:
        answer = click.prompt(f"Enter {expected_chips_number} chip name(s) separated by space",
                              type=str)
        chip_names = [name.upper() for name in answer.split()]
    
    if "matrix" in configs:
        if len(chip_names) != 1:
            raise click.BadParameter("Matrix measurement requires exactly one chip name")
    else:
        base_error_msg = f"{param.opts[0]} parameter is invalid. %s"
        if len(set(chip_names)) != len(chip_names):
            raise click.BadParameter(base_error_msg % "Chip names must be unique.")
        if len(chip_names) != expected_chips_number:
            raise click.BadParameter(base_error_msg % f"{expected_chips_number} chip names expected, based on provided config file.")
    
    return tuple(chip_names)


def preprocess_measurements(
    raw_measurements: dict[str, list], chip_config: dict
) -> dict[str, list]:
    """
    Preprocess raw measurement data based on `chips` configuration (measurement properties mapping).
    :param raw_measurements: a dictionary of raw measurements from the instrument
    :param chip_config: a mapping of measurement properties to the raw data
    :return:
    """
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
