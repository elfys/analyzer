from time import sleep
from typing import cast

import click
import numpy as np

from orm import (
    ChipRepository,
    ChipState,
    IVMeasurement,
    InstrumentRepository,
    IvConditionsRepository,
    Matrix,
    MatrixRepository,
)
from utils import (
    EntityOption,
)
from .common import (
    apply_configs,
    get_raw_measurements,
    preprocess_measurements,
    validate_chip_names,
    validate_measurements,
)
from .context import (
    MeasureContext,
    from_config,
    pass_measure_context,
)
from .exceptions import InvalidMeasurementError
from .instrument import (
    PyVisaInstrument,
    TemperatureInstrument,
)
from .iv import (
    measure_setup as measure_iv_setup,
    measure_matrix
)
from .cv import (
    create_measurements as create_cv_measurements

)


@click.command(name="mux", help="Measure IV and CV data of the current chip using mux card.")
@from_config("instruments.iv.name")
@from_config("instruments.cv.name")
@pass_measure_context
@click.option("-n",
              "--chip-name",
              "chip_names",
              help="Chip name.",
              multiple=True,
              callback=validate_chip_names)
@click.option("-w", "--wafer", "wafer_name", prompt="Input wafer name", help="Wafer name.")
@click.option(
    "-s",
    "--chip-state",
    "chip_state",
    prompt="Input chip state",
    help="State of the chips.",
    cls=EntityOption,
    entity_type=ChipState,
)
@click.option(
    "--auto",
    "automatic",
    is_flag=True,
    help="Automatic measurement mode. Invalid measurements will be skipped.",
)
def mux(
    ctx: MeasureContext,
    iv_instrument_name: str, 
    cv_instrument_name: str, 
    chip_names: tuple[str, ...], 
    wafer_name: str, 
    chip_state: ChipState, 
    automatic: bool, 
):
    """
    Function that allows measuring both iv and cv of singel or multiple pixels by switching the pixel/instrument using mux card.
    Assumptions:
    - Separate yaml file written for mux is needed, otherwise errors will follow.
    - Setup called "iv" measures only iv and cv instrument is not used in any way
    - Setup called "cv" can control both iv and cv instruments but measures only cv. Current measurement at the same is not possible. 

    :param ctx: The context object (provided by the click decorator).
    :param iv_instrument name: Name of the iv instrument taken from yaml file
    :param cv_instrument_name: Name of the cv instrument taken from yaml file
    :param chip_names: Name(s) of the chip(s) to be measured. Asked as input from user if not supplied as argument
    :param wafer_name: Name of the wafer. Asked as input from the user, if not supplied as argument
    :param chip_state: State of the chip to be measured. Asked as input from the user, if not supplied as argument
    :param automatic: Flag indicating if measurement is done in automatic mode (==true)
    :return:
    """
    iv_instrument_id = InstrumentRepository(ctx.session).get_id(name=iv_instrument_name)
    if (matrix_config := ctx.configs.get("matrix")) is not None:
        # Sample contains a matrix of pixels -> creates matrix object and separate chip names for each pixel
        matrix = MatrixRepository(ctx.session).get_or_create_from_configs(
            matrix_name=chip_names[0], wafer_name=wafer_name, matrix_config=matrix_config
        )
        ctx.session.add(matrix)
    else:
        # Sample contains only single pixel -> No need to create matrix object. Instead creates as many chip objects as chip names were given
        chips = ChipRepository(ctx.session).get_or_create_chips_for_wafer(chip_names, wafer_name)
        ctx.session.add_all(chips)
    ctx.session.commit()

    # Loops through all "setups" in the yaml file by first executing the instrument settings part and then executing the actual measurement 
    for setup_config in ctx.configs["setups"]:
        ctx.logger.info(f'Executing setup {setup_config["name"]}')
        if setup_config["name"] is "iv":
            # Setup name is "iv" -> Only Keithley SMU(s) need to be controlled
            apply_configs(setup_config["instrument"], instrument_type = "iv")
            conditions_kwargs = {
                "instrument_id": iv_instrument_id,
                "chip_state_id": chip_state.id,
                **setup_config["program"]["condition_kwargs"]
            }
            
            if (matrix := locals().get('matrix')) is not None:
                # Sample contains matrix of pixels -> matrix measurement is executed
                measure_matrix(matrix, automatic, setup_config, conditions_kwargs)
            else:
                # Sample contains only a single pixel -> single pixel measurement is executed
                measure_iv_setup(automatic, chips, setup_config, conditions_kwargs)
        elif setup_config["name"] is "cv":
            # Setup name is "cv" -> Keithley SMU(s) and Keysight impedance analyzer need to be controlled simultaneously
            apply_configs(setup_config["iv_instrument"], instrument_type = "iv")
            apply_configs(setup_config["cv_instrument"], instrument_type = "cv")
            if (matrix := locals().get('matrix')) is not None:
                chips = sorted(matrix.chips, key=lambda c: c.name)
            else:
                chips = ChipRepository(ctx.session).get_or_create_chips_for_wafer(chip_names, wafer_name)
            ctx.session.add_all(chips)
            ctx.session.commit()
            raw_measurements = get_raw_measurements(sweep_type = "cv")
            for chip, chip_config in zip(chips, ctx.configs["chips"], strict=True):
                measurements_dict = preprocess_measurements(raw_measurements, chip_config)
                validate_measurements(measurements_dict, setup_config, automatic)
                
                measurements_kwargs = dict(
                    chip_state_id=chip_state.id,
                    chip=chip,
                    **setup_config["program"]["measurements_kwargs"],
                )
                measurements = create_cv_measurements(measurements_dict, **measurements_kwargs)
                ctx.session.add_all(measurements)
        else: 
            ... # Setup name is unknown, do nothing 
    ctx.session.commit()
    ctx.logger.info("Measurements saved")



