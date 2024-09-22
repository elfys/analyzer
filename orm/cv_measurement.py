from datetime import datetime as datetime_type
from decimal import Decimal

from sqlalchemy import (
    DECIMAL,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .base import Base


class CVMeasurement(Base):
    __tablename__ = "cv_data"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    chip_id: Mapped[int] = mapped_column(
        ForeignKey("chip.id", name="cv_data__chip", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    chip: Mapped["SimpleChip"] = relationship(back_populates="cv_measurements")  # noqa: F821
    chip_state_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chip_state.id",
            name="cv_data__chip_state",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        index=True,
    )
    chip_state: Mapped["ChipState"] = relationship()  # noqa: F821
    voltage_input: Mapped[Decimal] = mapped_column(DECIMAL(precision=10, scale=5))
    capacitance: Mapped[float]
    datetime: Mapped[datetime_type] = mapped_column(DateTime(), server_default=func.current_timestamp())
    
    def __repr__(self):
        return "<CVMeasurement(id='%d', chip='%s', capacitance='%.3e')>" % (
            self.id,
            self.chip,
            self.capacitance,
        )
