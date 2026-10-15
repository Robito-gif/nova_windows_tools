# -*- coding: utf-8 -*-
"""Nova Windows Tools - Settings Manager.

Provides comprehensive settings lifecycle: validation, persistent storage,
change tracking, atomic file writes, backup & restore, export & import, and search.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from nova.core.constants import (
    LEGACY_APPDATA,
    SETTINGS_BACKUP_FILE,
    SETTINGS_FILE,
)
from nova.settings.model import SettingItem
from nova.settings.providers import (
    AISettingsProvider,
    AppsSettingsProvider,
    DevelopmentSettingsProvider,
    MCPSettingsProvider,
    NetworkSettingsProvider,
    SecuritySettingsProvider,
    SettingsProvider,
    SystemSettingsProvider,
    UpdatesSettingsProvider,
)


class SettingsManager:
    """Central manager for ecosystem settings."""

    def __init__(self, config_file: Path | str | None = None):
        self.config_file = Path(config_file) if config_file else SETTINGS_FILE
        self.backup_file = self.config_file.parent / (self.config_file.stem + ".backup.json")
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        self._providers: dict[str, SettingsProvider] = {}
        self._items: dict[str, SettingItem] = {}
        self._dirty_keys: set[str] = set()
        self._lock = threading.RLock()

        # Register standard built-in providers
        self.register_provider(AISettingsProvider())
        self.register_provider(MCPSettingsProvider())
        self.register_provider(DevelopmentSettingsProvider())
        self.register_provider(SystemSettingsProvider())
        self.register_provider(UpdatesSettingsProvider())
        self.register_provider(NetworkSettingsProvider())
        self.register_provider(SecuritySettingsProvider())
        self.register_provider(AppsSettingsProvider())

        # Load persisted values
        self.load()

    def register_provider(self, provider: SettingsProvider) -> None:
        """Register a new settings provider dynamically."""
        with self._lock:
            self._providers[provider.category] = provider
            for item in provider.get_settings():
                self._items[item.key] = item

    def get_item(self, key: str) -> SettingItem | None:
        """Get SettingItem by key."""
        with self._lock:
            return self._items.get(key)

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get the current value of a setting."""
        with self._lock:
            item = self._items.get(key)
            return item.current_value if item else default

    def set_value(self, key: str, raw_value: Any) -> tuple[bool, str | None]:
        """Validate and stage a setting modification."""
        with self._lock:
            item = self._items.get(key)
            if not item:
                return False, f"Ayar bulunamadı: '{key}'"

            # Validate against rules and types
            is_valid, error = item.validate(raw_value)
            if not is_valid:
                return False, error

            # Cast and assign
            typed_val = item.cast_value(raw_value)
            if item.current_value != typed_val:
                item.current_value = typed_val
                self._dirty_keys.add(key)

            return True, None

    @property
    def dirty_keys(self) -> set[str]:
        """Return the set of modified keys not yet saved to disk."""
        with self._lock:
            return set(self._dirty_keys)

    def has_unsaved_changes(self) -> bool:
        """Return True if there are staged modifications."""
        with self._lock:
            return bool(self._dirty_keys)

    def save(self) -> bool:
        """Atomically persist current settings to disk and create a backup."""
        with self._lock:
            data = {key: item.current_value for key, item in self._items.items()}
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # 1. Create backup of current file if it exists
            if self.config_file.is_file():
                try:
                    shutil.copy2(self.config_file, self.backup_file)
                except OSError:
                    pass

            # 2. Write to temporary file first, then atomically replace
            try:
                temp_dir = self.config_file.parent
                with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
                    json.dump(data, tf, indent=2, ensure_ascii=False)
                    temp_path = Path(tf.name)

                temp_path.replace(self.config_file)
                if not self.backup_file.is_file():
                    try:
                        shutil.copy2(self.config_file, self.backup_file)
                    except OSError:
                        pass
                self._dirty_keys.clear()
                return True
            except OSError:
                return False

    def load(self) -> bool:
        """Load settings from file or migrate from legacy location."""
        with self._lock:
            target_path = self.config_file

            # Check if file exists, else check legacy location
            if not target_path.is_file():
                legacy_file = LEGACY_APPDATA / "settings.json"
                if legacy_file.is_file():
                    target_path = legacy_file

            if not target_path.is_file():
                return False

            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                if not isinstance(stored, dict):
                    return False

                for key, val in stored.items():
                    if key in self._items:
                        item = self._items[key]
                        ok, _ = item.validate(val)
                        if ok:
                            item.current_value = item.cast_value(val)

                self._dirty_keys.clear()
                return True
            except (json.JSONDecodeError, OSError):
                return False

    def revert_unsaved(self) -> None:
        """Discard all staged changes and reload from disk."""
        with self._lock:
            # Revert items back to default or reloaded file state
            for key in self._dirty_keys:
                if key in self._items:
                    self._items[key].current_value = self._items[key].default_value
            self._dirty_keys.clear()
            self.load()

    def restore_backup(self) -> bool:
        """Restore settings from backup file."""
        with self._lock:
            if not self.backup_file.is_file():
                return False
            try:
                shutil.copy2(self.backup_file, self.config_file)
                self.load()
                return True
            except OSError:
                return False

    def reset_defaults(self, category: str | None = None) -> list[str]:
        """Reset all or category-specific settings to defaults."""
        with self._lock:
            reset_keys = []
            for key, item in self._items.items():
                if category is None or item.category == category:
                    if item.current_value != item.default_value:
                        item.current_value = item.default_value
                        self._dirty_keys.add(key)
                        reset_keys.append(key)
            return reset_keys

    def export_to_file(self, target_path: Path | str) -> bool:
        """Export all current settings to an external JSON file."""
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {key: item.current_value for key, item in self._items.items()}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except OSError:
            return False

    def import_from_file(self, source_path: Path | str) -> tuple[bool, str | None]:
        """Import settings from an external JSON file."""
        path = Path(source_path)
        if not path.is_file():
            return False, f"İçe aktarma dosyası bulunamadı: '{source_path}'"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False, "Geçersiz yapılandırma dosyası biçimi."

            applied = 0
            for key, val in data.items():
                if key in self._items:
                    ok, _ = self.set_value(key, val)
                    if ok:
                        applied += 1
            return True, f"{applied} ayar başarıyla yüklendi (Kalıcı kaydetmek için 'save' yazın)."
        except (json.JSONDecodeError, OSError) as err:
            return False, f"Ayar dosyası okunamadı: {err}"

    def search(self, query: str) -> list[SettingItem]:
        """Search settings across keys, names, descriptions, and categories."""
        q = query.lower().strip()
        if not q:
            return []
        with self._lock:
            return [
                item for item in self._items.values()
                if q in item.key.lower()
                or q in item.name.lower()
                or q in item.description.lower()
                or q in item.category.lower()
            ]

    def list_categories(self) -> list[dict[str, str]]:
        """Return metadata for all registered categories."""
        with self._lock:
            return [
                {
                    "category": prov.category,
                    "name": prov.name,
                    "description": prov.description,
                    "item_count": sum(1 for item in self._items.values() if item.category == prov.category),
                }
                for prov in self._providers.values()
            ]

    def list_items(self, category: str | None = None) -> list[SettingItem]:
        """List settings items, optionally filtered by category."""
        with self._lock:
            if category:
                return [item for item in self._items.values() if item.category == category]
            return list(self._items.values())
