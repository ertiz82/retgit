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
- **Task Management Integration**: Matches changes with Jira/Linear issues
- **Smart Branch Naming**: Creates branches based on issue keys
- **Workflow Automation**: Transitions issues through statuses
- **Plugin System**: Framework-specific prompts (Laravel, Vue, etc.)

---

## Installation

```bash
# Using Homebrew (macOS/Linux) - Recommended
brew tap ertiz82/tap
brew install redgit

# Using pip
pip install redgit
```

After installation, use either `redgit` or the short alias `rg`.

---

## Quick Start

```bash
# Initialize in your project
rg init

# Make changes to your code, then analyze and commit
rg propose

# Push and complete issues
rg push
```

---

## Documentation

| Section | Description |
|---------|-------------|
| **[Getting Started](docs/getting-started.md)** | Installation and first steps |
| **[Commands Reference](docs/commands.md)** | All CLI commands |
| **[Configuration](docs/configuration.md)** | Config file options |
| **[Integrations](docs/integrations/index.md)** | Task management, code hosting, CI/CD |
| **[Plugins](docs/plugins/index.md)** | Framework plugins and release management |
| **[Workflows](docs/workflows.md)** | Local merge vs merge request strategies |
| **[Troubleshooting](docs/troubleshooting.md)** | Common issues and solutions |

---

## RedGit Tap - Community Integrations

> **[RedGit Tap](https://github.com/ertiz82/redgit-tap)** provides 30+ additional integrations.

```bash
rg install linear      # Task management
rg install slack       # Notifications
rg install sonarqube   # Code quality
```

See the full list at **[github.com/ertiz82/redgit-tap](https://github.com/ertiz82/redgit-tap)**

---

## License

MIT License - see [LICENSE](LICENSE) for details.

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