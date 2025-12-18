"""
Plugin registry - dynamically loads and manages plugins.

Supports:
1. Builtin plugins: redgit/plugins/{name}.py or {name}/__init__.py
2. Global plugins: ~/.redgit/plugins/{name}/__init__.py (tap-installed)
3. Project plugins: .redgit/plugins/{name}/__init__.py (custom per-project)
"""

import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..core.config import GLOBAL_PLUGINS_DIR

# Builtin plugins directory (inside package)
BUILTIN_PLUGINS_DIR = Path(__file__).parent

# Global plugins directory (tap-installed, shared across projects)
GLOBAL_PLUGINS_PATH = GLOBAL_PLUGINS_DIR

# Project-specific plugins directory (custom per-project)
PROJECT_PLUGINS_DIR = Path(".redgit/plugins")

# Available builtin plugins
# Plugins are now loaded from tap (redgit-tap) via `rg install <plugin>`
# No builtin plugins in core package
BUILTIN_PLUGINS = []


def detect_project_type() -> list:
    """Detect project type based on files"""
    # Project type detection now handled by tap plugins
    return []


def get_builtin_plugins() -> List[str]:
    """List available builtin plugins"""
    available = []
    for name in BUILTIN_PLUGINS:
        # Check for single file plugin (name.py)
        if (BUILTIN_PLUGINS_DIR / f"{name}.py").exists():
            available.append(name)
        # Check for package plugin (name/__init__.py)
        elif (BUILTIN_PLUGINS_DIR / name / "__init__.py").exists():
            available.append(name)
    return available


def get_all_plugins() -> List[str]:
    """
    List all available plugins from all sources.

    Returns:
        List of plugin names from builtin, global, and project directories
    """
    plugins = set(get_builtin_plugins())

    # Add global plugins (tap-installed)
    if GLOBAL_PLUGINS_PATH.exists():
        for item in GLOBAL_PLUGINS_PATH.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                plugins.add(item.name)

    # Add project-specific plugins
    if PROJECT_PLUGINS_DIR.exists():
        for item in PROJECT_PLUGINS_DIR.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                plugins.add(item.name)

    return list(plugins)


def load_plugins(config: dict) -> Dict[str, Any]:
    """
    Load enabled plugins from all sources.

    Args:
        config: plugins section from config.yaml

    Returns:
        Dict of plugin_name -> plugin_instance
    """
    plugins = {}
    enabled = config.get("enabled", [])

    for name in enabled:
        plugin = _load_plugin(name)
        if plugin:
            plugins[name] = plugin

    return plugins


def _load_plugin(name: str) -> Optional[Any]:
    """
    Load a plugin by name from all sources.

    Load order (later can override earlier):
    1. Builtin plugins (package)
    2. Global plugins (tap-installed, ~/.redgit/plugins/)
    3. Project plugins (custom per-project, .redgit/plugins/)
    """
    plugin = None

    # 1. Check builtin plugins
    builtin_path = BUILTIN_PLUGINS_DIR / f"{name}.py"
    if builtin_path.exists():
        plugin = _load_plugin_from_file(builtin_path, name)
    else:
        package_path = BUILTIN_PLUGINS_DIR / name / "__init__.py"
        if package_path.exists():
            plugin = _load_plugin_from_file(package_path, name)

    # 2. Check global plugins (override builtin)
    global_path = GLOBAL_PLUGINS_PATH / name / "__init__.py"
    if global_path.exists():
        loaded = _load_plugin_from_file(global_path, name)
        if loaded:
            plugin = loaded

    # 3. Check project plugins (override global)
    project_path = PROJECT_PLUGINS_DIR / name / "__init__.py"
    if project_path.exists():
        loaded = _load_plugin_from_file(project_path, name)
        if loaded:
            plugin = loaded

    return plugin


def _load_plugin_from_file(path: Path, name: str) -> Optional[Any]:
    """Load plugin from a file path"""
    try:
        spec = importlib.util.spec_from_file_location(f"plugin_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for {Name}Plugin class
        class_name = f"{name.capitalize()}Plugin"
        if hasattr(module, class_name):
            cls = getattr(module, class_name)
            return cls()

        # Try CamelCase (MyPluginPlugin for my_plugin)
        camel_name = "".join(word.capitalize() for word in name.split("_")) + "Plugin"
        if hasattr(module, camel_name):
            cls = getattr(module, camel_name)
            return cls()

    except Exception:
        pass

    return None


def get_plugin_by_name(name: str) -> Optional[Any]:
    """
    Get a specific plugin by name.
    Used when -p <plugin_name> is specified.
    """
    return _load_plugin(name)


def get_active_plugin(plugins: Dict[str, Any]) -> Optional[Any]:
    """
    Get the first plugin that matches the current project.

    Args:
        plugins: Dict of loaded plugins

    Returns:
        First matching plugin or None
    """
    for plugin in plugins.values():
        if hasattr(plugin, "match") and plugin.match():
            return plugin
    return None


def get_plugin_commands(name: str) -> Optional[Any]:
    """
    Get CLI commands (typer app) for a plugin.

    Args:
        name: Plugin name (e.g., 'version', 'changelog')

    Returns:
        Typer app if plugin has commands, None otherwise
    """
    # Try builtin first
    try:
        module_name = f"redgit.plugins.{name}.commands"
        module = importlib.import_module(module_name)

        app_name = f"{name}_app"
        if hasattr(module, app_name):
            return getattr(module, app_name)
    except ImportError:
        pass

    # Try global plugin commands
    global_commands_path = GLOBAL_PLUGINS_PATH / name / "commands.py"
    if global_commands_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"global_plugin_commands_{name}",
                global_commands_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                app_name = f"{name}_app"
                if hasattr(module, app_name):
                    return getattr(module, app_name)
                if hasattr(module, "app"):
                    return getattr(module, "app")
        except Exception:
            pass

    # Try project plugin commands
    project_commands_path = PROJECT_PLUGINS_DIR / name / "commands.py"
    if project_commands_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"project_plugin_commands_{name}",
                project_commands_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                app_name = f"{name}_app"
                if hasattr(module, app_name):
                    return getattr(module, app_name)
                if hasattr(module, "app"):
                    return getattr(module, "app")
        except Exception:
            pass

    return None


def get_enabled_plugin_commands(config: dict) -> Dict[str, Any]:
    """
    Get CLI commands for all enabled plugins.

    Args:
        config: Full config dict

    Returns:
        Dict of plugin_name -> typer_app
    """
    commands = {}
    plugins_config = config.get("plugins", {})
    enabled = plugins_config.get("enabled", [])

    for name in enabled:
        app = get_plugin_commands(name)
        if app:
            commands[name] = app

    return commands


def get_plugin_shortcuts(name: str) -> Dict[str, Any]:
    """
    Get shortcut commands from a plugin.

    Args:
        name: Plugin name

    Returns:
        Dict of shortcut_name -> command_function
    """
    shortcuts = {}

    # Try builtin
    try:
        module_name = f"redgit.plugins.{name}.commands"
        module = importlib.import_module(module_name)

        for attr_name in dir(module):
            if attr_name.endswith("_shortcut"):
                shortcut_name = attr_name.replace("_shortcut", "")
                shortcuts[shortcut_name] = getattr(module, attr_name)
    except ImportError:
        pass

    # Try global plugin
    global_commands_path = GLOBAL_PLUGINS_PATH / name / "commands.py"
    if global_commands_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"global_plugin_shortcuts_{name}",
                global_commands_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for attr_name in dir(module):
                    if attr_name.endswith("_shortcut"):
                        shortcut_name = attr_name.replace("_shortcut", "")
                        shortcuts[shortcut_name] = getattr(module, attr_name)
        except Exception:
            pass

    return shortcuts


def get_all_plugin_shortcuts(config: dict) -> Dict[str, Any]:
    """
    Get all shortcut commands from enabled plugins.

    Args:
        config: Full config dict

    Returns:
        Dict of shortcut_name -> command_function
    """
    all_shortcuts = {}
    plugins_config = config.get("plugins", {})
    enabled = plugins_config.get("enabled", [])

    for name in enabled:
        shortcuts = get_plugin_shortcuts(name)
        all_shortcuts.update(shortcuts)

    return all_shortcuts