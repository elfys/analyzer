import re
from pathlib import Path

import click


def validate_wafer_name(ctx, param, wafer_name: str):
    special_wafer_names = {"TEST", "REF"}
    
    wafer_name = wafer_name.upper()
    if wafer_name in special_wafer_names:
        return wafer_name
    matcher = re.compile(r"^\w{2,3}\d{1,2}(-\w\d{4})?$")
    if not matcher.match(wafer_name):
        raise click.BadParameter(
            f"{wafer_name} is not valid wafer name. It must be in format LL[L]X[X][-LXXXX] where L is a letter and X is a number."
            f" [] denotes optional symbols."
            f'\nAlso you can use one of the special wafer names: {", ".join(special_wafer_names)}'
        )
    return wafer_name


def validate_chip_names(ctx, param, chip_names: list[str]):
    configs = ctx.obj["configs"]
    chip_names = [name.upper() for name in chip_names]
    if "matrix" in configs:
        if len(chip_names) != 1:
            raise click.BadParameter("Matrix measurement requires exactly one chip name")
    else:
        if len(set(chip_names)) != len(chip_names):
            raise ValueError("Chip names must be unique")
        expected_chips_number = len(configs["chips"])
        if len(chip_names) != expected_chips_number:
            raise ValueError(f"{expected_chips_number} chip names expected, based on provided config file ({len(chip_names)} names given)")
    
    return tuple(chip_names)


def validate_files_glob(ctx, param, value: str):
    if Path(value).is_dir():
        raise click.BadParameter(
            "Directories are not allowed. Please provide a pattern to find files to parse."
        )
    file_paths = tuple(Path(".").glob(value))
    ctx.obj["logger"].info(f"Found {len(file_paths)} files matching pattern {value}")
    if len(file_paths) == 0:
        ctx.exit()
    return tuple(Path(".").glob(value))
