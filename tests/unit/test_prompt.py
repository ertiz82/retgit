"""
Tests for redgit/core/prompt.py - Prompt management utilities.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from redgit.core.prompt import (
    get_prompt_path,
    get_user_prompt_path,
    PromptManager,
    BUILTIN_PROMPTS_DIR,
    PROMPT_CATEGORIES,
    RESPONSE_SCHEMA_WITH_ISSUES,
    RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE,
    RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE_EN,
    RESPONSE_SCHEMA_WITH_ISSUE_TITLE,
    RESPONSE_SCHEMA_WITH_ISSUE_TITLE_EN,
)
from redgit.prompts import RESPONSE_SCHEMA


class TestGetPromptPath:
    """Tests for get_prompt_path function."""

    def test_static_category_commit(self):
        """Test path for commit category."""
        path = get_prompt_path("commit", "default")
        assert path == PROMPT_CATEGORIES["commit"] / "default.md"

    def test_static_category_quality(self):
        """Test path for quality category."""
        path = get_prompt_path("quality", "default")
        assert path == PROMPT_CATEGORIES["quality"] / "default.md"

    def test_adds_md_extension(self):
        """Test that .md extension is added if missing."""
        path = get_prompt_path("commit", "minimal")
        assert str(path).endswith(".md")

    def test_preserves_md_extension(self):
        """Test that .md extension is not duplicated."""
        path = get_prompt_path("commit", "default.md")
        assert str(path).endswith("default.md")
        assert not str(path).endswith("default.md.md")

    def test_dynamic_category_integrations(self):
        """Test path for integration category."""
        path = get_prompt_path("integrations/jira", "issue_title")
        assert path == BUILTIN_PROMPTS_DIR / "integrations/jira" / "issue_title.md"

    def test_dynamic_category_plugins(self):
        """Test path for plugin category."""
        path = get_prompt_path("plugins/laravel", "default")
        assert path == BUILTIN_PROMPTS_DIR / "plugins/laravel" / "default.md"


class TestGetUserPromptPath:
    """Tests for get_user_prompt_path function."""

    def test_returns_user_path(self):
        """Test that user path is in .redgit/prompts."""
        path = get_user_prompt_path("commit", "default")
        assert ".redgit" in str(path)
        assert "prompts" in str(path)

    def test_adds_md_extension(self):
        """Test that .md extension is added."""
        path = get_user_prompt_path("quality", "custom")
        assert str(path).endswith("custom.md")

    def test_preserves_md_extension(self):
        """Test that .md extension is not duplicated."""
        path = get_user_prompt_path("commit", "default.md")
        assert not str(path).endswith("default.md.md")

    def test_nested_category(self):
        """Test nested category path."""
        path = get_user_prompt_path("integrations/jira", "issue_title")
        assert "integrations/jira" in str(path) or "integrations\\jira" in str(path)


class TestPromptManagerInit:
    """Tests for PromptManager initialization."""

    def test_default_values(self):
        """Test initialization with empty config."""
        pm = PromptManager({})
        assert pm.max_files == 100
        assert pm.include_content is False
        assert pm.default_prompt == "auto"

    def test_custom_max_files(self):
        """Test initialization with custom max_files."""
        pm = PromptManager({"max_files": 50})
        assert pm.max_files == 50

    def test_custom_include_content(self):
        """Test initialization with include_content."""
        pm = PromptManager({"include_content": True})
        assert pm.include_content is True

    def test_custom_prompt(self):
        """Test initialization with custom prompt."""
        pm = PromptManager({"prompt": "minimal"})
        assert pm.default_prompt == "minimal"


class TestPromptManagerFormatFiles:
    """Tests for PromptManager._format_files method."""

    def test_formats_basic_files(self):
        """Test basic file formatting."""
        pm = PromptManager({})
        changes = [
            {"file": "src/main.py", "status": "M"},
            {"file": "tests/test_main.py", "status": "A"},
        ]
        result = pm._format_files(changes)

        assert "src/main.py" in result
        assert "tests/test_main.py" in result
        assert "[modified]" in result
        assert "[added]" in result

    def test_formats_untracked_files(self):
        """Test untracked file status."""
        pm = PromptManager({})
        changes = [{"file": "new_file.py", "status": "U"}]
        result = pm._format_files(changes)

        assert "[untracked]" in result

    def test_formats_deleted_files(self):
        """Test deleted file status."""
        pm = PromptManager({})
        changes = [{"file": "old_file.py", "status": "D"}]
        result = pm._format_files(changes)

        assert "[deleted]" in result

    def test_includes_file_count_header(self):
        """Test that file count header is included."""
        pm = PromptManager({})
        changes = [{"file": "a.py", "status": "M"}, {"file": "b.py", "status": "M"}]
        result = pm._format_files(changes)

        assert "TOTAL: 2 FILES" in result

    def test_respects_max_files_limit(self):
        """Test max files limit."""
        pm = PromptManager({"max_files": 2})
        changes = [
            {"file": "a.py", "status": "M"},
            {"file": "b.py", "status": "M"},
            {"file": "c.py", "status": "M"},
        ]
        result = pm._format_files(changes)

        assert "a.py" in result
        assert "b.py" in result
        assert "... and 1 more files" in result

    def test_shows_truncation_message(self):
        """Test truncation message when files exceed limit."""
        pm = PromptManager({"max_files": 1})
        changes = [
            {"file": "a.py", "status": "M"},
            {"file": "b.py", "status": "M"},
            {"file": "c.py", "status": "M"},
        ]
        result = pm._format_files(changes)

        assert "... and 2 more files" in result

    def test_includes_reminder(self):
        """Test reminder message is included."""
        pm = PromptManager({})
        changes = [{"file": "a.py", "status": "M"}]
        result = pm._format_files(changes)

        assert "REMINDER" in result
        assert "MUST appear" in result

    def test_handles_unknown_status(self):
        """Test handling of unknown status codes."""
        pm = PromptManager({})
        changes = [{"file": "a.py", "status": "X"}]
        result = pm._format_files(changes)

        assert "[X]" in result

    def test_handles_conflict_status(self):
        """Test conflict status."""
        pm = PromptManager({})
        changes = [{"file": "a.py", "status": "C"}]
        result = pm._format_files(changes)

        assert "[conflict]" in result


class TestPromptManagerFormatIssues:
    """Tests for PromptManager._format_issues method."""

    @dataclass
    class MockIssue:
        key: str
        summary: str
        status: str = "Open"
        description: str = ""

    def test_formats_basic_issues(self):
        """Test basic issue formatting."""
        pm = PromptManager({})
        issues = [
            self.MockIssue(key="PROJ-123", summary="Fix login bug", status="In Progress"),
            self.MockIssue(key="PROJ-124", summary="Add feature", status="To Do"),
        ]
        result = pm._format_issues(issues)

        assert "PROJ-123" in result
        assert "PROJ-124" in result
        assert "Fix login bug" in result
        assert "[In Progress]" in result

    def test_includes_header(self):
        """Test that header is included."""
        pm = PromptManager({})
        issues = [self.MockIssue(key="PROJ-1", summary="Test")]
        result = pm._format_issues(issues)

        assert "Active Issues" in result
        assert "task management" in result

    def test_truncates_long_description(self):
        """Test that long descriptions are truncated."""
        pm = PromptManager({})
        long_desc = "A" * 200
        issues = [self.MockIssue(key="PROJ-1", summary="Test", description=long_desc)]
        result = pm._format_issues(issues)

        assert "..." in result
        assert len(result) < len(long_desc) + 200  # Some overhead for formatting

    def test_includes_short_description(self):
        """Test that short descriptions are included."""
        pm = PromptManager({})
        issues = [self.MockIssue(key="PROJ-1", summary="Test", description="Short desc")]
        result = pm._format_issues(issues)

        assert "Short desc" in result

    def test_handles_issue_without_status(self):
        """Test handling issue without status attribute."""
        pm = PromptManager({})

        class IssueNoStatus:
            key = "PROJ-1"
            summary = "Test"

        issues = [IssueNoStatus()]
        result = pm._format_issues(issues)

        assert "PROJ-1" in result


class TestPromptManagerGetResponseSchema:
    """Tests for PromptManager._get_response_schema method."""

    def test_basic_schema_no_issues(self):
        """Test basic schema without issues."""
        pm = PromptManager({})
        result = pm._get_response_schema(has_issues=False)

        assert result == RESPONSE_SCHEMA

    def test_schema_with_issues(self):
        """Test schema with issues."""
        pm = PromptManager({})
        result = pm._get_response_schema(has_issues=True)

        assert result == RESPONSE_SCHEMA_WITH_ISSUES
        assert "issue_key" in result

    def test_schema_with_english_language(self):
        """Test schema with English language."""
        pm = PromptManager({})
        result = pm._get_response_schema(has_issues=False, issue_language="en")

        assert result == RESPONSE_SCHEMA_WITH_ISSUE_TITLE_EN

    def test_schema_with_issues_and_english(self):
        """Test schema with issues and English."""
        pm = PromptManager({})
        result = pm._get_response_schema(has_issues=True, issue_language="en")

        assert result == RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE_EN

    def test_schema_with_turkish_language(self):
        """Test schema with Turkish language."""
        pm = PromptManager({})
        result = pm._get_response_schema(has_issues=False, issue_language="tr")

        assert "Turkish" in result
        assert "issue_title" in result

    def test_schema_with_issues_and_turkish(self):
        """Test schema with issues and Turkish."""
        pm = PromptManager({})
        result = pm._get_response_schema(has_issues=True, issue_language="tr")

        assert "Turkish" in result
        assert "LANGUAGE REQUIREMENT" in result

    def test_schema_with_unknown_language(self):
        """Test schema with unknown language code."""
        pm = PromptManager({})
        result = pm._get_response_schema(has_issues=False, issue_language="xx")

        assert "xx" in result  # Uses code as name

    def test_supported_languages(self):
        """Test various supported languages."""
        pm = PromptManager({})
        languages = ["de", "fr", "es", "pt", "it", "ru", "zh", "ja", "ko", "ar"]

        for lang in languages:
            result = pm._get_response_schema(has_issues=False, issue_language=lang)
            assert "issue_title" in result


class TestPromptManagerLoadByName:
    """Tests for PromptManager._load_by_name method."""

    def test_loads_from_url(self):
        """Test loading prompt from URL."""
        pm = PromptManager({})

        with patch.object(pm, '_fetch_url', return_value="URL content") as mock_fetch:
            result = pm._load_by_name("https://example.com/prompt.md")
            mock_fetch.assert_called_once_with("https://example.com/prompt.md")
            assert result == "URL content"

    def test_loads_from_http_url(self):
        """Test loading prompt from HTTP URL."""
        pm = PromptManager({})

        with patch.object(pm, '_fetch_url', return_value="HTTP content") as mock_fetch:
            result = pm._load_by_name("http://example.com/prompt.md")
            mock_fetch.assert_called_once()

    def test_loads_from_project_path(self, tmp_path):
        """Test loading from project prompts folder."""
        pm = PromptManager({})

        # Create temp prompt file
        prompt_dir = tmp_path / ".redgit" / "prompts" / "commit"
        prompt_dir.mkdir(parents=True)
        prompt_file = prompt_dir / "custom.md"
        prompt_file.write_text("Custom prompt content")

        with patch('redgit.core.prompt.RETGIT_DIR', tmp_path / ".redgit"):
            result = pm._load_by_name("custom", "commit")
            assert result == "Custom prompt content"

    def test_raises_file_not_found(self):
        """Test FileNotFoundError for missing prompt."""
        pm = PromptManager({})

        with patch('redgit.core.prompt.RETGIT_DIR', Path("/nonexistent")):
            with patch('redgit.core.prompt.PROMPT_CATEGORIES', {}):
                with pytest.raises(FileNotFoundError, match="Prompt not found"):
                    pm._load_by_name("nonexistent", "commit")


class TestPromptManagerFetchUrl:
    """Tests for PromptManager._fetch_url method."""

    def test_successful_fetch(self):
        """Test successful URL fetch."""
        pm = PromptManager({})

        mock_response = MagicMock()
        mock_response.text = "Prompt from URL"
        mock_response.raise_for_status = MagicMock()

        with patch('redgit.core.prompt.requests.get', return_value=mock_response) as mock_get:
            result = pm._fetch_url("https://example.com/prompt.md")
            mock_get.assert_called_once_with("https://example.com/prompt.md", timeout=10)
            assert result == "Prompt from URL"

    def test_fetch_error(self):
        """Test URL fetch error handling."""
        pm = PromptManager({})

        with patch('redgit.core.prompt.requests.get', side_effect=Exception("Network error")):
            with pytest.raises(RuntimeError, match="Failed to fetch prompt"):
                pm._fetch_url("https://example.com/prompt.md")


class TestPromptManagerGetPrompt:
    """Tests for PromptManager.get_prompt method."""

    def test_basic_prompt_generation(self):
        """Test basic prompt generation."""
        pm = PromptManager({})
        changes = [{"file": "test.py", "status": "M"}]

        with patch.object(pm, '_load_template', return_value="Template {{FILES}}"):
            result = pm.get_prompt(changes)

            assert "test.py" in result
            assert "Template" in result

    def test_prompt_with_issues(self):
        """Test prompt generation with issues."""
        pm = PromptManager({})
        changes = [{"file": "test.py", "status": "M"}]

        @dataclass
        class MockIssue:
            key: str
            summary: str
            status: str

        issues = [MockIssue(key="PROJ-1", summary="Test issue", status="Open")]

        with patch.object(pm, '_load_template', return_value="Template {{FILES}}"):
            result = pm.get_prompt(changes, active_issues=issues)

            assert "PROJ-1" in result
            assert "Active Issues" in result

    def test_prompt_with_language(self):
        """Test prompt generation with issue language."""
        pm = PromptManager({})
        changes = [{"file": "test.py", "status": "M"}]

        with patch.object(pm, '_load_template', return_value="Template {{FILES}}"):
            result = pm.get_prompt(changes, issue_language="tr")

            assert "Turkish" in result


class TestPromptManagerLoadTemplate:
    """Tests for PromptManager._load_template method."""

    def test_explicit_prompt_name(self):
        """Test loading with explicit prompt name."""
        pm = PromptManager({})

        with patch.object(pm, '_load_by_name', return_value="Named prompt") as mock_load:
            with patch('redgit.core.prompt.get_builtin_plugins', return_value=[]):
                result = pm._load_template("custom", None)
                mock_load.assert_called_with("custom")
                assert result == "Named prompt"

    def test_plugin_prompt_in_auto_mode(self):
        """Test using plugin prompt in auto mode."""
        pm = PromptManager({"prompt": "auto"})

        result = pm._load_template(None, "Plugin prompt content")
        assert result == "Plugin prompt content"

    def test_config_specified_prompt(self):
        """Test loading config-specified prompt."""
        pm = PromptManager({"prompt": "minimal"})

        with patch.object(pm, '_load_by_name', return_value="Minimal prompt") as mock_load:
            result = pm._load_template(None, None)
            mock_load.assert_called_with("minimal")

    def test_default_prompt_fallback(self):
        """Test default prompt fallback."""
        pm = PromptManager({})

        with patch.object(pm, '_load_by_name', return_value="Default prompt") as mock_load:
            result = pm._load_template(None, None)
            mock_load.assert_called_with("default")

    def test_plugin_name_as_prompt(self):
        """Test using plugin name as prompt."""
        pm = PromptManager({})

        mock_plugin = MagicMock()
        mock_plugin.get_prompt.return_value = "Laravel prompt"

        with patch('redgit.core.prompt.get_builtin_plugins', return_value=["laravel"]):
            with patch('redgit.core.prompt.get_plugin_by_name', return_value=mock_plugin):
                result = pm._load_template("laravel", None)
                assert result == "Laravel prompt"


class TestPromptManagerStaticMethods:
    """Tests for PromptManager static methods."""

    def test_load_prompt_user_override(self, tmp_path):
        """Test load_prompt with user override."""
        # Create user prompt
        user_dir = tmp_path / ".redgit" / "prompts" / "commit"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "default.md"
        user_file.write_text("User override content")

        with patch('redgit.core.prompt.get_user_prompt_path', return_value=user_file):
            result = PromptManager.load_prompt("commit", "default")
            assert result == "User override content"

    def test_load_prompt_builtin(self, tmp_path):
        """Test load_prompt with builtin."""
        builtin_file = tmp_path / "default.md"
        builtin_file.write_text("Builtin content")

        with patch('redgit.core.prompt.get_user_prompt_path', return_value=tmp_path / "nonexistent.md"):
            with patch('redgit.core.prompt.get_prompt_path', return_value=builtin_file):
                result = PromptManager.load_prompt("commit", "default")
                assert result == "Builtin content"

    def test_load_prompt_not_found(self, tmp_path):
        """Test load_prompt raises when not found."""
        with patch('redgit.core.prompt.get_user_prompt_path', return_value=tmp_path / "nonexistent.md"):
            with patch('redgit.core.prompt.get_prompt_path', return_value=tmp_path / "also_nonexistent.md"):
                with pytest.raises(FileNotFoundError):
                    PromptManager.load_prompt("commit", "nonexistent")

    def test_export_prompt(self, tmp_path):
        """Test export_prompt creates file."""
        with patch.object(PromptManager, 'load_prompt', return_value="Content to export"):
            with patch('redgit.core.prompt.RETGIT_DIR', tmp_path / ".redgit"):
                result = PromptManager.export_prompt("commit", "default")

                assert result.exists()
                assert result.read_text() == "Content to export"

    def test_get_available_prompts(self, tmp_path):
        """Test get_available_prompts returns list."""
        with patch('redgit.core.prompt.BUILTIN_PROMPTS_DIR', tmp_path):
            with patch('redgit.core.prompt.RETGIT_DIR', tmp_path / ".redgit"):
                with patch('redgit.core.prompt.get_builtin_plugins', return_value=["laravel", "django"]):
                    # Create a test prompt file
                    (tmp_path / "test.md").write_text("test")

                    result = PromptManager.get_available_prompts()

                    assert isinstance(result, list)
                    assert "laravel" in result
                    assert "django" in result
                    assert "test" in result


class TestPromptManagerListAllPrompts:
    """Tests for PromptManager.list_all_prompts method."""

    def test_returns_dict(self):
        """Test that list_all_prompts returns a dict."""
        with patch('redgit.core.prompt.PROMPT_CATEGORIES', {}):
            with patch('redgit.core.prompt.RETGIT_DIR', Path("/nonexistent")):
                with patch('redgit.integrations.registry.get_all_integration_classes', return_value={}):
                    result = PromptManager.list_all_prompts()
                    assert isinstance(result, dict)

    def test_includes_builtin_prompts(self, tmp_path):
        """Test that builtin prompts are included."""
        # Create temp category
        commit_dir = tmp_path / "commit"
        commit_dir.mkdir()
        (commit_dir / "default.md").write_text("default")
        (commit_dir / "minimal.md").write_text("minimal")

        with patch('redgit.core.prompt.PROMPT_CATEGORIES', {"commit": commit_dir}):
            with patch('redgit.core.prompt.RETGIT_DIR', Path("/nonexistent")):
                with patch('redgit.integrations.registry.get_all_integration_classes', return_value={}):
                    result = PromptManager.list_all_prompts()

                    assert "commit" in result
                    names = [p["name"] for p in result["commit"]]
                    assert "default" in names
                    assert "minimal" in names


class TestPromptManagerGetIntegrationPrompt:
    """Tests for PromptManager._get_integration_prompt method."""

    def test_returns_prompt_content(self):
        """Test returning integration prompt content."""
        mock_cls = MagicMock()
        mock_cls.get_prompts.return_value = {
            "issue_title": {"content": "Issue title prompt"}
        }

        with patch('redgit.integrations.registry.get_integration_class', return_value=mock_cls):
            result = PromptManager._get_integration_prompt("jira", "issue_title")
            assert result == "Issue title prompt"

    def test_returns_none_for_missing_integration(self):
        """Test returning None for missing integration."""
        with patch('redgit.integrations.registry.get_integration_class', return_value=None):
            result = PromptManager._get_integration_prompt("nonexistent", "default")
            assert result is None

    def test_returns_none_for_missing_prompt(self):
        """Test returning None for missing prompt name."""
        mock_cls = MagicMock()
        mock_cls.get_prompts.return_value = {}

        with patch('redgit.integrations.registry.get_integration_class', return_value=mock_cls):
            result = PromptManager._get_integration_prompt("jira", "nonexistent")
            assert result is None


class TestPromptCategories:
    """Tests for PROMPT_CATEGORIES constant."""

    def test_commit_category_exists(self):
        """Test commit category is defined."""
        assert "commit" in PROMPT_CATEGORIES

    def test_quality_category_exists(self):
        """Test quality category is defined."""
        assert "quality" in PROMPT_CATEGORIES

    def test_categories_are_paths(self):
        """Test categories contain Path objects."""
        for category, path in PROMPT_CATEGORIES.items():
            assert isinstance(path, Path)


class TestResponseSchemas:
    """Tests for response schema constants."""

    def test_basic_schema_has_files_field(self):
        """Test basic schema mentions files field."""
        assert "files" in RESPONSE_SCHEMA

    def test_issues_schema_has_issue_key(self):
        """Test issues schema has issue_key field."""
        assert "issue_key" in RESPONSE_SCHEMA_WITH_ISSUES

    def test_language_schema_has_warning(self):
        """Test language schema has language warning."""
        assert "LANGUAGE REQUIREMENT" in RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE

    def test_english_schema_no_warning(self):
        """Test English schema has no language warning."""
        assert "LANGUAGE REQUIREMENT" not in RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE_EN

    def test_issue_title_schema_required(self):
        """Test issue title schema marks it as required."""
        assert "REQUIRED" in RESPONSE_SCHEMA_WITH_ISSUE_TITLE

    def test_schemas_are_valid_strings(self):
        """Test all schemas are non-empty strings."""
        schemas = [
            RESPONSE_SCHEMA,
            RESPONSE_SCHEMA_WITH_ISSUES,
            RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE,
            RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE_EN,
            RESPONSE_SCHEMA_WITH_ISSUE_TITLE,
            RESPONSE_SCHEMA_WITH_ISSUE_TITLE_EN,
        ]
        for schema in schemas:
            assert isinstance(schema, str)
            assert len(schema) > 100  # Should be substantial
