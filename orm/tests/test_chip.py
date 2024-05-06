from unittest.mock import patch

import pytest

from orm import chip as chip_module
from orm.chip import (
    ChipRepository,
    SimpleChip,
)

ALL_CHIP_TYPES = [
    "A", "B", "C", "D", "E", "F", "G", "I", "IH", "IM", "J", "JH", "JM", "L", "LH", "LM", "REF",
    "TS", "U", "UH", "V", "VH", "X", "XH", "Y", "YH"
]


class TestChipRepository:
    @pytest.mark.parametrize('chip_type', ALL_CHIP_TYPES)
    def test_create_creates_chip_of_correct_type(self, chip_type):
        chip = ChipRepository.create(name=f'{chip_type}1234')
        assert isinstance(chip, chip_module.Chip)
    
    def test_get_area_for_simple_chip(self):
        result = ChipRepository.get_area('A')
        assert pytest.approx(result) == 2.8561
    
    def test_get_area_for_non_simple_chip_raises_error(self):
        with pytest.raises(AttributeError):
            ChipRepository.get_area('TS')
    
    def test_get_perimeter_for_simple_chip(self):
        result = ChipRepository.get_perimeter('A')
        assert pytest.approx(result) == 6.76
    
    def test_get_perimeter_for_non_simple_chip_raises_error(self):
        with pytest.raises(AttributeError):
            ChipRepository.get_perimeter('TS')
    
    def test_infer_chip_type_returns_chip_type(self):
        result = ChipRepository.infer_chip_type('A1234')
        assert result == 'A'
    
    def test_infer_chip_type_with_no_chip_type_raises_error(self):
        with pytest.raises(ValueError):
            ChipRepository.infer_chip_type('1234')
    
    def test_infer_chip_type_with_unknown_chip_type_raises_error(self):
        with patch.dict('orm.chip.ChipRepository.chip_types', {'A': SimpleChip}, clear=True):
            with pytest.raises(ValueError):
                ChipRepository.infer_chip_type('B1234')
    
    @pytest.mark.parametrize('chip_name, expected_type', [
        ('A1234', chip_module.AChip),  # noqa
        ('B1234', chip_module.BChip),  # noqa
        ('C1234', chip_module.CChip),  # noqa
        ('G1234', chip_module.GChip),  # noqa
        ('TS1234', chip_module.TestStructureChip),
    ])
    def test_create_creates_chip_of_inferred_type(self, chip_name, expected_type):
        chip = ChipRepository.create(name=chip_name)
        assert isinstance(chip, expected_type)
    
    def test_create_with_explicit_type_creates_chip_of_that_type(self):
        from orm.chip import GChip  # noqa
        chip = ChipRepository.create(name='A1234', type='G')
        assert isinstance(chip, GChip)
    
    def test_create_with_unknown_type_raises_error(self):
        with patch.dict('orm.chip.ChipRepository.chip_types', {'A': SimpleChip}, clear=True):
            with pytest.raises(ValueError):
                ChipRepository.create(name='A1234', type='B')
    
    @pytest.fixture
    def repo(self, session):
        return ChipRepository(session)
    
    @pytest.fixture
    def ab_chips(self, repo):
        chips = repo.get_or_create_chips_for_wafer(['A1234', 'B1234'], 'wafer')
        return chips
    
    def test_get_or_create_chips_for_wafer_returns_correct_number_of_chips(self, ab_chips):
        assert len(ab_chips) == 2
    
    def test_get_or_create_chips_for_wafer_returns_correct_chip_type(self, ab_chips):
        from orm.chip import AChip, BChip  # noqa
        assert isinstance(ab_chips[0], AChip)
        assert isinstance(ab_chips[1], BChip)
    
    def test_get_or_create_chips_for_wafer_does_not_add_to_session(self, ab_chips, session):
        assert not session.new
    
    def test_get_or_create_chips_for_wafer_does_not_increase_chip_count(self, ab_chips, session):
        assert session.query(chip_module.Chip).count() == 0
    
    def test_get_or_create_chips_for_wafer_after_commit(self, repo, session):
        chips = repo.get_or_create_chips_for_wafer(['A1234', 'B1234'], 'wafer')
        session.add_all(chips)
        assert len(session.new) == 3, "There should be 2 chips and 1 wafer in session"
        session.commit()
        
        chips = repo.get_or_create_chips_for_wafer(['A1234', 'B8931'], 'wafer')
        assert len(chips) == 2
        session.add_all(chips)
        assert len(session.new) == 1
    
    def test_get_or_create_chips_for_wafer_no_chips_exist(self, repo):
        chips = repo.get_or_create_chips_for_wafer(['A1234', 'B1234'], 'wafer')
        assert len(chips) == 2
        assert all(isinstance(chip, SimpleChip) for chip in chips)
    
