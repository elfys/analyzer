import pytest
from sqlalchemy import insert

from orm import Misc


@pytest.fixture(scope="class")
def iv_thresholds(session):
    thresholds = {
        'X': {'-1': 1, '0.01': 2, '10': 3, '20': 5},
        'G': {'-1': 2, '0.01': 5, '6': 10, },
    }
    session.execute(insert(Misc).values(name="iv_thresholds", data=thresholds))
