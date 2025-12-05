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
from redgit.plugins.version.commands import version_app, release_shortcut
from redgit.plugins.changelog.commands import changelog_app


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
app.add_typer(integration_app, name="integration")
app.add_typer(plugin_app, name="plugin")

# Version and Changelog plugins
app.add_typer(version_app, name="version")
app.add_typer(changelog_app, name="changelog")

# Shortcut: rg release = rg version release
app.command("release")(release_shortcut)


def main():
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