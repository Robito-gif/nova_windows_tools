# -*- coding: utf-8 -*-
"""Nova Windows Tools - Update Manifest and Repository Sources.

Defines approved Nova ecosystem distribution sources and release metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nova.core.constants import APP_VERSION


@dataclass
class ComponentRelease:
    """Release metadata for an approved ecosystem component."""

    component_id: str
    name: str
    version: str
    channel: str
    download_url: str
    sha256: str
    size_bytes: int
    changelog: str
    min_python: str = ">=3.10"
    dependencies: list[str] = field(default_factory=list)


# Official Nova Distribution Manifest (Built-in baseline / fallback)
DEFAULT_APPROVED_MANIFEST: dict[str, Any] = {
    "repository": "https://github.com/Robito-gif/nova-windows-tools",
    "updated_at": "2026-10-15T00:00:00Z",
    "channels": {
        "stable": {
            "nova-windows-tools": {
                "name": "Nova Windows Tools (Çekirdek Sistem)",
                "version": APP_VERSION,
                "download_url": "https://raw.githubusercontent.com/Robito-gif/nova-windows-tools/main/dist/nova_windows_tools.zip",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "size_bytes": 1024 * 250,
                "changelog": (
                    "• Yeni 5 kategorili komut sistemi mimarisi (Normal, Önemli, Ayarlar, Çıkış, Güncelleme).\n"
                    "• Çok ayrıntılı ve hiyerarşik Nova Ayarlar Merkezi (>).\n"
                    "• Tam otomatik sistem keşfi ve durum yönetimi.\n"
                    "• Güvenli güncelleme (#) ve otomatik geri alma (rollback) sistemi.\n"
                    "• Performans ve düşük donanımlı PC optimizasyonları."
                ),
            },
            "studio": {
                "name": "Nova Live Studio",
                "version": "1.2.0",
                "download_url": "https://raw.githubusercontent.com/Robito-gif/nova-windows-tools/main/dist/studio.zip",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "size_bytes": 1024 * 80,
                "changelog": "• Gelişmiş sahne kompozisyonu ve şeffaflık filtreleri.",
            },
        },
        "beta": {},
        "nightly": {},
    },
}
