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

# Task-Filtered Mode: Smart subtask creation under parent task
rg propose -t PROJ-123
rg propose --task 858

# Auto-detect task from branch name (if on feature/PROJ-123-xxx branch)
rg propose
# → "Branch'ten task tespit edildi: PROJ-123"
# → "Task-filtered mode ile devam edilsin mi?"

# Dry-run: See what would happen without making changes
rg propose --dry-run
rg propose -n

# Verbose mode: Show prompts, AI responses, and debug info
rg propose --verbose
rg propose -v

# Detailed mode: Generate better messages using file diffs
rg propose --detailed
rg propose -d

# Combine flags for debugging
rg propose -v -n -d
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--prompt` | `-p` | Use specific prompt or plugin |
| `--task` | `-t` | Task-filtered mode: create subtasks under parent task |
| `--no-task` | | Skip task management integration |
| `--dry-run` | `-n` | Analyze without making changes (preview mode) |
| `--verbose` | `-v` | Show detailed output (prompts, responses, debug) |
| `--detailed` | `-d` | Generate detailed messages using file diffs |

#### Dry-Run Mode (`--dry-run`, `-n`)

Preview what RedGit would do without making any changes:

```bash
rg propose -n
```

Shows:
- How changes would be grouped
- Which issues would be matched or created
- Branch names that would be created
- No commits, branches, or issues are actually created

#### Verbose Mode (`--verbose`, `-v`)

Show detailed information about the AI analysis process:

```bash
rg propose -v
```

Displays:
- **Config paths**: Which config files are being used
- **Task Management Config**: Integration name, issue language, project key
- **Prompt Sources**: Which prompt files are being used (user vs builtin)
- **Full AI Prompt**: The complete prompt sent to the LLM
- **Raw AI Response**: The unprocessed response from the LLM
- **Parsed Groups**: How the response was interpreted

This is invaluable for debugging prompt issues or understanding AI decisions.

#### Detailed Mode (`--detailed`, `-d`)

Generate more accurate commit messages by analyzing actual file diffs:

```bash
rg propose -d
```

How it works:
1. Initial analysis groups files by semantic similarity
2. For each group, file diffs are sent to LLM
3. LLM generates detailed `commit_title`, `commit_body`, `issue_title`, `issue_description`
4. If integration has custom prompts, they're used for issue content

Benefits:
- More accurate commit messages based on actual code changes
- Better issue descriptions with technical details
- Localized issue titles/descriptions (respects `issue_language` setting)

Note: Detailed mode is slower as it makes additional LLM calls per group.

#### Task-Filtered Mode (`--task`, `-t`)

Smart subtask creation mode that analyzes file relevance to a parent task:

```bash
# Explicit task ID
rg propose -t PROJ-123

# Just the number (project key added automatically)
rg propose -t 123
```

**How it works:**

1. **Fetches parent task** details from task management (Jira, Linear, etc.)
2. **Analyzes file relevance** using AI to determine which files relate to the parent task
3. **Creates subtasks** only for related files under the parent task
4. **Matches other files** to user's other open tasks
5. **Reports unmatched files** and leaves them in working directory
6. **Asks about pushing** parent branch after subtasks are processed
7. **Returns to original branch** - always returns to the starting branch

**Branch hierarchy:**

```
Original Branch (dev)
    ↓
Parent Branch (feature/PROJ-123-parent-task)
    ↓
Subtask Branch 1 (feature/PROJ-456-subtask-1) → merge to parent
    ↓
Subtask Branch 2 (feature/PROJ-457-subtask-2) → merge to parent
    ↓
Ask: "Push parent branch?"
    ↓
Return to Original Branch (dev)
```

**Auto-detection from branch:**

When you're on a task branch (e.g., `feature/PROJ-123-some-work`), running `rg propose` without `-t` will:

1. Detect the task ID from the branch name
2. Ask if you want to use task-filtered mode
3. If confirmed, proceed with subtask creation

```bash
# On branch: feature/SCRUM-858-admin-panel
$ rg propose

# Output:
# Branch'ten task tespit edildi: SCRUM-858
# Task-filtered mode ile devam edilsin mi? [Y/n]
```

**Example workflow:**

```bash
# Working on dev branch
git checkout dev

# Make changes to multiple files
vim src/admin/users.py
vim src/admin/settings.py
vim src/api/auth.py

# Create subtasks under SCRUM-858
rg propose -t SCRUM-858

# Output:
# ✓ Parent task: SCRUM-858 - Admin panel improvements
#
# Analysis Results:
#   ✓ 2 subtask(s) for SCRUM-858
#   → 1 group(s) match other tasks
#   ○ 0 file(s) unmatched
#
# Creating subtasks under SCRUM-858...
#   Subtask 1: Admin user management
#   Subtask 2: Admin settings page
#
# ✓ Tüm subtask'lar SCRUM-858 parent branch'ine merge edildi.
# Parent branch'i pushlamak istiyor musunuz? [y/N]
#
# ✓ dev branch'ine dönüldü
```

#### Combining Flags

```bash
# Full debug mode: verbose + dry-run + detailed
rg propose -v -n -d
```

This shows the complete analysis without making changes - perfect for:
- Debugging integration prompts
- Verifying `issue_language` is working
- Understanding how files are grouped
- Testing custom prompts

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

## Scout Command (AI Project Analysis)

### `rg scout`

AI-powered project analysis and task planning. Scout is a core feature that helps you understand your codebase, plan tasks, and generate implementation strategies.

```bash
# Analyze project and suggest tasks
rg scout

# Analyze with specific depth
rg scout --depth detailed

# Analyze specific directory
rg scout src/

# Generate task breakdown for a feature
rg scout --feature "add user authentication"

# Output as JSON
rg scout --format json -o analysis.json
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--depth` | `-d` | Analysis depth: quick, normal, detailed |
| `--feature` | `-f` | Analyze specific feature or task |
| `--format` | | Output format: text, json, markdown |
| `--output` | `-o` | Save analysis to file |
| `--max-files` | | Maximum files to analyze |

**Example Output:**

```
🔍 Project Analysis: my-project

📊 Structure:
   - 45 source files
   - 12 test files
   - Primary language: Python

🎯 Suggested Tasks:
   1. Add input validation to user forms
   2. Implement caching for API responses
   3. Add unit tests for auth module

📝 Implementation Notes:
   - Consider using Pydantic for validation
   - Redis recommended for caching layer
```

---

## Integration Commands

### `rg install`

Install integration or plugin from RedGit Tap. Downloads, configures, and activates in one step.

```bash
# Install integration from official tap
rg install jira
rg install slack
rg install github

# Install plugin from official tap
rg install plugin:laravel
rg install plugin:changelog

# Install specific version
rg install slack@v1.0.0

# Install from custom tap (auto-adds tap first)
rg install myorg/my-tap jira
rg install myorg/my-tap plugin:myplugin

# Skip configuration wizard
rg install slack --no-configure
```

### `rg integration`

Manage installed integrations.

```bash
# List installed integrations
rg integration list

# List all available from taps
rg integration list --all

# Reconfigure an integration
rg integration config jira

# Set active integration for its type
rg integration use linear

# Remove an integration
rg integration remove jira
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

> **Requires:** `version` plugin enabled (`rg plugin enable version`)

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

---

## Changelog Commands

> **Requires:** `changelog` plugin enabled (`rg plugin enable changelog`)

### `rg changelog`

Automatic changelog generation from commit history.

```bash
rg changelog init        # Initialize changelog plugin
rg changelog generate    # Generate changelog from commits
rg changelog show        # Show current changelog
```

---

## CI/CD Commands

> **Requires:** CI/CD integration installed (e.g., `rg install github-actions`)

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

Code quality checks with AI + linter + Semgrep integration.

```bash
# Check staged changes
rg quality check

# Check specific commit
rg quality check --commit HEAD

# Check branch against main
rg quality check --branch feature/my-feature

# Verbose output
rg quality check -v

# Show quality settings status
rg quality status

# Generate quality report
rg quality report --format json -o report.json
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--commit` | `-c` | Analyze specific commit |
| `--branch` | `-b` | Compare branch with main |
| `--threshold` | `-t` | Quality threshold (0-100) |
| `--verbose` | `-v` | Show detailed output |
| `--output` | `-o` | Save report to file |
| `--format` | `-f` | Output format: text, json |

### `rg quality scan`

Scan entire project with Semgrep (not just git changes). Useful for full project audits.

```bash
# Scan current directory
rg quality scan

# Scan specific directory
rg quality scan src/

# Use specific rule pack
rg quality scan -c p/security-audit

# Export as JSON
rg quality scan -o report.json -f json

# Filter by severity
rg quality scan -s ERROR,WARNING

# Verbose output with suggestions
rg quality scan -v
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--config` | `-c` | Semgrep config (e.g., auto, p/security-audit) |
| `--severity` | `-s` | Minimum severity: ERROR, WARNING, INFO |
| `--output` | `-o` | Save report to file |
| `--format` | `-f` | Output format: text, json |
| `--verbose` | `-v` | Show detailed output with suggestions |

---

## Semgrep Commands

### `rg config semgrep`

Configure Semgrep multi-language static analysis (35+ languages).

```bash
# Show Semgrep settings
rg config semgrep

# Enable Semgrep (installs if needed)
rg config semgrep --enable

# Disable Semgrep
rg config semgrep --disable

# Install Semgrep
rg config semgrep --install

# Add rule packs
rg config semgrep --add p/security-audit
rg config semgrep --add p/php
rg config semgrep --add p/javascript

# Remove rule pack
rg config semgrep --remove auto

# List available rule packs
rg config semgrep --list-rules
```

**Available Rule Packs:**

| Pack | Description |
|------|-------------|
| `auto` | Auto-detect based on project |
| `p/security-audit` | Security vulnerabilities |
| `p/owasp-top-ten` | OWASP Top 10 |
| `p/python` | Python best practices |
| `p/javascript` | JavaScript/TypeScript |
| `p/php` | PHP rules |
| `p/golang` | Go rules |
| `p/java` | Java rules |
| `p/ruby` | Ruby rules |
| `p/rust` | Rust rules |
| `p/csharp` | C# rules |
| `p/kotlin` | Kotlin rules |
| `p/swift` | Swift rules |
| `p/docker` | Dockerfile rules |
| `p/terraform` | Terraform/HCL rules |

See more at: https://semgrep.dev/explore

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

> **Requires:** Notification integration installed (e.g., `rg install slack`)

### `rg notify`

Send custom notifications.

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