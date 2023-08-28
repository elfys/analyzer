from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from orm import Misc


def get_thresholds(
    session: Session, kind: Literal["IV", "CV"], precision=Decimal("1e-2")
) -> dict[str, dict[Decimal, float]]:
    if kind == "IV":
        thresholds = session.execute(
            select(Misc.data).where(Misc.name == "iv_thresholds")
        ).scalar_one()
    elif kind == "CV":
        thresholds = session.execute(
            select(Misc.data).where(Misc.name == "cv_thresholds")
        ).scalar_one()
    else:
        raise ValueError(f"Unknown threshold kind: {kind}")

    return {
        chip_type: {
            Decimal(voltage).quantize(precision): threshold
            for voltage, threshold in chip_type_thresholds.items()
        }
        for chip_type, chip_type_thresholds in thresholds.items()
    }
