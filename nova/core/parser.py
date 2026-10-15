# -*- coding: utf-8 -*-
"""Nova Windows Tools - Command Parser Architecture.

Analyzes raw user input, identifies one of the 5 categories by prefix without
uncontrolled stripping, extracts command name, subcommands, positional arguments,
and option flags.
"""

from __future__ import annotations

import enum
import shlex
from dataclasses import dataclass, field
from typing import Any


class CommandCategory(str, enum.Enum):
    """The 5 distinct Nova command categories."""

    NORMAL = "normal"            # Single leading space ' '
    IMPORTANT = "important"        # Slash '/'
    SETTINGS = "settings"          # Greater-than '>'
    SETTINGS_EXIT = "settings_exit"  # Less-than '<'
    UPDATE = "update"              # Hash '#'
    INVALID_PREFIX = "invalid_prefix"  # Missing prefix or unrecognized leading character
    EMPTY = "empty"                # Empty input


@dataclass
class ParsedCommand:
    """Structured representation of a parsed command."""

    raw: str
    category: CommandCategory
    name: str = ""
    subcommand: str | None = None
    args: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    suggestion: str | None = None

    @property
    def is_valid(self) -> bool:
        """Return True if command has no parsing error and a recognized category."""
        return self.error is None and self.category not in (
            CommandCategory.INVALID_PREFIX,
            CommandCategory.EMPTY,
        )


class CommandParser:
    """Parser that respects the strict prefix protocol on raw user input."""

    # Dictionaries for intelligent suggestions when user forgets prefixes
    KNOWN_NORMAL_COMMANDS = {
        "help", "version", "status", "clear", "apps", "exit", "quit",
        "start", "stop", "display", "pomodoro", "meeting", "record", "studio",
        "license", "durum", "yardım", "yardim", "temizle", "başlat", "baslat",
        "durdur", "ekran", "çıkış", "cikis", "lisans"
    }

    KNOWN_IMPORTANT_COMMANDS = {
        "system", "diagnostics", "processes", "mcp", "ecosystem", "security",
        "update", "start", "stop", "record", "studio", "clear", "exit", "status", "help"
    }

    KNOWN_SETTINGS_COMMANDS = {
        "apps", "ai", "mcp", "development", "system", "updates", "network", "security"
    }

    KNOWN_UPDATE_COMMANDS = {
        "check", "preview", "download", "install", "full", "history", "rollback"
    }

    @classmethod
    def parse(cls, raw_input: str) -> ParsedCommand:
        """Parse raw user input without calling strip() beforehand."""
        if raw_input is None:
            return ParsedCommand(
                raw="",
                category=CommandCategory.EMPTY,
                error="Komut girişi boş olamaz.",
            )

        # Do NOT strip raw_input before checking the first character!
        if len(raw_input) == 0:
            return ParsedCommand(
                raw=raw_input,
                category=CommandCategory.EMPTY,
                error="Boş komut girişi.",
            )

        first_char = raw_input[0]

        # 1. Category A: Normal Command (Starts with a space)
        if first_char == " ":
            # Controlled removal of the single leading prefix space
            content = raw_input[1:]
            if not content.strip():
                return ParsedCommand(
                    raw=raw_input,
                    category=CommandCategory.NORMAL,
                    error="Normal komut adı belirtilmedi. Örnek: ' help', ' status'",
                    suggestion="Kullanılabilir normal komutları görmek için ' help' yazın.",
                )
            tokens = cls._tokenize(content)
            if not tokens:
                return ParsedCommand(
                    raw=raw_input,
                    category=CommandCategory.NORMAL,
                    error="Komut ayrıştırılamadı.",
                )
            name, subcommand, args, options = cls._extract_parts(tokens)
            return ParsedCommand(
                raw=raw_input,
                category=CommandCategory.NORMAL,
                name=name,
                subcommand=subcommand,
                args=args,
                options=options,
            )

        # 2. Category B: Important Command (Starts with '/')
        if first_char == "/":
            content = raw_input[1:]
            if not content.strip():
                return ParsedCommand(
                    raw=raw_input,
                    category=CommandCategory.IMPORTANT,
                    error="Önemli komut adı belirtilmedi. Örnek: '/system', '/diagnostics'",
                    suggestion="Sistem komutları için '/help' veya '/system' yazabilirsiniz.",
                )
            tokens = cls._tokenize(content)
            if not tokens:
                return ParsedCommand(
                    raw=raw_input,
                    category=CommandCategory.IMPORTANT,
                    error="Önemli komut ayrıştırılamadı.",
                )
            name, subcommand, args, options = cls._extract_parts(tokens)
            return ParsedCommand(
                raw=raw_input,
                category=CommandCategory.IMPORTANT,
                name=name,
                subcommand=subcommand,
                args=args,
                options=options,
            )

        # 3. Category C: Nova Ecosystem Settings (Starts with '>')
        if first_char == ">":
            content = raw_input[1:].strip()
            if not content:
                # Bare '>' opens the root settings center
                return ParsedCommand(
                    raw=raw_input,
                    category=CommandCategory.SETTINGS,
                    name="",
                )
            tokens = cls._tokenize(content)
            name, subcommand, args, options = cls._extract_parts(tokens)
            return ParsedCommand(
                raw=raw_input,
                category=CommandCategory.SETTINGS,
                name=name,
                subcommand=subcommand,
                args=args,
                options=options,
            )

        # 4. Category D: Settings Exit (Starts with '<')
        if first_char == "<":
            content = raw_input[1:].strip()
            tokens = cls._tokenize(content) if content else []
            name, subcommand, args, options = cls._extract_parts(tokens) if tokens else ("", None, [], {})
            return ParsedCommand(
                raw=raw_input,
                category=CommandCategory.SETTINGS_EXIT,
                name=name,
                subcommand=subcommand,
                args=args,
                options=options,
            )

        # 5. Category E: Full Update System (Starts with '#')
        if first_char == "#":
            content = raw_input[1:].strip()
            if not content:
                # Bare '#' opens the update center summary
                return ParsedCommand(
                    raw=raw_input,
                    category=CommandCategory.UPDATE,
                    name="",
                )
            tokens = cls._tokenize(content)
            name, subcommand, args, options = cls._extract_parts(tokens)
            return ParsedCommand(
                raw=raw_input,
                category=CommandCategory.UPDATE,
                name=name,
                subcommand=subcommand,
                args=args,
                options=options,
            )

        # 6. Invalid Prefix (No recognized starting character)
        clean_content = raw_input.strip()
        tokens = cls._tokenize(clean_content)
        first_token = tokens[0].lower() if tokens else clean_content.lower()

        suggestion = cls._generate_suggestion(first_token, clean_content)
        error_msg = (
            f"Geçersiz komut biçimi: '{raw_input}'. "
            f"Nova Windows Tools komutları tanımlı 5 kategoriden bir ön ek ile başlamalıdır."
        )

        return ParsedCommand(
            raw=raw_input,
            category=CommandCategory.INVALID_PREFIX,
            name=first_token,
            error=error_msg,
            suggestion=suggestion,
        )

    @classmethod
    def _tokenize(cls, text: str) -> list[str]:
        """Split text respecting quotes while avoiding shell escaping crashes."""
        if not text:
            return []
        try:
            return shlex.split(text, posix=False)
        except ValueError:
            # Fallback to standard whitespace split if quotes are unclosed
            return text.split()

    @classmethod
    def _extract_parts(
        cls, tokens: list[str]
    ) -> tuple[str, str | None, list[str], dict[str, Any]]:
        """Extract command name, subcommand, arguments and --options from tokens."""
        if not tokens:
            return "", None, [], {}

        name = tokens[0].lower()
        subcommand: str | None = None
        args: list[str] = []
        options: dict[str, Any] = {}

        idx = 1
        # If the second token is not an option flag, treat it as subcommand or first arg
        if idx < len(tokens) and not tokens[idx].startswith("-"):
            subcommand = tokens[idx].lower()
            idx += 1

        while idx < len(tokens):
            token = tokens[idx]
            if token.startswith("--"):
                option_name = token[2:].lower().replace("-", "_")
                # Check if next token is value
                if idx + 1 < len(tokens) and not tokens[idx + 1].startswith("-"):
                    options[option_name] = tokens[idx + 1]
                    idx += 2
                else:
                    options[option_name] = True
                    idx += 1
            elif token.startswith("-") and len(token) > 1 and not token[1].isdigit():
                flag_name = token[1:].lower()
                options[flag_name] = True
                idx += 1
            else:
                args.append(token)
                idx += 1

        return name, subcommand, args, options

    @classmethod
    def _generate_suggestion(cls, token: str, full_text: str) -> str:
        """Generate targeted suggestion for missing prefixes or typos."""
        if token in cls.KNOWN_NORMAL_COMMANDS:
            return (
                f"Normal bir işlem çalıştırmak istiyorsanız başına bir BOŞLUK ekleyin:\n"
                f"  ' {full_text}'"
            )
        if token in cls.KNOWN_IMPORTANT_COMMANDS:
            return (
                f"Önemli bir sistem komutu çalıştırmak istiyorsanız başına '/' ekleyin:\n"
                f"  '/{full_text}'"
            )
        if token in cls.KNOWN_SETTINGS_COMMANDS or token in {"settings", "ayarlar", "ayar"}:
            return (
                f"Nova Ayarlar Merkezi'ni açmak istiyorsanız başına '>' ekleyin:\n"
                f"  '> {full_text}' (veya doğrudan '>')"
            )
        if token in cls.KNOWN_UPDATE_COMMANDS or token in {"update", "güncelle", "guncelle"}:
            return (
                f"Güncelleme işlemlerini yönetmek için başına '#' ekleyin:\n"
                f"  '# {full_text}' (veya doğrudan '#')"
            )
        return (
            "Komut kategorileri:\n"
            "  ' <komut>' : Normal komutlar (başında 1 boşluk - örn: ' help')\n"
            "  '/<komut>' : Önemli sistem komutları (örn: '/system')\n"
            "  '>'        : Nova ayarlar merkezi (örn: '>', '> apps')\n"
            "  '<'        : Ayarlardan çıkış / geri dön\n"
            "  '#'        : Tam güncelleme sistemi (örn: '# check')"
        )
