# -*- coding: utf-8 -*-
"""Nova Windows Tools - Comprehensive Unit Tests for the Command Architecture.

Tests cover all 12 specified requirements:
1. Recognition of the 5 distinct command categories.
2. Exact leading space preservation and missing-prefix detection.
3. Empty inputs, malformed commands, and helpful suggestions.
4. Subcommands, positional arguments, and option flags.
5. Settings menu entry, hierarchical navigation, and '<' exit.
6. Unsaved settings change detection and confirmation guard.
7. Settings persistence across application restarts and backup restore.
8. Accurate system discovery (no false-positive installed status).
9. Full update pipeline: check, preview, download, SHA256 verify, backup, install.
10. Network failure retries, security mismatch detection, and automatic rollback.
11. Cancellation handling and clean resource cleanup.
12. Backward compatibility with Easy Windows Tools interfaces and modules.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from nova.core.audit import AuditLogger
from nova.core.constants import APP_NAME, APP_VERSION
from nova.core.parser import CommandCategory, CommandParser, ParsedCommand
from nova.core.permissions import PermissionLevel, PermissionManager
from nova.core.registry import CommandContext, CommandDefinition, CommandRegistry
from nova.core.router import CommandRouter
from nova.discovery.ecosystem import ComponentStatus, DiscoveredComponent, EcosystemDiscovery
from nova.settings.interactive import InteractiveSettingsREPL
from nova.settings.manager import SettingsManager
from nova.settings.model import SettingItem
from nova.updates.manager import UpdateItem, UpdateManager


class NovaCommandSystemTests(unittest.TestCase):
    """Test suite for Nova Windows Tools command system."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.config_file = self.temp_path / "settings.json"
        self.audit_log_file = self.temp_path / "audit.log"
        self.staging_dir = self.temp_path / "staging"
        self.backup_dir = self.temp_path / "backups"
        self.history_file = self.temp_path / "history.json"

        self.audit_logger = AuditLogger(log_file=self.audit_log_file)
        self.permission_manager = PermissionManager(
            audit_logger=self.audit_logger,
            confirm_callback=lambda prompt: True,
        )
        self.settings_manager = SettingsManager(config_file=self.config_file)
        self.discovery = EcosystemDiscovery()

    def tearDown(self):
        self.temp_dir.cleanup()

    # =========================================================================
    # 1. Her beş komut kategorisinin doğru algılanması
    # =========================================================================
    def test_01_all_five_command_categories_detected(self):
        # A. Normal commands (Leading space)
        cmd_a = CommandParser.parse(" help")
        self.assertEqual(cmd_a.category, CommandCategory.NORMAL)
        self.assertEqual(cmd_a.name, "help")

        cmd_a2 = CommandParser.parse(" status")
        self.assertEqual(cmd_a2.category, CommandCategory.NORMAL)
        self.assertEqual(cmd_a2.name, "status")

        # B. Important commands ('/')
        cmd_b = CommandParser.parse("/system")
        self.assertEqual(cmd_b.category, CommandCategory.IMPORTANT)
        self.assertEqual(cmd_b.name, "system")

        cmd_b2 = CommandParser.parse("/diagnostics")
        self.assertEqual(cmd_b2.category, CommandCategory.IMPORTANT)
        self.assertEqual(cmd_b2.name, "diagnostics")

        # C. Nova ecosystem settings ('>')
        cmd_c = CommandParser.parse(">")
        self.assertEqual(cmd_c.category, CommandCategory.SETTINGS)
        self.assertEqual(cmd_c.name, "")

        cmd_c2 = CommandParser.parse("> apps")
        self.assertEqual(cmd_c2.category, CommandCategory.SETTINGS)
        self.assertEqual(cmd_c2.name, "apps")

        # D. Settings exit ('<')
        cmd_d = CommandParser.parse("<")
        self.assertEqual(cmd_d.category, CommandCategory.SETTINGS_EXIT)

        # E. Full update system ('#')
        cmd_e = CommandParser.parse("#")
        self.assertEqual(cmd_e.category, CommandCategory.UPDATE)
        self.assertEqual(cmd_e.name, "")

        cmd_e2 = CommandParser.parse("# check")
        self.assertEqual(cmd_e2.category, CommandCategory.UPDATE)
        self.assertEqual(cmd_e2.name, "check")

    # =========================================================================
    # 2. Başlangıç boşluklarının doğru işlenmesi
    # =========================================================================
    def test_02_leading_space_preserved_and_missing_prefix_rejected(self):
        # Raw input with leading space is parsed as NORMAL
        cmd = CommandParser.parse(" version")
        self.assertEqual(cmd.category, CommandCategory.NORMAL)
        self.assertEqual(cmd.name, "version")

        # Raw input without leading space MUST NOT silently be accepted as NORMAL
        accidental = CommandParser.parse("help")
        self.assertEqual(accidental.category, CommandCategory.INVALID_PREFIX)
        self.assertFalse(accidental.is_valid)
        self.assertIn("BOŞLUK", accidental.suggestion)
        self.assertIn(" help", accidental.suggestion)

        # Another missing prefix test
        accidental_status = CommandParser.parse("status")
        self.assertEqual(accidental_status.category, CommandCategory.INVALID_PREFIX)
        self.assertIn(" status", accidental_status.suggestion)

    # =========================================================================
    # 3. Boş girişler ve hatalı komutlar
    # =========================================================================
    def test_03_empty_and_malformed_inputs(self):
        # Completely empty
        empty1 = CommandParser.parse("")
        self.assertEqual(empty1.category, CommandCategory.EMPTY)
        self.assertFalse(empty1.is_valid)

        # None input
        empty_none = CommandParser.parse(None)
        self.assertEqual(empty_none.category, CommandCategory.EMPTY)

        # Single space without command name
        space_only = CommandParser.parse(" ")
        self.assertEqual(space_only.category, CommandCategory.NORMAL)
        self.assertIsNotNone(space_only.error)

        # Slash without command name
        slash_only = CommandParser.parse("/")
        self.assertEqual(slash_only.category, CommandCategory.IMPORTANT)
        self.assertIsNotNone(slash_only.error)

        # Unknown word gives helpful guidance
        unknown = CommandParser.parse("bilinmeyen_komut_123")
        self.assertEqual(unknown.category, CommandCategory.INVALID_PREFIX)
        self.assertIsNotNone(unknown.suggestion)

    # =========================================================================
    # 4. Alt komutlar ve argümanlar
    # =========================================================================
    def test_04_subcommands_arguments_and_options(self):
        # Complex normal command with options
        cmd = CommandParser.parse(' record 30dk --fps 60 --resolution 1920x1080 --no-audio')
        self.assertEqual(cmd.category, CommandCategory.NORMAL)
        self.assertEqual(cmd.name, "record")
        self.assertEqual(cmd.subcommand, "30dk")
        self.assertEqual(cmd.options.get("fps"), "60")
        self.assertEqual(cmd.options.get("resolution"), "1920x1080")
        self.assertTrue(cmd.options.get("no_audio"))

        # Important command with subcommand and positional args
        cmd2 = CommandParser.parse("/mcp start my-desktop-server")
        self.assertEqual(cmd2.category, CommandCategory.IMPORTANT)
        self.assertEqual(cmd2.name, "mcp")
        self.assertEqual(cmd2.subcommand, "start")
        self.assertEqual(cmd2.args, ["my-desktop-server"])

        # Update command with subcommand
        cmd3 = CommandParser.parse("# download nova-windows-tools")
        self.assertEqual(cmd3.category, CommandCategory.UPDATE)
        self.assertEqual(cmd3.name, "download")
        self.assertEqual(cmd3.subcommand, "nova-windows-tools")

    # =========================================================================
    # 5. Ayarlar menüsüne giriş, menüler arası gezinme ve '<' ile çıkış
    # =========================================================================
    def test_05_settings_navigation_and_exit(self):
        outputs = []
        repl = InteractiveSettingsREPL(
            settings_manager=self.settings_manager,
            discovery=self.discovery,
            print_func=lambda msg: outputs.append(msg),
            confirm_func=lambda prompt: "e",
        )

        # 1. Enter root
        repl.enter()
        self.assertTrue(repl.is_active)
        self.assertIsNone(repl.current_category)
        self.assertIn("[Nova Ayarlar]", repl.get_prompt_text())

        # 2. Navigate to 'ai'
        repl.handle_input("cd ai")
        self.assertEqual(repl.current_category, "ai")
        self.assertIn("[Nova Ayarlar > ai]", repl.get_prompt_text())

        # 3. '<' moves from subcategory back to root
        active = repl.handle_input("<")
        self.assertTrue(active)
        self.assertIsNone(repl.current_category)
        self.assertIn("[Nova Ayarlar]", repl.get_prompt_text())

        # 4. '<' at root exits settings REPL
        active2 = repl.handle_input("<")
        self.assertFalse(active2)
        self.assertFalse(repl.is_active)

    # =========================================================================
    # 6. Kaydedilmemiş ayar değişiklikleri
    # =========================================================================
    def test_06_unsaved_changes_confirmation_guard(self):
        repl = InteractiveSettingsREPL(
            settings_manager=self.settings_manager,
            print_func=lambda msg: None,
            confirm_func=lambda prompt: "d",  # User chooses "D" (Stay)
        )
        repl.enter("ai")

        # Stage a change without saving
        ok, _ = self.settings_manager.set_value("ai.temperature", 1.5)
        self.assertTrue(ok)
        self.assertTrue(self.settings_manager.has_unsaved_changes())
        self.assertIn("ai.temperature", self.settings_manager.dirty_keys)

        # Move to root
        repl.handle_input("<")
        self.assertIsNone(repl.current_category)

        # User chooses 'D' -> exit is aborted, remains active
        active = repl.handle_input("<")
        self.assertTrue(active)
        self.assertTrue(repl.is_active)

        # Now simulate user choosing 'H' (Discard and exit)
        repl._confirm_func = lambda prompt: "h"
        active2 = repl.handle_input("<")
        self.assertFalse(active2)
        self.assertFalse(repl.is_active)
        self.assertFalse(self.settings_manager.has_unsaved_changes())
        self.assertEqual(self.settings_manager.get_value("ai.temperature"), 0.7)  # Reverted!

    # =========================================================================
    # 7. Ayarların uygulama yeniden başlatıldıktan sonra korunması
    # =========================================================================
    def test_07_settings_persistence_and_restore(self):
        # 1. Modify and save
        ok, _ = self.settings_manager.set_value("system.default_duration_minutes", 45)
        self.assertTrue(ok)
        ok_save = self.settings_manager.save()
        self.assertTrue(ok_save)
        self.assertTrue(self.config_file.is_file())

        # 2. Simulate application restart by creating a new SettingsManager instance
        new_manager = SettingsManager(config_file=self.config_file)
        self.assertEqual(new_manager.get_value("system.default_duration_minutes"), 45)

        # 3. Test backup restoration
        ok_backup = new_manager.restore_backup()
        # Backup exists and restore succeeds
        self.assertTrue(new_manager.backup_file.is_file())
        self.assertTrue(ok_backup)

    # =========================================================================
    # 8. Kurulu olmayan uygulamaların yanlışlıkla kurulu gösterilmemesi
    # =========================================================================
    def test_08_uninstalled_tools_marked_missing_accurately(self):
        with patch.object(self.discovery, "_run_command", return_value="1.0.0"):
            components = self.discovery.discover_all(force_refresh=True)
        by_id = {c.id: c for c in components}

        # Python is always active in this test runner
        self.assertIn("python", by_id)
        self.assertEqual(by_id["python"].status, ComponentStatus.ACTIVE)

        # Check that missing tools are NOT falsely marked as installed
        with patch("shutil.which", return_value=None):
            dev_tools = self.discovery._scan_development_tools()
            self.assertEqual(dev_tools["git"].status, ComponentStatus.MISSING)
            self.assertEqual(dev_tools["nodejs"].status, ComponentStatus.MISSING)
            self.assertEqual(dev_tools["vscode"].status, ComponentStatus.MISSING)

        with patch("urllib.request.urlopen", side_effect=OSError("Offline")):
            with patch("shutil.which", return_value=None):
                ai_tools = self.discovery._scan_ai_tools()
                self.assertEqual(ai_tools["ollama"].status, ComponentStatus.MISSING)

    # =========================================================================
    # 9. Güncelleme kontrolü, indirme, doğrulama, onay ve kurulum aşamaları
    # =========================================================================
    def test_09_full_update_pipeline_with_hash_verification(self):
        pkg_payload = b"Nova Windows Tools v3.1.0 update binary content"
        computed_sha256 = hashlib.sha256(pkg_payload).hexdigest()

        mock_manifest = {
            "repository": "https://github.com/Robito-gif/nova-windows-tools",
            "channels": {
                "stable": {
                    "nova-windows-tools": {
                        "name": "Nova Windows Tools (Çekirdek Sistem)",
                        "version": "3.1.0",
                        "download_url": "https://example.com/nova.zip",
                        "sha256": computed_sha256,
                        "size_bytes": len(pkg_payload),
                        "changelog": "• Test update changelog",
                    }
                }
            }
        }

        updater = UpdateManager(
            staging_dir=self.staging_dir,
            backup_dir=self.backup_dir,
            history_file=self.history_file,
            manifest_override=mock_manifest,
            audit_logger=self.audit_logger,
        )

        # 1. Check
        updates = updater.check_updates()
        self.assertEqual(len(updates), 1)
        self.assertTrue(updates[0].has_update)

        # 2. Preview
        preview_text = updater.preview("nova-windows-tools")
        self.assertIn("NOVA GÜNCELLEME ÖNİZLEMESİ", preview_text)
        self.assertIn("3.1.0", preview_text)

        # 3. Download & Hash verify
        ok_dl, msg_dl = updater.download("nova-windows-tools", mock_data=pkg_payload)
        self.assertTrue(ok_dl)
        self.assertIn("başarıyla indirildi ve doğrulandı", msg_dl)

        # 4. Install with confirmation
        ok_ins, msg_ins = updater.install("nova-windows-tools", confirm_callback=lambda p: True)
        self.assertTrue(ok_ins)
        self.assertIn("başarıyla kuruldu", msg_ins)

        # Verify backup was created
        backups = list(self.backup_dir.glob("nova-windows-tools_*"))
        self.assertEqual(len(backups), 1)

        # Verify history was recorded
        history = updater.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "install")

    # =========================================================================
    # 10. Ağ bağlantısı kesildiğinde ve güncelleme başarısız olduğunda hata yönetimi
    # =========================================================================
    def test_10_network_failure_and_automatic_rollback(self):
        mock_manifest = {
            "channels": {
                "stable": {
                    "nova-windows-tools": {
                        "name": "Nova Windows Tools",
                        "version": "3.1.0",
                        "download_url": "https://invalid.unreachable.domain/pkg.zip",
                        "sha256": "badhash123",
                        "size_bytes": 100,
                        "changelog": "None",
                    }
                }
            }
        }
        updater = UpdateManager(
            staging_dir=self.staging_dir,
            backup_dir=self.backup_dir,
            history_file=self.history_file,
            manifest_override=mock_manifest,
            audit_logger=self.audit_logger,
        )

        # Network failure during download
        with patch("time.sleep", return_value=None):
            with patch("urllib.request.urlopen", side_effect=OSError("Network down")):
                ok_dl, err_msg = updater.download("nova-windows-tools")
                self.assertFalse(ok_dl)
                self.assertIn("Ağ hatası", err_msg)

        # Hash mismatch check
        bad_payload = b"altered corrupted data"
        ok_hash, err_hash = updater.download("nova-windows-tools", mock_data=bad_payload)
        self.assertFalse(ok_hash)
        self.assertIn("bütünlük doğrulaması başarısız", err_hash)

        # Simulated installation failure triggers automatic rollback
        good_payload = b"good data"
        good_hash = hashlib.sha256(good_payload).hexdigest()
        mock_manifest["channels"]["stable"]["nova-windows-tools"]["sha256"] = good_hash
        updater.download("nova-windows-tools", mock_data=good_payload)

        ok_fail, msg_fail = updater.install("nova-windows-tools", simulate_failure=True)
        self.assertFalse(ok_fail)
        self.assertIn("otomatik olarak önceki sürüme geri döndürüldü", msg_fail)

    # =========================================================================
    # 11. İptal edilen işlemlerin kaynakları düzgün serbest bırakması
    # =========================================================================
    def test_11_cancellation_releases_resources(self):
        updater = UpdateManager(
            staging_dir=self.staging_dir,
            backup_dir=self.backup_dir,
            history_file=self.history_file,
            audit_logger=self.audit_logger,
        )

        cancel_event = threading.Event()
        cancel_event.set()  # Cancel immediately

        ok, msg = updater.download("nova-windows-tools", cancel_event=cancel_event)
        self.assertFalse(ok)
        self.assertIn("iptal edildi", msg)

        # Ensure no leftover files in staging
        staged_files = list(self.staging_dir.glob("*.pkg"))
        self.assertEqual(len(staged_files), 0)

    # =========================================================================
    # 12. Mevcut Easy Windows Tools özelliklerinin geriye dönük uyumluluğu
    # =========================================================================
    def test_12_backward_compatibility_interfaces(self):
        import easy_windows_tools as legacy
        import nova_windows_tools as modern

        # Check exported classes exist and match
        self.assertTrue(hasattr(legacy, "LocalWebSocketManager"))
        self.assertTrue(hasattr(legacy, "MCPManager"))
        self.assertTrue(hasattr(legacy, "ScreenRecorder"))
        self.assertTrue(hasattr(legacy, "KeepAwakeApp"))

        self.assertTrue(hasattr(modern, "NovaApp"))
        self.assertTrue(hasattr(modern, "LocalWebSocketManager"))
        self.assertTrue(hasattr(modern, "MCPManager"))
        self.assertTrue(hasattr(modern, "ScreenRecorder"))

        # Check updated branding
        self.assertEqual(legacy.APP_NAME, "Nova Windows Tools")
        self.assertEqual(legacy.APP_VERSION, "3.0.0")
        self.assertEqual(modern.APP_NAME, "Nova Windows Tools")


if __name__ == "__main__":
    unittest.main()
