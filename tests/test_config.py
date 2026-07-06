"""Comprehensive tests for the configuration system."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from config.defaults import INTERNAL_DEFAULTS
from config.loader import _load_env_overrides, _load_yaml_file, load_config
from config.schema import CONFIG_SCHEMA, _validate_ip_list
from config.validator import ConfigValidationError, validate_config
from security_agent.config.settings import (
    Settings,
    build_settings,
    load_settings,
    reload_settings,
)


class TestDefaults:
    def test_defaults_import(self) -> None:
        assert isinstance(INTERNAL_DEFAULTS, dict)

    def test_defaults_have_all_sections(self) -> None:
        required = {
            "general",
            "logging",
            "database",
            "discord",
            "security",
            "firewall",
            "monitoring",
            "performance",
            "developer",
            "metrics",
            "profiles",
            "rule_packs",
        }
        assert required.issubset(INTERNAL_DEFAULTS.keys())

    def test_defaults_no_empty_values(self) -> None:
        allowed_empty_str = {
            "general.hostname",
            "database.postgres.password",
            "database.mysql.password",
        }
        allowed_empty_list = {
            "security.trusted_networks",
            "security.whitelist",
            "security.blacklist",
        }

        def check(d: dict, path: str = "") -> None:
            for k, v in d.items():
                p = f"{path}.{k}" if path else k
                if isinstance(v, dict):
                    check(v, p)
                elif v is None:
                    pass
                elif isinstance(v, list):
                    assert len(v) > 0 or p in allowed_empty_list, f"Empty list at {p}"
                elif isinstance(v, str) and v == "":
                    assert p in allowed_empty_str, f"Empty string at {p}"
                elif isinstance(v, str):
                    assert v != "", f"Empty string at {p}"

        check(INTERNAL_DEFAULTS)

    def test_valid_config_passes(self) -> None:
        errors = validate_config(INTERNAL_DEFAULTS)
        assert errors == [], f"Unexpected errors: {errors}"


class TestSchemaValidation:
    def test_schema_import(self) -> None:
        assert isinstance(CONFIG_SCHEMA, dict)

    def test_invalid_log_level_fails(self) -> None:
        errors = validate_config({"general": {"log_level": "TRACE"}})
        assert len(errors) > 0

    def test_invalid_backend_fails(self) -> None:
        errors = validate_config({"database": {"backend": "mongodb"}})
        assert len(errors) > 0

    def test_invalid_port_fails(self) -> None:
        errors = validate_config({"database": {"postgres": {"port": 99999}}})
        assert len(errors) > 0

    def test_invalid_threshold_fails(self) -> None:
        errors = validate_config(
            {"security": {"thresholds": {"ssh_brute_force_count": 0}}}
        )
        assert len(errors) > 0

    def test_invalid_ban_policy_length_fails(self) -> None:
        errors = validate_config({"security": {"ban_policy": {"durations": [1, 2, 3]}}})
        assert len(errors) > 0

    def test_invalid_profile_fails(self) -> None:
        errors = validate_config({"general": {"profile": "nonexistent"}})
        assert len(errors) > 0

    def test_memory_limit_out_of_range_fails(self) -> None:
        errors = validate_config({"performance": {"memory_limit_mb": 500}})
        assert len(errors) > 0

    def test_invalid_firewall_backend_fails(self) -> None:
        errors = validate_config({"firewall": {"backend": "windows_firewall"}})
        assert len(errors) > 0

    def test_invalid_ip_address_fails(self) -> None:
        errors = _validate_ip_list(["not_an_ip"], "test")
        assert len(errors) > 0

    def test_valid_ip_passes(self) -> None:
        errors = _validate_ip_list(["10.0.0.0/8", "192.168.1.1"], "test")
        assert errors == []

    def test_wrong_type_fails(self) -> None:
        errors = validate_config({"general": {"debug": "not_a_boolean"}})
        assert len(errors) > 0

    def test_error_message_contains_path(self) -> None:
        errors = validate_config({"general": {"debug": "nope"}})
        assert any("debug" in e for e in errors)


class TestYamlLoading:
    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("general:\n  debug: true\n")
        assert _load_yaml_file(f) == {"general": {"debug": True}}

    def test_load_empty_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("")
        assert _load_yaml_file(f) == {}

    def test_load_missing_file(self, tmp_path: Path) -> None:
        assert _load_yaml_file(tmp_path / "nonexistent.yaml") == {}

    def test_load_malformed_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("{invalid: yaml: broken")
        with pytest.raises(ConfigValidationError):
            _load_yaml_file(f)


class TestEnvOverrides:
    def test_env_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AISEC_LOG_LEVEL", "DEBUG")
        result = _load_env_overrides()
        assert result["general"]["log_level"] == "DEBUG"

    def test_env_db_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AISEC_DB_BACKEND", "postgres")
        result = _load_env_overrides()
        assert result["database"]["backend"] == "postgres"

    def test_env_boolean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AISEC_DEBUG", "true")
        result = _load_env_overrides()
        assert result["general"]["debug"] is True

    def test_env_boolean_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AISEC_DEBUG", "false")
        result = _load_env_overrides()
        assert result["general"]["debug"] is False

    def test_env_comma_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AISEC_TRUSTED_NETWORKS", "10.0.0.0/8,192.168.0.0/16")
        result = _load_env_overrides()
        nets = result["security"]["trusted_networks"]
        assert isinstance(nets, list)
        assert len(nets) == 2

    def test_env_empty_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AISEC_DISCORD_WEBHOOK", "")
        result = _load_env_overrides()
        assert result["discord"]["webhook"] is None

    def test_env_ignores_non_aisec(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PATH", "/usr/bin")
        assert _load_env_overrides() == {}


class TestLoader:
    def test_without_file_uses_defaults(self) -> None:
        config = load_config()
        assert config["general"]["debug"] is False
        assert config["general"]["log_level"] == "INFO"
        assert config["database"]["backend"] == "sqlite"

    def test_file_overrides_defaults(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("general:\n  debug: true\n  log_level: DEBUG\n")
        config = load_config(f)
        assert config["general"]["debug"] is True
        assert config["general"]["log_level"] == "DEBUG"

    def test_partial_file_merges(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("general:\n  debug: true\n")
        config = load_config(f)
        assert config["general"]["debug"] is True
        assert config["general"]["log_level"] == "INFO"
        assert config["database"]["backend"] == "sqlite"

    def test_env_overrides_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("general:\n  debug: false\n  log_level: INFO\n")
        monkeypatch.setenv("AISEC_LOG_LEVEL", "DEBUG")
        config = load_config(f)
        assert config["general"]["log_level"] == "DEBUG"
        assert config["general"]["debug"] is False

    def test_config_not_found_graceful(self) -> None:
        config = load_config("/nonexistent/path/config.yaml")
        assert config["general"]["debug"] is False


class TestSettingsObjects:
    def test_settings_import(self) -> None:
        assert Settings is not None

    def test_settings_are_frozen(self) -> None:
        settings = build_settings(INTERNAL_DEFAULTS)
        with pytest.raises(AttributeError):
            settings.general.debug = True  # type: ignore[misc]

    def test_settings_api_access(self) -> None:
        settings = build_settings(INTERNAL_DEFAULTS)
        assert isinstance(settings.general.debug, bool)
        assert isinstance(settings.database.backend, str)
        assert isinstance(settings.security.thresholds.ssh_brute_force_count, int)
        assert isinstance(settings.monitoring.journald.enabled, bool)

    def test_build_from_valid_config(self) -> None:
        settings = build_settings(INTERNAL_DEFAULTS)
        assert settings.general.profile == "default"
        assert settings.database.backend == "sqlite"
        assert len(settings.security.ban_policy.durations) == 8

    def test_build_with_overrides(self) -> None:
        raw = {
            "general": {"debug": True, "log_level": "DEBUG"},
            "database": {"backend": "postgres"},
            "security": {"thresholds": {"ssh_brute_force_count": 20}},
        }
        settings = build_settings(raw)
        assert settings.general.debug is True
        assert settings.general.log_level == "DEBUG"
        assert settings.database.backend == "postgres"
        assert settings.security.thresholds.ssh_brute_force_count == 20

    def test_is_development_property(self) -> None:
        assert build_settings({"developer": {"developer_mode": True}}).is_development
        assert build_settings({"profiles": {"active": "development"}}).is_development
        assert build_settings({"general": {"profile": "development"}}).is_development
        assert not build_settings({}).is_development

    def test_load_settings_integration(self) -> None:
        settings = load_settings()
        assert isinstance(settings.general.debug, bool)
        assert settings.general.profile == "default"


class TestProfiles:
    def test_valid_profiles(self) -> None:
        for p in [
            "default",
            "web_server",
            "reverse_proxy",
            "database",
            "docker_host",
            "game_server",
            "mail_server",
            "development",
            "custom",
        ]:
            s = build_settings({"profiles": {"active": p}})
            assert s.profiles.active == p

    def test_invalid_profile_rejected(self) -> None:
        errors = validate_config({"profiles": {"active": "invalid"}})
        assert len(errors) > 0

    def test_default_profile_available(self) -> None:
        assert "default" in INTERNAL_DEFAULTS["profiles"]["available"]


class TestRulePacks:
    def test_rule_packs_configuration(self) -> None:
        s = build_settings({"rule_packs": {"active": ["core", "ssh", "nginx"]}})
        assert "core" in s.rule_packs.active
        assert "ssh" in s.rule_packs.active

    def test_default_rule_packs(self) -> None:
        s = build_settings(INTERNAL_DEFAULTS)
        assert "core" in s.rule_packs.active


class TestErrorReporting:
    def test_error_contains_value(self) -> None:
        errors = validate_config({"general": {"log_level": "BOGUS"}})
        assert any("BOGUS" in e for e in errors)

    def test_error_contains_expected(self) -> None:
        errors = validate_config({"general": {"log_level": "BOGUS"}})
        assert any("Expected" in e for e in errors)

    def test_error_contains_path(self) -> None:
        errors = validate_config(
            {"security": {"thresholds": {"ssh_brute_force_count": -1}}}
        )
        assert any("ssh_brute_force_count" in e for e in errors)

    def test_multiple_errors_reported(self) -> None:
        errors = validate_config(
            {
                "general": {"debug": "bad", "log_level": "BAD"},
                "database": {"backend": "bad"},
                "firewall": {"backend": "bad"},
            }
        )
        assert len(errors) >= 3

    def test_validation_error_raised(self) -> None:
        errors = validate_config({"general": {"log_level": "BAD"}})
        assert len(errors) > 0
        error = ConfigValidationError(errors)
        assert "BAD" in str(error)

    def test_error_is_actionable(self) -> None:
        errors = validate_config({"general": {"log_level": "BOGUS"}})
        assert any(
            "use one of" in e.lower()
            or "suggested" in e.lower()
            or "expected" in e.lower()
            for e in errors
        )


class TestExampleConfig:
    def test_example_config_exists(self) -> None:
        example = Path("config/config.yaml.example")
        assert example.exists()
        assert example.stat().st_size > 0

    def test_example_config_is_valid_yaml(self) -> None:
        with open("config/config.yaml.example") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_example_config_passes_validation(self) -> None:
        config = load_config("config/config.yaml.example")
        assert config["general"]["debug"] is False


class TestFullIntegration:
    def test_load_to_settings(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text(
            "general:\n  debug: true\n  log_level: DEBUG\n  profile: development\n"
        )
        raw = load_config(f)
        settings = build_settings(raw)
        assert settings.general.debug is True
        assert settings.general.log_level == "DEBUG"
        assert settings.general.profile == "development"
        assert settings.is_development

    def test_invalid_config_prevents_startup(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("general:\n  log_level: BAD\n")
        with pytest.raises(ConfigValidationError):
            load_config(f)

    def test_settings_cache(self) -> None:
        s1 = load_settings()
        s2 = load_settings()
        assert s1 is s2

    def test_reload_settings(self) -> None:
        s1 = load_settings()
        s2 = reload_settings()
        assert s1 is not s2
