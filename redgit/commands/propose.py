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
from ..integrations.registry import get_task_management, get_code_hosting, get_notification
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
    ),
    task: Optional[str] = typer.Option(
        None, "--task", "-t",
        help="Link all changes to a specific task/issue number (e.g., 123 or PROJ-123)"
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

    # Handle --task flag: commit all changes to a specific task
    if task:
        _process_task_commit(task, changes, gitops, task_mgmt, state_manager, config)
        return

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

    # Get issue_language from Jira config if available
    issue_language = None
    if task_mgmt and hasattr(task_mgmt, 'issue_language'):
        issue_language = task_mgmt.issue_language

    try:
        final_prompt = prompt_manager.get_prompt(
            changes=changes,
            prompt_name=prompt,
            plugin_prompt=plugin_prompt,
            active_issues=active_issues,
            issue_language=issue_language
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
    strategy = workflow.get("strategy", "local-merge")
    if session:
        branches = session.get("branches", [])
        issues = session.get("issues", [])
        console.print(f"\n[bold green]✅ Created {len(branches)} commits for {len(issues)} issues[/bold green]")
        if strategy == "local-merge":
            console.print("[dim]All commits are merged to current branch.[/dim]")
            console.print("[dim]Run 'rg push' to push to remote and complete issues[/dim]")
        else:
            console.print("[dim]Branches ready for push and PR creation.[/dim]")
            console.print("[dim]Run 'rg push --pr' to push branches and create pull requests[/dim]")

        # Send session summary notification
        _send_session_summary_notification(config, len(branches), len(issues))


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
    strategy = workflow.get("strategy", "local-merge")

    for i, group in enumerate(groups, 1):
        issue_key = group["issue_key"]
        issue = group.get("_issue")

        console.print(f"\n[cyan]({i}/{len(groups)}) {issue_key}: {group.get('commit_title', '')[:40]}...[/cyan]")

        # Format branch name using task management
        branch_name = task_mgmt.format_branch_name(issue_key, group.get("commit_title", ""))
        group["branch"] = branch_name

        # Build commit message with issue reference
        msg = f"{group['commit_title']}\n\n{group.get('commit_body', '')}"
        msg += f"\n\nRefs: {issue_key}"

        # Create branch and commit using new method
        try:
            files = group.get("files", [])
            success = gitops.create_branch_and_commit(branch_name, files, msg, strategy=strategy)

            if success:
                if strategy == "local-merge":
                    console.print(f"[green]   ✓ Committed and merged {branch_name}[/green]")
                else:
                    console.print(f"[green]   ✓ Committed to {branch_name}[/green]")

                # Add comment to issue
                task_mgmt.on_commit(group, {"issue_key": issue_key})

                # Transition to In Progress if configured
                if auto_transition and issue.status.lower() not in ["in progress", "in development"]:
                    if task_mgmt.transition_issue(issue_key, "In Progress"):
                        console.print(f"[blue]   → Issue moved to In Progress[/blue]")

                # Save to session
                state_manager.add_session_branch(branch_name, issue_key)
            else:
                console.print(f"[yellow]   ⚠️  No files to commit[/yellow]")

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
    strategy = workflow.get("strategy", "local-merge")

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
                # Get issue details - prefer issue_title (localized) if available
                default_summary = group.get("issue_title") or title[:100]
                summary = Prompt.ask("   Issue title", default=default_summary)
                description = group.get("commit_body", "")

                # Create issue
                issue_key = task_mgmt.create_issue(
                    summary=summary,
                    description=description,
                    issue_type=default_type
                )

                if issue_key:
                    console.print(f"[green]   ✓ Created issue: {issue_key}[/green]")
                    # Send notification for issue creation
                    _send_issue_created_notification(config, issue_key, summary)

                    # Transition to In Progress
                    if auto_transition:
                        if task_mgmt.transition_issue(issue_key, "In Progress"):
                            console.print(f"[green]   ✓ {issue_key} → In Progress[/green]")
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

        # Build commit message
        msg = f"{group['commit_title']}\n\n{group.get('commit_body', '')}"
        if issue_key:
            msg += f"\n\nRefs: {issue_key}"

        # Create branch and commit using new method
        try:
            files = group.get("files", [])
            success = gitops.create_branch_and_commit(branch_name, files, msg, strategy=strategy)

            if success:
                if strategy == "local-merge":
                    console.print(f"[green]   ✓ Committed and merged {branch_name}[/green]")
                else:
                    console.print(f"[green]   ✓ Committed to {branch_name}[/green]")

                # Add comment if issue was created
                if issue_key and task_mgmt:
                    task_mgmt.on_commit(group, {"issue_key": issue_key})

                # Save to session
                state_manager.add_session_branch(branch_name, issue_key)
            else:
                console.print(f"[yellow]   ⚠️  No files to commit[/yellow]")

        except Exception as e:
            console.print(f"[red]   ❌ Error: {e}[/red]")


def _process_task_commit(
    task_id: str,
    changes: List[str],
    gitops: GitOps,
    task_mgmt: Optional[TaskManagementBase],
    state_manager: StateManager,
    config: dict
):
    """
    Process all changes as a single commit linked to a specific task.

    This is triggered when --task flag is used:
    rg propose --task 123
    rg propose --task PROJ-123
    """
    workflow = config.get("workflow", {})
    strategy = workflow.get("strategy", "local-merge")
    auto_transition = workflow.get("auto_transition", True)

    # Resolve issue key
    issue_key = task_id
    issue = None

    if task_mgmt and task_mgmt.enabled:
        console.print(f"[blue]📋 Task management: {task_mgmt.name}[/blue]")

        # If task_id is just a number, prepend project key
        if task_id.isdigit() and hasattr(task_mgmt, 'project_key') and task_mgmt.project_key:
            issue_key = f"{task_mgmt.project_key}-{task_id}"

        # Fetch issue details
        with console.status(f"Fetching issue {issue_key}..."):
            issue = task_mgmt.get_issue(issue_key)

        if not issue:
            console.print(f"[red]❌ Issue {issue_key} not found[/red]")
            raise typer.Exit(1)

        console.print(f"[green]✓ Found: {issue_key} - {issue.summary}[/green]")
        console.print(f"[dim]   Status: {issue.status}[/dim]")
    else:
        console.print(f"[yellow]⚠️  No task management configured, using {issue_key} as reference[/yellow]")

    # Extract file paths from changes (changes is list of dicts)
    file_paths = [c["file"] if isinstance(c, dict) else c for c in changes]

    # Show changes summary
    console.print(f"\n[cyan]📁 {len(file_paths)} files will be committed:[/cyan]")
    for f in file_paths[:10]:
        console.print(f"[dim]   • {f}[/dim]")
    if len(file_paths) > 10:
        console.print(f"[dim]   ... and {len(file_paths) - 10} more[/dim]")

    # Generate commit message
    if issue:
        commit_title = f"{issue_key}: {issue.summary}"
        commit_body = issue.description[:500] if issue.description else ""
    else:
        commit_title = f"Changes for {issue_key}"
        commit_body = ""

    # Format branch name
    if task_mgmt and hasattr(task_mgmt, 'format_branch_name'):
        branch_name = task_mgmt.format_branch_name(issue_key, issue.summary if issue else task_id)
    else:
        branch_name = f"feature/{issue_key.lower()}"

    console.print(f"\n[cyan]📝 Commit:[/cyan]")
    console.print(f"   Title: {commit_title[:60]}{'...' if len(commit_title) > 60 else ''}")
    console.print(f"   Branch: {branch_name}")
    console.print(f"   Files: {len(changes)}")

    # Confirm
    if not Confirm.ask("\nProceed?", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    # Build full commit message
    msg = f"{commit_title}\n\n{commit_body}".strip()
    msg += f"\n\nRefs: {issue_key}"

    # Save base branch for session
    state_manager.set_base_branch(gitops.original_branch)

    # Create branch and commit (use file_paths, not changes dict)
    try:
        success = gitops.create_branch_and_commit(branch_name, file_paths, msg, strategy=strategy)

        if success:
            if strategy == "local-merge":
                console.print(f"[green]✓ Committed and merged {branch_name}[/green]")
            else:
                console.print(f"[green]✓ Committed to {branch_name}[/green]")

            # Add comment to issue
            if task_mgmt and issue:
                group = {
                    "commit_title": commit_title,
                    "branch": branch_name,
                    "files": file_paths
                }
                task_mgmt.on_commit(group, {"issue_key": issue_key})
                console.print(f"[blue]✓ Comment added to {issue_key}[/blue]")

            # Transition to In Progress if configured
            if task_mgmt and issue and auto_transition:
                if issue.status.lower() not in ["in progress", "in development"]:
                    if task_mgmt.transition_issue(issue_key, "In Progress"):
                        console.print(f"[blue]→ {issue_key} moved to In Progress[/blue]")

            # Save to session
            state_manager.add_session_branch(branch_name, issue_key)

            # Send commit notification
            _send_commit_notification(config, branch_name, issue_key, len(file_paths))

            console.print(f"\n[bold green]✅ All changes committed to {issue_key}[/bold green]")
            console.print("[dim]Run 'rg push' to push to remote[/dim]")
        else:
            console.print("[yellow]⚠️  No files to commit[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


def _is_notification_enabled(config: dict, event: str) -> bool:
    """Check if notification is enabled for a specific event."""
    from ..core.config import ConfigManager
    config_manager = ConfigManager()
    return config_manager.is_notification_enabled(event)


def _send_commit_notification(config: dict, branch: str, issue_key: str = None, files_count: int = 0):
    """Send notification about commit creation."""
    if not _is_notification_enabled(config, "commit"):
        return

    notification = get_notification(config)
    if not notification or not notification.enabled:
        return

    try:
        message = f"📝 Committed to `{branch}`"
        if issue_key:
            message += f" ({issue_key})"
        if files_count:
            message += f"\n{files_count} files"
        notification.send_message(message)
    except Exception:
        pass


def _send_issue_created_notification(config: dict, issue_key: str, summary: str = None):
    """Send notification about issue creation."""
    if not _is_notification_enabled(config, "issue_created"):
        return

    notification = get_notification(config)
    if not notification or not notification.enabled:
        return

    try:
        message = f"🆕 Issue created: {issue_key}"
        if summary:
            message += f"\n{summary[:100]}"
        notification.send_message(message)
    except Exception:
        pass


def _send_session_summary_notification(config: dict, branches_count: int, issues_count: int):
    """Send notification about session summary."""
    if not _is_notification_enabled(config, "session_complete"):
        return

    notification = get_notification(config)
    if not notification or not notification.enabled:
        return

    try:
        message = f"📦 Session complete: {branches_count} commits"
        if issues_count:
            message += f", {issues_count} issues"
        message += "\nRun `rg push` to push to remote"
        notification.send_message(message)
    except Exception:
        pass