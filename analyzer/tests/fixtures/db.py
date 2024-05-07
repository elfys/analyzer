import pytest
from sqlalchemy import (
    insert,
)

from orm import (
    Chip,
    ChipRepository,
    IVMeasurement,
    IvConditions,
    Misc,
    Wafer,
)


@pytest.fixture(scope="class")
def wafer(request):
    wafer_name = request.param
    yield Wafer(name=wafer_name)


@pytest.fixture(scope="class")
def chips(request):
    chip_names = request.param
    yield [ChipRepository.create(name=chip_name) for chip_name in chip_names]


@pytest.fixture(scope="class")
def iv_conditions(chips):
    yield [
        IvConditions(
            instrument_id=1,
            chip_state_id=i // 4 + 1,
        )
        for i in range(len(chips))
    ]


@pytest.fixture(scope="class")
def db(wafer, chips, iv_thresholds, session):
    session.query(Chip).delete()
    session.query(Wafer).delete()
    session.query(Misc).delete()
    
    session.execute(insert(Misc).values(name="iv_thresholds", data=iv_thresholds))
    voltage_measure = {
        "-1": [1, 2, 3, 4, 1, 2, 3, 4],
        "-0.01": list(range(8)),
        "0": [0, 0, 0, 0, 0, 0, 0, 0],
        "0.01": list(range(8)),
        "6": list(range(8)),
    }
    wafer.chips = chips
    session.add(wafer)
    session.commit()
    for i, chip in enumerate(chips):
        chip.iv_conditions.append(
            IvConditions(
                instrument_id=1,
                chip_state_id=i // 4 + 1,
            )
        )
        for voltage, measures in voltage_measure.items():
            chip.iv_conditions[0].measurements.append(
                IVMeasurement(voltage_input=voltage, anode_current=measures.pop())
            )
    session.add(wafer)
    session.commit()
