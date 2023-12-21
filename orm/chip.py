import functools
import re
from typing import (
    List,
    Union,
)

import click
from sqlalchemy import (
    ExecutionContext,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from .base import Base


@functools.lru_cache()
def get_chip_name_re() -> re.Pattern:
    known_chip_types = Chip.chip_sizes.keys()
    postfix_re = r"(H|M)?"
    pattern = rf"^(?P<type>[{''.join(known_chip_types)}]{postfix_re})(?P<number>\d{{4}})"
    return re.compile(pattern, re.IGNORECASE)


def infer_chip_type(ctx: ExecutionContext) -> Union[str, None]:
    if ctx.get_current_parameters()["test_structure"]:
        return "TS"
    
    chip_name = ctx.get_current_parameters()["name"]
    match = get_chip_name_re().match(chip_name.upper())
    if match:
        return match.group("type")
    
    return None


def validate_chip_name(name: str) -> str:
    match = get_chip_name_re().match(name.upper())
    if not match:
        raise click.BadParameter(f"{name} is not valid chip name.")
    
    return f"{match.group('type')}{match.group('number')}"


class Chip(Base):
    __tablename__ = "chip"
    __table_args__ = tuple([UniqueConstraint("name", "wafer_id", name="unique_chip")])
    
    chip_sizes = {
        "A": (1.69, 1.69),
        "B": (1.69, 1.69),
        "C": ...,
        "D": ...,
        "E": ...,
        "F": (2.56, 1.25),
        "G": (1.4, 3.25),
        "I": ...,
        "J": ...,
        "L": ...,
        "U": (5, 5),
        "UH": (5, 5),
        "V": (10, 10),
        "VH": (10, 10),
        "X": (1, 1),
        "XH": (1, 1),
        "Y": (2, 2),
        "YH": (2, 2),
    }
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wafer_id: Mapped[int] = mapped_column(
        ForeignKey("wafer.id", name="chip__wafer", ondelete="RESTRICT", onupdate="CASCADE"),
        index=True,
    )
    wafer: Mapped["Wafer"] = relationship(back_populates="chips")  # noqa: F821
    name: Mapped[str] = mapped_column(String(length=20))
    type: Mapped[str] = mapped_column(
        String(length=8), default=infer_chip_type, index=True, nullable=True
    )
    test_structure: Mapped[bool] = mapped_column(default=False)
    iv_conditions: Mapped[List["IvConditions"]] = relationship(back_populates="chip")  # noqa: F821
    cv_measurements: Mapped[List["CVMeasurement"]] = relationship(  # noqa: F821
        back_populates="chip"
    )
    eqe_conditions: Mapped[List["EqeConditions"]] = relationship(  # noqa: F821
        back_populates="chip"
    )
    
    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        return name.upper()
    
    @property
    def x_coordinate(self):
        if self.test_structure:
            raise ValueError("Test structure chips do not have coordinates")
        match = get_chip_name_re().match(self.name)
        if match.group("number"):
            return int(match.group("number")[0:2])
        else:
            raise ValueError(f"Could not parse chip coordinate {self.name}")
    
    @property
    def y_coordinate(self):
        if self.test_structure:
            raise ValueError("Test structure chips do not have coordinates")
        match = get_chip_name_re().match(self.name)
        if match.group("number"):
            return int(match.group("number")[2:4])
        else:
            raise ValueError(f"Could not parse chip coordinate {self.name}")
    
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
