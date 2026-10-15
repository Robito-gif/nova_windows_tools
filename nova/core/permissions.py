# -*- coding: utf-8 -*-
"""Nova Windows Tools - Permission and Authorization Management."""

from __future__ import annotations

import ctypes
import enum
import os
from typing import Callable

from nova.core.audit import AuditLogger


class PermissionLevel(enum.IntEnum):
    """Authorization tiers for operations."""

    NORMAL = 0      # Read-only, status, help, harmless
    IMPORTANT = 1   # System queries, diagnostics, listing processes
    SENSITIVE = 2   # Starting/stopping local services, recording, changing settings
    CRITICAL = 3    # Killing processes, installing updates, restoring backups, factory reset
    ELEVATED = 4    # Requires Windows UAC / Administrator rights


class PermissionManager:
    """Controls permissions and confirmation gates for commands."""

    def __init__(
        self,
        audit_logger: AuditLogger | None = None,
        confirm_callback: Callable[[str], bool] | None = None,
    ):
        self.audit_logger = audit_logger or AuditLogger()
        self.confirm_callback = confirm_callback or self._default_console_confirm

    @staticmethod
    def is_admin() -> bool:
        """Check if the current process is running with administrative privileges."""
        if os.name != "nt":
            return os.geteuid() == 0 if hasattr(os, "geteuid") else False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def _default_console_confirm(prompt: str) -> bool:
        """Default interactive confirmation via standard input."""
        try:
            response = input(f"{prompt} [E/h]: ").strip().lower()
            return response in {"e", "evet", "y", "yes", ""}
        except (EOFError, KeyboardInterrupt):
            return False

    def check(
        self,
        command_name: str,
        required_level: PermissionLevel,
        description: str = "",
        actor: str = "local_user",
    ) -> tuple[bool, str | None]:
        """Verify whether an operation is authorized to execute."""
        # 1. Elevated operations check
        if required_level >= PermissionLevel.ELEVATED:
            if not self.is_admin():
                reason = (
                    f"'{command_name}' komutu Windows Yönetici (Administrator) yetkisi gerektirir. "
                    f"Lütfen terminali 'Yönetici Olarak Çalıştır' seçeneğiyle açın."
                )
                self.audit_logger.log(
                    category="permission",
                    action=command_name,
                    status="DENIED_ELEVATION",
                    details={"required_level": required_level.name, "reason": reason},
                    actor=actor,
                )
                return False, reason

        # 2. Critical & Sensitive operations confirmation gate
        if required_level >= PermissionLevel.CRITICAL:
            prompt_text = (
                f"\n[DİKKAT - KRİTİK İŞLEM]\n"
                f"Komut: '{command_name}'\n"
                f"Açıklama: {description or 'Bu işlem sistemde önemli değişiklik yapacaktır.'}\n"
                f"Onaylıyor musunuz?"
            )
            confirmed = self.confirm_callback(prompt_text)
            if not confirmed:
                reason = "İşlem kullanıcı tarafından onaylanmadı ve güvenle iptal edildi."
                self.audit_logger.log(
                    category="permission",
                    action=command_name,
                    status="CANCELLED_BY_USER",
                    details={"required_level": required_level.name},
                    actor=actor,
                )
                return False, reason

        self.audit_logger.log(
            category="permission",
            action=command_name,
            status="GRANTED",
            details={"level": required_level.name},
            actor=actor,
        )
        return True, None
