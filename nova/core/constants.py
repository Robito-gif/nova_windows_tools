# -*- coding: utf-8 -*-
"""Nova Windows Tools constants and configuration paths."""

import os
from pathlib import Path

APP_NAME = "Nova Windows Tools"
APP_CODE = "NWT"
APP_VERSION = "2.4.0"

# AppData Directories
BASE_APPDATA = Path(os.environ.get("APPDATA", Path.home() / ".config"))
NOVA_APPDATA = BASE_APPDATA / "NovaWindowsTools"
LEGACY_APPDATA = BASE_APPDATA / "EasyWindowsTools"

# Ensure Nova AppData directory exists
NOVA_APPDATA.mkdir(parents=True, exist_ok=True)

# Configuration & Data files
SETTINGS_FILE = NOVA_APPDATA / "settings.json"
SETTINGS_BACKUP_FILE = NOVA_APPDATA / "settings.backup.json"
AUDIT_LOG_FILE = NOVA_APPDATA / "audit.log"
UPDATE_DIR = NOVA_APPDATA / "updates"
UPDATE_STAGING_DIR = UPDATE_DIR / "staging"
UPDATE_BACKUP_DIR = UPDATE_DIR / "backups"
UPDATE_HISTORY_FILE = UPDATE_DIR / "history.json"
DEFAULT_WEBSOCKET_DB = NOVA_APPDATA / "websocket_services.sqlite3"
DEFAULT_MCP_DB = NOVA_APPDATA / "mcps.sqlite3"

# Windows API Execution State Flags
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

# Claude Code / Nova Color Palette
CLAUDE_THEME = {
    "primary": "#E07A5F",      # Nova Terracotta / Amber
    "secondary": "#818CF8",    # Nova Indigo / Violet
    "accent": "#38BDF8",       # Cyber Sky Blue
    "success": "#34D399",      # Emerald Green
    "warning": "#FBBF24",      # Amber Yellow
    "error": "#F87171",        # Crimson Red
    "dim": "#64748B",          # Slate Gray
    "bright": "#F8FAFC",       # Cloud White
    "bg_subtle": "#1E293B",    # Dark Slate
}
