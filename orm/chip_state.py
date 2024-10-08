from sqlalchemy import VARCHAR
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from .base import Base


class ChipState(Base):
    """
    Indicates the state of a chip during measurement, such as "before wafer dicing", "after wire bonding" etc.
    """
    
    __tablename__ = "chip_state"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        VARCHAR(length=100),
        unique=True,
        comment="Chip state is used to indicate the state of corresponding chip during measurement (iv_data)",
    )
    
    def __repr__(self):
        return f"<ChipState(id={self.id}, name='{self.name}')>"
