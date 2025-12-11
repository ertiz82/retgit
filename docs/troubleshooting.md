# Troubleshooting

Common issues and their solutions.

---

## Installation Issues

### "Command not found: rg"

After installing with pip/pipx, the command may not be in PATH.

**Solution:**

```bash
# For pipx
pipx ensurepath

# Or manually add to ~/.zshrc or ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"

# Then restart terminal or
source ~/.zshrc
```

### Conflict with ripgrep

Both RedGit and ripgrep use the `rg` command.

**Solution:**

```bash
# Option 1: Use the full command
redgit --help

# Option 2: Add alias to ~/.zshrc or ~/.bashrc
alias rg='/opt/homebrew/opt/redgit/bin/rg'  # Homebrew
# or
alias rg="$HOME/.local/bin/rg"              # pip/pipx

# To access ripgrep when needed
$(brew --prefix ripgrep)/bin/rg
```

---

## LLM Issues

### "LLM not found"

No LLM provider is configured or installed.

**Solution:**

Install one of the supported providers:

```bash
# Option 1: Claude Code (Recommended)
npm install -g @anthropic-ai/claude-code

# Option 2: Qwen Code
npm install -g @anthropic-ai/qwen-code

# Option 3: OpenAI API
export OPENAI_API_KEY="your-api-key"

# Option 4: Ollama (Local)
# Install from https://ollama.ai
ollama pull qwen2.5-coder:7b
```

### LLM Response Timeout

The AI is taking too long to respond.

**Solution:**

```bash
# Try a faster/smaller model with Ollama
ollama pull qwen2.5-coder:3b

# Or use a different provider
rg config set llm.provider openai
```

---

## Git Issues

### "No changes found"

RedGit can't find any uncommitted changes.

**Solution:**

```bash
# Check for changes
git status

# Make sure you have unstaged changes
git diff
```

### SSH Push Hangs

`rg push` hangs when pushing via SSH.

**Solution:**

```bash
# Ensure SSH agent is running
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa

# Or use HTTPS instead
git remote set-url origin https://github.com/user/repo.git
```

### Merge Conflicts During Propose

Conflicts when merging feature branches (local-merge strategy).

**Solution:**

```bash
# Resolve conflicts manually
git status
# Edit conflicted files
git add .
git commit

# Or switch to merge-request strategy
rg config set workflow.strategy merge-request
```

---

## Integration Issues

### Jira Connection Failed

Can't connect to Jira.

**Checklist:**

1. Site URL includes `https://`
   ```yaml
   # Correct
   site: https://company.atlassian.net

   # Wrong
   site: company.atlassian.net
   ```

2. API token is valid
   - Create new token at [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

3. Project key is correct (case-sensitive)
   ```yaml
   project_key: PROJ  # Not "proj" or "Proj"
   ```

4. Environment variable is set
   ```bash
   export JIRA_API_TOKEN="your-token"
   ```

### GitHub Token Issues

GitHub integration not working.

**Solution:**

```bash
# Set token
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"

# Verify token has correct scopes
# Required: repo (Full control of private repositories)
```

### Integration Status Shows "Disabled"

Integration is configured but shows as disabled.

**Solution:**

Check that the integration is set as active:

```yaml
# .redgit/config.yaml
active:
  task_management: jira    # Must match integration name
  code_hosting: github

integrations:
  jira:
    # ... config
```

---

## Quality Check Issues

### Linter Not Found

`rg quality check` says no linter found.

**Solution:**

```bash
# Install ruff (recommended)
pip install ruff

# Or flake8
pip install flake8
```

### Quality Check Gives False Positives

AI is flagging things that aren't issues.

**Solution:**

Override the quality prompt in `.redgit/prompts/quality_prompt.md`:

```markdown
# Code Quality Check

Focus on:
- Syntax errors
- Security vulnerabilities
- Critical bugs

DO NOT flag:
- Style preferences
- Minor optimizations
- Personal coding choices
```

---

## Configuration Issues

### Config Not Loading

Changes to config aren't taking effect.

**Solution:**

```bash
# Check config path
ls -la .redgit/config.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('.redgit/config.yaml'))"

# View current config
rg config show
```

### Environment Variables Not Working

Environment variables in config aren't being read.

**Solution:**

Use the `${VAR}` syntax:

```yaml
# .redgit/config.yaml
integrations:
  jira:
    token: ${JIRA_API_TOKEN}  # Correct
    # token: $JIRA_API_TOKEN  # Wrong
```

---

## Session Issues

### Stale Session Data

Old session data causing issues.

**Solution:**

```bash
# Clear session
rm -rf .redgit/session/

# Or push/complete current session first
rg push
```

---

## Performance Issues

### Slow Analysis

`rg propose` is slow.

**Solutions:**

1. Use a faster LLM
   ```bash
   # Use smaller Ollama model
   ollama pull qwen2.5-coder:3b
   rg config set llm.model qwen2.5-coder:3b
   ```

2. Reduce number of files
   ```bash
   # Commit in smaller batches
   git add src/feature/
   rg propose
   ```

3. Skip task management
   ```bash
   rg propose --no-task
   ```

---

## Getting More Help

### Debug Mode

Run with verbose output:

```bash
rg propose -v
rg push -v
```

### Check Versions

```bash
rg --version
python --version
git --version
```

### Report Issues

If you're still stuck:

1. Check [GitHub Issues](https://github.com/ertiz82/redgit/issues)
2. Create a new issue with:
   - RedGit version
   - Python version
   - OS
   - Error message
   - Steps to reproduce

---

## See Also

- [Getting Started](getting-started.md)
- [Configuration](configuration.md)
- [Commands Reference](commands.md)