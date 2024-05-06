# pyright: reportUndefinedVariable=false

import datetime

from sqlalchemy import text
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .base import Base


class EqeSession(Base):
    __tablename__ = "eqe_session"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(server_default=text("(CURRENT_DATE)"))
    eqe_conditions: Mapped[list["EqeConditions"]] = relationship(  # noqa: F821
        back_populates="session"
    )
    
    def __repr__(self):
        return f"<EqeSession(id={self.id}, date={self.date})>"
