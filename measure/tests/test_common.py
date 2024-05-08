import itertools
from unittest.mock import patch

import click
import pytest

from measure import MeasureContext
from measure.common import (
    validate_chip_names,
    validate_measurements,
)


class TestValidateChipNames:
    @pytest.fixture
    def ctx(self, runner):
        ctx = click.Command('test').make_context('test', [])
        ctx.ensure_object(MeasureContext)
        return ctx
    
    @pytest.fixture
    def param(self):
        return click.Option(['--chip-name'], multiple=True, callback=validate_chip_names)
    
    def test_validate_chip_names_with_matrix_config(self, ctx, param):
        ctx.obj.configs = {'matrix': True}
        result = validate_chip_names(ctx, param, ['chip1'])
        assert result == ('CHIP1',)
    
    def test_validate_chip_names_without_matrix_config_unique_names(self, ctx, param):
        ctx.obj.configs = {'chips': ['chip1', 'chip2']}
        result = validate_chip_names(ctx, param, ['chip1', 'chip2'])
        assert result == ('CHIP1', 'CHIP2')
    
    def test_validate_chip_names_without_matrix_config_duplicate_names(self, ctx, param):
        ctx.obj.configs = {'chips': ['chip1', 'chip2']}
        with pytest.raises(click.BadParameter,
                           match='--chip-name parameter is invalid. Chip names must be unique.'):
            validate_chip_names(ctx, param, ['chip1', 'chip1'])
    
    def test_validate_chip_names_without_matrix_config_incorrect_number_of_names(self, ctx, param):
        ctx.obj.configs = {'chips': ['chip1', 'chip2', 'chip3']}
        with pytest.raises(click.BadParameter,
                           match='--chip-name parameter is invalid. 3 chip names expected, based on provided config file.'):
            validate_chip_names(ctx, param, ['chip1', 'chip2'])


class TestValidateMeasurements:
    @pytest.fixture
    def validation_config_min(self):
        return {"program": {"validation": {"capacitance[-1]": {
            "min": {"value": -4e-13, "message": "Too low"}
        }}}}
    
    @pytest.fixture
    def validation_config_max(self):
        return {"program": {"validation": {"capacitance[-1]": {
            "max": {"value": 1e-5, "message": "Too high"}
        }}}}
    
    @pytest.fixture
    def validation_config_abs(self):
        return {"program": {"validation": {"capacitance[-1]": {
            "max": {"value": 3e-13, "abs": True, "message": "Too high by module"}
        }}}}
    
    @pytest.fixture
    def too_low_measurements(self):
        return {
            'capacitance': [-6.25e-13, -6.20e-13, -5.99e-13, -5.97e-13],
            'voltage_input': [-15.0, -10.0, -5.0, 0.0]
        }
    
    @pytest.fixture
    def too_high_measurements(self):
        return {
            'capacitance': [-6.25e-13, -6.20e-13, -5.99e-13, 1],
            'voltage_input': [-15.0, -10.0, -5.0, 0.0]
        }
    
    @pytest.fixture
    def valid_measurements(self):
        return {
            'capacitance': [-6.25e-13, -6.20e-13, -5.99e-13, -2e-13],
            'voltage_input': [-15.0, -10.0, -5.0, 0.0]
        }
    
    @pytest.fixture
    def measurements(self, request):
        return request.getfixturevalue(request.param)
    
    @pytest.fixture
    def config(self, request):
        return request.getfixturevalue(request.param)
    
    @pytest.mark.parametrize("measurements, automatic", itertools.product(
        ['valid_measurements', 'too_high_measurements', 'too_low_measurements'], [True, False]),
                             indirect=['measurements'])
    def test_validate_measurements_with_no_validation_config(
        self, ctx_obj,
        measurements,
        automatic
    ):
        config = {"program": {}}
        with click.Context(click.Command('test'), obj=ctx_obj):
            assert validate_measurements(measurements, config, automatic) is None
    
    @pytest.mark.parametrize("config, automatic", itertools.product(
        ["validation_config_min", "validation_config_max", "validation_config_abs"],
        [True, False]
    ), indirect=["config"])
    def test_validate_measurements_with_valid_measurements(
        self,
        ctx_obj,
        valid_measurements,
        config,
        automatic
    ):
        with click.Context(click.Command('test'), obj=ctx_obj):
            assert validate_measurements(valid_measurements, config, automatic) is None
    
    @pytest.mark.parametrize("measurements, config, msg", [
        ('too_low_measurements', 'validation_config_min', "Too low"),
        ('too_low_measurements', 'validation_config_abs', "Too high by module"),
        ('too_high_measurements', 'validation_config_max', "Too high"),
    ], indirect=['measurements', 'config'])
    def test_validate_invalid_measurements(
        self, ctx_obj,
        measurements,
        config,
        msg,
        log_handler
    ):
        automatic = False
        
        with patch('click.confirm', return_value=True) as confirm_mock:
            with click.Context(click.Command('test'), obj=ctx_obj):
                validate_measurements(measurements, config, automatic)
            confirm_mock.assert_called_once()
        assert len(log_handler.records) == 1
        assert msg in str(log_handler.records[0].message)
    
    @pytest.mark.parametrize("measurements, config, msg", [
        ('too_low_measurements', 'validation_config_min', "Too low"),
        ('too_low_measurements', 'validation_config_abs', "Too high by module"),
        ('too_high_measurements', 'validation_config_max', "Too high"),
    ], indirect=['measurements', 'config'])
    def test_validate_invalid_measurements_in_automatic_mode(
        self, ctx_obj,
        measurements,
        config,
        msg,
        log_handler
    ):
        automatic = True
        
        with pytest.raises(RuntimeError, match="Measurement is invalid"):
            with patch('click.confirm', return_value=True) as confirm_mock:
                with click.Context(click.Command('test'), obj=ctx_obj):
                    validate_measurements(measurements, config, automatic)
                confirm_mock.assert_not_called()
        assert len(log_handler.records) == 1
        assert msg in str(log_handler.records[0].message)
    
    def test_validate_measurements_with_unexpected_measurements(
        self, ctx_obj,
        validation_config_min,
    ):
        automatic = False
        unexpected_measurements = {
            'voltage_input': [-15.0, -10.0, -5.0, 0.0],
            'unexpected': [1, 2, 3, 4]
        }
        with pytest.raises(click.BadParameter, match=r'Value "capacitance\[.*\]" not found in .*'):
            with click.Context(click.Command('test'), obj=ctx_obj):
                validate_measurements(unexpected_measurements, validation_config_min, automatic)
    
    def test_validate_measurements_with_incorrect_validation_config(
        self, ctx_obj,
        valid_measurements,
        log_handler
    ):
        automatic = False
        incorrect_config = {"program": {"validation": {"capacitance[-1]": {"incorrect": {}}}}}
        with pytest.raises(click.BadParameter, match='Unknown validator format in "incorrect"'):
            with click.Context(click.Command('test'), obj=ctx_obj):
                validate_measurements(valid_measurements, incorrect_config, automatic)
