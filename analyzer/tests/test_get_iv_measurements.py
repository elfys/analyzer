from datetime import datetime
from decimal import Decimal

import pytest

from analyzer.summary.iv import get_iv_measurements
from orm import (
    IVMeasurement,
    IvConditions,
)


class TestGetIvMeasurements:
    @pytest.fixture
    def sample_conditions(self):
        def low_amplitude_measurements():
            return [
                IVMeasurement(voltage_input=Decimal(-0.01), cathode_current=1),
                IVMeasurement(voltage_input=Decimal(0.00), cathode_current=2),
                IVMeasurement(voltage_input=Decimal(0.01), cathode_current=3)
            ]
        
        def high_amplitude_measurements():
            return [
                IVMeasurement(voltage_input=Decimal(-1), cathode_current=40),
                IVMeasurement(voltage_input=Decimal(0), cathode_current=50),
                IVMeasurement(voltage_input=Decimal(1), cathode_current=60)
            ]
        
        conditions = [
            IvConditions(id=1, chip_id=1,
                         measurements=low_amplitude_measurements(),
                         datetime=datetime.strptime("2021-01-01", "%Y-%m-%d")),
            IvConditions(id=2, chip_id=1,
                         measurements=high_amplitude_measurements(),
                         datetime=datetime.strptime("2021-01-01", "%Y-%m-%d")),
            IvConditions(id=3,
                         chip_id=1,
                         measurements=low_amplitude_measurements(),
                         datetime=datetime.strptime("2024-01-01", "%Y-%m-%d")),
            IvConditions(id=4,
                         chip_id=1,
                         measurements=high_amplitude_measurements(),
                         datetime=datetime.strptime("2024-01-01", "%Y-%m-%d")),
        ]
        return conditions
    
    def test_get_measurements_deduplication(self, sample_conditions):
        results = get_iv_measurements(sample_conditions)
        assert len(results) == 5, "Should deduplicate by voltage and chip name"
    
    def test_empty_list(self):
        results = get_iv_measurements([])
        assert len(results) == 0, "Should handle empty list of conditions without error"
    
    def test_empty_conditions(self):
        results = get_iv_measurements([IvConditions(measurements=[], chip_id=1)])
        assert len(results) == 0, "Should handle empty conditions without error"
    
    @pytest.mark.parametrize("reverse", [False, True], ids=["normal", "reversed"])
    def test_get_measurements_returns_lowest_amplitude_for_intersect(
        self,
        sample_conditions,
        reverse
    ):
        if reverse:
            sample_conditions = list(reversed(sample_conditions))
        results = get_iv_measurements(sample_conditions)
        zero_measurements = [m for m in results if
                             m.conditions.chip_id == 1 and m.voltage_input == 0]
        assert len(zero_measurements) == 1, "Should have one measurement with voltage 0"
        assert zero_measurements[0].cathode_current == 2, \
            "Should return measurement with lowest amplitude"
    
    @pytest.mark.parametrize("reverse", [False, True], ids=["normal", "reversed"])
    def test_get_measurements_returns_latest(self, sample_conditions, reverse):
        if reverse:
            sample_conditions = list(reversed(sample_conditions))
        results = get_iv_measurements(sample_conditions)
        
        assert len(results) == 5, ("Wrong number of measurements for two sweeps of 3 measurement "
                                   "where both with one measurement for 0")
        expected_date = datetime(2024, 1, 1, 0, 0)
        for measurement in results:
            actual_date = measurement.conditions.datetime
            assert actual_date == expected_date, "Should return latest measurements"
