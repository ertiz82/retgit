# Commands Reference

Complete reference for all RedGit CLI commands. You can use either `redgit` or the short alias `rg`.

---

## Core Commands

### `rg init`

Initialize RedGit in your project. Creates `.redgit/config.yaml`.

```bash
rg init
```

Interactive wizard configures:
- LLM provider selection
- Task management integration
- Plugins
- Workflow settings

### `rg propose`

Analyze changes and create commits.

```bash
# Basic usage - AI analyzes and groups changes
rg propose

# With specific prompt/plugin
rg propose -p laravel

# Skip task management
rg propose --no-task

# Link all changes to a specific task (single commit)
rg propose --task 123
rg propose -t PROJ-123
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--prompt` | `-p` | Use specific prompt or plugin |
| `--task` | `-t` | Link all changes to specific task |
| `--no-task` | | Skip task management integration |
| `--verbose` | `-v` | Show detailed output |

### `rg push`

Push branches and complete issues.

```bash
# Push current branch
rg push

# Push with specific issue
rg push -i PROJ-123

# Create pull request
rg push --pr

# Don't complete issues
rg push --no-complete

# Trigger CI/CD pipeline after push
rg push --ci

# Wait for CI/CD pipeline to complete
rg push --ci --wait-ci

# Push without triggering CI
rg push --no-ci
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--issue` | `-i` | Complete specific issue |
| `--pr` | | Create pull request |
| `--no-complete` | | Don't transition issues to Done |
| `--ci` | | Trigger CI/CD pipeline |
| `--wait-ci` | | Wait for CI/CD to complete |
| `--no-ci` | | Skip CI/CD trigger |

---

## Integration Commands

### `rg integration`

Manage integrations.

```bash
# List available integrations
rg integration list

# Install an integration
rg integration install jira
rg integration install github

# Show integration status
rg integration status

# Remove an integration
rg integration remove jira
```

### `rg install`

Install integration from RedGit Tap.

```bash
# Install from tap
rg install slack
rg install linear
rg install sonarqube

# Install specific version
rg install slack@v1.0.0
```

---

## Plugin Commands

### `rg plugin`

Manage plugins.

```bash
# List available plugins
rg plugin list

# Enable a plugin
rg plugin enable laravel

# Disable a plugin
rg plugin disable laravel
```

---

## Version & Release Commands

### `rg version`

Manage semantic versioning.

```bash
rg version init          # Initialize versioning
rg version show          # Show current version
rg version release patch # Bump patch version
```

### `rg release`

Shortcut for version releases.

```bash
rg release patch         # Bump patch (0.0.x)
rg release minor         # Bump minor (0.x.0)
rg release major         # Bump major (x.0.0)
rg release current       # Tag current version (no bump)
rg release patch --force # Replace existing tag
```

### `rg changelog`

Manage changelog generation.

```bash
rg changelog init        # Initialize changelog plugin
rg changelog generate    # Generate changelog
rg changelog show        # Show current changelog
```

---

## CI/CD Commands

### `rg ci`

CI/CD pipeline management.

```bash
# Show CI/CD status
rg ci status

# List recent pipelines
rg ci pipelines
rg ci pipelines --branch main --limit 20
rg ci pipelines --status failed

# Show pipeline details
rg ci pipeline 12345

# List jobs in a pipeline
rg ci jobs 12345

# Trigger a new pipeline
rg ci trigger
rg ci trigger --branch main --workflow build

# Watch a pipeline until completion
rg ci watch 12345
rg ci watch              # Watch latest on current branch

# Cancel/retry a pipeline
rg ci cancel 12345
rg ci retry 12345

# View pipeline logs
rg ci logs 12345
rg ci logs 12345 --job build --tail 100
```

---

## Quality Check Commands

### `rg quality`

Code quality checks with AI + linter integration.

```bash
# Check staged changes
rg quality check

# Check specific commit
rg quality check --commit HEAD

# Check branch against main
rg quality check --branch feature/my-feature

# Verbose output
rg quality check -v
```

---

## Configuration Commands

### `rg config`

Manage configuration.

```bash
# Show current config
rg config show

# Set a value
rg config set llm.provider ollama
rg config set workflow.strategy merge-request

# Get a value
rg config get llm.provider
```

---

## Notification Commands

### `rg notify`

Send custom notifications (requires notification integration).

```bash
rg notify "Deployment complete!"
rg notify "Build #123 passed" --channel "#builds"
```

---

## Global Options

These options work with most commands:

| Option | Short | Description |
|--------|-------|-------------|
| `--help` | `-h` | Show help message |
| `--version` | | Show version |
| `--verbose` | `-v` | Verbose output |
| `--quiet` | `-q` | Minimal output |
| `--config` | `-c` | Use custom config file |

---

## Examples

### Daily Workflow

```bash
# Start your day
cd my-project
rg integration status    # Check integrations

# Make changes...

# Commit with AI grouping
rg propose

# Push when ready
rg push
```

### Team Workflow with PRs

```bash
# Configure merge-request strategy
rg config set workflow.strategy merge-request

# Make changes...
rg propose

# Push and create PRs
rg push --pr
```

### Quick Commit to Specific Task

```bash
# All changes go to one task
rg propose --task PROJ-123
rg push
```

### Release Workflow

```bash
# Bump version and tag
rg release minor

# Generate changelog
rg changelog generate

# Push with CI
rg push --ci --wait-ci
```

---

## See Also

- [Getting Started](getting-started.md)
- [Configuration](configuration.md)
- [Workflows](workflows.md)