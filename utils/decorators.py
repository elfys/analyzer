from functools import wraps
from typing import (
    Callable,
    cast,
)

import click


def remember_choice[F: Callable](message: str):
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
