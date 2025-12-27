"""Tests for redgit/commands/init.py - Initialization command."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from redgit.commands.init import (
    get_builtin_prompts,
    copy_prompts,
    check_semgrep_installed,
    install_semgrep,
    PROMPT_CATEGORIES,
    PACKAGE_DIR,
    BUILTIN_PROMPTS_DIR,
)


# ==================== Tests for get_builtin_prompts ====================

class TestGetBuiltinPrompts:
    """Tests for get_builtin_prompts function."""

    def test_returns_list(self):
        """Test returns a list."""
        result = get_builtin_prompts()
        assert isinstance(result, list)

    def test_returns_prompt_names_without_extension(self):
        """Test returns prompt names without .md extension."""
        result = get_builtin_prompts()
        for name in result:
            assert not name.endswith(".md")

    @patch('redgit.commands.init.BUILTIN_PROMPTS_DIR')
    def test_returns_empty_when_no_commit_dir(self, mock_dir):
        """Test returns empty list when commit directory doesn't exist."""
        mock_commit_dir = MagicMock()
        mock_commit_dir.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_commit_dir)

        result = get_builtin_prompts()

        assert result == []


# ==================== Tests for copy_prompts ====================

class TestCopyPrompts:
    """Tests for copy_prompts function."""

    @patch('redgit.commands.init.BUILTIN_PROMPTS_DIR')
    def test_returns_zero_when_source_missing(self, mock_builtin_dir):
        """Test returns 0 when source directory doesn't exist."""
        mock_builtin_dir.exists.return_value = False

        result = copy_prompts()

        assert result == 0

    def test_copies_prompts_returns_count(self, tmp_path, monkeypatch):
        """Test copy_prompts copies files and returns count."""
        # Create source structure
        src_prompts = tmp_path / "src" / "prompts"
        src_commit = src_prompts / "commit"
        src_commit.mkdir(parents=True)
        (src_commit / "default.md").write_text("test prompt")
        (src_commit / "detailed.md").write_text("detailed prompt")

        # Create destination
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Patch the paths
        monkeypatch.setattr("redgit.commands.init.BUILTIN_PROMPTS_DIR", src_prompts)
        monkeypatch.setattr("redgit.commands.init.RETGIT_DIR", dest_dir)

        result = copy_prompts()

        assert result == 2  # Two .md files
        assert (dest_dir / "prompts" / "commit" / "default.md").exists()
        assert (dest_dir / "prompts" / "commit" / "detailed.md").exists()

    def test_prompt_categories_includes_commit(self):
        """Test PROMPT_CATEGORIES includes 'commit'."""
        assert "commit" in PROMPT_CATEGORIES


# ==================== Tests for check_semgrep_installed ====================

class TestCheckSemgrepInstalled:
    """Tests for check_semgrep_installed function."""

    @patch('subprocess.run')
    def test_returns_true_when_installed(self, mock_run):
        """Test returns True when semgrep is installed."""
        mock_run.return_value = MagicMock(returncode=0)

        result = check_semgrep_installed()

        assert result is True

    @patch('subprocess.run')
    def test_returns_false_when_not_installed(self, mock_run):
        """Test returns False when semgrep fails."""
        mock_run.return_value = MagicMock(returncode=1)

        result = check_semgrep_installed()

        assert result is False

    @patch('subprocess.run')
    def test_returns_false_when_file_not_found(self, mock_run):
        """Test returns False when semgrep not found."""
        mock_run.side_effect = FileNotFoundError("semgrep not found")

        result = check_semgrep_installed()

        assert result is False


# ==================== Tests for install_semgrep ====================

class TestInstallSemgrep:
    """Tests for install_semgrep function."""

    @patch('subprocess.run')
    @patch('typer.echo')
    def test_returns_true_on_success(self, mock_echo, mock_run):
        """Test returns True on successful installation."""
        mock_run.return_value = MagicMock(returncode=0)

        result = install_semgrep()

        assert result is True
        mock_run.assert_called_once()

    @patch('subprocess.run')
    @patch('typer.echo')
    def test_returns_false_on_failure(self, mock_echo, mock_run):
        """Test returns False on installation failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "pip install")

        result = install_semgrep()

        assert result is False

    @patch('subprocess.run')
    @patch('typer.echo')
    def test_calls_pip_install(self, mock_echo, mock_run):
        """Test calls pip install semgrep."""
        mock_run.return_value = MagicMock(returncode=0)

        install_semgrep()

        call_args = mock_run.call_args[0][0]
        assert "pip" in call_args
        assert "semgrep" in call_args


# ==================== Tests for select_llm_provider ====================

class TestSelectLLMProvider:
    """Tests for select_llm_provider function."""

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.echo')
    @patch('redgit.commands.init.check_provider_available')
    @patch('redgit.commands.init.load_providers')
    def test_returns_tuple(self, mock_load, mock_check, mock_echo, mock_prompt):
        """Test returns tuple of (provider, model, api_key)."""
        from redgit.commands.init import select_llm_provider

        mock_load.return_value = {
            "claude-code": {
                "name": "Claude Code",
                "type": "cli",
                "models": ["claude-sonnet-4-20250514"],
                "default_model": "claude-sonnet-4-20250514"
            }
        }
        mock_check.return_value = True
        mock_prompt.side_effect = ["claude-code", "claude-sonnet-4-20250514"]

        provider, model, api_key = select_llm_provider()

        assert provider == "claude-code"
        assert model is not None

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.echo')
    @patch('redgit.commands.init.check_provider_available')
    @patch('redgit.commands.init.load_providers')
    def test_defaults_to_claude_code_for_unknown(self, mock_load, mock_check, mock_echo, mock_prompt):
        """Test defaults to claude-code for unknown provider."""
        from redgit.commands.init import select_llm_provider

        mock_load.return_value = {
            "claude-code": {
                "name": "Claude Code",
                "type": "cli",
                "models": ["model1"],
                "default_model": "model1"
            }
        }
        mock_check.return_value = True
        mock_prompt.side_effect = ["unknown-provider", "model1"]

        provider, model, _ = select_llm_provider()

        assert provider == "claude-code"


# ==================== Tests for select_plugins ====================

class TestSelectPlugins:
    """Tests for select_plugins function."""

    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    @patch('redgit.commands.init.detect_project_type')
    @patch('redgit.commands.init.get_builtin_plugins')
    def test_returns_empty_when_no_plugins(self, mock_builtin, mock_detect, mock_echo, mock_confirm):
        """Test returns empty list when no plugins available."""
        from redgit.commands.init import select_plugins

        mock_builtin.return_value = []

        result = select_plugins()

        assert result == []

    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    @patch('redgit.commands.init.detect_project_type')
    @patch('redgit.commands.init.get_builtin_plugins')
    def test_returns_empty_when_user_declines(self, mock_builtin, mock_detect, mock_echo, mock_confirm):
        """Test returns empty list when user declines plugins."""
        from redgit.commands.init import select_plugins

        mock_builtin.return_value = ["laravel", "django"]
        mock_detect.return_value = ["laravel"]
        mock_confirm.return_value = False

        result = select_plugins()

        assert result == []

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    @patch('redgit.commands.init.detect_project_type')
    @patch('redgit.commands.init.get_builtin_plugins')
    def test_returns_all_plugins(self, mock_builtin, mock_detect, mock_echo, mock_confirm, mock_prompt):
        """Test returns all plugins when 'all' selected."""
        from redgit.commands.init import select_plugins

        mock_builtin.return_value = ["laravel", "django"]
        mock_detect.return_value = []
        mock_confirm.return_value = True
        mock_prompt.return_value = "all"

        result = select_plugins()

        assert result == ["laravel", "django"]

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    @patch('redgit.commands.init.detect_project_type')
    @patch('redgit.commands.init.get_builtin_plugins')
    def test_returns_selected_plugins(self, mock_builtin, mock_detect, mock_echo, mock_confirm, mock_prompt):
        """Test returns selected plugins from comma-separated list."""
        from redgit.commands.init import select_plugins

        mock_builtin.return_value = ["laravel", "django", "rails"]
        mock_detect.return_value = []
        mock_confirm.return_value = True
        mock_prompt.return_value = "laravel, django"

        result = select_plugins()

        assert "laravel" in result
        assert "django" in result
        assert "rails" not in result


# ==================== Tests for select_semgrep_settings ====================

class TestSelectSemgrepSettings:
    """Tests for select_semgrep_settings function."""

    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    def test_returns_disabled_when_declined(self, mock_echo, mock_confirm):
        """Test returns disabled config when user declines."""
        from redgit.commands.init import select_semgrep_settings

        mock_confirm.return_value = False

        result = select_semgrep_settings()

        assert result["enabled"] is False

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    @patch('redgit.commands.init.check_semgrep_installed')
    def test_returns_enabled_config(self, mock_check, mock_echo, mock_confirm, mock_prompt):
        """Test returns enabled config with settings."""
        from redgit.commands.init import select_semgrep_settings

        mock_confirm.return_value = True
        mock_check.return_value = True
        mock_prompt.return_value = "auto, p/security-audit"

        result = select_semgrep_settings()

        assert result["enabled"] is True
        assert "auto" in result["configs"]

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    @patch('redgit.commands.init.install_semgrep')
    @patch('redgit.commands.init.check_semgrep_installed')
    def test_installs_semgrep_if_missing(self, mock_check, mock_install, mock_echo, mock_confirm, mock_prompt):
        """Test offers to install semgrep if missing."""
        from redgit.commands.init import select_semgrep_settings

        mock_check.return_value = False
        mock_confirm.side_effect = [True, True]  # Enable, then install
        mock_install.return_value = True
        mock_prompt.return_value = "auto"

        result = select_semgrep_settings()

        mock_install.assert_called_once()


# ==================== Tests for select_quality_settings ====================

class TestSelectQualitySettings:
    """Tests for select_quality_settings function."""

    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    def test_returns_disabled_when_declined(self, mock_echo, mock_confirm):
        """Test returns disabled config when user declines."""
        from redgit.commands.init import select_quality_settings

        mock_confirm.return_value = False

        result = select_quality_settings()

        assert result["enabled"] is False

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    def test_returns_enabled_config_with_threshold(self, mock_echo, mock_confirm, mock_prompt):
        """Test returns enabled config with threshold."""
        from redgit.commands.init import select_quality_settings

        mock_confirm.side_effect = [True, True]  # Enable, fail on security
        mock_prompt.return_value = 80

        result = select_quality_settings()

        assert result["enabled"] is True
        assert result["threshold"] == 80
        assert result["fail_on_security"] is True

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    def test_clamps_threshold_to_valid_range(self, mock_echo, mock_confirm, mock_prompt):
        """Test clamps threshold to 0-100 range."""
        from redgit.commands.init import select_quality_settings

        mock_confirm.side_effect = [True, False]
        mock_prompt.return_value = 150  # Over 100

        result = select_quality_settings()

        assert result["threshold"] == 100

    @patch('redgit.commands.init.typer.prompt')
    @patch('redgit.commands.init.typer.confirm')
    @patch('redgit.commands.init.typer.echo')
    def test_clamps_negative_threshold(self, mock_echo, mock_confirm, mock_prompt):
        """Test clamps negative threshold to 0."""
        from redgit.commands.init import select_quality_settings

        mock_confirm.side_effect = [True, False]
        mock_prompt.return_value = -10  # Negative

        result = select_quality_settings()

        assert result["threshold"] == 0


# ==================== Tests for init_cmd CLI ====================

class TestInitCmdCLI:
    """CLI tests for init_cmd."""

    def test_init_help(self):
        """Test init command help."""
        from typer.testing import CliRunner
        from redgit.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "Initialize" in result.stdout or "init" in result.stdout.lower()

    @patch('redgit.commands.init.select_semgrep_settings')
    @patch('redgit.commands.init.select_quality_settings')
    @patch('redgit.commands.init.select_plugins')
    @patch('redgit.commands.init.select_llm_provider')
    @patch('redgit.commands.init.copy_prompts')
    @patch('redgit.commands.init.ConfigManager')
    @patch('redgit.commands.init.RETGIT_DIR')
    def test_init_creates_config(
        self, mock_dir, mock_config, mock_copy,
        mock_llm, mock_plugins, mock_quality, mock_semgrep
    ):
        """Test init creates configuration."""
        from typer.testing import CliRunner
        from redgit.commands.init import init_cmd
        import typer

        mock_dir.mkdir = MagicMock()
        mock_config.return_value.save = MagicMock()
        mock_copy.return_value = 3
        mock_llm.return_value = ("claude-code", "claude-sonnet-4-20250514", None)
        mock_plugins.return_value = []
        mock_quality.return_value = {"enabled": False}
        mock_semgrep.return_value = {"enabled": False}

        test_app = typer.Typer()
        test_app.command()(init_cmd)

        runner = CliRunner()
        result = runner.invoke(test_app, input="test-project\n")

        # Config should be saved
        mock_config.return_value.save.assert_called_once()


# ==================== Tests for Constants ====================

class TestInitConstants:
    """Tests for init module constants."""

    def test_package_dir_exists(self):
        """Test PACKAGE_DIR points to existing directory."""
        assert PACKAGE_DIR.exists()

    def test_builtin_prompts_dir_path(self):
        """Test BUILTIN_PROMPTS_DIR is under PACKAGE_DIR."""
        assert str(BUILTIN_PROMPTS_DIR).startswith(str(PACKAGE_DIR))

    def test_prompt_categories_not_empty(self):
        """Test PROMPT_CATEGORIES is not empty."""
        assert len(PROMPT_CATEGORIES) > 0
