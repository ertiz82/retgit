# Version Plugin

Semantic versioning management for projects with automatic file updates and git tagging.

## Overview

The Version plugin provides:
- Semantic versioning (major.minor.patch)
- Automatic version file detection and updates
- Git tag creation
- Integration with Changelog plugin for major releases

## Installation

The plugin is built-in and ready to use. Initialize with:

```bash
rg version init
```

## Commands

### Initialize Version

```bash
rg version init
```

Interactive setup:
```
Version Plugin Setup

Detected version 0.1.0 from pyproject.toml
Starting version (x.x.x format) [0.1.0]:
Git tag prefix [v]:

✓ Version plugin initialized at 0.1.0
```

### Show Current Version

```bash
rg version show
```

Output:
```
Current version: 0.1.15

Version files:
  - pyproject.toml
  - redgit/__init__.py
```

### Release New Version

```bash
# Bump patch version: 0.1.0 -> 0.1.1
rg version release patch
# or shortcut:
rg release patch

# Bump minor version: 0.1.0 -> 0.2.0
rg version release minor
# or shortcut:
rg release minor

# Bump major version: 0.1.0 -> 1.0.0
rg version release major
# or shortcut:
rg release major

# Tag current version without bumping
rg release current
```

### Release Current Version

Tag the current version without bumping. Useful when:
- Version files were updated manually
- Re-releasing after a failed push
- Creating a tag for an existing version

```bash
rg release current
```

Output:
```
Release current: 0.2.6 (no version bump)

Release v0.2.6? [y/n]: y

Skipping version file updates (current level)

Creating git tag...
  ✓ Tag created: v0.2.6

┌─────────────────────────────────┐
│ Released v0.2.6                 │
│                                 │
│ Run `rg push` to push the       │
│ release and tags to remote.     │
└─────────────────────────────────┘
```

### Force Replace Existing Tag

If a tag already exists, use `--force` to replace it:

```bash
rg release patch --force
# or for current version:
rg release current --force
```

This will:
1. Delete the existing local tag
2. Delete the existing remote tag (if exists)
3. Create a new tag

### Dry Run

Preview changes without making them:

```bash
rg release minor --dry-run
```

Output:
```
Release minor: 0.1.15 → 0.2.0

Dry run - no changes made

Would update:
  - pyproject.toml
  - redgit/__init__.py

Would create tag: v0.2.0
Would generate changelog for 0.2.0
```

## Configuration

```yaml
# .redgit/config.yaml
plugins:
  version:
    enabled: true
    current: "0.2.0"
    tag_prefix: "v"        # Git tag prefix (v0.2.0)
    auto_tag: true         # Create tag on release
    auto_commit: true      # Commit version changes
```

## Supported Version Files

The plugin automatically detects and updates:

| File | Pattern |
|------|---------|
| `pyproject.toml` | `version = "x.x.x"` |
| `package.json` | `"version": "x.x.x"` |
| `composer.json` | `"version": "x.x.x"` |
| `setup.py` | `version="x.x.x"` |
| `version.txt` | `x.x.x` |
| `VERSION` | `x.x.x` |
| `*/__init__.py` | `__version__ = "x.x.x"` |

## Release Workflow

When you run `rg release major`:

```
1. Version bump: 0.1.15 → 1.0.0

2. Updating version files...
   ✓ pyproject.toml
   ✓ package.json
   ✓ src/__init__.py
   ✓ .redgit/config.yaml

3. Generating changelog...
   ✓ Created changelogs/v1.0.0.md
   ✓ Updated CHANGELOG.md

4. Creating release commit...
   ✓ Committed: chore(release): v1.0.0

5. Creating git tag...
   ✓ Tag created: v1.0.0

┌─────────────────────────────────┐
│ Released v1.0.0                 │
│                                 │
│ Run `rg push` to push the       │
│ release and tags to remote.     │
└─────────────────────────────────┘
```

## Changelog Integration

For **major** releases, the plugin automatically:
1. Checks if Changelog plugin is enabled
2. Generates changelog from commits since last major version
3. Creates `changelogs/vX.0.0.md`
4. Updates `CHANGELOG.md`

To skip changelog:
```bash
rg release major --no-changelog
```

## Pushing Releases

After release, push branch and tags:

```bash
rg push
```

Output:
```
📤 Pushing current branch: main
✓ Pushed to origin/main

🏷️  Pushing 1 tag(s)...
  • v1.0.0
✓ Tags pushed

✅ Push complete!
```

## Semantic Versioning

The plugin follows [SemVer](https://semver.org/):

| Release | When to use |
|---------|-------------|
| `patch` | Bug fixes, small changes (0.1.0 → 0.1.1) |
| `minor` | New features, backwards compatible (0.1.1 → 0.2.0) |
| `major` | Breaking changes (0.2.0 → 1.0.0) |

## Examples

### Python Project

```bash
# pyproject.toml + __init__.py
rg version init
# Detected version 0.1.0 from pyproject.toml

rg release minor
# Updates: pyproject.toml, src/__init__.py
# Creates: v0.2.0 tag
```

### Node.js Project

```bash
# package.json
rg version init
# Detected version 1.0.0 from package.json

rg release patch
# Updates: package.json
# Creates: v1.0.1 tag
```

### PHP/Laravel Project

```bash
# composer.json
rg version init
# Detected version 2.1.0 from composer.json

rg release major
# Updates: composer.json
# Creates: v3.0.0 tag
# Generates: CHANGELOG.md
```

## Troubleshooting

### "No version configured"

Run initialization first:
```bash
rg version init
```

### "No version files found"

Create a version file or specify version manually:
```bash
echo "0.1.0" > version.txt
rg version init
```

### Tag Already Exists

Use the `--force` flag to replace an existing tag:
```bash
rg release patch --force
```

Or manually delete and recreate:
```bash
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0
rg release major
```

## See Also

- [Plugins Overview](../plugins.md)
- [Changelog Plugin](changelog.md)
- [Workflow Strategies](../workflow-strategies.md)