from sqlalchemy import (
    SmallInteger,
    VARCHAR,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from .base import Base


class Carrier(Base):
    __tablename__ = "carrier"
    
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(length=100), unique=True)
    
    def __repr__(self):
        return f"<Carrier(id={self.id} name='{self.name}')>"
