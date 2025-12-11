<p align="center">
  <img src="https://raw.githubusercontent.com/ertiz82/redgit/main/assets/logo.svg?v=9" alt="RedGit Logo" width="400"/>
</p>

<p align="center">
  <strong>AI-powered Git workflow assistant with task management integration</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/redgit/"><img src="https://img.shields.io/pypi/v/redgit.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/redgit/"><img src="https://img.shields.io/pypi/pyversions/redgit.svg" alt="Python versions"></a>
  <a href="https://github.com/ertiz82/redgit/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="https://buymeacoffee.com/ertiz"><img src="https://img.shields.io/badge/Support-Buy%20Me%20a%20Coffee-yellow" alt="Donate"></a>
</p>

---

RedGit analyzes your code changes, groups them logically, matches them with your active tasks (Jira, Linear, etc.), and creates well-structured commits automatically.

## Features

- **AI-Powered Grouping**: Automatically groups related file changes
- **Task Management Integration**: Matches changes with active Jira/Linear issues
- **Smart Branch Naming**: Creates branches based on issue keys
- **Auto Issue Creation**: Creates new issues for unmatched changes
- **Workflow Automation**: Transitions issues through statuses automatically
- **Plugin System**: Framework-specific prompts (Laravel, Vue, etc.)
- **Security**: Never commits sensitive files (.env, credentials, etc.)

---

## Installation

### Requirements

- Python 3.9+
- Git
- One of the supported LLM providers

### Install RedGit

```bash
# Using Homebrew (macOS/Linux) - Recommended
brew tap ertiz82/tap
brew install redgit

# Using pipx (isolated environment)
pipx install redgit

# Using pip (all platforms)
pip install redgit

# From source
git clone https://github.com/ertiz82/redgit.git
cd redgit
pip install -e .
```

> **Note:** If you see a warning about PATH after installation with pip/pipx, run:
> ```bash
> # For pipx
> pipx ensurepath
>
> # Or manually add to ~/.zshrc or ~/.bashrc:
> export PATH="$HOME/.local/bin:$PATH"
> ```
> Then restart your terminal.

After installation, you can use either `redgit` or the short alias `rg`:

```bash
redgit --help
# or
rg --help
```

> **Note:** If you have [ripgrep](https://github.com/BurntSushi/ripgrep) installed, both tools use the `rg` command. To use RedGit's `rg`, add an alias to your shell config:
> ```bash
> # Add to ~/.zshrc or ~/.bashrc
> alias rg='/opt/homebrew/opt/redgit/bin/rg'  # Homebrew
> # or
> alias rg="$HOME/.local/bin/rg"              # pip/pipx
> ```

### LLM Provider Setup

RedGit supports multiple LLM providers. Choose one:

#### Option 1: Claude Code (Recommended)
```bash
npm install -g @anthropic-ai/claude-code
```

#### Option 2: Qwen Code
```bash
npm install -g @anthropic-ai/qwen-code
```

#### Option 3: OpenAI API
```bash
export OPENAI_API_KEY="your-api-key"
```

#### Option 4: Ollama (Local)
```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5-coder:7b
```

---

## Quick Start

```bash
# 1. Initialize in your project
cd your-project
rg init

# 2. Make some changes to your code
# ...

# 3. Analyze and create commits
rg propose

# 4. Push and complete issues
rg push
```

---

## Commands

### `rg init`

Initialize RedGit in your project. Creates `.redgit/config.yaml`.

```bash
rg init
```

Interactive wizard will help you configure:
- LLM provider selection
- Task management integration (Jira, etc.)
- Plugins (Laravel, Vue, etc.)
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

**What it does:**
1. Detects all file changes in your repo
2. Fetches your active issues from task management
3. Uses AI to group files and match with issues
4. Creates branches and commits for each group
5. Transitions issues to "In Progress"

**Using `--task` flag:**

When you know which task you're working on, use `--task` to skip AI analysis and commit all changes directly:

```bash
# Using just the issue number (project key added automatically)
rg propose --task 123
# → Creates branch: feature/PROJ-123-issue-title
# → Commits all changes with "PROJ-123: Issue Title"

# Using full issue key
rg propose -t PROJ-123
```

This is useful when:
- You're working on a single task
- You want to skip AI analysis
- You want all changes in one commit

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

# Push without triggering CI (even if integration active)
rg push --no-ci
```

### `rg ci`

CI/CD pipeline management.

```bash
# Show CI/CD status
rg ci status

# List recent pipelines
rg ci pipelines
rg ci pipelines --branch main --limit 20

# Show pipeline details
rg ci pipeline 12345

# List jobs in a pipeline
rg ci jobs 12345

# Trigger a new pipeline
rg ci trigger
rg ci trigger --branch main --workflow build

# Watch a pipeline until completion
rg ci watch 12345

# Cancel/retry a pipeline
rg ci cancel 12345
rg ci retry 12345

# View pipeline logs
rg ci logs 12345 --tail 100
```

### `rg integration`

Manage integrations.

```bash
# List available integrations
rg integration list

# Install an integration
rg integration install jira

# Show integration status
rg integration status
```

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

## Configuration

Configuration is stored in `.redgit/config.yaml`:

```yaml
# Active integrations by type
active:
  task_management: jira      # jira | linear | none
  code_hosting: github       # github | gitlab | none
  ci_cd: github-actions      # github-actions | gitlab-ci | jenkins | none
  notification: slack        # slack | discord | none

# Workflow settings
workflow:
  strategy: local-merge      # local-merge | merge-request
  auto_transition: true      # Auto-move issues through statuses
  create_missing_issues: ask # ask | auto | skip
  default_issue_type: task   # Default type for new issues

# LLM configuration
llm:
  provider: claude-code      # claude-code | qwen-code | openai | ollama
  model: null                # Model override (optional)

# Plugins
plugins:
  enabled:
    - laravel

# Integration configurations
integrations:
  jira:
    site: https://your-domain.atlassian.net
    email: you@example.com
    project_key: PROJ
    board_type: scrum        # scrum | kanban | none
    # token: stored in JIRA_API_TOKEN env var

  github:
    owner: username
    repo: reponame
    default_base: main
    # token: stored in GITHUB_TOKEN env var
```

---

## Integrations

### Task Management

#### Jira

Full Jira Cloud support with Scrum/Kanban boards.

**Setup:**
```bash
rg integration install jira
```

**Required fields:**
- `site`: Your Jira site URL (e.g., `https://company.atlassian.net`)
- `email`: Your Jira account email
- `project_key`: Project key (e.g., `PROJ`, `SCRUM`)
- `token`: API token ([Create here](https://id.atlassian.com/manage-profile/security/api-tokens))

**Features:**
- Fetch active issues assigned to you
- Match commits with issues
- Add comments to issues on commit
- Transition issues (To Do → In Progress → Done)
- Sprint support for Scrum boards
- Auto-detect board ID

**Config example:**
```yaml
integrations:
  jira:
    site: https://company.atlassian.net
    email: dev@company.com
    project_key: PROJ
    board_type: scrum
    story_points_field: customfield_10016  # Optional
```

### Code Hosting

#### GitHub

GitHub integration for PR creation.

**Setup:**
```bash
rg integration install github
```

**Required fields:**
- `owner`: Repository owner (username or org)
- `repo`: Repository name
- `token`: Personal Access Token ([Create here](https://github.com/settings/tokens))

**Features:**
- Create pull requests
- Link PRs with issues

### CI/CD

RedGit supports various CI/CD platforms to manage pipelines directly from the command line.

#### Available CI/CD Integrations

| Integration | Description |
|-------------|-------------|
| `github-actions` | GitHub Actions workflows |
| `gitlab-ci` | GitLab CI/CD pipelines |
| `jenkins` | Jenkins jobs and builds |
| `circleci` | CircleCI pipelines |
| `travis-ci` | Travis CI builds |
| `azure-pipelines` | Azure DevOps pipelines |
| `bitbucket-pipelines` | Bitbucket Pipelines |
| `drone-ci` | Drone CI builds |

#### Setup

```bash
# Install a CI/CD integration
rg install github-actions
rg install gitlab-ci
rg install jenkins
```

#### GitHub Actions Example

```yaml
integrations:
  github-actions:
    owner: your-username
    repo: your-repo
    # token: stored in GITHUB_TOKEN env var
```

#### Jenkins Example

```yaml
integrations:
  jenkins:
    url: https://jenkins.company.com
    username: your-username
    # token: stored in JENKINS_API_TOKEN env var
```

#### Features

- **Pipeline Management**: List, view, trigger, cancel, and retry pipelines
- **Real-time Status**: Watch pipelines until completion
- **Log Viewing**: View build logs directly in terminal
- **Auto-trigger on Push**: Optionally trigger pipelines after `rg push`
- **Notifications**: Get notified when pipelines complete (with notification integration)

#### Usage with Push

```bash
# Push and trigger CI/CD pipeline
rg push --ci

# Push and wait for pipeline to complete
rg push --ci --wait-ci

# Push without triggering CI (even if integration is active)
rg push --no-ci
```

---

## Plugins

Plugins provide framework-specific prompts for better AI understanding.

### Available Plugins

| Plugin | Description |
|--------|-------------|
| `laravel` | Laravel/PHP projects |
| `vue` | Vue.js projects |
| `react` | React projects |
| `django` | Django/Python projects |

### Enable a Plugin

```bash
rg plugin enable laravel
```

Or in config:
```yaml
plugins:
  enabled:
    - laravel
```

### Using Plugin Prompts

```bash
# Use plugin's prompt directly
rg propose -p laravel
```

### Creating Custom Plugins

Create `.redgit/plugins/my-plugin.py`:

```python
class MyPlugin:
    name = "my-plugin"

    def get_prompt(self):
        return """
        You are analyzing a MyFramework project.

        Group files by:
        - Controllers in app/Http/Controllers
        - Models in app/Models
        - Views in resources/views

        {{FILES}}
        """
```

---

## Documentation

For detailed documentation, see:

- **[Integrations Guide](docs/integrations.md)** - Task management, code hosting, CI/CD, notifications, and code quality integrations
- **[Plugins Guide](docs/plugins.md)** - Framework plugins and release management
- **[Workflow Strategies](docs/workflow-strategies.md)** - Local merge vs merge request strategies

### Additional Integrations

Looking for more integrations? Check out **[RedGit Tap](https://github.com/ertiz82/redgit-tap)** - the official repository for community integrations and plugins.

```bash
# Install integrations from the tap
rg install slack
rg install linear
rg install sonarqube
```

---

## Security

RedGit automatically excludes sensitive files from:
1. Being sent to AI
2. Being committed

### Always Excluded

```
.redgit/              # Config directory
.env, .env.*           # Environment files
*.pem, *.key           # Private keys
credentials.*, secrets.* # Credential files
id_rsa, id_ed25519     # SSH keys
*.sqlite, *.db         # Databases
```

### Sensitive Warnings

These files trigger warnings but aren't blocked:
```
config.json, config.yaml
settings.json
appsettings.json
application.properties
```

---

## Workflow Strategies

### Local Merge (Default)

Branches are merged locally into your base branch, then pushed.

```
feature/PROJ-123-add-auth  ─┐
feature/PROJ-124-fix-bug   ─┼─► dev (merged) ─► push
feature/PROJ-125-update-ui ─┘
```

**Best for:** Solo developers, small teams

### Merge Request

Each branch is pushed separately, PRs are created.

```
feature/PROJ-123-add-auth  ─► push ─► PR
feature/PROJ-124-fix-bug   ─► push ─► PR
feature/PROJ-125-update-ui ─► push ─► PR
```

**Best for:** Teams with code review requirements

Set in config:
```yaml
workflow:
  strategy: merge-request  # or local-merge
```

---

## Custom Prompts

Create custom prompts in `.redgit/prompts/`:

**`.redgit/prompts/my-prompt.md`:**
```markdown
# My Custom Prompt

Analyze the following file changes and group them logically.

## Rules
- Group by feature
- Keep tests with their implementations
- Separate refactoring from features

## Files
{{FILES}}
```

Use it:
```bash
rg propose -p my-prompt
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `JIRA_API_TOKEN` | Jira API token |
| `GITHUB_TOKEN` | GitHub personal access token |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |

---

## Troubleshooting

### "No changes found"
Make sure you have uncommitted changes:
```bash
git status
```

### "LLM not found"
Install a supported LLM provider:
```bash
npm install -g @anthropic-ai/claude-code
```

### SSH Push Issues
If `rg push` hangs, ensure your SSH agent is running:
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa
```

### Jira Connection Issues
1. Verify your site URL includes `https://`
2. Check API token is valid
3. Ensure project key is correct (case-sensitive)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

---

<p align="center">
  <img src="https://raw.githubusercontent.com/ertiz82/redgit/main/assets/red-kit.png?v=2" alt="Red Kit - RedGit Mascot" width="150"/>
</p>

<p align="center">
  <em>"Gölgenden hızlı commit at, Red Git!"</em>
</p>

<p align="center">
  <strong>Made with love for developers who want smarter commits</strong>
</p>