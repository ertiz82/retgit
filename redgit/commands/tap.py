"""
Tap system for installing integrations and plugins from GitHub repositories.

Similar to Homebrew taps, users can install integrations/plugins from GitHub:

    # From default tap (ertiz82/redgit-tap)
    rg install jira               # integration from official tap
    rg install plugin:laravel     # plugin from official tap
    rg install slack@v1.0.0       # specific version

    # From custom tap (auto-adds tap first)
    rg install myorg/my-tap jira              # integration from custom tap
    rg install myorg/my-tap plugin:myplugin   # plugin from custom tap

Default tap structure (ertiz82/redgit-tap):
    redgit-tap/
    ├── integrations/
    │   ├── slack/
    │   │   ├── __init__.py
    │   │   ├── commands.py
    │   │   └── install_schema.json
    │   └── linear/
    │       └── ...
    └── plugins/
        ├── changelog/
        │   ├── __init__.py
        │   └── commands.py
        └── semver/
            └── ...
"""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

import typer

from ..core.config import (
    ConfigManager,
    GLOBAL_INTEGRATIONS_DIR,
    GLOBAL_PLUGINS_DIR,
    GLOBAL_TAP_REGISTRY,
    ensure_global_dirs
)

# Global tap registry file location
TAP_REGISTRY_FILE = GLOBAL_TAP_REGISTRY

# Default tap repository
DEFAULT_TAP_OWNER = "ertiz82"
DEFAULT_TAP_REPO = "redgit-tap"
DEFAULT_TAP = f"{DEFAULT_TAP_OWNER}/{DEFAULT_TAP_REPO}"

# Cache for default tap index
_default_tap_index_cache: Optional[Dict] = None


def _is_default_tap_spec(spec: str) -> bool:
    """Check if spec is for default tap (no owner specified)."""
    # If no "/" or starts with "plugin:", it's from default tap
    if "/" not in spec:
        return True
    # plugin:name format
    if spec.startswith("plugin:"):
        return True
    return False


def _parse_default_tap_spec(spec: str) -> Tuple[str, str, Optional[str]]:
    """
    Parse default tap specification.

    Formats:
        name              -> ("integration", name, None)
        name@v1.0.0       -> ("integration", name, "v1.0.0")
        plugin:name       -> ("plugin", name, None)
        plugin:name@v1.0  -> ("plugin", name, "v1.0")

    Returns:
        (item_type, name, version)
    """
    version = None
    item_type = "integration"

    # Check for version
    if "@" in spec:
        spec, version = spec.rsplit("@", 1)

    # Check for plugin prefix
    if spec.startswith("plugin:"):
        item_type = "plugin"
        spec = spec[7:]  # Remove "plugin:" prefix

    # Clean up name
    name = spec.lower().replace("-", "_")

    return item_type, name, version


def _parse_custom_tap_spec(spec: str) -> Tuple[str, str, Optional[str]]:
    """
    Parse custom tap specification.

    Formats:
        owner/name           -> (owner, name, None)
        owner/name@v1.0.0    -> (owner, name, "v1.0.0")

    Returns:
        (owner, repo_name, version)
    """
    version = None

    if "@" in spec:
        spec, version = spec.rsplit("@", 1)

    if "/" not in spec:
        raise ValueError(f"Invalid tap format: {spec}. Expected: owner/name")

    owner, name = spec.split("/", 1)
    name = name.lower().replace("-", "_")

    return owner, name, version


def _fetch_default_tap_index(force_refresh: bool = False) -> Dict:
    """
    Fetch the index of available items from default tap.

    Returns dict with structure:
    {
        "integrations": {"slack": {...}, "linear": {...}},
        "plugins": {"changelog": {...}, "semver": {...}}
    }
    """
    global _default_tap_index_cache

    if _default_tap_index_cache and not force_refresh:
        return _default_tap_index_cache

    # Try to fetch index.json from default tap
    index_url = f"https://raw.githubusercontent.com/{DEFAULT_TAP}/main/index.json"

    try:
        req = Request(index_url, headers={"User-Agent": "redgit"})
        with urlopen(req, timeout=10) as response:
            _default_tap_index_cache = json.loads(response.read().decode("utf-8"))
            return _default_tap_index_cache
    except (HTTPError, URLError, json.JSONDecodeError):
        # Return empty index if fetch fails
        return {"integrations": {}, "plugins": {}}


def _list_default_tap_items() -> Tuple[List[str], List[str]]:
    """
    List available integrations and plugins from default tap.

    Returns:
        (integrations_list, plugins_list)
    """
    index = _fetch_default_tap_index()
    integrations = list(index.get("integrations", {}).keys())
    plugins = list(index.get("plugins", {}).keys())
    return integrations, plugins


def _download_from_default_tap(
    item_type: str,
    name: str,
    version: Optional[str] = None
) -> Path:
    """
    Download an integration or plugin from the default tap.

    Args:
        item_type: "integration" or "plugin"
        name: Item name
        version: Optional version/branch

    Returns:
        Path to extracted directory
    """
    ref = version or "main"

    # Determine folder path in repo
    folder = "integrations" if item_type == "integration" else "plugins"

    # Download the whole repo and extract specific folder
    refs_to_try = [ref] if ref != "main" else ["main", "master"]

    for try_ref in refs_to_try:
        zip_url = f"https://github.com/{DEFAULT_TAP}/archive/refs/heads/{try_ref}.zip"

        if try_ref.startswith("v") or (try_ref[0].isdigit() if try_ref else False):
            zip_url = f"https://github.com/{DEFAULT_TAP}/archive/refs/tags/{try_ref}.zip"

        try:
            req = Request(zip_url, headers={"User-Agent": "redgit"})
            with urlopen(req, timeout=30) as response:
                temp_dir = Path(tempfile.mkdtemp(prefix="redgit_tap_"))
                zip_path = temp_dir / "repo.zip"

                with open(zip_path, "wb") as f:
                    f.write(response.read())

                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(temp_dir)

                # Find extracted directory
                repo_dir = None
                for item in temp_dir.iterdir():
                    if item.is_dir() and item.name != "__MACOSX":
                        repo_dir = item
                        break

                if not repo_dir:
                    raise FileNotFoundError("No directory found in zip")

                # Find the specific integration/plugin folder
                item_dir = repo_dir / folder / name.replace("_", "-")

                # Also try with underscores
                if not item_dir.exists():
                    item_dir = repo_dir / folder / name

                if not item_dir.exists():
                    # List available items for error message
                    available = []
                    folder_path = repo_dir / folder
                    if folder_path.exists():
                        available = [d.name for d in folder_path.iterdir() if d.is_dir()]
                    raise FileNotFoundError(
                        f"'{name}' not found in {folder}. "
                        f"Available: {', '.join(available) if available else 'none'}"
                    )

                # Copy to a new temp location (so we can cleanup repo)
                result_dir = Path(tempfile.mkdtemp(prefix="redgit_item_"))
                shutil.copytree(item_dir, result_dir / name)

                # Cleanup repo temp
                shutil.rmtree(temp_dir, ignore_errors=True)

                return result_dir / name

        except HTTPError as e:
            if e.code == 404 and try_ref == "main":
                continue
            raise

    raise HTTPError(zip_url, 404, "Default tap repository not found", {}, None)


def _download_from_custom_tap(
    owner: str,
    name: str,
    version: Optional[str] = None
) -> Path:
    """
    Download from a custom tap (owner's repo).

    Tries repo names: redgit-{name}, redgit-integration-{name}, {name}
    """
    ref = version or "main"

    # Try different repo name patterns
    patterns = [
        f"redgit-{name.replace('_', '-')}",
        f"redgit-integration-{name.replace('_', '-')}",
        name.replace("_", "-"),
    ]

    refs_to_try = [ref] if ref != "main" else ["main", "master"]

    for repo_name in patterns:
        for try_ref in refs_to_try:
            zip_url = f"https://github.com/{owner}/{repo_name}/archive/refs/heads/{try_ref}.zip"

            if try_ref.startswith("v") or (try_ref[0].isdigit() if try_ref else False):
                zip_url = f"https://github.com/{owner}/{repo_name}/archive/refs/tags/{try_ref}.zip"

            try:
                req = Request(zip_url, headers={"User-Agent": "redgit"})
                with urlopen(req, timeout=30) as response:
                    temp_dir = Path(tempfile.mkdtemp(prefix="redgit_tap_"))
                    zip_path = temp_dir / "repo.zip"

                    with open(zip_path, "wb") as f:
                        f.write(response.read())

                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.extractall(temp_dir)

                    for item in temp_dir.iterdir():
                        if item.is_dir() and item.name != "__MACOSX":
                            return item

                    raise FileNotFoundError("No directory found in zip")

            except HTTPError as e:
                if e.code == 404:
                    continue
                raise

    raise HTTPError(
        f"https://github.com/{owner}/...",
        404,
        f"Repository not found. Tried: {', '.join(patterns)}",
        {}, None
    )


def _validate_item(source_dir: Path, item_type: str) -> Dict[str, Any]:
    """
    Validate that the directory contains a valid integration or plugin.

    Returns:
        Dict with item info (name, type, description)
    """
    init_file = source_dir / "__init__.py"

    if not init_file.exists():
        raise ValueError("Missing __init__.py - not a valid package")

    content = init_file.read_text(encoding="utf-8")

    info = {
        "name": None,
        "item_type": item_type,
        "integration_type": "unknown",
        "description": "",
    }

    # Extract attributes
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("name = "):
            info["name"] = line.split("=", 1)[1].strip().strip('"\'')
        elif "IntegrationType." in line and "integration_type" in line:
            if "TASK_MANAGEMENT" in line:
                info["integration_type"] = "task_management"
            elif "CODE_HOSTING" in line:
                info["integration_type"] = "code_hosting"
            elif "NOTIFICATION" in line:
                info["integration_type"] = "notification"
            elif "ANALYSIS" in line:
                info["integration_type"] = "analysis"

    # Try install_schema.json for description
    schema_file = source_dir / "install_schema.json"
    if schema_file.exists():
        try:
            schema = json.loads(schema_file.read_text(encoding="utf-8"))
            info["description"] = schema.get("description", "")
            if not info["name"]:
                info["name"] = schema.get("name", "").lower().replace(" ", "_")
        except json.JSONDecodeError:
            pass

    # Try README
    if not info["description"]:
        readme = source_dir / "README.md"
        if readme.exists():
            lines = readme.read_text(encoding="utf-8").split("\n")
            for line in lines[1:10]:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("```"):
                    info["description"] = line[:100]
                    break

    return info


def _load_tap_registry() -> Dict[str, Dict]:
    """Load the tap registry from .redgit/taps.json"""
    if TAP_REGISTRY_FILE.exists():
        try:
            return json.loads(TAP_REGISTRY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_tap_registry(registry: Dict[str, Dict]):
    """Save the tap registry to .redgit/taps.json"""
    TAP_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    TAP_REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _register_integration_notification_events(target_dir: Path, name: str):
    """
    Register custom notification events from an integration.

    Reads notification_events from the integration class and adds
    any new events to the config file.
    """
    try:
        from ..integrations.registry import load_integration_by_name

        # Try to load the integration class
        integration = load_integration_by_name(name, {})
        if not integration:
            return

        # Get notification events from the class
        events = integration.get_notification_events()
        if not events:
            return

        # Skip notification integrations - they don't emit events
        from ..integrations.base import IntegrationType
        if integration.integration_type == IntegrationType.NOTIFICATION:
            return

        # Register events in config
        config_manager = ConfigManager()
        config_manager.register_notification_events(events)

        # Show registered events
        if events:
            typer.echo(f"   Registered {len(events)} notification event(s):")
            for event_name, event_def in events.items():
                default = "on" if event_def.get("default", True) else "off"
                typer.echo(f"     • {event_name} ({default})")

    except Exception:
        # Silently ignore errors - notification events are optional
        pass


def install_from_tap(
    spec: str,
    force: bool = False,
    no_configure: bool = False,
    tap_name: str = None
) -> bool:
    """
    Install an integration or plugin from a tap.

    Args:
        spec: Tap specification:
            - "name" or "name@version" for integration
            - "plugin:name" for plugin
        force: Overwrite if already exists
        no_configure: Skip configuration wizard
        tap_name: Optional tap name to install from (None = search all taps)

    Returns:
        True if successful
    """
    # Parse spec to get item type and name
    item_type, name, version = _parse_default_tap_spec(spec)

    # Search for item in configured taps
    from ..core.tap import find_item_in_taps

    result = find_item_in_taps(name, item_type, tap_name)

    if result:
        tap_url, found_tap_name, item_info = result
        return _install_from_tap_url(
            tap_url=tap_url,
            tap_name=found_tap_name,
            item_type=item_type,
            name=name,
            item_info=item_info,
            version=version,
            force=force,
            no_configure=no_configure
        )
    elif tap_name:
        # Specific tap requested but item not found - show error
        typer.secho(f"❌ '{name}' not found in tap '{tap_name}'.", fg=typer.colors.RED)
        typer.echo(f"\n   💡 Check available items: rg tap list -v")
        return False
    else:
        # No specific tap - fallback to default tap download
        return _install_from_default_tap(spec, force, no_configure)


def _download_from_tap_url(
    tap_url: str,
    item_type: str,
    name: str,
    item_info: Dict[str, Any],
    version: Optional[str] = None
) -> Path:
    """
    Download an item from a tap URL using the item's path from index.json.

    Args:
        tap_url: Base URL of the tap repository
        item_type: "integration" or "plugin"
        name: Item name
        item_info: Item info dict from index.json (contains 'path')
        version: Optional version/branch

    Returns:
        Path to extracted directory
    """
    from urllib.parse import urlparse

    ref = version or "main"

    # Get path from item_info, fallback to default structure
    item_path = item_info.get("path", f"{item_type}s/{name}")

    # Parse tap URL to get owner/repo
    parsed = urlparse(tap_url)
    path_parts = parsed.path.strip("/").split("/")

    if len(path_parts) < 2:
        raise ValueError(f"Invalid tap URL: {tap_url}")

    owner, repo = path_parts[0], path_parts[1]

    refs_to_try = [ref] if ref != "main" else ["main", "master"]

    for try_ref in refs_to_try:
        zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{try_ref}.zip"

        if try_ref.startswith("v") or (try_ref[0].isdigit() if try_ref else False):
            zip_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{try_ref}.zip"

        try:
            req = Request(zip_url, headers={"User-Agent": "redgit"})
            with urlopen(req, timeout=30) as response:
                temp_dir = Path(tempfile.mkdtemp(prefix="redgit_tap_"))
                zip_path = temp_dir / "repo.zip"

                with open(zip_path, "wb") as f:
                    f.write(response.read())

                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(temp_dir)

                # Find extracted directory
                repo_dir = None
                for item in temp_dir.iterdir():
                    if item.is_dir() and item.name != "__MACOSX":
                        repo_dir = item
                        break

                if not repo_dir:
                    raise FileNotFoundError("No directory found in zip")

                # Find the item using path from index
                item_dir = repo_dir / item_path

                # Try variations
                if not item_dir.exists():
                    item_dir = repo_dir / item_path.replace("-", "_")
                if not item_dir.exists():
                    item_dir = repo_dir / item_path.replace("_", "-")

                if not item_dir.exists():
                    raise FileNotFoundError(
                        f"'{name}' not found at path '{item_path}' in tap"
                    )

                # Copy to a new temp location
                result_dir = Path(tempfile.mkdtemp(prefix="redgit_item_"))
                shutil.copytree(item_dir, result_dir / name)

                # Cleanup repo temp
                shutil.rmtree(temp_dir, ignore_errors=True)

                return result_dir / name

        except HTTPError as e:
            if e.code == 404 and try_ref == "main":
                continue
            raise

    raise HTTPError(zip_url, 404, f"Tap repository not found: {tap_url}", {}, None)


def _install_from_tap_url(
    tap_url: str,
    tap_name: str,
    item_type: str,
    name: str,
    item_info: Dict[str, Any],
    version: Optional[str] = None,
    force: bool = False,
    no_configure: bool = False
) -> bool:
    """
    Install an item from a specific tap URL.

    Args:
        tap_url: URL of the tap repository
        tap_name: Name of the tap
        item_type: "integration" or "plugin"
        name: Item name
        item_info: Item info from index.json
        version: Optional version
        force: Overwrite existing
        no_configure: Skip configuration

    Returns:
        True if successful
    """
    typer.echo(f"\n📦 Installing {item_type}: {name}\n")
    typer.echo(f"   Source: {tap_name}/{item_type}s/{name}")
    if version:
        typer.echo(f"   Version: {version}")

    # Determine target directory (global)
    ensure_global_dirs()
    if item_type == "integration":
        target_dir = GLOBAL_INTEGRATIONS_DIR / name
    else:
        target_dir = GLOBAL_PLUGINS_DIR / name

    # Check if already exists
    if target_dir.exists() and not force:
        typer.secho(f"❌ {item_type.capitalize()} '{name}' already exists.", fg=typer.colors.RED)
        typer.echo(f"   Use --force to overwrite")
        typer.echo(f"   Location: {target_dir}")
        return False

    # Download from tap
    typer.echo(f"   Downloading from {tap_name} tap...")
    try:
        source_dir = _download_from_tap_url(tap_url, item_type, name, item_info, version)
    except FileNotFoundError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED)
        return False
    except HTTPError as e:
        typer.secho(f"❌ Failed to download: {e}", fg=typer.colors.RED)
        return False
    except URLError as e:
        typer.secho(f"❌ Network error: {e}", fg=typer.colors.RED)
        return False

    # Validate
    typer.echo(f"   Validating...")
    try:
        info = _validate_item(source_dir, item_type)
        if not info["name"]:
            info["name"] = name
    except ValueError as e:
        typer.secho(f"❌ Invalid {item_type}: {e}", fg=typer.colors.RED)
        shutil.rmtree(source_dir.parent, ignore_errors=True)
        return False

    # Remove existing if force
    if target_dir.exists() and force:
        typer.echo(f"   Removing existing installation...")
        shutil.rmtree(target_dir)

    # Install
    typer.echo(f"   Installing to {target_dir}...")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)

    # Cleanup
    shutil.rmtree(source_dir.parent, ignore_errors=True)

    # Update registry
    registry = _load_tap_registry()
    registry[name] = {
        "source": f"{tap_name}/{item_type}s/{name}",
        "tap_url": tap_url,
        "version": version or "latest",
        "item_type": item_type,
        "integration_type": info.get("integration_type", item_info.get("type", "unknown")),
        "description": info["description"] or item_info.get("description", ""),
        "installed_at": str(target_dir.resolve()),
    }
    _save_tap_registry(registry)

    # Refresh caches
    if item_type == "integration":
        from ..integrations.registry import refresh_integrations
        refresh_integrations()

        # Register custom notification events from the integration
        _register_integration_notification_events(target_dir, name)

    # Success
    typer.echo("")
    typer.secho(f"✅ Installed: {name}", fg=typer.colors.GREEN)
    typer.echo(f"   Type: {item_type}")
    desc = info["description"] or item_info.get("description", "")
    if desc:
        typer.echo(f"   {desc}")

    # Configure and activate
    if not no_configure and item_type == "integration":
        from ..integrations.registry import get_install_schema
        schema = get_install_schema(name)
        if schema:
            typer.echo("")
            from .integration import configure_integration
            configure_integration(name)
        else:
            # No schema, just enable
            config = ConfigManager().load()
            if "integrations" not in config:
                config["integrations"] = {}
            config["integrations"][name] = {"enabled": True}
            ConfigManager().save(config)
            typer.echo(f"\n   ✅ Integration enabled")
    elif item_type == "plugin":
        typer.echo(f"\n   💡 Enable with: rg plugin enable {name}")

    return True


def _install_from_default_tap(
    spec: str,
    force: bool = False,
    no_configure: bool = False
) -> bool:
    """Install from default tap (ertiz82/redgit-tap). Fallback when item not found in configured taps."""
    item_type, name, version = _parse_default_tap_spec(spec)

    typer.echo(f"\n📦 Installing {item_type}: {name}\n")
    typer.echo(f"   Source: {DEFAULT_TAP}/{item_type}s/{name}")
    if version:
        typer.echo(f"   Version: {version}")

    # Determine target directory (global)
    ensure_global_dirs()
    if item_type == "integration":
        target_dir = GLOBAL_INTEGRATIONS_DIR / name
    else:
        target_dir = GLOBAL_PLUGINS_DIR / name

    # Check if already exists
    if target_dir.exists() and not force:
        typer.secho(f"❌ {item_type.capitalize()} '{name}' already exists.", fg=typer.colors.RED)
        typer.echo(f"   Use --force to overwrite")
        typer.echo(f"   Location: {target_dir}")
        return False

    # Download from default tap
    typer.echo(f"   Downloading from default tap...")
    try:
        source_dir = _download_from_default_tap(item_type, name, version)
    except FileNotFoundError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED)
        return False
    except HTTPError as e:
        typer.secho(f"❌ Failed to download: {e}", fg=typer.colors.RED)
        return False
    except URLError as e:
        typer.secho(f"❌ Network error: {e}", fg=typer.colors.RED)
        return False

    # Validate
    typer.echo(f"   Validating...")
    try:
        info = _validate_item(source_dir, item_type)
        if not info["name"]:
            info["name"] = name
    except ValueError as e:
        typer.secho(f"❌ Invalid {item_type}: {e}", fg=typer.colors.RED)
        shutil.rmtree(source_dir.parent, ignore_errors=True)
        return False

    # Remove existing if force
    if target_dir.exists() and force:
        typer.echo(f"   Removing existing installation...")
        shutil.rmtree(target_dir)

    # Install
    typer.echo(f"   Installing to {target_dir}...")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)

    # Cleanup
    shutil.rmtree(source_dir.parent, ignore_errors=True)

    # Update registry
    registry = _load_tap_registry()
    registry[name] = {
        "source": f"{DEFAULT_TAP}/{item_type}s/{name}",
        "version": version or "latest",
        "item_type": item_type,
        "integration_type": info.get("integration_type", "unknown"),
        "description": info["description"],
        "installed_at": str(target_dir.resolve()),
    }
    _save_tap_registry(registry)

    # Refresh caches
    if item_type == "integration":
        from ..integrations.registry import refresh_integrations
        refresh_integrations()

        # Register custom notification events from the integration
        _register_integration_notification_events(target_dir, name)

    # Success
    typer.echo("")
    typer.secho(f"✅ Installed: {name}", fg=typer.colors.GREEN)
    typer.echo(f"   Type: {item_type}")
    if info["description"]:
        typer.echo(f"   {info['description']}")

    # Configure and activate
    if not no_configure and item_type == "integration":
        from ..integrations.registry import get_install_schema
        schema = get_install_schema(name)
        if schema:
            typer.echo("")
            from .integration import configure_integration
            configure_integration(name)
        else:
            # No schema, just enable
            config = ConfigManager().load()
            if "integrations" not in config:
                config["integrations"] = {}
            config["integrations"][name] = {"enabled": True}
            ConfigManager().save(config)
            typer.echo(f"\n   ✅ Integration enabled")
    elif item_type == "plugin":
        typer.echo(f"\n   💡 Enable with: rg plugin enable {name}")

    return True


def _install_from_custom_tap(
    spec: str,
    force: bool = False,
    no_configure: bool = False
) -> bool:
    """Install from a custom tap (user's GitHub repo)."""
    try:
        owner, name, version = _parse_custom_tap_spec(spec)
    except ValueError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED)
        return False

    typer.echo(f"\n📦 Installing from tap: {owner}/{name}\n")
    typer.echo(f"   Source: github.com/{owner}/...")
    if version:
        typer.echo(f"   Version: {version}")

    # Target directory (global - custom taps are always integrations)
    ensure_global_dirs()
    target_dir = GLOBAL_INTEGRATIONS_DIR / name

    if target_dir.exists() and not force:
        typer.secho(f"❌ Integration '{name}' already exists.", fg=typer.colors.RED)
        typer.echo(f"   Use --force to overwrite")
        return False

    # Download
    typer.echo(f"   Downloading...")
    try:
        source_dir = _download_from_custom_tap(owner, name, version)
    except HTTPError as e:
        typer.secho(f"❌ Failed to download: {e}", fg=typer.colors.RED)
        return False
    except URLError as e:
        typer.secho(f"❌ Network error: {e}", fg=typer.colors.RED)
        return False

    # Validate
    typer.echo(f"   Validating...")
    try:
        info = _validate_item(source_dir, "integration")
        if not info["name"]:
            info["name"] = name
    except ValueError as e:
        typer.secho(f"❌ Invalid integration: {e}", fg=typer.colors.RED)
        shutil.rmtree(source_dir.parent, ignore_errors=True)
        return False

    # Remove existing if force
    if target_dir.exists() and force:
        shutil.rmtree(target_dir)

    # Install
    typer.echo(f"   Installing to {target_dir}...")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)

    # Cleanup
    shutil.rmtree(source_dir.parent, ignore_errors=True)

    # Update registry
    registry = _load_tap_registry()
    registry[name] = {
        "source": f"{owner}/{name}",
        "version": version or "latest",
        "item_type": "integration",
        "integration_type": info.get("integration_type", "unknown"),
        "description": info["description"],
        "installed_at": str(target_dir.resolve()),
    }
    _save_tap_registry(registry)

    # Refresh
    from ..integrations.registry import refresh_integrations
    refresh_integrations()

    # Register custom notification events from the integration
    _register_integration_notification_events(target_dir, name)

    # Success
    typer.echo("")
    typer.secho(f"✅ Installed: {name}", fg=typer.colors.GREEN)
    if info["description"]:
        typer.echo(f"   {info['description']}")

    # Configure
    if not no_configure:
        from ..integrations.registry import get_install_schema
        schema = get_install_schema(name)
        if schema:
            typer.echo("")
            if typer.confirm("   Configure now?", default=True):
                from .integration import install_cmd as integration_install
                integration_install(name)
        else:
            typer.echo(f"\n   💡 Enable with: rg integration install {name}")

    return True


def uninstall_tap(name: str) -> bool:
    """Uninstall a tap-installed integration or plugin."""
    registry = _load_tap_registry()

    if name not in registry:
        typer.secho(f"❌ '{name}' was not installed from a tap.", fg=typer.colors.RED)
        typer.echo(f"   Use 'rg integration remove' or 'rg plugin disable' for builtin items")
        return False

    item_info = registry[name]
    item_type = item_info.get("item_type", "integration")

    # Remove directory (global)
    if item_type == "plugin":
        target_dir = GLOBAL_PLUGINS_DIR / name
    else:
        target_dir = GLOBAL_INTEGRATIONS_DIR / name

    if target_dir.exists():
        shutil.rmtree(target_dir)
        typer.echo(f"   Removed: {target_dir}")

    # Remove from config
    config = ConfigManager().load()
    config_key = "plugins" if item_type == "plugin" else "integrations"
    if config_key in config and name in config[config_key]:
        del config[config_key][name]
        ConfigManager().save(config)

    # Remove from registry
    source = item_info.get("source", "unknown")
    del registry[name]
    _save_tap_registry(registry)

    # Refresh cache
    if item_type == "integration":
        from ..integrations.registry import refresh_integrations
        refresh_integrations()

    typer.secho(f"✅ Uninstalled: {name}", fg=typer.colors.GREEN)
    typer.echo(f"   Source was: {source}")

    return True


def list_taps() -> Dict[str, Dict]:
    """List all tap-installed items."""
    return _load_tap_registry()


def update_tap(name: str) -> bool:
    """Update a tap-installed item to latest version."""
    registry = _load_tap_registry()

    if name not in registry:
        typer.secho(f"❌ '{name}' was not installed from a tap.", fg=typer.colors.RED)
        return False

    item_info = registry[name]
    source = item_info.get("source", "")
    item_type = item_info.get("item_type", "integration")

    if not source:
        typer.secho(f"❌ No source information for '{name}'.", fg=typer.colors.RED)
        return False

    typer.echo(f"\n🔄 Updating {name}...\n")

    # Determine spec for reinstall
    if source.startswith(DEFAULT_TAP):
        # Default tap item
        if item_type == "plugin":
            spec = f"plugin:{name}"
        else:
            spec = name
    else:
        # Custom tap
        spec = source.split("/")[0] + "/" + name

    return install_from_tap(spec, force=True, no_configure=True)


# ==================== CLI Commands ====================

tap_app = typer.Typer(help="Manage tap-installed integrations and plugins")


@tap_app.command("list")
def list_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info")
):
    """List configured taps and tap-installed items."""
    from ..core.tap import TapManager, OFFICIAL_TAP_NAME

    tap_mgr = TapManager()

    # Show configured taps
    taps = tap_mgr.list_taps()
    if taps:
        typer.echo("\n📦 Configured Taps:\n")
        for tap in taps:
            star = "⭐ " if tap.name == OFFICIAL_TAP_NAME else "   "
            typer.echo(f"{star}{tap.name} - {len(tap.plugins)} plugins, {len(tap.integrations)} integrations")
            if verbose:
                typer.echo(f"      URL: {tap.url}")
        typer.echo("")

    # Show installed items
    registry = list_taps()

    if registry:
        typer.echo("📥 Installed from taps:\n")

        # Group by type
        integrations = {k: v for k, v in registry.items() if v.get("item_type") != "plugin"}
        plugins = {k: v for k, v in registry.items() if v.get("item_type") == "plugin"}

        if integrations:
            typer.echo("   Integrations:")
            for name, info in integrations.items():
                source = info.get("source", "unknown")
                version = info.get("version", "latest")
                typer.echo(f"     • {name} ({version})")
                if verbose:
                    typer.echo(f"       {source}")
            typer.echo("")

        if plugins:
            typer.echo("   Plugins:")
            for name, info in plugins.items():
                source = info.get("source", "unknown")
                version = info.get("version", "latest")
                typer.echo(f"     • {name} ({version})")
                if verbose:
                    typer.echo(f"       {source}")
            typer.echo("")

    typer.echo("   💡 Commands:")
    typer.echo("      rg tap add <url>       - Add a tap repository")
    typer.echo("      rg tap remove <name>   - Remove a tap")
    typer.echo("      rg tap refresh         - Refresh tap caches")


@tap_app.command("add")
def add_cmd(
    url: str = typer.Argument(..., help="Tap repository URL (e.g., github.com/user/repo)"),
    name: str = typer.Option(None, "--name", "-n", help="Custom name for the tap")
):
    """Add a tap repository to fetch plugins and integrations from."""
    from ..core.tap import TapManager

    tap_mgr = TapManager()

    typer.echo(f"\n📦 Adding tap: {url}\n")

    try:
        added_tap_name = tap_mgr.add_tap(url, name)
        typer.secho(f"✅ Tap added: {added_tap_name}", fg=typer.colors.GREEN)
        typer.echo(f"   URL: {url}")
        typer.echo(f"\n   💡 View available items: rg tap list -v")
    except ValueError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@tap_app.command("remove")
def remove_cmd(
    name_or_url: str = typer.Argument(..., help="Tap name or URL to remove")
):
    """Remove a tap repository."""
    from ..core.tap import TapManager

    tap_mgr = TapManager()

    try:
        tap_mgr.remove_tap(name_or_url)
        typer.secho(f"✅ Tap removed: {name_or_url}", fg=typer.colors.GREEN)
    except ValueError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@tap_app.command("refresh")
def refresh_cmd():
    """Refresh all tap caches."""
    from ..core.tap import TapManager

    tap_mgr = TapManager()

    typer.echo("\n🔄 Refreshing tap caches...\n")
    tap_mgr.refresh_cache()
    typer.secho("✅ Tap caches refreshed", fg=typer.colors.GREEN)


@tap_app.command("search")
def search_cmd(query: str = typer.Argument(None, help="Search query (optional)")):
    """Search available integrations and plugins in default tap."""
    typer.echo(f"\n🔍 Fetching from {DEFAULT_TAP}...\n")

    try:
        integrations, plugins = _list_default_tap_items()
    except Exception as e:
        typer.secho(f"❌ Failed to fetch index: {e}", fg=typer.colors.RED)
        typer.echo(f"\n   Check: https://github.com/{DEFAULT_TAP}")
        return

    # Filter by query if provided
    if query:
        query = query.lower()
        integrations = [i for i in integrations if query in i.lower()]
        plugins = [p for p in plugins if query in p.lower()]

    if not integrations and not plugins:
        if query:
            typer.echo(f"   No items matching '{query}'")
        else:
            typer.echo("   No items available in default tap")
        typer.echo(f"\n   Check: https://github.com/{DEFAULT_TAP}")
        return

    index = _fetch_default_tap_index()

    if integrations:
        typer.echo("   📦 Integrations:")
        for name in integrations:
            info = index.get("integrations", {}).get(name, {})
            desc = info.get("description", "")
            typer.echo(f"     • {name}")
            if desc:
                typer.echo(f"       {desc}")
        typer.echo("")

    if plugins:
        typer.echo("   🔌 Plugins:")
        for name in plugins:
            info = index.get("plugins", {}).get(name, {})
            desc = info.get("description", "")
            typer.echo(f"     • {name}")
            if desc:
                typer.echo(f"       {desc}")
        typer.echo("")

    typer.echo("   💡 Install:")
    if integrations:
        typer.echo(f"      rg install {integrations[0]}")
    if plugins:
        typer.echo(f"      rg install plugin:{plugins[0]}")


@tap_app.command("update")
def update_cmd(
    name: str = typer.Argument(None, help="Item name to update"),
    all_taps: bool = typer.Option(False, "--all", "-a", help="Update all tap items")
):
    """Update tap-installed item(s) to latest version."""
    if all_taps:
        registry = list_taps()
        if not registry:
            typer.echo("No tap-installed items to update.")
            return

        for tap_name in registry.keys():
            update_tap(tap_name)
    elif name:
        update_tap(name)
    else:
        typer.echo("Please specify an item name or use --all")
        raise typer.Exit(1)


@tap_app.command("info")
def info_cmd(name: str = typer.Argument(..., help="Item name")):
    """Show detailed info about a tap-installed item."""
    registry = list_taps()

    if name not in registry:
        typer.secho(f"❌ '{name}' is not installed from a tap.", fg=typer.colors.RED)
        return

    info = registry[name]

    typer.echo(f"\n📦 {name}\n")
    typer.echo(f"   Source:      {info.get('source', 'unknown')}")
    typer.echo(f"   Version:     {info.get('version', 'latest')}")
    typer.echo(f"   Type:        {info.get('item_type', 'integration')}")

    if info.get("integration_type") and info["integration_type"] != "unknown":
        typer.echo(f"   Integration: {info['integration_type']}")

    if info.get("description"):
        typer.echo(f"   Description: {info['description']}")

    typer.echo(f"   Location:    {info.get('installed_at', 'unknown')}")


# ==================== Main CLI Commands ====================

def install_cmd(
    spec: str = typer.Argument(..., help="Item to install: name, plugin:name, or tap/repo name"),
    tap_source: str = typer.Argument(None, help="Custom tap source (e.g., github.com/user/tap)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing installation"),
    no_configure: bool = typer.Option(False, "--no-configure", help="Skip configuration wizard")
):
    """
    Install integration or plugin from tap.

    Examples:
        rg install jira                           # Integration from official tap
        rg install plugin:laravel                 # Plugin from official tap
        rg install slack@v1.0.0                   # Specific version
        rg install myorg/my-tap jira              # From custom tap (auto-adds tap)
        rg install myorg/my-tap plugin:myplugin   # Plugin from custom tap
    """
    # Check if first arg looks like a tap source (contains /)
    if "/" in spec and tap_source:
        # Format: rg install myorg/tap itemname
        tap_url = spec
        item_spec = tap_source

        # Auto-add the tap if not already added
        from ..core.tap import TapManager
        tap_mgr = TapManager()

        # Check if tap already exists and get its name
        configured_taps = tap_mgr.get_configured_taps()
        target_tap_name = None

        for t in configured_taps:
            if tap_url in t.get("url", "") or tap_url in t.get("name", ""):
                target_tap_name = t.get("name")
                break

        if not target_tap_name:
            typer.echo(f"\n📦 Adding tap: {tap_url}\n")
            try:
                target_tap_name = tap_mgr.add_tap(tap_url)
                typer.secho(f"✅ Tap added: {target_tap_name}", fg=typer.colors.GREEN)
            except ValueError as e:
                typer.secho(f"❌ Failed to add tap: {e}", fg=typer.colors.RED)
                raise typer.Exit(1)

        # Now install from that specific tap
        install_from_tap(item_spec, force=force, no_configure=no_configure, tap_name=target_tap_name)
    elif "/" in spec and not tap_source:
        # Old format: rg install user/repo - show help
        typer.secho("❌ Invalid format.", fg=typer.colors.RED)
        typer.echo("\n   To install from a custom tap:")
        typer.echo(f"     rg install {spec} <item-name>")
        typer.echo(f"     rg install {spec} plugin:<plugin-name>")
        typer.echo("\n   Examples:")
        typer.echo(f"     rg install {spec} jira")
        typer.echo(f"     rg install {spec} plugin:laravel")
        raise typer.Exit(1)
    else:
        # Standard format: rg install name or rg install plugin:name
        install_from_tap(spec, force=force, no_configure=no_configure)


def uninstall_cmd(
    name: str = typer.Argument(..., help="Item name to uninstall")
):
    """Uninstall a tap-installed integration or plugin."""
    uninstall_tap(name)