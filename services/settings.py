from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any
from config import BASIC_SETTINGS, PIV_SETTINGS, POSTPROC_SETTINGS, VIEWER_SETTINGS, CONVERT_SETTINGS
from .logger import logger
from shared.settings_json import load_json_settings, save_json_settings


@dataclass(frozen=True)
class BasicSettingsModel:
    values: Dict[str, Any]


@dataclass(frozen=True)
class PivSettingsModel:
    values: Dict[str, Any]


@dataclass(frozen=True)
class PostprocSettingsModel:
    values: Dict[str, Any]


@dataclass(frozen=True)
class ViewerSettingsModel:
    values: Dict[str, Any]


@dataclass(frozen=True)
class ConvertSettingsModel:
    values: Dict[str, Any]


@dataclass(frozen=True)
class AppSettingsModel:
    basic: BasicSettingsModel
    piv: PivSettingsModel
    postproc: PostprocSettingsModel
    viewer: ViewerSettingsModel
    convert: ConvertSettingsModel


def to_settings_model(settings: Dict[str, Dict[str, Any]]) -> AppSettingsModel:
    return AppSettingsModel(
        basic=BasicSettingsModel(dict(settings.get("basic", {}))),
        piv=PivSettingsModel(dict(settings.get("piv", {}))),
        postproc=PostprocSettingsModel(dict(settings.get("postproc", {}))),
        viewer=ViewerSettingsModel(dict(settings.get("viewer", {}))),
        convert=ConvertSettingsModel(dict(settings.get("convert", {}))),
    )


def to_persisted_dict(model: AppSettingsModel) -> Dict[str, Dict[str, Any]]:
    return {
        "basic": dict(model.basic.values),
        "piv": dict(model.piv.values),
        "postproc": dict(model.postproc.values),
        "viewer": dict(model.viewer.values),
        "convert": dict(model.convert.values),
    }

class SettingsService:
    def __init__(self, config_path: str = "user_settings.json"):
        # Resolve config path relative to pyCCV directory (1 level up from services/)
        self.config_path = Path(__file__).parent.parent / config_path
        
        self.settings = {
            "basic": BASIC_SETTINGS.copy(),
            "piv": PIV_SETTINGS.copy(),
            "postproc": POSTPROC_SETTINGS.copy(),
            "viewer": VIEWER_SETTINGS.copy(),
            "convert": CONVERT_SETTINGS.copy(),
        }
        self.load_settings()

    def load_settings(self) -> None:
        """Load settings from JSON file"""
        if not self.config_path.exists():
            logger.debug("找不到設定檔，使用預設值")
            return

        try:
            saved = load_json_settings(self.config_path, default={})

            def migrate_key(k):
                # Manual fixes for special cases
                if k == "subpixMethod":
                    return "sub_pix_method"
                if k.startswith("intArea"):
                    return f"int_area_{k[-1]}"

                import re

                # Standard camel to snake
                s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', k)
                return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

            # Deep update with key migration
            for section, values in saved.items():
                if section in self.settings:
                    migrated = {migrate_key(k): v for k, v in values.items()}
                    self.settings[section].update(migrated)
            logger.debug("載入設定 | 檔案=%s", self.config_path)
        except Exception as e:
            logger.error("載入設定失敗 | 檔案=%s | 原因=%s", self.config_path, e)

    def save_settings(self) -> None:
        """Save settings to JSON file"""
        try:
            save_json_settings(self.config_path, self.settings, indent=4, ensure_ascii=False)
            logger.debug("儲存設定 | 檔案=%s", self.config_path)
        except Exception as e:
            logger.error("儲存設定失敗 | 檔案=%s | 原因=%s", self.config_path, e)

    def update(self, section: str, key: str, value: Any) -> None:
        """Update a specific setting"""
        if section in self.settings and key in self.settings[section]:
            self.settings[section][key] = value
        else:
            logger.warning(f"Attempted to update unknown setting: {section}.{key}")

    def get(self, section: str, key: str = None) -> Any:
        """Get a setting value or section (returns a copy when key is None)"""
        if section not in self.settings:
            return None
        if key is None:
            return dict(self.settings[section])
        return self.settings[section].get(key)

    def merge(self, section: str, values: dict) -> None:
        """Merge values into a settings section (mutates internal state)"""
        if section in self.settings:
            self.settings[section].update(values)

    def get_model(self) -> AppSettingsModel:
        return to_settings_model(self.settings)

    def apply_model(self, model: AppSettingsModel) -> None:
        self.settings = to_persisted_dict(model)
