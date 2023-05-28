from datetime import datetime
from typing import Optional

from sqlalchemy import VARCHAR, DATETIME, func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class Wafer(Base):
    __tablename__ = "wafer"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(length=20), unique=True)
    chips: Mapped[list["Chip"]] = relationship(back_populates="wafer")  # noqa: F821
    record_created_at: Mapped[datetime] = mapped_column(
        DATETIME, server_default=func.current_timestamp())
    batch_id: Mapped[Optional[str]] = mapped_column(VARCHAR(length=10))
    type: Mapped[Optional[str]] = mapped_column(VARCHAR(length=10))

    def __repr__(self):
        return "<Wafer(name='%s', id='%d')>" % (self.name, self.id)
