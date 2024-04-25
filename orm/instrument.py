from sqlalchemy import (
    SmallInteger,
    VARCHAR,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from .abstract_repository import AbstractRepository
from .base import Base


class Instrument(Base):
    __tablename__ = "instrument"
    
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(length=100), unique=True)
    
    def __repr__(self):
        return "<Instrument(name='%s', id='%d')>" % (self.name, self.id)


class InstrumentRepository(AbstractRepository[Instrument]):
    model = Instrument
