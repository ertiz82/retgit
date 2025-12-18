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
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Analyze and show what would be done without making changes"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Show detailed information (prompts, AI request/response, etc.)"
    ),
    detailed: bool = typer.Option(
        False, "--detailed", "-d",
        help="Generate detailed commit messages using file diffs (slower but more accurate)"
    )
):
    """Analyze changes and propose commit groups with task matching."""

    # Dry run banner
    if dry_run:
        console.print(Panel("[bold yellow]DRY RUN MODE[/bold yellow] - No changes will be made", style="yellow"))

    config_manager = ConfigManager()
    state_manager = StateManager()
    config = config_manager.load()

    # Verbose: Show config paths
    if verbose:
        from ..core.config import RETGIT_DIR
        console.print(Panel("[bold cyan]VERBOSE MODE[/bold cyan]", style="cyan"))
        console.print(f"[dim]Config: {RETGIT_DIR / 'config.yaml'}[/dim]")

    try:
        gitops = GitOps()
    except NotAGitRepoError:
        console.print("[yellow]⚠️  Not a git repository.[/yellow]")
        if dry_run:
            console.print("[yellow]Dry run: Would ask to initialize git repository[/yellow]")
            return
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

    # Verbose: Show task management config
    if verbose and task_mgmt:
        console.print(f"\n[bold cyan]═══ Task Management Config ═══[/bold cyan]")
        console.print(f"[dim]Integration: {task_mgmt.name}[/dim]")
        if hasattr(task_mgmt, 'issue_language'):
            console.print(f"[dim]Issue Language: {task_mgmt.issue_language or 'default (en)'}[/dim]")
        if hasattr(task_mgmt, 'project_key'):
            console.print(f"[dim]Project Key: {task_mgmt.project_key}[/dim]")

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
        if dry_run:
            console.print(f"[yellow]Dry run: Would commit all changes to task {task}[/yellow]")
            return
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

    # Verbose: Show prompt sources
    if verbose:
        console.print(f"\n[bold cyan]═══ Prompt Sources ═══[/bold cyan]")
        _show_prompt_sources(prompt, plugin_prompt, active_plugin, issue_language)

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

    # Verbose: Show full prompt
    if verbose:
        console.print(f"\n[bold cyan]═══ Full Prompt Sent to AI ═══[/bold cyan]")
        console.print(Panel(final_prompt[:3000] + ("..." if len(final_prompt) > 3000 else ""), title="Prompt", border_style="cyan"))
        console.print(f"[dim]Total prompt length: {len(final_prompt)} characters[/dim]")

    # Generate groups with AI
    console.print("\n[yellow]🤖 AI analyzing changes...[/yellow]\n")
    try:
        if verbose:
            # Use verbose mode in LLM client if available
            groups, raw_response = llm.generate_groups(final_prompt, return_raw=True) if hasattr(llm, 'generate_groups') else (llm.generate_groups(final_prompt), None)
            if raw_response:
                console.print(f"\n[bold cyan]═══ Raw AI Response ═══[/bold cyan]")
                console.print(Panel(raw_response[:5000] + ("..." if len(raw_response) > 5000 else ""), title="AI Response", border_style="green"))
        else:
            groups = llm.generate_groups(final_prompt)
    except Exception as e:
        console.print(f"[red]❌ LLM error: {e}[/red]")
        return

    if not groups:
        console.print("[yellow]⚠️  No groups created.[/yellow]")
        return

    # Detailed mode: enhance groups with diff-based analysis
    if detailed:
        console.print("\n[cyan]🔍 Analyzing diffs for detailed messages...[/cyan]")
        groups = _enhance_groups_with_diffs(
            groups=groups,
            gitops=gitops,
            llm=llm,
            issue_language=issue_language,
            verbose=verbose,
            task_mgmt=task_mgmt
        )
        console.print("[green]✓ Detailed analysis complete[/green]\n")

    # Verbose: Show parsed groups
    if verbose:
        import json
        console.print(f"\n[bold cyan]═══ Parsed Groups ({len(groups)}) ═══[/bold cyan]")
        for i, g in enumerate(groups, 1):
            console.print(f"\n[bold]Group {i}:[/bold]")
            console.print(f"  [dim]Files:[/dim] {len(g.get('files', []))} files")
            console.print(f"  [dim]commit_title:[/dim] {g.get('commit_title', 'N/A')}")
            console.print(f"  [dim]issue_key:[/dim] {g.get('issue_key', 'null')}")
            console.print(f"  [dim]issue_title:[/dim] {g.get('issue_title', 'null')}")
            if g.get('files'):
                console.print(f"  [dim]Files list:[/dim]")
                for f in g.get('files', [])[:5]:
                    console.print(f"    - {f}")
                if len(g.get('files', [])) > 5:
                    console.print(f"    ... and {len(g.get('files', [])) - 5} more")

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

    # Dry run: Show what would be done and exit
    if dry_run:
        console.print(f"\n[bold yellow]═══ DRY RUN SUMMARY ═══[/bold yellow]")
        console.print(f"\n[yellow]Would create {len(matched_groups) + len(unmatched_groups)} commits:[/yellow]")

        if matched_groups:
            console.print(f"\n[green]Matched with existing issues ({len(matched_groups)}):[/green]")
            for g in matched_groups:
                issue = g.get("_issue")
                branch = task_mgmt.format_branch_name(g["issue_key"], g.get("commit_title", "")) if task_mgmt else f"feature/{g['issue_key']}"
                console.print(f"  • [bold]{g['issue_key']}[/bold]: {g.get('commit_title', '')[:50]}")
                console.print(f"    Branch: {branch}")
                console.print(f"    Files: {len(g.get('files', []))}")

        if unmatched_groups:
            console.print(f"\n[yellow]New issues to create ({len(unmatched_groups)}):[/yellow]")
            for g in unmatched_groups:
                console.print(f"  • {g.get('commit_title', '')[:50]}")
                console.print(f"    Issue title: {g.get('issue_title', 'N/A')}")
                console.print(f"    Files: {len(g.get('files', []))}")

        console.print(f"\n[dim]Run without --dry-run to apply changes[/dim]")
        return

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
            unmatched_groups, gitops, task_mgmt, state_manager, workflow, config, llm
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


def _show_prompt_sources(
    prompt_name: Optional[str],
    plugin_prompt: Optional[str],
    active_plugin: Optional[Any],
    issue_language: Optional[str]
):
    """Show which prompt sources are being used (for verbose mode)."""
    from pathlib import Path
    from ..core.config import RETGIT_DIR
    from ..core.prompt import BUILTIN_PROMPTS_DIR, PROMPT_CATEGORIES

    console.print(f"[dim]Prompt name (CLI): {prompt_name or 'auto'}[/dim]")
    console.print(f"[dim]Active plugin: {active_plugin.name if active_plugin else 'none'}[/dim]")
    console.print(f"[dim]Plugin prompt: {'yes' if plugin_prompt else 'no'}[/dim]")
    console.print(f"[dim]Issue language: {issue_language or 'en (default)'}[/dim]")

    # Check where the commit prompt comes from (same logic as _load_by_name)
    category = "commit"
    name = prompt_name or "default"

    # 1. User override path: .redgit/prompts/commit/default.md
    user_path = RETGIT_DIR / "prompts" / category / f"{name}.md"
    if user_path.exists():
        console.print(f"\n[green]✓ Using USER prompt:[/green] {user_path}")
    else:
        # 2. Legacy user path: .redgit/prompts/default.md
        user_legacy = RETGIT_DIR / "prompts" / f"{name}.md"
        if user_legacy.exists():
            console.print(f"\n[green]✓ Using USER prompt (legacy path):[/green] {user_legacy}")
        else:
            # 3. Builtin path
            builtin_dir = PROMPT_CATEGORIES.get(category)
            if builtin_dir:
                builtin_path = builtin_dir / f"{name}.md"
                if builtin_path.exists():
                    console.print(f"\n[cyan]Using BUILTIN prompt:[/cyan] {builtin_path}")
                else:
                    console.print(f"\n[yellow]Prompt not found:[/yellow] {name}")

    # Show all user overrides in prompts folder
    user_prompts_dir = RETGIT_DIR / "prompts"
    if user_prompts_dir.exists():
        user_files = list(user_prompts_dir.rglob("*.md"))
        if user_files:
            console.print(f"\n[dim]User prompt overrides ({len(user_files)}):[/dim]")
            for f in user_files[:10]:
                rel_path = f.relative_to(user_prompts_dir)
                console.print(f"  [dim]• {rel_path}[/dim]")
            if len(user_files) > 10:
                console.print(f"  [dim]... and {len(user_files) - 10} more[/dim]")


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
            # Show issue_title (localized) if available, fallback to commit_title
            display_title = g.get('issue_title') or g.get('commit_title', '')
            console.print(f"  [yellow]• {display_title[:60]}[/yellow]")
            # Also show commit_title if different from issue_title
            if g.get('issue_title') and g.get('commit_title'):
                console.print(f"    [dim]commit: {g.get('commit_title', '')[:50]}[/dim]")
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
                    _transition_issue_with_strategy(task_mgmt, issue_key, "after_propose")

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
    config: dict,
    llm: LLMClient = None
):
    """Process groups that didn't match any existing issue."""

    create_policy = workflow.get("create_missing_issues", "ask")
    default_type = workflow.get("default_issue_type", "task")
    auto_transition = workflow.get("auto_transition", True)
    strategy = workflow.get("strategy", "local-merge")

    for i, group in enumerate(groups, 1):
        # Show issue_title (localized) if available, fallback to commit_title
        display_title = group.get("issue_title") or group.get("commit_title", "Untitled")
        console.print(f"\n[yellow]({i}/{len(groups)}) {display_title[:50]}...[/yellow]")

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
                # Use issue_title and commit_body from group (already generated if -d was used)
                default_summary = group.get("issue_title") or display_title[:100]
                description = group.get("issue_description") or group.get("commit_body", "")

                # In auto mode, don't prompt for title
                if create_policy == "auto":
                    summary = default_summary
                    console.print(f"[dim]   Issue: {summary[:60]}...[/dim]")
                else:
                    summary = Prompt.ask("   Issue title", default=default_summary)

                # Try to create issue, handle permission errors
                try:
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
                            _transition_issue_with_strategy(task_mgmt, issue_key, "after_propose")
                    else:
                        console.print("[red]   ❌ Failed to create issue[/red]")

                except PermissionError as e:
                    # User doesn't have permission to create issues
                    console.print(f"[yellow]   ⚠️  No permission to create issues: {e}[/yellow]")
                    console.print("[dim]   You can create a subtask under an existing issue instead.[/dim]")

                    # Ask for parent issue key
                    parent_key = Prompt.ask(
                        "   Parent issue key (e.g., PROJ-123)",
                        default=""
                    )

                    if parent_key:
                        # Create subtask under parent
                        try:
                            issue_key = task_mgmt.create_issue(
                                summary=summary,
                                description=description,
                                issue_type="subtask",
                                parent_key=parent_key
                            )

                            if issue_key:
                                console.print(f"[green]   ✓ Created subtask: {issue_key} (under {parent_key})[/green]")
                                _send_issue_created_notification(config, issue_key, summary)

                                if auto_transition:
                                    _transition_issue_with_strategy(task_mgmt, issue_key, "after_propose")
                            else:
                                console.print("[red]   ❌ Failed to create subtask[/red]")
                        except Exception as sub_e:
                            console.print(f"[red]   ❌ Failed to create subtask: {sub_e}[/red]")
                    else:
                        console.print("[dim]   Skipping issue creation (no parent specified)[/dim]")

        # Determine branch name
        commit_title = group.get("commit_title", "untitled")
        if issue_key and task_mgmt:
            branch_name = task_mgmt.format_branch_name(issue_key, commit_title)
        else:
            # Generate branch name without issue
            clean_title = commit_title.lower()
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
                    _transition_issue_with_strategy(task_mgmt, issue_key, "after_propose")

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


def _transition_issue_with_strategy(task_mgmt, issue_key: str, target_status: str = "after_propose") -> bool:
    """Transition issue using the configured strategy (auto or ask).

    Args:
        task_mgmt: Task management integration
        issue_key: Issue key to transition
        target_status: Target status mapping key (default: after_propose)

    Returns:
        True if transitioned, False if skipped or failed
    """
    strategy = getattr(task_mgmt, 'transition_strategy', 'auto')

    if strategy == 'ask':
        return _transition_issue_interactive(task_mgmt, issue_key)
    else:
        # Auto mode - use status mapping
        return task_mgmt.transition_issue(issue_key, target_status)


def _transition_issue_interactive(task_mgmt, issue_key: str) -> bool:
    """Interactively ask user to select target status for an issue.

    Returns:
        True if transitioned, False if skipped
    """
    try:
        # Get current issue info
        issue = task_mgmt.get_issue(issue_key)
        old_status = issue.status if issue else "Unknown"

        # Get available transitions
        transitions = task_mgmt.get_available_transitions(issue_key)

        if not transitions:
            console.print(f"[dim]   No transitions available for {issue_key}[/dim]")
            return False

        # Show options
        console.print(f"[dim]   Current status: {old_status}[/dim]")
        console.print("   [bold]Move to:[/bold]")
        for i, t in enumerate(transitions, 1):
            console.print(f"     [{i}] {t['to']}")
        console.print(f"     [0] Skip (don't change)")

        # Get user choice
        while True:
            choice = Prompt.ask("   Select", default="1")

            if choice == "0":
                console.print(f"[dim]   - {issue_key}: Skipped[/dim]")
                return False

            elif choice.isdigit() and 1 <= int(choice) <= len(transitions):
                idx = int(choice) - 1
                target_status = transitions[idx]["to"]
                transition_id = transitions[idx]["id"]

                if task_mgmt.transition_issue_by_id(issue_key, transition_id):
                    console.print(f"[blue]   → {issue_key}: {old_status} → {target_status}[/blue]")
                    return True
                else:
                    console.print(f"[yellow]   ⚠️  Could not transition {issue_key}[/yellow]")
                    return False

            else:
                console.print("[red]   Invalid choice[/red]")

    except Exception as e:
        console.print(f"[red]   ❌ Transition error: {e}[/red]")
        return False


def _enhance_groups_with_diffs(
    groups: List[Dict],
    gitops: GitOps,
    llm: LLMClient,
    issue_language: Optional[str] = None,
    verbose: bool = False,
    task_mgmt: Optional[TaskManagementBase] = None
) -> List[Dict]:
    """
    Enhance each group with detailed commit messages generated from file diffs.

    For each group:
    1. Get the diffs for all files in the group
    2. Send diffs to LLM with a specialized prompt (or integration's prompts if available)
    3. Generate detailed commit_title, commit_body, issue_title, issue_description

    Args:
        groups: List of commit groups from initial analysis
        gitops: GitOps instance for getting diffs
        llm: LLM client for generating messages
        issue_language: Language for issue titles/descriptions
        verbose: Show detailed output
        task_mgmt: Task management integration (for custom prompts)

    Returns:
        Enhanced groups with better commit messages
    """
    enhanced_groups = []

    # Debug: Show what we received
    if verbose:
        console.print(f"\n[bold cyan]═══ Detailed Mode Debug ═══[/bold cyan]")
        console.print(f"[dim]task_mgmt: {task_mgmt}[/dim]")
        console.print(f"[dim]task_mgmt.name: {task_mgmt.name if task_mgmt else 'N/A'}[/dim]")
        console.print(f"[dim]issue_language param: {issue_language}[/dim]")
        if task_mgmt:
            console.print(f"[dim]task_mgmt.issue_language: {getattr(task_mgmt, 'issue_language', 'NOT_FOUND')}[/dim]")
            console.print(f"[dim]has_user_prompt method: {hasattr(task_mgmt, 'has_user_prompt')}[/dim]")

    # Check if user has EXPORTED custom prompts for this integration
    # (not just built-in defaults)
    has_custom_prompts = False
    title_prompt_path = None
    desc_prompt_path = None

    if task_mgmt and hasattr(task_mgmt, 'has_user_prompt'):
        from ..core.config import RETGIT_DIR
        has_title = task_mgmt.has_user_prompt("issue_title")
        has_desc = task_mgmt.has_user_prompt("issue_description")
        if has_title or has_desc:
            has_custom_prompts = True
            if has_title:
                title_prompt_path = str(RETGIT_DIR / "prompts" / "integrations" / task_mgmt.name / "issue_title.md")
            if has_desc:
                desc_prompt_path = str(RETGIT_DIR / "prompts" / "integrations" / task_mgmt.name / "issue_description.md")
            if verbose:
                console.print(f"\n[bold cyan]═══ Integration Prompts ═══[/bold cyan]")
                console.print(f"[green]✓ Using USER-EXPORTED prompts for issue generation[/green]")
                if title_prompt_path:
                    console.print(f"[dim]  issue_title: {title_prompt_path}[/dim]")
                if desc_prompt_path:
                    console.print(f"[dim]  issue_description: {desc_prompt_path}[/dim]")
        elif verbose:
            console.print(f"\n[bold cyan]═══ Integration Prompts ═══[/bold cyan]")
            console.print(f"[dim]Using RedGit default prompts (no user exports found)[/dim]")
            console.print(f"[dim]  issue_title: builtin default[/dim]")
            console.print(f"[dim]  issue_description: builtin default[/dim]")

    for i, group in enumerate(groups, 1):
        files = group.get("files", [])
        if not files:
            enhanced_groups.append(group)
            continue

        if verbose:
            console.print(f"\n[bold cyan]═══ Detailed Analysis: Group {i}/{len(groups)} ═══[/bold cyan]")
            console.print(f"[dim]Files: {len(files)}[/dim]")
            for f in files[:5]:
                console.print(f"[dim]  - {f}[/dim]")
            if len(files) > 5:
                console.print(f"[dim]  ... and {len(files) - 5} more[/dim]")
        else:
            console.print(f"[dim]   ({i}/{len(groups)}) Analyzing {len(files)} files...[/dim]")

        # Get diffs for files in this group
        try:
            diffs = gitops.get_diffs_for_files(files)
        except Exception as e:
            if verbose:
                console.print(f"[yellow]⚠️  Could not get diffs: {e}[/yellow]")
            enhanced_groups.append(group)
            continue

        if not diffs:
            enhanced_groups.append(group)
            continue

        # Build prompt for detailed analysis
        # Use integration's prompts if available
        if has_custom_prompts:
            prompt = _build_detailed_analysis_prompt_with_integration(
                files=files,
                diffs=diffs,
                initial_title=group.get("commit_title", ""),
                initial_body=group.get("commit_body", ""),
                task_mgmt=task_mgmt
            )
            prompt_source = "integration prompts"
        else:
            prompt = _build_detailed_analysis_prompt(
                files=files,
                diffs=diffs,
                initial_title=group.get("commit_title", ""),
                initial_body=group.get("commit_body", ""),
                issue_language=issue_language
            )
            prompt_source = f"builtin (issue_language={issue_language or 'en'})"

        if verbose:
            console.print(f"\n[bold]Prompt Source:[/bold] {prompt_source}")
            console.print(f"[dim]Prompt length: {len(prompt)} chars[/dim]")
            # Show full prompt in a panel
            console.print(Panel(
                prompt[:4000] + ("..." if len(prompt) > 4000 else ""),
                title=f"[cyan]LLM Prompt (Group {i})[/cyan]",
                border_style="cyan"
            ))

        # Get detailed analysis from LLM
        try:
            result = llm.chat(prompt)

            if verbose:
                # Show raw response
                console.print(Panel(
                    result[:3000] + ("..." if len(result) > 3000 else ""),
                    title=f"[green]LLM Raw Response (Group {i})[/green]",
                    border_style="green"
                ))

            enhanced = _parse_detailed_result(result, group)

            if verbose:
                console.print(f"\n[bold]Parsed Result:[/bold]")
                console.print(f"[dim]  commit_title: {enhanced.get('commit_title', 'N/A')[:60]}[/dim]")
                console.print(f"[dim]  issue_title: {enhanced.get('issue_title', 'N/A')[:60]}[/dim]")
                console.print(f"[dim]  issue_description: {enhanced.get('issue_description', 'N/A')[:80]}...[/dim]")

            enhanced_groups.append(enhanced)
        except Exception as e:
            if verbose:
                console.print(f"[yellow]⚠️  LLM error, using original: {e}[/yellow]")
            enhanced_groups.append(group)

    return enhanced_groups


def _build_detailed_analysis_prompt(
    files: List[str],
    diffs: str,
    initial_title: str = "",
    initial_body: str = "",
    issue_language: Optional[str] = None
) -> str:
    """Build a prompt for detailed commit message analysis from diffs."""

    # Language instruction
    lang_instruction = ""
    if issue_language and issue_language != "en":
        lang_names = {
            "tr": "Turkish",
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
        lang_name = lang_names.get(issue_language, issue_language)
        lang_instruction = f"""
## IMPORTANT: Language Requirements
- **issue_title**: MUST be written in {lang_name}
- **issue_description**: MUST be written in {lang_name}
- commit_title and commit_body: English
"""

    # Truncate diffs if too long (max ~8000 chars for diff content)
    max_diff_length = 8000
    if len(diffs) > max_diff_length:
        diffs = diffs[:max_diff_length] + "\n\n... (diff truncated)"

    prompt = f"""Analyze these code changes and generate a detailed commit message and issue description.

## Files Changed
{chr(10).join(f"- {f}" for f in files)}

## Code Diff
```diff
{diffs}
```

## Initial Analysis
- Title: {initial_title}
- Body: {initial_body}
{lang_instruction}
## Task
Based on the actual code changes (diff), generate:

1. **commit_title**: A concise conventional commit message (feat/fix/refactor/chore) in English
2. **commit_body**: Bullet points describing what changed in English
3. **issue_title**: A clear title for a Jira/task management issue{' in ' + lang_names.get(issue_language, issue_language) if issue_language and issue_language != 'en' else ''}
4. **issue_description**: A detailed description of what this change does{' in ' + lang_names.get(issue_language, issue_language) if issue_language and issue_language != 'en' else ''}

## Response Format (JSON only)
```json
{{
  "commit_title": "feat: add user authentication",
  "commit_body": "- Add login endpoint\\n- Add JWT token validation\\n- Add password hashing",
  "issue_title": "Add user authentication feature",
  "issue_description": "This change implements user authentication including login, JWT tokens, and secure password handling."
}}
```

Return ONLY the JSON object, no other text.
"""
    return prompt


def _build_detailed_analysis_prompt_with_integration(
    files: List[str],
    diffs: str,
    initial_title: str = "",
    initial_body: str = "",
    task_mgmt: Optional[TaskManagementBase] = None
) -> str:
    """Build a prompt using integration's custom prompts for issue generation."""

    # Truncate diffs if too long
    max_diff_length = 8000
    if len(diffs) > max_diff_length:
        diffs = diffs[:max_diff_length] + "\n\n... (diff truncated)"

    file_list = "\n".join(f"- {f}" for f in files[:20])
    if len(files) > 20:
        file_list += f"\n... and {len(files) - 20} more"

    # Get language info from task_mgmt
    language = "English"
    if task_mgmt and hasattr(task_mgmt, 'issue_language'):
        lang_names = {
            "tr": "Turkish",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "en": "English",
        }
        language = lang_names.get(task_mgmt.issue_language, task_mgmt.issue_language or "English")

    # Get custom prompts from integration
    title_prompt = ""
    desc_prompt = ""
    if task_mgmt and hasattr(task_mgmt, 'get_prompt'):
        title_prompt = task_mgmt.get_prompt("issue_title") or ""
        desc_prompt = task_mgmt.get_prompt("issue_description") or ""

    # Build combined prompt
    prompt = f"""Analyze these code changes and generate commit message and issue content.

## Files Changed
{file_list}

## Code Diff
```diff
{diffs}
```

## Initial Analysis
- Title: {initial_title}
- Body: {initial_body}

## TASK 1: Generate Commit Message (in English)
Generate:
- **commit_title**: A concise conventional commit message (feat/fix/refactor/chore)
- **commit_body**: Bullet points describing what changed

## TASK 2: Generate Issue Title
{title_prompt if title_prompt else f'Generate a clear issue title in {language}.'}

## TASK 3: Generate Issue Description
{desc_prompt if desc_prompt else f'Generate a detailed issue description in {language}.'}

## Response Format (JSON only)
```json
{{
  "commit_title": "feat: add feature name",
  "commit_body": "- Change 1\\n- Change 2",
  "issue_title": "Issue title in {language}",
  "issue_description": "Detailed description in {language}"
}}
```

Return ONLY the JSON object, no other text.
"""
    return prompt


def _parse_detailed_result(result: str, original_group: Dict) -> Dict:
    """Parse the LLM response and merge with original group."""
    import json

    # Try to extract JSON from response
    try:
        # Find JSON block
        start = result.find("{")
        end = result.rfind("}") + 1
        if start != -1 and end > start:
            json_str = result[start:end]
            data = json.loads(json_str)

            # Merge with original group
            enhanced = original_group.copy()
            if data.get("commit_title"):
                enhanced["commit_title"] = data["commit_title"]
            if data.get("commit_body"):
                enhanced["commit_body"] = data["commit_body"]
            if data.get("issue_title"):
                enhanced["issue_title"] = data["issue_title"]
            if data.get("issue_description"):
                enhanced["issue_description"] = data["issue_description"]

            return enhanced
    except (json.JSONDecodeError, Exception):
        pass

    return original_group