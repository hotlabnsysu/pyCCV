"""
UI smoke tests — verify instantiation, tab pages, and get/set round-trip.
Requires a QApplication instance (uses pytest-qt or creates one manually).
"""
import os
import sys
import pytest
from PySide6.QtGui import QCloseEvent

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def qt_app():
    """Create a QApplication for the test session."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class TestMainWindowSmoke:
    def test_instantiates(self, qt_app):
        from ui.app import PyCCVMainWindow
        win = PyCCVMainWindow()
        assert win is not None
        win.close()

    def test_four_tab_pages(self, qt_app):
        from ui.app import PyCCVMainWindow
        win = PyCCVMainWindow()
        assert win._tab_stack.count() == 4
        win.close()

    def test_tab_switch(self, qt_app):
        from ui.app import PyCCVMainWindow
        win = PyCCVMainWindow()
        for i in range(4):
            win._switch_tab(i)
            assert win._tab_stack.currentIndex() == i
        win.close()

    def test_main_window_uses_expected_chinese_labels(self, qt_app):
        from ui.app import PyCCVMainWindow
        from PySide6.QtWidgets import QLabel

        win = PyCCVMainWindow()

        assert win.progress_text.text() == "準備就緒"
        assert win.time_info_label.text() == "剩餘時間: --:--:--"
        assert win.btn_stop.text() == "停止"
        assert win.btn_pause.text() == "暫停"
        assert win.btn_start.text() == "開始分析"
        assert [btn.text() for btn in win._tab_buttons] == ["基本設定", "PIV 設定", "VIEW", "SERVICE"]

        win.close()

    def test_close_while_idle_saves_settings_and_shuts_down(self, qt_app, monkeypatch):
        from config import BASIC_SETTINGS, PIV_SETTINGS, POSTPROC_SETTINGS, VIEWER_SETTINGS, CONVERT_SETTINGS
        import ui.app as app_module

        class DummySignal:
            def connect(self, _callback):
                return None

        class FakeSettingsService:
            def __init__(self):
                self.saved = 0
                self.settings = {
                    "basic": BASIC_SETTINGS.copy(),
                    "piv": PIV_SETTINGS.copy(),
                    "postproc": POSTPROC_SETTINGS.copy(),
                    "viewer": VIEWER_SETTINGS.copy(),
                    "convert": CONVERT_SETTINGS.copy(),
                }

            def get(self, section, key=None):
                if key is None:
                    return dict(self.settings[section])
                return self.settings[section].get(key)

            def merge(self, section, values):
                if section in self.settings:
                    self.settings[section].update(values)

            def save_settings(self):
                self.saved += 1

        class FakeAnalysisService:
            def __init__(self):
                self.progress = DummySignal()
                self.result = DummySignal()
                self.completed = DummySignal()
                self.pair_error = DummySignal()
                self.is_running = False
                self.is_paused = False
                self.shutdown_called = False

            def shutdown(self):
                self.shutdown_called = True

        fake_settings = FakeSettingsService()
        fake_analysis = FakeAnalysisService()

        monkeypatch.setattr(app_module, "SettingsService", lambda: fake_settings)
        monkeypatch.setattr(app_module, "AnalysisService", lambda: fake_analysis)
        monkeypatch.setattr(
            app_module.QMessageBox,
            "question",
            lambda *args, **kwargs: pytest.fail("Idle close should not prompt for confirmation"),
        )

        win = app_module.PyCCVMainWindow()
        win.tab_basic.set_values({"input_dir": "/tmp/input", "plot_now": 1, "compute_mode": "cpu_parallel", "num_workers": 4})

        event = QCloseEvent()
        win.closeEvent(event)

        assert event.isAccepted()
        assert fake_settings.saved == 1
        assert fake_analysis.shutdown_called is True
        assert fake_settings.settings["basic"]["input_dir"] == "/tmp/input"
        assert fake_settings.settings["basic"]["plot_now"] == 1
        assert fake_settings.settings["basic"]["compute_mode"] == "cpu_parallel"
        assert fake_settings.settings["basic"]["num_workers"] == 4

    def test_start_with_invalid_interrogation_areas_shows_error_and_does_not_start(
        self, qt_app, monkeypatch
    ):
        from config import BASIC_SETTINGS, PIV_SETTINGS, POSTPROC_SETTINGS, VIEWER_SETTINGS, CONVERT_SETTINGS
        import ui.app as app_module

        class DummySignal:
            def connect(self, _callback):
                return None

        class FakeSettingsService:
            def __init__(self):
                self.saved = 0
                self.settings = {
                    "basic": BASIC_SETTINGS.copy(),
                    "piv": PIV_SETTINGS.copy(),
                    "postproc": POSTPROC_SETTINGS.copy(),
                    "viewer": VIEWER_SETTINGS.copy(),
                    "convert": CONVERT_SETTINGS.copy(),
                }

            def get(self, section, key=None):
                if key is None:
                    return dict(self.settings[section])
                return self.settings[section].get(key)

            def merge(self, section, values):
                if section in self.settings:
                    self.settings[section].update(values)

            def save_settings(self):
                self.saved += 1

        class FakeAnalysisService:
            def __init__(self):
                self.progress = DummySignal()
                self.result = DummySignal()
                self.completed = DummySignal()
                self.pair_error = DummySignal()
                self.is_running = False
                self.is_paused = False
                self.run_analysis_calls = 0

            def run_analysis(self, **kwargs):
                self.run_analysis_calls += 1

        fake_settings = FakeSettingsService()
        fake_analysis = FakeAnalysisService()
        critical_calls = []

        monkeypatch.setattr(app_module, "SettingsService", lambda: fake_settings)
        monkeypatch.setattr(app_module, "AnalysisService", lambda: fake_analysis)
        monkeypatch.setattr(
            app_module.QMessageBox,
            "critical",
            lambda *args: critical_calls.append(args[1:3]),
        )

        win = app_module.PyCCVMainWindow()
        win.tab_basic.set_values({"input_dir": "/tmp/input"})
        win.tab_piv.set_values({"int_area_1": "32", "int_area_2": "64"})

        win._on_start()

        assert critical_calls == [("設定錯誤", "設定錯誤: Int Area 1 至 Int Area 6 應依序變小")]
        assert fake_settings.saved == 0
        assert fake_analysis.run_analysis_calls == 0
        assert fake_settings.settings["piv"]["int_area_1"] == 64
        assert fake_settings.settings["piv"]["int_area_2"] == 32

    def test_completion_signal_is_ignored_after_close_starts(self, qt_app, monkeypatch):
        import ui.app as app_module

        info_calls = []
        monkeypatch.setattr(
            app_module.QMessageBox,
            "information",
            lambda *args, **kwargs: info_calls.append(args[1:3]),
        )

        win = app_module.PyCCVMainWindow()
        win._set_closing_state(True)
        original_start_enabled = win.btn_start.isEnabled()
        original_pause_text = win.btn_pause.text()

        win._on_complete("0:00:01", False)

        assert info_calls == []
        assert win.btn_start.isEnabled() == original_start_enabled
        assert win.btn_pause.text() == original_pause_text
        win.close()


class TestBasicSettingsTab:
    def test_get_values_keys(self, qt_app):
        from ui.tabs.basic_settings import BasicSettingsTab
        from config import BASIC_SETTINGS
        tab = BasicSettingsTab(BASIC_SETTINGS.copy())
        vals = tab.get_values()
        expected_keys = [
            "input_dir", "output_dir", "custom_select_enabled", "custom_selected_images",
            "export_smooth", "export_interp", "export_filt", "export_raw",
            "output_format", "plot_now", "vector_color", "grid_skip", "quiver_factor",
            "compute_mode", "num_workers",
        ]
        for key in expected_keys:
            assert key in vals, f"Missing key: {key}"

    def test_set_get_round_trip(self, qt_app):
        from ui.tabs.basic_settings import BasicSettingsTab
        from config import BASIC_SETTINGS
        tab = BasicSettingsTab(BASIC_SETTINGS.copy())
        test_vals = {
            "input_dir": "/test/input",
            "output_dir": "/test/output",
            "plot_now": 1,
            "vector_color": "red",
            "grid_skip": 3,
            "quiver_factor": 7.5,
        }
        tab.set_values(test_vals)
        result = tab.get_values()
        assert result["input_dir"] == "/test/input"
        assert result["plot_now"] == 1
        assert result["vector_color"] == "red"
        assert result["grid_skip"] == 3
        assert abs(result["quiver_factor"] - 7.5) < 0.01


class TestPivSettingsTab:
    def test_get_values_keys(self, qt_app):
        from ui.tabs.piv_settings import PivSettingsTab
        from config import PIV_SETTINGS, POSTPROC_SETTINGS
        tab = PivSettingsTab(PIV_SETTINGS.copy(), POSTPROC_SETTINGS.copy())
        vals = tab.get_values()
        for key in ["int_area_1", "int_area_2", "overlap", "sub_pix_method",
                    "window_deform", "repeat_corr", "disable_autocorr"]:
            assert key in vals

    def test_round_trip(self, qt_app):
        from ui.tabs.piv_settings import PivSettingsTab
        from config import PIV_SETTINGS, POSTPROC_SETTINGS
        tab = PivSettingsTab(PIV_SETTINGS.copy(), POSTPROC_SETTINGS.copy())
        tab.set_values({"int_area_1": "32", "overlap": 0.75, "repeat_corr": True})
        vals = tab.get_values()
        assert vals["int_area_1"] == "32"
        assert abs(vals["overlap"] - 0.75) < 0.01
        assert vals["repeat_corr"] is True


class TestPivPostprocSection:
    def test_postproc_values_keys(self, qt_app):
        from ui.tabs.piv_settings import PivSettingsTab
        from config import PIV_SETTINGS, POSTPROC_SETTINGS
        tab = PivSettingsTab(PIV_SETTINGS.copy(), POSTPROC_SETTINGS.copy())
        vals = tab.get_postproc_values()
        for key in ["thres_std", "thres_median", "thres_global",
                    "interp_method", "smooth_data"]:
            assert key in vals

    def test_filter_spin_disabled_when_unchecked(self, qt_app):
        from ui.tabs.piv_settings import PivSettingsTab
        from config import PIV_SETTINGS, POSTPROC_SETTINGS
        tab = PivSettingsTab(PIV_SETTINGS.copy(), POSTPROC_SETTINGS.copy())
        for key, (chk, spin) in tab._thres_spins.items():
            chk.setChecked(False)
            assert not spin.isEnabled()


class TestPerfSettingsInBasicTab:
    """PerfSettingsTab was removed (dead code); perf controls live in BasicSettingsTab."""

    def test_basic_tab_has_compute_mode(self, qt_app):
        from ui.tabs.basic_settings import BasicSettingsTab
        from config import BASIC_SETTINGS
        tab = BasicSettingsTab(BASIC_SETTINGS.copy())
        vals = tab.get_values()
        assert "compute_mode" in vals
        assert "num_workers" in vals
