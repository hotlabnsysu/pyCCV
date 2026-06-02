from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from services.analysis import build_export_plan
from services.logger import logger
from services.settings import to_persisted_dict, to_settings_model


class MainWindowController:
    def __init__(self, view, settings_service, analysis_service):
        self.view = view
        self.settings_service = settings_service
        self.analysis_service = analysis_service

    def handle_start(self):
        if self.analysis_service.is_running:
            return

        self.view.btn_start.setEnabled(False)

        try:
            self.view._update_settings_from_ui()
        except ValueError:
            self.view.btn_start.setEnabled(True)
            return

        settings_model = self.collect_settings_model()
        self._apply_settings_model(settings_model)
        self.settings_service.save_settings()

        input_dir = self.settings_service.get("basic", "input_dir")
        output_dir = self.settings_service.get("basic", "output_dir")

        basic_vals = self.view.tab_basic.get_values()
        custom_enabled = basic_vals.get("custom_select_enabled", False)
        custom_images = basic_vals.get("custom_selected_images", [])

        if not input_dir and not (custom_enabled and custom_images):
            QMessageBox.critical(self.view, "錯誤", "請選擇輸入目錄或選取影像檔案")
            self.view.btn_start.setEnabled(True)
            return

        has_exports = any(
            self.settings_service.get("basic", k)
            for k in ("export_raw", "export_filt", "export_interp", "export_smooth")
        )
        if has_exports and not output_dir:
            QMessageBox.critical(self.view, "錯誤", "已啟用輸出選項但未設定輸出目錄，請先選擇輸出目錄")
            self.view.btn_start.setEnabled(True)
            return

        if custom_enabled and custom_images:
            logger.info("分析開始 | 影像=%d (自訂選取)", len(custom_images))
        else:
            logger.info("分析開始 | 輸入=%s", input_dir)

        settings = to_persisted_dict(settings_model)

        try:

            if custom_enabled and custom_images:
                selected_files = sorted(Path(path) for path in custom_images)
                if len(selected_files) < 2:
                    logger.warning("需要至少選取 2 個影像檔案")
                    self.view.btn_start.setEnabled(True)
                    return
                pairs = [
                    (selected_files[index], selected_files[index + 1])
                    for index in range(len(selected_files) - 1)
                ]
                logger.info("使用自訂選取 | 影像對=%d", len(pairs))
            else:
                pairs = self.analysis_service.get_image_pairs(input_dir)

            if not pairs:
                logger.warning("未找到影像檔案")
                self.view.btn_start.setEnabled(True)
                return
        except Exception as exc:
            logger.error("檢查檔案失敗: %s", exc)
            self.view.btn_start.setEnabled(True)
            return

        force_overwrite = False
        export_plan = build_export_plan(pairs, settings["basic"], output_dir)
        if export_plan["has_output_options"] and export_plan["existing_folders"]:
            folder_names = "\n".join(folder.name for folder in export_plan["existing_folders"])
            button = QMessageBox.question(
                self.view,
                "輸出資料夾已存在",
                f"以下輸出資料夾已存在：\n{folder_names}\n\n選擇「Yes」覆蓋現有檔案\n選擇「No」取消分析",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if button != QMessageBox.StandardButton.Yes:
                logger.info("分析已取消")
                self.view.btn_start.setEnabled(True)
                return
            force_overwrite = True
            logger.info("將覆蓋現有輸出檔案")

        self.view.progress_bar.setValue(0)
        self.view.progress_text.setText("啟動中...")

        self.analysis_service.run_analysis(
            image_pairs=pairs,
            settings=settings,
            output_dir=output_dir,
            force_overwrite=force_overwrite,
        )

    def handle_stop(self):
        if not self.analysis_service.is_running:
            return

        button = QMessageBox.question(
            self.view,
            "停止",
            "確定停止分析?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if button != QMessageBox.StandardButton.Yes:
            return

        self.analysis_service.stop()
        self.view.btn_pause.setText("暫停")
        logger.info("停止中...")

    def handle_pause(self):
        if not self.analysis_service.is_running:
            return

        if self.analysis_service.is_paused:
            self.analysis_service.resume()
            self.view.btn_pause.setText("暫停")
            logger.info("繼續分析")
            return

        self.analysis_service.pause()
        self.view.btn_pause.setText("繼續")
        logger.info("暫停分析")

    def handle_close_request(self):
        if self.analysis_service.is_running:
            button = QMessageBox.question(
                self.view,
                "警告",
                "分析正在進行中，確定要關閉嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if button != QMessageBox.StandardButton.Yes:
                return False
            self.analysis_service.stop()

        if hasattr(self.view, "_set_closing_state"):
            self.view._set_closing_state(True)

        try:
            self.view._update_settings_from_ui()
            settings_model = self.collect_settings_model()
            self._apply_settings_model(settings_model)
            self.settings_service.save_settings()
        except Exception:
            logger.exception("關閉時儲存設定失敗")
        finally:
            self.analysis_service.shutdown()

        return True

    def handle_display_settings_changed(self):
        QTimer.singleShot(10, self.view._redraw_display)

    def collect_settings_model(self):
        if hasattr(self.settings_service, "get_model"):
            return self.settings_service.get_model()
        return to_settings_model(self.settings_service.settings)

    def _apply_settings_model(self, settings_model):
        if hasattr(self.settings_service, "apply_model"):
            self.settings_service.apply_model(settings_model)
            return
        self.settings_service.settings = to_persisted_dict(settings_model)
