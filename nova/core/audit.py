# -*- coding: utf-8 -*-
"""Nova Windows Tools - Audit Logger.

Provides persistent, thread-safe audit logging for all critical, sensitive,
and system-modifying operations.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nova.core.constants import AUDIT_LOG_FILE


class AuditLogger:
    """Thread-safe persistent audit log recorder."""

    MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB rotation limit

    def __init__(self, log_file: Path | str | None = None):
        self.log_file = Path(log_file) if log_file else AUDIT_LOG_FILE
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(
        self,
        category: str,
        action: str,
        status: str = "SUCCESS",
        details: dict[str, Any] | str | None = None,
        actor: str = "local_user",
    ) -> None:
        """Record an audit event."""
        now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
        
        # Sanitize sensitive fields if details is dict
        clean_details = details
        if isinstance(details, dict):
            clean_details = dict(details)
            for sensitive_key in ("pin", "password", "token", "secret", "api_key", "pin_hash"):
                if sensitive_key in clean_details:
                    clean_details[sensitive_key] = "***MASKED***"

        entry = {
            "timestamp": now_utc,
            "category": str(category),
            "action": str(action),
            "status": str(status),
            "actor": actor,
            "details": clean_details,
        }

        line = json.dumps(entry, ensure_ascii=False) + "\n"

        with self._lock:
            self._rotate_if_needed()
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                pass

    def _rotate_if_needed(self) -> None:
        """Rotate log file if larger than MAX_LOG_BYTES."""
        try:
            if self.log_file.is_file() and self.log_file.stat().st_size >= self.MAX_LOG_BYTES:
                backup_path = self.log_file.with_suffix(".log.1")
                if backup_path.exists():
                    backup_path.unlink()
                self.log_file.rename(backup_path)
        except OSError:
            pass

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent audit events in reverse chronological order."""
        if not self.log_file.is_file():
            return []
        entries: list[dict[str, Any]] = []
        with self._lock:
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                        if len(entries) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue
            except OSError:
                return []
        return entries
