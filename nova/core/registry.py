# -*- coding: utf-8 -*-
"""Nova Windows Tools - Command Registry and Execution Context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from nova.core.parser import CommandCategory, ParsedCommand
from nova.core.permissions import PermissionLevel


@dataclass
class CommandContext:
    """Execution context provided to command handlers."""

    parsed: ParsedCommand
    app: Any = None
    print_output: Callable[[str], None] = print
    print_error: Callable[[str], None] = print
    confirm: Callable[[str], bool] = lambda prompt: True
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandDefinition:
    """Specification of a registered command."""

    name: str
    category: CommandCategory
    handler: Callable[[CommandContext], Any]
    description: str = ""
    usage: str = ""
    permission_level: PermissionLevel = PermissionLevel.NORMAL
    aliases: list[str] = field(default_factory=list)


class CommandRegistry:
    """Registry maintaining commands organized by their category."""

    def __init__(self):
        # Maps (category, lookup_key) -> CommandDefinition
        self._commands: dict[tuple[CommandCategory, str], CommandDefinition] = {}
        self._definitions: list[CommandDefinition] = []

    def register(self, definition: CommandDefinition) -> None:
        """Register a command definition along with its aliases."""
        self._definitions.append(definition)
        key = (definition.category, definition.name.lower())
        self._commands[key] = definition

        for alias in definition.aliases:
            self._commands[(definition.category, alias.lower())] = definition

    def find(self, category: CommandCategory, name: str) -> CommandDefinition | None:
        """Find a registered command by category and name/alias."""
        return self._commands.get((category, name.lower()))

    def list_by_category(self, category: CommandCategory) -> list[CommandDefinition]:
        """Return unique command definitions under a category."""
        seen = set()
        result = []
        for cmd in self._definitions:
            if cmd.category == category and cmd.name not in seen:
                seen.add(cmd.name)
                result.append(cmd)
        return result

    def all_commands(self) -> list[CommandDefinition]:
        """Return all registered command definitions."""
        seen = set()
        result = []
        for cmd in self._definitions:
            key = (cmd.category, cmd.name)
            if key not in seen:
                seen.add(key)
                result.append(cmd)
        return result
