import re
from datetime import datetime
from itertools import chain
from typing import Sequence

import click
from sqlalchemy import desc
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from orm import (
    EqeSession,
    Wafer,
    WaferRepository,
)


def eqe_session_date(
    ctx: click.Context, param: click.Parameter, session_date: datetime | None
):
    """
    Retrieve an `EqeSession` based on the provided session date.

    This function is intended to be used as a callback for processing the
    `session_date` parameter in Click commands. It handles special cases
    like retrieving the most recent session when 'last' is specified.

    Parameters:
        ctx (click.Context): The Click context object.
        param (click.Parameter): The Click parameter object (unused in this
        function).
        session_date (datetime | None): The date of the session to retrieve.
        If `None`, no action is taken.

    Returns:
        EqeSession | None: The `EqeSession` object corresponding to the
        provided date, or `None` if no date is provided.

    Exits:
        Exits the program if the `EqeSession` is not found for the provided
        date.
    """
    if session_date is None:
        return None

    session: Session = ctx.obj["session"]
    if session_date == datetime(1900, 1, 1, 0, 0):  # 'last' is parsed as 1900-01-01
        eqe_session = session.query(EqeSession).order_by(desc(EqeSession.date)).first()
    else:
        eqe_session = (
            session.query(EqeSession)
            .filter(EqeSession.date == session_date)
            .one_or_none()
        )

    if eqe_session is None:
        ctx.obj.logger.warning("EQE session with specified date was not found!")
        ctx.exit()

    return eqe_session


def flatten_csv_tuples(values: str | Sequence[str]) -> set[str]:
    """
    Flatten a string or sequence of strings containing comma-separated
    values into a set of strings.

    Parameters:
        values (str | Sequence[str]): A string or a sequence of strings.

    Returns:
        set[str]: A set of individual strings extracted from the input.
    """
    if isinstance(values, str):
        return set(re.split(r",\s?", values))
    else:
        return set(
            chain.from_iterable(
                (
                    re.split(r",\s?", value) if isinstance(value, str) else value
                    for value in values
                )
            )
        )


def wafer_loader(
    ctx: click.Context, param: click.Parameter, value: str | Sequence[str] | None
):
    """
    Load `Wafer` objects based on the provided value.

    This function is intended to be used as a callback for processing the wafer
    parameter in Click commands. It supports loading multiple wafers if the
    parameter is configured to accept multiple values.

    Parameters:
        ctx (click.Context): The Click context object.
        param (click.Parameter): The Click parameter object that invoked this
        callback.
        value (str | Sequence[str] | None): The value provided for the wafer
        parameter. Can be a string or sequence of strings.

    Returns:
        Wafer | list[Wafer] | None: The loaded `Wafer` object(s), or
        `None` if no value was provided.

    Raises:
        click.BadParameter: If multiple wafers are provided but the
        parameter does not support multiple values.
        click.Abort: If a specified wafer is not found.
    """
    if not value:
        return None
    wafer_names = {n.upper() for n in flatten_csv_tuples(value)}
    if not param.multiple and len(wafer_names) > 1:
        raise click.BadParameter(
            "Multiple wafers are not supported. Please provide only one wafer."
        )

    from analyzer.context import AnalyzerContext

    obj = ctx.find_object(AnalyzerContext)

    if param.multiple:
        wafers = WaferRepository(obj.session).get_all_by(Wafer.name.in_(wafer_names))
        non_existing_wafers = wafer_names - {w.name for w in wafers}
        if non_existing_wafers:
            obj.logger.warning(
                f"Wafers {non_existing_wafers} not found. Continuing with existing wafers."
            )
        return wafers
    else:
        try:
            return WaferRepository(ctx.obj.session).get(name=wafer_names.pop())
        except NoResultFound:
            obj.logger.warning(f"Wafer {value} not found.")
            raise click.Abort()
