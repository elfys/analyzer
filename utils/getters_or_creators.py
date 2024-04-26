from typing import (
    Optional,
    Sequence,
)

import click
from sqlalchemy.orm import (
    Load,
    Session,
)

from orm import (
    Chip,
    Wafer,
)


def get_or_create_wafer(
    wafer_name: Optional[str] = None,
    default: Optional[str] = None,
    session: Session = None,
    query_options: Load = None,
) -> Wafer:
    if wafer_name is None:
        wafer_name = click.prompt(
            f"Input wafer name ({'press Enter to confirm default value ' if default else ''}or type 'skip' or 'exit')",
            type=str,
            default=default,
            show_default=True,
        ).upper()
        if wafer_name == "SKIP":
            raise click.Abort()
        if wafer_name == "EXIT":
            click.get_current_context().exit(0)
    
    query = session.query(Wafer).filter(Wafer.name == wafer_name)
    if query_options is not None:
        query = query.options(query_options)
    
    wafer = query.one_or_none()
    if wafer is None:
        click.confirm(
            f"There is no wafers with name={wafer_name} in the database. Do you want to create one?",
            default=True,
            abort=True,
        )
        wafer = Wafer(name=wafer_name)
    
    return wafer


def get_or_create_chips(wafer: Wafer, chip_names: Sequence[str]) -> list[Chip]:
    existing_chips_dict = {chip.name.upper(): chip for chip in wafer.chips}
    result = []
    for chip_name in chip_names:
        if chip_name.upper() not in existing_chips_dict:
            chip = Chip(name=chip_name)
            wafer.chips.append(chip)
            result.append(chip)
        else:
            result.append(existing_chips_dict[chip_name.upper()])
    
    return result
