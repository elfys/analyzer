import logging

import click
from sqlalchemy.orm import Session


class AnalyzerContext:
    def __init__(
        self,
        logger: logging.Logger = None,
        session: Session = None,
    ):
        self.logger = logger
        self.session = session


pass_analyzer_context = click.make_pass_decorator(AnalyzerContext)
