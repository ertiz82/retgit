# Plugins

Plugins extend RedGit with framework-specific features and additional functionality like version management and changelog generation.

---

## Plugin Types

| Type                    | Purpose                              | Examples              |
|-------------------------|--------------------------------------|-----------------------|
| **Framework**           | Smart file grouping, custom prompts  | Laravel, Django       |
| **Release Management**  | Versioning, changelogs, git tags     | Version, Changelog    |

---

## How Plugins Work

1. **Auto-Detection** - Framework plugins detect project type automatically
2. **Enable/Disable** - Manually control which plugins are active
3. **Configure** - Set plugin-specific options in config
4. **Use** - Plugins enhance `rg propose` and add new commands

### Plugin Commands

```bash
# List installed and available plugins
rg plugin list
rg plugin list --all

# Enable/disable a plugin
rg plugin enable laravel
rg plugin disable laravel
```

---

## Installing Plugins

Plugins are available from [RedGit Tap](../tap.md):

```bash
# Install a plugin
rg install plugin:laravel
rg install plugin:django

# List available
rg plugin list --all
```

---

## Configuration

Plugins are configured in `.redgit/config.yaml`:

```yaml
plugins:
  enabled:
    - laravel
    - version
    - changelog

  # Plugin-specific settings
  version:
    current: "1.0.0"
    tag_prefix: "v"

  changelog:
    output_dir: changelogs
    group_by_type: true
```

---

## Built-in Plugins

### Version Plugin

Semantic versioning with automatic file updates and git tagging.

```bash
rg version init           # Initialize versioning
rg version show           # Show current version
rg release patch          # Bump patch (1.0.x)
rg release minor          # Bump minor (1.x.0)
rg release major          # Bump major (x.0.0)
```

### Changelog Plugin

Automatic changelog generation from commit history.

```bash
rg changelog init         # Initialize changelog
rg changelog generate     # Generate from commits
rg changelog show         # Show current changelog
```

---

## Creating Custom Plugins

You can create custom plugins for your framework or workflow. Place them in `.redgit/plugins/`:

```
.redgit/plugins/my-plugin/
├── __init__.py          # Plugin class (required)
└── prompt.md            # Custom prompt (optional)
```

See [Custom Plugin Guide](custom.md) for detailed instructions.

---

## See Also

- [RedGit Tap](../tap.md) - Browse and install plugins
- [Custom Plugins](custom.md) - Create your own
- [Configuration](../configuration.md) - Full config reference