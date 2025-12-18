import typer
from pathlib import Path

from ..core.config import ConfigManager, GLOBAL_PLUGINS_DIR
from ..plugins.registry import get_all_plugins

plugin_app = typer.Typer(help="Plugin management")


def _get_installed_plugins() -> set:
    """
    Get names of plugins that are actually installed (global + project).
    """
    installed = set()

    # Global plugins (tap-installed)
    if GLOBAL_PLUGINS_DIR.exists():
        for item in GLOBAL_PLUGINS_DIR.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                installed.add(item.name)

    # Project plugins
    project_dir = Path(".redgit/plugins")
    if project_dir.exists():
        for item in project_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                installed.add(item.name)

    return installed


@plugin_app.command("list")
def list_cmd(
    all_plugins: bool = typer.Option(False, "--all", "-a", help="Show all available plugins from taps")
):
    """List installed and enabled plugins"""
    installed = _get_installed_plugins()
    config = ConfigManager().load()
    enabled = config.get("plugins", {}).get("enabled", [])

    if not installed:
        typer.echo("\n📦 No plugins installed.\n")
        typer.echo("  💡 Install from taps: rg install plugin:<name>")
        typer.echo("  💡 Browse available: rg plugin list --all")
        typer.echo("")
    else:
        typer.echo("\n📦 Installed plugins:")
        for name in sorted(installed):
            status = "✓ enabled" if name in enabled else "○ disabled"
            typer.echo(f"   {name} ({status})")
        typer.echo("")

    # Show available from taps
    if all_plugins:
        from ..core.tap import TapManager

        tap_mgr = TapManager()
        tap_plugins = tap_mgr.get_all_plugins(include_installed=True)

        # Filter out already installed
        available = [p for p in tap_plugins if p.name not in installed and p.name.replace("-", "_") not in installed]

        if available:
            typer.echo("📥 Available from taps:")
            for plugin in sorted(available, key=lambda x: x.name):
                tap_label = f" ({plugin.tap_name})" if plugin.tap_name != "official" else ""
                typer.echo(f"   {plugin.name}{tap_label}")
                if plugin.description:
                    typer.echo(f"      {plugin.description[:60]}...")

            typer.echo("\n   💡 Install: rg install plugin:<name>")
        typer.echo("")
    else:
        typer.echo("  💡 Show all from taps: rg plugin list --all")
        typer.echo("")


def _enable_plugin(name: str):
    """Enable a plugin (internal function)"""
    installed = _get_installed_plugins()

    if name not in installed:
        typer.secho(f"❌ '{name}' plugin not installed.", fg=typer.colors.RED)
        if installed:
            typer.echo(f"   Installed: {', '.join(sorted(installed))}")
        typer.echo(f"   💡 Install first: rg install plugin:{name}")
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


def _disable_plugin(name: str):
    """Disable a plugin (internal function)"""
    config = ConfigManager().load()
    enabled = config.get("plugins", {}).get("enabled", [])

    if name not in enabled:
        typer.secho(f"❌ '{name}' plugin is not enabled.", fg=typer.colors.RED)
        raise typer.Exit(1)

    config["plugins"]["enabled"].remove(name)
    ConfigManager().save(config)

    typer.secho(f"✅ {name} plugin disabled.", fg=typer.colors.GREEN)


@plugin_app.command("add")
def add_cmd(name: str):
    """Enable a plugin"""
    _enable_plugin(name)


@plugin_app.command("enable")
def enable_cmd(name: str):
    """Enable a plugin (alias for 'add')"""
    _enable_plugin(name)


@plugin_app.command("remove")
def remove_cmd(name: str):
    """Disable a plugin"""
    _disable_plugin(name)


@plugin_app.command("disable")
def disable_cmd(name: str):
    """Disable a plugin (alias for 'remove')"""
    _disable_plugin(name)