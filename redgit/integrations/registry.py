"""
Integration registry - dynamically loads and manages integrations.

Supports:
1. Builtin integrations: redgit/integrations/{name}.py or {name}/__init__.py
2. Global integrations: ~/.redgit/integrations/{name}/__init__.py (tap-installed)
3. Project integrations: .redgit/integrations/{name}/__init__.py (custom per-project)

Integration classes must:
- Inherit from IntegrationBase (or TaskManagementBase, CodeHostingBase, etc.)
- Be named {Name}Integration (e.g., JiraIntegration, MyCustomIntegration)
- Have a 'name' class attribute matching the file/folder name
"""

import importlib
import importlib.util
import inspect
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Type

from .base import (
    IntegrationBase,
    IntegrationType,
    TaskManagementBase,
    CodeHostingBase,
    NotificationBase,
    AnalysisBase,
    CICDBase,
    CodeQualityBase
)

from ..core.config import GLOBAL_INTEGRATIONS_DIR

# Builtin integrations directory (inside package)
BUILTIN_INTEGRATIONS_DIR = Path(__file__).parent

# Global integrations directory (tap-installed, shared across projects)
GLOBAL_INTEGRATIONS_PATH = GLOBAL_INTEGRATIONS_DIR

# Project-specific integrations directory (custom per-project)
PROJECT_INTEGRATIONS_DIR = Path(".redgit/integrations")

# Core integrations that come with redgit and should not be shown in
# integration lists or installation prompts. These are always available.
# Note: Scout is now a core command (not an integration), so it's not listed here.
CORE_INTEGRATIONS = set()

# Cache for discovered integrations
_integration_cache: Dict[str, Type[IntegrationBase]] = {}
_discovery_done = False


def _discover_integrations(force: bool = False) -> Dict[str, Type[IntegrationBase]]:
    """
    Discover all available integrations from builtin, global, and project directories.

    Load order (later can override earlier):
    1. Builtin integrations (package)
    2. Global integrations (tap-installed, ~/.redgit/integrations/)
    3. Project integrations (custom per-project, .redgit/integrations/)

    Returns:
        Dict of integration_name -> integration_class
    """
    global _integration_cache, _discovery_done

    if _discovery_done and not force:
        return _integration_cache

    _integration_cache = {}

    # 1. Discover builtin integrations
    _discover_from_directory(BUILTIN_INTEGRATIONS_DIR, is_builtin=True)

    # 2. Discover global integrations (tap-installed)
    if GLOBAL_INTEGRATIONS_PATH.exists():
        _discover_from_directory(GLOBAL_INTEGRATIONS_PATH, is_builtin=False)

    # 3. Discover project-specific integrations (can override global)
    if PROJECT_INTEGRATIONS_DIR.exists():
        _discover_from_directory(PROJECT_INTEGRATIONS_DIR, is_builtin=False)

    _discovery_done = True
    return _integration_cache


def _discover_from_directory(directory: Path, is_builtin: bool = False):
    """Discover integrations from a directory."""
    global _integration_cache

    if not directory.exists():
        return

    # Skip these files/folders
    skip_names = {"__init__", "__pycache__", "base", "registry", "install_schemas"}

    for item in directory.iterdir():
        name = item.stem

        if name.startswith("_") or name in skip_names:
            continue

        # Single file integration: name.py
        if item.suffix == ".py" and item.is_file():
            cls = _load_class_from_file(item, name, is_builtin)
            if cls:
                _integration_cache[name] = cls

        # Package integration: name/__init__.py
        elif item.is_dir() and (item / "__init__.py").exists():
            cls = _load_class_from_file(item / "__init__.py", name, is_builtin)
            if cls:
                _integration_cache[name] = cls


def _load_class_from_file(
    path: Path,
    name: str,
    is_builtin: bool = False
) -> Optional[Type[IntegrationBase]]:
    """Load integration class from a file."""
    try:
        if is_builtin:
            # Use proper module import for builtin integrations
            module_name = f"redgit.integrations.{name}"
            module = importlib.import_module(module_name)
        else:
            # Dynamic import for custom integrations
            spec = importlib.util.spec_from_file_location(
                f"custom_integration_{name}",
                path
            )
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        # Find the integration class
        return _find_integration_class(module, name)

    except Exception:
        return None


def _find_integration_class(module, name: str) -> Optional[Type[IntegrationBase]]:
    """Find the integration class in a module."""
    # Try {Name}Integration first (e.g., JiraIntegration)
    class_name = f"{name.capitalize()}Integration"
    if hasattr(module, class_name):
        cls = getattr(module, class_name)
        if _is_valid_integration_class(cls):
            return cls

    # Try CamelCase name (e.g., MyCustomIntegration for my_custom)
    camel_name = "".join(word.capitalize() for word in name.split("_")) + "Integration"
    if hasattr(module, camel_name):
        cls = getattr(module, camel_name)
        if _is_valid_integration_class(cls):
            return cls

    # Search all classes in module
    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue
        attr = getattr(module, attr_name)
        if _is_valid_integration_class(attr):
            # Verify the class's name attribute matches (normalize hyphens/underscores)
            if hasattr(attr, "name"):
                attr_name_normalized = attr.name.replace("-", "_")
                name_normalized = name.replace("-", "_")
                if attr_name_normalized == name_normalized:
                    return attr

    return None


def _is_valid_integration_class(cls) -> bool:
    """Check if a class is a valid integration class."""
    return (
        inspect.isclass(cls) and
        issubclass(cls, IntegrationBase) and
        cls is not IntegrationBase and
        cls is not TaskManagementBase and
        cls is not CodeHostingBase and
        cls is not NotificationBase and
        cls is not AnalysisBase and
        cls is not CICDBase and
        cls is not CodeQualityBase
    )


# ==================== Public API ====================

def get_integration_class(name: str) -> Optional[Type[IntegrationBase]]:
    """
    Get an integration class by name.

    Args:
        name: Integration name (e.g., "jira", "my_custom")

    Returns:
        Integration class or None
    """
    integrations = _discover_integrations()
    return integrations.get(name)


def get_all_integrations() -> Dict[str, Type[IntegrationBase]]:
    """
    Get all available integrations.

    Returns:
        Dict of integration_name -> integration_class
    """
    return _discover_integrations()


# Alias for consistency with prompt loading
get_all_integration_classes = get_all_integrations


def get_builtin_integrations(include_core: bool = False) -> List[str]:
    """
    List available builtin integration names.

    Args:
        include_core: If True, include core integrations (like scout).
                     If False (default), exclude them for installation lists.
    """
    all_integrations = list(_discover_integrations().keys())
    if include_core:
        return all_integrations
    return [name for name in all_integrations if name not in CORE_INTEGRATIONS]


def get_installable_integrations() -> List[str]:
    """
    List integrations available for installation.
    Excludes core integrations that come with redgit.
    """
    return get_builtin_integrations(include_core=False)


def get_integrations_by_type(integration_type: IntegrationType) -> List[str]:
    """List available integrations of a specific type."""
    integrations = _discover_integrations()
    result = []

    for name, cls in integrations.items():
        if hasattr(cls, "integration_type") and cls.integration_type == integration_type:
            result.append(name)

    return result


def get_integration_type(name: str) -> Optional[IntegrationType]:
    """Get the type of an integration by name."""
    cls = get_integration_class(name)
    if cls and hasattr(cls, "integration_type"):
        return cls.integration_type
    return None


# Backward compatibility
BUILTIN_INTEGRATIONS = property(lambda self: {
    name: cls.integration_type
    for name, cls in _discover_integrations().items()
    if hasattr(cls, "integration_type")
})


def _get_builtin_integrations_dict() -> Dict[str, IntegrationType]:
    """Get dict of integration names to their types."""
    return {
        name: cls.integration_type
        for name, cls in _discover_integrations().items()
        if hasattr(cls, "integration_type")
    }

# For backward compatibility - expose as module-level dict
BUILTIN_INTEGRATIONS = _get_builtin_integrations_dict()


# ==================== Loading Functions ====================

def load_integrations(config: dict) -> Dict[str, IntegrationBase]:
    """
    Load all enabled integrations from config.

    Args:
        config: integrations section from config.yaml

    Returns:
        Dict of integration_name -> integration_instance
    """
    integrations = {}

    for name, cfg in config.items():
        if isinstance(cfg, dict) and cfg.get("enabled", True):
            integration = load_integration_by_name(name, cfg)
            if integration and integration.enabled:
                integrations[name] = integration

    return integrations


def load_integration_by_name(name: str, config: dict) -> Optional[IntegrationBase]:
    """
    Load a specific integration by name.

    Args:
        name: Integration name (e.g., "jira", "github")
        config: Integration config dict

    Returns:
        Integration instance or None
    """
    cls = get_integration_class(name)
    if cls:
        instance = cls()
        instance.setup(config)
        if instance.enabled:
            return instance
    return None


def get_task_management(config: dict, active_name: Optional[str] = None) -> Optional[TaskManagementBase]:
    """
    Get the active task management integration.

    Args:
        config: Full config dict (with 'active' and 'integrations' sections)
        active_name: Override active integration name

    Returns:
        TaskManagementBase instance or None if not configured or disabled
    """
    if not active_name:
        active_name = config.get("active", {}).get("task_management")

    if not active_name or active_name.lower() == "none":
        return None

    integration_config = config.get("integrations", {}).get(active_name, {})

    # Check if explicitly disabled
    if integration_config.get("enabled") is False:
        return None

    integration = load_integration_by_name(active_name, integration_config)

    if integration and isinstance(integration, TaskManagementBase):
        # Double check enabled status after setup
        if not integration.enabled:
            return None
        return integration

    return None


def get_code_hosting(config: dict, active_name: Optional[str] = None) -> Optional[CodeHostingBase]:
    """
    Get the active code hosting integration.

    Args:
        config: Full config dict
        active_name: Override active integration name

    Returns:
        CodeHostingBase instance or None
    """
    if not active_name:
        active_name = config.get("active", {}).get("code_hosting")

    if not active_name:
        return None

    integration_config = config.get("integrations", {}).get(active_name, {})
    integration = load_integration_by_name(active_name, integration_config)

    if integration and isinstance(integration, CodeHostingBase):
        return integration

    return None


def get_analysis(config: dict, active_name: Optional[str] = None) -> Optional[AnalysisBase]:
    """
    Get the active analysis integration.

    Args:
        config: Full config dict
        active_name: Override active integration name

    Returns:
        AnalysisBase instance or None
    """
    if not active_name:
        active_name = config.get("active", {}).get("analysis")

    if not active_name:
        return None

    integration_config = config.get("integrations", {}).get(active_name, {})
    integration = load_integration_by_name(active_name, integration_config)

    if integration and isinstance(integration, AnalysisBase):
        return integration

    return None


def get_notification(config: dict, active_name: Optional[str] = None) -> Optional[NotificationBase]:
    """
    Get the active notification integration.

    This is the primary way other integrations should access notification services.

    Args:
        config: Full config dict
        active_name: Override active integration name

    Returns:
        NotificationBase instance or None

    Example:
        from redgit.integrations.registry import get_notification
        from redgit.core.config import ConfigManager

        config = ConfigManager().load()
        notifier = get_notification(config)

        if notifier:
            notifier.notify(
                event_type="deploy",
                title="Deployment Complete",
                message="v1.2.3 deployed to production",
                level="success"
            )
    """
    if not active_name:
        active_name = config.get("active", {}).get("notification")

    if not active_name:
        return None

    integration_config = config.get("integrations", {}).get(active_name, {})
    integration = load_integration_by_name(active_name, integration_config)

    if integration and isinstance(integration, NotificationBase):
        return integration

    return None


def get_cicd(config: dict, active_name: Optional[str] = None) -> Optional[CICDBase]:
    """
    Get the active CI/CD integration.

    Args:
        config: Full config dict
        active_name: Override active integration name

    Returns:
        CICDBase instance or None

    Example:
        from redgit.integrations.registry import get_cicd
        from redgit.core.config import ConfigManager

        config = ConfigManager().load()
        cicd = get_cicd(config)

        if cicd:
            # Trigger a pipeline
            run = cicd.trigger_pipeline(branch="main")

            # Check status
            status = cicd.get_pipeline_status(run.id)

            # List recent pipelines
            runs = cicd.list_pipelines(limit=5)
    """
    if not active_name:
        active_name = config.get("active", {}).get("ci_cd")

    if not active_name:
        return None

    integration_config = config.get("integrations", {}).get(active_name, {})
    integration = load_integration_by_name(active_name, integration_config)

    if integration and isinstance(integration, CICDBase):
        return integration

    return None


def get_code_quality(config: dict, active_name: Optional[str] = None) -> Optional[CodeQualityBase]:
    """
    Get the active code quality integration.

    Args:
        config: Full config dict
        active_name: Override active integration name

    Returns:
        CodeQualityBase instance or None

    Example:
        from redgit.integrations.registry import get_code_quality
        from redgit.core.config import ConfigManager

        config = ConfigManager().load()
        quality = get_code_quality(config)

        if quality:
            # Get quality status
            status = quality.get_quality_status(branch="main")

            # Get coverage report
            coverage = quality.get_coverage()

            # Get project metrics
            metrics = quality.get_project_metrics()
    """
    if not active_name:
        active_name = config.get("active", {}).get("code_quality")

    if not active_name:
        return None

    integration_config = config.get("integrations", {}).get(active_name, {})
    integration = load_integration_by_name(active_name, integration_config)

    if integration and isinstance(integration, CodeQualityBase):
        return integration

    return None


def send_notification(
    event_type: str,
    title: str,
    message: str = "",
    url: str = None,
    fields: dict = None,
    level: str = "info",
    channel: str = None
) -> bool:
    """
    Convenience function to send a notification through the active notification integration.

    This is the simplest way to send notifications from anywhere in the codebase.

    Args:
        event_type: Type of event (commit, branch, pr, task, deploy, alert, etc.)
        title: Notification title
        message: Notification body
        url: Optional URL
        fields: Optional key-value pairs
        level: info, success, warning, error
        channel: Optional channel override

    Returns:
        True if notification was sent, False if no notification integration or failed

    Example:
        from redgit.integrations.registry import send_notification

        send_notification(
            event_type="commit",
            title="New Commit",
            message="feat: add login",
            fields={"Branch": "main"}
        )
    """
    from ..core.config import ConfigManager

    try:
        config = ConfigManager().load()
        notifier = get_notification(config)

        if notifier:
            return notifier.notify(
                event_type=event_type,
                title=title,
                message=message,
                url=url,
                fields=fields or {},
                level=level,
                channel=channel
            )
    except Exception:
        pass

    return False


# ==================== Dynamic Command Loading ====================

def get_integration_commands(name: str):
    """
    Get CLI commands (typer app) for an integration.

    Looks for:
    1. redgit.integrations.{name}.commands module with {name}_app
    2. redgit.integrations.{name}.cli module with {name}_app
    3. Custom: .redgit/integrations/{name}/commands.py with {name}_app

    Returns:
        typer.Typer instance or None
    """
    # Try builtin first
    for module_suffix in ["commands", "cli"]:
        try:
            module_name = f"redgit.integrations.{name}.{module_suffix}"
            module = importlib.import_module(module_name)

            # Look for {name}_app
            app_name = f"{name}_app"
            if hasattr(module, app_name):
                return getattr(module, app_name)

            # Also try just 'app'
            if hasattr(module, "app"):
                return getattr(module, "app")

        except ImportError:
            continue
        except Exception:
            continue

    # Try global integration commands
    global_commands_path = GLOBAL_INTEGRATIONS_PATH / name / "commands.py"
    if global_commands_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"global_commands_{name}",
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

    # Try project-specific integration commands
    project_commands_path = PROJECT_INTEGRATIONS_DIR / name / "commands.py"
    if project_commands_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"project_commands_{name}",
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


def get_active_integration_commands(config: dict) -> Dict[str, Any]:
    """
    Get CLI commands for all active integrations.

    Args:
        config: Full config dict

    Returns:
        Dict of integration_name -> typer.Typer app
    """
    commands = {}
    active = config.get("active", {})
    integrations_config = config.get("integrations", {})

    # Collect all active integration names
    active_names = set(active.values())

    # Also check enabled integrations
    for name, cfg in integrations_config.items():
        if isinstance(cfg, dict) and cfg.get("enabled"):
            active_names.add(name)

    # Load commands for each active integration
    for name in active_names:
        if name:
            app = get_integration_commands(name)
            if app:
                commands[name] = app

    return commands


def get_all_integration_commands() -> Dict[str, Any]:
    """
    Get CLI commands for all available integrations (regardless of activation).

    Returns:
        Dict of integration_name -> typer.Typer app
    """
    commands = {}

    for name in get_builtin_integrations():
        app = get_integration_commands(name)
        if app:
            commands[name] = app

    return commands


# ==================== Refresh Cache ====================

def refresh_integrations():
    """Force refresh the integration cache (call after adding custom integrations)."""
    global _discovery_done
    _discovery_done = False
    _discover_integrations(force=True)


# ==================== Install Schema Loading ====================

def get_install_schema(name: str) -> Optional[Dict]:
    """
    Get install schema for an integration.

    Looks for (in order):
    1. Builtin package: redgit/integrations/{name}/install_schema.json
    2. Builtin single file: redgit/integrations/{name}_install_schema.json
    3. Global package: ~/.redgit/integrations/{name}/install_schema.json
    4. Project package: .redgit/integrations/{name}/install_schema.json

    Args:
        name: Integration name (e.g., "jira", "github")

    Returns:
        Schema dict or None
    """
    # Check all locations in order
    paths = [
        # Builtin
        BUILTIN_INTEGRATIONS_DIR / name / "install_schema.json",
        BUILTIN_INTEGRATIONS_DIR / f"{name}_install_schema.json",
        # Global (tap-installed)
        GLOBAL_INTEGRATIONS_PATH / name / "install_schema.json",
        # Project-specific
        PROJECT_INTEGRATIONS_DIR / name / "install_schema.json",
    ]

    for path in paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue

    return None


def get_all_install_schemas() -> Dict[str, Dict]:
    """
    Get install schemas for all available integrations.

    Returns:
        Dict of integration_name -> schema_dict
    """
    schemas = {}

    for name in get_builtin_integrations():
        schema = get_install_schema(name)
        if schema:
            schemas[name] = schema

    return schemas