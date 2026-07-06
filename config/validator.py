"""
Configuration validation engine.

Validates a configuration dictionary against the schema defined in schema.py.
Produces clear, actionable error messages for every invalid field.
"""

from __future__ import annotations

from typing import Any

from config.schema import CONFIG_SCHEMA


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        message = "Configuration validation failed:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        super().__init__(message)


def validate_config(
    config: dict[str, Any],
    schema: dict[str, Any] | None = None,
    path: str = "",
) -> list[str]:
    """
    Validate a configuration dictionary against the schema.

    Returns a list of error messages. Empty list = valid config.

    Each error message follows the format:
        "<section>: <key> — <problem>. Expected: <expected>. Got: <got>."
        "Suggested fix: <fix>"
    """
    if schema is None:
        schema = CONFIG_SCHEMA

    errors: list[str] = []

    for section_key, section_schema in schema.items():
        section_path = f"{path}.{section_key}" if path else section_key
        section_value = config.get(section_key)

        if section_value is None and section_schema.get("type") is not dict:
            # Optional fields (type includes None) are allowed to be missing
            expected_types = section_schema.get("type")
            is_optional = (
                isinstance(expected_types, tuple) and type(None) in expected_types
            )
            if not is_optional:
                errors.append(f"'{section_path}' is missing. It is required.")
            continue

        if isinstance(section_schema.get("fields"), dict):
            # Nested section — validate recursively
            if not isinstance(section_value, dict):
                errors.append(
                    f"'{section_path}' must be a section (dict). "
                    f"Got: {type(section_value).__name__}."
                )
                continue
            errors.extend(
                validate_config(section_value, section_schema["fields"], section_path)
            )
        else:
            # Leaf field — validate value
            errors.extend(
                _validate_field(
                    section_key, section_value, section_schema, section_path
                )
            )

    return errors


def _validate_field(
    _key: str,
    value: Any,
    schema_entry: dict[str, Any],
    path: str,
) -> list[str]:
    """Validate a single field against its schema entry."""
    errors: list[str] = []
    expected_types = schema_entry.get("type")

    # Check if value is None and nullable
    if value is None:
        if isinstance(expected_types, tuple) and type(None) in expected_types:
            return []  # None is allowed
        errors.append(
            f"'{path}': value is None but is required. "
            f"Expected type(s): {_type_names(expected_types)}."
        )
        return errors

    # Type check
    if not _check_type(value, expected_types):
        errors.append(
            f"'{path}': invalid type. "
            f"Expected: {_type_names(expected_types)}. "
            f"Got: {type(value).__name__} ('{str(value)[:50]}')."
        )
        return errors  # No further validation if type is wrong

    # Enum check
    enum_values = schema_entry.get("enum")
    if enum_values and value not in enum_values:
        errors.append(
            f"'{path}': invalid value. "
            f"Expected one of: {enum_values}. "
            f"Got: '{value}'."
            f"Suggested fix: use one of {enum_values}."
        )

    # Range check
    range_limits = schema_entry.get("range")
    if range_limits and isinstance(value, (int, float)):
        lo, hi = range_limits
        if not (lo <= value <= hi):
            errors.append(f"'{path}': out of range. Expected: {lo}-{hi}. Got: {value}.")

    # List item validation
    item_type = schema_entry.get("item_type")
    if item_type and isinstance(value, list):
        min_len = schema_entry.get("min_length", 0)
        max_len = schema_entry.get("max_length", len(value) + 1)
        if len(value) < min_len:
            errors.append(
                f"'{path}': too few items. Minimum: {min_len}. Got: {len(value)}."
            )
        if len(value) > max_len:
            errors.append(
                f"'{path}': too many items. Maximum: {max_len}. Got: {len(value)}."
            )
        for i, item in enumerate(value):
            if not _check_type(item, item_type):
                errors.append(
                    f"'{path}[{i}]': invalid type. "
                    f"Expected: {_type_names(item_type)}. "
                    f"Got: {type(item).__name__}."
                )

    # Custom validator
    custom_fn = schema_entry.get("custom")
    if custom_fn:
        try:
            custom_errors = custom_fn(value, path)
            errors.extend(custom_errors)
        except Exception as e:
            errors.append(f"'{path}': validation error: {e}")

    return errors


def _check_type(value: Any, expected: Any) -> bool:
    """Check if value matches the expected type(s)."""
    if isinstance(expected, tuple):
        return any(_check_type(value, t) for t in expected)
    if expected is str:
        return isinstance(value, str)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is bool:
        return isinstance(value, bool)
    if expected is float:
        return isinstance(value, (int, float))
    if expected is list:
        return isinstance(value, list)
    if expected is dict:
        return isinstance(value, dict)
    if expected is type(None):
        return value is None
    # Fallback: direct isinstance check
    return isinstance(value, expected) if isinstance(expected, type) else True


def _type_names(expected: Any) -> str:
    """Convert type spec to human-readable string."""
    if isinstance(expected, tuple):
        return " or ".join(_type_names(t) for t in expected)
    name_map = {
        str: "string",
        int: "integer",
        bool: "boolean",
        float: "number",
        list: "list",
        dict: "section (dict)",
        type(None): "null",
    }
    return name_map.get(expected, getattr(expected, "__name__", str(expected)))
