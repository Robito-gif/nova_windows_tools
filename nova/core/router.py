# -*- coding: utf-8 -*-
"""Nova Windows Tools - Command Router.

Dispatches parsed commands to registered handlers while strictly enforcing
category isolation, permission verification, and audit logging.
"""

from __future__ import annotations

from typing import Any

from nova.core.audit import AuditLogger
from nova.core.parser import CommandCategory, ParsedCommand
from nova.core.permissions import PermissionManager
from nova.core.registry import CommandContext, CommandRegistry


class CommandRouter:
    """Routes commands to registered handlers with validation and logging."""

    def __init__(
        self,
        registry: CommandRegistry,
        permission_manager: PermissionManager,
        audit_logger: AuditLogger | None = None,
    ):
        self.registry = registry
        self.permission_manager = permission_manager
        self.audit_logger = audit_logger or AuditLogger()

    def route(self, parsed: ParsedCommand, context: CommandContext) -> Any:
        """Route and execute a parsed command."""
        # 1. Handle empty input
        if parsed.category == CommandCategory.EMPTY:
            return None

        # 2. Handle invalid prefixes (missing prefix or syntax error)
        if parsed.category == CommandCategory.INVALID_PREFIX:
            if parsed.error:
                context.print_error(parsed.error)
            if parsed.suggestion:
                context.print_output(f"\n[İpucu]\n{parsed.suggestion}")
            self.audit_logger.log(
                category="command",
                action=parsed.raw,
                status="INVALID_PREFIX",
                details={"error": parsed.error, "suggestion": parsed.suggestion},
            )
            return None

        # 3. Handle parsing errors under recognized categories
        if parsed.error:
            context.print_error(parsed.error)
            if parsed.suggestion:
                context.print_output(f"\n[İpucu]\n{parsed.suggestion}")
            self.audit_logger.log(
                category=parsed.category.value,
                action=parsed.raw,
                status="PARSE_ERROR",
                details={"error": parsed.error},
            )
            return None

        # 4. Find handler in registry
        definition = self.registry.find(parsed.category, parsed.name)
        if not definition:
            context.print_error(
                f"'{parsed.category.value}' kategorisinde bilinmeyen komut: '{parsed.name}'"
            )
            # Offer category-specific help hint
            if parsed.category == CommandCategory.NORMAL:
                context.print_output("Normal komutların listesi için ' help' yazabilirsiniz.")
            elif parsed.category == CommandCategory.IMPORTANT:
                context.print_output("Önemli sistem komutları için '/help' veya '/system' yazabilirsiniz.")
            elif parsed.category == CommandCategory.UPDATE:
                context.print_output("Güncelleme komutları için '#' veya '# check' yazabilirsiniz.")
            elif parsed.category == CommandCategory.SETTINGS:
                context.print_output("Ayarlar merkezini açmak için '>' yazabilirsiniz.")

            self.audit_logger.log(
                category=parsed.category.value,
                action=parsed.name,
                status="NOT_FOUND",
                details={"raw": parsed.raw},
            )
            return None

        # 5. Permission / Authorization Gate
        authorized, denial_reason = self.permission_manager.check(
            command_name=f"{parsed.category.value}:{definition.name}",
            required_level=definition.permission_level,
            description=definition.description,
        )
        if not authorized:
            context.print_error(denial_reason or "Bu işlem için gerekli yetki bulunamadı.")
            return None

        # 6. Execute Handler
        try:
            result = definition.handler(context)
            self.audit_logger.log(
                category=parsed.category.value,
                action=definition.name,
                status="SUCCESS",
                details={"subcommand": parsed.subcommand, "args": parsed.args},
            )
            return result
        except Exception as error:
            context.print_error(f"Komut yürütülürken hata oluştu: {error}")
            self.audit_logger.log(
                category=parsed.category.value,
                action=definition.name,
                status="ERROR",
                details={"error": str(error), "raw": parsed.raw},
            )
            return None
