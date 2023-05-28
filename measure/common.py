from typing import Optional

from jsonpath_ng import parse
from pyvisa.resources import GPIBInstrument


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


def validate_raw_measurements(
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
