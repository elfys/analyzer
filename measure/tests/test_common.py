import click
import pytest

from measure import MeasureContext
from measure.common import validate_chip_names


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
        with pytest.raises(ValueError,
                           match='--chip-name parameter is invalid. Chip names must be unique.'):
            validate_chip_names(ctx, param, ['chip1', 'chip1'])
    
    def test_validate_chip_names_without_matrix_config_incorrect_number_of_names(self, ctx, param):
        ctx.obj.configs = {'chips': ['chip1', 'chip2', 'chip3']}
        with pytest.raises(ValueError,
                           match='--chip-name parameter is invalid. 3 chip names expected, based on provided config file.'):
            validate_chip_names(ctx, param, ['chip1', 'chip2'])
