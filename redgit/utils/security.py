"""
Security utilities for filtering sensitive files.

This module provides functions to:
1. Filter out sensitive files from AI prompts
2. Prevent sensitive files from being committed
3. Always exclude .redgit/ directory
"""

import os
import fnmatch
from pathlib import Path
from typing import List, Set

# Files/patterns that should NEVER be sent to AI or committed
# These are always excluded regardless of .gitignore
ALWAYS_EXCLUDED = [
    # RedGit internal
    ".redgit/",
    ".redgit/**",

    # Environment and secrets (but NOT .env.example which is safe)
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.staging",
    ".env.test",
    ".env.*.local",

    # Credentials and keys
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",

    # SSH keys
    "id_rsa",
    "id_rsa.pub",
    "id_ed25519",
    "id_ed25519.pub",
    "*.ppk",

    # API keys and tokens (common patterns)
    # Note: Using specific patterns to avoid false positives on code files
    "*_api_key.txt",
    "*_api_key.json",
    "*_api_key.yaml",
    "*_api_key.yml",
    "api_key",
    "api_key.*",
    "*_secret.txt",
    "*_secret.json",
    "*_secret.yaml",
    "*_secret.yml",
    "*.secrets",
    # Token files (but not code that handles tokens)
    "token.txt",
    "token.json",
    "*_token.txt",
    "*_token.json",
    "access_token",
    "refresh_token",

    # Cloud provider configs
    ".aws/credentials",
    ".aws/config",
    "gcloud-service-account*.json",
    "service-account*.json",
    "firebase-adminsdk*.json",

    # Database
    "*.sqlite",
    "*.sqlite3",
    "*.db",

    # IDE and local configs that might contain secrets
    ".idea/",
    ".vscode/settings.json",
    "*.local.json",
    "*.local.yaml",
    "*.local.yml",

    # Dependencies - should never be committed
    "vendor/",
    "node_modules/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    ".mypy_cache/",
    ".tox/",
    "dist/",
    "build/",
    ".eggs/",

    # Package lock files (optional, but often large)
    # "package-lock.json",  # Uncomment if you want to exclude
    # "composer.lock",      # Uncomment if you want to exclude
]

# Files that are explicitly safe to commit (override exclusions)
SAFE_FILES = [
    ".env.example",
    ".env.sample",
    ".env.template",
]

# Patterns for files that might contain secrets (warn but don't block)
SENSITIVE_PATTERNS = [
    "config.json",
    "config.yaml",
    "config.yml",
    "settings.json",
    "settings.yaml",
    "appsettings.json",
    "application.properties",
    "application.yml",
]


def is_excluded(file_path: str) -> bool:
    """
    Check if a file should be excluded from AI and git operations.

    Args:
        file_path: Path to the file (relative to repo root)

    Returns:
        True if file should be excluded
    """
    # Normalize path
    file_path = file_path.replace("\\", "/")
    file_name = os.path.basename(file_path)

    # Check if file is explicitly safe (e.g., .env.example)
    for safe_file in SAFE_FILES:
        if file_name == safe_file or fnmatch.fnmatch(file_name, safe_file):
            return False

    # Check against always excluded patterns
    for pattern in ALWAYS_EXCLUDED:
        # Directory pattern (ends with /)
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")
            if file_path.startswith(dir_name + "/") or file_path == dir_name:
                return True
        # Glob pattern
        elif fnmatch.fnmatch(file_path, pattern):
            return True
        elif fnmatch.fnmatch(file_name, pattern):
            return True

    return False


def is_sensitive(file_path: str) -> bool:
    """
    Check if a file might contain sensitive data (for warnings).

    Args:
        file_path: Path to the file

    Returns:
        True if file might contain sensitive data
    """
    file_name = os.path.basename(file_path)

    for pattern in SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(file_name.lower(), pattern.lower()):
            return True

    return False


def filter_files(files: List[str], warn_sensitive: bool = False) -> tuple:
    """
    Filter a list of files, removing excluded ones.

    Args:
        files: List of file paths
        warn_sensitive: If True, return sensitive files separately for warning

    Returns:
        If warn_sensitive: (allowed_files, excluded_files, sensitive_files)
        Otherwise: (allowed_files, excluded_files)
    """
    allowed = []
    excluded = []
    sensitive = []

    for f in files:
        if is_excluded(f):
            excluded.append(f)
        else:
            allowed.append(f)
            if warn_sensitive and is_sensitive(f):
                sensitive.append(f)

    if warn_sensitive:
        return allowed, excluded, sensitive
    return allowed, excluded


def filter_changes(changes: List[dict], warn_sensitive: bool = False) -> tuple:
    """
    Filter a list of change dicts, removing excluded ones.

    Args:
        changes: List of {"file": ..., "status": ...} dicts
        warn_sensitive: If True, return sensitive files separately

    Returns:
        If warn_sensitive: (allowed_changes, excluded_files, sensitive_files)
        Otherwise: (allowed_changes, excluded_files)
    """
    allowed = []
    excluded = []
    sensitive = []

    for change in changes:
        file_path = change.get("file", "")
        if is_excluded(file_path):
            excluded.append(file_path)
        else:
            allowed.append(change)
            if warn_sensitive and is_sensitive(file_path):
                sensitive.append(file_path)

    if warn_sensitive:
        return allowed, excluded, sensitive
    return allowed, excluded


def get_env_or_config(key: str, config: dict, default=None):
    """Get value from environment variable or config dict."""
    return os.getenv(key) or config.get(key, default)


def get_exclusion_summary() -> str:
    """Get a human-readable summary of excluded patterns."""
    return """
Excluded file patterns:
- .redgit/ (configuration directory)
- .env, .env.* (environment files)
- *.pem, *.key (private keys)
- credentials.*, secrets.* (credential files)
- id_rsa, id_ed25519 (SSH keys)
- *.sqlite, *.db (databases)
"""