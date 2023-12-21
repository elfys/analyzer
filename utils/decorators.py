from functools import wraps

import click


def remember_choice(message: str):
    def decorate(fn: callable):
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
        
        return wrapper
    
    return decorate
