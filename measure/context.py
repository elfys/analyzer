import logging
from functools import wraps
from typing import (
    Callable,
    Concatenate,
    ParamSpec,
    TypeVar,
)

import click
from sqlalchemy.orm import Session

from .instrument import InstrumentsTypes


class MeasureContext:
    def __init__(
        self,
        logger: logging.Logger | None = None,
        session: Session | None = None,
        instruments: dict[str, InstrumentsTypes] | None = None,
        configs: dict | None = None
    ):
        self.logger = logger
        self.session = session
        self.instruments = instruments or {}
        self.configs = configs or {}


pass_measure_context = click.make_pass_decorator(MeasureContext)

P = ParamSpec("P")
R = TypeVar("R")


def from_config[T](path: str, arg_name: str):
    def get() -> T:
        ctx = click.get_current_context().find_object(MeasureContext)
        obj = ctx.configs
        for key in path.split('.'):
            if key not in obj:
                raise KeyError(f"Key '{key}' not found in config object.")
            obj = obj[key]
        return obj
    
    def decorator(func: Callable[Concatenate[T, P], R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs):
            if arg_name in kwargs:
                return func(*args, **kwargs)
            
            kwargs[arg_name] = get()
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
