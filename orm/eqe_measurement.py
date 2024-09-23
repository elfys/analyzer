from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .base import Base


class EqeMeasurement(Base):
    """
    Stores the results of EQE measurements, including data like wavelength, light current, dark
    current, and calculated EQE values.
    """
    __tablename__ = "eqe_data"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    wavelength: Mapped[int]
    light_current: Mapped[float]
    dark_current: Mapped[Optional[float]]
    std: Mapped[Optional[float]]
    eqe: Mapped[Optional[float]]
    responsivity: Mapped[Optional[float]]
    conditions_id: Mapped[int] = mapped_column(
        ForeignKey(
            "eqe_conditions.id",
            name="eqe_data__conditions",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
    )
    conditions: Mapped["EqeConditions"] = relationship(back_populates="measurements")  # noqa: F821
    
    def __repr__(self):
        return f"<EqeMeasurement(id={self.id}, wavelength={self.wavelength})>"
