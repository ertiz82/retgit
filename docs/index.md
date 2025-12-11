# RedGit Documentation

Welcome to the RedGit documentation. RedGit is an AI-powered Git workflow assistant that analyzes your code changes, groups them logically, matches them with your active tasks, and creates well-structured commits automatically.

## Quick Navigation

| Section | Description |
|---------|-------------|
| [Getting Started](getting-started.md) | Installation and first steps |
| [Commands Reference](commands.md) | All CLI commands |
| [Configuration](configuration.md) | Config file options |
| [Integrations](integrations/index.md) | Task management, code hosting, CI/CD |
| [Plugins](plugins/index.md) | Framework plugins and release management |
| [Workflows](workflows.md) | Local merge vs merge request strategies |
| [RedGit Tap](tap.md) | Community integrations repository |
| [Troubleshooting](troubleshooting.md) | Common issues and solutions |

---

## Overview

### What RedGit Does

1. **Analyzes** your uncommitted changes
2. **Groups** related files using AI
3. **Matches** changes with your active issues (Jira, Linear, etc.)
4. **Creates** branches and commits for each group
5. **Transitions** issues through workflow statuses
6. **Pushes** and optionally creates pull requests

### Core Commands

```bash
rg init      # Initialize RedGit in your project
rg propose   # Analyze changes and create commits
rg push      # Push branches and complete issues
```

### Integration Types

| Type | Purpose | Examples |
|------|---------|----------|
| Task Management | Issue tracking | Jira, Linear, Asana |
| Code Hosting | Git hosting, PRs | GitHub, GitLab |
| CI/CD | Pipelines, builds | GitHub Actions, Jenkins |
| Notifications | Alerts, messages | Slack, Discord |
| Code Quality | Analysis, scanning | SonarQube, Snyk |

---

## Documentation Structure

```
docs/
├── index.md                 # This file
├── getting-started.md       # Installation and quick start
├── commands.md              # CLI command reference
├── configuration.md         # Config file options
├── integrations/
│   ├── index.md            # All integrations overview
│   ├── jira.md             # Jira integration
│   ├── github.md           # GitHub integration
│   ├── scout.md            # Scout AI integration
│   └── custom.md           # Custom integration guide
├── plugins/
│   ├── index.md            # Plugin overview
│   ├── laravel.md          # Laravel plugin
│   ├── version.md          # Version plugin
│   └── changelog.md        # Changelog plugin
├── workflows.md            # Workflow strategies
├── tap.md                  # RedGit Tap docs
└── troubleshooting.md      # Common issues
```

---

## Need More Integrations?

Check out **[RedGit Tap](https://github.com/ertiz82/redgit-tap)** - the official repository for community integrations with 30+ integrations including Linear, Notion, Slack, Discord, SonarQube, and more.

```bash
rg install slack
rg install linear
rg install sonarqube
```

---

## Getting Help

- **GitHub Issues**: [github.com/ertiz82/redgit/issues](https://github.com/ertiz82/redgit/issues)
- **Troubleshooting**: [troubleshooting.md](troubleshooting.md)