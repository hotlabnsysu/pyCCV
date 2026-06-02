"""Controller flow tests — verify handle_start/stop/pause/close logic."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ui.controller import MainWindowController


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _make_model():
    from config import BASIC_SETTINGS, PIV_SETTINGS, POSTPROC_SETTINGS, VIEWER_SETTINGS, CONVERT_SETTINGS
    from services.settings import to_settings_model
    data = {
        "basic": {**BASIC_SETTINGS, "input_dir": "/test/input", "output_dir": "/test/output"},
        "piv": dict(PIV_SETTINGS),
        "postproc": dict(POSTPROC_SETTINGS),
        "viewer": dict(VIEWER_SETTINGS),
        "convert": dict(CONVERT_SETTINGS),
    }
    return to_settings_model(data)


class FakeSettingsService:
    def __init__(self):
        self.saved = False
        self._data = {
            "basic": {"input_dir": "/test/input", "output_dir": "/test/output"},
            "piv": {},
            "postproc": {},
        }
        self._model = _make_model()

    def get(self, section, key=None):
        sec = self._data.get(section, {})
        if key is not None:
            return sec.get(key, "")
        return dict(sec)

    def merge(self, section, values):
        if section in self._data:
            self._data[section].update(values)

    def get_model(self):
        return self._model

    def apply_model(self, model):
        self._model = model

    def save_settings(self):
        self.saved = True


class FakeAnalysisService:
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.run_called = False
        self.stop_called = False
        self.pause_called = False
        self.resume_called = False
        self.shutdown_called = False
        self._pairs = []

    def get_image_pairs(self, input_dir, range_limit=0):
        return self._pairs

    def run_analysis(self, image_pairs, settings, output_dir, force_overwrite=False):
        self.run_called = True
        self.is_running = True

    def stop(self):
        self.stop_called = True
        self.is_running = False

    def pause(self):
        self.pause_called = True
        self.is_paused = True

    def resume(self):
        self.resume_called = True
        self.is_paused = False

    def shutdown(self):
        self.shutdown_called = True
        self.is_running = False


class FakeView:
    def __init__(self):
        self.update_called = False
        self.redraw_called = False
        self.close_called = False
        self._settings_error = None
        self.tab_basic = FakeBasicTab()
        self.btn_start = FakeButton()
        self.btn_pause = FakeButton()
        self.progress_bar = FakeProgressBar()
        self.progress_text = FakeLabel()

    def _update_settings_from_ui(self):
        self.update_called = True
        if self._settings_error:
            raise ValueError(self._settings_error)

    def _redraw_display(self):
        self.redraw_called = True

    def close(self):
        self.close_called = True


class FakeBasicTab:
    def get_values(self):
        return {
            "input_dir": "/test/input",
            "output_dir": "/test/output",
            "custom_select_enabled": False,
            "custom_selected_images": [],
        }


class FakeButton:
    def __init__(self):
        self._text = ""
        self._enabled = True

    def setText(self, t):
        self._text = t

    def text(self):
        return self._text

    def setEnabled(self, v):
        self._enabled = v


class FakeProgressBar:
    def setValue(self, v):
        pass


class FakeLabel:
    def setText(self, t):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHandleStart:
    @patch("ui.controller.build_export_plan", return_value={"has_output_options": False, "existing_folders": []})
    def test_collects_settings_before_running(self, mock_plan):
        svc = FakeSettingsService()
        analysis = FakeAnalysisService()
        analysis._pairs = [("a.png", "b.png")]
        view = FakeView()
        ctrl = MainWindowController(view, svc, analysis)

        ctrl.handle_start()

        assert view.update_called
        assert svc.saved

    def test_validation_failure_aborts(self):
        svc = FakeSettingsService()
        analysis = FakeAnalysisService()
        view = FakeView()
        view._settings_error = "bad settings"
        ctrl = MainWindowController(view, svc, analysis)

        ctrl.handle_start()

        assert not analysis.run_called

    @patch("ui.controller.build_export_plan", return_value={"has_output_options": False, "existing_folders": []})
    def test_no_pairs_does_not_run(self, mock_plan):
        svc = FakeSettingsService()
        analysis = FakeAnalysisService()
        analysis._pairs = []
        view = FakeView()
        ctrl = MainWindowController(view, svc, analysis)

        ctrl.handle_start()

        assert not analysis.run_called


class TestHandleStop:
    @patch("ui.controller.QMessageBox")
    def test_stops_running_analysis(self, mock_msgbox):
        from PySide6.QtWidgets import QMessageBox
        mock_msgbox.question.return_value = QMessageBox.StandardButton.Yes
        mock_msgbox.StandardButton = QMessageBox.StandardButton
        svc = FakeSettingsService()
        analysis = FakeAnalysisService()
        analysis.is_running = True
        view = FakeView()
        ctrl = MainWindowController(view, svc, analysis)

        ctrl.handle_stop()

        assert analysis.stop_called

    def test_noop_when_not_running(self):
        svc = FakeSettingsService()
        analysis = FakeAnalysisService()
        analysis.is_running = False
        view = FakeView()
        ctrl = MainWindowController(view, svc, analysis)

        ctrl.handle_stop()

        assert not analysis.stop_called


class TestHandlePause:
    def test_pauses_when_running(self):
        svc = FakeSettingsService()
        analysis = FakeAnalysisService()
        analysis.is_running = True
        analysis.is_paused = False
        view = FakeView()
        ctrl = MainWindowController(view, svc, analysis)

        ctrl.handle_pause()

        assert analysis.pause_called

    def test_resumes_when_paused(self):
        svc = FakeSettingsService()
        analysis = FakeAnalysisService()
        analysis.is_running = True
        analysis.is_paused = True
        view = FakeView()
        ctrl = MainWindowController(view, svc, analysis)

        ctrl.handle_pause()

        assert analysis.resume_called


class TestHandleCloseRequest:
    def test_shuts_down_service(self):
        svc = FakeSettingsService()
        analysis = FakeAnalysisService()
        view = FakeView()
        ctrl = MainWindowController(view, svc, analysis)

        ctrl.handle_close_request()

        assert analysis.shutdown_called
