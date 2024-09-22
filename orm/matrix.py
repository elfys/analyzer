from sqlalchemy import (
    Column,
    Integer,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    relationship,
)

from .abstract_repository import AbstractRepository
from .base import Base
from .chip import ChipRepository


class Matrix(Base):
    __tablename__ = 'matrix'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(length=20))
    width = Column(Integer)
    height = Column(Integer)
    chips: Mapped[list["MatrixChip"]] = relationship(back_populates="matrix")  # noqa: F821


class MatrixRepository(AbstractRepository[Matrix]):
    model = Matrix
    
    def get_or_create_from_configs(self, matrix_name, wafer_name, matrix_config) -> Matrix:
        width, height = matrix_config['width'], matrix_config['height']
        chip_names = [f"{matrix_name}_{i}{j}" for i in range(width) for j in range(height)]
        chips = ChipRepository(self.session).get_or_create_chips_for_wafer(chip_names, wafer_name)
        matrix = self.get_or_create(name=matrix_name, width=width, height=height)
        matrix.chips = chips
        return matrix
