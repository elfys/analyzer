from collections.abc import Callable
from typing import TypeVar

import click

T = TypeVar("T")


def select_one(items: list[T], prompt: str, id_name_getter: Callable[[T], (int, str)] = None) -> T:
    if id_name_getter is None:
        
        def id_name_getter(x):
            return x.id, x.name
    
    option_type = click.Choice([str(id_name_getter(item)[0]) for item in items])
    option_help = "\n".join(["{} - {};".format(*id_name_getter(item)) for item in items])
    selected_id = click.prompt(
        f"{prompt}\n{option_help}",
        type=option_type,
        show_choices=False,
        prompt_suffix="\n",
    )
    return next(item for item in items if str(id_name_getter(item)[0]) == selected_id)
