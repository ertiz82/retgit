"""
Config command - View and modify RedGit configuration.

Usage:
    rg config                  : Show entire config
    rg config plugins          : Show plugins section
    rg config notifications    : Show notification settings
    rg config get <path>       : Get a specific value
    rg config set <path> <val> : Set a specific value
    rg config edit             : Open config in editor
"""

import typer
from typing import Optional
from rich.console import Console
from rich.syntax import Syntax
from rich.tree import Tree
from rich.panel import Panel
import yaml
import os

from ..core.config import ConfigManager, CONFIG_PATH, DEFAULT_NOTIFICATIONS, DEFAULT_QUALITY

console = Console()
config_app = typer.Typer(help="View and modify configuration")


def _render_value(value, indent: int = 0) -> str:
    """Render a value for display."""
    if isinstance(value, dict):
        return yaml.dump(value, default_flow_style=False, allow_unicode=True)
    elif isinstance(value, list):
        return yaml.dump(value, default_flow_style=False, allow_unicode=True)
    elif isinstance(value, bool):
        return "[green]true[/green]" if value else "[red]false[/red]"
    elif value is None:
        return "[dim]null[/dim]"
    else:
        return str(value)


def _build_tree(data: dict, tree: Tree, prefix: str = ""):
    """Recursively build a rich tree from dict."""
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            branch = tree.add(f"[cyan]{key}[/cyan]")
            _build_tree(value, branch, path)
        elif isinstance(value, list):
            branch = tree.add(f"[cyan]{key}[/cyan] [dim]({len(value)} items)[/dim]")
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    item_branch = branch.add(f"[dim][{i}][/dim]")
                    _build_tree(item, item_branch, f"{path}[{i}]")
                else:
                    branch.add(f"[dim][{i}][/dim] {item}")
        elif isinstance(value, bool):
            color = "green" if value else "red"
            tree.add(f"[cyan]{key}[/cyan]: [{color}]{value}[/{color}]")
        elif value is None:
            tree.add(f"[cyan]{key}[/cyan]: [dim]null[/dim]")
        else:
            tree.add(f"[cyan]{key}[/cyan]: {value}")


@config_app.callback(invoke_without_command=True)
def config_cmd(ctx: typer.Context):
    """View configuration. Use subcommands for specific operations."""
    # If a subcommand was invoked, skip
    if ctx.invoked_subcommand is not None:
        return

    # Show entire config
    config_manager = ConfigManager()
    config = config_manager.load()

    console.print("\n[bold cyan]RedGit Configuration[/bold cyan]")
    console.print(f"[dim]File: {CONFIG_PATH}[/dim]\n")

    tree = Tree("[bold]config[/bold]")
    _build_tree(config, tree)
    console.print(tree)

    console.print(f"\n[dim]Use 'rg config show <section>' to view a specific section[/dim]")
    console.print(f"[dim]Use 'rg config set <path> <value>' to modify[/dim]")
    console.print(f"[dim]Use 'rg config quality --enable' to enable quality checks[/dim]")


@config_app.command("show")
def show_cmd(
    section: str = typer.Argument(..., help="Config section to view (e.g., plugins, integrations, notifications, quality)")
):
    """Show a specific config section."""
    config_manager = ConfigManager()

    # Show specific section
    data = config_manager.get_section(section)
    if not data:
        console.print(f"[yellow]Section '{section}' not found or empty.[/yellow]")
        console.print(f"\n[dim]Available sections: {', '.join(config_manager.list_keys())}[/dim]")
        return

    console.print(f"\n[bold cyan]Config: {section}[/bold cyan]\n")

    # Special handling for notifications - show with defaults
    if section == "notifications":
        data = config_manager.get_notifications_config()
    elif section == "quality":
        data = config_manager.get_quality_config()

    tree = Tree(f"[bold]{section}[/bold]")
    _build_tree(data, tree)
    console.print(tree)


@config_app.command("get")
def get_cmd(
    path: str = typer.Argument(..., help="Dot-notation path (e.g., integrations.scout.enabled)")
):
    """Get a specific config value."""
    config_manager = ConfigManager()
    value = config_manager.get_value(path)

    if value is None:
        console.print(f"[yellow]'{path}' not found[/yellow]")
        raise typer.Exit(1)

    console.print(f"[cyan]{path}[/cyan] = {_render_value(value)}")


@config_app.command("set")
def set_cmd(
    path: str = typer.Argument(..., help="Dot-notation path (e.g., notifications.events.push)"),
    value: str = typer.Argument(..., help="Value to set (supports: true/false, numbers, strings)")
):
    """Set a specific config value."""
    config_manager = ConfigManager()

    # Get old value for display
    old_value = config_manager.get_value(path)

    # Set new value
    config_manager.set_value(path, value)

    # Get parsed value for display
    new_value = config_manager.get_value(path)

    if old_value is not None:
        console.print(f"[cyan]{path}[/cyan]: {_render_value(old_value)} → {_render_value(new_value)}")
    else:
        console.print(f"[cyan]{path}[/cyan] = {_render_value(new_value)} [dim](created)[/dim]")


@config_app.command("unset")
def unset_cmd(
    path: str = typer.Argument(..., help="Dot-notation path to remove")
):
    """Remove a config value."""
    config_manager = ConfigManager()
    config = config_manager.load()

    keys = path.split(".")
    current = config

    # Navigate to parent
    for key in keys[:-1]:
        if key not in current:
            console.print(f"[yellow]'{path}' not found[/yellow]")
            raise typer.Exit(1)
        current = current[key]

    # Remove key
    final_key = keys[-1]
    if final_key in current:
        del current[final_key]
        config_manager.save(config)
        console.print(f"[green]Removed '{path}'[/green]")
    else:
        console.print(f"[yellow]'{path}' not found[/yellow]")
        raise typer.Exit(1)


@config_app.command("edit")
def edit_cmd():
    """Open config file in editor."""
    config_manager = ConfigManager()
    config = config_manager.load()  # Ensure file exists

    # Get editor from config or environment
    editor_config = config.get("editor", {})
    editor_cmd = editor_config.get("command", [])

    if not editor_cmd:
        # Try environment
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
        if editor:
            editor_cmd = [editor]
        else:
            # Default editors
            for default in ["code", "vim", "nano", "vi"]:
                if os.system(f"which {default} > /dev/null 2>&1") == 0:
                    editor_cmd = [default]
                    break

    if not editor_cmd:
        console.print("[red]No editor found. Set EDITOR environment variable.[/red]")
        raise typer.Exit(1)

    # Open editor
    import subprocess
    cmd = editor_cmd if isinstance(editor_cmd, list) else [editor_cmd]
    cmd.append(str(CONFIG_PATH))

    console.print(f"[dim]Opening {CONFIG_PATH}...[/dim]")
    subprocess.run(cmd)


@config_app.command("list")
def list_cmd(
    section: Optional[str] = typer.Argument(None, help="Section to list keys from")
):
    """List available config keys."""
    config_manager = ConfigManager()
    keys = config_manager.list_keys(section)

    if section:
        console.print(f"\n[bold cyan]Keys in '{section}':[/bold cyan]\n")
    else:
        console.print("\n[bold cyan]Top-level config keys:[/bold cyan]\n")

    if keys:
        for key in keys:
            console.print(f"  [cyan]•[/cyan] {key}")
    else:
        console.print("  [dim]No keys found[/dim]")


@config_app.command("notifications")
def notifications_cmd():
    """Show notification settings with all options."""
    config_manager = ConfigManager()
    notifications = config_manager.get_notifications_config()

    console.print("\n[bold cyan]Notification Settings[/bold cyan]\n")

    # Master switch
    enabled = notifications.get("enabled", True)
    status = "[green]enabled[/green]" if enabled else "[red]disabled[/red]"
    console.print(f"   Master switch: {status}")
    console.print(f"   [dim]rg config set notifications.enabled true/false[/dim]\n")

    # Events
    console.print("   [bold]Events:[/bold]\n")
    events = notifications.get("events", {})

    event_descriptions = {
        "push": "Push completed",
        "pr_created": "PR created",
        "issue_completed": "Issue marked as Done",
        "issue_created": "Issue created",
        "commit": "Commit created",
        "session_complete": "Session completed",
        "ci_success": "CI/CD success",
        "ci_failure": "CI/CD failure",
    }

    for event, description in event_descriptions.items():
        is_enabled = events.get(event, True)
        icon = "[green]✓[/green]" if is_enabled else "[red]✗[/red]"
        console.print(f"   {icon} {event:20} {description}")

    console.print(f"\n   [dim]Toggle: rg config set notifications.events.<event> true/false[/dim]")


@config_app.command("reset")
def reset_cmd(
    section: Optional[str] = typer.Argument(None, help="Section to reset (or all if not specified)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Reset config section to defaults."""
    from rich.prompt import Confirm

    if not section:
        if not force and not Confirm.ask("Reset entire config to defaults?", default=False):
            return
        # Can't reset entire config easily, just warn
        console.print("[yellow]Use 'rg init' to reinitialize config.[/yellow]")
        return

    config_manager = ConfigManager()

    # Handle specific sections
    if section == "notifications":
        if not force and not Confirm.ask(f"Reset '{section}' to defaults?", default=True):
            return

        config = config_manager.load()
        config["notifications"] = DEFAULT_NOTIFICATIONS.copy()
        config_manager.save(config)
        console.print(f"[green]Reset '{section}' to defaults[/green]")

    elif section == "workflow":
        from ..core.config import DEFAULT_WORKFLOW
        if not force and not Confirm.ask(f"Reset '{section}' to defaults?", default=True):
            return

        config = config_manager.load()
        config["workflow"] = DEFAULT_WORKFLOW.copy()
        config_manager.save(config)
        console.print(f"[green]Reset '{section}' to defaults[/green]")

    elif section == "quality":
        if not force and not Confirm.ask(f"Reset '{section}' to defaults?", default=True):
            return

        config = config_manager.load()
        config["quality"] = DEFAULT_QUALITY.copy()
        config_manager.save(config)
        console.print(f"[green]Reset '{section}' to defaults[/green]")

    else:
        console.print(f"[yellow]No defaults available for '{section}'[/yellow]")


@config_app.command("path")
def path_cmd():
    """Show config file path."""
    console.print(f"{CONFIG_PATH.absolute()}")


@config_app.command("yaml")
def yaml_cmd(
    section: Optional[str] = typer.Argument(None, help="Section to show as YAML")
):
    """Show config as raw YAML."""
    config_manager = ConfigManager()

    if section:
        data = config_manager.get_section(section)
        if not data:
            console.print(f"[yellow]Section '{section}' not found[/yellow]")
            raise typer.Exit(1)
    else:
        data = config_manager.load()

    yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=False)
    console.print(syntax)


@config_app.command("quality")
def quality_cmd(
    enable: bool = typer.Option(None, "--enable/--disable", help="Enable or disable quality checks"),
    threshold: Optional[int] = typer.Option(None, "--threshold", "-t", help="Set minimum quality score (0-100)"),
    fail_security: bool = typer.Option(None, "--fail-security/--no-fail-security", help="Fail on security issues")
):
    """View or modify code quality settings."""
    config_manager = ConfigManager()

    # If no options provided, show current settings
    if enable is None and threshold is None and fail_security is None:
        quality = config_manager.get_quality_config()

        console.print("\n[bold cyan]Code Quality Settings[/bold cyan]\n")

        # Status
        is_enabled = quality.get("enabled", False)
        status = "[green]enabled[/green]" if is_enabled else "[dim]disabled[/dim]"
        console.print(f"   Status: {status}")

        # Threshold
        console.print(f"   Threshold: {quality.get('threshold', 70)}")

        # Fail on security
        fail_sec = quality.get("fail_on_security", True)
        fail_sec_str = "[green]yes[/green]" if fail_sec else "[red]no[/red]"
        console.print(f"   Fail on security issues: {fail_sec_str}")

        # Prompt file
        console.print(f"   Prompt file: {quality.get('prompt_file', 'quality_prompt.md')}")

        console.print("\n[dim]Commands:[/dim]")
        console.print("   [dim]rg config quality --enable     # Enable quality checks[/dim]")
        console.print("   [dim]rg config quality --disable    # Disable quality checks[/dim]")
        console.print("   [dim]rg config quality --threshold 80  # Set threshold[/dim]")
        console.print("   [dim]rg quality check              # Run quality check manually[/dim]")
        return

    # Apply changes
    changes = []

    if enable is not None:
        config_manager.set_quality_enabled(enable)
        status = "enabled" if enable else "disabled"
        changes.append(f"Quality checks: [{'green' if enable else 'red'}]{status}[/{'green' if enable else 'red'}]")

    if threshold is not None:
        threshold = max(0, min(100, threshold))
        config_manager.set_quality_threshold(threshold)
        changes.append(f"Threshold: {threshold}")

    if fail_security is not None:
        config = config_manager.load()
        if "quality" not in config:
            config["quality"] = DEFAULT_QUALITY.copy()
        config["quality"]["fail_on_security"] = fail_security
        config_manager.save(config)
        changes.append(f"Fail on security: {'yes' if fail_security else 'no'}")

    if changes:
        console.print("\n[bold cyan]Quality Settings Updated[/bold cyan]\n")
        for change in changes:
            console.print(f"   ✓ {change}")