# Contributing to RedGit

First off, thank you for considering contributing to RedGit! It's people like you that make RedGit such a great tool.

## Code of Conduct

By participating in this project, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the [existing issues](https://github.com/ertiz82/redgit/issues) to avoid duplicates.

When you create a bug report, include as many details as possible:

- **RedGit version** (`rg --version`)
- **Python version** (`python --version`)
- **Operating system**
- **Steps to reproduce**
- **Expected behavior**
- **Actual behavior**
- **Error messages** (if any)

### Suggesting Features

Feature requests are welcome! Please:

1. Check if the feature has already been requested
2. Open an issue with the `enhancement` label
3. Describe the feature and why it would be useful
4. Provide examples of how it would work

### Creating Integrations

Want to add support for a new tool? Check out our [Custom Integration Guide](docs/integrations/custom.md).

You can either:
- Create a personal integration and share it via GitHub
- Submit a PR to [RedGit Tap](https://github.com/ertiz82/redgit-tap) for official inclusion

### Pull Requests

1. **Fork the repo** and create your branch from `main`
2. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```
3. **Make your changes**
4. **Test your changes**:
   ```bash
   # Run linter
   ruff check redgit/

   # Test manually
   rg --help
   ```
5. **Commit your changes** using conventional commits:
   ```
   feat: add new feature
   fix: resolve bug
   docs: update documentation
   refactor: code improvement
   ```
6. **Push and create a Pull Request**

## Development Setup

### Prerequisites

- Python 3.9+
- Git

### Local Installation

```bash
# Clone the repo
git clone https://github.com/ertiz82/redgit.git
cd redgit

# Install in development mode
pip install -e .

# Verify installation
rg --version
```

### Project Structure

```
redgit/
├── cli.py              # Main CLI entry point
├── commands/           # CLI commands (propose, push, etc.)
├── core/               # Core functionality
├── integrations/       # Integration implementations
├── plugins/            # Plugin system
└── templates/          # Prompt templates
```

### Running Tests

```bash
# Lint check
ruff check redgit/

# Type check (optional)
mypy redgit/
```

## Style Guide

- Follow PEP 8
- Use type hints where possible
- Write docstrings for public functions
- Keep functions focused and small

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `refactor:` Code change that neither fixes a bug nor adds a feature
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

## Questions?

Feel free to open an issue with the `question` label or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.