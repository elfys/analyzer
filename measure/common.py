import pprint
from typing import Optional

import click
from jsonpath_ng import parse
from pyvisa.resources import GPIBInstrument
from sqlalchemy.orm import joinedload

from orm import (
    Chip,
    Wafer,
)
from utils import (
    get_or_create_chips,
    get_or_create_wafer,
)


def set_configs(instrument: GPIBInstrument, commands: list[str]):
    for command in commands:
        instrument.write(command)


def execute_command(instrument: GPIBInstrument, command: str, command_type: str):
    if command_type == "query":
        return instrument.query(command)
    if command_type == "write":
        return instrument.write(command)
    if command_type == "query_ascii_values":
        return list(instrument.query_ascii_values(command))
    if command_type == "query_csv_values":
        return [float(value) for value in instrument.query(command).split(",")]
    raise ValueError(f"Invalid command type {command_type}")


def get_raw_measurements(instrument: GPIBInstrument, commands: dict) -> dict[str, list]:
    measurements: dict[str, list] = {}
    for command in commands:
        value = execute_command(instrument, command["command"], command["type"])
        if "name" in command:
            measurements[command["name"]] = value
    return measurements


def validate_measurements(raw_measurements, config: dict, automatic_mode: bool):
    validation_config = config["program"].get("validation")
    if not validation_config:
        return
    
    error_msg = _validate_measurements(raw_measurements, validation_config)
    if error_msg is None:
        return
    
    ctx = click.get_current_context()
    ctx.obj["logger"].warning(error_msg)
    if automatic_mode:
        raise RuntimeError("Measurement is invalid")
    
    ctx.obj["logger"].info("\n" + pprint.pformat(raw_measurements, compact=True, indent=4))
    click.confirm("Do you want to save these measurements?", abort=True, default=True)


def _validate_measurements(
    measurements: dict[str, list], configs: dict[str, dict[dict]]
) -> Optional[str]:
    for value_name, config in configs.items():
        for validator_name, rules in config.items():
            path = parse(value_name)
            for ctx in path.find(measurements):
                value = ctx.value
                if rules.get("abs"):
                    value = abs(value)
                if validator_name == "min":
                    if value < rules["value"]:
                        return rules["message"]
                elif validator_name == "max":
                    if value > rules["value"]:
                        return rules["message"]
                else:
                    raise ValueError(f"Unknown validator {validator_name}")
    return None


def get_chips_for_names(chip_names, wafer_name, chips_number, session) -> list[Chip]:
    ctx = click.get_current_context()
    if chips_number != len(chip_names):
        if len(chip_names) > 0:
            ctx.obj["logger"].warning(
                f"Number of chip names does not match number of chips in config file. {chips_number} chip names expected"
            )
        for i in range(len(chip_names), chips_number):
            chip_name = click.prompt(f"Input chip name {i + 1}", type=str)
            chip_names += (chip_name,)
    wafer = get_or_create_wafer(wafer_name, session=session, query_options=joinedload(Wafer.chips))
    chips = get_or_create_chips(session, wafer, chip_names)
    return chips
