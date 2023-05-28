from typing import Optional

import click
from sqlalchemy.orm import Session

from orm import Wafer, Chip


def get_or_create_wafer(
    wafer_name: Optional[str] = None,
    default: Optional[str] = None,
    session: Session = None,
    query_options: None = None,
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
        session.add(wafer)

    return wafer


def get_or_create_chips(session: Session, wafer: Wafer, chip_names: list[str]) -> dict[str, Chip]:
    existing_chip_names = [chip.name for chip in wafer.chips]
    new_chips = [
        Chip(name=chip_name) for chip_name in chip_names if chip_name not in existing_chip_names
    ]
    wafer.chips.extend(new_chips)
    session.add(wafer)
    return {chip.name: chip for chip in wafer.chips if chip.name in chip_names}
