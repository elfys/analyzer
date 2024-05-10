from pathlib import Path

import click

from orm import ChipRepository


def validate_files_glob(ctx: click.Context, param: click.Parameter, value: str):
    
    if Path(value).is_dir():
        raise click.BadParameter(
            "Directories are not allowed. Please provide a pattern to find files to parse."
        )
    file_paths = tuple(Path(".").glob(value))
    
    from analyzer.context import AnalyzerContext
    obj = ctx.find_object(AnalyzerContext)
    obj.logger.info(f"Found {len(file_paths)} files matching pattern {value}")
    if len(file_paths) == 0:
        ctx.exit(0)
    return tuple(Path(".").glob(value))


def validate_chip_types(ctx: click.Context, param: click.Parameter, value: str | None):
    if not value:
        return None
    
    given_chip_types = {t.upper() for t in value.split(",")}
    
    if not param.multiple and len(given_chip_types) > 1:
        raise click.BadParameter(
            "Multiple chip types are not supported. Please provide only one chip type."
        )
    
    supported_chip_types = ChipRepository.chip_types.keys()
    
    non_supported_chip_types = set(given_chip_types) - set(supported_chip_types)
    if non_supported_chip_types:
        raise click.BadParameter(
            f"Chip types {non_supported_chip_types} are not supported. "
            f"Supported chip types: {supported_chip_types}"
        )
    
    return given_chip_types.pop() if not param.multiple else given_chip_types
