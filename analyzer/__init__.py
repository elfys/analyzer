import logging
import os

import click
import sentry_sdk
from sqlalchemy import (
    URL,
    create_engine,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from orm import ClientVersion
from utils import get_db_url
from version import VERSION
from .compare import compare_group
from .context import AnalyzerContext
from .db import (
    db_group,
    set_db,
)
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
@click.option("--db-url", help="Database URL.", default=lambda: os.environ.get('DB_URL', None))
def analyzer(ctx: click.Context, log_level: str, db_url: str | URL | None):
    ctx_obj = ctx.ensure_object(AnalyzerContext)
    ctx_obj.logger = logging.getLogger("analyzer")
    ctx_obj.logger.setLevel(log_level)
    
    debug = log_level == "DEBUG"
    
    active_command = analyzer.commands.get(ctx.invoked_subcommand, None)
    if active_command and active_command is not db_group:
        try:
            if db_url is None:
                db_url = get_db_url()
            engine = create_engine(db_url, echo="debug" if debug else False)
            ctx.call_on_close(lambda: engine.dispose(close=True))
            session = Session(bind=engine, autoflush=False, autocommit=False, future=True)
            ctx.with_resource(session.begin())
            ctx_obj.session = session
            latest = session.query(ClientVersion).one()
            if ClientVersion(version=VERSION) < latest:
                ctx_obj.logger.warning(
                    f"Your analyzer version seems outdated. Your version {VERSION}, latest available version {latest.version}. Consider upgrading."
                )
        except OperationalError as e:
            if "Access denied" in str(e):
                ctx_obj.logger.warning(
                    f"Access denied to database. Try again or run {set_db.name} command to set new credentials."
                )
            else:
                ctx_obj.logger.error(f"Error connecting to database: {e}")
                sentry_sdk.capture_exception(e)
            ctx.exit(1)
