from sqlalchemy import (
    JSON,
    VARCHAR,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from .base import Base


class Misc(Base):
    """
    A miscellaneous table for storing additional data in JSON format that doesn't fit into other
    predefined tables. Stores the CV and IC threshold values for different chip types.
    """
    __tablename__ = "misc"
    
    name: Mapped[str] = mapped_column(VARCHAR(100), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    
    def __repr__(self):
        return f"<Misc(name='{self.name}')>"
