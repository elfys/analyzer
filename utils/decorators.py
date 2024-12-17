from functools import wraps
from typing import (
    Callable,
    TypeVar,
    cast,
)

import click

F = TypeVar('F', bound=Callable)

#def remember_choice[F: Callable](message: str):
def remember_choice(message: str):
    """
    Decorator to remember a user's choice and optionally apply it to subsequent calls.

    This decorator wraps a function that returns a choice (e.g., user input) and,
    after the first execution, prompts the user to confirm if the same choice should
    be used for all future calls. If confirmed, the choice is stored and returned
    directly in subsequent calls without re-executing the original function.

    Parameters:
        message (str): A confirmation message displayed to the user, which can include
                       placeholders for formatting with the choice.

    Returns:
        Callable: A decorator that wraps the original function.
    """

    def decorate(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                if fn.__previous_choice is not None:
                    return fn.__previous_choice
                ask = False
            except AttributeError:
                ask = True
            choice = fn(*args, **kwargs)
            if ask:
                apply_to_all = click.confirm(message.format(str(choice)), default=False)
                fn.__previous_choice = choice if apply_to_all else None
            return choice

        return cast(F, wrapper)

    return decorate
