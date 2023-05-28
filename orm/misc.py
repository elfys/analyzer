from sqlalchemy import JSON, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from orm import Base


class Misc(Base):
    __tablename__ = 'misc'

    name: Mapped[str] = mapped_column(VARCHAR(100), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)

    def __repr__(self):
        return f"<Misc(name='{self.name}')>"
