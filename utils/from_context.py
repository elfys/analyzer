from functools import wraps

import click


def from_context(path, arg_name):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ctx = click.get_current_context()
            obj = ctx.obj
            
            # if arg_name is already in kwargs, skip the injection
            if arg_name in kwargs:
                return func(*args, **kwargs)

            # Navigate through the nested dictionary using the path
            for key in path.split('.'):
                if obj is None or key not in obj:
                    raise KeyError(f"Key '{key}' not found in context object.")
                obj = obj[key]
            # Inject the object as a named argument if arg_name is specified
            kwargs[arg_name] = obj
            return func(*args, **kwargs)
        return wrapper
    return decorator
