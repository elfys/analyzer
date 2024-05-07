from unittest.mock import patch

import pytest

from orm import chip as chip_module
from orm.chip import (
    AChip,  # noqa;
    ChipRepository,
    DChip,  # noqa
    FChip,  # noqa
    SimpleChip,
)

ALL_CHIP_TYPES = [
    "A", "B", "C", "D", "E", "F", "G", "I", "IH", "IM", "J", "JH", "JM", "L", "LH", "LM", "REF",
    "TS", "U", "UH", "V", "VH", "X", "XH", "Y", "YH"
]


class TestSimpleChip:
    def test_get_area_with_known_chip_size(self):
        assert AChip.get_area() == pytest.approx(2.8561)  # Assuming the chip size is (1.69, 1.69)
    
    def test_get_area_with_unknown_chip_size(self):
        with pytest.raises(AttributeError, match="Chip size for DChip is unknown"):
            DChip.get_area()
    
    def test_get_perimeter_with_known_chip_size(self):
        assert FChip.get_perimeter() == pytest.approx(7.62)  # Assuming the chip size is (2.56, 1.25)
    
    def test_get_perimeter_with_unknown_chip_size(self):
        with pytest.raises(AttributeError, match="Chip size for DChip is unknown"):
            DChip.get_perimeter()
        
        assert FChip.get_chip_size() == pytest.approx((2.56, 1.25))
    
    def test_get_chip_size_with_unknown_chip_size(self):
        SimpleChip.chip_size = None
        with pytest.raises(AttributeError):
            SimpleChip.get_chip_size()
    
    def test_x_coordinate_with_valid_chip_name(self):
        chip = AChip(name="A1234")
        assert chip.x_coordinate == 12
    
    def test_x_coordinate_with_invalid_chip_name(self):
        chip = AChip(name="A12")
        with pytest.raises(ValueError):
            chip.x_coordinate
    
    def test_y_coordinate_with_valid_chip_name(self):
        chip = AChip(name="A1234")
        assert chip.y_coordinate == 34
    
    def test_y_coordinate_with_invalid_chip_name(self):
        chip = AChip(name="A12")
        with pytest.raises(ValueError):
            assert chip.y_coordinate == 0
    
    def test_chip_repository_get_area_with_known_chip_type(self):
        # Assuming the chip size for type "A" is (1.69, 1.69)
        assert ChipRepository.get_area("A") == pytest.approx(2.8561)
    
    def test_chip_repository_get_area_with_unknown_chip_type(self):
        with pytest.raises(ValueError, match="Unknown chip type Z"):
            ChipRepository.get_area("Z")
    
    def test_chip_repository_get_perimeter_with_known_chip_type(self):
        assert ChipRepository.get_perimeter("A") == 6.76  # Assuming the chip size for type "A" is (1.69, 1.69)
    
    def test_chip_repository_get_perimeter_with_unknown_chip_type(self):
        with pytest.raises(ValueError):
            ChipRepository.get_perimeter("Z")
    
    def test_chip_repository_infer_chip_type_with_known_chip_name(self):
        assert ChipRepository.infer_chip_type("A1234") == "A"
    
    def test_chip_repository_infer_chip_type_with_unknown_chip_name(self):
        with pytest.raises(ValueError):
            ChipRepository.infer_chip_type("Z1234")  # Assuming there is no chip type "Z"


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
        from orm.chip import (
            AChip,
            BChip,  # noqa
        )
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
