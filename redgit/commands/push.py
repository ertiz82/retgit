"""
Push command - Push branches and complete issues.
"""

from typing import Optional, List
import typer
from rich.console import Console
from rich.prompt import Confirm

from ..core.config import ConfigManager, StateManager
from ..core.gitops import GitOps
from ..integrations.registry import get_task_management, get_code_hosting, get_cicd, get_notification

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
    )
):
    """Push current branch or session branches and complete issues."""

    config_manager = ConfigManager()
    state_manager = StateManager()
    config = config_manager.load()

    # Get session info
    session = state_manager.get_session()
    gitops = GitOps()
    workflow = config.get("workflow", {})
    strategy = workflow.get("strategy", "local-merge")

    # If no session, push current branch
    if not session or not session.get("branches"):
        _push_current_branch(gitops, config, complete, create_pr, issue, tags, trigger_ci, wait_ci)
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
        _push_merge_request_strategy(
            branches, gitops, task_mgmt, code_hosting,
            base_branch, create_pr, complete, config
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
        _push_current_branch(gitops, config, complete=False, create_pr=create_pr, issue_key=issue, push_tags=tags)

        # Complete issues from session
        if complete and task_mgmt and task_mgmt.enabled and issues:
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
    config: dict = None
):
    """Push branches to remote and optionally create PRs."""

    console.print("\n[bold cyan]Pushing branches...[/bold cyan]")

    pushed_issues = []
    pushed_branches = []

    for b in branches:
        branch_name = b.get("branch", "")
        issue_key = b.get("issue_key")

        console.print(f"\n[cyan]• {branch_name}[/cyan]")

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

    # Send push notification for all branches
    if config and pushed_branches:
        _send_push_notification(config, f"{len(pushed_branches)} branches", pushed_issues if pushed_issues else None)

    # Complete issues
    if complete and task_mgmt and task_mgmt.enabled and pushed_issues:
        console.print("\n[bold cyan]Completing issues...[/bold cyan]")
        _complete_issues(pushed_issues, task_mgmt)
        # Send issue completion notification
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
    """Mark issues as Done using status_map from config."""
    for issue_key in issues:
        try:
            # Use "done" status - will try all mapped statuses from config
            if task_mgmt.transition_issue(issue_key, "done"):
                console.print(f"[green]  ✓ {issue_key} → Done[/green]")
            else:
                console.print(f"[yellow]  ⚠️  {issue_key} could not be transitioned[/yellow]")
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
    wait_ci: bool = False
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
                console.print(f"[green]✓ Tags pushed[/green]")
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

    console.print(f"\n[bold cyan]CI/CD Pipeline[/bold cyan]")

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
                console.print(f"[green]Pipeline completed successfully![/green]")
                _send_ci_notification(config, branch, "success", pipeline.url)
                return
            elif status.status in ("failed", "error", "failure"):
                console.print(f"[red]Pipeline failed![/red]")
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