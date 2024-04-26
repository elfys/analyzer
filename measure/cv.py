import click
from sqlalchemy.orm import Session

from orm import (
    CVMeasurement,
    ChipState,
)
from utils import (
    EntityOption,
    validate_chip_names,
)
from .common import (
    get_chips_for_names,
    get_raw_measurements,
    set_configs,
    validate_measurements,
)


@click.command(name="cv", help="Measure CV data of the current chip.")
@click.pass_context
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
    "automatic_mode",
    is_flag=True,
    help="Automatic measurement mode. Invalid measurements will be skipped.",
)
def cv(
    ctx: click.Context,
    chip_names: tuple[str],
    wafer_name: str,
    chip_state: ChipState,
    automatic_mode: bool,
):
    session: Session = ctx.obj["session"]
    configs: dict = ctx.obj["configs"]
    
    chips = get_chips_for_names(chip_names, wafer_name)
    
    for setup_config in configs["setups"]:
        ctx.obj["logger"].info(f'Executing setup {setup_config["name"]}')
        set_configs(setup_config["instrument"])
        raw_measurements = get_raw_measurements()
        
        validate_measurements(raw_measurements, setup_config, automatic_mode)
        
        for chip, chip_config in zip(chips, configs["chips"], strict=True):
            measurements_kwargs = dict(
                chip_state_id=chip_state.id,
                chip=chip,
                **setup_config["program"]["measurements_kwargs"],
            )
            measurements = create_measurements(raw_measurements, chip_config, **measurements_kwargs)
            session.add_all(measurements)
    session.commit()
    ctx.obj["logger"].info("Measurements saved")


def create_measurements(
    raw_measurements: dict[str, list], chip_config: dict, **kwargs
) -> list[CVMeasurement]:
    raw_measurements.get("voltage")
    kwarg_keys = list(chip_config.keys())
    
    grouped_numbers = []
    for key in kwarg_keys:
        s = slice(*chip_config[key].get("slice", [None]))
        p = chip_config[key].get("prop", None)
        grouped_numbers.append(raw_measurements[p][s])
    measurements = []
    
    for data in zip(*grouped_numbers, strict=True):
        measurement_kwargs = dict(zip(kwarg_keys, data, strict=True))
        measurements.append(CVMeasurement(**measurement_kwargs, **kwargs))
    return measurements
