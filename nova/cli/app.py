# -*- coding: utf-8 -*-
"""Nova Windows Tools - Central Application Engine.

Unifies power controls, recording, MCP, WebSocket, ecosystem discovery,
settings REPL, and update workflows under the 5-category command protocol.
"""

from __future__ import annotations

import ctypes
import os
import platform
try:
    import psutil
except ImportError:
    psutil = None
import re
import shlex
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

from nova.core.audit import AuditLogger
from nova.core.constants import (
    APP_NAME,
    APP_VERSION,
    ES_CONTINUOUS,
    ES_DISPLAY_REQUIRED,
    ES_SYSTEM_REQUIRED,
    NOVA_APPDATA,
)
from nova.core.parser import CommandCategory, CommandParser, ParsedCommand
from nova.core.permissions import PermissionLevel, PermissionManager
from nova.core.registry import CommandContext, CommandDefinition, CommandRegistry
from nova.core.router import CommandRouter
from nova.discovery.ecosystem import ComponentStatus, EcosystemDiscovery
from nova.settings.interactive import InteractiveSettingsREPL
from nova.settings.manager import SettingsManager
from nova.updates.manager import UpdateManager
from nova.cli.ui import TerminalUI

# Prompt Toolkit integration
HAS_PROMPT_TOOLKIT = False
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.styles import Style as PtStyle
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    pass


class NovaApp:
    """The central Nova Windows Tools application."""

    def __init__(self, low_resource: bool = False):
        self.supported = os.name == "nt"
        self.enabled = False
        self.keep_display_on = False
        self.session_start_time = None
        self.total_awake_seconds = 0
        self.completed_sessions = 0

        # UI & Logging
        self.ui = TerminalUI(low_resource=low_resource)
        self.audit_logger = AuditLogger()
        self.permission_manager = PermissionManager(
            audit_logger=self.audit_logger,
            confirm_callback=self._prompt_confirmation,
        )

        # Core Subsystems
        self.settings_manager = SettingsManager()
        self.discovery = EcosystemDiscovery()
        self.update_manager = UpdateManager(audit_logger=self.audit_logger)

        # Interactive Settings REPL
        self.settings_repl = InteractiveSettingsREPL(
            settings_manager=self.settings_manager,
            discovery=self.discovery,
            print_func=self.ui.print,
            confirm_func=self._prompt_choice,
        )

        # Legacy & Tool integrations (Lazy loaded or linked)
        self._init_legacy_managers()

        # Command Registry & Router
        self.registry = CommandRegistry()
        self.router = CommandRouter(
            registry=self.registry,
            permission_manager=self.permission_manager,
            audit_logger=self.audit_logger,
        )
        self._register_all_commands()

        # Windows Kernel32 Power API
        self.set_execution_state = None
        if self.supported:
            try:
                self.set_execution_state = ctypes.WinDLL("kernel32").SetThreadExecutionState
                self.set_execution_state.argtypes = [wintypes.DWORD]
                self.set_execution_state.restype = wintypes.DWORD
            except Exception:
                self.set_execution_state = None

        # Interactive input prompt session
        self.prompt_session = None
        self._init_prompt_session()

    def _init_legacy_managers(self) -> None:
        """Initialize MCP, WebSocket, and Recorder subsystems."""
        try:
            import easy_windows_tools as legacy
            self.mcp_manager = legacy.MCPManager(console=self.ui.console)
            self.websocket_manager = legacy.LocalWebSocketManager()
            self.recorder_cls = legacy.ScreenRecorder
            self.discovery.mcp_manager = self.mcp_manager
        except Exception:
            self.mcp_manager = None
            self.websocket_manager = None
            self.recorder_cls = None

    def _init_prompt_session(self) -> None:
        """Initialize PromptToolkit session with autocomplete for all 5 categories."""
        if HAS_PROMPT_TOOLKIT and sys.stdin.isatty():
            try:
                completions = [
                    # Normal Commands (Space)
                    " help", " version", " status", " clear", " apps", " exit",
                    " start", " start 15dk", " start 30dk", " start 1saat",
                    " stop", " display on", " display off", " pomodoro", " meeting",
                    " record", " studio", " license",
                    # Important Commands (/)
                    "/system", "/diagnostics", "/processes", "/mcp", "/mcp list",
                    "/mcp create", "/ecosystem", "/security", "/update",
                    "/start", "/stop", "/record", "/studio", "/status", "/clear", "/exit",
                    # Settings Commands (>)
                    ">", "> apps", "> ai", "> mcp", "> development", "> system",
                    "> updates", "> network", "> security",
                    # Settings Exit (<)
                    "<",
                    # Update Commands (#)
                    "#", "# check", "# preview", "# download", "# install",
                    "# full", "# history", "# rollback",
                ]
                self.completer = WordCompleter(completions, ignore_case=True, match_middle=True)
                self.pt_style = PtStyle.from_dict({
                    "prompt": "#E07A5F bold",
                    "symbol": "#38BDF8",
                })
                self.prompt_session = PromptSession(
                    history=InMemoryHistory(),
                    completer=self.completer,
                    style=self.pt_style,
                )
            except Exception:
                self.prompt_session = None

    def _prompt_confirmation(self, prompt: str) -> bool:
        """Prompt user for confirmation."""
        try:
            res = input(f"{prompt} [E/h]: ").strip().lower()
            return res in ("e", "evet", "y", "yes", "")
        except (EOFError, KeyboardInterrupt):
            return False

    def _prompt_choice(self, prompt: str) -> str:
        """Prompt user for multiple-choice option."""
        try:
            return input(f"{prompt}\nSeçiminiz [E/H/D]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "d"

    # ==========================================
    # POWER AND DISPLAY CONTROL METHODS
    # ==========================================
    def _set_awake(self, keep_system: bool, keep_display: bool) -> bool:
        if not self.supported or not self.set_execution_state:
            return False
        flags = ES_CONTINUOUS
        if keep_system:
            flags |= ES_SYSTEM_REQUIRED
        if keep_display:
            flags |= ES_DISPLAY_REQUIRED
        prev = self.set_execution_state(flags)
        return prev != 0

    def set_enabled(self, enabled: bool) -> bool:
        self.enabled = enabled
        if enabled:
            if not self.session_start_time:
                self.session_start_time = time.time()
            success = self._set_awake(True, self.keep_display_on)
            if success:
                self.ui.print_success("Sürekli Uyanık Modu ETKİNLEŞTİRİLDİ.")
            return success
        else:
            if self.session_start_time:
                self.total_awake_seconds += int(time.time() - self.session_start_time)
                self.session_start_time = None
                self.completed_sessions += 1
            success = self._set_awake(False, False)
            self.ui.print_warning("Uyanık modu DURDURULDU. Normal güç planına dönüldü.")
            return success

    def set_display(self, on: bool) -> bool:
        self.keep_display_on = on
        if self.enabled:
            return self._set_awake(True, on)
        return True

    def start_timed_session(self, seconds: int, title: str = "Süreli Oturum") -> None:
        """Start a timed keep-awake session with progress."""
        if not self.set_enabled(True):
            self.ui.print_error("Güç durumu ayarlanamadı.")
            return

        self.ui.print(f"\n[bold green]✦ {title} Başlatıldı[/] (Süre: {seconds // 60} dk {seconds % 60} sn)")
        self.ui.print("[dim]İptal etmek için Ctrl+C tuşlarına basın.[/dim]\n")

        start = time.time()
        try:
            while time.time() - start < seconds:
                elapsed = int(time.time() - start)
                remaining = seconds - elapsed
                pct = int((elapsed / seconds) * 100)
                sys.stdout.write(f"\r  Kalan Süre: {remaining // 60:02d}:{remaining % 60:02d}  [%{pct:02d}] ")
                sys.stdout.flush()
                time.sleep(1.0)
            sys.stdout.write("\n")
            self.ui.print_success(f"✓ {title} başarıyla tamamlandı.")
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            self.ui.print_warning(f"Oturum kullanıcı tarafından durduruldu.")
        finally:
            self.set_enabled(False)

    @staticmethod
    def parse_duration(text: str) -> int | None:
        """Parse natural duration strings like 30dk, 1h, 45sn."""
        match = re.fullmatch(r"(\d+)\s*(dk|dakika|min|saat|h|hour|sn|saniye|s)?", text.strip(), flags=re.IGNORECASE)
        if not match:
            return None
        amount = int(match.group(1))
        unit = (match.group(2) or "dk").lower()
        if unit in ("saat", "h", "hour"):
            return amount * 3600
        if unit in ("sn", "saniye", "s"):
            return amount
        return amount * 60

    # ==========================================
    # COMMAND REGISTRATIONS
    # ==========================================
    def _register_all_commands(self) -> None:
        """Register handlers for all 5 categories."""
        # ----------------------------------------
        # CATEGORY A: NORMAL COMMANDS (Space ' ')
        # ----------------------------------------
        self.registry.register(CommandDefinition(
            name="help",
            category=CommandCategory.NORMAL,
            handler=lambda ctx: self.ui.show_help_menu(),
            description="Tüm komut kategorilerini ve kullanım rehberini açar.",
            aliases=["yardım", "yardim", "?"],
        ))

        self.registry.register(CommandDefinition(
            name="version",
            category=CommandCategory.NORMAL,
            handler=self._cmd_version,
            description="Nova Windows Tools sürüm ve platform bilgilerini gösterir.",
            aliases=["sürüm", "surum"],
        ))

        self.registry.register(CommandDefinition(
            name="status",
            category=CommandCategory.NORMAL,
            handler=self._cmd_status,
            description="Geçerli uyanıklık ve sistem durumunu gösterir.",
            aliases=["durum"],
        ))

        self.registry.register(CommandDefinition(
            name="clear",
            category=CommandCategory.NORMAL,
            handler=lambda ctx: (self.ui.clear(), self.ui.print_banner()),
            description="Terminal ekranını temizler.",
            aliases=["cls", "temizle"],
        ))

        self.registry.register(CommandDefinition(
            name="apps",
            category=CommandCategory.NORMAL,
            handler=self._cmd_apps,
            description="Bilgisayarda algılanan uygulamaları listeler.",
            aliases=["uygulamalar"],
        ))

        self.registry.register(CommandDefinition(
            name="exit",
            category=CommandCategory.NORMAL,
            handler=lambda ctx: ctx.data.update({"exit": True}),
            description="Nova Windows Tools'dan güvenli şekilde çıkar.",
            aliases=["quit", "çıkış", "cikis", "q"],
        ))

        self.registry.register(CommandDefinition(
            name="start",
            category=CommandCategory.NORMAL,
            handler=self._cmd_start,
            description="Uyanık modunu başlatır (örn: ' start 30dk').",
            aliases=["başlat", "baslat", "on"],
        ))

        self.registry.register(CommandDefinition(
            name="stop",
            category=CommandCategory.NORMAL,
            handler=lambda ctx: self.set_enabled(False),
            description="Uyanık modunu sonlandırır.",
            aliases=["durdur", "off"],
        ))

        self.registry.register(CommandDefinition(
            name="display",
            category=CommandCategory.NORMAL,
            handler=self._cmd_display,
            description="Ekran kararmasını önler veya serbest bırakır (örn: ' display on').",
            aliases=["ekran"],
        ))

        self.registry.register(CommandDefinition(
            name="pomodoro",
            category=CommandCategory.NORMAL,
            handler=lambda ctx: self.start_timed_session(25 * 60, "🍅 Pomodoro Odak Oturumu (25 dk)"),
            description="25 dakikalık odak oturumu başlatır.",
            aliases=["pomo"],
        ))

        self.registry.register(CommandDefinition(
            name="meeting",
            category=CommandCategory.NORMAL,
            handler=lambda ctx: self.start_timed_session(60 * 60, "📅 Toplantı Oturumu (60 dk)"),
            description="60 dakikalık toplantı oturumu başlatır.",
            aliases=["toplantı", "toplanti"],
        ))

        self.registry.register(CommandDefinition(
            name="record",
            category=CommandCategory.NORMAL,
            handler=self._cmd_record,
            description="Ekran kaydı başlatır.",
            permission_level=PermissionLevel.SENSITIVE,
        ))

        self.registry.register(CommandDefinition(
            name="studio",
            category=CommandCategory.NORMAL,
            handler=self._cmd_studio,
            description="Canlı stüdyo penceresini açar.",
            aliases=["stüdyo", "studyo"],
        ))

        self.registry.register(CommandDefinition(
            name="license",
            category=CommandCategory.NORMAL,
            handler=self._cmd_license,
            description="GNU GPLv3 lisans ve garanti bildirimini gösterir.",
            aliases=["lisans"],
        ))

        # ----------------------------------------
        # CATEGORY B: IMPORTANT COMMANDS (Slash '/')
        # ----------------------------------------
        self.registry.register(CommandDefinition(
            name="system",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_slash_system,
            description="Kapsamlı Windows sistem ve donanım bilgilerini gösterir.",
            permission_level=PermissionLevel.IMPORTANT,
        ))

        self.registry.register(CommandDefinition(
            name="diagnostics",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_slash_diagnostics,
            description="Sistem API'leri, yetkiler ve paketler için tanılama yapar.",
            permission_level=PermissionLevel.IMPORTANT,
        ))

        self.registry.register(CommandDefinition(
            name="processes",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_slash_processes,
            description="Çalışan süreçleri görüntüler ve arar.",
            permission_level=PermissionLevel.IMPORTANT,
        ))

        self.registry.register(CommandDefinition(
            name="mcp",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_slash_mcp,
            description="MCP sunucularını yönetir (list, create, start, stop).",
            permission_level=PermissionLevel.SENSITIVE,
        ))

        self.registry.register(CommandDefinition(
            name="ecosystem",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_slash_ecosystem,
            description="Nova ekosistemi bileşenlerinin durumunu gösterir.",
            permission_level=PermissionLevel.IMPORTANT,
        ))

        self.registry.register(CommandDefinition(
            name="security",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_slash_security,
            description="Güvenlik izinlerini, UAC durumunu ve denetim günlüğünü gösterir.",
            permission_level=PermissionLevel.IMPORTANT,
        ))

        self.registry.register(CommandDefinition(
            name="update",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_slash_update,
            description="Güncelleme merkezini açar veya kontrol eder.",
            permission_level=PermissionLevel.IMPORTANT,
        ))

        # Convenience slash aliases
        self.registry.register(CommandDefinition(
            name="help",
            category=CommandCategory.IMPORTANT,
            handler=lambda ctx: self.ui.show_help_menu(),
            description="Yardım rehberini açar.",
        ))
        self.registry.register(CommandDefinition(
            name="status",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_status,
            description="Uyanıklık durumunu gösterir.",
        ))
        self.registry.register(CommandDefinition(
            name="clear",
            category=CommandCategory.IMPORTANT,
            handler=lambda ctx: (self.ui.clear(), self.ui.print_banner()),
            description="Ekranı temizler.",
        ))
        self.registry.register(CommandDefinition(
            name="exit",
            category=CommandCategory.IMPORTANT,
            handler=lambda ctx: ctx.data.update({"exit": True}),
            description="Programdan çıkar.",
        ))
        self.registry.register(CommandDefinition(
            name="start",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_start,
            description="Uyanıklığı başlatır.",
        ))
        self.registry.register(CommandDefinition(
            name="stop",
            category=CommandCategory.IMPORTANT,
            handler=lambda ctx: self.set_enabled(False),
            description="Uyanıklığı durdurur.",
        ))
        self.registry.register(CommandDefinition(
            name="studio",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_studio,
            description="Stüdyoyu açar.",
        ))
        self.registry.register(CommandDefinition(
            name="record",
            category=CommandCategory.IMPORTANT,
            handler=self._cmd_record,
            description="Ekran kaydeder.",
            permission_level=PermissionLevel.SENSITIVE,
        ))

        # ----------------------------------------
        # CATEGORY E: UPDATE COMMANDS (Hash '#')
        # ----------------------------------------
        self.registry.register(CommandDefinition(
            name="",  # Bare '#'
            category=CommandCategory.UPDATE,
            handler=self._cmd_update_center,
            description="Tam güncelleme merkezini açar.",
        ))
        self.registry.register(CommandDefinition(
            name="check",
            category=CommandCategory.UPDATE,
            handler=self._cmd_update_check,
            description="Güncellemeleri kontrol eder.",
        ))
        self.registry.register(CommandDefinition(
            name="preview",
            category=CommandCategory.UPDATE,
            handler=lambda ctx: self.ui.print(self.update_manager.preview()),
            description="Güncelleme değişikliklerini önizler.",
        ))
        self.registry.register(CommandDefinition(
            name="download",
            category=CommandCategory.UPDATE,
            handler=self._cmd_update_download,
            description="Onaylanan güncellemeyi indirir ve doğrular.",
            permission_level=PermissionLevel.SENSITIVE,
        ))
        self.registry.register(CommandDefinition(
            name="install",
            category=CommandCategory.UPDATE,
            handler=self._cmd_update_install,
            description="İndirilmiş güncellemeyi yedek alarak kurar.",
            permission_level=PermissionLevel.CRITICAL,
        ))
        self.registry.register(CommandDefinition(
            name="full",
            category=CommandCategory.UPDATE,
            handler=self._cmd_update_full,
            description="Tam güncelleme iş akışını baştan sona yürütür.",
            permission_level=PermissionLevel.CRITICAL,
        ))
        self.registry.register(CommandDefinition(
            name="history",
            category=CommandCategory.UPDATE,
            handler=self._cmd_update_history,
            description="Önceki güncelleme geçmişini gösterir.",
        ))
        self.registry.register(CommandDefinition(
            name="rollback",
            category=CommandCategory.UPDATE,
            handler=self._cmd_update_rollback,
            description="Önceki sürüme geri döner.",
            permission_level=PermissionLevel.CRITICAL,
        ))

    # ==========================================
    # HANDLER IMPLEMENTATIONS
    # ==========================================
    def _cmd_version(self, ctx: CommandContext) -> None:
        self.ui.print(f"\n[bold cyan]✦ {APP_NAME}[/] [dim]v{APP_VERSION}[/]")
        self.ui.print(f"  • Platform: {platform.system()} {platform.release()} ({platform.machine()})")
        self.ui.print(f"  • Python: {platform.python_version()} ({sys.executable})")
        self.ui.print(f"  • AppData: {NOVA_APPDATA}")
        self.ui.print(f"  • Yetki: {'Yönetici (Administrator)' if self.permission_manager.is_admin() else 'Standart Kullanıcı'}\n")

    def _cmd_status(self, ctx: CommandContext) -> None:
        status_str = "[bold green]UYANIK (Aktif)[/]" if self.enabled else "[dim]KAPALI (Normal)[/]"
        display_str = "[bold green]KORUMALI (Açık)[/]" if self.keep_display_on else "[dim]SERBEST (Uyuyabilir)[/]"
        current_time = int(time.time() - self.session_start_time) if self.session_start_time else 0
        total_mins = (self.total_awake_seconds + current_time) // 60

        self.ui.print(f"\n[Sistem ve Güç Durumu]")
        self.ui.print(f"  • Güç Koruma: {status_str}")
        self.ui.print(f"  • Ekran Durumu: {display_str}")
        self.ui.print(f"  • Tamamlanan Oturum: {self.completed_sessions}")
        self.ui.print(f"  • Toplam Korunan Süre: {total_mins} dakika\n")

    def _cmd_apps(self, ctx: CommandContext) -> None:
        self.ui.print("\n[Algılanan Uygulamalar ve Paket Yöneticileri]")
        components = self.discovery.discover_all(force_refresh=False)
        apps = [c for c in components if c.category in ("apps", "package_manager", "development")]
        for a in apps:
            tag = "[bold green]KURULU[/]" if a.status == ComponentStatus.INSTALLED or a.status == ComponentStatus.ACTIVE else "[dim red]YOK[/]"
            self.ui.print(f"  • {tag:<20} {a.name:<32} [dim]{a.version or ''}[/]")
            if a.path:
                self.ui.print(f"    [dim]Yol: {a.path}[/]")
        self.ui.print("")

    def _cmd_start(self, ctx: CommandContext) -> None:
        parsed = ctx.parsed
        duration_arg = parsed.subcommand or (parsed.args[0] if parsed.args else None)
        if duration_arg:
            secs = self.parse_duration(duration_arg)
            if secs is not None:
                self.start_timed_session(secs, f"Süreli Oturum ({duration_arg})")
                return
            self.ui.print_warning(f"Geçersiz süre biçimi: '{duration_arg}'. Örnekler: 30dk, 1saat, 45sn")
            return
        self.set_enabled(True)

    def _cmd_display(self, ctx: CommandContext) -> None:
        parsed = ctx.parsed
        sub = (parsed.subcommand or (parsed.args[0] if parsed.args else "")).lower()
        if sub in ("on", "açık", "acik", "1"):
            self.set_display(True)
            self.ui.print_success("Ekran kararması engellendi.")
        elif sub in ("off", "kapalı", "kapali", "0"):
            self.set_display(False)
            self.ui.print_warning("Ekran kararmasına izin verildi.")
        else:
            self.ui.print("Kullanım: ' display on' veya ' display off'")

    def _cmd_record(self, ctx: CommandContext) -> None:
        if not self.recorder_cls:
            self.ui.print_error("Ekran kayıt modülü yüklenemedi.")
            return
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        except ImportError:
            ffmpeg = None
        if not ffmpeg:
            self.ui.print_error("FFmpeg bulunamadı. Ekran kaydı için FFmpeg gereklidir.")
            return

        self.ui.print_success("Ekran kaydedici başlatılıyor... (Durdurmak için Ctrl+C)")
        try:
            recorder = self.recorder_cls()
            recorder.record_screen()
        except Exception as err:
            self.ui.print_error(f"Kayıt hatası: {err}")

    def _cmd_studio(self, ctx: CommandContext) -> None:
        try:
            from studio import open_studio
            if self.recorder_cls:
                open_studio(self.recorder_cls, self.recorder_cls.load_settings())
            else:
                self.ui.print_error("Stüdyo için ScreenRecorder sınıfı bulunamadı.")
        except Exception as err:
            self.ui.print_error(f"Stüdyo açılamadı: {err}")

    def _cmd_license(self, ctx: CommandContext) -> None:
        self.ui.print("\n[bold]GNU General Public License v3.0[/]")
        self.ui.print(
            "Copyright (C) 2026 Robin Güneş\n"
            "This program comes with ABSOLUTELY NO WARRANTY.\n"
            "This is free software under GNU GPL version 3; redistribution is permitted.\n"
            "License details: https://www.gnu.org/licenses/gpl-3.0.html\n"
        )

    # ----------------------------------------
    # IMPORTANT COMMAND HANDLERS (/)
    # ----------------------------------------
    def _cmd_slash_system(self, ctx: CommandContext) -> None:
        self.ui.print("\n[Ayrıntılı Sistem Bilgisi]")
        self.ui.print(f"  • İşletim Sistemi: {platform.system()} {platform.release()} (Build {platform.version()})")
        self.ui.print(f"  • Mimari: {platform.machine()} ({platform.architecture()[0]})")
        self.ui.print(f"  • İşlemci: {platform.processor() or 'Bilinmiyor'}")
        self.ui.print(f"  • Windows API Uyumluluğu: {'Evet (kernel32.dll)' if self.supported else 'Hayır'}")
        self.ui.print(f"  • Yönetici Yetkisi (UAC Elevation): {'Aktif (Administrator)' if self.permission_manager.is_admin() else 'Standart Kullanıcı'}")
        self.ui.print(f"  • Nova Veri Dizini: {NOVA_APPDATA}\n")

    def _cmd_slash_diagnostics(self, ctx: CommandContext) -> None:
        self.ui.print("\n[Nova Sistem Tanılaması]")
        # 1. API check
        api_ok = self.supported and self.set_execution_state is not None
        self.ui.print(f"  [{'green' if api_ok else 'red'}]{'✓' if api_ok else '✕'}[/] Windows Power API (SetThreadExecutionState): {'Başarılı' if api_ok else 'Başarısız'}")

        # 2. AppData write permission
        write_ok = False
        try:
            test_file = NOVA_APPDATA / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            write_ok = True
        except OSError:
            write_ok = False
        self.ui.print(f"  [{'green' if write_ok else 'red'}]{'✓' if write_ok else '✕'}[/] AppData Yazma İzni ({NOVA_APPDATA}): {'Başarılı' if write_ok else 'Başarısız'}")

        # 3. FFmpeg check
        ffmpeg_comp = self.discovery.get_component("ffmpeg")
        ff_ok = ffmpeg_comp and ffmpeg_comp.status == ComponentStatus.INSTALLED
        self.ui.print(f"  [{'green' if ff_ok else 'yellow'}]{'✓' if ff_ok else '⚠'}[/] FFmpeg Medya Kodlayıcı: {'Mevcut' if ff_ok else 'Eksik (Ekran kaydı etkilenebilir)'}")

        # 4. FastMCP SDK
        mcp_comp = self.discovery.get_component("fastmcp")
        mcp_ok = mcp_comp and mcp_comp.status == ComponentStatus.INSTALLED
        self.ui.print(f"  [{'green' if mcp_ok else 'yellow'}]{'✓' if mcp_ok else '⚠'}[/] Model Context Protocol (FastMCP): {'Yüklü' if mcp_ok else 'Yüklü Değil'}\n")

    def _cmd_slash_processes(self, ctx: CommandContext) -> None:
        self.ui.print("\n[Çalışan Süreçler]")
        query = ctx.parsed.subcommand or (ctx.parsed.args[0] if ctx.parsed.args else None)
        try:
            output = subprocess.run(
                ["tasklist"],
                capture_output=True,
                text=True,
                encoding="mbcs",
                errors="replace",
                check=False,
            ).stdout
            lines = output.splitlines()
            if query:
                q_lower = query.lower()
                matches = [l for l in lines if q_lower in l.lower()]
                self.ui.print(f"'{query}' filtresine uyan {len(matches)} süreç:")
                for m in matches[:20]:
                    self.ui.print(f"  {m}")
            else:
                self.ui.print(f"Toplam {len(lines) - 3} çalışan süreç. İlk 15 süreç:")
                for l in lines[3:18]:
                    self.ui.print(f"  {l}")
                self.ui.print("[dim]Arama yapmak için: '/processes <isim>' yazabilirsiniz.[/dim]\n")
        except Exception as err:
            self.ui.print_error(f"Süreç listesi alınamadı: {err}")

    def _cmd_slash_mcp(self, ctx: CommandContext) -> None:
        sub = ctx.parsed.subcommand or "list"
        if not self.mcp_manager:
            self.ui.print_error("MCP Yöneticisi kullanılamıyor.")
            return

        if sub in ("list", "liste"):
            servers = self.mcp_manager.list_servers()
            self.ui.print(f"\n[Kayıtlı MCP Sunucuları] ({len(servers)} sunucu)")
            for s in servers:
                running = self.mcp_manager.is_running(s["id"]) if hasattr(self.mcp_manager, "is_running") else False
                badge = "[bold green]ÇALIŞIYOR[/]" if running else "[dim]DURDU[/]"
                self.ui.print(f"  • {badge:<20} {s['name']} (Port: {s.get('port', 8800)})")
            self.ui.print("")
        elif sub == "create":
            self.mcp_manager.create_interactive()
        elif sub == "settings":
            self.mcp_manager.open_settings_gui()
        elif sub == "start":
            target = ctx.parsed.args[0] if ctx.parsed.args else None
            if not target:
                self.ui.print("Kullanım: /mcp start <sunucu_adı>")
            else:
                self.ui.print(self.mcp_manager.start_mcp_server(target))
        elif sub == "stop":
            target = ctx.parsed.args[0] if ctx.parsed.args else None
            if not target:
                self.ui.print("Kullanım: /mcp stop <sunucu_adı>")
            else:
                self.ui.print(self.mcp_manager.stop_mcp_server(target))
        else:
            self.ui.print("Kullanım: /mcp [list | create | start <ad> | stop <ad> | settings]")

    def _cmd_slash_ecosystem(self, ctx: CommandContext) -> None:
        self.ui.print("\n[Nova Ekosistem Genel Durumu]")
        components = self.discovery.discover_all(force_refresh=True)
        categories = {}
        for c in components:
            categories.setdefault(c.category, []).append(c)

        for cat, items in categories.items():
            self.ui.print(f"\n--- {cat.upper()} ---")
            for item in items:
                status_color = "green" if item.status.value in ("installed", "active") else "yellow" if item.status.value == "disabled" else "red"
                self.ui.print(f"  [{status_color}]{item.status.value.upper():<12}[/] {item.name:<32} [dim]{item.version or ''}[/]")
        self.ui.print("")

    def _cmd_slash_security(self, ctx: CommandContext) -> None:
        self.ui.print("\n[Güvenlik ve Yetkilendirme Durumu]")
        is_admin = self.permission_manager.is_admin()
        self.ui.print(f"  • Yönetici Yetkisi: {'AKTİF (Administrator)' if is_admin else 'STANDART (Kısıtlı)'}")
        self.ui.print(f"  • Denetim Günlüğü: {self.audit_logger.log_file}")
        recent = self.audit_logger.get_recent(limit=5)
        self.ui.print("\n  Son 5 Güvenlik Olayı:")
        for r in recent:
            self.ui.print(f"    [{r.get('status')}] {r.get('timestamp')} - {r.get('category')}:{r.get('action')}")
        self.ui.print("")

    def _cmd_slash_update(self, ctx: CommandContext) -> None:
        self._cmd_update_center(ctx)

    # ----------------------------------------
    # UPDATE COMMAND HANDLERS (#)
    # ----------------------------------------
    def _cmd_update_center(self, ctx: CommandContext) -> None:
        self.ui.print("\n" + "=" * 60)
        self.ui.print("✦ NOVA TAM GÜNCELLEME MERKEZİ")
        self.ui.print("=" * 60)
        self.ui.print("Komutlar:")
        self.ui.print("  # check     : Güncellemeleri kontrol et")
        self.ui.print("  # preview   : Değişiklikleri ve changelog'u önizle")
        self.ui.print("  # download  : Paketleri indir ve SHA256 doğrula")
        self.ui.print("  # install   : Doğrulanmış paketleri yedek alarak kur")
        self.ui.print("  # full      : Otomatik tam güncelleme akışını çalıştır")
        self.ui.print("  # history   : Güncelleme geçmişini listele")
        self.ui.print("  # rollback  : Önceki sürüme geri dön")
        self.ui.print("=" * 60 + "\n")

    def _cmd_update_check(self, ctx: CommandContext) -> None:
        self.ui.print("\nGüncellemeler denetleniyor...")
        updates = self.update_manager.check_updates()
        has_any = any(u.has_update for u in updates)
        if not has_any:
            self.ui.print_success("Tüm Nova bileşenleri güncel.")
        else:
            self.ui.print_warning(f"Kullanılabilir güncellemeler bulundu:")
            for u in updates:
                if u.has_update:
                    self.ui.print(f"  • {u.name}: {u.current_version} -> [bold green]{u.latest_version}[/]")
            self.ui.print("[dim]Önizlemek için '# preview', indirmek için '# download' yazabilirsiniz.[/dim]\n")

    def _cmd_update_download(self, ctx: CommandContext) -> None:
        updates = self.update_manager.check_updates()
        target = ctx.parsed.subcommand or (ctx.parsed.args[0] if ctx.parsed.args else (updates[0].component_id if updates else None))
        if not target:
            self.ui.print_error("İndirilecek bileşen belirtilmedi.")
            return

        def _on_progress(pct: float, msg: str):
            self.ui.print(f"  [dim]{msg}[/]")

        ok, msg = self.update_manager.download(target, progress_callback=_on_progress)
        if ok:
            self.ui.print_success(msg)
            self.ui.print("[dim]Kurmak için: '# install' yazın.[/dim]")
        else:
            self.ui.print_error(msg)

    def _cmd_update_install(self, ctx: CommandContext) -> None:
        updates = self.update_manager.check_updates()
        target = ctx.parsed.subcommand or (ctx.parsed.args[0] if ctx.parsed.args else (updates[0].component_id if updates else None))
        if not target:
            self.ui.print_error("Kurulacak bileşen bulunamadı.")
            return

        ok, msg = self.update_manager.install(target, confirm_callback=self._prompt_confirmation)
        if ok:
            self.ui.print_success(msg)
        else:
            self.ui.print_error(msg)

    def _cmd_update_full(self, ctx: CommandContext) -> None:
        self.ui.print("\n[Tam Güncelleme İş Akışı Başlatılıyor]")
        ok, msg = self.update_manager.run_full_workflow(
            confirm_callback=self._prompt_confirmation,
            progress_callback=lambda p, m: self.ui.print(f"  [{int(p):02d}%] {m}"),
        )
        if ok:
            self.ui.print_success(msg)
        else:
            self.ui.print_error(msg)

    def _cmd_update_history(self, ctx: CommandContext) -> None:
        history = self.update_manager.get_history()
        self.ui.print(f"\n[Güncelleme Geçmişi] ({len(history)} kayıt)")
        for h in history:
            self.ui.print(f"  • [{h.get('status')}] {h.get('timestamp')} - {h.get('action')} ({h.get('component_id')})")
        self.ui.print("")

    def _cmd_update_rollback(self, ctx: CommandContext) -> None:
        ok, msg = self.update_manager.rollback()
        if ok:
            self.ui.print_success(msg)
        else:
            self.ui.print_error(msg)

    # ==========================================
    # INPUT AND RUN LOOP
    # ==========================================
    def get_raw_user_input(self) -> str:
        """Read user input strictly preserving leading whitespace."""
        prompt_text = self.settings_repl.get_prompt_text() if self.settings_repl.is_active else "\n╭─ ⚡ nova-windows-tools\n╰─ ❯ "

        if self.prompt_session:
            try:
                # prompt_toolkit prompt (DO NOT strip!)
                return self.prompt_session.prompt(prompt_text)
            except Exception:
                pass

        # Standard console input fallback (DO NOT strip!)
        try:
            return input(prompt_text)
        except (EOFError, KeyboardInterrupt):
            return ""

    def run(self) -> None:
        """Main execution REPL."""
        self.ui.clear()
        self.ui.print_banner()

        if not self.supported:
            self.ui.print_warning(
                "Uyku ve ekran güç kontrolleri Windows gerektirir. "
                "Ecosystem, MCP ve ayarlar merkezi kullanılabilir."
            )

        context_data: dict[str, Any] = {}

        while True:
            try:
                raw_input = self.get_raw_user_input()
            except (EOFError, KeyboardInterrupt):
                self.ui.print()
                break

            # If user pressed enter on empty line in main mode
            if raw_input == "" and not self.settings_repl.is_active:
                continue

            # 1. If currently in Interactive Settings Mode
            if self.settings_repl.is_active:
                still_active = self.settings_repl.handle_input(raw_input)
                if not still_active:
                    # Exited settings mode
                    continue
                continue

            # 2. Main Terminal Mode:
            # Check for Settings Open Command ('>')
            if raw_input.startswith(">"):
                target = raw_input[1:].strip()
                self.settings_repl.enter(target if target else None)
                continue

            # Check for Settings Exit Command ('<') outside settings
            if raw_input.startswith("<"):
                self.ui.print_warning(
                    "Ayarlar merkezinde değilsiniz. Nova Ayarlar Merkezi'ni açmak için '>' yazabilirsiniz."
                )
                continue

            # 3. Parse input through strict 5-category parser
            parsed = CommandParser.parse(raw_input)

            context = CommandContext(
                parsed=parsed,
                app=self,
                print_output=self.ui.print,
                print_error=self.ui.print_error,
                confirm=self._prompt_confirmation,
                data=context_data,
            )

            # Route and execute
            self.router.route(parsed, context)

            if context_data.get("exit"):
                break

        # Cleanup on exit
        self._shutdown()

    def _shutdown(self) -> None:
        """Safely restore power states and close background services."""
        if self.websocket_manager:
            try:
                self.websocket_manager.stop_all()
            except Exception:
                pass

        if self.supported and self.set_execution_state:
            try:
                self.set_execution_state(ES_CONTINUOUS)
            except Exception:
                pass

        if self.session_start_time and self.enabled:
            self.total_awake_seconds += int(time.time() - self.session_start_time)

        total_mins = self.total_awake_seconds // 60
        self.ui.print_success("Güç ayarları başarıyla normale döndürüldü.")
        self.ui.print(f"• Toplam Korunan Süre: {total_mins} dakika.")
        self.ui.print(f"✦ {APP_NAME} güvenle kapatıldı.\n")
