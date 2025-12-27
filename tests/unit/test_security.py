"""
Unit tests for redgit.utils.security module.
"""

import pytest

from redgit.utils.security import (
    is_excluded,
    is_sensitive,
    filter_files,
    filter_changes,
    get_env_or_config,
    get_exclusion_summary,
    ALWAYS_EXCLUDED,
    SAFE_FILES,
    SENSITIVE_PATTERNS,
)


class TestIsExcluded:
    """Tests for is_excluded function."""

    # Environment files
    @pytest.mark.parametrize("file_path", [
        ".env",
        ".env.local",
        ".env.development",
        ".env.production",
        ".env.staging",
        ".env.test",
    ])
    def test_env_files_excluded(self, file_path):
        """Test that environment files are excluded."""
        assert is_excluded(file_path) is True

    def test_env_example_not_excluded(self):
        """Test that .env.example is NOT excluded (safe file)."""
        assert is_excluded(".env.example") is False

    def test_env_sample_not_excluded(self):
        """Test that .env.sample is NOT excluded (safe file)."""
        assert is_excluded(".env.sample") is False

    def test_env_template_not_excluded(self):
        """Test that .env.template is NOT excluded (safe file)."""
        assert is_excluded(".env.template") is False

    # Credentials and keys
    @pytest.mark.parametrize("file_path", [
        "credentials.json",
        "credentials.yaml",
        "credentials.yml",
        "secrets.json",
        "secrets.yaml",
        "secrets.yml",
    ])
    def test_credential_files_excluded(self, file_path):
        """Test that credential files are excluded."""
        assert is_excluded(file_path) is True

    @pytest.mark.parametrize("file_path", [
        "private.pem",
        "server.key",
        "certificate.p12",
        "keystore.pfx",
        "app.jks",
        "android.keystore",
    ])
    def test_key_files_excluded(self, file_path):
        """Test that key files are excluded."""
        assert is_excluded(file_path) is True

    # SSH keys
    @pytest.mark.parametrize("file_path", [
        "id_rsa",
        "id_rsa.pub",
        "id_ed25519",
        "id_ed25519.pub",
        "private.ppk",
    ])
    def test_ssh_keys_excluded(self, file_path):
        """Test that SSH keys are excluded."""
        assert is_excluded(file_path) is True

    # API keys and tokens
    @pytest.mark.parametrize("file_path", [
        "my_api_key.txt",
        "stripe_api_key.json",
        "github_secret.yaml",
        "token.txt",
        "token.json",
        "auth_token.txt",
        "api_key",
    ])
    def test_api_key_files_excluded(self, file_path):
        """Test that API key/token files are excluded."""
        assert is_excluded(file_path) is True

    # Cloud provider configs
    @pytest.mark.parametrize("file_path", [
        ".aws/credentials",
        ".aws/config",
        "gcloud-service-account-prod.json",
        "service-account-key.json",
        "firebase-adminsdk-abc123.json",
    ])
    def test_cloud_configs_excluded(self, file_path):
        """Test that cloud provider configs are excluded."""
        assert is_excluded(file_path) is True

    # Database files
    @pytest.mark.parametrize("file_path", [
        "database.sqlite",
        "app.sqlite3",
        "local.db",
    ])
    def test_database_files_excluded(self, file_path):
        """Test that database files are excluded."""
        assert is_excluded(file_path) is True

    # Directories
    @pytest.mark.parametrize("file_path", [
        ".redgit/config.yaml",
        ".redgit/state.yaml",
        "vendor/package/file.php",
        "node_modules/package/index.js",
        ".venv/lib/python/site.py",
        "venv/bin/activate",
        "__pycache__/module.pyc",
    ])
    def test_directories_excluded(self, file_path):
        """Test that entire directories are excluded."""
        assert is_excluded(file_path) is True

    # Safe source files
    @pytest.mark.parametrize("file_path", [
        "src/main.py",
        "src/config.py",
        "tests/test_main.py",
        "README.md",
        "package.json",
        "requirements.txt",
        "Dockerfile",
        ".github/workflows/ci.yml",
    ])
    def test_source_files_not_excluded(self, file_path):
        """Test that normal source files are NOT excluded."""
        assert is_excluded(file_path) is False

    def test_path_normalization(self):
        """Test that Windows paths are normalized."""
        assert is_excluded(".redgit\\config.yaml") is True
        assert is_excluded("vendor\\package\\file.php") is True


class TestIsSensitive:
    """Tests for is_sensitive function."""

    @pytest.mark.parametrize("file_path", [
        "config.json",
        "config.yaml",
        "config.yml",
        "settings.json",
        "settings.yaml",
        "appsettings.json",
        "application.properties",
        "application.yml",
    ])
    def test_sensitive_files_detected(self, file_path):
        """Test that sensitive config files are detected."""
        assert is_sensitive(file_path) is True

    @pytest.mark.parametrize("file_path", [
        "src/main.py",
        "package.json",
        "tsconfig.json",
        "pyproject.toml",
    ])
    def test_non_sensitive_files(self, file_path):
        """Test that non-sensitive files are not flagged."""
        assert is_sensitive(file_path) is False

    def test_case_insensitive(self):
        """Test that sensitive check is case-insensitive."""
        assert is_sensitive("CONFIG.JSON") is True
        assert is_sensitive("Settings.Yaml") is True


class TestFilterFiles:
    """Tests for filter_files function."""

    def test_filters_excluded_files(self):
        """Test that excluded files are filtered out."""
        files = [
            "src/main.py",
            ".env",
            "tests/test_main.py",
            "credentials.json",
        ]

        allowed, excluded = filter_files(files)

        assert "src/main.py" in allowed
        assert "tests/test_main.py" in allowed
        assert ".env" in excluded
        assert "credentials.json" in excluded

    def test_returns_sensitive_files_when_requested(self):
        """Test that sensitive files are returned separately when requested."""
        files = [
            "src/main.py",
            "config.json",
            ".env",
            "settings.yaml",
        ]

        allowed, excluded, sensitive = filter_files(files, warn_sensitive=True)

        assert "src/main.py" in allowed
        assert "config.json" in allowed
        assert ".env" in excluded
        assert "config.json" in sensitive
        assert "settings.yaml" in sensitive

    def test_empty_list_returns_empty(self):
        """Test that empty input returns empty lists."""
        allowed, excluded = filter_files([])

        assert allowed == []
        assert excluded == []


class TestFilterChanges:
    """Tests for filter_changes function."""

    def test_filters_excluded_changes(self):
        """Test that changes with excluded files are filtered out."""
        changes = [
            {"file": "src/main.py", "status": "modified"},
            {"file": ".env", "status": "modified"},
            {"file": "tests/test_main.py", "status": "new"},
            {"file": "credentials.json", "status": "new"},
        ]

        allowed, excluded = filter_changes(changes)

        assert len(allowed) == 2
        assert allowed[0]["file"] == "src/main.py"
        assert allowed[1]["file"] == "tests/test_main.py"
        assert ".env" in excluded
        assert "credentials.json" in excluded

    def test_returns_sensitive_changes_when_requested(self):
        """Test that sensitive files are returned separately when requested."""
        changes = [
            {"file": "src/main.py", "status": "modified"},
            {"file": "config.json", "status": "modified"},
            {"file": ".env", "status": "modified"},
        ]

        allowed, excluded, sensitive = filter_changes(changes, warn_sensitive=True)

        assert len(allowed) == 2
        assert "config.json" in sensitive
        assert ".env" in excluded

    def test_empty_changes_returns_empty(self):
        """Test that empty input returns empty lists."""
        allowed, excluded = filter_changes([])

        assert allowed == []
        assert excluded == []

    def test_handles_missing_file_key(self):
        """Test that changes without 'file' key are handled."""
        changes = [
            {"status": "modified"},  # No file key
            {"file": "src/main.py", "status": "modified"},
        ]

        allowed, excluded = filter_changes(changes)

        # Change without file key should be excluded (empty string is not excluded)
        assert len(allowed) == 2


class TestGetEnvOrConfig:
    """Tests for get_env_or_config function."""

    def test_returns_env_var_when_set(self, mock_env):
        """Test that environment variable takes precedence."""
        mock_env(MY_KEY="env_value")

        result = get_env_or_config("MY_KEY", {"MY_KEY": "config_value"})

        assert result == "env_value"

    def test_returns_config_when_no_env(self, mock_env):
        """Test that config value is used when no env var."""
        mock_env(MY_KEY=None)

        result = get_env_or_config("MY_KEY", {"MY_KEY": "config_value"})

        assert result == "config_value"

    def test_returns_default_when_neither(self, mock_env):
        """Test that default is used when neither env nor config has value."""
        mock_env(MY_KEY=None)

        result = get_env_or_config("MY_KEY", {}, default="default_value")

        assert result == "default_value"

    def test_returns_none_when_nothing(self, mock_env):
        """Test that None is returned when nothing is set."""
        mock_env(MY_KEY=None)

        result = get_env_or_config("MY_KEY", {})

        assert result is None


class TestGetExclusionSummary:
    """Tests for get_exclusion_summary function."""

    def test_returns_string(self):
        """Test that summary returns a non-empty string."""
        summary = get_exclusion_summary()

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_mentions_key_patterns(self):
        """Test that summary mentions key exclusion patterns."""
        summary = get_exclusion_summary()

        assert ".redgit" in summary
        assert ".env" in summary
        assert "pem" in summary or "key" in summary


class TestExclusionPatterns:
    """Tests for the exclusion pattern lists themselves."""

    def test_always_excluded_not_empty(self):
        """Test that ALWAYS_EXCLUDED list is not empty."""
        assert len(ALWAYS_EXCLUDED) > 0

    def test_safe_files_contains_env_example(self):
        """Test that SAFE_FILES contains .env.example."""
        assert ".env.example" in SAFE_FILES

    def test_sensitive_patterns_not_empty(self):
        """Test that SENSITIVE_PATTERNS list is not empty."""
        assert len(SENSITIVE_PATTERNS) > 0

    def test_redgit_directory_excluded(self):
        """Test that .redgit/ is in ALWAYS_EXCLUDED."""
        assert ".redgit/" in ALWAYS_EXCLUDED or ".redgit/**" in ALWAYS_EXCLUDED
