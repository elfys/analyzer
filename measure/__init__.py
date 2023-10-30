import logging
import os
from typing import Union

import click
import pyvisa
import sentry_sdk
import yaml
from pyvisa import Error
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from utils import get_db_url
from .cv import cv
from .iv import measure_iv


@click.group(name="measure", commands=[measure_iv, cv])
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
@click.option("--db-url", help="Database URL.")
@click.option("--simulate", is_flag=True, help="Simulate pyvisa instrument.", default=False)
def measure_group(
    ctx: click.Context,
    config_path: str,
    log_level: str,
    db_url: Union[str, None],
    simulate: bool,
):
    ctx.obj = ctx.obj or {}
    if "logger" in ctx.obj:
        logger = ctx.obj.get("logger")
    else:
        logger = logging.getLogger("analyzer")
        logger.setLevel(log_level)

    ctx.obj["logger"] = logger
    debug = log_level == "DEBUG"

    with click.open_file(config_path) as config_file:
        configs = yaml.safe_load(config_file)

    ctx.obj["simulate"] = simulate
    ctx.obj["configs"] = configs

    try:
        if db_url is None and not os.environ.get("DEV", False):
            db_url = get_db_url()
        engine = create_engine(db_url, echo="debug" if debug else False)
        session = Session(bind=engine, autoflush=False, autocommit=False, future=True)
        ctx.obj["session"] = session
        ctx.with_resource(session)

    except OperationalError as e:
        if "Access denied" in str(e):
            logger.warning(
                "Access denied to database. Try again or run set-db command to set new credentials."
            )
        else:
            logger.error(f"Error connecting to database: {e}")
            sentry_sdk.capture_exception(e)
        ctx.exit(1)

    try:
        if simulate:
            rm = pyvisa.ResourceManager("measure/simulation.yaml@sim")
            instrument = rm.open_resource(
                "GPIB0::9::INSTR", write_termination="\n", read_termination="\n"
            )
        else:
            pyvisa_config = configs["instruments"]["pyvisa"]
            rm = pyvisa.ResourceManager()
            instrument = rm.open_resource(pyvisa_config["resource"], **pyvisa_config["kwargs"])
            instrument.write("errorqueue.clear()")

        ctx.with_resource(instrument)
        ctx.call_on_close(lambda: check_errors(instrument, logger))
    except Error as e:
        logger.error(f"PYVISA error: {e}")
        ctx.exit()

    ctx.obj["instrument"] = instrument


def check_errors(instrument: pyvisa.resources.MessageBasedResource, logger: logging.Logger):
    while int(float(instrument.query("print(errorqueue.count)"))) > 0:
        error = instrument.query("print(errorqueue.next())")
        logger.warning(f"Instrument error: {error}")
