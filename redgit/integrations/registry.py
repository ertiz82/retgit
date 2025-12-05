"""
Integration registry - loads and manages integrations by type.
"""

import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any

from .base import (
    IntegrationBase,
    IntegrationType,
    TaskManagementBase,
    CodeHostingBase,
    NotificationBase
)

# Builtin integrations directory (inside package)
BUILTIN_INTEGRATIONS_DIR = Path(__file__).parent

# Available builtin integrations with their types
BUILTIN_INTEGRATIONS = {
    "jira": IntegrationType.TASK_MANAGEMENT,
    "github": IntegrationType.CODE_HOSTING,
    # Future integrations:
    # "linear": IntegrationType.TASK_MANAGEMENT,
    # "asana": IntegrationType.TASK_MANAGEMENT,
    # "gitlab": IntegrationType.CODE_HOSTING,
    # "slack": IntegrationType.NOTIFICATION,
}


def get_builtin_integrations() -> List[str]:
    """List available builtin integrations"""
    available = []
    for name in BUILTIN_INTEGRATIONS.keys():
        # Check for single file integration (name.py)
        if (BUILTIN_INTEGRATIONS_DIR / f"{name}.py").exists():
            available.append(name)
        # Check for package integration (name/__init__.py)
        elif (BUILTIN_INTEGRATIONS_DIR / name / "__init__.py").exists():
            available.append(name)
    return available


def get_integrations_by_type(integration_type: IntegrationType) -> List[str]:
    """List available integrations of a specific type."""
    available = []
    for name, itype in BUILTIN_INTEGRATIONS.items():
        if itype != integration_type:
            continue
        # Check for single file integration (name.py)
        if (BUILTIN_INTEGRATIONS_DIR / f"{name}.py").exists():
            available.append(name)
        # Check for package integration (name/__init__.py)
        elif (BUILTIN_INTEGRATIONS_DIR / name / "__init__.py").exists():
            available.append(name)
    return available


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
        if isinstance(cfg, dict):
            integration = _load_integration(name)
            if integration:
                integration.setup(cfg)
                if integration.enabled:
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
    integration = _load_integration(name)
    if integration:
        integration.setup(config)
        if integration.enabled:
            return integration
    return None


def get_task_management(config: dict, active_name: Optional[str] = None) -> Optional[TaskManagementBase]:
    """
    Get the active task management integration.

    Args:
        config: Full config dict (with 'active' and 'integrations' sections)
        active_name: Override active integration name

    Returns:
        TaskManagementBase instance or None
    """
    if not active_name:
        active_name = config.get("active", {}).get("task_management")

    if not active_name:
        return None

    integration_config = config.get("integrations", {}).get(active_name, {})
    integration = load_integration_by_name(active_name, integration_config)

    if integration and isinstance(integration, TaskManagementBase):
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


def _load_integration(name: str) -> Optional[IntegrationBase]:
    """Load an integration by name from builtin integrations"""
    # Check for single file integration (name.py)
    builtin_path = BUILTIN_INTEGRATIONS_DIR / f"{name}.py"
    if builtin_path.exists():
        return _load_integration_from_file(builtin_path, name)

    # Check for package integration (name/__init__.py)
    package_path = BUILTIN_INTEGRATIONS_DIR / name / "__init__.py"
    if package_path.exists():
        return _load_integration_from_file(package_path, name)

    return None


def _load_integration_from_file(path: Path, name: str) -> Optional[IntegrationBase]:
    """Load integration from a file path"""
    try:
        spec = importlib.util.spec_from_file_location(f"integration_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for {Name}Integration class
        class_name = f"{name.capitalize()}Integration"
        if hasattr(module, class_name):
            cls = getattr(module, class_name)
            return cls()

    except Exception:
        pass

    return None