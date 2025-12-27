"""
Unit tests for redgit.core.config module.
"""

import os
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from redgit.core.config import (
    ConfigManager,
    StateManager,
    DEFAULT_WORKFLOW,
    DEFAULT_NOTIFICATIONS,
    DEFAULT_QUALITY,
    DEFAULT_SEMGREP,
    RETGIT_DIR,
    CONFIG_PATH,
    STATE_PATH,
)


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_init_creates_redgit_dir(self, temp_dir, change_cwd):
        """Test that ConfigManager creates .redgit directory on init."""
        redgit_dir = temp_dir / ".redgit"
        assert not redgit_dir.exists()

        ConfigManager()

        assert redgit_dir.exists()

    def test_load_returns_empty_dict_when_no_config(self, temp_dir, change_cwd):
        """Test load returns empty dict with defaults when no config exists."""
        manager = ConfigManager()
        config = manager.load()

        assert isinstance(config, dict)
        assert "workflow" in config
        assert config["workflow"]["strategy"] == "local-merge"

    def test_load_returns_config_from_file(self, config_file, change_cwd, temp_dir):
        """Test load returns config from file."""
        os.chdir(temp_dir)
        manager = ConfigManager()
        config = manager.load()

        assert config["project"]["name"] == "TestProject"
        assert config["llm"]["provider"] == "ollama"

    def test_load_merges_workflow_defaults(self, temp_dir, change_cwd):
        """Test that missing workflow keys are filled with defaults."""
        redgit_dir = temp_dir / ".redgit"
        redgit_dir.mkdir()
        config_path = redgit_dir / "config.yaml"
        config_path.write_text(yaml.dump({"workflow": {"strategy": "merge-request"}}))

        manager = ConfigManager()
        config = manager.load()

        assert config["workflow"]["strategy"] == "merge-request"
        assert config["workflow"]["auto_transition"] == True
        assert config["workflow"]["create_missing_issues"] == "ask"

    def test_save_writes_config_file(self, temp_dir, change_cwd):
        """Test save writes config to file."""
        manager = ConfigManager()
        test_config = {"project": {"name": "SaveTest"}, "version": "1.0.0"}

        manager.save(test_config)

        saved = yaml.safe_load((temp_dir / ".redgit" / "config.yaml").read_text())
        assert saved["project"]["name"] == "SaveTest"
        assert saved["version"] == "1.0.0"

    def test_get_active_integration_returns_none_when_not_set(self, temp_dir, change_cwd):
        """Test get_active_integration returns None when not configured."""
        manager = ConfigManager()

        result = manager.get_active_integration("task_management")

        assert result is None

    def test_get_active_integration_returns_configured_value(self, config_file, change_cwd, temp_dir):
        """Test get_active_integration returns configured integration."""
        os.chdir(temp_dir)

        # Update config with active integration
        config = yaml.safe_load(config_file.read_text())
        config["active"] = {"task_management": "jira"}
        config_file.write_text(yaml.dump(config))

        manager = ConfigManager()
        result = manager.get_active_integration("task_management")

        assert result == "jira"

    def test_set_active_integration_creates_active_section(self, temp_dir, change_cwd):
        """Test set_active_integration creates active section if missing."""
        manager = ConfigManager()

        manager.set_active_integration("task_management", "linear")

        config = manager.load()
        assert config["active"]["task_management"] == "linear"

    def test_get_notifications_config_returns_defaults(self, temp_dir, change_cwd):
        """Test get_notifications_config returns defaults when not configured."""
        manager = ConfigManager()
        notifications = manager.get_notifications_config()

        assert notifications["enabled"] == True
        assert notifications["events"]["push"] == True
        assert notifications["events"]["commit"] == False

    def test_get_notifications_config_merges_with_defaults(self, temp_dir, change_cwd):
        """Test get_notifications_config merges user config with defaults."""
        redgit_dir = temp_dir / ".redgit"
        redgit_dir.mkdir()
        config_path = redgit_dir / "config.yaml"
        config_path.write_text(yaml.dump({
            "notifications": {
                "enabled": True,
                "events": {
                    "commit": True,  # Override default False
                    "push": False,   # Override default True
                }
            }
        }))

        manager = ConfigManager()
        notifications = manager.get_notifications_config()

        assert notifications["events"]["commit"] == True
        assert notifications["events"]["push"] == False
        assert notifications["events"]["pr_created"] == True  # Default preserved

    def test_is_notification_enabled_respects_master_switch(self, temp_dir, change_cwd):
        """Test is_notification_enabled returns False when master switch is off."""
        redgit_dir = temp_dir / ".redgit"
        redgit_dir.mkdir()
        config_path = redgit_dir / "config.yaml"
        config_path.write_text(yaml.dump({
            "notifications": {
                "enabled": False,
                "events": {"push": True}
            }
        }))

        manager = ConfigManager()

        assert manager.is_notification_enabled("push") == False

    def test_is_notification_enabled_returns_event_status(self, temp_dir, change_cwd):
        """Test is_notification_enabled returns correct event status."""
        manager = ConfigManager()

        assert manager.is_notification_enabled("push") == True
        assert manager.is_notification_enabled("commit") == False

    def test_get_value_returns_nested_value(self, config_file, change_cwd, temp_dir):
        """Test get_value returns nested config value by dot notation."""
        os.chdir(temp_dir)
        manager = ConfigManager()

        result = manager.get_value("llm.provider")

        assert result == "ollama"

    def test_get_value_returns_none_for_missing_path(self, temp_dir, change_cwd):
        """Test get_value returns None for non-existent path."""
        manager = ConfigManager()

        result = manager.get_value("non.existent.path")

        assert result is None

    def test_set_value_creates_nested_structure(self, temp_dir, change_cwd):
        """Test set_value creates nested structure if needed."""
        manager = ConfigManager()

        manager.set_value("integrations.jira.enabled", True)

        config = manager.load()
        assert config["integrations"]["jira"]["enabled"] == True

    def test_set_value_updates_existing_value(self, config_file, change_cwd, temp_dir):
        """Test set_value updates existing nested value."""
        os.chdir(temp_dir)
        manager = ConfigManager()

        manager.set_value("llm.timeout", 600)

        config = manager.load()
        assert config["llm"]["timeout"] == 600

    def test_get_quality_config_returns_defaults(self, temp_dir, change_cwd):
        """Test get_quality_config returns defaults when not configured."""
        manager = ConfigManager()
        quality = manager.get_quality_config()

        assert quality["enabled"] == False
        assert quality["threshold"] == 70
        assert quality["fail_on_security"] == True

    def test_get_semgrep_config_returns_defaults(self, temp_dir, change_cwd):
        """Test get_semgrep_config returns defaults when not configured."""
        manager = ConfigManager()
        semgrep = manager.get_semgrep_config()

        assert semgrep["enabled"] == False
        assert semgrep["configs"] == ["auto"]
        assert "ERROR" in semgrep["severity"]


class TestStateManager:
    """Tests for StateManager class."""

    def test_init_creates_redgit_dir(self, temp_dir, change_cwd):
        """Test that StateManager creates .redgit directory on init."""
        redgit_dir = temp_dir / ".redgit"
        assert not redgit_dir.exists()

        StateManager()

        assert redgit_dir.exists()

    def test_load_returns_empty_dict_when_no_state(self, temp_dir, change_cwd):
        """Test load returns empty dict when no state file exists."""
        manager = StateManager()
        state = manager.load()

        assert isinstance(state, dict)
        assert state == {}

    def test_save_writes_state_file(self, temp_dir, change_cwd):
        """Test save writes state to file."""
        manager = StateManager()
        test_state = {"session": {"branch": "feature/test"}}

        manager.save(test_state)

        saved = yaml.safe_load((temp_dir / ".redgit" / "state.yaml").read_text())
        assert saved["session"]["branch"] == "feature/test"

    def test_get_session_returns_none_when_no_session(self, temp_dir, change_cwd):
        """Test get_session returns None when no session exists."""
        manager = StateManager()

        result = manager.get_session()

        assert result is None

    def test_get_session_returns_session_data(self, temp_dir, change_cwd):
        """Test get_session returns session data when it exists."""
        manager = StateManager()
        manager.save({
            "session": {
                "branch": "feature/test",
                "issue_key": "PROJ-123"
            }
        })

        result = manager.get_session()

        assert result["branch"] == "feature/test"
        assert result["issue_key"] == "PROJ-123"

    def test_set_session_creates_session(self, temp_dir, change_cwd):
        """Test saving session via save method."""
        manager = StateManager()
        session_data = {"branch": "feature/new", "issue_key": "PROJ-456"}

        # Use save method directly to set session
        manager.save({"session": session_data})

        state = manager.load()
        assert state["session"]["branch"] == "feature/new"

    def test_clear_session_removes_session(self, temp_dir, change_cwd):
        """Test clear_session removes session data."""
        manager = StateManager()
        manager.save({"session": {"branch": "feature/test"}})

        manager.clear_session()

        state = manager.load()
        assert "session" not in state or state.get("session") is None


class TestDefaultConfigs:
    """Tests for default configuration values."""

    def test_default_workflow_has_required_keys(self):
        """Test DEFAULT_WORKFLOW has all required keys."""
        required_keys = ["strategy", "auto_transition", "create_missing_issues", "default_issue_type"]
        for key in required_keys:
            assert key in DEFAULT_WORKFLOW

    def test_default_notifications_has_required_keys(self):
        """Test DEFAULT_NOTIFICATIONS has all required keys."""
        assert "enabled" in DEFAULT_NOTIFICATIONS
        assert "events" in DEFAULT_NOTIFICATIONS
        assert "push" in DEFAULT_NOTIFICATIONS["events"]
        assert "commit" in DEFAULT_NOTIFICATIONS["events"]

    def test_default_quality_has_required_keys(self):
        """Test DEFAULT_QUALITY has all required keys."""
        required_keys = ["enabled", "threshold", "fail_on_security", "prompt_file"]
        for key in required_keys:
            assert key in DEFAULT_QUALITY

    def test_default_semgrep_has_required_keys(self):
        """Test DEFAULT_SEMGREP has all required keys."""
        required_keys = ["enabled", "configs", "severity", "exclude", "timeout"]
        for key in required_keys:
            assert key in DEFAULT_SEMGREP


class TestValueParsing:
    """Tests for value parsing in set_value."""

    def test_set_value_parses_boolean_true(self, temp_dir, change_cwd):
        """Test set_value parses 'true' as boolean True."""
        manager = ConfigManager()

        manager.set_value("test.enabled", "true")

        config = manager.load()
        assert config["test"]["enabled"] is True

    def test_set_value_parses_boolean_false(self, temp_dir, change_cwd):
        """Test set_value parses 'false' as boolean False."""
        manager = ConfigManager()

        manager.set_value("test.enabled", "false")

        config = manager.load()
        assert config["test"]["enabled"] is False

    def test_set_value_parses_integer(self, temp_dir, change_cwd):
        """Test set_value parses numeric strings as integers."""
        manager = ConfigManager()

        manager.set_value("test.count", "42")

        config = manager.load()
        assert config["test"]["count"] == 42

    def test_set_value_parses_float(self, temp_dir, change_cwd):
        """Test set_value parses decimal strings as floats."""
        manager = ConfigManager()

        manager.set_value("test.ratio", "3.14")

        config = manager.load()
        assert config["test"]["ratio"] == 3.14

    def test_set_value_parses_none(self, temp_dir, change_cwd):
        """Test set_value parses 'none' as None."""
        manager = ConfigManager()

        manager.set_value("test.value", "none")

        config = manager.load()
        assert config["test"]["value"] is None

    def test_set_value_preserves_strings(self, temp_dir, change_cwd):
        """Test set_value preserves regular strings."""
        manager = ConfigManager()

        manager.set_value("test.name", "my-project")

        config = manager.load()
        assert config["test"]["name"] == "my-project"