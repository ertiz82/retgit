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