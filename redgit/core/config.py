from pathlib import Path
from typing import Optional, Any, List
import yaml

from .constants import (
    DEFAULT_QUALITY_THRESHOLD,
    SEMGREP_TIMEOUT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_LOG_FILES,
)

# Global RedGit directory (shared across all projects)
GLOBAL_REDGIT_DIR = Path.home() / ".redgit"
GLOBAL_TAPS_DIR = GLOBAL_REDGIT_DIR / "taps"
GLOBAL_INTEGRATIONS_DIR = GLOBAL_REDGIT_DIR / "integrations"
GLOBAL_PLUGINS_DIR = GLOBAL_REDGIT_DIR / "plugins"
GLOBAL_TAP_REGISTRY = GLOBAL_REDGIT_DIR / "taps.json"

# Project-specific RedGit directory
RETGIT_DIR = Path(".redgit")
CONFIG_PATH = RETGIT_DIR / "config.yaml"
STATE_PATH = RETGIT_DIR / "state.yaml"


def ensure_global_dirs():
    """Ensure global RedGit directories exist."""
    GLOBAL_REDGIT_DIR.mkdir(exist_ok=True)
    GLOBAL_TAPS_DIR.mkdir(exist_ok=True)
    GLOBAL_INTEGRATIONS_DIR.mkdir(exist_ok=True)
    GLOBAL_PLUGINS_DIR.mkdir(exist_ok=True)

# Default workflow configuration
DEFAULT_WORKFLOW = {
    "strategy": "local-merge",      # local-merge | merge-request
    "auto_transition": True,        # Auto transition issues (In Progress on commit, Done on push)
    "create_missing_issues": "ask", # ask | auto | skip
    "default_issue_type": "task",   # Default type for new issues
}

# Default notification settings
DEFAULT_NOTIFICATIONS = {
    "enabled": True,                # Master switch for all notifications
    "events": {
        "push": True,               # Notify on push completion
        "pr_created": True,         # Notify on PR creation
        "issue_completed": True,    # Notify on issue completion
        "issue_created": True,      # Notify on issue creation
        "commit": False,            # Notify on each commit (can be noisy)
        "session_complete": True,   # Notify on session completion
        "ci_success": True,         # Notify on CI/CD success
        "ci_failure": True,         # Notify on CI/CD failure
        "quality_failed": True,     # Notify on quality check failure
    }
}

# Default code quality settings
DEFAULT_QUALITY = {
    "enabled": False,               # Master switch for quality checks
    "threshold": DEFAULT_QUALITY_THRESHOLD,  # Minimum score (0-100) to pass
    "fail_on_security": True,       # Always fail on critical/high security issues
    "prompt_file": "quality_prompt.md",  # Prompt template file name
}

# Default Semgrep settings
DEFAULT_SEMGREP = {
    "enabled": False,               # Master switch for Semgrep analysis
    "configs": ["auto"],            # Semgrep configs: auto, p/security-audit, p/python, etc.
    "severity": ["ERROR", "WARNING"],  # Minimum severity: ERROR, WARNING, INFO
    "exclude": [],                  # Paths to exclude
    "timeout": SEMGREP_TIMEOUT,     # Timeout in seconds
}

# Default logging settings
DEFAULT_LOGGING = {
    "enabled": True,                # Master switch for file logging
    "level": DEFAULT_LOG_LEVEL,     # Log level: DEBUG, INFO, WARNING, ERROR
    "file": True,                   # Log to file (.redgit/logs/)
    "console": True,                # Log to console
    "max_files": DEFAULT_MAX_LOG_FILES,  # Keep last N log files
}


class ConfigManager:
    def __init__(self):
        RETGIT_DIR.mkdir(exist_ok=True)

    def load(self) -> dict:
        """Load configuration from config.yaml"""
        if CONFIG_PATH.exists():
            config = yaml.safe_load(CONFIG_PATH.read_text()) or {}
        else:
            config = {}

        # Ensure workflow defaults
        if "workflow" not in config:
            config["workflow"] = DEFAULT_WORKFLOW.copy()
        else:
            for key, value in DEFAULT_WORKFLOW.items():
                if key not in config["workflow"]:
                    config["workflow"][key] = value

        return config

    def save(self, config: dict):
        """Save configuration to config.yaml"""
        CONFIG_PATH.write_text(yaml.dump(config, allow_unicode=True, sort_keys=False))

    def get_active_integration(self, integration_type: str) -> Optional[str]:
        """
        Get the active integration name for a given type.

        Args:
            integration_type: 'task_management', 'code_hosting', 'notification'

        Returns:
            Integration name or None
        """
        config = self.load()
        active = config.get("active", {})
        return active.get(integration_type)

    def set_active_integration(self, integration_type: str, name: str):
        """Set the active integration for a given type."""
        config = self.load()
        if "active" not in config:
            config["active"] = {}
        config["active"][integration_type] = name
        self.save(config)

    def get_notifications_config(self) -> dict:
        """Get notification settings with defaults."""
        config = self.load()
        notifications = config.get("notifications", {})

        # Merge with defaults
        result = DEFAULT_NOTIFICATIONS.copy()
        result["enabled"] = notifications.get("enabled", DEFAULT_NOTIFICATIONS["enabled"])

        # Merge events
        result["events"] = DEFAULT_NOTIFICATIONS["events"].copy()
        if "events" in notifications:
            result["events"].update(notifications["events"])

        return result

    def is_notification_enabled(self, event: str) -> bool:
        """Check if a specific notification event is enabled."""
        notifications = self.get_notifications_config()

        # Master switch
        if not notifications.get("enabled", True):
            return False

        # Event-specific setting
        events = notifications.get("events", {})
        return events.get(event, True)

    def get_value(self, path: str) -> Any:
        """
        Get a config value by dot-notation path.

        Example: get_value("integrations.scout.enabled")
        """
        config = self.load()
        keys = path.split(".")
        value = config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def set_value(self, path: str, value: Any) -> bool:
        """
        Set a config value by dot-notation path.

        Example: set_value("integrations.scout.enabled", False)
        """
        config = self.load()
        keys = path.split(".")

        # Navigate to parent
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Convert string values to appropriate types
        final_value = self._parse_value(value)
        current[keys[-1]] = final_value

        self.save(config)
        return True

    def _parse_value(self, value: Any) -> Any:
        """Parse string value to appropriate type."""
        if isinstance(value, str):
            # Boolean
            if value.lower() in ("true", "yes", "on", "1"):
                return True
            if value.lower() in ("false", "no", "off", "0"):
                return False
            # None
            if value.lower() in ("null", "none", "~"):
                return None
            # Number
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except ValueError:
                pass
        return value

    def get_section(self, section: str = None) -> dict:
        """
        Get a section of config or entire config.

        Example: get_section("plugins") or get_section() for full config
        """
        config = self.load()
        if not section:
            return config

        keys = section.split(".")
        value = config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return {}

        return value if isinstance(value, dict) else {section.split(".")[-1]: value}

    def list_keys(self, section: str = None) -> List[str]:
        """List all keys in a section."""
        data = self.get_section(section)
        if isinstance(data, dict):
            return list(data.keys())
        return []

    def register_notification_events(self, events: dict):
        """
        Register custom notification events from an integration.

        Args:
            events: Dict of event definitions
                   {"event_name": {"description": "...", "default": True/False}}
        """
        if not events:
            return

        config = self.load()

        # Ensure notifications.events exists
        if "notifications" not in config:
            config["notifications"] = {}
        if "events" not in config["notifications"]:
            config["notifications"]["events"] = {}

        # Add new events with their default values
        changed = False
        for event_name, event_def in events.items():
            if event_name not in config["notifications"]["events"]:
                default_value = event_def.get("default", True)
                config["notifications"]["events"][event_name] = default_value
                changed = True

        if changed:
            self.save(config)

    def get_all_notification_events(self) -> dict:
        """
        Get all notification events including custom ones.

        Returns:
            Dict of all events with their enabled status and descriptions
        """
        config = self.load()

        # Start with defaults
        result = {}
        for event, default in DEFAULT_NOTIFICATIONS["events"].items():
            result[event] = {
                "enabled": config.get("notifications", {}).get("events", {}).get(event, default),
                "description": self._get_event_description(event),
                "default": default
            }

        # Add custom events from config
        custom_events = config.get("notifications", {}).get("events", {})
        for event, enabled in custom_events.items():
            if event not in result:
                result[event] = {
                    "enabled": enabled,
                    "description": f"Custom: {event}",
                    "default": True
                }

        return result

    def _get_event_description(self, event: str) -> str:
        """Get description for a standard event."""
        descriptions = {
            "push": "Push completed",
            "pr_created": "PR created",
            "issue_completed": "Issue marked as Done",
            "issue_created": "Issue created",
            "commit": "Commit created",
            "session_complete": "Session completed",
            "ci_success": "CI/CD success",
            "ci_failure": "CI/CD failure",
            "ci_triggered": "CI/CD triggered",
            "deploy_started": "Deployment started",
            "deploy_success": "Deployment succeeded",
            "deploy_failure": "Deployment failed",
            "quality_failed": "Code quality check failed",
        }
        return descriptions.get(event, event.replace("_", " ").title())

    def get_quality_config(self) -> dict:
        """Get code quality settings with defaults."""
        config = self.load()
        quality = config.get("quality", {})

        # Merge with defaults
        result = DEFAULT_QUALITY.copy()
        for key in DEFAULT_QUALITY:
            if key in quality:
                result[key] = quality[key]

        return result

    def is_quality_enabled(self) -> bool:
        """Check if code quality checks are enabled."""
        quality = self.get_quality_config()
        return quality.get("enabled", False)

    def get_quality_threshold(self) -> int:
        """Get the minimum quality score threshold."""
        quality = self.get_quality_config()
        return quality.get("threshold", 70)

    def set_quality_enabled(self, enabled: bool):
        """Enable or disable quality checks."""
        config = self.load()
        if "quality" not in config:
            config["quality"] = DEFAULT_QUALITY.copy()
        config["quality"]["enabled"] = enabled
        self.save(config)

    def set_quality_threshold(self, threshold: int):
        """Set the quality score threshold."""
        config = self.load()
        if "quality" not in config:
            config["quality"] = DEFAULT_QUALITY.copy()
        config["quality"]["threshold"] = max(0, min(100, threshold))
        self.save(config)

    # Semgrep configuration methods
    def get_semgrep_config(self) -> dict:
        """Get Semgrep settings with defaults."""
        config = self.load()
        semgrep = config.get("semgrep", {})

        # Merge with defaults
        result = DEFAULT_SEMGREP.copy()
        for key in DEFAULT_SEMGREP:
            if key in semgrep:
                result[key] = semgrep[key]

        return result

    def is_semgrep_enabled(self) -> bool:
        """Check if Semgrep analysis is enabled."""
        semgrep = self.get_semgrep_config()
        return semgrep.get("enabled", False)

    def set_semgrep_enabled(self, enabled: bool):
        """Enable or disable Semgrep analysis."""
        config = self.load()
        if "semgrep" not in config:
            config["semgrep"] = DEFAULT_SEMGREP.copy()
        config["semgrep"]["enabled"] = enabled
        self.save(config)

    def get_semgrep_configs(self) -> List[str]:
        """Get Semgrep rule configs."""
        semgrep = self.get_semgrep_config()
        return semgrep.get("configs", ["auto"])

    def set_semgrep_configs(self, configs: List[str]):
        """Set Semgrep rule configs."""
        config = self.load()
        if "semgrep" not in config:
            config["semgrep"] = DEFAULT_SEMGREP.copy()
        config["semgrep"]["configs"] = configs
        self.save(config)

    def add_semgrep_config(self, config_name: str):
        """Add a Semgrep rule config."""
        configs = self.get_semgrep_configs()
        if config_name not in configs:
            configs.append(config_name)
            self.set_semgrep_configs(configs)

    def remove_semgrep_config(self, config_name: str):
        """Remove a Semgrep rule config."""
        configs = self.get_semgrep_configs()
        if config_name in configs:
            configs.remove(config_name)
            self.set_semgrep_configs(configs)

    # Logging configuration methods
    def get_logging_config(self) -> dict:
        """Get logging settings with defaults."""
        config = self.load()
        logging = config.get("logging", {})

        # Merge with defaults
        result = DEFAULT_LOGGING.copy()
        for key in DEFAULT_LOGGING:
            if key in logging:
                result[key] = logging[key]

        return result

    def is_logging_enabled(self) -> bool:
        """Check if file logging is enabled."""
        logging = self.get_logging_config()
        return logging.get("enabled", True)

    def get_log_level(self) -> str:
        """Get the configured log level."""
        logging = self.get_logging_config()
        return logging.get("level", "INFO")

    def set_logging_enabled(self, enabled: bool):
        """Enable or disable file logging."""
        config = self.load()
        if "logging" not in config:
            config["logging"] = DEFAULT_LOGGING.copy()
        config["logging"]["enabled"] = enabled
        self.save(config)

    def set_log_level(self, level: str):
        """Set the log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {level}. Must be one of {valid_levels}")
        config = self.load()
        if "logging" not in config:
            config["logging"] = DEFAULT_LOGGING.copy()
        config["logging"]["level"] = level.upper()
        self.save(config)


class StateManager:
    """Manages session state for redgit operations."""

    def __init__(self):
        RETGIT_DIR.mkdir(exist_ok=True)

    def load(self) -> dict:
        """Load state from state.yaml"""
        if STATE_PATH.exists():
            return yaml.safe_load(STATE_PATH.read_text()) or {}
        return {}

    def save(self, state: dict):
        """Save state to state.yaml"""
        STATE_PATH.write_text(yaml.dump(state, allow_unicode=True, sort_keys=False))

    def clear(self):
        """Clear state file"""
        if STATE_PATH.exists():
            STATE_PATH.unlink()

    def add_session_branch(self, branch_name: str, issue_key: Optional[str] = None):
        """Add a branch created in current session."""
        state = self.load()
        if "session" not in state:
            state["session"] = {
                "base_branch": None,
                "branches": [],
                "issues": []
            }

        branch_info = {"branch": branch_name}
        if issue_key:
            branch_info["issue_key"] = issue_key

        state["session"]["branches"].append(branch_info)

        if issue_key and issue_key not in state["session"]["issues"]:
            state["session"]["issues"].append(issue_key)

        self.save(state)

    def set_base_branch(self, branch_name: str):
        """Set the base branch for current session."""
        state = self.load()
        if "session" not in state:
            state["session"] = {
                "base_branch": branch_name,
                "branches": [],
                "issues": []
            }
        else:
            state["session"]["base_branch"] = branch_name
        self.save(state)

    def get_session(self) -> Optional[dict]:
        """Get current session info."""
        state = self.load()
        return state.get("session")

    def clear_session(self):
        """Clear current session."""
        state = self.load()
        if "session" in state:
            del state["session"]
        self.save(state)

    def set_subtask_session(
        self,
        parent_branch: str,
        parent_task: str,
        subtasks: list,
        subtask_branches: list
    ):
        """
        Set subtask mode session data.

        Args:
            parent_branch: Parent task branch name
            parent_task: Parent task key (e.g., SCRUM-858)
            subtasks: List of created subtask keys
            subtask_branches: List of subtask branch info dicts
        """
        state = self.load()
        if "session" not in state:
            state["session"] = {
                "base_branch": None,
                "branches": [],
                "issues": []
            }

        state["session"]["subtask_data"] = {
            "subtask_mode": True,
            "parent_branch": parent_branch,
            "parent_task": parent_task,
            "subtasks": subtasks,
            "subtask_branches": subtask_branches
        }
        self.save(state)

    def is_subtask_session(self) -> bool:
        """Check if current session is in subtask mode."""
        session = self.get_session()
        if not session:
            return False
        return session.get("subtask_data", {}).get("subtask_mode", False)

    def get_subtask_data(self) -> Optional[dict]:
        """Get subtask session data if in subtask mode."""
        session = self.get_session()
        if not session:
            return None
        return session.get("subtask_data")

    # Propose usage tracking methods
    def add_propose_usage(self, params: List[str]):
        """Track propose command usage pattern.

        Args:
            params: List of parameter names used (e.g., ["-t", "--subtasks"])
        """
        state = self.load()
        if "propose_history" not in state:
            state["propose_history"] = []
        state["propose_history"].insert(0, params)
        state["propose_history"] = state["propose_history"][:5]
        self.save(state)

    def get_propose_usage_history(self) -> List[List[str]]:
        """Get last 5 propose command usage patterns."""
        state = self.load()
        return state.get("propose_history", [])

    def get_common_propose_pattern(self) -> Optional[List[str]]:
        """Get common pattern if last 5 usages are identical.

        Returns:
            List of parameter names if all 5 are the same, None otherwise.
        """
        history = self.get_propose_usage_history()
        if len(history) < 5:
            return None
        first_pattern = history[0]
        if all(p == first_pattern for p in history[:5]):
            return first_pattern
        return None