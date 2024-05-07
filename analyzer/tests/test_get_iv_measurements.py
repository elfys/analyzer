import pytest

from analyzer.summary.iv import get_iv_measurements
from orm import (
    IVMeasurement,
    IvConditions,
)


class TestGetIvMeasurements:
    @pytest.fixture
    def sample_conditions(self):
        low_amplitude_measurements = [
            IVMeasurement(voltage_input=-0.01, cathode_current=1),
            IVMeasurement(voltage_input=0.00, cathode_current=2),
            IVMeasurement(voltage_input=0.01, cathode_current=3)
        ]
        high_amplitude_measurements = [
            IVMeasurement(voltage_input=-1, cathode_current=40),
            IVMeasurement(voltage_input=0, cathode_current=50),
            IVMeasurement(voltage_input=1, cathode_current=60)
        ]
        conditions = [
            IvConditions(id=1, measurements=low_amplitude_measurements, chip_id=1),
            IvConditions(id=2, measurements=high_amplitude_measurements, chip_id=1),
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
    def test_get_measurements_ordering(self, sample_conditions, reverse):
        if reverse:
            sample_conditions = list(reversed(sample_conditions))
        results = get_iv_measurements(sample_conditions)
        zero_measurement = [m for m in results if
                            m.conditions.chip_id == 1 and m.voltage_input == 0]
        assert len(zero_measurement) == 1, "Should have one measurement with voltage 0"
        assert zero_measurement[0].cathode_current == 2, \
            "Should have the measurement with low amplitude"
