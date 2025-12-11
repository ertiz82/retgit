<p align="center">
  <img src="https://raw.githubusercontent.com/ertiz82/redgit/main/assets/logo.svg?v=11" alt="RedGit Logo" width="400"/>
</p>

<p align="center">
  <strong>AI-powered Git workflow assistant with task management integration</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/redgit/"><img src="https://img.shields.io/pypi/v/redgit.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/redgit/"><img src="https://img.shields.io/pypi/dm/redgit.svg" alt="Downloads"></a>
  <a href="https://pypi.org/project/redgit/"><img src="https://img.shields.io/pypi/pyversions/redgit.svg" alt="Python versions"></a>
  <a href="https://github.com/ertiz82/redgit/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="https://github.com/ertiz82/redgit/stargazers"><img src="https://img.shields.io/github/stars/ertiz82/redgit.svg" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#integrations">Integrations</a>
</p>

---

## What is RedGit?

RedGit analyzes your code changes, groups them logically, matches them with your active tasks (Jira, Linear, etc.), and creates well-structured commits automatically.

**Stop writing commit messages manually.** Let AI understand your changes and create meaningful commits that link to your issues.

```bash
# Before: Manual workflow
git add .
git commit -m "fix: resolve login issue PROJ-123"
git push

# After: RedGit workflow
rg propose   # AI analyzes, groups, and commits
rg push      # Push and update Jira/Linear
```

---

## Demo

<!-- TODO: Add demo GIF showing rg propose and push in action -->
<p align="center">
  <img src="https://raw.githubusercontent.com/ertiz82/redgit/main/assets/rg_propose.png" alt="RedGit Propose" width="500"/>
<img src="https://raw.githubusercontent.com/ertiz82/redgit/main/assets/rg_push.png" alt="RedGit Push" width="500"/>
</p>

---

## Features

| Feature | Description |
|---------|-------------|
| **AI-Powered Grouping** | Automatically groups related file changes into logical commits |
| **Task Management** | Integrates with Jira, Linear, Asana, Trello, and more |
| **Smart Branching** | Creates branches based on issue keys (`feature/PROJ-123-description`) |
| **Auto Transitions** | Moves issues through workflow statuses (To Do → In Progress → Done) |
| **PR Creation** | Automatically creates pull requests with proper descriptions |
| **Code Quality** | Built-in quality checks with ruff/flake8 + AI analysis |
| **Semgrep Integration** | Multi-language static analysis (35+ languages) for security & best practices |
| **CI/CD Integration** | Trigger and monitor pipelines from the command line |
| **Plugin System** | Framework-specific prompts (Laravel, Django, etc.) |

---

## Why RedGit?

| | RedGit | Commitizen | Manual |
|---|:---:|:---:|:---:|
| AI-powered commit messages | ✅ | ❌ | ❌ |
| Groups related changes | ✅ | ❌ | ❌ |
| Task management integration | ✅ | ❌ | ❌ |
| Auto branch creation | ✅ | ❌ | ❌ |
| Issue status transitions | ✅ | ❌ | ❌ |
| PR creation | ✅ | ❌ | ❌ |
| Multi-language static analysis | ✅ | ❌ | ❌ |
| Works with any LLM | ✅ | - | - |

---

## Installation

```bash
# Using Homebrew (macOS/Linux) - Recommended
brew tap ertiz82/tap
brew install redgit

# Using pip
pip install redgit

# Using pipx (isolated environment)
pipx install redgit
```

After installation, use either `redgit` or the short alias `rg`.

---

## Quick Start

```bash
# 1. Initialize in your project
rg init

# 2. Make changes to your code...

# 3. Let AI analyze and create commits
rg propose

# 4. Push and complete issues
rg push
```

### With Jira Integration

```bash
# Setup Jira
rg integration install jira

# Your workflow
rg propose        # AI matches changes with your Jira issues
rg push           # Push and transition issues to Done
```

### With GitHub PRs

```bash
# Setup GitHub
rg integration install github

# Create commits and PRs
rg propose
rg push --pr      # Creates pull requests automatically
```

---

## Integrations

RedGit supports 30+ integrations across different categories:

| Category | Integrations |
|----------|-------------|
| **Task Management** | Jira, Linear, Asana, Trello, Notion |
| **Code Hosting** | GitHub, GitLab, Bitbucket, Azure Repos |
| **CI/CD** | GitHub Actions, GitLab CI, Jenkins, CircleCI |
| **Notifications** | Slack, Discord, Telegram, MS Teams |
| **Code Quality** | SonarQube, Snyk, Codecov, Codacy |

Install integrations from [RedGit Tap](https://github.com/ertiz82/redgit-tap):

```bash
rg install linear
rg install slack
rg install sonarqube
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
| **[Custom Integrations](docs/integrations/custom.md)** | Build your own integrations |
| **[Troubleshooting](docs/troubleshooting.md)** | Common issues and solutions |

---

## LLM Support

RedGit works with multiple LLM providers:

- **Claude Code** - Anthropic's Claude (recommended)
- **OpenAI** - GPT-4, GPT-3.5
- **Ollama** - Local models (Qwen, Llama, etc.)
- **Any OpenAI-compatible API**

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- Report bugs via [GitHub Issues](https://github.com/ertiz82/redgit/issues)
- Submit integrations to [RedGit Tap](https://github.com/ertiz82/redgit-tap)

---

## Support

If you find RedGit useful, consider supporting the project:

<a href="https://buymeacoffee.com/ertiz"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support-yellow?logo=buy-me-a-coffee&logoColor=white" alt="Buy Me a Coffee"></a>

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <img src="https://raw.githubusercontent.com/ertiz82/redgit/main/assets/red-kit.png?v=2" alt="Red Kit - RedGit Mascot" width="120"/>
</p>

<p align="center">
  <em>"Gölgenden hızlı commit at, Red Git!"</em>
</p>

<p align="center">
  <strong>Made with ❤️ for developers who want smarter commits</strong>
</p>