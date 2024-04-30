from pathlib import Path

import click


def validate_files_glob(ctx, param, value: str):
    if Path(value).is_dir():
        raise click.BadParameter(
            "Directories are not allowed. Please provide a pattern to find files to parse."
        )
    file_paths = tuple(Path(".").glob(value))
    ctx.obj.logger.info(f"Found {len(file_paths)} files matching pattern {value}")
    if len(file_paths) == 0:
        ctx.exit()
    return tuple(Path(".").glob(value))
