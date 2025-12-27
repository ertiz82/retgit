"""
Centralized constants for RedGit.

This module contains all magic numbers, strings, and configuration defaults
that were previously scattered throughout the codebase.
"""

# =============================================================================
# TIMEOUT VALUES (seconds)
# =============================================================================

LLM_REQUEST_TIMEOUT = 120       # Default timeout for LLM API calls
SEMGREP_TIMEOUT = 300           # Default timeout for Semgrep analysis
GIT_OPERATION_TIMEOUT = 30      # Default timeout for git operations
INTEGRATION_API_TIMEOUT = 10    # Default timeout for integration API calls


# =============================================================================
# TRUNCATION LIMITS (characters/items)
# =============================================================================

MAX_DIFF_LENGTH = 2000              # Maximum characters for git diff content
MAX_FILE_CONTENT_LENGTH = 500       # Maximum characters for file content in prompts
MAX_ISSUE_DESC_LENGTH = 150         # Maximum characters for issue description display
MAX_FILES_DISPLAY = 100             # Maximum number of files to display
MAX_SCOUT_FILES = 500               # Maximum files for scout analysis
MAX_README_LENGTH = 2000            # Maximum characters for README in prompts
MAX_ERROR_OUTPUT_LENGTH = 500       # Maximum characters for error output display


# =============================================================================
# QUALITY THRESHOLDS
# =============================================================================

DEFAULT_QUALITY_THRESHOLD = 70      # Minimum score (0-100) to pass quality checks
MIN_QUALITY_SCORE = 0
MAX_QUALITY_SCORE = 100


# =============================================================================
# GIT STATUS CODES
# =============================================================================

class GitStatus:
    """Git file status codes from porcelain format."""
    UNTRACKED = "U"     # New file not tracked by git
    MODIFIED = "M"      # File has been modified
    ADDED = "A"         # New file added to index
    DELETED = "D"       # File has been deleted
    CONFLICT = "C"      # Merge conflict (unmerged)


# Unmerged (conflict) status codes from git status --porcelain
# Format: XY where X is index status, Y is work tree status
GIT_CONFLICT_STATUSES = frozenset({
    "DD",  # Both deleted
    "AU",  # Added by us
    "UD",  # Deleted by them
    "UA",  # Added by them
    "DU",  # Deleted by us
    "AA",  # Both added
    "UU",  # Both modified
})

# Statuses that indicate file was deleted in conflict
GIT_DELETED_CONFLICT_STATUSES = frozenset({"UD", "DU", "DD"})


# =============================================================================
# FILE PATTERNS
# =============================================================================

# Files that should always be excluded from commits
ALWAYS_EXCLUDED_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa*",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    "credentials.json",
    "credentials.yaml",
    "secrets.json",
    "secrets.yaml",
]

# Directories that should be excluded
EXCLUDED_DIRECTORIES = [
    ".redgit",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
]


# =============================================================================
# LOGGING DEFAULTS
# =============================================================================

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_LOG_FILES = 7


# =============================================================================
# RICH CONSOLE STYLES
# =============================================================================

class Styles:
    """Rich console style constants."""
    SUCCESS = "green"
    ERROR = "red"
    WARNING = "yellow"
    INFO = "cyan"
    DIM = "dim"
    BOLD = "bold"

    # Combined styles
    HEADER = "bold cyan"
    SECTION = "bold white"
    HIGHLIGHT = "bold yellow"


# =============================================================================
# STATUS ICONS (Rich formatted)
# =============================================================================

class StatusIcons:
    """Unicode status icons with Rich formatting."""
    SUCCESS = "[green]✓[/green]"
    ERROR = "[red]✗[/red]"
    WARNING = "[yellow]⚠[/yellow]"
    INFO = "[cyan]ℹ[/cyan]"
    PENDING = "[blue]○[/blue]"
    RUNNING = "[yellow]◐[/yellow]"
    SKIPPED = "[dim]○[/dim]"
    QUESTION = "[dim]?[/dim]"


# =============================================================================
# WORKFLOW STRATEGIES
# =============================================================================

class WorkflowStrategy:
    """Git workflow strategy constants."""
    LOCAL_MERGE = "local-merge"
    MERGE_REQUEST = "merge-request"


class IssueCreationMode:
    """Issue creation mode constants."""
    ASK = "ask"
    AUTO = "auto"
    SKIP = "skip"


class TransitionStrategy:
    """Issue transition strategy constants."""
    AUTO = "auto"
    ASK = "ask"


# =============================================================================
# LANGUAGE CONFIGURATIONS
# =============================================================================

SUPPORTED_LANGUAGES = {
    "en": {
        "name": "English",
        "commit_example": "Add user authentication feature",
        "issue_example": "Implement login functionality",
    },
    "tr": {
        "name": "Turkish",
        "commit_example": "Kullanıcı kimlik doğrulama özelliği ekle",
        "issue_example": "Giriş işlevselliğini uygula",
    },
    "de": {
        "name": "German",
        "commit_example": "Benutzerauthentifizierung hinzufügen",
        "issue_example": "Anmeldefunktion implementieren",
    },
    "fr": {
        "name": "French",
        "commit_example": "Ajouter l'authentification utilisateur",
        "issue_example": "Implémenter la fonctionnalité de connexion",
    },
    "es": {
        "name": "Spanish",
        "commit_example": "Agregar autenticación de usuario",
        "issue_example": "Implementar funcionalidad de inicio de sesión",
    },
    "pt": {
        "name": "Portuguese",
        "commit_example": "Adicionar autenticação de usuário",
        "issue_example": "Implementar funcionalidade de login",
    },
    "it": {
        "name": "Italian",
        "commit_example": "Aggiungere autenticazione utente",
        "issue_example": "Implementare funzionalità di accesso",
    },
    "nl": {
        "name": "Dutch",
        "commit_example": "Gebruikersauthenticatie toevoegen",
        "issue_example": "Inlogfunctionaliteit implementeren",
    },
    "ru": {
        "name": "Russian",
        "commit_example": "Добавить аутентификацию пользователя",
        "issue_example": "Реализовать функцию входа",
    },
    "ja": {
        "name": "Japanese",
        "commit_example": "ユーザー認証機能を追加",
        "issue_example": "ログイン機能を実装する",
    },
    "zh": {
        "name": "Chinese",
        "commit_example": "添加用户身份验证功能",
        "issue_example": "实现登录功能",
    },
    "ko": {
        "name": "Korean",
        "commit_example": "사용자 인증 기능 추가",
        "issue_example": "로그인 기능 구현",
    },
}

DEFAULT_LANGUAGE = "en"
