import logging
import os
from typing import Union

import click
import sentry_sdk
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from orm import ClientVersion
from utils import get_db_url
from version import VERSION
from .compare import compare_group
from .db import db_group, set_db
from .parse import parse_group
from .show import show_group
from .summary import summary_group

LOGO = """
\b  █████╗  ███╗   ██╗  █████╗  ██╗   ██╗   ██╗ ███████╗ ███████╗ ██████╗
\b ██╔══██╗ ████╗  ██║ ██╔══██╗ ██║   ╚██╗ ██╔╝ ╚══███╔╝ ██╔════╝ ██╔══██╗
\b ███████║ ██╔██╗ ██║ ███████║ ██║    ╚████╔╝    ███╔╝  █████╗   ██████╔╝
\b ██╔══██║ ██║╚██╗██║ ██╔══██║ ██║     ╚██╔╝    ███╔╝   ██╔══╝   ██╔══██╗
\b ██║  ██║ ██║ ╚████║ ██║  ██║ ███████╗ ██║    ███████╗ ███████╗ ██║  ██║
\b ╚═╝  ╚═╝ ╚═╝  ╚═══╝ ╚═╝  ╚═╝ ╚══════╝ ╚═╝    ╚══════╝ ╚══════╝ ╚═╝  ╚═╝
"""


@click.group(
    commands=[summary_group, db_group, show_group, parse_group, compare_group],
    help=f"{LOGO}\nVersion: {VERSION}",
)
@click.pass_context
@click.option(
    "--log-level",
    default="INFO",
    help="Log level.",
    show_default=True,
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
)
@click.option("--db-url", help="Database URL.", default=os.environ.get('DB_URL', None))
def analyzer(ctx: click.Context, log_level: str, db_url: Union[str, None]):
    ctx.obj = ctx.obj or {}
    if "logger" in ctx.obj:
        logger = ctx.obj.get("logger")
    else:
        logger = logging.getLogger("analyzer")
        logger.setLevel(log_level)

    ctx.obj["logger"] = logger
    debug = log_level == "DEBUG"

    active_command = analyzer.commands[ctx.invoked_subcommand]
    if active_command is not db_group:
        try:
            if db_url is None and not os.environ.get("DEV", False):
                db_url = get_db_url()
            engine = create_engine(db_url, echo="debug" if debug else False)
            ctx.call_on_close(lambda: engine.dispose(close=True))
            session = Session(bind=engine, autoflush=False, autocommit=False, future=True)
            ctx.with_resource(session.begin())
            ctx.obj["session"] = session
            latest = session.query(ClientVersion).one()
            if ClientVersion(version=VERSION) < latest:
                logger.warning(
                    f"Your analyzer version seems outdated. Your version {VERSION}, latest available version {latest.version}. Consider upgrading."
                )
        except OperationalError as e:
            if "Access denied" in str(e):
                logger.warning(
                    f"Access denied to database. Try again or run {set_db.name} command to set new credentials."
                )
            else:
                logger.error(f"Error connecting to database: {e}")
                sentry_sdk.capture_exception(e)
            ctx.exit()
