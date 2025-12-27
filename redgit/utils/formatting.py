"""
Rich console formatting utilities for RedGit.

This module provides consistent formatting helpers for console output,
reducing duplication across command modules.
"""

from typing import List, Dict, Optional, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..core.constants import Styles, StatusIcons

# Shared console instance
console = Console()


# =============================================================================
# SECTION HEADERS
# =============================================================================

def format_section_header(title: str, char: str = "═") -> str:
    """
    Format a section header with decorative characters.

    Args:
        title: The header title
        char: The decorative character to use

    Returns:
        Formatted header string like "[bold cyan]═══ Title ═══[/bold cyan]"
    """
    return f"[{Styles.HEADER}]{char * 3} {title} {char * 3}[/{Styles.HEADER}]"


def print_section_header(title: str, char: str = "═") -> None:
    """Print a section header to console."""
    console.print(format_section_header(title, char))


# =============================================================================
# STATUS MESSAGES
# =============================================================================

def format_success(message: str, icon: bool = True) -> str:
    """Format a success message with green color and optional checkmark."""
    prefix = f"{StatusIcons.SUCCESS} " if icon else ""
    return f"[{Styles.SUCCESS}]{prefix}{message}[/{Styles.SUCCESS}]"


def format_error(message: str, icon: bool = True) -> str:
    """Format an error message with red color and optional X mark."""
    prefix = f"{StatusIcons.ERROR} " if icon else ""
    return f"[{Styles.ERROR}]{prefix}{message}[/{Styles.ERROR}]"


def format_warning(message: str, icon: bool = True) -> str:
    """Format a warning message with yellow color and optional warning icon."""
    prefix = f"{StatusIcons.WARNING} " if icon else ""
    return f"[{Styles.WARNING}]{prefix}{message}[/{Styles.WARNING}]"


def format_info(message: str, icon: bool = True) -> str:
    """Format an info message with cyan color and optional info icon."""
    prefix = f"{StatusIcons.INFO} " if icon else ""
    return f"[{Styles.INFO}]{prefix}{message}[/{Styles.INFO}]"


def format_dim(message: str) -> str:
    """Format a dimmed/muted message."""
    return f"[{Styles.DIM}]{message}[/{Styles.DIM}]"


def print_success(message: str, icon: bool = True) -> None:
    """Print a success message to console."""
    console.print(format_success(message, icon))


def print_error(message: str, icon: bool = True) -> None:
    """Print an error message to console."""
    console.print(format_error(message, icon))


def print_warning(message: str, icon: bool = True) -> None:
    """Print a warning message to console."""
    console.print(format_warning(message, icon))


def print_info(message: str, icon: bool = True) -> None:
    """Print an info message to console."""
    console.print(format_info(message, icon))


# =============================================================================
# PANELS
# =============================================================================

def create_status_panel(
    title: str,
    content: str,
    style: str = Styles.INFO,
    subtitle: Optional[str] = None
) -> Panel:
    """
    Create a Rich Panel with consistent styling.

    Args:
        title: Panel title
        content: Panel content
        style: Rich style string
        subtitle: Optional subtitle

    Returns:
        Rich Panel object
    """
    return Panel(
        content,
        title=title,
        subtitle=subtitle,
        style=style,
        border_style=style
    )


def print_mode_panel(mode_name: str, style: str = "yellow") -> None:
    """Print a mode indicator panel (e.g., DRY RUN MODE, VERBOSE MODE)."""
    console.print(Panel(
        f"[bold {style}]{mode_name}[/bold {style}]",
        style=style
    ))


# =============================================================================
# LISTS AND BRANCHES
# =============================================================================

def format_branch_item(
    branch_name: str,
    issue_key: Optional[str] = None,
    status: Optional[str] = None
) -> str:
    """
    Format a branch list item with optional issue key and status.

    Args:
        branch_name: Git branch name
        issue_key: Optional issue key (e.g., "PROJ-123")
        status: Optional status indicator

    Returns:
        Formatted string like "  • feature/branch → PROJ-123 [In Progress]"
    """
    line = f"  • {branch_name}"
    if issue_key:
        line += f" → [{Styles.INFO}]{issue_key}[/{Styles.INFO}]"
    if status:
        line += f" [{Styles.DIM}]{status}[/{Styles.DIM}]"
    return line


def format_file_list(
    files: List[str],
    max_display: int = 5,
    indent: str = "    "
) -> str:
    """
    Format a list of files with truncation.

    Args:
        files: List of file paths
        max_display: Maximum number of files to show
        indent: Indentation string

    Returns:
        Formatted string with file list
    """
    lines = []
    for f in files[:max_display]:
        lines.append(f"{indent}• {f}")

    if len(files) > max_display:
        remaining = len(files) - max_display
        lines.append(f"{indent}[{Styles.DIM}]... and {remaining} more files[/{Styles.DIM}]")

    return "\n".join(lines)


def print_branch_list(branches: List[Dict[str, Any]], title: Optional[str] = None) -> None:
    """
    Print a formatted list of branches.

    Args:
        branches: List of branch dicts with 'branch', 'issue_key' keys
        title: Optional section title
    """
    if title:
        print_section_header(title)

    for b in branches:
        console.print(format_branch_item(
            branch_name=b.get("branch", ""),
            issue_key=b.get("issue_key"),
            status=b.get("status")
        ))


# =============================================================================
# GROUPS AND COMMITS
# =============================================================================

def format_group_summary(
    group: Dict[str, Any],
    index: int,
    show_files: bool = True
) -> str:
    """
    Format a commit group summary.

    Args:
        group: Group dict with 'commit_title', 'files', 'issue_key' etc.
        index: Group number (1-based)
        show_files: Whether to show file list

    Returns:
        Formatted multi-line string
    """
    lines = []

    # Title line
    title = group.get("commit_title", group.get("purpose", "Untitled"))
    issue_key = group.get("issue_key")

    if issue_key:
        lines.append(f"[{Styles.SUCCESS}]{index}. {title}[/{Styles.SUCCESS}] → [{Styles.INFO}]{issue_key}[/{Styles.INFO}]")
    else:
        lines.append(f"[{Styles.WARNING}]{index}. {title}[/{Styles.WARNING}]")

    # File count
    files = group.get("files", [])
    lines.append(f"   [{Styles.DIM}]{len(files)} files[/{Styles.DIM}]")

    # File list (if enabled)
    if show_files and files:
        lines.append(format_file_list(files, max_display=3, indent="      "))

    return "\n".join(lines)


def print_groups_summary(
    matched: List[Dict],
    unmatched: List[Dict],
    verbose: bool = False
) -> None:
    """
    Print a summary of matched and unmatched groups.

    Args:
        matched: List of groups matched to issues
        unmatched: List of groups not matched to issues
        verbose: Whether to show detailed file lists
    """
    if matched:
        console.print(f"\n[{Styles.SUCCESS}]Matched with existing issues:[/{Styles.SUCCESS}]")
        for i, g in enumerate(matched, 1):
            console.print(format_group_summary(g, i, show_files=verbose))

    if unmatched:
        console.print(f"\n[{Styles.WARNING}]New issues will be created:[/{Styles.WARNING}]")
        for i, g in enumerate(unmatched, 1):
            console.print(format_group_summary(g, i, show_files=verbose))


# =============================================================================
# TABLES
# =============================================================================

def create_key_value_table(
    data: Dict[str, Any],
    title: Optional[str] = None,
    key_style: str = Styles.INFO,
    value_style: str = ""
) -> Table:
    """
    Create a simple key-value table.

    Args:
        data: Dictionary of key-value pairs
        title: Optional table title
        key_style: Style for key column
        value_style: Style for value column

    Returns:
        Rich Table object
    """
    table = Table(title=title, show_header=False, box=None)
    table.add_column("Key", style=key_style)
    table.add_column("Value", style=value_style)

    for key, value in data.items():
        table.add_row(str(key), str(value))

    return table


def create_status_table(
    items: List[Dict[str, Any]],
    columns: List[Dict[str, str]],
    title: Optional[str] = None
) -> Table:
    """
    Create a table with status indicators.

    Args:
        items: List of item dicts
        columns: List of column configs [{"name": "Name", "key": "name", "style": "cyan"}]
        title: Optional table title

    Returns:
        Rich Table object
    """
    table = Table(title=title)

    for col in columns:
        table.add_column(col["name"], style=col.get("style", ""))

    for item in items:
        row = []
        for col in columns:
            value = item.get(col["key"], "")
            row.append(str(value))
        table.add_row(*row)

    return table


# =============================================================================
# PROGRESS INDICATORS
# =============================================================================

def format_progress(current: int, total: int, label: str = "") -> str:
    """
    Format a progress indicator.

    Args:
        current: Current count
        total: Total count
        label: Optional label

    Returns:
        Formatted string like "[2/5] Processing files..."
    """
    prefix = f"[{current}/{total}]"
    if label:
        return f"[{Styles.INFO}]{prefix}[/{Styles.INFO}] {label}"
    return f"[{Styles.INFO}]{prefix}[/{Styles.INFO}]"


def print_step(step_num: int, total_steps: int, message: str) -> None:
    """Print a numbered step indicator."""
    console.print(f"[{Styles.DIM}][{step_num}/{total_steps}][/{Styles.DIM}] {message}")
