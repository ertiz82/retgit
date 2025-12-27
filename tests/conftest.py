"""
Pytest configuration and shared fixtures for RedGit tests.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Generator

import pytest
import yaml


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_git_repo(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository."""
    import subprocess

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_dir, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_dir, capture_output=True
    )

    # Create initial commit
    readme = temp_dir / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir, capture_output=True
    )

    yield temp_dir


@pytest.fixture
def sample_config() -> dict:
    """Return a sample RedGit configuration."""
    return {
        "project": {
            "name": "TestProject"
        },
        "llm": {
            "provider": "ollama",
            "model": "qwen-coder",
            "prompt": "auto",
            "max_files": 100,
            "include_content": False,
            "timeout": 300
        },
        "plugins": {
            "enabled": ["version", "changelog"],
            "version": {
                "current": "1.0.0",
                "enabled": True
            },
            "changelog": {
                "enabled": True,
                "format": "markdown",
                "output_dir": "changelogs"
            }
        },
        "integrations": {},
        "workflow": {
            "strategy": "local-merge",
            "auto_transition": True,
            "create_missing_issues": "ask"
        },
        "quality": {
            "enabled": True,
            "threshold": 70,
            "fail_on_security": True
        }
    }


@pytest.fixture
def config_file(temp_dir: Path, sample_config: dict) -> Path:
    """Create a .redgit/config.yaml file in temp directory."""
    redgit_dir = temp_dir / ".redgit"
    redgit_dir.mkdir(parents=True, exist_ok=True)

    config_path = redgit_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)

    return config_path


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables for testing."""
    def _mock_env(**kwargs):
        for key, value in kwargs.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
    return _mock_env


@pytest.fixture
def change_cwd(temp_dir: Path):
    """Change working directory to temp_dir for the test."""
    original_cwd = os.getcwd()
    os.chdir(temp_dir)
    yield temp_dir
    os.chdir(original_cwd)


@pytest.fixture
def sample_changes() -> list:
    """Return sample git changes for testing."""
    return [
        {
            "file": "src/main.py",
            "status": "modified",
            "diff": "@@ -1,3 +1,5 @@\n+import os\n def main():\n     pass"
        },
        {
            "file": "src/utils.py",
            "status": "new",
            "diff": "+def helper():\n+    return True"
        },
        {
            "file": "tests/test_main.py",
            "status": "modified",
            "diff": "@@ -5,6 +5,10 @@\n+def test_new():\n+    assert True"
        }
    ]


@pytest.fixture
def sample_issues() -> list:
    """Return sample issues for testing."""
    return [
        {
            "key": "PROJ-123",
            "summary": "Fix login bug",
            "type": "bug",
            "status": "In Progress"
        },
        {
            "key": "PROJ-124",
            "summary": "Add new feature",
            "type": "story",
            "status": "To Do"
        }
    ]


# Markers for test categorization
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")