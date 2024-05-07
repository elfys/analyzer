# pyright: reportUndefinedVariable=false

import re
from typing import (
    ClassVar,
    Type,
    TypeGuard,
)

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    joinedload,
    mapped_column,
    relationship,
    validates,
)

from .abstract_repository import AbstractRepository
from .base import Base


class ChipCollectionMeta(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        if chip_sizes := dct.get("chip_sizes"):
            for chip_type, chip_size in chip_sizes.items():
                cls.create_chip_class(chip_type, chip_size)
    
    def create_chip_class(cls, chip_type, chip_size):
        class_name = f"{chip_type}Chip"
        chip_class = type(
            class_name,
            (cls,),
            {
                '__mapper_args__': {'polymorphic_identity': chip_type},
                'chip_size': chip_size,
                '__chip_type__': chip_type,
            }
        )
        globals()[class_name] = chip_class


class BaseMeta(type(Base), ChipCollectionMeta):
    pass


class Chip(Base, metaclass=BaseMeta):
    __tablename__ = "chip"
    __table_args__ = tuple([UniqueConstraint("name", "wafer_id", name="unique_chip")])
    __mapper_args__ = {
        "polymorphic_on": 'type',
        "polymorphic_abstract": True,
    }
    __chip_type__: str
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wafer_id: Mapped[int] = mapped_column(
        ForeignKey("wafer.id", name="chip__wafer", ondelete="RESTRICT", onupdate="CASCADE"),
        index=True,
    )
    wafer: Mapped["Wafer"] = relationship(back_populates="chips")  # noqa: F821
    name: Mapped[str] = mapped_column(String(length=20))
    type: Mapped[str] = mapped_column(String(length=8), index=True, nullable=True)
    
    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        return name.upper()
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id} name='{self.name}')>"


class SimpleChip(Chip):  # all chips with size, have IV and CV measurements
    __mapper_args__ = {"polymorphic_abstract": True}
    
    chip_sizes = {
        "A": (1.69, 1.69),
        "B": (1.69, 1.69),
        "C": None,
        "D": None,
        "E": (1.806, 1.806),
        "F": (2.56, 1.25),
        "G": (1.4, 3.25),
        "S": (1.825, 1.825),
        "T": (1.45, 1.45),
        "V": (10, 10),
        "VH": (10, 10),
        "X": (1, 1),
        "XH": (1, 1),
        "Y": (2, 2),
        "YH": (2, 2),
    }
    chip_size: ClassVar[tuple[float, float]]
    
    iv_conditions: Mapped[list["IvConditions"]] = relationship(back_populates="chip")  # noqa: F821
    cv_measurements: Mapped[list["CVMeasurement"]] = relationship(  # noqa: F821
        back_populates="chip"
    )
    
    @property
    def x_coordinate(self):
        digits = re.sub(rf'^{self.type}', '', self.name)
        if not digits.isdigit() or len(digits) != 4:
            raise ValueError(f"Could not parse chip coordinate {self.name}. Expected format is chip type followed by 4 digits")
        return int(digits[0:2])
    
    @property
    def y_coordinate(self):
        digits = re.sub(rf'^{self.type}', '', self.name)
        if not digits.isdigit() or len(digits) != 4:
            raise ValueError(f"Could not parse chip coordinate {self.name}. Expected format is chip type followed by 4 digits")
        return int(digits[2:4])
    
    @classmethod
    def get_area(cls) -> float:
        chip_size = cls.get_chip_size()
        return chip_size[0] * chip_size[1]
    
    @classmethod
    def get_perimeter(cls) -> float:
        chip_size = cls.get_chip_size()
        return (chip_size[0] + chip_size[1]) * 2
    
    @classmethod
    def get_chip_size(cls) -> tuple[float, float]:
        if cls.chip_size is None:
            raise AttributeError(f"Chip size for {cls.__name__} is unknown")
        return cls.chip_size


class TestStructureChip(Chip):
    __mapper_args__ = {"polymorphic_identity": "TS"}
    
    ts_conditions: Mapped[list["TsConditions"]] = relationship(back_populates="chip")  # noqa: F821


class MatrixChip(SimpleChip):
    __mapper_args__ = {"polymorphic_abstract": True}
    chip_sizes = {
        "Q": (.448, .540),  # one pixel out of 9
        "R": (.830, .665),  # one pixel out of 9
    }
    
    matrix_id: Mapped[int | None] = mapped_column(
        ForeignKey("matrix.id", name="chip__matrix", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    matrix: Mapped["Matrix"] = relationship(back_populates="chips")  # noqa: F821


class EqeChip(SimpleChip):
    __mapper_args__ = {"polymorphic_abstract": True}
    eqe_conditions: Mapped[list["EqeConditions"]] = relationship(  # noqa: F821
        back_populates="chip"
    )
    
    chip_sizes = {
        "U": (5, 5),
        "UH": (5, 5),
        "I": None,
        "IH": None,
        "IM": None,
        "J": None,
        "JH": None,
        "JM": None,
        "L": None,
        "LH": None,
        "LM": None,
        "REF": None,
    }


class ChipRepositoryMeta(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        subclasses = cls.get_all_subclasses(Chip)
        cls.chip_types = {
            subclass.__mapper_args__["polymorphic_identity"]: subclass
            for subclass in subclasses
            if "polymorphic_identity" in subclass.__mapper_args__}
    
    def get_all_subclasses(cls, target: type[Chip]) -> list[type[Chip]]:
        all_subclasses = []
        
        for subclass in target.__subclasses__():
            all_subclasses.append(subclass)
            all_subclasses.extend(cls.get_all_subclasses(subclass))
        
        return all_subclasses


def is_simple_chip_type(cls: type[Chip]) -> TypeGuard[Type[SimpleChip]]:
    return issubclass(cls, SimpleChip)


class ChipRepository(AbstractRepository[Chip], metaclass=ChipRepositoryMeta):
    model = Chip
    chip_types: dict[str, type[Chip]]
    
    @classmethod
    def get_chip_class(cls, chip_type: str) -> type[Chip]:
        if chip_type not in cls.chip_types:
            raise ValueError(f"Unknown chip type {chip_type}")
        return cls.chip_types[chip_type]
    
    @classmethod
    def get_area(cls, chip_type: str) -> float:
        chip_cls = cls.get_chip_class(chip_type)
        if not is_simple_chip_type(chip_cls):
            raise AttributeError(f"Chip class {chip_cls.__name__} has no get_area method")
        else:
            return chip_cls.get_area()
    
    @classmethod
    def get_perimeter(cls, chip_type: str) -> float:
        chip_cls = cls.get_chip_class(chip_type)
        if not is_simple_chip_type(chip_cls):
            raise AttributeError(f"Chip class {chip_cls.__name__} has no get_perimeter method")
        else:
            return chip_cls.get_perimeter()
    
    @classmethod
    def infer_chip_type(cls, chip_name: str) -> str:
        match = re.match(r"^[A-Z]+", chip_name)
        if match is None:
            raise ValueError(f"Could not infer chip type from name {chip_name}")
        chip_type = match.group(0)
        if chip_type not in cls.chip_types:
            raise ValueError(f"Unknown chip type {chip_type}")
        return match.group(0)
    
    @classmethod
    def create(cls, **kwargs) -> Chip:
        if (chip_type := kwargs.get('type')) is None:
            chip_type = cls.infer_chip_type(kwargs["name"])
            kwargs["type"] = chip_type
        else:
            if chip_type not in cls.chip_types:
                raise ValueError(f"Unknown chip type {chip_type}")
        model = cls.get_chip_class(chip_type)
        try:
            chip = model(**kwargs)
        except TypeError:
            raise ValueError(f"Could not create chip of type {model.__name__} with arguments {kwargs}")
        return chip
    
    def get_or_create_chips_for_wafer(self, chip_names, wafer_name) -> list[Chip]:
        from .wafer import (
            Wafer,
            WaferRepository,
        )
        wafer_repo = WaferRepository(self.session)
        wafer = wafer_repo.get_or_create(name=wafer_name, query_options=joinedload(Wafer.chips))
        existing_chip_names = {chip.name.upper() for chip in wafer.chips}
        chip_names_to_create = {name.upper() for name in chip_names} - existing_chip_names
        
        for chip_name in chip_names_to_create:
            self.create(name=chip_name, wafer=wafer)
        chips_dict = {chip.name: chip for chip in wafer.chips}
        return [chips_dict[chip_name] for chip_name in chip_names]
