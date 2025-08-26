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
def apply_configs(ctx: MeasureContext, commands: list[str], instrument_type="main"):
    """
    Applies all measurement settings defined in yaml file under "setups" with certain "name"
    instrument_type defines to which instruments should be applied. If it is not given, "main" is assumed
    
    :param ctx: The context object (provided by the click decorator).
    :param commands: List of commands to execute.
    :param instrument_type: Defines to which instrument the commands should be sent. "main" by default
    :return:
    """
    instrument: PyVisaInstrument = cast(PyVisaInstrument, ctx.instruments[instrument_type])
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
        instrument.handle_error(e)


# Assumption: when mux mode is used and setup name is "cv", only CV is always measured. If instrument named "main" exists, then mux mode is not in use.
# If no instrument with "main" exists, then instuments named "iv" and "cv" need to be defined in the yaml file
@from_config("measure")
@pass_measure_context
def get_raw_measurements(ctx: MeasureContext, commands: list[dict], sweep_type = "single") -> dict[str, list]:
    """
    Measures raw data by executing the part of the yaml file that executes the measurement loop.
    Assumptions: 
    - When mux mode is used and setup name is "cv", only CV is always measured. 
    - If instrument named "main" exists, then mux mode is not in use.
    - If no instrument with "main" exists, then instuments named "iv" and "cv" need to be defined in the yaml file
    
    :param ctx: The context object (provided by the click decorator).
    :param commands: List of commands to execute.
    :param sweep_type: The type of sweep (iv or cv) that the commands are related to. Relevant only if instrument called "main" does not exist, i.e. mux is used
    :return: dict[str, list]: Dictionary containing raw measurement data
    """
    if ctx.instruments.get("main") is not None:
        # Instrument called "main" is found, so only one instrument needs to be controlled and mux card is not used 
        instrument: PyVisaInstrument = cast(PyVisaInstrument, ctx.instruments["main"])
        measurements: dict[str, list] = {}
        for command in commands:
            value = execute_command(instrument, command["command"], command["type"])
            if "name" in command:
                # If command has property name, the output of the command should be assigned to variable with that name
                if isinstance(value, list):
                    measurements[command["name"]] = value
                else:
                    raise click.BadParameter(
                        f"Invalid output for command {command['type']}:{command['command']}: {repr(value)}."
                        f"A list of values was expected.")
    else:
        # Instrument called "main" is not found which means that mux board is used and therefore instruments called 
        # "iv" and "cv" needs to be defined and both are controlled
        iv_instrument: PyVisaInstrument = cast(PyVisaInstrument, ctx.instruments["iv"])
        cv_instrument: PyVisaInstrument = cast(PyVisaInstrument, ctx.instruments["cv"])
        measurements: dict[str, list] = {}
        for command in commands:
            if command["command"].get("sweep") is sweep_type:
                if command["command"] is "loop":
                    # If command is called "loop" it means that all commands within its "steps" list need to be repeated
                    # as many times as count dictates. Otherwise each command is executed only once
                    iterations = command["command"].get("count")
                    for i in range(iterations):
                        for step in command["command"].get("steps"):
                            if step["tool"] is "iv":
                                value = execute_command(iv_instrument, step["command"], step["type"]) 
                            elif step["tool"] is "cv":
                                value = execute_command(cv_instrument, step["command"], step["type"])                  
                else:
                    if command["tool"] is "iv":
                        value = execute_command(iv_instrument, command["command"], command["type"])
                    elif command["tool"] is "cv":
                        value = execute_command(cv_instrument, command["command"], command["type"])
                    else:
                        raise click.BadParameter("Invalid tool name or tool not specified.")
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
