# Configuration

RedGit configuration is stored in `.redgit/config.yaml` in your project root.

---

## Full Configuration Reference

```yaml
# ============================================
# Active Integrations
# ============================================
# Set which integration to use for each type
active:
  task_management: jira      # jira | linear | asana | none
  code_hosting: github       # github | gitlab | bitbucket | none
  ci_cd: github-actions      # github-actions | gitlab-ci | jenkins | none
  notification: slack        # slack | discord | telegram | none
  code_quality: sonarqube    # sonarqube | snyk | codecov | none

# ============================================
# Workflow Settings
# ============================================
workflow:
  # Branching strategy
  strategy: local-merge      # local-merge | merge-request

  # Auto-transition issues through statuses
  auto_transition: true

  # What to do with changes that don't match an issue
  create_missing_issues: ask # ask | auto | skip

  # Default issue type when creating new issues
  default_issue_type: task   # task | bug | story

# ============================================
# LLM Configuration
# ============================================
llm:
  # LLM provider
  provider: claude-code      # claude-code | qwen-code | openai | ollama

  # Model override (optional)
  model: null                # e.g., gpt-4, qwen2.5-coder:7b

  # Custom API endpoint (for ollama or custom servers)
  endpoint: null             # e.g., http://localhost:11434

# ============================================
# Plugins
# ============================================
plugins:
  enabled:
    - laravel
    - version
    - changelog

  # Plugin-specific settings
  laravel:
    enabled: true

  version:
    enabled: true
    current: "1.0.0"
    tag_prefix: "v"
    files:
      - pyproject.toml
      - package.json

  changelog:
    enabled: true
    output_dir: changelogs
    group_by_type: true

# ============================================
# Integration Configurations
# ============================================
integrations:
  # --- Jira ---
  jira:
    site: https://your-domain.atlassian.net
    email: you@example.com
    project_key: PROJ
    board_type: scrum        # scrum | kanban | none
    board_id: null           # Auto-detected if empty
    story_points_field: customfield_10016
    branch_pattern: "feature/{issue_key}-{description}"
    # token: Use JIRA_API_TOKEN env var

  # --- GitHub ---
  github:
    owner: username
    repo: reponame
    default_base: main
    auto_pr: false
    # token: Use GITHUB_TOKEN env var

  # --- GitLab ---
  gitlab:
    url: https://gitlab.com
    project_id: "12345"      # or "group/project"
    default_base: main
    # token: Use GITLAB_TOKEN env var

  # --- GitHub Actions ---
  github-actions:
    owner: username
    repo: reponame
    # token: Use GITHUB_TOKEN env var

  # --- Jenkins ---
  jenkins:
    url: https://jenkins.company.com
    username: your-username
    job_name: my-pipeline
    # token: Use JENKINS_API_TOKEN env var

  # --- Slack ---
  slack:
    webhook_url: https://hooks.slack.com/services/xxx
    channel: "#dev-notifications"

  # --- Discord ---
  discord:
    webhook_url: https://discord.com/api/webhooks/xxx

  # --- SonarQube ---
  sonarqube:
    host: https://sonarcloud.io
    project_key: my-project
    organization: my-org
    # token: Use SONAR_TOKEN env var
```

---

## Environment Variables

Sensitive data should be stored in environment variables:

| Integration | Variable | Description |
|-------------|----------|-------------|
| Jira | `JIRA_API_TOKEN` | Jira API token |
| GitHub | `GITHUB_TOKEN` | Personal access token |
| GitLab | `GITLAB_TOKEN` | GitLab access token |
| Jenkins | `JENKINS_API_TOKEN` | Jenkins API token |
| Linear | `LINEAR_API_KEY` | Linear API key |
| SonarQube | `SONAR_TOKEN` | SonarQube token |
| Snyk | `SNYK_TOKEN` | Snyk API token |
| OpenAI | `OPENAI_API_KEY` | OpenAI API key |
| Anthropic | `ANTHROPIC_API_KEY` | Anthropic API key |

### Using Environment Variables in Config

```yaml
integrations:
  jira:
    token: ${JIRA_API_TOKEN}   # Resolved at runtime
```

---

## Workflow Strategies

### local-merge (Default)

Feature branches are merged immediately into your current branch.

```yaml
workflow:
  strategy: local-merge
```

Best for: Solo developers, small teams, fast iteration.

### merge-request

Feature branches are kept for pull request workflows.

```yaml
workflow:
  strategy: merge-request
```

Best for: Teams with code review, CI/CD pipelines.

See [Workflows](workflows.md) for detailed comparison.

---

## LLM Providers

### Claude Code

```yaml
llm:
  provider: claude-code
```

Requires: `npm install -g @anthropic-ai/claude-code`

### Qwen Code

```yaml
llm:
  provider: qwen-code
```

Requires: `npm install -g @anthropic-ai/qwen-code`

### OpenAI

```yaml
llm:
  provider: openai
  model: gpt-4
```

Requires: `OPENAI_API_KEY` environment variable

### Ollama (Local)

```yaml
llm:
  provider: ollama
  model: qwen2.5-coder:7b
  endpoint: http://localhost:11434
```

Requires: Ollama installed with model pulled

---

## Branch Patterns

Customize branch naming:

```yaml
integrations:
  jira:
    branch_pattern: "feature/{issue_key}-{description}"
```

Available placeholders:
- `{issue_key}` - e.g., PROJ-123
- `{description}` - Slugified issue title
- `{issue_type}` - e.g., task, bug, story

Examples:
- `feature/PROJ-123-add-login`
- `bugfix/PROJ-456-fix-crash`

---

## Custom Prompts

Override AI prompts in `.redgit/prompts/`:

```
.redgit/
├── config.yaml
└── prompts/
    ├── default.md         # Main grouping prompt
    ├── quality_prompt.md  # Quality check prompt
    └── laravel.md         # Framework-specific
```

Use with:

```bash
rg propose -p my-prompt
```

---

## Config Commands

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

## Project-Specific Config

Each project has its own `.redgit/config.yaml`. This allows different settings per project.

### Global Defaults

For global defaults, create `~/.redgit/config.yaml`:

```yaml
# ~/.redgit/config.yaml (global defaults)
llm:
  provider: claude-code

# Project configs override these
```

---

## Minimal Config

The minimum required configuration:

```yaml
llm:
  provider: claude-code
```

Everything else has sensible defaults.

---

## See Also

- [Getting Started](getting-started.md)
- [Commands Reference](commands.md)
- [Integrations](integrations/index.md)
- [Workflows](workflows.md)