# Getting Started

This guide will help you install RedGit and make your first AI-powered commit.

---

## Requirements

- Python 3.9+
- Git
- One of the supported LLM providers

---

## Installation

### Using Homebrew (macOS/Linux) - Recommended

```bash
brew tap ertiz82/tap
brew install redgit
```

### Using pipx (Isolated Environment)

```bash
pipx install redgit
```

### Using pip

```bash
pip install redgit
```

### From Source

```bash
git clone https://github.com/ertiz82/redgit.git
cd redgit
pip install -e .
```

---

## PATH Setup

If you see "command not found" after installation:

```bash
# For pipx
pipx ensurepath

# Or manually add to ~/.zshrc or ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"
```

Then restart your terminal.

---

## Verify Installation

```bash
# Either command works
redgit --version
rg --version
```

> **Note:** If you have ripgrep installed, both tools use `rg`. See [Troubleshooting](troubleshooting.md) for alias setup.

---

## LLM Provider Setup

RedGit needs an LLM to analyze your code. Choose one:

### Option 1: Claude Code (Recommended)

```bash
npm install -g @anthropic-ai/claude-code
```

### Option 2: Qwen Code

```bash
npm install -g @anthropic-ai/qwen-code
```

### Option 3: OpenAI API

```bash
export OPENAI_API_KEY="your-api-key"
```

### Option 4: Ollama (Local, Free)

```bash
# Install from https://ollama.ai
ollama pull qwen2.5-coder:7b
```

---

## Quick Start

### 1. Initialize RedGit

```bash
cd your-project
rg init
```

The interactive wizard will configure:
- LLM provider
- Task management integration (optional)
- Plugins
- Workflow settings

### 2. Make Some Changes

Edit your code as usual:

```bash
vim src/feature.py
vim tests/test_feature.py
```

### 3. Analyze and Commit

```bash
rg propose
```

RedGit will:
1. Detect all file changes
2. Analyze with AI
3. Group related files
4. Match with active issues (if configured)
5. Create branches and commits

### 4. Push

```bash
rg push
```

---

## Configuration

After `rg init`, your config is in `.redgit/config.yaml`:

```yaml
# LLM provider
llm:
  provider: claude-code

# Workflow strategy
workflow:
  strategy: local-merge

# Active integrations (optional)
active:
  task_management: jira
  code_hosting: github
```

See [Configuration](configuration.md) for all options.

---

## Adding Integrations

### Task Management (Jira, Linear, etc.)

```bash
rg integration install jira
```

Or from RedGit Tap:

```bash
rg install linear
rg install asana
```

### Code Hosting (GitHub, GitLab)

```bash
rg integration install github
```

### Notifications (Slack, Discord)

```bash
rg install slack
rg install discord
```

---

## Workflow Examples

### Solo Developer

```bash
# Make changes
vim src/app.py

# Let AI group and commit
rg propose

# Push to remote
rg push
```

### With Jira Integration

```bash
# Changes are matched to your active Jira issues
rg propose

# Push and transition issues to Done
rg push
```

### Specific Task

```bash
# Commit all changes to one task
rg propose --task PROJ-123
rg push
```

### Team with PRs

```bash
# Configure merge-request strategy
rg config set workflow.strategy merge-request

# Make changes
rg propose

# Push and create PRs
rg push --pr
```

---

## Next Steps

- [Commands Reference](commands.md) - All CLI commands
- [Configuration](configuration.md) - Detailed config options
- [Integrations](integrations/index.md) - Task management, CI/CD
- [Plugins](plugins/index.md) - Framework plugins
- [Workflows](workflows.md) - Local merge vs merge request

---

## Need Help?

- [Troubleshooting](troubleshooting.md) - Common issues
- [GitHub Issues](https://github.com/ertiz82/redgit/issues) - Report bugs