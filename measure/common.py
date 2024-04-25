from typing import Optional

import click
import pandas as pd
from jsonpath_ng import parse
from pyvisa.resources import GPIBInstrument

from utils import (
    from_context,
)


@from_context("instruments.main", "instrument")
def apply_configs(commands: list[str], instrument: GPIBInstrument):
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


@from_context("configs.measure", "commands")
@from_context("instruments.main", "instrument")
def get_raw_measurements(commands: dict, instrument: GPIBInstrument) -> dict[str, list]:
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
    ctx.obj["logger"].warning("%s\n%s", error_msg, pd.DataFrame(raw_measurements).to_string(
        index=False, float_format="%.2e",
    ))
    if automatic_mode:
        raise RuntimeError("Measurement is invalid")
    
    click.confirm(
        "Do you want to save these measurements?",
        abort=True, default=True, err=True)


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
