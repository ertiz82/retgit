"""
Daily command - Generate daily activity report from git history.
"""

import subprocess
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.config import ConfigManager, RETGIT_DIR
from ..core.daily_state import DailyStateManager
from ..core.gitops import GitOps, NotAGitRepoError
from ..core.llm import LLMClient

console = Console()

# Language display names
LANGUAGE_NAMES = {
    "en": "English",
    "tr": "Turkish",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
}


def get_commits_since(since: datetime, author: Optional[str] = None) -> List[Dict]:
    """
    Get commits since a given timestamp.

    Returns list of dicts with commit info:
    - hash: commit hash
    - author: author name
    - email: author email
    - timestamp: unix timestamp
    - date: formatted date
    - message: commit message
    - files: list of changed files with stats
    """
    since_str = since.strftime("%Y-%m-%dT%H:%M:%S")

    # Build git log command
    cmd = [
        "git", "log",
        f"--since={since_str}",
        "--format=%H|%an|%ae|%at|%s",
        "--numstat"
    ]

    if author:
        cmd.append(f"--author={author}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Git error: {e.stderr}[/red]")
        return []

    output = result.stdout.strip()
    if not output:
        return []

    commits = []
    current_commit = None

    for line in output.split('\n'):
        if not line:
            continue

        # Check if it's a commit line (has | separators)
        if '|' in line and line.count('|') >= 4:
            # Save previous commit
            if current_commit:
                commits.append(current_commit)

            parts = line.split('|', 4)
            if len(parts) >= 5:
                timestamp = int(parts[3])
                # Clean author name (remove literal \n if present)
                author = parts[1].replace('\\n', '').strip()
                current_commit = {
                    "hash": parts[0][:8],  # Short hash
                    "author": author,
                    "email": parts[2],
                    "timestamp": timestamp,
                    "date": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M"),
                    "message": parts[4],
                    "files": [],
                    "additions": 0,
                    "deletions": 0,
                }
        elif current_commit and '\t' in line:
            # File stat line: additions\tdeletions\tfilename
            parts = line.split('\t')
            if len(parts) >= 3:
                additions = int(parts[0]) if parts[0].isdigit() else 0
                deletions = int(parts[1]) if parts[1].isdigit() else 0
                filename = parts[2]
                current_commit["files"].append({
                    "name": filename,
                    "additions": additions,
                    "deletions": deletions,
                })
                current_commit["additions"] += additions
                current_commit["deletions"] += deletions

    # Don't forget the last commit
    if current_commit:
        commits.append(current_commit)

    return commits


def format_commits_for_llm(commits: List[Dict]) -> str:
    """Format commits for LLM prompt."""
    lines = []
    for c in commits:
        lines.append(f"- [{c['hash']}] {c['message']} (by {c['author']}, {c['date']})")
        if c["files"]:
            for f in c["files"][:5]:  # Limit files per commit
                lines.append(f"    {f['name']} (+{f['additions']}/-{f['deletions']})")
            if len(c["files"]) > 5:
                lines.append(f"    ... and {len(c['files']) - 5} more files")
    return '\n'.join(lines)


def calculate_stats(commits: List[Dict]) -> Dict:
    """Calculate aggregate statistics from commits."""
    stats = {
        "total_commits": len(commits),
        "total_additions": 0,
        "total_deletions": 0,
        "total_files": 0,
        "authors": set(),
        "directories": defaultdict(int),
    }

    seen_files = set()

    for c in commits:
        stats["total_additions"] += c["additions"]
        stats["total_deletions"] += c["deletions"]
        stats["authors"].add(c["author"].strip())

        for f in c["files"]:
            if f["name"] not in seen_files:
                seen_files.add(f["name"])
                stats["total_files"] += 1

                # Track directories
                if '/' in f["name"]:
                    dir_name = f["name"].split('/')[0]
                    stats["directories"][dir_name] += 1

    stats["authors"] = list(stats["authors"])
    stats["directories"] = dict(sorted(
        stats["directories"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10])  # Top 10 directories

    return stats


def load_daily_prompt(language: str) -> str:
    """Load the daily prompt template."""
    # Check project-specific first
    project_prompt = RETGIT_DIR / "prompts" / "daily" / "default.md"
    if project_prompt.exists():
        return project_prompt.read_text()

    # Fallback to builtin
    builtin_prompt = Path(__file__).parent.parent / "prompts" / "daily" / "default.md"
    if builtin_prompt.exists():
        return builtin_prompt.read_text()

    # Hardcoded fallback
    return f"""Analyze these git commits and create a daily report in {language}:

{{{{COMMITS}}}}

Provide:
1. Summary (2-3 sentences)
2. Key changes (bullet points)
3. Affected areas
"""


def daily_cmd(
    since: Optional[str] = typer.Option(
        None, "--since", "-s",
        help="Override start time (e.g., '24h', '2d', 'yesterday', '2024-01-15')"
    ),
    author: Optional[str] = typer.Option(
        None, "--author", "-a",
        help="Filter commits by author name"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Show detailed output including raw commit data"
    ),
    no_ai: bool = typer.Option(
        False, "--no-ai",
        help="Skip AI analysis, show only raw stats"
    ),
):
    """Generate a daily report of git activity since last run."""

    # Check git repo
    try:
        GitOps()
    except NotAGitRepoError:
        console.print("[red]Not a git repository.[/red]")
        raise typer.Exit(1)

    config_manager = ConfigManager()
    config = config_manager.load()
    state_manager = DailyStateManager()

    # Get language from config
    daily_config = config.get("daily", {})
    language = daily_config.get("language", "en")
    language_name = LANGUAGE_NAMES.get(language, language)

    # Determine since timestamp
    # If author filter is used without --since, default to 24h (don't use last_run)
    if since:
        since_dt = state_manager.parse_since_option(since)
        time_desc = f"since {since}"
    elif author:
        # When filtering by author, default to 24h instead of last_run
        from datetime import timedelta
        since_dt = datetime.now() - timedelta(hours=24)
        time_desc = "last 24 hours"
    else:
        since_dt = state_manager.get_since_timestamp()
        last_run = state_manager.get_last_run()
        if last_run:
            time_desc = f"since last run ({last_run.strftime('%Y-%m-%d %H:%M')})"
        else:
            time_desc = "last 24 hours (first run)"

    if verbose:
        console.print(f"[dim]Language: {language_name}[/dim]")
        console.print(f"[dim]Since: {since_dt.isoformat()}[/dim]")

    # Get commits
    with console.status("Fetching commits..."):
        commits = get_commits_since(since_dt, author)

    if not commits:
        console.print(Panel(
            f"[yellow]No commits found {time_desc}[/yellow]",
            title="Daily Report",
            border_style="yellow"
        ))
        # Only update last run if not filtering by author
        if not author:
            state_manager.set_last_run()
        return

    # Calculate stats
    stats = calculate_stats(commits)

    # Show header
    today = datetime.now().strftime("%d %B %Y")
    header_text = f"[bold]Daily Report - {today}[/bold]\n"
    header_text += f"[dim]{time_desc} | {stats['total_commits']} commits | {len(stats['authors'])} author(s)[/dim]"

    console.print(Panel(header_text, border_style="cyan"))

    # Show verbose commit list
    if verbose:
        console.print("\n[bold cyan]Commits:[/bold cyan]")
        for c in commits[:20]:  # Limit display
            console.print(f"  [dim]{c['hash']}[/dim] {c['message']} [dim]({c['author']})[/dim]")
        if len(commits) > 20:
            console.print(f"  [dim]... and {len(commits) - 20} more[/dim]")
        console.print()

    # Show stats table
    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")

    stats_table.add_row("Commits", str(stats["total_commits"]))
    stats_table.add_row("Lines added", f"+{stats['total_additions']}")
    stats_table.add_row("Lines deleted", f"-{stats['total_deletions']}")
    stats_table.add_row("Files changed", str(stats["total_files"]))
    stats_table.add_row("Authors", ", ".join(stats["authors"]))

    console.print(stats_table)

    # Show affected directories
    if stats["directories"]:
        console.print("\n[bold]Affected areas:[/bold]")
        for dir_name, count in list(stats["directories"].items())[:5]:
            console.print(f"  [dim]├──[/dim] {dir_name}/ [dim]({count} files)[/dim]")

    # AI Analysis
    if not no_ai:
        console.print()
        with console.status("Generating AI summary..."):
            try:
                llm_config = config.get("llm", {})
                llm = LLMClient(llm_config)

                # Load and prepare prompt
                prompt_template = load_daily_prompt(language)
                commits_text = format_commits_for_llm(commits)
                prompt = prompt_template.replace("{{COMMITS}}", commits_text)
                prompt = prompt.replace("{{LANGUAGE}}", language_name)

                # Get AI response
                report = llm.chat(prompt)

                console.print(Panel(
                    report,
                    title="[bold]AI Summary[/bold]",
                    border_style="green"
                ))

            except Exception as e:
                console.print(f"[yellow]AI analysis skipped: {e}[/yellow]")

    # Update last run timestamp (only if not filtering by author)
    if not author:
        state_manager.set_last_run()
        if verbose:
            console.print(f"\n[dim]Last run updated: {datetime.now().isoformat()}[/dim]")
