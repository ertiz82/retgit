import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..prompts import RESPONSE_SCHEMA
from ..core.config import RETGIT_DIR
from ..core.constants import (
    MAX_FILE_CONTENT_LENGTH,
    MAX_ISSUE_DESC_LENGTH,
    MAX_FILES_DISPLAY,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
)
from ..plugins.registry import get_plugin_by_name, get_builtin_plugins

# Builtin prompts directory (inside package)
BUILTIN_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Static prompt categories (inside package)
PROMPT_CATEGORIES = {
    "commit": BUILTIN_PROMPTS_DIR / "commit",
    "quality": BUILTIN_PROMPTS_DIR / "quality",
}

# Dynamic categories that are created at runtime
# - integrations/{name}/ : Integration-specific prompts (e.g., jira, github)
# - plugins/{name}/ : Plugin-specific prompts (e.g., laravel)


def get_prompt_path(category: str, name: str = "default") -> Path:
    """
    Get the path for a prompt file.

    Supports:
    - Static categories: commit, quality
    - Integration prompts: integrations/{integration_name}
    - Plugin prompts: plugins/{plugin_name}

    Args:
        category: Category path (e.g., "commit", "quality", "integrations/jira")
        name: Prompt name (default: "default")

    Returns:
        Path to the prompt file (may not exist)
    """
    if not name.endswith(".md"):
        name = f"{name}.md"

    # Check if it's a static category
    if category in PROMPT_CATEGORIES:
        return PROMPT_CATEGORIES[category] / name

    # Dynamic category (integrations/*, plugins/*)
    return BUILTIN_PROMPTS_DIR / category / name


def get_user_prompt_path(category: str, name: str = "default") -> Path:
    """
    Get the user override path for a prompt.

    User prompts are stored in .redgit/prompts/{category}/{name}.md

    Args:
        category: Category path (e.g., "commit", "integrations/jira")
        name: Prompt name

    Returns:
        Path to the user prompt file (may not exist)
    """
    if not name.endswith(".md"):
        name = f"{name}.md"

    return RETGIT_DIR / "prompts" / category / name


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
        self.max_files = config.get("max_files", MAX_FILES_DISPLAY)
        self.include_content = config.get("include_content", False)
        self.default_prompt = config.get("prompt", "auto")

    def get_prompt(
        self,
        changes: List[Dict],
        prompt_name: Optional[str] = None,
        plugin_prompt: Optional[str] = None,
        active_issues: Optional[List] = None,
        issue_language: Optional[str] = None
    ) -> str:
        """
        Build final prompt.

        Args:
            changes: List of file changes
            prompt_name: Prompt name from CLI (None if not specified)
            plugin_prompt: Prompt from active plugin (if any)
            active_issues: List of active issues from task management
            issue_language: Language for Jira issue titles (e.g., "tr", "en")

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
        prompt += "\n" + self._get_response_schema(
            has_issues=bool(active_issues),
            issue_language=issue_language
        )

        return prompt

    def get_task_filtered_prompt(
        self,
        changes: List[Dict],
        parent_task,  # Issue object
        other_tasks: Optional[List] = None,
        issue_language: Optional[str] = None
    ) -> str:
        """
        Build prompt for task-filtered mode.

        Analyzes files for relevance to a specific parent task and
        optionally matches unrelated files to other active tasks.

        Args:
            changes: List of file changes
            parent_task: Parent task Issue object (with key, summary, description)
            other_tasks: User's other active tasks for matching
            issue_language: Language for issue titles (e.g., "tr", "en")

        Returns:
            Complete prompt for task-filtered analysis
        """
        # Load task-filtered template
        template = self._load_by_name("task_filtered", category="commit")

        # Format file list
        files_section = self._format_files(changes)

        # Format parent task context
        # Add strict warning when description is missing or too short
        parent_desc = ""
        has_description = hasattr(parent_task, 'description') and parent_task.description
        if has_description and len(parent_task.description.strip()) > 50:
            parent_desc = parent_task.description
        else:
            parent_desc = (
                "⚠️ NO DESCRIPTION PROVIDED - BE EXTRA STRICT!\n"
                "Only match files where the path/name EXACTLY contains keywords from the task title.\n"
                "When in doubt, mark as unmatched_files."
            )

        # Replace placeholders
        prompt = template.replace("{{PARENT_TASK_KEY}}", parent_task.key)
        prompt = prompt.replace("{{PARENT_TASK_SUMMARY}}", parent_task.summary)
        prompt = prompt.replace("{{PARENT_TASK_DESCRIPTION}}", parent_desc)
        prompt = prompt.replace("{{FILES}}", files_section)

        # Format other tasks
        if other_tasks:
            other_tasks_lines = []
            for t in other_tasks[:15]:  # Limit to 15 tasks
                status = f"[{t.status}]" if hasattr(t, 'status') else ""
                other_tasks_lines.append(f"- **{t.key}** {status}: {t.summary}")
            other_tasks_section = "\n".join(other_tasks_lines)
        else:
            other_tasks_section = "No other active tasks found."

        prompt = prompt.replace("{{OTHER_TASKS}}", other_tasks_section)

        # Add language note if needed
        if issue_language and issue_language != "en":
            lang_names = {
                "tr": "Turkish", "de": "German", "fr": "French",
                "es": "Spanish", "pt": "Portuguese", "it": "Italian",
                "ru": "Russian", "zh": "Chinese", "ja": "Japanese",
                "ko": "Korean", "ar": "Arabic"
            }
            lang_name = lang_names.get(issue_language, issue_language)
            prompt += f"\n\n**IMPORTANT:** Write issue_title and issue_description in {lang_name}."

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

    def _load_by_name(self, name: str, category: str = "commit") -> str:
        """Load prompt by name from category folder.

        Args:
            name: Prompt name (e.g., "default", "minimal")
            category: Prompt category (e.g., "commit", "quality")

        Returns:
            Prompt content
        """
        # If URL, fetch it
        if name.startswith("http://") or name.startswith("https://"):
            return self._fetch_url(name)

        # Check project prompts folder first (.redgit/prompts/{category}/{name}.md)
        project_path = RETGIT_DIR / "prompts" / category / f"{name}.md"
        if project_path.exists():
            return project_path.read_text(encoding="utf-8")

        # Legacy: Check project prompts folder without category
        project_legacy = RETGIT_DIR / "prompts" / f"{name}.md"
        if project_legacy.exists():
            return project_legacy.read_text(encoding="utf-8")

        # Check builtin prompts (prompts/{category}/{name}.md)
        category_dir = PROMPT_CATEGORIES.get(category)
        if category_dir:
            builtin_path = category_dir / f"{name}.md"
            if builtin_path.exists():
                return builtin_path.read_text(encoding="utf-8")

        # Legacy: Check builtin prompts without category
        builtin_legacy = BUILTIN_PROMPTS_DIR / f"{name}.md"
        if builtin_legacy.exists():
            return builtin_legacy.read_text(encoding="utf-8")

        raise FileNotFoundError(f"Prompt not found: {category}/{name}")

    @staticmethod
    def load_prompt(category: str, name: str = "default") -> str:
        """Load a prompt from a category folder.

        Supports:
        - Static categories: "commit", "quality"
        - Integration prompts: "integrations/jira", "integrations/github"
        - Plugin prompts: "plugins/laravel"

        Args:
            category: Prompt category (e.g., "commit", "quality", "integrations/jira")
            name: Prompt name (e.g., "default", "minimal", "issue_title")

        Returns:
            Prompt content as string

        Example:
            PromptManager.load_prompt("quality")  # prompts/quality/default.md
            PromptManager.load_prompt("commit", "minimal")  # prompts/commit/minimal.md
            PromptManager.load_prompt("integrations/jira", "issue_title")  # integration prompt
        """
        # Ensure .md extension
        if not name.endswith(".md"):
            name = f"{name}.md"

        # Check user override first (.redgit/prompts/{category}/{name})
        user_path = get_user_prompt_path(category, name)
        if user_path.exists():
            return user_path.read_text(encoding="utf-8")

        # Check builtin prompts
        builtin_path = get_prompt_path(category, name)
        if builtin_path.exists():
            return builtin_path.read_text(encoding="utf-8")

        # For integration prompts, try to get from integration class
        if category.startswith("integrations/"):
            integration_name = category.split("/")[1]
            prompt_name = name.replace(".md", "")
            content = PromptManager._get_integration_prompt(integration_name, prompt_name)
            if content:
                return content

        raise FileNotFoundError(f"Prompt not found: {category}/{name}")

    @staticmethod
    def _get_integration_prompt(integration_name: str, prompt_name: str) -> Optional[str]:
        """Get prompt from integration's get_prompts() method."""
        from ..integrations.registry import get_integration_class

        integration_cls = get_integration_class(integration_name)
        if integration_cls and hasattr(integration_cls, "get_prompts"):
            prompts = integration_cls.get_prompts()
            if prompt_name in prompts:
                return prompts[prompt_name].get("content")
        return None

    @staticmethod
    def export_prompt(category: str, name: str = "default") -> Path:
        """Export a prompt to .redgit/prompts/{category}/{name}.md for customization.

        Args:
            category: Prompt category (e.g., "quality", "integrations/jira")
            name: Prompt name

        Returns:
            Path to exported file

        Example:
            PromptManager.export_prompt("quality")  # exports to .redgit/prompts/quality/default.md
            PromptManager.export_prompt("integrations/jira", "issue_title")
        """
        # Get the content first
        content = PromptManager.load_prompt(category, name)

        # Determine export path
        if not name.endswith(".md"):
            name = f"{name}.md"

        export_path = RETGIT_DIR / "prompts" / category / name
        export_path.parent.mkdir(parents=True, exist_ok=True)

        export_path.write_text(content, encoding="utf-8")
        return export_path

    @staticmethod
    def list_all_prompts() -> Dict[str, List[Dict[str, Any]]]:
        """List all available prompts organized by category.

        Returns:
            Dict with categories as keys and list of prompt info as values
        """
        result = {}

        # Static categories
        for category, category_path in PROMPT_CATEGORIES.items():
            if category_path.exists():
                prompts = []
                for f in category_path.glob("*.md"):
                    prompts.append({
                        "name": f.stem,
                        "path": str(f),
                        "source": "builtin"
                    })
                if prompts:
                    result[category] = prompts

        # Integration prompts (from loaded integrations)
        from ..integrations.registry import get_all_integration_classes

        for name, cls in get_all_integration_classes().items():
            if hasattr(cls, "get_prompts"):
                prompts_dict = cls.get_prompts()
                if prompts_dict:
                    category = f"integrations/{name}"
                    prompts = []
                    for prompt_name, prompt_info in prompts_dict.items():
                        prompts.append({
                            "name": prompt_name,
                            "description": prompt_info.get("description", ""),
                            "source": "integration"
                        })
                    if prompts:
                        result[category] = prompts

        # User overrides
        user_prompts_dir = RETGIT_DIR / "prompts"
        if user_prompts_dir.exists():
            for category_dir in user_prompts_dir.iterdir():
                if category_dir.is_dir():
                    category = category_dir.name
                    # Handle nested categories (integrations/jira)
                    if category == "integrations":
                        for sub_dir in category_dir.iterdir():
                            if sub_dir.is_dir():
                                sub_category = f"integrations/{sub_dir.name}"
                                for f in sub_dir.glob("*.md"):
                                    if sub_category not in result:
                                        result[sub_category] = []
                                    # Check if already in list
                                    existing = next(
                                        (p for p in result[sub_category] if p["name"] == f.stem),
                                        None
                                    )
                                    if existing:
                                        existing["has_override"] = True
                                    else:
                                        result[sub_category].append({
                                            "name": f.stem,
                                            "path": str(f),
                                            "source": "user"
                                        })
                    else:
                        for f in category_dir.glob("*.md"):
                            if category not in result:
                                result[category] = []
                            existing = next(
                                (p for p in result[category] if p["name"] == f.stem),
                                None
                            )
                            if existing:
                                existing["has_override"] = True
                            else:
                                result[category].append({
                                    "name": f.stem,
                                    "path": str(f),
                                    "source": "user"
                                })

        return result

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
            status_map = {"M": "modified", "U": "untracked", "A": "added", "D": "deleted", "C": "conflict"}
            status_text = status_map.get(status, status)

            line = f"{i}. [{status_text}] {file_path}"

            # Include file content if enabled
            if self.include_content:
                try:
                    path = Path(file_path)
                    if path.exists() and path.is_file():
                        ext = path.suffix.lstrip('.') or 'txt'
                        content = path.read_text(encoding="utf-8", errors="ignore")[:MAX_FILE_CONTENT_LENGTH]
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
                desc = issue.description[:MAX_ISSUE_DESC_LENGTH]
                if len(issue.description) > MAX_ISSUE_DESC_LENGTH:
                    desc += "..."
                lines.append(f"  {desc}")
            lines.append("")

        return "\n".join(lines)

    def _get_response_schema(
        self,
        has_issues: bool = False,
        issue_language: Optional[str] = None
    ) -> str:
        """Get response schema with optional issue_key and issue_title fields"""
        # Language config for issue titles
        lang_config = {
            "tr": {"name": "Turkish", "example": "Kullanıcı kimlik doğrulama özelliği eklendi"},
            "en": {"name": "English", "example": "Add user authentication feature"},
            "de": {"name": "German", "example": "Benutzerauthentifizierungsfunktion hinzugefügt"},
            "fr": {"name": "French", "example": "Ajout de la fonctionnalité d'authentification utilisateur"},
            "es": {"name": "Spanish", "example": "Añadir función de autenticación de usuario"},
            "pt": {"name": "Portuguese", "example": "Adicionar recurso de autenticação de usuário"},
            "it": {"name": "Italian", "example": "Aggiunta funzionalità di autenticazione utente"},
            "ru": {"name": "Russian", "example": "Добавлена функция аутентификации пользователя"},
            "zh": {"name": "Chinese", "example": "添加用户认证功能"},
            "ja": {"name": "Japanese", "example": "ユーザー認証機能を追加"},
            "ko": {"name": "Korean", "example": "사용자 인증 기능 추가"},
            "ar": {"name": "Arabic", "example": "إضافة ميزة مصادقة المستخدم"}
        }

        # If issue_language is set (task management configured), always use schema with issue_title
        if issue_language:
            config = lang_config.get(issue_language, {"name": issue_language, "example": "Issue title"})

            if has_issues:
                # With active issues - use schema that includes issue_key matching
                if issue_language == "en":
                    return RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE_EN
                else:
                    return RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE.format(
                        issue_language=config["name"],
                        issue_title_example=config["example"]
                    )
            else:
                # No active issues - use schema that generates issue_title in language
                if issue_language == "en":
                    return RESPONSE_SCHEMA_WITH_ISSUE_TITLE_EN
                else:
                    return RESPONSE_SCHEMA_WITH_ISSUE_TITLE.format(
                        issue_language=config["name"],
                        issue_title_example=config["example"]
                    )

        # No task management - use basic schema
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

# Extended response schema with issue_key and issue_title (with language support)
# For non-English languages
RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE = """
## Response Format

⚠️ LANGUAGE REQUIREMENT: The "issue_title" field MUST be written in {issue_language}. Not English!

Respond with a JSON array. Each object represents a commit group:

```json
[
  {{
    "files": ["path/to/file1.py", "path/to/file2.py"],
    "branch": "feature/short-description",
    "commit_title": "feat: add user authentication",
    "commit_body": "- Add login endpoint\\n- Add JWT token validation",
    "purpose": "User authentication feature",
    "issue_key": "PROJ-123",
    "issue_title": "{issue_title_example}"
  }}
]
```

### Fields:
- **files**: Array of file paths that belong together
- **branch**: Suggested branch name (will be overridden if issue_key matches)
- **commit_title**: Short commit message in English (follow conventional commits)
- **commit_body**: Detailed description with bullet points in English
- **purpose**: Brief explanation of why these files are grouped
- **issue_key**: Matching issue key from Active Issues list (null if no match)
- **issue_title**: Write in {issue_language}! Jira issue title in {issue_language} language. (null if issue_key is set)

### Language Rules:
- commit_title: English
- commit_body: English
- issue_title: {issue_language}

### Grouping Rules:
1. Group files by logical change/feature
2. One group per distinct change
3. Match groups to Active Issues when the changes clearly relate to the issue
4. If no issue matches and changes warrant a new issue, provide issue_title in {issue_language}
5. If an existing issue matches, set issue_key and leave issue_title as null

Return ONLY the JSON array, no other text.
"""

# For English language (no special warning needed)
RESPONSE_SCHEMA_WITH_ISSUES_AND_LANGUAGE_EN = """
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
    "issue_key": "PROJ-123",
    "issue_title": "Add user authentication feature"
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
- **issue_title**: Jira issue title for new issues (null if issue_key is set)

### Grouping Rules:
1. Group files by logical change/feature
2. One group per distinct change
3. Match groups to Active Issues when the changes clearly relate to the issue
4. If no issue matches and changes warrant a new issue, provide issue_title
5. If an existing issue matches, set issue_key and leave issue_title as null

Return ONLY the JSON array, no other text.
"""

# Schema for new issue creation with language (no active issues)
RESPONSE_SCHEMA_WITH_ISSUE_TITLE = """
## Response Format

⚠️ LANGUAGE REQUIREMENT: The "issue_title" field MUST be written in {issue_language}. Not English!

Respond with a JSON array. Each object represents a commit group:

```json
[
  {{
    "files": ["path/to/file1.py", "path/to/file2.py"],
    "branch": "feature/short-description",
    "commit_title": "feat: add user authentication",
    "commit_body": "- Add login endpoint\\n- Add JWT token validation",
    "purpose": "User authentication feature",
    "issue_title": "{issue_title_example}"
  }}
]
```

### Fields:
- **files**: Array of file paths that belong together
- **branch**: Suggested branch name
- **commit_title**: Short commit message in English (follow conventional commits)
- **commit_body**: Detailed description with bullet points in English
- **purpose**: Brief explanation of why these files are grouped
- **issue_title**: REQUIRED! Write in {issue_language}! Jira issue title describing this change in {issue_language} language.

### Language Rules:
- commit_title: English
- commit_body: English
- issue_title: {issue_language} (REQUIRED for each group)

### Grouping Rules:
1. Group files by logical change/feature
2. One group per distinct change
3. Each group MUST have an issue_title in {issue_language}

Return ONLY the JSON array, no other text.
"""

# Schema for new issue creation in English (no active issues)
RESPONSE_SCHEMA_WITH_ISSUE_TITLE_EN = """
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
    "issue_title": "Add user authentication feature"
  }
]
```

### Fields:
- **files**: Array of file paths that belong together
- **branch**: Suggested branch name
- **commit_title**: Short commit message (follow conventional commits)
- **commit_body**: Detailed description with bullet points
- **purpose**: Brief explanation of why these files are grouped
- **issue_title**: REQUIRED! Jira issue title describing this change

### Grouping Rules:
1. Group files by logical change/feature
2. One group per distinct change
3. Each group MUST have an issue_title

Return ONLY the JSON array, no other text.
"""