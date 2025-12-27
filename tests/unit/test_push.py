"""
Tests for redgit/commands/push.py - Push command and helpers.
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from redgit.commands.push import (
    _get_unpushed_tags,
    _extract_issue_from_branch,
    _is_notification_enabled,
    _send_push_notification,
    _send_pr_notification,
    _send_ci_notification,
    _send_issue_completion_notification,
    _send_quality_failed_notification,
    _save_status_to_config,
    _display_conflict_error,
)


class TestGetUnpushedTags:
    """Tests for _get_unpushed_tags function."""

    def test_returns_empty_list_when_no_tags(self, temp_git_repo, change_cwd):
        """Test returns empty list when no local tags."""
        import os
        os.chdir(temp_git_repo)

        from redgit.core.gitops import GitOps
        gitops = GitOps()

        result = _get_unpushed_tags(gitops)
        assert result == []

    def test_returns_local_tags_when_no_remote(self, temp_git_repo, change_cwd):
        """Test returns local tags when remote doesn't exist."""
        import os
        os.chdir(temp_git_repo)

        from redgit.core.gitops import GitOps
        gitops = GitOps()

        # Create a local tag
        gitops.repo.git.tag("v1.0.0")

        result = _get_unpushed_tags(gitops)
        assert "v1.0.0" in result

    def test_returns_list_type(self, temp_git_repo, change_cwd):
        """Test always returns a list."""
        import os
        os.chdir(temp_git_repo)

        from redgit.core.gitops import GitOps
        gitops = GitOps()

        result = _get_unpushed_tags(gitops)
        assert isinstance(result, list)


class TestExtractIssueFromBranch:
    """Tests for _extract_issue_from_branch function."""

    def test_extracts_issue_from_branch_name(self):
        """Test extracting issue key from branch name."""
        config = {
            "active": {"task_management": "jira"},
            "integrations": {"jira": {"project_key": "PROJ"}}
        }

        result = _extract_issue_from_branch("feature/PROJ-123-add-feature", config)
        assert result == "PROJ-123"

    def test_extracts_issue_case_insensitive(self):
        """Test extraction is case insensitive."""
        config = {
            "active": {"task_management": "jira"},
            "integrations": {"jira": {"project_key": "PROJ"}}
        }

        result = _extract_issue_from_branch("feature/proj-456-fix-bug", config)
        assert result == "PROJ-456"

    def test_returns_none_when_no_task_management(self):
        """Test returns None when no task management configured."""
        config = {"active": {}}

        result = _extract_issue_from_branch("feature/PROJ-123", config)
        assert result is None

    def test_returns_none_when_no_project_key(self):
        """Test returns None when no project key configured."""
        config = {
            "active": {"task_management": "jira"},
            "integrations": {"jira": {}}
        }

        result = _extract_issue_from_branch("feature/PROJ-123", config)
        assert result is None

    def test_returns_none_when_no_match(self):
        """Test returns None when branch doesn't contain issue key."""
        config = {
            "active": {"task_management": "jira"},
            "integrations": {"jira": {"project_key": "PROJ"}}
        }

        result = _extract_issue_from_branch("feature/add-feature", config)
        assert result is None

    def test_handles_different_branch_formats(self):
        """Test handles various branch name formats."""
        config = {
            "active": {"task_management": "jira"},
            "integrations": {"jira": {"project_key": "SCRUM"}}
        }

        # Different formats
        assert _extract_issue_from_branch("SCRUM-123", config) == "SCRUM-123"
        assert _extract_issue_from_branch("feature/SCRUM-123", config) == "SCRUM-123"
        assert _extract_issue_from_branch("bugfix/SCRUM-456-fix", config) == "SCRUM-456"
        assert _extract_issue_from_branch("SCRUM-789-some-work", config) == "SCRUM-789"


class TestIsNotificationEnabled:
    """Tests for _is_notification_enabled function."""

    def test_returns_boolean(self):
        """Test returns a boolean value."""
        with patch('redgit.core.config.ConfigManager') as mock_cm:
            mock_instance = MagicMock()
            mock_instance.is_notification_enabled.return_value = True
            mock_cm.return_value = mock_instance

            result = _is_notification_enabled({}, "push")
            assert isinstance(result, bool)

    def test_returns_true_when_enabled(self):
        """Test returns True when notification is enabled."""
        with patch('redgit.core.config.ConfigManager') as mock_cm:
            mock_instance = MagicMock()
            mock_instance.is_notification_enabled.return_value = True
            mock_cm.return_value = mock_instance

            result = _is_notification_enabled({}, "pr_created")
            assert result is True


class TestSendPushNotification:
    """Tests for _send_push_notification function."""

    def test_sends_message_when_enabled(self):
        """Test sends notification when enabled."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_push_notification({}, "main", ["PROJ-123"])

                mock_notification.send_message.assert_called_once()
                call_arg = mock_notification.send_message.call_args[0][0]
                assert "main" in call_arg
                assert "PROJ-123" in call_arg

    def test_skips_when_disabled(self):
        """Test skips notification when disabled."""
        mock_notification = MagicMock()

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = False
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_push_notification({}, "main", None)

                mock_notification.send_message.assert_not_called()

    def test_handles_no_issues(self):
        """Test handles case with no issues."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_push_notification({}, "feature/test", None)

                mock_notification.send_message.assert_called_once()
                call_arg = mock_notification.send_message.call_args[0][0]
                assert "feature/test" in call_arg

    def test_handles_notification_error(self):
        """Test handles notification sending error gracefully."""
        mock_notification = MagicMock()
        mock_notification.enabled = True
        mock_notification.send_message.side_effect = Exception("Network error")

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                # Should not raise
                _send_push_notification({}, "main", None)


class TestSendPrNotification:
    """Tests for _send_pr_notification function."""

    def test_sends_pr_notification(self):
        """Test sends PR notification with URL."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_pr_notification({}, "feature/test", "https://github.com/pr/1", "PROJ-123")

                mock_notification.send_message.assert_called_once()
                call_arg = mock_notification.send_message.call_args[0][0]
                assert "feature/test" in call_arg
                assert "https://github.com/pr/1" in call_arg
                assert "PROJ-123" in call_arg

    def test_handles_no_issue_key(self):
        """Test handles PR without issue key."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_pr_notification({}, "feature/test", "https://github.com/pr/1", None)

                mock_notification.send_message.assert_called_once()


class TestSendCiNotification:
    """Tests for _send_ci_notification function."""

    def test_sends_success_notification(self):
        """Test sends success notification."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_ci_notification({}, "main", "success", "https://ci.example.com/1")

                mock_notification.send_message.assert_called_once()
                call_arg = mock_notification.send_message.call_args[0][0]
                assert "success" in call_arg.lower() or "completed" in call_arg.lower()

    def test_sends_failure_notification(self):
        """Test sends failure notification."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_ci_notification({}, "main", "failed", None)

                mock_notification.send_message.assert_called_once()
                call_arg = mock_notification.send_message.call_args[0][0]
                assert "failed" in call_arg.lower()

    def test_checks_correct_event(self):
        """Test checks ci_success or ci_failure event."""
        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            with patch('redgit.utils.notifications.get_notification'):
                mock_cm.return_value.is_notification_enabled.return_value = False
                _send_ci_notification({}, "main", "success", None)
                # Verify is_notification_enabled was called with ci_success
                calls = [c[0][0] for c in mock_cm.return_value.is_notification_enabled.call_args_list]
                assert "ci_success" in calls


class TestSendIssueCompletionNotification:
    """Tests for _send_issue_completion_notification function."""

    def test_sends_single_issue_notification(self):
        """Test notification for single issue."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_issue_completion_notification({}, ["PROJ-123"])

                mock_notification.send_message.assert_called_once()
                call_arg = mock_notification.send_message.call_args[0][0]
                assert "PROJ-123" in call_arg

    def test_sends_multiple_issues_notification(self):
        """Test notification for multiple issues."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_issue_completion_notification({}, ["PROJ-1", "PROJ-2", "PROJ-3"])

                mock_notification.send_message.assert_called_once()
                call_arg = mock_notification.send_message.call_args[0][0]
                assert "3" in call_arg
                assert "PROJ-1" in call_arg


class TestSendQualityFailedNotification:
    """Tests for _send_quality_failed_notification function."""

    def test_sends_quality_failed_notification(self):
        """Test sends quality failed notification."""
        mock_notification = MagicMock()
        mock_notification.enabled = True

        with patch('redgit.utils.notifications.ConfigManager') as mock_cm:
            mock_cm.return_value.is_notification_enabled.return_value = True
            with patch('redgit.utils.notifications.get_notification', return_value=mock_notification):
                _send_quality_failed_notification({}, 65, 70)

                mock_notification.send_message.assert_called_once()
                call_arg = mock_notification.send_message.call_args[0][0]
                assert "65" in call_arg
                assert "70" in call_arg


class TestSaveStatusToConfig:
    """Tests for _save_status_to_config function."""

    def test_saves_new_status(self, tmp_path, monkeypatch):
        """Test saves new status to config."""
        config_file = tmp_path / ".redgit" / "config.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("""
integrations:
  jira:
    statuses:
      after_push:
        - Done
""")
        # Change to temp directory so Path(".redgit/config.yaml") resolves there
        monkeypatch.chdir(tmp_path)

        _save_status_to_config("Completed")

        import yaml
        saved = yaml.safe_load(config_file.read_text())
        after_push = saved["integrations"]["jira"]["statuses"]["after_push"]
        assert "Completed" in after_push
        assert "Done" in after_push

    def test_creates_structure_if_missing(self, tmp_path, monkeypatch):
        """Test creates config structure if missing."""
        config_file = tmp_path / ".redgit" / "config.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("project: test\n")

        monkeypatch.chdir(tmp_path)

        _save_status_to_config("Done")

        import yaml
        saved = yaml.safe_load(config_file.read_text())
        assert "integrations" in saved
        assert "jira" in saved["integrations"]
        assert "statuses" in saved["integrations"]["jira"]

    def test_handles_missing_file(self, tmp_path, monkeypatch):
        """Test handles missing config file gracefully."""
        monkeypatch.chdir(tmp_path)

        # Should not raise even without config file
        _save_status_to_config("Done")

    def test_does_not_duplicate_status(self, tmp_path, monkeypatch):
        """Test does not add duplicate status."""
        config_file = tmp_path / ".redgit" / "config.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("""
integrations:
  jira:
    statuses:
      after_push:
        - Done
        - Completed
""")

        monkeypatch.chdir(tmp_path)

        _save_status_to_config("Done")

        import yaml
        saved = yaml.safe_load(config_file.read_text())
        after_push = saved["integrations"]["jira"]["statuses"]["after_push"]
        assert after_push.count("Done") == 1


class TestDisplayConflictError:
    """Tests for _display_conflict_error function."""

    def test_displays_conflict_message(self):
        """Test displays conflict error message."""
        with patch('redgit.commands.push.console.print') as mock_print:
            _display_conflict_error(["file1.py", "file2.py"], "main")

            # Check that key messages are printed
            calls = [str(call) for call in mock_print.call_args_list]
            all_output = " ".join(calls)
            assert "Conflict" in all_output or "conflict" in all_output
            assert "file1.py" in all_output
            assert "file2.py" in all_output

    def test_handles_empty_conflict_list(self):
        """Test handles empty conflict file list."""
        with patch('redgit.commands.push.console.print') as mock_print:
            _display_conflict_error([], "main")

            # Should still display conflict message
            calls = [str(call) for call in mock_print.call_args_list]
            all_output = " ".join(calls)
            assert "Conflict" in all_output or "conflict" in all_output

    def test_shows_resolution_options(self):
        """Test shows resolution options."""
        with patch('redgit.commands.push.console.print') as mock_print:
            _display_conflict_error(["file.py"], "feature/test")

            calls = [str(call) for call in mock_print.call_args_list]
            all_output = " ".join(calls)
            assert "git pull" in all_output or "no-pull" in all_output or "force" in all_output


class TestPushCmdIntegration:
    """Integration tests for push_cmd using CLI runner."""

    def test_push_help(self):
        """Test push --help shows options."""
        from typer.testing import CliRunner
        from redgit.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["push", "--help"])

        assert result.exit_code == 0
        assert "--complete" in result.stdout or "complete" in result.stdout
        assert "--pr" in result.stdout
        assert "--force" in result.stdout

    def test_push_requires_git_repo(self, tmp_path):
        """Test push fails outside git repo."""
        import os
        original_cwd = os.getcwd()

        try:
            os.chdir(tmp_path)

            from typer.testing import CliRunner
            from redgit.cli import app

            runner = CliRunner()
            result = runner.invoke(app, ["push"])

            # Should fail with non-zero exit code
            assert result.exit_code != 0
            # Error could be in stdout, exception, or output
            output = (result.stdout or "") + str(result.exception or "")
            assert "git" in output.lower() or "repository" in output.lower()
        finally:
            os.chdir(original_cwd)


class TestCompleteIssuesHelpers:
    """Tests for issue completion helper functions."""

    def test_complete_issues_calls_task_mgmt(self):
        """Test _complete_issues calls task management."""
        from redgit.commands.push import _complete_issues

        mock_task_mgmt = MagicMock()
        mock_task_mgmt.transition_strategy = "auto"
        mock_task_mgmt.get_issue.return_value = MagicMock(status="In Progress")
        mock_task_mgmt.transition_issue.return_value = True

        with patch('redgit.commands.push.console.print'):
            _complete_issues(["PROJ-123"], mock_task_mgmt)

        mock_task_mgmt.transition_issue.assert_called()

    def test_complete_issues_handles_error(self):
        """Test _complete_issues handles errors gracefully."""
        from redgit.commands.push import _complete_issues

        mock_task_mgmt = MagicMock()
        mock_task_mgmt.transition_strategy = "auto"
        mock_task_mgmt.get_issue.side_effect = Exception("API error")

        with patch('redgit.commands.push.console.print'):
            # Should not raise
            _complete_issues(["PROJ-123"], mock_task_mgmt)

    def test_complete_issues_uses_ask_strategy(self):
        """Test _complete_issues uses interactive mode when strategy is 'ask'."""
        from redgit.commands.push import _complete_issues

        mock_task_mgmt = MagicMock()
        mock_task_mgmt.transition_strategy = "ask"

        with patch('redgit.commands.push._complete_issues_interactive') as mock_interactive:
            _complete_issues(["PROJ-123"], mock_task_mgmt)
            mock_interactive.assert_called_once_with(["PROJ-123"], mock_task_mgmt)


# ==================== Tests for _complete_issues_auto ====================

class TestCompleteIssuesAuto:
    """Tests for _complete_issues_auto function."""

    def test_transitions_issue_successfully(self):
        """Test successfully transitions issue."""
        from redgit.commands.push import _complete_issues_auto

        mock_task_mgmt = MagicMock()
        mock_task_mgmt.get_issue.return_value = MagicMock(status="In Progress")
        mock_task_mgmt.transition_issue.return_value = True

        with patch('redgit.commands.push.console.print'):
            _complete_issues_auto(["PROJ-123"], mock_task_mgmt)

        mock_task_mgmt.transition_issue.assert_called_with("PROJ-123", "after_push")

    def test_handles_transition_failure(self):
        """Test handles transition failure by prompting user."""
        from redgit.commands.push import _complete_issues_auto

        mock_task_mgmt = MagicMock()
        mock_task_mgmt.get_issue.return_value = MagicMock(status="Open")
        mock_task_mgmt.transition_issue.return_value = False
        mock_task_mgmt.get_available_transitions.return_value = []

        with patch('redgit.commands.push.console.print'):
            _complete_issues_auto(["PROJ-123"], mock_task_mgmt)

        # Should have tried to get available transitions
        mock_task_mgmt.get_available_transitions.assert_called_with("PROJ-123")

    def test_uses_saved_status_for_subsequent_issues(self):
        """Test uses previously selected status for remaining issues."""
        from redgit.commands.push import _complete_issues_auto

        mock_task_mgmt = MagicMock()
        mock_task_mgmt.get_issue.return_value = MagicMock(status="Open")
        mock_task_mgmt.transition_issue.side_effect = [True, True]

        with patch('redgit.commands.push.console.print'):
            _complete_issues_auto(["PROJ-1", "PROJ-2"], mock_task_mgmt)

        # Both issues should have been processed
        assert mock_task_mgmt.transition_issue.call_count == 2


# ==================== Tests for _complete_issues_interactive ====================

class TestCompleteIssuesInteractive:
    """Tests for _complete_issues_interactive function."""

    @patch('rich.prompt.Prompt.ask')
    def test_shows_available_transitions(self, mock_prompt_ask):
        """Test shows available transitions to user."""
        from redgit.commands.push import _complete_issues_interactive

        mock_prompt_ask.return_value = "0"  # Skip
        mock_task_mgmt = MagicMock()
        mock_task_mgmt.get_issue.return_value = MagicMock(status="Open", summary="Test issue")
        mock_task_mgmt.get_available_transitions.return_value = [
            {"id": "1", "to": "In Progress"},
            {"id": "2", "to": "Done"}
        ]

        with patch('redgit.commands.push.console.print'):
            _complete_issues_interactive(["PROJ-123"], mock_task_mgmt)

        mock_task_mgmt.get_available_transitions.assert_called()

    @patch('rich.prompt.Prompt.ask')
    def test_transitions_selected_status(self, mock_prompt_ask):
        """Test transitions to user-selected status."""
        from redgit.commands.push import _complete_issues_interactive

        mock_prompt_ask.return_value = "1"  # First option
        mock_task_mgmt = MagicMock()
        mock_task_mgmt.get_issue.return_value = MagicMock(status="Open", summary="Test")
        mock_task_mgmt.get_available_transitions.return_value = [
            {"id": "10", "to": "Done"}
        ]
        mock_task_mgmt.transition_issue_by_id.return_value = True

        with patch('redgit.commands.push.console.print'):
            _complete_issues_interactive(["PROJ-123"], mock_task_mgmt)

        mock_task_mgmt.transition_issue_by_id.assert_called_with("PROJ-123", "10")

    @patch('rich.prompt.Prompt.ask')
    def test_skip_option(self, mock_prompt_ask):
        """Test user can skip transition."""
        from redgit.commands.push import _complete_issues_interactive

        mock_prompt_ask.return_value = "0"  # Skip
        mock_task_mgmt = MagicMock()
        mock_task_mgmt.get_issue.return_value = MagicMock(status="Open", summary="Test")
        mock_task_mgmt.get_available_transitions.return_value = [
            {"id": "1", "to": "Done"}
        ]

        with patch('redgit.commands.push.console.print'):
            _complete_issues_interactive(["PROJ-123"], mock_task_mgmt)

        # Should not have transitioned
        mock_task_mgmt.transition_issue_by_id.assert_not_called()


# ==================== Tests for _push_current_branch ====================

class TestPushCurrentBranch:
    """Tests for _push_current_branch function."""

    @patch('os.system')
    @patch('redgit.commands.push._get_unpushed_tags')
    @patch('redgit.commands.push._sync_with_remote')
    @patch('redgit.commands.push.get_task_management')
    @patch('redgit.commands.push.get_code_hosting')
    @patch('redgit.commands.push.get_cicd')
    def test_pushes_branch_successfully(
        self, mock_cicd, mock_hosting, mock_task,
        mock_sync, mock_tags, mock_system
    ):
        """Test pushes branch successfully."""
        from redgit.commands.push import _push_current_branch

        mock_sync.return_value = (True, [])
        mock_tags.return_value = []
        mock_system.return_value = 0
        mock_task.return_value = None
        mock_hosting.return_value = None
        mock_cicd.return_value = None

        mock_gitops = MagicMock()
        mock_gitops.original_branch = "main"
        mock_gitops.repo.git.status.return_value = "Your branch is ahead"

        with patch('redgit.commands.push.console.print'):
            with patch('redgit.commands.push._send_push_notification'):
                _push_current_branch(
                    mock_gitops, {}, complete=False, create_pr=False,
                    issue_key=None, push_tags=False
                )

        mock_system.assert_called()

    @patch('os.system')
    @patch('redgit.commands.push._sync_with_remote')
    def test_aborts_on_conflict(self, mock_sync, mock_system):
        """Test aborts push when conflicts detected."""
        from redgit.commands.push import _push_current_branch
        import typer

        mock_sync.return_value = (False, ["conflict.py"])

        mock_gitops = MagicMock()
        mock_gitops.original_branch = "main"
        mock_gitops.repo.git.status.return_value = "Your branch is ahead"

        with patch('redgit.commands.push.console.print'):
            with patch('redgit.commands.push._display_conflict_error'):
                with pytest.raises(typer.Exit):
                    _push_current_branch(
                        mock_gitops, {}, complete=False, create_pr=False,
                        issue_key=None, no_pull=False, force=False
                    )

    @patch('os.system')
    @patch('redgit.commands.push._get_unpushed_tags')
    @patch('redgit.commands.push._sync_with_remote')
    @patch('redgit.commands.push.get_task_management')
    @patch('redgit.commands.push.get_code_hosting')
    @patch('redgit.commands.push.get_cicd')
    def test_pushes_tags_when_enabled(
        self, mock_cicd, mock_hosting, mock_task,
        mock_sync, mock_tags, mock_system
    ):
        """Test pushes tags when enabled."""
        from redgit.commands.push import _push_current_branch

        mock_sync.return_value = (True, [])
        mock_tags.return_value = ["v1.0.0", "v1.1.0"]
        mock_system.return_value = 0
        mock_task.return_value = None
        mock_hosting.return_value = None
        mock_cicd.return_value = None

        mock_gitops = MagicMock()
        mock_gitops.original_branch = "main"
        mock_gitops.repo.git.status.return_value = "Your branch is ahead"

        with patch('redgit.commands.push.console.print'):
            with patch('redgit.commands.push._send_push_notification'):
                _push_current_branch(
                    mock_gitops, {}, complete=False, create_pr=False,
                    issue_key=None, push_tags=True
                )

        # Should have called git push --tags
        assert any("--tags" in str(call) for call in mock_system.call_args_list)


# ==================== Tests for _sync_with_remote ====================

class TestSyncWithRemote:
    """Tests for _sync_with_remote function."""

    def test_returns_success_when_no_remote(self):
        """Test returns success when remote branch doesn't exist."""
        from redgit.commands.push import _sync_with_remote

        mock_gitops = MagicMock()
        mock_gitops.repo.git.ls_remote.return_value = ""

        with patch('redgit.commands.push.console.print'):
            success, conflicts = _sync_with_remote(mock_gitops, "main")

        assert success is True
        assert conflicts == []

    def test_returns_success_when_up_to_date(self):
        """Test returns success when already up to date."""
        from redgit.commands.push import _sync_with_remote

        mock_gitops = MagicMock()
        mock_gitops.repo.git.ls_remote.return_value = "abc123\trefs/heads/main"
        mock_gitops.repo.git.rev_list.return_value = "0"

        with patch('redgit.commands.push.console.print'):
            success, conflicts = _sync_with_remote(mock_gitops, "main")

        assert success is True
        assert conflicts == []

    def test_merges_remote_changes(self):
        """Test merges remote changes successfully."""
        from redgit.commands.push import _sync_with_remote

        mock_gitops = MagicMock()
        mock_gitops.repo.git.ls_remote.return_value = "abc123\trefs/heads/main"
        mock_gitops.repo.git.rev_list.return_value = "5"
        mock_gitops.repo.git.merge.return_value = None
        mock_gitops.repo.git.commit.return_value = None

        with patch('redgit.commands.push.console.print'):
            success, conflicts = _sync_with_remote(mock_gitops, "main")

        assert success is True
        mock_gitops.repo.git.merge.assert_called()

    def test_detects_conflicts(self):
        """Test detects merge conflicts."""
        from redgit.commands.push import _sync_with_remote
        import git

        mock_gitops = MagicMock()
        mock_gitops.repo.git.ls_remote.return_value = "abc123\trefs/heads/main"
        mock_gitops.repo.git.rev_list.return_value = "3"
        mock_gitops.repo.git.merge.side_effect = git.GitCommandError("merge", 1)
        mock_gitops.repo.git.status.return_value = "UU conflict.py\nUU another.py"

        with patch('redgit.commands.push.console.print'):
            success, conflicts = _sync_with_remote(mock_gitops, "main")

        assert success is False
        assert "conflict.py" in conflicts


# ==================== Tests for _trigger_cicd_pipeline ====================

class TestTriggerCicdPipeline:
    """Tests for _trigger_cicd_pipeline function."""

    def test_triggers_pipeline(self):
        """Test triggers CI/CD pipeline."""
        from redgit.commands.push import _trigger_cicd_pipeline

        mock_cicd = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.name = "test-pipeline"
        mock_pipeline.url = "https://ci.example.com/1"
        mock_cicd.trigger_pipeline.return_value = mock_pipeline

        with patch('redgit.commands.push.console.print'):
            _trigger_cicd_pipeline(mock_cicd, {}, "main", wait=False)

        mock_cicd.trigger_pipeline.assert_called_with(branch="main")

    def test_handles_pipeline_trigger_failure(self):
        """Test handles pipeline trigger failure."""
        from redgit.commands.push import _trigger_cicd_pipeline

        mock_cicd = MagicMock()
        mock_cicd.trigger_pipeline.return_value = None

        with patch('redgit.commands.push.console.print'):
            # Should not raise
            _trigger_cicd_pipeline(mock_cicd, {}, "main", wait=False)

    def test_waits_for_completion(self):
        """Test waits for pipeline completion when requested."""
        from redgit.commands.push import _trigger_cicd_pipeline
        import time

        mock_cicd = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.name = "test"
        mock_pipeline.url = None
        mock_cicd.trigger_pipeline.return_value = mock_pipeline

        mock_status = MagicMock()
        mock_status.status = "success"
        mock_cicd.get_pipeline_status.return_value = mock_status

        with patch('redgit.commands.push.console.print'):
            with patch('redgit.commands.push._send_ci_notification'):
                with patch('time.sleep'):
                    _trigger_cicd_pipeline(mock_cicd, {}, "main", wait=True)

        mock_cicd.get_pipeline_status.assert_called()


# ==================== Tests for _run_quality_check ====================

class TestRunQualityCheck:
    """Tests for _run_quality_check function."""

    def test_returns_true_when_disabled(self):
        """Test returns True when quality checks are disabled."""
        from redgit.commands.push import _run_quality_check

        mock_config_manager = MagicMock()
        mock_config_manager.is_quality_enabled.return_value = False

        result = _run_quality_check(mock_config_manager, {})

        assert result is True

    @patch('redgit.commands.push.get_code_quality')
    def test_uses_integration_when_available(self, mock_get_quality):
        """Test uses code quality integration when available."""
        from redgit.commands.push import _run_quality_check

        mock_quality = MagicMock()
        mock_status = MagicMock()
        mock_status.status = "passed"
        mock_status.coverage = 80
        mock_quality.get_quality_status.return_value = mock_status
        mock_get_quality.return_value = mock_quality

        mock_config_manager = MagicMock()
        mock_config_manager.is_quality_enabled.return_value = True
        mock_config_manager.get_quality_threshold.return_value = 70
        mock_config_manager.get_quality_config.return_value = {"fail_on_security": True}

        with patch('redgit.commands.push.console.print'):
            result = _run_quality_check(mock_config_manager, {})

        assert result is True

    @patch('redgit.commands.push.get_code_quality')
    def test_fails_on_quality_gate_failure(self, mock_get_quality):
        """Test fails when quality gate fails."""
        from redgit.commands.push import _run_quality_check

        mock_quality = MagicMock()
        mock_status = MagicMock()
        mock_status.status = "failed"
        mock_status.quality_gate_status = "ERROR"
        mock_quality.get_quality_status.return_value = mock_status
        mock_quality.name = "SonarQube"
        mock_get_quality.return_value = mock_quality

        mock_config_manager = MagicMock()
        mock_config_manager.is_quality_enabled.return_value = True
        mock_config_manager.get_quality_threshold.return_value = 70
        mock_config_manager.get_quality_config.return_value = {"fail_on_security": True}

        with patch('redgit.commands.push.console.print'):
            with patch('redgit.commands.push._send_quality_failed_notification'):
                result = _run_quality_check(mock_config_manager, {})

        assert result is False


# ==================== Tests for _push_merge_request_strategy ====================

class TestPushMergeRequestStrategy:
    """Tests for _push_merge_request_strategy function."""

    def test_pushes_branches_to_remote(self):
        """Test pushes branches to remote."""
        from redgit.commands.push import _push_merge_request_strategy

        mock_gitops = MagicMock()
        mock_gitops.repo.git.push.return_value = None

        branches = [
            {"branch": "feature/test-1", "issue_key": "PROJ-1"},
            {"branch": "feature/test-2", "issue_key": "PROJ-2"}
        ]

        with patch('redgit.commands.push.console.print'):
            with patch('redgit.commands.push._send_push_notification'):
                _push_merge_request_strategy(
                    branches, mock_gitops, None, None,
                    "main", create_pr=False, complete=False, no_pull=True
                )

        assert mock_gitops.repo.git.push.call_count == 2

    def test_creates_prs_when_requested(self):
        """Test creates PRs when requested and code hosting available."""
        from redgit.commands.push import _push_merge_request_strategy

        mock_gitops = MagicMock()
        mock_code_hosting = MagicMock()
        mock_code_hosting.enabled = True
        mock_code_hosting.create_pull_request.return_value = "https://github.com/pr/1"

        branches = [{"branch": "feature/test", "issue_key": "PROJ-1"}]

        with patch('redgit.commands.push.console.print'):
            with patch('redgit.commands.push._send_push_notification'):
                with patch('redgit.commands.push._send_pr_notification'):
                    _push_merge_request_strategy(
                        branches, mock_gitops, None, mock_code_hosting,
                        "main", create_pr=True, complete=False, no_pull=True
                    )

        mock_code_hosting.create_pull_request.assert_called_once()

    def test_handles_push_error(self):
        """Test handles push error gracefully."""
        from redgit.commands.push import _push_merge_request_strategy

        mock_gitops = MagicMock()
        mock_gitops.repo.git.push.side_effect = Exception("Push failed")

        branches = [{"branch": "feature/test", "issue_key": "PROJ-1"}]

        with patch('redgit.commands.push.console.print'):
            # Should not raise
            _push_merge_request_strategy(
                branches, mock_gitops, None, None,
                "main", create_pr=False, complete=False, no_pull=True
            )


# ==================== Tests for _push_local_merge_strategy ====================

class TestPushLocalMergeStrategy:
    """Tests for _push_local_merge_strategy function."""

    def test_merges_branches_locally(self):
        """Test merges branches into base branch."""
        from redgit.commands.push import _push_local_merge_strategy

        mock_gitops = MagicMock()

        branches = [
            {"branch": "feature/test-1", "issue_key": "PROJ-1"},
        ]

        with patch('redgit.commands.push.console.print'):
            _push_local_merge_strategy(
                branches, mock_gitops, None,
                "main", complete=False
            )

        mock_gitops.repo.git.checkout.assert_called_with("main")
        mock_gitops.repo.git.merge.assert_called()

    def test_deletes_merged_branches(self):
        """Test deletes merged branches after merge."""
        from redgit.commands.push import _push_local_merge_strategy

        mock_gitops = MagicMock()

        branches = [{"branch": "feature/test", "issue_key": None}]

        with patch('redgit.commands.push.console.print'):
            _push_local_merge_strategy(
                branches, mock_gitops, None,
                "main", complete=False
            )

        mock_gitops.repo.git.branch.assert_called_with("-d", "feature/test")

    def test_pushes_base_branch_after_merge(self):
        """Test pushes base branch after merging."""
        from redgit.commands.push import _push_local_merge_strategy

        mock_gitops = MagicMock()

        branches = [{"branch": "feature/test", "issue_key": None}]

        with patch('redgit.commands.push.console.print'):
            _push_local_merge_strategy(
                branches, mock_gitops, None,
                "main", complete=False
            )

        mock_gitops.repo.git.push.assert_called_with("origin", "main")

    def test_completes_issues_when_enabled(self):
        """Test completes issues when task management enabled."""
        from redgit.commands.push import _push_local_merge_strategy

        mock_gitops = MagicMock()
        mock_task_mgmt = MagicMock()
        mock_task_mgmt.enabled = True

        branches = [{"branch": "feature/test", "issue_key": "PROJ-123"}]

        with patch('redgit.commands.push.console.print'):
            with patch('redgit.commands.push._complete_issues') as mock_complete:
                _push_local_merge_strategy(
                    branches, mock_gitops, mock_task_mgmt,
                    "main", complete=True
                )

        mock_complete.assert_called_once()


# ==================== Tests for push_cmd CLI ====================

class TestPushCmdCLI:
    """CLI tests for push_cmd."""

    @patch('redgit.commands.push.StateManager')
    @patch('redgit.commands.push.ConfigManager')
    @patch('redgit.commands.push.GitOps')
    def test_push_without_session(self, mock_gitops, mock_config, mock_state):
        """Test push without active session pushes current branch."""
        from typer.testing import CliRunner
        from redgit.commands.push import push_cmd
        import typer

        mock_config.return_value.load.return_value = {}
        mock_config.return_value.is_quality_enabled.return_value = False
        mock_state.return_value.get_session.return_value = None
        mock_gitops.return_value.original_branch = "main"
        mock_gitops.return_value.repo.git.status.return_value = ""

        test_app = typer.Typer()
        test_app.command()(push_cmd)

        runner = CliRunner()
        result = runner.invoke(test_app, ["--skip-quality"])

        # Should attempt to push current branch (might fail without remote)
        assert result.exit_code == 0 or "No commits" in result.output or "Push" in result.output

    @patch('redgit.commands.push._run_quality_check')
    @patch('redgit.commands.push.StateManager')
    @patch('redgit.commands.push.ConfigManager')
    @patch('redgit.commands.push.GitOps')
    def test_push_fails_quality_check(self, mock_gitops, mock_config, mock_state, mock_quality):
        """Test push fails when quality check fails."""
        from typer.testing import CliRunner
        from redgit.commands.push import push_cmd
        import typer

        mock_config.return_value.load.return_value = {}
        mock_quality.return_value = False  # Quality check fails

        test_app = typer.Typer()
        test_app.command()(push_cmd)

        runner = CliRunner()
        result = runner.invoke(test_app, [])

        assert result.exit_code == 1
