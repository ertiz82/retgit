"""Tests for redgit/commands/quality.py - Quality analysis command."""

import pytest
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from redgit.commands.quality import (
    _find_linter,
    _get_changed_files,
    _get_error_severity,
    _run_linter,
    _merge_results,
    _load_prompt_template,
    _get_diff,
    _get_main_branch,
    _analyze_with_ai,
    _parse_quality_response,
    _severity_color,
    SEVERITY_MAP,
    LINTERS,
)


# ==================== Tests for _find_linter ====================

class TestFindLinter:
    """Tests for _find_linter function."""

    @patch('shutil.which')
    def test_finds_ruff_first(self, mock_which):
        """Test prefers ruff over flake8."""
        mock_which.side_effect = lambda x: x if x == "ruff" else None

        result = _find_linter()

        assert result == "ruff"

    @patch('shutil.which')
    def test_falls_back_to_flake8(self, mock_which):
        """Test falls back to flake8 when ruff not found."""
        mock_which.side_effect = lambda x: x if x == "flake8" else None

        result = _find_linter()

        assert result == "flake8"

    @patch('shutil.which')
    def test_returns_none_when_no_linter(self, mock_which):
        """Test returns None when no linter installed."""
        mock_which.return_value = None

        result = _find_linter()

        assert result is None


# ==================== Tests for _get_changed_files ====================

class TestGetChangedFiles:
    """Tests for _get_changed_files function."""

    @patch('subprocess.run')
    def test_gets_staged_files(self, mock_run):
        """Test gets files from staged changes."""
        mock_run.return_value = MagicMock(stdout="src/main.py\nsrc/test.py\n")

        with patch('pathlib.Path.exists', return_value=True):
            result = _get_changed_files()

        assert "src/main.py" in result
        assert "src/test.py" in result

    @patch('subprocess.run')
    def test_filters_python_files(self, mock_run):
        """Test filters to Python files only."""
        mock_run.return_value = MagicMock(stdout="main.py\nstyle.css\napp.js\n")

        with patch('pathlib.Path.exists', return_value=True):
            result = _get_changed_files(python_only=True)

        assert result == ["main.py"]

    @patch('subprocess.run')
    def test_returns_all_files_when_not_python_only(self, mock_run):
        """Test returns all files when python_only=False."""
        mock_run.return_value = MagicMock(stdout="main.py\nstyle.css\n")

        with patch('pathlib.Path.exists', return_value=True):
            result = _get_changed_files(python_only=False)

        assert len(result) == 2

    @patch('subprocess.run')
    def test_uses_commit_diff(self, mock_run):
        """Test uses commit diff when commit specified."""
        mock_run.return_value = MagicMock(stdout="")

        _get_changed_files(commit="abc123")

        call_args = mock_run.call_args[0][0]
        assert "abc123~1..abc123" in " ".join(call_args)

    @patch('subprocess.run')
    def test_filters_non_existent_files(self, mock_run):
        """Test filters out non-existent files."""
        mock_run.return_value = MagicMock(stdout="exists.py\ndeleted.py\n")

        def exists_mock(path):
            return "exists" in str(path)

        with patch.object(Path, 'exists', exists_mock):
            result = _get_changed_files()

        assert "exists.py" in result
        assert "deleted.py" not in result

    def test_returns_empty_on_exception(self):
        """Test returns empty list on exception."""
        with patch('subprocess.run', side_effect=Exception("Git error")):
            result = _get_changed_files()

        assert result == []


# ==================== Tests for _get_error_severity ====================

class TestGetErrorSeverity:
    """Tests for _get_error_severity function."""

    def test_security_is_critical(self):
        """Test S (bandit) codes are critical."""
        assert _get_error_severity("S101") == "critical"
        assert _get_error_severity("S501") == "critical"

    def test_bugbear_is_high(self):
        """Test B codes are high severity."""
        assert _get_error_severity("B001") == "high"
        assert _get_error_severity("B950") == "high"

    def test_runtime_errors_are_high(self):
        """Test E9xx codes are high severity."""
        assert _get_error_severity("E901") == "high"
        assert _get_error_severity("E999") == "high"

    def test_pyflakes_is_high(self):
        """Test F codes are high severity."""
        assert _get_error_severity("F401") == "high"
        assert _get_error_severity("F821") == "high"

    def test_pep8_errors_are_medium(self):
        """Test E codes (non-E9) are medium severity."""
        assert _get_error_severity("E101") == "medium"
        assert _get_error_severity("E501") == "medium"

    def test_warnings_are_medium(self):
        """Test W codes are medium severity."""
        assert _get_error_severity("W291") == "medium"
        assert _get_error_severity("W503") == "medium"

    def test_style_codes_are_low(self):
        """Test style codes (I, N, D) are low severity."""
        assert _get_error_severity("I001") == "low"
        assert _get_error_severity("N801") == "low"
        assert _get_error_severity("D100") == "low"

    def test_unknown_codes_are_low(self):
        """Test unknown codes default to low severity."""
        assert _get_error_severity("X999") == "low"
        assert _get_error_severity("Z001") == "low"  # Z is not mapped


# ==================== Tests for _run_linter ====================

class TestRunLinter:
    """Tests for _run_linter function."""

    def test_returns_empty_for_no_files(self):
        """Test returns empty list for no files."""
        issues, linter = _run_linter([])

        assert issues == []
        assert linter == ""

    @patch('redgit.commands.quality._find_linter')
    def test_returns_empty_when_no_linter(self, mock_find_linter):
        """Test returns empty when no linter available."""
        mock_find_linter.return_value = None

        issues, linter = _run_linter(["test.py"])

        assert issues == []
        assert linter == ""

    @patch('subprocess.run')
    @patch('redgit.commands.quality._find_linter')
    def test_runs_ruff_with_json_output(self, mock_find_linter, mock_run):
        """Test runs ruff with JSON output."""
        mock_find_linter.return_value = "ruff"
        mock_run.return_value = MagicMock(stdout=json.dumps([
            {
                "code": "F401",
                "message": "Unused import",
                "filename": "test.py",
                "location": {"row": 1, "column": 1}
            }
        ]))

        issues, linter = _run_linter(["test.py"])

        assert linter == "ruff"
        assert len(issues) == 1
        assert issues[0]["severity"] == "high"
        assert "F401" in issues[0]["description"]

    @patch('subprocess.run')
    @patch('redgit.commands.quality._find_linter')
    def test_runs_flake8_with_parseable_output(self, mock_find_linter, mock_run):
        """Test runs flake8 with parseable output."""
        mock_find_linter.return_value = "flake8"
        mock_run.return_value = MagicMock(stdout="test.py:10:1:E501:Line too long")

        issues, linter = _run_linter(["test.py"])

        assert linter == "flake8"
        assert len(issues) == 1
        assert issues[0]["line"] == 10

    @patch('subprocess.run')
    @patch('redgit.commands.quality._find_linter')
    def test_handles_empty_linter_output(self, mock_find_linter, mock_run):
        """Test handles empty linter output."""
        mock_find_linter.return_value = "ruff"
        mock_run.return_value = MagicMock(stdout="")

        issues, linter = _run_linter(["test.py"])

        assert issues == []

    @patch('subprocess.run')
    @patch('redgit.commands.quality._find_linter')
    def test_handles_linter_exception(self, mock_find_linter, mock_run):
        """Test handles linter exception gracefully."""
        mock_find_linter.return_value = "ruff"
        mock_run.side_effect = Exception("Linter crashed")

        issues, linter = _run_linter(["test.py"])

        assert issues == []


# ==================== Tests for _merge_results ====================

class TestMergeResults:
    """Tests for _merge_results function."""

    @patch('redgit.commands.quality.ConfigManager')
    def test_combines_ai_and_linter_issues(self, mock_config):
        """Test combines AI and linter issues."""
        mock_config.return_value.get_quality_threshold.return_value = 70

        ai_result = {
            "score": 80,
            "decision": "approve",
            "summary": "Good code",
            "issues": [{"file": "a.py", "line": 1, "severity": "medium"}]
        }
        linter_issues = [{"file": "b.py", "line": 2, "severity": "low"}]

        result = _merge_results(ai_result, linter_issues, "ruff")

        assert len(result["issues"]) == 2

    @patch('redgit.commands.quality.ConfigManager')
    def test_avoids_duplicate_issues(self, mock_config):
        """Test avoids duplicate issues at same location."""
        mock_config.return_value.get_quality_threshold.return_value = 70

        ai_result = {
            "score": 80,
            "issues": [{"file": "a.py", "line": 1, "severity": "medium"}]
        }
        linter_issues = [{"file": "a.py", "line": 1, "severity": "medium"}]

        result = _merge_results(ai_result, linter_issues, "ruff")

        assert len(result["issues"]) == 1  # Not duplicated

    @patch('redgit.commands.quality.ConfigManager')
    def test_deducts_points_for_critical(self, mock_config):
        """Test deducts 20 points per critical issue."""
        mock_config.return_value.get_quality_threshold.return_value = 70

        ai_result = {"score": 100, "issues": []}
        linter_issues = [{"severity": "critical"}]

        result = _merge_results(ai_result, linter_issues, "ruff")

        assert result["score"] == 80  # 100 - 20

    @patch('redgit.commands.quality.ConfigManager')
    def test_rejects_with_critical_issues(self, mock_config):
        """Test sets decision to reject with critical issues."""
        mock_config.return_value.get_quality_threshold.return_value = 70

        ai_result = {"score": 100, "decision": "approve", "issues": []}
        linter_issues = [{"severity": "critical"}]

        result = _merge_results(ai_result, linter_issues, "ruff")

        assert result["decision"] == "reject"

    @patch('redgit.commands.quality.ConfigManager')
    def test_penalty_capped_at_50(self, mock_config):
        """Test penalty is capped at 50 points."""
        mock_config.return_value.get_quality_threshold.return_value = 70

        ai_result = {"score": 100, "issues": []}
        linter_issues = [{"severity": "critical"} for _ in range(10)]  # 200 points

        result = _merge_results(ai_result, linter_issues, "ruff")

        assert result["score"] == 50  # 100 - 50 (capped)


# ==================== Tests for _load_prompt_template ====================

class TestLoadPromptTemplate:
    """Tests for _load_prompt_template function."""

    @patch('redgit.commands.quality.USER_PROMPT_PATH')
    @patch('redgit.commands.quality.DEFAULT_PROMPT_PATH')
    def test_prefers_user_template(self, mock_default, mock_user):
        """Test prefers user's custom template."""
        mock_user.exists.return_value = True
        mock_user.read_text.return_value = "Custom prompt"
        mock_default.exists.return_value = True

        result = _load_prompt_template()

        assert result == "Custom prompt"

    @patch('redgit.commands.quality.USER_PROMPT_PATH')
    @patch('redgit.commands.quality.DEFAULT_PROMPT_PATH')
    def test_falls_back_to_default(self, mock_default, mock_user):
        """Test falls back to default template."""
        mock_user.exists.return_value = False
        mock_default.exists.return_value = True
        mock_default.read_text.return_value = "Default prompt"

        result = _load_prompt_template()

        assert result == "Default prompt"

    @patch('redgit.commands.quality.USER_PROMPT_PATH')
    @patch('redgit.commands.quality.DEFAULT_PROMPT_PATH')
    def test_falls_back_to_inline(self, mock_default, mock_user):
        """Test falls back to inline prompt when no files exist."""
        mock_user.exists.return_value = False
        mock_default.exists.return_value = False

        result = _load_prompt_template()

        assert "{{DIFF}}" in result
        assert "score" in result


# ==================== Tests for _get_diff ====================

class TestGetDiff:
    """Tests for _get_diff function."""

    @patch('subprocess.run')
    def test_gets_staged_diff_by_default(self, mock_run):
        """Test gets staged diff by default."""
        mock_run.return_value = MagicMock(stdout="+ new code")

        result = _get_diff()

        call_args = mock_run.call_args_list[0][0][0]
        assert "--staged" in call_args

    @patch('subprocess.run')
    def test_gets_commit_diff(self, mock_run):
        """Test gets diff for specific commit."""
        mock_run.return_value = MagicMock(stdout="+ commit changes")

        _get_diff(commit="abc123")

        call_args = mock_run.call_args[0][0]
        assert "abc123~1..abc123" in " ".join(call_args)

    @patch('subprocess.run')
    def test_gets_branch_diff(self, mock_run):
        """Test gets diff for branch comparison."""
        mock_run.return_value = MagicMock(returncode=0, stdout="+ branch changes")

        _get_diff(branch="feature/test")

        # Should compare with main branch
        call_args = mock_run.call_args_list[-1][0][0]
        assert "feature/test" in " ".join(call_args)

    @patch('subprocess.run')
    def test_gets_file_diff(self, mock_run):
        """Test gets diff for specific file."""
        mock_run.return_value = MagicMock(stdout="+ file changes")

        _get_diff(file="test.py")

        call_args = mock_run.call_args[0][0]
        assert "test.py" in call_args

    @patch('subprocess.run')
    def test_falls_back_to_unstaged(self, mock_run):
        """Test falls back to unstaged diff when no staged changes."""
        mock_run.side_effect = [
            MagicMock(stdout=""),  # No staged
            MagicMock(stdout="+ unstaged changes")  # Unstaged
        ]

        result = _get_diff()

        assert result == "+ unstaged changes"

    def test_returns_empty_on_exception(self):
        """Test returns empty string on exception."""
        with patch('subprocess.run', side_effect=Exception("Git error")):
            result = _get_diff()

        assert result == ""


# ==================== Tests for _get_main_branch ====================

class TestGetMainBranch:
    """Tests for _get_main_branch function."""

    @patch('subprocess.run')
    def test_returns_main_if_exists(self, mock_run):
        """Test returns 'main' if it exists."""
        mock_run.return_value = MagicMock(returncode=0)

        result = _get_main_branch()

        assert result == "main"

    @patch('subprocess.run')
    def test_returns_master_if_no_main(self, mock_run):
        """Test returns 'master' if 'main' doesn't exist."""
        mock_run.side_effect = [
            MagicMock(returncode=1),  # main doesn't exist
            MagicMock(returncode=0)   # master exists
        ]

        result = _get_main_branch()

        assert result == "master"

    @patch('subprocess.run')
    def test_defaults_to_main(self, mock_run):
        """Test defaults to 'main' if neither exists."""
        mock_run.return_value = MagicMock(returncode=1)

        result = _get_main_branch()

        assert result == "main"


# ==================== Tests for _analyze_with_ai ====================

class TestAnalyzeWithAI:
    """Tests for _analyze_with_ai function."""

    def test_returns_approve_for_empty_diff(self):
        """Test returns approve for empty diff."""
        result = _analyze_with_ai("", {})

        assert result["decision"] == "approve"
        assert result["score"] == 100

    def test_raises_error_without_llm_config(self):
        """Test raises error without LLM configuration."""
        with pytest.raises(ValueError, match="No LLM configured"):
            _analyze_with_ai("+ code", {})

    @patch('redgit.commands.quality.LLMClient')
    @patch('redgit.commands.quality._load_prompt_template')
    def test_calls_llm_with_prompt(self, mock_load_prompt, mock_llm):
        """Test calls LLM with prompt containing diff."""
        mock_load_prompt.return_value = "Analyze: {{DIFF}}"
        mock_client = MagicMock()
        mock_client.chat.return_value = '{"score": 80, "decision": "approve", "issues": []}'
        mock_llm.return_value = mock_client

        result = _analyze_with_ai("+ new code", {"llm": {"provider": "test"}})

        assert "new code" in mock_client.chat.call_args[0][0]


# ==================== Tests for _parse_quality_response ====================

class TestParseQualityResponse:
    """Tests for _parse_quality_response function."""

    def test_parses_plain_json(self):
        """Test parses plain JSON response."""
        response = '{"score": 85, "decision": "approve", "summary": "Good", "issues": []}'

        result = _parse_quality_response(response)

        assert result["score"] == 85
        assert result["decision"] == "approve"

    def test_extracts_json_from_markdown(self):
        """Test extracts JSON from markdown code block."""
        response = '''Here's the analysis:
```json
{"score": 70, "decision": "reject", "summary": "Issues found", "issues": []}
```'''

        result = _parse_quality_response(response)

        assert result["score"] == 70
        assert result["decision"] == "reject"

    def test_extracts_json_from_generic_code_block(self):
        """Test extracts JSON from generic code block."""
        response = '''```
{"score": 90, "decision": "approve", "summary": "Clean code", "issues": []}
```'''

        result = _parse_quality_response(response)

        assert result["score"] == 90

    def test_handles_invalid_json(self):
        """Test handles invalid JSON gracefully."""
        response = "This is not JSON"

        result = _parse_quality_response(response)

        assert result["score"] == 0
        assert result["decision"] == "reject"
        assert "Failed to parse" in result["summary"]

    def test_handles_partial_response(self):
        """Test handles partial JSON response."""
        response = '{"score": 75}'

        result = _parse_quality_response(response)

        assert result["score"] == 75
        assert result["decision"] == "reject"  # Default
        assert result["issues"] == []


# ==================== Tests for _severity_color ====================

class TestSeverityColor:
    """Tests for _severity_color function."""

    def test_critical_is_red_bold(self):
        """Test critical severity is red bold."""
        assert _severity_color("critical") == "red bold"

    def test_high_is_red(self):
        """Test high severity is red."""
        assert _severity_color("high") == "red"

    def test_medium_is_yellow(self):
        """Test medium severity is yellow."""
        assert _severity_color("medium") == "yellow"

    def test_low_is_blue(self):
        """Test low severity is blue."""
        assert _severity_color("low") == "blue"

    def test_unknown_is_dim(self):
        """Test unknown severity is dim."""
        assert _severity_color("unknown") == "dim"

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert _severity_color("CRITICAL") == "red bold"
        assert _severity_color("High") == "red"


# ==================== Tests for Constants ====================

class TestConstants:
    """Tests for module constants."""

    def test_linters_order(self):
        """Test ruff is preferred over flake8."""
        assert LINTERS[0] == "ruff"
        assert "flake8" in LINTERS

    def test_severity_map_has_all_levels(self):
        """Test severity map has all severity levels."""
        severities = set(SEVERITY_MAP.values())
        assert "critical" in severities
        assert "high" in severities
        assert "medium" in severities
        assert "low" in severities


# ==================== CLI Integration Tests ====================

class TestQualityCLI:
    """CLI integration tests for quality command."""

    def test_quality_help(self):
        """Test quality --help shows subcommands."""
        from typer.testing import CliRunner
        from redgit.commands.quality import quality_app

        runner = CliRunner()
        result = runner.invoke(quality_app, ["--help"])

        assert result.exit_code == 0
        assert "analyze" in result.stdout.lower() or "check" in result.stdout.lower()

    def test_check_subcommand_exists(self):
        """Test check subcommand exists."""
        from typer.testing import CliRunner
        from redgit.commands.quality import quality_app

        runner = CliRunner()
        result = runner.invoke(quality_app, ["check", "--help"])

        # The command should exist and show help
        assert "commit" in result.stdout.lower() or "verbose" in result.stdout.lower() or result.exit_code == 0
