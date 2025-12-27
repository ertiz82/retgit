"""
Integration tests for RedGit CLI commands.

Tests the CLI commands using typer's CliRunner to simulate real command invocations.
"""

import pytest
import os
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch

from redgit.cli import app
from redgit import __version__


runner = CliRunner()


class TestMainApp:
    """Tests for the main CLI application."""

    def test_version_flag(self):
        """Test --version flag shows version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_version_short_flag(self):
        """Test -v flag shows version."""
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_help_flag(self):
        """Test --help flag shows help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "redgit" in result.stdout.lower()
        assert "Usage" in result.stdout or "usage" in result.stdout

    def test_no_args_shows_help(self):
        """Test that no args shows help (no_args_is_help=True)."""
        result = runner.invoke(app, [])
        # Should show help, not error
        assert "Usage" in result.stdout or "usage" in result.stdout


class TestConfigCommands:
    """Tests for config subcommands."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config directory and file."""
        redgit_dir = tmp_path / ".redgit"
        redgit_dir.mkdir()
        config_file = redgit_dir / "config.yaml"
        config_file.write_text("""
project:
  name: test-project
llm:
  provider: claude-code
  model: claude-3-opus
plugins:
  enabled:
    - laravel
notifications:
  enabled: true
  events:
    push: true
    commit: false
quality:
  enabled: false
  threshold: 70
""")
        return tmp_path

    def test_config_path(self, temp_config):
        """Test config path command."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "path"])
                assert result.exit_code == 0
                assert "config.yaml" in result.stdout

    def test_config_get_existing_value(self, temp_config):
        """Test config get for existing value."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "get", "project.name"])
                assert result.exit_code == 0
                assert "test-project" in result.stdout

    def test_config_get_nested_value(self, temp_config):
        """Test config get for nested value."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "get", "llm.provider"])
                assert result.exit_code == 0
                assert "claude-code" in result.stdout

    def test_config_get_missing_value(self, temp_config):
        """Test config get for missing value."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "get", "nonexistent.path"])
                assert result.exit_code == 1
                assert "not found" in result.stdout

    def test_config_set_value(self, temp_config):
        """Test config set command."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "set", "quality.threshold", "80"])
                assert result.exit_code == 0

                # Verify it was set
                result = runner.invoke(app, ["config", "get", "quality.threshold"])
                assert "80" in result.stdout

    def test_config_set_boolean_true(self, temp_config):
        """Test config set with boolean true."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "set", "quality.enabled", "true"])
                assert result.exit_code == 0

    def test_config_set_boolean_false(self, temp_config):
        """Test config set with boolean false."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "set", "notifications.enabled", "false"])
                assert result.exit_code == 0

    def test_config_show_section(self, temp_config):
        """Test config show for a section."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "show", "llm"])
                assert result.exit_code == 0
                assert "provider" in result.stdout or "llm" in result.stdout

    def test_config_show_missing_section(self, temp_config):
        """Test config show for missing section."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "show", "nonexistent"])
                assert "not found" in result.stdout or "empty" in result.stdout

    def test_config_list(self, temp_config):
        """Test config list command."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "list"])
                assert result.exit_code == 0
                assert "project" in result.stdout or "llm" in result.stdout

    def test_config_list_section(self, temp_config):
        """Test config list for a section."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "list", "llm"])
                assert result.exit_code == 0

    def test_config_yaml(self, temp_config):
        """Test config yaml command."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "yaml"])
                assert result.exit_code == 0
                # Should output YAML content
                assert "project" in result.stdout or "llm" in result.stdout

    def test_config_yaml_section(self, temp_config):
        """Test config yaml for a section."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "yaml", "llm"])
                assert result.exit_code == 0

    def test_config_unset_existing(self, temp_config):
        """Test config unset for existing value."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "unset", "quality.threshold"])
                assert result.exit_code == 0
                assert "Removed" in result.stdout

    def test_config_unset_missing(self, temp_config):
        """Test config unset for missing value."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "unset", "nonexistent.path"])
                assert result.exit_code == 1
                assert "not found" in result.stdout

    def test_config_notifications(self, temp_config):
        """Test config notifications command."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "notifications"])
                assert result.exit_code == 0
                assert "Notification" in result.stdout

    def test_config_quality_show(self, temp_config):
        """Test config quality command shows status."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "quality"])
                assert result.exit_code == 0
                assert "Quality" in result.stdout

    def test_config_quality_enable(self, temp_config):
        """Test config quality --enable."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "quality", "--enable"])
                assert result.exit_code == 0
                assert "enabled" in result.stdout

    def test_config_quality_disable(self, temp_config):
        """Test config quality --disable."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "quality", "--disable"])
                assert result.exit_code == 0
                assert "disabled" in result.stdout

    def test_config_quality_threshold(self, temp_config):
        """Test config quality --threshold."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "quality", "--threshold", "85"])
                assert result.exit_code == 0
                assert "85" in result.stdout


class TestConfigSemgrep:
    """Tests for config semgrep subcommand."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config directory and file."""
        redgit_dir = tmp_path / ".redgit"
        redgit_dir.mkdir()
        config_file = redgit_dir / "config.yaml"
        config_file.write_text("""
semgrep:
  enabled: false
  configs:
    - auto
""")
        return tmp_path

    def test_semgrep_show_status(self, temp_config):
        """Test config semgrep shows status."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                with patch('redgit.commands.config._check_semgrep_installed', return_value=False):
                    result = runner.invoke(app, ["config", "semgrep"])
                    assert result.exit_code == 0
                    assert "Semgrep" in result.stdout

    def test_semgrep_list_rules(self, temp_config):
        """Test config semgrep --list-rules."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "semgrep", "--list-rules"])
                assert result.exit_code == 0
                assert "security-audit" in result.stdout
                assert "python" in result.stdout

    def test_semgrep_add_config(self, temp_config):
        """Test config semgrep --add."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "semgrep", "--add", "p/python"])
                assert result.exit_code == 0
                assert "Added" in result.stdout or "p/python" in result.stdout

    def test_semgrep_remove_config(self, temp_config):
        """Test config semgrep --remove."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "semgrep", "--remove", "auto"])
                assert result.exit_code == 0
                assert "Removed" in result.stdout or "auto" in result.stdout


class TestHelpCommands:
    """Test help output for various commands."""

    def test_config_help(self):
        """Test config --help."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "config" in result.stdout.lower()

    def test_propose_help(self):
        """Test propose --help."""
        result = runner.invoke(app, ["propose", "--help"])
        assert result.exit_code == 0

    def test_push_help(self):
        """Test push --help."""
        result = runner.invoke(app, ["push", "--help"])
        assert result.exit_code == 0

    def test_integration_help(self):
        """Test integration --help."""
        result = runner.invoke(app, ["integration", "--help"])
        assert result.exit_code == 0

    def test_plugin_help(self):
        """Test plugin --help."""
        result = runner.invoke(app, ["plugin", "--help"])
        assert result.exit_code == 0

    def test_notify_help(self):
        """Test notify --help."""
        result = runner.invoke(app, ["notify", "--help"])
        assert result.exit_code == 0

    def test_quality_help(self):
        """Test quality --help."""
        result = runner.invoke(app, ["quality", "--help"])
        assert result.exit_code == 0


class TestConfigResetCommand:
    """Tests for config reset subcommand."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config directory and file."""
        redgit_dir = tmp_path / ".redgit"
        redgit_dir.mkdir()
        config_file = redgit_dir / "config.yaml"
        config_file.write_text("""
notifications:
  enabled: false
  events:
    push: false
quality:
  enabled: true
  threshold: 50
workflow:
  strategy: merge-request
""")
        return tmp_path

    def test_reset_notifications_with_force(self, temp_config):
        """Test config reset notifications --force."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "reset", "notifications", "--force"])
                assert result.exit_code == 0
                assert "Reset" in result.stdout

    def test_reset_quality_with_force(self, temp_config):
        """Test config reset quality --force."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "reset", "quality", "--force"])
                assert result.exit_code == 0
                assert "Reset" in result.stdout

    def test_reset_workflow_with_force(self, temp_config):
        """Test config reset workflow --force."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "reset", "workflow", "--force"])
                assert result.exit_code == 0
                assert "Reset" in result.stdout

    def test_reset_unknown_section(self, temp_config):
        """Test config reset with unknown section."""
        with patch('redgit.core.config.RETGIT_DIR', temp_config / ".redgit"):
            with patch('redgit.core.config.CONFIG_PATH', temp_config / ".redgit" / "config.yaml"):
                result = runner.invoke(app, ["config", "reset", "unknown", "--force"])
                assert "No defaults" in result.stdout


class TestConfigListPrompts:
    """Tests for config list-prompts subcommand."""

    def test_list_prompts(self):
        """Test config list-prompts shows available prompts."""
        result = runner.invoke(app, ["config", "list-prompts"])
        assert result.exit_code == 0
        assert "Prompt" in result.stdout or "prompt" in result.stdout


class TestSubApps:
    """Test that sub-apps are properly registered."""

    def test_integration_app_registered(self):
        """Test integration subcommand is available."""
        result = runner.invoke(app, ["integration"])
        # Should not error, might show help or list
        assert result.exit_code == 0 or "Usage" in result.stdout

    def test_plugin_app_registered(self):
        """Test plugin subcommand is available."""
        result = runner.invoke(app, ["plugin"])
        assert result.exit_code == 0 or "Usage" in result.stdout

    def test_tap_app_registered(self):
        """Test tap subcommand is available."""
        result = runner.invoke(app, ["tap"])
        assert result.exit_code == 0 or "Usage" in result.stdout

    def test_ci_app_registered(self):
        """Test ci subcommand is available."""
        result = runner.invoke(app, ["ci"])
        assert result.exit_code == 0 or "Usage" in result.stdout

    def test_quality_app_registered(self):
        """Test quality subcommand is available."""
        result = runner.invoke(app, ["quality"])
        assert result.exit_code == 0 or "Usage" in result.stdout

    def test_scout_app_registered(self):
        """Test scout subcommand is available."""
        result = runner.invoke(app, ["scout"])
        assert result.exit_code == 0 or "Usage" in result.stdout


class TestErrorHandling:
    """Test error handling in CLI commands."""

    def test_invalid_command(self):
        """Test invalid command shows error."""
        result = runner.invoke(app, ["invalid-command-that-doesnt-exist"])
        assert result.exit_code != 0

    def test_config_get_requires_path(self):
        """Test config get requires path argument."""
        result = runner.invoke(app, ["config", "get"])
        assert result.exit_code != 0

    def test_config_set_requires_both_args(self):
        """Test config set requires path and value."""
        result = runner.invoke(app, ["config", "set", "only.path"])
        assert result.exit_code != 0
