from sqlalchemy import VARCHAR, SmallInteger
from sqlalchemy.orm import mapped_column, Mapped

from .base import Base


class Instrument(Base):
    __tablename__ = "instrument"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(length=100), unique=True)

    def __repr__(self):
        return "<Instrument(name='%s', id='%d')>" % (self.name, self.id)
