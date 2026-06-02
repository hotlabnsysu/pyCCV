"""
Settings service round-trip tests.
"""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.settings import SettingsService, to_persisted_dict, to_settings_model
from config import BASIC_SETTINGS, PIV_SETTINGS, POSTPROC_SETTINGS


class TestSettingsRoundTrip:
    def test_defaults_loaded_when_no_file(self, tmp_path):
        """Service uses defaults if settings file does not exist."""
        fake_path = str(tmp_path / "nonexistent.json")
        svc = SettingsService(config_path=fake_path)
        assert svc.get("basic", "plot_now") == BASIC_SETTINGS["plot_now"]
        assert svc.get("piv", "int_area_1") == PIV_SETTINGS["int_area_1"]

    def test_save_and_reload(self, tmp_path):
        """Values written by save_settings() are correctly reloaded."""
        cfg = str(tmp_path / "settings.json")
        svc = SettingsService(config_path=cfg)
        svc.settings["basic"]["plot_now"] = 1
        svc.settings["piv"]["int_area_1"] = 128
        svc.save_settings()

        svc2 = SettingsService(config_path=cfg)
        assert svc2.get("basic", "plot_now") == 1
        assert svc2.get("piv", "int_area_1") == 128

    def test_save_keeps_perf_fields_under_basic_section(self, tmp_path):
        """Performance settings persist inside basic, with no top-level perf section."""
        cfg = tmp_path / "settings.json"
        svc = SettingsService(config_path=str(cfg))
        svc.settings["basic"]["compute_mode"] = "cpu_parallel"
        svc.settings["basic"]["num_workers"] = 6

        svc.save_settings()

        saved = json.loads(cfg.read_text(encoding="utf-8"))
        assert "performance" not in saved
        assert "perf" not in saved
        assert saved["basic"]["compute_mode"] == "cpu_parallel"
        assert saved["basic"]["num_workers"] == 6

        svc2 = SettingsService(config_path=str(cfg))
        assert svc2.get("basic", "compute_mode") == "cpu_parallel"
        assert svc2.get("basic", "num_workers") == 6

    def test_camel_to_snake_migration(self, tmp_path):
        """camelCase keys from old JSON are migrated to snake_case."""
        cfg = tmp_path / "settings.json"
        old_data = {
            "basic": {"plotNow": 2, "gridSkip": 3},
            "piv": {"intArea1": 32, "subpixMethod": 1},
            "postproc": {},
        }
        cfg.write_text(json.dumps(old_data))

        svc = SettingsService(config_path=str(cfg))
        assert svc.get("basic", "plot_now") == 2
        assert svc.get("basic", "grid_skip") == 3
        assert svc.get("piv", "int_area_1") == 32
        assert svc.get("piv", "sub_pix_method") == 1

    def test_update_and_get(self, tmp_path):
        cfg = str(tmp_path / "settings.json")
        svc = SettingsService(config_path=cfg)
        svc.update("basic", "vector_color", "red")
        assert svc.get("basic", "vector_color") == "red"

    def test_get_full_section(self, tmp_path):
        cfg = str(tmp_path / "settings.json")
        svc = SettingsService(config_path=cfg)
        section = svc.get("piv")
        assert isinstance(section, dict)
        assert "int_area_1" in section

    def test_model_round_trip_keeps_perf_fields_under_basic(self, tmp_path):
        settings = {
            "basic": BASIC_SETTINGS.copy(),
            "piv": PIV_SETTINGS.copy(),
            "postproc": POSTPROC_SETTINGS.copy(),
        }
        settings["basic"]["compute_mode"] = "cpu_parallel"
        settings["basic"]["num_workers"] = 4

        model = to_settings_model(settings)
        persisted = to_persisted_dict(model)

        assert persisted["basic"]["compute_mode"] == "cpu_parallel"
        assert persisted["basic"]["num_workers"] == 4
        assert "performance" not in persisted

    def test_get_returns_copy_not_reference(self, tmp_path):
        """Mutating the dict returned by get() must not affect internal state."""
        cfg = str(tmp_path / "settings.json")
        svc = SettingsService(config_path=cfg)
        original_value = svc.get("basic", "plot_now")

        section = svc.get("basic")
        section["plot_now"] = 999

        assert svc.get("basic", "plot_now") == original_value

    def test_merge_updates_internal_state(self, tmp_path):
        """merge() should update the internal settings dict."""
        cfg = str(tmp_path / "settings.json")
        svc = SettingsService(config_path=cfg)
        svc.merge("basic", {"plot_now": 42})
        assert svc.get("basic", "plot_now") == 42

    def test_merge_unknown_section_is_noop(self, tmp_path):
        """merge() on a non-existent section must not raise."""
        cfg = str(tmp_path / "settings.json")
        svc = SettingsService(config_path=cfg)
        svc.merge("nonexistent", {"key": "val"})  # must not raise
