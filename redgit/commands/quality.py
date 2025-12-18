"""
Code Quality command for RedGit.

Analyzes code changes for quality issues using AI + linter (ruff/flake8).

Usage:
    rg quality              : Analyze staged changes
    rg quality <file>       : Analyze specific file
    rg quality --commit sha : Analyze specific commit
    rg quality --branch     : Compare branch with main
"""

import json
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..core.config import ConfigManager, RETGIT_DIR
from ..core.gitops import GitOps
from ..core.llm import LLMClient
from ..core.semgrep import (
    is_semgrep_installed,
    analyze_files as semgrep_analyze_files,
    convert_to_quality_issues,
    calculate_score_penalty as semgrep_score_penalty
)
from ..integrations.registry import get_code_quality, get_integrations_by_type, IntegrationType

console = Console()
quality_app = typer.Typer(
    help="Code quality analysis",
    no_args_is_help=True
)

# Supported linters in order of preference
LINTERS = ["ruff", "flake8"]

# Ruff/flake8 error code to severity mapping
SEVERITY_MAP = {
    # Critical - Security issues
    "S": "critical",      # bandit security
    "B": "high",          # bugbear
    # High - Errors
    "E9": "high",         # runtime errors
    "F": "high",          # pyflakes (undefined names, etc)
    # Medium - Warnings
    "E": "medium",        # pep8 errors
    "W": "medium",        # pep8 warnings
    "C": "medium",        # complexity
    # Low - Style
    "I": "low",           # isort
    "N": "low",           # naming
    "D": "low",           # docstrings
}


def _find_linter() -> Optional[str]:
    """Find available linter (ruff preferred, then flake8)."""
    for linter in LINTERS:
        if shutil.which(linter):
            return linter
    return None


def _get_changed_files(commit: Optional[str] = None, branch: Optional[str] = None, python_only: bool = True) -> List[str]:
    """Get list of changed files."""
    try:
        if commit:
            cmd = ["git", "diff", "--name-only", f"{commit}~1..{commit}"]
        elif branch:
            main_branch = _get_main_branch()
            cmd = ["git", "diff", "--name-only", f"{main_branch}...{branch}"]
        else:
            # Staged + unstaged
            cmd = ["git", "diff", "--name-only", "HEAD"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        files = result.stdout.strip().split("\n")

        # Filter files that exist
        files = [f for f in files if f and Path(f).exists()]

        # Filter Python files only if requested
        if python_only:
            return [f for f in files if f.endswith(".py")]

        return files
    except Exception:
        return []


def _get_error_severity(code: str) -> str:
    """Map linter error code to severity."""
    for prefix, severity in SEVERITY_MAP.items():
        if code.startswith(prefix):
            return severity
    return "low"


def _run_linter(files: List[str], verbose: bool = False) -> Tuple[List[Dict[str, Any]], str]:
    """
    Run linter on files and return issues.

    Returns:
        (issues list, linter name used)
    """
    if not files:
        return [], ""

    linter = _find_linter()
    if not linter:
        return [], ""

    if verbose:
        console.print(f"[dim]Running {linter} on {len(files)} file(s)...[/dim]")

    issues = []

    try:
        if linter == "ruff":
            # Ruff with JSON output
            cmd = ["ruff", "check", "--output-format=json", "--no-fix"] + files
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.stdout.strip():
                try:
                    ruff_issues = json.loads(result.stdout)
                    for issue in ruff_issues:
                        code = issue.get("code", "")
                        issues.append({
                            "severity": _get_error_severity(code),
                            "type": "lint",
                            "file": issue.get("filename", ""),
                            "line": issue.get("location", {}).get("row", 0),
                            "description": f"[{code}] {issue.get('message', '')}",
                            "suggestion": issue.get("fix", {}).get("message", "") if issue.get("fix") else "",
                            "source": "ruff"
                        })
                except json.JSONDecodeError:
                    pass

        elif linter == "flake8":
            # Flake8 with parseable output
            cmd = ["flake8", "--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s"] + files
            result = subprocess.run(cmd, capture_output=True, text=True)

            for line in result.stdout.strip().split("\n"):
                if not line or ":" not in line:
                    continue
                parts = line.split(":", 4)
                if len(parts) >= 5:
                    file_path, row, col, code, message = parts
                    issues.append({
                        "severity": _get_error_severity(code),
                        "type": "lint",
                        "file": file_path,
                        "line": int(row) if row.isdigit() else 0,
                        "description": f"[{code}] {message}",
                        "suggestion": "",
                        "source": "flake8"
                    })

    except Exception as e:
        if verbose:
            console.print(f"[yellow]Linter error: {e}[/yellow]")

    return issues, linter


def _merge_results(ai_result: dict, linter_issues: List[Dict], linter_name: str) -> dict:
    """
    Merge AI analysis with linter results.

    - Linter issues are authoritative for syntax/lint errors
    - AI issues are used for logic/security/performance
    - Score is adjusted based on combined issues
    """
    all_issues = list(ai_result.get("issues", []))

    # Add linter issues (avoid duplicates based on file:line)
    existing_locations = {
        (i.get("file", ""), i.get("line", 0))
        for i in all_issues
    }

    for issue in linter_issues:
        loc = (issue.get("file", ""), issue.get("line", 0))
        if loc not in existing_locations:
            all_issues.append(issue)
            existing_locations.add(loc)

    # Recalculate score based on combined issues
    score = ai_result.get("score", 100)

    # Deduct points for linter issues
    critical_count = sum(1 for i in linter_issues if i.get("severity") == "critical")
    high_count = sum(1 for i in linter_issues if i.get("severity") == "high")
    medium_count = sum(1 for i in linter_issues if i.get("severity") == "medium")

    # Penalty: critical=-20, high=-10, medium=-3 (capped)
    penalty = min(50, critical_count * 20 + high_count * 10 + medium_count * 3)
    adjusted_score = max(0, score - penalty)

    # Update decision based on adjusted score and critical issues
    threshold = ConfigManager().get_quality_threshold()
    has_critical = critical_count > 0 or any(
        i.get("severity") == "critical" for i in ai_result.get("issues", [])
    )

    if has_critical or adjusted_score < threshold:
        decision = "reject"
    else:
        decision = "approve"

    # Build summary
    summary_parts = []
    if ai_result.get("summary"):
        summary_parts.append(ai_result["summary"])
    if linter_issues:
        summary_parts.append(f"{linter_name}: {len(linter_issues)} issue(s)")

    return {
        "score": adjusted_score,
        "decision": decision,
        "summary": " | ".join(summary_parts) if summary_parts else "No issues found",
        "issues": all_issues
    }


# Prompt paths (new structure: prompts/quality/default.md)
DEFAULT_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "quality" / "default.md"
USER_PROMPT_PATH = RETGIT_DIR / "prompts" / "quality" / "default.md"
# Legacy paths for backward compatibility
LEGACY_DEFAULT_PROMPT_PATH = Path(__file__).parent.parent / "templates" / "quality_prompt.md"
LEGACY_USER_PROMPT_PATH = RETGIT_DIR / "templates" / "quality_prompt.md"


def _get_code_quality():
    """Get the active code quality integration."""
    config = ConfigManager().load()
    return get_code_quality(config)


def _load_prompt_template() -> str:
    """Load the quality prompt template."""
    # Check user's custom template first
    if USER_PROMPT_PATH.exists():
        return USER_PROMPT_PATH.read_text()

    # Fall back to default template
    if DEFAULT_PROMPT_PATH.exists():
        return DEFAULT_PROMPT_PATH.read_text()

    # Fallback inline prompt
    return """Analyze the following git diff for code quality issues.
Output JSON only:
{
  "score": 0-100,
  "decision": "approve" or "reject",
  "summary": "Brief assessment",
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "type": "security|bug|performance|maintainability|style",
      "file": "path/to/file",
      "line": 123,
      "description": "Issue description",
      "suggestion": "How to fix"
    }
  ]
}

{{DIFF}}
"""


def _get_diff(commit: Optional[str] = None, branch: Optional[str] = None, file: Optional[str] = None) -> str:
    """Get git diff for analysis."""
    try:
        if commit:
            # Diff for specific commit
            cmd = ["git", "diff", f"{commit}~1..{commit}"]
        elif branch:
            # Diff between branch and main
            main_branch = _get_main_branch()
            cmd = ["git", "diff", f"{main_branch}...{branch}"]
        elif file:
            # Diff for specific file (staged or unstaged)
            cmd = ["git", "diff", "HEAD", "--", file]
        else:
            # Staged changes
            cmd = ["git", "diff", "--staged"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        diff = result.stdout.strip()

        # If no staged changes, try unstaged
        if not diff and not commit and not branch:
            result = subprocess.run(["git", "diff"], capture_output=True, text=True)
            diff = result.stdout.strip()

        return diff
    except Exception:
        return ""


def _get_main_branch() -> str:
    """Get the main branch name."""
    for name in ["main", "master"]:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", name],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return name
    return "main"


def _analyze_with_ai(diff: str, config: dict) -> dict:
    """Analyze code quality using AI."""
    if not diff:
        return {
            "score": 100,
            "decision": "approve",
            "summary": "No changes to analyze",
            "issues": []
        }

    # Load prompt template
    prompt_template = _load_prompt_template()
    prompt = prompt_template.replace("{{DIFF}}", diff)

    # Get LLM config
    llm_config = config.get("llm", {})
    if not llm_config:
        raise ValueError("No LLM configured. Run: rg init")

    # Call LLM
    client = LLMClient(llm_config)
    response = client.chat(prompt)

    # Parse JSON response
    return _parse_quality_response(response)


def _parse_quality_response(response: str) -> dict:
    """Parse JSON response from LLM."""
    # Find JSON block
    json_text = response
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        json_text = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        json_text = response[start:end].strip()

    try:
        data = json.loads(json_text)
        return {
            "score": data.get("score", 0),
            "decision": data.get("decision", "reject"),
            "summary": data.get("summary", ""),
            "issues": data.get("issues", [])
        }
    except json.JSONDecodeError:
        return {
            "score": 0,
            "decision": "reject",
            "summary": "Failed to parse quality analysis response",
            "issues": []
        }


def _severity_color(severity: str) -> str:
    """Get color for severity level."""
    colors = {
        "critical": "red bold",
        "high": "red",
        "medium": "yellow",
        "low": "blue",
    }
    return colors.get(severity.lower(), "dim")


def _display_result(result: dict, threshold: int):
    """Display quality analysis result."""
    score = result.get("score", 0)
    decision = result.get("decision", "reject")
    summary = result.get("summary", "")
    issues = result.get("issues", [])

    # Score panel
    score_color = "green" if score >= threshold else "red"
    decision_icon = "[green]APPROVE[/green]" if decision == "approve" else "[red]REJECT[/red]"

    panel_content = f"""Score: [{score_color}]{score}/100[/{score_color}]
Decision: {decision_icon}
Threshold: {threshold}"""

    console.print()
    console.print(Panel(panel_content, title="Code Quality Report", border_style="cyan"))

    if summary:
        console.print(f"\n[dim]{summary}[/dim]")

    # Issues table
    if issues:
        console.print("\n[bold]Issues Found:[/bold]\n")

        table = Table(show_header=True)
        table.add_column("Severity", width=10)
        table.add_column("File", style="dim")
        table.add_column("Line", width=6)
        table.add_column("Description")

        for issue in issues:
            severity = issue.get("severity", "medium")
            color = _severity_color(severity)
            table.add_row(
                f"[{color}]{severity.upper()}[/{color}]",
                issue.get("file", "-"),
                str(issue.get("line", "-")),
                issue.get("description", "")
            )

        console.print(table)

        # Show suggestions for critical/high issues
        critical_issues = [i for i in issues if i.get("severity", "").lower() in ("critical", "high")]
        if critical_issues:
            console.print("\n[bold]Suggestions:[/bold]")
            for issue in critical_issues:
                if issue.get("suggestion"):
                    file_info = f"{issue.get('file', '')}:{issue.get('line', '')}"
                    console.print(f"  [dim]{file_info}[/dim]")
                    console.print(f"    {issue.get('suggestion')}")
                    console.print()
    else:
        console.print("\n[green]No issues found.[/green]")


def analyze_quality(
    commit: Optional[str] = None,
    branch: Optional[str] = None,
    file: Optional[str] = None,
    verbose: bool = False,
    skip_linter: bool = False,
    skip_ai: bool = False,
    skip_semgrep: bool = False
) -> dict:
    """
    Analyze code quality using AI + linter (ruff/flake8) + Semgrep.

    Returns:
        dict with score, decision, summary, issues
    """
    config = ConfigManager()
    full_config = config.load()

    # Check if we have a code quality integration
    quality_integration = _get_code_quality()

    if quality_integration:
        # Use integration
        if verbose:
            console.print(f"[dim]Using {quality_integration.name} integration[/dim]")

        if commit:
            status = quality_integration.get_quality_status(commit_sha=commit)
        elif branch:
            status = quality_integration.get_quality_status(branch=branch)
        else:
            # Get current branch
            try:
                gitops = GitOps()
                status = quality_integration.get_quality_status(branch=gitops.original_branch)
            except Exception:
                status = quality_integration.get_quality_status()

        if status:
            return {
                "score": int(status.coverage or 70) if hasattr(status, 'coverage') else 70,
                "decision": "approve" if status.status in ("passed", "success") else "reject",
                "summary": f"Quality gate: {status.quality_gate_status}" if status.quality_gate_status else "",
                "issues": []
            }

    # Get changed Python files for linter
    if file:
        python_files = [file] if file.endswith(".py") and Path(file).exists() else []
    else:
        python_files = _get_changed_files(commit=commit, branch=branch, python_only=True)

    # Run linter on Python files
    linter_issues = []
    linter_name = ""
    if not skip_linter and python_files:
        linter_issues, linter_name = _run_linter(python_files, verbose=verbose)
        if verbose and linter_name:
            console.print(f"[dim]{linter_name} found {len(linter_issues)} issue(s)[/dim]")

    # Run Semgrep on all changed files (multi-language)
    semgrep_issues = []
    if not skip_semgrep and config.is_semgrep_enabled():
        # Get all changed files (not just Python) for Semgrep
        if file:
            semgrep_files = [file] if Path(file).exists() else []
        else:
            semgrep_files = _get_changed_files(commit=commit, branch=branch, python_only=False)

        if semgrep_files:
            if verbose:
                console.print(f"[dim]Running Semgrep on {len(semgrep_files)} file(s)...[/dim]")

            try:
                semgrep_result = semgrep_analyze_files(semgrep_files)
                if semgrep_result.get("success") and semgrep_result.get("results"):
                    semgrep_issues = convert_to_quality_issues(semgrep_result["results"])
                    if verbose:
                        console.print(f"[dim]Semgrep found {len(semgrep_issues)} issue(s)[/dim]")
                elif verbose and not semgrep_result.get("success"):
                    console.print(f"[yellow]Semgrep: {semgrep_result.get('error', 'Unknown error')}[/yellow]")
            except Exception as e:
                if verbose:
                    console.print(f"[yellow]Semgrep error: {e}[/yellow]")

    # Get diff for AI analysis
    diff = _get_diff(commit=commit, branch=branch, file=file)

    if not diff and not linter_issues and not semgrep_issues:
        return {
            "score": 100,
            "decision": "approve",
            "summary": "No changes to analyze",
            "issues": []
        }

    # AI analysis
    ai_result = {"score": 100, "decision": "approve", "summary": "", "issues": []}
    if not skip_ai and diff:
        if verbose:
            console.print("[dim]Running AI analysis...[/dim]")
        try:
            ai_result = _analyze_with_ai(diff, full_config)
        except Exception as e:
            if verbose:
                console.print(f"[yellow]AI analysis failed: {e}[/yellow]")
            # Continue with linter-only results

    # Merge all results
    all_issues = list(ai_result.get("issues", []))
    summary_parts = []

    if ai_result.get("summary"):
        summary_parts.append(ai_result["summary"])

    # Add linter issues
    existing_locations = {(i.get("file", ""), i.get("line", 0)) for i in all_issues}
    for issue in linter_issues:
        loc = (issue.get("file", ""), issue.get("line", 0))
        if loc not in existing_locations:
            all_issues.append(issue)
            existing_locations.add(loc)

    if linter_issues:
        summary_parts.append(f"{linter_name}: {len(linter_issues)} issue(s)")

    # Add Semgrep issues
    for issue in semgrep_issues:
        loc = (issue.get("file", ""), issue.get("line", 0))
        if loc not in existing_locations:
            all_issues.append(issue)
            existing_locations.add(loc)

    if semgrep_issues:
        summary_parts.append(f"Semgrep: {len(semgrep_issues)} issue(s)")

    # Calculate score
    score = ai_result.get("score", 100)

    # Deduct for linter issues
    linter_critical = sum(1 for i in linter_issues if i.get("severity") == "critical")
    linter_high = sum(1 for i in linter_issues if i.get("severity") == "high")
    linter_medium = sum(1 for i in linter_issues if i.get("severity") == "medium")
    linter_penalty = min(50, linter_critical * 20 + linter_high * 10 + linter_medium * 3)

    # Deduct for Semgrep issues
    semgrep_penalty = semgrep_score_penalty(semgrep_issues) if semgrep_issues else 0

    # Total penalty capped at 70
    total_penalty = min(70, linter_penalty + semgrep_penalty)
    adjusted_score = max(0, score - total_penalty)

    # Determine decision
    threshold = config.get_quality_threshold()
    has_critical = (
        linter_critical > 0 or
        any(i.get("severity") == "critical" for i in ai_result.get("issues", [])) or
        any(i.get("severity") == "critical" for i in semgrep_issues)
    )

    if has_critical or adjusted_score < threshold:
        decision = "reject"
    else:
        decision = "approve"

    return {
        "score": adjusted_score,
        "decision": decision,
        "summary": " | ".join(summary_parts) if summary_parts else "No issues found",
        "issues": all_issues
    }


@quality_app.command("check")
def check_cmd(
    file: Optional[str] = typer.Argument(None, help="File to analyze"),
    commit: Optional[str] = typer.Option(None, "--commit", "-c", help="Analyze specific commit"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Compare branch with main"),
    threshold: int = typer.Option(70, "--threshold", "-t", help="Quality threshold (0-100)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output")
):
    """
    Run quality check (works even if quality checks are disabled).

    This command always runs analysis regardless of the quality.enabled setting.
    """
    console.print("[bold cyan]Analyzing code quality...[/bold cyan]")

    try:
        result = analyze_quality(
            commit=commit,
            branch=branch,
            file=file,
            verbose=verbose
        )

        _display_result(result, threshold)

        # Exit with error if below threshold
        if result.get("score", 0) < threshold:
            console.print(f"\n[red]Quality score {result.get('score')} is below threshold {threshold}[/red]")
            raise typer.Exit(1)

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        raise typer.Exit(1)


def _count_files_by_extension(files: List[str]) -> Dict[str, int]:
    """Count files by extension for language summary."""
    ext_count: Dict[str, int] = {}
    ext_to_lang = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".java": "Java",
        ".go": "Go",
        ".php": "PHP",
        ".rb": "Ruby",
        ".rs": "Rust",
        ".c": "C",
        ".cpp": "C++",
        ".cs": "C#",
        ".kt": "Kotlin",
        ".swift": "Swift",
        ".scala": "Scala",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".json": "JSON",
        ".html": "HTML",
        ".css": "CSS",
        ".sql": "SQL",
        ".sh": "Shell",
        ".bash": "Shell",
    }

    for f in files:
        ext = Path(f).suffix.lower()
        lang = ext_to_lang.get(ext, ext.upper().lstrip(".") if ext else "Other")
        ext_count[lang] = ext_count.get(lang, 0) + 1

    return ext_count


@quality_app.command("scan")
def scan_cmd(
    path: str = typer.Argument(".", help="Directory or file to scan"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Semgrep config (e.g., auto, p/security-audit)"),
    severity: Optional[str] = typer.Option(None, "--severity", "-s", help="Minimum severity: ERROR, WARNING, INFO"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save report to file"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, json"),
    patterns: bool = typer.Option(False, "--patterns", "-p", help="Analyze code and suggest design patterns (AI)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output")
):
    """
    Scan entire project with Semgrep (not just changes).

    This command runs Semgrep on all files in the specified path,
    regardless of git status. Useful for full project audits.

    Examples:
        rg quality scan                    # Scan current directory
        rg quality scan src/               # Scan specific directory
        rg quality scan -c p/security-audit  # Use security rules
        rg quality scan -o report.json -f json  # Export as JSON
        rg quality scan --patterns         # Get design pattern suggestions
    """
    from ..core.semgrep import (
        is_semgrep_installed,
        run_semgrep,
        convert_to_quality_issues,
        get_severity_counts,
        format_issue_report
    )

    # Check if Semgrep is installed
    if not is_semgrep_installed():
        console.print("[red]Semgrep is not installed.[/red]")
        console.print("Install with: [cyan]pip install semgrep[/cyan]")
        console.print("Or run: [cyan]rg config semgrep --install[/cyan]")
        raise typer.Exit(1)

    # Get config
    cfg = ConfigManager()
    semgrep_config = cfg.get_semgrep_config()

    # Build configs list
    configs = [config] if config else semgrep_config.get("configs", ["auto"])

    # Build severity list
    if severity:
        severities = [s.strip().upper() for s in severity.split(",")]
    else:
        severities = semgrep_config.get("severity", ["ERROR", "WARNING"])

    console.print(f"[bold cyan]Scanning {path} with Semgrep...[/bold cyan]")
    if verbose:
        console.print(f"[dim]Configs: {', '.join(configs)}[/dim]")
        console.print(f"[dim]Severity: {', '.join(severities)}[/dim]")

    # Run Semgrep
    result = run_semgrep(
        path=path,
        configs=configs,
        severity=severities,
        exclude=semgrep_config.get("exclude", []),
        timeout=semgrep_config.get("timeout", 300)
    )

    if not result.get("success"):
        console.print(f"[red]Scan failed: {result.get('error', 'Unknown error')}[/red]")
        raise typer.Exit(1)

    # Get scan stats
    stats = result.get("stats", {})
    scanned_files = stats.get("paths_scanned", [])
    file_count = len(scanned_files)

    # Convert to quality issues
    issues = convert_to_quality_issues(result.get("results", []))
    counts = get_severity_counts(issues)

    # Output based on format
    if format == "json":
        json_output = json.dumps({
            "path": path,
            "configs": configs,
            "files_scanned": file_count,
            "total_issues": len(issues),
            "severity_counts": counts,
            "issues": issues
        }, indent=2)

        if output:
            Path(output).write_text(json_output)
            console.print(f"\n[green]Report saved to {output}[/green]")
        else:
            console.print(json_output)
    else:
        # Text format - Summary
        console.print()

        # Show scan summary
        if file_count > 0:
            lang_counts = _count_files_by_extension(scanned_files)
            lang_summary = ", ".join(f"{lang}: {count}" for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1])[:5])
            console.print("[bold]Scan Summary:[/bold]")
            console.print(f"  Files scanned: [cyan]{file_count}[/cyan]")
            console.print(f"  Languages: {lang_summary}")
            console.print()
        else:
            console.print("[dim]No files were scanned (Semgrep may have filtered all files)[/dim]")
            console.print()

        if not issues:
            console.print("[green]✓ No issues found! All files passed quality checks.[/green]")
        else:
            # Issues summary
            console.print(f"[bold]Found {len(issues)} issue(s):[/bold]")
            console.print(f"  [red]Critical: {counts['critical']}[/red]")
            console.print(f"  [red]High: {counts['high']}[/red]")
            console.print(f"  [yellow]Medium: {counts['medium']}[/yellow]")
            console.print(f"  [blue]Low: {counts['low']}[/blue]")
            console.print()

            # Issues table
            table = Table(show_header=True)
            table.add_column("Severity", width=10)
            table.add_column("File", style="dim")
            table.add_column("Line", width=6)
            table.add_column("Description")

            for issue in issues:
                sev = issue.get("severity", "medium")
                color = _severity_color(sev)
                table.add_row(
                    f"[{color}]{sev.upper()}[/{color}]",
                    issue.get("file", "-"),
                    str(issue.get("line", "-")),
                    issue.get("description", "")[:80]
                )

            console.print(table)

            # Show suggestions for critical/high
            if verbose:
                critical_issues = [i for i in issues if i.get("severity") in ("critical", "high")]
                if critical_issues:
                    console.print("\n[bold]Suggestions:[/bold]")
                    for issue in critical_issues[:10]:  # Limit to 10
                        if issue.get("suggestion"):
                            console.print(f"  [dim]{issue.get('file')}:{issue.get('line')}[/dim]")
                            console.print(f"    {issue.get('suggestion')[:100]}")

        # Save to file if requested
        if output:
            report = format_issue_report(issues, verbose=True)
            Path(output).write_text(report)
            console.print(f"\n[green]Report saved to {output}[/green]")

    # Run design pattern analysis if requested
    if patterns:
        console.print()
        _analyze_design_patterns(path, scanned_files, verbose)

    # Exit with error if critical issues found
    if counts["critical"] > 0:
        console.print(f"\n[red]Found {counts['critical']} critical issue(s)![/red]")
        raise typer.Exit(1)


def _analyze_design_patterns(path: str, files: List[str], verbose: bool = False):
    """Analyze code structure and suggest design patterns using AI."""
    from ..core.config import ConfigManager
    from ..core.llm import LLMClient

    console.print("[bold cyan]Analyzing code structure for design patterns...[/bold cyan]")

    # Get code summary - read key files
    code_summary = _build_code_summary(path, files, max_files=10)

    if not code_summary:
        console.print("[yellow]No suitable files found for pattern analysis.[/yellow]")
        return

    # Build prompt for design pattern analysis
    prompt = _build_pattern_prompt(code_summary)

    try:
        config = ConfigManager()
        llm_config = config.load().get("llm", {})

        if not llm_config:
            console.print("[yellow]No LLM configured. Run: rg init[/yellow]")
            return

        if verbose:
            console.print("[dim]Running AI analysis...[/dim]")

        client = LLMClient(llm_config)
        response = client.chat(prompt)

        # Parse and display results
        _display_pattern_suggestions(response)

    except Exception as e:
        console.print(f"[yellow]Pattern analysis failed: {e}[/yellow]")


def _build_code_summary(path: str, files: List[str], max_files: int = 10) -> str:
    """Build a summary of code structure for pattern analysis."""
    summary_parts = []

    # Filter to code files only
    code_extensions = {".py", ".js", ".ts", ".java", ".go", ".php", ".rb", ".cs", ".kt", ".swift", ".rs"}
    code_files = [f for f in files if Path(f).suffix.lower() in code_extensions]

    if not code_files:
        # Try to find files in path
        path_obj = Path(path)
        if path_obj.is_dir():
            for ext in code_extensions:
                code_files.extend([str(f) for f in path_obj.rglob(f"*{ext}")][:max_files])

    # Limit files
    code_files = code_files[:max_files]

    for file_path in code_files:
        try:
            content = Path(file_path).read_text(errors="ignore")
            # Truncate large files
            if len(content) > 3000:
                content = content[:3000] + "\n... (truncated)"

            summary_parts.append(f"=== {file_path} ===\n{content}\n")
        except Exception:
            continue

    return "\n".join(summary_parts)


def _build_pattern_prompt(code_summary: str) -> str:
    """Build prompt for design pattern analysis."""
    return f"""Analyze this codebase and suggest applicable design patterns.

## Code Summary
{code_summary}

## Instructions
1. Identify current patterns being used (if any)
2. Suggest design patterns that could improve the code
3. For EACH suggestion, provide:
   - Exact file paths that need changes
   - Current code snippet (copy from the code above)
   - Refactored code with the pattern applied
4. Focus on practical, actionable suggestions

## Design Patterns to Consider
- Creational: Factory, Builder, Singleton, Prototype
- Structural: Adapter, Facade, Decorator, Proxy, Composite
- Behavioral: Strategy, Observer, Command, State, Template Method
- Other: Repository, Service Layer, Dependency Injection, Event Sourcing

## Response Format (MUST follow this structure)

### CURRENT PATTERNS
List patterns already in use:
- **[Pattern Name]** in `[file_path]`: [Brief explanation]

### SUGGESTED IMPROVEMENTS

#### 1. [Pattern Name]

**Problem:** [What code smell or issue this solves]

**Affected Files:**
- `path/to/file1.py`
- `path/to/file2.py`

**Current Code:**
```[language]
# From: path/to/file.py (lines X-Y)
[paste the actual problematic code from the codebase]
```

**Refactored Code:**
```[language]
# Improved version with [Pattern Name]
[show the complete refactored code]
```

**Benefits:**
- [Benefit 1]
- [Benefit 2]

---

#### 2. [Next Pattern...]
[Same structure as above]

### SOLID VIOLATIONS

#### [S/O/L/I/D] - [Principle Name]
**File:** `path/to/file.py`
**Line:** [line number if applicable]
**Issue:** [Description]

**Current Code:**
```[language]
[problematic code]
```

**Fixed Code:**
```[language]
[corrected code]
```

---

IMPORTANT:
- Always include REAL code from the provided codebase
- Show complete, working code examples (not pseudocode)
- Be specific about file paths and line numbers
"""


def _display_pattern_suggestions(response: str):
    """Display pattern analysis results."""
    console.print()
    console.print(Panel(
        response,
        title="[bold]Design Pattern Analysis[/bold]",
        border_style="green",
        padding=(1, 2)
    ))


@quality_app.command("status")
def status_cmd():
    """Show quality settings and integration status."""
    config = ConfigManager()
    quality_config = config.get_quality_config()
    semgrep_config = config.get_semgrep_config()

    console.print("\n[bold cyan]Code Quality Settings[/bold cyan]\n")

    enabled = quality_config.get("enabled", False)
    enabled_str = "[green]Enabled[/green]" if enabled else "[dim]Disabled[/dim]"
    console.print(f"   Status: {enabled_str}")
    console.print(f"   Threshold: {quality_config.get('threshold', 70)}")
    console.print(f"   Fail on security: {quality_config.get('fail_on_security', True)}")
    console.print(f"   Prompt file: {quality_config.get('prompt_file', 'quality_prompt.md')}")

    # Check for custom prompt
    if USER_PROMPT_PATH.exists():
        console.print(f"   [green]Custom prompt: {USER_PROMPT_PATH}[/green]")
    else:
        console.print("   [dim]Using default prompt[/dim]")

    # Check for linter
    linter = _find_linter()
    console.print()
    if linter:
        console.print(f"   Linter: [green]{linter}[/green] (Python)")
    else:
        console.print("   Linter: [yellow]Not found[/yellow] (install ruff or flake8)")
        console.print("     [dim]pip install ruff[/dim]")

    # Check Semgrep status
    console.print()
    semgrep_enabled = semgrep_config.get("enabled", False)
    semgrep_installed = is_semgrep_installed()

    if semgrep_enabled and semgrep_installed:
        configs = ", ".join(semgrep_config.get("configs", ["auto"]))
        console.print("   Semgrep: [green]Enabled[/green] (35+ languages)")
        console.print(f"     Rule packs: {configs}")
    elif semgrep_enabled and not semgrep_installed:
        console.print("   Semgrep: [yellow]Enabled but not installed[/yellow]")
        console.print("     [dim]Install: pip install semgrep[/dim]")
    else:
        console.print("   Semgrep: [dim]Disabled[/dim]")
        console.print("     [dim]Enable: rg config semgrep --enable[/dim]")

    # Check for integration
    quality_integration = _get_code_quality()
    console.print()
    if quality_integration:
        console.print(f"   Integration: [green]{quality_integration.name}[/green]")
    else:
        console.print("   Integration: [dim]None (using AI + linter + Semgrep)[/dim]")
        available = get_integrations_by_type(IntegrationType.CODE_QUALITY)
        if available:
            console.print()
            console.print("   Available integrations:")
            for name in available[:5]:
                console.print(f"     [dim]- {name}[/dim]")
            console.print()
            console.print(f"   Install: [cyan]rg install {available[0]}[/cyan]")


@quality_app.command("report")
def report_cmd(
    commit: Optional[str] = typer.Option(None, "--commit", "-c", help="Analyze specific commit"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to analyze"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save report to file"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, json")
):
    """Generate a detailed quality report."""
    console.print("[bold cyan]Generating quality report...[/bold cyan]")

    try:
        result = analyze_quality(commit=commit, branch=branch, verbose=True)

        if format == "json":
            json_output = json.dumps(result, indent=2)
            if output:
                Path(output).write_text(json_output)
                console.print(f"\n[green]Report saved to {output}[/green]")
            else:
                console.print(json_output)
        else:
            if output:
                # Generate text report
                lines = [
                    "Code Quality Report",
                    "=" * 40,
                    f"Score: {result.get('score', 0)}/100",
                    f"Decision: {result.get('decision', 'reject').upper()}",
                    f"Summary: {result.get('summary', '')}",
                    "",
                    "Issues:",
                    "-" * 40,
                ]
                for issue in result.get("issues", []):
                    lines.append(
                        f"[{issue.get('severity', '').upper()}] "
                        f"{issue.get('file', '')}:{issue.get('line', '')} - "
                        f"{issue.get('description', '')}"
                    )
                    if issue.get("suggestion"):
                        lines.append(f"  Suggestion: {issue.get('suggestion')}")

                Path(output).write_text("\n".join(lines))
                console.print(f"\n[green]Report saved to {output}[/green]")
            else:
                config = ConfigManager()
                _display_result(result, config.get_quality_threshold())

    except Exception as e:
        console.print(f"[red]Report generation failed: {e}[/red]")
        raise typer.Exit(1)
