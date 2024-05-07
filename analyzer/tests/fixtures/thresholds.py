import pytest


@pytest.fixture(scope="class")
def iv_thresholds(session):
    return {
        "X": {"-1": 1, "0.01": 2, "10": 3, "20": 5},
        "G": {
            "-1": 2,
            "0.01": 5,
            "6": 10,
        },
    }
