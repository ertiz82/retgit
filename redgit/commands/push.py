"""
Push command - Push branches and complete issues.
"""

from typing import Optional, List
import typer
from rich.console import Console
from rich.prompt import Confirm

from ..core.config import ConfigManager, StateManager
from ..core.gitops import GitOps
from ..integrations.registry import get_task_management, get_code_hosting

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
    )
):
    """Push current branch or session branches and complete issues."""

    config_manager = ConfigManager()
    state_manager = StateManager()
    config = config_manager.load()
    workflow = config.get("workflow", {})
    strategy = workflow.get("strategy", "local-merge")

    # Get session info
    session = state_manager.get_session()
    gitops = GitOps()

    # If no session, push current branch
    if not session or not session.get("branches"):
        _push_current_branch(gitops, config, complete, create_pr, issue, tags)
        return

    branches = session.get("branches", [])
    issues = session.get("issues", [])
    base_branch = session.get("base_branch", "main")

    if not branches:
        _push_current_branch(gitops, config, complete, create_pr, issue, tags)
        return

    console.print(f"[cyan]📦 Session: {len(branches)} branches, {len(issues)} issues[/cyan]")
    console.print(f"[dim]Base branch: {base_branch}[/dim]")
    console.print(f"[dim]Strategy: {strategy}[/dim]")
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
    if not Confirm.ask("Push all branches?"):
        return

    # Initialize git
    gitops = GitOps()

    # Get integrations
    task_mgmt = get_task_management(config)
    code_hosting = get_code_hosting(config)

    # Process based on strategy
    if strategy == "merge-request":
        _push_merge_request_strategy(
            branches, gitops, task_mgmt, code_hosting,
            base_branch, create_pr, complete
        )
    else:
        _push_local_merge_strategy(
            branches, gitops, task_mgmt,
            base_branch, complete
        )

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
    complete: bool
):
    """Push branches to remote and optionally create PRs."""

    console.print("\n[bold cyan]Pushing branches...[/bold cyan]")

    pushed_issues = []

    for b in branches:
        branch_name = b.get("branch", "")
        issue_key = b.get("issue_key")

        console.print(f"\n[cyan]• {branch_name}[/cyan]")

        try:
            # Push to remote
            gitops.repo.git.push("-u", "origin", branch_name)
            console.print(f"[green]  ✓ Pushed to origin/{branch_name}[/green]")

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

            if issue_key:
                pushed_issues.append(issue_key)

        except Exception as e:
            console.print(f"[red]  ❌ Error: {e}[/red]")

    # Complete issues
    if complete and task_mgmt and task_mgmt.enabled and pushed_issues:
        console.print("\n[bold cyan]Completing issues...[/bold cyan]")
        _complete_issues(pushed_issues, task_mgmt)


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
    """Mark issues as Done."""
    for issue_key in issues:
        try:
            if task_mgmt.transition_issue(issue_key, "Done"):
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
    push_tags: bool = True
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

    # Complete issue
    if complete and issue_key and task_mgmt and task_mgmt.enabled:
        if Confirm.ask(f"Mark {issue_key} as Done?", default=True):
            if task_mgmt.transition_issue(issue_key, "Done"):
                console.print(f"[green]✓ {issue_key} → Done[/green]")
            else:
                console.print(f"[yellow]⚠️  Could not transition {issue_key}[/yellow]")

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