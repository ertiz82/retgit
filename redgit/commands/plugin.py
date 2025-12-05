import typer

from ..core.config import ConfigManager
from ..plugins.registry import get_builtin_plugins

plugin_app = typer.Typer(help="Plugin management")


@plugin_app.command("list")
def list_cmd():
    """List available and enabled plugins"""
    builtin = get_builtin_plugins()
    config = ConfigManager().load()
    enabled = config.get("plugins", {}).get("enabled", [])

    typer.echo("\n📦 Available plugins:")
    for name in builtin:
        status = "✓ enabled" if name in enabled else "○ disabled"
        typer.echo(f"   {name} ({status})")

    typer.echo("")


@plugin_app.command("add")
def add_cmd(name: str):
    """Enable a plugin"""
    builtin = get_builtin_plugins()

    if name not in builtin:
        typer.secho(f"❌ '{name}' plugin not found.", fg=typer.colors.RED)
        typer.echo(f"   Available: {', '.join(builtin)}")
        raise typer.Exit(1)

    # Add to config
    config = ConfigManager().load()
    if "plugins" not in config:
        config["plugins"] = {"enabled": []}
    if name not in config["plugins"].get("enabled", []):
        config["plugins"]["enabled"].append(name)
        ConfigManager().save(config)
        typer.secho(f"✅ {name} plugin enabled.", fg=typer.colors.GREEN)
    else:
        typer.echo(f"   {name} is already enabled.")


@plugin_app.command("remove")
def remove_cmd(name: str):
    """Disable a plugin"""
    config = ConfigManager().load()
    enabled = config.get("plugins", {}).get("enabled", [])

    if name not in enabled:
        typer.secho(f"❌ '{name}' plugin is not enabled.", fg=typer.colors.RED)
        raise typer.Exit(1)

    config["plugins"]["enabled"].remove(name)
    ConfigManager().save(config)

    typer.secho(f"✅ {name} plugin disabled.", fg=typer.colors.GREEN)