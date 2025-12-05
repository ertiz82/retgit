# Changelog Plugin

Automatic changelog generation from git commits with conventional commit support.

## Overview

The Changelog plugin provides:
- Automatic changelog generation from git history
- Conventional commit parsing and grouping
- Version-specific changelog files
- Main CHANGELOG.md management
- Integration with Version plugin

## Installation

The plugin is built-in. Initialize with:

```bash
rg changelog init
```

## Commands

### Initialize Changelog

```bash
rg changelog init
```

Output:
```
Changelog Plugin Setup

✓ Changelog plugin enabled
Changelogs will be saved to: changelogs/
```

### Generate Changelog

```bash
# Generate for current version
rg changelog generate

# Generate for specific version
rg changelog generate 1.0.0

# Generate from specific tag
rg changelog generate --from v0.9.0
```

### Show Changelog

```bash
# Show main CHANGELOG.md
rg changelog show

# Show specific version
rg changelog show v1.0.0
```

## Configuration

```yaml
# .redgit/config.yaml
plugins:
  changelog:
    enabled: true
    format: markdown      # Output format
    output_dir: changelogs  # Version-specific files
    group_by_type: true   # Group by commit type
```

## Output Files

The plugin creates two types of files:

### Version-Specific Files

Location: `changelogs/v{version}.md`

Example `changelogs/v1.0.0.md`:
```markdown
# 1.0.0

**Release Date:** 2024-01-15
**Previous Version:** v0.9.0
**Commits:** 42

---

## ✨ Features

- **auth:** add user authentication (`abc1234`)
- **api:** add REST endpoints (`def5678`)

## 🐛 Bug Fixes

- **ui:** fix button alignment (`ghi9012`)
- fix memory leak in worker (`jkl3456`)

## ♻️ Refactoring

- **core:** simplify config loading (`mno7890`)
```

### Main CHANGELOG.md

Location: `CHANGELOG.md` (project root)

New versions are prepended to the top:

```markdown
# Changelog

# 1.0.0

**Release Date:** 2024-01-15
...

---

# 0.9.0

**Release Date:** 2024-01-01
...
```

## Commit Type Grouping

Commits are grouped by conventional commit type:

| Type | Display | Emoji |
|------|---------|-------|
| `feat` | Features | ✨ |
| `fix` | Bug Fixes | 🐛 |
| `perf` | Performance | ⚡ |
| `refactor` | Refactoring | ♻️ |
| `docs` | Documentation | 📚 |
| `test` | Tests | 🧪 |
| `chore` | Chores | 🔧 |
| `style` | Styles | 💄 |
| `ci` | CI/CD | 👷 |
| `build` | Build | 📦 |
| `other` | Other | 📝 |

## Conventional Commits

The plugin parses conventional commit format:

```
type(scope): message

body (optional)
```

Examples:
```bash
feat(auth): add login endpoint
fix(ui): correct button color
refactor: simplify database queries
docs(readme): update installation guide
```

Non-conventional commits are grouped under "Other":
```bash
Update dependencies
Fix typo
```

## Integration with Version Plugin

When you run `rg release major`:

1. Version plugin bumps version
2. Changelog plugin automatically generates changelog
3. Both files are committed together

To skip changelog generation:
```bash
rg release major --no-changelog
```

## Usage Examples

### Generate After Manual Release

```bash
# Tag your release first
git tag v1.0.0

# Generate changelog
rg changelog generate 1.0.0 --from v0.9.0
```

### Generate Full History

```bash
# Generate from beginning of project
rg changelog generate 1.0.0
```

### Preview Changelog

```bash
# See what would be generated
rg changelog generate --dry-run
```

## Commit Parsing

### With Scope

```
feat(auth): add OAuth support
     ^^^^  ^^^^^^^^^^^^^^^^^
     scope message
```

Result: `- **auth:** add OAuth support`

### Without Scope

```
fix: resolve memory leak
     ^^^^^^^^^^^^^^^^^^^
     message
```

Result: `- resolve memory leak`

### With Body

```
feat: add user dashboard

- Add analytics widgets
- Add activity feed
- Add notification center
```

Body is currently not included in changelog (only first line).

## Best Practices

### 1. Use Conventional Commits

```bash
# Good
git commit -m "feat(api): add user endpoint"
git commit -m "fix(auth): resolve token expiry"

# Bad
git commit -m "added stuff"
git commit -m "fix"
```

### 2. Include Scope for Context

```bash
# Better changelog grouping
feat(auth): add login
feat(auth): add logout
feat(api): add users endpoint
```

### 3. Generate Before Release

```bash
# Preview changes
rg changelog generate --dry-run

# Then release
rg release major
```

## Troubleshooting

### "No commits found"

1. Check the from/to range:
   ```bash
   git log v0.9.0..HEAD --oneline
   ```

2. Ensure tags exist:
   ```bash
   git tag
   ```

### Commits Not Grouped Correctly

1. Ensure commits follow conventional format
2. Check for typos in type (e.g., `feat` not `feature`)

### Changelog Not Generated on Release

1. Ensure changelog plugin is enabled:
   ```yaml
   plugins:
     changelog:
       enabled: true
   ```

2. Changelog is only auto-generated for `major` releases

## See Also

- [Plugins Overview](../plugins.md)
- [Version Plugin](version.md)
- [Conventional Commits](https://www.conventionalcommits.org/)