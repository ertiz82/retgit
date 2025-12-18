 # Custom Plugins

Create your own plugins to add framework support or custom functionality to RedGit.

---

## Plugin Structure

Place custom plugins in `.redgit/plugins/`:

```
.redgit/plugins/my-plugin/
├── __init__.py          # Plugin class (required)
├── prompt.md            # Custom prompt (optional)
└── commands.py          # CLI commands (optional)
```

---

## Framework Plugin

Framework plugins provide auto-detection and custom prompts for `rg propose`.

### Basic Example

```python
# .redgit/plugins/django/__init__.py

from pathlib import Path

class DjangoPlugin:
    name = "django"

    def match(self) -> bool:
        """Auto-detect Django project"""
        return (
            Path("manage.py").exists() and
            Path("settings.py").exists()
        )

    def get_prompt(self) -> str:
        """Return Django-specific grouping prompt"""
        return """
        Group files by Django app and functionality:
        - Models with their migrations
        - Views with their templates and URLs
        - Admin configurations
        - Management commands
        - Tests with their fixtures
        """
```

### With Custom Prompt File

```python
# .redgit/plugins/django/__init__.py

from pathlib import Path

class DjangoPlugin:
    name = "django"
    prompt_file = "prompt.md"  # Load from .redgit/plugins/django/prompt.md

    def match(self) -> bool:
        return Path("manage.py").exists()
```

```markdown
<!-- .redgit/plugins/django/prompt.md -->

# Django Project Commit Grouping

Group changes by Django application structure:

## Grouping Rules
1. Models + migrations = single commit
2. Views + templates + URLs = single commit
3. Admin configurations separately
4. Tests with related code changes
```

---

## Command Plugin

Add custom CLI commands to RedGit.

```python
# .redgit/plugins/deploy/__init__.py

import typer

class DeployPlugin:
    name = "deploy"

    def get_commands(self):
        """Return typer app with commands"""
        app = typer.Typer()

        @app.command()
        def staging():
            """Deploy to staging"""
            typer.echo("Deploying to staging...")
            # Your deployment logic

        @app.command()
        def production():
            """Deploy to production"""
            typer.echo("Deploying to production...")

        return app
```

Usage:
```bash
rg deploy staging
rg deploy production
```

---

## Plugin with Configuration

Access plugin configuration from `.redgit/config.yaml`:

```python
# .redgit/plugins/myframework/__init__.py

class MyFrameworkPlugin:
    name = "myframework"

    def setup(self, config: dict):
        """Called with plugin config from config.yaml"""
        self.env = config.get("environment", "development")
        self.debug = config.get("debug", False)

    def match(self) -> bool:
        return Path("myframework.config").exists()
```

```yaml
# .redgit/config.yaml
plugins:
  enabled:
    - myframework

  myframework:
    environment: production
    debug: false
```

---

## Plugin Hooks

Plugins can hook into RedGit events:

```python
class MyPlugin:
    name = "myplugin"

    def on_propose_start(self, files: list):
        """Called before propose analysis"""
        pass

    def on_propose_end(self, groups: list):
        """Called after grouping, before commits"""
        pass

    def on_commit(self, branch: str, message: str, files: list):
        """Called after each commit"""
        pass

    def on_push(self, branch: str, remote: str):
        """Called after push"""
        pass
```

---

## Publishing to Tap

Share your plugin with the community:

1. Create a repository with your plugin
2. Add to [RedGit Tap](https://github.com/ertiz82/redgit-tap) index.json:

```json
{
  "plugins": {
    "django": {
      "name": "Django",
      "description": "Django framework support",
      "version": "1.0.0",
      "type": "framework",
      "author": "your-name",
      "repository": "https://github.com/you/redgit-plugin-django"
    }
  }
}
```

3. Submit a pull request

---

## See Also

- [Plugins Overview](index.md)
- [RedGit Tap](../tap.md) - Browse available plugins
- [Configuration](../configuration.md)