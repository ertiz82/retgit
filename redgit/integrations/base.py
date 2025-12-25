"""
Base classes for integrations.

Integration Types:
- task_management: Jira, Linear, Asana, GitHub Issues
- code_hosting: GitHub, GitLab, Bitbucket
- notification: Slack, Discord
- ci_cd: GitHub Actions, GitLab CI, Jenkins, CircleCI
- code_quality: SonarQube, CodeClimate, Snyk, Codecov
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
    CI_CD = "ci_cd"
    CODE_QUALITY = "code_quality"


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


@dataclass
class PipelineRun:
    """Standardized pipeline/workflow run representation"""
    id: str
    name: str
    status: str           # "pending", "running", "success", "failed", "cancelled"
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    url: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration: Optional[int] = None  # seconds
    trigger: Optional[str] = None   # "push", "pr", "manual", "schedule"


@dataclass
class PipelineJob:
    """Standardized job/step representation within a pipeline"""
    id: str
    name: str
    status: str           # "pending", "running", "success", "failed", "skipped"
    stage: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration: Optional[int] = None
    url: Optional[str] = None
    logs_url: Optional[str] = None


@dataclass
class QualityReport:
    """Standardized code quality report representation"""
    id: str
    status: str           # "passed", "failed", "warning", "pending"
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    url: Optional[str] = None
    analyzed_at: Optional[str] = None
    # Quality metrics
    bugs: Optional[int] = None
    vulnerabilities: Optional[int] = None
    code_smells: Optional[int] = None
    coverage: Optional[float] = None          # percentage (0-100)
    duplications: Optional[float] = None      # percentage
    technical_debt: Optional[str] = None      # e.g., "2h 30min"
    # Quality gate
    quality_gate_status: Optional[str] = None  # "passed", "failed"
    quality_gate_details: Optional[Dict[str, Any]] = None


@dataclass
class SecurityIssue:
    """Standardized security issue/vulnerability representation"""
    id: str
    severity: str         # "critical", "high", "medium", "low", "info"
    title: str
    description: Optional[str] = None
    package: Optional[str] = None         # affected package/dependency
    version: Optional[str] = None         # affected version
    fixed_in: Optional[str] = None        # version with fix
    cve: Optional[str] = None             # CVE identifier
    cwe: Optional[str] = None             # CWE identifier
    url: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class CoverageReport:
    """Standardized code coverage report representation"""
    id: str
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    url: Optional[str] = None
    # Coverage metrics
    line_coverage: Optional[float] = None      # percentage
    branch_coverage: Optional[float] = None    # percentage
    function_coverage: Optional[float] = None  # percentage
    lines_covered: Optional[int] = None
    lines_total: Optional[int] = None
    # Comparison
    coverage_change: Optional[float] = None    # delta from base
    base_coverage: Optional[float] = None


class IntegrationBase(ABC):
    """Base class for all integrations"""

    name: str = "base"
    integration_type: IntegrationType = None

    # Custom notification events this integration can emit
    # Override in subclass to define custom events
    # Format: {"event_name": {"description": "...", "default": True/False}}
    notification_events: Dict[str, Dict[str, Any]] = {}

    def __init__(self):
        self.enabled = False
        self._config = {}

    @abstractmethod
    def setup(self, config: dict):
        """Initialize integration with config"""
        pass

    def set_config(self, config: dict):
        """Store full config for notification access"""
        self._config = config

    def on_commit(self, group: dict, context: dict):
        """Hook called after each commit (optional)"""
        pass

    def notify(self, event: str, message: str, **kwargs) -> bool:
        """
        Send notification for an event if enabled.

        Args:
            event: Event name (must be in notification_events or standard events)
            message: Notification message
            **kwargs: Additional args (url, fields, level, etc.)

        Returns:
            True if notification sent successfully
        """
        from .registry import get_notification
        from ..core.config import ConfigManager

        # Skip if this is a notification integration
        if self.integration_type == IntegrationType.NOTIFICATION:
            return False

        # Check if event is enabled
        config_manager = ConfigManager()
        if not config_manager.is_notification_enabled(event):
            return False

        # Get notification integration
        notification = get_notification(self._config)
        if not notification or not notification.enabled:
            return False

        try:
            # Use structured notify if available
            if hasattr(notification, 'notify') and kwargs:
                return notification.notify(
                    event_type=event,
                    title=kwargs.get('title', event),
                    message=message,
                    url=kwargs.get('url'),
                    fields=kwargs.get('fields'),
                    level=kwargs.get('level', 'info')
                )
            else:
                return notification.send_message(message)
        except Exception:
            return False

    @classmethod
    def get_notification_events(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get all notification events this integration can emit.

        Returns:
            Dict of event definitions
        """
        return cls.notification_events

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """
        Hook called after integration install, before saving config.

        Override this to auto-detect fields, validate settings, etc.

        Args:
            config_values: Dict of collected config values from user input

        Returns:
            Updated config_values dict (can add/modify fields)

        Example:
            @staticmethod
            def after_install(config_values: dict) -> dict:
                # Auto-detect some field
                detected_value = detect_something(config_values)
                if detected_value:
                    config_values["some_field"] = detected_value
                return config_values
        """
        return config_values

    @classmethod
    def get_prompts(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get exportable prompts for this integration.

        Override this to provide custom prompts that users can export and customize.
        The response schema/format sections should NOT be included - RedGit manages those.

        Returns:
            Dict mapping prompt names to prompt definitions:
            {
                "prompt_name": {
                    "description": "What this prompt does",
                    "content": "The actual prompt template content...",
                    "variables": ["VAR1", "VAR2"],  # Variables that will be replaced
                }
            }

        Example:
            @classmethod
            def get_prompts(cls) -> Dict[str, Dict[str, Any]]:
                return {
                    "issue_title": {
                        "description": "Generate issue titles from code changes",
                        "content": "Generate a title for this change...\\n{{FILES}}",
                        "variables": ["FILES", "ISSUE_LANGUAGE"]
                    }
                }
        """
        return {}

    @classmethod
    def get_prompt(cls, name: str) -> Optional[str]:
        """
        Get a specific prompt by name.

        First checks for user-customized version in .redgit/templates/,
        then falls back to built-in prompt.

        Args:
            name: Prompt name (without .md extension)

        Returns:
            Prompt content or None if not found
        """
        from ..core.config import RETGIT_DIR

        # Check for user-customized prompt first
        custom_path = RETGIT_DIR / "templates" / f"{cls.name}_{name}.md"
        if custom_path.exists():
            return custom_path.read_text(encoding="utf-8")

        # Fall back to built-in prompt
        prompts = cls.get_prompts()
        if name in prompts:
            return prompts[name].get("content")

        return None


class TaskManagementBase(IntegrationBase):
    """
    Base class for task management integrations.

    All task management integrations (Jira, Linear, Asana, etc.)
    must implement these methods to work with redgit.

    Prompt System:
    - Each integration can have its own prompts for generating task titles/descriptions
    - Prompts are loaded from:
      1. User exported: .redgit/prompts/integrations/{integration_name}/
      2. Built-in: redgit/integrations/{integration_name}/prompts/
    - Available prompts: issue_title.md, issue_description.md
    """

    integration_type = IntegrationType.TASK_MANAGEMENT

    # Project/workspace identifier
    project_key: str = ""

    # Language for generated content (e.g., "tr", "en", "de")
    issue_language: str = "en"

    def has_user_prompt(self, prompt_name: str) -> bool:
        """
        Check if user has exported a custom prompt for this integration.

        Args:
            prompt_name: Name of the prompt (e.g., "issue_title", "issue_description")

        Returns:
            True if user has a custom prompt file
        """
        from pathlib import Path
        from ..core.config import RETGIT_DIR

        user_prompt_path = RETGIT_DIR / "prompts" / "integrations" / self.name / f"{prompt_name}.md"
        return user_prompt_path.exists()

    def get_user_prompt(self, prompt_name: str) -> Optional[str]:
        """
        Get ONLY user-exported prompt (not built-in fallback).

        Args:
            prompt_name: Name of the prompt (e.g., "issue_title", "issue_description")

        Returns:
            User's custom prompt string or None if not exported
        """
        from pathlib import Path
        from ..core.config import RETGIT_DIR

        user_prompt_path = RETGIT_DIR / "prompts" / "integrations" / self.name / f"{prompt_name}.md"
        if user_prompt_path.exists():
            return user_prompt_path.read_text(encoding='utf-8')
        return None

    def get_prompt(self, prompt_name: str) -> Optional[str]:
        """
        Get a prompt template for this integration.

        Looks for prompts in order:
        1. User exported: .redgit/prompts/integrations/{name}/{prompt_name}.md
        2. Built-in: (integration's own prompts directory)

        Args:
            prompt_name: Name of the prompt (e.g., "issue_title", "issue_description")

        Returns:
            Prompt template string or None if not found
        """
        # User exported prompts first
        user_prompt = self.get_user_prompt(prompt_name)
        if user_prompt:
            return user_prompt

        # Built-in prompts (integration can override this)
        builtin_prompt = self._get_builtin_prompt(prompt_name)
        if builtin_prompt:
            return builtin_prompt

        return None

    def _get_builtin_prompt(self, prompt_name: str) -> Optional[str]:
        """
        Get built-in prompt for this integration.
        Override in subclasses to provide integration-specific prompts.
        """
        # Default prompts
        default_prompts = {
            "issue_title": """Generate a clear, concise issue title for a task management system.

## Context
- Commit title: {commit_title}
- Files changed: {file_count}

## Requirements
- Title should be clear and actionable
- Language: {language}
- Max 100 characters

## Response
Return ONLY the issue title text, nothing else.
""",
            "issue_description": """Generate a detailed issue description for a task management system.

## Context
- Commit title: {commit_title}
- Commit body: {commit_body}
- Files changed:
{files}

## Code Changes (Diff)
```diff
{diff}
```

## Requirements
- Description should explain what was changed and why
- Use bullet points for clarity
- Language: {language}
- Include technical details relevant to developers

## Response
Return ONLY the issue description text, nothing else.
"""
        }
        return default_prompts.get(prompt_name)

    def generate_issue_content(
        self,
        commit_info: dict,
        diff: str = "",
        llm_client=None
    ) -> dict:
        """
        Generate issue title and description using integration prompts and LLM.

        Args:
            commit_info: Dict with commit_title, commit_body, files
            diff: Git diff of the changes
            llm_client: LLM client instance (optional, will create if not provided)

        Returns:
            Dict with 'title' and 'description' keys
        """
        result = {
            "title": commit_info.get("commit_title", "")[:100],
            "description": commit_info.get("commit_body", "")
        }

        # Get language name
        lang_names = {
            "tr": "Turkish",
            "en": "English",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "pt": "Portuguese",
            "it": "Italian",
            "ru": "Russian",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean"
        }
        language = lang_names.get(self.issue_language, self.issue_language)

        # If no LLM client, return defaults
        if not llm_client:
            return result

        files = commit_info.get("files", [])
        file_list = "\n".join(f"- {f}" for f in files[:20])
        if len(files) > 20:
            file_list += f"\n... and {len(files) - 20} more"

        # Generate title
        title_prompt = self.get_prompt("issue_title")
        if title_prompt:
            try:
                formatted_prompt = title_prompt.format(
                    commit_title=commit_info.get("commit_title", ""),
                    file_count=len(files),
                    language=language
                )
                generated_title = llm_client.chat(formatted_prompt)
                if generated_title:
                    result["title"] = generated_title.strip()[:100]
            except Exception:
                pass

        # Generate description
        desc_prompt = self.get_prompt("issue_description")
        if desc_prompt:
            try:
                # Truncate diff if too long
                truncated_diff = diff[:5000] if diff else ""
                if len(diff) > 5000:
                    truncated_diff += "\n... (diff truncated)"

                formatted_prompt = desc_prompt.format(
                    commit_title=commit_info.get("commit_title", ""),
                    commit_body=commit_info.get("commit_body", ""),
                    files=file_list,
                    diff=truncated_diff,
                    language=language
                )
                generated_desc = llm_client.chat(formatted_prompt)
                if generated_desc:
                    result["description"] = generated_desc.strip()
            except Exception:
                pass

        return result

    def export_prompts(self, target_dir: str = None) -> List[str]:
        """
        Export integration prompts to user's .redgit/prompts/integrations/{name}/ directory.

        Args:
            target_dir: Optional target directory (defaults to .redgit/prompts/integrations/{name}/)

        Returns:
            List of exported file paths
        """
        from pathlib import Path
        from ..core.config import RETGIT_DIR

        if target_dir:
            prompts_dir = Path(target_dir)
        else:
            prompts_dir = RETGIT_DIR / "prompts" / "integrations" / self.name

        prompts_dir.mkdir(parents=True, exist_ok=True)

        exported = []
        for prompt_name in ["issue_title", "issue_description"]:
            content = self._get_builtin_prompt(prompt_name)
            if content:
                file_path = prompts_dir / f"{prompt_name}.md"
                file_path.write_text(content, encoding='utf-8')
                exported.append(str(file_path))

        return exported

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
        story_points: Optional[float] = None,
        parent_key: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a new issue.

        Args:
            summary: Issue title
            description: Issue description
            issue_type: Type of issue (task, bug, story, subtask, etc.)
            story_points: Optional story points estimate
            parent_key: Parent issue key for subtasks (e.g., "SCRUM-123")

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

    Sends notifications to Slack, Discord, Teams, Discord, etc.

    All notification integrations must implement the standard notify() method
    so other integrations can send notifications through them.
    """

    integration_type = IntegrationType.NOTIFICATION

    @abstractmethod
    def send_message(self, message: str, channel: str = None) -> bool:
        """
        Send a simple text notification message.

        Args:
            message: Message text
            channel: Optional channel/room override

        Returns:
            True if successful
        """
        pass

    def notify(
        self,
        event_type: str,
        title: str,
        message: str = "",
        url: str = None,
        fields: Dict[str, str] = None,
        level: str = "info",
        channel: str = None
    ) -> bool:
        """
        Send a structured notification. This is the standard interface
        that other integrations should use.

        Args:
            event_type: Type of event (commit, branch, pr, task, deploy, alert, etc.)
            title: Notification title
            message: Notification body/description
            url: Optional URL to link to
            fields: Optional key-value pairs to display
            level: Notification level (info, success, warning, error)
            channel: Optional channel override

        Returns:
            True if successful

        Example:
            notify(
                event_type="commit",
                title="New commit on main",
                message="feat: add user authentication",
                fields={"Branch": "main", "Author": "developer"},
                level="success"
            )
        """
        # Default implementation - subclasses should override for rich formatting
        text = f"[{event_type.upper()}] {title}"
        if message:
            text += f"\n{message}"
        if fields:
            text += "\n" + "\n".join(f"{k}: {v}" for k, v in fields.items())
        if url:
            text += f"\n{url}"

        return self.send_message(text, channel=channel)

    def notify_commit(
        self,
        branch: str,
        message: str,
        author: str = None,
        files: List[str] = None,
        url: str = None
    ) -> bool:
        """Convenience method for commit notifications."""
        fields = {"Branch": branch}
        if author:
            fields["Author"] = author
        if files:
            fields["Files"] = str(len(files))

        return self.notify(
            event_type="commit",
            title="New Commit",
            message=message,
            url=url,
            fields=fields,
            level="info"
        )

    def notify_branch(self, branch_name: str, issue_key: str = None) -> bool:
        """Convenience method for branch creation notifications."""
        fields = {"Branch": branch_name}
        if issue_key:
            fields["Issue"] = issue_key

        return self.notify(
            event_type="branch",
            title="Branch Created",
            message=branch_name,
            fields=fields,
            level="info"
        )

    def notify_pr(
        self,
        title: str,
        url: str,
        head: str,
        base: str = "main"
    ) -> bool:
        """Convenience method for PR notifications."""
        return self.notify(
            event_type="pr",
            title="Pull Request Created",
            message=title,
            url=url,
            fields={"From": head, "To": base},
            level="success"
        )

    def notify_task(
        self,
        action: str,
        issue_key: str,
        summary: str,
        url: str = None
    ) -> bool:
        """Convenience method for task-related notifications."""
        return self.notify(
            event_type="task",
            title=f"Task {action.capitalize()}",
            message=f"{issue_key}: {summary}",
            url=url,
            level="info"
        )

    def notify_alert(
        self,
        title: str,
        message: str,
        level: str = "warning"
    ) -> bool:
        """Convenience method for alerts."""
        return self.notify(
            event_type="alert",
            title=title,
            message=message,
            level=level
        )


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


class CICDBase(IntegrationBase):
    """
    Base class for CI/CD integrations.

    Manages pipelines, workflows, builds on GitHub Actions, GitLab CI,
    Jenkins, CircleCI, etc.
    """

    integration_type = IntegrationType.CI_CD

    @abstractmethod
    def trigger_pipeline(
        self,
        branch: str = None,
        workflow: str = None,
        inputs: Dict[str, Any] = None
    ) -> Optional[PipelineRun]:
        """
        Trigger a new pipeline/workflow run.

        Args:
            branch: Branch to run on (default: current/main)
            workflow: Specific workflow/pipeline name (optional)
            inputs: Input parameters for the workflow

        Returns:
            PipelineRun object or None if failed
        """
        pass

    @abstractmethod
    def get_pipeline_status(self, run_id: str) -> Optional[PipelineRun]:
        """
        Get status of a specific pipeline run.

        Args:
            run_id: Pipeline/workflow run ID

        Returns:
            PipelineRun object or None if not found
        """
        pass

    @abstractmethod
    def list_pipelines(
        self,
        branch: str = None,
        status: str = None,
        limit: int = 10
    ) -> List[PipelineRun]:
        """
        List recent pipeline runs.

        Args:
            branch: Filter by branch (optional)
            status: Filter by status (optional)
            limit: Maximum number of runs to return

        Returns:
            List of PipelineRun objects
        """
        pass

    @abstractmethod
    def cancel_pipeline(self, run_id: str) -> bool:
        """
        Cancel a running pipeline.

        Args:
            run_id: Pipeline/workflow run ID

        Returns:
            True if cancelled successfully
        """
        pass

    def get_pipeline_jobs(self, run_id: str) -> List[PipelineJob]:
        """
        Get jobs/steps for a pipeline run.

        Args:
            run_id: Pipeline/workflow run ID

        Returns:
            List of PipelineJob objects
        """
        return []

    def retry_pipeline(self, run_id: str) -> Optional[PipelineRun]:
        """
        Retry a failed pipeline.

        Args:
            run_id: Pipeline/workflow run ID

        Returns:
            New PipelineRun object or None if failed
        """
        return None

    def get_pipeline_logs(self, run_id: str, job_id: str = None) -> Optional[str]:
        """
        Get logs for a pipeline run or specific job.

        Args:
            run_id: Pipeline/workflow run ID
            job_id: Specific job ID (optional)

        Returns:
            Log content as string or None
        """
        return None

    def list_workflows(self) -> List[Dict[str, Any]]:
        """
        List available workflows/pipelines.

        Returns:
            List of workflow definitions
        """
        return []

    def get_latest_run(self, branch: str = None, workflow: str = None) -> Optional[PipelineRun]:
        """
        Get the latest pipeline run.

        Args:
            branch: Filter by branch (optional)
            workflow: Filter by workflow name (optional)

        Returns:
            Latest PipelineRun or None
        """
        runs = self.list_pipelines(branch=branch, limit=1)
        return runs[0] if runs else None


class CodeQualityBase(IntegrationBase):
    """
    Base class for code quality integrations.

    Manages code quality analysis, security scanning, coverage reporting,
    and dependency management on SonarQube, CodeClimate, Snyk, Codecov, etc.
    """

    integration_type = IntegrationType.CODE_QUALITY

    @abstractmethod
    def get_quality_status(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[QualityReport]:
        """
        Get quality status for a branch or commit.

        Args:
            branch: Branch name (optional)
            commit_sha: Commit SHA (optional)

        Returns:
            QualityReport object or None if not found
        """
        pass

    @abstractmethod
    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Get overall project quality metrics.

        Returns:
            Dict with quality metrics or None
        """
        pass

    def trigger_analysis(self, branch: str = None) -> bool:
        """
        Trigger a new quality analysis.

        Args:
            branch: Branch to analyze (optional)

        Returns:
            True if triggered successfully
        """
        return False

    def get_issues(
        self,
        severity: str = None,
        issue_type: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get code quality issues (bugs, code smells, etc.).

        Args:
            severity: Filter by severity (optional)
            issue_type: Filter by type (optional)
            limit: Maximum number of issues

        Returns:
            List of issue dicts
        """
        return []

    def get_security_issues(
        self,
        severity: str = None,
        limit: int = 50
    ) -> List[SecurityIssue]:
        """
        Get security vulnerabilities.

        Args:
            severity: Filter by severity (optional)
            limit: Maximum number of issues

        Returns:
            List of SecurityIssue objects
        """
        return []

    def get_coverage(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[CoverageReport]:
        """
        Get code coverage report.

        Args:
            branch: Branch name (optional)
            commit_sha: Commit SHA (optional)

        Returns:
            CoverageReport object or None
        """
        return None

    def get_quality_gate_status(self) -> Optional[str]:
        """
        Get quality gate status.

        Returns:
            "passed", "failed", or None
        """
        return None

    def get_dependencies(self) -> List[Dict[str, Any]]:
        """
        Get project dependencies with vulnerability info.

        Returns:
            List of dependency dicts
        """
        return []

    def get_outdated_dependencies(self) -> List[Dict[str, Any]]:
        """
        Get outdated dependencies that need updates.

        Returns:
            List of outdated dependency dicts
        """
        return []

    def get_pr_analysis(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """
        Get quality analysis for a pull request.

        Args:
            pr_number: PR number

        Returns:
            Analysis dict or None
        """
        return None

    def compare_branches(
        self,
        head: str,
        base: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Compare quality metrics between branches.

        Args:
            head: Head branch
            base: Base branch (optional, defaults to main)

        Returns:
            Comparison dict or None
        """
        return None


# Backward compatibility alias
Integration = IntegrationBase