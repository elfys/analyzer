from typing import List

from sqlalchemy import (
    Integer,
    CHAR,
    VARCHAR,
    ForeignKey,
    Computed,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, mapped_column, Mapped

from .base import Base


class Chip(Base):
    __tablename__ = "chip"
    __table_args__ = tuple([UniqueConstraint("name", "wafer_id", name="unique_chip")])

    chip_sizes = {
        "X": (1, 1),
        "Y": (2, 2),
        "U": (5, 5),
        "V": (10, 10),
        "F": (2.56, 1.25),
        "G": (1.4, 3.25),
        "A": (1.69, 1.69),
        "B": (1.69, 1.69),
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wafer_id: Mapped[int] = mapped_column(
        ForeignKey("wafer.id", name="chip__wafer", ondelete="RESTRICT", onupdate="CASCADE"),
        index=True,
    )
    wafer: Mapped["Wafer"] = relationship(back_populates="chips")  # noqa: F821
    name: Mapped[str] = mapped_column(VARCHAR(length=20))
    type: Mapped[str] = mapped_column(
        CHAR(length=1),
        Computed("'(SUBSTR(`name`,1,1))'", persisted=False))
    test_structure: Mapped[bool] = mapped_column(default=False)
    iv_conditions: Mapped[List["IvConditions"]] = relationship(back_populates="chip")  # noqa: F821
    cv_measurements: Mapped[List["CVMeasurement"]] = relationship(back_populates="chip")  # noqa: F821
    eqe_conditions: Mapped[List["EqeConditions"]] = relationship(back_populates="chip")  # noqa: F821

    @property
    def x_coordinate(self):
        if self.test_structure:
            raise ValueError("Test structure chips do not have coordinates")
        return int(self.name[1:3])

    @property
    def y_coordinate(self):
        if self.test_structure:
            raise ValueError("Test structure chips do not have coordinates")
        return int(self.name[3:5])

    @property
    def area(self):
        if self.test_structure:
            raise ValueError("Test structure chips do not have area")
        return Chip.get_area(self.type)

    @staticmethod
    def get_area(chip_type: str) -> float:
        return Chip.chip_sizes[chip_type][0] * Chip.chip_sizes[chip_type][1]

    @staticmethod
    def get_perimeter(chip_type: str) -> float:
        return (Chip.chip_sizes[chip_type][0] + Chip.chip_sizes[chip_type][1]) * 2

    @property
    def perimeter(self) -> float:
        return Chip.get_perimeter(self.type)

    @staticmethod
    def get_types() -> list[str]:
        return list(Chip.chip_sizes.keys())

    def __repr__(self):
        return f"<Chip(id={self.id} name='{self.name}')>"
