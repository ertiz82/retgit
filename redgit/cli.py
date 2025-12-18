from typing import Optional
import sys
import typer
from rich import print as rprint

from redgit import __version__
from redgit.splash import splash
from redgit.commands.init import init_cmd
from redgit.commands.propose import propose_cmd
from redgit.commands.push import push_cmd
from redgit.commands.integration import integration_app
from redgit.commands.plugin import plugin_app
from redgit.commands.tap import tap_app, install_cmd as tap_install_cmd, uninstall_cmd as tap_uninstall_cmd
from redgit.commands.notify import notify_app
from redgit.commands.ci import ci_app
from redgit.commands.config import config_app
from redgit.commands.quality import quality_app
from redgit.commands.scout import scout_app


def version_callback(value: bool):
    if value:
        rprint(f"[bold cyan]redgit[/bold cyan] version [green]{__version__}[/green]")
        raise typer.Exit()


app = typer.Typer(
    name="redgit",
    help="🧠 AI-powered Git workflow assistant with task management integration",
    no_args_is_help=True,
    rich_markup_mode="rich"
)


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
    )
):
    """RedGit - AI-powered Git workflow assistant"""
    pass


app.command("init")(init_cmd)
app.command("propose")(propose_cmd)
app.command("push")(push_cmd)
app.command("install")(tap_install_cmd)
app.command("uninstall")(tap_uninstall_cmd)
app.add_typer(integration_app, name="integration")
app.add_typer(plugin_app, name="plugin")
app.add_typer(tap_app, name="tap")
app.add_typer(notify_app, name="notify")
app.add_typer(ci_app, name="ci")
app.add_typer(config_app, name="config")
app.add_typer(quality_app, name="quality")
app.add_typer(scout_app, name="scout")


def _load_plugin_commands():
    """Dynamically load commands from enabled plugins."""
    try:
        from redgit.core.config import ConfigManager
        from redgit.plugins.registry import get_enabled_plugin_commands, get_all_plugin_shortcuts

        config = ConfigManager().load()

        # Load plugin typer apps (e.g., version_app, changelog_app)
        commands = get_enabled_plugin_commands(config)
        for name, cmd_app in commands.items():
            app.add_typer(cmd_app, name=name)

        # Load plugin shortcuts (e.g., release_shortcut -> rg release)
        shortcuts = get_all_plugin_shortcuts(config)
        for name, cmd_func in shortcuts.items():
            app.command(name)(cmd_func)

    except Exception:
        # Silently fail if config not found (e.g., before init)
        pass


def _load_integration_commands():
    """Dynamically load commands from active integrations."""
    try:
        from redgit.core.config import ConfigManager
        from redgit.integrations.registry import get_active_integration_commands

        config = ConfigManager().load()
        commands = get_active_integration_commands(config)

        for name, cmd_app in commands.items():
            app.add_typer(cmd_app, name=name)
    except Exception:
        # Silently fail if config not found (e.g., before init)
        pass


def main():
    # Load plugin and integration commands dynamically
    _load_plugin_commands()
    _load_integration_commands()

    # Show splash animation on first run (skip with --no-anim, --help, --version)
    skip_flags = ["--no-anim", "--help", "-h", "--version", "-v"]
    if not any(flag in sys.argv for flag in skip_flags):
        splash(total_duration=1.0)

    # Remove --no-anim from argv before typer processes it
    if "--no-anim" in sys.argv:
        sys.argv.remove("--no-anim")

    app()

if __name__ == "__main__":
    main()