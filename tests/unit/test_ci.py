"""Tests for redgit/commands/ci.py - CI/CD command."""

import pytest
from unittest.mock import patch, MagicMock
import typer

from redgit.commands.ci import (
    _get_cicd,
    _check_cicd,
    _status_icon,
    ci_app,
)


# ==================== Tests for _get_cicd ====================

class TestGetCicd:
    """Tests for _get_cicd function."""

    @patch('redgit.commands.ci.get_cicd')
    @patch('redgit.commands.ci.ConfigManager')
    def test_returns_cicd_integration(self, mock_config, mock_get_cicd):
        """Test returns CI/CD integration from config."""
        mock_config.return_value.load.return_value = {"integrations": {}}
        mock_cicd = MagicMock()
        mock_get_cicd.return_value = mock_cicd

        result = _get_cicd()

        assert result == mock_cicd

    @patch('redgit.commands.ci.get_cicd')
    @patch('redgit.commands.ci.ConfigManager')
    def test_returns_none_when_not_configured(self, mock_config, mock_get_cicd):
        """Test returns None when not configured."""
        mock_config.return_value.load.return_value = {}
        mock_get_cicd.return_value = None

        result = _get_cicd()

        assert result is None


# ==================== Tests for _check_cicd ====================

class TestCheckCicd:
    """Tests for _check_cicd function."""

    @patch('redgit.commands.ci._get_cicd')
    def test_returns_cicd_when_configured(self, mock_get_cicd):
        """Test returns CI/CD integration when configured."""
        mock_cicd = MagicMock()
        mock_get_cicd.return_value = mock_cicd

        result = _check_cicd()

        assert result == mock_cicd

    @patch('redgit.commands.ci.console.print')
    @patch('redgit.commands.ci.get_integrations_by_type')
    @patch('redgit.commands.ci._get_cicd')
    def test_raises_exit_when_not_configured(self, mock_get_cicd, mock_get_integrations, mock_print):
        """Test raises Exit when not configured."""
        mock_get_cicd.return_value = None
        mock_get_integrations.return_value = ["github-actions", "gitlab-ci"]

        with pytest.raises(typer.Exit):
            _check_cicd()

    @patch('redgit.commands.ci.console.print')
    @patch('redgit.commands.ci.get_integrations_by_type')
    @patch('redgit.commands.ci._get_cicd')
    def test_shows_available_integrations(self, mock_get_cicd, mock_get_integrations, mock_print):
        """Test shows available integrations when not configured."""
        mock_get_cicd.return_value = None
        mock_get_integrations.return_value = ["github-actions"]

        with pytest.raises(typer.Exit):
            _check_cicd()

        # Should mention available integration
        calls = [str(c) for c in mock_print.call_args_list]
        assert any("github-actions" in c for c in calls)


# ==================== Tests for _status_icon ====================

class TestStatusIcon:
    """Tests for _status_icon function."""

    def test_success_statuses(self):
        """Test success statuses return green checkmark."""
        assert "[green]" in _status_icon("success")
        assert "[green]" in _status_icon("passed")
        assert "[green]" in _status_icon("completed")

    def test_failed_statuses(self):
        """Test failed statuses return red X."""
        assert "[red]" in _status_icon("failed")
        assert "[red]" in _status_icon("failure")
        assert "[red]" in _status_icon("error")

    def test_running_statuses(self):
        """Test running statuses return yellow circle."""
        assert "[yellow]" in _status_icon("running")
        assert "[yellow]" in _status_icon("in_progress")

    def test_pending_statuses(self):
        """Test pending statuses return blue circle."""
        assert "[blue]" in _status_icon("pending")
        assert "[blue]" in _status_icon("queued")
        assert "[blue]" in _status_icon("waiting")

    def test_cancelled_statuses(self):
        """Test cancelled statuses return dim icon."""
        assert "[dim]" in _status_icon("cancelled")
        assert "[dim]" in _status_icon("canceled")
        assert "[dim]" in _status_icon("skipped")

    def test_unknown_status(self):
        """Test unknown status returns question mark."""
        result = _status_icon("unknown_status")
        assert "[dim]?" in result

    def test_case_insensitive(self):
        """Test status matching is case insensitive."""
        assert "[green]" in _status_icon("SUCCESS")
        assert "[green]" in _status_icon("Success")
        assert "[red]" in _status_icon("FAILED")


# ==================== CLI Integration Tests ====================

class TestCiCLI:
    """CLI integration tests for ci_app."""

    def test_ci_help(self):
        """Test ci --help shows subcommands."""
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(ci_app, ["--help"])

        assert result.exit_code == 0
        assert "status" in result.stdout
        assert "pipelines" in result.stdout
        assert "trigger" in result.stdout

    @patch('redgit.commands.ci._check_cicd')
    def test_status_shows_integration_name(self, mock_check):
        """Test status command shows integration name."""
        from typer.testing import CliRunner

        mock_cicd = MagicMock()
        mock_cicd.name = "GitHub Actions"
        mock_cicd.list_pipelines.return_value = []
        mock_check.return_value = mock_cicd

        runner = CliRunner()
        result = runner.invoke(ci_app, ["status"])

        assert result.exit_code == 0
        assert "GitHub Actions" in result.stdout

    @patch('redgit.commands.ci._check_cicd')
    def test_pipelines_shows_table(self, mock_check):
        """Test pipelines command shows table."""
        from typer.testing import CliRunner
        from redgit.integrations.base import PipelineRun

        mock_cicd = MagicMock()
        mock_cicd.list_pipelines.return_value = [
            PipelineRun(
                id="12345",
                name="Build",
                status="success",
                branch="main",
                duration=120
            )
        ]
        mock_check.return_value = mock_cicd

        runner = CliRunner()
        result = runner.invoke(ci_app, ["pipelines"])

        assert result.exit_code == 0
        assert "12345" in result.stdout or "main" in result.stdout

    @patch('redgit.commands.ci._check_cicd')
    def test_pipelines_empty_list(self, mock_check):
        """Test pipelines command with no pipelines."""
        from typer.testing import CliRunner

        mock_cicd = MagicMock()
        mock_cicd.list_pipelines.return_value = []
        mock_check.return_value = mock_cicd

        runner = CliRunner()
        result = runner.invoke(ci_app, ["pipelines"])

        assert result.exit_code == 0
        assert "No pipelines found" in result.stdout

    @patch('redgit.commands.ci._check_cicd')
    def test_pipelines_with_branch_filter(self, mock_check):
        """Test pipelines command with branch filter."""
        from typer.testing import CliRunner

        mock_cicd = MagicMock()
        mock_cicd.list_pipelines.return_value = []
        mock_check.return_value = mock_cicd

        runner = CliRunner()
        result = runner.invoke(ci_app, ["pipelines", "--branch", "develop"])

        # Should pass branch to list_pipelines
        mock_cicd.list_pipelines.assert_called_with(branch="develop", status=None, limit=10)

    @patch('redgit.commands.ci._check_cicd')
    def test_trigger_calls_cicd(self, mock_check):
        """Test trigger command calls CI/CD."""
        from typer.testing import CliRunner
        from redgit.integrations.base import PipelineRun

        mock_cicd = MagicMock()
        mock_pipeline = PipelineRun(id="99999", name="Build", status="pending")
        mock_cicd.trigger_pipeline.return_value = mock_pipeline
        mock_check.return_value = mock_cicd

        runner = CliRunner()
        result = runner.invoke(ci_app, ["trigger"])

        mock_cicd.trigger_pipeline.assert_called()


# ==================== Tests for status_cmd ====================

class TestStatusCmd:
    """Tests for status_cmd function."""

    @patch('redgit.commands.ci.GitOps')
    @patch('redgit.commands.ci._check_cicd')
    @patch('redgit.commands.ci.console.print')
    def test_shows_connected_status(self, mock_print, mock_check, mock_gitops):
        """Test shows connected status."""
        from redgit.commands.ci import status_cmd

        mock_cicd = MagicMock()
        mock_cicd.name = "GitHub Actions"
        mock_cicd.list_pipelines.return_value = []
        mock_check.return_value = mock_cicd
        mock_gitops.return_value.original_branch = "main"

        status_cmd()

        calls = [str(c) for c in mock_print.call_args_list]
        assert any("Connected" in c for c in calls)

    @patch('redgit.commands.ci.GitOps')
    @patch('redgit.commands.ci._check_cicd')
    @patch('redgit.commands.ci.console.print')
    def test_shows_recent_pipelines(self, mock_print, mock_check, mock_gitops):
        """Test shows recent pipelines."""
        from redgit.commands.ci import status_cmd
        from redgit.integrations.base import PipelineRun

        mock_cicd = MagicMock()
        mock_cicd.name = "GitLab CI"
        mock_cicd.list_pipelines.return_value = [
            PipelineRun(id="build-1", name="Build", status="success", branch="main")
        ]
        mock_check.return_value = mock_cicd
        mock_gitops.return_value.original_branch = "main"

        status_cmd()

        calls = [str(c) for c in mock_print.call_args_list]
        assert any("Recent Pipelines" in c for c in calls)


# ==================== Tests for list_pipelines ====================

class TestListPipelines:
    """Tests for list_pipelines function."""

    @patch('redgit.commands.ci._check_cicd')
    @patch('redgit.commands.ci.console.print')
    def test_uses_limit_option(self, mock_print, mock_check):
        """Test respects limit option."""
        from redgit.commands.ci import list_pipelines

        mock_cicd = MagicMock()
        mock_cicd.list_pipelines.return_value = []
        mock_check.return_value = mock_cicd

        list_pipelines(branch=None, status=None, limit=5)

        mock_cicd.list_pipelines.assert_called_with(branch=None, status=None, limit=5)

    @patch('redgit.commands.ci._check_cicd')
    @patch('redgit.commands.ci.console.print')
    def test_uses_status_filter(self, mock_print, mock_check):
        """Test respects status filter option."""
        from redgit.commands.ci import list_pipelines

        mock_cicd = MagicMock()
        mock_cicd.list_pipelines.return_value = []
        mock_check.return_value = mock_cicd

        list_pipelines(branch=None, status="success", limit=10)

        mock_cicd.list_pipelines.assert_called_with(branch=None, status="success", limit=10)
