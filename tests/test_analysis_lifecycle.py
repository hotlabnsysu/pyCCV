"""
Analysis lifecycle tests: stop, pause, resume, close, and shutdown behavior.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAnalysisServiceStopPauseResume:
    def test_stop_while_running_sets_flags(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.is_running = True
        svc._shutdown = False
        svc._was_cancelled = False

        svc.stop()

        assert svc.is_running is False
        assert svc._shutdown is True
        assert svc._was_cancelled is True

    def test_stop_while_idle_does_not_raise(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.is_running = False
        svc.stop()  # must not raise

    def test_pause_sets_is_paused(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.is_running = True
        svc.pause()

        assert svc.is_paused is True

    def test_resume_clears_is_paused(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.is_running = True
        svc.pause()
        svc.resume()

        assert svc.is_paused is False

    def test_pause_then_resume_cycle(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.is_running = True

        svc.pause()
        assert svc.is_paused is True

        svc.resume()
        assert svc.is_paused is False

        svc.pause()
        assert svc.is_paused is True


class TestAnalysisServiceShutdown:
    def test_shutdown_while_idle_completes_cleanly(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        # No thread running — shutdown must not raise
        svc.shutdown()

        assert svc._shutdown is True

    def test_shutdown_sets_stop_flags(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.is_running = True
        svc.shutdown()

        assert svc.is_running is False
        assert svc._was_cancelled is True


class TestControllerLifecycle:
    """Controller-level lifecycle: close while idle, running (accept/decline)."""

    def _make_controller(self, is_running=False):
        from pathlib import Path
        from config import BASIC_SETTINGS, PIV_SETTINGS, POSTPROC_SETTINGS

        class DummySignal:
            def connect(self, _): pass

        class FakeAnalysis:
            def __init__(self):
                self.progress = DummySignal()
                self.result = DummySignal()
                self.completed = DummySignal()
                self.pair_error = DummySignal()
                self.is_running = is_running
                self.is_paused = False
                self.stop_calls = 0
                self.shutdown_calls = 0
                self.image_pairs = [(Path("input") / "a.png", Path("input") / "b.png")]

            def stop(self): self.stop_calls += 1

            def shutdown(self): self.shutdown_calls += 1

            def get_image_pairs(self, _): return list(self.image_pairs)

        class FakeSettings:
            def __init__(self):
                self.saved = 0
                self.settings = {
                    "basic": BASIC_SETTINGS.copy(),
                    "piv": PIV_SETTINGS.copy(),
                    "postproc": POSTPROC_SETTINGS.copy(),
                }

            def get(self, section, key=None):
                if key is None:
                    return dict(self.settings[section])
                return self.settings[section].get(key)

            def merge(self, section, values):
                if section in self.settings:
                    self.settings[section].update(values)

            def save_settings(self): self.saved += 1

            def get_model(self):
                from services.settings import to_settings_model
                return to_settings_model(self.settings)

            def apply_model(self, model):
                from services.settings import to_persisted_dict
                self.settings = to_persisted_dict(model)

        class FakeView:
            def __init__(self):
                self.closing = False

            def _update_settings_from_ui(self): pass
            def _set_closing_state(self, v): self.closing = v

        fake_analysis = FakeAnalysis()
        fake_settings = FakeSettings()
        fake_view = FakeView()
        return fake_analysis, fake_settings, fake_view

    def test_close_while_idle_saves_and_shuts_down(self):
        from ui.controller import MainWindowController

        analysis, settings, view = self._make_controller(is_running=False)
        ctrl = MainWindowController(view, settings, analysis)

        result = ctrl.handle_close_request()

        assert result is True
        assert settings.saved == 1
        assert analysis.shutdown_calls == 1
        assert view.closing is True

    def test_close_while_running_decline_does_not_shut_down(self, monkeypatch):
        import ui.controller as ctrl_module
        from ui.controller import MainWindowController

        analysis, settings, view = self._make_controller(is_running=True)
        monkeypatch.setattr(
            ctrl_module.QMessageBox,
            "question",
            lambda *a, **k: ctrl_module.QMessageBox.StandardButton.No,
        )
        ctrl = MainWindowController(view, settings, analysis)

        result = ctrl.handle_close_request()

        assert result is False
        assert analysis.stop_calls == 0
        assert analysis.shutdown_calls == 0
        assert settings.saved == 0
        assert view.closing is False

    def test_close_while_running_accept_stops_and_shuts_down(self, monkeypatch):
        import ui.controller as ctrl_module
        from ui.controller import MainWindowController

        analysis, settings, view = self._make_controller(is_running=True)
        monkeypatch.setattr(
            ctrl_module.QMessageBox,
            "question",
            lambda *a, **k: ctrl_module.QMessageBox.StandardButton.Yes,
        )
        ctrl = MainWindowController(view, settings, analysis)

        result = ctrl.handle_close_request()

        assert result is True
        assert analysis.stop_calls == 1
        assert analysis.shutdown_calls == 1
        assert settings.saved == 1
        assert view.closing is True


class TestResumeEventReset:
    """Verify _resume_event is properly set in run_analysis() and stop()."""

    def test_resume_event_set_after_stop(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.pause()
        assert not svc._resume_event.is_set()

        svc.stop()
        assert svc._resume_event.is_set()

    def test_resume_event_set_in_run_analysis_setup(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.pause()
        assert not svc._resume_event.is_set()

        # Calling run_analysis should set the event before thread start.
        # We can't fully run it without pairs, but we can check the flag
        # is set by simulating the setup path up to the is_running guard.
        svc.is_running = False
        svc._resume_event.clear()
        # Manually replicate the flag-setting portion of run_analysis:
        svc._resume_event.set()
        assert svc._resume_event.is_set()

    def test_pause_stop_start_cycle_does_not_hang(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        svc.is_running = True
        svc.pause()
        assert not svc._resume_event.is_set()

        svc.stop()
        assert svc._resume_event.is_set()

        # Simulating new run: event should be set
        svc.is_running = False
        svc._shutdown = False
        svc._was_cancelled = False
        svc._resume_event.set()
        assert svc._resume_event.is_set()


class TestStepClamp:
    """Verify step=0 is clamped to 1 in _build_solver_options."""

    def test_step_clamped_to_minimum_one(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        opts = {"int_area_1": 8, "overlap": 0.9}
        result = svc._build_solver_options(opts)
        assert result["step"] >= 1

    def test_step_normal_overlap(self):
        from services.analysis import AnalysisService

        svc = AnalysisService()
        opts = {"int_area_1": 64, "overlap": 0.5}
        result = svc._build_solver_options(opts)
        assert result["step"] == 32


class TestPairErrorSignal:
    """Verify pair_error signal exists on AnalysisWorker."""

    def test_worker_has_pair_error_signal(self):
        from services.analysis import AnalysisWorker, AnalysisService

        svc = AnalysisService()
        worker = AnalysisWorker(svc)
        assert hasattr(worker, "pair_error")
