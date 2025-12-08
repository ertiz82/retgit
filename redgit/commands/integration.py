import json
import typer
from pathlib import Path

from ..core.config import ConfigManager
from ..integrations.registry import get_builtin_integrations, BUILTIN_INTEGRATIONS, IntegrationType

integration_app = typer.Typer(help="Integration management")

# Load install schemas
SCHEMAS_FILE = Path(__file__).parent.parent / "integrations" / "install_schemas.json"


def load_install_schemas() -> dict:
    """Load integration install schemas"""
    if SCHEMAS_FILE.exists():
        with open(SCHEMAS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("integrations", {})
    return {}


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


@integration_app.command("list")
def list_cmd():
    """List available and enabled integrations"""
    builtin = get_builtin_integrations()
    schemas = load_install_schemas()
    config = ConfigManager().load()
    integrations_config = config.get("integrations", {})
    active_config = config.get("active", {})

    # Group integrations by type
    by_type = {}
    for name in builtin:
        itype = BUILTIN_INTEGRATIONS.get(name)
        if itype not in by_type:
            by_type[itype] = []
        by_type[itype].append(name)

    typer.echo("\n📦 Available integrations:\n")

    for itype, names in by_type.items():
        type_name = _get_integration_type_name(itype)
        type_label = _get_integration_type_label(itype)
        active_name = active_config.get(type_name)

        typer.echo(f"  {type_label}:")

        for name in names:
            schema = schemas.get(name, {})
            description = schema.get("description", "")
            enabled = integrations_config.get(name, {}).get("enabled", False)
            configured = _is_configured(integrations_config.get(name, {}), schema)
            is_active = (active_name == name)

            # Build status
            if is_active and enabled and configured:
                status = "✓ active"
                marker = "●"
            elif enabled and configured:
                status = "✓ installed"
                marker = "○"
            elif enabled:
                status = "⚠ not configured"
                marker = "○"
            else:
                status = "not installed"
                marker = "○"

            typer.echo(f"    {marker} {name} ({status})")

        # Show active integration for this type
        if active_name:
            typer.echo(f"    └─ Active: {active_name}")
        else:
            typer.echo(f"    └─ Active: none (use 'rg integration use {names[0]}' to set)")

        typer.echo("")

    typer.echo("  💡 Commands:")
    typer.echo("     rg integration install <name>  - Install and configure")
    typer.echo("     rg integration use <name>      - Set as active for its type")
    typer.echo("")


def _is_configured(config: dict, schema: dict) -> bool:
    """Check if integration has required fields configured"""
    if not config.get("enabled"):
        return False

    fields = schema.get("fields", [])
    for field in fields:
        if field.get("required"):
            key = field["key"]
            if key not in config or not config[key]:
                return False
    return True


@integration_app.command("install")
def install_cmd(name: str):
    """Install and configure an integration"""
    builtin = get_builtin_integrations()
    schemas = load_install_schemas()

    if name not in builtin:
        typer.secho(f"❌ '{name}' integration not found.", fg=typer.colors.RED)
        typer.echo(f"   Available: {', '.join(builtin)}")
        raise typer.Exit(1)

    schema = schemas.get(name)
    if not schema:
        typer.secho(f"❌ No install schema for '{name}'.", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(f"\n🔌 Installing {schema.get('name', name)} integration\n")

    if schema.get("description"):
        typer.echo(f"   {schema['description']}\n")

    # Collect field values
    config_values = {"enabled": True}

    for field in schema.get("fields", []):
        value = _prompt_field(field)
        if value is not None:
            config_values[field["key"]] = value

    # Save to config
    config = ConfigManager().load()
    if "integrations" not in config:
        config["integrations"] = {}

    config["integrations"][name] = config_values

    # Get integration type
    itype = BUILTIN_INTEGRATIONS.get(name)
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
    typer.secho(f"✅ {schema.get('name', name)} integration installed.", fg=typer.colors.GREEN)
    if set_active:
        typer.secho(f"   Set as active {type_label}.", fg=typer.colors.GREEN)
    typer.echo(f"   Configuration saved to .redgit/config.yaml")


def _prompt_field(field: dict):
    """Prompt user for a field value"""
    key = field["key"]
    prompt_text = field.get("prompt", key)
    field_type = field.get("type", "text")
    default = field.get("default")
    required = field.get("required", False)
    help_text = field.get("help")
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
        for int_name, itype in BUILTIN_INTEGRATIONS.items():
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
    schemas = load_install_schemas()

    if name not in builtin:
        typer.secho(f"❌ '{name}' integration not found.", fg=typer.colors.RED)
        typer.echo(f"   Available: {', '.join(builtin)}")
        raise typer.Exit(1)

    # Get integration type
    itype = BUILTIN_INTEGRATIONS.get(name)
    if not itype:
        typer.secho(f"❌ Unknown integration type for '{name}'.", fg=typer.colors.RED)
        raise typer.Exit(1)

    type_name = _get_integration_type_name(itype)
    type_label = _get_integration_type_label(itype)

    config = ConfigManager().load()
    integrations_config = config.get("integrations", {})
    schema = schemas.get(name, {})

    # Check if integration is installed and configured
    enabled = integrations_config.get(name, {}).get("enabled", False)
    configured = _is_configured(integrations_config.get(name, {}), schema)

    if not enabled or not configured:
        typer.secho(f"⚠️  '{name}' is not installed or configured.", fg=typer.colors.YELLOW)
        if typer.confirm(f"   Install '{name}' now?", default=True):
            install_cmd(name)
            # Reload config after install
            config = ConfigManager().load()
        else:
            typer.echo(f"   💡 Run 'rg integration install {name}' first")
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