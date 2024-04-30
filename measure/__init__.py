import logging
import os

import click
import sentry_sdk
import yaml
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from utils import get_db_url
from .context import MeasureContext
from .cv import cv
from .instrument import InstrumentFactory
from .iv import measure_iv_command


@click.group(name="measure", commands=[measure_iv_command, cv])
@click.pass_context
@click.option(
    "-c",
    "--config",
    "config_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to config file. See ./measure/configs/*.yaml",
)
@click.option(
    "--log-level",
    default="INFO",
    help="Log level.",
    show_default=True,
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
)
@click.option("--db-url", help="Database URL.", default=os.environ.get("DB_URL"))
@click.option("--simulate", is_flag=True, help="Simulate pyvisa instrument.", default=False)
def measure_group(
    ctx: click.Context,
    config_path: str,
    log_level: str,
    db_url: str | None,
    simulate: bool,
):
    ctx_obj = ctx.ensure_object(MeasureContext)
    
    if ctx_obj.logger is None:
        ctx_obj.logger = logging.getLogger("measure")
        ctx_obj.logger.setLevel(log_level)
    
    debug = log_level == "DEBUG"
    
    with click.open_file(config_path) as config_file:
        ctx_obj.configs = yaml.safe_load(config_file)
    
    try:
        if db_url is None:
            db_url = get_db_url()
        engine = create_engine(db_url, echo="debug" if debug else False)
        session = Session(bind=engine, autoflush=False, autocommit=False, future=True)
        ctx_obj.session = session
        ctx.with_resource(session)
    
    except OperationalError as e:
        if "Access denied" in str(e):
            ctx_obj.logger.warning(
                "Access denied to database. Try again or run set-db command to set new credentials."
            )
        else:
            ctx_obj.logger.error(f"Error connecting to database: {e}")
            sentry_sdk.capture_exception(e)
        ctx.exit(1)
    
    instrument_factory = InstrumentFactory()
    for key, instrument_config in ctx_obj.configs["instruments"].items():
        instrument = instrument_factory(instrument_config, simulate)
        ctx.with_resource(instrument)
        ctx_obj.instruments[key] = instrument
