"""
Jira integration for redgit.

Implements TaskManagementBase for Jira Cloud API v3.
"""

import os
import requests
from typing import Optional, Dict, List

from .base import TaskManagementBase, Issue, Sprint, IntegrationType


class JiraIntegration(TaskManagementBase):
    """Jira integration - Full task management support with Scrum/Kanban"""

    name = "jira"
    integration_type = IntegrationType.TASK_MANAGEMENT

    # Default issue type IDs (can be overridden in config)
    DEFAULT_ISSUE_TYPES = {
        "epic": "10001",
        "subtask": "10002",
        "task": "10003",
        "story": "10004",
        "feature": "10005",
        "bug": "10007"
    }

    # Status mappings (common Jira statuses)
    STATUS_MAP = {
        "todo": ["To Do", "Open", "Backlog"],
        "in_progress": ["In Progress", "In Development", "In Review"],
        "done": ["Done", "Closed", "Resolved"]
    }

    def __init__(self):
        super().__init__()
        self.site = ""
        self.email = ""
        self.token = ""
        self.project_key = ""
        self.project_name = ""
        self.board_type = "scrum"  # scrum, kanban, none
        self.board_id = None
        self.issue_types = self.DEFAULT_ISSUE_TYPES.copy()
        self.commit_prefix = ""
        self.branch_pattern = "feature/{issue_key}-{description}"
        self.story_points_field = "customfield_10016"
        self.session = None

    def setup(self, config: dict):
        """
        Setup Jira connection.

        Config example (.redgit/config.yaml):
            integrations:
              jira:
                site: "https://your-domain.atlassian.net"
                email: "you@example.com"
                project_key: "SCRUM"
                board_type: "scrum"  # scrum, kanban, none
                board_id: 1  # optional, auto-detected if empty
                story_points_field: "customfield_10016"  # optional
                # API token: JIRA_API_TOKEN env variable or token field
        """
        self.site = config.get("site", "").rstrip("/")
        self.email = config.get("email", "")
        self.token = config.get("token") or os.getenv("JIRA_API_TOKEN")
        self.project_key = config.get("project_key", "")
        self.project_name = config.get("project_name", "")
        self.board_type = config.get("board_type", "scrum")
        self.board_id = config.get("board_id")
        self.story_points_field = config.get("story_points_field", "customfield_10016")

        # Override issue types if provided
        if config.get("issue_types"):
            self.issue_types.update(config["issue_types"])

        # Commit and branch patterns
        self.commit_prefix = config.get("commit_prefix", self.project_key)
        self.branch_pattern = config.get(
            "branch_pattern",
            "feature/{issue_key}-{description}"
        )

        if not all([self.site, self.email, self.token]):
            self.enabled = False
            return

        self.session = requests.Session()
        self.session.auth = (self.email, self.token)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        self.enabled = True

        # Auto-detect board ID if not provided and board_type is not 'none'
        if self.board_type != "none" and not self.board_id and self.project_key:
            self.board_id = self._detect_board_id()

    def _detect_board_id(self) -> Optional[int]:
        """Auto-detect board ID for the project."""
        try:
            url = f"{self.site}/rest/agile/1.0/board"
            params = {"projectKeyOrId": self.project_key}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            boards = response.json().get("values", [])
            if boards:
                # Prefer matching board type
                for board in boards:
                    if board.get("type", "").lower() == self.board_type:
                        return board["id"]
                # Fallback to first board
                return boards[0]["id"]
        except Exception:
            pass
        return None

    # ==================== TaskManagementBase Implementation ====================

    def get_my_active_issues(self) -> List[Issue]:
        """Get issues assigned to current user that are in progress or to do."""
        if not self.enabled:
            return []

        issues = []

        # JQL to find active issues assigned to current user
        jql = (
            f'project = "{self.project_key}" '
            f'AND assignee = currentUser() '
            f'AND status in ("To Do", "In Progress", "Open", "In Development") '
            f'ORDER BY updated DESC'
        )

        try:
            url = f"{self.site}/rest/api/3/search"
            params = {
                "jql": jql,
                "maxResults": 50,
                "fields": "summary,status,issuetype,assignee,description,customfield_10016"
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for item in response.json().get("issues", []):
                issues.append(self._parse_issue(item))

        except Exception:
            pass

        # Also get issues from active sprint if using scrum
        if self.board_type == "scrum" and self.board_id:
            sprint_issues = self.get_sprint_issues()
            # Merge without duplicates
            existing_keys = {i.key for i in issues}
            for si in sprint_issues:
                if si.key not in existing_keys:
                    issues.append(si)

        return issues

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get a single issue by key."""
        if not self.enabled:
            return None

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}"
            params = {
                "fields": "summary,status,issuetype,assignee,description,customfield_10016"
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return self._parse_issue(response.json())
        except Exception:
            return None

    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        story_points: Optional[float] = None
    ) -> Optional[str]:
        """Create a new issue in the project."""
        if not self.enabled or not self.project_key:
            return None

        issue_type_id = self.issue_types.get(issue_type.lower(), self.issue_types["task"])

        try:
            url = f"{self.site}/rest/api/3/issue"
            payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "summary": summary,
                    "issuetype": {"id": issue_type_id}
                }
            }

            if description:
                payload["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }]
                }

            if story_points and self.story_points_field:
                payload["fields"][self.story_points_field] = story_points

            response = self.session.post(url, json=payload)
            response.raise_for_status()

            issue_key = response.json().get("key")

            # Add to active sprint if using scrum
            if self.board_type == "scrum" and issue_key:
                self.add_issue_to_active_sprint(issue_key)

            return issue_key
        except Exception:
            return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add comment to Jira issue."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}/comment"
            payload = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}]
                    }]
                }
            }
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def transition_issue(self, issue_key: str, status: str) -> bool:
        """Change issue status (e.g., 'In Progress', 'Done')."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}/transitions"
            response = self.session.get(url)
            response.raise_for_status()

            transitions = response.json().get("transitions", [])

            # Try exact match first
            for t in transitions:
                if t["name"].lower() == status.lower():
                    self.session.post(url, json={"transition": {"id": t["id"]}})
                    return True

            # Try mapped status names
            status_lower = status.lower().replace(" ", "_")
            if status_lower in self.STATUS_MAP:
                for status_name in self.STATUS_MAP[status_lower]:
                    for t in transitions:
                        if t["name"].lower() == status_name.lower():
                            self.session.post(url, json={"transition": {"id": t["id"]}})
                            return True

        except Exception:
            pass
        return False

    def format_branch_name(self, issue_key: str, description: str) -> str:
        """Format branch name using the configured pattern."""
        # Clean description for branch name
        clean_desc = description.lower()
        clean_desc = "".join(c if c.isalnum() or c == " " else "" for c in clean_desc)
        clean_desc = clean_desc.strip().replace(" ", "-")[:40]

        return self.branch_pattern.format(
            issue_key=issue_key,
            description=clean_desc
        )

    def get_commit_prefix(self) -> str:
        """Get prefix for commit messages."""
        return self.commit_prefix or self.project_key

    # ==================== Sprint Support ====================

    def supports_sprints(self) -> bool:
        """Jira supports sprints when board_type is scrum."""
        return self.board_type == "scrum" and self.board_id is not None

    def get_active_sprint(self) -> Optional[Sprint]:
        """Get the active sprint for the board."""
        if not self.enabled or not self.board_id or self.board_type != "scrum":
            return None

        try:
            url = f"{self.site}/rest/agile/1.0/board/{self.board_id}/sprint"
            params = {"state": "active"}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            sprints = response.json().get("values", [])
            if sprints:
                s = sprints[0]
                return Sprint(
                    id=str(s["id"]),
                    name=s.get("name", ""),
                    state=s.get("state", "active"),
                    start_date=s.get("startDate"),
                    end_date=s.get("endDate"),
                    goal=s.get("goal")
                )
        except Exception:
            pass
        return None

    def get_sprint_issues(self, sprint_id: str = None) -> List[Issue]:
        """Get issues in a sprint."""
        if not self.enabled:
            return []

        if sprint_id is None:
            sprint = self.get_active_sprint()
            if not sprint:
                return []
            sprint_id = sprint.id

        issues = []
        try:
            url = f"{self.site}/rest/agile/1.0/sprint/{sprint_id}/issue"
            params = {
                "fields": "summary,status,issuetype,assignee,description,customfield_10016"
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for item in response.json().get("issues", []):
                issues.append(self._parse_issue(item))
        except Exception:
            pass

        return issues

    def add_issue_to_sprint(self, issue_key: str, sprint_id: str) -> bool:
        """Add an issue to a sprint."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/agile/1.0/sprint/{sprint_id}/issue"
            payload = {"issues": [issue_key]}
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def add_issue_to_active_sprint(self, issue_key: str) -> bool:
        """Add an issue to the currently active sprint."""
        sprint = self.get_active_sprint()
        if sprint:
            return self.add_issue_to_sprint(issue_key, sprint.id)
        return False

    # ==================== Additional Jira-specific Methods ====================

    def get_board_info(self) -> Optional[Dict]:
        """Get board information."""
        if not self.enabled or not self.board_id:
            return None

        try:
            url = f"{self.site}/rest/agile/1.0/board/{self.board_id}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def get_backlog_issues(self, max_results: int = 50) -> List[Issue]:
        """Get issues in the backlog (not in any sprint)."""
        if not self.enabled or not self.board_id:
            return []

        issues = []
        try:
            url = f"{self.site}/rest/agile/1.0/board/{self.board_id}/backlog"
            params = {"maxResults": max_results}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for item in response.json().get("issues", []):
                issues.append(self._parse_issue(item))
        except Exception:
            pass

        return issues

    def get_future_sprints(self) -> List[Sprint]:
        """Get future sprints for the board."""
        if not self.enabled or not self.board_id or self.board_type != "scrum":
            return []

        sprints = []
        try:
            url = f"{self.site}/rest/agile/1.0/board/{self.board_id}/sprint"
            params = {"state": "future"}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for s in response.json().get("values", []):
                sprints.append(Sprint(
                    id=str(s["id"]),
                    name=s.get("name", ""),
                    state=s.get("state", "future"),
                    start_date=s.get("startDate"),
                    end_date=s.get("endDate"),
                    goal=s.get("goal")
                ))
        except Exception:
            pass

        return sprints

    # ==================== Hooks ====================

    def on_commit(self, group: dict, context: dict):
        """Add comment to Jira issue after commit."""
        if not self.enabled:
            return

        issue_key = context.get("issue_key")
        if not issue_key:
            return

        comment = (
            f"*Commit:* {group.get('commit_title', 'N/A')}\n"
            f"*Branch:* {group.get('branch', 'N/A')}\n"
            f"*Files:* {len(group.get('files', []))} files"
        )

        self.add_comment(issue_key, comment)

    # ==================== Internal Helpers ====================

    def _parse_issue(self, data: dict) -> Issue:
        """Parse Jira API response to Issue object."""
        fields = data.get("fields", {})

        # Extract description text
        description = ""
        desc_content = fields.get("description")
        if desc_content and isinstance(desc_content, dict):
            # ADF format
            for block in desc_content.get("content", []):
                if block.get("type") == "paragraph":
                    for item in block.get("content", []):
                        if item.get("type") == "text":
                            description += item.get("text", "")
                    description += "\n"
        elif isinstance(desc_content, str):
            description = desc_content

        # Extract assignee
        assignee = None
        assignee_data = fields.get("assignee")
        if assignee_data:
            assignee = assignee_data.get("displayName") or assignee_data.get("emailAddress")

        # Extract story points
        story_points = None
        if self.story_points_field:
            story_points = fields.get(self.story_points_field)

        return Issue(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            description=description.strip(),
            status=fields.get("status", {}).get("name", "Unknown"),
            issue_type=fields.get("issuetype", {}).get("name", "Task"),
            assignee=assignee,
            url=f"{self.site}/browse/{data.get('key', '')}",
            story_points=story_points
        )