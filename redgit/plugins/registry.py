import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any

# Builtin plugins directory (inside package)
BUILTIN_PLUGINS_DIR = Path(__file__).parent

# Available builtin plugins
# Single file plugins: laravel.py
# Package plugins: version/, changelog/
BUILTIN_PLUGINS = ["laravel", "version", "changelog"]


def detect_project_type() -> list:
    """Detect project type based on files"""
    plugins = []
    if Path("artisan").exists() and Path("composer.json").exists():
        try:
            composer = Path("composer.json").read_text().lower()
            if "laravel/framework" in composer:
                plugins.append("laravel")
        except Exception:
            pass
    if Path("go.mod").exists():
        plugins.append("golang")
    return plugins


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


def load_plugins(config: dict) -> Dict[str, Any]:
    """
    Load enabled plugins from package.

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
    """Load a plugin by name from builtin plugins"""
    # Check for single file plugin (name.py)
    builtin_path = BUILTIN_PLUGINS_DIR / f"{name}.py"
    if builtin_path.exists():
        return _load_plugin_from_file(builtin_path, name)

    # Check for package plugin (name/__init__.py)
    package_path = BUILTIN_PLUGINS_DIR / name / "__init__.py"
    if package_path.exists():
        return _load_plugin_from_file(package_path, name)

    return None


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
    import importlib

    # Try to import commands module from plugin package
    try:
        module_name = f"redgit.plugins.{name}.commands"
        module = importlib.import_module(module_name)

        # Look for {name}_app typer instance
        app_name = f"{name}_app"
        if hasattr(module, app_name):
            return getattr(module, app_name)
    except ImportError:
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
    import importlib

    shortcuts = {}
    try:
        module_name = f"redgit.plugins.{name}.commands"
        module = importlib.import_module(module_name)

        # Look for functions ending with _shortcut
        for attr_name in dir(module):
            if attr_name.endswith("_shortcut"):
                shortcut_name = attr_name.replace("_shortcut", "")
                shortcuts[shortcut_name] = getattr(module, attr_name)
    except ImportError:
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