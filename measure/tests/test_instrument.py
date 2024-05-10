from unittest.mock import (
    MagicMock,
    Mock,
    call,
)

import pytest
from pyvisa import (
    ResourceManager,
)
from pyvisa.resources import MessageBasedResource

from measure.instrument import PyVisaInstrument


@pytest.fixture
def resource_id():
    return "GPIB0::9::INSTR"


@pytest.fixture
def name():
    return "Test Instrument"


@pytest.fixture
def config():
    return {'read_termination': '\n', 'write_termination': '\n'}


@pytest.fixture
def resource_manager():
    resource_manager = Mock(spec=ResourceManager)
    resource_manager.open_resource.return_value = Mock(spec=MessageBasedResource)
    return resource_manager


@pytest.fixture
def instrument(resource_id, name, resource_manager, test_logger):
    return PyVisaInstrument(resource_id, name, {}, resource_manager, test_logger)


class TestPyVisaInstrument:
    def test_enter(self, instrument):
        with instrument as inst:
            assert inst is instrument
            instrument.rm.open_resource.assert_called_once_with(
                instrument.resource_id, **instrument.config)
    
    def test_exit(self, instrument):
        instrument.resource = MagicMock()
        instrument.__exit__(None, None, None)
        instrument.resource.close.assert_called_once()
    
    def test_eq(self, instrument, resource_id, name, config, resource_manager, test_logger):
        other = PyVisaInstrument(resource_id, name, config, resource_manager, test_logger)
        assert instrument == other
    
    def test_getattr(self, instrument):
        instrument.resource = MagicMock()
        instrument.resource.test_attr = "test"
        assert instrument.test_attr == "test"
    
    def test_check_errors(self, instrument, log_handler):
        instrument.name = "Keithley SMU 2636 (Innopoli)"
        instrument.resource = Mock(spec=MessageBasedResource)
        error_message = "-4.20000e+02\tQuery Unterminated\t2.00000e+01\t2.00000e+00"
        instrument.resource.query.side_effect = [
            "1.00000e+00\n",
            error_message,
            "0.00000e+00\n",
            '0.00000e+00\tQueue Is Empty\t0.00000e+00\t2.00000e+00'
        ]
        instrument.check_errors()
        assert instrument.resource.query.call_args_list == [
            call("print(errorqueue.count)"),
            call("print(errorqueue.next())"),
            call("print(errorqueue.count)"),
        ]
        assert log_handler.records[0].message == f"Instrument error: {error_message}"
    
    def test_check_errors_invalid_counter_value(self, instrument, log_handler):
        instrument.name = "Keithley SMU 2636 (Innopoli)"
        instrument.resource = Mock(spec=MessageBasedResource)
        instrument.resource.query.side_effect = [
            "invalid non-numeric value\n",
            "-4.20000e+02\tQuery Unterminated\t2.00000e+01\t2.00000e+00",
        ]
        instrument.check_errors()
        instrument.resource.query.assert_called_once_with("print(errorqueue.count)")
        
        instrument.check_errors()
        instrument.resource.query.assert_called_with("print(errorqueue.count)")
        assert "could not convert string to float" in log_handler.records[0].message
        assert "could not convert string to float" in log_handler.records[1].message
