from collections.abc import Callable
from typing import TypeVar, Optional

import click

from .name_id_interface import is_name_id_sequence

T = TypeVar('T')

#def select_one[T](
def select_one(
    items: list[T],
    prompt: str,
    id_name_getter: Callable[[T], tuple[int, str]] | None = None,
) -> T:
    """
    Prompt the user to select a single item from a list via the command line.

    This function displays a list of items with associated IDs and names, then
    prompts the user to select one by entering the corresponding ID. It utilizes
    the `click` library to handle the command-line interface.
    """

    if id_name_getter is None:
        if is_name_id_sequence(items):
            items_dict = {
                str(item.id): {"name": item.name, "item": item} for item in items
            }
        else:
            raise RuntimeError("id_name_getter is required for this type of items")
    else:
        items_dict = {
            str(id_name_getter(item)[0]): {
                "name": id_name_getter(item)[1],
                "item": item,
            }
            for item in items
        }

    option_type = click.Choice(list(items_dict.keys()))
    option_help = "\n".join(
        ["{} - {};".format(i, v["name"]) for i, v in items_dict.items()]
    )

    selected_id = click.prompt(
        f"{prompt}\n{option_help}",
        type=option_type,
        show_choices=False,
        prompt_suffix="\n",
    )

    return items_dict[selected_id]["item"]
