# pyright: reportUndefinedVariable=false

from datetime import datetime as datetime_type
from typing import Optional

from sqlalchemy import (
    DATETIME,
    ForeignKey,
    VARCHAR,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from . import AbstractRepository
from .base import Base


class IvConditions(Base):
    __tablename__ = "iv_conditions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    chip_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chip.id",
            name="iv_conditions__chip",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
    )
    chip: Mapped["SimpleChip"] = relationship(back_populates="iv_conditions")  # noqa: F821
    chip_state_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chip_state.id",
            name="iv_conditions__chip_state",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        index=True,
    )
    chip_state: Mapped["ChipState"] = relationship()  # noqa: F821
    measurements: Mapped[list["IVMeasurement"]] = relationship(  # noqa: F821
        back_populates="conditions"
    )
    datetime: Mapped[datetime_type] = mapped_column(
        DATETIME,
        server_default=func.current_timestamp(),
        deferred_group="full",
    )
    temperature: Mapped[Optional[float]] = mapped_column(deferred_group="full")
    int_time: Mapped[Optional[str]] = mapped_column(VARCHAR(length=20), deferred_group="full")
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey(
            "instrument.id",
            name="iv_conditions__instrument",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        deferred_group="full",
    )
    instrument: Mapped["Instrument"] = relationship()  # noqa: F821
    
    def __repr__(self):
        return f"<IvConditions(id={self.id}, datetime={self.datetime}>"


class IvConditionsRepository(AbstractRepository[IvConditions]):
    model = IvConditions
