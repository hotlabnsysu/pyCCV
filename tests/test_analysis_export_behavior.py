"""
Export planning seam tests for analysis output skip behavior.
"""
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import analysis
from services.analysis import AnalysisService, build_export_plan, should_skip_existing_outputs


class TestAnalysisExportSkipBehavior:
    def test_returns_false_when_no_exports_are_requested(self, tmp_path):
        should_skip = should_skip_existing_outputs([], "pair_001", ".flo")

        assert should_skip is False


class TestExportPlan:
    def test_build_export_plan_returns_existing_folders_for_enabled_exports(self, tmp_path):
        input_dir = tmp_path / "input" / "sample"
        input_dir.mkdir(parents=True)
        image_pairs = [(input_dir / "pair_001_a.png", input_dir / "pair_001_b.png")]
        output_dir = tmp_path / "out"
        existing = output_dir / "sample_Raw"
        existing.mkdir(parents=True)

        plan = build_export_plan(
            image_pairs,
            {"export_raw": True, "export_filt": False, "export_interp": False, "export_smooth": False},
            str(output_dir),
        )

        assert plan["has_output_options"] is True
        assert plan["suffixes"] == ["_Raw"]
        assert plan["existing_folders"] == [existing]

    def test_build_export_plan_returns_empty_when_no_exports_enabled(self, tmp_path):
        input_dir = tmp_path / "input" / "sample"
        input_dir.mkdir(parents=True)
        image_pairs = [(input_dir / "pair_001_a.png", input_dir / "pair_001_b.png")]

        plan = build_export_plan(
            image_pairs,
            {"export_raw": False, "export_filt": False, "export_interp": False, "export_smooth": False},
            str(tmp_path / "out"),
        )

        assert plan["has_output_options"] is False
        assert plan["export_folders"] == []
        assert plan["existing_folders"] == []

    def test_returns_true_only_when_all_requested_outputs_exist(self, tmp_path):
        raw_dir = tmp_path / "sample_Raw"
        filt_dir = tmp_path / "sample_Filt"
        raw_dir.mkdir()
        filt_dir.mkdir()
        (raw_dir / "pair_001.flo").write_text("raw", encoding="utf-8")
        (filt_dir / "pair_001.flo").write_text("filt", encoding="utf-8")

        should_skip = should_skip_existing_outputs(
            [(raw_dir, "raw"), (filt_dir, "filt")],
            "pair_001",
            ".flo",
        )

        assert should_skip is True

    def test_returns_false_when_any_requested_output_is_missing(self, tmp_path):
        raw_dir = tmp_path / "sample_Raw"
        filt_dir = tmp_path / "sample_Filt"
        raw_dir.mkdir()
        filt_dir.mkdir()
        (raw_dir / "pair_001.flo").write_text("raw", encoding="utf-8")

        should_skip = should_skip_existing_outputs(
            [(raw_dir, "raw"), (filt_dir, "filt")],
            "pair_001",
            ".flo",
        )

        assert should_skip is False


class TestAnalysisLoopUsesExportSkipSeam:
    def test_serial_path_routes_skip_decision_through_helper(self, monkeypatch, tmp_path):
        pair_dir = tmp_path / "input" / "sample"
        pair_dir.mkdir(parents=True)
        p1 = pair_dir / "pair_001_a.png"
        p2 = pair_dir / "pair_001_b.png"
        output_dir = tmp_path / "out"
        raw_dir = output_dir / "sample_Raw"
        filt_dir = output_dir / "sample_Filt"
        raw_dir.mkdir(parents=True)
        filt_dir.mkdir(parents=True)
        (raw_dir / "pair_001_a.flo").write_text("raw", encoding="utf-8")
        (filt_dir / "pair_001_a.flo").write_text("filt", encoding="utf-8")

        calls = []
        original_helper = analysis.should_skip_existing_outputs

        def spy_helper(current_exports, stem, output_ext):
            calls.append((list(current_exports), stem, output_ext))
            return original_helper(current_exports, stem, output_ext)

        monkeypatch.setattr(analysis, "should_skip_existing_outputs", spy_helper)

        svc = AnalysisService()
        svc._image_pairs = [(p1, p2)]
        svc._settings = {
            "basic": {
                "compute_mode": "cpu",
                "export_raw": True,
                "export_filt": True,
                "output_format": "flo",
            },
            "piv": {},
            "postproc": {},
        }
        svc._output_dir = str(output_dir)
        svc._force_overwrite = False
        svc._sliding_image_pairs = lambda pairs: iter([(((p1, p2)), (np.zeros((1, 1)), np.zeros((1, 1))))])
        svc._emit_result = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("skip path must not emit results"))

        svc._analysis_loop()

        assert calls == [([(raw_dir, "raw"), (filt_dir, "filt")], "pair_001_a", ".flo")]

    def test_pair_parallel_path_routes_skip_decision_through_helper(self, monkeypatch, tmp_path):
        pair_dir = tmp_path / "input" / "sample"
        pair_dir.mkdir(parents=True)
        image_pairs = [
            (pair_dir / "pair_001_a.png", pair_dir / "pair_001_b.png"),
            (pair_dir / "pair_002_a.png", pair_dir / "pair_002_b.png"),
        ]
        output_dir = tmp_path / "out"
        raw_dir = output_dir / "sample_Raw"
        filt_dir = output_dir / "sample_Filt"
        raw_dir.mkdir(parents=True)
        filt_dir.mkdir(parents=True)
        for stem in ("pair_001_a", "pair_002_a"):
            (raw_dir / f"{stem}.flo").write_text("raw", encoding="utf-8")
            (filt_dir / f"{stem}.flo").write_text("filt", encoding="utf-8")

        results_emitted = []

        svc = AnalysisService()
        svc._image_pairs = image_pairs
        svc._settings = {
            "basic": {
                "compute_mode": "cpu_parallel",
                "num_workers": 2,
                "export_raw": True,
                "export_filt": True,
                "output_format": "flo",
            },
            "piv": {},
            "postproc": {},
        }
        svc._output_dir = str(output_dir)
        svc._force_overwrite = False
        svc._emit_result = lambda *args, **kwargs: results_emitted.append(True)

        svc._analysis_loop()

        assert len(results_emitted) == 0, "Skip path must not emit results when outputs exist"
