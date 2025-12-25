"""
Push command - Push branches and complete issues.
"""

from typing import Optional, List
import typer
from rich.console import Console
from rich.prompt import Confirm

from ..core.config import ConfigManager, StateManager
from ..core.gitops import GitOps
from ..integrations.registry import get_task_management, get_code_hosting, get_cicd, get_notification, get_code_quality

console = Console()


def push_cmd(
    complete: bool = typer.Option(
        True, "--complete/--no-complete",
        help="Mark issues as Done after push"
    ),
    create_pr: bool = typer.Option(
        False, "--pr",
        help="Create pull/merge requests (requires code_hosting integration)"
    ),
    issue: Optional[str] = typer.Option(
        None, "--issue", "-i",
        help="Issue key to complete after push (e.g., SCRUM-123)"
    ),
    tags: bool = typer.Option(
        True, "--tags/--no-tags",
        help="Push tags along with branches"
    ),
    trigger_ci: bool = typer.Option(
        None, "--ci/--no-ci",
        help="Trigger CI/CD pipeline after push (auto-detects if ci_cd integration active)"
    ),
    wait_ci: bool = typer.Option(
        False, "--wait-ci", "-w",
        help="Wait for CI/CD pipeline to complete"
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Skip quality checks and push anyway"
    ),
    skip_quality: bool = typer.Option(
        False, "--skip-quality",
        help="Skip code quality checks"
    ),
    no_pull: bool = typer.Option(
        False, "--no-pull",
        help="Skip pulling from remote before push"
    )
):
    """Push current branch or session branches and complete issues."""

    config_manager = ConfigManager()
    state_manager = StateManager()
    config = config_manager.load()

    # Run quality check if enabled (unless skipped)
    if not skip_quality and not force:
        quality_passed = _run_quality_check(config_manager, config)
        if not quality_passed:
            console.print("\n[yellow]💡 Use --force to push anyway, or --skip-quality to skip checks[/yellow]")
            raise typer.Exit(1)

    # Get session info
    session = state_manager.get_session()
    gitops = GitOps()
    workflow = config.get("workflow", {})
    strategy = workflow.get("strategy", "local-merge")

    # If no session, push current branch
    if not session or not session.get("branches"):
        _push_current_branch(gitops, config, complete, create_pr, issue, tags, trigger_ci, wait_ci, no_pull, force)
        return

    branches = session.get("branches", [])
    issues = session.get("issues", [])
    base_branch = session.get("base_branch", gitops.original_branch)

    # Get integrations
    task_mgmt = get_task_management(config)
    code_hosting = get_code_hosting(config)

    if strategy == "merge-request":
        # merge-request strategy: branches exist and need to be pushed
        console.print(f"[cyan]📦 Session: {len(branches)} branches, {len(issues)} issues[/cyan]")
        console.print("[dim]Branches will be pushed to remote for PR creation.[/dim]")
        console.print("")

        # Show branches
        for b in branches:
            issue_key = b.get("issue_key", "")
            branch_name = b.get("branch", "")
            if issue_key:
                console.print(f"  • {branch_name} → {issue_key}")
            else:
                console.print(f"  • {branch_name}")

        console.print("")

        # Confirm
        if not Confirm.ask("Push branches to remote?"):
            return

        # Push branches and optionally create PRs
        # In subtask mode, pass subtask_issues for completion instead of branch issues
        subtask_issues = session.get("subtask_issues", [])
        _push_merge_request_strategy(
            branches, gitops, task_mgmt, code_hosting,
            base_branch, create_pr, complete, config, no_pull, force,
            subtask_issues=subtask_issues
        )
    else:
        # local-merge strategy: branches are already merged during propose
        # We just need to push current branch and complete issues
        console.print(f"[cyan]📦 Session: {len(branches)} commits, {len(issues)} issues[/cyan]")
        console.print("[dim]All commits are already merged to current branch.[/dim]")
        console.print("")

        # Show what was committed
        for b in branches:
            issue_key = b.get("issue_key", "")
            branch_name = b.get("branch", "")
            if issue_key:
                console.print(f"  ✓ {branch_name} → {issue_key}")
            else:
                console.print(f"  ✓ {branch_name}")

        console.print("")

        # Confirm
        if not Confirm.ask("Push to remote?"):
            return

        # Push current branch (all commits are already here)
        _push_current_branch(gitops, config, complete=False, create_pr=create_pr, issue_key=issue, push_tags=tags, no_pull=no_pull, force=force)

        # Complete issues from session
        # In subtask mode, only complete subtask issues (not parent task)
        subtask_issues = session.get("subtask_issues", [])
        if complete and task_mgmt and task_mgmt.enabled:
            if subtask_issues:
                # Subtask mode: only transition subtasks, not parent
                console.print("\n[bold cyan]Completing subtask issues...[/bold cyan]")
                _complete_issues(subtask_issues, task_mgmt)
            elif issues:
                # Standard mode: complete all issues
                console.print("\n[bold cyan]Completing issues...[/bold cyan]")
                _complete_issues(issues, task_mgmt)

    # Clear session
    if Confirm.ask("\nClear session?", default=True):
        state_manager.clear_session()
        console.print("[dim]Session cleared.[/dim]")

    console.print("\n[bold green]✅ Push complete![/bold green]")


def _push_merge_request_strategy(
    branches: List[dict],
    gitops: GitOps,
    task_mgmt,
    code_hosting,
    base_branch: str,
    create_pr: bool,
    complete: bool,
    config: dict = None,
    no_pull: bool = False,
    force: bool = False,
    subtask_issues: List[str] = None
):
    """Push branches to remote and optionally create PRs.

    Args:
        subtask_issues: If provided (subtask mode), complete these issues instead of
                       branch issues. This ensures only subtasks are transitioned,
                       not the parent task.
    """

    console.print("\n[bold cyan]Pushing branches...[/bold cyan]")

    pushed_issues = []
    pushed_branches = []
    skipped_branches = []

    for b in branches:
        branch_name = b.get("branch", "")
        issue_key = b.get("issue_key")

        console.print(f"\n[cyan]• {branch_name}[/cyan]")

        # Sync with remote before push (unless skipped)
        if not no_pull and not force:
            # Checkout branch first for sync
            try:
                gitops.repo.git.checkout(branch_name)
            except Exception:
                pass

            success, conflict_files = _sync_with_remote(gitops, branch_name)
            if not success:
                console.print(f"[red]  ⚠️  Conflicts detected in {branch_name}[/red]")
                if conflict_files:
                    for f in conflict_files[:3]:  # Show first 3
                        console.print(f"     [red]•[/red] {f}")
                    if len(conflict_files) > 3:
                        console.print(f"     [dim]... and {len(conflict_files) - 3} more[/dim]")
                skipped_branches.append(branch_name)
                continue

        try:
            # Push to remote
            gitops.repo.git.push("-u", "origin", branch_name)
            console.print(f"[green]  ✓ Pushed to origin/{branch_name}[/green]")
            pushed_branches.append(branch_name)

            # Create PR if requested and code_hosting available
            if create_pr and code_hosting and code_hosting.enabled:
                pr_title = f"{issue_key}: " if issue_key else ""
                pr_title += branch_name.split("/")[-1].replace("-", " ").title()

                pr_url = code_hosting.create_pull_request(
                    title=pr_title,
                    body=f"Refs: {issue_key}" if issue_key else "",
                    head_branch=branch_name,
                    base_branch=base_branch
                )
                if pr_url:
                    console.print(f"[green]  ✓ PR created: {pr_url}[/green]")
                    # Send PR notification
                    if config:
                        _send_pr_notification(config, branch_name, pr_url, issue_key)

            if issue_key:
                pushed_issues.append(issue_key)

        except Exception as e:
            console.print(f"[red]  ❌ Error: {e}[/red]")

    # Show skipped branches summary
    if skipped_branches:
        console.print(f"\n[yellow]⚠️  {len(skipped_branches)} branch(es) skipped due to conflicts[/yellow]")
        console.print("[dim]   Resolve conflicts and push manually, or use --no-pull[/dim]")

    # Send push notification for all branches
    if config and pushed_branches:
        _send_push_notification(config, f"{len(pushed_branches)} branches", pushed_issues if pushed_issues else None)

    # Complete issues
    # In subtask mode, complete subtask_issues instead of pushed branch issues
    if complete and task_mgmt and task_mgmt.enabled:
        if subtask_issues and pushed_branches:
            # Subtask mode: complete subtask issues (not parent task)
            console.print("\n[bold cyan]Completing subtask issues...[/bold cyan]")
            _complete_issues(subtask_issues, task_mgmt)
            if config:
                _send_issue_completion_notification(config, subtask_issues)
        elif pushed_issues:
            # Standard mode: complete branch issues
            console.print("\n[bold cyan]Completing issues...[/bold cyan]")
            _complete_issues(pushed_issues, task_mgmt)
            if config:
                _send_issue_completion_notification(config, pushed_issues)


def _push_local_merge_strategy(
    branches: List[dict],
    gitops: GitOps,
    task_mgmt,
    base_branch: str,
    complete: bool
):
    """Merge branches locally and push base branch."""

    console.print("\n[bold cyan]Merging branches locally...[/bold cyan]")

    merged_issues = []

    # Checkout base branch
    try:
        gitops.repo.git.checkout(base_branch)
        console.print(f"[dim]Switched to {base_branch}[/dim]")
    except Exception as e:
        console.print(f"[red]❌ Failed to checkout {base_branch}: {e}[/red]")
        return

    for b in branches:
        branch_name = b.get("branch", "")
        issue_key = b.get("issue_key")

        console.print(f"\n[cyan]• Merging {branch_name}[/cyan]")

        try:
            # Merge branch
            gitops.repo.git.merge(branch_name, "--no-ff", "-m", f"Merge branch '{branch_name}'")
            console.print(f"[green]  ✓ Merged into {base_branch}[/green]")

            # Delete local branch
            try:
                gitops.repo.git.branch("-d", branch_name)
                console.print(f"[dim]  Deleted local branch {branch_name}[/dim]")
            except Exception:
                pass

            if issue_key:
                merged_issues.append(issue_key)

        except Exception as e:
            console.print(f"[red]  ❌ Merge failed: {e}[/red]")
            console.print("[yellow]  Skipping this branch. Resolve conflicts manually.[/yellow]")

    # Push base branch
    console.print(f"\n[cyan]Pushing {base_branch}...[/cyan]")
    try:
        gitops.repo.git.push("origin", base_branch)
        console.print(f"[green]✓ Pushed {base_branch}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Push failed: {e}[/red]")

    # Complete issues
    if complete and task_mgmt and task_mgmt.enabled and merged_issues:
        console.print("\n[bold cyan]Completing issues...[/bold cyan]")
        _complete_issues(merged_issues, task_mgmt)


def _complete_issues(issues: List[str], task_mgmt):
    """Mark issues as completed using after_push status mapping from config.

    If transition_strategy is 'ask', prompts user to select target status.
    If transition_strategy is 'auto', uses status mapping and auto-advances if needed.
    """
    # Check transition strategy
    strategy = getattr(task_mgmt, 'transition_strategy', 'auto')

    if strategy == 'ask':
        _complete_issues_interactive(issues, task_mgmt)
    else:
        _complete_issues_auto(issues, task_mgmt)


def _complete_issues_auto(issues: List[str], task_mgmt):
    """Auto-transition issues using status mapping.

    If configured statuses are not available, asks user to select from
    available transitions and saves the selection to config for future use.
    """
    from rich.prompt import Prompt

    # Track if we already prompted and saved a new status
    saved_status_for_all = None

    for issue_key in issues:
        try:
            # Get current status before transition
            issue = task_mgmt.get_issue(issue_key)
            old_status = issue.status if issue else "Unknown"

            # If we already found a working status for previous issue, try it first
            if saved_status_for_all:
                transitions = task_mgmt.get_available_transitions(issue_key)
                matching = [t for t in transitions if t["to"].lower() == saved_status_for_all.lower()]
                if matching:
                    if task_mgmt.transition_issue_by_id(issue_key, matching[0]["id"]):
                        console.print(f"[green]  ✓ {issue_key}: {old_status} → {saved_status_for_all}[/green]")
                        continue

            # Use "after_push" status - will try all mapped statuses, then auto-advance
            if task_mgmt.transition_issue(issue_key, "after_push"):
                # Get new status after transition
                issue = task_mgmt.get_issue(issue_key)
                new_status = issue.status if issue else "Done"
                console.print(f"[green]  ✓ {issue_key}: {old_status} → {new_status}[/green]")
            else:
                # Transition failed - ask user to select from available transitions
                transitions = task_mgmt.get_available_transitions(issue_key)

                if not transitions:
                    console.print(f"[yellow]  ⚠️  {issue_key}: No available transitions[/yellow]")
                    continue

                console.print(f"\n[yellow]  ⚠️  {issue_key}: Configured status not available[/yellow]")
                console.print(f"  [dim]Current: {old_status}[/dim]")
                console.print("  [bold]Available transitions:[/bold]")

                for i, t in enumerate(transitions, 1):
                    console.print(f"    [{i}] {t['to']}")
                console.print(f"    [0] Skip (don't transition)")

                choice = Prompt.ask(
                    "  Select transition",
                    default="0"
                )

                if choice == "0":
                    console.print(f"[dim]  - {issue_key}: Skipped[/dim]")
                    continue

                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(transitions):
                        selected = transitions[idx]
                        if task_mgmt.transition_issue_by_id(issue_key, selected["id"]):
                            console.print(f"[green]  ✓ {issue_key}: {old_status} → {selected['to']}[/green]")

                            # Offer to save to config
                            if Confirm.ask(f"  Add '{selected['to']}' to after_push config?", default=True):
                                _save_status_to_config(selected['to'])
                                saved_status_for_all = selected['to']
                                console.print(f"[dim]  Saved '{selected['to']}' to config[/dim]")
                        else:
                            console.print(f"[red]  ❌ {issue_key}: Transition failed[/red]")
                    else:
                        console.print(f"[yellow]  Invalid choice, skipping {issue_key}[/yellow]")
                except ValueError:
                    console.print(f"[yellow]  Invalid choice, skipping {issue_key}[/yellow]")

        except Exception as e:
            console.print(f"[red]  ❌ {issue_key} error: {e}[/red]")


def _save_status_to_config(status_name: str):
    """Save a new status to after_push config."""
    import yaml
    from pathlib import Path

    config_path = Path(".redgit/config.yaml")
    if not config_path.exists():
        return

    try:
        config = yaml.safe_load(config_path.read_text()) or {}

        # Ensure structure exists
        if "integrations" not in config:
            config["integrations"] = {}
        if "jira" not in config["integrations"]:
            config["integrations"]["jira"] = {}
        if "statuses" not in config["integrations"]["jira"]:
            config["integrations"]["jira"]["statuses"] = {}
        if "after_push" not in config["integrations"]["jira"]["statuses"]:
            config["integrations"]["jira"]["statuses"]["after_push"] = []

        # Add new status if not already present
        after_push = config["integrations"]["jira"]["statuses"]["after_push"]
        if isinstance(after_push, list):
            if status_name not in after_push:
                after_push.append(status_name)
        elif isinstance(after_push, str):
            if after_push != status_name:
                config["integrations"]["jira"]["statuses"]["after_push"] = [after_push, status_name]

        # Write back
        config_path.write_text(yaml.dump(config, allow_unicode=True, sort_keys=False))

    except Exception:
        pass


def _complete_issues_interactive(issues: List[str], task_mgmt):
    """Interactively ask user to select target status for each issue."""
    from rich.prompt import Prompt

    # Track user's choice for "apply to all"
    apply_to_all_choice = None

    for issue_key in issues:
        try:
            # Get current issue info
            issue = task_mgmt.get_issue(issue_key)
            old_status = issue.status if issue else "Unknown"
            summary = issue.summary[:50] + "..." if issue and len(issue.summary) > 50 else (issue.summary if issue else "")

            # Get available transitions
            transitions = task_mgmt.get_available_transitions(issue_key)

            if not transitions:
                console.print(f"[yellow]  ⚠️  {issue_key} has no available transitions[/yellow]")
                continue

            # If user chose "apply to all" previously
            if apply_to_all_choice is not None:
                if apply_to_all_choice == "skip":
                    console.print(f"[dim]  - {issue_key}: Skipped (apply to all)[/dim]")
                    continue
                else:
                    # Try to find the same transition
                    matching = [t for t in transitions if t["to"] == apply_to_all_choice]
                    if matching:
                        if task_mgmt.transition_issue_by_id(issue_key, matching[0]["id"]):
                            console.print(f"[green]  ✓ {issue_key}: {old_status} → {apply_to_all_choice}[/green]")
                        else:
                            console.print(f"[yellow]  ⚠️  {issue_key} could not be transitioned[/yellow]")
                        continue
                    else:
                        # Target status not available for this issue, ask again
                        console.print(f"[dim]  Note: '{apply_to_all_choice}' not available for {issue_key}[/dim]")
                        apply_to_all_choice = None

            # Show issue info
            console.print(f"\n[cyan]  {issue_key}[/cyan] [dim]({old_status})[/dim]")
            if summary:
                console.print(f"  [dim]{summary}[/dim]")

            # Show options
            console.print("  [bold]Available transitions:[/bold]")
            for i, t in enumerate(transitions, 1):
                console.print(f"    [{i}] {t['to']}")
            console.print(f"    [0] Skip (don't change)")
            console.print(f"    [a] Apply to all remaining issues")

            # Get user choice
            while True:
                choice = Prompt.ask("  Select", default="1")

                if choice.lower() == "a":
                    # Apply to all - ask which status
                    console.print("  [dim]Apply which status to all remaining issues?[/dim]")
                    for i, t in enumerate(transitions, 1):
                        console.print(f"    [{i}] {t['to']}")
                    console.print(f"    [0] Skip all")

                    all_choice = Prompt.ask("  Select for all", default="1")
                    if all_choice == "0":
                        apply_to_all_choice = "skip"
                        console.print(f"[dim]  - {issue_key}: Skipped[/dim]")
                        break
                    elif all_choice.isdigit() and 1 <= int(all_choice) <= len(transitions):
                        idx = int(all_choice) - 1
                        apply_to_all_choice = transitions[idx]["to"]
                        if task_mgmt.transition_issue_by_id(issue_key, transitions[idx]["id"]):
                            console.print(f"[green]  ✓ {issue_key}: {old_status} → {apply_to_all_choice}[/green]")
                        else:
                            console.print(f"[yellow]  ⚠️  {issue_key} could not be transitioned[/yellow]")
                        break
                    else:
                        console.print("[red]  Invalid choice[/red]")
                        continue

                elif choice == "0":
                    console.print(f"[dim]  - {issue_key}: Skipped[/dim]")
                    break

                elif choice.isdigit() and 1 <= int(choice) <= len(transitions):
                    idx = int(choice) - 1
                    target_status = transitions[idx]["to"]
                    transition_id = transitions[idx]["id"]

                    if task_mgmt.transition_issue_by_id(issue_key, transition_id):
                        console.print(f"[green]  ✓ {issue_key}: {old_status} → {target_status}[/green]")
                    else:
                        console.print(f"[yellow]  ⚠️  {issue_key} could not be transitioned[/yellow]")
                    break

                else:
                    console.print("[red]  Invalid choice[/red]")

        except Exception as e:
            console.print(f"[red]  ❌ {issue_key} error: {e}[/red]")


def _push_current_branch(
    gitops: GitOps,
    config: dict,
    complete: bool,
    create_pr: bool,
    issue_key: Optional[str],
    push_tags: bool = True,
    trigger_ci: Optional[bool] = None,
    wait_ci: bool = False,
    no_pull: bool = False,
    force: bool = False
):
    """Push current branch without session."""

    current_branch = gitops.original_branch

    # Check if there are commits to push
    try:
        status = gitops.repo.git.status()
        if "Your branch is ahead" not in status and "have diverged" not in status:
            # Check for unpushed commits
            try:
                ahead = gitops.repo.git.rev_list("--count", f"origin/{current_branch}..HEAD")
                if int(ahead) == 0:
                    # Check for unpushed tags
                    if push_tags:
                        unpushed_tags = _get_unpushed_tags(gitops)
                        if not unpushed_tags:
                            console.print("[yellow]⚠️  No commits or tags to push.[/yellow]")
                            return
                    else:
                        console.print("[yellow]⚠️  No commits to push.[/yellow]")
                        return
            except Exception:
                pass  # Remote might not exist
    except Exception:
        pass

    console.print(f"[cyan]📤 Pushing current branch: {current_branch}[/cyan]")

    # Sync with remote before push (unless skipped)
    if not no_pull and not force:
        success, conflict_files = _sync_with_remote(gitops, current_branch)
        if not success:
            _display_conflict_error(conflict_files, current_branch)
            raise typer.Exit(1)

    # Try to extract issue key from branch name if not provided
    if not issue_key:
        issue_key = _extract_issue_from_branch(current_branch, config)
        if issue_key:
            console.print(f"[dim]Detected issue: {issue_key}[/dim]")

    # Push using os.system for full shell/SSH agent access
    import os
    console.print("[dim]Running git push...[/dim]")
    exit_code = os.system(f"git push -u origin {current_branch}")
    if exit_code == 0:
        console.print(f"[green]✓ Pushed to origin/{current_branch}[/green]")
        # Send push notification
        _send_push_notification(config, current_branch, [issue_key] if issue_key else None)
    else:
        console.print(f"[red]❌ Push failed (exit code {exit_code})[/red]")
        return

    # Push tags if enabled
    if push_tags:
        unpushed_tags = _get_unpushed_tags(gitops)
        if unpushed_tags:
            console.print(f"\n[cyan]🏷️  Pushing {len(unpushed_tags)} tag(s)...[/cyan]")
            for tag in unpushed_tags:
                console.print(f"  [dim]• {tag}[/dim]")

            exit_code = os.system("git push --tags")
            if exit_code == 0:
                console.print("[green]✓ Tags pushed[/green]")
            else:
                console.print(f"[yellow]⚠️  Tag push failed (exit code {exit_code})[/yellow]")

    # Get integrations
    task_mgmt = get_task_management(config)
    code_hosting = get_code_hosting(config)

    # Create PR if requested
    if create_pr and code_hosting and code_hosting.enabled:
        base_branch = code_hosting.get_default_branch()
        pr_title = f"{issue_key}: " if issue_key else ""
        pr_title += current_branch.split("/")[-1].replace("-", " ").title()

        pr_url = code_hosting.create_pull_request(
            title=pr_title,
            body=f"Refs: {issue_key}" if issue_key else "",
            head_branch=current_branch,
            base_branch=base_branch
        )
        if pr_url:
            console.print(f"[green]✓ PR created: {pr_url}[/green]")
            # Send PR notification
            _send_pr_notification(config, current_branch, pr_url, issue_key)

    # Complete issue
    if complete and issue_key and task_mgmt and task_mgmt.enabled:
        if Confirm.ask(f"Mark {issue_key} as completed?", default=True):
            _complete_issues([issue_key], task_mgmt)
            # Send issue completion notification
            _send_issue_completion_notification(config, [issue_key])

    # CI/CD integration
    cicd = get_cicd(config)
    should_trigger_ci = trigger_ci if trigger_ci is not None else (cicd and cicd.enabled)

    if should_trigger_ci and cicd and cicd.enabled:
        _trigger_cicd_pipeline(cicd, config, current_branch, wait_ci)

    console.print("\n[bold green]✅ Push complete![/bold green]")


def _get_unpushed_tags(gitops: GitOps) -> List[str]:
    """Get list of local tags not yet pushed to remote."""
    try:
        # Get all local tags
        local_tags = set(gitops.repo.git.tag().split("\n"))
        local_tags.discard("")

        if not local_tags:
            return []

        # Get remote tags
        try:
            remote_tags_output = gitops.repo.git.ls_remote("--tags", "origin")
            remote_tags = set()
            for line in remote_tags_output.split("\n"):
                if line and "refs/tags/" in line:
                    tag = line.split("refs/tags/")[-1].replace("^{}", "")
                    remote_tags.add(tag)
        except Exception:
            # No remote or error - assume all tags are unpushed
            return list(local_tags)

        # Return tags that exist locally but not on remote
        unpushed = local_tags - remote_tags
        return sorted(list(unpushed))

    except Exception:
        return []


def _extract_issue_from_branch(branch_name: str, config: dict) -> Optional[str]:
    """Try to extract issue key from branch name."""
    import re

    # Get project key from task management config
    task_mgmt_name = config.get("active", {}).get("task_management")
    if not task_mgmt_name:
        return None

    integration_config = config.get("integrations", {}).get(task_mgmt_name, {})
    project_key = integration_config.get("project_key", "")

    if not project_key:
        return None

    # Look for pattern like PROJ-123 in branch name
    pattern = rf"({re.escape(project_key)}-\d+)"
    match = re.search(pattern, branch_name, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    return None


def _trigger_cicd_pipeline(cicd, config: dict, branch: str, wait: bool = False):
    """Trigger CI/CD pipeline and optionally wait for completion."""
    import time

    console.print("\n[bold cyan]CI/CD Pipeline[/bold cyan]")

    try:
        # Trigger the pipeline
        console.print(f"[dim]Triggering pipeline for {branch}...[/dim]")
        pipeline = cicd.trigger_pipeline(branch=branch)

        if not pipeline:
            console.print("[yellow]Could not trigger pipeline (may already be running)[/yellow]")
            return

        console.print(f"[green]Pipeline triggered: {pipeline.name}[/green]")
        if pipeline.url:
            console.print(f"[dim]URL: {pipeline.url}[/dim]")

        if not wait:
            return

        # Wait for pipeline completion
        console.print("\n[dim]Waiting for pipeline to complete...[/dim]")
        max_wait = 600  # 10 minutes
        poll_interval = 10  # seconds
        elapsed = 0

        while elapsed < max_wait:
            status = cicd.get_pipeline_status(pipeline.name)
            if not status:
                console.print("[yellow]Could not get pipeline status[/yellow]")
                break

            if status.status in ("success", "passed"):
                console.print("[green]Pipeline completed successfully![/green]")
                _send_ci_notification(config, branch, "success", pipeline.url)
                return
            elif status.status in ("failed", "error", "failure"):
                console.print("[red]Pipeline failed![/red]")
                _send_ci_notification(config, branch, "failed", pipeline.url)
                return
            elif status.status in ("cancelled", "canceled", "skipped"):
                console.print(f"[yellow]Pipeline {status.status}[/yellow]")
                return

            # Still running
            elapsed += poll_interval
            remaining = max_wait - elapsed
            console.print(f"[dim]Status: {status.status} ({remaining}s remaining)[/dim]", end="\r")
            time.sleep(poll_interval)

        console.print(f"\n[yellow]Timeout waiting for pipeline (still {status.status if status else 'unknown'})[/yellow]")

    except Exception as e:
        console.print(f"[red]CI/CD error: {e}[/red]")


def _is_notification_enabled(config: dict, event: str) -> bool:
    """Check if notification is enabled for a specific event."""
    from ..core.config import ConfigManager
    config_manager = ConfigManager()
    return config_manager.is_notification_enabled(event)


def _send_ci_notification(config: dict, branch: str, status: str, url: Optional[str] = None):
    """Send notification about CI/CD pipeline result."""
    # Check event-specific setting
    event = "ci_success" if status == "success" else "ci_failure"
    if not _is_notification_enabled(config, event):
        return

    notification = get_notification(config)
    if not notification or not notification.enabled:
        return

    try:
        if status == "success":
            message = f"✅ Pipeline for `{branch}` completed successfully"
        else:
            message = f"❌ Pipeline for `{branch}` failed"

        if url:
            message += f"\n{url}"

        notification.send_message(message)
    except Exception:
        pass  # Notification failure shouldn't break the flow


def _send_push_notification(config: dict, branch: str, issues: List[str] = None):
    """Send notification about successful push."""
    if not _is_notification_enabled(config, "push"):
        return

    notification = get_notification(config)
    if not notification or not notification.enabled:
        return

    try:
        message = f"📤 Pushed `{branch}` to remote"
        if issues:
            message += f"\nIssues: {', '.join(issues)}"
        notification.send_message(message)
    except Exception:
        pass


def _send_pr_notification(config: dict, branch: str, pr_url: str, issue_key: str = None):
    """Send notification about PR creation."""
    if not _is_notification_enabled(config, "pr_created"):
        return

    notification = get_notification(config)
    if not notification or not notification.enabled:
        return

    try:
        message = f"🔀 PR created for `{branch}`"
        if issue_key:
            message += f" ({issue_key})"
        message += f"\n{pr_url}"
        notification.send_message(message)
    except Exception:
        pass


def _send_issue_completion_notification(config: dict, issues: List[str]):
    """Send notification about issues marked as done."""
    if not _is_notification_enabled(config, "issue_completed"):
        return

    notification = get_notification(config)
    if not notification or not notification.enabled:
        return

    try:
        if len(issues) == 1:
            message = f"✅ Issue {issues[0]} marked as Done"
        else:
            message = f"✅ {len(issues)} issues marked as Done: {', '.join(issues)}"
        notification.send_message(message)
    except Exception:
        pass


def _run_quality_check(config_manager: ConfigManager, config: dict) -> bool:
    """
    Run code quality check before push.

    Returns:
        True if quality check passed or disabled, False if failed
    """
    # Check if quality checks are enabled
    if not config_manager.is_quality_enabled():
        return True

    threshold = config_manager.get_quality_threshold()
    quality_config = config_manager.get_quality_config()
    fail_on_security = quality_config.get("fail_on_security", True)

    console.print("[bold cyan]🔍 Running code quality check...[/bold cyan]")

    try:
        # Try using code quality integration first
        quality_integration = get_code_quality(config)

        if quality_integration:
            console.print(f"[dim]Using {quality_integration.name} integration[/dim]")
            status = quality_integration.get_quality_status()

            if status:
                # Determine if passed based on integration status
                passed = status.status in ("passed", "success")
                score = int(status.coverage or 70) if hasattr(status, 'coverage') and status.coverage else 70

                if passed:
                    console.print(f"[green]✓ Quality check passed (score: {score})[/green]")
                    return True
                else:
                    console.print(f"[red]✗ Quality check failed: {status.quality_gate_status or status.status}[/red]")
                    _send_quality_failed_notification(config, score, threshold)
                    return False
        else:
            # Use AI analysis
            from .quality import analyze_quality, _display_result

            result = analyze_quality(verbose=False)
            score = result.get("score", 0)
            decision = result.get("decision", "reject")
            issues = result.get("issues", [])

            # Check for critical security issues
            if fail_on_security:
                security_issues = [
                    i for i in issues
                    if i.get("severity", "").lower() in ("critical", "high")
                    and i.get("type", "").lower() == "security"
                ]
                if security_issues:
                    console.print("[red]✗ Critical security issues found![/red]")
                    _display_result(result, threshold)
                    _send_quality_failed_notification(config, score, threshold)
                    return False

            # Check threshold
            if score >= threshold and decision == "approve":
                console.print(f"[green]✓ Quality check passed (score: {score}/{threshold})[/green]")
                return True
            else:
                console.print(f"[red]✗ Quality check failed (score: {score}/{threshold})[/red]")
                _display_result(result, threshold)
                _send_quality_failed_notification(config, score, threshold)
                return False

    except FileNotFoundError as e:
        # LLM not configured - skip quality check with warning
        console.print(f"[yellow]⚠️  Quality check skipped: {e}[/yellow]")
        return True
    except Exception as e:
        # Other errors - skip quality check with warning
        console.print(f"[yellow]⚠️  Quality check error: {e}[/yellow]")
        return True

    return True


def _send_quality_failed_notification(config: dict, score: int, threshold: int):
    """Send notification about failed quality check."""
    if not _is_notification_enabled(config, "quality_failed"):
        return

    notification = get_notification(config)
    if not notification or not notification.enabled:
        return

    try:
        message = f"⚠️ Code quality check failed\nScore: {score}/{threshold}"
        notification.send_message(message)
    except Exception:
        pass


def _sync_with_remote(gitops: GitOps, branch: str) -> tuple:
    """
    Sync with remote and check for conflicts.

    Returns:
        (success: bool, conflict_files: list)
        - success=True: Pull successful or not needed
        - success=False: Conflict detected, conflict_files list returned
    """
    import git

    # 1. Check if remote branch exists
    try:
        result = gitops.repo.git.ls_remote("--heads", "origin", branch)
        if not result.strip():
            # Remote branch doesn't exist, continue with push
            return True, []
    except Exception:
        # No remote or error, continue with push
        return True, []

    # 2. Fetch from remote
    console.print("[dim]🔄 Syncing with remote...[/dim]")
    try:
        gitops.repo.git.fetch("origin", branch)
    except Exception as e:
        console.print(f"[yellow]   ⚠️  Could not fetch from remote: {e}[/yellow]")
        return True, []  # Continue anyway

    # 3. Check if we're behind
    try:
        behind = gitops.repo.git.rev_list("--count", f"HEAD..origin/{branch}")
        behind_count = int(behind.strip()) if behind.strip() else 0
    except Exception:
        behind_count = 0

    if behind_count == 0:
        console.print(f"[green]   ✓ Up to date with origin/{branch}[/green]")
        return True, []

    console.print(f"[dim]   Remote has {behind_count} new commit(s), attempting merge...[/dim]")

    # 4. Try to merge (no commit, to test for conflicts)
    try:
        gitops.repo.git.merge(f"origin/{branch}", "--no-commit", "--no-ff")
        # Merge successful, commit it
        gitops.repo.git.commit("-m", f"Merge remote-tracking branch 'origin/{branch}'")
        console.print(f"[green]   ✓ Merged {behind_count} commit(s) from remote[/green]")
        return True, []
    except git.GitCommandError:
        # 5. Conflict detected - get conflict files
        conflict_files = []
        try:
            status = gitops.repo.git.status("--porcelain")
            for line in status.split("\n"):
                if line:
                    # UU = both modified, AA = both added, DD = both deleted
                    # DU = deleted by us, UD = deleted by them
                    # AU = added by us, UA = added by them
                    prefix = line[:2]
                    if "U" in prefix or prefix == "AA" or prefix == "DD":
                        conflict_files.append(line[3:].strip())
        except Exception:
            pass

        # 6. Abort merge to restore clean state
        try:
            gitops.repo.git.merge("--abort")
        except Exception:
            try:
                gitops.repo.git.reset("--hard", "HEAD")
            except Exception:
                pass

        return False, conflict_files


def _display_conflict_error(conflict_files: List[str], branch: str):
    """Display conflict error message with helpful options."""
    console.print("\n[red bold]⚠️  Conflicts detected![/red bold]")
    console.print("")

    if conflict_files:
        console.print("[bold]   Conflicting files:[/bold]")
        for f in conflict_files:
            console.print(f"   [red]•[/red] {f}")
        console.print("")

    console.print("[red]❌ Push blocked: Please resolve conflicts first[/red]")
    console.print("")
    console.print("[bold]💡 Options:[/bold]")
    console.print("   1. Resolve conflicts manually:")
    console.print(f"      [dim]git pull origin {branch}[/dim]")
    console.print("      [dim]# Fix conflicts in files[/dim]")
    console.print("      [dim]git add . && git commit[/dim]")
    console.print("   2. Skip sync check: [cyan]rg push --no-pull[/cyan]")
    console.print("   3. Force push (caution!): [cyan]rg push --force[/cyan]")