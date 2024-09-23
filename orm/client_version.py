from sqlalchemy import CHAR
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from .base import Base


class ClientVersion(Base):
    """
    Stores the latest release version of `analyzer.exe`. All versions below it will show a warning
     message and possibly raise an error due to breaking changes in the database structure.
    """
    __tablename__ = "client_version"
    version: Mapped[str] = mapped_column(CHAR(length=10), unique=True, primary_key=True)
    
    def __repr__(self):
        return f"<ClientVersion(version={self.version})>"
    
    def __eq__(self, other):
        return self.version == other.version
    
    def __lt__(self, other):
        if self.version == "DEV" or other.version == "DEV":
            return False
        return float(self.version) < float(other.version)
