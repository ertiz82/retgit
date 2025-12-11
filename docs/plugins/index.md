# Plugins

RedGit supports plugins for framework-specific features and extended functionality.

## Available Plugins

| Plugin | Type | Status | Documentation |
|--------|------|--------|---------------|
| Laravel | Framework | ✅ Available | [laravel.md](laravel.md) |
| Version | Release Management | ✅ Available | [version.md](version.md) |
| Changelog | Release Management | ✅ Available | [changelog.md](changelog.md) |

## Quick Start

### Check Active Plugins

```bash
rg plugin list
```

### Enable a Plugin

```bash
rg plugin enable laravel
```

### Disable a Plugin

```bash
rg plugin disable laravel
```

## Plugin Types

### Framework Plugins

Framework plugins provide intelligent file grouping and prompts for specific frameworks:

- **Laravel** - PHP Laravel framework support
- (Planned) Django, Rails, Next.js, etc.

### Release Management Plugins

These plugins help manage releases and versioning:

- **Version** - Semantic versioning with auto file updates
- **Changelog** - Automatic changelog generation

## Auto-Detection

Some plugins are automatically detected and activated:

| Plugin | Auto-Detected When |
|--------|-------------------|
| Laravel | `artisan` + `laravel/framework` in composer.json |

## Configuration

Plugins are configured in `.redgit/config.yaml`:

```yaml
plugins:
  laravel:
    enabled: true

  version:
    enabled: true
    current: "0.2.0"
    tag_prefix: "v"

  changelog:
    enabled: true
    output_dir: changelogs
    group_by_type: true
```

## Using Plugins

### Force a Specific Plugin

```bash
# Use Laravel plugin even if not auto-detected
rg propose -p laravel
```

### Version Plugin Commands

```bash
rg version init          # Initialize versioning
rg version show          # Show current version
rg version release patch # Bump patch version
rg release minor         # Shortcut for minor release
rg release major         # Shortcut for major release
rg release current       # Tag current version (no bump)
rg release patch --force # Replace existing tag
```

### Changelog Plugin Commands

```bash
rg changelog init        # Initialize changelog plugin
rg changelog generate    # Generate changelog
rg changelog show        # Show current changelog
```

---

## Detailed Documentation

### Framework Plugins

- **[Laravel Plugin](laravel.md)** - Intelligent Laravel file grouping, version detection, framework file identification

### Release Management Plugins

- **[Version Plugin](version.md)** - Semantic versioning, auto file updates, git tagging
- **[Changelog Plugin](changelog.md)** - Automatic changelog generation from commits

---

## Plugin Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Plugin Types                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Framework Plugins (auto-detection + prompts)               │
│  ├── LaravelPlugin                                          │
│  ├── DjangoPlugin (planned)                                 │
│  └── RailsPlugin (planned)                                  │
│                                                             │
│  Release Management Plugins (commands)                       │
│  ├── VersionPlugin                                          │
│  │   ├── rg version init                                    │
│  │   ├── rg version show                                    │
│  │   └── rg version release [patch|minor|major|current]     │
│  │                                                          │
│  └── ChangelogPlugin                                        │
│      ├── rg changelog init                                  │
│      ├── rg changelog generate                              │
│      └── rg changelog show                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Creating Custom Plugins

### Framework Plugin

```python
# redgit/plugins/django.py

from .base import Plugin

class DjangoPlugin(Plugin):
    name = "django"

    def match(self) -> bool:
        """Check if this is a Django project"""
        return Path("manage.py").exists() and Path("settings.py").exists()

    def get_prompt(self) -> str:
        """Return Django-specific prompt"""
        return """
        # Django Project Commit Grouping

        Group files by Django app and functionality:
        - Models with their migrations
        - Views with their templates
        - Admin configurations
        ...
        """
```

### Register Plugin

Add to `redgit/plugins/registry.py`:

```python
def get_builtin_plugins():
    return ["laravel", "django"]  # Add new plugin
```

---

## Best Practices

1. **Let plugins auto-detect** - Plugins will activate when appropriate
2. **Use version plugin for releases** - Keeps all version files in sync
3. **Generate changelogs for major releases** - Helps document changes
4. **Configure plugin-specific settings** - Each plugin has its own options

## See Also

- [Workflows](../workflows.md)
- [Integrations](../integrations/index.md)