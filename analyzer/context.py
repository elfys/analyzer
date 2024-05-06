import logging

import click
from sqlalchemy.orm import Session


class AnalyzerContext:
    def __init__(self) -> None:
        self._logger = None
        self._session = None

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            raise AttributeError("Logger is not set")
        return self._logger

    @logger.setter
    def logger(self, logger: logging.Logger) -> None:
        self._logger = logger
        
    def is_logger_set(self) -> bool:
        return self._logger is not None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise AttributeError("Session is not set")
        return self._session

    @session.setter
    def session(self, session: Session) -> None:
        self._session = session
        
    def is_session_set(self) -> bool:
        return self._session is not None
    

pass_analyzer_context = click.make_pass_decorator(AnalyzerContext)
