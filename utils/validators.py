from pathlib import Path

import click


def validate_files_glob(ctx: click.Context, param, value: str):
    from analyzer.context import AnalyzerContext

    if Path(value).is_dir():
        raise click.BadParameter(
            "Directories are not allowed. Please provide a pattern to find files to parse."
        )
    file_paths = tuple(Path(".").glob(value))
    obj = ctx.find_object(AnalyzerContext)
    obj.logger.info(f"Found {len(file_paths)} files matching pattern {value}")
    if len(file_paths) == 0:
        ctx.exit(0)
    return tuple(Path(".").glob(value))
