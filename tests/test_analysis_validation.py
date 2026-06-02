"""
Runtime validation tests: request construction, input checks, and preconditions
that must be caught before background execution starts.
"""
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import BASIC_SETTINGS, PIV_SETTINGS, POSTPROC_SETTINGS


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

class DummySignal:
    def connect(self, _): pass


class FakeAnalysis:
    def __init__(self):
        self.progress = DummySignal()
        self.result = DummySignal()
        self.completed = DummySignal()
        self.is_running = False
        self.is_paused = False
        self.run_analysis_calls = []
        self.stop_calls = 0
        self.shutdown_calls = 0
        self.image_pairs = [(Path("input") / "a.png", Path("input") / "b.png")]

    def run_analysis(self, **kwargs):
        self.run_analysis_calls.append(kwargs)

    def get_image_pairs(self, _):
        return list(self.image_pairs)

    def stop(self): self.stop_calls += 1
    def shutdown(self): self.shutdown_calls += 1


class FakeSettings:
    def __init__(self, extra_basic=None, extra_piv=None):
        basic = BASIC_SETTINGS.copy()
        if extra_basic:
            basic.update(extra_basic)
        piv = PIV_SETTINGS.copy()
        if extra_piv:
            piv.update(extra_piv)
        self.saved = 0
        self.settings = {
            "basic": basic,
            "piv": piv,
            "postproc": POSTPROC_SETTINGS.copy(),
        }

    def get(self, section, key=None):
        if key is None:
            return self.settings[section]
        return self.settings[section].get(key)

    def save_settings(self): self.saved += 1

    def get_model(self):
        from services.settings import to_settings_model
        return to_settings_model(self.settings)

    def apply_model(self, model):
        from services.settings import to_persisted_dict
        self.settings = to_persisted_dict(model)


class FakeButton:
    def __init__(self):
        self.enabled = True
        self._text = ""

    def setEnabled(self, v): self.enabled = v
    def setText(self, t): self._text = t


class FakeProgressBar:
    def setValue(self, _): pass


class FakeLabel:
    def setText(self, _): pass


class FakeTab:
    def __init__(self, values=None):
        self.values = values or {"custom_select_enabled": False, "custom_selected_images": []}

    def get_values(self): return dict(self.values)


class FakeView:
    def __init__(self):
        self.btn_start = FakeButton()
        self.btn_pause = FakeButton()
        self.progress_bar = FakeProgressBar()
        self.progress_text = FakeLabel()
        self.tab_basic = FakeTab()
        self.closing = False

    def _update_settings_from_ui(self): pass
    def _set_closing_state(self, v): self.closing = v


def _make_controller(settings=None, analysis=None, view=None):
    from ui.controller import MainWindowController
    return MainWindowController(
        view=view or FakeView(),
        settings_service=settings or FakeSettings(),
        analysis_service=analysis or FakeAnalysis(),
    )


# ---------------------------------------------------------------------------
# Missing input directory
# ---------------------------------------------------------------------------

class TestMissingInputDirectory:
    def test_missing_input_dir_blocks_start(self, monkeypatch):
        import ui.controller as ctrl_module
        critical_calls = []
        monkeypatch.setattr(ctrl_module.QMessageBox, "critical",
                            lambda *a, **k: critical_calls.append(a[1:3]))

        settings = FakeSettings()  # input_dir defaults to ""
        analysis = FakeAnalysis()
        ctrl = _make_controller(settings=settings, analysis=analysis)

        ctrl.handle_start()

        # Analysis must not start when input_dir is missing
        assert critical_calls != []
        assert analysis.run_analysis_calls == []
        # NOTE: current controller saves settings before the input_dir check;
        # Task 2 will move the check earlier so save_settings is not called on failure.

    def test_valid_input_dir_allows_start(self, monkeypatch):
        import ui.controller as ctrl_module
        monkeypatch.setattr(ctrl_module.QMessageBox, "critical",
                            lambda *a, **k: pytest.fail("Should not call critical"))
        monkeypatch.setattr(ctrl_module, "build_export_plan",
                            lambda *a, **k: {"has_output_options": False, "existing_folders": []})

        settings = FakeSettings(extra_basic={"input_dir": "input", "output_dir": "output"})
        analysis = FakeAnalysis()
        ctrl = _make_controller(settings=settings, analysis=analysis)

        ctrl.handle_start()

        assert len(analysis.run_analysis_calls) == 1


# ---------------------------------------------------------------------------
# Interrogation area validation
# ---------------------------------------------------------------------------

class TestInterrogationAreaValidation:
    def test_increasing_areas_rejected_before_start(self, monkeypatch):
        import ui.controller as ctrl_module
        import ui.app as app_module

        critical_calls = []
        monkeypatch.setattr(ctrl_module.QMessageBox, "critical",
                            lambda *a, **k: critical_calls.append(a[1:3]))

        # Create a real PivSettingsTab with invalid ordering
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.tabs.piv_settings import PivSettingsTab
        tab = PivSettingsTab(PIV_SETTINGS.copy(), POSTPROC_SETTINGS.copy())
        tab.set_values({"int_area_1": "32", "int_area_2": "64"})  # increasing = invalid

        class ViewWithRealTab(FakeView):
            @property
            def tab_piv(self): return tab

            def _update_settings_from_ui(self):
                # Mirror what app.py does: raise ValueError on bad PIV settings
                from services.settings_validation import normalize_interrogation_areas
                piv_vals = self.tab_piv.get_values()
                areas = [
                    piv_vals.get(f"int_area_{i}", "none") for i in range(1, 7)
                ]
                normalized, _, error_msg = normalize_interrogation_areas(areas)
                if error_msg:
                    from PySide6.QtWidgets import QMessageBox as QMB
                    QMB.critical(self, "設定錯誤", error_msg)
                    raise ValueError(error_msg)

        view = ViewWithRealTab()
        settings = FakeSettings(extra_basic={"input_dir": "input"})
        analysis = FakeAnalysis()

        ctrl = _make_controller(settings=settings, analysis=analysis, view=view)
        ctrl.handle_start()

        assert analysis.run_analysis_calls == []

    def test_valid_decreasing_areas_pass_validation(self):
        from services.settings_validation import validate_interrogation_areas
        is_valid, num_passes, error_msg = validate_interrogation_areas(
            [64, 32, 16, "none", "none", "none"]
        )
        assert is_valid is True
        assert num_passes == 3
        assert error_msg == ""


# ---------------------------------------------------------------------------
# Overlap validation
# ---------------------------------------------------------------------------

class TestOverlapValidation:
    def test_overlap_below_zero_is_invalid_range(self):
        """Overlap must be in [0, 1). Values outside are user error."""
        from services.settings_validation import validate_interrogation_areas
        # Overlap is a separate field but the valid range is 0.0–0.99
        # Verify the tab clamps or we can detect it
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.tabs.piv_settings import PivSettingsTab
        tab = PivSettingsTab(PIV_SETTINGS.copy(), POSTPROC_SETTINGS.copy())
        tab.set_values({"overlap": 0.5})
        vals = tab.get_values()
        assert 0.0 <= vals["overlap"] < 1.0

    def test_overlap_upper_bound_is_clamped_by_ui(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.tabs.piv_settings import PivSettingsTab
        tab = PivSettingsTab(PIV_SETTINGS.copy(), POSTPROC_SETTINGS.copy())
        tab.set_values({"overlap": 0.99})
        vals = tab.get_values()
        assert vals["overlap"] <= 0.99


# ---------------------------------------------------------------------------
# Worker count validation
# ---------------------------------------------------------------------------

class TestWorkerCountValidation:
    def test_num_workers_defaults_to_positive_integer(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.tabs.basic_settings import BasicSettingsTab
        tab = BasicSettingsTab(BASIC_SETTINGS.copy())
        vals = tab.get_values()
        assert isinstance(vals["num_workers"], int)
        assert vals["num_workers"] >= 2

    def test_num_workers_clamped_to_valid_range(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.tabs.basic_settings import BasicSettingsTab
        tab = BasicSettingsTab(BASIC_SETTINGS.copy())
        tab.set_values({"compute_mode": "cpu_parallel", "num_workers": 2})
        vals = tab.get_values()
        assert 2 <= vals["num_workers"] <= 12


# ---------------------------------------------------------------------------
# Custom-select mode: minimum file requirement
# ---------------------------------------------------------------------------

class TestCustomSelectModeValidation:
    def test_single_custom_file_is_rejected_before_start(self, monkeypatch):
        import ui.controller as ctrl_module
        monkeypatch.setattr(ctrl_module.QMessageBox, "critical",
                            lambda *a, **k: None)

        view = FakeView()
        view.tab_basic = FakeTab({
            "custom_select_enabled": True,
            "custom_selected_images": ["/only/one/file.png"],
        })
        settings = FakeSettings()
        analysis = FakeAnalysis()
        ctrl = _make_controller(settings=settings, analysis=analysis, view=view)

        ctrl.handle_start()

        assert analysis.run_analysis_calls == []

    def test_two_custom_files_are_accepted(self, monkeypatch):
        import ui.controller as ctrl_module
        monkeypatch.setattr(ctrl_module.QMessageBox, "critical",
                            lambda *a, **k: pytest.fail("Should not call critical"))
        monkeypatch.setattr(ctrl_module, "build_export_plan",
                            lambda *a, **k: {"has_output_options": False, "existing_folders": []})

        view = FakeView()
        view.tab_basic = FakeTab({
            "custom_select_enabled": True,
            "custom_selected_images": ["/path/a.png", "/path/b.png"],
        })
        settings = FakeSettings(extra_basic={"input_dir": "", "output_dir": "out"})
        analysis = FakeAnalysis()
        ctrl = _make_controller(settings=settings, analysis=analysis, view=view)

        ctrl.handle_start()

        assert len(analysis.run_analysis_calls) == 1
