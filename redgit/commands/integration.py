import json
import typer
from pathlib import Path

from ..core.config import ConfigManager
from ..integrations.registry import (
    get_builtin_integrations,
    get_all_integrations,
    get_integration_class,
    get_integration_type,
    get_install_schema,
    get_all_install_schemas,
    IntegrationType
)

integration_app = typer.Typer(help="Integration management")


def _get_integration_type_name(integration_type: IntegrationType) -> str:
    """Get human-readable type name"""
    type_names = {
        IntegrationType.TASK_MANAGEMENT: "task_management",
        IntegrationType.CODE_HOSTING: "code_hosting",
        IntegrationType.NOTIFICATION: "notification",
        IntegrationType.ANALYSIS: "analysis",
    }
    return type_names.get(integration_type, "unknown")


def _get_integration_type_label(integration_type: IntegrationType) -> str:
    """Get human-readable type label"""
    type_labels = {
        IntegrationType.TASK_MANAGEMENT: "Task Management",
        IntegrationType.CODE_HOSTING: "Code Hosting",
        IntegrationType.NOTIFICATION: "Notification",
        IntegrationType.ANALYSIS: "Analysis",
    }
    return type_labels.get(integration_type, "Unknown")


def _get_installed_integrations() -> set:
    """
    Get names of integrations that are actually installed (not package builtins).

    Returns integrations from:
    - Global directory: ~/.redgit/integrations/
    - Project directory: .redgit/integrations/
    """
    from ..core.config import GLOBAL_INTEGRATIONS_DIR

    installed = set()

    # Global integrations (tap-installed)
    global_dir = GLOBAL_INTEGRATIONS_DIR
    if global_dir.exists():
        for item in global_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                installed.add(item.name)

    # Project integrations
    project_dir = Path(".redgit/integrations")
    if project_dir.exists():
        for item in project_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                installed.add(item.name)

    return installed


@integration_app.command("list")
def list_cmd(
    all_integrations: bool = typer.Option(False, "--all", "-a", help="Show all available integrations from taps")
):
    """List installed integrations"""
    config = ConfigManager().load()
    integrations_config = config.get("integrations", {})
    active_config = config.get("active", {})

    # Get actually installed integrations (global + project, not package builtins)
    installed_names = _get_installed_integrations()

    # Also include integrations that are enabled in config
    for name, cfg in integrations_config.items():
        if isinstance(cfg, dict) and cfg.get("enabled"):
            installed_names.add(name)

    if not installed_names:
        typer.echo("\n📦 No integrations installed.\n")
        typer.echo("  💡 Install from taps: rg install <name>")
        typer.echo("  💡 Browse available: rg integration list --all")
        typer.echo("")
        return

    # Group installed integrations by type
    by_type = {}
    schemas = get_all_install_schemas()

    for name in installed_names:
        itype = get_integration_type(name)
        if itype not in by_type:
            by_type[itype] = []
        by_type[itype].append(name)

    typer.echo("\n📦 Installed integrations:\n")

    for itype, names in by_type.items():
        type_name = _get_integration_type_name(itype)
        type_label = _get_integration_type_label(itype)
        active_name = active_config.get(type_name)

        typer.echo(f"  {type_label}:")

        for name in sorted(names):
            schema = schemas.get(name, {})
            enabled = integrations_config.get(name, {}).get("enabled", False)
            configured = _is_configured(integrations_config.get(name, {}), schema)
            is_active = (active_name == name)

            # Build status
            if is_active and enabled and configured:
                status = "✓ active"
                marker = "●"
            elif enabled and configured:
                status = "✓ configured"
                marker = "○"
            elif enabled:
                status = "⚠ not configured"
                marker = "○"
            else:
                status = "installed"
                marker = "○"

            typer.echo(f"    {marker} {name} ({status})")

        # Show active integration for this type
        if active_name:
            typer.echo(f"    └─ Active: {active_name}")
        typer.echo("")

    # Show available from taps
    if all_integrations:
        from ..core.tap import TapManager

        tap_mgr = TapManager()
        tap_integrations = tap_mgr.get_all_integrations(include_installed=True)

        # Filter out already installed
        available = [i for i in tap_integrations if i.name not in installed_names and i.name.replace("-", "_") not in installed_names]

        if available:
            typer.echo("📥 Available from taps:\n")

            # Group by type
            by_item_type = {}
            for integ in available:
                item_type = integ.item_type or "utility"
                if item_type not in by_item_type:
                    by_item_type[item_type] = []
                by_item_type[item_type].append(integ)

            for item_type, integs in sorted(by_item_type.items()):
                type_label = item_type.replace("_", " ").title()
                typer.echo(f"  {type_label}:")
                for integ in sorted(integs, key=lambda x: x.name):
                    tap_label = f" ({integ.tap_name})" if integ.tap_name != "official" else ""
                    typer.echo(f"    ○ {integ.name}{tap_label}")
                    if integ.description:
                        typer.echo(f"      {integ.description[:60]}...")
                typer.echo("")

            typer.echo("  💡 Install: rg install <name>")
            typer.echo("")
    else:
        typer.echo("  💡 Show all from taps: rg integration list --all")
        typer.echo("")

    typer.echo("  💡 Commands:")
    typer.echo("     rg install <name>              - Install from tap")
    typer.echo("     rg integration config <name>   - Reconfigure")
    typer.echo("     rg integration use <name>      - Set as active")
    typer.echo("")


def _is_configured(config: dict, schema: dict) -> bool:
    """Check if integration has required fields configured"""
    if not config.get("enabled"):
        return False

    fields = schema.get("fields", [])
    for field in fields:
        if field.get("required"):
            key = field.get("key") or field.get("name") or ""
            if key and (key not in config or not config[key]):
                return False
    return True


def configure_integration(name: str):
    """Configure an integration (called by rg install)"""
    # Get all integrations including global (tap-installed)
    all_integrations = get_all_integrations()

    # Also try with normalized name (hyphen/underscore)
    normalized_name = name.replace("-", "_")

    if name not in all_integrations and normalized_name not in all_integrations:
        available = list(all_integrations.keys())
        typer.secho(f"❌ '{name}' integration not found.", fg=typer.colors.RED)
        typer.echo(f"   Available: {', '.join(available)}")
        raise typer.Exit(1)

    # Use the correct name
    if name not in all_integrations:
        name = normalized_name

    schema = get_install_schema(name)
    if not schema:
        # No schema, just enable
        config = ConfigManager().load()
        if "integrations" not in config:
            config["integrations"] = {}
        config["integrations"][name] = {"enabled": True}
        ConfigManager().save(config)
        return

    typer.echo(f"🔧 Configuring {schema.get('name', name)}\n")

    if schema.get("description"):
        typer.echo(f"   {schema['description']}\n")

    # Start with defaults from schema
    config_values = {"enabled": True}
    defaults = schema.get("defaults", {})
    for key, value in defaults.items():
        config_values[key] = value

    # Collect field values (overrides defaults)
    for field in schema.get("fields", []):
        value = _prompt_field(field)
        if value is not None:
            field_key = field.get("key") or field.get("name") or ""
            config_values[field_key] = value

    # Call integration's after_install hook if available
    try:
        integration_cls = get_integration_class(name)
        if integration_cls and hasattr(integration_cls, 'after_install'):
            config_values = integration_cls.after_install(config_values)
    except Exception:
        pass  # after_install is optional

    # Save to config
    config = ConfigManager().load()
    if "integrations" not in config:
        config["integrations"] = {}

    config["integrations"][name] = config_values

    # Get integration type
    itype = get_integration_type(name)
    type_name = _get_integration_type_name(itype) if itype else None
    type_label = _get_integration_type_label(itype) if itype else None

    # Check if should set as active
    set_active = False
    if type_name:
        current_active = config.get("active", {}).get(type_name)
        if not current_active:
            # No active integration for this type, set automatically
            set_active = True
        elif current_active != name:
            # Different integration active, ask user
            set_active = typer.confirm(
                f"\n   Set '{name}' as active {type_label}? (current: {current_active})",
                default=True
            )

    if set_active and type_name:
        if "active" not in config:
            config["active"] = {}
        config["active"][type_name] = name

    ConfigManager().save(config)

    typer.echo("")
    typer.secho(f"✅ {schema.get('name', name)} configured.", fg=typer.colors.GREEN)
    if set_active:
        typer.secho(f"   Set as active {type_label}.", fg=typer.colors.GREEN)
    typer.echo(f"   Configuration saved to .redgit/config.yaml")


@integration_app.command("config")
def config_cmd(name: str):
    """Reconfigure an installed integration"""
    configure_integration(name)


def _get_field_key(field: dict) -> str:
    """Get field key from schema field (supports both 'key' and 'name')"""
    return field.get("key") or field.get("name") or ""


def _prompt_field(field: dict):
    """Prompt user for a field value"""
    key = _get_field_key(field)
    prompt_text = field.get("prompt") or field.get("label") or key
    field_type = field.get("type", "text")
    # Normalize type: "string" -> "text"
    if field_type == "string":
        field_type = "text"
    default = field.get("default")
    required = field.get("required", False)
    help_text = field.get("help") or field.get("description")
    env_var = field.get("env_var")

    # Show help text if available
    if help_text:
        typer.echo(f"   💡 {help_text}")

    # Show env var hint for secrets
    if env_var:
        typer.echo(f"   💡 Can also be set via {env_var} environment variable")

    if field_type == "text":
        if default:
            value = typer.prompt(f"   {prompt_text}", default=default)
        elif required:
            value = typer.prompt(f"   {prompt_text}")
        else:
            value = typer.prompt(f"   {prompt_text} (optional)", default="")
        return value if value else None

    elif field_type == "secret":
        if required:
            value = typer.prompt(f"   {prompt_text}", hide_input=True)
        else:
            value = typer.prompt(f"   {prompt_text} (optional, press Enter to skip)",
                               hide_input=True, default="")
        return value if value else None

    elif field_type == "choice":
        choices = field.get("choices", [])
        typer.echo(f"   {prompt_text}")
        for i, choice in enumerate(choices, 1):
            marker = ">" if choice == default else " "
            typer.echo(f"   {marker} [{i}] {choice}")

        choice_idx = typer.prompt(f"   Select", default=str(choices.index(default) + 1) if default else "1")
        try:
            idx = int(choice_idx) - 1
            return choices[idx] if 0 <= idx < len(choices) else default
        except (ValueError, IndexError):
            return default

    elif field_type == "confirm":
        return typer.confirm(f"   {prompt_text}", default=default or False)

    elif field_type == "integration_select":
        # Select from available integrations of specific type
        integration_type_str = field.get("integration_type", "")
        config = ConfigManager().load()
        integrations_config = config.get("integrations", {})
        active_config = config.get("active", {})

        # Find available integrations of this type
        available = []
        all_integrations = get_all_integrations()
        for int_name, int_cls in all_integrations.items():
            itype = getattr(int_cls, 'integration_type', None)
            if itype:
                type_name = _get_integration_type_name(itype)
                if type_name == integration_type_str:
                    # Check if configured
                    if integrations_config.get(int_name, {}).get("enabled"):
                        available.append(int_name)

        if not available:
            typer.echo(f"   {prompt_text}")
            typer.echo(f"   [dim]No {integration_type_str} integrations available[/dim]")
            if not required:
                typer.echo(f"   [dim]Skipping...[/dim]")
                return None
            else:
                typer.secho(f"   ❌ No {integration_type_str} integrations configured.", fg=typer.colors.RED)
                typer.echo(f"   💡 Install one first: rg integration install jira")
                return None

        # Show options
        typer.echo(f"   {prompt_text}")
        typer.echo(f"     [0] None (skip)")
        for i, int_name in enumerate(available, 1):
            active_marker = " (active)" if active_config.get(integration_type_str) == int_name else ""
            typer.echo(f"     [{i}] {int_name}{active_marker}")

        choice_idx = typer.prompt(f"   Select", default="0")
        try:
            idx = int(choice_idx)
            if idx == 0:
                return None
            return available[idx - 1] if 0 < idx <= len(available) else None
        except (ValueError, IndexError):
            return None

    return None


@integration_app.command("add")
def add_cmd(name: str):
    """Enable an integration (use 'install' to configure)"""
    builtin = get_builtin_integrations()

    if name not in builtin:
        typer.secho(f"❌ '{name}' integration not found.", fg=typer.colors.RED)
        typer.echo(f"   Available: {', '.join(builtin)}")
        raise typer.Exit(1)

    config = ConfigManager().load()
    if "integrations" not in config:
        config["integrations"] = {}

    if name in config["integrations"] and config["integrations"][name].get("enabled"):
        typer.echo(f"   {name} is already enabled.")
        typer.echo(f"   💡 Run 'redgit integration install {name}' to reconfigure")
        return

    config["integrations"][name] = {"enabled": True}
    ConfigManager().save(config)

    typer.secho(f"✅ {name} integration enabled.", fg=typer.colors.GREEN)
    typer.echo(f"   ⚠️  Run 'redgit integration install {name}' to configure")


@integration_app.command("update")
def update_cmd(
    name: str = typer.Argument(None, help="Integration name to update (or omit to update all)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinstall even if up to date")
):
    """Update installed integrations from taps"""
    from ..core.tap import TapManager, find_item_in_taps
    from .tap import install_from_tap

    tap_mgr = TapManager()
    config = ConfigManager().load()
    integrations_config = config.get("integrations", {})

    # Get installed integrations
    installed_names = _get_installed_integrations()

    # Also include integrations enabled in config
    for int_name, cfg in integrations_config.items():
        if isinstance(cfg, dict) and cfg.get("enabled"):
            installed_names.add(int_name)

    if not installed_names:
        typer.echo("\n📦 No integrations installed.\n")
        typer.echo("  💡 Install from taps: rg install <name>")
        return

    # Determine which integrations to update
    if name:
        # Update specific integration
        # Normalize name
        normalized_name = name.replace("-", "_")
        if name not in installed_names and normalized_name not in installed_names:
            typer.secho(f"❌ '{name}' is not installed.", fg=typer.colors.RED)
            typer.echo(f"   Installed: {', '.join(sorted(installed_names))}")
            raise typer.Exit(1)

        target_name = name if name in installed_names else normalized_name
        to_update = [target_name]
    else:
        # Update all integrations
        to_update = sorted(installed_names)

    typer.echo(f"\n🔄 Updating {len(to_update)} integration(s)...\n")

    updated = 0
    failed = 0
    skipped = 0

    for int_name in to_update:
        typer.echo(f"   {int_name}...", nl=False)

        try:
            # Find integration in taps
            result = find_item_in_taps(int_name, "integration")

            if not result:
                # Try with hyphen variant
                result = find_item_in_taps(int_name.replace("_", "-"), "integration")

            if not result:
                # Not from a tap, might be local custom integration
                typer.secho(" skipped (local/custom)", fg=typer.colors.YELLOW)
                skipped += 1
                continue

            # Update from tap using install_from_tap with force=True
            success = install_from_tap(int_name, force=True, no_configure=True)

            if success:
                typer.secho(" ✓ updated", fg=typer.colors.GREEN)
                updated += 1
            else:
                typer.secho(" ✗ failed", fg=typer.colors.RED)
                failed += 1

        except Exception as e:
            typer.secho(f" ✗ failed: {e}", fg=typer.colors.RED)
            failed += 1

    # Summary
    typer.echo("")
    if updated > 0:
        typer.secho(f"✅ Updated {updated} integration(s)", fg=typer.colors.GREEN)
    if skipped > 0:
        typer.echo(f"   Skipped: {skipped}")
    if failed > 0:
        typer.secho(f"   Failed: {failed}", fg=typer.colors.RED)

    typer.echo("")


@integration_app.command("remove")
def remove_cmd(name: str):
    """Disable an integration"""
    config = ConfigManager().load()
    integrations = config.get("integrations", {})

    if name not in integrations:
        typer.secho(f"❌ '{name}' integration is not configured.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Keep config but disable
    config["integrations"][name]["enabled"] = False
    ConfigManager().save(config)

    typer.secho(f"✅ {name} integration disabled.", fg=typer.colors.GREEN)
    typer.echo(f"   💡 Configuration preserved. Use 'install' to re-enable.")


@integration_app.command("use")
def use_cmd(name: str):
    """Set an integration as active for its type"""
    builtin = get_builtin_integrations()

    if name not in builtin:
        typer.secho(f"❌ '{name}' integration not found.", fg=typer.colors.RED)
        typer.echo(f"   Available: {', '.join(builtin)}")
        raise typer.Exit(1)

    # Get integration type
    itype = get_integration_type(name)
    if not itype:
        typer.secho(f"❌ Unknown integration type for '{name}'.", fg=typer.colors.RED)
        raise typer.Exit(1)

    type_name = _get_integration_type_name(itype)
    type_label = _get_integration_type_label(itype)

    config = ConfigManager().load()
    integrations_config = config.get("integrations", {})
    schema = get_install_schema(name) or {}

    # Check if integration is installed and configured
    enabled = integrations_config.get(name, {}).get("enabled", False)
    configured = _is_configured(integrations_config.get(name, {}), schema)

    if not enabled or not configured:
        typer.secho(f"⚠️  '{name}' is not installed or configured.", fg=typer.colors.YELLOW)
        if typer.confirm(f"   Configure '{name}' now?", default=True):
            configure_integration(name)
            # Reload config after configuration
            config = ConfigManager().load()
        else:
            typer.echo(f"   💡 Run 'rg install {name}' first")
            raise typer.Exit(1)

    # Set as active
    if "active" not in config:
        config["active"] = {}

    old_active = config["active"].get(type_name)
    config["active"][type_name] = name
    ConfigManager().save(config)

    if old_active and old_active != name:
        typer.secho(f"✅ {type_label}: {old_active} → {name}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"✅ {type_label}: {name} (active)", fg=typer.colors.GREEN)

    typer.echo(f"   Configuration saved to .redgit/config.yaml")


# ==================== Create Custom Integration ====================

INTEGRATION_TYPES = {
    "1": ("task_management", "TaskManagementBase", "Task Management (Jira, Linear, etc.)"),
    "2": ("code_hosting", "CodeHostingBase", "Code Hosting (GitHub, GitLab, etc.)"),
    "3": ("notification", "NotificationBase", "Notification (Slack, Discord, etc.)"),
    "4": ("analysis", "AnalysisBase", "Analysis (Code review, metrics, etc.)"),
}


def _generate_init_py(name: str, class_name: str, base_class: str, type_name: str, description: str) -> str:
    """Generate __init__.py template for custom integration."""
    return f'''"""
{class_name} - Custom RedGit Integration

{description}

This integration was created with: rg integration create
Documentation: See README.md in this folder
"""

from pathlib import Path
from typing import Optional, Dict, Any, List

from redgit.integrations.base import {base_class}, IntegrationType


class {class_name}({base_class}):
    """
    {description}

    Configuration (.redgit/config.yaml):
        integrations:
          {name}:
            enabled: true
            api_key: "your-api-key"
            # Add your config fields here
    """

    name = "{name}"
    integration_type = IntegrationType.{type_name.upper()}

    def __init__(self):
        super().__init__()
        self.api_key = ""
        # Add your instance variables here

    def setup(self, config: dict):
        """
        Initialize the integration with config values.
        Called when the integration is loaded.
        """
        self.api_key = config.get("api_key", "")
        # Load your config values here

        if not self.api_key:
            self.enabled = False
            return

        self.enabled = True

    def validate_connection(self) -> bool:
        """Test if the integration can connect to the external service."""
        if not self.enabled:
            return False

        # TODO: Implement connection validation
        # Example: Make a test API call
        return True

    # ==================== AI-Powered Methods ====================
    # Use prompts from the prompts/ folder for AI operations

    def _load_prompt(self, prompt_name: str, **kwargs) -> str:
        """
        Load a prompt template from the prompts/ folder.

        Args:
            prompt_name: Name of the prompt file (without .txt extension)
            **kwargs: Variables to substitute in the prompt

        Returns:
            Formatted prompt string
        """
        prompt_dir = Path(__file__).parent / "prompts"
        prompt_file = prompt_dir / f"{{prompt_name}}.txt"

        if not prompt_file.exists():
            return ""

        template = prompt_file.read_text(encoding="utf-8")

        # Simple variable substitution
        for key, value in kwargs.items():
            template = template.replace(f"{{{{{{key}}}}}}", str(value))

        return template

    def analyze_with_ai(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Example AI-powered analysis method.

        Uses the 'analyze' prompt from prompts/analyze.txt
        """
        prompt = self._load_prompt("analyze", content=content)

        if not prompt:
            return None

        # TODO: Call your AI service here
        # Example with OpenAI:
        # response = openai.chat.completions.create(
        #     model="gpt-4",
        #     messages=[{{"role": "user", "content": prompt}}]
        # )
        # return {{"result": response.choices[0].message.content}}

        return {{"prompt": prompt, "status": "not_implemented"}}

    # ==================== Hook Methods ====================
    # Override these methods to react to RedGit events

    def on_commit(self, commit_data: dict):
        """Called after a commit is created."""
        pass

    def on_branch_create(self, branch_name: str):
        """Called after a branch is created."""
        pass

    # ==================== Custom Commands ====================
    # Add integration-specific CLI commands in commands.py

    @classmethod
    def after_install(cls, config: dict) -> dict:
        """
        Hook called after installation.
        Use this to modify config or perform setup tasks.
        """
        # Example: Add default values
        # config.setdefault("some_option", "default_value")
        return config
'''


def _generate_commands_py(name: str, class_name: str) -> str:
    """Generate commands.py template for CLI commands."""
    return f'''"""
CLI commands for {class_name} integration.

Commands are automatically registered when the integration is active.
Usage: rg {name} <command>
"""

import typer

{name}_app = typer.Typer(help="{class_name} integration commands")


@{name}_app.command("status")
def status_cmd():
    """Show integration status and connection info."""
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import load_integration_by_name

    config = ConfigManager().load()
    integration_config = config.get("integrations", {{}}).get("{name}", {{}})

    if not integration_config.get("enabled"):
        typer.secho("❌ {class_name} integration is not enabled.", fg=typer.colors.RED)
        typer.echo("   Run: rg integration install {name}")
        raise typer.Exit(1)

    integration = load_integration_by_name("{name}", integration_config)

    if not integration or not integration.enabled:
        typer.secho("⚠️  {class_name} is enabled but not properly configured.", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    typer.secho("✅ {class_name} integration is active", fg=typer.colors.GREEN)

    # Test connection
    if hasattr(integration, 'validate_connection'):
        if integration.validate_connection():
            typer.echo("   Connection: OK")
        else:
            typer.secho("   Connection: FAILED", fg=typer.colors.RED)


@{name}_app.command("test")
def test_cmd(message: str = typer.Argument("Hello from {class_name}!")):
    """Test the integration with a sample operation."""
    typer.echo(f"Testing {class_name} with: {{message}}")

    # TODO: Implement your test logic
    typer.secho("✅ Test completed!", fg=typer.colors.GREEN)


@{name}_app.command("analyze")
def analyze_cmd(
    text: str = typer.Option(None, "--text", "-t", help="Text to analyze"),
    file: str = typer.Option(None, "--file", "-f", help="File to analyze")
):
    """Run AI-powered analysis (example command)."""
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import load_integration_by_name

    config = ConfigManager().load()
    integration_config = config.get("integrations", {{}}).get("{name}", {{}})
    integration = load_integration_by_name("{name}", integration_config)

    if not integration:
        typer.secho("❌ Integration not configured.", fg=typer.colors.RED)
        raise typer.Exit(1)

    content = text
    if file:
        from pathlib import Path
        content = Path(file).read_text(encoding="utf-8")

    if not content:
        typer.echo("Please provide --text or --file")
        raise typer.Exit(1)

    typer.echo("Analyzing...")
    result = integration.analyze_with_ai(content)

    if result:
        typer.echo(f"Result: {{result}}")
    else:
        typer.secho("Analysis failed.", fg=typer.colors.RED)
'''


def _generate_install_schema(name: str, display_name: str, description: str) -> dict:
    """Generate install_schema.json content."""
    return {
        "name": display_name,
        "description": description,
        "fields": [
            {
                "key": "api_key",
                "prompt": "API Key",
                "type": "secret",
                "env_var": f"{name.upper()}_API_KEY",
                "help": "Your API key for authentication",
                "required": True
            },
            {
                "key": "base_url",
                "prompt": "API Base URL (optional)",
                "type": "text",
                "required": False,
                "help": "Override the default API endpoint"
            }
        ],
        "defaults": {}
    }


def _generate_readme(name: str, class_name: str, description: str) -> str:
    """Generate README.md documentation."""
    return f'''# {class_name} Integration

{description}

## Installation

```bash
rg integration install {name}
```

## Configuration

Add to `.redgit/config.yaml`:

```yaml
integrations:
  {name}:
    enabled: true
    api_key: "your-api-key"
    # Add additional config here
```

Or set environment variable:
```bash
export {name.upper()}_API_KEY="your-api-key"
```

## Usage

### CLI Commands

```bash
# Check integration status
rg {name} status

# Run a test
rg {name} test "Hello World"

# Analyze content with AI
rg {name} analyze --text "Your text here"
rg {name} analyze --file path/to/file.txt
```

### Programmatic Usage

```python
from redgit.integrations.registry import load_integration_by_name

config = {{"enabled": True, "api_key": "your-key"}}
integration = load_integration_by_name("{name}", config)

if integration and integration.enabled:
    result = integration.analyze_with_ai("Your content")
```

## AI Prompts

This integration uses prompt templates from the `prompts/` folder:

- `prompts/analyze.txt` - Template for AI analysis
- `prompts/summarize.txt` - Template for summarization
- `prompts/custom.txt` - Add your own prompts

### Using Prompts

```python
# In your integration code:
prompt = self._load_prompt("analyze", content="Your content here")
```

### Creating Custom Prompts

1. Create a new file in `prompts/` folder (e.g., `my_prompt.txt`)
2. Use `{{variable}}` syntax for substitution
3. Load with `self._load_prompt("my_prompt", variable="value")`

## Development

### File Structure

```
.redgit/integrations/{name}/
├── __init__.py          # Main integration class
├── commands.py          # CLI commands
├── install_schema.json  # Installation wizard schema
├── README.md            # This documentation
└── prompts/             # AI prompt templates
    ├── analyze.txt
    ├── summarize.txt
    └── custom.txt
```

### Adding New Features

1. Add methods to `{class_name}` in `__init__.py`
2. Add CLI commands in `commands.py`
3. Create prompt templates in `prompts/`

### Testing

```bash
# Test your integration
rg {name} status
rg {name} test
```

## API Reference

### {class_name}

| Method | Description |
|--------|-------------|
| `setup(config)` | Initialize with config |
| `validate_connection()` | Test API connection |
| `analyze_with_ai(content)` | AI-powered analysis |
| `_load_prompt(name, **kwargs)` | Load prompt template |

## Troubleshooting

### Integration not found

Make sure the integration folder is in `.redgit/integrations/` and contains `__init__.py`.

### Connection failed

1. Check your API key
2. Verify network connectivity
3. Check the base URL configuration

## License

This integration is part of your local RedGit configuration.
'''


def _generate_prompt_analyze() -> str:
    """Generate analyze.txt prompt template."""
    return '''You are an expert analyst. Analyze the following content and provide insights.

## Content to Analyze

{content}

## Instructions

1. Identify the main topics and themes
2. Extract key information
3. Provide a structured analysis

## Output Format

Provide your analysis in the following format:

### Summary
[Brief summary of the content]

### Key Points
- [Point 1]
- [Point 2]
- [Point 3]

### Recommendations
[Any recommendations based on the analysis]
'''


def _generate_prompt_summarize() -> str:
    """Generate summarize.txt prompt template."""
    return '''Summarize the following content concisely.

## Content

{content}

## Requirements

- Keep the summary under {max_length} words
- Focus on the most important information
- Use clear, simple language

## Summary
'''


def _generate_prompt_custom() -> str:
    """Generate custom.txt prompt template example."""
    return '''# Custom Prompt Template

This is an example custom prompt. Modify it for your specific use case.

## Input

{input}

## Context

{context}

## Task

{task}

## Output

Provide your response below:
'''


@integration_app.command("create")
def create_cmd(name: str = typer.Argument(None, help="Integration name (lowercase, underscores allowed)")):
    """Create a new custom integration from template."""
    typer.echo("\n🔧 Create Custom Integration\n")

    # Get integration name
    if not name:
        name = typer.prompt("   Integration name (lowercase, e.g., my_service)")

    # Validate name
    name = name.lower().replace("-", "_").replace(" ", "_")
    if not name.isidentifier():
        typer.secho(f"❌ Invalid name '{name}'. Use lowercase letters, numbers, and underscores.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Check if already exists
    integration_dir = Path(".redgit/integrations") / name
    if integration_dir.exists():
        typer.secho(f"❌ Integration '{name}' already exists at {integration_dir}", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Check builtin integrations
    builtin = get_builtin_integrations()
    if name in builtin:
        typer.secho(f"❌ '{name}' conflicts with a builtin integration.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Get display name
    default_display = "".join(word.capitalize() for word in name.split("_"))
    display_name = typer.prompt("   Display name", default=default_display)

    # Get description
    description = typer.prompt("   Description", default=f"{display_name} custom integration for RedGit")

    # Get integration type
    typer.echo("\n   Integration type:")
    for key, (_, _, label) in INTEGRATION_TYPES.items():
        typer.echo(f"     [{key}] {label}")

    type_choice = typer.prompt("   Select type", default="4")
    type_name, base_class, _ = INTEGRATION_TYPES.get(type_choice, INTEGRATION_TYPES["4"])

    # Generate class name
    class_name = "".join(word.capitalize() for word in name.split("_")) + "Integration"

    # Create directory structure
    typer.echo(f"\n   Creating {integration_dir}...")
    integration_dir.mkdir(parents=True, exist_ok=True)

    prompts_dir = integration_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    # Generate files
    files_created = []

    # __init__.py
    init_file = integration_dir / "__init__.py"
    init_file.write_text(_generate_init_py(name, class_name, base_class, type_name, description), encoding="utf-8")
    files_created.append("__init__.py")

    # commands.py
    commands_file = integration_dir / "commands.py"
    commands_file.write_text(_generate_commands_py(name, class_name), encoding="utf-8")
    files_created.append("commands.py")

    # install_schema.json
    schema_file = integration_dir / "install_schema.json"
    schema_file.write_text(json.dumps(_generate_install_schema(name, display_name, description), indent=2, ensure_ascii=False), encoding="utf-8")
    files_created.append("install_schema.json")

    # README.md
    readme_file = integration_dir / "README.md"
    readme_file.write_text(_generate_readme(name, class_name, description), encoding="utf-8")
    files_created.append("README.md")

    # Prompt templates
    (prompts_dir / "analyze.txt").write_text(_generate_prompt_analyze(), encoding="utf-8")
    (prompts_dir / "summarize.txt").write_text(_generate_prompt_summarize(), encoding="utf-8")
    (prompts_dir / "custom.txt").write_text(_generate_prompt_custom(), encoding="utf-8")
    files_created.append("prompts/analyze.txt")
    files_created.append("prompts/summarize.txt")
    files_created.append("prompts/custom.txt")

    # Refresh integration cache
    from ..integrations.registry import refresh_integrations
    refresh_integrations()

    # Success message
    typer.echo("")
    typer.secho(f"✅ Created custom integration: {name}", fg=typer.colors.GREEN)
    typer.echo(f"\n   📁 Location: {integration_dir}")
    typer.echo(f"\n   📄 Files created:")
    for f in files_created:
        typer.echo(f"      - {f}")

    typer.echo(f"\n   📚 Next steps:")
    typer.echo(f"      1. Edit {integration_dir}/__init__.py to add your logic")
    typer.echo(f"      2. Customize prompts in {prompts_dir}/")
    typer.echo(f"      3. Install: rg integration install {name}")
    typer.echo(f"      4. Test: rg {name} status")
    typer.echo("")