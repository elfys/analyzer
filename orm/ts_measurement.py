from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .base import Base


class TsMeasurement(Base):
    """
    Stores data from Test Structure (TS) measurements, including current, voltage readings, and
    calculated resistance.
    """
    __tablename__ = "ts_data"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    current: Mapped[float]
    voltage_1: Mapped[float]
    voltage_2: Mapped[float]
    resistance: Mapped[float]
    conditions_id: Mapped[int] = mapped_column(
        ForeignKey(
            "ts_conditions.id",
            name="ts_data__conditions",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
    )
    
    conditions: Mapped["TsConditions"] = relationship(back_populates="measurements")  # noqa: F821
    
    def __repr__(self):
        return f"<TsMeasurement(id={self.id}, current={self.current})>"
