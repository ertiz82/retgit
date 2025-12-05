import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..prompts import RESPONSE_SCHEMA
from ..core.config import RETGIT_DIR
from ..plugins.registry import get_plugin_by_name, get_builtin_plugins

# Builtin prompts directory (inside package)
BUILTIN_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PromptManager:
    """
    Prompt manager - loads prompts from various sources.

    Priority:
    1. If -p <plugin_name> is given, use plugin's get_prompt()
    2. If -p <prompt_name> is given, load from .md file
    3. If active plugin exists, use its get_prompt()
    4. Use default prompt
    """

    def __init__(self, config: dict):
        self.max_files = config.get("max_files", 100)
        self.include_content = config.get("include_content", False)
        self.default_prompt = config.get("prompt", "auto")

    def get_prompt(
        self,
        changes: List[Dict],
        prompt_name: Optional[str] = None,
        plugin_prompt: Optional[str] = None,
        active_issues: Optional[List] = None
    ) -> str:
        """
        Build final prompt.

        Args:
            changes: List of file changes
            prompt_name: Prompt name from CLI (None if not specified)
            plugin_prompt: Prompt from active plugin (if any)
            active_issues: List of active issues from task management

        Returns:
            Complete prompt (template + files + issues + response schema)
        """
        # Get prompt template
        template = self._load_template(prompt_name, plugin_prompt)

        # Format file list
        files_section = self._format_files(changes)

        # Format active issues if available
        issues_section = ""
        if active_issues:
            issues_section = self._format_issues(active_issues)

        # Insert files into template
        prompt = template.replace("{{FILES}}", files_section)

        # Insert issues section
        if issues_section:
            prompt += "\n\n" + issues_section

        # Always append response schema
        prompt += "\n" + self._get_response_schema(has_issues=bool(active_issues))

        return prompt

    def _load_template(
        self,
        prompt_name: Optional[str],
        plugin_prompt: Optional[str]
    ) -> str:
        """Load prompt template"""

        # 1. If explicit prompt name given via -p
        if prompt_name and prompt_name != "auto":
            # Check if it's a plugin name first
            builtin_plugins = get_builtin_plugins()
            if prompt_name in builtin_plugins:
                plugin = get_plugin_by_name(prompt_name)
                if plugin and hasattr(plugin, "get_prompt"):
                    plugin_prompt_text = plugin.get_prompt()
                    if plugin_prompt_text:
                        return plugin_prompt_text

            # Otherwise try to load as .md file
            return self._load_by_name(prompt_name)

        # 2. If active plugin has a prompt and we're in auto mode
        if self.default_prompt == "auto" and plugin_prompt:
            return plugin_prompt

        # 3. If config specifies a prompt name
        if self.default_prompt and self.default_prompt != "auto":
            return self._load_by_name(self.default_prompt)

        # 4. Default
        return self._load_by_name("default")

    def _load_by_name(self, name: str) -> str:
        """Load prompt by name"""

        # If URL, fetch it
        if name.startswith("http://") or name.startswith("https://"):
            return self._fetch_url(name)

        # Check project prompts folder first
        project_path = RETGIT_DIR / "prompts" / f"{name}.md"
        if project_path.exists():
            return project_path.read_text(encoding="utf-8")

        # Check builtin prompts
        builtin_path = BUILTIN_PROMPTS_DIR / f"{name}.md"
        if builtin_path.exists():
            return builtin_path.read_text(encoding="utf-8")

        raise FileNotFoundError(f"Prompt not found: {name}")

    def _fetch_url(self, url: str) -> str:
        """Fetch prompt from URL"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            raise RuntimeError(f"Failed to fetch prompt from URL: {e}")

    def _format_files(self, changes: List[Dict]) -> str:
        """Format file list"""
        lines = []

        # Apply max files limit
        files_to_process = changes[:self.max_files]
        total_files = len(files_to_process)

        # Add file count header for AI
        lines.append(f"**TOTAL: {total_files} FILES - YOU MUST INCLUDE ALL {total_files} FILES IN YOUR RESPONSE**")
        lines.append("")

        for i, change in enumerate(files_to_process, 1):
            file_path = change.get("file", "")
            status = change.get("status", "M")

            # Status description
            status_map = {"M": "modified", "U": "untracked", "A": "added", "D": "deleted"}
            status_text = status_map.get(status, status)

            line = f"{i}. [{status_text}] {file_path}"

            # Include file content if enabled
            if self.include_content:
                try:
                    path = Path(file_path)
                    if path.exists() and path.is_file():
                        ext = path.suffix.lstrip('.') or 'txt'
                        content = path.read_text(encoding="utf-8", errors="ignore")[:500]
                        line += f"\n```{ext}\n{content}\n```"
                except Exception:
                    pass

            lines.append(line)

        # Show truncation info
        if len(changes) > self.max_files:
            lines.append(f"\n... and {len(changes) - self.max_files} more files")

        # Add reminder at the end
        lines.append("")
        lines.append(f"**REMINDER: All {total_files} files above MUST appear in exactly one group. Do not skip any file.**")

        return "\n".join(lines)

    def _format_issues(self, issues: List) -> str:
        """Format active issues for AI context"""
        lines = [
            "## Active Issues (from task management)",
            "",
            "Match file groups to these issues when relevant. Use the issue_key field in your response.",
            "If files don't match any issue, leave issue_key as null.",
            ""
        ]

        for issue in issues:
            status = f"[{issue.status}]" if hasattr(issue, 'status') else ""
            lines.append(f"- **{issue.key}** {status}: {issue.summary}")
            if hasattr(issue, 'description') and issue.description:
                # Truncate long descriptions
                desc = issue.description[:150]
                if len(issue.description) > 150:
                    desc += "..."
                lines.append(f"  {desc}")
            lines.append("")

        return "\n".join(lines)

    def _get_response_schema(self, has_issues: bool = False) -> str:
        """Get response schema with optional issue_key field"""
        if has_issues:
            return RESPONSE_SCHEMA_WITH_ISSUES
        return RESPONSE_SCHEMA

    @staticmethod
    def get_available_prompts() -> List[str]:
        """List available prompts (includes plugin names)"""
        prompts = []

        # Builtin prompts (.md files)
        if BUILTIN_PROMPTS_DIR.exists():
            for f in BUILTIN_PROMPTS_DIR.glob("*.md"):
                prompts.append(f.stem)

        # Project prompts
        project_prompts = RETGIT_DIR / "prompts"
        if project_prompts.exists():
            for f in project_prompts.glob("*.md"):
                if f.stem not in prompts:
                    prompts.append(f.stem)

        # Add plugin names as valid prompt options
        for plugin_name in get_builtin_plugins():
            if plugin_name not in prompts:
                prompts.append(plugin_name)

        return sorted(prompts)


# Extended response schema with issue_key field
RESPONSE_SCHEMA_WITH_ISSUES = """
## Response Format

Respond with a JSON array. Each object represents a commit group:

```json
[
  {
    "files": ["path/to/file1.py", "path/to/file2.py"],
    "branch": "feature/short-description",
    "commit_title": "feat: add user authentication",
    "commit_body": "- Add login endpoint\\n- Add JWT token validation",
    "purpose": "User authentication feature",
    "issue_key": "PROJ-123"
  }
]
```

### Fields:
- **files**: Array of file paths that belong together
- **branch**: Suggested branch name (will be overridden if issue_key matches)
- **commit_title**: Short commit message (follow conventional commits)
- **commit_body**: Detailed description with bullet points
- **purpose**: Brief explanation of why these files are grouped
- **issue_key**: Matching issue key from Active Issues list (null if no match)

### Grouping Rules:
1. Group files by logical change/feature
2. One group per distinct change
3. Match groups to Active Issues when the changes clearly relate to the issue
4. If no issue matches, set issue_key to null

Return ONLY the JSON array, no other text.
"""