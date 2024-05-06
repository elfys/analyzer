from typing import (
    Protocol,
    Sequence,
    TypeGuard,
    runtime_checkable,
)

from sqlalchemy.orm import Mapped


@runtime_checkable
class NameIdInterface(Protocol):
    id: Mapped[int]
    name: Mapped[str]


def is_name_id_sequence(
    obj_list: Sequence,
) -> TypeGuard[Sequence[NameIdInterface]]:
    return isinstance(obj_list[0], NameIdInterface)
