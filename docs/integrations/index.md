# Integrations

Integrations extend RedGit with external services for task management, code hosting, CI/CD, notifications, and code quality analysis.

---

## Integration Types

| Type                | Purpose                         | Examples                   |
|---------------------|--------------------------------|----------------------------|
| **Task Management** | Issue tracking, sprint management | Jira, Linear, Asana        |
| **Code Hosting**    | PRs, branches, repository ops  | GitHub, GitLab, Bitbucket  |
| **CI/CD**           | Pipelines, builds, deployments | GitHub Actions, Jenkins    |
| **Notifications**   | Alerts, messages               | Slack, Discord, Telegram   |
| **Code Quality**    | Analysis, security scanning    | SonarQube, Snyk            |

---

## How Integrations Work

1. **Install** - Download integration from tap
2. **Configure** - Set credentials and options in config
3. **Activate** - Set as active for its type
4. **Use** - RedGit automatically uses active integrations

### Active Integrations

Only one integration per type can be active at a time:

```yaml
# .redgit/config.yaml
active:
  task_management: jira      # Used by rg propose, rg push
  code_hosting: github       # Used by rg push --pr
  ci_cd: github-actions      # Used by rg push --ci
  notification: slack        # Used for all notifications
```

---

## Installing Integrations

All integrations are available from [RedGit Tap](../tap.md):

```bash
# List available integrations
rg integration list --all

# Install an integration
rg install jira

# Check what's installed
rg integration list
```

See [RedGit Tap Documentation](../tap.md) for:
- Full list of available integrations
- Installation commands
- Configuration examples
- Environment variables

---

## Creating Custom Integrations

You can create custom integrations for internal tools. Place them in `.redgit/integrations/`:

```
.redgit/integrations/my-integration/
├── __init__.py          # Integration class (required)
├── install_schema.json  # Installation wizard (optional)
└── commands.py          # CLI commands (optional)
```

See [Custom Integration Guide](custom.md) for detailed instructions.

---

## See Also

- [RedGit Tap](../tap.md) - Browse and install integrations
- [Custom Integrations](custom.md) - Create your own
- [Configuration](../configuration.md) - Full config reference