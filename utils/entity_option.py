import abc
from typing import (
    Any,
    Optional,
)

import click
from click import Context
from sqlalchemy.orm import Session

from orm import Base


class EntityOptionChoice(metaclass=abc.ABCMeta):
    id: int
    name: str
    
    @classmethod
    def __subclasshook__(cls, subclass):
        return (
            issubclass(subclass, Base)
            and hasattr(subclass, "id")
            and subclass.id.type.python_type == int
            and hasattr(subclass, "name")
            and subclass.name.type.python_type == str
        )


class EntityOption(click.Option):
    def __init__(self, *args, entity_type: type[EntityOptionChoice], **kwargs: Any) -> None:
        if not issubclass(entity_type, EntityOptionChoice):
            raise RuntimeError("Given entity_type is not supported")
        self.entity_type = entity_type
        super().__init__(*args, **kwargs)
    
    def type_cast_value(self, ctx: Context, value):
        if isinstance(value, self.entity_type):
            return value
        options = self.get_options(ctx)
        if self.multiple:
            if any(v.upper() == "ALL" for v in value):
                return options
            return [o for o in options if str(o.id) in value]
        else:
            options_dict = {str(o.id): o for o in options}
            return options_dict[value]
    
    def get_options(self, ctx: Context):
        session: Session = ctx.obj["session"]
        return session.query(self.entity_type).order_by(self.entity_type.id).all()
    
    def get_help_record(self, ctx: Context) -> Optional[tuple[str, str]]:
        descriptions = [f"{o.id} - {o.name};" for o in self.get_options(ctx)]
        if self.multiple:
            descriptions.insert(0, "ALL - Select all options;")
        names, help_record = super().get_help_record(ctx)
        return names, help_record + "\n\n\b" + "\n".join([""] + descriptions)
