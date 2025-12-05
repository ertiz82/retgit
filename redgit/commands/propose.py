"""
Propose command - Analyze changes, match with tasks, and create commits.
"""

from typing import Optional, List, Dict, Any
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from ..core.config import ConfigManager, StateManager
from ..core.gitops import GitOps, NotAGitRepoError, init_git_repo
from ..core.llm import LLMClient
from ..core.prompt import PromptManager
from ..integrations.registry import get_task_management, get_code_hosting
from ..integrations.base import TaskManagementBase, Issue
from ..plugins.registry import load_plugins, get_active_plugin
from ..utils.security import filter_changes

console = Console()


def propose_cmd(
    prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p",
        help="Prompt template name (e.g., default, minimal, laravel)"
    ),
    no_task: bool = typer.Option(
        False, "--no-task",
        help="Skip task management integration"
    )
):
    """Analyze changes and propose commit groups with task matching."""

    config_manager = ConfigManager()
    state_manager = StateManager()
    config = config_manager.load()

    try:
        gitops = GitOps()
    except NotAGitRepoError:
        console.print("[yellow]⚠️  Not a git repository.[/yellow]")
        if Confirm.ask("Initialize git repository here?", default=True):
            remote_url = Prompt.ask("Remote URL (optional, press Enter to skip)", default="")
            remote_url = remote_url.strip() if remote_url else None
            try:
                init_git_repo(remote_url)
                console.print("[green]✓ Git repository initialized[/green]")
                if remote_url:
                    console.print(f"[green]✓ Remote 'origin' added: {remote_url}[/green]")
                gitops = GitOps()
            except Exception as e:
                console.print(f"[red]❌ Failed to initialize git: {e}[/red]")
                raise typer.Exit(1)
        else:
            raise typer.Exit(1)

    workflow = config.get("workflow", {})

    # Get task management integration if available
    task_mgmt: Optional[TaskManagementBase] = None
    if not no_task:
        task_mgmt = get_task_management(config)

    # Load plugins
    plugins = load_plugins(config.get("plugins", {}))
    active_plugin = get_active_plugin(plugins)

    # Get changes
    changes = gitops.get_changes()
    excluded_files = gitops.get_excluded_changes()

    if excluded_files:
        console.print(f"[dim]🔒 {len(excluded_files)} sensitive files excluded[/dim]")

    if not changes:
        console.print("[yellow]⚠️  No changes found.[/yellow]")
        return

    # Filter for sensitive files warning
    _, _, sensitive_files = filter_changes(changes, warn_sensitive=True)
    if sensitive_files:
        console.print(f"[yellow]⚠️  {len(sensitive_files)} potentially sensitive files detected[/yellow]")
        for f in sensitive_files[:3]:
            console.print(f"[yellow]   - {f}[/yellow]")
        if len(sensitive_files) > 3:
            console.print(f"[yellow]   ... and {len(sensitive_files) - 3} more[/yellow]")
        console.print("")

    console.print(f"[cyan]📁 {len(changes)} file changes found.[/cyan]")

    # Show active plugin
    if active_plugin:
        console.print(f"[magenta]🧩 Plugin: {active_plugin.name}[/magenta]")

    # Get active issues from task management
    active_issues: List[Issue] = []
    if task_mgmt and task_mgmt.enabled:
        console.print(f"[blue]📋 Task management: {task_mgmt.name}[/blue]")

        with console.status("Fetching active issues..."):
            active_issues = task_mgmt.get_my_active_issues()

        if active_issues:
            console.print(f"[green]   Found {len(active_issues)} active issues[/green]")
            _show_active_issues(active_issues)
        else:
            console.print("[dim]   No active issues found[/dim]")

        # Show sprint info if available
        if task_mgmt.supports_sprints():
            sprint = task_mgmt.get_active_sprint()
            if sprint:
                console.print(f"[blue]   🏃 Sprint: {sprint.name}[/blue]")

    console.print("")

    # Create LLM client
    try:
        llm = LLMClient(config.get("llm", {}))
        console.print(f"[dim]Using LLM: {llm.provider}[/dim]")
    except FileNotFoundError as e:
        console.print(f"[red]❌ LLM not found: {e}[/red]")
        return
    except Exception as e:
        console.print(f"[red]❌ LLM error: {e}[/red]")
        return

    # Get plugin prompt if available
    plugin_prompt = None
    if active_plugin and hasattr(active_plugin, "get_prompt"):
        plugin_prompt = active_plugin.get_prompt()

    # Create prompt with active issues context
    prompt_manager = PromptManager(config.get("llm", {}))
    try:
        final_prompt = prompt_manager.get_prompt(
            changes=changes,
            prompt_name=prompt,
            plugin_prompt=plugin_prompt,
            active_issues=active_issues
        )
    except FileNotFoundError as e:
        console.print(f"[red]❌ Prompt not found: {e}[/red]")
        return

    # Generate groups with AI
    console.print("\n[yellow]🤖 AI analyzing changes...[/yellow]\n")
    try:
        groups = llm.generate_groups(final_prompt)
    except Exception as e:
        console.print(f"[red]❌ LLM error: {e}[/red]")
        return

    if not groups:
        console.print("[yellow]⚠️  No groups created.[/yellow]")
        return

    # Separate matched and unmatched groups
    matched_groups = []
    unmatched_groups = []

    for group in groups:
        issue_key = group.get("issue_key")
        if issue_key and task_mgmt:
            # Verify issue exists
            issue = task_mgmt.get_issue(issue_key)
            if issue:
                group["_issue"] = issue
                matched_groups.append(group)
            else:
                console.print(f"[yellow]⚠️  Issue {issue_key} not found, treating as unmatched[/yellow]")
                group["issue_key"] = None
                unmatched_groups.append(group)
        else:
            unmatched_groups.append(group)

    # Show results
    _show_groups_summary(matched_groups, unmatched_groups, task_mgmt)

    # Confirm
    total_groups = len(matched_groups) + len(unmatched_groups)
    if not Confirm.ask(f"\nProceed with {total_groups} groups?"):
        return

    # Save base branch for session
    state_manager.set_base_branch(gitops.original_branch)

    # Process matched groups
    if matched_groups:
        console.print("\n[bold cyan]Processing matched groups...[/bold cyan]")
        _process_matched_groups(
            matched_groups, gitops, task_mgmt, state_manager, workflow
        )

    # Process unmatched groups
    if unmatched_groups:
        console.print("\n[bold yellow]Processing unmatched groups...[/bold yellow]")
        _process_unmatched_groups(
            unmatched_groups, gitops, task_mgmt, state_manager, workflow, config
        )

    # Summary
    session = state_manager.get_session()
    if session:
        branches = session.get("branches", [])
        issues = session.get("issues", [])
        console.print(f"\n[bold green]✅ Created {len(branches)} branches for {len(issues)} issues[/bold green]")

        strategy = workflow.get("strategy", "local-merge")
        if strategy == "local-merge":
            console.print("[dim]Run 'rg push' to push branches and complete issues[/dim]")
        else:
            console.print("[dim]Branches pushed. Run 'rg push' to complete issues[/dim]")


def _show_active_issues(issues: List[Issue]):
    """Display active issues in a compact format."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    for issue in issues[:5]:
        status_color = "green" if "progress" in issue.status.lower() else "yellow"
        table.add_row(
            f"[bold]{issue.key}[/bold]",
            f"[{status_color}]{issue.status}[/{status_color}]",
            issue.summary[:50] + ("..." if len(issue.summary) > 50 else "")
        )
    console.print(table)
    if len(issues) > 5:
        console.print(f"[dim]   ... and {len(issues) - 5} more[/dim]")


def _show_groups_summary(
    matched: List[Dict],
    unmatched: List[Dict],
    task_mgmt: Optional[TaskManagementBase]
):
    """Show summary of groups."""

    if matched:
        console.print("\n[bold green]✓ Matched with existing issues:[/bold green]")
        for g in matched:
            issue = g.get("_issue")
            console.print(f"  [green]• {g.get('issue_key')}[/green] - {g.get('commit_title', '')[:50]}")
            console.print(f"    [dim]{len(g.get('files', []))} files[/dim]")

    if unmatched:
        console.print("\n[bold yellow]? No matching issue:[/bold yellow]")
        for g in unmatched:
            console.print(f"  [yellow]• {g.get('commit_title', '')[:60]}[/yellow]")
            console.print(f"    [dim]{len(g.get('files', []))} files[/dim]")

        if task_mgmt and task_mgmt.enabled:
            console.print("\n[dim]New issues will be created for unmatched groups[/dim]")


def _process_matched_groups(
    groups: List[Dict],
    gitops: GitOps,
    task_mgmt: TaskManagementBase,
    state_manager: StateManager,
    workflow: dict
):
    """Process groups that matched with existing issues."""

    auto_transition = workflow.get("auto_transition", True)

    for i, group in enumerate(groups, 1):
        issue_key = group["issue_key"]
        issue = group.get("_issue")

        console.print(f"\n[cyan]({i}/{len(groups)}) {issue_key}: {group.get('commit_title', '')[:40]}...[/cyan]")

        # Format branch name using task management
        branch_name = task_mgmt.format_branch_name(issue_key, group.get("commit_title", ""))
        group["branch"] = branch_name

        # Create branch and commit
        try:
            with gitops.isolated_branch(branch_name):
                staged, excluded = gitops.stage_files(group.get("files", []))

                if excluded:
                    console.print(f"[yellow]   ⚠️  {len(excluded)} sensitive files skipped[/yellow]")

                if not staged:
                    console.print(f"[yellow]   ⚠️  No files to commit[/yellow]")
                    continue

                # Build commit message with issue reference
                commit_prefix = task_mgmt.get_commit_prefix()
                msg = f"{group['commit_title']}\n\n{group.get('commit_body', '')}"
                msg += f"\n\nRefs: {issue_key}"

                gitops.commit(msg, staged)
                console.print(f"[green]   ✓ Committed to {branch_name}[/green]")

                # Add comment to issue
                task_mgmt.on_commit(group, {"issue_key": issue_key})

                # Transition to In Progress if configured
                if auto_transition and issue.status.lower() not in ["in progress", "in development"]:
                    if task_mgmt.transition_issue(issue_key, "In Progress"):
                        console.print(f"[blue]   → Issue moved to In Progress[/blue]")

                # Save to session
                state_manager.add_session_branch(branch_name, issue_key)

        except Exception as e:
            console.print(f"[red]   ❌ Error: {e}[/red]")


def _process_unmatched_groups(
    groups: List[Dict],
    gitops: GitOps,
    task_mgmt: Optional[TaskManagementBase],
    state_manager: StateManager,
    workflow: dict,
    config: dict
):
    """Process groups that didn't match any existing issue."""

    create_policy = workflow.get("create_missing_issues", "ask")
    default_type = workflow.get("default_issue_type", "task")
    auto_transition = workflow.get("auto_transition", True)

    for i, group in enumerate(groups, 1):
        title = group.get("commit_title", "Untitled")
        console.print(f"\n[yellow]({i}/{len(groups)}) {title[:50]}...[/yellow]")

        issue_key = None

        # Handle issue creation
        if task_mgmt and task_mgmt.enabled:
            should_create = False

            if create_policy == "auto":
                should_create = True
            elif create_policy == "ask":
                should_create = Confirm.ask(f"   Create new issue for this group?", default=True)
            # else: skip

            if should_create:
                # Get issue details
                summary = Prompt.ask("   Issue title", default=title[:100])
                description = group.get("commit_body", "")

                # Create issue
                issue_key = task_mgmt.create_issue(
                    summary=summary,
                    description=description,
                    issue_type=default_type
                )

                if issue_key:
                    console.print(f"[green]   ✓ Created issue: {issue_key}[/green]")

                    # Transition to In Progress
                    if auto_transition:
                        task_mgmt.transition_issue(issue_key, "In Progress")
                else:
                    console.print("[red]   ❌ Failed to create issue[/red]")

        # Determine branch name
        if issue_key and task_mgmt:
            branch_name = task_mgmt.format_branch_name(issue_key, title)
        else:
            # Generate branch name without issue
            clean_title = title.lower()
            clean_title = "".join(c if c.isalnum() or c == " " else "" for c in clean_title)
            clean_title = clean_title.strip().replace(" ", "-")[:40]
            branch_name = f"feature/{clean_title}"

        group["branch"] = branch_name
        group["issue_key"] = issue_key

        # Create branch and commit
        try:
            with gitops.isolated_branch(branch_name):
                staged, excluded = gitops.stage_files(group.get("files", []))

                if excluded:
                    console.print(f"[yellow]   ⚠️  {len(excluded)} sensitive files skipped[/yellow]")

                if not staged:
                    console.print(f"[yellow]   ⚠️  No files to commit[/yellow]")
                    continue

                # Build commit message
                msg = f"{group['commit_title']}\n\n{group.get('commit_body', '')}"
                if issue_key:
                    msg += f"\n\nRefs: {issue_key}"

                gitops.commit(msg, staged)
                console.print(f"[green]   ✓ Committed to {branch_name}[/green]")

                # Add comment if issue was created
                if issue_key and task_mgmt:
                    task_mgmt.on_commit(group, {"issue_key": issue_key})

                # Save to session
                state_manager.add_session_branch(branch_name, issue_key)

        except Exception as e:
            console.print(f"[red]   ❌ Error: {e}[/red]")