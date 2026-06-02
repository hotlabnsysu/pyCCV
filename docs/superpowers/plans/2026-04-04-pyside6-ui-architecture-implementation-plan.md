# PySide6 UI Architecture Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incrementally refactor the PySide6 UI and related services to improve performance, extensibility, and robustness without changing the current visible workflow or persisted settings schema.

**Architecture:** Keep the existing window and tab layout intact while introducing a controller layer, explicit state/model boundaries, centralized validation, isolated plotting logic, and smaller analysis-service responsibilities. Preserve the current Qt signal contract and persisted `basic`/`piv`/`postproc` schema during the early phases to minimize regression risk.

**Tech Stack:** Python 3.10, PySide6, Matplotlib, NumPy, Pillow, pytest

---

## Planned File Structure

### Existing files to modify
- `ui/app.py`
  Purpose: slim down the main window into a view shell and delegate workflow logic.
- `services/analysis.py`
  Purpose: preserve public Qt behavior while extracting internal helper responsibilities.
- `services/settings.py`
  Purpose: keep persisted schema stable while supporting model conversion and compatibility tests.
- `ui/tabs/basic_settings.py`
  Purpose: preserve the current plot-related signal seam and expose only the minimal APIs needed by the controller.
- `tests/test_ui_smoke.py`
  Purpose: keep smoke coverage aligned with the refactored view wiring.
- `tests/test_settings.py`
  Purpose: add persisted-schema and migration compatibility assertions.

### New files to create
- `ui/controller.py`
  Purpose: coordinate settings collection, validation, analysis lifecycle, dialogs, and close handling.
- `ui/plot_presenter.py`
  Purpose: isolate display-state interpretation and Matplotlib redraw logic.
- `services/settings_validation.py`
  Purpose: centralize validation and normalization rules that are currently embedded in the main window.
- `tests/test_settings_validation.py`
  Purpose: validate interrogation-area rules and other pre-run checks independently of the UI.
- `tests/test_controller_flow.py`
  Purpose: verify start/pause/stop/close flow with fakes or lightweight test doubles.
- `tests/test_plot_presenter.py`
  Purpose: verify plot-mode and vector-selection behavior without needing the full application workflow.
- `tests/test_analysis_export_behavior.py`
  Purpose: lock down overwrite/skip/output compatibility behavior before internal analysis cleanup.

## Task 1: Expand the Safety Net for Current Behavior

**Files:**
- Modify: `tests/test_settings.py`
- Create: `tests/test_settings_validation.py`
- Create: `tests/test_analysis_export_behavior.py`
- Test: `tests/test_settings.py`
- Test: `tests/test_settings_validation.py`
- Test: `tests/test_analysis_export_behavior.py`

- [ ] **Step 1: Add failing persisted-schema compatibility tests**
- [ ] **Step 1: Add persisted-schema compatibility tests that lock existing behavior before refactor**

```python
def test_perf_fields_remain_under_basic_after_save(tmp_path):
    cfg = tmp_path / "settings.json"
    svc = SettingsService(config_path=str(cfg))
    svc.settings["basic"]["compute_mode"] = "cpu_parallel"
    svc.settings["basic"]["num_workers"] = 4
    svc.save_settings()

    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert "basic" in data
    assert "compute_mode" in data["basic"]
    assert "num_workers" in data["basic"]
    assert "performance" not in data
```

- [ ] **Step 2: Run settings tests to establish the baseline and confirm the compatibility rule is already true**

Run: `python -m pytest tests/test_settings.py -v`
Expected: PASS with newly added compatibility coverage

- [ ] **Step 3: Add failing validation tests for interrogation-area rules**

```python
def test_validate_int_areas_requires_first_pass():
    is_valid, num_passes, message = validate_interrogation_areas(
        ["none", "32", "none", "none", "none", "none"]
    )
    assert is_valid is False
    assert num_passes == 0
    assert message
```

- [ ] **Step 4: Run validation tests to verify they fail before the validator exists**

Run: `python -m pytest tests/test_settings_validation.py -v`
Expected: FAIL with import error or missing function

- [ ] **Step 5: Add regression characterization tests around current close/save behavior**

```python
def test_close_while_idle_still_saves_settings_and_shuts_down():
    window = PyCCVMainWindow()
    # Patch services and close path collaborators
    window.close()
    assert save_called is True
    assert shutdown_called is True
```

- [ ] **Step 6: Run UI and settings baseline tests**

Run: `python -m pytest tests/test_settings.py tests/test_ui_smoke.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tests/test_settings.py tests/test_settings_validation.py tests/test_ui_smoke.py
git commit -m "test: lock down settings and close-path compatibility"
```

## Task 2: Extract Centralized Settings Validation

**Files:**
- Create: `services/settings_validation.py`
- Modify: `ui/app.py`
- Test: `tests/test_settings_validation.py`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the minimal validator API to satisfy the failing tests**

```python
def validate_interrogation_areas(values: list[str]) -> tuple[bool, int, str]:
    ...

def validate_run_preconditions(settings: dict) -> tuple[bool, str]:
    ...
```

- [ ] **Step 2: Run validator tests and verify remaining failures are implementation-related**

Run: `python -m pytest tests/test_settings_validation.py -v`
Expected: FAIL on rule details, not import errors

- [ ] **Step 3: Implement interrogation-area normalization and rule checks**

```python
for value in values:
    if value == "none":
        normalized.append(None)
    else:
        normalized.append(int(value))
```

- [ ] **Step 4: Update `ui/app.py` to call the validator instead of its private `_validate_int_areas()` logic**

```python
is_valid, num_passes, error_msg = validate_interrogation_areas(int_areas_raw)
if not is_valid:
    QMessageBox.critical(self, "Settings Error", error_msg)
    raise ValueError(error_msg)
```

- [ ] **Step 5: Remove or inline-deprecate the old duplicated validation code from `ui/app.py`**

Run: `python -m pytest tests/test_settings_validation.py tests/test_ui_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/settings_validation.py ui/app.py tests/test_settings_validation.py tests/test_ui_smoke.py
git commit -m "refactor: centralize settings validation"
```

## Task 3: Introduce an Export Planning Seam Before Refactoring Analysis Internals

**Files:**
- Modify: `services/analysis.py`
- Create: `tests/test_analysis_export_behavior.py`
- Test: `tests/test_analysis_export_behavior.py`

- [ ] **Step 1: Add a small importable helper seam for export planning and skip decisions without changing behavior**

```python
def should_skip_existing_outputs(current_exports, stem, output_ext) -> bool:
    return all((folder_path / f"{stem}{output_ext}").exists() for folder_path, _ in current_exports)
```

- [ ] **Step 2: Add failing export-behavior tests against the new helper seam**

```python
def test_non_overwrite_skips_only_when_all_requested_outputs_exist(tmp_path):
    # Arrange export folders/files so one stage is missing
    # Assert the planner decides not to skip the pair
    assert should_skip is False
```

- [ ] **Step 3: Run export-behavior tests to verify they fail before helper extraction is complete**

Run: `python -m pytest tests/test_analysis_export_behavior.py -v`
Expected: FAIL with import error or missing helper

- [ ] **Step 4: Implement the helper using the current `_analysis_loop()` semantics exactly**

Run: `python -m pytest tests/test_analysis_export_behavior.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/analysis.py tests/test_analysis_export_behavior.py
git commit -m "refactor: add export planning seam"
```

## Task 4: Introduce a Controller Seam Without Changing the UI Layout

**Files:**
- Create: `ui/controller.py`
- Modify: `ui/app.py`
- Create: `tests/test_controller_flow.py`
- Test: `tests/test_controller_flow.py`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Add failing controller flow tests for start/pause/stop behavior using fakes**

```python
def test_controller_starts_analysis_when_settings_are_valid():
    controller = MainWindowController(view=fake_view, settings_service=fake_settings, analysis_service=fake_analysis)
    controller.handle_start()
    assert fake_analysis.run_called is True
```

- [ ] **Step 2: Run controller tests to verify the seam does not exist yet**

Run: `python -m pytest tests/test_controller_flow.py -v`
Expected: FAIL with import error or missing class

- [ ] **Step 3: Implement `MainWindowController` with a minimal public API**

```python
class MainWindowController:
    def handle_start(self): ...
    def handle_pause(self): ...
    def handle_stop(self): ...
    def handle_close_request(self): ...
```

- [ ] **Step 4: Refactor existing `_on_start`, `_on_pause`, `_on_stop`, and display-change entry points to become thin wrappers around the controller**

```python
self.controller = MainWindowController(view=self, settings_service=self.settings_service, analysis_service=self.analysis_service)

def _on_start(self):
    self.controller.handle_start()
```

- [ ] **Step 5: Preserve the existing signal wiring first, then reroute the wrapper methods only after direct duplicate logic has been removed**

```python
self.tab_basic.plot_params_changed.connect(self.controller.handle_display_settings_changed)
```

- [ ] **Step 6: Run controller and smoke tests**

Run: `python -m pytest tests/test_controller_flow.py tests/test_ui_smoke.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ui/controller.py ui/app.py tests/test_controller_flow.py tests/test_ui_smoke.py
git commit -m "refactor: add main window controller seam"
```

## Task 5: Separate Plotting Logic From Workflow Logic

**Files:**
- Create: `ui/plot_presenter.py`
- Modify: `ui/app.py`
- Create: `tests/test_plot_presenter.py`
- Test: `tests/test_plot_presenter.py`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Add failing tests for plot-mode result selection and redraw input shaping**

```python
def test_plot_presenter_prefers_interp_when_filter_mode_has_interp():
    settings = DisplaySettings(plot_now=2, grid_skip=1, quiver_factor=5.0, vector_color="lime")
    payload = make_result_payload()
    selected = choose_vectors(payload, settings)
    assert selected.u is payload["u_interp"]
```

- [ ] **Step 2: Run plot presenter tests to confirm the helper is missing**

Run: `python -m pytest tests/test_plot_presenter.py -v`
Expected: FAIL with import error or missing helper

- [ ] **Step 3: Implement a plot presenter API that matches the tests and current redraw split**

```python
def choose_vectors(results, display_settings):
    ...

class PlotPresenter:
    def redraw(self, axes, figure, canvas, image, results, display_settings): ...
```

- [ ] **Step 4: Update `ui/app.py` to delegate vector selection and redraw policy to the presenter**

Run: `python -m pytest tests/test_plot_presenter.py tests/test_ui_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Remove direct widget reads from redraw code where the presenter can use cached display settings**

Run: `python -m pytest tests/test_plot_presenter.py tests/test_ui_smoke.py tests/test_controller_flow.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ui/plot_presenter.py ui/app.py tests/test_plot_presenter.py tests/test_ui_smoke.py tests/test_controller_flow.py
git commit -m "refactor: isolate plot presentation logic"
```

## Task 6: Lock Down Close / Cancel Lifecycle Behavior

**Files:**
- Modify: `ui/controller.py`
- Modify: `ui/app.py`
- Modify: `services/analysis.py`
- Modify: `tests/test_controller_flow.py`
- Test: `tests/test_controller_flow.py`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Add failing tests for close-while-running acceptance/decline behavior**

```python
def test_close_while_running_decline_keeps_window_open():
    result = controller.handle_close_request()
    assert result.should_close is False

def test_close_while_running_accept_requests_stop_before_shutdown():
    result = controller.handle_close_request()
    assert fake_analysis.stop_called is True
```

- [ ] **Step 2: Add tests for idle close preserving save-and-shutdown guarantees**

```python
def test_close_while_idle_still_saves_and_shuts_down():
    result = controller.handle_close_request()
    assert fake_settings.save_called is True
    assert fake_analysis.shutdown_called is True
```

- [ ] **Step 3: Run controller tests to observe missing close invariants**

Run: `python -m pytest tests/test_controller_flow.py -v`
Expected: FAIL on close flow assertions

- [ ] **Step 4: Implement explicit close-ordering behavior in the controller**

```python
if analysis_service.is_running:
    confirmed = view.confirm_close_while_running()
    if not confirmed:
        return CloseDecision(should_close=False)
    analysis_service.stop()
```

- [ ] **Step 5: Preserve save-on-close and guaranteed shutdown behavior while adding safe handling for late signals**

Run: `python -m pytest tests/test_controller_flow.py tests/test_ui_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ui/controller.py ui/app.py services/analysis.py tests/test_controller_flow.py tests/test_ui_smoke.py
git commit -m "refactor: codify close and cancel lifecycle"
```

## Task 7: Extract Export / Overwrite Planning From Analysis Internals

**Files:**
- Modify: `services/analysis.py`
- Modify: `ui/controller.py`
- Modify: `tests/test_analysis_export_behavior.py`
- Test: `tests/test_analysis_export_behavior.py`
- Test: `tests/test_controller_flow.py`

- [ ] **Step 1: Introduce a helper seam for export folder planning and skip decisions inside `services/analysis.py`**

```python
def build_export_plan(image_pairs, basic_opts, output_dir, force_overwrite):
    ...
```

- [ ] **Step 2: Run export-behavior tests and verify failures narrow to compatibility details**

Run: `python -m pytest tests/test_analysis_export_behavior.py -v`
Expected: FAIL on behavior details, not missing helpers

- [ ] **Step 3: Implement current-compatibility behavior exactly**

```python
should_skip = all((folder_path / f"{stem}{output_ext}").exists() for folder_path, _ in current_exports)
```

- [ ] **Step 4: Move overwrite-confirmation preflight decisions to the controller using the helper seam**

Run: `python -m pytest tests/test_analysis_export_behavior.py tests/test_controller_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/analysis.py ui/controller.py tests/test_analysis_export_behavior.py tests/test_controller_flow.py
git commit -m "refactor: extract export planning behavior"
```

## Task 8: Normalize Settings Collection and Model Conversion

**Files:**
- Modify: `services/settings.py`
- Modify: `ui/controller.py`
- Modify: `ui/app.py`
- Modify: `tests/test_settings.py`
- Modify: `tests/test_controller_flow.py`
- Test: `tests/test_settings.py`
- Test: `tests/test_controller_flow.py`

- [ ] **Step 1: Add failing tests for converting collected tab values into a single app settings model while preserving persisted schema**

```python
def test_controller_collects_perf_values_but_persists_them_under_basic():
    model = controller.collect_settings_model()
    persisted = to_persisted_dict(model)
    assert persisted["basic"]["compute_mode"] == "cpu_parallel"
```

- [ ] **Step 2: Run settings and controller tests**

Run: `python -m pytest tests/test_settings.py tests/test_controller_flow.py -v`
Expected: FAIL on missing conversion helpers or serialization seams

- [ ] **Step 3: Implement minimal dataclass models and conversion helpers without changing on-disk schema**

```python
@dataclass
class AppSettingsModel:
    basic: BasicSettingsModel
    piv: PivSettingsModel
    postproc: PostprocSettingsModel
```

- [ ] **Step 4: Update the controller to collect, validate, and persist through the model boundary**

Run: `python -m pytest tests/test_settings.py tests/test_controller_flow.py tests/test_ui_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/settings.py ui/controller.py ui/app.py tests/test_settings.py tests/test_controller_flow.py tests/test_ui_smoke.py
git commit -m "refactor: normalize settings model conversion"
```

## Task 9: Clean Up Analysis Service Internals While Preserving Its Public Contract

**Files:**
- Modify: `services/analysis.py`
- Modify: `tests/test_analysis_export_behavior.py`
- Modify: `tests/test_controller_flow.py`
- Test: `tests/test_analysis_export_behavior.py`
- Test: `tests/test_controller_flow.py`
- Test: `tests/test_core_parity.py`

- [ ] **Step 1: Extract internal helpers for pair loading, pipeline execution, and progress calculation**

```python
def _run_single_pair(...): ...
def _emit_progress_update(...): ...
```

- [ ] **Step 2: Run targeted tests after each helper extraction**

Run: `python -m pytest tests/test_analysis_export_behavior.py tests/test_controller_flow.py tests/test_core_parity.py -v`
Expected: PASS

- [ ] **Step 3: Ensure no public signal names or emitted payload shapes change**

```python
self._worker.progress.emit(current, total, remaining)
self._worker.result.emit(x, y, results, img, path)
self._worker.completed.emit(time_str, cancelled)
```

- [ ] **Step 4: Re-run the full suite**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/analysis.py tests/test_analysis_export_behavior.py tests/test_controller_flow.py tests/test_core_parity.py
git commit -m "refactor: split analysis internals behind stable signals"
```

## Task 10: Final Verification and Manual Regression

**Files:**
- Test: `tests/test_settings.py`
- Test: `tests/test_settings_validation.py`
- Test: `tests/test_analysis_export_behavior.py`
- Test: `tests/test_controller_flow.py`
- Test: `tests/test_plot_presenter.py`
- Test: `tests/test_ui_smoke.py`
- Test: `tests/test_core_parity.py`

- [ ] **Step 1: Run the full automated suite**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 2: Run the UI-specific suite in isolation**

Run: `python -m pytest tests/test_ui_smoke.py tests/test_controller_flow.py tests/test_plot_presenter.py -v`
Expected: PASS

- [ ] **Step 3: Run the settings and compatibility suite**

Run: `python -m pytest tests/test_settings.py tests/test_settings_validation.py tests/test_analysis_export_behavior.py -v`
Expected: PASS

- [ ] **Step 4: Manual verification checklist**

Run: `pyCCV`
Expected:
- window opens and closes cleanly
- tab switching still works
- plot mode changes still affect the display
- vector color/scale/grid controls still update rendering
- start/pause/stop still behave correctly
- invalid interrogation area settings still show an error
- overwrite confirmation still appears only when appropriate
- settings still persist across close/reopen

- [ ] **Step 5: Headless verification when needed**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "refactor: complete incremental PySide6 architecture cleanup"
```
