from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DATETIME,
    VARCHAR,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .abstract_repository import AbstractRepository
from .base import Base


class Wafer(Base):
    __tablename__ = "wafer"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(length=20), unique=True)
    chips: Mapped[list["Chip"]] = relationship(back_populates="wafer")  # noqa: F821
    record_created_at: Mapped[datetime] = mapped_column(
        DATETIME, server_default=func.current_timestamp()
    )
    batch_id: Mapped[Optional[str]] = mapped_column(VARCHAR(length=10))
    type: Mapped[Optional[str]] = mapped_column(VARCHAR(length=10))
    
    def __repr__(self):
        return f"<Wafer(name='{self.name}, id='{self.id}')>"


class WaferRepository(AbstractRepository[Wafer]):
    model = Wafer
