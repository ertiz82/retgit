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

    console.print("\n[dim]Use 'rg config show <section>' to view a specific section[/dim]")
    console.print("[dim]Use 'rg config set <path> <value>' to modify[/dim]")
    console.print("[dim]Use 'rg config quality --enable' to enable quality checks[/dim]")


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
    console.print("   [dim]rg config set notifications.enabled true/false[/dim]\n")

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

    console.print("\n   [dim]Toggle: rg config set notifications.events.<event> true/false[/dim]")


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


def _check_semgrep_installed() -> bool:
    """Check if Semgrep is installed."""
    import subprocess
    try:
        result = subprocess.run(
            ["semgrep", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _install_semgrep() -> bool:
    """Install Semgrep using pip."""
    import subprocess
    console.print("   Installing Semgrep...")
    try:
        subprocess.run(
            ["pip", "install", "semgrep"],
            check=True,
            capture_output=True
        )
        console.print("   [green]✓ Semgrep installed successfully![/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"   [red]✗ Installation failed: {e}[/red]")
        console.print("   Try manually: pip install semgrep")
        return False


@config_app.command("semgrep")
def semgrep_cmd(
    enable: bool = typer.Option(None, "--enable/--disable", help="Enable or disable Semgrep analysis"),
    add_config: Optional[str] = typer.Option(None, "--add", "-a", help="Add a rule config (e.g., p/security-audit)"),
    remove_config: Optional[str] = typer.Option(None, "--remove", "-r", help="Remove a rule config"),
    install: bool = typer.Option(False, "--install", "-i", help="Install Semgrep if not installed"),
    list_rules: bool = typer.Option(False, "--list-rules", "-l", help="Show available rule packs")
):
    """View or modify Semgrep settings."""
    config_manager = ConfigManager()

    # Show available rule packs
    if list_rules:
        console.print("\n[bold cyan]Available Semgrep Rule Packs[/bold cyan]\n")
        console.print("   [cyan]auto[/cyan]              Auto-detect based on project languages")
        console.print("   [cyan]p/security-audit[/cyan]  Security vulnerabilities (all languages)")
        console.print("   [cyan]p/owasp-top-ten[/cyan]   OWASP Top 10 vulnerabilities")
        console.print("   [cyan]p/python[/cyan]          Python best practices")
        console.print("   [cyan]p/javascript[/cyan]      JavaScript/TypeScript rules")
        console.print("   [cyan]p/typescript[/cyan]      TypeScript specific rules")
        console.print("   [cyan]p/golang[/cyan]          Go rules")
        console.print("   [cyan]p/java[/cyan]            Java rules")
        console.print("   [cyan]p/php[/cyan]             PHP rules")
        console.print("   [cyan]p/ruby[/cyan]            Ruby rules")
        console.print("   [cyan]p/rust[/cyan]            Rust rules")
        console.print("   [cyan]p/csharp[/cyan]          C# rules")
        console.print("   [cyan]p/kotlin[/cyan]          Kotlin rules")
        console.print("   [cyan]p/swift[/cyan]           Swift rules")
        console.print("   [cyan]p/scala[/cyan]           Scala rules")
        console.print("   [cyan]p/docker[/cyan]          Dockerfile rules")
        console.print("   [cyan]p/terraform[/cyan]       Terraform/HCL rules")
        console.print("\n   [dim]See more at: https://semgrep.dev/explore[/dim]")
        return

    # Install Semgrep
    if install:
        if _check_semgrep_installed():
            console.print("   [green]✓ Semgrep is already installed[/green]")
        else:
            _install_semgrep()
        return

    # If no options provided, show current settings
    if enable is None and add_config is None and remove_config is None:
        semgrep = config_manager.get_semgrep_config()
        is_installed = _check_semgrep_installed()

        console.print("\n[bold cyan]Semgrep Settings[/bold cyan]\n")

        # Installation status
        install_status = "[green]installed[/green]" if is_installed else "[red]not installed[/red]"
        console.print(f"   Installation: {install_status}")

        # Status
        is_enabled = semgrep.get("enabled", False)
        status = "[green]enabled[/green]" if is_enabled else "[dim]disabled[/dim]"
        console.print(f"   Status: {status}")

        # Configs
        configs = semgrep.get("configs", ["auto"])
        console.print(f"   Rule packs: {', '.join(configs)}")

        # Severity
        severity = semgrep.get("severity", ["ERROR", "WARNING"])
        console.print(f"   Severity: {', '.join(severity)}")

        # Timeout
        console.print(f"   Timeout: {semgrep.get('timeout', 300)}s")

        # Excludes
        excludes = semgrep.get("exclude", [])
        if excludes:
            console.print(f"   Excludes: {', '.join(excludes)}")

        console.print("\n[dim]Commands:[/dim]")
        console.print("   [dim]rg config semgrep --enable       # Enable Semgrep[/dim]")
        console.print("   [dim]rg config semgrep --disable      # Disable Semgrep[/dim]")
        console.print("   [dim]rg config semgrep --install      # Install Semgrep[/dim]")
        console.print("   [dim]rg config semgrep --add p/python # Add rule pack[/dim]")
        console.print("   [dim]rg config semgrep --remove auto  # Remove rule pack[/dim]")
        console.print("   [dim]rg config semgrep --list-rules   # Show available packs[/dim]")
        return

    # Apply changes
    changes = []

    if enable is not None:
        # Check if semgrep is installed when enabling
        if enable and not _check_semgrep_installed():
            console.print("\n[yellow]⚠️  Semgrep is not installed.[/yellow]")
            if typer.confirm("   Install Semgrep now?", default=True):
                if not _install_semgrep():
                    console.print("   [red]Cannot enable Semgrep without installation.[/red]")
                    raise typer.Exit(1)
            else:
                console.print("   [red]Cannot enable Semgrep without installation.[/red]")
                console.print("   [dim]Install with: rg config semgrep --install[/dim]")
                raise typer.Exit(1)

        config_manager.set_semgrep_enabled(enable)
        status = "enabled" if enable else "disabled"
        changes.append(f"Semgrep: [{'green' if enable else 'red'}]{status}[/{'green' if enable else 'red'}]")

    if add_config:
        config_manager.add_semgrep_config(add_config)
        changes.append(f"Added rule pack: [cyan]{add_config}[/cyan]")

    if remove_config:
        config_manager.remove_semgrep_config(remove_config)
        changes.append(f"Removed rule pack: [cyan]{remove_config}[/cyan]")

    if changes:
        console.print("\n[bold cyan]Semgrep Settings Updated[/bold cyan]\n")
        for change in changes:
            console.print(f"   ✓ {change}")


@config_app.command("export-prompt")
def export_prompt_cmd(
    name: str = typer.Argument("default", help="Prompt name to export (e.g., default, jira:issue_title, quality)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output filename (defaults to <name>.md)")
):
    """Export a built-in prompt template to .redgit/prompts/ or .redgit/templates/ for customization.

    The response format (JSON schema) is automatically appended by RedGit and cannot be modified.
    You can only customize the instructions and guidelines part of the prompt.

    Examples:
        rg config export-prompt default              # Export default.md (for rg propose)
        rg config export-prompt laravel              # Export laravel plugin prompt
        rg config export-prompt jira:issue_title     # Export Jira issue title prompt
        rg config export-prompt jira:issue_description  # Export Jira description prompt
        rg config export-prompt quality              # Export quality analysis prompt
    """
    from pathlib import Path
    from ..core.prompt import BUILTIN_PROMPTS_DIR
    from ..core.config import RETGIT_DIR
    from ..plugins.registry import get_plugin_by_name, get_builtin_plugins
    from ..integrations.registry import get_all_integrations

    # Integration/template prompts
    TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

    # Try to get prompt content
    content = None
    prompt_type = "propose"  # propose, integration, or plugin
    variables = []

    # Parse name for integration:prompt_name format (e.g., jira:issue_title)
    integration_name = None
    prompt_name = name
    if ":" in name:
        integration_name, prompt_name = name.split(":", 1)

    # Determine output filename
    if output:
        output_name = output if output.endswith(".md") else f"{output}.md"
    elif integration_name:
        output_name = f"{integration_name}_{prompt_name}.md"
    else:
        output_name = f"{name}.md"

    # 1. Check if it's an integration prompt (jira:issue_title or just jira)
    if integration_name or name in ["jira"]:
        integrations = get_all_integrations()
        target_integration = integration_name or name

        for int_cls in integrations.values():
            if int_cls.name == target_integration:
                prompts = int_cls.get_prompts()
                if prompts:
                    # If specific prompt requested
                    if prompt_name and prompt_name != target_integration and prompt_name in prompts:
                        prompt_def = prompts[prompt_name]
                        content = prompt_def.get("content", "")
                        variables = prompt_def.get("variables", [])
                        prompt_type = "integration"
                        console.print(f"   [dim]Exporting {target_integration}:{prompt_name} prompt[/dim]")
                        break
                    # If just integration name, list available prompts
                    elif prompt_name == target_integration or not integration_name:
                        console.print(f"\n[cyan]Available prompts for {target_integration}:[/cyan]")
                        for pname, pdef in prompts.items():
                            console.print(f"   • {target_integration}:{pname} - {pdef.get('description', '')}")
                        console.print(f"\n[dim]Export with: rg config export-prompt {target_integration}:<prompt_name>[/dim]")
                        return
                break

    # 2. Check legacy templates (quality_prompt.md, etc.)
    if not content:
        legacy_templates = {
            "quality": "quality_prompt.md",
            "quality_prompt": "quality_prompt.md",
        }
        if name in legacy_templates:
            template_file = legacy_templates[name]
            template_path = TEMPLATES_DIR / template_file
            if template_path.exists():
                content = template_path.read_text(encoding="utf-8")
                prompt_type = "integration"
                output_name = template_file
                console.print(f"   [dim]Exporting {name} template[/dim]")

    # 3. Check if it's a plugin name
    if not content:
        builtin_plugins = get_builtin_plugins()
        if name in builtin_plugins:
            plugin = get_plugin_by_name(name)
            if plugin and hasattr(plugin, "get_prompt"):
                content = plugin.get_prompt()
                if content:
                    prompt_type = "plugin"
                    console.print(f"   [dim]Exporting plugin prompt: {name}[/dim]")

    # 4. Check builtin prompts directory
    if not content:
        builtin_path = BUILTIN_PROMPTS_DIR / f"{name}.md"
        if builtin_path.exists():
            content = builtin_path.read_text(encoding="utf-8")
            console.print(f"   [dim]Exporting builtin prompt: {name}[/dim]")

    if not content:
        console.print(f"[red]Prompt '{name}' not found.[/red]")
        console.print("\n[dim]Available prompts:[/dim]")

        # List available
        available = []
        if BUILTIN_PROMPTS_DIR.exists():
            for f in BUILTIN_PROMPTS_DIR.glob("*.md"):
                available.append(f.stem)
        builtin_plugins = get_builtin_plugins()
        for pname in builtin_plugins:
            if pname not in available:
                available.append(f"{pname} (plugin)")

        # Add integration prompts
        integrations = get_all_integrations()
        for int_cls in integrations.values():
            prompts = int_cls.get_prompts()
            for pname in prompts.keys():
                available.append(f"{int_cls.name}:{pname}")

        for p in sorted(available):
            console.print(f"   • {p}")
        raise typer.Exit(1)

    # Determine output directory based on prompt type
    if prompt_type == "integration":
        output_dir = RETGIT_DIR / "templates"
    else:
        output_dir = RETGIT_DIR / "prompts"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    # Check if already exists
    if output_path.exists():
        from rich.prompt import Confirm
        if not Confirm.ask(f"   [yellow]{output_path} already exists. Overwrite?[/yellow]", default=False):
            console.print("   [dim]Cancelled.[/dim]")
            return

    # Build header comment
    header_lines = [
        "# ============================================================================",
        "# This prompt template can be customized.",
        "#",
        "# IMPORTANT: The response format (JSON schema) is automatically appended",
        "# by RedGit. You can only modify the instructions and guidelines here.",
        "# Do NOT add your own JSON schema - it will be ignored.",
        "#",
    ]

    if variables:
        header_lines.append("# Variables available:")
        for var in variables:
            header_lines.append(f"#   {{{{{var}}}}} - Will be replaced at runtime")
    else:
        header_lines.append("# Variables available:")
        header_lines.append("#   {{FILES}} - Will be replaced with the list of changed files")

    header_lines.extend(["# ============================================================================", "", ""])
    header = "\n".join(header_lines)

    # Write to file
    output_path.write_text(header + content, encoding="utf-8")

    console.print(f"\n[green]✓ Exported prompt to:[/green] {output_path}")

    if prompt_type == "integration":
        console.print(f"\n[dim]This prompt is used by the {integration_name or name} integration.[/dim]")
        console.print(f"[dim]Edit the file to customize the prompt behavior.[/dim]")
    else:
        console.print(f"\n[dim]To use this prompt:[/dim]")
        console.print(f"   1. Edit {output_path}")
        console.print(f"   2. Set in config: rg config set llm.prompt {output_name.replace('.md', '')}")
        console.print(f"   3. Or use directly: rg propose -p {output_name.replace('.md', '')}")

    console.print(f"\n[yellow]Note:[/yellow] Response format (JSON schema) is managed by RedGit and cannot be modified.")


@config_app.command("list-prompts")
def list_prompts_cmd():
    """List available prompt templates."""
    from pathlib import Path
    from ..core.prompt import BUILTIN_PROMPTS_DIR
    from ..core.config import RETGIT_DIR
    from ..plugins.registry import get_builtin_plugins
    from ..integrations.registry import get_all_integrations

    # Integration/template prompts
    TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

    console.print("\n[bold cyan]Available Prompts[/bold cyan]\n")

    # Builtin prompts (for rg propose)
    console.print("   [bold]Propose prompts (rg propose):[/bold]")
    if BUILTIN_PROMPTS_DIR.exists():
        for f in sorted(BUILTIN_PROMPTS_DIR.glob("*.md")):
            console.print(f"   • {f.stem}")

    # Plugin prompts
    builtin_plugins = get_builtin_plugins()
    if builtin_plugins:
        console.print("\n   [bold]Plugin prompts:[/bold]")
        for pname in sorted(builtin_plugins):
            console.print(f"   • {pname}")

    # Integration prompts (dynamic from integrations)
    console.print("\n   [bold]Integration prompts:[/bold]")
    integrations = get_all_integrations()
    for int_cls in integrations.values():
        prompts = int_cls.get_prompts()
        if prompts:
            for pname, pdef in prompts.items():
                desc = pdef.get("description", "")
                console.print(f"   • {int_cls.name}:{pname} [dim]- {desc}[/dim]")

    # Legacy template prompts
    if TEMPLATES_DIR.exists():
        for f in sorted(TEMPLATES_DIR.glob("*_prompt.md")):
            name = f.stem.replace("_prompt", "")
            console.print(f"   • {name} [dim](template)[/dim]")

    # Project prompts
    project_prompts = RETGIT_DIR / "prompts"
    project_templates = RETGIT_DIR / "templates"

    has_custom = False
    if project_prompts.exists():
        custom_prompts = list(project_prompts.glob("*.md"))
        if custom_prompts:
            if not has_custom:
                console.print("\n   [bold]Custom prompts (.redgit/):[/bold]")
                has_custom = True
            for f in sorted(custom_prompts):
                console.print(f"   • {f.stem} [green](custom)[/green]")

    if project_templates.exists():
        custom_templates = list(project_templates.glob("*.md"))
        if custom_templates:
            if not has_custom:
                console.print("\n   [bold]Custom prompts (.redgit/):[/bold]")
            for f in sorted(custom_templates):
                console.print(f"   • {f.stem} [green](custom template)[/green]")

    console.print("\n[dim]Export a prompt for customization: rg config export-prompt <name>[/dim]")