import json
import typer
from pathlib import Path

from ..core.config import ConfigManager
from ..integrations.registry import get_builtin_integrations

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


@integration_app.command("list")
def list_cmd():
    """List available and enabled integrations"""
    builtin = get_builtin_integrations()
    schemas = load_install_schemas()
    config = ConfigManager().load()
    integrations = config.get("integrations", {})

    typer.echo("\n📦 Available integrations:")
    for name in builtin:
        schema = schemas.get(name, {})
        description = schema.get("description", "")
        enabled = integrations.get(name, {}).get("enabled", False)
        configured = _is_configured(integrations.get(name, {}), schema)

        if enabled and configured:
            status = "✓ installed"
        elif enabled:
            status = "⚠ enabled but not configured"
        else:
            status = "○ not installed"

        typer.echo(f"   {name} ({status})")
        if description:
            typer.echo(f"      {description}")

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
    ConfigManager().save(config)

    typer.echo("")
    typer.secho(f"✅ {schema.get('name', name)} integration installed.", fg=typer.colors.GREEN)
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