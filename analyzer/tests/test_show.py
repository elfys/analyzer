from datetime import datetime

import pytest
from click.testing import CliRunner
from sqlalchemy import text
from sqlalchemy.orm import Session

from analyzer import analyzer
from analyzer.show import show_wafers
from orm import (
    Chip,
    Wafer,
    XChip,
)


class TestShowWafers:
    chip_numbers = [108, 99, 3]
    
    @pytest.fixture(autouse=True, scope="class")
    def db(self, session: Session):
        session.query(Chip).delete()
        session.query(Wafer).delete()
        session.execute(text("ALTER TABLE wafer AUTO_INCREMENT = 1"))  # reset id generator
        session.commit()
        
        wafers = [
            Wafer(name="AB4", batch_id="PFM2B", type="PD", record_created_at=datetime(2023, 5, 26)),
            Wafer(name="AB5", batch_id="MA0002C", record_created_at=datetime(2022, 12, 6)),
            Wafer(
                name="AY8",
                batch_id="Pilotrun",
                type="AHMA",
                record_created_at=datetime(2023, 2, 11),
            ),
        ]
        for i, wafer in enumerate(wafers):
            wafer.chips = [XChip(name=f"X{j:04}") for j in range(self.chip_numbers[i])]
        
        session.add_all(wafers)
        session.commit()
        yield
    
    def test_invoke_from_root_group(self, runner):
        result = runner.invoke(analyzer, ["show", "wafers"])
        assert result.exit_code == 0
    
    def test_show_table(self, runner: CliRunner, ctx_obj):
        result = runner.invoke(show_wafers, obj=ctx_obj)
        assert result.exit_code == 0
        assert (
            result.output
            == """\
         Name      Created at           Batch       Type    Chips
id                                                               
1         AB4      2023-05-26           PFM2B         PD      108
3         AY8      2023-02-11        Pilotrun       AHMA        3
2         AB5      2022-12-06         MA0002C                  99
"""
        )
    
    def test_show_json(self, runner: CliRunner, ctx_obj):
        result = runner.invoke(show_wafers, ["--json"], obj=ctx_obj)
        assert result.exit_code == 0
        assert (
            result.output
            == """\
{
    "1":{
        "name":"AB4",
        "record_created_at":1685059200000,
        "batch_id":"PFM2B",
        "type":"PD",
        "chips_count":108
    },
    "3":{
        "name":"AY8",
        "record_created_at":1676073600000,
        "batch_id":"Pilotrun",
        "type":"AHMA",
        "chips_count":3
    },
    "2":{
        "name":"AB5",
        "record_created_at":1670284800000,
        "batch_id":"MA0002C",
        "type":null,
        "chips_count":99
    }
}
"""
        )
