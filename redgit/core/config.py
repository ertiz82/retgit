from pathlib import Path
from typing import Optional
import yaml

RETGIT_DIR = Path(".redgit")
CONFIG_PATH = RETGIT_DIR / "config.yaml"
STATE_PATH = RETGIT_DIR / "state.yaml"

# Default workflow configuration
DEFAULT_WORKFLOW = {
    "strategy": "local-merge",      # local-merge | merge-request
    "auto_transition": True,        # Auto transition issues (In Progress on commit, Done on push)
    "create_missing_issues": "ask", # ask | auto | skip
    "default_issue_type": "task",   # Default type for new issues
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