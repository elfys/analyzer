# pyright: reportUndefinedVariable=false

from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DECIMAL,
    ForeignKey,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .base import Base


class IVMeasurement(Base):
    __tablename__ = "iv_data"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    voltage_input: Mapped[Decimal] = mapped_column(DECIMAL(precision=10, scale=5))
    anode_current: Mapped[float]
    cathode_current: Mapped[Optional[float]]
    anode_current_corrected: Mapped[Optional[float]]
    guard_current: Mapped[Optional[float]]
    
    conditions_id: Mapped[int] = mapped_column(
        ForeignKey(
            "iv_conditions.id",
            name="iv_data__conditions",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
    )
    conditions: Mapped["IvConditions"] = relationship(back_populates="measurements")  # noqa: F821
    
    def __repr__(self):
        return f"<IVMeasurement(id={self.id} voltage_input={self.voltage_input})>"
    
    def get_anode_current_value(self):
        if self.anode_current_corrected is not None:
            return self.anode_current_corrected
        return self.anode_current
