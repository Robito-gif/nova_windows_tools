# -*- coding: utf-8 -*-
"""Nova Windows Tools - Settings Data Model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SettingItem:
    """Individual setting specification and current state."""

    key: str                         # Hierarchical key e.g. "ai.model"
    name: str                        # Human readable label
    current_value: Any
    default_value: Any
    value_type: type                 # bool, int, float, str
    description: str = ""
    choices: list[Any] | None = None
    min_value: Any | None = None
    max_value: Any | None = None
    validator: Callable[[Any], tuple[bool, str | None]] | None = None
    dependencies: list[str] = field(default_factory=list)
    requires_restart: bool = False
    category: str = "general"

    def validate(self, new_value: Any) -> tuple[bool, str | None]:
        """Validate a proposed new value against type, bounds, choices, and custom rules."""
        # Type casting / conversion check
        typed_val = new_value
        if self.value_type is bool and isinstance(new_value, str):
            if new_value.lower() in ("true", "1", "yes", "evet", "on", "açık", "acik"):
                typed_val = True
            elif new_value.lower() in ("false", "0", "no", "hayır", "hayir", "off", "kapalı", "kapali"):
                typed_val = False
            else:
                return False, f"'{new_value}' bir boolean (True/False) değer olmalıdır."
        elif self.value_type is int and isinstance(new_value, (str, float)):
            try:
                typed_val = int(new_value)
            except ValueError:
                return False, f"'{new_value}' bir tam sayı olmalıdır."
        elif self.value_type is float and isinstance(new_value, (str, int)):
            try:
                typed_val = float(new_value)
            except ValueError:
                return False, f"'{new_value}' bir ondalıklı sayı olmalıdır."
        elif self.value_type is str and not isinstance(new_value, str):
            typed_val = str(new_value)

        # Choices check
        if self.choices is not None and typed_val not in self.choices:
            return False, f"Geçersiz seçim. Geçerli değerler: {', '.join(map(str, self.choices))}"

        # Bounds check
        if self.min_value is not None and typed_val < self.min_value:
            return False, f"Değer en az {self.min_value} olmalıdır."
        if self.max_value is not None and typed_val > self.max_value:
            return False, f"Değer en çok {self.max_value} olmalıdır."

        # Custom validator check
        if self.validator:
            ok, err = self.validator(typed_val)
            if not ok:
                return False, err or "Değer doğrulama kuralına uymuyor."

        return True, None

    def cast_value(self, raw_value: Any) -> Any:
        """Cast input into appropriate setting type."""
        if self.value_type is bool and isinstance(raw_value, str):
            return raw_value.lower() in ("true", "1", "yes", "evet", "on", "açık", "acik")
        if self.value_type is int and isinstance(raw_value, (str, float)):
            return int(raw_value)
        if self.value_type is float and isinstance(raw_value, (str, int)):
            return float(raw_value)
        return raw_value
