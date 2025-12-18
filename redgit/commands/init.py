import shutil
import subprocess
import typer
from pathlib import Path

from ..core.config import ConfigManager, RETGIT_DIR
from ..core.llm import load_providers, check_provider_available
from ..plugins.registry import detect_project_type, get_builtin_plugins

# Package source directories
PACKAGE_DIR = Path(__file__).parent.parent
BUILTIN_PROMPTS_DIR = PACKAGE_DIR / "prompts"

# New prompt structure: prompts/{category}/{name}.md
# Only copy commit prompts, quality prompts are internal
PROMPT_CATEGORIES = ["commit"]


def get_builtin_prompts() -> list:
    """List builtin prompts from package (commit prompts only)"""
    commit_dir = BUILTIN_PROMPTS_DIR / "commit"
    if not commit_dir.exists():
        return []
    return [f.stem for f in commit_dir.glob("*.md")]


def copy_prompts() -> int:
    """Copy all builtin prompts to .redgit/prompts/ preserving category structure"""
    if not BUILTIN_PROMPTS_DIR.exists():
        return 0

    count = 0
    for category in PROMPT_CATEGORIES:
        src_dir = BUILTIN_PROMPTS_DIR / category
        if not src_dir.exists():
            continue

        dest_dir = RETGIT_DIR / "prompts" / category
        dest_dir.mkdir(parents=True, exist_ok=True)

        for src in src_dir.glob("*.md"):
            dest = dest_dir / src.name
            shutil.copy2(src, dest)
            count += 1

    return count


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
                    typer.echo("   ✗ Installation failed. Please install manually:")
                    typer.echo(f"     {install_cmd}")

        elif provider_config["type"] == "api":
            env_key = provider_config.get("env_key")
            if env_key:
                typer.echo(f"   You need to set {env_key} environment variable.")
                if typer.confirm("   Enter API key now?", default=True):
                    api_key = typer.prompt(f"   {env_key}", hide_input=True)
                    typer.echo("   ✓ API key will be saved to config")
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


def check_semgrep_installed() -> bool:
    """Check if Semgrep is installed."""
    try:
        result = subprocess.run(
            ["semgrep", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_semgrep() -> bool:
    """Install Semgrep using pip."""
    typer.echo("   Installing Semgrep...")
    try:
        subprocess.run(
            ["pip", "install", "semgrep"],
            check=True,
            capture_output=True
        )
        typer.echo("   ✓ Semgrep installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        typer.echo(f"   ✗ Installation failed: {e}")
        typer.echo("   Try manually: pip install semgrep")
        return False


def select_semgrep_settings() -> dict:
    """Interactive Semgrep settings. Returns semgrep config dict."""
    typer.echo("\n🔬 Semgrep (Multi-language Static Analysis):")
    typer.echo("   Supports 35+ languages: Python, JS, TS, Go, Java, PHP, Ruby, C#, etc.")

    if not typer.confirm("   Enable Semgrep analysis?", default=False):
        return {"enabled": False}

    # Check if Semgrep is installed
    if not check_semgrep_installed():
        typer.echo("\n   ⚠️  Semgrep is not installed.")
        if typer.confirm("   Install Semgrep now?", default=True):
            if not install_semgrep():
                typer.echo("   Semgrep will be disabled until installed.")
                return {"enabled": False}
        else:
            typer.echo("   Semgrep will be disabled until installed.")
            typer.echo("   Install later: pip install semgrep")
            return {"enabled": False}

    # Select rule configs
    typer.echo("\n   Available rule packs:")
    typer.echo("     [auto]            - Auto-detect based on project")
    typer.echo("     [p/security-audit] - Security vulnerabilities")
    typer.echo("     [p/python]        - Python best practices")
    typer.echo("     [p/javascript]    - JavaScript/TypeScript rules")
    typer.echo("     [p/golang]        - Go rules")
    typer.echo("     [p/php]           - PHP rules")
    typer.echo("     [p/java]          - Java rules")
    typer.echo("     [p/owasp-top-ten] - OWASP Top 10")

    configs_input = typer.prompt(
        "   Rule packs (comma-separated)",
        default="auto"
    )

    configs = [c.strip() for c in configs_input.split(",") if c.strip()]
    if not configs:
        configs = ["auto"]

    return {
        "enabled": True,
        "configs": configs,
        "severity": ["ERROR", "WARNING"],
        "exclude": [],
        "timeout": 300
    }


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
    config["integrations"] = {}

    # Code quality settings
    quality_config = select_quality_settings()
    config["quality"] = quality_config

    # Semgrep settings (only ask if quality is enabled)
    if quality_config.get("enabled"):
        semgrep_config = select_semgrep_settings()
    else:
        semgrep_config = {"enabled": False}
    config["semgrep"] = semgrep_config

    # Editor config
    config["editor"] = {"command": ["code", "--wait"]}

    # Create .redgit directory
    RETGIT_DIR.mkdir(parents=True, exist_ok=True)

    typer.echo("\n📁 Setting up:")

    # Copy prompts (commit and quality categories)
    prompt_count = copy_prompts()
    if prompt_count > 0:
        typer.echo(f"   ✓ {prompt_count} prompt templates copied")

    # Save config
    ConfigManager().save(config)
    typer.echo("   ✓ Config saved")

    typer.echo("")
    typer.secho("✅ redgit v1.0 setup complete.", fg=typer.colors.GREEN)
    typer.echo("   📄 Config: .redgit/config.yaml")
    typer.echo("   📝 Prompts: .redgit/prompts/")
    typer.echo(f"   🤖 LLM: {provider} ({model})")

    if selected_plugins:
        typer.echo(f"   🧩 Plugins: {', '.join(selected_plugins)}")

    if quality_config.get("enabled"):
        typer.echo(f"   🔍 Quality: enabled (threshold: {quality_config.get('threshold', 70)})")

    if semgrep_config.get("enabled"):
        configs_str = ", ".join(semgrep_config.get("configs", ["auto"]))
        typer.echo(f"   🔬 Semgrep: enabled ({configs_str})")

    typer.echo("\n💡 Usage:")
    typer.echo("   rg propose    # Generate commit messages")
    typer.echo("   rg push       # Push with task management integration")
    typer.echo("   rg scout      # AI-powered project analysis")

    typer.echo("\n📦 Extend with plugins & integrations:")
    typer.echo("   rg install jira              # Task management")
    typer.echo("   rg install slack             # Notifications")
    typer.echo("   rg install plugin:laravel    # Framework plugin")
    typer.echo("")
    typer.echo("   Browse all: https://github.com/ertiz82/redgit-tap")