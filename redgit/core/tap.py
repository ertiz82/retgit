"""
Tap Management - External plugin/integration repositories.

A "tap" is a repository containing plugins and integrations that can be
installed into RedGit. The official tap is at github.com/ertiz82/redgit-tap.

Users can add their own taps to extend RedGit with custom plugins/integrations.

Taps are stored globally in ~/.redgit/:
    ~/.redgit/
    ├── taps/           # Tap index cache
    ├── taps.yaml       # Tap configuration
    ├── integrations/   # Installed integrations
    └── plugins/        # Installed plugins
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import requests
import yaml

from .config import (
    GLOBAL_REDGIT_DIR,
    GLOBAL_TAPS_DIR,
    ensure_global_dirs
)

# Official tap URL
OFFICIAL_TAP_URL = "https://github.com/ertiz82/redgit-tap"
OFFICIAL_TAP_NAME = "official"

# Global tap cache directory
TAP_CACHE_DIR = GLOBAL_TAPS_DIR

# Global taps config file
GLOBAL_TAPS_CONFIG = GLOBAL_REDGIT_DIR / "taps.yaml"

# Cache expiry in seconds (1 hour)
CACHE_EXPIRY = 3600


@dataclass
class TapItem:
    """Represents a plugin or integration from a tap"""
    name: str
    description: str
    version: str
    type: str  # "plugin" or "integration"
    item_type: str  # e.g., "framework", "utility", "code_hosting", "notification"
    author: str = ""
    tap_name: str = ""
    tap_url: str = ""
    auto_detect: bool = False
    installed: bool = False


@dataclass
class Tap:
    """Represents a tap repository"""
    url: str
    name: str
    description: str = ""
    version: str = ""
    plugins: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    integrations: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_index(cls, url: str, name: str, index_data: dict) -> "Tap":
        """Create Tap from index.json data"""
        return cls(
            url=url,
            name=name,
            description=index_data.get("description", ""),
            version=index_data.get("version", "1.0.0"),
            plugins=index_data.get("plugins", {}),
            integrations=index_data.get("integrations", {})
        )


class TapManager:
    """Manages tap repositories and their indexes (stored globally)"""

    def __init__(self):
        ensure_global_dirs()
        self._taps: Dict[str, Tap] = {}

    def _load_taps_config(self) -> dict:
        """Load global taps configuration"""
        if GLOBAL_TAPS_CONFIG.exists():
            try:
                return yaml.safe_load(GLOBAL_TAPS_CONFIG.read_text()) or {}
            except Exception:
                return {}
        return {}

    def _save_taps_config(self, config: dict):
        """Save global taps configuration"""
        ensure_global_dirs()
        GLOBAL_TAPS_CONFIG.write_text(
            yaml.dump(config, allow_unicode=True, sort_keys=False)
        )

    def get_configured_taps(self) -> List[Dict[str, str]]:
        """Get list of configured taps from global config"""
        config = self._load_taps_config()
        taps = config.get("taps", [])

        # Always include official tap if not present
        has_official = any(t.get("name") == OFFICIAL_TAP_NAME for t in taps)
        if not has_official:
            taps.insert(0, {"url": OFFICIAL_TAP_URL, "name": OFFICIAL_TAP_NAME})

        return taps

    def add_tap(self, url: str, name: str = None) -> str:
        """
        Add a new tap (globally).

        Args:
            url: Repository URL (github.com/user/repo, gitlab.com/user/repo, etc.)
            name: Optional tap name (auto-generated from index.json or URL if not provided)

        Returns:
            Tap name if added successfully
        """
        # Normalize URL
        url = self._normalize_url(url)

        # Validate tap by fetching index first (we need it for the name)
        index = self._fetch_index(url)
        if not index:
            raise ValueError(f"Invalid tap: Could not fetch index.json from {url}")

        # Get name from index.json, user override, or URL fallback
        if not name:
            name = index.get("name") or self._extract_name_from_url(url)

        # Check if already exists
        config = self._load_taps_config()
        taps = config.get("taps", [])

        for tap in taps:
            if tap.get("url") == url:
                raise ValueError(f"Tap already exists: {url}")
            if tap.get("name") == name:
                raise ValueError(f"Tap name already in use: {name}")

        # Add to global config
        taps.append({"url": url, "name": name})
        config["taps"] = taps
        self._save_taps_config(config)

        # Clear cache for this tap
        self._clear_cache(name)

        return name

    def remove_tap(self, name_or_url: str) -> bool:
        """
        Remove a tap by name or URL (globally).

        Args:
            name_or_url: Tap name or URL

        Returns:
            True if removed
        """
        if name_or_url == OFFICIAL_TAP_NAME:
            raise ValueError("Cannot remove official tap")

        config = self._load_taps_config()
        taps = config.get("taps", [])

        original_count = len(taps)
        taps = [
            t for t in taps
            if t.get("name") != name_or_url and t.get("url") != name_or_url
        ]

        if len(taps) == original_count:
            raise ValueError(f"Tap not found: {name_or_url}")

        config["taps"] = taps
        self._save_taps_config(config)

        # Clear cache
        self._clear_cache(name_or_url)

        return True

    def list_taps(self) -> List[Tap]:
        """List all configured taps with their info"""
        taps = []
        for tap_config in self.get_configured_taps():
            tap = self._load_tap(tap_config["url"], tap_config["name"])
            if tap:
                taps.append(tap)
        return taps

    def get_all_plugins(self, include_installed: bool = True) -> List[TapItem]:
        """
        Get all available plugins from all taps.

        Args:
            include_installed: Whether to include already installed plugins

        Returns:
            List of TapItem objects
        """
        from ..plugins.registry import get_builtin_plugins

        items = []
        installed_plugins = set(get_builtin_plugins()) if include_installed else set()

        for tap_config in self.get_configured_taps():
            tap = self._load_tap(tap_config["url"], tap_config["name"])
            if not tap:
                continue

            for name, info in tap.plugins.items():
                item = TapItem(
                    name=name,
                    description=info.get("description", ""),
                    version=info.get("version", "1.0.0"),
                    type="plugin",
                    item_type=info.get("type", "utility"),
                    author=info.get("author", ""),
                    tap_name=tap.name,
                    tap_url=tap.url,
                    auto_detect=info.get("auto_detect", False),
                    installed=name in installed_plugins
                )
                items.append(item)

        return items

    def get_all_integrations(self, include_installed: bool = True) -> List[TapItem]:
        """
        Get all available integrations from all taps.

        Args:
            include_installed: Whether to include already installed integrations

        Returns:
            List of TapItem objects
        """
        from ..integrations.registry import get_builtin_integrations

        items = []
        installed_integrations = set(get_builtin_integrations(include_core=True)) if include_installed else set()

        for tap_config in self.get_configured_taps():
            tap = self._load_tap(tap_config["url"], tap_config["name"])
            if not tap:
                continue

            for name, info in tap.integrations.items():
                item = TapItem(
                    name=name,
                    description=info.get("description", ""),
                    version=info.get("version", "1.0.0"),
                    type="integration",
                    item_type=info.get("type", "utility"),
                    author=info.get("author", ""),
                    tap_name=tap.name,
                    tap_url=tap.url,
                    auto_detect=info.get("auto_detect", False),
                    installed=name in installed_integrations
                )
                items.append(item)

        return items

    def get_plugin_info(self, name: str) -> Optional[TapItem]:
        """Get info for a specific plugin from taps"""
        for item in self.get_all_plugins():
            if item.name == name:
                return item
        return None

    def get_integration_info(self, name: str) -> Optional[TapItem]:
        """Get info for a specific integration from taps"""
        for item in self.get_all_integrations():
            if item.name == name:
                return item
        return None

    def refresh_cache(self):
        """Refresh all tap caches"""
        TAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        for tap_config in self.get_configured_taps():
            self._clear_cache(tap_config["name"])
            self._load_tap(tap_config["url"], tap_config["name"], force_refresh=True)

    def _load_tap(self, url: str, name: str, force_refresh: bool = False) -> Optional[Tap]:
        """Load tap from cache or fetch from remote"""
        # Check cache first
        if not force_refresh:
            cached = self._load_from_cache(name)
            if cached:
                # If cache has no URL, update it from config
                if not cached.url:
                    cached.url = url
                return cached

        # Fetch from remote
        index = self._fetch_index(url)
        if not index:
            return None

        tap = Tap.from_index(url, name, index)

        # Save to cache with URL
        self._save_to_cache(name, index, url)

        return tap

    def _fetch_index(self, url: str) -> Optional[dict]:
        """Fetch index.json from tap repository"""
        # Convert GitHub/GitLab URL to raw content URL
        raw_url = self._get_raw_url(url, "index.json")

        try:
            response = requests.get(raw_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def _get_raw_url(self, repo_url: str, file_path: str) -> str:
        """Convert repository URL to raw file URL"""
        repo_url = self._normalize_url(repo_url)
        parsed = urlparse(repo_url)

        if "github.com" in parsed.netloc:
            # https://github.com/user/repo -> https://raw.githubusercontent.com/user/repo/main/file
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) >= 2:
                user, repo = path_parts[0], path_parts[1]
                return f"https://raw.githubusercontent.com/{user}/{repo}/main/{file_path}"

        elif "gitlab.com" in parsed.netloc:
            # https://gitlab.com/user/repo -> https://gitlab.com/user/repo/-/raw/main/file
            return f"{repo_url}/-/raw/main/{file_path}"

        elif "bitbucket.org" in parsed.netloc:
            # https://bitbucket.org/user/repo -> https://bitbucket.org/user/repo/raw/main/file
            return f"{repo_url}/raw/main/{file_path}"

        # Default: assume it's a direct URL or has raw endpoint
        return f"{repo_url}/{file_path}"

    def _normalize_url(self, url: str) -> str:
        """Normalize repository URL"""
        url = url.strip()

        # Add https:// if missing
        if not url.startswith("http://") and not url.startswith("https://"):
            # Handle shorthand: user/repo or github.com/user/repo
            if "/" in url and not "." in url.split("/")[0]:
                # user/repo -> https://github.com/user/repo
                url = f"https://github.com/{url}"
            else:
                url = f"https://{url}"

        # Remove trailing slash
        url = url.rstrip("/")

        # Remove .git suffix
        if url.endswith(".git"):
            url = url[:-4]

        return url

    def _extract_name_from_url(self, url: str) -> str:
        """Extract tap name from URL"""
        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) >= 2:
            # Use repo name, removing common prefixes/suffixes
            name = path_parts[-1]
            for prefix in ["redgit-", "rg-"]:
                if name.startswith(prefix):
                    name = name[len(prefix):]
            for suffix in ["-tap", "-plugins", "-integrations"]:
                if name.endswith(suffix):
                    name = name[:-len(suffix)]
            return name

        return "custom"

    def _load_from_cache(self, name: str) -> Optional[Tap]:
        """Load tap from cache if not expired"""
        import time

        cache_file = TAP_CACHE_DIR / f"{name}.json"
        if not cache_file.exists():
            return None

        # Check if cache is expired
        mtime = cache_file.stat().st_mtime
        if time.time() - mtime > CACHE_EXPIRY:
            return None

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                return Tap.from_index(
                    data.get("_url", ""),
                    name,
                    data
                )
        except Exception:
            return None

    def _save_to_cache(self, name: str, index: dict, url: str = ""):
        """Save tap index to cache with URL"""
        TAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = TAP_CACHE_DIR / f"{name}.json"

        try:
            # Add URL to cached data
            cache_data = index.copy()
            cache_data["_url"] = url

            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)
        except Exception:
            pass

    def _clear_cache(self, name: str):
        """Clear cache for a tap"""
        cache_file = TAP_CACHE_DIR / f"{name}.json"
        if cache_file.exists():
            cache_file.unlink()


# Convenience functions
def get_tap_manager() -> TapManager:
    """Get TapManager instance"""
    return TapManager()


def get_available_plugins() -> List[TapItem]:
    """Get all available plugins from all taps"""
    return TapManager().get_all_plugins()


def get_available_integrations() -> List[TapItem]:
    """Get all available integrations from all taps"""
    return TapManager().get_all_integrations()


def find_item_in_taps(
    item_name: str,
    item_type: str = "integration",
    tap_name: str = None
) -> Optional[tuple]:
    """
    Find an item in configured taps.

    Args:
        item_name: Name of the item to find
        item_type: "integration" or "plugin"
        tap_name: Optional tap name to search in (None = search all)

    Returns:
        Tuple of (tap_url, item_info) if found, None otherwise
    """
    tap_mgr = TapManager()

    for tap_config in tap_mgr.get_configured_taps():
        # Skip if specific tap requested and this isn't it
        if tap_name and tap_config["name"] != tap_name:
            continue

        tap = tap_mgr._load_tap(tap_config["url"], tap_config["name"])
        if not tap:
            continue

        items = tap.integrations if item_type == "integration" else tap.plugins

        # Try exact match first
        if item_name in items:
            return (tap.url, tap.name, items[item_name])

        # Try with underscores/hyphens
        normalized = item_name.replace("-", "_")
        if normalized in items:
            return (tap.url, tap.name, items[normalized])

        normalized = item_name.replace("_", "-")
        if normalized in items:
            return (tap.url, tap.name, items[normalized])

    return None