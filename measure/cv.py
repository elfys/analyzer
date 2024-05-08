import click

from orm import (
    CVMeasurement,
    ChipRepository,
    ChipState,
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
    pass_measure_context,
)


@click.command(name="cv", help="Measure CV data of the current chip.")
@pass_measure_context
@click.option("--chip-name", "-n", "chip_names",
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
    "automatic_mode",
    is_flag=True,
    help="Automatic measurement mode. Invalid measurements will be skipped.",
)
def cv(
    ctx: MeasureContext,
    chip_names: tuple[str],
    wafer_name: str,
    chip_state: ChipState,
    automatic_mode: bool,
):
    chips = ChipRepository(ctx.session).get_or_create_chips_for_wafer(chip_names, wafer_name)
    ctx.session.add_all(chips)
    ctx.session.commit()
    
    for setup_config in ctx.configs["setups"]:
        ctx.logger.info(f'Executing setup {setup_config["name"]}')
        apply_configs(setup_config["instrument"])
        raw_measurements = get_raw_measurements()
        
        for chip, chip_config in zip(chips, ctx.configs["chips"], strict=True):
            measurements_dict = preprocess_measurements(raw_measurements, chip_config)
            validate_measurements(measurements_dict, setup_config, automatic_mode)
            
            measurements_kwargs = dict(
                chip_state_id=chip_state.id,
                chip=chip,
                **setup_config["program"]["measurements_kwargs"],
            )
            measurements = create_measurements(measurements_dict, **measurements_kwargs)
            ctx.session.add_all(measurements)
    ctx.session.commit()
    ctx.logger.info("Measurements saved")


def create_measurements(
    measurements_dict: dict[str, list], **kwargs
) -> list[CVMeasurement]:
    measurements = []
    for values in zip(*measurements_dict.values(), strict=True):
        data = dict(zip(measurements_dict.keys(), values, strict=True))
        measurements.append(CVMeasurement(**data, **kwargs))
    return measurements
