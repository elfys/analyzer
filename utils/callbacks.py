import re
from datetime import datetime
from itertools import chain
from typing import    Sequence

from sqlalchemy import desc
from sqlalchemy.orm import Session

from orm import EqeSession


def eqe_session_date(ctx, param, session_date: datetime | None):
    if session_date is None:
        return None
    
    session: Session = ctx.obj["session"]
    if session_date == datetime(1900, 1, 1, 0, 0):  # 'last' is parsed as 1900-01-01
        eqe_session = session.query(EqeSession).order_by(desc(EqeSession.date)).first()
    else:
        eqe_session = (
            session.query(EqeSession).filter(EqeSession.date == session_date).one_or_none()
        )
    
    if eqe_session is None:
        ctx.obj["logger"].warning("EQE session with specified date was not found!")
        ctx.exit()
    
    return eqe_session


def flatten_options_type(values: str | Sequence[str]) -> set[str]:
    if isinstance(values, str):
        return set(re.split(r",\s?", values))
    else:
        return set(
            chain.from_iterable(
                (re.split(r",\s?", value) if isinstance(value, str) else value for value in values)
            )
        )


def flatten_options(ctx, param, values: str | Sequence[str]) -> set[str]:
    return flatten_options_type(values)
