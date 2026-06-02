"""
Safety-net tests for the future interrogation-area validation API.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from services.settings_validation import validate_interrogation_areas
    from services.settings_validation import normalize_interrogation_areas
except ImportError:
    validate_interrogation_areas = None
    normalize_interrogation_areas = None


def _validate_interrogation_areas(values):
    if validate_interrogation_areas is None:
        pytest.fail("services.settings_validation.validate_interrogation_areas is not implemented yet")
    return validate_interrogation_areas(values)


def _normalize_interrogation_areas(values):
    if normalize_interrogation_areas is None:
        pytest.fail("services.settings_validation.normalize_interrogation_areas is not implemented yet")
    return normalize_interrogation_areas(values)


class TestInterrogationAreaValidation:
    def test_requires_first_pass_area(self):
        is_valid, num_passes, error_msg = _validate_interrogation_areas(
            ["none", 32, "none", "none", "none", "none"]
        )

        assert is_valid is False
        assert num_passes == 0
        assert error_msg

    def test_rejects_non_numeric_area_values(self):
        is_valid, num_passes, error_msg = _validate_interrogation_areas(
            [64, "bad", "none", "none", "none", "none"]
        )

        assert is_valid is False
        assert num_passes == 0
        assert error_msg

    def test_rejects_increasing_pass_sizes(self):
        is_valid, num_passes, error_msg = _validate_interrogation_areas(
            [32, 64, "none", "none", "none", "none"]
        )

        assert is_valid is False
        assert num_passes == 0
        assert error_msg

    def test_counts_passes_until_first_none(self):
        is_valid, num_passes, error_msg = _validate_interrogation_areas(
            [64, 32, 16, "none", "none", "none"]
        )

        assert is_valid is True
        assert num_passes == 3
        assert error_msg == ""


class TestInterrogationAreaNormalization:
    def test_normalizes_numeric_values_for_ui_settings_merge(self):
        normalized, num_passes, error_msg = _normalize_interrogation_areas(
            ["64", 32, "none", "none", "none", "none"]
        )

        assert normalized == [64, 32, "none", "none", "none", "none"]
        assert num_passes == 2
        assert error_msg == ""
