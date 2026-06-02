"""State management tests for ui/tabs/viewer.py."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def viewer_tab(qt_app):
    from config import VIEWER_SETTINGS
    from ui.tabs.viewer import ViewerTab
    tab = ViewerTab(dict(VIEWER_SETTINGS))
    yield tab


class TestGetSetRoundTrip:
    def test_get_values_returns_dict(self, viewer_tab):
        vals = viewer_tab.get_values()
        assert isinstance(vals, dict)
        assert "display_mode" in vals
        assert "grid_skip" in vals
        assert "quiver_factor" in vals

    def test_set_values_does_not_crash(self, viewer_tab):
        vals = viewer_tab.get_values()
        viewer_tab.set_values(vals)

    def test_round_trip_preserves_display_mode(self, viewer_tab):
        vals = viewer_tab.get_values()
        original_mode = vals["display_mode"]
        viewer_tab.set_values(vals)
        assert viewer_tab.get_values()["display_mode"] == original_mode

    def test_partial_set_values_does_not_crash(self, viewer_tab):
        viewer_tab.set_values({"display_mode": "渦度"})
        viewer_tab.set_values({})


class TestDisplayModeSwitch:
    def test_vector_mode_enables_streamline(self, viewer_tab):
        viewer_tab._set_display_mode("向量")
        assert viewer_tab._btn_streamline.isEnabled()

    def test_vorticity_mode_enables_streamline(self, viewer_tab):
        viewer_tab._set_display_mode("渦度")
        assert viewer_tab._btn_streamline.isEnabled()

    def test_image_mode_enables_streamline(self, viewer_tab):
        viewer_tab._set_display_mode("影像")
        assert viewer_tab._btn_streamline.isEnabled()

    def test_mode_switches_stack_widget(self, viewer_tab):
        viewer_tab._set_display_mode("影像")
        assert viewer_tab._mode_stack.currentIndex() == 0
        viewer_tab._set_display_mode("向量")
        assert viewer_tab._mode_stack.currentIndex() == 1
        viewer_tab._set_display_mode("渦度")
        assert viewer_tab._mode_stack.currentIndex() == 2


class TestSignals:
    def test_streamline_toggled_emits(self, viewer_tab, qtbot=None):
        received = []
        viewer_tab.streamline_toggled.connect(lambda v: received.append(v))
        viewer_tab._on_streamline_toggled(True)
        assert received == [True]

    def test_streamline_clear_emits(self, viewer_tab):
        received = []
        viewer_tab.streamline_clear.connect(lambda: received.append(True))
        viewer_tab.streamline_clear.emit()
        assert len(received) == 1


class TestPairNavigation:
    def test_update_pair_count(self, viewer_tab):
        viewer_tab.update_pair_count(10)
        assert viewer_tab._total_pairs == 10

    def test_get_set_current_pair(self, viewer_tab):
        viewer_tab.update_pair_count(5)
        viewer_tab.set_current_pair(3)
        assert viewer_tab.get_current_pair() == 3

    def test_pair_beyond_total(self, viewer_tab):
        viewer_tab.update_pair_count(5)
        viewer_tab.set_current_pair(10)
        val = viewer_tab.get_current_pair()
        assert val >= 1
