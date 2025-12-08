"""
Base classes for integrations.

Integration Types:
- task_management: Jira, Linear, Asana, GitHub Issues
- code_hosting: GitHub, GitLab, Bitbucket
- notification: Slack, Discord
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum


class IntegrationType(Enum):
    TASK_MANAGEMENT = "task_management"
    CODE_HOSTING = "code_hosting"
    NOTIFICATION = "notification"
    ANALYSIS = "analysis"


@dataclass
class Issue:
    """Standardized issue representation across task management systems"""
    key: str              # e.g., "SCRUM-123", "LINEAR-456"
    summary: str          # Issue title
    description: str      # Issue description
    status: str           # e.g., "To Do", "In Progress", "Done"
    issue_type: str       # e.g., "task", "bug", "story"
    assignee: Optional[str] = None
    url: Optional[str] = None
    sprint: Optional[str] = None
    story_points: Optional[float] = None
    labels: Optional[List[str]] = None


@dataclass
class Sprint:
    """Standardized sprint representation"""
    id: str
    name: str
    state: str            # "active", "future", "closed"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    goal: Optional[str] = None


class IntegrationBase(ABC):
    """Base class for all integrations"""

    name: str = "base"
    integration_type: IntegrationType = None

    def __init__(self):
        self.enabled = False

    @abstractmethod
    def setup(self, config: dict):
        """Initialize integration with config"""
        pass

    def on_commit(self, group: dict, context: dict):
        """Hook called after each commit (optional)"""
        pass


class TaskManagementBase(IntegrationBase):
    """
    Base class for task management integrations.

    All task management integrations (Jira, Linear, Asana, etc.)
    must implement these methods to work with redgit.
    """

    integration_type = IntegrationType.TASK_MANAGEMENT

    # Project/workspace identifier
    project_key: str = ""

    @abstractmethod
    def get_my_active_issues(self) -> List[Issue]:
        """
        Get issues assigned to current user that are active.
        Active = In Progress, To Do, or in current sprint.

        Returns:
            List of Issue objects
        """
        pass

    @abstractmethod
    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """
        Get a single issue by key.

        Args:
            issue_key: Issue identifier (e.g., "SCRUM-123")

        Returns:
            Issue object or None if not found
        """
        pass

    @abstractmethod
    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        story_points: Optional[float] = None
    ) -> Optional[str]:
        """
        Create a new issue.

        Args:
            summary: Issue title
            description: Issue description
            issue_type: Type of issue (task, bug, story, etc.)
            story_points: Optional story points estimate

        Returns:
            Issue key (e.g., "SCRUM-123") or None if failed
        """
        pass

    @abstractmethod
    def add_comment(self, issue_key: str, comment: str) -> bool:
        """
        Add a comment to an issue.

        Args:
            issue_key: Issue identifier
            comment: Comment text

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def transition_issue(self, issue_key: str, status: str) -> bool:
        """
        Change issue status.

        Args:
            issue_key: Issue identifier
            status: Target status name (e.g., "In Progress", "Done")

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def format_branch_name(self, issue_key: str, description: str) -> str:
        """
        Format a git branch name for an issue.

        Args:
            issue_key: Issue identifier
            description: Short description for branch name

        Returns:
            Formatted branch name (e.g., "feature/SCRUM-123-add-login")
        """
        pass

    def get_commit_prefix(self) -> str:
        """Get prefix for commit messages (e.g., project key)"""
        return self.project_key

    # Optional methods for sprint-based systems

    def supports_sprints(self) -> bool:
        """Whether this integration supports sprints"""
        return False

    def get_active_sprint(self) -> Optional[Sprint]:
        """Get currently active sprint (if supported)"""
        return None

    def get_sprint_issues(self, sprint_id: str = None) -> List[Issue]:
        """Get issues in a sprint (if supported)"""
        return []

    def add_issue_to_sprint(self, issue_key: str, sprint_id: str) -> bool:
        """Add issue to a sprint (if supported)"""
        return False


class CodeHostingBase(IntegrationBase):
    """
    Base class for code hosting integrations.

    Handles PR/MR creation, branch management, etc.
    """

    integration_type = IntegrationType.CODE_HOSTING

    @abstractmethod
    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str
    ) -> Optional[str]:
        """
        Create a pull/merge request.

        Returns:
            PR URL or None if failed
        """
        pass

    @abstractmethod
    def push_branch(self, branch_name: str) -> bool:
        """
        Push a branch to remote.

        Returns:
            True if successful
        """
        pass

    def get_default_branch(self) -> str:
        """Get default base branch name"""
        return "main"


class NotificationBase(IntegrationBase):
    """
    Base class for notification integrations.

    Sends notifications to Slack, Discord, etc.
    """

    integration_type = IntegrationType.NOTIFICATION

    @abstractmethod
    def send_message(self, message: str, channel: str = None) -> bool:
        """
        Send a notification message.

        Returns:
            True if successful
        """
        pass


class AnalysisBase(IntegrationBase):
    """
    Base class for analysis integrations.

    Analyzes project structure, generates task plans, etc.
    """

    integration_type = IntegrationType.ANALYSIS

    # Optional linked task management integration
    task_management: Optional[str] = None

    @abstractmethod
    def analyze(self, path: str = ".") -> Dict[str, Any]:
        """
        Analyze project structure and return analysis results.

        Returns:
            Analysis results dict
        """
        pass

    @abstractmethod
    def get_analysis(self) -> Optional[Dict[str, Any]]:
        """
        Get stored analysis results.

        Returns:
            Stored analysis or None
        """
        pass

    @abstractmethod
    def generate_plan(self, analysis: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Generate task plan from analysis.

        Returns:
            List of task dicts with dependencies, estimates, etc.
        """
        pass


# Backward compatibility alias
Integration = IntegrationBase