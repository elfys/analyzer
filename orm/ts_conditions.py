from datetime import datetime as datetime_type

from sqlalchemy import (
    DateTime,
    ForeignKey,
    SmallInteger,
    UniqueConstraint,
    VARCHAR,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .base import Base


class TsConditions(Base):
    __tablename__ = "ts_conditions"
    __table_args__ = (
        UniqueConstraint(
            "chip_id",
            "ts_step",
            "ts_number",
            "structure_type",
            name="unique_ts_condition",
        ),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    chip_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chip.id",
            name="ts_conditions__chip",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
    )
    chip: Mapped["TestStructureChip"] = relationship(back_populates="ts_conditions")  # noqa: F821
    measurements: Mapped[list["TsMeasurement"]] = relationship(  # noqa: F821
        back_populates="conditions"
    )
    structure_type: Mapped[str] = mapped_column(VARCHAR(length=10))
    ts_step: Mapped[int] = mapped_column(SmallInteger)
    ts_number: Mapped[int] = mapped_column(SmallInteger)
    datetime: Mapped[datetime_type] = mapped_column(DateTime())
    
    def __repr__(self):
        return f"<TsConditions(id={self.id}, datetime={self.datetime}>"
