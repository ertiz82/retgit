import shutil
import subprocess
import typer
from pathlib import Path

from ..core.config import ConfigManager, RETGIT_DIR
from ..core.llm import load_providers, check_provider_available
from ..plugins.registry import detect_project_type, get_builtin_plugins
from ..integrations.registry import get_builtin_integrations

# Package source directories
PACKAGE_DIR = Path(__file__).parent.parent
BUILTIN_PROMPTS_DIR = PACKAGE_DIR / "prompts"
BUILTIN_TEMPLATES_DIR = PACKAGE_DIR / "templates"


def get_builtin_prompts() -> list:
    """List builtin prompts from package"""
    if not BUILTIN_PROMPTS_DIR.exists():
        return []
    return [f.stem for f in BUILTIN_PROMPTS_DIR.glob("*.md")]


def copy_prompts() -> int:
    """Copy all builtin prompts to .redgit/prompts/"""
    if not BUILTIN_PROMPTS_DIR.exists():
        return 0

    dest_dir = RETGIT_DIR / "prompts"
    dest_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for src in BUILTIN_PROMPTS_DIR.glob("*.md"):
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        count += 1

    return count


def copy_quality_template() -> bool:
    """Copy quality prompt template to .redgit/templates/"""
    src = BUILTIN_TEMPLATES_DIR / "quality_prompt.md"
    if not src.exists():
        return False

    dest_dir = RETGIT_DIR / "templates"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / "quality_prompt.md"
    shutil.copy2(src, dest)
    return True


def select_llm_provider() -> tuple:
    """Interactive LLM provider selection. Returns (provider, model, api_key)"""
    providers = load_providers()

    typer.echo("\n🤖 LLM Provider Selection:")
    typer.echo("   Available providers:\n")

    # Group by type
    cli_providers = {k: v for k, v in providers.items() if v["type"] == "cli"}
    api_providers = {k: v for k, v in providers.items() if v["type"] == "api"}

    # Show CLI providers
    typer.echo("   CLI-based (runs locally):")
    for name, config in cli_providers.items():
        available = check_provider_available(name, config)
        status = "✓ installed" if available else "○ not installed"
        typer.echo(f"     [{name}] {config['name']} ({status})")

    # Show API providers
    typer.echo("\n   API-based (requires API key):")
    for name, config in api_providers.items():
        available = check_provider_available(name, config)
        if name == "ollama":
            status = "✓ installed" if available else "○ not installed"
        else:
            env_key = config.get("env_key", "")
            status = "✓ configured" if available else f"○ needs {env_key}"
        typer.echo(f"     [{name}] {config['name']} ({status})")

    typer.echo("")

    # Provider selection
    provider_choice = typer.prompt(
        "   Select provider",
        default="claude-code",
        show_choices=False
    )

    if provider_choice not in providers:
        typer.echo(f"   ⚠️  Unknown provider: {provider_choice}, using claude-code")
        provider_choice = "claude-code"

    provider_config = providers[provider_choice]
    selected_model = None
    api_key = None

    # Check if provider is available
    if not check_provider_available(provider_choice, provider_config):
        typer.echo(f"\n   ⚠️  {provider_config['name']} is not available.")

        if provider_config["type"] == "cli":
            install_cmd = provider_config.get("install", "")
            if typer.confirm(f"   Install now? ({install_cmd})", default=True):
                typer.echo(f"   Installing {provider_config['name']}...")
                try:
                    subprocess.run(install_cmd, shell=True, check=True)
                    typer.echo(f"   ✓ {provider_config['name']} installed successfully!")
                except subprocess.CalledProcessError:
                    typer.echo(f"   ✗ Installation failed. Please install manually:")
                    typer.echo(f"     {install_cmd}")

        elif provider_config["type"] == "api":
            env_key = provider_config.get("env_key")
            if env_key:
                typer.echo(f"   You need to set {env_key} environment variable.")
                if typer.confirm("   Enter API key now?", default=True):
                    api_key = typer.prompt(f"   {env_key}", hide_input=True)
                    typer.echo(f"   ✓ API key will be saved to config")
            else:
                install_cmd = provider_config.get("install", "")
                typer.echo(f"   Install: {install_cmd}")

    # Model selection
    models = provider_config.get("models", [])
    default_model = provider_config.get("default_model", models[0] if models else "")

    if models:
        typer.echo(f"\n   Available models: {', '.join(models)}")
        selected_model = typer.prompt(
            "   Select model",
            default=default_model
        )

    return provider_choice, selected_model, api_key


def select_plugins() -> list:
    """Interactive plugin selection. Returns list of selected plugin names."""
    available_plugins = get_builtin_plugins()

    if not available_plugins:
        return []

    detected = detect_project_type()

    typer.echo("\n🧩 Plugins:")
    typer.echo(f"   Available: {', '.join(available_plugins)}")

    if detected:
        typer.echo(f"   Detected: {', '.join(detected)}")

    if not typer.confirm("   Enable plugins?", default=bool(detected)):
        return []

    # Show available plugins
    typer.echo("\n   Enter plugin names separated by comma (or 'all' for all):")
    default_selection = ",".join(detected) if detected else ""
    selection = typer.prompt("   Plugins", default=default_selection)

    if not selection.strip():
        return []

    if selection.strip().lower() == "all":
        return available_plugins

    # Parse comma-separated list
    selected = []
    for name in selection.split(","):
        name = name.strip().lower()
        if name in available_plugins:
            selected.append(name)
        elif name:
            typer.echo(f"   ⚠️  Unknown plugin: {name}")

    return selected


def select_quality_settings() -> dict:
    """Interactive code quality settings. Returns quality config dict."""
    typer.echo("\n🔍 Code Quality:")

    if not typer.confirm("   Enable code quality checks before push?", default=False):
        return {"enabled": False}

    threshold = typer.prompt(
        "   Minimum quality score (0-100)",
        default="70",
        type=int
    )
    threshold = max(0, min(100, threshold))

    fail_on_security = typer.confirm(
        "   Always fail on critical security issues?",
        default=True
    )

    return {
        "enabled": True,
        "threshold": threshold,
        "fail_on_security": fail_on_security,
        "prompt_file": "quality_prompt.md"
    }


def select_integrations() -> list:
    """Interactive integration selection. Returns list of selected integration names."""
    available_integrations = get_builtin_integrations()

    if not available_integrations:
        return []

    typer.echo("\n🔌 Integrations:")
    typer.echo(f"   Available: {', '.join(available_integrations)}")

    if not typer.confirm("   Install integrations?", default=False):
        return []

    # Show available integrations
    typer.echo("\n   Enter integration names separated by comma:")
    selection = typer.prompt("   Integrations", default="")

    if not selection.strip():
        return []

    # Parse comma-separated list
    selected = []
    for name in selection.split(","):
        name = name.strip().lower()
        if name in available_integrations:
            selected.append(name)
        elif name:
            typer.echo(f"   ⚠️  Unknown integration: {name}")

    return selected


def init_cmd():
    """Initialize redgit configuration for this project."""
    config = {}

    typer.echo("\n🧠 redgit v1.0 setup wizard\n")

    # Project info
    config["project"] = {
        "name": typer.prompt("📌 Project name", default=Path(".").resolve().name),
    }

    # LLM selection
    provider, model, api_key = select_llm_provider()

    config["llm"] = {
        "provider": provider,
        "model": model,
        "prompt": "auto",
        "max_files": 100,
        "include_content": False,
        "timeout": 120
    }

    if api_key:
        config["llm"]["api_key"] = api_key

    # Plugin selection (optional, single line)
    selected_plugins = select_plugins()
    config["plugins"] = {"enabled": selected_plugins}

    # Integration selection (optional, single line)
    selected_integrations = select_integrations()
    config["integrations"] = {}

    # Code quality settings
    quality_config = select_quality_settings()
    config["quality"] = quality_config

    # Editor config
    config["editor"] = {"command": ["code", "--wait"]}

    # Create .redgit directory
    RETGIT_DIR.mkdir(parents=True, exist_ok=True)

    typer.echo("\n📁 Setting up:")

    # Copy prompts
    prompt_count = copy_prompts()
    if prompt_count > 0:
        typer.echo(f"   ✓ {prompt_count} prompt templates copied")

    # Copy quality template if enabled
    if quality_config.get("enabled"):
        if copy_quality_template():
            typer.echo("   ✓ Quality prompt template copied")

    # Save config
    ConfigManager().save(config)
    typer.echo(f"   ✓ Config saved")

    typer.echo("")
    typer.secho("✅ redgit v1.0 setup complete.", fg=typer.colors.GREEN)
    typer.echo(f"   📄 Config: .redgit/config.yaml")
    typer.echo(f"   📝 Prompts: .redgit/prompts/")
    typer.echo(f"   🤖 LLM: {provider} ({model})")

    if selected_plugins:
        typer.echo(f"   🧩 Plugins: {', '.join(selected_plugins)}")

    if quality_config.get("enabled"):
        typer.echo(f"   🔍 Quality: enabled (threshold: {quality_config.get('threshold', 70)})")

    # Install selected integrations
    if selected_integrations:
        typer.echo(f"\n🔌 Installing integrations...")
        from .integration import install_cmd as integration_install

        for integ_name in selected_integrations:
            try:
                integration_install(integ_name)
            except SystemExit:
                pass  # Continue with other integrations

    typer.echo("\n💡 Usage:")
    typer.echo("   redgit propose              # Auto-detect plugin prompt")
    typer.echo("   redgit propose -p laravel   # Use Laravel plugin prompt")
    typer.echo("   redgit propose -p minimal   # Use minimal prompt")
    typer.echo("")
    typer.echo("💡 Manage plugins/integrations:")
    typer.echo("   redgit plugin list")
    typer.echo("   redgit plugin add <name>")
    typer.echo("   redgit integration install <name>")