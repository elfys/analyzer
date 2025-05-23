import re
import sys
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
    mapped_column,
    relationship,
    validates,
)

from .abstract_repository import AbstractRepository
from .base import Base


class ChipMetaclass(type(Base)):
    """
    Metaclass for Chip classes that creates a set of new classes for every chip type in `chip_sizes` class dict.
    Read more about metaclasses here: https://realpython.com/python-metaclasses/
    """
    
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        if chip_sizes := dct.get("chip_sizes"):
            for chip_type, chip_size in chip_sizes.items():
                cls.create_chip_class(chip_type, chip_size)
    
    def create_chip_class(cls, chip_type, chip_size):
        module = sys.modules[cls.__module__]
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
        chip_class.__module__ = cls.__module__
        setattr(module, class_name, chip_class)


class AbstractChip(Base, metaclass=ChipMetaclass):
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


class SimpleChip(AbstractChip):
    """
    Base class for simple chips with known size. Have related IV and CV measurements.
    """
    __mapper_args__ = {"polymorphic_abstract": True}
    
    chip_sizes = {
        "A": (1.69, 1.69),
        "B": (1.69, 1.69),
        "C": (1.23, 1.23),
        "CM": (0.76, 0.76),
        "D": (1.23, 1.23),
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
        if not digits.isdigit() or len(digits) %2 != 0:
            raise ValueError(f"Could not parse chip coordinate {self.name}. Expected format is chip type followed by 4 digits")
        return int(digits[(len(digits)//2):])
    
    @property
    def y_coordinate(self):
        digits = re.sub(rf'^{self.type}', '', self.name)
        if not digits.isdigit() or len(digits) %2 != 0:
            raise ValueError(f"Could not parse chip coordinate {self.name}. Expected format is chip type followed by 4 digits")
        return int(digits[:(len(digits)//2)])
    
    @property
    def width(self):
        return 1
    
    @property
    def height(self):
        return 1
    
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


class TestStructureChip(AbstractChip):
    __mapper_args__ = {"polymorphic_identity": "TS"}
    
    ts_conditions: Mapped[list["TsConditions"]] = relationship(back_populates="chip")  # noqa: F821


class MatrixChip(SimpleChip):
    """
    Represents chips that are part of a matrix, such as Q, R and W chips.
    """
    
    xcoord_re = re.compile(r'^\d\d(?P<matrix>\d\d)_\d(?P<px>\d)$')
    ycoord_re = re.compile(r'^(?P<matrix>\d\d)\d\d_(?P<px>\d)\d$')
    
    __mapper_args__ = {"polymorphic_abstract": True}
    chip_sizes = {
        "Q": (.448, .540),  # one pixel out of 9
        "R": (.830, .665),  # one pixel out of 9
        "W": (6.9, 6.9),  # one of 4 segments of a circle
    }
    
    matrix_id: Mapped[int | None] = mapped_column(
        ForeignKey("matrix.id", name="chip__matrix", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    matrix: Mapped["Matrix"] = relationship(back_populates="chips")  # noqa: F821
    
    @property
    def x_coordinate(self):
        coords = re.sub(rf'^{self.type}', '', self.name)
        match = self.xcoord_re.match(coords)
        
        # get matrix coordinate * (matrix.width + 1) + 2nd index * chip_size[0]
        return int(match.group('matrix')) + int(match.group('px')) / (self.matrix.width + 1)
    
    @property
    def width(self):
        return 1 / self.matrix.width
    
    @property
    def y_coordinate(self):
        coords = re.sub(rf'^{self.type}', '', self.name)
        match = self.ycoord_re.match(coords)
        
        return int(match.group('matrix')) + int(match.group('px')) / (self.matrix.height + 1)
    
    @property
    def height(self):
        return 1 / self.matrix.height


class EqeChip(SimpleChip):
    """
    Represents chips used in EQE measurements.
    """
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
        subclasses = cls.get_all_subclasses(AbstractChip)
        cls.chip_types = {
            subclass.__mapper_args__["polymorphic_identity"]: subclass
            for subclass in subclasses
            if "polymorphic_identity" in subclass.__mapper_args__}
    
    def get_all_subclasses(cls, target: type[AbstractChip]) -> list[type[AbstractChip]]:
        all_subclasses = []
        
        for subclass in target.__subclasses__():
            all_subclasses.append(subclass)
            all_subclasses.extend(cls.get_all_subclasses(subclass))
        
        return all_subclasses


def is_simple_chip_type(cls: type[AbstractChip]) -> TypeGuard[Type[SimpleChip]]:
    return issubclass(cls, SimpleChip)


class ChipRepository(AbstractRepository[AbstractChip], metaclass=ChipRepositoryMeta):
    model = AbstractChip
    chip_types: dict[str, type[AbstractChip]]
    
    @classmethod
    def get_chip_class(cls, chip_type: str) -> type[AbstractChip]:
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
    def create(cls, **kwargs) -> AbstractChip:
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
    
    def get_or_create_chips_for_wafer(self, chip_names, wafer_name) -> list[AbstractChip]:
        from .wafer import WaferRepository
        
        chip_names = [name.upper() for name in chip_names]
        wafer_repo = WaferRepository(self.session)
        wafer = wafer_repo.get_or_create(name=wafer_name)
        if wafer.id is not None:  # wafer already exists
            existing_chips = self.get_all_by(
                AbstractChip.wafer == wafer,
                AbstractChip.name.in_(chip_names)
            )
            existing_chip_names = {chip.name for chip in existing_chips}
            chip_names_to_create = set(chip_names) - existing_chip_names
        else:
            chip_names_to_create = chip_names
            existing_chips = []
        
        created_chips = []
        for chip_name in chip_names_to_create:
            chip = self.create(name=chip_name, wafer=wafer)
            created_chips.append(chip)

        chips_dict = {chip.name: chip for chip in created_chips + existing_chips}
        return [chips_dict[chip_name] for chip_name in chip_names]  # preserve order
