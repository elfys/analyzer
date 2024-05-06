# pyright: reportUndefinedVariable=false

from datetime import datetime as datetime_type
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    TEXT,
    VARCHAR,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .base import Base


class EqeConditions(Base):
    __tablename__ = "eqe_conditions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    chip_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chip.id",
            name="eqe_conditions__chip",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
    )
    chip: Mapped["EqeChip"] = relationship(back_populates="eqe_conditions")  # noqa: F821
    chip_state_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chip_state.id",
            name="eqe_conditions__chip_state",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        index=True,
    )
    chip_state: Mapped["ChipState"] = relationship()  # noqa: F821
    measurements: Mapped[list["EqeMeasurement"]] = relationship(  # noqa: F821
        back_populates="conditions"
    )
    datetime: Mapped[datetime_type] = mapped_column(DateTime(), server_default=func.current_timestamp())
    bias: Mapped[float]
    averaging: Mapped[int]
    dark_current: Mapped[float]
    temperature: Mapped[float]
    ddc: Mapped[Optional[str]] = mapped_column(VARCHAR(100), deferred_group="full")
    calibration_file: Mapped[str] = mapped_column(VARCHAR(100), deferred_group="full")
    session_id: Mapped[int] = mapped_column(
        ForeignKey(
            "eqe_session.id",
            name="eqe_conditions__session",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
    )
    session: Mapped["EqeSession"] = relationship(back_populates="eqe_conditions")  # noqa: F821
    instrument_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "instrument.id",
            name="eqe_conditions__instrument",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
    )
    instrument: Mapped["Instrument"] = relationship()  # noqa: F821
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey(
            "carrier.id",
            name="eqe_conditions__carrier",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
    )
    carrier: Mapped["Carrier"] = relationship()  # noqa: F821
    comment: Mapped[Optional[str]] = mapped_column(TEXT, deferred_group="full")
    
    def __repr__(self):
        return f"<EqeConditions(id={self.id}, datetime={self.datetime}>"
